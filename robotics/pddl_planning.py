#!/usr/bin/env python3
"""
PDDL Planning Integration for Robot Simulation
==============================================

This module provides declarative PDDL planning for robot control.
Instead of procedural decision logic (if/else chains), robots use
the PDDL planner to determine optimal actions.

Key Benefits:
- Collision avoidance is declarative (robot-blocking predicates)
- Multi-robot coordination handled by planner
- Same domain works across Python, TypeScript, Rust clients
- Behavior changes require only PDDL domain updates

Architecture:
    World State → Problem Generator → PDDL Problem
                                          ↓
                                    Planning API
                                          ↓
                                    Plan (actions)
                                          ↓
                              Execute first action
"""

import math
import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from dtaas import DTaaSClient
from dtaas.exceptions import DTaaSError, NotFoundError


# PDDL Domain with Multi-Robot Coordination
# TYPED version - SimplePlanner uses types to efficiently filter ground actions
PDDL_DOMAIN_ID = "robot-exploration-coordination"

PDDL_DOMAIN = """
(define (domain robot-exploration-coordination)
  (:requirements :strips :typing :negative-preconditions)

  (:types
    robot
    location
    object
  )

  (:predicates
    ;; Position predicates
    (at ?r - robot ?l - location)
    (adjacent ?l1 - location ?l2 - location)

    ;; Blocking predicates - obstacles and other robots
    (obstacle ?l - location)
    (robot-blocking ?l - location)

    ;; Home/base predicates - per-robot
    (base ?l - location)
    (home-position ?r - robot ?l - location)

    ;; Object predicates
    (object-at ?o - object ?l - location)
    (collected ?o - object)
    (carrying ?r - robot ?o - object)

    ;; Robot state predicates
    (low-battery ?r - robot)
    (at-base ?r - robot)
    (explored ?r - robot ?l - location)
  )

  ;; Move action - respects both obstacles AND other robots
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

  ;; Collect action
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

  ;; Return to robot's assigned home position
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

  ;; Move toward home when not adjacent
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

  ;; Recharge at any base location
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

  ;; Wait action - when path is blocked by another robot
  (:action wait
    :parameters (?r - robot ?l - location)
    :precondition (at ?r ?l)
    :effect ()
  )
)
"""


@dataclass
class Position:
    """Simple position class."""
    x: float
    y: float


@dataclass
class PlanningAction:
    """Action returned by the planner."""
    action: str
    target: Optional[Position]
    object_id: Optional[str] = None


@dataclass
class PlanningStats:
    """Statistics from the planning process."""
    planning_time_ms: int
    states_explored: int
    actions_planned: int
    plan_valid: bool


def calculate_home_offset(robot_index: int, max_slots: int = 8, radius: float = 2.0) -> tuple:
    """Calculate per-robot home position offset.

    Robots get unique positions around the base to avoid clumping.
    """
    if robot_index == 0:
        return (0, 0)
    slot = (robot_index - 1) % max_slots
    angle = (slot / max_slots) * math.pi * 2
    return (
        round(math.cos(angle) * radius),
        round(math.sin(angle) * radius),
    )


