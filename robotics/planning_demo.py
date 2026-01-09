#!/usr/bin/env python3
"""
Planning API Demo
=================

This script demonstrates how to use the PDDL Planning API with the DTaaS SDK.
It shows the workflow of:
1. Creating a PDDL domain
2. Validating PDDL content
3. Generating a plan from a problem specification
4. Executing plan actions

Usage:
    python planning_demo.py [--base-url URL]

Prerequisites:
    - TesseraiDB server running (default: http://localhost:8080)
    - Python SDK installed (dtaas package)
"""

import os
import sys
import argparse

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'sdks', 'python'))

from dtaas import DTaaSClient
from dtaas.exceptions import DTaaSError, NotFoundError, ValidationError

# Add common module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import DEFAULT_BASE_URL, DEFAULT_USERNAME, DEFAULT_PASSWORD, login

# Configuration
BASE_URL = os.environ.get("DTAAS_URL", DEFAULT_BASE_URL)


def get_token():
    """Get authentication token via login."""
    username = os.environ.get("DTAAS_USERNAME", DEFAULT_USERNAME)
    password = os.environ.get("DTAAS_PASSWORD", DEFAULT_PASSWORD)
    return login(BASE_URL, username, password)

# PDDL domain for simple robot navigation (STRIPS-only)
SIMPLE_DOMAIN = """
(define (domain robot-nav)
  (:requirements :strips :typing)
  (:types robot location)
  (:predicates
    (at ?r - robot ?l - location)
    (adjacent ?l1 - location ?l2 - location)
    (goal-location ?l - location)
  )
  (:action move
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (and (at ?r ?from) (adjacent ?from ?to))
    :effect (and (at ?r ?to) (not (at ?r ?from)))
  )
)
"""

# PDDL problem: robot at loc1, goal is loc3
SIMPLE_PROBLEM = """
(define (problem reach-goal)
  (:domain robot-nav)
  (:objects
    robot1 - robot
    loc1 loc2 loc3 - location
  )
  (:init
    (at robot1 loc1)
    (adjacent loc1 loc2)
    (adjacent loc2 loc1)
    (adjacent loc2 loc3)
    (adjacent loc3 loc2)
    (goal-location loc3)
  )
  (:goal (at robot1 loc3))
)
"""


def demo_planning_api(base_url: str, token: str):
    """Demonstrate the PDDL Planning API workflow."""

    print("=" * 60)
    print(" PDDL Planning API Demo")
    print("=" * 60)
    print(f"\nConnecting to: {base_url}")

    client = DTaaSClient(base_url, token=token)

    # Check server health
    try:
        health = client.health()
        print(f"Server status: {health.status}")
    except Exception as e:
        print(f"ERROR: Could not connect to server: {e}")
        return False

    domain_id = "demo-robot-nav"

    # Step 1: Validate PDDL domain
    print("\n" + "-" * 60)
    print(" Step 1: Validate PDDL Domain")
    print("-" * 60)

    try:
        validation = client.planning.validate(SIMPLE_DOMAIN)
        print(f"  Valid: {validation.valid}")
        print(f"  Type: {validation.pddl_type}")
        if validation.errors:
            print(f"  Errors: {validation.errors}")
        if validation.warnings:
            print(f"  Warnings: {validation.warnings}")
        if not validation.valid:
            print("  WARNING: Domain validation failed, continuing anyway...")
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # Step 2: Create or update domain
    print("\n" + "-" * 60)
    print(" Step 2: Create PDDL Domain")
    print("-" * 60)

    try:
        # Delete if exists (for demo repeatability)
        try:
            client.planning.delete_domain(domain_id)
            print(f"  Deleted existing domain: {domain_id}")
        except NotFoundError:
            pass

        domain = client.planning.create_domain({
            "id": domain_id,
            "name": "Robot Navigation Domain",
            "pddl": SIMPLE_DOMAIN,
        })
        print(f"  Created domain: {domain.id}")
        print(f"  Domain name: {domain.name}")
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # Step 3: List domains
    print("\n" + "-" * 60)
    print(" Step 3: List PDDL Domains")
    print("-" * 60)

    try:
        domains = client.planning.list_domains()
        print(f"  Found {len(domains)} domain(s):")
        for d in domains:
            print(f"    - {d.id}")
    except Exception as e:
        print(f"  ERROR: {e}")

    # Step 4: Generate plan
    print("\n" + "-" * 60)
    print(" Step 4: Generate Plan")
    print("-" * 60)

    try:
        plan = client.planning.plan(
            domain_id=domain_id,
            problem_pddl=SIMPLE_PROBLEM,
            timeout_ms=5000,
        )

        print(f"  Plan ID: {plan.id}")
        print(f"  Valid: {plan.valid}")
        print(f"  Actions ({len(plan.actions)}):")

        for i, action in enumerate(plan.actions):
            params = " ".join(action.parameters)
            print(f"    {i+1}. {action.name} {params}")

        print(f"\n  Statistics:")
        print(f"    Planning time: {plan.stats.planning_time_ms}ms")
        print(f"    States explored: {plan.stats.states_explored}")
        print(f"    Planner: {plan.stats.planner}")

    except ValidationError as e:
        print(f"  Planning failed: {e}")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

    # Step 5: Demonstrate plan execution (simulated)
    print("\n" + "-" * 60)
    print(" Step 5: Execute Plan (Simulated)")
    print("-" * 60)

    robot_position = "loc1"
    print(f"  Initial position: {robot_position}")

    for action in plan.actions:
        if action.name == "move":
            _, from_loc, to_loc = action.parameters
            if robot_position == from_loc:
                robot_position = to_loc
                print(f"  Executing: move from {from_loc} to {to_loc}")
                print(f"    New position: {robot_position}")
            else:
                print(f"  ERROR: Robot not at expected location {from_loc}")
                break

    goal_reached = robot_position == "loc3"
    print(f"\n  Goal reached: {goal_reached}")

    # Cleanup
    print("\n" + "-" * 60)
    print(" Cleanup")
    print("-" * 60)

    try:
        client.planning.delete_domain(domain_id)
        print(f"  Deleted domain: {domain_id}")
    except Exception as e:
        print(f"  Cleanup error: {e}")

    print("\n" + "=" * 60)
    print(" Demo Complete")
    print("=" * 60)

    return True


def main():
    parser = argparse.ArgumentParser(description="PDDL Planning API Demo")
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help=f"DTaaS server URL (default: {BASE_URL})",
    )
    parser.add_argument(
        "--username",
        default=DEFAULT_USERNAME,
        help="Username for authentication",
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_PASSWORD,
        help="Password for authentication",
    )
    args = parser.parse_args()

    # Login to get token
    token = login(args.base_url, args.username, args.password)

    success = demo_planning_api(args.base_url, token)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
