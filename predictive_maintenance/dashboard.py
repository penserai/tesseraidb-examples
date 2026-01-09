#!/usr/bin/env python3
"""
Predictive Maintenance - Real-Time Terminal Dashboard
======================================================

A rich terminal-based dashboard that displays:
- Fleet health overview with live updates
- Equipment status with color-coded alerts
- Trending graphs using ASCII art
- Failure predictions and maintenance alerts

Usage:
    python dashboard.py [--base-url URL] [--refresh SECONDS]
"""

import sys
import os
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import get_client, logger


# ANSI color codes for terminal
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def color_by_health(health: float) -> str:
    """Get color code based on health score."""
    if health < 20:
        return Colors.RED
    elif health < 50:
        return Colors.YELLOW
    elif health < 75:
        return Colors.CYAN
    else:
        return Colors.GREEN


def create_bar(value: float, max_value: float, width: int = 20) -> str:
    """Create an ASCII progress bar."""
    if max_value <= 0:
        return " " * width

    ratio = min(1.0, max(0, value / max_value))
    filled = int(width * ratio)
    empty = width - filled

    color = color_by_health(value if max_value == 100 else ratio * 100)

    bar = color + "█" * filled + Colors.DIM + "░" * empty + Colors.RESET
    return bar


def create_sparkline(values: List[float], width: int = 20) -> str:
    """Create an ASCII sparkline chart."""
    if not values:
        return " " * width

    # Use last 'width' values
    values = list(values)[-width:]

    if len(values) < width:
        values = [values[0]] * (width - len(values)) + values

    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return "▄" * width

    # Sparkline characters (8 levels)
    chars = "▁▂▃▄▅▆▇█"

    sparkline = ""
    for v in values:
        idx = int((v - min_val) / (max_val - min_val) * 7)
        idx = max(0, min(7, idx))
        sparkline += chars[idx]

    return sparkline


