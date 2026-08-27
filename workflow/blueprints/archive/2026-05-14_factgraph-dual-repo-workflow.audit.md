# Audit Log: factgraph Dual-Repo Workflow

Companion to [2026-05-14_factgraph-dual-repo-workflow.md](./2026-05-14_factgraph-dual-repo-workflow.md).

## Draft Audit (2026-05-14)

- Status: draft
- Scope reviewed: §1 Problem through §8 Open Questions
- No implementation yet — design only.

### User Review Round 1 (2026-05-14)

User raised 10 findings spanning naming, invariants, durability, failure
modes, scope edges, and acceptance heaviness. Triage:

| # | Topic | Type |
|---|---|---|
| 1 | master vs main | decision |
| 2 | tag SHA wording bug | text fix |
| 3 | durable sync state via footer | half-decision |
| 4 | rollback vs repair on partial push | text fix per user guidance |
| 5 | factgraph master bootstrap step missing | text fix (G0 precondition) |
| 6 | single-line release/v* as hard invariant | text fix |
| 7 | feature-branch projection privacy boundary | decision |
| 8 | revert is one-way | text fix (new invariant) |
| 9 | divergent-file deletion semantics | text fix |
| 10 | G5 acceptance too heavy | text fix |

Resolution order (per `feedback_iterative_gap_design`, one gap at a time):

