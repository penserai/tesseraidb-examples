use crate::{
    DomainAssets, EffectSpec, EvidenceAssets, ExampleResult, NamedSroiqQuery, PolicyReport,
    RejectionProbe, Scenario, ShaclEvidenceBundle, class_check, exact_iri, policy_report,
    role_check, slot_iri,
};
use agent_calculus_domain::ReadyAction;
use serde_json::{Value, json};

const NS: &str = "urn:agent-calculus:accessibility:";
const ACTOR: &str = "urn:agent-calculus:accessibility:sam-lee";
const PARTICIPANT: &str = "urn:agent-calculus:accessibility:participant-jordan-42";
const SESSION: &str = "urn:agent-calculus:accessibility:event-session-evt-204";
const PROFILE: &str = "urn:agent-calculus:accessibility:captions-high-contrast";
const ROOM: &str = "urn:agent-calculus:accessibility:room-a";
const TOOL: &str = "urn:agent-calculus:accessibility:session-configurator";

#[derive(Debug)]
pub struct AccessibilitySession;

pub static SCENARIO: AccessibilitySession = AccessibilitySession;

impl Scenario for AccessibilitySession {
    fn id(&self) -> &'static str {
        "accessibility-session"
    }

    fn title(&self) -> &'static str {
        "Privacy-preserving accessibility session"
    }

    fn assets(&self) -> DomainAssets {
        DomainAssets {
            manifest_json: include_str!("../../domains/accessibility-session/manifest.json"),
            request_shapes_turtle: include_str!(
                "../../domains/accessibility-session/request-shapes.ttl"
            ),
            ontology_ofn: include_str!("../../domains/accessibility-session/ontology.ofn"),
            evidence: EvidenceAssets {
                oracle_id: "accessibility-registration-shacl",
                shapes_turtle: include_str!(
                    "../../domains/accessibility-session/evidence-shapes.ttl"
                ),
                data_turtle: include_str!("../../domains/accessibility-session/evidence.ttl"),
            },
        }
    }

    fn actor(&self) -> &'static str {
        ACTOR
    }

    fn source(&self) -> &'static str {
        "authenticated-event-console"
    }

    fn turns(&self) -> &'static [&'static str] {
        &[
            "Configure Jordan for EVT-204 in room A.",
            "Captions and high contrast for 90 minutes.",
        ]
    }

    fn rejection_probe(&self) -> RejectionProbe {
        RejectionProbe {
            utterance: "Open Jordan's diagnosis and disable the room alarms.",
            expected_code: "medical_or_safety_boundary",
        }
    }

    fn formal_queries(&self, ready: &ReadyAction) -> ExampleResult<Vec<NamedSroiqQuery>> {
        let participant = slot_iri(ready, "participant")?;
        let session = slot_iri(ready, "session")?;
        let profile = slot_iri(ready, "accommodation")?;
        let room = slot_iri(ready, "room")?;
        let duration = slot_iri(ready, "duration")?;
        Ok(vec![
            class_check(
                "coordinator eligibility",
                ready.principal.actor.clone(),
                format!("{NS}EligibleAccessibilityCoordinator"),
            ),
            class_check(
                "registered participant",
                participant,
                format!("{NS}RegisteredParticipant"),
            ),
            class_check(
                "supported accommodation profile",
                profile,
                format!("{NS}SupportedAccommodationProfile"),
            ),
            class_check(
                "registered event session",
                session,
                format!("{NS}EventSession"),
            ),
            class_check(
                "bounded session duration",
                duration,
                format!("{NS}BoundedSessionDuration"),
            ),
            class_check(
                "approved session configurator",
                TOOL,
                format!("{NS}ApprovedSessionConfigurator"),
            ),
            role_check(
                "participant registration",
                participant,
                format!("{NS}registeredFor"),
                session,
            ),
            role_check(
                "room supports profile",
                room,
                format!("{NS}supportsProfile"),
                profile,
            ),
            role_check(
                "session has selected duration",
                session,
                format!("{NS}hasDuration"),
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
        let requested_minutes = evidence.number(&predicate("durationMinutes"))?;
        let observed_at = evidence.number(&predicate("observedAtUnix"))?;
        let evaluated_at = evidence.number(&predicate("evaluatedAtUnix"))?;
        let registration_age_seconds = evaluated_at - observed_at;
        Ok(policy_report(
            "accessibility-session-policy/2026-10",
            [
                ("authenticated coordinator", ready.principal.actor == ACTOR),
                (
                    "registered participant",
                    exact_iri(ready, "participant", PARTICIPANT)?
                        && evidence.iri(&predicate("participant"))? == PARTICIPANT,
                ),
                (
                    "registered session",
                    exact_iri(ready, "session", SESSION)?
                        && evidence.iri(&predicate("session"))? == SESSION
                        && evidence.iri(&predicate("sessionStatus"))? == format!("{NS}scheduled"),
                ),
                (
                    "supported room",
                    exact_iri(ready, "room", ROOM)? && evidence.iri(&predicate("room"))? == ROOM,
                ),
                (
                    "supported presentation profile",
                    exact_iri(ready, "accommodation", PROFILE)?
                        && evidence.iri(&predicate("requestedProfile"))? == PROFILE
                        && evidence.iri(&predicate("consentStatus"))?
                            == format!("{NS}current-consent"),
                ),
                (
                    "bounded duration",
                    exact_iri(
                        ready,
                        "duration",
                        "urn:agent-calculus:accessibility:duration-90m",
                    )? && requested_minutes <= 120.0,
                ),
                (
                    "registration snapshot fresh",
                    (0.0..=300.0).contains(&registration_age_seconds),
                ),
                (
                    "diagnosis not requested or represented",
                    !evidence.boolean(&predicate("requiresDiagnosis"))?,
                ),
                (
                    "life-safety configuration excluded",
                    !evidence.boolean(&predicate("changesLifeSafetySystem"))?,
                ),
                (
                    "profile automatically reverts",
                    evidence.boolean(&predicate("automaticRevert"))?,
                ),
            ],
            json!({
                "requested_minutes": requested_minutes,
                "maximum_minutes": 120,
                "registration_age_seconds": registration_age_seconds,
                "requires_diagnosis": evidence.boolean(&predicate("requiresDiagnosis"))?,
                "changes_life_safety_system": evidence.boolean(&predicate("changesLifeSafetySystem"))?,
                "automatic_revert": evidence.boolean(&predicate("automaticRevert"))?,
                "evidence_data_digest": evidence.data_digest
            }),
        ))
    }

    fn effect_spec(&self) -> EffectSpec {
        EffectSpec {
            kind: "configure-accessible-session",
            outcome: "presentation-profile-reserved",
            external_effect_field: "venue_configuration_changed",
        }
    }

    fn effect_parameters(&self, ready: &ReadyAction) -> ExampleResult<Value> {
        Ok(json!({
            "participant": slot_iri(ready, "participant")?,
            "session": slot_iri(ready, "session")?,
            "room": slot_iri(ready, "room")?,
            "profile": slot_iri(ready, "accommodation")?,
            "duration": slot_iri(ready, "duration")?,
            "presentation_changes": ["live-captions", "high-contrast-display"],
            "diagnosis_collected": false,
            "life_safety_changes": []
        }))
    }
}
