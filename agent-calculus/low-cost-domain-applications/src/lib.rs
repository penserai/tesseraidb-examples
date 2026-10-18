//! Runnable closed-domain applications whose normal control path never uses a
//! generative model.

#![forbid(unsafe_code)]

pub mod scenarios;

use agent_calculus::{
    BackendError, DecisionAnswer, DecisionBatch, DecisionQuestion, DecisionResponse, FormalOracle,
    FormalVerdict, OracleRequest, SystemOneProvider, digest_json,
};
use agent_calculus_domain::{
    ClosedDomain, ContinuationToken, CoverageGraph, CoverageRequest, CoverageValidator,
    DecisionThresholds, DomainManifest, DomainValue, InMemorySessionStore, ObservedInput,
    PrincipalBinding, ReadyAction, SessionEngine, SessionPolicy, SessionSnapshot, SessionState,
    ShaclCoverageValidator, UNKNOWN_CHOICE_ID,
};
use agent_calculus_shacl::ShaclOracle;
use agent_calculus_sroiq::{SroiqOracle, SroiqQuery};
use async_trait::async_trait;
use oxigraph::io::{RdfFormat, RdfParser};
use oxigraph::model::Term;
use oxigraph::store::Store;
use serde::Serialize;
use serde_json::{Map, Value, json};
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::io;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

pub type ExampleError = Box<dyn Error + Send + Sync>;
pub type ExampleResult<T> = Result<T, ExampleError>;

#[derive(Clone, Copy, Debug)]
pub struct EvidenceAssets {
    pub oracle_id: &'static str,
    pub shapes_turtle: &'static str,
    pub data_turtle: &'static str,
}

#[derive(Clone, Copy, Debug)]
pub struct DomainAssets {
    pub manifest_json: &'static str,
    pub request_shapes_turtle: &'static str,
    pub ontology_ofn: &'static str,
    pub evidence: EvidenceAssets,
}

#[derive(Clone, Copy, Debug)]
pub struct RejectionProbe {
    pub utterance: &'static str,
    pub expected_code: &'static str,
}

