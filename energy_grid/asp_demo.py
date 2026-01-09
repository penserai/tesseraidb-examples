#!/usr/bin/env python3
"""
Energy Grid ASP (Answer Set Programming) Demonstration

This example demonstrates how to use Answer Set Programming (ASP) with TesseraiDB
to solve complex energy grid optimization and diagnostic problems.

ASP Use Cases Demonstrated:
1. Unit Commitment - Which generators to turn on/off to meet demand at minimum cost
2. Economic Dispatch - Optimal power output from each active generator
3. Fault Diagnosis - Identify faulty components from observed symptoms
4. N-1 Contingency Analysis - Ensure grid stability if any single component fails

Requirements:
    - TesseraiDB server running at http://localhost:8080
    - Energy grid digital twin seeded (run seed.py first)
    - LLM configured for natural language ASP conversation (optional)

Usage:
    # First seed the energy grid
    python seed.py

    # Then run this demo
    python asp_demo.py

    # Or run specific demos
    python asp_demo.py --demo unit-commitment
    python asp_demo.py --demo fault-diagnosis
    python asp_demo.py --demo contingency
    python asp_demo.py --demo conversation  # NL interface demo
"""

import sys
import os
import json
import argparse
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import get_client, logger

# =============================================================================
# SPARQL Queries to Extract Grid State
# =============================================================================

QUERY_GENERATORS = """
PREFIX dt: <https://tesserai.dev/ontology/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?id ?name ?type ?capacity ?output ?efficiency ?emissions ?status
WHERE {
    ?gen a ?genType .
    FILTER(CONTAINS(STR(?genType), "PowerPlant") || CONTAINS(STR(?genType), "Farm"))

    ?gen dt:id ?id .
    OPTIONAL { ?gen dt:name ?name }
    OPTIONAL { ?gen dt:capacity ?capacity }
    OPTIONAL { ?gen dt:currentOutput ?output }
    OPTIONAL { ?gen dt:efficiency ?efficiency }
    OPTIONAL { ?gen dt:emissionsFactor ?emissions }
    OPTIONAL { ?gen dt:status ?status }

    BIND(REPLACE(STR(?genType), ".*#", "") AS ?type)
}
ORDER BY ?id
"""

QUERY_GRID_STATE = """
PREFIX dt: <https://tesserai.dev/ontology/>

SELECT ?totalCapacity ?currentLoad ?peakLoad ?frequency ?renewablePercentage
WHERE {
    ?grid a dt:PowerGrid .
    ?grid dt:totalCapacity ?totalCapacity .
    ?grid dt:currentLoad ?currentLoad .
    ?grid dt:peakLoad ?peakLoad .
    ?grid dt:frequency ?frequency .
    ?grid dt:renewablePercentage ?renewablePercentage .
}
"""

QUERY_SUBSTATIONS = """
PREFIX dt: <https://tesserai.dev/ontology/>

SELECT ?id ?name ?voltage ?capacity ?load ?status
WHERE {
    ?sub a ?subType .
    FILTER(CONTAINS(STR(?subType), "Substation"))

    ?sub dt:id ?id .
    OPTIONAL { ?sub dt:name ?name }
    OPTIONAL { ?sub dt:voltageLevel ?voltage }
    OPTIONAL { ?sub dt:capacity ?capacity }
    OPTIONAL { ?sub dt:currentLoad ?load }
    OPTIONAL { ?sub dt:status ?status }
}
"""

QUERY_TRANSMISSION_LINES = """
PREFIX dt: <https://tesserai.dev/ontology/>

SELECT ?id ?name ?voltage ?capacity ?flow ?status
WHERE {
    ?line a dt:TransmissionLine .
    ?line dt:id ?id .
    OPTIONAL { ?line dt:name ?name }
    OPTIONAL { ?line dt:voltage ?voltage }
    OPTIONAL { ?line dt:capacity ?capacity }
    OPTIONAL { ?line dt:currentFlow ?flow }
    OPTIONAL { ?line dt:status ?status }
}
"""

QUERY_BATTERIES = """
PREFIX dt: <https://tesserai.dev/ontology/>

SELECT ?id ?name ?capacity ?power ?soc ?status
WHERE {
    ?bat a dt:BatteryStorage .
    ?bat dt:id ?id .
    OPTIONAL { ?bat dt:name ?name }
    OPTIONAL { ?bat dt:capacity ?capacity }
    OPTIONAL { ?bat dt:power ?power }
    OPTIONAL { ?bat dt:stateOfCharge ?soc }
    OPTIONAL { ?bat dt:status ?status }
}
"""


