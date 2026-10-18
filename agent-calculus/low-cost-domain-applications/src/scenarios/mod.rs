use crate::Scenario;

mod accessibility_session;
mod building_demand_response;
mod ci_cd_canary;
mod cloud_volume_hygiene;
mod cold_chain_release;
mod configured;
mod data_privacy_query;
mod ev_charging_dispatch;
mod grocery_sku_substitution;
mod healthcare_referral_submit;
mod invoice_three_way_match;
mod laboratory_sample_routing;
mod maintenance_work_permit;
mod manufacturing_disposition;
mod secops_containment;
mod supplier_master_resolution;
mod tool_call_firewall;
mod workload_zero_trust;

pub fn all() -> Vec<&'static dyn Scenario> {
    vec![
        &tool_call_firewall::SCENARIO,
        &data_privacy_query::SCENARIO,
        &supplier_master_resolution::SCENARIO,
        &invoice_three_way_match::SCENARIO,
        &workload_zero_trust::SCENARIO,
        &secops_containment::SCENARIO,
        &manufacturing_disposition::SCENARIO,
        &cold_chain_release::SCENARIO,
        &building_demand_response::SCENARIO,
        &maintenance_work_permit::SCENARIO,
        &healthcare_referral_submit::SCENARIO,
        &cloud_volume_hygiene::SCENARIO,
        &ci_cd_canary::SCENARIO,
        &ev_charging_dispatch::SCENARIO,
        &laboratory_sample_routing::SCENARIO,
        &grocery_sku_substitution::SCENARIO,
        &accessibility_session::SCENARIO,
    ]
}
