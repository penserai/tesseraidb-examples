
This folder contains comprehensive sample digital twins across various domains of human knowledge. Each example demonstrates how to use the DTaaS platform to model complex real-world systems with entities, relationships, sensors, and rich metadata.

## Python Setup

### Required Python Version

**Python 3.10 or higher** is required. We recommend **Python 3.11** or **3.12** for best performance.

Check your Python version:
```bash
python --version
# or
python3 --version
```

### Setting Up a Virtual Environment

We strongly recommend using a virtual environment to isolate dependencies.

#### Option 1: Using `venv` (built-in)

```bash
# Navigate to the project root
cd /path/to/tesseraidb

# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate

# Verify you're in the virtual environment
which python  # Should show .venv/bin/python
```

#### Option 2: Using `conda`

```bash
# Create a new conda environment
conda create -n dtaas python=3.11

# Activate the environment
conda activate dtaas
```

#### Option 3: Using `pyenv` + `pyenv-virtualenv`

```bash
# Install Python 3.11 if not already installed
pyenv install 3.11

# Create a virtual environment
pyenv virtualenv 3.11 dtaas

# Activate it
pyenv activate dtaas

# Or set it as local for this directory
pyenv local dtaas
```

#### Option 4: Using Homebrew (macOS)

```bash
# Install Python 3.12 via Homebrew
brew install python@3.12

# Verify installation
/opt/homebrew/bin/python3.12 --version  # Apple Silicon
# or
/usr/local/bin/python3.12 --version     # Intel Mac

# Create a virtual environment using Homebrew's Python
/opt/homebrew/bin/python3.12 -m venv .venv  # Apple Silicon
# or
/usr/local/bin/python3.12 -m venv .venv     # Intel Mac

# Activate the virtual environment
source .venv/bin/activate

# Verify you're using the correct Python
which python   # Should show .venv/bin/python
python --version  # Should show 3.12.x
```

> **Tip**: You can also add Homebrew's Python to your PATH in `~/.zshrc` or `~/.bash_profile`:
> ```bash
> # For Apple Silicon Macs
> export PATH="/opt/homebrew/bin:$PATH"
>
> # For Intel Macs
> export PATH="/usr/local/bin:$PATH"
> ```

### Installing Dependencies

Once your virtual environment is activated:

```bash
# IMPORTANT: First upgrade pip to support modern pyproject.toml builds
pip install --upgrade pip

# Install the DTaaS Python SDK in development mode
pip install -e sdks/python

# Or install without editable mode (works with any pip version)
pip install sdks/python
```

> **Note**: Editable mode (`-e`) requires pip 21.3 or higher. If you get an error about
> `setup.py` not found, upgrade pip first with `pip install --upgrade pip`.

### Verifying the Installation

```bash
# Test that the SDK is installed correctly
python -c "from dtaas import DTaaSClient; print('DTaaS SDK installed successfully!')"
```

## Prerequisites

1. **Start the DTaaS server** on localhost:8080:
   ```bash
   cd /path/to/tesseraidb
   cargo run
   ```

2. **Ensure Python SDK is installed** (see Python Setup above):
   ```bash
   # With virtual environment activated
   pip install --upgrade pip  # Required for editable installs
   pip install -e sdks/python
   ```

3. **Set environment variables** (optional):
   ```bash
    
   export DTAAS_TOKEN="your-api-token"
   ```

## Available Examples

| Domain | Folder | Description | Twins | Relationships |
|--------|--------|-------------|-------|---------------|
| **Smart Building** | `smart_building/` | Office building with HVAC, sensors, access control + **RSP demo** | ~180 | ~250 |
| **Manufacturing** | `manufacturing/` | Industry 4.0 factory with CNC, robots, QC | ~120 | ~180 |
| **Healthcare** | `healthcare/` | Hospital with medical equipment, patient monitoring | ~200 | ~280 |
| **Supply Chain** | `supply_chain/` | Global logistics with warehouses, trucks, ships | ~150 | ~220 |
| **Smart City** | `smart_city/` | Urban infrastructure, transit, utilities | ~200 | ~300 |
| **Robotics** | `robotics/` | Automated fulfillment center with AMRs | ~400 | ~500 |
| **Robot Simulation** | `robotics/robot_simulation.py` | Ontology-driven robot with sense-reason-act loop | 1 twin | Dynamic |
| **Energy Grid** | `energy_grid/` | Power grid with renewables, storage, distribution | ~150 | ~200 |
| **Automotive** | `automotive/` | Fleet management with EVs, telematics | ~500 | ~700 |
| **Agriculture** | `agriculture/` | Precision farming with sensors, drones, tractors | ~100 | ~150 |
| **Aerospace** | `aerospace/` | Satellite constellation with ground stations | ~600 | ~800 |

## Advanced Examples (Production-Grade)

These advanced examples demonstrate enterprise-ready features with realistic simulations, live dashboards, and comprehensive documentation.

| Domain | Folder | Description | Key Features |
|--------|--------|-------------|--------------|
| **Predictive Maintenance** | `predictive_maintenance/` | Industrial equipment health monitoring | Weibull failure modeling, FMEA analysis, RUL prediction |
| **Cascading Failure Analysis** | `cascading_failure/` | Infrastructure dependency modeling | SPOF detection, blast radius, failure propagation |
| **Real-Time Alerting** | `alerting_system/` | Production alerting with lifecycle | Configurable rules, escalation policies, chaos engineering |

### Predictive Maintenance

Models industrial equipment (pumps, motors, bearings, gearboxes, compressors) with realistic failure patterns using Weibull distribution and FMEA-based risk analysis.

```bash
# Setup and run
python -m predictive_maintenance.seed           # Create equipment twins
python -m predictive_maintenance.simulation     # Run degradation simulation
python -m predictive_maintenance.analysis       # Analyze equipment health
python -m predictive_maintenance.dashboard      # Live monitoring dashboard
```

**Features:**
- Weibull-based Remaining Useful Life (RUL) estimation
- FMEA Risk Priority Number (RPN) calculation
- Sensor data with realistic noise and drift
- Maintenance scheduling recommendations

