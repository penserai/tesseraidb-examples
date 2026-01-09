# Cascading Failure Analysis Example

A sophisticated infrastructure dependency modeling system that demonstrates TesserAI DB's unique graph-based capabilities for analyzing how failures propagate through complex systems. This example showcases features that differentiate TesserAI from Neo4j and Neptune.

## Overview

This example models critical infrastructure with complex interdependencies: power grids, data centers, manufacturing plants, and supply chains. It simulates how a single point of failure can cascade through the dependency graph, enabling proactive risk mitigation.

### Key Features

- **Multi-Domain Infrastructure**: Power grid, data center, manufacturing, and supply chain systems
- **Dependency Graph Modeling**: Complex relationships with propagation delays and failure probabilities
- **Discrete-Event Simulation**: Realistic failure propagation using priority queues
- **Vulnerability Analysis**: Automatic SPOF detection and blast radius calculation
- **Critical Path Analysis**: Identify the most impactful failure sequences
- **What-If Scenarios**: Simulate specific failure scenarios (power outage, cooling failure, etc.)

## Why TesserAI?

This example demonstrates capabilities that set TesserAI apart:

| Feature | TesserAI | Neo4j | Neptune |
|---------|----------|-------|---------|
| Semantic Relationships | Native ontology support | Labels only | Labels only |
| Temporal Propagation | Built-in event simulation | Manual implementation | Manual implementation |
| Multi-Domain Integration | Unified graph model | Separate databases | Separate databases |
| Real-Time Analysis | Streaming with SSE | Polling required | Polling required |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Infrastructure Model                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    powerSupply    ┌─────────────┐    cooling    ┌───────┐ │
│  │ Power Grid  │ ─────────────────►│ Data Center │ ────────────► │ Racks │ │
│  └─────────────┘                   └─────────────┘               └───────┘ │
│        │                                  │                          │      │
│        │ backupPower                      │ networkLink              │      │
│        ▼                                  ▼                          ▼      │
│  ┌─────────────┐                   ┌─────────────┐            ┌──────────┐ │
│  │ UPS Systems │                   │  Services   │            │ Servers  │ │
│  └─────────────┘                   └─────────────┘            └──────────┘ │
│                                          │                                  │
│                                          │ dataFlow                         │
│                                          ▼                                  │
│                                   ┌─────────────┐                          │
│                                   │ Manufacturing│                         │
│                                   └─────────────┘                          │
│                                          │                                  │
│                                          │ supplyChain                      │
│                                          ▼                                  │
│                                   ┌─────────────┐                          │
│                                   │  Customers  │                          │
│                                   └─────────────┘                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `seed.py` | Creates infrastructure components and dependency relationships |
| `simulation.py` | Runs discrete-event failure cascade simulations |
| `analysis.py` | Performs vulnerability analysis, SPOF detection, blast radius |
| `visualize.py` | ASCII visualization of dependency trees and layer diagrams |

## Quick Start

### Prerequisites

```bash
# Ensure TesserAI DB server is running
cd /path/to/tesseraidb
cargo run

# Install Python dependencies
pip install dtaas requests
```

### Step 1: Seed Infrastructure Data

```bash
cd tesseraidb/examples
python -m cascading_failure.seed

# Options:
#   --base-url URL    DTaaS server URL (default: http://localhost:8080)
```

Expected output:
```
Creating infrastructure for cascading failure analysis...

Creating Power Grid infrastructure...
  Created power-grid-main (PowerGrid)
  Created substation-north (Substation)
  Created substation-south (Substation)
  Created generator-backup-1 (BackupGenerator)
  Created ups-datacenter-1 (UPS)
  ...

Creating Data Center infrastructure...
  Created datacenter-primary (DataCenter)
  Created cooling-chiller-1 (CoolingUnit)
  Created rack-zone-a-1 (ServerRack)
  Created server-app-1 (Server)
  ...

Creating Manufacturing Plant...
  Created mfg-plant-main (ManufacturingPlant)
  Created assembly-line-1 (AssemblyLine)
  Created robot-arm-1 (RoboticArm)
  ...

Creating Supply Chain...
  Created supplier-components (Supplier)
  Created warehouse-main (Warehouse)
  Created logistics-fleet (LogisticsProvider)
  ...

Creating dependency relationships...
  Created 156 dependency relationships

Summary:
  Components created: 87
  Dependencies created: 156
  Domains: power_grid, data_center, manufacturing, supply_chain
```

