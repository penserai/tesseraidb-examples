#!/usr/bin/env python3
"""
Robot Simulation with Ontology-Driven Reasoning and Partial Observability
==========================================================================

This example demonstrates how to use semantic reasoning to control a robot
in a simulated 2D grid world with PARTIAL OBSERVABILITY. The robot must
collect objects while avoiding obstacles, discovering the world as it moves.

Partial Observability Model:
- The robot can only see entities within its sensor_range
- Grid borders are unknown until the robot reaches or sees them
- Objects and obstacles are discovered when they enter sensor range
- The ontology only contains KNOWN/DISCOVERED information
- The robot cannot use global world knowledge for strategy

Key Concepts:
- The ontology is the robot's "brain memory" - stores only DISCOVERED state
- SWRL rules are the robot's "logic" - they determine what action to take
- SPARQL queries are the robot's "eyes" - they query the discovered state

The Simulation Loop:
1. SENSE: Discover new entities in sensor range, update ontology
2. REASON: Fire SWRL rules to infer next action and update metrics
3. QUERY: Use SPARQL to get the decided action from discovered state
4. ACT: Execute the action (explore if no known targets)
5. REPEAT

Usage:
    python robot_simulation.py [--base-url URL] [--ticks N] [--visualize]
"""

import os
import sys
import argparse
import math
import random
import time
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'sdks', 'python'))

from dtaas import DTaaSClient, WebSocketClient, WebSocketTwinClient
from dtaas.exceptions import DTaaSError

# Reactive Control Integration
# This module provides reactive rule evaluation - collision avoidance and action
# selection are handled by direct precondition checks, not expensive planning search.
# This is O(1) per tick instead of O(exponential) planning.
try:
    from reactive_control import get_reactive_action, ReactiveAction
    REACTIVE_CONTROL_AVAILABLE = True
except ImportError:
    REACTIVE_CONTROL_AVAILABLE = False
    get_reactive_action = None
    ReactiveAction = None

# PDDL Planning (kept for domain validation, not used for per-tick decisions)
try:
    from pddl_planning import PlanningController, PlanningAction
    PDDL_PLANNING_AVAILABLE = True
except ImportError:
    PDDL_PLANNING_AVAILABLE = False
    PlanningController = None
    PlanningAction = None

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import DEFAULT_BASE_URL, get_api_key

# Configuration
BASE_URL = os.environ.get("TESSERAI_API_URL", DEFAULT_BASE_URL)


def get_token():
    """Get authentication token from API key."""
    token = get_api_key()
    if not token:
        print("Error: No API key provided. Set TESSERAI_API_KEY environment variable.")
        print("Get your API key from https://tesserai.io")
        sys.exit(1)
    return token

# Ontology namespace
ROBO = "http://tesserai.io/ontology/robot_simulation#"
TWIN_ID = "robot-simulation"

# =============================================================================
# PERFORMANCE OPTIMIZATION
# =============================================================================
#
# This simulation uses optimized batch updates via the /api/v1/sparql/batch-update
# endpoint for efficient ontology operations:
#
# - Single combined SPARQL UPDATE per tick for all robots
# - Uses transactional batch API for atomic updates
# - 1-2 HTTP requests per tick regardless of robot count
# - Performance: ~3.8 seconds for 30 ticks with 5 robots
#
# TIMESERIES MODE (USE_TIMESERIES=True):
#    - Uses /api/v1/twins/{id}/timeseries for position history
#    - Efficient for time-series queries with aggregation
#
USE_TIMESERIES = False  # Set to True to enable timeseries position tracking


# =============================================================================
# BEHAVIOR CONFIGURATION - Loaded from ontology for language-agnostic design
# =============================================================================
# These parameters are defined in examples/ontologies/robot_simulation.ttl
# and queried at runtime. Both Python and TypeScript use the same values.

@dataclass
class ExplorationConfig:
    """Exploration scoring parameters from ontology."""
    quadrant_crossing_bonus: float = 40.0
    same_quadrant_penalty: float = 20.0
    center_approach_bonus: float = 30.0
    edge_distance_threshold: float = 0.3
    unexplored_target_bonus: float = 25.0
    unexplored_path_bonus: float = 10.0
    distance_bonus_multiplier: float = 0.5
    direction_sample_count: int = 24
    venture_distance_factor: float = 2.5
    grid_margin_factor: float = 0.1


@dataclass
class EscapeConfig:
    """Escape behavior parameters from ontology."""
    angle_variance: float = 90.0
    base_angle_offset: float = 180.0
    tick_duration: int = 25
    min_distance: float = 12.0
    distance_factor: float = 3.0
    target_reached_distance: float = 2.0
    clutter_clear_distance: float = 12.0


@dataclass
class DetectionConfig:
    """Detection threshold parameters from ontology."""
    low_battery_threshold: float = 20.0
    battery_drain_rate: float = 0.05
    at_object_distance: float = 1.0
    near_object_distance: float = 3.0
    must_avoid_distance: float = 1.5
    emergency_avoid_distance: float = 0.8
    small_coverage_threshold: float = 15.0
    severely_coverage_threshold: float = 8.0
    high_knottiness_threshold: float = 9.42  # ~3π
    very_high_knottiness_threshold: float = 18.84  # ~6π
    min_positions_for_detection: int = 10
    low_unique_cells_ratio: float = 0.4
    repeated_visit_threshold: int = 3


@dataclass
class ActionConfig:
    """Action execution parameters from ontology."""
    default_speed: float = 1.0
    turn_rate_explore: float = 25.0
    turn_rate_direct: float = 90.0
    avoidance_check_distance: float = 2.0
    collision_buffer: float = 0.3
    obstacle_buffer: float = 0.5
    avoidance_jitter: float = 20.0
    turn_around_jitter: float = 90.0
    world_boundary_margin: float = 3.0


