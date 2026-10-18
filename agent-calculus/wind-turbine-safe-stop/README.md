# Wind-turbine safe stop

This bundle models an agent that coordinates a controlled turbine stop while
keeping user claims, SCADA observations, validation, and authorization
separate.

Deterministic harvesters produce only IDs declared by the authoritative
`domain/manifest.json`.
System One selects only candidate IDs supplied in the current turn or abstains.
The ambiguous phrase “shut it down” deliberately yields no action candidate,
so SHACL makes the session ask the fixed 'wind.action.required' question. It
never lets a generative model decide which physical action to take.

    Operator: WT-204 is shaking hard. Shut it down.
    Agent: Confirm the supported stop mode: controlled stop.
    Operator: Controlled stop under WO-7712.

The claimed vibration remains user evidence; it is not SCADA telemetry. This
agent's declared expertise is deliberately narrow: only excess vibration can
authorize this workflow. Other fault classes must route to a different domain
before System One is called. A
connector independently observes registered sensors, timestamps, units, and
calibration records. The runnable demo uses a static connector fixture and
derives freshness from separate observation and evaluation timestamps rather
than trusting a supplied age. The typed observation deterministically produces
the RDF graph, and its SHACL certificate/data digest cross the effect boundary
with the observation. Closed SHACL shapes bind its metric and sensor evidence
to the selected excess-vibration reason. Fixed templates handle violations.

SHACL establishes data completeness, SROIQ proves categorical facts such as
operator eligibility and tool support, and a deterministic policy oracle checks
numeric thresholds and telemetry freshness. None substitutes for another. The
SCADA executor requires all judgments, verifies that actor, asset, action, work
order, telemetry, tool, and request digest match, and returns an idempotent
state-transition receipt. A production integration must preserve those exact
bindings across the customer validation, proof, and effect services.

Unknown assets and unmodeled operator language fail before System One. Sensor
evidence is fetched only after a complete in-domain request, then fails closed
at SHACL/policy validation. Qwen is absent from control; optional terminal
prose is 'Proposed', never re-ingested, and cannot trigger a stop or restart.

Emergency stop is intentionally recognizable but outside this agent's action
set, so that phrase hard-rejects before Clef. It cannot be routed into the
controlled-stop executor.

Run the deterministic path with:

    cargo run --manifest-path agent-calculus/Cargo.toml \
      -p agent-calculus-example-wind-turbine-safe-stop -- --replay
