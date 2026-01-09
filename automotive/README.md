# Automotive Example

A comprehensive connected vehicle fleet digital twin demonstrating TesseraiDB's capabilities for fleet management, telematics, predictive maintenance, and charging infrastructure.

## Overview

- What this domain models: Metropolitan delivery fleet with 150 vehicles including electric, hybrid, and conventional vehicles
- Key entities and relationships: Fleet, depots, vehicles, drivers, telematics devices, charging stations, maintenance records, routes, and deliveries
- Real-world use cases: Real-time vehicle tracking, predictive maintenance, driver behavior analysis, fuel/energy optimization, route optimization, compliance monitoring

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

- **VehicleFleet**: Top-level fleet management entity
- **VehicleDepot**: Physical depot locations with charging/maintenance
- **ElectricVehicle**: Battery electric delivery vehicles
- **HybridVehicle**: Plug-in hybrid vehicles
- **ConventionalVehicle**: Diesel/gasoline trucks and vans
- **TelematicsDevice**: GPS and OBD telematics units
- **Driver**: Driver profiles with safety scores
- **ChargingStation**: DC Fast and Level 2 charging
- **MaintenanceRecord**: Service history and schedules
- **DeliveryRoute**: Optimized delivery routes
- **Delivery**: Individual delivery trips
- **Sensors**: Tire pressure, brake wear, battery health, coolant temp
- **FuelCard**: Fleet fuel card management

## Ontology

The automotive ontology defines:

- **Vehicle hierarchy**: Fleet -> Depot -> Vehicle
- **Driver assignment**: Driver -> assignedTo -> Vehicle
- **Telematics**: TelematicsDevice -> installedIn -> Vehicle
- **Maintenance**: MaintenanceRecord -> forVehicle -> Vehicle
- **Operations**: Delivery -> usesVehicle -> Vehicle, followsRoute -> Route

## Web Dashboard

The `web_ui.py` provides visualization of:

- Real-time vehicle map with status
- Fleet utilization metrics
- Charging station availability
- Driver performance scorecards
- Maintenance alerts and scheduling
- Delivery progress tracking

Start the dashboard to monitor fleet operations in real-time.

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all vehicles with current status
vehicles = client.sparql.query("""
    PREFIX auto: <http://tesserai.io/ontology/automotive#>
    SELECT ?vehicle ?model ?status ?battery WHERE {
        ?vehicle a auto:ElectricVehicle .
        ?vehicle auto:model ?model .
        ?vehicle auto:status ?status .
        ?vehicle auto:currentBatteryLevel ?battery .
    }
""")

# Find vehicles needing maintenance
maintenance_due = client.sparql.query("""
    PREFIX auto: <http://tesserai.io/ontology/automotive#>
    SELECT ?vehicle ?nextService WHERE {
        ?vehicle a ?type .
        ?vehicle auto:nextServiceDue ?nextService .
        FILTER (?nextService < "2025-01-01")
    }
""")

# Update vehicle location
client.twins.update("ev-0001", properties={
    "currentLocation": {"lat": 34.0522, "lng": -118.2437},
    "speed": 35,
    "currentBatteryLevel": 72
})

# Get charging station status
stations = client.twins.list(type_filter="ChargingStation")
```

## Additional Features

### Fleet Composition

| Vehicle Type | Count | Models |
|--------------|-------|--------|
| Electric | 75 | Ford Transit Electric, Mercedes e-Sprinter, Rivian EDV |
| Hybrid | 30 | Chrysler Pacifica PHEV |
| Conventional | 45 | Ford F-750, Ford Transit 250 |

### Depot Network

- Central Depot (80 capacity, 20 chargers)
- North Valley Depot (40 capacity, 10 chargers)
- South Bay Depot (30 capacity, 8 chargers)

### Charging Infrastructure

- DC Fast Chargers: 150 kW, 8-port stations
- Level 2 Chargers: 19.2 kW stations

### Delivery Routes

- Downtown Delivery Route (45 miles, 25 stops)
- North Valley Route (65 miles, 30 stops)
- South Bay Route (55 miles, 20 stops)
- Industrial Zone Route (35 miles, 15 stops)
- Residential West Route (50 miles, 40 stops)
- Airport Cargo Route (75 miles, 8 stops)

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
