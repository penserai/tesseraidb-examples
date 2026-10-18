#![forbid(unsafe_code)]

use agent_calculus::SystemOneProvider;
use agent_calculus_example_low_cost_domain_applications::{
    CandidateOnlyReplay, all_scenarios, run_scenario,
};
use agent_calculus_ollama::{DEFAULT_BASE_URL, DEFAULT_DECISION_MODEL, OllamaSystemOneProvider};
use clap::Parser;
use serde_json::json;
use std::error::Error;
use std::io;
use std::sync::Arc;

#[derive(Debug, Parser)]
#[command(about = "Run realistic low-cost Agent Calculus domain applications")]
struct Args {
    /// List the installed application IDs.
    #[arg(long)]
    list: bool,
    /// Run every installed application.
    #[arg(long)]
    all: bool,
    /// Run one application by ID.
    #[arg(long)]
    scenario: Option<String>,
    /// Use deterministic closed-choice replay instead of local Ollama Clef.
    #[arg(long)]
    replay: bool,
    /// Ollama decision model tag.
    #[arg(long, default_value = DEFAULT_DECISION_MODEL)]
    decision_model: String,
    /// Base URL of the Ollama server.
    #[arg(long, default_value = DEFAULT_BASE_URL)]
    ollama_url: String,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error + Send + Sync>> {
    let args = Args::parse();
    let scenarios = all_scenarios();
    if args.list {
        for scenario in scenarios {
            println!("{}\t{}", scenario.id(), scenario.title());
        }
        return Ok(());
    }

    if args.all && args.scenario.is_some() {
        return Err(io::Error::other("--all and --scenario are mutually exclusive").into());
    }
    if !args.all && args.scenario.is_none() {
        return Err(io::Error::other("choose --all, --scenario <id>, or --list").into());
    }
    let selected = if let Some(id) = args.scenario.as_deref() {
        vec![
            scenarios
                .into_iter()
                .find(|scenario| scenario.id() == id)
                .ok_or_else(|| io::Error::other(format!("unknown scenario '{id}'")))?,
        ]
    } else {
        scenarios
    };

    let mut reports = Vec::with_capacity(selected.len());
    for scenario in selected {
        let provider: Arc<dyn SystemOneProvider> = if args.replay {
            Arc::new(CandidateOnlyReplay::default())
        } else {
            Arc::new(OllamaSystemOneProvider::with_base_url(
                &args.ollama_url,
                &args.decision_model,
            ))
        };
        reports.push(
            run_scenario(
                scenario,
                provider,
                if args.replay { "replay" } else { "ollama-clef" },
            )
            .await?,
        );
    }

    let output = if reports.len() == 1 {
        reports.pop().expect("one report")
    } else {
        let system_one_calls = reports
            .iter()
            .filter_map(|report| report["system_one_calls"].as_u64())
            .sum::<u64>();
        let cost_microusd = reports
            .iter()
            .filter_map(|report| report["usage"]["cost_microusd"].as_u64())
            .sum::<u64>();
        json!({
            "suite": "low-cost-domain-applications",
            "scenario_count": reports.len(),
            "system_one_calls": system_one_calls,
            "generative_calls": 0,
            "reported_cost_microusd": cost_microusd,
            "reports": reports
        })
    };
    println!("{}", serde_json::to_string_pretty(&output)?);
    Ok(())
}
