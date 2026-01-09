#!/usr/bin/env python3
"""
Transfer Pricing Seed Data for DTaaS

This script creates a comprehensive transfer pricing scenario for a multinational
technology company, demonstrating IRS documentation requirements and benchmarking.

Scenario: TechGlobal Inc.
- US Parent: Full-fledged manufacturer and IP owner
- Ireland Subsidiary: Limited risk distributor for EMEA
- Germany Subsidiary: Contract manufacturer
- Singapore Subsidiary: Regional headquarters for APAC
- Cayman Islands: IP holding company (licensing arrangements)

Transactions modeled:
- Goods sales (US to Ireland, Germany to Ireland)
- IP royalties (Cayman to all operating entities)
- Intercompany services (Singapore to APAC entities)
- Intercompany financing (US to Germany)
- Cost sharing arrangements (R&D)
"""

import sys
import os
from datetime import date, datetime
from decimal import Decimal
import random

# Add parent directory to path for common utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common import (
    get_client, print_summary, logger,
    bulk_create_twins, bulk_add_relationships,
    DOMAIN_NAMESPACES
)

# =============================================================================
# Configuration
# =============================================================================

TAX_NS = DOMAIN_NAMESPACES["taxation"]

def tax_type(local_name: str) -> str:
    """Expand local type to full taxation namespace URI."""
    return f"{TAX_NS}{local_name}"


def prepare_tax_twin(data: dict) -> dict:
    """Prepare a twin dict for bulk creation."""
    # Ensure domain is set
    if "domain" not in data:
        data["domain"] = "taxation"
    return data


