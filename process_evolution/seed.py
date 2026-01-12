#!/usr/bin/env python3
"""
Business Process Evolution - Seed Script

Seeds example data demonstrating how business systems use semantic memory for:
- Process definitions (Semantic/Procedural)
- Execution logs (Episodic)
- Bottleneck patterns (Semantic/Fact)
- Process versions and evolution

Usage:
    python seed.py
"""

import sys
import os
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Agent configuration
AGENT_ID = "process-manager-corp"

# Process definitions
PROCESSES = [
    {
        "id": "loan-approval-v1",
        "name": "Loan Approval Process",
        "version": 1,
        "steps": ["Receive Application", "Credit Check", "Manager Approval", "Disburse"],
        "expected_hours": {"Credit Check": 2, "Manager Approval": 4, "Disburse": 1},
        "topics": ["loan", "finance", "approval"],
    },
    {
        "id": "employee-onboarding-v1",
        "name": "Employee Onboarding Process",
        "version": 1,
        "steps": ["HR Intake", "IT Setup", "Badge & Access", "Department Training", "First Day Complete"],
        "expected_hours": {"HR Intake": 2, "IT Setup": 24, "Badge & Access": 4, "Department Training": 8, "First Day Complete": 1},
        "topics": ["hr", "onboarding", "employee"],
    },
    {
        "id": "purchase-order-v1",
        "name": "Purchase Order Process",
        "version": 1,
        "steps": ["Request Submitted", "Budget Check", "Manager Approval", "Procurement", "Delivery"],
        "expected_hours": {"Budget Check": 1, "Manager Approval": 8, "Procurement": 24, "Delivery": 48},
        "topics": ["procurement", "purchasing", "approval"],
    },
    {
        "id": "support-ticket-v1",
        "name": "Support Ticket Process",
        "version": 1,
        "steps": ["Ticket Created", "Triage", "Assignment", "Resolution", "Closure"],
        "expected_hours": {"Triage": 0.5, "Assignment": 1, "Resolution": 4, "Closure": 0.5},
        "topics": ["support", "customer-service", "ticket"],
    },
]

# Simulated execution logs with delays
EXECUTION_LOGS = [
    # Loan approval - manager bottleneck
    {"process": "loan-approval-v1", "exec_id": "loan-101", "step": "Manager Approval", "duration_hours": 48, "reason": "Manager OOO"},
    {"process": "loan-approval-v1", "exec_id": "loan-102", "step": "Manager Approval", "duration_hours": 24, "reason": "Manual signature required"},
    {"process": "loan-approval-v1", "exec_id": "loan-103", "step": "Manager Approval", "duration_hours": 72, "reason": "Email buried"},
    {"process": "loan-approval-v1", "exec_id": "loan-104", "step": "Manager Approval", "duration_hours": 36, "reason": "Vacation"},
    {"process": "loan-approval-v1", "exec_id": "loan-105", "step": "Credit Check", "duration_hours": 2, "reason": "Normal"},
    {"process": "loan-approval-v1", "exec_id": "loan-106", "step": "Credit Check", "duration_hours": 3, "reason": "Manual review"},

    # Employee onboarding - IT setup delays
    {"process": "employee-onboarding-v1", "exec_id": "onb-201", "step": "IT Setup", "duration_hours": 72, "reason": "Laptop shortage"},
    {"process": "employee-onboarding-v1", "exec_id": "onb-202", "step": "IT Setup", "duration_hours": 48, "reason": "Software license delay"},
    {"process": "employee-onboarding-v1", "exec_id": "onb-203", "step": "IT Setup", "duration_hours": 36, "reason": "Account provisioning queue"},
    {"process": "employee-onboarding-v1", "exec_id": "onb-204", "step": "Badge & Access", "duration_hours": 4, "reason": "Normal"},

    # Purchase order - procurement delays
    {"process": "purchase-order-v1", "exec_id": "po-301", "step": "Procurement", "duration_hours": 96, "reason": "Vendor backlog"},
    {"process": "purchase-order-v1", "exec_id": "po-302", "step": "Manager Approval", "duration_hours": 24, "reason": "Budget question"},
    {"process": "purchase-order-v1", "exec_id": "po-303", "step": "Procurement", "duration_hours": 48, "reason": "Normal"},

    # Support ticket - mixed
    {"process": "support-ticket-v1", "exec_id": "tkt-401", "step": "Resolution", "duration_hours": 8, "reason": "Complex issue"},
    {"process": "support-ticket-v1", "exec_id": "tkt-402", "step": "Assignment", "duration_hours": 4, "reason": "Understaffed"},
    {"process": "support-ticket-v1", "exec_id": "tkt-403", "step": "Resolution", "duration_hours": 2, "reason": "Quick fix"},
]

# Identified bottleneck patterns
BOTTLENECK_PATTERNS = [
    {
        "content": "Manager Approval in Loan Approval consistently exceeds SLA (4h expected, avg 45h actual). Root cause: Manual signature requirement and single-point-of-failure approval chain.",
        "topics": ["bottleneck", "loan", "manager-approval", "analysis"],
        "confidence": 0.92,
        "evidence_count": 4,
    },
    {
        "content": "IT Setup in Employee Onboarding averages 52h vs 24h expected. Primary causes: Laptop inventory management and software license procurement timing.",
        "topics": ["bottleneck", "onboarding", "it-setup", "analysis"],
        "confidence": 0.88,
        "evidence_count": 3,
    },
    {
        "content": "Procurement step shows high variance (24-96h). Recommend pre-approved vendor list and automated PO routing for standard items.",
        "topics": ["bottleneck", "procurement", "variance", "recommendation"],
        "confidence": 0.75,
        "evidence_count": 3,
    },
]

