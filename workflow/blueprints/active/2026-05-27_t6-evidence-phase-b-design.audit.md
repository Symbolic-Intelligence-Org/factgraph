# Audit: T6 Evidence Phase B Design Skeleton

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t6-evidence-phase-b-design.md`
- Stage: draft
- Class: L (design skeleton; may narrow after Step 4.6)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: four tracked docs/notebooks plus untracked Rainbird reference
  remain from T11.2.5 and must not be changed by T6.
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | TBD | T6 blueprint pair drafted | Draft uses Hubble read-only inventory and locks T6 as design-only Phase B evidence skeleton work. |

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

