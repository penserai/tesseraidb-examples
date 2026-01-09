/**
 * PDDL Problem Generator
 *
 * Converts the browser simulation world state into PDDL problem format
 * that can be solved by the planning API.
 */

import { Robot } from "./robot";
import { Position, WorldObject, Obstacle } from "./types";

export interface WorldState {
  width: number;
  height: number;
  robots: Robot[];
  objects: WorldObject[];
  obstacles: Obstacle[];
  homePosition: Position;
}

/**
 * Generate a PDDL problem from the current world state.
 * Uses a grid-based representation for locations.
 */
export function generatePddlProblem(
  world: WorldState,
  robotId: string,
  gridResolution: number = 1
): string {
  const robot = world.robots.find((r) => r.id === robotId);
  if (!robot) {
    throw new Error(`Robot ${robotId} not found`);
  }

  const objects: string[] = [];
  const init: string[] = [];

  // Robot object
  objects.push(`${robotId} - robot`);

  // Generate grid locations
  const gridWidth = Math.ceil(world.width / gridResolution);
  const gridHeight = Math.ceil(world.height / gridResolution);

  for (let x = 0; x < gridWidth; x++) {
    for (let y = 0; y < gridHeight; y++) {
      objects.push(`loc_${x}_${y} - location`);
    }
  }

  // Generate adjacencies (4-connected grid)
  for (let x = 0; x < gridWidth; x++) {
    for (let y = 0; y < gridHeight; y++) {
      const neighbors = [
        [x + 1, y],
        [x - 1, y],
        [x, y + 1],
        [x, y - 1],
      ];

      for (const [nx, ny] of neighbors) {
        if (nx >= 0 && nx < gridWidth && ny >= 0 && ny < gridHeight) {
          init.push(`(adjacent loc_${x}_${y} loc_${nx}_${ny})`);
        }
      }
    }
  }

  // Robot position
  const robotGridX = Math.floor(robot.position.x / gridResolution);
  const robotGridY = Math.floor(robot.position.y / gridResolution);
  init.push(`(at ${robotId} loc_${robotGridX}_${robotGridY})`);

  // Battery state
  if (robot.battery < 20) {
    init.push(`(low-battery ${robotId})`);
  }

  // Base location
  const baseGridX = Math.floor(world.homePosition.x / gridResolution);
  const baseGridY = Math.floor(world.homePosition.y / gridResolution);
  init.push(`(base loc_${baseGridX}_${baseGridY})`);

  // Obstacles - mark grid cells as blocked
  const blockedCells = new Set<string>();
  for (const obs of world.obstacles) {
    // Block cells within obstacle radius
    const obsGridX = Math.floor(obs.position.x / gridResolution);
    const obsGridY = Math.floor(obs.position.y / gridResolution);
    const radiusCells = Math.ceil(obs.radius / gridResolution) + 1;

    for (let dx = -radiusCells; dx <= radiusCells; dx++) {
      for (let dy = -radiusCells; dy <= radiusCells; dy++) {
        const gx = obsGridX + dx;
        const gy = obsGridY + dy;
        if (gx >= 0 && gx < gridWidth && gy >= 0 && gy < gridHeight) {
          // Check if cell center is within obstacle
          const cellCenterX = (gx + 0.5) * gridResolution;
          const cellCenterY = (gy + 0.5) * gridResolution;
          const dist = Math.sqrt(
            (cellCenterX - obs.position.x) ** 2 +
              (cellCenterY - obs.position.y) ** 2
          );
          if (dist < obs.radius + gridResolution * 0.5) {
            blockedCells.add(`loc_${gx}_${gy}`);
          }
        }
      }
    }
  }

  for (const cell of blockedCells) {
    init.push(`(obstacle ${cell})`);
  }

  // Objects (uncollected only)
  const uncollectedObjects: WorldObject[] = [];
  for (const obj of world.objects) {
    if (!obj.collected) {
      uncollectedObjects.push(obj);
      objects.push(`${obj.id} - object`);

      const objGridX = Math.floor(obj.position.x / gridResolution);
      const objGridY = Math.floor(obj.position.y / gridResolution);
      init.push(`(object-at ${obj.id} loc_${objGridX}_${objGridY})`);
    }
  }

  // Goal: collect all objects, or return home if none left
  let goal: string;
  if (uncollectedObjects.length > 0) {
    const goalConditions = uncollectedObjects
      .map((obj) => `(collected ${obj.id})`)
      .join(" ");
    goal = `(and ${goalConditions})`;
  } else {
    goal = `(at ${robotId} loc_${baseGridX}_${baseGridY})`;
  }

  return `(define (problem browser-robot-task)
  (:domain robot-exploration-strips)
  (:objects
    ${objects.join("\n    ")}
  )
  (:init
    ${init.join("\n    ")}
  )
  (:goal ${goal})
)`;
}

