# PDDL-Driven Robot Control Architecture

## Executive Summary

This document describes the architecture for robot control using PDDL (Planning Domain Definition Language) predicates and reactive rules. After extensive experimentation, we've adopted a **hybrid architecture**:

- **Reactive Control (O(1))**: Handles instant decisions (collect objects, recharge batteries)
- **Procedural Control**: Handles movement/exploration with proper path-finding and stuck detection
- **PDDL Planning**: Available for domain validation and occasional high-level planning (not per-tick)

### Key Insight

Per-tick PDDL planning is computationally infeasible for real-time robotics:
- Planning is O(exponential) in the worst case
- Real-time robotics needs O(1) action selection per tick
- The question "what's the best action NOW?" is fundamentally different from "what sequence reaches the goal?"

### Current Implementation Status

| Component | Status | Description |
|-----------|--------|-------------|
| `reactive_control.py` | ✅ Done | O(1) reactive rules for collect/recharge |
| `reactive-controller.ts` | ✅ Done | TypeScript equivalent |
| Procedural fallback | ✅ Done | Movement/exploration uses existing procedural code |
| `pddl_rs` planner | ✅ Available | A* planner for validation (not per-tick) |
| Configurable battery | ✅ Done | `battery_capacity` field on Robot class |

## Hybrid Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       PER-TICK DECISION LOOP                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   for each robot:                                                       │
│       predicates = extract_predicates(world)    // PDDL-style state    │
│                                                                         │
│       // REACTIVE CONTROL (O(1))                                        │
│       if can_recharge(robot, predicates):                               │
│           action = "Recharge"                                           │
│       elif can_collect(robot, predicates):                              │
│           action = "Collect"                                            │
│       else:                                                             │
│           // PROCEDURAL FALLBACK (exploration, path-finding)            │
│           action = determine_action(robot, world)                       │
│                                                                         │
│       execute(action)                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why This Hybrid Approach?

1. **Reactive control** for instant decisions:
   - `can_recharge()`: Check if at base with low battery
   - `can_collect()`: Check if at object location
   - These are O(1) precondition checks, not planning search

2. **Procedural fallback** for movement:
   - Proper path-finding around obstacles
   - Stuck detection and recovery
   - Exploration with frontier detection
   - Pheromone-based communication

3. **PDDL predicates** shared across implementations:
   - `(at ?robot ?location)` - robot position
   - `(adjacent ?loc1 ?loc2)` - cell connectivity
   - `(obstacle ?location)` - blocked cells
   - `(low-battery ?robot)` - battery state
   - `(object-at ?obj ?location)` - collectible positions

## Original Problem Statement

Originally, each language implementation (Python, TypeScript, Rust) duplicated:
- The sense-plan-act control loop
- Exploration scoring algorithms
- Decision-making logic (when to explore, escape, return)
- Direction sampling and pathfinding heuristics

Only the **state** and **behavior parameters** are shared via the ontology. The **planning algorithm itself** remains hardcoded per language.

## Solution: Declarative Planning with PDDL

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SHARED ASSETS (Language-Agnostic)               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   examples/ontologies/robot_simulation.ttl                              │
│   ├── State schema (Robot, Object, Obstacle classes)                   │
│   ├── Behavior parameters (ExplorationConfig, EscapeConfig, etc.)      │
│   └── Inference rules (SWRL-like axioms)                               │
│                                                                         │
│   examples/pddl/robot_exploration_domain.pddl                           │
│   ├── Action definitions (move, collect, explore, return-to-base)      │
│   ├── Preconditions (battery > 0, not obstacle, etc.)                  │
│   └── Effects (position change, battery drain, etc.)                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PLANNING ENGINE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Aries Planner (Rust)                                                  │
│   ├── Native binary for Python/Rust backends                           │
│   ├── WASM compilation for browser                                      │
│   └── up-aries PyPI package for Python integration                     │
│                                                                         │
│   Input:                                                                │
│   ├── Domain: robot_exploration_domain.pddl (static)                   │
│   └── Problem: Generated from current ontology state (dynamic)         │
│                                                                         │
│   Output:                                                               │
│   └── Plan: Sequence of actions [(move robot1 cell_5_3 cell_5_4), ...] │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      THIN EXECUTION LAYER                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Python / TypeScript / Rust implementations become simple executors:  │
│                                                                         │
│   loop {                                                                │
│       state = query_ontology()           // SPARQL                     │
│       problem = generate_pddl(state)     // State → PDDL problem       │
│       plan = aries.solve(domain, problem) // Call planner              │
│       execute(plan[0..N])                // Execute N actions          │
│       update_ontology(observations)      // Sensor feedback            │
│   }                                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Code Simplification Analysis

The following analysis demonstrates the dramatic reduction in code complexity when using PDDL-based planning versus procedural decision logic.

### Before: Procedural Python (~280+ lines)

