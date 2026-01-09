#!/usr/bin/env python3
"""
Cascading Failure Analysis - Failure Propagation Simulation
============================================================

Simulates how failures propagate through interconnected infrastructure:
- Initiates failures at specified components
- Propagates through dependency relationships with realistic delays
- Tracks cascade depth and impact metrics
- Supports intervention scenarios

The simulation uses a discrete-event model with configurable time acceleration.

Usage:
    python simulation.py [--base-url URL] --trigger COMPONENT_ID
    python simulation.py --trigger sub-trans-001 --watch    # Watch cascade
    python simulation.py --scenario power-outage            # Pre-defined scenario
    python simulation.py --random-failure                   # Random failure

Scenarios:
    power-outage - Major substation failure
    datacenter-power - Data center power feed failure
    cooling-failure - Cooling system cascade
    network-partition - Core switch failure
"""

import sys
import os
import time
import random
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import heapq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import get_client, logger


class ComponentStatus(Enum):
    """Component operational status."""
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    IMPACTED = "impacted"
    FAILED = "failed"
    RECOVERED = "recovered"


@dataclass
class PropagationEvent:
    """Event in the failure propagation queue."""
    timestamp: float  # Simulation time in seconds
    source_id: str
    target_id: str
    dependency_type: str
    failure_probability: float
    severity: float

    def __lt__(self, other):
        return self.timestamp < other.timestamp


@dataclass
class CascadeMetrics:
    """Metrics for the failure cascade."""
    trigger_component: str
    trigger_time: datetime
    total_affected: int = 0
    direct_impacts: int = 0
    cascade_depth: int = 0
    max_severity: float = 0.0
    total_business_impact: float = 0.0
    estimated_mttr: float = 0.0
    affected_applications: List[str] = field(default_factory=list)
    affected_by_layer: Dict[str, int] = field(default_factory=dict)
    propagation_timeline: List[Dict] = field(default_factory=list)


