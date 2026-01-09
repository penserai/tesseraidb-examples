# Smart Building Digital Twin Examples

This directory contains examples for creating and managing a smart building digital twin, including real-time sensor monitoring using RDF Stream Processing (RSP).

## Files

| File | Description |
|------|-------------|
| `seed.py` | Creates the smart building digital twin with floors, rooms, HVAC systems, sensors, and lighting |
| `rsp_demo.py` | Demonstrates real-time sensor monitoring using continuous SPARQL queries |

## Prerequisites

1. Start the TesseraiDB server:
   ```bash
   cargo run
   ```

2. Seed the smart building data:
   ```bash
   python examples/smart_building/seed.py
   ```

## RSP Demo

The `rsp_demo.py` script demonstrates RDF Stream Processing for real-time building monitoring:

### Features

- **Stream Sources**: Captures sensor updates from the EventBus
- **Continuous Queries**: Four pre-configured monitoring queries:
  - High Temperature Alert (> 26°C)
  - CO2 Threshold Violation (> 800 ppm)
  - Occupancy Pattern Detection
  - Low Humidity Alert (< 30%)
- **Sliding Windows**: Time-based and tumbling window configurations
- **Sensor Simulation**: Optional mode to generate realistic sensor events

### Usage

```bash
# Basic run - shows current RSP status and query results
python examples/smart_building/rsp_demo.py

# Run with sensor simulation (60 seconds of updates)
python examples/smart_building/rsp_demo.py --simulate

# Custom simulation duration
python examples/smart_building/rsp_demo.py --simulate --duration 120

# Clean up after demo
python examples/smart_building/rsp_demo.py --simulate --cleanup
```

### Example Output

```
============================================================
 Smart Building RSP Demo
 Real-time Sensor Monitoring with Continuous Queries
============================================================

  RSP Service Available ✓

============================================================
 Setting Up Stream Sources
============================================================
  ✓ Created stream source: smart-building-sensors (ID: example-token_019b...)
    Status: Running

============================================================
 Setting Up Continuous Queries
============================================================

  ✓ Created query: High Temperature Alert
    ID: example-token_019b...
    Window: time_based, 300s
    Active: True

  ✓ Created query: CO2 Threshold Violation
    ID: example-token_019b...
    Window: time_based, 180s
    Active: True

  ✓ Created query: Occupancy Pattern Detection
    ID: example-token_019b...
    Window: tumbling, 60s
    Active: True

  ✓ Created query: Low Humidity Alert
    ID: example-token_019b...
    Window: time_based, 600s
    Active: True

============================================================
 RSP Service Statistics
============================================================
  Total Queries:           4
  Active Queries:          4
  Total Sources:           1
  Events in Windows:       0
  Results Generated:       0

============================================================
 Simulating Sensor Updates (70s)
============================================================
  ✓ sensor-temp-room-2-101: 25.7°C
  ✓ sensor-co2-room-2-101: 518 ppm
  ✓ sensor-temp-room-2-106: 20.8°C
  🔥 HIGH sensor-temp-room-2-108: 26.5°C
  ✓ sensor-co2-room-2-108: 514 ppm
  🔥 HIGH sensor-temp-room-2-102: 28.7°C
  ⚠️  HIGH sensor-co2-room-2-103: 860 ppm
  ✓ sensor-temp-room-2-105: 25.0°C
  ...

  Total updates: 82

  Waiting for query evaluation...

============================================================
 Query Results
============================================================

  📊 High Temperature Alert
     ID: example-token_019b...
     Active: True
     Total Results: 1
     Recent Results:
  - Window: 2026-12-23T18:25:17Z to 2026-12-23T18:26:18Z
  - Window: 2026-12-23T18:25:17Z to 2026-12-23T18:26:18Z
  - Window: 2026-12-23T18:25:17Z to 2026-12-23T18:26:18Z
         Events: 71, Bindings: 50
         Sample: {'sensor': {'type': 'uri', 'value': '<urn:tesserai:twin:sensor-temp-room-2-102>'},
                  'temperature': {'type': 'literal', 'value': '"27.9"^^<xsd:double>'}}

  📊 CO2 Threshold Violation
     ID: example-token_019b...
     Active: True
     Total Results: 2
     Recent Results:
  - Window: 2026-12-23T18:25:17Z to 2026-12-23T18:26:18Z
  - Window: 2026-12-23T18:25:17Z to 2026-12-23T18:26:18Z
  - Window: 2026-12-23T18:25:17Z to 2026-12-23T18:26:18Z
         Events: 71, Bindings: 2
         Sample: {'co2Level': {'type': 'literal', 'value': '"958"^^<xsd:integer>'},
                  'sensor': {'type': 'uri', 'value': '<urn:tesserai:twin:sensor-co2-room-2-108>'}}

  📊 Occupancy Pattern Detection
     ID: example-token_019b...
     Active: True
     Total Results: 1
     Recent Results:
  - Window: 2026-12-23T18:25:17Z to 2026-12-23T18:26:18Z
  - Window: 2026-12-23T18:25:17Z to 2026-12-23T18:26:18Z
  - Window: 2026-12-23T18:25:17Z to 2026-12-23T18:26:18Z
         Events: 71, Bindings: 25
         Sample: {'isOccupied': {'type': 'literal', 'value': '"true"^^<xsd:boolean>'},
                  'occupancy': {'type': 'literal', 'value': '"8"^^<xsd:integer>'},
                  'sensor': {'type': 'uri', 'value': '<urn:tesserai:twin:sensor-occupancy-room-2-103>'}}

  📊 Low Humidity Alert
     ID: example-token_019b...
     Active: True
     Total Results: 0
     No results yet (waiting for matching events)

============================================================
 RSP Service Statistics
============================================================
  Total Queries:           4
  Active Queries:          4
  Total Sources:           1
  Events in Windows:       257
  Results Generated:       8

============================================================
 Cleanup
============================================================
  ✓ Deleted query: example-token_019b...
  ✓ Deleted query: example-token_019b...
  ✓ Deleted query: example-token_019b...
  ✓ Deleted query: example-token_019b...
  ✓ Deleted source: example-token_019b...

============================================================
 Demo Complete
============================================================
```

