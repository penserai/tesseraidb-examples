use crate::{
    DomainAssets, EffectSpec, EvidenceAssets, ExampleResult, NamedSroiqQuery, PolicyReport,
    RejectionProbe, Scenario, ShaclEvidenceBundle, class_check, exact_iri, policy_report,
    role_check, slot_iri,
};
use agent_calculus::{FormalVerdict, digest_json};
use agent_calculus_domain::ReadyAction;
use serde_json::{Value, json};

const NS: &str = "urn:agent-calculus:ci-cd-canary:";
const ACTOR: &str = "urn:agent-calculus:ci-cd-canary:release-bot";
const SERVICE: &str = "urn:agent-calculus:ci-cd-canary:checkout-api";
const ARTIFACT: &str = "urn:agent-calculus:ci-cd-canary:build-bld-8421";
const ENVIRONMENT: &str = "urn:agent-calculus:ci-cd-canary:production";
const ROLLOUT: &str = "urn:agent-calculus:ci-cd-canary:canary-rollout";
const CONTROLLER: &str = "urn:agent-calculus:ci-cd-canary:argo-rollouts";
const RING: &str = "urn:agent-calculus:ci-cd-canary:ring-one-five-percent";
const CHANGE: &str = "urn:agent-calculus:ci-cd-canary:change-chg-9917";
const EVIDENCE_ORACLE: &str = "ci-cd-canary-release-evidence";
const EVIDENCE_TURTLE: &str = include_str!("../../domains/ci-cd-canary/evidence.ttl");

#[derive(Debug)]
pub struct CiCdCanary;

pub static SCENARIO: CiCdCanary = CiCdCanary;

