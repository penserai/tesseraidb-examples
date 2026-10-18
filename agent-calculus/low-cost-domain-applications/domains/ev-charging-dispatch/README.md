# Fleet EV charging dispatch

This pack proposes an off-peak 35 kWh charge for `VAN-042` at `EVSE-17`.
Signed telemetry supplies state of charge, battery capacity, charger power,
grid headroom, tariff, time window, route reserve, connector compatibility,
availability, and interlock health.

SROIQ proves fleet/depot/vehicle/charger/tariff relationships. Rust computes
battery headroom and charge time, then checks grid, price, route, connector,
interlock, and freshness bounds. Grid, route, or interlock overrides reject
before System One. No physical command is sent and
`physical_charge_command_sent` is false.
