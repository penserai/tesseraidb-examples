# Low-cost domain applications

This package demonstrates **ambient formal micro-agency**: one bounded agent
per query, transaction, resource, component, shipment, device interval, or
administrative packet. The examples are intentionally narrow enough that the
normal control path needs no generative model.

Every application uses the same evidence ladder:

```text
authenticated observation
  -> deterministic closed candidate harvesting
  -> one batched System-One decision per natural-language turn
  -> closed SHACL request validation
  -> closed SHACL connector-evidence validation
  -> typed claims parsed from the one proven evidence focus node
  -> SROIQ authorization and relationship proofs
  -> deterministic arithmetic, freshness, and safety policy
  -> certificate-revalidated simulated effect
```

Clef may select only opaque candidate IDs issued for the current turn. A tie or
zero-confidence response is rejected. Clef cannot invent an identifier,
measurement, capability, or action. Qwen is not a dependency of this package
and the reports always record
`"generative_calls": 0`. Unsupported or unmatched language fails before a
provider call.

## Run

List the installed applications:

```bash
cargo run --manifest-path agent-calculus/Cargo.toml \
  -p agent-calculus-example-low-cost-domain-applications -- --list
```

Run the complete deterministic suite:

```bash
cargo run --manifest-path agent-calculus/Cargo.toml \
  -p agent-calculus-example-low-cost-domain-applications -- --all --replay
```

Run one application against local Ollama `clef:latest`:

```bash
cargo run --manifest-path agent-calculus/Cargo.toml \
  -p agent-calculus-example-low-cost-domain-applications -- \
  --scenario data-privacy-query
```

The output contains the request-coverage certificate, connector-evidence
certificate, SROIQ proof bundle, deterministic policy report, and a bound
idempotent receipt. All effects are simulations; each receipt has a
domain-specific field explicitly confirming that no external write, physical
command, clinical decision, payment, or infrastructure mutation occurred.

## Applications

| Application | Economic unit | Simulated safe effect |
|---|---|---|
| Tool-call firewall | Proposed agent tool call | One-use read capability |
| Data-privacy query | Query or protected projection | Governed aggregate plan |
| Supplier master resolution | Staged supplier record | Reversible canonical link |
| Invoice three-way match | Invoice line/workflow transition | Payment-release proposal, never payment |
| Workload zero trust | Service connection | Short-lived path-scoped grant proposal |
| SecOps containment | Correlated alert episode | Reversible single-host isolation proposal |
| Manufacturing disposition | Inspected component | Release/hold record |
| Cold-chain release | Pallet and custody transition | Release/quarantine recommendation |
| Building demand response | Zone/control interval | Bounded setpoint proposal |
| Maintenance work permit | Work order/intervention | Non-actuating permit proposal |
| Healthcare referral | Administrative referral packet | Minimum-necessary submission proposal |
| Cloud-volume hygiene | Cloud resource | Snapshot-backed quarantine plan |
| CI/CD canary | Deployment candidate | Bounded canary authorization |
| EV charging dispatch | Charger/tariff interval | Bounded charging proposal |
| Laboratory routing | Specimen | Analyzer routing proposal |
| Grocery substitution | Unavailable order line | Constrained substitute proposal |
| Accessibility session | Accommodation request | Scoped session configuration |

The repository also has deeper standalone JIT production-access and
wind-turbine safe-stop examples. Together they cover nineteen independently
modeled application loops.

## Trust boundary

SHACL establishes closed structural conformance, not truth. Policies consume
the typed values parsed from the exact SHACL-proven focus node, so changing a
measurement changes the policy result instead of leaving a parallel hard-coded
value behind. Connector authentication, signature verification, provenance,
and a trusted evaluation clock remain ingress responsibilities.
SROIQ establishes positive relationships and classifications, not arithmetic
or default-deny policy. Deterministic Rust owns quantities, time windows,
tolerances, and safety envelopes. The executor reruns all three layers and
compares complete certificates before producing a receipt.

Natural-language continuations are compare-and-swap session cursors, not
authentication. Actor and source identities must come from trusted ingress,
and production session storage must be trusted and access controlled.
