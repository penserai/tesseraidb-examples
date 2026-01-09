#!/usr/bin/env python3
"""
Manufacturing / Industry 4.0 Digital Twin - Interactive Web UI
==============================================================

A production-grade web interface for visualizing smart factory operations
including production lines, CNC machines, robots, and quality control.

Features:
- Production line OEE monitoring
- CNC machine status and performance
- Robot status tracking
- Quality control metrics
- Energy consumption
- Maintenance schedules
- RSP (RDF Stream Processing) real-time alerts

Usage:
    python web_ui.py [--port 8104]

Then open http://localhost:8104 in your browser.

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
from typing import Dict, List, Set, Optional
from collections import defaultdict

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'sdks', 'python'))

from common import get_client, logger

# RSP imports
try:
    from dtaas.models import (
        WindowConfig,
        WindowType,
        OutputConfig,
        ContinuousQueryCreate,
    )
    RSP_AVAILABLE = True
except ImportError:
    RSP_AVAILABLE = False
    logger.warning("RSP models not available - alerts will be disabled")

# Global state
client = None
factory: Dict = {}
production_lines: Dict[str, dict] = {}
cnc_machines: Dict[str, dict] = {}
robots: Dict[str, dict] = {}
conveyors: Dict[str, dict] = {}
qc_equipment: Dict[str, dict] = {}
maintenance: Dict[str, dict] = {}
energy_data: Dict[str, dict] = {}
connected_clients: Set = set()
ws_port = 8105

# RSP state
rsp_enabled = False
rsp_query_ids: List[str] = []
rsp_source_ids: List[str] = []
rsp_alerts: List[dict] = []

# RSP Configuration - Continuous queries for manufacturing monitoring
RSP_STREAM_CONFIG = {
    "type": "event_bus",
    "twin_id_patterns": ["*"],
    "event_types": ["twin.updated", "twin.property_changed"],
}

RSP_CONTINUOUS_QUERIES = [
    {
        "name": "High Spindle Load Alert",
        "description": "Detect CNC machines with spindle load exceeding 85%",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?machine ?spindleLoad
            WHERE {
                ?machine a <https://schema.org/CNCMachine> .
                ?machine dto:spindleLoad ?spindleLoad .
                FILTER(xsd:double(?spindleLoad) > 85.0)
            }
        """,
        "window_duration": 60,
        "window_slide": 15,
        "severity": "warning",
        "icon": "⚙️",
    },
    {
        "name": "Low OEE Alert",
        "description": "Detect production lines with OEE below 80%",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?line ?oee
            WHERE {
                ?line a <https://schema.org/ProductionLine> .
                ?line dto:currentOEE ?oee .
                FILTER(xsd:double(?oee) < 80.0)
            }
        """,
        "window_duration": 300,
        "window_slide": 60,
        "severity": "critical",
        "icon": "📉",
    },
    {
        "name": "Machine Error Detected",
        "description": "Detect machines entering error state",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>

            SELECT ?machine ?status
            WHERE {
                ?machine dto:status ?status .
                FILTER(CONTAINS(STR(?machine), "cnc-"))
                FILTER(?status = "error" || ?status = "maintenance_required")
            }
        """,
        "window_duration": 30,
        "window_slide": 10,
        "severity": "critical",
        "icon": "🔴",
    },
    {
        "name": "Low Coolant Level",
        "description": "Detect CNC machines with coolant level below 20%",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?machine ?coolantLevel
            WHERE {
                ?machine a <https://schema.org/CNCMachine> .
                ?machine dto:coolantLevel ?coolantLevel .
                FILTER(xsd:double(?coolantLevel) < 20.0)
            }
        """,
        "window_duration": 120,
        "window_slide": 30,
        "severity": "warning",
        "icon": "💧",
    },
    {
        "name": "High Defect Rate",
        "description": "Detect quality issues with defect rate exceeding 2%",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?equipment ?defects ?inspected
            WHERE {
                ?equipment dto:defectsFoundToday ?defects .
                ?equipment dto:partsInspectedToday ?inspected .
                FILTER(xsd:integer(?inspected) > 0)
                FILTER(xsd:double(?defects) / xsd:double(?inspected) > 0.02)
            }
        """,
        "window_duration": 180,
        "window_slide": 60,
        "severity": "critical",
        "icon": "⚠️",
    },
]


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