The current `determine_action()` function in `robot_simulation.py` implements a complex priority-based decision tree:

```python
# robot_simulation.py - determine_action() excerpt
# ~280 lines of complex priority-based logic with many edge cases

def determine_action(client, world, state, robot) -> tuple[str, Position, dict]:
    """Complex priority-based decision tree with many edge cases."""

    # Priority 1: Handle collision (10+ lines)
    if state.get("collision", False) or robot.has_collision:
        robot.has_collision = False
        robot.has_robot_collision = False
        # ... collision handling logic

    # Priority 2: LowBattery -> Return home (5+ lines)
    if state.get("lowBattery", False) or robot.battery < threshold:
        return "ReturnHome", world.home_position, avoidance

    # Priority 3: AtObject -> Collect (10+ lines)
    pickup = world.check_object_pickup(robot)
    if state.get("atObject", False) or pickup:
        if pickup:
            robot.ticks_in_cluster = 0
            return "Collect", pickup.position, avoidance

    # Priority 4: Cluster dispersion - ONTOLOGY-DRIVEN (40+ lines)
    if state.get("shouldDisperse", False) or state.get("priorityDisperse", False):
        dispersion_heading = state.get("dispersionHeading", robot.heading)
        ticks_in_cluster = state.get("ticksInCluster", 0)
        nearby_count = state.get("nearbyRobotCount", 0)

        disperse_dist = 5.0
        target_x = robot.position.x + disperse_dist * math.cos(math.radians(dispersion_heading))
        target_y = robot.position.y + disperse_dist * math.sin(math.radians(dispersion_heading))
        target_x = max(1, min(world.width - 1, target_x))
        target_y = max(1, min(world.height - 1, target_y))

        avoidance["disperseMode"] = True
        # ... more dispersion logic
        return "Explore", Position(target_x, target_y), avoidance

    # Priority 5: ESCAPE MODE - Persistent escape from clutter (80+ lines)
    if known.escape_mode and known.escape_target:
        target_x, target_y = known.escape_target
        dist_to_target = math.sqrt((robot.position.x - target_x)**2 + ...)

        if known.clutter_centroid:
            cx, cy = known.clutter_centroid
            dist_from_clutter = math.sqrt(...)

        if dist_to_target < 2.0 or dist_from_clutter > 12.0 or known.escape_ticks_remaining <= 0:
            known.escape_mode = False
            known.escape_target = None
            known.escape_ticks_remaining = 0
            known.clutter_centroid = None
            known.recent_positions.clear()
            known.coverage_area = 0.0
            known.path_knottiness = 0.0
        else:
            known.escape_ticks_remaining -= 1
            avoidance["escapeMode"] = True
            return "Explore", Position(target_x, target_y), avoidance

    # Check if we should ENTER escape mode (30+ lines)
    should_escape = state.get("shouldVenture", False) or state.get("severelyCircling", False)
    if should_escape or small_coverage:
        # Calculate clutter centroid
        if known.recent_positions:
            cx = sum(p[0] for p in known.recent_positions) / len(known.recent_positions)
            cy = sum(p[1] for p in known.recent_positions) / len(known.recent_positions)

        # Pick random escape direction
        base_angle = math.atan2(robot.position.y - cy, robot.position.x - cx)
        escape_angle = base_angle + random.uniform(-math.pi/2, math.pi/2)
        escape_dist = max(12.0, min(world.width, world.height) / 3)
        # ... more escape calculations
        return "Explore", Position(target_x, target_y), avoidance

    # Priority 6: Move to nearest KNOWN uncollected object (20+ lines)
    nearest_known = known.get_nearest_known_object(robot.position)
    if nearest_known:
        if state.get("mildCluster", False):
            nearby_robots = world.get_nearby_robots(robot, radius=4.0)
            for other in nearby_robots:
                # Target deconfliction logic
                if other_dist < my_dist and other.robot_index < robot.robot_index:
                    alternate = known.get_second_nearest_object(...)
                    if alternate:
                        return "MoveToObject", alternate.position, avoidance
        return "MoveToObject", nearest_known.position, avoidance

    # Priority 7: No known objects - EXPLORE (60+ lines)
    if actual_remaining > 0:
        if robot.is_stuck:
            # Stuck escape logic with escape heading
            if robot.escape_heading is not None:
                explore_heading = robot.escape_heading
            else:
                explore_heading = robot.get_escape_direction(robot.heading)
            if robot.ticks_without_movement > 6:
                explore_heading = random.uniform(0, 360)
        elif robot.needs_venture_out():
            # Venture direction calculation
            explore_heading = robot.get_venture_direction(...)
        elif in_loop:
            # Query ontology for least-visited direction
            explore_heading = query_least_visited_direction(client, world)
            if stuck_counter > 5:
                explore_heading = random.uniform(0, 360)
        else:
            # Frontier-based exploration
            frontier = query_frontier_cells(client, world)
            if frontier:
                nearest_frontier = min(frontier, key=lambda c: ...)
                explore_heading = math.degrees(math.atan2(dy, dx))
            else:
                explore_heading = world.get_exploration_direction(robot)

        return "Explore", Position(...), avoidance

    return "ReturnHome", world.home_position, avoidance
```

