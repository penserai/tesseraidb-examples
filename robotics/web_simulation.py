#!/usr/bin/env python3
"""
Web-based Robot Simulation with Ontology-Driven Reasoning
==========================================================

Runs the full ontology-driven robot simulation from robot_simulation.py
with a web-based visualization.

Requires:
- DTaaS server running (tesseraidb)
- websockets: pip install websockets

Usage:
    python web_simulation.py [--port 8090] [--ticks 100] [--robots 3]

Then open http://localhost:8090 in your browser.
"""

import asyncio
import json
import argparse
import math
import os
import sys
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

import websockets

# Import the actual simulation logic
from robot_simulation import (
    SimulationWorld, Robot, WorldObject, Obstacle, Position,
    KnownWorld, create_random_world, create_client, load_ontology,
    initialize_twin, setup_reasoning_rules, update_sensor_data,
    run_reasoning, query_robot_state, query_robot_state_ws, determine_action, execute_action,
    BatchUpdateBuilder, RobotStateUpdate, compute_obstacle_geometry,
    ROBO, TWIN_ID, enable_quiet_mode,
)
from dtaas import WebSocketClient, WebSocketTwinClient
# Reactive control (O(1) action selection, no planning)
try:
    from reactive_control import get_reactive_action, ReactiveAction
    REACTIVE_CONTROL_AVAILABLE = True
except ImportError:
    REACTIVE_CONTROL_AVAILABLE = False
    get_reactive_action = None
from dtaas.exceptions import DTaaSError

# Suppress HTTP logging
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# Global state
world: SimulationWorld = None
client = None  # HTTP client for initialization
ws_client: WebSocketClient = None  # WebSocket client for DTaaS
ws_twin: WebSocketTwinClient = None  # Twin-specific WebSocket wrapper
connected_clients: set = set()
simulation_running = False
simulation_task = None
max_ticks = 200
current_config = {"width": 40, "height": 25, "robots": 5, "objects": 15, "obstacles": 20, "battery": 100}
ws_port = 8091  # WebSocket port for dynamic HTML generation
BASE_URL = os.environ.get("DTAAS_URL", "http://localhost:8080")

# Import login from common
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import DEFAULT_USERNAME, DEFAULT_PASSWORD, login


def get_auth_token():
    """Get authentication token via login."""
    username = os.environ.get("DTAAS_USERNAME", DEFAULT_USERNAME)
    password = os.environ.get("DTAAS_PASSWORD", DEFAULT_PASSWORD)
    return login(BASE_URL, username, password)


def world_to_dict(world: SimulationWorld, tick: int) -> dict:
    """Convert world state to JSON-serializable dict."""
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]

    # Build robot ID to color mapping
    robot_colors = {}
    robots_data = []
    for i, r in enumerate(world.robots):
        color = colors[i % len(colors)]
        robot_colors[r.id] = color
        known = world.known_worlds.get(r.id)
        robots_data.append({
            "id": r.id,
            "x": r.position.x,
            "y": r.position.y,
            "heading": r.heading,
            "battery": r.battery,
            "sensorRange": r.sensor_range,
            "objectsCollected": r.objects_collected,
            "distanceTraveled": r.distance_traveled,
            "collisionCount": r.collision_count,
            "isExploring": len(known.get_uncollected_known_objects()) == 0 if known else True,
            "color": color,
            "action": r.current_action,
            "isStuck": r.is_stuck,
            "inLoop": known.loop_detected if known else False,
            "coverageArea": known.coverage_area if known else 0,
            "knottiness": known.path_knottiness if known else 0,
            "escapeMode": known.escape_mode if known else False,
            "escapeTicks": known.escape_ticks_remaining if known else 0,
        })

    # Get pheromone data with robot color
    pheromones_data = []
    for p in world.pheromones:
        pheromones_data.append({
            "x": p.position.x,
            "y": p.position.y,
            "type": p.pheromone_type,
            "strength": p.strength,
            "color": robot_colors.get(p.deposited_by, "#888"),
        })

    return {
        "tick": tick,
        "width": world.width,
        "height": world.height,
        "robots": robots_data,
        "objects": [
            {"id": o.id, "x": o.position.x, "y": o.position.y,
             "value": o.value, "collected": o.collected}
            for o in world.objects
        ],
        "obstacles": [
            {"id": o.id, "x": o.position.x, "y": o.position.y, "radius": o.radius}
            for o in world.obstacles
        ],
        "pheromones": pheromones_data,
        "explored": list({pos for known in world.known_worlds.values()
                         for pos in (known.explored_positions or [])}),
        "stats": {
            "totalObjects": len(world.objects),
            "collectedObjects": sum(1 for o in world.objects if o.collected),
            "totalCollisions": sum(r.collision_count for r in world.robots),
        }
    }


