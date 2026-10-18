# Cloud volume hygiene

This pack proposes a 30-day quarantine for one unattached production volume
only after a signed inventory snapshot proves ownership approval, age, cost,
and the existence of an encrypted, replicated, restore-tested snapshot. It
also requires healthy KMS and absence of legal, compliance, or deletion holds.

SROIQ proves operator/account/volume/region/snapshot relationships and planner
authority. Immediate deletion, missing-snapshot, KMS-disable, or retention
bypass requests reject before System One. The output is a recoverable plan;
no cloud API is called and `cloud_resources_mutated` is false.
