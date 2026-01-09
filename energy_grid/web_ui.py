#!/usr/bin/env python3
"""
Energy Grid Digital Twin - Interactive Web UI
==============================================

A production-grade web interface for visualizing power grid operations
including generation, transmission, distribution, and renewable energy.

Features:
- Real-time power flow visualization
- Generator status and output monitoring
- Renewable energy integration dashboard
- Battery storage status
- Transmission line monitoring
- Carbon intensity tracking
- RSP (RDF Stream Processing) real-time alerts

Usage:
    python web_ui.py [--port 8080]

Then open http://localhost:8080 in your browser.

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
grid_data: Dict[str, dict] = {}
generators: Dict[str, dict] = {}
substations: Dict[str, dict] = {}
transmission_lines: Dict[str, dict] = {}
storage_systems: Dict[str, dict] = {}
relationships: Dict[str, List[dict]] = defaultdict(list)
connected_clients: Set = set()
ws_port = 8081

# RSP state
rsp_enabled = False
rsp_query_ids: List[str] = []
rsp_source_ids: List[str] = []
rsp_alerts: List[dict] = []  # Recent alerts from RSP queries

# RSP Configuration - Continuous queries for grid monitoring
RSP_STREAM_CONFIG = {
    "type": "event_bus",
    "twin_id_patterns": ["*"],  # Monitor all twins
    "event_types": ["twin.updated", "twin.property_changed"],
}

RSP_CONTINUOUS_QUERIES = [
    {
        "name": "Frequency Deviation Alert",
        "description": "Detect grid frequency deviations outside normal range (59.95-60.05 Hz)",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?grid ?frequency
            WHERE {
                ?grid a <https://schema.org/PowerGrid> .
                ?grid dto:frequency ?frequency .
                FILTER(xsd:double(?frequency) < 59.95 || xsd:double(?frequency) > 60.05)
            }
        """,
        "window_duration": 60,
        "window_slide": 10,
        "severity": "critical",
        "icon": "⚡",
    },
    {
        "name": "Substation Overload Alert",
        "description": "Detect substations with load exceeding 85% capacity",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?substation ?load ?capacity
            WHERE {
                ?substation dto:currentLoad ?load .
                ?substation dto:capacity ?capacity .
                FILTER(CONTAINS(STR(?substation), "substation"))
                FILTER(xsd:double(?load) / xsd:double(?capacity) > 0.85)
            }
        """,
        "window_duration": 120,
        "window_slide": 30,
        "severity": "warning",
        "icon": "🔌",
    },
    {
        "name": "Transmission Line Congestion",
        "description": "Detect transmission lines with flow exceeding 80% capacity",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?line ?flow ?capacity
            WHERE {
                ?line a <https://schema.org/TransmissionLine> .
                ?line dto:currentFlow ?flow .
                ?line dto:capacity ?capacity .
                FILTER(xsd:double(?flow) / xsd:double(?capacity) > 0.80)
            }
        """,
        "window_duration": 180,
        "window_slide": 60,
        "severity": "warning",
        "icon": "🔗",
    },
    {
        "name": "Low Renewable Output",
        "description": "Detect when renewable generation drops below 30% capacity",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?generator ?output ?capacity
            WHERE {
                { ?generator a <https://schema.org/SolarFarm> }
                UNION
                { ?generator a <https://schema.org/WindFarm> }
                ?generator dto:currentOutput ?output .
                ?generator dto:capacity ?capacity .
                FILTER(xsd:double(?output) / xsd:double(?capacity) < 0.30)
            }
        """,
        "window_duration": 300,
        "window_slide": 60,
        "severity": "info",
        "icon": "🌤️",
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


def load_grid_data():
    """Load energy grid data from DTaaS."""
    global grid_data, generators, substations, transmission_lines, storage_systems, relationships

    grid_data = {}
    generators = {}
    substations = {}
    transmission_lines = {}
    storage_systems = {}
    relationships = defaultdict(list)

    try:
        twins = client.twins.list(domain="energy_grid", page_size=500)

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
            if twin_type == "PowerGrid":
                grid_data[twin_id] = item
            elif "PowerPlant" in twin_type or twin_type in ["SolarFarm", "WindFarm"]:
                generators[twin_id] = item
            elif "Substation" in twin_type:
                substations[twin_id] = item
            elif twin_type == "TransmissionLine":
                transmission_lines[twin_id] = item
            elif twin_type == "BatteryStorage":
                storage_systems[twin_id] = item

        # Load relationships for transmission lines
        for line_id in transmission_lines:
            try:
                rels = client.twins.get_relationships(line_id)
                for rel in rels:
                    rel_type = rel.get("type", "").split("#")[-1]
                    if rel_type.startswith("rel/"):
                        rel_type = rel_type[4:]
                    target = rel.get("twin", rel.get("target", ""))
                    direction = rel.get("direction", "outgoing")
                    relationships[line_id].append({
                        "type": rel_type,
                        "target": target,
                        "direction": direction
                    })
            except Exception:
                pass

        logger.info(f"Loaded grid data: {len(generators)} generators, "
                   f"{len(substations)} substations, {len(transmission_lines)} lines")

    except Exception as e:
        logger.error(f"Failed to load grid data: {e}")
        raise


def get_grid_summary() -> dict:
    """Get overall grid summary statistics."""
    total_capacity = 0
    total_output = 0
    renewable_capacity = 0
    renewable_output = 0

    for gen in generators.values():
        props = gen.get("properties", {})
        capacity = float(props.get("capacity", 0))
        output = float(props.get("currentOutput", 0))
        total_capacity += capacity
        total_output += output

        if gen["type"] in ["SolarFarm", "WindFarm", "HydroelectricPowerPlant"]:
            renewable_capacity += capacity
            renewable_output += output

    # Get grid properties
    grid_props = {}
    if grid_data:
        grid = list(grid_data.values())[0]
        grid_props = grid.get("properties", {})

    return {
        "totalCapacity": total_capacity,
        "totalOutput": total_output,
        "renewableCapacity": renewable_capacity,
        "renewableOutput": renewable_output,
        "renewablePercentage": (renewable_output / total_output * 100) if total_output > 0 else 0,
        "frequency": float(grid_props.get("frequency", 60.0)),
        "carbonIntensity": float(grid_props.get("carbonIntensity", 0)),
        "status": grid_props.get("status", "normal"),
    }


def get_generators_data() -> List[dict]:
    """Get generator data for visualization."""
    result = []
    for gen in generators.values():
        props = gen.get("properties", {})
        capacity = float(props.get("capacity", 0))
        output = float(props.get("currentOutput", 0))

        # Determine generator category
        gen_type = gen["type"]
        if gen_type == "SolarFarm":
            category = "solar"
            color = "#f1c40f"
        elif gen_type == "WindFarm":
            category = "wind"
            color = "#3498db"
        elif "Nuclear" in gen_type:
            category = "nuclear"
            color = "#9b59b6"
        elif "Hydroelectric" in gen_type:
            category = "hydro"
            color = "#1abc9c"
        elif "Coal" in gen_type:
            category = "coal"
            color = "#7f8c8d"
        else:
            category = "gas"
            color = "#e67e22"

        status = props.get("status", "generating")

        result.append({
            "id": gen["id"],
            "name": gen["name"],
            "type": gen_type,
            "category": category,
            "color": color,
            "capacity": capacity,
            "output": output,
            "utilization": (output / capacity * 100) if capacity > 0 else 0,
            "efficiency": float(props.get("efficiency", 0)),
            "emissionsFactor": float(props.get("emissionsFactor", 0)),
            "status": status,
        })

    return sorted(result, key=lambda x: -x["capacity"])


def get_substations_data() -> List[dict]:
    """Get substation data for visualization."""
    result = []
    for sub in substations.values():
        props = sub.get("properties", {})
        capacity = float(props.get("capacity", 0))
        load = float(props.get("currentLoad", 0))

        sub_type = sub["type"]
        is_hv = "HighVoltage" in sub_type

        status = props.get("status", "operational")
        load_pct = (load / capacity * 100) if capacity > 0 else 0

        result.append({
            "id": sub["id"],
            "name": sub["name"],
            "type": sub_type,
            "isHighVoltage": is_hv,
            "voltage": float(props.get("voltageLevel", props.get("inputVoltage", 0))),
            "capacity": capacity,
            "load": load,
            "loadPercentage": load_pct,
            "customersServed": int(props.get("customersServed", 0)),
            "status": status,
        })

    return sorted(result, key=lambda x: -x["capacity"])


def get_transmission_data() -> List[dict]:
    """Get transmission line data."""
    result = []
    for line in transmission_lines.values():
        props = line.get("properties", {})
        capacity = float(props.get("capacity", 0))
        flow = float(props.get("currentFlow", 0))

        # Find connected substations
        from_sub = None
        to_sub = None
        for rel in relationships.get(line["id"], []):
            if rel["type"] == "connectsFrom":
                from_sub = rel["target"]
            elif rel["type"] == "connectsTo":
                to_sub = rel["target"]

        result.append({
            "id": line["id"],
            "name": line["name"],
            "voltage": float(props.get("voltage", 0)),
            "length": float(props.get("length", 0)),
            "capacity": capacity,
            "currentFlow": flow,
            "utilization": (flow / capacity * 100) if capacity > 0 else 0,
            "temperature": float(props.get("temperature", 0)),
            "status": props.get("status", "energized"),
            "fromSubstation": from_sub,
            "toSubstation": to_sub,
        })

    return result


def get_storage_data() -> List[dict]:
    """Get battery storage data."""
    result = []
    for storage in storage_systems.values():
        props = storage.get("properties", {})

        result.append({
            "id": storage["id"],
            "name": storage["name"],
            "capacity": float(props.get("capacity", 0)),
            "power": float(props.get("power", 0)),
            "stateOfCharge": float(props.get("stateOfCharge", 0)),
            "cycleCount": int(props.get("cycleCount", 0)),
            "maxCycles": int(props.get("maxCycles", 6000)),
            "efficiency": float(props.get("roundTripEfficiency", 0)),
            "status": props.get("status", "standby"),
            "mode": props.get("mode", "grid-stabilization"),
        })

    return result


def get_full_state() -> dict:
    """Get full state for client initialization."""
    return {
        "summary": get_grid_summary(),
        "generators": get_generators_data(),
        "substations": get_substations_data(),
        "transmission": get_transmission_data(),
        "storage": get_storage_data(),
        "rspEnabled": rsp_enabled,
        "rspAlerts": rsp_alerts[-20:],  # Last 20 alerts
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
        # Check if RSP service is available
        stats = client.rsp.get_stats()
        logger.info(f"RSP service available: {stats.total_queries} queries, {stats.total_sources} sources")
    except Exception as e:
        logger.warning(f"RSP service not available: {e}")
        return False

    # Create stream source for grid events
    try:
        source = client.rsp.create_source(
            name="energy-grid-events",
            config=RSP_STREAM_CONFIG,
        )
        rsp_source_ids.append(source.id)
        logger.info(f"Created RSP stream source: {source.name} (ID: {source.id})")

        # Start the source
        client.rsp.start_source(source.id)
    except Exception as e:
        logger.warning(f"Could not create stream source (may already exist): {e}")
        # Try to use existing source
        try:
            sources = client.rsp.list_sources()
            for src in sources.sources:
                if "energy" in src.name.lower() or "grid" in src.name.lower():
                    rsp_source_ids.append(src.id)
                    logger.info(f"Using existing source: {src.name}")
                    break
        except Exception:
            pass

    if not rsp_source_ids:
        logger.warning("No RSP sources available")
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

            # Activate the query
            client.rsp.activate_query(query.id)
        except Exception as e:
            logger.warning(f"Could not create query '{query_def['name']}': {e}")
            # Try to find existing query
            try:
                queries = client.rsp.list_queries()
                for q in queries.queries:
                    if q.name == query_def["name"]:
                        rsp_query_ids.append(q.id)
                        logger.info(f"Using existing query: {q.name}")
                        break
            except Exception:
                pass

    rsp_enabled = len(rsp_query_ids) > 0
    logger.info(f"RSP enabled: {rsp_enabled} ({len(rsp_query_ids)} queries active)")
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

                        # Avoid duplicate alerts
                        if not any(a["id"] == alert["id"] for a in rsp_alerts):
                            new_alerts.append(alert)

        except Exception as e:
            logger.debug(f"Error checking query {query_id}: {e}")

    # Add new alerts and keep last 50
    rsp_alerts.extend(new_alerts)
    rsp_alerts[:] = rsp_alerts[-50:]

    return new_alerts


def format_alert_message(query_def: dict, binding: dict) -> str:
    """Format an alert message based on query type and binding data."""
    name = query_def.get("name", "Alert")

    if "Frequency" in name:
        freq = binding.get("frequency", "?")
        return f"Grid frequency deviation: {freq} Hz"
    elif "Overload" in name:
        load = binding.get("load", "?")
        capacity = binding.get("capacity", "?")
        substation = binding.get("substation", "").split(":")[-1]
        return f"Substation {substation}: {load}/{capacity} MW"
    elif "Congestion" in name:
        flow = binding.get("flow", "?")
        capacity = binding.get("capacity", "?")
        line = binding.get("line", "").split(":")[-1]
        return f"Line {line}: {flow}/{capacity} MW"
    elif "Renewable" in name:
        output = binding.get("output", "?")
        capacity = binding.get("capacity", "?")
        gen = binding.get("generator", "").split(":")[-1]
        return f"{gen}: {output}/{capacity} MW"
    else:
        return str(binding)


def get_rsp_stats() -> Optional[dict]:
    """Get RSP service statistics."""
    if not rsp_enabled:
        return None

    try:
        stats = client.rsp.get_stats()
        return {
            "totalQueries": stats.total_queries,
            "activeQueries": stats.active_queries,
            "totalSources": stats.total_sources,
            "windowEvents": stats.total_window_events,
            "resultsGenerated": stats.total_results_generated,
        }
    except Exception:
        return None


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
        # Send initial state
        await websocket.send(json.dumps({
            "type": "init",
            **get_full_state()
        }))

        async for message in websocket:
            data = json.loads(message)

            if data.get("type") == "refresh":
                load_grid_data()
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
                load_grid_data()

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


HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Energy Grid Digital Twin</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a192f 0%, #112240 100%);
            color: #e6f1ff;
            min-height: 100vh;
        }
        .header {
            background: rgba(0,0,0,0.3);
            padding: 15px 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #233554;
        }
        .header h1 {
            font-size: 1.4rem;
            font-weight: 500;
            color: #64ffda;
        }
        .header h1 span { color: #8892b0; font-weight: 300; }
        .status-badges {
            display: flex;
            gap: 15px;
        }
        .badge {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
        }
        .badge-ok { background: rgba(100, 255, 218, 0.15); color: #64ffda; }
        .badge-warning { background: rgba(241, 196, 15, 0.15); color: #f1c40f; }
        .badge-critical { background: rgba(231, 76, 60, 0.15); color: #e74c3c; animation: pulse 1s infinite; }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }

        .dashboard {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            grid-template-rows: auto auto 1fr;
            gap: 15px;
            padding: 15px;
            height: calc(100vh - 70px);
        }

        .card {
            background: rgba(17, 34, 64, 0.8);
            border-radius: 10px;
            border: 1px solid #233554;
            overflow: hidden;
        }
        .card-header {
            padding: 12px 15px;
            border-bottom: 1px solid #233554;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-header h3 {
            font-size: 0.8rem;
            color: #8892b0;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .card-body {
            padding: 15px;
            overflow-y: auto;
            max-height: calc(100% - 45px);
        }

        /* Summary Cards */
        .summary-row {
            grid-column: 1 / -1;
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 15px;
        }
        .summary-card {
            background: rgba(17, 34, 64, 0.8);
            border-radius: 10px;
            border: 1px solid #233554;
            padding: 15px;
            text-align: center;
        }
        .summary-value {
            font-size: 2rem;
            font-weight: 600;
            color: #64ffda;
        }
        .summary-value.warning { color: #f1c40f; }
        .summary-value.danger { color: #e74c3c; }
        .summary-label {
            font-size: 0.7rem;
            color: #8892b0;
            margin-top: 5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .summary-sub {
            font-size: 0.8rem;
            color: #64ffda;
            margin-top: 8px;
        }

        /* Generator Card */
        .generator-item {
            display: flex;
            align-items: center;
            padding: 10px;
            margin-bottom: 8px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            border-left: 3px solid;
            transition: all 0.2s;
        }
        .generator-item:hover {
            background: rgba(0,0,0,0.3);
        }
        .generator-item.offline {
            opacity: 0.5;
            border-left-color: #e74c3c !important;
            animation: offlinePulse 2s infinite;
        }
        @keyframes offlinePulse {
            0%, 100% { opacity: 0.5; }
            50% { opacity: 0.3; }
        }
        .gen-icon {
            width: 36px;
            height: 36px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
            margin-right: 12px;
        }
        .gen-info { flex: 1; }
        .gen-name {
            font-size: 0.85rem;
            font-weight: 500;
            color: #e6f1ff;
        }
        .gen-type {
            font-size: 0.7rem;
            color: #8892b0;
        }
        .gen-output {
            text-align: right;
        }
        .gen-power {
            font-size: 1rem;
            font-weight: 600;
            color: #64ffda;
        }
        .gen-capacity {
            font-size: 0.7rem;
            color: #8892b0;
        }

        /* Progress bar */
        .progress-bar {
            height: 4px;
            background: #233554;
            border-radius: 2px;
            margin-top: 6px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            border-radius: 2px;
            transition: width 0.5s ease;
        }

        /* Renewable Mix */
        .mix-chart {
            display: flex;
            height: 30px;
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 15px;
        }
        .mix-segment {
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7rem;
            font-weight: 500;
            color: #fff;
            transition: flex 0.5s ease;
        }
        .mix-legend {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 0.7rem;
            color: #8892b0;
        }
        .legend-dot {
            width: 10px;
            height: 10px;
            border-radius: 2px;
        }

        /* Substation List */
        .substation-item {
            display: flex;
            align-items: center;
            padding: 10px;
            margin-bottom: 8px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            transition: all 0.2s;
        }
        .substation-item:hover {
            background: rgba(0,0,0,0.3);
        }
        .substation-item.overload {
            border: 1px solid #e74c3c;
            animation: overloadPulse 1s infinite;
        }
        @keyframes overloadPulse {
            0%, 100% { box-shadow: 0 0 5px rgba(231, 76, 60, 0.3); }
            50% { box-shadow: 0 0 15px rgba(231, 76, 60, 0.6); }
        }
        .sub-icon {
            width: 32px;
            height: 32px;
            border-radius: 6px;
            background: #233554;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 10px;
        }
        .sub-info { flex: 1; }
        .sub-name {
            font-size: 0.8rem;
            font-weight: 500;
        }
        .sub-meta {
            font-size: 0.65rem;
            color: #8892b0;
        }
        .sub-load {
            text-align: right;
        }
        .load-value {
            font-size: 0.9rem;
            font-weight: 600;
        }
        .load-value.high { color: #f1c40f; }
        .load-value.critical { color: #e74c3c; }

        /* Storage Card */
        .storage-item {
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
        }
        .storage-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .storage-name {
            font-size: 0.85rem;
            font-weight: 500;
        }
        .storage-status {
            font-size: 0.65rem;
            padding: 3px 8px;
            border-radius: 10px;
            background: rgba(100, 255, 218, 0.15);
            color: #64ffda;
        }
        .storage-status.charging { background: rgba(52, 152, 219, 0.15); color: #3498db; }
        .storage-status.discharging { background: rgba(241, 196, 15, 0.15); color: #f1c40f; }
        .battery-visual {
            height: 24px;
            background: #233554;
            border-radius: 4px;
            overflow: hidden;
            position: relative;
        }
        .battery-level {
            height: 100%;
            background: linear-gradient(90deg, #64ffda, #4ecdc4);
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        .battery-text {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 0.7rem;
            font-weight: 600;
        }
        .storage-stats {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
            font-size: 0.7rem;
            color: #8892b0;
        }

        /* Transmission Lines */
        .line-item {
            display: flex;
            align-items: center;
            padding: 8px 10px;
            margin-bottom: 6px;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            font-size: 0.75rem;
        }
        .line-item.hot {
            border: 1px solid #f1c40f;
        }
        .line-name {
            flex: 1;
            font-weight: 500;
        }
        .line-flow {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .flow-bar {
            width: 60px;
            height: 6px;
            background: #233554;
            border-radius: 3px;
            overflow: hidden;
        }
        .flow-level {
            height: 100%;
            background: #64ffda;
            transition: width 0.5s, background 0.5s;
        }
        .flow-level.high { background: #f1c40f; }
        .flow-level.critical { background: #e74c3c; }

        /* Grid frequency display */
        .frequency-display {
            text-align: center;
            padding: 20px;
        }
        .freq-value {
            font-size: 3rem;
            font-weight: 300;
            color: #64ffda;
        }
        .freq-value.warning { color: #f1c40f; }
        .freq-value.danger { color: #e74c3c; animation: freqPulse 0.5s infinite; }
        @keyframes freqPulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        .freq-unit {
            font-size: 1rem;
            color: #8892b0;
        }
        .freq-indicator {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 15px;
        }
        .indicator-segment {
            width: 8px;
            height: 30px;
            border-radius: 4px;
            background: #233554;
        }
        .indicator-segment.active { background: #64ffda; }
        .indicator-segment.low { background: #e74c3c; }
        .indicator-segment.high { background: #f1c40f; }

        .generators-card { grid-row: span 2; }
        .substations-card { grid-row: span 2; }

        .refresh-btn {
            background: #233554;
            border: none;
            color: #8892b0;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.7rem;
            transition: all 0.2s;
        }
        .refresh-btn:hover {
            background: #64ffda;
            color: #0a192f;
        }

        /* RSP Alerts */
        .alerts-card {
            grid-column: 1 / -1;
        }
        .alerts-card .card-body {
            max-height: 200px;
        }
        .alert-item {
            display: flex;
            align-items: center;
            padding: 10px 12px;
            margin-bottom: 8px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
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
        .alert-icon {
            font-size: 1.2rem;
            margin-right: 12px;
        }
        .alert-content {
            flex: 1;
        }
        .alert-type {
            font-size: 0.7rem;
            font-weight: 600;
            color: #8892b0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .alert-message {
            font-size: 0.85rem;
            color: #e6f1ff;
            margin-top: 2px;
        }
        .alert-time {
            font-size: 0.65rem;
            color: #8892b0;
        }
        .rsp-badge {
            font-size: 0.6rem;
            padding: 2px 6px;
            background: rgba(100, 255, 218, 0.15);
            color: #64ffda;
            border-radius: 10px;
            margin-left: 8px;
        }
        .rsp-disabled {
            text-align: center;
            padding: 20px;
            color: #8892b0;
            font-size: 0.85rem;
        }
        .no-alerts {
            text-align: center;
            padding: 20px;
            color: #64ffda;
            font-size: 0.85rem;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Energy Grid <span>Digital Twin</span></h1>
        <div class="status-badges">
            <div id="gridStatus" class="badge badge-ok">Grid Normal</div>
            <div id="renewableBadge" class="badge badge-ok">42% Renewable</div>
        </div>
    </div>

    <div class="dashboard">
        <div class="summary-row">
            <div class="summary-card">
                <div class="summary-value" id="totalOutput">0</div>
                <div class="summary-label">Total Generation (MW)</div>
                <div class="summary-sub" id="capacityUtil">0% of capacity</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="renewableOutput">0</div>
                <div class="summary-label">Renewable (MW)</div>
                <div class="summary-sub" id="renewablePct">0% of total</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="frequency">60.00</div>
                <div class="summary-label">Grid Frequency (Hz)</div>
                <div class="summary-sub" id="freqStatus">Stable</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="carbonIntensity">0</div>
                <div class="summary-label">Carbon Intensity</div>
                <div class="summary-sub">gCO2/kWh</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="totalStorage">0</div>
                <div class="summary-label">Storage (MWh)</div>
                <div class="summary-sub" id="storageStatus">Available</div>
            </div>
        </div>

        <!-- RSP Alerts Section -->
        <div class="card alerts-card">
            <div class="card-header">
                <h3>RSP Stream Alerts <span class="rsp-badge" id="rspStatus">Connecting...</span></h3>
            </div>
            <div class="card-body" id="alertsList">
                <div class="rsp-disabled">Initializing RSP stream processing...</div>
            </div>
        </div>

        <div class="card generators-card">
            <div class="card-header">
                <h3>Power Generation</h3>
                <button class="refresh-btn" onclick="refresh()">Refresh</button>
            </div>
            <div class="card-body" id="generatorList"></div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Energy Mix</h3>
            </div>
            <div class="card-body">
                <div class="mix-chart" id="mixChart"></div>
                <div class="mix-legend" id="mixLegend"></div>
            </div>
        </div>

        <div class="card substations-card">
            <div class="card-header">
                <h3>Substations</h3>
            </div>
            <div class="card-body" id="substationList"></div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Battery Storage</h3>
            </div>
            <div class="card-body" id="storageList"></div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Transmission Lines</h3>
            </div>
            <div class="card-body" id="lineList"></div>
        </div>
    </div>

    <script>
        let ws = null;
        let state = {};

        const genIcons = {
            solar: '☀️',
            wind: '💨',
            nuclear: '⚛️',
            hydro: '💧',
            coal: '🏭',
            gas: '🔥'
        };

        function formatNumber(n, decimals = 0) {
            return new Intl.NumberFormat().format(Math.round(n * Math.pow(10, decimals)) / Math.pow(10, decimals));
        }

        function updateSummary(summary) {
            document.getElementById('totalOutput').textContent = formatNumber(summary.totalOutput);
            document.getElementById('capacityUtil').textContent =
                `${((summary.totalOutput / summary.totalCapacity) * 100).toFixed(1)}% of capacity`;

            document.getElementById('renewableOutput').textContent = formatNumber(summary.renewableOutput);
            document.getElementById('renewablePct').textContent = `${summary.renewablePercentage.toFixed(1)}% of total`;

            const freq = summary.frequency;
            const freqEl = document.getElementById('frequency');
            freqEl.textContent = freq.toFixed(2);
            freqEl.className = 'summary-value';

            const freqStatus = document.getElementById('freqStatus');
            if (freq < 59.95 || freq > 60.05) {
                freqEl.classList.add('danger');
                freqStatus.textContent = 'Critical!';
            } else if (freq < 59.98 || freq > 60.02) {
                freqEl.classList.add('warning');
                freqStatus.textContent = 'Deviation';
            } else {
                freqStatus.textContent = 'Stable';
            }

            document.getElementById('carbonIntensity').textContent = formatNumber(summary.carbonIntensity);

            // Update badges
            const gridBadge = document.getElementById('gridStatus');
            gridBadge.textContent = `Grid ${summary.status.charAt(0).toUpperCase() + summary.status.slice(1)}`;
            gridBadge.className = 'badge ' + (summary.status === 'normal' ? 'badge-ok' : 'badge-warning');

            const renewBadge = document.getElementById('renewableBadge');
            renewBadge.textContent = `${summary.renewablePercentage.toFixed(0)}% Renewable`;
        }

        function updateGenerators(generators) {
            const container = document.getElementById('generatorList');
            container.innerHTML = generators.map(gen => `
                <div class="generator-item ${gen.status !== 'generating' ? 'offline' : ''}"
                     style="border-left-color: ${gen.color}">
                    <div class="gen-icon" style="background: ${gen.color}20; color: ${gen.color}">
                        ${genIcons[gen.category] || '⚡'}
                    </div>
                    <div class="gen-info">
                        <div class="gen-name">${gen.name}</div>
                        <div class="gen-type">${gen.type.replace('PowerPlant', '')} · ${gen.efficiency}% eff</div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${gen.utilization}%; background: ${gen.color}"></div>
                        </div>
                    </div>
                    <div class="gen-output">
                        <div class="gen-power">${formatNumber(gen.output)} MW</div>
                        <div class="gen-capacity">/ ${formatNumber(gen.capacity)} MW</div>
                    </div>
                </div>
            `).join('');
        }

        function updateEnergyMix(generators) {
            const categories = {};
            let total = 0;

            generators.forEach(gen => {
                if (gen.status === 'generating') {
                    if (!categories[gen.category]) {
                        categories[gen.category] = { output: 0, color: gen.color, name: gen.category };
                    }
                    categories[gen.category].output += gen.output;
                    total += gen.output;
                }
            });

            const chart = document.getElementById('mixChart');
            const legend = document.getElementById('mixLegend');

            chart.innerHTML = Object.values(categories)
                .filter(c => c.output > 0)
                .map(c => `
                    <div class="mix-segment" style="flex: ${c.output}; background: ${c.color}">
                        ${((c.output / total) * 100).toFixed(0)}%
                    </div>
                `).join('');

            legend.innerHTML = Object.values(categories).map(c => `
                <div class="legend-item">
                    <div class="legend-dot" style="background: ${c.color}"></div>
                    ${c.name.charAt(0).toUpperCase() + c.name.slice(1)}: ${formatNumber(c.output)} MW
                </div>
            `).join('');
        }

        function updateSubstations(substations) {
            const container = document.getElementById('substationList');
            container.innerHTML = substations.map(sub => {
                const loadClass = sub.loadPercentage > 90 ? 'critical' : (sub.loadPercentage > 75 ? 'high' : '');
                const overload = sub.loadPercentage > 90 ? 'overload' : '';
                return `
                    <div class="substation-item ${overload}">
                        <div class="sub-icon">${sub.isHighVoltage ? '⚡' : '🔌'}</div>
                        <div class="sub-info">
                            <div class="sub-name">${sub.name}</div>
                            <div class="sub-meta">${sub.voltage} kV · ${sub.customersServed ? formatNumber(sub.customersServed) + ' customers' : 'HV Substation'}</div>
                        </div>
                        <div class="sub-load">
                            <div class="load-value ${loadClass}">${sub.loadPercentage.toFixed(0)}%</div>
                            <div class="progress-bar" style="width: 50px">
                                <div class="progress-fill" style="width: ${sub.loadPercentage}%; background: ${loadClass === 'critical' ? '#e74c3c' : (loadClass === 'high' ? '#f1c40f' : '#64ffda')}"></div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateStorage(storage) {
            const container = document.getElementById('storageList');
            let totalEnergy = 0;

            container.innerHTML = storage.map(s => {
                totalEnergy += s.capacity * s.stateOfCharge / 100;
                const statusClass = s.status === 'charging' ? 'charging' : (s.status === 'discharging' ? 'discharging' : '');
                return `
                    <div class="storage-item">
                        <div class="storage-header">
                            <div class="storage-name">${s.name}</div>
                            <div class="storage-status ${statusClass}">${s.status}</div>
                        </div>
                        <div class="battery-visual">
                            <div class="battery-level" style="width: ${s.stateOfCharge}%"></div>
                            <div class="battery-text">${s.stateOfCharge.toFixed(0)}%</div>
                        </div>
                        <div class="storage-stats">
                            <span>${s.capacity} MWh / ${s.power} MW</span>
                            <span>${formatNumber(s.cycleCount)} / ${formatNumber(s.maxCycles)} cycles</span>
                        </div>
                    </div>
                `;
            }).join('');

            document.getElementById('totalStorage').textContent = formatNumber(totalEnergy);
        }

        function updateTransmission(lines) {
            const container = document.getElementById('lineList');
            container.innerHTML = lines.map(line => {
                const util = line.utilization;
                const levelClass = util > 90 ? 'critical' : (util > 75 ? 'high' : '');
                const hot = util > 75 ? 'hot' : '';
                return `
                    <div class="line-item ${hot}">
                        <div class="line-name">${line.name}</div>
                        <div class="line-flow">
                            <span>${formatNumber(line.currentFlow)} MW</span>
                            <div class="flow-bar">
                                <div class="flow-level ${levelClass}" style="width: ${util}%"></div>
                            </div>
                            <span style="color: #8892b0">${util.toFixed(0)}%</span>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateUI(data) {
            if (data.summary) updateSummary(data.summary);
            if (data.generators) {
                updateGenerators(data.generators);
                updateEnergyMix(data.generators);
            }
            if (data.substations) updateSubstations(data.substations);
            if (data.storage) updateStorage(data.storage);
            if (data.transmission) updateTransmission(data.transmission);

            // Update RSP status
            if (data.rspEnabled !== undefined) {
                updateRspStatus(data.rspEnabled);
            }
            if (data.rspAlerts) {
                updateAlerts(data.rspAlerts);
            }
        }

        function updateRspStatus(enabled) {
            const badge = document.getElementById('rspStatus');
            if (enabled) {
                badge.textContent = 'Active';
                badge.style.background = 'rgba(100, 255, 218, 0.15)';
                badge.style.color = '#64ffda';
            } else {
                badge.textContent = 'Disabled';
                badge.style.background = 'rgba(136, 146, 176, 0.15)';
                badge.style.color = '#8892b0';
            }
        }

        function updateAlerts(alerts) {
            const container = document.getElementById('alertsList');

            if (!alerts || alerts.length === 0) {
                container.innerHTML = '<div class="no-alerts">No active alerts - Grid operating normally</div>';
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

            // Remove "no alerts" message if present
            if (container.querySelector('.no-alerts') || container.querySelector('.rsp-disabled')) {
                container.innerHTML = '';
            }

            alerts.forEach(alert => {
                const time = new Date(alert.timestamp).toLocaleTimeString();
                const alertHtml = `
                    <div class="alert-item ${alert.severity}">
                        <div class="alert-icon">${alert.icon}</div>
                        <div class="alert-content">
                            <div class="alert-type">${alert.type}</div>
                            <div class="alert-message">${alert.message}</div>
                        </div>
                        <div class="alert-time">${time}</div>
                    </div>
                `;
                container.insertAdjacentHTML('afterbegin', alertHtml);
            });

            // Keep only last 20 alerts
            while (container.children.length > 20) {
                container.removeChild(container.lastChild);
            }
        }

        function refresh() {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'refresh' }));
            }
        }

        function connect() {
            ws = new WebSocket(`ws://${window.location.hostname}:WS_PORT`);

            ws.onopen = () => {
                console.log('Connected');
            };

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
'''


def get_html_content():
    """Generate HTML content with current WebSocket port."""
    return HTML_TEMPLATE.replace('WS_PORT', str(ws_port))


class WebHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(get_html_content().encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


async def main(port: int):
    global client, ws_port

    ws_port = port + 1

    # Initialize client and load data
    client = get_client()
    load_grid_data()

    # Initialize RSP for real-time alerts
    rsp_status = setup_rsp()

    # Start HTTP server
    http_server = HTTPServer(('', port), WebHandler)
    http_thread = threading.Thread(target=http_server.serve_forever)
    http_thread.daemon = True
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Energy Grid Digital Twin - Web UI")
    print(f"{'='*60}")
    print(f"  Open http://localhost:{port} in your browser")
    print(f"  Generators: {len(generators)}")
    print(f"  Substations: {len(substations)}")
    print(f"  Transmission Lines: {len(transmission_lines)}")
    print(f"  Storage Systems: {len(storage_systems)}")
    print(f"  RSP Stream Processing: {'Enabled' if rsp_status else 'Disabled'}")
    print(f"{'='*60}\n")

    # Start periodic update task
    asyncio.create_task(periodic_update())

    # Start WebSocket server
    async with websockets.serve(handle_websocket, "", ws_port):
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Energy Grid Web UI")
    parser.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port))
    except KeyboardInterrupt:
        print("\nShutdown requested")
