/**
 * SimulationWorld - Main simulation container and logic.
 * Supports both ontology-driven and PDDL planning-driven robot control.
 */

import { Robot } from "./robot";
import { KnownWorld } from "./known-world";
import { OntologyStore } from "./ontology-store";
import { BehaviorParameters } from "./ontology-schema";
import { PlanningController, PlanningAction } from "./planning-controller";
import { getReactiveAction, ReactiveAction } from "./reactive-controller";
import {
  Position,
  WorldObject,
  Obstacle,
  Pheromone,
  PheromoneType,
  PHEROMONE_CONFIG,
  distance,
  RobotState,
  AvoidanceInfo,
} from "./types";

export class SimulationWorld {
  width: number;
  height: number;
  robots: Robot[] = [];
  objects: WorldObject[] = [];
  obstacles: Obstacle[] = [];
  pheromones: Pheromone[] = [];
  knownWorlds: Map<string, KnownWorld> = new Map();
  ontology: OntologyStore;
  currentTick: number = 0;
  homePosition: Position;

  // Optional PDDL planning controller (for validation/high-level planning only)
  private planningController: PlanningController | null = null;
  private pendingPlanActions: Map<string, PlanningAction | null> = new Map();

  // Reactive control mode - uses direct rule evaluation instead of planning
  private useReactiveControl: boolean = true;

  constructor(width: number, height: number) {
    this.width = width;
    this.height = height;
    this.homePosition = { x: width / 2, y: height / 2 };
    this.ontology = new OntologyStore();
  }

  /**
   * Initialize the world with random entities.
   */
  initialize(
    numRobots: number,
    numObjects: number,
    numObstacles: number,
    batteryCapacity: number = 100
  ): void {
    this.robots = [];
    this.objects = [];
    this.obstacles = [];
    this.pheromones = [];
    this.knownWorlds.clear();
    this.currentTick = 0;

    // Create robots
    for (let i = 0; i < numRobots; i++) {
      const pos = this.getRandomPosition(2);
      const robot = new Robot(
        `robot${i + 1}`,
        pos,
        Math.random() * 360,
        i,
        1.0,
        3.0,
        batteryCapacity,
        batteryCapacity
      );
      this.robots.push(robot);
      this.knownWorlds.set(robot.id, new KnownWorld(robot.id));
    }

    // Create objects
    for (let i = 0; i < numObjects; i++) {
      const pos = this.getRandomPosition(1);
      this.objects.push({
        id: `obj${i + 1}`,
        position: pos,
        value: 1 + Math.random() * 2,
        collected: false,
      });
    }

    // Create obstacles
    for (let i = 0; i < numObstacles; i++) {
      const pos = this.getRandomPosition(1);
      this.obstacles.push({
        id: `obs${i + 1}`,
        position: pos,
        radius: 0.4 + Math.random() * 0.3,
      });
    }

    // Initialize ontology
    this.ontology.initializeWorld(this.robots, this.objects, this.obstacles);
  }

  private getRandomPosition(margin: number): Position {
    return {
      x: margin + Math.random() * (this.width - 2 * margin),
      y: margin + Math.random() * (this.height - 2 * margin),
    };
  }

  /**
   * Run one simulation tick.
   */
  tick(): void {
    this.currentTick++;

    // Decay pheromones
    this.decayPheromones();

    // Process each robot
    for (const robot of this.robots) {
      if (!robot.isActive) continue;

      robot.tickCount = this.currentTick;
      const known = this.knownWorlds.get(robot.id)!;

      // Drain battery each tick (rate from ontology)
      robot.battery = Math.max(0, robot.battery - this.params.detection.batteryDrainRate);
      if (robot.battery <= 0) {
        robot.isActive = false;
        robot.currentAction = "Battery depleted";
        continue;
      }

      // 1. SENSE - Discover nearby entities
      this.senseEnvironment(robot, known);

      // 2. UPDATE ONTOLOGY - Push sensor data
      const distToNearest = this.getDistanceToNearestObject(robot);
      const distToObstacle = this.getDistanceToNearestObstacle(robot);
      this.ontology.updateRobotState(robot, known, distToNearest, distToObstacle);

      // 3. REASON - Query state with inference
      const state = this.ontology.queryRobotState(robot.id);

      // 4. ACT - Determine and execute action
      // Check if PDDL planning provides an action
      if (this.hasPlanningAction(robot.id)) {
        const planAction = this.getPendingPlanAction(robot.id);
        if (planAction) {
          this.executePlanningAction(robot, planAction);
        }
      } else {
        // Fall back to ontology-driven decision
        const { action, target, avoidance } = this.determineAction(robot, known, state);
        this.executeAction(robot, known, action, target, avoidance);
      }

      // Update stuck state
      robot.updateStuckState();
      robot.updateWanderlust(this.width, this.height);

      // Record exploration
      known.recordExploration(robot.position);
    }
  }