def load_manufacturing_data():
    """Load manufacturing data from DTaaS."""
    global factory, production_lines, cnc_machines, robots, conveyors, qc_equipment, maintenance, energy_data

    factory = {}
    production_lines = {}
    cnc_machines = {}
    robots = {}
    conveyors = {}
    qc_equipment = {}
    maintenance = {}
    energy_data = {}

    try:
        twins = client.twins.list(domain="manufacturing", page_size=500)

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

            if twin_type == "Factory":
                factory = item
            elif twin_type == "ProductionLine":
                production_lines[twin_id] = item
            elif twin_type == "CNCMachine":
                cnc_machines[twin_id] = item
            elif twin_type == "IndustrialRobot":
                robots[twin_id] = item
            elif twin_type == "Conveyor":
                conveyors[twin_id] = item
            elif twin_type in ["CoordinateMeasuringMachine", "VisionInspectionSystem", "XRayInspectionSystem", "HardnessTester", "SurfaceRoughnessTester"]:
                qc_equipment[twin_id] = item
            elif twin_type == "MaintenanceTask":
                maintenance[twin_id] = item
            elif twin_type == "EnergyMeter":
                energy_data[twin_id] = item

        logger.info(f"Loaded: {len(production_lines)} lines, {len(cnc_machines)} CNC machines, "
                   f"{len(robots)} robots")

    except Exception as e:
        logger.error(f"Failed to load manufacturing data: {e}")
        raise


def get_factory_summary() -> dict:
    """Get factory summary statistics."""
    props = factory.get("properties", {}) if factory else {}

    # Calculate averages
    avg_oee = 0
    running_machines = 0
    idle_machines = 0
    error_machines = 0

    for cnc in cnc_machines.values():
        cnc_props = cnc.get("properties", {})
        status = cnc_props.get("status", "unknown")
        if status == "running":
            running_machines += 1
        elif status == "idle":
            idle_machines += 1
        else:
            error_machines += 1

    for line in production_lines.values():
        line_props = line.get("properties", {})
        avg_oee += float(line_props.get("currentOEE", 0))
    if production_lines:
        avg_oee /= len(production_lines)

    # Energy
    current_power = 0
    for meter in energy_data.values():
        meter_props = meter.get("properties", {})
        current_power += float(meter_props.get("currentPower", 0))

    # Maintenance
    scheduled_maint = sum(1 for m in maintenance.values()
                         if m["properties"].get("status") == "scheduled")
    in_progress_maint = sum(1 for m in maintenance.values()
                           if m["properties"].get("status") == "in_progress")

    return {
        "name": factory.get("name", "Factory"),
        "employees": int(props.get("employees", 0)),
        "avgOEE": avg_oee,
        "targetOEE": 90,
        "runningMachines": running_machines,
        "idleMachines": idle_machines,
        "errorMachines": error_machines,
        "totalMachines": len(cnc_machines),
        "totalRobots": len(robots),
        "currentPower": current_power,
        "scheduledMaintenance": scheduled_maint,
        "inProgressMaintenance": in_progress_maint,
    }


def get_production_lines_data() -> List[dict]:
    """Get production line data."""
    result = []
    for line in production_lines.values():
        props = line.get("properties", {})
        oee = float(props.get("currentOEE", 0))
        target = float(props.get("targetOEE", 90))
        daily_actual = int(props.get("dailyActual", 0))
        daily_target = int(props.get("dailyTarget", 0))

        result.append({
            "id": line["id"],
            "name": line["name"],
            "productType": props.get("productType", ""),
            "status": props.get("status", "unknown"),
            "currentOEE": oee,
            "targetOEE": target,
            "oeeStatus": "good" if oee >= target else ("warning" if oee >= target * 0.9 else "critical"),
            "taktTime": int(props.get("taktTime", 0)),
            "dailyActual": daily_actual,
            "dailyTarget": daily_target,
            "productivity": (daily_actual / daily_target * 100) if daily_target > 0 else 0,
        })

    return result


