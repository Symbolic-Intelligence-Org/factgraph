# Task Blueprint Audit: Workflow Governance Promotion

- Status: draft
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Authority: paired blueprint audit log; tracks state transitions and decision notes for the sibling blueprint at [2026-05-22_workflow-governance-promotion.md](./2026-05-22_workflow-governance-promotion.md).
- Inputs:
  - [Sibling blueprint](./2026-05-22_workflow-governance-promotion.md)
- Outputs / Downstream:
  - (none) — paired audit logs are passive event records, not consumed downstream
- Related:
  - [workflow/CADENCE.md](../../CADENCE.md) §Step 4.1-4.9 — paired audit log lifecycle
  - [workflow/blueprints/AGENTS.md](../AGENTS.md) (will exist post-Phase 3 mv) — formal paired audit log convention
- Blueprint: [2026-05-22_workflow-governance-promotion.md](./2026-05-22_workflow-governance-promotion.md)
- Branch: `v0.2.0-blueprint-workflow-governance-promotion-2026-05-22`

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-22 | draft | Blueprint created | Initial scope per Q1-Q5 adopted decisions (batch commit `ae375ce5`) + post-Q synthesis §3 phase plan + Step 0.1 scaffold (`0199ab20`). Sibling audit log created together per CADENCE Step 4.1. |
| 2026-05-22 | draft | Step 4.2 tightening applied | 4 P-findings folded into blueprint (commit `bfafabbd`): P1 design-points mv phase consolidation; P2 working/README.md author location fix; P3 Phase 5 per-pair mv pattern; P4 Acceptance addressed-or-deferred. |
| 2026-05-22 | draft | Step 4.3 preflight landed on independent branch | Preflight at `c43ab22b` on `v0.2.0-workflow-governance-promotion-preflight-2026-05-22`. Findings: 2 Required + 2 Recommended + 14 Verified + 1 Scoped-detail + 0 Abandonment. |
| 2026-05-22 | draft | Step 4.4 preflight amendment applied | 3 PF items folded into blueprint on blueprint branch (this commit): PF-R1 design-points count 6 → 12 essays + 1 readme; PF-Rec1 README mv vs author ambiguity (Phase 2 step 4 delete + step 6 absorb-not-mv); PF-Rec2 factgraph-namespace-test-proposals reconnaissance sub-step. **PF-R2 deferred** (out of authorized scope) — see Decision Notes. |

## Decision Notes

### 2026-05-22 — Initial draft scope

This blueprint is the implementing artifact for the workflow-governance-promotion slice — the **first slice to formally exercise the new canonical cadence** (`workflow/CADENCE.md`) and the new pillar structure (per Q1-Q5).

Key scope-locked points captured here for traceability before Step 4.2 review:

1. **8-phase implementation plan** (Phase 1.5 → Phase 8) per blueprint §8, derived directly from synthesis §3. Phase 1 was Step 0.1 (already done).
2. **Phase 5 (491-archive mv) is conditional** with default DEFER. Decision gate is Phase 4 validator outcome.
3. **N-3 protective preservation locks** explicit per §6.1: docs/SECURITY + docs/api + docs/official + src/factgraph + sacred branches + 491 archive (if Phase 5 mv'd) + 6 companion auto-memory + unrelated dirty file set.
4. **Multi-Q single-branch consolidation** continues from Step 0.2 — Q1-Q5 all on the blueprint branch rather than 5 separate Q branches; deviation noted in synthesis and to be re-stated in §10 closure.
5. **Step 4.3 preflight is REQUIRED** per Q3 §4.4 trigger conditions (namespace migration + high-risk migration + cross-module).
6. **3-commit impl pattern** acceptable for large mv phases (Phase 2, Phase 5 if done, Phase 6) if Step 4.7 surfaces P1 findings.
7. **Synthesis self-narrative commit-count drift** (per user A-option authorization): synthesis §5 narrative is one commit short of actual lineage; documented carry-forward; will be reflected in §10 closure.

### Carry-forward decisions tracked here

| Item | Source | Status |
|---|---|---|
| Phase 5 outcome | Phase 4 validator | TBD at Phase 4 completion |
| Phase 7 case-by-case classifications for `references/working/` content | User AskUserQuestion (if needed) | TBD per file at Phase 7 |
| Memory content cleanup deferral | NG1 + Q5 §4.7 + audit §6 | Deferred to separate slice (out of scope this slice) |
| CLAUDE.md introduction | NG2 + audit §6 | Deferred to separate slice |
| Obsidian integration | NG3 + Q1 §4.3 | Deferred to separate slice |
| 6 companion auto-memory promotion | NG4 + Q5 §4.7 | Deferred to future per-discipline slices |
| Phase 8 root `/AGENTS.md` factpy_kernel → factgraph fix | Audit §3.3 D1 | Folded into Phase 8 |
| PF-R2 (/AGENTS.md 51 → 50 line count fix in Stage 1 audit doc) | Preflight `c43ab22b` PF-R2 + retraction note below | Deferred to a separate Stage 1 audit tightening commit (out of Step 4.4 authorized scope; user authorization covered blueprint + sibling audit log only) |

### 2026-05-22 — Step 4.4 preflight amendment notes

**PF-R1 applied** (blueprint §8 Phase 2 step 6): design-points essay count corrected from "6 essays + readme.md" to "12 essays + 1 readme" with explicit enumeration of the 12 essay filenames. Spot-checked at preflight time via `find docs/references/working/design-points -maxdepth 1 -name "*.md"`. Critical fix — without this, half the essays would have been missed in Phase 2 mv.

**PF-R2 NOT applied** (deferred):

- Preflight `c43ab22b` PF-R2 claimed the "51 lines" reference was in BOTH the Stage 1 audit doc AND this blueprint. Re-grep at amendment time shows the "51 lines" claim exists **only** in the Stage 1 audit doc (`workflow/audit/active/2026-05-22_workflow-governance-vs-shipped.md` line 17), NOT in this blueprint or sibling audit log.
- This is a **preflight calibration miss**: I (Claude, preflight drafter) over-attributed PF-R2 to the blueprint without grep-verifying. The PF-R2 finding itself is still factually correct (the file is 50 lines, not 51); only the location-claim was over-broad.
- User-authorized Step 4.4 scope was "blueprint branch + sibling audit log only". The Stage 1 audit doc is out of scope; PF-R2's fix is therefore deferred to a separate Stage 1 audit tightening commit. Tracked in the Carry-forward table above.

**PF-Rec1 applied** (blueprint §8 Phase 2 step 4 + step 6): README mv vs author ambiguity resolved.

- Step 4 now: delete legacy `docs/decisions/README.md` (superseded by Phase 1.5 fresh README); explicit "do NOT git mv" caveat.
- Step 6 now: 12 essays mv'd to active/; the legacy lowercase `readme.md` is NOT mv'd as pillar README; its content is absorbed into Phase 1.5 fresh `README.md` (uppercase) and the legacy is deleted in this Phase or Phase 7 cleanup.

**PF-Rec2 applied** (blueprint §8 Phase 7): `factgraph-namespace-test-proposals/` Phase 7 classification now requires reconnaissance read (`ls -la` + any README) at Step 4.7 time before classification AskUserQuestion. Default fallback (heritage/bundles/ + preserve) retained if reconnaissance inconclusive.

**Cadence calibration learning**: PF-R2 over-attribution surfaces a preflight discipline gap — finding-location claims should be grep-verified at preflight-row-drafting time, not just stated. Will note for future preflights via memory consolidation (out of slice scope).

## Anticipated stage transitions (planned, not retroactively logged)

The following transitions will be appended to the Event Log as they occur:

- `draft → scoped` after Step 4.2 (review + tightening) + Step 4.3 (preflight) + Step 4.4 (preflight amendment) + Step 4.5 (self-check) + optional Step 4.6.5 (pre-impl grep amendment)
- `scoped → implementing` is implicit in CADENCE; no separate Status field flip but Step 4.7 implementation begins on the impl branch
- `scoped → implemented` at Step 4.8 closure (commit on this blueprint branch updates Status + §10 Outcome)
- `implemented → archived` at Step 4.9 (`git mv` blueprint pair to `workflow/blueprints/archive/`)

Each transition gets its own Event Log row.
