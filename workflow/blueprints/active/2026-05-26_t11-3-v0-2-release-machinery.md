# Task Blueprint: T11.3 v0.2.0 Release Machinery

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Class: L (release machinery; may narrow after Step 4.6)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-26_t11-3-v0-2-release-machinery.audit.md`
- Trigger: Post-T5/T11 release path. T11.2.5 classified the dirty baseline,
  T11.2.6 landed the only production/test dirty blocker, and T11.2/T11.2.7
  resolved release-facing view metadata and match-design seams. T11.3 now owns
  the v0.2.0 release machinery dry-run path.

## 0. Scope Locks

### In scope

T11.3 prepares and verifies the v0.2.0 release workflow. It may edit only the
release machinery and release-facing metadata/docs needed to make a dry-run
truthful:

1. **Release script / projection modernization**:
   - `scripts/release.sh`;
   - `scripts/project_release_surface.sh`;
   - `scripts/release_surface_allowlist.txt`;
   - package/test path assumptions that still reference the old `src/kernel`
     projection.
2. **Release metadata**:
   - `pyproject.toml` version for the v0.2.0 candidate;
   - `CHANGELOG.md` v0.2.0 release notes;
   - root/package README release-facing wording only if dry-run or projection
     gates expose stale truth.
3. **CI / test-projection alignment**:
   - `.github/workflows/factpy-kernel-tests.yml` if it still assumes the old
     namespace or old package/test commands.
4. **Dry-run-first release verification**:
   - run `scripts/release.sh v0.2.0-rc.1 --source-ref <clean-source> --dry-run --yes`
     only after Step 4.6 locks how to handle the remaining tracked dirty docs /
     notebooks;
   - record all blockers and fixes before any live release decision.
5. **Known release traps**:
   - allowlist sync after file moves;
   - test-projection imports of excluded modules;
   - deny-pattern grep on private path references;
   - dry-run cleanup and no accidental tag / release-branch mutation;
   - dependency / environment corruption risks;
   - README / changelog projection truth.

### Out of scope

- Live release, live tag creation, GitHub Release creation, PyPI upload, or
  remote `release/*` mutation.
- Reissuing old `v0.1.0-*` tags or changing old release branches.
- Match API implementation.
- Evidence Phase B.
- Notebook namespace cleanup, unless Step 4.6 decides a temporary stash is the
  release-safe handling path.
- Broad docs rewrites outside release-facing README / changelog / projection
  truth.
- Service, agent, adapter, or SDK runtime feature changes.
- New public DTOs.
- Changing `master`.

### Stop / amend triggers

Pause and amend if Step 4.6 or dry-run shows:

- release dry-run requires production behavior changes outside release
  machinery;
- v0.2.0 scope would need notebook/example cleanup rather than stash/defer;
- v0.2.0 claims require T6 evidence Phase B, T10 adapter semantics execution,
  or other roadmap tracks not in release scope;
- existing `scripts/release.sh` cannot safely support v0.2.0 without a broad
  workflow redesign;
- live publish is requested before a clean dry-run has passed;
- destructive git operations are needed.

## 1. Problem

The current release workflow was last validated for `v0.1.0-rc.3`, when the
public projection still used `src/kernel`. The current codebase has moved the
package discovery to `factgraph*`:

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["factgraph*"]
```

However, the release allowlist and verify command still contain old
`src/kernel` assumptions. `scripts/release.sh` verifies projected tests with:

```bash
PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
```

and `scripts/release_surface_allowlist.txt` is still dominated by `src/kernel/*`
paths. A v0.2.0 dry-run will therefore fail until the projection and verification
machinery are brought forward to the shipped `factgraph` namespace.

T11.2.6 resolved the only production/test dirty blocker. The remaining tracked
dirty files are docs/notebooks classified by T11.2.5. T11.3 must decide how to
handle them before invoking release dry-run because `scripts/release.sh` fails
on tracked dirty files.

## 2. Goals

- Produce a scoped v0.2.0 release machinery plan from current source truth.
- Modernize projection / allowlist / verification only as required for
  `factgraph` v0.2.0.
- Run a clean dry-run for `v0.2.0-rc.1`, or record concrete blockers.
- Keep live publishing behind a separate explicit user authorization.
- Preserve sacred `master` and all existing release refs.

## 3. Inputs

| Source | Role |
|---|---|
| `scripts/release.sh` | Release branch / tag / dry-run driver; currently checks old `src/kernel/tests`. |
| `scripts/project_release_surface.sh` | Projection allowlist + denylist + private-link gate. |
| `scripts/release_surface_allowlist.txt` | Public package projection list; currently old `src/kernel` shaped. |
| `pyproject.toml` | Current package metadata; package discovery already targets `factgraph*`, version still `0.1.0rc3`. |
| `CHANGELOG.md` | Current release notes; only has `0.1.0-rc.1` and Unreleased stub. |
| `.github/workflows/factpy-kernel-tests.yml` | Existing CI surface to check against v0.2.0 commands. |
| `workflow/blueprints/archive/2026-05-13_v0.1.0-rc.3-release.md` | Prior dry-run blueprint and trap precedent. |
| `workflow/blueprints/archive/2026-05-26_t11-2-5-dirty-baseline-triage.md` | Dirty baseline release-handoff source. |
| `workflow/design/design-points/active/post-t5-completion-roadmap.zh.md` | Release ordering and T11.3 role. |

## 4. Draft Decisions To Lock

| # | Decision | Draft leaning |
|---|---|---|
| D1 | Candidate version | Use `v0.2.0-rc.1` as first v0.2 candidate unless Step 4.6 finds an existing tag. |
| D2 | Source ref | Use this T11 release branch HEAD after T11.3 implementation and archive, not `master`, unless user explicitly changes release source policy. |
| D3 | Dirty handling | Before dry-run, use a clean auxiliary worktree or user-authorized stash for the remaining tracked docs/notebooks; do not mutate or revert them in T11.3 by default. |
| D4 | Projection namespace | Migrate allowlist and verification from `src/kernel` to current `src/factgraph` public surface. |
| D5 | Release notes | Add a v0.2.0-rc.1 changelog section that summarizes T5/T11 public API changes without claiming deferred T6/T10 work. |
| D6 | Live release | No live publish in this cycle unless a later explicit user authorization says so after dry-run success. |
| D7 | PyPI | No PyPI upload in the initial dry-run slice; live PyPI remains a separate authorization gate. |

## 5. Expected Step 4.6 Inventory

The scoped commit must record concrete results for:

1. current local / origin branch state and remaining dirty files;
2. existing local and remote `v0.2.0*` tags and `release/0.2.x` refs;
3. current `pyproject.toml` package metadata and version;
4. release script assumptions (`src/kernel/tests`, worktree cleanup, source ref,
   tag checks, branch checks);
5. projection allowlist old/new namespace delta;
6. projection denylist / private-link gate risks;
7. current CI test command assumptions;
8. changelog / README release-facing stale truth;
9. known v0.1 rc.3 release traps and whether each applies to v0.2.0;
10. dry-run strategy in presence of remaining dirty docs/notebooks;
11. proposed exact dry-run command;
12. live publish authorization boundary;
13. implementation file set and any out-of-scope blockers.

## 6. Expected Implementation Shape

Implementation should be staged in small commits if Step 4.6 confirms the
current draft leaning:

1. release machinery sync (`release.sh`, projection script, allowlist, CI if
   needed);
2. release metadata sync (`pyproject.toml`, `CHANGELOG.md`, README only if
   needed);
3. dry-run execution and blocker fixes;
4. closure and archive.

If the dry-run exposes large non-release feature work, stop and amend instead
of absorbing that work into T11.3.

## 7. Verification Gates

- `git diff --check` clean.
- Projection script passes directly or through `release.sh`.
- `scripts/release.sh v0.2.0-rc.1 --source-ref <source> --dry-run --yes`
  passes, or records concrete blockers.
- Dry-run creates no remote refs and cleans local dry-run milestone/tag/branch
  refs.
- No live release without separate explicit authorization.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.

## 8. Acceptance

- [ ] Step 4.6 inventory completed with release refs, dirty handling, and
      namespace projection findings.
- [ ] Dirty docs/notebooks handling decided before any dry-run.
- [ ] v0.2.0 candidate version and source ref locked.
- [ ] Projection allowlist and verify command aligned to current public
      namespace.
- [ ] Release notes / README truth aligned or explicitly deferred.
- [ ] Dry-run passes or concrete blockers are recorded.
- [ ] No live publish / PyPI upload / release-branch push occurs without a
      separate user gate.
