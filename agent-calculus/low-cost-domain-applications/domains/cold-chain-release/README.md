# Cold-chain pallet release

This pack releases one registered refrigerated vaccine pallet only after closed
request SHACL, signed logger/custody evidence SHACL, SROIQ relationship proofs,
and deterministic checks of the 2–8 °C envelope, series completeness,
calibration, custody, seal, recall, expiration, digest, and freshness.
Logger bypass requests reject before System One. The proof-bound effect is a
simulation with `external_inventory_transition_performed: false`.
