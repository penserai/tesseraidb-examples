# TesseraiDB Examples

This directory contains example scripts demonstrating various capabilities of TesseraiDB.

## Domain Examples (15 Use Cases)

The following domain-specific examples demonstrate TesseraiDB's Digital Twin capabilities:

| # | Domain | Description | Script |
|---|--------|-------------|--------|
| 1 | **Aerospace** | Satellite constellation with LEO communications, ground stations, and mission control | `aerospace/` |
| 2 | **Agriculture** | Precision farming with sensors, drones, and tractors | `agriculture/` |
| 3 | **Alerting System** | Alert management and notification system | `alerting_system/` |
| 4 | **Automotive** | Fleet management with EVs and telematics | `automotive/` |
| 5 | **Cascading Failure** | System failure propagation and impact analysis | `cascading_failure/` |
| 6 | **Energy Grid** | Power grid with renewables and distribution systems | `energy_grid/` |
| 7 | **Finance** | Portfolio management, risk monitoring, and regulatory compliance | `finance/` |
| 8 | **Healthcare** | Hospital systems with medical equipment and patient monitoring | `healthcare/` |
| 9 | **Manufacturing** | Industry 4.0 factory with CNC machines, robots, and QC equipment | `manufacturing/` |
| 10 | **Predictive Maintenance** | Equipment monitoring and failure prediction | `predictive_maintenance/` |
| 11 | **Robotics** | Automated fulfillment center with AMRs and robotic arms | `robotics/` |
| 12 | **Smart Building** | Multi-floor commercial building with HVAC, lighting, and sensors | `smart_building/` |
| 13 | **Smart City** | Urban infrastructure, transit, and utilities management | `smart_city/` |
| 14 | **Supply Chain** | Global logistics with warehouses, trucks, and ships | `supply_chain/` |
| 15 | **Taxation** | Tax compliance and regulatory requirements | `taxation/` |

## Semantic Memory Examples (AI Agent Memory)

The following examples demonstrate the Semantic Memory system for AI agents. Each example includes:
- **seed.py** - Seeds example data into TesseraiDB
- **web_ui.py** - Interactive web dashboard for visualization
- **simulation.py** - Live simulation for demonstration

| # | Domain | Description | Directory |
|---|--------|-------------|-----------|
| 16 | **Code Agent Context** | AI coding assistant memory with debugging sessions, patterns, and reasoning | `code_agent_context/` |
| 17 | **Personal Assistant** | Context-aware mobile assistance with preferences, reminders, and location awareness | `personal_assistant/` |
| 18 | **Process Evolution** | Business process management with bottleneck detection and automatic optimization | `process_evolution/` |

### 16. Code Agent Context Management (`code_agent_context/`)

Demonstrates how an autonomous coding agent can use semantic memory to:
- Maintain context across a coding session (Working Memory)
- Store reasoning steps and decisions (Episodic Memory)
- Retrieve relevant documentation or past solutions (Semantic Search)
- Persist successful patterns for future use (Semantic Memory)

**Use Case:** AI coding assistants that need to remember past debugging sessions, successful patterns, and project-specific knowledge.

**Quick Start:**
```bash
cd code_agent_context
python seed.py              # Seed example data
python web_ui.py --port 8122  # Launch dashboard at http://localhost:8122
python simulation.py        # Run live simulation
```

### 17. Mobile Personal Assistant (`personal_assistant/`)

Demonstrates context-aware mobile assistance:
- Store user preferences (Semantic Memory)
- Log location context and visits (Episodic Memory)
- Set context-aware reminders with `valid_at` and `expires_at`
- Query memories filtered by context (e.g., "reminders relevant to Grocery Store")

**Use Case:** Personal AI assistants that learn user preferences, remember past interactions, and provide contextually relevant information.

**Quick Start:**
```bash
cd personal_assistant
python seed.py              # Seed example data
python web_ui.py --port 8123  # Launch dashboard at http://localhost:8123
python simulation.py        # Run day simulation
```

### 18. Business Process Evolution (`process_evolution/`)

Demonstrates adaptive business systems:
- Define process definitions (Semantic Memory with PROCEDURE type)
- Log process execution steps and delays (Episodic Memory)
- Detect patterns and bottlenecks through semantic queries
- Evolve process definitions based on operational evidence

**Use Case:** Business process management systems that automatically identify inefficiencies and suggest process improvements.

**Quick Start:**
```bash
cd process_evolution
python seed.py              # Seed example data
python web_ui.py --port 8124  # Launch dashboard at http://localhost:8124
python simulation.py        # Run process simulation
```

## Running Examples

### Prerequisites

- Python 3.8+
- `dtaas` SDK installed (`pip install dtaas` or from `sdks/python`)
- TesseraiDB server running at `http://localhost:8080`

### Quick Start

```bash
# Install SDK (dev mode)
pip install -e ../sdks/python
pip install websockets  # Required for web UIs

# Set environment variables
export TESSERAI_URL="http://localhost:8080"
export TESSERAI_API_KEY="your-api-key"

# Run Semantic Memory examples
cd code_agent_context && python seed.py && python web_ui.py
cd personal_assistant && python seed.py && python web_ui.py
cd process_evolution && python seed.py && python web_ui.py

# Run Domain examples (seed data first)
python load_ontologies.py
python seed_all.py
```

## Utility Scripts

| Script | Description |
|--------|-------------|
| `common.py` | Shared utilities and helper functions |
| `load_ontologies.py` | Load all domain ontologies |
| `seed_all.py` | Seed all domain example data |
| `queries.py` | Example SPARQL queries |
| `reasoning_demo.py` | OWL 2 RL reasoning demonstration |
| `domain_rules.py` | Custom domain rules examples |
| `validation_demo.py` | SHACL validation demonstration |
| `cross_domain_scenario.py` | Cross-domain relationship queries |