# =============================================================================
# ASP Program Templates
# =============================================================================

UNIT_COMMITMENT_PROGRAM = '''
% =============================================================================
% UNIT COMMITMENT PROBLEM
% =============================================================================
% Decide which generators to turn on/off to meet demand at minimum cost
% while respecting operational constraints.

% --- Generator Data (from digital twin) ---
{generator_facts}

% --- Demand and Reserve Requirements ---
demand({demand}).
reserve_margin({reserve}).  % Required spinning reserve (MW)

% --- Decision: Which generators to commit ---
{{ commit(G) }} :- generator(G, _, _, _, _).

% --- Power Output Bounds ---
% If committed, output between min and max capacity
output(G, Min) :- commit(G), generator(G, _, Max, _, _), Min = Max / 4.
output(G, Max) :- commit(G), generator(G, _, Max, _, _).

% For now, assume output at 80% of capacity when committed
actual_output(G, Out) :- commit(G), generator(G, _, Max, _, _), Out = (Max * 80) / 100.
actual_output(G, 0) :- generator(G, _, _, _, _), not commit(G).

% --- Constraint: Meet Demand ---
total_output(Total) :- Total = #sum {{ Out,G : actual_output(G, Out) }}.
:- total_output(Total), demand(D), Total < D.

% --- Constraint: Spinning Reserve ---
total_capacity(Cap) :- Cap = #sum {{ Max,G : commit(G), generator(G, _, Max, _, _) }}.
:- total_capacity(Cap), demand(D), reserve_margin(R), Cap < D + R.

% --- Cost Calculation ---
% Cost = fuel_cost * output + startup_cost (simplified: just variable cost)
gen_cost(G, Cost) :- actual_output(G, Out), generator(G, _, _, _, VarCost), Cost = Out * VarCost.
total_cost(TC) :- TC = #sum {{ Cost,G : gen_cost(G, Cost) }}.

% --- Emissions Calculation ---
gen_emissions(G, E) :- actual_output(G, Out), generator(G, _, _, Emissions, _), E = Out * Emissions.
total_emissions(TE) :- TE = #sum {{ E,G : gen_emissions(G, E) }}.

% --- Optimization: Minimize Cost ---
#minimize {{ Cost@1,G : gen_cost(G, Cost) }}.

% --- Show Results ---
#show commit/1.
#show actual_output/2.
#show total_cost/1.
#show total_emissions/1.
'''

FAULT_DIAGNOSIS_PROGRAM = '''
% =============================================================================
% FAULT DIAGNOSIS PROBLEM
% =============================================================================
% Given observed symptoms (alarms, measurements), identify faulty components
% using model-based diagnosis with abductive reasoning.

% --- System Components (from digital twin) ---
{component_facts}

% --- Normal Behavior Rules ---
% If a generator is working and committed, it produces power
produces_power(G) :- generator(G), working(G), committed(G).

% If a transmission line is working, it can transfer power
can_transfer(L) :- transmission_line(L), working(L).

% If a substation is working, it can transform voltage
can_transform(S) :- substation(S), working(S).

% Power flows through working paths
power_available(S) :- substation(S),
                      produces_power(G),
                      connected(G, L),
                      can_transfer(L),
                      connected(L, S).

% --- Abducibles: Components may be faulty ---
{{ faulty(C) }} :- component(C).
working(C) :- component(C), not faulty(C).

% --- Observations (symptoms from SCADA) ---
{observation_facts}

% --- Diagnosis Constraints ---
% If we observe no power at substation, there must be an explanation
:- obs_no_power(S), power_available(S).

% If we observe power available, it shouldn't be missing
:- obs_power_ok(S), not power_available(S).

% If we observe line fault alarm, line should be faulty
:- obs_line_fault(L), working(L).

% If generator output is zero unexpectedly, it's faulty
:- obs_gen_zero(G), committed(G), working(G).

% --- Minimize number of faults (parsimony principle) ---
#minimize {{ 1,C : faulty(C) }}.

% --- Show Diagnosis ---
#show faulty/1.
'''

