# Audit: T6 Evidence Phase B Design Skeleton

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t6-evidence-phase-b-design.md`
- Stage: scoped
- Class: L (design skeleton; may narrow after Step 4.6)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: four tracked docs/notebooks plus untracked Rainbird reference
  remain from T11.2.5 and must not be changed by T6.
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | `7f1a9e85` | T6 blueprint pair drafted | Draft uses Hubble read-only inventory and locks T6 as design-only Phase B evidence skeleton work. |
| 2026-05-27 | scoped | TBD | Step 4.6 inventory recorded | Inventory locked metadata fields, D1-D19 numbering, renderer threshold guidance, match witness seam, and T8 proposal boundary. |

## 2. Pre-Draft Inventory

Hubble completed read-only inventory before this draft. No files were edited.

| Area | Finding |
|---|---|
| §10 current state | `evidence-tree-rainbird-style-v1.zh.md` §10 is still a Phase B skeleton. It names `EvaluateResult.run_id/evaluated_at/result_digest` and `Explanation.head/expr/evidence.graph_id`, but lacks metadata table, immutable audit stance, package boundary, validator, and roundtrip contract. |
| §11 current state | §11 is still a Phase B skeleton. It names the shipped HTML renderer, tree/timeline layouts, and dict roundtrip, but lacks reference renderer vs product UI boundary, layout matrix, and error/empty/large graph behavior. |
| §14 current state | §14 lists D1-D19 but says Phase B should add triggers and scope sketches. Owner, v1/non-v1 boundary, and stop-amend notes are incomplete. |
| Shipped `EvidenceGraph` | `EvidenceGraph` is a frozen DTO with graph/root/nodes/edges/support/layout/metadata and validation for duplicate ids, missing endpoints, root, and cycles. HTML rendering and dict roundtrip already ship. |
| Shipped result DTOs | `Claim`, `EvidenceRef`, `EvaluateRow`, `EvaluateResult`, and `Explanation` ship in the application protocol. `Explanation` enforces passed/evidence and failed/failure-class invariants. |
| Metadata bridge | Current passed graph metadata copies row/result context including result, row, evidence ref, claim/closed head/expr/rule set/view/semantics/result digests, engine, versions, and evaluated timestamp. |
| T5 anchors | T5.1 locked DTO/digest foundation. T5.3 accepted minimal passed `EvidenceGraph`, metadata copy, and unsupported result on evidence validation failure. |
| Match seam | T11.2.7 says match returns snapshots and witness/assertion-returning output is deferred to evidence/witness design. T6 may record the seam but must not implement it. |
| Roadmap dependency | Roadmap states T6 feeds T8 evidence implementation, which feeds T9 release/docs alignment. T6 is not a v0.2 release blocker unless release claims full evidence-tree support. |

## 3. Step 4.6 Inventory Plan

The scoped commit must fill:

1. `git status --short --branch` and dirty baseline confirmation.
2. Current §10 text and exact missing audit-channel decisions.
3. Current §11 text and exact missing rendering decisions.
4. Current §14 D1-D19 table, numbering, and missing trigger/owner/non-goal data.
5. `EvidenceGraph` fields, validation rules, renderer functions, and roundtrip
   helpers with file:line refs.
6. `Claim`, `EvidenceRef`, `EvaluateRow`, `EvaluateResult`, and `Explanation`
   shipped fields/invariants with file:line refs.
7. Current evidence metadata bridge key list with file:line refs.
8. T5.1/T5.3 archived blueprint anchors and any later T11 references.
9. Current quickstart / audit docs stance on EvidenceGraph internals.
10. Match API witness boundary and deferral wording.
11. Roadmap T6/T8/T9 dependency and release-boundary wording.
12. Final implementation file set and class prediction.
13. Stop-amend findings, if any.

## 3.1 Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | Branch / dirty baseline | `git status --short --branch` shows branch ahead by the T6 draft commit and the same four tracked dirty docs/notebooks plus untracked Rainbird reference. T6 must preserve them. |
| 2 | §10 skeleton | `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md:2335-2345` is still skeleton text. It names `EvaluateResult.run_id`, `evaluated_at`, `result_digest`, `Explanation.head.id`, `head.content_digest`, `expr_digest`, and `evidence.graph_id`; it defers session logs and evidence signatures. Missing decisions: field table, audit package boundary, immutability stance, validator/roundtrip contract. |
| 3 | §11 skeleton | `evidence-tree-rainbird-style-v1.zh.md:2349-2357` is still skeleton text. It names shipped tree/timeline HTML rendering and dict roundtrip, but lacks layout matrix, reference-vs-product UI boundary, and empty/error/large behavior. |
| 4 | §14 numbering | Current rows are D1-D19 at `evidence-tree-rainbird-style-v1.zh.md:2588-2626`. D11-D13 are listed after D14-D19 in engine extensions. The status line at `:2582` says Phase A locked 11 items and must be corrected without renumbering existing IDs. |
| 5 | `EvidenceGraph` DTO | `EvidenceNode` fields at `src/factgraph/audit/evidence_graph.py:24-35`; `EvidenceEdge` fields at `:42-51`; `EvidenceGraph` fields at `:59-70`. Validations: layout enum, duplicate node/edge ids, root existence, edge endpoints, and cycle detection at `:72-115`. |
| 6 | Renderer / roundtrip | Layout constants are `tree` / `timeline` at `evidence_graph.py:8-21`; renderer dispatch at `:118-124`; dict serialization/deserialization at `:127-187`. Audit docs summarize current model at `src/factgraph/audit/docs/02_evidence_graph.md:28-56`, validation at `:79-91`, renderer at `:93-113`, and durable boundaries at `:115-155`. |
| 7 | Result DTO fields | `Claim` fields at `src/factgraph/application/protocol/evaluate_result.py:52-59`; `EvidenceRef` fields at `:69-76`; `EvaluateRow` fields at `:85-93`; `EvaluateResult` fields at `:128-143`; `Explanation` fields at `:202-216`. |
| 8 | Explanation invariants | `Explanation` status/evidence, passed claim/result, failed failure-class, and unsupported/invalid_request errors are enforced at `evaluate_result.py:218-246`. T6 must not loosen these. |
| 9 | Metadata bridge | `EvidenceGraph.metadata` currently copies `result_id`, `row_id`, `evidence_ref_id`, `claim_digest`, `closed_head_digest`, `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `semantics_digest`, `result_digest`, `engine`, `engine_version`, `adapter_version`, and `evaluated_at` at `evaluate_result.py:823-842`. `EvaluateResult.run_id` exists at `:128-143` but is not currently duplicated into graph metadata. |
| 10 | Minimal graph builder | Current builder creates one conclusion/root node, no edges, `support_kind="evaluate_row"`, and metadata copy at `evaluate_result.py:800-820`. T5.3 explicitly allowed minimal graph shape and no partial graph on validation failure at `workflow/blueprints/archive/2026-05-25_t5-3-explanation-envelope-live-row-resolver.md:198-213`. |
| 11 | T5 anchors | T5.1 scoped DTOs and mandatory `view_snapshot_digest` at `workflow/blueprints/archive/2026-05-25_t5-1-dto-foundation-digest-harness.audit.md:56-69`. T5.3 delivered `Explanation`, live `row.explain()`, minimal graph reuse, and graph validation failure behavior at `2026-05-25_t5-3-explanation-envelope-live-row-resolver.md:439-466`. |
| 12 | User docs stance | Quickstart says `EvidenceGraph` is intentionally opaque in v0.2 at `docs/official/kernel/quickstart/evidence.md:244-269`; no full teaching should be added in T6. |
| 13 | Parent §7 | Parent evidence section delegates authority to evidence design at `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md:1654-1675`; it still references old `docs/references/working/...` path at `:1656-1659`, so T6 may narrow-fix the path. |
| 14 | Match witness seam | Match design defers witness assertion ids at `workflow/design/design-points/active/match-api-design.zh.md:45-52` and lists `.as_assertions()`, `.witnesses()`, `.to_view()` as deferred at `:494-511`. T6 may add D20 as a seam marker only. |
| 15 | Roadmap dependency | Roadmap has T6 -> T8 -> T9 at `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md:76-97`, T6 outputs at `:127-150`, and T8 candidate scope at `:168-184`. T8 split must be proposal language. |
| 16 | Large graph threshold | No shipped threshold exists. Scoped design guidance: `>250` nodes or `>500` edges is "large" for the reference renderer; warn and hand off to product UI / custom renderer rather than silently truncating or refusing. |
| 17 | Final file set | Expected implementation files: evidence design doc plus optional parent §7 pointer fix. No production/test/release/notebook files. |
| 18 | Stop-amend findings | None. Current scope remains L-class design-only. |