@dataclass
class BehaviorConfig:
    """All behavior parameters loaded from ontology."""
    exploration: ExplorationConfig = field(default_factory=ExplorationConfig)
    escape: EscapeConfig = field(default_factory=EscapeConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    action: ActionConfig = field(default_factory=ActionConfig)


# Global behavior config - loaded from ontology at startup
_behavior_config: Optional[BehaviorConfig] = None

# Global PDDL planning controller - handles declarative robot control
_planning_controller: Optional['PlanningController'] = None


def get_behavior_config() -> BehaviorConfig:
    """Get the global behavior config (lazy initialization with defaults)."""
    global _behavior_config
    if _behavior_config is None:
        _behavior_config = BehaviorConfig()
    return _behavior_config


def init_planning_controller(client: DTaaSClient) -> bool:
    """Initialize the global PDDL planning controller.

    This sets up declarative planning where:
    - Collision avoidance is handled by PDDL predicates (robot-blocking)
    - Multi-robot coordination is automatic via the planner
    - No procedural decision logic needed in clients

    Returns:
        True if planning was successfully initialized
    """
    global _planning_controller

    if not PDDL_PLANNING_AVAILABLE:
        log("[Planning] PDDL planning module not available")
        return False

    try:
        _planning_controller = PlanningController(client)
        if _planning_controller.initialize():
            log("[Planning] PDDL planning controller initialized")
            return True
        else:
            _planning_controller = None
            return False
    except Exception as e:
        log(f"[Planning] Failed to initialize: {e}")
        _planning_controller = None
        return False


def get_planning_controller() -> Optional['PlanningController']:
    """Get the global planning controller (may be None if not initialized)."""
    return _planning_controller


def get_pddl_action(world, robot) -> Optional['PlanningAction']:
    """Get the next action for a robot from PDDL planning.

    NOTE: This is kept for backwards compatibility but is no longer used
    for per-tick decisions. Use get_robot_action() instead which uses
    reactive control (O(1) instead of O(exponential)).

    Returns:
        PlanningAction or None if planning is not available/failed
    """
    if _planning_controller is None:
        return None
    return _planning_controller.get_next_action(world, robot)


def get_robot_action(world, robot) -> Optional['ReactiveAction']:
    """Get the next action for a robot using reactive control.

    This uses direct precondition evaluation instead of planning search:
    - O(1) per tick instead of O(exponential) planning
    - Same PDDL semantics (predicates, preconditions)
    - Much faster and suitable for real-time control

    Priority:
    1. Recharge if at base with low battery
    2. Move toward home if low battery
    3. Collect object at current location
    4. Move toward nearest object
    5. Explore (move to unblocked neighbor)

    Returns:
        ReactiveAction or None if reactive control is not available
    """
    if not REACTIVE_CONTROL_AVAILABLE or get_reactive_action is None:
        return None
    return get_reactive_action(world, robot)


def load_behavior_config_from_ontology(client: DTaaSClient) -> BehaviorConfig:
    """Load behavior parameters from ontology via SPARQL query.

    This is the key to language-agnostic design - parameters live in the
    ontology, not hardcoded in Python.
    """
    global _behavior_config

    query = f"""
    PREFIX robo: <{ROBO}>
    SELECT
        ?quadrantCrossingBonus ?sameQuadrantPenalty ?centerApproachBonus
        ?edgeDistanceThreshold ?unexploredTargetBonus ?unexploredPathBonus
        ?distanceBonusMultiplier ?directionSampleCount ?ventureDistanceFactor
        ?gridMarginFactor
        ?escapeAngleVariance ?escapeBaseAngleOffset ?escapeTickDuration
        ?escapeMinDistance ?escapeDistanceFactor ?escapeTargetReachedDistance
        ?escapeClutterClearDistance
        ?lowBatteryThreshold ?batteryDrainRate ?atObjectDistance ?nearObjectDistance
        ?mustAvoidDistance ?emergencyAvoidDistance ?smallCoverageThreshold
        ?severelyCoverageThreshold ?highKnottinessThreshold ?veryHighKnottinessThreshold
        ?minPositionsForDetection ?lowUniqueCellsRatio ?repeatedVisitThreshold
        ?defaultSpeed ?turnRateExplore ?turnRateDirect ?avoidanceCheckDistance
        ?collisionBuffer ?obstacleBuffer ?avoidanceJitter ?turnAroundJitter
        ?worldBoundaryMargin
    WHERE {{
        ?exploreConfig a robo:ExplorationConfig .
        ?exploreConfig robo:quadrantCrossingBonus ?quadrantCrossingBonus .
        ?exploreConfig robo:sameQuadrantPenalty ?sameQuadrantPenalty .
        ?exploreConfig robo:centerApproachBonus ?centerApproachBonus .
        ?exploreConfig robo:edgeDistanceThreshold ?edgeDistanceThreshold .
        ?exploreConfig robo:unexploredTargetBonus ?unexploredTargetBonus .
        ?exploreConfig robo:unexploredPathBonus ?unexploredPathBonus .
        ?exploreConfig robo:distanceBonusMultiplier ?distanceBonusMultiplier .
        ?exploreConfig robo:directionSampleCount ?directionSampleCount .
        ?exploreConfig robo:ventureDistanceFactor ?ventureDistanceFactor .
        ?exploreConfig robo:gridMarginFactor ?gridMarginFactor .

        ?escapeConfig a robo:EscapeConfig .
        ?escapeConfig robo:escapeAngleVariance ?escapeAngleVariance .
        ?escapeConfig robo:escapeBaseAngleOffset ?escapeBaseAngleOffset .
        ?escapeConfig robo:escapeTickDuration ?escapeTickDuration .
        ?escapeConfig robo:escapeMinDistance ?escapeMinDistance .
        ?escapeConfig robo:escapeDistanceFactor ?escapeDistanceFactor .
        ?escapeConfig robo:escapeTargetReachedDistance ?escapeTargetReachedDistance .
        ?escapeConfig robo:escapeClutterClearDistance ?escapeClutterClearDistance .

        ?detectConfig a robo:DetectionConfig .
        ?detectConfig robo:lowBatteryThreshold ?lowBatteryThreshold .
        ?detectConfig robo:batteryDrainRate ?batteryDrainRate .
        ?detectConfig robo:atObjectDistance ?atObjectDistance .
        ?detectConfig robo:nearObjectDistance ?nearObjectDistance .
        ?detectConfig robo:mustAvoidDistance ?mustAvoidDistance .
        ?detectConfig robo:emergencyAvoidDistance ?emergencyAvoidDistance .
        ?detectConfig robo:smallCoverageThreshold ?smallCoverageThreshold .
        ?detectConfig robo:severelyCoverageThreshold ?severelyCoverageThreshold .
        ?detectConfig robo:highKnottinessThreshold ?highKnottinessThreshold .
        ?detectConfig robo:veryHighKnottinessThreshold ?veryHighKnottinessThreshold .
        ?detectConfig robo:minPositionsForDetection ?minPositionsForDetection .
        ?detectConfig robo:lowUniqueCellsRatio ?lowUniqueCellsRatio .
        ?detectConfig robo:repeatedVisitThreshold ?repeatedVisitThreshold .

        ?actionConfig a robo:ActionConfig .
        ?actionConfig robo:defaultSpeed ?defaultSpeed .
        ?actionConfig robo:turnRateExplore ?turnRateExplore .
        ?actionConfig robo:turnRateDirect ?turnRateDirect .
        ?actionConfig robo:avoidanceCheckDistance ?avoidanceCheckDistance .
        ?actionConfig robo:collisionBuffer ?collisionBuffer .
        ?actionConfig robo:obstacleBuffer ?obstacleBuffer .
        ?actionConfig robo:avoidanceJitter ?avoidanceJitter .
        ?actionConfig robo:turnAroundJitter ?turnAroundJitter .
        ?actionConfig robo:worldBoundaryMargin ?worldBoundaryMargin .
    }}
    """

    try:
        results = client.twins.query(TWIN_ID, query)
        if results and len(results) > 0:
            r = results[0]

            def get_float(key: str, default: float) -> float:
                val = r.get(key, {}).get('value', default)
                return float(val) if val else default

            def get_int(key: str, default: int) -> int:
                val = r.get(key, {}).get('value', default)
                return int(float(val)) if val else default

            _behavior_config = BehaviorConfig(
                exploration=ExplorationConfig(
                    quadrant_crossing_bonus=get_float('quadrantCrossingBonus', 40.0),
                    same_quadrant_penalty=get_float('sameQuadrantPenalty', 20.0),
                    center_approach_bonus=get_float('centerApproachBonus', 30.0),
                    edge_distance_threshold=get_float('edgeDistanceThreshold', 0.3),
                    unexplored_target_bonus=get_float('unexploredTargetBonus', 25.0),
                    unexplored_path_bonus=get_float('unexploredPathBonus', 10.0),
                    distance_bonus_multiplier=get_float('distanceBonusMultiplier', 0.5),
                    direction_sample_count=get_int('directionSampleCount', 24),
                    venture_distance_factor=get_float('ventureDistanceFactor', 2.5),
                    grid_margin_factor=get_float('gridMarginFactor', 0.1),
                ),
                escape=EscapeConfig(
                    angle_variance=get_float('escapeAngleVariance', 90.0),
                    base_angle_offset=get_float('escapeBaseAngleOffset', 180.0),
                    tick_duration=get_int('escapeTickDuration', 25),
                    min_distance=get_float('escapeMinDistance', 12.0),
                    distance_factor=get_float('escapeDistanceFactor', 3.0),
                    target_reached_distance=get_float('escapeTargetReachedDistance', 2.0),
                    clutter_clear_distance=get_float('escapeClutterClearDistance', 12.0),
                ),
                detection=DetectionConfig(
                    low_battery_threshold=get_float('lowBatteryThreshold', 20.0),
                    battery_drain_rate=get_float('batteryDrainRate', 0.05),
                    at_object_distance=get_float('atObjectDistance', 1.0),
                    near_object_distance=get_float('nearObjectDistance', 3.0),
                    must_avoid_distance=get_float('mustAvoidDistance', 1.5),
                    emergency_avoid_distance=get_float('emergencyAvoidDistance', 0.8),
                    small_coverage_threshold=get_float('smallCoverageThreshold', 15.0),
                    severely_coverage_threshold=get_float('severelyCoverageThreshold', 8.0),
                    high_knottiness_threshold=get_float('highKnottinessThreshold', 9.42),
                    very_high_knottiness_threshold=get_float('veryHighKnottinessThreshold', 18.84),
                    min_positions_for_detection=get_int('minPositionsForDetection', 10),
                    low_unique_cells_ratio=get_float('lowUniqueCellsRatio', 0.4),
                    repeated_visit_threshold=get_int('repeatedVisitThreshold', 3),
                ),
                action=ActionConfig(
                    default_speed=get_float('defaultSpeed', 1.0),
                    turn_rate_explore=get_float('turnRateExplore', 25.0),
                    turn_rate_direct=get_float('turnRateDirect', 90.0),
                    avoidance_check_distance=get_float('avoidanceCheckDistance', 2.0),
                    collision_buffer=get_float('collisionBuffer', 0.3),
                    obstacle_buffer=get_float('obstacleBuffer', 0.5),
                    avoidance_jitter=get_float('avoidanceJitter', 20.0),
                    turn_around_jitter=get_float('turnAroundJitter', 90.0),
                    world_boundary_margin=get_float('worldBoundaryMargin', 3.0),
                ),
            )
            log("[CONFIG] Loaded behavior parameters from ontology")
        else:
            log("[CONFIG] No config in ontology, using defaults")
            _behavior_config = BehaviorConfig()

    except Exception as e:
        log(f"[CONFIG] Failed to load from ontology: {e}, using defaults")
        _behavior_config = BehaviorConfig()

    return _behavior_config


# =============================================================================
# BATCH UPDATE BUILDER - Consolidates SPARQL operations for efficiency
# =============================================================================

@dataclass
class RobotStateUpdate:
    """Captures all state updates for a single robot in a tick."""
    robot_id: str
    position_x: float
    position_y: float
    heading: float
    battery: float
    has_collision: bool
    dist_to_object: float
    dist_to_obstacle: float
    distance_traveled: float
    collision_count: int
    tick_count: int
    success_metric: float
    objects_collected: int
    known_objects: int
    is_exploring: bool
    path_blocked: bool
    obstacle_angle: float
    obstacle_on_left: bool
    obstacle_on_right: bool
    clear_path_angle: float
    is_stuck: bool = False
    ticks_without_movement: int = 0
    escape_heading: float = 0.0
    in_loop: bool = False
    stuck_counter: int = 0
    # Cluster avoidance properties (for ontology-based reasoning)
    nearby_robot_count: int = 0
    ticks_in_cluster: int = 0
    dispersion_heading: float = 0.0
    robot_priority: int = 0  # Higher = disperse sooner


@dataclass
class BatchUpdateBuilder:
    """
    Accumulates all state changes for a simulation tick and executes them
    in a single SPARQL UPDATE operation.

    This dramatically reduces the number of HTTP requests from ~50+ per tick
    to just 1-2 per tick, improving performance by 10-50x.
    """
    robot_states: list[RobotStateUpdate] = field(default_factory=list)
    new_objects: list = field(default_factory=list)  # WorldObject
    new_obstacles: list = field(default_factory=list)  # Obstacle
    collected_objects: list[str] = field(default_factory=list)  # Object IDs

    def add_robot_state(self, state: RobotStateUpdate):
        """Add a robot state update to the batch."""
        self.robot_states.append(state)

    def add_discovered_object(self, obj):
        """Add a newly discovered object."""
        self.new_objects.append(obj)

    def add_discovered_obstacle(self, obs):
        """Add a newly discovered obstacle."""
        self.new_obstacles.append(obs)

    def mark_object_collected(self, obj_id: str):
        """Mark an object as collected."""
        self.collected_objects.append(obj_id)

    def build_sparql_update(self) -> str:
        """Build a single SPARQL UPDATE that applies all accumulated changes."""
        if not self.robot_states and not self.new_objects and not self.new_obstacles and not self.collected_objects:
            return ""

        delete_clauses = []
        insert_clauses = []
        where_patterns = []

        # Build robot state updates
        for i, state in enumerate(self.robot_states):
            robot_uri = f"<urn:robot:{state.robot_id}>"
            var_prefix = f"r{i}"

            # Delete old values
            delete_clauses.append(f"""
    {robot_uri} robo:positionX ?{var_prefix}X .
    {robot_uri} robo:positionY ?{var_prefix}Y .
    {robot_uri} robo:heading ?{var_prefix}H .
    {robot_uri} robo:batteryLevel ?{var_prefix}B .
    {robot_uri} robo:hasCollision ?{var_prefix}C .
    {robot_uri} robo:distanceToNearest ?{var_prefix}DN .
    {robot_uri} robo:distanceToObstacle ?{var_prefix}DO .
    {robot_uri} robo:distanceTraveled ?{var_prefix}DT .
    {robot_uri} robo:collisionCount ?{var_prefix}CC .
    {robot_uri} robo:tickCount ?{var_prefix}TC .
    {robot_uri} robo:successMetric ?{var_prefix}SM .
    {robot_uri} robo:objectsCollected ?{var_prefix}OC .
    {robot_uri} robo:knownObjects ?{var_prefix}KO .
    {robot_uri} robo:isExploring ?{var_prefix}IE .
    {robot_uri} robo:pathBlocked ?{var_prefix}PB .
    {robot_uri} robo:obstacleAngle ?{var_prefix}OA .
    {robot_uri} robo:obstacleOnLeft ?{var_prefix}OL .
    {robot_uri} robo:obstacleOnRight ?{var_prefix}OR .
    {robot_uri} robo:clearPathAngle ?{var_prefix}CPA .
    {robot_uri} robo:isStuck ?{var_prefix}IS .
    {robot_uri} robo:ticksWithoutMovement ?{var_prefix}TW .
    {robot_uri} robo:escapeHeading ?{var_prefix}EH .
    {robot_uri} robo:inLoop ?{var_prefix}IL .
    {robot_uri} robo:stuckCounter ?{var_prefix}SC .
    {robot_uri} robo:nearbyRobotCount ?{var_prefix}NRC .
    {robot_uri} robo:ticksInCluster ?{var_prefix}TIC .
    {robot_uri} robo:dispersionHeading ?{var_prefix}DH .
    {robot_uri} robo:robotPriority ?{var_prefix}RP .""")

            # Insert new values
            insert_clauses.append(f"""
    {robot_uri} robo:positionX "{state.position_x}"^^xsd:float .
    {robot_uri} robo:positionY "{state.position_y}"^^xsd:float .
    {robot_uri} robo:heading "{state.heading}"^^xsd:float .
    {robot_uri} robo:batteryLevel "{state.battery}"^^xsd:float .
    {robot_uri} robo:hasCollision "{str(state.has_collision).lower()}"^^xsd:boolean .
    {robot_uri} robo:distanceToNearest "{state.dist_to_object}"^^xsd:float .
    {robot_uri} robo:distanceToObstacle "{state.dist_to_obstacle}"^^xsd:float .
    {robot_uri} robo:distanceTraveled "{state.distance_traveled}"^^xsd:float .
    {robot_uri} robo:collisionCount "{state.collision_count}"^^xsd:integer .
    {robot_uri} robo:tickCount "{state.tick_count}"^^xsd:integer .
    {robot_uri} robo:successMetric "{state.success_metric}"^^xsd:float .
    {robot_uri} robo:objectsCollected "{state.objects_collected}"^^xsd:integer .
    {robot_uri} robo:knownObjects "{state.known_objects}"^^xsd:integer .
    {robot_uri} robo:isExploring "{str(state.is_exploring).lower()}"^^xsd:boolean .
    {robot_uri} robo:pathBlocked "{str(state.path_blocked).lower()}"^^xsd:boolean .
    {robot_uri} robo:obstacleAngle "{state.obstacle_angle}"^^xsd:float .
    {robot_uri} robo:obstacleOnLeft "{str(state.obstacle_on_left).lower()}"^^xsd:boolean .
    {robot_uri} robo:obstacleOnRight "{str(state.obstacle_on_right).lower()}"^^xsd:boolean .
    {robot_uri} robo:clearPathAngle "{state.clear_path_angle}"^^xsd:float .
    {robot_uri} robo:isStuck "{str(state.is_stuck).lower()}"^^xsd:boolean .
    {robot_uri} robo:ticksWithoutMovement "{state.ticks_without_movement}"^^xsd:integer .
    {robot_uri} robo:escapeHeading "{state.escape_heading}"^^xsd:float .
    {robot_uri} robo:inLoop "{str(state.in_loop).lower()}"^^xsd:boolean .
    {robot_uri} robo:stuckCounter "{state.stuck_counter}"^^xsd:integer .
    {robot_uri} robo:nearbyRobotCount "{state.nearby_robot_count}"^^xsd:integer .
    {robot_uri} robo:ticksInCluster "{state.ticks_in_cluster}"^^xsd:integer .
    {robot_uri} robo:dispersionHeading "{state.dispersion_heading}"^^xsd:float .
    {robot_uri} robo:robotPriority "{state.robot_priority}"^^xsd:integer .""")

            # Where clause with OPTIONAL bindings
            where_patterns.append(f"""
    OPTIONAL {{ {robot_uri} robo:positionX ?{var_prefix}X }}
    OPTIONAL {{ {robot_uri} robo:positionY ?{var_prefix}Y }}
    OPTIONAL {{ {robot_uri} robo:heading ?{var_prefix}H }}
    OPTIONAL {{ {robot_uri} robo:batteryLevel ?{var_prefix}B }}
    OPTIONAL {{ {robot_uri} robo:hasCollision ?{var_prefix}C }}
    OPTIONAL {{ {robot_uri} robo:distanceToNearest ?{var_prefix}DN }}
    OPTIONAL {{ {robot_uri} robo:distanceToObstacle ?{var_prefix}DO }}
    OPTIONAL {{ {robot_uri} robo:distanceTraveled ?{var_prefix}DT }}
    OPTIONAL {{ {robot_uri} robo:collisionCount ?{var_prefix}CC }}
    OPTIONAL {{ {robot_uri} robo:tickCount ?{var_prefix}TC }}
    OPTIONAL {{ {robot_uri} robo:successMetric ?{var_prefix}SM }}
    OPTIONAL {{ {robot_uri} robo:objectsCollected ?{var_prefix}OC }}
    OPTIONAL {{ {robot_uri} robo:knownObjects ?{var_prefix}KO }}
    OPTIONAL {{ {robot_uri} robo:isExploring ?{var_prefix}IE }}
    OPTIONAL {{ {robot_uri} robo:pathBlocked ?{var_prefix}PB }}
    OPTIONAL {{ {robot_uri} robo:obstacleAngle ?{var_prefix}OA }}
    OPTIONAL {{ {robot_uri} robo:obstacleOnLeft ?{var_prefix}OL }}
    OPTIONAL {{ {robot_uri} robo:obstacleOnRight ?{var_prefix}OR }}
    OPTIONAL {{ {robot_uri} robo:clearPathAngle ?{var_prefix}CPA }}
    OPTIONAL {{ {robot_uri} robo:isStuck ?{var_prefix}IS }}
    OPTIONAL {{ {robot_uri} robo:ticksWithoutMovement ?{var_prefix}TW }}
    OPTIONAL {{ {robot_uri} robo:escapeHeading ?{var_prefix}EH }}
    OPTIONAL {{ {robot_uri} robo:inLoop ?{var_prefix}IL }}
    OPTIONAL {{ {robot_uri} robo:stuckCounter ?{var_prefix}SC }}
    OPTIONAL {{ {robot_uri} robo:nearbyRobotCount ?{var_prefix}NRC }}
    OPTIONAL {{ {robot_uri} robo:ticksInCluster ?{var_prefix}TIC }}
    OPTIONAL {{ {robot_uri} robo:dispersionHeading ?{var_prefix}DH }}
    OPTIONAL {{ {robot_uri} robo:robotPriority ?{var_prefix}RP }}""")

        # Add newly discovered objects
        for obj in self.new_objects:
            insert_clauses.append(f"""
    <urn:object:{obj.id}> a robo:CollectibleObject, robo:DiscoveredObject ;
        robo:positionX "{obj.position.x}"^^xsd:float ;
        robo:positionY "{obj.position.y}"^^xsd:float ;
        robo:objectValue "{obj.value}"^^xsd:float ;
        robo:isCollected "false"^^xsd:boolean .""")

        # Add newly discovered obstacles
        for obs in self.new_obstacles:
            insert_clauses.append(f"""
    <urn:obstacle:{obs.id}> a robo:Obstacle, robo:DiscoveredObstacle ;
        robo:positionX "{obs.position.x}"^^xsd:float ;
        robo:positionY "{obs.position.y}"^^xsd:float .""")

        # Mark objects as collected
        for obj_id in self.collected_objects:
            delete_clauses.append(f"""
    <urn:object:{obj_id}> robo:isCollected ?col_{obj_id.replace('-', '_')} .""")
            insert_clauses.append(f"""
    <urn:object:{obj_id}> robo:isCollected "true"^^xsd:boolean .""")
            where_patterns.append(f"""
    OPTIONAL {{ <urn:object:{obj_id}> robo:isCollected ?col_{obj_id.replace('-', '_')} }}""")

        # Build final query
        query = f"""
PREFIX robo: <{ROBO}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

DELETE {{
{"".join(delete_clauses)}
}}
INSERT {{
{"".join(insert_clauses)}
}}
WHERE {{
{"".join(where_patterns)}
}}
"""
        return query

    def execute(self, client: DTaaSClient) -> bool:
        """Execute the batch update using the twin-specific SPARQL update endpoint."""
        query = self.build_sparql_update()
        if not query:
            return True

        try:
            # Use twin-specific update to operate on the twin's named graph
            client.twins.sparql_update(TWIN_ID, query)
            return True
        except DTaaSError as e:
            log(f"[BATCH] Error executing batch update: {e}")
            return False

    def clear(self):
        """Clear all accumulated updates."""
        self.robot_states.clear()
        self.new_objects.clear()
        self.new_obstacles.clear()
        self.collected_objects.clear()


# Quiet mode for animation - suppresses logs during simulation
QUIET_MODE = False
LOG_FILE = None

# Store original log levels to restore later
_original_log_levels = {}


def enable_quiet_mode():
    """Enable quiet mode - suppress all logging including HTTP client."""
    global QUIET_MODE, _original_log_levels
    QUIET_MODE = True

    # Suppress HTTP client logging (httpx, urllib3, httpcore)
    for logger_name in ['httpx', 'httpcore', 'urllib3', 'requests', 'http.client']:
        logger = logging.getLogger(logger_name)
        _original_log_levels[logger_name] = logger.level
        logger.setLevel(logging.CRITICAL)


def disable_quiet_mode():
    """Disable quiet mode - restore all logging."""
    global QUIET_MODE, _original_log_levels
    QUIET_MODE = False

    # Restore original log levels
    for logger_name, level in _original_log_levels.items():
        logging.getLogger(logger_name).setLevel(level)
    _original_log_levels.clear()


def log(msg: str):
    """Print log message unless in quiet mode. If log file set, write there instead."""
    global LOG_FILE
    if QUIET_MODE:
        if LOG_FILE:
            LOG_FILE.write(msg + "\n")
        return
    print(msg)


# =============================================================================
# SIMULATION WORLD
# =============================================================================

@dataclass
class Position:
    """2D position in the world."""
    x: float
    y: float

    def distance_to(self, other: "Position") -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def __repr__(self):
        return f"({self.x:.1f}, {self.y:.1f})"


@dataclass
class WorldObject:
    """An object in the simulation world."""
    id: str
    position: Position
    value: float
    collected: bool = False
    collected_by: Optional[str] = None  # Robot ID that collected this object


@dataclass
class Obstacle:
    """An obstacle in the simulation world."""
    id: str
    position: Position
    radius: float = 0.5


@dataclass
class Robot:
    """The robot agent in a multi-robot simulation."""
    id: str
    position: Position
    heading: float = 0.0  # degrees
    speed: float = 1.0
    battery: float = 100.0
    battery_capacity: float = 100.0  # Configurable battery capacity
    sensor_range: float = 5.0  # How far the robot can see
    collision_radius: float = 0.3

    # Multi-robot identification
    robot_index: int = 0  # 0-based index for this robot
    symbol: str = "R"  # Display symbol (R, B, G, Y, etc.)
    color_name: str = "red"  # Color name for display

    # Metrics
    success_metric: float = 0.0
    objects_collected: int = 0
    distance_traveled: float = 0.0
    collision_count: int = 0
    robot_collision_count: int = 0  # Collisions with other robots
    tick_count: int = 0

    # State
    has_collision: bool = False
    has_robot_collision: bool = False  # Collision with another robot
    is_active: bool = True
    current_action: str = "Idle"

    # Exploration state
    exploration_heading: float = 0.0  # Direction for exploration when no targets visible

    # Stuck detection - track actual movement
    last_position_x: float = 0.0
    last_position_y: float = 0.0
    ticks_without_movement: int = 0
    is_stuck: bool = False
    escape_heading: Optional[float] = None  # Direction to try when escaping

    # Discovery tracking - for exploration incentives
    ticks_since_discovery: int = 0  # Ticks since last object/obstacle discovery
    ticks_since_collection: int = 0  # Ticks since last object collection
    wanderlust: float = 0.0  # Increases when not finding anything, triggers venture-out
    venture_heading: Optional[float] = None  # Direction for venturing to new areas

    # Cluster avoidance - prevents robots from clumping together
    ticks_in_cluster: int = 0  # How long robot has been in a cluster
    dispersion_heading: Optional[float] = None  # Direction to escape cluster

    def reset_discovery_timer(self):
        """Reset discovery timer when something new is found."""
        self.ticks_since_discovery = 0
        self.wanderlust = 0.0
        self.venture_heading = None

    def reset_collection_timer(self):
        """Reset collection timer when object is collected."""
        self.ticks_since_collection = 0

    def update_wanderlust(self, world_width: float, world_height: float):
        """Update wanderlust factor based on discovery and collection rates."""
        self.ticks_since_discovery += 1
        self.ticks_since_collection += 1

        # Wanderlust increases faster on larger grids
        grid_factor = (world_width * world_height) / 400  # Normalized to 20x20
        discovery_factor = min(self.ticks_since_discovery / 20, 5.0)  # Max 5x
        collection_factor = min(self.ticks_since_collection / 30, 3.0)  # Max 3x

        self.wanderlust = (discovery_factor + collection_factor) * math.sqrt(grid_factor)

    def needs_venture_out(self) -> bool:
        """Check if robot should venture to completely new area."""
        return self.wanderlust > 3.0 or self.ticks_since_discovery > 25

    def get_venture_direction(self, current_pos_x: float, current_pos_y: float,
                               world_width: float, world_height: float,
                               explored_positions: set) -> float:
        """Get direction to venture toward unexplored regions of the grid.

        All scoring parameters are loaded from ontology via get_behavior_config().
        This enables language-agnostic behavior - same parameters work in Python, TypeScript, etc.
        """
        import random

        # Recalculate venture heading periodically or if we've been going same direction too long
        if (self.venture_heading is None or
            self.ticks_since_discovery % 15 == 0 or  # Recalculate every 15 ticks
            self.ticks_since_discovery > 40):
            pass  # Will calculate new heading below
        else:
            return self.venture_heading

        # Get exploration parameters from ontology config
        cfg = get_behavior_config().exploration

        # Calculate center of grid
        center_x, center_y = world_width / 2, world_height / 2

        # Check which quadrant robot is in and prefer heading toward opposite quadrant
        in_left = current_pos_x < center_x
        in_bottom = current_pos_y < center_y

        # Sample directions and find the best one
        best_direction = random.uniform(0, 360)
        best_score = -float('inf')

        # Sample count from ontology
        for _ in range(cfg.direction_sample_count):
            angle = random.uniform(0, 360)
            angle_rad = math.radians(angle)

            # Project far into that direction (factor from ontology)
            venture_dist = max(world_width, world_height) / cfg.venture_distance_factor
            target_x = current_pos_x + math.cos(angle_rad) * venture_dist
            target_y = current_pos_y + math.sin(angle_rad) * venture_dist

            # Clamp to grid bounds with margin (from ontology)
            margin = min(world_width, world_height) * cfg.grid_margin_factor
            target_x = max(margin, min(world_width - margin, target_x))
            target_y = max(margin, min(world_height - margin, target_y))

            score = 0

            # Quadrant crossing bonus (from ontology)
            target_in_left = target_x < center_x
            target_in_bottom = target_y < center_y
            if target_in_left != in_left:
                score += cfg.quadrant_crossing_bonus
            if target_in_bottom != in_bottom:
                score += cfg.quadrant_crossing_bonus

            # Center approach bonus when at edges (from ontology)
            dist_to_center_now = math.sqrt((current_pos_x - center_x)**2 + (current_pos_y - center_y)**2)
            dist_to_center_target = math.sqrt((target_x - center_x)**2 + (target_y - center_y)**2)
            if dist_to_center_now > min(world_width, world_height) * cfg.edge_distance_threshold:
                if dist_to_center_target < dist_to_center_now:
                    score += cfg.center_approach_bonus

            # Unexplored target bonus (from ontology)
            target_cell = (round(target_x), round(target_y))
            if target_cell not in explored_positions:
                score += cfg.unexplored_target_bonus

            # Path exploration bonus (from ontology)
            path_explored = 0
            for t in [0.25, 0.5, 0.75]:
                check_x = current_pos_x + (target_x - current_pos_x) * t
                check_y = current_pos_y + (target_y - current_pos_y) * t
                if (round(check_x), round(check_y)) in explored_positions:
                    path_explored += 1
            score += (3 - path_explored) * cfg.unexplored_path_bonus

            # Distance bonus (from ontology)
            dist = math.sqrt((target_x - current_pos_x)**2 + (target_y - current_pos_y)**2)
            score += dist * cfg.distance_bonus_multiplier

            # Same quadrant penalty (from ontology)
            if target_in_left == in_left and target_in_bottom == in_bottom:
                score -= cfg.same_quadrant_penalty

            if score > best_score:
                best_score = score
                best_direction = math.degrees(math.atan2(target_y - current_pos_y,
                                                          target_x - current_pos_x))

        self.venture_heading = best_direction
        return best_direction

    def update_stuck_state(self, movement_threshold: float = 0.3):
        """Update stuck detection based on actual movement."""
        dist_moved = math.sqrt(
            (self.position.x - self.last_position_x) ** 2 +
            (self.position.y - self.last_position_y) ** 2
        )

        if dist_moved < movement_threshold:
            self.ticks_without_movement += 1
        else:
            self.ticks_without_movement = 0
            self.is_stuck = False
            self.escape_heading = None

        # Consider stuck after 3 ticks without movement
        if self.ticks_without_movement >= 3:
            self.is_stuck = True

        # Update last position
        self.last_position_x = self.position.x
        self.last_position_y = self.position.y

    def get_escape_direction(self, current_heading: float) -> float:
        """Get a direction to escape when stuck. Tries progressively different angles."""
        import random

        if self.escape_heading is None or self.ticks_without_movement % 3 == 0:
            # Try a new escape direction every 3 stuck ticks
            # Use a combination of opposite direction and randomness
            base_angle = (current_heading + 180) % 360  # Opposite direction
            randomness = random.uniform(-90, 90)  # Add randomness
            self.escape_heading = (base_angle + randomness) % 360

        return self.escape_heading


# =============================================================================
# PHEROMONE SYSTEM - Ant-inspired stigmergic communication
# =============================================================================

class PheromoneType:
    """Types of pheromones robots can deposit."""
    EXPLORATION = "exploration"  # "I've been here" - avoid redundant exploration
    OBJECT_FOUND = "object_found"  # "Object found nearby!" - attracts to fruitful areas
    OBJECT_COLLECTED = "object_collected"  # "Object collected here" - no need to come
    DANGER = "danger"  # "Collision/obstacle here" - warning signal


@dataclass
class Pheromone:
    """
    A pheromone marker left by a robot in the environment.

    Inspired by ant colony behavior:
    - Robots deposit pheromones as they move
    - Pheromones decay over time (evaporation)
    - Other robots can sense nearby pheromones within sensor range
    - Different types convey different information
    """
    id: str
    position: Position
    pheromone_type: str  # PheromoneType value
    strength: float  # 0.0 to 1.0, decays over time
    deposited_by: str  # Robot ID that left this pheromone
    tick_deposited: int  # When it was deposited

    # Decay rate per tick (default: loses 5% strength per tick)
    decay_rate: float = 0.05

    def decay(self, current_tick: int) -> float:
        """Calculate current strength after decay. Returns new strength."""
        ticks_elapsed = current_tick - self.tick_deposited
        self.strength = max(0.0, 1.0 - (self.decay_rate * ticks_elapsed))
        return self.strength

    def is_expired(self) -> bool:
        """Check if pheromone has fully decayed."""
        return self.strength <= 0.0


# Pheromone configuration
PHEROMONE_CONFIG = {
    PheromoneType.EXPLORATION: {
        "decay_rate": 0.03,  # Slow decay - exploration trails last longer
        "deposit_interval": 2,  # Deposit every N ticks while moving
        "initial_strength": 0.8,
    },
    PheromoneType.OBJECT_FOUND: {
        "decay_rate": 0.02,  # Very slow decay - object locations are valuable
        "deposit_interval": 1,
        "initial_strength": 1.0,
    },
    PheromoneType.OBJECT_COLLECTED: {
        "decay_rate": 0.04,
        "deposit_interval": 1,
        "initial_strength": 1.0,
    },
    PheromoneType.DANGER: {
        "decay_rate": 0.05,  # Medium decay
        "deposit_interval": 1,
        "initial_strength": 1.0,
    },
}


# Robot symbols and colors for multi-robot display
ROBOT_CONFIGS = [
    {"symbol": "R", "color": "red", "start_corner": "SW"},
    {"symbol": "B", "color": "blue", "start_corner": "NE"},
    {"symbol": "G", "color": "green", "start_corner": "NW"},
    {"symbol": "Y", "color": "yellow", "start_corner": "SE"},
    {"symbol": "P", "color": "purple", "start_corner": "center"},
    {"symbol": "C", "color": "cyan", "start_corner": "center"},
]


@dataclass
class KnownWorld:
    """
    Tracks what the robot has discovered about the world.

    This is the robot's internal model - it only knows what it has sensed.
    The actual world dimensions are NOT known until borders are discovered.
    """
    # Discovered entities
    discovered_objects: dict  # id -> WorldObject
    discovered_obstacles: dict  # id -> Obstacle

    # Discovered borders (None = unknown)
    known_min_x: Optional[float] = None
    known_max_x: Optional[float] = None
    known_min_y: Optional[float] = None
    known_max_y: Optional[float] = None

    # Exploration history to avoid revisiting
    explored_positions: list = None  # List of (x, y) positions visited

    # Loop detection - track recent positions
    recent_positions: list = None  # Circular buffer of recent (x, y) cells
    loop_detected: bool = False
    stuck_counter: int = 0
    coverage_area: float = 0.0  # Convex hull area of recent positions
    path_knottiness: float = 0.0  # Total angular change (curvature metric)
    # Escape mode - persists across ticks until target reached
    escape_mode: bool = False
    escape_target: tuple = None  # (x, y) target to escape to
    escape_ticks_remaining: int = 0
    clutter_centroid: tuple = None  # Center of the clutter we're escaping from

    def __post_init__(self):
        if self.explored_positions is None:
            self.explored_positions = []
        if self.recent_positions is None:
            self.recent_positions = []

    def has_discovered_object(self, obj_id: str) -> bool:
        return obj_id in self.discovered_objects

    def has_discovered_obstacle(self, obs_id: str) -> bool:
        return obs_id in self.discovered_obstacles

    def get_uncollected_known_objects(self) -> list[WorldObject]:
        """Get objects that are discovered and not yet collected."""
        return [o for o in self.discovered_objects.values() if not o.collected]

    def get_nearest_known_object(self, from_pos: Position) -> Optional[WorldObject]:
        """Get nearest uncollected discovered object."""
        uncollected = self.get_uncollected_known_objects()
        if not uncollected:
            return None
        return min(uncollected, key=lambda o: from_pos.distance_to(o.position))

    def get_second_nearest_object(self, from_pos: Position, exclude: WorldObject = None) -> Optional[WorldObject]:
        """Get second nearest uncollected discovered object (for target deconfliction)."""
        uncollected = self.get_uncollected_known_objects()
        if exclude:
            uncollected = [o for o in uncollected if o.id != exclude.id]
        if not uncollected:
            return None
        return min(uncollected, key=lambda o: from_pos.distance_to(o.position))

    def get_nearest_known_obstacle(self, from_pos: Position) -> Optional[Obstacle]:
        """Get nearest discovered obstacle."""
        if not self.discovered_obstacles:
            return None
        return min(self.discovered_obstacles.values(),
                   key=lambda o: from_pos.distance_to(o.position))

    def is_border_known(self, direction: str) -> bool:
        """Check if a border in a direction is known."""
        if direction == "north":
            return self.known_max_y is not None
        elif direction == "south":
            return self.known_min_y is not None
        elif direction == "east":
            return self.known_max_x is not None
        elif direction == "west":
            return self.known_min_x is not None
        return False

    def record_exploration(self, pos: Position):
        """Record that a position has been explored and check for loops."""
        # Round to grid cells to avoid too many entries
        cell = (round(pos.x), round(pos.y))
        if cell not in self.explored_positions:
            self.explored_positions.append(cell)

        # Track recent positions for loop detection (keep last 30 positions)
        self.recent_positions.append(cell)
        if len(self.recent_positions) > 30:
            self.recent_positions.pop(0)

        # Detect loops - if we've visited the same cell multiple times recently
        self._check_for_loop()

    def _calculate_convex_hull_area(self, points: list) -> float:
        """Calculate convex hull area using Graham scan + Shoelace formula."""
        if len(points) < 3:
            return 0.0

        # Get unique points
        unique_points = list(set(points))
        if len(unique_points) < 3:
            return 0.0

        # Find convex hull using Graham scan
        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        pts = sorted(unique_points)
        if len(pts) <= 1:
            return 0.0

        # Build lower hull
        lower = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        # Build upper hull
        upper = []
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        hull = lower[:-1] + upper[:-1]
        if len(hull) < 3:
            return 0.0

        # Shoelace formula for area
        n = len(hull)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += hull[i][0] * hull[j][1]
            area -= hull[j][0] * hull[i][1]
        return abs(area) / 2.0

    def _calculate_path_knottiness(self, positions: list) -> float:
        """Calculate total angular change (curvature) of the path."""
        if len(positions) < 3:
            return 0.0

        total_angle_change = 0.0
        for i in range(1, len(positions) - 1):
            p0, p1, p2 = positions[i-1], positions[i], positions[i+1]

            # Vector from p0 to p1
            v1x, v1y = p1[0] - p0[0], p1[1] - p0[1]
            # Vector from p1 to p2
            v2x, v2y = p2[0] - p1[0], p2[1] - p1[1]

            # Calculate angle between vectors
            len1 = math.sqrt(v1x*v1x + v1y*v1y)
            len2 = math.sqrt(v2x*v2x + v2y*v2y)

            if len1 > 0.01 and len2 > 0.01:
                dot = v1x*v2x + v1y*v2y
                cos_angle = max(-1, min(1, dot / (len1 * len2)))
                angle = math.acos(cos_angle)
                total_angle_change += angle

        return total_angle_change

    def _check_for_loop(self):
        """Detect if robot is stuck in a loop by analyzing recent positions."""
        if len(self.recent_positions) < 15:
            self.loop_detected = False
            self.coverage_area = 0.0
            self.path_knottiness = 0.0
            return

        # Calculate coverage area (convex hull of recent positions)
        self.coverage_area = self._calculate_convex_hull_area(self.recent_positions[-20:])

        # Calculate path knottiness (total curvature)
        self.path_knottiness = self._calculate_path_knottiness(self.recent_positions[-20:])

        # Count how many times each cell appears in recent history
        from collections import Counter
        cell_counts = Counter(self.recent_positions)
        max_visits = max(cell_counts.values())

        # Detect loop based on multiple criteria:
        # 1. Repeated cell visits (original method)
        # 2. Very small coverage area (circling in tight space)
        # 3. High knottiness with small area (lots of turning in small space)

        small_area = self.coverage_area < 12  # Less than ~12 square cells
        high_knottiness = self.path_knottiness > math.pi * 4  # More than 720 degrees of turning
        repeated_visits = max_visits >= 3

        if repeated_visits or (small_area and len(self.recent_positions) >= 20):
            self.loop_detected = True
            self.stuck_counter += 1
        elif small_area and high_knottiness:
            # Lots of turning in a small area = probably stuck
            self.loop_detected = True
            self.stuck_counter += 1
        else:
            self.loop_detected = False
            self.stuck_counter = max(0, self.stuck_counter - 1)

    def get_least_visited_direction(self, from_pos: Position, directions: list[float]) -> float:
        """Get the direction that leads to least visited areas."""
        best_direction = directions[0] if directions else 0
        best_score = float('inf')

        for angle in directions:
            angle_rad = math.radians(angle)
            # Check cells in this direction
            visit_count = 0
            for dist in [2, 4, 6, 8]:
                check_x = round(from_pos.x + math.cos(angle_rad) * dist)
                check_y = round(from_pos.y + math.sin(angle_rad) * dist)
                check_cell = (check_x, check_y)
                # Count visits in recent history
                visit_count += self.recent_positions.count(check_cell)
                # Also penalize explored cells slightly
                if check_cell in self.explored_positions:
                    visit_count += 0.5

            if visit_count < best_score:
                best_score = visit_count
                best_direction = angle

        return best_direction

    def clear_loop_state(self):
        """Clear loop detection state (call when discovering new object)."""
        self.loop_detected = False
        self.stuck_counter = 0
        self.recent_positions = []


class SimulationWorld:
    """The simulated 2D world with multiple competing robots.

    The world has actual dimensions, but robots don't know them.
    Each robot only discovers the world through its own sensors.
    Robots compete to collect objects and can collide with each other.
    """

    def __init__(self, width: int = 20, height: int = 20, num_robots: int = 1,
                 battery_capacity: float = 100.0):
        # Actual world dimensions (unknown to robots)
        self._width = width
        self._height = height
        self._num_robots = num_robots
        self._battery_capacity = battery_capacity

        # Create robots at different starting positions
        self.robots: list[Robot] = []
        self.known_worlds: dict[str, KnownWorld] = {}  # robot_id -> KnownWorld
        self.home_positions: dict[str, Position] = {}  # robot_id -> home position

        for i in range(num_robots):
            config = ROBOT_CONFIGS[i % len(ROBOT_CONFIGS)]
            start_pos = self._get_start_position(config["start_corner"], i)

            robot = Robot(
                id=f"robot{i+1}",
                position=start_pos,
                robot_index=i,
                symbol=config["symbol"],
                color_name=config["color"],
                battery=battery_capacity,
                battery_capacity=battery_capacity
            )
            self.robots.append(robot)

            # Each robot has its own knowledge model
            self.known_worlds[robot.id] = KnownWorld(
                discovered_objects={},
                discovered_obstacles={}
            )
            self.home_positions[robot.id] = Position(start_pos.x, start_pos.y)

        # For backward compatibility - primary robot reference
        self.robot = self.robots[0] if self.robots else None
        self.known_world = self.known_worlds.get("robot1") if self.robots else None
        self.home_position = self.home_positions.get("robot1") if self.robots else Position(width/2, height/2)

        self.objects: list[WorldObject] = []
        self.obstacles: list[Obstacle] = []

        # Track total objects for completion check
        self._total_objects_in_world = 0

        # Competition tracking
        self.winner: Optional[Robot] = None
        self.game_over: bool = False
        self.game_over_reason: str = ""

        # Pheromone system - shared environment markers
        self.pheromones: list[Pheromone] = []
        self._pheromone_counter: int = 0
        self.current_tick: int = 0

    def _get_start_position(self, corner: str, robot_index: int) -> Position:
        """Get starting position based on corner assignment."""
        margin = 2.0
        if corner == "SW":
            return Position(margin, margin)
        elif corner == "NE":
            return Position(self._width - margin, self._height - margin)
        elif corner == "NW":
            return Position(margin, self._height - margin)
        elif corner == "SE":
            return Position(self._width - margin, margin)
        else:  # center with slight offset
            offset = robot_index * 1.5
            return Position(self._width / 2 + offset, self._height / 2 + offset)

    def get_robot_by_id(self, robot_id: str) -> Optional[Robot]:
        """Get robot by ID."""
        for r in self.robots:
            if r.id == robot_id:
                return r
        return None

    def get_known_world(self, robot_id: str) -> Optional[KnownWorld]:
        """Get a robot's known world."""
        return self.known_worlds.get(robot_id)

    def get_active_robots(self) -> list[Robot]:
        """Get list of robots that are still active."""
        return [r for r in self.robots if r.is_active]

    def get_rankings(self) -> list[Robot]:
        """Get robots sorted by performance (best first).

        Ranking criteria (in order):
        1. Objects collected (higher is better)
        2. Success metric (higher is better)
        3. Fewer obstacle collisions
        4. Fewer robot collisions
        5. Less distance traveled (more efficient)
        """
        return sorted(self.robots, key=lambda r: (
            -r.objects_collected,
            -r.success_metric,
            r.collision_count,
            r.robot_collision_count,
            r.distance_traveled
        ))

    def determine_winner(self) -> Optional[Robot]:
        """Determine the winner of the competition.

        A winner is determined when:
        - All objects are collected
        - All robots are inactive
        - Max ticks reached

        Returns the robot with best performance.
        """
        if not self.robots:
            return None
        rankings = self.get_rankings()
        return rankings[0] if rankings else None

    def check_game_over(self) -> tuple[bool, str]:
        """Check if the game/competition is over.

        Returns (is_over, reason).
        """
        # All objects collected
        if not self.get_uncollected_objects():
            return True, "All objects collected"

        # All robots inactive
        if not self.get_active_robots():
            return True, "All robots inactive"

        return False, ""

    # =========================================================================
    # PHEROMONE METHODS - Stigmergic communication
    # =========================================================================

    def deposit_pheromone(self, robot: Robot, pheromone_type: str, position: Position = None):
        """
        Deposit a pheromone at the robot's current position.

        Pheromones are shared environment markers that any robot can sense
        within their sensor range.
        """
        if position is None:
            position = Position(robot.position.x, robot.position.y)

        config = PHEROMONE_CONFIG.get(pheromone_type, {})
        self._pheromone_counter += 1

        pheromone = Pheromone(
            id=f"pheromone_{self._pheromone_counter}",
            position=position,
            pheromone_type=pheromone_type,
            strength=config.get("initial_strength", 1.0),
            deposited_by=robot.id,
            tick_deposited=self.current_tick,
            decay_rate=config.get("decay_rate", 0.05)
        )
        self.pheromones.append(pheromone)

    def decay_pheromones(self):
        """Update pheromone strengths based on decay and remove expired ones."""
        for pheromone in self.pheromones:
            pheromone.decay(self.current_tick)

        # Remove expired pheromones
        self.pheromones = [p for p in self.pheromones if not p.is_expired()]

    def sense_pheromones(self, robot: Robot) -> dict:
        """
        Sense pheromones within the robot's sensor range.

        Returns a dict with pheromones grouped by type.
        Robots can sense pheromones from ANY robot (including themselves).
        """
        sensor_range = robot.sensor_range
        nearby_pheromones = {
            PheromoneType.EXPLORATION: [],
            PheromoneType.OBJECT_FOUND: [],
            PheromoneType.OBJECT_COLLECTED: [],
            PheromoneType.DANGER: [],
        }

        for pheromone in self.pheromones:
            dist = robot.position.distance_to(pheromone.position)
            if dist <= sensor_range:
                if pheromone.pheromone_type in nearby_pheromones:
                    nearby_pheromones[pheromone.pheromone_type].append(pheromone)

        return nearby_pheromones

    def get_strongest_pheromone_direction(self, robot: Robot, pheromone_type: str) -> Optional[float]:
        """
        Get the direction toward the strongest pheromone of a given type.

        Returns heading in degrees, or None if no pheromones of that type are sensed.
        """
        nearby = self.sense_pheromones(robot)
        pheromones_of_type = nearby.get(pheromone_type, [])

        if not pheromones_of_type:
            return None

        # Find the strongest pheromone
        strongest = max(pheromones_of_type, key=lambda p: p.strength)

        # Calculate heading toward it
        dx = strongest.position.x - robot.position.x
        dy = strongest.position.y - robot.position.y
        heading = math.degrees(math.atan2(dy, dx))

        return heading

    def get_pheromone_gradient(self, robot: Robot, pheromone_type: str) -> Optional[float]:
        """
        Calculate the gradient direction for a pheromone type.

        This uses weighted average of all nearby pheromones to find the
        direction of increasing pheromone concentration (like ants follow).
        Returns heading in degrees, or None if no pheromones sensed.
        """
        nearby = self.sense_pheromones(robot)
        pheromones_of_type = nearby.get(pheromone_type, [])

        if not pheromones_of_type:
            return None

        # Calculate weighted centroid of pheromones (stronger = more weight)
        total_weight = 0.0
        weighted_x = 0.0
        weighted_y = 0.0

        for p in pheromones_of_type:
            weighted_x += p.position.x * p.strength
            weighted_y += p.position.y * p.strength
            total_weight += p.strength

        if total_weight < 0.01:
            return None

        centroid_x = weighted_x / total_weight
        centroid_y = weighted_y / total_weight

        # Direction toward the centroid
        dx = centroid_x - robot.position.x
        dy = centroid_y - robot.position.y

        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return None

        return math.degrees(math.atan2(dy, dx))

    def has_exploration_pheromone_at(self, position: Position, threshold: float = 0.3) -> bool:
        """Check if there's a strong exploration pheromone at a position."""
        for p in self.pheromones:
            if p.pheromone_type == PheromoneType.EXPLORATION:
                if p.position.distance_to(position) < 1.0 and p.strength >= threshold:
                    return True
        return False

    @property
    def width(self):
        """Actual world width (for simulation/visualization only, not for robot logic)."""
        return self._width

    @property
    def height(self):
        """Actual world height (for simulation/visualization only, not for robot logic)."""
        return self._height

    def add_object(self, obj: WorldObject):
        self.objects.append(obj)
        self._total_objects_in_world += 1

    def add_obstacle(self, obs: Obstacle):
        self.obstacles.append(obs)

    # =========================================================================
    # SENSOR METHODS - What a robot can perceive
    # =========================================================================

    def sense_environment(self, robot: Robot = None) -> dict:
        """
        Sense the environment within sensor range and discover new entities.

        This is the PRIMARY way a robot learns about the world.
        Each robot has its own KnownWorld.
        Returns information about newly discovered entities.
        """
        if robot is None:
            robot = self.robot  # Backward compatibility
        known = self.known_worlds[robot.id]
        sensor_range = robot.sensor_range
        discoveries = {
            "new_objects": [],
            "new_obstacles": [],
            "new_robots": [],  # Other robots spotted
            "borders_discovered": []
        }

        # Discover objects within sensor range
        for obj in self.objects:
            if obj.collected:
                continue
            dist = robot.position.distance_to(obj.position)
            if dist <= sensor_range and not known.has_discovered_object(obj.id):
                known.discovered_objects[obj.id] = obj
                discoveries["new_objects"].append(obj)

        # If we discovered new objects, clear loop state - we have new goals!
        if discoveries["new_objects"]:
            known.clear_loop_state()
            robot.reset_discovery_timer()  # Found something! Reset wanderlust
            # Deposit OBJECT_FOUND pheromone - tells others "objects nearby!"
            for obj in discoveries["new_objects"]:
                self.deposit_pheromone(robot, PheromoneType.OBJECT_FOUND, obj.position)

        # Discover obstacles within sensor range
        for obs in self.obstacles:
            dist = robot.position.distance_to(obs.position)
            if dist <= sensor_range and not known.has_discovered_obstacle(obs.id):
                known.discovered_obstacles[obs.id] = obs
                discoveries["new_obstacles"].append(obs)
                robot.reset_discovery_timer()  # Found something! Reset wanderlust

        # Discover other robots within sensor range
        for other_robot in self.robots:
            if other_robot.id == robot.id:
                continue
            dist = robot.position.distance_to(other_robot.position)
            if dist <= sensor_range:
                discoveries["new_robots"].append(other_robot)

        # Discover borders if within sensor range of them
        if robot.position.x <= sensor_range and known.known_min_x is None:
            known.known_min_x = 0
            discoveries["borders_discovered"].append("west")

        if robot.position.x >= self._width - sensor_range and known.known_max_x is None:
            known.known_max_x = self._width
            discoveries["borders_discovered"].append("east")

        if robot.position.y <= sensor_range and known.known_min_y is None:
            known.known_min_y = 0
            discoveries["borders_discovered"].append("south")

        if robot.position.y >= self._height - sensor_range and known.known_max_y is None:
            known.known_max_y = self._height
            discoveries["borders_discovered"].append("north")

        # Record current position as explored
        known.record_exploration(robot.position)

        return discoveries

    def get_visible_objects(self, robot: Robot = None) -> list[WorldObject]:
        """Get objects currently visible to a robot (within sensor range)."""
        if robot is None:
            robot = self.robot
        visible = []
        for obj in self.objects:
            if obj.collected:
                continue
            dist = robot.position.distance_to(obj.position)
            if dist <= robot.sensor_range:
                visible.append(obj)
        return visible

    def get_visible_obstacles(self, robot: Robot = None) -> list[Obstacle]:
        """Get obstacles currently visible to a robot (within sensor range)."""
        if robot is None:
            robot = self.robot
        visible = []
        for obs in self.obstacles:
            dist = robot.position.distance_to(obs.position)
            if dist <= robot.sensor_range:
                visible.append(obs)
        return visible

    def get_visible_robots(self, robot: Robot) -> list[Robot]:
        """Get other robots visible to this robot."""
        visible = []
        for other in self.robots:
            if other.id == robot.id:
                continue
            dist = robot.position.distance_to(other.position)
            if dist <= robot.sensor_range:
                visible.append(other)
        return visible

    def can_see_border(self, direction: str, robot: Robot = None) -> bool:
        """Check if the robot can see a border in the given direction."""
        if robot is None:
            robot = self.robot
        sensor_range = robot.sensor_range

        if direction == "north":
            return robot.position.y >= self._height - sensor_range
        elif direction == "south":
            return robot.position.y <= sensor_range
        elif direction == "east":
            return robot.position.x >= self._width - sensor_range
        elif direction == "west":
            return robot.position.x <= sensor_range
        return False

    def is_at_border(self, robot: Robot = None) -> Optional[str]:
        """Check if robot is at (touching) any border."""
        if robot is None:
            robot = self.robot
        margin = 0.5

        if robot.position.x <= margin:
            return "west"
        if robot.position.x >= self._width - margin:
            return "east"
        if robot.position.y <= margin:
            return "south"
        if robot.position.y >= self._height - margin:
            return "north"
        return None

    def get_uncollected_objects(self) -> list[WorldObject]:
        return [o for o in self.objects if not o.collected]

    def get_nearest_object(self, robot: Robot = None) -> Optional[WorldObject]:
        if robot is None:
            robot = self.robot
        uncollected = self.get_uncollected_objects()
        if not uncollected:
            return None
        return min(uncollected, key=lambda o: robot.position.distance_to(o.position))

    def get_nearest_obstacle(self, robot: Robot = None) -> Optional[Obstacle]:
        if robot is None:
            robot = self.robot
        if not self.obstacles:
            return None
        return min(self.obstacles, key=lambda o: robot.position.distance_to(o.position))

    def check_collision(self, robot: Robot = None) -> Optional[Obstacle]:
        """Check if robot is colliding with any obstacle."""
        if robot is None:
            robot = self.robot
        for obs in self.obstacles:
            dist = robot.position.distance_to(obs.position)
            if dist < (robot.collision_radius + obs.radius):
                return obs
        return None

    def check_robot_collision(self, robot: Robot) -> Optional[Robot]:
        """Check if robot is colliding with any other robot."""
        for other in self.robots:
            if other.id == robot.id:
                continue
            dist = robot.position.distance_to(other.position)
            if dist < (robot.collision_radius + other.collision_radius):
                return other
        return None

    def get_nearby_robots(self, robot: Robot, radius: float = 4.0) -> list[Robot]:
        """Get all other robots within a certain radius (cluster detection)."""
        nearby = []
        for other in self.robots:
            if other.id == robot.id or not other.is_active:
                continue
            dist = robot.position.distance_to(other.position)
            if dist < radius:
                nearby.append(other)
        return nearby

    def get_dispersion_direction(self, robot: Robot, nearby_robots: list[Robot]) -> float:
        """Calculate direction to move away from cluster centroid.

        Returns a heading (0-360) that moves the robot away from the center
        of mass of nearby robots, encouraging dispersion.
        """
        if not nearby_robots:
            return robot.heading

        # Calculate centroid of nearby robots (including self)
        cx = robot.position.x
        cy = robot.position.y
        for other in nearby_robots:
            cx += other.position.x
            cy += other.position.y
        cx /= (len(nearby_robots) + 1)
        cy /= (len(nearby_robots) + 1)

        # Direction away from centroid
        dx = robot.position.x - cx
        dy = robot.position.y - cy

        # If robot is at centroid, pick a direction based on robot index
        if abs(dx) < 0.1 and abs(dy) < 0.1:
            # Use robot index to pick different escape directions
            base_angle = (robot.robot_index * 72) % 360  # 5 robots = 72° apart
            import random
            return (base_angle + random.uniform(-30, 30)) % 360

        # Calculate angle away from centroid
        angle = math.degrees(math.atan2(dy, dx))
        if angle < 0:
            angle += 360

        # Add some randomness to prevent synchronized movement
        import random
        angle = (angle + random.uniform(-20, 20)) % 360

        return angle

    def is_robot_in_cluster(self, robot: Robot, min_robots: int = 2, radius: float = 4.0) -> bool:
        """Check if robot is in a cluster with other robots."""
        nearby = self.get_nearby_robots(robot, radius)
        return len(nearby) >= min_robots

    def check_object_pickup(self, robot: Robot = None) -> Optional[WorldObject]:
        """Check if robot can pick up any object.

        In multi-robot mode, objects are collected on first-come-first-serve basis.
        Pickup range is 1.0 to allow collection when obstacles are nearby
        (obstacle avoidance requires ~0.8 distance from obstacles).
        """
        if robot is None:
            robot = self.robot
        for obj in self.objects:
            if obj.collected:
                continue
            dist = robot.position.distance_to(obj.position)
            if dist < 1.0:  # Pickup range - increased to work with obstacle avoidance
                return obj
        return None

    def collect_object(self, robot: Robot, obj: WorldObject) -> bool:
        """Try to collect an object. Returns True if successful.

        Handles race conditions - if another robot collected it first, returns False.
        """
        if obj.collected:
            return False  # Already collected by another robot
        obj.collected = True
        obj.collected_by = robot.id  # Track who collected it
        robot.objects_collected += 1
        robot.success_metric += obj.value
        return True

    def get_obstacle_in_path(self, target: Position, robot: Robot = None, margin: float = 0.5) -> Optional[Obstacle]:
        """Check if any obstacle blocks the path to target."""
        if robot is None:
            robot = self.robot
        for obs in self.obstacles:
            dx = target.x - robot.position.x
            dy = target.y - robot.position.y
            path_len = math.sqrt(dx * dx + dy * dy)
            if path_len < 0.1:
                continue

            ox = obs.position.x - robot.position.x
            oy = obs.position.y - robot.position.y
            proj = (ox * dx + oy * dy) / path_len

            if proj < 0 or proj > path_len:
                continue

            perp_dist = abs(ox * dy - oy * dx) / path_len

            if perp_dist < (obs.radius + robot.collision_radius + margin):
                return obs

        return None

    def get_robot_in_path(self, target: Position, robot: Robot, margin: float = 0.5) -> Optional[Robot]:
        """Check if any other robot blocks the path to target."""
        for other in self.robots:
            if other.id == robot.id:
                continue

            dx = target.x - robot.position.x
            dy = target.y - robot.position.y
            path_len = math.sqrt(dx * dx + dy * dy)
            if path_len < 0.1:
                continue

            ox = other.position.x - robot.position.x
            oy = other.position.y - robot.position.y
            proj = (ox * dx + oy * dy) / path_len

            if proj < 0 or proj > path_len:
                continue

            perp_dist = abs(ox * dy - oy * dx) / path_len

            if perp_dist < (other.collision_radius + robot.collision_radius + margin):
                return other

        return None

    def is_position_safe(self, pos: Position, robot: Robot = None, margin: float = 0.2) -> bool:
        """Check if a position is safe (not colliding with any KNOWN obstacle or border)."""
        if robot is None:
            robot = self.robot
        known = self.known_worlds[robot.id]

        for obs in known.discovered_obstacles.values():
            dist = pos.distance_to(obs.position)
            if dist < (robot.collision_radius + obs.radius + margin):
                return False

        if known.known_min_x is not None and pos.x < known.known_min_x + margin:
            return False
        if known.known_max_x is not None and pos.x > known.known_max_x - margin:
            return False
        if known.known_min_y is not None and pos.y < known.known_min_y + margin:
            return False
        if known.known_max_y is not None and pos.y > known.known_max_y - margin:
            return False

        return True

    def is_position_actually_safe(self, pos: Position, robot: Robot = None, margin: float = 0.2) -> bool:
        """Check if a position is actually safe (for simulation collision detection).

        Checks obstacles and other robots.
        """
        if robot is None:
            robot = self.robot
        # Check obstacles
        for obs in self.obstacles:
            dist = pos.distance_to(obs.position)
            if dist < (robot.collision_radius + obs.radius + margin):
                return False
        # Check other robots
        for other in self.robots:
            if other.id == robot.id:
                continue
            dist = pos.distance_to(other.position)
            if dist < (robot.collision_radius + other.collision_radius + margin):
                return False
        # Check actual world bounds
        if pos.x < 0 or pos.x > self._width or pos.y < 0 or pos.y > self._height:
            return False
        return True

    def get_exploration_direction(self, robot: Robot = None) -> float:
        """
        Determine a direction to explore when no known objects are available.

        Uses multiple strategies:
        1. Normal: head towards unexplored areas, avoiding known obstacles
        2. Loop detected: pick least-visited direction to break the loop
        3. Frontier: head towards frontier cells (unexplored adjacent to explored)

        Returns heading in degrees.
        """
        if robot is None:
            robot = self.robot  # Backward compatibility
        known = self.known_worlds.get(robot.id, self.known_world)

        # All possible exploration directions (16 for finer control)
        directions = [i * 22.5 for i in range(16)]

        # If loop detected, use special loop-breaking strategy
        if known.loop_detected:
            # When stuck, pick a random unexplored direction or least visited
            safe_directions = []
            for angle in directions:
                angle_rad = math.radians(angle)
                test_dist = robot.sensor_range * 0.6
                test_x = robot.position.x + math.cos(angle_rad) * test_dist
                test_y = robot.position.y + math.sin(angle_rad) * test_dist
                test_pos = Position(test_x, test_y)

                # Must be safe to move there
                if not self.is_position_safe(test_pos, margin=0.3):
                    continue

                # Avoid known borders
                if known.known_min_x is not None and test_x < known.known_min_x + 1:
                    continue
                if known.known_max_x is not None and test_x > known.known_max_x - 1:
                    continue
                if known.known_min_y is not None and test_y < known.known_min_y + 1:
                    continue
                if known.known_max_y is not None and test_y > known.known_max_y - 1:
                    continue

                safe_directions.append(angle)

            if safe_directions:
                # Pick direction leading to least visited cells
                best_dir = known.get_least_visited_direction(robot.position, safe_directions)

                # If very stuck, add randomness to break pattern
                if known.stuck_counter > 5:
                    import random
                    best_dir = random.choice(safe_directions)

                return best_dir

        # Try frontier-based exploration: find unexplored cells adjacent to explored
        frontier_cells = self._find_frontier_cells()
        if frontier_cells:
            # Find nearest frontier cell
            nearest_frontier = min(frontier_cells,
                                   key=lambda c: math.sqrt((c[0] - robot.position.x)**2 +
                                                          (c[1] - robot.position.y)**2))
            # Direction to frontier
            dx = nearest_frontier[0] - robot.position.x
            dy = nearest_frontier[1] - robot.position.y
            if abs(dx) > 0.1 or abs(dy) > 0.1:
                return math.degrees(math.atan2(dy, dx))

        # Standard exploration scoring
        best_direction = robot.exploration_heading
        best_score = -float('inf')

        # Sense nearby pheromones for decision-making
        nearby_pheromones = self.sense_pheromones(robot)

        # Calculate grid size factor for scaling
        grid_factor = math.sqrt((self._width * self._height) / 400)  # Normalized to 20x20

        for angle in directions:
            angle_rad = math.radians(angle)
            # Extend test distance on larger grids
            test_dist = robot.sensor_range * 0.8 * min(grid_factor, 2.0)
            test_x = robot.position.x + math.cos(angle_rad) * test_dist
            test_y = robot.position.y + math.sin(angle_rad) * test_dist
            test_pos = Position(test_x, test_y)

            score = 0

            # Strongly prefer unexplored areas (scaled for grid size)
            test_cell = (round(test_x), round(test_y))
            if test_cell not in known.explored_positions:
                score += 15 * grid_factor  # Bigger bonus on larger grids

            # Penalize recently visited cells
            recent_visits = known.recent_positions.count(test_cell)
            score -= recent_visits * 5

            # === PHEROMONE-BASED SCORING ===
            # Only penalize OTHER robots' exploration pheromones
            for p in nearby_pheromones.get(PheromoneType.EXPLORATION, []):
                if p.position.distance_to(test_pos) < 2.0:
                    # Don't penalize own pheromones as much - we want to keep exploring!
                    if p.deposited_by == robot.id:
                        score -= 2 * p.strength  # Mild penalty for own trails
                    else:
                        score -= 6 * p.strength  # Stronger penalty for others' trails

            # Boost directions toward OBJECT_FOUND pheromones (potential objects)
            for p in nearby_pheromones.get(PheromoneType.OBJECT_FOUND, []):
                if p.position.distance_to(test_pos) < 3.0:
                    score += 15 * p.strength  # Strong attraction to object trails

            # Penalize directions with OBJECT_COLLECTED pheromones (nothing there)
            for p in nearby_pheromones.get(PheromoneType.OBJECT_COLLECTED, []):
                if p.position.distance_to(test_pos) < 2.0:
                    score -= 10 * p.strength

            # Penalize directions with DANGER pheromones
            for p in nearby_pheromones.get(PheromoneType.DANGER, []):
                if p.position.distance_to(test_pos) < 2.0:
                    score -= 12 * p.strength

            # === LARGE GRID BONUSES ===
            # Bonus for heading toward unexplored regions (center of unknown space)
            if grid_factor > 1.5:
                # Calculate distance to center of grid
                center_x, center_y = self._width / 2, self._height / 2
                dist_to_center = math.sqrt((test_x - center_x)**2 + (test_y - center_y)**2)

                # If we're not near center and this direction heads toward it, bonus
                robot_dist_to_center = math.sqrt((robot.position.x - center_x)**2 +
                                                  (robot.position.y - center_y)**2)
                if dist_to_center < robot_dist_to_center:
                    score += 5 * grid_factor

            # Bonus for heading toward edges (often unexplored on large grids)
            edge_dist = min(test_x, self._width - test_x, test_y, self._height - test_y)
            if edge_dist < 5:
                # Near edge - bonus if borders not known yet
                if ((test_x < 5 and known.known_min_x is None) or
                    (test_x > self._width - 5 and known.known_max_x is None) or
                    (test_y < 5 and known.known_min_y is None) or
                    (test_y > self._height - 5 and known.known_max_y is None)):
                    score += 10 * grid_factor

            # Avoid going towards known borders
            if known.known_min_x is not None and test_x < known.known_min_x + 2:
                score -= 25
            if known.known_max_x is not None and test_x > known.known_max_x - 2:
                score -= 25
            if known.known_min_y is not None and test_y < known.known_min_y + 2:
                score -= 25
            if known.known_max_y is not None and test_y > known.known_max_y - 2:
                score -= 25

            # Check if path is clear of known obstacles
            if self.is_position_safe(test_pos, margin=0.5):
                score += 5
            else:
                score -= 20

            # Preference for continuing in same direction (momentum)
            angle_diff = abs(angle - robot.exploration_heading)
            if angle_diff > 180:
                angle_diff = 360 - angle_diff
            if angle_diff < 45:
                score += 3  # Momentum bonus

            if score > best_score:
                best_score = score
                best_direction = angle

        return best_direction

    def _find_frontier_cells(self) -> list[tuple[int, int]]:
        """Find unexplored cells that are adjacent to explored cells (the frontier)."""
        known = self.known_world
        frontier = []

        # For each explored cell, check if neighbors are unexplored
        for (ex, ey) in known.explored_positions:
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                nx, ny = ex + dx, ey + dy
                neighbor = (nx, ny)

                # Skip if already explored
                if neighbor in known.explored_positions:
                    continue

                # Skip if out of known bounds
                if known.known_min_x is not None and nx < known.known_min_x:
                    continue
                if known.known_max_x is not None and nx > known.known_max_x:
                    continue
                if known.known_min_y is not None and ny < known.known_min_y:
                    continue
                if known.known_max_y is not None and ny > known.known_max_y:
                    continue

                # Check if it's a valid position (not blocked by known obstacle)
                test_pos = Position(float(nx), float(ny))
                if self.is_position_safe(test_pos, margin=0.3):
                    if neighbor not in frontier:
                        frontier.append(neighbor)

        return frontier

    def move_robot_direct(self, target: Position, dt: float = 1.0, robot: Robot = None):
        """Move robot directly towards target.

        Uses KNOWN obstacles for pathfinding, but actual collision detection
        will discover unknown obstacles if we hit them.
        """
        if robot is None:
            robot = self.robot  # Backward compatibility
        if not robot.is_active:
            return

        dx = target.x - robot.position.x
        dy = target.y - robot.position.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 0.1:
            return

        norm_dx, norm_dy = dx / dist, dy / dist
        move_dist = min(robot.speed * dt, dist)

        # Reduce safety margin when close to target to prevent oscillation
        safety_margin = 0.1 if dist > 2.0 else 0.0

        # Try direct movement first (using KNOWN world for planning)
        direct_pos = Position(
            robot.position.x + norm_dx * move_dist,
            robot.position.y + norm_dy * move_dist
        )

        best_pos = None
        if self.is_position_safe(direct_pos, robot, margin=safety_margin):
            best_pos = direct_pos
        elif dist < 1.5 and self.is_position_safe(direct_pos, robot, margin=0.0):
            best_pos = direct_pos
        else:
            # Direct blocked by known obstacle - try angles
            for angle in [15, -15, 30, -30, 45, -45, 60, -60, 90, -90]:
                angle_rad = math.radians(angle)
                cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
                rot_dx = norm_dx * cos_a - norm_dy * sin_a
                rot_dy = norm_dx * sin_a + norm_dy * cos_a

                test_pos = Position(
                    robot.position.x + rot_dx * move_dist,
                    robot.position.y + rot_dy * move_dist
                )
                if self.is_position_safe(test_pos, robot, margin=safety_margin):
                    best_pos = test_pos
                    norm_dx, norm_dy = rot_dx, rot_dy
                    break

        if best_pos is None:
            # Try smaller movement
            small_move = move_dist * 0.2
            small_pos = Position(
                robot.position.x + norm_dx * small_move,
                robot.position.y + norm_dy * small_move
            )
            if self.is_position_safe(small_pos, robot, margin=0.0):
                best_pos = small_pos
                move_dist = small_move

        if best_pos is None:
            return  # Can't move

        # Before actually moving, check ACTUAL safety (may hit unknown obstacle)
        if not self.is_position_actually_safe(best_pos, robot, margin=0.0):
            # Hit something unknown! This causes a collision and discovers it
            robot.has_collision = True
            robot.collision_count += 1
            # Don't move, but the sensor will discover the obstacle next tick
            return

        # Move is safe
        robot.position.x = best_pos.x
        robot.position.y = best_pos.y

        # Update state
        robot.heading = math.degrees(math.atan2(norm_dy, norm_dx))
        robot.distance_traveled += move_dist
        robot.battery -= 0.1 * move_dist

        # Clamp to actual bounds (robot discovers border if it hits it)
        known = self.known_worlds.get(robot.id, self.known_world)
        if robot.position.x < 0:
            robot.position.x = 0
            known.known_min_x = 0
        if robot.position.x > self._width:
            robot.position.x = self._width
            known.known_max_x = self._width
        if robot.position.y < 0:
            robot.position.y = 0
            known.known_min_y = 0
        if robot.position.y > self._height:
            robot.position.y = self._height
            known.known_max_y = self._height

    def move_robot_with_avoidance(self, target: Position, clear_angle: float, dt: float = 1.0, robot: Robot = None):
        """Move robot with avoidance angle specified by ontology rules.

        Uses KNOWN obstacles for planning. May still hit unknown obstacles.
        """
        if robot is None:
            robot = self.robot  # Backward compatibility
        if not robot.is_active:
            return

        dx = target.x - robot.position.x
        dy = target.y - robot.position.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 0.1:
            return

        norm_dx, norm_dy = dx / dist, dy / dist
        move_dist = min(robot.speed * dt, dist)

        best_pos = None
        best_dx, best_dy = norm_dx, norm_dy

        # Try the suggested angle and variations
        angles_to_try = [clear_angle]
        for extra in [15, 30, 45, 60, 75, 90, 120, 150, 180]:
            angles_to_try.extend([clear_angle + extra, clear_angle - extra])

        for angle in angles_to_try:
            angle_rad = math.radians(angle)
            cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
            rot_dx = norm_dx * cos_a - norm_dy * sin_a
            rot_dy = norm_dx * sin_a + norm_dy * cos_a

            test_pos = Position(
                robot.position.x + rot_dx * move_dist,
                robot.position.y + rot_dy * move_dist
            )

            if self.is_position_safe(test_pos, robot, margin=0.1):
                best_pos = test_pos
                best_dx, best_dy = rot_dx, rot_dy
                break

        if best_pos is None:
            small_move = move_dist * 0.3
            direct_pos = Position(
                robot.position.x + norm_dx * small_move,
                robot.position.y + norm_dy * small_move
            )
            if self.is_position_safe(direct_pos, robot, margin=0.05):
                best_pos = direct_pos
                best_dx, best_dy = norm_dx, norm_dy
                move_dist = small_move

        if best_pos is None:
            return

        # Check actual safety before moving
        if not self.is_position_actually_safe(best_pos, robot, margin=0.0):
            robot.has_collision = True
            robot.collision_count += 1
            return

        robot.position.x = best_pos.x
        robot.position.y = best_pos.y

        robot.heading = math.degrees(math.atan2(best_dy, best_dx))
        robot.distance_traveled += move_dist
        robot.battery -= 0.1 * move_dist

        # Clamp and discover borders
        known = self.known_worlds.get(robot.id, self.known_world)
        if robot.position.x < 0:
            robot.position.x = 0
            known.known_min_x = 0
        if robot.position.x > self._width:
            robot.position.x = self._width
            known.known_max_x = self._width
        if robot.position.y < 0:
            robot.position.y = 0
            known.known_min_y = 0
        if robot.position.y > self._height:
            robot.position.y = self._height
            known.known_max_y = self._height

    def move_robot_explore(self, heading: float, dt: float = 1.0, robot: Robot = None):
        """Move robot in exploration mode - heading towards unexplored area."""
        if robot is None:
            robot = self.robot  # Backward compatibility
        if not robot.is_active:
            return

        angle_rad = math.radians(heading)
        move_dist = robot.speed * dt

        dx = math.cos(angle_rad) * move_dist
        dy = math.sin(angle_rad) * move_dist

        target_pos = Position(
            robot.position.x + dx,
            robot.position.y + dy
        )

        # Use direct movement logic
        if self.is_position_safe(target_pos, robot, margin=0.1):
            if self.is_position_actually_safe(target_pos, robot, margin=0.0):
                robot.position.x = target_pos.x
                robot.position.y = target_pos.y
                robot.heading = heading
                robot.exploration_heading = heading
                robot.distance_traveled += move_dist
                robot.battery -= 0.1 * move_dist
            else:
                # Hit unknown obstacle
                robot.has_collision = True
                robot.collision_count += 1
        else:
            # Known obstacle, change exploration direction
            robot.exploration_heading = (heading + 90) % 360

        # Clamp and discover borders
        known = self.known_worlds.get(robot.id, self.known_world)
        if robot.position.x < 0:
            robot.position.x = 0
            known.known_min_x = 0
        if robot.position.x > self._width:
            robot.position.x = self._width
            known.known_max_x = self._width
        if robot.position.y < 0:
            robot.position.y = 0
            known.known_min_y = 0
        if robot.position.y > self._height:
            robot.position.y = self._height
            known.known_max_y = self._height


def create_random_world(num_objects: int = 10, num_obstacles: int = 5,
                        width: int = 20, height: int = 20,
                        num_robots: int = 1,
                        battery_capacity: float = 100.0) -> SimulationWorld:
    """Create a random simulation world with multiple competing robots.

    Args:
        num_objects: Number of collectible objects to spawn
        num_obstacles: Number of obstacles to spawn
        width: World width
        height: World height
        num_robots: Number of competing robots (1-6)
        battery_capacity: Battery capacity for each robot
    """
    world = SimulationWorld(width=width, height=height, num_robots=num_robots,
                            battery_capacity=battery_capacity)

    # Add collectible objects
    for i in range(num_objects):
        obj = WorldObject(
            id=f"obj{i+1}",
            position=Position(
                random.uniform(2, world.width - 2),
                random.uniform(2, world.height - 2)
            ),
            value=random.uniform(10, 50)
        )
        world.add_object(obj)

    # Add obstacles (avoiding all robot start positions)
    for i in range(num_obstacles):
        while True:
            pos = Position(
                random.uniform(2, world.width - 2),
                random.uniform(2, world.height - 2)
            )
            # Ensure not too close to any robot start position
            too_close = False
            for robot in world.robots:
                if pos.distance_to(robot.position) < 3:
                    too_close = True
                    break
            if not too_close:
                break

        obs = Obstacle(
            id=f"obs{i+1}",
            position=pos,
            radius=random.uniform(0.3, 0.8)
        )
        world.add_obstacle(obs)

    return world


# =============================================================================
# ONTOLOGY INTEGRATION
# =============================================================================

def create_client() -> DTaaSClient:
    """Create DTaaS client with authentication."""
    token = get_token()
    return DTaaSClient(base_url=BASE_URL, token=token, timeout=60.0)


def load_ontology(client: DTaaSClient):
    """Load the robot simulation ontology."""
    ontology_path = os.path.join(
        os.path.dirname(__file__), '..', 'ontologies', 'robot_simulation.ttl'
    )

    if os.path.exists(ontology_path):
        with open(ontology_path, 'r') as f:
            content = f.read()
        try:
            client.ontologies.create({
                "id": "robot_simulation",
                "name": "Robot Simulation Ontology",
                "content": content,
                "format": "turtle"
            })
            log("[ONTOLOGY] Loaded robot_simulation ontology")
        except DTaaSError:
            log("[ONTOLOGY] Ontology already loaded")
    else:
        log(f"[WARNING] Ontology file not found: {ontology_path}")


def initialize_twin(client: DTaaSClient, world: SimulationWorld):
    """Initialize the twin with all robots' known state.

    In partial observability, each robot starts knowing only:
    - Its own position and state
    - Home location (where it started)
    Nothing else is known until discovered through sensing.
    """
    # Do initial sensing for all robots to discover nearby entities
    all_discoveries = {"new_objects": [], "new_obstacles": []}
    for robot in world.robots:
        discoveries = world.sense_environment(robot)
        all_discoveries["new_objects"].extend(discoveries["new_objects"])
        all_discoveries["new_obstacles"].extend(discoveries["new_obstacles"])

    # Create initial RDF with all robots
    turtle = f"""
@prefix robo: <{ROBO}> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
"""

    # Add each robot
    for robot in world.robots:
        home_pos = world.home_positions.get(robot.id, world.home_position)
        turtle += f"""
# Robot {robot.id} - knows its own state
<urn:robot:{robot.id}> a robo:Robot, robo:ActiveRobot ;
    robo:positionX "{robot.position.x}"^^xsd:float ;
    robo:positionY "{robot.position.y}"^^xsd:float ;
    robo:heading "{robot.heading}"^^xsd:float ;
    robo:speed "{robot.speed}"^^xsd:float ;
    robo:batteryLevel "{robot.battery}"^^xsd:float ;
    robo:sensorRange "{robot.sensor_range}"^^xsd:float ;
    robo:hasCollision "false"^^xsd:boolean ;
    robo:hasRobotCollision "false"^^xsd:boolean ;
    robo:isActive "true"^^xsd:boolean ;
    robo:isExploring "false"^^xsd:boolean ;
    robo:successMetric "0.0"^^xsd:float ;
    robo:objectsCollected "0"^^xsd:integer ;
    robo:knownObjects "0"^^xsd:integer ;
    robo:distanceTraveled "0.0"^^xsd:float ;
    robo:collisionCount "0"^^xsd:integer ;
    robo:robotCollisionCount "0"^^xsd:integer ;
    robo:tickCount "0"^^xsd:integer ;
    robo:hasHomeLocation <urn:location:home_{robot.id}> .

# Home location for {robot.id}
<urn:location:home_{robot.id}> a robo:Location ;
    robo:gridX "{int(home_pos.x)}"^^xsd:integer ;
    robo:gridY "{int(home_pos.y)}"^^xsd:integer .
"""

    # Add DISCOVERED objects (combine from all robots' known worlds)
    all_discovered_objects = {}
    all_discovered_obstacles = {}
    for robot in world.robots:
        known = world.known_worlds.get(robot.id)
        if known:
            all_discovered_objects.update(known.discovered_objects)
            all_discovered_obstacles.update(known.discovered_obstacles)

    for obj in all_discovered_objects.values():
        turtle += f"""
<urn:object:{obj.id}> a robo:CollectibleObject, robo:DiscoveredObject ;
    robo:positionX "{obj.position.x}"^^xsd:float ;
    robo:positionY "{obj.position.y}"^^xsd:float ;
    robo:objectValue "{obj.value}"^^xsd:float ;
    robo:isCollected "false"^^xsd:boolean .
"""

    # Add DISCOVERED obstacles
    for obs in all_discovered_obstacles.values():
        turtle += f"""
<urn:obstacle:{obs.id}> a robo:Obstacle, robo:DiscoveredObstacle ;
    robo:positionX "{obs.position.x}"^^xsd:float ;
    robo:positionY "{obs.position.y}"^^xsd:float .
"""

    # Create or update twin
    try:
        client.twins.delete(TWIN_ID)
    except DTaaSError:
        pass

    client.twins.create({
        "id": TWIN_ID,
        "name": "Robot Simulation",
        "type": f"{ROBO}SimulationWorld",
        "domain": "robotics"
    })

    client.twins.add_triples(TWIN_ID, turtle, format="turtle")

    # Report initial discoveries
    log(f"[TWIN] Initialized twin '{TWIN_ID}' with {len(world.robots)} robot(s)")
    log(f"[SENSE] Initial scan: discovered {len(all_discoveries['new_objects'])} objects, "
        f"{len(all_discoveries['new_obstacles'])} obstacles")


def compute_obstacle_geometry(world: SimulationWorld, target: Optional[Position], robot: Robot = None) -> dict:
    """Compute geometric relationships between robot, KNOWN obstacles, and target.

    This data will be stored in the ontology for rules to reason about.
    Uses only discovered obstacles - the robot can't plan around what it doesn't know.
    """
    if robot is None:
        robot = world.robot  # Backward compatibility
    known = world.known_worlds.get(robot.id, world.known_world)
    result = {
        "pathBlocked": False,
        "obstacleAngle": 0.0,  # Angle of nearest blocking obstacle relative to heading
        "obstacleOnLeft": False,
        "obstacleOnRight": False,
        "clearPathAngle": 0.0,  # Suggested clear angle if path is blocked
    }

    if not target:
        return result

    # Direction to target
    dx = target.x - robot.position.x
    dy = target.y - robot.position.y
    dist_to_target = math.sqrt(dx * dx + dy * dy)
    if dist_to_target < 0.1:
        return result

    target_angle = math.degrees(math.atan2(dy, dx))

    # Check each KNOWN obstacle only
    blocking_obstacle = None
    min_blocking_dist = float('inf')

    for obs in known.discovered_obstacles.values():
        obs_dx = obs.position.x - robot.position.x
        obs_dy = obs.position.y - robot.position.y
        obs_dist = math.sqrt(obs_dx * obs_dx + obs_dy * obs_dy)

        if obs_dist > dist_to_target + 2:  # Obstacle is beyond target
            continue

        # Check if obstacle is in path (using cross product for perpendicular distance)
        # Project obstacle onto path direction
        path_proj = (obs_dx * dx + obs_dy * dy) / dist_to_target
        if path_proj < 0:  # Behind us
            continue

        perp_dist = abs(obs_dx * dy - obs_dy * dx) / dist_to_target
        collision_radius = robot.collision_radius + obs.radius + 0.5  # Safety margin

        if perp_dist < collision_radius and path_proj < min_blocking_dist:
            blocking_obstacle = obs
            min_blocking_dist = path_proj

    if blocking_obstacle:
        result["pathBlocked"] = True

        # Compute angle of obstacle relative to target direction
        obs_dx = blocking_obstacle.position.x - robot.position.x
        obs_dy = blocking_obstacle.position.y - robot.position.y
        obs_angle = math.degrees(math.atan2(obs_dy, obs_dx))

        # Relative angle (positive = obstacle is to the left of target direction)
        rel_angle = obs_angle - target_angle
        # Normalize to -180 to 180
        while rel_angle > 180: rel_angle -= 360
        while rel_angle < -180: rel_angle += 360

        result["obstacleAngle"] = rel_angle
        result["obstacleOnLeft"] = rel_angle > 0
        result["obstacleOnRight"] = rel_angle <= 0

        # Suggest avoidance angle (go opposite side of obstacle)
        if rel_angle > 0:
            result["clearPathAngle"] = -45  # Go right
        else:
            result["clearPathAngle"] = 45  # Go left

    return result


def update_sensor_data(client: DTaaSClient, world: SimulationWorld, robot: Robot = None):
    """Update ontology with current sensor readings via SPARQL UPDATE (SENSE phase).

    This is the primary sensing function that:
    1. Discovers new entities in sensor range
    2. Adds newly discovered entities to the ontology
    3. Updates robot sensor data in the ontology
    """
    if robot is None:
        robot = world.robot  # Backward compatibility
    known = world.known_worlds.get(robot.id, world.known_world)

    # SENSE: Discover new entities in range
    discoveries = world.sense_environment(robot)

    # Add newly discovered entities to ontology
    if discoveries["new_objects"] or discoveries["new_obstacles"]:
        insert_parts = []

        for obj in discoveries["new_objects"]:
            insert_parts.append(f"""
<urn:object:{obj.id}> a robo:CollectibleObject, robo:DiscoveredObject ;
    robo:positionX "{obj.position.x}"^^xsd:float ;
    robo:positionY "{obj.position.y}"^^xsd:float ;
    robo:objectValue "{obj.value}"^^xsd:float ;
    robo:isCollected "false"^^xsd:boolean .""")

        for obs in discoveries["new_obstacles"]:
            insert_parts.append(f"""
<urn:obstacle:{obs.id}> a robo:Obstacle, robo:DiscoveredObstacle ;
    robo:positionX "{obs.position.x}"^^xsd:float ;
    robo:positionY "{obs.position.y}"^^xsd:float .""")

        if insert_parts:
            insert_query = f"""
PREFIX robo: <{ROBO}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

INSERT DATA {{
{"".join(insert_parts)}
}}
"""
            try:
                client.twins.sparql_update(TWIN_ID, insert_query)
            except DTaaSError as e:
                log(f"[SENSE] Error adding discoveries to ontology: {e}")

    # Check for collision (uses actual world state for collision detection)
    collision = world.check_collision(robot)
    if collision:
        robot.has_collision = True
        robot.collision_count += 1
        # Collision also discovers the obstacle if not known
        if not known.has_discovered_obstacle(collision.id):
            known.discovered_obstacles[collision.id] = collision
    else:
        robot.has_collision = False

    # Find nearest KNOWN object and obstacle (robot can only reason about what it knows)
    nearest_obj = known.get_nearest_known_object(robot.position)
    nearest_obs = known.get_nearest_known_obstacle(robot.position)

    dist_to_obj = robot.position.distance_to(nearest_obj.position) if nearest_obj else 999
    dist_to_obs = robot.position.distance_to(nearest_obs.position) if nearest_obs else 999

    # Track if robot is in exploration mode (no known uncollected objects)
    is_exploring = len(known.get_uncollected_known_objects()) == 0

    # Compute obstacle geometry for ontology-based reasoning (uses known obstacles)
    target = nearest_obj.position if nearest_obj else None
    geometry = compute_obstacle_geometry(world, target, robot)

    # Count known uncollected objects
    known_uncollected = len(known.get_uncollected_known_objects())

    # Build SPARQL UPDATE to modify sensor values in the RDF store
    update = f"""
PREFIX robo: <{ROBO}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

DELETE {{
    <urn:robot:{robot.id}> robo:positionX ?oldX .
    <urn:robot:{robot.id}> robo:positionY ?oldY .
    <urn:robot:{robot.id}> robo:heading ?oldH .
    <urn:robot:{robot.id}> robo:batteryLevel ?oldB .
    <urn:robot:{robot.id}> robo:hasCollision ?oldC .
    <urn:robot:{robot.id}> robo:distanceToNearest ?oldDN .
    <urn:robot:{robot.id}> robo:distanceToObstacle ?oldDO .
    <urn:robot:{robot.id}> robo:distanceTraveled ?oldDT .
    <urn:robot:{robot.id}> robo:collisionCount ?oldCC .
    <urn:robot:{robot.id}> robo:tickCount ?oldTC .
    <urn:robot:{robot.id}> robo:successMetric ?oldSM .
    <urn:robot:{robot.id}> robo:objectsCollected ?oldOC .
    <urn:robot:{robot.id}> robo:knownObjects ?oldKO .
    <urn:robot:{robot.id}> robo:isExploring ?oldIE .
    <urn:robot:{robot.id}> robo:pathBlocked ?oldPB .
    <urn:robot:{robot.id}> robo:obstacleAngle ?oldOA .
    <urn:robot:{robot.id}> robo:obstacleOnLeft ?oldOL .
    <urn:robot:{robot.id}> robo:obstacleOnRight ?oldOR .
    <urn:robot:{robot.id}> robo:clearPathAngle ?oldCPA .
}}
INSERT {{
    <urn:robot:{robot.id}> robo:positionX "{robot.position.x}"^^xsd:float .
    <urn:robot:{robot.id}> robo:positionY "{robot.position.y}"^^xsd:float .
    <urn:robot:{robot.id}> robo:heading "{robot.heading}"^^xsd:float .
    <urn:robot:{robot.id}> robo:batteryLevel "{robot.battery}"^^xsd:float .
    <urn:robot:{robot.id}> robo:hasCollision "{str(robot.has_collision).lower()}"^^xsd:boolean .
    <urn:robot:{robot.id}> robo:distanceToNearest "{dist_to_obj}"^^xsd:float .
    <urn:robot:{robot.id}> robo:distanceToObstacle "{dist_to_obs}"^^xsd:float .
    <urn:robot:{robot.id}> robo:distanceTraveled "{robot.distance_traveled}"^^xsd:float .
    <urn:robot:{robot.id}> robo:collisionCount "{robot.collision_count}"^^xsd:integer .
    <urn:robot:{robot.id}> robo:tickCount "{robot.tick_count}"^^xsd:integer .
    <urn:robot:{robot.id}> robo:successMetric "{robot.success_metric}"^^xsd:float .
    <urn:robot:{robot.id}> robo:objectsCollected "{robot.objects_collected}"^^xsd:integer .
    <urn:robot:{robot.id}> robo:knownObjects "{known_uncollected}"^^xsd:integer .
    <urn:robot:{robot.id}> robo:isExploring "{str(is_exploring).lower()}"^^xsd:boolean .
    <urn:robot:{robot.id}> robo:pathBlocked "{str(geometry['pathBlocked']).lower()}"^^xsd:boolean .
    <urn:robot:{robot.id}> robo:obstacleAngle "{geometry['obstacleAngle']}"^^xsd:float .
    <urn:robot:{robot.id}> robo:obstacleOnLeft "{str(geometry['obstacleOnLeft']).lower()}"^^xsd:boolean .
    <urn:robot:{robot.id}> robo:obstacleOnRight "{str(geometry['obstacleOnRight']).lower()}"^^xsd:boolean .
    <urn:robot:{robot.id}> robo:clearPathAngle "{geometry['clearPathAngle']}"^^xsd:float .
}}
WHERE {{
    OPTIONAL {{ <urn:robot:{robot.id}> robo:positionX ?oldX }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:positionY ?oldY }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:heading ?oldH }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:batteryLevel ?oldB }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:hasCollision ?oldC }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:distanceToNearest ?oldDN }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:distanceToObstacle ?oldDO }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:distanceTraveled ?oldDT }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:collisionCount ?oldCC }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:tickCount ?oldTC }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:successMetric ?oldSM }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:objectsCollected ?oldOC }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:knownObjects ?oldKO }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:isExploring ?oldIE }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:pathBlocked ?oldPB }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:obstacleAngle ?oldOA }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:obstacleOnLeft ?oldOL }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:obstacleOnRight ?oldOR }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:clearPathAngle ?oldCPA }}
}}
"""

    try:
        client.twins.sparql_update(TWIN_ID, update)
    except DTaaSError as e:
        log(f"[SENSE] Error updating sensor data: {e}")

    # Record position in ontology for exploration memory
    record_position_in_ontology(client, world)

    # Detect loops from ontology and update loop state
    detect_loops_from_ontology(client, world)


def record_position_in_ontology(client: DTaaSClient, world: SimulationWorld):
    """Record current position in ontology as PositionRecord and update ExploredCell.

    This stores the robot's spatial memory in the ontology, enabling
    SPARQL-based loop detection and exploration direction decisions.
    """
    robot = world.robot
    tick = robot.tick_count
    cell_x = round(robot.position.x)
    cell_y = round(robot.position.y)
    cell_id = f"cell_{cell_x}_{cell_y}"

    # Insert new position record
    insert_position = f"""
PREFIX robo: <{ROBO}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

INSERT DATA {{
    <urn:position:tick_{tick}> a robo:PositionRecord ;
        robo:cellX "{cell_x}"^^xsd:integer ;
        robo:cellY "{cell_y}"^^xsd:integer ;
        robo:atTick "{tick}"^^xsd:integer .
    <urn:robot:{robot.id}> robo:hasPositionRecord <urn:position:tick_{tick}> .
}}
"""
    try:
        client.twins.sparql_update(TWIN_ID, insert_position)
    except DTaaSError as e:
        log(f"[MEMORY] Error recording position: {e}")

    # Update or create ExploredCell with visit count
    # First check if cell exists and get current visit count
    check_cell = f"""
PREFIX robo: <{ROBO}>

SELECT ?visitCount ?lastTick WHERE {{
    <urn:cell:{cell_id}> a robo:ExploredCell ;
        robo:visitCount ?visitCount ;
        robo:lastVisitTick ?lastTick .
}}
"""
    try:
        result = client.twins.sparql_query(TWIN_ID, check_cell)
        if result.bindings:
            # Cell exists - update visit count
            old_count = int(result.bindings[0].get("visitCount", {}).get("value", 0))
            new_count = old_count + 1
            update_cell = f"""
PREFIX robo: <{ROBO}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

DELETE {{
    <urn:cell:{cell_id}> robo:visitCount ?oldCount .
    <urn:cell:{cell_id}> robo:lastVisitTick ?oldTick .
}}
INSERT {{
    <urn:cell:{cell_id}> robo:visitCount "{new_count}"^^xsd:integer .
    <urn:cell:{cell_id}> robo:lastVisitTick "{tick}"^^xsd:integer .
}}
WHERE {{
    <urn:cell:{cell_id}> robo:visitCount ?oldCount .
    <urn:cell:{cell_id}> robo:lastVisitTick ?oldTick .
}}
"""
            client.twins.sparql_update(TWIN_ID, update_cell)
        else:
            # New cell - create it
            create_cell = f"""
PREFIX robo: <{ROBO}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

INSERT DATA {{
    <urn:cell:{cell_id}> a robo:ExploredCell ;
        robo:cellX "{cell_x}"^^xsd:integer ;
        robo:cellY "{cell_y}"^^xsd:integer ;
        robo:visitCount "1"^^xsd:integer ;
        robo:lastVisitTick "{tick}"^^xsd:integer .
    <urn:robot:{robot.id}> robo:hasExploredCell <urn:cell:{cell_id}> .
}}
"""
            client.twins.sparql_update(TWIN_ID, create_cell)
    except DTaaSError as e:
        log(f"[MEMORY] Error updating explored cell: {e}")

    # Clean up old position records (keep only last 30)
    cleanup_old = f"""
PREFIX robo: <{ROBO}>

DELETE {{
    ?record a robo:PositionRecord .
    ?record robo:cellX ?x .
    ?record robo:cellY ?y .
    ?record robo:atTick ?tick .
    <urn:robot:{robot.id}> robo:hasPositionRecord ?record .
}}
WHERE {{
    ?record a robo:PositionRecord .
    ?record robo:atTick ?tick .
    FILTER(?tick < {tick - 30})
}}
"""
    try:
        client.twins.sparql_update(TWIN_ID, cleanup_old)
    except DTaaSError:
        pass  # Ignore cleanup errors


def detect_loops_from_ontology(client: DTaaSClient, world: SimulationWorld):
    """Query ontology to detect if robot is stuck in a loop.

    A loop is detected if the robot has visited the same cell 3+ times
    in the last 30 ticks. This is computed via SPARQL aggregation.
    """
    robot = world.robot
    tick = robot.tick_count
    known = world.known_world

    # Query for cells visited 3+ times in recent history
    loop_query = f"""
PREFIX robo: <{ROBO}>

SELECT ?cellX ?cellY (COUNT(*) as ?visitCount) WHERE {{
    <urn:robot:{robot.id}> robo:hasPositionRecord ?record .
    ?record robo:cellX ?cellX ;
            robo:cellY ?cellY ;
            robo:atTick ?tick .
    FILTER(?tick > {tick - 30})
}}
GROUP BY ?cellX ?cellY
HAVING (COUNT(*) >= 3)
ORDER BY DESC(?visitCount)
LIMIT 1
"""
    try:
        result = client.twins.sparql_query(TWIN_ID, loop_query)
        if result.bindings:
            # Loop detected!
            visit_count = int(result.bindings[0].get("visitCount", {}).get("value", 0))
            known.loop_detected = True
            known.stuck_counter += 1

            # Update ontology with loop state
            update_loop = f"""
PREFIX robo: <{ROBO}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

DELETE {{
    <urn:robot:{robot.id}> robo:inLoop ?oldLoop .
    <urn:robot:{robot.id}> robo:stuckCounter ?oldStuck .
}}
INSERT {{
    <urn:robot:{robot.id}> robo:inLoop "true"^^xsd:boolean .
    <urn:robot:{robot.id}> robo:stuckCounter "{known.stuck_counter}"^^xsd:integer .
    <urn:robot:{robot.id}> a robo:InLoop .
}}
WHERE {{
    OPTIONAL {{ <urn:robot:{robot.id}> robo:inLoop ?oldLoop }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:stuckCounter ?oldStuck }}
}}
"""
            client.twins.sparql_update(TWIN_ID, update_loop)
        else:
            # No loop
            if known.loop_detected:
                known.stuck_counter = max(0, known.stuck_counter - 1)
            known.loop_detected = False

            # Update ontology - remove InLoop classification
            update_no_loop = f"""
PREFIX robo: <{ROBO}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

DELETE {{
    <urn:robot:{robot.id}> robo:inLoop ?oldLoop .
    <urn:robot:{robot.id}> robo:stuckCounter ?oldStuck .
    <urn:robot:{robot.id}> a robo:InLoop .
}}
INSERT {{
    <urn:robot:{robot.id}> robo:inLoop "false"^^xsd:boolean .
    <urn:robot:{robot.id}> robo:stuckCounter "{known.stuck_counter}"^^xsd:integer .
}}
WHERE {{
    OPTIONAL {{ <urn:robot:{robot.id}> robo:inLoop ?oldLoop }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:stuckCounter ?oldStuck }}
}}
"""
            client.twins.sparql_update(TWIN_ID, update_no_loop)
    except DTaaSError as e:
        log(f"[LOOP] Error detecting loops: {e}")

    # Push geometric metrics to ontology for SWRL rules
    # These enable ontology-driven venture decisions based on coverage area
    try:
        update_metrics = f"""
PREFIX robo: <{ROBO}>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

DELETE {{
    <urn:robot:{robot.id}> robo:coverageArea ?oldArea .
    <urn:robot:{robot.id}> robo:pathKnottiness ?oldKnot .
    <urn:robot:{robot.id}> robo:recentPositionCount ?oldCount .
}}
INSERT {{
    <urn:robot:{robot.id}> robo:coverageArea "{known.coverage_area:.2f}"^^xsd:float .
    <urn:robot:{robot.id}> robo:pathKnottiness "{known.path_knottiness:.2f}"^^xsd:float .
    <urn:robot:{robot.id}> robo:recentPositionCount "{len(known.recent_positions)}"^^xsd:integer .
}}
WHERE {{
    OPTIONAL {{ <urn:robot:{robot.id}> robo:coverageArea ?oldArea }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:pathKnottiness ?oldKnot }}
    OPTIONAL {{ <urn:robot:{robot.id}> robo:recentPositionCount ?oldCount }}
}}
"""
        client.twins.sparql_update(TWIN_ID, update_metrics)
    except DTaaSError as e:
        log(f"[METRICS] Error updating geometric metrics: {e}")


# =============================================================================
# OPTIMIZED BATCH UPDATE FUNCTIONS
# =============================================================================

def update_tick_batched(
    client: DTaaSClient,
    world: SimulationWorld,
    batch: BatchUpdateBuilder
) -> None:
    """
    Process all robots in a tick and accumulate updates in the batch builder.

    This is the optimized version that:
    1. Senses environment for all robots
    2. Computes state updates locally (Python, not SPARQL)
    3. Accumulates all changes in a single BatchUpdateBuilder
    4. Uses timeseries API for position history (if enabled)

    Call batch.execute(client) after all robots are processed to apply updates.
    """
    for robot in world.get_active_robots():
        # SENSE: Discover new entities
        known = world.known_worlds.get(robot.id, world.known_world)
        discoveries = world.sense_environment(robot)

        # Add discoveries to batch
        for obj in discoveries["new_objects"]:
            batch.add_discovered_object(obj)
        for obs in discoveries["new_obstacles"]:
            batch.add_discovered_obstacle(obs)

        # Check for collision (uses actual world state)
        collision = world.check_collision(robot)
        if collision:
            robot.has_collision = True
            robot.collision_count += 1
            if not known.has_discovered_obstacle(collision.id):
                known.discovered_obstacles[collision.id] = collision
        else:
            robot.has_collision = False

        # Find nearest KNOWN object and obstacle
        nearest_obj = known.get_nearest_known_object(robot.position)
        nearest_obs = known.get_nearest_known_obstacle(robot.position)

        dist_to_obj = robot.position.distance_to(nearest_obj.position) if nearest_obj else 999
        dist_to_obs = robot.position.distance_to(nearest_obs.position) if nearest_obs else 999

        # Track if robot is in exploration mode
        known_uncollected = known.get_uncollected_known_objects()
        is_exploring = len(known_uncollected) == 0

        # Compute obstacle geometry
        target = nearest_obj.position if nearest_obj else None
        geometry = compute_obstacle_geometry(world, target, robot)

        # Detect loops locally (no SPARQL)
        detect_loops_local(known)

        # Calculate cluster state for ontology
        nearby_robots = world.get_nearby_robots(robot, radius=4.0)
        nearby_count = len(nearby_robots)

        # Update cluster tracking
        if nearby_count >= 2:
            robot.ticks_in_cluster += 1
        else:
            robot.ticks_in_cluster = max(0, robot.ticks_in_cluster - 1)

        # Calculate dispersion heading (away from cluster centroid)
        dispersion_heading = world.get_dispersion_direction(robot, nearby_robots) if nearby_count > 0 else robot.heading
        robot.dispersion_heading = dispersion_heading

        # Build robot state update
        state = RobotStateUpdate(
            robot_id=robot.id,
            position_x=robot.position.x,
            position_y=robot.position.y,
            heading=robot.heading,
            battery=robot.battery,
            has_collision=robot.has_collision,
            dist_to_object=dist_to_obj,
            dist_to_obstacle=dist_to_obs,
            distance_traveled=robot.distance_traveled,
            collision_count=robot.collision_count,
            tick_count=robot.tick_count,
            success_metric=robot.success_metric,
            objects_collected=robot.objects_collected,
            known_objects=len(known_uncollected),
            is_exploring=is_exploring,
            path_blocked=geometry['pathBlocked'],
            obstacle_angle=geometry['obstacleAngle'],
            obstacle_on_left=geometry['obstacleOnLeft'],
            obstacle_on_right=geometry['obstacleOnRight'],
            clear_path_angle=geometry['clearPathAngle'],
            is_stuck=robot.is_stuck,
            ticks_without_movement=robot.ticks_without_movement,
            escape_heading=robot.escape_heading or 0.0,
            in_loop=known.loop_detected,
            stuck_counter=known.stuck_counter,
            # Cluster avoidance state (for ontology-based reasoning)
            nearby_robot_count=nearby_count,
            ticks_in_cluster=robot.ticks_in_cluster,
            dispersion_heading=dispersion_heading,
            robot_priority=robot.robot_index,  # Higher index = disperse sooner
        )
        batch.add_robot_state(state)


def detect_loops_local(known: KnownWorld) -> None:
    """
    Detect loops using local Python code instead of SPARQL queries.

    This is much faster than the SPARQL-based version because:
    1. No network round-trip
    2. Python dict/Counter operations are O(1)
    3. Already have the data in memory from sense_environment()
    """
    # Use Counter to find cells visited 3+ times in recent history
    if len(known.recent_positions) < 15:
        known.loop_detected = False
        return

    cell_counts = Counter(known.recent_positions)
    max_visits = max(cell_counts.values())

    if max_visits >= 3:
        known.loop_detected = True
        known.stuck_counter += 1
    else:
        if known.loop_detected:
            known.stuck_counter = max(0, known.stuck_counter - 1)
        known.loop_detected = False


def ingest_position_timeseries(
    client: DTaaSClient,
    world: SimulationWorld,
    tick: int
) -> None:
    """
    Record all robot positions to timeseries API for efficient history tracking.

    This replaces the heavy PositionRecord RDF entities with lightweight
    SOSA observations that are optimized for time-series queries.
    """
    if not USE_TIMESERIES:
        return

    try:
        # Use ISO format string for JSON serialization
        now = datetime.now(timezone.utc).isoformat()

        for robot in world.robots:
            # Ingest position as timeseries data points
            client.timeseries.ingest(
                TWIN_ID,
                f"robot_{robot.id}_positionX",
                [{"timestamp": now, "value": robot.position.x}]
            )
            client.timeseries.ingest(
                TWIN_ID,
                f"robot_{robot.id}_positionY",
                [{"timestamp": now, "value": robot.position.y}]
            )

            # Also record key metrics for historical analysis
            if tick % 5 == 0:  # Every 5 ticks to reduce overhead
                client.timeseries.ingest(
                    TWIN_ID,
                    f"robot_{robot.id}_battery",
                    [{"timestamp": now, "value": robot.battery}]
                )
                client.timeseries.ingest(
                    TWIN_ID,
                    f"robot_{robot.id}_successMetric",
                    [{"timestamp": now, "value": robot.success_metric}]
                )
    except DTaaSError as e:
        log(f"[TIMESERIES] Error ingesting position data: {e}")


def query_least_visited_direction(client: DTaaSClient, world: SimulationWorld) -> Optional[float]:
    """Query ontology to find direction leading to least-visited cells.

    Returns the direction (in degrees) that leads to unexplored or
    least-recently-visited areas, computed via SPARQL.
    """
    robot = world.robot
    known = world.known_world
    tick = robot.tick_count

    # Get all explored cells with their visit counts from recent history
    cell_query = f"""
PREFIX robo: <{ROBO}>

SELECT ?cellX ?cellY (COUNT(*) as ?recentVisits) WHERE {{
    <urn:robot:{robot.id}> robo:hasPositionRecord ?record .
    ?record robo:cellX ?cellX ;
            robo:cellY ?cellY ;
            robo:atTick ?recordTick .
    FILTER(?recordTick > {tick - 30})
}}
GROUP BY ?cellX ?cellY
"""
    try:
        result = client.twins.sparql_query(TWIN_ID, cell_query)

        # Build a map of cell -> recent visit count
        visit_counts = {}
        for binding in result.bindings:
            cx = int(binding.get("cellX", {}).get("value", 0))
            cy = int(binding.get("cellY", {}).get("value", 0))
            visits = int(binding.get("recentVisits", {}).get("value", 0))
            visit_counts[(cx, cy)] = visits

        # Score directions based on visit counts
        directions = [i * 22.5 for i in range(16)]
        best_direction = robot.exploration_heading
        best_score = float('inf')

        for angle in directions:
            angle_rad = math.radians(angle)
            score = 0

            # Check cells in this direction
            for dist in [2, 4, 6]:
                check_x = round(robot.position.x + math.cos(angle_rad) * dist)
                check_y = round(robot.position.y + math.sin(angle_rad) * dist)
                cell = (check_x, check_y)

                # Add visit count to score (fewer = better)
                score += visit_counts.get(cell, 0) * 2

                # Penalize known borders
                if known.known_min_x is not None and check_x < known.known_min_x + 1:
                    score += 100
                if known.known_max_x is not None and check_x > known.known_max_x - 1:
                    score += 100
                if known.known_min_y is not None and check_y < known.known_min_y + 1:
                    score += 100
                if known.known_max_y is not None and check_y > known.known_max_y - 1:
                    score += 100

            if score < best_score:
                best_score = score
                best_direction = angle

        return best_direction

    except DTaaSError as e:
        log(f"[EXPLORE] Error querying directions: {e}")
        return None


def query_frontier_cells(client: DTaaSClient, world: SimulationWorld) -> list[tuple[int, int]]:
    """Query ontology to find frontier cells (unexplored adjacent to explored).

    Frontier cells are exploration targets - unexplored cells that are
    adjacent to cells we've already visited.
    """
    robot = world.robot
    known = world.known_world

    # Get all explored cells
    explored_query = f"""
PREFIX robo: <{ROBO}>

SELECT DISTINCT ?cellX ?cellY WHERE {{
    <urn:robot:{robot.id}> robo:hasExploredCell ?cell .
    ?cell robo:cellX ?cellX ;
          robo:cellY ?cellY .
}}
"""
    try:
        result = client.twins.sparql_query(TWIN_ID, explored_query)

        explored_cells = set()
        for binding in result.bindings:
            cx = int(binding.get("cellX", {}).get("value", 0))
            cy = int(binding.get("cellY", {}).get("value", 0))
            explored_cells.add((cx, cy))

        # Find frontier cells (unexplored neighbors of explored cells)
        frontier = []
        for (ex, ey) in explored_cells:
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = ex + dx, ey + dy
                if (nx, ny) in explored_cells:
                    continue

                # Check known borders
                if known.known_min_x is not None and nx < known.known_min_x:
                    continue
                if known.known_max_x is not None and nx > known.known_max_x:
                    continue
                if known.known_min_y is not None and ny < known.known_min_y:
                    continue
                if known.known_max_y is not None and ny > known.known_max_y:
                    continue

                if (nx, ny) not in frontier:
                    frontier.append((nx, ny))

        return frontier

    except DTaaSError as e:
        log(f"[EXPLORE] Error querying frontier: {e}")
        return []


def setup_reasoning_rules(client: DTaaSClient):
    """Set up SWRL-style reasoning rules for robot behavior.

    These rules encode the robot's behavioral logic in the ontology,
    rather than in Python code. The rules infer classifications and
    recommended actions based on sensor data.
    """
    # Clean up any existing rules from previous runs to prevent state accumulation
    existing_rule_ids = [
        "robo-collision-stop", "robo-low-battery", "robo-at-object", "robo-near-object",
        "robo-path-blocked", "robo-avoid-right", "robo-avoid-left", "robo-near-obstacle",
        "robo-emergency-avoid", "robo-high-performer", "robo-exploring-mode", "robo-in-loop",
        "robo-stuck-exploring", "robo-physically-stuck", "robo-severely-stuck",
        "robo-in-cluster", "robo-should-disperse", "robo-mild-cluster", "robo-priority-disperse",
        "robo-small-coverage", "robo-high-knottiness", "robo-should-venture", "robo-severely-circling"
    ]
    for rule_id in existing_rule_ids:
        try:
            client.reasoning.delete_rule(rule_id)
        except DTaaSError:
            pass  # Rule doesn't exist, that's fine

    # Also clean up temp reasoning file to prevent stale data
    import glob
    temp_files = glob.glob("/var/folders/*/T/reasoner_*.n3") + glob.glob("/tmp/reasoner_*.n3")
    for f in temp_files:
        try:
            os.remove(f)
        except OSError:
            pass

    rules = [
        # ======================
        # STATE CLASSIFICATION RULES
        # ======================

        # Rule 1: Collision -> Stop
        {
            "id": "robo-collision-stop",
            "name": "Collision Stop Rule",
            "description": "If robot has collision, classify as CollisionState -> must stop",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}hasCollision",
                "operator": "=",
                "value": 1.0,
                "target_class": f"{ROBO}CollisionState"
            }
        },

        # Rule 2: Low battery -> Return home
        {
            "id": "robo-low-battery",
            "name": "Low Battery Rule",
            "description": "If battery below 20%, classify as LowBattery -> should return home",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}batteryLevel",
                "operator": "<",
                "value": 20.0,
                "target_class": f"{ROBO}LowBattery"
            }
        },

        # Rule 3: At object (close enough to collect) -> Can collect
        {
            "id": "robo-at-object",
            "name": "At Object Rule",
            "description": "If distance to nearest < 1.0, classify as AtObject -> can collect",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}distanceToNearest",
                "operator": "<",
                "value": 1.0,
                "target_class": f"{ROBO}AtObject"
            }
        },

        # Rule 4: Near object
        {
            "id": "robo-near-object",
            "name": "Near Object Rule",
            "description": "If distance to nearest < sensor range, classify as NearObject",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}distanceToNearest",
                "operator": "<",
                "value": 3.0,
                "target_class": f"{ROBO}NearObject"
            }
        },

        # ======================
        # OBSTACLE AVOIDANCE RULES
        # ======================

        # Rule 5: Path blocked -> Must avoid
        {
            "id": "robo-path-blocked",
            "name": "Path Blocked Rule",
            "description": "If pathBlocked is true, classify as MustAvoid",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}pathBlocked",
                "operator": "=",
                "value": 1.0,
                "target_class": f"{ROBO}MustAvoid"
            }
        },

        # Rule 6: Obstacle on left -> Avoid right
        {
            "id": "robo-avoid-right",
            "name": "Avoid Right Rule",
            "description": "If obstacle is on left side of path, classify as AvoidRight",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}obstacleOnLeft",
                "operator": "=",
                "value": 1.0,
                "target_class": f"{ROBO}AvoidRight"
            }
        },

        # Rule 7: Obstacle on right -> Avoid left
        {
            "id": "robo-avoid-left",
            "name": "Avoid Left Rule",
            "description": "If obstacle is on right side of path, classify as AvoidLeft",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}obstacleOnRight",
                "operator": "=",
                "value": 1.0,
                "target_class": f"{ROBO}AvoidLeft"
            }
        },

        # Rule 8: Near obstacle -> Caution mode
        {
            "id": "robo-near-obstacle",
            "name": "Near Obstacle Rule",
            "description": "If distance to obstacle < 1.5, classify as NearObstacle",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}distanceToObstacle",
                "operator": "<",
                "value": 1.5,
                "target_class": f"{ROBO}NearObstacle"
            }
        },

        # Rule 9: Very near obstacle -> Emergency avoid
        {
            "id": "robo-emergency-avoid",
            "name": "Emergency Avoid Rule",
            "description": "If distance to obstacle < 0.8, classify as EmergencyAvoid",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}distanceToObstacle",
                "operator": "<",
                "value": 0.8,
                "target_class": f"{ROBO}EmergencyAvoid"
            }
        },

        # ======================
        # PERFORMANCE RULES
        # ======================

        # Rule 10: High performer
        {
            "id": "robo-high-performer",
            "name": "High Performer Rule",
            "description": "If success metric > 100, classify as HighPerformer",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}successMetric",
                "operator": ">",
                "value": 100.0,
                "target_class": f"{ROBO}HighPerformer"
            }
        },

        # ======================
        # EXPLORATION & LOOP DETECTION RULES
        # ======================

        # Rule 11: Exploring mode - no known objects
        {
            "id": "robo-exploring-mode",
            "name": "Exploring Mode Rule",
            "description": "If knownObjects = 0 and isExploring = true, classify as ExploringMode",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}isExploring",
                "operator": "=",
                "value": 1.0,
                "target_class": f"{ROBO}ExploringMode"
            }
        },

        # Rule 12: In loop - detected via ontology position history
        {
            "id": "robo-in-loop",
            "name": "In Loop Rule",
            "description": "If inLoop = true, classify as InLoop (needs to break pattern)",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}inLoop",
                "operator": "=",
                "value": 1.0,
                "target_class": f"{ROBO}InLoop"
            }
        },

        # Rule 13: Stuck exploring - in loop for extended time
        {
            "id": "robo-stuck-exploring",
            "name": "Stuck Exploring Rule",
            "description": "If stuckCounter > 5, classify as StuckExploring (needs random direction)",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}stuckCounter",
                "operator": ">",
                "value": 5.0,
                "target_class": f"{ROBO}StuckExploring"
            }
        },

        # Rule 14: Physically stuck - no movement for several ticks
        {
            "id": "robo-physically-stuck",
            "name": "Physically Stuck Rule",
            "description": "If ticksWithoutMovement >= 3, classify as StuckState (needs escape)",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}ticksWithoutMovement",
                "operator": ">=",
                "value": 3.0,
                "target_class": f"{ROBO}StuckState"
            }
        },

        # Rule 15: Severely stuck - needs aggressive escape
        {
            "id": "robo-severely-stuck",
            "name": "Severely Stuck Rule",
            "description": "If ticksWithoutMovement >= 6, classify as EscapingState (needs random direction)",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}ticksWithoutMovement",
                "operator": ">=",
                "value": 6.0,
                "target_class": f"{ROBO}EscapingState"
            }
        },

        # ======================
        # GEOMETRIC STUCK DETECTION & VENTURE RULES
        # ======================
        # These rules use coverage area and path knottiness to detect when
        # robots are circling in a small area and should venture outward

        # Rule 16: Small coverage area -> Should venture (move to unexplored area)
        {
            "id": "robo-small-coverage",
            "name": "Small Coverage Area Rule",
            "description": "If coverageArea < 15 with enough positions, robot is circling and should venture",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}coverageArea",
                "operator": "<",
                "value": 15.0,
                "target_class": f"{ROBO}SmallCoverage"
            }
        },

        # Rule 17: High knottiness -> Circling behavior detected
        {
            "id": "robo-high-knottiness",
            "name": "High Knottiness Rule",
            "description": "If pathKnottiness > 10 (lots of turning), classify as CirclingBehavior",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}pathKnottiness",
                "operator": ">",
                "value": 10.0,
                "target_class": f"{ROBO}CirclingBehavior"
            }
        },

        # Rule 18: Should venture - small coverage with sufficient history
        {
            "id": "robo-should-venture",
            "name": "Should Venture Rule",
            "description": "If recentPositionCount >= 15 and coverageArea < 20, should venture to new area",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}recentPositionCount",
                "operator": ">=",
                "value": 15.0,
                "target_class": f"{ROBO}ShouldVenture"
            }
        },

        # Rule 19: Severely circling - needs immediate dispersion
        {
            "id": "robo-severely-circling",
            "name": "Severely Circling Rule",
            "description": "If coverageArea < 8 with high knottiness, needs aggressive venture",
            "rule": {
                "type": "threshold",
                "property": f"{ROBO}coverageArea",
                "operator": "<",
                "value": 8.0,
                "target_class": f"{ROBO}SeverelyCircling"
            }
        },

        # ======================
        # CLUSTER AVOIDANCE RULES (temporarily disabled - may cause reasoning loop)
        # ======================
        # These rules are disabled pending investigation of server CPU spike
        # TODO: Re-enable once reasoning performance is fixed

        # # Rule 16: In cluster - multiple robots nearby
        # {
        #     "id": "robo-in-cluster",
        #     "name": "In Cluster Rule",
        #     "description": "If nearbyRobotCount >= 2, classify as InCluster",
        #     "rule": {
        #         "type": "threshold",
        #         "property": f"{ROBO}nearbyRobotCount",
        #         "operator": ">=",
        #         "value": 2.0,
        #         "target_class": f"{ROBO}InCluster"
        #     }
        # },

        # # Rule 17: Should disperse - clustered too long
        # {
        #     "id": "robo-should-disperse",
        #     "name": "Should Disperse Rule",
        #     "description": "If ticksInCluster >= dispersionThreshold, classify as ShouldDisperse",
        #     "rule": {
        #         "type": "threshold",
        #         "property": f"{ROBO}ticksInCluster",
        #         "operator": ">=",
        #         "value": 4.0,  # Base threshold, adjusted by robot priority
        #         "target_class": f"{ROBO}ShouldDisperse"
        #     }
        # },

        # # Rule 18: Mild cluster - one robot nearby (for target deconfliction)
        # {
        #     "id": "robo-mild-cluster",
        #     "name": "Mild Cluster Rule",
        #     "description": "If nearbyRobotCount >= 1, classify as MildCluster",
        #     "rule": {
        #         "type": "threshold",
        #         "property": f"{ROBO}nearbyRobotCount",
        #         "operator": ">=",
        #         "value": 1.0,
        #         "target_class": f"{ROBO}MildCluster"
        #     }
        # },

        # # Rule 19: Priority disperse - lower priority robots disperse first
        # {
        #     "id": "robo-priority-disperse",
        #     "name": "Priority Disperse Rule",
        #     "description": "If shouldDisperse and robotPriority > 2, classify as PriorityDisperse",
        #     "rule": {
        #         "type": "threshold",
        #         "property": f"{ROBO}robotPriority",
        #         "operator": ">",
        #         "value": 2.0,  # Higher index = disperse sooner
        #         "target_class": f"{ROBO}PriorityDisperse"
        #     }
        # },
    ]

    log("\n[RULES] Setting up reasoning rules...")
    for rule_data in rules:
        try:
            client.reasoning.create_rule(rule_data)
            log(f"  [OK] {rule_data['id']}: {rule_data['name']}")
        except DTaaSError as e:
            if "already exists" in str(e).lower():
                log(f"  [EXISTS] {rule_data['id']}")
            else:
                log(f"  [FAIL] {rule_data['id']}: {e}")


