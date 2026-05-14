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

Today the first cross-repo commit landed as a one-off manual operation (`feature/factgraph-post-rc1-2026-05-14 @ 35ad6662` on the factgraph remote, built from a `/tmp` worktree rooted at `factgraph_test/release/v1.0.1-rc.1`). Going forward this needs a stable, repeatable workflow covering: asymmetric default branch names (hnsm `master` / factgraph `main`), sync cadence, release path through factgraph `release/v*` and `main`, dev/release-manager boundary, tagging by release manager, hotfix handling, and divergence rules.

Without an explicit workflow:

- branches in the two repos will drift in naming and HEAD;
- developers may push uneven shared-region states to factgraph;
- release artifacts may disagree across repos (different `src/factgraph` content under the same tag);
- divergent files (pyproject.toml etc.) may get accidentally synced and break factgraph's hatch+pixi build.

## 2. Goals

1. Define a single source-of-truth direction: **hnsm-backend → factgraph** projection. factgraph never originates shared-region commits.
2. **Asymmetric default branches** (Gap 8.A, 2026-05-14): hnsm-backend uses `master`, factgraph uses `main`. Shared-region working branches (`feature/X`, `hotfix/X`) keep identical names across both repos. `release/v*` only exists on factgraph (Gap 8.D); hnsm-backend has no `release/v*` branch. Scripts SHOULD discover the factgraph default branch dynamically (`git ls-remote --symref factgraph HEAD`) rather than hardcoding `main`; documentation refers to it as `main`.
3. Define the release pipeline: `feature/* → factgraph release/v* → factgraph main → release-manager tags main → release-manager publishes`. The developer phase ends at "merge release/v* into factgraph main"; tagging and publishing are explicitly out of the developer workflow (Gap 8.F).
4. Hotfix path uses the same shape (`hotfix/X → factgraph release/v* → factgraph main`). Hotfix-parent SHA on hnsm is looked up via the factgraph release tag's `From-hnsm-backend` footer.
5. Sync cadence: **per-push** of shared-region branches (`feature/X`, `hotfix/X`). When a developer pushes hnsm-backend with shared-region changes, the same push action projects to factgraph. `release/v*` on factgraph is created and advanced by direct factgraph operations + targeted hnsm projection pushes for QA fixes; it is not a `dual-push.sh <branch>` argument in normal use.
6. Version + tag authority: **factgraph**. factgraph's `pyproject.toml` uses `hatch-vcs` to derive version from the tag, and the tag itself is created on factgraph by the release manager (not by the developer, not on hnsm-backend). hnsm-backend does not carry the same tag by default. Optional `milestone/v*` branch refs on hnsm-backend may be used as forensic anchors (per `feedback_milestone_branch_refs`) but are not load-bearing on the release pipeline. hnsm-backend's `pyproject.toml` version remains advisory only — not source of truth for PyPI.
7. PyPI publish: handled by the release manager from factgraph. Both `rc` and `final` tags publish (per the v0.1.0-rc.1 precedent).
8. Tooling: a `scripts/dual-push.sh` script implementing the projection, plus a `scripts/verify-shared-region-parity.sh` invariant checker. Both live in hnsm-backend.
9. **Developer / release-manager boundary** (Gap 8.F): explicit two-phase workflow. Developer phase ends at "merge release/v* into factgraph main". Release-manager phase covers tag + PyPI publish + release/v* cleanup-on-next-create. The handoff contract is captured in §5.10.

## 3. Non-goals

- Not changing factgraph's existing `release/v1.0.1-rc.1` branch or the v0.1.0rc1 / v0.1.0rc2 tags.
- Not rewriting `scripts/release.sh`. This blueprint complements it; `release.sh` may still drive PyPI publish from factgraph in a future iteration.
- Not auto-syncing every hnsm-backend commit via a post-commit hook. Push-time projection is the explicit chosen cadence.
- Not allowing concurrent `release/v*` branches. Single-line invariant (§6.1.7).
- Not bridging pyproject.toml or any non-shared file. These are accepted divergences.
- Not synchronizing factgraph-only scaffolding edits (pixi.lock updates, README authoring, CI yaml tweaks) back to hnsm-backend. Those live only in factgraph.
- Not introducing a `develop` branch or any GitFlow construct beyond `feature/*`, `release/v*` (factgraph-only), `master` (hnsm) / `main` (factgraph), `hotfix/*`.
- **Not having the developer cut tags or push to PyPI.** Tag creation and PyPI publish are release-manager responsibilities (Gap 8.F). The dev workflow ends at the factgraph `main` merge.
- Not migrating hnsm-backend's `master` to `main`. Asymmetric naming is the explicit choice (Gap 8.A supersedes Gap 1's "both master" decision); hnsm stays `master`.

## 4. Current Context

