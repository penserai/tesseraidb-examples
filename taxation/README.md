# Transfer Pricing Example

This example demonstrates DTaaS capabilities for IRS-compliant transfer pricing documentation, focusing on the generation of Principal Documents from background data.

## Overview

Transfer pricing documentation is required for multinational enterprises with intercompany transactions. This example models:

- **Multinational Group Structure**: Legal entities across jurisdictions
- **Intercompany Transactions**: Goods, services, IP licensing, financing
- **Comparability Analysis**: Comparable companies and arm's length ranges
- **Documentation**: Principal documents and background documents
- **Compliance**: IRS Section 482 and Treasury Regulations

## Scenario: TechGlobal Inc.

The example models a technology multinational with:

| Entity | Jurisdiction | Functional Profile |
|--------|--------------|-------------------|
| TechGlobal Inc. | US | Full-Fledged Manufacturer (Parent) |
| TechGlobal Ireland Ltd. | Ireland | Limited Risk Distributor |
| TechGlobal Germany GmbH | Germany | Contract Manufacturer |
| TechGlobal Asia Pacific | Singapore | Regional Service Provider |
| TechGlobal IP Holdings | Cayman Islands | IP Holding Company |
| TechGlobal Japan K.K. | Japan | Limited Risk Distributor |

### Intercompany Transactions

| Transaction Type | Flow | Method | FY2024 Value |
|-----------------|------|--------|--------------|
| Goods Sales | US → Ireland | TNMM | $850M |
| Components | Germany → Ireland | Cost Plus | EUR 180M |
| IP Royalties | Cayman → US | CUP | $96M |
| IP Royalties | Cayman → Ireland | CUP | $48M |
| Management Services | Singapore → Japan | Cost Plus | $12.5M |
| Technical Services | US → All | Cost Plus | $45M |
| Intercompany Loan | US → Germany | CUP | $4.5M (interest) |

## Files

| File | Description |
|------|-------------|
| `seed.py` | Seed transfer pricing data into DTaaS |
| `report_generator.py` | Streamlit UI for generating Principal Documents |
| `demo_phase13.py` | Demonstrate Phase 13 adaptive schema features |
| `../ontologies/taxation.ttl` | Transfer pricing ontology (OWL + SHACL) |

## Quick Start

### 1. Start the Server

```bash
cargo run --release
```

### 2. Load the Ontology

```bash
curl -X POST http://localhost:8080/api/v1/ontologies/taxation \
  -H "Authorization: Bearer taxation-demo" \
  -H "Content-Type: text/turtle" \
  --data-binary @examples/ontologies/taxation.ttl
```

### 3. Seed Transfer Pricing Data

```bash
cd examples/taxation
python seed.py
```

### 4. Run the Report Generator

```bash
pip install streamlit httpx pandas plotly
streamlit run report_generator.py
```

Access the UI at http://localhost:8501

### 5. Run the Phase 13 Demo

```bash
python demo_phase13.py
```

## Report Generator Features

The Streamlit application provides:

### Entity Structure Tab
- View multinational group hierarchy
- Legal entity details and functional profiles
- Organizational chart visualization

### Transactions Tab
- List all intercompany transactions
- Transaction value breakdown by type (pie chart)
- Detailed transaction information

### Benchmarking Tab
- Comparable companies by functional profile
- Operating margin distributions (box plots)
- Arm's length ranges (interquartile)

### Background Documents Tab
- View source documents (price lists, invoices, financials)
- Document content preview
- Metadata and status

### Generate Report Tab
- One-click Principal Document generation
- IRS-compliant format
- Download as Markdown

## IRS Documentation Requirements

### Principal Documents (30-day rule)

Must be provided within 30 days of IRS request:

1. Overview of taxpayer's business
2. Organizational structure description
3. Documentation of transfer pricing method
4. Description of controlled transactions
5. Description of comparables used
6. Economic analysis
7. Index of principal and background documents

### Background Documents

Provided upon specific request:

- Intercompany agreements
- Price lists and invoices
- Financial statements
- Loan agreements
- License agreements
- Comparability search results

## Penalty Protection

Proper documentation provides protection under IRC Section 6662(e):

| Penalty Type | Rate | Protection Requirement |
|--------------|------|----------------------|
| Substantial Valuation Misstatement | 20% | Contemporaneous documentation |
| Gross Valuation Misstatement | 40% | Contemporaneous documentation |

Documentation must be prepared by the tax return due date to qualify as "contemporaneous."

## Domain Model

### Core Classes

