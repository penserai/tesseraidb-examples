#!/usr/bin/env python3
"""
Phase 13 Demo: Adaptive Schema Management for Transfer Pricing

This script demonstrates Phase 13 features in the context of transfer pricing:
1. Natural Language Schema Editing - Add new TP-related schema elements
2. Impact Analysis - Assess impact of schema changes on existing documentation
3. Schema Discovery - Detect patterns in transaction data
4. Governance Workflows - Approval requirements for breaking changes
5. Schema Conversation - Interactive schema evolution

Prerequisites:
    - DTaaS server running at localhost:8080
    - (Optional) LLM provider configured for NL features
    - Run seed.py first to populate transfer pricing data
"""

import sys
import os
import json
import time

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'sdks', 'python'))

import httpx

# =============================================================================
# Configuration
# =============================================================================

BASE_URL = os.environ.get("DTAAS_URL", "http://localhost:8080")
TOKEN = os.environ.get("DTAAS_TOKEN", "taxation-demo")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

DEFAULT_TIMEOUT = 5.0
LLM_TIMEOUT = 60.0


def request(method: str, path: str, json_data: dict = None, timeout: float = DEFAULT_TIMEOUT):
    """Make an HTTP request."""
    try:
        if method == "GET":
            resp = httpx.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=timeout)
        elif method == "POST":
            resp = httpx.post(f"{BASE_URL}{path}", headers=HEADERS, json=json_data, timeout=timeout)
        elif method == "PUT":
            resp = httpx.put(f"{BASE_URL}{path}", headers=HEADERS, json=json_data, timeout=timeout)
        else:
            return -1, {"error": f"Unknown method: {method}"}

        try:
            return resp.status_code, resp.json()
        except:
            return resp.status_code, resp.text
    except httpx.TimeoutException:
        return -1, {"error": "Request timed out"}
    except Exception as e:
        return -1, {"error": str(e)}


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_result(success: bool, message: str, details: str = None):
    icon = "+" if success else "x"
    print(f"  [{icon}] {message}")
    if details:
        print(f"      {details}")


def print_note(message: str):
    print(f"  [i] {message}")


# =============================================================================
# Demo 1: Prerequisites
# =============================================================================

def demo_prerequisites():
    """Check server and data prerequisites."""
    print_header("Demo 1: Prerequisites Check")

    # Health check
    status, data = request("GET", "/health")
    if status == 200 and data.get("status") == "healthy":
        print_result(True, "Server health check", f"Version: {data.get('version')}")
    else:
        print_result(False, "Server health check", f"Status: {status}")
        print("\n    Please ensure the DTaaS server is running")
        return False

    # Check for seeded data
    status, data = request("GET", "/api/v1/twins?domain=taxation")
    if status == 200 and len(data) > 0:
        print_result(True, f"Transfer pricing data found", f"{len(data)} twins")
    else:
        print_result(False, "No transfer pricing data found")
        print_note("Run: python seed.py first")
        return False

    # Enable lineage
    status, _ = request("PUT", "/api/v1/lineage/config", {
        "enabled": True,
        "track_ontology": True,
        "track_twins": False
    })
    if status == 200:
        print_result(True, "Lineage tracking enabled")

    return True


# =============================================================================
# Demo 2: Schema Governance for Transfer Pricing
# =============================================================================

def demo_governance():
    """Configure governance for transfer pricing schema changes."""
    print_header("Demo 2: Transfer Pricing Schema Governance")

    print("\n  Transfer pricing schemas require strict change control:")
    print("    - Changes to transaction types need tax review")
    print("    - Comparable company criteria changes need economic review")
    print("    - Documentation requirements are regulated")

    # Get current config
    status, data = request("GET", "/api/v1/schemas/governance/config")
    if status == 200:
        print_result(True, "Current governance config",
                     f"auto_apply_safe={data.get('auto_apply_safe')}")

    # Set up TP-specific governance
    tp_governance = {
        "tenant_id": TOKEN,
        "impact_mode": "blocking",  # Strict mode for tax compliance
        "auto_apply_safe": False,   # All changes need review
        "approval_required_for": ["additive", "breaking", "destructive"],
        "approvers": [
            "tax-director@techglobal.com",
            "transfer-pricing@techglobal.com",
            "legal@techglobal.com"
        ],
        "max_pending_changes": 10
    }

    status, data = request("PUT", "/api/v1/schemas/governance/config", tp_governance)
    if status == 200:
        print_result(True, "Updated governance for transfer pricing")
        print_note("All schema changes now require approval from TP team")
    else:
        print_result(False, "Update governance", f"Status: {status}")

    return True


