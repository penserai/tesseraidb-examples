# Aerospace Example

A comprehensive satellite constellation digital twin demonstrating TesseraiDB's capabilities for space systems management, including satellites, ground stations, payloads, and mission control.

## Overview

- What this domain models: Low Earth Orbit communications satellite constellation with 150 satellites across 6 orbital planes
- Key entities and relationships: Satellites, ground stations, payloads (Ka-band, Ku-band transponders), inter-satellite links, mission control centers, and user terminals
- Real-world use cases: Satellite health monitoring, orbit prediction, collision avoidance, ground station scheduling, payload management, anomaly detection

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

- **SatelliteConstellation**: Top-level constellation management entity
- **CommunicationsSatellite**: Individual LEO communication satellites
- **KaBandPayload**: Ka-band transponder payloads
- **KuBandPayload**: Ku-band transponder payloads
- **GroundStation**: Gateway and TT&C ground stations worldwide
- **MissionControlCenter**: Primary and backup mission control
- **OrbitDeterminationSystem**: Orbit tracking and prediction
- **CollisionAvoidanceSystem**: Space debris and conjunction monitoring
- **InterSatelliteLink**: Optical inter-satellite communication links
- **UserTerminal**: Consumer, enterprise, maritime, and aviation terminals
- **SpaceWeatherMonitor**: Solar and geomagnetic monitoring
- **Launch**: Launch vehicle and deployment records
- **Subsystems**: ADCS, EPS, TCS, OBC, COMM, PROP subsystems

## Ontology

The aerospace ontology defines:

- **Satellite classes**: Communications satellites with orbital parameters
- **Payload types**: Ka-band and Ku-band with frequency ranges and throughput
- **Ground segment**: Gateway stations, TT&C stations, mission control
- **Orbital mechanics**: Altitude, inclination, RAAN, mean anomaly, eccentricity
- **Subsystems**: Attitude control, power, thermal, computer, communications, propulsion

## Web Dashboard

The `web_ui.py` provides visualization of:

- Constellation overview with satellite positions
- Ground station coverage maps
- Link budget and connectivity status
- Telemetry monitoring and anomaly alerts
- Orbital visualization

Start the dashboard to monitor constellation operations in real-time.

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all operational satellites
satellites = client.sparql.query("""
    PREFIX aero: <http://tesserai.io/ontology/aerospace#>
    SELECT ?sat ?name ?plane ?status WHERE {
        ?sat a aero:CommunicationsSatellite .
        ?sat aero:name ?name .
        ?sat aero:orbitalPlane ?plane .
        ?sat aero:status ?status .
        FILTER (?status = "operational")
    }
""")

# Check satellite health metrics
health = client.sparql.query("""
    PREFIX aero: <http://tesserai.io/ontology/aerospace#>
    SELECT ?sat ?battery ?temp WHERE {
        ?sat a aero:CommunicationsSatellite .
        ?sat aero:batteryLevel ?battery .
        ?sat aero:temperature ?temp .
        FILTER (?battery < 50)
    }
""")

# Update satellite telemetry
client.twins.update("sat-0001", properties={
    "batteryLevel": 92,
    "temperature": 22.5,
    "attitudeError": 0.03
})

# Get ground station contacts
contacts = client.sparql.query("""
    PREFIX aero: <http://tesserai.io/ontology/aerospace#>
    SELECT ?gs ?name ?type WHERE {
        ?gs a aero:GroundStation .
        ?gs aero:name ?name .
        ?gs aero:stationType ?type .
    }
""")
```

## Additional Features

### Constellation Configuration

| Parameter | Value |
|-----------|-------|
| Total Satellites | 150 |
| Orbital Planes | 6 |
| Satellites per Plane | 25 |
| Altitude | 550 km |
| Inclination | 53 degrees |
| Coverage | Global |

### Ground Station Network

- 6 Gateway stations (Svalbard, Alaska, Hawaii, Santiago, Perth, Dubai)
- 3 TT&C stations (London, Virginia, Singapore)
- Ka and Ku-band support at gateways
- S and X-band at TT&C stations

### Payload Capabilities

- Ka-band: 17.7-20.2 GHz downlink, 27.5-30.0 GHz uplink, 20 Gbps
- Ku-band: 10.7-12.7 GHz downlink, 14.0-14.5 GHz uplink, 8 Gbps

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
