#!/usr/bin/env python3
"""
Energy Grid Digital Twin Example

This example creates a comprehensive digital twin of a modern power grid,
including generation, transmission, distribution, and renewable energy sources.

Domain: Energy / Utilities
Use Cases:
  - Grid stability monitoring
  - Renewable energy integration
  - Demand forecasting and load balancing
  - Fault detection and isolation
  - Energy trading optimization
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
DOMAIN = "energy_grid"
ENERGY_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_energy_grid_twin(data: dict) -> dict:
    """Prepare a twin dict for the energy_grid domain with proper namespace.

    Returns the dict without making any API calls.
    """
    # Expand type to full URI if it's a short name
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{ENERGY_NS}{twin_type}"

    # Add domain tag
    data["domain"] = DOMAIN

    return data


def seed_energy_grid():
    """Seed the energy grid digital twin."""
    client = get_client()

    # Collect all twins and relationships for bulk operations
    all_twins = []
    all_relationships = []

    # =========================================================================
    # GRID OPERATOR
    # =========================================================================
    all_twins.append(prepare_energy_grid_twin({
        "id": "grid-regional-001",
        "type": "PowerGrid",
        "name": "Regional Power Grid",
        "description": "Regional electricity transmission and distribution network",
        "properties": {
            "region": "Western Region",
            "country": "USA",
            "totalCapacity": 15000,
            "capacityUnit": "MW",
            "currentLoad": 11500,
            "peakLoad": 14200,
            "frequency": 60.0,
            "frequencyUnit": "Hz",
            "voltageLevel": "high",
            "renewablePercentage": 42,
            "carbonIntensity": 285,
            "carbonIntensityUnit": "gCO2/kWh",
            "status": "normal"
        }
    }))

    # =========================================================================
    # POWER PLANTS - CONVENTIONAL
    # =========================================================================
    conventional_plants = [
        {"id": "plant-gas-001", "name": "Riverside Gas Plant", "type": "NaturalGas", "capacity": 1200, "efficiency": 58},
        {"id": "plant-gas-002", "name": "Valley Combined Cycle", "type": "NaturalGas", "capacity": 800, "efficiency": 62},
        {"id": "plant-coal-001", "name": "Mountain Coal Station", "type": "Coal", "capacity": 1500, "efficiency": 38},
        {"id": "plant-nuclear-001", "name": "Lakeside Nuclear", "type": "Nuclear", "capacity": 2200, "efficiency": 33},
        {"id": "plant-hydro-001", "name": "Grand Dam Hydro", "type": "Hydroelectric", "capacity": 1800, "efficiency": 90},
    ]

    for plant in conventional_plants:
        all_twins.append(prepare_energy_grid_twin({
            "id": plant["id"],
            "type": f"{plant['type']}PowerPlant",
            "name": plant["name"],
            "properties": {
                "capacity": plant["capacity"],
                "capacityUnit": "MW",
                "currentOutput": int(plant["capacity"] * 0.75),
                "efficiency": plant["efficiency"],
                "efficiencyUnit": "percent",
                "availability": 95,
                "fuelType": plant["type"].lower(),
                "emissionsFactor": 0 if plant["type"] in ["Nuclear", "Hydroelectric"] else (450 if plant["type"] == "NaturalGas" else 900),
                "emissionsUnit": "gCO2/kWh",
                "yearBuilt": 2015 if plant["type"] == "NaturalGas" else (1985 if plant["type"] == "Coal" else 1990),
                "lastOverhaul": "2023-06-15",
                "status": "generating"
            }
        }))
        all_relationships.append(("grid-regional-001", "hasGenerator", plant["id"], None))

    # =========================================================================
    # RENEWABLE ENERGY - SOLAR FARMS
    # =========================================================================
    solar_farms = [
        {"id": "solar-farm-001", "name": "Desert Sun Solar Farm", "capacity": 500, "panels": 1500000, "lat": 33.5, "lng": -115.2},
        {"id": "solar-farm-002", "name": "Valley Solar Array", "capacity": 300, "panels": 900000, "lat": 34.1, "lng": -117.8},
        {"id": "solar-farm-003", "name": "Hilltop Solar Park", "capacity": 200, "panels": 600000, "lat": 35.2, "lng": -118.5},
    ]

    for farm in solar_farms:
        all_twins.append(prepare_energy_grid_twin({
            "id": farm["id"],
            "type": "SolarFarm",
            "name": farm["name"],
            "properties": {
                "capacity": farm["capacity"],
                "capacityUnit": "MW",
                "currentOutput": int(farm["capacity"] * 0.65),
                "panelCount": farm["panels"],
                "panelType": "monocrystalline",
                "efficiency": 22,
                "area": farm["capacity"] * 2,
                "areaUnit": "hectares",
                "coordinates": {"lat": farm["lat"], "lng": farm["lng"]},
                "trackingType": "single-axis",
                "inverterCapacity": farm["capacity"] * 1.1,
                "degradationRate": 0.5,
                "installDate": "2021-03-15",
                "status": "generating"
            }
        }))
        all_relationships.append(("grid-regional-001", "hasGenerator", farm["id"], None))

    # =========================================================================
    # RENEWABLE ENERGY - WIND FARMS
    # =========================================================================
    wind_farms = [
        {"id": "wind-farm-001", "name": "Coastal Wind Farm", "capacity": 600, "turbines": 120, "lat": 35.8, "lng": -120.5},
        {"id": "wind-farm-002", "name": "Mountain Pass Wind", "capacity": 450, "turbines": 90, "lat": 34.9, "lng": -116.2},
        {"id": "wind-farm-003", "name": "Plains Wind Energy", "capacity": 800, "turbines": 160, "lat": 36.5, "lng": -119.8},
        {"id": "wind-offshore-001", "name": "Pacific Offshore Wind", "capacity": 1000, "turbines": 100, "lat": 34.0, "lng": -121.0},
    ]

    for farm in wind_farms:
        all_twins.append(prepare_energy_grid_twin({
            "id": farm["id"],
            "type": "WindFarm",
            "name": farm["name"],
            "properties": {
                "capacity": farm["capacity"],
                "capacityUnit": "MW",
                "currentOutput": int(farm["capacity"] * 0.35),
                "turbineCount": farm["turbines"],
                "turbineCapacity": farm["capacity"] / farm["turbines"],
                "turbineType": "offshore" if "offshore" in farm["id"] else "onshore",
                "hubHeight": 150 if "offshore" in farm["id"] else 100,
                "hubHeightUnit": "meters",
                "rotorDiameter": 180 if "offshore" in farm["id"] else 130,
                "rotorDiameterUnit": "meters",
                "coordinates": {"lat": farm["lat"], "lng": farm["lng"]},
                "averageWindSpeed": 9.5 if "offshore" in farm["id"] else 7.8,
                "windSpeedUnit": "m/s",
                "capacityFactor": 0.45 if "offshore" in farm["id"] else 0.35,
                "installDate": "2022-08-01",
                "status": "generating"
            }
        }))
        all_relationships.append(("grid-regional-001", "hasGenerator", farm["id"], None))

    # =========================================================================
    # BATTERY STORAGE SYSTEMS
    # =========================================================================
    battery_systems = [
        {"id": "battery-001", "name": "Grid Storage East", "capacity": 400, "power": 200},
        {"id": "battery-002", "name": "Grid Storage West", "capacity": 600, "power": 300},
        {"id": "battery-003", "name": "Solar Farm Storage", "capacity": 250, "power": 125, "linkedTo": "solar-farm-001"},
        {"id": "battery-004", "name": "Wind Farm Storage", "capacity": 300, "power": 150, "linkedTo": "wind-farm-001"},
    ]

    for battery in battery_systems:
        all_twins.append(prepare_energy_grid_twin({
            "id": battery["id"],
            "type": "BatteryStorage",
            "name": battery["name"],
            "properties": {
                "capacity": battery["capacity"],
                "capacityUnit": "MWh",
                "power": battery["power"],
                "powerUnit": "MW",
                "stateOfCharge": 65,
                "stateOfChargeUnit": "percent",
                "technology": "lithium-ion",
                "cycleCount": 1250,
                "maxCycles": 6000,
                "roundTripEfficiency": 92,
                "efficiencyUnit": "percent",
                "status": "standby",
                "mode": "grid-stabilization",
                "installDate": "2023-01-15"
            }
        }))
        all_relationships.append(("grid-regional-001", "hasStorage", battery["id"], None))
        if "linkedTo" in battery:
            all_relationships.append((battery["id"], "supports", battery["linkedTo"], None))

    # =========================================================================
    # TRANSMISSION - HIGH VOLTAGE SUBSTATIONS
    # =========================================================================
    hv_substations = [
        {"id": "substation-hv-001", "name": "Central HV Substation", "voltage": 500, "lat": 34.5, "lng": -118.0},
        {"id": "substation-hv-002", "name": "North HV Substation", "voltage": 500, "lat": 36.0, "lng": -117.5},
        {"id": "substation-hv-003", "name": "South HV Substation", "voltage": 345, "lat": 33.0, "lng": -118.5},
        {"id": "substation-hv-004", "name": "East HV Substation", "voltage": 345, "lat": 34.8, "lng": -115.5},
        {"id": "substation-hv-005", "name": "West HV Substation", "voltage": 500, "lat": 34.2, "lng": -120.0},
    ]

    for sub in hv_substations:
        all_twins.append(prepare_energy_grid_twin({
            "id": sub["id"],
            "type": "HighVoltageSubstation",
            "name": sub["name"],
            "properties": {
                "voltageLevel": sub["voltage"],
                "voltageUnit": "kV",
                "capacity": 2000,
                "capacityUnit": "MVA",
                "currentLoad": 1500,
                "coordinates": {"lat": sub["lat"], "lng": sub["lng"]},
                "transformers": 4,
                "breakers": 12,
                "status": "operational",
                "lastInspection": "2024-10-15"
            }
        }))
        all_relationships.append(("grid-regional-001", "hasSubstation", sub["id"], None))

    # Connect generators to nearest substations
    all_relationships.append(("plant-nuclear-001", "connectsTo", "substation-hv-001", None))
    all_relationships.append(("plant-gas-001", "connectsTo", "substation-hv-002", None))
    all_relationships.append(("plant-hydro-001", "connectsTo", "substation-hv-004", None))
    all_relationships.append(("solar-farm-001", "connectsTo", "substation-hv-003", None))
    all_relationships.append(("wind-farm-003", "connectsTo", "substation-hv-002", None))
    all_relationships.append(("wind-offshore-001", "connectsTo", "substation-hv-005", None))

    # =========================================================================
    # TRANSMISSION LINES
    # =========================================================================
    transmission_lines = [
        {"id": "line-hv-001", "name": "Central-North 500kV", "voltage": 500, "length": 150, "from": "substation-hv-001", "to": "substation-hv-002"},
        {"id": "line-hv-002", "name": "Central-South 345kV", "voltage": 345, "length": 120, "from": "substation-hv-001", "to": "substation-hv-003"},
        {"id": "line-hv-003", "name": "Central-East 345kV", "voltage": 345, "length": 180, "from": "substation-hv-001", "to": "substation-hv-004"},
        {"id": "line-hv-004", "name": "Central-West 500kV", "voltage": 500, "length": 160, "from": "substation-hv-001", "to": "substation-hv-005"},
        {"id": "line-hv-005", "name": "North-East 345kV", "voltage": 345, "length": 200, "from": "substation-hv-002", "to": "substation-hv-004"},
    ]

    for line in transmission_lines:
        all_twins.append(prepare_energy_grid_twin({
            "id": line["id"],
            "type": "TransmissionLine",
            "name": line["name"],
            "properties": {
                "voltage": line["voltage"],
                "voltageUnit": "kV",
                "length": line["length"],
                "lengthUnit": "km",
                "capacity": 1500 if line["voltage"] == 500 else 1000,
                "capacityUnit": "MW",
                "currentFlow": 850,
                "conductorType": "ACSR",
                "circuits": 2,
                "status": "energized",
                "temperature": 45,
                "temperatureUnit": "Celsius"
            }
        }))
        all_relationships.append((line["id"], "connectsFrom", line["from"], None))
        all_relationships.append((line["id"], "connectsTo", line["to"], None))

    # =========================================================================
    # DISTRIBUTION SUBSTATIONS
    # =========================================================================
    dist_substations = [
        {"id": "substation-dist-001", "name": "Downtown Distribution", "hvParent": "substation-hv-001", "customers": 25000},
        {"id": "substation-dist-002", "name": "Industrial Park Distribution", "hvParent": "substation-hv-001", "customers": 500},
        {"id": "substation-dist-003", "name": "Residential North Distribution", "hvParent": "substation-hv-002", "customers": 35000},
        {"id": "substation-dist-004", "name": "Commercial West Distribution", "hvParent": "substation-hv-005", "customers": 15000},
        {"id": "substation-dist-005", "name": "Suburban East Distribution", "hvParent": "substation-hv-004", "customers": 28000},
        {"id": "substation-dist-006", "name": "Rural South Distribution", "hvParent": "substation-hv-003", "customers": 8000},
    ]

    for sub in dist_substations:
        all_twins.append(prepare_energy_grid_twin({
            "id": sub["id"],
            "type": "DistributionSubstation",
            "name": sub["name"],
            "properties": {
                "inputVoltage": 138,
                "outputVoltage": 13.8,
                "voltageUnit": "kV",
                "capacity": 100,
                "capacityUnit": "MVA",
                "currentLoad": 75,
                "customersServed": sub["customers"],
                "feeders": 8,
                "status": "operational"
            }
        }))
        all_relationships.append((sub["hvParent"], "feedsTo", sub["id"], None))

    # =========================================================================
    # SMART METERS (Sample)
    # =========================================================================
    for i in range(1, 21):
        meter_id = f"smart-meter-{i:06d}"
        meter_type = "residential" if i <= 15 else ("commercial" if i <= 18 else "industrial")
        all_twins.append(prepare_energy_grid_twin({
            "id": meter_id,
            "type": "SmartMeter",
            "name": f"Smart Meter {i:06d}",
            "properties": {
                "meterType": meter_type,
                "manufacturer": "Itron",
                "model": "OpenWay Riva",
                "currentReading": 45000 + (i * 1000),
                "readingUnit": "kWh",
                "currentPower": 2.5 if meter_type == "residential" else (15 if meter_type == "commercial" else 150),
                "powerUnit": "kW",
                "voltage": 240 if meter_type == "residential" else 480,
                "voltageUnit": "V",
                "powerFactor": 0.95,
                "lastReading": "2024-12-15T10:00:00Z",
                "communicationStatus": "online"
            }
        }))

    # =========================================================================
    # GRID CONTROL CENTER
    # =========================================================================
    all_twins.append(prepare_energy_grid_twin({
        "id": "control-center-001",
        "type": "GridControlCenter",
        "name": "Regional Grid Control Center",
        "properties": {
            "location": "Sacramento, CA",
            "operators": 45,
            "scadaSystem": "GE PowerOn",
            "emsSystem": "Siemens Spectrum",
            "backupPower": "48 hours",
            "communicationRedundancy": True,
            "status": "operational"
        }
    }))
    all_relationships.append(("control-center-001", "monitors", "grid-regional-001", None))

    # =========================================================================
    # PROTECTIVE RELAYS
    # =========================================================================
    for i, sub in enumerate(hv_substations):
        relay_id = f"relay-{sub['id']}"
        all_twins.append(prepare_energy_grid_twin({
            "id": relay_id,
            "type": "ProtectiveRelay",
            "name": f"Protective Relay - {sub['name']}",
            "properties": {
                "manufacturer": "SEL",
                "model": "SEL-421",
                "protectionType": ["distance", "overcurrent", "differential"],
                "settingsVersion": "2024.3",
                "status": "armed",
                "lastTrip": "2024-08-15T14:30:00Z",
                "lastTest": "2024-11-01"
            }
        }))
        all_relationships.append((relay_id, "protects", sub["id"], None))

    # =========================================================================
    # WEATHER STATIONS (for renewable forecasting)
    # =========================================================================
    weather_stations = [
        {"id": "weather-solar-001", "name": "Solar Farm Weather", "linkedTo": "solar-farm-001"},
        {"id": "weather-wind-001", "name": "Wind Farm Weather", "linkedTo": "wind-farm-001"},
        {"id": "weather-offshore-001", "name": "Offshore Weather Buoy", "linkedTo": "wind-offshore-001"},
    ]

    for station in weather_stations:
        all_twins.append(prepare_energy_grid_twin({
            "id": station["id"],
            "type": "WeatherStation",
            "name": station["name"],
            "properties": {
                "temperature": 25,
                "temperatureUnit": "Celsius",
                "windSpeed": 8.5,
                "windSpeedUnit": "m/s",
                "windDirection": 270,
                "solarIrradiance": 850,
                "irradianceUnit": "W/m2",
                "humidity": 45,
                "pressure": 1015,
                "pressureUnit": "hPa",
                "lastReading": "2024-12-15T10:00:00Z",
                "status": "online"
            }
        }))
        all_relationships.append((station["id"], "monitors", station["linkedTo"], None))

    # =========================================================================
    # ELECTRIC VEHICLE CHARGING INFRASTRUCTURE
    # =========================================================================
    ev_stations = [
        {"id": "ev-station-001", "name": "Downtown EV Hub", "chargers": 20, "substation": "substation-dist-001"},
        {"id": "ev-station-002", "name": "Highway Rest Stop Chargers", "chargers": 12, "substation": "substation-dist-004"},
        {"id": "ev-station-003", "name": "Shopping Mall EV", "chargers": 30, "substation": "substation-dist-004"},
    ]

    for station in ev_stations:
        all_twins.append(prepare_energy_grid_twin({
            "id": station["id"],
            "type": "EVChargingStation",
            "name": station["name"],
            "properties": {
                "chargerCount": station["chargers"],
                "fastChargers": station["chargers"] // 3,
                "standardChargers": station["chargers"] - (station["chargers"] // 3),
                "maxPower": 350,
                "maxPowerUnit": "kW",
                "currentLoad": 250,
                "sessionsToday": 85,
                "energyDeliveredToday": 2500,
                "energyUnit": "kWh",
                "status": "operational"
            }
        }))
        all_relationships.append((station["id"], "poweredBy", station["substation"], None))

    # =========================================================================
    # DEMAND RESPONSE RESOURCES
    # =========================================================================
    dr_resources = [
        {"id": "dr-industrial-001", "name": "Steel Plant DR", "capacity": 50, "type": "industrial"},
        {"id": "dr-commercial-001", "name": "Mall HVAC DR", "capacity": 20, "type": "commercial"},
        {"id": "dr-residential-001", "name": "Smart Thermostat Program", "capacity": 100, "type": "residential"},
    ]

    for dr in dr_resources:
        all_twins.append(prepare_energy_grid_twin({
            "id": dr["id"],
            "type": "DemandResponseResource",
            "name": dr["name"],
            "properties": {
                "resourceType": dr["type"],
                "capacity": dr["capacity"],
                "capacityUnit": "MW",
                "responseTime": 15 if dr["type"] == "industrial" else (30 if dr["type"] == "commercial" else 60),
                "responseTimeUnit": "minutes",
                "maxDuration": 4,
                "durationUnit": "hours",
                "status": "available",
                "eventsThisYear": 12,
                "energyCurtailed": 450,
                "curtailedUnit": "MWh"
            }
        }))
        all_relationships.append(("grid-regional-001", "hasDRResource", dr["id"], None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, twins_failed = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships...")
    relationships_created, relationships_failed = bulk_add_relationships(client, all_relationships)

    print_summary("Energy Grid", twins_created, relationships_created)
    logger.info("Energy Grid digital twin seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_energy_grid()
