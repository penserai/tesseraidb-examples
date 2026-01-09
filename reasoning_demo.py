#!/usr/bin/env python3
"""
Comprehensive Reasoning Demo for DTaaS
=======================================

This script demonstrates the OWL 2 RL reasoning capabilities in DTaaS:

1. Basic materialization (subclass/subproperty inference)
2. Inverse property reasoning
3. Custom threshold-based rules
4. SWRL-style rules
5. Inference explanation
6. Consistency checking
7. Rule execution and profiles

Prerequisites:
- DTaaS service running at http://localhost:8080
- Ontologies loaded via load_ontologies.py
- Example data seeded via seed_all.py

Usage:
    python reasoning_demo.py [--base-url URL] [--section SECTION]
"""

import os
import sys
import argparse
import json

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdks', 'python'))

from dtaas import DTaaSClient
from dtaas.exceptions import DTaaSError, NotFoundError

from common import (
    DEFAULT_BASE_URL, DEFAULT_USERNAME, DEFAULT_PASSWORD, login,
    NAMESPACE_PREFIXES
)

# Configuration
BASE_URL = os.environ.get("DTAAS_URL", DEFAULT_BASE_URL)


def create_client() -> DTaaSClient:
    """Create a DTaaS SDK client with authentication."""
    username = os.environ.get("DTAAS_USERNAME", DEFAULT_USERNAME)
    password = os.environ.get("DTAAS_PASSWORD", DEFAULT_PASSWORD)
    token = login(BASE_URL, username, password)
    return DTaaSClient(base_url=BASE_URL, token=token, timeout=60.0)


def print_section(num: int, title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f" SECTION {num}: {title}")
    print("=" * 70)


def print_subsection(title: str):
    """Print a subsection header."""
    print(f"\n--- {title} ---")


def print_json(data, indent: int = 2):
    """Pretty print JSON data or Pydantic models."""
    if hasattr(data, 'model_dump'):
        data = data.model_dump()
    print(json.dumps(data, indent=indent, default=str))


def get_sample_twin_id(client: DTaaSClient, domain: str = "automotive") -> str | None:
    """Get a sample twin ID from the specified domain."""
    try:
        twins = client.twins.list()
        # Try to find a twin from the specified domain
        for twin in twins:
            twin_type = (twin.type_uri or "").lower()
            if domain.lower() in twin_type or any(d in twin_type for d in ["vehicle", "fleet", "engine"]):
                return twin.id
        # Return first twin if no domain match
        if twins:
            return twins[0].id
    except DTaaSError as e:
        print(f"Error listing twins: {e}")
    return None


# =============================================================================
# SECTION 1: Basic Materialization
# =============================================================================

def demo_basic_materialization():
    """Demonstrate basic OWL 2 RL materialization."""
    print_section(1, "Basic OWL 2 RL Materialization")

    print("""
OWL 2 RL reasoning performs inference based on ontology axioms:
- rdfs:subClassOf: If X is type A and A subClassOf B, then X is type B
- rdfs:subPropertyOf: If P subPropertyOf Q, then P facts imply Q facts
- rdfs:domain/range: Using property implies subject/object types

The class hierarchy in the automotive domain:
  auto:FleetVehicle -> auto:Vehicle -> dtaas:Asset -> dtaas:DigitalTwin

So a FleetVehicle is automatically inferred to be a Vehicle, Asset, and DigitalTwin.
""")

    client = create_client()

    # Check current reasoning stats
    print_subsection("Current Reasoning Statistics")
    try:
        stats = client.reasoning.get_stats()
        print_json(stats)
    except DTaaSError as e:
        print(f"Stats error: {e}")

    # Find a twin to reason over
    print_subsection("Finding a Sample Twin")
    twin_id = get_sample_twin_id(client, "automotive")
    if twin_id:
        print(f"Selected twin: {twin_id}")

        # Materialize inferences
        print_subsection("Materializing Inferences for Twin")
        try:
            result = client.reasoning.materialize(twin_id)
            print(f"Inferred triples: {result.inferred_triples}")
            print(f"Duration: {result.duration_ms}ms")
            if result.rules_applied:
                print(f"Rules applied: {result.rules_applied}")
        except DTaaSError as e:
            print(f"Materialization error: {e}")
    else:
        print("No twins found - please run seed_all.py first")

    # Explain what kinds of inferences are possible
    print_subsection("Types of Inferences")
    print("""
Based on the loaded ontologies, the following inferences are performed:

1. Type Propagation (rdfs:subClassOf):
   - FleetVehicle -> Vehicle -> Asset -> DigitalTwin
   - ElectricVehicle -> Vehicle -> Asset -> DigitalTwin
   - Engine -> Component -> DigitalTwin

2. Property Inheritance (rdfs:subPropertyOf):
   - auto:hasEngine rdfs:subPropertyOf dtaas:hasComponent
   - bldg:hasFloor rdfs:subPropertyOf dtaas:hasComponent

3. Inverse Property Inference (owl:inverseOf):
   - dtaas:hasComponent owl:inverseOf dtaas:isComponentOf
   - auto:belongsToFleet owl:inverseOf auto:hasVehicle
""")