#[derive(Clone, Copy, Debug)]
pub struct EffectSpec {
    pub kind: &'static str,
    pub outcome: &'static str,
    pub external_effect_field: &'static str,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct NamedSroiqQuery {
    pub check: String,
    pub query: SroiqQuery,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct SroiqProofCheck {
    pub check: String,
    pub query: SroiqQuery,
    pub verdict: FormalVerdict,
    pub certificate: Value,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct SroiqProofBundle {
    pub oracle_id: String,
    pub oracle_version: String,
    pub checks: Vec<SroiqProofCheck>,
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct ShaclEvidenceBundle {
    pub oracle_id: String,
    pub oracle_version: String,
    pub verdict: FormalVerdict,
    pub data_digest: String,
    /// The single SHACL focus node whose closed evidence record was proven.
    pub focus_node: String,
    /// Typed claims parsed from that exact, digest-bound focus-node record.
    /// Deterministic policies consume these values instead of parallel Rust
    /// constants, preventing the policy and the validated RDF from drifting.
    pub claims: BTreeMap<String, Vec<EvidenceTerm>>,
    pub certificate: Value,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum EvidenceTerm {
    Iri {
        value: String,
    },
    Literal {
        lexical: String,
        datatype: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        language: Option<String>,
    },
}

impl ShaclEvidenceBundle {
    pub fn term(&self, predicate_iri: &str) -> ExampleResult<&EvidenceTerm> {
        let values = self
            .claims
            .get(predicate_iri)
            .ok_or_else(|| io::Error::other(format!("evidence lacks <{predicate_iri}>")))?;
        let [value] = values.as_slice() else {
            return Err(io::Error::other(format!(
                "evidence predicate <{predicate_iri}> must have exactly one value, got {}",
                values.len()
            ))
            .into());
        };
        Ok(value)
    }

    pub fn iri(&self, predicate_iri: &str) -> ExampleResult<&str> {
        let EvidenceTerm::Iri { value } = self.term(predicate_iri)? else {
            return Err(
                io::Error::other(format!("evidence <{predicate_iri}> is not an IRI")).into(),
            );
        };
        Ok(value)
    }

    pub fn literal(&self, predicate_iri: &str) -> ExampleResult<&str> {
        let EvidenceTerm::Literal { lexical, .. } = self.term(predicate_iri)? else {
            return Err(
                io::Error::other(format!("evidence <{predicate_iri}> is not a literal")).into(),
            );
        };
        Ok(lexical)
    }

    pub fn boolean(&self, predicate_iri: &str) -> ExampleResult<bool> {
        self.literal(predicate_iri)?.parse().map_err(|error| {
            io::Error::other(format!(
                "invalid boolean evidence <{predicate_iri}>: {error}"
            ))
            .into()
        })
    }

    pub fn number(&self, predicate_iri: &str) -> ExampleResult<f64> {
        self.literal(predicate_iri)?.parse().map_err(|error| {
            io::Error::other(format!(
                "invalid numeric evidence <{predicate_iri}>: {error}"
            ))
            .into()
        })
    }

    pub fn datetime(&self, predicate_iri: &str) -> ExampleResult<OffsetDateTime> {
        OffsetDateTime::parse(self.literal(predicate_iri)?, &Rfc3339).map_err(|error| {
            io::Error::other(format!(
                "invalid dateTime evidence <{predicate_iri}>: {error}"
            ))
            .into()
        })
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
pub struct PolicyReport {
    pub policy_id: String,
    pub allowed: bool,
    pub checks: BTreeMap<String, bool>,
    pub details: Value,
}

pub trait Scenario: Sync {
    fn id(&self) -> &'static str;
    fn title(&self) -> &'static str;
    fn assets(&self) -> DomainAssets;
    fn actor(&self) -> &'static str;
    fn source(&self) -> &'static str;
    fn turns(&self) -> &'static [&'static str];
    fn rejection_probe(&self) -> RejectionProbe;
    fn formal_queries(&self, ready: &ReadyAction) -> ExampleResult<Vec<NamedSroiqQuery>>;
    fn evaluate_policy(
        &self,
        ready: &ReadyAction,
        evidence: &ShaclEvidenceBundle,
    ) -> ExampleResult<PolicyReport>;
    fn effect_spec(&self) -> EffectSpec;
    fn effect_parameters(&self, ready: &ReadyAction) -> ExampleResult<Value>;

    fn session_policy(&self) -> SessionPolicy {
        SessionPolicy {
            max_turns: 8,
            max_system_one_calls: 8,
            system_one_timeout_ms: 30_000,
            thresholds: DecisionThresholds {
                // These packs issue at most one authority-bearing candidate
                // plus `unknown` for each question. Clef's job is therefore
                // closed selection, not calibrated authorization. A nonzero
                // floor still rejects zero-confidence answers and ties;
                // SHACL, SROIQ, and deterministic policy remain effect gates.
                min_confidence: 0.01,
                min_choice_margin: 0.01,
            },
        }
    }
}

#[derive(Debug, Default)]
pub struct CandidateOnlyReplay {
    calls: AtomicUsize,
}

impl CandidateOnlyReplay {
    #[must_use]
    pub fn calls(&self) -> usize {
        self.calls.load(Ordering::Relaxed)
    }
}

#[async_trait]
impl SystemOneProvider for CandidateOnlyReplay {
    fn id(&self) -> &str {
        "unique-candidate-replay"
    }

    fn version(&self) -> &str {
        "1"
    }

    fn configuration_fingerprint(&self) -> String {
        digest_json(&json!({
            "contract": "agent-calculus.example.unique-candidate-replay.v1",
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
            let issued = criteria
                .keys()
                .filter(|candidate| candidate.as_str() != UNKNOWN_CHOICE_ID)
                .cloned()
                .collect::<Vec<_>>();
            let [choice] = issued.as_slice() else {
                return Err(BackendError {
                    backend: self.id().into(),
                    message: format!(
                        "question '{name}' must have exactly one issued non-unknown choice in replay, got {}",
                        issued.len()
                    ),
                });
            };
            let probabilities = criteria
                .keys()
                .map(|candidate| {
                    (
                        candidate.clone(),
                        if candidate == choice { 0.99 } else { 0.01 },
                    )
                })
                .collect();
            answers.insert(
                name.clone(),
                DecisionAnswer::Choice {
                    choice: choice.clone(),
                    probabilities,
                    confidence: 0.99,
                },
            );
        }
        Ok(DecisionResponse {
            model: "unique-candidate-replay".into(),
            answers,
            input_tokens: u64::try_from(request.state.to_string().split_whitespace().count())
                .unwrap_or(u64::MAX),
            output_tokens: 0,
            cost_microusd: 0,
        })
    }
}

pub fn all_scenarios() -> Vec<&'static dyn Scenario> {
    scenarios::all()
}

pub async fn run_scenario(
    scenario: &'static dyn Scenario,
    provider: Arc<dyn SystemOneProvider>,
    mode: &str,
) -> ExampleResult<Value> {
    let prepared = prepare_scenario(scenario, provider).await?;
    let assets = scenario.assets();
    let ready = &prepared.ready;
    let evidence = prove_evidence(assets.evidence).await?;
    let formal = prove_sroiq(scenario, ready, assets).await?;
    let policy = scenario.evaluate_policy(ready, &evidence)?;
    require_allowed(&policy)?;
    let receipt = simulate_effect(
        scenario,
        &prepared.domain,
        prepared.coverage.as_ref(),
        &prepared.session_id,
        ready,
        &evidence,
        &formal,
        &policy,
    )
    .await?;

    Ok(json!({
        "scenario": scenario.id(),
        "title": scenario.title(),
        "mode": mode,
        "turns": prepared.turn_reports,
        "system_one_calls": prepared.snapshot.usage.system_one_calls,
        "generative_calls": 0,
        "usage": prepared.snapshot.usage,
        "request_coverage": ready.coverage,
        "observed_evidence": evidence,
        "formal_checks": formal,
        "deterministic_policy": policy,
        "simulated_effect_receipt": receipt
    }))
}

struct PreparedScenario {
    domain: ClosedDomain,
    coverage: Arc<ShaclCoverageValidator>,
    session_id: String,
    snapshot: SessionSnapshot,
    ready: ReadyAction,
    turn_reports: Vec<Value>,
}

async fn prepare_scenario(
    scenario: &'static dyn Scenario,
    provider: Arc<dyn SystemOneProvider>,
) -> ExampleResult<PreparedScenario> {
    let assets = scenario.assets();
    let manifest: DomainManifest = serde_json::from_str(assets.manifest_json)?;
    let domain = ClosedDomain::compile(manifest)?;
    let coverage = Arc::new(ShaclCoverageValidator::from_turtle(
        format!("{}-request-shacl", scenario.id()),
        assets.request_shapes_turtle,
        None,
    )?);
    let engine = SessionEngine::new(
        domain.clone(),
        provider,
        coverage.clone(),
        Arc::new(InMemorySessionStore::new()),
        scenario.session_policy(),
    )?;
    let session_id = format!("{}-example", scenario.id());
    let principal = principal(scenario);
    let mut snapshot = engine.start(&session_id, principal.clone())?;
    let mut turn_reports = Vec::new();
    for utterance in scenario.turns() {
        let token = continuation(&snapshot)?;
        snapshot = engine
            .resume(
                &token,
                ObservedInput {
                    actor: principal.actor.clone(),
                    source: principal.source.clone(),
                    text: (*utterance).into(),
                },
            )
            .await?;
        turn_reports.push(turn_report(utterance, &snapshot));
    }
    let SessionState::Ready(ready) = &snapshot.state else {
        return Err(io::Error::other(format!(
            "scenario '{}' did not reach Ready: {}",
            scenario.id(),
            serde_json::to_string_pretty(&snapshot)?
        ))
        .into());
    };
    Ok(PreparedScenario {
        domain,
        coverage,
        session_id,
        ready: ready.clone(),
        snapshot,
        turn_reports,
    })
}

pub async fn run_rejection_probe(
    scenario: &'static dyn Scenario,
) -> ExampleResult<(String, usize)> {
    let assets = scenario.assets();
    let manifest: DomainManifest = serde_json::from_str(assets.manifest_json)?;
    let provider = Arc::new(CandidateOnlyReplay::default());
    let coverage = Arc::new(ShaclCoverageValidator::from_turtle(
        format!("{}-request-shacl", scenario.id()),
        assets.request_shapes_turtle,
        None,
    )?);
    let engine = SessionEngine::new(
        ClosedDomain::compile(manifest)?,
        provider.clone(),
        coverage,
        Arc::new(InMemorySessionStore::new()),
        scenario.session_policy(),
    )?;
    let principal = principal(scenario);
    let started = engine.start(format!("{}-rejection", scenario.id()), principal.clone())?;
    let stopped = engine
        .resume(
            &continuation(&started)?,
            ObservedInput {
                actor: principal.actor,
                source: principal.source,
                text: scenario.rejection_probe().utterance.into(),
            },
        )
        .await?;
    let code = match stopped.state {
        SessionState::OutOfDomain { code, .. } | SessionState::Rejected { code, .. } => code,
        state => {
            return Err(io::Error::other(format!(
                "rejection probe for '{}' unexpectedly reached {state:?}",
                scenario.id()
            ))
            .into());
        }
    };
    Ok((code, provider.calls()))
}

fn principal(scenario: &dyn Scenario) -> PrincipalBinding {
    PrincipalBinding {
        actor: scenario.actor().into(),
        source: scenario.source().into(),
    }
}

fn continuation(snapshot: &SessionSnapshot) -> ExampleResult<ContinuationToken> {
    match &snapshot.state {
        SessionState::Awaiting(awaiting) => Ok(awaiting.continuation.clone()),
        state => Err(io::Error::other(format!(
            "session has no continuation from terminal state: {state:?}"
        ))
        .into()),
    }
}

fn turn_report(utterance: &str, snapshot: &SessionSnapshot) -> Value {
    match &snapshot.state {
        SessionState::Awaiting(awaiting) => json!({
            "input": utterance,
            "state": "awaiting",
            "reason": awaiting.reason_code,
            "prompt_id": awaiting.prompt.id,
            "prompt": awaiting.prompt.text
        }),
        SessionState::Ready(ready) => json!({
            "input": utterance,
            "state": "ready",
            "action": ready.action_id,
            "coverage_conforms": ready.coverage.conforms
        }),
        SessionState::OutOfDomain { code, message } => json!({
            "input": utterance,
            "state": "out_of_domain",
            "code": code,
            "message": message
        }),
        SessionState::Rejected { code, message } => json!({
            "input": utterance,
            "state": "rejected",
            "code": code,
            "message": message
        }),
    }
}

async fn prove_evidence(assets: EvidenceAssets) -> ExampleResult<ShaclEvidenceBundle> {
    let oracle = ShaclOracle::from_turtle(assets.oracle_id, assets.shapes_turtle, None)?;
    let response = oracle
        .evaluate(&OracleRequest {
            payload: json!({
                "query": "validate_turtle",
                "data": assets.data_turtle
            }),
            assumptions: vec![],
        })
        .await?;
    if response.verdict != FormalVerdict::Proven {
        return Err(io::Error::other(format!(
            "observed evidence for '{}' failed SHACL: {:?}; certificate={}",
            assets.oracle_id,
            response.verdict,
            serde_json::to_string(&response.certificate)?
        ))
        .into());
    }
    let certificate = response
        .certificate
        .ok_or_else(|| io::Error::other("SHACL evidence omitted its certificate"))?;
    let focus_nodes = certificate["report"]["focus_nodes"]
        .as_array()
        .ok_or_else(|| io::Error::other("SHACL certificate omitted focus nodes"))?;
    let [focus_node] = focus_nodes.as_slice() else {
        return Err(io::Error::other(format!(
            "evidence '{}' must prove exactly one focus node, got {}",
            assets.oracle_id,
            focus_nodes.len()
        ))
        .into());
    };
    let focus_node = focus_node
        .as_str()
        .ok_or_else(|| io::Error::other("SHACL focus node was not an IRI string"))?
        .trim_start_matches('<')
        .trim_end_matches('>')
        .to_owned();
    let claims = parse_focus_claims(assets.data_turtle, &focus_node)?;
    Ok(ShaclEvidenceBundle {
        oracle_id: oracle.id().into(),
        oracle_version: oracle.version().into(),
        verdict: response.verdict,
        data_digest: digest_json(&Value::String(assets.data_turtle.into())),
        focus_node,
        claims,
        certificate,
    })
}

fn parse_focus_claims(
    data_turtle: &str,
    focus_node: &str,
) -> ExampleResult<BTreeMap<String, Vec<EvidenceTerm>>> {
    let store = Store::new()?;
    store.load_from_slice(
        RdfParser::from_format(RdfFormat::Turtle).without_named_graphs(),
        data_turtle.as_bytes(),
    )?;
    let mut claims = BTreeMap::<String, Vec<EvidenceTerm>>::new();
    for quad in store.iter() {
        let quad = quad?;
        let subject = quad
            .subject
            .to_string()
            .trim_start_matches('<')
            .trim_end_matches('>')
            .to_owned();
        if subject != focus_node {
            continue;
        }
        let value = match &quad.object {
            Term::NamedNode(node) => EvidenceTerm::Iri {
                value: node.as_str().to_owned(),
            },
            Term::Literal(literal) => EvidenceTerm::Literal {
                lexical: literal.value().to_owned(),
                datatype: literal.datatype().as_str().to_owned(),
                language: literal.language().map(str::to_owned),
            },
            Term::BlankNode(_) | Term::Triple(_) => {
                return Err(io::Error::other(format!(
                    "focus-node claim <{}> has unsupported object {}",
                    quad.predicate.as_str(),
                    quad.object
                ))
                .into());
            }
        };
        claims
            .entry(quad.predicate.as_str().to_owned())
            .or_default()
            .push(value);
    }
    if claims.is_empty() {
        return Err(io::Error::other(format!(
            "SHACL focus node <{focus_node}> has no parsed claims"
        ))
        .into());
    }
    Ok(claims)
}

async fn prove_sroiq(
    scenario: &dyn Scenario,
    ready: &ReadyAction,
    assets: DomainAssets,
) -> ExampleResult<SroiqProofBundle> {
    let oracle = SroiqOracle::from_ofn(format!("{}-sroiq", scenario.id()), assets.ontology_ofn)?;
    let mut expected = vec![
        NamedSroiqQuery {
            check: "ontology consistency".into(),
            query: SroiqQuery::Consistency,
        },
        class_check(
            "compiled action satisfies its manifest capability class",
            &ready.action.action_iri,
            &ready.action.capability_class_iri,
        ),
    ];
    expected.extend(scenario.formal_queries(ready)?);
    let mut checks = Vec::with_capacity(expected.len());
    for named in expected {
        let response = oracle
            .evaluate(&OracleRequest {
                payload: serde_json::to_value(&named.query)?,
                assumptions: vec![],
            })
            .await?;
        if response.verdict != FormalVerdict::Proven {
            return Err(io::Error::other(format!(
                "formal check '{}' was {:?}",
                named.check, response.verdict
            ))
            .into());
        }
        checks.push(SroiqProofCheck {
            check: named.check,
            query: named.query,
            verdict: response.verdict,
            certificate: response
                .certificate
                .ok_or_else(|| io::Error::other("proven SROIQ response omitted its certificate"))?,
        });
    }
    Ok(SroiqProofBundle {
        oracle_id: oracle.id().into(),
        oracle_version: oracle.version().into(),
        checks,
    })
}

#[allow(clippy::too_many_arguments)]
async fn simulate_effect(
    scenario: &dyn Scenario,
    domain: &ClosedDomain,
    coverage: &ShaclCoverageValidator,
    session_id: &str,
    ready: &ReadyAction,
    supplied_evidence: &ShaclEvidenceBundle,
    supplied_formal: &SroiqProofBundle,
    supplied_policy: &PolicyReport,
) -> ExampleResult<Value> {
    verify_request_coverage(domain, coverage, session_id, ready)?;
    let expected_evidence = prove_evidence(scenario.assets().evidence).await?;
    if &expected_evidence != supplied_evidence {
        return Err(io::Error::other("effect rejected forged or stale SHACL evidence").into());
    }
    let expected_formal = prove_sroiq(scenario, ready, scenario.assets()).await?;
    if &expected_formal != supplied_formal {
        return Err(io::Error::other("effect rejected forged or stale SROIQ evidence").into());
    }
    let expected_policy = scenario.evaluate_policy(ready, &expected_evidence)?;
    require_allowed(&expected_policy)?;
    if &expected_policy != supplied_policy {
        return Err(
            io::Error::other("effect rejected forged deterministic policy evidence").into(),
        );
    }
    if ready.principal != principal(scenario) {
        return Err(
            io::Error::other("effect principal does not match authenticated scenario").into(),
        );
    }

    let parameters = scenario.effect_parameters(ready)?;
    let request_digest = digest_json(&serde_json::to_value(&ready.interpretation)?);
    let request_coverage_digest = digest_json(&serde_json::to_value(&ready.coverage)?);
    let observed_evidence_digest = digest_json(&serde_json::to_value(supplied_evidence)?);
    let formal_evidence_digest = digest_json(&serde_json::to_value(supplied_formal)?);
    let policy_digest = digest_json(&serde_json::to_value(supplied_policy)?);
    let spec = scenario.effect_spec();
    let effect_contract = json!({
        "kind": spec.kind,
        "outcome": spec.outcome,
        "external_effect_field": spec.external_effect_field,
    });
    let binding_digest = digest_json(&json!({
        "scenario": scenario.id(),
        "principal": ready.principal,
        "action_id": ready.action_id,
        "action": ready.action,
        "parameters": parameters,
        "request_digest": request_digest,
        "request_coverage_digest": request_coverage_digest,
        "observed_evidence_digest": observed_evidence_digest,
        "formal_evidence_digest": formal_evidence_digest,
        "policy_digest": policy_digest,
        "effect_contract": effect_contract,
    }));
    let mut receipt = Map::new();
    receipt.insert("mode".into(), json!("simulation"));
    receipt.insert("effect_kind".into(), json!(spec.kind));
    receipt.insert("outcome".into(), json!(spec.outcome));
    receipt.insert(spec.external_effect_field.into(), json!(false));
    receipt.insert(
        "receipt_id".into(),
        json!(format!(
            "simulated-{}-{}",
            scenario.id(),
            &binding_digest[..24]
        )),
    );
    receipt.insert(
        "idempotency_key".into(),
        json!(format!("{}-{}", scenario.id(), &binding_digest[..24])),
    );
    receipt.insert("parameters".into(), parameters);
    receipt.insert("request_digest".into(), json!(request_digest));
    receipt.insert(
        "request_coverage_digest".into(),
        json!(request_coverage_digest),
    );
    receipt.insert(
        "observed_evidence_digest".into(),
        json!(observed_evidence_digest),
    );
    receipt.insert(
        "formal_evidence_digest".into(),
        json!(formal_evidence_digest),
    );
    receipt.insert("policy_digest".into(), json!(policy_digest));
    receipt.insert(
        "effect_contract_digest".into(),
        json!(digest_json(&effect_contract)),
    );
    Ok(Value::Object(receipt))
}

fn verify_request_coverage(
    domain: &ClosedDomain,
    coverage: &ShaclCoverageValidator,
    session_id: &str,
    ready: &ReadyAction,
) -> ExampleResult<()> {
    let intent = ready
        .interpretation
        .intent
        .as_ref()
        .ok_or_else(|| io::Error::other("ready action lacks an intent"))?;
    let intent_spec = domain
        .manifest()
        .intents
        .get(&intent.intent)
        .ok_or_else(|| io::Error::other("ready action has an unknown intent"))?;
    if intent_spec.action != ready.action_id {
        return Err(io::Error::other("ready action does not match the selected intent").into());
    }
    let expected_action = domain
        .manifest()
        .actions
        .get(&ready.action_id)
        .ok_or_else(|| io::Error::other("ready action is absent from the domain manifest"))?;
    if expected_action != &ready.action {
        return Err(io::Error::other("ready action metadata does not match the manifest").into());
    }
    let predicate_slots = domain
        .manifest()
        .slots
        .iter()
        .map(|(slot, spec)| (spec.predicate_iri.clone(), slot.clone()))
        .collect();
    let mut properties: BTreeMap<String, Vec<DomainValue>> = BTreeMap::new();
    for (slot, selection) in &ready.interpretation.slots {
        let predicate = &domain
            .manifest()
            .slots
            .get(slot)
            .ok_or_else(|| io::Error::other(format!("unknown slot '{slot}'")))?
            .predicate_iri;
        properties
            .entry(predicate.clone())
            .or_default()
            .push(selection.candidate.value.clone());
    }
    let request = CoverageRequest {
        domain_id: domain.manifest().id.clone(),
        domain_version: domain.manifest().version.clone(),
        domain_digest: domain.digest().into(),
        interpretation_digest: digest_json(&serde_json::to_value(&ready.interpretation)?),
        predicate_slots,
        graph: CoverageGraph {
            focus_node_iri: format!(
                "urn:agent-calculus:session:{}",
                digest_json(&Value::String(session_id.into()))
            ),
            type_iri: intent_spec.type_iri.clone(),
            properties,
        },
    };
    let expected = coverage.validate(&request)?;
    if expected != ready.coverage || !expected.conforms {
        return Err(io::Error::other("effect rejected forged request coverage").into());
    }
    Ok(())
}

fn require_allowed(policy: &PolicyReport) -> ExampleResult<()> {
    if !policy.allowed || policy.checks.values().any(|passed| !passed) {
        return Err(io::Error::other(format!(
            "deterministic policy '{}' did not authorize the effect",
            policy.policy_id
        ))
        .into());
    }
    Ok(())
}

pub fn policy_report(
    policy_id: impl Into<String>,
    checks: impl IntoIterator<Item = (impl Into<String>, bool)>,
    details: Value,
) -> PolicyReport {
    let checks = checks
        .into_iter()
        .map(|(name, passed)| (name.into(), passed))
        .collect::<BTreeMap<_, _>>();
    PolicyReport {
        policy_id: policy_id.into(),
        allowed: checks.values().all(|passed| *passed),
        checks,
        details,
    }
}

pub fn slot_iri<'a>(ready: &'a ReadyAction, slot: &str) -> ExampleResult<&'a str> {
    match ready
        .interpretation
        .slots
        .get(slot)
        .map(|selection| &selection.candidate.value)
    {
        Some(DomainValue::Iri(iri)) => Ok(iri),
        _ => Err(io::Error::other(format!("ready action lacks IRI slot '{slot}'")).into()),
    }
}

pub fn slot_integer(ready: &ReadyAction, slot: &str) -> ExampleResult<i64> {
    match ready
        .interpretation
        .slots
        .get(slot)
        .map(|selection| &selection.candidate.value)
    {
        Some(DomainValue::Integer(value)) => Ok(*value),
        _ => Err(io::Error::other(format!("ready action lacks integer slot '{slot}'")).into()),
    }
}

pub fn exact_iri(ready: &ReadyAction, slot: &str, expected: &str) -> ExampleResult<bool> {
    Ok(slot_iri(ready, slot)? == expected)
}

pub fn class_check(
    label: impl Into<String>,
    individual_iri: impl Into<String>,
    class_iri: impl Into<String>,
) -> NamedSroiqQuery {
    NamedSroiqQuery {
        check: label.into(),
        query: SroiqQuery::ClassMembership {
            individual_iri: individual_iri.into(),
            class_iri: class_iri.into(),
        },
    }
}

pub fn role_check(
    label: impl Into<String>,
    subject_iri: impl Into<String>,
    role_iri: impl Into<String>,
    object_iri: impl Into<String>,
) -> NamedSroiqQuery {
    NamedSroiqQuery {
        check: label.into(),
        query: SroiqQuery::RoleAssertion {
            subject_iri: subject_iri.into(),
            role_iri: role_iri.into(),
            object_iri: object_iri.into(),
        },
    }
}

pub fn distinct(values: impl IntoIterator<Item = String>) -> bool {
    let values = values.into_iter().collect::<Vec<_>>();
    values.iter().collect::<BTreeSet<_>>().len() == values.len()
}

#[cfg(test)]
mod tests {
    use super::*;
    use agent_calculus_domain::HarvestRule;

    #[derive(Debug, Default)]
    struct AmbiguousReplay;

    #[async_trait]
    impl SystemOneProvider for AmbiguousReplay {
        fn id(&self) -> &str {
            "ambiguous-replay"
        }

        fn version(&self) -> &str {
            "1"
        }

        fn configuration_fingerprint(&self) -> String {
            digest_json(&json!({"provider": self.id(), "version": self.version()}))
        }

        async fn decide(&self, request: &DecisionBatch) -> Result<DecisionResponse, BackendError> {
            let mut answers = BTreeMap::new();
            for (name, question) in &request.questions {
                let DecisionQuestion::Choice { criteria, .. } = question else {
                    return Err(BackendError {
                        backend: self.id().into(),
                        message: "expected choice question".into(),
                    });
                };
                let choice = criteria
                    .keys()
                    .find(|candidate| candidate.as_str() != UNKNOWN_CHOICE_ID)
                    .ok_or_else(|| BackendError {
                        backend: self.id().into(),
                        message: "missing authority-bearing candidate".into(),
                    })?
                    .clone();
                answers.insert(
                    name.clone(),
                    DecisionAnswer::Choice {
                        choice: choice.clone(),
                        probabilities: BTreeMap::from([
                            (choice, 0.5),
                            (UNKNOWN_CHOICE_ID.into(), 0.5),
                        ]),
                        confidence: 0.5,
                    },
                );
            }
            Ok(DecisionResponse {
                model: "ambiguous-replay".into(),
                answers,
                input_tokens: 0,
                output_tokens: 0,
                cost_microusd: 0,
            })
        }
    }

    #[tokio::test]
    async fn every_application_replays_without_generative_control() {
        let scenarios = all_scenarios();
        assert_eq!(
            scenarios.len(),
            17,
            "the complete application catalog is required"
        );
        for scenario in scenarios {
            let report = run_scenario(scenario, Arc::new(CandidateOnlyReplay::default()), "replay")
                .await
                .unwrap_or_else(|error| panic!("scenario '{}' failed: {error}", scenario.id()));
            assert_eq!(scenario.turns().len(), 2, "{}", scenario.id());
            assert!(
                report["system_one_calls"]
                    .as_u64()
                    .is_some_and(|calls| calls > 0 && calls <= 2),
                "{}",
                scenario.id()
            );
            assert_eq!(
                report["request_coverage"]["conforms"],
                true,
                "{}",
                scenario.id()
            );
            assert_eq!(
                report["observed_evidence"]["verdict"],
                "proven",
                "{}",
                scenario.id()
            );
            assert!(
                report["formal_checks"]["checks"]
                    .as_array()
                    .is_some_and(|checks| checks.len() >= 3),
                "{} must prove principal, selected capability/resource, and executor relationships",
                scenario.id()
            );
            assert_eq!(
                report["simulated_effect_receipt"]["mode"],
                "simulation",
                "{}",
                scenario.id()
            );
            assert_eq!(
                report["simulated_effect_receipt"][scenario.effect_spec().external_effect_field],
                false,
                "{}",
                scenario.id()
            );
            assert!(
                report["deterministic_policy"]["allowed"]
                    .as_bool()
                    .unwrap_or(false),
                "{}",
                scenario.id()
            );
            assert!(
                report["deterministic_policy"]["checks"]
                    .as_object()
                    .is_some_and(|checks| checks.len() >= 4),
                "{} must expose substantive deterministic checks",
                scenario.id()
            );
        }
    }

    #[test]
    fn example_runtime_has_no_generative_provider_or_dependency() {
        let manifest = include_str!("../Cargo.toml");
        let library = include_str!("lib.rs");
        let binary = include_str!("main.rs");
        let forbidden_provider = ["Generative", "Provider"].concat();
        assert!(!manifest.contains("agent-calculus-llm"));
        assert!(!library.contains(&forbidden_provider));
        assert!(!binary.contains(&forbidden_provider));
    }

    #[tokio::test]
    async fn every_forbidden_probe_stops_before_system_one() {
        for scenario in all_scenarios() {
            let (code, calls) = run_rejection_probe(scenario)
                .await
                .unwrap_or_else(|error| panic!("scenario '{}' failed: {error}", scenario.id()));
            assert_eq!(
                code,
                scenario.rejection_probe().expected_code,
                "{}",
                scenario.id()
            );
            assert_eq!(calls, 0, "{}", scenario.id());
        }
    }

    #[tokio::test]
    async fn tied_system_one_choices_never_reach_ready() {
        for scenario in all_scenarios() {
            assert!(
                prepare_scenario(scenario, Arc::new(AmbiguousReplay))
                    .await
                    .is_err(),
                "{} accepted a candidate/unknown tie",
                scenario.id()
            );
        }
    }

    #[tokio::test]
    async fn every_selected_iri_and_action_capability_has_a_formal_query() {
        for scenario in all_scenarios() {
            let prepared = prepare_scenario(scenario, Arc::new(CandidateOnlyReplay::default()))
                .await
                .unwrap_or_else(|error| panic!("scenario '{}': {error}", scenario.id()));
            let mut queries = scenario
                .formal_queries(&prepared.ready)
                .unwrap_or_else(|error| panic!("queries '{}': {error}", scenario.id()));
            queries.push(class_check(
                "compiled action capability",
                &prepared.ready.action.action_iri,
                &prepared.ready.action.capability_class_iri,
            ));
            let mut queried_resources = BTreeSet::new();
            for named in &queries {
                match &named.query {
                    SroiqQuery::ClassMembership { individual_iri, .. } => {
                        queried_resources.insert(individual_iri.as_str());
                    }
                    SroiqQuery::RoleAssertion {
                        subject_iri,
                        object_iri,
                        ..
                    } => {
                        queried_resources.insert(subject_iri.as_str());
                        queried_resources.insert(object_iri.as_str());
                    }
                    SroiqQuery::Consistency | SroiqQuery::Subsumption { .. } => {}
                }
            }
            for (slot, selection) in &prepared.ready.interpretation.slots {
                if let DomainValue::Iri(iri) = &selection.candidate.value {
                    assert!(
                        queried_resources.contains(iri.as_str()),
                        "{} leaves authority-bearing IRI slot '{}' outside formal queries",
                        scenario.id(),
                        slot
                    );
                }
            }
            assert!(
                queries.iter().any(|named| matches!(
                    &named.query,
                    SroiqQuery::ClassMembership { individual_iri, class_iri }
                        if individual_iri == &prepared.ready.action.action_iri
                            && class_iri == &prepared.ready.action.capability_class_iri
                )),
                "{} omits its compiled action capability",
                scenario.id()
            );
        }
    }

    #[test]
    fn every_application_uses_closed_authority_bearing_harvesters() {
        for scenario in all_scenarios() {
            let manifest: DomainManifest = serde_json::from_str(scenario.assets().manifest_json)
                .unwrap_or_else(|error| panic!("manifest '{}': {error}", scenario.id()));
            assert_eq!(manifest.intents.len(), 1, "{}", scenario.id());
            assert!(
                manifest
                    .harvest_rules
                    .iter()
                    .any(|rule| matches!(rule, HarvestRule::ClosedLookup { .. })),
                "{} must bind at least one identifier to a registry",
                scenario.id()
            );
            assert!(
                manifest
                    .harvest_rules
                    .iter()
                    .any(|rule| matches!(rule, HarvestRule::Reject { .. })),
                "{} must define a recognizable hard rejection",
                scenario.id()
            );
            assert!(
                manifest
                    .harvest_rules
                    .iter()
                    .all(|rule| !matches!(rule, HarvestRule::RegexCapture { .. })),
                "{} must not turn open text into authority-bearing values",
                scenario.id()
            );
        }
    }

    #[tokio::test]
    async fn every_evidence_shape_is_closed_against_an_extra_property() {
        for scenario in all_scenarios() {
            let assets = scenario.assets();
            let valid = prove_evidence(assets.evidence)
                .await
                .unwrap_or_else(|error| panic!("valid evidence '{}': {error}", scenario.id()));
            let focus = valid.certificate["report"]["focus_nodes"][0]
                .as_str()
                .unwrap_or_else(|| panic!("evidence '{}' has no focus node", scenario.id()));
            let focus = if focus.starts_with('<') {
                focus.to_owned()
            } else {
                format!("<{focus}>")
            };
            let poisoned = format!(
                "{}\n{} <urn:agent-calculus:unexpected> true .\n",
                assets.evidence.data_turtle, focus
            );
            let oracle = ShaclOracle::from_turtle(
                assets.evidence.oracle_id,
                assets.evidence.shapes_turtle,
                None,
            )
            .unwrap_or_else(|error| panic!("evidence schema '{}': {error}", scenario.id()));
            match oracle
                .evaluate(&OracleRequest {
                    payload: json!({"query": "validate_turtle", "data": poisoned}),
                    assumptions: vec![],
                })
                .await
            {
                Ok(response) => assert_eq!(
                    response.verdict,
                    FormalVerdict::Refuted,
                    "{}",
                    scenario.id()
                ),
                Err(_) => {
                    // The adapter deliberately fails closed if the upstream
                    // SHACL engine reports a closed-property violation that it
                    // cannot safely attribute to the selected focus node.
                }
            }
        }
    }

    #[tokio::test]
    async fn effect_boundary_rejects_forged_certificates_and_policy() {
        let scenario = all_scenarios()
            .into_iter()
            .find(|scenario| scenario.id() == "invoice-three-way-match")
            .expect("configured application in catalog");
        let prepared = prepare_scenario(scenario, Arc::new(CandidateOnlyReplay::default()))
            .await
            .expect("scenario prepares");
        let assets = scenario.assets();
        let evidence = prove_evidence(assets.evidence)
            .await
            .expect("evidence conforms");
        let formal = prove_sroiq(scenario, &prepared.ready, assets)
            .await
            .expect("formal checks prove");
        let policy = scenario
            .evaluate_policy(&prepared.ready, &evidence)
            .expect("policy evaluates");

        let mut forged_evidence = evidence.clone();
        forged_evidence.certificate["data_sha256"] = json!("forged");
        assert!(
            simulate_effect(
                scenario,
                &prepared.domain,
                prepared.coverage.as_ref(),
                &prepared.session_id,
                &prepared.ready,
                &forged_evidence,
                &formal,
                &policy,
            )
            .await
            .is_err()
        );

        let mut forged_formal = formal.clone();
        forged_formal.checks[0].certificate["ontology_sha256"] = json!("forged");
        assert!(
            simulate_effect(
                scenario,
                &prepared.domain,
                prepared.coverage.as_ref(),
                &prepared.session_id,
                &prepared.ready,
                &evidence,
                &forged_formal,
                &policy,
            )
            .await
            .is_err()
        );

        let mut forged_policy = policy.clone();
        forged_policy.details["forged"] = json!(true);
        assert!(
            simulate_effect(
                scenario,
                &prepared.domain,
                prepared.coverage.as_ref(),
                &prepared.session_id,
                &prepared.ready,
                &evidence,
                &formal,
                &forged_policy,
            )
            .await
            .is_err()
        );

        let mut forged_ready = prepared.ready.clone();
        forged_ready.coverage.certificate["data_digest"] = json!("forged");
        assert!(
            simulate_effect(
                scenario,
                &prepared.domain,
                prepared.coverage.as_ref(),
                &prepared.session_id,
                &forged_ready,
                &evidence,
                &formal,
                &policy,
            )
            .await
            .is_err()
        );

        let mut forged_action = prepared.ready.clone();
        forged_action.action.action_iri = "urn:forged:payment-action".into();
        assert!(
            simulate_effect(
                scenario,
                &prepared.domain,
                prepared.coverage.as_ref(),
                &prepared.session_id,
                &forged_action,
                &evidence,
                &formal,
                &policy,
            )
            .await
            .is_err()
        );

        let mut forged_capability = prepared.ready.clone();
        forged_capability.action.capability_class_iri = "urn:forged:payment-capability".into();
        assert!(
            simulate_effect(
                scenario,
                &prepared.domain,
                prepared.coverage.as_ref(),
                &prepared.session_id,
                &forged_capability,
                &evidence,
                &formal,
                &policy,
            )
            .await
            .is_err()
        );
    }

    #[tokio::test]
    async fn deterministic_policy_reads_the_validated_rdf_claims() {
        let scenario = all_scenarios()
            .into_iter()
            .find(|scenario| scenario.id() == "invoice-three-way-match")
            .expect("invoice scenario in catalog");
        let prepared = prepare_scenario(scenario, Arc::new(CandidateOnlyReplay::default()))
            .await
            .expect("scenario prepares");
        let mut evidence = prove_evidence(scenario.assets().evidence)
            .await
            .expect("evidence conforms");
        let predicate = "urn:agent-calculus:invoice-three-way-match:invoicedQuantity";
        let [EvidenceTerm::Literal { lexical, .. }] = evidence
            .claims
            .get_mut(predicate)
            .expect("invoiced quantity claim")
            .as_mut_slice()
        else {
            panic!("invoiced quantity must be one literal")
        };
        *lexical = "99".into();

        let policy = scenario
            .evaluate_policy(&prepared.ready, &evidence)
            .expect("policy evaluates mutated claims");
        assert!(!policy.allowed);
        assert!(!policy.checks["invoiced and received quantities agree"]);
        assert!(!policy.checks["invoice subtotal recomputes from quantity and unit price"]);
    }

    #[tokio::test]
    async fn evidence_evaluation_time_cannot_cross_an_expiry() {
        let scenario = all_scenarios()
            .into_iter()
            .find(|scenario| scenario.id() == "healthcare-referral-submit")
            .expect("healthcare scenario in catalog");
        let prepared = prepare_scenario(scenario, Arc::new(CandidateOnlyReplay::default()))
            .await
            .expect("scenario prepares");
        let mut evidence = prove_evidence(scenario.assets().evidence)
            .await
            .expect("evidence conforms");
        for (predicate, replacement) in [
            (
                "urn:agent-calculus:healthcare-referral-submit:observedAt",
                "2026-10-25T18:34:20Z",
            ),
            (
                "urn:agent-calculus:healthcare-referral-submit:evaluatedAt",
                "2026-10-25T18:35:20Z",
            ),
        ] {
            let [EvidenceTerm::Literal { lexical, .. }] = evidence
                .claims
                .get_mut(predicate)
                .expect("timestamp claim")
                .as_mut_slice()
            else {
                panic!("timestamp must be one literal")
            };
            *lexical = replacement.into();
        }

        let policy = scenario
            .evaluate_policy(&prepared.ready, &evidence)
            .expect("policy evaluates future claims");
        assert!(!policy.allowed);
        assert!(!policy.checks["prior authorization is unexpired at evaluation"]);
    }

    #[tokio::test]
    async fn cold_chain_shape_rejects_an_inverted_temperature_range() {
        let scenario = all_scenarios()
            .into_iter()
            .find(|scenario| scenario.id() == "cold-chain-release")
            .expect("cold-chain scenario in catalog");
        let assets = scenario.assets();
        let inverted = assets
            .evidence
            .data_turtle
            .replace(
                ":observedMinimumTemperature \"2.8\"",
                ":observedMinimumTemperature \"7.4\"",
            )
            .replace(
                ":observedMaximumTemperature \"7.4\"",
                ":observedMaximumTemperature \"2.8\"",
            );
        let oracle = ShaclOracle::from_turtle(
            assets.evidence.oracle_id,
            assets.evidence.shapes_turtle,
            None,
        )
        .expect("cold-chain evidence schema compiles");
        let response = oracle
            .evaluate(&OracleRequest {
                payload: json!({"query": "validate_turtle", "data": inverted}),
                assumptions: vec![],
            })
            .await
            .expect("invalid range produces a SHACL report");
        assert_eq!(response.verdict, FormalVerdict::Refuted);
    }
}