N1_CONTINGENCY_PROGRAM = '''
% =============================================================================
% N-1 CONTINGENCY ANALYSIS
% =============================================================================
% Verify that the grid remains stable if any single component fails.
% Find configurations that would cause cascading failures.

% --- Grid Topology (from digital twin) ---
{topology_facts}

% --- Simulate single component failure ---
1 {{ failed(C) : critical_component(C) }} 1.

% --- Component still operational if not failed ---
operational(C) :- component(C), not failed(C).

% --- Power Flow Analysis (simplified) ---
% A load can be served if there's a path from a generator
can_serve(Load) :- load(Load),
                   generator(G), operational(G),
                   path(G, Load).

% Path exists through operational components
path(X, Y) :- connected(X, Y), operational(X), operational(Y).
path(X, Z) :- path(X, Y), connected(Y, Z), operational(Z).

% --- Constraint: All critical loads must be served ---
critical_unserved(L) :- critical_load(L), not can_serve(L).

% --- Find vulnerable configurations ---
#show failed/1.
#show critical_unserved/1.
'''

BATTERY_SCHEDULE_PROGRAM = '''
% =============================================================================
% BATTERY SCHEDULING WITH RENEWABLE FORECAST
% =============================================================================
% Optimize battery charge/discharge schedule to maximize renewable utilization
% and minimize grid costs.

% --- Time Periods (e.g., hourly for 24 hours) ---
time(0..23).

% --- Battery Parameters ---
{battery_facts}

% --- Renewable Forecast (MW available each hour) ---
{renewable_forecast}

% --- Demand Forecast (MW needed each hour) ---
{demand_forecast}

% --- Battery Decisions ---
% Each hour: charge, discharge, or idle
1 {{ charge(B, T); discharge(B, T); idle(B, T) }} 1 :- battery(B, _, _), time(T).

% --- State of Charge Dynamics ---
% Initial SOC
soc(B, 0, Init) :- battery(B, _, Init).

% SOC evolution
soc(B, T+1, SOC+Rate) :- soc(B, T, SOC), charge(B, T), battery(B, Rate, _), T < 23.
soc(B, T+1, SOC-Rate) :- soc(B, T, SOC), discharge(B, T), battery(B, Rate, _), T < 23.
soc(B, T+1, SOC) :- soc(B, T, SOC), idle(B, T), T < 23.

% --- Constraints ---
% SOC bounds (0-100%)
:- soc(B, T, SOC), SOC < 10.  % Minimum 10%
:- soc(B, T, SOC), SOC > 95.  % Maximum 95%

% Charge only when excess renewables
should_charge(T) :- time(T), renewable(T, R), demand(T, D), R > D.
:- charge(B, T), not should_charge(T).

% Discharge to reduce peak demand
peak_hour(T) :- demand(T, D), D > 10000.
:- peak_hour(T), not discharge(_, T), battery(_, _, _).

% --- Optimization ---
% Maximize renewable utilization (minimize curtailment)
curtailed(T, C) :- renewable(T, R), demand(T, D),
                   TotalCharge = #sum {{ Rate,B : charge(B, T), battery(B, Rate, _) }},
                   C = R - D - TotalCharge, C > 0.

#minimize {{ C,T : curtailed(T, C) }}.

% --- Results ---
#show charge/2.
#show discharge/2.
#show soc/3.
#show curtailed/2.
'''


# =============================================================================
# Helper Functions
# =============================================================================

