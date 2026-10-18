# Accessibility session configuration

This example configures captions and a high-contrast display for a registered
event session without collecting or inferring a diagnosis. The natural-language
surface can select only a pseudonymous participant, registered session and
room, supported profile, and bounded duration.

The registration connector supplies consent, room, session status, timestamp,
and an opaque snapshot digest. SHACL closes both request and registration
evidence. SROIQ proves coordinator eligibility, registration, profile support,
and tool authority. Deterministic policy caps the duration, requires fresh
consent, excludes life-safety changes, and schedules an automatic revert.

The effect is a simulated presentation-profile reservation. No venue device is
changed, and no medical record or diagnosis enters the model.