/**
 * Parse a location string like "loc_5_3" into grid coordinates.
 */
export function parseLocation(loc: string): { x: number; y: number } {
  const match = loc.match(/loc_(\d+)_(\d+)/);
  if (!match) {
    throw new Error(`Invalid location format: ${loc}`);
  }
  return {
    x: parseInt(match[1], 10),
    y: parseInt(match[2], 10),
  };
}

/**
 * Convert grid coordinates to world position (center of cell).
 */
export function gridToWorld(
  gridX: number,
  gridY: number,
  gridResolution: number = 1
): Position {
  return {
    x: (gridX + 0.5) * gridResolution,
    y: (gridY + 0.5) * gridResolution,
  };
}

/**
 * Calculate per-robot home position offset.
 * Robots get unique positions around the base to avoid clumping.
 */
function calculateHomeOffset(
  robotIndex: number,
  maxSlots: number = 8,
  radius: number = 2
): { dx: number; dy: number } {
  if (robotIndex === 0) {
    return { dx: 0, dy: 0 }; // First robot goes to center
  }
  const slot = (robotIndex - 1) % maxSlots;
  const angle = (slot / maxSlots) * Math.PI * 2;
  return {
    dx: Math.round(Math.cos(angle) * radius),
    dy: Math.round(Math.sin(angle) * radius),
  };
}

/**
 * Get robot index from ID for home offset calculation.
 */
function getRobotIndex(robotId: string, robots: Robot[]): number {
  const sorted = [...robots].sort((a, b) => a.id.localeCompare(b.id));
  return sorted.findIndex((r) => r.id === robotId);
}

/**
 * Generate a simplified problem for single-step planning.
 * Includes robot-blocking predicates for multi-robot coordination.
 * The planner handles collision avoidance declaratively.
 *
 * OPTIMIZATION: Uses Manhattan distance (diamond shape) and small radius (2)
 * for fast planning. With radius 2, we have ~13 cells max, which gives
 * ~169 ground move actions per state (vs 625+ with radius 3).
 *
 * The BFS planner has O(b^d) complexity where b = branching factor.
 * Keeping the problem small is critical for sub-second response.
 */
