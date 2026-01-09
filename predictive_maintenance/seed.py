#!/usr/bin/env python3
"""
Predictive Maintenance - Industrial Equipment Seed Data
========================================================

Creates a comprehensive digital twin network of industrial equipment with:
- Realistic failure modes and degradation patterns
- Sensor configurations for condition monitoring
- Maintenance history and schedules
- Component hierarchies with failure dependencies

Equipment Types:
- Industrial pumps (centrifugal, positive displacement)
- Electric motors (AC induction, servo motors)
- Bearings (ball bearings, roller bearings)
- Gearboxes (helical, planetary)
- Compressors (reciprocating, screw)
- Heat exchangers

Each equipment type has domain-specific failure modes based on real-world
industrial failure analysis (FMEA data).

Usage:
    python seed.py [--base-url URL] [--clean]
"""

import sys
import os
import random
import argparse
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import (
    get_client, print_summary, logger,
    bulk_create_twins, bulk_add_relationships,
    DOMAIN_NAMESPACES
)

# Register new domain namespace
DOMAIN = "predictive_maintenance"
PM_NS = "http://tesserai.io/ontology/predictive_maintenance#"
DOMAIN_NAMESPACES[DOMAIN] = PM_NS

# Seed for reproducibility (but with realistic variation)
random.seed(42)


def prepare_pm_twin(data: dict) -> dict:
    """Prepare a twin dict for bulk creation in the predictive maintenance domain."""
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{PM_NS}{twin_type}"
    data["domain"] = DOMAIN
    return data


# =============================================================================
# FAILURE MODE DATA (Based on real FMEA analysis)
# =============================================================================

PUMP_FAILURE_MODES = [
    {"mode": "seal_leakage", "mtbf_hours": 8760, "severity": 7, "detection": 6},
    {"mode": "impeller_erosion", "mtbf_hours": 17520, "severity": 8, "detection": 4},
    {"mode": "cavitation_damage", "mtbf_hours": 10000, "severity": 9, "detection": 3},
    {"mode": "bearing_failure", "mtbf_hours": 15000, "severity": 8, "detection": 5},
    {"mode": "shaft_misalignment", "mtbf_hours": 12000, "severity": 6, "detection": 7},
]

MOTOR_FAILURE_MODES = [
    {"mode": "winding_insulation_breakdown", "mtbf_hours": 25000, "severity": 9, "detection": 4},
    {"mode": "bearing_wear", "mtbf_hours": 18000, "severity": 7, "detection": 6},
    {"mode": "rotor_bar_crack", "mtbf_hours": 30000, "severity": 8, "detection": 3},
    {"mode": "cooling_fan_failure", "mtbf_hours": 20000, "severity": 5, "detection": 8},
    {"mode": "shaft_eccentricity", "mtbf_hours": 22000, "severity": 6, "detection": 5},
]

BEARING_FAILURE_MODES = [
    {"mode": "inner_race_spalling", "mtbf_hours": 12000, "severity": 8, "detection": 6},
    {"mode": "outer_race_defect", "mtbf_hours": 14000, "severity": 8, "detection": 5},
    {"mode": "cage_wear", "mtbf_hours": 16000, "severity": 7, "detection": 4},
    {"mode": "lubrication_starvation", "mtbf_hours": 8000, "severity": 9, "detection": 7},
    {"mode": "contamination", "mtbf_hours": 10000, "severity": 6, "detection": 5},
]

GEARBOX_FAILURE_MODES = [
    {"mode": "gear_tooth_pitting", "mtbf_hours": 20000, "severity": 7, "detection": 5},
    {"mode": "gear_tooth_breakage", "mtbf_hours": 35000, "severity": 10, "detection": 3},
    {"mode": "shaft_bearing_failure", "mtbf_hours": 15000, "severity": 8, "detection": 6},
    {"mode": "seal_degradation", "mtbf_hours": 12000, "severity": 5, "detection": 7},
    {"mode": "oil_contamination", "mtbf_hours": 8000, "severity": 6, "detection": 8},
]

COMPRESSOR_FAILURE_MODES = [
    {"mode": "valve_failure", "mtbf_hours": 10000, "severity": 8, "detection": 5},
    {"mode": "piston_ring_wear", "mtbf_hours": 15000, "severity": 7, "detection": 4},
    {"mode": "intercooler_fouling", "mtbf_hours": 8000, "severity": 5, "detection": 7},
    {"mode": "unloader_malfunction", "mtbf_hours": 12000, "severity": 6, "detection": 6},
    {"mode": "crankshaft_bearing_failure", "mtbf_hours": 25000, "severity": 9, "detection": 4},
]