  private senseEnvironment(robot: Robot, known: KnownWorld): void {
    // Discover objects within sensor range
    for (const obj of this.objects) {
      if (!obj.collected && distance(robot.position, obj.position) <= robot.sensorRange) {
        if (!known.hasDiscoveredObject(obj.id)) {
          known.discoverObject(obj);
          robot.resetDiscoveryTimer();

          // Deposit object_found pheromone
          this.depositPheromone(robot, PheromoneType.OBJECT_FOUND);
        }
      }
    }

    // Discover obstacles within sensor range
    for (const obs of this.obstacles) {
      if (distance(robot.position, obs.position) <= robot.sensorRange + obs.radius) {
        known.discoverObstacle(obs);
      }
    }
  }

  private getDistanceToNearestObject(robot: Robot): number {
    let minDist = 999;
    for (const obj of this.objects) {
      if (!obj.collected) {
        const d = distance(robot.position, obj.position);
        if (d < minDist) minDist = d;
      }
    }
    return minDist;
  }

  private getDistanceToNearestObstacle(robot: Robot): number {
    let minDist = 999;
    for (const obs of this.obstacles) {
      const d = distance(robot.position, obs.position) - obs.radius;
      if (d < minDist) minDist = d;
    }
    return minDist;
  }

  private determineAction(
    robot: Robot,
    known: KnownWorld,
    state: RobotState
  ): { action: string; target: Position | null; avoidance: AvoidanceInfo } {
    const avoidance: AvoidanceInfo = {
      mustAvoid: state.mustAvoid,
      avoidLeft: false,
      avoidRight: false,
      clearPathAngle: 0,
      emergencyAvoid: state.emergencyAvoid,
      inLoop: state.inLoop,
      stuckCounter: known.stuckCounter,
      escapeMode: false,
      escapeTicks: 0,
      coverageArea: state.coverageArea,
    };

    // Priority 1: Handle collision
    if (state.collision || robot.hasCollision) {
      robot.hasCollision = false;
    }

    // Priority 2: At object -> Collect IMMEDIATELY
    const pickup = this.checkObjectPickup(robot);
    if (pickup) {
      return { action: "Collect", target: pickup.position, avoidance };
    }

    // Priority 3: Object visible in sensor range -> Move to it directly
    const visibleObject = this.getVisibleObject(robot);
    if (visibleObject) {
      // Clear escape mode if we see an object - object collection is priority
      if (known.escapeMode) {
        known.clearEscapeMode();
      }
      return { action: "MoveToObject", target: visibleObject.position, avoidance };
    }

    // Priority 4: Low battery -> Return home
    if (state.lowBattery) {
      // Calculate offset to avoid clumping at home
      // Robots with higher index get offset positions around home
      const homeOffset = this.getHomeOffset(robot);
      const target: Position = {
        x: this.homePosition.x + homeOffset.x,
        y: this.homePosition.y + homeOffset.y,
      };

      // If stuck while returning home, add random jitter to escape clump
      if (robot.isStuck && robot.ticksWithoutMovement > 2) {
        const jitterAngle = Math.random() * Math.PI * 2;
        const jitterDist = 1.5 + Math.random() * 1.5;
        target.x += Math.cos(jitterAngle) * jitterDist;
        target.y += Math.sin(jitterAngle) * jitterDist;

        // Clamp to world bounds
        target.x = Math.max(1, Math.min(this.width - 1, target.x));
        target.y = Math.max(1, Math.min(this.height - 1, target.y));
      }

      return { action: "ReturnHome", target, avoidance };
    }

    // Priority 5: Move to nearest KNOWN object (discovered earlier, not currently visible)
    const nearestKnown = known.getNearestKnownObject(robot.position);
    if (nearestKnown) {
      // Update known object's collected status from world state
      const worldObj = this.objects.find(o => o.id === nearestKnown.id);
      if (worldObj && !worldObj.collected) {
        return { action: "MoveToObject", target: nearestKnown.position, avoidance };
      } else {
        // Object was collected, remove from known
        known.discoveredObjects.delete(nearestKnown.id);
      }
    }

    // Priority 6: ESCAPE MODE (persistent) - only when no objects to collect
    // Escape parameters from ontology
    const escapeParams = this.params.escape;
    const actionParams = this.params.action;

    if (known.escapeMode && known.escapeTarget) {
      const distToTarget = distance(robot.position, known.escapeTarget);
      let distFromClutter = 999;

      if (known.clutterCentroid) {
        distFromClutter = distance(robot.position, known.clutterCentroid);
      }

      // Check if escape is complete (thresholds from ontology)
      if (distToTarget < escapeParams.targetReachedDistance ||
          distFromClutter > escapeParams.clutterClearDistance ||
          known.escapeTicksRemaining <= 0) {
        known.clearEscapeMode();
      } else {
        known.escapeTicksRemaining--;
        avoidance.escapeMode = true;
        avoidance.escapeTicks = known.escapeTicksRemaining;
        return { action: "Explore", target: known.escapeTarget, avoidance };
      }
    }

    // Priority 7: Enter escape mode if stuck/circling
    const shouldEscape = state.shouldVenture || state.severelyCircling || state.inLoop;

    if (shouldEscape && !known.escapeMode) {
      // Escape direction: opposite + randomness (parameters from ontology)
      const baseAngle = (robot.heading + escapeParams.baseAngleOffset) % 360;
      const randomness = (Math.random() - 0.5) * (escapeParams.angleVariance * 2);
      const escapeAngle = ((baseAngle + randomness) * Math.PI) / 180;

      const escapeDist = Math.max(
        escapeParams.minDistance,
        Math.min(this.width, this.height) / escapeParams.distanceFactor
      );

      const margin = actionParams.worldBoundaryMargin;
      const targetX = Math.max(margin, Math.min(this.width - margin, robot.position.x + escapeDist * Math.cos(escapeAngle)));
      const targetY = Math.max(margin, Math.min(this.height - margin, robot.position.y + escapeDist * Math.sin(escapeAngle)));

      known.escapeMode = true;
      known.escapeTarget = { x: targetX, y: targetY };
      known.escapeTicksRemaining = escapeParams.tickDuration;
      known.clutterCentroid = { x: robot.position.x, y: robot.position.y };

      avoidance.escapeMode = true;
      avoidance.escapeTicks = escapeParams.tickDuration;

      return { action: "Explore", target: known.escapeTarget, avoidance };
    }

    // Priority 8: Explore - pick a fresh direction
    const exploreAngle = this.getExploreDirection(robot, known);
    const exploreTarget: Position = {
      x: robot.position.x + Math.cos((exploreAngle * Math.PI) / 180) * 5,
      y: robot.position.y + Math.sin((exploreAngle * Math.PI) / 180) * 5,
    };

    return { action: "Explore", target: exploreTarget, avoidance };
  }

