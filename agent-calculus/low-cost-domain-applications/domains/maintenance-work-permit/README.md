# Industrial maintenance work permit

This pack stages a permit-to-work proposal for mechanical-seal replacement on
pump `P-17`. Signed safety evidence records all four isolations, two LOTO
signatures, zero residual energy, a calibrated atmospheric test, PPE,
equipment state, concurrency exclusions, and permit revision.

SROIQ proves technician assignment, work-order scope, asset location, permit
governance, and planner authority. Rust evaluates the zero-energy and gas
thresholds. Requests to skip LOTO or gas testing, energize, or start equipment
reject before System One. No permit is activated and no equipment is
commanded; `external_permit_activation_performed` is false.
