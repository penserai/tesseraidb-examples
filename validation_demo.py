#!/usr/bin/env python3
"""
Demonstration of SHACL validation in DTaaS.

This script demonstrates how to:
1. Load ontologies with SHACL shapes
2. Create twins with validation
3. Handle validation errors

Usage:
    python validation_demo.py
"""

import os
import sys
import json
import httpx

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdks', 'python'))

from common import logger, DEFAULT_BASE_URL, DEFAULT_USERNAME, DEFAULT_PASSWORD, login

# Example data - Valid vehicle
VALID_VEHICLE_TURTLE = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix auto: <http://tesserai.io/ontology/automotive#> .
@prefix dtaas: <http://tesserai.io/ontology/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/vehicle/truck-001>
    rdf:type auto:FleetVehicle ;
    dtaas:name "Truck 001" ;
    auto:vin "1HGBH41JXMN109186"^^xsd:string ;
    auto:make "Ford"^^xsd:string ;
    auto:model "F-150"^^xsd:string ;
    auto:year "2023"^^xsd:integer ;
    auto:mileage "15000.5"^^xsd:decimal ;
    auto:fuelLevel "75.0"^^xsd:decimal .
"""

# Example data - Invalid vehicle (year out of range, invalid VIN)
INVALID_VEHICLE_TURTLE = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix auto: <http://tesserai.io/ontology/automotive#> .
@prefix dtaas: <http://tesserai.io/ontology/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/vehicle/bad-vehicle>
    rdf:type auto:FleetVehicle ;
    dtaas:name "Bad Vehicle" ;
    auto:vin "INVALID_VIN"^^xsd:string ;
    auto:year "1800"^^xsd:integer ;
    auto:fuelLevel "150.0"^^xsd:decimal .
"""

# Example data - Valid robot
VALID_ROBOT_TURTLE = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix robo: <http://tesserai.io/ontology/robotics#> .
@prefix dtaas: <http://tesserai.io/ontology/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/robot/amr-001>
    rdf:type robo:AMR ;
    dtaas:name "AMR Unit 001" ;
    robo:serialNumber "SN-AMR-2026-001"^^xsd:string ;
    robo:manufacturer "Boston Dynamics"^^xsd:string ;
    robo:payload "50.0"^^xsd:decimal ;
    robo:operationalStatus "idle"^^xsd:string ;
    robo:batteryLevel "85.0"^^xsd:decimal ;
    robo:maxSpeed "2.5"^^xsd:decimal .
"""

# Example data - Invalid robot (invalid operational status)
INVALID_ROBOT_TURTLE = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix robo: <http://tesserai.io/ontology/robotics#> .
@prefix dtaas: <http://tesserai.io/ontology/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://example.org/robot/bad-robot>
    rdf:type robo:AMR ;
    dtaas:name "Bad Robot" ;
    robo:operationalStatus "flying"^^xsd:string ;
    robo:batteryLevel "200.0"^^xsd:decimal .
"""


class SimpleClient:
    """Simple HTTP client for demo purposes."""
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.http = httpx.Client()

    def close(self):
        self.http.close()


def create_twin_with_validation(client: SimpleClient, twin_id: str, rdf_data: str, schema: str):
    """Create a twin with SHACL validation."""
    try:
        response = client.http.post(
            f"{client.base_url}/twins/{twin_id}?schema={schema}",
            content=rdf_data,
            headers={
                "Content-Type": "text/turtle",
                "Authorization": f"Bearer {client.token}"
            }
        )

        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            result = response.json() if 'application/json' in content_type else {"message": response.text}
            return True, result
        elif response.status_code == 422:
            # Validation failed
            return False, response.json()
        else:
            return False, {"error": f"HTTP {response.status_code}: {response.text}"}

    except Exception as e:
        return False, {"error": str(e)}


def validate_existing_twin(client: SimpleClient, twin_id: str, schema: str):
    """Validate an existing twin against a schema."""
    try:
        response = client.http.post(
            f"{client.base_url}/twins/{twin_id}/validate?schema={schema}",
            headers={"Authorization": f"Bearer {client.token}"}
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}: {response.text}"}

    except Exception as e:
        return {"error": str(e)}


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 70}")
    print(f" {title}")
    print('=' * 70)


def print_result(success: bool, result: dict):
    """Print the result of an operation."""
    if success:
        print("  Status: SUCCESS")
        if "validation_report" in result:
            report = result["validation_report"]
            print(f"  Validated: {report.get('conforms', True)}")
    else:
        print("  Status: FAILED (Validation Error)")
        errors = result.get("errors", [])
        if errors:
            print(f"  Errors ({len(errors)}):")
            for error in errors[:5]:  # Show first 5 errors
                print(f"    - {error.get('message', 'Unknown error')}")
                if error.get('focus_node'):
                    print(f"      Focus: {error['focus_node']}")
                if error.get('path'):
                    print(f"      Path: {error['path']}")
        if len(errors) > 5:
            print(f"    ... and {len(errors) - 5} more errors")


