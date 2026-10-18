# Building demand response

This pack proposes a one-degree, 30-minute setback for `ZONE-4E` during a
verified grid event. Signed BMS evidence supplies occupancy, comfort bounds,
temperature, humidity, CO2, protected-load state, interlocks, and load
forecast.

SROIQ proves the operator/building/zone/air-handler/event graph. Rust verifies
the projected setpoint, indoor-air-quality bounds, life-safety state, and event
cap. Requests to bypass ventilation, comfort, fire safety, or interlocks stop
before System One. This example never commands a BMS and reports
`physical_bms_command_sent: false`.
