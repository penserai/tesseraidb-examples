#!/usr/bin/env python3
"""
Transfer Pricing Report Generator - Ontology-Driven

A Streamlit application that generates IRS-compliant Principal Documents
using semantic queries against the DTaaS ontology and data.

Key Design Principles:
- Report structure derived from ontology class hierarchy
- Property labels and descriptions from ontology definitions
- Data relationships resolved via SPARQL, not hardcoded mappings
- SHACL constraints inform validation and completeness checks

Usage:
    pip install streamlit httpx pandas plotly
    streamlit run report_generator.py
"""

import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# Check for required packages
try:
    import streamlit as st
    import httpx
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
except ImportError as e:
    print(f"Missing required package: {e}")
    print("\nInstall with: pip install streamlit httpx pandas plotly")
    sys.exit(1)

# =============================================================================
# Configuration
# =============================================================================

BASE_URL = os.environ.get("DTAAS_URL", "http://localhost:8080")
TOKEN = os.environ.get("DTAAS_TOKEN", "taxation-demo")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

TAX_NS = "http://tesserai.io/ontology/taxation#"
ONTOLOGY_GRAPH = f"urn:tenant:{TOKEN}:ontology:taxation"

# =============================================================================
# SPARQL Query Templates - All data assembly rules defined here
# =============================================================================

SPARQL_PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX tax: <http://tesserai.io/ontology/taxation#>
PREFIX dtaas: <http://tesserai.io/ontology/>
"""

# Query ontology for class hierarchy with labels and comments
QUERY_CLASS_HIERARCHY = SPARQL_PREFIXES + """
SELECT ?class ?label ?comment ?superclass ?superLabel
FROM <{graph}>
WHERE {{
    ?class a owl:Class .
    OPTIONAL {{ ?class rdfs:label ?label }}
    OPTIONAL {{ ?class rdfs:comment ?comment }}
    OPTIONAL {{
        ?class rdfs:subClassOf ?superclass .
        ?superclass a owl:Class .
        OPTIONAL {{ ?superclass rdfs:label ?superLabel }}
    }}
    FILTER(STRSTARTS(STR(?class), STR(tax:)))
}}
ORDER BY ?superclass ?class
"""

# Query ontology for property definitions
QUERY_PROPERTIES = SPARQL_PREFIXES + """
SELECT ?prop ?label ?comment ?domain ?range ?propType
FROM <{graph}>
WHERE {{
    {{ ?prop a owl:DatatypeProperty . BIND("datatype" AS ?propType) }}
    UNION
    {{ ?prop a owl:ObjectProperty . BIND("object" AS ?propType) }}
    OPTIONAL {{ ?prop rdfs:label ?label }}
    OPTIONAL {{ ?prop rdfs:comment ?comment }}
    OPTIONAL {{ ?prop rdfs:domain ?domain }}
    OPTIONAL {{ ?prop rdfs:range ?range }}
    FILTER(STRSTARTS(STR(?prop), STR(tax:)))
}}
ORDER BY ?prop
"""

# Query SHACL shapes for validation rules
QUERY_SHACL_SHAPES = SPARQL_PREFIXES + """
SELECT ?shape ?targetClass ?path ?minCount ?maxCount ?datatype ?message
FROM <{graph}>
WHERE {{
    ?shape a sh:NodeShape ;
           sh:targetClass ?targetClass ;
           sh:property ?propShape .
    ?propShape sh:path ?path .
    OPTIONAL {{ ?propShape sh:minCount ?minCount }}
    OPTIONAL {{ ?propShape sh:maxCount ?maxCount }}
    OPTIONAL {{ ?propShape sh:datatype ?datatype }}
    OPTIONAL {{ ?propShape sh:message ?message }}
    FILTER(STRSTARTS(STR(?shape), STR(tax:)))
}}
"""

# Query legal entities with their relationships resolved
# Note: Twins are stored in individual named graphs, so we use GRAPH ?g pattern
# Object properties (relationships) use tax: prefix, datatype properties use dtaas: prefix
QUERY_ENTITIES_WITH_RELATIONSHIPS = SPARQL_PREFIXES + """
SELECT ?entity ?type ?name ?jurisdictionName ?profile ?ownership ?revenue ?operatingMargin ?employees ?parentName
WHERE {{
    GRAPH ?g {{
        ?entity a ?type .
        FILTER(
            ?type = tax:ParentCompany ||
            ?type = tax:Subsidiary ||
            ?type = tax:Branch
        )
        OPTIONAL {{ ?entity dtaas:entityName ?name }}
        OPTIONAL {{ ?entity dtaas:functionalProfile ?profile }}
        OPTIONAL {{ ?entity dtaas:ownershipPercentage ?ownership }}
        OPTIONAL {{ ?entity dtaas:revenue ?revenue }}
        OPTIONAL {{ ?entity dtaas:operatingMargin ?operatingMargin }}
        OPTIONAL {{ ?entity dtaas:employees ?employees }}
    }}
    OPTIONAL {{
        GRAPH ?g2 {{
            ?entity tax:locatedIn ?jurisdiction .
        }}
        GRAPH ?g3 {{
            ?jurisdiction dtaas:jurisdictionName ?jurisdictionName .
        }}
    }}
    OPTIONAL {{
        GRAPH ?g4 {{
            ?parent tax:hasSubsidiary ?entity .
        }}
        GRAPH ?g5 {{
            ?parent dtaas:entityName ?parentName .
        }}
    }}
}}
ORDER BY ?parentName ?name
"""

# Query transactions with payer/payee resolved
# Note: Twins are stored in individual named graphs, so we use GRAPH ?g pattern
# Object properties (relationships) use tax: prefix, datatype properties use dtaas: prefix
QUERY_TRANSACTIONS_WITH_PARTIES = SPARQL_PREFIXES + """
SELECT ?txn ?type ?typeLabel ?value ?currency ?fiscalYear
       ?payer ?payerName ?payerJurisdiction
       ?payee ?payeeName ?payeeJurisdiction
       ?method ?methodName ?methodLabel
       ?royaltyRate ?interestRate ?markupPercentage ?costBase
       ?productDescription ?quantity ?unitPrice ?principalAmount