  private getVisibleObject(robot: Robot): WorldObject | null {
    let nearest: WorldObject | null = null;
    let nearestDist = Infinity;

    for (const obj of this.objects) {
      if (obj.collected) continue;
      const dist = distance(robot.position, obj.position);
      if (dist <= robot.sensorRange && dist < nearestDist) {
        nearest = obj;
        nearestDist = dist;
      }
    }

    return nearest;
  }

  /**
   * Get behavior parameters from ontology.
   * This is the key to language-agnostic implementations.
   */
  get params(): BehaviorParameters {
    return this.ontology.params;
  }

  /**
   * Exploration direction using parameters from ontology.
   * All scoring weights are queried from the ontology, not hardcoded.
   */
  private getExploreDirection(robot: Robot, known: KnownWorld): number {
    const p = this.params.exploration;
    const centerX = this.width / 2;
    const centerY = this.height / 2;

    // Which quadrant is robot in?
    const inLeft = robot.position.x < centerX;
    const inBottom = robot.position.y < centerY;

    let bestDirection = Math.random() * 360;
    let bestScore = -Infinity;

    // Sample directions (count from ontology)
    for (let i = 0; i < p.directionSampleCount; i++) {
      const angle = Math.random() * 360;
      const angleRad = (angle * Math.PI) / 180;

      // Project far into that direction (factor from ontology)
      const ventureDist = Math.max(this.width, this.height) / p.ventureDistanceFactor;
      let targetX = robot.position.x + Math.cos(angleRad) * ventureDist;
      let targetY = robot.position.y + Math.sin(angleRad) * ventureDist;

      // Clamp to grid bounds (margin from ontology)
      const margin = Math.min(this.width, this.height) * p.gridMarginFactor;
      targetX = Math.max(margin, Math.min(this.width - margin, targetX));
      targetY = Math.max(margin, Math.min(this.height - margin, targetY));

      let score = 0;

      // Quadrant crossing bonus (from ontology)
      const targetInLeft = targetX < centerX;
      const targetInBottom = targetY < centerY;
      if (targetInLeft !== inLeft) {
        score += p.quadrantCrossingBonus;
      }
      if (targetInBottom !== inBottom) {
        score += p.quadrantCrossingBonus;
      }

      // Center approach bonus when at edges (from ontology)
      const distToCenterNow = Math.sqrt(
        (robot.position.x - centerX) ** 2 + (robot.position.y - centerY) ** 2
      );
      const distToCenterTarget = Math.sqrt(
        (targetX - centerX) ** 2 + (targetY - centerY) ** 2
      );
      if (distToCenterNow > Math.min(this.width, this.height) * p.edgeDistanceThreshold) {
        if (distToCenterTarget < distToCenterNow) {
          score += p.centerApproachBonus;
        }
      }

      // Unexplored target bonus (from ontology)
      const targetCell = `${Math.round(targetX)},${Math.round(targetY)}`;
      if (!known.exploredPositions.has(targetCell)) {
        score += p.unexploredTargetBonus;
      }

      // Path exploration bonus (from ontology)
      let pathExplored = 0;
      for (const t of [0.25, 0.5, 0.75]) {
        const checkX = Math.round(robot.position.x + (targetX - robot.position.x) * t);
        const checkY = Math.round(robot.position.y + (targetY - robot.position.y) * t);
        if (known.exploredPositions.has(`${checkX},${checkY}`)) {
          pathExplored++;
        }
      }
      score += (3 - pathExplored) * p.unexploredPathBonus;

      // Distance bonus (from ontology)
      const dist = Math.sqrt(
        (targetX - robot.position.x) ** 2 + (targetY - robot.position.y) ** 2
      );
      score += dist * p.distanceBonusMultiplier;

      // Same quadrant penalty (from ontology)
      if (targetInLeft === inLeft && targetInBottom === inBottom) {
        score -= p.sameQuadrantPenalty;
      }

      if (score > bestScore) {
        bestScore = score;
        bestDirection = (Math.atan2(targetY - robot.position.y, targetX - robot.position.x) * 180) / Math.PI;
      }
    }

    return bestDirection;
  }

