#!/usr/bin/env python3
"""
Personal Assistant - Live Simulation

Simulates a day in the life with location changes and context triggers:
- Morning routine at home
- Commute and coffee stop
- Work day at office
- Lunch at restaurant
- Shopping errands
- Evening at home

Usage:
    python simulation.py

Watch the web UI to see context-triggered memories.
"""

import sys
import os
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Agent configuration
AGENT_ID = "assistant-user-alex"

# Day simulation timeline
DAY_EVENTS = [
    {
        "time": "7:00 AM",
        "location": "Home",
        "category": "home",
        "duration_mins": 60,
        "description": "Morning routine - wake up, shower, breakfast",
        "triggers": ["medication reminder", "calendar overview"],
    },
    {
        "time": "8:00 AM",
        "location": "Blue Bottle Coffee",
        "category": "cafe",
        "duration_mins": 10,
        "description": "Quick coffee stop on commute",
        "triggers": ["favorite order", "loyalty card"],
    },
    {
        "time": "8:30 AM",
        "location": "TechCorp Office",
        "category": "work",
        "duration_mins": 180,
        "description": "Morning work block - meetings and emails",
        "triggers": ["meeting preferences", "manager contact"],
    },
    {
        "time": "12:00 PM",
        "location": "Saigon Kitchen",
        "category": "restaurant",
        "duration_mins": 45,
        "description": "Lunch break at favorite restaurant",
        "triggers": ["dietary preferences", "pescatarian options"],
    },
    {
        "time": "1:00 PM",
        "location": "TechCorp Office",
        "category": "work",
        "duration_mins": 240,
        "description": "Afternoon deep work block",
        "triggers": ["calendar blocks", "do not disturb"],
    },
    {
        "time": "5:30 PM",
        "location": "Whole Foods Market",
        "category": "grocery",
        "duration_mins": 25,
        "description": "Grocery shopping on way home",
        "triggers": ["shopping reminders", "allergy warnings", "coffee beans"],
    },
    {
        "time": "6:15 PM",
        "location": "CVS Pharmacy",
        "category": "pharmacy",
        "duration_mins": 10,
        "description": "Quick stop for prescriptions",
        "triggers": ["medication refill", "birthday card for Sarah"],
    },
    {
        "time": "6:45 PM",
        "location": "Home",
        "category": "home",
        "duration_mins": 180,
        "description": "Evening at home - dinner, relaxation",
        "triggers": ["evening medication", "library book reminder"],
    },
]


def run_simulation():
    """Run the day simulation."""
    client = get_client()

    print("\n" + "=" * 60)
    print("  PERSONAL ASSISTANT - DAY SIMULATION")
    print("=" * 60)
    print(f"\n  Agent: {AGENT_ID}")
    print("  Simulating a day with location changes")
    print("  Watch the web UI to see context triggers")
    print("\n  Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    try:
        while True:
            for event in DAY_EVENTS:
                print(f"\n[{event['time']}] Arriving at {event['location']}")
                print(f"  {event['description']}")

                # Log the visit
                try:
                    client.memory.create(
                        agent_id=AGENT_ID,
                        data={
                            "memory_type": "episodic",
                            "content": f"Arrived at {event['location']} - {event['description']}",
                            "topics": ["location-history", event["category"], "simulation"],
                            "metadata": {
                                "location": event["location"],
                                "category": event["category"],
                                "duration_mins": event["duration_mins"],
                                "simulated_time": event["time"],
                            },
                            "source": {"source_type": "system"},
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to log visit: {e}")

                # Query for relevant context
                print("\n  Searching for relevant memories...")
                try:
                    result = client.memory.query(
                        agent_id=AGENT_ID,
                        query={
                            "query": f"relevant to {event['location']} {event['category']}",
                            "limit": 5,
                            "min_relevance": 0.5,
                        }
                    )

                    if result.memories:
                        print(f"  Found {len(result.memories)} relevant memories:")
                        for mem in result.memories[:3]:
                            mem_dict = mem.model_dump() if hasattr(mem, 'model_dump') else mem
                            content = mem_dict.get("content", "")[:60]
                            mem_type = mem_dict.get("memory_type", "")
                            print(f"    - [{mem_type}] {content}...")
                    else:
                        print("  No relevant memories found")

                except Exception as e:
                    logger.warning(f"Query failed: {e}")

                # Show expected triggers
                if event["triggers"]:
                    print(f"\n  Expected triggers: {', '.join(event['triggers'])}")

                # Wait before next event
                wait_time = random.randint(3, 8)
                print(f"\n  Next event in {wait_time} seconds...")
                time.sleep(wait_time)

            print("\n" + "=" * 60)
            print("  Day complete! Restarting simulation...")
            print("=" * 60)
            time.sleep(5)

    except KeyboardInterrupt:
        print("\n\nSimulation stopped.")


if __name__ == "__main__":
    run_simulation()