def run_reasoning(client: DTaaSClient) -> dict:
    """Run reasoning to determine next action (REASON phase)."""
    try:
        result = client.reasoning.execute_rules(TWIN_ID)
        return {
            "rules_executed": result.rules_executed,
            "inferred_triples": result.inferred_triples,
            "iterations": result.iterations
        }
    except DTaaSError as e:
        log(f"[REASON] Error: {e}")
        return {"rules_executed": [], "inferred_triples": 0, "iterations": 0}


def query_robot_state(client: DTaaSClient, robot: Robot = None) -> dict:
    """Query current robot state from ontology via SPARQL (QUERY phase).

    This queries both raw sensor data and inferred classifications from reasoning rules.
    The inferred states drive the robot's behavior decisions, including exploration
    and loop detection states from the ontology's position memory.
    """
    robot_id = robot.id if robot else "robot1"
    robot_uri = f"<urn:robot:{robot_id}>"

    query = f"""
PREFIX robo: <{ROBO}>

SELECT ?collision ?battery ?nearObj ?atObj ?lowBat ?highPerf ?collected ?total
       ?distance ?metric ?distNearest ?distObs ?clearAngle
       ?mustAvoid ?avoidLeft ?avoidRight ?nearObs ?emergencyAvoid
       ?isExploring ?inLoop ?stuckCounter ?knownObjects
       ?nearbyRobotCount ?ticksInCluster ?dispersionHeading ?robotPriority
       ?inCluster ?shouldDisperse ?mildCluster ?priorityDisperse
       ?coverageArea ?pathKnottiness ?recentPositionCount
       ?smallCoverage ?circlingBehavior ?shouldVenture ?severelyCircling
WHERE {{
    {robot_uri} a robo:Robot .
    OPTIONAL {{ {robot_uri} robo:hasCollision ?collision }}
    OPTIONAL {{ {robot_uri} robo:batteryLevel ?battery }}
    OPTIONAL {{ {robot_uri} robo:objectsCollected ?collected }}
    OPTIONAL {{ {robot_uri} robo:totalObjects ?total }}
    OPTIONAL {{ {robot_uri} robo:distanceTraveled ?distance }}
    OPTIONAL {{ {robot_uri} robo:successMetric ?metric }}
    OPTIONAL {{ {robot_uri} robo:distanceToNearest ?distNearest }}
    OPTIONAL {{ {robot_uri} robo:distanceToObstacle ?distObs }}
    OPTIONAL {{ {robot_uri} robo:clearPathAngle ?clearAngle }}

    # Exploration and loop detection state from ontology
    OPTIONAL {{ {robot_uri} robo:isExploring ?isExploring }}
    OPTIONAL {{ {robot_uri} robo:inLoop ?inLoop }}
    OPTIONAL {{ {robot_uri} robo:stuckCounter ?stuckCounter }}
    OPTIONAL {{ {robot_uri} robo:knownObjects ?knownObjects }}

    # Cluster avoidance state from ontology
    OPTIONAL {{ {robot_uri} robo:nearbyRobotCount ?nearbyRobotCount }}
    OPTIONAL {{ {robot_uri} robo:ticksInCluster ?ticksInCluster }}
    OPTIONAL {{ {robot_uri} robo:dispersionHeading ?dispersionHeading }}
    OPTIONAL {{ {robot_uri} robo:robotPriority ?robotPriority }}

    # Check inferred states from reasoning rules
    BIND(EXISTS {{ {robot_uri} a robo:NearObject }} AS ?nearObj)
    BIND(EXISTS {{ {robot_uri} a robo:AtObject }} AS ?atObj)
    BIND(EXISTS {{ {robot_uri} a robo:LowBattery }} AS ?lowBat)
    BIND(EXISTS {{ {robot_uri} a robo:HighPerformer }} AS ?highPerf)

    # Obstacle avoidance inferences from rules
    BIND(EXISTS {{ {robot_uri} a robo:MustAvoid }} AS ?mustAvoid)
    BIND(EXISTS {{ {robot_uri} a robo:AvoidLeft }} AS ?avoidLeft)
    BIND(EXISTS {{ {robot_uri} a robo:AvoidRight }} AS ?avoidRight)
    BIND(EXISTS {{ {robot_uri} a robo:NearObstacle }} AS ?nearObs)
    BIND(EXISTS {{ {robot_uri} a robo:EmergencyAvoid }} AS ?emergencyAvoid)

    # Cluster avoidance inferences from rules
    BIND(EXISTS {{ {robot_uri} a robo:InCluster }} AS ?inCluster)
    BIND(EXISTS {{ {robot_uri} a robo:ShouldDisperse }} AS ?shouldDisperse)
    BIND(EXISTS {{ {robot_uri} a robo:MildCluster }} AS ?mildCluster)
    BIND(EXISTS {{ {robot_uri} a robo:PriorityDisperse }} AS ?priorityDisperse)

    # Geometric metrics for venture detection (from ontology)
    OPTIONAL {{ {robot_uri} robo:coverageArea ?coverageArea }}
    OPTIONAL {{ {robot_uri} robo:pathKnottiness ?pathKnottiness }}
    OPTIONAL {{ {robot_uri} robo:recentPositionCount ?recentPositionCount }}

    # Venture behavior inferences from SWRL rules
    BIND(EXISTS {{ {robot_uri} a robo:SmallCoverage }} AS ?smallCoverage)
    BIND(EXISTS {{ {robot_uri} a robo:CirclingBehavior }} AS ?circlingBehavior)
    BIND(EXISTS {{ {robot_uri} a robo:ShouldVenture }} AS ?shouldVenture)
    BIND(EXISTS {{ {robot_uri} a robo:SeverelyCircling }} AS ?severelyCircling)
}}
LIMIT 1
"""

    try:
        # Use twin-specific query endpoint to query data in the twin's graph
        result = client.twins.sparql_query(TWIN_ID, query)
        if not result.bindings:
            log(f"[QUERY] No bindings returned for {robot_id}")
            return {}
        b = result.bindings[0]
        return {
                # Raw sensor data
                "collision": b.get("collision", {}).get("value", "false") == "true",
                "battery": float(b.get("battery", {}).get("value", 100)),
                "collected": int(b.get("collected", {}).get("value", 0)),
                "total": int(b.get("total", {}).get("value", 0)),
                "distance": float(b.get("distance", {}).get("value", 0)),
                "metric": float(b.get("metric", {}).get("value", 0)),
                "distanceToNearest": float(b.get("distNearest", {}).get("value", 999)),
                "distanceToObstacle": float(b.get("distObs", {}).get("value", 999)),
                "clearPathAngle": float(b.get("clearAngle", {}).get("value", 0)),

                # Inferred states from ontology rules
                "nearObject": b.get("nearObj", {}).get("value", "false") == "true",
                "atObject": b.get("atObj", {}).get("value", "false") == "true",
                "lowBattery": b.get("lowBat", {}).get("value", "false") == "true",
                "highPerformer": b.get("highPerf", {}).get("value", "false") == "true",

                # Obstacle avoidance inferences (from ontology rules)
                "mustAvoid": b.get("mustAvoid", {}).get("value", "false") == "true",
                "avoidLeft": b.get("avoidLeft", {}).get("value", "false") == "true",
                "avoidRight": b.get("avoidRight", {}).get("value", "false") == "true",
                "nearObstacle": b.get("nearObs", {}).get("value", "false") == "true",
                "emergencyAvoid": b.get("emergencyAvoid", {}).get("value", "false") == "true",

                # Exploration and loop state from ontology (position memory)
                "isExploring": b.get("isExploring", {}).get("value", "false") == "true",
                "inLoop": b.get("inLoop", {}).get("value", "false") == "true",
                "stuckCounter": int(b.get("stuckCounter", {}).get("value", 0)),
                "knownObjects": int(b.get("knownObjects", {}).get("value", 0)),

                # Cluster avoidance state from ontology
                "nearbyRobotCount": int(b.get("nearbyRobotCount", {}).get("value", 0)),
                "ticksInCluster": int(b.get("ticksInCluster", {}).get("value", 0)),
                "dispersionHeading": float(b.get("dispersionHeading", {}).get("value", 0)),
                "robotPriority": int(b.get("robotPriority", {}).get("value", 0)),

                # Cluster avoidance inferences from rules
                "inCluster": b.get("inCluster", {}).get("value", "false") == "true",
                "shouldDisperse": b.get("shouldDisperse", {}).get("value", "false") == "true",
                "mildCluster": b.get("mildCluster", {}).get("value", "false") == "true",
                "priorityDisperse": b.get("priorityDisperse", {}).get("value", "false") == "true",

                # Geometric metrics for venture detection
                "coverageArea": float(b.get("coverageArea", {}).get("value", 0)),
                "pathKnottiness": float(b.get("pathKnottiness", {}).get("value", 0)),
                "recentPositionCount": int(b.get("recentPositionCount", {}).get("value", 0)),

                # Venture behavior inferences from SWRL rules
                "smallCoverage": b.get("smallCoverage", {}).get("value", "false") == "true",
                "circlingBehavior": b.get("circlingBehavior", {}).get("value", "false") == "true",
                "shouldVenture": b.get("shouldVenture", {}).get("value", "false") == "true",
                "severelyCircling": b.get("severelyCircling", {}).get("value", "false") == "true",
            }
    except DTaaSError as e:
        log(f"[QUERY] Error querying {robot_id}: {e}")
    except Exception as e:
        log(f"[QUERY] Parse error for {robot_id}: {e}")
        import traceback
        traceback.print_exc()

    return {}


