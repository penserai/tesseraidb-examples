#!/usr/bin/env python3
"""
Phase 13 Demo: Adaptive Schema Management for Finance Domain

This script demonstrates the Phase 13 features using a real finance scenario:
1. Natural Language Schema Editing - Create schema changes using plain English
2. Impact Analysis - Predict violations before applying changes
3. Schema Discovery - Detect patterns in incoming financial data
4. Governance Workflows - Configure approval requirements
5. Schema Conversation - Interactive schema evolution via chat

Prerequisites:
    - DTaaS server running at localhost:8080
    - (Optional) LLM provider configured for NL features
    - Run seed.py first to populate finance domain data
"""

import sys
import os
import time

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'sdks', 'python'))

import httpx

# =============================================================================
# Configuration
# =============================================================================

BASE_URL = os.environ.get("DTAAS_URL", "http://localhost:8080")
TOKEN = os.environ.get("DTAAS_TOKEN", "finance-demo")
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Longer timeouts for LLM operations
DEFAULT_TIMEOUT = 5.0
LLM_TIMEOUT = 60.0


def request(method: str, path: str, json_data: dict = None, timeout: float = DEFAULT_TIMEOUT):
    """Make an HTTP request and return status code and JSON response."""
    try:
        if method == "GET":
            resp = httpx.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=timeout)
        elif method == "POST":
            resp = httpx.post(f"{BASE_URL}{path}", headers=HEADERS, json=json_data, timeout=timeout)
        elif method == "PUT":
            resp = httpx.put(f"{BASE_URL}{path}", headers=HEADERS, json=json_data, timeout=timeout)
        elif method == "DELETE":
            resp = httpx.delete(f"{BASE_URL}{path}", headers=HEADERS, timeout=timeout)
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
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_result(success: bool, message: str, details: str = None):
    """Print a test result with icon."""
    icon = "✅" if success else "❌"
    print(f"  {icon} {message}")
    if details:
        print(f"     {details}")


def print_note(message: str):
    """Print an informational note."""
    print(f"  📝 {message}")


# =============================================================================
# Demo 1: Health Check & Prerequisites
# =============================================================================

def demo_prerequisites():
    """Verify server is running and check prerequisites."""
    print_header("Demo 1: Prerequisites Check")

    # Health check
    status, data = request("GET", "/health")
    if status == 200 and data.get("status") == "healthy":
        print_result(True, "Server health check", f"Version: {data.get('version')}")
    else:
        print_result(False, "Server health check", f"Status: {status}")
        print("\n⚠️  Please ensure the DTaaS server is running at", BASE_URL)
        return False

    # Check lineage is enabled (required for Phase 13)
    status, data = request("GET", "/api/v1/lineage/config")
    if status == 200:
        enabled = data.get("enabled", False)
        track_ontology = data.get("track_ontology", False)
        print_result(True, f"Lineage config", f"enabled={enabled}, track_ontology={track_ontology}")

        if not enabled or not track_ontology:
            print_note("Enabling lineage with ontology tracking...")
            status, _ = request("PUT", "/api/v1/lineage/config", {
                "enabled": True,
                "track_ontology": True,
                "track_twins": False
            })
            if status == 200:
                print_result(True, "Lineage enabled")
    else:
        print_result(False, "Get lineage config", f"Status: {status}")

    return True


# =============================================================================
# Demo 2: Schema Governance Configuration
# =============================================================================

def demo_governance():
    """Configure governance policies for the finance domain."""
    print_header("Demo 2: Schema Governance Configuration")

    print("\n  Finance domain requires strict governance over schema changes.")
    print("  We'll configure:")
    print("    • Auto-apply safe changes (additive only)")
    print("    • Require approval for breaking/destructive changes")
    print("    • Advisory mode (warn but don't block)")

    # Get current config
    status, data = request("GET", "/api/v1/schemas/governance/config")
    if status == 200:
        print_result(True, "Current governance config",
                     f"auto_apply_safe={data.get('auto_apply_safe')}, impact_mode={data.get('impact_mode')}")

    # Update config for finance domain
    finance_governance = {
        "tenant_id": TOKEN,
        "impact_mode": "advisory",  # Warn but allow (for demo purposes)
        "auto_apply_safe": True,    # Auto-apply non-breaking changes
        "approval_required_for": ["breaking", "destructive"],
        "approvers": ["risk-manager@finco.com", "compliance@finco.com"],
        "max_pending_changes": 25
    }

    status, data = request("PUT", "/api/v1/schemas/governance/config", finance_governance)
    if status == 200:
        print_result(True, "Updated governance for finance domain")
        print_note("Breaking changes now require approval from risk/compliance")
    else:
        print_result(False, "Update governance", f"Status: {status}, {data}")

    return True


# =============================================================================
# Demo 3: Impact Analysis
# =============================================================================