# =============================================================================
# SECTION 2: Custom Rules
# =============================================================================

def demo_custom_rules():
    """Demonstrate custom threshold-based rules."""
    print_section(2, "Custom Threshold-Based Rules")

    print("""
Custom rules extend OWL reasoning with domain-specific logic:
- Classify entities based on property value thresholds
- Apply business rules that can't be expressed in pure OWL

Examples:
- If batteryLevel < 20% -> classify as LowBatteryVehicle
- If mileage > 100000 -> classify as HighMileageVehicle
- If co2Level > 1000ppm -> classify as PoorAirQualityZone
""")

    client = create_client()

    # List available rule templates
    print_subsection("Available Rule Templates")
    try:
        templates = client.reasoning.list_templates()
        for tmpl in templates[:5]:
            print(f"  - {tmpl.id}")
            if tmpl.description:
                print(f"    {tmpl.description[:60]}")
    except DTaaSError as e:
        print(f"Templates error: {e}")

    # Create a custom rule
    print_subsection("Creating Custom Rule: Low Battery Alert")
    low_battery_rule = {
        "id": "low-battery-alert",
        "name": "Low Battery Vehicle Classification",
        "description": "Classify EVs with battery below 20% as needing charge",
        "priority": 10,
        "rule": {
            "type": "threshold",
            "property": "http://tesserai.io/ontology/automotive#batteryLevel",
            "operator": "<",
            "value": 20.0,
            "target_class": "http://tesserai.io/ontology/automotive#LowBatteryVehicle"
        }
    }
    try:
        rule = client.reasoning.create_rule(low_battery_rule)
        print(f"Created rule: {rule.name}")
        print("  Condition: batteryLevel < 20%")
        print("  Action: Classify as LowBatteryVehicle")
    except DTaaSError as e:
        print(f"Rule creation: {e}")

    # Create another rule
    print_subsection("Creating Custom Rule: High Mileage Alert")
    high_mileage_rule = {
        "id": "high-mileage-alert",
        "name": "High Mileage Vehicle Classification",
        "description": "Classify vehicles with mileage > 100000 km",
        "priority": 10,
        "rule": {
            "type": "threshold",
            "property": "http://tesserai.io/ontology/automotive#mileage",
            "operator": ">",
            "value": 100000.0,
            "target_class": "http://tesserai.io/ontology/automotive#HighMileageVehicle"
        }
    }
    try:
        rule = client.reasoning.create_rule(high_mileage_rule)
        print(f"Created rule: {rule.name}")
    except DTaaSError as e:
        print(f"Rule creation: {e}")

    # List all custom rules
    print_subsection("All Custom Rules")
    try:
        rules = client.reasoning.list_rules()
        print(f"Total rules: {len(rules)}")
        for rule in rules[:10]:
            status = "enabled" if rule.enabled else "disabled"
            print(f"  [{status}] {rule.id}: {rule.name}")
    except DTaaSError as e:
        print(f"List rules error: {e}")


# =============================================================================
# SECTION 3: SWRL Rules
# =============================================================================