def determine_action(client: DTaaSClient, world: SimulationWorld, state: dict, robot: Robot = None) -> tuple[str, Optional[Position], dict]:
    """Determine next action based on ontology-inferred state and partial observability.

    The action is derived from classifications inferred by reasoning rules,
    not from Python logic. This function translates ontology states to actions.

    Loop Detection and Exploration:
    - Loop state is queried from ontology (state["inLoop"], state["stuckCounter"])
    - When in a loop, use ontology-based direction query to break the pattern
    - Frontier cells and visit counts are computed via SPARQL

    Partial Observability:
    - The robot can only target KNOWN (discovered) objects
    - If no known objects remain, the robot explores to discover more
    - Exploration continues until all objects are found and collected

    Returns:
        tuple: (action_name, target_position, avoidance_info)
    """
    if robot is None:
        robot = world.robot  # Backward compatibility
    known = world.known_worlds.get(robot.id, world.known_world)

    # Avoidance info from ontology (with fallback to local computation)
    avoidance = {
        "mustAvoid": state.get("mustAvoid", False),
        "avoidLeft": state.get("avoidLeft", False),
        "avoidRight": state.get("avoidRight", False),
        "clearPathAngle": state.get("clearPathAngle", 0),
        "emergencyAvoid": state.get("emergencyAvoid", False),
        # Include loop info for execute_action
        "inLoop": state.get("inLoop", False),
        "stuckCounter": state.get("stuckCounter", 0),
    }

    # Priority 1: Handle collision - but don't stop permanently!
    # In multi-robot competition, collisions are penalties, not game-overs
    if state.get("collision", False) or robot.has_collision or robot.has_robot_collision:
        # Clear the collision flags so robot can continue
        robot.has_collision = False
        robot.has_robot_collision = False
        # Robot will just explore in a different direction instead of stopping
        # The collision has already been counted in collision_count/robot_collision_count

    # Priority 2: LowBattery -> Return home (check both ontology AND local)
    # Threshold from ontology config
    if state.get("lowBattery", False) or robot.battery < get_behavior_config().detection.low_battery_threshold:
        return "ReturnHome", world.home_position, avoidance

    # Priority 3: AtObject -> Collect (check both ontology AND local)
    pickup = world.check_object_pickup(robot)
    if state.get("atObject", False) or pickup:
        if pickup:
            # Reset cluster counter when collecting - productive action
            robot.ticks_in_cluster = 0
            return "Collect", pickup.position, avoidance

    # Priority 4: CLUSTER DISPERSION (ONTOLOGY-DRIVEN)
    # The ontology contains:
    #   - nearbyRobotCount: number of robots within cluster radius
    #   - ticksInCluster: how long robot has been clustered
    #   - dispersionHeading: pre-calculated direction away from cluster centroid
    #   - Inferred classes: InCluster, ShouldDisperse, PriorityDisperse
    #
    # SWRL rules infer when robot should disperse based on cluster state
    if state.get("shouldDisperse", False) or state.get("priorityDisperse", False):
        # Use dispersion heading from ontology (calculated during sense phase)
        dispersion_heading = state.get("dispersionHeading", robot.heading)
        ticks_in_cluster = state.get("ticksInCluster", 0)
        nearby_count = state.get("nearbyRobotCount", 0)

        # Create target position in dispersion direction
        disperse_dist = 5.0  # Move 5 units away from cluster
        target_x = robot.position.x + disperse_dist * math.cos(math.radians(dispersion_heading))
        target_y = robot.position.y + disperse_dist * math.sin(math.radians(dispersion_heading))

        # Clamp to world bounds
        target_x = max(1, min(world.width - 1, target_x))
        target_y = max(1, min(world.height - 1, target_y))

        avoidance["disperseMode"] = True
        avoidance["ticksInCluster"] = ticks_in_cluster
        avoidance["nearbyRobots"] = nearby_count

        log(f"[{robot.id}] CLUSTER DISPERSION (ontology): {nearby_count} nearby, heading={dispersion_heading:.1f}°, ticks={ticks_in_cluster}")

        return "Explore", Position(target_x, target_y), avoidance

    # Priority 5: ESCAPE MODE (ONTOLOGY-DRIVEN) - Persistent escape from clutter
    # This is a committed escape that persists for multiple ticks until the robot
    # reaches a safe distance from the clutter centroid. Once triggered, the robot
    # ignores pheromones and known objects until escape is complete.
    #
    # The ontology infers when escape is needed based on geometric metrics:
    #   - coverageArea < 15: SmallCoverage (circling in tight area)
    #   - pathKnottiness > 10: CirclingBehavior (lots of turning)
    #   - recentPositionCount >= 15: ShouldVenture (enough history to judge)
    #   - coverageArea < 8: SeverelyCircling (urgent escape needed)
    import random

    # Check if already in escape mode - CONTINUE until complete
    if known.escape_mode and known.escape_target:
        target_x, target_y = known.escape_target
        dist_to_target = math.sqrt((robot.position.x - target_x)**2 + (robot.position.y - target_y)**2)

        # Check if we've escaped far enough from the clutter centroid
        if known.clutter_centroid:
            cx, cy = known.clutter_centroid
            dist_from_clutter = math.sqrt((robot.position.x - cx)**2 + (robot.position.y - cy)**2)
        else:
            dist_from_clutter = 999

        # Exit escape mode if: reached target OR far enough from clutter OR timed out
        if dist_to_target < 2.0 or dist_from_clutter > 12.0 or known.escape_ticks_remaining <= 0:
            log(f"[{robot.id}] ESCAPE COMPLETE: dist_to_target={dist_to_target:.1f}, dist_from_clutter={dist_from_clutter:.1f}")
            known.escape_mode = False
            known.escape_target = None
            known.escape_ticks_remaining = 0
            known.clutter_centroid = None
            # Clear position history for fresh metrics
            known.recent_positions.clear()
            known.coverage_area = 0.0
            known.path_knottiness = 0.0
        else:
            # Continue escaping - decrement counter
            known.escape_ticks_remaining -= 1
            avoidance["escapeMode"] = True
            avoidance["escapeTicks"] = known.escape_ticks_remaining

            log(f"[{robot.id}] ESCAPING: ticks_left={known.escape_ticks_remaining}, dist_to_target={dist_to_target:.1f}, dist_from_clutter={dist_from_clutter:.1f}")

            return "Explore", Position(target_x, target_y), avoidance

    # Check if we should ENTER escape mode (from ontology or local metrics)
    should_escape = state.get("shouldVenture", False) or state.get("severelyCircling", False)
    small_coverage = state.get("smallCoverage", False)
    coverage_area = state.get("coverageArea", 0)

    # Also check local Python metrics as fallback
    if not should_escape and known.coverage_area > 0 and known.coverage_area < 15 and len(known.recent_positions) >= 15:
        should_escape = True
        small_coverage = True

    if should_escape or small_coverage:
        # ENTER ESCAPE MODE - Calculate clutter centroid and escape target

        # Find the centroid of recent positions (the "clutter center")
        if known.recent_positions:
            cx = sum(p[0] for p in known.recent_positions) / len(known.recent_positions)
            cy = sum(p[1] for p in known.recent_positions) / len(known.recent_positions)
        else:
            cx, cy = robot.position.x, robot.position.y

        known.clutter_centroid = (cx, cy)

        # Pick a RANDOM direction away from centroid with more variance
        base_angle = math.atan2(robot.position.y - cy, robot.position.x - cx)
        # Add significant randomness - can go 90 degrees either way from "away"
        escape_angle = base_angle + random.uniform(-math.pi/2, math.pi/2)

        # Escape distance - go FAR to really escape (at least 12 cells or 1/3 world)
        escape_dist = max(12.0, min(world.width, world.height) / 3)

        target_x = robot.position.x + escape_dist * math.cos(escape_angle)
        target_y = robot.position.y + escape_dist * math.sin(escape_angle)

        # Clamp to world bounds with margin
        target_x = max(3, min(world.width - 3, target_x))
        target_y = max(3, min(world.height - 3, target_y))

        # Set escape mode state
        known.escape_mode = True
        known.escape_target = (target_x, target_y)
        known.escape_ticks_remaining = 25  # Persist for up to 25 ticks

        avoidance["escapeMode"] = True
        avoidance["coverageArea"] = coverage_area

        log(f"[{robot.id}] ESCAPE START (ontology): area={coverage_area:.1f}, target=({target_x:.1f},{target_y:.1f}), away from clutter ({cx:.1f},{cy:.1f})")

        return "Explore", Position(target_x, target_y), avoidance

    # Priority 6: Move to nearest KNOWN uncollected object
    nearest_known = known.get_nearest_known_object(robot.position)
    if nearest_known:
        # Check for mild cluster - ontology infers MildCluster when 1+ robots nearby
        # Use target deconfliction: yield to lower-indexed robots
        if state.get("mildCluster", False):
            nearby_robots = world.get_nearby_robots(robot, radius=4.0)
            for other in nearby_robots:
                other_dist = other.position.distance_to(nearest_known.position)
                my_dist = robot.position.distance_to(nearest_known.position)
                # If another robot is closer and has lower index (priority), find alternate
                if other_dist < my_dist and other.robot_index < robot.robot_index:
                    # Try to find a different object
                    alternate = known.get_second_nearest_object(robot.position, exclude=nearest_known)
                    if alternate:
                        log(f"[{robot.id}] TARGET DECONFLICT (ontology): yielding {nearest_known.id} to {other.id}, targeting {alternate.id}")
                        return "MoveToObject", alternate.position, avoidance
                    break  # No alternate, just go for it

        return "MoveToObject", nearest_known.position, avoidance

    # Priority 7: No known objects - EXPLORE to discover more
    # Check if there are still uncollected objects in the world (robot doesn't know)
    actual_remaining = len(world.get_uncollected_objects())
    if actual_remaining > 0:
        # Get loop state from ontology
        in_loop = state.get("inLoop", False)
        stuck_counter = state.get("stuckCounter", 0)

        # === STUCK ESCAPE LOGIC ===
        # If robot is physically stuck (no movement for several ticks), use escape direction
        if robot.is_stuck:
            import random
            # Use escape heading calculated from pheromone avoidance
            if robot.escape_heading is not None:
                explore_heading = robot.escape_heading
            else:
                # Generate escape direction away from current heading
                explore_heading = robot.get_escape_direction(robot.heading)

            # If stuck for too long, become more aggressive with randomness
            if robot.ticks_without_movement > 6:
                explore_heading = random.uniform(0, 360)
                robot.escape_heading = explore_heading

            # Add escape status to avoidance dict for logging
            avoidance["escapeMode"] = True
            avoidance["ticksStuck"] = robot.ticks_without_movement

            log(f"[{robot.id}] STUCK ESCAPE: heading={explore_heading:.1f}°, stuck_ticks={robot.ticks_without_movement}")

        # === VENTURE OUT MODE ===
        # If robot hasn't found anything for a while, venture to new areas
        elif robot.needs_venture_out():
            explore_heading = robot.get_venture_direction(
                robot.position.x, robot.position.y,
                world.width, world.height,
                known.explored_positions
            )
            avoidance["ventureMode"] = True
            avoidance["wanderlust"] = robot.wanderlust
            avoidance["ticksSinceDiscovery"] = robot.ticks_since_discovery

            log(f"[{robot.id}] VENTURE OUT: heading={explore_heading:.1f}°, wanderlust={robot.wanderlust:.1f}, no_discovery={robot.ticks_since_discovery}")

        # Determine exploration direction using ontology queries
        elif in_loop:
            # Query ontology for least-visited direction to break the loop
            explore_heading = query_least_visited_direction(client, world)
            if explore_heading is None:
                explore_heading = world.get_exploration_direction(robot)

            # If very stuck, add randomness
            if stuck_counter > 5:
                import random
                explore_heading = random.uniform(0, 360)
        else:
            # Normal exploration - try frontier-based first
            frontier = query_frontier_cells(client, world)
            if frontier:
                # Head toward nearest frontier cell
                nearest_frontier = min(frontier,
                                       key=lambda c: math.sqrt((c[0] - robot.position.x)**2 +
                                                              (c[1] - robot.position.y)**2))
                dx = nearest_frontier[0] - robot.position.x
                dy = nearest_frontier[1] - robot.position.y
                explore_heading = math.degrees(math.atan2(dy, dx))
            else:
                # Fallback to standard exploration
                explore_heading = world.get_exploration_direction(robot)

        return "Explore", Position(
            robot.position.x + math.cos(math.radians(explore_heading)) * 5,
            robot.position.y + math.sin(math.radians(explore_heading)) * 5
        ), avoidance

    # Priority 6: All objects collected - return home
    return "ReturnHome", world.home_position, avoidance