See [`predictive_maintenance/README.md`](predictive_maintenance/README.md) for full documentation.

### Cascading Failure Analysis

Models complex infrastructure (power grids, data centers, manufacturing plants, supply chains) with dependency relationships to analyze how failures propagate.

```bash
# Setup and run
python -m cascading_failure.seed                           # Create infrastructure
python -m cascading_failure.simulation --scenario power-outage  # Run failure cascade
python -m cascading_failure.analysis                       # Vulnerability analysis
python -m cascading_failure.visualize --mode tree          # Visualize dependencies
```

**Features:**
- Discrete-event failure propagation simulation
- Single Point of Failure (SPOF) detection
- Blast radius calculation
- Critical path analysis
- Predefined scenarios: power-outage, datacenter-power, cooling-failure, network-partition

See [`cascading_failure/README.md`](cascading_failure/README.md) for full documentation.

### Real-Time Alerting System

Production-grade alerting with configurable rules, multi-severity classification, and notification channels.

```bash
# Setup and run
python -m alerting_system.seed                   # Create systems and rules
python -m alerting_system.simulator --chaos      # Generate metrics with anomalies
python -m alerting_system.monitor               # Run alert detection
python -m alerting_system.dashboard             # Live alert dashboard
```

**Features:**
- Threshold-based alert rules with duration requirements
- Alert lifecycle: open, acknowledged, resolved
- Escalation policies with time-based triggers
- Chaos engineering mode for random anomaly injection
- Real-time terminal dashboard

See [`alerting_system/README.md`](alerting_system/README.md) for full documentation.

## Reasoning Examples

DTaaS includes OWL 2 RL semantic reasoning capabilities demonstrated by these scripts:

| Script | Description |
|--------|-------------|
| `reasoning_demo.py` | Comprehensive 7-section demo of all reasoning capabilities |
| `domain_rules.py` | Domain-specific threshold rules for all 10 domains |
| `ontologies/reasoning_axioms.ttl` | Extended ontology with OWL 2 RL axioms |

### Running Reasoning Examples

```bash
# First, load ontologies (including reasoning axioms)
python examples/load_ontologies.py

# Seed example data
python examples/seed_all.py

# Run the comprehensive reasoning demo
python examples/reasoning_demo.py

# Or run specific sections
python examples/reasoning_demo.py --section 1  # Basic materialization
python examples/reasoning_demo.py --section 2  # Custom rules
python examples/reasoning_demo.py --section 3  # SWRL rules
python examples/reasoning_demo.py --section 4  # Explanation API
python examples/reasoning_demo.py --section 5  # Consistency checking
python examples/reasoning_demo.py --section 6  # Rule conflicts
python examples/reasoning_demo.py --section 7  # Batch reasoning

# Create domain-specific rules
python examples/domain_rules.py                    # Create all rules
python examples/domain_rules.py --domain automotive  # Specific domain
python examples/domain_rules.py --list              # List all rules
python examples/domain_rules.py --execute --domain automotive  # Execute rules
```

### Reasoning Demo Sections

1. **Basic Materialization** - OWL 2 RL inference (subClassOf, subPropertyOf, inverseOf)
2. **Custom Rules** - Threshold-based classification rules
3. **SWRL Rules** - Semantic Web Rule Language style rules
4. **Explanation API** - Understanding why inferences were made
5. **Consistency Checking** - Detecting logical contradictions
6. **Conflict Detection** - Analyzing rules for conflicts
7. **Batch Reasoning** - Processing multiple domains efficiently

### Domain Rules

The `domain_rules.py` script includes 18 predefined threshold rules across 8 domains:

| Domain | Rules | Examples |
|--------|-------|----------|
| Automotive | 3 | Low battery, high mileage, low fuel alerts |
| Smart Building | 3 | Overheated zones, poor air quality, high energy consumption |
| Energy Grid | 2 | Overloaded transformers, low voltage nodes |
| Healthcare | 2 | Critical battery devices, calibration overdue |
| Robotics | 2 | Error state robots, low battery robots |
| Supply Chain | 2 | Low stock items, delayed shipments |
| Agriculture | 2 | Dry soil, low nutrients |
| Aerospace | 2 | Low fuel aircraft, maintenance due |

## Robot Simulation Example

The `robotics/robot_simulation.py` example demonstrates how to build an **ontology-driven autonomous robot** using the sense-reason-act paradigm. This is a complete working simulation where all robot decisions are made through semantic reasoning.

### Concept

```
┌─────────────────────────────────────────────────────────────────┐
│                    SENSE-REASON-ACT LOOP                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐  │
│   │  SENSE  │────▶│  REASON │────▶│  QUERY  │────▶│   ACT   │  │
│   └─────────┘     └─────────┘     └─────────┘     └─────────┘  │
│        │               │               │               │        │
│        ▼               ▼               ▼               ▼        │
│   Update RDF      Fire SWRL      Query state     Execute       │
│   with sensor     rules to       via SPARQL     action in      │
│   readings        infer next                     world         │
│                   action                                       │
│                                                                 │
│   The ontology is the robot's "brain memory"                   │
│   SWRL rules are the robot's "decision logic"                  │
│   SPARQL queries are how the robot "sees" its state            │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

1. **Ontology** (`ontologies/robot_simulation.ttl`)
   - OWL 2 classes: `Robot`, `CollectibleObject`, `Obstacle`, `Location`, `Action`
   - State classes: `ActiveRobot`, `CollisionState`, `NearObject`, `AtObject`, `LowBattery`
   - Data properties: `positionX`, `positionY`, `batteryLevel`, `successMetric`
   - SHACL shapes for validation

2. **Reasoning Rules**
   - `collision-stop`: Robot in collision → Stop immediately
   - `low-battery`: Battery < 20% → Return to home
   - `near-object`: Distance to object < sensor range → Navigate toward it
   - `at-object`: Distance < 0.5 → Can collect the object
   - `near-obstacle`: Distance to obstacle < 1.5 → Activate avoidance

3. **Simulation World**
   - 20x20 grid with random objects and obstacles
   - Robot starts at center with 100% battery
   - Objects have random values (points when collected)
   - Obstacles block movement and cause collisions

### Running the Simulation

```bash
# Run with default settings (50 ticks, visualization enabled)
python examples/robotics/robot_simulation.py

