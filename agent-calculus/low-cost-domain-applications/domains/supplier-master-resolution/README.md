# Supplier-master resolution

This pack models a reversible link from staged supplier `STG-9012` to one
existing canonical supplier. Closed harvesters resolve the record, legal-name
token, VAT, location, and operation; merge, deletion, overwrite, and bank-data
requests reject before System One.

Closed SHACL validates the request and independent ERP registry evidence,
including both legal identities, country/VAT/address matches, source and target
states, match score, unique-match count, bank-conflict flag, snapshot, and
timestamp. SROIQ proves steward assignment, case scope, supplier approval,
location, reversible operation, and resolver authority. Deterministic policy
owns equality, uniqueness, score, freshness, and link-only checks.

The effect only emits a proof-bound proposal with `master_data_mutated: false`;
records are not merged and bank data is never changed.
