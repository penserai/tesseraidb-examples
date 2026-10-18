#![forbid(unsafe_code)]

use agent_calculus::{
    BackendError, Compiler, DecisionAnswer, DecisionQuestion, DecisionResponse, EffectExecutor,
    EffectRequest, EffectResponse, EffectRisk, ExecutionPolicy, FormalVerdict, GenerationResponse,
    GenerativeProvider, GuardRule, Node, NodeId, Operation, Program, Runtime, SystemOneProvider,
    ValueType,
};
use agent_calculus_jev::ReplaySystemOne;
use agent_calculus_llm::ReplayGenerative;
use agent_calculus_ollama::{
    DEFAULT_BASE_URL, DEFAULT_COMPLETION_MODEL, DEFAULT_DECISION_MODEL, OllamaGenerativeProvider,
    OllamaSystemOneProvider,
};
use agent_calculus_sroiq::{SroiqOracle, SroiqQuery};
use async_trait::async_trait;
use clap::Parser;
use serde::Deserialize;
use std::collections::BTreeMap;
use std::sync::Arc;

const TOOL_IRI: &str = "urn:agent-calculus:incident:checkout-health-snapshot";
const TOOL_CLASS_IRI: &str = "urn:agent-calculus:incident:ProductionSafeReadOnlyDiagnostic";

#[derive(Debug, Parser)]
#[command(about = "Interleave Clef, Qwen, and SROIQ for checkout incident response")]
struct Args {
    /// Use deterministic local fixtures instead of Ollama.
    #[arg(long)]
    replay: bool,
    /// Ollama decision model tag.
    #[arg(long, default_value = DEFAULT_DECISION_MODEL)]
    decision_model: String,
    /// Ollama ordinary-completion model tag.
    #[arg(long, default_value = DEFAULT_COMPLETION_MODEL)]
    completion_model: String,
    /// Base URL of the Ollama server.
    #[arg(long, default_value = DEFAULT_BASE_URL)]
    ollama_url: String,
    /// End-to-end deadline, including cold model loads.
    #[arg(long, default_value_t = 180_000)]
    deadline_ms: u64,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();
    let policy = ExecutionPolicy {
        deadline_ms: args.deadline_ms,
        max_llm_calls: 1,
        max_system_one_calls: 1,
        max_formal_calls: 1,
        max_effect_calls: 1,
        // Calibrated for this exact Clef question. The effect remains fixed,
        // read-only, and separately capability-checked by SROIQ.
        min_confidence: 0.85,
        ..ExecutionPolicy::default()
    };
    let compiled = Compiler::compile(program(), &policy)?;
    let mut runtime = Runtime::new();
    let (decision, generation) = providers(&args);
    runtime.register_system_one(decision);
    runtime.register_generative(generation);
    runtime.register_oracle(Arc::new(SroiqOracle::from_ofn("sroiq", ontology())?));
    runtime.register_effect(Arc::new(CheckoutDiagnostic));

    let report = runtime.execute(&compiled, &policy).await?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    if !report.failures.is_empty() {
        return Err(std::io::Error::other("incident workflow did not complete").into());
    }
    for required in [NodeId(3), NodeId(4), NodeId(5)] {
        if !report.values.contains_key(&required) {
            return Err(std::io::Error::other(format!(
                "required node {} did not complete",
                required.0
            ))
            .into());
        }
    }
    let brief: OperatorBrief = serde_json::from_value(report.values[&NodeId(5)].value.clone())?;
    brief.validate()?;
    Ok(())
}

fn providers(args: &Args) -> (Arc<dyn SystemOneProvider>, Arc<dyn GenerativeProvider>) {
    if args.replay {
        let decision = DecisionResponse {
            model: "clef-replay".into(),
            answers: BTreeMap::from([(
                "failure_domain".into(),
                DecisionAnswer::Choice {
                    choice: "payment_provider_degradation".into(),
                    probabilities: BTreeMap::from([
                        ("checkout_application_regression".into(), 0.03),
                        ("payment_provider_degradation".into(), 0.95),
                        ("traffic_or_client_anomaly".into(), 0.02),
                    ]),
                    confidence: 0.92,
                },
            )]),
            input_tokens: 164,
            output_tokens: 0,
            cost_microusd: 0,
        };
        let generation = GenerationResponse {
            model: "qwen-replay".into(),
            value: serde_json::json!({
                "incident_summary": "Payment authorization failures rose sharply across regions without a recent checkout deployment.",
                "likely_domain": "payment_provider_degradation",
                "observations": [
                    "Failure rate is 37% against a 0.6% baseline",
                    "The diagnostic found gateway timeouts across three regions"
                ],
                "next_steps": [
                    "Compare gateway failures by payment processor and region",
                    "Page the payments on-call if the error rate remains above the alert threshold"
                ],
                "customer_message": "We are investigating elevated checkout failures.",
                "caveats": ["The failure domain is a model triage result, not a proven root cause"]
            }),
            input_tokens: 120,
            output_tokens: 74,
            cost_microusd: 0,
        };
        (
            Arc::new(ReplaySystemOne::new("system-one", [decision])),
            Arc::new(ReplayGenerative::new("llm", [generation])),
        )
    } else {
        (
            Arc::new(OllamaSystemOneProvider::with_base_url(
                &args.ollama_url,
                &args.decision_model,
            )),
            Arc::new(OllamaGenerativeProvider::with_base_url(
                &args.ollama_url,
                &args.completion_model,
            )),
        )
    }
}

