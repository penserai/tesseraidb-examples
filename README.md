# TesseraiDB Examples

This repository contains comprehensive example digital twins and scenarios for [TesseraiDB](https://tesserai.io), a semantic knowledge graph database designed for AI agents.

Each example demonstrates how to model complex real-world systems using TesseraiDB's ontology-based approach, including entities, relationships, semantic reasoning, and real-time streaming.

## Demo Environment

> **Note:** The `default` tenant on [tesserai.io](https://tesserai.io) includes pre-seeded data for all examples below. You can explore the digital twins, run SPARQL queries, and interact with the data immediately.

## Quick Start

### 1. Sign Up

Create an account at [tesserai.io](https://tesserai.io) to access the platform.

### 2. Explore the Data

Navigate to the `default` tenant to explore pre-seeded example data:
- Use the **Twin Explorer** to browse digital twins
- Use the **SPARQL Editor** to run queries
- View the **Graph Visualization** to see relationships

### 3. Use the Python SDK (Optional)

```bash
export TESSERAI_API_KEY="your-api-key"
pip install tesserai
```

## Available Examples

| Domain | Description | Key Features |
|--------|-------------|--------------|
| [Smart Building](smart_building/) | Office building with HVAC, sensors, access control | RSP streaming, real-time alerts |
| [Manufacturing](manufacturing/) | Industry 4.0 factory with CNC, robots, QC | Production line monitoring |
| [Healthcare](healthcare/) | Hospital with medical equipment, patient monitoring | Equipment tracking, OR status |
| [Supply Chain](supply_chain/) | Global logistics with warehouses, trucks, ships | Shipment tracking, inventory |
| [Smart City](smart_city/) | Urban infrastructure, transit, utilities | Traffic, air quality monitoring |
| [Robotics](robotics/) | Automated fulfillment center with AMRs | Fleet management, path planning |
| [Energy Grid](energy_grid/) | Power grid with renewables, storage, distribution | ASP-based grid optimization |
| [Automotive](automotive/) | Fleet management with EVs, telematics | Battery monitoring, maintenance |
| [Agriculture](agriculture/) | Precision farming with sensors, drones, tractors | Irrigation, crop health |
| [Aerospace](aerospace/) | Satellite constellation with ground stations | Orbital mechanics, telemetry |
| [Finance](finance/) | Trading systems with risk management | Portfolio analytics |
| [Taxation](taxation/) | Transfer pricing and tax compliance | Entity relationships |

## Advanced Examples

These examples demonstrate production-grade features with realistic simulations and live dashboards:

| Example | Description |
|---------|-------------|
| [Predictive Maintenance](predictive_maintenance/) | Industrial equipment health monitoring with Weibull failure modeling and RUL prediction |
| [Cascading Failure](cascading_failure/) | Infrastructure dependency modeling with SPOF detection and blast radius analysis |
| [Alerting System](alerting_system/) | Production alerting with configurable rules, escalation policies, and chaos engineering |

## Project Structure

```
examples/
├── common.py              # Shared utilities and client initialization
├── ontologies/           # OWL/Turtle ontology definitions
│   ├── core.ttl
│   ├── smart_building.ttl
│   └── ...
├── smart_building/
│   ├── web_ui.py         # Real-time dashboard
│   └── README.md         # Domain-specific guide
└── ... (other domains)
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TESSERAI_API_KEY` | (required) | Your TesseraiDB API key |
| `TESSERAI_API_URL` | `https://api.tesserai.io` | TesseraiDB API endpoint |

### Python Requirements

- Python 3.10 or higher (3.11+ recommended)
- Install dependencies: `pip install tesserai httpx`

## Using the Examples

### Web Dashboards

Most examples include interactive web dashboards:

```bash
# Start a dashboard
python energy_grid/web_ui.py

# Dashboards are available at http://localhost:<port>
# Check each domain's README for the specific port
```

### Python SDK Usage

```python
from common import get_client

# Initialize the client (uses TESSERAI_API_KEY from environment)
client = get_client()

# List twins by domain
twins = client.twins.list(domain="smart_building")

# Get a specific twin
twin = client.twins.get("urn:tesserai:twin:building-001")

# Query with SPARQL
results = client.query.select("""
    SELECT ?sensor ?temp WHERE {
        ?sensor a <http://tesserai.io/ontology/smart_building#TemperatureSensor> ;
                <http://tesserai.io/ontology/core#currentValue> ?temp .
        FILTER (?temp > 25)
    }
""")
```

## Ontology Structure

Each domain uses semantic ontologies (OWL 2) to define:

- **Classes**: Types of entities (e.g., `Sensor`, `Vehicle`, `Equipment`)
- **Properties**: Attributes and relationships between entities
- **SHACL Shapes**: Data validation constraints
- **Reasoning Rules**: SWRL-style inference rules

Example ontology hierarchy:
```
dtaas:Entity
├── dtaas:Sensor
│   ├── bldg:TemperatureSensor
│   ├── bldg:HumiditySensor
│   └── bldg:CO2Sensor
├── dtaas:Equipment
│   ├── mfg:CNCMachine
│   └── mfg:Robot
└── dtaas:Location
    ├── bldg:Floor
    └── bldg:Room
```

## Semantic Reasoning

TesseraiDB supports OWL 2 RL reasoning for automatic inference:

```python
# Materialize inferences
client.reasoning.materialize()

# Execute custom rules
client.reasoning.execute_rules("automotive")

# Get explanations for inferred facts
explanation = client.reasoning.explain("urn:tesserai:twin:vehicle-001", "LowBattery")
```

## RDF Stream Processing (RSP)

Real-time monitoring with continuous SPARQL queries:

```python
from dtaas.models import ContinuousQueryCreate, WindowConfig, WindowType

# Create a stream source
source = client.rsp.create_source(
    name="sensor-stream",
    config={"type": "event_bus", "twin_id_patterns": ["sensor-*"]}
)

# Create a continuous query with sliding window
query = client.rsp.create_query(
    ContinuousQueryCreate(
        name="High Temperature Alert",
        sparql="SELECT ?s ?temp WHERE { ?s <temp> ?temp . FILTER(?temp > 28) }",
        window=WindowConfig(
            type=WindowType.TIME_BASED,
            duration_seconds=300,
            slide_seconds=60
        ),
        stream_sources=[source.id]
    )
)
```

## API Reference

For complete API documentation, visit:
- **API Docs**: [docs.tesserai.io](https://docs.tesserai.io)
- **Interactive API**: Your TesseraiDB instance at `/swagger-ui/`

## Contributing

We welcome contributions! To add a new domain example:

1. Create a new folder under `examples/`
2. Create an ontology in `ontologies/`
3. Add a `README.md` with domain-specific documentation
4. Include example SPARQL queries demonstrating the domain

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

- **Documentation**: [docs.tesserai.io](https://docs.tesserai.io)
- **Issues**: [GitHub Issues](https://github.com/penserai/tesseraidb-examples/issues)
- **Community**: [Discord](https://discord.gg/tesserai)

---

Copyright 2026 Penserai Inc.
