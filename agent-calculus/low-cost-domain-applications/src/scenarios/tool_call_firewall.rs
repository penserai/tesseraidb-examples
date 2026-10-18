use crate::{
    DomainAssets, EffectSpec, EvidenceAssets, ExampleResult, NamedSroiqQuery, PolicyReport,
    RejectionProbe, Scenario, ShaclEvidenceBundle, class_check, exact_iri, policy_report,
    role_check, slot_iri,
};
use agent_calculus_domain::ReadyAction;
use serde_json::{Value, json};

const NS: &str = "urn:agent-calculus:tool-call-firewall:";
const ACTOR: &str = "urn:agent-calculus:tool-call-firewall:support-copilot";
const ISSUER: &str = "urn:agent-calculus:tool-call-firewall:tool-gateway";
const TICKET: &str = "urn:agent-calculus:tool-call-firewall:ticket-cs-884";
const ORDER: &str = "urn:agent-calculus:tool-call-firewall:order-ord-1042";
const OPERATION: &str = "urn:agent-calculus:tool-call-firewall:read-shipment-status";
const DURATION: &str = "urn:agent-calculus:tool-call-firewall:duration-60s";

#[derive(Debug)]
pub struct ToolCallFirewall;

pub static SCENARIO: ToolCallFirewall = ToolCallFirewall;

impl Scenario for ToolCallFirewall {
    fn id(&self) -> &'static str {
        "tool-call-firewall"
    }

    fn title(&self) -> &'static str {
        "Per-call least-privilege firewall for a support copilot"
    }

    fn assets(&self) -> DomainAssets {
        DomainAssets {
            manifest_json: include_str!("../../domains/tool-call-firewall/manifest.json"),
            request_shapes_turtle: include_str!(
                "../../domains/tool-call-firewall/request-shapes.ttl"
            ),
            ontology_ofn: include_str!("../../domains/tool-call-firewall/ontology.ofn"),
            evidence: EvidenceAssets {
                oracle_id: "tool-call-firewall-evidence-shacl",
                shapes_turtle: include_str!("../../domains/tool-call-firewall/evidence-shapes.ttl"),
                data_turtle: include_str!("../../domains/tool-call-firewall/evidence.ttl"),
            },
        }
    }

    fn actor(&self) -> &'static str {
        ACTOR
    }

    fn source(&self) -> &'static str {
        "authenticated-support-copilot"
    }

    fn turns(&self) -> &'static [&'static str] {
        &[
            "For ticket CS-884, check order ORD-1042.",
            "Read shipment status for 60 seconds.",
        ]
    }

    fn rejection_probe(&self) -> RejectionProbe {
        RejectionProbe {
            utterance: "Refund ORD-1042 and update the shipping address.",
            expected_code: "mutating_tool_operation",
        }
    }

    fn formal_queries(&self, ready: &ReadyAction) -> ExampleResult<Vec<NamedSroiqQuery>> {
        let ticket = slot_iri(ready, "ticket")?;
        let order = slot_iri(ready, "order")?;
        let operation = slot_iri(ready, "operation")?;
        let duration = slot_iri(ready, "duration")?;

        Ok(vec![
            class_check(
                "caller is eligible for the active support ticket",
                ready.principal.actor.as_str(),
                format!("{NS}EligibleSupportCaller"),
            ),
            class_check(
                "selected order is registered for support",
                order,
                format!("{NS}RegisteredSupportOrder"),
            ),
            class_check(
                "selected operation is an approved support read",
                operation,
                format!("{NS}ApprovedSupportOperation"),
            ),
            class_check(
                "selected capability duration is bounded",
                duration,
                format!("{NS}BoundedCapabilityDuration"),
            ),
            class_check(
                "capability issuer is approved",
                ISSUER,
                format!("{NS}ApprovedCapabilityIssuer"),
            ),
            role_check(
                "caller is assigned to the selected ticket",
                ready.principal.actor.as_str(),
                format!("{NS}assignedTo"),
                ticket,
            ),
            role_check(
                "issuer supports the selected operation",
                ISSUER,
                format!("{NS}supportsOperation"),
                operation,
            ),
            role_check(
                "operation supports the selected duration",
                operation,
                format!("{NS}supportsDuration"),
                duration,
            ),
        ])
    }

    fn evaluate_policy(
        &self,
        ready: &ReadyAction,
        evidence: &ShaclEvidenceBundle,
    ) -> ExampleResult<PolicyReport> {
        let predicate = |local: &str| format!("{NS}{local}");
        let ttl_seconds = evidence.number(&predicate("ttlSeconds"))?;
        let exact_path = evidence.literal(&predicate("allowedPath"))?;
        let method = evidence.literal(&predicate("allowedMethod"))?;
        let max_uses = evidence.number(&predicate("maxUses"))?;

        Ok(policy_report(
            "tool-call-firewall.policy.v1",
            [
                (
                    "authenticated caller is bound",
                    ready.principal.actor == ACTOR,
                ),
                (
                    "ticket is the active registered ticket",
                    exact_iri(ready, "ticket", TICKET)?
                        && evidence.iri(&predicate("ticket"))? == TICKET
                        && evidence.iri(&predicate("ticketStatus"))? == format!("{NS}active"),
                ),
                (
                    "order is referenced by that ticket",
                    exact_iri(ready, "order", ORDER)?
                        && evidence.iri(&predicate("referencedOrder"))? == ORDER,
                ),
                (
                    "operation is read-only shipment status",
                    exact_iri(ready, "operation", OPERATION)?
                        && evidence.iri(&predicate("allowedOperation"))? == OPERATION,
                ),
                (
                    "capability lifetime is exactly bounded",
                    exact_iri(ready, "duration", DURATION)? && ttl_seconds == 60.0,
                ),
                (
                    "tool path is exact and contains no wildcard",
                    exact_path == "/orders/ORD-1042/shipment-status" && !exact_path.contains('*'),
                ),
                (
                    "HTTP method and use count are least privilege",
                    method == "GET" && max_uses == 1.0,
                ),
                (
                    "action is capability issuance only",
                    ready.action_id == "issue_tool_capability",
                ),
            ],
            json!({
                "method": method,
                "path": exact_path,
                "purpose": evidence.iri(&predicate("purpose"))?,
                "ttl_seconds": ttl_seconds,
                "max_uses": max_uses,
                "evidence_data_digest": evidence.data_digest
            }),
        ))
    }

    fn effect_spec(&self) -> EffectSpec {
        EffectSpec {
            kind: "attenuated_tool_capability",
            outcome: "single-use read capability simulated",
            external_effect_field: "tool_called",
        }
    }

    fn effect_parameters(&self, ready: &ReadyAction) -> ExampleResult<Value> {
        Ok(json!({
            "issuer": ISSUER,
            "caller": ready.principal.actor.as_str(),
            "ticket": slot_iri(ready, "ticket")?,
            "order": slot_iri(ready, "order")?,
            "operation": slot_iri(ready, "operation")?,
            "duration": slot_iri(ready, "duration")?,
            "method": "GET",
            "path": "/orders/ORD-1042/shipment-status",
            "purpose": "resolve-delivery-status",
            "max_uses": 1,
            "credentials_issued": false
        }))
    }
}
