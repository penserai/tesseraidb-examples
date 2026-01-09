#!/usr/bin/env python3
"""
Reactive Controller for Robot Simulation
=========================================

This controller uses PDDL-style predicates to describe the world state,
but evaluates action preconditions DIRECTLY instead of calling a planner.

Key insight: For real-time robotics, we need "what's the best action NOW?"
not "what sequence of actions reaches the goal?" - a fundamentally different question.

Architecture:
- World state represented as PDDL-style predicates
- Action preconditions checked directly (O(1) per action)
- Simple heuristics select the best valid action
- No planning search needed for per-tick decisions

This approach is:
- Fast: O(1) per tick instead of O(exponential) planning
- Predictable: Same state always produces same action
- Debuggable: Clear precondition checks
"""

import math
from dataclasses import dataclass
from typing import Optional, Set, Dict, List, Tuple, Any

# Grid resolution in meters
GRID_RESOLUTION = 1.0


@dataclass
class ReactiveAction:
    """An action returned by the reactive controller."""
    action: str  # "Move", "Collect", "Recharge", "Wait"
    target: Optional[Tuple[float, float]] = None
    object_id: Optional[str] = None


@dataclass
class WorldPredicates:
    """PDDL-style predicates extracted from world state."""
    # Robot state
    robot_at: Dict[str, str]  # robotId -> locationId
    low_battery: Set[str]  # robotIds with low battery
    carrying: Dict[str, str]  # robotId -> objectId

    # Location state
    obstacles: Set[str]  # locationIds that are obstacles
    robot_blocking: Set[str]  # locationIds blocked by robots
    bases: Set[str]  # locationIds that are bases
    home_positions: Dict[str, str]  # robotId -> home locationId

    # Object state
    object_at: Dict[str, str]  # objectId -> locationId
    collected: Set[str]  # objectIds that are collected

    # Adjacency graph
    adjacent: Dict[str, Set[str]]  # locationId -> adjacent locationIds


def pos_to_loc(x: float, y: float) -> str:
    """Convert world position to location identifier."""
    gx = int(x / GRID_RESOLUTION)
    gy = int(y / GRID_RESOLUTION)
    return f"loc_{gx}_{gy}"


def loc_to_pos(loc: str) -> Tuple[float, float]:
    """Convert location identifier to world position (cell center)."""
    parts = loc.split("_")
    gx = int(parts[1])
    gy = int(parts[2])
    return ((gx + 0.5) * GRID_RESOLUTION, (gy + 0.5) * GRID_RESOLUTION)


def parse_loc(loc: str) -> Tuple[int, int]:
    """Parse location string to grid coordinates."""
    parts = loc.split("_")
    return (int(parts[1]), int(parts[2]))


def get_adjacent_locs(loc: str) -> List[str]:
    """Get orthogonally adjacent locations."""
    gx, gy = parse_loc(loc)
    return [
        f"loc_{gx - 1}_{gy}",
        f"loc_{gx + 1}_{gy}",
        f"loc_{gx}_{gy - 1}",
        f"loc_{gx}_{gy + 1}",
    ]


def calculate_home_offset(robot_index: int) -> Tuple[int, int]:
    """Calculate home position offset for a robot."""
    offsets = [
        (0, 0),
        (1, 0),
        (0, 1),
        (-1, 0),
        (0, -1),
    ]
    return offsets[robot_index % len(offsets)]