- [x] Gap 1 (master/main): both repos use `master`. factgraph master to be bootstrapped from current release branch as G0 precondition. Locked into §2.2, §3, §4, §5.1-5.5, §6.1.6, §6.3, §7.G0.1.
- [x] Gap 2 (feature-branch projection cadence): **per-push transparent**. User explicitly chose A over B (release-only). Implications: factgraph remote will show feature/X for any shared-region-touching branch; rebase / amend hygiene becomes a real concern (handled via §5.2 note + Gap 3 footer detection + `--force-rewrite` escape hatch). Locked into §5.2, §7.G0.2.
- [x] Gap 3 (durable sync state + footer): 2-field footer protocol (`From-hnsm-backend` SHA + `From-hnsm-backend-branch`). Projector version field considered and dropped for simplicity. Footer is authoritative; `.git/dual-sync/<branch>` is performance cache cross-validated at each invocation. Missing footer = warn + merge-base fallback + deviation log. Stale footer (rebase) = refuse without `--force-rewrite`. Locked into §5.6, §5.7, §7.G0.3.
- [x] Gap 4 (repair, not rollback): per user finding 4, failure mode codified as "sync debt". hnsm push success + factgraph push failure → script exits non-zero with explicit status report, NO git rollback. Recovery via `dual-push.sh --repair <branch>` (skip hnsm push step) or plain rerun (idempotent). Closes §8 Q6. Locked into §5.6 step 7 + `--repair` flag + §5.9 Sync-debt handling + §7.G0.4.
- [x] Gap 5 (release/v* lifecycle + single-line + bootstrap): three sub-decisions all confirmed: 5.1 release/v* deleted after merge to master (tag is durable pointer) — closes §8 Q1; 5.2 factgraph master bootstrap from `release/v1.0.1-rc.1 @ 2bcd153f`, G0 precondition spec'd in §5.8, the post-rc.1 feature branch continues as normal feature; 5.3 tag-naming alignment deferred to §8 Q7. Single-line `release/v*` formalized as script-enforced hard invariant in §6.1.7 with `--allow-multiple-release` escape — closes §8 Q2. Caught and fixed an editing artifact: `## 6. Boundaries And Invariants` heading was accidentally consumed by an earlier Edit during Gap 3 and has been restored.
- [x] Gap 6 (G1-G5 acceptance sharpening, drop heavy G5): acceptance reorganized to G0 (design lock, sub-0.1-0.6 closed) / G1 (bootstrap) / G2 (dual-push.sh + 8 self-tests) / G3 (parity script + integration) / G4 (synthetic end-to-end with explicit test ref names, no production tag push) / G5 (docs + memory sync). Real first-release rollout moved out to a separate `first-dual-repo-release-rollout` blueprint that depends on these gates being green. Closes user finding 10.
- [x] Gap 7 (round-2 refinement: topology + tag authority + hotfix lookup): user 2026-05-14 round-2 review surfaced that the current design implies a single local hnsm clone with two remotes (not three repos), and that tag duplication is unnecessary work since Gap 3 footer already encodes the hnsm↔factgraph correspondence. Two refinements locked: (A) factgraph tag is the single release authority — hnsm-backend gets no same-name tag by default, only optional `milestone/v*` branch refs as forensic anchors (consistent with `feedback_milestone_branch_refs`); (B) hotfix-parent SHA lookup goes through `From-hnsm-backend` footer on the factgraph release tag's commit, not via hnsm-side tag matching. New §6.1.9 invariant codifies this. Added `dual-push.sh --hotfix-from <factgraph-tag>` convenience to automate the lookup. Updated §1 (topology diagram), §2.6 (tag authority), §5.4 (single-tag flow + optional milestone branch on hnsm), §5.5 (footer-lookup hotfix path), §5.6 (--hotfix-from sub-command), §6.1.2 (rewritten invariant), §6.1.9 (new invariant), §7.G4 (synthetic flow updated to single-tag).
- [x] Gap 9 (scope-freeze readiness review, 2026-05-14): self-review found 2 substantive flow gaps (A3 hotfix-during-active-rc, C2 shared-region direct-edit guard tool) + 1 spec gap (E1 `--force-delete-stalled-release` behavior detail) + 4 polish items (cross-refs / Q-numbering / usage clarity / tag format disclaimer / stale audit text). User chose decisive resolutions:
  - **A3 = park/resume flow**: when a hotfix is needed while another `release/v*` is in active stabilization, the active rc must be **parked** under `stabilization/<branch>-paused` (a namespace OUTSIDE `release/v*`) before the hotfix release branch is created. After the hotfix is released and tagged, the parked rc is resumed back to `release/v*` and absorbs the hotfix via `git merge factgraph/main`. This preserves §6.1.7 single-line invariant while avoiding the unsafe `--force-delete-stalled-release` on active branches. Drives §5.3 step 2 (parking guidance), §5.5 step 5 + step 12 (parking + resume procedures), §6.1.7 (parking exception clause), §7.G4 (synthetic parking test).
  - **C2 = independent boundary-check script**: `scripts/check-release-stabilization-boundary.sh` defined explicitly in §5.6. Three invocation modes (`<ref-or-range>`, `--staged`, `--against <base>`). Allowed: divergent allowlist (pyproject.toml, README.md, LICENSE, CHANGELOG.md, CODE_OF_CONDUCT.md, CONTRIBUTING.md, pixi.lock, .github/**). Forbidden: src/factgraph/**, tests/**. Unknown paths default to FORBIDDEN (safe-fail). Script is the testable contract; hook installation is optional and out of scope. Drives §5.6 (new script subsection), §7.G3.b (new sub-gate), §7.G4 (integrated into synthetic flow).
  - **E1 = full force-delete spec**: `--force-delete-stalled-release` requires non-empty `--reason`. Refuses on merged branches (plain delete suffices). Refuses on tagged branches (plain delete suffices). Active-stabilization gating relies on caller's `--reason` acknowledgement that the branch is stalled (active branches use the §5.5 parking flow instead). Pre-delete prints SHA + reason. Appends timestamped entry to `.git/dual-sync/release-deletions.log`. Does NOT delete tags. Drives §5.6 new sub-command block, §7.G2 expanded self-test.
  - Polish: A1 (§5.2 cross-ref fix), A4 (§5.6 usage three-form split with explicit "allowed targets apply to form 1" note), A5 (§5.8 §8.Q7→Q9 reference), F1 (§5.5 + §5.10 tag-format-illustrative disclaimer), F2 (audit "Open before scoped" section refreshed to reflect Gap 1-9 closure). Plus header Related-Modules list adds the new boundary script.
  - Acceptance side: new G0.9 sub-gate; G3 restructured into G3.a (parity) + G3.b (boundary); G2 self-tests expand `--force-delete-stalled-release` from one-line to four-bullet check; G4 synthetic flow gains explicit parking subsection + force-delete edge cases.

- [x] Gap 8 (round-3 refinement: asymmetric default branches + dev/release-manager boundary + release/v* factgraph-only): user 2026-05-14 round-3 review picked apart the remaining inconsistencies. Six sub-locks:
  - **8.A asymmetric defaults**: hnsm `master`, factgraph `main`. Scripts discover factgraph default dynamically (`git ls-remote --symref factgraph HEAD`), no hardcoded names. Supersedes Gap 1 (which locked both to `master`). Drives §2.2, §3, §4, §5.1, §5.2, §5.3, §5.6, §5.8, §6.1.6.
  - **8.B hnsm feature collection**: after dual-push, dev merges `feature/X` into hnsm `master` locally; hnsm `master` is the dev integration line with no release semantics; `git push origin master` is plain, never `dual-push.sh master`. Drives §5.2 step 6-7, §6.1.6.
  - **8.C stabilization stratification**: factgraph `release/v*` accepts divergent-files-only commits authored directly on factgraph; shared-region fixes MUST originate in hnsm and arrive via projection. Preserves §6.1.3. Drives §5.3 step 4, §6.1.3 (expanded), §5.6 (allowed-target list).
  - **8.D release/v* kept-last-1**: deletion happens only when the next `release/v*` is being created; the previous must be merged-to-main AND tagged before delete, otherwise refuse without `--force-delete-stalled-release`. Supersedes Gap 5.1 (which deleted on merge to master). Drives §5.3 step 2, §6.1.7.
  - **8.E hotfix same model**: `hnsm hotfix/X → dual-push → factgraph hotfix/X → factgraph release/v0.X.Y.Z → factgraph main → release manager tag`. Same shape as feature, scaled down. Drives §5.5 (rewritten).
  - **8.F dev / release-manager boundary**: developer phase ends at `release/v* → factgraph main` merge; release-manager phase covers tag + PyPI publish (cleanly described in new §5.10 handoff contract). Drives §2.3, §2.9, §3 (new non-goal), §5.4 (now a summary section), §5.5 step 9, §5.10 (new), §6.1.10 (new invariant).
  - Acceptance side: added G0.8 sub-gates, expanded G2 (default-branch discovery, allowed-targets, --force-delete-stalled-release self-test), restructured G4 (dev phase + release-manager phase + next-cycle hotfix verification, explicitly aligned with Gap 8 design).
  - §8 supersede notes added for Q1 (release/v* lifecycle) and the master/main decision; new Q10 raised about release-manager identity + escalation deviation-log format (does not block scope-freeze).
  - Audit trail: this is the third user review round; two prior rounds resolved Gap 1-6 (round-1) and Gap 7 (round-2). The blueprint has now absorbed every finding in user's three review messages.

### Open before scoped

All items in the original "Open before scoped" list have been resolved:

- ~~§7 acceptance criteria G0-G5 are placeholder; refine when scoping~~ — handled at Gap 6 (acceptance restructured + sharpened) and re-aligned at Gap 8 (dev/RM split) and Gap 9 (boundary-check script added to G3, force-delete enriched in G2, parking flow added to G4).
- ~~§8 open questions need user resolution~~ — Q1-Q7 all resolved. Q8/Q9/Q10 remain open but confirmed non-blocking for scope-freeze (see Gap 9 readiness review for the explicit non-blocking justification).
- ~~Confirm scripts/dual-push.sh interface~~ — finalized at Gap 9: three usage forms (primary projection / `--hotfix-from` / `--force-delete-stalled-release`), allowed/disallowed target list, default-branch discovery, footer protocol, full sub-command behavior blocks. See §5.6.
- ~~Confirm whether release/v* is deleted post-merge or retained~~ — Gap 5.1 initially said delete-on-merge; superseded at Gap 8.D (kept-last-1 with delete-on-next-create + guards) and reinforced at Gap 9.A3 (parking exception for active stabilization).

## Scoped Audit

(To be filled at scope-freeze.)

## Phase Audits

(To be filled per `feedback_audit_cadence_per_phase` once implementation begins.)

## Final Audit

### Superseded (2026-08-27)

- Status: superseded
- Successor:
  [FactGraph repository canonicalization](../active/2026-08-27_factgraph-repository-canonicalization.md)
- Reason: `hnsm-backend` was a rough shared-workflow superset, not a second
  durable FactGraph product authority. Extracting shared workflow removes the
  need for path projection, dual pushes, or a clean publication clone.
- Historical commands remain rationale only and must not be executed for new
  FactGraph work.
