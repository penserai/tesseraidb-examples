# Code Agent Context Management

A semantic memory system for autonomous coding agents that enables persistent context, reasoning chains, and pattern learning across coding sessions.

## Overview

This example demonstrates how AI coding assistants can use TesseraiDB's semantic memory to:

- **Working Memory**: Maintain session goals, constraints, and active context
- **Episodic Memory**: Log reasoning steps, decisions, and executed actions
- **Semantic Memory**: Store learned patterns, successful fixes, and best practices
- **Semantic Search**: Retrieve relevant past solutions using natural language queries

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Code Agent Session                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Working    │    │   Episodic   │    │   Semantic   │  │
│  │   Memory     │───▶│   Memory     │───▶│   Memory     │  │
│  │              │    │              │    │              │  │
│  │ • Goals      │    │ • Reasoning  │    │ • Patterns   │  │
│  │ • Context    │    │ • Actions    │    │ • Solutions  │  │
│  │ • Constraints│    │ • Results    │    │ • Facts      │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│          │                   │                   │          │
│          └───────────────────┴───────────────────┘          │
│                              │                              │
│                    ┌─────────▼──────────┐                   │
│                    │  Semantic Search   │                   │
│                    │  "401 auth errors" │                   │
│                    └────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## Entities

| Type | Description | Memory Type |
|------|-------------|-------------|
| **Session** | Coding session with goal and constraints | Working |
| **ReasoningStep** | A thought or hypothesis during debugging | Episodic |
| **Action** | An executed fix or code change | Episodic |
| **Pattern** | A learned best practice or solution | Semantic |
| **ErrorCategory** | Classification of error types | Semantic |

## Running the Example

### 1. Start TesseraiDB Server

```bash
cd tesseraidb
cargo run --release
```

### 2. Seed Example Data

```bash
cd examples/code_agent_context
python seed.py
```

### 3. Launch Web UI Dashboard

```bash
python web_ui.py --port 8120
# Open http://localhost:8120
```

### 4. Run Simulation

```bash
python simulation.py
# Watch live coding sessions and memory updates
```

## Web UI Features

- **Sessions View**: Active and past coding sessions with goals
- **Memory Explorer**: Browse episodic and semantic memories
- **Search Interface**: Natural language queries across all memories
- **Pattern Library**: Learned patterns and their usage stats
- **Session Timeline**: Visual timeline of reasoning steps

## API Highlights

### Create Working Memory (Session Context)

```python
from dtaas import DTaaSClient
from dtaas.models_memory import MemoryCreate, MemoryType

client = DTaaSClient(base_url, token=token, tenant_id=tenant_id)

# Initialize session context
client.memory.create(
    agent_id="code-agent-01",
    data=MemoryCreate(
        memory_type=MemoryType.WORKING,
        content="Goal: Fix intermittent 401 errors in auth service",
        session_id="session-123",
        topics=["bugfix", "auth", "api"],
        importance_weight=1.5,
    )
)
```

### Log Reasoning Step

```python
# Record a hypothesis
client.memory.create(
    agent_id="code-agent-01",
    data=MemoryCreate(
        memory_type=MemoryType.EPISODIC,
        record_type=RecordType.BELIEF,
        content="Clock skew between servers may cause JWT exp failures",
        session_id="session-123",
        confidence=0.8,
    )
)
```

### Semantic Search for Past Solutions

```python
results = client.memory.query(
    agent_id="code-agent-01",
    query=MemoryQuery(
        query="intermittent 401 unauthorized errors jwt",
        memory_types=[MemoryType.SEMANTIC, MemoryType.EPISODIC],
        min_relevance=0.7,
        limit=5
    )
)

for mem in results.memories:
    print(f"Found: {mem.content[:80]}...")
```

### Promote Pattern to Long-Term Memory

```python
# After successful fix, save as reusable pattern
client.memory.create(
    agent_id="code-agent-01",
    data=MemoryCreate(
        memory_type=MemoryType.SEMANTIC,
        record_type=RecordType.FACT,
        content="JWT validation requires 30s clock skew leeway for distributed systems",
        topics=["auth", "jwt", "best-practice"],
        confidence=0.95,
    )
)
```

## Simulation Scenarios

The simulation generates realistic coding agent sessions:

1. **Bug Investigation**: Agent investigates intermittent errors
2. **Feature Development**: Agent implements new functionality
3. **Refactoring**: Agent improves code structure
4. **Documentation**: Agent generates or updates docs

Each scenario demonstrates:
- Context initialization
- Multi-step reasoning
- Pattern retrieval
- Knowledge consolidation

## Related

- [Personal Assistant](../personal_assistant/) - Context-aware mobile assistance
- [Process Evolution](../process_evolution/) - Business process optimization
- [Memory API Reference](../../sdks/python/dtaas/resources/memory.py)
