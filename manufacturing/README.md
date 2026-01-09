# Manufacturing Example

A comprehensive Industry 4.0 smart factory digital twin demonstrating TesseraiDB's capabilities for production monitoring, predictive maintenance, quality control, and process optimization.

## Overview

- What this domain models: High-precision automotive parts manufacturing facility in Munich with CNC machines, industrial robots, and quality control systems
- Key entities and relationships: Factory, production areas, production lines, CNC machines, robots, conveyors, quality equipment, tooling, workpieces
- Real-world use cases: Production monitoring, OEE calculation, predictive maintenance, quality control, defect tracking, energy consumption analysis

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

- **Factory**: Top-level manufacturing facility
- **ProductionArea**: Receiving, machining, assembly, QC, finishing, packaging
- **ProductionLine**: Engine block, crankshaft, cylinder head, transmission lines
- **CNCMachine**: 5-axis mills, CNC lathes, grinders, boring mills
- **IndustrialRobot**: KUKA, Fanuc, ABB, Universal Robots
- **Conveyor**: Belt, roller, chain conveyors connecting areas
- **CoordinateMeasuringMachine**: CMM quality inspection
- **VisionInspectionSystem**: Automated visual inspection
- **XRayInspectionSystem**: Internal defect detection
- **CuttingTool**: End mills, face mills, drills, taps
- **Workpiece**: Work-in-progress tracking
- **VibrationSensor**: Spindle health monitoring
- **TemperatureSensor/HumiditySensor**: Environmental monitoring
- **EnergyMeter**: Factory power consumption
- **MaintenanceTask**: Preventive and corrective maintenance

## Ontology

The manufacturing ontology defines:

- **Facility hierarchy**: Factory -> Area -> Line -> Machine
- **Equipment relationships**: Line -> hasMachine -> CNC, hasRobot -> Robot
- **Material flow**: Conveyor -> connectsFrom/To -> Area
- **Quality control**: Area -> hasEquipment -> CMM, VisionSystem
- **Tooling**: Machine -> usesTool -> CuttingTool
- **Maintenance**: MaintenanceTask -> targetMachine -> Machine

## Web Dashboard

The `web_ui.py` provides visualization of:

- Real-time production status
- OEE metrics per line and machine
- Quality metrics and defect tracking
- Maintenance schedules and alerts
- Energy consumption dashboard

Start the dashboard to monitor factory operations in real-time.

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all CNC machines with status
machines = client.sparql.query("""
    PREFIX mfg: <http://tesserai.io/ontology/manufacturing#>
    SELECT ?machine ?name ?status ?oee WHERE {
        ?machine a mfg:CNCMachine .
        ?machine mfg:name ?name .
        ?machine mfg:status ?status .
        OPTIONAL { ?machine mfg:currentOEE ?oee }
    }
""")

# Find machines with high spindle load
high_load = client.sparql.query("""
    PREFIX mfg: <http://tesserai.io/ontology/manufacturing#>
    SELECT ?machine ?load WHERE {
        ?machine a mfg:CNCMachine .
        ?machine mfg:spindleLoad ?load .
        FILTER (?load > 80)
    }
""")

# Update machine status
client.twins.update("cnc-001", properties={
    "status": "running",
    "spindleSpeed": 8500,
    "spindleLoad": 72,
    "partsProduced": 165
})

# Get quality inspection results
quality = client.sparql.query("""
    PREFIX mfg: <http://tesserai.io/ontology/manufacturing#>
    SELECT ?equip ?inspected ?defects WHERE {
        ?equip a ?type .
        ?equip mfg:partsInspectedToday ?inspected .
        ?equip mfg:defectsFoundToday ?defects .
        FILTER (?type IN (mfg:CoordinateMeasuringMachine, mfg:VisionInspectionSystem))
    }
""")
```

## Additional Features

### Production Lines

| Line | Product | Takt Time | Target OEE |
|------|---------|-----------|------------|
| Engine Block | Engine Blocks | 180s | 90% |
| Crankshaft | Crankshafts | 240s | 90% |
| Cylinder Head | Cylinder Heads | 200s | 90% |
| Transmission | Transmission Housings | 300s | 90% |

### CNC Machine Fleet

- 3 DMG MORI 5-axis mills (engine blocks)
- 2 Mazak CNC lathes (crankshafts)
- 1 Studer cylindrical grinder
- 2 Makino horizontal mills (cylinder heads)
- 1 Boring mill, 1 Haas vertical mill (transmission)

### Industrial Robots

| Robot | Type | Payload | Line |
|-------|------|---------|------|
| KUKA #1-2 | Material Handling | 210 kg | Engine Block |
| Fanuc | Welding | 20 kg | Crankshaft |
| ABB | Assembly | 12 kg | Cylinder Head |
| KUKA | Palletizing | 500 kg | Transmission |
| UR10 | Collaborative | 10 kg | Engine Block |

### Quality Control

- 2 CMM systems (Zeiss Prismo, Hexagon Global)
- Vision inspection system (Keyence)
- X-Ray inspection (YXLON)
- Hardness and surface roughness testers

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