**Problems with this approach:**
- 280+ lines of intricate, interleaved logic
- 7+ priority levels with complex conditions
- Manual state management (escape mode, cluster tracking, stuck counters)
- Hard to verify correctness
- Duplicated across Python/TypeScript/Rust implementations
- Adding new behaviors requires modifying the priority chain

### After: PDDL-Based Approach (~50 lines)

```python
# planning_robot.py - PDDL-driven robot control

from dtaas import DTaaSClient

DOMAIN_ID = "robot-exploration-strips"

def determine_action_pddl(client: DTaaSClient, robot, world) -> tuple[str, list]:
    """Let the planner decide - just generate problem and call plan()."""

    # Generate PDDL problem from current world state
    problem_pddl = generate_problem_from_state(robot, world)

    # Ask planner for next action
    plan = client.planning.plan(
        domain_id=DOMAIN_ID,
        problem_pddl=problem_pddl,
        timeout_ms=100,
    )

    if plan.valid and plan.actions:
        action = plan.actions[0]
        return action.name, action.parameters

    return "idle", []


def generate_problem_from_state(robot, world) -> str:
    """Convert world state to PDDL problem - pure data transformation."""

    objects, init = [], []

    # Robot
    objects.append(f"{robot.id} - robot")
    rx, ry = int(robot.position.x), int(robot.position.y)
    init.append(f"(at {robot.id} loc_{rx}_{ry})")

    # Locations and adjacencies
    for x in range(world.width):
        for y in range(world.height):
            objects.append(f"loc_{x}_{y} - location")
            for dx, dy in [(0,1), (1,0), (0,-1), (-1,0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < world.width and 0 <= ny < world.height:
                    init.append(f"(adjacent loc_{x}_{y} loc_{nx}_{ny})")

    # Obstacles
    for obs in world.obstacles:
        init.append(f"(obstacle loc_{int(obs.position.x)}_{int(obs.position.y)})")

    # Objects
    for obj in world.objects:
        if not obj.collected:
            objects.append(f"{obj.id} - object")
            init.append(f"(object-at {obj.id} loc_{int(obj.position.x)}_{int(obj.position.y)})")

    # Battery and base
    if robot.battery < 20:
        init.append(f"(low-battery {robot.id})")
    init.append("(base loc_0_0)")

    # Goal
    uncollected = [obj for obj in world.objects if not obj.collected]
    goal = " ".join(f"(collected {obj.id})" for obj in uncollected) or f"(at {robot.id} loc_0_0)"

    return f"""(define (problem robot-task)
  (:domain robot-exploration-strips)
  (:objects {' '.join(objects)})
  (:init {' '.join(init)})
  (:goal (and {goal}))
)"""


def execute_plan_action(action_name: str, params: list, robot, world):
    """Execute a PDDL action - simple dispatch."""

    if action_name == "move":
        _, _, to_loc = params
        x, y = parse_location(to_loc)
        robot.move_to(x, y)
    elif action_name == "collect":
        _, _, obj_id = params
        world.collect_object(robot, world.get_object(obj_id))
    elif action_name == "recharge":
        robot.battery = 100
    elif action_name == "return-to-base":
        _, _, to_loc = params
        x, y = parse_location(to_loc)
        robot.move_to(x, y)
```

### Comparison Summary

| Aspect | Procedural Python | PDDL-Based |
|--------|-------------------|------------|
| **Lines of code** | 280+ lines | ~50 lines |
| **Decision logic** | Complex priority tree | Declarative domain |
| **State management** | Manual flags & counters | PDDL predicates |
| **Edge cases** | Each handled explicitly | Handled by preconditions |
| **Adding new behavior** | Modify priority chain | Add action to domain |
| **Correctness** | Hard to verify | Planner guarantees validity |
| **Cross-language** | Duplicated per language | Single PDDL domain |

### What the PDDL Domain Handles Automatically

The declarative PDDL domain specifies:

```pddl
(:action move
  :parameters (?r - robot ?from - location ?to - location)
  :precondition (and
    (at ?r ?from)           ; Must be at source
    (adjacent ?from ?to)    ; Cells must be adjacent
    (not (obstacle ?to))    ; Can't move into obstacles
    (not (low-battery ?r))  ; Battery must not be low
  )
  :effect (and
    (at ?r ?to)             ; Now at destination
    (not (at ?r ?from))     ; No longer at source
    (explored ?r ?to)       ; Mark as explored
  )
)
```

The planner automatically handles:
- **Goal-directed behavior** - finds optimal path to collect all objects
- **Obstacle avoidance** - preconditions prevent invalid moves
- **Battery management** - low-battery triggers return-to-base
- **Valid action sequencing** - only executable actions are planned
- **Replanning** - when world changes, just regenerate problem

