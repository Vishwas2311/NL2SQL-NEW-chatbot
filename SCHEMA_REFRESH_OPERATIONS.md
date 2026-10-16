# Refresh operations

Scheduling defaults disabled. An authorized administrator configures 5..86400 seconds, initially with
--dry-run. A separate `metadata monitor` process atomically claims due work. `--once` runs one tick.
API workers never create poller threads. The laptop must remain on; no system service was deployed.

Refresh discovers -> compares -> impacts -> reconciles -> stages. It never auto-approves/publishes.
Retries default to one (ceiling two), only for discovery timeout/unavailability or contention, with
bounded backoff. Logs contain safe IDs/codes, not exception text, comments or credentials. A lease
prevents duplicate work and fences expired workers. Unaffected approved reports remain available.

For a new Oracle column: authorized sync --dry-run; inspect impacts; sync to persist; inspect the
private candidate. Owners decide whether it stays unmapped. For approved business use, supply a
revised semantic file and current grants file, obtain physical/business/security signatures, approve
and publish. Supported mapping changes need no Python rewrite. Unknown semantics need a certified
compiler extension rather than an inferred rule.

Disable scheduling for maintenance. Failed discovery retains the active bundle. A detected physical
break quarantines dependent reports until compatible reviewed publication. Rollback requires physical
compatibility and unchanged policy/grants. See ORACLE_BOOTSTRAP_RUNBOOK.md for commands.
