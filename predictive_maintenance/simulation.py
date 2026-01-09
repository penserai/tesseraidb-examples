#!/usr/bin/env python3
"""
Predictive Maintenance - Real-Time Degradation Simulation
==========================================================

Simulates realistic equipment degradation with:
- Weibull failure distribution modeling
- Physics-based degradation curves
- Sensor noise and drift
- Maintenance interventions
- Failure events with cascading effects

The simulation updates equipment health scores, sensor readings, and
remaining useful life estimates in real-time.

Usage:
    python simulation.py [--base-url URL] [--interval SECONDS] [--duration MINUTES]
    python simulation.py --accelerated  # Run 100x faster for demo
"""

import sys
import os
import math
import random
import time
import argparse
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import get_client, logger


# =============================================================================
# DEGRADATION MODELS
# =============================================================================

@dataclass
class WeibullParameters:
    """Weibull distribution parameters for failure modeling."""
    shape: float  # beta - shape parameter (>1 = wear-out, <1 = early failure, =1 = random)
    scale: float  # eta - characteristic life in hours
    location: float = 0  # gamma - minimum life before failure possible


# Equipment-specific Weibull parameters based on industry data
WEIBULL_PARAMS = {
    "IndustrialPump": WeibullParameters(shape=2.5, scale=15000, location=2000),
    "ElectricMotor": WeibullParameters(shape=3.0, scale=25000, location=5000),
    "RollingElementBearing": WeibullParameters(shape=2.0, scale=12000, location=1000),
    "Gearbox": WeibullParameters(shape=2.2, scale=20000, location=3000),
    "IndustrialCompressor": WeibullParameters(shape=2.8, scale=18000, location=2500),
    "HeatExchanger": WeibullParameters(shape=1.8, scale=30000, location=5000),
}


@dataclass
class DegradationState:
    """Current degradation state of equipment."""
    equipment_id: str
    equipment_type: str
    health_score: float
    remaining_useful_life: float
    vibration_level: float
    temperature: float
    operating_hours: float
    degradation_rate: float  # Current rate of degradation
    failure_probability: float  # P(failure in next interval)
    anomaly_score: float  # 0-1 scale
    last_update: datetime