class CascadeSimulator:
    """
    Failure cascade propagation simulator.

    Uses a discrete-event simulation approach where:
    1. Initial failure is injected at a trigger component
    2. Propagation events are queued based on dependency relationships
    3. Events are processed in time order
    4. Each event may trigger further cascades
    """

    # Dependency propagation characteristics
    DEPENDENCY_CONFIG = {
        "powerSupply": {
            "delay_seconds": 0,
            "probability": 1.0,
            "severity": 1.0,
        },
        "backupPower": {
            "delay_seconds": 30,
            "probability": 0.8,
            "severity": 0.6,
        },
        "networkConnectivity": {
            "delay_seconds": 5,
            "probability": 0.95,
            "severity": 0.8,
        },
        "cooling": {
            "delay_seconds": 300,  # 5 minutes for thermal issues
            "probability": 0.7,
            "severity": 0.9,
        },
        "control": {
            "delay_seconds": 10,
            "probability": 0.9,
            "severity": 0.85,
        },
        "material": {
            "delay_seconds": 3600,  # 1 hour for supply issues
            "probability": 0.5,
            "severity": 0.4,
        },
        "data": {
            "delay_seconds": 60,
            "probability": 0.6,
            "severity": 0.5,
        },
        "hosts": {
            "delay_seconds": 0,
            "probability": 1.0,
            "severity": 1.0,
        },
        "hasEquipment": {
            "delay_seconds": 0,
            "probability": 1.0,
            "severity": 0.9,
        },
        "dependsOn": {
            "delay_seconds": 5,
            "probability": 0.9,
            "severity": 0.8,
        },
    }

    def __init__(self, client, time_acceleration: float = 1.0):
        self.client = client
        self.time_acceleration = time_acceleration
        self.components: Dict[str, Dict] = {}
        self.dependencies: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.reverse_deps: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.status: Dict[str, ComponentStatus] = {}
        self.metrics: Optional[CascadeMetrics] = None

    def _normalize_rel_type(self, rel_type: str) -> str:
        """Normalize relationship type by stripping domain prefixes."""
        if '#' in rel_type:
            rel_type = rel_type.split('#', 1)[1]
        if rel_type.startswith('rel/'):
            rel_type = rel_type[4:]
        return rel_type

    def load_infrastructure(self):
        """Load all components and their dependencies."""
        try:
            twins = self.client.twins.list(domain="cascading_failure", page_size=200)

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                component_id = twin_dict["id"]

                # SDK model uses 'type_uri' not 'type'
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                self.components[component_id] = {
                    "id": component_id,
                    "name": twin_dict.get("name", component_id),
                    "type": type_val.split("#")[-1] if type_val else "",
                    "properties": twin_dict.get("properties", {}),
                    "relationships": [],
                }
                self.status[component_id] = ComponentStatus.OPERATIONAL

            # Load relationships separately (SDK list() doesn't include them)
            for component_id in self.components:
                try:
                    relationships = self.client.twins.get_relationships(component_id)
                    for rel in relationships:
                        rel_type = self._normalize_rel_type(rel.get("type", ""))
                        other_twin = rel.get("twin", rel.get("target", ""))
                        direction = rel.get("direction", "outgoing")

                        if other_twin and other_twin in self.components:
                            if direction == "outgoing":
                                self.dependencies[component_id].append((other_twin, rel_type))
                                self.reverse_deps[other_twin].append((component_id, rel_type))
                            else:
                                self.dependencies[other_twin].append((component_id, rel_type))
                                self.reverse_deps[component_id].append((other_twin, rel_type))
                except Exception as e:
                    logger.debug(f"No relationships for {component_id}: {e}")

            logger.info(f"Loaded {len(self.components)} components with "
                       f"{sum(len(d) for d in self.dependencies.values())} dependencies")

        except Exception as e:
            logger.error(f"Failed to load infrastructure: {e}")
            raise

    def get_downstream_components(self, component_id: str) -> List[Tuple[str, str]]:
        """Get components that depend on this one (will be affected by its failure)."""
        # Components where this one provides something TO them
        return self.dependencies.get(component_id, [])

    def _resolve_component_id(self, component_id: str) -> str:
        """Resolve a short component ID to full URN if needed."""
        if component_id in self.components:
            return component_id
        # Try with URN prefix
        full_id = f"urn:tesserai:twin:{component_id}"
        if full_id in self.components:
            return full_id
        return component_id  # Return original if not found

    def inject_failure(self, component_id: str) -> CascadeMetrics:
        """
        Inject a failure at the specified component and simulate cascade.
        """
        component_id = self._resolve_component_id(component_id)
        if component_id not in self.components:
            raise ValueError(f"Component {component_id} not found")

        # Initialize metrics
        self.metrics = CascadeMetrics(
            trigger_component=component_id,
            trigger_time=datetime.now(),
        )

        # Event queue (priority queue by time)
        event_queue: List[PropagationEvent] = []
        processed: Set[str] = set()
        current_time = 0.0

        # Initial failure
        self.status[component_id] = ComponentStatus.FAILED
        processed.add(component_id)
        self.metrics.total_affected = 1
        self.metrics.direct_impacts = 0

        component = self.components[component_id]
        self.metrics.propagation_timeline.append({
            "time": 0,
            "component": component_id,
            "name": component["name"],
            "type": component["type"],
            "status": "FAILED",
            "cascade_level": 0,
        })

        business_impact = component["properties"].get("businessImpact", 5)
        self.metrics.total_business_impact += business_impact
        self.metrics.max_severity = 1.0

        # Queue initial propagation events
        for target_id, dep_type in self.get_downstream_components(component_id):
            if target_id not in processed and target_id in self.components:
                config = self.DEPENDENCY_CONFIG.get(dep_type, {
                    "delay_seconds": 10,
                    "probability": 0.5,
                    "severity": 0.5,
                })

                heapq.heappush(event_queue, PropagationEvent(
                    timestamp=config["delay_seconds"],
                    source_id=component_id,
                    target_id=target_id,
                    dependency_type=dep_type,
                    failure_probability=config["probability"],
                    severity=config["severity"],
                ))

        # Process event queue
        cascade_level = 1
        while event_queue:
            event = heapq.heappop(event_queue)

            if event.target_id in processed:
                continue

            # Check if failure propagates (probabilistic)
            if random.random() > event.failure_probability:
                continue

            # Failure propagates
            processed.add(event.target_id)
            current_time = event.timestamp

            # Determine impact level based on severity
            if event.severity >= 0.9:
                new_status = ComponentStatus.FAILED
            elif event.severity >= 0.6:
                new_status = ComponentStatus.IMPACTED
            else:
                new_status = ComponentStatus.DEGRADED

            self.status[event.target_id] = new_status

            target = self.components[event.target_id]
            self.metrics.total_affected += 1
            self.metrics.direct_impacts += 1
            self.metrics.cascade_depth = max(self.metrics.cascade_depth, cascade_level)

            # Track by component type
            comp_type = target["type"]
            self.metrics.affected_by_layer[comp_type] = \
                self.metrics.affected_by_layer.get(comp_type, 0) + 1

            # Track applications
            if target["type"] == "Application":
                self.metrics.affected_applications.append(event.target_id)

            # Update business impact
            impact = target["properties"].get("businessImpact", 5) * event.severity
            self.metrics.total_business_impact += impact

            # Update severity tracking
            self.metrics.max_severity = max(self.metrics.max_severity, event.severity)

            # Add to timeline
            self.metrics.propagation_timeline.append({
                "time": event.timestamp,
                "component": event.target_id,
                "name": target["name"],
                "type": target["type"],
                "status": new_status.value.upper(),
                "cascade_level": cascade_level,
                "triggered_by": event.source_id,
                "dependency_type": event.dependency_type,
                "severity": event.severity,
            })

            # Queue further propagation
            for next_target, dep_type in self.get_downstream_components(event.target_id):
                if next_target not in processed and next_target in self.components:
                    config = self.DEPENDENCY_CONFIG.get(dep_type, {
                        "delay_seconds": 10,
                        "probability": 0.5,
                        "severity": 0.5,
                    })

                    # Cascade severity diminishes
                    cascaded_severity = event.severity * config["severity"]

                    heapq.heappush(event_queue, PropagationEvent(
                        timestamp=current_time + config["delay_seconds"],
                        source_id=event.target_id,
                        target_id=next_target,
                        dependency_type=dep_type,
                        failure_probability=config["probability"] * event.severity,
                        severity=cascaded_severity,
                    ))

            cascade_level += 1

        # Estimate MTTR based on affected components
        mttr_by_type = {
            "PowerPlant": 24,
            "Substation": 8,
            "ServerRack": 2,
            "Application": 1,
            "NetworkSwitch": 1,
            "CoolingUnit": 4,
            "ProductionLine": 6,
        }

        total_mttr = 0
        for comp_id, status in self.status.items():
            if status in [ComponentStatus.FAILED, ComponentStatus.IMPACTED]:
                comp_type = self.components[comp_id]["type"]
                total_mttr = max(total_mttr, mttr_by_type.get(comp_type, 2))

        self.metrics.estimated_mttr = total_mttr

        return self.metrics

    def get_affected_components(self) -> List[Dict]:
        """Get list of all affected components with their status."""
        affected = []
        for comp_id, status in self.status.items():
            if status != ComponentStatus.OPERATIONAL:
                comp = self.components[comp_id]
                affected.append({
                    "id": comp_id,
                    "name": comp["name"],
                    "type": comp["type"],
                    "status": status.value,
                    "business_impact": comp["properties"].get("businessImpact", 5),
                })
        return sorted(affected, key=lambda x: -x["business_impact"])

    def reset(self):
        """Reset all components to operational status."""
        for comp_id in self.status:
            self.status[comp_id] = ComponentStatus.OPERATIONAL
        self.metrics = None


