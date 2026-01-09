#!/usr/bin/env python3
"""
Supply Chain / Logistics Digital Twin Example

This example creates a comprehensive digital twin of a global supply chain,
including warehouses, distribution centers, trucks, ships, and shipments.

Domain: Supply Chain / Logistics
Use Cases:
  - Real-time shipment tracking
  - Inventory optimization
  - Route optimization
  - Demand forecasting
  - Supplier performance monitoring
  - Carbon footprint tracking
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import (
    get_client, print_summary, logger,
    bulk_create_twins, bulk_add_relationships,
    DOMAIN_NAMESPACES
)

# Domain for this seed script
DOMAIN = "supply_chain"
SUPPLY_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_supply_chain_twin(data: dict) -> dict:
    """Prepare a twin dict for the supply_chain domain with proper namespace.

    Returns the dict without making any API calls.
    """
    # Expand type to full URI if it's a short name
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{SUPPLY_NS}{twin_type}"

    # Add domain tag
    data["domain"] = DOMAIN

    return data


def seed_supply_chain():
    """Seed the supply chain digital twin."""
    client = get_client()

    # Collect all twins and relationships for bulk operations
    all_twins = []
    all_relationships = []

    # =========================================================================
    # SUPPLY CHAIN NETWORK
    # =========================================================================
    all_twins.append(prepare_supply_chain_twin({
        "id": "supply-chain-global",
        "type": "SupplyChainNetwork",
        "name": "Global Distribution Network",
        "description": "End-to-end supply chain from suppliers to customers",
        "properties": {
            "regions": ["North America", "Europe", "Asia Pacific"],
            "totalWarehouses": 12,
            "totalVehicles": 450,
            "annualShipments": 2500000,
            "headquarters": "Chicago, IL, USA"
        }
    }))

    # =========================================================================
    # SUPPLIERS
    # =========================================================================
    suppliers = [
        {"id": "supplier-china-001", "name": "Shanghai Electronics Co.", "country": "China", "city": "Shanghai", "category": "Electronics"},
        {"id": "supplier-china-002", "name": "Shenzhen Components Ltd.", "country": "China", "city": "Shenzhen", "category": "Components"},
        {"id": "supplier-germany-001", "name": "Munich Precision GmbH", "country": "Germany", "city": "Munich", "category": "Machinery"},
        {"id": "supplier-japan-001", "name": "Tokyo Tech Industries", "country": "Japan", "city": "Tokyo", "category": "Electronics"},
        {"id": "supplier-mexico-001", "name": "Monterrey Manufacturing", "country": "Mexico", "city": "Monterrey", "category": "Assembly"},
        {"id": "supplier-usa-001", "name": "Detroit Parts Inc.", "country": "USA", "city": "Detroit", "category": "Automotive"},
    ]

    for supp in suppliers:
        all_twins.append(prepare_supply_chain_twin({
            "id": supp["id"],
            "type": "Supplier",
            "name": supp["name"],
            "properties": {
                "country": supp["country"],
                "city": supp["city"],
                "category": supp["category"],
                "rating": 4.5,
                "onTimeDeliveryRate": 94.5,
                "qualityScore": 98.2,
                "leadTimeDays": 14,
                "certifications": ["ISO 9001", "ISO 14001"],
                "status": "active"
            }
        }))
        all_relationships.append(("supply-chain-global", "hasSupplier", supp["id"], None))

    # =========================================================================
    # WAREHOUSES & DISTRIBUTION CENTERS
    # =========================================================================
    warehouses = [
        {"id": "warehouse-la", "name": "Los Angeles Distribution Center", "type": "DistributionCenter", "city": "Los Angeles", "country": "USA", "area": 50000, "lat": 33.9425, "lng": -118.4081},
        {"id": "warehouse-chicago", "name": "Chicago Regional Warehouse", "type": "RegionalWarehouse", "city": "Chicago", "country": "USA", "area": 75000, "lat": 41.8781, "lng": -87.6298},
        {"id": "warehouse-newark", "name": "Newark East Coast Hub", "type": "DistributionCenter", "city": "Newark", "country": "USA", "area": 60000, "lat": 40.7357, "lng": -74.1724},
        {"id": "warehouse-dallas", "name": "Dallas Regional Warehouse", "type": "RegionalWarehouse", "city": "Dallas", "country": "USA", "area": 45000, "lat": 32.7767, "lng": -96.7970},
        {"id": "warehouse-rotterdam", "name": "Rotterdam European Hub", "type": "DistributionCenter", "city": "Rotterdam", "country": "Netherlands", "area": 80000, "lat": 51.9244, "lng": 4.4777},
        {"id": "warehouse-frankfurt", "name": "Frankfurt Fulfillment Center", "type": "FulfillmentCenter", "city": "Frankfurt", "country": "Germany", "area": 35000, "lat": 50.1109, "lng": 8.6821},
        {"id": "warehouse-shanghai", "name": "Shanghai Import Hub", "type": "ImportHub", "city": "Shanghai", "country": "China", "area": 100000, "lat": 31.2304, "lng": 121.4737},
        {"id": "warehouse-singapore", "name": "Singapore APAC Hub", "type": "DistributionCenter", "city": "Singapore", "country": "Singapore", "area": 55000, "lat": 1.3521, "lng": 103.8198},
    ]

    for wh in warehouses:
        all_twins.append(prepare_supply_chain_twin({
            "id": wh["id"],
            "type": wh["type"],
            "name": wh["name"],
            "properties": {
                "city": wh["city"],
                "country": wh["country"],
                "area": wh["area"],
                "areaUnit": "sqm",
                "coordinates": {"lat": wh["lat"], "lng": wh["lng"]},
                "capacity": wh["area"] * 10,
                "capacityUnit": "pallets",
                "currentUtilization": 78,
                "employees": wh["area"] // 200,
                "docks": wh["area"] // 2500,
                "operatingHours": "24/7",
                "temperature": {
                    "ambient": {"min": 15, "max": 25},
                    "coldStorage": {"min": -25, "max": 5},
                    "freezer": {"min": -25, "max": -18}
                },
                "automationLevel": "high" if wh["area"] > 60000 else "medium",
                "status": "operational"
            }
        }))
        all_relationships.append(("supply-chain-global", "hasWarehouse", wh["id"], None))

    # Warehouse connections (supply routes)
    routes = [
        ("warehouse-shanghai", "warehouse-la", "transPacific"),
        ("warehouse-shanghai", "warehouse-rotterdam", "maritime"),
        ("warehouse-la", "warehouse-chicago", "rail"),
        ("warehouse-la", "warehouse-dallas", "truck"),
        ("warehouse-chicago", "warehouse-newark", "truck"),
        ("warehouse-rotterdam", "warehouse-frankfurt", "truck"),
        ("warehouse-singapore", "warehouse-shanghai", "maritime"),
    ]
    for src, dst, mode in routes:
        all_relationships.append((src, f"suppliesTo_{mode}", dst, None))

    # =========================================================================
    # INVENTORY ZONES (per warehouse)
    # =========================================================================
    for wh in warehouses[:3]:  # Just first 3 for brevity
        zones = [
            {"zone": "receiving", "name": "Receiving Dock"},
            {"zone": "bulk", "name": "Bulk Storage"},
            {"zone": "pick", "name": "Pick Zone"},
            {"zone": "pack", "name": "Pack Station"},
            {"zone": "ship", "name": "Shipping Dock"},
            {"zone": "cold", "name": "Cold Storage"},
        ]
        for zone in zones:
            zone_id = f"{wh['id']}-zone-{zone['zone']}"
            all_twins.append(prepare_supply_chain_twin({
                "id": zone_id,
                "type": "WarehouseZone",
                "name": f"{zone['name']} - {wh['name']}",
                "properties": {
                    "zoneType": zone["zone"],
                    "capacity": 1000,
                    "currentOccupancy": 750,
                    "temperature": -18 if zone["zone"] == "cold" else 20,
                    "status": "active"
                }
            }))
            all_relationships.append((wh["id"], "hasZone", zone_id, None))

    # =========================================================================
    # FLEET - TRUCKS
    # =========================================================================
    trucks = [
        {"id": "truck-001", "name": "Truck CHI-001", "type": "SemiTruck", "homeBase": "warehouse-chicago", "capacity": 22000},
        {"id": "truck-002", "name": "Truck CHI-002", "type": "SemiTruck", "homeBase": "warehouse-chicago", "capacity": 22000},
        {"id": "truck-003", "name": "Truck CHI-003", "type": "SemiTruck", "homeBase": "warehouse-chicago", "capacity": 22000},
        {"id": "truck-004", "name": "Truck LA-001", "type": "SemiTruck", "homeBase": "warehouse-la", "capacity": 22000},
        {"id": "truck-005", "name": "Truck LA-002", "type": "SemiTruck", "homeBase": "warehouse-la", "capacity": 22000},
        {"id": "truck-006", "name": "Truck NYC-001", "type": "SemiTruck", "homeBase": "warehouse-newark", "capacity": 22000},
        {"id": "truck-007", "name": "Truck DAL-001", "type": "SemiTruck", "homeBase": "warehouse-dallas", "capacity": 22000},
        {"id": "truck-008", "name": "Delivery Van CHI-001", "type": "DeliveryVan", "homeBase": "warehouse-chicago", "capacity": 2000},
        {"id": "truck-009", "name": "Delivery Van CHI-002", "type": "DeliveryVan", "homeBase": "warehouse-chicago", "capacity": 2000},
        {"id": "truck-010", "name": "Refrigerated Truck CHI-001", "type": "RefrigeratedTruck", "homeBase": "warehouse-chicago", "capacity": 18000},
    ]

    for truck in trucks:
        all_twins.append(prepare_supply_chain_twin({
            "id": truck["id"],
            "type": truck["type"],
            "name": truck["name"],
            "properties": {
                "capacity": truck["capacity"],
                "capacityUnit": "kg",
                "manufacturer": "Freightliner" if truck["type"] == "SemiTruck" else ("Ford" if truck["type"] == "DeliveryVan" else "Carrier"),
                "model": "Cascadia" if truck["type"] == "SemiTruck" else "Transit",
                "year": 2022,
                "fuelType": "diesel",
                "currentLocation": {"lat": 41.8781, "lng": -87.6298},
                "status": "in_transit",
                "currentLoad": truck["capacity"] * 0.8,
                "mileage": 125000,
                "mileageUnit": "miles",
                "fuelLevel": 75,
                "nextMaintenance": "2026-01-15",
                "driverAssigned": True,
                "hasTelematics": True,
                "hasRefrigeration": truck["type"] == "RefrigeratedTruck"
            }
        }))
        all_relationships.append((truck["id"], "basedAt", truck["homeBase"], None))

    # =========================================================================
    # FLEET - SHIPS
    # =========================================================================
    ships = [
        {"id": "ship-001", "name": "MV Pacific Star", "type": "ContainerShip", "capacity": 8000, "route": "transPacific"},
        {"id": "ship-002", "name": "MV Atlantic Voyager", "type": "ContainerShip", "capacity": 6000, "route": "transAtlantic"},
        {"id": "ship-003", "name": "MV Asia Express", "type": "ContainerShip", "capacity": 10000, "route": "asiaPacific"},
    ]

    for ship in ships:
        all_twins.append(prepare_supply_chain_twin({
            "id": ship["id"],
            "type": ship["type"],
            "name": ship["name"],
            "properties": {
                "capacity": ship["capacity"],
                "capacityUnit": "TEU",
                "currentLoad": int(ship["capacity"] * 0.85),
                "route": ship["route"],
                "flag": "Panama",
                "imo": f"IMO{9800000 + int(ship['id'][-3:])}",
                "currentPosition": {"lat": 35.0, "lng": -140.0},
                "speed": 18,
                "speedUnit": "knots",
                "status": "at_sea",
                "eta": "2024-12-20T08:00:00Z",
                "departurePort": "Shanghai",
                "destinationPort": "Los Angeles"
            }
        }))
        all_relationships.append(("supply-chain-global", "hasVessel", ship["id"], None))

    # =========================================================================
    # CONTAINERS
    # =========================================================================
    containers = [
        {"id": "container-001", "type": "DryContainer", "size": "40ft", "ship": "ship-001"},
        {"id": "container-002", "type": "DryContainer", "size": "40ft", "ship": "ship-001"},
        {"id": "container-003", "type": "ReeferContainer", "size": "40ft", "ship": "ship-001"},
        {"id": "container-004", "type": "DryContainer", "size": "20ft", "ship": "ship-002"},
        {"id": "container-005", "type": "DryContainer", "size": "40ft", "warehouse": "warehouse-la"},
        {"id": "container-006", "type": "DryContainer", "size": "40ft", "warehouse": "warehouse-rotterdam"},
    ]

    for cont in containers:
        all_twins.append(prepare_supply_chain_twin({
            "id": cont["id"],
            "type": cont["type"],
            "name": f"Container {cont['id'][-3:]}",
            "properties": {
                "size": cont["size"],
                "maxWeight": 30480 if cont["size"] == "40ft" else 21770,
                "weightUnit": "kg",
                "tareWeight": 3800 if cont["size"] == "40ft" else 2200,
                "currentWeight": 25000 if cont["size"] == "40ft" else 18000,
                "isRefrigerated": cont["type"] == "ReeferContainer",
                "temperature": -18 if cont["type"] == "ReeferContainer" else None,
                "sealNumber": f"SEAL{cont['id'][-3:]}2024",
                "status": "in_transit" if "ship" in cont else "at_warehouse"
            }
        }))
        if "ship" in cont:
            all_relationships.append((cont["id"], "loadedOn", cont["ship"], None))
        else:
            all_relationships.append((cont["id"], "locatedAt", cont["warehouse"], None))

    # =========================================================================
    # SHIPMENTS / ORDERS
    # =========================================================================
    shipments = [
        {"id": "shipment-001", "type": "InboundShipment", "origin": "supplier-china-001", "destination": "warehouse-la", "status": "in_transit"},
        {"id": "shipment-002", "type": "InboundShipment", "origin": "supplier-germany-001", "destination": "warehouse-rotterdam", "status": "delivered"},
        {"id": "shipment-003", "type": "OutboundShipment", "origin": "warehouse-chicago", "destination": "customer-ny", "status": "in_transit"},
        {"id": "shipment-004", "type": "OutboundShipment", "origin": "warehouse-la", "destination": "customer-seattle", "status": "pending"},
        {"id": "shipment-005", "type": "TransferShipment", "origin": "warehouse-la", "destination": "warehouse-chicago", "status": "in_transit"},
        {"id": "shipment-006", "type": "InboundShipment", "origin": "supplier-japan-001", "destination": "warehouse-shanghai", "status": "pending"},
    ]

    for ship_item in shipments:
        all_twins.append(prepare_supply_chain_twin({
            "id": ship_item["id"],
            "type": ship_item["type"],
            "name": f"Shipment {ship_item['id'][-3:]}",
            "properties": {
                "origin": ship_item["origin"],
                "destination": ship_item["destination"],
                "status": ship_item["status"],
                "priority": "standard",
                "weight": 15000,
                "weightUnit": "kg",
                "pieces": 450,
                "createdAt": "2024-12-10T08:00:00Z",
                "estimatedDelivery": "2024-12-18T18:00:00Z",
                "trackingNumber": f"TRK{ship_item['id'][-3:]}2024DEC",
                "incoterms": "DDP",
                "customsStatus": "cleared" if ship_item["status"] != "pending" else "pending"
            }
        }))
        all_relationships.append((ship_item["id"], "originatesFrom", ship_item["origin"], None))
        all_relationships.append((ship_item["id"], "destinedFor", ship_item["destination"], None))

    # Link shipments to vehicles
    all_relationships.append(("shipment-001", "transportedBy", "ship-001", None))
    all_relationships.append(("shipment-003", "transportedBy", "truck-001", None))
    all_relationships.append(("shipment-005", "transportedBy", "truck-004", None))

    # =========================================================================
    # PRODUCTS / SKUs
    # =========================================================================
    products = [
        {"id": "sku-001", "name": "Laptop Computer Model X", "category": "Electronics", "weight": 2.5},
        {"id": "sku-002", "name": "Smartphone Model Y", "category": "Electronics", "weight": 0.2},
        {"id": "sku-003", "name": "Industrial Sensor Pack", "category": "Components", "weight": 1.0},
        {"id": "sku-004", "name": "Electric Motor 5HP", "category": "Machinery", "weight": 25},
        {"id": "sku-005", "name": "Automotive Brake Assembly", "category": "Automotive", "weight": 8},
    ]

    for prod in products:
        all_twins.append(prepare_supply_chain_twin({
            "id": prod["id"],
            "type": "Product",
            "name": prod["name"],
            "properties": {
                "category": prod["category"],
                "weight": prod["weight"],
                "weightUnit": "kg",
                "dimensions": {"length": 30, "width": 20, "height": 10},
                "dimensionUnit": "cm",
                "hazmat": False,
                "temperatureSensitive": False,
                "value": 500,
                "currency": "USD"
            }
        }))
        all_relationships.append(("supply-chain-global", "handlesProduct", prod["id"], None))

    # =========================================================================
    # INVENTORY LEVELS
    # =========================================================================
    inventory_items = [
        {"product": "sku-001", "warehouse": "warehouse-chicago", "quantity": 5000},
        {"product": "sku-001", "warehouse": "warehouse-la", "quantity": 3500},
        {"product": "sku-002", "warehouse": "warehouse-chicago", "quantity": 15000},
        {"product": "sku-002", "warehouse": "warehouse-newark", "quantity": 8000},
        {"product": "sku-003", "warehouse": "warehouse-rotterdam", "quantity": 2500},
        {"product": "sku-004", "warehouse": "warehouse-frankfurt", "quantity": 500},
        {"product": "sku-005", "warehouse": "warehouse-chicago", "quantity": 1200},
    ]

    for inv in inventory_items:
        inv_id = f"inventory-{inv['product']}-{inv['warehouse']}"
        all_twins.append(prepare_supply_chain_twin({
            "id": inv_id,
            "type": "InventoryLevel",
            "name": f"Inventory {inv['product']} at {inv['warehouse']}",
            "properties": {
                "quantity": inv["quantity"],
                "reorderPoint": inv["quantity"] // 5,
                "maxQuantity": inv["quantity"] * 2,
                "lastUpdated": "2024-12-15T10:00:00Z",
                "status": "adequate"
            }
        }))
        all_relationships.append((inv_id, "forProduct", inv["product"], None))
        all_relationships.append((inv_id, "atWarehouse", inv["warehouse"], None))

    # =========================================================================
    # IoT SENSORS
    # =========================================================================
    # GPS trackers on trucks
    for truck in trucks[:5]:
        tracker_id = f"gps-{truck['id']}"
        all_twins.append(prepare_supply_chain_twin({
            "id": tracker_id,
            "type": "GPSTracker",
            "name": f"GPS Tracker - {truck['name']}",
            "properties": {
                "manufacturer": "Samsara",
                "model": "VG34",
                "currentLocation": {"lat": 41.8781, "lng": -87.6298},
                "speed": 65,
                "speedUnit": "mph",
                "heading": 270,
                "lastUpdate": "2024-12-15T10:30:00Z",
                "status": "online"
            }
        }))
        all_relationships.append((tracker_id, "installedOn", truck["id"], None))

    # Temperature sensors in refrigerated units
    for cont in [c for c in containers if c["type"] == "ReeferContainer"]:
        temp_sensor_id = f"temp-sensor-{cont['id']}"
        all_twins.append(prepare_supply_chain_twin({
            "id": temp_sensor_id,
            "type": "TemperatureSensor",
            "name": f"Temperature Sensor - {cont['id']}",
            "properties": {
                "currentValue": -18.5,
                "unit": "Celsius",
                "minThreshold": -22,
                "maxThreshold": -15,
                "status": "normal",
                "lastReading": "2024-12-15T10:30:00Z"
            }
        }))
        all_relationships.append((temp_sensor_id, "monitors", cont["id"], None))

    # =========================================================================
    # CUSTOMERS
    # =========================================================================
    customers = [
        {"id": "customer-ny", "name": "New York Electronics Retailer", "city": "New York", "type": "Retailer"},
        {"id": "customer-seattle", "name": "Seattle Tech Store", "city": "Seattle", "type": "Retailer"},
        {"id": "customer-berlin", "name": "Berlin Industrial Supplies", "city": "Berlin", "type": "Distributor"},
        {"id": "customer-tokyo", "name": "Tokyo Consumer Electronics", "city": "Tokyo", "type": "Retailer"},
    ]

    for cust in customers:
        all_twins.append(prepare_supply_chain_twin({
            "id": cust["id"],
            "type": "Customer",
            "name": cust["name"],
            "properties": {
                "city": cust["city"],
                "customerType": cust["type"],
                "tier": "Gold",
                "creditLimit": 500000,
                "status": "active"
            }
        }))
        all_relationships.append(("supply-chain-global", "servesCustomer", cust["id"], None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, twins_failed = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships...")
    relationships_created, relationships_failed = bulk_add_relationships(client, all_relationships)

    print_summary("Supply Chain / Logistics", twins_created, relationships_created)
    logger.info("Supply Chain digital twin seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_supply_chain()
