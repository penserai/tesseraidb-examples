# Business Process Evolution

A semantic memory system for business process management that learns from execution data to identify bottlenecks and automatically evolve process definitions.

## Overview

This example demonstrates how business systems can use TesseraiDB's semantic memory to:

- **Process Definitions**: Store canonical process workflows (Semantic/Procedural)
- **Execution Logs**: Track individual process runs and outcomes (Episodic)
- **Bottleneck Detection**: Query for patterns indicating inefficiencies
- **Process Evolution**: Automatically update definitions based on evidence

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Process Management System                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Process    │    │  Execution   │    │  Analytics   │  │
│  │ Definitions  │    │    Logs      │    │   Insights   │  │
│  │  (Semantic)  │    │  (Episodic)  │    │  (Semantic)  │  │
│  │              │    │              │    │              │  │
│  │ • Steps      │    │ • Duration   │    │ • Patterns   │  │
│  │ • Rules      │    │ • Delays     │    │ • KPIs       │  │
│  │ • Versions   │    │ • Exceptions │    │ • Trends     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│          │                   │                   │          │
│          └───────────────────┴───────────────────┘          │
│                              │                              │
│                    ┌─────────▼──────────┐                   │
│                    │  Pattern Analysis  │                   │
│                    │ "Delays in step 3" │                   │
│                    └────────────────────┘                   │
│                              │                              │
│                    ┌─────────▼──────────┐                   │
│                    │  Process Evolution │                   │
│                    │   v1 → v2 → v3     │                   │
│                    └────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## Entities

| Type | Description | Memory Type |
|------|-------------|-------------|
| **ProcessDefinition** | Canonical workflow steps | Semantic (PROCEDURE) |
| **ExecutionLog** | Individual process run | Episodic |
| **StepExecution** | Single step completion | Episodic |
| **BottleneckPattern** | Identified inefficiency | Semantic (FACT) |
| **ProcessVersion** | Version with changes | Semantic |

## Running the Example

### 1. Start TesseraiDB Server

```bash
cd tesseraidb
cargo run --release
```

### 2. Seed Example Data

```bash
cd examples/process_evolution
python seed.py
```

### 3. Launch Web UI Dashboard

```bash
python web_ui.py --port 8124
# Open http://localhost:8124
```

### 4. Run Simulation

```bash
python simulation.py
# Simulates process executions with varying performance
```

## Web UI Features

- **Process Library**: All defined processes and their versions
- **Execution Dashboard**: Live process runs with status
- **Performance Analytics**: Step duration histograms, bottleneck detection
- **Evolution Timeline**: History of process changes and their triggers
- **Recommendations**: Suggested optimizations based on patterns

## API Highlights

### Define a Process

```python
from dtaas import DTaaSClient
from dtaas.models_memory import MemoryCreate, MemoryType, RecordType

client = DTaaSClient(base_url, token=token, tenant_id=tenant_id)

# Create process definition
client.memory.create(
    agent_id="process-manager",
    data=MemoryCreate(
        memory_type=MemoryType.SEMANTIC,
        record_type=RecordType.PROCEDURE,
        content="Loan Approval Process v1: 1. Receive Application -> 2. Credit Check -> 3. Manager Approval -> 4. Disburse",
        topics=["process-definition", "loan"],
        version=1,
    )
)
```

### Log Process Execution

```python
# Log a step with duration
client.memory.create(
    agent_id="process-manager",
    data=MemoryCreate(
        memory_type=MemoryType.EPISODIC,
        content="Execution #101: Manager Approval took 48 hours. Reason: Manager OOO",
        topics=["process-log", "loan", "delay"],
        metadata={
            "process_id": "loan-approval-v1",
            "execution_id": "exec-101",
            "step": "manager-approval",
            "duration_hours": 48,
            "expected_hours": 4,
        },
        related_to=["loan-approval-v1"],
    )
)
```

### Query for Bottlenecks

```python
# Find delay patterns
results = client.memory.query(
    agent_id="process-manager",
    query=MemoryQuery(
        query="delays or bottlenecks in loan approval manager approval step",
        memory_types=[MemoryType.EPISODIC],
        min_relevance=0.5,
    )
)

print(f"Found {len(results.memories)} delay incidents")
```

### Evolve Process Definition

```python
# Create new version that supersedes the old
new_process = client.memory.create(
    agent_id="process-manager",
    data=MemoryCreate(
        memory_type=MemoryType.SEMANTIC,
        record_type=RecordType.PROCEDURE,
        content="Loan Approval v2: 1. Receive -> 2. Credit Check -> 3. Auto-Approval (if <$10k) OR Manager Approval -> 4. Disburse",
        topics=["process-definition", "loan"],
        related_to=[old_process_id],
        metadata={
            "supersedes": old_process_id,
            "reason": "Optimize manager bottleneck for low-value loans",
            "evidence": ["exec-101", "exec-102", "exec-103"],
        },
    )
)
```

## Process Types Included

1. **Loan Approval** - Financial services workflow with approvals
2. **Employee Onboarding** - HR process with multiple departments
3. **Purchase Order** - Procurement with budget checks
4. **Support Ticket** - Customer service escalation flow
5. **Release Deployment** - Software delivery pipeline

## Simulation Scenarios

The simulation generates realistic process executions:

1. **Normal Flow**: Processes complete within expected times
2. **Bottleneck**: Specific step consistently slow
3. **Exception**: Process fails and needs rework
4. **Optimization**: After enough evidence, process evolves

## Related

- [Code Agent Context](../code_agent_context/) - AI coding assistant memory
- [Personal Assistant](../personal_assistant/) - Context-aware mobile assistance
- [Memory API Reference](../../sdks/python/dtaas/resources/memory.py)
