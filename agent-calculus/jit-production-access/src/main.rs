#![forbid(unsafe_code)]

use agent_calculus::{
    BackendError, DecisionAnswer, DecisionBatch, DecisionQuestion, DecisionResponse, FormalOracle,
    FormalVerdict, OracleRequest, SystemOneProvider, digest_json,
};
use agent_calculus_domain::{
    ClosedDomain, ContinuationToken, DecisionThresholds, DomainManifest, DomainValue,
    InMemorySessionStore, ObservedInput, PrincipalBinding, ReadyAction, SessionEngine,
    SessionPolicy, SessionSnapshot, SessionState, ShaclCoverageValidator, UNKNOWN_CHOICE_ID,
};
use agent_calculus_ollama::{DEFAULT_BASE_URL, DEFAULT_DECISION_MODEL, OllamaSystemOneProvider};
use agent_calculus_sroiq::{SroiqOracle, SroiqQuery};
use async_trait::async_trait;
use clap::Parser;
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::error::Error;
use std::io;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};

const NS: &str = "urn:agent-calculus:jit-access:";
const ACTOR: &str = "urn:agent-calculus:jit-access:alex-chen";
const SERVICE: &str = "urn:agent-calculus:jit-access:checkout-api";
const ENVIRONMENT: &str = "urn:agent-calculus:jit-access:production";
const REGION: &str = "urn:agent-calculus:jit-access:eu-west-1";
const INCIDENT: &str = "urn:agent-calculus:jit-access:incident-inc-4821";
const TOOL: &str = "urn:agent-calculus:jit-access:jit-lease-issuer";

#[derive(Debug, Parser)]
#[command(about = "Run a two-turn, closed-domain JIT access session")]
struct Args {
    /// Use the deterministic candidate-only provider instead of local Clef.
    #[arg(long)]
    replay: bool,
    /// Ollama decision model tag.
    #[arg(long, default_value = DEFAULT_DECISION_MODEL)]
    decision_model: String,
    /// Base URL of the Ollama server.
    #[arg(long, default_value = DEFAULT_BASE_URL)]
    ollama_url: String,
}

#[derive(Clone, Debug, Serialize)]
struct SroiqProofCheck {
    check: String,
    query: SroiqQuery,
    verdict: FormalVerdict,
    certificate: Value,
}

#[derive(Clone, Debug, Serialize)]
struct SroiqProofBundle {
    oracle_id: String,
    oracle_version: String,
    checks: Vec<SroiqProofCheck>,
}

#[derive(Debug, Default)]
struct CandidateOnlyReplay {
    calls: AtomicUsize,
}

#[async_trait]
impl SystemOneProvider for CandidateOnlyReplay {
    fn id(&self) -> &str {
        "candidate-only-replay"
    }

    fn version(&self) -> &str {
        "1"
    }

    fn configuration_fingerprint(&self) -> String {
        digest_json(&json!({
            "contract": "agent-calculus.example.candidate-only-replay.v1",
            "id": self.id(),
            "version": self.version()
        }))
    }

