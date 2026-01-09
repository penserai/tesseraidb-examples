#!/usr/bin/env python3
"""
Smart Building RSP (RDF Stream Processing) Demo

This example demonstrates real-time monitoring of a smart building using
continuous SPARQL queries over streaming sensor data. It showcases:

  - Creating stream sources to capture sensor updates from the EventBus
  - Defining continuous queries with sliding time windows
  - Setting up alerts for temperature, CO2, and occupancy thresholds
  - Retrieving query results and RSP statistics

Prerequisites:
  - Run seed.py first to create the smart building digital twin
  - Server must be running with RSP enabled (streams.enabled = true)

Usage:
    python rsp_demo.py [--simulate]

    --simulate: Run sensor simulation to generate events
"""

import sys
import os
import time
import random
import argparse
from datetime import datetime

# Add parent and SDK to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'sdks', 'python'))

from dtaas import DTaaSClient
from dtaas.models import (
    WindowConfig,
    WindowType,
    OutputConfig,
    ContinuousQueryCreate,
)
from common import get_client, logger, NAMESPACE_PREFIXES


# =============================================================================
# RSP Configuration
# =============================================================================

# Stream source configurations
SENSOR_STREAM_CONFIG = {
    "type": "event_bus",
    "twin_id_patterns": ["sensor-*"],  # Match all sensors
    "event_types": ["twin.updated", "twin.property_changed"],
}

# Continuous query definitions
# The RDF structure uses:
#   - Types: https://schema.org/{Type} (e.g., TemperatureSensor)
#   - Properties: http://tesserai.io/ontology/{property} (e.g., currentValue)
#   - Relationships: http://tesserai.io/ontology/rel/{rel} (e.g., locatedIn)
CONTINUOUS_QUERIES = [
    {
        "name": "High Temperature Alert",
        "description": "Detect rooms with temperature above comfort threshold (26°C)",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?sensor ?temperature ?timestamp
            WHERE {
                ?sensor dto:currentValue ?temperature .
                OPTIONAL { ?sensor dto:lastReading ?timestamp }
                FILTER(CONTAINS(STR(?sensor), "sensor-temp-"))
                FILTER(xsd:double(?temperature) > 26.0)
            }
        """,
        "window": WindowConfig(
            type=WindowType.TIME_BASED,
            duration_seconds=300,  # 5-minute window
            slide_seconds=60,      # Slide every minute
        ),
        "output": OutputConfig(
            push_to_event_bus=True,
            persist_results=True,
        ),
    },
    {
        "name": "CO2 Threshold Violation",
        "description": "Alert when CO2 levels exceed 800 ppm (ventilation needed)",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>

            SELECT ?sensor ?co2Level
            WHERE {
                ?sensor dto:currentValue ?co2Level .
                FILTER(CONTAINS(STR(?sensor), "sensor-co2-"))
                FILTER(?co2Level > 800)
            }
        """,
        "window": WindowConfig(
            type=WindowType.TIME_BASED,
            duration_seconds=180,  # 3-minute window
            slide_seconds=30,      # Slide every 30 seconds
        ),
        "output": OutputConfig(
            push_to_event_bus=True,
            persist_results=True,
        ),
    },
    {
        "name": "Occupancy Pattern Detection",
        "description": "Track room occupancy for energy optimization",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>

            SELECT ?sensor ?isOccupied ?occupancy
            WHERE {
                ?sensor dto:isOccupied ?isOccupied .
                ?sensor dto:currentOccupancy ?occupancy .
                FILTER(CONTAINS(STR(?sensor), "sensor-occupancy-"))
                FILTER(?isOccupied = true)
            }
        """,
        "window": WindowConfig(
            type=WindowType.TUMBLING,
            duration_seconds=60,  # 1-minute tumbling window
        ),
        "output": OutputConfig(
            push_to_event_bus=False,
            persist_results=True,
        ),
    },
    {
        "name": "Low Humidity Alert",
        "description": "Detect areas with humidity below 30% (comfort issue)",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?sensor ?humidity
            WHERE {
                ?sensor dto:currentValue ?humidity .
                FILTER(CONTAINS(STR(?sensor), "sensor-humidity-"))
                FILTER(xsd:double(?humidity) < 30)
            }
        """,
        "window": WindowConfig(
            type=WindowType.TIME_BASED,
            duration_seconds=600,  # 10-minute window
            slide_seconds=120,     # Slide every 2 minutes
        ),
        "output": OutputConfig(
            push_to_event_bus=True,
            persist_results=False,
        ),
    },
]