### Migration Path

The existing procedural code can be migrated incrementally:

1. **Keep ontology for state** - Continue using SPARQL for sensor data
2. **Add PDDL for planning** - Replace `determine_action()` with planner call
3. **Simplify executors** - Reduce to state→problem and action dispatch
4. **Share PDDL domain** - Same domain works for Python, TypeScript, Rust

## File Structure

```
examples/
├── ontologies/
│   └── robot_simulation.ttl          # Existing ontology (state + params)
│
├── pddl/
│   ├── robot_exploration_domain.pddl # Action definitions (NEW)
│   └── README.md                     # PDDL documentation
│
├── robotics/
│   ├── robot_simulation.py           # Python executor (simplified)
│   ├── browser/                      # TypeScript executor (simplified)
│   └── planner/                      # Aries integration (NEW)
│       ├── Cargo.toml
│       ├── src/
│       │   ├── lib.rs               # Aries wrapper
│       │   ├── problem_generator.rs # Ontology state → PDDL problem
│       │   └── wasm.rs              # WASM bindings
│       └── pkg/                     # WASM output for browser
│
└── PDDL_PLANNING_ARCHITECTURE.md     # This document
```

## PDDL Domain Design

### Domain: `robot_exploration_domain.pddl`

```pddl
(define (domain robot-exploration)
  (:requirements :strips :typing :numeric-fluents :negative-preconditions)

  ;; ==========================================================================
  ;; TYPES
  ;; ==========================================================================
  (:types
    robot - agent
    cell - location
    object - collectible
    quadrant - region
  )

  ;; ==========================================================================
  ;; PREDICATES (Boolean state)
  ;; ==========================================================================
  (:predicates
    ;; Spatial relationships
    (at ?r - robot ?c - cell)
    (adjacent ?c1 - cell ?c2 - cell)
    (obstacle ?c - cell)
    (base ?c - cell)

    ;; Object state
    (object-at ?o - object ?c - cell)
    (collected ?o - object)
    (carrying ?r - robot ?o - object)

    ;; Exploration state
    (explored ?r - robot ?c - cell)
    (in-quadrant ?c - cell ?q - quadrant)
    (visited-quadrant ?r - robot ?q - quadrant)

    ;; Robot state flags
    (low-battery ?r - robot)
    (escaping ?r - robot)
    (idle ?r - robot)
  )

  ;; ==========================================================================
  ;; NUMERIC FLUENTS (Continuous state)
  ;; ==========================================================================
  (:functions
    (battery ?r - robot)                    ; Current battery level
    (pos-x ?r - robot)                      ; X coordinate (for distance calc)
    (pos-y ?r - robot)                      ; Y coordinate
    (objects-collected ?r - robot)          ; Count of collected objects
    (exploration-priority ?c - cell)        ; Computed from ontology params

    ;; Constants from ontology (injected into problem)
    (low-battery-threshold)
    (quadrant-crossing-bonus)
    (unexplored-bonus)
  )

  ;; ==========================================================================
  ;; ACTIONS
  ;; ==========================================================================

  ;; Move to adjacent cell
  (:action move
    :parameters (?r - robot ?from - cell ?to - cell)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (> (battery ?r) 0)
      (not (low-battery ?r))
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (explored ?r ?to)
      (decrease (battery ?r) 1)
    )
  )

  ;; Collect object at current location
  (:action collect
    :parameters (?r - robot ?c - cell ?o - object)
    :precondition (and
      (at ?r ?c)
      (object-at ?o ?c)
      (not (collected ?o))
    )
    :effect (and
      (collected ?o)
      (not (object-at ?o ?c))
      (increase (objects-collected ?r) 1)
    )
  )

  ;; Move toward unexplored high-priority cell
  (:action explore
    :parameters (?r - robot ?from - cell ?to - cell ?q - quadrant)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (not (explored ?r ?to))
      (in-quadrant ?to ?q)
      (not (low-battery ?r))
      (> (exploration-priority ?to) 0)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (explored ?r ?to)
      (visited-quadrant ?r ?q)
      (decrease (battery ?r) 1)
    )
  )

  ;; Return to base when battery is low
  (:action return-to-base
    :parameters (?r - robot ?from - cell ?to - cell)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (base ?to)
      (low-battery ?r)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (not (low-battery ?r))
      (assign (battery ?r) 100)
    )
  )

  ;; Escape from stuck position (random direction)
  (:action escape
    :parameters (?r - robot ?from - cell ?to - cell)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (escaping ?r)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (not (escaping ?r))
      (decrease (battery ?r) 1)
    )
  )
)
```

## Problem Generation

The dynamic PDDL problem is generated from the current ontology state:

### Rust Implementation

