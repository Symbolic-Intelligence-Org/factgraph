# Task Blueprint Audit: Engine Candidate Explain-Tree Degraded Node Shape

- Blueprint: [2026-03-19_engine-candidate-explain-tree-degraded-node-shape.md](./2026-03-19_engine-candidate-explain-tree-degraded-node-shape.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Opened a narrow capability-decision blueprint for engine degraded explain-tree shape after native recursive proof, winning-branch narrowing, and richer unresolved taxonomy had already landed. Scope is limited to tree-surface node shape, not full engine witness parity. |
| 2026-03-19 | draft | First-round freeze positions written back | Recorded the narrow first-round degraded-tree stance: return a valid tree instead of unsupported, keep the normal envelope, attach a `degraded_support` node under `support_section`, keep the node fields minimal, and keep engine degraded shape separate from native recursive nodes and unresolved taxonomy. |
| 2026-03-19 | scoped | Scope freeze completed | Scoped freeze confirmed after fixing the degraded tree envelope, the `support_section -> degraded_support` shape, the minimal payload fields, the no-`support_digest` rule, and the legacy `"none"` compatibility boundary. |
| 2026-03-19 | implemented | Degraded tree shape landed | Runtime, audit, and static now accept degraded engine candidates on the tree surface; the dedicated `degraded_support` node was added, focused tests passed, and module docs were synced to the new contract. |

## Decision Notes

- 2026-03-19
  - Scope rule: this blueprint is not reopening full engine witness parity. It only asks what valid tree shape an engine no-witness candidate should return instead of `runtime_explain_not_supported`.
- 2026-03-19
  - Boundary rule: engine degraded candidate must stay separate from native recursive terminal taxonomy. `unresolved_support` and `recursion_boundary` already have frozen meanings and should not be reused as generic no-witness wrappers.
- 2026-03-19
  - Reality rule: the current gap is not runtime-only. Audit query and static candidate evidence generation are also effectively native-only because they reject or fail on non-native `support_kind`.
- 2026-03-19
  - Shape rule: first-round engine degraded candidate should still return a valid `candidate_evidence_tree` envelope, with `candidate_result -> support_section -> degraded_support`.
- 2026-03-19
  - Node rule: `degraded_support` is the new dedicated node kind. Engine no-witness must not be mapped onto `unresolved_support` or `recursion_boundary`.
- 2026-03-19
  - Payload rule: the degraded node should minimally carry `support_kind`, `witness_status="degraded"`, and `children=[]`. It should not expose `support_digest`, because the current zero digest is only a compatibility placeholder and not a real witness handle.
- 2026-03-19
  - Compatibility rule: legacy `"none"` and `engine_no_witness_v1` should be fully isomorphic on the tree surface; the only remaining difference may be the raw `support_kind` value itself.
- 2026-03-19
  - Freeze rule: the blueprint is now scoped. Follow-on work should stay inside engine degraded tree shape and consumer-contract alignment, and should not reopen full engine witness parity, adapter provenance, or native recursive taxonomy without a new scope update.
- 2026-03-19
  - Outcome rule: the slice landed without introducing a new witness carrier. The first-round contract stayed narrow: valid tree envelope, `support_section -> degraded_support`, no node-level `support_digest`, and full isomorphism between legacy `"none"` and `engine_no_witness_v1`.