def cleanup_twin(client: SimpleClient, twin_id: str):
    """Delete a twin (cleanup)."""
    try:
        client.http.delete(
            f"{client.base_url}/twins/{twin_id}",
            headers={"Authorization": f"Bearer {client.token}"}
        )
    except:
        pass


def main():
    base_url = os.environ.get("DTAAS_URL", DEFAULT_BASE_URL)
    username = os.environ.get("DTAAS_USERNAME", DEFAULT_USERNAME)
    password = os.environ.get("DTAAS_PASSWORD", DEFAULT_PASSWORD)
    logger.info(f"Logging in as {username}")
    token = login(base_url, username, password)
    client = SimpleClient(base_url, token)

    print_section("DTaaS SHACL Validation Demo")
    print("\nThis demo shows how SHACL validation works when creating twins.")
    print("Ontologies must be loaded first. Run: python load_ontologies.py")

    # Demo 1: Valid vehicle
    print_section("Demo 1: Creating Valid Vehicle (with automotive schema)")
    success, result = create_twin_with_validation(
        client, "demo-vehicle-valid", VALID_VEHICLE_TURTLE, "automotive"
    )
    print_result(success, result)
    if success:
        cleanup_twin(client, "demo-vehicle-valid")

    # Demo 2: Invalid vehicle
    print_section("Demo 2: Creating Invalid Vehicle (validation should fail)")
    print("  Violations: Invalid VIN format, year out of range, fuel level > 100%")
    success, result = create_twin_with_validation(
        client, "demo-vehicle-invalid", INVALID_VEHICLE_TURTLE, "automotive"
    )
    print_result(success, result)
    if success:
        cleanup_twin(client, "demo-vehicle-invalid")

    # Demo 3: Valid robot
    print_section("Demo 3: Creating Valid AMR Robot (with robotics schema)")
    success, result = create_twin_with_validation(
        client, "demo-robot-valid", VALID_ROBOT_TURTLE, "robotics"
    )
    print_result(success, result)
    if success:
        cleanup_twin(client, "demo-robot-valid")

    # Demo 4: Invalid robot
    print_section("Demo 4: Creating Invalid Robot (validation should fail)")
    print("  Violations: Invalid operational status, battery level > 100%")
    success, result = create_twin_with_validation(
        client, "demo-robot-invalid", INVALID_ROBOT_TURTLE, "robotics"
    )
    print_result(success, result)
    if success:
        cleanup_twin(client, "demo-robot-invalid")

    # Demo 5: Create without validation
    print_section("Demo 5: Creating Twin Without Validation")
    print("  When no schema is specified, data is inserted without validation.")
    try:
        response = client.http.post(
            f"{client.base_url}/twins/demo-no-validation",
            content=INVALID_VEHICLE_TURTLE,
            headers={
                "Content-Type": "text/turtle",
                "Authorization": f"Bearer {client.token}"
            }
        )
        if response.status_code == 200:
            print("  Status: SUCCESS (no validation performed)")
            cleanup_twin(client, "demo-no-validation")
        else:
            print(f"  Status: FAILED - {response.status_code}")
    except Exception as e:
        print(f"  Error: {e}")

    # Demo 6: Post-hoc validation
    print_section("Demo 6: Post-hoc Validation of Existing Twin")
    print("  Creating unvalidated twin, then validating it...")
    try:
        # Create without validation
        response = client.http.post(
            f"{client.base_url}/twins/demo-posthoc",
            content=INVALID_VEHICLE_TURTLE,
            headers={
                "Content-Type": "text/turtle",
                "Authorization": f"Bearer {client.token}"
            }
        )
        if response.status_code == 200:
            print("  Created twin without validation")

            # Now validate it
            validation = validate_existing_twin(client, "demo-posthoc", "automotive")
            print(f"  Post-hoc validation result: conforms={validation.get('conforms', 'unknown')}")
            if not validation.get('conforms', True):
                errors = validation.get('errors', [])
                print(f"  Found {len(errors)} validation errors")

            cleanup_twin(client, "demo-posthoc")
    except Exception as e:
        print(f"  Error: {e}")

    print_section("Demo Complete")
    print("\nKey takeaways:")
    print("  1. Use ?schema=<ontology_id> to validate during creation")
    print("  2. Invalid data is rejected with HTTP 422 and error details")
    print("  3. Valid data includes a validation report in the response")
    print("  4. Post-hoc validation is available via /twins/{id}/validate")
    print("=" * 70)

    client.close()


if __name__ == "__main__":
    main()