# Run for more ticks
python examples/robotics/robot_simulation.py --ticks 100

# Disable ASCII visualization
python examples/robotics/robot_simulation.py --no-visualize

# Use custom server URL
python examples/robotics/robot_simulation.py --base-url http://localhost:9000
```

### Sample Output

```
+===========================================================================+
|           Robot Simulation with Ontology-Driven Reasoning                 |
+===========================================================================+

[SETUP] World: 20x20 grid
[SETUP] Objects: 8
[SETUP] Obstacles: 4
[SETUP] Robot starts at: (10.0, 10.0)

[PHASE 0] Initialization
[ONTOLOGY] Loaded robot_simulation ontology
[TWIN] Initialized twin 'robot-simulation' with world state
[RULES] Setting up reasoning rules...
  [OK] robo-collision-stop: Collision Stop Rule
  [OK] robo-low-battery: Low Battery Rule
  [OK] robo-near-object: Near Object Rule
  ...

============================================================
 TICK 1
============================================================
 Robot Position: (10.3, 10.8)
 Battery: 99.8%
 Current Action: Moving to (12.5, 14.2)
 Objects: 0/8 collected
 Score: 0.0

  World Map (R=Robot, O=Object, #=Obstacle, H=Home)
  ------------
  |..O.......|
  |.....O....|
  |....R.....|
  |..#....O..|
  |.....H....|
  ------------
```

### How It Works

1. **Initialization**: Creates a digital twin representing the robot and world state as RDF triples
2. **Each Tick**:
   - **SENSE**: Updates ontology with current sensor readings (position, battery, distances)
   - **REASON**: Fires SWRL-style rules to classify the robot's state
   - **QUERY**: Uses SPARQL to retrieve the inferred state and recommended action
   - **ACT**: Executes the action (move, collect, avoid, stop)
3. **Completion**: Ends when all objects collected, robot stopped, or tick limit reached

This example showcases how semantic reasoning can replace traditional if-else logic with declarative rules, making robot behavior more maintainable, explainable, and adaptable.

## RDF Stream Processing (RSP) Examples

TesseraiDB supports real-time monitoring through RDF Stream Processing (RSP) with continuous SPARQL queries over streaming data.

### Smart Building RSP Demo

The `smart_building/rsp_demo.py` script demonstrates:

- **Stream Sources**: Capturing sensor updates from the EventBus
- **Continuous Queries**: Real-time alerts for temperature, CO2, occupancy, and humidity
- **Sliding Windows**: Time-based and tumbling window configurations
- **Python SDK Usage**: Full RSP API demonstration

```bash
# First, seed the smart building data
python examples/smart_building/seed.py

# Run the RSP demo (shows current status)
python examples/smart_building/rsp_demo.py

# Run with sensor simulation (generates events)
python examples/smart_building/rsp_demo.py --simulate --duration 60

# Clean up after demo
python examples/smart_building/rsp_demo.py --simulate --cleanup
```

### RSP Python SDK Usage

```python
from dtaas import DTaaSClient
from dtaas.models import WindowConfig, WindowType, OutputConfig, ContinuousQueryCreate

client = DTaaSClient("http://localhost:8080")

# Create a stream source for sensor updates
source = client.rsp.create_source(
    name="sensor-stream",
    config={
        "type": "event_bus",
        "twin_id_patterns": ["sensor-*"],
        "event_types": ["twin.updated"],
    }
)
client.rsp.start_source(source.id)

# Create a continuous query with a 5-minute sliding window
query = client.rsp.create_query(
    ContinuousQueryCreate(
        name="High Temperature Alert",
        sparql="SELECT ?sensor ?temp WHERE { ?sensor <temp> ?temp . FILTER(?temp > 26) }",
        window=WindowConfig(
            type=WindowType.TIME_BASED,
            duration_seconds=300,
            slide_seconds=60,
        ),
        stream_sources=[source.id],
        output=OutputConfig(push_to_event_bus=True),
    )
)

# Activate and get results
client.rsp.activate_query(query.id)
results = client.rsp.get_query_results(query.id, limit=10)

# Get RSP statistics
stats = client.rsp.get_stats()
print(f"Active queries: {stats.active_queries}")
```

## Running Individual Examples

Each example can be run independently:

```bash
# Smart Building
python examples/smart_building/seed.py
python examples/smart_building/rsp_demo.py  # RSP real-time monitoring

# Manufacturing
python examples/manufacturing/seed.py

# Healthcare
python examples/healthcare/seed.py

# Supply Chain
python examples/supply_chain/seed.py

# Smart City
python examples/smart_city/seed.py

# Robotics / Warehouse Automation
python examples/robotics/seed.py

# Robot Simulation (Ontology-Driven)
python examples/robotics/robot_simulation.py

# Energy Grid
python examples/energy_grid/seed.py

# Automotive / Fleet Management
python examples/automotive/seed.py

# Agriculture / Smart Farm
python examples/agriculture/seed.py

# Aerospace / Satellites
python examples/aerospace/seed.py
```

## Running All Examples

To seed all examples at once:

```bash
python examples/seed_all.py
```

You will see:

```
============================================================
 SEEDING COMPLETE - SUMMARY
============================================================

Domain                         Twins    Relations       Time
------------------------------------------------------------
smart_building                   105          149       0.2s
manufacturing                     71           75       0.2s
healthcare                       146          133       0.3s
supply_chain                      80          102       0.2s
smart_city                       101          109       0.2s
robotics                         296          302       0.8s
energy_grid                       68           60       0.2s
automotive                       548          597       1.6s
agriculture                       90           99       0.3s
aerospace                        680          822       2.2s
------------------------------------------------------------
TOTAL                           2185         2448       6.2s
============================================================

All domains seeded successfully!
```

Or run specific examples:

```bash
python examples/seed_all.py --domains smart_building,manufacturing,healthcare
```

## Example Structure

Each example follows the same pattern:

```
examples/
├── common.py                 # Shared utilities and client initialization
├── seed_all.py              # Master script to run all examples
├── README.md                # This file
│
├── smart_building/
│   └── seed.py              # Smart building digital twin
│
├── manufacturing/
│   └── seed.py              # Manufacturing digital twin
│
├── healthcare/
│   └── seed.py              # Healthcare digital twin
│
└── ... (other domains)
```

## Domain Details

### Smart Building / IoT
Models a modern office building with:
- 10-floor building hierarchy
- HVAC system (plant, AHUs, VAV boxes)
- Temperature, CO2, humidity, and occupancy sensors
- Lighting zones and controllers
- Electrical distribution and power meters
- Elevators, fire safety, access control
- Water metering

### Manufacturing / Industry 4.0
Models a precision manufacturing facility with:
- Production areas and lines
- CNC machines with spindle sensors
- Industrial robots (KUKA, Fanuc, ABB)
- Conveyor systems
- Quality control equipment (CMM, vision, X-ray)
- Cutting tools with wear tracking
- Work-in-progress tracking
- Maintenance scheduling

### Healthcare / Hospital
Models a Level 1 trauma center with:
- Multiple buildings and departments
- Operating rooms with surgical robots
- Medical imaging (MRI, CT, X-ray, ultrasound)
- ICU with patient monitors and ventilators
- Laboratory equipment
- Pharmacy automation
- Medical gas systems
- Sterilization equipment

### Supply Chain / Logistics
Models a global distribution network with:
- Suppliers across multiple countries
- Warehouses and distribution centers
- Container ships and tracking
- Truck fleet with GPS
- Inventory levels by SKU/location
- Shipment tracking
- Customer relationships

### Smart City
Models urban infrastructure with:
- City districts by type
- Roads and intersections with traffic signals
- Metro lines and stations
- Bus routes and vehicles
- Power grid and substations
- Water treatment and distribution
- Air quality and noise monitoring
- Police and fire stations
- Street lighting
- Parking facilities

### Robotics / Warehouse Automation
Models an automated fulfillment center with:
- 185+ autonomous mobile robots (AMRs)
- Robotic picking and packing arms
- Vision-guided systems
- AS/RS (Automated Storage/Retrieval)
- Conveyor systems
- Charging stations
- Human-robot collaboration workstations
- Fleet management
- Safety systems

### Energy Grid
Models a regional power grid with:
- Conventional power plants (gas, coal, nuclear, hydro)
- Solar and wind farms
- Battery energy storage
- High-voltage substations
- Transmission lines
- Distribution substations
- Smart meters
- EV charging infrastructure
- Demand response resources

### Automotive / Fleet Management
Models a delivery fleet with:
- Electric, hybrid, and conventional vehicles
- Vehicle depots
- Telematics devices
- Driver management
- Charging stations
- Maintenance records
- Delivery routes and trips
- Vehicle sensors (tire, brake, battery)
- Fuel cards

### Agriculture / Smart Farm
Models a precision agriculture operation with:
- Agricultural fields with crop tracking
- Soil sensors at multiple depths
- Weather stations
- Irrigation system with zones
- Agricultural drones (survey, spray)
- Autonomous tractors
- Implements (planter, sprayer, harvester)
- Pest monitoring traps
- Crop health cameras
- Water sources (wells, canals, ponds)

### Aerospace / Satellites
Models a LEO communications constellation with:
- 150 satellites across 6 orbital planes
- Ka-band and Ku-band payloads
- Ground stations (gateway and TT&C)
- Mission control centers
- Satellite subsystems (ADCS, EPS, TCS, etc.)
- Inter-satellite optical links
- Space weather monitoring
- User terminals (consumer, enterprise, maritime, aviation)
- Launch vehicle records

## Querying the Data

After seeding, you can query the data using SPARQL via the `/sparql` endpoint or Swagger UI.

### Using cURL

```bash
# Execute a SPARQL query
curl -X POST -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/sparql-query" \
  -d "SELECT * WHERE { ?s ?p ?o } LIMIT 10" \
  "http://localhost:8080/sparql"
```

### Using the Python SDK

```python
from dtaas import DTaaSClient

client = DTaaSClient("http://localhost:8080", token="your-token")

# Find all sensors using client.query.select()
result = client.query.select("""
    SELECT ?sensor ?type WHERE {
        ?sensor <http://tesserai.io/ontology/type> ?type .
        FILTER(CONTAINS(STR(?type), "Sensor"))
    }
    LIMIT 100
""")

# Access results
for binding in result.bindings:
    print(binding)
```

---

## Example Queries

Below are example queries for each domain showing how to explore the digital twin data.

> **Note**: The DTaaS server uses SPARQL internally but doesn't expose a direct SPARQL endpoint. Use the REST API (`/api/twins`, `/api/twins/{id}/relationships`) or the Python SDK to query data. The SPARQL queries below illustrate the data model and can be used if a SPARQL endpoint is added in the future.

### Using the Python SDK

```python
from dtaas import DTaaSClient

client = DTaaSClient("http://localhost:8080", token="your-token")

# List twins by type
twins = client.twins.list(page_size=100, type_filter="ElectricVehicle")

# Filter in Python
sensors = [t for t in twins if t.type_uri and "Sensor" in t.type_uri]

# Get relationships
rels = client.twins.get_relationships("twin-id")
```

### Conceptual SPARQL Queries

The following SPARQL queries illustrate the data model for each domain:

### Smart Building

**Find all temperature sensors and their readings:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?sensor ?name ?zone ?currentValue WHERE {
  ?sensor dtaas:type "TemperatureSensor" ;
          dtaas:name ?name .
  OPTIONAL {
    ?sensor dtaas:properties ?props .
    ?props dtaas:currentValue ?currentValue .
  }
  OPTIONAL { ?sensor dtaas:locatedIn ?z . ?z dtaas:name ?zone }
}
ORDER BY ?zone
```

**HVAC system overview - all air handling units:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?ahu ?name ?status ?supplyTemp ?returnTemp WHERE {
  ?ahu dtaas:type "AirHandlingUnit" ;
       dtaas:name ?name ;
       dtaas:properties ?props .
  ?props dtaas:status ?status .
  OPTIONAL { ?props dtaas:supplyAirTemperature ?supplyTemp }
  OPTIONAL { ?props dtaas:returnAirTemperature ?returnTemp }
}
```

**Elevator utilization across the building:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?elevator ?name ?currentFloor ?tripsToday ?status WHERE {
  ?elevator dtaas:type "Elevator" ;
            dtaas:name ?name ;
            dtaas:properties ?props .
  ?props dtaas:currentFloor ?currentFloor ;
         dtaas:status ?status .
  OPTIONAL { ?props dtaas:tripsToday ?tripsToday }
}
ORDER BY DESC(?tripsToday)
```

---

### Manufacturing

**Production line efficiency comparison:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?line ?name ?oee ?throughput ?status WHERE {
  ?line dtaas:type "ProductionLine" ;
        dtaas:name ?name ;
        dtaas:properties ?props .
  OPTIONAL { ?props dtaas:oee ?oee }
  OPTIONAL { ?props dtaas:currentThroughput ?throughput }
  OPTIONAL { ?props dtaas:status ?status }
}
ORDER BY DESC(?oee)
```

**CNC machines with high operating hours (maintenance candidates):**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?machine ?name ?hours ?nextMaint ?status WHERE {
  ?machine dtaas:type "CNCMachine" ;
           dtaas:name ?name ;
           dtaas:properties ?props .
  ?props dtaas:operatingHours ?hours ;
         dtaas:status ?status .
  OPTIONAL { ?props dtaas:nextMaintenance ?nextMaint }
  FILTER (?hours > 5000)
}
ORDER BY DESC(?hours)
```

**Robot utilization across workstations:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?robot ?name ?manufacturer ?cyclesCompleted ?status WHERE {
  ?robot dtaas:type "IndustrialRobot" ;
         dtaas:name ?name ;
         dtaas:properties ?props .
  ?props dtaas:manufacturer ?manufacturer ;
         dtaas:status ?status .
  OPTIONAL { ?props dtaas:cyclesCompleted ?cyclesCompleted }
}
ORDER BY DESC(?cyclesCompleted)
```

---

### Healthcare

**Operating room availability and capabilities:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?or ?name ?surgeryType ?status ?hasRobotic WHERE {
  ?or dtaas:type "OperatingRoom" ;
      dtaas:name ?name ;
      dtaas:properties ?props .
  ?props dtaas:surgeryType ?surgeryType ;
         dtaas:status ?status ;
         dtaas:hasRoboticSystem ?hasRobotic .
}
ORDER BY ?status ?surgeryType
```

**Medical imaging equipment with scan counts:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?equipment ?name ?type ?manufacturer ?scansToday ?scansThisMonth WHERE {
  ?equipment dtaas:name ?name ;
             dtaas:type ?type ;
             dtaas:properties ?props .
  ?props dtaas:manufacturer ?manufacturer ;
         dtaas:scansToday ?scansToday ;
         dtaas:scansThisMonth ?scansThisMonth .
  FILTER (?type IN ("MRI", "CT", "X-Ray", "Ultrasound", "PET-CT"))
}
ORDER BY DESC(?scansThisMonth)
```

**ICU bed occupancy with monitoring equipment:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?room ?roomName ?occupied WHERE {
  ?room dtaas:type "PatientRoom" ;
        dtaas:name ?roomName ;
        dtaas:properties ?props .
  ?props dtaas:roomType "ICU" ;
         dtaas:isOccupied ?occupied .
}
ORDER BY ?roomName
```

**Department bed capacity utilization:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?dept ?name ?totalBeds ?occupiedBeds WHERE {
  ?dept dtaas:type "HospitalDepartment" ;
        dtaas:name ?name ;
        dtaas:properties ?props .
  ?props dtaas:totalBeds ?totalBeds ;
         dtaas:occupiedBeds ?occupiedBeds .
  FILTER (?totalBeds > 0)
}
ORDER BY DESC(?occupiedBeds)
```

---

### Supply Chain

**Warehouse capacity utilization by location:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?warehouse ?name ?city ?country ?utilization WHERE {
  ?warehouse dtaas:name ?name ;
             dtaas:properties ?props .
  ?props dtaas:city ?city ;
         dtaas:country ?country ;
         dtaas:currentUtilization ?utilization .
  FILTER (?utilization > 50)
}
ORDER BY DESC(?utilization)
```

**Shipments in transit with carriers:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?shipment ?trackingNo ?origin ?destination ?status WHERE {
  ?shipment dtaas:properties ?props .
  ?props dtaas:trackingNumber ?trackingNo ;
         dtaas:origin ?origin ;
         dtaas:destination ?destination ;
         dtaas:status ?status .
  FILTER (?status = "in_transit")
}
```

**Fleet vehicles by type and status:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?vehicle ?name ?type ?status ?fuelLevel WHERE {
  ?vehicle dtaas:type ?type ;
           dtaas:name ?name ;
           dtaas:properties ?props .
  ?props dtaas:status ?status .
  OPTIONAL { ?props dtaas:fuelLevel ?fuelLevel }
  FILTER (?type IN ("SemiTruck", "DeliveryVan", "RefrigeratedTruck", "ContainerShip"))
}
ORDER BY ?type ?status
```

**Container ships at sea:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?ship ?name ?route ?currentLoad ?capacity ?eta WHERE {
  ?ship dtaas:type "ContainerShip" ;
        dtaas:name ?name ;
        dtaas:properties ?props .
  ?props dtaas:route ?route ;
         dtaas:currentLoad ?currentLoad ;
         dtaas:capacity ?capacity ;
         dtaas:eta ?eta .
}
```

---

### Smart City

**Traffic sensor readings across major roads:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?sensor ?road ?vehicleCount ?avgSpeed ?occupancy WHERE {
  ?sensor dtaas:type "TrafficSensor" ;
          dtaas:properties ?props .
  OPTIONAL { ?sensor dtaas:monitors ?r . ?r dtaas:name ?road }
  ?props dtaas:vehicleCount ?vehicleCount ;
         dtaas:averageSpeed ?avgSpeed ;
         dtaas:occupancy ?occupancy .
}
ORDER BY DESC(?occupancy)
```

**Metro lines with ridership data:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?line ?name ?stations ?length ?ridership WHERE {
  ?line dtaas:type "MetroLine" ;
        dtaas:name ?name ;
        dtaas:properties ?props .
  ?props dtaas:stations ?stations ;
         dtaas:length ?length ;
         dtaas:dailyRidership ?ridership .
}
ORDER BY DESC(?ridership)
```

**Air quality across monitoring stations:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?station ?name ?aqi ?pm25 ?pm10 WHERE {
  ?station dtaas:type "AirQualityStation" ;
           dtaas:name ?name ;
           dtaas:properties ?props .
  ?props dtaas:aqi ?aqi ;
         dtaas:pm25 ?pm25 ;
         dtaas:pm10 ?pm10 .
}
ORDER BY DESC(?aqi)
```

**Parking facility availability:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?facility ?name ?type ?totalSpaces ?available WHERE {
  ?facility dtaas:type "ParkingFacility" ;
            dtaas:name ?name ;
            dtaas:properties ?props .
  ?props dtaas:facilityType ?type ;
         dtaas:totalSpaces ?totalSpaces ;
         dtaas:availableSpaces ?available .
}
ORDER BY ?available
```

---

### Energy Grid

**Power generation by plant type:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?plant ?name ?type ?capacity ?currentOutput WHERE {
  ?plant dtaas:name ?name ;
         dtaas:type ?type ;
         dtaas:properties ?props .
  ?props dtaas:capacity ?capacity ;
         dtaas:currentOutput ?currentOutput .
  FILTER (CONTAINS(?type, "PowerPlant") || ?type IN ("SolarFarm", "WindFarm"))
}
ORDER BY DESC(?currentOutput)
```

**Renewable energy sources (solar + wind):**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?farm ?name ?type ?capacity ?output ?turbineCount ?panelCount WHERE {
  ?farm dtaas:name ?name ;
        dtaas:type ?type ;
        dtaas:properties ?props .
  ?props dtaas:capacity ?capacity ;
         dtaas:currentOutput ?output .
  OPTIONAL { ?props dtaas:turbineCount ?turbineCount }
  OPTIONAL { ?props dtaas:panelCount ?panelCount }
  FILTER (?type IN ("SolarFarm", "WindFarm"))
}
ORDER BY DESC(?capacity)
```

**Battery storage state of charge:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?battery ?name ?capacity ?power ?soc ?cycleCount WHERE {
  ?battery dtaas:type "BatteryStorage" ;
           dtaas:name ?name ;
           dtaas:properties ?props .
  ?props dtaas:capacity ?capacity ;
         dtaas:power ?power ;
         dtaas:stateOfCharge ?soc ;
         dtaas:cycleCount ?cycleCount .
}
ORDER BY ?soc
```

**Transmission line loading:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?line ?name ?voltage ?capacity ?currentFlow WHERE {
  ?line dtaas:type "TransmissionLine" ;
        dtaas:name ?name ;
        dtaas:properties ?props .
  ?props dtaas:voltage ?voltage ;
         dtaas:capacity ?capacity ;
         dtaas:currentFlow ?currentFlow .
}
ORDER BY DESC(?currentFlow)
```

---

### Automotive (Fleet Management)

**Electric vehicles with low battery:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?vehicle ?name ?model ?batteryLevel ?range ?status WHERE {
  ?vehicle dtaas:type "ElectricVehicle" ;
           dtaas:name ?name ;
           dtaas:properties ?props .
  ?props dtaas:model ?model ;
         dtaas:currentBatteryLevel ?batteryLevel ;
         dtaas:currentRange ?range ;
         dtaas:status ?status .
  FILTER (?batteryLevel < 50)
}
ORDER BY ?batteryLevel
```

**Fleet vehicles requiring service:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?vehicle ?name ?odometer ?lastService ?nextService ?status WHERE {
  ?vehicle dtaas:name ?name ;
           dtaas:properties ?props .
  ?props dtaas:odometer ?odometer ;
         dtaas:lastService ?lastService ;
         dtaas:nextServiceDue ?nextService ;
         dtaas:status ?status .
  FILTER (?status = "maintenance")
}
ORDER BY ?nextService
```

**Depot capacity and utilization:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?depot ?name ?capacity ?current ?chargingStations WHERE {
  ?depot dtaas:type "VehicleDepot" ;
         dtaas:name ?name ;
         dtaas:properties ?props .
  ?props dtaas:capacity ?capacity ;
         dtaas:currentVehicles ?current ;
         dtaas:chargingStations ?chargingStations .
}
ORDER BY DESC(?current)
```

**Hybrid vehicles with fuel and battery status:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?vehicle ?name ?fuelLevel ?batteryLevel ?mpg WHERE {
  ?vehicle dtaas:type "HybridVehicle" ;
           dtaas:name ?name ;
           dtaas:properties ?props .
  ?props dtaas:currentFuelLevel ?fuelLevel ;
         dtaas:currentBatteryLevel ?batteryLevel ;
         dtaas:mpgCombined ?mpg .
}
ORDER BY ?fuelLevel
```

---

### Agriculture (Smart Farm)

**Field status with crops and soil moisture:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?field ?name ?crop ?moisture ?irrigationType WHERE {
  ?field dtaas:type "AgriculturalField" ;
         dtaas:name ?name ;
         dtaas:properties ?props .
  ?props dtaas:currentCrop ?crop ;
         dtaas:soilMoisture ?moisture ;
         dtaas:irrigationType ?irrigationType .
}
ORDER BY ?moisture
```

**Crop health and growth stage:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?crop ?name ?type ?healthScore ?growthStage ?waterReq WHERE {
  ?crop dtaas:type "Crop" ;
        dtaas:name ?name ;
        dtaas:properties ?props .
  ?props dtaas:cropType ?type ;
         dtaas:healthScore ?healthScore ;
         dtaas:currentGrowthStage ?growthStage ;
         dtaas:waterRequirement ?waterReq .
}
ORDER BY ?healthScore
```

**Irrigation zones and scheduling:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?zone ?name ?type ?flowRate ?lastIrrigation ?nextScheduled WHERE {
  ?zone dtaas:type "IrrigationZone" ;
        dtaas:name ?name ;
        dtaas:properties ?props .
  ?props dtaas:irrigationType ?type ;
         dtaas:flowRate ?flowRate ;
         dtaas:lastIrrigation ?lastIrrigation ;
         dtaas:nextScheduled ?nextScheduled .
}
ORDER BY ?nextScheduled
```

**Yield estimates by field:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?field ?name ?crop ?area ?yieldEstimate ?expectedHarvest WHERE {
  ?field dtaas:type "AgriculturalField" ;
         dtaas:name ?name ;
         dtaas:properties ?props .
  ?props dtaas:currentCrop ?crop ;
         dtaas:area ?area ;
         dtaas:yieldEstimate ?yieldEstimate ;
         dtaas:expectedHarvest ?expectedHarvest .
}
ORDER BY DESC(?yieldEstimate)
```

---

### Aerospace (Satellite Constellation)

**Satellite status by orbital plane:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?sat ?name ?plane ?altitude ?batteryLevel ?status WHERE {
  ?sat dtaas:type "CommunicationsSatellite" ;
       dtaas:name ?name ;
       dtaas:properties ?props .
  ?props dtaas:orbitalPlane ?plane ;
         dtaas:altitude ?altitude ;
         dtaas:batteryLevel ?batteryLevel ;
         dtaas:status ?status .
}
ORDER BY ?plane ?name
LIMIT 50
```

**Satellites with anomalies or low battery:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?sat ?name ?batteryLevel ?status ?thermalStatus WHERE {
  ?sat dtaas:type "CommunicationsSatellite" ;
       dtaas:name ?name ;
       dtaas:properties ?props .
  ?props dtaas:batteryLevel ?batteryLevel ;
         dtaas:status ?status ;
         dtaas:thermalStatus ?thermalStatus .
  FILTER (?batteryLevel < 85 || ?status != "operational")
}
ORDER BY ?batteryLevel
```

**Ground station coverage:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?gs ?name ?type ?country ?antennas ?status WHERE {
  ?gs dtaas:type "GroundStation" ;
      dtaas:name ?name ;
      dtaas:properties ?props .
  ?props dtaas:stationType ?type ;
         dtaas:country ?country ;
         dtaas:antennas ?antennas ;
         dtaas:status ?status .
}
ORDER BY ?type ?country
```

**Constellation operational summary:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?status (COUNT(*) AS ?count) WHERE {
  ?sat dtaas:type "CommunicationsSatellite" ;
       dtaas:properties ?props .
  ?props dtaas:status ?status .
}
GROUP BY ?status
ORDER BY DESC(?count)
```

---

### Robotics (Warehouse Automation)

**AMR fleet status by robot type:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?type (COUNT(*) AS ?count) WHERE {
  ?robot dtaas:type ?type ;
         dtaas:properties ?props .
  FILTER (?type IN ("ShelfCarrier", "ToteRunner", "PalletMover",
                    "SortationRobot", "FloorCleaner"))
}
GROUP BY ?type
ORDER BY DESC(?count)
```

**Robots with low battery needing charge:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?robot ?name ?type ?batteryLevel ?status WHERE {
  ?robot dtaas:name ?name ;
         dtaas:type ?type ;
         dtaas:properties ?props .
  ?props dtaas:batteryLevel ?batteryLevel ;
         dtaas:status ?status .
  FILTER (?batteryLevel < 30 && ?status != "charging")
}
ORDER BY ?batteryLevel
```

**Robotic arm performance:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?arm ?name ?manufacturer ?cyclesCompleted ?successRate ?status WHERE {
  ?arm dtaas:type "PickingArm" ;
       dtaas:name ?name ;
       dtaas:properties ?props .
  ?props dtaas:manufacturer ?manufacturer ;
         dtaas:cyclesCompleted ?cyclesCompleted ;
         dtaas:status ?status .
  OPTIONAL { ?props dtaas:pickSuccessRate ?successRate }
}
ORDER BY DESC(?cyclesCompleted)
```

**Zone robot distribution:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?zone ?zoneName ?zoneType WHERE {
  ?zone dtaas:type "WarehouseZone" ;
        dtaas:name ?zoneName ;
        dtaas:properties ?props .
  ?props dtaas:zoneType ?zoneType .
}
ORDER BY ?zoneType
```

**Conveyor system throughput:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?conveyor ?name ?length ?speed ?itemsProcessed ?status WHERE {
  ?conveyor dtaas:type "ConveyorBelt" ;
            dtaas:name ?name ;
            dtaas:properties ?props .
  ?props dtaas:length ?length ;
         dtaas:speed ?speed ;
         dtaas:status ?status .
  OPTIONAL { ?props dtaas:itemsProcessedToday ?itemsProcessed }
}
ORDER BY DESC(?itemsProcessed)
```

**Robots due for maintenance:**
```sparql
PREFIX dtaas: <http://tesserai.io/ontology/>

SELECT ?robot ?name ?type ?runtime ?lastMaint ?status WHERE {
  ?robot dtaas:name ?name ;
         dtaas:type ?type ;
         dtaas:properties ?props .
  ?props dtaas:totalRuntime ?runtime ;
         dtaas:lastMaintenance ?lastMaint ;
         dtaas:status ?status .
  FILTER (?status = "maintenance" || ?runtime > 15000)
}
ORDER BY DESC(?runtime)
```

---

## Real-Time Web Dashboards

Most examples include standalone web dashboards that provide real-time visualization of digital twin data. These dashboards use WebSocket connections to stream live updates every 5 seconds.

### Available Dashboards

| Domain | Port | Command | Key Visualizations |
|--------|------|---------|-------------------|
| **Energy Grid** | 8080 | `python energy_grid/web_ui.py` | Power generation, grid load, renewable sources |
| **Smart Building** | 8082 | `python smart_building/web_ui.py` | HVAC status, zone temperatures, occupancy |
| **Supply Chain** | 8102 | `python supply_chain/web_ui.py` | Warehouses, shipments, inventory levels |
| **Manufacturing** | 8104 | `python manufacturing/web_ui.py` | Production lines, QC metrics, energy usage |
| **Healthcare** | 8088 | `python healthcare/web_ui.py` | Departments, ORs, imaging equipment, ventilators |
| **Finance** | 8106 | `python finance/web_ui.py` | Trading desks, P&L, risk limits, market data |
| **Smart City** | 8092 | `python smart_city/web_ui.py` | Transit, traffic, utilities, emergency services |
| **Automotive** | 8094 | `python automotive/web_ui.py` | Fleet status, EVs, charging, deliveries |
| **Aerospace** | 8096 | `python aerospace/web_ui.py` | Satellite constellation, orbital planes, ground stations |
| **Agriculture** | 8098 | `python agriculture/web_ui.py` | Fields, crops, irrigation, drones, tractors |
| **Taxation** | 8100 | `python taxation/web_ui.py` | Transfer pricing, entities, benchmarking |

### Running a Dashboard

1. **Seed the example data first**:
   ```bash
   python examples/<domain>/seed.py
   ```

2. **Start the web UI**:
   ```bash
   python examples/<domain>/web_ui.py
   ```

3. **Open in browser**: Navigate to `http://localhost:<port>`

### Dashboard Features

All dashboards share common features:

- **Real-time Updates**: WebSocket-based streaming (5-second refresh)
- **Dark Theme**: Professional gradient backgrounds with glass-morphism effects
- **Responsive Layout**: Grid-based layouts that adapt to screen size
- **Status Indicators**: Color-coded health and status visualizations
- **Animated Alerts**: CSS animations for critical conditions
- **Connection Status**: Live indicator showing WebSocket connection state

### Example: Energy Grid Dashboard

```bash
# Terminal 1: Start the DTaaS server
cargo run

# Terminal 2: Seed energy grid data
python examples/energy_grid/seed.py

# Terminal 3: Start the dashboard
python examples/energy_grid/web_ui.py
# Open http://localhost:8080 in your browser
```

The Energy Grid dashboard displays:
- Power generation from various sources (solar, wind, hydro, thermal)
- Real-time grid load and capacity utilization
- Battery storage levels
- Substation status and transformer loads
- Transmission line health

### Dashboard Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Web Browser (Dashboard)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐        WebSocket         ┌────────────────┐  │
│   │   HTML/CSS  │◄───────────────────────►│  Data Collector │  │
│   │  JavaScript │     (Port + 1)           │   (Python)      │  │
│   └─────────────┘                          └────────────────┘  │
│         ▲                                         │            │
│         │ HTTP (Dashboard)                        │            │
│         │                                         ▼            │
│   ┌─────────────┐                         ┌────────────────┐  │
│   │ HTTP Server │                         │  DTaaS Client  │  │
│   │  (Port)     │                         │   (SDK)        │  │
│   └─────────────┘                         └────────────────┘  │
│                                                   │            │
└───────────────────────────────────────────────────│────────────┘
                                                    ▼
                                           ┌────────────────┐
                                           │  DTaaS Server  │
                                           │   (Port 8080)  │
                                           └────────────────┘
```

### Customizing Dashboards

Each `web_ui.py` file contains:

1. **Data Collector Class**: Queries the DTaaS API and structures data
2. **HTML Template**: Embedded HTML/CSS/JavaScript dashboard
3. **WebSocket Server**: Broadcasts updates to connected clients
4. **HTTP Server**: Serves the dashboard HTML

To customize:
- Modify the HTML template string to change visualizations
- Adjust the data collector to include additional twin properties
- Change the refresh interval (default: 5 seconds)
- Add new panels or metrics as needed

---

## Performance Optimization

The example scripts use bulk APIs for efficient seeding against remote servers.

### Bulk API Functions

The `common.py` module provides these bulk helper functions:

```python
from common import bulk_create_twins, bulk_add_relationships, bulk_upload_ontologies

# Create multiple twins in one batch request
twins_data = [
    {"id": "twin-1", "type": "http://example.org/Sensor", "name": "Sensor 1", ...},
    {"id": "twin-2", "type": "http://example.org/Sensor", "name": "Sensor 2", ...},
]
succeeded, failed = bulk_create_twins(client, twins_data)

# Add relationships in parallel
relationships = [
    ("building-001", "hasFloor", "floor-001", None),
    ("floor-001", "hasRoom", "room-001", None),
]
succeeded, failed = bulk_add_relationships(client, relationships)

# Upload ontologies in parallel
ontologies = [
    ("core", "/path/to/core.ttl", "Core Ontology"),
    ("domain", "/path/to/domain.ttl", "Domain Ontology"),
]
succeeded, failed = bulk_upload_ontologies(base_url, token, ontologies)
```

### Converting Seed Scripts to Bulk API

To convert a seed script to use bulk operations:

1. Replace `create_twin_safe()` calls with collecting twins in a list
2. Replace `add_relationship_safe()` calls with collecting relationships in a list
3. Call `bulk_create_twins()` and `bulk_add_relationships()` at the end

See `smart_building/seed.py` for a complete example of the bulk pattern.

### Command-Line Options

```bash
# Load ontologies in parallel (default, ~3x faster)
python load_ontologies.py

# Load ontologies sequentially (for debugging)
python load_ontologies.py --sequential
```

---

## Customization

Each seed script can be easily customized:

1. **Modify entity counts**: Change loop ranges to create more or fewer entities
2. **Add custom properties**: Extend the `properties` dictionaries
3. **Create new relationships**: Use `add_relationship_safe()` for new connections
4. **Change data patterns**: Modify the data generation logic

## Contributing

To add a new domain example:

1. Create a new folder under `examples/`
2. Create a `seed.py` file following the existing patterns
3. Import and use the utilities from `common.py`
4. Update this README with the new domain
5. Add the domain to `seed_all.py`

## License

These examples are provided under the same license as the main DTaaS project.
