# Real-Time Alerting System Example

A production-grade alerting and monitoring system demonstrating TesserAI DB's capabilities for real-time operations. This example proves TesserAI's readiness for mission-critical monitoring use cases.

## Overview

This example implements a complete alerting system with configurable rules, multi-severity classification, alert lifecycle management, and notification channels. It simulates realistic metric data with anomalies and provides a live dashboard for monitoring.

### Key Features

- **Configurable Alert Rules**: Threshold-based rules with duration requirements
- **Multi-Severity Alerts**: Critical, warning, and info levels with escalation
- **Alert Lifecycle**: Open, acknowledged, resolved states with timestamps
- **Notification Channels**: Console, webhook, and log-based notifications
- **Alert Deduplication**: Prevents duplicate alerts for the same condition
- **Escalation Policies**: Time-based escalation to different channels
- **Chaos Engineering**: Random anomaly injection for testing
- **Live Dashboard**: Real-time terminal visualization

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Alerting System                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐     metrics      ┌─────────────┐     alerts    ┌────────┐ │
│  │  Monitored  │ ────────────────►│  Alert      │ ─────────────►│ Notif  │ │
│  │  Systems    │                  │  Engine     │               │ Channels│ │
│  └─────────────┘                  └─────────────┘               └────────┘ │
│   Web Servers                      │         │                    Console  │
│   Databases                        │         │                    Webhook  │
│   Services                    ┌────┴────┐    │                    Log      │
│   Queues                      │  Rules  │    │                             │
│                               └─────────┘    │                             │
│                                              ▼                             │
│                               ┌─────────────────────────────┐              │
│                               │      Alert Twins            │              │
│                               │  (lifecycle, history)       │              │
│                               └─────────────────────────────┘              │
│                                              │                             │
│                                              ▼                             │
│                               ┌─────────────────────────────┐              │
│                               │      Dashboard              │              │
│                               │  (real-time monitoring)     │              │
│                               └─────────────────────────────┘              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Files

| File | Description |
|------|-------------|
| `seed.py` | Creates monitored systems, alert rules, and notification channels |
| `monitor.py` | Real-time monitoring daemon with alert detection and lifecycle |
| `simulator.py` | Generates realistic metrics with anomaly injection |
| `dashboard.py` | Live terminal dashboard with system health overview |

## Quick Start

### Prerequisites

```bash
# Ensure TesserAI DB server is running
cd /path/to/tesseraidb
cargo run

# Install Python dependencies
pip install dtaas requests
```

### Step 1: Seed Alerting Configuration

```bash
cd tesseraidb/examples
python -m alerting_system.seed

# Options:
#   --base-url URL    DTaaS server URL (default: http://localhost:8080)
```

Expected output:
```
Creating alerting system configuration...

Creating monitored systems...
  Created web-server-1 (WebServer)
  Created web-server-2 (WebServer)
  Created db-primary (DatabaseServer)
  Created db-replica-1 (DatabaseServer)
  Created api-service (ApplicationService)
  Created worker-service (ApplicationService)
  Created message-queue-1 (MessageQueue)
  ...

Creating alert rules...
  Created rule-cpu-critical (threshold: cpuUsage > 90 for 60s)
  Created rule-cpu-warning (threshold: cpuUsage > 70 for 120s)
  Created rule-memory-critical (threshold: memoryUsage > 95 for 60s)
  Created rule-disk-critical (threshold: diskUsage > 90 for 300s)
  Created rule-latency-high (threshold: avgLatencyMs > 500 for 30s)
  Created rule-error-rate (threshold: errorRate > 5 for 60s)
  ...

Creating notification channels...
  Created channel-console (ConsoleChannel)
  Created channel-webhook-ops (WebhookChannel)
  Created channel-log-audit (LogChannel)

Creating escalation policies...
  Created escalation-critical (stages: console → webhook → pagerduty)
  Created escalation-warning (stages: log → console)

Summary:
  Systems created: 12
  Alert rules created: 15
  Notification channels: 3
  Escalation policies: 2
```

### Step 2: Start Metric Simulator

The simulator generates realistic metric data with natural variation:

```bash
python -m alerting_system.simulator

# Options:
#   --base-url URL      DTaaS server URL
#   --interval SECONDS  Update interval (default: 5)
#   --chaos             Enable random anomaly injection
#   --scenario NAME     Inject specific scenario
```

Normal mode:
```bash
python -m alerting_system.simulator
```