def demo_swrl_rules():
    """Demonstrate SWRL-style rule creation."""
    print_section(3, "SWRL-Style Rules")

    print("""
SWRL (Semantic Web Rule Language) extends OWL with IF-THEN rules:
- Body: conditions that must all match (conjunction)
- Head: conclusions to infer when body matches

Example SWRL Rule (in readable form):
  IF: System(?sys) AND hasComponent(?sys, ?comp) AND status(?comp, "critical")
  THEN: MaintenanceRequired(?sys)

This means: Any system with a component in critical status needs maintenance.
""")

    client = create_client()

    # List SWRL rules
    print_subsection("Existing SWRL Rules")
    try:
        swrl_rules = client.reasoning.list_swrl_rules()
        if swrl_rules:
            for rule in swrl_rules[:5]:
                print(f"  - {rule.id}: {rule.name}")
        else:
            print("  No SWRL rules defined yet")
    except DTaaSError as e:
        print(f"SWRL rules error: {e}")

    # Create an SWRL rule
    print_subsection("Creating SWRL Rule: Component Failure Propagation")
    swrl_rule = {
        "id": "component-failure-propagation",
        "name": "Component Failure Propagation",
        "description": "If any component has critical status, parent needs maintenance",
        "body": [
            {"type": "class", "class": "http://tesserai.io/ontology/core#System", "variable": "?system"},
            {"type": "property", "property": "http://tesserai.io/ontology/core#hasComponent",
             "subject": "?system", "object": "?component"},
            {"type": "property", "property": "http://tesserai.io/ontology/core#status",
             "subject": "?component", "object": "\"critical\""}
        ],
        "head": [
            {"type": "class", "class": "http://tesserai.io/ontology/core#MaintenanceRequired",
             "variable": "?system"}
        ],
        "enabled": True
    }
    try:
        rule = client.reasoning.create_swrl_rule(swrl_rule)
        print("Created SWRL rule!")
        print("  Body:")
        print("    - System(?sys)")
        print("    - hasComponent(?sys, ?comp)")
        print("    - status(?comp, 'critical')")
        print("  Head:")
        print("    - MaintenanceRequired(?sys)")
    except DTaaSError as e:
        print(f"SWRL rule creation: {e}")


# =============================================================================
# SECTION 4: Inference Explanation
# =============================================================================

def demo_explanation_api():
    """Demonstrate inference explanation capabilities."""
    print_section(4, "Inference Explanation API")

    print("""
The Explanation API shows WHY an inference was made:
- What rules/axioms were applied
- What source facts were used
- The derivation chain from asserted to inferred facts

This is essential for:
- Debugging reasoning problems
- Compliance and audit trails
- Understanding complex inference chains
""")

    client = create_client()

    # Find a twin to explain
    print_subsection("Finding an Entity to Explain")
    twin_id = get_sample_twin_id(client, "automotive")

    if twin_id:
        print(f"Selected twin: {twin_id}")

        # Get twin details
        try:
            twin = client.twins.get(twin_id)
            print(f"  Type: {twin.type_uri or 'unknown'}")
            print(f"  Name: {twin.name or 'unnamed'}")
        except DTaaSError:
            pass

        # Explain entity inferences
        print_subsection("Explaining Entity Inferences")
        entity_uri = f"http://tesserai.io/twins/{twin_id}"
        try:
            explanation = client.reasoning.explain_entity(twin_id, entity_uri)
            print(f"Entity: {explanation.entity}")
            print(f"Asserted types: {len(explanation.asserted_types)}")
            for t in explanation.asserted_types[:3]:
                print(f"  - {t}")
            print(f"Inferred types: {len(explanation.inferred_types)}")
            for it in explanation.inferred_types[:5]:
                print(f"  - {it.type_uri}")
                if it.reason:
                    print(f"    Reason: {it.reason[:60]}")
        except DTaaSError as e:
            print(f"Explanation error: {e}")
    else:
        print("No twins found - please run seed_all.py first")

    print_subsection("How Explanation Works")
    print("""
For a FleetVehicle twin, the explanation might show:

1. Asserted: twin rdf:type auto:FleetVehicle
2. Inferred: twin rdf:type auto:Vehicle
   Reason: FleetVehicle rdfs:subClassOf Vehicle
3. Inferred: twin rdf:type dtaas:Asset
   Reason: Vehicle rdfs:subClassOf Asset
4. Inferred: twin rdf:type dtaas:DigitalTwin
   Reason: Asset rdfs:subClassOf DigitalTwin
""")


