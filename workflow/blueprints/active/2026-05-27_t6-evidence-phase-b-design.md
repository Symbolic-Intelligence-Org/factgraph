# Task Blueprint: T6 Evidence Phase B Design Skeleton

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: L (design skeleton; may narrow after Step 4.6)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t6-evidence-phase-b-design.audit.md`
- Trigger: Post-T5/T11 roadmap N2. `EvidenceGraph` is shipped as a minimal
  opaque graph, match witness output is explicitly deferred, and T8/T9 depend
  on evidence design sources that can guide implementation and release-facing
  docs without inventing semantics during implementation.

## 0. Scope Locks

### In scope

T6 makes the active evidence design implementable for Phase B. It is a
design-source cycle, not a runtime implementation cycle.

1. **Audit Channel v1 (`evidence-tree-rainbird-style-v1.zh.md` §10)**:
   - replace the skeleton with an implementable v1 audit channel contract;
   - lock the shipped metadata bridge and the durable graph metadata stance;
   - define immutability / hash / signature boundaries for v1 vs v2+;
   - define validator and JSON roundtrip expectations without changing code.
2. **Rendering (`evidence-tree-rainbird-style-v1.zh.md` §11)**:
   - replace the skeleton with a reference-renderer contract;
   - distinguish reference HTML renderers from product UI obligations;
   - lock layout mode matrix, JSON roundtrip, error / empty / large graph
     behavior, and custom UI boundaries.
3. **Deferred Items (`evidence-tree-rainbird-style-v1.zh.md` §14)**:
   - expand D1-D19 with owner candidate, trigger, v1/non-v1 boundary, and
     stop-amend notes;
   - keep failure-side why-not, per-fact ACL, session logs, match witness APIs,
     and engine-specific advanced evidence out of v1 unless a scoped decision
     says otherwise.
4. **T8 implementation split proposal**:
   - add a follow-on split matrix for T8 evidence implementation;
   - separate validator / metadata population, native/Souffle topology, and
     engine-specific enrichments gated by T10 or later cycles.
5. **Cross-reference hygiene**:
   - update the parent rule-expression essay §7 only if needed to point to the
     Phase B design source;
   - preserve quickstart/user docs silence about full EvidenceGraph internals
     unless the change is a narrow forward reference.

### Out of scope

- Production code changes in `src/factgraph/audit`, SDK, adapters, service,
  release tooling, or tests.
- Changing public DTOs (`Claim`, `EvidenceRef`, `EvaluateRow`, `EvaluateResult`,
  `Explanation`, `EvidenceGraph`).
- Implementing richer evidence graph population.
- Adapter evidence semantics, ProbLog/PyReason/Nemo enrichment, or T10 carrier
  execution.
- Failed graph / why-not tree runtime implementation.
- Match witness APIs such as `.as_assertions()`, `.witnesses()`, or `.to_view()`.
- Service/OpenAPI routes, ACL, signature, session log, or LLM explain channels.
- Broad quickstart teaching for EvidenceGraph internals before runtime support.
- v0.2 release machinery or live release work.
- Dirty baseline cleanup.

### Stop / amend triggers

Pause and amend if Step 4.6 or implementation shows:

- T6 cannot write an implementable design without changing shipped DTOs;
- `EvidenceGraph` internals must become public user-facing guarantees in v0.2;
- failed/why-not evidence, match witness output, or session log APIs need to be
  pulled into this cycle;
- adapter production semantics or engine math must change;
- service/OpenAPI, ACL, signature, or persistence-layer schema changes are
  required;
- the work expands into the full T8 implementation instead of a T6 design
  source.

## 1. Problem

The active evidence design has shipped Phase A/B-1 through B-6 decisions, and
T5 delivered a minimal `Explanation` + `EvidenceGraph` bridge. But the sections
that should guide the next evidence implementation step are still skeletons:

- §10 only says v1 audit is carried by `EvaluateResult` and `Explanation`
  metadata, while session logs and signatures are deferred.
- §11 only lists existing render/roundtrip helpers and says product UI should
  remain custom.
- §14 lists D1-D19 but still says Phase B should later fill triggers and scope
  sketches.

This leaves T8 at risk of inventing audit metadata, renderer behavior, and
deferred-item boundaries during implementation. T6 closes that design gap.

## 2. Goals

- Turn §10, §11, and §14 into implementable design sources.
- Preserve the shipped v0.2 boundary: `EvidenceGraph` remains opaque in user
  docs and minimal in runtime behavior.
- Record a T8 implementation split that can start from stable design facts.
- Clarify what remains v2+ or T10/T7-dependent.
- Keep the release path and dirty baseline untouched.

## 3. Inputs

| Source | Role |
|---|---|
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` | Primary design target; §10/§11/§14 are the skeletons to complete. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | Parent essay; §7 delegates evidence authority to the evidence design. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` | T6/T8/T9 dependency and release-boundary source. |
| `workflow/design/design-points/active/match-api-design.zh.md` | Match witness boundary; witness/assertion-returning match output is deferred to evidence/witness design. |
| `src/factgraph/audit/evidence_graph.py` | Shipped `EvidenceGraph`, renderer, validation, and JSON roundtrip truth. |
| `src/factgraph/application/protocol/evaluate_result.py` | Shipped `Claim`, `EvidenceRef`, `EvaluateRow`, `EvaluateResult`, `Explanation`, and metadata bridge truth. |
| `docs/official/kernel/quickstart/evidence.md` | User-facing boundary: EvidenceGraph internals remain intentionally opaque in v0.2 docs. |
| `src/factgraph/audit/docs/02_evidence_graph.md` | Current audit module docs for `EvidenceGraph` structure and reference renderer. |
| T5.1 / T5.3 archived blueprints | DTO and minimal evidence bridge anchors. |
| Hubble read-only inventory | Pre-draft evidence Phase B inventory and recommended scope. |

## 4. Draft Decisions To Lock

| # | Decision | Draft leaning |
|---|---|---|
| D1 | T6 output shape | Directly edit `evidence-tree-rainbird-style-v1.zh.md` §10/§11/§14, plus narrow parent §7 cross-link only if needed. |
| D2 | Audit channel v1 | Define v1 as metadata carried by `EvaluateResult`, `Explanation`, and `EvidenceGraph.metadata`; no session log or signatures in v1. |
| D3 | Audit immutability stance | v1 requires deterministic IDs/digests and JSON roundtrip validation; cryptographic signatures and append-only session logs are v2+. |
| D4 | Renderer boundary | Reference HTML renderers are diagnostic utilities, not product UI obligations; product UI remains custom. |
| D5 | Renderer modes | Keep `tree` and `timeline` as shipped modes; matrix should say which engines/forms each mode is appropriate for. |
| D6 | Deferred registry | Expand D1-D19 with trigger, owner, v1 boundary, and implementation-cycle hint; do not promote any deferred item by default. |
| D7 | T8 split | Propose T8-A validator/metadata, T8-B native/Souffle topology, T8-C engine-specific enrichment gated by T10/PyReason work. |
| D8 | User docs | Do not add full EvidenceGraph teaching until implementation exists; at most keep forward references. |
| D9 | Match witness seam | Keep witness-returning match output deferred; T6 may record the seam but must not design the runtime API in detail. |

## 4.1 Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | Branch / dirty baseline | Branch is ahead of origin by the T6 draft commit. Dirty baseline remains the four tracked docs/notebooks plus untracked Rainbird reference; T6 must not touch them. |
| 2 | §10 current text | §10 is a skeleton at `evidence-tree-rainbird-style-v1.zh.md:2335-2345`. It names `EvaluateResult.run_id`, `evaluated_at`, `result_digest`, `Explanation.head.id`, `head.content_digest`, `expr_digest`, and `evidence.graph_id`, then defers session logs and evidence signatures. Missing: full field table, package boundary, validation/roundtrip, and immutability stance. |
| 3 | §11 current text | §11 is a skeleton at `evidence-tree-rainbird-style-v1.zh.md:2349-2357`. It names tree/timeline HTML rendering and dict roundtrip, but lacks reference-renderer vs product-UI boundary, layout matrix, empty/error/large behavior, and custom UI obligations. |
| 4 | §14 D-numbering | Current table is D1-D19, not D1-D11+. Rows are at `evidence-tree-rainbird-style-v1.zh.md:2588-2626`. D11-D13 are under engine extensions after D14-D19, and the status line still says "Phase A locked 11 items"; implementation must normalize the prose without renumbering existing IDs. |
| 5 | Shipped `EvidenceGraph` | Fields: `graph_id`, `engine`, `root_node_id`, `nodes`, `edges`, `support_kind`, `layout_hint`, `metadata` at `src/factgraph/audit/evidence_graph.py:59-70`. Node fields at `:24-35`; edge fields at `:42-51`. Validation covers layout enum, duplicate node/edge ids, root existence, endpoint references, and DFS cycle detection at `:72-115`. |
| 6 | Renderer / roundtrip truth | Shipped layouts are `tree` and `timeline` at `evidence_graph.py:8-21`; renderer dispatch is `:118-124`; JSON dict roundtrip is `:127-187`. Audit docs describe renderer role and current model at `src/factgraph/audit/docs/02_evidence_graph.md:28-56`, validation at `:79-91`, renderer at `:93-113`, and durable audit boundaries at `:115-155`. |
| 7 | Result DTO fields | `Claim` fields are `kind/name/arguments/repr/digest` at `evaluate_result.py:52-59`; `EvidenceRef` fields are `ref_id/result_id/row_id/fact_digest/closed_head_digest` at `:69-76`; `EvaluateRow` fields are at `:85-93`; `EvaluateResult` fields include `result_id/run_id/rows/head/engine/engine_version/adapter_version/expr_digest/rule_set_digest/view_snapshot_digest/semantics_digest/evaluated_at/result_digest` at `:128-143`; `Explanation` fields are at `:202-216`. |
| 8 | Explanation invariants | `Explanation(status="passed") iff evidence is not None`, passed requires claim/result id, failed requires `failure_class`, and unsupported/invalid_request require errors at `evaluate_result.py:218-246`. T6 must preserve this envelope boundary. |
| 9 | Metadata bridge full key list | Current `EvidenceGraph.metadata` row/result copy includes `result_id`, `row_id`, `evidence_ref_id`, `claim_digest`, `closed_head_digest`, `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `semantics_digest`, `result_digest`, `engine`, `engine_version`, `adapter_version`, `evaluated_at` at `evaluate_result.py:823-842`. Audit channel also includes `EvaluateResult.run_id` and `EvaluateResult.evaluated_at/result_digest` at `:128-143`; `run_id` is not currently duplicated into `EvidenceGraph.metadata`. |
| 10 | Minimal graph truth | Current passed graph builder emits one conclusion/root node, zero edges, `support_kind="evaluate_row"`, and copied metadata at `evaluate_result.py:800-820`. T5.3 explicitly allowed this minimal graph shape at `workflow/blueprints/archive/2026-05-25_t5-3-explanation-envelope-live-row-resolver.md:198-213`. |
| 11 | T5 anchors | T5.1 scoped DTOs, SDK re-exports, digest helpers, and mandatory `view_snapshot_digest` at `workflow/blueprints/archive/2026-05-25_t5-1-dto-foundation-digest-harness.audit.md:56-69`. T5.3 delivered `Explanation`, live row `explain()`, graph validation failure behavior, and minimal graph reuse at `2026-05-25_t5-3-explanation-envelope-live-row-resolver.md:439-466`. |
| 12 | User docs stance | Quickstart keeps `EvidenceGraph` intentionally opaque in v0.2 at `docs/official/kernel/quickstart/evidence.md:244-269`. T6 must not add full user-facing teaching until runtime support exists. |
| 13 | Parent evidence authority | Parent §7 delegates detailed evidence authority to the evidence design at `rule-expression-and-proof-attempt.zh.md:1654-1675`; it still points to an old `docs/references/working/...` path at `:1656-1659`, so implementation may narrow-fix that pointer to the active design path. |
| 14 | Match witness seam | Match design states match returns snapshots and does not expose witness assertion ids at `match-api-design.zh.md:45-52`; `.as_assertions()`, `.witnesses()`, and `.to_view()` are deferred at `:494-511`. T6 should add a deferred registry seam only, not API shape. |
| 15 | Roadmap dependency | Roadmap locks T6 -> T8 -> T9 at `post-t5-completion-roadmap.zh.md:76-97`, T6 expected outputs at `:127-150`, and T8 candidate scope at `:168-184`. T6 split language must be a proposal for future T8, not a hard order lock. |
| 16 | Large graph threshold | No shipped node/edge threshold exists in code or docs. Scoped decision: T6 should define a reference-renderer warning threshold (`>250` nodes or `>500` edges) as design guidance only; product UIs may set stricter limits. No runtime truncation or refusal is required by T6. |
| 17 | Implementation file set | Expected implementation files: evidence design doc; optional parent §7 pointer fix. No runtime/test/release/notebook files. |
| 18 | Stop-amend findings | None for scoped. All requested T6 work remains design-only. |