    async fn decide(&self, request: &DecisionBatch) -> Result<DecisionResponse, BackendError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let mut answers = BTreeMap::new();
        for (name, question) in &request.questions {
            let DecisionQuestion::Choice { criteria, .. } = question else {
                return Err(BackendError {
                    backend: self.id().into(),
                    message: "closed-domain replay accepts only choice questions".into(),
                });
            };
            let choice = criteria
                .keys()
                .find(|candidate| candidate.as_str() != UNKNOWN_CHOICE_ID)
                .filter(|candidate| candidate.starts_with("candidate:"))
                .cloned()
                .ok_or_else(|| BackendError {
                    backend: self.id().into(),
                    message: format!("question '{name}' has no issued candidate ID"),
                })?;
            let remainder = if criteria.len() > 1 {
                0.01 / (criteria.len() - 1) as f64
            } else {
                0.0
            };
            let probabilities = criteria
                .keys()
                .map(|candidate| {
                    (
                        candidate.clone(),
                        if candidate == &choice {
                            0.99
                        } else {
                            remainder
                        },
                    )
                })
                .collect();
            answers.insert(
                name.clone(),
                DecisionAnswer::Choice {
                    choice,
                    probabilities,
                    confidence: 0.99,
                },
            );
        }
        Ok(DecisionResponse {
            model: "candidate-only-replay".into(),
            answers,
            input_tokens: u64::try_from(request.state.to_string().split_whitespace().count())
                .unwrap_or(u64::MAX),
            output_tokens: 0,
            cost_microusd: 0,
        })
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::parse();
    let provider: Arc<dyn SystemOneProvider> = if args.replay {
        Arc::new(CandidateOnlyReplay::default())
    } else {
        Arc::new(OllamaSystemOneProvider::with_base_url(
            &args.ollama_url,
            &args.decision_model,
        ))
    };
    let report = run(provider, if args.replay { "replay" } else { "ollama-clef" }).await?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

async fn run(provider: Arc<dyn SystemOneProvider>, mode: &str) -> Result<Value, Box<dyn Error>> {
    let domain = ClosedDomain::compile(manifest()?)?;
    let coverage = ShaclCoverageValidator::from_turtle(
        "jit-access-shacl",
        include_str!("../domain/shapes.ttl"),
        None,
    )?;
    let engine = SessionEngine::new(
        domain,
        provider,
        Arc::new(coverage),
        Arc::new(InMemorySessionStore::new()),
        SessionPolicy {
            // Six required slots may be supplied one clarification at a time.
            // Keep enough budget for every fixed prompt plus one retry.
            max_turns: 8,
            max_system_one_calls: 8,
            system_one_timeout_ms: 30_000,
            thresholds: DecisionThresholds {
                // Clef reports an entropy-derived confidence in addition to
                // the candidate probabilities. Require both a non-trivial
                // entropy signal and a clear winner inside the closed set.
                min_confidence: 0.05,
                min_choice_margin: 0.25,
            },
        },
    )?;

    let started = engine.start("jit-access-demo", principal())?;
    let first_text = "I'm covering checkout. Give me prod access in eu-west for INC-4821.";
    let first = engine
        .resume(&continuation(&started)?, observed(first_text))
        .await?;
    let SessionState::Awaiting(first_await) = &first.state else {
        return Err(io::Error::other(format!(
            "turn one must await missing domain slots: {}",
            serde_json::to_string_pretty(&first)?
        ))
        .into());
    };
    let first_prompt = first_await.prompt.clone();

    let second_text = "Logs for half an hour.";
    let second = engine
        .resume(&first_await.continuation, observed(second_text))
        .await?;
    let SessionState::Ready(ready) = &second.state else {
        return Err(io::Error::other(format!(
            "turn two must become Ready after SHACL coverage: {}",
            serde_json::to_string_pretty(&second)?
        ))
        .into());
    };
    if !ready.coverage.conforms {
        return Err(io::Error::other("Ready without conforming SHACL coverage").into());
    }

    let formal_checks = prove_authorization(ready).await?;
    let receipt = simulate_lease(ready, &formal_checks).await?;
    Ok(json!({
        "scenario": "jit-production-access",
        "mode": mode,
        "turns": [
            {
                "input": first_text,
                "state": "awaiting",
                "prompt_id": first_prompt.id,
                "prompt": first_prompt.text,
                "coverage_conforms": first.history.last().and_then(|turn| turn.coverage.as_ref()).is_some_and(|coverage| coverage.conforms)
            },
            {
                "input": second_text,
                "state": "ready",
                "action": ready.action_id,
                "coverage_conforms": ready.coverage.conforms
            }
        ],
        "system_one_calls": second.usage.system_one_calls,
        "generative_calls": 0,
        "formal_checks": formal_checks,
        "policy": {
            "allowed": true,
            "rule": "read-only capability, active incident assignment, approved issuer, maximum 60 minute lease"
        },
        "simulated_effect_receipt": receipt
    }))
}

fn observed(text: &str) -> ObservedInput {
    let principal = principal();
    ObservedInput {
        actor: principal.actor,
        source: principal.source,
        text: text.into(),
    }
}

fn principal() -> PrincipalBinding {
    PrincipalBinding {
        actor: ACTOR.into(),
        source: "operator-chat".into(),
    }
}

fn continuation(snapshot: &SessionSnapshot) -> Result<ContinuationToken, io::Error> {
    match &snapshot.state {
        SessionState::Awaiting(awaiting) => Ok(awaiting.continuation.clone()),
        _ => Err(io::Error::other("session has no continuation")),
    }
}

fn authorization_queries(
    ready: &ReadyAction,
) -> Result<Vec<(&'static str, SroiqQuery)>, io::Error> {
    let actor = ready.principal.actor.as_str();
    let capability = slot_iri(ready, "capability")?;
    let incident = slot_iri(ready, "incident")?;
    Ok(vec![
        (
            "requester eligibility",
            SroiqQuery::ClassMembership {
                individual_iri: actor.into(),
                class_iri: format!("{NS}EligibleIncidentResponder"),
            },
        ),
        (
            "capability approval",
            SroiqQuery::ClassMembership {
                individual_iri: capability.into(),
                class_iri: format!("{NS}ApprovedJitCapability"),
            },
        ),
        (
            "issuer approval",
            SroiqQuery::ClassMembership {
                individual_iri: TOOL.into(),
                class_iri: format!("{NS}ApprovedJitLeaseIssuer"),
            },
        ),
        (
            "incident assignment",
            SroiqQuery::RoleAssertion {
                subject_iri: actor.into(),
                role_iri: format!("{NS}assignedTo"),
                object_iri: incident.into(),
            },
        ),
    ])
}

async fn prove_authorization(ready: &ReadyAction) -> Result<SroiqProofBundle, Box<dyn Error>> {
    let oracle = SroiqOracle::from_ofn("jit-access-sroiq", include_str!("../domain/ontology.ofn"))?;
    let mut reports = Vec::new();
    for (label, query) in authorization_queries(ready)? {
        let response = oracle
            .evaluate(&OracleRequest {
                payload: serde_json::to_value(&query)?,
                assumptions: vec![],
            })
            .await?;
        if response.verdict != FormalVerdict::Proven {
            return Err(io::Error::other(format!(
                "formal check '{label}' was {:?}",
                response.verdict
            ))
            .into());
        }
        reports.push(SroiqProofCheck {
            check: label.into(),
            query,
            verdict: response.verdict,
            certificate: response.certificate.ok_or_else(|| {
                io::Error::other(format!("formal check '{label}' omitted its certificate"))
            })?,
        });
    }
    Ok(SroiqProofBundle {
        oracle_id: oracle.id().into(),
        oracle_version: oracle.version().into(),
        checks: reports,
    })
}

async fn verify_authorization(
    ready: &ReadyAction,
    supplied: &SroiqProofBundle,
) -> Result<(), Box<dyn Error>> {
    let oracle = SroiqOracle::from_ofn("jit-access-sroiq", include_str!("../domain/ontology.ofn"))?;
    if supplied.oracle_id != oracle.id() || supplied.oracle_version != oracle.version() {
        return Err(io::Error::other("formal evidence belongs to a different oracle").into());
    }
    let expected = authorization_queries(ready)?;
    if supplied.checks.len() != expected.len() {
        return Err(io::Error::other("formal evidence has the wrong check count").into());
    }
    for (proof, (label, query)) in supplied.checks.iter().zip(expected) {
        let response = oracle
            .evaluate(&OracleRequest {
                payload: serde_json::to_value(&query)?,
                assumptions: vec![],
            })
            .await?;
        let certificate = response.certificate.ok_or_else(|| {
            io::Error::other(format!("formal check '{label}' omitted its certificate"))
        })?;
        if proof.check != label
            || proof.query != query
            || proof.verdict != FormalVerdict::Proven
            || response.verdict != FormalVerdict::Proven
            || proof.certificate != certificate
        {
            return Err(io::Error::other(format!(
                "formal evidence does not bind expected check '{label}'"
            ))
            .into());
        }
    }
    Ok(())
}

async fn simulate_lease(
    ready: &ReadyAction,
    formal_checks: &SroiqProofBundle,
) -> Result<Value, Box<dyn Error>> {
    let actor = ready.principal.actor.as_str();
    let service = slot_iri(ready, "service")?;
    let environment = slot_iri(ready, "environment")?;
    let region = slot_iri(ready, "region")?;
    let incident = slot_iri(ready, "incident")?;
    let capability = slot_iri(ready, "capability")?;
    let duration = slot_iri(ready, "duration")?;
    for (actual, expected, field) in [
        (service, SERVICE, "service"),
        (environment, ENVIRONMENT, "environment"),
        (region, REGION, "region"),
        (incident, INCIDENT, "incident"),
    ] {
        if actual != expected {
            return Err(
                io::Error::other(format!("policy rejected mismatched {field}: {actual}")).into(),
            );
        }
    }
    if !approved_read_capability(capability) {
        return Err(io::Error::other(format!(
            "policy rejected non-read-only capability: {capability}"
        ))
        .into());
    }
    let duration_minutes = lease_duration_minutes(duration)?;
    verify_authorization(ready, formal_checks).await?;
    if !ready.coverage.conforms
        || ready.action.action_iri != format!("{NS}issue-read-lease")
        || ready.action.capability_class_iri != format!("{NS}ApprovedJitCapability")
        || actor != ACTOR
        || ready.principal.source != "operator-chat"
    {
        return Err(io::Error::other("lease action is not coverage-bound").into());
    }
    let request_digest = digest_json(&serde_json::to_value(&ready.interpretation)?);
    let formal_evidence_digest = digest_json(&serde_json::to_value(formal_checks)?);
    let idempotency_digest = digest_json(&json!({
        "principal": ready.principal,
        "action": ready.action,
        "request_digest": request_digest,
        "formal_evidence_digest": formal_evidence_digest
    }));
    let idempotency_key = format!("jit-lease-{}", &idempotency_digest[..24]);
    Ok(json!({
        "mode": "simulation",
        "lease_id": format!("simulated-{idempotency_key}"),
        "idempotency_key": idempotency_key,
        "request_digest": request_digest,
        "formal_evidence_digest": formal_evidence_digest,
        "requester": actor,
        "service": service,
        "environment": environment,
        "region": region,
        "incident": incident,
        "capability": capability,
        "duration_minutes": duration_minutes,
        "expires_after_minutes": duration_minutes,
        "credential_material_issued": false
    }))
}

fn approved_read_capability(capability: &str) -> bool {
    matches!(
        capability,
        "urn:agent-calculus:jit-access:read-logs"
            | "urn:agent-calculus:jit-access:query-metrics"
            | "urn:agent-calculus:jit-access:run-read-only-diagnostic"
    )
}

fn lease_duration_minutes(duration: &str) -> Result<u64, io::Error> {
    match duration {
        "urn:agent-calculus:jit-access:duration-15m" => Ok(15),
        "urn:agent-calculus:jit-access:duration-30m" => Ok(30),
        "urn:agent-calculus:jit-access:duration-60m" => Ok(60),
        _ => Err(io::Error::other(format!(
            "policy rejected unsupported duration: {duration}"
        ))),
    }
}

fn slot_iri<'a>(ready: &'a ReadyAction, slot: &str) -> Result<&'a str, io::Error> {
    match ready
        .interpretation
        .slots
        .get(slot)
        .map(|selection| &selection.candidate.value)
    {
        Some(DomainValue::Iri(iri)) => Ok(iri),
        _ => Err(io::Error::other(format!(
            "Ready action lacks IRI slot '{slot}'"
        ))),
    }
}

