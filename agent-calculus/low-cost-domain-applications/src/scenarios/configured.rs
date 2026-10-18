use crate::{
    DomainAssets, EffectSpec, EvidenceTerm, ExampleResult, NamedSroiqQuery, PolicyReport,
    RejectionProbe, Scenario, ShaclEvidenceBundle, class_check, policy_report, role_check,
    slot_integer, slot_iri,
};
use agent_calculus::{FormalVerdict, digest_json};
use agent_calculus_domain::{DomainManifest, ReadyAction};
use serde_json::{Map, Value, json};
use std::io;
use time::OffsetDateTime;
use time::format_description::well_known::Rfc3339;

#[derive(Clone, Copy, Debug)]
pub enum ResourceRef {
    Actor,
    Slot(&'static str),
    Constant(&'static str),
}

#[derive(Clone, Copy, Debug)]
pub struct ClassCheckSpec {
    pub label: &'static str,
    pub resource: ResourceRef,
    pub class_iri: &'static str,
}

#[derive(Clone, Copy, Debug)]
pub struct RoleCheckSpec {
    pub label: &'static str,
    pub subject: ResourceRef,
    pub role_iri: &'static str,
    pub object: ResourceRef,
}

#[derive(Clone, Copy, Debug)]
pub enum ExpectedSlot {
    Iri {
        slot: &'static str,
        value: &'static str,
    },
    Integer {
        slot: &'static str,
        value: i64,
    },
}

impl ExpectedSlot {
    fn slot(self) -> &'static str {
        match self {
            Self::Iri { slot, .. } | Self::Integer { slot, .. } => slot,
        }
    }

    fn matches(self, ready: &ReadyAction) -> ExampleResult<bool> {
        match self {
            Self::Iri { slot, value } => Ok(slot_iri(ready, slot)? == value),
            Self::Integer { slot, value } => Ok(slot_integer(ready, slot)? == value),
        }
    }
}

#[derive(Clone, Copy, Debug)]
pub enum DeterministicCheck {
    Boolean {
        label: &'static str,
        predicate: &'static str,
        expected: bool,
    },
    Iri {
        label: &'static str,
        predicate: &'static str,
        expected: &'static str,
    },
    Literal {
        label: &'static str,
        predicate: &'static str,
        expected: &'static str,
    },
    IriEqualsSlot {
        label: &'static str,
        predicate: &'static str,
        slot: &'static str,
    },
    NumberEqualsSlot {
        label: &'static str,
        predicate: &'static str,
        slot: &'static str,
    },
    NumberAtLeastSlot {
        label: &'static str,
        predicate: &'static str,
        slot: &'static str,
    },
    NumberAtMostSlot {
        label: &'static str,
        predicate: &'static str,
        slot: &'static str,
    },
    NumberAtLeast {
        label: &'static str,
        predicate: &'static str,
        minimum: f64,
    },
    NumberAtMost {
        label: &'static str,
        predicate: &'static str,
        maximum: f64,
    },
    NumberWithin {
        label: &'static str,
        predicate: &'static str,
        minimum: f64,
        maximum: f64,
    },
    NumbersEqual {
        label: &'static str,
        left: &'static str,
        right: &'static str,
    },
    NumberAtMostProperty {
        label: &'static str,
        left: &'static str,
        right: &'static str,
    },
    NumberAtLeastProperty {
        label: &'static str,
        left: &'static str,
        right: &'static str,
    },
    NumberBetweenProperties {
        label: &'static str,
        value: &'static str,
        minimum: &'static str,
        maximum: &'static str,
    },
    SumEquals {
        label: &'static str,
        left: &'static str,
        right: &'static str,
        sum: &'static str,
    },
    ProductEquals {
        label: &'static str,
        left: &'static str,
        right: &'static str,
        product: &'static str,
    },
    DifferenceEquals {
        label: &'static str,
        minuend: &'static str,
        subtrahend: &'static str,
        difference: &'static str,
    },
    BasisPointVarianceAtMost {
        label: &'static str,
        baseline: &'static str,
        observed: &'static str,
        tolerance_basis_points: &'static str,
    },
    ScaledDifferenceCovers {
        label: &'static str,
        capacity: &'static str,
        upper_percent: &'static str,
        lower_percent: &'static str,
        required: &'static str,
    },
    ProductAtMostProduct {
        label: &'static str,
        left_a: &'static str,
        left_b: f64,
        right_a: &'static str,
        right_b: &'static str,
    },
    DateTimeBefore {
        label: &'static str,
        earlier: &'static str,
        later: &'static str,
    },
    DurationAtMost {
        label: &'static str,
        earlier: &'static str,
        later: &'static str,
        maximum_seconds: i64,
    },
}

impl DeterministicCheck {
    fn evaluate(
        self,
        scenario_id: &str,
        ready: &ReadyAction,
        evidence: &ShaclEvidenceBundle,
    ) -> ExampleResult<(&'static str, bool)> {
        let number = |predicate| evidence_number(evidence, scenario_id, predicate);
        let almost_equal = |left: f64, right: f64| (left - right).abs() <= 1e-9;
        Ok(match self {
            Self::Boolean {
                label,
                predicate,
                expected,
            } => (
                label,
                evidence_boolean(evidence, scenario_id, predicate)? == expected,
            ),
            Self::Iri {
                label,
                predicate,
                expected,
            } => (
                label,
                evidence_iri(evidence, scenario_id, predicate)? == qualify(scenario_id, expected),
            ),
            Self::Literal {
                label,
                predicate,
                expected,
            } => (
                label,
                evidence_literal(evidence, scenario_id, predicate)? == expected,
            ),
            Self::IriEqualsSlot {
                label,
                predicate,
                slot,
            } => (
                label,
                evidence_iri(evidence, scenario_id, predicate)? == slot_iri(ready, slot)?,
            ),
            Self::NumberEqualsSlot {
                label,
                predicate,
                slot,
            } => (
                label,
                almost_equal(number(predicate)?, slot_integer(ready, slot)? as f64),
            ),
            Self::NumberAtLeastSlot {
                label,
                predicate,
                slot,
            } => (
                label,
                number(predicate)? >= slot_integer(ready, slot)? as f64,
            ),
            Self::NumberAtMostSlot {
                label,
                predicate,
                slot,
            } => (
                label,
                number(predicate)? <= slot_integer(ready, slot)? as f64,
            ),
            Self::NumberAtLeast {
                label,
                predicate,
                minimum,
            } => (label, number(predicate)? >= minimum),
            Self::NumberAtMost {
                label,
                predicate,
                maximum,
            } => (label, number(predicate)? <= maximum),
            Self::NumberWithin {
                label,
                predicate,
                minimum,
                maximum,
            } => {
                let observed = number(predicate)?;
                (label, observed >= minimum && observed <= maximum)
            }
            Self::NumbersEqual { label, left, right } => {
                (label, almost_equal(number(left)?, number(right)?))
            }
            Self::NumberAtMostProperty { label, left, right } => {
                (label, number(left)? <= number(right)?)
            }
            Self::NumberAtLeastProperty { label, left, right } => {
                (label, number(left)? >= number(right)?)
            }
            Self::NumberBetweenProperties {
                label,
                value,
                minimum,
                maximum,
            } => {
                let value = number(value)?;
                (
                    label,
                    value >= number(minimum)? && value <= number(maximum)?,
                )
            }
            Self::SumEquals {
                label,
                left,
                right,
                sum,
            } => (
                label,
                almost_equal(number(left)? + number(right)?, number(sum)?),
            ),
            Self::ProductEquals {
                label,
                left,
                right,
                product,
            } => (
                label,
                almost_equal(number(left)? * number(right)?, number(product)?),
            ),
            Self::DifferenceEquals {
                label,
                minuend,
                subtrahend,
                difference,
            } => (
                label,
                almost_equal(number(minuend)? - number(subtrahend)?, number(difference)?),
            ),
            Self::BasisPointVarianceAtMost {
                label,
                baseline,
                observed,
                tolerance_basis_points,
            } => {
                let baseline = number(baseline)?;
                (
                    label,
                    baseline > 0.0
                        && (number(observed)? - baseline).abs() * 10_000.0
                            <= baseline * number(tolerance_basis_points)?,
                )
            }
            Self::ScaledDifferenceCovers {
                label,
                capacity,
                upper_percent,
                lower_percent,
                required,
            } => (
                label,
                number(required)? * 100.0
                    <= number(capacity)? * (number(upper_percent)? - number(lower_percent)?),
            ),
            Self::ProductAtMostProduct {
                label,
                left_a,
                left_b,
                right_a,
                right_b,
            } => (
                label,
                number(left_a)? * left_b <= number(right_a)? * number(right_b)?,
            ),
            Self::DateTimeBefore {
                label,
                earlier,
                later,
            } => (
                label,
                evidence_datetime(evidence, scenario_id, earlier)?
                    < evidence_datetime(evidence, scenario_id, later)?,
            ),
            Self::DurationAtMost {
                label,
                earlier,
                later,
                maximum_seconds,
            } => {
                let earlier = evidence_datetime(evidence, scenario_id, earlier)?;
                let later = evidence_datetime(evidence, scenario_id, later)?;
                let duration = later - earlier;
                (
                    label,
                    !duration.is_negative() && duration.whole_seconds() <= maximum_seconds,
                )
            }
        })
    }
}

fn qualify(scenario_id: &str, local_or_iri: &str) -> String {
    if local_or_iri.contains(':') {
        local_or_iri.to_owned()
    } else {
        format!("urn:agent-calculus:{scenario_id}:{local_or_iri}")
    }
}

fn evidence_term<'a>(
    evidence: &'a ShaclEvidenceBundle,
    scenario_id: &str,
    predicate: &str,
) -> ExampleResult<&'a EvidenceTerm> {
    let predicate = qualify(scenario_id, predicate);
    let values = evidence
        .claims
        .get(&predicate)
        .ok_or_else(|| io::Error::other(format!("evidence lacks <{predicate}>")))?;
    let [value] = values.as_slice() else {
        return Err(io::Error::other(format!(
            "evidence predicate <{predicate}> must have exactly one value, got {}",
            values.len()
        ))
        .into());
    };
    Ok(value)
}

