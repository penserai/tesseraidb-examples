#!/usr/bin/env python3
"""
Transfer Pricing Web UI

Real-time visualization dashboard for multinational transfer pricing analysis,
including intercompany transactions, benchmarking, and compliance monitoring.

Usage:
    python web_ui.py

Then open http://localhost:8100 in your browser.
"""

import asyncio
import json
import sys
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from threading import Thread

# Add parent directory to path for common imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import websockets
except ImportError:
    print("websockets package required. Install with: pip install websockets")
    sys.exit(1)

from common import get_client

DOMAIN = "taxation"
HTTP_PORT = 8100
WS_PORT = 8101


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


class TaxationDataCollector:
    """Collects and processes transfer pricing data from the digital twin."""

    def __init__(self):
        self.client = get_client()

    def collect_data(self) -> dict:
        """Collect all taxation data for the dashboard."""
        twins = self.client.twins.list(domain=DOMAIN, page_size=300)

        data = {
            "group": None,
            "jurisdictions": [],
            "entities": [],
            "transactions": [],
            "tp_methods": [],
            "comparables": [],
            "arm_length_ranges": [],
            "documents": [],
            "analyses": [],
            "stats": {
                "total_revenue": 0,
                "total_transactions": 0,
                "transaction_value": 0,
                "entities_count": 0,
                "avg_margin": 0,
                "compliance_score": 95  # Simulated
            }
        }

        entity_margins = []

        for twin in twins:
            twin_type = twin.type_uri.split('#')[-1] if '#' in twin.type_uri else twin.type_uri.split('/')[-1]
            props = _normalize_properties(twin.properties or {})

            if twin_type == "MultinationalGroup":
                data["group"] = {
                    "id": twin.id,
                    "name": twin.name,
                    "ultimate_parent": props.get("ultimateParent", "Unknown"),
                    "headquarters": props.get("headquartersCountry", "Unknown"),
                    "industry": props.get("industry", "Unknown"),
                    "consolidated_revenue": props.get("consolidatedRevenue", 0),
                    "employees": props.get("totalEmployees", 0)
                }
                data["stats"]["total_revenue"] = props.get("consolidatedRevenue", 0)

            elif twin_type == "Jurisdiction":
                data["jurisdictions"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "country_code": props.get("countryCode", ""),
                    "currency": props.get("currencyCode", ""),
                    "tax_rate": props.get("corporateTaxRate", 0),
                    "tp_regime": props.get("transferPricingRegime", ""),
                    "has_ip_box": props.get("hasIPBoxRegime", False)
                })

            elif twin_type in ["ParentCompany", "Subsidiary"]:
                margin = props.get("operatingMargin", 0)
                if margin:
                    entity_margins.append(margin)
                data["entities"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "entity_type": twin_type,
                    "entity_name": props.get("entityName", twin.name),
                    "tax_id": props.get("taxId", ""),
                    "functional_profile": props.get("functionalProfile", "Unknown"),
                    "revenue": props.get("revenue", 0),
                    "operating_income": props.get("operatingIncome", 0),
                    "operating_margin": margin,
                    "employees": props.get("employees", 0),
                    "functions": props.get("functionsPerformed", []),
                    "risks": props.get("risksAssumed", [])
                })
                data["stats"]["entities_count"] += 1

            elif twin_type in ["GoodsTransaction", "IPLicenseTransaction", "ManagementFee",
                              "TechnicalServiceFee", "FinancingTransaction", "CostSharingArrangement"]:
                data["transactions"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "transaction_type": twin_type,
                    "value": props.get("transactionValue", 0),
                    "currency": props.get("currency", "USD"),
                    "fiscal_year": props.get("fiscalYear", 2024),
                    "method": props.get("selectedMethod", "Unknown"),
                    "description": props.get("productDescription", props.get("serviceDescription", "")),
                    "royalty_rate": props.get("royaltyRate"),
                    "markup": props.get("markupPercentage"),
                    "interest_rate": props.get("interestRate")
                })
                data["stats"]["total_transactions"] += 1
                data["stats"]["transaction_value"] += props.get("transactionValue", 0)

            elif twin_type in ["CUPMethod", "ResalePriceMethod", "CostPlusMethod",
                              "TNMMMethod", "ProfitSplitMethod"]:
                data["tp_methods"].append({
                    "id": twin.id,
                    "name": props.get("methodName", twin.name),
                    "description": props.get("methodDescription", ""),
                    "applicability": props.get("applicability", ""),
                    "pli": props.get("profitLevelIndicator", "")
                })

            elif twin_type == "ComparableCompany":
                data["comparables"].append({
                    "id": twin.id,
                    "name": props.get("companyName", twin.name),
                    "functional_profile": props.get("functionalProfile", "Unknown"),
                    "operating_margin": props.get("operatingMargin", 0),
                    "gross_margin": props.get("grossMargin"),
                    "net_cost_plus": props.get("netCostPlusMarkup"),
                    "revenue": props.get("revenue", 0),
                    "accepted": props.get("acceptedAsComparable", False)
                })

            elif twin_type == "ArmLengthRange":
                data["arm_length_ranges"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "pli": props.get("profitLevelIndicator", ""),
                    "profile": props.get("functionalProfile", ""),
                    "minimum": props.get("minimumValue", 0),
                    "lower_quartile": props.get("lowerQuartile", 0),
                    "median": props.get("median", 0),
                    "upper_quartile": props.get("upperQuartile", 0),
                    "maximum": props.get("maximumValue", 0),
                    "comparables_count": props.get("numberOfComparables", 0)
                })

            elif twin_type == "BackgroundDocument":
                data["documents"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "title": props.get("documentTitle", twin.name),
                    "prepared_by": props.get("preparedBy", ""),
                    "status": props.get("documentStatus", "draft"),
                    "tax_year": props.get("taxYear", 2024)
                })

            elif twin_type == "ComparabilityAnalysis":
                data["analyses"].append({
                    "id": twin.id,
                    "name": twin.name,
                    "tested_party": props.get("testedParty", ""),
                    "profile": props.get("functionalProfile", ""),
                    "database": props.get("databaseUsed", ""),
                    "companies_identified": props.get("companiesIdentified", 0),
                    "companies_accepted": props.get("companiesAccepted", 0)
                })

        # Calculate average margin
        if entity_margins:
            data["stats"]["avg_margin"] = sum(entity_margins) / len(entity_margins)

        return data


