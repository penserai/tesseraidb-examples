#!/usr/bin/env python3
"""
Cascading Failure Analysis - Infrastructure Dependency Graph
=============================================================

Creates a comprehensive digital twin network modeling complex infrastructure
dependencies across multiple domains:

1. Power Grid Infrastructure
   - Power plants, substations, transformers, feeders
   - Load centers, distribution networks

2. Data Center & IT Infrastructure
   - Servers, network equipment, storage systems
   - Cooling systems, UPS, generators

3. Manufacturing Plant Systems
   - Production lines dependent on power & IT
   - Critical equipment chains

4. Supply Chain Network
   - Suppliers, warehouses, logistics
   - Just-in-time dependencies

The graph structure enables analysis of how failures propagate through
interconnected systems with different time delays and impact severities.

Usage:
    python seed.py [--base-url URL] [--scenario SCENARIO]

Scenarios:
    full - Complete infrastructure (default)
    power - Power grid only
    datacenter - Data center only
    manufacturing - Manufacturing plant only
"""

import sys
import os
import random
import argparse
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import (
    get_client, print_summary, logger,
    bulk_create_twins, bulk_add_relationships,
    DOMAIN_NAMESPACES
)

# Register new domain namespace
DOMAIN = "cascading_failure"
CF_NS = "http://tesserai.io/ontology/cascading_failure#"
DOMAIN_NAMESPACES[DOMAIN] = CF_NS

# Seed for reproducibility
random.seed(42)


def prepare_cf_twin(data: dict) -> dict:
    """Prepare a twin dict for bulk creation in the cascading failure domain."""
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{CF_NS}{twin_type}"
    data["domain"] = DOMAIN
    return data


def collect_power_grid(all_twins: List[dict], all_relationships: List[Tuple]) -> None:
    """Collect power grid infrastructure twins and relationships."""

    # Power Generation
    power_plants = [
        {"id": "pp-gas-001", "name": "Riverside Gas Plant", "type": "natural_gas", "capacity": 500, "status": "online"},
        {"id": "pp-gas-002", "name": "Harbor Gas Plant", "type": "natural_gas", "capacity": 400, "status": "online"},
        {"id": "pp-coal-001", "name": "Northern Coal Station", "type": "coal", "capacity": 800, "status": "online"},
        {"id": "pp-nuclear-001", "name": "Bayshore Nuclear", "type": "nuclear", "capacity": 1200, "status": "online"},
        {"id": "pp-solar-001", "name": "Desert Solar Farm", "type": "solar", "capacity": 200, "status": "online"},
        {"id": "pp-wind-001", "name": "Coastal Wind Farm", "type": "wind", "capacity": 150, "status": "online"},
    ]

    for plant in power_plants:
        all_twins.append(prepare_cf_twin({
            "id": plant["id"],
            "type": "PowerPlant",
            "name": plant["name"],
            "properties": {
                "fuelType": plant["type"],
                "generationCapacity": plant["capacity"],
                "capacityUnit": "MW",
                "status": plant["status"],
                "currentOutput": round(plant["capacity"] * random.uniform(0.6, 0.95), 1),
                "reliability": round(random.uniform(0.95, 0.999), 4),
                "criticality": "critical",
                "mttr": random.randint(4, 48),
                "redundancyLevel": random.choice(["N", "N+1", "2N"]),
                "businessImpact": random.randint(8, 10),
            }
        }))

    # Transmission Substations
    substations = [
        {"id": "sub-trans-001", "name": "Central Grid Substation", "voltage": 345, "load": 1500},
        {"id": "sub-trans-002", "name": "North Grid Hub", "voltage": 345, "load": 1200},
        {"id": "sub-trans-003", "name": "South Distribution Hub", "voltage": 138, "load": 800},
        {"id": "sub-trans-004", "name": "Industrial Zone Substation", "voltage": 138, "load": 600},
        {"id": "sub-trans-005", "name": "Commercial District Hub", "voltage": 69, "load": 400},
        {"id": "sub-trans-006", "name": "Residential Zone Substation", "voltage": 69, "load": 350},
    ]

    for sub in substations:
        all_twins.append(prepare_cf_twin({
            "id": sub["id"],
            "type": "Substation",
            "name": sub["name"],
            "properties": {
                "voltageLevel": sub["voltage"],
                "voltageUnit": "kV",
                "loadCapacity": sub["load"],
                "loadUnit": "MW",
                "currentLoad": round(sub["load"] * random.uniform(0.5, 0.85), 1),
                "status": "operational",
                "hasRedundantPath": random.choice([True, False]),
                "transformerCount": random.randint(2, 6),
                "criticality": "critical" if sub["voltage"] > 100 else "high",
                "cascadeDepth": random.randint(2, 5),
                "businessImpact": random.randint(7, 10),
            }
        }))

    # Power Grid Connections
    grid_connections = [
        ("pp-gas-001", "sub-trans-001", "powerSupply"),
        ("pp-gas-002", "sub-trans-002", "powerSupply"),
        ("pp-coal-001", "sub-trans-001", "powerSupply"),
        ("pp-nuclear-001", "sub-trans-002", "powerSupply"),
        ("pp-solar-001", "sub-trans-003", "powerSupply"),
        ("pp-wind-001", "sub-trans-003", "powerSupply"),
        ("sub-trans-001", "sub-trans-003", "powerSupply"),
        ("sub-trans-001", "sub-trans-004", "powerSupply"),
        ("sub-trans-002", "sub-trans-003", "powerSupply"),
        ("sub-trans-002", "sub-trans-005", "powerSupply"),
        ("sub-trans-003", "sub-trans-004", "powerSupply"),
        ("sub-trans-003", "sub-trans-006", "powerSupply"),
        ("sub-trans-004", "sub-trans-005", "backupPower"),
        ("sub-trans-005", "sub-trans-006", "backupPower"),
    ]

    for source, target, dep_type in grid_connections:
        all_relationships.append((source, dep_type, target, None))
        all_relationships.append((target, "dependsOn", source, None))

    logger.info("Collected power grid data")


