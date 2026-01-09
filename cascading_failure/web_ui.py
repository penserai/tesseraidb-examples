#!/usr/bin/env python3
"""
Cascading Failure Analysis - Interactive Web UI
================================================

A production-grade web interface for visualizing infrastructure dependencies
and simulating cascading failures in real-time.

Features:
- Interactive network graph visualization
- Real-time failure cascade animation
- Multiple failure scenarios
- Blast radius analysis
- Single point of failure detection

Usage:
    python web_ui.py [--port 8108]

Then open http://localhost:8108 in your browser.

Requires:
    pip install websockets
"""

import asyncio
import json
import argparse
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict
from enum import Enum

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Global state
client = None
components: Dict[str, dict] = {}
forward_deps: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
reverse_deps: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
connected_clients: Set = set()
simulation_running = False
ws_port = 8091


class ComponentStatus(Enum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    FAILED = "failed"


component_status: Dict[str, ComponentStatus] = {}
cascade_events: List[dict] = []


def _normalize_properties(properties: dict) -> dict:
    """Normalize property names by stripping domain prefixes."""
    normalized = {}
    for key, value in properties.items():
        if '#' in key:
            short_key = key.split('#', 1)[1]
        else:
            short_key = key
        normalized[short_key] = value
    return normalized


def _normalize_rel_type(rel_type: str) -> str:
    """Normalize relationship type by stripping domain prefixes."""
    if '#' in rel_type:
        rel_type = rel_type.split('#', 1)[1]
    if rel_type.startswith('rel/'):
        rel_type = rel_type[4:]
    return rel_type


def load_infrastructure():
    """Load infrastructure data from DTaaS."""
    global components, forward_deps, reverse_deps, component_status

    components = {}
    forward_deps = defaultdict(list)
    reverse_deps = defaultdict(list)
    component_status = {}

    try:
        twins = client.twins.list(domain="cascading_failure", page_size=200)

        for twin in twins:
            twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
            component_id = twin_dict["id"]

            type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
            raw_props = twin_dict.get("properties", {})

            components[component_id] = {
                "id": component_id,
                "name": twin_dict.get("name", component_id),
                "type": type_val.split("#")[-1] if type_val else "",
                "properties": _normalize_properties(raw_props),
            }
            component_status[component_id] = ComponentStatus.OPERATIONAL

        # Load relationships
        for component_id in components:
            try:
                relationships = client.twins.get_relationships(component_id)
                for rel in relationships:
                    rel_type = _normalize_rel_type(rel.get("type", ""))
                    other_twin = rel.get("twin", rel.get("target", ""))
                    direction = rel.get("direction", "outgoing")

                    if other_twin and other_twin in components:
                        if direction == "outgoing":
                            forward_deps[component_id].append((other_twin, rel_type))
                            reverse_deps[other_twin].append((component_id, rel_type))
                        else:
                            forward_deps[other_twin].append((component_id, rel_type))
                            reverse_deps[component_id].append((other_twin, rel_type))
            except Exception:
                pass

        logger.info(f"Loaded {len(components)} components with "
                   f"{sum(len(d) for d in forward_deps.values())} dependencies")

    except Exception as e:
        logger.error(f"Failed to load infrastructure: {e}")
        raise


def get_graph_data() -> dict:
    """Convert infrastructure to graph visualization format."""
    nodes = []
    edges = []

    # Type to color mapping
    type_colors = {
        "Substation": "#e74c3c",
        "PowerFeed": "#c0392b",
        "UPSSystem": "#f39c12",
        "Generator": "#d35400",
        "NetworkSwitch": "#3498db",
        "ServerRack": "#2ecc71",
        "CoolingUnit": "#1abc9c",
        "Application": "#9b59b6",
        "Database": "#8e44ad",
        "ProductionLine": "#e91e63",
        "ManufacturingEquipment": "#ff5722",
        "LogisticsHub": "#795548",
        "PowerPlant": "#607d8b",
    }

    for comp_id, comp in components.items():
        status = component_status.get(comp_id, ComponentStatus.OPERATIONAL)
        comp_type = comp.get("type", "Unknown")
        props = comp.get("properties", {})

        nodes.append({
            "id": comp_id,
            "label": comp.get("name", comp_id).replace("urn:tesserai:twin:", ""),
            "type": comp_type,
            "color": type_colors.get(comp_type, "#666"),
            "status": status.value,
            "criticality": props.get("criticality", "medium"),
            "redundancyLevel": props.get("redundancyLevel", 0),
        })

    edge_id = 0
    seen_edges = set()
    for source_id, deps in forward_deps.items():
        for target_id, rel_type in deps:
            edge_key = f"{source_id}->{target_id}"
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "type": rel_type,
                })
                edge_id += 1

    return {"nodes": nodes, "edges": edges}


