#!/usr/bin/env python3
"""
Agriculture / Smart Farm Web UI

Real-time visualization dashboard for precision agriculture operations
including fields, crops, irrigation, drones, and autonomous equipment.

Usage:
    python web_ui.py

Then open http://localhost:8098 in your browser.
"""

import asyncio
import json
import sys
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread

# Add parent directory to path for common imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import websockets
except ImportError:
    print("websockets package required. Install with: pip install websockets")
    sys.exit(1)

from common import get_client

DOMAIN = "agriculture"
HTTP_PORT = 8098
WS_PORT = 8099


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


class AgricultureDataCollector:
    """Collects and processes agriculture data from the digital twin."""

    def __init__(self):
        self.client = get_client()

    def collect_data(self) -> dict:
        """Collect all agriculture data for the dashboard."""
        twins = self.client.twins.list(domain=DOMAIN, page_size=500)

        data = {
            "farm": None,
            "fields": [],
            "crops": [],
            "irrigation_controller": None,
            "irrigation_zones": [],
            "soil_sensors": [],
            "weather_stations": [],
            "drones": [],
            "tractors": [],
            "implements": [],
            "storage_facilities": [],
            "water_sources": [],
            "pest_traps": [],
            "crop_cameras": [],
            "farm_management": None,
            "stats": {
                "total_area": 0,
                "active_irrigation_zones": 0,
                "online_sensors": 0,
                "operational_equipment": 0,
                "avg_crop_health": 0,
                "water_usage_today": 0
            }
        }

        crop_health_scores = []

        for twin in twins:
            twin_type = twin.type_uri.split('#')[-1] if '#' in twin.type_uri else twin.type_uri.split('/')[-1]
            props = _normalize_properties(twin.properties or {})

            if twin_type == "Farm":
                data["farm"] = {
                    "id": twin.id,
                    "name": twin.name,
                    "total_area": props.get("totalArea", 0),
                    "cultivated_area": props.get("cultivatedArea", 0),
                    "climate": props.get("climate", "Unknown"),
                    "soil_type": props.get("soilType", "Unknown"),
                    "certifications": props.get("certifications", []),
                    "employees": props.get("employees", 0)
                }
                data["stats"]["total_area"] = props.get("totalArea", 0)

            elif twin_type == "AgriculturalField":
                data["fields"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "area": props.get("area", 0),
                    "current_crop": props.get("currentCrop", "Unknown"),
                    "irrigation_type": props.get("irrigationType", "Unknown"),
                    "soil_moisture": props.get("soilMoisture", 0),
                    "soil_ph": props.get("soilPH", 0),
                    "yield_estimate": props.get("yieldEstimate", 0),
                    "status": props.get("status", "Unknown"),
                    "expected_harvest": props.get("expectedHarvest", "")
                })

            elif twin_type == "Crop":
                health_score = props.get("healthScore", 0)
                crop_health_scores.append(health_score)
                data["crops"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "crop_type": props.get("cropType", "Unknown"),
                    "growth_cycle_days": props.get("growthCycleDays", 0),
                    "water_requirement": props.get("waterRequirement", "medium"),
                    "growth_stage": props.get("currentGrowthStage", "Unknown"),
                    "health_score": health_score
                })

            elif twin_type == "IrrigationController":
                data["irrigation_controller"] = {
                    "id": twin.id,
                    "name": twin.name,
                    "zones": props.get("zones", 0),
                    "active_zones": props.get("activeZones", 0),
                    "total_capacity": props.get("totalCapacity", 0),
                    "status": props.get("status", "Unknown")
                }

            elif twin_type == "IrrigationZone":
                status = props.get("currentStatus", "idle")
                if status == "irrigating":
                    data["stats"]["active_irrigation_zones"] += 1
                data["irrigation_zones"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "irrigation_type": props.get("irrigationType", "Unknown"),
                    "flow_rate": props.get("flowRate", 0),
                    "current_status": status,
                    "area": props.get("area", 0)
                })

            elif twin_type == "SoilSensor":
                status = props.get("status", "offline")
                if status == "online":
                    data["stats"]["online_sensors"] += 1
                data["soil_sensors"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "depth": props.get("depth", 0),
                    "moisture": props.get("moisture", 0),
                    "temperature": props.get("temperature", 0),
                    "ec": props.get("electricalConductivity", 0),
                    "battery": props.get("batteryLevel", 0),
                    "status": status
                })

            elif twin_type == "WeatherStation":
                data["weather_stations"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "temperature": props.get("temperature", 0),
                    "humidity": props.get("humidity", 0),
                    "wind_speed": props.get("windSpeed", 0),
                    "solar_radiation": props.get("solarRadiation", 0),
                    "rainfall": props.get("rainfall", 0),
                    "evapotranspiration": props.get("evapotranspiration", 0),
                    "status": props.get("status", "offline")
                })

            elif twin_type == "AgriculturalDrone":
                status = props.get("status", "offline")
                if status in ["idle", "flying", "charging"]:
                    data["stats"]["operational_equipment"] += 1
                data["drones"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "drone_type": props.get("droneType", "Unknown"),
                    "payload_type": props.get("payloadType", "Unknown"),
                    "battery": props.get("batteryLevel", 0),
                    "flight_time": props.get("flightTime", 0),
                    "status": status,
                    "total_hours": props.get("totalFlightHours", 0)
                })

            elif twin_type == "AgriculturalTractor":
                status = props.get("status", "offline")
                if status in ["idle", "working", "moving"]:
                    data["stats"]["operational_equipment"] += 1
                data["tractors"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "autonomy_level": props.get("autonomyLevel", "manual"),
                    "horsepower": props.get("horsepower", 0),
                    "fuel_level": props.get("fuelLevel", 0),
                    "hours_of_operation": props.get("hoursOfOperation", 0),
                    "status": status,
                    "attached_implement": props.get("attachedImplement")
                })

            elif twin_type == "AgriculturalImplement":
                data["implements"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "implement_type": props.get("implementType", "Unknown"),
                    "working_width": props.get("workingWidth", 0),
                    "status": props.get("status", "Unknown"),
                    "hours_of_use": props.get("hoursOfUse", 0)
                })

            elif twin_type == "StorageFacility":
                data["storage_facilities"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "storage_type": props.get("storageType", "Unknown"),
                    "capacity": props.get("capacity", 0),
                    "current_level": props.get("currentLevel", 0),
                    "capacity_unit": props.get("capacityUnit", ""),
                    "temperature": props.get("temperature", 0),
                    "status": props.get("status", "Unknown")
                })

            elif twin_type == "WaterSource":
                data["water_sources"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "source_type": props.get("sourceType", "Unknown"),
                    "flow_rate": props.get("flowRate", props.get("allocation", 0)),
                    "water_quality": props.get("waterQualityIndex", 0),
                    "status": props.get("status", "Unknown")
                })

            elif twin_type == "PestTrap":
                data["pest_traps"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "target_pest": props.get("targetPest", "Unknown"),
                    "catch_count": props.get("catchCount", 0),
                    "threshold": props.get("thresholdLevel", 0),
                    "alert_level": props.get("alertLevel", "low"),
                    "status": props.get("status", "inactive")
                })

            elif twin_type == "CropHealthCamera":
                data["crop_cameras"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "ndvi_value": props.get("ndviValue", 0),
                    "crop_stress_index": props.get("cropStressIndex", 0),
                    "coverage_area": props.get("coverageArea", 0),
                    "status": props.get("status", "offline")
                })

            elif twin_type == "FarmManagementSystem":
                data["farm_management"] = {
                    "id": twin.id,
                    "name": twin.name,
                    "connected_sensors": props.get("connectedSensors", 0),
                    "connected_equipment": props.get("connectedEquipment", 0),
                    "active_alerts": props.get("activeAlerts", 0),
                    "water_usage_today": props.get("waterUsageToday", 0),
                    "status": props.get("status", "Unknown")
                }
                data["stats"]["water_usage_today"] = props.get("waterUsageToday", 0)

        # Calculate average crop health
        if crop_health_scores:
            data["stats"]["avg_crop_health"] = sum(crop_health_scores) / len(crop_health_scores)

        return data


