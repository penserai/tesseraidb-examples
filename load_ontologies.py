#!/usr/bin/env python3
"""
Load example ontologies into the TesseraiDB service.

This script loads the core and domain-specific ontologies with their SHACL shapes
into the service, making them available for twin validation.

Uses parallel uploads for faster execution against remote APIs.

Usage:
    python load_ontologies.py [--base-url URL] [--api-key KEY]

Authentication:
    Set the TESSERAI_API_KEY environment variable or use --api-key.
    Get your API key from https://tesserai.io

Example:
    export TESSERAI_API_KEY="your-api-key"
    python load_ontologies.py

    # Or with explicit URL and key:
    python load_ontologies.py --base-url http://localhost:8080 --api-key your-key
"""

import os
import sys
import argparse
import time
from pathlib import Path
import httpx

# Add the SDK to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdks', 'python'))

from common import logger, DEFAULT_BASE_URL, get_api_key, bulk_upload_ontologies

# Ontology definitions with their IDs and file paths
ONTOLOGIES = [
    ("core", "ontologies/core.ttl", "DTaaS Core Ontology"),
    ("automotive", "ontologies/automotive.ttl", "Automotive Domain Ontology"),
    ("robotics", "ontologies/robotics.ttl", "Robotics Domain Ontology"),
    ("healthcare", "ontologies/healthcare.ttl", "Healthcare Domain Ontology"),
    ("smart_building", "ontologies/smart_building.ttl", "Smart Building Domain Ontology"),
    ("supply_chain", "ontologies/supply_chain.ttl", "Supply Chain Domain Ontology"),
    ("energy_grid", "ontologies/energy_grid.ttl", "Energy Grid Domain Ontology"),
    ("finance", "ontologies/finance.ttl", "Finance Domain Ontology"),
    ("agriculture", "ontologies/agriculture.ttl", "Agriculture Domain Ontology"),
    ("manufacturing", "ontologies/manufacturing.ttl", "Manufacturing Domain Ontology"),
    ("aerospace", "ontologies/aerospace.ttl", "Aerospace Domain Ontology"),
    ("smart_city", "ontologies/smart_city.ttl", "Smart City Domain Ontology"),
    ("taxation", "ontologies/taxation.ttl", "Taxation Domain Ontology"),
    ("predictive_maintenance", "ontologies/predictive_maintenance.ttl", "Predictive Maintenance Domain Ontology"),
    ("cascading_failure", "ontologies/cascading_failure.ttl", "Cascading Failure Analysis Domain Ontology"),
    ("alerting_system", "ontologies/alerting_system.ttl", "Real-Time Alerting System Domain Ontology"),
    ("reasoning_axioms", "ontologies/reasoning_axioms.ttl", "OWL 2 RL Reasoning Axioms"),
]


def list_loaded_ontologies(base_url: str, token: str) -> list:
    """List all ontologies currently loaded in the service."""
    try:
        with httpx.Client() as http:
            response = http.get(
                f"{base_url}/api/v1/ontologies",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": "default"
                }
            )
            if response.status_code == 200:
                data = response.json()
                # Handle both list and dict responses
                if isinstance(data, list):
                    return data
                return data.get("ontologies", [])
        return []
    except Exception as e:
        logger.error(f"Error listing ontologies: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Load example ontologies into TesseraiDB")
    parser.add_argument("--base-url", help="TesseraiDB service base URL", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", help="API key for authentication (or set TESSERAI_API_KEY env var)")
    parser.add_argument("--list", action="store_true", help="List loaded ontologies only")
    parser.add_argument("--ontology", help="Load only a specific ontology by ID")
    parser.add_argument("--sequential", action="store_true", help="Load ontologies one at a time (slower)")
    args = parser.parse_args()

    base_url = os.environ.get("TESSERAI_API_URL", args.base_url)

    logger.info(f"Connecting to TesseraiDB at {base_url}")

    # Get API key from argument or environment variable
    token = args.api_key or get_api_key()
    if not token:
        print("Error: No API key provided. Set TESSERAI_API_KEY environment variable or use --api-key")
        print("Get your API key from https://tesserai.io")
        sys.exit(1)

    if args.list:
        # Just list existing ontologies
        print("\nLoaded Ontologies:")
        print("=" * 60)
        ontologies = list_loaded_ontologies(base_url, token)
        if ontologies:
            for ont in ontologies:
                print(f"  - {ont.get('id', 'unknown')}: {ont.get('label', 'No label')}")
        else:
            print("  No ontologies loaded")
        print("=" * 60)
        return

    # Filter ontologies if specific one requested
    ontologies_to_load = ONTOLOGIES
    if args.ontology:
        ontologies_to_load = [(oid, fp, desc) for oid, fp, desc in ONTOLOGIES if oid == args.ontology]
        if not ontologies_to_load:
            print(f"Error: Ontology '{args.ontology}' not found")
            sys.exit(1)

    # Load ontologies
    print("\nLoading DTaaS Example Ontologies")
    print("=" * 60)
    print(f"  Mode: {'Sequential' if args.sequential else 'Parallel'}")
    print(f"  Count: {len(ontologies_to_load)} ontologies")
    print("=" * 60)

    start_time = time.time()
    examples_dir = Path(__file__).parent

    # Convert relative paths to absolute
    ontologies_with_paths = [
        (oid, str(examples_dir / fp), desc)
        for oid, fp, desc in ontologies_to_load
    ]

    if args.sequential:
        # Sequential loading (for debugging)
        loaded = 0
        failed = 0
        for ontology_id, file_path, description in ontologies_with_paths:
            full_path = Path(file_path)
            if not full_path.exists():
                logger.warning(f"Ontology file not found: {full_path}")
                failed += 1
                continue

            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    ontology_data = f.read()

                with httpx.Client(timeout=60.0) as http:
                    response = http.post(
                        f"{base_url}/api/v1/ontologies/{ontology_id}",
                        content=ontology_data,
                        headers={
                            "Content-Type": "text/turtle",
                            "Authorization": f"Bearer {token}",
                            "X-Tenant-ID": "default"
                        }
                    )

                    if response.status_code in (200, 201):
                        logger.info(f"Loaded ontology: {ontology_id} ({description})")
                        loaded += 1
                    else:
                        logger.error(f"Failed to load ontology {ontology_id}: {response.status_code}")
                        failed += 1

            except Exception as e:
                logger.error(f"Error loading ontology {ontology_id}: {e}")
                failed += 1
    else:
        # Parallel loading (default, faster)
        loaded, failed = bulk_upload_ontologies(base_url, token, ontologies_with_paths)

    elapsed = time.time() - start_time

    print("=" * 60)
    print(f"Summary: {loaded} loaded, {failed} failed in {elapsed:.1f}s")

    if loaded > 0:
        print("\nOntologies are now available for validation.")
        print("Use the '?schema=<ontology_id>' query parameter when creating twins.")
        print("\nExample:")
        print("  POST /twins/my-vehicle?schema=automotive")
        print("=" * 60)


if __name__ == "__main__":
    main()
