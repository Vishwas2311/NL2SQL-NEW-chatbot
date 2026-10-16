# Change impact matrix

| Change | Active behavior | Candidate/approval |
|---|---|---|
| Ordinary rows | Current authorized rows queried | No schema/index rebuild |
| New table/column/FK | No new metric, edge or permission | Pending review; unchanged artifacts reused |
| Comment/synonym | Approved meanings stay active | Reviewed retrieval update |
| Type/precision/nullability/key/removal | Dependent views quarantined | Reconcile before publication |
| View/metric/grain/time rule | Old semantics retained unless physically broken | Review and rebuild/check |
| Grants/policy | Current grants checked every turn/capability | Security review; rollback cannot restore access |
| Ambiguous/unverified join | Plan refused | Resolve evidence and grain |
| Graph/index/runtime failure | Active pointer/resources retained | Candidate never activates |
| Source change during activation | Transaction rejected | Rediscover and review |
| Lease expiry/CAS conflict | Stale worker rejected | Retry current revision |

Saved-plan consumers are invalidated by catalog/policy proofs; a separate enterprise report scheduler
is not implemented. Removed sources remain traceable through old mappings. Proposed grant changes
mark consumers for revalidation without disabling the currently approved bundle.