def collect_data_center(all_twins: List[dict], all_relationships: List[Tuple]) -> None:
    """Collect data center infrastructure twins and relationships."""

    # Main power feeds
    power_feeds = [
        {"id": "dc-power-feed-a", "name": "Data Center Power Feed A", "capacity": 10, "source": "sub-trans-004"},
        {"id": "dc-power-feed-b", "name": "Data Center Power Feed B", "capacity": 10, "source": "sub-trans-005"},
    ]

    for feed in power_feeds:
        all_twins.append(prepare_cf_twin({
            "id": feed["id"],
            "type": "PowerFeed",
            "name": feed["name"],
            "properties": {
                "capacity": feed["capacity"],
                "capacityUnit": "MW",
                "status": "active",
                "redundancyType": "2N",
                "criticality": "critical",
                "businessImpact": 10,
            }
        }))
        all_relationships.append((feed["source"], "powerSupply", feed["id"], None))
        all_relationships.append((feed["id"], "dependsOn", feed["source"], None))

    # UPS Systems
    ups_systems = [
        {"id": "dc-ups-001", "name": "UPS Room A-1", "capacity": 2000, "runtime": 15},
        {"id": "dc-ups-002", "name": "UPS Room A-2", "capacity": 2000, "runtime": 15},
        {"id": "dc-ups-003", "name": "UPS Room B-1", "capacity": 2000, "runtime": 15},
        {"id": "dc-ups-004", "name": "UPS Room B-2", "capacity": 2000, "runtime": 15},
    ]

    for ups in ups_systems:
        all_twins.append(prepare_cf_twin({
            "id": ups["id"],
            "type": "UPSSystem",
            "name": ups["name"],
            "properties": {
                "capacity": ups["capacity"],
                "capacityUnit": "kVA",
                "batteryRuntime": ups["runtime"],
                "runtimeUnit": "minutes",
                "batteryHealth": random.randint(85, 100),
                "loadLevel": random.randint(40, 75),
                "status": "online",
                "criticality": "critical",
                "businessImpact": 9,
            }
        }))

    # Connect UPS to power feeds
    all_relationships.append(("dc-power-feed-a", "powerSupply", "dc-ups-001", None))
    all_relationships.append(("dc-power-feed-a", "powerSupply", "dc-ups-002", None))
    all_relationships.append(("dc-power-feed-b", "powerSupply", "dc-ups-003", None))
    all_relationships.append(("dc-power-feed-b", "powerSupply", "dc-ups-004", None))

    # Backup Generators
    generators = [
        {"id": "dc-gen-001", "name": "Generator A", "capacity": 3000, "fuel": 5000},
        {"id": "dc-gen-002", "name": "Generator B", "capacity": 3000, "fuel": 5000},
    ]

    for gen in generators:
        all_twins.append(prepare_cf_twin({
            "id": gen["id"],
            "type": "BackupGenerator",
            "name": gen["name"],
            "properties": {
                "capacity": gen["capacity"],
                "capacityUnit": "kW",
                "fuelCapacity": gen["fuel"],
                "fuelUnit": "gallons",
                "currentFuel": round(gen["fuel"] * random.uniform(0.7, 1.0)),
                "startupTime": 10,
                "status": "standby",
                "lastTest": (datetime.now() - timedelta(days=random.randint(7, 30))).strftime("%Y-%m-%d"),
                "criticality": "critical",
                "businessImpact": 10,
            }
        }))

    # Generators provide backup to UPS
    all_relationships.append(("dc-gen-001", "backupPower", "dc-ups-001", None))
    all_relationships.append(("dc-gen-001", "backupPower", "dc-ups-002", None))
    all_relationships.append(("dc-gen-002", "backupPower", "dc-ups-003", None))
    all_relationships.append(("dc-gen-002", "backupPower", "dc-ups-004", None))

    # Cooling Systems
    cooling_units = [
        {"id": "dc-cooling-001", "name": "CRAC Unit A-1", "capacity": 200, "zone": "A"},
        {"id": "dc-cooling-002", "name": "CRAC Unit A-2", "capacity": 200, "zone": "A"},
        {"id": "dc-cooling-003", "name": "CRAC Unit B-1", "capacity": 200, "zone": "B"},
        {"id": "dc-cooling-004", "name": "CRAC Unit B-2", "capacity": 200, "zone": "B"},
    ]

    for cooling in cooling_units:
        all_twins.append(prepare_cf_twin({
            "id": cooling["id"],
            "type": "CoolingUnit",
            "name": cooling["name"],
            "properties": {
                "coolingCapacity": cooling["capacity"],
                "capacityUnit": "kW",
                "zone": cooling["zone"],
                "supplyTemp": round(random.uniform(55, 65), 1),
                "returnTemp": round(random.uniform(70, 85), 1),
                "tempUnit": "F",
                "status": "running",
                "criticality": "high",
                "thermalThreshold": 85,
                "businessImpact": 8,
            }
        }))
        ups_id = f"dc-ups-00{1 + (int(cooling['zone'] == 'B') * 2)}"
        all_relationships.append((ups_id, "powerSupply", cooling["id"], None))
        all_relationships.append((cooling["id"], "dependsOn", ups_id, None))

    # Chiller Plant
    all_twins.append(prepare_cf_twin({
        "id": "dc-chiller-plant",
        "type": "ChillerPlant",
        "name": "Central Chiller Plant",
        "properties": {
            "capacity": 1000,
            "capacityUnit": "tons",
            "chillerCount": 3,
            "redundancy": "N+1",
            "status": "running",
            "criticality": "high",
            "businessImpact": 9,
        }
    }))

    for cooling in cooling_units:
        all_relationships.append(("dc-chiller-plant", "cooling", cooling["id"], None))

    # Network Infrastructure
    network_devices = [
        {"id": "dc-core-sw-001", "name": "Core Switch A", "type": "core_switch", "ports": 48},
        {"id": "dc-core-sw-002", "name": "Core Switch B", "type": "core_switch", "ports": 48},
        {"id": "dc-agg-sw-001", "name": "Aggregation Switch A-1", "type": "aggregation", "ports": 48},
        {"id": "dc-agg-sw-002", "name": "Aggregation Switch A-2", "type": "aggregation", "ports": 48},
        {"id": "dc-agg-sw-003", "name": "Aggregation Switch B-1", "type": "aggregation", "ports": 48},
        {"id": "dc-agg-sw-004", "name": "Aggregation Switch B-2", "type": "aggregation", "ports": 48},
        {"id": "dc-tor-sw-001", "name": "Top of Rack 1", "type": "tor", "ports": 48},
        {"id": "dc-tor-sw-002", "name": "Top of Rack 2", "type": "tor", "ports": 48},
        {"id": "dc-tor-sw-003", "name": "Top of Rack 3", "type": "tor", "ports": 48},
        {"id": "dc-tor-sw-004", "name": "Top of Rack 4", "type": "tor", "ports": 48},
    ]

    for device in network_devices:
        zone = "A" if "A" in device["id"] or "001" in device["id"] or "002" in device["id"] else "B"
        all_twins.append(prepare_cf_twin({
            "id": device["id"],
            "type": "NetworkSwitch",
            "name": device["name"],
            "properties": {
                "switchType": device["type"],
                "portCount": device["ports"],
                "zone": zone,
                "throughput": random.randint(100, 400),
                "throughputUnit": "Gbps",
                "cpuUtilization": random.randint(15, 60),
                "memoryUtilization": random.randint(30, 70),
                "status": "operational",
                "criticality": "critical" if device["type"] == "core_switch" else "high",
                "businessImpact": 10 if device["type"] == "core_switch" else 8,
            }
        }))

    # Network topology connections
    network_connections = [
        ("dc-ups-001", "powerSupply", "dc-core-sw-001"),
        ("dc-ups-003", "powerSupply", "dc-core-sw-002"),
        ("dc-core-sw-001", "networkConnectivity", "dc-agg-sw-001"),
        ("dc-core-sw-001", "networkConnectivity", "dc-agg-sw-002"),
        ("dc-core-sw-002", "networkConnectivity", "dc-agg-sw-003"),
        ("dc-core-sw-002", "networkConnectivity", "dc-agg-sw-004"),
        ("dc-agg-sw-001", "networkConnectivity", "dc-tor-sw-001"),
        ("dc-agg-sw-002", "networkConnectivity", "dc-tor-sw-002"),
        ("dc-agg-sw-003", "networkConnectivity", "dc-tor-sw-003"),
        ("dc-agg-sw-004", "networkConnectivity", "dc-tor-sw-004"),
        ("dc-core-sw-001", "networkConnectivity", "dc-core-sw-002"),
        ("dc-agg-sw-001", "networkConnectivity", "dc-agg-sw-002"),
        ("dc-agg-sw-003", "networkConnectivity", "dc-agg-sw-004"),
    ]

    for source, dep_type, target in network_connections:
        all_relationships.append((source, dep_type, target, None))

    # Server Racks and Compute
    server_racks = [
        {"id": "dc-rack-001", "name": "Rack A-01", "tor": "dc-tor-sw-001", "cooling": "dc-cooling-001"},
        {"id": "dc-rack-002", "name": "Rack A-02", "tor": "dc-tor-sw-001", "cooling": "dc-cooling-001"},
        {"id": "dc-rack-003", "name": "Rack A-03", "tor": "dc-tor-sw-002", "cooling": "dc-cooling-002"},
        {"id": "dc-rack-004", "name": "Rack B-01", "tor": "dc-tor-sw-003", "cooling": "dc-cooling-003"},
        {"id": "dc-rack-005", "name": "Rack B-02", "tor": "dc-tor-sw-003", "cooling": "dc-cooling-003"},
        {"id": "dc-rack-006", "name": "Rack B-03", "tor": "dc-tor-sw-004", "cooling": "dc-cooling-004"},
    ]

    for rack in server_racks:
        zone = "A" if "A" in rack["name"] else "B"
        ups_id = "dc-ups-001" if zone == "A" else "dc-ups-003"

        all_twins.append(prepare_cf_twin({
            "id": rack["id"],
            "type": "ServerRack",
            "name": rack["name"],
            "properties": {
                "zone": zone,
                "serverCount": random.randint(8, 16),
                "totalPower": random.randint(15, 25),
                "powerUnit": "kW",
                "temperature": round(random.uniform(68, 78), 1),
                "tempUnit": "F",
                "status": "operational",
                "criticality": "high",
                "businessImpact": 7,
            }
        }))

        all_relationships.append((ups_id, "powerSupply", rack["id"], None))
        all_relationships.append((rack["tor"], "networkConnectivity", rack["id"], None))
        all_relationships.append((rack["cooling"], "cooling", rack["id"], None))

    # Critical Applications
    applications = [
        {"id": "app-erp", "name": "ERP System", "tier": 1, "racks": ["dc-rack-001", "dc-rack-004"]},
        {"id": "app-crm", "name": "CRM Platform", "tier": 1, "racks": ["dc-rack-002", "dc-rack-005"]},
        {"id": "app-scm", "name": "Supply Chain Management", "tier": 1, "racks": ["dc-rack-001", "dc-rack-005"]},
        {"id": "app-mes", "name": "Manufacturing Execution", "tier": 1, "racks": ["dc-rack-003", "dc-rack-006"]},
        {"id": "app-scada", "name": "SCADA System", "tier": 0, "racks": ["dc-rack-002", "dc-rack-004"]},
        {"id": "app-email", "name": "Email System", "tier": 2, "racks": ["dc-rack-003"]},
        {"id": "app-web", "name": "Public Website", "tier": 2, "racks": ["dc-rack-006"]},
    ]

    for app in applications:
        all_twins.append(prepare_cf_twin({
            "id": app["id"],
            "type": "Application",
            "name": app["name"],
            "properties": {
                "tier": app["tier"],
                "sla": 99.99 if app["tier"] == 0 else (99.9 if app["tier"] == 1 else 99.5),
                "users": random.randint(100, 5000),
                "transactions": random.randint(1000, 100000),
                "transactionUnit": "per_hour",
                "status": "running",
                "criticality": "critical" if app["tier"] <= 1 else "high",
                "businessImpact": 10 - app["tier"],
                "revenueImpact": random.randint(10000, 1000000),
            }
        }))

        for rack in app["racks"]:
            all_relationships.append((rack, "hosts", app["id"], None))
            all_relationships.append((app["id"], "dependsOn", rack, None))

    # Application dependencies
    app_dependencies = [
        ("app-crm", "data", "app-erp"),
        ("app-scm", "data", "app-erp"),
        ("app-mes", "data", "app-erp"),
        ("app-mes", "control", "app-scada"),
        ("app-web", "data", "app-crm"),
    ]

    for app, dep_type, dependency in app_dependencies:
        all_relationships.append((app, dep_type, dependency, None))
        all_relationships.append((dependency, "dependedUponBy", app, None))

    logger.info("Collected data center data")