  private executeAction(
    robot: Robot,
    known: KnownWorld,
    action: string,
    target: Position | null,
    avoidance: AvoidanceInfo
  ): void {
    if (action === "Collect" && target) {
      const obj = this.checkObjectPickup(robot);
      if (obj) {
        this.collectObject(robot, obj);
        const knownObj = known.discoveredObjects.get(obj.id);
        if (knownObj) knownObj.collected = true;
        this.ontology.markObjectCollected(obj.id);
        robot.currentAction = `Collected ${obj.id}`;
        return;
      }
    }

    if (action === "MoveToObject" && target) {
      // Direct movement to objects - no gradual turns
      this.moveToward(robot, target, avoidance, true);
      const dist = distance(robot.position, target);
      robot.currentAction = `Moving to object (${dist.toFixed(1)} away)`;
    } else if (action === "ReturnHome" && target) {
      this.moveToward(robot, target, avoidance, true);
      robot.currentAction = `Returning home (battery: ${robot.battery.toFixed(0)}%)`;
    } else if (action === "Explore" && target) {
      this.moveToward(robot, target, avoidance, false);

      if (avoidance.escapeMode) {
        robot.currentAction = `ESCAPE (${robot.heading.toFixed(0)}°), area=${avoidance.coverageArea.toFixed(1)}, ticks=${avoidance.escapeTicks}`;
      } else {
        robot.currentAction = `Exploring (${robot.heading.toFixed(0)}°)`;
      }

      // Deposit exploration pheromone
      if (this.currentTick % PHEROMONE_CONFIG[PheromoneType.EXPLORATION].depositInterval === 0) {
        this.depositPheromone(robot, PheromoneType.EXPLORATION);
      }
    } else {
      robot.currentAction = "Idle";
    }

    // Handle collision
    if (robot.hasCollision) {
      this.depositPheromone(robot, PheromoneType.DANGER);
    }
  }