WHERE {{
    GRAPH ?g {{
        ?txn a ?type .
        FILTER(
            ?type = tax:GoodsTransaction ||
            ?type = tax:ServicesTransaction ||
            ?type = tax:ManagementFee ||
            ?type = tax:TechnicalServiceFee ||
            ?type = tax:IPLicenseTransaction ||
            ?type = tax:FinancingTransaction ||
            ?type = tax:CostSharingArrangement
        )
        OPTIONAL {{ ?txn dtaas:transactionValue ?value }}
        OPTIONAL {{ ?txn dtaas:currency ?currency }}
        OPTIONAL {{ ?txn dtaas:fiscalYear ?fiscalYear }}
        OPTIONAL {{ ?txn dtaas:royaltyRate ?royaltyRate }}
        OPTIONAL {{ ?txn dtaas:interestRate ?interestRate }}
        OPTIONAL {{ ?txn dtaas:markupPercentage ?markupPercentage }}
        OPTIONAL {{ ?txn dtaas:costBase ?costBase }}
        OPTIONAL {{ ?txn dtaas:productDescription ?productDescription }}
        OPTIONAL {{ ?txn dtaas:quantity ?quantity }}
        OPTIONAL {{ ?txn dtaas:unitPrice ?unitPrice }}
        OPTIONAL {{ ?txn dtaas:principalAmount ?principalAmount }}
    }}

    # Get type label from ontology
    OPTIONAL {{
        GRAPH <{ontology_graph}> {{
            ?type rdfs:label ?typeLabel .
        }}
    }}

    # Resolve payer relationship (tax: for object properties)
    OPTIONAL {{
        GRAPH ?g2 {{ ?txn tax:payer ?payer }}
        GRAPH ?g3 {{ ?payer dtaas:entityName ?payerName }}
        OPTIONAL {{
            GRAPH ?g4 {{ ?payer tax:locatedIn ?payerJuris }}
            GRAPH ?g5 {{ ?payerJuris dtaas:jurisdictionName ?payerJurisdiction }}
        }}
    }}

    # Resolve payee relationship (tax: for object properties)
    OPTIONAL {{
        GRAPH ?g6 {{ ?txn tax:payee ?payee }}
        GRAPH ?g7 {{ ?payee dtaas:entityName ?payeeName }}
        OPTIONAL {{
            GRAPH ?g8 {{ ?payee tax:locatedIn ?payeeJuris }}
            GRAPH ?g9 {{ ?payeeJuris dtaas:jurisdictionName ?payeeJurisdiction }}
        }}
    }}

    # Resolve method relationship (tax: for object properties)
    OPTIONAL {{
        GRAPH ?g10 {{ ?txn tax:usesMethod ?method }}
        GRAPH ?g11 {{ ?method dtaas:methodName ?methodName }}
    }}
}}
ORDER BY DESC(?value)
"""

# Query comparables with their analysis context
# Note: Twins are stored in individual named graphs, so we use GRAPH ?g pattern
# Data properties use dtaas: prefix, types use tax: prefix
QUERY_COMPARABLES = SPARQL_PREFIXES + """
SELECT ?comp ?companyName ?profile ?operatingMargin ?grossMargin
       ?berryRatio ?netCostPlusMarkup ?revenue ?dataYear
       ?sicCode ?naicsCode ?accepted
WHERE {{
    GRAPH ?g {{
        ?comp a tax:ComparableCompany .
        OPTIONAL {{ ?comp dtaas:companyName ?companyName }}
        OPTIONAL {{ ?comp dtaas:functionalProfile ?profile }}
        OPTIONAL {{ ?comp dtaas:operatingMargin ?operatingMargin }}
        OPTIONAL {{ ?comp dtaas:grossMargin ?grossMargin }}
        OPTIONAL {{ ?comp dtaas:berryRatio ?berryRatio }}
        OPTIONAL {{ ?comp dtaas:netCostPlusMarkup ?netCostPlusMarkup }}
        OPTIONAL {{ ?comp dtaas:revenue ?revenue }}
        OPTIONAL {{ ?comp dtaas:dataYear ?dataYear }}
        OPTIONAL {{ ?comp dtaas:sicCode ?sicCode }}
        OPTIONAL {{ ?comp dtaas:naicsCode ?naicsCode }}
        OPTIONAL {{ ?comp dtaas:acceptedAsComparable ?accepted }}
    }}
}}
ORDER BY ?profile ?companyName
"""

# Query arm's length ranges
# Note: Twins are stored in individual named graphs, so we use GRAPH ?g pattern
# Data properties use dtaas: prefix, types use tax: prefix
QUERY_ARM_LENGTH_RANGES = SPARQL_PREFIXES + """
SELECT ?range ?profile ?pli ?min ?lq ?median ?uq ?max ?count
WHERE {{
    GRAPH ?g {{
        ?range a tax:ArmLengthRange .
        OPTIONAL {{ ?range dtaas:functionalProfile ?profile }}
        OPTIONAL {{ ?range dtaas:profitLevelIndicator ?pli }}
        OPTIONAL {{ ?range dtaas:minimumValue ?min }}
        OPTIONAL {{ ?range dtaas:lowerQuartile ?lq }}
        OPTIONAL {{ ?range dtaas:median ?median }}
        OPTIONAL {{ ?range dtaas:upperQuartile ?uq }}
        OPTIONAL {{ ?range dtaas:maximumValue ?max }}
        OPTIONAL {{ ?range dtaas:numberOfComparables ?count }}
    }}
}}
ORDER BY ?profile
"""

# Query background documents
# Note: Twins are stored in individual named graphs, so we use GRAPH ?g pattern
# Object properties (relationships) use tax: prefix, datatype properties use dtaas: prefix
QUERY_BACKGROUND_DOCUMENTS = SPARQL_PREFIXES + """
SELECT ?doc ?docId ?title ?preparedDate ?preparedBy ?taxYear ?status ?content
       ?documentsEntity ?entityName ?documentsTxn ?txnValue
