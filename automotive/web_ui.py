#!/usr/bin/env python3
"""
Automotive / Fleet Management Digital Twin - Web UI
=====================================================

Real-time fleet monitoring dashboard showing:
- Vehicle fleet overview
- Vehicle locations and status
- Charging station usage
- Driver status and safety scores
- Delivery tracking
- Maintenance schedule

Usage:
    python web_ui.py [--port PORT] [--base-url URL]
"""

import sys
import os
import json
import asyncio
import argparse
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Domain
DOMAIN = "automotive"


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


class AutomotiveDataCollector:
    """Collects data from the automotive digital twin."""

    def __init__(self, client):
        self.client = client

    def collect_data(self) -> dict:
        """Collect all automotive data."""
        try:
            twins = self.client.twins.list(domain=DOMAIN, page_size=500)

            data = {
                "timestamp": datetime.now().isoformat(),
                "fleet": None,
                "depots": [],
                "electricVehicles": [],
                "hybridVehicles": [],
                "conventionalVehicles": [],
                "drivers": [],
                "chargingStations": [],
                "maintenanceRecords": [],
                "routes": [],
                "deliveries": [],
                "fms": None,
                "stats": {
                    "totalVehicles": 0,
                    "activeVehicles": 0,
                    "chargingVehicles": 0,
                    "maintenanceVehicles": 0,
                    "totalDrivers": 0,
                    "driversOnDuty": 0,
                    "portsInUse": 0,
                    "totalPorts": 0,
                    "deliveriesInProgress": 0,
                    "deliveriesCompleted": 0,
                    "avgBatteryLevel": 0,
                    "avgSafetyScore": 0
                }
            }

            ev_battery_total = 0
            ev_count = 0
            safety_total = 0
            driver_count = 0

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                twin_type = type_val.split("#")[-1] if type_val else ""
                twin_id = twin_dict["id"]
                raw_props = twin_dict.get("properties", {})
                props = _normalize_properties(raw_props)

                item = {
                    "id": twin_id,
                    "name": twin_dict.get("name", twin_id),
                    "type": twin_type,
                    "properties": props
                }

                if twin_type == "VehicleFleet":
                    data["fleet"] = item
                elif twin_type == "VehicleDepot":
                    data["depots"].append(item)
                elif twin_type == "ElectricVehicle":
                    data["electricVehicles"].append(item)
                    data["stats"]["totalVehicles"] += 1
                    status = props.get("status", "")
                    if status == "active":
                        data["stats"]["activeVehicles"] += 1
                    elif status == "charging":
                        data["stats"]["chargingVehicles"] += 1
                    elif status == "maintenance":
                        data["stats"]["maintenanceVehicles"] += 1
                    ev_battery_total += props.get("currentBatteryLevel", 0)
                    ev_count += 1
                elif twin_type == "HybridVehicle":
                    data["hybridVehicles"].append(item)
                    data["stats"]["totalVehicles"] += 1
                    if props.get("status") == "active":
                        data["stats"]["activeVehicles"] += 1
                elif twin_type == "ConventionalVehicle":
                    data["conventionalVehicles"].append(item)
                    data["stats"]["totalVehicles"] += 1
                    status = props.get("status", "")
                    if status == "active":
                        data["stats"]["activeVehicles"] += 1
                    elif status == "maintenance":
                        data["stats"]["maintenanceVehicles"] += 1
                elif twin_type == "Driver":
                    data["drivers"].append(item)
                    data["stats"]["totalDrivers"] += 1
                    if props.get("currentDutyStatus") == "driving":
                        data["stats"]["driversOnDuty"] += 1
                    safety_total += props.get("safetyScore", 0)
                    driver_count += 1
                elif twin_type == "ChargingStation":
                    data["chargingStations"].append(item)
                    data["stats"]["portsInUse"] += props.get("portsInUse", 0)
                    data["stats"]["totalPorts"] += props.get("ports", 0)
                elif twin_type == "MaintenanceRecord":
                    data["maintenanceRecords"].append(item)
                elif twin_type == "DeliveryRoute":
                    data["routes"].append(item)
                elif twin_type == "Delivery":
                    data["deliveries"].append(item)
                    status = props.get("status", "")
                    if status == "in_progress":
                        data["stats"]["deliveriesInProgress"] += 1
                    elif status == "completed":
                        data["stats"]["deliveriesCompleted"] += 1
                elif twin_type == "FleetManagementSystem":
                    data["fms"] = item

            if ev_count > 0:
                data["stats"]["avgBatteryLevel"] = round(ev_battery_total / ev_count)
            if driver_count > 0:
                data["stats"]["avgSafetyScore"] = round(safety_total / driver_count)

            return data

        except Exception as e:
            logger.error(f"Failed to collect data: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fleet Management Digital Twin - Metro Logistics</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f1a 100%);
            min-height: 100vh;
            color: #e2e8f0;
            padding: 20px;
        }

        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 20px;
            background: linear-gradient(135deg, rgba(251, 146, 60, 0.2), rgba(234, 88, 12, 0.2));
            border-radius: 16px;
            border: 1px solid rgba(251, 146, 60, 0.3);
        }

        .header h1 {
            font-size: 2em;
            color: #fb923c;
            margin-bottom: 5px;
        }

        .header .subtitle {
            color: #94a3b8;
            font-size: 0.95em;
        }

        .stats-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9));
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            border: 1px solid rgba(251, 146, 60, 0.2);
        }

        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #fb923c;
        }

        .stat-value.success { color: #34d399; }
        .stat-value.warning { color: #fbbf24; }
        .stat-value.info { color: #60a5fa; }

        .stat-label {
            color: #94a3b8;
            font-size: 0.8em;
            margin-top: 5px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .panel {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.8));
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(251, 146, 60, 0.15);
        }

        .panel h2 {
            color: #fb923c;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.1em;
        }

        /* Vehicle Grid */
        .vehicle-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
            gap: 8px;
            max-height: 280px;
            overflow-y: auto;
        }

        .vehicle-card {
            background: rgba(34, 197, 94, 0.15);
            border: 1px solid rgba(34, 197, 94, 0.3);
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            font-size: 0.8em;
        }

        .vehicle-card.charging {
            background: rgba(59, 130, 246, 0.15);
            border-color: rgba(59, 130, 246, 0.3);
            animation: pulse-charge 2s infinite;
        }

        .vehicle-card.maintenance {
            background: rgba(239, 68, 68, 0.15);
            border-color: rgba(239, 68, 68, 0.3);
        }

        @keyframes pulse-charge {
            0%, 100% { box-shadow: 0 0 5px rgba(59, 130, 246, 0.3); }
            50% { box-shadow: 0 0 15px rgba(59, 130, 246, 0.6); }
        }

        .vehicle-icon {
            font-size: 1.5em;
            margin-bottom: 4px;
        }

        .vehicle-id {
            font-weight: 600;
        }

        .vehicle-battery {
            font-size: 0.75em;
            color: #94a3b8;
        }

        /* Charging Stations */
        .charger-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
        }

        .charger-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
            border-left: 4px solid #22c55e;
        }

        .charger-name {
            font-weight: 600;
            font-size: 0.85em;
            margin-bottom: 8px;
        }

        .charger-type {
            font-size: 0.7em;
            color: #64748b;
            margin-bottom: 8px;
        }

        .port-indicator {
            display: flex;
            gap: 4px;
            flex-wrap: wrap;
        }

        .port {
            width: 12px;
            height: 12px;
            border-radius: 3px;
            background: rgba(34, 197, 94, 0.3);
            border: 1px solid rgba(34, 197, 94, 0.5);
        }

        .port.in-use {
            background: rgba(59, 130, 246, 0.8);
            border-color: rgba(59, 130, 246, 1);
        }

        /* Drivers */
        .driver-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
            max-height: 280px;
            overflow-y: auto;
        }

        .driver-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .driver-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(135deg, #fb923c, #ea580c);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
        }

        .driver-info {
            flex: 1;
        }

        .driver-name {
            font-weight: 500;
            font-size: 0.85em;
        }

        .driver-status {
            font-size: 0.7em;
            padding: 2px 6px;
            border-radius: 8px;
            display: inline-block;
            margin-top: 4px;
        }

        .driver-status.driving { background: rgba(34, 197, 94, 0.2); color: #34d399; }
        .driver-status.on_break { background: rgba(234, 179, 8, 0.2); color: #fbbf24; }
        .driver-status.off_duty { background: rgba(100, 116, 139, 0.2); color: #94a3b8; }

        .driver-score {
            text-align: right;
        }

        .score-value {
            font-size: 1.2em;
            font-weight: bold;
            color: #34d399;
        }

        .score-value.medium { color: #fbbf24; }
        .score-value.low { color: #ef4444; }

        .score-label {
            font-size: 0.65em;
            color: #64748b;
        }

        /* Deliveries */
        .delivery-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            max-height: 280px;
            overflow-y: auto;
        }

        .delivery-item {
            background: rgba(15, 23, 42, 0.5);
            border-radius: 10px;
            padding: 12px;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .delivery-status-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2em;
        }

        .delivery-status-icon.in_progress {
            background: rgba(59, 130, 246, 0.2);
        }

        .delivery-status-icon.completed {
            background: rgba(34, 197, 94, 0.2);
        }

        .delivery-status-icon.scheduled {
            background: rgba(100, 116, 139, 0.2);
        }

        .delivery-info {
            flex: 1;
        }

        .delivery-name {
            font-weight: 500;
            font-size: 0.9em;
        }

        .delivery-progress {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 6px;
        }

        .progress-bar {
            flex: 1;
            height: 6px;
            background: rgba(51, 65, 85, 0.5);
            border-radius: 3px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #3b82f6, #60a5fa);
            border-radius: 3px;
        }

        .progress-text {
            font-size: 0.75em;
            color: #94a3b8;
            min-width: 60px;
        }

        /* Maintenance */
        .maintenance-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .maintenance-item {
            background: rgba(15, 23, 42, 0.5);
            border-radius: 8px;
            padding: 10px 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .maintenance-info {
            flex: 1;
        }

        .maintenance-type {
            font-weight: 500;
            font-size: 0.85em;
        }

        .maintenance-vehicle {
            font-size: 0.75em;
            color: #64748b;
        }

        .maintenance-status {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.7em;
            font-weight: 600;
        }

        .maintenance-status.completed { background: rgba(34, 197, 94, 0.2); color: #34d399; }
        .maintenance-status.scheduled { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
        .maintenance-status.in_progress { background: rgba(234, 179, 8, 0.2); color: #fbbf24; }

        /* Depots */
        .depot-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }

        .depot-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 15px;
            border-left: 4px solid #fb923c;
        }

        .depot-name {
            font-weight: 600;
            font-size: 0.95em;
            margin-bottom: 10px;
        }

        .depot-stats {
            font-size: 0.8em;
            color: #94a3b8;
        }

        .depot-stat {
            display: flex;
            justify-content: space-between;
            margin-bottom: 4px;
        }

        /* Connection Status */
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }

        .connection-status.connected {
            background: rgba(34, 197, 94, 0.2);
            color: #34d399;
            border: 1px solid rgba(34, 197, 94, 0.3);
        }

        .connection-status.disconnected {
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .timestamp {
            text-align: center;
            color: #64748b;
            font-size: 0.85em;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div id="connection-status" class="connection-status disconnected">Connecting...</div>

    <div class="header">
        <h1>Metro Logistics Fleet Management</h1>
        <div class="subtitle">Automotive Digital Twin - Real-Time Fleet Monitoring</div>
    </div>

    <div class="stats-bar">
        <div class="stat-card">
            <div class="stat-value" id="total-vehicles">-</div>
            <div class="stat-label">Total Vehicles</div>
        </div>
        <div class="stat-card">
            <div class="stat-value success" id="active-vehicles">-</div>
            <div class="stat-label">Active</div>
        </div>
        <div class="stat-card">
            <div class="stat-value info" id="charging-vehicles">-</div>
            <div class="stat-label">Charging</div>
        </div>
        <div class="stat-card">
            <div class="stat-value warning" id="maintenance-vehicles">-</div>
            <div class="stat-label">In Maintenance</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="drivers-on-duty">-</div>
            <div class="stat-label">Drivers On Duty</div>
        </div>
        <div class="stat-card">
            <div class="stat-value info" id="avg-battery">-</div>
            <div class="stat-label">Avg EV Battery</div>
        </div>
        <div class="stat-card">
            <div class="stat-value success" id="avg-safety">-</div>
            <div class="stat-label">Avg Safety Score</div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Electric Vehicle Fleet</h2>
            <div class="vehicle-grid" id="ev-fleet"></div>
        </div>

        <div class="panel">
            <h2>Charging Stations</h2>
            <div class="charger-grid" id="chargers"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Driver Status</h2>
            <div class="driver-grid" id="drivers"></div>
        </div>

        <div class="panel">
            <h2>Active Deliveries</h2>
            <div class="delivery-list" id="deliveries"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Depots</h2>
            <div class="depot-grid" id="depots"></div>
        </div>

        <div class="panel">
            <h2>Maintenance Schedule</h2>
            <div class="maintenance-list" id="maintenance"></div>
        </div>
    </div>

    <div class="timestamp" id="timestamp">Waiting for data...</div>

    <script>
        let ws;
        let reconnectInterval;

        function connect() {
            const wsUrl = `ws://${window.location.hostname}:${parseInt(window.location.port) + 1}`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                document.getElementById('connection-status').className = 'connection-status connected';
                document.getElementById('connection-status').textContent = 'Connected';
                if (reconnectInterval) {
                    clearInterval(reconnectInterval);
                    reconnectInterval = null;
                }
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };

            ws.onclose = () => {
                document.getElementById('connection-status').className = 'connection-status disconnected';
                document.getElementById('connection-status').textContent = 'Disconnected';
                if (!reconnectInterval) {
                    reconnectInterval = setInterval(connect, 3000);
                }
            };

            ws.onerror = () => ws.close();
        }

        function updateDashboard(data) {
            if (data.error) {
                document.getElementById('timestamp').textContent = `Error: ${data.error}`;
                return;
            }

            const stats = data.stats || {};

            // Stats
            document.getElementById('total-vehicles').textContent = stats.totalVehicles || 0;
            document.getElementById('active-vehicles').textContent = stats.activeVehicles || 0;
            document.getElementById('charging-vehicles').textContent = stats.chargingVehicles || 0;
            document.getElementById('maintenance-vehicles').textContent = stats.maintenanceVehicles || 0;
            document.getElementById('drivers-on-duty').textContent = `${stats.driversOnDuty || 0}/${stats.totalDrivers || 0}`;
            document.getElementById('avg-battery').textContent = (stats.avgBatteryLevel || 0) + '%';
            document.getElementById('avg-safety').textContent = stats.avgSafetyScore || 0;

            // EV Fleet
            const evContainer = document.getElementById('ev-fleet');
            evContainer.innerHTML = (data.electricVehicles || []).slice(0, 40).map(ev => {
                const props = ev.properties || {};
                const status = props.status || 'active';
                const battery = props.currentBatteryLevel || 0;
                const icon = status === 'charging' ? '🔌' : '🚐';
                return `
                    <div class="vehicle-card ${status}">
                        <div class="vehicle-icon">${icon}</div>
                        <div class="vehicle-id">${ev.id.replace('ev-', 'EV-')}</div>
                        <div class="vehicle-battery">${battery}%</div>
                    </div>
                `;
            }).join('');

            // Charging Stations
            const chargerContainer = document.getElementById('chargers');
            chargerContainer.innerHTML = (data.chargingStations || []).map(charger => {
                const props = charger.properties || {};
                const ports = props.ports || 0;
                const inUse = props.portsInUse || 0;
                let portHtml = '';
                for (let i = 0; i < ports; i++) {
                    portHtml += `<div class="port ${i < inUse ? 'in-use' : ''}"></div>`;
                }
                return `
                    <div class="charger-card">
                        <div class="charger-name">${charger.name}</div>
                        <div class="charger-type">${props.chargerType || ''} - ${props.maxPower || 0} kW</div>
                        <div class="port-indicator">${portHtml}</div>
                    </div>
                `;
            }).join('');

            // Drivers
            const driverContainer = document.getElementById('drivers');
            driverContainer.innerHTML = (data.drivers || []).slice(0, 20).map(driver => {
                const props = driver.properties || {};
                const status = props.currentDutyStatus || 'off_duty';
                const score = props.safetyScore || 0;
                const scoreClass = score >= 90 ? '' : score >= 75 ? 'medium' : 'low';
                const initials = driver.name.split(' ').pop().replace(/[0-9]/g, '').substring(0, 2).toUpperCase() || 'DR';
                return `
                    <div class="driver-card">
                        <div class="driver-avatar">${initials}</div>
                        <div class="driver-info">
                            <div class="driver-name">${driver.name}</div>
                            <span class="driver-status ${status}">${status.replace('_', ' ')}</span>
                        </div>
                        <div class="driver-score">
                            <div class="score-value ${scoreClass}">${score}</div>
                            <div class="score-label">Safety</div>
                        </div>
                    </div>
                `;
            }).join('');

            // Deliveries
            const deliveryContainer = document.getElementById('deliveries');
            const activeDeliveries = (data.deliveries || []).filter(d =>
                d.properties?.status === 'in_progress' || d.properties?.status === 'scheduled'
            ).slice(0, 10);
            deliveryContainer.innerHTML = activeDeliveries.map(delivery => {
                const props = delivery.properties || {};
                const status = props.status || 'scheduled';
                const completed = props.stopsCompleted || 0;
                const total = props.totalStops || 1;
                const progress = Math.round((completed / total) * 100);
                const icon = status === 'in_progress' ? '🚚' : status === 'completed' ? '✓' : '📋';
                return `
                    <div class="delivery-item">
                        <div class="delivery-status-icon ${status}">${icon}</div>
                        <div class="delivery-info">
                            <div class="delivery-name">${delivery.name}</div>
                            <div class="delivery-progress">
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${progress}%"></div>
                                </div>
                                <span class="progress-text">${completed}/${total} stops</span>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // Depots
            const depotContainer = document.getElementById('depots');
            depotContainer.innerHTML = (data.depots || []).map(depot => {
                const props = depot.properties || {};
                return `
                    <div class="depot-card">
                        <div class="depot-name">${depot.name}</div>
                        <div class="depot-stats">
                            <div class="depot-stat">
                                <span>Vehicles</span>
                                <span>${props.currentVehicles || 0}/${props.capacity || 0}</span>
                            </div>
                            <div class="depot-stat">
                                <span>Chargers</span>
                                <span>${props.chargingStations || 0}</span>
                            </div>
                            <div class="depot-stat">
                                <span>Maintenance Bays</span>
                                <span>${props.maintenanceBays || 0}</span>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // Maintenance
            const maintContainer = document.getElementById('maintenance');
            const recentMaint = (data.maintenanceRecords || []).slice(0, 8);
            maintContainer.innerHTML = recentMaint.map(maint => {
                const props = maint.properties || {};
                const status = props.status || 'scheduled';
                const type = (props.maintenanceType || '').replace(/_/g, ' ');
                return `
                    <div class="maintenance-item">
                        <div class="maintenance-info">
                            <div class="maintenance-type">${type}</div>
                            <div class="maintenance-vehicle">Vehicle: ${maint.name.split('-')[1] || 'N/A'}</div>
                        </div>
                        <span class="maintenance-status ${status}">${status.replace('_', ' ')}</span>
                    </div>
                `;
            }).join('');

            // Timestamp
            document.getElementById('timestamp').textContent =
                `Last updated: ${new Date(data.timestamp).toLocaleString()}`;
        }

        connect();
    </script>
</body>
</html>
"""


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for the dashboard."""

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Suppress logging


async def websocket_handler(websocket, collector):
    """Handle WebSocket connections."""
    logger.info(f"Client connected: {websocket.remote_address}")
    try:
        while True:
            data = collector.collect_data()
            await websocket.send(json.dumps(data))
            await asyncio.sleep(5)
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {websocket.remote_address}")


async def start_websocket_server(port: int, collector: AutomotiveDataCollector):
    """Start the WebSocket server."""
    async with websockets.serve(
        lambda ws: websocket_handler(ws, collector),
        "0.0.0.0",
        port
    ):
        logger.info(f"WebSocket server started on port {port}")
        await asyncio.Future()


def run_http_server(port: int):
    """Run the HTTP server."""
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    logger.info(f"HTTP server started on port {port}")
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Automotive Digital Twin Web UI")
    parser.add_argument("--port", type=int, default=8094, help="HTTP server port")
    parser.add_argument("--base-url", help="DTaaS server URL")
    args = parser.parse_args()

    client = get_client(args.base_url)
    collector = AutomotiveDataCollector(client)

    # Start HTTP server in a thread
    http_thread = threading.Thread(target=run_http_server, args=(args.port,), daemon=True)
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Automotive Digital Twin - Web UI")
    print(f"  Open http://localhost:{args.port} in your browser")
    print(f"{'='*60}\n")

    # Run WebSocket server
    asyncio.run(start_websocket_server(args.port + 1, collector))


if __name__ == "__main__":
    main()