def get_cnc_machines_data() -> List[dict]:
    """Get CNC machine data."""
    result = []
    for cnc in cnc_machines.values():
        props = cnc.get("properties", {})

        result.append({
            "id": cnc["id"],
            "name": cnc["name"],
            "machineType": props.get("machineType", ""),
            "status": props.get("status", "unknown"),
            "spindleSpeed": int(props.get("spindleSpeed", 0)),
            "spindleLoad": float(props.get("spindleLoad", 0)),
            "powerConsumption": float(props.get("powerConsumption", 0)),
            "coolantLevel": float(props.get("coolantLevel", 0)),
            "coolantTemp": float(props.get("coolantTemp", 0)),
            "partsProduced": int(props.get("partsProduced", 0)),
            "partsTarget": int(props.get("partsTarget", 0)),
            "cycleTime": int(props.get("cycleTime", 0)),
            "totalRuntime": int(props.get("totalRuntime", 0)),
        })

    return sorted(result, key=lambda x: x["id"])


def get_robots_data() -> List[dict]:
    """Get robot data."""
    result = []
    for robot in robots.values():
        props = robot.get("properties", {})

        result.append({
            "id": robot["id"],
            "name": robot["name"],
            "robotType": props.get("robotType", ""),
            "manufacturer": props.get("manufacturer", ""),
            "status": props.get("status", "unknown"),
            "payload": int(props.get("payload", 0)),
            "reach": int(props.get("reach", 0)),
            "cycleCount": int(props.get("cycleCount", 0)),
            "programName": props.get("programName", ""),
            "tcpSpeed": int(props.get("tcpSpeed", 0)),
        })

    return result


def get_qc_data() -> dict:
    """Get quality control data."""
    inspected = 0
    defects = 0
    available = 0

    for qc in qc_equipment.values():
        props = qc.get("properties", {})
        inspected += int(props.get("partsInspectedToday", 0))
        defects += int(props.get("defectsFoundToday", 0))
        if props.get("status") == "available":
            available += 1

    defect_rate = (defects / inspected * 100) if inspected > 0 else 0

    return {
        "totalEquipment": len(qc_equipment),
        "availableEquipment": available,
        "partsInspected": inspected,
        "defectsFound": defects,
        "defectRate": defect_rate,
        "equipment": [
            {
                "id": qc["id"],
                "name": qc["name"],
                "type": qc["type"],
                "status": qc["properties"].get("status", "unknown"),
                "inspectedToday": int(qc["properties"].get("partsInspectedToday", 0)),
            }
            for qc in qc_equipment.values()
        ]
    }


def get_maintenance_data() -> List[dict]:
    """Get maintenance tasks."""
    result = []
    for maint in maintenance.values():
        props = maint.get("properties", {})
        result.append({
            "id": maint["id"],
            "name": maint["name"],
            "type": props.get("maintenanceType", ""),
            "description": props.get("description", ""),
            "status": props.get("status", "unknown"),
            "scheduledDate": props.get("scheduledDate", ""),
            "priority": props.get("priority", "medium"),
        })

    return sorted(result, key=lambda x: (x["status"] != "in_progress", x["priority"] != "high"))


def get_full_state() -> dict:
    """Get full state for client initialization."""
    return {
        "summary": get_factory_summary(),
        "productionLines": get_production_lines_data(),
        "cncMachines": get_cnc_machines_data(),
        "robots": get_robots_data(),
        "qualityControl": get_qc_data(),
        "maintenance": get_maintenance_data(),
        "rspEnabled": rsp_enabled,
        "rspAlerts": rsp_alerts[-20:],
    }


# =============================================================================
# RSP (RDF Stream Processing) Functions
# =============================================================================

