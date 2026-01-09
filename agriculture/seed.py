#!/usr/bin/env python3
"""
Agriculture / Smart Farm Digital Twin Example

This example creates a comprehensive digital twin of a precision agriculture operation,
including fields, crops, irrigation, sensors, drones, and autonomous equipment.

Domain: Agriculture / AgriTech
Use Cases:
  - Precision irrigation management
  - Crop health monitoring
  - Yield prediction
  - Pest and disease detection
  - Autonomous farming equipment
  - Resource optimization (water, fertilizer, pesticides)
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
DOMAIN = "agriculture"
AGRI_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_agriculture_twin(data: dict) -> dict:
    """Prepare a twin dict for the agriculture domain with proper namespace.

    Returns the dict without making any API calls.
    """
    # Expand type to full URI if it's a short name
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{AGRI_NS}{twin_type}"

    # Add domain tag
    data["domain"] = DOMAIN

    return data


def seed_agriculture():
    """Seed the agriculture/smart farm digital twin."""
    client = get_client()

    # Collect all twins and relationships for bulk operations
    all_twins = []
    all_relationships = []

    # =========================================================================
    # FARM
    # =========================================================================
    all_twins.append(prepare_agriculture_twin({
        "id": "farm-sunrise-001",
        "type": "Farm",
        "name": "Sunrise Precision Farm",
        "description": "Modern precision agriculture operation with IoT integration",
        "properties": {
            "address": "15000 Agricultural Road, Fresno, CA 93706",
            "totalArea": 5000,
            "areaUnit": "acres",
            "cultivatedArea": 4500,
            "coordinates": {"lat": 36.7378, "lng": -119.7871},
            "elevation": 100,
            "elevationUnit": "meters",
            "climate": "Mediterranean",
            "soilType": "Sandy Loam",
            "waterSource": ["groundwater", "canal"],
            "certifications": ["USDA Organic", "GlobalGAP"],
            "employees": 45
        }
    }))

    # =========================================================================
    # FIELDS
    # =========================================================================
    fields = [
        {"id": "field-001", "name": "North Field A", "area": 500, "crop": "Almonds", "irrigation": "drip"},
        {"id": "field-002", "name": "North Field B", "area": 450, "crop": "Almonds", "irrigation": "drip"},
        {"id": "field-003", "name": "East Field A", "area": 600, "crop": "Tomatoes", "irrigation": "drip"},
        {"id": "field-004", "name": "East Field B", "area": 550, "crop": "Peppers", "irrigation": "drip"},
        {"id": "field-005", "name": "South Field A", "area": 700, "crop": "Cotton", "irrigation": "center_pivot"},
        {"id": "field-006", "name": "South Field B", "area": 650, "crop": "Corn", "irrigation": "center_pivot"},
        {"id": "field-007", "name": "West Field A", "area": 400, "crop": "Grapes", "irrigation": "drip"},
        {"id": "field-008", "name": "West Field B", "area": 350, "crop": "Citrus", "irrigation": "micro_sprinkler"},
        {"id": "field-009", "name": "Central Field", "area": 300, "crop": "Strawberries", "irrigation": "drip"},
    ]

    for field in fields:
        all_twins.append(prepare_agriculture_twin({
            "id": field["id"],
            "type": "AgriculturalField",
            "name": field["name"],
            "properties": {
                "area": field["area"],
                "areaUnit": "acres",
                "currentCrop": field["crop"],
                "irrigationType": field["irrigation"],
                "soilPH": 6.5 + (hash(field["id"]) % 10) / 10,
                "soilMoisture": 35 + (hash(field["id"]) % 20),
                "soilMoistureUnit": "percent",
                "organicMatter": 3.5,
                "organicMatterUnit": "percent",
                "lastTilled": "2026-03-15",
                "plantingDate": "2026-04-01",
                "expectedHarvest": "2026-10-15",
                "yieldEstimate": field["area"] * 2.5,
                "yieldUnit": "tons",
                "status": "growing"
            }
        }))
        all_relationships.append(("farm-sunrise-001", "hasField", field["id"], None))

    # =========================================================================
    # CROPS
    # =========================================================================
    crops = [
        {"id": "crop-almonds", "name": "Almonds", "type": "tree", "growthCycle": 210, "waterNeed": "medium"},
        {"id": "crop-tomatoes", "name": "Tomatoes", "type": "vegetable", "growthCycle": 120, "waterNeed": "high"},
        {"id": "crop-peppers", "name": "Peppers", "type": "vegetable", "growthCycle": 90, "waterNeed": "medium"},
        {"id": "crop-cotton", "name": "Cotton", "type": "fiber", "growthCycle": 180, "waterNeed": "medium"},
        {"id": "crop-corn", "name": "Corn", "type": "grain", "growthCycle": 100, "waterNeed": "high"},
        {"id": "crop-grapes", "name": "Grapes", "type": "vine", "growthCycle": 180, "waterNeed": "low"},
        {"id": "crop-citrus", "name": "Citrus", "type": "tree", "growthCycle": 365, "waterNeed": "medium"},
        {"id": "crop-strawberries", "name": "Strawberries", "type": "fruit", "growthCycle": 90, "waterNeed": "high"},
    ]

    for crop in crops:
        all_twins.append(prepare_agriculture_twin({
            "id": crop["id"],
            "type": "Crop",
            "name": crop["name"],
            "properties": {
                "cropType": crop["type"],
                "growthCycleDays": crop["growthCycle"],
                "waterRequirement": crop["waterNeed"],
                "optimalTemperature": {"min": 15, "max": 30},
                "temperatureUnit": "Celsius",
                "optimalPH": {"min": 6.0, "max": 7.0},
                "nitrogenNeed": "medium",
                "currentGrowthStage": "vegetative",
                "healthScore": 85 + (hash(crop["id"]) % 15)
            }
        }))

    # Link fields to crops
    field_crop_mapping = {
        "field-001": "crop-almonds",
        "field-002": "crop-almonds",
        "field-003": "crop-tomatoes",
        "field-004": "crop-peppers",
        "field-005": "crop-cotton",
        "field-006": "crop-corn",
        "field-007": "crop-grapes",
        "field-008": "crop-citrus",
        "field-009": "crop-strawberries",
    }

    for field_id, crop_id in field_crop_mapping.items():
        all_relationships.append((field_id, "grows", crop_id, None))

    # =========================================================================
    # IRRIGATION SYSTEM
    # =========================================================================
    all_twins.append(prepare_agriculture_twin({
        "id": "irrigation-controller",
        "type": "IrrigationController",
        "name": "Central Irrigation Controller",
        "properties": {
            "manufacturer": "Lindsay",
            "model": "FieldNET",
            "zones": 45,
            "activeZones": 12,
            "waterSource": "well",
            "totalCapacity": 5000,
            "capacityUnit": "gallons/minute",
            "status": "irrigating"
        }
    }))
    all_relationships.append(("farm-sunrise-001", "hasIrrigation", "irrigation-controller", None))

    # Irrigation zones per field
    for field in fields:
        zone_id = f"irrigation-zone-{field['id']}"
        all_twins.append(prepare_agriculture_twin({
            "id": zone_id,
            "type": "IrrigationZone",
            "name": f"Irrigation Zone - {field['name']}",
            "properties": {
                "irrigationType": field["irrigation"],
                "area": field["area"],
                "areaUnit": "acres",
                "emitterSpacing": 12 if field["irrigation"] == "drip" else 0,
                "emitterSpacingUnit": "inches",
                "flowRate": 200 if field["irrigation"] == "drip" else 800,
                "flowRateUnit": "gallons/minute",
                "currentStatus": "idle",
                "lastIrrigation": "2026-12-14T22:00:00Z",
                "nextScheduled": "2026-12-15T22:00:00Z",
                "waterAppliedToday": 0,
                "waterAppliedUnit": "acre-feet"
            }
        }))
        all_relationships.append(("irrigation-controller", "controls", zone_id, None))
        all_relationships.append((zone_id, "irrigates", field["id"], None))

    # =========================================================================
    # SOIL SENSORS
    # =========================================================================
    for field in fields:
        # Multiple sensors per field
        for i in range(1, 4):
            sensor_id = f"soil-sensor-{field['id']}-{i:02d}"
            all_twins.append(prepare_agriculture_twin({
                "id": sensor_id,
                "type": "SoilSensor",
                "name": f"Soil Sensor {i} - {field['name']}",
                "properties": {
                    "manufacturer": "Sentek",
                    "model": "Drill & Drop",
                    "depth": i * 12,
                    "depthUnit": "inches",
                    "moisture": 32 + (i * 3) + (hash(field["id"]) % 10),
                    "moistureUnit": "percent",
                    "temperature": 18 + (hash(sensor_id) % 5),
                    "temperatureUnit": "Celsius",
                    "electricalConductivity": 1.2 + (i * 0.2),
                    "ecUnit": "dS/m",
                    "batteryLevel": 85,
                    "lastReading": "2026-12-15T10:00:00Z",
                    "status": "online"
                }
            }))
            all_relationships.append((sensor_id, "monitors", field["id"], None))

    # =========================================================================
    # WEATHER STATIONS
    # =========================================================================
    weather_stations = [
        {"id": "weather-north", "name": "North Weather Station", "lat": 36.75, "lng": -119.78},
        {"id": "weather-south", "name": "South Weather Station", "lat": 36.72, "lng": -119.79},
        {"id": "weather-central", "name": "Central Weather Station", "lat": 36.74, "lng": -119.785},
    ]

    for station in weather_stations:
        all_twins.append(prepare_agriculture_twin({
            "id": station["id"],
            "type": "WeatherStation",
            "name": station["name"],
            "properties": {
                "manufacturer": "Davis Instruments",
                "model": "Vantage Pro2",
                "coordinates": {"lat": station["lat"], "lng": station["lng"]},
                "temperature": 22.5,
                "temperatureUnit": "Celsius",
                "humidity": 55,
                "humidityUnit": "percent",
                "windSpeed": 8,
                "windSpeedUnit": "km/h",
                "windDirection": 270,
                "solarRadiation": 650,
                "solarRadiationUnit": "W/m2",
                "rainfall": 0,
                "rainfallUnit": "mm",
                "evapotranspiration": 5.2,
                "etUnit": "mm/day",
                "lastReading": "2026-12-15T10:00:00Z",
                "status": "online"
            }
        }))
        all_relationships.append(("farm-sunrise-001", "hasWeatherStation", station["id"], None))

    # =========================================================================
    # DRONES
    # =========================================================================
    drones = [
        {"id": "drone-001", "name": "Survey Drone 1", "type": "survey", "payload": "multispectral"},
        {"id": "drone-002", "name": "Survey Drone 2", "type": "survey", "payload": "RGB"},
        {"id": "drone-003", "name": "Spray Drone 1", "type": "sprayer", "payload": "pesticide"},
        {"id": "drone-004", "name": "Spray Drone 2", "type": "sprayer", "payload": "fertilizer"},
    ]

    for drone in drones:
        all_twins.append(prepare_agriculture_twin({
            "id": drone["id"],
            "type": "AgriculturalDrone",
            "name": drone["name"],
            "properties": {
                "manufacturer": "DJI" if drone["type"] == "survey" else "XAG",
                "model": "Matrice 300 RTK" if drone["type"] == "survey" else "P100",
                "droneType": drone["type"],
                "payloadType": drone["payload"],
                "flightTime": 45,
                "flightTimeUnit": "minutes",
                "range": 15,
                "rangeUnit": "km",
                "batteryLevel": 80,
                "status": "idle",
                "totalFlightHours": 250,
                "lastMission": "2026-12-14T14:00:00Z",
                "firmwareVersion": "2026.3"
            }
        }))
        all_relationships.append(("farm-sunrise-001", "hasDrone", drone["id"], None))

    # =========================================================================
    # AUTONOMOUS TRACTORS
    # =========================================================================
    tractors = [
        {"id": "tractor-001", "name": "AutoTrac 1", "type": "autonomous", "power": 400},
        {"id": "tractor-002", "name": "AutoTrac 2", "type": "autonomous", "power": 400},
        {"id": "tractor-003", "name": "Tractor 3", "type": "assisted", "power": 300},
        {"id": "tractor-004", "name": "Tractor 4", "type": "assisted", "power": 250},
    ]

    for tractor in tractors:
        all_twins.append(prepare_agriculture_twin({
            "id": tractor["id"],
            "type": "AgriculturalTractor",
            "name": tractor["name"],
            "properties": {
                "manufacturer": "John Deere",
                "model": "8R 410" if tractor["power"] == 400 else "7R 350",
                "autonomyLevel": "full" if tractor["type"] == "autonomous" else "guidance",
                "horsepower": tractor["power"],
                "fuelType": "diesel",
                "fuelLevel": 75,
                "hoursOfOperation": 5500,
                "currentLocation": {"lat": 36.74, "lng": -119.79},
                "currentSpeed": 0,
                "speedUnit": "km/h",
                "attachedImplement": None,
                "status": "idle",
                "lastService": "2026-11-01",
                "nextService": "2026-02-01"
            }
        }))
        all_relationships.append(("farm-sunrise-001", "hasEquipment", tractor["id"], None))

    # =========================================================================
    # IMPLEMENTS
    # =========================================================================
    implements = [
        {"id": "implement-planter", "name": "Precision Planter", "type": "planter", "width": 40},
        {"id": "implement-sprayer", "name": "Field Sprayer", "type": "sprayer", "width": 120},
        {"id": "implement-harvester", "name": "Combine Harvester", "type": "harvester", "width": 30},
        {"id": "implement-tiller", "name": "Rotary Tiller", "type": "tillage", "width": 25},
        {"id": "implement-spreader", "name": "Fertilizer Spreader", "type": "spreader", "width": 60},
    ]

    for impl in implements:
        all_twins.append(prepare_agriculture_twin({
            "id": impl["id"],
            "type": "AgriculturalImplement",
            "name": impl["name"],
            "properties": {
                "implementType": impl["type"],
                "workingWidth": impl["width"],
                "widthUnit": "feet",
                "manufacturer": "John Deere",
                "compatibleTractors": ["tractor-001", "tractor-002", "tractor-003", "tractor-004"],
                "status": "available",
                "hoursOfUse": 1200,
                "lastCalibration": "2026-09-15"
            }
        }))
        all_relationships.append(("farm-sunrise-001", "hasEquipment", impl["id"], None))

    # =========================================================================
    # STORAGE FACILITIES
    # =========================================================================
    storage = [
        {"id": "storage-grain", "name": "Grain Silos", "type": "silo", "capacity": 100000, "unit": "bushels"},
        {"id": "storage-cold", "name": "Cold Storage", "type": "cold_storage", "capacity": 50000, "unit": "lbs"},
        {"id": "storage-chemical", "name": "Chemical Storage", "type": "chemical", "capacity": 10000, "unit": "gallons"},
        {"id": "storage-equipment", "name": "Equipment Barn", "type": "barn", "capacity": 20, "unit": "vehicles"},
    ]

    for stor in storage:
        all_twins.append(prepare_agriculture_twin({
            "id": stor["id"],
            "type": "StorageFacility",
            "name": stor["name"],
            "properties": {
                "storageType": stor["type"],
                "capacity": stor["capacity"],
                "capacityUnit": stor["unit"],
                "currentLevel": int(stor["capacity"] * 0.6),
                "temperature": -2 if stor["type"] == "cold_storage" else 20,
                "temperatureUnit": "Celsius",
                "humidity": 45,
                "status": "operational"
            }
        }))
        all_relationships.append(("farm-sunrise-001", "hasStorage", stor["id"], None))

    # =========================================================================
    # WATER SOURCES
    # =========================================================================
    water_sources = [
        {"id": "well-001", "name": "Deep Well 1", "type": "well", "depth": 400, "flow": 1500},
        {"id": "well-002", "name": "Deep Well 2", "type": "well", "depth": 350, "flow": 1200},
        {"id": "canal-001", "name": "Irrigation Canal Intake", "type": "canal", "flow": 3000},
        {"id": "pond-001", "name": "Retention Pond", "type": "pond", "capacity": 5000000},
    ]

    for source in water_sources:
        props = {
            "sourceType": source["type"],
            "status": "operational",
            "waterQualityIndex": 92,
            "lastTest": "2026-12-01"
        }

        if source["type"] == "well":
            props["depth"] = source["depth"]
            props["depthUnit"] = "feet"
            props["flowRate"] = source["flow"]
            props["flowRateUnit"] = "gallons/minute"
            props["pumpPower"] = 75
            props["pumpPowerUnit"] = "HP"
        elif source["type"] == "canal":
            props["allocation"] = source["flow"]
            props["allocationUnit"] = "gallons/minute"
        elif source["type"] == "pond":
            props["capacity"] = source["capacity"]
            props["capacityUnit"] = "gallons"
            props["currentLevel"] = int(source["capacity"] * 0.7)

        all_twins.append(prepare_agriculture_twin({
            "id": source["id"],
            "type": "WaterSource",
            "name": source["name"],
            "properties": props
        }))
        all_relationships.append(("irrigation-controller", "drawsFrom", source["id"], None))

    # =========================================================================
    # PEST MONITORING
    # =========================================================================
    pest_traps = [
        {"id": "trap-001", "field": "field-003", "pest": "aphids"},
        {"id": "trap-002", "field": "field-004", "pest": "whiteflies"},
        {"id": "trap-003", "field": "field-005", "pest": "boll_weevil"},
        {"id": "trap-004", "field": "field-006", "pest": "corn_borer"},
        {"id": "trap-005", "field": "field-007", "pest": "grape_berry_moth"},
    ]

    for trap in pest_traps:
        all_twins.append(prepare_agriculture_twin({
            "id": trap["id"],
            "type": "PestTrap",
            "name": f"Pest Trap - {trap['field']}",
            "properties": {
                "targetPest": trap["pest"],
                "trapType": "pheromone",
                "catchCount": hash(trap["id"]) % 50,
                "thresholdLevel": 25,
                "alertLevel": "low",
                "lastChecked": "2026-12-14T08:00:00Z",
                "batteryLevel": 90,
                "status": "active"
            }
        }))
        all_relationships.append((trap["id"], "monitors", trap["field"], None))

    # =========================================================================
    # CROP HEALTH CAMERAS
    # =========================================================================
    for i, field in enumerate(fields[:5]):
        camera_id = f"camera-{field['id']}"
        all_twins.append(prepare_agriculture_twin({
            "id": camera_id,
            "type": "CropHealthCamera",
            "name": f"Health Camera - {field['name']}",
            "properties": {
                "manufacturer": "Arable",
                "model": "Mark 3",
                "sensorTypes": ["RGB", "NDVI", "thermal"],
                "resolution": "12MP",
                "coverageArea": 50,
                "coverageUnit": "acres",
                "lastImage": "2026-12-15T06:00:00Z",
                "ndviValue": 0.75 + (i * 0.02),
                "cropStressIndex": 15 + (i * 2),
                "status": "online"
            }
        }))
        all_relationships.append((camera_id, "monitors", field["id"], None))

    # =========================================================================
    # FARM MANAGEMENT SYSTEM
    # =========================================================================
    all_twins.append(prepare_agriculture_twin({
        "id": "fms-001",
        "type": "FarmManagementSystem",
        "name": "Integrated Farm Management Platform",
        "properties": {
            "vendor": "Climate Corporation",
            "version": "2026.4",
            "connectedSensors": 150,
            "connectedEquipment": 15,
            "activeAlerts": 3,
            "waterUsageToday": 125000,
            "waterUsageUnit": "gallons",
            "fertilizerAppliedThisWeek": 5000,
            "fertilizerUnit": "lbs",
            "status": "operational"
        }
    }))
    all_relationships.append(("fms-001", "manages", "farm-sunrise-001", None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, twins_failed = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships...")
    relationships_created, relationships_failed = bulk_add_relationships(client, all_relationships)

    print_summary("Agriculture / Smart Farm", twins_created, relationships_created)
    logger.info("Agriculture digital twin seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_agriculture()