def collect_manufacturing(all_twins: List[dict], all_relationships: List[Tuple]) -> None:
    """Collect manufacturing plant dependencies."""

    # Manufacturing Control System
    all_twins.append(prepare_cf_twin({
        "id": "mfg-control-system",
        "type": "ControlSystem",
        "name": "Plant Control System",
        "properties": {
            "vendor": "Siemens",
            "version": "7.5",
            "plcCount": 24,
            "status": "running",
            "criticality": "critical",
            "businessImpact": 10,
        }
    }))

    all_relationships.append(("mfg-control-system", "dependsOn", "app-scada", None))
    all_relationships.append(("mfg-control-system", "dependsOn", "dc-core-sw-001", None))

    # Production Lines
    production_lines = [
        {"id": "mfg-line-001", "name": "Assembly Line 1", "output": 500, "products": "widgets"},
        {"id": "mfg-line-002", "name": "Assembly Line 2", "output": 450, "products": "widgets"},
        {"id": "mfg-line-003", "name": "Packaging Line", "output": 1000, "products": "packaged_goods"},
        {"id": "mfg-line-004", "name": "Quality Inspection", "output": 1500, "products": "inspected_goods"},
    ]

    for line in production_lines:
        all_twins.append(prepare_cf_twin({
            "id": line["id"],
            "type": "ProductionLine",
            "name": line["name"],
            "properties": {
                "outputRate": line["output"],
                "outputUnit": "units_per_hour",
                "productType": line["products"],
                "currentEfficiency": random.randint(85, 98),
                "status": "running",
                "operators": random.randint(3, 8),
                "criticality": "critical",
                "businessImpact": 9,
                "hourlyRevenue": line["output"] * random.randint(5, 20),
            }
        }))

        all_relationships.append((line["id"], "dependsOn", "sub-trans-004", None))
        all_relationships.append((line["id"], "dependsOn", "mfg-control-system", None))
        all_relationships.append((line["id"], "dependsOn", "app-mes", None))

    # Line sequence dependencies
    all_relationships.append(("mfg-line-003", "material", "mfg-line-001", None))
    all_relationships.append(("mfg-line-003", "material", "mfg-line-002", None))
    all_relationships.append(("mfg-line-004", "material", "mfg-line-003", None))

    # Critical Equipment
    equipment = [
        {"id": "mfg-robot-001", "name": "Welding Robot 1", "line": "mfg-line-001"},
        {"id": "mfg-robot-002", "name": "Welding Robot 2", "line": "mfg-line-001"},
        {"id": "mfg-cnc-001", "name": "CNC Machine 1", "line": "mfg-line-002"},
        {"id": "mfg-cnc-002", "name": "CNC Machine 2", "line": "mfg-line-002"},
        {"id": "mfg-conveyor-001", "name": "Main Conveyor", "line": "mfg-line-003"},
        {"id": "mfg-vision-001", "name": "Vision Inspection System", "line": "mfg-line-004"},
    ]

    for eq in equipment:
        all_twins.append(prepare_cf_twin({
            "id": eq["id"],
            "type": "ManufacturingEquipment",
            "name": eq["name"],
            "properties": {
                "equipmentType": eq["id"].split("-")[1],
                "status": "running",
                "utilization": random.randint(70, 95),
                "criticality": "high",
                "businessImpact": 7,
            }
        }))

        all_relationships.append((eq["line"], "hasEquipment", eq["id"], None))
        all_relationships.append((eq["id"], "dependsOn", "mfg-control-system", None))

    logger.info("Collected manufacturing data")


