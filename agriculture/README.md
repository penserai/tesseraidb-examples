# Agriculture Example

A comprehensive precision agriculture digital twin demonstrating TesseraiDB's capabilities for smart farming operations, including fields, crops, irrigation, sensors, drones, and autonomous equipment.

## Overview

- What this domain models: Modern precision agriculture operation with 5,000 acres of cultivated land in California's Central Valley
- Key entities and relationships: Farm, fields, crops, irrigation systems, soil sensors, weather stations, drones, autonomous tractors, and implements
- Real-world use cases: Precision irrigation management, crop health monitoring, yield prediction, pest detection, autonomous farming, resource optimization

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

- **Farm**: Top-level farm entity with certifications and properties
- **AgriculturalField**: Individual fields with crop assignments
- **Crop**: Crop types with growth requirements
- **IrrigationController**: Central irrigation management
- **IrrigationZone**: Per-field irrigation zones
- **SoilSensor**: Multi-depth soil moisture and EC sensors
- **WeatherStation**: On-farm weather monitoring
- **AgriculturalDrone**: Survey and spray drones
- **AgriculturalTractor**: Autonomous and assisted tractors
- **AgriculturalImplement**: Planters, sprayers, harvesters
- **StorageFacility**: Grain silos, cold storage, equipment barns
- **WaterSource**: Wells, canals, retention ponds
- **PestTrap**: Pheromone pest monitoring traps
- **CropHealthCamera**: NDVI and thermal imaging cameras
- **FarmManagementSystem**: Integrated platform

## Ontology

The agriculture ontology defines:

- **Spatial hierarchy**: Farm -> Field -> Zones
- **Crop relationships**: Field -> grows -> Crop
- **Irrigation topology**: Controller -> Zone -> Field
- **Equipment relationships**: Farm -> hasEquipment -> Tractor/Implement
- **Sensor monitoring**: Sensor -> monitors -> Field

## Web Dashboard

The `web_ui.py` provides visualization of:

- Field map with crop status and health
- Irrigation scheduling and water usage
- Equipment tracking and status
- Weather conditions and forecasts
- Pest and disease alerts
- Yield predictions

Start the dashboard to monitor farm operations in real-time.

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all fields with current crop status
fields = client.sparql.query("""
    PREFIX agri: <http://tesserai.io/ontology/agriculture#>
    SELECT ?field ?name ?crop ?moisture WHERE {
        ?field a agri:AgriculturalField .
        ?field agri:name ?name .
        ?field agri:currentCrop ?crop .
        OPTIONAL { ?field agri:soilMoisture ?moisture }
    }
""")

# Find fields needing irrigation
dry_fields = client.sparql.query("""
    PREFIX agri: <http://tesserai.io/ontology/agriculture#>
    SELECT ?field ?moisture WHERE {
        ?field a agri:AgriculturalField .
        ?field agri:soilMoisture ?moisture .
        FILTER (?moisture < 30)
    }
""")

# Update soil sensor reading
client.twins.update("soil-sensor-field-001-01", properties={
    "moisture": 35.5,
    "temperature": 22.0,
    "electricalConductivity": 1.4,
    "lastReading": "2026-12-15T10:30:00Z"
})

# Get drone status
drones = client.twins.list(type_filter="AgriculturalDrone")
```

## Additional Features

### Crops Grown

| Crop | Field | Area | Irrigation |
|------|-------|------|------------|
| Almonds | North A, B | 950 acres | Drip |
| Tomatoes | East A | 600 acres | Drip |
| Cotton | South A | 700 acres | Center Pivot |
| Corn | South B | 650 acres | Center Pivot |
| Grapes | West A | 400 acres | Drip |
| Citrus | West B | 350 acres | Micro Sprinkler |
| Strawberries | Central | 300 acres | Drip |

### Equipment Fleet

- 4 Autonomous/assisted tractors (John Deere 8R 410, 7R 350)
- 4 Agricultural drones (survey and spray)
- 5 Implements (planter, sprayer, harvester, tiller, spreader)

### Sensor Network

- 27 soil sensors (3 per field at different depths)
- 3 weather stations
- 5 pest traps
- 5 crop health cameras

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
