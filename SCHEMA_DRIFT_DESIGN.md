# Drift classification

Normalized fingerprints omit observation time and business rows. They retain source identity,
owners, classification, verification, columns, keys, dependencies, definition digests and DDL evidence.
SQLite FK identities use endpoints/pairs rather than unstable PRAGMA sequence numbers.

Classes: compatible physical addition, metadata-only, approval-required addition, breaking physical,
breaking semantic, security-sensitive and unknown. Possible renames remain unverified. Type,
precision, nullability, removal, key, definition, policy and source changes are not assumed harmless.

DependencyGraph links tables -> columns -> relationships/dimensions/metrics -> views -> compiler/
saved-plan consumers, plus retrieval and policies. Physical breaks quarantine affected active views.
A missing account table blocks account/portfolio reports while dated loans still work. Proposed
semantic changes do not mutate active access.

Every candidate requires certification. Unmapped compatible additions retain approved semantics and
reuse artifact references. Row changes update answers without schema/index rebuild. Unknown or
incomplete evidence fails closed for dependent reports.
