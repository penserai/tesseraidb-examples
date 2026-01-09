#!/usr/bin/env python3
"""
Automotive / Fleet Management Digital Twin Example

This example creates a comprehensive digital twin of a connected vehicle fleet,
including vehicles, telematics, maintenance, and charging infrastructure.

Domain: Automotive / Fleet Management
Use Cases:
  - Real-time vehicle tracking
  - Predictive maintenance
  - Driver behavior analysis
  - Fuel/energy optimization
  - Route optimization
  - Compliance and safety monitoring
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
DOMAIN = "automotive"
AUTO_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_automotive_twin(data: dict) -> dict:
    """Prepare a twin dict for the automotive domain with proper namespace.

    Returns the dict without making any API calls.
    """
    # Expand type to full URI if it's a short name
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{AUTO_NS}{twin_type}"

    # Add domain tag
    data["domain"] = DOMAIN

    return data


def seed_automotive():
    """Seed the automotive/fleet management digital twin."""
    client = get_client()

    # Collect all twins and relationships for bulk operations
    all_twins = []
    all_relationships = []

    # =========================================================================
    # FLEET
    # =========================================================================
    all_twins.append(prepare_automotive_twin({
        "id": "fleet-001",
        "type": "VehicleFleet",
        "name": "Metropolitan Delivery Fleet",
        "description": "Mixed fleet of delivery and service vehicles",
        "properties": {
            "company": "Metro Logistics Inc.",
            "totalVehicles": 150,
            "electricVehicles": 75,
            "hybridVehicles": 30,
            "conventionalVehicles": 45,
            "averageAge": 2.5,
            "ageUnit": "years",
            "serviceArea": "Greater Metropolitan Area",
            "headquarters": "Los Angeles, CA"
        }
    }))

    # =========================================================================
    # DEPOTS
    # =========================================================================
    depots = [
        {"id": "depot-central", "name": "Central Depot", "capacity": 80, "lat": 34.0522, "lng": -118.2437},
        {"id": "depot-north", "name": "North Valley Depot", "capacity": 40, "lat": 34.2011, "lng": -118.5373},
        {"id": "depot-south", "name": "South Bay Depot", "capacity": 30, "lat": 33.8358, "lng": -118.3406},
    ]

    for depot in depots:
        all_twins.append(prepare_automotive_twin({
            "id": depot["id"],
            "type": "VehicleDepot",
            "name": depot["name"],
            "properties": {
                "capacity": depot["capacity"],
                "currentVehicles": int(depot["capacity"] * 0.8),
                "coordinates": {"lat": depot["lat"], "lng": depot["lng"]},
                "chargingStations": depot["capacity"] // 4,
                "maintenanceBays": depot["capacity"] // 20,
                "fuelPumps": 4,
                "operatingHours": "24/7",
                "status": "operational"
            }
        }))
        all_relationships.append(("fleet-001", "hasDepot", depot["id"], None))

    # =========================================================================
    # ELECTRIC VEHICLES
    # =========================================================================
    ev_models = [
        {"model": "Transit Electric", "manufacturer": "Ford", "range": 203, "battery": 68},
        {"model": "e-Sprinter", "manufacturer": "Mercedes-Benz", "range": 248, "battery": 113},
        {"model": "Rivian EDV", "manufacturer": "Rivian", "range": 150, "battery": 100},
    ]

    for i in range(1, 76):
        model = ev_models[i % len(ev_models)]
        depot = depots[i % len(depots)]
        vehicle_id = f"ev-{i:04d}"

        all_twins.append(prepare_automotive_twin({
            "id": vehicle_id,
            "type": "ElectricVehicle",
            "name": f"EV {i:04d} - {model['model']}",
            "properties": {
                "vin": f"1HGBH41JXMN{100000 + i}",
                "manufacturer": model["manufacturer"],
                "model": model["model"],
                "year": 2023 if i > 30 else 2022,
                "batteryCapacity": model["battery"],
                "batteryCapacityUnit": "kWh",
                "range": model["range"],
                "rangeUnit": "miles",
                "currentBatteryLevel": 45 + (i % 50),
                "currentRange": int(model["range"] * (45 + (i % 50)) / 100),
                "odometer": 15000 + (i * 500),
                "odometerUnit": "miles",
                "status": "active" if i % 10 != 0 else "charging",
                "currentLocation": {
                    "lat": depot["lat"] + ((i % 10) * 0.01),
                    "lng": depot["lng"] - ((i % 10) * 0.01)
                },
                "speed": 35 if i % 10 != 0 else 0,
                "speedUnit": "mph",
                "lastService": "2026-10-15",
                "nextServiceDue": "2026-01-15",
                "licensePlate": f"EV{i:04d}CA"
            }
        }))
        all_relationships.append((vehicle_id, "basedAt", depot["id"], None))

    # =========================================================================
    # HYBRID VEHICLES
    # =========================================================================
    for i in range(1, 31):
        depot = depots[i % len(depots)]
        vehicle_id = f"hybrid-{i:04d}"

        all_twins.append(prepare_automotive_twin({
            "id": vehicle_id,
            "type": "HybridVehicle",
            "name": f"Hybrid {i:04d} - Pacifica PHEV",
            "properties": {
                "vin": f"2C4RC1N7XNR{200000 + i}",
                "manufacturer": "Chrysler",
                "model": "Pacifica PHEV",
                "year": 2022,
                "batteryCapacity": 16,
                "batteryCapacityUnit": "kWh",
                "electricRange": 32,
                "totalRange": 520,
                "rangeUnit": "miles",
                "fuelTankCapacity": 16.5,
                "fuelTankUnit": "gallons",
                "currentFuelLevel": 60 + (i % 35),
                "currentBatteryLevel": 40 + (i % 55),
                "odometer": 35000 + (i * 800),
                "odometerUnit": "miles",
                "status": "active",
                "currentLocation": {
                    "lat": depot["lat"] + ((i % 8) * 0.015),
                    "lng": depot["lng"] - ((i % 8) * 0.015)
                },
                "speed": 45,
                "speedUnit": "mph",
                "mpgCombined": 82,
                "lastService": "2026-09-20",
                "nextServiceDue": "2026-03-20",
                "licensePlate": f"HY{i:04d}CA"
            }
        }))
        all_relationships.append((vehicle_id, "basedAt", depot["id"], None))

    # =========================================================================
    # CONVENTIONAL VEHICLES
    # =========================================================================
    for i in range(1, 46):
        depot = depots[i % len(depots)]
        vehicle_id = f"ice-{i:04d}"
        is_heavy = i <= 15

        all_twins.append(prepare_automotive_twin({
            "id": vehicle_id,
            "type": "ConventionalVehicle",
            "name": f"ICE {i:04d} - {'F-750' if is_heavy else 'Transit'}",
            "properties": {
                "vin": f"1FDRF7A68PEA{300000 + i}",
                "manufacturer": "Ford",
                "model": "F-750" if is_heavy else "Transit 250",
                "year": 2021 if i > 20 else 2020,
                "fuelType": "diesel" if is_heavy else "gasoline",
                "fuelTankCapacity": 65 if is_heavy else 25,
                "fuelTankUnit": "gallons",
                "currentFuelLevel": 50 + (i % 45),
                "odometer": 65000 + (i * 1200),
                "odometerUnit": "miles",
                "payloadCapacity": 12000 if is_heavy else 3500,
                "payloadCapacityUnit": "lbs",
                "status": "active" if i % 8 != 0 else "maintenance",
                "currentLocation": {
                    "lat": depot["lat"] + ((i % 12) * 0.02),
                    "lng": depot["lng"] - ((i % 12) * 0.02)
                },
                "speed": 55 if i % 8 != 0 else 0,
                "speedUnit": "mph",
                "mpg": 12 if is_heavy else 18,
                "lastService": "2026-08-10",
                "nextServiceDue": "2026-12-10",
                "licensePlate": f"DL{i:04d}CA"
            }
        }))
        all_relationships.append((vehicle_id, "basedAt", depot["id"], None))

    # =========================================================================
    # TELEMATICS DEVICES
    # =========================================================================
    vehicle_ids = [f"ev-{i:04d}" for i in range(1, 76)] + \
                  [f"hybrid-{i:04d}" for i in range(1, 31)] + \
                  [f"ice-{i:04d}" for i in range(1, 46)]

    for vid in vehicle_ids[:50]:  # Sample of 50 vehicles
        telematics_id = f"telematics-{vid}"
        all_twins.append(prepare_automotive_twin({
            "id": telematics_id,
            "type": "TelematicsDevice",
            "name": f"Telematics - {vid}",
            "properties": {
                "manufacturer": "Geotab",
                "model": "GO9",
                "firmwareVersion": "2026.3.1",
                "updateRate": 10,
                "updateRateUnit": "seconds",
                "gpsPrecision": 2.5,
                "gpsPrecisionUnit": "meters",
                "hasAccelerometer": True,
                "hasOBDConnection": True,
                "hasDriverCamera": True,
                "cellularNetwork": "LTE",
                "signalStrength": 85,
                "status": "online",
                "lastCommunication": "2026-12-15T10:30:00Z"
            }
        }))
        all_relationships.append((telematics_id, "installedIn", vid, None))

    # =========================================================================
    # DRIVERS
    # =========================================================================
    for i in range(1, 121):
        driver_id = f"driver-{i:04d}"
        all_twins.append(prepare_automotive_twin({
            "id": driver_id,
            "type": "Driver",
            "name": f"Driver {i:04d}",
            "properties": {
                "employeeId": f"EMP{i:05d}",
                "licenseClass": "A" if i <= 20 else "B",
                "licenseExpiry": "2026-06-15",
                "yearsExperience": 3 + (i % 15),
                "safetyScore": 85 + (i % 15),
                "safetyScoreMax": 100,
                "totalMiles": 45000 + (i * 2000),
                "totalMilesUnit": "miles",
                "totalHours": 2500 + (i * 100),
                "totalHoursUnit": "hours",
                "assignedVehicle": vehicle_ids[i % len(vehicle_ids)],
                "status": "active",
                "currentDutyStatus": "driving" if i % 3 == 0 else ("on_break" if i % 3 == 1 else "off_duty"),
                "hoursAvailableToday": 6 + (i % 5)
            }
        }))
        all_relationships.append((driver_id, "assignedTo", vehicle_ids[i % len(vehicle_ids)], None))

    # =========================================================================
    # CHARGING STATIONS
    # =========================================================================
    charging_stations = [
        {"id": "charger-central-001", "depot": "depot-central", "type": "DC Fast", "power": 150, "ports": 8},
        {"id": "charger-central-002", "depot": "depot-central", "type": "DC Fast", "power": 150, "ports": 8},
        {"id": "charger-central-003", "depot": "depot-central", "type": "Level 2", "power": 19.2, "ports": 10},
        {"id": "charger-north-001", "depot": "depot-north", "type": "DC Fast", "power": 150, "ports": 6},
        {"id": "charger-north-002", "depot": "depot-north", "type": "Level 2", "power": 19.2, "ports": 8},
        {"id": "charger-south-001", "depot": "depot-south", "type": "DC Fast", "power": 100, "ports": 4},
        {"id": "charger-south-002", "depot": "depot-south", "type": "Level 2", "power": 19.2, "ports": 6},
    ]

    for charger in charging_stations:
        all_twins.append(prepare_automotive_twin({
            "id": charger["id"],
            "type": "ChargingStation",
            "name": f"{charger['type']} Charger - {charger['depot']}",
            "properties": {
                "chargerType": charger["type"],
                "maxPower": charger["power"],
                "powerUnit": "kW",
                "ports": charger["ports"],
                "portsInUse": charger["ports"] // 2,
                "manufacturer": "ChargePoint" if "DC" in charger["type"] else "ClipperCreek",
                "energyDeliveredToday": charger["power"] * 8,
                "energyUnit": "kWh",
                "sessionsToday": charger["ports"] * 3,
                "status": "operational",
                "networkConnected": True
            }
        }))
        all_relationships.append((charger["id"], "locatedAt", charger["depot"], None))

    # =========================================================================
    # MAINTENANCE RECORDS
    # =========================================================================
    maintenance_types = ["oil_change", "tire_rotation", "brake_inspection", "battery_check", "software_update"]

    for i in range(1, 31):
        maint_id = f"maintenance-{i:04d}"
        vehicle = vehicle_ids[i % len(vehicle_ids)]
        maint_type = maintenance_types[i % len(maintenance_types)]

        all_twins.append(prepare_automotive_twin({
            "id": maint_id,
            "type": "MaintenanceRecord",
            "name": f"Maintenance {i:04d} - {maint_type}",
            "properties": {
                "maintenanceType": maint_type,
                "status": "completed" if i <= 20 else ("scheduled" if i <= 25 else "in_progress"),
                "scheduledDate": "2026-12-10" if i <= 25 else "2026-12-15",
                "completedDate": "2026-12-10" if i <= 20 else None,
                "odometerAtService": 50000 + (i * 1000),
                "cost": 150 + (i * 25),
                "costCurrency": "USD",
                "technician": f"TECH-{i % 5 + 1:03d}",
                "notes": f"Routine {maint_type.replace('_', ' ')}"
            }
        }))
        all_relationships.append((maint_id, "forVehicle", vehicle, None))

    # =========================================================================
    # ROUTES
    # =========================================================================
    routes = [
        {"id": "route-001", "name": "Downtown Delivery Route", "stops": 25, "distance": 45},
        {"id": "route-002", "name": "North Valley Route", "stops": 30, "distance": 65},
        {"id": "route-003", "name": "South Bay Route", "stops": 20, "distance": 55},
        {"id": "route-004", "name": "Industrial Zone Route", "stops": 15, "distance": 35},
        {"id": "route-005", "name": "Residential West Route", "stops": 40, "distance": 50},
        {"id": "route-006", "name": "Airport Cargo Route", "stops": 8, "distance": 75},
    ]

    for route in routes:
        all_twins.append(prepare_automotive_twin({
            "id": route["id"],
            "type": "DeliveryRoute",
            "name": route["name"],
            "properties": {
                "totalStops": route["stops"],
                "totalDistance": route["distance"],
                "distanceUnit": "miles",
                "estimatedDuration": route["distance"] * 2,
                "durationUnit": "minutes",
                "optimized": True,
                "vehicleType": "electric" if route["distance"] < 60 else "hybrid",
                "frequency": "daily",
                "status": "active"
            }
        }))
        all_relationships.append(("fleet-001", "operates", route["id"], None))

    # =========================================================================
    # DELIVERIES / TRIPS
    # =========================================================================
    for i in range(1, 51):
        delivery_id = f"delivery-{i:05d}"
        route = routes[i % len(routes)]
        vehicle = vehicle_ids[i % len(vehicle_ids)]

        all_twins.append(prepare_automotive_twin({
            "id": delivery_id,
            "type": "Delivery",
            "name": f"Delivery {i:05d}",
            "properties": {
                "status": "completed" if i <= 30 else ("in_progress" if i <= 40 else "scheduled"),
                "startTime": "2026-12-15T06:00:00Z",
                "endTime": "2026-12-15T14:00:00Z" if i <= 30 else None,
                "stopsCompleted": route["stops"] if i <= 30 else (route["stops"] // 2 if i <= 40 else 0),
                "totalStops": route["stops"],
                "distanceTraveled": route["distance"] if i <= 30 else (route["distance"] / 2 if i <= 40 else 0),
                "distanceUnit": "miles",
                "packagesDelivered": route["stops"] * 3 if i <= 30 else 0,
                "onTimePercentage": 95 if i <= 30 else None
            }
        }))
        all_relationships.append((delivery_id, "usesVehicle", vehicle, None))
        all_relationships.append((delivery_id, "followsRoute", route["id"], None))

    # =========================================================================
    # SENSORS (Vehicle-Level)
    # =========================================================================
    sensor_types = [
        {"type": "TirePressureSensor", "unit": "PSI", "normal": 35},
        {"type": "BrakeWearSensor", "unit": "percent", "normal": 75},
        {"type": "BatteryHealthSensor", "unit": "percent", "normal": 95},
        {"type": "CoolantTemperatureSensor", "unit": "Celsius", "normal": 90},
    ]

    for i, vid in enumerate(vehicle_ids[:20]):  # Sample of 20 vehicles
        for sensor in sensor_types:
            sensor_id = f"sensor-{vid}-{sensor['type'].lower().replace('sensor', '')}"
            all_twins.append(prepare_automotive_twin({
                "id": sensor_id,
                "type": sensor["type"],
                "name": f"{sensor['type']} - {vid}",
                "properties": {
                    "currentValue": sensor["normal"] + ((i % 10) - 5),
                    "unit": sensor["unit"],
                    "normalRange": {"min": sensor["normal"] - 10, "max": sensor["normal"] + 10},
                    "status": "normal",
                    "lastReading": "2026-12-15T10:30:00Z"
                }
            }))
            all_relationships.append((sensor_id, "monitors", vid, None))

    # =========================================================================
    # FUEL CARDS
    # =========================================================================
    for i in range(1, 51):
        card_id = f"fuelcard-{i:04d}"
        vehicle = vehicle_ids[i % 46] if i <= 46 else vehicle_ids[30 + (i % 30)]

        all_twins.append(prepare_automotive_twin({
            "id": card_id,
            "type": "FuelCard",
            "name": f"Fuel Card {i:04d}",
            "properties": {
                "cardNumber": f"4000{i:08d}",
                "provider": "WEX",
                "monthlyLimit": 1000,
                "monthlySpent": 450 + (i * 10),
                "currency": "USD",
                "transactionsThisMonth": 15 + (i % 10),
                "gallonsThisMonth": 150 + (i * 5),
                "status": "active",
                "expiryDate": "2026-12-31"
            }
        }))
        all_relationships.append((card_id, "assignedTo", vehicle, None))

    # =========================================================================
    # FLEET MANAGEMENT SYSTEM
    # =========================================================================
    all_twins.append(prepare_automotive_twin({
        "id": "fms-001",
        "type": "FleetManagementSystem",
        "name": "Fleet Management Platform",
        "properties": {
            "vendor": "Samsara",
            "version": "2026.4",
            "connectedVehicles": 150,
            "activeDrivers": 120,
            "dailyTrips": 450,
            "totalMilesToday": 12500,
            "fuelCostToday": 2500,
            "electricityCostToday": 350,
            "currency": "USD",
            "alertsActive": 8,
            "status": "operational"
        }
    }))
    all_relationships.append(("fms-001", "manages", "fleet-001", None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, twins_failed = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships...")
    relationships_created, relationships_failed = bulk_add_relationships(client, all_relationships)

    print_summary("Automotive / Fleet Management", twins_created, relationships_created)
    logger.info("Automotive digital twin seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_automotive()
