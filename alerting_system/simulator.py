#!/usr/bin/env python3
"""
Real-Time Alerting System - Metric Simulator
=============================================

Generates realistic metric data with:
- Normal operating patterns with daily/weekly cycles
- Random anomalies and spikes
- Gradual degradation patterns
- Correlated metrics (CPU -> Memory -> Response Time)
- Configurable anomaly injection

Usage:
    python simulator.py [--base-url URL] [--interval SECONDS]
    python simulator.py --chaos           # Inject random failures
    python simulator.py --scenario spike  # Run specific scenario
"""

import sys
import os
import time
import math
import random
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import get_client, logger


class AnomalyType(Enum):
    NONE = "none"
    SPIKE = "spike"
    DEGRADATION = "degradation"
    OUTAGE = "outage"
    RECOVERY = "recovery"


@dataclass
class MetricSimulator:
    """Simulator for a single metric."""
    base_value: float
    noise_std: float
    min_value: float = 0
    max_value: float = 100
    trend: float = 0  # Rate of change per tick
    seasonality_amplitude: float = 0
    seasonality_period: float = 3600  # seconds


class SystemSimulator:
    """
    Simulates realistic system metrics with anomalies.
    """

    def __init__(self, system_id: str, system_type: str, properties: Dict):
        self.system_id = system_id
        self.system_type = system_type
        self.properties = properties.copy()

        self.tick_count = 0
        self.anomaly_type = AnomalyType.NONE
        self.anomaly_start: Optional[datetime] = None
        self.anomaly_duration: int = 0

        # Initialize metric simulators based on system type
        self.setup_simulators()

    def setup_simulators(self):
        """Configure metric simulators based on system type."""
        self.simulators: Dict[str, MetricSimulator] = {}

        if self.system_type == "WebServer":
            self.simulators = {
                "cpuUsage": MetricSimulator(40, 8, 0, 100, 0, 10, 3600),
                "memoryUsage": MetricSimulator(55, 5, 0, 100, 0, 5, 7200),
                "diskUsage": MetricSimulator(45, 2, 0, 100, 0.001, 0, 0),  # Slow growth
                "requestsPerSecond": MetricSimulator(500, 100, 0, 5000, 0, 200, 3600),
                "responseTimeMs": MetricSimulator(100, 30, 10, 5000, 0, 20, 1800),
                "errorRate": MetricSimulator(0.5, 0.3, 0, 100, 0, 0.2, 3600),
                "activeConnections": MetricSimulator(200, 50, 0, 1000, 0, 50, 1800),
            }

        elif self.system_type == "DatabaseServer":
            self.simulators = {
                "cpuUsage": MetricSimulator(30, 10, 0, 100, 0, 15, 3600),
                "memoryUsage": MetricSimulator(60, 8, 0, 100, 0, 10, 7200),
                "diskUsage": MetricSimulator(50, 3, 0, 100, 0.002, 0, 0),
                "connections": MetricSimulator(50, 20, 0, 200, 0, 30, 1800),
                "queriesPerSecond": MetricSimulator(1000, 300, 0, 10000, 0, 500, 3600),
                "avgQueryTimeMs": MetricSimulator(10, 5, 0.1, 1000, 0, 5, 1800),
                "slowQueries": MetricSimulator(2, 2, 0, 100, 0, 1, 3600),
                "replicationLagMs": MetricSimulator(10, 15, 0, 10000, 0, 10, 600),
            }

        elif self.system_type == "ApplicationService":
            self.simulators = {
                "cpuUsage": MetricSimulator(35, 12, 0, 100, 0, 10, 3600),
                "memoryUsage": MetricSimulator(50, 8, 0, 100, 0.0005, 5, 7200),
                "requestsPerSecond": MetricSimulator(300, 80, 0, 5000, 0, 100, 1800),
                "avgLatencyMs": MetricSimulator(50, 15, 1, 5000, 0, 10, 1800),
                "p99LatencyMs": MetricSimulator(200, 50, 10, 10000, 0, 30, 1800),
                "errorRate": MetricSimulator(0.3, 0.2, 0, 100, 0, 0.1, 3600),
                "successRate": MetricSimulator(99.5, 0.3, 0, 100, 0, 0.2, 3600),
            }

        elif self.system_type == "MessageQueue":
            self.simulators = {
                "messageCount": MetricSimulator(5000, 2000, 0, 100000, 0, 1000, 1800),
                "consumerCount": MetricSimulator(5, 2, 1, 20, 0, 0, 0),
                "publishRate": MetricSimulator(500, 150, 0, 5000, 0, 200, 1800),
                "consumeRate": MetricSimulator(480, 150, 0, 5000, 0, 200, 1800),
                "oldestMessageAge": MetricSimulator(30, 20, 0, 3600, 0, 10, 600),
                "deadLetterCount": MetricSimulator(10, 10, 0, 1000, 0.01, 0, 0),
            }

    def simulate_tick(self, elapsed_seconds: float) -> Dict[str, float]:
        """Simulate one tick of metrics."""
        self.tick_count += 1
        new_values = {}

        for metric_name, sim in self.simulators.items():
            # Base value with trend
            value = sim.base_value + sim.trend * self.tick_count

            # Add seasonality
            if sim.seasonality_amplitude > 0:
                phase = (elapsed_seconds % sim.seasonality_period) / sim.seasonality_period
                value += sim.seasonality_amplitude * math.sin(2 * math.pi * phase)

            # Add noise
            value += random.gauss(0, sim.noise_std)

            # Apply anomaly effects
            value = self.apply_anomaly(metric_name, value)

            # Clamp to valid range
            value = max(sim.min_value, min(sim.max_value, value))

            new_values[metric_name] = round(value, 2)

        # Apply metric correlations
        new_values = self.apply_correlations(new_values)

        return new_values

    def apply_anomaly(self, metric_name: str, value: float) -> float:
        """Apply anomaly effects to a metric value."""
        if self.anomaly_type == AnomalyType.NONE:
            return value

        anomaly_age = 0
        if self.anomaly_start:
            anomaly_age = (datetime.now() - self.anomaly_start).total_seconds()

        if anomaly_age > self.anomaly_duration:
            self.anomaly_type = AnomalyType.NONE
            return value

        if self.anomaly_type == AnomalyType.SPIKE:
            # Sudden spike in resource usage
            if metric_name in ["cpuUsage", "memoryUsage", "responseTimeMs", "avgLatencyMs"]:
                spike_factor = 1.5 + random.uniform(0, 0.5)
                return value * spike_factor

        elif self.anomaly_type == AnomalyType.DEGRADATION:
            # Gradual degradation
            progress = anomaly_age / self.anomaly_duration
            if metric_name in ["cpuUsage", "memoryUsage"]:
                return value * (1 + 0.5 * progress)
            elif metric_name in ["errorRate"]:
                return value * (1 + 3 * progress)
            elif metric_name in ["responseTimeMs", "avgLatencyMs"]:
                return value * (1 + 2 * progress)

        elif self.anomaly_type == AnomalyType.OUTAGE:
            # Complete outage
            if metric_name in ["requestsPerSecond", "queriesPerSecond"]:
                return 0
            elif metric_name == "errorRate":
                return 100
            elif metric_name == "successRate":
                return 0
            elif metric_name in ["healthyInstances"]:
                return 0

        return value

    def apply_correlations(self, values: Dict[str, float]) -> Dict[str, float]:
        """Apply realistic correlations between metrics."""
        # High CPU -> Higher response time
        if "cpuUsage" in values and "responseTimeMs" in values:
            if values["cpuUsage"] > 70:
                factor = 1 + (values["cpuUsage"] - 70) / 30
                values["responseTimeMs"] *= factor

        # High response time -> Higher error rate
        if "responseTimeMs" in values and "errorRate" in values:
            if values["responseTimeMs"] > 500:
                values["errorRate"] += (values["responseTimeMs"] - 500) / 100

        # High error rate -> Lower success rate
        if "errorRate" in values and "successRate" in values:
            values["successRate"] = max(0, 100 - values["errorRate"])

        # Queue depth affects consume rate
        if "messageCount" in values and "consumeRate" in values:
            if values["messageCount"] > 20000:
                values["consumeRate"] *= 0.8  # Consumers struggling

        return values

    def inject_anomaly(self, anomaly_type: AnomalyType, duration: int = 60):
        """Inject an anomaly into the system."""
        self.anomaly_type = anomaly_type
        self.anomaly_start = datetime.now()
        self.anomaly_duration = duration
        logger.info(f"Injected {anomaly_type.value} anomaly into {self.system_id} "
                   f"for {duration}s")


