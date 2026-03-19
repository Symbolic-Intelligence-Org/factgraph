# Task Blueprint Audit: Native Candidate Evidence Tree Recursive Proof Semantics

- Blueprint: [2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md](./2026-03-19_native-candidate-evidence-tree-recursive-proof-semantics.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Opened a narrow next-stage blueprint to evaluate `recursive proof semantics` as the first capability line after native candidate evidence tree v2, using Rainbird only as an external design reference rather than implementation truth. |
| 2026-03-19 | draft | Review constraint added | Incorporated the explicit dependency between the recursive tree contract and the native capture gap, requiring the first scoped freeze to verify a minimal child-proof edge handle instead of silently shipping placeholder-only recursion. |
| 2026-03-19 | draft | Execution blocker confirmed | Confirmed that the current native derivation path not only emits `rule_refs=()`, but also rejects `ruleref` in `where_eval` and does not thread registry-backed rule resolution through `Store.evaluate(...)`. This means the current blocker is execution-plus-capture, not capture-only. |
| 2026-03-19 | draft | Upstream substrate blueprint linked | Recorded that the next prerequisite is now tracked in a separate `native where RuleRef execution substrate` draft, with `query + derivation` as the first-round owners. |
| 2026-03-19 | draft | Blocker narrowed after upstream implementation | The upstream `native where RuleRef execution substrate` is now implemented for `query + derivation`, so the remaining blocker for recursive proof work is no longer execution. The blueprint stays `draft` because capture still cannot emit `rule_ref_id + child_support_digest`, and multi-branch child-proof semantics remain deferred. |

## Decision Notes

- 2026-03-19
  - Direction rule: after `native candidate evidence tree v2`, the next discussion line should stay inside `native + candidate + tree`, rather than expanding into graph, engine parity, or value semantics.
- 2026-03-19
  - Reference rule: `docs/references/external/rainbird-evidence-chain-compare.md` is adopted only as design guidance for result-centric entry, recursive tree thinking, and multi-surface delivery; it does not define project truth.
- 2026-03-19
  - Scope rule: the first thing to freeze is not implementation detail, but the recursive carrier boundary, stop conditions, and whether current native support capture can actually supply the needed proof edges.
- 2026-03-19
  - Dependency rule: answers to the recursive tree questions are gated by what native capture can actually emit. First-round recursion should only freeze once capture can stably provide at least `rule_ref_id + child_support_digest`; otherwise capture must be fixed first and recursion remains deferred.
- 2026-03-19
  - Blocker rule: the capture review shows a deeper blocker than `rule_refs=()`. Native derivation currently cannot execute `RuleRef` in the formal `Store.evaluate(...)` path, and runtime derivation evaluation does not thread `RuleRegistry` into that path. Therefore this blueprint must stay `draft` until the team decides whether to extend native derivation execution to support referenced child proofs.
- 2026-03-19
  - Updated blocker rule: the execution-side prerequisite is now satisfied by the shared native where substrate, but recursive proof still cannot scope-freeze because support capture only exposes direct `rule_refs`, not child-proof handles. The remaining gate is now capture-first, not execution-first.
