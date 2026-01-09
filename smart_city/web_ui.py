#!/usr/bin/env python3
"""
Smart City Digital Twin - Web UI
=================================

Real-time city monitoring dashboard showing:
- District overview and population
- Traffic status and intersections
- Public transit (metro, buses)
- Power grid and utilities
- Environmental monitoring (air quality, weather)
- Public safety (police, fire stations)
- Parking availability

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
DOMAIN = "smart_city"


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


class SmartCityDataCollector:
    """Collects data from the smart city digital twin."""

    def __init__(self, client):
        self.client = client

    def collect_data(self) -> dict:
        """Collect all smart city data."""
        try:
            twins = self.client.twins.list(domain=DOMAIN, page_size=300)

            data = {
                "timestamp": datetime.now().isoformat(),
                "city": None,
                "districts": [],
                "roads": [],
                "intersections": [],
                "trafficSensors": [],
                "trafficSignals": [],
                "metroLines": [],
                "metroStations": [],
                "busRoutes": [],
                "buses": [],
                "powerGrid": None,
                "substations": [],
                "waterSystem": None,
                "waterTanks": [],
                "airStations": [],
                "noiseSensors": [],
                "weather": None,
                "policeStations": [],
                "fireStations": [],
                "cameras": [],
                "parkingFacilities": [],
                "streetlights": [],
                "stats": {
                    "population": 0,
                    "districts": 0,
                    "busesActive": 0,
                    "parkingAvailable": 0,
                    "parkingTotal": 0,
                    "powerLoad": 0,
                    "powerCapacity": 0,
                    "airQuality": 0
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

                if twin_type == "City":
                    data["city"] = item
                    data["stats"]["population"] = props.get("population", 0)
                elif twin_type == "District":
                    data["districts"].append(item)
                    data["stats"]["districts"] += 1
                elif twin_type == "Road":
                    data["roads"].append(item)
                elif twin_type == "TrafficIntersection":
                    data["intersections"].append(item)
                elif twin_type == "TrafficSensor":
                    data["trafficSensors"].append(item)
                elif twin_type == "TrafficSignal":
                    data["trafficSignals"].append(item)
                elif twin_type == "MetroLine":
                    data["metroLines"].append(item)
                elif twin_type == "MetroStation":
                    data["metroStations"].append(item)
                elif twin_type == "BusRoute":
                    data["busRoutes"].append(item)
                elif twin_type == "Bus":
                    data["buses"].append(item)
                    if props.get("status") == "in_service":
                        data["stats"]["busesActive"] += 1
                elif twin_type == "PowerGrid":
                    data["powerGrid"] = item
                    data["stats"]["powerLoad"] = props.get("currentLoad", 0)
                    data["stats"]["powerCapacity"] = props.get("totalCapacity", 0)
                elif twin_type == "ElectricalSubstation":
                    data["substations"].append(item)
                elif twin_type == "WaterSystem":
                    data["waterSystem"] = item
                elif twin_type == "WaterTank":
                    data["waterTanks"].append(item)
                elif twin_type == "AirQualityStation":
                    data["airStations"].append(item)
                    if data["stats"]["airQuality"] == 0:
                        data["stats"]["airQuality"] = props.get("aqi", 0)
                elif twin_type == "NoiseSensor":
                    data["noiseSensors"].append(item)
                elif twin_type == "WeatherStation":
                    data["weather"] = item
                elif twin_type == "PoliceStation":
                    data["policeStations"].append(item)
                elif twin_type == "FireStation":
                    data["fireStations"].append(item)
                elif twin_type == "SurveillanceCamera":
                    data["cameras"].append(item)
                elif twin_type == "ParkingFacility":
                    data["parkingFacilities"].append(item)
                    data["stats"]["parkingAvailable"] += props.get("availableSpaces", 0)
                    data["stats"]["parkingTotal"] += props.get("totalSpaces", 0)
                elif twin_type == "SmartStreetlight":
                    data["streetlights"].append(item)

            return data

        except Exception as e:
            logger.error(f"Failed to collect data: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart City Digital Twin - Metropolis</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0c1929 100%);
            min-height: 100vh;
            color: #e2e8f0;
            padding: 20px;
        }

        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 20px;
            background: linear-gradient(135deg, rgba(14, 165, 233, 0.2), rgba(139, 92, 246, 0.2));
            border-radius: 16px;
            border: 1px solid rgba(14, 165, 233, 0.3);
        }

        .header h1 {
            font-size: 2em;
            color: #38bdf8;
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
            background: linear-gradient(135deg, rgba(30, 58, 95, 0.9), rgba(15, 35, 60, 0.9));
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            border: 1px solid rgba(14, 165, 233, 0.2);
        }

        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #38bdf8;
        }

        .stat-value.good { color: #34d399; }
        .stat-value.warning { color: #fbbf24; }
        .stat-value.critical { color: #ef4444; }

        .stat-label {
            color: #94a3b8;
            font-size: 0.8em;
            margin-top: 5px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .panel {
            background: linear-gradient(135deg, rgba(30, 58, 95, 0.8), rgba(15, 35, 60, 0.8));
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(14, 165, 233, 0.15);
        }

        .panel h2 {
            color: #38bdf8;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.1em;
        }

        /* Districts */
        .district-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 10px;
        }

        .district-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
            text-align: center;
            border-left: 4px solid #3b82f6;
        }

        .district-card.commercial { border-left-color: #8b5cf6; }
        .district-card.residential { border-left-color: #22c55e; }
        .district-card.industrial { border-left-color: #f59e0b; }
        .district-card.educational { border-left-color: #06b6d4; }

        .district-name {
            font-weight: 600;
            font-size: 0.85em;
            margin-bottom: 5px;
        }

        .district-pop {
            font-size: 0.75em;
            color: #94a3b8;
        }

        /* Metro Lines */
        .metro-grid {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .metro-line {
            display: flex;
            align-items: center;
            gap: 15px;
            background: rgba(15, 23, 42, 0.5);
            border-radius: 10px;
            padding: 12px;
        }

        .metro-indicator {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: white;
        }

        .metro-info {
            flex: 1;
        }

        .metro-name {
            font-weight: 600;
            font-size: 0.9em;
        }

        .metro-stats {
            font-size: 0.75em;
            color: #94a3b8;
        }

        /* Bus Fleet */
        .bus-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
            gap: 8px;
        }

        .bus-card {
            background: rgba(34, 197, 94, 0.2);
            border: 1px solid rgba(34, 197, 94, 0.3);
            border-radius: 8px;
            padding: 8px;
            text-align: center;
            font-size: 0.8em;
        }

        .bus-card.charging {
            background: rgba(234, 179, 8, 0.2);
            border-color: rgba(234, 179, 8, 0.3);
        }

        .bus-icon {
            font-size: 1.2em;
        }

        .bus-id {
            font-weight: 600;
            margin-top: 4px;
        }

        .bus-battery {
            font-size: 0.7em;
            color: #94a3b8;
        }

        /* Traffic */
        .traffic-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
        }

        .traffic-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
        }

        .traffic-name {
            font-weight: 500;
            font-size: 0.85em;
            margin-bottom: 8px;
        }

        .traffic-bar {
            height: 6px;
            background: rgba(51, 65, 85, 0.5);
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 5px;
        }

        .traffic-fill {
            height: 100%;
            border-radius: 3px;
        }

        .traffic-fill.light { background: #22c55e; }
        .traffic-fill.moderate { background: #eab308; }
        .traffic-fill.heavy { background: #ef4444; }

        .traffic-stats {
            display: flex;
            justify-content: space-between;
            font-size: 0.7em;
            color: #94a3b8;
        }

        /* Power Grid */
        .power-overview {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 15px;
        }

        .power-gauge {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: conic-gradient(
                #22c55e 0deg,
                #22c55e calc(var(--load) * 3.6deg),
                rgba(51, 65, 85, 0.5) calc(var(--load) * 3.6deg)
            );
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }

        .power-gauge::before {
            content: '';
            position: absolute;
            width: 70px;
            height: 70px;
            background: #1e3a5f;
            border-radius: 50%;
        }

        .power-value {
            position: relative;
            z-index: 1;
            font-size: 1.2em;
            font-weight: bold;
        }

        .power-details {
            flex: 1;
        }

        .power-stat {
            margin-bottom: 8px;
            font-size: 0.85em;
        }

        .substation-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 10px;
        }

        .substation-card {
            background: rgba(15, 23, 42, 0.5);
            border-radius: 8px;
            padding: 10px;
        }

        .substation-name {
            font-size: 0.8em;
            font-weight: 500;
            margin-bottom: 5px;
        }

        .substation-load {
            height: 4px;
            background: rgba(51, 65, 85, 0.5);
            border-radius: 2px;
            overflow: hidden;
        }

        .substation-fill {
            height: 100%;
            background: linear-gradient(90deg, #22c55e, #16a34a);
            border-radius: 2px;
        }

        /* Air Quality */
        .air-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 10px;
        }

        .air-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
            text-align: center;
        }

        .aqi-value {
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .aqi-value.good { color: #22c55e; }
        .aqi-value.moderate { color: #eab308; }
        .aqi-value.unhealthy { color: #ef4444; }

        .aqi-label {
            font-size: 0.75em;
            padding: 2px 8px;
            border-radius: 10px;
            display: inline-block;
        }

        .aqi-label.good { background: rgba(34, 197, 94, 0.2); color: #34d399; }
        .aqi-label.moderate { background: rgba(234, 179, 8, 0.2); color: #fbbf24; }

        .air-location {
            font-size: 0.75em;
            color: #94a3b8;
            margin-top: 5px;
        }

        /* Weather */
        .weather-display {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .weather-temp {
            font-size: 3em;
            font-weight: bold;
            color: #38bdf8;
        }

        .weather-details {
            flex: 1;
            font-size: 0.9em;
        }

        .weather-detail {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            color: #94a3b8;
        }

        /* Emergency Services */
        .emergency-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
            gap: 10px;
        }

        .emergency-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
            border-left: 4px solid #3b82f6;
        }

        .emergency-card.police { border-left-color: #3b82f6; }
        .emergency-card.fire { border-left-color: #ef4444; }

        .emergency-name {
            font-weight: 600;
            font-size: 0.85em;
            margin-bottom: 8px;
        }

        .emergency-stats {
            font-size: 0.75em;
            color: #94a3b8;
        }

        .response-time {
            color: #34d399;
            font-weight: 600;
        }

        /* Parking */
        .parking-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
            gap: 10px;
        }

        .parking-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
        }

        .parking-name {
            font-weight: 500;
            font-size: 0.85em;
            margin-bottom: 8px;
        }

        .parking-spaces {
            display: flex;
            align-items: baseline;
            gap: 5px;
        }

        .parking-available {
            font-size: 1.5em;
            font-weight: bold;
            color: #22c55e;
        }

        .parking-available.low { color: #fbbf24; }
        .parking-available.full { color: #ef4444; }

        .parking-total {
            font-size: 0.8em;
            color: #64748b;
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
        <h1>Metropolis Smart City</h1>
        <div class="subtitle">Integrated Urban Digital Twin - Real-Time Monitoring</div>
    </div>

    <div class="stats-bar">
        <div class="stat-card">
            <div class="stat-value" id="population">-</div>
            <div class="stat-label">Population</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="districts">-</div>
            <div class="stat-label">Districts</div>
        </div>
        <div class="stat-card">
            <div class="stat-value good" id="buses-active">-</div>
            <div class="stat-label">Active Buses</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="parking">-</div>
            <div class="stat-label">Parking Available</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="power-load">-</div>
            <div class="stat-label">Power Load</div>
        </div>
        <div class="stat-card">
            <div class="stat-value good" id="air-quality">-</div>
            <div class="stat-label">Air Quality (AQI)</div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>City Districts</h2>
            <div class="district-grid" id="districts-grid"></div>
        </div>

        <div class="panel">
            <h2>Metro System</h2>
            <div class="metro-grid" id="metro-lines"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Bus Fleet</h2>
            <div class="bus-grid" id="buses"></div>
        </div>

        <div class="panel">
            <h2>Traffic Flow</h2>
            <div class="traffic-grid" id="traffic"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Power Grid</h2>
            <div class="power-overview" id="power-overview"></div>
            <div class="substation-grid" id="substations"></div>
        </div>

        <div class="panel">
            <h2>Weather & Air Quality</h2>
            <div class="weather-display" id="weather"></div>
            <div class="air-grid" id="air-quality-grid" style="margin-top: 15px;"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Emergency Services</h2>
            <div class="emergency-grid" id="emergency"></div>
        </div>

        <div class="panel">
            <h2>Parking Facilities</h2>
            <div class="parking-grid" id="parking-grid"></div>
        </div>
    </div>

    <div class="timestamp" id="timestamp">Waiting for data...</div>

    <script>
        let ws;
        let reconnectInterval;

        function formatNumber(num) {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(0) + 'K';
            return num.toString();
        }

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

            // Stats Bar
            document.getElementById('population').textContent = formatNumber(stats.population || 0);
            document.getElementById('districts').textContent = stats.districts || 0;
            document.getElementById('buses-active').textContent = stats.busesActive || 0;
            document.getElementById('parking').textContent = formatNumber(stats.parkingAvailable || 0);
            const loadPercent = stats.powerCapacity ? Math.round((stats.powerLoad / stats.powerCapacity) * 100) : 0;
            document.getElementById('power-load').textContent = loadPercent + '%';
            document.getElementById('air-quality').textContent = stats.airQuality || '-';
            const aqiEl = document.getElementById('air-quality');
            aqiEl.className = 'stat-value ' + (stats.airQuality <= 50 ? 'good' : stats.airQuality <= 100 ? 'warning' : 'critical');

            // Districts
            const districtContainer = document.getElementById('districts-grid');
            districtContainer.innerHTML = (data.districts || []).map(d => {
                const props = d.properties || {};
                const typeClass = props.districtType || 'residential';
                return `
                    <div class="district-card ${typeClass}">
                        <div class="district-name">${d.name}</div>
                        <div class="district-pop">${formatNumber(props.population || 0)} pop</div>
                    </div>
                `;
            }).join('');

            // Metro Lines
            const metroContainer = document.getElementById('metro-lines');
            const lineColors = { red: '#ef4444', blue: '#3b82f6', green: '#22c55e' };
            metroContainer.innerHTML = (data.metroLines || []).map(line => {
                const props = line.properties || {};
                const color = lineColors[props.color] || '#64748b';
                return `
                    <div class="metro-line">
                        <div class="metro-indicator" style="background: ${color}">
                            ${(props.color || 'X')[0].toUpperCase()}
                        </div>
                        <div class="metro-info">
                            <div class="metro-name">${line.name}</div>
                            <div class="metro-stats">
                                ${props.stations || 0} stations | ${props.length || 0} km |
                                ${formatNumber(props.dailyRidership || 0)} daily riders
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // Buses
            const busContainer = document.getElementById('buses');
            busContainer.innerHTML = (data.buses || []).map(bus => {
                const props = bus.properties || {};
                const battery = props.batteryLevel || 100;
                const isCharging = battery < 30;
                return `
                    <div class="bus-card ${isCharging ? 'charging' : ''}">
                        <div class="bus-icon">${isCharging ? '🔌' : '🚌'}</div>
                        <div class="bus-id">${bus.name.replace('Bus ', '#')}</div>
                        <div class="bus-battery">${battery}%</div>
                    </div>
                `;
            }).join('');

            // Traffic
            const trafficContainer = document.getElementById('traffic');
            trafficContainer.innerHTML = (data.trafficSensors || []).map(sensor => {
                const props = sensor.properties || {};
                const occupancy = props.occupancy || 0;
                const flowClass = occupancy < 40 ? 'light' : occupancy < 70 ? 'moderate' : 'heavy';
                return `
                    <div class="traffic-card">
                        <div class="traffic-name">${sensor.name.replace('Traffic Sensor - ', '')}</div>
                        <div class="traffic-bar">
                            <div class="traffic-fill ${flowClass}" style="width: ${occupancy}%"></div>
                        </div>
                        <div class="traffic-stats">
                            <span>${props.averageSpeed || 0} mph</span>
                            <span>${props.vehicleCount || 0} vehicles</span>
                        </div>
                    </div>
                `;
            }).join('');

            // Power Grid
            const powerContainer = document.getElementById('power-overview');
            if (data.powerGrid) {
                const props = data.powerGrid.properties || {};
                const load = props.currentLoad || 0;
                const capacity = props.totalCapacity || 1;
                const loadPct = Math.round((load / capacity) * 100);
                powerContainer.innerHTML = `
                    <div class="power-gauge" style="--load: ${loadPct}">
                        <span class="power-value">${loadPct}%</span>
                    </div>
                    <div class="power-details">
                        <div class="power-stat">Load: ${load} / ${capacity} MW</div>
                        <div class="power-stat">Peak: ${props.peakLoad || 0} MW</div>
                        <div class="power-stat">Renewable: ${props.renewablePercentage || 0}%</div>
                    </div>
                `;
            }

            // Substations
            const subContainer = document.getElementById('substations');
            subContainer.innerHTML = (data.substations || []).map(sub => {
                const props = sub.properties || {};
                const load = props.currentLoad || 0;
                const capacity = props.capacity || 1;
                const pct = Math.round((load / capacity) * 100);
                return `
                    <div class="substation-card">
                        <div class="substation-name">${sub.name.replace(' Substation', '')}</div>
                        <div class="substation-load">
                            <div class="substation-fill" style="width: ${pct}%"></div>
                        </div>
                    </div>
                `;
            }).join('');

            // Weather
            const weatherContainer = document.getElementById('weather');
            if (data.weather) {
                const props = data.weather.properties || {};
                weatherContainer.innerHTML = `
                    <div class="weather-temp">${props.temperature || '-'}°C</div>
                    <div class="weather-details">
                        <div class="weather-detail"><span>Humidity</span><span>${props.humidity || 0}%</span></div>
                        <div class="weather-detail"><span>Wind</span><span>${props.windSpeed || 0} km/h</span></div>
                        <div class="weather-detail"><span>Pressure</span><span>${props.pressure || 0} hPa</span></div>
                        <div class="weather-detail"><span>Visibility</span><span>${props.visibility || 0} km</span></div>
                    </div>
                `;
            }

            // Air Quality
            const airContainer = document.getElementById('air-quality-grid');
            airContainer.innerHTML = (data.airStations || []).map(station => {
                const props = station.properties || {};
                const aqi = props.aqi || 0;
                const aqiClass = aqi <= 50 ? 'good' : aqi <= 100 ? 'moderate' : 'unhealthy';
                const label = aqi <= 50 ? 'Good' : aqi <= 100 ? 'Moderate' : 'Unhealthy';
                return `
                    <div class="air-card">
                        <div class="aqi-value ${aqiClass}">${aqi}</div>
                        <span class="aqi-label ${aqiClass}">${label}</span>
                        <div class="air-location">${station.name.replace(' Air Quality Station', '')}</div>
                    </div>
                `;
            }).join('');

            // Emergency Services
            const emergencyContainer = document.getElementById('emergency');
            const services = [
                ...(data.policeStations || []).map(s => ({...s, stype: 'police'})),
                ...(data.fireStations || []).map(s => ({...s, stype: 'fire'}))
            ];
            emergencyContainer.innerHTML = services.map(svc => {
                const props = svc.properties || {};
                return `
                    <div class="emergency-card ${svc.stype}">
                        <div class="emergency-name">${svc.stype === 'police' ? '👮' : '🚒'} ${svc.name}</div>
                        <div class="emergency-stats">
                            ${svc.stype === 'police' ? `${props.officers || 0} officers` : `${props.firefighters || 0} firefighters`}<br>
                            Response: <span class="response-time">${props.responseTime || 0} min</span>
                        </div>
                    </div>
                `;
            }).join('');

            // Parking
            const parkingContainer = document.getElementById('parking-grid');
            parkingContainer.innerHTML = (data.parkingFacilities || []).map(pf => {
                const props = pf.properties || {};
                const available = props.availableSpaces || 0;
                const total = props.totalSpaces || 1;
                const ratio = available / total;
                const availClass = ratio < 0.1 ? 'full' : ratio < 0.3 ? 'low' : '';
                return `
                    <div class="parking-card">
                        <div class="parking-name">${pf.name}</div>
                        <div class="parking-spaces">
                            <span class="parking-available ${availClass}">${available}</span>
                            <span class="parking-total">/ ${total} spaces</span>
                        </div>
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


async def start_websocket_server(port: int, collector: SmartCityDataCollector):
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
    parser = argparse.ArgumentParser(description="Smart City Digital Twin Web UI")
    parser.add_argument("--port", type=int, default=8092, help="HTTP server port")
    parser.add_argument("--base-url", help="DTaaS server URL")
    args = parser.parse_args()

    client = get_client(args.base_url)
    collector = SmartCityDataCollector(client)

    # Start HTTP server in a thread
    http_thread = threading.Thread(target=run_http_server, args=(args.port,), daemon=True)
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Smart City Digital Twin - Web UI")
    print(f"  Open http://localhost:{args.port} in your browser")
    print(f"{'='*60}\n")

    # Run WebSocket server
    asyncio.run(start_websocket_server(args.port + 1, collector))


if __name__ == "__main__":
    main()
