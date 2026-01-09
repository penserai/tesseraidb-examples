/**
 * Planning Controller
 *
 * Integrates PDDL planning with the browser simulation.
 * Provides an alternative to the procedural determineAction logic.
 */

import { PlanningClient, Plan, PlanAction } from "./planning-client";
import {
  generateLocalPddlProblem,
  parseLocation,
  gridToWorld,
  WorldState,
} from "./problem-generator";
import { Position } from "./types";

// PDDL Domain (STRIPS version with multi-robot coordination)
// TYPED version - SimplePlanner uses types to efficiently filter ground actions
const DOMAIN_ID = "browser-robot-coordination";

const PDDL_DOMAIN = `(define (domain robot-exploration-coordination)
  (:requirements :strips :typing :negative-preconditions)

  (:types
    robot
    location
    object
  )

  (:predicates
    ; Position predicates
    (at ?r - robot ?l - location)
    (adjacent ?l1 - location ?l2 - location)

    ; Blocking predicates - obstacles and other robots
    (obstacle ?l - location)
    (robot-blocking ?l - location)

    ; Home/base predicates
    (base ?l - location)
    (home-position ?r - robot ?l - location)

    ; Object predicates
    (object-at ?o - object ?l - location)
    (collected ?o - object)
    (carrying ?r - robot ?o - object)

    ; Robot state predicates
    (low-battery ?r - robot)
    (at-base ?r - robot)
    (explored ?r - robot ?l - location)
  )

  ; Move action - respects both obstacles AND other robots
  (:action move
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (not (robot-blocking ?to))
      (not (low-battery ?r))
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (explored ?r ?to)
      (not (at-base ?r))
      (robot-blocking ?to)
      (not (robot-blocking ?from))
    )
  )

  ; Collect action
  (:action collect
    :parameters (?r - robot ?l - location ?o - object)
    :precondition (and
      (at ?r ?l)
      (object-at ?o ?l)
      (not (collected ?o))
      (not (low-battery ?r))
    )
    :effect (and
      (collected ?o)
      (carrying ?r ?o)
      (not (object-at ?o ?l))
    )
  )

  ; Return to robot's assigned home position
  (:action return-to-home
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (not (robot-blocking ?to))
      (low-battery ?r)
      (home-position ?r ?to)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (robot-blocking ?to)
      (not (robot-blocking ?from))
      (at-base ?r)
    )
  )

  ; Move toward home when not adjacent
  (:action move-toward-home
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (not (robot-blocking ?to))
      (low-battery ?r)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (robot-blocking ?to)
      (not (robot-blocking ?from))
    )
  )

  ; Recharge at any base location
  (:action recharge
    :parameters (?r - robot ?l - location)
    :precondition (and
      (at ?r ?l)
      (base ?l)
      (low-battery ?r)
    )
    :effect (and
      (not (low-battery ?r))
      (at-base ?r)
    )
  )

  ; Wait action - when path is blocked by another robot
  (:action wait
    :parameters (?r - robot ?l - location)
    :precondition (at ?r ?l)
    :effect ()
  )
)`;

export interface PlanningAction {
  action: string;
  target: Position | null;
  objectId?: string;
}

export interface PlanningStats {
  planningTimeMs: number;
  statesExplored: number;
  actionsPlanned: number;
  planValid: boolean;
}

export class PlanningController {
  private client: PlanningClient;
  private domainRegistered: boolean = false;
  private lastStats: PlanningStats | null = null;
  private planCache: Map<string, { plan: Plan; timestamp: number }> = new Map();
  private readonly cacheTtlMs = 500; // Cache plans for 500ms

  constructor(baseUrl: string, token?: string) {
    this.client = new PlanningClient({
      baseUrl,
      token,
      timeout: 5000, // 5 second timeout for planning
    });
  }

  /**
   * Check if the controller is ready (domain registered).
   */
  isReady(): boolean {
    return this.domainRegistered;
  }

  /**
   * Initialize the planning controller.
   * Registers the PDDL domain with the server.
   */
  async initialize(): Promise<boolean> {
    try {
      // Check if server is available
      const healthy = await this.client.healthCheck();
      if (!healthy) {
        console.warn("[Planning] Server not available");
        return false;
      }

      // Register domain
      await this.client.createDomain(
        DOMAIN_ID,
        "Browser Robot Exploration Domain",
        PDDL_DOMAIN
      );

      this.domainRegistered = true;
      console.log("[Planning] Domain registered successfully");
      return true;
    } catch (error) {
      console.error("[Planning] Initialization failed:", error);
      return false;
    }
  }