def calculate_blast_radius(component_id: str) -> Tuple[int, List[str]]:
    """Calculate blast radius for a component."""
    affected = set([component_id])
    affected_list = [component_id]
    queue = [component_id]

    while queue:
        current = queue.pop(0)
        for dependent, _ in reverse_deps.get(current, []):
            if dependent not in affected and dependent in components:
                affected.add(dependent)
                affected_list.append(dependent)
                queue.append(dependent)

    return len(affected), affected_list


async def simulate_cascade(trigger_id: str):
    """Simulate a cascading failure with real-time updates."""
    global component_status, cascade_events, simulation_running

    # Reset all components
    for comp_id in components:
        component_status[comp_id] = ComponentStatus.OPERATIONAL
    cascade_events = []

    # Resolve short ID to full URN if needed
    if trigger_id not in components:
        full_id = f"urn:tesserai:twin:{trigger_id}"
        if full_id in components:
            trigger_id = full_id

    if trigger_id not in components:
        await broadcast({"type": "error", "message": f"Component {trigger_id} not found"})
        return

    simulation_running = True
    await broadcast({"type": "simulation_started", "trigger": trigger_id})

    # Initial failure
    component_status[trigger_id] = ComponentStatus.FAILED
    cascade_events.append({
        "time": 0,
        "component": trigger_id,
        "status": "failed",
        "via": "trigger",
    })

    await broadcast({
        "type": "cascade_event",
        "event": cascade_events[-1],
        "graph": get_graph_data(),
    })
    await asyncio.sleep(0.5)

    # Propagate failure
    queue = [(trigger_id, 0)]
    processed = set([trigger_id])
    tick = 0

    while queue and simulation_running:
        current_id, depth = queue.pop(0)
        tick += 1

        # Get dependents (components that depend on this one)
        for dependent_id, rel_type in reverse_deps.get(current_id, []):
            if dependent_id in processed:
                continue

            processed.add(dependent_id)
            comp = components.get(dependent_id, {})
            props = comp.get("properties", {})
            redundancy = props.get("redundancyLevel", 0)
            # Convert to int if it's a string
            try:
                redundancy = int(redundancy) if redundancy else 0
            except (ValueError, TypeError):
                redundancy = 0

            # Check if component fails
            if redundancy > 0:
                component_status[dependent_id] = ComponentStatus.DEGRADED
                status = "degraded"
            else:
                component_status[dependent_id] = ComponentStatus.FAILED
                status = "failed"
                queue.append((dependent_id, depth + 1))

            cascade_events.append({
                "time": tick,
                "component": dependent_id,
                "status": status,
                "via": rel_type,
                "from": current_id,
            })

            await broadcast({
                "type": "cascade_event",
                "event": cascade_events[-1],
                "graph": get_graph_data(),
            })
            await asyncio.sleep(0.3)

    simulation_running = False

    # Calculate summary
    failed = sum(1 for s in component_status.values() if s == ComponentStatus.FAILED)
    degraded = sum(1 for s in component_status.values() if s == ComponentStatus.DEGRADED)

    await broadcast({
        "type": "simulation_complete",
        "summary": {
            "trigger": trigger_id,
            "totalAffected": failed + degraded,
            "failed": failed,
            "degraded": degraded,
            "cascadeDepth": max((e["time"] for e in cascade_events), default=0),
            "events": len(cascade_events),
        },
        "graph": get_graph_data(),
    })


def find_single_points_of_failure() -> List[dict]:
    """Find components that are single points of failure."""
    spofs = []

    for comp_id in components:
        blast_size, affected = calculate_blast_radius(comp_id)
        props = components[comp_id].get("properties", {})

        if blast_size > 3 and props.get("redundancyLevel", 0) == 0:
            spofs.append({
                "component": comp_id,
                "name": components[comp_id].get("name", comp_id),
                "type": components[comp_id].get("type", "Unknown"),
                "blastRadius": blast_size,
                "criticality": props.get("criticality", "medium"),
            })

    return sorted(spofs, key=lambda x: -x["blastRadius"])[:20]


