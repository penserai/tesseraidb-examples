/**
 * Reactive Controller for Robot Simulation
 * =========================================
 *
 * This controller uses PDDL-style predicates to describe the world state,
 * but evaluates action preconditions DIRECTLY instead of calling a planner.
 *
 * Key insight: For real-time robotics, we need "what's the best action NOW?"
 * not "what sequence of actions reaches the goal?" - a fundamentally different question.
 *
 * Architecture:
 * - World state represented as PDDL-style predicates
 * - Action preconditions checked directly (O(1) per action)
 * - Simple heuristics select the best valid action
 * - No planning search needed for per-tick decisions
 *
 * This approach is:
 * - Fast: O(1) per tick instead of O(exponential) planning
 * - Predictable: Same state always produces same action
 * - Debuggable: Clear precondition checks
 */

import { Position, WorldObject, Obstacle } from "./types";
import { Robot } from "./robot";

// World state interface matching SimulationWorld's worldState structure
export interface WorldState {
  width: number;
  height: number;
  robots: Robot[];
  objects: WorldObject[];
  obstacles: Obstacle[];
  homePosition: Position;
}

// ============================================================================
// Types
// ============================================================================

export interface ReactiveAction {
  action: "Move" | "Collect" | "Recharge" | "Wait";
  target: Position | null;
  objectId?: string;
}

interface WorldPredicates {
  // Robot state
  robotAt: Map<string, string>;        // robotId -> locationId
  lowBattery: Set<string>;             // robotIds with low battery
  carrying: Map<string, string>;       // robotId -> objectId

  // Location state
  obstacles: Set<string>;              // locationIds that are obstacles
  robotBlocking: Set<string>;          // locationIds blocked by robots
  bases: Set<string>;                  // locationIds that are bases
  homePositions: Map<string, string>;  // robotId -> home locationId

  // Object state
  objectAt: Map<string, string>;       // objectId -> locationId
  collected: Set<string>;              // objectIds that are collected

  // Adjacency graph
  adjacent: Map<string, Set<string>>;  // locationId -> adjacent locationIds
}

// ============================================================================
// Predicate Extraction
// ============================================================================

const GRID_RESOLUTION = 1; // meters per cell

function posToLoc(pos: Position): string {
  const gx = Math.floor(pos.x / GRID_RESOLUTION);
  const gy = Math.floor(pos.y / GRID_RESOLUTION);
  return `loc_${gx}_${gy}`;
}

function getAdjacentLocs(loc: string): string[] {
  const parts = loc.split("_");
  const gx = parseInt(parts[1]);
  const gy = parseInt(parts[2]);
  return [
    `loc_${gx - 1}_${gy}`,
    `loc_${gx + 1}_${gy}`,
    `loc_${gx}_${gy - 1}`,
    `loc_${gx}_${gy + 1}`,
  ];
}

/**
 * Extract PDDL-style predicates from world state.
 * This is a pure function - same world always produces same predicates.
 */
export function extractPredicates(world: WorldState): WorldPredicates {
  const predicates: WorldPredicates = {
    robotAt: new Map(),
    lowBattery: new Set(),
    carrying: new Map(),
    obstacles: new Set(),
    robotBlocking: new Set(),
    bases: new Set(),
    homePositions: new Map(),
    objectAt: new Map(),
    collected: new Set(),
    adjacent: new Map(),
  };

  // Extract robot predicates
  for (const robot of world.robots) {
    const loc = posToLoc(robot.position);
    predicates.robotAt.set(robot.id, loc);

    if (robot.battery < 20) {
      predicates.lowBattery.add(robot.id);
    }

    // All active robots block their cell (for other robots)
    if (robot.isActive) {
      predicates.robotBlocking.add(loc);
    }
  }

  // Extract obstacle predicates
  for (const obs of world.obstacles) {
    const radiusCells = Math.ceil(obs.radius / GRID_RESOLUTION) + 1;
    const cx = Math.floor(obs.position.x / GRID_RESOLUTION);
    const cy = Math.floor(obs.position.y / GRID_RESOLUTION);

    for (let dx = -radiusCells; dx <= radiusCells; dx++) {
      for (let dy = -radiusCells; dy <= radiusCells; dy++) {
        const gx = cx + dx;
        const gy = cy + dy;
        const cellCenterX = (gx + 0.5) * GRID_RESOLUTION;
        const cellCenterY = (gy + 0.5) * GRID_RESOLUTION;
        const dist = Math.sqrt(
          (cellCenterX - obs.position.x) ** 2 +
          (cellCenterY - obs.position.y) ** 2
        );
        if (dist < obs.radius + GRID_RESOLUTION * 0.5) {
          predicates.obstacles.add(`loc_${gx}_${gy}`);
        }
      }
    }
  }

  // Extract object predicates
  for (const obj of world.objects) {
    if (obj.collected) {
      predicates.collected.add(obj.id);
    } else {
      predicates.objectAt.set(obj.id, posToLoc(obj.position));
    }
  }

  // Base/home positions
  const baseLoc = posToLoc(world.homePosition);
  predicates.bases.add(baseLoc);

  // Calculate per-robot home positions (offset from base)
  for (let i = 0; i < world.robots.length; i++) {
    const robot = world.robots[i];
    const offset = calculateHomeOffset(i);
    const baseX = Math.floor(world.homePosition.x / GRID_RESOLUTION);
    const baseY = Math.floor(world.homePosition.y / GRID_RESOLUTION);
    const homeLoc = `loc_${baseX + offset.dx}_${baseY + offset.dy}`;
    predicates.homePositions.set(robot.id, homeLoc);
    predicates.bases.add(homeLoc);
  }

  // Build adjacency graph for the relevant area
  // (We build this lazily based on robot positions)
  const relevantLocs = new Set<string>();
  for (const robot of world.robots) {
    const loc = posToLoc(robot.position);
    relevantLocs.add(loc);
    for (const adj of getAdjacentLocs(loc)) {
      relevantLocs.add(adj);
    }
  }

  for (const loc of relevantLocs) {
    const adjSet = new Set<string>();
    for (const adj of getAdjacentLocs(loc)) {
      adjSet.add(adj);
    }
    predicates.adjacent.set(loc, adjSet);
  }

  return predicates;
}

