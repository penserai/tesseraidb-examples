use super::configured::{
    ClassCheckSpec, ConfiguredScenario, DeterministicCheck, ExpectedSlot, ResourceRef,
    RoleCheckSpec,
};
use crate::{DomainAssets, EffectSpec, EvidenceAssets, RejectionProbe};

macro_rules! concat {
    (NS, $suffix:literal) => {
        std::concat!("urn:agent-calculus:workload-zero-trust:", $suffix)
    };
}

pub static SCENARIO: ConfiguredScenario = ConfiguredScenario {
    id: "workload-zero-trust",
    title: "Ephemeral workload-to-workload authorization",
    assets: DomainAssets {
        manifest_json: include_str!("../../domains/workload-zero-trust/manifest.json"),
        request_shapes_turtle: include_str!("../../domains/workload-zero-trust/request-shapes.ttl"),
        ontology_ofn: include_str!("../../domains/workload-zero-trust/ontology.ofn"),
        evidence: EvidenceAssets {
            oracle_id: "workload-zero-trust-evidence-shacl",
            shapes_turtle: include_str!("../../domains/workload-zero-trust/evidence-shapes.ttl"),
            data_turtle: include_str!("../../domains/workload-zero-trust/evidence.ttl"),
        },
    },
    actor: "urn:agent-calculus:workload-zero-trust:inventory-api",
    source: "attested-workload-identity-channel",
    turns: &[
        "inventory-api needs stock-api access in production us-east-1.",
        "Allow GET availability for 10 minutes.",
    ],
    rejection: RejectionProbe {
        utterance: "Allow POST admin on all endpoints for one hour.",
        expected_code: "excessive_workload_authority",
    },
    action_id: "propose_ephemeral_grant",
    expected_slots: &[
        ExpectedSlot::Iri {
            slot: "target",
            value: "urn:agent-calculus:workload-zero-trust:stock-api",
        },
        ExpectedSlot::Iri {
            slot: "environment",
            value: "urn:agent-calculus:workload-zero-trust:production",
        },
        ExpectedSlot::Iri {
            slot: "region",
            value: "urn:agent-calculus:workload-zero-trust:us-east-1",
        },
        ExpectedSlot::Iri {
            slot: "method",
            value: "urn:agent-calculus:workload-zero-trust:http-get",
        },
        ExpectedSlot::Iri {
            slot: "endpoint",
            value: "urn:agent-calculus:workload-zero-trust:availability-endpoint",
        },
        ExpectedSlot::Integer {
            slot: "duration_minutes",
            value: 10,
        },
    ],
    class_checks: &[
        ClassCheckSpec {
            label: "caller is an attested workload",
            resource: ResourceRef::Actor,
            class_iri: concat!(NS, "AttestedWorkload"),
        },
        ClassCheckSpec {
            label: "target is a protected service",
            resource: ResourceRef::Slot("target"),
            class_iri: concat!(NS, "ProtectedService"),
        },
        ClassCheckSpec {
            label: "method is read only",
            resource: ResourceRef::Slot("method"),
            class_iri: concat!(NS, "ReadOnlyMethod"),
        },
        ClassCheckSpec {
            label: "environment is registered",
            resource: ResourceRef::Slot("environment"),
            class_iri: concat!(NS, "DeploymentEnvironment"),
        },
        ClassCheckSpec {
            label: "region is registered",
            resource: ResourceRef::Slot("region"),
            class_iri: concat!(NS, "CloudRegion"),
        },
        ClassCheckSpec {
            label: "planner is approved",
            resource: ResourceRef::Constant(concat!(NS, "credential-proposal-planner")),
            class_iri: concat!(NS, "ApprovedCredentialProposalPlanner"),
        },
    ],
    role_checks: &[
        RoleCheckSpec {
            label: "caller may invoke target",
            subject: ResourceRef::Actor,
            role_iri: concat!(NS, "mayInvoke"),
            object: ResourceRef::Slot("target"),
        },
        RoleCheckSpec {
            label: "caller is deployed in selected environment",
            subject: ResourceRef::Actor,
            role_iri: concat!(NS, "deployedIn"),
            object: ResourceRef::Slot("environment"),
        },
        RoleCheckSpec {
            label: "caller is deployed in selected region",
            subject: ResourceRef::Actor,
            role_iri: concat!(NS, "deployedIn"),
            object: ResourceRef::Slot("region"),
        },
        RoleCheckSpec {
            label: "target exposes endpoint",
            subject: ResourceRef::Slot("target"),
            role_iri: concat!(NS, "exposes"),
            object: ResourceRef::Slot("endpoint"),
        },
        RoleCheckSpec {
            label: "endpoint permits method",
            subject: ResourceRef::Slot("endpoint"),
            role_iri: concat!(NS, "permitsMethod"),
            object: ResourceRef::Slot("method"),
        },
        RoleCheckSpec {
            label: "planner targets service",
            subject: ResourceRef::Constant(concat!(NS, "credential-proposal-planner")),
            role_iri: concat!(NS, "canPlanFor"),
            object: ResourceRef::Slot("target"),
        },
    ],
    policy_id: "workload-zero-trust.least-privilege.v1",
    deterministic_checks: &[
        DeterministicCheck::Iri {
            label: "evidence binds the authenticated caller",
            predicate: "caller",
            expected: "inventory-api",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected target",
            predicate: "target",
            slot: "target",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected method",
            predicate: "method",
            slot: "method",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected endpoint",
            predicate: "endpoint",
            slot: "endpoint",
        },
        DeterministicCheck::Boolean {
            label: "SVID verifier accepted the signature and nonce",
            predicate: "svidValid",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "identity issuer is healthy",
            predicate: "issuerHealthy",
            expected: true,
        },
        DeterministicCheck::Boolean {
            label: "policy decision permits issuance",
            predicate: "issuanceAllowed",
            expected: true,
        },
        DeterministicCheck::Literal {
            label: "deployment digest is the allowlisted artifact",
            predicate: "deploymentDigest",
            expected: "sha256:ee8c468af77ab99178c3aeaa7508a9a3f658a1bf844848dc24b51a57b76d9239",
        },
        DeterministicCheck::Literal {
            label: "policy bundle digest is pinned",
            predicate: "policyDigest",
            expected: "sha256:b7ae5a1613dbfe114a765204c6b28e642566840b9816f3189cf296cd28b1f758",
        },
        DeterministicCheck::NumberEqualsSlot {
            label: "attested grant duration matches the request",
            predicate: "durationMinutes",
            slot: "duration_minutes",
        },
        DeterministicCheck::NumberAtMost {
            label: "grant duration is bounded",
            predicate: "durationMinutes",
            maximum: 10.0,
        },
        DeterministicCheck::DurationAtMost {
            label: "attestation evidence is fresh",
            earlier: "observedAt",
            later: "evaluatedAt",
            maximum_seconds: 60,
        },
        DeterministicCheck::DateTimeBefore {
            label: "attestation remains unexpired at evaluation",
            earlier: "evaluatedAt",
            later: "expiresAt",
        },
    ],
    policy_details_json: r#"{"spiffe_id":"spiffe://example.test/ns/inventory/sa/inventory-api","namespace":"inventory","deployment_digest":"sha256:ee8c468af77a","policy_bundle":"mesh-policy-2026-10-17","nonce":"n-74b19","ttl_minutes":10}"#,
    effect: EffectSpec {
        kind: "ephemeral_credential_proposal",
        outcome: "least-privilege-grant-proposed",
        external_effect_field: "credential_or_mesh_policy_issued",
    },
    effect_details_json: r#"{"state":"proposed","credential_issued":false,"mesh_policy_changed":false}"#,
};
