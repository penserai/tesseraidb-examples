# Administrative healthcare referral

This is deliberately an administrative capability, not a clinical one. It
proposes routing an existing signed routine cardiology referral using active
patient, encounter, facility, payer, consent, coverage, and prior-authorization
records. Diagnosis, prescribing, emergency triage, and symptom interpretation
reject before System One.

Closed EHR/payer evidence proves current consent, eligibility, authorization,
network participation, facility acceptance, uniqueness, and minimum-necessary
disclosure. SROIQ proves the referral graph and gateway authority. The effect
writes neither the EHR nor payer channel: `ehr_referral_written` and the nested
`payer_submission_sent` value are false.
