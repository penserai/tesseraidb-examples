use crate::{
    DomainAssets, EffectSpec, EvidenceAssets, ExampleResult, NamedSroiqQuery, PolicyReport,
    RejectionProbe, Scenario, ShaclEvidenceBundle, class_check, exact_iri, policy_report,
    role_check, slot_iri,
};
use agent_calculus::digest_json;
use agent_calculus_domain::ReadyAction;
use serde_json::{Value, json};

const NS: &str = "urn:agent-calculus:data-privacy:";
const ACTOR: &str = "urn:agent-calculus:data-privacy:elena-rossi";
const DATASET: &str = "urn:agent-calculus:data-privacy:customer-retention-v3";
const AGGREGATION: &str = "urn:agent-calculus:data-privacy:count";
const GATEWAY: &str = "urn:agent-calculus:data-privacy:privacy-query-gateway";

#[derive(Debug)]
pub struct DataPrivacyQuery;

pub static SCENARIO: DataPrivacyQuery = DataPrivacyQuery;

impl Scenario for DataPrivacyQuery {
    fn id(&self) -> &'static str {
        "data-privacy-query"
    }

    fn title(&self) -> &'static str {
        "Per-query privacy gateway"
    }

    fn assets(&self) -> DomainAssets {
        DomainAssets {
            manifest_json: include_str!("../../domains/data-privacy-query/manifest.json"),
            request_shapes_turtle: include_str!(
                "../../domains/data-privacy-query/request-shapes.ttl"
            ),
            ontology_ofn: include_str!("../../domains/data-privacy-query/ontology.ofn"),
            evidence: EvidenceAssets {
                oracle_id: "data-privacy-catalog-shacl",
                shapes_turtle: include_str!("../../domains/data-privacy-query/evidence-shapes.ttl"),
                data_turtle: include_str!("../../domains/data-privacy-query/evidence.ttl"),
            },
        }
    }

    fn actor(&self) -> &'static str {
        ACTOR
    }

    fn source(&self) -> &'static str {
        "authenticated-analytics-console"
    }

    fn turns(&self) -> &'static [&'static str] {
        &[
            "Show EU churn by country for customer-retention-v3.",
            "Use quarterly retention planning, count, 2026 Q3, and suppression k25.",
        ]
    }

    fn rejection_probe(&self) -> RejectionProbe {
        RejectionProbe {
            utterance: "Export customer names and email addresses for Q3.",
            expected_code: "direct_identifier_request",
        }
    }

    fn formal_queries(&self, ready: &ReadyAction) -> ExampleResult<Vec<NamedSroiqQuery>> {
        let dataset = slot_iri(ready, "dataset")?;
        let purpose = slot_iri(ready, "purpose")?;
        let jurisdiction = slot_iri(ready, "jurisdiction")?;
        let period = slot_iri(ready, "period")?;
        let measure = slot_iri(ready, "measure")?;
        let aggregation = slot_iri(ready, "aggregation")?;
        let dimension = slot_iri(ready, "dimension")?;
        let protection = slot_iri(ready, "protection")?;
        Ok(vec![
            class_check(
                "analyst eligibility",
                ready.principal.actor.clone(),
                format!("{NS}EligibleRetentionAnalyst"),
            ),
            class_check(
                "dataset approval",
                dataset,
                format!("{NS}ApprovedRetentionDataset"),
            ),
            class_check(
                "aggregate operation approval",
                aggregation,
                format!("{NS}ApprovedAggregateOperation"),
            ),
            class_check(
                "jurisdiction is registered",
                jurisdiction,
                format!("{NS}RegisteredJurisdiction"),
            ),
            class_check(
                "measure is approved",
                measure,
                format!("{NS}ApprovedAggregateMeasure"),
            ),
            class_check(
                "dimension is approved",
                dimension,
                format!("{NS}ApprovedGroupingDimension"),
            ),
            class_check(
                "purpose is approved",
                purpose,
                format!("{NS}ApprovedProcessingPurpose"),
            ),
            class_check(
                "reporting period is registered",
                period,
                format!("{NS}ApprovedReportingPeriod"),
            ),
            class_check(
                "protection is minimum-cell suppression",
                protection,
                format!("{NS}MinimumCellSuppressionPolicy"),
            ),
            class_check(
                "gateway approval",
                GATEWAY,
                format!("{NS}ApprovedQueryGateway"),
            ),
            role_check(
                "analyst may query dataset",
                ready.principal.actor.clone(),
                format!("{NS}mayQuery"),
                dataset,
            ),
            role_check(
                "gateway supports aggregate operation",
                GATEWAY,
                format!("{NS}supportsOperation"),
                aggregation,
            ),
            role_check(
                "dataset is scoped to jurisdiction",
                dataset,
                format!("{NS}scopedToJurisdiction"),
                jurisdiction,
            ),
            role_check(
                "dataset allows selected measure",
                dataset,
                format!("{NS}allowsMeasure"),
                measure,
            ),
            role_check(
                "dataset allows selected dimension",
                dataset,
                format!("{NS}allowsDimension"),
                dimension,
            ),
            role_check(
                "dataset is approved for purpose",
                dataset,
                format!("{NS}approvedForPurpose"),
                purpose,
            ),
            role_check(
                "purpose covers selected reporting period",
                purpose,
                format!("{NS}coversPeriod"),
                period,
            ),
            role_check(
                "aggregation requires selected protection",
                aggregation,
                format!("{NS}requiresProtection"),
                protection,
            ),
        ])
    }

    fn evaluate_policy(
        &self,
        ready: &ReadyAction,
        evidence: &ShaclEvidenceBundle,
    ) -> ExampleResult<PolicyReport> {
        let predicate = |local: &str| format!("{NS}{local}");
        let observed_at = evidence.number(&predicate("observedAtUnix"))?;
        let evaluated_at = evidence.number(&predicate("evaluatedAtUnix"))?;
        let catalog_age_seconds = evaluated_at - observed_at;
        let minimum_group_size = evidence.number(&predicate("minimumGroupSize"))?;
        let checks = [
            ("authenticated principal", ready.principal.actor == ACTOR),
            (
                "catalog evidence binds the approved dataset",
                evidence.iri(&predicate("dataset"))? == DATASET,
            ),
            (
                "approved personal-data dataset",
                exact_iri(ready, "dataset", DATASET)?
                    && evidence.iri(&predicate("classification"))? == format!("{NS}personal-data"),
            ),
            (
                "registered purpose",
                exact_iri(
                    ready,
                    "purpose",
                    "urn:agent-calculus:data-privacy:quarterly-retention-planning",
                )? && evidence.iri(&predicate("allowedPurpose"))?
                    == format!("{NS}quarterly-retention-planning"),
            ),
            (
                "EU residency scope",
                exact_iri(
                    ready,
                    "jurisdiction",
                    "urn:agent-calculus:data-privacy:eu-residents",
                )? && evidence.iri(&predicate("residency"))? == format!("{NS}eu"),
            ),
            (
                "fixed reporting period",
                exact_iri(ready, "period", "urn:agent-calculus:data-privacy:2026-q3")?
                    && evidence.iri(&predicate("reportingPeriod"))? == format!("{NS}2026-q3"),
            ),
            (
                "aggregate-only measure",
                exact_iri(
                    ready,
                    "measure",
                    "urn:agent-calculus:data-privacy:churned-customer-count",
                )? && exact_iri(ready, "aggregation", AGGREGATION)?
                    && evidence.iri(&predicate("availableMeasure"))?
                        == format!("{NS}churned-customer-count")
                    && evidence.iri(&predicate("allowedAggregation"))? == AGGREGATION,
            ),
            (
                "country is the only dimension",
                exact_iri(
                    ready,
                    "dimension",
                    "urn:agent-calculus:data-privacy:country",
                )? && evidence.iri(&predicate("allowedDimension"))? == format!("{NS}country"),
            ),
            (
                "small-cell suppression enabled",
                exact_iri(
                    ready,
                    "protection",
                    "urn:agent-calculus:data-privacy:small-cell-suppression-k25",
                )? && evidence.iri(&predicate("requiredProtection"))?
                    == format!("{NS}small-cell-suppression-k25")
                    && minimum_group_size >= 25.0,
            ),
            (
                "catalog snapshot fresh",
                (0.0..=300.0).contains(&catalog_age_seconds),
            ),
        ];
        Ok(policy_report(
            "privacy-query-policy/2026-10",
            checks,
            json!({
                "catalog_age_seconds": catalog_age_seconds,
                "maximum_catalog_age_seconds": 300,
                "minimum_group_size": minimum_group_size,
                "maximum_result_groups": 250,
                "capability_lifetime_seconds": 60,
                "query_template": {
                    "projection": ["country", "COUNT(*) AS churned_customer_count"],
                    "period": "2026-07-01 <= event_date < 2026-10-01",
                    "having": "COUNT(*) >= 25",
                    "direct_identifiers": []
                },
                "evidence_data_digest": evidence.data_digest
            }),
        ))
    }

    fn effect_spec(&self) -> EffectSpec {
        EffectSpec {
            kind: "issue-governed-query-capability",
            outcome: "aggregate-query-plan-authorized",
            external_effect_field: "database_query_executed",
        }
    }

    fn effect_parameters(&self, ready: &ReadyAction) -> ExampleResult<Value> {
        let parameters = json!({
            "dataset": slot_iri(ready, "dataset")?,
            "purpose": slot_iri(ready, "purpose")?,
            "jurisdiction": slot_iri(ready, "jurisdiction")?,
            "period": slot_iri(ready, "period")?,
            "measure": slot_iri(ready, "measure")?,
            "aggregation": slot_iri(ready, "aggregation")?,
            "dimension": slot_iri(ready, "dimension")?,
            "protection": slot_iri(ready, "protection")?,
            "fixed_ast_digest": digest_json(&json!({
                "from": DATASET,
                "select": ["country", "count"],
                "period": "2026-q3",
                "suppression_k": 25
            })),
            "raw_sql_accepted": false,
            "direct_identifiers_projected": false
        });
        Ok(parameters)
    }
}