export function generateLocalPddlProblem(
  world: WorldState,
  robotId: string,
  radius: number = 2,
  gridResolution: number = 1
): string {
  const robot = world.robots.find((r) => r.id === robotId);
  if (!robot) {
    throw new Error(`Robot ${robotId} not found`);
  }

  const robotGridX = Math.floor(robot.position.x / gridResolution);
  const robotGridY = Math.floor(robot.position.y / gridResolution);

  const objects: string[] = [];
  const init: string[] = [];
  const locationSet = new Set<string>();
  const adjacenciesAdded = new Set<string>(); // Track to avoid duplicates

  // Robot object (typed)
  objects.push(`${robotId} - robot`);

  // Generate local grid locations with Manhattan distance (diamond shape)
  // Radius 1 with Manhattan distance = 5 cells (center + 4 neighbors)
  // With typed PDDL: 1 robot × 5 locations × 5 locations = 25 move groundings
  const gridRadius = Math.min(Math.ceil(radius / gridResolution), 1);
  const gridWidth = Math.ceil(world.width / gridResolution);
  const gridHeight = Math.ceil(world.height / gridResolution);

  for (let dx = -gridRadius; dx <= gridRadius; dx++) {
    for (let dy = -gridRadius; dy <= gridRadius; dy++) {
      // Manhattan distance to create diamond shape (fewer cells)
      if (Math.abs(dx) + Math.abs(dy) <= gridRadius) {
        const x = robotGridX + dx;
        const y = robotGridY + dy;
        if (x >= 0 && x < gridWidth && y >= 0 && y < gridHeight) {
          const loc = `loc_${x}_${y}`;
          if (!locationSet.has(loc)) {
            locationSet.add(loc);
            objects.push(`${loc} - location`);
          }
        }
      }
    }
  }

  // Generate adjacencies with deduplication
  for (const loc of locationSet) {
    const { x, y } = parseLocation(loc);
    const neighbors = [
      [x + 1, y],
      [x - 1, y],
      [x, y + 1],
      [x, y - 1],
    ];

    for (const [nx, ny] of neighbors) {
      const neighborLoc = `loc_${nx}_${ny}`;
      if (locationSet.has(neighborLoc)) {
        const adjKey = [loc, neighborLoc].sort().join(":");
        if (!adjacenciesAdded.has(adjKey)) {
          adjacenciesAdded.add(adjKey);
          // Add both directions for PDDL
          init.push(`(adjacent ${loc} ${neighborLoc})`);
          init.push(`(adjacent ${neighborLoc} ${loc})`);
        }
      }
    }
  }

  // Robot position - mark this robot's cell
  const robotLoc = `loc_${robotGridX}_${robotGridY}`;
  init.push(`(at ${robotId} ${robotLoc})`);

  // Battery state
  if (robot.battery < 20) {
    init.push(`(low-battery ${robotId})`);
  }

  // Base location (if in range)
  const baseGridX = Math.floor(world.homePosition.x / gridResolution);
  const baseGridY = Math.floor(world.homePosition.y / gridResolution);
  const baseLoc = `loc_${baseGridX}_${baseGridY}`;
  const baseCells = new Set<string>(); // Track base cells to avoid duplicates

  if (locationSet.has(baseLoc)) {
    baseCells.add(baseLoc);
  }

  // Per-robot home position (offset from base to avoid clumping)
  const robotIndex = getRobotIndex(robotId, world.robots);
  const homeOffset = calculateHomeOffset(robotIndex);
  const homeGridX = baseGridX + homeOffset.dx;
  const homeGridY = baseGridY + homeOffset.dy;
  const homeLoc = `loc_${homeGridX}_${homeGridY}`;

  // Only add home to location_set if it's within or adjacent to local grid
  // Otherwise it becomes an unreachable island in the PDDL problem
  let homeInRange = locationSet.has(homeLoc);
  if (!homeInRange) {
    // Check if home is adjacent to any local cell
    for (const loc of locationSet) {
      const { x: lx, y: ly } = parseLocation(loc);
      if (Math.abs(lx - homeGridX) + Math.abs(ly - homeGridY) === 1) {
        // Home is adjacent to local grid - add it with adjacency
        locationSet.add(homeLoc);
        objects.push(`${homeLoc} - location`);
        init.push(`(adjacent ${loc} ${homeLoc})`);
        init.push(`(adjacent ${homeLoc} ${loc})`);
        homeInRange = true;
        break;
      }
    }
  }

  if (homeInRange) {
    init.push(`(home-position ${robotId} ${homeLoc})`);
    // Mark home position as base too (for recharging at robot's home)
    baseCells.add(homeLoc);
  }

  // Add base predicates (deduplicated)
  for (const bc of baseCells) {
    if (locationSet.has(bc)) {
      init.push(`(base ${bc})`);
    }
  }

  // Obstacles in range
  const obstacleCells = new Set<string>();
  for (const obs of world.obstacles) {
    const obsGridX = Math.floor(obs.position.x / gridResolution);
    const obsGridY = Math.floor(obs.position.y / gridResolution);
    const radiusCells = Math.ceil(obs.radius / gridResolution) + 1;

    for (let ddx = -radiusCells; ddx <= radiusCells; ddx++) {
      for (let ddy = -radiusCells; ddy <= radiusCells; ddy++) {
        const gx = obsGridX + ddx;
        const gy = obsGridY + ddy;
        const cellLoc = `loc_${gx}_${gy}`;

        if (locationSet.has(cellLoc)) {
          const cellCenterX = (gx + 0.5) * gridResolution;
          const cellCenterY = (gy + 0.5) * gridResolution;
          const dist = Math.sqrt(
            (cellCenterX - obs.position.x) ** 2 +
              (cellCenterY - obs.position.y) ** 2
          );
          if (dist < obs.radius + gridResolution * 0.5) {
            obstacleCells.add(cellLoc);
            init.push(`(obstacle ${cellLoc})`);
          }
        }
      }
    }
  }

  // =========================================================================
  // ROBOT BLOCKING - The key to declarative collision avoidance!
  // Instead of procedural collision checks, we add facts about blocked cells.
  // The planner's preconditions handle collision avoidance automatically.
  // =========================================================================
  const robotBlockingCells = new Set<string>();
  for (const otherRobot of world.robots) {
    if (otherRobot.id === robotId) continue; // Skip self
    if (!otherRobot.isActive) continue; // Skip inactive robots

    const otherGridX = Math.floor(otherRobot.position.x / gridResolution);
    const otherGridY = Math.floor(otherRobot.position.y / gridResolution);
    const otherLoc = `loc_${otherGridX}_${otherGridY}`;

    if (locationSet.has(otherLoc)) {
      robotBlockingCells.add(otherLoc);
      init.push(`(robot-blocking ${otherLoc})`);
    }
  }

  // All blocked cells (obstacles + other robots)
  const allBlocked = new Set([...obstacleCells, ...robotBlockingCells]);

  // Objects in range
  const uncollectedObjects: WorldObject[] = [];
  for (const obj of world.objects) {
    if (!obj.collected) {
      const objGridX = Math.floor(obj.position.x / gridResolution);
      const objGridY = Math.floor(obj.position.y / gridResolution);
      const objLoc = `loc_${objGridX}_${objGridY}`;

      if (locationSet.has(objLoc)) {
        uncollectedObjects.push(obj);
        objects.push(`${obj.id} - object`);
        init.push(`(object-at ${obj.id} ${objLoc})`);
      }
    }
  }

  // Goal depends on robot state
  // IMPORTANT: Goal must be achievable within local radius for fast planning
  // Use allBlocked (obstacles + other robots) when selecting goal locations
  let goal: string = `(at ${robotId} ${robotLoc})`; // Default: stay in place

  // Helper to find best unblocked location toward a target
  const findBestLocationToward = (
    targetX: number,
    targetY: number
  ): string => {
    let bestLoc = robotLoc;
    let bestDist = Infinity;
    for (const loc of locationSet) {
      if (allBlocked.has(loc)) continue;
      if (loc === robotLoc) continue; // Never select current location
      const { x, y } = parseLocation(loc);
      const dist = Math.abs(x - targetX) + Math.abs(y - targetY);
      if (dist < bestDist) {
        bestDist = dist;
        bestLoc = loc;
      }
    }
    return bestLoc;
  };

  if (robot.battery < 20) {
    // Low battery - move toward home (one step at a time)
    if (homeInRange && !allBlocked.has(homeLoc)) {
      goal = `(at ${robotId} ${homeLoc})`;
    } else {
      // Home is blocked or outside radius - find closest unblocked cell toward home
      goal = `(at ${robotId} ${findBestLocationToward(homeGridX, homeGridY)})`;
    }
  } else if (uncollectedObjects.length > 0) {
    // Find nearest object that's not blocked
    const sortedObjects = [...uncollectedObjects].sort((a, b) => {
      const distA = Math.sqrt(
        (a.position.x - robot.position.x) ** 2 +
          (a.position.y - robot.position.y) ** 2
      );
      const distB = Math.sqrt(
        (b.position.x - robot.position.x) ** 2 +
          (b.position.y - robot.position.y) ** 2
      );
      return distA - distB;
    });

    // Find first object whose cell is not blocked
    let foundUnblockedObject = false;
    for (const obj of sortedObjects) {
      const objGridX = Math.floor(obj.position.x / gridResolution);
      const objGridY = Math.floor(obj.position.y / gridResolution);
      const objLoc = `loc_${objGridX}_${objGridY}`;
      if (!allBlocked.has(objLoc)) {
        goal = `(collected ${obj.id})`;
        foundUnblockedObject = true;
        break;
      }
    }

    if (!foundUnblockedObject) {
      // All objects are blocked - move toward nearest
      const nearest = sortedObjects[0];
      const objX = Math.floor(nearest.position.x / gridResolution);
      const objY = Math.floor(nearest.position.y / gridResolution);
      goal = `(at ${robotId} ${findBestLocationToward(objX, objY)})`;
    }
  } else {
    // No objects nearby - move toward edge (exploration, farthest unblocked cell)
    let bestLoc = robotLoc;
    let bestDist = 0;
    for (const loc of locationSet) {
      if (allBlocked.has(loc)) continue;
      if (loc === robotLoc) continue; // Never select current location for exploration
      const { x, y } = parseLocation(loc);
      const dist = Math.abs(x - robotGridX) + Math.abs(y - robotGridY);
      if (dist > bestDist) {
        bestDist = dist;
        bestLoc = loc;
      }
    }
    // If bestLoc is still robotLoc, all neighbors are blocked - stay in place
    if (bestLoc === robotLoc) {
      console.warn(`[Planning Debug] ${robotId}: all neighbors blocked, staying in place`);
    }
    goal = `(at ${robotId} ${bestLoc})`;
  }

  // SAFETY CHECK: If goal is current location, force movement to ANY unblocked neighbor
  // This prevents empty plans which cause robots to stop moving
  const goalMatch = goal.match(/\(at \S+ (\S+)\)/);
  if (goalMatch && goalMatch[1] === robotLoc) {
    console.warn(`[Planning Debug] ${robotId}: goal was current location, forcing neighbor`);
    // Find ANY unblocked neighbor
    for (const loc of locationSet) {
      if (loc !== robotLoc && !allBlocked.has(loc)) {
        goal = `(at ${robotId} ${loc})`;
        console.log(`[Planning Debug] ${robotId}: forced goal to ${loc}`);
        break;
      }
    }
  }

  // Minimal debug logging
  console.log(
    `[Planning] ${robotId}: goal=${goal}, locations=${locationSet.size}, blocked=${allBlocked.size}`
  );

  return `(define (problem browser-robot-coordination)
  (:domain robot-exploration-coordination)
  (:objects
    ${objects.join("\n    ")}
  )
  (:init
    ${init.join("\n    ")}
  )
  (:goal ${goal})
)`;
}