fn evidence_boolean(
    evidence: &ShaclEvidenceBundle,
    scenario_id: &str,
    predicate: &str,
) -> ExampleResult<bool> {
    let EvidenceTerm::Literal { lexical, .. } = evidence_term(evidence, scenario_id, predicate)?
    else {
        return Err(
            io::Error::other(format!("evidence <{predicate}> is not a boolean literal")).into(),
        );
    };
    lexical.parse().map_err(|error| {
        io::Error::other(format!("invalid boolean evidence <{predicate}>: {error}")).into()
    })
}

fn evidence_number(
    evidence: &ShaclEvidenceBundle,
    scenario_id: &str,
    predicate: &str,
) -> ExampleResult<f64> {
    let EvidenceTerm::Literal { lexical, .. } = evidence_term(evidence, scenario_id, predicate)?
    else {
        return Err(io::Error::other(format!("evidence <{predicate}> is not numeric")).into());
    };
    lexical.parse().map_err(|error| {
        io::Error::other(format!("invalid numeric evidence <{predicate}>: {error}")).into()
    })
}

fn evidence_iri<'a>(
    evidence: &'a ShaclEvidenceBundle,
    scenario_id: &str,
    predicate: &str,
) -> ExampleResult<&'a str> {
    let EvidenceTerm::Iri { value } = evidence_term(evidence, scenario_id, predicate)? else {
        return Err(io::Error::other(format!("evidence <{predicate}> is not an IRI")).into());
    };
    Ok(value)
}

