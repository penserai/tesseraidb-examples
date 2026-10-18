use super::configured::{
    ClassCheckSpec, ConfiguredScenario, DeterministicCheck, ExpectedSlot, ResourceRef,
    RoleCheckSpec,
};
use crate::{DomainAssets, EffectSpec, EvidenceAssets, RejectionProbe};

macro_rules! concat {
    (NS, $suffix:literal) => {
        std::concat!("urn:agent-calculus:laboratory-sample-routing:", $suffix)
    };
}

pub static SCENARIO: ConfiguredScenario = ConfiguredScenario {
    id: "laboratory-sample-routing",
    title: "Chain-of-custody laboratory sample routing",
    assets: DomainAssets {
        manifest_json: include_str!("../../domains/laboratory-sample-routing/manifest.json"),
        request_shapes_turtle: include_str!(
            "../../domains/laboratory-sample-routing/request-shapes.ttl"
        ),
        ontology_ofn: include_str!("../../domains/laboratory-sample-routing/ontology.ofn"),
        evidence: EvidenceAssets {
            oracle_id: "laboratory-sample-routing-evidence-shacl",
            shapes_turtle: include_str!(
                "../../domains/laboratory-sample-routing/evidence-shapes.ttl"
            ),
            data_turtle: include_str!("../../domains/laboratory-sample-routing/evidence.ttl"),
        },
    },
    actor: "urn:agent-calculus:laboratory-sample-routing:alex-morgan",
    source: "authenticated-lims-console",
    turns: &[
        "Route accession ACC-2048 serum for potassium assay to central chemistry.",
        "Use analyzer CHEM-7 with custody COC-881 under biosafety two.",
    ],
    rejection: RejectionProbe {
        utterance: "Skip custody and alter the result for ACC-2048.",
        expected_code: "laboratory_safety_bypass_forbidden",
    },
    action_id: "propose_sample_route",
    expected_slots: &[
        ExpectedSlot::Iri {
            slot: "accession",
            value: "urn:agent-calculus:laboratory-sample-routing:acc-2048",
        },
        ExpectedSlot::Iri {
            slot: "specimen",
            value: "urn:agent-calculus:laboratory-sample-routing:serum",
        },
        ExpectedSlot::Iri {
            slot: "assay",
            value: "urn:agent-calculus:laboratory-sample-routing:potassium-assay",
        },
        ExpectedSlot::Iri {
            slot: "laboratory",
            value: "urn:agent-calculus:laboratory-sample-routing:central-chemistry",
        },
        ExpectedSlot::Iri {
            slot: "analyzer",
            value: "urn:agent-calculus:laboratory-sample-routing:chem-7",
        },
        ExpectedSlot::Iri {
            slot: "custody",
            value: "urn:agent-calculus:laboratory-sample-routing:coc-881",
        },
        ExpectedSlot::Iri {
            slot: "biosafety",
            value: "urn:agent-calculus:laboratory-sample-routing:biosafety-two",
        },
    ],
    class_checks: &[
        ClassCheckSpec {
            label: "technologist is qualified",
            resource: ResourceRef::Actor,
            class_iri: concat!(NS, "QualifiedLaboratoryTechnologist"),
        },
        ClassCheckSpec {
            label: "accession is a registered serum sample",
            resource: ResourceRef::Slot("accession"),
            class_iri: concat!(NS, "RegisteredSerumAccession"),
        },
        ClassCheckSpec {
            label: "specimen type is registered",
            resource: ResourceRef::Slot("specimen"),
            class_iri: concat!(NS, "SpecimenType"),
        },
        ClassCheckSpec {
            label: "biosafety level is registered",
            resource: ResourceRef::Slot("biosafety"),
            class_iri: concat!(NS, "BiosafetyLevel"),
        },
        ClassCheckSpec {
            label: "analyzer supports potassium assay",
            resource: ResourceRef::Slot("analyzer"),
            class_iri: concat!(NS, "PotassiumAnalyzer"),
        },
        ClassCheckSpec {
            label: "queue planner is approved",
            resource: ResourceRef::Constant(concat!(NS, "lims-routing-planner")),
            class_iri: concat!(NS, "ApprovedLimsRoutingPlanner"),
        },
    ],
    role_checks: &[
        RoleCheckSpec {
            label: "technologist is qualified for assay",
            subject: ResourceRef::Actor,
            role_iri: concat!(NS, "qualifiedFor"),
            object: ResourceRef::Slot("assay"),
        },
        RoleCheckSpec {
            label: "accession has custody record",
            subject: ResourceRef::Slot("accession"),
            role_iri: concat!(NS, "hasCustodyRecord"),
            object: ResourceRef::Slot("custody"),
        },
        RoleCheckSpec {
            label: "accession has selected specimen type",
            subject: ResourceRef::Slot("accession"),
            role_iri: concat!(NS, "hasSpecimenType"),
            object: ResourceRef::Slot("specimen"),
        },
        RoleCheckSpec {
            label: "assay requires selected biosafety level",
            subject: ResourceRef::Slot("assay"),
            role_iri: concat!(NS, "requiresBiosafetyLevel"),
            object: ResourceRef::Slot("biosafety"),
        },
        RoleCheckSpec {
            label: "assay routes to laboratory",
            subject: ResourceRef::Slot("assay"),
            role_iri: concat!(NS, "routedTo"),
            object: ResourceRef::Slot("laboratory"),
        },
        RoleCheckSpec {
            label: "analyzer is located in laboratory",
            subject: ResourceRef::Slot("analyzer"),
            role_iri: concat!(NS, "locatedIn"),
            object: ResourceRef::Slot("laboratory"),
        },
        RoleCheckSpec {
            label: "planner supports analyzer",
            subject: ResourceRef::Constant(concat!(NS, "lims-routing-planner")),
            role_iri: concat!(NS, "plansFor"),
            object: ResourceRef::Slot("analyzer"),
        },
    ],
    policy_id: "laboratory-sample-routing.custody-and-quality.v1",
    deterministic_checks: &[
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected accession",
            predicate: "accession",
            slot: "accession",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the specimen type",
            predicate: "specimen",
            slot: "specimen",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected assay",
            predicate: "assay",
            slot: "assay",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the destination laboratory",
            predicate: "laboratory",
            slot: "laboratory",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected analyzer",
            predicate: "analyzer",
            slot: "analyzer",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the custody record",
            predicate: "custody",
            slot: "custody",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the biosafety classification",
            predicate: "biosafety",
            slot: "biosafety",
        },
        DeterministicCheck::Boolean {
            label: "accession label is verified",
            predicate: "labelVerified",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "chain of custody is signed",
            predicate: "custodySigned",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "analyzer QC is current",
            predicate: "qcCurrent",
            expected: true,
        },
        DeterministicCheck::NumberAtLeast {
            label: "biosafety numeric level is at least two",
            predicate: "biosafetyLevel",
            minimum: 2.0,
        },
        DeterministicCheck::NumberWithin {
            label: "specimen temperature is acceptable",
            predicate: "temperatureMillicelsius",
            minimum: 2000.0,
            maximum: 8000.0,
        },
        DeterministicCheck::NumberAtLeast {
            label: "analyzer has queue capacity",
            predicate: "queueCapacity",
            minimum: 1.0,
        },
        DeterministicCheck::NumberAtLeast {
            label: "sample volume meets assay minimum",
            predicate: "volumeMicroliters",
            minimum: 1000.0,
        },
        DeterministicCheck::NumberAtMost {
            label: "hemolysis index is below threshold",
            predicate: "hemolysisIndex",
            maximum: 20.0,
        },
        DeterministicCheck::NumberAtLeast {
            label: "stability window covers processing",
            predicate: "stabilityRemainingMinutes",
            minimum: 45.0,
        },
        DeterministicCheck::Literal {
            label: "custody digest is pinned",
            predicate: "custodyDigest",
            expected: "sha256:8dd12a2be68a091fad5343df5f6efc932633a04397b40ba31770bc2cf40173e4",
        },
    ],
    policy_details_json: r#"{"label_verified":true,"custody_signed":true,"qc_current":true,"biosafety_level":2,"temperature_millicelsius":4200,"queue_capacity":12,"volume_microliters":2500,"hemolysis_index":12,"hemolysis_limit":20,"stability_remaining_minutes":120}"#,
    effect: EffectSpec {
        kind: "laboratory_route_proposal",
        outcome: "sample-routing-proposed",
        external_effect_field: "laboratory_queue_modified",
    },
    effect_details_json: r#"{"state":"proposed","lims_queue_written":false,"result_changed":false}"#,
};
