# Invoice three-way match

This pack proposes release of invoice `INV-88231` only after the registered
purchase order and goods receipt agree with its vendor, quantities, currency,
unit price, subtotal, tax, and total. A signed ERP snapshot supplies those
facts; user prose cannot manufacture them.

Closed request and evidence SHACL reject missing, extra, or mistyped facts.
SROIQ proves reviewer assignment, vendor identity across documents, receipt to
order linkage, and executor authority. Rust recomputes quantity equality,
arithmetic, tolerance, duplicate, status, tier, and freshness checks. Direct
payment, bank changes, or tolerance bypass reject before System One. The
effect is a proposal and reports `payment_or_erp_mutated: false`.
