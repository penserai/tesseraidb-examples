# Alerting System Example

A production-grade alerting and monitoring system demonstrating TesseraiDB's capabilities for real-time operations and mission-critical monitoring use cases.

## Overview

- What this domain models: Complete alerting system with configurable rules, multi-severity classification, alert lifecycle management, and notification channels
- Key entities and relationships: Monitored systems (web servers, databases, services, queues), alert rules, notification channels, escalation policies, and alerts
- Real-world use cases: Infrastructure monitoring, threshold-based alerting, anomaly detection, on-call escalation

## Prerequisites

- TesseraiDB account at [tesserai.io](https://tesserai.io)
- Set your API key: `export TESSERAI_API_KEY="your-api-key"`
- Python 3.10+ with the TesseraiDB SDK: `pip install tesserai`

## Quick Start

```bash
# Seed the example data
python seed.py

# (Optional) Start the web dashboard
python web_ui.py
```

## Digital Twins

List of main twin types created:

- **WebServer**: Web servers with metrics (CPU, memory, response time, error rate)
- **DatabaseServer**: Database instances with metrics (connections, queries/sec, replication lag)
- **ApplicationService**: Application services with latency and error tracking
- **MessageQueue**: Message queues with depth, consumer count, dead letters
- **AlertRule**: Configurable threshold rules with severity and duration
- **NotificationChannel**: Console, webhook, and log-based notification channels
- **EscalationPolicy**: Time-based escalation to different notification channels
- **Alert**: Active alerts with lifecycle (open, acknowledged, resolved)

## Ontology

The alerting system ontology defines:

- **System types**: WebServer, DatabaseServer, ApplicationService, MessageQueue
- **Rule configuration**: Metric thresholds, operators (gt, lt, eq), duration requirements
- **Alert lifecycle**: Status transitions, timestamps, severity levels
- **Notification routing**: Channel types, escalation stages

## Web Dashboard

The `web_ui.py` provides a real-time dashboard showing:

- System health overview with status indicators
- Active alerts grouped by severity
- RSP (RDF Stream Processing) query results for pattern detection
- Scenario injection buttons (spike, cascade, degradation, recovery)

Start the dashboard and open your browser to view real-time monitoring with continuous SPARQL queries.

## API Usage Examples

```python
from common import get_client

client = get_client()

# List all monitored systems
systems = client.twins.list(type_filter="WebServer")

# Get active critical alerts
alerts = client.sparql.query("""
    PREFIX alert: <http://tesserai.io/ontology/alerting_system#>
    SELECT ?alert ?source ?metric ?value WHERE {
        ?alert a alert:Alert .
        ?alert alert:status "open" .
        ?alert alert:severity "critical" .
        ?alert alert:sourceId ?source .
        ?alert alert:metric ?metric .
        ?alert alert:currentValue ?value .
    }
""")

# Update a system's metrics
client.twins.update("web-server-001", properties={
    "cpuUsage": 75.5,
    "memoryUsage": 82.0,
    "responseTimeMs": 250
})
```

## Additional Features

### Alert Rules

| Rule | Threshold | Duration | Severity |
|------|-----------|----------|----------|
| CPU Critical | > 90% | 60s | critical |
| CPU Warning | > 70% | 120s | warning |
| Memory Critical | > 95% | 60s | critical |
| Latency Critical | > 1000ms | 30s | critical |
| Error Rate | > 5% | 60s | warning |

### RSP Pattern Detection

The dashboard implements continuous SPARQL queries for detecting:

- **Cross-Tier Failure Correlation**: Frontend AND backend degraded simultaneously
- **Resource Exhaustion Sequence**: CPU spike followed by memory pressure followed by disk full
- **Incident Blast Radius**: Count of distinct affected systems

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