## 4.2 Final Scoped Decisions

| Decision | Scoped lock |
|---|---|
| T8 split status | T6 will provide a **proposal**, not a binding T8 execution order. T8 may revise the split based on then-current T10/T7 state. |
| Metadata enumeration | §10 must enumerate both envelope-level audit fields and `EvidenceGraph.metadata` keys, explicitly noting that `run_id` is envelope-level and not currently duplicated into graph metadata. |
| Large graph handling | §11 must define design guidance for reference renderer "large" graphs (`>250` nodes or `>500` edges) with warning / product-UI handoff language, not runtime truncation. |
| Deferred numbering | §14 remains D1-D19. T6 may add new deferred items after D19 but must not renumber existing IDs. The stale "11 items" status line must be corrected. |
| Match witness seam | Add a narrow deferred seam, expected as D20, for witness/assertion-returning match output. It records trigger/owner/boundary only; it must not design `.as_assertions()` API details. |
| Parent cross-link | Narrow-fix parent §7 path if implementation touches the delegation paragraph; do not re-open parent evidence design. |

## 5. Expected Step 4.6 Inventory

The scoped commit filled concrete results for:

1. current branch / dirty baseline status;
2. exact current content of §10 and its missing fields;
3. exact current content of §11 and its missing rendering decisions;
4. exact current D1-D19 deferred table and any numbering gaps;
5. shipped `EvidenceGraph` fields, validation rules, renderer modes, and
   dict roundtrip functions with file:line refs;