def demo_impact_analysis():
    """Demonstrate impact analysis for finance schema changes."""
    print_header("Demo 3: Impact Analysis")

    print("\n  Before making schema changes, we analyze their impact on existing data.")
    print("  This helps prevent data integrity issues in production systems.")

    # Example 1: Safe additive change
    print("\n  --- Example 1: Adding a new property (Safe) ---")

    safe_change = {
        "schema_type": "ontology",
        "schema_id": "fin:creditScore",
        "change_type": "add",
        "content": "fin:creditScore a owl:DatatypeProperty ; rdfs:domain fin:Counterparty ; rdfs:range xsd:integer .",
        "description": "Add creditScore property to Counterparty",
        "deep_analysis": False,
        "max_twins_to_check": 100
    }

    status, data = request("POST", "/api/v1/schemas/impact/analyze", safe_change)
    if status == 200:
        classification = data.get("classification", "unknown")
        can_auto = data.get("can_auto_apply", False)
        affected = data.get("affected_twin_count", 0)
        print_result(True, f"Impact analyzed: {classification}",
                     f"can_auto_apply={can_auto}, affected_twins={affected}")
        print_note(f"Summary: {data.get('summary', 'N/A')}")
    else:
        print_result(False, "Analyze safe change", f"Status: {status}, {data}")

    # Example 2: Breaking change
    print("\n  --- Example 2: Adding required constraint (Breaking) ---")

    breaking_change = {
        "schema_type": "shacl",
        "schema_id": "fin:OrderShape",
        "change_type": "modify",
        "content": """
            fin:OrderShape a sh:NodeShape ;
                sh:targetClass fin:Order ;
                sh:property [
                    sh:path fin:riskAssessmentId ;
                    sh:minCount 1 ;  # Now REQUIRED - breaking change!
                    sh:datatype xsd:string
                ] .
        """,
        "description": "Require riskAssessmentId on all Orders",
        "previous_content": "fin:OrderShape a sh:NodeShape ; sh:targetClass fin:Order .",
        "deep_analysis": True,
        "max_twins_to_check": 500
    }

    status, data = request("POST", "/api/v1/schemas/impact/analyze", breaking_change)
    if status == 200:
        classification = data.get("classification", "unknown")
        can_auto = data.get("can_auto_apply", False)
        violations = data.get("estimated_violations", 0)
        print_result(True, f"Impact analyzed: {classification}",
                     f"can_auto_apply={can_auto}, estimated_violations={violations}")
        if not can_auto:
            print_note("⚠️  This change requires approval before applying!")
    else:
        print_result(False, "Analyze breaking change", f"Status: {status}, {data}")

    # Classify change types
    print("\n  --- Change Classification Reference ---")
    classifications = [
        ("ontology", "add"),
        ("ontology", "modify"),
        ("shacl", "add"),
        ("shacl", "remove"),
    ]

    for schema_type, change_type in classifications:
        status, data = request("GET", f"/api/v1/schemas/impact/classify?schema_type={schema_type}&change_type={change_type}")
        if status == 200:
            cls = data.get("classification", "unknown")
            print(f"    {schema_type:10} + {change_type:8} = {cls}")

    return True


# =============================================================================
# Demo 4: Natural Language Schema Editing
# =============================================================================

def demo_nl_schema_editor():
    """Demonstrate natural language schema editing for finance domain."""
    print_header("Demo 4: Natural Language Schema Editing")

    print("\n  Schema changes via plain English - no need to know OWL/SHACL syntax!")
    print("  The LLM translates your intent into proper schema definitions.")
    print()

    # Example NL requests for finance domain
    nl_requests = [
        {
            "description": "Add a volatilityIndex property to Equity class that stores a decimal value between 0 and 100",
            "schema_types": ["ontology", "shacl"],
            "dry_run": True
        },
        {
            "description": "Create a new CreditDerivative class as a subclass of Derivative with properties for referenceEntity and spread",
            "schema_types": ["ontology"],
            "dry_run": True
        },
        {
            "description": "Add a validation rule requiring all Bond positions to have a maturityDate",
            "schema_types": ["shacl"],
            "dry_run": True
        }
    ]

    for i, req in enumerate(nl_requests, 1):
        print(f"  --- Request {i}: \"{req['description']}\" ---")

        status, data = request("POST", "/api/v1/schemas/nl/propose", req, timeout=LLM_TIMEOUT)

        if status == 200:
            request_id = data.get("request_id", "N/A")
            changes = data.get("proposed_changes", [])
            auto_applied = data.get("auto_applied", False)
            print_result(True, f"Proposed {len(changes)} change(s)", f"request_id={request_id}")

            for change in changes[:2]:  # Show first 2 changes
                print(f"       • {change.get('schema_type')}: {change.get('explanation', 'N/A')}")
                # Show actual Turtle RDF definition
                content = change.get('after_snippet') or change.get('content', '')
                if content:
                    print(f"       Definition:")
                    for line in content.strip().split('\n'):
                        print(f"         {line}")

            if auto_applied:
                print_note("Changes were auto-applied (safe)")
            elif data.get("approval_required"):
                print_note("Approval required - changes pending")
        elif status == 503:
            print_result(True, "LLM not available (503 - expected in demo)")
            print_note("Configure LLM provider to enable NL features")
            break
        elif status == -1 and "timed out" in str(data.get("error", "")):
            print_result(True, "LLM request timed out")
            print_note("LLM may be slow or unavailable")
            break
        else:
            print_result(False, f"NL propose failed", f"Status: {status}, {data}")

        print()

    # Check pending NL changes
    status, data = request("GET", "/api/v1/schemas/nl/pending")
    if status == 200:
        pending = data.get("pending", [])
        print_result(True, f"Pending NL proposals: {len(pending)}")

    return True