Output:
```
Starting metric simulator...
Loaded 12 systems for simulation

Simulating 12 systems
Update interval: 5.0s
Chaos mode: OFF

Press Ctrl+C to stop

[14:30:05] Simulating 12 systems | Elapsed: 60s | Active anomalies: 0
```

Chaos mode (random failures):
```bash
python -m alerting_system.simulator --chaos
```

Output:
```
[14:31:15] Simulating 12 systems | Elapsed: 120s | Active anomalies: 2
  Injected SPIKE anomaly into web-server-1 for 45s
  Injected DEGRADATION anomaly into db-primary for 90s
```

Specific scenarios:
```bash
python -m alerting_system.simulator --scenario spike
python -m alerting_system.simulator --scenario degradation
python -m alerting_system.simulator --scenario cascade
python -m alerting_system.simulator --scenario recovery
```

### Step 3: Start Alert Monitor

The monitor evaluates rules and manages alert lifecycle:

```bash
python -m alerting_system.monitor

# Options:
#   --base-url URL      DTaaS server URL
#   --interval SECONDS  Check interval (default: 10)
```

Output:
```
Starting alert monitor...
Loaded 12 systems and 15 rules

Alert Monitor Active
Check interval: 10.0s

Press Ctrl+C to stop

[14:32:00] Checking 12 systems against 15 rules...
[14:32:00] ✓ All systems healthy

[14:32:10] Checking 12 systems against 15 rules...
[14:32:10] ⚠ ALERT TRIGGERED: rule-cpu-warning on web-server-1
           CPU usage at 78% (threshold: 70%)
           Notifying: channel-console

[14:32:20] Checking 12 systems against 15 rules...
[14:32:20] 🔴 ALERT TRIGGERED: rule-cpu-critical on web-server-1
           CPU usage at 94% (threshold: 90%)
           Notifying: channel-console, channel-webhook-ops
           Escalation started: escalation-critical

[14:32:50] Checking 12 systems against 15 rules...
[14:32:50] ✓ ALERT RESOLVED: rule-cpu-critical on web-server-1
           Duration: 30s
           Resolution: metric returned to normal

[14:33:00] Summary: 2 active alerts (1 critical, 1 warning)
```

### Step 4: Live Dashboard

```bash
python -m alerting_system.dashboard

# Options:
#   --base-url URL      DTaaS server URL
#   --refresh SECONDS   Refresh interval (default: 5)
```

Output:
```
╔════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                  REAL-TIME ALERTING DASHBOARD                                  ║
║                                     2024-01-15 14:35:22                                       ║
╚════════════════════════════════════════════════════════════════════════════════════════════════╝

 OVERVIEW
────────────────────────────────────────────────────────────────────────────────────────────────────
 Systems: ● 8 healthy  ● 3 degraded  ● 1 unhealthy
 Alerts:  ● 1 critical  ● 2 warning

 SYSTEM STATUS
────────────────────────────────────────────────────────────────────────────────────────────────────
 System                    Type              CPU          Memory       Errors     Status
────────────────────────────────────────────────────────────────────────────────────────────────────
 web-server-1              WebServer         ██████████ 94% ████████░░ 78%  0.12%  CRITICAL
 db-primary                DatabaseServer    ███████░░░ 72% ██████████ 95%  0.05%  WARNING
 api-service               ApplicationService████████░░ 81% ███████░░░ 68%  2.34%  WARNING
 worker-service            ApplicationService███████░░░ 65% ██████░░░░ 58%  0.08%  HEALTHY
 message-queue-1           MessageQueue      ████░░░░░░ 42% ██████░░░░ 55%  0.00%  HEALTHY
 ...

 ACTIVE ALERTS
────────────────────────────────────────────────────────────────────────────────────────────────────
 Severity   Source                    Metric          Value      Threshold   Age      Status
────────────────────────────────────────────────────────────────────────────────────────────────────
 CRITICAL   web-server-1              cpuUsage        94.00      90.00       5m       OPEN
 WARNING    db-primary                memoryUsage     95.20      90.00       3m       ACK
 WARNING    api-service               errorRate       2.34       2.00        1m       OPEN

 ALERT RULES
────────────────────────────────────────────────────────────────────────────────────────────────────
 Total: 15 | Enabled: 15 | Currently Triggered: 3

 Triggered Rules:
   - High CPU (Critical)
   - High Memory (Warning)
   - Elevated Error Rate

────────────────────────────────────────────────────────────────────────────────────────────────────
 Refresh: 5s | Systems: 12 | Rules: 15 | Press Ctrl+C to exit
```

## Alert Rules

