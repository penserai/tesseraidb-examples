# Laboratory sample routing

This pack proposes routing serum accession `ACC-2048` to `CHEM-7` for a
potassium assay. Signed LIMS/QC evidence supplies label and custody status,
biosafety level, temperature, analyzer capacity, volume, hemolysis index,
stability window, timestamp, and digest.

SROIQ proves technologist qualification, custody, assay-to-laboratory routing,
analyzer location, and planner authority. Rust applies the quality and timing
thresholds. Custody bypass, specimen discard, result alteration, or biosafety
bypass rejects before System One. The LIMS queue remains untouched and
`laboratory_queue_modified` is false.
