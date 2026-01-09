#!/usr/bin/env python3
"""
Healthcare / Hospital Digital Twin - Web UI
============================================

Real-time hospital monitoring dashboard showing:
- Department status and bed occupancy
- Operating room availability
- ICU patient rooms and equipment
- Medical imaging equipment status
- Surgical robots
- Laboratory equipment
- Emergency department metrics

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
DOMAIN = "healthcare"


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


class HealthcareDataCollector:
    """Collects data from the healthcare digital twin."""

    def __init__(self, client):
        self.client = client

    def collect_data(self) -> dict:
        """Collect all healthcare data."""
        try:
            twins = self.client.twins.list(domain=DOMAIN, page_size=300)

            data = {
                "timestamp": datetime.now().isoformat(),
                "hospital": None,
                "buildings": [],
                "departments": [],
                "operatingRooms": [],
                "icuRooms": [],
                "imagingEquipment": [],
                "monitors": [],
                "ventilators": [],
                "infusionPumps": [],
                "surgicalRobots": [],
                "labEquipment": [],
                "pharmacySystems": [],
                "medicalGas": [],
                "sterilizers": [],
                "stats": {
                    "totalBeds": 0,
                    "occupiedBeds": 0,
                    "availableORs": 0,
                    "totalORs": 0,
                    "activeMonitors": 0,
                    "ventilatorInUse": 0,
                    "criticalAlerts": 0
                }
            }

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

                if twin_type == "Hospital":
                    data["hospital"] = item
                elif twin_type == "HospitalBuilding":
                    data["buildings"].append(item)
                elif twin_type == "HospitalDepartment":
                    data["departments"].append(item)
                    total_beds = props.get("totalBeds", 0)
                    occupied = props.get("occupiedBeds", 0)
                    data["stats"]["totalBeds"] += total_beds
                    data["stats"]["occupiedBeds"] += occupied
                elif twin_type == "OperatingRoom":
                    data["operatingRooms"].append(item)
                    data["stats"]["totalORs"] += 1
                    if props.get("status") == "available":
                        data["stats"]["availableORs"] += 1
                elif twin_type == "PatientRoom":
                    if props.get("roomType") == "ICU":
                        data["icuRooms"].append(item)
                elif twin_type in ["MRI", "CT", "X-Ray", "PortableXRay", "Ultrasound", "PET-CT", "Mammography", "Fluoroscopy"]:
                    data["imagingEquipment"].append(item)
                elif twin_type == "PatientMonitor":
                    data["monitors"].append(item)
                    if props.get("status") == "active":
                        data["stats"]["activeMonitors"] += 1
                elif twin_type == "Ventilator":
                    data["ventilators"].append(item)
                    if props.get("status") == "in_use":
                        data["stats"]["ventilatorInUse"] += 1
                elif twin_type == "InfusionPump":
                    data["infusionPumps"].append(item)
                elif twin_type in ["DaVinciRobot", "MAKORobot", "ROSARobot"]:
                    data["surgicalRobots"].append(item)
                elif twin_type in ["ChemistryAnalyzer", "HematologyAnalyzer", "BloodGasAnalyzer",
                                   "CoagulationAnalyzer", "UrinalysisAnalyzer", "Centrifuge", "PCRMachine"]:
                    data["labEquipment"].append(item)
                elif twin_type in ["PharmacyRobot", "MedicationCabinet"]:
                    data["pharmacySystems"].append(item)
                elif twin_type == "MedicalGasSystem":
                    data["medicalGas"].append(item)
                    if props.get("tankLevel", 100) < 25:
                        data["stats"]["criticalAlerts"] += 1
                elif twin_type == "Sterilizer":
                    data["sterilizers"].append(item)

            return data

        except Exception as e:
            logger.error(f"Failed to collect data: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Healthcare Digital Twin - Central Medical Center</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #0a1628 0%, #1a365d 50%, #0d2137 100%);
            min-height: 100vh;
            color: #e2e8f0;
            padding: 20px;
        }

        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 20px;
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(6, 182, 212, 0.2));
            border-radius: 16px;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }

        .header h1 {
            font-size: 2em;
            color: #60a5fa;
            margin-bottom: 5px;
        }

        .header .subtitle {
            color: #94a3b8;
            font-size: 0.95em;
        }

        .stats-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: linear-gradient(135deg, rgba(30, 58, 95, 0.9), rgba(15, 35, 60, 0.9));
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            border: 1px solid rgba(59, 130, 246, 0.2);
        }

        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #60a5fa;
        }

        .stat-value.warning { color: #fbbf24; }
        .stat-value.critical { color: #ef4444; }
        .stat-value.success { color: #34d399; }

        .stat-label {
            color: #94a3b8;
            font-size: 0.85em;
            margin-top: 5px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .panel {
            background: linear-gradient(135deg, rgba(30, 58, 95, 0.8), rgba(15, 35, 60, 0.8));
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(59, 130, 246, 0.2);
        }

        .panel h2 {
            color: #60a5fa;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.1em;
        }

        /* Department Status */
        .department-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
        }

        .department-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
            border-left: 4px solid #3b82f6;
        }

        .department-card.high-occupancy { border-left-color: #f59e0b; }
        .department-card.full { border-left-color: #ef4444; }

        .dept-name {
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 0.9em;
        }

        .dept-beds {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .bed-bar {
            flex: 1;
            height: 8px;
            background: rgba(51, 65, 85, 0.5);
            border-radius: 4px;
            overflow: hidden;
        }

        .bed-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }

        .bed-fill.low { background: linear-gradient(90deg, #22c55e, #16a34a); }
        .bed-fill.medium { background: linear-gradient(90deg, #eab308, #ca8a04); }
        .bed-fill.high { background: linear-gradient(90deg, #ef4444, #dc2626); }

        .bed-text {
            font-size: 0.8em;
            color: #94a3b8;
            min-width: 50px;
            text-align: right;
        }

        /* Operating Rooms */
        .or-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
            gap: 8px;
        }

        .or-card {
            background: rgba(34, 197, 94, 0.2);
            border: 1px solid rgba(34, 197, 94, 0.4);
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            transition: all 0.3s;
        }

        .or-card.in-use {
            background: rgba(239, 68, 68, 0.2);
            border-color: rgba(239, 68, 68, 0.4);
            animation: pulse-red 2s infinite;
        }

        .or-card.preparing {
            background: rgba(234, 179, 8, 0.2);
            border-color: rgba(234, 179, 8, 0.4);
        }

        .or-card.cleaning {
            background: rgba(59, 130, 246, 0.2);
            border-color: rgba(59, 130, 246, 0.4);
        }

        @keyframes pulse-red {
            0%, 100% { box-shadow: 0 0 5px rgba(239, 68, 68, 0.3); }
            50% { box-shadow: 0 0 15px rgba(239, 68, 68, 0.6); }
        }

        .or-number {
            font-weight: bold;
            font-size: 1.1em;
        }

        .or-type {
            font-size: 0.7em;
            color: #94a3b8;
            text-transform: uppercase;
        }

        /* ICU Rooms */
        .icu-grid {
            display: grid;
            grid-template-columns: repeat(10, 1fr);
            gap: 6px;
        }

        .icu-room {
            aspect-ratio: 1;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75em;
            font-weight: bold;
            border: 1px solid rgba(100, 116, 139, 0.3);
            background: rgba(34, 197, 94, 0.2);
        }

        .icu-room.occupied {
            background: rgba(239, 68, 68, 0.3);
            border-color: rgba(239, 68, 68, 0.5);
        }

        .icu-room.isolation {
            background: rgba(168, 85, 247, 0.3);
            border-color: rgba(168, 85, 247, 0.5);
        }

        /* Equipment Grid */
        .equipment-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
            max-height: 300px;
            overflow-y: auto;
        }

        .equipment-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(15, 23, 42, 0.5);
            padding: 10px 12px;
            border-radius: 8px;
            border-left: 3px solid #3b82f6;
        }

        .equipment-item.offline {
            border-left-color: #ef4444;
            opacity: 0.7;
        }

        .equip-info {
            flex: 1;
        }

        .equip-name {
            font-weight: 500;
            font-size: 0.9em;
        }

        .equip-model {
            font-size: 0.75em;
            color: #64748b;
        }

        .equip-status {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 600;
            text-transform: uppercase;
        }

        .equip-status.available { background: rgba(34, 197, 94, 0.2); color: #34d399; }
        .equip-status.in-use { background: rgba(239, 68, 68, 0.2); color: #f87171; }
        .equip-status.maintenance { background: rgba(234, 179, 8, 0.2); color: #fbbf24; }
        .equip-status.operational { background: rgba(34, 197, 94, 0.2); color: #34d399; }

        /* Surgical Robots */
        .robot-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 10px;
        }

        .robot-card {
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(59, 130, 246, 0.2));
            border: 1px solid rgba(139, 92, 246, 0.3);
            border-radius: 10px;
            padding: 15px;
            text-align: center;
        }

        .robot-icon {
            font-size: 2em;
            margin-bottom: 8px;
        }

        .robot-name {
            font-weight: 600;
            font-size: 0.85em;
            margin-bottom: 5px;
        }

        .robot-stats {
            font-size: 0.75em;
            color: #94a3b8;
        }

        /* Ventilators */
        .vent-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 10px;
        }

        .vent-card {
            background: rgba(6, 182, 212, 0.1);
            border: 1px solid rgba(6, 182, 212, 0.3);
            border-radius: 10px;
            padding: 12px;
            text-align: center;
        }

        .vent-card.in-use {
            animation: breathe 3s infinite;
        }

        @keyframes breathe {
            0%, 100% { background: rgba(6, 182, 212, 0.1); }
            50% { background: rgba(6, 182, 212, 0.25); }
        }

        .vent-icon {
            font-size: 1.5em;
            margin-bottom: 5px;
        }

        .vent-mode {
            font-size: 0.75em;
            color: #22d3ee;
            font-weight: 600;
        }

        .vent-params {
            font-size: 0.7em;
            color: #94a3b8;
            margin-top: 4px;
        }

        /* Medical Gas */
        .gas-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
            gap: 10px;
        }

        .gas-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
            text-align: center;
        }

        .gas-icon {
            font-size: 1.8em;
            margin-bottom: 5px;
        }

        .gas-name {
            font-size: 0.8em;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .gas-level {
            height: 60px;
            width: 30px;
            margin: 0 auto;
            background: rgba(51, 65, 85, 0.5);
            border-radius: 15px;
            position: relative;
            overflow: hidden;
        }

        .gas-fill {
            position: absolute;
            bottom: 0;
            width: 100%;
            border-radius: 15px;
            transition: height 0.5s;
        }

        .gas-fill.high { background: linear-gradient(180deg, #22c55e, #16a34a); }
        .gas-fill.medium { background: linear-gradient(180deg, #eab308, #ca8a04); }
        .gas-fill.low { background: linear-gradient(180deg, #ef4444, #dc2626); }

        .gas-percent {
            font-size: 0.75em;
            color: #94a3b8;
            margin-top: 8px;
        }

        /* Lab Equipment */
        .lab-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
        }

        .lab-card {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 10px;
            padding: 12px;
        }

        .lab-name {
            font-weight: 600;
            font-size: 0.85em;
            margin-bottom: 5px;
        }

        .lab-model {
            font-size: 0.7em;
            color: #64748b;
            margin-bottom: 8px;
        }

        .lab-stats {
            display: flex;
            justify-content: space-between;
            font-size: 0.75em;
            color: #94a3b8;
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
        <h1>Central Medical Center</h1>
        <div class="subtitle">Healthcare Digital Twin - Real-Time Monitoring</div>
    </div>

    <div class="stats-bar" id="stats-bar">
        <div class="stat-card">
            <div class="stat-value" id="total-beds">-</div>
            <div class="stat-label">Total Beds</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="bed-occupancy">-</div>
            <div class="stat-label">Bed Occupancy</div>
        </div>
        <div class="stat-card">
            <div class="stat-value success" id="available-ors">-</div>
            <div class="stat-label">Available ORs</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="active-monitors">-</div>
            <div class="stat-label">Active Monitors</div>
        </div>
        <div class="stat-card">
            <div class="stat-value warning" id="vents-in-use">-</div>
            <div class="stat-label">Ventilators In Use</div>
        </div>
        <div class="stat-card">
            <div class="stat-value critical" id="critical-alerts">-</div>
            <div class="stat-label">Critical Alerts</div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Department Status</h2>
            <div class="department-grid" id="departments"></div>
        </div>

        <div class="panel">
            <h2>Operating Rooms</h2>
            <div class="or-grid" id="operating-rooms"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>ICU Patient Rooms</h2>
            <div class="icu-grid" id="icu-rooms"></div>
        </div>

        <div class="panel">
            <h2>Ventilators</h2>
            <div class="vent-grid" id="ventilators"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Medical Imaging</h2>
            <div class="equipment-list" id="imaging-equipment"></div>
        </div>

        <div class="panel">
            <h2>Surgical Robots</h2>
            <div class="robot-grid" id="surgical-robots"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Laboratory Equipment</h2>
            <div class="lab-grid" id="lab-equipment"></div>
        </div>

        <div class="panel">
            <h2>Medical Gas Systems</h2>
            <div class="gas-grid" id="medical-gas"></div>
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

            // Stats
            const stats = data.stats || {};
            document.getElementById('total-beds').textContent = stats.totalBeds || 0;
            const occupancy = stats.totalBeds > 0 ? Math.round((stats.occupiedBeds / stats.totalBeds) * 100) : 0;
            document.getElementById('bed-occupancy').textContent = occupancy + '%';
            document.getElementById('bed-occupancy').className = 'stat-value ' + (occupancy > 90 ? 'critical' : occupancy > 75 ? 'warning' : 'success');
            document.getElementById('available-ors').textContent = `${stats.availableORs}/${stats.totalORs}`;
            document.getElementById('active-monitors').textContent = stats.activeMonitors || 0;
            document.getElementById('vents-in-use').textContent = stats.ventilatorInUse || 0;
            document.getElementById('critical-alerts').textContent = stats.criticalAlerts || 0;

            // Departments
            const deptContainer = document.getElementById('departments');
            deptContainer.innerHTML = (data.departments || []).map(dept => {
                const props = dept.properties || {};
                const total = props.totalBeds || 0;
                const occupied = props.occupiedBeds || 0;
                const ratio = total > 0 ? occupied / total : 0;
                const fillClass = ratio > 0.9 ? 'high' : ratio > 0.7 ? 'medium' : 'low';
                const cardClass = ratio > 0.9 ? 'full' : ratio > 0.8 ? 'high-occupancy' : '';

                return `
                    <div class="department-card ${cardClass}">
                        <div class="dept-name">${dept.name}</div>
                        ${total > 0 ? `
                        <div class="dept-beds">
                            <div class="bed-bar">
                                <div class="bed-fill ${fillClass}" style="width: ${ratio * 100}%"></div>
                            </div>
                            <div class="bed-text">${occupied}/${total}</div>
                        </div>
                        ` : '<div class="bed-text" style="font-size: 0.75em; color: #64748b;">No beds</div>'}
                    </div>
                `;
            }).join('');

            // Operating Rooms
            const orContainer = document.getElementById('operating-rooms');
            orContainer.innerHTML = (data.operatingRooms || []).map(or => {
                const props = or.properties || {};
                const status = props.status || 'available';
                return `
                    <div class="or-card ${status === 'in_use' ? 'in-use' : status}">
                        <div class="or-number">${or.id.replace('or-', 'OR ')}</div>
                        <div class="or-type">${props.surgeryType || ''}</div>
                    </div>
                `;
            }).join('');

            // ICU Rooms
            const icuContainer = document.getElementById('icu-rooms');
            icuContainer.innerHTML = (data.icuRooms || []).map(room => {
                const props = room.properties || {};
                const occupied = props.isOccupied;
                const isolation = props.hasNegativePressure;
                const roomNum = room.id.split('-').pop();
                return `
                    <div class="icu-room ${occupied ? 'occupied' : ''} ${isolation ? 'isolation' : ''}"
                         title="${room.name}${isolation ? ' (Isolation)' : ''}">
                        ${roomNum}
                    </div>
                `;
            }).join('');

            // Ventilators
            const ventContainer = document.getElementById('ventilators');
            ventContainer.innerHTML = (data.ventilators || []).map(vent => {
                const props = vent.properties || {};
                const inUse = props.status === 'in_use';
                return `
                    <div class="vent-card ${inUse ? 'in-use' : ''}">
                        <div class="vent-icon">${inUse ? '💨' : '🔌'}</div>
                        <div class="vent-mode">${props.mode || 'Standby'}</div>
                        ${inUse ? `
                        <div class="vent-params">
                            TV: ${props.tidalVolume}mL<br>
                            RR: ${props.respiratoryRate} | PEEP: ${props.peep}
                        </div>
                        ` : ''}
                    </div>
                `;
            }).join('');

            // Imaging Equipment
            const imgContainer = document.getElementById('imaging-equipment');
            imgContainer.innerHTML = (data.imagingEquipment || []).map(equip => {
                const props = equip.properties || {};
                const status = props.status || 'available';
                const statusClass = status.replace('_', '-');
                return `
                    <div class="equipment-item">
                        <div class="equip-info">
                            <div class="equip-name">${equip.name}</div>
                            <div class="equip-model">${props.manufacturer || ''} ${props.model || ''}</div>
                        </div>
                        <span class="equip-status ${statusClass}">${status}</span>
                    </div>
                `;
            }).join('');

            // Surgical Robots
            const robotContainer = document.getElementById('surgical-robots');
            robotContainer.innerHTML = (data.surgicalRobots || []).map(robot => {
                const props = robot.properties || {};
                const icon = robot.type.includes('DaVinci') ? '🤖' :
                            robot.type.includes('MAKO') ? '🦿' : '🧠';
                return `
                    <div class="robot-card">
                        <div class="robot-icon">${icon}</div>
                        <div class="robot-name">${robot.name.split(' ').slice(0, 2).join(' ')}</div>
                        <div class="robot-stats">
                            ${props.proceduresCompleted || 0} procedures<br>
                            ${props.hoursOfOperation || 0} hours
                        </div>
                    </div>
                `;
            }).join('');

            // Lab Equipment
            const labContainer = document.getElementById('lab-equipment');
            labContainer.innerHTML = (data.labEquipment || []).map(equip => {
                const props = equip.properties || {};
                return `
                    <div class="lab-card">
                        <div class="lab-name">${equip.name}</div>
                        <div class="lab-model">${props.manufacturer || ''} ${props.model || ''}</div>
                        <div class="lab-stats">
                            <span>Today: ${props.testsToday || 0}</span>
                            <span>QC: ${props.qcStatus || 'N/A'}</span>
                        </div>
                    </div>
                `;
            }).join('');

            // Medical Gas
            const gasContainer = document.getElementById('medical-gas');
            gasContainer.innerHTML = (data.medicalGas || []).map(gas => {
                const props = gas.properties || {};
                const level = props.tankLevel || 0;
                const fillClass = level > 50 ? 'high' : level > 25 ? 'medium' : 'low';
                const icon = props.gasType === 'O2' ? '💨' :
                            props.gasType === 'N2O' ? '😷' :
                            props.gasType === 'Vacuum' ? '🔽' : '🌬️';
                return `
                    <div class="gas-card">
                        <div class="gas-icon">${icon}</div>
                        <div class="gas-name">${props.gasType || gas.name}</div>
                        <div class="gas-level">
                            <div class="gas-fill ${fillClass}" style="height: ${level}%"></div>
                        </div>
                        <div class="gas-percent">${level}%</div>
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


async def start_websocket_server(port: int, collector: HealthcareDataCollector):
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
    parser = argparse.ArgumentParser(description="Healthcare Digital Twin Web UI")
    parser.add_argument("--port", type=int, default=8088, help="HTTP server port")
    parser.add_argument("--base-url", help="DTaaS server URL")
    args = parser.parse_args()

    client = get_client(args.base_url)
    collector = HealthcareDataCollector(client)

    # Start HTTP server in a thread
    http_thread = threading.Thread(target=run_http_server, args=(args.port,), daemon=True)
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Healthcare Digital Twin - Web UI")
    print(f"  Open http://localhost:{args.port} in your browser")
    print(f"{'='*60}\n")

    # Run WebSocket server
    asyncio.run(start_websocket_server(args.port + 1, collector))


if __name__ == "__main__":
    main()
