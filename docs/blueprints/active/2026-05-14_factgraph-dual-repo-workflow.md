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

Today the first cross-repo commit landed as a one-off manual operation (`feature/factgraph-post-rc1-2026-05-14 @ 35ad6662` on the factgraph remote, built from a `/tmp` worktree rooted at `factgraph_test/release/v1.0.1-rc.1`). Going forward this needs a stable, repeatable workflow covering: branch naming, sync cadence, release path through `release/v*` and `main`, tagging, hotfix handling, and divergence rules.

Without an explicit workflow:

- branches in the two repos will drift in naming and HEAD;
- developers may push uneven shared-region states to factgraph;
- release artifacts may disagree across repos (different `src/factgraph` content under the same tag);
- divergent files (pyproject.toml etc.) may get accidentally synced and break factgraph's hatch+pixi build.

## 2. Goals

1. Define a single source-of-truth direction: **hnsm-backend → factgraph** projection. factgraph never originates business-logic commits.
2. Same-name branches across both repos when shared region is involved (`feature/X`, `release/v*`, `main`, `hotfix/X` all use identical names).
3. Define the release pipeline: `feature/* → release/v* → main → tag main → publish`. Force a deliberate "is this ready for release" gate at the feature → release/v* merge.
4. Hotfix path: `hotfix/X` branches from latest tag on `main`, merges back to `main`, gets a new patch tag (gist-style fast lane, no `release/v*` detour).
5. Sync cadence: **per-push**. When a developer pushes hnsm-backend with shared-region changes, the same push action projects to factgraph. Atomic at push time, not commit time.
6. Version authority: **factgraph**. factgraph's `pyproject.toml` uses `hatch-vcs` to derive version from the tag. hnsm-backend's `pyproject.toml` carries a manually-bumped version that mirrors what factgraph will tag (advisory, not authoritative).
7. PyPI publish: both `rc` and `final` tags publish to PyPI from the factgraph repo (matches the v0.1.0-rc.1 precedent).
8. Tooling: a `scripts/dual-push.sh` script implementing the projection, plus a `scripts/verify-shared-region-parity.sh` invariant checker. Both live in hnsm-backend.

## 3. Non-goals

- Not changing factgraph's existing `release/v1.0.1-rc.1` branch or the v0.1.0rc1 / v0.1.0rc2 tags.
- Not rewriting `scripts/release.sh`. This blueprint complements it; `release.sh` may still drive PyPI publish from factgraph in a future iteration.
- Not auto-syncing every hnsm-backend commit via a post-commit hook. Push-time projection is the explicit chosen cadence.
- Not handling more than one active `release/v*` branch at a time. Concurrent release lines are out of scope.
- Not bridging pyproject.toml or any non-shared file. These are accepted divergences.
- Not synchronizing factgraph-only scaffolding edits (pixi.lock updates, README authoring, CI yaml tweaks) back to hnsm-backend. Those live only in factgraph.
- Not introducing a `develop` branch or any GitFlow construct beyond `feature/*`, `release/v*`, `main`, `hotfix/*`.

## 4. Current Context

- hnsm-backend default branch: `master @ 99452270` (origin).
- factgraph default branch: not yet created; only `release/v1.0.1-rc.1 @ 2bcd153f` + `feature/factgraph-post-rc1-2026-05-14 @ 35ad6662` exist.
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
main ───────────────────────────────────────────────────────────────────●─────►
                              │                                        ╱
release/v0.1.0-rc.4 ──────────●──●(version bump, CHANGELOG, QA fix)──●
                              ▲                                     
                              │ (merge --no-ff, deliberate gate)
                              │
feature/A ──●──●──●──●────────●           ← may include internal-only commits
feature/B ──●──●──●──●───●────●(later)    ← same
hotfix/Z   ←─ from tag v0.1.0-rc.3 ─→ merge back to main → tag v0.1.0-rc.3.1


factgraph (shared region only):                                     tag v0.1.0-rc.4
                                                                         ▼
main ───────────────────────────────────────────────────────────────────●─────► PyPI publish
                              │                                        ╱
release/v0.1.0-rc.4 ──────────●───────────●(CHANGELOG, pyproject.toml in factgraph)─●
                              ▲                                     
                              │
