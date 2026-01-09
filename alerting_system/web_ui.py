#!/usr/bin/env python3
"""
Real-Time Alerting System - Web Dashboard
==========================================

A standalone web-based dashboard for monitoring and managing alerts with:
- Real-time system health monitoring with gauges
- Active alerts display with severity indicators
- Alert rule management
- Scenario injection (spike, degradation, cascade, recovery)
- Notification channel status
- RSP (RDF Stream Processing) continuous queries
- Metric trends visualization

Usage:
    python web_ui.py [--base-url URL] [--port PORT]
"""

import sys
import os
import json
import asyncio
import argparse
import random
import math
import textwrap
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field
from enum import Enum
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import websockets
from websockets.server import serve

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'sdks', 'python'))

from common import get_client, logger

# RSP imports
try:
    from dtaas.models import (
        WindowConfig,
        WindowType,
        OutputConfig,
        ContinuousQueryCreate,
    )
    RSP_AVAILABLE = True
except ImportError:
    RSP_AVAILABLE = False
    logger.warning("RSP models not available - RSP features will be disabled")


# RSP Configuration for alerting system
RSP_STREAM_CONFIG = {
    "type": "event_bus",
    "twin_id_patterns": ["*"],
    "event_types": ["twin.updated", "twin.property_changed"],
}

