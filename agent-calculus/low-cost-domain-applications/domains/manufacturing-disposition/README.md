# Manufacturing disposition

This pack models release of one serialized hydraulic manifold to assembly from
a registered CMM inspection. The user can name only known part, lot, and report
IDs; tolerance waivers and “ship anyway” requests reject before System One.

Closed request SHACL fixes the selected assets. Independent, closed evidence
SHACL binds the measurement device, calibration, units, dimensions, timestamp,
revision, nonconformance count, digest, and MES/QMS provenance. SROIQ proves
inspector eligibility, part/lot/report relationships, and tool capability.
Deterministic policy checks inclusive tolerances, measurement age, calibration
coverage, revision, digest, and absence of open nonconformances.

The result is a proof-bound simulation receipt with
`external_qms_write_performed: false`; no generative model controls release.