HEAT_EXCHANGER_FAILURE_MODES = [
    {"mode": "tube_fouling", "mtbf_hours": 6000, "severity": 5, "detection": 8},
    {"mode": "tube_corrosion", "mtbf_hours": 20000, "severity": 8, "detection": 4},
    {"mode": "tube_erosion", "mtbf_hours": 18000, "severity": 7, "detection": 5},
    {"mode": "gasket_failure", "mtbf_hours": 10000, "severity": 6, "detection": 7},
    {"mode": "baffle_damage", "mtbf_hours": 30000, "severity": 6, "detection": 3},
]


# =============================================================================
# SENSOR CONFIGURATIONS
# =============================================================================

VIBRATION_SENSOR_CONFIG = {
    "type": "VibrationSensor",
    "manufacturer": "SKF",
    "model": "CMSS 2200",
    "frequency_range": {"min": 10, "max": 10000, "unit": "Hz"},
    "sensitivity": 100,
    "sampling_rate": 25600,
}

TEMPERATURE_SENSOR_CONFIG = {
    "type": "TemperatureSensor",
    "manufacturer": "Omega",
    "model": "TJ36-CASS",
    "range": {"min": -40, "max": 260, "unit": "Celsius"},
    "accuracy": 0.5,
}

PRESSURE_SENSOR_CONFIG = {
    "type": "PressureSensor",
    "manufacturer": "Endress+Hauser",
    "model": "Cerabar PMC51",
    "range": {"min": 0, "max": 40, "unit": "bar"},
    "accuracy": 0.05,
}

FLOW_SENSOR_CONFIG = {
    "type": "FlowSensor",
    "manufacturer": "Siemens",
    "model": "SITRANS FM MAG 5100W",
    "range": {"min": 0, "max": 1000, "unit": "m3/h"},
    "accuracy": 0.2,
}

CURRENT_SENSOR_CONFIG = {
    "type": "CurrentSensor",
    "manufacturer": "Fluke",
    "model": "i400",
    "range": {"min": 0, "max": 400, "unit": "A"},
    "accuracy": 2.0,
}

OIL_SENSOR_CONFIG = {
    "type": "OilConditionSensor",
    "manufacturer": "Parker Kittiwake",
    "model": "OILWEAR",
    "parameters": ["viscosity", "water_content", "particle_count", "temperature"],
}


def generate_operating_hours():
    """Generate realistic operating hours with variation."""
    base = random.randint(5000, 45000)
    return base + random.randint(0, 2000)


def generate_installation_date():
    """Generate realistic installation dates."""
    years_ago = random.uniform(0.5, 8)
    return (datetime.now() - timedelta(days=years_ago * 365)).strftime("%Y-%m-%d")


def generate_last_maintenance():
    """Generate last maintenance date (within past year)."""
    days_ago = random.randint(30, 365)
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def generate_health_score(operating_hours: int, mtbf: int) -> float:
    """Calculate health score based on operating hours and expected MTBF."""
    utilization = operating_hours / mtbf
    base_health = 100 * (1 - (utilization ** 1.5) * 0.3)
    variation = random.gauss(0, 5)
    return max(0, min(100, base_health + variation))