### CPU Rules
| Rule | Threshold | Duration | Severity |
|------|-----------|----------|----------|
| `rule-cpu-critical` | > 90% | 60s | critical |
| `rule-cpu-warning` | > 70% | 120s | warning |

### Memory Rules
| Rule | Threshold | Duration | Severity |
|------|-----------|----------|----------|
| `rule-memory-critical` | > 95% | 60s | critical |
| `rule-memory-warning` | > 80% | 180s | warning |

### Disk Rules
| Rule | Threshold | Duration | Severity |
|------|-----------|----------|----------|
| `rule-disk-critical` | > 90% | 300s | critical |
| `rule-disk-warning` | > 75% | 600s | warning |

### Latency Rules
| Rule | Threshold | Duration | Severity |
|------|-----------|----------|----------|
| `rule-latency-critical` | > 1000ms | 30s | critical |
| `rule-latency-high` | > 500ms | 60s | warning |

### Error Rate Rules
| Rule | Threshold | Duration | Severity |
|------|-----------|----------|----------|
| `rule-error-critical` | > 10% | 30s | critical |
| `rule-error-rate` | > 5% | 60s | warning |

### Database-Specific
| Rule | Threshold | Duration | Severity |
|------|-----------|----------|----------|
| `rule-replication-lag` | > 1000ms | 60s | critical |
| `rule-slow-queries` | > 50/s | 120s | warning |

### Queue-Specific
| Rule | Threshold | Duration | Severity |
|------|-----------|----------|----------|
| `rule-queue-depth` | > 10000 | 120s | critical |
| `rule-dead-letters` | > 100 | 60s | warning |

## System Types

### Web Server
**Metrics**: cpuUsage, memoryUsage, diskUsage, requestsPerSecond, responseTimeMs, errorRate, activeConnections

### Database Server
**Metrics**: cpuUsage, memoryUsage, diskUsage, connections, queriesPerSecond, avgQueryTimeMs, slowQueries, replicationLagMs

### Application Service
**Metrics**: cpuUsage, memoryUsage, requestsPerSecond, avgLatencyMs, p99LatencyMs, errorRate, successRate

### Message Queue
**Metrics**: messageCount, consumerCount, publishRate, consumeRate, oldestMessageAge, deadLetterCount

## Anomaly Scenarios

### Spike
Sudden resource spike affecting web servers.
- CPU increases by 50-75%
- Response time increases proportionally
- Duration: 45-90 seconds

### Degradation
Gradual performance degradation.
- Slow increase in CPU and memory
- Error rate climbs over time
- Duration: 2-3 minutes

### Cascade
Simulates cascading failure starting from database.
- Primary DB experiences outage
- Dependent services degrade
- Error rates spike across system

### Recovery
Clears all active anomalies.
- All metrics return to normal baselines
- Useful for testing alert resolution

## Alert Lifecycle

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    ALERT LIFECYCLE                      │
                    └─────────────────────────────────────────────────────────┘

  Threshold        Duration           First            Manual           Metric
  Exceeded         Exceeded           Notification     Ack              Normal
      │                │                   │              │                │
      ▼                ▼                   ▼              ▼                ▼
┌──────────┐     ┌───────────┐      ┌───────────┐   ┌───────────┐   ┌──────────┐
│ PENDING  │────►│  FIRING   │─────►│   OPEN    │──►│  ACK'D    │──►│ RESOLVED │
└──────────┘     └───────────┘      └───────────┘   └───────────┘   └──────────┘
     │                │                                   │
     │                │                                   │
     │                │              Escalation           │
     │                │              Timer                │
     │                │                │                  │
     │                ▼                ▼                  │
     │           ┌───────────────────────────────┐       │
     │           │        ESCALATED              │       │
     │           │  (additional notifications)   │       │
     │           └───────────────────────────────┘       │
     │                                                    │
     │                    Metric Returns Normal           │
     └─────────────────── (before duration) ─────────────►│