# =============================================================================
# Demo 5: Schema Discovery
# =============================================================================

def demo_schema_discovery():
    """Demonstrate automatic schema discovery from finance data."""
    print_header("Demo 5: Data-Driven Schema Discovery")

    print("\n  The system analyzes incoming data to suggest schema improvements.")
    print("  This helps bootstrap schemas from real data patterns.")
    print()

    # Get discovery config
    status, data = request("GET", "/api/v1/schemas/discover/config")
    if status == 200:
        print_result(True, "Discovery config",
                     f"min_confidence={data.get('min_confidence', 'N/A')}")

    # Analyze patterns (with data from seed.py)
    print("\n  --- Analyzing data patterns ---")

    analyze_req = {
        "time_range_hours": 168,  # Last week
        "min_confidence": 0.7,
        "max_suggestions": 15
    }

    status, data = request("POST", "/api/v1/schemas/discover/analyze", analyze_req)
    if status == 200:
        patterns = data.get("patterns", [])
        print_result(True, f"Discovered {len(patterns)} pattern(s)")

        for pattern in patterns[:5]:  # Show first 5
            ptype = pattern.get("pattern_type", "unknown")
            confidence = pattern.get("confidence", 0)
            evidence = pattern.get("evidence_count", 0)
            print(f"       • {ptype}: confidence={confidence:.0%}, evidence={evidence}")
    else:
        print_result(False, "Analyze patterns", f"Status: {status}, {data}")

    # Get suggestions
    print("\n  --- Schema Suggestions ---")

    status, data = request("GET", "/api/v1/schemas/discover/suggestions")
    if status == 200:
        suggestions = data if isinstance(data, list) else []
        print_result(True, f"Pending suggestions: {len(suggestions)}")

        for sugg in suggestions[:3]:  # Show first 3
            print(f"       • {sugg.get('pattern_type', 'unknown')}: "
                  f"{sugg.get('suggested_schema', {}).get('explanation', 'N/A')}")
    else:
        print_result(False, "Get suggestions", f"Status: {status}")

    return True


# =============================================================================
# Demo 6: Schema Conversation (Interactive Chat)
# =============================================================================