def get_ontology_state() -> dict:
    """Get the current ontology state including twins, rules, and TBox."""
    global world

    # Twins (ABox individuals)
    twins = []

    # Add robots as twins
    if world:
        for r in world.robots:
            known = world.known_worlds.get(r.id)
            props = f"pos=({r.position.x:.1f},{r.position.y:.1f}), heading={r.heading:.0f}°, battery={r.battery:.0f}%"
            if known:
                props += f", area={known.coverage_area:.1f}, escape={known.escape_mode}"
            twins.append({"type": "Robot", "id": r.id, "properties": props})

        # Add objects as twins
        for o in world.objects:
            status = "collected" if o.collected else "available"
            props = f"pos=({o.position.x:.1f},{o.position.y:.1f}), value={o.value:.1f}, {status}"
            twins.append({"type": "Object", "id": o.id, "properties": props})

        # Add obstacles as twins
        for obs in world.obstacles:
            props = f"pos=({obs.position.x:.1f},{obs.position.y:.1f}), radius={obs.radius:.1f}"
            twins.append({"type": "Obstacle", "id": obs.id, "properties": props})

    # SWRL Rules (from robot_simulation.py)
    rules = [
        {"id": "robo-collision-stop", "name": "Collision Stop Rule",
         "description": "If robot has collision, must stop",
         "condition": "hasCollision = 1.0", "target": "CollisionState"},

        {"id": "robo-low-battery", "name": "Low Battery Rule",
         "description": "If battery below 20%, should return home",
         "condition": "batteryLevel < 20.0", "target": "LowBattery"},

        {"id": "robo-at-object", "name": "At Object Rule",
         "description": "If distance to nearest < 1.0, can collect",
         "condition": "distanceToNearest < 1.0", "target": "AtObject"},

        {"id": "robo-near-object", "name": "Near Object Rule",
         "description": "If distance to nearest < sensor range, classify as NearObject",
         "condition": "distanceToNearest < 3.0", "target": "NearObject"},

        {"id": "robo-path-blocked", "name": "Path Blocked Rule",
         "description": "If pathBlocked is true, must avoid",
         "condition": "pathBlocked = 1.0", "target": "MustAvoid"},

        {"id": "robo-near-obstacle", "name": "Near Obstacle Rule",
         "description": "If distance to obstacle < 1.5, getting close",
         "condition": "distanceToObstacle < 1.5", "target": "NearObstacle"},

        {"id": "robo-emergency-avoid", "name": "Emergency Avoid Rule",
         "description": "If distance to obstacle < 0.8, emergency avoid",
         "condition": "distanceToObstacle < 0.8", "target": "EmergencyAvoid"},

        {"id": "robo-in-loop", "name": "In Loop Rule",
         "description": "If inLoop = true, needs to break pattern",
         "condition": "inLoop = true", "target": "InLoop"},

        {"id": "robo-stuck-exploring", "name": "Stuck Exploring Rule",
         "description": "If stuckCounter > 5, needs random direction",
         "condition": "stuckCounter > 5", "target": "StuckExploring"},

        {"id": "robo-small-coverage", "name": "Small Coverage Area Rule",
         "description": "If coverageArea < 15, robot is circling and should venture",
         "condition": "coverageArea < 15.0", "target": "SmallCoverage"},

        {"id": "robo-high-knottiness", "name": "High Knottiness Rule",
         "description": "If pathKnottiness > 10 (lots of turning), circling behavior",
         "condition": "pathKnottiness > 10.0", "target": "CirclingBehavior"},

        {"id": "robo-should-venture", "name": "Should Venture Rule",
         "description": "If recentPositionCount >= 15, should venture to new area",
         "condition": "recentPositionCount >= 15", "target": "ShouldVenture"},

        {"id": "robo-severely-circling", "name": "Severely Circling Rule",
         "description": "If coverageArea < 8, needs aggressive venture",
         "condition": "coverageArea < 8.0", "target": "SeverelyCircling"},
    ]

    # TBox (Schema) - Classes
    classes = [
        "Robot", "WorldObject", "Obstacle", "Position",
        "CollisionState", "LowBattery", "AtObject", "NearObject",
        "MustAvoid", "AvoidLeft", "AvoidRight", "NearObstacle", "EmergencyAvoid",
        "HighPerformer", "ExploringMode", "InLoop", "StuckExploring", "StuckState", "EscapingState",
        "SmallCoverage", "CirclingBehavior", "ShouldVenture", "SeverelyCircling",
        "InCluster", "ShouldDisperse", "MildCluster", "PriorityDisperse"
    ]

    # TBox - Properties
    properties = [
        {"name": "positionX", "type": "DataProperty"},
        {"name": "positionY", "type": "DataProperty"},
        {"name": "heading", "type": "DataProperty"},
        {"name": "batteryLevel", "type": "DataProperty"},
        {"name": "hasCollision", "type": "DataProperty"},
        {"name": "distanceToNearest", "type": "DataProperty"},
        {"name": "distanceToObstacle", "type": "DataProperty"},
        {"name": "distanceTraveled", "type": "DataProperty"},
        {"name": "successMetric", "type": "DataProperty"},
        {"name": "objectsCollected", "type": "DataProperty"},
        {"name": "knownObjects", "type": "DataProperty"},
        {"name": "isExploring", "type": "DataProperty"},
        {"name": "inLoop", "type": "DataProperty"},
        {"name": "stuckCounter", "type": "DataProperty"},
        {"name": "coverageArea", "type": "DataProperty"},
        {"name": "pathKnottiness", "type": "DataProperty"},
        {"name": "recentPositionCount", "type": "DataProperty"},
        {"name": "nearbyRobotCount", "type": "DataProperty"},
        {"name": "ticksInCluster", "type": "DataProperty"},
        {"name": "dispersionHeading", "type": "DataProperty"},
        {"name": "robotPriority", "type": "DataProperty"},
        {"name": "pathBlocked", "type": "DataProperty"},
        {"name": "clearPathAngle", "type": "DataProperty"},
        {"name": "hasDiscovered", "type": "ObjectProperty"},
        {"name": "locatedAt", "type": "ObjectProperty"},
        {"name": "collected", "type": "DataProperty"},
        {"name": "value", "type": "DataProperty"},
    ]

    return {
        "twins": twins,
        "rules": rules,
        "classes": classes,
        "properties": properties,
    }


async def broadcast(msg: dict):
    """Broadcast message to all connected clients."""
    if connected_clients:
        data = json.dumps(msg)
        await asyncio.gather(
            *[c.send(data) for c in connected_clients],
            return_exceptions=True
        )


