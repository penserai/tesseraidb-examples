# Smart Building Example

A comprehensive smart building digital twin demonstrating TesseraiDB's capabilities for building management, sensor monitoring, and real-time stream processing (RSP).

## Overview

- What this domain models: Multi-floor commercial building with HVAC, lighting, electrical systems, and environmental sensors
- Key entities and relationships: Building, floors, rooms, HVAC equipment (AHUs, VAV boxes), sensors (temperature, CO2, occupancy, humidity), lighting zones
- Real-world use cases: Energy optimization, occupant comfort, predictive maintenance, space utilization, air quality monitoring

## Prerequisites

- TesseraiDB account at [tesserai.io](https://tesserai.io)
- Set your API key: `export TESSERAI_API_KEY="your-api-key"`
- Python 3.10+ with the TesseraiDB SDK: `pip install tesserai`

## Quick Start

```bash
# Seed the example data
python seed.py

# Run the RSP demo with sensor simulation
python rsp_demo.py --simulate

# Custom simulation duration
python rsp_demo.py --simulate --duration 120
```

## Digital Twins

List of main twin types created:

- **Building**: Main building entity with metadata
- **Floor**: Building floors (lobby through rooftop)
- **Room**: Offices, meeting rooms, break rooms, restrooms
- **HVACPlant**: Central HVAC plant equipment
- **AirHandlingUnit**: Air handling units per zone
- **VAVBox**: Variable air volume boxes per room
- **TemperatureSensor**: Room temperature monitoring
- **CO2Sensor**: Air quality monitoring in large rooms
- **OccupancySensor**: Space utilization tracking
- **HumiditySensor**: Humidity monitoring
- **LightingController**: Building lighting system
- **LightingZone**: Lighting fixtures per zone
- **ElectricalPanel**: Main and floor sub-panels

## Ontology

The smart building ontology defines:

- **Spatial hierarchy**: Building -> Floor -> Room
- **HVAC topology**: Plant -> AHU -> VAV -> Room
- **Sensor relationships**: Sensor -> monitors -> Room/Equipment
- **Control relationships**: Controller -> controls -> Zone/Equipment

## RSP Demo Features

The `rsp_demo.py` demonstrates RDF Stream Processing for real-time monitoring:

- **Stream Sources**: Captures sensor updates from the EventBus
- **Continuous Queries**: Pre-configured monitoring queries
  - High Temperature Alert (> 26C)
  - CO2 Threshold Violation (> 800 ppm)
  - Occupancy Pattern Detection
  - Low Humidity Alert (< 30%)
- **Sliding Windows**: Time-based and tumbling window configurations

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all rooms with current conditions
rooms = client.sparql.query("""
    PREFIX bldg: <http://tesserai.io/ontology/smart_building#>
    SELECT ?room ?name ?temp ?co2 ?occupancy WHERE {
        ?room a bldg:Room ;
              bldg:name ?name .
        OPTIONAL { ?room bldg:currentTemperature ?temp }
        OPTIONAL { ?room bldg:currentCO2 ?co2 }
        OPTIONAL { ?room bldg:currentOccupancy ?occupancy }
    }
""")

# Find rooms with environmental issues
issues = client.sparql.query("""
    PREFIX bldg: <http://tesserai.io/ontology/smart_building#>
    SELECT ?room ?temp ?co2 WHERE {
        ?room a bldg:Room .
        OPTIONAL { ?room bldg:currentTemperature ?temp }
        OPTIONAL { ?room bldg:currentCO2 ?co2 }
        FILTER (?temp > 26 || ?co2 > 800)
    }
""")

# Update sensor reading
client.twins.update("sensor-temp-room-2-101", properties={
    "currentValue": 25.7,
    "unit": "Celsius",
    "lastReading": "2024-12-15T10:00:00Z",
    "status": "online"
})

# Create RSP continuous query
query = client.rsp.create_query({
    "name": "High Temperature Alert",
    "sparql": """
        PREFIX bldg: <http://tesserai.io/ontology/smart_building#>
        SELECT ?sensor ?temperature WHERE {
            ?sensor bldg:currentValue ?temperature .
            FILTER(CONTAINS(STR(?sensor), "sensor-temp-"))
            FILTER(?temperature > 26.0)
        }
    """,
    "window": {"type": "time_based", "duration_seconds": 300}
})
```

## Additional Features

### Building Data Model

- **Building**: Main entity with metadata
- **10 Floors**: Lobby through rooftop
- **Multiple Room Types**: Offices, meeting rooms, break rooms
- **Sensor Coverage**:
  - Temperature sensors in all rooms
  - CO2 sensors in large rooms
  - Occupancy sensors throughout
  - Humidity sensors in offices and technical areas

### HVAC System

- Central plant with chillers and boilers
- Air handling units per zone
- VAV boxes per room for individual control
- Energy monitoring and optimization

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
