# Audit: T8-C Engine Enrichment Inventory

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-c-engine-enrichment-inventory.md`
- Stage: draft
- Class: S/M (design-only planning inventory)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 3 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-C inventory blueprint pair drafted | Triggered after T8-B-2 + T8-D round 2 completed native/Souffle loop; Q1-Q12 intentionally pending for Step 4.6. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8-C is the remaining evidence engine-enrichment lane after T8-A, T8-B-1,
  T8-B-2, and T8-D round 2.
- The reviewer supplied a factual observation that ProbLog/PyReason do not
  create `SupportArtifact` instances and instead sit in provenance-bearing
  support-kind space. This is useful orientation but must be independently
  verified in Step 4.6.
- Evidence §15.2 names ProbLog multi-path / probability carrier enrichment,
  PyReason timeline/Form 2, Nemo opt-in, and engine_meta contract/debug split
  hardening.
- T10 C74/C76/C77/C78 is adjacent adapter semantics work and may gate T8-C
  slices, but the exact dependency must be source-backed per C-id.

This draft scan is not a Step 4.6 answer and does not select an architecture
path.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which architecture path should T8-C use? | Pending Step 4.6. |
| Q2 | What is the current ProbLog adapter evidence shape? | Pending Step 4.6. |
| Q3 | What is the current PyReason adapter evidence shape? | Pending Step 4.6. |
| Q4 | How do T10 C74 / C76 / C77 / C78 affect T8-C? | Pending Step 4.6. |
| Q5 | Should T8-C split into ProbLog and PyReason sub-cycles? | Pending Step 4.6. |
| Q6 | Is PyReason Form 2 temporal in T8-C-2 scope or deferred? | Pending Step 4.6. |
| Q7 | Is C119 ProbLog multi-path DAG in first ProbLog scope or deferred? | Pending Step 4.6. |
| Q8 | Does T8-C handle C136 aggregate envelope? | Pending Step 4.6. |
| Q9 | What is the engine-meta extension policy? | Pending Step 4.6. |
| Q10 | Is Nemo in any T8-C scope? | Pending Step 4.6. |
| Q11 | What durable output shape should this cycle produce? | Pending Step 4.6. |
| Q12 | Are there stop/amend findings? | Pending Step 4.6. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Reviewer SupportArtifact-free finding is accepted without verification | Wrong architecture path | Verify with source refs and grep results. |
| T8-C starts runtime work inside planning cycle | Scope creep | Keep commits docs/blueprint only. |
| T10 dependency is described too broadly | Blocks useful engine-local planning or starts work too early | Map C74/C76/C77/C78 separately. |
| PyReason Form 2 sketch is treated as implementation-ready | Premature temporal schema commitment | Check D11 and §8 Form 2 deferrals. |
| Engine-specific metadata is flattened into generic fields | Violates §15.2 non-goal | Decide engine_meta namespace policy. |
| Dirty baseline is touched | Workflow violation | Stage only T8-C inventory files. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q12 answered.
- [ ] Output shape selected.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending inventory / closure.