```rust
// planner/src/problem_generator.rs

use oxigraph::store::Store;
use oxigraph::sparql::QueryResults;

pub struct ProblemGenerator {
    store: Store,
    domain_params: DomainParams,
}

#[derive(Debug)]
pub struct DomainParams {
    pub low_battery_threshold: f64,
    pub quadrant_crossing_bonus: f64,
    pub unexplored_bonus: f64,
}

impl ProblemGenerator {
    /// Query ontology and generate PDDL problem string
    pub fn generate(&self) -> String {
        let robots = self.query_robots();
        let cells = self.query_cells();
        let objects = self.query_objects();
        let obstacles = self.query_obstacles();
        let explored = self.query_explored();

        format!(r#"
(define (problem robot-exploration-current)
  (:domain robot-exploration)

  (:objects
    {robots}
    {cells}
    {objects}
    q1 q2 q3 q4 - quadrant
  )

  (:init
    ;; Robot positions and battery
    {robot_positions}
    {robot_batteries}
    {low_battery_flags}

    ;; Cell adjacencies
    {adjacencies}

    ;; Obstacles
    {obstacle_facts}

    ;; Objects
    {object_facts}

    ;; Explored cells
    {explored_facts}

    ;; Ontology-derived parameters
    (= (low-battery-threshold) {low_battery_threshold})
    (= (quadrant-crossing-bonus) {quadrant_crossing_bonus})
    (= (unexplored-bonus) {unexplored_bonus})

    ;; Exploration priorities (computed from ontology params)
    {exploration_priorities}
  )

  (:goal (and
    {goal_objects_collected}
  ))
)
"#,
            robots = self.format_robot_objects(&robots),
            cells = self.format_cell_objects(&cells),
            objects = self.format_object_objects(&objects),
            robot_positions = self.format_robot_positions(&robots),
            robot_batteries = self.format_robot_batteries(&robots),
            low_battery_flags = self.format_low_battery_flags(&robots),
            adjacencies = self.generate_adjacencies(&cells),
            obstacle_facts = self.format_obstacles(&obstacles),
            object_facts = self.format_objects(&objects),
            explored_facts = self.format_explored(&explored),
            low_battery_threshold = self.domain_params.low_battery_threshold,
            quadrant_crossing_bonus = self.domain_params.quadrant_crossing_bonus,
            unexplored_bonus = self.domain_params.unexplored_bonus,
            exploration_priorities = self.compute_exploration_priorities(&cells, &explored),
            goal_objects_collected = self.format_goal(&objects),
        )
    }

    fn query_robots(&self) -> Vec<RobotState> {
        let query = r#"
            PREFIX robo: <http://tesserai.io/ontology/robot_simulation#>
            SELECT ?id ?x ?y ?battery WHERE {
                ?robot a robo:Robot ;
                       robo:robotId ?id ;
                       robo:positionX ?x ;
                       robo:positionY ?y ;
                       robo:batteryLevel ?battery .
            }
        "#;
        // ... execute query and parse results
    }

    fn compute_exploration_priorities(
        &self,
        cells: &[Cell],
        explored: &HashSet<(i32, i32)>
    ) -> String {
        // Apply ontology-derived scoring algorithm:
        // - unexplored_bonus for unvisited cells
        // - quadrant_crossing_bonus for cells in different quadrant
        // - distance factors from ontology params
        cells.iter()
            .filter(|c| !explored.contains(&(c.x, c.y)))
            .map(|c| {
                let priority = self.calculate_priority(c);
                format!("(= (exploration-priority cell_{x}_{y}) {p})",
                    x = c.x, y = c.y, p = priority)
            })
            .collect::<Vec<_>>()
            .join("\n    ")
    }
}
```

## Aries Integration

### Native Rust Usage

```rust
// planner/src/lib.rs

use aries::core::Lit;
use aries::planning::parsing::pddl;
use aries::planning::chronicles::Problem;
use aries::solver::Solver;

pub struct AriesPlanner {
    domain: String,
}

impl AriesPlanner {
    pub fn new(domain_path: &str) -> Self {
        let domain = std::fs::read_to_string(domain_path)
            .expect("Failed to read PDDL domain");
        Self { domain }
    }

    pub fn solve(&self, problem: &str) -> Result<Plan, PlanningError> {
        // Parse domain and problem
        let dom = pddl::parse_pddl_domain(&self.domain)?;
        let prob = pddl::parse_pddl_problem(problem, &dom)?;

        // Build chronicles problem
        let chronicles = Problem::from_pddl(dom, prob)?;

        // Solve
        let mut solver = Solver::new(chronicles);
        match solver.solve() {
            Some(solution) => Ok(self.extract_plan(solution)),
            None => Err(PlanningError::NoPlanFound),
        }
    }

    fn extract_plan(&self, solution: Solution) -> Plan {
        Plan {
            actions: solution.actions()
                .map(|a| PlanAction {
                    name: a.name().to_string(),
                    params: a.params().map(|p| p.to_string()).collect(),
                })
                .collect()
        }
    }
}

#[derive(Debug)]
pub struct Plan {
    pub actions: Vec<PlanAction>,
}

#[derive(Debug)]
pub struct PlanAction {
    pub name: String,
    pub params: Vec<String>,
}
```