def execute_action(world: SimulationWorld, action: str, target: Optional[Position], avoidance: dict, robot: Robot = None):
    """Execute the decided action (ACT phase).

    The avoidance behavior is determined by ontology rules:
    - mustAvoid: True if path is blocked (inferred by robo-path-blocked rule)
    - avoidLeft/avoidRight: Which direction to go (inferred by robo-avoid-left/right rules)
    - clearPathAngle: Specific angle offset to use (from ontology data)
    """
    if robot is None:
        robot = world.robot  # Backward compatibility

    if action == "Stop":
        robot.is_active = False
        robot.current_action = "Stopped (Collision)"

    elif action == "Collect":
        obj = world.check_object_pickup(robot)
        if obj:
            # Use collect_object for multi-robot race condition handling
            if world.collect_object(robot, obj):
                robot.current_action = f"Collected {obj.id} (+{obj.value:.1f})"
                # Deposit OBJECT_COLLECTED pheromone - tells others "nothing here anymore"
                world.deposit_pheromone(robot, PheromoneType.OBJECT_COLLECTED)
            else:
                robot.current_action = f"Object {obj.id} was taken by another robot"

    elif action == "MoveToObject" and target:
        dist_to_target = robot.position.distance_to(target)

        # When very close to target, go direct - don't let avoidance cause oscillation
        if dist_to_target < 2.0:
            world.move_robot_direct(target, robot=robot)
            robot.current_action = f"Approaching {target} (dist: {dist_to_target:.1f})"
        elif avoidance.get("mustAvoid"):
            clear_angle = avoidance.get("clearPathAngle", 0)
            direction = "left" if avoidance.get("avoidLeft") else "right"
            world.move_robot_with_avoidance(target, clear_angle, robot=robot)
            robot.current_action = f"Avoiding {direction} (angle {clear_angle:.0f}°) toward target"
        else:
            world.move_robot_direct(target, robot=robot)
            robot.current_action = f"Moving to {target}"

    elif action == "ReturnHome" and target:
        # Use ontology-inferred avoidance behavior
        if avoidance.get("mustAvoid"):
            clear_angle = avoidance.get("clearPathAngle", 0)
            direction = "left" if avoidance.get("avoidLeft") else "right"
            world.move_robot_with_avoidance(target, clear_angle, robot=robot)
            robot.current_action = f"Avoiding {direction}, returning home"
        else:
            world.move_robot_direct(target, robot=robot)
            dist = robot.position.distance_to(target)
            if dist < 0.5:
                robot.current_action = "At home"
            else:
                robot.current_action = f"Returning home ({dist:.1f} away)"

    elif action == "Explore":
        # Exploration mode - no known objects, need to discover more
        # Check if we have a specific target from venture/escape mode
        venture_mode = avoidance.get("ventureMode", False)
        escape_mode = avoidance.get("escapeMode", False)

        if (venture_mode or escape_mode) and target:
            # Use the heading toward the target set by determine_action
            dx = target.x - robot.position.x
            dy = target.y - robot.position.y
            explore_heading = math.degrees(math.atan2(dy, dx))
        else:
            # Standard exploration - use local exploration direction
            explore_heading = world.get_exploration_direction(robot)

        old_pos = Position(robot.position.x, robot.position.y)
        world.move_robot_explore(explore_heading, robot=robot)

        # Deposit exploration pheromone if we moved
        if robot.position.distance_to(old_pos) > 0.1:
            # Only deposit every few ticks to avoid flooding
            if world.current_tick % PHEROMONE_CONFIG[PheromoneType.EXPLORATION]["deposit_interval"] == 0:
                world.deposit_pheromone(robot, PheromoneType.EXPLORATION)

        known = world.known_worlds.get(robot.id, world.known_world)
        borders_known = sum([
            known.known_min_x is not None,
            known.known_max_x is not None,
            known.known_min_y is not None,
            known.known_max_y is not None
        ])

        # Show status from ontology state (via avoidance dict)
        in_loop = avoidance.get("inLoop", False)
        stuck_counter = avoidance.get("stuckCounter", 0)
        escape_mode = avoidance.get("escapeMode", False)
        escape_ticks = avoidance.get("escapeTicks", 0)
        coverage_area = avoidance.get("coverageArea", 0)

        if escape_mode:
            # Persistent escape from clutter - ontology-driven
            robot.current_action = f"ESCAPE ({explore_heading:.0f}°), area={coverage_area:.1f}, ticks={escape_ticks} [ontology]"
        elif in_loop:
            robot.current_action = f"LOOP BREAK ({explore_heading:.0f}°), stuck={stuck_counter} [ontology]"
        else:
            robot.current_action = f"Exploring ({explore_heading:.0f}°), {borders_known}/4 borders"

    else:
        robot.current_action = "Idle"

    # Deposit danger pheromone on collision
    if robot.has_collision or robot.has_robot_collision:
        world.deposit_pheromone(robot, PheromoneType.DANGER)

    # Deposit stuck pheromone when stuck - warns others to avoid this area
    if robot.is_stuck:
        world.deposit_pheromone(robot, PheromoneType.DANGER)