def setup_stream_sources(client: DTaaSClient) -> list[str]:
    """Create stream sources for sensor data."""
    print("\n" + "=" * 60)
    print(" Setting Up Stream Sources")
    print("=" * 60)

    source_ids = []

    # Create EventBus source for sensor updates
    try:
        source = client.rsp.create_source(
            name="smart-building-sensors",
            config=SENSOR_STREAM_CONFIG,
        )
        source_ids.append(source.id)
        print(f"  ✓ Created stream source: {source.name} (ID: {source.id})")

        # Start the source
        status = client.rsp.start_source(source.id)
        print(f"    Status: {'Running' if status.connected else 'Stopped'}")

    except Exception as e:
        # Source might already exist
        print(f"  ! Stream source setup: {e}")

        # Try to list existing sources
        try:
            sources = client.rsp.list_sources()
            for src in sources.sources:
                if "sensor" in src.name.lower() or "building" in src.name.lower():
                    source_ids.append(src.id)
                    print(f"  ✓ Using existing source: {src.name} (ID: {src.id})")
        except Exception:
            pass

    return source_ids


def setup_continuous_queries(client: DTaaSClient, source_ids: list[str]) -> list[str]:
    """Create and activate continuous queries."""
    print("\n" + "=" * 60)
    print(" Setting Up Continuous Queries")
    print("=" * 60)

    query_ids = []

    for query_def in CONTINUOUS_QUERIES:
        try:
            query = client.rsp.create_query(
                ContinuousQueryCreate(
                    name=query_def["name"],
                    description=query_def["description"],
                    sparql=query_def["sparql"],
                    window=query_def["window"],
                    stream_sources=source_ids,
                    output=query_def["output"],
                )
            )
            query_ids.append(query.id)
            print(f"\n  ✓ Created query: {query.name}")
            print(f"    ID: {query.id}")
            print(f"    Window: {query.window.type.value}, {query.window.duration_seconds}s")

            # Activate the query
            activated = client.rsp.activate_query(query.id)
            print(f"    Active: {activated.active}")

        except Exception as e:
            print(f"\n  ! Query '{query_def['name']}': {e}")

            # Try to find existing query
            try:
                queries = client.rsp.list_queries()
                for q in queries.queries:
                    if q.name == query_def["name"]:
                        query_ids.append(q.id)
                        print(f"    Using existing query: {q.id}")
                        break
            except Exception:
                pass

    return query_ids


def display_rsp_stats(client: DTaaSClient) -> None:
    """Display RSP service statistics."""
    print("\n" + "=" * 60)
    print(" RSP Service Statistics")
    print("=" * 60)

    try:
        stats = client.rsp.get_stats()
        print(f"  Total Queries:           {stats.total_queries}")
        print(f"  Active Queries:          {stats.active_queries}")
        print(f"  Total Sources:           {stats.total_sources}")
        print(f"  Events in Windows:       {stats.total_window_events}")
        print(f"  Results Generated:       {stats.total_results_generated}")
    except Exception as e:
        print(f"  ! Could not retrieve stats: {e}")


def check_query_results(client: DTaaSClient, query_ids: list[str]) -> None:
    """Check and display results from continuous queries."""
    print("\n" + "=" * 60)
    print(" Query Results")
    print("=" * 60)

    for query_id in query_ids:
        try:
            # Get query details
            query = client.rsp.get_query(query_id)
            print(f"\n  📊 {query.name}")
            print(f"     ID: {query_id}")
            print(f"     Active: {query.active}")

            # Get recent results
            results = client.rsp.get_query_results(query_id, limit=5)
            print(f"     Total Results: {results.total}")

            if results.results:
                print("     Recent Results:")
                for result in results.results[:3]:
                    print(f"       - Window: {result.window_start} to {result.window_end}")
                    print(f"         Events: {result.event_count}, Bindings: {len(result.bindings)}")
                    if result.bindings:
                        # Show first binding as example
                        print(f"         Sample: {result.bindings[0]}")
            else:
                print("     No results yet (waiting for matching events)")

        except Exception as e:
            print(f"\n  ! Query {query_id}: {e}")