fn manifest() -> Result<DomainManifest, serde_json::Error> {
    serde_json::from_str(include_str!("../domain/manifest.json"))
}

#[cfg(test)]
mod tests {
    use super::*;

    async fn ready_action(session_id: &str) -> ReadyAction {
        let coverage = ShaclCoverageValidator::from_turtle(
            "jit-access-shacl",
            include_str!("../domain/shapes.ttl"),
            None,
        )
        .expect("valid shapes");
        let engine = SessionEngine::new(
            ClosedDomain::compile(manifest().expect("manifest JSON")).expect("valid domain"),
            Arc::new(CandidateOnlyReplay::default()),
            Arc::new(coverage),
            Arc::new(InMemorySessionStore::new()),
            SessionPolicy::default(),
        )
        .expect("valid session engine");
        let started = engine
            .start(session_id, principal())
            .expect("session starts");
        let first = engine
            .resume(
                &continuation(&started).expect("initial continuation"),
                observed("I'm covering checkout. Give me prod access in eu-west for INC-4821."),
            )
            .await
            .expect("first turn succeeds");
        let SessionState::Awaiting(awaiting) = first.state else {
            panic!("first turn must await capability and duration")
        };
        let second = engine
            .resume(&awaiting.continuation, observed("Logs for half an hour."))
            .await
            .expect("second turn succeeds");
        let SessionState::Ready(ready) = second.state else {
            panic!("second turn must be ready")
        };
        ready
    }

