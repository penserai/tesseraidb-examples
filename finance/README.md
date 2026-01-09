# Finance Domain Example

This example demonstrates DTaaS capabilities for financial services, including portfolio management, risk monitoring, trading systems, and regulatory compliance.

## Overview

The finance domain showcases:

- **Portfolio Management**: Track portfolios, positions, and instruments
- **Risk Monitoring**: Real-time risk metrics, VaR calculations, exposure limits
- **Trading Systems**: Order management, market data feeds, execution venues
- **Counterparty Risk**: Counterparty profiles, credit limits, clearing relationships
- **Regulatory Compliance**: Compliance rules, audit trails, reporting

## Files

| File | Description |
|------|-------------|
| `seed.py` | Populates the database with example finance twins |
| `demo_phase13.py` | Demonstrates Phase 13 adaptive schema features |
| `../ontologies/finance.ttl` | Finance domain ontology (OWL + SHACL) |

## Quick Start

### 1. Start the Server

```bash
cargo run --release
```

### 2. Load the Ontology

```bash
curl -X POST http://localhost:8080/api/v1/ontologies/finance \
  -H "Authorization: Bearer finance-demo" \
  -H "Content-Type: text/turtle" \
  --data-binary @examples/ontologies/finance.ttl
```

### 3. Run the Seed Script

```bash
cd examples/finance
python seed.py
```

### 4. Run the Phase 13 Demo

```bash
python demo_phase13.py
```

## Domain Model

### Core Classes

```
FinancialInstitution
  |-- TradingDesk
  |-- Portfolio
  |-- ClearingHouse

FinancialInstrument
  |-- Equity
  |-- Bond
  |-- Derivative
  |     |-- Option
  |     |-- Future
  |     |-- Swap
  |-- Currency
  |-- Cryptocurrency
  |-- ETF

Position
  |-- belongs to Portfolio
  |-- references Instrument

RiskMetric
RiskLimit
RiskAlert

Order
  |-- placed by TradingDesk
  |-- for Instrument

Counterparty
ComplianceRule
```

### Key Relationships

- `hasPortfolio`: Institution -> Portfolio
- `hasPosition`: Portfolio -> Position
- `holdsInstrument`: Position -> Instrument
- `hasRiskLimit`: Portfolio/Desk -> RiskLimit
- `tradedOn`: Instrument -> Exchange
- `clearedThrough`: Order -> ClearingHouse

## Phase 13 Features

The `demo_phase13.py` script demonstrates:

### 1. Natural Language Schema Editing

Modify schemas using plain English:
```
"Add a volatilityIndex property to Equity class with decimal values 0-100"
```

### 2. Impact Analysis

Predict the impact of schema changes before applying:
- Safe changes (additive) auto-apply
- Breaking changes require approval
- Destructive changes show estimated violations

### 3. Schema Discovery

Automatically detect patterns in incoming data:
- New classes/properties from unknown predicates
- Property ranges from value distributions
- Cardinality patterns

### 4. Governance Workflows

Configure approval requirements:
```python
{
    "impact_mode": "advisory",
    "auto_apply_safe": True,
    "approval_required_for": ["breaking", "destructive"],
    "approvers": ["risk-manager@finco.com"]
}
```

### 5. Schema Conversation

Interactive chat for schema evolution:
```
> I want to model cryptocurrency trading
> What crypto classes do we have?
> Add a WalletAddress property to Cryptocurrency
```

## Example Queries

### Get all portfolios with their risk metrics

```sparql
PREFIX fin: <http://tesserai.io/ontology/finance#>

SELECT ?portfolio ?name ?var ?exposure
WHERE {
    ?portfolio a fin:Portfolio ;
               fin:name ?name .
    OPTIONAL {
        ?portfolio fin:hasRiskMetric ?metric .
        ?metric fin:valueAtRisk ?var ;
                fin:totalExposure ?exposure .
    }
}
```

### Find positions exceeding risk limits

```sparql
PREFIX fin: <http://tesserai.io/ontology/finance#>

SELECT ?portfolio ?position ?value ?limit
WHERE {
    ?portfolio fin:hasPosition ?position ;
               fin:hasRiskLimit ?limitDef .
    ?position fin:marketValue ?value .
    ?limitDef fin:maxValue ?limit .
    FILTER (?value > ?limit)
}
```

### Get trading desk performance

```sparql
PREFIX fin: <http://tesserai.io/ontology/finance#>

SELECT ?desk ?deskName (SUM(?pnl) as ?totalPnL)
WHERE {
    ?desk a fin:TradingDesk ;
          fin:name ?deskName ;
          fin:hasOrder ?order .
    ?order fin:realizedPnL ?pnl .
}
GROUP BY ?desk ?deskName
ORDER BY DESC(?totalPnL)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DTAAS_URL` | `http://localhost:8080` | Server URL |
| `DTAAS_TOKEN` | `finance-demo` | API token (tenant ID) |

## LLM Configuration

For natural language features, configure an LLM provider in `config.toml`:

```toml
[llm]
enabled = true

[llm.primary]
provider = "ollama"
base_url = "http://localhost:11434"
model = "llama3.2"

# Or use OpenAI
[llm.primary]
provider = "openai"
api_key = "sk-..."
model = "gpt-4"
```

## Related Examples

- `automotive/` - Fleet and vehicle management
- `robotics/` - Industrial automation
- `supply_chain/` - Logistics and inventory
- `healthcare/` - Patient and device monitoring