def update_stuck_state_in_ontology(client: DTaaSClient, robot: Robot, world: SimulationWorld):
    """Update the robot's stuck state in the ontology for reasoning."""
    robot_uri = f"<urn:robot:{robot.id}>"

    # Update stuck state properties
    sparql = f"""
    PREFIX robo: <{ROBO}>
    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

    DELETE {{
        {robot_uri} robo:isStuck ?oldStuck .
        {robot_uri} robo:ticksWithoutMovement ?oldTicks .
        {robot_uri} robo:escapeHeading ?oldEscape .
    }}
    INSERT {{
        {robot_uri} robo:isStuck "true"^^xsd:boolean .
        {robot_uri} robo:ticksWithoutMovement "{robot.ticks_without_movement}"^^xsd:integer .
        {robot_uri} robo:escapeHeading "{robot.escape_heading or 0.0}"^^xsd:float .
        {robot_uri} a robo:StuckState .
    }}
    WHERE {{
        OPTIONAL {{ {robot_uri} robo:isStuck ?oldStuck }}
        OPTIONAL {{ {robot_uri} robo:ticksWithoutMovement ?oldTicks }}
        OPTIONAL {{ {robot_uri} robo:escapeHeading ?oldEscape }}
    }}
    """
    try:
        client.sparql_update(sparql)
    except Exception as e:
        log(f"[WARN] Failed to update stuck state: {e}")

    # Query nearby pheromones to find escape direction away from explored areas
    nearby = world.sense_pheromones(robot)
    exploration_pheromones = nearby.get(PheromoneType.EXPLORATION, [])
    danger_pheromones = nearby.get(PheromoneType.DANGER, [])

    # Calculate direction AWAY from pheromone concentrations
    if exploration_pheromones or danger_pheromones:
        all_repel = exploration_pheromones + danger_pheromones
        # Calculate centroid of pheromones to avoid
        total_weight = 0.0
        weighted_x = 0.0
        weighted_y = 0.0

        for p in all_repel:
            weighted_x += p.position.x * p.strength
            weighted_y += p.position.y * p.strength
            total_weight += p.strength

        if total_weight > 0.1:
            centroid_x = weighted_x / total_weight
            centroid_y = weighted_y / total_weight

            # Direction AWAY from centroid (opposite of gradient)
            dx = robot.position.x - centroid_x
            dy = robot.position.y - centroid_y

            if abs(dx) > 0.1 or abs(dy) > 0.1:
                escape_away = math.degrees(math.atan2(dy, dx))
                # Add some randomness to prevent getting stuck in patterns
                import random
                robot.escape_heading = (escape_away + random.uniform(-30, 30)) % 360


