#!/usr/bin/env python3
"""
Domain-Specific SWRL Rules for DTaaS
====================================

This script creates SWRL-style rules for each domain, demonstrating
how business rules can be encoded and executed via the reasoning API.

Uses the DTaaS Python SDK for all API interactions.

Usage:
    python domain_rules.py [--base-url URL] [--domain DOMAIN] [--list]
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdks', 'python'))

from dtaas import DTaaSClient
from dtaas.exceptions import DTaaSError

from common import DEFAULT_BASE_URL, get_api_key

BASE_URL = os.environ.get("TESSERAI_API_URL", DEFAULT_BASE_URL)


def create_client() -> DTaaSClient:
    """Create a TesseraiDB SDK client with authentication."""
    token = get_api_key()
    if not token:
        print("Error: No API key provided. Set TESSERAI_API_KEY environment variable.")
        print("Get your API key from https://tesserai.io")
        sys.exit(1)
    return DTaaSClient(base_url=BASE_URL, token=token, timeout=60.0)


# =============================================================================
# Domain-Specific Rule Definitions
# =============================================================================

DOMAIN_RULES = {
    "automotive": [
        {
            "id": "auto-low-battery",
            "name": "Low Battery Vehicle Alert",
            "description": "Flag electric vehicles with battery < 20% as low battery",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/automotive#batteryLevel",
                "operator": "<",
                "value": 20.0,
                "target_class": "http://tesserai.io/ontology/automotive#LowBatteryVehicle"
            }
        },
        {
            "id": "auto-high-mileage",
            "name": "High Mileage Vehicle Alert",
            "description": "Flag vehicles with mileage > 100,000 km",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/automotive#mileage",
                "operator": ">",
                "value": 100000.0,
                "target_class": "http://tesserai.io/ontology/automotive#HighMileageVehicle"
            }
        },
        {
            "id": "auto-low-fuel",
            "name": "Low Fuel Vehicle Alert",
            "description": "Flag vehicles with fuel < 15%",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/automotive#fuelLevel",
                "operator": "<",
                "value": 15.0,
                "target_class": "http://tesserai.io/ontology/automotive#LowFuelVehicle"
            }
        },
    ],

    "smart_building": [
        {
            "id": "bldg-high-temp",
            "name": "Overheated Zone Alert",
            "description": "Flag zones with temperature > 28C as overheated",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/smart_building#temperature",
                "operator": ">",
                "value": 28.0,
                "target_class": "http://tesserai.io/ontology/smart_building#OverheatedZone"
            }
        },
        {
            "id": "bldg-poor-air",
            "name": "Poor Air Quality Zone Alert",
            "description": "Flag zones with CO2 > 1000 ppm",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/smart_building#co2Level",
                "operator": ">",
                "value": 1000.0,
                "target_class": "http://tesserai.io/ontology/smart_building#PoorAirQualityZone"
            }
        },
        {
            "id": "bldg-high-energy",
            "name": "High Energy Consumer Alert",
            "description": "Flag equipment with energy > 500 kWh",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/smart_building#energyConsumption",
                "operator": ">",
                "value": 500.0,
                "target_class": "http://tesserai.io/ontology/smart_building#HighEnergyConsumer"
            }
        },
    ],

    "energy_grid": [
        {
            "id": "energy-overload",
            "name": "Overloaded Transformer Alert",
            "description": "Flag transformers with load > 90%",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/energy_grid#loadPercentage",
                "operator": ">",
                "value": 90.0,
                "target_class": "http://tesserai.io/ontology/energy_grid#OverloadedTransformer"
            }
        },
        {
            "id": "energy-low-voltage",
            "name": "Low Voltage Alert",
            "description": "Flag nodes with voltage < 95% of nominal",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/energy_grid#voltageRatio",
                "operator": "<",
                "value": 0.95,
                "target_class": "http://tesserai.io/ontology/energy_grid#LowVoltageNode"
            }
        },
    ],

    "healthcare": [
        {
            "id": "health-critical-battery",
            "name": "Critical Device Battery Alert",
            "description": "Flag medical devices with battery < 10%",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/healthcare#batteryLevel",
                "operator": "<",
                "value": 10.0,
                "target_class": "http://tesserai.io/ontology/healthcare#CriticalBatteryDevice"
            }
        },
        {
            "id": "health-cal-overdue",
            "name": "Calibration Overdue Alert",
            "description": "Flag devices past calibration date",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/healthcare#daysSinceCalibration",
                "operator": ">",
                "value": 365.0,
                "target_class": "http://tesserai.io/ontology/healthcare#CalibrationOverdue"
            }
        },
    ],

    "robotics": [
        {
            "id": "robo-error-state",
            "name": "Robot Error State Alert",
            "description": "Flag robots with error count > 5",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/robotics#errorCount",
                "operator": ">",
                "value": 5.0,
                "target_class": "http://tesserai.io/ontology/robotics#RobotInErrorState"
            }
        },
        {
            "id": "robo-low-battery",
            "name": "Robot Low Battery Alert",
            "description": "Flag robots with battery < 25%",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/robotics#batteryLevel",
                "operator": "<",
                "value": 25.0,
                "target_class": "http://tesserai.io/ontology/robotics#LowBatteryRobot"
            }
        },
    ],

    "supply_chain": [
        {
            "id": "supply-low-stock",
            "name": "Low Stock Alert",
            "description": "Flag items with stock < 10",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/supply_chain#stockLevel",
                "operator": "<",
                "value": 10.0,
                "target_class": "http://tesserai.io/ontology/supply_chain#LowStockItem"
            }
        },
        {
            "id": "supply-delayed",
            "name": "Delayed Shipment Alert",
            "description": "Flag shipments delayed > 2 days",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/supply_chain#daysDelayed",
                "operator": ">",
                "value": 2.0,
                "target_class": "http://tesserai.io/ontology/supply_chain#DelayedShipment"
            }
        },
    ],

    "agriculture": [
        {
            "id": "agri-dry-soil",
            "name": "Dry Soil Alert",
            "description": "Flag fields with soil moisture < 20%",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/agriculture#soilMoisture",
                "operator": "<",
                "value": 20.0,
                "target_class": "http://tesserai.io/ontology/agriculture#DrySoilField"
            }
        },
        {
            "id": "agri-low-nutrients",
            "name": "Low Nutrient Alert",
            "description": "Flag fields with nutrient level < 30%",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/agriculture#nutrientLevel",
                "operator": "<",
                "value": 30.0,
                "target_class": "http://tesserai.io/ontology/agriculture#LowNutrientField"
            }
        },
    ],

    "aerospace": [
        {
            "id": "aero-fuel-low",
            "name": "Low Fuel Alert",
            "description": "Flag aircraft with fuel < 20%",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/aerospace#fuelLevel",
                "operator": "<",
                "value": 20.0,
                "target_class": "http://tesserai.io/ontology/aerospace#LowFuelAircraft"
            }
        },
        {
            "id": "aero-maintenance",
            "name": "Maintenance Due Alert",
            "description": "Flag aircraft past maintenance hours",
            "rule": {
                "type": "threshold",
                "property": "http://tesserai.io/ontology/aerospace#hoursSinceMaintenance",
                "operator": ">",
                "value": 500.0,
                "target_class": "http://tesserai.io/ontology/aerospace#MaintenanceDue"
            }
        },
    ],
}


def create_rules(domain: str = None):
    """Create rules for specified domain or all domains."""
    domains_to_process = [domain] if domain else DOMAIN_RULES.keys()

    client = create_client()
    created = 0
    failed = 0

    for dom in domains_to_process:
        if dom not in DOMAIN_RULES:
            print(f"Unknown domain: {dom}")
            continue

        print(f"\n--- {dom.upper()} Domain Rules ---")
        rules = DOMAIN_RULES[dom]

        for rule_def in rules:
            rule_data = {
                "id": rule_def["id"],
                "name": rule_def["name"],
                "description": rule_def["description"],
                "priority": 10,
                "rule": rule_def["rule"]
            }

            try:
                rule = client.reasoning.create_rule(rule_data)
                # Handle both dict and model responses
                rule_id = rule.get("id", rule_def["id"]) if isinstance(rule, dict) else rule.id
                rule_name = rule.get("name", rule_def["name"]) if isinstance(rule, dict) else rule.name
                print(f"  [OK] {rule_id}: {rule_name}")
                created += 1
            except DTaaSError as e:
                print(f"  [FAIL] {rule_def['id']}: {e}")
                failed += 1

    print(f"\n{'='*50}")
    print(f"Summary: {created} created, {failed} failed")


def list_rules():
    """List all rules currently registered."""
    client = create_client()

    try:
        rules = client.reasoning.list_rules()
        print(f"\nRegistered Rules ({len(rules)} total):")
        print("=" * 60)
        for rule in rules:
            # Handle both dict and model responses
            if isinstance(rule, dict):
                enabled = rule.get("enabled", True)
                rule_id = rule.get("id", "unknown")
                rule_name = rule.get("name", "")
                desc = rule.get("description", "") or ""
            else:
                enabled = rule.enabled
                rule_id = rule.id
                rule_name = rule.name
                desc = rule.description or ""
            status = "[enabled]" if enabled else "[disabled]"
            print(f"  {status} {rule_id}")
            print(f"         {rule_name}")
            print(f"         {desc[:50]}")
    except DTaaSError as e:
        print(f"Error listing rules: {e}")


def delete_rules(domain: str = None):
    """Delete rules for specified domain or all."""
    domains_to_process = [domain] if domain else DOMAIN_RULES.keys()

    client = create_client()
    deleted = 0
    failed = 0

    for dom in domains_to_process:
        if dom not in DOMAIN_RULES:
            continue

        print(f"\n--- Deleting {dom.upper()} Domain Rules ---")

        for rule_def in DOMAIN_RULES[dom]:
            rule_id = rule_def["id"]
            try:
                client.reasoning.delete_rule(rule_id)
                print(f"  [DELETED] {rule_id}")
                deleted += 1
            except DTaaSError as e:
                print(f"  [FAIL] {rule_id}: {e}")
                failed += 1

    print(f"\n{'='*50}")
    print(f"Summary: {deleted} deleted, {failed} failed")


def execute_domain_rules(domain: str):
    """Execute all rules for a domain and show results."""
    if domain not in DOMAIN_RULES:
        print(f"Unknown domain: {domain}")
        return

    client = create_client()

    print(f"\n--- Executing {domain.upper()} Domain Rules ---")

    # Get rule IDs for this domain
    rule_ids = [r["id"] for r in DOMAIN_RULES[domain]]

    try:
        result = client.reasoning.execute_rules_by_domain(domain, rule_ids=rule_ids)
        print(f"\nExecution Results:")
        # Handle both dict and model responses
        if isinstance(result, dict):
            print(f"  Rules executed: {result.get('rules_executed', 'N/A')}")
            print(f"  Inferred triples: {result.get('inferred_triples', 'N/A')}")
            print(f"  Duration: {result.get('duration_ms', 'N/A')}ms")
            print(f"  Iterations: {result.get('iterations', 'N/A')}")
        else:
            print(f"  Rules executed: {result.rules_executed}")
            print(f"  Inferred triples: {result.inferred_triples}")
            print(f"  Duration: {result.duration_ms}ms")
            print(f"  Iterations: {result.iterations}")
    except DTaaSError as e:
        print(f"Execution error: {e}")


def main():
    global BASE_URL
    parser = argparse.ArgumentParser(description="Domain-Specific Rules Manager")
    parser.add_argument("--base-url", help="DTaaS service URL")
    parser.add_argument("--domain", help="Specific domain (automotive, smart_building, etc.)")
    parser.add_argument("--list", action="store_true", help="List all rules")
    parser.add_argument("--delete", action="store_true", help="Delete rules")
    parser.add_argument("--execute", action="store_true", help="Execute rules for domain")
    args = parser.parse_args()

    if args.base_url:
        BASE_URL = args.base_url

    print("""
+=============================================================+
|          Domain-Specific SWRL Rules for DTaaS               |
|          Using the DTaaS Python SDK                         |
+=============================================================+
""")

    if args.list:
        list_rules()
    elif args.delete:
        delete_rules(args.domain)
    elif args.execute:
        if not args.domain:
            print("Error: --domain required with --execute")
            sys.exit(1)
        execute_domain_rules(args.domain)
    else:
        create_rules(args.domain)

    print(f"\nAvailable domains: {', '.join(DOMAIN_RULES.keys())}")


if __name__ == "__main__":
    main()
