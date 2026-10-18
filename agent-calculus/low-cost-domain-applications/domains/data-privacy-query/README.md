# Per-query privacy gateway

An authenticated retention analyst asks for one fixed, aggregate view over a
registered EU dataset. The first turn identifies only catalog-owned candidates;
the second supplies the registered purpose, period, aggregation, and mandatory
small-cell protection.

SHACL closes both the request and the independently observed data-catalog
snapshot. SROIQ proves analyst eligibility, dataset and operation
classification, the analyst-to-dataset relation, and gateway capability.
Deterministic policy constructs a fixed aggregate AST, enforces Q3 boundaries,
country-only grouping, `k >= 25`, result and lifetime bounds, and a fresh
catalog snapshot.

The effect is a simulated governed-query capability. It contains no arbitrary
SQL, projects no direct identifier, and does not contact a database.

```bash
cargo run --manifest-path agent-calculus/Cargo.toml \
  -p agent-calculus-example-low-cost-domain-applications -- \
  --scenario data-privacy-query --replay
```
