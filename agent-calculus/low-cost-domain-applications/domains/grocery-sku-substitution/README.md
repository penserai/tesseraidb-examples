# Grocery SKU substitution

This pack proposes `SKU-2007` as the registered substitute for `SKU-1001` on
one active order line. Signed store data supplies consent, dietary preference,
vegan certification, milk and peanut exclusions, seal and barcode checks,
stock, prices, package size, and freshness.

Positional closed lookups distinguish requested and substitute SKUs. SROIQ
proves the picker/store/order/preference/substitute/certification graph. Rust
checks inventory, price delta, package equivalence, and freshness. Allergen or
consent bypass rejects before System One. The proposal leaves
`order_line_modified` false.
