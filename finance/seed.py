#!/usr/bin/env python3
"""
Finance Domain Digital Twin Example

This example creates a comprehensive digital twin of a financial institution,
including trading desks, portfolios, positions, risk management, and compliance.

Domain: Financial Services
Use Cases:
  - Real-time portfolio valuation and P&L
  - Risk monitoring and limit management
  - Trading system health tracking
  - Regulatory compliance monitoring
  - Counterparty exposure management
  - Market data integration
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import (
    get_client, print_summary, logger,
    bulk_create_twins, bulk_add_relationships,
    DOMAIN_NAMESPACES
)

# Domain for this seed script
DOMAIN = "finance"
FIN_NS = DOMAIN_NAMESPACES[DOMAIN]


def prepare_finance_twin(data: dict) -> dict:
    """Prepare a twin dict for bulk creation in the finance domain.

    Accepts the same dict format as before, but expands the type
    to use the full finance ontology namespace.
    """
    # Expand type to full URI if it's a short name
    twin_type = data.get("type", "")
    if twin_type and "://" not in twin_type:
        data["type"] = f"{FIN_NS}{twin_type}"

    # Add domain tag
    data["domain"] = DOMAIN

    return data


def seed_finance():
    """Seed the finance digital twin."""
    client = get_client()
    all_twins = []
    all_relationships = []

    # =========================================================================
    # FINANCIAL INSTITUTION
    # =========================================================================
    all_twins.append(prepare_finance_twin({
        "id": "bank-globalcapital-001",
        "type": "FinancialInstitution",
        "name": "GlobalCapital Investment Bank",
        "description": "Full-service investment bank with trading, asset management, and wealth services",
        "properties": {
            "legalEntityIdentifier": "5493001KJTIIGC8Y1R12",
            "headquarters": "New York, NY",
            "regulators": ["SEC", "FINRA", "OCC", "Federal Reserve"],
            "tier1Capital": 45000000000,
            "totalAssets": 890000000000,
            "employees": 12500,
            "tradingLocations": ["New York", "London", "Tokyo", "Hong Kong", "Singapore"],
            "riskRating": "A+",
            "currency": "USD"
        }
    }))

    # =========================================================================
    # EXCHANGES
    # =========================================================================
    exchanges = [
        {"id": "exchange-nyse", "name": "New York Stock Exchange", "mic": "XNYS", "timezone": "America/New_York"},
        {"id": "exchange-nasdaq", "name": "NASDAQ", "mic": "XNAS", "timezone": "America/New_York"},
        {"id": "exchange-lse", "name": "London Stock Exchange", "mic": "XLON", "timezone": "Europe/London"},
        {"id": "exchange-tse", "name": "Tokyo Stock Exchange", "mic": "XJPX", "timezone": "Asia/Tokyo"},
        {"id": "exchange-cme", "name": "Chicago Mercantile Exchange", "mic": "XCME", "timezone": "America/Chicago"},
        {"id": "exchange-ice", "name": "Intercontinental Exchange", "mic": "IFUS", "timezone": "America/New_York"},
    ]

    for exch in exchanges:
        all_twins.append(prepare_finance_twin({
            "id": exch["id"],
            "type": "Exchange",
            "name": exch["name"],
            "properties": {
                "mic": exch["mic"],
                "timezone": exch["timezone"],
                "status": "open",
                "tradingHours": "09:30-16:00",
                "latencyMs": 0.5
            }
        }))

    # =========================================================================
    # TRADING DESKS
    # =========================================================================
    desks = [
        {"id": "desk-equities", "name": "Equities Trading Desk", "assetClass": "Equities", "traders": 45},
        {"id": "desk-fixed-income", "name": "Fixed Income Desk", "assetClass": "Fixed Income", "traders": 38},
        {"id": "desk-fx", "name": "FX Trading Desk", "assetClass": "Foreign Exchange", "traders": 22},
        {"id": "desk-derivatives", "name": "Derivatives Desk", "assetClass": "Derivatives", "traders": 35},
        {"id": "desk-commodities", "name": "Commodities Desk", "assetClass": "Commodities", "traders": 18},
        {"id": "desk-crypto", "name": "Digital Assets Desk", "assetClass": "Cryptocurrency", "traders": 12},
    ]

    for desk in desks:
        all_twins.append(prepare_finance_twin({
            "id": desk["id"],
            "type": "TradingDesk",
            "name": desk["name"],
            "properties": {
                "assetClass": desk["assetClass"],
                "headCount": desk["traders"],
                "location": "New York",
                "status": "active",
                "dailyVolumeLimit": 5000000000,
                "currentDailyVolume": 2340000000,
                "riskLimit": 100000000,
                "currentExposure": 45000000,
                "pnlMTD": 12500000,
                "currency": "USD"
            }
        }))
        all_relationships.append(("bank-globalcapital-001", "hasTradingDesk", desk["id"], None))

    # =========================================================================
    # TRADING SYSTEMS
    # =========================================================================
    systems = [
        {"id": "system-oms-equities", "name": "Equities OMS", "type": "OrderManagementSystem", "desk": "desk-equities"},
        {"id": "system-oms-fi", "name": "Fixed Income OMS", "type": "OrderManagementSystem", "desk": "desk-fixed-income"},
        {"id": "system-ems", "name": "Execution Management System", "type": "TradingSystem", "desk": "desk-equities"},
        {"id": "system-algo", "name": "Algorithmic Trading Engine", "type": "TradingSystem", "desk": "desk-equities"},
        {"id": "system-risk-realtime", "name": "Real-time Risk Engine", "type": "TradingSystem", "desk": "desk-derivatives"},
    ]

    for sys in systems:
        all_twins.append(prepare_finance_twin({
            "id": sys["id"],
            "type": sys["type"],
            "name": sys["name"],
            "properties": {
                "version": "3.2.1",
                "status": "running",
                "uptime": 99.97,
                "latencyP99": 2.5,
                "latencyUnit": "ms",
                "ordersPerSecond": 15000,
                "currentLoad": 45,
                "maxCapacity": 50000,
                "lastHealthCheck": "2024-12-21T10:30:00Z",
                "dataCenter": "NY4"
            }
        }))
        all_relationships.append((sys["desk"], "usesSystem", sys["id"], None))

    # =========================================================================
    # MARKET DATA FEEDS
    # =========================================================================
    feeds = [
        {"id": "feed-nyse", "name": "NYSE Market Data", "exchange": "exchange-nyse", "type": "L2"},
        {"id": "feed-nasdaq", "name": "NASDAQ TotalView", "exchange": "exchange-nasdaq", "type": "L3"},
        {"id": "feed-bloomberg", "name": "Bloomberg B-PIPE", "exchange": None, "type": "consolidated"},
        {"id": "feed-reuters", "name": "Refinitiv Elektron", "exchange": None, "type": "consolidated"},
        {"id": "feed-cme", "name": "CME Market Data", "exchange": "exchange-cme", "type": "L2"},
    ]

    for feed in feeds:
        all_twins.append(prepare_finance_twin({
            "id": feed["id"],
            "type": "MarketDataFeed",
            "name": feed["name"],
            "properties": {
                "feedType": feed["type"],
                "status": "connected",
                "messagesPerSecond": 250000,
                "latencyUs": 50,
                "lastUpdate": "2024-12-21T14:30:45.123Z",
                "gapCount": 0,
                "staleThresholdMs": 100
            }
        }))
        if feed["exchange"]:
            all_relationships.append((feed["id"], "providesDataFrom", feed["exchange"], None))
        all_relationships.append(("system-oms-equities", "usesDataFeed", feed["id"], None))

    # =========================================================================
    # FINANCIAL INSTRUMENTS
    # =========================================================================
    equities = [
        {"id": "equity-aapl", "ticker": "AAPL", "name": "Apple Inc.", "price": 195.50, "volume": 45000000},
        {"id": "equity-msft", "ticker": "MSFT", "name": "Microsoft Corp.", "price": 378.25, "volume": 22000000},
        {"id": "equity-googl", "ticker": "GOOGL", "name": "Alphabet Inc.", "price": 141.80, "volume": 18000000},
        {"id": "equity-amzn", "ticker": "AMZN", "name": "Amazon.com Inc.", "price": 153.40, "volume": 35000000},
        {"id": "equity-nvda", "ticker": "NVDA", "name": "NVIDIA Corp.", "price": 495.20, "volume": 42000000},
        {"id": "equity-tsla", "ticker": "TSLA", "name": "Tesla Inc.", "price": 252.10, "volume": 85000000},
        {"id": "equity-jpm", "ticker": "JPM", "name": "JPMorgan Chase", "price": 168.90, "volume": 8500000},
        {"id": "equity-gs", "ticker": "GS", "name": "Goldman Sachs", "price": 385.60, "volume": 2200000},
    ]

    for eq in equities:
        all_twins.append(prepare_finance_twin({
            "id": eq["id"],
            "type": "Equity",
            "name": eq["name"],
            "properties": {
                "ticker": eq["ticker"],
                "exchange": "NYSE" if eq["ticker"] in ["AAPL", "JPM", "GS"] else "NASDAQ",
                "price": eq["price"],
                "bidPrice": eq["price"] - 0.01,
                "askPrice": eq["price"] + 0.01,
                "volume": eq["volume"],
                "volatility": 0.25,
                "beta": 1.15,
                "marketCap": eq["price"] * 1000000000,
                "currency": "USD",
                "sector": "Technology" if eq["ticker"] not in ["JPM", "GS"] else "Financials",
                "lastUpdate": "2024-12-21T14:30:45Z"
            }
        }))
        all_relationships.append((eq["id"], "tradedOn", "exchange-nyse" if eq["ticker"] in ["AAPL", "JPM", "GS"] else "exchange-nasdaq", None))

    # Bonds
    bonds = [
        {"id": "bond-ust-10y", "name": "US Treasury 10Y", "yield": 4.25, "maturity": "2033-12-15"},
        {"id": "bond-ust-2y", "name": "US Treasury 2Y", "yield": 4.65, "maturity": "2026-12-15"},
        {"id": "bond-corp-aapl-25", "name": "Apple 3.5% 2026", "yield": 4.85, "maturity": "2026-06-15"},
        {"id": "bond-corp-msft-30", "name": "Microsoft 2.5% 2030", "yield": 4.45, "maturity": "2030-09-15"},
    ]

    for bond in bonds:
        all_twins.append(prepare_finance_twin({
            "id": bond["id"],
            "type": "Bond",
            "name": bond["name"],
            "properties": {
                "yield": bond["yield"],
                "maturityDate": bond["maturity"],
                "couponRate": 3.5,
                "couponFrequency": "semi-annual",
                "faceValue": 1000,
                "price": 98.50,
                "duration": 7.5,
                "convexity": 0.65,
                "creditRating": "AAA" if "Treasury" in bond["name"] else "AA+",
                "currency": "USD"
            }
        }))

    # Derivatives
    derivatives = [
        {"id": "option-aapl-c-200-dec", "name": "AAPL Dec $200 Call", "underlying": "equity-aapl", "strike": 200, "type": "call"},
        {"id": "option-aapl-p-190-dec", "name": "AAPL Dec $190 Put", "underlying": "equity-aapl", "strike": 190, "type": "put"},
        {"id": "future-es-dec", "name": "E-mini S&P 500 Dec", "underlying": "SPX", "expiry": "2024-12-20"},
        {"id": "future-gc-feb", "name": "Gold Feb", "underlying": "GC", "expiry": "2026-02-26"},
    ]

    for deriv in derivatives:
        deriv_type = "Option" if "option" in deriv["id"] else "Future"
        all_twins.append(prepare_finance_twin({
            "id": deriv["id"],
            "type": deriv_type,
            "name": deriv["name"],
            "properties": {
                "underlyingAsset": deriv.get("underlying", ""),
                "strikePrice": deriv.get("strike", 0),
                "optionType": deriv.get("type", ""),
                "expiryDate": deriv.get("expiry", "2024-12-20"),
                "price": 5.50,
                "impliedVolatility": 0.28,
                "delta": 0.55 if deriv.get("type") == "call" else -0.45,
                "gamma": 0.02,
                "theta": -0.15,
                "vega": 0.18,
                "openInterest": 125000,
                "currency": "USD"
            }
        }))

    # Cryptocurrencies
    cryptos = [
        {"id": "crypto-btc", "ticker": "BTC", "name": "Bitcoin", "price": 42500},
        {"id": "crypto-eth", "ticker": "ETH", "name": "Ethereum", "price": 2250},
        {"id": "crypto-sol", "ticker": "SOL", "name": "Solana", "price": 85.50},
    ]

    for crypto in cryptos:
        all_twins.append(prepare_finance_twin({
            "id": crypto["id"],
            "type": "Cryptocurrency",
            "name": crypto["name"],
            "properties": {
                "ticker": crypto["ticker"],
                "price": crypto["price"],
                "volume24h": 25000000000,
                "marketCap": crypto["price"] * 19000000 if crypto["ticker"] == "BTC" else crypto["price"] * 120000000,
                "volatility": 0.65,
                "custody": "Fireblocks",
                "currency": "USD"
            }
        }))

    # =========================================================================
    # PORTFOLIOS
    # =========================================================================
    portfolios = [
        {"id": "portfolio-equity-growth", "name": "Equity Growth Fund", "desk": "desk-equities", "aum": 2500000000},
        {"id": "portfolio-fixed-income", "name": "Investment Grade Bond Fund", "desk": "desk-fixed-income", "aum": 4200000000},
        {"id": "portfolio-multi-asset", "name": "Multi-Asset Balanced Fund", "desk": "desk-equities", "aum": 1800000000},
        {"id": "portfolio-quant-alpha", "name": "Quantitative Alpha Strategy", "desk": "desk-equities", "aum": 850000000},
        {"id": "portfolio-fx-carry", "name": "FX Carry Trade Fund", "desk": "desk-fx", "aum": 650000000},
        {"id": "portfolio-digital-assets", "name": "Digital Assets Fund", "desk": "desk-crypto", "aum": 125000000},
    ]

    for pf in portfolios:
        all_twins.append(prepare_finance_twin({
            "id": pf["id"],
            "type": "Portfolio",
            "name": pf["name"],
            "properties": {
                "assetsUnderManagement": pf["aum"],
                "currency": "USD",
                "benchmark": "S&P 500" if "equity" in pf["id"].lower() else "Bloomberg Aggregate",
                "returnYTD": 12.5,
                "returnMTD": 2.3,
                "sharpeRatio": 1.45,
                "beta": 1.05,
                "alpha": 2.1,
                "valueAtRisk": pf["aum"] * 0.02,
                "varConfidence": 0.95,
                "varHorizon": 1,
                "positionCount": 85,
                "turnover": 0.35,
                "expenseRatio": 0.0065,
                "inceptionDate": "2018-03-15",
                "status": "active"
            }
        }))
        all_relationships.append((pf["id"], "managedBy", pf["desk"], None))

    # =========================================================================
    # POSITIONS
    # =========================================================================
    positions = [
        {"id": "pos-growth-aapl", "portfolio": "portfolio-equity-growth", "instrument": "equity-aapl", "qty": 250000, "avgCost": 175.00},
        {"id": "pos-growth-msft", "portfolio": "portfolio-equity-growth", "instrument": "equity-msft", "qty": 150000, "avgCost": 320.00},
        {"id": "pos-growth-nvda", "portfolio": "portfolio-equity-growth", "instrument": "equity-nvda", "qty": 80000, "avgCost": 420.00},
        {"id": "pos-growth-googl", "portfolio": "portfolio-equity-growth", "instrument": "equity-googl", "qty": 120000, "avgCost": 125.00},
        {"id": "pos-fi-ust10y", "portfolio": "portfolio-fixed-income", "instrument": "bond-ust-10y", "qty": 50000000, "avgCost": 99.50},
        {"id": "pos-fi-ust2y", "portfolio": "portfolio-fixed-income", "instrument": "bond-ust-2y", "qty": 75000000, "avgCost": 99.25},
        {"id": "pos-digital-btc", "portfolio": "portfolio-digital-assets", "instrument": "crypto-btc", "qty": 1500, "avgCost": 35000},
        {"id": "pos-digital-eth", "portfolio": "portfolio-digital-assets", "instrument": "crypto-eth", "qty": 25000, "avgCost": 1800},
    ]

    for pos in positions:
        instrument = next((e for e in equities + bonds + cryptos if e["id"] == pos["instrument"]), None)
        # Use price if available, otherwise fall back to avgCost (bonds use yield, not price)
        current_price = instrument.get("price", pos["avgCost"]) if instrument else pos["avgCost"]
        market_value = pos["qty"] * current_price
        unrealized_pnl = pos["qty"] * (current_price - pos["avgCost"])

        all_twins.append(prepare_finance_twin({
            "id": pos["id"],
            "type": "Position",
            "name": f"Position: {pos['instrument'].split('-')[-1].upper()}",
            "properties": {
                "quantity": pos["qty"],
                "averageCost": pos["avgCost"],
                "currentPrice": current_price,
                "marketValue": market_value,
                "unrealizedPnL": unrealized_pnl,
                "unrealizedPnLPct": (unrealized_pnl / (pos["qty"] * pos["avgCost"])) * 100,
                "weight": 0.08,
                "currency": "USD",
                "costBasis": pos["qty"] * pos["avgCost"],
                "lastUpdate": "2024-12-21T14:30:00Z"
            }
        }))
        all_relationships.append((pos["portfolio"], "hasPosition", pos["id"], None))
        all_relationships.append((pos["id"], "holdsInstrument", pos["instrument"], None))

    # =========================================================================
    # COUNTERPARTIES
    # =========================================================================
    counterparties = [
        {"id": "cp-goldmansachs", "name": "Goldman Sachs", "lei": "784F5XWPLTWKTBV3E584", "rating": "low"},
        {"id": "cp-jpmorgan", "name": "JPMorgan Chase", "lei": "8I5DZWZKVSZI1NUHU748", "rating": "low"},
        {"id": "cp-citadel", "name": "Citadel Securities", "lei": "5493008JNS5SP6JNBY82", "rating": "medium"},
        {"id": "cp-hedgefund-alpha", "name": "Alpha Capital Partners", "lei": "EXAMPLE12345678901234", "rating": "high"},
        {"id": "cp-prime-broker", "name": "Prime Services LLC", "lei": "EXAMPLE98765432109876", "rating": "low"},
    ]

    for cp in counterparties:
        all_twins.append(prepare_finance_twin({
            "id": cp["id"],
            "type": "Counterparty",
            "name": cp["name"],
            "properties": {
                "legalEntityIdentifier": cp["lei"],
                "riskRating": cp["rating"],
                "creditLimit": 500000000 if cp["rating"] == "low" else 100000000,
                "currentExposure": 125000000 if cp["rating"] == "low" else 45000000,
                "utilizationPct": 25 if cp["rating"] == "low" else 45,
                "kycStatus": "approved",
                "kycLastReview": "2024-06-15",
                "jurisdictions": ["US", "UK", "EU"],
                "nettingAgreement": True,
                "isda": True,
                "csa": True
            }
        }))

    # =========================================================================
    # RISK LIMITS
    # =========================================================================
    limits = [
        {"id": "limit-var-firm", "name": "Firm-wide VaR Limit", "type": "VaR", "amount": 250000000, "utilization": 65},
        {"id": "limit-var-equities", "name": "Equities Desk VaR", "type": "VaR", "amount": 75000000, "utilization": 72},
        {"id": "limit-var-fi", "name": "Fixed Income VaR", "type": "VaR", "amount": 50000000, "utilization": 58},
        {"id": "limit-notional-deriv", "name": "Derivatives Notional", "type": "Notional", "amount": 10000000000, "utilization": 45},
        {"id": "limit-concentration", "name": "Single Name Concentration", "type": "Concentration", "amount": 0.05, "utilization": 78},
        {"id": "limit-leverage", "name": "Leverage Limit", "type": "Leverage", "amount": 3.0, "utilization": 82},
    ]

    for limit in limits:
        all_twins.append(prepare_finance_twin({
            "id": limit["id"],
            "type": "RiskLimit",
            "name": limit["name"],
            "properties": {
                "limitType": limit["type"],
                "limitAmount": limit["amount"],
                "currentValue": limit["amount"] * limit["utilization"] / 100,
                "utilizationPercent": limit["utilization"],
                "warningThreshold": 75,
                "criticalThreshold": 90,
                "status": "critical" if limit["utilization"] > 90 else "warning" if limit["utilization"] > 75 else "normal",
                "currency": "USD" if limit["type"] != "Leverage" else None,
                "lastUpdate": "2024-12-21T14:30:00Z"
            }
        }))

    # =========================================================================
    # RISK METRICS
    # =========================================================================
    metrics = [
        {"id": "metric-var-95-1d", "name": "95% 1-Day VaR", "entity": "bank-globalcapital-001", "value": 162500000},
        {"id": "metric-var-99-1d", "name": "99% 1-Day VaR", "entity": "bank-globalcapital-001", "value": 225000000},
        {"id": "metric-expected-shortfall", "name": "Expected Shortfall", "entity": "bank-globalcapital-001", "value": 285000000},
        {"id": "metric-stress-equity-crash", "name": "Equity Market Crash Stress", "entity": "portfolio-equity-growth", "value": -375000000},
        {"id": "metric-stress-rate-shock", "name": "Interest Rate Shock +200bp", "entity": "portfolio-fixed-income", "value": -420000000},
    ]

    for metric in metrics:
        all_twins.append(prepare_finance_twin({
            "id": metric["id"],
            "type": "VaRMetric" if "var" in metric["id"].lower() else "RiskMetric",
            "name": metric["name"],
            "properties": {
                "value": metric["value"],
                "currency": "USD",
                "confidenceLevel": 0.95 if "95" in metric["name"] else 0.99,
                "timeHorizon": 1,
                "methodology": "Historical Simulation",
                "scenarioCount": 500,
                "lastCalculation": "2024-12-21T14:00:00Z",
                "nextCalculation": "2024-12-21T15:00:00Z"
            }
        }))
        all_relationships.append((metric["id"], "monitorsRisk", metric["entity"], None))

    # =========================================================================
    # RISK ALERTS
    # =========================================================================
    alerts = [
        {"id": "alert-leverage-warning", "name": "Leverage Limit Warning", "trigger": "limit-leverage", "severity": "warning"},
        {"id": "alert-concentration-warning", "name": "Concentration Limit Warning", "trigger": "limit-concentration", "severity": "warning"},
    ]

    for alert in alerts:
        all_twins.append(prepare_finance_twin({
            "id": alert["id"],
            "type": "RiskAlert",
            "name": alert["name"],
            "properties": {
                "severity": alert["severity"],
                "status": "active",
                "triggeredAt": "2024-12-21T13:45:00Z",
                "acknowledgedBy": None,
                "message": f"Risk limit approaching critical threshold",
                "recommendedAction": "Review positions and consider reducing exposure"
            }
        }))
        all_relationships.append((alert["id"], "triggeredBy", alert["trigger"], None))

    # =========================================================================
    # COMPLIANCE RULES
    # =========================================================================
    rules = [
        {"id": "rule-volcker", "name": "Volcker Rule Compliance", "regulation": "Dodd-Frank Act"},
        {"id": "rule-mifid2", "name": "MiFID II Best Execution", "regulation": "MiFID II"},
        {"id": "rule-emir", "name": "EMIR Reporting", "regulation": "EMIR"},
        {"id": "rule-aml", "name": "AML/KYC Compliance", "regulation": "Bank Secrecy Act"},
        {"id": "rule-basel3", "name": "Basel III Capital Requirements", "regulation": "Basel III"},
    ]

    for rule in rules:
        all_twins.append(prepare_finance_twin({
            "id": rule["id"],
            "type": "ComplianceRule",
            "name": rule["name"],
            "properties": {
                "regulation": rule["regulation"],
                "jurisdiction": "US" if "Dodd" in rule["regulation"] or "Bank" in rule["regulation"] else "EU",
                "status": "compliant",
                "lastAudit": "2024-09-15",
                "nextAudit": "2026-03-15",
                "riskLevel": "medium",
                "automatedChecks": True,
                "checkFrequency": "daily"
            }
        }))
        all_relationships.append(("bank-globalcapital-001", "subjectTo", rule["id"], None))

    # =========================================================================
    # CLEARING HOUSES
    # =========================================================================
    clearing_houses = [
        {"id": "clearing-dtcc", "name": "DTCC", "region": "US"},
        {"id": "clearing-lch", "name": "LCH Clearnet", "region": "EU"},
        {"id": "clearing-cme-clearing", "name": "CME Clearing", "region": "US"},
    ]

    for ch in clearing_houses:
        all_twins.append(prepare_finance_twin({
            "id": ch["id"],
            "type": "ClearingHouse",
            "name": ch["name"],
            "properties": {
                "region": ch["region"],
                "status": "active",
                "marginPosted": 2500000000 if ch["name"] == "DTCC" else 1200000000,
                "marginRequired": 2200000000 if ch["name"] == "DTCC" else 1100000000,
                "excessMargin": 300000000 if ch["name"] == "DTCC" else 100000000
            }
        }))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, _ = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships via bulk API...")
    relationships_created, _ = bulk_add_relationships(client, all_relationships)

    # Print summary
    print_summary("Finance", twins_created, relationships_created)

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_finance()