class MetricSimulatorEngine:
    """
    Engine that simulates metrics for all systems.
    """

    def __init__(self, client, update_interval: float = 5.0, chaos_mode: bool = False):
        self.client = client
        self.update_interval = update_interval
        self.chaos_mode = chaos_mode

        self.systems: Dict[str, SystemSimulator] = {}
        self.start_time = datetime.now()

    def load_systems(self):
        """Load systems from DTaaS."""
        try:
            twins = self.client.twins.list(domain="alerting_system")

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                # SDK model uses 'type_uri' not 'type'
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                twin_type = type_val.split("#")[-1] if type_val else ""
                twin_id = twin_dict["id"]

                if twin_type in ["WebServer", "DatabaseServer", "ApplicationService", "MessageQueue"]:
                    self.systems[twin_id] = SystemSimulator(
                        twin_id,
                        twin_type,
                        twin_dict.get("properties", {})
                    )

            logger.info(f"Loaded {len(self.systems)} systems for simulation")

        except Exception as e:
            logger.error(f"Failed to load systems: {e}")
            raise

    def run_tick(self):
        """Run one simulation tick for all systems."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        for system_id, simulator in self.systems.items():
            # Generate new metric values
            new_values = simulator.simulate_tick(elapsed)

            # Update in DTaaS
            try:
                update_props = {
                    "lastHeartbeat": datetime.now().isoformat(),
                    **new_values
                }
                self.client.twins.update(system_id, {"properties": update_props})

            except Exception as e:
                logger.warning(f"Failed to update {system_id}: {e}")

        # Chaos mode: randomly inject anomalies
        if self.chaos_mode and random.random() < 0.05:  # 5% chance per tick
            self.inject_random_anomaly()

    def inject_random_anomaly(self):
        """Inject a random anomaly into a random system."""
        if not self.systems:
            return

        system_id = random.choice(list(self.systems.keys()))
        anomaly_type = random.choice([AnomalyType.SPIKE, AnomalyType.DEGRADATION])
        duration = random.randint(30, 120)

        self.systems[system_id].inject_anomaly(anomaly_type, duration)

    def inject_scenario(self, scenario: str):
        """Inject a predefined scenario."""
        scenarios = {
            "spike": self.scenario_spike,
            "degradation": self.scenario_degradation,
            "cascade": self.scenario_cascade,
            "recovery": self.scenario_recovery,
        }

        if scenario not in scenarios:
            print(f"Unknown scenario: {scenario}")
            print(f"Available: {', '.join(scenarios.keys())}")
            return

        scenarios[scenario]()

    def scenario_spike(self):
        """Sudden spike scenario on web servers."""
        for sys_id, sim in self.systems.items():
            if sim.system_type == "WebServer":
                sim.inject_anomaly(AnomalyType.SPIKE, 60)
                print(f"Injected spike into {sys_id}")

    def scenario_degradation(self):
        """Gradual degradation scenario."""
        for sys_id, sim in self.systems.items():
            if sim.system_type == "DatabaseServer":
                sim.inject_anomaly(AnomalyType.DEGRADATION, 180)
                print(f"Injected degradation into {sys_id}")

    def scenario_cascade(self):
        """Cascading failure scenario."""
        # Database goes down first
        for sys_id, sim in self.systems.items():
            if "db-primary" in sys_id:
                sim.inject_anomaly(AnomalyType.OUTAGE, 120)
                print(f"Injected outage into {sys_id}")
                break

        # Then services degrade
        time.sleep(2)
        for sys_id, sim in self.systems.items():
            if sim.system_type == "ApplicationService":
                sim.inject_anomaly(AnomalyType.DEGRADATION, 90)

    def scenario_recovery(self):
        """Clear all anomalies."""
        for sim in self.systems.values():
            sim.anomaly_type = AnomalyType.NONE
        print("All anomalies cleared")

    def print_status(self):
        """Print current simulation status."""
        print("\r" + " " * 80, end="")  # Clear line

        active_anomalies = sum(1 for s in self.systems.values()
                               if s.anomaly_type != AnomalyType.NONE)

        elapsed = (datetime.now() - self.start_time).total_seconds()

        print(f"\r[{datetime.now().strftime('%H:%M:%S')}] "
              f"Simulating {len(self.systems)} systems | "
              f"Elapsed: {elapsed:.0f}s | "
              f"Active anomalies: {active_anomalies}",
              end="", flush=True)

    def run(self):
        """Run the simulation loop."""
        logger.info("Starting metric simulator...")
        self.load_systems()

        if not self.systems:
            print("No systems found. Run seed.py first.")
            return

        print(f"\nSimulating {len(self.systems)} systems")
        print(f"Update interval: {self.update_interval}s")
        print(f"Chaos mode: {'ON' if self.chaos_mode else 'OFF'}")
        print("\nPress Ctrl+C to stop\n")

        try:
            while True:
                self.run_tick()
                self.print_status()
                time.sleep(self.update_interval)

        except KeyboardInterrupt:
            print("\n\nSimulator stopped.")


def main():
    parser = argparse.ArgumentParser(description="Metric Simulator")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--interval", type=float, default=5.0,
                       help="Update interval in seconds (default: 5)")
    parser.add_argument("--chaos", action="store_true",
                       help="Enable random anomaly injection")
    parser.add_argument("--scenario",
                       choices=["spike", "degradation", "cascade", "recovery"],
                       help="Inject specific scenario and exit")
    args = parser.parse_args()

    client = get_client(args.base_url)
    engine = MetricSimulatorEngine(client, args.interval, args.chaos)

    engine.load_systems()

    if args.scenario:
        engine.inject_scenario(args.scenario)
        # Run a few ticks to apply the scenario
        for _ in range(5):
            engine.run_tick()
            time.sleep(1)
        print("\nScenario applied.")
    else:
        engine.run()


if __name__ == "__main__":
    main()