### Step 2: Run Failure Simulation

```bash
python -m cascading_failure.simulation

# Options:
#   --base-url URL        DTaaS server URL
#   --scenario SCENARIO   Predefined scenario to run
#   --source COMPONENT    Component ID to fail (for custom scenarios)
#   --duration SECONDS    Simulation duration (default: 300)
```

Available scenarios:
- `power-outage`: Main power grid failure
- `datacenter-power`: Data center power feed failure
- `cooling-failure`: Cooling system cascade
- `network-partition`: Network connectivity loss

Example:
```bash
python -m cascading_failure.simulation --scenario power-outage
```

Output:
```
╔════════════════════════════════════════════════════════════════════╗
║               CASCADING FAILURE SIMULATION                        ║
╠════════════════════════════════════════════════════════════════════╣
║  Scenario: power-outage                                           ║
║  Initial Failure: power-grid-main                                 ║
║  Simulation Start: 2024-01-15 14:45:00                           ║
╚════════════════════════════════════════════════════════════════════╝

 FAILURE PROPAGATION TIMELINE
─────────────────────────────────────────────────────────────────────
 T+0.0s    power-grid-main           FAILED    (initial trigger)
 T+0.0s    ├─► substation-north      FAILED    (powerSupply, 100%)
 T+0.0s    ├─► substation-south      FAILED    (powerSupply, 100%)
 T+30.0s   │   └─► ups-datacenter-1  DEGRADED  (backupPower, 80%)
 T+30.0s   │   └─► ups-datacenter-2  DEGRADED  (backupPower, 80%)
 T+45.0s   ├─► datacenter-primary    FAILED    (powerSupply, 100%)
 T+45.0s   │   ├─► cooling-chiller-1 FAILED    (powerSupply, 100%)
 T+60.0s   │   │   └─► rack-zone-a-1 OVERHEATING (cooling, 95%)
 T+60.0s   │   │   └─► rack-zone-a-2 OVERHEATING (cooling, 95%)
 T+90.0s   │   │       └─► server-*  SHUTDOWN  (thermal protection)
 ...

 IMPACT SUMMARY
─────────────────────────────────────────────────────────────────────
 Total Components Affected: 67 / 87 (77%)

 By Domain:
   Power Grid:      12/15 (80%) affected
   Data Center:     34/38 (89%) affected
   Manufacturing:   15/20 (75%) affected
   Supply Chain:     6/14 (43%) affected

 By Severity:
   FAILED:          23 components
   DEGRADED:        31 components
   OVERHEATING:      8 components
   ISOLATED:         5 components

 Estimated Recovery Time: 4.5 hours
```

### Step 3: Vulnerability Analysis

```bash
python -m cascading_failure.analysis

# Options:
#   --base-url URL        DTaaS server URL
#   --depth N             Maximum dependency depth to analyze (default: 5)
```