class DegradationSimulator:
    """
    Physics-based degradation simulator using Weibull reliability models.
    """

    def __init__(self, client, time_acceleration: float = 1.0):
        self.client = client
        self.time_acceleration = time_acceleration
        self.states: Dict[str, DegradationState] = {}
        self.history: Dict[str, deque] = {}
        self.failures: List[Dict] = []
        self.running = False

        # Sensor noise parameters
        self.vibration_noise_std = 0.3
        self.temperature_noise_std = 2.0
        self.drift_rate = 0.001  # Sensor drift per hour

    def weibull_reliability(self, t: float, params: WeibullParameters) -> float:
        """Calculate reliability R(t) using Weibull distribution."""
        if t <= params.location:
            return 1.0
        adjusted_t = t - params.location
        return math.exp(-((adjusted_t / params.scale) ** params.shape))

    def weibull_hazard_rate(self, t: float, params: WeibullParameters) -> float:
        """Calculate hazard rate h(t) - instantaneous failure rate."""
        if t <= params.location:
            return 0.0
        adjusted_t = t - params.location
        return (params.shape / params.scale) * ((adjusted_t / params.scale) ** (params.shape - 1))

    def calculate_health_score(self, reliability: float, anomaly_score: float) -> float:
        """
        Calculate health score combining reliability and anomaly detection.
        """
        # Base health from reliability
        base_health = reliability * 100

        # Anomaly penalty (exponential impact at high anomaly scores)
        anomaly_penalty = (anomaly_score ** 2) * 30

        # Add random micro-fluctuations
        noise = random.gauss(0, 1)

        return max(0, min(100, base_health - anomaly_penalty + noise))

    def simulate_vibration(self, base_level: float, health_score: float,
                           operating_hours: float) -> float:
        """
        Simulate vibration readings with realistic patterns.
        Vibration increases as health decreases.
        """
        # Base vibration inversely related to health
        health_factor = (100 - health_score) / 100

        # Non-linear degradation - accelerates near failure
        degradation_vibration = base_level * (1 + health_factor ** 1.5 * 3)

        # Operating hours effect (slight increase over time)
        age_factor = 1 + (operating_hours / 50000) * 0.3

        # Add realistic noise
        noise = random.gauss(0, self.vibration_noise_std)

        # Occasional spikes (1% chance)
        spike = random.uniform(2, 5) if random.random() < 0.01 else 0

        return max(0.5, degradation_vibration * age_factor + noise + spike)

    def simulate_temperature(self, base_temp: float, health_score: float,
                             load_factor: float) -> float:
        """
        Simulate temperature readings based on health and load.
        Degraded equipment runs hotter due to friction, misalignment, etc.
        """
        # Health impact on temperature
        health_factor = (100 - health_score) / 100
        health_temp_rise = health_factor ** 1.3 * 25

        # Load impact
        load_temp_rise = load_factor * 15

        # Ambient variation
        ambient_variation = random.gauss(0, 3)

        # Add noise
        noise = random.gauss(0, self.temperature_noise_std)

        return base_temp + health_temp_rise + load_temp_rise + ambient_variation + noise

    def calculate_anomaly_score(self, vibration: float, temperature: float,
                                vib_threshold: float, temp_threshold: float) -> float:
        """
        Calculate anomaly score based on deviation from normal operating range.
        Uses a soft threshold approach.
        """
        vib_ratio = vibration / vib_threshold
        temp_ratio = temperature / temp_threshold

        # Soft threshold - starts rising above 0.7, rapid above 1.0
        vib_anomaly = max(0, (vib_ratio - 0.7) / 0.3) if vib_ratio > 0.7 else 0
        temp_anomaly = max(0, (temp_ratio - 0.8) / 0.2) if temp_ratio > 0.8 else 0

        # Combined anomaly (take max with weighted average)
        combined = max(vib_anomaly, temp_anomaly) * 0.7 + (vib_anomaly + temp_anomaly) / 2 * 0.3

        return min(1.0, combined)

    def simulate_failure_event(self, state: DegradationState) -> Optional[Dict]:
        """
        Determine if a failure event occurs based on probability.
        Returns failure details if failure occurred.
        """
        # Random failure check based on hazard rate
        if random.random() < state.failure_probability:
            failure_modes = {
                "IndustrialPump": ["seal_failure", "impeller_damage", "bearing_seizure", "cavitation"],
                "ElectricMotor": ["winding_burnout", "bearing_failure", "shaft_fracture"],
                "RollingElementBearing": ["spalling", "cage_failure", "seizure"],
                "Gearbox": ["tooth_breakage", "shaft_failure", "oil_starvation"],
                "IndustrialCompressor": ["valve_failure", "piston_seizure", "bearing_failure"],
                "HeatExchanger": ["tube_leak", "gasket_blowout", "severe_fouling"],
            }

            modes = failure_modes.get(state.equipment_type, ["general_failure"])
            failure_mode = random.choice(modes)

            return {
                "equipment_id": state.equipment_id,
                "equipment_type": state.equipment_type,
                "failure_mode": failure_mode,
                "timestamp": datetime.now().isoformat(),
                "health_at_failure": state.health_score,
                "operating_hours": state.operating_hours,
                "severity": random.choice(["minor", "moderate", "major", "critical"]),
            }

        return None

    def update_equipment_state(self, equipment_id: str, equipment_type: str,
                               current_props: Dict, delta_hours: float) -> DegradationState:
        """
        Update equipment degradation state based on physics models.
        """
        # Get or create state
        if equipment_id not in self.states:
            self.states[equipment_id] = DegradationState(
                equipment_id=equipment_id,
                equipment_type=equipment_type,
                health_score=current_props.get("healthScore", 85),
                remaining_useful_life=current_props.get("remainingUsefulLife", 5000),
                vibration_level=current_props.get("currentVibration", 2.5),
                temperature=current_props.get("currentTemperature", 55),
                operating_hours=current_props.get("operatingHours", 10000),
                degradation_rate=0.01,
                failure_probability=0.0001,
                anomaly_score=0.0,
                last_update=datetime.now()
            )
            self.history[equipment_id] = deque(maxlen=1000)

        state = self.states[equipment_id]

        # Update operating hours
        state.operating_hours += delta_hours

        # Get Weibull parameters
        params = WEIBULL_PARAMS.get(equipment_type, WeibullParameters(2.0, 15000, 2000))

        # Calculate reliability and hazard rate
        reliability = self.weibull_reliability(state.operating_hours, params)
        hazard_rate = self.weibull_hazard_rate(state.operating_hours, params)

        # Calculate failure probability for this interval
        state.failure_probability = 1 - math.exp(-hazard_rate * delta_hours)

        # Simulate sensor readings
        load_factor = random.uniform(0.5, 1.0)  # Simulated load
        state.vibration_level = self.simulate_vibration(
            current_props.get("currentVibration", 2.5),
            state.health_score,
            state.operating_hours
        )
        state.temperature = self.simulate_temperature(
            current_props.get("currentTemperature", 55),
            state.health_score,
            load_factor
        )

        # Calculate anomaly score
        vib_threshold = current_props.get("vibrationThreshold", 5.0)
        temp_threshold = current_props.get("temperatureThreshold", 100.0)
        state.anomaly_score = self.calculate_anomaly_score(
            state.vibration_level, state.temperature,
            vib_threshold, temp_threshold
        )

        # Update health score
        state.health_score = self.calculate_health_score(reliability, state.anomaly_score)

        # Calculate RUL (Remaining Useful Life)
        if state.health_score > 10:
            # Estimate RUL based on current degradation trajectory
            rul_estimate = (state.health_score / 100) * params.scale * reliability
            state.remaining_useful_life = max(0, rul_estimate)
        else:
            state.remaining_useful_life = 0

        # Calculate degradation rate
        state.degradation_rate = hazard_rate

        state.last_update = datetime.now()

        # Store in history
        self.history[equipment_id].append({
            "timestamp": state.last_update.isoformat(),
            "health_score": state.health_score,
            "vibration": state.vibration_level,
            "temperature": state.temperature,
            "rul": state.remaining_useful_life,
        })

        return state

    def apply_maintenance(self, equipment_id: str, maintenance_type: str) -> bool:
        """
        Apply maintenance effect to equipment.
        Returns True if maintenance was successful.
        """
        if equipment_id not in self.states:
            return False

        state = self.states[equipment_id]

        if maintenance_type == "preventive":
            # Preventive maintenance restores 20-40% health
            recovery = random.uniform(20, 40)
            state.health_score = min(100, state.health_score + recovery)
            state.anomaly_score *= 0.5

        elif maintenance_type == "corrective":
            # Corrective/repair restores to near-new condition
            state.health_score = random.uniform(85, 95)
            state.anomaly_score = random.uniform(0, 0.1)

        elif maintenance_type == "predictive":
            # Predictive - targeted repair of identified issue
            recovery = random.uniform(30, 50)
            state.health_score = min(100, state.health_score + recovery)
            state.anomaly_score *= 0.3

        logger.info(f"Maintenance applied to {equipment_id}: {maintenance_type}, "
                   f"new health: {state.health_score:.1f}")
        return True

    def run_simulation_tick(self, delta_hours: float = 1.0) -> Dict:
        """
        Run one simulation tick, updating all equipment.
        Returns summary of updates.
        """
        updates = []
        new_failures = []

        # Get all equipment twins
        try:
            all_twins = self.client.twins.list(domain="predictive_maintenance")
        except Exception as e:
            logger.error(f"Failed to list twins: {e}")
            return {"updates": 0, "failures": 0}

        equipment_types = ["IndustrialPump", "ElectricMotor", "RollingElementBearing",
                          "Gearbox", "IndustrialCompressor", "HeatExchanger"]

        for twin in all_twins:
            twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin

            # Check if this is equipment we simulate
            # SDK model uses 'type_uri' not 'type'
            twin_type = twin_dict.get("type_uri") or twin_dict.get("type") or ""
            equipment_type = None
            for et in equipment_types:
                if et in twin_type:
                    equipment_type = et
                    break

            if not equipment_type:
                continue

            equipment_id = twin_dict["id"]
            properties = twin_dict.get("properties", {})

            # Update state
            state = self.update_equipment_state(
                equipment_id, equipment_type, properties, delta_hours
            )

            # Check for failure
            failure = self.simulate_failure_event(state)
            if failure:
                new_failures.append(failure)
                self.failures.append(failure)
                logger.warning(f"FAILURE: {equipment_id} - {failure['failure_mode']}")

            # Update twin in database
            try:
                update_props = {
                    "healthScore": round(state.health_score, 1),
                    "remainingUsefulLife": round(state.remaining_useful_life, 0),
                    "currentVibration": round(state.vibration_level, 2),
                    "currentTemperature": round(state.temperature, 1),
                    "operatingHours": round(state.operating_hours, 0),
                    "anomalyScore": round(state.anomaly_score, 3),
                    "failureProbability": round(state.failure_probability, 6),
                    "lastSimulationUpdate": datetime.now().isoformat(),
                }

                if failure:
                    update_props["status"] = "failed"
                    update_props["lastFailure"] = failure["timestamp"]
                    update_props["lastFailureMode"] = failure["failure_mode"]

                self.client.twins.update(equipment_id, {"properties": update_props})
                updates.append(equipment_id)

            except Exception as e:
                logger.error(f"Failed to update {equipment_id}: {e}")

        return {
            "updates": len(updates),
            "failures": len(new_failures),
            "failure_details": new_failures,
        }

    def get_equipment_status(self) -> List[Dict]:
        """Get current status of all monitored equipment."""
        statuses = []
        for eq_id, state in self.states.items():
            statuses.append({
                "equipment_id": eq_id,
                "equipment_type": state.equipment_type,
                "health_score": round(state.health_score, 1),
                "rul_hours": round(state.remaining_useful_life, 0),
                "vibration": round(state.vibration_level, 2),
                "temperature": round(state.temperature, 1),
                "anomaly_score": round(state.anomaly_score, 3),
                "failure_probability": round(state.failure_probability, 6),
                "status": "critical" if state.health_score < 20 else
                         "warning" if state.health_score < 50 else
                         "degraded" if state.health_score < 75 else "healthy"
            })
        return sorted(statuses, key=lambda x: x["health_score"])

    def get_failure_history(self) -> List[Dict]:
        """Get history of all failures."""
        return self.failures