```

## Integration with TesserAI DB

This example demonstrates production features:

1. **Twin-Based Alerts**: Each alert is a Digital Twin with full lifecycle
2. **Real-Time Updates**: Continuous metric updates via DTaaS API
3. **Relationship Modeling**: Rules, channels, and escalations as twins
4. **Event Streaming**: Subscribe to alert changes via SSE
5. **Historical Queries**: Query alert history with SPARQL

### Example Queries

Find all active critical alerts:
```sparql
PREFIX alert: <http://tesserai.dev/ontology/alerting_system#>
SELECT ?alert ?source ?metric ?value WHERE {
  ?alert a alert:Alert .
  ?alert alert:status "open" .
  ?alert alert:severity "critical" .
  ?alert alert:sourceId ?source .
  ?alert alert:metric ?metric .
  ?alert alert:currentValue ?value .
}
```

Get alert history for a system:
```sparql
PREFIX alert: <http://tesserai.dev/ontology/alerting_system#>
SELECT ?alert ?triggered ?resolved ?duration WHERE {
  ?alert a alert:Alert .
  ?alert alert:sourceId "web-server-1" .
  ?alert alert:triggeredAt ?triggered .
  OPTIONAL { ?alert alert:resolvedAt ?resolved }
  BIND(IF(BOUND(?resolved), ?resolved - ?triggered, 0) AS ?duration)
}
ORDER BY DESC(?triggered)
LIMIT 100
```

## Customization

### Adding Alert Rules

Edit `seed.py` to add new rules:

```python
CUSTOM_RULES = [
    {
        "id": "rule-custom-metric",
        "name": "Custom Metric Alert",
        "metric": "customMetric",
        "operator": "gt",      # gt, lt, eq, ne, gte, lte
        "threshold": 100,
        "duration": 60,        # seconds threshold must be exceeded
        "severity": "warning",
        "enabled": True,
    }
]
```

### Adding Notification Channels

```python
CUSTOM_CHANNELS = [
    {
        "id": "channel-slack",
        "name": "Slack Notifications",
        "type": "WebhookChannel",
        "properties": {
            "url": "https://hooks.slack.com/...",
            "format": "slack",
        }
    }
]
```

### Custom Escalation Policies

```python
CUSTOM_ESCALATION = {
    "id": "escalation-custom",
    "name": "Custom Escalation",
    "stages": [
        {"delay": 0, "channels": ["channel-log"]},
        {"delay": 300, "channels": ["channel-console"]},
        {"delay": 900, "channels": ["channel-slack"]},
        {"delay": 1800, "channels": ["channel-pagerduty"]},
    ]
}
```

## RSP and CEP-Style Pattern Detection

This example includes RDF Stream Processing (RSP) with CEP-style temporal patterns for detecting sophisticated failure scenarios. Note: RSP provides continuous query execution over sliding windows; sequence detection is implemented via SPARQL timestamp comparison rather than native CEP operators.

### Web Dashboard with RSP

Start the web-based dashboard (instead of terminal dashboard):

```bash
python web_ui.py
# Open http://localhost:8085 in your browser
```

The dashboard shows RSP query results in real-time and allows you to:
- Click on RSP query boxes to view SPARQL definitions
- Click on alert rules to see threshold configurations
- Inject scenarios (spike, cascade, degradation, recovery)

### Pattern Types

The dashboard implements two types of patterns:

#### 1. Concurrent Patterns (Simultaneous Conditions)

Detect when multiple conditions are true at the same time:

```sparql
# Cross-Tier Failure Correlation
# Fires when BOTH frontend AND backend systems are degraded
SELECT ?frontendCount ?backendCount
WHERE {
    { SELECT (COUNT(?f) AS ?frontendCount) WHERE { ?f dto:cpuUsage ?cpu . FILTER(?cpu > 50) } }
    { SELECT (COUNT(?b) AS ?backendCount) WHERE { ?b dto:cpuUsage ?cpu . FILTER(?cpu > 40) } }
    FILTER(?frontendCount >= 1 && ?backendCount >= 1)
}
```

#### 2. Temporal Sequence Patterns (Events in Order)

Detect when events occur in a specific temporal order: Event A → Event B → Event C.

**How It Works:**

1. **Events are stored as ISO 8601 timestamps** on the twin:
   ```
   ?system dto:highCpuEvent "2025-12-29T07:10:07.123456" .
   ?system dto:highMemoryEvent "2025-12-29T07:10:32.789012" .
   ```

2. **SPARQL compares timestamps using string comparison**:
   ```sparql
   FILTER(STR(?cpuTime) < STR(?memTime))
   ```

3. **Why string comparison works for temporal ordering:**

   ISO 8601 timestamps are **lexicographically sortable** - string comparison produces the same result as chronological comparison because:
   - Year comes first (4 digits)
   - Month comes next (2 digits, zero-padded)
   - Day, hour, minute, second follow in order
   - All components are fixed-width and zero-padded

   ```
   "2025-12-29T07:10:07" < "2025-12-29T07:10:32"  ← String comparison
   2025-12-29 07:10:07   < 2025-12-29 07:10:32    ← Temporal comparison
   Both are TRUE because ISO 8601 is lexicographically sortable!
   ```

**Complete Sequence Pattern Example:**

```sparql
PREFIX dto: <http://tesserai.io/ontology/alerting_system#>