fn evidence_literal<'a>(
    evidence: &'a ShaclEvidenceBundle,
    scenario_id: &str,
    predicate: &str,
) -> ExampleResult<&'a str> {
    let EvidenceTerm::Literal { lexical, .. } = evidence_term(evidence, scenario_id, predicate)?
    else {
        return Err(io::Error::other(format!("evidence <{predicate}> is not a literal")).into());
    };
    Ok(lexical)
}

fn evidence_datetime(
    evidence: &ShaclEvidenceBundle,
    scenario_id: &str,
    predicate: &str,
) -> ExampleResult<OffsetDateTime> {
    let lexical = evidence_literal(evidence, scenario_id, predicate)?;
    OffsetDateTime::parse(lexical, &Rfc3339).map_err(|error| {
        io::Error::other(format!("invalid dateTime evidence <{predicate}>: {error}")).into()
    })
}

#[derive(Debug)]
pub struct ConfiguredScenario {
    pub id: &'static str,
    pub title: &'static str,
    pub assets: DomainAssets,
    pub actor: &'static str,
    pub source: &'static str,
    pub turns: &'static [&'static str],
    pub rejection: RejectionProbe,
    pub action_id: &'static str,
    pub expected_slots: &'static [ExpectedSlot],
    pub class_checks: &'static [ClassCheckSpec],
    pub role_checks: &'static [RoleCheckSpec],
    pub policy_id: &'static str,
    pub deterministic_checks: &'static [DeterministicCheck],
    pub policy_details_json: &'static str,
    pub effect: EffectSpec,
    pub effect_details_json: &'static str,
}