def extract_predicates(world: Any) -> WorldPredicates:
    """
    Extract PDDL-style predicates from world state.
    This is a pure function - same world always produces same predicates.
    """
    predicates = WorldPredicates(
        robot_at={},
        low_battery=set(),
        carrying={},
        obstacles=set(),
        robot_blocking=set(),
        bases=set(),
        home_positions={},
        object_at={},
        collected=set(),
        adjacent={},
    )

    # Extract robot predicates
    for robot in world.robots:
        loc = pos_to_loc(robot.position.x, robot.position.y)
        predicates.robot_at[robot.id] = loc

        if robot.battery < 20:
            predicates.low_battery.add(robot.id)

        # All active robots block their cell
        if robot.is_active:
            predicates.robot_blocking.add(loc)

    # Extract obstacle predicates
    for obs in world.obstacles:
        cx = int(obs.position.x / GRID_RESOLUTION)
        cy = int(obs.position.y / GRID_RESOLUTION)
        radius_cells = int(math.ceil(obs.radius / GRID_RESOLUTION)) + 1

        for dx in range(-radius_cells, radius_cells + 1):
            for dy in range(-radius_cells, radius_cells + 1):
                gx = cx + dx
                gy = cy + dy
                cell_center_x = (gx + 0.5) * GRID_RESOLUTION
                cell_center_y = (gy + 0.5) * GRID_RESOLUTION
                dist = math.sqrt(
                    (cell_center_x - obs.position.x) ** 2 +
                    (cell_center_y - obs.position.y) ** 2
                )
                if dist < obs.radius + GRID_RESOLUTION * 0.5:
                    predicates.obstacles.add(f"loc_{gx}_{gy}")

    # Extract object predicates
    for obj in world.objects:
        if obj.collected:
            predicates.collected.add(obj.id)
        else:
            predicates.object_at[obj.id] = pos_to_loc(obj.position.x, obj.position.y)

    # Base/home positions
    base_loc = pos_to_loc(world.home_position.x, world.home_position.y)
    predicates.bases.add(base_loc)

    # Calculate per-robot home positions
    for i, robot in enumerate(world.robots):
        dx, dy = calculate_home_offset(i)
        base_x = int(world.home_position.x / GRID_RESOLUTION)
        base_y = int(world.home_position.y / GRID_RESOLUTION)
        home_loc = f"loc_{base_x + dx}_{base_y + dy}"
        predicates.home_positions[robot.id] = home_loc
        predicates.bases.add(home_loc)

    # Build adjacency graph for relevant area
    relevant_locs = set()
    for robot in world.robots:
        loc = predicates.robot_at.get(robot.id)
        if loc:
            relevant_locs.add(loc)
            for adj in get_adjacent_locs(loc):
                relevant_locs.add(adj)

    for loc in relevant_locs:
        predicates.adjacent[loc] = set(get_adjacent_locs(loc))

    return predicates


# =============================================================================
# Action Precondition Checks
# =============================================================================

def can_move(robot_id: str, to_loc: str, predicates: WorldPredicates,
             allow_low_battery: bool = False) -> bool:
    """
    Check if a robot can move to an adjacent cell.
    Preconditions:
      - Robot is at 'from' location
      - 'from' and 'to' are adjacent
      - 'to' is not an obstacle
      - 'to' is not blocked by another robot
      - Robot does not have low battery (unless moving toward home)
    """
    from_loc = predicates.robot_at.get(robot_id)
    if not from_loc:
        return False

    # Check adjacency
    adjacent = predicates.adjacent.get(from_loc)
    if not adjacent or to_loc not in adjacent:
        return False

    # Check not obstacle
    if to_loc in predicates.obstacles:
        return False

    # Check not blocked by other robot
    if to_loc in predicates.robot_blocking and to_loc != from_loc:
        # Check if it's actually another robot
        for rid, rloc in predicates.robot_at.items():
            if rid != robot_id and rloc == to_loc:
                return False

    # Check battery
    if not allow_low_battery and robot_id in predicates.low_battery:
        return False

    return True


def can_collect(robot_id: str, object_id: str, predicates: WorldPredicates) -> bool:
    """
    Check if a robot can collect an object.
    Preconditions:
      - Robot is at the object's location
      - Object is not already collected
      - Robot does not have low battery
    """
    robot_loc = predicates.robot_at.get(robot_id)
    object_loc = predicates.object_at.get(object_id)

    if not robot_loc or not object_loc:
        return False
    if robot_loc != object_loc:
        return False
    if object_id in predicates.collected:
        return False
    if robot_id in predicates.low_battery:
        return False

    return True


def can_recharge(robot_id: str, predicates: WorldPredicates) -> bool:
    """
    Check if a robot can recharge.
    Preconditions:
      - Robot is at a base location
      - Robot has low battery
    """
    robot_loc = predicates.robot_at.get(robot_id)
    if not robot_loc:
        return False

    if robot_loc not in predicates.bases:
        return False
    if robot_id not in predicates.low_battery:
        return False

    return True


# =============================================================================
# Heuristic Action Selection
# =============================================================================

# Track location history to detect cycles (last N positions per robot)
_location_history: Dict[str, List[str]] = {}
HISTORY_SIZE = 6  # Track last 6 positions to detect cycles


def _is_cycling(robot_id: str, current_loc: str) -> bool:
    """Check if robot is stuck in a cycle."""
    history = _location_history.get(robot_id, [])
    if len(history) < 4:
        return False
    # Check if current location appears in recent history (cycle detected)
    return current_loc in history[-4:]


