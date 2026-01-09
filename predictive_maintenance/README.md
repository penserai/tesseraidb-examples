# Predictive Maintenance Example

A production-grade predictive maintenance system demonstrating TesserAI DB's capabilities for industrial IoT and equipment health monitoring. This example uses realistic failure modes, Weibull distribution modeling, and FMEA-based risk analysis.

## Overview

This example simulates a factory floor with various industrial equipment types, each with sensors monitoring their operational parameters. The system predicts equipment failures before they occur, enabling proactive maintenance scheduling.

### Key Features

- **Realistic Equipment Modeling**: Pumps, motors, bearings, gearboxes, compressors, and heat exchangers with physics-based failure modes
- **Weibull Failure Distribution**: Industry-standard reliability modeling with shape, scale, and location parameters
- **FMEA Integration**: Failure Mode and Effects Analysis with severity, occurrence, and detection ratings
- **Real-Time Degradation**: Continuous simulation of equipment wear patterns
- **RUL Estimation**: Remaining Useful Life prediction using degradation trajectories
- **Risk Prioritization**: Automatic ranking based on failure probability and business impact

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     TesserAI DB (DTaaS)                        │
├─────────────────────────────────────────────────────────────────┤
│  Equipment Twins          Sensor Twins         Failure Modes   │
│  ┌─────────────┐         ┌───────────┐        ┌─────────────┐  │
│  │ Pump-001    │◄────────│ Temp-001  │        │ seal_leak   │  │
│  │ Motor-002   │◄────────│ Vibr-002  │        │ bearing_fail│  │
│  │ Gearbox-003 │◄────────│ Press-003 │        │ gear_pitting│  │
│  └─────────────┘         └───────────┘        └─────────────┘  │
│         ▲                      │                     │          │
│         └──────────────────────┼─────────────────────┘          │
│                                │                                 │
│              Degradation Simulation Engine                      │
└─────────────────────────────────────────────────────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `seed.py` | Creates equipment, sensors, and failure mode twins in DTaaS |
| `simulation.py` | Runs real-time degradation simulation using Weibull models |
| `analysis.py` | Analyzes equipment health, predicts failures, schedules maintenance |
| `dashboard.py` | Live terminal dashboard showing equipment health status |

## Quick Start

### Prerequisites

```bash
# Ensure TesserAI DB server is running
cd /path/to/tesseraidb
cargo run

# Install Python dependencies
pip install dtaas requests
```

### Step 1: Seed Equipment Data

```bash
cd tesseraidb/examples
python -m predictive_maintenance.seed

# Options:
#   --base-url URL    DTaaS server URL (default: http://localhost:8080)
#   --equipment N     Number of equipment per type (default: 5)
```

Expected output:
```
Creating industrial equipment for predictive maintenance demo...
Creating 5 pumps with sensors and failure modes...
  Created pump-001 (IndustrialPump) with 4 sensors and 5 failure modes
  Created pump-002 (IndustrialPump) with 4 sensors and 5 failure modes
  ...
Creating 5 motors...
  Created motor-001 (ElectricMotor) with 3 sensors and 4 failure modes
  ...

Summary:
  Equipment created: 30
  Sensors created: 105
  Failure modes defined: 135
```

### Step 2: Run Degradation Simulation

```bash
python -m predictive_maintenance.simulation

# Options:
#   --base-url URL      DTaaS server URL
#   --interval SECONDS  Update interval (default: 5)
#   --speed FACTOR      Time acceleration (default: 100)
```

This simulates equipment aging in accelerated time:
```
Starting predictive maintenance simulation...
Loaded 30 equipment items

[14:23:45] Simulating 30 equipment | Speed: 100x | Runtime: 125.0h simulated
  pump-003: health=0.72, RUL=2847h (seal_leakage risk: HIGH)
  motor-001: health=0.89, RUL=8234h (bearing_wear risk: LOW)
```

### Step 3: Analyze Equipment Health