def seed_predictive_maintenance(base_url: Optional[str] = None, clean: bool = False):
    """Seed the predictive maintenance digital twin network."""
    client = get_client(base_url)
    all_twins = []
    all_relationships = []

    # =========================================================================
    # FACILITY
    # =========================================================================
    all_twins.append(prepare_pm_twin({
        "id": "facility-petrochemical-001",
        "type": "IndustrialFacility",
        "name": "Gulf Coast Petrochemical Plant",
        "description": "Heavy industrial petrochemical processing facility",
        "properties": {
            "location": "Houston, TX",
            "coordinates": {"lat": 29.7604, "lng": -95.3698},
            "area": 500000,
            "areaUnit": "sqft",
            "operatingHours": "24/7",
            "employees": 850,
            "certifications": ["ISO 55000", "API 580", "OSHA VPP Star"],
            "annualMaintenanceBudget": 12500000,
            "budgetCurrency": "USD"
        }
    }))
    logger.info("Created facility")

    # =========================================================================
    # PROCESS UNITS
    # =========================================================================
    process_units = [
        {"id": "unit-distillation", "name": "Crude Distillation Unit", "process": "distillation", "criticality": "critical"},
        {"id": "unit-cracking", "name": "Fluid Catalytic Cracker", "process": "cracking", "criticality": "critical"},
        {"id": "unit-reforming", "name": "Catalytic Reformer", "process": "reforming", "criticality": "high"},
        {"id": "unit-hydrotreating", "name": "Hydrotreater Unit", "process": "hydrotreating", "criticality": "high"},
        {"id": "unit-utilities", "name": "Utilities & Offsites", "process": "utilities", "criticality": "medium"},
    ]

    for unit in process_units:
        all_twins.append(prepare_pm_twin({
            "id": unit["id"],
            "type": "ProcessUnit",
            "name": unit["name"],
            "properties": {
                "processType": unit["process"],
                "criticality": unit["criticality"],
                "status": "operational",
                "availability": random.uniform(95, 99.9),
                "reliability": random.uniform(92, 99),
            }
        }))
        all_relationships.append(("facility-petrochemical-001", "hasUnit", unit["id"], None))

    # =========================================================================
    # PUMPS - Critical rotating equipment
    # =========================================================================
    pumps = [
        {"id": "pump-feed-001", "name": "Crude Feed Pump A", "type": "centrifugal", "unit": "unit-distillation", "power": 500, "flow": 800},
        {"id": "pump-feed-002", "name": "Crude Feed Pump B", "type": "centrifugal", "unit": "unit-distillation", "power": 500, "flow": 800},
        {"id": "pump-reflux-001", "name": "Reflux Pump A", "type": "centrifugal", "unit": "unit-distillation", "power": 150, "flow": 400},
        {"id": "pump-reflux-002", "name": "Reflux Pump B", "type": "centrifugal", "unit": "unit-distillation", "power": 150, "flow": 400},
        {"id": "pump-transfer-001", "name": "Product Transfer Pump", "type": "positive_displacement", "unit": "unit-distillation", "power": 75, "flow": 150},
        {"id": "pump-fcc-001", "name": "FCC Slurry Pump A", "type": "centrifugal", "unit": "unit-cracking", "power": 350, "flow": 600},
        {"id": "pump-fcc-002", "name": "FCC Slurry Pump B", "type": "centrifugal", "unit": "unit-cracking", "power": 350, "flow": 600},
        {"id": "pump-reformer-001", "name": "Reformer Recycle Pump", "type": "centrifugal", "unit": "unit-reforming", "power": 200, "flow": 350},
        {"id": "pump-cooling-001", "name": "Cooling Water Pump A", "type": "centrifugal", "unit": "unit-utilities", "power": 250, "flow": 2000},
        {"id": "pump-cooling-002", "name": "Cooling Water Pump B", "type": "centrifugal", "unit": "unit-utilities", "power": 250, "flow": 2000},
        {"id": "pump-firewater-001", "name": "Firewater Pump", "type": "centrifugal", "unit": "unit-utilities", "power": 400, "flow": 1500},
        {"id": "pump-boiler-001", "name": "Boiler Feed Pump A", "type": "centrifugal", "unit": "unit-utilities", "power": 300, "flow": 500},
    ]

    for pump in pumps:
        operating_hours = generate_operating_hours()
        primary_failure_mode = random.choice(PUMP_FAILURE_MODES)
        health_score = generate_health_score(operating_hours, primary_failure_mode["mtbf_hours"])
        rul_hours = max(0, primary_failure_mode["mtbf_hours"] - operating_hours + random.gauss(0, 1000))

        all_twins.append(prepare_pm_twin({
            "id": pump["id"],
            "type": "IndustrialPump",
            "name": pump["name"],
            "properties": {
                "pumpType": pump["type"],
                "manufacturer": random.choice(["Flowserve", "Sulzer", "KSB", "Grundfos"]),
                "model": f"Model-{random.randint(1000, 9999)}",
                "ratedPower": pump["power"],
                "powerUnit": "kW",
                "ratedFlow": pump["flow"],
                "flowUnit": "m3/h",
                "ratedHead": random.randint(50, 200),
                "headUnit": "m",
                "operatingSpeed": random.choice([1450, 1750, 2950, 3550]),
                "speedUnit": "RPM",
                "installationDate": generate_installation_date(),
                "lastMaintenance": generate_last_maintenance(),
                "operatingHours": operating_hours,
                "startCount": random.randint(500, 5000),
                "status": "running" if random.random() > 0.1 else "standby",
                "healthScore": round(health_score, 1),
                "remainingUsefulLife": round(rul_hours, 0),
                "rulUnit": "hours",
                "primaryFailureMode": primary_failure_mode["mode"],
                "failureModeSeverity": primary_failure_mode["severity"],
                "mtbf": primary_failure_mode["mtbf_hours"],
                "criticality": "critical" if pump["power"] > 200 else "high",
                "currentFlow": round(pump["flow"] * random.uniform(0.7, 1.0), 1),
                "currentPressure": round(random.uniform(5, 25), 2),
                "currentVibration": round(random.uniform(1.5, 4.5), 2),
                "currentTemperature": round(random.uniform(45, 85), 1),
                "currentPower": round(pump["power"] * random.uniform(0.6, 0.95), 1),
            }
        }))
        all_relationships.append((pump["unit"], "hasEquipment", pump["id"], None))

        # Add sensors to each pump
        sensors = [
            {"suffix": "vib-de", "name": "Drive End Vibration", "config": VIBRATION_SENSOR_CONFIG, "position": "drive_end"},
            {"suffix": "vib-nde", "name": "Non-Drive End Vibration", "config": VIBRATION_SENSOR_CONFIG, "position": "non_drive_end"},
            {"suffix": "temp-bearing", "name": "Bearing Temperature", "config": TEMPERATURE_SENSOR_CONFIG, "position": "bearing"},
            {"suffix": "pressure-discharge", "name": "Discharge Pressure", "config": PRESSURE_SENSOR_CONFIG, "position": "discharge"},
            {"suffix": "flow", "name": "Flow Rate", "config": FLOW_SENSOR_CONFIG, "position": "discharge"},
        ]

        for sensor in sensors:
            sensor_id = f"sensor-{pump['id']}-{sensor['suffix']}"
            all_twins.append(prepare_pm_twin({
                "id": sensor_id,
                "type": sensor["config"]["type"],
                "name": f"{pump['name']} - {sensor['name']}",
                "properties": {
                    "manufacturer": sensor["config"]["manufacturer"],
                    "model": sensor["config"]["model"],
                    "position": sensor["position"],
                    "status": "active",
                    "lastReading": datetime.now().isoformat(),
                    "samplingInterval": 1000 if "Vibration" in sensor["name"] else 5000,
                    "samplingUnit": "ms",
                }
            }))
            all_relationships.append((sensor_id, "monitors", pump["id"], None))

    # =========================================================================
    # ELECTRIC MOTORS
    # =========================================================================
    motors = [
        {"id": "motor-feed-001", "name": "Crude Feed Motor A", "pump": "pump-feed-001", "power": 500, "voltage": 4160},
        {"id": "motor-feed-002", "name": "Crude Feed Motor B", "pump": "pump-feed-002", "power": 500, "voltage": 4160},
        {"id": "motor-reflux-001", "name": "Reflux Motor A", "pump": "pump-reflux-001", "power": 150, "voltage": 480},
        {"id": "motor-reflux-002", "name": "Reflux Motor B", "pump": "pump-reflux-002", "power": 150, "voltage": 480},
        {"id": "motor-fcc-001", "name": "FCC Slurry Motor A", "pump": "pump-fcc-001", "power": 350, "voltage": 4160},
        {"id": "motor-fcc-002", "name": "FCC Slurry Motor B", "pump": "pump-fcc-002", "power": 350, "voltage": 4160},
        {"id": "motor-cooling-001", "name": "Cooling Water Motor A", "pump": "pump-cooling-001", "power": 250, "voltage": 480},
        {"id": "motor-cooling-002", "name": "Cooling Water Motor B", "pump": "pump-cooling-002", "power": 250, "voltage": 480},
    ]

    for motor in motors:
        operating_hours = generate_operating_hours()
        primary_failure_mode = random.choice(MOTOR_FAILURE_MODES)
        health_score = generate_health_score(operating_hours, primary_failure_mode["mtbf_hours"])
        rul_hours = max(0, primary_failure_mode["mtbf_hours"] - operating_hours + random.gauss(0, 1500))
        insulation_mohm = max(50, 1000 - (operating_hours / 50) + random.gauss(0, 100))

        all_twins.append(prepare_pm_twin({
            "id": motor["id"],
            "type": "ElectricMotor",
            "name": motor["name"],
            "properties": {
                "motorType": "AC_Induction",
                "manufacturer": random.choice(["ABB", "Siemens", "WEG", "Nidec"]),
                "model": f"Model-{random.randint(1000, 9999)}",
                "ratedPower": motor["power"],
                "powerUnit": "kW",
                "ratedVoltage": motor["voltage"],
                "voltageUnit": "V",
                "ratedCurrent": round(motor["power"] / (motor["voltage"] * 0.85 * 1.732) * 1000, 1),
                "currentUnit": "A",
                "poles": random.choice([2, 4, 6]),
                "frequency": 60,
                "efficiency": round(random.uniform(94, 97), 1),
                "powerFactor": round(random.uniform(0.85, 0.92), 2),
                "insulation_class": random.choice(["F", "H"]),
                "installationDate": generate_installation_date(),
                "lastMaintenance": generate_last_maintenance(),
                "operatingHours": operating_hours,
                "startCount": random.randint(200, 3000),
                "status": "running",
                "healthScore": round(health_score, 1),
                "remainingUsefulLife": round(rul_hours, 0),
                "rulUnit": "hours",
                "primaryFailureMode": primary_failure_mode["mode"],
                "mtbf": primary_failure_mode["mtbf_hours"],
                "insulationResistance": round(insulation_mohm, 0),
                "insulationUnit": "MOhm",
                "windingTemperature": round(random.uniform(65, 120), 1),
                "bearingTemperature": round(random.uniform(45, 75), 1),
                "currentImbalance": round(random.uniform(0.5, 5), 1),
                "vibrationVelocity": round(random.uniform(1.5, 4.0), 2),
            }
        }))
        all_relationships.append((motor["id"], "drives", motor["pump"], None))
        all_relationships.append((motor["pump"], "drivenBy", motor["id"], None))

        # Motor current sensor
        sensor_id = f"sensor-{motor['id']}-current"
        all_twins.append(prepare_pm_twin({
            "id": sensor_id,
            "type": "CurrentSensor",
            "name": f"{motor['name']} - Current Monitor",
            "properties": {
                "manufacturer": CURRENT_SENSOR_CONFIG["manufacturer"],
                "model": CURRENT_SENSOR_CONFIG["model"],
                "phases": 3,
                "status": "active",
            }
        }))
        all_relationships.append((sensor_id, "monitors", motor["id"], None))

    # =========================================================================
    # BEARINGS - Critical subcomponents
    # =========================================================================
    bearing_locations = [
        ("pump-feed-001", "DE", "SKF 6316"), ("pump-feed-001", "NDE", "SKF 6314"),
        ("pump-feed-002", "DE", "SKF 6316"), ("pump-feed-002", "NDE", "SKF 6314"),
        ("pump-fcc-001", "DE", "FAG 22318"), ("pump-fcc-001", "NDE", "FAG 22316"),
        ("pump-cooling-001", "DE", "NSK 6312"), ("pump-cooling-001", "NDE", "NSK 6310"),
    ]

    for equipment_id, position, model in bearing_locations:
        bearing_id = f"bearing-{equipment_id}-{position.lower()}"
        operating_hours = generate_operating_hours()
        primary_failure_mode = random.choice(BEARING_FAILURE_MODES)
        health_score = generate_health_score(operating_hours, primary_failure_mode["mtbf_hours"])
        rul_hours = max(0, primary_failure_mode["mtbf_hours"] - operating_hours + random.gauss(0, 800))

        bpfo = round(random.uniform(80, 150), 1)
        bpfi = round(random.uniform(100, 180), 1)
        bsf = round(random.uniform(40, 80), 1)
        ftf = round(random.uniform(10, 25), 1)

        all_twins.append(prepare_pm_twin({
            "id": bearing_id,
            "type": "RollingElementBearing",
            "name": f"{model} Bearing - {position}",
            "properties": {
                "manufacturer": model.split()[0],
                "model": model,
                "position": position,
                "bearingType": "deep_groove_ball" if "63" in model else "spherical_roller",
                "innerDiameter": random.choice([60, 70, 80, 90, 100]),
                "outerDiameter": random.choice([110, 130, 150, 170, 180]),
                "width": random.choice([22, 25, 28, 31]),
                "dimensionUnit": "mm",
                "installationDate": generate_installation_date(),
                "lastGreasing": generate_last_maintenance(),
                "operatingHours": operating_hours,
                "healthScore": round(health_score, 1),
                "remainingUsefulLife": round(rul_hours, 0),
                "rulUnit": "hours",
                "primaryFailureMode": primary_failure_mode["mode"],
                "mtbf": primary_failure_mode["mtbf_hours"],
                "bpfo": bpfo,
                "bpfi": bpfi,
                "bsf": bsf,
                "ftf": ftf,
                "peakVibration": round(random.uniform(2, 8), 2),
                "rmsVibration": round(random.uniform(1, 4), 2),
                "temperature": round(random.uniform(40, 70), 1),
                "greaseCycles": random.randint(5, 50),
            }
        }))
        all_relationships.append((bearing_id, "partOf", equipment_id, None))
        all_relationships.append((equipment_id, "hasComponent", bearing_id, None))

    # =========================================================================
    # GEARBOXES
    # =========================================================================
    gearboxes = [
        {"id": "gearbox-agitator-001", "name": "Reactor Agitator Gearbox", "unit": "unit-cracking", "ratio": "25:1", "power": 75},
        {"id": "gearbox-agitator-002", "name": "Mixing Tank Gearbox", "unit": "unit-hydrotreating", "ratio": "15:1", "power": 55},
        {"id": "gearbox-conveyor-001", "name": "Belt Conveyor Gearbox", "unit": "unit-utilities", "ratio": "30:1", "power": 22},
    ]

    for gearbox in gearboxes:
        operating_hours = generate_operating_hours()
        primary_failure_mode = random.choice(GEARBOX_FAILURE_MODES)
        health_score = generate_health_score(operating_hours, primary_failure_mode["mtbf_hours"])
        rul_hours = max(0, primary_failure_mode["mtbf_hours"] - operating_hours + random.gauss(0, 1200))

        all_twins.append(prepare_pm_twin({
            "id": gearbox["id"],
            "type": "Gearbox",
            "name": gearbox["name"],
            "properties": {
                "gearboxType": random.choice(["helical", "planetary", "worm"]),
                "manufacturer": random.choice(["Flender", "SEW-Eurodrive", "Nord"]),
                "model": f"Model-{random.randint(1000, 9999)}",
                "gearRatio": gearbox["ratio"],
                "ratedPower": gearbox["power"],
                "powerUnit": "kW",
                "oilType": "ISO VG 320",
                "oilCapacity": random.randint(20, 100),
                "oilCapacityUnit": "liters",
                "installationDate": generate_installation_date(),
                "lastOilChange": generate_last_maintenance(),
                "operatingHours": operating_hours,
                "healthScore": round(health_score, 1),
                "remainingUsefulLife": round(rul_hours, 0),
                "rulUnit": "hours",
                "primaryFailureMode": primary_failure_mode["mode"],
                "mtbf": primary_failure_mode["mtbf_hours"],
                "oilViscosity": round(random.uniform(280, 360), 1),
                "waterContent": round(random.uniform(50, 500), 0),
                "waterContentUnit": "ppm",
                "particleCount": random.randint(15, 19),
                "ironContent": round(random.uniform(10, 150), 0),
                "ironContentUnit": "ppm",
                "vibrationLevel": round(random.uniform(2, 6), 2),
            }
        }))
        all_relationships.append((gearbox["unit"], "hasEquipment", gearbox["id"], None))

        # Oil condition sensor
        oil_sensor_id = f"sensor-{gearbox['id']}-oil"
        all_twins.append(prepare_pm_twin({
            "id": oil_sensor_id,
            "type": "OilConditionSensor",
            "name": f"{gearbox['name']} - Oil Monitor",
            "properties": {
                "manufacturer": OIL_SENSOR_CONFIG["manufacturer"],
                "model": OIL_SENSOR_CONFIG["model"],
                "parameters": OIL_SENSOR_CONFIG["parameters"],
                "status": "active",
            }
        }))
        all_relationships.append((oil_sensor_id, "monitors", gearbox["id"], None))

    # =========================================================================
    # COMPRESSORS
    # =========================================================================
    compressors = [
        {"id": "compressor-air-001", "name": "Plant Air Compressor A", "unit": "unit-utilities", "type": "screw", "power": 200},
        {"id": "compressor-air-002", "name": "Plant Air Compressor B", "unit": "unit-utilities", "type": "screw", "power": 200},
        {"id": "compressor-process-001", "name": "Process Gas Compressor", "unit": "unit-cracking", "type": "reciprocating", "power": 500},
        {"id": "compressor-hydrogen-001", "name": "Hydrogen Compressor", "unit": "unit-hydrotreating", "type": "reciprocating", "power": 350},
    ]

    for compressor in compressors:
        operating_hours = generate_operating_hours()
        primary_failure_mode = random.choice(COMPRESSOR_FAILURE_MODES)
        health_score = generate_health_score(operating_hours, primary_failure_mode["mtbf_hours"])
        rul_hours = max(0, primary_failure_mode["mtbf_hours"] - operating_hours + random.gauss(0, 1000))

        all_twins.append(prepare_pm_twin({
            "id": compressor["id"],
            "type": "IndustrialCompressor",
            "name": compressor["name"],
            "properties": {
                "compressorType": compressor["type"],
                "manufacturer": random.choice(["Atlas Copco", "Ingersoll Rand", "Gardner Denver"]),
                "model": f"Model-{random.randint(1000, 9999)}",
                "ratedPower": compressor["power"],
                "powerUnit": "kW",
                "dischargePress": random.randint(7, 40),
                "dischargePressUnit": "bar",
                "capacity": random.randint(500, 3000),
                "capacityUnit": "m3/h",
                "stages": random.choice([1, 2, 3]),
                "installationDate": generate_installation_date(),
                "lastMaintenance": generate_last_maintenance(),
                "operatingHours": operating_hours,
                "loadHours": round(operating_hours * random.uniform(0.6, 0.9), 0),
                "healthScore": round(health_score, 1),
                "remainingUsefulLife": round(rul_hours, 0),
                "rulUnit": "hours",
                "primaryFailureMode": primary_failure_mode["mode"],
                "mtbf": primary_failure_mode["mtbf_hours"],
                "dischargePressure": round(random.uniform(6, 35), 1),
                "dischargeTemperature": round(random.uniform(80, 150), 1),
                "suctionPressure": round(random.uniform(0.9, 5), 2),
                "oilPressure": round(random.uniform(3, 6), 1),
                "vibrationLevel": round(random.uniform(2, 5), 2),
            }
        }))
        all_relationships.append((compressor["unit"], "hasEquipment", compressor["id"], None))

    # =========================================================================
    # HEAT EXCHANGERS
    # =========================================================================
    heat_exchangers = [
        {"id": "hx-crude-001", "name": "Crude Preheat Exchanger 1", "unit": "unit-distillation", "type": "shell_tube"},
        {"id": "hx-crude-002", "name": "Crude Preheat Exchanger 2", "unit": "unit-distillation", "type": "shell_tube"},
        {"id": "hx-overhead-001", "name": "Overhead Condenser", "unit": "unit-distillation", "type": "shell_tube"},
        {"id": "hx-reboiler-001", "name": "Column Reboiler", "unit": "unit-distillation", "type": "kettle"},
        {"id": "hx-fcc-001", "name": "FCC Feed/Effluent Exchanger", "unit": "unit-cracking", "type": "shell_tube"},
        {"id": "hx-cooling-001", "name": "Process Cooler", "unit": "unit-utilities", "type": "plate"},
    ]

    for hx in heat_exchangers:
        operating_hours = generate_operating_hours()
        primary_failure_mode = random.choice(HEAT_EXCHANGER_FAILURE_MODES)
        health_score = generate_health_score(operating_hours, primary_failure_mode["mtbf_hours"])
        rul_hours = max(0, primary_failure_mode["mtbf_hours"] - operating_hours + random.gauss(0, 800))

        clean_u = random.uniform(800, 1500)
        fouling_factor = 1 - (operating_hours / 50000) * random.uniform(0.1, 0.3)
        current_u = clean_u * max(0.5, fouling_factor)

        all_twins.append(prepare_pm_twin({
            "id": hx["id"],
            "type": "HeatExchanger",
            "name": hx["name"],
            "properties": {
                "exchangerType": hx["type"],
                "manufacturer": random.choice(["Alfa Laval", "Koch Heat Transfer", "API Heat Transfer"]),
                "model": f"Model-{random.randint(1000, 9999)}",
                "heatDuty": random.randint(500, 5000),
                "heatDutyUnit": "kW",
                "surfaceArea": random.randint(50, 500),
                "surfaceAreaUnit": "m2",
                "designPressure": random.randint(10, 50),
                "designPressureUnit": "bar",
                "designTemperature": random.randint(150, 400),
                "designTempUnit": "C",
                "installationDate": generate_installation_date(),
                "lastCleaning": generate_last_maintenance(),
                "operatingHours": operating_hours,
                "healthScore": round(health_score, 1),
                "remainingUsefulLife": round(rul_hours, 0),
                "rulUnit": "hours",
                "primaryFailureMode": primary_failure_mode["mode"],
                "mtbf": primary_failure_mode["mtbf_hours"],
                "cleanUValue": round(clean_u, 1),
                "currentUValue": round(current_u, 1),
                "uValueUnit": "W/m2K",
                "foulingFactor": round(1 - fouling_factor, 3),
                "approachTemperature": round(random.uniform(5, 25), 1),
                "shellPressureDrop": round(random.uniform(0.2, 1.5), 2),
                "tubePressureDrop": round(random.uniform(0.3, 2.0), 2),
                "pressureDropUnit": "bar",
            }
        }))
        all_relationships.append((hx["unit"], "hasEquipment", hx["id"], None))

    # =========================================================================
    # MAINTENANCE WORK ORDERS (Historical and Scheduled)
    # =========================================================================
    work_orders = [
        {"id": "wo-001", "equipment": "pump-feed-001", "type": "preventive", "status": "completed", "date": -90, "description": "Seal replacement and alignment check"},
        {"id": "wo-002", "equipment": "motor-feed-001", "type": "predictive", "status": "completed", "date": -60, "description": "Bearing replacement based on vibration analysis"},
        {"id": "wo-003", "equipment": "pump-fcc-001", "type": "corrective", "status": "completed", "date": -30, "description": "Emergency impeller repair"},
        {"id": "wo-004", "equipment": "compressor-air-001", "type": "preventive", "status": "scheduled", "date": 15, "description": "Valve inspection and replacement"},
        {"id": "wo-005", "equipment": "gearbox-agitator-001", "type": "preventive", "status": "scheduled", "date": 30, "description": "Oil change and alignment verification"},
        {"id": "wo-006", "equipment": "hx-crude-001", "type": "preventive", "status": "scheduled", "date": 45, "description": "Tube bundle cleaning"},
        {"id": "wo-007", "equipment": "pump-cooling-001", "type": "predictive", "status": "pending_parts", "date": 7, "description": "Bearing replacement - high vibration detected"},
        {"id": "wo-008", "equipment": "motor-fcc-002", "type": "predictive", "status": "in_progress", "date": 0, "description": "Winding insulation testing"},
    ]

    for wo in work_orders:
        wo_date = (datetime.now() + timedelta(days=wo["date"])).strftime("%Y-%m-%d")
        mttr = random.randint(2, 24)
        cost = random.randint(500, 25000) if wo["type"] != "preventive" else random.randint(200, 5000)

        all_twins.append(prepare_pm_twin({
            "id": wo["id"],
            "type": "MaintenanceWorkOrder",
            "name": f"WO-{wo['id'].upper()} - {wo['description'][:40]}",
            "properties": {
                "workOrderType": wo["type"],
                "status": wo["status"],
                "priority": "critical" if wo["type"] == "corrective" else ("high" if wo["type"] == "predictive" else "medium"),
                "description": wo["description"],
                "scheduledDate": wo_date,
                "estimatedDuration": mttr,
                "durationUnit": "hours",
                "estimatedCost": cost,
                "costCurrency": "USD",
                "technician": random.choice(["John Smith", "Maria Garcia", "Ahmed Hassan", "Lisa Chen"]),
                "spareParts": random.choice([
                    ["Mechanical Seal Kit", "O-Rings"],
                    ["Bearing SKF 6316", "Grease Cartridge"],
                    ["Valve Assembly", "Gasket Set"],
                    ["Coupling Insert", "Alignment Shims"],
                ]),
            }
        }))
        all_relationships.append((wo["id"], "targetEquipment", wo["equipment"], None))
        all_relationships.append((wo["equipment"], "hasWorkOrder", wo["id"], None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, _ = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships via bulk API...")
    relationships_created, _ = bulk_add_relationships(client, all_relationships)

    print_summary("Predictive Maintenance", twins_created, relationships_created)
    logger.info("Predictive Maintenance digital twin network seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Predictive Maintenance data")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--clean", action="store_true", help="Clean existing data first")
    args = parser.parse_args()

    seed_predictive_maintenance(args.base_url, args.clean)
