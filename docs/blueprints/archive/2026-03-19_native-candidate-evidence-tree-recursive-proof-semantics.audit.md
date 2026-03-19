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
| 2026-03-19 | draft | Capture contract narrowed to structured edges | Froze the next discussion line around `rule_ref_edges + legacy rule_refs`: recursive proof must use per-occurrence structured edges keyed by `ruleref_atom_key`, not flat rule-id lists. The upstream substrate output also needs to widen beyond `bindings + rule_refs`. |
| 2026-03-19 | draft | Terminal semantics and branch constraint clarified | Recorded that recursive terminal nodes must distinguish `unresolved_support` from traversal boundaries such as `cycle` and `depth_limit`, and that multi-branch `RuleRef` child edges remain conservative until winning-branch semantics are explicitly designed. |
| 2026-03-19 | draft | DTO shapes frozen for next discussion round | Froze the concrete first-round DTO targets: `SupportArtifact.rule_ref_edges` as binding-scoped structured edges, and widened `NativeWhereEvaluation.rule_ref_resolutions` as occurrence-scoped row-support carriers that let `_evaluate.py` derive those edges without pushing selection logic into tree rendering. |
| 2026-03-19 | draft | Matching and unresolved enum frozen | Froze a deterministic `row_terms` exact-match rule for deriving binding-scoped edges, and kept `unresolved_reason` narrow: only capture-side `child_support_unavailable` belongs on row-support / edge DTOs, while `artifact_missing`, `cycle`, and `depth_limit` remain tree-level terminal reasons. |
| 2026-03-19 | scoped | Scope freeze completed | Scoped freeze confirmed after settling the recursive proof carrier around `rule_ref_edges + legacy rule_refs`, widened `NativeWhereEvaluation.rule_ref_resolutions`, exact tuple matching, narrow `unresolved_reason`, and explicit separation between capture-side unresolved edges and tree-level terminal reasons. |
| 2026-03-19 | implemented | Recursive proof implementation completed | Landed widened substrate DTOs, binding-scoped `rule_ref_edges`, recursive `candidate_evidence_tree` expansion via `child_support_digest`, explicit `unresolved_support` / `recursion_boundary` nodes, runtime/audit/static consumer updates, and targeted tests covering resolved, unresolved, zero-match, and duplicate-match paths. |

## Decision Notes

- 2026-03-19
  - Direction rule: after `native candidate evidence tree v2`, the next discussion line should stay inside `native + candidate + tree`, rather than expanding into graph, engine parity, or value semantics.
- 2026-03-19
  - Reference rule: `docs/references/external/rainbird-evidence-chain-compare.md` is adopted only as design guidance for result-centric entry, recursive tree thinking, and multi-surface delivery; it does not define project truth.
- 2026-03-19
  - Scope rule: the first thing to freeze is not implementation detail, but the recursive carrier boundary, stop conditions, and whether current native support capture can actually supply the needed proof edges.
- 2026-03-19
  - Dependency rule: answers to the recursive tree questions are gated by what native capture can actually emit. First-round recursion should only freeze once capture can stably provide occurrence-aware structured edges, at least reaching `ruleref_atom_key + rule_ref_id + rule_ref_version + child_support_digest`; otherwise capture must be fixed first and recursion remains deferred.
- 2026-03-19
  - Blocker rule: the capture review shows a deeper blocker than `rule_refs=()`. Native derivation currently cannot execute `RuleRef` in the formal `Store.evaluate(...)` path, and runtime derivation evaluation does not thread `RuleRegistry` into that path. Therefore this blueprint must stay `draft` until the team decides whether to extend native derivation execution to support referenced child proofs.
- 2026-03-19
  - Updated blocker rule: the execution-side prerequisite is now satisfied by the shared native where substrate, but recursive proof still cannot scope-freeze because support capture only exposes direct `rule_refs`, not child-proof handles. The remaining gate is now capture-first, not execution-first.
- 2026-03-19
  - Edge-shape rule: first-round recursive proof should not freeze around flat `rule_refs`. The minimum resolved edge handle must be occurrence-aware and carry `ruleref_atom_key`, `rule_ref_id`, `rule_ref_version`, and `child_support_digest`.
- 2026-03-19
  - Compatibility rule: recursive proof work should add `rule_ref_edges` while keeping legacy `rule_refs` as a compatibility summary field; replacing `rule_refs` in place would create avoidable surface churn in runtime/audit/static consumers.
- 2026-03-19
  - Boundary rule: `child_support_digest` belongs to native capture, not tree rendering. If shared substrate output remains flat, recursive proof still cannot be scoped, even if tree builder nodes are redesigned.
- 2026-03-19
  - DTO rule: first-round should distinguish occurrence-scoped substrate output from binding-scoped support output. `NativeWhereEvaluation.rule_ref_resolutions` carries `row_terms -> child_support_digest` data; `SupportArtifact.rule_ref_edges` carries the single binding-selected edge set that tree consumers read.
- 2026-03-19
  - Matching rule: binding-scoped edge derivation should use exact tuple equality between grounded `ruleref` terms and `row_support.row_terms`. Zero matches emit no edge; multiple matches are a substrate contract violation.
- 2026-03-19
  - Enum rule: `unresolved_reason` should stay capture-local and narrow in the first round. Use `child_support_unavailable` for matched rows that lack a digest; keep readback misses and recursion boundaries out of this enum.
- 2026-03-19
  - Implementation rule: recursive proof now ships on the existing `SupportArtifact` substrate by adding `rule_ref_edges` and `root_result_kind="row"` child artifacts, rather than inventing a parallel proof carrier.
- 2026-03-19
  - Terminal rule: tree traversal may emit `artifact_missing`, `cycle`, and `depth_limit` as explicit terminal node reasons even though capture-side `unresolved_reason` remains limited to `child_support_unavailable`.