# HTML Dashboard
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart Farm Dashboard - TesserAI</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a472a 0%, #2d5016 50%, #1a3a1a 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 20px;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 15px;
            border: 1px solid rgba(76, 175, 80, 0.3);
        }

        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, #81c784, #4caf50, #66bb6a);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }

        .header .subtitle {
            color: #a5d6a7;
            font-size: 1.1em;
        }

        .dashboard {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            max-width: 1800px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(0, 0, 0, 0.4);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(76, 175, 80, 0.2);
        }

        .panel-title {
            font-size: 1.1em;
            color: #81c784;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(76, 175, 80, 0.2);
        }

        .panel-icon {
            font-size: 1.3em;
        }

        /* Farm Overview */
        .farm-overview {
            grid-column: span 2;
        }

        .farm-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
        }

        .stat-card {
            background: rgba(76, 175, 80, 0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }

        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #4caf50;
        }

        .stat-label {
            font-size: 0.85em;
            color: #a5d6a7;
            margin-top: 5px;
        }

        /* Field Grid */
        .field-grid {
            grid-column: span 2;
        }

        .fields-container {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }

        .field-card {
            background: linear-gradient(135deg, rgba(46, 125, 50, 0.3), rgba(27, 94, 32, 0.3));
            padding: 12px;
            border-radius: 10px;
            border: 1px solid rgba(76, 175, 80, 0.3);
        }

        .field-name {
            font-weight: bold;
            font-size: 0.9em;
            margin-bottom: 8px;
        }

        .field-crop {
            display: inline-block;
            background: rgba(139, 195, 74, 0.3);
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.75em;
            margin-bottom: 8px;
        }

        .moisture-bar {
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            overflow: hidden;
            margin-top: 8px;
        }

        .moisture-fill {
            height: 100%;
            background: linear-gradient(90deg, #4caf50, #8bc34a);
            transition: width 0.5s ease;
        }

        .moisture-low .moisture-fill {
            background: linear-gradient(90deg, #ff9800, #f57c00);
        }

        .field-stats {
            display: flex;
            justify-content: space-between;
            font-size: 0.75em;
            color: #a5d6a7;
            margin-top: 5px;
        }

        /* Weather Panel */
        .weather-panel {
            grid-column: span 2;
        }

        .weather-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
        }

        .weather-station {
            background: rgba(33, 150, 243, 0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }

        .weather-temp {
            font-size: 2em;
            font-weight: bold;
            color: #64b5f6;
        }

        .weather-conditions {
            display: flex;
            justify-content: space-around;
            margin-top: 10px;
            font-size: 0.85em;
        }

        .weather-item {
            text-align: center;
        }

        .weather-icon {
            font-size: 1.2em;
            margin-bottom: 3px;
        }

        /* Equipment Panel */
        .equipment-panel {
            grid-column: span 2;
        }

        .equipment-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }

        .equipment-section {
            background: rgba(255, 193, 7, 0.1);
            padding: 15px;
            border-radius: 10px;
        }

        .equipment-section h4 {
            color: #ffd54f;
            margin-bottom: 10px;
            font-size: 0.95em;
        }

        .equipment-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
            margin-bottom: 8px;
        }

        .equipment-name {
            font-size: 0.85em;
        }

        .equipment-status {
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 0.75em;
        }

        .status-idle { background: rgba(76, 175, 80, 0.3); color: #81c784; }
        .status-working { background: rgba(33, 150, 243, 0.3); color: #64b5f6; }
        .status-flying { background: rgba(156, 39, 176, 0.3); color: #ce93d8; }
        .status-charging { background: rgba(255, 193, 7, 0.3); color: #ffd54f; }
        .status-offline { background: rgba(244, 67, 54, 0.3); color: #ef5350; }

        .battery-indicator {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.8em;
        }

        .battery-bar {
            width: 30px;
            height: 12px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
            overflow: hidden;
        }

        .battery-fill {
            height: 100%;
            transition: width 0.5s;
        }

        .battery-high { background: #4caf50; }
        .battery-medium { background: #ff9800; }
        .battery-low { background: #f44336; }

        /* Irrigation Panel */
        .irrigation-panel {
            grid-column: span 2;
        }

        .irrigation-status {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: rgba(0, 150, 136, 0.2);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }

        .irrigation-main {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .irrigation-icon {
            font-size: 2.5em;
            color: #4dd0e1;
        }

        .irrigation-info h4 {
            color: #4dd0e1;
            margin-bottom: 5px;
        }

        .zone-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
        }

        .zone-item {
            padding: 8px;
            border-radius: 8px;
            font-size: 0.8em;
            text-align: center;
        }

        .zone-active {
            background: rgba(0, 188, 212, 0.3);
            border: 1px solid #00bcd4;
            animation: pulse 2s infinite;
        }

        .zone-idle {
            background: rgba(158, 158, 158, 0.2);
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }

        /* Storage Panel */
        .storage-panel {
            grid-column: span 2;
        }

        .storage-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }

        .storage-item {
            background: rgba(121, 85, 72, 0.2);
            padding: 15px;
            border-radius: 10px;
        }

        .storage-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }

        .storage-name {
            font-weight: bold;
            color: #bcaaa4;
        }

        .storage-type {
            font-size: 0.8em;
            padding: 2px 8px;
            background: rgba(121, 85, 72, 0.3);
            border-radius: 10px;
        }

        .storage-bar {
            height: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            overflow: hidden;
            position: relative;
        }

        .storage-fill {
            height: 100%;
            background: linear-gradient(90deg, #8d6e63, #a1887f);
            transition: width 0.5s;
        }

        .storage-percent {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 0.8em;
            font-weight: bold;
        }

        /* Crop Health Panel */
        .health-panel {
            grid-column: span 2;
        }

        .health-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
        }

        .crop-health-card {
            background: rgba(76, 175, 80, 0.1);
            padding: 12px;
            border-radius: 10px;
            text-align: center;
        }

        .crop-name {
            font-size: 0.9em;
            margin-bottom: 8px;
            color: #a5d6a7;
        }

        .health-ring {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 8px;
            font-weight: bold;
            font-size: 1.1em;
        }

        .health-excellent { background: conic-gradient(#4caf50 calc(var(--percent) * 1%), rgba(76, 175, 80, 0.2) 0); }
        .health-good { background: conic-gradient(#8bc34a calc(var(--percent) * 1%), rgba(139, 195, 74, 0.2) 0); }
        .health-moderate { background: conic-gradient(#ff9800 calc(var(--percent) * 1%), rgba(255, 152, 0, 0.2) 0); }
        .health-poor { background: conic-gradient(#f44336 calc(var(--percent) * 1%), rgba(244, 67, 54, 0.2) 0); }

        .health-inner {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: rgba(0, 0, 0, 0.6);
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .growth-stage {
            font-size: 0.75em;
            color: #81c784;
        }

        /* Pest Monitoring */
        .pest-panel {
            grid-column: span 2;
        }

        .pest-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 10px;
        }

        .pest-trap {
            background: rgba(156, 39, 176, 0.1);
            padding: 12px;
            border-radius: 10px;
            text-align: center;
        }

        .pest-target {
            font-size: 0.85em;
            color: #ce93d8;
            margin-bottom: 8px;
        }

        .pest-count {
            font-size: 1.5em;
            font-weight: bold;
        }

        .pest-threshold {
            font-size: 0.75em;
            color: #9e9e9e;
            margin-top: 5px;
        }

        .alert-low { color: #4caf50; }
        .alert-medium { color: #ff9800; }
        .alert-high { color: #f44336; animation: blink 1s infinite; }

        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* Water Sources */
        .water-panel {
            grid-column: span 2;
        }

        .water-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
        }

        .water-source {
            background: rgba(33, 150, 243, 0.1);
            padding: 12px;
            border-radius: 10px;
            text-align: center;
        }

        .water-icon {
            font-size: 1.5em;
            margin-bottom: 8px;
        }

        .water-name {
            font-size: 0.85em;
            margin-bottom: 5px;
        }

        .water-flow {
            font-size: 1.2em;
            font-weight: bold;
            color: #64b5f6;
        }

        .water-quality {
            font-size: 0.75em;
            margin-top: 5px;
        }

        .quality-good { color: #4caf50; }
        .quality-fair { color: #ff9800; }
        .quality-poor { color: #f44336; }

        /* Connection status */
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.85em;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .status-connected {
            background: rgba(76, 175, 80, 0.3);
            border: 1px solid #4caf50;
        }

        .status-disconnected {
            background: rgba(244, 67, 54, 0.3);
            border: 1px solid #f44336;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .status-connected .status-dot {
            background: #4caf50;
            animation: pulse-dot 2s infinite;
        }

        .status-disconnected .status-dot {
            background: #f44336;
        }

        @keyframes pulse-dot {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.2); opacity: 0.7; }
        }

        @media (max-width: 1400px) {
            .dashboard {
                grid-template-columns: repeat(2, 1fr);
            }
            .farm-overview, .field-grid, .weather-panel, .equipment-panel,
            .irrigation-panel, .storage-panel, .health-panel, .pest-panel, .water-panel {
                grid-column: span 2;
            }
        }
    </style>
</head>
<body>
    <div id="connection-status" class="connection-status status-disconnected">
        <span class="status-dot"></span>
        <span id="status-text">Connecting...</span>
    </div>

    <div class="header">
        <h1>Smart Farm Dashboard</h1>
        <div class="subtitle">Precision Agriculture Digital Twin - Real-time Monitoring</div>
    </div>

    <div class="dashboard">
        <!-- Farm Overview -->
        <div class="panel farm-overview">
            <div class="panel-title">
                <span class="panel-icon">&#127793;</span>
                Farm Overview
            </div>
            <div id="farm-stats" class="farm-stats">
                <div class="stat-card">
                    <div class="stat-value" id="total-area">--</div>
                    <div class="stat-label">Total Acres</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="avg-health">--</div>
                    <div class="stat-label">Avg Crop Health</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="online-sensors">--</div>
                    <div class="stat-label">Online Sensors</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="active-zones">--</div>
                    <div class="stat-label">Active Irrigation</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="operational-equip">--</div>
                    <div class="stat-label">Equipment Ready</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="water-usage">--</div>
                    <div class="stat-label">Water Today (gal)</div>
                </div>
            </div>
        </div>

        <!-- Field Grid -->
        <div class="panel field-grid">
            <div class="panel-title">
                <span class="panel-icon">&#127806;</span>
                Field Status
            </div>
            <div id="fields-container" class="fields-container">
                <!-- Fields populated by JS -->
            </div>
        </div>

        <!-- Weather Stations -->
        <div class="panel weather-panel">
            <div class="panel-title">
                <span class="panel-icon">&#9728;</span>
                Weather Conditions
            </div>
            <div id="weather-grid" class="weather-grid">
                <!-- Weather stations populated by JS -->
            </div>
        </div>

        <!-- Crop Health -->
        <div class="panel health-panel">
            <div class="panel-title">
                <span class="panel-icon">&#127807;</span>
                Crop Health Monitor
            </div>
            <div id="health-grid" class="health-grid">
                <!-- Crop health populated by JS -->
            </div>
        </div>

        <!-- Equipment Status -->
        <div class="panel equipment-panel">
            <div class="panel-title">
                <span class="panel-icon">&#128737;</span>
                Equipment Fleet
            </div>
            <div id="equipment-grid" class="equipment-grid">
                <!-- Equipment populated by JS -->
            </div>
        </div>

        <!-- Irrigation System -->
        <div class="panel irrigation-panel">
            <div class="panel-title">
                <span class="panel-icon">&#128167;</span>
                Irrigation System
            </div>
            <div id="irrigation-container">
                <!-- Irrigation populated by JS -->
            </div>
        </div>

        <!-- Storage Facilities -->
        <div class="panel storage-panel">
            <div class="panel-title">
                <span class="panel-icon">&#127751;</span>
                Storage Facilities
            </div>
            <div id="storage-grid" class="storage-grid">
                <!-- Storage populated by JS -->
            </div>
        </div>

        <!-- Water Sources -->
        <div class="panel water-panel">
            <div class="panel-title">
                <span class="panel-icon">&#128166;</span>
                Water Sources
            </div>
            <div id="water-grid" class="water-grid">
                <!-- Water sources populated by JS -->
            </div>
        </div>

        <!-- Pest Monitoring -->
        <div class="panel pest-panel">
            <div class="panel-title">
                <span class="panel-icon">&#128028;</span>
                Pest Monitoring
            </div>
            <div id="pest-grid" class="pest-grid">
                <!-- Pest traps populated by JS -->
            </div>
        </div>
    </div>

    <script>
        let ws;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 10;

        function connect() {
            ws = new WebSocket('ws://localhost:WS_PORT_PLACEHOLDER');

            ws.onopen = () => {
                console.log('Connected to agriculture data stream');
                document.getElementById('connection-status').className = 'connection-status status-connected';
                document.getElementById('status-text').textContent = 'Live';
                reconnectAttempts = 0;
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };

            ws.onclose = () => {
                document.getElementById('connection-status').className = 'connection-status status-disconnected';
                document.getElementById('status-text').textContent = 'Reconnecting...';

                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    setTimeout(connect, 2000);
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }

        function updateDashboard(data) {
            // Update stats
            document.getElementById('total-area').textContent =
                data.stats.total_area.toLocaleString();
            document.getElementById('avg-health').textContent =
                data.stats.avg_crop_health.toFixed(0) + '%';
            document.getElementById('online-sensors').textContent =
                data.stats.online_sensors;
            document.getElementById('active-zones').textContent =
                data.stats.active_irrigation_zones;
            document.getElementById('operational-equip').textContent =
                data.stats.operational_equipment;
            document.getElementById('water-usage').textContent =
                (data.stats.water_usage_today / 1000).toFixed(0) + 'K';

            // Update fields
            updateFields(data.fields);

            // Update weather
            updateWeather(data.weather_stations);

            // Update crop health
            updateCropHealth(data.crops);

            // Update equipment
            updateEquipment(data.drones, data.tractors);

            // Update irrigation
            updateIrrigation(data.irrigation_controller, data.irrigation_zones);

            // Update storage
            updateStorage(data.storage_facilities);

            // Update water sources
            updateWaterSources(data.water_sources);

            // Update pest monitoring
            updatePestTraps(data.pest_traps);
        }

        function updateFields(fields) {
            const container = document.getElementById('fields-container');
            container.innerHTML = fields.map(field => {
                const moistureClass = field.soil_moisture < 30 ? 'moisture-low' : '';
                return `
                    <div class="field-card">
                        <div class="field-name">${field.name}</div>
                        <span class="field-crop">${field.current_crop}</span>
                        <div class="moisture-bar ${moistureClass}">
                            <div class="moisture-fill" style="width: ${field.soil_moisture}%"></div>
                        </div>
                        <div class="field-stats">
                            <span>Moisture: ${field.soil_moisture}%</span>
                            <span>pH: ${field.soil_ph.toFixed(1)}</span>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateWeather(stations) {
            const container = document.getElementById('weather-grid');
            container.innerHTML = stations.map(station => `
                <div class="weather-station">
                    <div class="weather-temp">${station.temperature.toFixed(1)}°C</div>
                    <div style="color: #90caf9; font-size: 0.9em">${station.name.replace('Weather Station', '').trim()}</div>
                    <div class="weather-conditions">
                        <div class="weather-item">
                            <div class="weather-icon">&#128167;</div>
                            <div>${station.humidity}%</div>
                        </div>
                        <div class="weather-item">
                            <div class="weather-icon">&#127788;</div>
                            <div>${station.wind_speed} km/h</div>
                        </div>
                        <div class="weather-item">
                            <div class="weather-icon">&#9728;</div>
                            <div>${station.solar_radiation} W/m²</div>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        function updateCropHealth(crops) {
            const container = document.getElementById('health-grid');
            container.innerHTML = crops.map(crop => {
                const health = crop.health_score;
                let healthClass = 'health-excellent';
                if (health < 70) healthClass = 'health-poor';
                else if (health < 80) healthClass = 'health-moderate';
                else if (health < 90) healthClass = 'health-good';

                return `
                    <div class="crop-health-card">
                        <div class="crop-name">${crop.name}</div>
                        <div class="health-ring ${healthClass}" style="--percent: ${health}">
                            <div class="health-inner">${health}%</div>
                        </div>
                        <div class="growth-stage">${crop.growth_stage}</div>
                    </div>
                `;
            }).join('');
        }

        function updateEquipment(drones, tractors) {
            const container = document.getElementById('equipment-grid');

            const droneHtml = `
                <div class="equipment-section">
                    <h4>&#128681; Drone Fleet</h4>
                    ${drones.map(drone => {
                        const batteryClass = drone.battery > 50 ? 'battery-high' :
                                           drone.battery > 20 ? 'battery-medium' : 'battery-low';
                        return `
                            <div class="equipment-item">
                                <div>
                                    <div class="equipment-name">${drone.name}</div>
                                    <div style="font-size: 0.75em; color: #9e9e9e">${drone.payload_type}</div>
                                </div>
                                <div style="display: flex; align-items: center; gap: 10px">
                                    <div class="battery-indicator">
                                        <div class="battery-bar">
                                            <div class="battery-fill ${batteryClass}" style="width: ${drone.battery}%"></div>
                                        </div>
                                        ${drone.battery}%
                                    </div>
                                    <span class="equipment-status status-${drone.status}">${drone.status}</span>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;

            const tractorHtml = `
                <div class="equipment-section">
                    <h4>&#128663; Tractor Fleet</h4>
                    ${tractors.map(tractor => {
                        const fuelClass = tractor.fuel_level > 50 ? 'battery-high' :
                                        tractor.fuel_level > 20 ? 'battery-medium' : 'battery-low';
                        return `
                            <div class="equipment-item">
                                <div>
                                    <div class="equipment-name">${tractor.name}</div>
                                    <div style="font-size: 0.75em; color: #9e9e9e">${tractor.autonomy_level} - ${tractor.horsepower}HP</div>
                                </div>
                                <div style="display: flex; align-items: center; gap: 10px">
                                    <div class="battery-indicator">
                                        <div class="battery-bar">
                                            <div class="battery-fill ${fuelClass}" style="width: ${tractor.fuel_level}%"></div>
                                        </div>
                                        ${tractor.fuel_level}%
                                    </div>
                                    <span class="equipment-status status-${tractor.status}">${tractor.status}</span>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;

            container.innerHTML = droneHtml + tractorHtml;
        }

        function updateIrrigation(controller, zones) {
            const container = document.getElementById('irrigation-container');

            const controllerHtml = controller ? `
                <div class="irrigation-status">
                    <div class="irrigation-main">
                        <span class="irrigation-icon">&#128167;</span>
                        <div class="irrigation-info">
                            <h4>${controller.name}</h4>
                            <div>Zones: ${controller.active_zones}/${controller.zones} active</div>
                        </div>
                    </div>
                    <div>
                        <span class="equipment-status status-${controller.status === 'irrigating' ? 'working' : 'idle'}">
                            ${controller.status}
                        </span>
                    </div>
                </div>
            ` : '';

            const zonesHtml = `
                <div class="zone-grid">
                    ${zones.slice(0, 9).map(zone => `
                        <div class="zone-item ${zone.current_status === 'irrigating' ? 'zone-active' : 'zone-idle'}">
                            <div style="font-size: 0.85em">${zone.name.replace('Irrigation Zone - ', '')}</div>
                            <div style="font-size: 0.75em; color: #80deea">${zone.flow_rate} gpm</div>
                        </div>
                    `).join('')}
                </div>
            `;

            container.innerHTML = controllerHtml + zonesHtml;
        }

        function updateStorage(facilities) {
            const container = document.getElementById('storage-grid');
            container.innerHTML = facilities.map(facility => {
                const percent = facility.capacity > 0 ?
                    (facility.current_level / facility.capacity * 100).toFixed(0) : 0;
                return `
                    <div class="storage-item">
                        <div class="storage-header">
                            <span class="storage-name">${facility.name}</span>
                            <span class="storage-type">${facility.storage_type}</span>
                        </div>
                        <div class="storage-bar">
                            <div class="storage-fill" style="width: ${percent}%"></div>
                            <span class="storage-percent">${percent}%</span>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateWaterSources(sources) {
            const container = document.getElementById('water-grid');
            const icons = {
                'well': '&#128704;',
                'canal': '&#127754;',
                'pond': '&#128166;'
            };

            container.innerHTML = sources.map(source => {
                const qualityClass = source.water_quality > 90 ? 'quality-good' :
                                   source.water_quality > 70 ? 'quality-fair' : 'quality-poor';
                return `
                    <div class="water-source">
                        <div class="water-icon">${icons[source.source_type] || '&#128167;'}</div>
                        <div class="water-name">${source.name}</div>
                        <div class="water-flow">${source.flow_rate.toLocaleString()}</div>
                        <div style="font-size: 0.75em; color: #90caf9">gal/min</div>
                        <div class="water-quality ${qualityClass}">Quality: ${source.water_quality}%</div>
                    </div>
                `;
            }).join('');
        }

        function updatePestTraps(traps) {
            const container = document.getElementById('pest-grid');
            container.innerHTML = traps.map(trap => {
                const alertClass = trap.alert_level === 'high' ? 'alert-high' :
                                 trap.alert_level === 'medium' ? 'alert-medium' : 'alert-low';
                return `
                    <div class="pest-trap">
                        <div class="pest-target">${trap.target_pest.replace('_', ' ')}</div>
                        <div class="pest-count ${alertClass}">${trap.catch_count}</div>
                        <div class="pest-threshold">Threshold: ${trap.threshold}</div>
                    </div>
                `;
            }).join('');
        }

        // Start connection
        connect();
    </script>
</body>
</html>
""".replace('WS_PORT_PLACEHOLDER', str(WS_PORT))


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for serving the dashboard."""

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


async def broadcast_data(websocket, collector: AgricultureDataCollector):
    """Broadcast agriculture data to connected clients."""
    try:
        while True:
            data = collector.collect_data()
            await websocket.send(json.dumps(data))
            await asyncio.sleep(5)
    except websockets.exceptions.ConnectionClosed:
        pass


async def ws_handler(websocket, collector: AgricultureDataCollector):
    """Handle WebSocket connections."""
    await broadcast_data(websocket, collector)


def run_http_server():
    """Run the HTTP server for the dashboard."""
    server = HTTPServer(('0.0.0.0', HTTP_PORT), DashboardHandler)
    server.serve_forever()


async def main():
    """Main entry point."""
    print(f"\n{'='*60}")
    print("  Smart Farm Dashboard - TesserAI Digital Twin")
    print(f"{'='*60}")
    print(f"\n  Dashboard: http://localhost:{HTTP_PORT}")
    print(f"  WebSocket: ws://localhost:{WS_PORT}")
    print(f"\n  Press Ctrl+C to stop\n")

    collector = AgricultureDataCollector()

    # Start HTTP server in background thread
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()

    # Start WebSocket server
    async with websockets.serve(
        lambda ws: ws_handler(ws, collector),
        "0.0.0.0",
        WS_PORT
    ):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
