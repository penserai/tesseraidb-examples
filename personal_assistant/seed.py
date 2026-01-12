#!/usr/bin/env python3
"""
Personal Assistant - Seed Script

Seeds example data demonstrating how personal assistants use semantic memory for:
- User preferences (dietary, favorites, habits)
- Context-aware reminders
- Location history
- Learned patterns

Usage:
    python seed.py
"""

import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Agent configuration
AGENT_ID = "assistant-user-alex"

# User preferences
PREFERENCES = [
    {
        "content": "I prefer oat milk over almond milk, and I'm allergic to peanuts",
        "topics": ["food-preference", "dietary-restriction", "allergy"],
        "source": "user",
    },
    {
        "content": "I like to exercise in the morning before 8am, preferring outdoor runs over gym workouts",
        "topics": ["fitness", "schedule", "preference"],
        "source": "user",
    },
    {
        "content": "My favorite coffee order is a large oat milk latte with an extra shot",
        "topics": ["coffee", "order", "preference"],
        "source": "user",
    },
    {
        "content": "I prefer window seats on flights and always need extra legroom",
        "topics": ["travel", "flight", "preference"],
        "source": "user",
    },
    {
        "content": "I'm vegetarian but eat fish occasionally (pescatarian)",
        "topics": ["food-preference", "dietary-restriction"],
        "source": "user",
    },
    {
        "content": "I take medication at 8am and 8pm daily - Lisinopril for blood pressure",
        "topics": ["health", "medication", "schedule"],
        "source": "user",
    },
]

# Context-aware reminders
REMINDERS = [
    {
        "content": "Buy coffee beans",
        "context": "grocery store",
        "topics": ["reminder", "shopping", "coffee"],
        "priority": "medium",
    },
    {
        "content": "Pick up dry cleaning - ticket #4521",
        "context": "dry cleaner OR downtown",
        "topics": ["reminder", "errand"],
        "priority": "high",
    },
    {
        "content": "Get birthday card for Sarah",
        "context": "card shop OR pharmacy OR grocery",
        "topics": ["reminder", "birthday", "shopping"],
        "priority": "medium",
    },
    {
        "content": "Return library books - due Thursday",
        "context": "library OR home",
        "topics": ["reminder", "library"],
        "priority": "high",
    },
    {
        "content": "Schedule dentist appointment",
        "context": "home OR office",
        "topics": ["reminder", "health", "appointment"],
        "priority": "low",
    },
]

# Location history (past visits)
LOCATION_HISTORY = [
    {"location": "Whole Foods Market", "category": "grocery", "duration_mins": 25, "days_ago": 2},
    {"location": "Blue Bottle Coffee", "category": "cafe", "duration_mins": 15, "days_ago": 1},
    {"location": "TechCorp Office", "category": "work", "duration_mins": 480, "days_ago": 1},
    {"location": "Equinox Gym", "category": "fitness", "duration_mins": 60, "days_ago": 3},
    {"location": "Saigon Kitchen", "category": "restaurant", "duration_mins": 45, "days_ago": 4},
    {"location": "Central Library", "category": "library", "duration_mins": 90, "days_ago": 7},
    {"location": "CVS Pharmacy", "category": "pharmacy", "duration_mins": 10, "days_ago": 5},
    {"location": "TechCorp Office", "category": "work", "duration_mins": 510, "days_ago": 2},
]

# Learned habits/patterns
HABITS = [
    {
        "content": "Alex typically visits Whole Foods on Saturdays around 10am",
        "topics": ["habit", "shopping", "schedule"],
        "confidence": 0.85,
    },
    {
        "content": "Alex usually orders from Saigon Kitchen on Fridays for lunch",
        "topics": ["habit", "food", "restaurant"],
        "confidence": 0.8,
    },
    {
        "content": "Alex prefers morning meetings before 11am and blocks afternoons for deep work",
        "topics": ["habit", "work", "calendar"],
        "confidence": 0.9,
    },
    {
        "content": "Alex runs 3-4 times per week, usually Tuesday, Thursday, and Saturday mornings",
        "topics": ["habit", "fitness", "schedule"],
        "confidence": 0.88,
    },
]

