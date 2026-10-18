use crate::{
    DomainAssets, EffectSpec, EvidenceAssets, ExampleResult, NamedSroiqQuery, PolicyReport,
    RejectionProbe, Scenario, ShaclEvidenceBundle, class_check, exact_iri, policy_report,
    role_check, slot_iri,
};
use agent_calculus_domain::ReadyAction;
use serde_json::{Value, json};

const NS: &str = "urn:agent-calculus:supplier-master-resolution:";
const ACTOR: &str = "urn:agent-calculus:supplier-master-resolution:master-data-steward-17";
const CASE: &str = "urn:agent-calculus:supplier-master-resolution:case-stg-9012";
const RESOLVER: &str = "urn:agent-calculus:supplier-master-resolution:master-data-linker";
const STAGING_RECORD: &str =
    "urn:agent-calculus:supplier-master-resolution:staging-record-stg-9012";
const REPORTED_NAME: &str =
    "urn:agent-calculus:supplier-master-resolution:name-northwind-components";
const CANONICAL_SUPPLIER: &str = "urn:agent-calculus:supplier-master-resolution:supplier-sup-00417";
const LOCATION: &str = "urn:agent-calculus:supplier-master-resolution:manchester";
const RESOLUTION: &str = "urn:agent-calculus:supplier-master-resolution:link-existing";
const EVIDENCE_ORACLE: &str = "supplier-master-resolution-evidence-shacl";

#[derive(Debug)]
pub struct SupplierMasterResolution;

pub static SCENARIO: SupplierMasterResolution = SupplierMasterResolution;