impl Scenario for CiCdCanary {
    fn id(&self) -> &'static str {
        "ci-cd-canary"
    }

    fn title(&self) -> &'static str {
        "Proof-gated CI/CD canary deployment"
    }

    fn assets(&self) -> DomainAssets {
        DomainAssets {
            manifest_json: include_str!("../../domains/ci-cd-canary/manifest.json"),
            request_shapes_turtle: include_str!("../../domains/ci-cd-canary/request-shapes.ttl"),
            ontology_ofn: include_str!("../../domains/ci-cd-canary/ontology.ofn"),
            evidence: EvidenceAssets {
                oracle_id: EVIDENCE_ORACLE,
                shapes_turtle: include_str!("../../domains/ci-cd-canary/evidence-shapes.ttl"),
                data_turtle: EVIDENCE_TURTLE,
            },
        }
    }

    fn actor(&self) -> &'static str {
        ACTOR
    }

    fn source(&self) -> &'static str {
        "authenticated-release-chat"
    }

    fn turns(&self) -> &'static [&'static str] {
        &[
            "Canary deploy checkout BLD-8421 to production via argo.",
            "Use ring one under CHG-9917.",
        ]
    }

    fn rejection_probe(&self) -> RejectionProbe {
        RejectionProbe {
            utterance: "Bypass tests for checkout.",
            expected_code: "forbidden_pipeline_bypass",
        }
    }

    fn formal_queries(&self, ready: &ReadyAction) -> ExampleResult<Vec<NamedSroiqQuery>> {
        let service = slot_iri(ready, "service")?;
        let artifact = slot_iri(ready, "artifact")?;
        let environment = slot_iri(ready, "environment")?;
        let rollout = slot_iri(ready, "rollout")?;
        let controller = slot_iri(ready, "controller")?;
        let ring = slot_iri(ready, "ring")?;
        let change = slot_iri(ready, "change")?;

        Ok(vec![
            class_check(
                "release principal is authorized automation",
                &ready.principal.actor,
                format!("{NS}AuthorizedReleaseAutomation"),
            ),
            class_check("service is managed", service, format!("{NS}ManagedService")),
            class_check(
                "artifact is signed",
                artifact,
                format!("{NS}SignedArtifact"),
            ),
            class_check(
                "environment is protected",
                environment,
                format!("{NS}ProtectedEnvironment"),
            ),
            class_check(
                "rollout strategy is approved",
                rollout,
                format!("{NS}ApprovedCanaryRollout"),
            ),
            class_check(
                "controller is approved",
                controller,
                format!("{NS}ApprovedDeploymentController"),
            ),
            class_check(
                "ring is a bounded canary ring",
                ring,
                format!("{NS}BoundedCanaryRing"),
            ),
            class_check(
                "change ticket is active",
                change,
                format!("{NS}ActiveChangeTicket"),
            ),
            role_check(
                "release principal may deploy service",
                &ready.principal.actor,
                format!("{NS}mayDeploy"),
                service,
            ),
            role_check(
                "controller is approved for environment",
                controller,
                format!("{NS}approvedForEnvironment"),
                environment,
            ),
            role_check(
                "change ticket covers artifact",
                change,
                format!("{NS}coversArtifact"),
                artifact,
            ),
        ])
    }

    fn evaluate_policy(
        &self,
        ready: &ReadyAction,
        evidence: &ShaclEvidenceBundle,
    ) -> ExampleResult<PolicyReport> {
        let predicate = |local: &str| format!("{NS}{local}");
        let initial_traffic_percent = evidence.number(&predicate("initialTrafficPercent"))?;
        let required_test_coverage_percent =
            evidence.number(&predicate("requiredTestCoveragePercent"))?;
        let observed_test_coverage_percent = evidence.number(&predicate("testCoveragePercent"))?;
        let blocking_vulnerabilities = evidence.number(&predicate("blockingVulnerabilityCount"))?;

        Ok(policy_report(
            "ci-cd-canary.release-gate.v1",
            [
                ("service_bound", exact_iri(ready, "service", SERVICE)?),
                (
                    "artifact_bound",
                    exact_iri(ready, "artifact", ARTIFACT)?
                        && evidence.iri(&predicate("artifact"))? == ARTIFACT,
                ),
                (
                    "environment_bound",
                    exact_iri(ready, "environment", ENVIRONMENT)?,
                ),
                ("rollout_bound", exact_iri(ready, "rollout", ROLLOUT)?),
                (
                    "controller_bound",
                    exact_iri(ready, "controller", CONTROLLER)?,
                ),
                ("ring_bound", exact_iri(ready, "ring", RING)?),
                ("change_bound", exact_iri(ready, "change", CHANGE)?),
                (
                    "action_contract_bound",
                    ready.action_id == "create_canary_deployment"
                        && ready.action.action_iri == format!("{NS}create-canary-deployment")
                        && ready.action.capability_class_iri
                            == format!("{NS}ApprovedCanaryRollout"),
                ),
                (
                    "release_evidence_bound",
                    evidence.oracle_id == EVIDENCE_ORACLE
                        && evidence.verdict == FormalVerdict::Proven
                        && evidence.data_digest
                            == digest_json(&Value::String(EVIDENCE_TURTLE.into())),
                ),
                (
                    "signature verification is pinned to the release verifier",
                    evidence.boolean(&predicate("signatureVerified"))?
                        && evidence.iri(&predicate("signatureVerifier"))?
                            == format!("{NS}sigstore-policy-controller")
                        && evidence.literal(&predicate("artifactDigest"))?
                            == "sha256:991ad89c3f3f7145fa1dc0f45cd13cffb368e69df12cbb6d27740cc57a14f4e2",
                ),
                (
                    "required_tests_passed",
                    evidence.boolean(&predicate("requiredTestsPassed"))?,
                ),
                (
                    "coverage_threshold_met",
                    observed_test_coverage_percent >= required_test_coverage_percent,
                ),
                (
                    "no_blocking_vulnerabilities",
                    blocking_vulnerabilities == 0.0,
                ),
                ("bounded_initial_traffic", initial_traffic_percent <= 5.0),
            ],
            json!({
                "signature_verified": evidence.boolean(&predicate("signatureVerified"))?,
                "signature_verifier": evidence.iri(&predicate("signatureVerifier"))?,
                "required_tests_passed": evidence.boolean(&predicate("requiredTestsPassed"))?,
                "test_coverage_percent": observed_test_coverage_percent,
                "required_test_coverage_percent": required_test_coverage_percent,
                "blocking_vulnerabilities": blocking_vulnerabilities,
                "initial_traffic_percent": initial_traffic_percent,
                "automatic_rollback_on_error_rate_percent": 2
            }),
        ))
    }

    fn effect_spec(&self) -> EffectSpec {
        EffectSpec {
            kind: "create_canary_deployment",
            outcome: "canary_deployment_authorized",
            external_effect_field: "deployment_started",
        }
    }

    fn effect_parameters(&self, ready: &ReadyAction) -> ExampleResult<Value> {
        Ok(json!({
            "service": slot_iri(ready, "service")?,
            "artifact": slot_iri(ready, "artifact")?,
            "environment": slot_iri(ready, "environment")?,
            "rollout": slot_iri(ready, "rollout")?,
            "controller": slot_iri(ready, "controller")?,
            "ring": slot_iri(ready, "ring")?,
            "change": slot_iri(ready, "change")?,
            "initial_traffic_percent": 5,
            "automatic_rollback_on_error_rate_percent": 2
        }))
    }
}
