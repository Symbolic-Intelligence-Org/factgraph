# Task Blueprint: factgraph Dual-Repo Workflow

- Status: draft
- Created: 2026-05-14
- Last Updated: 2026-05-14
- Related Modules:
  - `scripts/release.sh` (existing; to be complemented, not replaced)
  - `scripts/dual-push.sh` (new; to be implemented post-scope)
  - `scripts/verify-shared-region-parity.sh` (new; invariant check)
  - `pyproject.toml` (divergent file; not synced)
- Related Docs:
  - [Friend's gist branching model](https://gist.github.com/digitaljhelms/4287848)
  - [feedback_blueprint_workflow](../../../memory/feedback_blueprint_workflow.md)
  - [feedback_release_workflow_traps](../../../memory/feedback_release_workflow_traps.md)
  - [feedback_push_master_gate](../../../memory/feedback_push_master_gate.md)
  - [project_release_branch_invariants](../../../memory/project_release_branch_invariants.md)
- Audit Log:
  - [2026-05-14_factgraph-dual-repo-workflow.audit.md](./2026-05-14_factgraph-dual-repo-workflow.audit.md)

## 1. Problem

On 2026-05-14 the codebase finished a structural split between two GitHub repos:

- **hnsm-backend** (`Symbolic-Intelligence-Org/hnsm-backend.git`) — private full-content repo. Contains `src/factgraph`, `src/agent`, `src/service`, `src/domains`, `docs/`, blueprints, internal scripts, memory, etc. No longer the publish target.
- **factgraph** (`Symbolic-Intelligence-Org/factgraph.git`) — public release repo. Contains only `src/factgraph` + `tests/` + release-form scaffolding (`pyproject.toml`, `pixi.lock`, `LICENSE`, `README.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `.github/`).

**Topology** (made explicit at Gap 7, 2026-05-14): developers use **one local clone of hnsm-backend** with two configured Git remotes — `origin` pointing at hnsm-backend, and `factgraph` pointing at the public release repo. There is no separate "factgraph clone" used for daily development. factgraph is purely a remote target.

```
local hnsm-backend  <─bidirectional─>  origin/hnsm-backend     (full development truth)
local hnsm-backend  ──one-way projection──►  factgraph         (shared region only)
factgraph tag                          ──►  PyPI publish       (release authority)
```

`git fetch factgraph` is used to read remote state (branches, tags, footers of existing projection commits) but never absorbs business changes back into hnsm-backend. Divergent files (`pyproject.toml`, `pixi.lock`, etc.) are edited on factgraph and never flow back.

Today the first cross-repo commit landed as a one-off manual operation (`feature/factgraph-post-rc1-2026-05-14 @ 35ad6662` on the factgraph remote, built from a `/tmp` worktree rooted at `factgraph_test/release/v1.0.1-rc.1`). Going forward this needs a stable, repeatable workflow covering: branch naming, sync cadence, release path through `release/v*` and `master`, tagging, hotfix handling, and divergence rules.

Without an explicit workflow:

- branches in the two repos will drift in naming and HEAD;
- developers may push uneven shared-region states to factgraph;
- release artifacts may disagree across repos (different `src/factgraph` content under the same tag);
- divergent files (pyproject.toml etc.) may get accidentally synced and break factgraph's hatch+pixi build.

## 2. Goals

1. Define a single source-of-truth direction: **hnsm-backend → factgraph** projection. factgraph never originates business-logic commits.
2. Same-name branches across both repos when shared region is involved (`feature/X`, `release/v*`, `master`, `hotfix/X` all use identical names). Both repos use `master` as the default branch; modern `main` convention is explicitly declined to avoid touching sacred `master` refs already established in hnsm-backend memory and tooling (Gap 1 resolution, 2026-05-14).
3. Define the release pipeline: `feature/* → release/v* → master → tag master → publish`. Force a deliberate "is this ready for release" gate at the feature → release/v* merge.
4. Hotfix path: `hotfix/X` branches from latest tag on `master`, merges back to `master`, gets a new patch tag (gist-style fast lane, no `release/v*` detour).
5. Sync cadence: **per-push**. When a developer pushes hnsm-backend with shared-region changes, the same push action projects to factgraph. Atomic at push time, not commit time.
6. Version + tag authority: **factgraph**. factgraph's `pyproject.toml` uses `hatch-vcs` to derive version from the tag, and the tag itself is created on factgraph (not on hnsm-backend). hnsm-backend does not carry the same tag by default. Optional `milestone/v*` branch refs on hnsm-backend may be used as forensic anchors (per `feedback_milestone_branch_refs`) but are not load-bearing on the release pipeline. hnsm-backend's `pyproject.toml` version remains advisory only — not source of truth for PyPI.
7. PyPI publish: both `rc` and `final` tags publish to PyPI from the factgraph repo (matches the v0.1.0-rc.1 precedent).
8. Tooling: a `scripts/dual-push.sh` script implementing the projection, plus a `scripts/verify-shared-region-parity.sh` invariant checker. Both live in hnsm-backend.

## 3. Non-goals

- Not changing factgraph's existing `release/v1.0.1-rc.1` branch or the v0.1.0rc1 / v0.1.0rc2 tags.
- Not rewriting `scripts/release.sh`. This blueprint complements it; `release.sh` may still drive PyPI publish from factgraph in a future iteration.
- Not auto-syncing every hnsm-backend commit via a post-commit hook. Push-time projection is the explicit chosen cadence.
- Not handling more than one active `release/v*` branch at a time. Concurrent release lines are out of scope.
- Not bridging pyproject.toml or any non-shared file. These are accepted divergences.
- Not synchronizing factgraph-only scaffolding edits (pixi.lock updates, README authoring, CI yaml tweaks) back to hnsm-backend. Those live only in factgraph.
- Not introducing a `develop` branch or any GitFlow construct beyond `feature/*`, `release/v*`, `master`, `hotfix/*`.
- Not renaming hnsm-backend's `master` to `main`. A future migration may be done as an independent blueprint; this one does not depend on it.

## 4. Current Context

- hnsm-backend default branch: `master @ 99452270` (origin). Sacred per `project_release_branch_invariants`; stays as `master`.
- factgraph default branch: not yet created; only `release/v1.0.1-rc.1 @ 2bcd153f` + `feature/factgraph-post-rc1-2026-05-14 @ 35ad6662` exist. A `master` branch will be bootstrapped from `release/v1.0.1-rc.1 @ 2bcd153f` as a G0 precondition of this workflow (see §5.8 Bootstrap). The post-rc.1 feature branch continues to live as a normal feature branch and will eventually merge through `release/v*` gate.
- factgraph tags on origin: `v0.1.0rc1 @ f4aa551e`, `v0.1.0rc2 @ 96152547`. Both immutable.
- hnsm-backend tags: `v0.1.0-rc.1`, `v0.1.0-rc.2` (per memory `project_v0_1_0_rc1_published`). Plus milestone branch refs under `refs/heads/milestone/...`.
- Local hnsm-backend remote alias: `factgraph` (set on 2026-05-14 after the factgraph_test → factgraph repo rename).
- Push permission verified for `GigaGaiaWorld` on the factgraph repo (admin/maintain/push all true).
- Shared region paths: `src/factgraph` (243 files post-rename) + `tests/` (123 files, tree hash `06688b6502a3e67ce86b028cb5bcf1376a7c0b61` identical to remote release branch).
- Divergent file inventory: `pyproject.toml`, `README.md`, `LICENSE`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `pixi.lock`, `.github/`, plus all hnsm-internal paths (`src/agent`, `src/service`, `src/domains`, `docs/`, `memory/`, `scripts/`, etc.).
- Active worktrees: main (`/Users/zhenzhili/hnsm-backend @ master`), this rename worktree (`.claude/worktrees/hardcore-mahavira-2155e3 @ claude/hardcore-mahavira-2155e3`), one detached dryrun, one uncertainty-transmission topic worktree.

## 5. Proposed Shape

### 5.1 Branching graph

```
hnsm-backend (full):                                                tag v0.1.0-rc.4
                                                                         ▼
master ─────────────────────────────────────────────────────────────────●─────►
                              │                                        ╱
release/v0.1.0-rc.4 ──────────●──●(version bump, CHANGELOG, QA fix)──●
                              ▲                                     
                              │ (merge --no-ff, deliberate gate)
                              │
feature/A ──●──●──●──●────────●           ← may include internal-only commits
feature/B ──●──●──●──●───●────●(later)    ← same
hotfix/Z   ←─ from tag v0.1.0-rc.3 ─→ merge back to master → tag v0.1.0-rc.3.1


factgraph (shared region only):                                     tag v0.1.0-rc.4
                                                                         ▼
master ─────────────────────────────────────────────────────────────────●─────► PyPI publish
                              │                                        ╱
release/v0.1.0-rc.4 ──────────●───────────●(CHANGELOG, pyproject.toml in factgraph)─●
                              ▲                                     
                              │
feature/A ──●─────────────────●           ← 0..N projected commits (only shared-region delta)
feature/B ──●─────────────────●           ← same
hotfix/Z   ←─ from tag v0.1.0-rc.3 ─→ merge back to master → tag v0.1.0-rc.3.1
```

Same branch names, identical lifecycle, parallel commits when shared region is involved.

### 5.2 Daily flow (feature development)

1. `git checkout master && git pull origin master` in hnsm-backend.
2. `git checkout -b feature/X`.
3. Work on hnsm-backend. Commits may touch anything (shared region + internal).
4. When ready to publish progress: `scripts/dual-push.sh feature/X`.
   - The script pushes `feature/X` to `origin` (hnsm-backend).
   - Detects commits since last sync point that touched `src/factgraph` or `tests/`.
   - If any: projects a single new commit onto factgraph's `feature/X`, parented on factgraph's `master` (which must exist per §5.7 bootstrap; the script does not guess parents at runtime).
   - Pushes factgraph branch.
5. If `feature/X` touches no shared region at all, the script is a no-op for factgraph (only hnsm-backend gets pushed). factgraph branch is never created.

**Rebase / amend hygiene (Gap 2 + Gap 3 interlock):**

Once a hnsm-backend `feature/X` commit has been projected to factgraph, subsequent rebase / amend / force-push of that commit on hnsm-backend creates a divergence:

- factgraph's `feature/X` already published commit(s) marked with `From-hnsm-backend-end: <old-sha>` (see Gap 3 footer).
- The new (rebased) hnsm-backend commit has a different SHA. `dual-push.sh` will detect the footer ≠ branch state and refuse without `--force-rewrite`.
- `--force-rewrite` force-pushes factgraph `feature/X` to a new projection of the rewritten hnsm-backend HEAD. Public callers tracking the old SHA may need to refetch.

Recommended discipline: treat `feature/X` as append-only after first `dual-push`. Reserve rebases for pre-first-push cleanup.

### 5.3 Feature → release/v* gate

1. Decide that `feature/X` is ready for the next release. This is the deliberate "ready" moment.
2. Ensure `release/v0.1.0-rc.4` exists. If not: `git checkout -b release/v0.1.0-rc.4 master` on both repos (only on factgraph if shared region exists).
3. On hnsm-backend: `git checkout release/v0.1.0-rc.4 && git merge --no-ff feature/X`.
4. `scripts/dual-push.sh release/v0.1.0-rc.4` — pushes release branch on hnsm-backend, projects to factgraph release branch.
5. Stabilization commits go directly onto `release/v0.1.0-rc.4` (version bump in hnsm pyproject, CHANGELOG entries in factgraph, last-mile QA fixes). Each one is dual-pushed.

### 5.4 Release / tag / publish

(Refined at Gap 7, 2026-05-14: tag authority single-sourced on factgraph; hnsm does not get a same-name tag.)

1. Verify `scripts/verify-shared-region-parity.sh release/v0.1.0-rc.4` shows `src/factgraph` + `tests/` tree hashes identical between hnsm-backend and factgraph.
2. On hnsm-backend: `git checkout master && git merge --ff-only release/v0.1.0-rc.4` (FF preferred to keep master linear).
3. `scripts/dual-push.sh master` (pushes hnsm origin master + projects to factgraph master).
4. **Tag only on factgraph** (factgraph is the release authority; hatch-vcs derives PyPI version from this tag):
   ```bash
   git -C <local-hnsm-clone> tag -a v0.1.0-rc.4 \
       --message "..." \
       factgraph/master
   git push factgraph v0.1.0-rc.4
   ```
   The tag points at the factgraph master HEAD commit. The factgraph commit's footer (`From-hnsm-backend: <hnsm-sha>`) serves as the durable back-pointer to the hnsm-backend commit that produced this release; no hnsm-side tag is required.
5. (Optional, recommended for forensic / incident anchor) Create a hnsm-backend milestone branch ref pointing at the hnsm release commit:
   ```bash
   git -C <local-hnsm-clone> branch milestone/v0.1.0-rc.4 master
   git -C <local-hnsm-clone> push origin milestone/v0.1.0-rc.4
   ```
   This follows the existing `feedback_milestone_branch_refs` convention. It is not load-bearing on the release; hotfix lookup uses footer (§5.5), not the milestone branch.
6. From a local clone with factgraph configured: `python -m build && twine upload dist/*` (PyPI publish). The hatch-vcs plugin picks up `v0.1.0-rc.4` automatically.
7. Delete `release/v0.1.0-rc.4` on both remotes. The factgraph tag is the durable historical pointer; the release branch ref is operational state and is removed on every release to keep the remote `release/v*` set always representing only the active stabilization line (or empty between releases). Reactivation of a deleted release branch is forbidden — start a new one if needed.

### 5.5 Hotfix path

(Refined at Gap 7, 2026-05-14: hotfix parent SHA on hnsm-backend is looked up via the factgraph release tag's commit footer; no hnsm-side tag is required.)

1. **Lookup hnsm-backend anchor SHA from the factgraph release tag's footer**:
   ```bash
   git fetch factgraph
   factgraph_tag=v0.1.0-rc.3
   hnsm_anchor=$(git log -1 --format=%B factgraph/refs/tags/$factgraph_tag \
       | sed -n 's/^From-hnsm-backend: //p')
   ```
   Or use the convenience flag: `scripts/dual-push.sh --hotfix-from $factgraph_tag` (see §5.6) which performs the lookup + checkout in one step.

2. Branch on hnsm-backend at the anchor:
   ```bash
   git checkout -b hotfix/X $hnsm_anchor
   ```
   The anchor SHA is guaranteed reachable from hnsm master (master is FF-only per §6.1.6, so once a release/v* merged in, its tip lives in master history forever even after release/v* deletion).

3. Fix. Commit(s) on hnsm-backend `hotfix/X`.
4. `scripts/dual-push.sh hotfix/X` — projects shared region to factgraph `hotfix/X` (footer back-reference will point to the new hnsm hotfix HEAD).
5. Verify shared-region parity: `scripts/verify-shared-region-parity.sh hotfix/X`.
6. Merge to master on both repos: `git checkout master && git merge --no-ff hotfix/X`.
7. `scripts/dual-push.sh master`.
8. Tag factgraph (only): `git tag -a v0.1.0-rc.3.1 -m "..." factgraph/master && git push factgraph v0.1.0-rc.3.1`.
9. (Optional) milestone branch on hnsm: `git branch milestone/v0.1.0-rc.3.1 master && git push origin milestone/v0.1.0-rc.3.1`.
10. Publish from factgraph (PyPI).
11. (If there's an active `release/v0.1.0-rc.4` branch already, the next stabilization commit on it must `git merge master` to absorb the hotfix into the ongoing stabilization line.)
12. Delete `hotfix/X` on both remotes after merge.

### 5.6 Tooling

#### scripts/dual-push.sh

```
Usage:
  scripts/dual-push.sh <branch> [--squash | --keep-granular] [--force-rewrite] [--repair] [--dry-run]
  scripts/dual-push.sh --hotfix-from <factgraph-tag>  [--into <hotfix-branch-name>]

Behavior:
  1. Sync-debt self-check (before any push):
     - Read footer From-hnsm-backend: <last> on factgraph/<branch> HEAD.
     - If <last> is behind hnsm/<branch> HEAD: WARN "sync debt: N hnsm commits
       since <last> not yet projected" but proceed (the projection step will
       cover the range; this is the recovery path for any prior dual-push
       that failed mid-way).
  2. If --repair is set, SKIP step 3 (do not push hnsm; assume hnsm already
     ahead due to a prior failed sync). Otherwise:
  3. git push origin <branch>  (hnsm-backend; respects feedback_push_master_gate)
  4. Determine <last-sync-sha> for the projection range:
     a. Read factgraph/<branch> HEAD commit message footer From-hnsm-backend: <sha>.
        - Cross-validate against .git/dual-sync/<branch> cache; mismatch → trust footer, refresh cache.
        - Verify footer's From-hnsm-backend-branch == <branch>; mismatch → refuse.
     b. If factgraph/<branch> does not exist (first projection):
        Parent for new branch = factgraph/master (assumed bootstrapped per §5.8).
        <last-sync-sha> = merge-base(hnsm/<branch>, factgraph/master tree's hnsm-backend mapping)
        — pragmatically the script falls back to the first hnsm-backend commit that touches
        shared region on this branch. Records deviation if ambiguous.
     c. If footer is absent from factgraph/<branch> HEAD (externally-pushed commit):
        WARN, fall back to merge-base(hnsm/<branch>, hnsm/master), continue, append a
        deviation entry to .git/dual-sync/<branch>.deviations.log.
     d. If From-hnsm-backend: <sha> is not an ancestor of hnsm/<branch>'s HEAD
        (rebase/reset detected):
        Refuse unless --force-rewrite is passed. With --force-rewrite, the projection
        is built from factgraph/master parent and force-pushed.
  5. Walk commits in (<last-sync-sha>..hnsm/<branch>]. If none touched src/factgraph or tests/:
     exit (no factgraph push needed; hnsm push already done in step 3).
  6. Build factgraph projection commit:
     - Parent = current factgraph/<branch> HEAD (or factgraph/master if branch is new
       or --force-rewrite).
     - Tree = parent's tree with src/factgraph and tests subtrees replaced by hnsm/<branch>
       HEAD's corresponding subtrees (tree-replace, NOT diff patch — handles deletions
       within shared region automatically; ignores divergent files entirely).
     - Message:
         Either condensed (single commit summarizing range, default) or per-commit
         (granular projection) per --keep-granular.
         MUST include footer:
           From-hnsm-backend: <hnsm-backend HEAD full SHA>
           From-hnsm-backend-branch: <branch>
  7. git push factgraph <branch>  (regular push, or --force-with-lease under --force-rewrite).
     - On push failure: do NOT rollback origin push from step 3. Print clear
       sync-debt status and exit non-zero with instructions to retry via
       `dual-push.sh --repair <branch>` once the cause is resolved.
  8. Refresh .git/dual-sync/<branch> cache with the new <last-sync-sha>.

Sub-command `--hotfix-from <factgraph-tag>`:
  1. git fetch factgraph
  2. Resolve factgraph/refs/tags/<factgraph-tag> commit; read its footer
     From-hnsm-backend: <hnsm-anchor-sha>. Refuse if footer is missing.
  3. Verify <hnsm-anchor-sha> is reachable from hnsm/master. Refuse otherwise
     with a "anchor lost from master history" error (would indicate a
     corrupted release lineage, very rare).
  4. Default --into is hotfix/<factgraph-tag>-fix. Allow override.
  5. git checkout -b <hotfix-branch-name> <hnsm-anchor-sha> on hnsm-backend.
  6. Print follow-up instructions: commit fix → dual-push.sh <hotfix-branch-name>
     → merge to master → tag factgraph.
```

#### scripts/verify-shared-region-parity.sh

```
Usage: scripts/verify-shared-region-parity.sh <branch-or-ref>

Behavior:
  Computes tree hashes of src/factgraph and tests on both repos at <branch-or-ref>.
  Exits 0 if hnsm's src/factgraph tree hash == factgraph's src/factgraph tree hash,
  AND hnsm's tests tree hash == factgraph's tests tree hash.
  Exits 1 with a clear report on drift (including which subtree, expected vs actual hash).
  Also verifies factgraph HEAD has well-formed footer (warning if missing).
```

### 5.7 Durable Sync State (footer protocol)

Sync state between the two repos is encoded **inside the factgraph projection commit message**, not in any local file. The local `.git/dual-sync/<branch>` is a performance cache only; the footer is authoritative.

**Footer format** (appended to every factgraph projection commit; trailing block, parsed via `git interpret-trailers`):

```
From-hnsm-backend: <40-hex hnsm HEAD SHA at projection time>
From-hnsm-backend-branch: <hnsm branch name; must equal the factgraph branch name>
```

Two fields:

- `From-hnsm-backend`: the hnsm commit SHA being projected (the "end of range"). The next projection starts from this SHA + 1.
- `From-hnsm-backend-branch`: enforces same-name policy. Rejects accidental cross-branch projections (e.g. hnsm `feature/X` → factgraph `feature/Y`).

A projector version field was considered and explicitly dropped at Gap 3 (2026-05-14) for simplicity. If future debugging requires it, it can be added without changing the meaning of existing footers.

**Multi-machine / CI semantics:**

- Any clone of factgraph can reconstruct the full sync state by reading commit footers along its branches. No local state required.
- Local `.git/dual-sync/<branch>` cache stores the last computed footer SHA for fast script startup. Always cross-validated against the actual footer at script start; cache disagreement → trust footer, refresh cache.

**Missing footer (externally-pushed commit on factgraph that bypassed dual-push.sh):**

- `dual-push.sh` emits a WARN, falls back to computing the projection range via `merge-base(hnsm/<branch>, hnsm/master)`, proceeds with the push, and appends a deviation entry to `.git/dual-sync/<branch>.deviations.log` for later audit.
- This keeps work flowing while flagging the anomaly. Hard-rejection was considered and dropped at Gap 3.2 in favor of this softer recovery.

**Stale footer (hnsm rebased, footer SHA no longer reachable):**

- `dual-push.sh` refuses to push without `--force-rewrite`.
- `--force-rewrite` rebuilds the projection from `factgraph/master` and force-pushes (with `--force-with-lease`).
- This is the codified path for the rebase / amend hygiene rule in §5.2.

### 5.8 factgraph master bootstrap (G0 precondition)

Before this workflow can run, factgraph must have a `master` branch.
This is a **one-time setup** executed manually (not by `dual-push.sh`), and
must be completed before §7.G0 closes.

Procedure (executed once on 2026-05-14 G5 work, or whenever the workflow
is first adopted):

```bash
# 1. Verify the source of truth: release branch tip on factgraph
git -C <factgraph clone or worktree> fetch factgraph
git -C <...> rev-parse factgraph/release/v1.0.1-rc.1  # → 2bcd153f

# 2. Create local master at the release branch tip
git -C <...> branch master factgraph/release/v1.0.1-rc.1

# 3. Push master to factgraph remote
git -C <...> push factgraph master

# 4. Make master the default branch on GitHub
gh -R Symbolic-Intelligence-Org/factgraph repo edit --default-branch master

# 5. (Optional) Add branch protection on master in the GitHub UI:
#    require PR + 1 review (or admin override) before merge into master.
```

After bootstrap:

- `factgraph/master` is the **release-only line**. No direct commits. Only
  fast-forward / merge-no-ff from `release/v*` or `hotfix/*` (mirroring hnsm
  master's rule per §6.1.6).
- The existing `feature/factgraph-post-rc1-2026-05-14 @ 35ad6662` branch
  stays alive as a normal feature branch. It will eventually merge through a
  `release/v0.1.0-rc.4` (or analogously named) `release/v*` gate, then up to
  master, then a tag goes on master, then PyPI publish.
- `release/v1.0.1-rc.1` is preserved on factgraph as a historical
  reference until the project explicitly decides to clean up legacy refs.
  It is NOT part of the active workflow after bootstrap.

If the factgraph repo's release naming and hnsm's tag naming need to be
reconciled (`v0.1.0-rc.x` vs `v1.0.1-rc.1` style), that is tracked as §8 Q7
and does NOT block this blueprint's scope-freeze.

### 5.9 Sync-debt handling

**Sync-debt (factgraph push failed after hnsm push succeeded):**

Failure mode policy: **repair, never rollback**.

- If `dual-push.sh` step 3 (hnsm push) succeeds but step 7 (factgraph push) fails — for any reason: network, transient remote auth issue, branch protection, push race — the script DOES NOT rollback the hnsm push. Rolling back a published hnsm branch is more dangerous than carrying sync-debt (other consumers may have already fetched).
- The script exits non-zero with an explicit report:
  ```
  ERROR: factgraph push failed.
    hnsm-backend <branch>: pushed to <new-sha>
    factgraph     <branch>: stuck at <last-sha>  (sync debt: N commits)
  
    Retry: ./scripts/dual-push.sh --repair <branch>
  ```
- Self-recovery on next run:
  - Plain `dual-push.sh <branch>` will detect the sync-debt at step 1 self-check, warn, and proceed (effectively retries the failed factgraph projection because step 3 is a no-op when hnsm is already up to date — but pushing twice is idempotent).
  - `dual-push.sh --repair <branch>` skips step 3 explicitly, documenting intent. Semantically equivalent to plain rerun when hnsm is already up to date.
- This codifies the "sync-debt is a state, not an error" model. No git history rewrites are issued by the failure path.

## 6. Boundaries And Invariants

### 6.1 Invariants (always hold)

1. **Shared region tree-hash parity at sync points**: every commit on a factgraph branch has `src/factgraph` + `tests/` tree hashes identical to the corresponding hnsm-backend branch HEAD at the time of projection.
2. **Tag authority single-sourced on factgraph** (refined at Gap 7, 2026-05-14): the factgraph `vX.Y.Z[-rc.N]` tag is the release truth. PyPI version is derived from it via `hatch-vcs`. hnsm-backend does NOT carry the same tag by default. Optional `milestone/v*` branch refs on hnsm-backend serve as forensic anchors but are not load-bearing. The factgraph tag's commit footer (`From-hnsm-backend: <sha>`) is the durable back-pointer from a release to the hnsm-backend commit that produced it.
3. **factgraph never originates shared-region commits**: no shared-region change is authored on factgraph. All `src/factgraph` or `tests/` modifications originate in hnsm-backend and arrive in factgraph via projection.
4. **Reverts are one-way**: any revert of a previously-projected shared-region change originates in hnsm-backend as a new commit, then projects to factgraph. Manual revert on factgraph is forbidden — factgraph's shared region is always a projection result, never an authored state.
5. **Divergent files never enter the projection set**: `pyproject.toml`, `README.md`, `LICENSE`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `pixi.lock`, `.github/` are owned by factgraph (factgraph-side edits live in factgraph commits only; hnsm-side edits to the same files live in hnsm commits only and never project).
6. **master is release-only**: no direct commits to master on either repo. Only fast-forward (or merge --no-ff) from `release/v*` or `hotfix/*`.
7. **One active `release/v*` at a time** (hard, script-enforced): `dual-push.sh` queries `git ls-remote factgraph 'refs/heads/release/v*'` before any operation on a `release/v*` branch. If any other open `release/v*` exists, the script refuses unless `--allow-multiple-release` is passed (intended as a one-time escape, not a normal mode). `release/v*` branches are deleted on both remotes the moment they merge to master (§5.4 step 7); the tag is the durable historical pointer.
8. **Tags are immutable**.
9. **Hotfix-parent SHA lookup goes through the factgraph release tag's footer**, not through any hnsm-side tag. hnsm release tags are not required. The footer's `From-hnsm-backend: <sha>` is the authoritative back-reference; SHA reachability is guaranteed by master being FF-only (§6.1.6) so any commit that ever made it to master remains reachable post-release-branch-deletion.

### 6.2 Boundaries (what this blueprint does not regulate)

- Internal-only hnsm-backend feature branches that never touch shared region: lifecycle is unconstrained by this blueprint. They live and die on hnsm-backend without factgraph involvement.
- Documentation under `docs/`, blueprints under `docs/blueprints/`, memory under `memory/` — these are hnsm-internal and never project to factgraph.
- PyPI release mechanics beyond `python -m build && twine upload`. Specific testing on TestPyPI is out of scope here.
- GitHub Release artifact creation (separate concern; may piggyback on the tag step in a future blueprint).
- CI/CD configuration on either repo.

### 6.3 Re-iteration of related-memory traps

- `feedback_push_master_gate`: never auto-push master. `dual-push.sh master` must require explicit invocation; no automation.
- `feedback_release_workflow_traps`: the 6 known release-script traps still apply when wiring `release.sh` together with this workflow.
- `feedback_blueprint_workflow`: this blueprint follows the standard `docs/blueprints/active/` draft → scoped → implementing → implemented → archived lifecycle.
- `project_release_branch_invariants`: existing `release/0.1.x` and `master` in hnsm-backend remain sacred; this blueprint does NOT modify them.

## 7. Acceptance

Scoped (after Gap 1-6 resolution on 2026-05-14). Acceptance is **synthetic verification only**; the first real release using this workflow is a separate blueprint (see deferral note below).

- [ ] **G0: Design lock**. Sub-gates:
  - [x] G0.1 (Gap 1, 2026-05-14): default branch is `master` on both repos. hnsm `master` stays, factgraph `master` to be bootstrapped per §5.8.
  - [x] G0.2 (Gap 2, 2026-05-14): feature-branch cadence = **per-push transparent**. Rebase / amend hygiene rule in §5.2.
  - [x] G0.3 (Gap 3, 2026-05-14): durable sync state via 2-field footer. `.git/dual-sync/<branch>` performance cache, always cross-validated. Missing footer → warn + fallback + deviation log. Stale footer → refuse without `--force-rewrite`. Locked into §5.6 and §5.7.
  - [x] G0.4 (Gap 4, 2026-05-14): failure mode = **repair, never rollback**. Sync-debt is a state, not an error. Locked into §5.6 step 7 + `--repair` flag + §5.9.
  - [x] G0.5 (Gap 5, 2026-05-14): release/v* deleted after merge to master; tag is durable. factgraph master bootstrap from `release/v1.0.1-rc.1 @ 2bcd153f`. Single-line `release/v*` is script-enforced hard invariant. Tag-naming schema alignment deferred to §8.Q7.
  - [x] G0.6 (Gap 6, 2026-05-14): G1-G5 acceptance sharpened to synthetic verification only; real first release deferred to separate blueprint.
  - [x] G0.7 (Gap 7, 2026-05-14): topology made explicit (one local hnsm clone, two remotes — `origin` + `factgraph`); tag authority single-sourced on factgraph (no required hnsm-side tag); hotfix-parent SHA lookup via factgraph tag's `From-hnsm-backend` footer (no hnsm tag dependency); `dual-push.sh --hotfix-from <factgraph-tag>` convenience added. Locked into §1, §2.6, §5.4, §5.5, §5.6, §6.1.2, §6.1.9.

- [ ] **G1: Bootstrap factgraph master** (§5.8 procedure executed end-to-end):
  - `factgraph/master` branch exists at `2bcd153f`.
  - GitHub default branch is `master`.
  - hnsm-backend `feature/factgraph-post-rc1-2026-05-14` reachable from factgraph and recognized by `dual-push.sh` as a normal feature branch.
  - The pre-existing `release/v1.0.1-rc.1` and `v0.1.0rc1` / `v0.1.0rc2` tags are untouched on factgraph.

- [ ] **G2: `scripts/dual-push.sh` implemented** with self-tests covering:
  - Normal projection of N shared-region commits as a single new factgraph commit.
  - No-op when the range touches zero shared-region paths.
  - Missing-footer fallback (manually push a footerless commit to a test branch on factgraph; verify warn + merge-base fallback + deviation log entry).
  - Stale-footer detection (rebase hnsm branch; verify refuse without `--force-rewrite`; verify `--force-rewrite` rebuilds projection from `factgraph/master` and force-pushes with `--force-with-lease`).
  - Sync-debt recovery (simulate factgraph push failure, verify plain rerun OR `--repair` catches up without git rewrite).
  - Single-line `release/v*` refusal (open two synthetic `release/v*` branches, verify second `dual-push.sh release/v0.1.0-rc.X` is refused unless `--allow-multiple-release`).
  - `--dry-run` prints intended actions without mutating anything.
  - Same-name footer cross-check (try `dual-push.sh feature/X` when factgraph `feature/X` HEAD's `From-hnsm-backend-branch` says `feature/Y`; verify refusal).

- [ ] **G3: `scripts/verify-shared-region-parity.sh` implemented** as a standalone tool AND integrated as `dual-push.sh`'s step 1 self-check helper. Returns 0 on parity, 1 with structured drift report otherwise. Tested at every gate in G4.

- [ ] **G4: Synthetic end-to-end dry-run** of a complete release cycle on synthetic refs only — does NOT push origin or factgraph in production-impacting ways:
  - Open synthetic `feature/test-dual-push` on hnsm-backend, touching one file in `src/factgraph` and one in `tests/`.
  - `dual-push.sh feature/test-dual-push` to a sandbox factgraph remote (or `--dry-run` for full path simulation against real remote without push side-effects).
  - Verify `verify-shared-region-parity.sh feature/test-dual-push` is green.
  - Open `release/v-test-1` (synthetic, name picked to be obviously test-only), merge feature into it on both repos.
  - Verify single-line invariant refuses a second concurrent `release/v-test-2`.
  - Stabilization commit on `release/v-test-1` (CHANGELOG-only on factgraph + pyproject bump on hnsm).
  - Merge `release/v-test-1` → `master` on both repos (FF on hnsm; factgraph projection per workflow).
  - Tag factgraph only: `v-test-1` (synthetic, factgraph-side). Verify shared-region tree at the tagged commit matches hnsm master at the corresponding anchor (read via tag footer). Tag is NOT pushed to factgraph remote (kept local only) and may be deleted after the gate.
  - Verify hotfix lookup path: `dual-push.sh --hotfix-from v-test-1` correctly reads the tag footer, finds the hnsm anchor, and creates the hotfix branch from it (dry-run if avoiding actual branch creation).
  - Verify deletion of `release/v-test-1` on both remotes.
  - Clean up all synthetic refs.

- [ ] **G5: Docs + memory sync**:
  - `docs/blueprints/README.md` references this workflow under a new "Cross-repo workflow" entry.
  - `docs/architecture_principles.md` (if relevant) updated.
  - A new memory anchor under `memory/` records the headline decisions (master/master, per-push transparent, 2-field footer, repair-never-rollback, release/v* single-line + delete, factgraph as version authority) so future sessions don't relitigate Gap 1-5.
  - Add `scripts/dual-push.sh` and `scripts/verify-shared-region-parity.sh` references to `feedback_release_workflow_traps` or a sibling memory entry as the canonical tools.

**Deferred (separate blueprint):**

The first real release using this workflow — e.g., shipping `v0.1.0-rc.4` (or whichever tag schema is chosen per §8.Q7) — is **explicitly out of scope** for this blueprint per Gap 6. That work will live in a new `<date>_first-dual-repo-release-rollout.md` blueprint that depends on G0-G5 here being green. It will be a "first-use audit" capturing real-world surprises and feeding any required fixes back into a follow-up revision of this workflow.

## 8. Open Questions

Resolved during 2026-05-14 scope round:

1. ~~Where do `release/v*` branches die? Delete after merge to master? Keep as historical pointers?~~ **Resolved at Gap 5.1**: delete on both remotes the moment they merge to master; tag is the durable pointer. See §5.4 step 7 + §6.1.7.
2. ~~Should `release/v*` lifetime support concurrent stabilization of more than one rc?~~ **Resolved at Gap 5**: no. Single-line is a hard invariant (§6.1.7), script-enforced. `--allow-multiple-release` exists as an escape hatch only.
3. ~~Should the projection commit message preserve per-commit hnsm-backend lineage?~~ **Resolved at Gap 3**: yes, via 2-field footer (`From-hnsm-backend: <sha>` + `From-hnsm-backend-branch: <name>`) appended to every factgraph projection commit. See §5.7.
4. ~~How do we handle reverts? Two-way mirror or one-way?~~ **Resolved at user finding 8 / §6.1.4**: reverts are one-way. Manual revert on factgraph is forbidden; reverts originate in hnsm-backend and project to factgraph like any other commit. The tree-replace mechanism in §5.6 step 6 handles deletions and tree-shape changes automatically (it is a tree replacement, not a diff cherry-pick).
5. ~~Does `dual-push.sh` need a `--rollback` path for factgraph push failures?~~ **Resolved at Gap 4**: no rollback. Failure mode is "sync debt", recoverable via `dual-push.sh --repair <branch>` or plain rerun. See §5.9.

Remaining open (do not block scope-freeze):

6. **Internal-only test files broken by tests removal** — `src/agent/tests/`, `src/domains/*/tests/` reference the deleted `src/kernel/tests/` helpers. Decision (drop / repoint to root `tests/_test_helpers` / move entirely into `tests/`) is a separate cleanup blueprint, independent of dual-repo workflow.
7. **Tag-naming schema alignment** (deferred from Gap 5.3): hnsm-backend uses `v0.1.0-rc.x` (per `project_v0_1_0_rc1_published`), factgraph's existing release branch uses `release/v1.0.1-rc.1`. Next tag schema is unresolved. Options: (a) continue hnsm's `v0.1.x` lineage on factgraph (downgrade from v1 naming, treat v1.x as test-era artifact), (b) reset to a unified v1.x lineage going forward, (c) bridge with an explicit "rebrand" tag. Decision is independent of this workflow and can be made at the next tag-cut moment.

## Outcome

(To be filled at implemented phase.)

## Deviations

(To be filled at implemented phase.)