  /**
   * Get the next action for a robot using PDDL planning.
   */
  async getNextAction(
    world: WorldState,
    robotId: string
  ): Promise<PlanningAction | null> {
    if (!this.domainRegistered) {
      return null;
    }

    try {
      // Check cache
      const cacheKey = this.getCacheKey(world, robotId);
      const cached = this.planCache.get(cacheKey);
      if (cached && Date.now() - cached.timestamp < this.cacheTtlMs) {
        return this.planToAction(cached.plan, world, robotId);
      }

      // Generate problem with minimal radius for fast planning
      // Radius of 1 gives us 5 cells (center + 4 orthogonal neighbors)
      // This keeps BFS tractable: ~25 ground move actions per state
      const problemPddl = generateLocalPddlProblem(world, robotId, 1, 1);

      // Get plan from server
      const plan = await this.client.plan(DOMAIN_ID, problemPddl);

      // Debug: log plan details
      console.log(
        `[Planning] ${robotId}: valid=${plan.valid}, actions=${plan.actions.length}, ` +
          `states=${plan.stats.states_explored}, time=${plan.stats.planning_time_ms}ms`
      );
      if (plan.actions.length > 0) {
        console.log(`[Planning] ${robotId}: first action = ${plan.actions[0].name}(${plan.actions[0].parameters.join(", ")})`);
      }

      // Update stats
      this.lastStats = {
        planningTimeMs: plan.stats.planning_time_ms,
        statesExplored: plan.stats.states_explored,
        actionsPlanned: plan.actions.length,
        planValid: plan.valid,
      };

      // Cache the plan
      this.planCache.set(cacheKey, { plan, timestamp: Date.now() });

      // Convert first action to simulation action
      return this.planToAction(plan, world, robotId);
    } catch (error) {
      console.error("[Planning] Error getting action:", error);
      return null;
    }
  }

  /**
   * Convert a PDDL plan to a simulation action.
   */
  private planToAction(
    plan: Plan,
    world: WorldState,
    robotId: string
  ): PlanningAction | null {
    if (!plan.valid) {
      console.warn(`[Planning] ${robotId}: invalid plan`);
      return null;
    }

    if (plan.actions.length === 0) {
      // Goal already satisfied - this shouldn't happen often
      // Return Idle to indicate we're waiting for world state to change
      console.log(`[Planning] ${robotId}: empty plan (goal satisfied), returning Idle`);
      return { action: "Idle", target: null };
    }

    const action = plan.actions[0];
    return this.convertPddlAction(action, world, robotId);
  }

  /**
   * Convert a single PDDL action to simulation action.
   *
   * The planner now handles collision avoidance through robot-blocking
   * predicates, so these actions are safe to execute directly.
   */
  private convertPddlAction(
    pddlAction: PlanAction,
    world: WorldState,
    _robotId: string
  ): PlanningAction {
    switch (pddlAction.name) {
      case "move": {
        // (move robot from to)
        // Precondition already checked (not robot-blocking to)
        const toLoc = pddlAction.parameters[2];
        const { x, y } = parseLocation(toLoc);
        const target = gridToWorld(x, y, 1);
        return { action: "Move", target };
      }

      case "collect": {
        // (collect robot location object)
        const objId = pddlAction.parameters[2];
        const obj = world.objects.find((o) => o.id === objId);
        return {
          action: "Collect",
          target: obj?.position || null,
          objectId: objId,
        };
      }

      case "return-to-home": {
        // (return-to-home robot from to)
        // Robot's unique home position, avoids other robots
        const toLoc = pddlAction.parameters[2];
        const { x, y } = parseLocation(toLoc);
        const target = gridToWorld(x, y, 1);
        return { action: "ReturnHome", target };
      }

      case "move-toward-home": {
        // (move-toward-home robot from to)
        // Moving toward home when not adjacent, avoids other robots
        const toLoc = pddlAction.parameters[2];
        const { x, y } = parseLocation(toLoc);
        const target = gridToWorld(x, y, 1);
        return { action: "ReturnHome", target };
      }

      case "recharge": {
        // (recharge robot location)
        return { action: "Recharge", target: world.homePosition };
      }

      case "wait": {
        // (wait robot location)
        // Path is blocked - wait for other robot to move
        return { action: "Wait", target: null };
      }

      default:
        console.warn(`[Planning] Unknown action: ${pddlAction.name}`);
        return { action: "Idle", target: null };
    }
  }

  /**
   * Generate a cache key for the current world state.
   */
  private getCacheKey(world: WorldState, robotId: string): string {
    const robot = world.robots.find((r) => r.id === robotId);
    if (!robot) return robotId;

    // Key based on robot position and nearby object/obstacle state
    const rx = Math.floor(robot.position.x);
    const ry = Math.floor(robot.position.y);
    const uncollected = world.objects.filter((o) => !o.collected).length;

    return `${robotId}-${rx}-${ry}-${uncollected}`;
  }

  /**
   * Get the last planning statistics.
   */
  getStats(): PlanningStats | null {
    return this.lastStats;
  }

  /**
   * Clear the plan cache.
   */
  clearCache(): void {
    this.planCache.clear();
  }
}
