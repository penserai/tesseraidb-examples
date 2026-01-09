#!/usr/bin/env python3
"""
Real-Time Alerting System - Live Dashboard
===========================================

A rich terminal dashboard showing:
- System health overview with status indicators
- Active alerts with severity and age
- Metric trends for key systems
- Alert rule status and triggers

Usage:
    python dashboard.py [--base-url URL] [--refresh SECONDS]
"""

import sys
import os
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, List
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import get_client, logger


class Colors:
    """ANSI color codes."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"


def clear_screen():
    """Clear terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')


def create_bar(value: float, max_val: float, width: int = 20) -> str:
    """Create a colored progress bar."""
    if max_val <= 0:
        return " " * width

    ratio = min(1.0, max(0, value / max_val))
    filled = int(width * ratio)

    # Color based on percentage
    if ratio > 0.9:
        color = Colors.RED
    elif ratio > 0.7:
        color = Colors.YELLOW
    else:
        color = Colors.GREEN

    bar = color + "█" * filled + Colors.DIM + "░" * (width - filled) + Colors.RESET
    return bar


def format_age(dt: datetime) -> str:
    """Format age as human-readable string."""
    delta = datetime.now() - dt
    seconds = delta.total_seconds()

    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m"
    elif seconds < 86400:
        return f"{int(seconds/3600)}h"
    else:
        return f"{int(seconds/86400)}d"