```bash
python -m predictive_maintenance.analysis

# Options:
#   --base-url URL     DTaaS server URL
#   --rul-threshold H  Hours threshold for urgent alerts (default: 500)
#   --top N            Show top N at-risk equipment (default: 10)
```

Output includes:
```
╔════════════════════════════════════════════════════════════════════╗
║              PREDICTIVE MAINTENANCE ANALYSIS REPORT               ║
╠════════════════════════════════════════════════════════════════════╣
║  Analysis Time: 2024-01-15 14:30:22                               ║
║  Equipment Analyzed: 30                                            ║
║  Total Failure Modes: 135                                          ║
╚════════════════════════════════════════════════════════════════════╝

 TOP 10 AT-RISK EQUIPMENT
─────────────────────────────────────────────────────────────────────
 Rank  Equipment         Type              Health    RUL      Risk
─────────────────────────────────────────────────────────────────────
 1     pump-003          IndustrialPump    0.34     423h     CRITICAL
 2     compressor-002    Compressor        0.45     678h     HIGH
 3     motor-005         ElectricMotor     0.52     892h     HIGH
 ...

 FAILURE MODE ANALYSIS (FMEA)
─────────────────────────────────────────────────────────────────────
 Equipment      Mode              Severity  Occur  Detect  RPN   Priority
─────────────────────────────────────────────────────────────────────
 pump-003       seal_leakage      7         8      6       336   CRITICAL
 pump-003       impeller_erosion  8         5      4       160   HIGH
 ...

 RECOMMENDED MAINTENANCE SCHEDULE
─────────────────────────────────────────────────────────────────────
 Date           Equipment         Action                    Priority
─────────────────────────────────────────────────────────────────────
 2024-01-18     pump-003          Replace mechanical seal   URGENT
 2024-01-25     compressor-002    Inspect valve assembly    HIGH
 2024-02-01     motor-005         Check bearing clearance   MEDIUM
```

### Step 4: Live Dashboard

```bash
python -m predictive_maintenance.dashboard

# Options:
#   --base-url URL      DTaaS server URL
#   --refresh SECONDS   Refresh interval (default: 5)
```

The dashboard shows real-time equipment health:
```
╔════════════════════════════════════════════════════════════════════════════╗
║                    PREDICTIVE MAINTENANCE DASHBOARD                        ║
║                         2024-01-15 14:35:22                                ║
╚════════════════════════════════════════════════════════════════════════════╝

 FLEET OVERVIEW
───────────────────────────────────────────────────────────────────────────────
 Total Equipment: 30 | Healthy: 22 | Degraded: 6 | Critical: 2

 EQUIPMENT STATUS
───────────────────────────────────────────────────────────────────────────────
 Equipment             Type              Health              RUL      Status
───────────────────────────────────────────────────────────────────────────────
 pump-003              IndustrialPump    ██░░░░░░░░ 34%      423h    CRITICAL
 compressor-002        Compressor        ████░░░░░░ 45%      678h    DEGRADED
 motor-005             ElectricMotor     █████░░░░░ 52%      892h    DEGRADED
 gearbox-001           Gearbox           ████████░░ 82%     3421h    HEALTHY
 ...

 SENSOR READINGS (pump-003)
───────────────────────────────────────────────────────────────────────────────
 Sensor                Value        Trend        Threshold    Status
───────────────────────────────────────────────────────────────────────────────
 Temperature           87.3°C       ▲ +2.1       80°C         WARNING
 Vibration             4.2 mm/s     ▲ +0.8       3.5 mm/s     ALARM
 Pressure              145 psi      ─ +0.0       200 psi      OK
 Flow Rate             42 GPM       ▼ -3.2       35 GPM       OK
```

## Equipment Types

### Industrial Pump
- **Sensors**: Temperature, Vibration, Pressure, Flow Rate
- **Failure Modes**: Seal leakage, Impeller erosion, Bearing wear, Cavitation, Shaft misalignment

