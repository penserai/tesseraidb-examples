use super::configured::{
    ClassCheckSpec, ConfiguredScenario, DeterministicCheck, ExpectedSlot, ResourceRef,
    RoleCheckSpec,
};
use crate::{DomainAssets, EffectSpec, EvidenceAssets, RejectionProbe};

macro_rules! concat {
    (NS, $suffix:literal) => {
        std::concat!("urn:agent-calculus:invoice-three-way-match:", $suffix)
    };
}

pub static SCENARIO: ConfiguredScenario = ConfiguredScenario {
    id: "invoice-three-way-match",
    title: "Auditable invoice three-way match",
    assets: DomainAssets {
        manifest_json: include_str!("../../domains/invoice-three-way-match/manifest.json"),
        request_shapes_turtle: include_str!(
            "../../domains/invoice-three-way-match/request-shapes.ttl"
        ),
        ontology_ofn: include_str!("../../domains/invoice-three-way-match/ontology.ofn"),
        evidence: EvidenceAssets {
            oracle_id: "invoice-three-way-match-evidence-shacl",
            shapes_turtle: include_str!(
                "../../domains/invoice-three-way-match/evidence-shapes.ttl"
            ),
            data_turtle: include_str!("../../domains/invoice-three-way-match/evidence.ttl"),
        },
    },
    actor: "urn:agent-calculus:invoice-three-way-match:ap-analyst-17",
    source: "authenticated-accounts-payable-console",
    turns: &[
        "Match invoice INV-88231 with PO-7319 and receipt GR-5512.",
        "Use vendor SUP-0144 and propose payment release at AP tier one.",
    ],
    rejection: RejectionProbe {
        utterance: "Pay INV-88231 directly and override the tolerance.",
        expected_code: "payment_control_bypass",
    },
    action_id: "propose_payment_release",
    expected_slots: &[
        ExpectedSlot::Iri {
            slot: "invoice",
            value: "urn:agent-calculus:invoice-three-way-match:inv-88231",
        },
        ExpectedSlot::Iri {
            slot: "purchase_order",
            value: "urn:agent-calculus:invoice-three-way-match:po-7319",
        },
        ExpectedSlot::Iri {
            slot: "goods_receipt",
            value: "urn:agent-calculus:invoice-three-way-match:gr-5512",
        },
        ExpectedSlot::Iri {
            slot: "vendor",
            value: "urn:agent-calculus:invoice-three-way-match:sup-0144",
        },
        ExpectedSlot::Iri {
            slot: "release_operation",
            value: "urn:agent-calculus:invoice-three-way-match:payment-release-proposal",
        },
        ExpectedSlot::Iri {
            slot: "approval_tier",
            value: "urn:agent-calculus:invoice-three-way-match:ap-tier-one",
        },
    ],
    class_checks: &[
        ClassCheckSpec {
            label: "actor is an authorized AP reviewer",
            resource: ResourceRef::Actor,
            class_iri: concat!(NS, "AuthorizedAccountsPayableReviewer"),
        },
        ClassCheckSpec {
            label: "invoice is a registered payment candidate",
            resource: ResourceRef::Slot("invoice"),
            class_iri: concat!(NS, "RegisteredInvoice"),
        },
        ClassCheckSpec {
            label: "operation is proposal only",
            resource: ResourceRef::Slot("release_operation"),
            class_iri: concat!(NS, "PaymentReleaseProposal"),
        },
        ClassCheckSpec {
            label: "approval tier is registered",
            resource: ResourceRef::Slot("approval_tier"),
            class_iri: concat!(NS, "AccountsPayableApprovalTier"),
        },
        ClassCheckSpec {
            label: "executor is approved",
            resource: ResourceRef::Constant(concat!(NS, "payment-proposal-planner")),
            class_iri: concat!(NS, "ApprovedPaymentProposalPlanner"),
        },
    ],
    role_checks: &[
        RoleCheckSpec {
            label: "reviewer is assigned to invoice",
            subject: ResourceRef::Actor,
            role_iri: concat!(NS, "assignedTo"),
            object: ResourceRef::Slot("invoice"),
        },
        RoleCheckSpec {
            label: "reviewer is authorized at selected tier",
            subject: ResourceRef::Actor,
            role_iri: concat!(NS, "authorizedAtTier"),
            object: ResourceRef::Slot("approval_tier"),
        },
        RoleCheckSpec {
            label: "invoice was issued by selected vendor",
            subject: ResourceRef::Slot("invoice"),
            role_iri: concat!(NS, "issuedBy"),
            object: ResourceRef::Slot("vendor"),
        },
        RoleCheckSpec {
            label: "purchase order names selected vendor",
            subject: ResourceRef::Slot("purchase_order"),
            role_iri: concat!(NS, "orderedFrom"),
            object: ResourceRef::Slot("vendor"),
        },
        RoleCheckSpec {
            label: "receipt fulfills purchase order",
            subject: ResourceRef::Slot("goods_receipt"),
            role_iri: concat!(NS, "fulfills"),
            object: ResourceRef::Slot("purchase_order"),
        },
        RoleCheckSpec {
            label: "executor supports proposal",
            subject: ResourceRef::Constant(concat!(NS, "payment-proposal-planner")),
            role_iri: concat!(NS, "supportsOperation"),
            object: ResourceRef::Slot("release_operation"),
        },
    ],
    policy_id: "invoice-three-way-match.exact-match.v1",
    deterministic_checks: &[
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected invoice",
            predicate: "invoice",
            slot: "invoice",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected purchase order",
            predicate: "purchaseOrder",
            slot: "purchase_order",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected goods receipt",
            predicate: "goodsReceipt",
            slot: "goods_receipt",
        },
        DeterministicCheck::IriEqualsSlot {
            label: "evidence binds the selected vendor",
            predicate: "vendor",
            slot: "vendor",
        },
        DeterministicCheck::NumbersEqual {
            label: "ordered and invoiced quantities agree",
            left: "orderedQuantity",
            right: "invoicedQuantity",
        },
        DeterministicCheck::NumbersEqual {
            label: "invoiced and received quantities agree",
            left: "invoicedQuantity",
            right: "receivedQuantity",
        },
        DeterministicCheck::BasisPointVarianceAtMost {
            label: "PO and invoice unit prices stay within tolerance",
            baseline: "orderedUnitPriceCents",
            observed: "invoicedUnitPriceCents",
            tolerance_basis_points: "toleranceBasisPoints",
        },
        DeterministicCheck::ProductEquals {
            label: "invoice subtotal recomputes from quantity and unit price",
            left: "invoicedQuantity",
            right: "invoicedUnitPriceCents",
            product: "subtotalCents",
        },
        DeterministicCheck::SumEquals {
            label: "invoice total recomputes from subtotal and tax",
            left: "subtotalCents",
            right: "taxCents",
            sum: "totalCents",
        },
        DeterministicCheck::NumberAtMost {
            label: "duplicate invoice count is zero",
            predicate: "duplicateCount",
            maximum: 0.0,
        },
        DeterministicCheck::Iri {
            label: "purchase order is approved",
            predicate: "poStatus",
            expected: "approved",
        },
        DeterministicCheck::Iri {
            label: "goods receipt is accepted",
            predicate: "receiptStatus",
            expected: "accepted",
        },
        DeterministicCheck::Iri {
            label: "invoice awaits matching",
            predicate: "invoiceStatus",
            expected: "pending-match",
        },
    ],
    policy_details_json: r#"{"currency":"USD","quantity":100,"unit_price_cents":2450,"subtotal_cents":245000,"tax_cents":19600,"total_cents":264600,"tolerance_basis_points":50,"duplicate_count":0,"vendor_fingerprint":"sha256:7ce73909d1e87a13"}"#,
    effect: EffectSpec {
        kind: "payment_release_proposal",
        outcome: "three-way-match-proposal-authorized",
        external_effect_field: "payment_or_erp_mutated",
    },
    effect_details_json: r#"{"state":"proposed","payment_sent":false,"erp_posted":false}"#,
};