class Dashboard:
    """Real-time predictive maintenance dashboard."""

    def __init__(self, client, refresh_interval: float = 5.0):
        self.client = client
        self.refresh_interval = refresh_interval
        self.health_history: Dict[str, deque] = {}
        self.alerts: deque = deque(maxlen=10)
        self.running = False

    def _normalize_properties(self, properties: Dict) -> Dict:
        """Normalize property names by stripping domain prefixes."""
        normalized = {}
        for key, value in properties.items():
            if '#' in key:
                short_key = key.split('#', 1)[1]
            else:
                short_key = key
            normalized[short_key] = value
        return normalized

    def get_equipment_data(self) -> List[Dict]:
        """Fetch current equipment data."""
        try:
            twins = self.client.twins.list(domain="predictive_maintenance", page_size=200)
            equipment = []

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                raw_props = twin_dict.get("properties", {})
                props = self._normalize_properties(raw_props)

                if "healthScore" not in props:
                    continue

                eq_id = twin_dict["id"]

                # Track history
                if eq_id not in self.health_history:
                    self.health_history[eq_id] = deque(maxlen=60)
                self.health_history[eq_id].append(props.get("healthScore", 0))

                # SDK model uses 'type_uri' not 'type'
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                equipment.append({
                    "id": eq_id,
                    "name": twin_dict.get("name", eq_id),
                    "type": type_val.split("#")[-1] if type_val else "",
                    "health": props.get("healthScore", 0),
                    "rul": props.get("remainingUsefulLife", 0),
                    "vibration": props.get("currentVibration", 0),
                    "temperature": props.get("currentTemperature", 0),
                    "anomaly": props.get("anomalyScore", 0),
                    "status": props.get("status", "unknown"),
                    "criticality": props.get("criticality", "medium"),
                    "history": list(self.health_history[eq_id]),
                })

            return sorted(equipment, key=lambda x: x["health"])

        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return []

    def check_alerts(self, equipment: List[Dict]):
        """Check for new alert conditions."""
        for eq in equipment:
            # Critical health alert
            if eq["health"] < 20:
                alert = {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "type": "CRITICAL",
                    "equipment": eq["id"],
                    "message": f"Health critical: {eq['health']:.1f}%"
                }
                if not any(a["equipment"] == eq["id"] and a["type"] == "CRITICAL"
                          for a in self.alerts):
                    self.alerts.append(alert)

            # Failure imminent
            if eq["rul"] < 100:
                alert = {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "type": "FAILURE",
                    "equipment": eq["id"],
                    "message": f"Failure imminent: RUL={eq['rul']:.0f}h"
                }
                if not any(a["equipment"] == eq["id"] and a["type"] == "FAILURE"
                          for a in self.alerts):
                    self.alerts.append(alert)

            # High anomaly score
            if eq["anomaly"] > 0.7:
                alert = {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "type": "ANOMALY",
                    "equipment": eq["id"],
                    "message": f"Anomaly detected: {eq['anomaly']:.2f}"
                }
                if not any(a["equipment"] == eq["id"] and a["type"] == "ANOMALY"
                          for a in self.alerts):
                    self.alerts.append(alert)

    def render(self, equipment: List[Dict]):
        """Render the dashboard."""
        clear_screen()

        width = 120
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Header
        print(Colors.BOLD + Colors.CYAN)
        print("╔" + "═" * (width - 2) + "╗")
        print("║" + " PREDICTIVE MAINTENANCE DASHBOARD ".center(width - 2) + "║")
        print("║" + f" {now} ".center(width - 2) + "║")
        print("╚" + "═" * (width - 2) + "╝")
        print(Colors.RESET)

        # Summary statistics
        total = len(equipment)
        if total == 0:
            print("\nNo equipment data found. Run seed.py first.")
            return

        critical = sum(1 for e in equipment if e["health"] < 20)
        warning = sum(1 for e in equipment if 20 <= e["health"] < 50)
        degraded = sum(1 for e in equipment if 50 <= e["health"] < 75)
        healthy = sum(1 for e in equipment if e["health"] >= 75)

        avg_health = sum(e["health"] for e in equipment) / total
        avg_rul = sum(e["rul"] for e in equipment) / total

        print(Colors.BOLD + "\n FLEET OVERVIEW" + Colors.RESET)
        print("─" * width)

        # Fleet health bar
        fleet_bar = create_bar(avg_health, 100, 40)
        print(f" Fleet Health: {fleet_bar} {avg_health:.1f}%")
        print(f" Avg RUL: {avg_rul:,.0f} hours")
        print()

        # Status boxes
        print(f" {Colors.GREEN}▓ Healthy: {healthy:3d}{Colors.RESET}  "
              f" {Colors.CYAN}▓ Degraded: {degraded:3d}{Colors.RESET}  "
              f" {Colors.YELLOW}▓ Warning: {warning:3d}{Colors.RESET}  "
              f" {Colors.RED}▓ Critical: {critical:3d}{Colors.RESET}")

        # Equipment table
        print(Colors.BOLD + "\n EQUIPMENT STATUS (Top 15 by Priority)" + Colors.RESET)
        print("─" * width)

        header = (f"{'Status':<8} {'Equipment ID':<30} {'Type':<18} "
                 f"{'Health':>8} {'RUL(h)':>8} {'Vib':>6} {'Temp':>6} "
                 f"{'Trend':<20}")
        print(Colors.BOLD + header + Colors.RESET)
        print("─" * width)

        for eq in equipment[:15]:
            # Status indicator
            if eq["health"] < 20:
                status = Colors.RED + "CRITICAL" + Colors.RESET
            elif eq["health"] < 50:
                status = Colors.YELLOW + "WARNING " + Colors.RESET
            elif eq["health"] < 75:
                status = Colors.CYAN + "DEGRADED" + Colors.RESET
            else:
                status = Colors.GREEN + "HEALTHY " + Colors.RESET

            # Color code health
            health_color = color_by_health(eq["health"])
            health_str = f"{health_color}{eq['health']:>6.1f}%{Colors.RESET}"

            # Trend sparkline
            trend = create_sparkline(eq["history"], 20)
            trend_color = Colors.GREEN if eq["history"][-1] >= eq["history"][0] else Colors.RED
            trend_str = trend_color + trend + Colors.RESET

            print(f" {status} {eq['id'][:28]:<30} {eq['type'][:18]:<18} "
                  f"{health_str} {eq['rul']:>7.0f} {eq['vibration']:>5.2f} "
                  f"{eq['temperature']:>5.1f} {trend_str}")

        # Alerts section
        if self.alerts:
            print(Colors.BOLD + "\n RECENT ALERTS" + Colors.RESET)
            print("─" * width)

            for alert in list(self.alerts)[-5:]:
                if alert["type"] == "CRITICAL":
                    color = Colors.RED
                elif alert["type"] == "FAILURE":
                    color = Colors.RED + Colors.BOLD
                else:
                    color = Colors.YELLOW

                print(f" {color}[{alert['time']}] {alert['type']}: "
                      f"{alert['equipment'][:25]} - {alert['message']}{Colors.RESET}")

        # Predictions section
        print(Colors.BOLD + "\n FAILURE PREDICTIONS (Next 7 Days)" + Colors.RESET)
        print("─" * width)

        # Find equipment likely to fail soon
        at_risk = [e for e in equipment if e["rul"] < 168]  # 168 hours = 7 days
        if at_risk:
            for eq in at_risk[:5]:
                days_left = eq["rul"] / 24
                urgency = Colors.RED if days_left < 2 else Colors.YELLOW

                bar = create_bar(eq["rul"], 168, 15)
                print(f" {urgency}► {eq['id'][:25]:<25} "
                      f"RUL: {eq['rul']:>5.0f}h ({days_left:.1f} days) {bar}{Colors.RESET}")
        else:
            print(f" {Colors.GREEN}✓ No imminent failures predicted{Colors.RESET}")

        # Footer
        print("\n" + "─" * width)
        print(f" Press Ctrl+C to exit | Refresh: {self.refresh_interval}s | "
              f"Equipment: {total}")

    def run(self):
        """Run the dashboard continuously."""
        self.running = True

        try:
            while self.running:
                equipment = self.get_equipment_data()
                self.check_alerts(equipment)
                self.render(equipment)

                time.sleep(self.refresh_interval)

        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")
            self.running = False


def main():
    parser = argparse.ArgumentParser(description="Predictive Maintenance Dashboard")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--refresh", type=float, default=5.0,
                       help="Refresh interval in seconds (default: 5)")
    args = parser.parse_args()

    client = get_client(args.base_url)
    dashboard = Dashboard(client, args.refresh)

    print("Starting Predictive Maintenance Dashboard...")
    print("Connecting to DTaaS server...")

    dashboard.run()


if __name__ == "__main__":
    main()