def print_cascade_report(metrics: CascadeMetrics, affected: List[Dict]):
    """Print detailed cascade report."""
    print("\n" + "=" * 80)
    print(" CASCADING FAILURE ANALYSIS REPORT")
    print(" Triggered: " + metrics.trigger_time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 80)

    print(f"\n TRIGGER: {metrics.trigger_component}")

    print("\n IMPACT SUMMARY")
    print("-" * 80)
    print(f" Total Components Affected: {metrics.total_affected}")
    print(f" Maximum Cascade Depth:     {metrics.cascade_depth} levels")
    print(f" Max Impact Severity:       {metrics.max_severity:.1%}")
    print(f" Total Business Impact:     {metrics.total_business_impact:.1f} (scale 1-100)")
    print(f" Estimated Recovery Time:   {metrics.estimated_mttr} hours")

    if metrics.affected_applications:
        print(f"\n CRITICAL APPLICATIONS AFFECTED ({len(metrics.affected_applications)}):")
        for app in metrics.affected_applications:
            print(f"   - {app}")

    print("\n IMPACT BY COMPONENT TYPE:")
    print("-" * 40)
    for comp_type, count in sorted(metrics.affected_by_layer.items(),
                                    key=lambda x: -x[1]):
        print(f"   {comp_type:<25} {count:3d}")

    print("\n PROPAGATION TIMELINE (first 15 events):")
    print("-" * 80)
    print(f" {'Time':>8} {'Component':<25} {'Type':<18} {'Status':<10} {'Via':<12}")
    print("-" * 80)

    for event in metrics.propagation_timeline[:15]:
        time_str = f"+{event['time']:.0f}s" if event['time'] > 0 else "T=0"
        triggered_by = event.get('dependency_type', 'trigger')[:12]
        print(f" {time_str:>8} {event['component'][:25]:<25} "
              f"{event['type'][:18]:<18} {event['status']:<10} {triggered_by:<12}")

    if len(metrics.propagation_timeline) > 15:
        print(f"   ... and {len(metrics.propagation_timeline) - 15} more events")

    print("\n AFFECTED COMPONENTS (by business impact):")
    print("-" * 80)

    for comp in affected[:10]:
        status_color = {
            "failed": "!!!",
            "impacted": "!! ",
            "degraded": "!  ",
        }
        prefix = status_color.get(comp["status"], "   ")
        print(f" {prefix} {comp['id'][:30]:<30} {comp['type'][:15]:<15} "
              f"{comp['status']:<10} Impact: {comp['business_impact']}")