# Resource Exhaustion Sequence: CPU spike → Memory pressure → Disk full
# This pattern detects cascading resource exhaustion where:
#   T1: CPU crosses threshold (recorded as highCpuEvent timestamp)
#   T2: Memory crosses threshold (recorded as highMemoryEvent timestamp)
#   T3: Disk crosses threshold (recorded as highDiskEvent timestamp)
# Only fires if T1 < T2 < T3 (events happened in that order)

SELECT ?system ?cpuTime ?memTime ?diskTime
WHERE {
    # Match systems that have all three event timestamps
    ?system dto:highCpuEvent ?cpuTime .
    ?system dto:highMemoryEvent ?memTime .
    ?system dto:highDiskEvent ?diskTime .

    FILTER(
        # Ensure all timestamps are present and non-empty
        BOUND(?cpuTime) && ?cpuTime != "" &&
        BOUND(?memTime) && ?memTime != "" &&
        BOUND(?diskTime) && ?diskTime != "" &&

        # TEMPORAL ORDERING: T1 < T2 < T3
        # String comparison of ISO timestamps = chronological comparison
        STR(?cpuTime) < STR(?memTime) &&
        STR(?memTime) < STR(?diskTime)
    )
}
```

### Event Tracking Mechanism

When a metric crosses a threshold, the system records a timestamp:

```python
# When CPU > 70%, record the event timestamp
if cpu_value > 70.0 and "highCpuEvent" not in active_events:
    event_timestamp = datetime.now().isoformat()  # "2025-12-29T07:10:07.123456"
    twin_update({"highCpuEvent": event_timestamp})
    active_events["highCpuEvent"] = event_timestamp

# When CPU returns below 60%, clear the event
if cpu_value < 60.0 and "highCpuEvent" in active_events:
    twin_update({"highCpuEvent": ""})
    del active_events["highCpuEvent"]
```

This enables detecting **new** sequences - after events clear and thresholds are crossed again in order, a new sequence can be detected.

### Available Patterns

| Pattern | Type | Description |
|---------|------|-------------|
| Resource Exhaustion Sequence | Temporal | CPU → Memory → Disk (in order) |
| Performance Degradation Sequence | Temporal | Slow response → High latency → Errors (in order) |
| Queue Pressure Sequence | Temporal | Backlog → Stale messages → DLQ growth (in order) |
| CPU-Memory Cascade | Temporal | CPU → Memory (2-event sequence) |
| Cross-Tier Failure Correlation | Concurrent | Frontend AND backend degraded simultaneously |
| Incident Blast Radius | Concurrent | Count of distinct affected systems |

### Why Use Temporal Sequences?

Temporal sequence detection is valuable for:

1. **Root Cause Analysis**: CPU spike → Memory exhaustion → Disk full tells you CPU was the root cause
2. **Predictive Alerting**: Detecting early stages of a cascade before full failure
3. **Reducing Alert Noise**: Only alert when the full pattern completes, not on individual events
4. **Compliance**: Some regulations require proving event ordering for audit trails

### Testing Sequence Patterns

Sequence patterns require events to occur in the correct order. To test:

1. **Manual testing**: Use scenarios that push metrics above thresholds in sequence:
   ```
   # In the web dashboard, click "Inject Scenario" → "Spike"
   # This raises CPU and memory on web servers
   ```

2. **Verify event timestamps** are being recorded:
   ```bash
   curl -s "http://localhost:8080/api/v1/twins/json/urn:tesserai:twin:web-server-001" | \
     python3 -c "import json,sys; d=json.load(sys.stdin)['properties']; \
     print('\n'.join(f'{k}: {v}' for k,v in d.items() if 'Event' in k))"
   ```

3. **Check RSP query results** in the dashboard - sequence patterns show timestamps in the alert message:
   ```
   web-server-001: SEQUENCE CPU(07:10:07) -> Mem(07:10:32) -> Disk(07:15:45)
   ```

## Troubleshooting

**"No systems found"**
```
Run seed.py first to create systems and rules
```

**"Alerts not triggering"**
```
1. Ensure simulator is running with anomalies (--chaos or --scenario)
2. Check that rules match the metrics being generated
3. Verify duration thresholds (alert triggers after sustained violation)
```

**"Dashboard shows stale data"**
```
1. Check that simulator is updating metrics
2. Verify connection to DTaaS server
3. Try reducing --refresh interval
```

**"Notifications not working"**
```
1. Check notification channel configuration
2. Verify webhook URLs are accessible
3. Check monitor logs for channel errors
```