# Process evolution records
PROCESS_EVOLUTIONS = [
    {
        "from_process": "loan-approval-v1",
        "to_process": "loan-approval-v2",
        "change": "Added auto-approval path for loans under $10,000 to bypass manager approval",
        "reason": "Reduce manager approval bottleneck for low-risk loans",
        "new_definition": "Loan Approval v2: 1. Receive Application -> 2. Credit Check -> 3. Auto-Approval (if <$10k) OR Manager Approval -> 4. Disburse",
        "topics": ["process-definition", "loan", "evolution"],
    },
    {
        "from_process": "employee-onboarding-v1",
        "to_process": "employee-onboarding-v2",
        "change": "IT Setup now starts in parallel with HR Intake using pre-provisioned laptop pool",
        "reason": "Eliminate IT Setup as critical path blocker",
        "new_definition": "Employee Onboarding v2: 1. HR Intake (+ IT Setup parallel) -> 2. Badge & Access -> 3. Department Training -> 4. First Day Complete",
        "topics": ["process-definition", "onboarding", "evolution"],
    },
]


def seed_process_evolution():
    """Seed the process evolution example data."""
    client = get_client()

    logger.info(f"Seeding process evolution for agent: {AGENT_ID}")
    created_count = 0

    # 1. Seed process definitions (Semantic/Procedural)
    logger.info("Seeding process definitions...")
    process_ids = {}

    for process in PROCESSES:
        steps_str = " -> ".join(process["steps"])
        content = f"{process['name']} v{process['version']}: {steps_str}"

        try:
            mem = client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "semantic",
                    "record_type": "procedure",
                    "content": content,
                    "topics": process["topics"] + ["process-definition"],
                    "version": process["version"],
                    "metadata": {
                        "process_id": process["id"],
                        "steps": process["steps"],
                        "expected_hours": process["expected_hours"],
                    },
                }
            )
            process_ids[process["id"]] = mem.id
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create process: {e}")

    # 2. Seed execution logs (Episodic)
    logger.info("Seeding execution logs...")
    base_time = datetime.now(timezone.utc) - timedelta(days=30)

    for i, log in enumerate(EXECUTION_LOGS):
        exec_time = base_time + timedelta(days=i % 15, hours=random.randint(0, 23))
        process_info = next((p for p in PROCESSES if p["id"] == log["process"]), None)
        expected = process_info["expected_hours"].get(log["step"], 4) if process_info else 4

        is_delay = log["duration_hours"] > expected * 2
        delay_factor = log["duration_hours"] / expected if expected > 0 else 1

        content = f"Execution {log['exec_id']}: {log['step']} took {log['duration_hours']} hours. Reason: {log['reason']}"
        if is_delay:
            content += f" [DELAY: {delay_factor:.1f}x expected]"

        try:
            client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "episodic",
                    "content": content,
                    "topics": ["process-log", log["process"].split("-")[0], "delay" if is_delay else "normal"],
                    "related_to": [process_ids.get(log["process"])] if process_ids.get(log["process"]) else [],
                    "metadata": {
                        "process_id": log["process"],
                        "execution_id": log["exec_id"],
                        "step": log["step"],
                        "duration_hours": log["duration_hours"],
                        "expected_hours": expected,
                        "delay_factor": delay_factor,
                        "is_delay": is_delay,
                    },
                }
            )
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create execution log: {e}")

    # 3. Seed bottleneck patterns (Semantic/Fact)
    logger.info("Seeding bottleneck patterns...")
    for pattern in BOTTLENECK_PATTERNS:
        try:
            client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "semantic",
                    "record_type": "fact",
                    "content": pattern["content"],
                    "topics": pattern["topics"],
                    "confidence": pattern["confidence"],
                    "metadata": {"evidence_count": pattern["evidence_count"]},
                    "source": {"source_type": "inferred"},
                }
            )
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create pattern: {e}")

    # 4. Seed process evolutions (Semantic/Procedural with lineage)
    logger.info("Seeding process evolutions...")
    for evolution in PROCESS_EVOLUTIONS:
        try:
            client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "semantic",
                    "record_type": "procedure",
                    "content": evolution["new_definition"],
                    "topics": evolution["topics"],
                    "related_to": [process_ids.get(evolution["from_process"])] if process_ids.get(evolution["from_process"]) else [],
                    "metadata": {
                        "supersedes": evolution["from_process"],
                        "change": evolution["change"],
                        "reason": evolution["reason"],
                    },
                }
            )
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create evolution: {e}")

    logger.info(f"Process evolution seeding complete. Created {created_count} memories.")

    # Print summary
    print("\n" + "=" * 60)
    print("  PROCESS EVOLUTION - SEED COMPLETE")
    print("=" * 60)
    print(f"\n  Agent ID: {AGENT_ID}")
    print(f"  Memories Created: {created_count}")
    print(f"    - Process Definitions: {len(PROCESSES)}")
    print(f"    - Execution Logs: {len(EXECUTION_LOGS)}")
    print(f"    - Bottleneck Patterns: {len(BOTTLENECK_PATTERNS)}")
    print(f"    - Process Evolutions: {len(PROCESS_EVOLUTIONS)}")
    print("\n  Next Steps:")
    print("    1. Run: python web_ui.py --port 8124")
    print("    2. Open: http://localhost:8124")
    print("    3. Run: python simulation.py (optional)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    seed_process_evolution()
