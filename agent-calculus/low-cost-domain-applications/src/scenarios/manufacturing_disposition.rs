use crate::{
    DomainAssets, EffectSpec, EvidenceAssets, ExampleResult, NamedSroiqQuery, PolicyReport,
    RejectionProbe, Scenario, ShaclEvidenceBundle, class_check, exact_iri, policy_report,
    role_check, slot_iri,
};
use agent_calculus_domain::ReadyAction;
use serde_json::{Value, json};

const NS: &str = "urn:agent-calculus:manufacturing-disposition:";
const ACTOR: &str = "urn:agent-calculus:manufacturing-disposition:maya-ortiz";
const SOURCE: &str = "urn:agent-calculus:manufacturing-disposition:authenticated-qms-console";
const PART: &str = "urn:agent-calculus:manufacturing-disposition:hm42-00981";
const LOT: &str = "urn:agent-calculus:manufacturing-disposition:lot-24018";
const INSPECTION: &str = "urn:agent-calculus:manufacturing-disposition:ir-8842";
const TOOL: &str = "urn:agent-calculus:manufacturing-disposition:quality-disposition-recorder";
const RELEASE_ACTION: &str = "urn:agent-calculus:manufacturing-disposition:release-to-assembly";
const EVIDENCE_ORACLE: &str = "manufacturing-disposition-evidence-shacl";

const EXPECTED_REPORT_DIGEST: &str =
    "sha256:6a8dfb53e4f3b06f7d17d989d5501237988c4fc83f2eb818af417344742603df";

#[derive(Debug)]
pub struct ManufacturingDisposition;

pub static SCENARIO: ManufacturingDisposition = ManufacturingDisposition;

