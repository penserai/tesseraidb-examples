use super::configured::{
    ClassCheckSpec, ConfiguredScenario, DeterministicCheck, ExpectedSlot, ResourceRef,
    RoleCheckSpec,
};
use crate::{DomainAssets, EffectSpec, EvidenceAssets, RejectionProbe};

macro_rules! concat {
    (NS, $suffix:literal) => {
        std::concat!("urn:agent-calculus:ev-charging-dispatch:", $suffix)
    };
}

pub static SCENARIO: ConfiguredScenario = ConfiguredScenario {
    id: "ev-charging-dispatch",
    title: "Fleet EV off-peak charging dispatch",
    assets: DomainAssets {
        manifest_json: include_str!("../../domains/ev-charging-dispatch/manifest.json"),
        request_shapes_turtle: include_str!(
            "../../domains/ev-charging-dispatch/request-shapes.ttl"
        ),
        ontology_ofn: include_str!("../../domains/ev-charging-dispatch/ontology.ofn"),
        evidence: EvidenceAssets {
            oracle_id: "ev-charging-dispatch-evidence-shacl",
            shapes_turtle: include_str!("../../domains/ev-charging-dispatch/evidence-shapes.ttl"),
            data_turtle: include_str!("../../domains/ev-charging-dispatch/evidence.ttl"),
        },
    },
    actor: "urn:agent-calculus:ev-charging-dispatch:fleet-optimizer",
    source: "authenticated-fleet-energy-console",
    turns: &[
        "Schedule VAN-042 at EVSE-17 in depot west under tariff T-LOW.",
        "Use window W-0200 for 35 kWh scheduled charge.",
    ],
    rejection: RejectionProbe {
        utterance: "Override the grid interlock and force charge VAN-042.",
        expected_code: "charging_safety_override_forbidden",
    },
    action_id: "propose_scheduled_charge",
    expected_slots: &[
        ExpectedSlot::Iri {
            slot: "vehicle",
            value: "urn:agent-calculus:ev-charging-dispatch:van-042",
        },
        ExpectedSlot::Iri {
            slot: "charger",
            value: "urn:agent-calculus:ev-charging-dispatch:evse-17",
        },
        ExpectedSlot::Iri {
            slot: "depot",
            value: "urn:agent-calculus:ev-charging-dispatch:depot-west",
        },
        ExpectedSlot::Iri {
            slot: "tariff",
            value: "urn:agent-calculus:ev-charging-dispatch:t-low",
        },
        ExpectedSlot::Iri {
            slot: "window",
            value: "urn:agent-calculus:ev-charging-dispatch:w-0200",
        },
        ExpectedSlot::Integer {
            slot: "energy_kwh",
            value: 35,
        },
        ExpectedSlot::Iri {
            slot: "operation",
            value: "urn:agent-calculus:ev-charging-dispatch:scheduled-charge",
        },
    ],
    class_checks: &[
        ClassCheckSpec {
            label: "optimizer is authorized",
            resource: ResourceRef::Actor,
            class_iri: concat!(NS, "AuthorizedFleetOptimizer"),
        },
        ClassCheckSpec {
            label: "vehicle is a managed fleet EV",
            resource: ResourceRef::Slot("vehicle"),
            class_iri: concat!(NS, "ManagedFleetEv"),
        },
        ClassCheckSpec {
            label: "charger is an available depot charger",
            resource: ResourceRef::Slot("charger"),
            class_iri: concat!(NS, "AvailableDepotCharger"),
        },
        ClassCheckSpec {
            label: "operation is a bounded scheduled-charge proposal",
            resource: ResourceRef::Slot("operation"),
            class_iri: concat!(NS, "ScheduledChargeProposal"),
        },
        ClassCheckSpec {
            label: "orchestrator is approved",
            resource: ResourceRef::Constant(concat!(NS, "charge-proposal-orchestrator")),
            class_iri: concat!(NS, "ApprovedChargeProposalOrchestrator"),
        },
    ],
    role_checks: &[
        RoleCheckSpec {
            label: "optimizer is authorized for depot",
            subject: ResourceRef::Actor,
            role_iri: concat!(NS, "authorizedFor"),
            object: ResourceRef::Slot("depot"),
        },
        RoleCheckSpec {
            label: "vehicle is assigned to depot",
            subject: ResourceRef::Slot("vehicle"),
            role_iri: concat!(NS, "assignedTo"),
            object: ResourceRef::Slot("depot"),
        },
        RoleCheckSpec {
            label: "charger is installed at depot",
            subject: ResourceRef::Slot("charger"),
            role_iri: concat!(NS, "installedAt"),
            object: ResourceRef::Slot("depot"),
        },
        RoleCheckSpec {
            label: "tariff applies to window",
            subject: ResourceRef::Slot("tariff"),
            role_iri: concat!(NS, "appliesDuring"),
            object: ResourceRef::Slot("window"),
        },
        RoleCheckSpec {
            label: "orchestrator controls charger",
            subject: ResourceRef::Constant(concat!(NS, "charge-proposal-orchestrator")),
            role_iri: concat!(NS, "controls"),
            object: ResourceRef::Slot("charger"),
        },
        RoleCheckSpec {
            label: "orchestrator supports the selected operation",
            subject: ResourceRef::Constant(concat!(NS, "charge-proposal-orchestrator")),
            role_iri: concat!(NS, "supportsOperation"),
            object: ResourceRef::Slot("operation"),
        },
    ],
    policy_id: "ev-charging-dispatch.grid-route-safe.v1",
    deterministic_checks: &[
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected vehicle",
            predicate: "vehicle",
            slot: "vehicle",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected charger",
            predicate: "charger",
            slot: "charger",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected charging window",
            predicate: "window",
            slot: "window",
        },
        DeterministicCheck::NumberWithin {
            label: "current state of charge is valid",
            predicate: "socPercent",
            minimum: 0.0,
            maximum: 100.0,
        },
        DeterministicCheck::NumberEqualsSlot {
            label: "evidence energy matches the requested amount",
            predicate: "requestedKwh",
            slot: "energy_kwh",
        },
        DeterministicCheck::ScaledDifferenceCovers {
            label: "requested energy stays below target-SOC headroom",
            capacity: "batteryKwh",
            upper_percent: "targetSocPercent",
            lower_percent: "socPercent",
            required: "requestedKwh",
        },
        DeterministicCheck::ProductAtMostProduct {
            label: "charge duration fits two-hour window",
            left_a: "requestedKwh",
            left_b: 60.0,
            right_a: "chargerKw",
            right_b: "windowMinutes",
        },
        DeterministicCheck::NumberAtMostProperty {
            label: "charger draw stays below grid headroom",
            left: "chargerKw",
            right: "gridHeadroomKw",
        },
        DeterministicCheck::NumberAtMost {
            label: "tariff is below fleet cap",
            predicate: "tariffCentsPerKwh",
            maximum: 12.0,
        },
        DeterministicCheck::NumberAtLeast {
            label: "route reserve remains sufficient",
            predicate: "routeMarginKwh",
            minimum: 8.0,
        },
        DeterministicCheck::Iri {
            label: "connector is CCS2",
            predicate: "connector",
            expected: "ccs2",
        },
        DeterministicCheck::Boolean {
            label: "charger is available",
            predicate: "chargerAvailable",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "charging interlock is healthy",
            predicate: "interlockHealthy",
            expected: true,
        },
    ],
    policy_details_json: r#"{"soc_percent":31,"target_soc_percent":80,"battery_kwh":72,"requested_kwh":35,"charger_kw":22,"grid_headroom_kw":48,"tariff_cents_per_kwh":9,"tariff_cap_cents":12,"window_minutes":120,"connector":"CCS2","route_margin_kwh":8}"#,
    effect: EffectSpec {
        kind: "scheduled_charge_proposal",
        outcome: "grid-and-route-safe-charge-proposed",
        external_effect_field: "physical_charge_command_sent",
    },
    effect_details_json: r#"{"state":"proposed","charge_command_sent":false,"interlock_overridden":false}"#,
};