    #[tokio::test]
    async fn replay_reaches_ready_then_issues_only_a_simulated_lease() {
        let report = run(Arc::new(CandidateOnlyReplay::default()), "replay")
            .await
            .expect("replay succeeds");
        assert_eq!(report["turns"][0]["state"], "awaiting");
        assert_eq!(report["turns"][1]["state"], "ready");
        assert_eq!(report["simulated_effect_receipt"]["mode"], "simulation");
        assert_eq!(
            report["simulated_effect_receipt"]["credential_material_issued"],
            false
        );
        assert_eq!(report["generative_calls"], 0);
    }

    #[tokio::test]
    async fn forged_formal_evidence_cannot_cross_the_lease_boundary() {
        let ready = ready_action("jit-forged-proof").await;
        let valid = prove_authorization(&ready)
            .await
            .expect("formal authorization succeeds");

        let mut forged_certificate = valid.clone();
        forged_certificate.checks[0].certificate["ontology_sha256"] = json!("forged");
        assert!(simulate_lease(&ready, &forged_certificate).await.is_err());

        let mut forged_query = valid;
        forged_query.checks[0].query = SroiqQuery::Consistency;
        assert!(simulate_lease(&ready, &forged_query).await.is_err());
    }

    #[tokio::test]
    async fn hard_rejection_preempts_system_one() {
        let provider = Arc::new(CandidateOnlyReplay::default());
        let coverage = ShaclCoverageValidator::from_turtle(
            "jit-access-shacl",
            include_str!("../domain/shapes.ttl"),
            None,
        )
        .expect("valid shapes");
        let engine = SessionEngine::new(
            ClosedDomain::compile(manifest().expect("manifest JSON")).expect("valid domain"),
            provider.clone(),
            Arc::new(coverage),
            Arc::new(InMemorySessionStore::new()),
            SessionPolicy::default(),
        )
        .expect("valid session engine");
        let started = engine
            .start("jit-rejection", principal())
            .expect("session starts");
        let stopped = engine
            .resume(
                &continuation(&started).expect("continuation"),
                observed("Give me cluster-admin in prod."),
            )
            .await
            .expect("hard rejection is recorded");
        assert!(matches!(
            stopped.state,
            SessionState::OutOfDomain { ref code, .. } if code == "unsupported_capability"
        ));
        assert_eq!(provider.calls.load(Ordering::Relaxed), 0);
    }