- hnsm-backend default branch: `master @ 99452270` (origin). Sacred per `project_release_branch_invariants`; stays as `master`.
- factgraph default branch: not yet created; only `release/v1.0.1-rc.1 @ 2bcd153f` + `feature/factgraph-post-rc1-2026-05-14 @ 35ad6662` exist. A `main` branch (Gap 8.A) will be bootstrapped from `release/v1.0.1-rc.1 @ 2bcd153f` as a G1 precondition of this workflow (see §5.8 Bootstrap). The post-rc.1 feature branch continues to live as a normal feature branch and will eventually flow through `release/v*` gate on factgraph.
- factgraph tags on origin: `v0.1.0rc1 @ f4aa551e`, `v0.1.0rc2 @ 96152547`. Both immutable.
- hnsm-backend tags: `v0.1.0-rc.1`, `v0.1.0-rc.2` (per memory `project_v0_1_0_rc1_published`). Plus milestone branch refs under `refs/heads/milestone/...`.
- Local hnsm-backend remote alias: `factgraph` (set on 2026-05-14 after the factgraph_test → factgraph repo rename).
- Push permission verified for `GigaGaiaWorld` on the factgraph repo (admin/maintain/push all true).
- Shared region paths: `src/factgraph` (243 files post-rename) + `tests/` (123 files, tree hash `06688b6502a3e67ce86b028cb5bcf1376a7c0b61` identical to remote release branch).
- Divergent file inventory: `pyproject.toml`, `README.md`, `LICENSE`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `pixi.lock`, `.github/`, plus all hnsm-internal paths (`src/agent`, `src/service`, `src/domains`, `docs/`, `memory/`, `scripts/`, etc.).
- Active worktrees: main (`/Users/zhenzhili/hnsm-backend @ master`), this rename worktree (`.claude/worktrees/hardcore-mahavira-2155e3 @ claude/hardcore-mahavira-2155e3`), one detached dryrun, one uncertainty-transmission topic worktree.

## 5. Proposed Shape

### 5.1 Branching graph

Two repos, asymmetric default branches (Gap 8.A). `release/v*` lives only on factgraph (Gap 8.D). hnsm-backend `master` is the **development integration line** with no release semantics; factgraph `main` is **release-only**, updated only via merging `release/v*` in.

```
hnsm-backend (full; dev integration line; no release/v*):

master ───────────────────────●─────●─────●────────────►   (collects every merged feature; not release-gated)
                              ▲    ▲      ▲
                              │    │      │ (git merge --no-ff hotfix/Z after dual-push)
feature/A ──●──●──●──●────────●    │      │
                                   │      │
feature/B ──●──●──●──●─────────────●      │
                                          │
hotfix/Z  ──●──●──────────────────────────●  ← parent SHA from factgraph release tag footer (§5.5)

(Each feature/hotfix is dual-pushed to factgraph at push-time during dev.)


factgraph (shared region only; release-gated):
                                                                       release manager:
                                                                       tag v0.1.0-rc.4
                                                                            ▼
main ────────────────────────────────────────────────────────────●─────────●─────► PyPI
                                            │                  ╱
                                            │  (dev: git merge --no-ff release/v0.1.0-rc.4)
                                            │
release/v0.1.0-rc.4 ─●─●─●(divergent fixes + projected QA from hnsm)
                     ▲
                     │ (dev: created from factgraph feature/A or feature/B HEAD)
                     │
feature/A ──●────────●  ← projected from hnsm feature/A (per-push, shared-region delta only)
feature/B ──●────────●  ← same
hotfix/Z   ──●──● (when shared region touched, projected from hnsm hotfix/Z;
                  feeds an emergency release/v* gate the same way features do)

release/v0.1.0-rc.4 stays alive after merge to main and tag.
Deleted only when the NEXT release/v0.1.0-rc.5 is created (Gap 8.D).
```

Naming summary:

| Branch | hnsm-backend | factgraph | Notes |
|---|---|---|---|
| Default | `master` | `main` | asymmetric (Gap 8.A) |
| Feature | `feature/X` | `feature/X` (if shared region touched) | same name |
| Release candidate | — (doesn't exist) | `release/v*` | factgraph-only (Gap 8.D) |
| Hotfix | `hotfix/X` | `hotfix/X` (if shared region touched) | same name |
| Internal-only | `feature/X` (hnsm only) | — | no factgraph counterpart |

### 5.2 Daily flow (feature development)

1. `git checkout master && git pull origin master` in hnsm-backend.
2. `git checkout -b feature/X`.
3. Work on hnsm-backend. Commits may touch anything (shared region + internal).
4. When ready to publish progress: `scripts/dual-push.sh feature/X`.
   - The script pushes `feature/X` to `origin` (hnsm-backend).
   - Detects commits since last sync point that touched `src/factgraph` or `tests/`.
   - If any: projects a single new commit onto factgraph's `feature/X`, parented on factgraph's default branch (`main`, discovered dynamically via `git ls-remote --symref factgraph HEAD`; the script does not guess parents at runtime and does not hardcode the branch name).
   - Pushes factgraph branch.
5. If `feature/X` touches no shared region at all, the script is a no-op for factgraph (only hnsm-backend gets pushed). factgraph branch is never created.
6. **Collect feature back into hnsm master** (Gap 8.B): once dev is satisfied that the feature is done from hnsm's perspective — regardless of whether it will become part of a release — locally merge `feature/X` into hnsm `master`:
   ```bash
   git checkout master
   git merge --no-ff feature/X
   git push origin master
   ```
   hnsm `master` is the **development integration line**; it collects every merged feature and has **no release semantics**. Release semantics live entirely on factgraph (§5.3+). Note: this `git push origin master` step is intentionally a plain push, NOT `scripts/dual-push.sh master` — hnsm master never projects to factgraph (factgraph `main` is updated only via release/v* merge on the factgraph side, §5.4).
7. Delete the hnsm `feature/X` branch on origin after merge (optional). If the feature was also dual-pushed, the factgraph `feature/X` lives on until it feeds a `release/v*` and the next release/v* cycle deletes its predecessor (§5.4).

**Rebase / amend hygiene (Gap 2 + Gap 3 interlock):**

Once a hnsm-backend `feature/X` commit has been projected to factgraph, subsequent rebase / amend / force-push of that commit on hnsm-backend creates a divergence:

- factgraph's `feature/X` already published commit(s) marked with `From-hnsm-backend: <old-sha>` (see Gap 3 footer).
- The new (rebased) hnsm-backend commit has a different SHA. `dual-push.sh` will detect the footer ≠ branch state and refuse without `--force-rewrite`.
- `--force-rewrite` force-pushes factgraph `feature/X` to a new projection of the rewritten hnsm-backend HEAD. Public callers tracking the old SHA may need to refetch.

Recommended discipline: treat `feature/X` as append-only after first `dual-push`. Reserve rebases for pre-first-push cleanup.

### 5.3 Feature → release/v* gate (factgraph-only)

(Refined at Gap 8.C+D, 2026-05-14: `release/v*` lives only on factgraph. Stabilization commits are stratified — divergent files on factgraph directly, shared-region fixes originate in hnsm.)

1. **Pre-flight**: decide which factgraph `feature/X` will seed the next release. The deliberate "ready" moment. Not every feature needs a release/v*; only those at a release node.
2. **Delete previous `release/v*` if any** (Gap 8.D): check `git ls-remote factgraph 'refs/heads/release/v*'`. If a prior `release/v*` exists, verify it has been merged into factgraph `main` AND its tag exists on factgraph (release-manager phase completed). If both true, delete:
   ```bash
   git push factgraph --delete release/v0.1.0-rc.3
   ```
   If the previous `release/v*` is NOT merged or tag is missing → refuse. Require explicit `dual-push.sh --force-delete-stalled-release release/v0.1.0-rc.3` to override (use only on aborted release lines, never on a release that's mid-stabilization).
3. **Create the new `release/v*` on factgraph only**, seeded from the chosen factgraph `feature/X` HEAD:
   ```bash
   git -C <local-hnsm-clone> fetch factgraph
   git -C <...> push factgraph factgraph/feature/X:refs/heads/release/v0.1.0-rc.4
   ```
   (No hnsm-side `release/v*` branch is ever created; hnsm has no release/v*.)
4. **Stabilization stratified by file kind** (Gap 8.C; layered to preserve §6.1.3 "factgraph never originates shared-region commits"):

   - **Divergent files only** (CHANGELOG, pyproject.toml hatch-vcs config, pixi.lock, .github/ workflows, README updates): edit directly on factgraph `release/v*`. These commits are factgraph-side authored and never project back. Example:
     ```bash
     git -C <local-hnsm-clone> checkout -b stabilize-rc4 factgraph/release/v0.1.0-rc.4
     # edit CHANGELOG.md only; no src/factgraph or tests changes
     git commit -am "..."
     git push factgraph HEAD:release/v0.1.0-rc.4
     ```
     A pre-push tree check rejects commits that touch `src/factgraph/` or `tests/`.

   - **Shared-region QA fixes** (code or test fixes in `src/factgraph` or `tests/`): MUST originate in hnsm-backend. Two patterns:
     - Add commits to the same hnsm `feature/X` branch that seeded this release, then `dual-push.sh feature/X` — the projection arrives on factgraph `feature/X`. Then on factgraph: `git push factgraph factgraph/feature/X:release/v0.1.0-rc.4` (fast-forward) OR `git merge` if non-FF.
     - Start a small hnsm `feature/X-rc4-fixup` branch from hnsm master (post-feature-merge), dual-push, then merge into factgraph `release/v0.1.0-rc.4`.

   Either way, factgraph `release/v*` only receives shared-region commits that bear a valid `From-hnsm-backend` footer (§5.7).

5. **Merge `release/v*` → factgraph `main`** when stabilization is done:
   ```bash
   git -C <local-hnsm-clone> fetch factgraph
   git -C <...> checkout -B fg-main factgraph/main
   git -C <...> merge --no-ff factgraph/release/v0.1.0-rc.4
   git -C <...> push factgraph HEAD:main
   ```
   `release/v0.1.0-rc.4` is NOT deleted at this step (Gap 8.D — it stays alive until the next release/v* is created).

6. **Verify shared-region parity** (final dev-side check): `scripts/verify-shared-region-parity.sh main` reports green between hnsm `master` and factgraph `main` (modulo any feature changes in hnsm not yet flowed through a release/v*).

**Developer phase ends here.** Tag + PyPI publish are release-manager actions, captured in §5.10 as a handoff contract.

### 5.4 Developer release path summary

(Superseded structure as of Gap 8.F, 2026-05-14: this section formerly housed full tag + publish steps. They have moved to §5.10 Release-manager handoff. This section now summarizes the developer's release-related obligations.)

Developer-side release path is the §5.3 walk: feature on hnsm → dual-push → factgraph `release/v*` → stabilization (stratified) → merge into factgraph `main`.

Boundary: **developer phase ends at the `release/v*` → factgraph `main` merge** (§5.3 step 5). After that point, the next actions are owned by the release manager (§5.10):

- Tagging factgraph `main` with `v0.1.0-rc.4` (or whatever schema).
- Pushing the tag.
- PyPI publish (`python -m build && twine upload`, hatch-vcs reads tag for version).
- Optional internal milestone branch on hnsm-backend (forensic anchor; `feedback_milestone_branch_refs` convention).

The developer does NOT execute these tag/publish actions. If a release manager is unavailable and the work needs to land anyway, that is a deliberate escalation, not the workflow's default path.

### 5.5 Hotfix path

(Refined at Gap 8.E, 2026-05-14: hotfix uses the same `feature → release/v* → main → tag → publish` shape, scaled-down. Hotfix-parent SHA on hnsm-backend is looked up via the factgraph release tag's commit footer (Gap 7).)

**Developer phase:**

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
   The anchor SHA is guaranteed reachable from hnsm `master` (master is FF-only on the merge side, so once a feature merged in, its tip lives in master history forever).

3. Fix. Commit(s) on hnsm-backend `hotfix/X`.

4. **If the hotfix touches shared region** (the usual case for code/test fixes): `scripts/dual-push.sh hotfix/X` — projects to factgraph `hotfix/X` (footer back-references the new hnsm hotfix HEAD). Verify parity: `scripts/verify-shared-region-parity.sh hotfix/X`.

   **If the hotfix only touches divergent / release-metadata files on factgraph** (rare; e.g., a CHANGELOG correction post-release): no hnsm-side originate is needed; do the fix directly on factgraph as part of §5.5 step 5 below.

5. **Create or use a `release/v0.1.0-rc.3.1` branch on factgraph** (factgraph-only, per §5.3 lifecycle):
   - Delete the previous `release/v*` if any (with the Gap 8.D guard).
   - Seed `release/v0.1.0-rc.3.1` from the factgraph commit corresponding to the original `v0.1.0-rc.3` tag (so the hotfix is layered onto the exact released state):
     ```bash
     git -C <...> push factgraph factgraph/refs/tags/v0.1.0-rc.3^{commit}:refs/heads/release/v0.1.0-rc.3.1
     ```
   - Merge factgraph `hotfix/X` into `release/v0.1.0-rc.3.1` on factgraph (or fast-forward if linear).

6. (Optional divergent stabilization, same stratification as §5.3 step 4.)

7. **Merge `release/v0.1.0-rc.3.1` → factgraph `main`**.

8. **Locally on hnsm: merge `hotfix/X` back into hnsm master** so the dev integration line absorbs the fix:
   ```bash
   git checkout master && git merge --no-ff hotfix/X && git push origin master
   ```

9. **Developer phase ends here.** Release manager picks up per §5.10:
   - Tag factgraph `main` with `v0.1.0-rc.3.1`.
   - Push tag.
   - PyPI publish.

10. (If there is an active `release/v0.1.0-rc.4` for the next release at the time of this hotfix, the next stabilization commit on it must absorb the hotfix — e.g., via `git merge factgraph/main` on the factgraph release/v0.1.0-rc.4 branch.)

11. Delete `hotfix/X` on both remotes after the release/v0.1.0-rc.3.1 merge to main.

### 5.6 Tooling

#### scripts/dual-push.sh

```
Usage:
  scripts/dual-push.sh <branch> [--squash | --keep-granular] [--force-rewrite] [--repair] [--dry-run]
  scripts/dual-push.sh --hotfix-from <factgraph-tag>  [--into <hotfix-branch-name>]
  scripts/dual-push.sh --force-delete-stalled-release <release/v*-branch>

Allowed <branch> targets: feature/*, hotfix/*  (shared-region working branches).
Disallowed:
  - master  (hnsm `master` is plain git push origin master, NEVER projects to factgraph;
             factgraph `main` is updated via release/v* merge on factgraph side, NEVER
             via dual-push)
  - main    (factgraph default; same as above)
  - release/v*  (created and advanced directly on factgraph per §5.3; shared-region
             commits on it come via separate hnsm feature/X projections, then merged
             on factgraph)

The script discovers factgraph's default branch dynamically:
  factgraph_default=$(git ls-remote --symref factgraph HEAD \
      | awk '/^ref:/ { sub("refs/heads/","",$2); print $2; exit }')
It does NOT hardcode `main` or `master`.

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
        Parent for new branch = factgraph/<factgraph-default-branch> (i.e., factgraph/main
        per §5.8 bootstrap; discovered dynamically as shown above).
        <last-sync-sha> = merge-base(hnsm/<branch>, factgraph/main tree's hnsm-backend mapping)
        — pragmatically the script falls back to the first hnsm-backend commit that touches
        shared region on this branch. Records deviation if ambiguous.
     c. If footer is absent from factgraph/<branch> HEAD (externally-pushed commit):
        WARN, fall back to merge-base(hnsm/<branch>, hnsm/master), continue, append a
        deviation entry to .git/dual-sync/<branch>.deviations.log.
     d. If From-hnsm-backend: <sha> is not an ancestor of hnsm/<branch>'s HEAD
        (rebase/reset detected):
        Refuse unless --force-rewrite is passed. With --force-rewrite, the projection
        is built from factgraph/<factgraph-default-branch> parent and force-pushed.
  5. Walk commits in (<last-sync-sha>..hnsm/<branch>]. If none touched src/factgraph or tests/:
     exit (no factgraph push needed; hnsm push already done in step 3).
  6. Build factgraph projection commit:
     - Parent = current factgraph/<branch> HEAD (or factgraph/<factgraph-default-branch>
       if branch is new or --force-rewrite).
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
- `--force-rewrite` rebuilds the projection from `factgraph/<factgraph-default-branch>` (typically `factgraph/main`) and force-pushes (with `--force-with-lease`).
- This is the codified path for the rebase / amend hygiene rule in §5.2.

### 5.8 factgraph main bootstrap (G1 precondition)

Before this workflow can run, factgraph must have a `main` branch (Gap 8.A: asymmetric naming).
This is a **one-time setup** executed manually (not by `dual-push.sh`), and
must be completed before §7.G1 closes.

Procedure (executed once on first adoption):

```bash
# 1. Verify the source of truth: release branch tip on factgraph
git fetch factgraph
git rev-parse factgraph/release/v1.0.1-rc.1  # → 2bcd153f

# 2. Push factgraph/release/v1.0.1-rc.1 tip up as a new branch `main`
git push factgraph factgraph/release/v1.0.1-rc.1:refs/heads/main

# 3. Make main the default branch on GitHub
gh -R Symbolic-Intelligence-Org/factgraph repo edit --default-branch main

# 4. (Optional) Add branch protection on main in the GitHub UI:
#    require PR + 1 review (or admin override) before merge into main.
#    This complements §6.1.6 (factgraph main is release-only).
```

After bootstrap:

- `factgraph/main` is the **release-only line**. No direct commits. Only
  fast-forward / merge-no-ff from `release/v*` (and `hotfix/X` flowing
  through a `release/v*` per §5.5).
- `hnsm-backend/master` stays as it is — the dev integration line. No
  same-name branch on factgraph; the developer's `dual-push.sh` never
  touches factgraph `main` directly.
- The existing `feature/factgraph-post-rc1-2026-05-14 @ 35ad6662` branch
  stays alive as a normal feature branch. It will eventually flow through
  a `release/v*` gate (factgraph-only, per §5.3), into factgraph `main`,
  then the release manager (§5.10) tags and publishes.
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

### 5.10 Release-manager handoff contract

(Added at Gap 8.F, 2026-05-14. This section is **not part of the developer workflow**; it captures what the developer hands over and what the release manager owes back, so each side can act independently.)

**Trigger (developer side):** developer has finished §5.3 step 5 — `release/v0.1.0-rc.4` (factgraph-only) is merged into factgraph `main`. The release/v* branch is still alive on factgraph and contains the full stabilization history.

**Inputs to release manager (everything observable on factgraph alone):**

- `factgraph/main` HEAD has the merge commit from `release/v0.1.0-rc.4`.
- The commit at `factgraph/main` HEAD whose tree includes the latest shared-region delta carries `From-hnsm-backend: <sha>` footer pointing into hnsm history.
- `factgraph/release/v0.1.0-rc.4` still exists (kept-last-1 per Gap 8.D).
- No `v0.1.0-rc.4` tag exists yet on factgraph.

**Release-manager actions:**

1. Verify dev handoff (sanity, optional but recommended):
   - `git ls-tree factgraph/main src/factgraph tests/` reports the expected post-release tree.
   - The CHANGELOG entry, version field (if applicable), and `pixi.lock` on `factgraph/main` match the rc-4 contents.

2. Tag factgraph `main`:
   ```bash
   git -C <factgraph clone or local hnsm clone> fetch factgraph
   git tag -a v0.1.0-rc.4 --message "..." factgraph/main
   git push factgraph v0.1.0-rc.4
   ```
   `hatch-vcs` derives the PyPI version from this tag.

3. (Optional, recommended) Create a hnsm-backend `milestone/v0.1.0-rc.4` branch ref as forensic anchor:
   ```bash
   git checkout master   # (in local hnsm clone)
   git branch milestone/v0.1.0-rc.4
   git push origin milestone/v0.1.0-rc.4
   ```
   Per `feedback_milestone_branch_refs`. Not load-bearing.

4. PyPI publish (from factgraph local checkout):
   ```bash
   python -m build
   twine upload dist/*
   ```
   Hatch-vcs reads the tag, so version is correct without manual editing.

5. **Notify dev side**: release manager confirms the tag was pushed and PyPI publish succeeded. Until this notification, dev should NOT start creating the next `release/v*` (which would attempt to delete the previous one per Gap 8.D and refuse if the tag is missing).

**Outputs back to developer:**

- `factgraph/refs/tags/v0.1.0-rc.4` exists on factgraph remote.
- The package is installable from PyPI.
- The `release/v0.1.0-rc.4` branch is left alone (the developer's next `release/v*` creation per §5.3 step 2 will delete it).

**Boundary contract** (single sentence): developer leaves `factgraph/main` advanced and `release/v*` alive but un-tagged; release manager makes the tag, pushes it, and publishes. No git rebase or history rewrite by either side after handoff.

**Release-manager unavailable / emergency escalation:** if no release manager is available and the release MUST land, a developer may execute steps 2 + 4 above with explicit acknowledgement that this crosses the dev/release-manager boundary. Record the escalation in a deviation log (a separate audit anchor; not specified here).

## 6. Boundaries And Invariants

### 6.1 Invariants (always hold)

1. **Shared region tree-hash parity at sync points**: every commit on a factgraph branch has `src/factgraph` + `tests/` tree hashes identical to the corresponding hnsm-backend branch HEAD at the time of projection.
2. **Tag authority single-sourced on factgraph** (refined at Gap 7, 2026-05-14): the factgraph `vX.Y.Z[-rc.N]` tag is the release truth. PyPI version is derived from it via `hatch-vcs`. hnsm-backend does NOT carry the same tag by default. Optional `milestone/v*` branch refs on hnsm-backend serve as forensic anchors but are not load-bearing. The factgraph tag's commit footer (`From-hnsm-backend: <sha>`) is the durable back-pointer from a release to the hnsm-backend commit that produced it.
3. **factgraph never originates shared-region commits**: no shared-region change is authored on factgraph. All `src/factgraph` or `tests/` modifications originate in hnsm-backend and arrive in factgraph via projection. In particular, factgraph `release/v*` stabilization commits that touch shared region MUST come from hnsm projection (Gap 8.C); commits that touch only divergent files MAY be authored directly on factgraph `release/v*`.
4. **Reverts are one-way**: any revert of a previously-projected shared-region change originates in hnsm-backend as a new commit, then projects to factgraph. Manual revert on factgraph is forbidden — factgraph's shared region is always a projection result, never an authored state.
5. **Divergent files never enter the projection set**: `pyproject.toml`, `README.md`, `LICENSE`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `pixi.lock`, `.github/` are owned by factgraph (factgraph-side edits live in factgraph commits only; hnsm-side edits to the same files live in hnsm commits only and never project).
6. **Asymmetric default branches with split semantics** (Gap 8.A+B, supersedes pre-Gap-8 §6.1.6): hnsm-backend default is `master` (dev integration line, no release semantics; collects every merged feature); factgraph default is `main` (release-only line, updated only via merging in `release/v*`). Neither default is ever a direct target of `dual-push.sh`. `release/v*` does not exist on hnsm-backend; it lives only on factgraph.
7. **At most one `release/v*` open on factgraph at a time** (Gap 8.D, supersedes pre-Gap-8 §6.1.7 delete-on-merge semantics): the active `release/v*` is preserved after its merge into factgraph `main` and tag. It is deleted only when the NEXT `release/v*` is being created. The creation script (`dual-push.sh` or manual procedure per §5.3 step 2) MUST verify the previous `release/v*` is (a) merged into factgraph `main` AND (b) has a corresponding tag, before deleting. Failing either guard requires explicit `--force-delete-stalled-release` override. `--allow-multiple-release` remains available as a separate one-time escape for parallel-rc scenarios that are otherwise prohibited.
8. **Tags are immutable**.
9. **Hotfix-parent SHA lookup goes through the factgraph release tag's footer**, not through any hnsm-side tag. hnsm release tags are not required. The footer's `From-hnsm-backend: <sha>` is the authoritative back-reference; SHA reachability is guaranteed by hnsm `master` collecting every feature merge (§6.1.6) so any commit that ever made it to master remains reachable post-release.
10. **Developer / release-manager separation** (Gap 8.F): tag creation and PyPI publish are release-manager-owned actions, NOT part of the developer workflow. Developer phase ends at `merge release/v* → factgraph main` (§5.3). The handoff contract is in §5.10. Crossing this boundary on the developer side is an explicit escalation, not a default path.

### 6.2 Boundaries (what this blueprint does not regulate)

- Internal-only hnsm-backend feature branches that never touch shared region: lifecycle is unconstrained by this blueprint. They live and die on hnsm-backend without factgraph involvement.
- Documentation under `docs/`, blueprints under `docs/blueprints/`, memory under `memory/` — these are hnsm-internal and never project to factgraph.
- PyPI release mechanics beyond `python -m build && twine upload`. Specific testing on TestPyPI is out of scope here.
- GitHub Release artifact creation (separate concern; may piggyback on the tag step in a future blueprint).
- CI/CD configuration on either repo.

### 6.3 Re-iteration of related-memory traps

- `feedback_push_master_gate`: never auto-push hnsm `master`. After merging a feature into hnsm `master` (§5.2 step 6), `git push origin master` requires explicit invocation; no automation. `dual-push.sh` does NOT accept `master` or `main` as targets (§5.6).
- `feedback_release_workflow_traps`: the 6 known release-script traps still apply when wiring `release.sh` together with this workflow.
- `feedback_blueprint_workflow`: this blueprint follows the standard `docs/blueprints/active/` draft → scoped → implementing → implemented → archived lifecycle.
- `project_release_branch_invariants`: existing `release/0.1.x` and `master` in hnsm-backend remain sacred; this blueprint does NOT modify them.

## 7. Acceptance

Scoped (after Gap 1-6 resolution on 2026-05-14). Acceptance is **synthetic verification only**; the first real release using this workflow is a separate blueprint (see deferral note below).

- [ ] **G0: Design lock**. Sub-gates:
  - [x] G0.1 (Gap 1, 2026-05-14; **SUPERSEDED by G0.8.A**): originally locked both repos to `master`. Gap 8.A switches factgraph to `main` per user round-3 review.
  - [x] G0.2 (Gap 2, 2026-05-14): feature-branch cadence = **per-push transparent**. Rebase / amend hygiene rule in §5.2.
  - [x] G0.3 (Gap 3, 2026-05-14): durable sync state via 2-field footer. `.git/dual-sync/<branch>` performance cache, always cross-validated. Missing footer → warn + fallback + deviation log. Stale footer → refuse without `--force-rewrite`. Locked into §5.6 and §5.7.
  - [x] G0.4 (Gap 4, 2026-05-14): failure mode = **repair, never rollback**. Sync-debt is a state, not an error. Locked into §5.6 step 7 + `--repair` flag + §5.9.
  - [x] G0.5 (Gap 5, 2026-05-14; **release/v* delete-on-merge SUPERSEDED by G0.8.D**): original Gap 5.1 deleted release/v* on merge to master. Gap 8.D switches to keep-last-1 with delete-on-next-create. Gap 5.2 bootstrap procedure superseded by Gap 8.A (factgraph default branch is now `main`, not `master`). Tag-naming schema alignment (Gap 5.3) still deferred to §8.Q7.
  - [x] G0.6 (Gap 6, 2026-05-14): G1-G5 acceptance sharpened to synthetic verification only; real first release deferred to separate blueprint.
  - [x] G0.7 (Gap 7, 2026-05-14): topology made explicit (one local hnsm clone, two remotes — `origin` + `factgraph`); tag authority single-sourced on factgraph (no required hnsm-side tag); hotfix-parent SHA lookup via factgraph tag's `From-hnsm-backend` footer (no hnsm tag dependency); `dual-push.sh --hotfix-from <factgraph-tag>` convenience added. Locked into §1, §2.6, §5.4, §5.5, §5.6, §6.1.2, §6.1.9.
  - [x] G0.8 (Gap 8, 2026-05-14): six sub-locks from user round-3 review:
    - G0.8.A: asymmetric default branches (hnsm `master`, factgraph `main`). Supersedes G0.1.
    - G0.8.B: hnsm `feature/X` collected into hnsm `master` after dual-push; hnsm `master` is dev integration line with no release semantics.
    - G0.8.C: factgraph `release/v*` stabilization is stratified — divergent files edited directly on factgraph, shared-region fixes originate in hnsm and project in.
    - G0.8.D: factgraph `release/v*` kept-last-1 with delete-on-next-create + tag-and-merged guard + `--force-delete-stalled-release` escape. Supersedes Gap 5.1.
    - G0.8.E: hotfix uses the same `feature → release/v* → main → tag → publish` shape, scaled-down.
    - G0.8.F: explicit dev/release-manager separation. Dev phase ends at `release/v* → factgraph main` merge. Tag + PyPI publish are release-manager-owned (§5.10 handoff contract).

- [ ] **G1: Bootstrap factgraph main** (§5.8 procedure executed end-to-end):
  - `factgraph/main` branch exists at `2bcd153f` (seeded from `factgraph/release/v1.0.1-rc.1`).
  - GitHub default branch on factgraph is `main`.
  - hnsm-backend `feature/factgraph-post-rc1-2026-05-14` reachable from factgraph and recognized by `dual-push.sh` as a normal feature branch.
  - The pre-existing `release/v1.0.1-rc.1` and `v0.1.0rc1` / `v0.1.0rc2` tags are untouched on factgraph.
  - hnsm-backend `master` remains untouched at its current HEAD.

- [ ] **G2: `scripts/dual-push.sh` implemented** with self-tests covering:
  - Normal projection of N shared-region commits as a single new factgraph commit.
  - No-op when the range touches zero shared-region paths.
  - factgraph default branch discovery via `git ls-remote --symref factgraph HEAD` (not hardcoded `main` or `master`).
  - Disallowed targets: `master`, `main`, `release/v*` (script refuses with clear message).
  - Missing-footer fallback (manually push a footerless commit to a test branch on factgraph; verify warn + merge-base fallback + deviation log entry).
  - Stale-footer detection (rebase hnsm branch; verify refuse without `--force-rewrite`; verify `--force-rewrite` rebuilds projection from `factgraph/<default-branch>` and force-pushes with `--force-with-lease`).
  - Sync-debt recovery (simulate factgraph push failure, verify plain rerun OR `--repair` catches up without git rewrite).
  - `--hotfix-from <factgraph-tag>`: footer parsing, hnsm anchor reachability check, refuse on missing footer.
  - `--force-delete-stalled-release <release/v*>`: refuses without flag when guards fail (not merged, or no tag); succeeds with flag.
  - `--dry-run` prints intended actions without mutating anything.
  - Same-name footer cross-check (try `dual-push.sh feature/X` when factgraph `feature/X` HEAD's `From-hnsm-backend-branch` says `feature/Y`; verify refusal).

- [ ] **G3: `scripts/verify-shared-region-parity.sh` implemented** as a standalone tool AND integrated as `dual-push.sh`'s step 1 self-check helper. Returns 0 on parity, 1 with structured drift report otherwise. Tested at every gate in G4.

- [ ] **G4: Synthetic end-to-end dry-run** of a complete release cycle on synthetic refs only — does NOT push origin or factgraph in production-impacting ways. The flow must match Gap 8 design (dev / release-manager split, asymmetric defaults, factgraph-only release/v*):

  Developer phase (the script + manual sequence covers this end-to-end):
  - Open synthetic `feature/test-dual-push` on hnsm-backend, touching one file in `src/factgraph` and one in `tests/`.
  - `dual-push.sh feature/test-dual-push` to a sandbox factgraph remote (or `--dry-run` for full path simulation against real remote without push side-effects).
  - Verify `verify-shared-region-parity.sh feature/test-dual-push` is green.
  - Merge `feature/test-dual-push` into hnsm `master` locally; plain `git push origin master` (Gap 8.B).
  - Create `release/v-test-1` on factgraph only (synthetic, name picked to be obviously test-only), seeded from `factgraph/feature/test-dual-push`. Confirm hnsm-backend has no `release/v-test-1` branch.
  - Stabilization stratification check: attempt a divergent-files-only commit on factgraph `release/v-test-1` (CHANGELOG); attempt a shared-region edit directly on factgraph (must fail or be rejected by tooling).
  - Stabilization shared-region fix: small hnsm `feature/test-fixup`, dual-push, merge into factgraph `release/v-test-1`. Verify footer parity.
  - Verify single-line invariant refuses a second concurrent `release/v-test-2` while `release/v-test-1` is alive and untagged.
  - Merge `release/v-test-1` → `factgraph main` (factgraph-side operation).
  - **Developer phase ends here.** `release/v-test-1` stays alive. No tag created by dev.

  Release-manager phase (acted as a separate operator role, even if the same human in the synthetic run):
  - Tag factgraph: `v-test-1` (synthetic). Verify shared-region tree at the tagged commit matches hnsm master at the corresponding anchor (read via tag footer).
  - Tag is NOT pushed to factgraph remote (kept local only) and may be deleted after the gate.

  Next-cycle / hotfix verification:
  - Verify hotfix lookup path: `dual-push.sh --hotfix-from v-test-1` correctly reads the tag footer, finds the hnsm anchor, and creates the hotfix branch from it (dry-run if avoiding actual branch creation).
  - Verify Gap 8.D delete-on-next-create: starting `release/v-test-2` removes `release/v-test-1` (since merged + tagged); attempting same on a release/v* that was never tagged refuses without `--force-delete-stalled-release`.
  - Clean up all synthetic refs.

- [ ] **G5: Docs + memory sync**:
  - `docs/blueprints/README.md` references this workflow under a new "Cross-repo workflow" entry.
  - `docs/architecture_principles.md` (if relevant) updated.
  - A new memory anchor under `memory/` records the headline decisions (asymmetric hnsm-master / factgraph-main, per-push transparent, 2-field footer, repair-never-rollback, release/v* factgraph-only + keep-last-1, factgraph as tag/version authority, dev/release-manager separation) so future sessions don't relitigate Gap 1-8.
  - Add `scripts/dual-push.sh` and `scripts/verify-shared-region-parity.sh` references to `feedback_release_workflow_traps` or a sibling memory entry as the canonical tools.

**Deferred (separate blueprint):**

The first real release using this workflow — e.g., shipping `v0.1.0-rc.4` (or whichever tag schema is chosen per §8.Q7) — is **explicitly out of scope** for this blueprint per Gap 6. That work will live in a new `<date>_first-dual-repo-release-rollout.md` blueprint that depends on G0-G5 here being green. It will be a "first-use audit" capturing real-world surprises and feeding any required fixes back into a follow-up revision of this workflow.

## 8. Open Questions

Resolved during 2026-05-14 scope round:

1. ~~Where do `release/v*` branches die? Delete after merge to master? Keep as historical pointers?~~ **Initially resolved at Gap 5.1** (delete on merge to master). **Superseded at Gap 8.D** (kept-last-1, delete only when next release/v* is created, with merged+tagged guard). See §5.3 step 2 + §6.1.7.
2. ~~Should `release/v*` lifetime support concurrent stabilization of more than one rc?~~ **Resolved at Gap 5**: no. Single-line is a hard invariant (§6.1.7), script-enforced. `--allow-multiple-release` exists as an escape hatch only.
3. ~~Should the projection commit message preserve per-commit hnsm-backend lineage?~~ **Resolved at Gap 3**: yes, via 2-field footer (`From-hnsm-backend: <sha>` + `From-hnsm-backend-branch: <name>`) appended to every factgraph projection commit. See §5.7.
4. ~~How do we handle reverts? Two-way mirror or one-way?~~ **Resolved at user finding 8 / §6.1.4**: reverts are one-way. Manual revert on factgraph is forbidden; reverts originate in hnsm-backend and project to factgraph like any other commit. The tree-replace mechanism in §5.6 step 6 handles deletions and tree-shape changes automatically (it is a tree replacement, not a diff cherry-pick).
5. ~~Does `dual-push.sh` need a `--rollback` path for factgraph push failures?~~ **Resolved at Gap 4**: no rollback. Failure mode is "sync debt", recoverable via `dual-push.sh --repair <branch>` or plain rerun. See §5.9.
6. ~~Should both repos use `master`, both use `main`, or differ?~~ **Initially resolved at Gap 1** (both `master`). **Superseded at Gap 8.A**: asymmetric — hnsm `master`, factgraph `main`. Scripts discover factgraph default dynamically. See §2.2 + §5.8 + §6.1.6.
7. ~~Who creates release tags and publishes to PyPI?~~ **Resolved at Gap 8.F**: a separate release-manager role, not the developer. Developer phase ends at `release/v* → factgraph main` merge. Release manager owns tag + PyPI publish. Handoff contract in §5.10.

Remaining open (do not block scope-freeze):

8. **Internal-only test files broken by tests removal** — `src/agent/tests/`, `src/domains/*/tests/` reference the deleted `src/kernel/tests/` helpers. Decision (drop / repoint to root `tests/_test_helpers` / move entirely into `tests/`) is a separate cleanup blueprint, independent of dual-repo workflow.
9. **Tag-naming schema alignment** (deferred from Gap 5.3): hnsm-backend uses `v0.1.0-rc.x` (per `project_v0_1_0_rc1_published`), factgraph's existing release branch uses `release/v1.0.1-rc.1`. Next tag schema is unresolved. Options: (a) continue hnsm's `v0.1.x` lineage on factgraph (downgrade from v1 naming, treat v1.x as test-era artifact), (b) reset to a unified v1.x lineage going forward, (c) bridge with an explicit "rebrand" tag. Decision is independent of this workflow and can be made at the next tag-cut moment.
10. **Release-manager identity + escalation policy**: §5.10 handoff contract assumes a release-manager role exists. The specific assignee (Raphael per pyproject co-author, or a CI bot via Trusted Publishers, or rotating duty) is out of scope here. Also the deviation-log format for "developer crosses the boundary in emergency" is left unspecified until first real use surfaces a concrete need.

## Outcome

(To be filled at implemented phase.)

## Deviations

(To be filled at implemented phase.)