function calculateHomeOffset(robotIndex: number): { dx: number; dy: number } {
  // Spread robots around the base in a pattern
  const offsets = [
    { dx: 0, dy: 0 },
    { dx: 1, dy: 0 },
    { dx: 0, dy: 1 },
    { dx: -1, dy: 0 },
    { dx: 0, dy: -1 },
  ];
  return offsets[robotIndex % offsets.length];
}

// ============================================================================
// Action Precondition Checks
// ============================================================================

/**
 * Check if a robot can collect an object.
 * Preconditions:
 *   - Robot is at the object's location
 *   - Object is not already collected
 *   - Robot does not have low battery
 */
function canCollect(
  robotId: string,
  objectId: string,
  predicates: WorldPredicates
): boolean {
  const robotLoc = predicates.robotAt.get(robotId);
  const objectLoc = predicates.objectAt.get(objectId);

  if (!robotLoc || !objectLoc) return false;
  if (robotLoc !== objectLoc) return false;
  if (predicates.collected.has(objectId)) return false;
  if (predicates.lowBattery.has(robotId)) return false;

  return true;
}

/**
 * Check if a robot can recharge.
 * Preconditions:
 *   - Robot is at a base location
 *   - Robot has low battery
 */
function canRecharge(
  robotId: string,
  predicates: WorldPredicates
): boolean {
  const robotLoc = predicates.robotAt.get(robotId);
  if (!robotLoc) return false;

  if (!predicates.bases.has(robotLoc)) return false;
  if (!predicates.lowBattery.has(robotId)) return false;

  return true;
}

// ============================================================================
// Heuristic Action Selection
// ============================================================================

/**
 * Get the best action for a robot using reactive rule evaluation.
 *
 * SIMPLIFIED: Only handles immediate actions (collect, recharge).
 * Returns null for movement to trigger fallback exploration.
 *
 * Priority:
 * 1. If at base with low battery → Recharge
 * 2. If at object location → Collect
 * 3. Everything else → null (use fallback exploration)
 */
export function getReactiveAction(
  world: WorldState,
  robotId: string
): ReactiveAction | null {
  const predicates = extractPredicates(world);
  const robot = world.robots.find((r: Robot) => r.id === robotId);
  if (!robot) {
    return null;
  }

  const robotLoc = predicates.robotAt.get(robotId);
  if (!robotLoc) {
    return null;
  }

  // 1. Recharge if at base with low battery
  if (canRecharge(robotId, predicates)) {
    return { action: "Recharge", target: null };
  }

  // 2. Collect object at current location
  for (const [objId, objLoc] of predicates.objectAt) {
    if (objLoc === robotLoc && canCollect(robotId, objId, predicates)) {
      return { action: "Collect", target: null, objectId: objId };
    }
  }

  // 3. All movement uses fallback (has better exploration/path-finding)
  return null;
}

// ============================================================================
// Debugging / Diagnostics
// ============================================================================

/**
 * Get a human-readable summary of the predicates for debugging.
 */
export function predicatesToString(predicates: WorldPredicates): string {
  const lines: string[] = [];

  lines.push("=== World Predicates ===");

  lines.push("\nRobot positions:");
  for (const [id, loc] of predicates.robotAt) {
    const lowBatt = predicates.lowBattery.has(id) ? " (LOW BATTERY)" : "";
    lines.push(`  ${id} at ${loc}${lowBatt}`);
  }

  lines.push("\nBlocked cells:");
  lines.push(`  Obstacles: ${Array.from(predicates.obstacles).slice(0, 10).join(", ")}${predicates.obstacles.size > 10 ? "..." : ""}`);
  lines.push(`  Robot blocking: ${Array.from(predicates.robotBlocking).join(", ")}`);

  lines.push("\nObjects:");
  for (const [id, loc] of predicates.objectAt) {
    lines.push(`  ${id} at ${loc}`);
  }
  if (predicates.collected.size > 0) {
    lines.push(`  Collected: ${Array.from(predicates.collected).join(", ")}`);
  }

  return lines.join("\n");
}