def simulate_sensor_updates(client: DTaaSClient, duration_seconds: int = 60) -> None:
    """Simulate sensor updates to trigger continuous queries."""
    print("\n" + "=" * 60)
    print(f" Simulating Sensor Updates ({duration_seconds}s)")
    print("=" * 60)

    # Rooms to update
    rooms = [
        "room-2-101", "room-2-102", "room-2-103", "room-2-104",
        "room-2-105", "room-2-106", "room-2-107", "room-2-108",
    ]

    start_time = time.time()
    update_count = 0

    try:
        while time.time() - start_time < duration_seconds:
            # Pick a random room
            room = random.choice(rooms)

            # Simulate temperature update (occasionally high)
            temp_sensor_id = f"sensor-temp-{room}"
            temperature = random.uniform(20, 28) if random.random() > 0.2 else random.uniform(26, 30)

            try:
                client.twins.update(temp_sensor_id, {
                    "properties": {
                        "currentValue": round(temperature, 1),
                        "lastReading": datetime.utcnow().isoformat() + "Z",
                    }
                })
                update_count += 1
                status = "🔥 HIGH" if temperature > 26 else "✓"
                print(f"  {status} {temp_sensor_id}: {temperature:.1f}°C")
            except Exception:
                pass

            # Simulate CO2 update (occasionally high)
            if room in ["room-2-101", "room-2-102", "room-2-103", "room-2-108"]:
                co2_sensor_id = f"sensor-co2-{room}"
                co2 = random.randint(400, 700) if random.random() > 0.3 else random.randint(800, 1200)

                try:
                    client.twins.update(co2_sensor_id, {
                        "properties": {
                            "currentValue": co2,
                            "lastReading": datetime.utcnow().isoformat() + "Z",
                        }
                    })
                    update_count += 1
                    status = "⚠️  HIGH" if co2 > 800 else "✓"
                    print(f"  {status} {co2_sensor_id}: {co2} ppm")
                except Exception:
                    pass

            # Simulate occupancy update
            occupancy_sensor_id = f"sensor-occupancy-{room}"
            is_occupied = random.random() > 0.4
            occupancy = random.randint(1, 10) if is_occupied else 0

            try:
                client.twins.update(occupancy_sensor_id, {
                    "properties": {
                        "isOccupied": is_occupied,
                        "currentOccupancy": occupancy,
                        "lastMotionDetected": datetime.utcnow().isoformat() + "Z" if is_occupied else None,
                    }
                })
                update_count += 1
            except Exception:
                pass

            time.sleep(2)  # Update every 2 seconds

    except KeyboardInterrupt:
        print("\n  Simulation interrupted.")

    print(f"\n  Total updates: {update_count}")


def cleanup(client: DTaaSClient, query_ids: list[str], source_ids: list[str]) -> None:
    """Clean up queries and sources."""
    print("\n" + "=" * 60)
    print(" Cleanup")
    print("=" * 60)

    # Deactivate and delete queries
    for query_id in query_ids:
        try:
            client.rsp.deactivate_query(query_id)
            client.rsp.delete_query(query_id)
            print(f"  ✓ Deleted query: {query_id}")
        except Exception as e:
            print(f"  ! Could not delete query {query_id}: {e}")

    # Stop and delete sources
    for source_id in source_ids:
        try:
            client.rsp.stop_source(source_id)
            client.rsp.delete_source(source_id)
            print(f"  ✓ Deleted source: {source_id}")
        except Exception as e:
            print(f"  ! Could not delete source {source_id}: {e}")


def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(description="Smart Building RSP Demo")
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run sensor simulation to generate events",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Simulation duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up queries and sources after demo",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print(" Smart Building RSP Demo")
    print(" Real-time Sensor Monitoring with Continuous Queries")
    print("=" * 60)

    # Initialize client
    client = get_client()

    # Check RSP availability
    try:
        stats = client.rsp.get_stats()
        print(f"\n  RSP Service Available ✓")
    except Exception as e:
        print(f"\n  ! RSP Service not available: {e}")
        print("  Make sure streams.enabled = true in config.toml")
        return

    # Setup stream sources
    source_ids = setup_stream_sources(client)
    if not source_ids:
        print("\n  ! No stream sources available. Exiting.")
        return

    # Setup continuous queries
    query_ids = setup_continuous_queries(client, source_ids)
    if not query_ids:
        print("\n  ! No queries created. Exiting.")
        return

    # Display initial stats
    display_rsp_stats(client)

    # Run simulation if requested
    if args.simulate:
        simulate_sensor_updates(client, args.duration)

        # Check results after simulation
        print("\n  Waiting for query evaluation...")
        time.sleep(5)
        check_query_results(client, query_ids)
        display_rsp_stats(client)
    else:
        # Just check current results
        check_query_results(client, query_ids)
        print("\n  Tip: Run with --simulate to generate sensor events")

    # Cleanup if requested
    if args.cleanup:
        cleanup(client, query_ids, source_ids)
    else:
        print("\n  Tip: Run with --cleanup to remove queries and sources")

    print("\n" + "=" * 60)
    print(" Demo Complete")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
