"""
Real-Time Alerting System Example for TesserAI DB

This example demonstrates production-grade alerting capabilities:
- Configurable alert rules with thresholds and conditions
- Multi-severity alert classification
- Alert lifecycle management (open, acknowledged, resolved)
- Notification channels (console, webhook, log)
- Alert aggregation and deduplication
- Escalation policies

This proves TesserAI's production readiness for real-time monitoring use cases.

Modules:
    seed.py - Creates alert rules, thresholds, and notification channels
    monitor.py - Real-time monitoring daemon with alert detection
    simulator.py - Generates realistic metric data with anomalies
    dashboard.py - Live alert dashboard with status overview
"""

__all__ = ["seed", "monitor", "simulator", "dashboard"]