async def broadcast(message: dict):
    """Broadcast message to all connected clients."""
    if connected_clients:
        msg = json.dumps(message)
        await asyncio.gather(*[client.send(msg) for client in connected_clients])


async def handle_websocket(websocket):
    """Handle WebSocket connections."""
    global simulation_running

    connected_clients.add(websocket)
    print(f"Client connected. Total: {len(connected_clients)}")

    try:
        # Send initial state
        await websocket.send(json.dumps({
            "type": "init",
            "graph": get_graph_data(),
            "spofs": find_single_points_of_failure(),
            "scenarios": get_scenarios(),
        }))

        async for message in websocket:
            data = json.loads(message)

            if data.get("type") == "simulate":
                trigger = data.get("trigger")
                if trigger and not simulation_running:
                    asyncio.create_task(simulate_cascade(trigger))

            elif data.get("type") == "reset":
                simulation_running = False
                await asyncio.sleep(0.2)
                for comp_id in components:
                    component_status[comp_id] = ComponentStatus.OPERATIONAL
                await websocket.send(json.dumps({
                    "type": "reset",
                    "graph": get_graph_data(),
                }))

            elif data.get("type") == "reload":
                simulation_running = False
                await asyncio.sleep(0.2)
                load_infrastructure()
                await websocket.send(json.dumps({
                    "type": "init",
                    "graph": get_graph_data(),
                    "spofs": find_single_points_of_failure(),
                    "scenarios": get_scenarios(),
                }))

            elif data.get("type") == "blast_radius":
                comp_id = data.get("component")
                if comp_id:
                    if comp_id not in components:
                        full_id = f"urn:tesserai:twin:{comp_id}"
                        if full_id in components:
                            comp_id = full_id

                    size, affected = calculate_blast_radius(comp_id)
                    await websocket.send(json.dumps({
                        "type": "blast_radius",
                        "component": comp_id,
                        "size": size,
                        "affected": affected,
                    }))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"Client disconnected. Total: {len(connected_clients)}")


def get_scenarios() -> List[dict]:
    """Get predefined failure scenarios."""
    return [
        {"id": "power-outage", "trigger": "sub-trans-001", "name": "Power Outage", "description": "Major substation failure"},
        {"id": "datacenter-power", "trigger": "dc-power-feed-a", "name": "DC Power Feed", "description": "Data center power feed A failure"},
        {"id": "cooling-failure", "trigger": "dc-chiller-plant", "name": "Cooling Failure", "description": "Central chiller plant failure"},
        {"id": "network-partition", "trigger": "dc-core-sw-001", "name": "Network Partition", "description": "Core switch failure"},
        {"id": "generator-failure", "trigger": "dc-gen-001", "name": "Generator Failure", "description": "Backup generator failure"},
    ]