def update_metrics_in_ontology(_client: DTaaSClient, _world: SimulationWorld, _robot: Robot = None):
    """Update metrics in twin properties after action."""
    # Metrics are already updated in update_sensor_data(), so this is now a no-op
    # Keeping the function for structure clarity in the simulation loop
    pass


# =============================================================================
# VISUALIZATION
# =============================================================================

# ANSI escape codes for terminal animation
CLEAR_SCREEN = "\033[2J"
CURSOR_HOME = "\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


def build_world_visualization(world: SimulationWorld, scale: int = 1, fog_of_war: bool = True) -> list[str]:
    """Build ASCII visualization of the world with fog of war.

    With fog_of_war=True (default):
    - '?' = unexplored area (not yet seen by any robot's sensors)
    - '.' = explored empty area
    - 'O' = discovered uncollected object
    - '#' = discovered obstacle
    - 'o' = undiscovered object (hidden, shown as '?' in fog mode)
    - 'x' = undiscovered obstacle (hidden, shown as '?' in fog mode)
    - Robot symbols (R, B, G, Y, etc.) for each robot

    With fog_of_war=False: shows complete world state (god mode / debug).
    """
    width = world.width // scale
    height = world.height // scale

    # Initialize grid - '?' for unexplored, '.' for explored
    grid = [['?' for _ in range(width)] for _ in range(height)]

    # Combine explored positions from all robots for fog-of-war
    all_explored = set()
    all_discovered_objects = {}
    all_discovered_obstacles = {}
    max_sensor_range = 5.0

    for robot in world.robots:
        known = world.known_worlds.get(robot.id)
        if known:
            all_explored.update(known.explored_positions)
            all_discovered_objects.update(known.discovered_objects)
            all_discovered_obstacles.update(known.discovered_obstacles)
            max_sensor_range = max(max_sensor_range, robot.sensor_range)

    # Mark explored positions (cells any robot has been near enough to see)
    for (ex, ey) in all_explored:
        if 0 <= ex < width and 0 <= ey < height:
            grid[ey][ex] = '.'
        # Also mark cells within sensor range of explored positions
        for dx in range(-int(max_sensor_range), int(max_sensor_range) + 1):
            for dy in range(-int(max_sensor_range), int(max_sensor_range) + 1):
                nx, ny = ex + dx, ey + dy
                if 0 <= nx < width and 0 <= ny < height:
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist <= max_sensor_range:
                        grid[ny][nx] = '.'

    # Mark pheromone trails (lower priority - will be overwritten by obstacles/objects)
    # Only show pheromones on explored cells (can't see pheromones in fog)
    for pheromone in world.pheromones:
        px = int(pheromone.position.x / scale)
        py = int(pheromone.position.y / scale)
        if 0 <= px < width and 0 <= py < height and grid[py][px] == '.':
            # Only show if pheromone is strong enough
            if pheromone.strength >= 0.3:
                if pheromone.pheromone_type == PheromoneType.EXPLORATION:
                    grid[py][px] = '~'  # Exploration trail
                elif pheromone.pheromone_type == PheromoneType.OBJECT_FOUND:
                    grid[py][px] = '*'  # Object found marker
                elif pheromone.pheromone_type == PheromoneType.DANGER:
                    grid[py][px] = '!'  # Danger marker

    if fog_of_war:
        # Show only DISCOVERED obstacles (by any robot)
        for obs in all_discovered_obstacles.values():
            x = int(obs.position.x / scale)
            y = int(obs.position.y / scale)
            if 0 <= x < width and 0 <= y < height:
                grid[y][x] = '#'

        # Show only DISCOVERED uncollected objects (by any robot)
        for obj in all_discovered_objects.values():
            if not obj.collected:
                x = int(obj.position.x / scale)
                y = int(obj.position.y / scale)
                if 0 <= x < width and 0 <= y < height:
                    grid[y][x] = 'O'
    else:
        # Debug mode - show ALL obstacles and objects
        for obs in world.obstacles:
            x = int(obs.position.x / scale)
            y = int(obs.position.y / scale)
            if 0 <= x < width and 0 <= y < height:
                # Mark undiscovered vs discovered
                if obs.id in all_discovered_obstacles:
                    grid[y][x] = '#'
                else:
                    grid[y][x] = 'x'  # Hidden obstacle

        for obj in world.objects:
            if not obj.collected:
                x = int(obj.position.x / scale)
                y = int(obj.position.y / scale)
                if 0 <= x < width and 0 <= y < height:
                    if obj.id in all_discovered_objects:
                        grid[y][x] = 'O'
                    else:
                        grid[y][x] = 'o'  # Hidden object

    # Place all robots (always visible - each robot knows where it is)
    for r in world.robots:
        rx = int(r.position.x / scale)
        ry = int(r.position.y / scale)
        if 0 <= rx < width and 0 <= ry < height:
            # Use robot's symbol (R, B, G, Y, etc.)
            grid[ry][rx] = r.symbol

    # Place home positions for all robots
    for _, home_pos in world.home_positions.items():
        hx = int(home_pos.x / scale)
        hy = int(home_pos.y / scale)
        if 0 <= hx < width and 0 <= hy < height and grid[hy][hx] in ['.', '?']:
            grid[hy][hx] = 'H'

    lines = []
    # Build legend with robot symbols
    robot_legend = ", ".join([f"{r.symbol}={r.color_name}" for r in world.robots])
    if fog_of_war:
        lines.append(f"  Robot View ({robot_legend}, O=Object, #=Obstacle, H=Home, ?=Unknown, ~=Trail, *=Found, !=Danger)")
    else:
        lines.append(f"  Debug View ({robot_legend}, o=hidden obj, x=hidden obs, ?=unexplored)")
    lines.append("  " + "-" * (width + 2))
    for row in reversed(grid):  # Reverse for y-up orientation
        lines.append("  |" + "".join(row) + "|")
    lines.append("  " + "-" * (width + 2))
    return lines


def build_state_display(world: SimulationWorld, tick: int, max_ticks: int, scale: int = 1) -> str:
    """Build complete animation frame as a single string with partial observability info."""
    robot = world.robot
    known = world.known_world
    uncollected = world.get_uncollected_objects()
    known_uncollected = known.get_uncollected_known_objects()

    # Calculate box width based on grid size
    grid_width = world.width // scale
    box_width = max(65, grid_width + 8)  # Minimum 65, or grid width + padding

    lines = []

    # Header with progress bar
    progress = tick / max_ticks
    bar_width = box_width - 22
    filled = int(bar_width * progress)
    bar = "█" * filled + "░" * (bar_width - filled)

    lines.append("╔" + "═" * box_width + "╗")
    tick_str = f"  TICK {tick:3d}/{max_ticks}  [{bar}] {progress*100:5.1f}%  "
    lines.append(f"║{tick_str:<{box_width}}║")
    lines.append("╠" + "═" * box_width + "╣")

    # Robot status
    battery_bar_width = 20
    battery_filled = int(battery_bar_width * robot.battery / 100)
    battery_bar = "█" * battery_filled + "░" * (battery_bar_width - battery_filled)
    battery_color = "🟢" if robot.battery > 50 else "🟡" if robot.battery > 20 else "🔴"

    lines.append(f"║  Position: ({robot.position.x:5.1f}, {robot.position.y:5.1f})" + " " * (box_width - 30) + "║")
    battery_line = f"  Battery:  [{battery_bar}] {robot.battery:5.1f}% {battery_color}"
    lines.append(f"║{battery_line}" + " " * (box_width - len(battery_line) + 1) + "║")
    lines.append(f"║  Action:   {robot.current_action:<{box_width - 13}}║")

    # Partial observability status
    discovered_objs = len(known.discovered_objects)
    discovered_obs = len(known.discovered_obstacles)
    borders_known = sum([
        known.known_min_x is not None,
        known.known_max_x is not None,
        known.known_min_y is not None,
        known.known_max_y is not None
    ])

    # Show collected/discovered/total objects
    obj_line = f"  Objects:  {robot.objects_collected} collected, {len(known_uncollected)} visible ({discovered_objs} discovered)"
    lines.append(f"║{obj_line:<{box_width}}║")

    # Show discovery status
    discovery_line = f"  Discovery: {discovered_obs} obstacles, {borders_known}/4 borders"
    lines.append(f"║{discovery_line:<{box_width}}║")

    stats_line = f"  Score: {robot.success_metric:6.1f}  |  Distance: {robot.distance_traveled:6.1f}  |  Hits: {robot.collision_count}"
    lines.append(f"║{stats_line:<{box_width}}║")

    if known_uncollected:
        # Show nearest KNOWN object
        nearest_known = known.get_nearest_known_object(robot.position)
        if nearest_known:
            dist = robot.position.distance_to(nearest_known.position)
            target_line = f"  Target:   {nearest_known.id} at ({nearest_known.position.x:.0f},{nearest_known.position.y:.0f}) - {dist:5.1f} units away"
            lines.append(f"║{target_line:<{box_width}}║")
        else:
            lines.append("║" + " " * box_width + "║")
    elif uncollected:
        # Objects exist but not discovered - exploring
        lines.append(f"║  Exploring... ({len(uncollected)} objects remain undiscovered)" + " " * (box_width - 50) + "║")
    else:
        lines.append(f"║  ✓ ALL OBJECTS COLLECTED!" + " " * (box_width - 26) + "║")

    lines.append("╠" + "═" * box_width + "╣")

    # World visualization with fog of war
    map_lines = build_world_visualization(world, scale, fog_of_war=True)
    for map_line in map_lines:
        lines.append(f"║ {map_line:<{box_width - 2}} ║")

    lines.append("╚" + "═" * box_width + "╝")

    return "\n".join(lines)


def render_animation_frame(world: SimulationWorld, tick: int, max_ticks: int, scale: int = 1):
    """Render a single animation frame in-place."""
    frame = build_state_display(world, tick, max_ticks, scale)
    # Move cursor to top-left and draw frame
    print(f"{CURSOR_HOME}{frame}", flush=True)


def print_world_state(world: SimulationWorld, tick: int):
    """Print current world state with partial observability info (legacy, non-animated version)."""
    uncollected = world.get_uncollected_objects()

    print(f"\n{'='*60}")
    print(f" TICK {tick}  |  Objects remaining: {len(uncollected)}")
    print(f"{'='*60}")

    # Show status for each robot
    for robot in world.robots:
        known = world.known_worlds.get(robot.id, world.known_world)
        known_uncollected = known.get_uncollected_known_objects()

        print(f" [{robot.symbol}] {robot.id}: {robot.position} | {robot.current_action}")
        print(f"     Score: {robot.success_metric:.1f} | Collected: {robot.objects_collected} | Dist: {robot.distance_traveled:.1f}")


def visualize_world(world: SimulationWorld, scale: int = 1, fog_of_war: bool = True):
    """Simple ASCII visualization of the world with fog of war."""
    lines = build_world_visualization(world, scale, fog_of_war)
    print()
    for line in lines:
        print(line)


# =============================================================================
# WEBSOCKET SIMULATION (async version for lower latency)
# =============================================================================