class AlertDashboard:
    """Live alert monitoring dashboard."""

    def __init__(self, client, refresh_interval: float = 5.0):
        self.client = client
        self.refresh_interval = refresh_interval

        self.systems: Dict[str, Dict] = {}
        self.alerts: List[Dict] = []
        self.rules: Dict[str, Dict] = {}

        # History for sparklines
        self.metric_history: Dict[str, deque] = {}

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

    def refresh_data(self):
        """Refresh all data from DTaaS."""
        try:
            twins = self.client.twins.list(domain="alerting_system", page_size=200)

            self.systems = {}
            self.alerts = []
            self.rules = {}

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                # SDK model uses 'type_uri' not 'type'
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                twin_type = type_val.split("#")[-1] if type_val else ""
                twin_id = twin_dict["id"]
                raw_props = twin_dict.get("properties", {})
                props = self._normalize_properties(raw_props)

                if twin_type in ["WebServer", "DatabaseServer", "ApplicationService", "MessageQueue"]:
                    self.systems[twin_id] = {
                        "id": twin_id,
                        "name": twin_dict.get("name", twin_id),
                        "type": twin_type,
                        "properties": props,
                    }

                    # Track metric history
                    if twin_id not in self.metric_history:
                        self.metric_history[twin_id] = deque(maxlen=30)
                    self.metric_history[twin_id].append({
                        "cpu": props.get("cpuUsage", 0),
                        "mem": props.get("memoryUsage", 0),
                        "time": datetime.now(),
                    })

                elif twin_type == "Alert":
                    status = props.get("status", "")
                    if status in ["open", "acknowledged"]:
                        triggered_at = datetime.fromisoformat(props.get("triggeredAt", datetime.now().isoformat()))
                        self.alerts.append({
                            "id": twin_id,
                            "rule": props.get("ruleId", ""),
                            "source": props.get("sourceId", ""),
                            "severity": props.get("severity", "warning"),
                            "status": status,
                            "triggered_at": triggered_at,
                            "metric": props.get("metric", ""),
                            "value": props.get("currentValue", 0),
                            "threshold": props.get("threshold", 0),
                        })

                elif twin_type == "AlertRule":
                    self.rules[twin_id] = {
                        "id": twin_id,
                        "name": twin_dict.get("name", twin_id),
                        "metric": props.get("metric", ""),
                        "threshold": props.get("threshold", 0),
                        "severity": props.get("severity", "warning"),
                        "enabled": props.get("enabled", True),
                    }

        except Exception as e:
            logger.error(f"Failed to refresh data: {e}")

    def render_header(self, width: int):
        """Render dashboard header."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(Colors.BOLD + Colors.CYAN)
        print("╔" + "═" * (width - 2) + "╗")
        print("║" + " REAL-TIME ALERTING DASHBOARD ".center(width - 2) + "║")
        print("║" + f" {now} ".center(width - 2) + "║")
        print("╚" + "═" * (width - 2) + "╝")
        print(Colors.RESET)

    def render_summary(self):
        """Render summary statistics."""
        total_systems = len(self.systems)
        total_alerts = len(self.alerts)
        critical = sum(1 for a in self.alerts if a["severity"] == "critical")
        warning = sum(1 for a in self.alerts if a["severity"] == "warning")

        # System health
        healthy = 0
        degraded = 0
        unhealthy = 0

        for sys in self.systems.values():
            props = sys.get("properties", {})
            cpu = props.get("cpuUsage", 0)
            error_rate = props.get("errorRate", 0)

            if cpu > 90 or error_rate > 5:
                unhealthy += 1
            elif cpu > 70 or error_rate > 1:
                degraded += 1
            else:
                healthy += 1

        print(Colors.BOLD + " OVERVIEW" + Colors.RESET)
        print("─" * 60)

        # System status
        print(f" Systems: {Colors.GREEN}● {healthy} healthy{Colors.RESET}  "
              f"{Colors.YELLOW}● {degraded} degraded{Colors.RESET}  "
              f"{Colors.RED}● {unhealthy} unhealthy{Colors.RESET}")

        # Alert status
        if total_alerts == 0:
            print(f" Alerts:  {Colors.GREEN}✓ No active alerts{Colors.RESET}")
        else:
            print(f" Alerts:  {Colors.RED}● {critical} critical{Colors.RESET}  "
                  f"{Colors.YELLOW}● {warning} warning{Colors.RESET}")

    def render_systems(self):
        """Render system status table."""
        print(Colors.BOLD + "\n SYSTEM STATUS" + Colors.RESET)
        print("─" * 100)

        print(f" {'System':<25} {'Type':<15} {'CPU':>10} {'Memory':>12} "
              f"{'Errors':>8} {'Status':<12}")
        print("─" * 100)

        # Sort by health (worst first)
        sorted_systems = sorted(
            self.systems.values(),
            key=lambda s: -(s["properties"].get("cpuUsage", 0) +
                          s["properties"].get("errorRate", 0) * 10)
        )

        for sys in sorted_systems[:10]:
            props = sys.get("properties", {})
            cpu = props.get("cpuUsage", 0)
            mem = props.get("memoryUsage", 0)
            errors = props.get("errorRate", 0)

            # Status indicator
            if cpu > 90 or errors > 5:
                status = f"{Colors.RED}CRITICAL{Colors.RESET}"
            elif cpu > 70 or errors > 1:
                status = f"{Colors.YELLOW}WARNING{Colors.RESET}"
            else:
                status = f"{Colors.GREEN}HEALTHY{Colors.RESET}"

            cpu_bar = create_bar(cpu, 100, 10)
            mem_bar = create_bar(mem, 100, 10)

            print(f" {sys['name'][:25]:<25} {sys['type'][:15]:<15} "
                  f"{cpu_bar} {cpu:>4.0f}% {mem_bar} {mem:>4.0f}% "
                  f"{errors:>6.2f}% {status}")

    def render_alerts(self):
        """Render active alerts."""
        print(Colors.BOLD + "\n ACTIVE ALERTS" + Colors.RESET)
        print("─" * 100)

        if not self.alerts:
            print(f" {Colors.GREEN}✓ No active alerts{Colors.RESET}")
            return

        # Sort by severity and age
        sorted_alerts = sorted(
            self.alerts,
            key=lambda a: (a["severity"] != "critical", a["triggered_at"])
        )

        print(f" {'Severity':<10} {'Source':<25} {'Metric':<15} "
              f"{'Value':>10} {'Threshold':>10} {'Age':>8} {'Status':<12}")
        print("─" * 100)

        for alert in sorted_alerts[:8]:
            if alert["severity"] == "critical":
                sev_color = Colors.RED + Colors.BOLD
                sev_str = "CRITICAL"
            else:
                sev_color = Colors.YELLOW
                sev_str = "WARNING"

            status_str = alert["status"].upper()
            if alert["status"] == "acknowledged":
                status_str = f"{Colors.BLUE}ACK{Colors.RESET}"

            age = format_age(alert["triggered_at"])

            print(f" {sev_color}{sev_str:<10}{Colors.RESET} "
                  f"{alert['source'][:25]:<25} {alert['metric'][:15]:<15} "
                  f"{alert['value']:>10.2f} {alert['threshold']:>10.2f} "
                  f"{age:>8} {status_str}")

    def render_rules_status(self):
        """Render alert rules status."""
        print(Colors.BOLD + "\n ALERT RULES" + Colors.RESET)
        print("─" * 80)

        # Count triggered rules
        triggered_rules = set(a["rule"] for a in self.alerts)

        enabled = sum(1 for r in self.rules.values() if r.get("enabled"))
        triggered = len(triggered_rules)

        print(f" Total: {len(self.rules)} | Enabled: {enabled} | "
              f"Currently Triggered: {triggered}")

        if triggered > 0:
            print("\n Triggered Rules:")
            for rule_id in list(triggered_rules)[:5]:
                rule = self.rules.get(rule_id, {})
                print(f"   - {rule.get('name', rule_id)}")

    def render_footer(self, width: int):
        """Render dashboard footer."""
        print("\n" + "─" * width)
        print(f" Refresh: {self.refresh_interval}s | "
              f"Systems: {len(self.systems)} | "
              f"Rules: {len(self.rules)} | "
              f"Press Ctrl+C to exit")

    def render(self):
        """Render the complete dashboard."""
        clear_screen()
        width = 100

        self.render_header(width)
        self.render_summary()
        self.render_systems()
        self.render_alerts()
        self.render_rules_status()
        self.render_footer(width)

    def run(self):
        """Run the dashboard loop."""
        try:
            while True:
                self.refresh_data()
                self.render()
                time.sleep(self.refresh_interval)

        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")


def main():
    parser = argparse.ArgumentParser(description="Alert Dashboard")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--refresh", type=float, default=5.0,
                       help="Refresh interval in seconds (default: 5)")
    args = parser.parse_args()

    client = get_client(args.base_url)
    dashboard = AlertDashboard(client, args.refresh)

    print("Starting Alert Dashboard...")
    dashboard.run()


if __name__ == "__main__":
    main()