Output:
```
╔════════════════════════════════════════════════════════════════════╗
║               INFRASTRUCTURE VULNERABILITY ANALYSIS               ║
╠════════════════════════════════════════════════════════════════════╣
║  Analysis Time: 2024-01-15 14:50:00                               ║
║  Components Analyzed: 87                                           ║
║  Dependencies Analyzed: 156                                        ║
╚════════════════════════════════════════════════════════════════════╝

 SINGLE POINTS OF FAILURE (SPOF)
─────────────────────────────────────────────────────────────────────
 Component              Type              Blast Radius    Risk Score
─────────────────────────────────────────────────────────────────────
 power-grid-main        PowerGrid         67 (77%)        CRITICAL
 datacenter-primary     DataCenter        45 (52%)        CRITICAL
 cooling-chiller-1      CoolingUnit       28 (32%)        HIGH
 network-core-switch    NetworkSwitch     34 (39%)        HIGH
 mfg-plant-main         ManufacturingPlant 15 (17%)       MEDIUM

 DEPENDENCY DEPTH ANALYSIS
─────────────────────────────────────────────────────────────────────
 Depth    Components    Avg Dependencies    Max Chain Length
─────────────────────────────────────────────────────────────────────
 0        5             0.0                 -
 1        18            1.2                 1
 2        31            2.4                 2
 3        22            3.1                 3
 4        8             4.2                 4
 5+       3             5.7                 7

 CRITICAL PATHS
─────────────────────────────────────────────────────────────────────
 Path                                           Impact Score
─────────────────────────────────────────────────────────────────────
 power-grid → datacenter → services → customers     0.92
 cooling → racks → servers → applications           0.87
 network-core → api-gateway → all-services          0.85

 REDUNDANCY ANALYSIS
─────────────────────────────────────────────────────────────────────
 Component              Required    Available    Redundancy
─────────────────────────────────────────────────────────────────────
 Power Supply           1           2            OK (N+1)
 Cooling Units          2           3            OK (N+1)
 Network Paths          2           2            WARNING (N+0)
 Database Replicas      3           2            CRITICAL (N-1)

 RECOMMENDATIONS
─────────────────────────────────────────────────────────────────────
 Priority    Recommendation
─────────────────────────────────────────────────────────────────────
 CRITICAL    Add redundant database replica to meet N+1 requirement
 HIGH        Add secondary network path to network-core-switch
 MEDIUM      Consider geographic distribution for power-grid-main
 LOW         Increase UPS capacity from 30min to 60min
```

### Step 4: Visualize Dependencies

```bash
python -m cascading_failure.visualize

# Options:
#   --base-url URL    DTaaS server URL
#   --component ID    Root component for tree view
#   --depth N         Maximum depth to show (default: 4)
#   --mode MODE       Visualization mode: tree, layers, matrix
```

Tree visualization:
```
python -m cascading_failure.visualize --component power-grid-main --mode tree
```

Output:
```
 DEPENDENCY TREE: power-grid-main
═══════════════════════════════════════════════════════════════════════════

power-grid-main [PowerGrid]
├── substation-north [Substation] ─── powerSupply (delay: 0s, prob: 100%)
│   ├── transformer-n1 [Transformer]
│   │   └── datacenter-primary [DataCenter]
│   │       ├── cooling-chiller-1 [CoolingUnit]
│   │       │   ├── rack-zone-a-1 [ServerRack]
│   │       │   │   ├── server-app-1 [Server]
│   │       │   │   └── server-app-2 [Server]
│   │       │   └── rack-zone-a-2 [ServerRack]
│   │       │       └── server-db-1 [Server]
│   │       ├── cooling-chiller-2 [CoolingUnit]
│   │       │   └── rack-zone-b-1 [ServerRack]
│   │       └── network-core-switch [NetworkSwitch]
│   │           ├── network-access-1 [NetworkSwitch]
│   │           └── network-access-2 [NetworkSwitch]
│   └── ups-datacenter-1 [UPS] ─── backupPower (delay: 30s, prob: 80%)
└── substation-south [Substation] ─── powerSupply (delay: 0s, prob: 100%)
    └── mfg-plant-main [ManufacturingPlant]
        ├── assembly-line-1 [AssemblyLine]
        └── assembly-line-2 [AssemblyLine]

 Legend: ─── powerSupply  ─·─ backupPower  ═══ cooling  ~~~ networkLink
```

Layer visualization:
```
python -m cascading_failure.visualize --mode layers
```

Output:
```
 INFRASTRUCTURE LAYERS
═══════════════════════════════════════════════════════════════════════════

 Layer 0: Foundation (no dependencies)
 ┌────────────────────────────────────────────────────────────────────────┐
 │ power-grid-main   generator-backup-1   supplier-components           │
 │ [PowerGrid]       [BackupGenerator]    [Supplier]                     │
 └────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
 Layer 1: Primary Infrastructure
 ┌────────────────────────────────────────────────────────────────────────┐
 │ substation-north  substation-south  warehouse-main  logistics-fleet  │
 │ [Substation]      [Substation]      [Warehouse]     [Logistics]       │
 └────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
 Layer 2: Core Services
 ┌────────────────────────────────────────────────────────────────────────┐
 │ datacenter-primary  mfg-plant-main  network-core-switch              │
 │ [DataCenter]        [Manufacturing] [NetworkSwitch]                   │
 └────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
 Layer 3: Operational
 ┌────────────────────────────────────────────────────────────────────────┐
 │ cooling-*  rack-*  assembly-line-*  api-gateway  database-primary    │
 └────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
 Layer 4: Edge Services
 ┌────────────────────────────────────────────────────────────────────────┐
 │ server-app-*  server-db-*  robot-arm-*  service-*                    │
 └────────────────────────────────────────────────────────────────────────┘
```