  private findClearDirectionToward(robot: Robot, target: Position): number {
    const p = this.params.action;
    const targetAngle = (Math.atan2(target.y - robot.position.y, target.x - robot.position.x) * 180) / Math.PI;

    // Randomize whether to try left or right first
    const preferLeft = Math.random() > 0.5;
    const baseOffsets = [0, 30, 60, 90, 120, 150, 180];
    const offsets: number[] = [];

    for (const o of baseOffsets) {
      if (preferLeft) {
        offsets.push(-o);
        if (o !== 0 && o !== 180) offsets.push(o);
      } else {
        offsets.push(o);
        if (o !== 0 && o !== 180) offsets.push(-o);
      }
    }

    // Add some randomness to each test angle (jitter from ontology)
    const robotAvoidRadius = 1.5; // Distance to keep from other robots

    for (const offset of offsets) {
      const randomJitter = (Math.random() - 0.5) * p.avoidanceJitter;
      const testAngle = targetAngle + offset + randomJitter;
      const rad = (testAngle * Math.PI) / 180;
      const checkX = robot.position.x + Math.cos(rad) * p.avoidanceCheckDistance;
      const checkY = robot.position.y + Math.sin(rad) * p.avoidanceCheckDistance;

      let clear = true;

      // Check obstacles
      for (const obs of this.obstacles) {
        if (distance({ x: checkX, y: checkY }, obs.position) < obs.radius + p.obstacleBuffer) {
          clear = false;
          break;
        }
      }

      // Check other robots
      if (clear) {
        for (const other of this.robots) {
          if (other.id !== robot.id && other.isActive) {
            if (distance({ x: checkX, y: checkY }, other.position) < robotAvoidRadius) {
              clear = false;
              break;
            }
          }
        }
      }

      if (clear) {
        return testAngle;
      }
    }

    // Fall back to random turn around (jitter from ontology)
    return robot.heading + 180 + (Math.random() - 0.5) * p.turnAroundJitter;
  }

  private checkObstacleAhead(robot: Robot, target: Position): boolean {
    const p = this.params.action;
    const rad = Math.atan2(target.y - robot.position.y, target.x - robot.position.x);

    const checkX = robot.position.x + Math.cos(rad) * p.avoidanceCheckDistance;
    const checkY = robot.position.y + Math.sin(rad) * p.avoidanceCheckDistance;

    for (const obs of this.obstacles) {
      if (distance({ x: checkX, y: checkY }, obs.position) < obs.radius + p.obstacleBuffer) {
        return true;
      }
    }

    return false;
  }