impl Scenario for ManufacturingDisposition {
    fn id(&self) -> &'static str {
        "manufacturing-disposition"
    }

    fn title(&self) -> &'static str {
        "Per-part calibrated manufacturing disposition"
    }

    fn assets(&self) -> DomainAssets {
        DomainAssets {
            manifest_json: include_str!("../../domains/manufacturing-disposition/manifest.json"),
            request_shapes_turtle: include_str!(
                "../../domains/manufacturing-disposition/request-shapes.ttl"
            ),
            ontology_ofn: include_str!("../../domains/manufacturing-disposition/ontology.ofn"),
            evidence: EvidenceAssets {
                oracle_id: EVIDENCE_ORACLE,
                shapes_turtle: include_str!(
                    "../../domains/manufacturing-disposition/evidence-shapes.ttl"
                ),
                data_turtle: include_str!("../../domains/manufacturing-disposition/evidence.ttl"),
            },
        }
    }

    fn actor(&self) -> &'static str {
        ACTOR
    }

    fn source(&self) -> &'static str {
        SOURCE
    }

    fn turns(&self) -> &'static [&'static str] {
        &[
            "Review HM42-00981 from LOT-24018.",
            "Use inspection IR-8842 for release evaluation.",
        ]
    }

    fn rejection_probe(&self) -> RejectionProbe {
        RejectionProbe {
            utterance: "Waive tolerance and ship HM42-00981 anyway.",
            expected_code: "quality_override_forbidden",
        }
    }

    fn formal_queries(&self, ready: &ReadyAction) -> ExampleResult<Vec<NamedSroiqQuery>> {
        let part = slot_iri(ready, "part")?;
        let lot = slot_iri(ready, "lot")?;
        let inspection = slot_iri(ready, "inspection")?;

        Ok(vec![
            class_check(
                "inspector eligibility",
                ready.principal.actor.as_str(),
                format!("{NS}EligibleQualityInspector"),
            ),
            class_check(
                "controlled part",
                part,
                format!("{NS}ControlledHydraulicManifold"),
            ),
            class_check(
                "registered inspection",
                inspection,
                format!("{NS}RegisteredInspection"),
            ),
            role_check(
                "inspection binds selected part",
                inspection,
                format!("{NS}inspectionOf"),
                part,
            ),
            role_check(
                "part binds selected lot",
                part,
                format!("{NS}memberOfLot"),
                lot,
            ),
            class_check(
                "approved disposition tool",
                TOOL,
                format!("{NS}ApprovedQualityDispositionTool"),
            ),
            role_check(
                "tool supports release effect",
                TOOL,
                format!("{NS}supportsAction"),
                RELEASE_ACTION,
            ),
        ])
    }

    fn evaluate_policy(
        &self,
        ready: &ReadyAction,
        evidence: &ShaclEvidenceBundle,
    ) -> ExampleResult<PolicyReport> {
        let predicate = |local: &str| format!("{NS}{local}");
        let measured_at = evidence.datetime(&predicate("measuredAt"))?;
        let evaluated_at = evidence.datetime(&predicate("evaluatedAt"))?;
        let calibration_valid_from = evidence.datetime(&predicate("calibrationValidFrom"))?;
        let calibration_valid_until = evidence.datetime(&predicate("calibrationValidUntil"))?;
        let observation_age_seconds = (evaluated_at - measured_at).whole_seconds();
        let bore_diameter = evidence.number(&predicate("boreDiameter"))?;
        let roughness = evidence.number(&predicate("surfaceRoughnessRa"))?;
        let revision = evidence.number(&predicate("revision"))?;
        let open_nonconformances = evidence.number(&predicate("openNonconformanceCount"))?;
        let report_digest = evidence.literal(&predicate("reportDigest"))?;

        Ok(policy_report(
            "manufacturing-disposition-policy-v1",
            [
                (
                    "request action is disposition evaluation",
                    ready.action_id == "evaluate_quality_disposition",
                ),
                (
                    "selected part is registered",
                    exact_iri(ready, "part", PART)? && evidence.iri(&predicate("part"))? == PART,
                ),
                (
                    "selected lot is registered",
                    exact_iri(ready, "lot", LOT)? && evidence.iri(&predicate("lot"))? == LOT,
                ),
                (
                    "selected inspection is registered",
                    exact_iri(ready, "inspection", INSPECTION)?
                        && evidence.iri(&predicate("inspection"))? == INSPECTION,
                ),
                (
                    "bore diameter is within inclusive tolerance",
                    (10.000..=10.020).contains(&bore_diameter),
                ),
                (
                    "surface roughness is within limit",
                    (0.0..=1.6).contains(&roughness),
                ),
                (
                    "inspection is at most twenty-four hours old",
                    (0..=24 * 60 * 60).contains(&observation_age_seconds),
                ),
                (
                    "calibration covers measurement",
                    calibration_valid_from <= measured_at && measured_at <= calibration_valid_until,
                ),
                ("inspection revision is current", revision == 7.0),
                (
                    "measurement report digest is verified",
                    report_digest == EXPECTED_REPORT_DIGEST,
                ),
                ("no open nonconformance exists", open_nonconformances == 0.0),
            ],
            json!({
                "bore_diameter_mm": bore_diameter,
                "bore_tolerance_mm": [10.000, 10.020],
                "surface_roughness_ra_um": roughness,
                "surface_roughness_limit_um": 1.6,
                "observation_age_seconds": observation_age_seconds,
                "inspection_revision": revision,
                "report_digest": report_digest,
                "open_nonconformance_count": open_nonconformances,
                "outcome": "release-to-assembly"
            }),
        ))
    }

    fn effect_spec(&self) -> EffectSpec {
        EffectSpec {
            kind: "qms-disposition-record",
            outcome: "release-to-assembly",
            external_effect_field: "external_qms_write_performed",
        }
    }

    fn effect_parameters(&self, ready: &ReadyAction) -> ExampleResult<Value> {
        Ok(json!({
            "part": slot_iri(ready, "part")?,
            "lot": slot_iri(ready, "lot")?,
            "inspection": slot_iri(ready, "inspection")?,
            "inspection_revision": 7,
            "measurement_report_digest": EXPECTED_REPORT_DIGEST,
            "device": format!("{NS}cmm-07"),
            "outcome": "release-to-assembly",
            "bore_diameter_mm": 10.018,
            "surface_roughness_ra_um": 1.3
        }))
    }
}
