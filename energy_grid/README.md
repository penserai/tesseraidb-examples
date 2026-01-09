# Energy Grid Example

A comprehensive power grid digital twin with Answer Set Programming (ASP) integration for solving complex optimization and diagnostic problems in energy systems.

## Overview

- What this domain models: Complete power grid infrastructure from generation (solar, wind, gas, hydro, nuclear) through transmission and distribution to consumption
- Key entities and relationships: Power plants, substations, transformers, transmission lines, battery storage, loads, and smart meters connected via grid topology
- Real-world use cases: Unit commitment optimization, fault diagnosis, N-1 contingency analysis, renewable energy integration, and grid stability monitoring

## Prerequisites

- TesseraiDB account at [tesserai.io](https://tesserai.io)
- Set your API key: `export TESSERAI_API_KEY="your-api-key"`
- Python 3.10+ with the TesseraiDB SDK: `pip install tesserai`

## Quick Start

```bash
# Seed the example data
python seed.py

# Run all ASP demonstrations
python asp_demo.py

# Or run specific demos
python asp_demo.py --demo unit-commitment
python asp_demo.py --demo fault-diagnosis
python asp_demo.py --demo contingency
```

## Digital Twins

List of main twin types created:

- **Grid**: Top-level grid network container
- **NuclearPowerPlant**: Nuclear generation (2,200 MW baseload)
- **NaturalGasPowerPlant**: Gas turbine generation (dispatchable)
- **CoalPowerPlant**: Coal generation (baseload, being phased out)
- **HydroPowerPlant**: Hydroelectric generation (dispatchable)
- **SolarFarm**: Solar photovoltaic generation (intermittent)
- **WindFarm**: Wind turbine generation (intermittent)
- **BatteryStorage**: Grid-scale battery storage systems
- **Substation**: HV transmission and distribution substations
- **TransmissionLine**: High-voltage transmission infrastructure
- **DistributionSubstation**: Step-down to distribution voltage
- **SmartMeter**: Consumer smart meters
- **ProtectiveRelay**: Fault detection and isolation equipment
- **WeatherStation**: Renewable forecasting inputs
- **DemandResponseProgram**: Curtailable load programs

## Ontology

The energy grid ontology defines:

- **Generation classes**: Dispatchable vs. intermittent sources with capacity and ramp rates
- **Grid topology**: Voltage levels, bus connections, line impedances
- **Measurements**: Active/reactive power, voltage, frequency, power factor
- **States**: Online, offline, faulted, islanded, curtailed

## ASP Demonstrations

The example includes Answer Set Programming demos for:

### 1. Unit Commitment Optimization

Decide which generators to turn on to meet forecasted demand at minimum cost while maintaining spinning reserve.

### 2. Model-Based Fault Diagnosis

Given SCADA alarms and sensor readings, identify the minimal set of faulty components that explains all observations.

### 3. N-1 Contingency Analysis

Verify that the grid remains stable if any single component fails and identify vulnerable configurations.

### 4. Natural Language ASP Interface

Create and refine ASP programs through conversational interaction using plain English.

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all generation assets
generators = client.twins.list(type_filter="PowerPlant")

# Query current grid balance
balance = client.sparql.query("""
    PREFIX energy: <http://tesserai.io/ontology/energy_grid#>
    SELECT (SUM(?gen) as ?totalGeneration) (SUM(?load) as ?totalLoad) WHERE {
        {
            ?plant a energy:PowerPlant .
            ?plant energy:currentOutput ?gen .
        } UNION {
            ?consumer a energy:Load .
            ?consumer energy:currentDemand ?load .
        }
    }
""")

# Update renewable generation based on weather
client.twins.update("solar-farm-001", properties={
    "currentOutput": 45.5,  # MW
    "irradiance": 850,      # W/m2
    "cloudCover": 15        # percent
})

# Check for overloaded transmission lines
overloaded = client.sparql.query("""
    PREFIX energy: <http://tesserai.io/ontology/energy_grid#>
    SELECT ?line ?loading WHERE {
        ?line a energy:TransmissionLine .
        ?line energy:loadingPercent ?loading .
        FILTER (?loading > 80)
    }
""")
```

## Additional Features

### Generation Mix

| Type | Capacity | Characteristics |
|------|----------|-----------------|
| Nuclear | 2,200 MW | Baseload, zero emissions, low variable cost |
| Natural Gas | 2,000 MW | Dispatchable, moderate emissions |
| Coal | 1,500 MW | Baseload, high emissions (being phased out) |
| Solar | 1,000 MW | Intermittent, zero emissions |
| Wind | 2,850 MW | Intermittent, zero emissions |
| Hydro | 1,800 MW | Dispatchable, seasonal |
| Battery | 1,550 MWh | Fast response, 4hr duration |

### ASP Solver

TesseraiDB uses Clingo, the state-of-the-art ASP solver, for declarative problem solving:

- Handles millions of variables
- Supports optimization (finding best solutions)
- Provides all solutions or optimal ones
- Runs in milliseconds for typical grid problems

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