### Python SDK Usage

The demo uses the DTaaS Python SDK's RSP module:

```python
from dtaas import DTaaSClient
from dtaas.models import WindowConfig, WindowType, OutputConfig, ContinuousQueryCreate

client = DTaaSClient("http://localhost:8080")

# Create a stream source for sensor events
source = client.rsp.create_source(
    name="sensor-stream",
    config={
        "type": "event_bus",
        "twin_id_patterns": ["sensor-*"],
        "event_types": ["twin.updated", "twin.property_changed"],
    }
)

# Start the source
client.rsp.start_source(source.id)

# Create a continuous query for high temperature alerts
query = client.rsp.create_query(
    ContinuousQueryCreate(
        name="High Temperature Alert",
        sparql="""
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
        window=WindowConfig(
            type=WindowType.TIME_BASED,
            duration_seconds=300,  # 5-minute window
            slide_seconds=60,      # Evaluate every minute
        ),
        stream_sources=[source.id],
        output=OutputConfig(push_to_event_bus=True, persist_results=True),
    )
)

# Activate and get results
client.rsp.activate_query(query.id)
results = client.rsp.get_query_results(query.id, limit=10)

for result in results.results:
    print(f"Window: {result.window_start} to {result.window_end}")
    print(f"  Events: {result.event_count}, Bindings: {len(result.bindings)}")

# Get RSP statistics
stats = client.rsp.get_stats()
print(f"Active queries: {stats.active_queries}")
print(f"Events in windows: {stats.total_window_events}")
print(f"Results generated: {stats.total_results_generated}")
```

## Data Model

The smart building twin includes:

- **Building**: Main building entity with metadata
- **Floors**: 10 floors (lobby through rooftop)
- **Rooms**: Offices, meeting rooms, break rooms, etc.
- **Sensors**:
  - Temperature sensors (all rooms)
  - CO2 sensors (large rooms)
  - Occupancy sensors (all rooms)
  - Humidity sensors (offices, technical areas)
- **HVAC**: Plant, air handling units, VAV boxes
- **Lighting**: Controller and zone fixtures
- **Electrical**: Main panel and floor sub-panels
