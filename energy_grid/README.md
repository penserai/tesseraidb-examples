# Energy Grid Digital Twin with ASP (Answer Set Programming)

This example demonstrates a comprehensive **digital twin of a regional power grid** integrated with **Answer Set Programming (ASP)** for solving complex optimization and diagnostic problems.

## Table of Contents

1. [Overview](#overview)
2. [What is Answer Set Programming?](#what-is-answer-set-programming)
3. [Use Cases Demonstrated](#use-cases-demonstrated)
4. [Prerequisites](#prerequisites)
5. [Quick Start](#quick-start)
6. [The Energy Grid Model](#the-energy-grid-model)
7. [ASP Demonstrations](#asp-demonstrations)
   - [Unit Commitment Optimization](#1-unit-commitment-optimization)
   - [Fault Diagnosis](#2-fault-diagnosis)
   - [N-1 Contingency Analysis](#3-n-1-contingency-analysis)
   - [Natural Language ASP Conversation](#4-natural-language-asp-conversation)
8. [ASP Program Reference](#asp-program-reference)
9. [API Endpoints](#api-endpoints)
10. [Extending the Example](#extending-the-example)
11. [Troubleshooting](#troubleshooting)

---

## Overview

Power grids are complex cyber-physical systems requiring sophisticated decision-making for:
- **Economic dispatch**: Minimize generation costs while meeting demand
- **Reliability**: Ensure the grid survives component failures
- **Diagnostics**: Quickly identify faults when alarms trigger
- **Renewable integration**: Balance intermittent sources with storage

This example creates a **semantic digital twin** of a power grid in TesseraiDB and demonstrates how **Answer Set Programming (ASP)** can solve these problems declaratively.

### Why ASP for Power Grids?

| Problem | Traditional Approach | ASP Advantage |
|---------|---------------------|---------------|
| Unit Commitment | Mixed-integer programming | Natural modeling of discrete on/off decisions |
| Fault Diagnosis | Expert systems, decision trees | Logical abduction with minimal explanations |
| Contingency Analysis | Simulation-based | Enumerate all scenarios declaratively |
| Configuration | Manual rules | Constraint satisfaction with optimization |

---

## What is Answer Set Programming?

**Answer Set Programming (ASP)** is a declarative programming paradigm for solving difficult combinatorial problems. Instead of writing *how* to solve a problem, you declare *what* the problem is.

### Key Concepts

```prolog
% FACTS: Things that are true
generator("plant-gas-001", "NaturalGas", 1200, 450, 45).
% generator(ID, Type, Capacity_MW, Emissions_gCO2/kWh, Cost_$/MWh)

% RULES: Define derived knowledge
committed(G) :- generator(G, _, _, _, _), online(G).
% "G is committed if G is a generator and G is online"

% CHOICE RULES: Non-deterministic decisions
{ commit(G) } :- generator(G, _, _, _, _).
% "We may or may not commit each generator"

% CONSTRAINTS: Eliminate invalid solutions
:- total_output(T), demand(D), T < D.
% "It's forbidden for total output to be less than demand"

% OPTIMIZATION: Find the best solution
#minimize { Cost,G : gen_cost(G, Cost) }.
% "Minimize the sum of all generator costs"
```

### The Clingo Solver

TesseraiDB uses **[Clingo](https://potassco.org/clingo/)**, the state-of-the-art ASP solver from the University of Potsdam. Clingo:
- Handles millions of variables
- Supports optimization (finding best solutions)
- Provides all solutions or optimal ones
- Runs in milliseconds for typical grid problems

---

## Use Cases Demonstrated

### 1. Unit Commitment Optimization
Decide which generators to turn on to meet forecasted demand at minimum cost while maintaining spinning reserve.

### 2. Model-Based Fault Diagnosis
Given SCADA alarms and sensor readings, identify the minimal set of faulty components that explains all observations.

### 3. N-1 Contingency Analysis
Verify that the grid remains stable if any single component fails. Identify vulnerable configurations.

### 4. Natural Language ASP Interface
Create and refine ASP programs through conversational interaction using plain English.

---

## Prerequisites

### Software Requirements

1. **TesseraiDB Server** running at `http://localhost:8080`
   ```bash
   cargo run --release --bin tesseraidb
   ```

2. **Python 3.10+** with the DTaaS SDK
   ```bash
   cd sdks/python
   pip install -e .
   ```

3. **LLM Configuration** (for NL conversation demo)
   - Configure Ollama or OpenAI in `config.toml`
   - See [LLM Gateway documentation](../../docs/llm_gateway.md)

### Verify Setup

```bash
# Check server health
curl http://localhost:8080/health

# Should return: {"status":"healthy","version":"0.1.0",...}
```

---

## Quick Start

```bash
# 1. Navigate to the energy_grid example
cd examples/energy_grid

# 2. Seed the digital twin with grid data
python seed.py

# 3. Run all ASP demonstrations
python asp_demo.py

# Or run specific demos
python asp_demo.py --demo unit-commitment
python asp_demo.py --demo fault-diagnosis
python asp_demo.py --demo contingency
python asp_demo.py --demo conversation
```

---

## The Energy Grid Model

The digital twin represents a **regional power grid** with the following components:

### Generation Assets (12 units)

| Type | Units | Total Capacity | Characteristics |
|------|-------|----------------|-----------------|
| Nuclear | 1 | 2,200 MW | Baseload, zero emissions, low variable cost |
| Natural Gas | 2 | 2,000 MW | Dispatchable, moderate emissions |
| Coal | 1 | 1,500 MW | Baseload, high emissions (being phased out) |
| Hydroelectric | 1 | 1,800 MW | Dispatchable, zero emissions, seasonal |
| Solar Farms | 3 | 1,000 MW | Intermittent, zero emissions |
| Wind Farms | 4 | 2,850 MW | Intermittent, zero emissions |

### Grid Infrastructure

| Component | Count | Description |
|-----------|-------|-------------|
| HV Substations | 5 | 345-500 kV transmission nodes |
| Transmission Lines | 5 | High-voltage interconnections |
| Distribution Substations | 6 | Step-down to distribution voltage |
| Battery Storage | 4 | 1,550 MWh total capacity |
| Smart Meters | 20 | Sample residential/commercial/industrial |
| Protective Relays | 5 | Fault detection and isolation |
| Weather Stations | 3 | Renewable forecasting inputs |
| EV Charging | 3 | Demand-side resources |
| Demand Response | 3 | Curtailable load programs |

### Ontology

The grid is modeled using semantic relationships:

```turtle
@prefix energy: <https://tesserai.dev/ontology/energy#> .

:grid-regional-001 a energy:PowerGrid ;
    energy:hasGenerator :plant-nuclear-001, :plant-gas-001, ... ;
    energy:hasSubstation :substation-hv-001, ... ;
    energy:hasStorage :battery-001, ... ;
    energy:currentLoad 11500 ;
    energy:totalCapacity 15000 .

:plant-nuclear-001 a energy:NuclearPowerPlant ;
    energy:capacity 2200 ;
    energy:currentOutput 1650 ;
    energy:connectsTo :substation-hv-001 .
```

---

## ASP Demonstrations

### 1. Unit Commitment Optimization

**Problem Statement**: Given forecasted demand and available generators, decide which generators to commit (turn on) to meet demand at minimum operating cost while maintaining required spinning reserve.

**Why It's Hard**:
- Binary decisions (on/off) create 2^N combinations
- Must satisfy demand and reserve constraints
- Minimize cost (or emissions, or both)
- Respect minimum run times, ramp rates, etc.

**ASP Approach**:

```prolog
% Generator data from digital twin
generator("plant-gas-001", "NaturalGas", 1200, 450, 45).
generator("plant-nuclear-001", "Nuclear", 2200, 0, 10).
generator("solar-farm-001", "Solar", 500, 0, 0).

% Demand requirement
demand(10000).  % 10 GW demand
reserve_margin(1000).  % 1 GW spinning reserve

% Decision: which generators to commit
{ commit(G) } :- generator(G, _, _, _, _).

% Calculate output (simplified: 80% of capacity when committed)
output(G, Out) :- commit(G), generator(G, _, Cap, _, _), Out = Cap * 80 / 100.

% Constraint: meet demand
total_output(T) :- T = #sum { Out,G : output(G, Out) }.
:- total_output(T), demand(D), T < D.

% Constraint: maintain reserve
total_capacity(C) :- C = #sum { Cap,G : commit(G), generator(G, _, Cap, _, _) }.
:- total_capacity(C), demand(D), reserve_margin(R), C < D + R.

% Optimization: minimize cost
gen_cost(G, Cost) :- output(G, Out), generator(G, _, _, _, VarCost), Cost = Out * VarCost.
#minimize { Cost,G : gen_cost(G, Cost) }.
```

**Running the Demo**:

```bash
python asp_demo.py --demo unit-commitment
```

**Sample Output**:

```
DEMO 1: UNIT COMMITMENT OPTIMIZATION
================================================================================
Current Grid State:
  - Demand: 11500 MW
  - Reserve Requirement: 1000 MW
  - Available Generators: 12

Solving with ASP (clingo)...

SOLUTION FOUND!

Committed Generators:
------------------------------------------------------------
  [ON] plant-nuclear-001: 1760 MW
  [ON] plant-hydro-001: 1440 MW
  [ON] plant-gas-001: 960 MW
  [ON] solar-farm-001: 325 MW
  [ON] wind-farm-003: 560 MW
  ...

Total Cost: $85,000/hour
Total Emissions: 432,000 kg CO2/hour
```

---

### 2. Fault Diagnosis

**Problem Statement**: Given observed symptoms from SCADA (alarms, zero readings, voltage anomalies), identify the minimal set of faulty components that explains all observations.

**Why It's Hard**:
- Multiple faults can produce similar symptoms
- Want the *simplest* explanation (Occam's razor)
- Must reason about system structure and physics

**ASP Approach** (Model-Based Diagnosis):

```prolog
% System components
component("line-hv-005"). component("plant-gas-002"). component("substation-dist-003").
transmission_line("line-hv-005").
generator("plant-gas-002").
substation("substation-dist-003").

% Connectivity
connected("plant-gas-002", "line-hv-005").
connected("line-hv-005", "substation-hv-002").
connected("substation-hv-002", "substation-dist-003").

% Abducibles: components may be faulty
{ faulty(C) } :- component(C).
working(C) :- component(C), not faulty(C).

% Normal behavior: power flows through working components
power_flows(S) :- substation(S),
                  generator(G), working(G),
                  connected(G, L), working(L),
                  connected(L, S).

% Observations (from SCADA)
obs_no_power("substation-dist-003").
obs_line_fault("line-hv-005").

% Diagnosis constraints
:- obs_no_power(S), power_flows(S).  % No power means path is broken
:- obs_line_fault(L), working(L).    % Fault alarm means line is faulty

% Minimize faults (parsimony)
#minimize { 1,C : faulty(C) }.
```

**Running the Demo**:

```bash
python asp_demo.py --demo fault-diagnosis
```

**Sample Output**:

```
DEMO 2: FAULT DIAGNOSIS
================================================================================
Simulated Fault Scenario:
  - Substation dist-003: No power detected
  - Line hv-005: Fault alarm triggered
  - Generator gas-002: Zero output (unexpected)

Running Diagnosis with ASP...

DIAGNOSIS RESULTS:
------------------------------------------------------------

Diagnosis 1 (cardinality 2):
  - FAULTY: line-hv-005
  - FAULTY: plant-gas-002

Explanation: Line hv-005 failure explains the fault alarm.
             Generator gas-002 failure explains zero output.
             Both together explain no power at substation.
```

---

### 3. N-1 Contingency Analysis

**Problem Statement**: Verify that the grid remains stable if any single critical component fails. Identify configurations where a single failure would cause load shedding.

**Why It's Important**:
- NERC reliability standards require N-1 security
- Must plan for equipment failures
- Identifies needed infrastructure investments

**ASP Approach**:

```prolog
% Critical components
critical_component("line-hv-001").
critical_component("line-hv-002").
critical_component("plant-nuclear-001").

% Critical loads
critical_load("substation-dist-001").
critical_load("substation-dist-002").

% Simulate single failure
1 { failed(C) : critical_component(C) } 1.

% Component operational if not failed
operational(C) :- component(C), not failed(C).

% Load can be served if path exists from generator
can_serve(L) :- load(L), path(G, L), generator(G), operational(G).
path(X, Y) :- connected(X, Y), operational(X), operational(Y).
path(X, Z) :- path(X, Y), connected(Y, Z), operational(Z).

% Find unserved critical loads
critical_unserved(L) :- critical_load(L), not can_serve(L).

#show failed/1.
#show critical_unserved/1.
```

**Running the Demo**:

```bash
python asp_demo.py --demo contingency
```

**Sample Output**:

```
DEMO 3: N-1 CONTINGENCY ANALYSIS
================================================================================
Critical Components Under Analysis:
  - line-hv-001: Central-North 500kV
  - line-hv-002: Central-South 345kV
  - plant-nuclear-001: Lakeside Nuclear (2200 MW)

Analyzing contingencies...

CONTINGENCY RESULTS:
------------------------------------------------------------

[VULNERABLE] If failed("line-hv-001") fails:
  -> Load "substation-dist-003" would lose power!

[OK] All other single failures are survivable.

Found 1 vulnerable configuration!
Recommendation: Add redundant path to substation-dist-003.
```

---

### 4. Natural Language ASP Conversation

**Problem Statement**: Allow operators to create and refine ASP programs using plain English, without knowing ASP syntax.

**How It Works**:
1. User describes the problem in natural language
2. LLM translates to ASP program
3. User can refine iteratively ("add emissions constraint")
4. System executes and shows results

**Example Conversation**:

```
[User 1]: Create a simple ASP program that models a power grid with 3 generators
          and finds which ones to turn on to meet 100 MW demand

[Assistant]: I'll create an ASP program for the unit commitment problem...

Proposed ASP Program:
----------------------------------------
% Generator definitions
generator(g1, 50, 30).   % 50 MW capacity, $30/MWh
generator(g2, 40, 25).   % 40 MW capacity, $25/MWh
generator(g3, 60, 35).   % 60 MW capacity, $35/MWh

% Demand
demand(100).

% Decision: commit generators
{ commit(G) } :- generator(G, _, _).

% Calculate output
output(G, Cap) :- commit(G), generator(G, Cap, _).

% Meet demand
:- #sum { Out,G : output(G, Out) } < 100.

% Minimize cost
#minimize { Cap*Cost,G : commit(G), generator(G, Cap, Cost) }.

#show commit/1.
----------------------------------------

[User 2]: Add a constraint that we need at least 20 MW of reserve capacity

[Assistant]: I'll add a spinning reserve constraint...

Updated program adds:
  :- #sum { Cap,G : commit(G), generator(G, Cap, _) } < 120.
  % Total capacity must be at least demand + 20 MW reserve

[User 3]: Run the program

[Assistant]: Executing...

Result: SATISFIABLE
Answer set: commit(g2), commit(g3)
Total capacity: 100 MW, Reserve: 0 MW...

Wait, this doesn't meet the reserve constraint. Let me add g1...
Final: commit(g1), commit(g2), commit(g3)
Total capacity: 150 MW, Reserve: 50 MW, Cost: $4,500/hour
```

**Running the Demo**:

```bash
python asp_demo.py --demo conversation
```

---

## ASP Program Reference

### Syntax Quick Reference

| Construct | Syntax | Meaning |
|-----------|--------|---------|
| Fact | `fact(a, b).` | Unconditionally true |
| Rule | `head :- body.` | Head is true if body is true |
| Choice | `{ a; b; c }.` | Choose subset of {a, b, c} |
| Cardinality | `2 { a; b; c } 3.` | Choose 2-3 from set |
| Constraint | `:- condition.` | Condition must be false |
| Aggregates | `#sum`, `#count`, `#min`, `#max` | Aggregate functions |
| Optimization | `#minimize { ... }.` | Minimize objective |
| Show | `#show pred/arity.` | Include in output |

### Common Patterns for Power Grids

**Binary Commitment**:
```prolog
{ commit(G) } :- generator(G).
output(G, Cap) :- commit(G), generator(G, Cap).
output(G, 0) :- generator(G), not commit(G).
```

**Meet Demand Constraint**:
```prolog
:- #sum { Out,G : output(G, Out) } < demand.
```

**Spinning Reserve**:
```prolog
:- #sum { Cap,G : commit(G), gen(G, Cap) } < demand + reserve.
```

**Minimum Generators**:
```prolog
:- #count { G : commit(G) } < 3.
```

**Emissions Limit**:
```prolog
:- #sum { E,G : commit(G), emissions(G, E) } > max_emissions.
```

---

## API Endpoints

### ASP Solver Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/asp/solve` | Solve an ASP program |
| POST | `/api/v1/asp/diagnose` | Model-based diagnosis |
| POST | `/api/v1/asp/configure` | Configuration solving |
| POST | `/api/v1/asp/programs` | Store a reusable program |
| GET | `/api/v1/asp/programs` | List stored programs |

### ASP Conversation Endpoints (NL Interface)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/asp/conversations` | Create session |
| POST | `/api/v1/asp/conversations/{id}/chat` | Send message |
| POST | `/api/v1/asp/conversations/{id}/apply` | Apply changes |
| POST | `/api/v1/asp/conversations/{id}/reset` | Reset session |
| DELETE | `/api/v1/asp/conversations/{id}` | Delete session |

### Example API Calls

**Solve a Program**:
```bash
curl -X POST http://localhost:8080/api/v1/asp/solve \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: default" \
  -d '{
    "problem": {
      "source": "{ a; b; c }. :- not a. #show."
    },
    "max_models": 5
  }'
```

**Start NL Conversation**:
```bash
# Create session
SESSION=$(curl -s -X POST http://localhost:8080/api/v1/asp/conversations \
  -H "X-Tenant-ID: default" | jq -r '.session_id')

# Chat
curl -X POST "http://localhost:8080/api/v1/asp/conversations/$SESSION/chat" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: default" \
  -d '{
    "message": "Create a graph coloring program for 3 colors"
  }'
```

---

## Extending the Example

### Add Real-Time Data

Connect to SCADA/EMS systems to fetch live grid state:

```python
def fetch_live_data():
    # Poll SCADA via OPC-UA, ICCP, or REST
    readings = scada_client.get_measurements()

    # Update digital twin
    for reading in readings:
        client.twins.update(reading["twin_id"], {
            "properties": {
                "currentOutput": reading["value"],
                "timestamp": reading["time"]
            }
        })
```

### Add Weather Forecasting

Incorporate weather forecasts for renewable prediction:

```python
def update_renewable_forecast():
    weather = fetch_weather_forecast()  # From weather API

    for farm in solar_farms:
        # Calculate expected output from irradiance
        expected = calculate_solar_output(farm, weather["irradiance"])
        client.twins.update(farm["id"], {
            "properties": {"forecastedOutput": expected}
        })
```

### Custom ASP Rules

Create domain-specific rules for your grid:

```prolog
% Must-run units (e.g., nuclear for baseload)
:- not commit("plant-nuclear-001").

% Environmental zone restrictions
:- commit(G), generator(G, "Coal", _, _, _), peak_ozone_day.

% Maintenance windows
:- commit(G), maintenance_scheduled(G, today).

% Transmission limits
:- line_flow(L, F), line_capacity(L, C), F > C.
```

---

## Troubleshooting

### Common Issues

**"No generators found"**
```bash
# Make sure you've seeded the data first
python seed.py
```

**"ASP solver error"**
```bash
# Check server logs for clingo errors
# Verify ASP syntax (balanced braces, periods at end)
```

**"LLM not configured"**
```toml
# In config.toml, ensure LLM is configured:
[llm]
primary_provider = "ollama"

[llm.providers.ollama]
endpoint = "http://localhost:11434"
model = "llama3.2"
```

**"Connection refused"**
```bash
# Make sure TesseraiDB is running
cargo run --release --bin tesseraidb

# Check health
curl http://localhost:8080/health
```

### Debug Tips

1. **Enable verbose logging**:
   ```bash
   RUST_LOG=debug cargo run --release --bin tesseraidb
   ```

2. **Test ASP program standalone**:
   ```bash
   # Install clingo locally
   brew install clingo  # macOS
   apt install gringo   # Ubuntu

   # Test program
   echo "{ a; b }. :- not a." | clingo -
   ```

3. **Check Swagger UI**: Visit `http://localhost:8080/swagger-ui/` for interactive API docs.

---

## References

- [Clingo User Guide](https://potassco.org/clingo/)
- [ASP Tutorial](https://teaching.potassco.org/)
- [Model-Based Diagnosis](https://en.wikipedia.org/wiki/Model-based_diagnosis)
- [Unit Commitment Problem](https://en.wikipedia.org/wiki/Unit_commitment_problem_in_electrical_power_production)
- [NERC Reliability Standards](https://www.nerc.com/pa/Stand/Pages/default.aspx)

---

## License

This example is part of TesseraiDB and is provided under the same license.

## Contributing

Contributions welcome! Please see the main repository's CONTRIBUTING.md for guidelines.
