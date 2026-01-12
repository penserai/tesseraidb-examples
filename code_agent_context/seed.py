#!/usr/bin/env python3
"""
Code Agent Context Management - Seed Script

Seeds example data demonstrating how coding agents use semantic memory for:
- Session context management (Working Memory)
- Reasoning chain logging (Episodic Memory)
- Pattern learning and retrieval (Semantic Memory)

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
AGENT_ID = "code-agent-vscode"

# Sample session data
SESSIONS = [
    {
        "id": "session-auth-bug-2024-01",
        "goal": "Fix intermittent 401 errors in auth service",
        "constraints": ["Maintain v1 API compatibility", "No breaking changes"],
        "topics": ["auth", "jwt", "api", "bugfix"],
        "outcome": "success",
    },
    {
        "id": "session-perf-opt-2024-01",
        "goal": "Optimize database query performance in user service",
        "constraints": ["Keep existing API contracts", "Memory limit 512MB"],
        "topics": ["performance", "database", "optimization"],
        "outcome": "success",
    },
    {
        "id": "session-refactor-2024-01",
        "goal": "Refactor authentication middleware for cleaner separation",
        "constraints": ["100% test coverage", "Backward compatible"],
        "topics": ["refactoring", "auth", "middleware"],
        "outcome": "success",
    },
]

# Sample reasoning steps for sessions
REASONING_STEPS = {
    "session-auth-bug-2024-01": [
        {"type": "observation", "content": "Error logs show 401s occurring sporadically around :00 and :30 minute marks", "confidence": 0.9},
        {"type": "hypothesis", "content": "Clock skew between auth server and validation service may cause JWT exp claim failures", "confidence": 0.75},
        {"type": "test", "content": "Added debug logging to capture token exp time vs server time", "confidence": 1.0},
        {"type": "confirmation", "content": "Confirmed 2-5 second clock drift between containers", "confidence": 0.95},
        {"type": "solution", "content": "Added 30-second leeway to JWT validation configuration", "confidence": 0.95},
    ],
    "session-perf-opt-2024-01": [
        {"type": "observation", "content": "User list endpoint P99 latency is 800ms, target is 200ms", "confidence": 1.0},
        {"type": "analysis", "content": "Query EXPLAIN shows full table scan on users table", "confidence": 1.0},
        {"type": "hypothesis", "content": "Missing index on status column used in WHERE clause", "confidence": 0.8},
        {"type": "test", "content": "Created index on users(status, created_at)", "confidence": 1.0},
        {"type": "confirmation", "content": "P99 dropped to 45ms after index creation", "confidence": 1.0},
    ],
    "session-refactor-2024-01": [
        {"type": "observation", "content": "Auth middleware has 500 lines with mixed concerns", "confidence": 1.0},
        {"type": "plan", "content": "Extract token validation, session management, and rate limiting into separate modules", "confidence": 0.9},
        {"type": "action", "content": "Created TokenValidator, SessionManager, RateLimiter classes", "confidence": 1.0},
        {"type": "action", "content": "Updated auth middleware to compose the three components", "confidence": 1.0},
        {"type": "verification", "content": "All 45 existing tests pass, coverage at 98%", "confidence": 1.0},
    ],
}

# Learned patterns (promoted to semantic memory)
PATTERNS = [
    {
        "content": "JWT validation in distributed systems requires clock skew leeway (recommended: 30s) to prevent intermittent 401 errors",
        "topics": ["auth", "jwt", "distributed-systems", "best-practice"],
        "confidence": 0.95,
        "usage_count": 12,
    },
    {
        "content": "Database queries with WHERE clauses on status columns benefit from composite indexes including (status, created_at) for time-based pagination",
        "topics": ["database", "performance", "indexing", "best-practice"],
        "confidence": 0.92,
        "usage_count": 8,
    },
    {
        "content": "Python middleware refactoring pattern: Extract responsibilities into composable classes following Single Responsibility Principle",
        "topics": ["refactoring", "python", "middleware", "design-pattern"],
        "confidence": 0.88,
        "usage_count": 5,
    },
    {
        "content": "When debugging intermittent failures, check system time synchronization across containers first",
        "topics": ["debugging", "distributed-systems", "docker"],
        "confidence": 0.85,
        "usage_count": 15,
    },
    {
        "content": "Rate limiting should be implemented at the middleware layer with configurable limits per endpoint",
        "topics": ["auth", "rate-limiting", "api", "security"],
        "confidence": 0.9,
        "usage_count": 7,
    },
]

# Error categories (semantic knowledge)
ERROR_CATEGORIES = [
    {"name": "AuthenticationError", "description": "Issues with user identity verification", "common_causes": ["expired tokens", "invalid credentials", "clock skew"]},
    {"name": "AuthorizationError", "description": "Issues with permission checks", "common_causes": ["missing roles", "scope mismatch", "resource ownership"]},
    {"name": "PerformanceIssue", "description": "Slow response times or timeouts", "common_causes": ["missing indexes", "N+1 queries", "memory leaks"]},
    {"name": "ConcurrencyBug", "description": "Race conditions and deadlocks", "common_causes": ["missing locks", "transaction isolation", "async timing"]},
]


def seed_code_agent_context():
    """Seed the code agent context example data."""
    client = get_client()

    logger.info(f"Seeding code agent context for agent: {AGENT_ID}")

    # Track created memories
    created_count = 0

    # 1. Seed learned patterns (Semantic Memory)
    logger.info("Seeding learned patterns...")
    for pattern in PATTERNS:
        try:
            client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "semantic",
                    "record_type": "fact",
                    "content": pattern["content"],
                    "topics": pattern["topics"],
                    "confidence": pattern["confidence"],
                    "metadata": {"usage_count": pattern["usage_count"]},
                }
            )
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create pattern: {e}")

    # 2. Seed error categories (Semantic Memory)
    logger.info("Seeding error categories...")
    for category in ERROR_CATEGORIES:
        try:
            client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "semantic",
                    "record_type": "fact",
                    "content": f"{category['name']}: {category['description']}. Common causes: {', '.join(category['common_causes'])}",
                    "topics": ["error-taxonomy", category["name"].lower()],
                    "confidence": 1.0,
                }
            )
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create error category: {e}")

    # 3. Seed sessions and reasoning steps
    logger.info("Seeding coding sessions and reasoning steps...")
    base_time = datetime.now(timezone.utc) - timedelta(days=30)

    for i, session in enumerate(SESSIONS):
        session_time = base_time + timedelta(days=i * 10)

        # Create session context (Working Memory - but marked as completed)
        try:
            session_mem = client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "episodic",
                    "record_type": "episode",
                    "content": f"Session Goal: {session['goal']}. Constraints: {', '.join(session['constraints'])}",
                    "session_id": session["id"],
                    "topics": session["topics"],
                    "metadata": {"outcome": session["outcome"], "session_type": "coding"},
                }
            )
            created_count += 1

            # Create reasoning steps for this session
            steps = REASONING_STEPS.get(session["id"], [])
            prev_step_id = None

            for j, step in enumerate(steps):
                step_time = session_time + timedelta(minutes=j * 15)

                step_mem = client.memory.create(
                    agent_id=AGENT_ID,
                    data={
                        "memory_type": "episodic",
                        "record_type": "belief" if step["type"] in ["hypothesis", "observation"] else "episode",
                        "content": f"[{step['type'].upper()}] {step['content']}",
                        "session_id": session["id"],
                        "confidence": step["confidence"],
                        "related_to": [prev_step_id] if prev_step_id else [],
                        "topics": session["topics"],
                    }
                )
                prev_step_id = step_mem.id
                created_count += 1

        except Exception as e:
            logger.warning(f"Failed to create session {session['id']}: {e}")

    logger.info(f"Code agent context seeding complete. Created {created_count} memories.")

    # Print summary
    print("\n" + "=" * 60)
    print("  CODE AGENT CONTEXT - SEED COMPLETE")
    print("=" * 60)
    print(f"\n  Agent ID: {AGENT_ID}")
    print(f"  Memories Created: {created_count}")
    print(f"    - Patterns: {len(PATTERNS)}")
    print(f"    - Error Categories: {len(ERROR_CATEGORIES)}")
    print(f"    - Sessions: {len(SESSIONS)}")
    print(f"    - Reasoning Steps: {sum(len(s) for s in REASONING_STEPS.values())}")
    print("\n  Next Steps:")
    print("    1. Run: python web_ui.py --port 8120")
    print("    2. Open: http://localhost:8120")
    print("    3. Run: python simulation.py (optional)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    seed_code_agent_context()
