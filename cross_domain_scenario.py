#!/usr/bin/env python3
"""
Cross-Domain Interoperability Scenario

This example demonstrates how digital twins from different domains can
interoperate through shared ontology concepts and cross-domain relationships.

Scenario: Smart Hospital with Integrated Systems
================================================

This scenario models a modern hospital that integrates:

1. HEALTHCARE Domain:
   - Hospital facility and medical departments
   - Medical devices (MRI, ventilators, monitors)
   - Surgical robots
   - Vaccine cold storage

2. SMART BUILDING Domain:
   - HVAC systems for temperature control
   - Lighting systems
   - Access control systems
   - Environmental sensors

3. ROBOTICS Domain:
   - Material handling robots for supply delivery
   - Cleaning robots
   - Pharmacy automation

4. SUPPLY CHAIN Domain:
   - Medical supply warehousing
   - Pharmaceutical logistics
   - Cold chain management

5. ENERGY GRID Domain:
   - Hospital power systems
   - Backup generators
   - Solar panels

Cross-Domain Relationships:
===========================
- Hospital (healthcare) --> hasBuilding --> Building (smart_building)
- HVAC (smart_building) --> maintains --> Operating Room (healthcare)
- Material Robot (robotics) --> deliversTo --> Pharmacy (healthcare)
- Cold Storage (supply_chain) --> stores --> Vaccine (healthcare)
- Solar Panel (energy_grid) --> powers --> Building (smart_building)

This demonstrates:
- Shared core concepts (facilities, equipment, sensors)
- Domain-specific specializations
- Cross-domain relationships for integrated operations
- Unified querying across domains
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (
    get_client,
    create_twin_safe,
    add_relationship_safe,
    DOMAIN_NAMESPACES,
    DTAAS_CORE_NS,
)


def create_domain_twin(client, domain: str, twin_id: str, twin_type: str,
                       name: str, description: str = None, properties: dict = None):
    """Create a twin with domain namespace and tagging."""
    namespace = DOMAIN_NAMESPACES.get(domain, DTAAS_CORE_NS)
    full_type = f"{namespace}{twin_type}"

    data = {
        "id": twin_id,
        "type": full_type,
        "name": name,
        "domain": domain,
        "properties": properties or {},
    }
    if description:
        data["description"] = description

    return create_twin_safe(client, data)


def seed_cross_domain_scenario():
    """Create the cross-domain hospital scenario."""
    client = get_client()
    twins_created = 0
    rels_created = 0

    print("\n" + "=" * 70)
    print(" Cross-Domain Interoperability Scenario: Smart Hospital")
    print("=" * 70)

    # =========================================================================
    # HEALTHCARE DOMAIN - Hospital Core
    # =========================================================================
    print("\n[1/5] Creating Healthcare domain twins...")

    create_domain_twin(client, "healthcare",
        twin_id="smart-hospital-central",
        twin_type="Hospital",
        name="Central Smart Hospital",
        description="Modern integrated hospital with cross-domain systems",
        properties={
            "beds": 500,
            "departments": 15,
            "operatingRooms": 20,
            "icuBeds": 50,
            "emergencyBays": 30,
            "staff": 2500,
            "annualPatients": 150000
        }
    )
    twins_created += 1

    # Operating Rooms
    for i in range(1, 5):
        create_domain_twin(client, "healthcare",
            twin_id=f"or-room-{i:02d}",
            twin_type="OperatingRoom",
            name=f"Operating Room {i}",
            properties={
                "specialty": ["cardiac", "neuro", "orthopedic", "general"][i-1],
                "class": "ISO 5",
                "size": 60,
                "sizeUnit": "sqm"
            }
        )
        twins_created += 1
        add_relationship_safe(client, "smart-hospital-central", "hasDepartment", f"or-room-{i:02d}")
        rels_created += 1

    # ICU
    create_domain_twin(client, "healthcare",
        twin_id="icu-main",
        twin_type="ICU",
        name="Main Intensive Care Unit",
        properties={"beds": 30, "isolationRooms": 5, "monitors": 30}
    )
    twins_created += 1
    add_relationship_safe(client, "smart-hospital-central", "hasDepartment", "icu-main")
    rels_created += 1

    # Pharmacy
    create_domain_twin(client, "healthcare",
        twin_id="pharmacy-central",
        twin_type="Pharmacy",
        name="Central Pharmacy",
        properties={"automatedDispensers": 4, "refrigerators": 8, "controlledSubstanceVault": True}
    )
    twins_created += 1
    add_relationship_safe(client, "smart-hospital-central", "hasDepartment", "pharmacy-central")
    rels_created += 1

    # Medical Devices
    medical_devices = [
        {"id": "mri-001", "type": "MRI", "name": "MRI Scanner 1", "props": {"tesla": 3.0, "manufacturer": "Siemens"}},
        {"id": "mri-002", "type": "MRI", "name": "MRI Scanner 2", "props": {"tesla": 1.5, "manufacturer": "GE Healthcare"}},
        {"id": "ct-001", "type": "CTScanner", "name": "CT Scanner 1", "props": {"slices": 128, "manufacturer": "Philips"}},
        {"id": "surgical-robot-001", "type": "SurgicalRobot", "name": "Da Vinci Xi System", "props": {"arms": 4, "manufacturer": "Intuitive Surgical"}},
        {"id": "ventilator-001", "type": "Ventilator", "name": "ICU Ventilator 1", "props": {"modes": ["SIMV", "CPAP", "BiPAP"]}},
    ]

    for device in medical_devices:
        create_domain_twin(client, "healthcare",
            twin_id=device["id"],
            twin_type=device["type"],
            name=device["name"],
            properties=device["props"]
        )
        twins_created += 1

    # Surgical robot in OR
    add_relationship_safe(client, "surgical-robot-001", "installedIn", "or-room-01")
    rels_created += 1

    # Vaccines
    create_domain_twin(client, "healthcare",
        twin_id="vaccine-batch-flu-2024",
        twin_type="Vaccine",
        name="Influenza Vaccine Batch 2024",
        properties={
            "batchNumber": "FLU-2024-12345",
            "doses": 5000,
            "requiredTemp": -20,
            "tempUnit": "celsius",
            "expiryDate": "2026-06-01"
        }
    )
    twins_created += 1

    # =========================================================================
    # SMART BUILDING DOMAIN - Hospital Building Infrastructure
    # =========================================================================
    print("[2/5] Creating Smart Building domain twins...")

    create_domain_twin(client, "smart_building",
        twin_id="hospital-building-main",
        twin_type="Building",
        name="Hospital Main Building",
        properties={
            "floors": 8,
            "area": 50000,
            "areaUnit": "sqm",
            "yearBuilt": 2020,
            "energyRating": "A+"
        }
    )
    twins_created += 1

    # HVAC Systems
    hvac_systems = [
        {"id": "hvac-or-001", "name": "OR HVAC System 1", "zone": "or-room-01", "type": "surgical"},
        {"id": "hvac-or-002", "name": "OR HVAC System 2", "zone": "or-room-02", "type": "surgical"},
        {"id": "hvac-icu", "name": "ICU HVAC System", "zone": "icu-main", "type": "critical"},
        {"id": "hvac-pharmacy", "name": "Pharmacy HVAC", "zone": "pharmacy-central", "type": "controlled"},
    ]

    for hvac in hvac_systems:
        create_domain_twin(client, "smart_building",
            twin_id=hvac["id"],
            twin_type="HVACSystem",
            name=hvac["name"],
            properties={
                "hvacType": hvac["type"],
                "airChangesPerHour": 20 if hvac["type"] == "surgical" else 12,
                "hepaFilterClass": "H14" if hvac["type"] in ["surgical", "critical"] else "H13",
                "status": "running"
            }
        )
        twins_created += 1
        # Cross-domain relationship: HVAC maintains healthcare zone
        add_relationship_safe(client, hvac["id"], "maintains", hvac["zone"])
        rels_created += 1

    # Environmental Sensors
    for i in range(1, 5):
        for sensor_type in ["Temperature", "Humidity", "Pressure"]:
            sensor_id = f"sensor-{sensor_type.lower()}-or{i:02d}"
            create_domain_twin(client, "smart_building",
                twin_id=sensor_id,
                twin_type=f"{sensor_type}Sensor",
                name=f"OR-{i} {sensor_type} Sensor",
                properties={"accuracy": 0.1 if sensor_type == "Temperature" else 1.0}
            )
            twins_created += 1
            add_relationship_safe(client, sensor_id, "monitors", f"or-room-{i:02d}")
            rels_created += 1

    # =========================================================================
    # ROBOTICS DOMAIN - Hospital Automation
    # =========================================================================
    print("[3/5] Creating Robotics domain twins...")

    # Material Delivery Robots
    for i in range(1, 6):
        create_domain_twin(client, "robotics",
            twin_id=f"delivery-robot-{i:03d}",
            twin_type="DeliveryRobot",
            name=f"Material Delivery Robot {i}",
            properties={
                "manufacturer": "Aethon",
                "model": "TUG T3",
                "payload": 200,
                "payloadUnit": "kg",
                "batteryLevel": 75 + i * 5,
                "status": "idle"
            }
        )
        twins_created += 1
        # Cross-domain: Robots deliver to pharmacy
        add_relationship_safe(client, f"delivery-robot-{i:03d}", "deliversTo", "pharmacy-central")
        rels_created += 1

    # Cleaning Robots
    for i in range(1, 4):
        create_domain_twin(client, "robotics",
            twin_id=f"cleaning-robot-{i:03d}",
            twin_type="CleaningRobot",
            name=f"UV Disinfection Robot {i}",
            properties={
                "manufacturer": "Xenex",
                "uvPower": 25,
                "uvPowerUnit": "W",
                "cycleTime": 10,
                "cycleTimeUnit": "minutes"
            }
        )
        twins_created += 1
        # Cross-domain: Cleaning robots service ORs
        add_relationship_safe(client, f"cleaning-robot-{i:03d}", "services", f"or-room-{i:02d}")
        rels_created += 1

    # Pharmacy Automation
    create_domain_twin(client, "robotics",
        twin_id="pharmacy-robot-001",
        twin_type="PharmacyRobot",
        name="Pharmacy Dispensing Robot",
        properties={
            "manufacturer": "Omnicell",
            "capacity": 1000,
            "dispensesPerHour": 200,
            "accuracy": 99.99
        }
    )
    twins_created += 1
    add_relationship_safe(client, "pharmacy-robot-001", "locatedIn", "pharmacy-central")
    rels_created += 1

    # =========================================================================
    # SUPPLY CHAIN DOMAIN - Medical Supplies
    # =========================================================================
    print("[4/5] Creating Supply Chain domain twins...")

    # Medical Supply Warehouse
    create_domain_twin(client, "supply_chain",
        twin_id="medical-supply-warehouse",
        twin_type="Warehouse",
        name="Hospital Medical Supply Warehouse",
        properties={
            "area": 5000,
            "areaUnit": "sqm",
            "palletPositions": 2000,
            "temperatureZones": ["ambient", "refrigerated", "frozen"]
        }
    )
    twins_created += 1
    add_relationship_safe(client, "smart-hospital-central", "hasWarehouse", "medical-supply-warehouse")
    rels_created += 1

    # Cold Chain Storage
    create_domain_twin(client, "supply_chain",
        twin_id="cold-storage-vaccines",
        twin_type="ColdStorage",
        name="Vaccine Cold Storage Facility",
        properties={
            "temperature": -25,
            "tempUnit": "celsius",
            "capacity": 10000,
            "capacityUnit": "doses",
            "backup": "dual-redundant"
        }
    )
    twins_created += 1
    add_relationship_safe(client, "medical-supply-warehouse", "contains", "cold-storage-vaccines")
    rels_created += 1
    # Cross-domain: Cold storage stores healthcare vaccines
    add_relationship_safe(client, "cold-storage-vaccines", "stores", "vaccine-batch-flu-2024")
    rels_created += 1

    # Pharmaceutical Shipment
    create_domain_twin(client, "supply_chain",
        twin_id="pharma-shipment-001",
        twin_type="Shipment",
        name="Emergency Medication Shipment",
        properties={
            "origin": "Pharma Distribution Center",
            "destination": "Central Smart Hospital",
            "contents": ["antibiotics", "analgesics", "anesthetics"],
            "priority": "high",
            "status": "in_transit",
            "eta": "2024-12-16T14:00:00Z"
        }
    )
    twins_created += 1
    add_relationship_safe(client, "pharma-shipment-001", "destination", "pharmacy-central")
    rels_created += 1

    # =========================================================================
    # ENERGY GRID DOMAIN - Hospital Power Systems
    # =========================================================================
    print("[5/5] Creating Energy Grid domain twins...")

    # Main Power Substation
    create_domain_twin(client, "energy_grid",
        twin_id="hospital-substation",
        twin_type="DistributionSubstation",
        name="Hospital Distribution Substation",
        properties={
            "capacity": 10,
            "capacityUnit": "MW",
            "voltage": 11,
            "voltageUnit": "kV",
            "redundancy": "N+1"
        }
    )
    twins_created += 1

    # Backup Generators
    for i in range(1, 4):
        create_domain_twin(client, "energy_grid",
            twin_id=f"generator-backup-{i:02d}",
            twin_type="BackupGenerator",
            name=f"Backup Generator {i}",
            properties={
                "fuelType": "diesel",
                "capacity": 2000,
                "capacityUnit": "kW",
                "startupTime": 10,
                "startupTimeUnit": "seconds",
                "fuelCapacity": 2000,
                "fuelCapacityUnit": "liters"
            }
        )
        twins_created += 1
        add_relationship_safe(client, f"generator-backup-{i:02d}", "backsUp", "hospital-substation")
        rels_created += 1

    # Solar Installation
    create_domain_twin(client, "energy_grid",
        twin_id="solar-rooftop",
        twin_type="SolarFarm",
        name="Hospital Rooftop Solar Installation",
        properties={
            "panelCount": 500,
            "capacity": 250,
            "capacityUnit": "kW",
            "annualGeneration": 350,
            "annualGenerationUnit": "MWh"
        }
    )
    twins_created += 1

    # Cross-domain: Power infrastructure powers building
    add_relationship_safe(client, "hospital-substation", "powers", "hospital-building-main")
    rels_created += 1
    add_relationship_safe(client, "solar-rooftop", "feedsInto", "hospital-substation")
    rels_created += 1

    # Battery Storage
    create_domain_twin(client, "energy_grid",
        twin_id="battery-storage-001",
        twin_type="BatteryStorage",
        name="Hospital Battery Storage System",
        properties={
            "capacity": 1000,
            "capacityUnit": "kWh",
            "stateOfCharge": 85,
            "manufacturer": "Tesla",
            "cycleCount": 250
        }
    )
    twins_created += 1
    add_relationship_safe(client, "battery-storage-001", "connectedTo", "hospital-substation")
    rels_created += 1

    # =========================================================================
    # Cross-Domain Relationships Summary
    # =========================================================================
    # Hospital --> Building
    add_relationship_safe(client, "smart-hospital-central", "occupies", "hospital-building-main")
    rels_created += 1

    print("\n" + "=" * 70)
    print(" Cross-Domain Scenario Seeding Complete!")
    print("=" * 70)
    print(f" Total twins created:        {twins_created}")
    print(f" Total relationships created: {rels_created}")
    print("=" * 70)

    # Print domain summary
    print("\n Domain Distribution:")
    print("-" * 40)
    domains_count = {
        "healthcare": 0,
        "smart_building": 0,
        "robotics": 0,
        "supply_chain": 0,
        "energy_grid": 0
    }

    # Count twins by domain
    twins = client.twins.list(page_size=1000)
    for twin in twins:
        if twin.domain:
            if twin.domain in domains_count:
                domains_count[twin.domain] += 1

    for domain, count in domains_count.items():
        if count > 0:
            print(f"   {domain:20}: {count:4} twins")

    print("\n Cross-Domain Relationship Examples:")
    print("-" * 40)
    print("   HVAC (smart_building) --> maintains --> Operating Room (healthcare)")
    print("   Delivery Robot (robotics) --> deliversTo --> Pharmacy (healthcare)")
    print("   Cold Storage (supply_chain) --> stores --> Vaccine (healthcare)")
    print("   Substation (energy_grid) --> powers --> Building (smart_building)")
    print("   Solar (energy_grid) --> feedsInto --> Substation (energy_grid)")
    print("-" * 40)

    return {
        "twins_created": twins_created,
        "relationships_created": rels_created
    }


if __name__ == "__main__":
    seed_cross_domain_scenario()