def _update_history(robot_id: str, loc: str) -> None:
    """Update location history for a robot."""
    if robot_id not in _location_history:
        _location_history[robot_id] = []
    history = _location_history[robot_id]
    history.append(loc)
    if len(history) > HISTORY_SIZE:
        history.pop(0)


def find_best_move_toward(robot_id: str, target_loc: str,
                          predicates: WorldPredicates,
                          allow_low_battery: bool) -> Optional[str]:
    """Find the best adjacent cell to move toward a target.

    Returns None if cycling detected (triggers procedural fallback).
    """
    robot_loc = predicates.robot_at.get(robot_id)
    if not robot_loc:
        return None

    # Detect cycles - if cycling, return None to use procedural exploration
    if _is_cycling(robot_id, robot_loc):
        _location_history[robot_id] = []  # Clear history
        return None

    target_x, target_y = parse_loc(target_loc)
    adjacent = predicates.adjacent.get(robot_loc)
    if not adjacent:
        return None

    history = _location_history.get(robot_id, [])

    best_loc = None
    best_dist = float('inf')
    backup_loc = None

    for adj_loc in adjacent:
        if not can_move(robot_id, adj_loc, predicates, allow_low_battery):
            continue

        x, y = parse_loc(adj_loc)
        dist = abs(x - target_x) + abs(y - target_y)

        # Avoid recently visited locations unless it's the only option
        if adj_loc in history:
            if backup_loc is None:
                backup_loc = adj_loc
            continue

        if dist < best_dist:
            best_dist = dist
            best_loc = adj_loc

    # If no new location available, use backup
    if best_loc is None:
        best_loc = backup_loc

    # Update history
    if best_loc:
        _update_history(robot_id, robot_loc)

    return best_loc


def find_nearest_object(robot_pos: Tuple[float, float], world: Any,
                        predicates: WorldPredicates) -> Optional[Any]:
    """Find the nearest uncollected object."""
    nearest = None
    nearest_dist = float('inf')

    for obj in world.objects:
        if obj.id in predicates.collected:
            continue

        dist = math.sqrt(
            (obj.position.x - robot_pos[0]) ** 2 +
            (obj.position.y - robot_pos[1]) ** 2
        )

        if dist < nearest_dist:
            nearest_dist = dist
            nearest = obj

    return nearest


def get_reactive_action(world: Any, robot: Any) -> ReactiveAction:
    """
    Get the best action for a robot using reactive rule evaluation.

    SIMPLIFIED: Only handles immediate actions (collect, recharge).
    All movement decisions use procedural (which has proper path-finding).

    Priority:
    1. If at base with low battery → Recharge
    2. If at object location → Collect
    3. Everything else → None (use procedural)
    """
    predicates = extract_predicates(world)
    robot_id = robot.id

    if robot_id not in predicates.robot_at:
        return None

    robot_loc = predicates.robot_at[robot_id]

    # 1. Recharge if at base with low battery
    if can_recharge(robot_id, predicates):
        return ReactiveAction(action="Recharge")

    # 2. Collect object at current location
    for obj_id, obj_loc in predicates.object_at.items():
        if obj_loc == robot_loc and can_collect(robot_id, obj_id, predicates):
            return ReactiveAction(action="Collect", object_id=obj_id)

    # 3. All movement handled by procedural (has better path-finding)
    return None


# =============================================================================
# Debugging / Diagnostics
# =============================================================================

def predicates_to_string(predicates: WorldPredicates) -> str:
    """Get a human-readable summary of the predicates for debugging."""
    lines = ["=== World Predicates ==="]

    lines.append("\nRobot positions:")
    for rid, loc in predicates.robot_at.items():
        low_batt = " (LOW BATTERY)" if rid in predicates.low_battery else ""
        lines.append(f"  {rid} at {loc}{low_batt}")

    lines.append("\nBlocked cells:")
    obs_list = list(predicates.obstacles)[:10]
    lines.append(f"  Obstacles: {', '.join(obs_list)}{'...' if len(predicates.obstacles) > 10 else ''}")
    lines.append(f"  Robot blocking: {', '.join(predicates.robot_blocking)}")

    lines.append("\nObjects:")
    for oid, loc in predicates.object_at.items():
        lines.append(f"  {oid} at {loc}")
    if predicates.collected:
        lines.append(f"  Collected: {', '.join(predicates.collected)}")

    return "\n".join(lines)