fn program() -> Program {
    let incident = serde_json::json!({
        "service": "checkout-api",
        "environment": "production",
        "window_minutes": 8,
        "payment_authorization_failure_rate": 0.37,
        "baseline_failure_rate": 0.006,
        "affected_regions": ["us-west", "us-east", "eu-west"],
        "symptom": "payment gateway requests time out after 10 seconds",
        "latest_deployment_minutes_ago": 430,
        "configuration_change_detected": false
    });
    let questions = BTreeMap::from([(
        "failure_domain".into(),
        DecisionQuestion::Choice {
            instructions: "Which failure domain best explains the observed checkout incident?"
                .into(),
            criteria: BTreeMap::from([
                (
                    "checkout_application_regression".into(),
                    "A checkout code deployment or application behavior caused the failures".into(),
                ),
                (
                    "payment_provider_degradation".into(),
                    "An upstream payment gateway or processor is degraded".into(),
                ),
                (
                    "traffic_or_client_anomaly".into(),
                    "Unusual client behavior or traffic shape caused the failures".into(),
                ),
            ]),
        },
    )]);
    Program {
        name: "checkout-incident-response".into(),
        nodes: vec![
            Node {
                id: NodeId(0),
                label: "observe checkout incident".into(),
                output_type: ValueType::Json,
                operation: Operation::Observe {
                    value: incident,
                    source: "checkout-monitor".into(),
                },
            },
            Node {
                id: NodeId(1),
                label: "triage failure domain".into(),
                output_type: ValueType::Decision,
                operation: Operation::Decide {
                    provider: "system-one".into(),
                    state: NodeId(0),
                    questions,
                    max_attempts: 1,
                },
            },
            Node {
                id: NodeId(2),
                label: "require decisive triage".into(),
                output_type: ValueType::Decision,
                operation: Operation::Guard {
                    input: NodeId(1),
                    rules: vec![
                        GuardRule::MinimumConfidence { value: 0.85 },
                        GuardRule::MinimumChoiceMargin { value: 0.40 },
                    ],
                },
            },
            Node {
                id: NodeId(3),
                label: "certify fixed diagnostic capability".into(),
                output_type: ValueType::FormalJudgment,
                operation: Operation::Prove {
                    oracle: "sroiq".into(),
                    query: serde_json::to_value(SroiqQuery::ClassMembership {
                        individual_iri: TOOL_IRI.into(),
                        class_iri: TOOL_CLASS_IRI.into(),
                    })
                    .expect("query serializes"),
                    assumptions: vec![NodeId(2)],
                    max_attempts: 1,
                },
            },
            Node {
                id: NodeId(4),
                label: "capture checkout health snapshot".into(),
                output_type: ValueType::EffectReceipt,
                operation: Operation::Effect {
                    executor: "checkout-diagnostics".into(),
                    authorization: NodeId(3),
                    payload: serde_json::json!({
                        "tool_iri": TOOL_IRI,
                        "service": "checkout-api",
                        "lookback_minutes": 10,
                        "filter": "payment_gateway_timeout"
                    }),
                    risk: EffectRisk::ReadOnly,
                },
            },
            Node {
                id: NodeId(5),
                label: "draft operator brief".into(),
                output_type: ValueType::Json,
                operation: Operation::Generate {
                    provider: "llm".into(),
                    inputs: vec![NodeId(0), NodeId(2), NodeId(3), NodeId(4)],
                    instructions: "Write a concise incident-response brief grounded only in the supplied observation, probabilistic triage, capability proof, and diagnostic receipt. Do not claim a proven root cause or any production mutation. Return only the requested JSON.".into(),
                    output_schema: operator_brief_schema(),
                    max_attempts: 1,
                },
            },
        ],
    }
}