## 3.2 Final Scoped Decisions

| Decision | Lock |
|---|---|
| Audit metadata table | §10 must enumerate `EvaluateResult` envelope fields separately from current `EvidenceGraph.metadata` keys, including `view_snapshot_digest` and noting `run_id` is not duplicated into graph metadata today. |
| Renderer large threshold | §11 should define reference-renderer guidance for graphs larger than 250 nodes or 500 edges; product UI may choose stricter thresholds. |
| D-numbering | Keep D1-D19 IDs stable. Correct stale "11 items" prose. New witness seam may be D20. |
| T8 split | T6 proposes T8-A/B/C but does not lock future T8 execution order. |
| Match seam | Record witness/assertion-returning match output as deferred seam only; do not design method names or return types. |
| Parent link | Fix parent §7 path if touched; no parent redesign. |

## 4. Draft Implementation Expectations

Expected files:

| File | Expected role |
|---|---|
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` | Main design edits to §10/§11/§14 and T8 split proposal. |
| `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` | Narrow parent §7 cross-link only if Step 4.6 finds it stale. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` | No edit expected unless T6 discovers roadmap wording is stale. |
| `docs/official/kernel/quickstart/evidence.md` | No edit expected; user-facing internals remain deferred. |

No production, test, release, service, OpenAPI, adapter, notebook, or dirty
baseline files are expected.

## 5. Verification Plan

- `git diff --check`.
- Review changed files manually for skeleton removal and deferred-boundary
  preservation.
- Verify no production/test/runtime/release files changed.
- Verify dirty baseline remains unchanged.
- Verify `master` remains sacred.

## 6. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 inventory complete.
- [ ] §10 audit channel contract reviewed.
- [ ] §11 rendering contract reviewed.
- [ ] §14 deferred registry reviewed.
- [ ] T8 split proposal reviewed.
- [ ] No production / DTO / adapter / service / release changes.
- [ ] Closure notes filled.

## 7. Closure Notes

Pending.
