# Runtime consistency

RuntimeMetadataBundle retains one specification/catalog and matching compiler, validator, graph,
retriever, service and execution pool. RuntimeFactory prepares complete resources outside the swap
lock. Preparation failures close new handles and preserve active resources. Fingerprints/model
versions must match.

RuntimeManager reads a protected local publication pointer before pinning. Chat never queries Oracle
dictionary metadata. A request lease keeps one bundle through planning, validation, execution and
response authorization. Retired pools/indexes close after their final request. Shutdown drains leases.
Rollback to a still-leased version creates a separate lease identity to prevent double closure.

Capabilities include bundle version and principal digest. Guards check the durable pointer, current
grants, policy compatibility, quarantine and physical impacts. A worker observing another publication
fails closed until reload. Revocation during execution discards the response. History also uses current
grants and session ownership.

Unchanged catalog/grants/encoder partitions share a reference-counted retriever. Startup reconciles
physical metadata once; polling runs only in an explicitly enabled external process. Tests exercise
concurrent threads, separate repository connections, CLI processes and recovery. Distributed storage,
multi-node HA and production load are unqualified.