def setup_rsp() -> bool:
    """Initialize RSP stream sources and continuous queries."""
    global rsp_enabled, rsp_query_ids, rsp_source_ids

    if not RSP_AVAILABLE:
        logger.warning("RSP models not available")
        return False

    try:
        stats = client.rsp.get_stats()
        logger.info(f"RSP service available: {stats.total_queries} queries")
    except Exception as e:
        logger.warning(f"RSP service not available: {e}")
        return False

    # Create stream source
    try:
        source = client.rsp.create_source(
            name="manufacturing-events",
            config=RSP_STREAM_CONFIG,
        )
        rsp_source_ids.append(source.id)
        logger.info(f"Created RSP stream source: {source.name}")
        client.rsp.start_source(source.id)
    except Exception as e:
        logger.warning(f"Could not create stream source: {e}")
        try:
            sources = client.rsp.list_sources()
            for src in sources.sources:
                if "manufacturing" in src.name.lower():
                    rsp_source_ids.append(src.id)
                    logger.info(f"Using existing source: {src.name}")
                    break
        except Exception:
            pass

    if not rsp_source_ids:
        return False

    # Create continuous queries
    for query_def in RSP_CONTINUOUS_QUERIES:
        try:
            query = client.rsp.create_query(
                ContinuousQueryCreate(
                    name=query_def["name"],
                    description=query_def["description"],
                    sparql=query_def["sparql"],
                    window=WindowConfig(
                        type=WindowType.TIME_BASED,
                        duration_seconds=query_def["window_duration"],
                        slide_seconds=query_def["window_slide"],
                    ),
                    stream_sources=rsp_source_ids,
                    output=OutputConfig(
                        push_to_event_bus=True,
                        persist_results=True,
                    ),
                )
            )
            rsp_query_ids.append(query.id)
            logger.info(f"Created RSP query: {query.name}")
            client.rsp.activate_query(query.id)
        except Exception as e:
            logger.warning(f"Could not create query '{query_def['name']}': {e}")
            try:
                queries = client.rsp.list_queries()
                for q in queries.queries:
                    if q.name == query_def["name"]:
                        rsp_query_ids.append(q.id)
                        break
            except Exception:
                pass

    rsp_enabled = len(rsp_query_ids) > 0
    logger.info(f"RSP enabled: {rsp_enabled} ({len(rsp_query_ids)} queries)")
    return rsp_enabled


def check_rsp_alerts() -> List[dict]:
    """Check RSP query results and generate alerts."""
    global rsp_alerts

    if not rsp_enabled:
        return []

    new_alerts = []

    for i, query_id in enumerate(rsp_query_ids):
        query_def = RSP_CONTINUOUS_QUERIES[i] if i < len(RSP_CONTINUOUS_QUERIES) else {}

        try:
            results = client.rsp.get_query_results(query_id, limit=5)

            for result in results.results:
                if result.bindings:
                    for binding in result.bindings:
                        alert = {
                            "id": f"{query_id}-{result.window_start}",
                            "type": query_def.get("name", "Alert"),
                            "severity": query_def.get("severity", "info"),
                            "icon": query_def.get("icon", "⚠️"),
                            "message": format_alert_message(query_def, binding),
                            "timestamp": result.window_end or datetime.utcnow().isoformat(),
                            "data": binding,
                        }

                        if not any(a["id"] == alert["id"] for a in rsp_alerts):
                            new_alerts.append(alert)

        except Exception as e:
            logger.debug(f"Error checking query {query_id}: {e}")

    rsp_alerts.extend(new_alerts)
    rsp_alerts[:] = rsp_alerts[-50:]

    return new_alerts