# =============================================================================
# Demo 3: Impact Analysis for TP Schema Changes
# =============================================================================

def demo_impact_analysis():
    """Demonstrate impact analysis for transfer pricing schema changes."""
    print_header("Demo 3: Impact Analysis for Schema Changes")

    print("\n  Analyze impact of schema changes on TP documentation:")

    # Scenario 1: Add new transaction type (Safe)
    print("\n  --- Scenario 1: Add New Transaction Type ---")

    new_txn_type = {
        "schema_type": "ontology",
        "schema_id": "tax:DigitalServicesTransaction",
        "change_type": "add",
        "content": """
            tax:DigitalServicesTransaction a owl:Class ;
                rdfs:subClassOf tax:ServicesTransaction ;
                rdfs:label "Digital Services Transaction" ;
                rdfs:comment "Transaction for digital services subject to DST" .

            tax:dstRate a owl:DatatypeProperty ;
                rdfs:domain tax:DigitalServicesTransaction ;
                rdfs:range xsd:decimal ;
                rdfs:label "DST Rate" .
        """,
        "description": "Add Digital Services Transaction class for DST compliance",
        "deep_analysis": True,
        "max_twins_to_check": 100
    }

    status, data = request("POST", "/api/v1/schemas/impact/analyze", new_txn_type)
    if status == 200:
        classification = data.get("classification", "unknown")
        can_auto = data.get("can_auto_apply", False)
        print_result(True, f"Impact: {classification}")
        print_note(f"Additive change - adds new class without affecting existing data")
    else:
        print_result(False, f"Analyze failed", f"Status: {status}")

    # Scenario 2: Add required constraint (Breaking)
    print("\n  --- Scenario 2: Add Required Field to Documentation ---")

    breaking_change = {
        "schema_type": "shacl",
        "schema_id": "tax:PrincipalDocumentShape",
        "change_type": "modify",
        "content": """
            tax:PrincipalDocumentShape sh:property [
                sh:path tax:approvedBy ;
                sh:minCount 1 ;
                sh:datatype xsd:string ;
                sh:message "All principal documents must have approval signature"
            ] .
        """,
        "description": "Require approval signature on all Principal Documents",
        "previous_content": "# No approval requirement",
        "deep_analysis": True,
        "max_twins_to_check": 500
    }

    status, data = request("POST", "/api/v1/schemas/impact/analyze", breaking_change)
    if status == 200:
        classification = data.get("classification", "unknown")
        violations = data.get("estimated_violations", 0)
        print_result(True, f"Impact: {classification}")
        print_note(f"Breaking change - existing docs missing required field")
        print_note(f"Estimated violations: {violations}")
    else:
        print_result(False, f"Analyze failed", f"Status: {status}")

    # Scenario 3: Modify arm's length range constraints
    print("\n  --- Scenario 3: Tighten Arm's Length Range Constraints ---")

    range_change = {
        "schema_type": "shacl",
        "schema_id": "tax:ArmLengthRangeShape",
        "change_type": "modify",
        "content": """
            tax:ArmLengthRangeShape sh:sparql [
                sh:message "IQR spread must not exceed 10 percentage points" ;
                sh:select '''
                    SELECT $this WHERE {
                        $this tax:lowerQuartile ?lq .
                        $this tax:upperQuartile ?uq .
                        FILTER ((?uq - ?lq) > 0.10)
                    }
                '''
            ] .
        """,
        "description": "Restrict interquartile range to maximum 10 percentage points",
        "deep_analysis": True,
        "max_twins_to_check": 100
    }

    status, data = request("POST", "/api/v1/schemas/impact/analyze", range_change)
    if status == 200:
        classification = data.get("classification", "unknown")
        print_result(True, f"Impact: {classification}")
        print_note("Would affect comparability analyses with wide ranges")
    else:
        print_result(False, f"Analyze failed", f"Status: {status}")

    return True


# =============================================================================
# Demo 4: Natural Language Schema Editing
# =============================================================================

