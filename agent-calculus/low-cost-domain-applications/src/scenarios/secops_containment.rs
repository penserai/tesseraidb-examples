use super::configured::{
    ClassCheckSpec, ConfiguredScenario, DeterministicCheck, ExpectedSlot, ResourceRef,
    RoleCheckSpec,
};
use crate::{DomainAssets, EffectSpec, EvidenceAssets, RejectionProbe};

macro_rules! concat {
    (NS, $suffix:literal) => {
        std::concat!("urn:agent-calculus:secops-containment:", $suffix)
    };
}

pub static SCENARIO: ConfiguredScenario = ConfiguredScenario {
    id: "secops-containment",
    title: "Evidence-gated endpoint containment",
    assets: DomainAssets {
        manifest_json: include_str!("../../domains/secops-containment/manifest.json"),
        request_shapes_turtle: include_str!("../../domains/secops-containment/request-shapes.ttl"),
        ontology_ofn: include_str!("../../domains/secops-containment/ontology.ofn"),
        evidence: EvidenceAssets {
            oracle_id: "secops-containment-evidence-shacl",
            shapes_turtle: include_str!("../../domains/secops-containment/evidence-shapes.ttl"),
            data_turtle: include_str!("../../domains/secops-containment/evidence.ttl"),
        },
    },
    actor: "urn:agent-calculus:secops-containment:secops-analyst-42",
    source: "authenticated-soc-console",
    turns: &[
        "Contain host FIN-LT-204 for incident INC-7741 and alert ALT-9007.",
        "Use EDR network isolation for 30 minutes in finance-user at Tier-2.",
    ],
    rejection: RejectionProbe {
        utterance: "Wipe FIN-LT-204 and block the whole network.",
        expected_code: "destructive_containment_forbidden",
    },
    action_id: "propose_endpoint_isolation",
    expected_slots: &[
        ExpectedSlot::Iri {
            slot: "incident",
            value: "urn:agent-calculus:secops-containment:inc-7741",
        },
        ExpectedSlot::Iri {
            slot: "alert",
            value: "urn:agent-calculus:secops-containment:alt-9007",
        },
        ExpectedSlot::Iri {
            slot: "host",
            value: "urn:agent-calculus:secops-containment:fin-lt-204",
        },
        ExpectedSlot::Iri {
            slot: "segment",
            value: "urn:agent-calculus:secops-containment:finance-user",
        },
        ExpectedSlot::Iri {
            slot: "containment",
            value: "urn:agent-calculus:secops-containment:edr-network-isolation",
        },
        ExpectedSlot::Iri {
            slot: "approval_tier",
            value: "urn:agent-calculus:secops-containment:tier-2",
        },
        ExpectedSlot::Integer {
            slot: "duration_minutes",
            value: 30,
        },
    ],
    class_checks: &[
        ClassCheckSpec {
            label: "actor is a Tier-2 containment analyst",
            resource: ResourceRef::Actor,
            class_iri: concat!(NS, "TierTwoContainmentAnalyst"),
        },
        ClassCheckSpec {
            label: "host is a managed endpoint",
            resource: ResourceRef::Slot("host"),
            class_iri: concat!(NS, "ManagedEndpoint"),
        },
        ClassCheckSpec {
            label: "containment is reversible",
            resource: ResourceRef::Slot("containment"),
            class_iri: concat!(NS, "ReversibleNetworkIsolation"),
        },
        ClassCheckSpec {
            label: "approval tier is registered",
            resource: ResourceRef::Slot("approval_tier"),
            class_iri: concat!(NS, "ContainmentApprovalTier"),
        },
        ClassCheckSpec {
            label: "executor is approved",
            resource: ResourceRef::Constant(concat!(NS, "containment-proposal-planner")),
            class_iri: concat!(NS, "ApprovedContainmentPlanner"),
        },
    ],
    role_checks: &[
        RoleCheckSpec {
            label: "analyst owns incident",
            subject: ResourceRef::Actor,
            role_iri: concat!(NS, "assignedTo"),
            object: ResourceRef::Slot("incident"),
        },
        RoleCheckSpec {
            label: "analyst is authorized at selected tier",
            subject: ResourceRef::Actor,
            role_iri: concat!(NS, "authorizedAtTier"),
            object: ResourceRef::Slot("approval_tier"),
        },
        RoleCheckSpec {
            label: "alert supports incident",
            subject: ResourceRef::Slot("alert"),
            role_iri: concat!(NS, "supportsIncident"),
            object: ResourceRef::Slot("incident"),
        },
        RoleCheckSpec {
            label: "alert concerns host",
            subject: ResourceRef::Slot("alert"),
            role_iri: concat!(NS, "concernsHost"),
            object: ResourceRef::Slot("host"),
        },
        RoleCheckSpec {
            label: "host belongs to segment",
            subject: ResourceRef::Slot("host"),
            role_iri: concat!(NS, "memberOf"),
            object: ResourceRef::Slot("segment"),
        },
        RoleCheckSpec {
            label: "planner supports containment",
            subject: ResourceRef::Constant(concat!(NS, "containment-proposal-planner")),
            role_iri: concat!(NS, "supportsOperation"),
            object: ResourceRef::Slot("containment"),
        },
    ],
    policy_id: "secops-containment.reversible-host-isolation.v1",
    deterministic_checks: &[
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected incident",
            predicate: "incident",
            slot: "incident",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected alert",
            predicate: "alert",
            slot: "alert",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected host",
            predicate: "host",
            slot: "host",
        },
        DeterministicCheck::Iri {
            label: "incident is active",
            predicate: "incidentStatus",
            expected: "active",
        },
        DeterministicCheck::Iri {
            label: "incident severity is critical",
            predicate: "severity",
            expected: "critical",
        },
        DeterministicCheck::NumberAtLeast {
            label: "alert confidence clears threshold",
            predicate: "confidence",
            minimum: 0.95,
        },
        DeterministicCheck::NumberAtLeast {
            label: "two independent signals correlate",
            predicate: "correlatedSignalCount",
            minimum: 2.0,
        },
        DeterministicCheck::Iri {
            label: "EDR sensor reports healthy",
            predicate: "edrHealth",
            expected: "healthy",
        },
        DeterministicCheck::Boolean {
            label: "EDR supports reversible isolation",
            predicate: "isolationSupported",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "no isolation exception exists",
            predicate: "isolationException",
            expected: false,
        },
        DeterministicCheck::Boolean {
            label: "break-glass is inactive",
            predicate: "breakGlassActive",
            expected: false,
        },
        DeterministicCheck::Iri {
            label: "asset criticality permits a proposal",
            predicate: "assetCriticality",
            expected: "medium",
        },
        DeterministicCheck::NumberEqualsSlot {
            label: "evidence duration matches requested isolation",
            predicate: "durationMinutes",
            slot: "duration_minutes",
        },
        DeterministicCheck::DurationAtMost {
            label: "sensor observation is fresh in the signed snapshot",
            earlier: "sensorObservedAt",
            later: "observedAt",
            maximum_seconds: 120,
        },
    ],
    policy_details_json: r#"{"severity":"critical","confidence":0.98,"correlated_signals":2,"edr_health":"healthy","asset_criticality":"medium","isolation_exception":false,"break_glass":false,"owner":"Maya Ortiz","ttl_minutes":30}"#,
    effect: EffectSpec {
        kind: "endpoint_isolation_proposal",
        outcome: "bounded-host-containment-proposed",
        external_effect_field: "host_or_network_changed",
    },
    effect_details_json: r#"{"scope":"single-host","state":"proposed","edr_command_sent":false}"#,
};
