# Versioning and approval

BundleSpec SHA256 binds inventory, catalog, current principals, artifact fingerprints, impacts and
creation time. Lifecycle status and signed evidence live separately in a private SQLite WAL store.
Source profiles store paths/source identity, never passwords.
The candidate also binds its base publication. Publishing after another activation requires restaging
and fresh review, preventing an older approval from undoing newer revocations. Changed policy
fingerprints require a fresh revision label and matching principal revisions, invalidating saved history.

Lifecycle: pending_verification or pending_approval -> certified -> published -> superseded, with
rejection/retirement. Physical verification is separate evidence. Imported catalog.approved=true is
not publication authority. Three configured roles (physical, business, security) and a separately
authenticated administrator are required. Protected environment keys authenticate local HS256
review/admin evidence. Manifests cannot nominate trust anchors or confer roles. Signatures bind the
candidate, source, reviewer and reference with issuer/audience/time checks.

demo-trust/sign-demo are explicit fictional-synthetic-only commands. They cannot certify company
metadata. Corporate SSO/key distribution, asymmetric-signing policy, external owner approval and
rotation need enterprise integration. Published review evidence may outlive token expiry; revoking
its configured key still blocks verification/recovery.

Publication checks signatures, live physical fingerprints, all artifact versions and runtime readiness,
then rediscovers for concurrent source changes. One transaction compares revision/active ID and
swaps the pointer. A bounded cross-process refresh lease fences expired workers.

Rollback requires a previously published, trusted, physically compatible version with security policy
and grants equal to current. It cannot restore older access. To revert semantics with newer grants,
stage a newly reviewed revision. Restricted storage/OS permissions remain deployment requirements.
