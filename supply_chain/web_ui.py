#!/usr/bin/env python3
"""
Supply Chain Digital Twin - Interactive Web UI
===============================================

A production-grade web interface for visualizing global supply chain operations
including warehouses, fleet, shipments, and inventory.

Features:
- Global warehouse and route visualization
- Fleet tracking (trucks, ships, containers)
- Real-time shipment status
- Inventory level monitoring
- Supplier performance dashboard

Usage:
    python web_ui.py [--port 8102]

Then open http://localhost:8102 in your browser.

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
network: Dict = {}
warehouses: Dict[str, dict] = {}
suppliers: Dict[str, dict] = {}
trucks: Dict[str, dict] = {}
ships: Dict[str, dict] = {}
containers: Dict[str, dict] = {}
shipments: Dict[str, dict] = {}
inventory: Dict[str, dict] = {}
customers: Dict[str, dict] = {}
connected_clients: Set = set()
ws_port = 8103


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


def _safe_json_parse(value, default=None):
    """Safely parse a value that might be a JSON string or already a dict."""
    if default is None:
        default = {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return default


def load_supply_chain_data():
    """Load supply chain data from DTaaS."""
    global network, warehouses, suppliers, trucks, ships, containers, shipments, inventory, customers

    network = {}
    warehouses = {}
    suppliers = {}
    trucks = {}
    ships = {}
    containers = {}
    shipments = {}
    inventory = {}
    customers = {}

    try:
        twins = client.twins.list(domain="supply_chain", page_size=500)

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
            if twin_type == "SupplyChainNetwork":
                network = item
            elif twin_type == "Supplier":
                suppliers[twin_id] = item
            elif twin_type in ["DistributionCenter", "RegionalWarehouse", "FulfillmentCenter", "ImportHub"]:
                warehouses[twin_id] = item
            elif twin_type in ["SemiTruck", "DeliveryVan", "RefrigeratedTruck"]:
                trucks[twin_id] = item
            elif twin_type == "ContainerShip":
                ships[twin_id] = item
            elif twin_type in ["DryContainer", "ReeferContainer"]:
                containers[twin_id] = item
            elif "Shipment" in twin_type:
                shipments[twin_id] = item
            elif twin_type == "InventoryLevel":
                inventory[twin_id] = item
            elif twin_type == "Customer":
                customers[twin_id] = item

        logger.info(f"Loaded: {len(warehouses)} warehouses, {len(trucks)} trucks, "
                   f"{len(ships)} ships, {len(shipments)} shipments")

    except Exception as e:
        logger.error(f"Failed to load supply chain data: {e}")
        raise


def get_network_summary() -> dict:
    """Get network summary statistics."""
    props = network.get("properties", {}) if network else {}

    # Count by status
    active_shipments = sum(1 for s in shipments.values()
                          if s["properties"].get("status") == "in_transit")
    delivered = sum(1 for s in shipments.values()
                   if s["properties"].get("status") == "delivered")
    pending = sum(1 for s in shipments.values()
                 if s["properties"].get("status") == "pending")

    # Fleet status
    trucks_in_transit = sum(1 for t in trucks.values()
                           if t["properties"].get("status") == "in_transit")

    # Inventory health
    low_stock = sum(1 for inv in inventory.values()
                   if int(inv["properties"].get("quantity", 0)) <
                      int(inv["properties"].get("reorderPoint", 0)))

    return {
        "totalWarehouses": len(warehouses),
        "totalSuppliers": len(suppliers),
        "totalTrucks": len(trucks),
        "totalShips": len(ships),
        "activeShipments": active_shipments,
        "deliveredShipments": delivered,
        "pendingShipments": pending,
        "trucksInTransit": trucks_in_transit,
        "containersTracked": len(containers),
        "lowStockItems": low_stock,
    }


def get_warehouses_data() -> List[dict]:
    """Get warehouse data for visualization."""
    result = []
    for wh in warehouses.values():
        props = wh.get("properties", {})
        coords = _safe_json_parse(props.get("coordinates", {}))

        result.append({
            "id": wh["id"],
            "name": wh["name"],
            "type": wh["type"],
            "city": props.get("city", ""),
            "country": props.get("country", ""),
            "lat": coords.get("lat", 0),
            "lng": coords.get("lng", 0),
            "capacity": int(props.get("capacity", 0)),
            "utilization": float(props.get("currentUtilization", 0)),
            "employees": int(props.get("employees", 0)),
            "docks": int(props.get("docks", 0)),
            "automationLevel": props.get("automationLevel", "medium"),
            "status": props.get("status", "unknown"),
        })

    return result


def get_fleet_data() -> dict:
    """Get fleet data (trucks and ships)."""
    truck_list = []
    for truck in trucks.values():
        props = truck.get("properties", {})
        loc = _safe_json_parse(props.get("currentLocation", {}))

        truck_list.append({
            "id": truck["id"],
            "name": truck["name"],
            "type": truck["type"],
            "lat": loc.get("lat", 0),
            "lng": loc.get("lng", 0),
            "capacity": int(props.get("capacity", 0)),
            "currentLoad": float(props.get("currentLoad", 0)),
            "fuelLevel": float(props.get("fuelLevel", 0)),
            "status": props.get("status", "unknown"),
            "hasRefrigeration": props.get("hasRefrigeration", False),
        })

    ship_list = []
    for ship in ships.values():
        props = ship.get("properties", {})
        pos = _safe_json_parse(props.get("currentPosition", {}))

        ship_list.append({
            "id": ship["id"],
            "name": ship["name"],
            "lat": pos.get("lat", 0),
            "lng": pos.get("lng", 0),
            "capacity": int(props.get("capacity", 0)),
            "currentLoad": int(props.get("currentLoad", 0)),
            "speed": float(props.get("speed", 0)),
            "status": props.get("status", "unknown"),
            "route": props.get("route", ""),
            "departurePort": props.get("departurePort", ""),
            "destinationPort": props.get("destinationPort", ""),
            "eta": props.get("eta", ""),
        })

    return {
        "trucks": truck_list,
        "ships": ship_list,
    }


def get_shipments_data() -> List[dict]:
    """Get shipment data."""
    result = []
    for ship in shipments.values():
        props = ship.get("properties", {})
        result.append({
            "id": ship["id"],
            "name": ship["name"],
            "type": ship["type"],
            "origin": props.get("origin", ""),
            "destination": props.get("destination", ""),
            "status": props.get("status", "unknown"),
            "priority": props.get("priority", "standard"),
            "weight": float(props.get("weight", 0)),
            "pieces": int(props.get("pieces", 0)),
            "trackingNumber": props.get("trackingNumber", ""),
            "estimatedDelivery": props.get("estimatedDelivery", ""),
            "customsStatus": props.get("customsStatus", "pending"),
        })

    return sorted(result, key=lambda x: (x["status"] != "in_transit", x["status"] != "pending"))


def get_containers_data() -> List[dict]:
    """Get container data."""
    result = []
    for cont in containers.values():
        props = cont.get("properties", {})
        result.append({
            "id": cont["id"],
            "name": cont["name"],
            "type": cont["type"],
            "size": props.get("size", "40ft"),
            "currentWeight": float(props.get("currentWeight", 0)),
            "maxWeight": float(props.get("maxWeight", 0)),
            "isRefrigerated": props.get("isRefrigerated", False),
            "temperature": props.get("temperature"),
            "status": props.get("status", "unknown"),
            "sealNumber": props.get("sealNumber", ""),
        })

    return result


def get_inventory_data() -> List[dict]:
    """Get inventory levels."""
    result = []
    for inv in inventory.values():
        props = inv.get("properties", {})
        qty = int(props.get("quantity", 0))
        reorder = int(props.get("reorderPoint", 0))
        max_qty = int(props.get("maxQuantity", 1))

        health = "good"
        if qty < reorder:
            health = "low"
        elif qty > max_qty * 0.9:
            health = "overstocked"

        result.append({
            "id": inv["id"],
            "name": inv["name"],
            "quantity": qty,
            "reorderPoint": reorder,
            "maxQuantity": max_qty,
            "utilization": (qty / max_qty * 100) if max_qty > 0 else 0,
            "health": health,
            "status": props.get("status", "adequate"),
        })

    return sorted(result, key=lambda x: (x["health"] != "low", x["utilization"]))


def get_suppliers_data() -> List[dict]:
    """Get supplier data."""
    result = []
    for supp in suppliers.values():
        props = supp.get("properties", {})
        result.append({
            "id": supp["id"],
            "name": supp["name"],
            "country": props.get("country", ""),
            "city": props.get("city", ""),
            "category": props.get("category", ""),
            "rating": float(props.get("rating", 0)),
            "onTimeDeliveryRate": float(props.get("onTimeDeliveryRate", 0)),
            "qualityScore": float(props.get("qualityScore", 0)),
            "leadTimeDays": int(props.get("leadTimeDays", 0)),
            "status": props.get("status", "unknown"),
        })

    return sorted(result, key=lambda x: -x["rating"])


def get_full_state() -> dict:
    """Get full state for client initialization."""
    return {
        "summary": get_network_summary(),
        "warehouses": get_warehouses_data(),
        "fleet": get_fleet_data(),
        "shipments": get_shipments_data(),
        "containers": get_containers_data(),
        "inventory": get_inventory_data(),
        "suppliers": get_suppliers_data(),
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
                load_supply_chain_data()
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
                load_supply_chain_data()
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
    <title>Supply Chain Digital Twin</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
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
            color: #00d4aa;
        }
        .header h1 span { color: #888; font-weight: 300; }

        .dashboard {
            display: grid;
            grid-template-columns: 1fr 1fr 320px;
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
            color: #00d4aa;
        }
        .summary-value.warning { color: #f1c40f; }
        .summary-value.danger { color: #e74c3c; }
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

        /* Warehouse Map */
        .map-container {
            position: relative;
            background: #0a0a1a;
            border-radius: 8px;
            height: 100%;
            min-height: 200px;
            overflow: hidden;
        }
        .world-map {
            position: absolute;
            width: 100%;
            height: 100%;
            opacity: 0.3;
            background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1000 500'%3E%3Crect fill='%23111' width='1000' height='500'/%3E%3Cpath fill='%23333' d='M200 150 L300 140 L320 180 L280 220 L220 200 Z M400 100 L500 90 L520 150 L480 200 L420 180 Z M600 120 L700 100 L740 160 L680 220 L620 180 Z M150 280 L250 260 L270 320 L230 360 L170 340 Z M500 250 L600 230 L640 290 L580 350 L520 320 Z M750 200 L850 180 L880 240 L820 300 L760 260 Z'/%3E%3C/svg%3E");
            background-size: cover;
        }
        .map-point {
            position: absolute;
            transform: translate(-50%, -50%);
            cursor: pointer;
            transition: all 0.2s;
        }
        .map-point:hover { transform: translate(-50%, -50%) scale(1.3); }
        .map-point.warehouse {
            width: 12px;
            height: 12px;
            background: #00d4aa;
            border-radius: 50%;
            box-shadow: 0 0 10px rgba(0, 212, 170, 0.5);
        }
        .map-point.ship {
            width: 10px;
            height: 10px;
            background: #3498db;
            border-radius: 50%;
            animation: shipPulse 2s infinite;
        }
        @keyframes shipPulse {
            0%, 100% { box-shadow: 0 0 5px rgba(52, 152, 219, 0.5); }
            50% { box-shadow: 0 0 15px rgba(52, 152, 219, 0.8); }
        }
        .map-point.truck {
            width: 8px;
            height: 8px;
            background: #f1c40f;
            border-radius: 2px;
        }

        /* Shipment List */
        .shipment-item {
            display: flex;
            align-items: center;
            padding: 10px;
            margin-bottom: 8px;
            background: rgba(0,0,0,0.3);
            border-radius: 8px;
            border-left: 3px solid #333;
        }
        .shipment-item.in_transit { border-left-color: #3498db; }
        .shipment-item.delivered { border-left-color: #2ecc71; }
        .shipment-item.pending { border-left-color: #f1c40f; }
        .shipment-item.delayed { border-left-color: #e74c3c; animation: delayPulse 1s infinite; }
        @keyframes delayPulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        .shipment-icon {
            width: 32px;
            height: 32px;
            background: #222;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 10px;
            font-size: 0.9rem;
        }
        .shipment-info { flex: 1; }
        .shipment-route {
            font-size: 0.75rem;
            font-weight: 500;
        }
        .shipment-meta {
            font-size: 0.6rem;
            color: #888;
            margin-top: 2px;
        }
        .shipment-status {
            font-size: 0.6rem;
            padding: 3px 8px;
            border-radius: 10px;
            text-transform: uppercase;
            font-weight: 500;
        }
        .status-in_transit { background: rgba(52, 152, 219, 0.2); color: #3498db; }
        .status-delivered { background: rgba(46, 204, 113, 0.2); color: #2ecc71; }
        .status-pending { background: rgba(241, 196, 15, 0.2); color: #f1c40f; }

        /* Fleet Status */
        .fleet-section { margin-bottom: 15px; }
        .fleet-title {
            font-size: 0.7rem;
            color: #888;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .fleet-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
            gap: 8px;
        }
        .fleet-item {
            background: rgba(0,0,0,0.3);
            border-radius: 6px;
            padding: 10px;
            text-align: center;
            border: 1px solid #333;
        }
        .fleet-item.active { border-color: #00d4aa; }
        .fleet-item.idle { opacity: 0.6; }
        .fleet-icon { font-size: 1.2rem; margin-bottom: 5px; }
        .fleet-name { font-size: 0.65rem; color: #ccc; }
        .fleet-load {
            font-size: 0.55rem;
            color: #888;
            margin-top: 3px;
        }

        /* Inventory */
        .inventory-item {
            display: flex;
            align-items: center;
            padding: 8px 10px;
            margin-bottom: 6px;
            background: rgba(0,0,0,0.3);
            border-radius: 6px;
        }
        .inventory-item.low { border-left: 3px solid #e74c3c; }
        .inventory-item.overstocked { border-left: 3px solid #f1c40f; }
        .inventory-info { flex: 1; }
        .inventory-name {
            font-size: 0.7rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .inventory-bar {
            width: 60px;
            height: 6px;
            background: #222;
            border-radius: 3px;
            overflow: hidden;
            margin-left: 10px;
        }
        .inventory-level {
            height: 100%;
            background: #00d4aa;
            transition: width 0.5s;
        }
        .inventory-level.low { background: #e74c3c; }
        .inventory-level.overstocked { background: #f1c40f; }
        .inventory-qty {
            font-size: 0.65rem;
            color: #888;
            width: 50px;
            text-align: right;
        }

        /* Suppliers */
        .supplier-item {
            display: flex;
            align-items: center;
            padding: 10px;
            margin-bottom: 8px;
            background: rgba(0,0,0,0.3);
            border-radius: 6px;
        }
        .supplier-rating {
            width: 40px;
            height: 40px;
            background: #222;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.9rem;
            font-weight: 600;
            color: #00d4aa;
            margin-right: 10px;
        }
        .supplier-info { flex: 1; }
        .supplier-name { font-size: 0.8rem; font-weight: 500; }
        .supplier-meta { font-size: 0.6rem; color: #888; }
        .supplier-stats {
            display: flex;
            gap: 8px;
            font-size: 0.55rem;
            color: #888;
        }
        .stat-good { color: #2ecc71; }

        .refresh-btn {
            background: #222;
            border: none;
            color: #888;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.65rem;
        }
        .refresh-btn:hover {
            background: #00d4aa;
            color: #000;
        }

        .tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 10px;
        }
        .tab {
            padding: 5px 10px;
            background: #222;
            border: none;
            border-radius: 4px;
            color: #888;
            font-size: 0.65rem;
            cursor: pointer;
        }
        .tab.active {
            background: #00d4aa;
            color: #000;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Supply Chain <span>Digital Twin</span></h1>
        <button class="refresh-btn" onclick="refresh()">Refresh Data</button>
    </div>

    <div class="dashboard">
        <div class="summary-row">
            <div class="summary-card">
                <div class="summary-value" id="activeShipments">0</div>
                <div class="summary-label">Active Shipments</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="trucksInTransit">0</div>
                <div class="summary-label">Trucks In Transit</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="totalShips">0</div>
                <div class="summary-label">Ships At Sea</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="totalWarehouses">0</div>
                <div class="summary-label">Warehouses</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="containersTracked">0</div>
                <div class="summary-label">Containers</div>
            </div>
            <div class="summary-card">
                <div class="summary-value" id="lowStockItems">0</div>
                <div class="summary-label">Low Stock Alerts</div>
            </div>
        </div>

        <div class="card" style="grid-column: 1 / 3;">
            <div class="card-header">
                <h3>Global Network</h3>
            </div>
            <div class="card-body" style="padding: 0;">
                <div class="map-container" id="mapContainer">
                    <div class="world-map"></div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Shipments</h3>
            </div>
            <div class="card-body" id="shipmentList"></div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Fleet Status</h3>
            </div>
            <div class="card-body" id="fleetStatus"></div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Inventory Levels</h3>
            </div>
            <div class="card-body" id="inventoryList"></div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3>Top Suppliers</h3>
            </div>
            <div class="card-body" id="supplierList"></div>
        </div>
    </div>

    <script>
        let ws = null;
        let state = {};

        function formatNumber(n) {
            return new Intl.NumberFormat().format(Math.round(n));
        }

        function latLngToPercent(lat, lng) {
            // Simple mercator-ish projection
            const x = ((lng + 180) / 360) * 100;
            const y = ((90 - lat) / 180) * 100;
            return { x: Math.max(5, Math.min(95, x)), y: Math.max(5, Math.min(95, y)) };
        }

        function updateSummary(summary) {
            document.getElementById('activeShipments').textContent = summary.activeShipments;
            document.getElementById('trucksInTransit').textContent = summary.trucksInTransit;
            document.getElementById('totalShips').textContent = summary.totalShips;
            document.getElementById('totalWarehouses').textContent = summary.totalWarehouses;
            document.getElementById('containersTracked').textContent = summary.containersTracked;

            const lowStock = document.getElementById('lowStockItems');
            lowStock.textContent = summary.lowStockItems;
            lowStock.className = 'summary-value' + (summary.lowStockItems > 0 ? ' danger' : '');
        }

        function updateMap(warehouses, fleet) {
            const container = document.getElementById('mapContainer');
            // Keep world map background
            const worldMap = container.querySelector('.world-map');
            container.innerHTML = '';
            container.appendChild(worldMap);

            // Add warehouses
            warehouses.forEach(wh => {
                const pos = latLngToPercent(wh.lat, wh.lng);
                const point = document.createElement('div');
                point.className = 'map-point warehouse';
                point.style.left = pos.x + '%';
                point.style.top = pos.y + '%';
                point.title = `${wh.name}\\n${wh.city}, ${wh.country}\\nUtilization: ${wh.utilization}%`;
                container.appendChild(point);
            });

            // Add ships
            fleet.ships.forEach(ship => {
                const pos = latLngToPercent(ship.lat, ship.lng);
                const point = document.createElement('div');
                point.className = 'map-point ship';
                point.style.left = pos.x + '%';
                point.style.top = pos.y + '%';
                point.title = `${ship.name}\\n${ship.departurePort} → ${ship.destinationPort}\\nLoad: ${ship.currentLoad}/${ship.capacity} TEU`;
                container.appendChild(point);
            });

            // Add trucks (only in transit)
            fleet.trucks.filter(t => t.status === 'in_transit').forEach(truck => {
                const pos = latLngToPercent(truck.lat, truck.lng);
                const point = document.createElement('div');
                point.className = 'map-point truck';
                point.style.left = pos.x + '%';
                point.style.top = pos.y + '%';
                point.title = `${truck.name}\\nLoad: ${Math.round(truck.currentLoad/1000)}t\\nFuel: ${truck.fuelLevel}%`;
                container.appendChild(point);
            });
        }

        function updateShipments(shipments) {
            const container = document.getElementById('shipmentList');
            const icons = {
                'InboundShipment': '📥',
                'OutboundShipment': '📤',
                'TransferShipment': '🔄'
            };

            container.innerHTML = shipments.slice(0, 10).map(ship => `
                <div class="shipment-item ${ship.status}">
                    <div class="shipment-icon">${icons[ship.type] || '📦'}</div>
                    <div class="shipment-info">
                        <div class="shipment-route">${ship.origin.split('-').pop()} → ${ship.destination.split('-').pop()}</div>
                        <div class="shipment-meta">${ship.trackingNumber} · ${formatNumber(ship.weight)}kg · ${ship.pieces} pcs</div>
                    </div>
                    <div class="shipment-status status-${ship.status}">${ship.status.replace('_', ' ')}</div>
                </div>
            `).join('');
        }

        function updateFleet(fleet) {
            const container = document.getElementById('fleetStatus');

            let html = '<div class="fleet-section">';
            html += '<div class="fleet-title">Ships (' + fleet.ships.length + ')</div>';
            html += '<div class="fleet-grid">';
            fleet.ships.forEach(ship => {
                const loadPct = Math.round((ship.currentLoad / ship.capacity) * 100);
                html += `
                    <div class="fleet-item ${ship.status === 'at_sea' ? 'active' : 'idle'}">
                        <div class="fleet-icon">🚢</div>
                        <div class="fleet-name">${ship.name.split(' ').pop()}</div>
                        <div class="fleet-load">${loadPct}% loaded</div>
                    </div>
                `;
            });
            html += '</div></div>';

            html += '<div class="fleet-section">';
            html += '<div class="fleet-title">Trucks (' + fleet.trucks.length + ')</div>';
            html += '<div class="fleet-grid">';
            fleet.trucks.slice(0, 12).forEach(truck => {
                const icon = truck.hasRefrigeration ? '🧊' : (truck.type === 'DeliveryVan' ? '🚐' : '🚛');
                html += `
                    <div class="fleet-item ${truck.status === 'in_transit' ? 'active' : 'idle'}">
                        <div class="fleet-icon">${icon}</div>
                        <div class="fleet-name">${truck.name.split('-').pop()}</div>
                        <div class="fleet-load">${truck.fuelLevel}% fuel</div>
                    </div>
                `;
            });
            html += '</div></div>';

            container.innerHTML = html;
        }

        function updateInventory(inventory) {
            const container = document.getElementById('inventoryList');

            container.innerHTML = inventory.slice(0, 10).map(inv => {
                const levelClass = inv.health === 'low' ? 'low' : (inv.health === 'overstocked' ? 'overstocked' : '');
                return `
                    <div class="inventory-item ${levelClass}">
                        <div class="inventory-info">
                            <div class="inventory-name">${inv.name.replace('Inventory ', '').replace(' at ', ' @ ')}</div>
                        </div>
                        <div class="inventory-bar">
                            <div class="inventory-level ${levelClass}" style="width: ${Math.min(100, inv.utilization)}%"></div>
                        </div>
                        <div class="inventory-qty">${formatNumber(inv.quantity)}</div>
                    </div>
                `;
            }).join('');
        }

        function updateSuppliers(suppliers) {
            const container = document.getElementById('supplierList');

            container.innerHTML = suppliers.slice(0, 5).map(supp => `
                <div class="supplier-item">
                    <div class="supplier-rating">${supp.rating.toFixed(1)}</div>
                    <div class="supplier-info">
                        <div class="supplier-name">${supp.name}</div>
                        <div class="supplier-meta">${supp.city}, ${supp.country} · ${supp.category}</div>
                        <div class="supplier-stats">
                            <span class="${supp.onTimeDeliveryRate > 90 ? 'stat-good' : ''}">OTD: ${supp.onTimeDeliveryRate}%</span>
                            <span class="${supp.qualityScore > 95 ? 'stat-good' : ''}">Quality: ${supp.qualityScore}%</span>
                            <span>Lead: ${supp.leadTimeDays}d</span>
                        </div>
                    </div>
                </div>
            `).join('');
        }

        function updateUI(data) {
            state = data;
            if (data.summary) updateSummary(data.summary);
            if (data.warehouses && data.fleet) updateMap(data.warehouses, data.fleet);
            if (data.shipments) updateShipments(data.shipments);
            if (data.fleet) updateFleet(data.fleet);
            if (data.inventory) updateInventory(data.inventory);
            if (data.suppliers) updateSuppliers(data.suppliers);
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
    load_supply_chain_data()

    http_server = HTTPServer(('', port), WebHandler)
    http_thread = threading.Thread(target=http_server.serve_forever)
    http_thread.daemon = True
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Supply Chain Digital Twin - Web UI")
    print(f"{'='*60}")
    print(f"  Open http://localhost:{port} in your browser")
    print(f"  Warehouses: {len(warehouses)}")
    print(f"  Trucks: {len(trucks)}")
    print(f"  Ships: {len(ships)}")
    print(f"  Shipments: {len(shipments)}")
    print(f"{'='*60}\n")

    asyncio.create_task(periodic_update())

    async with websockets.serve(handle_websocket, "", ws_port):
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Supply Chain Web UI")
    parser.add_argument("--port", type=int, default=8102, help="HTTP port (default: 8102)")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.port))
    except KeyboardInterrupt:
        print("\nShutdown requested")
