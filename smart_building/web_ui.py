#!/usr/bin/env python3
"""
Smart Building Digital Twin - Interactive Web UI
=================================================

A production-grade web interface for visualizing smart building operations
including HVAC, lighting, sensors, occupancy, and energy management.

Features:
- Floor-by-floor building visualization
- Real-time sensor data (temp, CO2, occupancy, humidity)
- HVAC system status and control view
- Energy consumption monitoring
- Elevator status tracking
- Environmental quality indicators

Usage:
    python web_ui.py [--port 8082]

Then open http://localhost:8082 in your browser.

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
from typing import Dict, List, Set
from collections import defaultdict

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Global state
client = None
building: Dict = {}
floors: Dict[str, dict] = {}
rooms: Dict[str, dict] = {}
sensors: Dict[str, dict] = {}
hvac_equipment: Dict[str, dict] = {}
elevators: Dict[str, dict] = {}
energy_data: Dict[str, dict] = {}
connected_clients: Set = set()
ws_port = 8083


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


def load_building_data():
    """Load building data from DTaaS."""
    global building, floors, rooms, sensors, hvac_equipment, elevators, energy_data

    building = {}
    floors = {}
    rooms = {}
    sensors = {}
    hvac_equipment = {}
    elevators = {}
    energy_data = {}

    try:
        twins = client.twins.list(domain="smart_building", page_size=500)

        for twin in twins:
            twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
            twin_id = twin_dict["id"]

            type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
            twin_type = type_val.split("#")[-1] if type_val else ""
            raw_props = twin_dict.get("properties", {})

            item = {
                "id": twin_id,
                "name": twin_dict.get("name", twin_id),
                "type": twin_type,
                "properties": _normalize_properties(raw_props),
            }

            # Categorize by type
            if twin_type == "Building":
                building = item
            elif twin_type == "Floor":
                floors[twin_id] = item
            elif twin_type == "Room":
                rooms[twin_id] = item
            elif "Sensor" in twin_type:
                sensors[twin_id] = item
            elif twin_type in ["HVACPlant", "AirHandlingUnit", "VAVBox"]:
                hvac_equipment[twin_id] = item
            elif twin_type == "Elevator":
                elevators[twin_id] = item
            elif twin_type == "PowerMeter":
                energy_data[twin_id] = item

        logger.info(f"Loaded: {len(floors)} floors, {len(rooms)} rooms, "
                   f"{len(sensors)} sensors, {len(elevators)} elevators")

    except Exception as e:
        logger.error(f"Failed to load building data: {e}")
        raise


def get_building_summary() -> dict:
    """Get building summary statistics."""
    props = building.get("properties", {}) if building else {}

    # Calculate occupancy
    total_occupancy = 0
    max_occupancy = 0
    occupied_rooms = 0

    for sensor in sensors.values():
        if sensor["type"] == "OccupancySensor":
            sensor_props = sensor.get("properties", {})
            if sensor_props.get("isOccupied"):
                occupied_rooms += 1
            occ = int(sensor_props.get("currentOccupancy", 0))
            total_occupancy += occ

    for room in rooms.values():
        room_props = room.get("properties", {})
        max_occupancy += int(room_props.get("maxOccupancy", 0))

    # Get energy data
    current_power = 0
    today_consumption = 0
    for meter in energy_data.values():
        meter_props = meter.get("properties", {})
        current_power += float(meter_props.get("currentPower", 0))
        today_consumption += float(meter_props.get("todayConsumption", 0))

    # Calculate average temperature
    temp_sum = 0
    temp_count = 0
    for sensor in sensors.values():
        if sensor["type"] == "TemperatureSensor":
            sensor_props = sensor.get("properties", {})
            temp_sum += float(sensor_props.get("currentValue", 22))
            temp_count += 1
    avg_temp = temp_sum / temp_count if temp_count > 0 else 22

    return {
        "name": building.get("name", "Building"),
        "totalFloors": int(props.get("totalFloors", len(floors))),
        "totalArea": int(props.get("totalArea", 0)),
        "certification": props.get("certification", ""),
        "currentOccupancy": total_occupancy,
        "maxOccupancy": max_occupancy,
        "occupiedRooms": occupied_rooms,
        "totalRooms": len(rooms),
        "currentPower": current_power,
        "todayConsumption": today_consumption,
        "avgTemperature": avg_temp,
    }


def get_floors_data() -> List[dict]:
    """Get floor data for visualization."""
    result = []
    for floor in floors.values():
        props = floor.get("properties", {})

        # Get floor rooms
        floor_rooms = []
        for room in rooms.values():
            room_props = room.get("properties", {})
            # For simplicity, assume rooms are linked by ID pattern
            if floor["id"].replace("floor-", "") in room["id"]:
                floor_rooms.append(room)

        result.append({
            "id": floor["id"],
            "name": floor["name"],
            "level": int(props.get("level", 0)),
            "area": int(props.get("area", 0)),
            "floorType": props.get("floorType", "office"),
            "maxOccupancy": int(props.get("maxOccupancy", 0)),
            "roomCount": len(floor_rooms),
        })

    return sorted(result, key=lambda x: x["level"])


def get_rooms_data() -> List[dict]:
    """Get room data with sensor readings."""
    result = []
    for room in rooms.values():
        props = room.get("properties", {})

        # Find associated sensors
        temp = None
        co2 = None
        humidity = None
        is_occupied = False
        occupancy = 0

        for sensor in sensors.values():
            sensor_id = sensor["id"]
            if room["id"] in sensor_id:
                sensor_props = sensor.get("properties", {})
                if sensor["type"] == "TemperatureSensor":
                    temp = float(sensor_props.get("currentValue", 0))
                elif sensor["type"] == "CO2Sensor":
                    co2 = int(sensor_props.get("currentValue", 0))
                elif sensor["type"] == "HumiditySensor":
                    humidity = float(sensor_props.get("currentValue", 0))
                elif sensor["type"] == "OccupancySensor":
                    is_occupied = sensor_props.get("isOccupied", False)
                    occupancy = int(sensor_props.get("currentOccupancy", 0))

        result.append({
            "id": room["id"],
            "name": room["name"],
            "roomType": props.get("roomType", "unknown"),
            "area": int(props.get("area", 0)),
            "maxOccupancy": int(props.get("maxOccupancy", 0)),
            "isBookable": props.get("isBookable", False),
            "hasWindows": props.get("hasWindows", False),
            "temperature": temp,
            "co2": co2,
            "humidity": humidity,
            "isOccupied": is_occupied,
            "currentOccupancy": occupancy,
        })

    return result


def get_hvac_data() -> dict:
    """Get HVAC system data."""
    plant = None
    ahus = []
    vavs = []

    for equip in hvac_equipment.values():
        props = equip.get("properties", {})
        if equip["type"] == "HVACPlant":
            plant = {
                "id": equip["id"],
                "name": equip["name"],
                "coolingCapacity": int(props.get("coolingCapacity", 0)),
                "heatingCapacity": int(props.get("heatingCapacity", 0)),
                "status": props.get("status", "unknown"),
                "lastMaintenance": props.get("lastMaintenance", ""),
            }
        elif equip["type"] == "AirHandlingUnit":
            ahus.append({
                "id": equip["id"],
                "name": equip["name"],
                "airflowCapacity": int(props.get("airflowCapacity", 0)),
                "filterType": props.get("filterType", ""),
                "status": props.get("status", "unknown"),
            })
        elif equip["type"] == "VAVBox":
            vavs.append({
                "id": equip["id"],
                "name": equip["name"],
                "damperPosition": int(props.get("damperPosition", 50)),
                "status": props.get("status", "unknown"),
            })

    return {
        "plant": plant,
        "ahus": ahus,
        "vavs": vavs,
    }


def get_elevators_data() -> List[dict]:
    """Get elevator data."""
    result = []
    for elevator in elevators.values():
        props = elevator.get("properties", {})
        result.append({
            "id": elevator["id"],
            "name": elevator["name"],
            "currentFloor": int(props.get("currentFloor", 0)),
            "direction": props.get("direction", "idle"),
            "status": props.get("status", "unknown"),
            "capacity": int(props.get("maxPersons", 0)),
        })

    return sorted(result, key=lambda x: x["id"])


def get_sensor_summary() -> dict:
    """Get sensor statistics."""
    online = 0
    offline = 0
    alert = 0

    for sensor in sensors.values():
        props = sensor.get("properties", {})
        status = props.get("status", "offline")
        if status == "online":
            online += 1
        else:
            offline += 1

        # Check for alerts (high CO2, extreme temp)
        if sensor["type"] == "CO2Sensor":
            if int(props.get("currentValue", 0)) > int(props.get("threshold", 1000)):
                alert += 1
        elif sensor["type"] == "TemperatureSensor":
            temp = float(props.get("currentValue", 22))
            if temp < 18 or temp > 28:
                alert += 1

    return {
        "total": len(sensors),
        "online": online,
        "offline": offline,
        "alerts": alert,
    }


def get_full_state() -> dict:
    """Get full state for client initialization."""
    return {
        "summary": get_building_summary(),
        "floors": get_floors_data(),
        "rooms": get_rooms_data(),
        "hvac": get_hvac_data(),
        "elevators": get_elevators_data(),
        "sensors": get_sensor_summary(),
    }


async def broadcast(message: dict):
    """Broadcast message to all connected clients."""
    if connected_clients:
        msg = json.dumps(message)
        await asyncio.gather(*[c.send(msg) for c in connected_clients])


async def handle_websocket(websocket):
    """Handle WebSocket connections."""
    connected_clients.add(websocket)
    print(f"Client connected. Total: {len(connected_clients)}")

    try:
        await websocket.send(json.dumps({
            "type": "init",
            **get_full_state()
        }))

        async for message in websocket:
            data = json.loads(message)
            if data.get("type") == "refresh":
                load_building_data()
                await websocket.send(json.dumps({
                    "type": "update",
                    **get_full_state()
                }))

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.discard(websocket)
        print(f"Client disconnected. Total: {len(connected_clients)}")


async def periodic_update():
    """Send periodic updates to clients."""
    while True:
        await asyncio.sleep(5)
        if connected_clients:
            try:
                load_building_data()
                await broadcast({
                    "type": "update",
                    **get_full_state()
                })
            except Exception as e:
                logger.error(f"Update error: {e}")


HTML_CONTENT = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Building Digital Twin</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
        }
        .header {
            background: rgba(0,0,0,0.3);
            padding: 15px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #333;
        }
        .header h1 {
            font-size: 1.4rem;
            font-weight: 500;
            color: #4ecdc4;
        }
        .header h1 span { color: #888; font-weight: 300; }
        .cert-badge {
            padding: 5px 12px;
            background: rgba(46, 204, 113, 0.15);
            border: 1px solid rgba(46, 204, 113, 0.3);
            border-radius: 15px;
            font-size: 0.7rem;
            color: #2ecc71;
        }

        .dashboard {
            display: grid;
            grid-template-columns: 280px 1fr 320px;
            grid-template-rows: auto 1fr;
            gap: 15px;
            padding: 15px;
            height: calc(100vh - 70px);
        }

        .summary-row {
            grid-column: 1 / -1;
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 15px;
        }
        .summary-card {
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            border: 1px solid #333;
            padding: 15px;
            text-align: center;
        }
        .summary-value {
            font-size: 1.8rem;
            font-weight: 600;
            color: #4ecdc4;
        }
        .summary-value.warning { color: #f1c40f; }
        .summary-value.danger { color: #e74c3c; }
        .summary-label {
            font-size: 0.7rem;
            color: #888;
            margin-top: 5px;
            text-transform: uppercase;
        }

        .card {
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            border: 1px solid #333;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .card-header {
            padding: 12px 15px;
            border-bottom: 1px solid #333;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-header h3 {
            font-size: 0.75rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .card-body {
            padding: 15px;
            overflow-y: auto;
            flex: 1;
        }

        /* Building visualization */
        .building-viz {
            display: flex;
            flex-direction: column-reverse;
            gap: 4px;
        }
        .floor-bar {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 10px;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
            border-left: 3px solid #333;
        }
        .floor-bar:hover { background: rgba(0,0,0,0.4); }
        .floor-bar.selected {
            border-left-color: #4ecdc4;
            background: rgba(78, 205, 196, 0.1);
        }
        .floor-bar.occupied { border-left-color: #2ecc71; }
        .floor-level {
            width: 24px;
            height: 24px;
            background: #333;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: 600;
        }
        .floor-name {
            flex: 1;
            font-size: 0.75rem;
        }
        .floor-type {
            font-size: 0.6rem;
            color: #666;
            padding: 2px 6px;
            background: #222;
            border-radius: 3px;
        }

        /* Rooms Grid */
        .rooms-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }
        .room-card {
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            padding: 12px;
            border: 1px solid #333;
            transition: all 0.2s;
        }
        .room-card:hover {
            border-color: #4ecdc4;
        }
        .room-card.occupied {
            border-color: #2ecc71;
            box-shadow: 0 0 10px rgba(46, 204, 113, 0.2);
        }
        .room-card.alert {
            border-color: #e74c3c;
            animation: alertPulse 1s infinite;
        }
        @keyframes alertPulse {
            0%, 100% { box-shadow: 0 0 5px rgba(231, 76, 60, 0.3); }
            50% { box-shadow: 0 0 15px rgba(231, 76, 60, 0.6); }
        }
        .room-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }
        .room-name {
            font-size: 0.85rem;
            font-weight: 500;
        }
        .room-type {
            font-size: 0.6rem;
            color: #888;
        }
        .room-status {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #666;
        }
        .room-status.occupied { background: #2ecc71; animation: pulse 2s infinite; }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .room-sensors {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }
        .sensor-reading {
            background: rgba(0,0,0,0.3);
            border-radius: 4px;
            padding: 6px 8px;
            text-align: center;
        }
        .sensor-value {
            font-size: 0.9rem;
            font-weight: 600;
            color: #4ecdc4;
        }
        .sensor-value.warning { color: #f1c40f; }
        .sensor-value.danger { color: #e74c3c; }
        .sensor-label {
            font-size: 0.55rem;
            color: #666;
            text-transform: uppercase;
        }

        /* HVAC Section */
        .hvac-status {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .hvac-plant {
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            padding: 12px;
            border-left: 3px solid #3498db;
        }
        .hvac-plant-name {
            font-size: 0.85rem;
            font-weight: 500;
            margin-bottom: 8px;
        }
        .hvac-stats {
            display: flex;
            gap: 15px;
            font-size: 0.7rem;
            color: #888;
        }
        .hvac-stat { color: #4ecdc4; font-weight: 500; }

        .ahu-list {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        .ahu-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 10px;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
        }
        .ahu-icon {
            width: 28px;
            height: 28px;
            background: #333;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
        }
        .ahu-info { flex: 1; }
        .ahu-name { font-size: 0.75rem; }
        .ahu-meta { font-size: 0.6rem; color: #666; }
        .ahu-status {
            font-size: 0.6rem;
            padding: 2px 6px;
            border-radius: 3px;
            background: rgba(46, 204, 113, 0.15);
            color: #2ecc71;
        }
        .ahu-status.warning {
            background: rgba(241, 196, 15, 0.15);
            color: #f1c40f;
        }

        /* Elevators */
        .elevators-row {
            display: flex;
            gap: 15px;
            justify-content: center;
        }
        .elevator-shaft {
            width: 50px;
            background: rgba(0,0,0,0.3);
            border-radius: 6px;
            position: relative;
            height: 200px;
            border: 1px solid #333;
        }
        .elevator-car {
            position: absolute;
            width: 44px;
            height: 20px;
            background: #4ecdc4;
            border-radius: 4px;
            left: 2px;
            transition: bottom 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.6rem;
            font-weight: 600;
            color: #000;
        }
        .elevator-car.idle { background: #4ecdc4; }
        .elevator-car.up { background: #2ecc71; }
        .elevator-car.down { background: #f1c40f; }
        .elevator-car.fault { background: #e74c3c; animation: faultPulse 0.5s infinite; }
        @keyframes faultPulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .elevator-label {
            text-align: center;
            font-size: 0.65rem;
            color: #888;
            margin-top: 5px;
        }
        .elevator-floor-marks {
            position: absolute;
            right: -20px;
            top: 0;
            bottom: 0;
            display: flex;
            flex-direction: column-reverse;
            justify-content: space-between;
            font-size: 0.5rem;
            color: #666;
            padding: 5px 0;
        }

        /* Sensor Summary */
        .sensor-summary {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }
        .sensor-stat {
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            padding: 10px;
            text-align: center;
        }
        .sensor-stat-value {
            font-size: 1.3rem;
            font-weight: 600;
            color: #4ecdc4;
        }
        .sensor-stat-value.online { color: #2ecc71; }
        .sensor-stat-value.offline { color: #e74c3c; }
        .sensor-stat-value.alert { color: #f1c40f; }
        .sensor-stat-label {
            font-size: 0.6rem;
            color: #666;
            text-transform: uppercase;
            margin-top: 3px;
        }

        .refresh-btn {
            background: #333;
            border: none;
            color: #888;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.65rem;
        }
        .refresh-btn:hover {
            background: #4ecdc4;
            color: #000;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Smart Building <span>Digital Twin</span></h1>
        <div id="certBadge" class="cert-badge"></div>
    </div>

    <div class="dashboard">
        <div class="summary-row">
            <div class="summary-card">
                <div class="summary-value" id="currentOccupancy">0</div>
                <div class="summary-label">Current Occupancy</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="occupiedRooms">0</div>
                <div class="summary-label">Occupied Rooms</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="avgTemp">22.0</div>
                <div class="summary-label">Avg Temp (C)</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="currentPower">0</div>
                <div class="summary-label">Power (kW)</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="todayEnergy">0</div>
                <div class="summary-label">Today (kWh)</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="sensorAlerts">0</div>
                <div class="summary-label">Sensor Alerts</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Building Floors</h3>
            </div>
            <div class="card-body">
                <div class="building-viz" id="floorList"></div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Rooms & Sensors</h3>
                <button class="refresh-btn" onclick="refresh()">Refresh</button>
            </div>
            <div class="card-body">
                <div class="rooms-grid" id="roomsGrid"></div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>HVAC System</h3>
            </div>
            <div class="card-body">
                <div class="hvac-status" id="hvacStatus"></div>
            </div>
        </div>

        <div class="card" style="grid-column: 2 / 3;">
            <div class="card-header">
                <h3>Elevators</h3>
            </div>
            <div class="card-body" style="display: flex; flex-direction: column; align-items: center; justify-content: center;">
                <div class="elevators-row" id="elevatorRow"></div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Sensor Health</h3>
            </div>
            <div class="card-body">
                <div class="sensor-summary" id="sensorSummary"></div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let selectedFloor = null;
        let state = {};

        function formatNumber(n) {
            return new Intl.NumberFormat().format(Math.round(n));
        }

        function updateSummary(summary) {
            document.getElementById('currentOccupancy').textContent = summary.currentOccupancy;
            document.getElementById('occupiedRooms').textContent =
                `${summary.occupiedRooms}/${summary.totalRooms}`;
            document.getElementById('avgTemp').textContent = summary.avgTemperature.toFixed(1);
            document.getElementById('currentPower').textContent = formatNumber(summary.currentPower);
            document.getElementById('todayEnergy').textContent = formatNumber(summary.todayConsumption);
            document.getElementById('certBadge').textContent = summary.certification || 'Smart Building';
        }

        function updateFloors(floors) {
            const container = document.getElementById('floorList');
            container.innerHTML = floors.map(floor => {
                const isSelected = selectedFloor === floor.id;
                return `
                    <div class="floor-bar ${isSelected ? 'selected' : ''}"
                         onclick="selectFloor('${floor.id}')">
                        <div class="floor-level">${floor.level}</div>
                        <div class="floor-name">${floor.name}</div>
                        <div class="floor-type">${floor.floorType}</div>
                    </div>
                `;
            }).join('');
        }

        function updateRooms(rooms) {
            const container = document.getElementById('roomsGrid');

            // Filter by selected floor if any
            let displayRooms = rooms;
            if (selectedFloor) {
                const floorNum = selectedFloor.replace('floor-', '');
                displayRooms = rooms.filter(r => r.id.includes(`-${floorNum}-`));
            }

            container.innerHTML = displayRooms.map(room => {
                const hasAlert = (room.co2 && room.co2 > 1000) ||
                                (room.temperature && (room.temperature < 18 || room.temperature > 28));
                const alertClass = hasAlert ? 'alert' : (room.isOccupied ? 'occupied' : '');

                const tempClass = room.temperature ?
                    (room.temperature < 18 || room.temperature > 28 ? 'danger' :
                     room.temperature < 20 || room.temperature > 26 ? 'warning' : '') : '';
                const co2Class = room.co2 ? (room.co2 > 1000 ? 'danger' : room.co2 > 800 ? 'warning' : '') : '';

                return `
                    <div class="room-card ${alertClass}">
                        <div class="room-header">
                            <div>
                                <div class="room-name">${room.name}</div>
                                <div class="room-type">${room.roomType} · ${room.area}m²</div>
                            </div>
                            <div class="room-status ${room.isOccupied ? 'occupied' : ''}"></div>
                        </div>
                        <div class="room-sensors">
                            ${room.temperature !== null ? `
                                <div class="sensor-reading">
                                    <div class="sensor-value ${tempClass}">${room.temperature.toFixed(1)}°</div>
                                    <div class="sensor-label">Temp</div>
                                </div>
                            ` : '<div class="sensor-reading"><div class="sensor-value">--</div><div class="sensor-label">Temp</div></div>'}
                            ${room.co2 !== null ? `
                                <div class="sensor-reading">
                                    <div class="sensor-value ${co2Class}">${room.co2}</div>
                                    <div class="sensor-label">CO2 ppm</div>
                                </div>
                            ` : '<div class="sensor-reading"><div class="sensor-value">--</div><div class="sensor-label">CO2</div></div>'}
                            ${room.humidity !== null ? `
                                <div class="sensor-reading">
                                    <div class="sensor-value">${room.humidity.toFixed(0)}%</div>
                                    <div class="sensor-label">Humidity</div>
                                </div>
                            ` : ''}
                            <div class="sensor-reading">
                                <div class="sensor-value">${room.currentOccupancy}/${room.maxOccupancy}</div>
                                <div class="sensor-label">Occupancy</div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateHVAC(hvac) {
            const container = document.getElementById('hvacStatus');
            let html = '';

            if (hvac.plant) {
                html += `
                    <div class="hvac-plant">
                        <div class="hvac-plant-name">${hvac.plant.name}</div>
                        <div class="hvac-stats">
                            <span>Cooling: <span class="hvac-stat">${hvac.plant.coolingCapacity} tons</span></span>
                            <span>Heating: <span class="hvac-stat">${hvac.plant.heatingCapacity} kW</span></span>
                        </div>
                    </div>
                `;
            }

            if (hvac.ahus.length > 0) {
                html += '<div class="ahu-list">';
                hvac.ahus.forEach(ahu => {
                    const statusClass = ahu.status === 'operational' ? '' : 'warning';
                    html += `
                        <div class="ahu-item">
                            <div class="ahu-icon">🌀</div>
                            <div class="ahu-info">
                                <div class="ahu-name">${ahu.name}</div>
                                <div class="ahu-meta">${ahu.airflowCapacity} CFM · ${ahu.filterType}</div>
                            </div>
                            <div class="ahu-status ${statusClass}">${ahu.status}</div>
                        </div>
                    `;
                });
                html += '</div>';
            }

            container.innerHTML = html;
        }

        function updateElevators(elevators) {
            const container = document.getElementById('elevatorRow');
            const maxFloor = 9;

            container.innerHTML = elevators.map(elev => {
                const bottomPct = (elev.currentFloor / maxFloor) * 100;
                const dirClass = elev.direction === 'up' ? 'up' :
                                 elev.direction === 'down' ? 'down' :
                                 elev.status !== 'operational' ? 'fault' : 'idle';
                return `
                    <div>
                        <div class="elevator-shaft">
                            <div class="elevator-car ${dirClass}"
                                 style="bottom: calc(${bottomPct}% - 10px)">
                                ${elev.currentFloor}
                            </div>
                            <div class="elevator-floor-marks">
                                ${Array.from({length: 10}, (_, i) => `<span>${i}</span>`).join('')}
                            </div>
                        </div>
                        <div class="elevator-label">${elev.name}</div>
                    </div>
                `;
            }).join('');
        }

        function updateSensorSummary(sensors) {
            document.getElementById('sensorAlerts').textContent = sensors.alerts;
            const alertEl = document.getElementById('sensorAlerts');
            alertEl.className = 'summary-value' + (sensors.alerts > 0 ? ' danger' : '');

            document.getElementById('sensorSummary').innerHTML = `
                <div class="sensor-stat">
                    <div class="sensor-stat-value">${sensors.total}</div>
                    <div class="sensor-stat-label">Total Sensors</div>
                </div>
                <div class="sensor-stat">
                    <div class="sensor-stat-value online">${sensors.online}</div>
                    <div class="sensor-stat-label">Online</div>
                </div>
                <div class="sensor-stat">
                    <div class="sensor-stat-value offline">${sensors.offline}</div>
                    <div class="sensor-stat-label">Offline</div>
                </div>
                <div class="sensor-stat">
                    <div class="sensor-stat-value alert">${sensors.alerts}</div>
                    <div class="sensor-stat-label">Alerts</div>
                </div>
            `;
        }

        function selectFloor(floorId) {
            selectedFloor = selectedFloor === floorId ? null : floorId;
            updateFloors(state.floors || []);
            updateRooms(state.rooms || []);
        }

        function updateUI(data) {
            state = data;
            if (data.summary) updateSummary(data.summary);
            if (data.floors) updateFloors(data.floors);
            if (data.rooms) updateRooms(data.rooms);
            if (data.hvac) updateHVAC(data.hvac);
            if (data.elevators) updateElevators(data.elevators);
            if (data.sensors) updateSensorSummary(data.sensors);
        }

        function refresh() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'refresh' }));
            }
        }

        function connect() {
            ws = new WebSocket(`ws://${window.location.hostname}:WS_PORT`);

            ws.onopen = () => console.log('Connected');
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'init' || data.type === 'update') {
                    updateUI(data);
                }
            };
            ws.onclose = () => {
                console.log('Disconnected, reconnecting...');
                setTimeout(connect, 2000);
            };
        }

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

    client = get_client()
    load_building_data()

    http_server = HTTPServer(('', port), WebHandler)
    http_thread = threading.Thread(target=http_server.serve_forever)
    http_thread.daemon = True
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Smart Building Digital Twin - Web UI")
    print(f"{'='*60}")
    print(f"  Open http://localhost:{port} in your browser")
    print(f"  Building: {building.get('name', 'Unknown')}")
    print(f"  Floors: {len(floors)}")
    print(f"  Rooms: {len(rooms)}")
    print(f"  Sensors: {len(sensors)}")
    print(f"{'='*60}\n")

    asyncio.create_task(periodic_update())

    async with websockets.serve(handle_websocket, "", ws_port):
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Building Web UI")
    parser.add_argument("--port", type=int, default=8082, help="HTTP port (default: 8082)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port))
    except KeyboardInterrupt:
        print("\nShutdown requested")
