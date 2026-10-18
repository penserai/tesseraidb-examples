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
use agent_calculus_shacl::{ShaclCertificate, ShaclOracle, ShaclQuery};
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

const NS: &str = "urn:agent-calculus:wind-safe-stop:";
const ACTOR: &str = "urn:agent-calculus:wind-safe-stop:morgan-reyes";
const ASSET: &str = "urn:agent-calculus:wind-safe-stop:wt-204";
const ACTION: &str = "urn:agent-calculus:wind-safe-stop:controlled-stop";
const WORK_ORDER: &str = "urn:agent-calculus:wind-safe-stop:work-order-wo-7712";
const TOOL: &str = "urn:agent-calculus:wind-safe-stop:scada-controlled-stop";
const SENSOR: &str = "urn:agent-calculus:wind-safe-stop:wt-204-bearing-vibration";
const METRIC: &str = "urn:agent-calculus:wind-safe-stop:main-bearing-vibration";
const UNIT: &str = "urn:agent-calculus:wind-safe-stop:millimeter-per-second";
const CALIBRATION: &str = "urn:agent-calculus:wind-safe-stop:calibration-vibration-2026-09";
const SOURCE: &str = "urn:agent-calculus:wind-safe-stop:scada";
const SYMPTOM: &str = "urn:agent-calculus:wind-safe-stop:excess-vibration";

