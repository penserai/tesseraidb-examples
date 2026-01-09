#!/usr/bin/env python3
"""
Robotics / Warehouse Automation Digital Twin Example

This example creates a comprehensive digital twin of an automated fulfillment center,
including autonomous mobile robots (AMRs), robotic arms, conveyors, and storage systems.

Domain: Robotics / Warehouse Automation
Ontology: http://tesserai.io/ontology/robotics#

Use Cases:
  - Robot fleet management
  - Task allocation and path planning
  - Predictive maintenance for robots
  - Throughput optimization
  - Human-robot collaboration safety
  - Real-time inventory tracking

Cross-Domain Interoperability:
  - Robotics twins can interact with supply_chain (freight handling)
  - Robotics twins can interact with manufacturing (industrial robots)
  - Uses dtaas:core concepts for shared robot/vehicle types
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
DOMAIN = "robotics"
ROBO_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_robotics_twin(twin_id: str, twin_type: str, name: str,
                          description: str = None, properties: dict = None) -> dict:
    """Prepare a twin dict for the robotics domain with proper namespace."""
    # Expand type to full URI
    full_type = f"{ROBO_NS}{twin_type}"

    data = {
        "id": twin_id,
        "type": full_type,
        "name": name,
        "domain": DOMAIN,
        "properties": properties or {},
    }
    if description:
        data["description"] = description

    return data


def prepare_generic_twin(data: dict) -> dict:
    """Prepare a generic twin dict (for types without namespace expansion)."""
    data["domain"] = DOMAIN
    return data


def seed_robotics():
    """Seed the robotics/warehouse automation digital twin."""
    client = get_client()

    # Collect all twins and relationships for bulk operations
    all_twins = []
    all_relationships = []

    # =========================================================================
    # FULFILLMENT CENTER
    # =========================================================================
    all_twins.append(prepare_robotics_twin(
        twin_id="fulfillment-center-001",
        twin_type="FulfillmentCenter",
        name="Advanced Robotics Fulfillment Center",
        description="Highly automated fulfillment center with AMR fleet",
        properties={
            "address": "1000 Automation Way, Phoenix, AZ 85001",
            "area": 100000,
            "areaUnit": "sqm",
            "clearHeight": 12,
            "heightUnit": "meters",
            "dailyOrders": 50000,
            "skuCount": 500000,
            "automationLevel": 95,
            "employees": 150,
            "robotCount": 200,
            "operatingHours": "24/7"
        }
    ))

    # =========================================================================
    # ZONES
    # =========================================================================
    zones = [
        {"id": "zone-receiving", "name": "Receiving Zone", "type": "receiving", "area": 8000},
        {"id": "zone-storage-a", "name": "Storage Zone A - Small Items", "type": "storage", "area": 25000},
        {"id": "zone-storage-b", "name": "Storage Zone B - Medium Items", "type": "storage", "area": 20000},
        {"id": "zone-storage-c", "name": "Storage Zone C - Large Items", "type": "storage", "area": 15000},
        {"id": "zone-picking", "name": "Picking Zone", "type": "picking", "area": 15000},
        {"id": "zone-packing", "name": "Packing Zone", "type": "packing", "area": 8000},
        {"id": "zone-shipping", "name": "Shipping Zone", "type": "shipping", "area": 6000},
        {"id": "zone-charging", "name": "Robot Charging Zone", "type": "charging", "area": 2000},
        {"id": "zone-maintenance", "name": "Robot Maintenance Zone", "type": "maintenance", "area": 1000},
    ]

    for zone in zones:
        all_twins.append(prepare_robotics_twin(
            twin_id=zone["id"],
            twin_type="WarehouseZone",
            name=zone["name"],
            properties={
                "zoneType": zone["type"],
                "area": zone["area"],
                "areaUnit": "sqm",
                "robotsAllowed": zone["type"] not in ["maintenance"],
                "humanTrafficLevel": "low" if zone["type"] in ["storage", "charging"] else "medium",
                "temperature": 22,
                "status": "active"
            }
        ))
        all_relationships.append(("fulfillment-center-001", "hasZone", zone["id"], None))

    # =========================================================================
    # AUTONOMOUS MOBILE ROBOTS (AMRs)
    # =========================================================================
    amr_types = [
        {"type": "ShelfCarrier", "count": 80, "manufacturer": "Kiva/Amazon", "payload": 500},
        {"type": "ToteRunner", "count": 50, "manufacturer": "Locus Robotics", "payload": 35},
        {"type": "FloorCleaner", "count": 5, "manufacturer": "Brain Corp", "payload": 0},
        {"type": "PalletMover", "count": 20, "manufacturer": "Vecna Robotics", "payload": 1500},
        {"type": "SortationRobot", "count": 30, "manufacturer": "Geek+", "payload": 30},
    ]

    robot_id = 1
    for amr_type in amr_types:
        for i in range(amr_type["count"]):
            rid = f"amr-{robot_id:04d}"
            status_options = ["idle", "working", "charging", "maintenance"]
            status = status_options[robot_id % 4] if robot_id % 10 != 0 else "maintenance"

            all_twins.append(prepare_robotics_twin(
                twin_id=rid,
                twin_type=amr_type["type"],
                name=f"{amr_type['type']} {robot_id:04d}",
                properties={
                    "manufacturer": amr_type["manufacturer"],
                    "payload": amr_type["payload"],
                    "payloadUnit": "kg",
                    "batteryLevel": 45 + (robot_id % 50),
                    "batteryCapacity": 100,
                    "batteryUnit": "Ah",
                    "speed": 1.5,
                    "speedUnit": "m/s",
                    "currentLocation": {"x": (robot_id % 50) * 2, "y": (robot_id % 30) * 2, "z": 0},
                    "currentZone": zones[robot_id % 6]["id"],
                    "status": status,
                    "tasksCompletedToday": robot_id * 5,
                    "totalRuntime": 12500 + (robot_id * 100),
                    "runtimeUnit": "hours",
                    "lastMaintenance": "2026-11-15",
                    "firmwareVersion": "3.4.2"
                }
            ))

            # Add to appropriate zone
            if status == "charging":
                all_relationships.append((rid, "locatedIn", "zone-charging", None))
            elif status == "maintenance":
                all_relationships.append((rid, "locatedIn", "zone-maintenance", None))
            else:
                all_relationships.append((rid, "locatedIn", zones[robot_id % 6]["id"], None))

            robot_id += 1

    # =========================================================================
    # ROBOTIC ARMS (Pick & Place)
    # =========================================================================
    robotic_arms = [
        {"id": "arm-pick-001", "name": "Picking Arm 1", "type": "PickingArm", "zone": "zone-picking", "manufacturer": "Universal Robots"},
        {"id": "arm-pick-002", "name": "Picking Arm 2", "type": "PickingArm", "zone": "zone-picking", "manufacturer": "Universal Robots"},
        {"id": "arm-pick-003", "name": "Picking Arm 3", "type": "PickingArm", "zone": "zone-picking", "manufacturer": "Fanuc"},
        {"id": "arm-pick-004", "name": "Picking Arm 4", "type": "PickingArm", "zone": "zone-picking", "manufacturer": "Fanuc"},
        {"id": "arm-pack-001", "name": "Packing Arm 1", "type": "PackingArm", "zone": "zone-packing", "manufacturer": "ABB"},
        {"id": "arm-pack-002", "name": "Packing Arm 2", "type": "PackingArm", "zone": "zone-packing", "manufacturer": "ABB"},
        {"id": "arm-palletize-001", "name": "Palletizing Arm 1", "type": "PalletizingArm", "zone": "zone-shipping", "manufacturer": "KUKA"},
        {"id": "arm-palletize-002", "name": "Palletizing Arm 2", "type": "PalletizingArm", "zone": "zone-shipping", "manufacturer": "KUKA"},
        {"id": "arm-depalletize-001", "name": "Depalletizing Arm 1", "type": "DepalletizingArm", "zone": "zone-receiving", "manufacturer": "KUKA"},
    ]

    for arm in robotic_arms:
        all_twins.append(prepare_generic_twin({
            "id": arm["id"],
            "type": arm["type"],
            "name": arm["name"],
            "properties": {
                "manufacturer": arm["manufacturer"],
                "model": "UR10e" if arm["manufacturer"] == "Universal Robots" else "M-20iA",
                "reach": 1300,
                "reachUnit": "mm",
                "payload": 10 if "pick" in arm["id"] else (20 if "pack" in arm["id"] else 120),
                "payloadUnit": "kg",
                "repeatability": 0.03,
                "repeatabilityUnit": "mm",
                "axes": 6,
                "cycleTime": 3.5,
                "cycleTimeUnit": "seconds",
                "picksPerHour": 900,
                "status": "running",
                "currentTask": "picking" if "pick" in arm["id"] else ("packing" if "pack" in arm["id"] else "palletizing"),
                "itemsProcessedToday": 4500,
                "errorRate": 0.02,
                "lastCalibration": "2026-12-01"
            }
        }))
        all_relationships.append((arm["id"], "installedIn", arm["zone"], None))

    # =========================================================================
    # VISION SYSTEMS
    # =========================================================================
    vision_systems = [
        {"id": "vision-pick-001", "name": "Pick Station Vision 1", "arm": "arm-pick-001"},
        {"id": "vision-pick-002", "name": "Pick Station Vision 2", "arm": "arm-pick-002"},
        {"id": "vision-pick-003", "name": "Pick Station Vision 3", "arm": "arm-pick-003"},
        {"id": "vision-pick-004", "name": "Pick Station Vision 4", "arm": "arm-pick-004"},
        {"id": "vision-qc-001", "name": "QC Vision System 1", "zone": "zone-packing"},
        {"id": "vision-qc-002", "name": "QC Vision System 2", "zone": "zone-packing"},
        {"id": "vision-receiving-001", "name": "Receiving Vision System", "zone": "zone-receiving"},
    ]

    for vis in vision_systems:
        all_twins.append(prepare_generic_twin({
            "id": vis["id"],
            "type": "VisionSystem",
            "name": vis["name"],
            "properties": {
                "manufacturer": "Cognex",
                "model": "In-Sight D900",
                "resolution": "5MP",
                "frameRate": 60,
                "hasDeepLearning": True,
                "scanRate": 3000,
                "scanRateUnit": "items/hour",
                "accuracy": 99.5,
                "status": "online",
                "defectsDetectedToday": 23
            }
        }))
        if "arm" in vis:
            all_relationships.append((vis["id"], "guidesArm", vis["arm"], None))
        else:
            all_relationships.append((vis["id"], "installedIn", vis["zone"], None))

    # =========================================================================
    # AUTOMATED STORAGE AND RETRIEVAL SYSTEM (AS/RS)
    # =========================================================================
    all_twins.append(prepare_generic_twin({
        "id": "asrs-main",
        "type": "ASRS",
        "name": "Main AS/RS System",
        "description": "Automated Storage and Retrieval System",
        "properties": {
            "manufacturer": "Dematic",
            "type": "shuttle",
            "aisles": 20,
            "levels": 15,
            "locationsPerAisle": 100,
            "totalLocations": 30000,
            "occupancy": 85,
            "throughput": 500,
            "throughputUnit": "totes/hour",
            "status": "operational"
        }
    }))
    all_relationships.append(("fulfillment-center-001", "hasASRS", "asrs-main", None))

    # AS/RS Shuttles
    for i in range(1, 21):
        shuttle_id = f"asrs-shuttle-{i:03d}"
        all_twins.append(prepare_generic_twin({
            "id": shuttle_id,
            "type": "ASRSShuttle",
            "name": f"AS/RS Shuttle {i:03d}",
            "properties": {
                "aisle": i,
                "currentLevel": (i % 15) + 1,
                "currentPosition": i * 5,
                "speed": 4,
                "speedUnit": "m/s",
                "payload": 35,
                "payloadUnit": "kg",
                "status": "running" if i % 5 != 0 else "idle",
                "cyclesCompleted": 25000 + (i * 500),
                "lastMaintenance": "2026-11-20"
            }
        }))
        all_relationships.append((shuttle_id, "partOf", "asrs-main", None))

    # =========================================================================
    # CONVEYOR SYSTEM
    # =========================================================================
    conveyor_sections = [
        {"id": "conveyor-induct-001", "name": "Induction Conveyor 1", "type": "induction", "from": "zone-receiving", "to": "zone-storage-a"},
        {"id": "conveyor-induct-002", "name": "Induction Conveyor 2", "type": "induction", "from": "zone-receiving", "to": "zone-storage-b"},
        {"id": "conveyor-main-001", "name": "Main Loop Conveyor", "type": "main", "length": 500},
        {"id": "conveyor-pick-001", "name": "Picking Conveyor", "type": "picking", "from": "zone-storage-a", "to": "zone-picking"},
        {"id": "conveyor-pick-002", "name": "Picking Conveyor 2", "type": "picking", "from": "zone-storage-b", "to": "zone-picking"},
        {"id": "conveyor-pack-001", "name": "Packing Conveyor", "type": "packing", "from": "zone-picking", "to": "zone-packing"},
        {"id": "conveyor-ship-001", "name": "Shipping Conveyor", "type": "shipping", "from": "zone-packing", "to": "zone-shipping"},
        {"id": "conveyor-sorter-001", "name": "Sortation System", "type": "sorter", "length": 100},
    ]

    for conv in conveyor_sections:
        props = {
            "conveyorType": conv["type"],
            "speed": 2.5,
            "speedUnit": "m/s",
            "width": 600,
            "widthUnit": "mm",
            "itemsPerHour": 3000,
            "status": "running",
            "motorStatus": "normal"
        }
        if "length" in conv:
            props["length"] = conv["length"]
            props["lengthUnit"] = "meters"

        all_twins.append(prepare_generic_twin({
            "id": conv["id"],
            "type": "Conveyor",
            "name": conv["name"],
            "properties": props
        }))
        if "from" in conv:
            all_relationships.append((conv["id"], "connectsFrom", conv["from"], None))
            all_relationships.append((conv["id"], "connectsTo", conv["to"], None))
        else:
            all_relationships.append(("fulfillment-center-001", "hasConveyor", conv["id"], None))

    # =========================================================================
    # CHARGING STATIONS
    # =========================================================================
    for i in range(1, 31):
        station_id = f"charging-station-{i:03d}"
        all_twins.append(prepare_generic_twin({
            "id": station_id,
            "type": "ChargingStation",
            "name": f"Charging Station {i:03d}",
            "properties": {
                "type": "fast" if i <= 10 else "standard",
                "power": 20 if i <= 10 else 10,
                "powerUnit": "kW",
                "status": "occupied" if i % 3 == 0 else "available",
                "currentRobot": f"amr-{i:04d}" if i % 3 == 0 else None,
                "chargesCompletedToday": 15 + (i % 10),
                "energyDeliveredToday": 200 + (i * 5),
                "energyUnit": "kWh"
            }
        }))
        all_relationships.append((station_id, "locatedIn", "zone-charging", None))

    # =========================================================================
    # WORK STATIONS (Human-Robot Collaboration)
    # =========================================================================
    workstations = [
        {"id": "workstation-pack-001", "name": "Packing Station 1", "type": "packing", "zone": "zone-packing"},
        {"id": "workstation-pack-002", "name": "Packing Station 2", "type": "packing", "zone": "zone-packing"},
        {"id": "workstation-pack-003", "name": "Packing Station 3", "type": "packing", "zone": "zone-packing"},
        {"id": "workstation-pack-004", "name": "Packing Station 4", "type": "packing", "zone": "zone-packing"},
        {"id": "workstation-problem-001", "name": "Problem Resolution Station", "type": "problem", "zone": "zone-picking"},
        {"id": "workstation-receive-001", "name": "Receiving Station 1", "type": "receiving", "zone": "zone-receiving"},
        {"id": "workstation-receive-002", "name": "Receiving Station 2", "type": "receiving", "zone": "zone-receiving"},
    ]

    for ws in workstations:
        all_twins.append(prepare_generic_twin({
            "id": ws["id"],
            "type": "Workstation",
            "name": ws["name"],
            "properties": {
                "stationType": ws["type"],
                "hasCobot": ws["type"] == "packing",
                "hasScanner": True,
                "hasPrinter": ws["type"] in ["packing", "receiving"],
                "hasScale": ws["type"] == "packing",
                "isOccupied": True,
                "operatorId": f"OP-{ws['id'][-3:]}",
                "itemsProcessedToday": 450,
                "averageCycleTime": 25,
                "cycleTimeUnit": "seconds"
            }
        }))
        all_relationships.append((ws["id"], "locatedIn", ws["zone"], None))

    # =========================================================================
    # FLEET MANAGEMENT SYSTEM
    # =========================================================================
    all_twins.append(prepare_generic_twin({
        "id": "fleet-manager",
        "type": "FleetManagementSystem",
        "name": "Robot Fleet Manager",
        "properties": {
            "manufacturer": "6 River Systems",
            "totalRobots": 185,
            "activeRobots": 160,
            "chargingRobots": 18,
            "maintenanceRobots": 7,
            "pendingTasks": 2500,
            "completedTasksToday": 45000,
            "averageTaskTime": 120,
            "taskTimeUnit": "seconds",
            "status": "operational"
        }
    }))
    all_relationships.append(("fulfillment-center-001", "hasFleetManager", "fleet-manager", None))

    # =========================================================================
    # WAREHOUSE MANAGEMENT SYSTEM
    # =========================================================================
    all_twins.append(prepare_generic_twin({
        "id": "wms-main",
        "type": "WarehouseManagementSystem",
        "name": "Warehouse Management System",
        "properties": {
            "vendor": "Manhattan Associates",
            "version": "2026.1",
            "ordersInQueue": 8500,
            "ordersInProgress": 2000,
            "ordersCompletedToday": 35000,
            "inventoryAccuracy": 99.8,
            "pickAccuracy": 99.95,
            "shipmentsOnTime": 98.5,
            "status": "operational"
        }
    }))
    all_relationships.append(("fulfillment-center-001", "hasWMS", "wms-main", None))
    all_relationships.append(("wms-main", "controls", "fleet-manager", None))

    # =========================================================================
    # SAFETY SYSTEMS
    # =========================================================================
    safety_sensors = [
        {"id": "safety-lidar-001", "name": "Safety LiDAR 1", "zone": "zone-picking"},
        {"id": "safety-lidar-002", "name": "Safety LiDAR 2", "zone": "zone-packing"},
        {"id": "safety-lidar-003", "name": "Safety LiDAR 3", "zone": "zone-receiving"},
        {"id": "safety-curtain-001", "name": "Light Curtain - Palletizer 1", "arm": "arm-palletize-001"},
        {"id": "safety-curtain-002", "name": "Light Curtain - Palletizer 2", "arm": "arm-palletize-002"},
        {"id": "safety-scanner-001", "name": "Area Scanner 1", "zone": "zone-picking"},
        {"id": "safety-scanner-002", "name": "Area Scanner 2", "zone": "zone-packing"},
    ]

    for sensor in safety_sensors:
        all_twins.append(prepare_generic_twin({
            "id": sensor["id"],
            "type": "SafetySensor",
            "name": sensor["name"],
            "properties": {
                "sensorType": "lidar" if "lidar" in sensor["id"] else ("lightCurtain" if "curtain" in sensor["id"] else "areaScanner"),
                "manufacturer": "SICK",
                "range": 8,
                "rangeUnit": "meters",
                "responseTime": 10,
                "responseTimeUnit": "ms",
                "status": "active",
                "lastTriggered": "2026-12-14T15:30:00Z",
                "triggersToday": 5
            }
        }))
        if "arm" in sensor:
            all_relationships.append((sensor["id"], "protects", sensor["arm"], None))
        else:
            all_relationships.append((sensor["id"], "monitors", sensor["zone"], None))

    # Emergency stops
    for i in range(1, 11):
        estop_id = f"estop-{i:03d}"
        all_twins.append(prepare_generic_twin({
            "id": estop_id,
            "type": "EmergencyStop",
            "name": f"E-Stop {i:03d}",
            "properties": {
                "location": {"x": i * 10, "y": i * 8},
                "status": "armed",
                "lastTest": "2026-12-01",
                "lastActivation": "2026-10-15"
            }
        }))
        all_relationships.append((estop_id, "locatedIn", zones[i % len(zones)]["id"], None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, twins_failed = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships...")
    relationships_created, relationships_failed = bulk_add_relationships(client, all_relationships)

    print_summary("Robotics / Warehouse Automation", twins_created, relationships_created)
    logger.info("Robotics digital twin seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_robotics()