def collect_supply_chain(all_twins: List[dict], all_relationships: List[Tuple]) -> None:
    """Collect supply chain dependencies."""

    # Suppliers
    suppliers = [
        {"id": "supplier-raw-001", "name": "Steel Supplier Co", "material": "steel", "lead_time": 14},
        {"id": "supplier-raw-002", "name": "Aluminum Corp", "material": "aluminum", "lead_time": 10},
        {"id": "supplier-comp-001", "name": "Electronics Components Inc", "material": "electronics", "lead_time": 21},
        {"id": "supplier-comp-002", "name": "Precision Parts Ltd", "material": "precision_parts", "lead_time": 7},
    ]

    for supplier in suppliers:
        all_twins.append(prepare_cf_twin({
            "id": supplier["id"],
            "type": "Supplier",
            "name": supplier["name"],
            "properties": {
                "materialType": supplier["material"],
                "leadTime": supplier["lead_time"],
                "leadTimeUnit": "days",
                "reliability": round(random.uniform(0.9, 0.99), 3),
                "currentInventory": random.randint(1000, 10000),
                "inventoryUnit": "units",
                "status": "active",
                "criticality": "high",
                "businessImpact": 6,
            }
        }))

    # Warehouse
    all_twins.append(prepare_cf_twin({
        "id": "warehouse-main",
        "type": "Warehouse",
        "name": "Main Distribution Warehouse",
        "properties": {
            "capacity": 50000,
            "capacityUnit": "sqft",
            "currentUtilization": random.randint(60, 85),
            "dockCount": 12,
            "status": "operational",
            "criticality": "high",
            "businessImpact": 7,
        }
    }))

    all_relationships.append(("warehouse-main", "dependsOn", "sub-trans-005", None))
    all_relationships.append(("warehouse-main", "dependsOn", "app-scm", None))

    # Material flow to production
    for supplier in suppliers:
        all_relationships.append((supplier["id"], "material", "warehouse-main", None))

    all_relationships.append(("warehouse-main", "material", "mfg-line-001", None))
    all_relationships.append(("warehouse-main", "material", "mfg-line-002", None))

    # Logistics
    logistics_providers = [
        {"id": "logistics-primary", "name": "Primary Freight Co", "mode": "truck"},
        {"id": "logistics-backup", "name": "Backup Logistics LLC", "mode": "truck"},
    ]

    for provider in logistics_providers:
        all_twins.append(prepare_cf_twin({
            "id": provider["id"],
            "type": "LogisticsProvider",
            "name": provider["name"],
            "properties": {
                "transportMode": provider["mode"],
                "fleetSize": random.randint(20, 100),
                "onTimeDelivery": round(random.uniform(0.92, 0.99), 3),
                "status": "active",
                "criticality": "medium",
                "businessImpact": 5,
            }
        }))

    logger.info("Collected supply chain data")


def seed_cascading_failure(base_url: Optional[str] = None, scenario: str = "full"):
    """Seed the cascading failure digital twin network."""
    client = get_client(base_url)
    all_twins = []
    all_relationships = []

    print(f"\nSeeding Cascading Failure Analysis - Scenario: {scenario}")
    print("=" * 60)

    if scenario in ["full", "power"]:
        collect_power_grid(all_twins, all_relationships)

    if scenario in ["full", "datacenter"]:
        collect_data_center(all_twins, all_relationships)

    if scenario in ["full", "manufacturing"]:
        collect_manufacturing(all_twins, all_relationships)

    if scenario == "full":
        collect_supply_chain(all_twins, all_relationships)

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, _ = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships via bulk API...")
    relationships_created, _ = bulk_add_relationships(client, all_relationships)

    print_summary("Cascading Failure Analysis", twins_created, relationships_created)
    logger.info("Cascading Failure digital twin network seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Cascading Failure Analysis data")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--scenario", default="full",
                       choices=["full", "power", "datacenter", "manufacturing"],
                       help="Scenario to seed (default: full)")
    args = parser.parse_args()

    seed_cascading_failure(args.base_url, args.scenario)
