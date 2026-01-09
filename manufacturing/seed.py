#!/usr/bin/env python3
"""
Manufacturing / Industry 4.0 Digital Twin Example

This example creates a comprehensive digital twin of a smart factory,
including production lines, CNC machines, robots, conveyors, and quality control.

Domain: Manufacturing / Industry 4.0
Use Cases:
  - Production monitoring and OEE (Overall Equipment Effectiveness)
  - Predictive maintenance
  - Quality control and defect tracking
  - Supply chain integration
  - Process optimization
  - Energy consumption analysis

Performance: Uses bulk API for fast seeding against remote servers.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import (
    get_client, print_summary, logger,
    DOMAIN_NAMESPACES, bulk_create_twins, bulk_add_relationships
)

# Domain for this seed script
DOMAIN = "manufacturing"
MFG_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_manufacturing_twin(data: dict) -> dict:
    """Prepare twin data with proper namespace and domain tag."""
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{MFG_NS}{twin_type}"
    data["domain"] = DOMAIN
    return data


def seed_manufacturing():
    """Seed the manufacturing digital twin using bulk API for performance."""
    client = get_client()

    # Collect all twins and relationships for bulk operations
    all_twins = []
    all_relationships = []

    # =========================================================================
    # FACTORY
    # =========================================================================
    all_twins.append(prepare_manufacturing_twin({
        "id": "factory-munich-001",
        "type": "Factory",
        "name": "Munich Precision Manufacturing Plant",
        "description": "High-precision automotive parts manufacturing facility",
        "properties": {
            "address": "Industriestraße 45, 80939 Munich, Germany",
            "area": 25000,
            "areaUnit": "sqm",
            "employees": 450,
            "shifts": 3,
            "operatingHours": "24/7",
            "certifications": ["ISO 9001", "ISO 14001", "IATF 16949"],
            "annualCapacity": 5000000,
            "capacityUnit": "parts",
            "coordinates": {"lat": 48.1851, "lng": 11.6191}
        }
    }))

    # =========================================================================
    # PRODUCTION AREAS
    # =========================================================================
    areas = [
        {"id": "area-receiving", "name": "Receiving & Raw Materials", "type": "warehouse", "area": 3000},
        {"id": "area-machining", "name": "CNC Machining Hall", "type": "production", "area": 8000},
        {"id": "area-assembly", "name": "Assembly Line", "type": "production", "area": 5000},
        {"id": "area-quality", "name": "Quality Control Lab", "type": "inspection", "area": 1500},
        {"id": "area-finishing", "name": "Surface Treatment & Finishing", "type": "production", "area": 3000},
        {"id": "area-packaging", "name": "Packaging & Shipping", "type": "warehouse", "area": 3000},
        {"id": "area-maintenance", "name": "Maintenance Workshop", "type": "support", "area": 1500},
    ]

    for area in areas:
        all_twins.append(prepare_manufacturing_twin({
            "id": area["id"],
            "type": "ProductionArea",
            "name": area["name"],
            "properties": {
                "areaType": area["type"],
                "area": area["area"],
                "areaUnit": "sqm",
                "temperature": 22,
                "humidity": 45
            }
        }))
        all_relationships.append(("factory-munich-001", "hasArea", area["id"], None))

    # =========================================================================
    # PRODUCTION LINES
    # =========================================================================
    lines = [
        {"id": "line-engine-block", "name": "Engine Block Production Line", "product": "Engine Blocks", "taktTime": 180},
        {"id": "line-crankshaft", "name": "Crankshaft Production Line", "product": "Crankshafts", "taktTime": 240},
        {"id": "line-cylinder-head", "name": "Cylinder Head Production Line", "product": "Cylinder Heads", "taktTime": 200},
        {"id": "line-transmission", "name": "Transmission Housing Line", "product": "Transmission Housings", "taktTime": 300},
    ]

    for line in lines:
        all_twins.append(prepare_manufacturing_twin({
            "id": line["id"],
            "type": "ProductionLine",
            "name": line["name"],
            "properties": {
                "productType": line["product"],
                "taktTime": line["taktTime"],
                "taktTimeUnit": "seconds",
                "status": "running",
                "currentOEE": 85.5,
                "targetOEE": 90,
                "shiftsPerDay": 3,
                "dailyTarget": 480,
                "dailyActual": 465
            }
        }))
        all_relationships.append(("area-machining", "containsLine", line["id"], None))

    # =========================================================================
    # CNC MACHINES
    # =========================================================================
    cnc_machines = [
        {"id": "cnc-001", "name": "CNC Mill DMG MORI #1", "type": "5-axis Mill", "line": "line-engine-block"},
        {"id": "cnc-002", "name": "CNC Mill DMG MORI #2", "type": "5-axis Mill", "line": "line-engine-block"},
        {"id": "cnc-003", "name": "CNC Mill DMG MORI #3", "type": "5-axis Mill", "line": "line-engine-block"},
        {"id": "cnc-004", "name": "CNC Lathe Mazak #1", "type": "CNC Lathe", "line": "line-crankshaft"},
        {"id": "cnc-005", "name": "CNC Lathe Mazak #2", "type": "CNC Lathe", "line": "line-crankshaft"},
        {"id": "cnc-006", "name": "CNC Grinder Studer", "type": "Cylindrical Grinder", "line": "line-crankshaft"},
        {"id": "cnc-007", "name": "CNC Mill Makino #1", "type": "Horizontal Mill", "line": "line-cylinder-head"},
        {"id": "cnc-008", "name": "CNC Mill Makino #2", "type": "Horizontal Mill", "line": "line-cylinder-head"},
        {"id": "cnc-009", "name": "CNC Boring Mill", "type": "Boring Mill", "line": "line-transmission"},
        {"id": "cnc-010", "name": "CNC Mill Haas", "type": "Vertical Mill", "line": "line-transmission"},
    ]

    for cnc in cnc_machines:
        all_twins.append(prepare_manufacturing_twin({
            "id": cnc["id"],
            "type": "CNCMachine",
            "name": cnc["name"],
            "properties": {
                "machineType": cnc["type"],
                "manufacturer": cnc["name"].split()[2] if len(cnc["name"].split()) > 2 else "Unknown",
                "status": "running",
                "spindleSpeed": 8000,
                "spindleSpeedUnit": "RPM",
                "spindleLoad": 65,
                "spindleLoadUnit": "percent",
                "feedRate": 500,
                "feedRateUnit": "mm/min",
                "powerConsumption": 45,
                "powerUnit": "kW",
                "coolantLevel": 85,
                "coolantTemp": 22,
                "partsProduced": 156,
                "partsTarget": 160,
                "cycleTime": 180,
                "cycleTimeUnit": "seconds",
                "lastMaintenance": "2026-11-15",
                "nextMaintenance": "2026-01-15",
                "totalRuntime": 15420,
                "runtimeUnit": "hours"
            }
        }))
        all_relationships.append((cnc["line"], "hasMachine", cnc["id"], None))

        # Add spindle sensor
        spindle_sensor_id = f"sensor-spindle-{cnc['id']}"
        all_twins.append(prepare_manufacturing_twin({
            "id": spindle_sensor_id,
            "type": "VibrationSensor",
            "name": f"Spindle Vibration Sensor - {cnc['name']}",
            "properties": {
                "manufacturer": "SKF",
                "model": "CMSS 2200",
                "currentValue": 2.5,
                "unit": "mm/s",
                "threshold": 4.5,
                "status": "normal",
                "lastReading": "2026-12-15T10:30:00Z"
            }
        }))
        all_relationships.append((spindle_sensor_id, "monitors", cnc["id"], None))

    # =========================================================================
    # INDUSTRIAL ROBOTS
    # =========================================================================
    robots = [
        {"id": "robot-001", "name": "KUKA Loading Robot #1", "type": "Material Handling", "payload": 210, "line": "line-engine-block"},
        {"id": "robot-002", "name": "KUKA Loading Robot #2", "type": "Material Handling", "payload": 210, "line": "line-engine-block"},
        {"id": "robot-003", "name": "Fanuc Welding Robot", "type": "Welding", "payload": 20, "line": "line-crankshaft"},
        {"id": "robot-004", "name": "ABB Assembly Robot", "type": "Assembly", "payload": 12, "line": "line-cylinder-head"},
        {"id": "robot-005", "name": "KUKA Palletizing Robot", "type": "Palletizing", "payload": 500, "line": "line-transmission"},
        {"id": "robot-006", "name": "Universal Robots UR10", "type": "Collaborative", "payload": 10, "line": "line-engine-block"},
    ]

    for robot in robots:
        all_twins.append(prepare_manufacturing_twin({
            "id": robot["id"],
            "type": "IndustrialRobot",
            "name": robot["name"],
            "properties": {
                "robotType": robot["type"],
                "manufacturer": robot["name"].split()[0],
                "payload": robot["payload"],
                "payloadUnit": "kg",
                "reach": 2500,
                "reachUnit": "mm",
                "axes": 6,
                "repeatability": 0.05,
                "repeatabilityUnit": "mm",
                "status": "running",
                "cycleCount": 125000,
                "programName": "MAIN_CYCLE",
                "jointPositions": [0, -45, 90, 0, 45, 0],
                "tcpSpeed": 1500,
                "tcpSpeedUnit": "mm/s",
                "lastMaintenance": "2026-10-20"
            }
        }))
        all_relationships.append((robot["line"], "hasRobot", robot["id"], None))

    # =========================================================================
    # CONVEYORS
    # =========================================================================
    conveyors = [
        {"id": "conveyor-001", "name": "Main In-Feed Conveyor", "type": "belt", "length": 50, "from": "area-receiving", "to": "area-machining"},
        {"id": "conveyor-002", "name": "Machining Transfer Conveyor", "type": "roller", "length": 30, "from": "area-machining", "to": "area-assembly"},
        {"id": "conveyor-003", "name": "Assembly Line Conveyor", "type": "chain", "length": 100, "from": "area-assembly", "to": "area-quality"},
        {"id": "conveyor-004", "name": "QC to Finishing Conveyor", "type": "belt", "length": 20, "from": "area-quality", "to": "area-finishing"},
        {"id": "conveyor-005", "name": "Finishing to Packaging", "type": "roller", "length": 40, "from": "area-finishing", "to": "area-packaging"},
    ]

    for conv in conveyors:
        all_twins.append(prepare_manufacturing_twin({
            "id": conv["id"],
            "type": "Conveyor",
            "name": conv["name"],
            "properties": {
                "conveyorType": conv["type"],
                "length": conv["length"],
                "lengthUnit": "meters",
                "width": 800,
                "widthUnit": "mm",
                "speed": 0.5,
                "speedUnit": "m/s",
                "motorPower": 5.5,
                "motorPowerUnit": "kW",
                "status": "running",
                "itemsPerHour": 120
            }
        }))
        all_relationships.append((conv["id"], "connectsFrom", conv["from"], None))
        all_relationships.append((conv["id"], "connectsTo", conv["to"], None))

    # =========================================================================
    # QUALITY CONTROL EQUIPMENT
    # =========================================================================
    qc_equipment = [
        {"id": "qc-cmm-001", "name": "CMM Zeiss Prismo", "type": "CoordinateMeasuringMachine"},
        {"id": "qc-cmm-002", "name": "CMM Hexagon Global", "type": "CoordinateMeasuringMachine"},
        {"id": "qc-vision-001", "name": "Vision System Keyence", "type": "VisionInspectionSystem"},
        {"id": "qc-xray-001", "name": "X-Ray Inspection YXLON", "type": "XRayInspectionSystem"},
        {"id": "qc-hardness-001", "name": "Hardness Tester Instron", "type": "HardnessTester"},
        {"id": "qc-roughness-001", "name": "Surface Roughness Tester", "type": "SurfaceRoughnessTester"},
    ]

    for qc in qc_equipment:
        all_twins.append(prepare_manufacturing_twin({
            "id": qc["id"],
            "type": qc["type"],
            "name": qc["name"],
            "properties": {
                "status": "available",
                "accuracy": 0.001 if "CMM" in qc["type"] else 0.01,
                "accuracyUnit": "mm",
                "calibrationDate": "2026-11-01",
                "nextCalibration": "2026-05-01",
                "partsInspectedToday": 45,
                "defectsFoundToday": 2
            }
        }))
        all_relationships.append(("area-quality", "hasEquipment", qc["id"], None))

    # =========================================================================
    # TOOLING
    # =========================================================================
    tools = [
        {"id": "tool-001", "name": "End Mill 20mm", "type": "EndMill", "diameter": 20, "machine": "cnc-001"},
        {"id": "tool-002", "name": "Face Mill 80mm", "type": "FaceMill", "diameter": 80, "machine": "cnc-001"},
        {"id": "tool-003", "name": "Drill 10mm", "type": "Drill", "diameter": 10, "machine": "cnc-002"},
        {"id": "tool-004", "name": "Boring Bar", "type": "BoringBar", "diameter": 50, "machine": "cnc-009"},
        {"id": "tool-005", "name": "Threading Tap M12", "type": "Tap", "diameter": 12, "machine": "cnc-003"},
    ]

    for tool in tools:
        all_twins.append(prepare_manufacturing_twin({
            "id": tool["id"],
            "type": "CuttingTool",
            "name": tool["name"],
            "properties": {
                "toolType": tool["type"],
                "diameter": tool["diameter"],
                "diameterUnit": "mm",
                "material": "Carbide",
                "coating": "TiAlN",
                "lifeRemaining": 75,
                "lifeUnit": "percent",
                "totalCuts": 4500,
                "maxCuts": 6000,
                "status": "in_use"
            }
        }))
        all_relationships.append((tool["machine"], "usesTool", tool["id"], None))

    # =========================================================================
    # WORKPIECES / WORK IN PROGRESS
    # =========================================================================
    workpieces = [
        {"id": "wip-001", "name": "Engine Block #EB-2026-1215-001", "type": "EngineBlock", "stage": "machining"},
        {"id": "wip-002", "name": "Engine Block #EB-2026-1215-002", "type": "EngineBlock", "stage": "machining"},
        {"id": "wip-003", "name": "Crankshaft #CS-2026-1215-001", "type": "Crankshaft", "stage": "grinding"},
        {"id": "wip-004", "name": "Cylinder Head #CH-2026-1215-001", "type": "CylinderHead", "stage": "assembly"},
        {"id": "wip-005", "name": "Transmission Housing #TH-2026-1215-001", "type": "TransmissionHousing", "stage": "quality"},
    ]

    for wp in workpieces:
        all_twins.append(prepare_manufacturing_twin({
            "id": wp["id"],
            "type": "Workpiece",
            "name": wp["name"],
            "properties": {
                "productType": wp["type"],
                "stage": wp["stage"],
                "batchNumber": "BATCH-2026-1215",
                "orderNumber": "PO-2026-5678",
                "material": "Aluminum Alloy 356" if wp["type"] in ["EngineBlock", "CylinderHead", "TransmissionHousing"] else "Steel 42CrMo4",
                "weight": 35 if wp["type"] == "EngineBlock" else 15,
                "weightUnit": "kg",
                "startTime": "2026-12-15T06:00:00Z",
                "dueDate": "2026-12-16T18:00:00Z",
                "qualityStatus": "pending"
            }
        }))

    # Connect workpieces to current machines
    all_relationships.append(("wip-001", "currentlyAt", "cnc-001", None))
    all_relationships.append(("wip-002", "currentlyAt", "cnc-002", None))
    all_relationships.append(("wip-003", "currentlyAt", "cnc-006", None))
    all_relationships.append(("wip-004", "currentlyAt", "robot-004", None))
    all_relationships.append(("wip-005", "currentlyAt", "qc-cmm-001", None))

    # =========================================================================
    # ENVIRONMENTAL SENSORS
    # =========================================================================
    for area in areas:
        if area["type"] in ["production", "inspection"]:
            # Temperature sensor
            temp_sensor_id = f"sensor-temp-{area['id']}"
            all_twins.append(prepare_manufacturing_twin({
                "id": temp_sensor_id,
                "type": "TemperatureSensor",
                "name": f"Temperature Sensor - {area['name']}",
                "properties": {
                    "currentValue": 22.5,
                    "unit": "Celsius",
                    "minThreshold": 18,
                    "maxThreshold": 26,
                    "status": "normal"
                }
            }))
            all_relationships.append((temp_sensor_id, "locatedIn", area["id"], None))

            # Humidity sensor
            humidity_sensor_id = f"sensor-humidity-{area['id']}"
            all_twins.append(prepare_manufacturing_twin({
                "id": humidity_sensor_id,
                "type": "HumiditySensor",
                "name": f"Humidity Sensor - {area['name']}",
                "properties": {
                    "currentValue": 45,
                    "unit": "percent",
                    "minThreshold": 30,
                    "maxThreshold": 60,
                    "status": "normal"
                }
            }))
            all_relationships.append((humidity_sensor_id, "locatedIn", area["id"], None))

    # =========================================================================
    # ENERGY METERS
    # =========================================================================
    all_twins.append(prepare_manufacturing_twin({
        "id": "energy-meter-main",
        "type": "EnergyMeter",
        "name": "Main Factory Energy Meter",
        "properties": {
            "currentPower": 850,
            "currentPowerUnit": "kW",
            "todayConsumption": 15200,
            "monthConsumption": 456000,
            "consumptionUnit": "kWh",
            "powerFactor": 0.92,
            "peakDemand": 1200,
            "peakDemandUnit": "kW"
        }
    }))
    all_relationships.append(("factory-munich-001", "hasEnergyMeter", "energy-meter-main", None))

    # =========================================================================
    # MAINTENANCE RECORDS
    # =========================================================================
    maintenance_tasks = [
        {"id": "maint-001", "machine": "cnc-001", "type": "Preventive", "description": "Spindle bearing replacement", "status": "scheduled", "date": "2026-01-15"},
        {"id": "maint-002", "machine": "cnc-004", "type": "Preventive", "description": "Coolant system flush", "status": "scheduled", "date": "2026-12-20"},
        {"id": "maint-003", "machine": "robot-001", "type": "Corrective", "description": "Gripper calibration", "status": "in_progress", "date": "2026-12-15"},
    ]

    for maint in maintenance_tasks:
        all_twins.append(prepare_manufacturing_twin({
            "id": maint["id"],
            "type": "MaintenanceTask",
            "name": f"Maintenance - {maint['description']}",
            "properties": {
                "maintenanceType": maint["type"],
                "description": maint["description"],
                "status": maint["status"],
                "scheduledDate": maint["date"],
                "estimatedDuration": 4,
                "durationUnit": "hours",
                "priority": "high" if maint["type"] == "Corrective" else "medium"
            }
        }))
        all_relationships.append((maint["id"], "targetMachine", maint["machine"], None))

    # =========================================================================
    # BULK CREATION
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_succeeded, twins_failed = bulk_create_twins(client, all_twins)

    logger.info(f"Creating {len(all_relationships)} relationships...")
    rels_succeeded, rels_failed = bulk_add_relationships(client, all_relationships)

    twins_created = twins_succeeded
    relationships_created = rels_succeeded

    print_summary("Manufacturing / Industry 4.0", twins_created, relationships_created)
    logger.info("Manufacturing digital twin seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_manufacturing()
