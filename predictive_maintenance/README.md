# Predictive Maintenance Example

A production-grade predictive maintenance system demonstrating TesseraiDB's capabilities for industrial IoT and equipment health monitoring with Weibull distribution modeling and FMEA-based risk analysis.

## Overview

- What this domain models: Factory floor with industrial equipment types including pumps, motors, bearings, gearboxes, compressors, and heat exchangers
- Key entities and relationships: Equipment connected to sensors monitoring operational parameters, with failure modes and maintenance records
- Real-world use cases: Equipment health monitoring, failure prediction, RUL estimation, maintenance scheduling, FMEA risk analysis

## Prerequisites

- TesseraiDB account at [tesserai.io](https://tesserai.io)
- Set your API key: `export TESSERAI_API_KEY="your-api-key"`
- Python 3.10+ with the TesseraiDB SDK: `pip install tesserai`

## Quick Start

```bash
# Seed the example data
python seed.py

# Run degradation simulation
python simulation.py

# Analyze equipment health
python analysis.py

# (Optional) Start the live dashboard
python dashboard.py
```

## Digital Twins

List of main twin types created:

- **IndustrialPump**: Centrifugal and positive displacement pumps
- **ElectricMotor**: AC/DC motors with various configurations
- **RollingBearing**: Ball and roller bearings
- **Gearbox**: Speed reduction and transmission gearboxes
- **Compressor**: Air and gas compressors
- **HeatExchanger**: Shell-and-tube and plate heat exchangers
- **Sensor**: Temperature, vibration, pressure, flow sensors
- **FailureMode**: FMEA failure modes with severity ratings
- **MaintenanceRecord**: Scheduled and corrective maintenance

## Ontology

The predictive maintenance ontology defines:

- **Equipment hierarchy**: Equipment types with physics-based failure modes
- **Sensor relationships**: Equipment -> Sensor with measurement types
- **Failure modes**: FMEA parameters (severity, occurrence, detection)
- **Maintenance relationships**: Equipment -> MaintenanceRecord with history

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get equipment health status
health = client.sparql.query("""
    PREFIX maint: <http://tesserai.io/ontology/predictive_maintenance#>
    SELECT ?equipment ?type ?health ?rul WHERE {
        ?equipment a ?type .
        ?equipment maint:healthScore ?health .
        ?equipment maint:remainingUsefulLife ?rul .
        FILTER (?health < 0.7)
    }
    ORDER BY ?health
""")

# Find critical failure modes by RPN
critical = client.sparql.query("""
    PREFIX maint: <http://tesserai.io/ontology/predictive_maintenance#>
    SELECT ?equipment ?mode ?rpn WHERE {
        ?equipment maint:hasFailureMode ?fm .
        ?fm maint:modeName ?mode .
        ?fm maint:severity ?s .
        ?fm maint:occurrence ?o .
        ?fm maint:detection ?d .
        BIND(?s * ?o * ?d AS ?rpn)
        FILTER (?rpn > 200)
    }
    ORDER BY DESC(?rpn)
""")

# Update sensor reading
client.twins.update("sensor-vibration-pump-001", properties={
    "currentValue": 4.2,
    "unit": "mm/s",
    "status": "warning",
    "lastReading": "2026-12-15T10:30:00Z"
})
```

## Additional Features

### Weibull Parameters

Each equipment type has calibrated Weibull distribution parameters:

| Equipment | Shape | Scale | Location | MTTF |
|-----------|-------|-------|----------|------|
| Industrial Pump | 2.5 | 15,000h | 2,000h | ~15,300h |
| Electric Motor | 3.0 | 25,000h | 5,000h | ~27,400h |
| Rolling Bearing | 2.0 | 20,000h | 1,000h | ~18,700h |
| Gearbox | 2.8 | 30,000h | 3,000h | ~29,800h |
| Compressor | 2.2 | 18,000h | 2,500h | ~18,400h |
| Heat Exchanger | 1.8 | 40,000h | 5,000h | ~40,600h |

### FMEA Risk Calculation

Risk Priority Number (RPN) = Severity x Occurrence x Detection

| RPN Range | Priority | Action |
|-----------|----------|--------|
| > 200 | CRITICAL | Immediate maintenance required |
| 100-200 | HIGH | Schedule maintenance within 1 week |
| 50-100 | MEDIUM | Monitor closely, plan maintenance |
| < 50 | LOW | Continue normal operation |

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