impl Scenario for SupplierMasterResolution {
    fn id(&self) -> &'static str {
        "supplier-master-resolution"
    }

    fn title(&self) -> &'static str {
        "Reversible supplier-master duplicate resolution"
    }

    fn assets(&self) -> DomainAssets {
        DomainAssets {
            manifest_json: include_str!("../../domains/supplier-master-resolution/manifest.json"),
            request_shapes_turtle: include_str!(
                "../../domains/supplier-master-resolution/request-shapes.ttl"
            ),
            ontology_ofn: include_str!("../../domains/supplier-master-resolution/ontology.ofn"),
            evidence: EvidenceAssets {
                oracle_id: EVIDENCE_ORACLE,
                shapes_turtle: include_str!(
                    "../../domains/supplier-master-resolution/evidence-shapes.ttl"
                ),
                data_turtle: include_str!("../../domains/supplier-master-resolution/evidence.ttl"),
            },
        }
    }

    fn actor(&self) -> &'static str {
        ACTOR
    }

    fn source(&self) -> &'static str {
        "authenticated-master-data-console"
    }

    fn turns(&self) -> &'static [&'static str] {
        &[
            "Resolve staging supplier STG-9012 for Northwind Components.",
            "Link VAT GB123456789 to the Manchester supplier.",
        ]
    }

    fn rejection_probe(&self) -> RejectionProbe {
        RejectionProbe {
            utterance: "Merge STG-9012 into both suppliers and replace the bank account.",
            expected_code: "destructive_master_mutation",
        }
    }

    fn formal_queries(&self, ready: &ReadyAction) -> ExampleResult<Vec<NamedSroiqQuery>> {
        let staging_record = slot_iri(ready, "staging_record")?;
        let reported_name = slot_iri(ready, "reported_name")?;
        let supplier = slot_iri(ready, "supplier")?;
        let location = slot_iri(ready, "location")?;
        let resolution = slot_iri(ready, "resolution")?;
        Ok(vec![
            class_check(
                "actor is an eligible master-data steward",
                ready.principal.actor.as_str(),
                format!("{NS}EligibleMasterDataSteward"),
            ),
            class_check(
                "selected source is a staged supplier record",
                staging_record,
                format!("{NS}StagedSupplierRecord"),
            ),
            class_check(
                "reported supplier name is a controlled token",
                reported_name,
                format!("{NS}ReportedSupplierNameToken"),
            ),
            class_check(
                "selected target is an approved canonical supplier",
                supplier,
                format!("{NS}ApprovedCanonicalSupplier"),
            ),
            class_check(
                "selected resolution is reversible",
                resolution,
                format!("{NS}ReversibleLinkOperation"),
            ),
            class_check(
                "resolver is an approved master-data tool",
                RESOLVER,
                format!("{NS}ApprovedMasterDataLinker"),
            ),
            role_check(
                "steward is assigned to the active resolution case",
                ready.principal.actor.as_str(),
                format!("{NS}assignedTo"),
                CASE,
            ),
            role_check(
                "resolution case targets the selected staging record",
                CASE,
                format!("{NS}caseTargetsRecord"),
                staging_record,
            ),
            role_check(
                "staging record carries selected reported name",
                staging_record,
                format!("{NS}recordHasReportedName"),
                reported_name,
            ),
            role_check(
                "canonical supplier is registered in the selected location",
                supplier,
                format!("{NS}registeredIn"),
                location,
            ),
            role_check(
                "resolver supports the selected resolution operation",
                RESOLVER,
                format!("{NS}supportsOperation"),
                resolution,
            ),
        ])
    }

    fn evaluate_policy(
        &self,
        ready: &ReadyAction,
        evidence: &ShaclEvidenceBundle,
    ) -> ExampleResult<PolicyReport> {
        let predicate = |local: &str| format!("{NS}{local}");
        let name_match_score = evidence.number(&predicate("matchScore"))?;
        let observed_at = evidence.datetime(&predicate("observedAt"))?;
        let evaluated_at = evidence.datetime(&predicate("evaluatedAt"))?;
        let evidence_age_seconds = (evaluated_at - observed_at).whole_seconds();
        let freshness_limit_seconds = 300_i64;
        Ok(policy_report(
            "supplier-master-resolution.policy.v1",
            [
                (
                    "authenticated steward is bound",
                    ready.principal.actor == ACTOR,
                ),
                (
                    "staging record is exact",
                    exact_iri(ready, "staging_record", STAGING_RECORD)?
                        && evidence.iri(&predicate("stagingRecord"))? == STAGING_RECORD,
                ),
                (
                    "reported supplier name is exact",
                    exact_iri(ready, "reported_name", REPORTED_NAME)?,
                ),
                (
                    "canonical supplier is exact",
                    exact_iri(ready, "supplier", CANONICAL_SUPPLIER)?
                        && evidence.iri(&predicate("canonicalSupplier"))? == CANONICAL_SUPPLIER,
                ),
                (
                    "registry location is exact",
                    exact_iri(ready, "location", LOCATION)?,
                ),
                (
                    "resolution is reversible link-only",
                    exact_iri(ready, "resolution", RESOLUTION)?,
                ),
                (
                    "VAT and country identifiers agree",
                    evidence.literal(&predicate("stagedVat"))?
                        == evidence.literal(&predicate("masterVat"))?
                        && evidence.iri(&predicate("stagedCountry"))?
                            == evidence.iri(&predicate("masterCountry"))?,
                ),
                (
                    "address tokens agree",
                    evidence.literal(&predicate("stagedAddressToken"))?
                        == evidence.literal(&predicate("masterAddressToken"))?,
                ),
                (
                    "name matcher cleared the fixed threshold",
                    name_match_score >= 0.98,
                ),
                (
                    "bank fingerprints do not conflict",
                    !evidence.boolean(&predicate("bankConflict"))?,
                ),
                (
                    "source is unlinked and target is active",
                    evidence.iri(&predicate("stagingStatus"))? == format!("{NS}unlinked")
                        && evidence.iri(&predicate("supplierStatus"))? == format!("{NS}active"),
                ),
                (
                    "registry match is unique",
                    evidence.number(&predicate("uniqueRegistryMatches"))? == 1.0,
                ),
                (
                    "registry evidence is fresh",
                    evidence_age_seconds >= 0 && evidence_age_seconds <= freshness_limit_seconds,
                ),
                (
                    "action records a link without merging",
                    ready.action_id == "record_supplier_link",
                ),
            ],
            json!({
                "staged_vat": evidence.literal(&predicate("stagedVat"))?,
                "master_vat": evidence.literal(&predicate("masterVat"))?,
                "country": evidence.iri(&predicate("masterCountry"))?,
                "address_token": evidence.literal(&predicate("masterAddressToken"))?,
                "name_match_score": name_match_score,
                "unique_registry_matches": evidence.number(&predicate("uniqueRegistryMatches"))?,
                "bank_fingerprint_conflict": evidence.boolean(&predicate("bankConflict"))?,
                "evidence_age_seconds": evidence_age_seconds,
                "freshness_limit_seconds": freshness_limit_seconds,
                "registry_snapshot": "supplier-registry-snapshot-44"
            }),
        ))
    }

    fn effect_spec(&self) -> EffectSpec {
        EffectSpec {
            kind: "reversible_supplier_link",
            outcome: "supplier-master link proposal simulated",
            external_effect_field: "master_data_mutated",
        }
    }

    fn effect_parameters(&self, ready: &ReadyAction) -> ExampleResult<Value> {
        Ok(json!({
            "resolver": RESOLVER,
            "actor": ready.principal.actor.as_str(),
            "case": CASE,
            "staging_record": slot_iri(ready, "staging_record")?,
            "reported_name": slot_iri(ready, "reported_name")?,
            "canonical_supplier": slot_iri(ready, "supplier")?,
            "location": slot_iri(ready, "location")?,
            "resolution": slot_iri(ready, "resolution")?,
            "link_state": "proposed",
            "reversible": true,
            "records_merged": false,
            "bank_data_changed": false
        }))
    }
}