  private checkCollision(robot: Robot, newPos: Position): boolean {
    const p = this.params.action;

    // Check obstacle collision (buffer from ontology)
    for (const obs of this.obstacles) {
      if (distance(newPos, obs.position) < obs.radius + p.collisionBuffer) {
        return true;
      }
    }

    // Check robot-to-robot collision
    const robotCollisionRadius = 1.2; // Robots avoid each other within this distance
    for (const other of this.robots) {
      if (other.id !== robot.id && other.isActive) {
        if (distance(newPos, other.position) < robotCollisionRadius) {
          // Record robot collision for stuck detection
          robot.hasRobotCollision = true;
          return true;
        }
      }
    }

    // Check world bounds
    if (newPos.x < 0.5 || newPos.x > this.width - 0.5 || newPos.y < 0.5 || newPos.y > this.height - 0.5) {
      return true;
    }

    return false;
  }

  checkObjectPickup(robot: Robot): WorldObject | null {
    const p = this.params.detection;
    for (const obj of this.objects) {
      if (!obj.collected && distance(robot.position, obj.position) < p.atObjectDistance) {
        return obj;
      }
    }
    return null;
  }

  private depositPheromone(robot: Robot, type: PheromoneType): void {
    this.pheromones.push({
      position: { ...robot.position },
      type,
      strength: PHEROMONE_CONFIG[type].initialStrength,
      depositedBy: robot.id,
      tickDeposited: this.currentTick,
    });
  }

  private decayPheromones(): void {
    this.pheromones = this.pheromones.filter((p) => {
      p.strength -= PHEROMONE_CONFIG[p.type].decayRate;
      return p.strength > 0.1;
    });
  }

  /**
   * Check if simulation is complete (all objects collected).
   */
  isComplete(): boolean {
    return this.objects.every((o) => o.collected);
  }

  /**
   * Get statistics for display.
   */
  getStats(): { totalObjects: number; collectedObjects: number; totalCollisions: number } {
    return {
      totalObjects: this.objects.length,
      collectedObjects: this.objects.filter((o) => o.collected).length,
      totalCollisions: this.robots.reduce((sum, r) => sum + r.collisionCount, 0),
    };
  }

  /**
   * Get a unique offset for each robot's home position to avoid clumping.
   * Robots arrange in a circle around the home base.
   */
  private getHomeOffset(robot: Robot): Position {
    const numRobots = this.robots.length;
    const angle = (robot.robotIndex / numRobots) * Math.PI * 2;
    const radius = 2.0; // Offset distance from center

    return {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
    };
  }

  /**
   * Set the planning controller for PDDL-based decision making.
   */
  setPlanningController(controller: PlanningController | null): void {
    this.planningController = controller;
    this.pendingPlanActions.clear();
  }

  /**
   * Get the planning controller.
   */
  getPlanningController(): PlanningController | null {
    return this.planningController;
  }

  /**
   * Request a plan for a specific robot (async).
   * Called at the start of tick to allow planning to happen in parallel.
   */
  async requestPlanForRobot(robotId: string): Promise<void> {
    if (!this.planningController || !this.planningController.isReady()) {
      return;
    }

    try {
      const worldState = {
        width: this.width,
        height: this.height,
        robots: this.robots,
        objects: this.objects,
        obstacles: this.obstacles,
        homePosition: this.homePosition,
      };

      const action = await this.planningController.getNextAction(worldState, robotId);
      this.pendingPlanActions.set(robotId, action);
    } catch (error) {
      console.error(`[Planning] Error getting plan for ${robotId}:`, error);
      this.pendingPlanActions.set(robotId, null);
    }
  }

  /**
   * Get the pending planned action for a robot.
   */
  getPendingPlanAction(robotId: string): PlanningAction | null {
    return this.pendingPlanActions.get(robotId) || null;
  }

