# Task Blueprint Audit: Meander × FactGraph 统一设计 Review Freeze v0.1.1 文本收敛

- Status: scoped
- Created: 2026-08-10
- Last Updated: 2026-08-10
- Authority: paired blueprint audit log
- Inputs:
  - [`2026-08-10_meander-factgraph-unified-design-v0-1-1.md`](./2026-08-10_meander-factgraph-unified-design-v0-1-1.md)
  - fixed independent preflight `workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md` at commit `c59bfc77b2a7f316fd750e2d413e979fb532ea63`, blob `6f17cdfb2f73732e34fa3e07d03f7cbc2a1c8521`, SHA-256 `0b2702d36310161e7df1c29b1880c7f7d167abc4f528140cda9fe0ebc30146b4`
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
| 2026-08-10 | draft | Step 4.3 independent preflight completed | User separately authorized “可以继续”. Standalone preflight commit `c59bfc77...` produced 41 semantic atoms, an exact 16-row prospective non-preselection matrix and `5 Required / 3 Recommended / 5 Verified / 4 Scoped-detail / 0 Abandonment`; three closure reviews and a post-commit audit returned `CLEAR`. |
| 2026-08-10 | draft | Step 4.4 preflight amendment | User separately authorized “下一步”. The blueprint pair absorbed and dispositioned all five Required and three Recommended findings below; no successor, preflight artifact, source, experiment or external repository was changed. Blueprint remains `draft`; Step 4.5 is not authorized by this event. |
| 2026-08-10 | draft | Step 4.4 independent diff-check | Three read-only reviews attacked Required closure, Recommended/audit closure and cross-section consistency. Their concrete findings were amended inside the pair and all three final rechecks returned `CLEAR`; Step 4.5 remains separately gated. |
| 2026-08-10 | scoped | Preflight amendments and self-check passed | After Step 4.5 was separately authorized and returned three-way `CLEAR` with no tightening commit, the user separately authorized Step 4.6 via “下一步”. PF-R01…PF-R05 and PF-Rec01…PF-Rec03 are covered by `cfb1ccb7abfaf3e42fe6d8ac42814fad038240db`; its exact content/path allowlists are frozen as the implementation contract. This event does not authorize Step 4.6.5 or Step 4.7. |
| 2026-08-10 | scoped | Step 4.6.5 deletion-grep explicitly skipped | User separately authorized Step 4.6.5 via “下一步”. The scoped slice changes documentation only and removes no shipped symbol/API, so no deletion target or deletion grep applies. Replacement coverage is mandatory at Step 4.7: frozen predecessor hash; fixed 41-atom normalized semantic comparator and before/after guards; added-semantic-span negative scans; repository commit path allowlist; and mixed-file cached/residual two-sided proof. Any newly discovered consumer or scope issue returns to amendment. This event does not authorize Step 4.7. |
| 2026-08-10 | scoped | Step 4.7 docs content landed | User separately authorized Step 4.7 via “下一步”. The implementation content adds only the v0.1.1 Option 1 narrow lineage revision, the disposition §11 cross-link/status note, one safely isolated design-point index row, and this paired-audit event. Frozen v0.1, disposition finding rows/counts/verdicts, the exact 16 open decisions, runtime/external repositories and the fixed preflight artifact remain unchanged. Independent Step 4.7 review, Step 4.8 closure, Step 4.9 archive, push and merge remain separately gated. |

## Decision Notes

### 2026-08-10 — Stage 1 handoff and authorization boundary

- User authorized Step 4.1 blueprint drafting from Stage 1 audit commit `e32ec385427a5eabb4645d3a4da06cef3c9fe652`, whose repo-local audit records `Status: complete` and the frozen inputs/evidence limits.
- Stage 2 is skipped because this slice closes no load-bearing decision. Stage 3 is skipped because there is no Q-closure chain and the actionable subset is one docs-only small-gap bucket.
- The physical write scope is this hnsm-backend workflow blueprint pair only. Meander, meander-agent, factgraph-new and FactGraph runtime files remain read-only.
- Step 4.2 review, Step 4.3 preflight, Step 4.4 amendment, Step 4.5 self-check, Step 4.6 scoped anchor, Step 4.7 implementation, Step 4.8 closure, Step 4.9 archive, push and merge are distinct authorization gates.

### 2026-08-10 — Dirty-worktree preservation lock

- Fork basis: `e32ec385427a5eabb4645d3a4da06cef3c9fe652`.
- Unrelated dirty baseline: exact output of `git status --porcelain=v1 --untracked-files=all`, 112 lines, SHA-256 `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326`; index empty at branch creation.
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
- No **additional** user-side/cross-model Step 4.2 report was supplied before Step 4.3 began. This does not erase or downgrade the already dispositioned 28-agent adversarial review in `claude_report/`. The three same-model preflight reviews are internal independent checks and are not relabelled as cross-model evidence.

### 2026-08-10 — Step 4.3 fixed preflight intake

- Preflight branch: `v0.3.0-meander-factgraph-unified-design-v0-1-1-preflight-2026-08-10`.
- Commit / parent: `c59bfc77b2a7f316fd750e2d413e979fb532ea63` / `b392f45f2a9762c7d9225b73acb59077474ffea0`.
- Artifact: `workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md`, 353 lines, Git blob `6f17cdfb2f73732e34fa3e07d03f7cbc2a1c8521`, SHA-256 `0b2702d36310161e7df1c29b1880c7f7d167abc4f528140cda9fe0ebc30146b4`.
- Result: `5 Required / 3 Recommended / 5 Verified / 4 Scoped-detail / 0 Abandonment`; Option 1 remains viable and docs-only.
- The fixed artifact carries the sole preflight ledger/matrix/guard copy. This blueprint pins and consumes it; it does not copy a second truth source into the blueprint pair.

