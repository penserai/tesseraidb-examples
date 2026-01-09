#!/usr/bin/env python3
"""
Smart City Digital Twin Example

This example creates a comprehensive digital twin of a smart city,
including transportation, utilities, public safety, and environmental monitoring.

Domain: Smart City / Urban Planning
Use Cases:
  - Traffic management and optimization
  - Public transit coordination
  - Utility management (water, electricity, gas)
  - Environmental monitoring (air quality, noise)
  - Emergency response coordination
  - Urban planning and simulation
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
DOMAIN = "smart_city"
CITY_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_smart_city_twin(data: dict) -> dict:
    """Prepare a twin dict for the smart_city domain with proper namespace.

    Returns the dict without making any API calls.
    """
    # Expand type to full URI if it's a short name
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{CITY_NS}{twin_type}"

    # Add domain tag
    data["domain"] = DOMAIN

    return data


def seed_smart_city():
    """Seed the smart city digital twin."""
    client = get_client()

    # Collect all twins and relationships for bulk operations
    all_twins = []
    all_relationships = []

    # =========================================================================
    # CITY
    # =========================================================================
    all_twins.append(prepare_smart_city_twin({
        "id": "city-metropolis",
        "type": "City",
        "name": "Metropolis Smart City",
        "description": "Model smart city with integrated IoT infrastructure",
        "properties": {
            "country": "USA",
            "state": "California",
            "population": 850000,
            "area": 320,
            "areaUnit": "sq_km",
            "timezone": "America/Los_Angeles",
            "coordinates": {"lat": 37.5, "lng": -122.0},
            "mayor": "Jane Smith",
            "smartCityRating": "A+"
        }
    }))

    # =========================================================================
    # DISTRICTS
    # =========================================================================
    districts = [
        {"id": "district-downtown", "name": "Downtown", "type": "commercial", "population": 50000, "area": 15},
        {"id": "district-tech-park", "name": "Tech Park", "type": "business", "population": 25000, "area": 20},
        {"id": "district-harbor", "name": "Harbor District", "type": "industrial", "population": 15000, "area": 35},
        {"id": "district-riverside", "name": "Riverside", "type": "residential", "population": 120000, "area": 45},
        {"id": "district-greenvalley", "name": "Green Valley", "type": "residential", "population": 180000, "area": 60},
        {"id": "district-university", "name": "University District", "type": "educational", "population": 80000, "area": 25},
        {"id": "district-airport", "name": "Airport Zone", "type": "transportation", "population": 5000, "area": 40},
        {"id": "district-old-town", "name": "Old Town", "type": "historic", "population": 35000, "area": 12},
    ]

    for dist in districts:
        all_twins.append(prepare_smart_city_twin({
            "id": dist["id"],
            "type": "District",
            "name": dist["name"],
            "properties": {
                "districtType": dist["type"],
                "population": dist["population"],
                "area": dist["area"],
                "areaUnit": "sq_km",
                "populationDensity": dist["population"] / dist["area"]
            }
        }))
        all_relationships.append(("city-metropolis", "hasDistrict", dist["id"], None))

    # =========================================================================
    # ROADS & INTERSECTIONS
    # =========================================================================
    major_roads = [
        {"id": "road-main-st", "name": "Main Street", "type": "arterial", "lanes": 6, "length": 8.5},
        {"id": "road-broadway", "name": "Broadway Avenue", "type": "arterial", "lanes": 4, "length": 12.0},
        {"id": "road-highway-101", "name": "Highway 101", "type": "highway", "lanes": 8, "length": 25.0},
        {"id": "road-tech-blvd", "name": "Technology Boulevard", "type": "arterial", "lanes": 4, "length": 5.5},
        {"id": "road-harbor-rd", "name": "Harbor Road", "type": "arterial", "lanes": 4, "length": 7.0},
        {"id": "road-university-ave", "name": "University Avenue", "type": "collector", "lanes": 2, "length": 3.5},
    ]

    for road in major_roads:
        all_twins.append(prepare_smart_city_twin({
            "id": road["id"],
            "type": "Road",
            "name": road["name"],
            "properties": {
                "roadType": road["type"],
                "lanes": road["lanes"],
                "length": road["length"],
                "lengthUnit": "km",
                "speedLimit": 65 if road["type"] == "highway" else (45 if road["type"] == "arterial" else 35),
                "speedUnit": "mph",
                "surfaceCondition": "good",
                "lastMaintenance": "2026-06-15"
            }
        }))
        all_relationships.append(("city-metropolis", "hasRoad", road["id"], None))

    # Traffic intersections
    intersections = [
        {"id": "intersection-001", "name": "Main & Broadway", "roads": ["road-main-st", "road-broadway"], "lat": 37.51, "lng": -122.01},
        {"id": "intersection-002", "name": "Main & Tech Blvd", "roads": ["road-main-st", "road-tech-blvd"], "lat": 37.52, "lng": -122.02},
        {"id": "intersection-003", "name": "Broadway & University", "roads": ["road-broadway", "road-university-ave"], "lat": 37.50, "lng": -122.03},
        {"id": "intersection-004", "name": "Harbor & Main", "roads": ["road-harbor-rd", "road-main-st"], "lat": 37.49, "lng": -122.01},
    ]

    for inter in intersections:
        all_twins.append(prepare_smart_city_twin({
            "id": inter["id"],
            "type": "TrafficIntersection",
            "name": inter["name"],
            "properties": {
                "coordinates": {"lat": inter["lat"], "lng": inter["lng"]},
                "signalType": "adaptive",
                "hasCamera": True,
                "hasPedestrianCrossing": True,
                "averageWaitTime": 45,
                "waitTimeUnit": "seconds",
                "currentPhase": "NS_Green"
            }
        }))
        for road_id in inter["roads"]:
            all_relationships.append((inter["id"], "connectsRoad", road_id, None))

    # Traffic signals
    for inter in intersections:
        signal_id = f"traffic-signal-{inter['id']}"
        all_twins.append(prepare_smart_city_twin({
            "id": signal_id,
            "type": "TrafficSignal",
            "name": f"Traffic Signal - {inter['name']}",
            "properties": {
                "manufacturer": "Siemens",
                "model": "SCOOT",
                "cycleTime": 120,
                "cycleTimeUnit": "seconds",
                "mode": "adaptive",
                "lastMaintenance": "2026-10-01",
                "status": "operational"
            }
        }))
        all_relationships.append((signal_id, "controlsIntersection", inter["id"], None))

    # =========================================================================
    # TRAFFIC SENSORS
    # =========================================================================
    for road in major_roads:
        sensor_id = f"traffic-sensor-{road['id']}"
        all_twins.append(prepare_smart_city_twin({
            "id": sensor_id,
            "type": "TrafficSensor",
            "name": f"Traffic Sensor - {road['name']}",
            "properties": {
                "sensorType": "inductive_loop",
                "vehicleCount": 1250,
                "averageSpeed": 42,
                "speedUnit": "mph",
                "occupancy": 35,
                "lastReading": "2026-12-15T10:30:00Z",
                "status": "online"
            }
        }))
        all_relationships.append((sensor_id, "monitors", road["id"], None))

    # =========================================================================
    # PUBLIC TRANSIT
    # =========================================================================
    # Metro/Subway Lines
    metro_lines = [
        {"id": "metro-red", "name": "Red Line", "color": "red", "stations": 12, "length": 18.5},
        {"id": "metro-blue", "name": "Blue Line", "color": "blue", "stations": 15, "length": 22.0},
        {"id": "metro-green", "name": "Green Line", "color": "green", "stations": 10, "length": 14.0},
    ]

    for line in metro_lines:
        all_twins.append(prepare_smart_city_twin({
            "id": line["id"],
            "type": "MetroLine",
            "name": line["name"],
            "properties": {
                "color": line["color"],
                "stations": line["stations"],
                "length": line["length"],
                "lengthUnit": "km",
                "headway": 5,
                "headwayUnit": "minutes",
                "dailyRidership": 45000,
                "operatingHours": "5:00-24:00",
                "status": "operational"
            }
        }))
        all_relationships.append(("city-metropolis", "hasMetroLine", line["id"], None))

    # Metro Stations
    stations = [
        {"id": "station-central", "name": "Central Station", "lines": ["metro-red", "metro-blue"], "district": "district-downtown"},
        {"id": "station-tech-park", "name": "Tech Park Station", "lines": ["metro-blue"], "district": "district-tech-park"},
        {"id": "station-university", "name": "University Station", "lines": ["metro-green"], "district": "district-university"},
        {"id": "station-harbor", "name": "Harbor Station", "lines": ["metro-red"], "district": "district-harbor"},
        {"id": "station-airport", "name": "Airport Station", "lines": ["metro-red", "metro-blue"], "district": "district-airport"},
    ]

    for station in stations:
        all_twins.append(prepare_smart_city_twin({
            "id": station["id"],
            "type": "MetroStation",
            "name": station["name"],
            "properties": {
                "platforms": len(station["lines"]) * 2,
                "hasElevator": True,
                "hasEscalator": True,
                "hasParking": station["id"] in ["station-airport", "station-tech-park"],
                "dailyRidership": 8500,
                "status": "operational"
            }
        }))
        for line_id in station["lines"]:
            all_relationships.append((station["id"], "onLine", line_id, None))
        all_relationships.append((station["id"], "locatedIn", station["district"], None))

    # Bus Routes
    bus_routes = [
        {"id": "bus-route-1", "name": "Route 1 - Downtown Express", "stops": 15, "length": 12},
        {"id": "bus-route-5", "name": "Route 5 - University Loop", "stops": 20, "length": 8},
        {"id": "bus-route-10", "name": "Route 10 - Harbor Connector", "stops": 18, "length": 15},
        {"id": "bus-route-15", "name": "Route 15 - Residential Circuit", "stops": 25, "length": 20},
    ]

    for route in bus_routes:
        all_twins.append(prepare_smart_city_twin({
            "id": route["id"],
            "type": "BusRoute",
            "name": route["name"],
            "properties": {
                "stops": route["stops"],
                "length": route["length"],
                "lengthUnit": "km",
                "frequency": 15,
                "frequencyUnit": "minutes",
                "busesAssigned": 8,
                "dailyRidership": 3500,
                "status": "active"
            }
        }))
        all_relationships.append(("city-metropolis", "hasBusRoute", route["id"], None))

    # Buses
    for i in range(1, 11):
        bus_id = f"bus-{i:03d}"
        route = bus_routes[i % len(bus_routes)]
        all_twins.append(prepare_smart_city_twin({
            "id": bus_id,
            "type": "Bus",
            "name": f"Bus {i:03d}",
            "properties": {
                "manufacturer": "New Flyer",
                "model": "Xcelsior XE40",
                "type": "electric",
                "capacity": 40,
                "currentPassengers": 25,
                "currentLocation": {"lat": 37.5 + (i * 0.01), "lng": -122.0 - (i * 0.01)},
                "batteryLevel": 75,
                "status": "in_service",
                "nextStop": f"Stop {i + 1}"
            }
        }))
        all_relationships.append((bus_id, "operatesOn", route["id"], None))

    # =========================================================================
    # UTILITIES - ELECTRICITY
    # =========================================================================
    all_twins.append(prepare_smart_city_twin({
        "id": "power-grid-main",
        "type": "PowerGrid",
        "name": "City Power Grid",
        "properties": {
            "totalCapacity": 2500,
            "capacityUnit": "MW",
            "currentLoad": 1850,
            "peakLoad": 2200,
            "renewablePercentage": 45,
            "status": "normal"
        }
    }))
    all_relationships.append(("city-metropolis", "hasPowerGrid", "power-grid-main", None))

    # Substations
    substations = [
        {"id": "substation-north", "name": "North Substation", "capacity": 500, "district": "district-tech-park"},
        {"id": "substation-south", "name": "South Substation", "capacity": 600, "district": "district-riverside"},
        {"id": "substation-east", "name": "East Substation", "capacity": 450, "district": "district-harbor"},
        {"id": "substation-west", "name": "West Substation", "capacity": 550, "district": "district-greenvalley"},
        {"id": "substation-downtown", "name": "Downtown Substation", "capacity": 400, "district": "district-downtown"},
    ]

    for sub in substations:
        all_twins.append(prepare_smart_city_twin({
            "id": sub["id"],
            "type": "ElectricalSubstation",
            "name": sub["name"],
            "properties": {
                "capacity": sub["capacity"],
                "capacityUnit": "MW",
                "currentLoad": sub["capacity"] * 0.75,
                "voltage": 138,
                "voltageUnit": "kV",
                "transformers": 4,
                "status": "operational"
            }
        }))
        all_relationships.append(("power-grid-main", "hasSubstation", sub["id"], None))
        all_relationships.append((sub["id"], "serves", sub["district"], None))

    # Smart Meters (sampling)
    for i in range(1, 11):
        meter_id = f"smart-meter-{i:05d}"
        all_twins.append(prepare_smart_city_twin({
            "id": meter_id,
            "type": "SmartMeter",
            "name": f"Smart Meter {i:05d}",
            "properties": {
                "type": "electricity",
                "currentReading": 4500 + (i * 100),
                "readingUnit": "kWh",
                "currentPower": 2.5,
                "powerUnit": "kW",
                "lastReading": "2026-12-15T10:00:00Z",
                "status": "online"
            }
        }))

    # =========================================================================
    # UTILITIES - WATER
    # =========================================================================
    all_twins.append(prepare_smart_city_twin({
        "id": "water-system-main",
        "type": "WaterSystem",
        "name": "City Water System",
        "properties": {
            "dailyCapacity": 500,
            "capacityUnit": "million_gallons",
            "currentDemand": 380,
            "reservoirLevel": 85,
            "waterQualityIndex": 98,
            "status": "normal"
        }
    }))
    all_relationships.append(("city-metropolis", "hasWaterSystem", "water-system-main", None))

    # Water Treatment Plant
    all_twins.append(prepare_smart_city_twin({
        "id": "water-treatment-plant",
        "type": "WaterTreatmentPlant",
        "name": "Central Water Treatment Plant",
        "properties": {
            "capacity": 200,
            "capacityUnit": "million_gallons_per_day",
            "currentThroughput": 165,
            "treatmentStages": ["coagulation", "sedimentation", "filtration", "disinfection"],
            "chlorineLevel": 0.8,
            "phLevel": 7.2,
            "turbidity": 0.3,
            "status": "operational"
        }
    }))
    all_relationships.append(("water-system-main", "hasTreatmentPlant", "water-treatment-plant", None))

    # Water Tanks
    water_tanks = [
        {"id": "water-tank-hill", "name": "Hilltop Reservoir", "capacity": 10, "district": "district-greenvalley"},
        {"id": "water-tank-downtown", "name": "Downtown Storage Tank", "capacity": 5, "district": "district-downtown"},
        {"id": "water-tank-industrial", "name": "Industrial Zone Tank", "capacity": 8, "district": "district-harbor"},
    ]

    for tank in water_tanks:
        all_twins.append(prepare_smart_city_twin({
            "id": tank["id"],
            "type": "WaterTank",
            "name": tank["name"],
            "properties": {
                "capacity": tank["capacity"],
                "capacityUnit": "million_gallons",
                "currentLevel": tank["capacity"] * 0.8,
                "status": "normal"
            }
        }))
        all_relationships.append(("water-system-main", "hasTank", tank["id"], None))
        all_relationships.append((tank["id"], "serves", tank["district"], None))

    # =========================================================================
    # ENVIRONMENTAL MONITORING
    # =========================================================================
    # Air Quality Stations
    air_stations = [
        {"id": "air-station-downtown", "name": "Downtown Air Quality Station", "district": "district-downtown"},
        {"id": "air-station-industrial", "name": "Industrial Air Quality Station", "district": "district-harbor"},
        {"id": "air-station-residential", "name": "Residential Air Quality Station", "district": "district-greenvalley"},
        {"id": "air-station-highway", "name": "Highway Air Quality Station", "district": "district-airport"},
    ]

    for station in air_stations:
        all_twins.append(prepare_smart_city_twin({
            "id": station["id"],
            "type": "AirQualityStation",
            "name": station["name"],
            "properties": {
                "aqi": 45,
                "pm25": 12.5,
                "pm10": 28.0,
                "o3": 0.035,
                "no2": 0.018,
                "co": 0.4,
                "so2": 0.002,
                "units": {
                    "pm": "ug/m3",
                    "gases": "ppm"
                },
                "lastReading": "2026-12-15T10:00:00Z",
                "status": "online"
            }
        }))
        all_relationships.append((station["id"], "monitors", station["district"], None))

    # Noise Monitoring
    noise_sensors = [
        {"id": "noise-sensor-downtown", "name": "Downtown Noise Sensor", "district": "district-downtown"},
        {"id": "noise-sensor-airport", "name": "Airport Noise Sensor", "district": "district-airport"},
        {"id": "noise-sensor-residential", "name": "Residential Noise Sensor", "district": "district-riverside"},
    ]

    for sensor in noise_sensors:
        all_twins.append(prepare_smart_city_twin({
            "id": sensor["id"],
            "type": "NoiseSensor",
            "name": sensor["name"],
            "properties": {
                "currentLevel": 55,
                "unit": "dB",
                "averageLevel": 52,
                "peakLevel": 78,
                "lastReading": "2026-12-15T10:00:00Z",
                "status": "online"
            }
        }))
        all_relationships.append((sensor["id"], "monitors", sensor["district"], None))

    # Weather Stations
    all_twins.append(prepare_smart_city_twin({
        "id": "weather-station-central",
        "type": "WeatherStation",
        "name": "Central Weather Station",
        "properties": {
            "temperature": 18.5,
            "temperatureUnit": "Celsius",
            "humidity": 65,
            "pressure": 1015,
            "pressureUnit": "hPa",
            "windSpeed": 12,
            "windSpeedUnit": "km/h",
            "windDirection": 270,
            "precipitation": 0,
            "visibility": 10,
            "visibilityUnit": "km",
            "lastReading": "2026-12-15T10:00:00Z",
            "status": "online"
        }
    }))
    all_relationships.append(("city-metropolis", "hasWeatherStation", "weather-station-central", None))

    # =========================================================================
    # PUBLIC SAFETY
    # =========================================================================
    # Police Stations
    police_stations = [
        {"id": "police-central", "name": "Central Police Station", "district": "district-downtown", "officers": 150},
        {"id": "police-north", "name": "North Precinct", "district": "district-tech-park", "officers": 80},
        {"id": "police-south", "name": "South Precinct", "district": "district-riverside", "officers": 100},
    ]

    for station in police_stations:
        all_twins.append(prepare_smart_city_twin({
            "id": station["id"],
            "type": "PoliceStation",
            "name": station["name"],
            "properties": {
                "officers": station["officers"],
                "vehicles": station["officers"] // 5,
                "responseTime": 8,
                "responseTimeUnit": "minutes",
                "activeCalls": 12,
                "status": "operational"
            }
        }))
        all_relationships.append((station["id"], "serves", station["district"], None))

    # Fire Stations
    fire_stations = [
        {"id": "fire-station-1", "name": "Fire Station 1", "district": "district-downtown", "trucks": 4},
        {"id": "fire-station-2", "name": "Fire Station 2", "district": "district-harbor", "trucks": 3},
        {"id": "fire-station-3", "name": "Fire Station 3", "district": "district-greenvalley", "trucks": 3},
        {"id": "fire-station-4", "name": "Fire Station 4", "district": "district-airport", "trucks": 5},
    ]

    for station in fire_stations:
        all_twins.append(prepare_smart_city_twin({
            "id": station["id"],
            "type": "FireStation",
            "name": station["name"],
            "properties": {
                "trucks": station["trucks"],
                "firefighters": station["trucks"] * 8,
                "responseTime": 6,
                "responseTimeUnit": "minutes",
                "hasLadderTruck": station["trucks"] >= 4,
                "hasHazmatUnit": station["id"] in ["fire-station-2", "fire-station-4"],
                "status": "operational"
            }
        }))
        all_relationships.append((station["id"], "serves", station["district"], None))

    # Surveillance Cameras
    for i, inter in enumerate(intersections):
        camera_id = f"camera-{inter['id']}"
        all_twins.append(prepare_smart_city_twin({
            "id": camera_id,
            "type": "SurveillanceCamera",
            "name": f"Camera - {inter['name']}",
            "properties": {
                "type": "PTZ",
                "resolution": "4K",
                "hasNightVision": True,
                "hasFacialRecognition": True,
                "hasLicensePlateRecognition": True,
                "status": "online",
                "storageRetentionDays": 30
            }
        }))
        all_relationships.append((camera_id, "monitors", inter["id"], None))

    # =========================================================================
    # STREET LIGHTING
    # =========================================================================
    all_twins.append(prepare_smart_city_twin({
        "id": "streetlight-controller",
        "type": "StreetLightingController",
        "name": "City Street Lighting System",
        "properties": {
            "totalLights": 25000,
            "ledLights": 22000,
            "smartLights": 15000,
            "energySavings": 45,
            "energySavingsUnit": "percent",
            "status": "operational"
        }
    }))
    all_relationships.append(("city-metropolis", "hasLightingSystem", "streetlight-controller", None))

    # Smart streetlights (sampling)
    for i in range(1, 6):
        light_id = f"streetlight-smart-{i:04d}"
        all_twins.append(prepare_smart_city_twin({
            "id": light_id,
            "type": "SmartStreetlight",
            "name": f"Smart Streetlight {i:04d}",
            "properties": {
                "type": "LED",
                "wattage": 100,
                "dimmingLevel": 80,
                "hasMotionSensor": True,
                "hasAirQualitySensor": True,
                "hasWifi": True,
                "status": "on",
                "energyConsumedToday": 0.8,
                "energyUnit": "kWh"
            }
        }))
        all_relationships.append(("streetlight-controller", "controls", light_id, None))

    # =========================================================================
    # PARKING
    # =========================================================================
    parking_facilities = [
        {"id": "parking-downtown-1", "name": "Downtown Parking Garage", "type": "garage", "capacity": 500, "district": "district-downtown"},
        {"id": "parking-downtown-2", "name": "Main Street Lot", "type": "surface", "capacity": 200, "district": "district-downtown"},
        {"id": "parking-tech-park", "name": "Tech Park Garage", "type": "garage", "capacity": 800, "district": "district-tech-park"},
        {"id": "parking-airport", "name": "Airport Long-Term Parking", "type": "surface", "capacity": 2000, "district": "district-airport"},
    ]

    for parking in parking_facilities:
        all_twins.append(prepare_smart_city_twin({
            "id": parking["id"],
            "type": "ParkingFacility",
            "name": parking["name"],
            "properties": {
                "facilityType": parking["type"],
                "totalSpaces": parking["capacity"],
                "availableSpaces": int(parking["capacity"] * 0.3),
                "evChargingSpaces": int(parking["capacity"] * 0.1),
                "handicapSpaces": int(parking["capacity"] * 0.05),
                "hourlyRate": 3.50 if parking["type"] == "garage" else 2.00,
                "currency": "USD",
                "hasRealTimeAvailability": True,
                "status": "open"
            }
        }))
        all_relationships.append((parking["id"], "locatedIn", parking["district"], None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, twins_failed = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships...")
    relationships_created, relationships_failed = bulk_add_relationships(client, all_relationships)

    print_summary("Smart City", twins_created, relationships_created)
    logger.info("Smart City digital twin seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_smart_city()