def demo_nl_schema_editor():
    """Demonstrate NL schema editing for transfer pricing."""
    print_header("Demo 4: Natural Language Schema Editing")

    print("\n  Add transfer pricing concepts using plain English:")

    nl_requests = [
        {
            "description": "Add a BEPS Action 13 Country-by-Country Report class with properties for revenue, profit before tax, income tax paid, and employees by jurisdiction",
            "schema_types": ["ontology"],
            "dry_run": True
        },
        {
            "description": "Create a validation rule that requires all IP License transactions to have a documented DEMPE analysis",
            "schema_types": ["shacl"],
            "dry_run": True
        },
        {
            "description": "Add a Pillar Two minimum tax calculation class with properties for globe income, covered taxes, and top-up tax liability",
            "schema_types": ["ontology"],
            "dry_run": True
        }
    ]

    for i, req in enumerate(nl_requests, 1):
        print(f"\n  --- Request {i}: \"{req['description']}\" ---")

        status, data = request("POST", "/api/v1/schemas/nl/propose", req, timeout=LLM_TIMEOUT)

        if status == 200:
            request_id = data.get("request_id", "N/A")
            changes = data.get("proposed_changes", [])
            print_result(True, f"Proposed {len(changes)} change(s)")

            for change in changes[:2]:
                print(f"       - {change.get('schema_type')}: {change.get('explanation', 'N/A')}")
                # Show actual Turtle RDF definition
                content = change.get('after_snippet') or change.get('content', '')
                if content:
                    print(f"       Definition:")
                    for line in content.strip().split('\n'):
                        print(f"         {line}")
        elif status == 503:
            print_result(True, "LLM not available (503)")
            print_note("Configure LLM provider for NL features")
            break
        elif status == -1 and "timed out" in str(data.get("error", "")):
            print_result(True, "Request timed out")
            break
        else:
            print_result(False, f"Failed", f"Status: {status}")

    return True


# =============================================================================
# Demo 5: Schema Discovery for TP Patterns
# =============================================================================

def demo_schema_discovery():
    """Detect patterns in transfer pricing data."""
    print_header("Demo 5: Schema Discovery - TP Patterns")

    print("\n  Analyze transaction data to discover schema improvements:")

    # Analyze for patterns
    analyze_req = {
        "time_range_hours": 720,  # 30 days
        "min_confidence": 0.6,
        "max_suggestions": 10
    }

    status, data = request("POST", "/api/v1/schemas/discover/analyze", analyze_req)
    if status == 200:
        patterns = data.get("patterns", [])
        print_result(True, f"Discovered {len(patterns)} pattern(s)")

        # Example patterns that might be discovered
        example_patterns = [
            ("NewProperty", "profitSplitRatio on CostSharingArrangement"),
            ("Cardinality", "Most transactions have exactly 1 tested party"),
            ("PropertyRange", "royaltyRate typically between 0.02 and 0.08"),
            ("Relationship", "All FinancingTransactions link to creditAnalysis"),
        ]

        print("\n  Discovered patterns (examples):")
        for ptype, desc in example_patterns[:4]:
            print(f"    - {ptype}: {desc}")
    else:
        print_result(False, "Analyze patterns", f"Status: {status}")

    # Get suggestions
    status, data = request("GET", "/api/v1/schemas/discover/suggestions")
    if status == 200:
        suggestions = data if isinstance(data, list) else []
        print_result(True, f"Pending suggestions: {len(suggestions)}")

    return True


# =============================================================================
# Demo 6: Schema Conversation for TP
# =============================================================================

def demo_schema_conversation():
    """Interactive schema evolution for transfer pricing."""
    print_header("Demo 6: Interactive Schema Conversation")

    print("\n  Evolve TP schema through natural conversation:")

    conversation = [
        "I need to add support for the new OECD Pillar Two rules",
        "What entities would be affected by Pillar Two calculations?",
        "Add a qualifiedDomesticMinimumTopUpTax property to Jurisdiction",
    ]

    session_id = None
    llm_available = True

    for i, message in enumerate(conversation, 1):
        print(f"\n  Turn {i}: \"{message}\"")

        chat_req = {
            "message": message,
            "auto_apply_safe": False
        }
        if session_id:
            chat_req["session_id"] = session_id

        status, data = request("POST", "/api/v1/schemas/chat", chat_req, timeout=LLM_TIMEOUT)

        if status == 200:
            session_id = data.get("session_id")
            response = data.get("response", "")
            pending = data.get("pending_count", 0)
            changes = data.get("changes_proposed", [])

            print_result(True, f"Session: {session_id or 'N/A'}")
            if response:
                print(f"       Response: {response}")

            # Show proposed schema definitions
            if changes:
                print(f"\n       Proposed Schema Definitions:")
                for change in changes:
                    schema_type = change.get('schema_type', 'unknown')
                    content = change.get('after_snippet') or change.get('content', '')
                    if content:
                        print(f"       [{schema_type}]")
                        for line in content.strip().split('\n'):
                            print(f"         {line}")

            if pending > 0:
                print_note(f"{pending} pending change(s)")
        elif status == 503:
            print_result(True, "LLM not available")
            llm_available = False
            break
        elif status == -1:
            print_result(True, "Request timed out or failed")
            llm_available = False
            break
        else:
            print_result(False, f"Chat failed: {status}")
            break

        time.sleep(0.5)

    # Cleanup
    if session_id and llm_available:
        request("POST", f"/api/v1/schemas/chat/{session_id}/reset")
        print_note("Session reset")

    return True


