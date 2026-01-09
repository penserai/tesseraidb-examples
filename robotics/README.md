# Robotics Example

A comprehensive warehouse automation digital twin demonstrating TesseraiDB's capabilities for robot fleet management, autonomous mobile robots (AMRs), robotic arms, and fulfillment operations.

## Overview

- What this domain models: Highly automated fulfillment center with 200 robots, AS/RS system, and 50,000 daily orders
- Key entities and relationships: Fulfillment center, warehouse zones, AMRs (shelf carriers, tote runners, pallet movers), robotic arms, AS/RS shuttles, conveyors, charging stations
- Real-world use cases: Robot fleet management, task allocation, path planning, predictive maintenance, throughput optimization, human-robot collaboration safety

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

- **FulfillmentCenter**: Top-level facility entity
- **WarehouseZone**: Receiving, storage, picking, packing, shipping, charging, maintenance
- **ShelfCarrier**: Amazon Kiva-style shelf-moving robots
- **ToteRunner**: Locus Robotics tote delivery robots
- **PalletMover**: Heavy-duty pallet transport robots
- **SortationRobot**: Geek+ sortation robots
- **FloorCleaner**: Brain Corp autonomous cleaning robots
- **PickingArm/PackingArm/PalletizingArm**: Robotic manipulators
- **VisionSystem**: Cognex vision-guided picking
- **ASRS**: Automated Storage and Retrieval System
- **ASRSShuttle**: Individual AS/RS shuttles
- **Conveyor**: Induction, picking, packing, shipping conveyors
- **ChargingStation**: Robot charging infrastructure
- **Workstation**: Human-robot collaboration stations
- **FleetManagementSystem**: Robot fleet orchestration
- **WarehouseManagementSystem**: Order and inventory management
- **SafetySensor**: LiDAR, light curtains, area scanners
- **EmergencyStop**: E-stop stations

## Ontology

The robotics ontology defines:

- **Facility hierarchy**: FulfillmentCenter -> Zone -> Equipment
- **Robot types**: AMR (ShelfCarrier, ToteRunner, PalletMover, Sortation)
- **Arm types**: Picking, Packing, Palletizing, Depalletizing
- **Safety systems**: SafetySensor -> monitors -> Zone, protects -> Arm
- **Fleet management**: FleetManager -> controls -> Robots

## Web Dashboard

The `web_ui.py` provides visualization of:

- Real-time robot map and status
- Task queue and completion rates
- Charging station utilization
- AS/RS throughput metrics
- Safety system status

Start the dashboard to monitor fulfillment operations in real-time.

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all AMRs with status
robots = client.sparql.query("""
    PREFIX robo: <http://tesserai.io/ontology/robotics#>
    SELECT ?robot ?type ?status ?battery WHERE {
        ?robot a ?type .
        ?robot robo:status ?status .
        ?robot robo:batteryLevel ?battery .
        FILTER (?type IN (robo:ShelfCarrier, robo:ToteRunner, robo:PalletMover))
    }
""")

# Find robots needing charging
low_battery = client.sparql.query("""
    PREFIX robo: <http://tesserai.io/ontology/robotics#>
    SELECT ?robot ?battery WHERE {
        ?robot robo:batteryLevel ?battery .
        FILTER (?battery < 30)
    }
""")

# Update robot position
client.twins.update("amr-0001", properties={
    "currentLocation": {"x": 45.5, "y": 22.3, "z": 0},
    "status": "working",
    "currentZone": "zone-picking"
})

# Get picking arm performance
arms = client.sparql.query("""
    PREFIX robo: <http://tesserai.io/ontology/robotics#>
    SELECT ?arm ?picks ?errors WHERE {
        ?arm a robo:PickingArm .
        ?arm robo:itemsProcessedToday ?picks .
        ?arm robo:errorRate ?errors .
    }
""")
```

## Additional Features

### Robot Fleet

| Type | Count | Manufacturer | Payload |
|------|-------|--------------|---------|
| Shelf Carrier | 80 | Kiva/Amazon | 500 kg |
| Tote Runner | 50 | Locus Robotics | 35 kg |
| Pallet Mover | 20 | Vecna Robotics | 1,500 kg |
| Sortation Robot | 30 | Geek+ | 30 kg |
| Floor Cleaner | 5 | Brain Corp | - |

### Robotic Arms

- 4 Picking arms (Universal Robots, Fanuc)
- 2 Packing arms (ABB)
- 2 Palletizing arms (KUKA)
- 1 Depalletizing arm (KUKA)

### AS/RS System

- Dematic shuttle-based system
- 20 aisles, 15 levels
- 30,000 storage locations
- 500 totes/hour throughput

### Charging Infrastructure

- 10 fast chargers (20 kW)
- 20 standard chargers (10 kW)

### Safety Systems

- 3 Safety LiDAR units
- 2 Light curtains at palletizers
- 2 Area scanners
- 10 Emergency stop stations

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