### WASM Bindings for Browser

```rust
// planner/src/wasm.rs

use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub struct WasmPlanner {
    planner: AriesPlanner,
}

#[wasm_bindgen]
impl WasmPlanner {
    #[wasm_bindgen(constructor)]
    pub fn new(domain_pddl: &str) -> Self {
        Self {
            planner: AriesPlanner::from_string(domain_pddl),
        }
    }

    #[wasm_bindgen]
    pub fn solve(&self, problem_pddl: &str) -> Result<JsValue, JsError> {
        let plan = self.planner.solve(problem_pddl)
            .map_err(|e| JsError::new(&e.to_string()))?;

        // Return as JSON for JavaScript consumption
        Ok(serde_wasm_bindgen::to_value(&plan)?)
    }
}
```

### Python Integration (via up-aries)

```python
# robot_simulation.py

from unified_planning.shortcuts import *
from up_aries import AriesEngine

class PlanningController:
    def __init__(self, domain_path: str, ontology_store: OntologyStore):
        self.domain_path = domain_path
        self.ontology = ontology_store
        self.planner = AriesEngine()

    def get_next_actions(self, horizon: int = 5) -> list[Action]:
        """Generate plan from current state and return next N actions."""
        # 1. Generate PDDL problem from ontology state
        problem_pddl = self.generate_problem()

        # 2. Parse and solve
        problem = self.parse_problem(problem_pddl)
        result = self.planner.solve(problem)

        if result.status == PlanGenerationResultStatus.SOLVED:
            return list(result.plan.actions)[:horizon]
        else:
            return []

    def generate_problem(self) -> str:
        """Query ontology and generate PDDL problem."""
        state = self.ontology.get_current_state()
        params = self.ontology.get_behavior_params()

        return f"""
(define (problem robot-current)
  (:domain robot-exploration)

  (:objects
    {self._format_robots(state.robots)}
    {self._format_cells(state.width, state.height)}
    {self._format_objects(state.objects)}
  )

  (:init
    {self._format_init(state, params)}
  )

  (:goal (and
    {self._format_goal(state.objects)}
  ))
)
"""
```

## Execution Loop (Unified Across Languages)

The execution loop becomes nearly identical in every language:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EXECUTION LOOP (Pseudocode)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   REPLAN_HORIZON = 5  // Execute 5 actions before replanning           │
│                                                                         │
│   while not goal_reached():                                             │
│       # 1. SENSE: Get current state from ontology                       │
│       state = ontology.query_current_state()                            │
│                                                                         │
│       # 2. PLAN: Generate problem and solve                             │
│       problem = generate_pddl_problem(state, ontology.params)           │
│       plan = planner.solve(domain, problem)                             │
│                                                                         │
│       if plan.empty():                                                  │
│           handle_no_plan()  // Escape behavior                          │
│           continue                                                      │
│                                                                         │
│       # 3. ACT: Execute first N actions                                 │
│       for action in plan[0:REPLAN_HORIZON]:                             │
│           execute_action(action)                                        │
│           update_ontology_from_sensors()                                │
│                                                                         │
│           # Check for replanning triggers                               │
│           if unexpected_obstacle() or object_collected():               │
│               break  // Replan immediately                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### TypeScript Executor

```typescript
// browser/src/planning-executor.ts

export class PlanningExecutor {
  private planner: WasmPlanner;
  private ontology: OntologyStore;
  private domain: string;

  constructor(domainPddl: string, ontology: OntologyStore) {
    this.planner = new WasmPlanner(domainPddl);
    this.ontology = ontology;
    this.domain = domainPddl;
  }

  tick(): void {
    // 1. Generate problem from ontology state
    const problem = this.generateProblem();

    // 2. Get plan from Aries
    const plan = this.planner.solve(problem);

    // 3. Execute first action
    if (plan.actions.length > 0) {
      this.executeAction(plan.actions[0]);
    }
  }

  private executeAction(action: PlanAction): void {
    switch (action.name) {
      case 'move':
      case 'explore':
        const [robot, from, to] = action.params;
        this.ontology.updateRobotPosition(robot, to);
        break;
      case 'collect':
        const [r, cell, obj] = action.params;
        this.ontology.markObjectCollected(obj);
        break;
      case 'return-to-base':
        const [rob, f, base] = action.params;
        this.ontology.updateRobotPosition(rob, base);
        this.ontology.rechargeBattery(rob);
        break;
    }
  }
}
```

### Python Executor

