# Audit: T8-D Round 2 Souffle User Docs

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-d-round2-souffle-user-docs.md`
- Stage: draft
- Class: S (docs-only, pending Step 4.6)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 3 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-D round 2 Souffle user docs blueprint pair drafted | Triggered by T8-B-2 Q8 / closure follow-up; Q1-Q8 intentionally pending for Step 4.6. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8-D first round edited exactly `evidence.md` and SDK `00_user_guide.en.md`.
- T8-B-2 shipped Souffle row-level Form 1 through the same row-result helper
  shape as native.
- The evidence quickstart still appears to contain native-only Form 1 wording
  and a deferred Souffle row-level Form 1 boundary.
- The SDK user guide appears to contain a concise native-only Form 1 summary.
- Audit module docs were already updated by T8-B-2 and are not expected to be
  edited in this round.

This draft scan is not a Step 4.6 answer. Step 4.6 must verify exact line refs
and file scope before implementation.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Is the file scope exactly `evidence.md` + SDK `00_user_guide.en.md`? | Pending Step 4.6. |
| Q2 | Which exact `evidence.md` locations need native -> native + Souffle expansion? | Pending Step 4.6. |
| Q3 | Which exact SDK user-guide locations need native -> native + Souffle expansion? | Pending Step 4.6. |
| Q4 | How should the deferred row-level Form 1 boundary change? | Pending Step 4.6. |
| Q5 | Does the existing ASCII Form 1 topology remain valid for Souffle? | Pending Step 4.6. |
| Q6 | Does the `winning_path_only` marker apply to Souffle user docs? | Pending Step 4.6. |
| Q7 | What verification is appropriate for docs-only round 2? | Pending Step 4.6. |
| Q8 | Should user docs mention the Souffle proof-tree converter boundary? | Pending Step 4.6. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Souffle behavior differs from native in a user-visible way | Symmetric text edit would overstate behavior | Verify T8-B-2 archive and current runtime/docs source. |
| Docs edit grows beyond two files | Scope creep for S-cycle | Count file scope and stop/amend if needed. |
| Deferred boundary accidentally teaches ProbLog/PyReason as shipped | User-facing contract drift | Explicit Current boundaries edit plan. |
| Docs duplicate quickstart detail in SDK guide | Future drift risk | Preserve quickstart-detail / SDK-summary split. |
| Audit module docs are edited unnecessarily | Duplicates T8-B-2 completed alignment | Treat audit docs as reference only unless Step 4.6 finds gap. |
| Dirty baseline is touched | Workflow violation | Stage only scoped blueprint/docs files. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q8 answered.
- [ ] File scope and verification locked.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending inventory / implementation / closure.
