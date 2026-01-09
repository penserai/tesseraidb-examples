#!/usr/bin/env python3
"""
Cross-Domain Queries for DTaaS Examples.

This script demonstrates querying digital twins across multiple domains,
showing how cross-domain interoperability enables unified analysis.

Usage:
    python examples/queries.py
    python examples/queries.py --domain healthcare
    python examples/queries.py --cross-domain

Features:
    - Query twins by domain
    - Count twins across all domains
    - Find cross-domain relationships
    - Analyze shared infrastructure
"""

import argparse
from collections import Counter
from common import get_client, DOMAIN_NAMESPACES, get_all_domains


def print_section(name: str):
    """Print a section header."""
    print(f"\n{'='*70}")
    print(f" {name}")
    print('='*70)


def print_subsection(name: str):
    """Print a subsection header."""
    print(f"\n  --- {name} ---")


def query_all_domains(client):
    """Query and display twins from all domains."""
    print_section("Domain Overview")

    twins = client.twins.list(page_size=1000)
    print(f"Total twins in system: {len(twins)}")

    # Count by domain
    domain_counts = Counter(t.domain for t in twins if t.domain)
    no_domain = len([t for t in twins if not t.domain])

    print("\nTwins by Domain:")
    print("-" * 40)
    for domain in get_all_domains():
        count = domain_counts.get(domain, 0)
        if count > 0:
            bar = "#" * min(count // 5, 30)
            print(f"  {domain:20}: {count:4}  {bar}")

    if no_domain > 0:
        print(f"  {'(no domain)':20}: {no_domain:4}")

    return twins


def query_domain(client, domain: str):
    """Query twins from a specific domain."""
    print_section(f"Domain: {domain}")

    if domain not in DOMAIN_NAMESPACES:
        print(f"Unknown domain: {domain}")
        print(f"Available domains: {', '.join(get_all_domains())}")
        return []

    twins = client.twins.list(domain=domain, page_size=1000)
    print(f"Found {len(twins)} twins in the '{domain}' domain")

    # Count by type
    type_counts = Counter(t.type_uri.split('#')[-1] if t.type_uri else 'Unknown' for t in twins)

    print("\nTypes in this domain:")
    for twin_type, count in type_counts.most_common(15):
        print(f"  {twin_type}: {count}")

    return twins


def query_cross_domain_relationships(client):
    """Find and display cross-domain relationships."""
    print_section("Cross-Domain Relationships")

    twins = client.twins.list(page_size=1000)
    twin_domains = {t.id: t.domain for t in twins if t.domain}

    cross_domain_rels = []
    checked = 0

    print("\nScanning for cross-domain relationships...")
    for twin in twins[:100]:  # Check first 100 twins to keep it fast
        if not twin.domain:
            continue

        try:
            rels = client.twins.get_relationships(twin.id)
            for rel in rels:
                target_id = rel.get('target', '')
                # Look up target's domain
                target_domain = twin_domains.get(target_id)

                if target_domain and target_domain != twin.domain:
                    cross_domain_rels.append({
                        'source_id': twin.id,
                        'source_domain': twin.domain,
                        'rel_type': rel.get('type', 'unknown'),
                        'target_id': target_id,
                        'target_domain': target_domain
                    })
            checked += 1
        except Exception:
            pass

    print(f"Checked {checked} twins, found {len(cross_domain_rels)} cross-domain relationships\n")

    if cross_domain_rels:
        # Group by domain pair
        domain_pairs = Counter(
            f"{r['source_domain']} --> {r['target_domain']}"
            for r in cross_domain_rels
        )

        print("Cross-Domain Connections:")
        print("-" * 50)
        for pair, count in domain_pairs.most_common():
            print(f"  {pair}: {count} relationships")

        print("\nSample Cross-Domain Relationships:")
        print("-" * 50)
        for rel in cross_domain_rels[:10]:
            print(f"  [{rel['source_domain']}] {rel['source_id']}")
            print(f"    --[{rel['rel_type']}]-->")
            print(f"  [{rel['target_domain']}] {rel['target_id']}")
            print()

    return cross_domain_rels


def query_shared_infrastructure(client):
    """Find infrastructure that serves multiple domains."""
    print_section("Shared Infrastructure Analysis")

    twins = client.twins.list(page_size=1000)

    # Find twins that could be shared infrastructure
    # (HVAC, Power, Buildings, etc.)
    shared_types = ['Building', 'HVAC', 'Substation', 'Generator', 'Solar', 'Battery']
    infrastructure = [
        t for t in twins
        if t.type_uri and any(st in t.type_uri for st in shared_types)
    ]

    print(f"Found {len(infrastructure)} infrastructure twins\n")

    for infra in infrastructure[:10]:
        print(f"  {infra.id}: {infra.type_uri}")
        print(f"    Domain: {infra.domain or 'unspecified'}")
        print(f"    Name: {infra.name}")

        # Check what it's connected to
        try:
            rels = client.twins.get_relationships(infra.id)
            if rels:
                targets_by_domain = {}
                twins_lookup = {t.id: t for t in twins}
                for rel in rels:
                    target_id = rel.get('target', '')
                    target = twins_lookup.get(target_id)
                    if target and target.domain:
                        if target.domain not in targets_by_domain:
                            targets_by_domain[target.domain] = []
                        targets_by_domain[target.domain].append(rel.get('type', 'unknown'))

                if targets_by_domain:
                    print(f"    Serves domains: {', '.join(targets_by_domain.keys())}")
        except Exception:
            pass
        print()


def query_type_distribution(client):
    """Analyze type distribution across domains."""
    print_section("Type Distribution Across Domains")

    twins = client.twins.list(page_size=1000)

    # Build domain -> types mapping
    domain_types = {}
    for twin in twins:
        if not twin.domain:
            continue
        if twin.domain not in domain_types:
            domain_types[twin.domain] = Counter()
        type_name = twin.type_uri.split('#')[-1] if twin.type_uri else 'Unknown'
        domain_types[twin.domain][type_name] += 1

    for domain in sorted(domain_types.keys()):
        print(f"\n{domain.upper()}:")
        print("-" * 40)
        for type_name, count in domain_types[domain].most_common(5):
            print(f"  {type_name}: {count}")


def query_sensors_by_domain(client):
    """Find sensors across all domains."""
    print_section("Sensors Across Domains")

    twins = client.twins.list(page_size=1000)
    sensors = [t for t in twins if t.type_uri and 'Sensor' in t.type_uri]

    print(f"Total sensors: {len(sensors)}\n")

    # Group by domain
    sensors_by_domain = {}
    for sensor in sensors:
        domain = sensor.domain or 'unspecified'
        if domain not in sensors_by_domain:
            sensors_by_domain[domain] = []
        sensors_by_domain[domain].append(sensor)

    for domain, domain_sensors in sorted(sensors_by_domain.items()):
        print(f"{domain}: {len(domain_sensors)} sensors")
        for sensor in domain_sensors[:3]:
            type_name = sensor.type_uri.split('#')[-1] if sensor.type_uri else 'Sensor'
            print(f"    - {sensor.id}: {type_name}")
        if len(domain_sensors) > 3:
            print(f"    ... and {len(domain_sensors) - 3} more")


def query_robots_and_automation(client):
    """Find robots and automation systems across domains."""
    print_section("Robots & Automation Systems")

    twins = client.twins.list(page_size=1000)

    robot_keywords = ['Robot', 'AMR', 'AGV', 'Drone', 'Arm', 'Shuttle', 'Autonomous']
    robots = [
        t for t in twins
        if t.type_uri and any(kw in t.type_uri for kw in robot_keywords)
    ]

    print(f"Total robotic/automated systems: {len(robots)}\n")

    # Group by domain
    robots_by_domain = {}
    for robot in robots:
        domain = robot.domain or 'unspecified'
        if domain not in robots_by_domain:
            robots_by_domain[domain] = Counter()
        type_name = robot.type_uri.split('#')[-1] if robot.type_uri else 'Robot'
        robots_by_domain[domain][type_name] += 1

    for domain, type_counts in sorted(robots_by_domain.items()):
        total = sum(type_counts.values())
        print(f"\n{domain} ({total} robots):")
        for type_name, count in type_counts.most_common(5):
            print(f"    {type_name}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Query DTaaS digital twins")
    parser.add_argument('--domain', type=str, help="Query specific domain")
    parser.add_argument('--cross-domain', action='store_true', help="Show cross-domain relationships")
    parser.add_argument('--infrastructure', action='store_true', help="Analyze shared infrastructure")
    parser.add_argument('--types', action='store_true', help="Show type distribution")
    parser.add_argument('--sensors', action='store_true', help="Find sensors across domains")
    parser.add_argument('--robots', action='store_true', help="Find robots and automation")
    parser.add_argument('--all', action='store_true', help="Run all queries")
    args = parser.parse_args()

    client = get_client()

    # Check token being used
    token = client._token or "(no token)"
    print(f"Using token: {token[:20]}..." if len(token) > 20 else f"Using token: {token}")

    if args.domain:
        query_domain(client, args.domain)
    elif args.cross_domain:
        query_cross_domain_relationships(client)
    elif args.infrastructure:
        query_shared_infrastructure(client)
    elif args.types:
        query_type_distribution(client)
    elif args.sensors:
        query_sensors_by_domain(client)
    elif args.robots:
        query_robots_and_automation(client)
    elif args.all:
        query_all_domains(client)
        query_type_distribution(client)
        query_cross_domain_relationships(client)
        query_sensors_by_domain(client)
        query_robots_and_automation(client)
        query_shared_infrastructure(client)
    else:
        # Default: overview and basic stats
        query_all_domains(client)
        query_type_distribution(client)

    print_section("Query Complete")
    print("Use --help to see available query options")
    print("Examples:")
    print("  python queries.py --domain healthcare")
    print("  python queries.py --cross-domain")
    print("  python queries.py --all")


if __name__ == "__main__":
    main()