def fetch_grid_data(client) -> dict:
    """Fetch current grid state from digital twin."""
    logger.info("Fetching grid data from digital twin...")

    data = {
        "generators": [],
        "substations": [],
        "lines": [],
        "batteries": [],
        "grid": {}
    }

    # Fetch generators
    try:
        result = client.query.select(QUERY_GENERATORS)
        for binding in result.bindings:
            data["generators"].append({
                "id": str(binding.get("id", "")),
                "name": str(binding.get("name", "")),
                "type": str(binding.get("type", "")),
                "capacity": float(binding.get("capacity", 0)),
                "output": float(binding.get("output", 0)),
                "efficiency": float(binding.get("efficiency", 0)),
                "emissions": float(binding.get("emissions", 0)),
                "status": str(binding.get("status", ""))
            })
    except Exception as e:
        logger.warning(f"Could not fetch generators: {e}")

    # Fetch grid state
    try:
        result = client.query.select(QUERY_GRID_STATE)
        if result.bindings:
            b = result.bindings[0]
            data["grid"] = {
                "totalCapacity": float(b.get("totalCapacity", 0)),
                "currentLoad": float(b.get("currentLoad", 0)),
                "peakLoad": float(b.get("peakLoad", 0)),
                "frequency": float(b.get("frequency", 60)),
                "renewablePercentage": float(b.get("renewablePercentage", 0))
            }
    except Exception as e:
        logger.warning(f"Could not fetch grid state: {e}")

    # Fetch substations
    try:
        result = client.query.select(QUERY_SUBSTATIONS)
        for binding in result.bindings:
            data["substations"].append({
                "id": str(binding.get("id", "")),
                "name": str(binding.get("name", "")),
                "voltage": float(binding.get("voltage", 0)),
                "capacity": float(binding.get("capacity", 0)),
                "load": float(binding.get("load", 0)),
                "status": str(binding.get("status", ""))
            })
    except Exception as e:
        logger.warning(f"Could not fetch substations: {e}")

    # Fetch transmission lines
    try:
        result = client.query.select(QUERY_TRANSMISSION_LINES)
        for binding in result.bindings:
            data["lines"].append({
                "id": str(binding.get("id", "")),
                "name": str(binding.get("name", "")),
                "voltage": float(binding.get("voltage", 0)),
                "capacity": float(binding.get("capacity", 0)),
                "flow": float(binding.get("flow", 0)),
                "status": str(binding.get("status", ""))
            })
    except Exception as e:
        logger.warning(f"Could not fetch lines: {e}")

    # Fetch batteries
    try:
        result = client.query.select(QUERY_BATTERIES)
        for binding in result.bindings:
            data["batteries"].append({
                "id": str(binding.get("id", "")),
                "name": str(binding.get("name", "")),
                "capacity": float(binding.get("capacity", 0)),
                "power": float(binding.get("power", 0)),
                "soc": float(binding.get("soc", 0)),
                "status": str(binding.get("status", ""))
            })
    except Exception as e:
        logger.warning(f"Could not fetch batteries: {e}")

    logger.info(f"Fetched {len(data['generators'])} generators, "
                f"{len(data['substations'])} substations, "
                f"{len(data['lines'])} lines, "
                f"{len(data['batteries'])} batteries")

    return data


def generate_asp_facts(data: dict) -> str:
    """Convert digital twin data to ASP facts."""
    facts = []

    # Generator facts: generator(id, type, capacity, emissions, variable_cost)
    # Variable cost approximation based on type
    cost_by_type = {
        "Coal": 35,
        "NaturalGas": 45,
        "Nuclear": 10,
        "Hydroelectric": 5,
        "Solar": 0,
        "Wind": 0
    }

    for gen in data["generators"]:
        gen_type = gen["type"].replace("PowerPlant", "").replace("Farm", "")
        var_cost = cost_by_type.get(gen_type, 30)
        facts.append(f'generator("{gen["id"]}", "{gen_type}", {int(gen["capacity"])}, '
                    f'{int(gen["emissions"])}, {var_cost}).')

    return "\n".join(facts)


def generate_component_facts(data: dict) -> str:
    """Generate component facts for fault diagnosis."""
    facts = []

    for gen in data["generators"]:
        facts.append(f'component("{gen["id"]}").')
        facts.append(f'generator("{gen["id"]}").')
        if gen["status"] == "generating":
            facts.append(f'committed("{gen["id"]}").')

    for sub in data["substations"]:
        facts.append(f'component("{sub["id"]}").')
        facts.append(f'substation("{sub["id"]}").')

    for line in data["lines"]:
        facts.append(f'component("{line["id"]}").')
        facts.append(f'transmission_line("{line["id"]}").')

    return "\n".join(facts)


# =============================================================================
# Demo Functions
# =============================================================================

