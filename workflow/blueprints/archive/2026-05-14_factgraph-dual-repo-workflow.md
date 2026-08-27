# Task Blueprint: factgraph Publish Projection Runbook

- Status: superseded
- Created: 2026-05-14
- Last Updated: 2026-08-27
- Superseded By:
  - [FactGraph repository canonicalization](../active/2026-08-27_factgraph-repository-canonicalization.md)

> Historical rationale only. The dual-repository projection topology and every
> command below are superseded. Current FactGraph work uses one canonical
> repository whose `origin` is `Symbolic-Intelligence-Org/factgraph`; shared
> workflow moves to `symbolic-workflow`.
- Related Modules:
  - `scripts/release.sh` (existing; not modified by this blueprint)
  - Projection tool (new; small wrapper around `git push factgraph`)
- Related Docs:
  - [feedback_blueprint_workflow](../../../memory/feedback_blueprint_workflow.md)
  - [feedback_release_workflow_traps](../../../memory/feedback_release_workflow_traps.md)
  - [feedback_push_master_gate](../../../memory/feedback_push_master_gate.md)
  - [project_release_branch_invariants](../../../memory/project_release_branch_invariants.md)
- Audit Log:
  - [2026-05-14_factgraph-dual-repo-workflow.audit.md](./2026-05-14_factgraph-dual-repo-workflow.audit.md)

## 1. Problem

On 2026-05-14 the codebase finished a structural split between two GitHub repos:

- **hnsm-backend** (`Symbolic-Intelligence-Org/hnsm-backend.git`) — private full-content repo. Contains `src/factgraph`, `src/agent`, `src/service`, `src/domains`, `docs/`, blueprints, scripts, memory, etc. Not the publish target.
- **factgraph** (`Symbolic-Intelligence-Org/factgraph.git`) — public release repo. Contains the public-package subset plus release scaffolding.

A developer uses **one local clone of hnsm-backend** with two configured Git remotes — `origin` = hnsm-backend, `factgraph` = the public release repo. A separate release manager tags and publishes from factgraph.

This blueprint is a **runbook**, not a full workflow design. It exists to lock down four boundaries that prevent publish accidents:

1. Leaking internal-only paths (`src/agent`, `docs/`, hnsm's own `pyproject.toml`, etc.) into factgraph.
2. factgraph drifting from hnsm because somebody edited shared code directly on the public side.
3. PyPI publishing from an unauthorized source or out-of-sync version.
4. Push failures leaving the two repos in an inconsistent state that's hard to recover from.

Everything else — branching mechanics, rebase strategy, CI integration, release-manager mechanics — is **out of scope** by design.

## 2. Goals

1. **Path allowlist**: only `src/factgraph/**` and `tests/**` project from hnsm to factgraph. Nothing else.
2. **factgraph never originates shared-region commits**: any change to `src/factgraph/**` or `tests/**` arrives in factgraph by projection from hnsm, carrying a `From-hnsm-backend: <sha>` footer for traceability.
3. **Tag authority lives on factgraph**: the factgraph tag is the PyPI source. hnsm does not tag releases (optional `milestone/v*` branch refs only, for internal forensics).
4. **Push failure = catch up, never rollback**: if `git push origin` succeeds but the factgraph projection push fails, the hnsm push stays. Fix the cause and push factgraph again.
5. **A minimal projection tool exists** so 1 + 2 are mechanically enforced, not just discipline.

## 3. Non-goals

- Not a comprehensive git/branching tutorial. The procedure below uses plain `git` commands — anything not stated is left to operator judgement.
- Not supporting concurrent `release/v*` branches. One at a time on factgraph.
- Not supporting hotfix-during-active-release as a normal path: finish or formally abandon the active release first.
- Not designing CI/CD integration on either repo.
- Not synchronizing factgraph's `pyproject.toml`, `pixi.lock`, `LICENSE`, `README.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `.github/` back to hnsm. These are factgraph-owned.
- Not maintaining hnsm-side release tags. PyPI publishes from factgraph tag only.
- Not deciding tag naming schema. Deferred to §8.
- Not specifying release-manager identity, handoff signal, or escalation log format. Deferred to §8.
- Not micromanaging rebase / amend / `release/v*` cleanup. Operator discipline.

## 4. Current Context

- hnsm-backend default branch: `master @ 99452270` (origin). Stays as `master`; sacred per `project_release_branch_invariants`.
- factgraph default branch: not yet created. Existing refs on factgraph: `release/v1.0.1-rc.1 @ 2bcd153f`, tags `v0.1.0rc1` / `v0.1.0rc2`, and `feature/factgraph-post-rc1-2026-05-14 @ 35ad6662` (today's one-off manual projection).
- Shared region: `src/factgraph` (243 files) + `tests/` (123 files; tree hash `06688b6502a3e67ce86b028cb5bcf1376a7c0b61` already matches factgraph release/v1.0.1-rc.1).
- Local remote alias `factgraph` set up; push permission verified for `GigaGaiaWorld`.
- Bootstrap not yet executed (§5.1).

```
local hnsm-backend  <─bidirectional─►  origin/hnsm-backend     (full development truth)
local hnsm-backend  ──one-way projection──►  factgraph         (shared region only)
factgraph tag                          ──►  PyPI publish       (release manager)
```

Default branch names are asymmetric: hnsm `master`, factgraph `main`. Working branches (`feature/X`, `hotfix/X`) keep identical names across both repos when shared region is involved. `release/v*` lives only on factgraph.

## 5. Procedure

### 5.1 Bootstrap (one-time)

```bash
git fetch factgraph
git push factgraph factgraph/release/v1.0.1-rc.1:refs/heads/main
gh -R Symbolic-Intelligence-Org/factgraph repo edit --default-branch main
# Optional: enable branch protection on factgraph main in the GitHub UI.
```

After bootstrap, `factgraph main` is the **release-only line**. Direct commits to it are forbidden; only `release/v*` (and hotfix-driven `release/v*`) merges in.

### 5.2 Daily feature flow

```
1. git checkout master && git pull origin master    (in local hnsm-backend)
2. git checkout -b feature/X
3. (work; commit on hnsm-backend)
4. git push origin feature/X
5. Run the projection tool against feature/X.
   - Tool copies src/factgraph + tests only (allowlist-enforced).
   - Tool appends footer:
       From-hnsm-backend: <hnsm-sha>
       From-hnsm-backend-branch: feature/X
   - Tool pushes to factgraph feature/X.
6. When feature is done from hnsm's perspective (regardless of release plans):
       git checkout master && git merge --no-ff feature/X
       git push origin master
   This is a plain push. hnsm `master` is the dev integration line and has
   no release semantics; it never projects to factgraph.
7. (Optional) delete hnsm feature/X.
```

If `feature/X` touches no shared region, step 5 is a no-op on factgraph.

### 5.3 Release flow

When one or more features are ready for the next public release:

```
1. Decide which factgraph feature branch(es) seed the release. This is the
   deliberate "ready" moment — not every feature gets a release.

2. Ensure no other release/v* is open on factgraph. If a prior release/v*
   exists from a completed release and is no longer needed, delete it:
       git push factgraph --delete release/v0.1.0-rc.3

3. Create release/v0.1.0-rc.4 on factgraph from the chosen feature tip:
       git push factgraph factgraph/feature/X:refs/heads/release/v0.1.0-rc.4
   (No hnsm-side release/v* branch is ever created.)

4. Stabilization on factgraph release/v0.1.0-rc.4:
   - Divergent-files-only commits (CHANGELOG, pyproject hatch-vcs config,
     pixi.lock, README, .github/ workflows) may be authored directly on
     factgraph release/v*. They never project back to hnsm.
   - Shared-region fixes (src/factgraph, tests) MUST originate in hnsm and
     arrive via the projection tool. Pattern: add commits to the hnsm
     feature branch (or a small fix-up branch), re-run projection, then
     fast-forward / merge the projected feature into release/v* on factgraph.

5. Merge release/v0.1.0-rc.4 → factgraph main (factgraph-side operation).

6. Developer phase ends here. Hand off to release manager.

7. (Release manager) Tag factgraph main with v0.1.0-rc.4, push tag,
   `python -m build && twine upload dist/*`. hatch-vcs derives PyPI version
   from the tag.
```

The release manager phase is a separate role: the developer's last action is the merge to factgraph `main`. The footer on the merge commit (`From-hnsm-backend: <sha>`) records which hnsm-backend state produced the release.

### 5.4 Hotfix flow

If a bug needs to ship as a patch on an already-released version (e.g., `v0.1.0-rc.3` has a defect):

```
1. Find the hnsm anchor via the factgraph release tag's footer:
       git fetch factgraph
       hnsm_sha=$(git log -1 --format=%B v0.1.0-rc.3 \
           | sed -n 's/^From-hnsm-backend: //p')

2. git checkout -b hotfix/X $hnsm_sha    (on local hnsm-backend)

3. Fix; commit on hotfix/X.

4. git push origin hotfix/X
   Run projection tool: hotfix/X → factgraph hotfix/X.

5. On factgraph: create release/v0.1.0-rc.3.1 from the tagged release commit,
   then merge hotfix/X into it:
       git push factgraph factgraph/refs/tags/v0.1.0-rc.3^{commit}:refs/heads/release/v0.1.0-rc.3.1
       (then merge factgraph/hotfix/X into release/v0.1.0-rc.3.1 on factgraph side)

6. Merge release/v0.1.0-rc.3.1 → factgraph main.

7. Locally on hnsm: merge hotfix/X back into hnsm master; push origin master.

8. Developer phase ends. Release manager tags v0.1.0-rc.3.1 and publishes.

9. Delete hotfix/X on both remotes.
```

**Constraint**: if an active `release/v0.1.0-rc.4` is in progress when a hotfix is needed, finish it (release-manager tagged) or formally abandon (delete the branch with explicit operator decision) BEFORE starting the hotfix. This blueprint does not support running both in parallel.

### 5.5 Failure handling

If `git push origin <branch>` succeeds but the subsequent factgraph projection push fails (network, transient auth, branch protection, push race):

- **Do NOT rollback the origin push.** Rewriting a published shared branch is more dangerous than carrying a temporary mismatch.
- The projection tool exits non-zero with an explicit status report.
- Fix the underlying cause, re-run the projection tool. The tool re-projects from the last known sync point — read from the `From-hnsm-backend` footer on the current factgraph branch tip, falling back to merge-base if the footer is missing.

Same rule applies if `git push factgraph <ref>` fails when establishing a `release/v*` or merging to main: do not roll back any prior successful push; resolve and retry.

### 5.6 Projection tool — minimal contract

The projection tool is whatever script or wrapper implements these requirements. It is the only mechanism that places shared-region content on factgraph.

**MUST do:**

- Compute the changed shared paths (`src/factgraph/**` and `tests/**`) in the hnsm branch since the last sync point.
- Produce a factgraph commit whose tree equals the parent factgraph tree with `src/factgraph` and `tests/` replaced by the hnsm branch HEAD's corresponding subtrees (tree-replace, not diff-patch — handles deletions correctly).
- Append two footer trailers to the commit message:
  ```
  From-hnsm-backend: <40-hex hnsm HEAD SHA>
  From-hnsm-backend-branch: <hnsm branch name; must equal factgraph branch name>
  ```
- Push the resulting factgraph branch.
- On failure after `git push origin` succeeded, exit non-zero with a clear report and DO NOT rollback origin.

**MUST NOT do:**

- Copy any path outside `src/factgraph/**` and `tests/**`.
- Push to `factgraph master` (does not exist), `factgraph main` (only updated via release/v* merge), or arbitrary branches outside `feature/*` / `hotfix/*`.
- Author shared-region commits without the footer.
- Roll back a successful `git push origin` if the subsequent factgraph push fails.

The tool's CLI shape (single-form `tool <branch>`, additional convenience flags, caching strategy, etc.) is an implementation choice and not pinned by this blueprint.

## 6. Invariants and Allowlists

### 6.1 Invariants (always hold)

1. **Path allowlist** (§5.6): the projection tool copies only `src/factgraph/**` and `tests/**`. Nothing else moves from hnsm to factgraph.
2. **Shared-region origin = hnsm**: every factgraph commit whose tree changes `src/factgraph/**` or `tests/**` carries a `From-hnsm-backend: <sha>` footer. Direct factgraph edits to those paths are forbidden.
3. **Tag authority = factgraph**: PyPI version derives from the factgraph tag (via `hatch-vcs`). hnsm-backend does not carry a same-name release tag. Optional `milestone/v*` branch refs on hnsm are non-load-bearing forensics.
4. **Failure mode = catch up, never rollback**: a successful `git push origin` is never undone if a later factgraph push fails. The mismatch is resolved by re-running projection.
5. **One `release/v*` at a time on factgraph**. No parallel rc, no parallel hotfix-rc + ongoing-rc. Operator decides which one is alive.

### 6.2 Allowlist tables

**Shared** (projects from hnsm → factgraph):

- `src/factgraph/**`
- `tests/**`

**Divergent** (factgraph-owned; not projected from hnsm; not synced back):

- `pyproject.toml`
- `README.md`
- `LICENSE`
- `CHANGELOG.md`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `pixi.lock`
- `.github/**`

**hnsm-internal** (never project; live only on hnsm):

- `src/agent/**`, `src/service/**`, `src/domains/**`
- `docs/**`
- `memory/**`
- `scripts/**`
- everything else not in the shared or divergent lists

### 6.3 Related memory anchors

- `feedback_push_master_gate`: never auto-push hnsm `master`. After merging a feature into hnsm `master` (§5.2 step 6), `git push origin master` is a deliberate act.
- `feedback_release_workflow_traps`: 6 known release-script traps. Continue to apply when invoking `scripts/release.sh` for PyPI mechanics.
- `feedback_milestone_branch_refs`: hnsm uses `refs/heads/milestone/...` for snapshots, not tags. Optional anchors for releases (forensic only).
- `project_release_branch_invariants`: existing `release/0.1.x` and `master` in hnsm-backend remain sacred; this blueprint does not modify them.

## 7. Acceptance

Minimal. Real first release is a separate blueprint.

- [ ] **G0**: Design locked (this blueprint reaches `scoped` status).
- [ ] **G1**: factgraph `main` bootstrapped from `release/v1.0.1-rc.1 @ 2bcd153f` per §5.1; default branch on GitHub is `main`; pre-existing tags untouched; hnsm `master` untouched.
- [ ] **G2**: Projection tool exists and the §5.6 contract is verified by self-tests:
  - Project a `feature/X` that touches only `src/factgraph` and `tests/` → succeeds; factgraph commit carries the footer.
  - Project a `feature/X` that touches only hnsm-internal paths (`docs/`, `src/agent/`) → factgraph no-op.
  - Project a `feature/X` that touches both shared and internal → only shared content arrives on factgraph; internal stays out.
  - Simulated factgraph-push failure after a successful origin push → tool exits non-zero; hnsm push is not rolled back; re-run catches up.
- [ ] **G3**: Synthetic end-to-end dry-run on test refs (no production tag push, no PyPI publish):
  - `feature/test-projection` → projection → factgraph `feature/test-projection` → factgraph `release/v-test-1` → factgraph `main` → local-only tag `v-test-1` → `python -m build` (no upload).
  - Tag footer correctly identifies the hnsm anchor SHA.
  - `dual-push.sh` (or whatever the projection tool ends up named) `--hotfix-from v-test-1` resolves the anchor SHA correctly.
- [ ] **G4**: Docs sync — `docs/blueprints/README.md` references this runbook under a "Cross-repo workflow" entry; one memory anchor under `memory/` records the 5 invariants of §6.1 so future sessions do not relitigate them.

## 8. Open Questions (non-blocking)

1. **Tag-naming schema**: hnsm uses `v0.1.0-rc.x`; factgraph existing release branch uses `v1.0.1-rc.1`. Next tag schema is undecided. Workflow is independent of the chosen string format. Resolve at next tag cut.
2. **Release-manager identity + escalation policy**: §5.3 step 7 assumes a release-manager role exists. Assignee (Raphael per pyproject co-author, or CI bot via Trusted Publishers, or rotating duty) and the "dev escalation if RM unavailable" policy are out of scope here. To be decided when the first real release lands.
3. **Optional boundary-check script** for direct factgraph `release/v*` edits during stabilization (catches accidental shared-region commits by hand): not implemented. Default is operator discipline + the projection tool's allowlist guarantee. If a real incident makes this worthwhile, add as a separate small blueprint.
4. **Internal-only test files broken by the 2026-05-14 `src/kernel/tests` deletion** (`src/agent/tests/`, `src/domains/*/tests/`): a separate cleanup blueprint, independent of this runbook.

## Outcome

(To be filled at implemented phase.)

## Deviations

(To be filled at implemented phase.)