```python
# robot_simulation.py

class PlanningExecutor:
    def __init__(self, domain_path: str, ontology: OntologyStore):
        self.planner = AriesPlanner(domain_path)
        self.ontology = ontology

    def tick(self) -> None:
        # 1. Generate problem from ontology state
        problem = self.generate_problem()

        # 2. Get plan from Aries
        plan = self.planner.solve(problem)

        # 3. Execute first action
        if plan.actions:
            self.execute_action(plan.actions[0])

    def execute_action(self, action: PlanAction) -> None:
        match action.name:
            case 'move' | 'explore':
                robot, from_cell, to_cell = action.params
                self.ontology.update_robot_position(robot, to_cell)
            case 'collect':
                robot, cell, obj = action.params
                self.ontology.mark_object_collected(obj)
            case 'return-to-base':
                robot, from_cell, base = action.params
                self.ontology.update_robot_position(robot, base)
                self.ontology.recharge_battery(robot)
```

## Implementation Phases

### Phase 1: PDDL Domain Creation ✅ COMPLETE
- [x] Create `examples/pddl/robot_exploration_domain.pddl` (full version with numeric fluents)
- [x] Create `examples/pddl/robot_exploration_strips.pddl` (STRIPS version for SimplePlanner)
- [x] Define all actions with correct preconditions/effects (move, collect, return-to-base, recharge)
- [x] Test domain syntax via planning API validation endpoint
- [x] Document mapping between ontology concepts and PDDL predicates (this document)

### Phase 2: Planning Engine (Rust) ✅ COMPLETE
> **Note:** Implemented with SimplePlanner (BFS forward search) instead of Aries for simplicity.
> Aries integration can be added later for more advanced planning capabilities.

- [x] Create planning modules in `src/` (planning.rs, planning_service.rs, simple_planner.rs, pddl_parser.rs)
- [x] Implement PDDL parser for domain and problem files
- [x] Implement SimplePlanner with BFS forward search
- [x] Implement problem generator (twin state → PDDL problem via `generate_problem_from_twin`)
- [x] Implement solution parser (plan → action list with parameters)
- [x] Write unit tests with sample problems (tests.rs)
- [x] Add authentication to planning API endpoints

### Phase 3: Browser Planning Integration ✅ COMPLETE
> **Note:** Instead of compiling SimplePlanner to WASM, we integrated with the Planning REST API.
> This provides the same functionality with simpler architecture.

- [x] Create planning-client.ts for API communication
- [x] Create problem-generator.ts for PDDL problem generation from world state
- [x] Create planning-controller.ts for simulation integration
- [x] Bundle PDDL domain as static asset in browser app (embedded in main.ts)
- [x] Display PDDL domain in browser UI (PDDL tab with syntax highlighting)
- [x] Add planning mode toggle to browser UI
- [x] Integrate planning API calls into browser simulation tick
- [x] Show planning statistics (time, states explored, plan length)

### Phase 4: Python SDK Integration ✅ COMPLETE
- [x] Add PlanningResource to Python SDK (dtaas/client.py)
- [x] Add planning models (PddlDomain, Plan, PlanAction, PlanningStats, etc.)
- [x] Create planning_demo.py example script
- [x] Implement validate, create_domain, plan API methods
- [ ] Refactor robot_simulation.py to use planner (optional - demo works standalone)
- [ ] Verify behavior matches original implementation

### Phase 5: Simplify Existing Code 🚧 IN PROGRESS
- [ ] Remove hardcoded exploration algorithms from TypeScript browser app
- [ ] Remove hardcoded exploration algorithms from Python robot_simulation.py
- [ ] Keep only thin execution layer
- [x] Update documentation (this document, Code Simplification Analysis section)
- [x] Add PDDL display to browser and web_simulation UIs

## Future Framework Considerations

This architecture sets the stage for a reusable framework:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     DOMAIN DEVELOPMENT FRAMEWORK                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   dtaas-cli new-domain warehouse-robots                                 │
│                                                                         │
│   Creates:                                                              │
│   ├── ontology/                                                         │
│   │   └── warehouse_robots.ttl      # State schema template             │
│   ├── pddl/                                                             │
│   │   └── warehouse_domain.pddl     # Action definitions                │
│   ├── executors/                                                        │
│   │   ├── python/                   # Generated executor stub           │
│   │   ├── typescript/               # Generated executor stub           │
│   │   └── rust/                     # Generated executor stub           │
│   └── tests/                                                            │
│       └── scenarios/                # Test scenarios                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Multi-Robot Coordination (Declarative Collision Avoidance)

A key benefit of PDDL planning is handling multi-robot coordination **declaratively** rather than with procedural code. This section documents the architecture.

### The Problem

When multiple robots return home simultaneously (e.g., low battery), they tend to clump together and get stuck. The procedural solution would require:

```typescript
// BAD: Procedural collision avoidance - must be duplicated in every language
function checkCollision(robot, newPos) {
  for (const other of robots) {
    if (other.id !== robot.id && distance(newPos, other.position) < 1.2) {
      return true; // Would collide with another robot
    }
  }
  return false;
}

function getHomeOffset(robot) {
  const angle = (robot.index / numRobots) * Math.PI * 2;
  return { x: Math.cos(angle) * 2, y: Math.sin(angle) * 2 };
}
```

This code must be replicated in Python, TypeScript, Rust, etc.

### The Solution: Declarative Predicates

With PDDL, collision avoidance is encoded in the **domain once**:

```pddl
(:predicates
  (robot-blocking ?l - location)         ; Cell occupied by another robot
  (home-position ?r - robot ?l - location)  ; Per-robot home (offset from base)
)

(:action move
  :precondition (and
    (at ?r ?from)
    (adjacent ?from ?to)
    (not (obstacle ?to))
    (not (robot-blocking ?to))           ; Cannot move into cell with another robot
  )
  :effect (and
    (at ?r ?to)
    (robot-blocking ?to)                 ; Mark new position as blocked
    (not (robot-blocking ?from))         ; Clear old position
  )
)
```

### Problem Generation with Robot Blocking

The problem generator adds facts about blocked cells:

```typescript
// problem-generator.ts
for (const otherRobot of world.robots) {
  if (otherRobot.id === robotId) continue; // Skip self
  if (!otherRobot.isActive) continue;

  const otherGridX = Math.floor(otherRobot.position.x);
  const otherGridY = Math.floor(otherRobot.position.y);
  const otherLoc = `loc_${otherGridX}_${otherGridY}`;

  init.push(`(robot-blocking ${otherLoc})`);
}
```

### Per-Robot Home Positions

Each robot gets a unique home position offset from the base:

```typescript
function calculateHomeOffset(robotIndex: number): { dx: number; dy: number } {
  if (robotIndex === 0) return { dx: 0, dy: 0 };
  const angle = ((robotIndex - 1) % 8) / 8 * Math.PI * 2;
  return {
    dx: Math.round(Math.cos(angle) * 2),
    dy: Math.round(Math.sin(angle) * 2),
  };
}
```

This is added to the problem as a per-robot predicate:
```pddl
(home-position robot1 loc_10_10)
(home-position robot2 loc_12_10)
(home-position robot3 loc_10_12)
```

### Wait Action

When a robot's path is blocked by another robot, the planner can choose to wait:

```pddl
(:action wait
  :parameters (?r - robot ?l - location)
  :precondition (at ?r ?l)
  :effect ()  ; No state change
)
```

This is better than getting stuck - the robot explicitly waits one tick.

### Ontology Extensions

The `robot_simulation.ttl` ontology includes multi-robot coordination concepts:

```turtle
# Spatial blocking properties
robo:occupiesCell a owl:ObjectProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range robo:GridCell .

robo:blockedByRobot a owl:ObjectProperty ;
    rdfs:domain robo:GridCell ;
    rdfs:range robo:Robot .

robo:assignedHomeCell a owl:ObjectProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range robo:HomeCell .

robo:homeOffsetIndex a owl:DatatypeProperty ;
    rdfs:domain robo:Robot ;
    rdfs:range xsd:integer .

# Inference rule for blocked cells
robo:Rule_BlockedCell a robo:InferenceRule ;
    robo:ruleCondition "robot.occupiesCell = cell AND robot.isActive = true" ;
    robo:ruleConclusion "cell.blockedByRobot = robot" .
```

### Architecture Benefits

| Aspect | Procedural (Before) | Declarative (After) |
|--------|---------------------|---------------------|
| **Collision check** | Each language implements | PDDL precondition once |
| **Home offset** | Hardcoded in each lang | Problem generator adds facts |
| **Stuck handling** | Complex retry logic | Planner chooses `wait` action |
| **Testing** | Integration tests per lang | Unit test PDDL domain once |
| **New behaviors** | Modify 3+ codebases | Add action to domain |

### Ontology ↔ PDDL Synchronization

The framework should ensure consistency:

| Ontology (RDF/OWL) | PDDL |
|--------------------|------|
| `robo:Robot` class | `robot` type |
| `robo:positionX/Y` properties | `(at ?r ?c)` predicate |
| `robo:batteryLevel` property | `(battery ?r)` function |
| `robo:lowBatteryThreshold` param | `(low-battery-threshold)` constant |
| SWRL rules | Action preconditions/effects |

A validation tool should check that:
1. All ontology classes have corresponding PDDL types
2. All PDDL predicates map to ontology properties
3. Behavior parameters in ontology are injected into PDDL problems

## References

- [Aries Planner](https://github.com/plaans/aries) - Rust planning solver
- [PDDL 2.1 Specification](https://planning.wiki/ref/pddl21) - Numeric fluents
- [Unified Planning Framework](https://unified-planning.readthedocs.io/) - Python integration
- [TesseraiDB](https://github.com/penserai/tesseraidb) - Ontology storage