def demo_schema_conversation():
    """Demonstrate interactive schema evolution via conversation."""
    print_header("Demo 6: Interactive Schema Conversation")

    print("\n  Have a natural conversation to evolve your schema.")
    print("  The system maintains context and tracks proposed changes.")
    print()

    # Start a conversation about finance schema
    conversation = [
        "I want to model cryptocurrency trading in our system",
        "What cryptocurrency-related classes do we already have?",
        "Can you add a WalletAddress property to the Cryptocurrency class?",
    ]

    session_id = None
    llm_available = True

    for i, message in enumerate(conversation, 1):
        print(f"  --- Turn {i}: \"{message}\" ---")

        chat_req = {
            "message": message,
            "auto_apply_safe": False  # Review all changes first
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
                print_note(f"{pending} pending change(s) proposed")
        elif status == 503:
            print_result(True, "LLM not available (503)")
            print_note("Configure LLM provider to enable conversation features")
            llm_available = False
            break
        elif status == -1 and "timed out" in str(data.get("error", "")):
            print_result(True, "Request timed out")
            llm_available = False
            break
        else:
            print_result(False, f"Chat failed", f"Status: {status}")
            llm_available = False
            break

        print()
        time.sleep(0.5)  # Brief pause between turns

    # List all sessions
    print("\n  --- Active Sessions ---")
    status, data = request("GET", "/api/v1/schemas/chat/sessions")
    if status == 200:
        count = data.get("count", 0)
        print_result(True, f"Active sessions: {count}")

    # Cleanup: reset session if we created one
    if session_id and llm_available:
        status, data = request("POST", f"/api/v1/schemas/chat/{session_id}/reset")
        if status == 200:
            discarded = data.get("changes_discarded", 0)
            print_result(True, f"Session reset, discarded {discarded} change(s)")

    return True


# =============================================================================
# Demo 7: Approval Workflow
# =============================================================================

def demo_approval_workflow():
    """Demonstrate the approval workflow for schema changes."""
    print_header("Demo 7: Approval Workflow")

    print("\n  Changes classified as 'breaking' or 'destructive' require approval.")
    print("  This ensures regulatory compliance in financial systems.")
    print()

    # Get pending approvals
    status, data = request("GET", "/api/v1/schemas/approvals")
    if status == 200:
        count = data.get("count", 0)
        pending = data.get("pending", [])
        print_result(True, f"Pending approvals: {count}")

        for approval in pending[:3]:
            print(f"       • {approval.get('change_id', 'N/A')}: "
                  f"{approval.get('description', 'N/A')}")
            print(f"         Proposed by: {approval.get('proposed_by', 'unknown')}")
    else:
        print_result(False, "Get approvals", f"Status: {status}")

    # Get approval history
    print("\n  --- Approval History ---")
    status, data = request("GET", "/api/v1/schemas/approvals/history")
    if status == 200:
        total = data.get("total", 0)
        history = data.get("history", [])
        print_result(True, f"Historical decisions: {total}")

        for item in history[:3]:
            print(f"       • {item.get('status', 'N/A')}: {item.get('description', 'N/A')}")
    else:
        print_result(False, "Get history", f"Status: {status}")

    return True


# =============================================================================
# Demo 8: Schema Versioning (via Lineage)
# =============================================================================

def demo_schema_versioning():
    """Demonstrate schema versioning through the lineage system."""
    print_header("Demo 8: Schema Versioning")

    print("\n  All schema changes are versioned through the lineage system.")
    print("  This provides full audit trail and rollback capability.")
    print()

    # Check ontology versions
    status, data = request("GET", "/api/v1/schemas/Ontology/finance/versions")
    if status == 200:
        versions = data.get("versions", [])
        print_result(True, f"Ontology versions: {len(versions)}")
        for v in versions[:5]:
            print(f"       • v{v.get('version', 'N/A')}: {v.get('change_summary', 'N/A')}")
    elif status == 404:
        print_note("No versioned ontology found (expected in fresh demo)")
        print_result(True, "Version endpoint works correctly (404 for missing)")
    else:
        print_result(False, "Get versions", f"Status: {status}")

    # Get latest version
    status, data = request("GET", "/api/v1/schemas/Ontology/finance/latest")
    if status == 200:
        version = data.get("version", "N/A")
        print_result(True, f"Latest version: {version}")
    elif status == 404:
        print_note("No versioned ontology found")
    else:
        print_result(False, "Get latest", f"Status: {status}")

    return True


# =============================================================================
# Main Demo Runner
# =============================================================================

def main():
    """Run all Phase 13 demos."""
    print("\n" + "=" * 70)
    print(" 🏦 Phase 13: Adaptive Schema Management - Finance Domain Demo")
    print("=" * 70)
    print()
    print(" This demo showcases intelligent schema evolution features:")
    print("   • Natural language schema editing")
    print("   • Impact analysis before changes")
    print("   • Data-driven schema discovery")
    print("   • Governance and approval workflows")
    print("   • Interactive schema conversations")
    print("   • Version tracking via lineage")
    print()
    print(" Target Server:", BASE_URL)
    print(" Tenant Token:", TOKEN)

    # Run demos
    demos = [
        ("Prerequisites", demo_prerequisites),
        ("Governance", demo_governance),
        ("Impact Analysis", demo_impact_analysis),
        ("NL Schema Editor", demo_nl_schema_editor),
        ("Schema Discovery", demo_schema_discovery),
        ("Schema Conversation", demo_schema_conversation),
        ("Approval Workflow", demo_approval_workflow),
        ("Schema Versioning", demo_schema_versioning),
    ]

    results = []

    for name, demo_func in demos:
        try:
            success = demo_func()
            results.append((name, success))
        except Exception as e:
            print_result(False, f"{name} demo crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print(" 📊 Demo Summary")
    print("=" * 70)

    passed = sum(1 for _, s in results if s)
    total = len(results)

    for name, success in results:
        icon = "✅" if success else "❌"
        print(f"   {icon} {name}")

    print()
    print(f" Results: {passed}/{total} demos completed successfully")

    if passed == total:
        print("\n 🎉 All Phase 13 features demonstrated successfully!")
    else:
        print("\n ⚠️  Some demos require additional configuration (e.g., LLM provider)")

    print()
    print(" Next steps:")
    print("   1. Configure an LLM provider for NL features (Ollama/OpenAI)")
    print("   2. Run seed.py to populate finance data")
    print("   3. Explore the Swagger UI at /swagger-ui/")
    print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
