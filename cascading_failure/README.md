# Cascading Failure Analysis Example

A sophisticated infrastructure dependency modeling system demonstrating TesseraiDB's graph-based capabilities for analyzing how failures propagate through complex systems.

## Overview

- What this domain models: Critical infrastructure with complex interdependencies including power grids, data centers, manufacturing plants, and supply chains
- Key entities and relationships: Infrastructure components connected via typed dependencies (powerSupply, backupPower, cooling, networkLink, dataFlow)
- Real-world use cases: Failure cascade simulation, single point of failure detection, blast radius calculation, infrastructure resilience planning

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

- **PowerGrid**: Main power grid infrastructure
- **Substation**: Power substations with capacity and load
- **BackupGenerator**: Emergency backup power sources
- **UPS**: Uninterruptible power supply units
- **DataCenter**: Data center facilities with cooling and network
- **CoolingUnit**: Cooling systems (chillers, HVAC)
- **ServerRack**: Server rack enclosures
- **Server**: Individual servers with thermal monitoring
- **NetworkSwitch**: Network infrastructure components
- **ManufacturingPlant**: Manufacturing facilities
- **AssemblyLine**: Production assembly lines
- **Supplier**: Supply chain suppliers
- **Warehouse**: Storage and logistics facilities

## Ontology

The cascading failure ontology defines:

- **Dependency types**: powerSupply (100% propagation), backupPower (80% with 30s delay), cooling (95% with 300s delay), networkLink (100%)
- **Component states**: operational, failed, degraded, overheating, isolated
- **Impact metrics**: Blast radius, failure probability, propagation delay

## Web Dashboard

The `web_ui.py` provides visualization of:

- Infrastructure dependency graph
- Real-time failure propagation simulation
- SPOF (Single Point of Failure) analysis
- Impact assessment for what-if scenarios

Start the dashboard to interact with failure simulations and view dependency visualizations.

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all power grid components
components = client.twins.list(type_filter="PowerGrid")

# Find components affected by a specific failure
affected = client.sparql.query("""
    PREFIX cascade: <http://tesserai.io/ontology/cascading_failure#>
    SELECT ?affected ?type ?depth WHERE {
        ?source a cascade:PowerGrid .
        ?source cascade:dependsOn* ?affected .
        ?affected a ?type .
    }
""")

# Analyze blast radius of a component
lineage = client.lineage.get_downstream("power-grid-main", max_depth=5)

# Update component status during simulation
client.twins.update("datacenter-primary", properties={
    "status": "degraded",
    "powerSource": "backup"
})
```

## Additional Features

### Dependency Types

| Type | Propagation Delay | Failure Probability | Description |
|------|-------------------|---------------------|-------------|
| powerSupply | 0s | 100% | Immediate failure on power loss |
| backupPower | 30s | 80% | Battery backup with limited duration |
| cooling | 300s | 95% | Thermal issues after cooling loss |
| networkLink | 0s | 100% | Network connectivity dependency |
| dataFlow | 60s | 90% | Data processing dependency |
| supplyChain | 86400s | 60% | Inventory buffer delays impact |

### Failure Scenarios

- **Power Outage**: Main grid failure affecting all dependent infrastructure
- **Datacenter Power**: Localized power failure in the data center
- **Cooling Failure**: Primary cooling system failure leading to thermal cascade
- **Network Partition**: Core network switch failure isolating services

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
