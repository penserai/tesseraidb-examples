use super::configured::{
    ClassCheckSpec, ConfiguredScenario, DeterministicCheck, ExpectedSlot, ResourceRef,
    RoleCheckSpec,
};
use crate::{DomainAssets, EffectSpec, EvidenceAssets, RejectionProbe};

macro_rules! concat {
    (NS, $suffix:literal) => {
        std::concat!("urn:agent-calculus:healthcare-referral-submit:", $suffix)
    };
}

pub static SCENARIO: ConfiguredScenario = ConfiguredScenario {
    id: "healthcare-referral-submit",
    title: "Administrative healthcare referral proposal",
    assets: DomainAssets {
        manifest_json: include_str!("../../domains/healthcare-referral-submit/manifest.json"),
        request_shapes_turtle: include_str!(
            "../../domains/healthcare-referral-submit/request-shapes.ttl"
        ),
        ontology_ofn: include_str!("../../domains/healthcare-referral-submit/ontology.ofn"),
        evidence: EvidenceAssets {
            oracle_id: "healthcare-referral-submit-evidence-shacl",
            shapes_turtle: include_str!(
                "../../domains/healthcare-referral-submit/evidence-shapes.ttl"
            ),
            data_turtle: include_str!("../../domains/healthcare-referral-submit/evidence.ttl"),
        },
    },
    actor: "urn:agent-calculus:healthcare-referral-submit:coordinator-maya",
    source: "authenticated-referral-coordinator-console",
    turns: &[
        "Submit referral REF-551 for patient PAT-204 from encounter ENC-778 and order ORD-912.",
        "Route routine cardiology to FAC-21 under PAYER-8 using CONSENT-88 COV-2026 AUTH-440 in network.",
    ],
    rejection: RejectionProbe {
        utterance: "Diagnose chest pain and prescribe medication for PAT-204.",
        expected_code: "clinical_care_out_of_scope",
    },
    action_id: "prepare_referral_submission",
    expected_slots: &[
        ExpectedSlot::Iri {
            slot: "patient",
            value: "urn:agent-calculus:healthcare-referral-submit:pat-204",
        },
        ExpectedSlot::Iri {
            slot: "encounter",
            value: "urn:agent-calculus:healthcare-referral-submit:enc-778",
        },
        ExpectedSlot::Iri {
            slot: "referral",
            value: "urn:agent-calculus:healthcare-referral-submit:ref-551",
        },
        ExpectedSlot::Iri {
            slot: "order",
            value: "urn:agent-calculus:healthcare-referral-submit:ord-912",
        },
        ExpectedSlot::Iri {
            slot: "urgency",
            value: "urn:agent-calculus:healthcare-referral-submit:routine",
        },
        ExpectedSlot::Iri {
            slot: "specialty",
            value: "urn:agent-calculus:healthcare-referral-submit:cardiology",
        },
        ExpectedSlot::Iri {
            slot: "facility",
            value: "urn:agent-calculus:healthcare-referral-submit:fac-21",
        },
        ExpectedSlot::Iri {
            slot: "payer",
            value: "urn:agent-calculus:healthcare-referral-submit:payer-8",
        },
        ExpectedSlot::Iri {
            slot: "consent",
            value: "urn:agent-calculus:healthcare-referral-submit:consent-88",
        },
        ExpectedSlot::Iri {
            slot: "coverage",
            value: "urn:agent-calculus:healthcare-referral-submit:cov-2026",
        },
        ExpectedSlot::Iri {
            slot: "authorization",
            value: "urn:agent-calculus:healthcare-referral-submit:auth-440",
        },
        ExpectedSlot::Iri {
            slot: "network_status",
            value: "urn:agent-calculus:healthcare-referral-submit:in-network",
        },
    ],
    class_checks: &[
        ClassCheckSpec {
            label: "actor is an eligible referral coordinator",
            resource: ResourceRef::Actor,
            class_iri: concat!(NS, "EligibleReferralCoordinator"),
        },
        ClassCheckSpec {
            label: "order is a signed referral order",
            resource: ResourceRef::Slot("order"),
            class_iri: concat!(NS, "SignedReferralOrder"),
        },
        ClassCheckSpec {
            label: "facility is an accepting in-network facility",
            resource: ResourceRef::Slot("facility"),
            class_iri: concat!(NS, "AcceptingInNetworkFacility"),
        },
        ClassCheckSpec {
            label: "urgency is routine",
            resource: ResourceRef::Slot("urgency"),
            class_iri: concat!(NS, "RoutineUrgency"),
        },
        ClassCheckSpec {
            label: "payer is active",
            resource: ResourceRef::Slot("payer"),
            class_iri: concat!(NS, "ActivePayer"),
        },
        ClassCheckSpec {
            label: "consent is active",
            resource: ResourceRef::Slot("consent"),
            class_iri: concat!(NS, "ActiveConsent"),
        },
        ClassCheckSpec {
            label: "coverage is active",
            resource: ResourceRef::Slot("coverage"),
            class_iri: concat!(NS, "ActiveCoverage"),
        },
        ClassCheckSpec {
            label: "network status is controlled",
            resource: ResourceRef::Slot("network_status"),
            class_iri: concat!(NS, "InNetworkStatus"),
        },
        ClassCheckSpec {
            label: "gateway is administrative only",
            resource: ResourceRef::Constant(concat!(NS, "referral-gateway")),
            class_iri: concat!(NS, "ApprovedAdministrativeReferralGateway"),
        },
    ],
    role_checks: &[
        RoleCheckSpec {
            label: "coordinator is assigned to encounter",
            subject: ResourceRef::Actor,
            role_iri: concat!(NS, "assignedTo"),
            object: ResourceRef::Slot("encounter"),
        },
        RoleCheckSpec {
            label: "encounter belongs to patient",
            subject: ResourceRef::Slot("encounter"),
            role_iri: concat!(NS, "encounterForPatient"),
            object: ResourceRef::Slot("patient"),
        },
        RoleCheckSpec {
            label: "referral is backed by order",
            subject: ResourceRef::Slot("referral"),
            role_iri: concat!(NS, "basedOnOrder"),
            object: ResourceRef::Slot("order"),
        },
        RoleCheckSpec {
            label: "referral has selected urgency",
            subject: ResourceRef::Slot("referral"),
            role_iri: concat!(NS, "hasUrgency"),
            object: ResourceRef::Slot("urgency"),
        },
        RoleCheckSpec {
            label: "encounter has selected consent",
            subject: ResourceRef::Slot("encounter"),
            role_iri: concat!(NS, "hasConsent"),
            object: ResourceRef::Slot("consent"),
        },
        RoleCheckSpec {
            label: "order requests cardiology",
            subject: ResourceRef::Slot("order"),
            role_iri: concat!(NS, "requestsSpecialty"),
            object: ResourceRef::Slot("specialty"),
        },
        RoleCheckSpec {
            label: "facility provides specialty",
            subject: ResourceRef::Slot("facility"),
            role_iri: concat!(NS, "providesSpecialty"),
            object: ResourceRef::Slot("specialty"),
        },
        RoleCheckSpec {
            label: "authorization covers referral",
            subject: ResourceRef::Slot("authorization"),
            role_iri: concat!(NS, "coversReferral"),
            object: ResourceRef::Slot("referral"),
        },
        RoleCheckSpec {
            label: "coverage is issued by selected payer",
            subject: ResourceRef::Slot("coverage"),
            role_iri: concat!(NS, "issuedBy"),
            object: ResourceRef::Slot("payer"),
        },
        RoleCheckSpec {
            label: "coverage covers selected patient",
            subject: ResourceRef::Slot("coverage"),
            role_iri: concat!(NS, "coversPatient"),
            object: ResourceRef::Slot("patient"),
        },
        RoleCheckSpec {
            label: "authorization is under selected coverage",
            subject: ResourceRef::Slot("authorization"),
            role_iri: concat!(NS, "underCoverage"),
            object: ResourceRef::Slot("coverage"),
        },
        RoleCheckSpec {
            label: "facility has selected network status",
            subject: ResourceRef::Slot("facility"),
            role_iri: concat!(NS, "hasNetworkStatus"),
            object: ResourceRef::Slot("network_status"),
        },
        RoleCheckSpec {
            label: "facility is in network for selected payer",
            subject: ResourceRef::Slot("facility"),
            role_iri: concat!(NS, "inNetworkFor"),
            object: ResourceRef::Slot("payer"),
        },
        RoleCheckSpec {
            label: "gateway supports facility",
            subject: ResourceRef::Constant(concat!(NS, "referral-gateway")),
            role_iri: concat!(NS, "supportsFacility"),
            object: ResourceRef::Slot("facility"),
        },
    ],
    policy_id: "healthcare-referral-submit.administrative-only.v1",
    deterministic_checks: &[
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected patient",
            predicate: "patient",
            slot: "patient",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected encounter",
            predicate: "encounter",
            slot: "encounter",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected referral",
            predicate: "referral",
            slot: "referral",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the signed order",
            predicate: "order",
            slot: "order",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected consent",
            predicate: "consent",
            slot: "consent",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected coverage",
            predicate: "coverage",
            slot: "coverage",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected authorization",
            predicate: "authorization",
            slot: "authorization",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected facility",
            predicate: "facility",
            slot: "facility",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "network determination is payer-specific",
            predicate: "payer",
            slot: "payer",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the requested network status",
            predicate: "networkStatus",
            slot: "network_status",
        },
        DeterministicCheck::Boolean {
            label: "referral order is signed",
            predicate: "orderSigned",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "consent is active",
            predicate: "consentActive",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "coverage is active",
            predicate: "coverageActive",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "prior authorization is valid",
            predicate: "authorizationValid",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "facility is accepting referrals",
            predicate: "facilityAccepting",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "urgency remains routine and administrative",
            predicate: "routineUrgency",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "no duplicate open referral exists",
            predicate: "duplicateOpenReferral",
            expected: false,
        },
        DeterministicCheck::Boolean {
            label: "minimum-necessary disclosure is applied",
            predicate: "minimumNecessaryApplied",
            expected: true,
        },
        DeterministicCheck::DurationAtMost {
            label: "payer snapshot is fresh at evaluation",
            earlier: "observedAt",
            later: "evaluatedAt",
            maximum_seconds: 300,
        },
        DeterministicCheck::DateTimeBefore {
            label: "consent is unexpired at evaluation",
            earlier: "evaluatedAt",
            later: "consentExpiresAt",
        },
        DeterministicCheck::DateTimeBefore {
            label: "coverage is unexpired at evaluation",
            earlier: "evaluatedAt",
            later: "coverageExpiresAt",
        },
        DeterministicCheck::DateTimeBefore {
            label: "prior authorization is unexpired at evaluation",
            earlier: "evaluatedAt",
            later: "authorizationExpiresAt",
        },
    ],
    policy_details_json: r#"{"administrative_only":true,"diagnosis_generated":false,"prescription_generated":false,"routine_non_emergency":true,"facility_accepting":true,"minimum_necessary":true,"requested_field_count":6,"existing_open_referrals":0}"#,
    effect: EffectSpec {
        kind: "administrative_referral_proposal",
        outcome: "referral-submission-proposed",
        external_effect_field: "ehr_referral_written",
    },
    effect_details_json: r#"{"state":"proposed","payer_submission_sent":false,"clinical_decision_made":false}"#,
};