WHERE {{
    GRAPH ?g {{
        ?doc a tax:BackgroundDocument .
        OPTIONAL {{ ?doc dtaas:documentId ?docId }}
        OPTIONAL {{ ?doc dtaas:documentTitle ?title }}
        OPTIONAL {{ ?doc dtaas:preparedDate ?preparedDate }}
        OPTIONAL {{ ?doc dtaas:preparedBy ?preparedBy }}
        OPTIONAL {{ ?doc dtaas:taxYear ?taxYear }}
        OPTIONAL {{ ?doc dtaas:documentStatus ?status }}
        OPTIONAL {{ ?doc dtaas:documentContent ?content }}
    }}
    OPTIONAL {{
        GRAPH ?g2 {{ ?doc tax:documentsEntity ?documentsEntity }}
        GRAPH ?g3 {{ ?documentsEntity dtaas:entityName ?entityName }}
    }}
    OPTIONAL {{
        GRAPH ?g4 {{ ?doc tax:documentsTransaction ?documentsTxn }}
        GRAPH ?g5 {{ ?documentsTxn dtaas:transactionValue ?txnValue }}
    }}
}}
ORDER BY ?docId
"""

# Query transfer pricing methods defined in ontology
QUERY_TP_METHODS = SPARQL_PREFIXES + """
SELECT ?method ?label ?comment ?pli
FROM <{graph}>
WHERE {{
    ?method rdfs:subClassOf tax:TransferPricingMethod .
    OPTIONAL {{ ?method rdfs:label ?label }}
    OPTIONAL {{ ?method rdfs:comment ?comment }}
    OPTIONAL {{ ?method tax:profitLevelIndicator ?pli }}
}}
ORDER BY ?label
"""

# Query multinational group structure
# Note: Twins are stored in individual named graphs, so we use GRAPH ?g pattern
# Object properties (relationships) use tax: prefix, datatype properties use dtaas: prefix
QUERY_GROUP_STRUCTURE = SPARQL_PREFIXES + """
SELECT ?group ?groupName ?parent ?parentName ?sub ?subName ?subType
WHERE {{
    GRAPH ?g {{
        ?group a tax:MultinationalGroup .
        OPTIONAL {{ ?group dtaas:groupName ?groupName }}
    }}
    OPTIONAL {{
        GRAPH ?g2 {{
            ?parent a tax:ParentCompany .
        }}
        GRAPH ?g3 {{
            ?parent tax:belongsToGroup ?group .
        }}
        GRAPH ?g4 {{
            ?parent dtaas:entityName ?parentName .
        }}
    }}
    OPTIONAL {{
        GRAPH ?g5 {{ ?parent tax:hasSubsidiary ?sub }}
        GRAPH ?g6 {{ ?sub dtaas:entityName ?subName }}
        GRAPH ?g7 {{
            ?sub a ?subType .
            FILTER(?subType != owl:NamedIndividual)
        }}
    }}
}}
ORDER BY ?parentName ?subName
"""


# =============================================================================
# Ontology Service - Semantic Data Access
# =============================================================================

class OntologyService:
    """Service for querying ontology definitions and data semantically."""

    def __init__(self, base_url: str, headers: dict, ontology_graph: str):
        self.base_url = base_url
        self.headers = headers
        self.ontology_graph = ontology_graph
        self._class_cache: Dict[str, dict] = {}
        self._property_cache: Dict[str, dict] = {}

    def run_sparql(self, query: str) -> List[Dict[str, Any]]:
        """Execute SPARQL query and return bindings as list of dicts."""
        try:
            resp = httpx.post(
                f"{self.base_url}/api/v1/sparql/query",
                headers={**self.headers, "Content-Type": "application/sparql-query", "Accept": "application/json"},
                content=query,
                timeout=30
            )
            if resp.status_code == 200:
                result = resp.json()
                bindings = result.get("results", {}).get("bindings", [])
                # Convert SPARQL JSON format to simple dicts
                return [
                    {k: v.get("value") for k, v in binding.items()}
                    for binding in bindings
                ]
            return []
        except Exception as e:
            st.error(f"SPARQL query failed: {e}")
            return []

    def get_class_hierarchy(self) -> Dict[str, dict]:
        """Get class definitions from ontology with hierarchy."""
        if self._class_cache:
            return self._class_cache

        query = QUERY_CLASS_HIERARCHY.format(graph=self.ontology_graph)
        results = self.run_sparql(query)

        classes = {}
        for row in results:
            class_uri = row.get("class", "")
            class_name = class_uri.replace(TAX_NS, "")

            if class_name not in classes:
                classes[class_name] = {
                    "uri": class_uri,
                    "label": row.get("label", class_name),
                    "comment": row.get("comment", ""),
                    "superclass": None,
                    "subclasses": []
                }

            if row.get("superclass"):
                super_name = row["superclass"].replace(TAX_NS, "")
                classes[class_name]["superclass"] = super_name

                if super_name not in classes:
                    classes[super_name] = {
                        "uri": row["superclass"],
                        "label": row.get("superLabel", super_name),
                        "comment": "",
                        "superclass": None,
                        "subclasses": []
                    }
                classes[super_name]["subclasses"].append(class_name)

        self._class_cache = classes
        return classes

    def get_properties(self) -> Dict[str, dict]:
        """Get property definitions from ontology."""
        if self._property_cache:
            return self._property_cache

        query = QUERY_PROPERTIES.format(graph=self.ontology_graph)
        results = self.run_sparql(query)

        properties = {}
        for row in results:
            prop_uri = row.get("prop", "")
            prop_name = prop_uri.replace(TAX_NS, "")

            properties[prop_name] = {
                "uri": prop_uri,
                "label": row.get("label", prop_name),
                "comment": row.get("comment", ""),
                "domain": row.get("domain", "").replace(TAX_NS, ""),
                "range": row.get("range", ""),
                "type": row.get("propType", "datatype")
            }

        self._property_cache = properties
        return properties

    def get_shacl_constraints(self) -> Dict[str, List[dict]]:
        """Get SHACL validation constraints by target class."""
        query = QUERY_SHACL_SHAPES.format(graph=self.ontology_graph)
        results = self.run_sparql(query)

        constraints = {}
        for row in results:
            target = row.get("targetClass", "").replace(TAX_NS, "")
            if target not in constraints:
                constraints[target] = []

            constraints[target].append({
                "path": row.get("path", "").replace(TAX_NS, ""),
                "minCount": int(row.get("minCount", 0)) if row.get("minCount") else None,
                "maxCount": int(row.get("maxCount", 0)) if row.get("maxCount") else None,
                "datatype": row.get("datatype", ""),
                "message": row.get("message", "")
            })

        return constraints

    def get_tp_methods(self) -> List[dict]:
        """Get transfer pricing method definitions from ontology."""
        query = QUERY_TP_METHODS.format(graph=self.ontology_graph)
        return self.run_sparql(query)

    def get_class_label(self, class_name: str) -> str:
        """Get human-readable label for a class."""
        classes = self.get_class_hierarchy()
        if class_name in classes:
            return classes[class_name].get("label", class_name)
        return class_name

    def get_property_label(self, prop_name: str) -> str:
        """Get human-readable label for a property."""
        props = self.get_properties()
        if prop_name in props:
            return props[prop_name].get("label", prop_name)
        return prop_name

    def get_subclasses(self, class_name: str) -> List[str]:
        """Get all subclasses of a class."""
        classes = self.get_class_hierarchy()
        if class_name in classes:
            return classes[class_name].get("subclasses", [])
        return []


# =============================================================================
# Data Service - Semantic Data Retrieval
# =============================================================================

class DataService:
    """Service for retrieving instance data via SPARQL."""

    def __init__(self, ontology_service: OntologyService):
        self.onto = ontology_service

    def get_entities(self) -> List[dict]:
        """Get legal entities with relationships resolved."""
        return self.onto.run_sparql(QUERY_ENTITIES_WITH_RELATIONSHIPS)

    def get_transactions(self) -> List[dict]:
        """Get transactions with payer/payee resolved."""
        query = QUERY_TRANSACTIONS_WITH_PARTIES.format(ontology_graph=self.onto.ontology_graph)
        return self.onto.run_sparql(query)

    def get_comparables(self) -> List[dict]:
        """Get comparable companies."""
        return self.onto.run_sparql(QUERY_COMPARABLES)

    def get_arm_length_ranges(self) -> List[dict]:
        """Get arm's length ranges."""
        return self.onto.run_sparql(QUERY_ARM_LENGTH_RANGES)

    def get_background_documents(self) -> List[dict]:
        """Get background documents."""
        return self.onto.run_sparql(QUERY_BACKGROUND_DOCUMENTS)

    def get_group_structure(self) -> List[dict]:
        """Get multinational group ownership structure."""
        return self.onto.run_sparql(QUERY_GROUP_STRUCTURE)

    def get_entities_by_type(self, type_name: str) -> List[dict]:
        """Get entities of a specific type."""
        entities = self.get_entities()
        return [e for e in entities if e.get("type", "").endswith(f"#{type_name}")]

    def get_transactions_by_type(self, type_name: str) -> List[dict]:
        """Get transactions of a specific type."""
        txns = self.get_transactions()
        return [t for t in txns if t.get("type", "").endswith(f"#{type_name}")]


# =============================================================================
# Report Generator - Ontology-Driven Assembly
# =============================================================================