async def simulation_loop():
    """Main simulation loop using ontology-driven reasoning with WebSocket.

    Uses WebSocket for low-latency SPARQL operations instead of REST.
    """
    global world, client, simulation_running, ws_client, ws_twin

    tick = 0
    batch = BatchUpdateBuilder()

    # Connect to DTaaS via WebSocket for low-latency operations
    print("[WS] Connecting to DTaaS WebSocket...", flush=True)
    try:
        token = get_auth_token()
        ws_client = WebSocketClient(BASE_URL, token=token)
        await ws_client.connect()
        ws_twin = WebSocketTwinClient(ws_client, TWIN_ID)
        print("[WS] Connected - using WebSocket for SPARQL operations", flush=True)
    except Exception as e:
        print(f"[WS] Failed to connect: {e} - falling back to REST", flush=True)
        ws_client = None
        ws_twin = None

    try:
        while simulation_running and tick < max_ticks:
            tick += 1
            world.current_tick = tick

            # Decay pheromones
            world.decay_pheromones()

            # Process each robot - SENSE phase
            for robot in world.robots:
                if not robot.is_active:
                    continue

                robot.tick_count = tick
                known = world.known_worlds[robot.id]

                # 1. SENSE - Update ontology with sensor data
                discoveries = world.sense_environment(robot)

                # Add discoveries to batch
                for obj in discoveries.get("new_objects", []):
                    batch.add_discovered_object(obj)
                for obs in discoveries.get("new_obstacles", []):
                    batch.add_discovered_obstacle(obs)

                # Check for collisions
                collision = world.check_collision(robot)
                robot.has_collision = collision is not None
                if collision:
                    robot.collision_count += 1

                # Robot collision check
                robot_collision = world.check_robot_collision(robot)
                robot.has_robot_collision = robot_collision is not None
                if robot_collision:
                    robot.robot_collision_count += 1

                # Get distances
                nearest_obj = known.get_nearest_known_object(robot.position)
                nearest_obs = known.get_nearest_known_obstacle(robot.position)
                dist_to_obj = robot.position.distance_to(nearest_obj.position) if nearest_obj else 999
                dist_to_obs = robot.position.distance_to(nearest_obs.position) if nearest_obs else 999

                # Compute obstacle geometry
                target = nearest_obj.position if nearest_obj else None
                geometry = compute_obstacle_geometry(world, target, robot)

                # Cluster detection
                nearby_robots = world.get_nearby_robots(robot, radius=4.0)
                robot.ticks_in_cluster = robot.ticks_in_cluster + 1 if len(nearby_robots) >= 2 else 0
                dispersion_heading = world.get_dispersion_direction(robot, nearby_robots) if nearby_robots else robot.heading

                # Build robot state for batch update
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
                    tick_count=tick,
                    success_metric=robot.success_metric,
                    objects_collected=robot.objects_collected,
                    known_objects=len(known.get_uncollected_known_objects()),
                    is_exploring=len(known.get_uncollected_known_objects()) == 0,
                    path_blocked=geometry["pathBlocked"],
                    obstacle_angle=geometry["obstacleAngle"],
                    obstacle_on_left=geometry["obstacleOnLeft"],
                    obstacle_on_right=geometry["obstacleOnRight"],
                    clear_path_angle=geometry["clearPathAngle"],
                    is_stuck=robot.is_stuck,
                    ticks_without_movement=robot.ticks_without_movement,
                    escape_heading=robot.escape_heading or 0.0,
                    in_loop=known.loop_detected,
                    stuck_counter=known.stuck_counter,
                    nearby_robot_count=len(nearby_robots),
                    ticks_in_cluster=robot.ticks_in_cluster,
                    dispersion_heading=dispersion_heading,
                    robot_priority=robot.robot_index,
                )
                batch.add_robot_state(state)

            # Execute batch update to ontology via WebSocket or REST
            try:
                if ws_twin:
                    sparql_update = batch.build_sparql_update()
                    if sparql_update:
                        await ws_twin.update(sparql_update)
                else:
                    batch.execute(client)
            except Exception as e:
                print(f"Batch update error: {e}")
            batch.clear()

            # 2. REASON - Fire SWRL rules (still uses REST - reasoning is heavy)
            try:
                run_reasoning(client)
            except Exception as e:
                print(f"Reasoning error: {e}")

            # 3. ACT - Get actions from ontology and execute
            for robot in world.robots:
                if not robot.is_active:
                    continue

                known = world.known_worlds[robot.id]

                # Check for object pickup first
                pickup_obj = world.check_object_pickup(robot)
                if pickup_obj and world.collect_object(robot, pickup_obj):
                    robot.current_action = f"Collected {pickup_obj.id}"
                    known.discovered_objects[pickup_obj.id].collected = True
                    robot.reset_collection_timer()
                    batch.mark_object_collected(pickup_obj.id)
                    continue

                # Query state via WebSocket or REST, determine action, and execute
                try:
                    if ws_twin:
                        state = await query_robot_state_ws(ws_twin, robot)
                    else:
                        state = query_robot_state(client, robot)

                    # Use reactive control (O(1) action selection, no planning)
                    reactive_action = None
                    if REACTIVE_CONTROL_AVAILABLE and get_reactive_action is not None:
                        reactive_action = get_reactive_action(world, robot)

                    if reactive_action is not None:
                        # Reactive control - execute the action
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
                        # Fallback to procedural determination (exploration, stuck recovery)
                        action, target, avoidance = determine_action(client, world, state, robot)
                        execute_action(world, action, target, avoidance, robot)
                except Exception as e:
                    print(f"Action error for {robot.id}: {e}")

                # Update stuck state
                robot.update_stuck_state()
                robot.update_wanderlust(world.width, world.height)

            # Broadcast state to web clients
            state_data = world_to_dict(world, tick)
            if tick % 10 == 0:  # Log every 10 ticks
                print(f"Tick {tick}: {len(state_data.get('pheromones', []))} pheromones", flush=True)
            await broadcast({"type": "state", "data": state_data})

            # Check win condition
            if all(o.collected for o in world.objects):
                await broadcast({"type": "end", "reason": "All objects collected!"})
                break

            await asyncio.sleep(0.15)  # ~7 FPS for smoother visualization

    finally:
        # Clean up WebSocket connection
        if ws_client:
            try:
                await ws_client.close()
                print("[WS] Disconnected from DTaaS", flush=True)
            except Exception:
                pass
            ws_client = None
            ws_twin = None

    simulation_running = False
    await broadcast({"type": "stopped"})


def setup_world():
    """Initialize world and ontology."""
    global world, client, current_config

    # Create world
    num_objects = current_config["objects"]
    num_obstacles = current_config["obstacles"]
    world = create_random_world(
        num_objects=num_objects,
        num_obstacles=num_obstacles,
        width=current_config["width"],
        height=current_config["height"],
        num_robots=current_config["robots"],
        battery_capacity=current_config.get("battery", 100)
    )

    # Initialize client and ontology
    client = create_client()
    load_ontology(client)
    initialize_twin(client, world)
    setup_reasoning_rules(client)

    # Reactive control status
    if REACTIVE_CONTROL_AVAILABLE:
        print(f"[SETUP] Reactive control enabled - O(1) action selection (get_reactive_action={get_reactive_action})", flush=True)
    else:
        print("[SETUP] Reactive control NOT available - using procedural fallback", flush=True)

    print("Setup complete.", flush=True)

    return world