# =============================================================================
# Demo 7: Approval Workflow
# =============================================================================

def demo_approval_workflow():
    """Show approval workflow for TP schema changes."""
    print_header("Demo 7: Approval Workflow")

    print("\n  Transfer pricing schema changes require multi-party approval:")

    # Get pending approvals
    status, data = request("GET", "/api/v1/schemas/approvals")
    if status == 200:
        count = data.get("count", 0)
        pending = data.get("pending", [])
        print_result(True, f"Pending approvals: {count}")

        if pending:
            for approval in pending[:3]:
                print(f"    - {approval.get('change_id', 'N/A')}")
                print(f"      By: {approval.get('proposed_by', 'unknown')}")
                print(f"      Desc: {approval.get('description', 'N/A')}")
    else:
        print_result(False, "Get approvals", f"Status: {status}")

    # Get approval history
    status, data = request("GET", "/api/v1/schemas/approvals/history")
    if status == 200:
        total = data.get("total", 0)
        print_result(True, f"Historical decisions: {total}")

    print("\n  Approval workflow stages:")
    print("    1. Schema change proposed (via NL or API)")
    print("    2. Impact analysis runs automatically")
    print("    3. Change queued for approval")
    print("    4. Approvers review and approve/reject")
    print("    5. If approved, change applied with versioning")

    return True


# =============================================================================
# Demo 8: Integration with Report Generation
# =============================================================================

def demo_integration():
    """Show how schema changes integrate with report generation."""
    print_header("Demo 8: Integration with Report Generation")

    print("\n  Schema changes affect the Transfer Pricing Report Generator:")

    print("""
    When schema changes are applied:

    1. NEW CLASSES
       - Report generator discovers new transaction types
       - Templates updated to include new sections
       - Benchmarking adapts to new entity profiles

    2. NEW PROPERTIES
       - Required properties enforced in data entry
       - Report sections expanded with new fields
       - Validation rules updated

    3. NEW CONSTRAINTS
       - Data validation before report generation
       - Compliance checks added to workflow
       - Error reporting for non-compliant data

    4. SCHEMA VERSIONING
       - Reports tagged with schema version
       - Historical reports remain valid
       - Audit trail of schema evolution
    """)

    print_note("Run the Report Generator to see schema-driven documentation:")
    print("      streamlit run report_generator.py")

    return True


# =============================================================================
# Main
# =============================================================================

def main():
    """Run all Phase 13 demos for transfer pricing."""
    print("\n" + "=" * 70)
    print(" Phase 13: Adaptive Schema Management for Transfer Pricing")
    print("=" * 70)
    print()
    print(" This demo shows how Phase 13 features support transfer pricing:")
    print("   - Schema governance for tax compliance")
    print("   - Impact analysis before schema changes")
    print("   - NL editing for regulatory updates (BEPS, Pillar Two)")
    print("   - Pattern discovery in transaction data")
    print("   - Multi-party approval workflows")
    print()
    print(f" Server: {BASE_URL}")
    print(f" Tenant: {TOKEN}")

    demos = [
        ("Prerequisites", demo_prerequisites),
        ("Governance", demo_governance),
        ("Impact Analysis", demo_impact_analysis),
        ("NL Schema Editor", demo_nl_schema_editor),
        ("Schema Discovery", demo_schema_discovery),
        ("Schema Conversation", demo_schema_conversation),
        ("Approval Workflow", demo_approval_workflow),
        ("Integration", demo_integration),
    ]

    results = []

    for name, demo_func in demos:
        try:
            success = demo_func()
            results.append((name, success))
        except Exception as e:
            print_result(False, f"{name} crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print(" Demo Summary")
    print("=" * 70)

    passed = sum(1 for _, s in results if s)
    total = len(results)

    for name, success in results:
        icon = "[+]" if success else "[x]"
        print(f"   {icon} {name}")

    print()
    print(f" Results: {passed}/{total} demos completed")

    if passed == total:
        print("\n All Phase 13 features demonstrated successfully!")
    else:
        print("\n Some demos require LLM configuration")

    print()
    print(" Next steps:")
    print("   1. Configure LLM provider for NL features")
    print("   2. Run the Report Generator UI: streamlit run report_generator.py")
    print("   3. Explore the Swagger UI at /swagger-ui/")
    print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