```
MultinationalGroup
  |-- LegalEntity
        |-- ParentCompany
        |-- Subsidiary
        |-- Branch

IntercompanyTransaction
  |-- GoodsTransaction
  |-- ServicesTransaction
  |     |-- ManagementFee
  |     |-- TechnicalServiceFee
  |-- IPLicenseTransaction
  |-- FinancingTransaction
  |-- CostSharingArrangement

TransferPricingMethod
  |-- CUPMethod
  |-- ResalePriceMethod
  |-- CostPlusMethod
  |-- TNMMMethod
  |-- ProfitSplitMethod

ComparabilityAnalysis
  |-- ComparableCompany
  |-- ComparableTransaction
  |-- ArmLengthRange

TransferPricingDocumentation
  |-- PrincipalDocument
  |-- BackgroundDocument
  |-- LocalFile
  |-- MasterFile
  |-- CountryByCountryReport
```

### Key Relationships

- `belongsToGroup`: Entity → MultinationalGroup
- `hasSubsidiary`: Parent → Subsidiary
- `locatedIn`: Entity → Jurisdiction
- `payer`: Transaction → Entity
- `payee`: Transaction → Entity
- `usesMethod`: Transaction → Method
- `hasComparable`: Analysis → ComparableCompany
- `hasArmLengthRange`: Analysis → ArmLengthRange
- `documentsTransaction`: Documentation → Transaction

## Phase 13 Features

The `demo_phase13.py` script demonstrates:

### Schema Governance
Configure strict governance for tax-sensitive schema changes:
```python
{
    "impact_mode": "blocking",
    "auto_apply_safe": False,
    "approval_required_for": ["additive", "breaking", "destructive"],
    "approvers": ["tax-director@company.com", "legal@company.com"]
}
```

### Impact Analysis
Analyze impact of schema changes before applying:
- Adding new transaction types (safe)
- Adding required documentation fields (breaking)
- Modifying arm's length range constraints

### Natural Language Schema Editing
Add regulatory concepts using plain English:
```
"Add a BEPS Action 13 Country-by-Country Report class with
properties for revenue, profit before tax, and employees by jurisdiction"
```

### Schema Discovery
Detect patterns in transaction data:
- Identify common property ranges (royalty rates)
- Discover implicit relationships
- Suggest schema improvements

## Example Queries

### Get all intercompany transactions by type

```sparql
PREFIX tax: <http://tesserai.io/ontology/taxation#>

SELECT ?txn ?type ?value ?method
WHERE {
    ?txn a ?type ;
         tax:transactionValue ?value ;
         tax:usesMethod ?methodEntity .
    ?methodEntity tax:methodName ?method .
    FILTER (?type != owl:NamedIndividual)
}
ORDER BY DESC(?value)
```

### Find transactions outside arm's length range

```sparql
PREFIX tax: <http://tesserai.io/ontology/taxation#>

SELECT ?entity ?margin ?lq ?uq
WHERE {
    ?entity a tax:Subsidiary ;
            tax:operatingMargin ?margin .
    ?range a tax:ArmLengthRange ;
           tax:functionalProfile "Limited Risk Distributor" ;
           tax:lowerQuartile ?lq ;
           tax:upperQuartile ?uq .
    FILTER (?margin < ?lq || ?margin > ?uq)
}
```

### Get documentation coverage by transaction

```sparql
PREFIX tax: <http://tesserai.io/ontology/taxation#>

SELECT ?txn ?txnValue (COUNT(?doc) as ?docCount)
WHERE {
    ?txn a tax:IntercompanyTransaction ;
         tax:transactionValue ?txnValue .
    OPTIONAL { ?doc tax:documentsTransaction ?txn }
}
GROUP BY ?txn ?txnValue
ORDER BY DESC(?txnValue)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DTAAS_URL` | `http://localhost:8080` | Server URL |
| `DTAAS_TOKEN` | `taxation-demo` | API token (tenant ID) |

## Regulatory References

- **IRC Section 482**: Allocation of income among related entities
- **Treasury Reg. 1.482-1**: General principles and methods
- **Treasury Reg. 1.6662-6**: Penalty protection requirements
- **OECD Transfer Pricing Guidelines**: International standards
- **BEPS Action 13**: Country-by-country reporting
- **Pillar Two**: Global minimum tax (15%)

## LLM Configuration

For natural language features, configure in `config.toml`:

```toml
[llm]
enabled = true

[llm.primary]
provider = "ollama"
base_url = "http://localhost:11434"
model = "llama3.2"
```

## Related Examples

- `finance/` - Financial services and trading
- `supply_chain/` - Global supply chain
- `healthcare/` - HIPAA-compliant healthcare