## Dependency Types

| Type | Propagation Delay | Failure Probability | Description |
|------|-------------------|---------------------|-------------|
| `powerSupply` | 0s | 100% | Immediate failure on power loss |
| `backupPower` | 30s | 80% | Battery backup with limited duration |
| `cooling` | 300s | 95% | Thermal issues after cooling loss |
| `networkLink` | 0s | 100% | Network connectivity dependency |
| `dataFlow` | 60s | 90% | Data processing dependency |
| `supplyChain` | 86400s | 60% | Inventory buffer delays impact |
| `processControl` | 5s | 95% | Manufacturing control systems |
| `humanOperator` | 900s | 30% | Manual intervention possible |

## Scenarios

### Power Outage
Simulates main grid failure affecting all dependent infrastructure.

```bash
python -m cascading_failure.simulation --scenario power-outage
```

### Data Center Power
Simulates localized power failure in the data center.

```bash
python -m cascading_failure.simulation --scenario datacenter-power
```

### Cooling Failure
Simulates primary cooling system failure leading to thermal cascade.

```bash
python -m cascading_failure.simulation --scenario cooling-failure
```

### Network Partition
Simulates core network switch failure isolating services.

```bash
python -m cascading_failure.simulation --scenario network-partition
```

### Custom Scenario
Inject failure into any component:

```bash
python -m cascading_failure.simulation --source cooling-chiller-1
```

## Integration with TesserAI DB

This example demonstrates advanced DTaaS features:

1. **Semantic Relationships**: Typed dependencies with rich metadata
2. **Graph Traversal**: BFS-based propagation through dependency chains
3. **Temporal Modeling**: Propagation delays and duration tracking
4. **Property Updates**: Real-time status changes during simulation
5. **Event Streaming**: Subscribe to failure events via SSE
6. **SPARQL Queries**: Complex dependency analysis queries

### Example SPARQL Query

Find all components affected by a specific failure:

```sparql
PREFIX cascade: <http://tesserai.dev/ontology/cascading_failure#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?affected ?type ?depth WHERE {
  ?source a cascade:PowerGrid .
  ?source cascade:dependsOn* ?affected .
  ?affected rdf:type ?type .

  # Calculate depth
  {
    SELECT ?affected (COUNT(?mid) as ?depth) WHERE {
      ?source cascade:dependsOn* ?mid .
      ?mid cascade:dependsOn* ?affected .
    } GROUP BY ?affected
  }
}
ORDER BY ?depth
```

## Customization

### Adding New Infrastructure

Edit `seed.py` to add new components:

```python
# Define new component type
NEW_COMPONENTS = [
    {
        "id": "new-component-1",
        "name": "New Component",
        "type": "NewType",
        "properties": {
            "capacity": 100,
            "redundancy": "N+1",
        }
    }
]

# Add dependencies
NEW_DEPENDENCIES = [
    {
        "source": "new-component-1",
        "target": "existing-component",
        "type": "powerSupply",
    }
]
```

### Modifying Propagation Rules

Edit `simulation.py` to adjust failure behavior:

```python
DEPENDENCY_TYPES = {
    "myDependency": {
        "propagation_delay": 60,      # Seconds before failure propagates
        "failure_probability": 0.85,   # Chance of downstream failure
        "severity_multiplier": 0.9,    # Severity reduction factor
    }
}
```

## Troubleshooting

**"No components found"**
```
Run seed.py first to create infrastructure twins
```

**"Simulation completes instantly"**
```
Check that dependencies are correctly created with seed.py
Use --scenario to test with predefined failure points
```

**"Analysis shows no SPOFs"**
```
Ensure dependency relationships exist (check with visualize.py)
Increase --depth parameter for deeper analysis
```
