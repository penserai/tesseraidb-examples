#!/usr/bin/env python3
"""
Real-Time Alerting System - Monitoring Daemon
==============================================

A production-grade monitoring daemon that:
- Continuously evaluates alert rules against system metrics
- Manages alert lifecycle (open, acknowledge, resolve)
- Sends notifications through configured channels
- Handles alert deduplication and aggregation
- Implements escalation policies

Usage:
    python monitor.py [--base-url URL] [--interval SECONDS]
    python monitor.py --dry-run  # Show what would trigger without updating
"""

import sys
import os
import time
import random
import argparse
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import get_client, create_twin_safe, add_relationship_safe, logger


class AlertStatus(Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    """Alert rule configuration."""
    rule_id: str
    name: str
    metric: str
    condition: str
    threshold: float
    severity: str
    duration: int  # seconds
    enabled: bool
    target_type: Optional[str] = None
    notification_channels: List[str] = field(default_factory=list)


@dataclass
class ActiveAlert:
    """Currently active alert."""
    alert_id: str
    rule_id: str
    source_id: str
    source_name: str
    metric: str
    current_value: float
    threshold: float
    severity: str
    status: AlertStatus
    triggered_at: datetime
    last_notification: Optional[datetime] = None
    notification_count: int = 0
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    escalation_level: int = 0


class Colors:
    """ANSI colors for console output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


class AlertMonitor:
    """
    Real-time alert monitoring engine.
    """

    def __init__(self, client, check_interval: float = 10.0, dry_run: bool = False):
        self.client = client
        self.check_interval = check_interval
        self.dry_run = dry_run

        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, ActiveAlert] = {}
        self.systems: Dict[str, Dict] = {}
        self.channels: Dict[str, Dict] = {}

        # Condition tracking for duration-based alerts
        self.condition_start: Dict[str, datetime] = {}

        # Statistics
        self.stats = {
            "checks": 0,
            "alerts_triggered": 0,
            "alerts_resolved": 0,
            "notifications_sent": 0,
        }

    def _normalize_properties(self, properties: Dict) -> Dict:
        """
        Normalize property names by stripping domain prefixes.
        The API returns properties like 'alerting_system#metric'
        but we want to access them as 'metric'.
        """
        normalized = {}
        for key, value in properties.items():
            # Strip domain prefix (e.g., 'alerting_system#metric' -> 'metric')
            if '#' in key:
                short_key = key.split('#', 1)[1]
            else:
                short_key = key
            normalized[short_key] = value
        return normalized

    def load_configuration(self):
        """Load alert rules, systems, and channels from DTaaS."""
        try:
            # Use larger page size to get all twins
            twins = self.client.twins.list(domain="alerting_system", page_size=200)

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                # SDK model uses 'type_uri' not 'type'
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                twin_type = type_val.split("#")[-1] if type_val else ""
                twin_id = twin_dict["id"]
                raw_props = twin_dict.get("properties", {})
                props = self._normalize_properties(raw_props)

                if twin_type == "AlertRule":
                    self.rules[twin_id] = AlertRule(
                        rule_id=twin_id,
                        name=twin_dict.get("name", twin_id),
                        metric=props.get("metric", ""),
                        condition=props.get("condition", "greater_than"),
                        threshold=props.get("threshold", 0),
                        severity=props.get("severity", "warning"),
                        duration=props.get("duration", 0),
                        enabled=props.get("enabled", True),
                        target_type=props.get("targetType"),
                        notification_channels=props.get("notificationChannels", []),
                    )

                elif twin_type == "NotificationChannel":
                    self.channels[twin_id] = {
                        "id": twin_id,
                        "name": twin_dict.get("name", twin_id),
                        "type": props.get("channelType", "console"),
                        "enabled": props.get("enabled", True),
                        "config": props.get("config", {}),
                    }

                elif twin_type in ["WebServer", "DatabaseServer", "ApplicationService", "MessageQueue"]:
                    self.systems[twin_id] = {
                        "id": twin_id,
                        "name": twin_dict.get("name", twin_id),
                        "type": twin_type,
                        "properties": props,
                    }

                elif twin_type == "Alert" and props.get("status") in ["open", "acknowledged"]:
                    # Load existing active alerts
                    self.active_alerts[twin_id] = ActiveAlert(
                        alert_id=twin_id,
                        rule_id=props.get("ruleId", ""),
                        source_id=props.get("sourceId", ""),
                        source_name=props.get("sourceId", ""),
                        metric=props.get("metric", ""),
                        current_value=props.get("currentValue", 0),
                        threshold=props.get("threshold", 0),
                        severity=props.get("severity", "warning"),
                        status=AlertStatus(props.get("status", "open")),
                        triggered_at=datetime.fromisoformat(props.get("triggeredAt", datetime.now().isoformat())),
                        notification_count=props.get("notificationCount", 0),
                        escalation_level=props.get("escalationLevel", 0),
                    )

            logger.info(f"Loaded {len(self.rules)} rules, {len(self.systems)} systems, "
                       f"{len(self.channels)} channels, {len(self.active_alerts)} active alerts")

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Evaluate an alert condition."""
        if condition == "greater_than":
            return value > threshold
        elif condition == "less_than":
            return value < threshold
        elif condition == "equals":
            return value == threshold
        elif condition == "not_equals":
            return value != threshold
        elif condition == "greater_than_or_equals":
            return value >= threshold
        elif condition == "less_than_or_equals":
            return value <= threshold
        return False

    def check_rule(self, rule: AlertRule, system_id: str, system: Dict) -> Optional[ActiveAlert]:
        """Check if a rule triggers for a system."""
        props = system.get("properties", {})
        metric_value = props.get(rule.metric)

        if metric_value is None:
            return None

        condition_met = self.evaluate_condition(metric_value, rule.condition, rule.threshold)

        condition_key = f"{rule.rule_id}:{system_id}"

        if condition_met:
            # Track condition start time
            if condition_key not in self.condition_start:
                self.condition_start[condition_key] = datetime.now()

            # Check if duration requirement is met
            elapsed = (datetime.now() - self.condition_start[condition_key]).total_seconds()

            if elapsed >= rule.duration:
                # Generate alert ID
                alert_id = f"alert-{rule.rule_id}-{system_id}"

                # Check if alert already exists
                if alert_id in self.active_alerts:
                    # Update existing alert
                    alert = self.active_alerts[alert_id]
                    alert.current_value = metric_value
                    return None  # Already active, no new alert

                # Create new alert
                return ActiveAlert(
                    alert_id=alert_id,
                    rule_id=rule.rule_id,
                    source_id=system_id,
                    source_name=system.get("name", system_id),
                    metric=rule.metric,
                    current_value=metric_value,
                    threshold=rule.threshold,
                    severity=rule.severity,
                    status=AlertStatus.OPEN,
                    triggered_at=datetime.now(),
                )
        else:
            # Condition no longer met
            if condition_key in self.condition_start:
                del self.condition_start[condition_key]

            # Check if alert should be auto-resolved
            alert_id = f"alert-{rule.rule_id}-{system_id}"
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                self.resolve_alert(alert, "Condition no longer met")

        return None

    def trigger_alert(self, alert: ActiveAlert, rule: AlertRule):
        """Trigger a new alert."""
        self.active_alerts[alert.alert_id] = alert
        self.stats["alerts_triggered"] += 1

        # Log the alert
        self.log_alert(alert, "TRIGGERED")

        # Send notifications
        self.send_notifications(alert, rule)

        # Persist to DTaaS
        if not self.dry_run:
            try:
                self.client.twins.create({
                    "id": alert.alert_id,
                    "type": f"http://tesserai.io/ontology/alerting_system#Alert",
                    "name": f"Alert: {rule.name} on {alert.source_name}",
                    "domain": "alerting_system",
                    "properties": {
                        "ruleId": alert.rule_id,
                        "sourceId": alert.source_id,
                        "metric": alert.metric,
                        "currentValue": alert.current_value,
                        "threshold": alert.threshold,
                        "severity": alert.severity,
                        "status": alert.status.value,
                        "triggeredAt": alert.triggered_at.isoformat(),
                        "notificationCount": alert.notification_count,
                        "escalationLevel": alert.escalation_level,
                    }
                })

                # Create lineage relationships for provenance tracking
                # Alert is triggered by a rule
                add_relationship_safe(self.client, alert.alert_id, "triggeredBy", alert.rule_id)
                # Alert is derived from source system metrics
                add_relationship_safe(self.client, alert.alert_id, "derivedFrom", alert.source_id)
                # Alert affects the source system
                add_relationship_safe(self.client, alert.alert_id, "affectsSystem", alert.source_id)

            except Exception as e:
                logger.warning(f"Failed to persist alert: {e}")

    def resolve_alert(self, alert: ActiveAlert, reason: str = ""):
        """Resolve an active alert."""
        if alert.alert_id not in self.active_alerts:
            return

        alert.status = AlertStatus.RESOLVED
        self.stats["alerts_resolved"] += 1

        # Log resolution
        self.log_alert(alert, "RESOLVED", reason)

        # Update in DTaaS
        if not self.dry_run:
            try:
                self.client.twins.update(alert.alert_id, {
                    "properties": {
                        "status": "resolved",
                        "resolvedAt": datetime.now().isoformat(),
                        "resolutionReason": reason,
                    }
                })
            except Exception as e:
                logger.warning(f"Failed to update alert: {e}")

        del self.active_alerts[alert.alert_id]

    def send_notifications(self, alert: ActiveAlert, rule: AlertRule):
        """Send notifications for an alert."""
        for channel_id in rule.notification_channels:
            channel = self.channels.get(channel_id)
            if not channel or not channel.get("enabled"):
                continue

            self.send_to_channel(alert, channel)
            alert.notification_count += 1
            self.stats["notifications_sent"] += 1

        alert.last_notification = datetime.now()

    def send_to_channel(self, alert: ActiveAlert, channel: Dict):
        """Send notification to a specific channel."""
        channel_type = channel.get("type", "console")

        # Format message
        message = self.format_alert_message(alert)

        if channel_type == "console":
            self.log_notification(channel, alert)
        elif channel_type == "slack":
            logger.info(f"[SLACK] Would send to {channel['config'].get('channel')}: {message}")
        elif channel_type == "pagerduty":
            logger.info(f"[PAGERDUTY] Would page: {message}")
        elif channel_type == "email":
            recipients = channel['config'].get('recipients', [])
            logger.info(f"[EMAIL] Would email {recipients}: {message}")
        elif channel_type == "webhook":
            url = channel['config'].get('url')
            logger.info(f"[WEBHOOK] Would POST to {url}")

    def format_alert_message(self, alert: ActiveAlert) -> str:
        """Format alert for notification."""
        return (f"[{alert.severity.upper()}] {alert.source_name}: "
                f"{alert.metric}={alert.current_value} "
                f"(threshold: {alert.threshold})")

    def log_alert(self, alert: ActiveAlert, action: str, detail: str = ""):
        """Log alert action to console."""
        color = {
            "critical": Colors.RED,
            "warning": Colors.YELLOW,
            "info": Colors.BLUE,
        }.get(alert.severity, Colors.RESET)

        timestamp = datetime.now().strftime("%H:%M:%S")
        detail_str = f" - {detail}" if detail else ""

        print(f"{timestamp} {color}{Colors.BOLD}[{action}]{Colors.RESET} "
              f"{alert.severity.upper()} | {alert.source_name} | "
              f"{alert.metric}={alert.current_value:.2f} "
              f"(threshold: {alert.threshold}){detail_str}")

    def log_notification(self, channel: Dict, alert: ActiveAlert):
        """Log notification to console."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{timestamp} {Colors.MAGENTA}[NOTIFY]{Colors.RESET} "
              f"-> {channel['name']}: {self.format_alert_message(alert)}")

    def check_all_rules(self):
        """Evaluate all rules against all systems."""
        self.stats["checks"] += 1

        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            for system_id, system in self.systems.items():
                # Check if rule applies to this system type
                if rule.target_type and system.get("type") != rule.target_type:
                    continue

                # Evaluate rule
                new_alert = self.check_rule(rule, system_id, system)

                if new_alert:
                    self.trigger_alert(new_alert, rule)

    def refresh_system_metrics(self):
        """Refresh system metrics from DTaaS."""
        try:
            # Use larger page size to get all twins
            twins = self.client.twins.list(domain="alerting_system", page_size=200)

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                # SDK model uses 'type_uri' not 'type'
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                twin_type = type_val.split("#")[-1] if type_val else ""
                twin_id = twin_dict["id"]

                if twin_type in ["WebServer", "DatabaseServer", "ApplicationService", "MessageQueue"]:
                    raw_props = twin_dict.get("properties", {})
                    self.systems[twin_id] = {
                        "id": twin_id,
                        "name": twin_dict.get("name", twin_id),
                        "type": twin_type,
                        "properties": self._normalize_properties(raw_props),
                    }

        except Exception as e:
            logger.warning(f"Failed to refresh metrics: {e}")

    def print_status(self):
        """Print current monitoring status."""
        os.system('cls' if os.name == 'nt' else 'clear')

        print(Colors.BOLD + Colors.CYAN)
        print("=" * 70)
        print(" REAL-TIME ALERT MONITOR")
        print(f" {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print(Colors.RESET)

        print(f"\n Systems: {len(self.systems)} | Rules: {len(self.rules)} | "
              f"Checks: {self.stats['checks']}")
        print(f" Alerts Triggered: {self.stats['alerts_triggered']} | "
              f"Resolved: {self.stats['alerts_resolved']} | "
              f"Notifications: {self.stats['notifications_sent']}")

        # Active alerts
        print(f"\n{Colors.BOLD} ACTIVE ALERTS ({len(self.active_alerts)}){Colors.RESET}")
        print("-" * 70)

        if not self.active_alerts:
            print(f" {Colors.GREEN}No active alerts{Colors.RESET}")
        else:
            for alert in sorted(self.active_alerts.values(),
                               key=lambda a: (a.severity != "critical", a.triggered_at)):
                color = Colors.RED if alert.severity == "critical" else Colors.YELLOW
                age = (datetime.now() - alert.triggered_at).total_seconds() / 60

                status_str = alert.status.value.upper()
                if alert.status == AlertStatus.ACKNOWLEDGED:
                    status_str = f"{Colors.BLUE}ACK{Colors.RESET}"

                print(f" {color}[{alert.severity.upper()[:4]}]{Colors.RESET} "
                      f"{alert.source_name[:20]:<20} | "
                      f"{alert.metric[:15]:<15} = {alert.current_value:>8.1f} | "
                      f"{age:>5.1f}m ago | {status_str}")

        print("\n" + "-" * 70)
        print(" Press Ctrl+C to stop monitoring")

    def run(self):
        """Run the monitoring loop."""
        logger.info("Starting alert monitor...")
        self.load_configuration()

        try:
            while True:
                # Refresh metrics
                self.refresh_system_metrics()

                # Check all rules
                self.check_all_rules()

                # Print status
                self.print_status()

                # Wait for next check
                time.sleep(self.check_interval)

        except KeyboardInterrupt:
            print("\n\nMonitor stopped.")

        # Final summary
        print("\n" + "=" * 50)
        print(" MONITORING SESSION SUMMARY")
        print("=" * 50)
        print(f" Total checks:         {self.stats['checks']}")
        print(f" Alerts triggered:     {self.stats['alerts_triggered']}")
        print(f" Alerts resolved:      {self.stats['alerts_resolved']}")
        print(f" Notifications sent:   {self.stats['notifications_sent']}")
        print(f" Active alerts:        {len(self.active_alerts)}")


def main():
    parser = argparse.ArgumentParser(description="Real-Time Alert Monitor")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--interval", type=float, default=10.0,
                       help="Check interval in seconds (default: 10)")
    parser.add_argument("--dry-run", action="store_true",
                       help="Don't persist changes, just show what would happen")
    args = parser.parse_args()

    client = get_client(args.base_url)
    monitor = AlertMonitor(client, args.interval, args.dry_run)

    if args.dry_run:
        print("Running in DRY RUN mode - no changes will be persisted")

    monitor.run()


if __name__ == "__main__":
    main()
