#!/usr/bin/env python3
"""
Predictive Maintenance - Interactive Web Dashboard
===================================================

A production-grade web dashboard for monitoring equipment health,
predicting failures, and managing maintenance schedules.

Features:
- Real-time equipment health monitoring
- Risk matrix visualization
- Health trend sparklines
- Maintenance priority queue
- Failure prediction alerts

Usage:
    python web_ui.py [--port 8090]

Then open http://localhost:8090 in your browser.

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
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
import random
import math

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Global state
client = None
equipment: Dict[str, dict] = {}
health_history: Dict[str, deque] = {}
connected_clients: set = set()
simulation_running = False
ws_port = 8091


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


def load_equipment():
    """Load equipment data from DTaaS."""
    global equipment, health_history

    equipment = {}

    try:
        twins = client.twins.list(domain="predictive_maintenance", page_size=200)

        for twin in twins:
            twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
            raw_props = twin_dict.get("properties", {})
            props = _normalize_properties(raw_props)

            if "healthScore" not in props:
                continue

            eq_id = twin_dict["id"]
            type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""

            # Initialize history if needed
            if eq_id not in health_history:
                health_history[eq_id] = deque(maxlen=30)
            health_history[eq_id].append(props.get("healthScore", 0))

            equipment[eq_id] = {
                "id": eq_id,
                "name": twin_dict.get("name", eq_id),
                "type": type_val.split("#")[-1] if type_val else "",
                "healthScore": props.get("healthScore", 0),
                "remainingUsefulLife": props.get("remainingUsefulLife", 0),
                "failureProbability": props.get("failureProbability", 0),
                "anomalyScore": props.get("anomalyScore", 0),
                "currentVibration": props.get("currentVibration", 0),
                "currentTemperature": props.get("currentTemperature", 0),
                "operatingHours": props.get("operatingHours", 0),
                "criticality": props.get("criticality", "medium"),
                "status": props.get("status", "unknown"),
                "history": list(health_history[eq_id]),
            }

        logger.info(f"Loaded {len(equipment)} equipment items")

    except Exception as e:
        logger.error(f"Failed to load equipment: {e}")
        raise


def get_dashboard_data() -> dict:
    """Get aggregated dashboard data."""
    if not equipment:
        return {
            "equipment": [],
            "summary": {"total": 0, "critical": 0, "warning": 0, "healthy": 0},
            "riskMatrix": [],
            "maintenanceQueue": [],
        }

    eq_list = list(equipment.values())

    # Calculate summary
    critical = sum(1 for e in eq_list if e["healthScore"] < 30)
    warning = sum(1 for e in eq_list if 30 <= e["healthScore"] < 70)
    healthy = sum(1 for e in eq_list if e["healthScore"] >= 70)

    # Risk matrix data (criticality vs health)
    risk_matrix = []
    criticality_map = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    for eq in eq_list:
        risk_matrix.append({
            "id": eq["id"],
            "name": eq["name"].replace("urn:tesserai:twin:", ""),
            "x": eq["healthScore"],
            "y": criticality_map.get(eq["criticality"], 1),
            "size": max(5, min(20, eq["failureProbability"] * 50)),
            "criticality": eq["criticality"],
        })

    # Maintenance priority queue
    maintenance_queue = sorted(
        eq_list,
        key=lambda e: (
            -criticality_map.get(e["criticality"], 1),
            e["healthScore"],
            e["remainingUsefulLife"]
        )
    )[:15]

    return {
        "equipment": sorted(eq_list, key=lambda e: e["healthScore"]),
        "summary": {
            "total": len(eq_list),
            "critical": critical,
            "warning": warning,
            "healthy": healthy,
            "avgHealth": sum(e["healthScore"] for e in eq_list) / len(eq_list) if eq_list else 0,
            "avgRUL": sum(e["remainingUsefulLife"] for e in eq_list) / len(eq_list) if eq_list else 0,
        },
        "riskMatrix": risk_matrix,
        "maintenanceQueue": maintenance_queue,
    }


async def simulate_degradation():
    """Simulate equipment degradation over time."""
    global simulation_running

    while simulation_running:
        for eq_id, eq in equipment.items():
            # Simulate degradation
            degradation = random.uniform(0.1, 0.5)
            eq["healthScore"] = max(0, eq["healthScore"] - degradation)

            # Update other metrics
            eq["remainingUsefulLife"] = max(0, eq["remainingUsefulLife"] - random.uniform(0.5, 2))
            eq["failureProbability"] = min(1, (100 - eq["healthScore"]) / 100)
            eq["anomalyScore"] = min(1, eq["anomalyScore"] + random.uniform(-0.02, 0.05))
            eq["currentVibration"] += random.uniform(-0.5, 1)
            eq["currentTemperature"] += random.uniform(-1, 2)

            # Update history
            if eq_id in health_history:
                health_history[eq_id].append(eq["healthScore"])
                eq["history"] = list(health_history[eq_id])

        # Broadcast update
        await broadcast({
            "type": "update",
            "data": get_dashboard_data(),
        })

        await asyncio.sleep(2)


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
            "data": get_dashboard_data(),
        }))

        async for message in websocket:
            data = json.loads(message)

            if data.get("type") == "start_simulation":
                if not simulation_running:
                    simulation_running = True
                    asyncio.create_task(simulate_degradation())
                    await broadcast({"type": "simulation_started"})

            elif data.get("type") == "stop_simulation":
                simulation_running = False
                await broadcast({"type": "simulation_stopped"})

            elif data.get("type") == "reload":
                simulation_running = False
                await asyncio.sleep(0.2)
                load_equipment()
                await websocket.send(json.dumps({
                    "type": "init",
                    "data": get_dashboard_data(),
                }))

            elif data.get("type") == "get_details":
                eq_id = data.get("equipment_id")
                if eq_id in equipment:
                    await websocket.send(json.dumps({
                        "type": "equipment_details",
                        "data": equipment[eq_id],
                    }))

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
    <title>Predictive Maintenance Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
            color: #eee;
            min-height: 100vh;
        }
        .header {
            background: rgba(0,0,0,0.4);
            padding: 15px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #333;
        }
        .header h1 {
            font-size: 1.4rem;
            font-weight: 400;
            color: #4ecdc4;
        }
        .header-controls {
            display: flex;
            gap: 10px;
        }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 500;
            transition: all 0.2s;
        }
        .btn-success { background: #2ecc71; color: #fff; }
        .btn-success:hover { background: #27ae60; }
        .btn-danger { background: #e74c3c; color: #fff; }
        .btn-danger:hover { background: #c0392b; }
        .btn-primary { background: #3498db; color: #fff; }
        .btn-primary:hover { background: #2980b9; }
        .main-container {
            display: grid;
            grid-template-columns: 1fr 1fr 350px;
            gap: 20px;
            padding: 20px;
            height: calc(100vh - 70px);
        }
        .panel {
            background: rgba(0,0,0,0.3);
            border-radius: 12px;
            border: 1px solid #333;
            overflow: hidden;
        }
        .panel-header {
            background: rgba(0,0,0,0.3);
            padding: 12px 15px;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel-header h2 {
            font-size: 0.8rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .panel-content {
            padding: 15px;
            height: calc(100% - 45px);
            overflow-y: auto;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        .summary-card {
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            border: 1px solid #333;
        }
        .summary-card .value {
            font-size: 2.5rem;
            font-weight: 600;
            line-height: 1;
        }
        .summary-card .label {
            font-size: 0.75rem;
            color: #888;
            margin-top: 8px;
            text-transform: uppercase;
        }
        .summary-card.critical .value { color: #e74c3c; }
        .summary-card.warning .value { color: #f39c12; }
        .summary-card.healthy .value { color: #2ecc71; }
        .summary-card.info .value { color: #4ecdc4; }
        .equipment-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .equipment-item {
            background: #1a1a2e;
            border-radius: 8px;
            padding: 12px;
            display: grid;
            grid-template-columns: 1fr 100px 80px;
            gap: 10px;
            align-items: center;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }
        .equipment-item:hover {
            border-color: #4ecdc4;
            background: #252545;
        }
        .equipment-item .name {
            font-size: 0.85rem;
            color: #fff;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .equipment-item .type {
            font-size: 0.7rem;
            color: #888;
        }
        .equipment-item .health-bar {
            height: 8px;
            background: #333;
            border-radius: 4px;
            overflow: hidden;
        }
        .equipment-item .health-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s, background 0.3s;
        }
        .equipment-item .rul {
            font-size: 0.8rem;
            color: #888;
            text-align: right;
        }
        .sparkline {
            display: flex;
            align-items: flex-end;
            height: 30px;
            gap: 1px;
        }
        .sparkline-bar {
            flex: 1;
            background: #4ecdc4;
            border-radius: 1px;
            transition: height 0.2s;
        }
        .risk-matrix {
            position: relative;
            height: 100%;
            background: #0d0d1a;
            border-radius: 8px;
            padding: 40px 40px 40px 50px;
        }
        .risk-matrix-grid {
            position: relative;
            width: 100%;
            height: 100%;
            border-left: 2px solid #333;
            border-bottom: 2px solid #333;
        }
        .risk-matrix-point {
            position: absolute;
            border-radius: 50%;
            transform: translate(-50%, 50%);
            cursor: pointer;
            transition: all 0.2s;
            border: 2px solid rgba(255,255,255,0.3);
        }
        .risk-matrix-point:hover {
            transform: translate(-50%, 50%) scale(1.3);
            border-color: #fff;
        }
        .risk-matrix-label {
            position: absolute;
            font-size: 0.65rem;
            color: #666;
        }
        .risk-matrix-label.x-axis { bottom: -25px; }
        .risk-matrix-label.y-axis { left: -40px; transform: rotate(-90deg); }
        .risk-zones {
            position: absolute;
            inset: 0;
            pointer-events: none;
        }
        .risk-zone {
            position: absolute;
            opacity: 0.1;
        }
        .risk-zone.high { background: #e74c3c; left: 0; width: 30%; top: 0; height: 100%; }
        .risk-zone.medium { background: #f39c12; left: 30%; width: 40%; top: 0; height: 100%; }
        .risk-zone.low { background: #2ecc71; left: 70%; width: 30%; top: 0; height: 100%; }
        .maintenance-queue {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .maintenance-item {
            background: #1a1a2e;
            border-radius: 8px;
            padding: 12px;
            display: flex;
            align-items: center;
            gap: 10px;
            border-left: 3px solid;
        }
        .maintenance-item.critical { border-color: #e74c3c; }
        .maintenance-item.high { border-color: #f39c12; }
        .maintenance-item.medium { border-color: #3498db; }
        .maintenance-item.low { border-color: #2ecc71; }
        .maintenance-item .priority {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: 600;
            color: #fff;
        }
        .maintenance-item.critical .priority { background: #e74c3c; }
        .maintenance-item.high .priority { background: #f39c12; }
        .maintenance-item.medium .priority { background: #3498db; }
        .maintenance-item.low .priority { background: #2ecc71; }
        .maintenance-item .info { flex: 1; }
        .maintenance-item .name { font-size: 0.8rem; color: #fff; }
        .maintenance-item .details { font-size: 0.7rem; color: #888; margin-top: 2px; }
        .gauge {
            position: relative;
            width: 120px;
            height: 60px;
            margin: 0 auto;
        }
        .gauge-bg {
            fill: none;
            stroke: #333;
            stroke-width: 12;
        }
        .gauge-fill {
            fill: none;
            stroke-width: 12;
            stroke-linecap: round;
            transition: stroke-dashoffset 0.5s, stroke 0.5s;
        }
        .gauge-value {
            position: absolute;
            bottom: 5px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 1.2rem;
            font-weight: 600;
        }
        .status-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.65rem;
            font-weight: 500;
            text-transform: uppercase;
        }
        .status-badge.running { background: #2ecc71; color: #fff; }
        .status-badge.stopped { background: #e74c3c; color: #fff; }
        .modal {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        .modal.hidden { display: none; }
        .modal-content {
            background: #1a1a2e;
            border-radius: 12px;
            padding: 25px;
            min-width: 400px;
            max-width: 600px;
            border: 1px solid #333;
        }
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .modal-header h3 { color: #4ecdc4; font-size: 1.1rem; }
        .modal-close {
            background: none;
            border: none;
            color: #888;
            font-size: 1.5rem;
            cursor: pointer;
        }
        .detail-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }
        .detail-item {
            background: #252545;
            padding: 12px;
            border-radius: 6px;
        }
        .detail-item .label { font-size: 0.7rem; color: #888; margin-bottom: 4px; }
        .detail-item .value { font-size: 1.1rem; font-weight: 500; }
        .detail-item .value.danger { color: #e74c3c; }
        .detail-item .value.warning { color: #f39c12; }
        .detail-item .value.success { color: #2ecc71; }

        /* Animations for failing equipment */
        @keyframes criticalPulse {
            0%, 100% {
                box-shadow: 0 0 5px rgba(231, 76, 60, 0.5);
                border-color: rgba(231, 76, 60, 0.5);
            }
            50% {
                box-shadow: 0 0 20px rgba(231, 76, 60, 0.8);
                border-color: rgba(231, 76, 60, 1);
            }
        }
        @keyframes warningPulse {
            0%, 100% {
                box-shadow: 0 0 3px rgba(243, 156, 18, 0.3);
                border-color: rgba(243, 156, 18, 0.3);
            }
            50% {
                box-shadow: 0 0 12px rgba(243, 156, 18, 0.6);
                border-color: rgba(243, 156, 18, 0.8);
            }
        }
        @keyframes riskPointPulse {
            0%, 100% { transform: translate(-50%, 50%) scale(1); }
            50% { transform: translate(-50%, 50%) scale(1.4); }
        }
        .equipment-item.critical-state {
            animation: criticalPulse 1s ease-in-out infinite;
            border: 1px solid rgba(231, 76, 60, 0.5);
            background: rgba(231, 76, 60, 0.1);
        }
        .equipment-item.warning-state {
            animation: warningPulse 1.5s ease-in-out infinite;
            border: 1px solid rgba(243, 156, 18, 0.3);
            background: rgba(243, 156, 18, 0.05);
        }
        .risk-matrix-point.critical-state {
            animation: riskPointPulse 0.8s ease-in-out infinite;
            box-shadow: 0 0 15px rgba(231, 76, 60, 0.8);
        }
        .risk-matrix-point.warning-state {
            animation: riskPointPulse 1.2s ease-in-out infinite;
            box-shadow: 0 0 10px rgba(243, 156, 18, 0.6);
        }
        .maintenance-item.critical {
            animation: criticalPulse 1s ease-in-out infinite;
        }
        .summary-card.critical .value {
            animation: criticalPulse 1s ease-in-out infinite;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Predictive Maintenance Dashboard</h1>
        <div class="header-controls">
            <span id="simStatus" class="status-badge stopped">Stopped</span>
            <button class="btn btn-success" id="startBtn">Start Simulation</button>
            <button class="btn btn-danger" id="stopBtn">Stop</button>
            <button class="btn btn-primary" id="reloadBtn">Reload Data</button>
        </div>
    </div>

    <div class="summary-grid" style="padding: 20px 20px 0;">
        <div class="summary-card info">
            <div class="value" id="totalEquipment">0</div>
            <div class="label">Total Equipment</div>
        </div>
        <div class="summary-card critical">
            <div class="value" id="criticalCount">0</div>
            <div class="label">Critical</div>
        </div>
        <div class="summary-card warning">
            <div class="value" id="warningCount">0</div>
            <div class="label">Warning</div>
        </div>
        <div class="summary-card healthy">
            <div class="value" id="healthyCount">0</div>
            <div class="label">Healthy</div>
        </div>
    </div>

    <div class="main-container">
        <div class="panel">
            <div class="panel-header">
                <h2>Equipment Health</h2>
                <span style="color: #4ecdc4; font-size: 0.8rem;">Avg: <span id="avgHealth">0</span>%</span>
            </div>
            <div class="panel-content">
                <div class="equipment-list" id="equipmentList"></div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <h2>Risk Matrix</h2>
                <span style="color: #888; font-size: 0.7rem;">Health vs Criticality</span>
            </div>
            <div class="panel-content" style="padding: 0;">
                <div class="risk-matrix" id="riskMatrix">
                    <div class="risk-zones">
                        <div class="risk-zone high"></div>
                        <div class="risk-zone medium"></div>
                        <div class="risk-zone low"></div>
                    </div>
                    <div class="risk-matrix-grid" id="riskMatrixGrid">
                        <span class="risk-matrix-label x-axis" style="left: 50%;">Health Score &rarr;</span>
                        <span class="risk-matrix-label y-axis" style="top: 50%;">Criticality &rarr;</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <h2>Maintenance Priority</h2>
            </div>
            <div class="panel-content">
                <div class="maintenance-queue" id="maintenanceQueue"></div>
            </div>
        </div>
    </div>

    <div id="detailModal" class="modal hidden">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modalTitle">Equipment Details</h3>
                <button class="modal-close" id="modalClose">&times;</button>
            </div>
            <div class="detail-grid" id="detailGrid"></div>
            <div style="margin-top: 20px;">
                <h4 style="color: #888; font-size: 0.75rem; margin-bottom: 10px;">HEALTH HISTORY</h4>
                <div class="sparkline" id="detailSparkline"></div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let isSimulating = false;

        function getHealthColor(health) {
            if (health < 30) return '#e74c3c';
            if (health < 70) return '#f39c12';
            return '#2ecc71';
        }

        function createSparkline(container, data, height = 30) {
            container.innerHTML = '';
            const max = Math.max(...data, 100);
            data.forEach(v => {
                const bar = document.createElement('div');
                bar.className = 'sparkline-bar';
                bar.style.height = `${(v / max) * height}px`;
                bar.style.background = getHealthColor(v);
                container.appendChild(bar);
            });
        }

        function updateDashboard(data) {
            // Summary
            document.getElementById('totalEquipment').textContent = data.summary.total;
            document.getElementById('criticalCount').textContent = data.summary.critical;
            document.getElementById('warningCount').textContent = data.summary.warning;
            document.getElementById('healthyCount').textContent = data.summary.healthy;
            document.getElementById('avgHealth').textContent = data.summary.avgHealth.toFixed(1);

            // Equipment list
            const list = document.getElementById('equipmentList');
            list.innerHTML = '';
            data.equipment.forEach(eq => {
                const item = document.createElement('div');
                // Add animation class based on health
                let stateClass = '';
                if (eq.healthScore < 30) stateClass = 'critical-state';
                else if (eq.healthScore < 70) stateClass = 'warning-state';
                item.className = `equipment-item ${stateClass}`;
                item.innerHTML = `
                    <div>
                        <div class="name">${eq.name.replace('urn:tesserai:twin:', '')}</div>
                        <div class="type">${eq.type}</div>
                    </div>
                    <div>
                        <div class="health-bar">
                            <div class="health-fill" style="width: ${eq.healthScore}%; background: ${getHealthColor(eq.healthScore)};"></div>
                        </div>
                        <div style="font-size: 0.7rem; color: #888; margin-top: 2px;">${eq.healthScore.toFixed(1)}%</div>
                    </div>
                    <div class="rul">${eq.remainingUsefulLife.toFixed(0)}h RUL</div>
                `;
                item.onclick = () => showDetails(eq);
                list.appendChild(item);
            });

            // Risk matrix
            const grid = document.getElementById('riskMatrixGrid');
            // Remove old points
            grid.querySelectorAll('.risk-matrix-point').forEach(p => p.remove());
            data.riskMatrix.forEach(point => {
                const dot = document.createElement('div');
                // Add animation class based on health
                let stateClass = '';
                if (point.x < 30) stateClass = 'critical-state';
                else if (point.x < 70) stateClass = 'warning-state';
                dot.className = `risk-matrix-point ${stateClass}`;
                dot.style.left = `${point.x}%`;
                dot.style.bottom = `${(point.y / 3) * 100}%`;
                dot.style.width = `${point.size}px`;
                dot.style.height = `${point.size}px`;
                dot.style.background = getHealthColor(point.x);
                dot.title = `${point.name}: ${point.x.toFixed(1)}% health`;
                grid.appendChild(dot);
            });

            // Maintenance queue
            const queue = document.getElementById('maintenanceQueue');
            queue.innerHTML = '';
            data.maintenanceQueue.forEach((eq, i) => {
                const item = document.createElement('div');
                item.className = `maintenance-item ${eq.criticality}`;
                item.innerHTML = `
                    <div class="priority">${i + 1}</div>
                    <div class="info">
                        <div class="name">${eq.name.replace('urn:tesserai:twin:', '')}</div>
                        <div class="details">Health: ${eq.healthScore.toFixed(1)}% | RUL: ${eq.remainingUsefulLife.toFixed(0)}h</div>
                    </div>
                `;
                queue.appendChild(item);
            });
        }

        function showDetails(eq) {
            document.getElementById('modalTitle').textContent = eq.name.replace('urn:tesserai:twin:', '');

            const healthClass = eq.healthScore < 30 ? 'danger' : eq.healthScore < 70 ? 'warning' : 'success';

            document.getElementById('detailGrid').innerHTML = `
                <div class="detail-item">
                    <div class="label">Health Score</div>
                    <div class="value ${healthClass}">${eq.healthScore.toFixed(1)}%</div>
                </div>
                <div class="detail-item">
                    <div class="label">Remaining Useful Life</div>
                    <div class="value">${eq.remainingUsefulLife.toFixed(0)} hours</div>
                </div>
                <div class="detail-item">
                    <div class="label">Failure Probability</div>
                    <div class="value ${eq.failureProbability > 0.5 ? 'danger' : ''}">${(eq.failureProbability * 100).toFixed(1)}%</div>
                </div>
                <div class="detail-item">
                    <div class="label">Anomaly Score</div>
                    <div class="value ${eq.anomalyScore > 0.7 ? 'warning' : ''}">${(eq.anomalyScore * 100).toFixed(1)}%</div>
                </div>
                <div class="detail-item">
                    <div class="label">Vibration</div>
                    <div class="value">${eq.currentVibration.toFixed(2)} mm/s</div>
                </div>
                <div class="detail-item">
                    <div class="label">Temperature</div>
                    <div class="value">${eq.currentTemperature.toFixed(1)}°C</div>
                </div>
                <div class="detail-item">
                    <div class="label">Operating Hours</div>
                    <div class="value">${eq.operatingHours.toFixed(0)}</div>
                </div>
                <div class="detail-item">
                    <div class="label">Criticality</div>
                    <div class="value" style="text-transform: capitalize;">${eq.criticality}</div>
                </div>
            `;

            if (eq.history && eq.history.length > 0) {
                createSparkline(document.getElementById('detailSparkline'), eq.history, 40);
            }

            document.getElementById('detailModal').classList.remove('hidden');
        }

        function connect() {
            ws = new WebSocket(`ws://${window.location.hostname}:WS_PORT`);

            ws.onopen = () => {
                console.log('Connected to server');
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);

                if (data.type === 'init' || data.type === 'update') {
                    updateDashboard(data.data);
                }
                else if (data.type === 'simulation_started') {
                    isSimulating = true;
                    document.getElementById('simStatus').textContent = 'Running';
                    document.getElementById('simStatus').className = 'status-badge running';
                }
                else if (data.type === 'simulation_stopped') {
                    isSimulating = false;
                    document.getElementById('simStatus').textContent = 'Stopped';
                    document.getElementById('simStatus').className = 'status-badge stopped';
                }
            };

            ws.onclose = () => {
                console.log('Disconnected, reconnecting...');
                setTimeout(connect, 2000);
            };
        }

        // Event listeners
        document.getElementById('startBtn').onclick = () => {
            ws.send(JSON.stringify({type: 'start_simulation'}));
        };

        document.getElementById('stopBtn').onclick = () => {
            ws.send(JSON.stringify({type: 'stop_simulation'}));
        };

        document.getElementById('reloadBtn').onclick = () => {
            ws.send(JSON.stringify({type: 'reload'}));
        };

        document.getElementById('modalClose').onclick = () => {
            document.getElementById('detailModal').classList.add('hidden');
        };

        document.getElementById('detailModal').onclick = (e) => {
            if (e.target.id === 'detailModal') {
                document.getElementById('detailModal').classList.add('hidden');
            }
        };

        // Initialize
        connect();
    </script>
</body>
</html>
'''.replace('WS_PORT', str(ws_port))


class WebHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


async def main(port: int):
    global client, ws_port

    ws_port = port + 1

    # Initialize client and load data
    client = get_client()
    load_equipment()

    # Start HTTP server
    http_server = HTTPServer(('', port), WebHandler)
    http_thread = threading.Thread(target=http_server.serve_forever)
    http_thread.daemon = True
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Predictive Maintenance - Web Dashboard")
    print(f"{'='*60}")
    print(f"  Open http://localhost:{port} in your browser")
    print(f"  Equipment loaded: {len(equipment)}")
    print(f"{'='*60}\n")

    # Start WebSocket server
    async with websockets.serve(handle_websocket, "", ws_port):
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predictive Maintenance Web Dashboard")
    parser.add_argument("--port", type=int, default=8090, help="HTTP port (default: 8090)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port))
    except KeyboardInterrupt:
        print("\nShutdown requested")