    #[tokio::test]
    async fn mixed_known_and_unknown_command_preempts_system_one() {
        let provider = Arc::new(CandidateOnlyReplay::default());
        let coverage = ShaclCoverageValidator::from_turtle(
            "jit-access-shacl",
            include_str!("../domain/shapes.ttl"),
            None,
        )
        .expect("valid shapes");
        let engine = SessionEngine::new(
            ClosedDomain::compile(manifest().expect("manifest JSON")).expect("valid domain"),
            provider.clone(),
            Arc::new(coverage),
            Arc::new(InMemorySessionStore::new()),
            SessionPolicy::default(),
        )
        .expect("valid session engine");
        let started = engine
            .start("jit-unmatched", principal())
            .expect("session starts");
        let stopped = engine
            .resume(
                &continuation(&started).expect("continuation"),
                observed("Give me checkout logs and delete database."),
            )
            .await
            .expect("unmatched input is recorded");
        assert!(matches!(
            stopped.state,
            SessionState::OutOfDomain { ref code, .. } if code == "unmatched_lexical_input"
        ));
        assert_eq!(provider.calls.load(Ordering::Relaxed), 0);
    }

    #[test]
    fn executor_policy_matches_the_manifest_read_only_capabilities_and_durations() {
        for capability in [
            "urn:agent-calculus:jit-access:read-logs",
            "urn:agent-calculus:jit-access:query-metrics",
            "urn:agent-calculus:jit-access:run-read-only-diagnostic",
        ] {
            assert!(approved_read_capability(capability));
        }
        for capability in [
            "urn:agent-calculus:jit-access:production-shell",
            "urn:agent-calculus:jit-access:change-configuration",
            "urn:agent-calculus:jit-access:cluster-admin",
        ] {
            assert!(!approved_read_capability(capability));
        }
        assert_eq!(
            lease_duration_minutes("urn:agent-calculus:jit-access:duration-15m").unwrap(),
            15
        );
        assert_eq!(
            lease_duration_minutes("urn:agent-calculus:jit-access:duration-30m").unwrap(),
            30
        );
        assert_eq!(
            lease_duration_minutes("urn:agent-calculus:jit-access:duration-60m").unwrap(),
            60
        );
        assert!(lease_duration_minutes("urn:agent-calculus:jit-access:duration-120m").is_err());
    }
}