def demo_unit_commitment(client):
    """
    Demonstrate Unit Commitment optimization.

    Problem: Given forecasted demand and available generators, decide which
    generators to commit (turn on) to meet demand at minimum cost while
    maintaining required spinning reserve.
    """
    print("\n" + "="*70)
    print("DEMO 1: UNIT COMMITMENT OPTIMIZATION")
    print("="*70)
    print("""
This demo solves the Unit Commitment problem using ASP:
- Given: Demand forecast, generator capacities, costs, emissions
- Decide: Which generators to turn on
- Objective: Minimize total operating cost
- Constraints:
  * Meet demand
  * Maintain spinning reserve margin
  * Respect generator limits
""")

    # Fetch data
    data = fetch_grid_data(client)

    if not data["generators"]:
        print("ERROR: No generators found. Run seed.py first.")
        return

    # Generate ASP facts
    gen_facts = generate_asp_facts(data)
    demand = int(data["grid"].get("currentLoad", 10000))
    reserve = 1000  # 1000 MW spinning reserve

    print(f"\nCurrent Grid State:")
    print(f"  - Demand: {demand} MW")
    print(f"  - Reserve Requirement: {reserve} MW")
    print(f"  - Available Generators: {len(data['generators'])}")

    print("\nGenerator Data:")
    print("-" * 80)
    print(f"{'ID':<20} {'Type':<15} {'Capacity':>10} {'Emissions':>12} {'Status':<12}")
    print("-" * 80)
    for gen in data["generators"]:
        print(f"{gen['id']:<20} {gen['type']:<15} {gen['capacity']:>10.0f} MW "
              f"{gen['emissions']:>8.0f} g/kWh  {gen['status']:<12}")

    # Build a simplified, working ASP program
    # Using simple atom names (no quotes) for compatibility
    gen_facts_simple = []
    for i, gen in enumerate(data["generators"][:8], 1):  # Limit to 8 generators
        gen_type = gen["type"].replace("PowerPlant", "").replace("Farm", "")
        cap = int(gen["capacity"])
        emissions = int(gen["emissions"])
        cost = {"Coal": 35, "NaturalGas": 45, "Nuclear": 10, "Hydroelectric": 5}.get(gen_type, 0)
        gen_facts_simple.append(f"gen(g{i}, {cap}, {emissions}, {cost}).")

    program = f"""
% =============================================================================
% UNIT COMMITMENT PROBLEM
% =============================================================================

% Generator data: gen(ID, Capacity_MW, Emissions_gCO2_kWh, Cost_$_MWh)
{chr(10).join(gen_facts_simple)}

% Demand and reserve requirements
demand({demand}).
reserve({reserve}).

% Decision: which generators to commit
{{ commit(G) }} :- gen(G, _, _, _).

% Calculate output (80% of capacity when committed)
output(G, O) :- commit(G), gen(G, Cap, _, _), O = Cap * 8 / 10.

% Total output from all committed generators
total_output(T) :- T = #sum {{ O,G : output(G, O) }}.

% Total capacity of committed generators
total_capacity(C) :- C = #sum {{ Cap,G : commit(G), gen(G, Cap, _, _) }}.

% Constraint: meet demand
:- total_output(T), demand(D), T < D.

% Constraint: maintain spinning reserve
:- total_capacity(C), demand(D), reserve(R), C < D + R.

% Cost calculation
gen_cost(G, Cost) :- output(G, O), gen(G, _, _, VarCost), Cost = O * VarCost.
total_cost(TC) :- TC = #sum {{ Cost,G : gen_cost(G, Cost) }}.

% Emissions calculation
gen_emissions(G, E) :- output(G, O), gen(G, _, EmFactor, _), E = O * EmFactor.
total_emissions(TE) :- TE = #sum {{ E,G : gen_emissions(G, E) }}.

% Minimize total cost
#minimize {{ Cost@1,G : gen_cost(G, Cost) }}.

% Show results
#show commit/1.
#show total_cost/1.
#show total_emissions/1.
"""

    print("\n" + "-"*70)
    print("Solving with ASP (clingo)...")
    print("-"*70)

    # Call ASP solver
    try:
        result = client.asp.solve(source=program, max_models=1, optimize=True)

        if result.satisfiable:
            print("\nSOLUTION FOUND!")
            print("\nCommitted Generators:")
            print("-" * 60)

            for answer_set in result.answer_sets:
                symbols = answer_set.symbols

                # Parse committed generators
                committed = [s for s in symbols if s.startswith("commit(")]
                for c in committed:
                    gen_id = c.replace("commit(", "").rstrip(")")
                    # Find matching generator
                    idx = int(gen_id[1:]) - 1 if gen_id.startswith("g") else 0
                    if idx < len(data["generators"]):
                        gen = data["generators"][idx]
                        out = int(gen["capacity"] * 0.8)
                        print(f"  [ON] {gen['id']}: {out} MW ({gen['type']})")

                # Parse totals
                for s in symbols:
                    if s.startswith("total_cost("):
                        cost = s.replace("total_cost(", "").rstrip(")")
                        print(f"\nTotal Cost: ${cost}/hour")
                    elif s.startswith("total_emissions("):
                        em = s.replace("total_emissions(", "").rstrip(")")
                        print(f"Total Emissions: {em} kg CO2/hour")

                if answer_set.is_optimal:
                    print("\n[OPTIMAL SOLUTION]")

        else:
            print("\nNo solution found - demand cannot be met with available generators!")

    except Exception as e:
        print(f"\nASP Solver Error: {e}")
        print("\nMake sure the ASP endpoint is available and clingo is working.")