  /**
   * Check if planning is enabled and has a pending action.
   */
  hasPlanningAction(robotId: string): boolean {
    return (
      this.planningController !== null &&
      this.planningController.isReady() &&
      this.pendingPlanActions.has(robotId) &&
      this.pendingPlanActions.get(robotId) !== null
    );
  }

  /**
   * Execute a planned action for a robot.
   *
   * IMPORTANT: In PDDL planning mode, collision avoidance is handled DECLARATIVELY:
   *
   * 1. The problem generator adds (robot-blocking loc_X_Y) facts for other robots
   * 2. The PDDL domain has preconditions: (not (robot-blocking ?to))
   * 3. The planner finds paths that avoid other robots automatically
   * 4. This executor just follows the plan - no procedural collision checks needed
   *
   * This is the power of declarative planning: collision avoidance logic is in the
   * PDDL domain (once), not in every client language (TypeScript, Python, Rust, etc.)
   */
  executePlanningAction(robot: Robot, action: PlanningAction): void {
    const known = this.knownWorlds.get(robot.id)!;
    const noAvoidance: AvoidanceInfo = {
      mustAvoid: false,
      avoidLeft: false,
      avoidRight: false,
      clearPathAngle: 0,
      emergencyAvoid: false,
      inLoop: false,
      stuckCounter: 0,
      escapeMode: false,
      escapeTicks: 0,
      coverageArea: 0,
    };

    switch (action.action) {
      case "Move":
        if (action.target) {
          // Planner already checked (not robot-blocking target) - safe to move
          this.moveToward(robot, action.target, noAvoidance, true);
          robot.currentAction = `[PDDL] Moving to (${action.target.x.toFixed(1)}, ${action.target.y.toFixed(1)})`;
        }
        break;

      case "Collect":
        if (action.objectId) {
          const obj = this.objects.find((o) => o.id === action.objectId);
          if (obj && !obj.collected) {
            const dist = distance(robot.position, obj.position);
            if (dist < this.params.detection.atObjectDistance) {
              this.collectObject(robot, obj);
              const knownObj = known.discoveredObjects.get(obj.id);
              if (knownObj) knownObj.collected = true;
              this.ontology.markObjectCollected(obj.id);
              robot.currentAction = `[PDDL] Collected ${obj.id}`;
            } else {
              this.moveToward(robot, obj.position, noAvoidance, true);
              robot.currentAction = `[PDDL] Approaching ${obj.id}`;
            }
          }
        }
        break;

      case "ReturnHome":
        if (action.target) {
          // Target is robot's unique home position (offset from base)
          // Planner already found collision-free path
          this.moveToward(robot, action.target, noAvoidance, true);
          robot.currentAction = `[PDDL] Returning to home (${action.target.x.toFixed(1)}, ${action.target.y.toFixed(1)})`;
        }
        break;

      case "Recharge":
        robot.battery = robot.batteryCapacity;
        robot.currentAction = `[PDDL] Recharged`;
        break;

      case "Wait":
        // Path is blocked by another robot - the planner determined waiting is optimal
        // This is a key benefit of PDDL: explicit wait actions instead of getting stuck
        robot.currentAction = `[PDDL] Waiting (path blocked)`;
        break;

      case "Idle":
        robot.currentAction = `[PDDL] Idle`;
        break;

      default:
        robot.currentAction = `[PDDL] ${action.action}`;
    }
  }

  // =========================================================================
  // REACTIVE CONTROL
  // =========================================================================
  // Uses direct rule evaluation instead of planning search.
  // Much faster (O(1) vs O(exponential)) and suitable for per-tick decisions.
  // =========================================================================

  /**
   * Enable or disable reactive control mode.
   * When enabled, robots use direct rule evaluation instead of planning.
   */
  setReactiveControl(enabled: boolean): void {
    this.useReactiveControl = enabled;
    console.log(`[Control] Reactive mode: ${enabled ? "ON" : "OFF"}`);
  }

  /**
   * Check if reactive control is enabled.
   */
  isReactiveControlEnabled(): boolean {
    return this.useReactiveControl;
  }

