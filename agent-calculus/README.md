# Agent Calculus customer examples

These examples are customer-side applications built against the supported
Tesserai Agent Calculus libraries and formal-reasoning backends. They contain
domain manifests, ontologies, SHACL shapes, connector fixtures, and application
orchestration only.

The Agent Calculus runtime, provider adapters, SROIQ implementation, and other
Tesserai internals are intentionally not included. A Tesserai customer
distribution that provides the `0.1.0` packages declared in `Cargo.toml` is
required to compile the examples.

All checked-in effects are simulations. Replace fixtures only with authenticated
customer connectors and preserve the same proof and policy boundaries when
integrating an external system.

## Application suite

[`low-cost-domain-applications`](low-cost-domain-applications/) contains a
shared, proof-revalidating runner and seventeen realistic domain packs for
micro-decision-scale automation. Each pack owns its manifest, closed SHACL
request and connector-evidence shapes, SROIQ ontology, deterministic policy,
multi-turn conversation, rejection probe, and simulation-only effect.

Run every pack without a model server:

```bash
cargo run --manifest-path agent-calculus/Cargo.toml \
  -p agent-calculus-example-low-cost-domain-applications -- --all --replay
```

Each subdirectory is an independently runnable workspace package. Examples are
intended to show a complete evidence flow, not just an isolated provider call.

| Example | System One | Generative model | Formal module | Effect |
|---|---|---|---|---|
| [`checkout-incident`](checkout-incident/) | Triage the likely failure domain | Produce a structured operator brief | Certify a fixed production-safe read-only diagnostic | Return a mock health snapshot |
| [`jit-production-access`](jit-production-access/) | Select only harvested intent/slot candidate IDs across two turns | None in control | SHACL request coverage, then SROIQ requester/capability/tool proofs | Return a proof-bound simulated lease receipt |
| [`wind-turbine-safe-stop`](wind-turbine-safe-stop/) | Resolve only harvested asset/action/reason/work-order candidates | None in control | SHACL request and telemetry coverage, SROIQ capability proofs, deterministic freshness/threshold policy | Return a proof-bound simulated SCADA receipt; send no physical command |

Every example provides a deterministic `--replay` mode for CI and a live mode
for the providers configured in the customer environment.

The two domain-session examples deliberately omit ordinary completion. Unknown
or unregistered identifiers, unmatched meaningful text, and domain-authored
forbidden patterns reject before a System-One call. Each example has one
authoritative `domain/manifest.json`; Clef can select only opaque choices
issued from that manifest for the current turn.