RSP_CONTINUOUS_QUERIES = [
    # ==========================================================================
    # Pattern 1: Resource Exhaustion Sequence (Temporal)
    # Detects: High CPU (T1) -> High Memory (T2) -> High Disk (T3)
    # Sequence detection via SPARQL timestamp comparison (not native CEP)
    # T1 < T2 < T3 ordering enforced by comparing ISO 8601 strings
    # ==========================================================================
    {
        "name": "Resource Exhaustion Sequence",
        "description": "CPU spike -> Memory pressure -> Disk full (in sequence)",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/alerting_system#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?system ?cpuTime ?memTime ?diskTime
            WHERE {
                ?system dto:highCpuEvent ?cpuTime .
                ?system dto:highMemoryEvent ?memTime .
                ?system dto:highDiskEvent ?diskTime .
                FILTER(
                    BOUND(?cpuTime) && ?cpuTime != "" &&
                    BOUND(?memTime) && ?memTime != "" &&
                    BOUND(?diskTime) && ?diskTime != "" &&
                    STR(?cpuTime) < STR(?memTime) &&
                    STR(?memTime) < STR(?diskTime)
                )
            }
        """,
        "window_duration": 300,
        "window_slide": 30,
        "severity": "critical",
        "icon": "🔥",
    },
    # ==========================================================================
    # Pattern 2: Performance Degradation Sequence (Temporal)
    # Detects: Slow Response (T1) -> High Latency (T2) -> Errors (T3)
    # Classic cascading failure pattern via timestamp comparison
    # ==========================================================================
    {
        "name": "Performance Degradation Sequence",
        "description": "Slow response -> High latency -> Errors (in sequence)",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/alerting_system#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?system ?slowTime ?latencyTime ?errorTime
            WHERE {
                ?system dto:slowResponseEvent ?slowTime .
                ?system dto:highLatencyEvent ?latencyTime .
                ?system dto:highErrorEvent ?errorTime .
                FILTER(
                    BOUND(?slowTime) && ?slowTime != "" &&
                    BOUND(?latencyTime) && ?latencyTime != "" &&
                    BOUND(?errorTime) && ?errorTime != "" &&
                    STR(?slowTime) < STR(?latencyTime) &&
                    STR(?latencyTime) < STR(?errorTime)
                )
            }
        """,
        "window_duration": 300,
        "window_slide": 30,
        "severity": "critical",
        "icon": "⚡",
    },
    # ==========================================================================
    # Pattern 3: Queue Pressure Sequence (Temporal)
    # Detects: Queue Backlog (T1) -> Stale Messages (T2) -> DLQ Growth (T3)
    # Message processing degradation via timestamp comparison
    # ==========================================================================
    {
        "name": "Queue Pressure Sequence",
        "description": "Queue backlog -> Stale messages -> DLQ growth (in sequence)",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/alerting_system#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?queue ?backlogTime ?staleTime ?dlqTime
            WHERE {
                ?queue dto:queueBacklogEvent ?backlogTime .
                ?queue dto:staleMessagesEvent ?staleTime .
                ?queue dto:dlqGrowthEvent ?dlqTime .
                FILTER(
                    BOUND(?backlogTime) && ?backlogTime != "" &&
                    BOUND(?staleTime) && ?staleTime != "" &&
                    BOUND(?dlqTime) && ?dlqTime != "" &&
                    STR(?backlogTime) < STR(?staleTime) &&
                    STR(?staleTime) < STR(?dlqTime)
                )
            }
        """,
        "window_duration": 300,
        "window_slide": 30,
        "severity": "critical",
        "icon": "📬",
    },
    # ==========================================================================
    # Pattern 4: Cross-Tier Failure Correlation (Concurrent)
    # Detects when BOTH web servers AND databases show stress simultaneously
    # This indicates a systemic issue rather than isolated component failure
    # ==========================================================================
    {
        "name": "Cross-Tier Failure Correlation",
        "description": "Frontend AND backend tiers both degraded (concurrent)",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/alerting_system#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?frontendCount ?backendCount
            WHERE {
                {
                    SELECT (COUNT(DISTINCT ?frontend) AS ?frontendCount)
                    WHERE {
                        ?frontend dto:cpuUsage ?cpu .
                        FILTER(CONTAINS(STR(?frontend), "web-server"))
                        FILTER(xsd:double(?cpu) > 50.0)
                    }
                }
                {
                    SELECT (COUNT(DISTINCT ?backend) AS ?backendCount)
                    WHERE {
                        ?backend dto:cpuUsage ?cpu .
                        FILTER(CONTAINS(STR(?backend), "db-"))
                        FILTER(xsd:double(?cpu) > 40.0)
                    }
                }
                FILTER(?frontendCount >= 1 && ?backendCount >= 1)
            }
        """,
        "window_duration": 90,
        "window_slide": 30,
        "severity": "critical",
        "icon": "🔗",
    },
    # ==========================================================================
    # Pattern 5: Incident Blast Radius (Concurrent)
    # Counts DISTINCT affected systems to measure incident scope
    # High count = wide blast radius = major incident
    # ==========================================================================
    {
        "name": "Incident Blast Radius",
        "description": "Count of distinct systems showing any failure symptom",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/alerting_system#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT (COUNT(DISTINCT ?system) AS ?affectedSystems)
            WHERE {
                ?system ?metric ?value .
                FILTER(
                    (?metric = dto:cpuUsage && xsd:double(?value) > 70.0) ||
                    (?metric = dto:memoryUsage && xsd:double(?value) > 75.0) ||
                    (?metric = dto:errorRate && xsd:double(?value) > 1.0) ||
                    (?metric = dto:responseTimeMs && xsd:double(?value) > 300.0)
                )
            }
            HAVING (COUNT(DISTINCT ?system) >= 3)
        """,
        "window_duration": 60,
        "window_slide": 20,
        "severity": "critical",
        "icon": "💥",
    },
    # ==========================================================================
    # Pattern 6: CPU-Memory Cascade (Temporal, 2-event)
    # Detects: High CPU (T1) -> High Memory (T2) on same system
    # Simpler sequence pattern via timestamp comparison
    # ==========================================================================
    {
        "name": "CPU-Memory Cascade",
        "description": "CPU spike -> Memory pressure (2-event sequence)",
        "sparql": """
            PREFIX dto: <http://tesserai.io/ontology/alerting_system#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

            SELECT ?system ?cpuTime ?memTime
            WHERE {
                ?system dto:highCpuEvent ?cpuTime .
                ?system dto:highMemoryEvent ?memTime .
                FILTER(
                    BOUND(?cpuTime) && ?cpuTime != "" &&
                    BOUND(?memTime) && ?memTime != "" &&
                    STR(?cpuTime) < STR(?memTime)
                )
            }
        """,
        "window_duration": 180,
        "window_slide": 30,
        "severity": "warning",
        "icon": "📈",
    },
]


class AnomalyType(Enum):
    NONE = "none"
    SPIKE = "spike"
    DEGRADATION = "degradation"
    OUTAGE = "outage"


@dataclass
class MetricSimulator:
    """Simulator for a single metric."""
    base_value: float
    noise_std: float
    min_value: float = 0
    max_value: float = 100


@dataclass
class SystemState:
    """State of a monitored system."""
    id: str
    name: str
    type: str
    properties: Dict
    anomaly_type: AnomalyType = AnomalyType.NONE
    anomaly_start: Optional[datetime] = None
    anomaly_duration: int = 0
    simulators: Dict[str, MetricSimulator] = field(default_factory=dict)
    tick_count: int = 0


class AlertingDashboard:
    """
    Web-based alerting dashboard with real-time updates.
    """

    def __init__(self, client, http_port: int = 8085, ws_port: int = 8086):
        self.client = client
        self.http_port = http_port
        self.ws_port = ws_port

        self.systems: Dict[str, SystemState] = {}
        self.alerts: Dict[str, Dict] = {}
        self.rules: Dict[str, Dict] = {}
        self.channels: Dict[str, Dict] = {}
        self.policies: Dict[str, Dict] = {}

        self.connected_clients: Set = set()
        self.running = False
        self.start_time = datetime.now()

        # Alert history for notifications
        self.alert_history: List[Dict] = []

        # RSP state
        self.rsp_enabled = False
        self.rsp_query_ids: List[str] = []
        self.rsp_source_ids: List[str] = []
        self.rsp_alerts: List[Dict] = []

    def _normalize_properties(self, properties: dict) -> dict:
        """Normalize property names by stripping domain prefixes."""
        normalized = {}
        for key, value in properties.items():
            if '#' in key:
                short_key = key.split('#', 1)[1]
            else:
                short_key = key
            normalized[short_key] = value
        return normalized

    def load_data(self):
        """Load all data from DTaaS."""
        try:
            twins = self.client.twins.list(domain="alerting_system", page_size=200)

            self.systems = {}
            self.rules = {}
            self.channels = {}
            self.policies = {}

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                twin_type = type_val.split("#")[-1] if type_val else ""
                twin_id = twin_dict["id"]
                raw_props = twin_dict.get("properties", {})
                props = self._normalize_properties(raw_props)

                if twin_type in ["WebServer", "DatabaseServer", "ApplicationService", "MessageQueue"]:
                    state = SystemState(
                        id=twin_id,
                        name=twin_dict.get("name", twin_id),
                        type=twin_type,
                        properties=props
                    )
                    self._setup_simulators(state)
                    self.systems[twin_id] = state

                elif twin_type == "Alert":
                    status = props.get("status", "")
                    if status in ["open", "acknowledged"]:
                        self.alerts[twin_id] = {
                            "id": twin_id,
                            "rule": props.get("ruleId", ""),
                            "source": props.get("sourceId", ""),
                            "severity": props.get("severity", "warning"),
                            "status": status,
                            "triggeredAt": props.get("triggeredAt", datetime.now().isoformat()),
                            "metric": props.get("metric", ""),
                            "value": props.get("currentValue", 0),
                            "threshold": props.get("threshold", 0),
                        }

                elif twin_type == "AlertRule":
                    self.rules[twin_id] = {
                        "id": twin_id,
                        "name": twin_dict.get("name", twin_id),
                        "metric": props.get("metric", ""),
                        "condition": props.get("condition", "greater_than"),
                        "threshold": props.get("threshold", 0),
                        "severity": props.get("severity", "warning"),
                        "enabled": props.get("enabled", True),
                        "duration": props.get("duration", 0),
                        "targetType": props.get("targetType", ""),
                    }

                elif twin_type == "NotificationChannel":
                    self.channels[twin_id] = {
                        "id": twin_id,
                        "name": twin_dict.get("name", twin_id),
                        "type": props.get("channelType", ""),
                        "enabled": props.get("enabled", True),
                        "notificationCount": props.get("notificationCount", 0),
                    }

                elif twin_type == "EscalationPolicy":
                    self.policies[twin_id] = {
                        "id": twin_id,
                        "name": twin_dict.get("name", twin_id),
                        "severity": props.get("severity", ""),
                        "enabled": props.get("enabled", True),
                    }

            logger.info(f"Loaded {len(self.systems)} systems, {len(self.rules)} rules, "
                       f"{len(self.channels)} channels, {len(self.alerts)} active alerts")

        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise

    def _setup_simulators(self, state: SystemState):
        """Configure metric simulators based on system type."""
        if state.type == "WebServer":
            state.simulators = {
                "cpuUsage": MetricSimulator(40, 8, 0, 100),
                "memoryUsage": MetricSimulator(55, 5, 0, 100),
                "diskUsage": MetricSimulator(45, 2, 0, 100),
                "requestsPerSecond": MetricSimulator(500, 100, 0, 5000),
                "responseTimeMs": MetricSimulator(100, 30, 10, 5000),
                "errorRate": MetricSimulator(0.5, 0.3, 0, 100),
            }
        elif state.type == "DatabaseServer":
            state.simulators = {
                "cpuUsage": MetricSimulator(30, 10, 0, 100),
                "memoryUsage": MetricSimulator(60, 8, 0, 100),
                "diskUsage": MetricSimulator(50, 3, 0, 100),
                "connections": MetricSimulator(50, 20, 0, 200),
                "queriesPerSecond": MetricSimulator(1000, 300, 0, 10000),
                "avgQueryTimeMs": MetricSimulator(10, 5, 0.1, 1000),
                "replicationLagMs": MetricSimulator(10, 15, 0, 10000),
            }
        elif state.type == "ApplicationService":
            state.simulators = {
                "cpuUsage": MetricSimulator(35, 12, 0, 100),
                "memoryUsage": MetricSimulator(50, 8, 0, 100),
                "requestsPerSecond": MetricSimulator(300, 80, 0, 5000),
                "avgLatencyMs": MetricSimulator(50, 15, 1, 5000),
                "errorRate": MetricSimulator(0.3, 0.2, 0, 100),
                "successRate": MetricSimulator(99.5, 0.3, 0, 100),
            }
        elif state.type == "MessageQueue":
            state.simulators = {
                "messageCount": MetricSimulator(5000, 2000, 0, 100000),
                "publishRate": MetricSimulator(500, 150, 0, 5000),
                "consumeRate": MetricSimulator(480, 150, 0, 5000),
                "oldestMessageAge": MetricSimulator(30, 20, 0, 3600),
                "deadLetterCount": MetricSimulator(10, 10, 0, 1000),
            }

    def simulate_tick(self):
        """Simulate one tick for all systems."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        for sys_id, state in self.systems.items():
            state.tick_count += 1
            new_values = {}

            for metric_name, sim in state.simulators.items():
                # Base value with noise
                value = sim.base_value + random.gauss(0, sim.noise_std)

                # Add seasonality
                phase = (elapsed % 3600) / 3600
                value += sim.noise_std * math.sin(2 * math.pi * phase)

                # Apply anomaly effects
                value = self._apply_anomaly(state, metric_name, value)

                # Clamp to valid range
                value = max(sim.min_value, min(sim.max_value, value))
                new_values[metric_name] = round(value, 2)

            # Apply correlations
            new_values = self._apply_correlations(new_values)

            # Update state
            state.properties.update(new_values)
            state.properties["lastHeartbeat"] = datetime.now().isoformat()

            # CEP Event Detection: Track threshold crossings with timestamps
            # This enables sequence detection (Event A -> Event B -> Event C)
            event_updates = self._track_threshold_events(state, new_values)
            new_values.update(event_updates)

            # Update in DTaaS
            try:
                self.client.twins.update(sys_id, {"properties": new_values})
            except Exception as e:
                logger.warning(f"Failed to update {sys_id}: {e}")

        # Check alert rules
        self._check_alert_rules()

    def _apply_anomaly(self, state: SystemState, metric_name: str, value: float) -> float:
        """Apply anomaly effects to a metric value."""
        if state.anomaly_type == AnomalyType.NONE:
            return value

        anomaly_age = 0
        if state.anomaly_start:
            anomaly_age = (datetime.now() - state.anomaly_start).total_seconds()

        if anomaly_age > state.anomaly_duration:
            state.anomaly_type = AnomalyType.NONE
            return value

        if state.anomaly_type == AnomalyType.SPIKE:
            if metric_name in ["cpuUsage", "memoryUsage", "responseTimeMs", "avgLatencyMs"]:
                return value * (1.5 + random.uniform(0, 0.5))

        elif state.anomaly_type == AnomalyType.DEGRADATION:
            progress = anomaly_age / state.anomaly_duration
            if metric_name in ["cpuUsage", "memoryUsage"]:
                return value * (1 + 0.5 * progress)
            elif metric_name == "errorRate":
                return value * (1 + 3 * progress)
            elif metric_name in ["responseTimeMs", "avgLatencyMs"]:
                return value * (1 + 2 * progress)

        elif state.anomaly_type == AnomalyType.OUTAGE:
            if metric_name in ["requestsPerSecond", "queriesPerSecond"]:
                return 0
            elif metric_name == "errorRate":
                return 100
            elif metric_name == "successRate":
                return 0

        return value

    def _apply_correlations(self, values: Dict[str, float]) -> Dict[str, float]:
        """Apply realistic correlations between metrics."""
        if "cpuUsage" in values and "responseTimeMs" in values:
            if values["cpuUsage"] > 70:
                factor = 1 + (values["cpuUsage"] - 70) / 30
                values["responseTimeMs"] *= factor

        if "responseTimeMs" in values and "errorRate" in values:
            if values["responseTimeMs"] > 500:
                values["errorRate"] += (values["responseTimeMs"] - 500) / 100

        if "errorRate" in values and "successRate" in values:
            values["successRate"] = max(0, 100 - values["errorRate"])

        return values

    def _track_threshold_events(self, state: SystemState, values: Dict[str, float]) -> Dict[str, str]:
        """
        Track threshold crossing events with timestamps for CEP sequence detection.

        When a metric crosses a threshold, we record the timestamp. This enables
        SPARQL queries to detect temporal sequences like:
        "CPU high (T1) -> Memory high (T2) -> Disk full (T3)" where T1 < T2 < T3

        Events are cleared when conditions normalize, allowing new sequences to be detected.
        """
        # Initialize event tracking state if not present
        if not hasattr(state, 'active_events'):
            state.active_events = {}

        event_updates = {}
        now = datetime.now().isoformat()

        # Define CEP event thresholds
        # Format: (metric_name, threshold, comparison, event_name, clear_threshold)
        cep_thresholds = [
            # Resource exhaustion sequence
            ("cpuUsage", 70.0, "gt", "highCpuEvent", 60.0),
            ("memoryUsage", 75.0, "gt", "highMemoryEvent", 65.0),
            ("diskUsage", 85.0, "gt", "highDiskEvent", 75.0),

            # Performance degradation sequence
            ("responseTimeMs", 500.0, "gt", "slowResponseEvent", 300.0),
            ("avgLatencyMs", 200.0, "gt", "highLatencyEvent", 100.0),
            ("errorRate", 2.0, "gt", "highErrorEvent", 1.0),

            # Queue pressure sequence
            ("messageCount", 10000.0, "gt", "queueBacklogEvent", 5000.0),
            ("oldestMessageAge", 300.0, "gt", "staleMessagesEvent", 120.0),
            ("deadLetterCount", 50.0, "gt", "dlqGrowthEvent", 20.0),

            # Database stress sequence
            ("connections", 150.0, "gt", "highConnectionsEvent", 100.0),
            ("replicationLagMs", 1000.0, "gt", "replicationLagEvent", 500.0),
            ("avgQueryTimeMs", 100.0, "gt", "slowQueriesEvent", 50.0),
        ]

        for metric, threshold, comparison, event_name, clear_threshold in cep_thresholds:
            if metric not in values:
                continue

            value = values[metric]
            is_crossed = value > threshold if comparison == "gt" else value < threshold
            is_cleared = value < clear_threshold if comparison == "gt" else value > clear_threshold

            if is_crossed and event_name not in state.active_events:
                # Threshold just crossed - record timestamp
                state.active_events[event_name] = now
                event_updates[event_name] = now
            elif is_cleared and event_name in state.active_events:
                # Condition normalized - clear the event
                del state.active_events[event_name]
                event_updates[event_name] = ""  # Empty string clears the property
            elif event_name in state.active_events:
                # Event still active - keep the original timestamp
                event_updates[event_name] = state.active_events[event_name]

        return event_updates

    def _check_alert_rules(self):
        """Check alert rules and create/update alerts."""
        new_alerts = []

        for rule_id, rule in self.rules.items():
            if not rule.get("enabled", True):
                continue

            metric = rule.get("metric", "")
            threshold = rule.get("threshold", 0)
            condition = rule.get("condition", "greater_than")
            severity = rule.get("severity", "warning")
            target_type = rule.get("targetType", "")

            for sys_id, state in self.systems.items():
                # Check if rule applies to this system type
                if target_type and state.type != target_type:
                    continue

                value = state.properties.get(metric)
                if value is None:
                    continue

                triggered = False
                if condition == "greater_than" and value > threshold:
                    triggered = True
                elif condition == "less_than" and value < threshold:
                    triggered = True
                elif condition == "equals" and value == threshold:
                    triggered = True

                alert_key = f"{rule_id}:{sys_id}"

                if triggered:
                    if alert_key not in self.alerts:
                        # Create new alert
                        alert = {
                            "id": f"alert-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(self.alerts)}",
                            "rule": rule_id,
                            "source": sys_id,
                            "severity": severity,
                            "status": "open",
                            "triggeredAt": datetime.now().isoformat(),
                            "metric": metric,
                            "value": value,
                            "threshold": threshold,
                        }
                        self.alerts[alert_key] = alert
                        new_alerts.append(alert)
                else:
                    # Resolve alert if it exists
                    if alert_key in self.alerts:
                        del self.alerts[alert_key]

        return new_alerts

    def inject_scenario(self, scenario: str) -> Dict:
        """Inject a predefined scenario."""
        affected = []

        if scenario == "spike":
            for sys_id, state in self.systems.items():
                if state.type == "WebServer":
                    state.anomaly_type = AnomalyType.SPIKE
                    state.anomaly_start = datetime.now()
                    state.anomaly_duration = 60
                    affected.append(sys_id)

        elif scenario == "degradation":
            for sys_id, state in self.systems.items():
                if state.type == "DatabaseServer":
                    state.anomaly_type = AnomalyType.DEGRADATION
                    state.anomaly_start = datetime.now()
                    state.anomaly_duration = 180
                    affected.append(sys_id)

        elif scenario == "cascade":
            # Database outage first
            for sys_id, state in self.systems.items():
                if "db-primary" in sys_id:
                    state.anomaly_type = AnomalyType.OUTAGE
                    state.anomaly_start = datetime.now()
                    state.anomaly_duration = 120
                    affected.append(sys_id)
                    break

            # Services degrade
            for sys_id, state in self.systems.items():
                if state.type == "ApplicationService":
                    state.anomaly_type = AnomalyType.DEGRADATION
                    state.anomaly_start = datetime.now()
                    state.anomaly_duration = 90
                    affected.append(sys_id)

        elif scenario == "recovery":
            for state in self.systems.values():
                state.anomaly_type = AnomalyType.NONE
                affected.append(state.id)
            self.alerts.clear()

        return {"scenario": scenario, "affected": affected}

    def setup_rsp(self) -> bool:
        """Initialize RSP stream sources and continuous queries."""
        if not RSP_AVAILABLE:
            logger.warning("RSP models not available")
            return False

        try:
            stats = self.client.rsp.get_stats()
            logger.info(f"RSP service available: {stats.total_queries} queries")
        except Exception as e:
            logger.warning(f"RSP service not available: {e}")
            return False

        # Create stream source
        try:
            source = self.client.rsp.create_source(
                name="alerting-system-events",
                config=RSP_STREAM_CONFIG,
            )
            self.rsp_source_ids.append(source.id)
            logger.info(f"Created RSP stream source: {source.name}")
            self.client.rsp.start_source(source.id)
        except Exception as e:
            logger.warning(f"Could not create stream source: {e}")
            try:
                sources = self.client.rsp.list_sources()
                for src in sources.sources:
                    if "alerting" in src.name.lower():
                        self.rsp_source_ids.append(src.id)
                        logger.info(f"Using existing source: {src.name}")
                        break
            except Exception:
                pass

        if not self.rsp_source_ids:
            return False

        # Create continuous queries
        for query_def in RSP_CONTINUOUS_QUERIES:
            try:
                query = self.client.rsp.create_query(
                    ContinuousQueryCreate(
                        name=query_def["name"],
                        description=query_def["description"],
                        sparql=query_def["sparql"],
                        window=WindowConfig(
                            type=WindowType.TIME_BASED,
                            duration_seconds=query_def["window_duration"],
                            slide_seconds=query_def["window_slide"],
                        ),
                        stream_sources=self.rsp_source_ids,
                        output=OutputConfig(
                            push_to_event_bus=True,
                            persist_results=True,
                        ),
                    )
                )
                self.rsp_query_ids.append(query.id)
                logger.info(f"Created RSP query: {query.name}")
                self.client.rsp.activate_query(query.id)
            except Exception as e:
                logger.warning(f"Could not create query '{query_def['name']}': {e}")
                try:
                    queries = self.client.rsp.list_queries()
                    for q in queries.queries:
                        if q.name == query_def["name"]:
                            self.rsp_query_ids.append(q.id)
                            break
                except Exception:
                    pass

        self.rsp_enabled = len(self.rsp_query_ids) > 0
        logger.info(f"RSP enabled: {self.rsp_enabled} ({len(self.rsp_query_ids)} queries)")
        return self.rsp_enabled

    def check_rsp_alerts(self) -> List[Dict]:
        """Check RSP query results and generate alerts."""
        if not self.rsp_enabled:
            return []

        new_alerts = []

        for i, query_id in enumerate(self.rsp_query_ids):
            query_def = RSP_CONTINUOUS_QUERIES[i] if i < len(RSP_CONTINUOUS_QUERIES) else {}

            try:
                results = self.client.rsp.get_query_results(query_id, limit=5)

                # Log raw RSP response structure
                if hasattr(results, 'results') and results.results:
                    logger.info(f"=== RSP Response for '{query_def.get('name', query_id)}' ===")
                    logger.info(f"  Total results: {len(results.results)}")

                    for result in results.results:
                        bindings = result.bindings if hasattr(result, 'bindings') else []
                        logger.info(f"  Window: {result.window_start} -> {result.window_end}")
                        logger.info(f"  Event count: {getattr(result, 'event_count', 'N/A')}")
                        logger.info(f"  Bindings count: {len(bindings)}")

                        if bindings:
                            # Log first binding as example of raw format
                            logger.info(f"  Example binding (raw): {json.dumps(bindings[0], default=str)}")

                            for binding in bindings:
                                binding_hash = hash(str(sorted(binding.items()) if isinstance(binding, dict) else binding))
                                window_id = result.window_start or datetime.now().isoformat()
                                alert_id = f"rsp-{query_id}-{window_id}-{binding_hash}"

                                alert = {
                                    "id": alert_id,
                                    "type": query_def.get("name", "RSP Alert"),
                                    "severity": query_def.get("severity", "info"),
                                    "icon": query_def.get("icon", "📊"),
                                    "message": self._format_rsp_alert(query_def, binding),
                                    "timestamp": result.window_end or datetime.now().isoformat(),
                                    "source": "RSP",
                                    "data": binding,
                                }

                                if not any(a["id"] == alert_id for a in self.rsp_alerts):
                                    new_alerts.append(alert)
                                    logger.info(f"  RSP Alert: {alert['message']}")

            except Exception as e:
                logger.warning(f"Error checking RSP query {query_id}: {e}")

        self.rsp_alerts.extend(new_alerts)
        self.rsp_alerts[:] = self.rsp_alerts[-30:]

        return new_alerts

    def _parse_sparql_value(self, binding: dict, var_name: str) -> str:
        """Parse a SPARQL binding value from RSP results.

        Backend returns bindings in format: {"var": {"type": "literal", "value": "42.5"}}
        The value is already clean (no quotes or type annotations).
        """
        if var_name not in binding:
            return "?"

        var_data = binding[var_name]

        # Handle dict format with "value" key (standard SPARQL JSON results)
        if isinstance(var_data, dict):
            return var_data.get("value", str(var_data))

        return str(var_data)

    def _format_rsp_alert(self, query_def: dict, binding: dict) -> str:
        """Format an RSP alert message based on CEP pattern type."""
        name = query_def.get("name", "Alert")

        def get_val(var: str) -> str:
            return self._parse_sparql_value(binding, var)

        def get_system(var: str = "system") -> str:
            return get_val(var).split(":")[-1]

        def format_time(var: str) -> str:
            """Extract just the time portion from an ISO timestamp."""
            ts = get_val(var)
            if "T" in ts:
                return ts.split("T")[1][:8]  # HH:MM:SS
            return ts

        # CEP Pattern 1: Resource Exhaustion Sequence (3-event)
        if "Resource Exhaustion Sequence" in name:
            system = get_system()
            t1, t2, t3 = format_time("cpuTime"), format_time("memTime"), format_time("diskTime")
            return f"{system}: SEQUENCE CPU({t1}) -> Mem({t2}) -> Disk({t3})"

        # CEP Pattern 2: Performance Degradation Sequence (3-event)
        elif "Performance Degradation Sequence" in name:
            system = get_system()
            t1, t2, t3 = format_time("slowTime"), format_time("latencyTime"), format_time("errorTime")
            return f"{system}: SEQUENCE Slow({t1}) -> Latency({t2}) -> Errors({t3})"

        # CEP Pattern 3: Queue Pressure Sequence (3-event)
        elif "Queue Pressure Sequence" in name:
            queue = get_system("queue")
            t1, t2, t3 = format_time("backlogTime"), format_time("staleTime"), format_time("dlqTime")
            return f"{queue}: SEQUENCE Backlog({t1}) -> Stale({t2}) -> DLQ({t3})"

        # CEP Pattern 4: Database Stress Sequence (3-event)
        elif "Database Stress Sequence" in name:
            db = get_system("db")
            t1, t2, t3 = format_time("connTime"), format_time("queryTime"), format_time("lagTime")
            return f"{db}: SEQUENCE Connections({t1}) -> SlowQueries({t2}) -> RepLag({t3})"

        # CEP Pattern 5: CPU-Memory Cascade (2-event)
        elif "CPU-Memory Cascade" in name:
            system = get_system()
            t1, t2 = format_time("cpuTime"), format_time("memTime")
            return f"{system}: SEQUENCE CPU({t1}) -> Memory({t2})"

        # CEP Pattern: Cross-Tier Failure Correlation (concurrent)
        elif "Cross-Tier" in name:
            frontend = get_val("frontendCount")
            backend = get_val("backendCount")
            return f"SYSTEMIC: {frontend} frontend + {backend} backend systems degraded simultaneously"

        # CEP Pattern: Incident Blast Radius (concurrent)
        elif "Blast Radius" in name:
            affected = get_val("affectedSystems")
            return f"BLAST RADIUS: {affected} distinct systems affected by incident"

        # Fallback: format all binding values
        else:
            parts = []
            for var, data in binding.items():
                val = data.get("value", data) if isinstance(data, dict) else data
                parts.append(f"{var}={val}")
            return " | ".join(parts)

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for key, alert in self.alerts.items():
            if alert["id"] == alert_id:
                alert["status"] = "acknowledged"
                alert["acknowledgedAt"] = datetime.now().isoformat()
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        for key, alert in list(self.alerts.items()):
            if alert["id"] == alert_id:
                del self.alerts[key]
                return True
        return False

    def toggle_rule(self, rule_id: str) -> bool:
        """Toggle an alert rule enabled/disabled."""
        if rule_id in self.rules:
            self.rules[rule_id]["enabled"] = not self.rules[rule_id]["enabled"]
            return True
        return False

    def get_dashboard_data(self) -> Dict:
        """Get current dashboard state."""
        # System stats
        total_systems = len(self.systems)
        healthy = degraded = unhealthy = 0

        systems_data = []
        for sys_id, state in self.systems.items():
            cpu = state.properties.get("cpuUsage", 0)
            error_rate = state.properties.get("errorRate", 0)

            if cpu > 90 or error_rate > 5:
                status = "critical"
                unhealthy += 1
            elif cpu > 70 or error_rate > 1:
                status = "warning"
                degraded += 1
            else:
                status = "healthy"
                healthy += 1

            systems_data.append({
                "id": sys_id,
                "name": state.name,
                "type": state.type,
                "status": status,
                "anomaly": state.anomaly_type.value,
                "metrics": {
                    "cpu": state.properties.get("cpuUsage", 0),
                    "memory": state.properties.get("memoryUsage", 0),
                    "disk": state.properties.get("diskUsage", 0),
                    "errorRate": state.properties.get("errorRate", 0),
                    "responseTime": state.properties.get("responseTimeMs") or state.properties.get("avgLatencyMs", 0),
                    "requests": state.properties.get("requestsPerSecond") or state.properties.get("queriesPerSecond", 0),
                }
            })

        # Sort systems by status (critical first)
        status_order = {"critical": 0, "warning": 1, "healthy": 2}
        systems_data.sort(key=lambda s: status_order.get(s["status"], 3))

        # Alert stats
        alerts_data = list(self.alerts.values())
        alerts_data.sort(key=lambda a: (a["severity"] != "critical", a["triggeredAt"]))

        critical_count = sum(1 for a in alerts_data if a["severity"] == "critical")
        warning_count = sum(1 for a in alerts_data if a["severity"] == "warning")

        # Rules data
        rules_data = list(self.rules.values())
        triggered_rules = set(a["rule"] for a in alerts_data)

        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "systems": {
                    "total": total_systems,
                    "healthy": healthy,
                    "degraded": degraded,
                    "unhealthy": unhealthy,
                },
                "alerts": {
                    "total": len(alerts_data),
                    "critical": critical_count,
                    "warning": warning_count,
                },
                "rules": {
                    "total": len(self.rules),
                    "enabled": sum(1 for r in self.rules.values() if r.get("enabled")),
                    "triggered": len(triggered_rules),
                },
            },
            "systems": systems_data,
            "alerts": alerts_data,
            "rules": rules_data,
            "triggeredRules": list(triggered_rules),
            "channels": list(self.channels.values()),
            "rspEnabled": self.rsp_enabled,
            "rspAlerts": self.rsp_alerts[-15:],
            "rspQueryCount": len(self.rsp_query_ids),
            "rspQueries": [
                {
                    "name": q["name"],
                    "description": q["description"],
                    "icon": q["icon"],
                    "severity": q["severity"],
                    "window": f"{q['window_duration']}s window / {q['window_slide']}s slide",
                    "sparql": textwrap.dedent(q["sparql"]).strip(),
                }
                for q in RSP_CONTINUOUS_QUERIES
            ],
        }

    async def handle_websocket(self, websocket):
        """Handle WebSocket connections."""
        self.connected_clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.connected_clients)}")

        try:
            # Send initial state
            await websocket.send(json.dumps({
                "type": "init",
                "data": self.get_dashboard_data()
            }))

            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "inject_scenario":
                        scenario = data.get("scenario", "")
                        result = self.inject_scenario(scenario)
                        await websocket.send(json.dumps({
                            "type": "scenario_injected",
                            "data": result
                        }))

                    elif msg_type == "acknowledge_alert":
                        alert_id = data.get("alertId", "")
                        success = self.acknowledge_alert(alert_id)
                        await websocket.send(json.dumps({
                            "type": "alert_acknowledged",
                            "data": {"alertId": alert_id, "success": success}
                        }))

                    elif msg_type == "resolve_alert":
                        alert_id = data.get("alertId", "")
                        success = self.resolve_alert(alert_id)
                        await websocket.send(json.dumps({
                            "type": "alert_resolved",
                            "data": {"alertId": alert_id, "success": success}
                        }))

                    elif msg_type == "toggle_rule":
                        rule_id = data.get("ruleId", "")
                        success = self.toggle_rule(rule_id)
                        await websocket.send(json.dumps({
                            "type": "rule_toggled",
                            "data": {"ruleId": rule_id, "success": success}
                        }))

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON received: {message}")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connected_clients.discard(websocket)
            logger.info(f"Client disconnected. Total clients: {len(self.connected_clients)}")

    async def broadcast_update(self):
        """Broadcast updates to all connected clients."""
        if not self.connected_clients:
            return

        message = json.dumps({
            "type": "update",
            "data": self.get_dashboard_data()
        })

        await asyncio.gather(
            *[client.send(message) for client in self.connected_clients],
            return_exceptions=True
        )

    async def simulation_loop(self):
        """Main simulation loop."""
        while self.running:
            self.simulate_tick()

            # Check RSP for streaming alerts
            rsp_alerts = self.check_rsp_alerts()
            if rsp_alerts:
                # Broadcast RSP alerts immediately
                await asyncio.gather(
                    *[client.send(json.dumps({
                        "type": "rsp_alerts",
                        "alerts": rsp_alerts
                    })) for client in self.connected_clients],
                    return_exceptions=True
                )

            await self.broadcast_update()
            await asyncio.sleep(2)

    async def start_servers(self):
        """Start WebSocket server and simulation."""
        self.running = True

        # Start HTTP server in a thread
        http_thread = threading.Thread(target=self._run_http_server, daemon=True)
        http_thread.start()

        # Start WebSocket server
        async with serve(self.handle_websocket, "localhost", self.ws_port):
            logger.info(f"WebSocket server running on ws://localhost:{self.ws_port}")
            await self.simulation_loop()

    def _run_http_server(self):
        """Run the HTTP server for serving the dashboard."""
        class DashboardHandler(SimpleHTTPRequestHandler):
            dashboard_html = get_dashboard_html(self.ws_port)

            def do_GET(self):
                if self.path == "/" or self.path == "/index.html":
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(self.dashboard_html.encode())
                else:
                    self.send_error(404)

            def log_message(self, format, *args):
                pass  # Suppress HTTP logs

        server = HTTPServer(("localhost", self.http_port), DashboardHandler)
        logger.info(f"HTTP server running on http://localhost:{self.http_port}")
        server.serve_forever()

    def run(self):
        """Run the dashboard."""
        # Initialize RSP
        rsp_status = self.setup_rsp()

        print(f"\nStarting Alerting System Web Dashboard...")
        print(f"HTTP Server: http://localhost:{self.http_port}")
        print(f"WebSocket:   ws://localhost:{self.ws_port}")
        print(f"RSP Stream Processing: {'Enabled' if rsp_status else 'Disabled'}")
        print("\nOpen the HTTP URL in your browser to view the dashboard.")
        print("Press Ctrl+C to stop.\n")

        try:
            asyncio.run(self.start_servers())
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
            self.running = False