async def handle_websocket(websocket):
    """Handle WebSocket connections."""
    global simulation_running, simulation_task, world, current_config

    connected_clients.add(websocket)
    print(f"Client connected. Total: {len(connected_clients)}")

    try:
        # Send initial state
        if world:
            await websocket.send(json.dumps({
                "type": "state",
                "data": world_to_dict(world, 0)
            }))

        async for message in websocket:
            data = json.loads(message)

            if data.get("type") == "start":
                if not simulation_running:
                    simulation_running = True
                    simulation_task = asyncio.create_task(simulation_loop())
                    await broadcast({"type": "started"})

            elif data.get("type") == "pause":
                simulation_running = False
                if simulation_task:
                    simulation_task.cancel()
                await broadcast({"type": "paused"})

            elif data.get("type") == "reset":
                simulation_running = False
                if simulation_task:
                    simulation_task.cancel()
                await asyncio.sleep(0.3)
                setup_world()
                await broadcast({"type": "state", "data": world_to_dict(world, 0)})

            elif data.get("type") == "configure":
                simulation_running = False
                if simulation_task:
                    simulation_task.cancel()
                await asyncio.sleep(0.3)

                cfg = data.get("config", {})
                current_config = {
                    "width": cfg.get("width", 20),
                    "height": cfg.get("height", 15),
                    "robots": cfg.get("robots", 3),
                    "objects": cfg.get("objects", 12),
                    "obstacles": cfg.get("obstacles", 6),
                    "battery": cfg.get("battery", 100),
                }
                setup_world()
                await broadcast({"type": "state", "data": world_to_dict(world, 0)})

            elif data.get("type") == "get_ontology":
                ontology_data = get_ontology_state()
                await websocket.send(json.dumps({"type": "ontology", "data": ontology_data}))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"Client disconnected. Total: {len(connected_clients)}")