### 2026-08-10 — Step 4.4 Required finding disposition

| ID | Preflight finding | Disposition and applied blueprint locus |
|---|---|---|
| PF-R01 | New successor path makes repository commit diff unsuitable as a semantic comparator; 112-line baseline command was underspecified | **ACCEPTED.** Inputs/§4.1/§4.3/§5.3/INV-9/INV-10/§7.2/§8 now separate normalized predecessor→successor content diff from repository path diff, define exit `1`, limit negative checks to added semantic spans, fix `--untracked-files=all`, and preserve mixed dirty paths through residual proof rather than whole-path filtering. |
| PF-R02 | O1-02 omitted report09 `:98-106`, which carries the Phase 2 Managed Translator >50% condition | **ACCEPTED.** Inputs, O1-02, INV-5 and A-O1-02 now pin `:98-106` and state that it neither elevates research authority nor authorizes an experiment. |
| PF-R03 | O1-06 collapsed two terminal write-failure facts and treated recovery-needed `ingesting` too narrowly | **ACCEPTED.** O1-06/INV-6/A-O1-06 now distinguish PlanStore lifecycle, graph-service orchestration and adjacent ledger history; governance/validation rejection; rollback-success `PlanWriteFailure`; no-write second `WriteBoundaryError`; and all post-`create_ingesting` unexpected failures, including cases where written facts may temporarily coexist with nonterminal state. Both terminal branches retain PlanStore audit/lifecycle records but have no effective Claim state or evaluation; terminal-branch trace distinctions do not exclude nonterminal/recovery assertion/retract history. Scenario premise lifecycle remains untouched. |
| PF-R04 | O1-09 handoff anchors were one line early and ProbLog captured fallback still consults current ledger certainty | **ACCEPTED.** O1-09/INV-7/A-O1-09 now separate builder dispatch, native current-ledger probe, Soufflé/ProbLog preferred paths, Soufflé captured/minimal fallback and ProbLog hybrid fallback; use actual `self._store` lines `:3414/:3454` plus `:3488/:3518-3536`; and forbid all-path-live/fully-frozen/replay-safe claims. |
| PF-R05 | Independent preflight branch was not a stable input to the future implementation branch | **ACCEPTED.** Header/§4.1/§4.3/§5.3–5.4/INV-8–9/§7/§8/§9 pin commit/blob/content SHA and fixed `git show` consumption. Step 4.9 is three-state: absent path imports the exact blob in its own commit; exact presence skips import; nonexact presence stops for amendment/coordination and forbids overwrite, repair or archive. Only exact presence permits the later separate archive commit; floating branch/object reachability is insufficient. |

### 2026-08-10 — Step 4.4 Recommended finding disposition

| ID | Preflight recommendation | Disposition and applied blueprint locus |
|---|---|---|
| PF-Rec01 | Limit §16.4 `SETTLED DIRECTION` so it cannot close tenant/retention questions | **APPLIED.** O1-08 and A-O1-08 settle only minimum disclosure and Meander access-control boundary; CE-05/CE-06/AS-02 remain open for tenant keying and retention/erasure/legal-hold/replay precedence. |
| PF-Rec02 | Keep OEM and both/neither inside PM-03's packaging space | **APPLIED.** O1-02/INV-5/A-O1-02 state that the two quote arms neither exclude OEM nor require a unique winner. |
| PF-Rec03 | Pin mixed-file seam identities and revalidate instead of treating the current patch check as future permission | **APPLIED WITH EVIDENCE CORRECTION.** §4.3/INV-11/§7.2 pin both index/worktree identities and the tested zero-context separator seams, require index-side and worktree-side synthetic checks plus cached/residual/post-commit proofs, and stop on drift. The directly tested separator location controls over the preflight recommendation's untested “active-table tail” wording. |

### 2026-08-10 — Step 4.4 carry-forward and authorization boundary

- PF-S01…PF-S04 remain Step 4.7 guards: exact before anchors rather than successor line numbers; a fresh actual-successor 16-row matrix; one owner per semantic span even in shared hunks; and negative checks over added semantic spans only.
- The preflight branch ref must remain pinned at `c59bfc77...` until exact blob `6f17cdfb...` is present in the implementation-branch tree.
- This amendment does not check any §7 acceptance box, create a successor, run a gate/experiment, change an open decision, import the preflight artifact, or authorize Step 4.5/4.6/4.7.

### 2026-08-10 — Step 4.4 independent diff-check closure

- Three independent read-only passes reviewed the actual amendment diff: PF-R01…PF-R05 mapping, PF-Rec01…PF-Rec03 plus audit authority, and end-to-end blueprint consistency.
- Review-found corrections were applied only inside this pair: Step 4.9 now has absent/exact/nonexact fail-closed states; O1-06 preserves terminal PlanStore audit records while denying effective Claim state/evaluation; O1-09 separates dispatch, native probe, preferred current-store paths and captured/hybrid fallbacks.
- Final results: Required `CLEAR`; Recommended/audit `CLEAR`; consistency/threat review `CLEAR`; unresolved Required `0`; Abandonment blockers `0`.
- `git diff --check` passed; index remained empty; exact exclusion of the two previously clean task paths restored the unrelated `git status --porcelain=v1 --untracked-files=all` baseline to 112 lines and SHA-256 `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326`.
- Blueprint status remains `draft`. This closure completes Step 4.4 only and does not authorize Step 4.5.