# =============================================================================
# SECTION 5: Consistency Checking
# =============================================================================

def demo_consistency_checking():
    """Demonstrate ontology consistency checking."""
    print_section(5, "Consistency Checking")

    print("""
OWL 2 RL supports consistency checking to detect logical contradictions:

- Disjoint class violations: Entity cannot be both A and B if owl:disjointWith
- Property restrictions: Cardinality, domain/range violations
- Same/Different individual conflicts

Example disjoint classes:
- auto:PrivateVehicle owl:disjointWith auto:FleetVehicle
  (A vehicle can't be both private and fleet)
- dtaas:HeatingEquipment owl:disjointWith dtaas:CoolingEquipment
  (Equipment is either heating or cooling)
""")

    client = create_client()
    twin_id = get_sample_twin_id(client, "automotive")

    # Check consistency
    print_subsection("Running Consistency Check")
    try:
        if twin_id:
            result = client.reasoning.check_consistency(twin_id)
        else:
            result = client.reasoning.check_consistency_by_domain("automotive")

        print(f"Knowledge base is consistent: {result.is_consistent}")

        if result.violations:
            print(f"\nViolations found ({len(result.violations)}):")
            for v in result.violations[:5]:
                print(f"  - {v.get('type', 'unknown')}: {v.get('message', 'No message')}")
        else:
            print("No violations detected.")
    except DTaaSError as e:
        print(f"Consistency check error: {e}")

    print_subsection("What Would Cause Inconsistency")
    print("""
Creating a twin like this would cause inconsistency:

{
  "id": "confused-vehicle",
  "types": [
    "http://tesserai.io/ontology/automotive#FleetVehicle",
    "http://tesserai.io/ontology/automotive#PrivateVehicle"
  ]
}

Since FleetVehicle and PrivateVehicle are disjoint, having both types
is a logical contradiction.
""")


# =============================================================================
# SECTION 6: Rule Conflicts
# =============================================================================

def demo_conflict_detection():
    """Demonstrate rule conflict detection."""
    print_section(6, "Rule Conflict Detection")

    print("""
The system can analyze rules for potential conflicts:
- Contradictory classifications (mutually exclusive outcomes)
- Overlapping conditions with different results
- Circular dependencies between rules
""")

    client = create_client()

    # Analyze rule conflicts
    print_subsection("Analyzing Rule Conflicts")
    try:
        conflicts = client.reasoning.check_conflicts()

        if conflicts:
            print(f"Found {len(conflicts)} potential conflicts:")
            for c in conflicts[:5]:
                print(f"\n  Conflict between:")
                print(f"    Rule 1: {c.rule1_id}")
                print(f"    Rule 2: {c.rule2_id}")
                print(f"    Type: {c.conflict_type}")
        else:
            print("No rule conflicts detected.")
    except DTaaSError as e:
        print(f"Conflict analysis error: {e}")

    print_subsection("Types of Conflicts Detected")
    print("""
1. Disjoint Target Classes:
   - Rule A: temperature > 30 -> OverheatedZone
   - Rule B: temperature < 15 -> OvercooledZone
   These are fine (mutually exclusive conditions)

2. Overlapping Conditions, Disjoint Outcomes:
   - Rule A: speed > 100 -> SpeedingVehicle
   - Rule A: speed > 100 -> SafeVehicle
   These conflict! (same condition, contradictory classes)

3. Circular Dependencies:
   - Rule A: HighRisk(?x) -> NeedsReview(?x)
   - Rule B: NeedsReview(?x) -> HighRisk(?x)
   This creates an infinite loop!
""")


# =============================================================================
# SECTION 7: Reasoning Profiles & Batch Processing
# =============================================================================