impl ConfiguredScenario {
    fn resolve(resource: ResourceRef, ready: &ReadyAction) -> ExampleResult<&str> {
        match resource {
            ResourceRef::Actor => Ok(ready.principal.actor.as_str()),
            ResourceRef::Slot(slot) => slot_iri(ready, slot),
            ResourceRef::Constant(value) => Ok(value),
        }
    }
}

impl Scenario for ConfiguredScenario {
    fn id(&self) -> &'static str {
        self.id
    }

    fn title(&self) -> &'static str {
        self.title
    }

    fn assets(&self) -> DomainAssets {
        self.assets
    }

    fn actor(&self) -> &'static str {
        self.actor
    }

    fn source(&self) -> &'static str {
        self.source
    }

    fn turns(&self) -> &'static [&'static str] {
        self.turns
    }

    fn rejection_probe(&self) -> RejectionProbe {
        self.rejection
    }

    fn formal_queries(&self, ready: &ReadyAction) -> ExampleResult<Vec<NamedSroiqQuery>> {
        let mut queries = Vec::with_capacity(self.class_checks.len() + self.role_checks.len());
        for check in self.class_checks {
            queries.push(class_check(
                check.label,
                Self::resolve(check.resource, ready)?,
                check.class_iri,
            ));
        }
        for check in self.role_checks {
            queries.push(role_check(
                check.label,
                Self::resolve(check.subject, ready)?,
                check.role_iri,
                Self::resolve(check.object, ready)?,
            ));
        }
        Ok(queries)
    }

    fn evaluate_policy(
        &self,
        ready: &ReadyAction,
        evidence: &ShaclEvidenceBundle,
    ) -> ExampleResult<PolicyReport> {
        let manifest: DomainManifest = serde_json::from_str(self.assets.manifest_json)?;
        let expected_action = manifest
            .actions
            .get(self.action_id)
            .ok_or_else(|| io::Error::other("configured action is absent from the manifest"))?;
        let expected_evidence_digest =
            digest_json(&Value::String(self.assets.evidence.data_turtle.into()));
        let mut checks = vec![
            (
                "authenticated principal is exact",
                ready.principal.actor == self.actor,
            ),
            (
                "compiled action is exact",
                ready.action_id == self.action_id,
            ),
            (
                "compiled action IRI is exact",
                ready.action.action_iri == expected_action.action_iri,
            ),
            (
                "compiled capability class is exact",
                ready.action.capability_class_iri == expected_action.capability_class_iri,
            ),
            (
                "connector evidence is proven",
                evidence.verdict == FormalVerdict::Proven
                    && evidence.oracle_id == self.assets.evidence.oracle_id,
            ),
            (
                "connector snapshot digest is exact",
                evidence.data_digest == expected_evidence_digest,
            ),
        ];
        for expected in self.expected_slots {
            checks.push((expected.slot(), expected.matches(ready)?));
        }
        for check in self.deterministic_checks {
            checks.push((*check).evaluate(self.id, ready, evidence)?);
        }
        let details = json!({
            "domain_summary": serde_json::from_str::<Value>(self.policy_details_json)?,
            "evidence_focus_node": evidence.focus_node,
            "evidence_claims_digest": digest_json(&serde_json::to_value(&evidence.claims)?),
        });
        Ok(policy_report(self.policy_id, checks, details))
    }

    fn effect_spec(&self) -> EffectSpec {
        self.effect
    }

    fn effect_parameters(&self, ready: &ReadyAction) -> ExampleResult<Value> {
        let mut slots = Map::new();
        for expected in self.expected_slots {
            let slot = expected.slot();
            let selected = ready
                .interpretation
                .slots
                .get(slot)
                .ok_or_else(|| io::Error::other(format!("missing selected slot '{slot}'")))?;
            slots.insert(
                slot.into(),
                serde_json::to_value(&selected.candidate.value)?,
            );
        }
        Ok(json!({
            "actor": ready.principal.actor,
            "action": ready.action_id,
            "slots": slots,
            "proposal": serde_json::from_str::<Value>(self.effect_details_json)?,
        }))
    }
}