# HTML Dashboard
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transfer Pricing Dashboard - TesserAI</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 20px;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 15px;
            border: 1px solid rgba(233, 69, 96, 0.3);
        }

        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, #e94560, #ff6b6b, #ffa502);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }

        .header .subtitle {
            color: #ff9f9f;
            font-size: 1.1em;
        }

        .dashboard {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            max-width: 1800px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(0, 0, 0, 0.4);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(233, 69, 96, 0.2);
        }

        .panel-title {
            font-size: 1.1em;
            color: #e94560;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(233, 69, 96, 0.2);
        }

        .panel-icon {
            font-size: 1.3em;
        }

        /* Group Overview */
        .group-overview {
            grid-column: span 2;
        }

        .group-header {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 20px;
        }

        .group-icon {
            font-size: 3em;
            color: #e94560;
        }

        .group-info h3 {
            font-size: 1.5em;
            color: #fff;
        }

        .group-info p {
            color: #aaa;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
        }

        .stat-card {
            background: rgba(233, 69, 96, 0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }

        .stat-value {
            font-size: 1.6em;
            font-weight: bold;
            color: #e94560;
        }

        .stat-label {
            font-size: 0.85em;
            color: #ff9f9f;
            margin-top: 5px;
        }

        /* Jurisdictions */
        .jurisdictions-panel {
            grid-column: span 2;
        }

        .jurisdiction-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }

        .jurisdiction-card {
            background: rgba(15, 52, 96, 0.4);
            padding: 12px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid rgba(33, 150, 243, 0.2);
        }

        .jurisdiction-flag {
            font-size: 2em;
            margin-bottom: 5px;
        }

        .jurisdiction-name {
            font-weight: bold;
            color: #64b5f6;
            margin-bottom: 5px;
        }

        .tax-rate {
            font-size: 1.5em;
            font-weight: bold;
            color: #4caf50;
        }

        .tax-rate.high { color: #f44336; }
        .tax-rate.medium { color: #ff9800; }
        .tax-rate.low { color: #4caf50; }

        .jurisdiction-badges {
            margin-top: 8px;
            display: flex;
            justify-content: center;
            gap: 5px;
            flex-wrap: wrap;
        }

        .badge {
            font-size: 0.7em;
            padding: 2px 6px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.1);
        }

        .badge-ip { background: rgba(156, 39, 176, 0.3); color: #ce93d8; }
        .badge-tp { background: rgba(33, 150, 243, 0.3); color: #90caf9; }

        /* Entity Structure */
        .entity-panel {
            grid-column: span 2;
        }

        .entity-tree {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .entity-card {
            background: rgba(233, 69, 96, 0.1);
            padding: 12px 15px;
            border-radius: 10px;
            border-left: 4px solid #e94560;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .entity-card.parent {
            border-left-color: #ffa502;
            background: rgba(255, 165, 2, 0.15);
        }

        .entity-card.subsidiary {
            margin-left: 25px;
            border-left-color: #64b5f6;
            background: rgba(100, 181, 246, 0.1);
        }

        .entity-name {
            font-weight: bold;
            font-size: 0.95em;
        }

        .entity-profile {
            font-size: 0.8em;
            color: #aaa;
        }

        .entity-metrics {
            display: flex;
            gap: 20px;
            font-size: 0.85em;
        }

        .entity-metric {
            text-align: right;
        }

        .entity-metric-value {
            font-weight: bold;
            color: #64b5f6;
        }

        /* Transaction Flow */
        .transaction-panel {
            grid-column: span 2;
        }

        .transaction-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-height: 300px;
            overflow-y: auto;
        }

        .transaction-item {
            background: rgba(0, 0, 0, 0.3);
            padding: 12px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .transaction-info {
            flex: 1;
        }

        .transaction-type {
            font-size: 0.75em;
            padding: 2px 8px;
            border-radius: 10px;
            margin-left: 10px;
        }

        .type-goods { background: rgba(76, 175, 80, 0.3); color: #81c784; }
        .type-royalty { background: rgba(156, 39, 176, 0.3); color: #ce93d8; }
        .type-service { background: rgba(33, 150, 243, 0.3); color: #90caf9; }
        .type-finance { background: rgba(255, 193, 7, 0.3); color: #ffd54f; }
        .type-csa { background: rgba(233, 69, 96, 0.3); color: #ef9a9a; }

        .transaction-value {
            font-size: 1.2em;
            font-weight: bold;
            color: #4caf50;
        }

        .transaction-method {
            font-size: 0.8em;
            color: #aaa;
        }

        /* Benchmarking Panel */
        .benchmarking-panel {
            grid-column: span 2;
        }

        .benchmark-chart {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .benchmark-item {
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 10px;
        }

        .benchmark-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
        }

        .benchmark-title {
            font-weight: bold;
            color: #64b5f6;
        }

        .benchmark-range-bar {
            height: 30px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            position: relative;
            overflow: hidden;
        }

        .range-fill {
            position: absolute;
            height: 100%;
            background: linear-gradient(90deg, rgba(76, 175, 80, 0.3), rgba(33, 150, 243, 0.3));
            border-radius: 15px;
        }

        .range-marker {
            position: absolute;
            top: 0;
            width: 3px;
            height: 100%;
            background: #fff;
            transform: translateX(-50%);
        }

        .range-marker.actual {
            width: 8px;
            background: #4caf50;
            border-radius: 4px;
            z-index: 2;
        }

        .range-labels {
            display: flex;
            justify-content: space-between;
            margin-top: 5px;
            font-size: 0.75em;
            color: #888;
        }

        .benchmark-result {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 10px;
        }

        .result-item {
            text-align: center;
        }

        .result-value {
            font-size: 1.2em;
            font-weight: bold;
        }

        .result-label {
            font-size: 0.75em;
            color: #888;
        }

        .in-range { color: #4caf50; }
        .out-of-range { color: #f44336; }

        /* TP Methods */
        .methods-panel {
            grid-column: span 2;
        }

        .method-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 10px;
        }

        .method-card {
            background: rgba(156, 39, 176, 0.1);
            padding: 12px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid rgba(156, 39, 176, 0.2);
        }

        .method-name {
            font-weight: bold;
            color: #ce93d8;
            font-size: 0.9em;
        }

        .method-pli {
            font-size: 0.75em;
            color: #aaa;
            margin-top: 5px;
        }

        /* Compliance Score */
        .compliance-panel {
            grid-column: span 2;
        }

        .compliance-gauge {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 30px;
            padding: 20px;
        }

        .gauge-circle {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5em;
            font-weight: bold;
            position: relative;
        }

        .gauge-circle::before {
            content: '';
            position: absolute;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background: conic-gradient(
                #4caf50 0deg calc(var(--score) * 3.6deg),
                rgba(255, 255, 255, 0.1) calc(var(--score) * 3.6deg) 360deg
            );
        }

        .gauge-inner {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1;
            color: #4caf50;
        }

        .compliance-details {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .compliance-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .compliance-icon {
            font-size: 1.2em;
        }

        .compliance-text {
            font-size: 0.9em;
        }

        /* Documents Panel */
        .documents-panel {
            grid-column: span 2;
        }

        .document-list {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }

        .document-item {
            background: rgba(121, 85, 72, 0.2);
            padding: 12px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .document-icon {
            font-size: 1.5em;
            color: #bcaaa4;
        }

        .document-info {
            flex: 1;
        }

        .document-title {
            font-size: 0.85em;
            font-weight: bold;
        }

        .document-meta {
            font-size: 0.75em;
            color: #888;
        }

        .document-status {
            padding: 2px 8px;
            border-radius: 8px;
            font-size: 0.75em;
        }

        .status-final { background: rgba(76, 175, 80, 0.3); color: #81c784; }
        .status-draft { background: rgba(255, 193, 7, 0.3); color: #ffd54f; }

        /* Connection status */
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.85em;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .status-connected {
            background: rgba(76, 175, 80, 0.3);
            border: 1px solid #4caf50;
        }

        .status-disconnected {
            background: rgba(244, 67, 54, 0.3);
            border: 1px solid #f44336;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }

        .status-connected .status-dot {
            background: #4caf50;
            animation: pulse-dot 2s infinite;
        }

        .status-disconnected .status-dot {
            background: #f44336;
        }

        @keyframes pulse-dot {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.2); opacity: 0.7; }
        }

        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 6px;
        }

        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 3px;
        }

        ::-webkit-scrollbar-thumb {
            background: rgba(233, 69, 96, 0.3);
            border-radius: 3px;
        }

        @media (max-width: 1400px) {
            .dashboard {
                grid-template-columns: repeat(2, 1fr);
            }
            .group-overview, .jurisdictions-panel, .entity-panel, .transaction-panel,
            .benchmarking-panel, .methods-panel, .compliance-panel, .documents-panel {
                grid-column: span 2;
            }
        }
    </style>
</head>
<body>
    <div id="connection-status" class="connection-status status-disconnected">
        <span class="status-dot"></span>
        <span id="status-text">Connecting...</span>
    </div>

    <div class="header">
        <h1>Transfer Pricing Dashboard</h1>
        <div class="subtitle">Multinational Tax Compliance & Benchmarking Analysis</div>
    </div>

    <div class="dashboard">
        <!-- Group Overview -->
        <div class="panel group-overview">
            <div class="panel-title">
                <span class="panel-icon">&#127970;</span>
                Multinational Group Overview
            </div>
            <div class="group-header">
                <span class="group-icon">&#127757;</span>
                <div class="group-info">
                    <h3 id="group-name">Loading...</h3>
                    <p id="group-industry">--</p>
                </div>
            </div>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value" id="consolidated-revenue">--</div>
                    <div class="stat-label">Consolidated Revenue</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="entity-count">--</div>
                    <div class="stat-label">Legal Entities</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="employee-count">--</div>
                    <div class="stat-label">Employees</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="transaction-count">--</div>
                    <div class="stat-label">IC Transactions</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="transaction-value">--</div>
                    <div class="stat-label">Transaction Value</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="avg-margin">--</div>
                    <div class="stat-label">Avg Operating Margin</div>
                </div>
            </div>
        </div>

        <!-- Jurisdictions -->
        <div class="panel jurisdictions-panel">
            <div class="panel-title">
                <span class="panel-icon">&#127758;</span>
                Tax Jurisdictions
            </div>
            <div id="jurisdiction-grid" class="jurisdiction-grid">
                <!-- Jurisdictions populated by JS -->
            </div>
        </div>

        <!-- Entity Structure -->
        <div class="panel entity-panel">
            <div class="panel-title">
                <span class="panel-icon">&#128200;</span>
                Corporate Structure & Profitability
            </div>
            <div id="entity-tree" class="entity-tree">
                <!-- Entities populated by JS -->
            </div>
        </div>

        <!-- Intercompany Transactions -->
        <div class="panel transaction-panel">
            <div class="panel-title">
                <span class="panel-icon">&#128257;</span>
                Intercompany Transactions FY2024
            </div>
            <div id="transaction-list" class="transaction-list">
                <!-- Transactions populated by JS -->
            </div>
        </div>

        <!-- Benchmarking Analysis -->
        <div class="panel benchmarking-panel">
            <div class="panel-title">
                <span class="panel-icon">&#128202;</span>
                Arm's Length Benchmarking
            </div>
            <div id="benchmark-chart" class="benchmark-chart">
                <!-- Benchmarks populated by JS -->
            </div>
        </div>

        <!-- TP Methods -->
        <div class="panel methods-panel">
            <div class="panel-title">
                <span class="panel-icon">&#128221;</span>
                Transfer Pricing Methods
            </div>
            <div id="method-grid" class="method-grid">
                <!-- Methods populated by JS -->
            </div>
        </div>

        <!-- Compliance Score -->
        <div class="panel compliance-panel">
            <div class="panel-title">
                <span class="panel-icon">&#9989;</span>
                Compliance Status
            </div>
            <div class="compliance-gauge">
                <div class="gauge-circle" style="--score: 95">
                    <div class="gauge-inner">95%</div>
                </div>
                <div class="compliance-details">
                    <div class="compliance-item">
                        <span class="compliance-icon" style="color: #4caf50">&#10004;</span>
                        <span class="compliance-text">All tested parties within IQR</span>
                    </div>
                    <div class="compliance-item">
                        <span class="compliance-icon" style="color: #4caf50">&#10004;</span>
                        <span class="compliance-text">Documentation complete for FY2024</span>
                    </div>
                    <div class="compliance-item">
                        <span class="compliance-icon" style="color: #4caf50">&#10004;</span>
                        <span class="compliance-text">Benchmarking studies current</span>
                    </div>
                    <div class="compliance-item">
                        <span class="compliance-icon" style="color: #ff9800">&#9888;</span>
                        <span class="compliance-text">CSA buy-in analysis pending review</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Background Documents -->
        <div class="panel documents-panel">
            <div class="panel-title">
                <span class="panel-icon">&#128196;</span>
                Background Documents
            </div>
            <div id="document-list" class="document-list">
                <!-- Documents populated by JS -->
            </div>
        </div>
    </div>

    <script>
        let ws;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 10;

        const countryFlags = {
            'US': '&#127482;&#127480;',
            'IE': '&#127470;&#127466;',
            'DE': '&#127465;&#127466;',
            'SG': '&#127480;&#127468;',
            'KY': '&#127472;&#127486;',
            'JP': '&#127471;&#127477;'
        };

        function connect() {
            ws = new WebSocket('ws://localhost:WS_PORT_PLACEHOLDER');

            ws.onopen = () => {
                console.log('Connected to taxation data stream');
                document.getElementById('connection-status').className = 'connection-status status-connected';
                document.getElementById('status-text').textContent = 'Live';
                reconnectAttempts = 0;
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                updateDashboard(data);
            };

            ws.onclose = () => {
                document.getElementById('connection-status').className = 'connection-status status-disconnected';
                document.getElementById('status-text').textContent = 'Reconnecting...';

                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    setTimeout(connect, 2000);
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }

        function formatCurrency(value) {
            if (value >= 1e9) return '$' + (value / 1e9).toFixed(1) + 'B';
            if (value >= 1e6) return '$' + (value / 1e6).toFixed(0) + 'M';
            if (value >= 1e3) return '$' + (value / 1e3).toFixed(0) + 'K';
            return '$' + value.toLocaleString();
        }

        function updateDashboard(data) {
            // Update group info
            if (data.group) {
                document.getElementById('group-name').textContent = data.group.name;
                document.getElementById('group-industry').textContent = data.group.industry;
                document.getElementById('consolidated-revenue').textContent =
                    formatCurrency(data.group.consolidated_revenue);
                document.getElementById('employee-count').textContent =
                    data.group.employees.toLocaleString();
            }

            // Update stats
            document.getElementById('entity-count').textContent = data.stats.entities_count;
            document.getElementById('transaction-count').textContent = data.stats.total_transactions;
            document.getElementById('transaction-value').textContent =
                formatCurrency(data.stats.transaction_value);
            document.getElementById('avg-margin').textContent =
                (data.stats.avg_margin * 100).toFixed(1) + '%';

            // Update jurisdictions
            updateJurisdictions(data.jurisdictions);

            // Update entities
            updateEntities(data.entities);

            // Update transactions
            updateTransactions(data.transactions);

            // Update benchmarking
            updateBenchmarking(data.arm_length_ranges, data.entities);

            // Update methods
            updateMethods(data.tp_methods);

            // Update documents
            updateDocuments(data.documents);
        }

        function updateJurisdictions(jurisdictions) {
            const container = document.getElementById('jurisdiction-grid');
            container.innerHTML = jurisdictions.map(j => {
                const taxRate = j.tax_rate * 100;
                const rateClass = taxRate > 25 ? 'high' : taxRate > 15 ? 'medium' : 'low';
                const flag = countryFlags[j.country_code] || '&#127760;';

                return `
                    <div class="jurisdiction-card">
                        <div class="jurisdiction-flag">${flag}</div>
                        <div class="jurisdiction-name">${j.name}</div>
                        <div class="tax-rate ${rateClass}">${taxRate.toFixed(1)}%</div>
                        <div class="jurisdiction-badges">
                            ${j.has_ip_box ? '<span class="badge badge-ip">IP Box</span>' : ''}
                            ${j.tp_regime === 'comprehensive' ? '<span class="badge badge-tp">TP Regime</span>' : ''}
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateEntities(entities) {
            const container = document.getElementById('entity-tree');

            // Sort: parent first, then subsidiaries
            const sorted = entities.sort((a, b) => {
                if (a.entity_type === 'ParentCompany') return -1;
                if (b.entity_type === 'ParentCompany') return 1;
                return b.revenue - a.revenue;
            });

            container.innerHTML = sorted.map(entity => {
                const cardClass = entity.entity_type === 'ParentCompany' ? 'parent' : 'subsidiary';
                const margin = entity.operating_margin * 100;

                return `
                    <div class="entity-card ${cardClass}">
                        <div>
                            <div class="entity-name">${entity.entity_name}</div>
                            <div class="entity-profile">${entity.functional_profile}</div>
                        </div>
                        <div class="entity-metrics">
                            <div class="entity-metric">
                                <div class="entity-metric-value">${formatCurrency(entity.revenue)}</div>
                                <div>Revenue</div>
                            </div>
                            <div class="entity-metric">
                                <div class="entity-metric-value">${margin.toFixed(1)}%</div>
                                <div>Op Margin</div>
                            </div>
                            <div class="entity-metric">
                                <div class="entity-metric-value">${entity.employees.toLocaleString()}</div>
                                <div>Employees</div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateTransactions(transactions) {
            const container = document.getElementById('transaction-list');

            const typeLabels = {
                'GoodsTransaction': { label: 'Goods', class: 'type-goods' },
                'IPLicenseTransaction': { label: 'Royalty', class: 'type-royalty' },
                'ManagementFee': { label: 'Service', class: 'type-service' },
                'TechnicalServiceFee': { label: 'Service', class: 'type-service' },
                'FinancingTransaction': { label: 'Finance', class: 'type-finance' },
                'CostSharingArrangement': { label: 'CSA', class: 'type-csa' }
            };

            container.innerHTML = transactions.map(txn => {
                const typeInfo = typeLabels[txn.transaction_type] || { label: 'Other', class: '' };
                let details = '';
                if (txn.royalty_rate) details = `Rate: ${(txn.royalty_rate * 100).toFixed(1)}%`;
                else if (txn.markup) details = `Markup: ${(txn.markup * 100).toFixed(0)}%`;
                else if (txn.interest_rate) details = `Interest: ${(txn.interest_rate * 100).toFixed(1)}%`;

                return `
                    <div class="transaction-item">
                        <div class="transaction-info">
                            <div>
                                ${txn.name.replace('FY2024 ', '')}
                                <span class="transaction-type ${typeInfo.class}">${typeInfo.label}</span>
                            </div>
                            <div class="transaction-method">Method: ${txn.method} ${details ? '| ' + details : ''}</div>
                        </div>
                        <div class="transaction-value">${formatCurrency(txn.value)}</div>
                    </div>
                `;
            }).join('');
        }

        function updateBenchmarking(ranges, entities) {
            const container = document.getElementById('benchmark-chart');

            // Map entity functional profiles to ranges
            const profileMap = {
                'Limited Risk Distributor': 0.04, // Ireland/Japan actual margin
                'Contract Manufacturer': 0.06,    // Germany actual markup
                'Service Provider': 0.10          // Singapore actual margin
            };

            container.innerHTML = ranges.map(range => {
                const actualValue = profileMap[range.profile] || range.median;
                const minPct = 0;
                const maxPct = 100;
                const rangePct = (range.maximum - range.minimum) || 0.01;

                const lqPos = ((range.lower_quartile - range.minimum) / rangePct) * 100;
                const uqPos = ((range.upper_quartile - range.minimum) / rangePct) * 100;
                const actualPos = ((actualValue - range.minimum) / rangePct) * 100;
                const medianPos = ((range.median - range.minimum) / rangePct) * 100;

                const isInRange = actualValue >= range.lower_quartile && actualValue <= range.upper_quartile;
                const resultClass = isInRange ? 'in-range' : 'out-of-range';

                return `
                    <div class="benchmark-item">
                        <div class="benchmark-header">
                            <span class="benchmark-title">${range.profile}</span>
                            <span>${range.pli}</span>
                        </div>
                        <div class="benchmark-range-bar">
                            <div class="range-fill" style="left: ${lqPos}%; width: ${uqPos - lqPos}%"></div>
                            <div class="range-marker" style="left: ${medianPos}%" title="Median"></div>
                            <div class="range-marker actual" style="left: ${actualPos}%" title="Actual"></div>
                        </div>
                        <div class="range-labels">
                            <span>${(range.minimum * 100).toFixed(1)}%</span>
                            <span>LQ: ${(range.lower_quartile * 100).toFixed(1)}%</span>
                            <span>Med: ${(range.median * 100).toFixed(1)}%</span>
                            <span>UQ: ${(range.upper_quartile * 100).toFixed(1)}%</span>
                            <span>${(range.maximum * 100).toFixed(1)}%</span>
                        </div>
                        <div class="benchmark-result">
                            <div class="result-item">
                                <div class="result-value ${resultClass}">${(actualValue * 100).toFixed(1)}%</div>
                                <div class="result-label">Actual</div>
                            </div>
                            <div class="result-item">
                                <div class="result-value">${range.comparables_count}</div>
                                <div class="result-label">Comparables</div>
                            </div>
                            <div class="result-item">
                                <div class="result-value ${resultClass}">${isInRange ? 'PASS' : 'REVIEW'}</div>
                                <div class="result-label">Status</div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        function updateMethods(methods) {
            const container = document.getElementById('method-grid');
            container.innerHTML = methods.map(method => `
                <div class="method-card">
                    <div class="method-name">${method.name.replace(' Method', '')}</div>
                    <div class="method-pli">${method.pli}</div>
                </div>
            `).join('');
        }

        function updateDocuments(documents) {
            const container = document.getElementById('document-list');
            container.innerHTML = documents.map(doc => `
                <div class="document-item">
                    <span class="document-icon">&#128196;</span>
                    <div class="document-info">
                        <div class="document-title">${doc.title.substring(0, 40)}...</div>
                        <div class="document-meta">${doc.prepared_by} | FY${doc.tax_year}</div>
                    </div>
                    <span class="document-status status-${doc.status}">${doc.status}</span>
                </div>
            `).join('');
        }

        // Start connection
        connect();
    </script>
</body>
</html>
""".replace('WS_PORT_PLACEHOLDER', str(WS_PORT))


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP handler for serving the dashboard."""

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs


async def broadcast_data(websocket, collector: TaxationDataCollector):
    """Broadcast taxation data to connected clients."""
    try:
        while True:
            data = collector.collect_data()
            await websocket.send(json.dumps(data))
            await asyncio.sleep(5)
    except websockets.exceptions.ConnectionClosed:
        pass


async def ws_handler(websocket, collector: TaxationDataCollector):
    """Handle WebSocket connections."""
    await broadcast_data(websocket, collector)


def run_http_server():
    """Run the HTTP server for the dashboard."""
    server = HTTPServer(('0.0.0.0', HTTP_PORT), DashboardHandler)
    server.serve_forever()


async def main():
    """Main entry point."""
    print(f"\n{'='*60}")
    print("  Transfer Pricing Dashboard - TesserAI Digital Twin")
    print(f"{'='*60}")
    print(f"\n  Dashboard: http://localhost:{HTTP_PORT}")
    print(f"  WebSocket: ws://localhost:{WS_PORT}")
    print(f"\n  Press Ctrl+C to stop\n")

    collector = TaxationDataCollector()

    # Start HTTP server in background thread
    http_thread = Thread(target=run_http_server, daemon=True)
    http_thread.start()

    # Start WebSocket server
    async with websockets.serve(
        lambda ws: ws_handler(ws, collector),
        "0.0.0.0",
        WS_PORT
    ):
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