#[derive(Clone, Debug, Serialize)]
struct TelemetryObservation {
    evidence_kind: &'static str,
    source: &'static str,
    asset: &'static str,
    sensor: &'static str,
    metric: &'static str,
    symptom: &'static str,
    numeric_value: f64,
    unit: &'static str,
    observed_at: &'static str,
    observed_at_unix_ms: u64,
    evaluated_at: &'static str,
    evaluated_at_unix_ms: u64,
    calibration: &'static str,
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

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
struct ApprovalEvidence {
    evidence_kind: String,
    source: String,
    approval_id: String,
    actor: String,
    asset: String,
    action: String,
    work_order: String,
    approved: bool,
}

impl TelemetryObservation {
    fn to_turtle(&self) -> String {
        format!(
            r#"@prefix : <{NS}> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
:telemetry-observation a :TelemetryObservation ;
    :sensor <{sensor}> ;
    :asset <{asset}> ;
    :metric <{metric}> ;
    :supportsReason <{symptom}> ;
    :numericValue "{numeric_value}"^^xsd:decimal ;
    :unit <{unit}> ;
    :observedAt "{observed_at}"^^xsd:dateTime ;
    :source <{source}> ;
    :calibration <{calibration}> .
<{calibration}> a :CurrentCalibration .
"#,
            sensor = self.sensor,
            asset = self.asset,
            metric = self.metric,
            symptom = self.symptom,
            numeric_value = self.numeric_value,
            unit = self.unit,
            observed_at = self.observed_at,
            source = self.source,
            calibration = self.calibration,
        )
    }
}

#[derive(Debug, Parser)]
#[command(about = "Run a two-turn, closed-domain turbine safe-stop session")]
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
        "wind-stop-shacl",
        include_str!("../domain/shapes.ttl"),
        None,
    )?;
    let engine = SessionEngine::new(
        domain,
        provider,
        Arc::new(coverage),
        Arc::new(InMemorySessionStore::new()),
        SessionPolicy {
            // Four required slots may be supplied one clarification at a time.
            max_turns: 6,
            max_system_one_calls: 6,
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

    let started = engine.start("wind-safe-stop-demo", principal())?;
    let first_text = "WT-204 is shaking hard. Shut it down.";
    let first = engine
        .resume(&continuation(&started)?, observed(first_text))
        .await?;
    let SessionState::Awaiting(first_await) = &first.state else {
        return Err(io::Error::other(format!(
            "turn one must await stop mode and work order: {}",
            serde_json::to_string_pretty(&first)?
        ))
        .into());
    };
    let first_prompt = first_await.prompt.clone();

    let second_text = "Controlled stop under WO-7712.";
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
    let approval = approval_evidence(ready)?;
    let telemetry = telemetry_evidence();
    let telemetry_certificate = validate_telemetry(&telemetry).await?;
    let receipt = simulate_stop(
        ready,
        &formal_checks,
        &approval,
        &telemetry,
        &telemetry_certificate,
    )
    .await?;
    Ok(json!({
        "scenario": "wind-turbine-safe-stop",
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
        "deterministic_policy": {
            "allowed": true,
            "telemetry_shape_conforms": telemetry_certificate.report.conforms,
            "telemetry_data_digest": telemetry_certificate.data_sha256,
            "telemetry_max_age_seconds": 60,
            "vibration_stop_threshold_mm_s": 12.0
        },
        "approval_evidence": approval,
        "telemetry_evidence": telemetry,
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
    let action = slot_iri(ready, "action")?;
    let asset = slot_iri(ready, "asset")?;
    let work_order = slot_iri(ready, "work_order")?;
    Ok(vec![
        (
            "operator eligibility",
            SroiqQuery::ClassMembership {
                individual_iri: actor.into(),
                class_iri: format!("{NS}EligibleControlledStopOperator"),
            },
        ),
        (
            "asset type",
            SroiqQuery::ClassMembership {
                individual_iri: asset.into(),
                class_iri: format!("{NS}VariableSpeedWindTurbine"),
            },
        ),
        (
            "work order active",
            SroiqQuery::ClassMembership {
                individual_iri: work_order.into(),
                class_iri: format!("{NS}ActiveMaintenanceWorkOrder"),
            },
        ),
        (
            "tool safety class",
            SroiqQuery::ClassMembership {
                individual_iri: TOOL.into(),
                class_iri: format!("{NS}SafetyPreservingTool"),
            },
        ),
        (
            "operator certified for asset",
            SroiqQuery::RoleAssertion {
                subject_iri: actor.into(),
                role_iri: format!("{NS}certifiedFor"),
                object_iri: asset.into(),
            },
        ),
        (
            "tool supports action",
            SroiqQuery::RoleAssertion {
                subject_iri: TOOL.into(),
                role_iri: format!("{NS}supportsAction"),
                object_iri: action.into(),
            },
        ),
    ])
}

async fn prove_authorization(ready: &ReadyAction) -> Result<SroiqProofBundle, Box<dyn Error>> {
    let oracle = SroiqOracle::from_ofn("wind-stop-sroiq", include_str!("../domain/ontology.ofn"))?;
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
    let oracle = SroiqOracle::from_ofn("wind-stop-sroiq", include_str!("../domain/ontology.ofn"))?;
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

fn approval_evidence(ready: &ReadyAction) -> Result<ApprovalEvidence, io::Error> {
    Ok(ApprovalEvidence {
        evidence_kind: "observed".into(),
        source: "maintenance-registry".into(),
        approval_id: "approval-WO-7712-controlled-stop".into(),
        actor: ready.principal.actor.clone(),
        asset: slot_iri(ready, "asset")?.into(),
        action: slot_iri(ready, "action")?.into(),
        work_order: slot_iri(ready, "work_order")?.into(),
        approved: true,
    })
}

fn telemetry_evidence() -> TelemetryObservation {
    TelemetryObservation {
        evidence_kind: "observed",
        source: SOURCE,
        asset: ASSET,
        sensor: SENSOR,
        metric: METRIC,
        symptom: SYMPTOM,
        numeric_value: 14.2,
        unit: UNIT,
        observed_at: "2026-10-17T17:41:48Z",
        observed_at_unix_ms: 1_792_258_908_000_u64,
        evaluated_at: "2026-10-17T17:42:00Z",
        evaluated_at_unix_ms: 1_792_258_920_000_u64,
        calibration: CALIBRATION,
    }
}

async fn validate_telemetry(
    telemetry: &TelemetryObservation,
) -> Result<ShaclCertificate, Box<dyn Error>> {
    let oracle = ShaclOracle::from_turtle(
        "wind-telemetry-shacl",
        include_str!("../domain/shapes.ttl"),
        None,
    )?;
    let response = oracle
        .evaluate(&OracleRequest {
            payload: serde_json::to_value(ShaclQuery::ValidateTurtle {
                data: telemetry.to_turtle(),
                base_iri: None,
            })?,
            assumptions: vec![],
        })
        .await?;
    if response.verdict != FormalVerdict::Proven {
        return Err(io::Error::other("deterministic SCADA evidence failed SHACL").into());
    }
    Ok(serde_json::from_value(response.certificate.ok_or_else(
        || io::Error::other("SHACL proof omitted its certificate"),
    )?)?)
}

async fn verify_telemetry_certificate(
    telemetry: &TelemetryObservation,
    supplied: &ShaclCertificate,
) -> Result<(), Box<dyn Error>> {
    let expected = validate_telemetry(telemetry).await?;
    if supplied != &expected {
        return Err(io::Error::other(
            "SHACL certificate does not bind the exact telemetry document and validator",
        )
        .into());
    }
    Ok(())
}

async fn simulate_stop(
    ready: &ReadyAction,
    formal_checks: &SroiqProofBundle,
    approval: &ApprovalEvidence,
    telemetry: &TelemetryObservation,
    telemetry_certificate: &ShaclCertificate,
) -> Result<Value, Box<dyn Error>> {
    let actor = ready.principal.actor.as_str();
    let action = slot_iri(ready, "action")?;
    let asset = slot_iri(ready, "asset")?;
    let symptom = slot_iri(ready, "symptom")?;
    let work_order = slot_iri(ready, "work_order")?;
    verify_authorization(ready, formal_checks).await?;
    verify_telemetry_certificate(telemetry, telemetry_certificate).await?;
    if action != ACTION
        || asset != ASSET
        || symptom != SYMPTOM
        || work_order != WORK_ORDER
        || !ready.coverage.conforms
        || !telemetry_certificate.report.conforms
        || ready.action.action_iri != format!("{NS}execute-controlled-stop")
        || ready.action.capability_class_iri != format!("{NS}SafetyPreservingTool")
        || actor != ACTOR
        || ready.principal.source != "operator-chat"
    {
        return Err(io::Error::other("stop request is not coverage-bound").into());
    }
    if !approval.approved
        || approval.evidence_kind != "observed"
        || approval.source != "maintenance-registry"
        || approval.approval_id != "approval-WO-7712-controlled-stop"
        || approval.actor != actor
        || approval.asset != asset
        || approval.action != action
        || approval.work_order != work_order
    {
        return Err(io::Error::other("approval evidence does not bind the request").into());
    }
    let age_ms = telemetry
        .evaluated_at_unix_ms
        .checked_sub(telemetry.observed_at_unix_ms)
        .ok_or_else(|| io::Error::other("telemetry timestamp is in the future"))?;
    if telemetry.source != SOURCE
        || telemetry.asset != asset
        || telemetry.sensor != SENSOR
        || telemetry.metric != METRIC
        || telemetry.symptom != symptom
        || telemetry.unit != UNIT
        || telemetry.calibration != CALIBRATION
        || age_ms > 60_000
        || telemetry.numeric_value < 12.0
    {
        return Err(io::Error::other("telemetry policy did not authorize a stop").into());
    }
    let telemetry_value = serde_json::to_value(telemetry)?;
    let request_digest = digest_json(&serde_json::to_value(&ready.interpretation)?);
    let formal_evidence_digest = digest_json(&serde_json::to_value(formal_checks)?);
    let approval_digest = digest_json(&serde_json::to_value(approval)?);
    let telemetry_digest = digest_json(&telemetry_value);
    let telemetry_certificate_digest = digest_json(&serde_json::to_value(telemetry_certificate)?);
    let idempotency_digest = digest_json(&json!({
        "principal": ready.principal,
        "action": ready.action,
        "request_digest": request_digest,
        "formal_evidence_digest": formal_evidence_digest,
        "approval_digest": approval_digest,
        "telemetry_digest": telemetry_digest,
        "telemetry_certificate_digest": telemetry_certificate_digest
    }));
    let idempotency_key = format!("wind-stop-{}", &idempotency_digest[..24]);
    Ok(json!({
        "mode": "simulation",
        "command_id": format!("simulated-{idempotency_key}"),
        "idempotency_key": idempotency_key,
        "request_digest": request_digest,
        "formal_evidence_digest": formal_evidence_digest,
        "approval_digest": approval_digest,
        "telemetry_digest": telemetry_digest,
        "telemetry_certificate_digest": telemetry_certificate_digest,
        "telemetry_data_digest": telemetry_certificate.data_sha256,
        "telemetry_age_seconds": age_ms / 1_000,
        "actor": actor,
        "asset": asset,
        "action": action,
        "symptom": symptom,
        "work_order": work_order,
        "tool": TOOL,
        "resulting_state": "controlled_stop_accepted",
        "physical_command_sent": false
    }))
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
            "wind-stop-shacl",
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
                observed("WT-204 is shaking hard. Shut it down."),
            )
            .await
            .expect("first turn succeeds");
        let SessionState::Awaiting(awaiting) = first.state else {
            panic!("first turn must await controlled stop and work order")
        };
        let second = engine
            .resume(
                &awaiting.continuation,
                observed("Controlled stop under WO-7712."),
            )
            .await
            .expect("second turn succeeds");
        let SessionState::Ready(ready) = second.state else {
            panic!("second turn must be ready")
        };
        ready
    }

    #[tokio::test]
    async fn replay_binds_formal_approval_and_telemetry_before_simulation() {
        let report = run(Arc::new(CandidateOnlyReplay::default()), "replay")
            .await
            .expect("replay succeeds");
        assert_eq!(report["turns"][0]["state"], "awaiting");
        assert_eq!(report["turns"][1]["state"], "ready");
        assert_eq!(report["deterministic_policy"]["allowed"], true);
        assert_eq!(report["simulated_effect_receipt"]["mode"], "simulation");
        assert_eq!(
            report["simulated_effect_receipt"]["telemetry_age_seconds"],
            12
        );
        assert_eq!(
            report["simulated_effect_receipt"]["physical_command_sent"],
            false
        );
        assert_eq!(report["simulated_effect_receipt"]["symptom"], SYMPTOM);
        assert_eq!(
            report["simulated_effect_receipt"]["telemetry_data_digest"],
            report["deterministic_policy"]["telemetry_data_digest"]
        );
        assert!(
            report["simulated_effect_receipt"]["idempotency_key"]
                .as_str()
                .is_some_and(|key| key.starts_with("wind-stop-") && key.len() > 20)
        );
        assert_eq!(report["generative_calls"], 0);
    }

    #[tokio::test]
    async fn forged_formal_or_shacl_evidence_cannot_cross_the_stop_boundary() {
        let ready = ready_action("wind-forged-evidence").await;
        let formal = prove_authorization(&ready)
            .await
            .expect("formal authorization succeeds");
        let approval = approval_evidence(&ready).expect("approval fixture binds request");
        let telemetry = telemetry_evidence();
        let certificate = validate_telemetry(&telemetry)
            .await
            .expect("telemetry conforms");

        let mut forged_formal = formal.clone();
        forged_formal.checks[0].certificate["ontology_sha256"] = json!("forged");
        assert!(
            simulate_stop(&ready, &forged_formal, &approval, &telemetry, &certificate,)
                .await
                .is_err()
        );

        let mut forged_certificate = certificate;
        forged_certificate.data_sha256 = "forged".into();
        assert!(
            simulate_stop(&ready, &formal, &approval, &telemetry, &forged_certificate,)
                .await
                .is_err()
        );
    }

    #[tokio::test]
    async fn telemetry_shape_binds_the_selected_excess_vibration_reason_and_sensor() {
        let valid = telemetry_evidence();
        let certificate = validate_telemetry(&valid)
            .await
            .expect("fixture telemetry conforms");
        assert!(certificate.report.conforms);

        let mut wrong_reason = valid.clone();
        wrong_reason.symptom = "urn:agent-calculus:wind-safe-stop:over-temperature";
        assert!(validate_telemetry(&wrong_reason).await.is_err());

        let mut wrong_sensor = valid;
        wrong_sensor.sensor = "urn:agent-calculus:wind-safe-stop:wt-204-nacelle-temp";
        assert!(validate_telemetry(&wrong_sensor).await.is_err());
    }

    #[tokio::test]
    async fn unregistered_asset_preempts_system_one() {
        let provider = Arc::new(CandidateOnlyReplay::default());
        let coverage = ShaclCoverageValidator::from_turtle(
            "wind-stop-shacl",
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
            .start("wind-rejection", principal())
            .expect("session starts");
        let stopped = engine
            .resume(
                &continuation(&started).expect("continuation"),
                observed("Controlled stop WT-999 under WO-7712."),
            )
            .await
            .expect("closed lookup rejection is recorded");
        assert!(matches!(
            stopped.state,
            SessionState::OutOfDomain { ref code, .. } if code == "unsupported_asset"
        ));
        assert_eq!(provider.calls.load(Ordering::Relaxed), 0);
    }

    #[tokio::test]
    async fn unsupported_or_unmodeled_commands_never_reach_system_one() {
        for (session_id, text, expected_code) in [
            (
                "wind-emergency",
                "Emergency stop WT-204 under WO-7712 for shaking.",
                "unsupported_action",
            ),
            (
                "wind-unmatched",
                "Controlled stop WT-204 under WO-7712 for shaking and bypass brakes.",
                "unmatched_lexical_input",
            ),
        ] {
            let provider = Arc::new(CandidateOnlyReplay::default());
            let coverage = ShaclCoverageValidator::from_turtle(
                "wind-stop-shacl",
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
                .start(session_id, principal())
                .expect("session starts");
            let stopped = engine
                .resume(
                    &continuation(&started).expect("continuation"),
                    observed(text),
                )
                .await
                .expect("domain rejection is recorded");
            assert!(matches!(
                stopped.state,
                SessionState::OutOfDomain { ref code, .. } if code == expected_code
            ));
            assert_eq!(provider.calls.load(Ordering::Relaxed), 0);
        }
    }
}
