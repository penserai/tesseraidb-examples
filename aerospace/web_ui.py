#!/usr/bin/env python3
"""
Aerospace / Satellite Constellation Digital Twin - Web UI
==========================================================

Real-time satellite constellation monitoring dashboard showing:
- Constellation overview
- Satellite status by orbital plane
- Ground station connectivity
- Payload status
- Space weather conditions
- Collision avoidance alerts

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
DOMAIN = "aerospace"


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


class AerospaceDataCollector:
    """Collects data from the aerospace digital twin."""

    def __init__(self, client):
        self.client = client

    def collect_data(self) -> dict:
        """Collect all aerospace data."""
        try:
            twins = self.client.twins.list(domain=DOMAIN, page_size=600)

            data = {
                "timestamp": datetime.now().isoformat(),
                "constellation": None,
                "satellites": [],
                "groundStations": [],
                "missionControl": [],
                "payloads": [],
                "spaceWeather": None,
                "collisionAvoidance": None,
                "terminals": [],
                "launches": [],
                "stats": {
                    "totalSatellites": 0,
                    "operationalSatellites": 0,
                    "standbySatellites": 0,
                    "decommissioned": 0,
                    "groundStations": 0,
                    "activeTerminals": 0,
                    "avgBatteryLevel": 0,
                    "collisionWarnings": 0,
                    "totalThroughput": 0
                }
            }

            battery_total = 0
            sat_count = 0

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

                if twin_type == "SatelliteConstellation":
                    data["constellation"] = item
                elif twin_type == "CommunicationsSatellite":
                    data["satellites"].append(item)
                    data["stats"]["totalSatellites"] += 1
                    status = props.get("status", "")
                    if status == "operational":
                        data["stats"]["operationalSatellites"] += 1
                    elif status == "standby":
                        data["stats"]["standbySatellites"] += 1
                    elif status == "decommissioned":
                        data["stats"]["decommissioned"] += 1
                    battery_total += props.get("batteryLevel", 0)
                    sat_count += 1
                elif twin_type == "GroundStation":
                    data["groundStations"].append(item)
                    data["stats"]["groundStations"] += 1
                elif twin_type == "MissionControlCenter":
                    data["missionControl"].append(item)
                elif twin_type in ["KaBandPayload", "KuBandPayload"]:
                    data["payloads"].append(item)
                    if props.get("status") == "active":
                        data["stats"]["totalThroughput"] += props.get("throughput", 0)
                elif twin_type == "SpaceWeatherMonitor":
                    data["spaceWeather"] = item
                elif twin_type == "CollisionAvoidanceSystem":
                    data["collisionAvoidance"] = item
                    data["stats"]["collisionWarnings"] = props.get("activeWarnings", 0)
                elif "Terminal" in twin_type:
                    data["terminals"].append(item)
                    if props.get("status") == "connected":
                        data["stats"]["activeTerminals"] += 1
                elif twin_type == "Launch":
                    data["launches"].append(item)

            if sat_count > 0:
                data["stats"]["avgBatteryLevel"] = round(battery_total / sat_count)

            return data

        except Exception as e:
            logger.error(f"Failed to collect data: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aerospace Digital Twin - GlobalNet Constellation</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #020617 0%, #0f172a 50%, #020617 100%);
            min-height: 100vh;
            color: #e2e8f0;
            padding: 20px;
        }

        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 20px;
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(59, 130, 246, 0.2));
            border-radius: 16px;
            border: 1px solid rgba(139, 92, 246, 0.3);
        }

        .header h1 {
            font-size: 2em;
            color: #a78bfa;
            margin-bottom: 5px;
        }

        .header .subtitle {
            color: #94a3b8;
            font-size: 0.95em;
        }

        .stats-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9));
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            border: 1px solid rgba(139, 92, 246, 0.2);
        }

        .stat-value {
            font-size: 1.7em;
            font-weight: bold;
            color: #a78bfa;
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
            border: 1px solid rgba(139, 92, 246, 0.15);
        }

        .panel h2 {
            color: #a78bfa;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.1em;
        }

        /* Orbital Planes */
        .orbital-planes {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
        }

        .orbital-plane {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 12px;
            padding: 15px;
            text-align: center;
        }

        .plane-header {
            font-weight: 600;
            margin-bottom: 10px;
            color: #60a5fa;
        }

        .plane-ring {
            width: 100px;
            height: 100px;
            margin: 0 auto 10px;
            border: 3px solid rgba(139, 92, 246, 0.3);
            border-radius: 50%;
            position: relative;
        }

        .sat-dot {
            position: absolute;
            width: 8px;
            height: 8px;
            background: #34d399;
            border-radius: 50%;
            transform: translate(-50%, -50%);
        }

        .sat-dot.standby { background: #fbbf24; }
        .sat-dot.decommissioned { background: #64748b; }

        .plane-stats {
            font-size: 0.8em;
            color: #94a3b8;
        }

        /* Ground Stations */
        .gs-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
        }

        .gs-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
            border-left: 4px solid #22c55e;
        }

        .gs-card.ttc { border-left-color: #f59e0b; }

        .gs-name {
            font-weight: 600;
            font-size: 0.85em;
            margin-bottom: 5px;
        }

        .gs-location {
            font-size: 0.7em;
            color: #64748b;
            margin-bottom: 8px;
        }

        .gs-stats {
            font-size: 0.75em;
            color: #94a3b8;
        }

        .gs-status {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.7em;
            background: rgba(34, 197, 94, 0.2);
            color: #34d399;
        }

        /* Space Weather */
        .weather-display {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 12px;
        }

        .weather-item {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 15px;
            text-align: center;
        }

        .weather-value {
            font-size: 1.5em;
            font-weight: bold;
            color: #60a5fa;
            margin-bottom: 5px;
        }

        .weather-value.warning { color: #fbbf24; }
        .weather-value.danger { color: #ef4444; }

        .weather-label {
            font-size: 0.75em;
            color: #94a3b8;
        }

        /* Mission Control */
        .mcc-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }

        .mcc-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 15px;
        }

        .mcc-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }

        .mcc-name {
            font-weight: 600;
            font-size: 0.9em;
        }

        .mcc-status {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.7em;
            font-weight: 600;
        }

        .mcc-status.operational { background: rgba(34, 197, 94, 0.2); color: #34d399; }
        .mcc-status.standby { background: rgba(234, 179, 8, 0.2); color: #fbbf24; }

        .mcc-stats {
            font-size: 0.8em;
            color: #94a3b8;
        }

        /* Collision Avoidance */
        .collision-panel {
            display: flex;
            align-items: center;
            gap: 20px;
            padding: 15px;
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
        }

        .collision-icon {
            font-size: 2.5em;
        }

        .collision-info {
            flex: 1;
        }

        .collision-status {
            font-size: 1.2em;
            font-weight: 600;
            margin-bottom: 5px;
        }

        .collision-status.clear { color: #34d399; }
        .collision-status.warning { color: #fbbf24; }
        .collision-status.danger { color: #ef4444; }

        .collision-details {
            font-size: 0.85em;
            color: #94a3b8;
        }

        /* Terminals */
        .terminal-summary {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
        }

        .terminal-type {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 15px;
            text-align: center;
        }

        .terminal-icon {
            font-size: 1.5em;
            margin-bottom: 5px;
        }

        .terminal-count {
            font-size: 1.3em;
            font-weight: bold;
            color: #60a5fa;
        }

        .terminal-label {
            font-size: 0.75em;
            color: #94a3b8;
        }

        /* Launches */
        .launch-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .launch-item {
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(15, 23, 42, 0.5);
            border-radius: 8px;
            padding: 10px 12px;
        }

        .launch-icon {
            font-size: 1.3em;
        }

        .launch-info {
            flex: 1;
        }

        .launch-name {
            font-weight: 500;
            font-size: 0.85em;
        }

        .launch-date {
            font-size: 0.7em;
            color: #64748b;
        }

        .launch-sats {
            font-size: 0.8em;
            color: #a78bfa;
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
        <h1>GlobalNet Communications Constellation</h1>
        <div class="subtitle">Aerospace Digital Twin - LEO Satellite Network Monitoring</div>
    </div>

    <div class="stats-bar">
        <div class="stat-card">
            <div class="stat-value" id="total-sats">-</div>
            <div class="stat-label">Total Satellites</div>
        </div>
        <div class="stat-card">
            <div class="stat-value success" id="operational">-</div>
            <div class="stat-label">Operational</div>
        </div>
        <div class="stat-card">
            <div class="stat-value warning" id="standby">-</div>
            <div class="stat-label">Standby</div>
        </div>
        <div class="stat-card">
            <div class="stat-value info" id="ground-stations">-</div>
            <div class="stat-label">Ground Stations</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="avg-battery">-</div>
            <div class="stat-label">Avg Battery</div>
        </div>
        <div class="stat-card">
            <div class="stat-value info" id="throughput">-</div>
            <div class="stat-label">Total Gbps</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="terminals">-</div>
            <div class="stat-label">Active Terminals</div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Orbital Planes</h2>
            <div class="orbital-planes" id="orbital-planes"></div>
        </div>

        <div class="panel">
            <h2>Ground Stations</h2>
            <div class="gs-grid" id="ground-stations-grid"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Space Weather</h2>
            <div class="weather-display" id="space-weather"></div>
        </div>

        <div class="panel">
            <h2>Collision Avoidance</h2>
            <div class="collision-panel" id="collision-avoidance"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Mission Control Centers</h2>
            <div class="mcc-grid" id="mission-control"></div>
        </div>

        <div class="panel">
            <h2>User Terminals</h2>
            <div class="terminal-summary" id="terminals-summary"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Launch History</h2>
            <div class="launch-list" id="launches"></div>
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
            document.getElementById('total-sats').textContent = stats.totalSatellites || 0;
            document.getElementById('operational').textContent = stats.operationalSatellites || 0;
            document.getElementById('standby').textContent = stats.standbySatellites || 0;
            document.getElementById('ground-stations').textContent = stats.groundStations || 0;
            document.getElementById('avg-battery').textContent = (stats.avgBatteryLevel || 0) + '%';
            document.getElementById('throughput').textContent = stats.totalThroughput || 0;
            document.getElementById('terminals').textContent = stats.activeTerminals || 0;

            // Orbital Planes
            const planeContainer = document.getElementById('orbital-planes');
            const satsByPlane = {};
            (data.satellites || []).forEach(sat => {
                const plane = sat.properties?.orbitalPlane || 1;
                if (!satsByPlane[plane]) satsByPlane[plane] = [];
                satsByPlane[plane].push(sat);
            });

            let planesHtml = '';
            for (let plane = 1; plane <= 6; plane++) {
                const sats = satsByPlane[plane] || [];
                const operational = sats.filter(s => s.properties?.status === 'operational').length;
                const total = sats.length;

                let dotsHtml = '';
                sats.slice(0, 12).forEach((sat, i) => {
                    const angle = (i / 12) * 360;
                    const radius = 40;
                    const x = 50 + radius * Math.cos(angle * Math.PI / 180);
                    const y = 50 + radius * Math.sin(angle * Math.PI / 180);
                    const status = sat.properties?.status || 'operational';
                    dotsHtml += `<div class="sat-dot ${status}" style="left: ${x}%; top: ${y}%"></div>`;
                });

                planesHtml += `
                    <div class="orbital-plane">
                        <div class="plane-header">Plane ${plane}</div>
                        <div class="plane-ring">${dotsHtml}</div>
                        <div class="plane-stats">${operational}/${total} operational</div>
                    </div>
                `;
            }
            planeContainer.innerHTML = planesHtml;

            // Ground Stations
            const gsContainer = document.getElementById('ground-stations-grid');
            gsContainer.innerHTML = (data.groundStations || []).map(gs => {
                const props = gs.properties || {};
                const type = props.stationType || 'gateway';
                return `
                    <div class="gs-card ${type}">
                        <div class="gs-name">${gs.name}</div>
                        <div class="gs-location">${props.country || ''}</div>
                        <div class="gs-stats">
                            ${props.antennas || 0} antennas | ${props.bands?.join('/') || 'N/A'}
                        </div>
                        <span class="gs-status">${props.status || 'unknown'}</span>
                    </div>
                `;
            }).join('');

            // Space Weather
            const weatherContainer = document.getElementById('space-weather');
            if (data.spaceWeather) {
                const props = data.spaceWeather.properties || {};
                const kp = props.kpIndex || 0;
                const kpClass = kp > 5 ? 'danger' : kp > 3 ? 'warning' : '';
                weatherContainer.innerHTML = `
                    <div class="weather-item">
                        <div class="weather-value">${props.solarFluxIndex || '-'}</div>
                        <div class="weather-label">Solar Flux (SFU)</div>
                    </div>
                    <div class="weather-item">
                        <div class="weather-value ${kpClass}">${kp}</div>
                        <div class="weather-label">Kp Index</div>
                    </div>
                    <div class="weather-item">
                        <div class="weather-value">${props.radiationStormLevel || 'S0'}</div>
                        <div class="weather-label">Radiation Storm</div>
                    </div>
                    <div class="weather-item">
                        <div class="weather-value">${props.geomagneticStormLevel || 'G0'}</div>
                        <div class="weather-label">Geomagnetic Storm</div>
                    </div>
                `;
            }

            // Collision Avoidance
            const collisionContainer = document.getElementById('collision-avoidance');
            if (data.collisionAvoidance) {
                const props = data.collisionAvoidance.properties || {};
                const warnings = props.activeWarnings || 0;
                const statusClass = warnings > 2 ? 'danger' : warnings > 0 ? 'warning' : 'clear';
                const icon = warnings > 0 ? '⚠️' : '✅';
                collisionContainer.innerHTML = `
                    <div class="collision-icon">${icon}</div>
                    <div class="collision-info">
                        <div class="collision-status ${statusClass}">
                            ${warnings > 0 ? `${warnings} Active Warnings` : 'All Clear'}
                        </div>
                        <div class="collision-details">
                            Maneuvers this month: ${props.maneuversThisMonth || 0} |
                            Warning threshold: ${props.warningThreshold || 1} km
                        </div>
                    </div>
                `;
            }

            // Mission Control
            const mccContainer = document.getElementById('mission-control');
            mccContainer.innerHTML = (data.missionControl || []).map(mcc => {
                const props = mcc.properties || {};
                const status = props.status || 'operational';
                return `
                    <div class="mcc-card">
                        <div class="mcc-header">
                            <span class="mcc-name">${mcc.name}</span>
                            <span class="mcc-status ${status}">${status}</span>
                        </div>
                        <div class="mcc-stats">
                            ${props.location || ''}<br>
                            ${props.operators || 0} operators |
                            ${props.activeAlerts || 0} alerts
                        </div>
                    </div>
                `;
            }).join('');

            // Terminals
            const terminalContainer = document.getElementById('terminals-summary');
            const terminalTypes = {};
            (data.terminals || []).forEach(t => {
                const type = t.properties?.terminalType || 'Unknown';
                terminalTypes[type] = (terminalTypes[type] || 0) + 1;
            });

            const icons = { Consumer: '🏠', Enterprise: '🏢', Maritime: '🚢', Aviation: '✈️' };
            terminalContainer.innerHTML = Object.entries(terminalTypes).map(([type, count]) => `
                <div class="terminal-type">
                    <div class="terminal-icon">${icons[type] || '📡'}</div>
                    <div class="terminal-count">${count}</div>
                    <div class="terminal-label">${type}</div>
                </div>
            `).join('');

            // Launches
            const launchContainer = document.getElementById('launches');
            launchContainer.innerHTML = (data.launches || []).map(launch => {
                const props = launch.properties || {};
                return `
                    <div class="launch-item">
                        <div class="launch-icon">🚀</div>
                        <div class="launch-info">
                            <div class="launch-name">${launch.name}</div>
                            <div class="launch-date">${props.launchDate || ''} | ${props.launchVehicle || ''}</div>
                        </div>
                        <div class="launch-sats">${props.satellitesDeployed || 0} sats</div>
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


async def start_websocket_server(port: int, collector: AerospaceDataCollector):
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
    parser = argparse.ArgumentParser(description="Aerospace Digital Twin Web UI")
    parser.add_argument("--port", type=int, default=8096, help="HTTP server port")
    parser.add_argument("--base-url", help="DTaaS server URL")
    args = parser.parse_args()

    client = get_client(args.base_url)
    collector = AerospaceDataCollector(client)

    # Start HTTP server in a thread
    http_thread = threading.Thread(target=run_http_server, args=(args.port,), daemon=True)
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Aerospace Digital Twin - Web UI")
    print(f"  Open http://localhost:{args.port} in your browser")
    print(f"{'='*60}\n")

    # Run WebSocket server
    asyncio.run(start_websocket_server(args.port + 1, collector))


if __name__ == "__main__":
    main()