### Electric Motor
- **Sensors**: Winding temperature, Vibration, Current
- **Failure Modes**: Bearing failure, Winding insulation, Rotor bar damage, Shaft misalignment

### Rolling Bearing
- **Sensors**: Vibration, Temperature, Acoustic emission
- **Failure Modes**: Outer race spalling, Inner race damage, Cage wear, Lubrication failure

### Gearbox
- **Sensors**: Vibration, Oil temperature, Oil particle count
- **Failure Modes**: Gear tooth pitting, Bearing wear, Oil degradation, Shaft fatigue

### Compressor
- **Sensors**: Suction pressure, Discharge pressure, Temperature, Vibration
- **Failure Modes**: Valve failure, Bearing wear, Seal leakage, Intercooler fouling

### Heat Exchanger
- **Sensors**: Inlet temperature, Outlet temperature, Pressure drop, Flow rate
- **Failure Modes**: Fouling, Tube leak, Gasket failure, Corrosion

## Weibull Parameters

Each equipment type has calibrated Weibull distribution parameters:

| Equipment | Shape (β) | Scale (η) | Location (γ) | MTTF |
|-----------|-----------|-----------|--------------|------|
| Industrial Pump | 2.5 | 15,000h | 2,000h | ~15,300h |
| Electric Motor | 3.0 | 25,000h | 5,000h | ~27,400h |
| Rolling Bearing | 2.0 | 20,000h | 1,000h | ~18,700h |
| Gearbox | 2.8 | 30,000h | 3,000h | ~29,800h |
| Compressor | 2.2 | 18,000h | 2,500h | ~18,400h |
| Heat Exchanger | 1.8 | 40,000h | 5,000h | ~40,600h |

## FMEA Risk Calculation

Risk Priority Number (RPN) = Severity × Occurrence × Detection

| RPN Range | Priority | Action |
|-----------|----------|--------|
| > 200 | CRITICAL | Immediate maintenance required |
| 100-200 | HIGH | Schedule maintenance within 1 week |
| 50-100 | MEDIUM | Monitor closely, plan maintenance |
| < 50 | LOW | Continue normal operation |

## Integration with TesserAI DB

This example demonstrates key DTaaS capabilities:

1. **Digital Twin Modeling**: Equipment as first-class twins with rich metadata
2. **Sensor Relationships**: `hasSensor` relationships linking equipment to sensors
3. **Failure Mode Ontology**: `hasFailureMode` relationships with FMEA parameters
4. **Real-Time Updates**: Continuous property updates via DTaaS API
5. **Graph Queries**: Finding related sensors, failure modes, and maintenance history
6. **Event Streaming**: Subscribe to equipment health changes via SSE

## Customization

### Adding New Equipment Types

Edit `seed.py` to add new equipment definitions:

```python
# Define failure modes
MY_EQUIPMENT_FAILURE_MODES = [
    {"mode": "failure_a", "mtbf_hours": 5000, "severity": 8, "detection": 5},
    {"mode": "failure_b", "mtbf_hours": 10000, "severity": 6, "detection": 7},
]

# Define sensors
MY_EQUIPMENT_SENSORS = [
    {"type": "SensorA", "unit": "units", "threshold_high": 100},
    {"type": "SensorB", "unit": "units", "threshold_high": 50},
]

# Add to creation functions
def create_my_equipment(client, count: int):
    # ... implementation
```

### Adjusting Degradation Models

Edit `simulation.py` to modify Weibull parameters:

```python
WEIBULL_PARAMS = {
    "MyEquipment": WeibullParameters(
        shape=2.5,      # β: wear-out pattern (>1)
        scale=15000,    # η: characteristic life in hours
        location=2000,  # γ: failure-free period
    ),
}
```

## Troubleshooting

**No equipment found**
```
Run seed.py first to create equipment twins
```

**Connection refused**
```
Ensure TesserAI DB server is running on the specified URL
```

**Slow updates**
```
Reduce --interval or increase --speed for faster simulation
```
