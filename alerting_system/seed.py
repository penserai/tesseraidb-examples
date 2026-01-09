#!/usr/bin/env python3
"""
Real-Time Alerting System - Alert Configuration Seed
=====================================================

Creates a comprehensive alerting infrastructure with:
- Monitored systems (servers, databases, services)
- Alert rules with thresholds and conditions
- Notification channels and escalation policies
- Alert templates and severity classifications

Usage:
    python seed.py [--base-url URL]
"""

import sys
import os
import random
import argparse
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import (
    get_client, print_summary, logger,
    bulk_create_twins, bulk_add_relationships,
    DOMAIN_NAMESPACES
)

# Register new domain namespace
DOMAIN = "alerting_system"
ALERT_NS = "http://tesserai.io/ontology/alerting_system#"
DOMAIN_NAMESPACES[DOMAIN] = ALERT_NS

random.seed(42)


def prepare_alert_twin(data: dict) -> dict:
    """Prepare a twin dict for bulk creation in the alerting system domain."""
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{ALERT_NS}{twin_type}"
    data["domain"] = DOMAIN
    return data


def seed_alerting_system(base_url: Optional[str] = None):
    """Seed the alerting system digital twin network."""
    client = get_client(base_url)
    all_twins = []
    all_relationships = []

    print("\nSeeding Real-Time Alerting System")
    print("=" * 60)

    # =========================================================================
    # MONITORED SYSTEMS - Web Servers
    # =========================================================================
    web_servers = [
        {"id": "web-server-001", "name": "Web Server 1 (Primary)", "role": "primary", "az": "us-east-1a"},
        {"id": "web-server-002", "name": "Web Server 2 (Secondary)", "role": "secondary", "az": "us-east-1b"},
        {"id": "web-server-003", "name": "Web Server 3 (Backup)", "role": "backup", "az": "us-east-1c"},
    ]

    for server in web_servers:
        all_twins.append(prepare_alert_twin({
            "id": server["id"],
            "type": "WebServer",
            "name": server["name"],
            "properties": {
                "role": server["role"],
                "availabilityZone": server["az"],
                "cpuCores": 8,
                "memoryGB": 32,
                "status": "running",
                "cpuUsage": round(random.uniform(20, 60), 1),
                "memoryUsage": round(random.uniform(40, 70), 1),
                "diskUsage": round(random.uniform(30, 60), 1),
                "networkIn": round(random.uniform(100, 500), 1),
                "networkOut": round(random.uniform(50, 300), 1),
                "requestsPerSecond": random.randint(100, 1000),
                "responseTimeMs": round(random.uniform(50, 200), 1),
                "errorRate": round(random.uniform(0, 2), 2),
                "activeConnections": random.randint(50, 500),
                "lastHeartbeat": datetime.now().isoformat(),
            }
        }))

    # =========================================================================
    # MONITORED SYSTEMS - Database Servers
    # =========================================================================
    db_servers = [
        {"id": "db-primary", "name": "PostgreSQL Primary", "role": "primary", "engine": "postgresql"},
        {"id": "db-replica-1", "name": "PostgreSQL Replica 1", "role": "replica", "engine": "postgresql"},
        {"id": "db-replica-2", "name": "PostgreSQL Replica 2", "role": "replica", "engine": "postgresql"},
        {"id": "cache-redis-1", "name": "Redis Cache 1", "role": "primary", "engine": "redis"},
        {"id": "cache-redis-2", "name": "Redis Cache 2", "role": "replica", "engine": "redis"},
    ]

    for db in db_servers:
        all_twins.append(prepare_alert_twin({
            "id": db["id"],
            "type": "DatabaseServer",
            "name": db["name"],
            "properties": {
                "role": db["role"],
                "engine": db["engine"],
                "status": "running",
                "cpuUsage": round(random.uniform(10, 50), 1),
                "memoryUsage": round(random.uniform(50, 80), 1),
                "diskUsage": round(random.uniform(40, 70), 1),
                "connections": random.randint(10, 100),
                "maxConnections": 200,
                "queriesPerSecond": random.randint(100, 5000),
                "avgQueryTimeMs": round(random.uniform(1, 50), 2),
                "slowQueries": random.randint(0, 10),
                "replicationLagMs": random.randint(0, 100) if db["role"] == "replica" else 0,
                "cacheHitRate": round(random.uniform(0.85, 0.99), 3) if db["engine"] == "redis" else None,
                "lastHeartbeat": datetime.now().isoformat(),
            }
        }))

    # =========================================================================
    # MONITORED SYSTEMS - Application Services
    # =========================================================================
    services = [
        {"id": "svc-api", "name": "API Gateway", "type": "api_gateway", "critical": True},
        {"id": "svc-auth", "name": "Authentication Service", "type": "microservice", "critical": True},
        {"id": "svc-payment", "name": "Payment Service", "type": "microservice", "critical": True},
        {"id": "svc-notification", "name": "Notification Service", "type": "microservice", "critical": False},
        {"id": "svc-analytics", "name": "Analytics Service", "type": "microservice", "critical": False},
        {"id": "svc-search", "name": "Search Service", "type": "microservice", "critical": False},
    ]

    for svc in services:
        all_twins.append(prepare_alert_twin({
            "id": svc["id"],
            "type": "ApplicationService",
            "name": svc["name"],
            "properties": {
                "serviceType": svc["type"],
                "critical": svc["critical"],
                "status": "healthy",
                "instances": random.randint(2, 5),
                "healthyInstances": random.randint(2, 5),
                "requestsPerSecond": random.randint(50, 2000),
                "avgLatencyMs": round(random.uniform(10, 100), 1),
                "p99LatencyMs": round(random.uniform(100, 500), 1),
                "errorRate": round(random.uniform(0, 1), 2),
                "successRate": round(random.uniform(98, 100), 2),
                "cpuUsage": round(random.uniform(20, 60), 1),
                "memoryUsage": round(random.uniform(40, 70), 1),
                "lastHealthCheck": datetime.now().isoformat(),
            }
        }))

    # =========================================================================
    # MONITORED SYSTEMS - Message Queues
    # =========================================================================
    queues = [
        {"id": "queue-orders", "name": "Orders Queue", "type": "rabbitmq"},
        {"id": "queue-events", "name": "Events Queue", "type": "kafka"},
        {"id": "queue-notifications", "name": "Notifications Queue", "type": "rabbitmq"},
    ]

    for queue in queues:
        all_twins.append(prepare_alert_twin({
            "id": queue["id"],
            "type": "MessageQueue",
            "name": queue["name"],
            "properties": {
                "queueType": queue["type"],
                "status": "running",
                "messageCount": random.randint(0, 10000),
                "consumerCount": random.randint(1, 10),
                "publishRate": random.randint(100, 1000),
                "consumeRate": random.randint(100, 1000),
                "oldestMessageAge": random.randint(0, 300),
                "deadLetterCount": random.randint(0, 50),
                "lastHeartbeat": datetime.now().isoformat(),
            }
        }))

    # =========================================================================
    # ALERT RULES - CPU
    # =========================================================================
    cpu_rules = [
        {"id": "rule-cpu-warning", "threshold": 70, "severity": "warning", "duration": 300},
        {"id": "rule-cpu-critical", "threshold": 90, "severity": "critical", "duration": 120},
    ]

    for rule in cpu_rules:
        all_twins.append(prepare_alert_twin({
            "id": rule["id"],
            "type": "AlertRule",
            "name": f"CPU Usage {rule['severity'].title()}",
            "properties": {
                "metric": "cpuUsage",
                "condition": "greater_than",
                "threshold": rule["threshold"],
                "unit": "percent",
                "severity": rule["severity"],
                "duration": rule["duration"],
                "durationUnit": "seconds",
                "enabled": True,
                "notificationChannels": ["channel-pagerduty", "channel-slack"],
                "description": f"CPU usage exceeds {rule['threshold']}% for {rule['duration']}s",
                "runbook": "https://wiki.example.com/runbooks/high-cpu",
            }
        }))

    # =========================================================================
    # ALERT RULES - Memory
    # =========================================================================
    memory_rules = [
        {"id": "rule-memory-warning", "threshold": 75, "severity": "warning", "duration": 300},
        {"id": "rule-memory-critical", "threshold": 90, "severity": "critical", "duration": 60},
    ]

    for rule in memory_rules:
        all_twins.append(prepare_alert_twin({
            "id": rule["id"],
            "type": "AlertRule",
            "name": f"Memory Usage {rule['severity'].title()}",
            "properties": {
                "metric": "memoryUsage",
                "condition": "greater_than",
                "threshold": rule["threshold"],
                "unit": "percent",
                "severity": rule["severity"],
                "duration": rule["duration"],
                "durationUnit": "seconds",
                "enabled": True,
                "notificationChannels": ["channel-slack"],
                "description": f"Memory usage exceeds {rule['threshold']}%",
            }
        }))

    # =========================================================================
    # ALERT RULES - Disk
    # =========================================================================
    disk_rules = [
        {"id": "rule-disk-warning", "threshold": 80, "severity": "warning"},
        {"id": "rule-disk-critical", "threshold": 95, "severity": "critical"},
    ]

    for rule in disk_rules:
        all_twins.append(prepare_alert_twin({
            "id": rule["id"],
            "type": "AlertRule",
            "name": f"Disk Usage {rule['severity'].title()}",
            "properties": {
                "metric": "diskUsage",
                "condition": "greater_than",
                "threshold": rule["threshold"],
                "unit": "percent",
                "severity": rule["severity"],
                "duration": 0,
                "enabled": True,
                "notificationChannels": ["channel-pagerduty"],
            }
        }))

    # =========================================================================
    # ALERT RULES - Response Time
    # =========================================================================
    latency_rules = [
        {"id": "rule-latency-warning", "threshold": 500, "severity": "warning"},
        {"id": "rule-latency-critical", "threshold": 2000, "severity": "critical"},
    ]

    for rule in latency_rules:
        all_twins.append(prepare_alert_twin({
            "id": rule["id"],
            "type": "AlertRule",
            "name": f"Response Time {rule['severity'].title()}",
            "properties": {
                "metric": "responseTimeMs",
                "condition": "greater_than",
                "threshold": rule["threshold"],
                "unit": "ms",
                "severity": rule["severity"],
                "duration": 60,
                "enabled": True,
                "notificationChannels": ["channel-slack", "channel-pagerduty"],
            }
        }))

    # =========================================================================
    # ALERT RULES - Error Rate
    # =========================================================================
    error_rules = [
        {"id": "rule-error-warning", "threshold": 1, "severity": "warning"},
        {"id": "rule-error-critical", "threshold": 5, "severity": "critical"},
    ]

    for rule in error_rules:
        all_twins.append(prepare_alert_twin({
            "id": rule["id"],
            "type": "AlertRule",
            "name": f"Error Rate {rule['severity'].title()}",
            "properties": {
                "metric": "errorRate",
                "condition": "greater_than",
                "threshold": rule["threshold"],
                "unit": "percent",
                "severity": rule["severity"],
                "duration": 120,
                "enabled": True,
                "notificationChannels": ["channel-pagerduty", "channel-slack", "channel-email"],
            }
        }))

    # =========================================================================
    # ALERT RULES - Database-specific
    # =========================================================================
    db_rules = [
        {"id": "rule-db-connections-warning", "metric": "connections", "threshold": 150, "severity": "warning"},
        {"id": "rule-db-connections-critical", "metric": "connections", "threshold": 190, "severity": "critical"},
        {"id": "rule-db-slow-queries", "metric": "slowQueries", "threshold": 10, "severity": "warning"},
        {"id": "rule-db-replication-lag", "metric": "replicationLagMs", "threshold": 1000, "severity": "critical"},
    ]

    for rule in db_rules:
        all_twins.append(prepare_alert_twin({
            "id": rule["id"],
            "type": "AlertRule",
            "name": f"Database {rule['metric'].replace('_', ' ').title()}",
            "properties": {
                "metric": rule["metric"],
                "condition": "greater_than",
                "threshold": rule["threshold"],
                "severity": rule["severity"],
                "duration": 60,
                "enabled": True,
                "targetType": "DatabaseServer",
                "notificationChannels": ["channel-pagerduty"],
            }
        }))

    # =========================================================================
    # ALERT RULES - Queue
    # =========================================================================
    queue_rules = [
        {"id": "rule-queue-depth-warning", "metric": "messageCount", "threshold": 10000, "severity": "warning"},
        {"id": "rule-queue-depth-critical", "metric": "messageCount", "threshold": 50000, "severity": "critical"},
        {"id": "rule-queue-age-warning", "metric": "oldestMessageAge", "threshold": 300, "severity": "warning"},
        {"id": "rule-dead-letter", "metric": "deadLetterCount", "threshold": 100, "severity": "critical"},
    ]

    for rule in queue_rules:
        all_twins.append(prepare_alert_twin({
            "id": rule["id"],
            "type": "AlertRule",
            "name": f"Queue {rule['metric'].replace('_', ' ').title()}",
            "properties": {
                "metric": rule["metric"],
                "condition": "greater_than",
                "threshold": rule["threshold"],
                "severity": rule["severity"],
                "duration": 60,
                "enabled": True,
                "targetType": "MessageQueue",
                "notificationChannels": ["channel-slack"],
            }
        }))

    # =========================================================================
    # ALERT RULES - Service Health
    # =========================================================================
    service_rules = [
        {"id": "rule-service-down", "metric": "healthyInstances", "condition": "equals", "threshold": 0, "severity": "critical"},
        {"id": "rule-service-degraded", "metric": "successRate", "condition": "less_than", "threshold": 99, "severity": "warning"},
        {"id": "rule-service-failing", "metric": "successRate", "condition": "less_than", "threshold": 95, "severity": "critical"},
    ]

    for rule in service_rules:
        all_twins.append(prepare_alert_twin({
            "id": rule["id"],
            "type": "AlertRule",
            "name": f"Service {rule['metric'].replace('_', ' ').title()}",
            "properties": {
                "metric": rule["metric"],
                "condition": rule["condition"],
                "threshold": rule["threshold"],
                "severity": rule["severity"],
                "duration": 30,
                "enabled": True,
                "targetType": "ApplicationService",
                "notificationChannels": ["channel-pagerduty", "channel-slack"],
            }
        }))

    # =========================================================================
    # NOTIFICATION CHANNELS
    # =========================================================================
    channels = [
        {
            "id": "channel-pagerduty",
            "name": "PagerDuty",
            "type": "pagerduty",
            "config": {
                "serviceKey": "xxx-pagerduty-key-xxx",
                "severity_mapping": {
                    "critical": "critical",
                    "warning": "warning",
                    "info": "info"
                }
            }
        },
        {
            "id": "channel-slack",
            "name": "Slack #alerts",
            "type": "slack",
            "config": {
                "webhookUrl": "https://hooks.slack.com/services/xxx/yyy/zzz",
                "channel": "#alerts",
                "username": "AlertBot",
                "icon_emoji": ":warning:"
            }
        },
        {
            "id": "channel-email",
            "name": "Email - Ops Team",
            "type": "email",
            "config": {
                "recipients": ["ops@example.com", "oncall@example.com"],
                "from": "alerts@example.com",
                "subject_prefix": "[ALERT]"
            }
        },
        {
            "id": "channel-webhook",
            "name": "Custom Webhook",
            "type": "webhook",
            "config": {
                "url": "https://api.example.com/alerts",
                "method": "POST",
                "headers": {"Authorization": "Bearer xxx"}
            }
        },
        {
            "id": "channel-console",
            "name": "Console Output",
            "type": "console",
            "config": {
                "format": "detailed",
                "colorize": True
            }
        },
    ]

    for channel in channels:
        all_twins.append(prepare_alert_twin({
            "id": channel["id"],
            "type": "NotificationChannel",
            "name": channel["name"],
            "properties": {
                "channelType": channel["type"],
                "enabled": True,
                "config": channel["config"],
                "rateLimitPerHour": 100,
                "lastNotification": None,
                "notificationCount": 0,
            }
        }))

    # =========================================================================
    # ESCALATION POLICIES
    # =========================================================================
    policies = [
        {
            "id": "policy-critical",
            "name": "Critical Escalation",
            "severity": "critical",
            "steps": [
                {"delay": 0, "channels": ["channel-pagerduty", "channel-slack"]},
                {"delay": 300, "channels": ["channel-email"]},
                {"delay": 900, "action": "escalate_to_manager"},
            ]
        },
        {
            "id": "policy-warning",
            "name": "Warning Escalation",
            "severity": "warning",
            "steps": [
                {"delay": 0, "channels": ["channel-slack"]},
                {"delay": 600, "channels": ["channel-email"]},
                {"delay": 1800, "channels": ["channel-pagerduty"]},
            ]
        },
        {
            "id": "policy-info",
            "name": "Info Notification",
            "severity": "info",
            "steps": [
                {"delay": 0, "channels": ["channel-slack"]},
            ]
        },
    ]

    for policy in policies:
        all_twins.append(prepare_alert_twin({
            "id": policy["id"],
            "type": "EscalationPolicy",
            "name": policy["name"],
            "properties": {
                "severity": policy["severity"],
                "steps": policy["steps"],
                "enabled": True,
                "repeatInterval": 3600,
                "maxRepeats": 3,
            }
        }))

    # =========================================================================
    # SAMPLE ALERTS (Historical)
    # =========================================================================
    sample_alerts = [
        {
            "id": "alert-001",
            "rule": "rule-cpu-warning",
            "source": "web-server-001",
            "status": "resolved",
            "severity": "warning",
            "triggered": -120,
            "resolved": -90,
        },
        {
            "id": "alert-002",
            "rule": "rule-memory-critical",
            "source": "db-primary",
            "status": "resolved",
            "severity": "critical",
            "triggered": -60,
            "resolved": -30,
        },
        {
            "id": "alert-003",
            "rule": "rule-latency-warning",
            "source": "svc-api",
            "status": "acknowledged",
            "severity": "warning",
            "triggered": -15,
            "acknowledged": -5,
        },
        {
            "id": "alert-004",
            "rule": "rule-queue-depth-warning",
            "source": "queue-orders",
            "status": "open",
            "severity": "warning",
            "triggered": -5,
        },
    ]

    for alert in sample_alerts:
        triggered_at = datetime.now() + timedelta(minutes=alert["triggered"])
        resolved_at = datetime.now() + timedelta(minutes=alert.get("resolved", 0)) if alert.get("resolved") else None
        ack_at = datetime.now() + timedelta(minutes=alert.get("acknowledged", 0)) if alert.get("acknowledged") else None

        all_twins.append(prepare_alert_twin({
            "id": alert["id"],
            "type": "Alert",
            "name": f"Alert from {alert['source']}",
            "properties": {
                "ruleId": alert["rule"],
                "sourceId": alert["source"],
                "status": alert["status"],
                "severity": alert["severity"],
                "triggeredAt": triggered_at.isoformat(),
                "resolvedAt": resolved_at.isoformat() if resolved_at else None,
                "acknowledgedAt": ack_at.isoformat() if ack_at else None,
                "acknowledgedBy": "oncall@example.com" if ack_at else None,
                "notificationCount": random.randint(1, 5),
                "escalationLevel": 0 if alert["status"] == "resolved" else random.randint(0, 2),
            }
        }))

        # Link alert to rule and source
        all_relationships.append((alert["id"], "triggeredBy", alert["rule"], None))
        all_relationships.append((alert["id"], "affectsSystem", alert["source"], None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, _ = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships via bulk API...")
    relationships_created, _ = bulk_add_relationships(client, all_relationships)

    print_summary("Real-Time Alerting System", twins_created, relationships_created)
    logger.info("Alerting System digital twin network seeded successfully!")

    return {"twins_created": twins_created, "relationships_created": relationships_created}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Alerting System data")
    parser.add_argument("--base-url", help="DTaaS server URL")
    args = parser.parse_args()

    seed_alerting_system(args.base_url)