def demo_fault_diagnosis(client):
    """
    Demonstrate Fault Diagnosis using ASP.

    Problem: Given observed symptoms (alarms, zero readings), identify the
    minimal set of faulty components that explain all observations.
    """
    print("\n" + "="*70)
    print("DEMO 2: FAULT DIAGNOSIS")
    print("="*70)
    print("""
This demo uses ASP for Model-Based Diagnosis:
- Given: System model, observed symptoms
- Find: Minimal set of faulty components
- Method: Abductive reasoning with parsimony
- Principle: Prefer simpler explanations (fewer faults)
""")

    print("\nSimulated Fault Scenario:")
    print("  - Substation sub3: No power detected")
    print("  - Line line2: Fault alarm triggered")
    print("  - Generator gen2: Zero output (unexpected)")

    # Simplified diagnosis program that works
    diagnosis_program = """
% =============================================================================
% FAULT DIAGNOSIS - Simplified Model
% =============================================================================

% Components in the system
component(gen1). component(gen2). component(gen3).
component(line1). component(line2). component(line3).
component(sub1). component(sub2). component(sub3).

% Component types
generator(gen1). generator(gen2). generator(gen3).
line(line1). line(line2). line(line3).
substation(sub1). substation(sub2). substation(sub3).

% Topology: generators connect through lines to substations
connects(gen1, line1). connects(line1, sub1).
connects(gen2, line2). connects(line2, sub2).
connects(sub2, line3). connects(line3, sub3).
connects(gen3, line1).

% Abducibles: any component may be faulty
{ faulty(C) } :- component(C).
working(C) :- component(C), not faulty(C).

% Power propagation (simplified)
has_power(G) :- generator(G), working(G).
has_power(S) :- substation(S), has_power(L), connects(L, S), working(S).
has_power(L) :- line(L), has_power(X), connects(X, L), working(L).

% Observations (from SCADA system)
% obs1: Substation sub3 has no power
:- has_power(sub3).

% obs2: Line2 triggered fault alarm (so it must be faulty)
:- working(line2).

% obs3: Generator gen2 output is zero unexpectedly
:- working(gen2).

% Minimize the number of faults (parsimony)
#minimize { 1,C : faulty(C) }.

% Show which components are faulty
#show faulty/1.
"""

    print("\n" + "-"*70)
    print("Running Diagnosis with ASP...")
    print("-"*70)

    try:
        result = client.asp.solve(source=diagnosis_program, max_models=3, optimize=True)

        if result.satisfiable:
            print("\nDIAGNOSIS RESULTS:")
            print("-" * 60)

            for i, answer_set in enumerate(result.answer_sets, 1):
                faults = [s for s in answer_set.symbols if s.startswith("faulty(")]

                print(f"\nDiagnosis {i} (cardinality: {len(faults)}):")
                for f in faults:
                    comp = f.replace("faulty(", "").rstrip(")")
                    comp_type = "Generator" if comp.startswith("gen") else \
                               "Line" if comp.startswith("line") else "Substation"
                    print(f"  - FAULTY: {comp} ({comp_type})")

                if answer_set.is_optimal:
                    print("  [OPTIMAL - Minimal diagnosis]")

            print("\n" + "-" * 60)
            print("Interpretation:")
            print("  The diagnosis shows the minimal set of component failures")
            print("  that explains all observed symptoms.")
        else:
            print("\nNo diagnosis found - observations are inconsistent with model.")

    except Exception as e:
        print(f"\nASP Solver Error: {e}")
        print("\nNote: Make sure the ASP endpoint is available.")