def run_continuous_simulation(base_url: Optional[str], interval: float,
                               duration: Optional[float], accelerated: bool):
    """
    Run continuous degradation simulation.
    """
    client = get_client(base_url)
    time_acceleration = 100.0 if accelerated else 1.0

    simulator = DegradationSimulator(client, time_acceleration)

    logger.info(f"Starting degradation simulation")
    logger.info(f"  Update interval: {interval}s")
    logger.info(f"  Time acceleration: {time_acceleration}x")
    if duration:
        logger.info(f"  Duration: {duration} minutes")

    start_time = time.time()
    tick_count = 0

    try:
        while True:
            tick_start = time.time()

            # Calculate simulated hours since last tick
            delta_hours = (interval / 3600) * time_acceleration

            # Run simulation tick
            result = simulator.run_simulation_tick(delta_hours)

            tick_count += 1
            elapsed = time.time() - start_time

            # Print status
            equipment_status = simulator.get_equipment_status()
            critical_count = sum(1 for s in equipment_status if s["status"] == "critical")
            warning_count = sum(1 for s in equipment_status if s["status"] == "warning")

            print(f"\r[Tick {tick_count}] Updated: {result['updates']}, "
                  f"Failures: {result['failures']}, "
                  f"Critical: {critical_count}, Warnings: {warning_count}, "
                  f"Elapsed: {elapsed:.0f}s", end="", flush=True)

            # Print any new failures
            for failure in result.get("failure_details", []):
                print(f"\n  >>> FAILURE: {failure['equipment_id']} - "
                      f"{failure['failure_mode']} ({failure['severity']})")

            # Check duration limit
            if duration and elapsed >= duration * 60:
                print(f"\n\nDuration limit reached ({duration} minutes)")
                break

            # Sleep for remaining interval
            tick_duration = time.time() - tick_start
            sleep_time = max(0, interval - tick_duration)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n\nSimulation stopped by user")

    # Final summary
    print("\n" + "=" * 60)
    print("SIMULATION SUMMARY")
    print("=" * 60)
    print(f"Total ticks: {tick_count}")
    print(f"Total failures: {len(simulator.failures)}")
    print(f"Simulated hours: {tick_count * (interval / 3600) * time_acceleration:.1f}")
    print()

    # Equipment status
    print("Equipment Status:")
    for status in simulator.get_equipment_status()[:10]:
        status_icon = "X" if status["status"] == "critical" else \
                      "!" if status["status"] == "warning" else \
                      "~" if status["status"] == "degraded" else "o"
        print(f"  [{status_icon}] {status['equipment_id'][:30]:30} "
              f"Health: {status['health_score']:5.1f}% "
              f"RUL: {status['rul_hours']:6.0f}h "
              f"Vib: {status['vibration']:4.2f}")

    if simulator.failures:
        print("\nFailure History:")
        for f in simulator.failures[-5:]:
            print(f"  - {f['equipment_id']}: {f['failure_mode']} at {f['timestamp']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run degradation simulation")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--interval", type=float, default=5.0,
                       help="Update interval in seconds (default: 5)")
    parser.add_argument("--duration", type=float,
                       help="Simulation duration in minutes")
    parser.add_argument("--accelerated", action="store_true",
                       help="Run 100x faster for demo")
    args = parser.parse_args()

    run_continuous_simulation(args.base_url, args.interval, args.duration, args.accelerated)