def get_dashboard_html(ws_port: int) -> str:
    """Return the dashboard HTML content."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-Time Alerting Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #1a1a2e 50%, #16213e 100%);
            color: #e0e0e0;
            min-height: 100vh;
            overflow-x: hidden;
        }}

        .dashboard {{
            padding: 20px;
            max-width: 1800px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            border: 1px solid rgba(255,255,255,0.1);
        }}

        header h1 {{
            font-size: 2.5em;
            background: linear-gradient(90deg, #00d4ff, #7b2ff7, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}

        .timestamp {{
            color: #888;
            font-size: 0.9em;
        }}

        .connection-status {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.85em;
            margin-top: 10px;
        }}

        .connected {{
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
            border: 1px solid #00ff88;
        }}

        .disconnected {{
            background: rgba(255, 68, 68, 0.2);
            color: #ff4444;
            border: 1px solid #ff4444;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}

        .card {{
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
        }}

        .card h2 {{
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #00d4ff;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .card h2::before {{
            content: '';
            width: 4px;
            height: 20px;
            background: linear-gradient(180deg, #00d4ff, #7b2ff7);
            border-radius: 2px;
        }}

        /* Summary Cards */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }}

        .summary-card {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }}

        .summary-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}

        .summary-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }}

        .summary-card .label {{
            color: #888;
            font-size: 0.9em;
        }}

        .summary-card.healthy .value {{ color: #00ff88; }}
        .summary-card.warning .value {{ color: #ffaa00; }}
        .summary-card.critical .value {{ color: #ff4444; }}
        .summary-card.info .value {{ color: #00d4ff; }}

        /* Control Panel */
        .controls {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
        }}

        .btn {{
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9em;
            font-weight: 600;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .btn-spike {{
            background: linear-gradient(135deg, #ff6b6b, #ee5a24);
            color: white;
        }}

        .btn-degradation {{
            background: linear-gradient(135deg, #ffaa00, #f39c12);
            color: white;
        }}

        .btn-cascade {{
            background: linear-gradient(135deg, #e74c3c, #c0392b);
            color: white;
        }}

        .btn-recovery {{
            background: linear-gradient(135deg, #00ff88, #00b894);
            color: #1a1a2e;
        }}

        .btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.3);
        }}

        .btn:active {{
            transform: translateY(0);
        }}

        /* Systems Table */
        .systems-table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .systems-table th,
        .systems-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}

        .systems-table th {{
            color: #888;
            font-weight: 600;
            font-size: 0.85em;
            text-transform: uppercase;
        }}

        .systems-table tr:hover {{
            background: rgba(255,255,255,0.05);
        }}

        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .status-healthy {{
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
        }}

        .status-warning {{
            background: rgba(255, 170, 0, 0.2);
            color: #ffaa00;
        }}

        .status-critical {{
            background: rgba(255, 68, 68, 0.2);
            color: #ff4444;
        }}

        .anomaly-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 8px;
            font-size: 0.75em;
            margin-left: 8px;
            background: rgba(255, 68, 68, 0.3);
            color: #ff6b6b;
        }}

        /* Metric Bar */
        .metric-bar {{
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            overflow: hidden;
            width: 100px;
            display: inline-block;
            vertical-align: middle;
            margin-right: 8px;
        }}

        .metric-bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }}

        .metric-bar-fill.low {{
            background: linear-gradient(90deg, #00ff88, #00d4ff);
        }}

        .metric-bar-fill.medium {{
            background: linear-gradient(90deg, #ffaa00, #ff6b6b);
        }}

        .metric-bar-fill.high {{
            background: linear-gradient(90deg, #ff4444, #e74c3c);
        }}

        /* Alerts List */
        .alert-item {{
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
            border-left: 4px solid;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .alert-item.critical {{
            border-color: #ff4444;
            background: rgba(255, 68, 68, 0.1);
        }}

        .alert-item.warning {{
            border-color: #ffaa00;
            background: rgba(255, 170, 0, 0.1);
        }}

        .alert-info {{
            flex: 1;
        }}

        .alert-source {{
            font-weight: 600;
            margin-bottom: 5px;
        }}

        .alert-details {{
            font-size: 0.85em;
            color: #888;
        }}

        .alert-actions {{
            display: flex;
            gap: 8px;
        }}

        .alert-btn {{
            padding: 6px 12px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8em;
            transition: all 0.2s;
        }}

        .alert-btn.ack {{
            background: rgba(0, 212, 255, 0.2);
            color: #00d4ff;
            border: 1px solid #00d4ff;
        }}

        .alert-btn.resolve {{
            background: rgba(0, 255, 136, 0.2);
            color: #00ff88;
            border: 1px solid #00ff88;
        }}

        .alert-btn:hover {{
            transform: scale(1.05);
        }}

        /* Rules List */
        .rule-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: rgba(255,255,255,0.03);
            border-radius: 8px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
        }}
        .rule-item:hover {{
            background: rgba(255,255,255,0.06);
            transform: translateX(2px);
        }}
        .rule-item:active {{
            transform: translateX(0);
        }}
        .rule-hint {{
            font-size: 0.65em;
            color: #555;
            margin-top: 4px;
        }}

        .rule-info {{
            flex: 1;
        }}

        .rule-name {{
            font-weight: 500;
            margin-bottom: 3px;
        }}

        .rule-condition {{
            font-size: 0.8em;
            color: #888;
        }}

        .rule-toggle {{
            position: relative;
            width: 50px;
            height: 26px;
        }}

        .rule-toggle input {{
            opacity: 0;
            width: 0;
            height: 0;
        }}

        .toggle-slider {{
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255,255,255,0.1);
            border-radius: 13px;
            transition: 0.3s;
        }}

        .toggle-slider:before {{
            position: absolute;
            content: "";
            height: 20px;
            width: 20px;
            left: 3px;
            bottom: 3px;
            background: white;
            border-radius: 50%;
            transition: 0.3s;
        }}

        input:checked + .toggle-slider {{
            background: #00ff88;
        }}

        input:checked + .toggle-slider:before {{
            transform: translateX(24px);
        }}

        .rule-triggered {{
            background: rgba(255, 170, 0, 0.1);
            border: 1px solid rgba(255, 170, 0, 0.3);
        }}

        /* System Type Icons */
        .type-icon {{
            display: inline-block;
            width: 30px;
            height: 30px;
            border-radius: 8px;
            text-align: center;
            line-height: 30px;
            font-size: 0.9em;
            margin-right: 10px;
        }}

        .type-WebServer {{ background: rgba(0, 212, 255, 0.2); color: #00d4ff; }}
        .type-DatabaseServer {{ background: rgba(123, 47, 247, 0.2); color: #7b2ff7; }}
        .type-ApplicationService {{ background: rgba(0, 255, 136, 0.2); color: #00ff88; }}
        .type-MessageQueue {{ background: rgba(255, 170, 0, 0.2); color: #ffaa00; }}

        /* Scrollable containers */
        .scrollable {{
            max-height: 400px;
            overflow-y: auto;
        }}

        .scrollable::-webkit-scrollbar {{
            width: 6px;
        }}

        .scrollable::-webkit-scrollbar-track {{
            background: rgba(255,255,255,0.05);
            border-radius: 3px;
        }}

        .scrollable::-webkit-scrollbar-thumb {{
            background: rgba(255,255,255,0.2);
            border-radius: 3px;
        }}

        /* Channels Grid */
        .channels-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 10px;
        }}

        .channel-item {{
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }}

        .channel-icon {{
            font-size: 1.5em;
            margin-bottom: 5px;
        }}

        .channel-name {{
            font-size: 0.85em;
            color: #888;
        }}

        .channel-status {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-top: 8px;
        }}

        .channel-status.active {{
            background: #00ff88;
            box-shadow: 0 0 10px #00ff88;
        }}

        .channel-status.inactive {{
            background: #666;
        }}

        /* Empty state */
        .empty-state {{
            text-align: center;
            padding: 30px;
            color: #666;
        }}

        .empty-state .icon {{
            font-size: 3em;
            margin-bottom: 10px;
        }}

        /* RSP Section */
        .rsp-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            margin-left: 10px;
        }}
        .rsp-badge.active {{
            background: rgba(123, 47, 247, 0.2);
            color: #7b2ff7;
            border: 1px solid #7b2ff7;
        }}
        .rsp-badge.inactive {{
            background: rgba(100, 100, 100, 0.2);
            color: #888;
            border: 1px solid #666;
        }}
        .rsp-queries-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 10px;
        }}
        .rsp-query-card {{
            background: rgba(123, 47, 247, 0.08);
            border: 1px solid rgba(123, 47, 247, 0.2);
            border-radius: 8px;
            padding: 10px 12px;
            display: flex;
            align-items: flex-start;
            gap: 10px;
            position: relative;
            cursor: pointer;
            transition: transform 0.1s, border-color 0.2s;
        }}
        .rsp-query-card:hover {{
            border-color: rgba(123, 47, 247, 0.5);
            transform: translateY(-1px);
        }}
        .rsp-query-card:active {{
            transform: translateY(0);
        }}
        .rsp-query-card.severity-critical {{
            border-color: rgba(255, 68, 68, 0.3);
            background: rgba(255, 68, 68, 0.05);
        }}
        .rsp-query-card.severity-warning {{
            border-color: rgba(255, 170, 0, 0.3);
            background: rgba(255, 170, 0, 0.05);
        }}
        .rsp-query-icon {{
            font-size: 1.3em;
            flex-shrink: 0;
        }}
        .rsp-query-info {{
            flex: 1;
            min-width: 0;
        }}
        .rsp-query-name {{
            font-weight: 600;
            font-size: 0.85em;
            margin-bottom: 2px;
        }}
        .rsp-query-desc {{
            font-size: 0.72em;
            color: #888;
            margin-bottom: 2px;
        }}
        .rsp-query-window {{
            font-size: 0.65em;
            color: #666;
            font-family: monospace;
        }}
        .rsp-query-hint {{
            font-size: 0.65em;
            color: #666;
            margin-top: 4px;
        }}
        /* Modal overlay for SPARQL query display */
        .sparql-modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            z-index: 10000;
            justify-content: center;
            align-items: center;
        }}
        .sparql-modal-overlay.active {{
            display: flex;
        }}
        .sparql-modal {{
            background: #1a1a2e;
            border: 2px solid #7b2ff7;
            border-radius: 12px;
            padding: 20px;
            max-width: 600px;
            width: 90%;
            max-height: 80vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            box-shadow: 0 20px 60px rgba(123, 47, 247, 0.3);
        }}
        .sparql-modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(123, 47, 247, 0.3);
        }}
        .sparql-modal-title {{
            font-size: 1.1em;
            color: #7b2ff7;
            font-weight: 600;
        }}
        .sparql-modal-close {{
            background: none;
            border: none;
            color: #888;
            font-size: 1.5em;
            cursor: pointer;
            padding: 0 5px;
            transition: color 0.2s;
        }}
        .sparql-modal-close:hover {{
            color: #ff4757;
        }}
        .sparql-modal pre {{
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 0.85em;
            color: #00d4ff;
            background: rgba(0, 0, 0, 0.4);
            padding: 15px;
            border-radius: 8px;
            overflow: auto;
            white-space: pre-wrap;
            word-break: break-word;
            margin: 0;
            flex: 1;
            max-height: 50vh;
        }}
        /* Rule detail modal */
        .rule-modal-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            z-index: 10000;
            justify-content: center;
            align-items: center;
        }}
        .rule-modal-overlay.active {{
            display: flex;
        }}
        .rule-modal {{
            background: #1a1a2e;
            border: 2px solid #00d4ff;
            border-radius: 12px;
            padding: 20px;
            max-width: 500px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 212, 255, 0.2);
        }}
        .rule-modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(0, 212, 255, 0.3);
        }}
        .rule-modal-title {{
            font-size: 1.1em;
            color: #00d4ff;
            font-weight: 600;
        }}
        .rule-modal-close {{
            background: none;
            border: none;
            color: #888;
            font-size: 1.5em;
            cursor: pointer;
            padding: 0 5px;
            transition: color 0.2s;
        }}
        .rule-modal-close:hover {{
            color: #ff4757;
        }}
        .rule-modal-body {{
            display: grid;
            gap: 12px;
        }}
        .rule-detail-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 6px;
        }}
        .rule-detail-label {{
            color: #888;
            font-size: 0.85em;
        }}
        .rule-detail-value {{
            color: #fff;
            font-weight: 500;
            font-family: 'Monaco', 'Consolas', monospace;
        }}
        .rule-detail-value.severity-critical {{
            color: #ff4444;
        }}
        .rule-detail-value.severity-warning {{
            color: #ffaa00;
        }}
        .rule-detail-value.severity-info {{
            color: #00d4ff;
        }}
        .rule-expression {{
            background: rgba(0, 212, 255, 0.1);
            border: 1px solid rgba(0, 212, 255, 0.3);
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            margin-top: 10px;
        }}
        .rule-expression-text {{
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 1.1em;
            color: #00ff88;
        }}
        .rsp-alert-item {{
            display: flex;
            align-items: center;
            padding: 10px 12px;
            background: rgba(123, 47, 247, 0.1);
            border-left: 3px solid #7b2ff7;
            border-radius: 8px;
            margin-bottom: 8px;
            animation: rspSlideIn 0.3s ease;
        }}
        @keyframes rspSlideIn {{
            from {{ opacity: 0; transform: translateX(-10px); }}
            to {{ opacity: 1; transform: translateX(0); }}
        }}
        .rsp-alert-item.critical {{
            background: rgba(255, 68, 68, 0.1);
            border-left-color: #ff4444;
        }}
        .rsp-alert-item.warning {{
            background: rgba(255, 170, 0, 0.1);
            border-left-color: #ffaa00;
        }}
        .rsp-alert-icon {{
            font-size: 1.2em;
            margin-right: 10px;
        }}
        .rsp-alert-content {{
            flex: 1;
        }}
        .rsp-alert-type {{
            font-size: 0.7em;
            color: #888;
            text-transform: uppercase;
        }}
        .rsp-alert-message {{
            font-size: 0.85em;
            color: #e0e0e0;
        }}
        .rsp-alert-time {{
            font-size: 0.65em;
            color: #666;
        }}

        /* Animations for failing systems */
        @keyframes criticalPulse {{
            0%, 100% {{
                box-shadow: 0 0 5px rgba(255, 68, 68, 0.5);
                border-color: rgba(255, 68, 68, 0.5);
            }}
            50% {{
                box-shadow: 0 0 25px rgba(255, 68, 68, 0.9);
                border-color: rgba(255, 68, 68, 1);
            }}
        }}

        @keyframes warningPulse {{
            0%, 100% {{
                box-shadow: 0 0 3px rgba(255, 170, 0, 0.3);
                border-color: rgba(255, 170, 0, 0.3);
            }}
            50% {{
                box-shadow: 0 0 15px rgba(255, 170, 0, 0.7);
                border-color: rgba(255, 170, 0, 0.8);
            }}
        }}

        @keyframes shake {{
            0%, 100% {{ transform: translateX(0); }}
            25% {{ transform: translateX(-2px); }}
            75% {{ transform: translateX(2px); }}
        }}

        @keyframes alertFlash {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.6; }}
        }}

        .system-row-critical {{
            animation: criticalPulse 1s ease-in-out infinite;
            background: rgba(255, 68, 68, 0.1) !important;
        }}

        .system-row-warning {{
            animation: warningPulse 1.5s ease-in-out infinite;
            background: rgba(255, 170, 0, 0.05) !important;
        }}

        .alert-item.critical {{
            animation: criticalPulse 0.8s ease-in-out infinite, shake 0.3s ease-in-out infinite;
        }}

        .alert-item.warning {{
            animation: warningPulse 1.2s ease-in-out infinite;
        }}

        .anomaly-badge {{
            animation: alertFlash 0.5s ease-in-out infinite;
        }}

        .status-badge.status-critical {{
            animation: criticalPulse 1s ease-in-out infinite;
        }}

        .summary-card.critical .value {{
            animation: alertFlash 1s ease-in-out infinite;
        }}

        @media (max-width: 768px) {{
            .summary-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .controls {{
                justify-content: center;
            }}

            .systems-table {{
                font-size: 0.85em;
            }}
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <header>
            <h1>Real-Time Alerting Dashboard</h1>
            <div class="timestamp" id="timestamp">Connecting...</div>
            <div class="connection-status disconnected" id="connection-status">Disconnected</div>
        </header>

        <!-- Summary Cards -->
        <div class="summary-grid">
            <div class="summary-card healthy">
                <div class="value" id="healthy-count">0</div>
                <div class="label">Healthy Systems</div>
            </div>
            <div class="summary-card warning">
                <div class="value" id="degraded-count">0</div>
                <div class="label">Degraded</div>
            </div>
            <div class="summary-card critical">
                <div class="value" id="critical-alerts">0</div>
                <div class="label">Critical Alerts</div>
            </div>
            <div class="summary-card info">
                <div class="value" id="total-rules">0</div>
                <div class="label">Active Rules</div>
            </div>
        </div>

        <!-- Scenario Controls -->
        <div class="card">
            <h2>Scenario Injection</h2>
            <div class="controls">
                <button class="btn btn-spike" onclick="injectScenario('spike')">
                    <span>Inject Spike</span>
                </button>
                <button class="btn btn-degradation" onclick="injectScenario('degradation')">
                    <span>Inject Degradation</span>
                </button>
                <button class="btn btn-cascade" onclick="injectScenario('cascade')">
                    <span>Cascading Failure</span>
                </button>
                <button class="btn btn-recovery" onclick="injectScenario('recovery')">
                    <span>Recovery / Clear All</span>
                </button>
            </div>
        </div>

        <div class="grid">
            <!-- Active Alerts -->
            <div class="card" style="grid-column: span 2;">
                <h2>Active Alerts</h2>
                <div class="scrollable" id="alerts-container">
                    <div class="empty-state">
                        <div class="icon">&#10003;</div>
                        <div>No active alerts</div>
                    </div>
                </div>
            </div>

            <!-- Notification Channels -->
            <div class="card">
                <h2>Notification Channels</h2>
                <div class="channels-grid" id="channels-container">
                </div>
            </div>
        </div>

        <!-- RSP Stream Processing -->
        <div class="card">
            <h2>RSP Stream Processing <span class="rsp-badge inactive" id="rsp-status">Connecting...</span></h2>
            <div style="margin-bottom: 15px;">
                <h3 style="font-size: 0.9em; color: #888; margin-bottom: 10px;">Continuous Queries</h3>
                <div class="rsp-queries-grid" id="rsp-queries-container">
                </div>
            </div>
            <div>
                <h3 style="font-size: 0.9em; color: #888; margin-bottom: 10px;">Stream Alerts</h3>
                <div class="scrollable" id="rsp-alerts-container" style="max-height: 200px;">
                    <div class="empty-state">
                        <div class="icon">&#128202;</div>
                        <div>Waiting for events...</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Systems Status -->
        <div class="card">
            <h2>System Status</h2>
            <div class="scrollable">
                <table class="systems-table">
                    <thead>
                        <tr>
                            <th>System</th>
                            <th>Type</th>
                            <th>CPU</th>
                            <th>Memory</th>
                            <th>Error Rate</th>
                            <th>Response Time</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="systems-table-body">
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Alert Rules -->
        <div class="card">
            <h2>Alert Rules</h2>
            <div class="scrollable" id="rules-container">
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let dashboardData = null;

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        const typeIcons = {{
            'WebServer': 'W',
            'DatabaseServer': 'D',
            'ApplicationService': 'A',
            'MessageQueue': 'Q'
        }};

        const channelIcons = {{
            'pagerduty': '&#128276;',
            'slack': '&#128172;',
            'email': '&#9993;',
            'webhook': '&#128279;',
            'console': '&#128187;'
        }};

        function connect() {{
            ws = new WebSocket('ws://localhost:{ws_port}');

            ws.onopen = () => {{
                document.getElementById('connection-status').textContent = 'Connected';
                document.getElementById('connection-status').className = 'connection-status connected';
            }};

            ws.onclose = () => {{
                document.getElementById('connection-status').textContent = 'Disconnected';
                document.getElementById('connection-status').className = 'connection-status disconnected';
                setTimeout(connect, 3000);
            }};

            ws.onmessage = (event) => {{
                const message = JSON.parse(event.data);
                if (message.type === 'init' || message.type === 'update') {{
                    dashboardData = message.data;
                    updateDashboard();
                }} else if (message.type === 'scenario_injected') {{
                    console.log('Scenario injected:', message.data);
                }} else if (message.type === 'rsp_alerts') {{
                    addRspAlerts(message.alerts);
                }}
            }};
        }}

        function updateDashboard() {{
            if (!dashboardData) return;

            // Update timestamp
            const ts = new Date(dashboardData.timestamp);
            document.getElementById('timestamp').textContent = ts.toLocaleString();

            // Update summary cards
            const summary = dashboardData.summary;
            document.getElementById('healthy-count').textContent = summary.systems.healthy;
            document.getElementById('degraded-count').textContent = summary.systems.degraded + summary.systems.unhealthy;
            document.getElementById('critical-alerts').textContent = summary.alerts.critical;
            document.getElementById('total-rules').textContent = summary.rules.enabled;

            // Update systems table
            updateSystemsTable();

            // Update alerts
            updateAlerts();

            // Update rules
            updateRules();

            // Update channels
            updateChannels();

            // Update RSP status and alerts
            updateRspStatus();
            updateRspAlerts();
        }}

        function updateSystemsTable() {{
            const tbody = document.getElementById('systems-table-body');
            tbody.innerHTML = '';

            dashboardData.systems.forEach(system => {{
                const row = document.createElement('tr');

                const anomalyBadge = system.anomaly !== 'none'
                    ? `<span class="anomaly-badge">${{system.anomaly}}</span>`
                    : '';

                // Add animation class for failing systems
                if (system.status === 'critical') {{
                    row.className = 'system-row-critical';
                }} else if (system.status === 'warning') {{
                    row.className = 'system-row-warning';
                }}

                row.innerHTML = `
                    <td>
                        <span class="type-icon type-${{system.type}}">${{typeIcons[system.type] || '?'}}</span>
                        ${{system.name}}
                        ${{anomalyBadge}}
                    </td>
                    <td>${{system.type}}</td>
                    <td>${{renderMetricBar(system.metrics.cpu, 100)}}</td>
                    <td>${{renderMetricBar(system.metrics.memory, 100)}}</td>
                    <td>${{system.metrics.errorRate.toFixed(2)}}%</td>
                    <td>${{system.metrics.responseTime.toFixed(0)}}ms</td>
                    <td><span class="status-badge status-${{system.status}}">${{system.status}}</span></td>
                `;

                tbody.appendChild(row);
            }});
        }}

        function renderMetricBar(value, max) {{
            const pct = Math.min(100, (value / max) * 100);
            let colorClass = 'low';
            if (pct > 70) colorClass = 'medium';
            if (pct > 90) colorClass = 'high';

            return `
                <div class="metric-bar">
                    <div class="metric-bar-fill ${{colorClass}}" style="width: ${{pct}}%"></div>
                </div>
                ${{value.toFixed(1)}}%
            `;
        }}

        function updateAlerts() {{
            const container = document.getElementById('alerts-container');

            if (dashboardData.alerts.length === 0) {{
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">&#10003;</div>
                        <div>No active alerts</div>
                    </div>
                `;
                return;
            }}

            container.innerHTML = dashboardData.alerts.map(alert => {{
                const triggeredAt = new Date(alert.triggeredAt);
                const age = formatAge(triggeredAt);

                return `
                    <div class="alert-item ${{alert.severity}}">
                        <div class="alert-info">
                            <div class="alert-source">
                                ${{alert.severity.toUpperCase()}} - ${{alert.source}}
                            </div>
                            <div class="alert-details">
                                ${{alert.metric}}: ${{alert.value.toFixed(2)}} (threshold: ${{alert.threshold}}) |
                                Status: ${{alert.status}} | Age: ${{age}}
                            </div>
                        </div>
                        <div class="alert-actions">
                            ${{alert.status === 'open' ? `<button class="alert-btn ack" onclick="acknowledgeAlert('${{alert.id}}')">ACK</button>` : ''}}
                            <button class="alert-btn resolve" onclick="resolveAlert('${{alert.id}}')">Resolve</button>
                        </div>
                    </div>
                `;
            }}).join('');
        }}

        function updateRules() {{
            const container = document.getElementById('rules-container');
            const triggeredRules = new Set(dashboardData.triggeredRules);

            container.innerHTML = dashboardData.rules.map((rule, i) => {{
                const isTriggered = triggeredRules.has(rule.id);
                const triggeredClass = isTriggered ? 'rule-triggered' : '';

                return `
                    <div class="rule-item ${{triggeredClass}}" onclick="showRuleModal(${{i}})">
                        <div class="rule-info">
                            <div class="rule-name">
                                ${{rule.name}}
                                ${{isTriggered ? '<span class="anomaly-badge">TRIGGERED</span>' : ''}}
                            </div>
                            <div class="rule-condition">
                                ${{rule.metric}} ${{rule.condition.replace('_', ' ')}} ${{rule.threshold}}
                                | Severity: ${{rule.severity}}
                            </div>
                            <div class="rule-hint">Click to view details</div>
                        </div>
                        <label class="rule-toggle" onclick="event.stopPropagation()">
                            <input type="checkbox" ${{rule.enabled ? 'checked' : ''}}
                                   onchange="toggleRule('${{rule.id}}')">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                `;
            }}).join('');
        }}

        function showRuleModal(ruleIndex) {{
            const rules = dashboardData.rules || [];
            const rule = rules[ruleIndex];
            if (!rule) return;

            document.getElementById('rule-modal-name').textContent = rule.name;

            const conditionMap = {{
                'greater_than': '>',
                'less_than': '<',
                'equals': '=',
                'not_equals': '!=',
                'greater_equal': '>=',
                'less_equal': '<='
            }};
            const operator = conditionMap[rule.condition] || rule.condition;

            document.getElementById('rule-modal-expression').textContent =
                `${{rule.metric}} ${{operator}} ${{rule.threshold}}`;
            document.getElementById('rule-modal-metric').textContent = rule.metric;
            document.getElementById('rule-modal-condition').textContent = rule.condition.replace('_', ' ');
            document.getElementById('rule-modal-threshold').textContent = rule.threshold;
            document.getElementById('rule-modal-severity').textContent = rule.severity;
            document.getElementById('rule-modal-severity').className = `rule-detail-value severity-${{rule.severity}}`;
            document.getElementById('rule-modal-duration').textContent = rule.duration ? `${{rule.duration}}s` : 'Immediate';
            document.getElementById('rule-modal-target').textContent = rule.targetType || 'All';
            document.getElementById('rule-modal-enabled').textContent = rule.enabled ? 'Yes' : 'No';

            document.getElementById('rule-modal-overlay').classList.add('active');
        }}

        function closeRuleModal() {{
            document.getElementById('rule-modal-overlay').classList.remove('active');
        }}

        function updateChannels() {{
            const container = document.getElementById('channels-container');

            container.innerHTML = dashboardData.channels.map(channel => {{
                const icon = channelIcons[channel.type] || '&#128227;';
                const statusClass = channel.enabled ? 'active' : 'inactive';

                return `
                    <div class="channel-item">
                        <div class="channel-icon">${{icon}}</div>
                        <div class="channel-name">${{channel.name}}</div>
                        <div class="channel-status ${{statusClass}}"></div>
                    </div>
                `;
            }}).join('');
        }}

        function updateRspStatus() {{
            const badge = document.getElementById('rsp-status');
            if (dashboardData.rspEnabled) {{
                badge.textContent = `Active (${{dashboardData.rspQueryCount}} queries)`;
                badge.className = 'rsp-badge active';
            }} else {{
                badge.textContent = 'Disabled';
                badge.className = 'rsp-badge inactive';
            }}

            // Render continuous queries
            renderRspQueries();
        }}

        function renderRspQueries() {{
            const container = document.getElementById('rsp-queries-container');
            const queries = dashboardData.rspQueries || [];

            if (queries.length === 0) {{
                container.innerHTML = '<div style="color: #666; font-size: 0.85em;">No queries configured</div>';
                return;
            }}

            container.innerHTML = queries.map((q, i) => `
                <div class="rsp-query-card severity-${{q.severity}}" onclick="showSparqlModal(${{i}})">
                    <div class="rsp-query-icon">${{q.icon}}</div>
                    <div class="rsp-query-info">
                        <div class="rsp-query-name">${{q.name}}</div>
                        <div class="rsp-query-desc">${{q.description}}</div>
                        <div class="rsp-query-window">${{q.window}}</div>
                        <div class="rsp-query-hint">Click to view SPARQL</div>
                    </div>
                </div>
            `).join('');
        }}

        function showSparqlModal(queryIndex) {{
            const queries = dashboardData.rspQueries || [];
            const q = queries[queryIndex];
            if (!q) return;

            document.getElementById('sparql-modal-query-name').textContent = q.name;
            document.getElementById('sparql-modal-content').textContent = q.sparql || 'No query defined';
            document.getElementById('sparql-modal-overlay').classList.add('active');
        }}

        function closeSparqlModal() {{
            document.getElementById('sparql-modal-overlay').classList.remove('active');
        }}

        function updateRspAlerts() {{
            const container = document.getElementById('rsp-alerts-container');
            const alerts = dashboardData.rspAlerts || [];

            if (alerts.length === 0) {{
                if (!dashboardData.rspEnabled) {{
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="icon">&#128202;</div>
                            <div>RSP not available</div>
                        </div>
                    `;
                }} else {{
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="icon">&#10003;</div>
                            <div>No stream alerts - All patterns normal</div>
                        </div>
                    `;
                }}
                return;
            }}

            container.innerHTML = alerts.slice().reverse().map(alert => {{
                const time = new Date(alert.timestamp).toLocaleTimeString();
                return `
                    <div class="rsp-alert-item ${{alert.severity}}">
                        <div class="rsp-alert-icon">${{alert.icon}}</div>
                        <div class="rsp-alert-content">
                            <div class="rsp-alert-type">${{alert.type}}</div>
                            <div class="rsp-alert-message">${{alert.message}}</div>
                        </div>
                        <div class="rsp-alert-time">${{time}}</div>
                    </div>
                `;
            }}).join('');
        }}

        function addRspAlerts(alerts) {{
            const container = document.getElementById('rsp-alerts-container');
            const emptyState = container.querySelector('.empty-state');
            if (emptyState) container.innerHTML = '';

            alerts.forEach(alert => {{
                const time = new Date(alert.timestamp).toLocaleTimeString();
                const html = `
                    <div class="rsp-alert-item ${{alert.severity}}">
                        <div class="rsp-alert-icon">${{alert.icon}}</div>
                        <div class="rsp-alert-content">
                            <div class="rsp-alert-type">${{alert.type}}</div>
                            <div class="rsp-alert-message">${{alert.message}}</div>
                        </div>
                        <div class="rsp-alert-time">${{time}}</div>
                    </div>
                `;
                container.insertAdjacentHTML('afterbegin', html);
            }});

            // Keep only last 15
            while (container.children.length > 15) {{
                container.removeChild(container.lastChild);
            }}
        }}

        function formatAge(date) {{
            const seconds = Math.floor((new Date() - date) / 1000);
            if (seconds < 60) return `${{seconds}}s`;
            if (seconds < 3600) return `${{Math.floor(seconds / 60)}}m`;
            if (seconds < 86400) return `${{Math.floor(seconds / 3600)}}h`;
            return `${{Math.floor(seconds / 86400)}}d`;
        }}

        function injectScenario(scenario) {{
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'inject_scenario',
                    scenario: scenario
                }}));
            }}
        }}

        function acknowledgeAlert(alertId) {{
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'acknowledge_alert',
                    alertId: alertId
                }}));
            }}
        }}

        function resolveAlert(alertId) {{
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'resolve_alert',
                    alertId: alertId
                }}));
            }}
        }}

        function toggleRule(ruleId) {{
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'toggle_rule',
                    ruleId: ruleId
                }}));
            }}
        }}

        // Initialize connection
        connect();

        // Close modals on overlay click
        document.getElementById('sparql-modal-overlay').addEventListener('click', function(e) {{
            if (e.target === this) closeSparqlModal();
        }});
        document.getElementById('rule-modal-overlay').addEventListener('click', function(e) {{
            if (e.target === this) closeRuleModal();
        }});

        // Close modals on Escape key
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                closeSparqlModal();
                closeRuleModal();
            }}
        }});
    </script>

    <!-- SPARQL Query Modal -->
    <div id="sparql-modal-overlay" class="sparql-modal-overlay">
        <div class="sparql-modal">
            <div class="sparql-modal-header">
                <div class="sparql-modal-title" id="sparql-modal-query-name">Query Name</div>
                <button class="sparql-modal-close" onclick="closeSparqlModal()">&times;</button>
            </div>
            <pre id="sparql-modal-content"></pre>
        </div>
    </div>

    <!-- Rule Detail Modal -->
    <div id="rule-modal-overlay" class="rule-modal-overlay">
        <div class="rule-modal">
            <div class="rule-modal-header">
                <div class="rule-modal-title" id="rule-modal-name">Rule Name</div>
                <button class="rule-modal-close" onclick="closeRuleModal()">&times;</button>
            </div>
            <div class="rule-expression">
                <div style="font-size: 0.75em; color: #888; margin-bottom: 5px;">CONDITION</div>
                <div class="rule-expression-text" id="rule-modal-expression">metric > threshold</div>
            </div>
            <div class="rule-modal-body">
                <div class="rule-detail-row">
                    <span class="rule-detail-label">Metric</span>
                    <span class="rule-detail-value" id="rule-modal-metric">cpuUsage</span>
                </div>
                <div class="rule-detail-row">
                    <span class="rule-detail-label">Condition</span>
                    <span class="rule-detail-value" id="rule-modal-condition">greater than</span>
                </div>
                <div class="rule-detail-row">
                    <span class="rule-detail-label">Threshold</span>
                    <span class="rule-detail-value" id="rule-modal-threshold">80</span>
                </div>
                <div class="rule-detail-row">
                    <span class="rule-detail-label">Severity</span>
                    <span class="rule-detail-value" id="rule-modal-severity">critical</span>
                </div>
                <div class="rule-detail-row">
                    <span class="rule-detail-label">Duration</span>
                    <span class="rule-detail-value" id="rule-modal-duration">300s</span>
                </div>
                <div class="rule-detail-row">
                    <span class="rule-detail-label">Target Type</span>
                    <span class="rule-detail-value" id="rule-modal-target">Server</span>
                </div>
                <div class="rule-detail-row">
                    <span class="rule-detail-label">Enabled</span>
                    <span class="rule-detail-value" id="rule-modal-enabled">Yes</span>
                </div>
            </div>
        </div>
    </div>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Alerting System Web Dashboard")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--port", type=int, default=8085, help="HTTP port (default: 8085)")
    parser.add_argument("--ws-port", type=int, default=8086, help="WebSocket port (default: 8086)")
    args = parser.parse_args()

    client = get_client(args.base_url)
    dashboard = AlertingDashboard(client, args.port, args.ws_port)

    print("Loading data from DTaaS...")
    dashboard.load_data()

    if not dashboard.systems:
        print("No systems found. Run seed.py first.")
        return

    dashboard.run()


if __name__ == "__main__":
    main()