def demo_contingency_analysis(client):
    """
    Demonstrate N-1 Contingency Analysis using ASP.

    Problem: For each critical component, verify that the grid remains
    operational if that component fails.
    """
    print("\n" + "="*70)
    print("DEMO 3: N-1 CONTINGENCY ANALYSIS")
    print("="*70)
    print("""
This demo performs N-1 Contingency Analysis:
- Question: What happens if any single component fails?
- Method: Enumerate single-failure scenarios
- Goal: Identify vulnerable configurations
- Output: Components whose failure would cause outages
""")

    # Simplified contingency program
    program = """
% =============================================================================
% N-1 CONTINGENCY ANALYSIS
% =============================================================================

% Grid topology (simplified)
% Generators
generator(nuclear). generator(gas1). generator(gas2). generator(hydro).

% Transmission lines
line(line1). line(line2). line(line3). line(line4).

% Substations and loads
substation(hv1). substation(hv2). substation(hv3).
load(dist1). load(dist2). load(dist3).
critical_load(dist1). critical_load(dist2).

% All components
component(C) :- generator(C).
component(C) :- line(C).
component(C) :- substation(C).

% Connectivity
path(nuclear, hv1). path(gas1, hv1). path(gas2, hv2). path(hydro, hv3).
path(hv1, line1). path(line1, hv2).
path(hv1, line2). path(line2, hv3).
path(hv2, line3). path(line3, hv3).
path(hv1, dist1). path(hv2, dist2). path(hv3, dist3).

% N-1: Simulate exactly one component failure
1 { failed(C) : component(C) } 1.

% Component is operational if not failed
operational(C) :- component(C), not failed(C).

% Reachability with operational components
reachable(G) :- generator(G), operational(G).
reachable(Y) :- reachable(X), path(X, Y), operational(Y).
reachable(Y) :- reachable(X), path(X, L), path(L, Y), operational(L), operational(Y).

% Load is served if reachable from any generator
served(L) :- load(L), reachable(L).

% Find critical loads that lose power
loses_power(L) :- critical_load(L), not served(L).

% We want to find failures that cause critical load loss
has_impact :- loses_power(_).

% Only show scenarios with impact
:- not has_impact.

#show failed/1.
#show loses_power/1.
"""

    print("\nCritical Components Under Analysis:")
    print("  - Generators: nuclear, gas1, gas2, hydro")
    print("  - Lines: line1, line2, line3, line4")
    print("  - Substations: hv1, hv2, hv3")
    print("  - Critical Loads: dist1, dist2")

    print("\n" + "-"*70)
    print("Analyzing contingencies...")
    print("-"*70)

    try:
        # Find all vulnerable configurations (where a single failure causes outage)
        result = client.asp.solve(source=program, max_models=20)

        print("\nCONTINGENCY RESULTS:")
        print("-" * 60)

        if result.satisfiable:
            vulnerable_count = 0
            seen = set()

            for answer_set in result.answer_sets:
                symbols = answer_set.symbols
                failed = [a for a in symbols if a.startswith("failed(")]
                loses = [a for a in symbols if a.startswith("loses_power(")]

                if loses:
                    failed_comp = failed[0].replace("failed(", "").rstrip(")") if failed else "unknown"
                    if failed_comp not in seen:
                        seen.add(failed_comp)
                        vulnerable_count += 1
                        print(f"\n[VULNERABLE] If '{failed_comp}' fails:")
                        for l in loses:
                            load = l.replace("loses_power(", "").rstrip(")")
                            print(f"  -> Critical load '{load}' would lose power!")

            if vulnerable_count == 0:
                print("\nGrid is N-1 secure - no single failure causes critical outages.")
            else:
                print(f"\nFound {vulnerable_count} vulnerable component(s)!")
                print("\nRecommendation: Add redundant paths to protect critical loads.")
        else:
            print("\nGrid is N-1 SECURE!")
            print("No single component failure causes loss of critical loads.")

    except Exception as e:
        print(f"\nContingency analysis error: {e}")


