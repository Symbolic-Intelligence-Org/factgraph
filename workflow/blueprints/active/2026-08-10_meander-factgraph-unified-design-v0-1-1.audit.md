# Task Blueprint Audit: Meander × FactGraph 统一设计 Review Freeze v0.1.1 文本收敛

- Status: draft
- Created: 2026-08-10
- Last Updated: 2026-08-10
- Authority: paired blueprint audit log
- Inputs:
  - [`2026-08-10_meander-factgraph-unified-design-v0-1-1.md`](./2026-08-10_meander-factgraph-unified-design-v0-1-1.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [`2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md`](../../audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md)
  - [`meander-factgraph-unified-design-adversarial-review-disposition.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md)
- Blueprint: [`2026-08-10_meander-factgraph-unified-design-v0-1-1.md`](./2026-08-10_meander-factgraph-unified-design-v0-1-1.md)
- Branch: `v0.3.0-blueprint-meander-factgraph-unified-design-v0-1-1-2026-08-10`

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-10 | draft | Blueprint created | Initial Option 1 docs-only scope recorded from the Stage 1 audit; no downstream phase authorized. |
| 2026-08-10 | draft | Step 4.2 independent review tightening | Three read-only reviews were deduplicated into 11 Required and 6 Recommended amendments; all were applied below. One lower-priority lifecycle finding was rejected under the governance conflict order. Blueprint remains draft; preflight is not authorized. |
| 2026-08-10 | draft | Step 4.2 evidence closure recheck | Independent internal read-only closure confirmed all six evidence Required findings and the recommendations resolved: `0 OPEN`, `0 REGRESSION`. Blueprint remains draft; Step 4.3 was neither performed nor authorized. |

## Decision Notes

### 2026-08-10 — Stage 1 handoff and authorization boundary

- User authorized Step 4.1 blueprint drafting from Stage 1 audit commit `e32ec385427a5eabb4645d3a4da06cef3c9fe652`, whose repo-local audit records `Status: complete` and the frozen inputs/evidence limits.
- Stage 2 is skipped because this slice closes no load-bearing decision. Stage 3 is skipped because there is no Q-closure chain and the actionable subset is one docs-only small-gap bucket.
- The physical write scope is this hnsm-backend workflow blueprint pair only. Meander, meander-agent, factgraph-new and FactGraph runtime files remain read-only.
- Step 4.2 review, Step 4.3 preflight, Step 4.4 amendment, Step 4.5 self-check, Step 4.6 scoped anchor, Step 4.7 implementation, Step 4.8 closure, Step 4.9 archive, push and merge are distinct authorization gates.

### 2026-08-10 — Dirty-worktree preservation lock

- Fork basis: `e32ec385427a5eabb4645d3a4da06cef3c9fe652`.
- Unrelated dirty baseline: exactly 112 porcelain-v1 lines, SHA-256 `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326`; index empty at branch creation.
- This draft commit may contain only the paired blueprint files. Existing design-point index and archive inventory changes are explicitly excluded.

### 2026-08-10 — Step 4.2 Required finding disposition

| ID | Independent review finding | Disposition and applied location |
|---|---|---|
| DR-01 | O1-02 compressed independent Gate -1/DoD conditions into vague quantitative scope | **ACCEPTED.** Blueprint §4.2/INV-5/A-O1-02 now enumerate walkthrough, case bundle, claim classes, four arms, dual quote, value/access/pilot and the distinct 30%/10-offer/>50% scopes with pinned source anchors. |
| DR-02 | O1-01's discovery exception omitted named approval, budget, disposability and no-forcing-product-conclusion constraints | **ACCEPTED.** O1-01 and A-O1-01 now lock all constraints and separate pure design/audit from an experiment exception. |
| DR-03 | O1-03 did not force §1.1 from `SETTLED DIRECTION` to `PROVISIONAL` + `EXPERIMENT REQUIRED` | **ACCEPTED.** §4.2 and A-O1-03 now require both labels, Gate -1-unpassed wording and post-gate P0. |
| DR-04 | O1-06 overgeneralized graph-write failure and omitted Meander/FactGraph ownership | **ACCEPTED.** §4.2/INV-6/A-O1-06 now distinguish governance-blocked, validation-rejected, terminal rollback-success write failure and rollback-failure recovery, with Meander as owner and FactGraph/adapter excluded. |
| DR-05 | O1-09 lacked the already frozen `store.py` evidence ranges and fallback boundary | **ACCEPTED.** Exact manual/preferred-live/fallback anchors are now present in §4.2 and A-O1-09. |
| DR-06 | “one physical Git hunk = one O1” was impossible where target sections overlap | **ACCEPTED.** §5.3 now uses semantic edit atoms; a physical hunk may contain several atoms while every added/removed text span remains covered. |
| DR-07 | Stable 16 IDs/counts could conceal semantic preselection in successor prose | **ACCEPTED.** §5.4/INV-4/§7.3 require an exact 16-row non-preselection matrix with evidence. |
| DR-08 | Acceptance mixed machine checks and semantic judgment, and incorrectly required preflight to discover no Required finding | **ACCEPTED.** §7 is split into content, machine and semantic/review gates; scoped requires zero *unresolved* Required and zero Abandonment blockers after amendment. |
| DR-09 | Step 4.7 omitted the mandatory independent implementation branch | **ACCEPTED.** §4.3 and §8 pin the implementation branch forked from the scoped anchor; closure/archive remain there. |
| DR-10 | Stage allowlists omitted preflight reconciliation, standalone-audit archive and the already-dirty archive INVENTORY seam | **ACCEPTED.** §4.3 now has a stage/branch/path table and stop-on-unsafe rules for both mixed index files. |
| DR-11 | Step 4.4 amendment and Step 4.5 self-check were collapsed behind one transition | **ACCEPTED.** §8 and this audit enumerate them as separate authorization gates. |

### 2026-08-10 — Step 4.2 Recommended finding disposition

| ID | Recommendation | Disposition |
|---|---|---|
| rr-01 | Limit O1-04 to one §17 preamble rule rather than rewriting every phase | **APPLIED** in §4.2. |
| rr-02 | Limit disposition mutation to a §11 successor link/status note | **APPLIED** in §4.3, INV-11 and acceptance. |
| rr-03 | Require cached-task versus residual-user two-sided proof for mixed index files | **APPLIED** in §4.3, INV-11 and §7.2. |
| rr-04 | Explicitly record why Step 4.6.5 deletion grep is skipped and what replaces it | **APPLIED** in §8. |
| rr-05 | Call v0.1.1 a lineage successor, not formal design-point supersession | **APPLIED** in §4.3/§5.1/acceptance. |
| rr-06 | Add per-path counts, PF alignment, baseline-failure field and archive readiness to Outcome | **APPLIED** in §10. |

### 2026-08-10 — Step 4.2 internal closure recheck

- Review basis: draft commit `e180f366de8f6996d39a4684a6b33e19a9a32cac` plus the current pair-only working-tree tightening; no successor content or runtime file was reviewed as if already implemented.
- DR-01 closure: §4.2, INV-5 and A-O1-02 preserve the distinct Phase 3 promotion, Phase 3 kill/total-stop, Phase 2 Managed Translator and Gate C/total-stop scopes rather than compressing the 30%/10-offer/>50% conditions.
- DR-06 closure: Problem, §5.3 and INV-9 consistently use semantic edit atoms; physical Git hunk shape is not treated as semantic ownership.
- DR-02 through DR-05 and DR-07 through DR-11 remained `CLEAR`; the scope and governance closure checks likewise reported no open finding or regression.
- `git diff --check` passed for the blueprint pair at closure review time.
- This was an internal repository-grounded, read-only closure review. It is not a user-supplied external or cross-model review.
- Step 4.3 independent preflight was not performed and is not authorized by this record.

### 2026-08-10 — Reviewed finding not adopted

- One reviewer required a `scoped → implementing → implemented` status transition based on `workflow/blueprints/README.md`. This is **not adopted** because the repository conflict order makes `workflow/CADENCE.md` authoritative for stage transitions, and CADENCE Step 4.8 explicitly specifies `scoped → implemented`. The governance reviewer independently confirmed that this upstream documentation tension is not a defect in this blueprint. The independent Step 4.7 implementation branch is nevertheless required and is now explicit.

### 2026-08-10 — Cross-model review intake

- This commit dispositions the three repository-grounded read-only reviews run by the primary agent. If the user supplies a separate Agent review before Step 4.3, it remains a Step 4.2 input and must receive its own finding/disposition entry before preflight begins. If none is supplied, the record must say so; it must not imply that an external cross-model review occurred.