HTML_CONTENT = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ontology-Driven Robot Simulation</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }
        h1 { font-size: 1.4rem; font-weight: 300; margin-bottom: 15px; color: #888; }
        .container { display: flex; gap: 20px; align-items: flex-start; justify-content: center; }
        .side-panel { width: 320px; flex-shrink: 0; }
        canvas {
            background: #16213e;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        .panel {
            background: #16213e;
            border-radius: 8px;
            padding: 15px;
            width: 100%;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        .panel h2 { font-size: 0.8rem; color: #666; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
        .stat { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #252545; font-size: 0.85rem; }
        .stat:last-child { border-bottom: none; }
        .stat-value { color: #4ecdc4; font-weight: 500; }
        .controls { display: flex; gap: 8px; margin-top: 12px; }
        button {
            flex: 1; padding: 8px 12px; border: none; border-radius: 6px;
            cursor: pointer; font-size: 0.8rem; font-weight: 500; transition: all 0.2s;
        }
        .btn-start { background: #2ecc71; color: #fff; }
        .btn-start:hover { background: #27ae60; }
        .btn-pause { background: #e74c3c; color: #fff; }
        .btn-pause:hover { background: #c0392b; }
        .btn-reset { background: #3498db; color: #fff; }
        .btn-reset:hover { background: #2980b9; }
        .robot-list { margin-top: 12px; }
        .robot-item {
            display: flex; align-items: center; gap: 8px; padding: 6px 8px;
            background: #1a1a2e; border-radius: 4px; margin-bottom: 4px; font-size: 0.8rem;
            min-height: 52px; width: 100%;
        }
        .robot-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
        .robot-info { flex: 1; min-width: 0; overflow: hidden; }
        .robot-stats { color: #888; font-size: 0.7rem; white-space: nowrap; }
        .robot-action { color: #4ecdc4; font-size: 0.65rem; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 250px; }
        .status { text-align: center; padding: 6px; border-radius: 4px; margin-bottom: 10px; font-size: 0.8rem; }
        .status-running { background: #27ae60; }
        .status-paused { background: #f39c12; }
        .status-ended { background: #9b59b6; }
        .config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 8px; }
        .config-item { display: flex; flex-direction: column; gap: 2px; }
        .config-item label { font-size: 0.65rem; color: #666; text-transform: uppercase; }
        .config-item input {
            width: 100%; padding: 5px 6px; border: 1px solid #252545; border-radius: 4px;
            background: #1a1a2e; color: #eee; font-size: 0.8rem;
        }
        .config-item input:focus { outline: none; border-color: #4ecdc4; }
        .btn-apply { background: #9b59b6; color: #fff; margin-top: 8px; width: 100%; }
        .btn-apply:hover { background: #8e44ad; }
        .legend { margin-top: 12px; font-size: 0.7rem; color: #666; }
        .legend-item { display: flex; align-items: center; gap: 6px; margin: 4px 0; }
        .legend-dot { width: 12px; height: 12px; border-radius: 2px; }

        /* Tab system */
        .tabs { display: flex; gap: 0; margin-bottom: 0; border-bottom: 2px solid #252545; }
        .tab-btn {
            padding: 8px 16px; background: transparent; border: none; color: #666;
            cursor: pointer; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px;
            transition: all 0.2s; border-bottom: 2px solid transparent; margin-bottom: -2px;
        }
        .tab-btn:hover { color: #aaa; }
        .tab-btn.active { color: #4ecdc4; border-bottom-color: #4ecdc4; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* Ontology panel */
        .ontology-panel {
            background: #16213e; border-radius: 8px; padding: 12px;
            width: 100%; max-height: 70vh; overflow-y: auto;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        .onto-section { margin-bottom: 15px; }
        .onto-section h3 { font-size: 0.75rem; color: #4ecdc4; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; border-bottom: 1px solid #252545; padding-bottom: 4px; }
        .onto-table { width: 100%; border-collapse: collapse; font-size: 0.7rem; }
        .onto-table th { text-align: left; color: #888; font-weight: 500; padding: 4px 8px; background: #1a1a2e; }
        .onto-table td { padding: 4px 8px; border-bottom: 1px solid #252545; color: #ccc; }
        .onto-table tr:hover td { background: #1a1a2e; }
        .rule-card { background: #1a1a2e; border-radius: 4px; padding: 8px; margin-bottom: 6px; }
        .rule-id { color: #f39c12; font-weight: 500; font-size: 0.7rem; }
        .rule-name { color: #eee; font-size: 0.75rem; margin: 2px 0; }
        .rule-desc { color: #888; font-size: 0.65rem; }
        .rule-condition { color: #9b59b6; font-size: 0.65rem; font-family: monospace; margin-top: 4px; }
        .axiom-item { padding: 3px 6px; background: #1a1a2e; border-radius: 3px; font-size: 0.6rem; display: inline-block; }
        .axiom-class { color: #3498db; }
        .axiom-prop { color: #2ecc71; }
        .axiom-type { color: #888; font-style: italic; }
        .refresh-btn { background: #3498db; color: #fff; border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 0.7rem; margin-left: 10px; }
        .refresh-btn:hover { background: #2980b9; }
        .twin-count { color: #4ecdc4; font-size: 0.7rem; margin-left: 8px; }

        /* PDDL panel */
        .pddl-panel { background: #16213e; border-radius: 8px; padding: 12px; width: 100%; max-height: 70vh; overflow-y: auto; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
        .pddl-section { margin-bottom: 15px; }
        .pddl-section h3 { font-size: 0.75rem; color: #4ecdc4; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; border-bottom: 1px solid #252545; padding-bottom: 4px; }
        .pddl-code { background: #1a1a2e; padding: 10px; border-radius: 4px; font-family: 'Monaco', 'Consolas', monospace; font-size: 0.65rem; line-height: 1.4; white-space: pre-wrap; color: #ccc; }
        .pddl-info { background: #1a1a2e; padding: 8px 12px; border-radius: 4px; margin-bottom: 12px; font-size: 0.7rem; }
        .pddl-info span { color: #4ecdc4; }
        .pddl-code .keyword { color: #e74c3c; }
        .pddl-code .type { color: #9b59b6; }
        .pddl-code .predicate { color: #3498db; }
        .pddl-code .action { color: #2ecc71; font-weight: bold; }
        .pddl-code .comment { color: #666; font-style: italic; }
    </style>
</head>
<body>
    <h1>Ontology-Driven Robot Simulation</h1>
    <div class="container">
        <canvas id="canvas"></canvas>

        <!-- Side Panel with Tabs -->
        <div class="side-panel">
            <div class="tabs">
                <button class="tab-btn active" data-tab="simulation">Simulation</button>
                <button class="tab-btn" data-tab="ontology">Ontology</button>
                <button class="tab-btn" data-tab="pddl">PDDL</button>
            </div>

            <!-- Simulation Tab -->
            <div class="tab-content active" id="tab-simulation">
                <div class="panel" style="border-top-left-radius: 0;">
            <div id="status" class="status status-paused">Paused</div>
            <h2>Statistics</h2>
            <div class="stat"><span>Tick</span><span class="stat-value" id="tick">0</span></div>
            <div class="stat"><span>Objects</span><span class="stat-value" id="objects">0 / 0</span></div>
            <div class="stat"><span>Collisions</span><span class="stat-value" id="collisions">0</span></div>
            <div class="controls">
                <button class="btn-start" id="startBtn">Start</button>
                <button class="btn-pause" id="pauseBtn">Pause</button>
                <button class="btn-reset" id="resetBtn">Reset</button>
            </div>
            <div class="robot-list" id="robotList"></div>

            <h2 style="margin-top: 15px;">Configuration</h2>
            <div class="config-grid">
                <div class="config-item"><label>Width</label><input type="number" id="cfgWidth" value="40" min="10" max="50"></div>
                <div class="config-item"><label>Height</label><input type="number" id="cfgHeight" value="25" min="10" max="40"></div>
                <div class="config-item"><label>Robots</label><input type="number" id="cfgRobots" value="5" min="1" max="6"></div>
                <div class="config-item"><label>Objects</label><input type="number" id="cfgObjects" value="15" min="1" max="30"></div>
                <div class="config-item"><label>Obstacles</label><input type="number" id="cfgObstacles" value="20" min="0" max="20"></div>
                <div class="config-item"><label>Battery</label><input type="number" id="cfgBattery" value="100" min="10" max="1000"></div>
            </div>
            <button class="btn-apply" id="applyBtn">Apply & Reset</button>

            <div class="legend">
                <div class="legend-item"><div class="legend-dot" style="background: #f1c40f;"></div> Object (collectible)</div>
                <div class="legend-item"><div class="legend-dot" style="background: #555;"></div> Obstacle</div>
                <div class="legend-item"><div class="legend-dot" style="background: #4ecdc455; border: 1px solid #4ecdc4;"></div> Sensor range</div>
            </div>
                </div>
            </div>

            <!-- Ontology Tab -->
            <div class="tab-content" id="tab-ontology">
                <div class="ontology-panel" style="border-top-left-radius: 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <h2 style="margin: 0;">Ontology State</h2>
                        <button class="refresh-btn" id="refreshOntology">↻ Refresh</button>
                    </div>

                    <!-- Twins Section -->
                    <div class="onto-section">
                        <h3>Digital Twins (ABox Individuals) <span class="twin-count" id="twinCount"></span></h3>
                        <div id="twinsContent">
                            <table class="onto-table">
                                <thead><tr><th>Type</th><th>ID</th><th>Key Properties</th></tr></thead>
                                <tbody id="twinsTable"></tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Rules Section -->
                    <div class="onto-section">
                        <h3>SWRL Reasoning Rules <span class="twin-count" id="ruleCount"></span></h3>
                        <div id="rulesContent"></div>
                    </div>

                    <!-- TBox Section -->
                    <div class="onto-section">
                        <h3>TBox (Schema & Axioms)</h3>
                        <div>
                            <h4 style="font-size: 0.65rem; color: #888; margin-bottom: 4px;">Classes</h4>
                            <div id="classesContent" style="display: flex; flex-wrap: wrap; gap: 3px;"></div>
                        </div>
                        <div style="margin-top: 8px;">
                            <h4 style="font-size: 0.65rem; color: #888; margin-bottom: 4px;">Properties</h4>
                            <div id="propertiesContent" style="max-height: 150px; overflow-y: auto;"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- PDDL Tab -->
            <div class="tab-content" id="tab-pddl">
                <div class="pddl-panel" style="border-top-left-radius: 0;">
                    <h2 style="margin: 0 0 10px 0; font-size: 0.8rem; color: #666; text-transform: uppercase; letter-spacing: 1px;">PDDL Domain</h2>

                    <div class="pddl-info">
                        <div>Domain: <span id="pddlDomainName">robot-exploration-strips</span></div>
                        <div>Requirements: <span id="pddlRequirements">:strips :typing :negative-preconditions</span></div>
                        <div>Actions: <span id="pddlActionCount">4</span></div>
                    </div>

                    <div class="pddl-section">
                        <h3>Types</h3>
                        <div class="pddl-code" id="pddlTypes"></div>
                    </div>

                    <div class="pddl-section">
                        <h3>Predicates</h3>
                        <div class="pddl-code" id="pddlPredicates"></div>
                    </div>

                    <div class="pddl-section">
                        <h3>Actions</h3>
                        <div id="pddlActions"></div>
                    </div>

                    <div class="pddl-section">
                        <h3>Full Domain Definition</h3>
                        <div class="pddl-code" id="pddlFullDomain" style="max-height: 300px; overflow-y: auto;"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const CELL_SIZE = 28;
        let state = null, ws = null, isRunning = false;
        let revealedCells = new Set();  // Persistent set of revealed cells

        // PDDL Domain Definition
        const PDDL_DOMAIN = `(define (domain robot-exploration-strips)
  (:requirements :strips :typing :negative-preconditions)

  (:types
    robot
    location
    object
  )

  (:predicates
    ;; Spatial state
    (at ?r - robot ?l - location)
    (adjacent ?l1 - location ?l2 - location)
    (obstacle ?l - location)
    (base ?l - location)

    ;; Object state
    (object-at ?o - object ?l - location)
    (collected ?o - object)
    (carrying ?r - robot ?o - object)

    ;; Robot state
    (low-battery ?r - robot)
    (at-base ?r - robot)
    (explored ?r - robot ?l - location)
  )

  (:action move
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (not (low-battery ?r))
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
      (explored ?r ?to)
      (not (at-base ?r))
    )
  )

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

  (:action return-to-base
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and
      (at ?r ?from)
      (adjacent ?from ?to)
      (not (obstacle ?to))
      (low-battery ?r)
    )
    :effect (and
      (at ?r ?to)
      (not (at ?r ?from))
    )
  )

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
)`;

        function highlightPddl(code) {
            return code
                .replace(/(;;.*)/g, '<span class="comment">$1</span>')
                .replace(/(:requirements|:types|:predicates|:action|:parameters|:precondition|:effect)/g, '<span class="keyword">$1</span>')
                .replace(/- (robot|location|object)/g, '- <span class="type">$1</span>')
                .replace(/\\((at|adjacent|obstacle|base|object-at|collected|carrying|low-battery|at-base|explored)\\s/g, '(<span class="predicate">$1</span> ')
                .replace(/\\((and|not|or)\\s/g, '(<span class="keyword">$1</span> ');
        }

        function renderPddlTab() {
            // Extract types
            const typesMatch = PDDL_DOMAIN.match(/\\(:types([\\s\\S]*?)\\)/);
            const typesContent = typesMatch ? typesMatch[1].trim() : '';
            document.getElementById('pddlTypes').innerHTML = highlightPddl(typesContent);

            // Extract predicates
            const predicatesMatch = PDDL_DOMAIN.match(/\\(:predicates([\\s\\S]*?)\\)\\s*\\(:action/);
            const predicatesContent = predicatesMatch ? predicatesMatch[1].trim() : '';
            document.getElementById('pddlPredicates').innerHTML = highlightPddl(predicatesContent);

            // Extract and render actions
            const actionMatches = PDDL_DOMAIN.matchAll(/\\(:action\\s+(\\w+)([\\s\\S]*?)(?=\\(:action|\\)\\s*$)/g);
            const actionsHtml = Array.from(actionMatches).map(match => {
                const actionName = match[1];
                const actionBody = match[2].trim();
                return '<div class="pddl-code" style="margin-bottom: 8px;"><span class="action">(:action ' + actionName + '</span>\\n' + highlightPddl(actionBody) + '</div>';
            }).join('');
            document.getElementById('pddlActions').innerHTML = actionsHtml;

            // Render full domain
            document.getElementById('pddlFullDomain').innerHTML = highlightPddl(PDDL_DOMAIN);
        }

        function connect() {
            ws = new WebSocket(`ws://${location.hostname}:8001`);
            ws.onopen = () => console.log('Connected to simulation');
            ws.onclose = () => setTimeout(connect, 1000);
            ws.onerror = (e) => console.error('WebSocket error:', e);
            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'state') {
                    const first = !state;
                    state = msg.data;
                    render();
                    updateStats();
                    if (first) updateConfigInputs();
                } else if (msg.type === 'end') {
                    isRunning = false;
                    updateStatus('ended', msg.reason);
                } else if (msg.type === 'started') {
                    isRunning = true;
                    updateStatus('running');
                } else if (msg.type === 'paused' || msg.type === 'stopped') {
                    isRunning = false;
                    updateStatus('paused');
                } else if (msg.type === 'ontology') {
                    renderOntology(msg.data);
                }
            };
        }

        function render() {
            if (!state) return;
            const width = state.width * CELL_SIZE, height = state.height * CELL_SIZE;
            if (canvas.width !== width || canvas.height !== height) {
                canvas.width = width; canvas.height = height;
            }
            ctx.fillStyle = '#16213e'; ctx.fillRect(0, 0, width, height);

            // Grid
            ctx.strokeStyle = '#252545'; ctx.lineWidth = 1;
            for (let x = 0; x <= state.width; x++) { ctx.beginPath(); ctx.moveTo(x * CELL_SIZE, 0); ctx.lineTo(x * CELL_SIZE, height); ctx.stroke(); }
            for (let y = 0; y <= state.height; y++) { ctx.beginPath(); ctx.moveTo(0, y * CELL_SIZE); ctx.lineTo(width, y * CELL_SIZE); ctx.stroke(); }

            // Pheromone trails (small dots matching robot color)
            if (state.pheromones && state.pheromones.length > 0) {
                for (const p of state.pheromones) {
                    const size = 1.5 + p.strength;  // 1.5-2.5px dots
                    ctx.globalAlpha = 0.2 + p.strength * 0.3;
                    ctx.fillStyle = p.color;
                    ctx.beginPath();
                    ctx.arc(p.x * CELL_SIZE, p.y * CELL_SIZE, size, 0, Math.PI * 2);
                    ctx.fill();
                }
                ctx.globalAlpha = 1;
            }

            // Obstacles (stone-like rectangles with rough edges)
            for (const obs of state.obstacles) {
                const ox = obs.x * CELL_SIZE;
                const oy = obs.y * CELL_SIZE;
                const r = obs.radius * CELL_SIZE;
                // Create irregular stone shape
                ctx.fillStyle = '#3d3d3d';
                ctx.beginPath();
                // Irregular polygon for stone effect
                const points = 6 + Math.floor(obs.radius * 2);
                const angleStep = (Math.PI * 2) / points;
                for (let i = 0; i < points; i++) {
                    const angle = i * angleStep + (obs.x * 0.5);  // Seed variation by position
                    const variation = 0.7 + 0.3 * Math.sin(i * 2.5 + obs.y);
                    const px = ox + Math.cos(angle) * r * variation;
                    const py = oy + Math.sin(angle) * r * variation;
                    if (i === 0) ctx.moveTo(px, py);
                    else ctx.lineTo(px, py);
                }
                ctx.closePath();
                ctx.fill();
                // Stone texture/highlight
                ctx.strokeStyle = '#555';
                ctx.lineWidth = 2;
                ctx.stroke();
                // Inner shadow
                ctx.fillStyle = '#2a2a2a';
                ctx.beginPath();
                ctx.arc(ox + r * 0.15, oy + r * 0.15, r * 0.5, 0, Math.PI * 2);
                ctx.fill();
            }

            // Objects
            for (const obj of state.objects) {
                if (obj.collected) continue;
                const size = 5 + obj.value / 10;
                ctx.fillStyle = '#f1c40f'; ctx.shadowColor = '#f1c40f'; ctx.shadowBlur = 8;
                ctx.beginPath(); ctx.arc(obj.x * CELL_SIZE, obj.y * CELL_SIZE, size, 0, Math.PI * 2); ctx.fill();
                ctx.shadowBlur = 0;
            }

            // Robots
            for (const robot of state.robots) {
                const x = robot.x * CELL_SIZE, y = robot.y * CELL_SIZE;
                const angle = robot.heading * Math.PI / 180;

                // Sensor range
                ctx.fillStyle = robot.color + '12';
                ctx.beginPath(); ctx.arc(x, y, robot.sensorRange * CELL_SIZE, 0, Math.PI * 2); ctx.fill();

                // Body
                ctx.save(); ctx.translate(x, y); ctx.rotate(angle);
                ctx.fillStyle = robot.color;
                ctx.beginPath(); ctx.moveTo(10, 0); ctx.lineTo(-6, -6); ctx.lineTo(-3, 0); ctx.lineTo(-6, 6); ctx.closePath(); ctx.fill();

                // Stuck indicator
                if (robot.isStuck || robot.inLoop) {
                    ctx.strokeStyle = '#e74c3c'; ctx.lineWidth = 2;
                    ctx.beginPath(); ctx.arc(0, 0, 12, 0, Math.PI * 2); ctx.stroke();
                }
                ctx.restore();

                // Label
                ctx.fillStyle = '#fff'; ctx.font = 'bold 9px sans-serif'; ctx.textAlign = 'center';
                ctx.fillText(robot.id.replace('robot', 'R'), x, y - 14);
            }

            // Fog of war - permanently reveal cells within sensor range
            // Add all cells within current sensor range of each robot to persistent set
            for (const robot of state.robots) {
                const range = robot.sensorRange;
                const rx = robot.x, ry = robot.y;
                for (let dx = -Math.ceil(range); dx <= Math.ceil(range); dx++) {
                    for (let dy = -Math.ceil(range); dy <= Math.ceil(range); dy++) {
                        const cx = Math.floor(rx + dx);
                        const cy = Math.floor(ry + dy);
                        if (cx >= 0 && cx < state.width && cy >= 0 && cy < state.height) {
                            const dist = Math.sqrt(dx * dx + dy * dy);
                            if (dist <= range) {
                                revealedCells.add(`${cx},${cy}`);
                            }
                        }
                    }
                }
            }

            // Draw fog over non-revealed cells
            ctx.fillStyle = '#0a0a15';
            for (let gx = 0; gx < state.width; gx++) {
                for (let gy = 0; gy < state.height; gy++) {
                    if (!revealedCells.has(`${gx},${gy}`)) {
                        ctx.fillRect(gx * CELL_SIZE, gy * CELL_SIZE, CELL_SIZE, CELL_SIZE);
                    }
                }
            }
        }

        function updateStats() {
            if (!state) return;
            document.getElementById('tick').textContent = state.tick;
            document.getElementById('objects').textContent = `${state.stats.collectedObjects} / ${state.stats.totalObjects}`;
            document.getElementById('collisions').textContent = state.stats.totalCollisions;

            document.getElementById('robotList').innerHTML = state.robots.map(r => {
                const isEscaping = r.action && r.action.includes('ESCAPE');
                const isInLoop = r.inLoop;
                const indicator = isEscaping ? ' 🚀' : (isInLoop ? ' 🔄' : '');
                const areaStr = r.coverageArea > 0 ? r.coverageArea.toFixed(1) : '-';
                return `
                <div class="robot-item">
                    <div class="robot-dot" style="background: ${r.color}"></div>
                    <div class="robot-info">
                        <div>${r.id.replace('robot', 'Robot ')}${indicator}</div>
                        <div class="robot-stats">${r.objectsCollected} obj | ${r.collisionCount} col | area: ${areaStr}</div>
                        <div class="robot-action" title="${r.action || ''}">${r.action || (r.isExploring ? 'Exploring' : 'Seeking')}</div>
                    </div>
                </div>
            `}).join('');
        }

        function updateStatus(status, text) {
            const el = document.getElementById('status');
            el.className = 'status status-' + status;
            el.textContent = text || (status === 'running' ? 'Running (SWRL reasoning)' : status === 'paused' ? 'Paused' : 'Ended');
        }

        function updateConfigInputs() {
            if (!state) return;
            document.getElementById('cfgWidth').value = state.width;
            document.getElementById('cfgHeight').value = state.height;
            document.getElementById('cfgRobots').value = state.robots.length;
            document.getElementById('cfgObjects').value = state.stats.totalObjects;
            document.getElementById('cfgObstacles').value = state.obstacles.length;
        }

        document.getElementById('startBtn').onclick = () => {
            if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({type: 'start'}));
        };
        document.getElementById('pauseBtn').onclick = () => {
            if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({type: 'pause'}));
        };
        document.getElementById('resetBtn').onclick = () => {
            revealedCells = new Set();  // Clear fog of war
            if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({type: 'reset'}));
        };
        document.getElementById('applyBtn').onclick = () => {
            revealedCells = new Set();  // Clear fog of war
            if (ws?.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'configure',
                    config: {
                        width: parseInt(document.getElementById('cfgWidth').value) || 40,
                        height: parseInt(document.getElementById('cfgHeight').value) || 25,
                        robots: parseInt(document.getElementById('cfgRobots').value) || 3,
                        objects: parseInt(document.getElementById('cfgObjects').value) || 15,
                        obstacles: parseInt(document.getElementById('cfgObstacles').value) || 20,
                        battery: parseInt(document.getElementById('cfgBattery').value) || 100
                    }
                }));
            }
        };

        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.onclick = () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
                if (btn.dataset.tab === 'ontology') refreshOntology();
            };
        });

        // Ontology data (will be populated from state)
        let ontologyData = null;

        function refreshOntology() {
            if (ws?.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'get_ontology'}));
            }
        }

        function renderOntology(data) {
            ontologyData = data;

            // Render twins table
            const twins = data.twins || [];
            document.getElementById('twinCount').textContent = `(${twins.length})`;
            document.getElementById('twinsTable').innerHTML = twins.map(t => `
                <tr>
                    <td><span style="color: ${t.type === 'Robot' ? '#3498db' : t.type === 'Object' ? '#f1c40f' : '#888'}">${t.type}</span></td>
                    <td style="font-family: monospace; font-size: 0.65rem;">${t.id}</td>
                    <td style="font-size: 0.6rem; color: #888;">${t.properties || '-'}</td>
                </tr>
            `).join('');

            // Render rules
            const rules = data.rules || [];
            document.getElementById('ruleCount').textContent = `(${rules.length})`;
            document.getElementById('rulesContent').innerHTML = rules.map(r => `
                <div class="rule-card">
                    <div class="rule-id">${r.id}</div>
                    <div class="rule-name">${r.name}</div>
                    <div class="rule-desc">${r.description}</div>
                    <div class="rule-condition">${r.condition} → ${r.target}</div>
                </div>
            `).join('');

            // Render TBox classes
            const classes = data.classes || [];
            document.getElementById('classesContent').innerHTML = classes.map(c => `
                <div class="axiom-item"><span class="axiom-class">${c}</span></div>
            `).join('');

            // Render TBox properties
            const properties = data.properties || [];
            document.getElementById('propertiesContent').innerHTML = properties.map(p => `
                <div class="axiom-item"><span class="axiom-prop">${p.name}</span> <span class="axiom-type">(${p.type})</span></div>
            `).join('');
        }

        document.getElementById('refreshOntology').onclick = refreshOntology;

        connect();
    </script>
</body>
</html>
'''


class HTMLHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            # Replace the hardcoded WebSocket port with the configured one
            html = HTML_CONTENT.replace(':8001`', f':{ws_port}`')
            self.wfile.write(html.encode())
        else:
            self.send_error(404)

    def log_message(self, *_):
        pass


def run_http_server(port):
    server = HTTPServer(('', port), HTMLHandler)
    server.serve_forever()


async def main():
    global max_ticks, current_config, ws_port

    parser = argparse.ArgumentParser(description='Web-based Ontology-Driven Robot Simulation')
    parser.add_argument('--port', type=int, default=8090, help='HTTP port')
    parser.add_argument('--ws-port', type=int, default=8091, help='WebSocket port')
    parser.add_argument('--width', type=int, default=40, help='Grid width')
    parser.add_argument('--height', type=int, default=25, help='Grid height')
    parser.add_argument('--robots', type=int, default=5, help='Number of robots')
    parser.add_argument('--objects', type=int, default=15, help='Number of objects')
    parser.add_argument('--obstacles', type=int, default=20, help='Number of obstacles')
    parser.add_argument('--battery', type=int, default=100, help='Battery capacity')
    parser.add_argument('--ticks', type=int, default=500, help='Max ticks')
    args = parser.parse_args()

    max_ticks = args.ticks
    ws_port = args.ws_port
    current_config = {
        "width": args.width,
        "height": args.height,
        "robots": args.robots,
        "objects": args.objects,
        "obstacles": args.obstacles,
        "battery": args.battery,
    }

    # Enable quiet mode to suppress simulation logs
    enable_quiet_mode()

    # Initialize world and ontology
    print("Initializing ontology-driven simulation...")
    try:
        setup_world()
        print("Ontology and SWRL rules loaded.")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure tesseraidb is running!")
        return

    # Start HTTP server
    http_thread = threading.Thread(target=run_http_server, args=(args.port,), daemon=True)
    http_thread.start()

    print(f"\n  Ontology-Driven Robot Simulation")
    print(f"  ==================================")
    print(f"  Open http://localhost:{args.port} in your browser")
    print(f"  Press Ctrl+C to stop\n")

    async with websockets.serve(handle_websocket, "0.0.0.0", args.ws_port):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
