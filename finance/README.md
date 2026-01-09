# Finance Example

A comprehensive financial services digital twin demonstrating TesseraiDB's capabilities for portfolio management, risk monitoring, trading systems, and regulatory compliance.

## Overview

- What this domain models: Complete financial services infrastructure including portfolios, instruments, trading desks, counterparties, and compliance rules
- Key entities and relationships: Financial institutions, portfolios, positions, instruments (equities, bonds, derivatives), orders, risk metrics, and counterparties
- Real-world use cases: Portfolio management, real-time risk monitoring, VaR calculations, trading system management, counterparty risk assessment, regulatory compliance

## Prerequisites

- TesseraiDB account at [tesserai.io](https://tesserai.io)
- Set your API key: `export TESSERAI_API_KEY="your-api-key"`
- Python 3.10+ with the TesseraiDB SDK: `pip install tesserai`

## Quick Start

```bash
# Seed the example data
python seed.py

# Run the Phase 13 adaptive schema demo
python demo_phase13.py
```

## Digital Twins

List of main twin types created:

- **FinancialInstitution**: Banks and financial organizations
- **TradingDesk**: Trading desk operations
- **Portfolio**: Investment portfolios
- **ClearingHouse**: Central clearing counterparties
- **Equity**: Stock instruments
- **Bond**: Fixed income instruments
- **Derivative**: Options, futures, swaps
- **Currency**: FX instruments
- **Cryptocurrency**: Digital assets
- **ETF**: Exchange-traded funds
- **Position**: Portfolio positions
- **RiskMetric**: VaR, exposure metrics
- **RiskLimit**: Portfolio risk limits
- **RiskAlert**: Risk threshold alerts
- **Order**: Trading orders
- **Counterparty**: Trading counterparties
- **ComplianceRule**: Regulatory compliance rules

## Ontology

The finance ontology defines:

- **Instrument hierarchy**: Equity, Bond, Derivative (Option, Future, Swap), Currency, Cryptocurrency, ETF
- **Position relationships**: Portfolio -> Position -> Instrument
- **Risk relationships**: Portfolio/Desk -> RiskLimit, RiskMetric, RiskAlert
- **Trading relationships**: Order -> Instrument, TradingDesk, ClearingHouse

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all portfolios with their risk metrics
portfolios = client.sparql.query("""
    PREFIX fin: <http://tesserai.io/ontology/finance#>
    SELECT ?portfolio ?name ?var ?exposure WHERE {
        ?portfolio a fin:Portfolio ;
                   fin:name ?name .
        OPTIONAL {
            ?portfolio fin:hasRiskMetric ?metric .
            ?metric fin:valueAtRisk ?var ;
                    fin:totalExposure ?exposure .
        }
    }
""")

# Find positions exceeding risk limits
breaches = client.sparql.query("""
    PREFIX fin: <http://tesserai.io/ontology/finance#>
    SELECT ?portfolio ?position ?value ?limit WHERE {
        ?portfolio fin:hasPosition ?position ;
                   fin:hasRiskLimit ?limitDef .
        ?position fin:marketValue ?value .
        ?limitDef fin:maxValue ?limit .
        FILTER (?value > ?limit)
    }
""")

# Get trading desk performance
performance = client.sparql.query("""
    PREFIX fin: <http://tesserai.io/ontology/finance#>
    SELECT ?desk ?deskName (SUM(?pnl) as ?totalPnL) WHERE {
        ?desk a fin:TradingDesk ;
              fin:name ?deskName ;
              fin:hasOrder ?order .
        ?order fin:realizedPnL ?pnl .
    }
    GROUP BY ?desk ?deskName
    ORDER BY DESC(?totalPnL)
""")
```

## Additional Features

### Phase 13 Adaptive Schema

The `demo_phase13.py` script demonstrates:

- **Natural Language Schema Editing**: Modify schemas using plain English
- **Impact Analysis**: Predict impact of schema changes before applying
- **Schema Discovery**: Automatically detect patterns in incoming data
- **Governance Workflows**: Configure approval requirements for schema changes
- **Schema Conversation**: Interactive chat for schema evolution

### Risk Monitoring

- Real-time Value-at-Risk (VaR) calculations
- Exposure tracking by asset class
- Risk limit monitoring and alerting
- Counterparty credit risk assessment

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
