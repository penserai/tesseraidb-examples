#!/usr/bin/env python3
"""
Healthcare / Hospital Digital Twin Example

This example creates a comprehensive digital twin of a hospital,
including departments, medical equipment, patient rooms, and monitoring systems.

Domain: Healthcare / Medical
Use Cases:
  - Medical equipment asset tracking and maintenance
  - Patient flow optimization
  - Resource allocation and capacity planning
  - Equipment utilization analytics
  - Compliance and regulatory tracking
  - Emergency response coordination
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
DOMAIN = "healthcare"
HEALTH_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_healthcare_twin(data: dict) -> dict:
    """Prepare a twin dict for the healthcare domain with proper namespace.

    Returns the dict without making any API calls.
    """
    # Expand type to full URI if it's a short name
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{HEALTH_NS}{twin_type}"

    # Add domain tag
    data["domain"] = DOMAIN

    return data


def seed_healthcare():
    """Seed the healthcare digital twin."""
    client = get_client()

    # Collect all twins and relationships for bulk operations
    all_twins = []
    all_relationships = []

    # =========================================================================
    # HOSPITAL
    # =========================================================================
    all_twins.append(prepare_healthcare_twin({
        "id": "hospital-central-001",
        "type": "Hospital",
        "name": "Central Medical Center",
        "description": "Level 1 Trauma Center with comprehensive medical services",
        "properties": {
            "address": "500 Medical Plaza Drive, Boston, MA 02115",
            "beds": 650,
            "operatingRooms": 24,
            "emergencyBays": 48,
            "icuBeds": 120,
            "employees": 4500,
            "accreditations": ["Joint Commission", "Magnet Recognition", "Level 1 Trauma"],
            "coordinates": {"lat": 42.3601, "lng": -71.0589},
            "founded": 1892
        }
    }))

    # =========================================================================
    # BUILDINGS
    # =========================================================================
    buildings = [
        {"id": "building-main", "name": "Main Hospital Building", "floors": 12, "area": 50000},
        {"id": "building-cancer", "name": "Cancer Treatment Center", "floors": 6, "area": 15000},
        {"id": "building-cardiac", "name": "Cardiac Care Pavilion", "floors": 8, "area": 20000},
        {"id": "building-pediatric", "name": "Children's Hospital Wing", "floors": 5, "area": 12000},
        {"id": "building-research", "name": "Medical Research Center", "floors": 10, "area": 25000},
    ]

    for bldg in buildings:
        all_twins.append(prepare_healthcare_twin({
            "id": bldg["id"],
            "type": "HospitalBuilding",
            "name": bldg["name"],
            "properties": {
                "floors": bldg["floors"],
                "totalArea": bldg["area"],
                "areaUnit": "sqm",
                "hasHelipad": bldg["id"] == "building-main",
                "emergencyAccess": bldg["id"] in ["building-main", "building-cardiac"]
            }
        }))
        all_relationships.append(("hospital-central-001", "hasBuilding", bldg["id"], None))

    # =========================================================================
    # DEPARTMENTS
    # =========================================================================
    departments = [
        {"id": "dept-emergency", "name": "Emergency Department", "building": "building-main", "floor": 1, "beds": 48},
        {"id": "dept-icu", "name": "Intensive Care Unit", "building": "building-main", "floor": 3, "beds": 60},
        {"id": "dept-nicu", "name": "Neonatal ICU", "building": "building-pediatric", "floor": 2, "beds": 30},
        {"id": "dept-surgery", "name": "Surgical Services", "building": "building-main", "floor": 4, "beds": 0},
        {"id": "dept-cardiology", "name": "Cardiology Department", "building": "building-cardiac", "floor": 2, "beds": 45},
        {"id": "dept-oncology", "name": "Oncology Department", "building": "building-cancer", "floor": 3, "beds": 40},
        {"id": "dept-radiology", "name": "Radiology Department", "building": "building-main", "floor": 1, "beds": 0},
        {"id": "dept-lab", "name": "Clinical Laboratory", "building": "building-main", "floor": 2, "beds": 0},
        {"id": "dept-pharmacy", "name": "Pharmacy", "building": "building-main", "floor": 1, "beds": 0},
        {"id": "dept-neurology", "name": "Neurology Department", "building": "building-main", "floor": 7, "beds": 35},
        {"id": "dept-orthopedics", "name": "Orthopedics Department", "building": "building-main", "floor": 6, "beds": 40},
        {"id": "dept-pediatrics", "name": "Pediatrics Department", "building": "building-pediatric", "floor": 3, "beds": 50},
    ]

    for dept in departments:
        all_twins.append(prepare_healthcare_twin({
            "id": dept["id"],
            "type": "HospitalDepartment",
            "name": dept["name"],
            "properties": {
                "floor": dept["floor"],
                "totalBeds": dept["beds"],
                "occupiedBeds": int(dept["beds"] * 0.75) if dept["beds"] > 0 else 0,
                "staffOnDuty": 15 + (dept["beds"] // 5),
                "status": "operational"
            }
        }))
        all_relationships.append((dept["building"], "hasDepartment", dept["id"], None))

    # =========================================================================
    # OPERATING ROOMS
    # =========================================================================
    operating_rooms = [
        {"id": "or-001", "name": "OR 1 - General Surgery", "type": "general", "size": "large"},
        {"id": "or-002", "name": "OR 2 - General Surgery", "type": "general", "size": "large"},
        {"id": "or-003", "name": "OR 3 - Cardiac Surgery", "type": "cardiac", "size": "large"},
        {"id": "or-004", "name": "OR 4 - Cardiac Surgery", "type": "cardiac", "size": "large"},
        {"id": "or-005", "name": "OR 5 - Neurosurgery", "type": "neuro", "size": "large"},
        {"id": "or-006", "name": "OR 6 - Orthopedic Surgery", "type": "orthopedic", "size": "large"},
        {"id": "or-007", "name": "OR 7 - Orthopedic Surgery", "type": "orthopedic", "size": "medium"},
        {"id": "or-008", "name": "OR 8 - Robotic Surgery", "type": "robotic", "size": "large"},
        {"id": "or-009", "name": "OR 9 - Minimally Invasive", "type": "laparoscopic", "size": "medium"},
        {"id": "or-010", "name": "OR 10 - Trauma", "type": "trauma", "size": "large"},
    ]

    for or_room in operating_rooms:
        all_twins.append(prepare_healthcare_twin({
            "id": or_room["id"],
            "type": "OperatingRoom",
            "name": or_room["name"],
            "properties": {
                "surgeryType": or_room["type"],
                "size": or_room["size"],
                "status": "available",
                "laminarFlowClass": "ISO 5",
                "hasRoboticSystem": or_room["type"] == "robotic",
                "hasIntraopMRI": or_room["type"] == "neuro",
                "temperature": 18,
                "humidity": 50,
                "lastCleaned": "2024-12-15T06:00:00Z",
                "nextScheduled": "2024-12-15T14:00:00Z"
            }
        }))
        all_relationships.append(("dept-surgery", "hasOperatingRoom", or_room["id"], None))

    # =========================================================================
    # PATIENT ROOMS (ICU)
    # =========================================================================
    for i in range(1, 21):
        room_id = f"room-icu-{i:03d}"
        all_twins.append(prepare_healthcare_twin({
            "id": room_id,
            "type": "PatientRoom",
            "name": f"ICU Room {i}",
            "properties": {
                "roomType": "ICU",
                "bedCount": 1,
                "isOccupied": i <= 15,
                "hasNegativePressure": i <= 5,
                "hasIsolationCapability": True,
                "monitoringLevel": "continuous",
                "lastSanitized": "2024-12-15T06:00:00Z"
            }
        }))
        all_relationships.append(("dept-icu", "hasRoom", room_id, None))

    # =========================================================================
    # MEDICAL IMAGING EQUIPMENT
    # =========================================================================
    imaging_equipment = [
        {"id": "mri-001", "name": "MRI Scanner 1", "type": "MRI", "manufacturer": "Siemens", "model": "MAGNETOM Vida 3T"},
        {"id": "mri-002", "name": "MRI Scanner 2", "type": "MRI", "manufacturer": "GE Healthcare", "model": "SIGNA Premier 3T"},
        {"id": "ct-001", "name": "CT Scanner 1", "type": "CT", "manufacturer": "Siemens", "model": "SOMATOM Force"},
        {"id": "ct-002", "name": "CT Scanner 2", "type": "CT", "manufacturer": "GE Healthcare", "model": "Revolution CT"},
        {"id": "ct-003", "name": "CT Scanner ED", "type": "CT", "manufacturer": "Canon", "model": "Aquilion ONE"},
        {"id": "xray-001", "name": "X-Ray Room 1", "type": "X-Ray", "manufacturer": "Philips", "model": "DigitalDiagnost C90"},
        {"id": "xray-002", "name": "X-Ray Room 2", "type": "X-Ray", "manufacturer": "Siemens", "model": "Ysio Max"},
        {"id": "xray-mobile-001", "name": "Portable X-Ray 1", "type": "PortableXRay", "manufacturer": "GE Healthcare", "model": "Optima XR220amx"},
        {"id": "xray-mobile-002", "name": "Portable X-Ray 2", "type": "PortableXRay", "manufacturer": "Siemens", "model": "Mobilett Mira Max"},
        {"id": "ultrasound-001", "name": "Ultrasound 1", "type": "Ultrasound", "manufacturer": "GE Healthcare", "model": "Voluson E10"},
        {"id": "ultrasound-002", "name": "Ultrasound 2", "type": "Ultrasound", "manufacturer": "Philips", "model": "EPIQ Elite"},
        {"id": "pet-ct-001", "name": "PET-CT Scanner", "type": "PET-CT", "manufacturer": "Siemens", "model": "Biograph Vision Quadra"},
        {"id": "mammography-001", "name": "Mammography System", "type": "Mammography", "manufacturer": "Hologic", "model": "3Dimensions"},
        {"id": "fluoro-001", "name": "Fluoroscopy Suite", "type": "Fluoroscopy", "manufacturer": "Philips", "model": "Allura Xper FD20"},
    ]

    for equip in imaging_equipment:
        all_twins.append(prepare_healthcare_twin({
            "id": equip["id"],
            "type": equip["type"],
            "name": equip["name"],
            "properties": {
                "manufacturer": equip["manufacturer"],
                "model": equip["model"],
                "serialNumber": f"SN-{equip['id'].upper()}-2024",
                "status": "available",
                "installDate": "2022-06-15",
                "lastMaintenance": "2024-11-01",
                "nextMaintenance": "2025-05-01",
                "scansToday": 12,
                "scansThisMonth": 320,
                "calibrationStatus": "current",
                "radiationDoseTracking": equip["type"] in ["CT", "X-Ray", "PET-CT", "Fluoroscopy"]
            }
        }))
        all_relationships.append(("dept-radiology", "hasEquipment", equip["id"], None))

    # =========================================================================
    # PATIENT MONITORING EQUIPMENT
    # =========================================================================
    # Bedside monitors for ICU
    for i in range(1, 21):
        monitor_id = f"monitor-icu-{i:03d}"
        all_twins.append(prepare_healthcare_twin({
            "id": monitor_id,
            "type": "PatientMonitor",
            "name": f"ICU Bedside Monitor {i}",
            "properties": {
                "manufacturer": "Philips",
                "model": "IntelliVue MX800",
                "serialNumber": f"SN-MON-{i:05d}",
                "capabilities": ["ECG", "SpO2", "NIBP", "IBP", "Temperature", "Capnography", "Cardiac Output"],
                "status": "active" if i <= 15 else "standby",
                "alarmStatus": "normal",
                "lastCalibration": "2024-10-15",
                "firmwareVersion": "L.01.23"
            }
        }))
        all_relationships.append((monitor_id, "locatedIn", f"room-icu-{i:03d}", None))

    # Ventilators
    ventilators = [
        {"id": "vent-001", "room": "room-icu-001"},
        {"id": "vent-002", "room": "room-icu-002"},
        {"id": "vent-003", "room": "room-icu-003"},
        {"id": "vent-004", "room": "room-icu-005"},
        {"id": "vent-005", "room": "room-icu-008"},
        {"id": "vent-006", "room": "room-icu-010"},
        {"id": "vent-007", "room": "room-icu-012"},
        {"id": "vent-008", "room": "room-icu-015"},
    ]

    for vent in ventilators:
        all_twins.append(prepare_healthcare_twin({
            "id": vent["id"],
            "type": "Ventilator",
            "name": f"Ventilator {vent['id'][-3:]}",
            "properties": {
                "manufacturer": "Medtronic",
                "model": "Puritan Bennett 980",
                "serialNumber": f"SN-VENT-{vent['id'][-3:]}",
                "status": "in_use",
                "mode": "SIMV-PC",
                "tidalVolume": 450,
                "tidalVolumeUnit": "mL",
                "respiratoryRate": 14,
                "peep": 8,
                "fio2": 40,
                "hoursInUse": 72,
                "lastMaintenance": "2024-11-15"
            }
        }))
        all_relationships.append((vent["id"], "locatedIn", vent["room"], None))

    # Infusion Pumps
    for i in range(1, 31):
        pump_id = f"infusion-pump-{i:03d}"
        all_twins.append(prepare_healthcare_twin({
            "id": pump_id,
            "type": "InfusionPump",
            "name": f"Infusion Pump {i}",
            "properties": {
                "manufacturer": "BD",
                "model": "Alaris System",
                "serialNumber": f"SN-PUMP-{i:05d}",
                "status": "in_use" if i <= 20 else "available",
                "channels": 4,
                "drugLibraryVersion": "2024.3",
                "batteryLevel": 85,
                "lastMaintenance": "2024-09-01"
            }
        }))
        if i <= 15:
            all_relationships.append((pump_id, "locatedIn", f"room-icu-{i:03d}", None))

    # =========================================================================
    # SURGICAL ROBOTS
    # =========================================================================
    surgical_robots = [
        {"id": "robot-davinci-001", "name": "da Vinci Xi Surgical System #1", "type": "DaVinciRobot"},
        {"id": "robot-davinci-002", "name": "da Vinci Xi Surgical System #2", "type": "DaVinciRobot"},
        {"id": "robot-mako-001", "name": "MAKO Robotic Arm", "type": "MAKORobot"},
        {"id": "robot-rosa-001", "name": "ROSA Brain Neurosurgical Robot", "type": "ROSARobot"},
    ]

    for robot in surgical_robots:
        all_twins.append(prepare_healthcare_twin({
            "id": robot["id"],
            "type": robot["type"],
            "name": robot["name"],
            "properties": {
                "manufacturer": "Intuitive Surgical" if "davinci" in robot["id"] else ("Stryker" if "mako" in robot["id"] else "Zimmer Biomet"),
                "status": "available",
                "proceduresCompleted": 450,
                "hoursOfOperation": 2200,
                "lastCalibration": "2024-12-01",
                "softwareVersion": "4.5.1",
                "lastMaintenance": "2024-11-15"
            }
        }))
        all_relationships.append(("dept-surgery", "hasEquipment", robot["id"], None))

    # Link robots to specific ORs
    all_relationships.append(("robot-davinci-001", "installedIn", "or-008", None))
    all_relationships.append(("robot-mako-001", "installedIn", "or-006", None))
    all_relationships.append(("robot-rosa-001", "installedIn", "or-005", None))

    # =========================================================================
    # LABORATORY EQUIPMENT
    # =========================================================================
    lab_equipment = [
        {"id": "lab-analyzer-001", "name": "Chemistry Analyzer", "type": "ChemistryAnalyzer", "manufacturer": "Roche", "model": "Cobas 8000"},
        {"id": "lab-analyzer-002", "name": "Hematology Analyzer", "type": "HematologyAnalyzer", "manufacturer": "Sysmex", "model": "XN-9000"},
        {"id": "lab-analyzer-003", "name": "Blood Gas Analyzer", "type": "BloodGasAnalyzer", "manufacturer": "Radiometer", "model": "ABL90 FLEX"},
        {"id": "lab-analyzer-004", "name": "Coagulation Analyzer", "type": "CoagulationAnalyzer", "manufacturer": "Siemens", "model": "CS-5100"},
        {"id": "lab-analyzer-005", "name": "Urinalysis System", "type": "UrinalysisAnalyzer", "manufacturer": "Beckman Coulter", "model": "iRICELL"},
        {"id": "lab-centrifuge-001", "name": "High-Speed Centrifuge", "type": "Centrifuge", "manufacturer": "Beckman Coulter", "model": "Allegra X-30R"},
        {"id": "lab-pcr-001", "name": "PCR System", "type": "PCRMachine", "manufacturer": "Roche", "model": "LightCycler 480 II"},
    ]

    for equip in lab_equipment:
        all_twins.append(prepare_healthcare_twin({
            "id": equip["id"],
            "type": equip["type"],
            "name": equip["name"],
            "properties": {
                "manufacturer": equip["manufacturer"],
                "model": equip["model"],
                "status": "operational",
                "testsToday": 250,
                "testsThisMonth": 6500,
                "lastCalibration": "2024-12-01",
                "qcStatus": "passed"
            }
        }))
        all_relationships.append(("dept-lab", "hasEquipment", equip["id"], None))

    # =========================================================================
    # PHARMACY AUTOMATION
    # =========================================================================
    pharmacy_systems = [
        {"id": "pharmacy-robot-001", "name": "Automated Dispensing System", "type": "PharmacyRobot"},
        {"id": "pharmacy-cabinet-001", "name": "Medication Cabinet - ED", "type": "MedicationCabinet", "location": "dept-emergency"},
        {"id": "pharmacy-cabinet-002", "name": "Medication Cabinet - ICU", "type": "MedicationCabinet", "location": "dept-icu"},
        {"id": "pharmacy-cabinet-003", "name": "Medication Cabinet - Surgery", "type": "MedicationCabinet", "location": "dept-surgery"},
    ]

    for sys_item in pharmacy_systems:
        all_twins.append(prepare_healthcare_twin({
            "id": sys_item["id"],
            "type": sys_item["type"],
            "name": sys_item["name"],
            "properties": {
                "manufacturer": "BD Pyxis",
                "status": "operational",
                "inventoryLevel": 92,
                "lastRestock": "2024-12-14T22:00:00Z",
                "dispensesToday": 145 if "robot" in sys_item["id"] else 85,
                "controlledSubstanceTracking": True
            }
        }))
        if "location" in sys_item:
            all_relationships.append((sys_item["id"], "locatedIn", sys_item["location"], None))
        else:
            all_relationships.append(("dept-pharmacy", "hasEquipment", sys_item["id"], None))

    # =========================================================================
    # NURSE CALL SYSTEM
    # =========================================================================
    all_twins.append(prepare_healthcare_twin({
        "id": "nurse-call-system",
        "type": "NurseCallSystem",
        "name": "Hospital Nurse Call System",
        "properties": {
            "manufacturer": "Hill-Rom",
            "model": "Voalte Platform",
            "totalStations": 650,
            "activeStations": 480,
            "averageResponseTime": 45,
            "responseTimeUnit": "seconds",
            "status": "operational"
        }
    }))
    all_relationships.append(("hospital-central-001", "hasSystem", "nurse-call-system", None))

    # =========================================================================
    # HVAC - MEDICAL GRADE
    # =========================================================================
    all_twins.append(prepare_healthcare_twin({
        "id": "hvac-medical-001",
        "type": "MedicalHVAC",
        "name": "Medical Grade HVAC System",
        "properties": {
            "manufacturer": "Trane",
            "zones": ["Operating Rooms", "ICU", "Isolation Rooms", "Clean Rooms"],
            "hepaFilterEfficiency": 99.97,
            "airChangesPerHour": {
                "OR": 20,
                "ICU": 12,
                "Isolation": 12,
                "General": 6
            },
            "temperatureControl": True,
            "humidityControl": True,
            "pressureDifferentialMonitoring": True,
            "status": "operational"
        }
    }))
    all_relationships.append(("hospital-central-001", "hasSystem", "hvac-medical-001", None))

    # =========================================================================
    # MEDICAL GAS SYSTEMS
    # =========================================================================
    gas_systems = [
        {"id": "gas-oxygen-001", "name": "Oxygen Supply System", "gas": "O2"},
        {"id": "gas-nitrogen-001", "name": "Nitrogen Supply System", "gas": "N2"},
        {"id": "gas-nitrous-001", "name": "Nitrous Oxide System", "gas": "N2O"},
        {"id": "gas-vacuum-001", "name": "Medical Vacuum System", "gas": "Vacuum"},
        {"id": "gas-air-001", "name": "Medical Air System", "gas": "Air"},
    ]

    for gas in gas_systems:
        all_twins.append(prepare_healthcare_twin({
            "id": gas["id"],
            "type": "MedicalGasSystem",
            "name": gas["name"],
            "properties": {
                "gasType": gas["gas"],
                "pressure": 55 if gas["gas"] != "Vacuum" else -15,
                "pressureUnit": "PSI",
                "tankLevel": 78,
                "status": "normal",
                "lastInspection": "2024-11-01",
                "alarmThreshold": 20
            }
        }))
        all_relationships.append(("hospital-central-001", "hasSystem", gas["id"], None))

    # =========================================================================
    # STERILIZATION EQUIPMENT
    # =========================================================================
    sterilizers = [
        {"id": "sterilizer-001", "name": "Steam Sterilizer 1", "type": "autoclave", "capacity": "large"},
        {"id": "sterilizer-002", "name": "Steam Sterilizer 2", "type": "autoclave", "capacity": "large"},
        {"id": "sterilizer-003", "name": "Low-Temp Sterilizer", "type": "plasma", "capacity": "medium"},
        {"id": "sterilizer-004", "name": "ETO Sterilizer", "type": "ethyleneOxide", "capacity": "large"},
    ]

    for ster in sterilizers:
        all_twins.append(prepare_healthcare_twin({
            "id": ster["id"],
            "type": "Sterilizer",
            "name": ster["name"],
            "properties": {
                "sterilizationType": ster["type"],
                "capacity": ster["capacity"],
                "manufacturer": "STERIS",
                "cyclesToday": 8,
                "status": "idle",
                "lastValidation": "2024-11-15",
                "biologicalIndicatorStatus": "passed"
            }
        }))
        all_relationships.append(("dept-surgery", "hasEquipment", ster["id"], None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, twins_failed = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships...")
    relationships_created, relationships_failed = bulk_add_relationships(client, all_relationships)

    print_summary("Healthcare / Hospital", twins_created, relationships_created)
    logger.info("Healthcare digital twin seeded successfully!")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_healthcare()