def seed_taxation():
    """Seed all transfer pricing data for the taxation domain."""
    print("\n" + "=" * 70)
    print(" Transfer Pricing Seed Data - TechGlobal Inc.")
    print("=" * 70)

    client = get_client()
    all_twins = []
    all_relationships = []

    # =========================================================================
    # JURISDICTIONS
    # =========================================================================
    logger.info("Creating jurisdictions...")
    jurisdictions = [
        {
            "id": "jurisdiction-us",
            "type": tax_type("Jurisdiction"),
            "name": "United States",
            "domain": "taxation",
            "properties": {
                "countryCode": "US",
                "currencyCode": "USD",
                "corporateTaxRate": 0.21,
                "hasControlledForeignCorporationRules": True,
                "hasThinCapitalizationRules": True,
                "transferPricingRegime": "comprehensive"
            }
        },
        {
            "id": "jurisdiction-ie",
            "type": tax_type("Jurisdiction"),
            "name": "Ireland",
            "domain": "taxation",
            "properties": {
                "countryCode": "IE",
                "currencyCode": "EUR",
                "corporateTaxRate": 0.125,
                "hasIPBoxRegime": True,
                "transferPricingRegime": "comprehensive"
            }
        },
        {
            "id": "jurisdiction-de",
            "type": tax_type("Jurisdiction"),
            "name": "Germany",
            "domain": "taxation",
            "properties": {
                "countryCode": "DE",
                "currencyCode": "EUR",
                "corporateTaxRate": 0.2975,
                "transferPricingRegime": "comprehensive"
            }
        },
        {
            "id": "jurisdiction-sg",
            "type": tax_type("Jurisdiction"),
            "name": "Singapore",
            "domain": "taxation",
            "properties": {
                "countryCode": "SG",
                "currencyCode": "SGD",
                "corporateTaxRate": 0.17,
                "hasIPBoxRegime": True,
                "transferPricingRegime": "comprehensive"
            }
        },
        {
            "id": "jurisdiction-ky",
            "type": tax_type("Jurisdiction"),
            "name": "Cayman Islands",
            "domain": "taxation",
            "properties": {
                "countryCode": "KY",
                "currencyCode": "USD",
                "corporateTaxRate": 0.0,
                "transferPricingRegime": "limited"
            }
        },
        {
            "id": "jurisdiction-jp",
            "type": tax_type("Jurisdiction"),
            "name": "Japan",
            "domain": "taxation",
            "properties": {
                "countryCode": "JP",
                "currencyCode": "JPY",
                "corporateTaxRate": 0.2974,
                "transferPricingRegime": "comprehensive"
            }
        }
    ]

    for j in jurisdictions:
        all_twins.append(prepare_tax_twin(j))

    # =========================================================================
    # MULTINATIONAL GROUP
    # =========================================================================
    logger.info("Creating multinational group structure...")

    all_twins.append(prepare_tax_twin({
        "id": "mne-techglobal",
        "type": tax_type("MultinationalGroup"),
        "name": "TechGlobal Inc. Group",
        "domain": "taxation",
        "properties": {
            "ultimateParent": "TechGlobal Inc.",
            "headquartersCountry": "US",
            "industry": "Technology - Software & Hardware",
            "sicCode": "7372",
            "naicsCode": "511210",
            "fiscalYearEnd": "12-31",
            "consolidatedRevenue": 5200000000,
            "totalEmployees": 12500
        }
    }))

    # Legal entities
    entities = [
        {
            "id": "entity-techglobal-us",
            "type": tax_type("ParentCompany"),
            "name": "TechGlobal Inc. (US Parent)",
            "domain": "taxation",
            "properties": {
                "entityName": "TechGlobal Inc.",
                "taxId": "12-3456789",
                "incorporationDate": "1995-03-15",
                "fiscalYearEnd": "12-31",
                "ownershipPercentage": 100.0,
                "functionalProfile": "Full-Fledged Manufacturer",
                "functionsPerformed": ["R&D", "Manufacturing", "Strategic Management", "IP Development", "US Sales & Marketing"],
                "assetsUsed": ["Manufacturing IP", "Product Patents", "Trademarks", "Manufacturing Facilities", "Workforce"],
                "risksAssumed": ["Market Risk", "R&D Risk", "Inventory Risk", "Credit Risk", "Foreign Exchange Risk"],
                "revenue": 3200000000,
                "operatingIncome": 640000000,
                "totalAssets": 2800000000,
                "employees": 5500
            }
        },
        {
            "id": "entity-techglobal-ie",
            "type": tax_type("Subsidiary"),
            "name": "TechGlobal Ireland Ltd.",
            "domain": "taxation",
            "properties": {
                "entityName": "TechGlobal Ireland Limited",
                "taxId": "IE-9876543",
                "incorporationDate": "2008-06-20",
                "fiscalYearEnd": "12-31",
                "ownershipPercentage": 100.0,
                "functionalProfile": "Limited Risk Distributor",
                "functionsPerformed": ["Sales & Marketing (EMEA)", "Customer Support", "Order Processing", "Logistics Coordination"],
                "assetsUsed": ["Limited Inventory", "Customer Lists", "Workforce"],
                "risksAssumed": ["Limited Market Risk", "Limited Credit Risk"],
                "revenue": 1200000000,
                "operatingIncome": 48000000,
                "operatingMargin": 0.04,
                "totalAssets": 320000000,
                "employees": 1800
            }
        },
        {
            "id": "entity-techglobal-de",
            "type": tax_type("Subsidiary"),
            "name": "TechGlobal Germany GmbH",
            "domain": "taxation",
            "properties": {
                "entityName": "TechGlobal Germany GmbH",
                "taxId": "DE-112233445",
                "incorporationDate": "2005-09-10",
                "fiscalYearEnd": "12-31",
                "ownershipPercentage": 100.0,
                "functionalProfile": "Contract Manufacturer",
                "functionsPerformed": ["Manufacturing (to specification)", "Quality Control", "Warehousing"],
                "assetsUsed": ["Manufacturing Equipment", "Facilities (leased)", "Workforce"],
                "risksAssumed": ["Minimal Market Risk", "Limited Inventory Risk"],
                "revenue": 450000000,
                "operatingIncome": 27000000,
                "operatingMargin": 0.06,
                "totalAssets": 180000000,
                "employees": 2200
            }
        },
        {
            "id": "entity-techglobal-sg",
            "type": tax_type("Subsidiary"),
            "name": "TechGlobal Asia Pacific Pte. Ltd.",
            "domain": "taxation",
            "properties": {
                "entityName": "TechGlobal Asia Pacific Pte. Ltd.",
                "taxId": "SG-201234567",
                "incorporationDate": "2010-01-15",
                "fiscalYearEnd": "12-31",
                "ownershipPercentage": 100.0,
                "functionalProfile": "Service Provider",
                "functionsPerformed": ["Regional Management", "Sales Support (APAC)", "Technical Support", "Shared Services"],
                "assetsUsed": ["Workforce", "IT Infrastructure"],
                "risksAssumed": ["Limited Operational Risk"],
                "revenue": 85000000,
                "operatingIncome": 8500000,
                "operatingMargin": 0.10,
                "totalAssets": 45000000,
                "employees": 650
            }
        },
        {
            "id": "entity-techglobal-ky",
            "type": tax_type("Subsidiary"),
            "name": "TechGlobal IP Holdings Ltd.",
            "domain": "taxation",
            "properties": {
                "entityName": "TechGlobal IP Holdings Ltd.",
                "taxId": "KY-99887766",
                "incorporationDate": "2012-04-01",
                "fiscalYearEnd": "12-31",
                "ownershipPercentage": 100.0,
                "functionalProfile": "IP Holding Company",
                "functionsPerformed": ["IP Ownership", "License Management"],
                "assetsUsed": ["Intangible Assets (licensed IP)"],
                "risksAssumed": ["IP Obsolescence Risk"],
                "revenue": 180000000,
                "operatingIncome": 175000000,
                "operatingMargin": 0.97,
                "totalAssets": 520000000,
                "employees": 3
            }
        },
        {
            "id": "entity-techglobal-jp",
            "type": tax_type("Subsidiary"),
            "name": "TechGlobal Japan K.K.",
            "domain": "taxation",
            "properties": {
                "entityName": "TechGlobal Japan K.K.",
                "taxId": "JP-1234567890123",
                "incorporationDate": "2007-11-20",
                "fiscalYearEnd": "12-31",
                "ownershipPercentage": 100.0,
                "functionalProfile": "Limited Risk Distributor",
                "functionsPerformed": ["Sales & Marketing (Japan)", "Customer Support", "Localization"],
                "assetsUsed": ["Limited Inventory", "Customer Relationships", "Workforce"],
                "risksAssumed": ["Limited Market Risk", "Limited Credit Risk"],
                "revenue": 280000000,
                "operatingIncome": 11200000,
                "operatingMargin": 0.04,
                "totalAssets": 95000000,
                "employees": 420
            }
        }
    ]

    for entity in entities:
        all_twins.append(prepare_tax_twin(entity))

    # Entity relationships
    for entity in entities:
        all_relationships.append((entity["id"], tax_type("belongsToGroup"), "mne-techglobal", None))

    # Location relationships
    location_map = {
        "entity-techglobal-us": "jurisdiction-us",
        "entity-techglobal-ie": "jurisdiction-ie",
        "entity-techglobal-de": "jurisdiction-de",
        "entity-techglobal-sg": "jurisdiction-sg",
        "entity-techglobal-ky": "jurisdiction-ky",
        "entity-techglobal-jp": "jurisdiction-jp"
    }

    for entity_id, jurisdiction_id in location_map.items():
        all_relationships.append((entity_id, tax_type("locatedIn"), jurisdiction_id, None))

    # Parent-subsidiary relationships
    all_relationships.append(("entity-techglobal-us", tax_type("hasSubsidiary"), "entity-techglobal-ie", None))
    all_relationships.append(("entity-techglobal-us", tax_type("hasSubsidiary"), "entity-techglobal-de", None))
    all_relationships.append(("entity-techglobal-us", tax_type("hasSubsidiary"), "entity-techglobal-sg", None))
    all_relationships.append(("entity-techglobal-us", tax_type("hasSubsidiary"), "entity-techglobal-ky", None))
    all_relationships.append(("entity-techglobal-sg", tax_type("hasSubsidiary"), "entity-techglobal-jp", None))

    # =========================================================================
    # TRANSFER PRICING METHODS
    # =========================================================================
    logger.info("Creating transfer pricing methods...")
    methods = [
        {
            "id": "method-cup",
            "type": tax_type("CUPMethod"),
            "name": "Comparable Uncontrolled Price Method",
            "domain": "taxation",
            "properties": {
                "methodName": "CUP",
                "methodDescription": "Compares the price charged in a controlled transaction to the price charged in a comparable uncontrolled transaction",
                "applicability": "Best for commodity-type products or quoted prices",
                "profitLevelIndicator": "Price"
            }
        },
        {
            "id": "method-resale-price",
            "type": tax_type("ResalePriceMethod"),
            "name": "Resale Price Method",
            "domain": "taxation",
            "properties": {
                "methodName": "Resale Price Method",
                "methodDescription": "Subtracts an appropriate gross profit from the resale price to an independent party",
                "applicability": "Best for distributors with limited value-add",
                "profitLevelIndicator": "Gross Margin"
            }
        },
        {
            "id": "method-cost-plus",
            "type": tax_type("CostPlusMethod"),
            "name": "Cost Plus Method",
            "domain": "taxation",
            "properties": {
                "methodName": "Cost Plus Method",
                "methodDescription": "Adds an appropriate gross profit markup to costs incurred",
                "applicability": "Best for manufacturers or service providers",
                "profitLevelIndicator": "Gross Markup on Costs"
            }
        },
        {
            "id": "method-tnmm",
            "type": tax_type("TNMMMethod"),
            "name": "Transactional Net Margin Method",
            "domain": "taxation",
            "properties": {
                "methodName": "TNMM",
                "methodDescription": "Examines the net profit margin relative to an appropriate base (costs, sales, assets)",
                "applicability": "Most commonly used method globally",
                "profitLevelIndicator": "Operating Margin"
            }
        },
        {
            "id": "method-profit-split",
            "type": tax_type("ProfitSplitMethod"),
            "name": "Profit Split Method",
            "domain": "taxation",
            "properties": {
                "methodName": "Profit Split",
                "methodDescription": "Splits combined profits based on the relative contributions of each party",
                "applicability": "Best for highly integrated operations or unique intangibles",
                "profitLevelIndicator": "Profit Allocation"
            }
        }
    ]

    for method in methods:
        all_twins.append(prepare_tax_twin(method))

    # =========================================================================
    # INTERCOMPANY TRANSACTIONS
    # =========================================================================
    logger.info("Creating intercompany transactions...")
    transactions = [
        {
            "id": "txn-goods-us-ie-2026",
            "type": tax_type("GoodsTransaction"),
            "name": "FY2026 Goods Sales: US to Ireland",
            "domain": "taxation",
            "properties": {
                "transactionId": "TXN-GOODS-2026-001",
                "transactionDate": "2026-12-31",
                "fiscalYear": 2026,
                "transactionValue": 850000000,
                "currency": "USD",
                "productDescription": "Enterprise software appliances and hardware",
                "productCode": "HW-ENT-SERIES",
                "quantity": 125000,
                "unitPrice": 6800,
                "transferPrice": 6800,
                "testedParty": "Ireland (Buyer)",
                "selectedMethod": "TNMM",
                "profitLevelIndicator": "Operating Margin",
                "testedPartyMargin": 0.04
            }
        },
        {
            "id": "txn-goods-de-ie-2026",
            "type": tax_type("GoodsTransaction"),
            "name": "FY2026 Goods Sales: Germany to Ireland",
            "domain": "taxation",
            "properties": {
                "transactionId": "TXN-GOODS-2026-002",
                "transactionDate": "2026-12-31",
                "fiscalYear": 2026,
                "transactionValue": 180000000,
                "currency": "EUR",
                "productDescription": "Manufactured hardware components",
                "productCode": "COMP-MFG-SERIES",
                "quantity": 450000,
                "unitPrice": 400,
                "transferPrice": 400,
                "testedParty": "Germany (Seller)",
                "selectedMethod": "Cost Plus",
                "profitLevelIndicator": "Net Cost Plus Markup",
                "testedPartyMarkup": 0.06
            }
        },
        {
            "id": "txn-royalty-ky-us-2026",
            "type": tax_type("IPLicenseTransaction"),
            "name": "FY2026 IP Royalty: Cayman to US",
            "domain": "taxation",
            "properties": {
                "transactionId": "TXN-IP-2026-001",
                "transactionDate": "2026-12-31",
                "fiscalYear": 2026,
                "transactionValue": 96000000,
                "currency": "USD",
                "royaltyRate": 0.03,
                "royaltyBase": "Net Sales",
                "licensedIP": "Manufacturing process patents and trade secrets",
                "licenseTerm": "Perpetual with annual review",
                "selectedMethod": "CUP",
                "comparableRoyaltyRates": [0.025, 0.03, 0.035, 0.04]
            }
        },
        {
            "id": "txn-royalty-ky-ie-2026",
            "type": tax_type("IPLicenseTransaction"),
            "name": "FY2026 IP Royalty: Cayman to Ireland",
            "domain": "taxation",
            "properties": {
                "transactionId": "TXN-IP-2026-002",
                "transactionDate": "2026-12-31",
                "fiscalYear": 2026,
                "transactionValue": 48000000,
                "currency": "USD",
                "royaltyRate": 0.04,
                "royaltyBase": "Net Sales",
                "licensedIP": "Trademarks and distribution rights",
                "licenseTerm": "10 years renewable",
                "selectedMethod": "CUP",
                "comparableRoyaltyRates": [0.03, 0.04, 0.045, 0.05]
            }
        },
        {
            "id": "txn-services-sg-jp-2026",
            "type": tax_type("ManagementFee"),
            "name": "FY2026 Management Services: Singapore to Japan",
            "domain": "taxation",
            "properties": {
                "transactionId": "TXN-SVC-2026-001",
                "transactionDate": "2026-12-31",
                "fiscalYear": 2026,
                "transactionValue": 12500000,
                "currency": "USD",
                "serviceDescription": "Regional management, HR, IT support, and financial services",
                "costBase": 11363636,
                "markupPercentage": 0.10,
                "benefitTest": "Passed - Services provide direct benefit to Japan operations",
                "selectedMethod": "Cost Plus",
                "profitLevelIndicator": "Net Cost Plus Markup"
            }
        },
        {
            "id": "txn-services-us-all-2026",
            "type": tax_type("TechnicalServiceFee"),
            "name": "FY2026 Technical Services: US to Subsidiaries",
            "domain": "taxation",
            "properties": {
                "transactionId": "TXN-SVC-2026-002",
                "transactionDate": "2026-12-31",
                "fiscalYear": 2026,
                "transactionValue": 45000000,
                "currency": "USD",
                "serviceDescription": "R&D support, product development, and technical training",
                "costBase": 40909091,
                "markupPercentage": 0.10,
                "allocationMethod": "Headcount and revenue-based allocation",
                "selectedMethod": "Cost Plus",
                "profitLevelIndicator": "Net Cost Plus Markup"
            }
        },
        {
            "id": "txn-loan-us-de-2026",
            "type": tax_type("FinancingTransaction"),
            "name": "FY2026 Intercompany Loan: US to Germany",
            "domain": "taxation",
            "properties": {
                "transactionId": "TXN-FIN-2026-001",
                "transactionDate": "2026-12-31",
                "fiscalYear": 2026,
                "transactionValue": 4500000,
                "currency": "USD",
                "principalAmount": 75000000,
                "interestRate": 0.06,
                "loanTerm": "5 years",
                "securityProvided": "Unsecured",
                "creditRating": "Equivalent to BBB",
                "selectedMethod": "CUP",
                "comparableInterestRates": [0.055, 0.06, 0.065, 0.07]
            }
        },
        {
            "id": "txn-csa-us-ky-2026",
            "type": tax_type("CostSharingArrangement"),
            "name": "FY2026 Cost Sharing: US and Cayman",
            "domain": "taxation",
            "properties": {
                "transactionId": "TXN-CSA-2026-001",
                "transactionDate": "2026-12-31",
                "fiscalYear": 2026,
                "transactionValue": 125000000,
                "currency": "USD",
                "participants": ["TechGlobal Inc. (US)", "TechGlobal IP Holdings (Cayman)"],
                "allocationBasis": "Reasonably anticipated benefits (RAB)",
                "usShare": 0.65,
                "caymanShare": 0.35,
                "buyInPayment": 0,
                "selectedMethod": "Profit Split"
            }
        }
    ]

    for txn in transactions:
        all_twins.append(prepare_tax_twin(txn))

    # Transaction relationships
    txn_relationships = [
        ("txn-goods-us-ie-2026", "payer", "entity-techglobal-ie"),
        ("txn-goods-us-ie-2026", "payee", "entity-techglobal-us"),
        ("txn-goods-de-ie-2026", "payer", "entity-techglobal-ie"),
        ("txn-goods-de-ie-2026", "payee", "entity-techglobal-de"),
        ("txn-royalty-ky-us-2026", "payer", "entity-techglobal-us"),
        ("txn-royalty-ky-us-2026", "payee", "entity-techglobal-ky"),
        ("txn-royalty-ky-ie-2026", "payer", "entity-techglobal-ie"),
        ("txn-royalty-ky-ie-2026", "payee", "entity-techglobal-ky"),
        ("txn-services-sg-jp-2026", "payer", "entity-techglobal-jp"),
        ("txn-services-sg-jp-2026", "payee", "entity-techglobal-sg"),
        ("txn-loan-us-de-2026", "payer", "entity-techglobal-de"),
        ("txn-loan-us-de-2026", "payee", "entity-techglobal-us"),
    ]

    for txn_id, rel_type, entity_id in txn_relationships:
        all_relationships.append((txn_id, tax_type(rel_type), entity_id, None))

    # Link transactions to methods
    method_links = [
        ("txn-goods-us-ie-2026", "method-tnmm"),
        ("txn-goods-de-ie-2026", "method-cost-plus"),
        ("txn-royalty-ky-us-2026", "method-cup"),
        ("txn-royalty-ky-ie-2026", "method-cup"),
        ("txn-services-sg-jp-2026", "method-cost-plus"),
        ("txn-services-us-all-2026", "method-cost-plus"),
        ("txn-loan-us-de-2026", "method-cup"),
        ("txn-csa-us-ky-2026", "method-profit-split"),
    ]

    for txn_id, method_id in method_links:
        all_relationships.append((txn_id, tax_type("usesMethod"), method_id, None))

    # =========================================================================
    # COMPARABLE COMPANIES
    # =========================================================================
    logger.info("Creating comparable companies...")

    # LRD Comparables
    lrd_comparables = [
        {"id": "comp-lrd-001", "name": "TechDist Solutions Inc.", "operatingMargin": 0.032, "grossMargin": 0.18, "revenue": 450000000, "sicCode": "5045", "dataYear": 2026},
        {"id": "comp-lrd-002", "name": "GlobalTech Distributors Ltd.", "operatingMargin": 0.038, "grossMargin": 0.20, "revenue": 680000000, "sicCode": "5045", "dataYear": 2026},
        {"id": "comp-lrd-003", "name": "ElectroWholesale Corp.", "operatingMargin": 0.041, "grossMargin": 0.19, "revenue": 320000000, "sicCode": "5045", "dataYear": 2026},
        {"id": "comp-lrd-004", "name": "DigiSupply Partners", "operatingMargin": 0.035, "grossMargin": 0.17, "revenue": 520000000, "sicCode": "5045", "dataYear": 2026},
        {"id": "comp-lrd-005", "name": "IT Distribution Group", "operatingMargin": 0.045, "grossMargin": 0.21, "revenue": 890000000, "sicCode": "5045", "dataYear": 2026},
        {"id": "comp-lrd-006", "name": "CompuChannel Inc.", "operatingMargin": 0.029, "grossMargin": 0.16, "revenue": 280000000, "sicCode": "5045", "dataYear": 2026},
        {"id": "comp-lrd-007", "name": "NetWare Distributors", "operatingMargin": 0.043, "grossMargin": 0.22, "revenue": 410000000, "sicCode": "5045", "dataYear": 2026},
        {"id": "comp-lrd-008", "name": "SysTech Supply Co.", "operatingMargin": 0.037, "grossMargin": 0.19, "revenue": 560000000, "sicCode": "5045", "dataYear": 2026},
    ]

    for comp in lrd_comparables:
        all_twins.append(prepare_tax_twin({
            "id": comp["id"],
            "type": tax_type("ComparableCompany"),
            "name": comp["name"],
            "domain": "taxation",
            "properties": {
                "companyName": comp["name"],
                "sicCode": comp["sicCode"],
                "operatingMargin": comp["operatingMargin"],
                "grossMargin": comp["grossMargin"],
                "revenue": comp["revenue"],
                "dataYear": comp["dataYear"],
                "functionalProfile": "Limited Risk Distributor",
                "acceptedAsComparable": True
            }
        }))

    # CM Comparables
    cm_comparables = [
        {"id": "comp-cm-001", "name": "PrecisionMfg Services GmbH", "operatingMargin": 0.055, "netCostPlusMarkup": 0.058, "revenue": 380000000, "sicCode": "3672", "dataYear": 2026},
        {"id": "comp-cm-002", "name": "EuroTech Manufacturing", "operatingMargin": 0.062, "netCostPlusMarkup": 0.066, "revenue": 290000000, "sicCode": "3672", "dataYear": 2026},
        {"id": "comp-cm-003", "name": "ContractBuild Industries", "operatingMargin": 0.048, "netCostPlusMarkup": 0.051, "revenue": 420000000, "sicCode": "3672", "dataYear": 2026},
        {"id": "comp-cm-004", "name": "TechAssembly Solutions", "operatingMargin": 0.058, "netCostPlusMarkup": 0.062, "revenue": 510000000, "sicCode": "3672", "dataYear": 2026},
        {"id": "comp-cm-005", "name": "MfgPartners Europe", "operatingMargin": 0.065, "netCostPlusMarkup": 0.069, "revenue": 340000000, "sicCode": "3672", "dataYear": 2026},
        {"id": "comp-cm-006", "name": "IndustrialCraft GmbH", "operatingMargin": 0.052, "netCostPlusMarkup": 0.055, "revenue": 275000000, "sicCode": "3672", "dataYear": 2026},
    ]

    for comp in cm_comparables:
        all_twins.append(prepare_tax_twin({
            "id": comp["id"],
            "type": tax_type("ComparableCompany"),
            "name": comp["name"],
            "domain": "taxation",
            "properties": {
                "companyName": comp["name"],
                "sicCode": comp["sicCode"],
                "operatingMargin": comp["operatingMargin"],
                "netCostPlusMarkup": comp["netCostPlusMarkup"],
                "revenue": comp["revenue"],
                "dataYear": comp["dataYear"],
                "functionalProfile": "Contract Manufacturer",
                "acceptedAsComparable": True
            }
        }))

    # SP Comparables
    sp_comparables = [
        {"id": "comp-sp-001", "name": "Asia Regional Services Pte Ltd", "operatingMargin": 0.085, "netCostPlusMarkup": 0.093, "revenue": 65000000, "sicCode": "7389", "dataYear": 2026},
        {"id": "comp-sp-002", "name": "ManagedOps Asia", "operatingMargin": 0.095, "netCostPlusMarkup": 0.105, "revenue": 88000000, "sicCode": "7389", "dataYear": 2026},
        {"id": "comp-sp-003", "name": "TechSupport International", "operatingMargin": 0.102, "netCostPlusMarkup": 0.114, "revenue": 72000000, "sicCode": "7389", "dataYear": 2026},
        {"id": "comp-sp-004", "name": "SharedServices Hub Pte", "operatingMargin": 0.078, "netCostPlusMarkup": 0.085, "revenue": 54000000, "sicCode": "7389", "dataYear": 2026},
        {"id": "comp-sp-005", "name": "RegionalAdmin Solutions", "operatingMargin": 0.112, "netCostPlusMarkup": 0.126, "revenue": 95000000, "sicCode": "7389", "dataYear": 2026},
    ]

    for comp in sp_comparables:
        all_twins.append(prepare_tax_twin({
            "id": comp["id"],
            "type": tax_type("ComparableCompany"),
            "name": comp["name"],
            "domain": "taxation",
            "properties": {
                "companyName": comp["name"],
                "sicCode": comp["sicCode"],
                "operatingMargin": comp["operatingMargin"],
                "netCostPlusMarkup": comp["netCostPlusMarkup"],
                "revenue": comp["revenue"],
                "dataYear": comp["dataYear"],
                "functionalProfile": "Service Provider",
                "acceptedAsComparable": True
            }
        }))

    # =========================================================================
    # ARM'S LENGTH RANGES
    # =========================================================================
    logger.info("Creating arm's length ranges...")
    ranges = [
        {
            "id": "alr-lrd-om-2026",
            "type": tax_type("ArmLengthRange"),
            "name": "LRD Operating Margin Range FY2026",
            "domain": "taxation",
            "properties": {
                "profitLevelIndicator": "Operating Margin",
                "functionalProfile": "Limited Risk Distributor",
                "dataYear": 2026,
                "minimumValue": 0.029,
                "lowerQuartile": 0.034,
                "median": 0.038,
                "upperQuartile": 0.043,
                "maximumValue": 0.045,
                "numberOfComparables": 8,
                "databaseUsed": "S&P Capital IQ"
            }
        },
        {
            "id": "alr-cm-ncpm-2026",
            "type": tax_type("ArmLengthRange"),
            "name": "Contract Mfg Net Cost Plus Range FY2026",
            "domain": "taxation",
            "properties": {
                "profitLevelIndicator": "Net Cost Plus Markup",
                "functionalProfile": "Contract Manufacturer",
                "dataYear": 2026,
                "minimumValue": 0.051,
                "lowerQuartile": 0.055,
                "median": 0.060,
                "upperQuartile": 0.066,
                "maximumValue": 0.069,
                "numberOfComparables": 6,
                "databaseUsed": "S&P Capital IQ"
            }
        },
        {
            "id": "alr-sp-ncpm-2026",
            "type": tax_type("ArmLengthRange"),
            "name": "Service Provider Net Cost Plus Range FY2026",
            "domain": "taxation",
            "properties": {
                "profitLevelIndicator": "Net Cost Plus Markup",
                "functionalProfile": "Service Provider",
                "dataYear": 2026,
                "minimumValue": 0.085,
                "lowerQuartile": 0.089,
                "median": 0.100,
                "upperQuartile": 0.112,
                "maximumValue": 0.126,
                "numberOfComparables": 5,
                "databaseUsed": "S&P Capital IQ"
            }
        }
    ]

    for r in ranges:
        all_twins.append(prepare_tax_twin(r))

    # =========================================================================
    # BACKGROUND DOCUMENTS
    # =========================================================================
    logger.info("Creating background documents...")
    documents = [
        {
            "id": "bgdoc-price-list-2026",
            "type": tax_type("BackgroundDocument"),
            "name": "FY2026 Intercompany Price List",
            "domain": "taxation",
            "properties": {
                "documentId": "BGDOC-2026-001",
                "documentTitle": "TechGlobal Intercompany Price List FY2026",
                "preparedDate": "2026-01-15",
                "preparedBy": "Transfer Pricing Department",
                "documentStatus": "final",
                "taxYear": 2026,
                "documentContent": """
TECHGLOBAL INC. - INTERCOMPANY PRICE LIST FY2026
=================================================

PRODUCT TRANSFERS (US to Ireland/Japan)
----------------------------------------
HW-ENT-1000: Enterprise Server          Unit Price: $6,800
HW-ENT-2000: Enterprise Storage         Unit Price: $12,500
HW-ENT-3000: Network Appliance          Unit Price: $3,200
SW-ENT-1000: Enterprise Software Suite  License: $45,000/seat

COMPONENT TRANSFERS (Germany to Ireland)
-----------------------------------------
COMP-PCB-001: Main Circuit Board        Unit Price: EUR 180
COMP-PSU-001: Power Supply Unit         Unit Price: EUR 95
COMP-CHS-001: Server Chassis            Unit Price: EUR 320
COMP-MEM-001: Memory Module             Unit Price: EUR 45

ROYALTY RATES
-------------
Manufacturing IP License: 3% of net sales
Trademark License: 4% of net sales
Software IP License: 5% of net sales

SERVICE FEES
------------
Management Services: Cost + 10%
Technical Services: Cost + 10%
R&D Support: Cost + 12%
""",
                "effectiveDate": "2026-01-01",
                "expirationDate": "2026-12-31"
            }
        },
        {
            "id": "bgdoc-invoices-sample-2026",
            "type": tax_type("BackgroundDocument"),
            "name": "Sample Intercompany Invoices Q4 2026",
            "domain": "taxation",
            "properties": {
                "documentId": "BGDOC-2026-002",
                "documentTitle": "Sample Intercompany Invoices Q4 2026",
                "preparedDate": "2026-12-31",
                "preparedBy": "Accounts Payable",
                "documentStatus": "final",
                "taxYear": 2026,
                "invoiceCount": 4,
                "totalValue": 70125000
            }
        },
        {
            "id": "bgdoc-financials-ie-2026",
            "type": tax_type("BackgroundDocument"),
            "name": "TechGlobal Ireland Financial Statements FY2026",
            "domain": "taxation",
            "properties": {
                "documentId": "BGDOC-2026-003",
                "preparedDate": "2026-02-15",
                "preparedBy": "External Auditors - Big4 LLP",
                "documentStatus": "final",
                "taxYear": 2026,
                "revenue": 1080000000,
                "operatingIncome": 75600000,
                "operatingMargin": 0.07,
                "auditOpinion": "Unqualified"
            }
        },
        {
            "id": "bgdoc-financials-de-2026",
            "type": tax_type("BackgroundDocument"),
            "name": "TechGlobal Germany Financial Statements FY2026",
            "domain": "taxation",
            "properties": {
                "documentId": "BGDOC-2026-004",
                "documentTitle": "TechGlobal Germany GmbH - Financial Statements FY2026",
                "preparedDate": "2026-02-15",
                "preparedBy": "External Auditors - Big4 LLP",
                "documentStatus": "final",
                "taxYear": 2026,
                "revenue": 405000000,
                "operatingIncome": 28350000,
                "operatingMargin": 0.07,
                "netCostPlusMarkup": 0.06,
                "auditOpinion": "Unqualified"
            }
        },
        {
            "id": "bgdoc-loan-agreement-2026",
            "type": tax_type("BackgroundDocument"),
            "name": "US-Germany Intercompany Loan Agreement",
            "domain": "taxation",
            "properties": {
                "documentId": "BGDOC-2026-005",
                "documentTitle": "Intercompany Loan Agreement - TechGlobal Inc. to TechGlobal Germany GmbH",
                "preparedDate": "2022-01-01",
                "preparedBy": "Legal Department",
                "documentStatus": "final",
                "taxYear": 2026,
                "principalAmount": 75000000,
                "interestRate": 0.06,
                "annualInterest": 4500000
            }
        },
        {
            "id": "bgdoc-royalty-agreements-2026",
            "type": tax_type("BackgroundDocument"),
            "name": "IP License Agreements Summary",
            "domain": "taxation",
            "properties": {
                "documentId": "BGDOC-2026-006",
                "documentTitle": "Summary of IP License Agreements",
                "preparedDate": "2026-03-15",
                "preparedBy": "Legal Department",
                "documentStatus": "final",
                "taxYear": 2026,
                "totalRoyalties": 148250000
            }
        }
    ]

    for doc in documents:
        all_twins.append(prepare_tax_twin(doc))

    # =========================================================================
    # COMPARABILITY ANALYSES
    # =========================================================================
    logger.info("Creating comparability analyses...")
    analyses = [
        {
            "id": "companalysis-lrd-2026",
            "type": tax_type("ComparabilityAnalysis"),
            "name": "LRD Benchmarking Study FY2026",
            "domain": "taxation",
            "properties": {
                "analysisId": "CA-LRD-2026",
                "testedParty": "TechGlobal Ireland Ltd.",
                "functionalProfile": "Limited Risk Distributor",
                "databaseUsed": "S&P Capital IQ",
                "searchDate": "2026-09-15",
                "companiesIdentified": 156,
                "companiesAccepted": 8,
                "rejectionCriteria": ["Non-comparable functions", "Insufficient data", "Loss-making entities", "Significant intangible ownership"]
            }
        },
        {
            "id": "companalysis-cm-2026",
            "type": tax_type("ComparabilityAnalysis"),
            "name": "Contract Mfg Benchmarking Study FY2026",
            "domain": "taxation",
            "properties": {
                "analysisId": "CA-CM-2026",
                "testedParty": "TechGlobal Germany GmbH",
                "functionalProfile": "Contract Manufacturer",
                "databaseUsed": "S&P Capital IQ",
                "searchDate": "2026-09-15",
                "companiesIdentified": 89,
                "companiesAccepted": 6,
                "rejectionCriteria": ["IP ownership", "Brand ownership", "Insufficient data", "Non-comparable products"]
            }
        },
        {
            "id": "companalysis-sp-2026",
            "type": tax_type("ComparabilityAnalysis"),
            "name": "Service Provider Benchmarking Study FY2026",
            "domain": "taxation",
            "properties": {
                "analysisId": "CA-SP-2026",
                "testedParty": "TechGlobal Asia Pacific Pte. Ltd.",
                "functionalProfile": "Service Provider",
                "databaseUsed": "S&P Capital IQ",
                "searchDate": "2026-09-15",
                "companiesIdentified": 67,
                "companiesAccepted": 5,
                "rejectionCriteria": ["Software development", "R&D activities", "Insufficient data", "Non-comparable services"]
            }
        }
    ]

    for analysis in analyses:
        all_twins.append(prepare_tax_twin(analysis))

    # Link analyses to arm's length ranges
    all_relationships.append(("companalysis-lrd-2026", tax_type("hasArmLengthRange"), "alr-lrd-om-2026", None))
    all_relationships.append(("companalysis-cm-2026", tax_type("hasArmLengthRange"), "alr-cm-ncpm-2026", None))
    all_relationships.append(("companalysis-sp-2026", tax_type("hasArmLengthRange"), "alr-sp-ncpm-2026", None))

    # Link analyses to comparable companies
    for i in range(1, 9):
        all_relationships.append(("companalysis-lrd-2026", tax_type("hasComparable"), f"comp-lrd-00{i}", None))
    for i in range(1, 7):
        all_relationships.append(("companalysis-cm-2026", tax_type("hasComparable"), f"comp-cm-00{i}", None))
    for i in range(1, 6):
        all_relationships.append(("companalysis-sp-2026", tax_type("hasComparable"), f"comp-sp-00{i}", None))

    # =========================================================================
    # BULK CREATE ALL TWINS AND RELATIONSHIPS
    # =========================================================================
    logger.info(f"Creating {len(all_twins)} twins via bulk API...")
    twins_created, _ = bulk_create_twins(client, all_twins, upsert=True)

    logger.info(f"Creating {len(all_relationships)} relationships via bulk API...")
    relationships_created, _ = bulk_add_relationships(client, all_relationships)

    print_summary("Transfer Pricing", twins_created, relationships_created)

    print("\nSeeded entities summary:")
    print(f"  - Jurisdictions: {len(jurisdictions)}")
    print(f"  - Legal Entities: {len(entities)}")
    print(f"  - TP Methods: {len(methods)}")
    print(f"  - Transactions: {len(transactions)}")
    print(f"  - Comparable Companies: {len(lrd_comparables) + len(cm_comparables) + len(sp_comparables)}")
    print(f"  - Arm's Length Ranges: {len(ranges)}")
    print(f"  - Background Documents: {len(documents)}")
    print(f"  - Comparability Analyses: {len(analyses)}")

    print("\nNext steps:")
    print("  1. Run: python report_generator.py")
    print("  2. Access the UI at http://localhost:8501")
    print("  3. Generate a Principal Document report from the background data")

    return {
        "twins_created": twins_created,
        "relationships_created": relationships_created
    }


if __name__ == "__main__":
    seed_taxation()
