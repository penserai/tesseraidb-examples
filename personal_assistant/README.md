# Personal Assistant

A context-aware mobile personal assistant that uses semantic memory to learn user preferences, manage reminders, and provide contextually relevant information.

## Overview

This example demonstrates how AI personal assistants can use TesseraiDB's semantic memory to:

- **User Preferences**: Remember dietary restrictions, favorite places, habits
- **Context-Aware Reminders**: Trigger reminders based on location, time, or activity
- **Location History**: Learn from past visits to provide relevant suggestions
- **Personalization**: Adapt responses based on learned user patterns

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Personal Assistant                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Preferences │    │  Reminders   │    │   Location   │  │
│  │  (Semantic)  │    │  (Episodic)  │    │   History    │  │
│  │              │    │              │    │  (Episodic)  │  │
│  │ • Diet       │    │ • Shopping   │    │ • Visits     │  │
│  │ • Favorites  │    │ • Tasks      │    │ • Duration   │  │
│  │ • Habits     │    │ • Meetings   │    │ • Patterns   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│          │                   │                   │          │
│          └───────────────────┴───────────────────┘          │
│                              │                              │
│                    ┌─────────▼──────────┐                   │
│                    │  Context Trigger   │                   │
│                    │ "At grocery store" │                   │
│                    └────────────────────┘                   │
│                              │                              │
│                    ┌─────────▼──────────┐                   │
│                    │  Relevant Memories │                   │
│                    │  • Buy coffee      │                   │
│                    │  • Avoid peanuts   │                   │
│                    └────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## Entities

| Type | Description | Memory Type |
|------|-------------|-------------|
| **Preference** | User dietary/lifestyle preferences | Semantic |
| **Reminder** | Context-triggered tasks | Episodic |
| **Visit** | Location visit history | Episodic |
| **Habit** | Learned behavioral patterns | Semantic |
| **Contact** | People and relationships | Semantic |

## Running the Example

### 1. Start TesseraiDB Server

```bash
cd tesseraidb
cargo run --release
```

### 2. Seed Example Data

```bash
cd examples/personal_assistant
python seed.py
```

### 3. Launch Web UI Dashboard

```bash
python web_ui.py --port 8122
# Open http://localhost:8122
```

### 4. Run Simulation

```bash
python simulation.py
# Simulates a day in the life with location changes
```

## Web UI Features

- **User Profile**: Preferences and dietary restrictions
- **Active Reminders**: List of pending context-aware reminders
- **Location History**: Map of recent visits
- **Memory Timeline**: Chronological view of all memories
- **Context Simulator**: Manually trigger location changes

## API Highlights

### Store User Preference

```python
from dtaas import DTaaSClient
from dtaas.models_memory import MemoryCreate, MemoryType, SourceType, MemorySource

client = DTaaSClient(base_url, token=token, tenant_id=tenant_id)

# Store dietary preference
client.memory.create(
    agent_id="assistant-user-123",
    data=MemoryCreate(
        memory_type=MemoryType.SEMANTIC,
        content="I prefer oat milk over almond milk, and I'm allergic to peanuts",
        topics=["food-preference", "dietary-restriction"],
        confidence=1.0,
        source=MemorySource(source_type=SourceType.USER),
    )
)
```

### Create Context-Aware Reminder

```python
from datetime import datetime, timedelta, timezone

# Reminder with location context
client.memory.create(
    agent_id="assistant-user-123",
    data=MemoryCreate(
        memory_type=MemoryType.EPISODIC,
        content="Buy coffee beans",
        context="Location: Grocery Store",
        topics=["reminder", "shopping"],
        valid_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
)
```

### Query by Context

```python
# When user arrives at grocery store
results = client.memory.query(
    agent_id="assistant-user-123",
    query=MemoryQuery(
        query="reminders or preferences for grocery shopping",
        context="Whole Foods Market, Downtown",
        min_relevance=0.6,
        exclude_hallucinations=True
    )
)

for mem in results.memories:
    # Trigger notification
    notify_user(mem.content)
```

### Log Location Visit

```python
# Automatically log visit
client.memory.create(
    agent_id="assistant-user-123",
    data=MemoryCreate(
        memory_type=MemoryType.EPISODIC,
        content="Visited Whole Foods Market for 20 minutes",
        topics=["location-history", "grocery"],
        metadata={"location": "Whole Foods", "duration_mins": 20},
        source=MemorySource(source_type=SourceType.SYSTEM),
    )
)
```

## Simulation Scenarios

The simulation walks through a typical day:

1. **Morning**: Wake up, check calendar, commute
2. **Work Hours**: Office context, meeting reminders
3. **Lunch**: Restaurant visit, dietary preferences
4. **Afternoon**: Shopping errands with location triggers
5. **Evening**: Home context, routine suggestions

## Related

- [Code Agent Context](../code_agent_context/) - AI coding assistant memory
- [Process Evolution](../process_evolution/) - Business process optimization
- [Memory API Reference](../../sdks/python/dtaas/resources/memory.py)