def run_watch_mode(simulator: CascadeSimulator, metrics: CascadeMetrics):
    """Run interactive watch mode showing cascade in real-time."""
    print("\n" + "=" * 60)
    print(" LIVE CASCADE PROPAGATION")
    print("=" * 60)

    sorted_events = sorted(metrics.propagation_timeline,
                          key=lambda x: x['time'])

    last_time = 0
    for event in sorted_events:
        # Simulate time delay
        delay = (event['time'] - last_time) / 10  # Speed up 10x
        if delay > 0:
            time.sleep(min(delay, 1.0))  # Cap at 1 second

        status_icon = {
            "FAILED": "\033[91mX\033[0m",
            "IMPACTED": "\033[93m!\033[0m",
            "DEGRADED": "\033[94m~\033[0m",
        }
        icon = status_icon.get(event['status'], "?")

        time_str = f"+{event['time']:.0f}s" if event['time'] > 0 else "T=0"
        print(f" {time_str:>8} [{icon}] {event['name'][:35]:<35} "
              f"-> {event['status']}")

        last_time = event['time']

    print("\n" + "=" * 60)
    print(f" CASCADE COMPLETE: {metrics.total_affected} components affected")
    print("=" * 60)


def run_scenario(simulator: CascadeSimulator, scenario: str) -> CascadeMetrics:
    """Run a pre-defined failure scenario."""
    scenarios = {
        "power-outage": {
            "trigger": "sub-trans-001",
            "description": "Major substation failure causing widespread power outage",
        },
        "datacenter-power": {
            "trigger": "dc-power-feed-a",
            "description": "Data center power feed A failure",
        },
        "cooling-failure": {
            "trigger": "dc-chiller-plant",
            "description": "Central chiller plant failure causing thermal cascade",
        },
        "network-partition": {
            "trigger": "dc-core-sw-001",
            "description": "Core network switch failure causing network partition",
        },
        "generator-failure": {
            "trigger": "dc-gen-001",
            "description": "Backup generator failure during power event",
        },
    }

    if scenario not in scenarios:
        available = ", ".join(scenarios.keys())
        raise ValueError(f"Unknown scenario: {scenario}. Available: {available}")

    config = scenarios[scenario]
    print(f"\n Running Scenario: {scenario}")
    print(f" Description: {config['description']}")
    print(f" Trigger: {config['trigger']}")

    return simulator.inject_failure(config["trigger"])


def main():
    parser = argparse.ArgumentParser(description="Cascading Failure Simulation")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--trigger", help="Component ID to trigger failure")
    parser.add_argument("--scenario", help="Run pre-defined scenario")
    parser.add_argument("--random-failure", action="store_true",
                       help="Trigger random component failure")
    parser.add_argument("--watch", action="store_true",
                       help="Watch cascade in real-time")
    parser.add_argument("--list-components", action="store_true",
                       help="List available components")
    args = parser.parse_args()

    client = get_client(args.base_url)
    simulator = CascadeSimulator(client)

    print("Loading infrastructure graph...")
    simulator.load_infrastructure()

    if args.list_components:
        print("\nAvailable Components:")
        print("-" * 60)
        for comp_id, comp in sorted(simulator.components.items()):
            criticality = comp["properties"].get("criticality", "unknown")
            print(f"  {comp_id:<35} {comp['type']:<20} [{criticality}]")
        return

    if args.random_failure:
        # Select random critical component
        critical = [c for c, data in simulator.components.items()
                   if data["properties"].get("criticality") == "critical"]
        if critical:
            trigger = random.choice(critical)
            print(f"\nRandom failure selected: {trigger}")
            metrics = simulator.inject_failure(trigger)
        else:
            print("No critical components found")
            return

    elif args.scenario:
        metrics = run_scenario(simulator, args.scenario)

    elif args.trigger:
        metrics = simulator.inject_failure(args.trigger)

    else:
        print("\nUsage: Specify --trigger, --scenario, or --random-failure")
        print("       Use --list-components to see available components")
        return

    if args.watch:
        run_watch_mode(simulator, metrics)
    else:
        affected = simulator.get_affected_components()
        print_cascade_report(metrics, affected)


if __name__ == "__main__":
    main()
