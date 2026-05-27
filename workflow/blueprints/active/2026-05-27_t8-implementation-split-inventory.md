# Task Blueprint: T8 Implementation Split Inventory

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S/M (design-only planning inventory)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-implementation-split-inventory.audit.md`
- Trigger: T6 added evidence §15 T8-A/B/C/D implementation split proposal; T7 shipped the audit/rendering bridge and contract matrix. Before opening T8-A runtime work, quantify the proposed split against current runtime and tests.

## 0. Scope Locks

### In scope

This cycle is **T8 implementation planning**, not T8 implementation. It should
turn §15's proposed T8-A/B/C/D split into implementable future cycle units.

Candidate planning outputs:

1. Re-read and verify `evidence-tree-rainbird-style-v1.zh.md` §15.1-§15.5
   after T7.
2. Map every T7 §4.2 contract-matrix row to T8-A/B/C/D or explicitly mark it
   already shipped / out-of-scope.
3. Quantify per-slice file boundaries, likely touch points, new-vs-existing
   surfaces, fixture/test entry points, and rough class/LOC estimates.
4. Build the dependency graph across T8-A/B/C/D and decide whether any work can
   proceed in parallel.
5. Decide whether T8-A must be split further before implementation.
6. Refine per-slice stop/amend triggers from §15.4.
7. Clarify T8-C's coordination with T10 adapter semantics.
8. Map D1-D20 deferred items to T8-A/B/C/D or future/non-T8 buckets.
9. Choose the durable output shape for this planning result.

### Out of scope

- Runtime code changes of any kind.
- Test code changes.
- Audit docs or public docs changes.
- Drafting the actual T8-A/B/C/D implementation blueprints.
- D20 match witness API design.
- D1/D2 why-not / counterfactual runtime.
- Service / OpenAPI, Database / view runtime, cross-entity match, or
  `fg.eval.run` deletion.
- SDK API shape changes.
- Release machinery, PyPI, tags, or live release work.
- Dirty baseline cleanup.

### Stop / amend triggers

Pause and amend before closure if Step 4.6 shows:

- §15's proposed T8-A/B/C/D split no longer fits current runtime after T7.
- T7's contract matrix is materially wrong and must be fixed before T8
  planning can proceed.
- T8-A cannot reasonably ship as one cycle and needs an explicit T8-A-1 /
  T8-A-2 split.
- A planning item attempts to make runtime/test/doc edits.
- T8-C requires adapter semantics that are not merely coordination with T10 but
  a fresh T10 design scope.
- The output shape choice requires a durable design-point artifact not covered
  by this blueprint.

## 1. Problem

T6 §15 already proposes a T8 split, and T7 confirmed that the audit/rendering
bridge is now aligned enough for implementation planning. The remaining risk is
starting T8-A as a large runtime cycle without first quantifying the actual file
boundaries, tests, dependencies, and stop conditions.

T8 implementation should begin from a scoped split inventory, not from the
high-level §15 proposal alone.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §15.1-§15.5 | Primary proposed T8 split: goals, T8-A/B/C/D rows, first-blueprint recommendation, stop-amend triggers, T9 handoff. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §14 D1-D20 | Deferred registry to classify per T8 slice. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §10/§11 | Metadata/rendering contracts that drive T8-A/T8-D boundaries. |
| `workflow/blueprints/archive/2026-05-27_t7-evidence-audit-rendering-bridge.md` §4.1/§4.2/§6 | T7 final scoped decisions, contract matrix, and source-backed runtime map. |
| `workflow/blueprints/archive/2026-05-27_t7-evidence-audit-rendering-bridge.audit.md` | Closure observations and verification context. |
| `src/factgraph/audit/evidence_graph.py` | Existing DTO, validation, roundtrip, renderer, and T7 bridge behavior. |
| `src/factgraph/application/protocol/evaluate_result.py` | Current metadata writer and minimal passed-row graph builder. |
| `src/factgraph/audit/` modules | Audit package read/query/event/proof-frame boundaries for T8-A/T8-D planning. |
| Engine evidence tests and core candidate evidence paths | Candidate surfaces for T8-B/T8-C boundary quantification. |

## 3. Draft Source Scan

Draft scan only confirms orientation:

- §15 is already a proposal, not an empty design slot.
- §15.3 explicitly recommends the first implementation blueprint be T8-A only.
- T7's bridge cycle already mapped §10/§11 to shipped behavior and deferred
  central metadata sufficiency to T8-A.
- Current runtime already has `EvidenceGraph`, minimal passed-row graph builder,
  renderer, and engine evidence tests.

This scan does not answer Q1-Q9. Step 4.6 must replace it with source-backed
file:line and section-anchor evidence.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Does §15.2's four-slice proposal still hold after T7? | Keep / revise / split / merge decision with rationale. |
| Q2 | How do T7 §4.2 contract rows map to T8 slices? | Complete 10-row matrix to T8-A/B/C/D / shipped / out-of-scope. |
| Q3 | What is T8-A's real code boundary? | Central metadata builder, sufficiency checker, strict validation gate, and debug assertion surfaces with file:line refs and LOC/class estimates. |
| Q4 | Does T8-A need to split? | Single-cycle vs T8-A-1/T8-A-2 recommendation. |
| Q5 | What is T8-B's real code boundary? | Candidate evidence / native / Souffle reuse-vs-rewrite map with refs. |
| Q6 | How does T8-C depend on T10? | Sequential / parallel / prerequisite-subset decision. |
| Q7 | What is the dependency graph? | Table or DOT-like graph for T8-A/B/C/D. |
| Q8 | Which D1-D20 items are triggered by each slice? | Per-slice deferred-item mapping. |
| Q9 | What durable output shape should this cycle produce? | Option A design-point note, Option B blueprint-only split plan, or Option C hybrid. |

## 5. Existing Invariants To Preserve

- No runtime, test, docs, release, or dirty-baseline files are edited in this
  cycle unless scope is amended first.
- T7 behavior remains current truth: renderer type guard, large-graph warning,
  14-key §10.3 metadata test, and `run_id` envelope-only stance.
- T6 v1 sessionless boundary remains intact: no session ids, session logs,
  `/interactions/{sessionID}`, ACL, signatures, salience, impact, or
  `x-evidence-key`.
- T8 split planning must not silently start T8 graph construction.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains the known four tracked docs/notebooks plus untracked
  `rainbird-ai sdk code/`.

## 6. Step 4.6 Inventory Plan

Step 4.6 should fill:

1. §15.1-§15.5 exact section anchors and current wording.
2. T7 §4.1/§4.2/§6 anchors relevant to T8 split planning.
3. Current `EvidenceGraph` / metadata builder / renderer code boundaries.
4. Current audit package modules and which are likely T8-A/T8-D surfaces.
5. Current candidate evidence / native / Souffle / engine-specific paths for
   T8-B/T8-C boundary estimation.
6. Existing test modules and fixtures per slice.
7. T7 contract matrix -> T8 slice mapping.
8. D1-D20 -> T8 slice mapping.
9. T8-A decomposition analysis.
10. T8-C/T10 dependency analysis.
11. Output shape decision and resulting files.
12. Verification commands for a design-only cycle.
13. Dirty baseline and sacred master preservation check.
14. Stop/amend findings.

## 7. Implementation Shape

This cycle may not have a runtime implementation phase. Depending on Q9:

- Option A: add a lightweight design-point note for the split plan.
- Option B: keep the split plan entirely in this blueprint and archive it.
- Option C: add a design-point note and close the blueprint as the audit trail.

Any durable note must be docs-only and must not draft T8-A implementation
details beyond boundary, dependency, and testing plans.

## 8. Acceptance

- [ ] Step 4.6 answers Q1-Q9 with source-backed evidence.
- [ ] §15 proposal is either confirmed or revised with explicit rationale.
- [ ] T7 contract matrix is mapped to T8 slices.
- [ ] T8-A boundary and split/no-split decision are recorded.
- [ ] T8-B/T8-C/T8-D boundaries and prerequisites are recorded.
- [ ] D1-D20 per-slice mapping is recorded.
- [ ] Output shape is locked and produced if needed.
- [ ] No runtime/test/docs/release/dirty-baseline files are edited unless
      explicitly amended.
- [ ] `git diff --check` passes.
- [ ] Dirty baseline and sacred master are preserved.

## 9. Verification Commands

Draft expected checks:

```bash
git diff --check
git status --short --branch
```

Step 4.6 may add read-only grep commands or focused no-op runtime baselines if
the chosen output shape justifies them.

## 10. Outcome / Deviations

Pending implementation / closure.
