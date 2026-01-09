#!/usr/bin/env python3
"""
Master script to seed all digital twin examples.

Usage:
    python seed_all.py                              # Seed all domains
    python seed_all.py --domains smart_building     # Seed specific domain
    python seed_all.py --domains smart_building,manufacturing  # Multiple domains
    python seed_all.py --list                       # List available domains
"""

import argparse
import sys
import time
from typing import Dict, Callable

# Import all seed functions
from smart_building.seed import seed_smart_building
from manufacturing.seed import seed_manufacturing
from healthcare.seed import seed_healthcare
from supply_chain.seed import seed_supply_chain
from smart_city.seed import seed_smart_city
from robotics.seed import seed_robotics
from energy_grid.seed import seed_energy_grid
from automotive.seed import seed_automotive
from agriculture.seed import seed_agriculture
from aerospace.seed import seed_aerospace
from finance.seed import seed_finance
from taxation.seed import seed_taxation
from predictive_maintenance.seed import seed_predictive_maintenance
from cascading_failure.seed import seed_cascading_failure
from alerting_system.seed import seed_alerting_system

# Registry of all available domains
DOMAINS: Dict[str, Callable] = {
    "smart_building": seed_smart_building,
    "manufacturing": seed_manufacturing,
    "healthcare": seed_healthcare,
    "supply_chain": seed_supply_chain,
    "smart_city": seed_smart_city,
    "robotics": seed_robotics,
    "energy_grid": seed_energy_grid,
    "automotive": seed_automotive,
    "agriculture": seed_agriculture,
    "aerospace": seed_aerospace,
    "finance": seed_finance,
    "taxation": seed_taxation,
    "predictive_maintenance": seed_predictive_maintenance,
    "cascading_failure": seed_cascading_failure,
    "alerting_system": seed_alerting_system,
}


def list_domains():
    """Print available domains."""
    print("\nAvailable domains:")
    print("-" * 40)
    for domain in DOMAINS:
        print(f"  - {domain}")
    print()


def seed_domain(domain: str) -> dict:
    """Seed a single domain and return results."""
    if domain not in DOMAINS:
        print(f"Error: Unknown domain '{domain}'")
        print(f"Available domains: {', '.join(DOMAINS.keys())}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f" Seeding: {domain.replace('_', ' ').title()}")
    print(f"{'='*60}")

    start_time = time.time()
    result = DOMAINS[domain]()
    elapsed = time.time() - start_time

    result["domain"] = domain
    result["elapsed_seconds"] = elapsed

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Seed digital twin examples into DTaaS"
    )
    parser.add_argument(
        "--domains",
        type=str,
        help="Comma-separated list of domains to seed (default: all)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available domains and exit"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8080",
        help="DTaaS server URL (default: http://localhost:8080)"
    )

    args = parser.parse_args()

    if args.list:
        list_domains()
        sys.exit(0)

    # Determine which domains to seed
    if args.domains:
        domains_to_seed = [d.strip() for d in args.domains.split(",")]
    else:
        domains_to_seed = list(DOMAINS.keys())

    print("\n" + "=" * 60)
    print(" DTaaS Digital Twin Examples - Seeding")
    print("=" * 60)
    print(f" Server URL: {args.url}")
    print(f" Domains to seed: {len(domains_to_seed)}")
    print("=" * 60)

    # Seed each domain
    results = []
    total_twins = 0
    total_relationships = 0
    total_start = time.time()

    for domain in domains_to_seed:
        try:
            result = seed_domain(domain)
            results.append(result)
            total_twins += result.get("twins_created", 0)
            total_relationships += result.get("relationships_created", 0)
        except Exception as e:
            print(f"\nError seeding {domain}: {e}")
            results.append({
                "domain": domain,
                "error": str(e),
                "twins_created": 0,
                "relationships_created": 0
            })

    total_elapsed = time.time() - total_start

    # Print summary
    print("\n" + "=" * 60)
    print(" SEEDING COMPLETE - SUMMARY")
    print("=" * 60)
    print(f"\n{'Domain':<25} {'Twins':>10} {'Relations':>12} {'Time':>10}")
    print("-" * 60)

    for r in results:
        domain = r.get("domain", "unknown")
        twins = r.get("twins_created", 0)
        rels = r.get("relationships_created", 0)
        elapsed = r.get("elapsed_seconds", 0)
        error = r.get("error")

        if error:
            print(f"{domain:<25} {'ERROR':>10} {'-':>12} {'-':>10}")
        else:
            print(f"{domain:<25} {twins:>10} {rels:>12} {elapsed:>9.1f}s")

    print("-" * 60)
    print(f"{'TOTAL':<25} {total_twins:>10} {total_relationships:>12} {total_elapsed:>9.1f}s")
    print("=" * 60)

    # Check for errors
    errors = [r for r in results if "error" in r]
    if errors:
        print(f"\n{len(errors)} domain(s) failed to seed.")
        sys.exit(1)
    else:
        print("\nAll domains seeded successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