def generate_pddl_problem(
    world,  # SimulationWorld
    robot,  # Robot
    radius: int = 2,
    grid_resolution: int = 1,
) -> str:
    """Generate a PDDL problem from the current world state.

    This function converts the simulation world state into a PDDL problem
    that includes:
    - Robot position
    - Nearby obstacles
    - Nearby objects
    - Other robots as blocking cells (for collision avoidance)
    - Per-robot home positions

    OPTIMIZATION: Uses small radius (2) and Manhattan distance to ensure
    fast planning. With radius 2, we have ~13 cells max, which gives
    ~169 ground move actions per state (vs 625+ with radius 3).

    The BFS planner has O(b^d) complexity where b = branching factor.
    Keeping the problem small is critical for sub-second response.

    Args:
        world: The simulation world
        robot: The robot to plan for
        radius: Local planning radius (cells) - keep small for speed
        grid_resolution: Grid cell size

    Returns:
        PDDL problem string
    """
    robot_grid_x = int(robot.position.x / grid_resolution)
    robot_grid_y = int(robot.position.y / grid_resolution)

    objects = []
    init = []
    location_set = set()
    adjacencies_added = set()  # Track added adjacencies to avoid duplicates

    # Robot object (typed)
    objects.append(f"{robot.id} - robot")

    # Generate local grid locations - use minimal radius for speed
    # Radius 1 with Manhattan distance = 5 cells (center + 4 neighbors)
    # With typed PDDL: 1 robot × 5 locations × 5 locations = 25 move groundings
    grid_radius = min(radius, 1)  # Cap at 1 for performance
    grid_width = int(math.ceil(world.width / grid_resolution))
    grid_height = int(math.ceil(world.height / grid_resolution))

    for dx in range(-grid_radius, grid_radius + 1):
        for dy in range(-grid_radius, grid_radius + 1):
            # Use Manhattan distance to reduce cells (diamond shape)
            if abs(dx) + abs(dy) <= grid_radius:
                x = robot_grid_x + dx
                y = robot_grid_y + dy
                if 0 <= x < grid_width and 0 <= y < grid_height:
                    loc = f"loc_{x}_{y}"
                    if loc not in location_set:
                        location_set.add(loc)
                        objects.append(f"{loc} - location")

    # Generate adjacencies - only one direction to reduce predicates
    for loc in location_set:
        parts = loc.split("_")
        x, y = int(parts[1]), int(parts[2])
        # Only check right and down to avoid duplicate adjacencies
        neighbors = [(x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)]
        for nx, ny in neighbors:
            neighbor_loc = f"loc_{nx}_{ny}"
            if neighbor_loc in location_set:
                adj_key = tuple(sorted([loc, neighbor_loc]))
                if adj_key not in adjacencies_added:
                    adjacencies_added.add(adj_key)
                    # Add both directions for PDDL
                    init.append(f"(adjacent {loc} {neighbor_loc})")
                    init.append(f"(adjacent {neighbor_loc} {loc})")

    # Robot position - ensure it's in location set
    robot_loc = f"loc_{robot_grid_x}_{robot_grid_y}"
    if robot_loc not in location_set:
        # This shouldn't happen, but add it just in case
        location_set.add(robot_loc)
        objects.append(f"{robot_loc} - location")
        print(f"[Planning Warning] {robot.id}: current location {robot_loc} was not in location set!")
    init.append(f"(at {robot.id} {robot_loc})")

    # Battery state
    if robot.battery < 20:
        init.append(f"(low-battery {robot.id})")

    # Base location
    base_grid_x = int(world.home_position.x / grid_resolution)
    base_grid_y = int(world.home_position.y / grid_resolution)
    base_loc = f"loc_{base_grid_x}_{base_grid_y}"
    base_cells = set()  # Track base cells to avoid duplicates

    if base_loc in location_set:
        base_cells.add(base_loc)

    # Per-robot home position (offset from base)
    home_offset = calculate_home_offset(robot.robot_index)
    home_grid_x = base_grid_x + home_offset[0]
    home_grid_y = base_grid_y + home_offset[1]
    home_loc = f"loc_{home_grid_x}_{home_grid_y}"

    # Only add home to location_set if it's within or adjacent to local grid
    # Otherwise it becomes an unreachable island
    home_in_range = home_loc in location_set
    if not home_in_range:
        # Check if home is adjacent to any local cell
        for loc in list(location_set):
            parts = loc.split("_")
            lx, ly = int(parts[1]), int(parts[2])
            if abs(lx - home_grid_x) + abs(ly - home_grid_y) == 1:
                # Home is adjacent to local grid - add it with adjacency
                location_set.add(home_loc)
                objects.append(f"{home_loc} - location")
                init.append(f"(adjacent {loc} {home_loc})")
                init.append(f"(adjacent {home_loc} {loc})")
                home_in_range = True
                break

    if home_in_range:
        init.append(f"(home-position {robot.id} {home_loc})")
        # Mark home position as base too (for recharging at robot's home)
        base_cells.add(home_loc)

    # Add base predicates (deduplicated)
    for bc in base_cells:
        if bc in location_set:
            init.append(f"(base {bc})")

    # Obstacles
    obstacle_cells = set()
    for obs in world.obstacles:
        obs_grid_x = int(obs.position.x / grid_resolution)
        obs_grid_y = int(obs.position.y / grid_resolution)
        radius_cells = int(math.ceil(obs.radius / grid_resolution)) + 1

        for ddx in range(-radius_cells, radius_cells + 1):
            for ddy in range(-radius_cells, radius_cells + 1):
                gx = obs_grid_x + ddx
                gy = obs_grid_y + ddy
                cell_loc = f"loc_{gx}_{gy}"

                if cell_loc in location_set:
                    cell_center_x = (gx + 0.5) * grid_resolution
                    cell_center_y = (gy + 0.5) * grid_resolution
                    dist = math.sqrt(
                        (cell_center_x - obs.position.x) ** 2 +
                        (cell_center_y - obs.position.y) ** 2
                    )
                    if dist < obs.radius + grid_resolution * 0.5:
                        obstacle_cells.add(cell_loc)
                        init.append(f"(obstacle {cell_loc})")

    # ROBOT BLOCKING - Key to declarative collision avoidance
    # Track blocked cells for goal selection
    robot_blocking_cells = set()
    for other_robot in world.robots:
        if other_robot.id == robot.id:
            continue
        if not other_robot.is_active:
            continue

        other_grid_x = int(other_robot.position.x / grid_resolution)
        other_grid_y = int(other_robot.position.y / grid_resolution)
        other_loc = f"loc_{other_grid_x}_{other_grid_y}"

        if other_loc in location_set:
            robot_blocking_cells.add(other_loc)
            init.append(f"(robot-blocking {other_loc})")

    # All blocked cells (obstacles + other robots)
    all_blocked = obstacle_cells | robot_blocking_cells

    # Objects
    uncollected_objects = []
    known = world.known_worlds.get(robot.id)

    for obj in world.objects:
        if not obj.collected:
            obj_grid_x = int(obj.position.x / grid_resolution)
            obj_grid_y = int(obj.position.y / grid_resolution)
            obj_loc = f"loc_{obj_grid_x}_{obj_grid_y}"

            if obj_loc in location_set:
                # Only include objects the robot knows about
                if known and obj.id in known.discovered_objects:
                    uncollected_objects.append(obj)
                    objects.append(f"{obj.id} - object")
                    init.append(f"(object-at {obj.id} {obj_loc})")

    # Goal depends on robot state
    # IMPORTANT: Goal must be achievable within local radius for fast planning
    # Use all_blocked (obstacles + other robots) when selecting goal locations

    # Helper to find best unblocked location toward a target
    def find_best_toward(target_x: int, target_y: int) -> str:
        best_loc = robot_loc
        best_dist = float('inf')
        for loc in location_set:
            if loc in all_blocked:
                continue
            if loc == robot_loc:
                continue  # Never select current location
            parts = loc.split("_")
            lx, ly = int(parts[1]), int(parts[2])
            dist = abs(lx - target_x) + abs(ly - target_y)
            if dist < best_dist:
                best_dist = dist
                best_loc = loc
        return best_loc

    if robot.battery < 20:
        # Low battery - move toward home (one step at a time)
        if home_in_range and home_loc not in all_blocked:
            goal = f"(at {robot.id} {home_loc})"
        else:
            # Home is not reachable or blocked - find closest unblocked cell toward home
            best_loc = find_best_toward(home_grid_x, home_grid_y)
            goal = f"(at {robot.id} {best_loc})"
    elif uncollected_objects:
        # Find nearest known object that's in our local area
        in_range_objects = [
            o for o in uncollected_objects
            if f"loc_{int(o.position.x / grid_resolution)}_{int(o.position.y / grid_resolution)}" in location_set
        ]
        if in_range_objects:
            # Check if robot can reach the object (object cell not blocked, or robot is at object cell)
            found_reachable = False
            for obj in sorted(in_range_objects, key=lambda o: math.sqrt(
                (o.position.x - robot.position.x) ** 2 +
                (o.position.y - robot.position.y) ** 2
            )):
                obj_grid_x = int(obj.position.x / grid_resolution)
                obj_grid_y = int(obj.position.y / grid_resolution)
                obj_loc = f"loc_{obj_grid_x}_{obj_grid_y}"

                # Can collect if: object is at robot's current cell, OR object cell is not blocked
                if obj_loc == robot_loc or obj_loc not in all_blocked:
                    goal = f"(collected {obj.id})"
                    found_reachable = True
                    break

            if not found_reachable:
                # All objects are blocked - move toward nearest (or stay if stuck)
                nearest = in_range_objects[0]
                obj_x = int(nearest.position.x / grid_resolution)
                obj_y = int(nearest.position.y / grid_resolution)
                best_loc = find_best_toward(obj_x, obj_y)
                goal = f"(at {robot.id} {best_loc})"
        else:
            # Object is outside radius - just move toward it
            nearest = min(
                uncollected_objects,
                key=lambda o: math.sqrt(
                    (o.position.x - robot.position.x) ** 2 +
                    (o.position.y - robot.position.y) ** 2
                )
            )
            obj_x = int(nearest.position.x / grid_resolution)
            obj_y = int(nearest.position.y / grid_resolution)
            best_loc = find_best_toward(obj_x, obj_y)
            goal = f"(at {robot.id} {best_loc})"
    else:
        # Explore - move to edge of local area (farthest unblocked cell)
        best_loc = robot_loc
        best_dist = 0
        for loc in location_set:
            if loc in all_blocked:
                continue
            if loc == robot_loc:
                continue  # Never select current location for exploration
            parts = loc.split("_")
            lx, ly = int(parts[1]), int(parts[2])
            dist = abs(lx - robot_grid_x) + abs(ly - robot_grid_y)
            if dist > best_dist:
                best_dist = dist
                best_loc = loc
        # If best_loc is still robot_loc, all neighbors are blocked
        if best_loc == robot_loc:
            print(f"[Planning Debug] {robot.id}: all neighbors blocked, staying in place")
        goal = f"(at {robot.id} {best_loc})"

    # SAFETY CHECK: If goal is current location, force movement to ANY unblocked neighbor
    # This prevents empty plans which cause robots to stop moving
    goal_match = re.match(r'\(at \S+ (\S+)\)', goal)
    if goal_match and goal_match.group(1) == robot_loc:
        print(f"[Planning Debug] {robot.id}: goal was current location, forcing neighbor")
        for loc in location_set:
            if loc != robot_loc and loc not in all_blocked:
                goal = f"(at {robot.id} {loc})"
                print(f"[Planning Debug] {robot.id}: forced goal to {loc}")
                break

    # Debug: Log goal selection details
    robot_current = robot_loc
    num_locations = len(location_set)
    num_blocked = len(all_blocked)
    print(f"[Planning Debug] {robot.id}: locations={num_locations}, blocked={num_blocked}, "
          f"current={robot_current}, goal={goal}")

    objects_str = "\n    ".join(objects)
    init_str = "\n    ".join(init)

    return f"""(define (problem robot-coordination)
  (:domain robot-exploration-coordination)
  (:objects
    {objects_str}
  )
  (:init
    {init_str}
  )
  (:goal {goal})
)"""


