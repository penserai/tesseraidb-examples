#!/usr/bin/env python3
"""
Finance Domain Digital Twin - Web UI
=====================================

Real-time financial monitoring dashboard showing:
- Trading desk P&L and exposure
- Portfolio performance and risk metrics
- Risk limits utilization
- Market data and instrument prices
- Counterparty exposure
- Compliance status

Usage:
    python web_ui.py [--port PORT] [--base-url URL]
"""

import sys
import os
import json
import asyncio
import argparse
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import get_client, logger

# Domain
DOMAIN = "finance"


def _normalize_properties(properties: dict) -> dict:
    """Normalize property names by stripping domain prefixes."""
    normalized = {}
    for key, value in properties.items():
        if '#' in key:
            short_key = key.split('#', 1)[1]
        else:
            short_key = key
        normalized[short_key] = value
    return normalized


class FinanceDataCollector:
    """Collects data from the finance digital twin."""

    def __init__(self, client):
        self.client = client

    def collect_data(self) -> dict:
        """Collect all finance data."""
        try:
            twins = self.client.twins.list(domain=DOMAIN, page_size=200)

            data = {
                "timestamp": datetime.now().isoformat(),
                "institution": None,
                "exchanges": [],
                "tradingDesks": [],
                "tradingSystems": [],
                "marketDataFeeds": [],
                "equities": [],
                "bonds": [],
                "derivatives": [],
                "cryptos": [],
                "portfolios": [],
                "positions": [],
                "counterparties": [],
                "riskLimits": [],
                "riskMetrics": [],
                "riskAlerts": [],
                "complianceRules": [],
                "clearingHouses": [],
                "stats": {
                    "totalAUM": 0,
                    "totalPnL": 0,
                    "activeAlerts": 0,
                    "limitsBreached": 0,
                    "systemsOnline": 0,
                    "feedsConnected": 0
                }
            }

            for twin in twins:
                twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
                type_val = twin_dict.get("type_uri") or twin_dict.get("type") or ""
                twin_type = type_val.split("#")[-1] if type_val else ""
                twin_id = twin_dict["id"]
                raw_props = twin_dict.get("properties", {})
                props = _normalize_properties(raw_props)

                item = {
                    "id": twin_id,
                    "name": twin_dict.get("name", twin_id),
                    "type": twin_type,
                    "properties": props
                }

                if twin_type == "FinancialInstitution":
                    data["institution"] = item
                elif twin_type == "Exchange":
                    data["exchanges"].append(item)
                elif twin_type == "TradingDesk":
                    data["tradingDesks"].append(item)
                    data["stats"]["totalPnL"] += props.get("pnlMTD", 0)
                elif twin_type in ["OrderManagementSystem", "TradingSystem"]:
                    data["tradingSystems"].append(item)
                    if props.get("status") == "running":
                        data["stats"]["systemsOnline"] += 1
                elif twin_type == "MarketDataFeed":
                    data["marketDataFeeds"].append(item)
                    if props.get("status") == "connected":
                        data["stats"]["feedsConnected"] += 1
                elif twin_type == "Equity":
                    data["equities"].append(item)
                elif twin_type == "Bond":
                    data["bonds"].append(item)
                elif twin_type in ["Option", "Future"]:
                    data["derivatives"].append(item)
                elif twin_type == "Cryptocurrency":
                    data["cryptos"].append(item)
                elif twin_type == "Portfolio":
                    data["portfolios"].append(item)
                    data["stats"]["totalAUM"] += props.get("assetsUnderManagement", 0)
                elif twin_type == "Position":
                    data["positions"].append(item)
                elif twin_type == "Counterparty":
                    data["counterparties"].append(item)
                elif twin_type == "RiskLimit":
                    data["riskLimits"].append(item)
                    if props.get("status") == "critical":
                        data["stats"]["limitsBreached"] += 1
                elif twin_type in ["RiskMetric", "VaRMetric"]:
                    data["riskMetrics"].append(item)
                elif twin_type == "RiskAlert":
                    data["riskAlerts"].append(item)
                    if props.get("status") == "active":
                        data["stats"]["activeAlerts"] += 1
                elif twin_type == "ComplianceRule":
                    data["complianceRules"].append(item)
                elif twin_type == "ClearingHouse":
                    data["clearingHouses"].append(item)

            return data

        except Exception as e:
            logger.error(f"Failed to collect data: {e}")
            return {"error": str(e), "timestamp": datetime.now().isoformat()}


HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Finance Digital Twin - GlobalCapital Investment Bank</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #0a0f1c 0%, #1a1f3c 50%, #0d1220 100%);
            min-height: 100vh;
            color: #e2e8f0;
            padding: 20px;
        }

        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 20px;
            background: linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(59, 130, 246, 0.1));
            border-radius: 16px;
            border: 1px solid rgba(34, 197, 94, 0.2);
        }

        .header h1 {
            font-size: 2em;
            color: #34d399;
            margin-bottom: 5px;
        }

        .header .subtitle {
            color: #94a3b8;
            font-size: 0.95em;
        }

        .stats-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9));
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            border: 1px solid rgba(34, 197, 94, 0.2);
        }

        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #34d399;
        }

        .stat-value.warning { color: #fbbf24; }
        .stat-value.critical { color: #ef4444; }
        .stat-value.positive { color: #22c55e; }
        .stat-value.negative { color: #ef4444; }

        .stat-label {
            color: #94a3b8;
            font-size: 0.85em;
            margin-top: 5px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .panel {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.8));
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(34, 197, 94, 0.15);
        }

        .panel h2 {
            color: #34d399;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 1.1em;
        }

        /* Trading Desks */
        .desk-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 12px;
        }

        .desk-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 15px;
            border-left: 4px solid #3b82f6;
        }

        .desk-card.positive { border-left-color: #22c55e; }
        .desk-card.negative { border-left-color: #ef4444; }

        .desk-name {
            font-weight: 600;
            margin-bottom: 5px;
            font-size: 0.9em;
        }

        .desk-asset-class {
            font-size: 0.75em;
            color: #64748b;
            margin-bottom: 10px;
        }

        .desk-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 0.8em;
        }

        .desk-metric {
            display: flex;
            justify-content: space-between;
        }

        .metric-label { color: #64748b; }
        .metric-value.positive { color: #22c55e; }
        .metric-value.negative { color: #ef4444; }

        /* Risk Limits */
        .limit-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .limit-item {
            background: rgba(15, 23, 42, 0.5);
            border-radius: 10px;
            padding: 12px;
        }

        .limit-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .limit-name {
            font-weight: 500;
            font-size: 0.9em;
        }

        .limit-status {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.7em;
            font-weight: 600;
            text-transform: uppercase;
        }

        .limit-status.normal { background: rgba(34, 197, 94, 0.2); color: #34d399; }
        .limit-status.warning { background: rgba(234, 179, 8, 0.2); color: #fbbf24; }
        .limit-status.critical { background: rgba(239, 68, 68, 0.2); color: #f87171; }

        .limit-bar {
            height: 8px;
            background: rgba(51, 65, 85, 0.5);
            border-radius: 4px;
            overflow: hidden;
        }

        .limit-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }

        .limit-fill.low { background: linear-gradient(90deg, #22c55e, #16a34a); }
        .limit-fill.medium { background: linear-gradient(90deg, #eab308, #ca8a04); }
        .limit-fill.high { background: linear-gradient(90deg, #ef4444, #dc2626); }

        .limit-values {
            display: flex;
            justify-content: space-between;
            font-size: 0.75em;
            color: #64748b;
            margin-top: 4px;
        }

        /* Portfolios */
        .portfolio-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
        }

        .portfolio-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
            border: 1px solid rgba(59, 130, 246, 0.2);
        }

        .portfolio-name {
            font-weight: 600;
            font-size: 0.85em;
            margin-bottom: 8px;
        }

        .portfolio-aum {
            font-size: 1.2em;
            font-weight: bold;
            color: #60a5fa;
            margin-bottom: 5px;
        }

        .portfolio-stats {
            display: flex;
            justify-content: space-between;
            font-size: 0.75em;
        }

        /* Market Data - Stock Ticker Style */
        .ticker-container {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }

        .ticker-item {
            background: rgba(15, 23, 42, 0.7);
            border-radius: 8px;
            padding: 10px 14px;
            min-width: 100px;
            border: 1px solid rgba(100, 116, 139, 0.2);
        }

        .ticker-symbol {
            font-weight: bold;
            font-size: 0.9em;
            margin-bottom: 4px;
        }

        .ticker-price {
            font-size: 1.1em;
            font-weight: 600;
        }

        .ticker-price.up { color: #22c55e; }
        .ticker-price.down { color: #ef4444; }

        /* Trading Systems */
        .system-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 10px;
        }

        .system-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 10px;
            padding: 12px;
            border-left: 3px solid #22c55e;
        }

        .system-card.offline {
            border-left-color: #ef4444;
            opacity: 0.7;
        }

        .system-name {
            font-weight: 500;
            font-size: 0.85em;
            margin-bottom: 5px;
        }

        .system-status {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.7em;
            margin-bottom: 8px;
        }

        .system-status.running { background: rgba(34, 197, 94, 0.2); color: #34d399; }
        .system-status.stopped { background: rgba(239, 68, 68, 0.2); color: #f87171; }

        .system-metrics {
            font-size: 0.75em;
            color: #94a3b8;
        }

        /* Counterparties */
        .cp-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .cp-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(15, 23, 42, 0.5);
            padding: 10px 12px;
            border-radius: 8px;
        }

        .cp-name {
            font-weight: 500;
            font-size: 0.9em;
        }

        .cp-exposure {
            text-align: right;
        }

        .cp-amount {
            font-weight: 600;
            font-size: 0.9em;
        }

        .cp-util {
            font-size: 0.7em;
            color: #64748b;
        }

        /* Risk Alerts */
        .alert-list {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .alert-item {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 8px;
            padding: 12px;
            animation: pulse-alert 2s infinite;
        }

        .alert-item.warning {
            background: rgba(234, 179, 8, 0.1);
            border-color: rgba(234, 179, 8, 0.3);
        }

        @keyframes pulse-alert {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        .alert-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
        }

        .alert-name {
            font-weight: 600;
            font-size: 0.9em;
            color: #f87171;
        }

        .alert-item.warning .alert-name { color: #fbbf24; }

        .alert-severity {
            font-size: 0.7em;
            text-transform: uppercase;
            font-weight: 600;
        }

        .alert-message {
            font-size: 0.8em;
            color: #94a3b8;
        }

        /* Compliance */
        .compliance-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 10px;
        }

        .compliance-card {
            background: rgba(15, 23, 42, 0.6);
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }

        .compliance-icon {
            font-size: 1.5em;
            margin-bottom: 5px;
        }

        .compliance-name {
            font-size: 0.8em;
            font-weight: 500;
            margin-bottom: 4px;
        }

        .compliance-status {
            font-size: 0.7em;
            padding: 2px 8px;
            border-radius: 10px;
            display: inline-block;
        }

        .compliance-status.compliant { background: rgba(34, 197, 94, 0.2); color: #34d399; }
        .compliance-status.non-compliant { background: rgba(239, 68, 68, 0.2); color: #f87171; }

        /* Connection Status */
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }

        .connection-status.connected {
            background: rgba(34, 197, 94, 0.2);
            color: #34d399;
            border: 1px solid rgba(34, 197, 94, 0.3);
        }

        .connection-status.disconnected {
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .timestamp {
            text-align: center;
            color: #64748b;
            font-size: 0.85em;
            margin-top: 20px;
        }

        .no-alerts {
            text-align: center;
            color: #34d399;
            padding: 20px;
        }
    </style>
</head>
<body>
    <div id="connection-status" class="connection-status disconnected">Connecting...</div>

    <div class="header">
        <h1>GlobalCapital Investment Bank</h1>
        <div class="subtitle">Finance Digital Twin - Real-Time Risk & Trading Dashboard</div>
    </div>

    <div class="stats-bar" id="stats-bar">
        <div class="stat-card">
            <div class="stat-value" id="total-aum">-</div>
            <div class="stat-label">Total AUM</div>
        </div>
        <div class="stat-card">
            <div class="stat-value positive" id="total-pnl">-</div>
            <div class="stat-label">MTD P&L</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="systems-online">-</div>
            <div class="stat-label">Systems Online</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="feeds-connected">-</div>
            <div class="stat-label">Data Feeds</div>
        </div>
        <div class="stat-card">
            <div class="stat-value warning" id="active-alerts">-</div>
            <div class="stat-label">Active Alerts</div>
        </div>
        <div class="stat-card">
            <div class="stat-value critical" id="limits-breached">-</div>
            <div class="stat-label">Limits Breached</div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Trading Desks</h2>
            <div class="desk-grid" id="trading-desks"></div>
        </div>

        <div class="panel">
            <h2>Risk Limits</h2>
            <div class="limit-list" id="risk-limits"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Market Data - Equities</h2>
            <div class="ticker-container" id="equities"></div>
        </div>

        <div class="panel">
            <h2>Digital Assets</h2>
            <div class="ticker-container" id="cryptos"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Portfolios</h2>
            <div class="portfolio-grid" id="portfolios"></div>
        </div>

        <div class="panel">
            <h2>Trading Systems</h2>
            <div class="system-grid" id="trading-systems"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Risk Alerts</h2>
            <div class="alert-list" id="risk-alerts"></div>
        </div>

        <div class="panel">
            <h2>Counterparty Exposure</h2>
            <div class="cp-list" id="counterparties"></div>
        </div>
    </div>

    <div class="grid">
        <div class="panel">
            <h2>Compliance Status</h2>
            <div class="compliance-grid" id="compliance"></div>
        </div>
    </div>

    <div class="timestamp" id="timestamp">Waiting for data...</div>

    <script>
        let ws;
        let reconnectInterval;

        function formatCurrency(value, short = false) {
            if (value === undefined || value === null) return '-';
            const absVal = Math.abs(value);
            if (short) {
                if (absVal >= 1e9) return (value / 1e9).toFixed(1) + 'B';
                if (absVal >= 1e6) return (value / 1e6).toFixed(1) + 'M';
                if (absVal >= 1e3) return (value / 1e3).toFixed(1) + 'K';
            }
            return '$' + value.toLocaleString();
        }

        function connect() {
            const wsUrl = `ws://${window.location.hostname}:${parseInt(window.location.port) + 1}`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                document.getElementById('connection-status').className = 'connection-status connected';
                document.getElementById('connection-status').textContent = 'Connected';
                if (reconnectInterval) {
                    clearInterval(reconnectInterval);
                    reconnectInterval = null;
                }
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };

            ws.onclose = () => {
                document.getElementById('connection-status').className = 'connection-status disconnected';
                document.getElementById('connection-status').textContent = 'Disconnected';
                if (!reconnectInterval) {
                    reconnectInterval = setInterval(connect, 3000);
                }
            };

            ws.onerror = () => ws.close();
        }

        function updateDashboard(data) {
            if (data.error) {
                document.getElementById('timestamp').textContent = `Error: ${data.error}`;
                return;
            }

            // Stats
            const stats = data.stats || {};
            document.getElementById('total-aum').textContent = '$' + formatCurrency(stats.totalAUM, true).replace('$', '');
            document.getElementById('total-pnl').textContent = '$' + formatCurrency(stats.totalPnL, true).replace('$', '');
            document.getElementById('total-pnl').className = 'stat-value ' + (stats.totalPnL >= 0 ? 'positive' : 'negative');
            document.getElementById('systems-online').textContent = stats.systemsOnline || 0;
            document.getElementById('feeds-connected').textContent = stats.feedsConnected || 0;
            document.getElementById('active-alerts').textContent = stats.activeAlerts || 0;
            document.getElementById('limits-breached').textContent = stats.limitsBreached || 0;

            // Trading Desks
            const deskContainer = document.getElementById('trading-desks');
            deskContainer.innerHTML = (data.tradingDesks || []).map(desk => {
                const props = desk.properties || {};
                const pnl = props.pnlMTD || 0;
                const cardClass = pnl >= 0 ? 'positive' : 'negative';
                return `
                    <div class="desk-card ${cardClass}">
                        <div class="desk-name">${desk.name}</div>
                        <div class="desk-asset-class">${props.assetClass || ''}</div>
                        <div class="desk-metrics">
                            <div class="desk-metric">
                                <span class="metric-label">P&L MTD</span>
                                <span class="metric-value ${pnl >= 0 ? 'positive' : 'negative'}">$${formatCurrency(pnl, true).replace('$', '')}</span>
                            </div>
                            <div class="desk-metric">
                                <span class="metric-label">Exposure</span>
                                <span class="metric-value">$${formatCurrency(props.currentExposure, true).replace('$', '')}</span>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // Risk Limits
            const limitContainer = document.getElementById('risk-limits');
            limitContainer.innerHTML = (data.riskLimits || []).map(limit => {
                const props = limit.properties || {};
                const util = props.utilizationPercent || 0;
                const status = props.status || 'normal';
                const fillClass = util > 90 ? 'high' : util > 75 ? 'medium' : 'low';
                return `
                    <div class="limit-item">
                        <div class="limit-header">
                            <span class="limit-name">${limit.name}</span>
                            <span class="limit-status ${status}">${status}</span>
                        </div>
                        <div class="limit-bar">
                            <div class="limit-fill ${fillClass}" style="width: ${util}%"></div>
                        </div>
                        <div class="limit-values">
                            <span>${util.toFixed(1)}% utilized</span>
                            <span>Limit: $${formatCurrency(props.limitAmount, true).replace('$', '')}</span>
                        </div>
                    </div>
                `;
            }).join('');

            // Equities
            const equityContainer = document.getElementById('equities');
            equityContainer.innerHTML = (data.equities || []).map(eq => {
                const props = eq.properties || {};
                const change = Math.random() > 0.5 ? 'up' : 'down'; // Simulated for demo
                return `
                    <div class="ticker-item">
                        <div class="ticker-symbol">${props.ticker || eq.id}</div>
                        <div class="ticker-price ${change}">$${(props.price || 0).toFixed(2)}</div>
                    </div>
                `;
            }).join('');

            // Cryptos
            const cryptoContainer = document.getElementById('cryptos');
            cryptoContainer.innerHTML = (data.cryptos || []).map(crypto => {
                const props = crypto.properties || {};
                return `
                    <div class="ticker-item">
                        <div class="ticker-symbol">${props.ticker || crypto.name}</div>
                        <div class="ticker-price">$${(props.price || 0).toLocaleString()}</div>
                    </div>
                `;
            }).join('');

            // Portfolios
            const portfolioContainer = document.getElementById('portfolios');
            portfolioContainer.innerHTML = (data.portfolios || []).map(pf => {
                const props = pf.properties || {};
                return `
                    <div class="portfolio-card">
                        <div class="portfolio-name">${pf.name}</div>
                        <div class="portfolio-aum">$${formatCurrency(props.assetsUnderManagement, true).replace('$', '')}</div>
                        <div class="portfolio-stats">
                            <span>YTD: ${(props.returnYTD || 0).toFixed(1)}%</span>
                            <span>Sharpe: ${(props.sharpeRatio || 0).toFixed(2)}</span>
                        </div>
                    </div>
                `;
            }).join('');

            // Trading Systems
            const systemContainer = document.getElementById('trading-systems');
            systemContainer.innerHTML = (data.tradingSystems || []).map(sys => {
                const props = sys.properties || {};
                const isRunning = props.status === 'running';
                return `
                    <div class="system-card ${isRunning ? '' : 'offline'}">
                        <div class="system-name">${sys.name}</div>
                        <span class="system-status ${props.status || ''}">${props.status || 'unknown'}</span>
                        <div class="system-metrics">
                            Uptime: ${(props.uptime || 0).toFixed(2)}%<br>
                            Latency: ${props.latencyP99 || 0}ms
                        </div>
                    </div>
                `;
            }).join('');

            // Risk Alerts
            const alertContainer = document.getElementById('risk-alerts');
            const activeAlerts = (data.riskAlerts || []).filter(a => a.properties?.status === 'active');
            if (activeAlerts.length === 0) {
                alertContainer.innerHTML = '<div class="no-alerts">No active alerts</div>';
            } else {
                alertContainer.innerHTML = activeAlerts.map(alert => {
                    const props = alert.properties || {};
                    const sevClass = props.severity === 'critical' ? '' : 'warning';
                    return `
                        <div class="alert-item ${sevClass}">
                            <div class="alert-header">
                                <span class="alert-name">${alert.name}</span>
                                <span class="alert-severity">${props.severity || 'warning'}</span>
                            </div>
                            <div class="alert-message">${props.message || ''}</div>
                        </div>
                    `;
                }).join('');
            }

            // Counterparties
            const cpContainer = document.getElementById('counterparties');
            cpContainer.innerHTML = (data.counterparties || []).map(cp => {
                const props = cp.properties || {};
                return `
                    <div class="cp-item">
                        <div class="cp-name">${cp.name}</div>
                        <div class="cp-exposure">
                            <div class="cp-amount">$${formatCurrency(props.currentExposure, true).replace('$', '')}</div>
                            <div class="cp-util">${props.utilizationPct || 0}% of limit</div>
                        </div>
                    </div>
                `;
            }).join('');

            // Compliance
            const compContainer = document.getElementById('compliance');
            compContainer.innerHTML = (data.complianceRules || []).map(rule => {
                const props = rule.properties || {};
                const isCompliant = props.status === 'compliant';
                return `
                    <div class="compliance-card">
                        <div class="compliance-icon">${isCompliant ? '✓' : '✗'}</div>
                        <div class="compliance-name">${rule.name.replace(' Compliance', '').replace(' Requirements', '')}</div>
                        <span class="compliance-status ${isCompliant ? 'compliant' : 'non-compliant'}">${props.status || 'unknown'}</span>
                    </div>
                `;
            }).join('');

            // Timestamp
            document.getElementById('timestamp').textContent =
                `Last updated: ${new Date(data.timestamp).toLocaleString()}`;
        }

        connect();
    </script>
</body>
</html>
"""


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for the dashboard."""

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Suppress logging


async def websocket_handler(websocket, collector):
    """Handle WebSocket connections."""
    logger.info(f"Client connected: {websocket.remote_address}")
    try:
        while True:
            data = collector.collect_data()
            await websocket.send(json.dumps(data))
            await asyncio.sleep(5)
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {websocket.remote_address}")


async def start_websocket_server(port: int, collector: FinanceDataCollector):
    """Start the WebSocket server."""
    async with websockets.serve(
        lambda ws: websocket_handler(ws, collector),
        "0.0.0.0",
        port
    ):
        logger.info(f"WebSocket server started on port {port}")
        await asyncio.Future()


def run_http_server(port: int):
    """Run the HTTP server."""
    server = HTTPServer(('0.0.0.0', port), DashboardHandler)
    logger.info(f"HTTP server started on port {port}")
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Finance Digital Twin Web UI")
    parser.add_argument("--port", type=int, default=8106, help="HTTP server port")
    parser.add_argument("--base-url", help="DTaaS server URL")
    args = parser.parse_args()

    client = get_client(args.base_url)
    collector = FinanceDataCollector(client)

    # Start HTTP server in a thread
    http_thread = threading.Thread(target=run_http_server, args=(args.port,), daemon=True)
    http_thread.start()

    print(f"\n{'='*60}")
    print(f"  Finance Digital Twin - Web UI")
    print(f"  Open http://localhost:{args.port} in your browser")
    print(f"{'='*60}\n")

    # Run WebSocket server
    asyncio.run(start_websocket_server(args.port + 1, collector))


if __name__ == "__main__":
    main()