  /**
   * Get and execute reactive action for a robot.
   * Uses reactive control for collect/recharge, falls back to procedural for movement.
   */
  executeReactiveAction(robotId: string): void {
    const robot = this.robots.find((r) => r.id === robotId);
    if (!robot || !robot.isActive) return;

    const known = this.knownWorlds.get(robot.id)!;

    const worldState = {
      width: this.width,
      height: this.height,
      robots: this.robots,
      objects: this.objects,
      obstacles: this.obstacles,
      homePosition: this.homePosition,
    };

    const reactiveAction = getReactiveAction(worldState, robotId);

    if (reactiveAction) {
      // Reactive control handles collect/recharge
      this.executeReactiveActionImpl(robot, reactiveAction);
    } else {
      // Fallback to procedural for movement/exploration
      const state = this.ontology.queryRobotState(robot.id);
      const { action, target, avoidance } = this.determineAction(robot, known, state);
      this.executeAction(robot, known, action, target, avoidance);
    }
  }

  /**
   * Execute a reactive action.
   */
  private executeReactiveActionImpl(robot: Robot, action: ReactiveAction): void {
    const known = this.knownWorlds.get(robot.id)!;
    const noAvoidance: AvoidanceInfo = {
      mustAvoid: false,
      avoidLeft: false,
      avoidRight: false,
      clearPathAngle: 0,
      emergencyAvoid: false,
      inLoop: false,
      stuckCounter: 0,
      escapeMode: false,
      escapeTicks: 0,
      coverageArea: 0,
    };

    switch (action.action) {
      case "Move":
        if (action.target) {
          this.moveToward(robot, action.target, noAvoidance, true);
          robot.currentAction = `Moving to (${action.target.x.toFixed(1)}, ${action.target.y.toFixed(1)})`;
        }
        break;

      case "Collect":
        if (action.objectId) {
          const obj = this.objects.find((o) => o.id === action.objectId);
          if (obj && !obj.collected) {
            this.collectObject(robot, obj);
            const knownObj = known.discoveredObjects.get(obj.id);
            if (knownObj) knownObj.collected = true;
            this.ontology.markObjectCollected(obj.id);
            robot.currentAction = `Collected ${obj.id}`;
          }
        }
        break;

      case "Recharge":
        robot.battery = robot.batteryCapacity;
        robot.currentAction = `Recharged`;
        break;

      case "Wait":
        robot.currentAction = `Waiting`;
        break;
    }
  }

  /**
   * Collect an object (made public for planning actions).
   */
  collectObject(robot: Robot, obj: WorldObject): void {
    obj.collected = true;
    robot.objectsCollected++;
    robot.successMetric += obj.value * 10;
    this.depositPheromone(robot, PheromoneType.OBJECT_COLLECTED);
  }

  /**
   * Move toward a target (made public for planning actions).
   */
  moveToward(robot: Robot, target: Position, avoidance: AvoidanceInfo, direct: boolean = false): void {
    const p = this.params.action;

    // Check for obstacle collision along path to target
    const obstacleAhead = this.checkObstacleAhead(robot, target);

    if (obstacleAhead || avoidance.mustAvoid) {
      // Find clear direction that still moves toward target if possible
      const clearAngle = this.findClearDirectionToward(robot, target);
      robot.turnTo(clearAngle);
    } else {
      // Direct movement toward target - turn immediately to face it
      if (direct) {
        const targetAngle = (Math.atan2(target.y - robot.position.y, target.x - robot.position.x) * 180) / Math.PI;
        robot.turnTo(targetAngle);
      } else {
        // Gradual turn for exploration (rate from ontology)
        robot.turnToward(target, p.turnRateExplore);
      }
    }

    // Check if move is valid
    const rad = (robot.heading * Math.PI) / 180;
    const newX = robot.position.x + Math.cos(rad) * robot.speed;
    const newY = robot.position.y + Math.sin(rad) * robot.speed;

    if (!this.checkCollision(robot, { x: newX, y: newY })) {
      robot.moveForward(this.width, this.height);
    } else {
      robot.hasCollision = true;
      robot.collisionCount++;
    }
  }
}