# Important contacts
CONTACTS = [
    {
        "content": "Sarah Chen is my sister, birthday is March 15th, lives in Seattle",
        "topics": ["contact", "family"],
    },
    {
        "content": "Dr. Martinez is my primary care physician at Bay Medical, phone 555-0123",
        "topics": ["contact", "health", "doctor"],
    },
    {
        "content": "Mike is my manager at TechCorp, prefers Slack over email",
        "topics": ["contact", "work"],
    },
]


def seed_personal_assistant():
    """Seed the personal assistant example data."""
    client = get_client()

    logger.info(f"Seeding personal assistant for agent: {AGENT_ID}")
    created_count = 0

    # 1. Seed user preferences (Semantic Memory)
    logger.info("Seeding user preferences...")
    for pref in PREFERENCES:
        try:
            client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "semantic",
                    "content": pref["content"],
                    "topics": pref["topics"],
                    "confidence": 1.0,
                    "source": {"source_type": pref["source"]},
                }
            )
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create preference: {e}")

    # 2. Seed reminders (Episodic Memory with context)
    logger.info("Seeding reminders...")
    now = datetime.now(timezone.utc)
    for reminder in REMINDERS:
        try:
            client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "episodic",
                    "content": reminder["content"],
                    "context": f"Location trigger: {reminder['context']}",
                    "topics": reminder["topics"],
                    "metadata": {"priority": reminder["priority"], "type": "reminder"},
                    "valid_at": now.isoformat(),
                    "expires_at": (now + timedelta(days=14)).isoformat(),
                }
            )
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create reminder: {e}")

    # 3. Seed location history (Episodic Memory)
    logger.info("Seeding location history...")
    for visit in LOCATION_HISTORY:
        visit_time = now - timedelta(days=visit["days_ago"])
        try:
            client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "episodic",
                    "content": f"Visited {visit['location']} for {visit['duration_mins']} minutes",
                    "topics": ["location-history", visit["category"]],
                    "metadata": {
                        "location": visit["location"],
                        "category": visit["category"],
                        "duration_mins": visit["duration_mins"],
                    },
                    "source": {"source_type": "system"},
                }
            )
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create visit: {e}")

    # 4. Seed learned habits (Semantic Memory)
    logger.info("Seeding learned habits...")
    for habit in HABITS:
        try:
            client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "semantic",
                    "record_type": "fact",
                    "content": habit["content"],
                    "topics": habit["topics"],
                    "confidence": habit["confidence"],
                    "source": {"source_type": "inferred"},
                }
            )
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create habit: {e}")

    # 5. Seed contacts (Semantic Memory)
    logger.info("Seeding contacts...")
    for contact in CONTACTS:
        try:
            client.memory.create(
                agent_id=AGENT_ID,
                data={
                    "memory_type": "semantic",
                    "content": contact["content"],
                    "topics": contact["topics"],
                    "confidence": 1.0,
                    "source": {"source_type": "user"},
                }
            )
            created_count += 1
        except Exception as e:
            logger.warning(f"Failed to create contact: {e}")

    logger.info(f"Personal assistant seeding complete. Created {created_count} memories.")

    # Print summary
    print("\n" + "=" * 60)
    print("  PERSONAL ASSISTANT - SEED COMPLETE")
    print("=" * 60)
    print(f"\n  Agent ID: {AGENT_ID}")
    print(f"  Memories Created: {created_count}")
    print(f"    - Preferences: {len(PREFERENCES)}")
    print(f"    - Reminders: {len(REMINDERS)}")
    print(f"    - Location History: {len(LOCATION_HISTORY)}")
    print(f"    - Habits: {len(HABITS)}")
    print(f"    - Contacts: {len(CONTACTS)}")
    print("\n  Next Steps:")
    print("    1. Run: python web_ui.py --port 8122")
    print("    2. Open: http://localhost:8122")
    print("    3. Run: python simulation.py (optional)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    seed_personal_assistant()