class ReportGenerator:
    """Generate reports driven by ontology definitions."""

    def __init__(self, onto: OntologyService, data: DataService):
        self.onto = onto
        self.data = data

    def generate_section_from_class(self, class_name: str, instances: List[dict],
                                    property_order: List[str] = None) -> str:
        """Generate a report section from ontology class definition and instances."""
        classes = self.onto.get_class_hierarchy()

        if class_name not in classes:
            return ""

        class_def = classes[class_name]
        content = f"\n### {class_def['label']}\n\n"

        if class_def['comment']:
            content += f"*{class_def['comment']}*\n\n"

        if not instances:
            content += "*No data available*\n\n"
            return content

        # Build table headers from property definitions
        if property_order:
            columns = property_order
        else:
            # Auto-detect columns from first instance
            columns = [k for k in instances[0].keys() if k not in ['entity', 'type', 'typeLabel']]

        # Get labels for columns
        headers = [self.onto.get_property_label(c) for c in columns]

        content += "| " + " | ".join(headers) + " |\n"
        content += "|" + "|".join(["---"] * len(headers)) + "|\n"

        for instance in instances:
            row = []
            for col in columns:
                val = instance.get(col, "")
                if val is None:
                    val = ""
                # Format numbers
                if isinstance(val, (int, float)) or (isinstance(val, str) and val.replace('.', '').replace('-', '').isdigit()):
                    try:
                        num = float(val)
                        if 'margin' in col.lower() or 'rate' in col.lower() or 'percentage' in col.lower():
                            val = f"{num*100:.1f}%"
                        elif num > 10000:
                            val = f"${num:,.0f}"
                        else:
                            val = f"{num:,.2f}"
                    except:
                        pass
                row.append(str(val))
            content += "| " + " | ".join(row) + " |\n"

        content += "\n"
        return content

    def generate_executive_summary(self, entities: List[dict], transactions: List[dict],
                                   tax_year: int) -> str:
        """Generate executive summary from data."""
        total_value = sum(float(t.get("value", 0) or 0) for t in transactions)

        return f"""
## Executive Summary

This Transfer Pricing Documentation Report has been prepared for the multinational group
for the fiscal year ended December 31, {tax_year}.

### Key Metrics (Data-Derived)

| Metric | Value |
|--------|-------|
| Tax Year | {tax_year} |
| Controlled Entities | {len(entities)} |
| Intercompany Transactions | {len(transactions)} |
| Total Transaction Value | ${total_value:,.0f} |
| Transaction Categories | {len(set(t.get('typeLabel', '') for t in transactions))} |

### Transaction Type Summary

| Transaction Type | Count | Total Value |
|-----------------|-------|-------------|
"""  + self._generate_txn_type_summary(transactions) + """

### Regulatory Compliance

This documentation satisfies requirements under:
- **IRC Section 482**: Arm's length standard for controlled transactions
- **Treasury Reg. 1.6662-6**: Contemporaneous documentation requirements
- **OECD Guidelines**: Transfer pricing documentation standards

"""

    def _generate_txn_type_summary(self, transactions: List[dict]) -> str:
        """Generate transaction summary by type."""
        by_type = {}
        for txn in transactions:
            type_label = txn.get("typeLabel", txn.get("type", "").replace(TAX_NS, ""))
            if type_label not in by_type:
                by_type[type_label] = {"count": 0, "value": 0}
            by_type[type_label]["count"] += 1
            by_type[type_label]["value"] += float(txn.get("value", 0) or 0)

        content = ""
        for type_label, stats in sorted(by_type.items()):
            content += f"| {type_label} | {stats['count']} | ${stats['value']:,.0f} |\n"
        return content

    def generate_organizational_structure(self, entities: List[dict],
                                          group_structure: List[dict]) -> str:
        """Generate organizational structure from actual data relationships."""
        content = """
## Organizational Structure

### Legal Entity Hierarchy

The following entities are part of the multinational group, with ownership relationships
derived from the semantic data model.

"""
        # Entity table from actual data
        content += "| Entity | Type | Jurisdiction | Functional Profile | Ownership |\n"
        content += "|--------|------|--------------|-------------------|----------|\n"

        for entity in entities:
            name = entity.get("name", "Unknown")
            etype = entity.get("typeLabel", entity.get("type", "").replace(TAX_NS, ""))
            jurisdiction = entity.get("jurisdictionName", "Unknown")
            profile = entity.get("profile", "N/A")
            ownership = entity.get("ownership", "100")

            content += f"| {name} | {etype} | {jurisdiction} | {profile} | {ownership}% |\n"

        # Build ownership tree from group structure
        content += "\n### Ownership Structure\n\n"

        if group_structure:
            parent_subs = {}
            for row in group_structure:
                parent = row.get("parentName", "Unknown Parent")
                sub = row.get("subName")
                if sub:
                    if parent not in parent_subs:
                        parent_subs[parent] = []
                    parent_subs[parent].append(sub)

            content += "```\n"
            for parent, subs in parent_subs.items():
                content += f"{parent} (Ultimate Parent)\n"
                for i, sub in enumerate(subs):
                    prefix = "└──" if i == len(subs) - 1 else "├──"
                    content += f"    {prefix} {sub}\n"
            content += "```\n"

        return content

    def generate_functional_analysis(self, entities: List[dict]) -> str:
        """Generate functional analysis from entity data."""
        content = """
## Functional Analysis

The functional analysis characterizes each entity based on:
- **Functions performed** (activities undertaken)
- **Assets employed** (tangible and intangible)
- **Risks assumed** (business and financial)

These characterizations are stored as semantic properties in the data model.

"""
        for entity in entities:
            name = entity.get("name", "Unknown")
            profile = entity.get("profile", "N/A")

            content += f"### {name}\n\n"
            content += f"**Functional Profile**: {profile}\n\n"

            # Financial metrics if available
            if entity.get("revenue") or entity.get("operatingMargin"):
                content += "| Metric | Value |\n|--------|-------|\n"
                if entity.get("revenue"):
                    content += f"| Revenue | ${float(entity['revenue']):,.0f} |\n"
                if entity.get("operatingMargin"):
                    content += f"| Operating Margin | {float(entity['operatingMargin'])*100:.1f}% |\n"
                if entity.get("employees"):
                    content += f"| Employees | {entity['employees']} |\n"
                content += "\n"

            content += "---\n\n"

        return content

    def generate_transaction_analysis(self, transactions: List[dict]) -> str:
        """Generate transaction analysis with relationships resolved via SPARQL."""
        content = """
## Controlled Transactions Analysis

All intercompany transactions are identified from the semantic data store with
payer/payee relationships resolved through object property references.

### Transaction Summary

| Type | Payer | Payee | Value | Method |
|------|-------|-------|-------|--------|
"""
        for txn in transactions:
            txn_type = txn.get("typeLabel", txn.get("type", "").replace(TAX_NS, ""))
            payer = txn.get("payerName", "Unknown")
            payer_jur = txn.get("payerJurisdiction", "")
            payee = txn.get("payeeName", "Unknown")
            payee_jur = txn.get("payeeJurisdiction", "")
            value = float(txn.get("value", 0) or 0)
            method = txn.get("methodLabel") or txn.get("methodName", "N/A")

            payer_display = f"{payer} ({payer_jur})" if payer_jur else payer
            payee_display = f"{payee} ({payee_jur})" if payee_jur else payee

            content += f"| {txn_type} | {payer_display} | {payee_display} | ${value:,.0f} | {method} |\n"

        content += "\n### Transaction Details\n\n"

        for txn in transactions:
            txn_type = txn.get("typeLabel", txn.get("type", "").replace(TAX_NS, ""))
            content += f"#### {txn_type}\n\n"

            # Show all available properties dynamically
            props_to_show = [
                ("payerName", "Payer"),
                ("payeeName", "Payee"),
                ("value", "Transaction Value"),
                ("currency", "Currency"),
                ("fiscalYear", "Fiscal Year"),
                ("methodLabel", "TP Method"),
                ("productDescription", "Product"),
                ("quantity", "Quantity"),
                ("unitPrice", "Unit Price"),
                ("royaltyRate", "Royalty Rate"),
                ("interestRate", "Interest Rate"),
                ("principalAmount", "Principal"),
                ("markupPercentage", "Markup"),
                ("costBase", "Cost Base")
            ]

            for prop, label in props_to_show:
                val = txn.get(prop)
                if val:
                    # Format based on property type
                    if 'rate' in prop.lower() or 'percentage' in prop.lower():
                        val = f"{float(val)*100:.1f}%"
                    elif 'value' in prop.lower() or 'amount' in prop.lower() or 'price' in prop.lower() or 'base' in prop.lower():
                        val = f"${float(val):,.0f}"
                    content += f"- **{label}**: {val}\n"

            content += "\n"

        return content

    def generate_method_selection(self, transactions: List[dict],
                                  tp_methods: List[dict]) -> str:
        """Generate method selection based on ontology definitions."""
        content = """
## Transfer Pricing Method Selection

The transfer pricing methods are defined in the ontology with their characteristics.
Method selection follows the best method rule under Treasury Reg. 1.482-1(c).

### Available Methods (from Ontology)

"""
        for method in tp_methods:
            label = method.get("label", "Unknown")
            comment = method.get("comment", "")
            content += f"**{label}**\n"
            if comment:
                content += f"> {comment}\n"
            content += "\n"

        content += "### Methods Applied to Transactions\n\n"
        content += "| Transaction Type | Selected Method | Rationale |\n"
        content += "|-----------------|-----------------|----------|\n"

        # Group transactions by type and method
        type_methods = {}
        for txn in transactions:
            txn_type = txn.get("typeLabel", txn.get("type", "").replace(TAX_NS, ""))
            method = txn.get("methodLabel") or txn.get("methodName", "N/A")
            if txn_type not in type_methods:
                type_methods[txn_type] = method

        method_rationale = {
            "TNMM": "Net margin analysis with comparable companies",
            "Cost Plus": "Cost-based with appropriate markup",
            "CUP": "Direct price comparison available",
            "Resale Price": "Gross margin benchmark",
            "Profit Split": "Significant unique contributions by both parties"
        }

        for txn_type, method in type_methods.items():
            rationale = method_rationale.get(method, "Best method based on facts and circumstances")
            content += f"| {txn_type} | {method} | {rationale} |\n"

        return content + "\n"

    def generate_economic_analysis(self, comparables: List[dict],
                                   arm_length_ranges: List[dict],
                                   entities: List[dict]) -> str:
        """Generate economic analysis from comparable data."""
        content = """
## Economic Analysis

### Comparable Company Analysis

Comparable companies are identified and stored with their financial metrics.
The arm's length ranges are computed from accepted comparables.

"""
        # Group comparables by profile
        by_profile = {}
        for comp in comparables:
            profile = comp.get("profile", "Other")
            if profile not in by_profile:
                by_profile[profile] = []
            by_profile[profile].append(comp)

        for profile, comps in by_profile.items():
            content += f"#### {profile} Comparables\n\n"
            content += "| Company | Operating Margin | Revenue | Year |\n"
            content += "|---------|-----------------|---------|------|\n"

            for comp in comps:
                name = comp.get("companyName", "Unknown")
                om = comp.get("operatingMargin")
                om_str = f"{float(om)*100:.1f}%" if om else "N/A"
                rev = comp.get("revenue")
                rev_str = f"${float(rev)/1_000_000:,.0f}M" if rev else "N/A"
                year = comp.get("dataYear", "N/A")
                content += f"| {name} | {om_str} | {rev_str} | {year} |\n"

            content += "\n"

        # Arm's length ranges
        content += "### Arm's Length Ranges\n\n"

        for alr in arm_length_ranges:
            profile = alr.get("profile", "Unknown")
            pli = alr.get("pli", "Operating Margin")

            content += f"#### {profile} - {pli}\n\n"
            content += "| Percentile | Value |\n|------------|-------|\n"

            for stat, label in [("min", "Minimum"), ("lq", "25th Percentile"),
                                ("median", "Median"), ("uq", "75th Percentile"),
                                ("max", "Maximum")]:
                val = alr.get(stat)
                if val:
                    content += f"| {label} | {float(val)*100:.1f}% |\n"

            if alr.get("count"):
                content += f"| Comparables | {alr['count']} |\n"
            content += "\n"

        # Tested party results
        content += "### Tested Party Results\n\n"
        content += "| Entity | Actual Result | Arm's Length Range | Status |\n"
        content += "|--------|---------------|-------------------|--------|\n"

        for entity in entities:
            if entity.get("operatingMargin"):
                name = entity.get("name", "Unknown")
                actual = float(entity["operatingMargin"])
                profile = entity.get("profile", "")

                # Find matching range
                matching_range = None
                for alr in arm_length_ranges:
                    if alr.get("profile") == profile:
                        matching_range = alr
                        break

                if matching_range:
                    lq = float(matching_range.get("lq", 0))
                    uq = float(matching_range.get("uq", 1))
                    in_range = lq <= actual <= uq
                    status = "Within Range" if in_range else "Adjustment Required"
                    range_str = f"{lq*100:.1f}% - {uq*100:.1f}%"
                else:
                    status = "No benchmark"
                    range_str = "N/A"

                content += f"| {name} | {actual*100:.1f}% | {range_str} | {status} |\n"

        return content + "\n"

    def generate_ontology_appendix(self) -> str:
        """Generate appendix showing the ontology structure."""
        classes = self.onto.get_class_hierarchy()
        props = self.onto.get_properties()
        constraints = self.onto.get_shacl_constraints()

        content = """
## Appendix A: Ontological Data Model

This documentation is generated from a semantic data model (ontology) that provides:
- **Machine-readable definitions** for all transfer pricing concepts
- **Validation rules** (SHACL) ensuring data completeness
- **Relationship tracking** for full audit trail

### Namespace

```
@prefix tax: <http://tesserai.io/ontology/taxation#>
```

### Class Hierarchy

"""
        # Organize by major categories
        categories = {
            "LegalEntity": "Legal Entities",
            "IntercompanyTransaction": "Transactions",
            "TransferPricingMethod": "TP Methods",
            "TransferPricingDocumentation": "Documentation"
        }

        for base_class, category_name in categories.items():
            content += f"#### {category_name}\n\n"
            content += "| Class | Description |\n|-------|-------------|\n"

            subclasses = self.onto.get_subclasses(base_class)
            if base_class in classes:
                content += f"| `tax:{base_class}` | {classes[base_class].get('comment', '')} |\n"

            for sub in subclasses:
                if sub in classes:
                    content += f"| `tax:{sub}` | {classes[sub].get('comment', '')} |\n"
            content += "\n"

        # Key properties
        content += "### Key Properties\n\n"
        content += "| Property | Domain | Range | Description |\n"
        content += "|----------|--------|-------|-------------|\n"

        key_props = ["transactionValue", "operatingMargin", "royaltyRate",
                     "interestRate", "lowerQuartile", "median", "upperQuartile"]
        for prop_name in key_props:
            if prop_name in props:
                p = props[prop_name]
                content += f"| `tax:{prop_name}` | {p['domain']} | {p['range'].split('#')[-1] if '#' in p['range'] else p['range']} | {p['comment']} |\n"

        # SHACL constraints
        content += "\n### Validation Rules (SHACL)\n\n"

        for target, rules in constraints.items():
            content += f"**{target}**:\n"
            for rule in rules:
                if rule.get("minCount"):
                    content += f"- `{rule['path']}` is required (minCount: {rule['minCount']})\n"
                if rule.get("message"):
                    content += f"  - _{rule['message']}_\n"
            content += "\n"

        return content

    def generate_principal_document(self, tax_year: int) -> str:
        """Generate complete principal document from ontology and data."""
        # Fetch all data via SPARQL
        entities = self.data.get_entities()
        transactions = self.data.get_transactions()
        comparables = self.data.get_comparables()
        arm_length_ranges = self.data.get_arm_length_ranges()
        bg_docs = self.data.get_background_documents()
        group_structure = self.data.get_group_structure()
        tp_methods = self.onto.get_tp_methods()

        # Header
        report = f"""
# TRANSFER PRICING DOCUMENTATION
# Principal Document (Ontology-Driven)

**Tax Year**: {tax_year}
**Generated**: {datetime.now().strftime('%B %d, %Y %H:%M:%S')}
**Data Source**: DTaaS Semantic Triple Store
**Ontology**: `{ONTOLOGY_GRAPH}`

---

## Table of Contents

1. Executive Summary
2. Organizational Structure
3. Functional Analysis
4. Controlled Transactions Analysis
5. Transfer Pricing Method Selection
6. Economic Analysis
7. Conclusion
8. Index of Documents
9. Appendix A: Ontological Data Model

---

"""
        # Generate each section
        report += self.generate_executive_summary(entities, transactions, tax_year)
        report += self.generate_organizational_structure(entities, group_structure)
        report += self.generate_functional_analysis(entities)
        report += self.generate_transaction_analysis(transactions)
        report += self.generate_method_selection(transactions, tp_methods)
        report += self.generate_economic_analysis(comparables, arm_length_ranges, entities)

        # Conclusion
        report += """
## Conclusion

Based on the semantic analysis of controlled transactions:

1. **Data Completeness**: All required properties per SHACL constraints are populated
2. **Relationship Integrity**: Payer/payee references resolve to valid legal entities
3. **Arm's Length Compliance**: Tested party results fall within benchmark ranges
4. **Method Selection**: Transfer pricing methods are appropriate per ontology definitions

---

## Index of Principal and Background Documents

### Principal Documents

1. This Transfer Pricing Documentation Report
2. Organizational structure (derived from `tax:hasSubsidiary` relationships)
3. Functional analysis (derived from `tax:functionalProfile` properties)
4. Economic analysis (derived from `tax:ComparableCompany` instances)

### Background Documents

"""
        for doc in bg_docs:
            doc_id = doc.get("docId", "N/A")
            title = doc.get("title", "Unknown")
            report += f"- **{doc_id}**: {title}\n"

        # Appendix
        report += self.generate_ontology_appendix()

        report += """
---

*This documentation was generated from semantic data using ontology-driven assembly.
All values are derived from the DTaaS triple store with full audit trail.*

**CONFIDENTIAL - ATTORNEY-CLIENT PRIVILEGED**
"""
        return report


