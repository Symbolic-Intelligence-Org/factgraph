# Task Blueprint Audit: Native Candidate Evidence Tree Richer Unresolved Taxonomy

- Blueprint: [2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.md](./2026-03-19_native-candidate-evidence-tree-richer-unresolved-taxonomy.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Opened a narrow capability-decision blueprint for richer unresolved / boundary taxonomy after recursive proof and winning-branch implementation, with scope explicitly limited to terminal reason classification and ownership. |
| 2026-03-19 | draft | First-round freeze positions written back | Recorded the narrow first-round taxonomy stance: keep the current four reasons, preserve the `unresolved_support` / `recursion_boundary` split, freeze owner layers, require shared raw enums across consumers, and keep legacy fallback outside recursive terminal taxonomy. |
| 2026-03-19 | scoped | Scope freeze completed | Scoped freeze confirmed after fixing the first-round reason set, node-kind split, owner layers, shared raw-enum rule, and legacy fallback boundary. |
| 2026-03-19 | implemented | Contract promotion completed | Confirmed that code already matched the scoped taxonomy contract, updated core/service/audit module docs to promote it from implementation detail to formal contract, and closed the blueprint without a separate implementation child blueprint. |

## Decision Notes

- 2026-03-19
  - Scope rule: this blueprint is not a continuation of winning-branch, execution substrate, or recursive DTO design. It starts from the implemented recursive proof tree and only discusses unresolved / boundary taxonomy.
- 2026-03-19
  - Reality rule: the current live surface is already split across capture-side `child_support_unavailable` and tree-side `artifact_missing` / `cycle` / `depth_limit`. Any taxonomy freeze must account for both existing owners rather than pretending all reasons originate in one layer.
- 2026-03-19
  - Boundary rule: fail-fast capture violations such as no-satisfying-branch or duplicate row-support match are explicitly out of scope. This blueprint only covers terminal semantics that are represented inside the candidate evidence tree.
- 2026-03-19
  - Taxonomy scope rule: first-round should freeze only the current four live reasons: `child_support_unavailable`, `artifact_missing`, `cycle`, and `depth_limit`. New enums should not be invented before current live surface is formalized.
- 2026-03-19
  - Node-kind rule: `unresolved_support` and `recursion_boundary` are not interchangeable terminal wrappers. The former means “wanted to continue but child support was unavailable,” while the latter means traversal deliberately stopped.
- 2026-03-19
  - Owner rule: `child_support_unavailable` remains capture-owned, `artifact_missing` is lookup/readback-owned, and `cycle` / `depth_limit` are traversal-owned. `artifact_missing` must not be reframed as capture-owned because capture only emits the digest reference.
- 2026-03-19
  - Consumer rule: runtime / audit / static should share the same raw reason enums and terminal node kinds. Documentation may explain them, but consumers should not invent a second translation layer.
- 2026-03-19
  - Legacy rule: richer unresolved taxonomy applies only to the structured `rule_ref_edges` path. Legacy `rule_refs` fallback continues to emit flat `rule_ref` nodes and does not enter recursive terminal taxonomy.
- 2026-03-19
  - Freeze rule: the blueprint is now scoped. Follow-on work should stay inside unresolved/boundary taxonomy and consumer-contract clarification, and should not reopen winning-branch, execution substrate, or carrier-shape topics without a new scope update.
- 2026-03-19
  - Outcome rule: no separate implementation blueprint was needed. This slice formalized an already-live behavior: the code path already matched the scoped taxonomy, so the remaining work was doc-and-contract promotion plus archive completion.