6. shipped `Claim` / `EvidenceRef` / `EvaluateRow` / `EvaluateResult` /
   `Explanation` fields and invariants with file:line refs;
7. current metadata bridge keys copied into evidence graph metadata;
8. T5.1/T5.3 archived blueprint anchors for DTO and minimal EvidenceGraph
   behavior;
9. current quickstart / audit docs stance on EvidenceGraph internals;
10. match design witness boundary and how T6 should avoid overclaiming it;
11. roadmap T6/T8/T9 dependency and v0.2 release boundary;
12. final class confirmation and implementation file set;
13. any stop-amend findings.

## 6. Expected Implementation Shape

Implementation should be staged in design commits:

1. **§10 Audit Channel**: metadata field table, audit package boundary,
   immutability stance, validation and roundtrip expectations, v2+ exclusions.
2. **§11 Rendering**: reference renderer boundary, layout matrix, product UI
   split, JSON roundtrip, error/empty/large graph behavior.
3. **§14 Deferred Items + T8 split**: D1-D19 owner/trigger/non-goal expansion
   and follow-on T8 implementation split proposal.
4. **Cross-link cleanup**: parent §7 and roadmap/quickstart references only if
   Step 4.6 shows stale pointers.

If any step requires production code or public DTO changes, stop and amend.

## 7. Verification Gates

- `git diff --check` clean.
- No production, test, service, OpenAPI, adapter, release, or notebook changes.
- Design references have file:line-supported source anchors from Step 4.6.
- Deferred items D1-D19 retain explicit trigger and non-goal boundaries.
- T8 split proposal is specific enough to seed a future blueprint.
- Sacred `master` unchanged.
- Dirty baseline preserved.

## 8. Acceptance

- [ ] Step 4.6 inventory completed with source refs.
- [ ] §10 Audit Channel is no longer a skeleton.
- [ ] §11 Rendering is no longer a skeleton.
- [ ] §14 Deferred Items has owner / trigger / non-goal / implementation hint
      coverage for D1-D19.
- [ ] T8 implementation split proposal exists.
- [ ] Match witness boundary remains deferred.
- [ ] No production / DTO / adapter / service / release changes.
- [ ] Dirty baseline and sacred master preserved.
