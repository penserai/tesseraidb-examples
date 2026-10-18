# SecOps endpoint containment

This pack models a Tier-2 analyst proposing 30-minute EDR network isolation of
one managed endpoint for a correlated critical incident. Signed SIEM and EDR
evidence supplies confidence, independent signal count, sensor health,
criticality, exception, and break-glass state.

SROIQ proves analyst assignment, alert-to-incident and alert-to-host links,
segment membership, and executor authority. Deterministic policy permits only
reversible single-host isolation. Wipe, reimage, account disablement, or
whole-network blocking rejects before System One. No EDR command is sent and
`host_or_network_changed` is false.