async def query_robot_state_ws(ws_client: WebSocketTwinClient, robot: Robot) -> dict:
    """Query robot state using WebSocket (async version of query_robot_state)."""
    robot_uri = f"<urn:robot:{robot.id}>"

    query = f"""
PREFIX robo: <{ROBO}>

SELECT ?collision ?battery ?nearObj ?atObj ?lowBat ?highPerf ?collected ?total
       ?distance ?metric ?distNearest ?distObs ?clearAngle
       ?mustAvoid ?avoidLeft ?avoidRight ?nearObs ?emergencyAvoid
       ?isExploring ?inLoop ?stuckCounter ?knownObjects
       ?nearbyRobotCount ?ticksInCluster ?dispersionHeading ?robotPriority
       ?inCluster ?shouldDisperse ?mildCluster ?priorityDisperse
       ?coverageArea ?pathKnottiness ?recentPositionCount
       ?smallCoverage ?circlingBehavior ?shouldVenture ?severelyCircling
WHERE {{
    {robot_uri} a robo:Robot .
    OPTIONAL {{ {robot_uri} robo:hasCollision ?collision }}
    OPTIONAL {{ {robot_uri} robo:batteryLevel ?battery }}
    OPTIONAL {{ {robot_uri} robo:objectsCollected ?collected }}
    OPTIONAL {{ {robot_uri} robo:totalObjects ?total }}
    OPTIONAL {{ {robot_uri} robo:distanceTraveled ?distance }}
    OPTIONAL {{ {robot_uri} robo:successMetric ?metric }}
    OPTIONAL {{ {robot_uri} robo:distanceToNearest ?distNearest }}
    OPTIONAL {{ {robot_uri} robo:distanceToObstacle ?distObs }}
    OPTIONAL {{ {robot_uri} robo:clearPathAngle ?clearAngle }}

    OPTIONAL {{ {robot_uri} robo:isExploring ?isExploring }}
    OPTIONAL {{ {robot_uri} robo:inLoop ?inLoop }}
    OPTIONAL {{ {robot_uri} robo:stuckCounter ?stuckCounter }}
    OPTIONAL {{ {robot_uri} robo:knownObjects ?knownObjects }}

    OPTIONAL {{ {robot_uri} robo:nearbyRobotCount ?nearbyRobotCount }}
    OPTIONAL {{ {robot_uri} robo:ticksInCluster ?ticksInCluster }}
    OPTIONAL {{ {robot_uri} robo:dispersionHeading ?dispersionHeading }}
    OPTIONAL {{ {robot_uri} robo:robotPriority ?robotPriority }}

    BIND(EXISTS {{ {robot_uri} a robo:NearObject }} AS ?nearObj)
    BIND(EXISTS {{ {robot_uri} a robo:AtObject }} AS ?atObj)
    BIND(EXISTS {{ {robot_uri} a robo:LowBattery }} AS ?lowBat)
    BIND(EXISTS {{ {robot_uri} a robo:HighPerformer }} AS ?highPerf)

    BIND(EXISTS {{ {robot_uri} a robo:MustAvoid }} AS ?mustAvoid)
    BIND(EXISTS {{ {robot_uri} a robo:AvoidLeft }} AS ?avoidLeft)
    BIND(EXISTS {{ {robot_uri} a robo:AvoidRight }} AS ?avoidRight)
    BIND(EXISTS {{ {robot_uri} a robo:NearObstacle }} AS ?nearObs)
    BIND(EXISTS {{ {robot_uri} a robo:EmergencyAvoid }} AS ?emergencyAvoid)

    BIND(EXISTS {{ {robot_uri} a robo:InCluster }} AS ?inCluster)
    BIND(EXISTS {{ {robot_uri} a robo:ShouldDisperse }} AS ?shouldDisperse)
    BIND(EXISTS {{ {robot_uri} a robo:MildCluster }} AS ?mildCluster)
    BIND(EXISTS {{ {robot_uri} a robo:PriorityDisperse }} AS ?priorityDisperse)

    OPTIONAL {{ {robot_uri} robo:coverageArea ?coverageArea }}
    OPTIONAL {{ {robot_uri} robo:pathKnottiness ?pathKnottiness }}
    OPTIONAL {{ {robot_uri} robo:recentPositionCount ?recentPositionCount }}

    BIND(EXISTS {{ {robot_uri} a robo:SmallCoverage }} AS ?smallCoverage)
    BIND(EXISTS {{ {robot_uri} a robo:CirclingBehavior }} AS ?circlingBehavior)
    BIND(EXISTS {{ {robot_uri} a robo:ShouldVenture }} AS ?shouldVenture)
    BIND(EXISTS {{ {robot_uri} a robo:SeverelyCircling }} AS ?severelyCircling)
}}
LIMIT 1
"""

    try:
        result = await ws_client.query(query)
        if not result.bindings:
            return {}
        b = result.bindings[0]
        return {
            "collision": b.get("collision", {}).get("value", "false") == "true",
            "battery": float(b.get("battery", {}).get("value", 100)),
            "collected": int(b.get("collected", {}).get("value", 0)),
            "total": int(b.get("total", {}).get("value", 0)),
            "distance": float(b.get("distance", {}).get("value", 0)),
            "metric": float(b.get("metric", {}).get("value", 0)),
            "distanceToNearest": float(b.get("distNearest", {}).get("value", 999)),
            "distanceToObstacle": float(b.get("distObs", {}).get("value", 999)),
            "clearPathAngle": float(b.get("clearAngle", {}).get("value", 0)),
            "nearObject": b.get("nearObj", {}).get("value", "false") == "true",
            "atObject": b.get("atObj", {}).get("value", "false") == "true",
            "lowBattery": b.get("lowBat", {}).get("value", "false") == "true",
            "highPerformer": b.get("highPerf", {}).get("value", "false") == "true",
            "mustAvoid": b.get("mustAvoid", {}).get("value", "false") == "true",
            "avoidLeft": b.get("avoidLeft", {}).get("value", "false") == "true",
            "avoidRight": b.get("avoidRight", {}).get("value", "false") == "true",
            "nearObstacle": b.get("nearObs", {}).get("value", "false") == "true",
            "emergencyAvoid": b.get("emergencyAvoid", {}).get("value", "false") == "true",
            "isExploring": b.get("isExploring", {}).get("value", "false") == "true",
            "inLoop": b.get("inLoop", {}).get("value", "false") == "true",
            "stuckCounter": int(b.get("stuckCounter", {}).get("value", 0)),
            "knownObjects": int(b.get("knownObjects", {}).get("value", 0)),
            "nearbyRobotCount": int(b.get("nearbyRobotCount", {}).get("value", 0)),
            "ticksInCluster": int(b.get("ticksInCluster", {}).get("value", 0)),
            "inCluster": b.get("inCluster", {}).get("value", "false") == "true",
            "shouldDisperse": b.get("shouldDisperse", {}).get("value", "false") == "true",
        }
    except Exception as e:
        log(f"[WS-QUERY] Error querying robot state: {e}")
        return {}


async def run_simulation_websocket(max_ticks: int = 50, visualize: bool = True, animate: bool = True,
                                    grid_width: int = 20, grid_height: int = 20, scale: int = 1,
                                    num_robots: int = 1, num_objects: Optional[int] = None,
                                    battery_capacity: float = 100.0):
    """Run simulation using WebSocket for lower latency.

    This async version uses a persistent WebSocket connection instead of
    REST calls, reducing per-operation latency from ~5-10ms to ~1-2ms.
    """
    import asyncio

    competition_mode = num_robots > 1
    mode_str = "COMPETITION MODE (WebSocket)" if competition_mode else "SINGLE ROBOT (WebSocket)"

    print(f"""
+===========================================================================+
|     Robot Simulation with Ontology-Driven Reasoning (WebSocket Mode)     |
|                                                                           |
|  Using WebSocket for lower latency SPARQL operations.                     |
|  Expected ~5-10x performance improvement over REST.                       |
|                                                                           |
|  MODE: {mode_str:^63}|
+===========================================================================+
""")

    # Create HTTP client for initialization (ontology loading, etc.)
    http_client = create_client()

    # Scale objects/obstacles based on grid size
    area_factor = (grid_width * grid_height) / 400
    if num_objects is None:
        num_objects = max(4, int(8 * area_factor))
    num_obstacles = max(2, int(4 * area_factor))
    world = create_random_world(num_objects=num_objects, num_obstacles=num_obstacles,
                                 width=grid_width, height=grid_height,
                                 num_robots=num_robots,
                                 battery_capacity=battery_capacity)

    print(f"\n[SETUP] World: {world.width}x{world.height} grid")
    print(f"[SETUP] Objects: {len(world.objects)}, Obstacles: {len(world.obstacles)}, Robots: {len(world.robots)}")

    # Initialize using HTTP client (one-time setup)
    print("\n[PHASE 0] Initialization (HTTP)")
    load_ontology(http_client)
    initialize_twin(http_client, world)
    setup_reasoning_rules(http_client)

    if animate and visualize:
        enable_quiet_mode()

    # Now switch to WebSocket for the simulation loop
    print("\n[PHASE 1] Connecting WebSocket...")
    token = get_token()

    async with WebSocketClient(BASE_URL, token=token) as ws:
        ws_twin = WebSocketTwinClient(ws, TWIN_ID)
        print("[WS] Connected - starting simulation loop")

        if visualize and animate:
            print(HIDE_CURSOR, end="")
            print(CLEAR_SCREEN, end="")
            await asyncio.sleep(0.5)

        start_time = time.time()
        completion_reason = None

        try:
            for tick in range(1, max_ticks + 1):
                world.current_tick = tick
                for robot in world.robots:
                    robot.tick_count = tick

                world.decay_pheromones()

                is_over, reason = world.check_game_over()
                if is_over:
                    completion_reason = f"{reason} at tick {tick}!"
                    break

                # === BATCH UPDATE via WebSocket ===
                batch = BatchUpdateBuilder()
                update_tick_batched(http_client, world, batch)  # Prepare updates

                # Execute via WebSocket
                sparql_update = batch.build_sparql_update()
                if sparql_update:
                    await ws_twin.update(sparql_update)

                # === QUERY each robot via WebSocket ===
                for robot in world.get_active_robots():
                    state = await query_robot_state_ws(ws_twin, robot)

                    # === DECIDE & ACT ===
                    reactive_action = get_robot_action(world, robot)
                    if reactive_action is not None:
                        action = reactive_action.action
                        target = None
                        if reactive_action.target is not None:
                            target = Position(reactive_action.target[0], reactive_action.target[1])

                        avoidance = {"mustAvoid": False, "avoidLeft": False, "avoidRight": False,
                                     "clearPathAngle": 0, "emergencyAvoid": False, "inLoop": False,
                                     "stuckCounter": 0, "reactiveControl": True}

                        if action == "Wait":
                            robot.current_action = "Waiting"
                        elif action == "Recharge":
                            robot.battery = robot.battery_capacity
                            robot.current_action = "Recharged"
                        elif action == "Collect":
                            if reactive_action.object_id:
                                obj = next((o for o in world.objects if o.id == reactive_action.object_id), None)
                                if obj and not obj.collected:
                                    world.collect_object(robot, obj)
                                    robot.current_action = f"Collected {obj.id}"
                        elif action == "Move" and target:
                            # Map reactive "Move" to execute_action's "MoveToObject"
                            execute_action(world, "MoveToObject", target, avoidance, robot)
                        else:
                            execute_action(world, action, target, avoidance, robot)
                    else:
                        action, target, avoidance = determine_action(http_client, world, state, robot)
                        execute_action(world, action, target, avoidance, robot)

                    # === UPDATE STUCK/WANDERLUST STATE ===
                    robot.update_stuck_state()
                    robot.update_wanderlust(world.width, world.height)

                    # Check for robot-robot collision after move
                    other_robot = world.check_robot_collision(robot)
                    if other_robot:
                        robot.has_robot_collision = True
                        robot.robot_collision_count += 1
                        other_robot.has_robot_collision = True
                        other_robot.robot_collision_count += 1

                # Visualization
                if visualize:
                    if animate:
                        render_animation_frame(world, tick, max_ticks, scale)
                        await asyncio.sleep(0.15)
                    else:
                        visualize_world(world, scale)

            elapsed = time.time() - start_time

        finally:
            if animate and visualize:
                print(SHOW_CURSOR, end="")
                disable_quiet_mode()

    # Print summary
    print("\n" + "=" * 60)
    print(" SIMULATION COMPLETE (WebSocket Mode)")
    print("=" * 60)
    if completion_reason:
        print(f"Result: {completion_reason}")
    print(f"Duration: {elapsed:.2f}s for {tick} ticks ({tick/elapsed:.1f} ticks/sec)")

    for robot in world.robots:
        print(f"\n{robot.id} ({robot.symbol}):")
        print(f"  Objects collected: {robot.objects_collected}")
        print(f"  Distance traveled: {robot.distance_traveled:.1f}")
        print(f"  Battery remaining: {robot.battery:.1f}%")


# =============================================================================
# MAIN SIMULATION (HTTP version)
# =============================================================================

def run_simulation(max_ticks: int = 50, visualize: bool = True, animate: bool = True,
                   grid_width: int = 20, grid_height: int = 20, scale: int = 1,
                   num_robots: int = 1, num_objects: Optional[int] = None,
                   battery_capacity: float = 100.0):
    """Run the complete simulation with multiple competing robots.

    Args:
        max_ticks: Maximum number of simulation ticks
        visualize: Whether to show any visualization
        animate: If True, use in-place animation; if False, use scrolling output
        grid_width: Width of the simulation world
        grid_height: Height of the simulation world
        scale: Display scale factor (1 = full size, 2 = half size, etc.)
        num_robots: Number of competing robots (1-6)
        num_objects: Number of collectible objects (None = auto based on grid size)
    """

    competition_mode = num_robots > 1
    mode_str = "COMPETITION MODE" if competition_mode else "SINGLE ROBOT"

    print(f"""
+===========================================================================+
|     Robot Simulation with Ontology-Driven Reasoning & Partial Observability|
|                                                                           |
|  Robots use semantic reasoning to navigate, collect objects,              |
|  and avoid obstacles. All decisions are made through SWRL rules           |
|  fired against an OWL ontology.                                           |
|                                                                           |
|  PARTIAL OBSERVABILITY: Robots can only see entities within their         |
|  sensor range. They must explore to discover objects and obstacles.       |
|  Grid borders are unknown until a robot reaches them.                     |
|                                                                           |
|  MODE: {mode_str:^63}|
+===========================================================================+
""")

    # Create client and world
    client = create_client()

    # Scale objects/obstacles based on grid size
    area_factor = (grid_width * grid_height) / 400  # 400 = 20x20 base
    if num_objects is None:
        num_objects = max(4, int(8 * area_factor))
    num_obstacles = max(2, int(4 * area_factor))
    world = create_random_world(num_objects=num_objects, num_obstacles=num_obstacles,
                                 width=grid_width, height=grid_height,
                                 num_robots=num_robots,
                                 battery_capacity=battery_capacity)

    print(f"\n[SETUP] World: {world.width}x{world.height} grid")
    print(f"[SETUP] Objects: {len(world.objects)}")
    print(f"[SETUP] Obstacles: {len(world.obstacles)}")
    print(f"[SETUP] Robots: {len(world.robots)}")
    for robot in world.robots:
        print(f"  - {robot.id} ({robot.symbol}/{robot.color_name}) starts at: {robot.position}")

    # Enable quiet mode early if animating to suppress httpx logs during initialization
    if animate and visualize:
        enable_quiet_mode()

    # Initialize
    print("\n[PHASE 0] Initialization")
    load_ontology(client)
    initialize_twin(client, world)
    setup_reasoning_rules(client)

    # Initialize reactive control (O(1) per tick, no planning)
    if REACTIVE_CONTROL_AVAILABLE:
        print("[SETUP] Reactive control enabled - O(1) action selection")
    else:
        print("[SETUP] Reactive control not available - using procedural fallback")

    # Skip PDDL planning initialization - reactive control doesn't need it
    # (pddl_rs has "not yet implemented" panics for some PDDL features)
    print("[SETUP] Skipping PDDL planning - using reactive control only")

    if visualize and not animate:
        visualize_world(world, scale)

    # Main simulation loop
    print("\n" + "="*60)
    print(" STARTING SIMULATION LOOP")
    print("="*60)

    if animate and visualize:
        print(HIDE_CURSOR, end="")
        print(CLEAR_SCREEN, end="")
        time.sleep(0.5)

    completion_reason = None

    try:
        for tick in range(1, max_ticks + 1):
            # Update tick count for world and all robots
            world.current_tick = tick
            for robot in world.robots:
                robot.tick_count = tick

            # Decay pheromones at start of tick
            world.decay_pheromones()

            # Check if game over (all objects collected or all robots inactive)
            is_over, reason = world.check_game_over()
            if is_over:
                completion_reason = f"{reason} at tick {tick}!"
                break

            # Check if this is the last tick (time limit)
            if tick == max_ticks:
                uncollected = len(world.get_uncollected_objects())
                total = len(world.objects)
                collected = total - uncollected
                completion_reason = f"Time limit reached! {collected}/{total} objects collected"

            # === BATCH UPDATE (using /api/v1/sparql/batch-update) ===
            # Create batch builder for this tick
            batch = BatchUpdateBuilder()

            # Process all robots: SENSE + compute state updates
            update_tick_batched(client, world, batch)

            # Execute single batch SPARQL UPDATE for all robots (transactional)
            batch.execute(client)

            # Record positions to timeseries (if enabled)
            if USE_TIMESERIES and tick % 2 == 0:  # Every 2 ticks to reduce load
                ingest_position_timeseries(client, world, tick)

            # REASON once for all updates
            # DISABLED: Reasonable crate has memory issues causing 100% CPU on subsequent runs
            # _ = run_reasoning(client)

            # Process each robot for action/movement
            for robot in world.get_active_robots():
                # === QUERY ===
                state = query_robot_state(client, robot)

                # Debug cluster state from ontology
                nearby = state.get("nearbyRobotCount", 0)
                if tick < 5 or nearby >= 1:  # Always show first 5 ticks for debugging
                    log(f"[{robot.id}] CLUSTER STATE: nearby={nearby}, ticksInCluster={state.get('ticksInCluster')}, inCluster={state.get('inCluster')}, shouldDisperse={state.get('shouldDisperse')}")

                # === DECIDE ===
                # Use reactive control (O(1) precondition checks, not planning)
                reactive_action = get_robot_action(world, robot)

                if reactive_action is not None:
                    # Reactive control - execute the action
                    # Collision avoidance handled by precondition checks
                    action = reactive_action.action

                    # Convert target tuple to Position
                    target = None
                    if reactive_action.target is not None:
                        target = Position(reactive_action.target[0], reactive_action.target[1])

                    avoidance = {"mustAvoid": False, "avoidLeft": False, "avoidRight": False,
                                 "clearPathAngle": 0, "emergencyAvoid": False, "inLoop": False,
                                 "stuckCounter": 0, "reactiveControl": True}

                    if action == "Wait":
                        robot.current_action = "Waiting"
                    elif action == "Recharge":
                        robot.battery = robot.battery_capacity
                        robot.current_action = "Recharged"
                    elif action == "Collect":
                        # Find and collect the object
                        if reactive_action.object_id:
                            obj = next((o for o in world.objects if o.id == reactive_action.object_id), None)
                            if obj and not obj.collected:
                                world.collect_object(robot, obj)
                                robot.current_action = f"Collected {obj.id}"
                    elif action == "Move" and target:
                        # Map reactive "Move" to execute_action's "MoveToObject"
                        execute_action(world, "MoveToObject", target, avoidance, robot)
                    else:
                        execute_action(world, action, target, avoidance, robot)
                        robot.current_action = f"{action}"
                else:
                    # Fallback to procedural action determination (exploration, stuck recovery)
                    action, target, avoidance = determine_action(client, world, state, robot)
                    execute_action(world, action, target, avoidance, robot)
                    log(f"[Procedural] {robot.id}: {action}")

                # === UPDATE STUCK/WANDERLUST STATE ===
                robot.update_stuck_state()
                robot.update_wanderlust(world.width, world.height)

                # Check for robot-robot collision after move
                other_robot = world.check_robot_collision(robot)
                if other_robot:
                    robot.has_robot_collision = True
                    robot.robot_collision_count += 1
                    other_robot.has_robot_collision = True
                    other_robot.robot_collision_count += 1

            # === DISPLAY ===
            if visualize:
                if animate:
                    render_animation_frame(world, tick, max_ticks, scale)
                    time.sleep(0.15)  # Slightly slower for animation effect
                else:
                    print_world_state(world, tick)
                    if tick % 5 == 0:  # Show map every 5 ticks
                        visualize_world(world, scale)
                    time.sleep(0.1)

    finally:
        # Disable quiet mode after animation
        disable_quiet_mode()
        if animate and visualize:
            print(SHOW_CURSOR, end="")

    # Final summary - print below the animation frame
    if animate and visualize:
        # Calculate lines needed: header(3) + status(7) + map header(2) + grid height + footer(1)
        frame_lines = 13 + (grid_height // scale)
        print("\n" * frame_lines)  # Move below animation area

    # Determine winner
    winner = world.determine_winner()
    rankings = world.get_rankings()

    print("\n" + "="*60)
    print(" SIMULATION COMPLETE")
    print("="*60)
    if completion_reason:
        print(f" Result: {completion_reason}")

    # Show competition results if multi-robot
    if len(world.robots) > 1:
        print("\n" + "-"*60)
        print(" COMPETITION RESULTS")
        print("-"*60)
        for i, robot in enumerate(rankings):
            medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
            status = "WINNER!" if i == 0 else ""
            print(f" {medal} {robot.id} ({robot.symbol}/{robot.color_name}): "
                  f"{robot.objects_collected} objects, "
                  f"score={robot.success_metric:.1f} {status}")

    # Show stats for each robot
    print("\n" + "-"*60)
    print(" ROBOT STATISTICS")
    print("-"*60)
    for robot in world.robots:
        known = world.known_worlds.get(robot.id)
        print(f"\n [{robot.id}] ({robot.symbol}/{robot.color_name})")
        print(f"   Objects Collected: {robot.objects_collected}/{len(world.objects)}")
        print(f"   Success Score: {robot.success_metric:.1f}")
        print(f"   Distance Traveled: {robot.distance_traveled:.1f}")
        print(f"   Battery Remaining: {robot.battery:.1f}%")
        print(f"   Obstacle Collisions: {robot.collision_count}")
        print(f"   Robot Collisions: {robot.robot_collision_count}")
        if known:
            print(f"   Explored Cells: {len(known.explored_positions)}")

    # Query final state from ontology (for primary robot)
    print("\n[ONTOLOGY] Final state query (robot1):")
    final_state = query_robot_state(client, world.robots[0])
    for key, value in final_state.items():
        print(f"  {key}: {value}")

    if visualize and not animate:
        visualize_world(world, scale)

    return world


def main():
    global BASE_URL
    parser = argparse.ArgumentParser(description="Robot Simulation with Ontology Reasoning")
    parser.add_argument("--base-url", help="DTaaS service URL")
    parser.add_argument("--ticks", type=int, default=50, help="Maximum simulation ticks")
    parser.add_argument("--visualize", action="store_true", default=True, help="Show visualization")
    parser.add_argument("--no-visualize", action="store_false", dest="visualize", help="Disable visualization")
    parser.add_argument("--animate", action="store_true", default=True, help="Use in-place animation (default)")
    parser.add_argument("--no-animate", action="store_false", dest="animate", help="Use scrolling output instead of animation")
    parser.add_argument("--grid-width", type=int, default=20, help="World grid width (default: 20)")
    parser.add_argument("--grid-height", type=int, default=20, help="World grid height (default: 20)")
    parser.add_argument("--grid-size", type=int, help="Set both grid width and height (shorthand)")
    parser.add_argument("--scale", type=int, default=1, help="Display scale factor, 1=full size, 2=half size (default: 1)")
    parser.add_argument("--robots", type=int, default=1, choices=[1, 2, 3, 4, 5, 6],
                        help="Number of competing robots (1-6, default: 1)")
    parser.add_argument("--objects", type=int, default=None,
                        help="Number of collectible objects (default: auto based on grid size)")
    parser.add_argument("--websocket", action="store_true",
                        help="Use WebSocket connection for lower latency (async mode)")
    parser.add_argument("--battery-capacity", type=float, default=100.0,
                        help="Robot battery capacity (default: 100.0)")
    args = parser.parse_args()

    if args.base_url:
        BASE_URL = args.base_url

    # Handle --grid-size shorthand
    grid_width = args.grid_size if args.grid_size else args.grid_width
    grid_height = args.grid_size if args.grid_size else args.grid_height

    if args.websocket:
        # Use async WebSocket mode for lower latency
        import asyncio
        asyncio.run(run_simulation_websocket(
            max_ticks=args.ticks,
            visualize=args.visualize,
            animate=args.animate,
            grid_width=grid_width,
            grid_height=grid_height,
            scale=args.scale,
            num_robots=args.robots,
            num_objects=args.objects,
            battery_capacity=args.battery_capacity,
        ))
    else:
        run_simulation(
            max_ticks=args.ticks,
            visualize=args.visualize,
            animate=args.animate,
            grid_width=grid_width,
            grid_height=grid_height,
            scale=args.scale,
            num_robots=args.robots,
            num_objects=args.objects,
            battery_capacity=args.battery_capacity,
        )


if __name__ == "__main__":
    main()