fn operator_brief_schema() -> serde_json::Value {
    serde_json::json!({
        "type": "object",
        "additionalProperties": false,
        "required": ["incident_summary", "likely_domain", "observations", "next_steps", "customer_message", "caveats"],
        "properties": {
            "incident_summary": {"type": "string"},
            "likely_domain": {"type": "string"},
            "observations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 6,
                "items": {"type": "string"}
            },
            "next_steps": {
                "type": "array",
                "minItems": 2,
                "maxItems": 5,
                "items": {"type": "string"}
            },
            "customer_message": {"type": "string"},
            "caveats": {
                "type": "array",
                "minItems": 1,
                "maxItems": 4,
                "items": {"type": "string"}
            }
        }
    })
}

fn ontology() -> &'static str {
    r#"
Prefix(:=<urn:agent-calculus:incident:>)
Ontology(
 Declaration(Class(:OperationalTool))
 Declaration(Class(:DiagnosticTool))
 Declaration(Class(:ReadOnlyDiagnosticTool))
 Declaration(Class(:ProductionSafeTool))
 Declaration(Class(:ProductionSafeReadOnlyDiagnostic))
 Declaration(NamedIndividual(:checkout-health-snapshot))
 SubClassOf(:ReadOnlyDiagnosticTool :DiagnosticTool)
 SubClassOf(:DiagnosticTool :OperationalTool)
 EquivalentClasses(:ProductionSafeReadOnlyDiagnostic ObjectIntersectionOf(:ReadOnlyDiagnosticTool :ProductionSafeTool))
 ClassAssertion(:ReadOnlyDiagnosticTool :checkout-health-snapshot)
 ClassAssertion(:ProductionSafeTool :checkout-health-snapshot)
)
"#
}

#[derive(Debug)]
struct CheckoutDiagnostic;

#[async_trait]
impl EffectExecutor for CheckoutDiagnostic {
    fn id(&self) -> &str {
        "checkout-diagnostics"
    }

    async fn execute(&self, request: &EffectRequest) -> Result<EffectResponse, BackendError> {
        let payload_iri = request
            .payload
            .get("tool_iri")
            .and_then(|value| value.as_str());
        let proof_iri = request
            .authorization
            .value
            .get("individual_iri")
            .and_then(|value| value.as_str());
        if payload_iri != Some(TOOL_IRI) || proof_iri != Some(TOOL_IRI) {
            return Err(BackendError {
                backend: self.id().into(),
                message: "diagnostic payload is not bound to the certified tool IRI".into(),
            });
        }
        if request.authorization.formal_verdict != Some(FormalVerdict::Proven) {
            return Err(BackendError {
                backend: self.id().into(),
                message: "diagnostic capability is not proven".into(),
            });
        }
        Ok(EffectResponse {
            receipt: serde_json::json!({
                "tool_iri": TOOL_IRI,
                "observed_at": "2026-10-17T17:42:00Z",
                "matched_events": 2431,
                "top_error": "payment_gateway_timeout",
                "regions": {
                    "us-west": 0.41,
                    "us-east": 0.35,
                    "eu-west": 0.32
                },
                "production_state_changed": false
            }),
            cost_microusd: 0,
        })
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct OperatorBrief {
    incident_summary: String,
    likely_domain: String,
    observations: Vec<String>,
    next_steps: Vec<String>,
    customer_message: String,
    caveats: Vec<String>,
}

impl OperatorBrief {
    fn validate(&self) -> Result<(), std::io::Error> {
        let strings = [
            self.incident_summary.as_str(),
            self.likely_domain.as_str(),
            self.customer_message.as_str(),
        ];
        if strings.iter().any(|value| value.trim().is_empty())
            || self.observations.is_empty()
            || self.next_steps.len() < 2
            || self.caveats.is_empty()
        {
            return Err(std::io::Error::other(
                "operator brief did not satisfy semantic constraints",
            ));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn workflow_compiles_under_default_policy() {
        Compiler::compile(program(), &ExecutionPolicy::default()).unwrap();
    }

    #[tokio::test]
    async fn diagnostic_rejects_a_payload_not_bound_to_the_proof() {
        let request = EffectRequest {
            payload: serde_json::json!({"tool_iri": "urn:wrong"}),
            authorization: agent_calculus::EvidenceValue {
                value: serde_json::json!({"individual_iri": TOOL_IRI}),
                value_type: ValueType::FormalJudgment,
                kind: agent_calculus::EvidenceKind::Certified,
                source: "test".into(),
                confidence: None,
                formal_verdict: Some(FormalVerdict::Proven),
                certificate: None,
                assumptions: Vec::new(),
            },
        };
        assert!(CheckoutDiagnostic.execute(&request).await.is_err());
    }
}
