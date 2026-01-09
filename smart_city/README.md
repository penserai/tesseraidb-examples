# Smart City Example

A comprehensive smart city digital twin demonstrating TesseraiDB's capabilities for urban infrastructure management, including transportation, utilities, public safety, and environmental monitoring.

## Overview

- What this domain models: Model smart city with 850,000 population, integrated IoT infrastructure, and multiple districts
- Key entities and relationships: City, districts, roads, intersections, public transit (metro, buses), power grid, water system, air quality stations, public safety
- Real-world use cases: Traffic management, public transit coordination, utility management, environmental monitoring, emergency response, urban planning

## Prerequisites

- TesseraiDB account at [tesserai.io](https://tesserai.io)
- Set your API key: `export TESSERAI_API_KEY="your-api-key"`
- Python 3.10+ with the TesseraiDB SDK: `pip install tesserai`

## Quick Start

```bash
# Seed the example data
python seed.py

# (Optional) Start the web dashboard
python web_ui.py
```

## Digital Twins

List of main twin types created:

- **City**: Top-level city entity
- **District**: Downtown, Tech Park, Harbor, Riverside, University, Airport, etc.
- **Road**: Highways, arterials, collectors
- **TrafficIntersection**: Signalized intersections
- **TrafficSignal**: Adaptive traffic signal controllers
- **TrafficSensor**: Inductive loop detectors
- **MetroLine**: Red, Blue, Green subway lines
- **MetroStation**: Transit hubs with connections
- **BusRoute**: City bus routes
- **Bus**: Electric buses with real-time tracking
- **PowerGrid**: City electrical grid
- **ElectricalSubstation**: Power distribution
- **SmartMeter**: Electricity consumption monitoring
- **WaterSystem**: Municipal water supply
- **WaterTreatmentPlant**: Water treatment facility
- **WaterTank**: Storage reservoirs
- **AirQualityStation**: PM2.5, O3, NO2 monitoring
- **NoiseSensor**: Urban noise monitoring
- **WeatherStation**: Meteorological data
- **PoliceStation/FireStation**: Public safety
- **SurveillanceCamera**: Traffic and security cameras
- **SmartStreetlight**: Connected LED lighting
- **ParkingFacility**: Smart parking management

## Ontology

The smart city ontology defines:

- **Administrative hierarchy**: City -> District -> Infrastructure
- **Transportation network**: Road -> Intersection, Metro Line -> Station
- **Utility systems**: PowerGrid -> Substation -> Meter
- **Environmental monitoring**: Sensor -> monitors -> District
- **Public safety**: Station -> serves -> District

## Web Dashboard

The `web_ui.py` provides visualization of:

- City-wide infrastructure map
- Real-time traffic conditions
- Public transit tracking
- Utility status dashboard
- Air quality and environmental data
- Emergency services status

Start the dashboard to monitor city operations in real-time.

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get traffic conditions on major roads
traffic = client.sparql.query("""
    PREFIX city: <http://tesserai.io/ontology/smart_city#>
    SELECT ?road ?name ?count ?speed WHERE {
        ?sensor a city:TrafficSensor .
        ?sensor city:monitors ?road .
        ?sensor city:vehicleCount ?count .
        ?sensor city:averageSpeed ?speed .
        ?road city:name ?name .
    }
""")

# Check air quality across districts
air = client.sparql.query("""
    PREFIX city: <http://tesserai.io/ontology/smart_city#>
    SELECT ?station ?district ?aqi ?pm25 WHERE {
        ?station a city:AirQualityStation .
        ?station city:aqi ?aqi .
        ?station city:pm25 ?pm25 .
        ?station city:monitors ?district .
    }
""")

# Update bus location
client.twins.update("bus-001", properties={
    "currentLocation": {"lat": 37.51, "lng": -122.01},
    "currentPassengers": 28,
    "nextStop": "Central Station"
})

# Get power grid status
grid = client.sparql.query("""
    PREFIX city: <http://tesserai.io/ontology/smart_city#>
    SELECT ?sub ?name ?load ?capacity WHERE {
        ?sub a city:ElectricalSubstation .
        ?sub city:name ?name .
        ?sub city:currentLoad ?load .
        ?sub city:capacity ?capacity .
    }
""")
```

## Additional Features

### Districts

| District | Type | Population | Area |
|----------|------|------------|------|
| Downtown | Commercial | 50,000 | 15 km2 |
| Tech Park | Business | 25,000 | 20 km2 |
| Harbor | Industrial | 15,000 | 35 km2 |
| Riverside | Residential | 120,000 | 45 km2 |
| Green Valley | Residential | 180,000 | 60 km2 |
| University | Educational | 80,000 | 25 km2 |
| Airport Zone | Transportation | 5,000 | 40 km2 |

### Public Transit

- 3 Metro lines (Red, Blue, Green)
- 37 total stations
- 4 Bus routes
- 10 Electric buses

### Utilities

- Power Grid: 2,500 MW capacity, 45% renewable
- Water System: 500 million gallons/day capacity
- 25,000 streetlights (22,000 LED, 15,000 smart)

### Environmental Monitoring

- 4 Air quality stations
- 3 Noise sensors
- 1 Central weather station

### Public Safety

- 3 Police stations (330 officers)
- 4 Fire stations (15 trucks)
- Surveillance cameras at major intersections

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