def demo_nl_conversation(client):
    """
    Demonstrate Natural Language ASP Conversation.

    Shows how to use the conversational interface to create and
    refine ASP programs through natural language.

    IMPORTANT: This demo requires an LLM to be configured on the server.
    The server uses the LLM to:
    - Understand natural language requests
    - Generate ASP programs from descriptions
    - Explain and debug existing programs
    - Provide optimization suggestions
    """
    print("\n" + "="*70)
    print("DEMO 4: NATURAL LANGUAGE ASP CONVERSATION")
    print("="*70)
    print("""
This demo shows the NL interface for ASP programming:
- Create ASP programs by describing problems in plain English
- Iteratively refine and debug programs
- Get explanations of ASP concepts
- Auto-execute and see results

NOTE: This demo invokes an LLM on the server for each message.
      Make sure the server has LLM configured (Anthropic, OpenAI, or Ollama).
""")

    print("\n" + "-"*70)
    print("Creating ASP conversation session...")
    print("-"*70)

    try:
        # Create a new conversation session
        session = client.asp_conversation.create_session()
        session_id = session.session_id
        print(f"Session created: {session_id}")

        # Example conversation - each message triggers LLM invocation
        conversations = [
            "Create a simple ASP program that models a power grid with 3 generators and finds which ones to turn on to meet 100 MW demand",
            "Add a constraint that we need at least 20 MW of reserve capacity",
            "Now add emissions data and minimize total emissions instead of cost",
            "Run the program and show me the optimal solution"
        ]

        for i, message in enumerate(conversations, 1):
            print(f"\n[User {i}]: {message}")
            print("-" * 50)
            print("  (Sending to server -> LLM invocation...)")

            start_time = time.time()

            response = client.asp_conversation.chat(
                session_id=session_id,
                message=message,
                auto_apply=(i == len(conversations))  # Auto-apply on last message
            )

            elapsed = time.time() - start_time
            print(f"  (Response received in {elapsed:.2f}s)")
            print(f"  Intent detected: {response.intent}")
            print(f"  Status: {response.status}")
            print()

            # Show full response (LLM-generated)
            print(f"[Assistant - LLM Generated]:")
            print(response.response)

            if response.proposed_program:
                print(f"\n[LLM-Generated ASP Program]:")
                print("-" * 40)
                print(response.proposed_program)
                print("-" * 40)

            if response.solve_result:
                print(f"\nExecution Result:")
                print(f"  Satisfiable: {response.solve_result.satisfiable}")
                if response.solve_result.answer_sets:
                    print(f"  Answer sets: {len(response.solve_result.answer_sets)}")
                    for j, ans in enumerate(response.solve_result.answer_sets[:2]):
                        print(f"  Answer set {j+1}: {ans.symbols[:10]}...")

            if response.suggestions:
                print(f"\n[LLM Suggestions]:")
                for sug in response.suggestions:
                    print(f"  - [{sug.category}] {sug.description}")

            if response.approval_required:
                print("\n[Applying proposed changes...]")
                apply_result = client.asp_conversation.apply_pending(session_id)
                print(f"Applied: {apply_result.applied}")

        # Clean up
        print("\n" + "-"*70)
        print("Cleaning up session...")
        client.asp_conversation.delete_session(session_id)
        print("Session deleted.")

    except Exception as e:
        print(f"\nConversation error: {e}")
        print("\nNote: This demo requires:")
        print("  1. ASP conversation endpoints available")
        print("  2. LLM configured on the server")
        print("\nTo configure LLM, set in config.toml:")
        print("  [llm]")
        print("  primary_provider = \"anthropic\"  # or \"openai\", \"ollama\"")
        print("  primary_model = \"claude-sonnet-4-20260514\"")
        print("  # For Anthropic: set ANTHROPIC_API_KEY env var")
        print("  # For OpenAI: set openai_api_key in config or OPENAI_API_KEY env var")
        print("  # For Ollama: set primary_base_url = \"http://localhost:11434\"")


def demo_all(client):
    """Run all demonstrations."""
    demo_unit_commitment(client)
    demo_fault_diagnosis(client)
    demo_contingency_analysis(client)
    demo_nl_conversation(client)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Energy Grid ASP Demonstration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python asp_demo.py                        # Run all demos
    python asp_demo.py --demo unit-commitment # Only unit commitment
    python asp_demo.py --demo fault-diagnosis # Only fault diagnosis
    python asp_demo.py --demo contingency     # Only N-1 analysis
    python asp_demo.py --demo conversation    # Only NL conversation
        """
    )
    parser.add_argument(
        "--demo",
        choices=["all", "unit-commitment", "fault-diagnosis", "contingency", "conversation"],
        default="all",
        help="Which demo to run (default: all)"
    )
    args = parser.parse_args()

    print("""
================================================================================
       ENERGY GRID ASP (Answer Set Programming) DEMONSTRATION
================================================================================

This demonstration shows how to use ASP with TesseraiDB for:
  * Unit Commitment Optimization
  * Fault Diagnosis
  * N-1 Contingency Analysis
  * Natural Language ASP Programming

Make sure you have:
  1. TesseraiDB running at http://localhost:8080
  2. Energy grid seeded (run: python seed.py)
================================================================================
""")

    client = get_client()

    # Verify connection
    try:
        health = client.health()
        print(f"Connected to TesseraiDB (version {health.version})")
    except Exception as e:
        print(f"ERROR: Cannot connect to TesseraiDB: {e}")
        print("Please make sure the server is running.")
        sys.exit(1)

    # Run selected demo
    demos = {
        "all": demo_all,
        "unit-commitment": demo_unit_commitment,
        "fault-diagnosis": demo_fault_diagnosis,
        "contingency": demo_contingency_analysis,
        "conversation": demo_nl_conversation
    }

    demos[args.demo](client)

    print("\n" + "="*70)
    print("DEMONSTRATION COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()