def demo_batch_reasoning():
    """Demonstrate batch reasoning and profiles."""
    print_section(7, "Reasoning Profiles & Batch Processing")

    print("""
Reasoning profiles allow different levels of inference:
- Light: Basic type propagation only
- Standard: Full OWL 2 RL without custom rules
- Full: All OWL 2 RL plus custom rules
- Custom: Only user-defined rules

Batch reasoning processes multiple twins efficiently.
""")

    client = create_client()

    # Get reasoning profiles
    print_subsection("Available Reasoning Profiles")
    try:
        profiles = client.reasoning.get_profiles()
        for p in profiles:
            print(f"\n  {p.name}:")
            if p.description:
                print(f"    {p.description}")
            if p.rules_count is not None:
                print(f"    Rules: {p.rules_count}")
    except DTaaSError as e:
        print(f"Profiles error: {e}")

    # Execute batch reasoning
    print_subsection("Executing Batch Reasoning")
    try:
        result = client.reasoning.execute_batch({
            "domains": ["automotive", "smart_building"],
            "profile": "standard"
        })
        print("Batch reasoning completed:")
        print(f"  Total inferred: {result.total_inferred} triples")
        print(f"  Duration: {result.duration_ms}ms")
        print(f"  Domains processed: {result.domains}")

        if result.metrics:
            print("  Per-domain:")
            for domain, m in result.metrics.items():
                print(f"    {domain}: {m.get('inferred', 0)} inferred")
    except DTaaSError as e:
        print(f"Batch reasoning error: {e}")

    # Execute specific rules
    print_subsection("Executing Specific Rules")
    try:
        result = client.reasoning.execute_rules_by_domain(
            "automotive",
            rule_ids=["low-battery-alert", "high-mileage-alert"]
        )
        print("Custom rules executed:")
        print(f"  Rules: {result.rules_executed}")
        print(f"  Inferred: {result.inferred_triples} triples")
        print(f"  Iterations: {result.iterations}")
    except DTaaSError as e:
        print(f"Rule execution error: {e}")

    # Final statistics
    print_subsection("Final Reasoning Statistics")
    try:
        stats = client.reasoning.get_stats()
        print_json(stats)
    except DTaaSError as e:
        print(f"Stats error: {e}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    global BASE_URL
    parser = argparse.ArgumentParser(description="DTaaS Reasoning Demo")
    parser.add_argument("--base-url", default=None, help="DTaaS service URL")
    parser.add_argument("--section", type=int, help="Run specific section (1-7)")
    args = parser.parse_args()

    if args.base_url:
        BASE_URL = args.base_url

    print("""
+===========================================================================+
|                    DTaaS Reasoning Capabilities Demo                      |
|                                                                           |
|  Demonstrating OWL 2 RL Semantic Reasoning for Digital Twins              |
|  Using the DTaaS Python SDK                                               |
+===========================================================================+
""")

    sections = {
        1: demo_basic_materialization,
        2: demo_custom_rules,
        3: demo_swrl_rules,
        4: demo_explanation_api,
        5: demo_consistency_checking,
        6: demo_conflict_detection,
        7: demo_batch_reasoning,
    }

    if args.section:
        if args.section in sections:
            sections[args.section]()
        else:
            print(f"Invalid section {args.section}. Choose 1-7.")
            sys.exit(1)
    else:
        for num, func in sections.items():
            try:
                func()
            except Exception as e:
                print(f"\n[ERROR in Section {num}]: {e}")
                continue

    print("\n" + "=" * 70)
    print(" Demo Complete!")
    print("=" * 70)
    print("""
Resources:
- Swagger UI: http://localhost:8080/swagger-ui/
- OWL 2 RL Spec: https://www.w3.org/TR/owl2-profiles/#OWL_2_RL
- SWRL Spec: https://www.w3.org/submissions/SWRL/

Run specific sections:
  python reasoning_demo.py --section 1  # Basic materialization
  python reasoning_demo.py --section 2  # Custom rules
  python reasoning_demo.py --section 3  # SWRL rules
  python reasoning_demo.py --section 4  # Explanation API
  python reasoning_demo.py --section 5  # Consistency checking
  python reasoning_demo.py --section 6  # Conflict detection
  python reasoning_demo.py --section 7  # Batch reasoning
""")


if __name__ == "__main__":
    main()