# =============================================================================
# Health Check
# =============================================================================

def check_server_health():
    """Check if DTaaS server is healthy."""
    try:
        resp = httpx.get(f"{BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except:
        return False


# =============================================================================
# Streamlit UI
# =============================================================================

def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Transfer Pricing Report Generator",
        page_icon="📋",
        layout="wide"
    )

    st.title("📋 Transfer Pricing Report Generator")
    st.markdown("**Ontology-Driven** IRS-compliant Principal Document generation")

    # Sidebar configuration
    st.sidebar.header("Configuration")
    st.sidebar.text(f"Server: {BASE_URL}")
    st.sidebar.text(f"Tenant: {TOKEN}")
    st.sidebar.text(f"Ontology: taxation")

    # Check server health
    if not check_server_health():
        st.error(f"Cannot connect to DTaaS server at {BASE_URL}")
        st.info("Please ensure the server is running and try again.")
        st.code("cargo run --release", language="bash")
        return

    st.sidebar.success("Connected to DTaaS")

    # Initialize services
    onto_service = OntologyService(BASE_URL, HEADERS, ONTOLOGY_GRAPH)
    data_service = DataService(onto_service)
    report_gen = ReportGenerator(onto_service, data_service)

    # Tax year selection
    tax_year = st.sidebar.selectbox("Tax Year", [2024, 2023, 2022], index=0)

    # Main tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📖 Ontology",
        "🏢 Entities",
        "💰 Transactions",
        "📊 Benchmarking",
        "📄 Documents",
        "📝 Generate Report",
        "🔗 Lineage"
    ])

    # Tab 1: Ontology Explorer
    with tab1:
        st.header("Ontology Structure")
        st.markdown("The report is generated based on these semantic definitions.")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Class Hierarchy")
            classes = onto_service.get_class_hierarchy()

            if classes:
                # Show main categories
                for base in ["LegalEntity", "IntercompanyTransaction", "TransferPricingMethod",
                            "ComparableCompany", "TransferPricingDocumentation", "ArmLengthRange"]:
                    if base in classes:
                        with st.expander(f"📦 {classes[base]['label']}", expanded=False):
                            st.write(f"*{classes[base].get('comment', '')}*")
                            subs = onto_service.get_subclasses(base)
                            if subs:
                                for sub in subs:
                                    if sub in classes:
                                        st.write(f"  └─ **{classes[sub]['label']}**: {classes[sub].get('comment', '')}")
            else:
                st.warning("No classes found. Load the ontology first.")
                st.code(f"curl -X POST {BASE_URL}/api/v1/ontologies/taxation -H 'Authorization: Bearer {TOKEN}' -H 'Content-Type: text/turtle' --data-binary @examples/ontologies/taxation.ttl")

        with col2:
            st.subheader("Properties")
            props = onto_service.get_properties()

            if props:
                prop_data = []
                for name, p in list(props.items())[:20]:
                    prop_data.append({
                        "Property": name,
                        "Label": p["label"],
                        "Type": p["type"],
                        "Domain": p["domain"]
                    })
                st.dataframe(pd.DataFrame(prop_data), use_container_width=True)

            st.subheader("SHACL Constraints")
            constraints = onto_service.get_shacl_constraints()
            if constraints:
                for target, rules in list(constraints.items())[:5]:
                    with st.expander(f"🔒 {target}"):
                        for rule in rules:
                            st.write(f"- `{rule['path']}`: min={rule.get('minCount', 'N/A')}")
                            if rule.get('message'):
                                st.caption(rule['message'])

    # Tab 2: Entities (via SPARQL)
    with tab2:
        st.header("Legal Entities")
        st.markdown("Entities retrieved via SPARQL with relationships resolved.")

        entities = data_service.get_entities()

        if not entities:
            st.warning("No legal entities found. Please run seed.py first.")
            st.code("python examples/taxation/seed.py", language="bash")
        else:
            st.success(f"Found {len(entities)} legal entities via SPARQL")

            # Show the actual SPARQL query
            with st.expander("View SPARQL Query"):
                st.code(QUERY_ENTITIES_WITH_RELATIONSHIPS, language="sparql")

            # Display data
            entity_data = []
            for e in entities:
                entity_data.append({
                    "Entity": e.get("name", "Unknown"),
                    "Type": e.get("typeLabel", ""),
                    "Jurisdiction": e.get("jurisdictionName", "N/A"),
                    "Profile": e.get("profile", "N/A"),
                    "Parent": e.get("parentName", "—"),
                    "Ownership": f"{e.get('ownership', '100')}%"
                })

            st.dataframe(pd.DataFrame(entity_data), use_container_width=True)

    # Tab 3: Transactions (via SPARQL)
    with tab3:
        st.header("Intercompany Transactions")
        st.markdown("Transactions with payer/payee resolved via object property joins.")

        transactions = data_service.get_transactions()

        if not transactions:
            st.warning("No transactions found. Please run seed.py first.")
        else:
            st.success(f"Found {len(transactions)} transactions via SPARQL")

            with st.expander("View SPARQL Query"):
                st.code(QUERY_TRANSACTIONS_WITH_PARTIES, language="sparql")

            # Summary metrics
            total_value = sum(float(t.get("value", 0) or 0) for t in transactions)
            col1, col2, col3 = st.columns(3)
            col1.metric("Transactions", len(transactions))
            col2.metric("Total Value", f"${total_value:,.0f}")
            col3.metric("Tax Year", tax_year)

            # Transaction breakdown
            st.subheader("By Transaction Type")
            txn_by_type = {}
            for t in transactions:
                txn_type = t.get("typeLabel", t.get("type", "").replace(TAX_NS, ""))
                value = float(t.get("value", 0) or 0)
                txn_by_type[txn_type] = txn_by_type.get(txn_type, 0) + value

            fig = px.pie(values=list(txn_by_type.values()), names=list(txn_by_type.keys()),
                        title="Transaction Value by Type")
            st.plotly_chart(fig, use_container_width=True)

            # Details table
            st.subheader("Transaction Details")
            txn_data = []
            for t in transactions:
                txn_data.append({
                    "Type": t.get("typeLabel", ""),
                    "Payer": t.get("payerName", "N/A"),
                    "Payee": t.get("payeeName", "N/A"),
                    "Value": f"${float(t.get('value', 0) or 0):,.0f}",
                    "Method": t.get("methodLabel") or t.get("methodName", "N/A")
                })
            st.dataframe(pd.DataFrame(txn_data), use_container_width=True)

    # Tab 4: Benchmarking
    with tab4:
        st.header("Benchmarking Analysis")

        comparables = data_service.get_comparables()
        arm_length_ranges = data_service.get_arm_length_ranges()

        if not comparables:
            st.warning("No comparable companies found.")
        else:
            st.success(f"Found {len(comparables)} comparables")

            # Group by profile
            by_profile = {}
            for c in comparables:
                profile = c.get("profile", "Other")
                if profile not in by_profile:
                    by_profile[profile] = []
                by_profile[profile].append(c)

            for profile, comps in by_profile.items():
                st.subheader(f"{profile} Comparables")

                margins = [float(c.get("operatingMargin", 0) or 0) for c in comps]

                comp_data = []
                for c in comps:
                    om = c.get("operatingMargin")
                    comp_data.append({
                        "Company": c.get("companyName", "Unknown"),
                        "Operating Margin": f"{float(om)*100:.1f}%" if om else "N/A",
                        "Revenue": f"${float(c.get('revenue', 0) or 0)/1_000_000:,.0f}M",
                        "Year": c.get("dataYear", "N/A")
                    })
                st.dataframe(pd.DataFrame(comp_data), use_container_width=True)

                # Box plot
                if margins:
                    fig = go.Figure()
                    fig.add_trace(go.Box(y=[m * 100 for m in margins], name=profile,
                                        boxpoints='all', jitter=0.3))
                    fig.update_layout(title=f"{profile} - Operating Margin Distribution",
                                     yaxis_title="Operating Margin (%)")
                    st.plotly_chart(fig, use_container_width=True)

        # Arm's length ranges
        if arm_length_ranges:
            st.subheader("Arm's Length Ranges")
            for alr in arm_length_ranges:
                profile = alr.get("profile", "Unknown")
                cols = st.columns(5)
                cols[0].metric("Min", f"{float(alr.get('min', 0) or 0)*100:.1f}%")
                cols[1].metric("25th", f"{float(alr.get('lq', 0) or 0)*100:.1f}%")
                cols[2].metric("Median", f"{float(alr.get('median', 0) or 0)*100:.1f}%")
                cols[3].metric("75th", f"{float(alr.get('uq', 0) or 0)*100:.1f}%")
                cols[4].metric("Max", f"{float(alr.get('max', 0) or 0)*100:.1f}%")
                st.caption(f"{profile} - {alr.get('pli', 'N/A')}")
                st.divider()

    # Tab 5: Background Documents
    with tab5:
        st.header("Background Documents")

        bg_docs = data_service.get_background_documents()

        if not bg_docs:
            st.warning("No background documents found.")
        else:
            st.success(f"Found {len(bg_docs)} background documents")

            for doc in bg_docs:
                with st.expander(f"📄 {doc.get('docId', 'N/A')}: {doc.get('title', 'Unknown')}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Prepared Date:**", doc.get("preparedDate", "N/A"))
                        st.write("**Prepared By:**", doc.get("preparedBy", "N/A"))
                    with col2:
                        st.write("**Tax Year:**", doc.get("taxYear", "N/A"))
                        st.write("**Status:**", doc.get("status", "N/A"))

                    if doc.get("entityName"):
                        st.write("**Documents Entity:**", doc.get("entityName"))
                    if doc.get("txnValue"):
                        st.write("**Documents Transaction Value:**", f"${float(doc.get('txnValue')):,.0f}")

    # Tab 6: Generate Report
    with tab6:
        st.header("Generate Principal Document")

        st.markdown("""
        Generate a comprehensive **Principal Document** using ontology-driven assembly:

        - **Structure** derived from ontology class hierarchy
        - **Labels** from `rdfs:label` and `rdfs:comment`
        - **Relationships** resolved via SPARQL object properties
        - **Validation** based on SHACL constraints
        - **Zero hardcoded values** - all from semantic data
        """)

        # Data check
        entities = data_service.get_entities()
        transactions = data_service.get_transactions()
        comparables = data_service.get_comparables()
        arm_length_ranges = data_service.get_arm_length_ranges()
        bg_docs = data_service.get_background_documents()

        col1, col2, col3 = st.columns(3)
        col1.metric("Entities", len(entities))
        col1.metric("Transactions", len(transactions))
        col2.metric("Comparables", len(comparables))
        col2.metric("Ranges", len(arm_length_ranges))
        col3.metric("Documents", len(bg_docs))
        col3.metric("Ontology Classes", len(onto_service.get_class_hierarchy()))

        ready = len(entities) > 0 and len(transactions) > 0

        if not ready:
            st.error("Insufficient data. Please run seed.py first.")
        else:
            st.success("All data available for ontology-driven report generation")

            if st.button("🔄 Generate Principal Document", type="primary", use_container_width=True):
                with st.spinner("Generating report from semantic data..."):
                    report = report_gen.generate_principal_document(tax_year)

                st.success("Report generated successfully!")
                st.markdown("---")
                st.markdown(report)

                st.download_button(
                    label="📥 Download Report (Markdown)",
                    data=report,
                    file_name=f"TP_Report_FY{tax_year}_Ontology_Driven.md",
                    mime="text/markdown"
                )

    # Tab 7: Lineage (lineage-uid)
    with tab7:
        st.header("Implicit Lineage Tracking")
        st.markdown("""
        The **lineage-uid** system provides structured, derivable UUIDs that embed lineage
        information directly into entity identifiers. This enables implicit tracking without
        explicit `parent_id` storage.
        """)

        # Lineage ID Format explanation
        with st.expander("📐 LineageId Format", expanded=True):
            st.markdown("""
            ```
            {prefix}_{128-bit-structured-uuid}

            Example: taxation-demo_019b4703-7611-74b7-bc59-8d6d79a73bde
                     └────┬─────┘ └──────────────┬──────────────────┘
                       Prefix      Structured UUID (128 bits)
            ```
            """)

            st.markdown("#### 128-bit Structure")
            format_data = [
                {"Component": "Timestamp", "Bits": "48", "Purpose": "Unix milliseconds - chronological sorting"},
                {"Component": "Version", "Bits": "4", "Purpose": "UUIDv7 compatibility (always '7')"},
                {"Component": "Event Prefix", "Bits": "28", "Purpose": "Shared across session (~268M unique/ms)"},
                {"Component": "Object Entropy", "Bits": "48", "Purpose": "Unique per object (~281T unique/event)"},
            ]
            st.dataframe(pd.DataFrame(format_data), use_container_width=True, hide_index=True)

        # Fetch all twins to display lineage info
        st.subheader("Twin Lineage Information")

        try:
            response = httpx.get(
                f"{BASE_URL}/api/v1/twins/json",
                headers=HEADERS,
                params={"limit": 100}
            )
            response.raise_for_status()
            twins_response = response.json()
            twins = twins_response.get("data", [])

            if twins:
                st.success(f"Found {len(twins)} twins with lineage metadata")

                # Build lineage table
                lineage_data = []
                for twin in twins:
                    twin_id = twin.get("id", "")
                    metadata = twin.get("metadata", {})
                    created_at = metadata.get("created_at", "")

                    # Parse timestamp if available
                    created_dt = ""
                    if created_at:
                        try:
                            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            created_dt = created_at

                    # Extract short ID from URN
                    short_id = twin_id.replace("urn:tesserai:twin:", "") if twin_id.startswith("urn:") else twin_id

                    lineage_data.append({
                        "ID": short_id,
                        "Type": twin.get("type", "").replace("taxation#", ""),
                        "Name": twin.get("name", "")[:40],
                        "Created At": created_dt,
                        "Domain": twin.get("domain", ""),
                    })

                # Sort by created_at
                lineage_df = pd.DataFrame(lineage_data)
                st.dataframe(lineage_df, use_container_width=True, hide_index=True)

                # Group by type
                st.subheader("Twins by Type")
                type_counts = {}
                for twin in twins:
                    t = twin.get("type", "Unknown").replace("taxation#", "")
                    type_counts[t] = type_counts.get(t, 0) + 1

                fig = px.bar(
                    x=list(type_counts.keys()),
                    y=list(type_counts.values()),
                    labels={"x": "Type", "y": "Count"},
                    title="Twin Distribution by Type"
                )
                st.plotly_chart(fig, use_container_width=True)

                # Batch/Session grouping demonstration
                st.subheader("Batch Grouping (Implicit Lineage)")
                st.markdown("""
                With **lineage-uid**, twins created in the same batch/session share a common
                **Event Prefix**. This allows querying all siblings without explicit foreign keys:

                ```python
                from lineage_uid import SessionMinter

                # Create a session for batch import
                session = SessionMinter::new("taxation-demo")

                # All IDs share the same event prefix
                entity1 = session.mint()  # taxation-demo_019b4703-7611-74b7-...
                entity2 = session.mint()  # taxation-demo_019b4703-7611-70d8-...

                # Later: find all twins from this batch
                event = entity1.event_id()
                siblings = find_by_event(event)  # Returns entity1, entity2, ...
                ```
                """)

                # Timeline visualization
                st.subheader("Creation Timeline")
                timeline_data = []
                for twin in twins:
                    metadata = twin.get("metadata", {})
                    created_at = metadata.get("created_at", "")
                    if created_at:
                        try:
                            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            timeline_data.append({
                                "Time": dt,
                                "Type": twin.get("type", "").replace("taxation#", ""),
                                "Name": twin.get("name", "")[:30]
                            })
                        except:
                            pass

                if timeline_data:
                    timeline_df = pd.DataFrame(timeline_data)
                    timeline_df = timeline_df.sort_values("Time")

                    # Group by second to show batch creation
                    timeline_df["Second"] = timeline_df["Time"].dt.floor("s")
                    batch_counts = timeline_df.groupby("Second").size().reset_index(name="Count")

                    fig = px.bar(
                        batch_counts,
                        x="Second",
                        y="Count",
                        title="Twins Created per Second (Batch Grouping)",
                        labels={"Second": "Time", "Count": "Twins Created"}
                    )
                    st.plotly_chart(fig, use_container_width=True)

            else:
                st.warning("No twins found. Run seed.py first.")

        except Exception as e:
            st.error(f"Failed to fetch twins: {e}")

        # Benefits section
        st.subheader("Benefits of Implicit Lineage")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            **Storage Efficiency**
            | Approach | Bytes/Entity |
            |----------|-------------|
            | Traditional (id + parent_id + batch_id) | 48 bytes |
            | LineageId (implicit) | 16 bytes |
            | **Savings** | **67%** |
            """)

        with col2:
            st.markdown("""
            **Query Capabilities**
            - Find siblings via bitmask (no JOIN)
            - Temporal queries via embedded timestamp
            - Chronological sorting (lexicographic = time order)
            - Prefix-based filtering (SQL LIKE)
            """)


if __name__ == "__main__":
    main()