def parse_location(loc: str) -> tuple:
    """Parse a location string like 'loc_5_3' into (x, y)."""
    parts = loc.split("_")
    return (int(parts[1]), int(parts[2]))


def grid_to_world(grid_x: int, grid_y: int, grid_resolution: int = 1) -> Position:
    """Convert grid coordinates to world coordinates."""
    return Position(
        x=(grid_x + 0.5) * grid_resolution,
        y=(grid_y + 0.5) * grid_resolution,
    )


class PlanningController:
    """Controller for PDDL-based robot planning.

    This class handles:
    - Domain registration with the planning server
    - Problem generation for each robot
    - Plan caching for efficiency
    - Action conversion to simulation format
    """

    def __init__(self, client: DTaaSClient):
        """Initialize the planning controller.

        Args:
            client: DTaaS client for API calls
        """
        self.client = client
        self.domain_registered = False
        self.last_stats: Optional[PlanningStats] = None
        self.plan_cache: Dict[str, tuple] = {}  # {key: (plan, timestamp)}
        self.cache_ttl_ms = 500

    def initialize(self) -> bool:
        """Initialize the planning controller.

        Registers the PDDL domain with the server.

        Returns:
            True if initialization succeeded
        """
        try:
            # Delete existing domain if present
            try:
                self.client.planning.delete_domain(PDDL_DOMAIN_ID)
            except NotFoundError:
                pass

            # Create domain
            self.client.planning.create_domain({
                "id": PDDL_DOMAIN_ID,
                "name": "Robot Exploration with Multi-Robot Coordination",
                "pddl": PDDL_DOMAIN,
            })

            self.domain_registered = True
            print(f"[Planning] Domain '{PDDL_DOMAIN_ID}' registered successfully")
            return True

        except Exception as e:
            print(f"[Planning] Initialization failed: {e}")
            return False

    def is_ready(self) -> bool:
        """Check if the controller is ready."""
        return self.domain_registered

    def get_next_action(
        self,
        world,  # SimulationWorld
        robot,  # Robot
    ) -> Optional[PlanningAction]:
        """Get the next action for a robot using PDDL planning.

        Args:
            world: The simulation world
            robot: The robot to plan for

        Returns:
            PlanningAction or None if planning failed
        """
        if not self.domain_registered:
            return None

        try:
            # Generate problem with minimal radius for fast planning
            # Radius of 1 gives us 5 cells (center + 4 orthogonal neighbors)
            # This results in ~25 ground move actions which BFS can handle quickly
            problem_pddl = generate_pddl_problem(world, robot, radius=1)

            # Get plan from server
            try:
                plan = self.client.planning.plan(
                    domain_id=PDDL_DOMAIN_ID,
                    problem_pddl=problem_pddl,
                    timeout_ms=2000,
                )
            except Exception as plan_error:
                # Dump the PDDL for debugging
                print(f"\n{'='*60}")
                print(f"PLANNING FAILED for {robot.id}: {plan_error}")
                print(f"Problem PDDL:\n{problem_pddl}")
                print(f"{'='*60}\n")
                raise

            # Update stats
            self.last_stats = PlanningStats(
                planning_time_ms=plan.stats.planning_time_ms,
                states_explored=plan.stats.states_explored,
                actions_planned=len(plan.actions),
                plan_valid=plan.valid,
            )

            # Convert first action
            if plan.valid and plan.actions:
                return self._convert_action(plan.actions[0], world, robot)

            return None

        except Exception as e:
            print(f"[Planning] Error getting action for {robot.id}: {e}")
            return None

    def _convert_action(
        self,
        pddl_action,
        world,
        robot,
    ) -> PlanningAction:
        """Convert a PDDL action to a simulation action."""
        name = pddl_action.name
        params = pddl_action.parameters

        if name == "move":
            # (move robot from to)
            to_loc = params[2]
            x, y = parse_location(to_loc)
            target = grid_to_world(x, y)
            return PlanningAction(action="Move", target=target)

        elif name == "collect":
            # (collect robot location object)
            obj_id = params[2]
            obj = next((o for o in world.objects if o.id == obj_id), None)
            target = Position(obj.position.x, obj.position.y) if obj else None
            return PlanningAction(action="Collect", target=target, object_id=obj_id)

        elif name == "return-to-home":
            # (return-to-home robot from to)
            to_loc = params[2]
            x, y = parse_location(to_loc)
            target = grid_to_world(x, y)
            return PlanningAction(action="ReturnHome", target=target)

        elif name == "move-toward-home":
            # (move-toward-home robot from to)
            to_loc = params[2]
            x, y = parse_location(to_loc)
            target = grid_to_world(x, y)
            return PlanningAction(action="ReturnHome", target=target)

        elif name == "recharge":
            # (recharge robot location)
            return PlanningAction(
                action="Recharge",
                target=Position(world.home_position.x, world.home_position.y)
            )

        elif name == "wait":
            # (wait robot location)
            return PlanningAction(action="Wait", target=None)

        else:
            print(f"[Planning] Unknown action: {name}")
            return PlanningAction(action="Idle", target=None)

    def get_stats(self) -> Optional[PlanningStats]:
        """Get the last planning statistics."""
        return self.last_stats
