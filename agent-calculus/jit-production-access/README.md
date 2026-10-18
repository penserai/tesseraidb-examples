# Just-in-time production access

This bundle models a closed-domain agent that issues a short-lived,
least-privilege production lease.

1. Deterministic harvesters resolve text to candidate IDs declared by the
   authoritative `domain/manifest.json`.
2. System One may select only an ID supplied in that turn or abstain. It cannot
   invent an IRI, capability, duration, or argument.
3. Selected IDs bind to canonical IRIs and a closed SHACL shape validates the
   request.
4. Every violation code selects a fixed response from that same manifest.
5. Registry connectors supply incident and on-call observations.
6. SROIQ proves requester, capability, and tool classes for the exact request.
7. The executor verifies those bindings before issuing an idempotent lease.

Representative dialogue:

    Operator: I'm covering checkout. Give me prod access in eu-west for INC-4821.
    Agent: Which capability do you need: logs, metrics, a read-only diagnostic,
           production shell, or configuration changes?
    Operator: Logs for half an hour.

Generic “access” is intentionally not a capability candidate. The first turn
therefore reaches SHACL with no capability or duration; its report contains
'jit.capability.required' and 'jit.duration.required', and the session emits a
fixed clarification. The reply yields the explicit 'capability.read-logs' and
'duration.30m' candidates for System One to select in one batched call.

SHACL conformance establishes completeness and domain coverage, not
authorization. The effect also requires proof that the requester is an
'EligibleIncidentResponder', the capability an 'ApprovedJitCapability', and
the tool an 'ApprovedJitLeaseIssuer'. The runnable demo uses a static registry
fixture for the incident assignment; a production connector must refresh that
observation before each session. The executor binds requester, service,
environment, region, incident, capability, duration, and request digest to its
receipt. A production integration must preserve those bindings across the
customer proof service and effect boundary.

Known privileged capabilities such as production shell are in-domain and
shape-valid, but not approved by this ontology. Domain-authored forbidden
capabilities such as cluster-admin hard-reject before System One; unregistered
incident IDs are rejected by a closed lookup before System One as well.

Run the deterministic path with:

    cargo run --manifest-path agent-calculus/Cargo.toml \
      -p agent-calculus-example-jit-production-access -- --replay

Qwen is absent from control. It may optionally render a terminal receipt as
'Proposed' prose, but that output is never re-ingested and authorizes nothing.
