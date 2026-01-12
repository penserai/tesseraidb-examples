#!/usr/bin/env python3
"""
Business Process Evolution - Live Simulation

Simulates business process executions with varying performance:
- Normal executions within SLA
- Delayed steps causing bottlenecks
- Exception handling and rework
- Process evolution based on patterns

Usage:
    python simulation.py

Watch the web UI to see process executions and pattern detection.
"""

import sys
import os
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Agent configuration
AGENT_ID = "process-manager-corp"

# Process templates for simulation
PROCESS_TEMPLATES = [
    {
        "id": "loan-approval",
        "name": "Loan Approval",
        "steps": [
            {"name": "Receive Application", "expected_hours": 0.5, "delay_prob": 0.05},
            {"name": "Credit Check", "expected_hours": 2, "delay_prob": 0.1},
            {"name": "Manager Approval", "expected_hours": 4, "delay_prob": 0.4},  # High delay probability
            {"name": "Disburse", "expected_hours": 1, "delay_prob": 0.05},
        ],
        "delay_reasons": ["Manager OOO", "Manual signature required", "Email buried", "Vacation", "High workload"],
    },
    {
        "id": "employee-onboarding",
        "name": "Employee Onboarding",
        "steps": [
            {"name": "HR Intake", "expected_hours": 2, "delay_prob": 0.1},
            {"name": "IT Setup", "expected_hours": 24, "delay_prob": 0.35},  # High delay probability
            {"name": "Badge & Access", "expected_hours": 4, "delay_prob": 0.15},
            {"name": "Department Training", "expected_hours": 8, "delay_prob": 0.1},
        ],
        "delay_reasons": ["Laptop shortage", "Software license delay", "Account provisioning queue", "Vendor backlog"],
    },
    {
        "id": "support-ticket",
        "name": "Support Ticket",
        "steps": [
            {"name": "Triage", "expected_hours": 0.5, "delay_prob": 0.1},
            {"name": "Assignment", "expected_hours": 1, "delay_prob": 0.2},
            {"name": "Resolution", "expected_hours": 4, "delay_prob": 0.25},
            {"name": "Closure", "expected_hours": 0.5, "delay_prob": 0.05},
        ],
        "delay_reasons": ["Complex issue", "Understaffed", "Waiting for customer", "Escalation required"],
    },
]

# Counter for execution IDs
execution_counter = 1000


def simulate_step(step: dict, delay_reasons: list) -> tuple:
    """Simulate a single step execution. Returns (duration_hours, is_delay, reason)."""
    expected = step["expected_hours"]

    if random.random() < step["delay_prob"]:
        # Delayed execution
        delay_factor = random.uniform(2, 8)
        duration = expected * delay_factor
        reason = random.choice(delay_reasons)
        return (round(duration, 1), True, reason)
    else:
        # Normal execution with slight variance
        variance = random.uniform(0.8, 1.3)
        duration = expected * variance
        return (round(duration, 1), False, "Normal completion")


def run_simulation():
    """Run the process simulation."""
    global execution_counter
    client = get_client()

    print("\n" + "=" * 60)
    print("  PROCESS EVOLUTION - LIVE SIMULATION")
    print("=" * 60)
    print(f"\n  Agent: {AGENT_ID}")
    print("  Simulating business process executions")
    print("  Watch the web UI to see patterns emerge")
    print("\n  Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    delay_counts = {}

    try:
        while True:
            # Pick a random process
            process = random.choice(PROCESS_TEMPLATES)
            execution_counter += 1
            exec_id = f"{process['id'][:3]}-{execution_counter}"

            print(f"\n[EXECUTION {exec_id}] Starting {process['name']}")

            total_duration = 0
            had_delay = False

            for step in process["steps"]:
                duration, is_delay, reason = simulate_step(step, process["delay_reasons"])
                total_duration += duration

                status = "DELAY" if is_delay else "OK"
                if is_delay:
                    had_delay = True
                    key = f"{process['id']}-{step['name']}"
                    delay_counts[key] = delay_counts.get(key, 0) + 1

                print(f"  [{status}] {step['name']}: {duration}h (expected: {step['expected_hours']}h)")
                if is_delay:
                    print(f"        Reason: {reason}")

                # Log to memory
                content = f"Execution {exec_id}: {step['name']} took {duration} hours. Reason: {reason}"
                if is_delay:
                    content += f" [DELAY: {duration/step['expected_hours']:.1f}x expected]"

                try:
                    client.memory.create(
                        agent_id=AGENT_ID,
                        data={
                            "memory_type": "episodic",
                            "content": content,
                            "topics": ["process-log", process["id"].split("-")[0], "delay" if is_delay else "normal", "simulation"],
                            "metadata": {
                                "process_id": f"{process['id']}-v1",
                                "execution_id": exec_id,
                                "step": step["name"],
                                "duration_hours": duration,
                                "expected_hours": step["expected_hours"],
                                "delay_factor": round(duration / step["expected_hours"], 2),
                                "is_delay": is_delay,
                                "reason": reason,
                            },
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to log step: {e}")

                time.sleep(0.5)  # Brief pause between steps

            status_icon = "⚠️" if had_delay else "✓"
            print(f"\n  {status_icon} Completed in {total_duration:.1f}h total")

            # Check if we should generate a bottleneck insight
            for key, count in delay_counts.items():
                if count >= 3 and count % 3 == 0:  # Every 3 delays
                    process_id, step_name = key.rsplit("-", 1)
                    print(f"\n  [INSIGHT] Bottleneck pattern detected: {step_name} in {process_id}")
                    print(f"            {count} delay incidents recorded")

                    try:
                        client.memory.create(
                            agent_id=AGENT_ID,
                            data={
                                "memory_type": "semantic",
                                "record_type": "fact",
                                "content": f"Bottleneck pattern: {step_name} in {process_id} has {count} delays. Recommend process review.",
                                "topics": ["bottleneck", "analysis", process_id.split("-")[0], "auto-detected"],
                                "confidence": min(0.5 + count * 0.1, 0.95),
                                "metadata": {"evidence_count": count, "step": step_name, "process": process_id},
                                "source": {"source_type": "inferred"},
                            }
                        )
                    except Exception as e:
                        logger.warning(f"Failed to create insight: {e}")

            # Wait before next execution
            wait_time = random.randint(3, 8)
            print(f"\n  Next execution in {wait_time} seconds...")
            time.sleep(wait_time)

    except KeyboardInterrupt:
        print("\n\nSimulation stopped.")
        print("\nDelay Summary:")
        for key, count in sorted(delay_counts.items(), key=lambda x: -x[1]):
            print(f"  {key}: {count} delays")


if __name__ == "__main__":
    run_simulation()
