# Audit: T8-D Evidence Docs Alignment

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-d-evidence-docs-alignment.md`
- Stage: draft
- Class: S/M (docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current four modified tracked docs/notebooks plus two untracked reference directories
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-D evidence docs alignment blueprint pair drafted | Triggered by shipped T8-A + T8-B-1 behavior; Q1-Q9 intentionally pending for source-backed Step 4.6. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8-A and T8-B-1 are both archived and published on this branch.
- The official evidence quickstart is the likely primary user-facing doc.
- SDK docs contain several evidence/explanation mentions and need per-file
  triage before any edit.
- Audit module docs were aligned by T7 and T8-B-1 and should be used as a
  reference rather than edited by default.

This draft scan is not a Step 4.6 answer. It intentionally avoids choosing
file scope or wording strategy before source-backed inventory.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which docs files must change and which should remain untouched? | Pending Step 4.6. |
| Q2 | What is the shape of the `evidence.md` update? | Pending Step 4.6. |
| Q3 | Should docs show concrete Form 1 JSON / HTML render shape? | Pending Step 4.6. |
| Q4 | How should the 14-key metadata contract be presented? | Pending Step 4.6. |
| Q5 | How should hard vs soft graph failure be described? | Pending Step 4.6. |
| Q6 | Where should deferred boundaries be marked? | Pending Step 4.6. |
| Q7 | How should quickstart and SDK docs split responsibility? | Pending Step 4.6. |
| Q8 | Should quickstart/SDK docs cross-link to audit module docs? | Pending Step 4.6. |
| Q9 | Should docs cite tests or line numbers? | Pending Step 4.6. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Docs teach deferred behavior as shipped | Users depend on unavailable adapter/failed-graph/match-witness behavior | Build explicit shipped/deferred map before editing. |
| File scope balloons | Docs-only cycle becomes broad rewrite | Per-file triage and stop if more than five secondary files need non-trivial edits. |
| Quickstart over-specifies internals | Users depend on implementation-only `engine_meta` details | Decide example granularity before implementation. |
| SDK docs duplicate quickstart heavily | Drift risk between public docs surfaces | Lock quickstart vs SDK role split. |
| Runtime/test edit temptation | Violates T8-D docs-only purpose | Stop if any docs gap requires code/test changes. |
| Dirty baseline edited accidentally | Workflow violation | Status checks before commit/closure. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q9 answered.
- [ ] File scope locked.
- [ ] Shipped/deferred evidence behavior map complete.
- [ ] Docs-only boundary preserved.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending inventory / implementation / closure.