def format_alert_message(query_def: dict, binding: dict) -> str:
    """Format an alert message based on query type and binding data."""
    name = query_def.get("name", "Alert")

    if "Spindle" in name:
        load = binding.get("spindleLoad", "?")
        machine = binding.get("machine", "").split(":")[-1]
        return f"{machine}: Spindle load at {load}%"
    elif "OEE" in name:
        oee = binding.get("oee", "?")
        line = binding.get("line", "").split(":")[-1]
        return f"{line}: OEE at {oee}%"
    elif "Error" in name:
        status = binding.get("status", "?")
        machine = binding.get("machine", "").split(":")[-1]
        return f"{machine}: Status {status}"
    elif "Coolant" in name:
        level = binding.get("coolantLevel", "?")
        machine = binding.get("machine", "").split(":")[-1]
        return f"{machine}: Coolant at {level}%"
    elif "Defect" in name:
        defects = binding.get("defects", "?")
        inspected = binding.get("inspected", "?")
        return f"QC: {defects} defects in {inspected} parts"
    else:
        return str(binding)


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
                load_manufacturing_data()
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
                load_manufacturing_data()

                # Check for new RSP alerts
                new_alerts = check_rsp_alerts()
                if new_alerts:
                    await broadcast({
                        "type": "alerts",
                        "alerts": new_alerts,
                    })

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
    <title>Manufacturing Digital Twin</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
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
            font-weight: 500;
            color: #ff6b35;
        }
        .header h1 span { color: #888; font-weight: 300; }

        .dashboard {
            display: grid;
            grid-template-columns: 1fr 1fr 300px;
            grid-template-rows: auto 1fr 1fr;
            gap: 15px;
            padding: 15px;
            height: calc(100vh - 70px);
        }

        .summary-row {
            grid-column: 1 / -1;
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 12px;
        }
        .summary-card {
            background: rgba(0,0,0,0.4);
            border-radius: 10px;
            border: 1px solid #333;
            padding: 15px;
            text-align: center;
        }
        .summary-value {
            font-size: 1.8rem;
            font-weight: 600;
            color: #ff6b35;
        }
        .summary-value.good { color: #2ecc71; }
        .summary-value.warning { color: #f1c40f; }
        .summary-value.critical { color: #e74c3c; }
        .summary-label {
            font-size: 0.65rem;
            color: #888;
            margin-top: 5px;
            text-transform: uppercase;
        }

        .card {
            background: rgba(0,0,0,0.4);
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
            padding: 12px;
            overflow-y: auto;
            flex: 1;
        }

        /* Production Lines */
        .line-item {
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            border-left: 3px solid #333;
        }
        .line-item.running { border-left-color: #2ecc71; }
        .line-item.stopped { border-left-color: #e74c3c; }
        .line-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .line-name { font-size: 0.9rem; font-weight: 500; }
        .line-product { font-size: 0.65rem; color: #888; }
        .line-oee {
            font-size: 1.2rem;
            font-weight: 600;
        }
        .line-oee.good { color: #2ecc71; }
        .line-oee.warning { color: #f1c40f; }
        .line-oee.critical { color: #e74c3c; }
        .line-stats {
            display: flex;
            gap: 15px;
            font-size: 0.7rem;
            color: #888;
        }
        .progress-bar {
            height: 4px;
            background: #333;
            border-radius: 2px;
            margin-top: 8px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: #ff6b35;
            transition: width 0.5s;
        }

        /* CNC Machines Grid */
        .cnc-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 10px;
        }
        .cnc-item {
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            border: 1px solid #333;
            transition: all 0.2s;
        }
        .cnc-item:hover { border-color: #ff6b35; }
        .cnc-item.running { border-color: #2ecc71; }
        .cnc-item.error {
            border-color: #e74c3c;
            animation: errorPulse 1s infinite;
        }
        @keyframes errorPulse {
            0%, 100% { box-shadow: 0 0 5px rgba(231, 76, 60, 0.3); }
            50% { box-shadow: 0 0 15px rgba(231, 76, 60, 0.6); }
        }
        .cnc-icon {
            font-size: 1.5rem;
            margin-bottom: 5px;
        }
        .cnc-name {
            font-size: 0.7rem;
            font-weight: 500;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .cnc-status {
            font-size: 0.55rem;
            color: #888;
            margin-top: 3px;
        }
        .cnc-load {
            font-size: 0.6rem;
            margin-top: 5px;
        }

        /* Robots */
        .robot-item {
            display: flex;
            align-items: center;
            padding: 10px;
            margin-bottom: 8px;
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
        }
        .robot-icon {
            width: 36px;
            height: 36px;
            background: #333;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 10px;
            font-size: 1.1rem;
        }
        .robot-info { flex: 1; }
        .robot-name { font-size: 0.8rem; font-weight: 500; }
        .robot-type { font-size: 0.6rem; color: #888; }
        .robot-status {
            font-size: 0.6rem;
            padding: 3px 8px;
            border-radius: 10px;
            background: rgba(46, 204, 113, 0.2);
            color: #2ecc71;
        }
        .robot-status.idle {
            background: rgba(241, 196, 15, 0.2);
            color: #f1c40f;
        }

        /* QC Section */
        .qc-summary {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }
        .qc-stat {
            background: rgba(0,0,0,0.3);
            border-radius: 6px;
            padding: 10px;
            text-align: center;
        }
        .qc-stat-value {
            font-size: 1.3rem;
            font-weight: 600;
            color: #ff6b35;
        }
        .qc-stat-value.good { color: #2ecc71; }
        .qc-stat-value.bad { color: #e74c3c; }
        .qc-stat-label {
            font-size: 0.55rem;
            color: #666;
            text-transform: uppercase;
        }

        /* Maintenance */
        .maint-item {
            display: flex;
            align-items: center;
            padding: 8px 10px;
            margin-bottom: 6px;
            background: rgba(0,0,0,0.3);
            border-radius: 6px;
            border-left: 3px solid #333;
        }
        .maint-item.in_progress { border-left-color: #3498db; }
        .maint-item.scheduled { border-left-color: #f1c40f; }
        .maint-item.high { border-left-color: #e74c3c; }
        .maint-info { flex: 1; }
        .maint-desc {
            font-size: 0.7rem;
            font-weight: 500;
        }
        .maint-meta {
            font-size: 0.55rem;
            color: #666;
        }
        .maint-status {
            font-size: 0.55rem;
            padding: 2px 6px;
            border-radius: 3px;
            background: #333;
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
            background: #ff6b35;
            color: #000;
        }

        /* RSP Alerts */
        .alerts-card {
            grid-column: 1 / -1;
        }
        .alerts-card .card-body {
            max-height: 180px;
        }
        .alert-item {
            display: flex;
            align-items: center;
            padding: 8px 10px;
            margin-bottom: 6px;
            background: rgba(0,0,0,0.3);
            border-radius: 6px;
            border-left: 3px solid;
            animation: alertFadeIn 0.3s ease;
        }
        @keyframes alertFadeIn {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }
        .alert-item.critical {
            border-left-color: #e74c3c;
            background: rgba(231, 76, 60, 0.1);
        }
        .alert-item.warning {
            border-left-color: #f1c40f;
            background: rgba(241, 196, 15, 0.1);
        }
        .alert-item.info {
            border-left-color: #3498db;
            background: rgba(52, 152, 219, 0.1);
        }
        .alert-icon { font-size: 1rem; margin-right: 10px; }
        .alert-content { flex: 1; }
        .alert-type {
            font-size: 0.6rem;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
        }
        .alert-message {
            font-size: 0.75rem;
            color: #eee;
        }
        .alert-time {
            font-size: 0.55rem;
            color: #666;
        }
        .rsp-badge {
            font-size: 0.55rem;
            padding: 2px 6px;
            background: rgba(255, 107, 53, 0.2);
            color: #ff6b35;
            border-radius: 8px;
            margin-left: 8px;
        }
        .no-alerts {
            text-align: center;
            padding: 15px;
            color: #2ecc71;
            font-size: 0.75rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Manufacturing <span>Industry 4.0 Digital Twin</span></h1>
        <button class="refresh-btn" onclick="refresh()">Refresh Data</button>
    </div>

    <div class="dashboard">
        <div class="summary-row">
            <div class="summary-card">
                <div class="summary-value" id="avgOEE">0%</div>
                <div class="summary-label">Average OEE</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="runningMachines">0</div>
                <div class="summary-label">Running Machines</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="errorMachines">0</div>
                <div class="summary-label">Machines w/ Issues</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="totalRobots">0</div>
                <div class="summary-label">Active Robots</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="currentPower">0</div>
                <div class="summary-label">Power (kW)</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="maintenanceCount">0</div>
                <div class="summary-label">Pending Maint.</div>
            </div>
        </div>

        <!-- RSP Alerts Section -->
        <div class="card alerts-card">
            <div class="card-header">
                <h3>RSP Stream Alerts <span class="rsp-badge" id="rspStatus">Connecting...</span></h3>
            </div>
            <div class="card-body" id="alertsList">
                <div class="no-alerts">Initializing RSP stream processing...</div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Production Lines</h3>
            </div>
            <div class="card-body" id="linesList"></div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>CNC Machines</h3>
            </div>
            <div class="card-body">
                <div class="cnc-grid" id="cncGrid"></div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Robots</h3>
            </div>
            <div class="card-body" id="robotsList"></div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Quality Control</h3>
            </div>
            <div class="card-body" id="qcSection"></div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Maintenance</h3>
            </div>
            <div class="card-body" id="maintenanceList"></div>
        </div>
    </div>

    <script>
        let ws = null;

        function formatNumber(n) {
            return new Intl.NumberFormat().format(Math.round(n));
        }

        function updateSummary(summary) {
            const oeeEl = document.getElementById('avgOEE');
            oeeEl.textContent = summary.avgOEE.toFixed(1) + '%';
            oeeEl.className = 'summary-value ' + (summary.avgOEE >= summary.targetOEE ? 'good' : (summary.avgOEE >= summary.targetOEE * 0.9 ? 'warning' : 'critical'));

            document.getElementById('runningMachines').textContent = `${summary.runningMachines}/${summary.totalMachines}`;

            const errorEl = document.getElementById('errorMachines');
            errorEl.textContent = summary.errorMachines;
            errorEl.className = 'summary-value ' + (summary.errorMachines > 0 ? 'critical' : 'good');

            document.getElementById('totalRobots').textContent = summary.totalRobots;
            document.getElementById('currentPower').textContent = formatNumber(summary.currentPower);
            document.getElementById('maintenanceCount').textContent = summary.scheduledMaintenance + summary.inProgressMaintenance;
        }

        function updateProductionLines(lines) {
            const container = document.getElementById('linesList');
            container.innerHTML = lines.map(line => {
                const oeeClass = line.oeeStatus;
                const statusClass = line.status === 'running' ? 'running' : 'stopped';
                return `
                    <div class="line-item ${statusClass}">
                        <div class="line-header">
                            <div>
                                <div class="line-name">${line.name}</div>
                                <div class="line-product">${line.productType}</div>
                            </div>
                            <div class="line-oee ${oeeClass}">${line.currentOEE.toFixed(1)}%</div>
                        </div>
                        <div class="line-stats">
                            <span>Takt: ${line.taktTime}s</span>
                            <span>Output: ${line.dailyActual}/${line.dailyTarget}</span>
                            <span>Status: ${line.status}</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${line.productivity}%"></div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateCNCMachines(machines) {
            const container = document.getElementById('cncGrid');
            container.innerHTML = machines.map(cnc => {
                const statusClass = cnc.status === 'running' ? 'running' : (cnc.status === 'error' ? 'error' : '');
                const icon = cnc.machineType.includes('Mill') ? '🔧' : (cnc.machineType.includes('Lathe') ? '⚙️' : '🔩');
                return `
                    <div class="cnc-item ${statusClass}">
                        <div class="cnc-icon">${icon}</div>
                        <div class="cnc-name">${cnc.name.replace('CNC ', '').substring(0, 15)}</div>
                        <div class="cnc-status">${cnc.machineType}</div>
                        <div class="cnc-load">Load: ${cnc.spindleLoad.toFixed(0)}%</div>
                    </div>
                `;
            }).join('');
        }

        function updateRobots(robots) {
            const container = document.getElementById('robotsList');
            const typeIcons = {
                'Material Handling': '🤖',
                'Welding': '⚡',
                'Assembly': '🔨',
                'Palletizing': '📦',
                'Collaborative': '🤝'
            };

            container.innerHTML = robots.map(robot => {
                const statusClass = robot.status === 'running' ? '' : 'idle';
                const icon = typeIcons[robot.robotType] || '🤖';
                return `
                    <div class="robot-item">
                        <div class="robot-icon">${icon}</div>
                        <div class="robot-info">
                            <div class="robot-name">${robot.name}</div>
                            <div class="robot-type">${robot.manufacturer} · ${robot.robotType}</div>
                        </div>
                        <div class="robot-status ${statusClass}">${robot.status}</div>
                    </div>
                `;
            }).join('');
        }

        function updateQC(qc) {
            const container = document.getElementById('qcSection');
            const defectClass = qc.defectRate < 1 ? 'good' : 'bad';

            container.innerHTML = `
                <div class="qc-summary">
                    <div class="qc-stat">
                        <div class="qc-stat-value">${formatNumber(qc.partsInspected)}</div>
                        <div class="qc-stat-label">Inspected Today</div>
                    </div>
                    <div class="qc-stat">
                        <div class="qc-stat-value ${defectClass}">${qc.defectRate.toFixed(2)}%</div>
                        <div class="qc-stat-label">Defect Rate</div>
                    </div>
                    <div class="qc-stat">
                        <div class="qc-stat-value">${qc.defectsFound}</div>
                        <div class="qc-stat-label">Defects Found</div>
                    </div>
                    <div class="qc-stat">
                        <div class="qc-stat-value">${qc.availableEquipment}/${qc.totalEquipment}</div>
                        <div class="qc-stat-label">Equipment Ready</div>
                    </div>
                </div>
            `;
        }

        function updateMaintenance(tasks) {
            const container = document.getElementById('maintenanceList');
            container.innerHTML = tasks.map(task => {
                const statusClass = task.status === 'in_progress' ? 'in_progress' : (task.priority === 'high' ? 'high' : 'scheduled');
                return `
                    <div class="maint-item ${statusClass}">
                        <div class="maint-info">
                            <div class="maint-desc">${task.description}</div>
                            <div class="maint-meta">${task.type} · ${task.scheduledDate}</div>
                        </div>
                        <div class="maint-status">${task.status}</div>
                    </div>
                `;
            }).join('');
        }

        function updateUI(data) {
            if (data.summary) updateSummary(data.summary);
            if (data.productionLines) updateProductionLines(data.productionLines);
            if (data.cncMachines) updateCNCMachines(data.cncMachines);
            if (data.robots) updateRobots(data.robots);
            if (data.qualityControl) updateQC(data.qualityControl);
            if (data.maintenance) updateMaintenance(data.maintenance);

            if (data.rspEnabled !== undefined) updateRspStatus(data.rspEnabled);
            if (data.rspAlerts) updateAlerts(data.rspAlerts);
        }

        function updateRspStatus(enabled) {
            const badge = document.getElementById('rspStatus');
            if (enabled) {
                badge.textContent = 'Active';
                badge.style.background = 'rgba(46, 204, 113, 0.2)';
                badge.style.color = '#2ecc71';
            } else {
                badge.textContent = 'Disabled';
                badge.style.background = 'rgba(136, 136, 136, 0.2)';
                badge.style.color = '#888';
            }
        }

        function updateAlerts(alerts) {
            const container = document.getElementById('alertsList');
            if (!alerts || alerts.length === 0) {
                container.innerHTML = '<div class="no-alerts">No active alerts - Factory operating normally</div>';
                return;
            }
            container.innerHTML = alerts.slice().reverse().map(alert => {
                const time = new Date(alert.timestamp).toLocaleTimeString();
                return `
                    <div class="alert-item ${alert.severity}">
                        <div class="alert-icon">${alert.icon}</div>
                        <div class="alert-content">
                            <div class="alert-type">${alert.type}</div>
                            <div class="alert-message">${alert.message}</div>
                        </div>
                        <div class="alert-time">${time}</div>
                    </div>
                `;
            }).join('');
        }

        function addNewAlerts(alerts) {
            const container = document.getElementById('alertsList');
            if (container.querySelector('.no-alerts')) container.innerHTML = '';
            alerts.forEach(alert => {
                const time = new Date(alert.timestamp).toLocaleTimeString();
                const html = `
                    <div class="alert-item ${alert.severity}">
                        <div class="alert-icon">${alert.icon}</div>
                        <div class="alert-content">
                            <div class="alert-type">${alert.type}</div>
                            <div class="alert-message">${alert.message}</div>
                        </div>
                        <div class="alert-time">${time}</div>
                    </div>
                `;
                container.insertAdjacentHTML('afterbegin', html);
            });
            while (container.children.length > 15) container.removeChild(container.lastChild);
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
                } else if (data.type === 'alerts') {
                    addNewAlerts(data.alerts);
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
    load_manufacturing_data()

    # Initialize RSP for real-time alerts
    rsp_status = setup_rsp()

    http_server = HTTPServer(('', port), WebHandler)
    http_thread = threading.Thread(target=http_server.serve_forever)
    http_thread.daemon = True
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Manufacturing Digital Twin - Web UI")
    print(f"{'='*60}")
    print(f"  Open http://localhost:{port} in your browser")
    print(f"  Factory: {factory.get('name', 'Unknown')}")
    print(f"  Production Lines: {len(production_lines)}")
    print(f"  CNC Machines: {len(cnc_machines)}")
    print(f"  Robots: {len(robots)}")
    print(f"  RSP Stream Processing: {'Enabled' if rsp_status else 'Disabled'}")
    print(f"{'='*60}\n")

    asyncio.create_task(periodic_update())

    async with websockets.serve(handle_websocket, "", ws_port):
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manufacturing Web UI")
    parser.add_argument("--port", type=int, default=8104, help="HTTP port (default: 8104)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port))
    except KeyboardInterrupt:
        print("\nShutdown requested")
