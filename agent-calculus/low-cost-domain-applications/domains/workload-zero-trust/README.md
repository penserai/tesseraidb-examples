# Workload zero-trust authorization

This pack lets the attested `inventory-api` request exactly `GET availability`
from `stock-api` in production `us-east-1` for ten minutes. The vocabulary is
closed; POST, mutation, admin, wildcard, and long-lived scopes reject before
System One.

Signed workload-attestation evidence covers SPIFFE identities, SVID validity,
deployment and policy digests, issuer health, nonce, endpoint, method, and
expiry. SROIQ proves the caller-to-target and target-to-endpoint capability
graph. Deterministic policy bounds freshness and TTL. The effect proposes an
ephemeral grant while `credential_or_mesh_policy_issued` remains false.
