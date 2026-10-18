# Checkout incident responder

This example models the first minute of a production checkout incident. The
input describes widespread payment authorization failures without a matching
deployment. Agent Calculus divides the work by epistemic role:

1. **Clef / System One** triages the likely failure domain in one typed
   decision call.
2. A **confidence guard** rejects an ambiguous route.
3. **SROIQ** certifies that the fixed `checkout-health-snapshot` capability is a
   production-safe read-only diagnostic. It does not reason over Clef's dynamic
   output; that output is linked as explicit provenance and a sequencing gate.
4. A proof-gated **mock diagnostic** returns an observed health snapshot. Its
   executor verifies that the proof and payload name the same tool IRI.
5. **Qwen** turns the incident, triage, proof, and diagnostic receipt into a
   structured operator brief. The brief remains proposed evidence and
   authorizes nothing.

The example deliberately makes the least-privilege split visible: probabilistic
evidence may support a fixed read-only investigation after meeting policy
thresholds, but it cannot authorize a mutating production change. The
confidence threshold is calibrated to `0.85` for this exact triage question;
the independent choice-margin threshold is `0.40`.

## Run locally

The live mode expects Ollama at `http://127.0.0.1:11434`, with `clef:latest`
for typed decisions and `qwen2.5:14b` for ordinary completion:

```bash
cargo run --manifest-path agent-calculus/Cargo.toml \
  -p agent-calculus-example-checkout-incident
```

Use deterministic replay without Ollama:

```bash
cargo run --manifest-path agent-calculus/Cargo.toml \
  -p agent-calculus-example-checkout-incident -- --replay
```

Model tags, Ollama URL, and the cold-load-aware deadline are configurable with
`--decision-model`, `--completion-model`, `--ollama-url`, and `--deadline-ms`.
