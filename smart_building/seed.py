#!/usr/bin/env python3
"""
Smart Building Digital Twin Example

This example creates a comprehensive digital twin of a smart office building,
including floors, rooms, HVAC systems, sensors, and occupancy tracking.

Domain: Building Automation / IoT
Use Cases:
  - Energy management and optimization
  - Occupancy-based HVAC control
  - Predictive maintenance
  - Space utilization analytics
  - Indoor environmental quality monitoring

Performance: Uses bulk API for fast seeding against remote servers.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import (
    get_client, print_summary, logger,
    upload_ontology_safe, DOMAIN_NAMESPACES,
    create_twins_with_lineage, bulk_add_relationships
)

# Domain for this seed script
DOMAIN = "smart_building"
BLDG_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_smart_building_twin(data: dict) -> dict:
    """Prepare twin data with proper namespace and domain tag.

    Accepts the same dict format as create_twin_safe, but expands the type
    to use the full smart_building ontology namespace.
    """
    # Expand type to full URI if it's a short name
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{BLDG_NS}{twin_type}"

    # Add domain tag
    data["domain"] = DOMAIN

    return data


def seed_smart_building():
    """Seed the smart building digital twin using bulk API for performance."""
    client = get_client()
    ontologies_uploaded = 0

    # Collect all twins and relationships for bulk operations
    all_twins = []
    all_relationships = []  # (source_id, rel_type, target_id, properties)

    # =========================================================================
    # ONTOLOGY (uploaded via API for lineage tracking)
    # =========================================================================
    ontology_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "ontologies",
        "smart_building.ttl"
    )
    if upload_ontology_safe(client, "smart-building-ontology", ontology_path):
        ontologies_uploaded += 1
        logger.info("Smart Building ontology uploaded with lineage tracking")

    # =========================================================================
    # BUILDING
    # =========================================================================
    all_twins.append(prepare_smart_building_twin({
        "id": "building-hq-001",
        "type": "Building",
        "name": "TechCorp Headquarters",
        "description": "Main corporate office building with smart building systems",
        "properties": {
            "address": "123 Innovation Drive, San Francisco, CA 94105",
            "totalFloors": 10,
            "totalArea": 50000,
            "areaUnit": "sqm",
            "yearBuilt": 2019,
            "certification": "LEED Platinum",
            "coordinates": {"lat": 37.7749, "lng": -122.4194},
            "timezone": "America/Los_Angeles"
        }
    }))

    # =========================================================================
    # FLOORS
    # =========================================================================
    floor_configs = [
        {"id": "floor-lobby", "name": "Lobby", "level": 0, "area": 3000, "type": "public"},
        {"id": "floor-1", "name": "Floor 1 - Reception & Cafeteria", "level": 1, "area": 5000, "type": "amenity"},
        {"id": "floor-2", "name": "Floor 2 - Engineering", "level": 2, "area": 5000, "type": "office"},
        {"id": "floor-3", "name": "Floor 3 - Engineering", "level": 3, "area": 5000, "type": "office"},
        {"id": "floor-4", "name": "Floor 4 - Product & Design", "level": 4, "area": 5000, "type": "office"},
        {"id": "floor-5", "name": "Floor 5 - Sales & Marketing", "level": 5, "area": 5000, "type": "office"},
        {"id": "floor-6", "name": "Floor 6 - Executive", "level": 6, "area": 5000, "type": "executive"},
        {"id": "floor-7", "name": "Floor 7 - Data Center", "level": 7, "area": 5000, "type": "technical"},
        {"id": "floor-8", "name": "Floor 8 - Conference Center", "level": 8, "area": 5000, "type": "meeting"},
        {"id": "floor-9", "name": "Floor 9 - Rooftop Garden", "level": 9, "area": 2000, "type": "amenity"},
    ]

    for fc in floor_configs:
        all_twins.append(prepare_smart_building_twin({
            "id": fc["id"],
            "type": "Floor",
            "name": fc["name"],
            "properties": {
                "level": fc["level"],
                "area": fc["area"],
                "areaUnit": "sqm",
                "floorType": fc["type"],
                "maxOccupancy": fc["area"] // 10
            }
        }))
        all_relationships.append(("building-hq-001", "hasFloor", fc["id"], None))

    # =========================================================================
    # ROOMS (for Floor 2 - Engineering)
    # =========================================================================
    rooms = [
        {"id": "room-2-101", "name": "Open Office Area A", "type": "openOffice", "area": 800, "capacity": 50},
        {"id": "room-2-102", "name": "Open Office Area B", "type": "openOffice", "area": 800, "capacity": 50},
        {"id": "room-2-103", "name": "Meeting Room - Alpha", "type": "meetingRoom", "area": 30, "capacity": 8},
        {"id": "room-2-104", "name": "Meeting Room - Beta", "type": "meetingRoom", "area": 30, "capacity": 8},
        {"id": "room-2-105", "name": "Focus Room 1", "type": "focusRoom", "area": 10, "capacity": 2},
        {"id": "room-2-106", "name": "Focus Room 2", "type": "focusRoom", "area": 10, "capacity": 2},
        {"id": "room-2-107", "name": "Server Closet", "type": "technical", "area": 20, "capacity": 2},
        {"id": "room-2-108", "name": "Kitchen & Break Room", "type": "breakRoom", "area": 100, "capacity": 20},
        {"id": "room-2-109", "name": "Phone Booth 1", "type": "phoneBooth", "area": 4, "capacity": 1},
        {"id": "room-2-110", "name": "Phone Booth 2", "type": "phoneBooth", "area": 4, "capacity": 1},
    ]

    for room in rooms:
        all_twins.append(prepare_smart_building_twin({
            "id": room["id"],
            "type": "Room",
            "name": room["name"],
            "properties": {
                "roomType": room["type"],
                "area": room["area"],
                "areaUnit": "sqm",
                "maxOccupancy": room["capacity"],
                "hasWindows": room["type"] in ["openOffice", "meetingRoom"],
                "isBookable": room["type"] in ["meetingRoom", "focusRoom", "phoneBooth"]
            }
        }))
        all_relationships.append(("floor-2", "hasRoom", room["id"], None))

    # =========================================================================
    # HVAC SYSTEM
    # =========================================================================
    all_twins.append(prepare_smart_building_twin({
        "id": "hvac-plant-001",
        "type": "HVACPlant",
        "name": "Main HVAC Plant",
        "description": "Central heating, ventilation, and air conditioning plant",
        "properties": {
            "manufacturer": "Carrier",
            "model": "AquaEdge 23XRV",
            "coolingCapacity": 500,
            "coolingCapacityUnit": "tons",
            "heatingCapacity": 2000,
            "heatingCapacityUnit": "kW",
            "installDate": "2019-03-15",
            "lastMaintenance": "2024-11-01",
            "status": "operational"
        }
    }))
    all_relationships.append(("building-hq-001", "hasSystem", "hvac-plant-001", None))

    # Air Handling Units (one per floor)
    for i, floor in enumerate(floor_configs[1:8]):  # Floors 1-7
        ahu_id = f"ahu-{i+1:03d}"
        all_twins.append(prepare_smart_building_twin({
            "id": ahu_id,
            "type": "AirHandlingUnit",
            "name": f"AHU {floor['name']}",
            "properties": {
                "manufacturer": "Trane",
                "model": "IntelliPak",
                "airflowCapacity": 5000,
                "airflowUnit": "CFM",
                "filterType": "MERV-13",
                "hasHeatRecovery": True,
                "status": "operational"
            }
        }))
        all_relationships.append(("hvac-plant-001", "suppliesTo", ahu_id, None))
        all_relationships.append((ahu_id, "servesFloor", floor["id"], None))

    # VAV Boxes for Floor 2 rooms
    for room in rooms[:6]:  # Office and meeting rooms
        vav_id = f"vav-{room['id']}"
        all_twins.append(prepare_smart_building_twin({
            "id": vav_id,
            "type": "VAVBox",
            "name": f"VAV Box - {room['name']}",
            "properties": {
                "minAirflow": 100,
                "maxAirflow": 500,
                "airflowUnit": "CFM",
                "hasReheat": True,
                "damperPosition": 50,
                "status": "operational"
            }
        }))
        all_relationships.append(("ahu-001", "suppliesTo", vav_id, None))
        all_relationships.append((vav_id, "servesRoom", room["id"], None))

    # =========================================================================
    # SENSORS
    # =========================================================================
    # Temperature sensors in each room
    for room in rooms:
        sensor_id = f"sensor-temp-{room['id']}"
        all_twins.append(prepare_smart_building_twin({
            "id": sensor_id,
            "type": "TemperatureSensor",
            "name": f"Temperature Sensor - {room['name']}",
            "properties": {
                "manufacturer": "Honeywell",
                "model": "T6 Pro",
                "unit": "Celsius",
                "accuracy": 0.5,
                "currentValue": 22.5,
                "minValue": -10,
                "maxValue": 50,
                "lastReading": "2024-12-15T10:30:00Z",
                "status": "online"
            }
        }))
        all_relationships.append((sensor_id, "locatedIn", room["id"], None))

    # CO2 sensors in larger rooms
    for room in [r for r in rooms if r["type"] in ["openOffice", "meetingRoom", "breakRoom"]]:
        sensor_id = f"sensor-co2-{room['id']}"
        all_twins.append(prepare_smart_building_twin({
            "id": sensor_id,
            "type": "CO2Sensor",
            "name": f"CO2 Sensor - {room['name']}",
            "properties": {
                "manufacturer": "Sensirion",
                "model": "SCD41",
                "unit": "ppm",
                "accuracy": 50,
                "currentValue": 450,
                "threshold": 1000,
                "lastReading": "2024-12-15T10:30:00Z",
                "status": "online"
            }
        }))
        all_relationships.append((sensor_id, "locatedIn", room["id"], None))

    # Occupancy sensors
    for room in rooms:
        sensor_id = f"sensor-occupancy-{room['id']}"
        all_twins.append(prepare_smart_building_twin({
            "id": sensor_id,
            "type": "OccupancySensor",
            "name": f"Occupancy Sensor - {room['name']}",
            "properties": {
                "manufacturer": "Philips",
                "model": "OccuSwitch",
                "sensorType": "PIR",
                "currentOccupancy": 0,
                "isOccupied": False,
                "lastMotionDetected": "2024-12-15T09:45:00Z",
                "status": "online"
            }
        }))
        all_relationships.append((sensor_id, "locatedIn", room["id"], None))

    # Humidity sensors in key areas
    for room in [r for r in rooms if r["type"] in ["openOffice", "technical"]]:
        sensor_id = f"sensor-humidity-{room['id']}"
        all_twins.append(prepare_smart_building_twin({
            "id": sensor_id,
            "type": "HumiditySensor",
            "name": f"Humidity Sensor - {room['name']}",
            "properties": {
                "manufacturer": "Sensirion",
                "model": "SHT45",
                "unit": "percent",
                "accuracy": 2,
                "currentValue": 45,
                "minValue": 0,
                "maxValue": 100,
                "lastReading": "2024-12-15T10:30:00Z",
                "status": "online"
            }
        }))
        all_relationships.append((sensor_id, "locatedIn", room["id"], None))

    # =========================================================================
    # LIGHTING SYSTEM
    # =========================================================================
    all_twins.append(prepare_smart_building_twin({
        "id": "lighting-controller-001",
        "type": "LightingController",
        "name": "Main Lighting Controller",
        "properties": {
            "manufacturer": "Lutron",
            "model": "Vive Hub",
            "protocol": "DALI",
            "totalZones": 50,
            "status": "operational"
        }
    }))
    all_relationships.append(("building-hq-001", "hasSystem", "lighting-controller-001", None))

    # Light fixtures in each room
    for room in rooms:
        fixture_id = f"light-{room['id']}"
        num_fixtures = room["area"] // 15  # Roughly 1 fixture per 15 sqm
        all_twins.append(prepare_smart_building_twin({
            "id": fixture_id,
            "type": "LightingZone",
            "name": f"Lighting - {room['name']}",
            "properties": {
                "fixtureCount": num_fixtures,
                "fixtureType": "LED Panel",
                "wattagePerFixture": 40,
                "colorTemperature": 4000,
                "colorTemperatureUnit": "K",
                "isDimmable": True,
                "currentLevel": 80,
                "status": "on"
            }
        }))
        all_relationships.append(("lighting-controller-001", "controls", fixture_id, None))
        all_relationships.append((fixture_id, "illuminates", room["id"], None))

    # =========================================================================
    # ELECTRICAL SYSTEM
    # =========================================================================
    all_twins.append(prepare_smart_building_twin({
        "id": "electrical-main-panel",
        "type": "ElectricalPanel",
        "name": "Main Electrical Distribution Panel",
        "properties": {
            "voltage": 480,
            "voltageUnit": "V",
            "capacity": 2000,
            "capacityUnit": "A",
            "phases": 3,
            "manufacturer": "Schneider Electric",
            "status": "operational"
        }
    }))
    all_relationships.append(("building-hq-001", "hasSystem", "electrical-main-panel", None))

    # Sub-panels per floor
    for floor in floor_configs[1:8]:
        panel_id = f"electrical-panel-{floor['id']}"
        all_twins.append(prepare_smart_building_twin({
            "id": panel_id,
            "type": "ElectricalPanel",
            "name": f"Electrical Panel - {floor['name']}",
            "properties": {
                "voltage": 208,
                "voltageUnit": "V",
                "capacity": 200,
                "capacityUnit": "A",
                "phases": 3,
                "status": "operational"
            }
        }))
        all_relationships.append(("electrical-main-panel", "feedsTo", panel_id, None))
        all_relationships.append((panel_id, "servesFloor", floor["id"], None))

    # Power meters
    all_twins.append(prepare_smart_building_twin({
        "id": "power-meter-main",
        "type": "PowerMeter",
        "name": "Main Building Power Meter",
        "properties": {
            "manufacturer": "Schneider Electric",
            "model": "ION9000",
            "currentPower": 450,
            "currentPowerUnit": "kW",
            "todayConsumption": 5400,
            "monthConsumption": 162000,
            "consumptionUnit": "kWh",
            "powerFactor": 0.95,
            "lastReading": "2024-12-15T10:30:00Z",
            "status": "online"
        }
    }))
    all_relationships.append(("power-meter-main", "monitors", "electrical-main-panel", None))

    # =========================================================================
    # ELEVATORS
    # =========================================================================
    for i in range(1, 5):
        elevator_id = f"elevator-{i:03d}"
        all_twins.append(prepare_smart_building_twin({
            "id": elevator_id,
            "type": "Elevator",
            "name": f"Elevator {i}",
            "properties": {
                "manufacturer": "Otis",
                "model": "Gen2",
                "capacity": 1600,
                "capacityUnit": "kg",
                "maxPersons": 21,
                "currentFloor": i,
                "direction": "idle",
                "status": "operational",
                "lastMaintenance": "2024-10-15"
            }
        }))
        all_relationships.append(("building-hq-001", "hasElevator", elevator_id, None))

    # =========================================================================
    # FIRE SAFETY SYSTEM
    # =========================================================================
    all_twins.append(prepare_smart_building_twin({
        "id": "fire-panel-main",
        "type": "FireAlarmPanel",
        "name": "Main Fire Alarm Control Panel",
        "properties": {
            "manufacturer": "Notifier",
            "model": "NFS2-3030",
            "totalZones": 100,
            "activeAlarms": 0,
            "status": "armed",
            "lastTest": "2024-12-01"
        }
    }))
    all_relationships.append(("building-hq-001", "hasSystem", "fire-panel-main", None))

    # Smoke detectors per floor
    for floor in floor_configs:
        detector_id = f"smoke-detector-{floor['id']}"
        all_twins.append(prepare_smart_building_twin({
            "id": detector_id,
            "type": "SmokeDetector",
            "name": f"Smoke Detectors - {floor['name']}",
            "properties": {
                "count": floor["area"] // 50,  # 1 detector per 50 sqm
                "type": "photoelectric",
                "status": "normal",
                "lastTest": "2024-12-01"
            }
        }))
        all_relationships.append(("fire-panel-main", "monitors", detector_id, None))
        all_relationships.append((detector_id, "protectsFloor", floor["id"], None))

    # =========================================================================
    # ACCESS CONTROL SYSTEM
    # =========================================================================
    all_twins.append(prepare_smart_building_twin({
        "id": "access-control-main",
        "type": "AccessControlSystem",
        "name": "Main Access Control System",
        "properties": {
            "manufacturer": "HID Global",
            "model": "Aero Controller",
            "totalDoors": 150,
            "totalCardholders": 500,
            "status": "operational"
        }
    }))
    all_relationships.append(("building-hq-001", "hasSystem", "access-control-main", None))

    # Card readers for Floor 2 rooms
    for room in [r for r in rooms if r["type"] in ["meetingRoom", "focusRoom", "technical"]]:
        reader_id = f"card-reader-{room['id']}"
        all_twins.append(prepare_smart_building_twin({
            "id": reader_id,
            "type": "CardReader",
            "name": f"Card Reader - {room['name']}",
            "properties": {
                "manufacturer": "HID Global",
                "model": "iCLASS SE",
                "technology": "RFID",
                "status": "online",
                "lastAccess": "2024-12-15T09:30:00Z"
            }
        }))
        all_relationships.append(("access-control-main", "controls", reader_id, None))
        all_relationships.append((reader_id, "securesAccess", room["id"], None))

    # =========================================================================
    # WATER SYSTEM
    # =========================================================================
    all_twins.append(prepare_smart_building_twin({
        "id": "water-meter-main",
        "type": "WaterMeter",
        "name": "Main Water Meter",
        "properties": {
            "manufacturer": "Badger Meter",
            "model": "E-Series",
            "todayConsumption": 5000,
            "monthConsumption": 150000,
            "consumptionUnit": "liters",
            "flowRate": 50,
            "flowRateUnit": "liters/min",
            "lastReading": "2024-12-15T10:30:00Z",
            "status": "online"
        }
    }))
    all_relationships.append(("building-hq-001", "hasSystem", "water-meter-main", None))

    # =========================================================================
    # CREATION WITH LINEAGE TRACKING
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins with lineage tracking...")
    twins_succeeded, twins_failed = create_twins_with_lineage(client, all_twins)

    logger.info(f"Creating {len(all_relationships)} relationships...")
    rels_succeeded, rels_failed = bulk_add_relationships(client, all_relationships)

    twins_created = twins_succeeded
    relationships_created = rels_succeeded

    print_summary("Smart Building", twins_created, relationships_created, ontologies_uploaded)
    logger.info("Smart Building digital twin seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created,
        "ontologies_uploaded": ontologies_uploaded
    }


if __name__ == "__main__":
    seed_smart_building()
