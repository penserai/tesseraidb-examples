# Transfer Pricing Example

A comprehensive transfer pricing documentation system demonstrating TesseraiDB's capabilities for IRS-compliant multinational enterprise documentation, intercompany transaction analysis, and regulatory compliance.

## Overview

- What this domain models: Multinational enterprise structure with legal entities, intercompany transactions, comparability analysis, and transfer pricing documentation
- Key entities and relationships: Multinational groups, legal entities (parent/subsidiaries), intercompany transactions, transfer pricing methods, comparable companies, and documentation
- Real-world use cases: Transfer pricing documentation, IRS Section 482 compliance, BEPS Action 13 reporting, arm's length analysis, penalty protection

## Prerequisites

- TesseraiDB account at [tesserai.io](https://tesserai.io)
- Set your API key: `export TESSERAI_API_KEY="your-api-key"`
- Python 3.10+ with the TesseraiDB SDK: `pip install tesserai`

## Quick Start

```bash
# Seed the example data
python seed.py

# Run the report generator (requires streamlit)
pip install streamlit httpx pandas plotly
streamlit run report_generator.py

# Run the Phase 13 adaptive schema demo
python demo_phase13.py
```

## Digital Twins

List of main twin types created:

- **MultinationalGroup**: Top-level enterprise group
- **LegalEntity**: Legal entities (ParentCompany, Subsidiary, Branch)
- **GoodsTransaction**: Intercompany goods sales
- **ServicesTransaction**: Management and technical services
- **IPLicenseTransaction**: Intellectual property royalties
- **FinancingTransaction**: Intercompany loans
- **TransferPricingMethod**: CUP, TNMM, Cost Plus, etc.
- **ComparableCompany**: Benchmark comparable companies
- **ArmLengthRange**: Interquartile ranges
- **PrincipalDocument**: IRS-required principal documents
- **BackgroundDocument**: Supporting documentation

## Ontology

The taxation ontology defines:

- **Entity hierarchy**: MultinationalGroup -> LegalEntity (Parent, Subsidiary, Branch)
- **Transaction types**: Goods, Services, IP License, Financing, Cost Sharing
- **Method classes**: CUP, Resale Price, Cost Plus, TNMM, Profit Split
- **Documentation**: Principal Document, Background Document, Local File, Master File, CbCR

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

## API Usage Examples

```python
from common import get_client

client = get_client()

# Get all intercompany transactions by type
transactions = client.sparql.query("""
    PREFIX tax: <http://tesserai.io/ontology/taxation#>
    SELECT ?txn ?type ?value ?method WHERE {
        ?txn a ?type ;
             tax:transactionValue ?value ;
             tax:usesMethod ?methodEntity .
        ?methodEntity tax:methodName ?method .
        FILTER (?type != owl:NamedIndividual)
    }
    ORDER BY DESC(?value)
""")

# Find transactions outside arm's length range
breaches = client.sparql.query("""
    PREFIX tax: <http://tesserai.io/ontology/taxation#>
    SELECT ?entity ?margin ?lq ?uq WHERE {
        ?entity a tax:Subsidiary ;
                tax:operatingMargin ?margin .
        ?range a tax:ArmLengthRange ;
               tax:functionalProfile "Limited Risk Distributor" ;
               tax:lowerQuartile ?lq ;
               tax:upperQuartile ?uq .
        FILTER (?margin < ?lq || ?margin > ?uq)
    }
""")

# Get documentation coverage by transaction
coverage = client.sparql.query("""
    PREFIX tax: <http://tesserai.io/ontology/taxation#>
    SELECT ?txn ?txnValue (COUNT(?doc) as ?docCount) WHERE {
        ?txn a tax:IntercompanyTransaction ;
             tax:transactionValue ?txnValue .
        OPTIONAL { ?doc tax:documentsTransaction ?txn }
    }
    GROUP BY ?txn ?txnValue
    ORDER BY DESC(?txnValue)
""")
```

## Additional Features

### Report Generator

The Streamlit application provides:

- **Entity Structure Tab**: View multinational group hierarchy
- **Transactions Tab**: List and analyze intercompany transactions
- **Benchmarking Tab**: Comparable companies and arm's length ranges
- **Background Documents Tab**: View source documents
- **Generate Report Tab**: One-click IRS-compliant Principal Document generation

### Phase 13 Adaptive Schema

Demonstrates strict governance for tax-sensitive schema changes:

- Approval-required workflows for all schema modifications
- Impact analysis before applying changes
- Natural language schema editing for regulatory concepts
- Schema discovery for transaction patterns

### Regulatory References

- IRC Section 482: Allocation of income among related entities
- Treasury Reg. 1.482-1: General principles and methods
- Treasury Reg. 1.6662-6: Penalty protection requirements
- OECD Transfer Pricing Guidelines
- BEPS Action 13: Country-by-country reporting

## License

Apache License 2.0 - See [LICENSE](../LICENSE)