HTML_CONTENT = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cascading Failure Analysis</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            overflow: hidden;
        }
        .header {
            background: rgba(0,0,0,0.3);
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #333;
        }
        .header h1 {
            font-size: 1.3rem;
            font-weight: 400;
            color: #4ecdc4;
        }
        .header-stats {
            display: flex;
            gap: 20px;
            font-size: 0.85rem;
        }
        .header-stat { color: #888; }
        .header-stat span { color: #4ecdc4; font-weight: 500; }
        .main-container {
            display: flex;
            height: calc(100vh - 50px);
        }
        .graph-container {
            flex: 1;
            position: relative;
        }
        #graph-canvas {
            width: 100%;
            height: 100%;
            background: transparent;
        }
        .side-panel {
            width: 340px;
            background: rgba(0,0,0,0.4);
            border-left: 1px solid #333;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .panel-section {
            padding: 15px;
            border-bottom: 1px solid #333;
        }
        .panel-section h3 {
            font-size: 0.75rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        .scenario-list {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .scenario-btn {
            background: #252545;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 10px 12px;
            cursor: pointer;
            text-align: left;
            transition: all 0.2s;
        }
        .scenario-btn:hover {
            background: #2d2d5a;
            border-color: #4ecdc4;
        }
        .scenario-btn .name {
            color: #fff;
            font-size: 0.85rem;
            font-weight: 500;
        }
        .scenario-btn .desc {
            color: #666;
            font-size: 0.7rem;
            margin-top: 2px;
        }
        .controls {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }
        .btn {
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 500;
            transition: all 0.2s;
        }
        .btn-danger { background: #e74c3c; color: #fff; }
        .btn-danger:hover { background: #c0392b; }
        .btn-primary { background: #3498db; color: #fff; }
        .btn-primary:hover { background: #2980b9; }
        .spof-list {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
        }
        .spof-item {
            background: #1a1a2e;
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }
        .spof-item:hover {
            border-color: #e74c3c;
        }
        .spof-item .name {
            color: #fff;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .spof-item .meta {
            display: flex;
            justify-content: space-between;
            margin-top: 4px;
            font-size: 0.7rem;
        }
        .spof-item .type { color: #888; }
        .spof-item .blast {
            color: #e74c3c;
            font-weight: 500;
        }
        .event-log {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 0.7rem;
            background: #0d0d1a;
        }
        .event {
            padding: 4px 8px;
            border-radius: 3px;
            margin-bottom: 2px;
        }
        .event.failed { background: rgba(231, 76, 60, 0.2); color: #e74c3c; }
        .event.degraded { background: rgba(243, 156, 18, 0.2); color: #f39c12; }
        .event.info { background: rgba(52, 152, 219, 0.2); color: #3498db; }
        .summary-panel {
            background: #1a1a2e;
            border-radius: 8px;
            padding: 15px;
            margin: 10px;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .summary-stat {
            text-align: center;
            padding: 10px;
            background: #252545;
            border-radius: 6px;
        }
        .summary-stat .value {
            font-size: 1.5rem;
            font-weight: 600;
            color: #4ecdc4;
        }
        .summary-stat .label {
            font-size: 0.7rem;
            color: #888;
            margin-top: 2px;
        }
        .summary-stat.danger .value { color: #e74c3c; }
        .summary-stat.warning .value { color: #f39c12; }
        .legend {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            padding: 10px 15px;
            background: rgba(0,0,0,0.2);
            border-top: 1px solid #333;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 4px;
            font-size: 0.65rem;
            color: #888;
        }
        .legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 2px;
        }
        .status-indicator {
            position: absolute;
            top: 10px;
            left: 10px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 500;
        }
        .status-indicator.running {
            background: #e74c3c;
            color: #fff;
            animation: pulse 1s infinite;
        }
        .status-indicator.idle {
            background: #2ecc71;
            color: #fff;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        @keyframes nodePulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.3); }
        }
        @keyframes nodeShake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-3px); }
            75% { transform: translateX(3px); }
        }
        .zoom-controls {
            position: absolute;
            bottom: 20px;
            left: 20px;
            display: flex;
            gap: 5px;
        }
        .zoom-btn {
            width: 36px;
            height: 36px;
            border: none;
            border-radius: 6px;
            background: #252545;
            color: #fff;
            font-size: 1.2rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .zoom-btn:hover { background: #3498db; }
        .tooltip {
            position: absolute;
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 10px;
            font-size: 0.75rem;
            pointer-events: none;
            z-index: 1000;
            max-width: 250px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }
        .tooltip .title { color: #4ecdc4; font-weight: 500; margin-bottom: 5px; }
        .tooltip .info { color: #888; margin: 2px 0; }
        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Cascading Failure Analysis</h1>
        <div class="header-stats">
            <div class="header-stat">Components: <span id="totalComponents">0</span></div>
            <div class="header-stat">Dependencies: <span id="totalDeps">0</span></div>
            <div class="header-stat">SPOFs: <span id="totalSpofs">0</span></div>
        </div>
    </div>

    <div class="main-container">
        <div class="graph-container">
            <canvas id="graph-canvas"></canvas>
            <div id="status" class="status-indicator idle">Ready</div>
            <div class="zoom-controls">
                <button class="zoom-btn" id="zoomIn">+</button>
                <button class="zoom-btn" id="zoomOut">-</button>
                <button class="zoom-btn" id="zoomFit">&#8644;</button>
            </div>
            <div id="tooltip" class="tooltip hidden"></div>
        </div>

        <div class="side-panel">
            <div class="panel-section">
                <h3>Failure Scenarios</h3>
                <div class="scenario-list" id="scenarioList"></div>
                <div class="controls">
                    <button class="btn btn-danger" id="resetBtn">Reset</button>
                    <button class="btn btn-primary" id="reloadBtn">Reload Data</button>
                </div>
            </div>

            <div class="panel-section">
                <h3>Single Points of Failure</h3>
            </div>
            <div class="spof-list" id="spofList"></div>

            <div id="summaryPanel" class="summary-panel hidden">
                <h3 style="font-size: 0.75rem; color: #888; margin-bottom: 10px;">CASCADE SUMMARY</h3>
                <div class="summary-grid">
                    <div class="summary-stat danger">
                        <div class="value" id="sumFailed">0</div>
                        <div class="label">Failed</div>
                    </div>
                    <div class="summary-stat warning">
                        <div class="value" id="sumDegraded">0</div>
                        <div class="label">Degraded</div>
                    </div>
                    <div class="summary-stat">
                        <div class="value" id="sumDepth">0</div>
                        <div class="label">Cascade Depth</div>
                    </div>
                    <div class="summary-stat">
                        <div class="value" id="sumEvents">0</div>
                        <div class="label">Events</div>
                    </div>
                </div>
            </div>

            <div class="panel-section" style="flex: 0;">
                <h3>Event Log</h3>
            </div>
            <div class="event-log" id="eventLog"></div>

            <div class="legend">
                <div class="legend-item"><div class="legend-dot" style="background: #e74c3c;"></div> Power</div>
                <div class="legend-item"><div class="legend-dot" style="background: #3498db;"></div> Network</div>
                <div class="legend-item"><div class="legend-dot" style="background: #2ecc71;"></div> Compute</div>
                <div class="legend-item"><div class="legend-dot" style="background: #1abc9c;"></div> Cooling</div>
                <div class="legend-item"><div class="legend-dot" style="background: #9b59b6;"></div> Application</div>
            </div>
        </div>
    </div>

    <script>
        const canvas = document.getElementById('graph-canvas');
        const ctx = canvas.getContext('2d');
        let ws = null;
        let nodes = [], edges = [];
        let nodePositions = {};
        let zoom = 1, panX = 0, panY = 0;
        let dragging = false, lastMouse = {x: 0, y: 0};
        let hoveredNode = null;
        let isSimulating = false;

        // Colors for status
        const statusColors = {
            operational: null,  // Use type color
            degraded: '#f39c12',
            failed: '#e74c3c'
        };

        function resizeCanvas() {
            canvas.width = canvas.parentElement.clientWidth;
            canvas.height = canvas.parentElement.clientHeight;
            render();
        }

        function layoutGraph() {
            // Force-directed layout
            const width = canvas.width;
            const height = canvas.height;

            // Initialize positions
            nodes.forEach((node, i) => {
                if (!nodePositions[node.id]) {
                    const angle = (i / nodes.length) * Math.PI * 2;
                    const radius = Math.min(width, height) * 0.35;
                    nodePositions[node.id] = {
                        x: width/2 + Math.cos(angle) * radius * (0.5 + Math.random() * 0.5),
                        y: height/2 + Math.sin(angle) * radius * (0.5 + Math.random() * 0.5),
                        vx: 0, vy: 0
                    };
                }
            });

            // Run force simulation
            for (let iter = 0; iter < 100; iter++) {
                // Repulsion between nodes
                nodes.forEach(n1 => {
                    nodes.forEach(n2 => {
                        if (n1.id === n2.id) return;
                        const p1 = nodePositions[n1.id];
                        const p2 = nodePositions[n2.id];
                        const dx = p2.x - p1.x;
                        const dy = p2.y - p1.y;
                        const dist = Math.sqrt(dx*dx + dy*dy) || 1;
                        const force = 5000 / (dist * dist);
                        p1.vx -= (dx / dist) * force;
                        p1.vy -= (dy / dist) * force;
                    });
                });

                // Attraction along edges
                edges.forEach(edge => {
                    const p1 = nodePositions[edge.source];
                    const p2 = nodePositions[edge.target];
                    if (!p1 || !p2) return;
                    const dx = p2.x - p1.x;
                    const dy = p2.y - p1.y;
                    const dist = Math.sqrt(dx*dx + dy*dy) || 1;
                    const force = (dist - 100) * 0.05;
                    p1.vx += (dx / dist) * force;
                    p1.vy += (dy / dist) * force;
                    p2.vx -= (dx / dist) * force;
                    p2.vy -= (dy / dist) * force;
                });

                // Center gravity
                nodes.forEach(n => {
                    const p = nodePositions[n.id];
                    p.vx += (width/2 - p.x) * 0.001;
                    p.vy += (height/2 - p.y) * 0.001;
                });

                // Apply velocities
                nodes.forEach(n => {
                    const p = nodePositions[n.id];
                    p.x += p.vx * 0.1;
                    p.y += p.vy * 0.1;
                    p.vx *= 0.9;
                    p.vy *= 0.9;
                    // Keep in bounds
                    p.x = Math.max(50, Math.min(width - 50, p.x));
                    p.y = Math.max(50, Math.min(height - 50, p.y));
                });
            }
        }

        function render() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.save();
            ctx.translate(panX, panY);
            ctx.scale(zoom, zoom);

            // Draw edges
            ctx.lineWidth = 1;
            edges.forEach(edge => {
                const p1 = nodePositions[edge.source];
                const p2 = nodePositions[edge.target];
                if (!p1 || !p2) return;

                ctx.strokeStyle = '#333';
                ctx.beginPath();
                ctx.moveTo(p1.x, p1.y);
                ctx.lineTo(p2.x, p2.y);
                ctx.stroke();

                // Arrow
                const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);
                const arrowX = p2.x - Math.cos(angle) * 15;
                const arrowY = p2.y - Math.sin(angle) * 15;
                ctx.beginPath();
                ctx.moveTo(arrowX, arrowY);
                ctx.lineTo(arrowX - 8*Math.cos(angle - 0.4), arrowY - 8*Math.sin(angle - 0.4));
                ctx.lineTo(arrowX - 8*Math.cos(angle + 0.4), arrowY - 8*Math.sin(angle + 0.4));
                ctx.closePath();
                ctx.fillStyle = '#333';
                ctx.fill();
            });

            // Draw nodes
            const time = Date.now();
            nodes.forEach(node => {
                const p = nodePositions[node.id];
                if (!p) return;

                const color = statusColors[node.status] || node.color;
                let radius = 10;
                let offsetX = 0, offsetY = 0;

                // Animate failed and degraded nodes
                if (node.status === 'failed') {
                    // Pulsing effect for failed nodes
                    const pulse = Math.sin(time / 150) * 0.3 + 1;
                    radius = 14 * pulse;
                    // Shake effect
                    offsetX = Math.sin(time / 50) * 2;
                    offsetY = Math.cos(time / 50) * 2;
                } else if (node.status === 'degraded') {
                    // Slower pulse for degraded
                    const pulse = Math.sin(time / 300) * 0.2 + 1;
                    radius = 12 * pulse;
                }

                // Glow for failed nodes
                if (node.status === 'failed') {
                    ctx.shadowColor = '#e74c3c';
                    ctx.shadowBlur = 20 + Math.sin(time / 100) * 10;
                } else if (node.status === 'degraded') {
                    ctx.shadowColor = '#f39c12';
                    ctx.shadowBlur = 10 + Math.sin(time / 200) * 5;
                }

                ctx.beginPath();
                ctx.arc(p.x + offsetX, p.y + offsetY, radius, 0, Math.PI * 2);
                ctx.fillStyle = color;
                ctx.fill();

                ctx.shadowBlur = 0;

                // Border for hovered node
                if (hoveredNode === node.id) {
                    ctx.strokeStyle = '#fff';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
            });

            ctx.restore();
        }

        function getNodeAtPosition(x, y) {
            const mx = (x - panX) / zoom;
            const my = (y - panY) / zoom;

            for (const node of nodes) {
                const p = nodePositions[node.id];
                if (!p) continue;
                const dist = Math.sqrt((mx - p.x) ** 2 + (my - p.y) ** 2);
                if (dist < 15) return node;
            }
            return null;
        }

        function showTooltip(node, x, y) {
            const tooltip = document.getElementById('tooltip');
            tooltip.innerHTML = `
                <div class="title">${node.label}</div>
                <div class="info">Type: ${node.type}</div>
                <div class="info">Status: ${node.status}</div>
                <div class="info">Criticality: ${node.criticality}</div>
                <div class="info">Redundancy: ${node.redundancyLevel}</div>
            `;
            tooltip.style.left = (x + 15) + 'px';
            tooltip.style.top = (y + 15) + 'px';
            tooltip.classList.remove('hidden');
        }

        function hideTooltip() {
            document.getElementById('tooltip').classList.add('hidden');
        }

        function logEvent(message, type = 'info') {
            const log = document.getElementById('eventLog');
            const event = document.createElement('div');
            event.className = `event ${type}`;
            event.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            log.appendChild(event);
            log.scrollTop = log.scrollHeight;
        }

        function updateScenarios(scenarios) {
            const list = document.getElementById('scenarioList');
            list.innerHTML = '';
            scenarios.forEach(s => {
                const btn = document.createElement('button');
                btn.className = 'scenario-btn';
                btn.innerHTML = `<div class="name">${s.name}</div><div class="desc">${s.description}</div>`;
                btn.onclick = () => {
                    if (!isSimulating) {
                        ws.send(JSON.stringify({type: 'simulate', trigger: s.trigger}));
                    }
                };
                list.appendChild(btn);
            });
        }

        function updateSpofs(spofs) {
            const list = document.getElementById('spofList');
            list.innerHTML = '';
            document.getElementById('totalSpofs').textContent = spofs.length;

            spofs.forEach(s => {
                const item = document.createElement('div');
                item.className = 'spof-item';
                item.innerHTML = `
                    <div class="name">${s.name.replace('urn:tesserai:twin:', '')}</div>
                    <div class="meta">
                        <span class="type">${s.type}</span>
                        <span class="blast">Blast: ${s.blastRadius}</span>
                    </div>
                `;
                item.onclick = () => {
                    if (!isSimulating) {
                        ws.send(JSON.stringify({type: 'simulate', trigger: s.component}));
                    }
                };
                list.appendChild(item);
            });
        }

        function updateGraph(graphData) {
            nodes = graphData.nodes;
            edges = graphData.edges;

            document.getElementById('totalComponents').textContent = nodes.length;
            document.getElementById('totalDeps').textContent = edges.length;

            if (Object.keys(nodePositions).length === 0) {
                layoutGraph();
            } else {
                // Just update node status
                nodes.forEach(n => {
                    const existing = nodes.find(en => en.id === n.id);
                    if (existing) {
                        existing.status = n.status;
                    }
                });
            }

            render();
        }

        // WebSocket connection
        function connect() {
            ws = new WebSocket(`ws://${window.location.hostname}:WS_PORT`);

            ws.onopen = () => {
                console.log('Connected to server');
                logEvent('Connected to DTaaS', 'info');
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === 'init' || data.type === 'reset') {
                    nodePositions = {};
                    updateGraph(data.graph);
                    if (data.spofs) updateSpofs(data.spofs);
                    if (data.scenarios) updateScenarios(data.scenarios);
                    document.getElementById('summaryPanel').classList.add('hidden');
                    document.getElementById('status').className = 'status-indicator idle';
                    document.getElementById('status').textContent = 'Ready';
                    isSimulating = false;
                    if (data.type === 'reset') {
                        logEvent('System reset - all components operational', 'info');
                    }
                }
                else if (data.type === 'simulation_started') {
                    isSimulating = true;
                    document.getElementById('eventLog').innerHTML = '';
                    document.getElementById('status').className = 'status-indicator running';
                    document.getElementById('status').textContent = 'Simulating...';
                    logEvent(`CASCADE TRIGGERED: ${data.trigger}`, 'failed');
                }
                else if (data.type === 'cascade_event') {
                    updateGraph(data.graph);
                    const e = data.event;
                    const name = e.component.replace('urn:tesserai:twin:', '');
                    logEvent(`T=${e.time} ${name} ${e.status.toUpperCase()} via ${e.via}`, e.status);
                }
                else if (data.type === 'simulation_complete') {
                    isSimulating = false;
                    updateGraph(data.graph);
                    const s = data.summary;
                    document.getElementById('sumFailed').textContent = s.failed;
                    document.getElementById('sumDegraded').textContent = s.degraded;
                    document.getElementById('sumDepth').textContent = s.cascadeDepth;
                    document.getElementById('sumEvents').textContent = s.events;
                    document.getElementById('summaryPanel').classList.remove('hidden');
                    document.getElementById('status').className = 'status-indicator idle';
                    document.getElementById('status').textContent = 'Complete';
                    logEvent(`CASCADE COMPLETE: ${s.totalAffected} affected (${s.failed} failed, ${s.degraded} degraded)`, 'info');
                }
                else if (data.type === 'error') {
                    logEvent(`ERROR: ${data.message}`, 'failed');
                }
            };

            ws.onclose = () => {
                console.log('Disconnected, reconnecting...');
                setTimeout(connect, 2000);
            };
        }

        // Event listeners
        canvas.addEventListener('mousedown', e => {
            dragging = true;
            lastMouse = {x: e.clientX, y: e.clientY};
        });

        canvas.addEventListener('mousemove', e => {
            if (dragging) {
                panX += e.clientX - lastMouse.x;
                panY += e.clientY - lastMouse.y;
                lastMouse = {x: e.clientX, y: e.clientY};
                render();
            } else {
                const rect = canvas.getBoundingClientRect();
                const node = getNodeAtPosition(e.clientX - rect.left, e.clientY - rect.top);
                if (node) {
                    hoveredNode = node.id;
                    showTooltip(node, e.clientX, e.clientY);
                    canvas.style.cursor = 'pointer';
                } else {
                    hoveredNode = null;
                    hideTooltip();
                    canvas.style.cursor = 'grab';
                }
                render();
            }
        });

        canvas.addEventListener('mouseup', () => { dragging = false; });
        canvas.addEventListener('mouseleave', () => { dragging = false; hideTooltip(); });

        canvas.addEventListener('wheel', e => {
            e.preventDefault();
            const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
            zoom *= zoomFactor;
            zoom = Math.max(0.3, Math.min(3, zoom));
            render();
        });

        canvas.addEventListener('dblclick', e => {
            const rect = canvas.getBoundingClientRect();
            const node = getNodeAtPosition(e.clientX - rect.left, e.clientY - rect.top);
            if (node && !isSimulating) {
                ws.send(JSON.stringify({type: 'simulate', trigger: node.id}));
            }
        });

        document.getElementById('resetBtn').onclick = () => {
            ws.send(JSON.stringify({type: 'reset'}));
        };

        document.getElementById('reloadBtn').onclick = () => {
            ws.send(JSON.stringify({type: 'reload'}));
        };

        document.getElementById('zoomIn').onclick = () => { zoom *= 1.2; render(); };
        document.getElementById('zoomOut').onclick = () => { zoom *= 0.8; render(); };
        document.getElementById('zoomFit').onclick = () => { zoom = 1; panX = 0; panY = 0; render(); };

        // Animation loop for continuous rendering during simulation
        function animate() {
            if (isSimulating || nodes.some(n => n.status === 'failed' || n.status === 'degraded')) {
                render();
            }
            requestAnimationFrame(animate);
        }

        // Initialize
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
        connect();
        animate();
    </script>
</body>
</html>
'''


class WebHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            # Replace WS_PORT dynamically with current ws_port value
            html_content = HTML_CONTENT.replace('WS_PORT', str(ws_port))
            self.wfile.write(html_content.encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Suppress logging


async def main(port: int):
    global client, ws_port

    ws_port = port + 1

    # Initialize client and load data
    client = get_client()
    load_infrastructure()

    # Start HTTP server
    http_server = HTTPServer(('', port), WebHandler)
    http_thread = threading.Thread(target=http_server.serve_forever)
    http_thread.daemon = True
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Cascading Failure Analysis - Web UI")
    print(f"{'='*60}")
    print(f"  Open http://localhost:{port} in your browser")
    print(f"  Components loaded: {len(components)}")
    print(f"  Dependencies: {sum(len(d) for d in forward_deps.values())}")
    print(f"{'='*60}\n")

    # Start WebSocket server
    async with websockets.serve(handle_websocket, "", ws_port):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cascading Failure Web UI")
    parser.add_argument("--port", type=int, default=8108, help="HTTP port (default: 8108)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port))
    except KeyboardInterrupt:
        print("\nShutdown requested")