feature/A ──●─────────────────●           ← 0..N projected commits (only shared-region delta)
feature/B ──●─────────────────●           ← same
hotfix/Z   ←─ from tag v0.1.0-rc.3 ─→ merge back to main → tag v0.1.0-rc.3.1
```

Same branch names, identical lifecycle, parallel commits when shared region is involved.

### 5.2 Daily flow (feature development)

1. `git checkout main && git pull origin main` in hnsm-backend.
2. `git checkout -b feature/X`.
3. Work on hnsm-backend. Commits may touch anything (shared region + internal).
4. When ready to publish progress: `scripts/dual-push.sh feature/X`.
   - The script pushes `feature/X` to `origin` (hnsm-backend).
   - Detects commits since last sync point that touched `src/factgraph` or `tests/`.
   - If any: projects a single new commit onto factgraph's `feature/X` (creating the branch if it doesn't exist, rooted at `factgraph/main` if it exists, else at the latest factgraph tag).
   - Pushes factgraph branch.
5. If `feature/X` touches no shared region at all, the script is a no-op for factgraph (only hnsm-backend gets pushed). factgraph branch is never created.

### 5.3 Feature → release/v* gate

1. Decide that `feature/X` is ready for the next release. This is the deliberate "ready" moment.
2. Ensure `release/v0.1.0-rc.4` exists. If not: `git checkout -b release/v0.1.0-rc.4 main` on both repos (only on factgraph if shared region exists).
3. On hnsm-backend: `git checkout release/v0.1.0-rc.4 && git merge --no-ff feature/X`.
4. `scripts/dual-push.sh release/v0.1.0-rc.4` — pushes release branch on hnsm-backend, projects to factgraph release branch.
5. Stabilization commits go directly onto `release/v0.1.0-rc.4` (version bump in hnsm pyproject, CHANGELOG entries in factgraph, last-mile QA fixes). Each one is dual-pushed.

### 5.4 Release / tag / publish

1. Verify `scripts/verify-shared-region-parity.sh release/v0.1.0-rc.4` shows `src/factgraph` + `tests/` tree hashes identical between hnsm-backend and factgraph.
2. On hnsm-backend: `git checkout main && git merge --ff-only release/v0.1.0-rc.4` (FF preferred to keep main linear).
3. `scripts/dual-push.sh main`.
4. Tag both repos at the same SHA on their respective `main`:
   - `git -C hnsm-backend tag -a v0.1.0-rc.4 -m "..."`
   - `git -C factgraph tag -a v0.1.0-rc.4 -m "..."`
5. `git push origin v0.1.0-rc.4` (hnsm-backend) and `git push factgraph v0.1.0-rc.4`.
6. From the factgraph local checkout: `python -m build && twine upload dist/*` (PyPI publish).
7. Delete `release/v0.1.0-rc.4` on both repos (origin + local).

### 5.5 Hotfix path

1. `git checkout -b hotfix/X v0.1.0-rc.3` (latest tag) on hnsm-backend.
2. Fix. Commit(s).
3. `scripts/dual-push.sh hotfix/X` — projects shared region to factgraph hotfix/X.
4. Verify shared-region parity.
5. Merge to main on both repos: `git checkout main && git merge --no-ff hotfix/X`.
6. Dual-push main.
7. Tag both repos: `v0.1.0-rc.3.1`. Push tags.
8. Publish from factgraph (PyPI).
9. (If there's an active `release/v0.1.0-rc.4` branch already, the next stabilization commit on it must `git merge main` to absorb the hotfix.)

### 5.6 Tooling

#### scripts/dual-push.sh

```
Usage: scripts/dual-push.sh <branch> [--from <last-sync-ref>] [--squash | --keep-granular] [--dry-run]

Behavior:
  1. git push origin <branch>
  2. Walk commits in [<last-sync-ref>..<branch>]. Default <last-sync-ref> is the
     branch's last recorded sync point (stored in .git/dual-sync/<branch>) or
     the merge-base with main.
  3. If no commit in that range touched src/factgraph or tests/: exit (no factgraph push).
  4. Else: build factgraph commit:
     - Parent = current factgraph/<branch> if it exists, else factgraph/main, else factgraph/release/v1.0.1-rc.1.
     - Tree = parent tree with src/factgraph + tests replaced by hnsm-backend HEAD's.
     - Message: condensed log (or per-commit log if --keep-granular).
  5. git push factgraph <branch>.
  6. Record new sync point in .git/dual-sync/<branch>.
```

#### scripts/verify-shared-region-parity.sh

```
Usage: scripts/verify-shared-region-parity.sh <ref>

Behavior:
  Computes tree hashes of src/factgraph and tests on both repos at <ref>.
  Exits 0 if all four hashes (hnsm src/factgraph, factgraph src/factgraph,
  hnsm tests, factgraph tests) reduce to the expected 2-pair parity.
  Exits 1 with a clear report on drift otherwise.
```

## 6. Boundaries And Invariants

### 6.1 Invariants (always hold)

1. **Shared region tree-hash parity at sync points**: every commit on a factgraph branch has `src/factgraph` + `tests/` tree hashes identical to the corresponding hnsm-backend branch HEAD at the time of projection.
2. **Same tag name + same SHA pointers across both repos for each tag**: e.g., `v0.1.0-rc.4` exists in both repos. The objects they point to differ (one is a hnsm-backend commit, the other is a factgraph commit) but the tag NAME and the shared-region tree under each is identical.
3. **factgraph never originates shared-region commits**: no shared-region change is authored on factgraph. All `src/factgraph` or `tests/` modifications originate in hnsm-backend and arrive in factgraph via projection.
4. **Divergent files never enter the projection set**: `pyproject.toml`, `README.md`, `LICENSE`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `pixi.lock`, `.github/` are owned by factgraph (factgraph-side edits live in factgraph commits only; hnsm-side edits to the same files live in hnsm commits only and never project).
5. **main is release-only**: no direct commits to main on either repo. Only fast-forward (or merge --no-ff) from `release/v*` or `hotfix/*`.
6. **One active `release/v*` at a time**.
7. **Tags are immutable**.

### 6.2 Boundaries (what this blueprint does not regulate)

- Internal-only hnsm-backend feature branches that never touch shared region: lifecycle is unconstrained by this blueprint. They live and die on hnsm-backend without factgraph involvement.
- Documentation under `docs/`, blueprints under `docs/blueprints/`, memory under `memory/` — these are hnsm-internal and never project to factgraph.
- PyPI release mechanics beyond `python -m build && twine upload`. Specific testing on TestPyPI is out of scope here.
- GitHub Release artifact creation (separate concern; may piggyback on the tag step in a future blueprint).
- CI/CD configuration on either repo.

### 6.3 Re-iteration of related-memory traps

- `feedback_push_master_gate`: never auto-push main. `dual-push.sh main` must require explicit invocation; no automation.
- `feedback_release_workflow_traps`: the 6 known release-script traps still apply when wiring `release.sh` together with this workflow.
- `feedback_blueprint_workflow`: this blueprint follows the standard `docs/blueprints/active/` draft → scoped → implementing → implemented → archived lifecycle.
- `project_release_branch_invariants`: existing `release/0.1.x` and `master` in hnsm-backend remain sacred; this blueprint does NOT modify them.

## 7. Acceptance

(To be filled at scoped phase. Working draft of acceptance gates:)

- [ ] G0: Workflow design and naming locked. User-confirmed.
- [ ] G1: `scripts/dual-push.sh` implemented; passes self-test on a small feature branch.
- [ ] G2: `scripts/verify-shared-region-parity.sh` implemented; integrated into `dual-push.sh` pre-push check.
- [ ] G3: Worked example: dry-run the workflow on a synthetic `feature/test-dual-push` end-to-end (feature → release/v* → main → tag → no actual PyPI publish).
- [ ] G4: Update `docs/architecture_principles.md` and / or `docs/blueprints/README.md` to reference this workflow. Sync `feedback_blueprint_workflow` or related memory as needed.
- [ ] G5: First real cycle: ship the next release (`v0.1.0-rc.4` candidate) using this workflow. Outcome recorded.

## 8. Open Questions

1. Where do `release/v*` branches die? Delete after merge to main? Keep as historical pointers?
2. Should `release/v*` lifetime support concurrent stabilization of more than one rc (e.g., rc.4 and rc.5 in parallel) if we ever cross-ship to two PyPI lines? (Currently scoped as "one at a time".)
3. Should the projection commit message preserve per-commit hnsm-backend lineage (e.g., footer `from-hnsm-backend: <sha>`)? Tradeoff: traceability vs. clutter.
4. How do we handle reverts? If a hnsm-backend commit that already projected to factgraph is reverted, do we revert in factgraph too?
5. Internal-only test files (e.g., `src/agent/tests/`) currently broken after the kernel/tests deletion — should we drop them, repoint them at root `tests/_test_helpers`, or move them entirely into the `tests/` directory? (Tangentially related; can defer to a separate cleanup blueprint.)
6. Does `dual-push.sh` need a `--rollback` path for when a push to factgraph fails after origin push succeeds?

## Outcome

(To be filled at implemented phase.)

## Deviations

(To be filled at implemented phase.)
