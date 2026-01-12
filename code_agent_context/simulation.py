#!/usr/bin/env python3
"""
Code Agent Context Management - Live Simulation

Simulates coding agent sessions creating memories in real-time:
- Bug investigation sessions with reasoning chains
- Pattern learning from successful fixes
- Semantic search for relevant past solutions

Usage:
    python simulation.py

Watch the web UI to see memories appear in real-time.
"""

import sys
import os
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Agent configuration
AGENT_ID = "code-agent-vscode"

# Simulation scenarios
SCENARIOS = [
    {
        "name": "Database Connection Pool Exhaustion",
        "goal": "Fix 'too many connections' errors in production",
        "topics": ["database", "connection-pool", "production", "bugfix"],
        "steps": [
            {"type": "observation", "content": "Error logs show 'FATAL: too many connections for role postgres' starting at 2am", "confidence": 1.0, "delay": 2},
            {"type": "observation", "content": "Connection count in pg_stat_activity shows 150+ connections (max is 100)", "confidence": 1.0, "delay": 2},
            {"type": "hypothesis", "content": "Connection leak in the async job processor not releasing connections", "confidence": 0.7, "delay": 3},
            {"type": "test", "content": "Added connection pool monitoring with prometheus metrics", "confidence": 1.0, "delay": 2},
            {"type": "confirmation", "content": "Confirmed: background job workers not calling connection.close() in error paths", "confidence": 0.95, "delay": 3},
            {"type": "solution", "content": "Added context manager wrapper to ensure connection release in finally block", "confidence": 1.0, "delay": 2},
        ],
        "pattern": "Database connections in async workers must use context managers (with statement) to ensure cleanup in error paths"
    },
    {
        "name": "Memory Leak in Cache Layer",
        "goal": "Investigate gradual memory increase over 24 hours",
        "topics": ["memory", "cache", "performance", "debugging"],
        "steps": [
            {"type": "observation", "content": "Memory usage grows from 500MB to 4GB over 24 hours without restart", "confidence": 1.0, "delay": 2},
            {"type": "analysis", "content": "Heap dump shows large number of cached response objects", "confidence": 1.0, "delay": 3},
            {"type": "hypothesis", "content": "Cache TTL not being respected due to clock comparison bug", "confidence": 0.6, "delay": 2},
            {"type": "test", "content": "Instrumented cache eviction with debug logging", "confidence": 1.0, "delay": 2},
            {"type": "confirmation", "content": "Cache entries using datetime.now() without timezone, causing comparison issues with UTC timestamps", "confidence": 0.9, "delay": 3},
            {"type": "solution", "content": "Standardized all timestamps to UTC using datetime.now(timezone.utc)", "confidence": 1.0, "delay": 2},
        ],
        "pattern": "Always use timezone-aware datetime objects (datetime.now(timezone.utc)) for cache TTL comparisons to avoid timezone bugs"
    },
    {
        "name": "API Rate Limiting Bypass",
        "goal": "Fix rate limiter not blocking excessive requests",
        "topics": ["security", "rate-limiting", "api", "redis"],
        "steps": [
            {"type": "observation", "content": "Single IP making 10,000+ requests/minute despite 100/minute limit", "confidence": 1.0, "delay": 2},
            {"type": "analysis", "content": "Rate limiter using X-Forwarded-For header which can be spoofed", "confidence": 1.0, "delay": 2},
            {"type": "hypothesis", "content": "Attacker rotating X-Forwarded-For values to bypass per-IP limits", "confidence": 0.85, "delay": 3},
            {"type": "test", "content": "Tested with curl -H 'X-Forwarded-For: random' - confirmed bypass", "confidence": 1.0, "delay": 2},
            {"type": "solution", "content": "Changed to use real IP from socket, with X-Forwarded-For only from trusted proxies", "confidence": 1.0, "delay": 2},
        ],
        "pattern": "Rate limiting must use verified client IP from trusted proxy chain, never trust arbitrary X-Forwarded-For headers"
    },
]


def run_simulation():
    """Run the live simulation."""
    client = get_client()

    print("\n" + "=" * 60)
    print("  CODE AGENT CONTEXT - LIVE SIMULATION")
    print("=" * 60)
    print(f"\n  Agent: {AGENT_ID}")
    print("  Watch the web UI to see memories appear in real-time")
    print("\n  Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    try:
        while True:
            # Pick a random scenario
            scenario = random.choice(SCENARIOS)
            session_id = f"sim-{scenario['name'].lower().replace(' ', '-')[:20]}-{int(time.time())}"

            print(f"\n[SESSION START] {scenario['name']}")
            print(f"  Session ID: {session_id}")
            print(f"  Goal: {scenario['goal']}")

            # Create session context (working memory)
            try:
                client.memory.create(
                    agent_id=AGENT_ID,
                    data={
                        "memory_type": "working",
                        "content": f"Session Goal: {scenario['goal']}",
                        "session_id": session_id,
                        "topics": scenario["topics"],
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to create session: {e}")

            # Process each reasoning step
            prev_step_id = None
            for i, step in enumerate(scenario["steps"]):
                time.sleep(step["delay"])

                step_content = f"[{step['type'].upper()}] {step['content']}"
                print(f"  Step {i+1}: {step_content[:60]}...")

                try:
                    mem = client.memory.create(
                        agent_id=AGENT_ID,
                        data={
                            "memory_type": "episodic",
                            "record_type": "belief" if step["type"] in ["hypothesis", "observation"] else "episode",
                            "content": step_content,
                            "session_id": session_id,
                            "confidence": step["confidence"],
                            "related_to": [prev_step_id] if prev_step_id else [],
                            "topics": scenario["topics"],
                        }
                    )
                    prev_step_id = mem.id
                except Exception as e:
                    logger.warning(f"Failed to create step: {e}")

            # Promote pattern to semantic memory
            print(f"\n  [PATTERN LEARNED] {scenario['pattern'][:60]}...")
            try:
                client.memory.create(
                    agent_id=AGENT_ID,
                    data={
                        "memory_type": "semantic",
                        "record_type": "fact",
                        "content": scenario["pattern"],
                        "topics": scenario["topics"] + ["best-practice"],
                        "confidence": 0.9,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to create pattern: {e}")

            print(f"\n[SESSION COMPLETE] Pattern promoted to semantic memory")

            # Wait before next session
            wait_time = random.randint(5, 15)
            print(f"\n  Next session in {wait_time} seconds...")
            time.sleep(wait_time)

    except KeyboardInterrupt:
        print("\n\nSimulation stopped.")


if __name__ == "__main__":
    run_simulation()
