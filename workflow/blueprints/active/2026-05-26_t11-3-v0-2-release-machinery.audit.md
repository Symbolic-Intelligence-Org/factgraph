# Audit: T11.3 v0.2.0 Release Machinery

- Status: scoped
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-3-v0-2-release-machinery.md`
- Stage: scoped
- Class: L (release machinery; may narrow after Step 4.6)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: four tracked docs/notebooks plus untracked Rainbird reference
  remain from T11.2.5; T11.3 must decide release-dry-run handling before running
  `scripts/release.sh`.
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | `589a2f4e` | T11.3 blueprint pair drafted | Release machinery cycle after T11.2.6 pushed; current release tooling still contains old `src/kernel` assumptions. |
| 2026-05-26 | scoped | TBD | Step 4.6 release inventory recorded | v0.2 refs absent, package rename B locked, old projection assumptions quantified, clean-worktree dry-run strategy chosen. |

## 2. Pre-Draft Inventory

Read-only findings:

| Item | Finding |
|---|---|
| Branch state | Local branch equals origin after T11.2.6 push before drafting; remaining dirty files are docs/notebooks plus untracked Rainbird reference. |
| Release script | `scripts/release.sh` supports `vX.Y.Z[-rc.N]`, clean tracked-tree preflight, milestone branch, projection, verify, release branch, and tag flow. It still verifies with `PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"`. |
| Projection allowlist | `scripts/release_surface_allowlist.txt` is still old `src/kernel/...` shaped, while current `pyproject.toml` package discovery includes `factgraph*`. |
| Projection denylist | `scripts/project_release_surface.sh` denies private paths including `docs/references/*`, `src/service/*`, `src/agent/*`, `examples/*`, `scripts/*`, `third_party/*`, and repo-governance files. |
| Package metadata | `pyproject.toml` project name remains `factpy-kernel`, version is `0.1.0rc3`, package discovery is `include = ["factgraph*"]`. |
| Changelog | `CHANGELOG.md` has an `Unreleased` stub and `0.1.0-rc.1`; it does not yet describe v0.2.0. |
| Prior release precedent | `2026-05-13_v0.1.0-rc.3-release` dry-run passed after allowlist sync; it recorded release traps and no-live-publish boundary. |

## 3. Step 4.6 Inventory Plan

The scoped inventory must fill:

1. `git status --short --branch`, local/origin ref parity, and remaining dirty
   tracked/untracked files.
2. `git ls-remote --tags origin "v0.2.0*"` and release branch refs for
   `release/0.2.x`.
3. `pyproject.toml` package name/version/package-discovery result.
4. `scripts/release.sh` assumptions and any old namespace/test path references.
5. `scripts/release_surface_allowlist.txt` old namespace hit count and proposed
   target public surface.
6. `scripts/project_release_surface.sh` denylist / private-link gate impact.
7. `.github/workflows/factpy-kernel-tests.yml` current command shape.
8. `README.md` / `CHANGELOG.md` release-facing stale claims.
9. v0.1 rc.3 release-trap checklist, with applicability to v0.2.0.
10. Dirty docs/notebooks dry-run handling decision.
11. Exact dry-run command and source ref.
12. Live release / PyPI authorization boundary.
13. Implementation file set and class confirmation.

## 3.1 Step 4.6 Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | Branch / dirty state | `git status --short --branch`: branch is ahead of origin by the draft commit; remaining dirty tracked files are `docs/references/working/design-points/readme.md`, `examples/01_sdk_check_diagnose.ipynb`, `examples/02_overlay_why_not_frontier.ipynb`, `examples/archive/01_sdk_basics.ipynb`; untracked `rainbird-ai sdk code/` remains ignored. |
| 2 | Release refs | `git ls-remote --tags origin "v0.2.0*"` returned no tags; `git ls-remote --heads origin "release/0.2.x"` returned no branch. |
| 3 | Package metadata | Current `pyproject.toml`: `name = "factpy-kernel"`, `version = "0.1.0rc3"`, `include = ["factgraph*"]`. Scoped decision B: rename distribution to `factgraph`, version `0.2.0rc1`. |
| 4 | Release script assumptions | `scripts/release.sh` still runs projected verification with `src/kernel/tests`; this is stale for current `factgraph` package layout. |
| 5 | Allowlist delta | `scripts/release_surface_allowlist.txt` has 361 lines; 351 are `src/kernel/*`; 0 are `src/factgraph/*`. Full allowlist migration is required before projection can be truthful. |
| 6 | Projection gates | `project_release_surface.sh` denylist excludes private docs, examples, service, agent, domains, third_party, tools, scripts, and governance files. This preserves release-surface hygiene but means README / docs links must not point to excluded paths. |
| 7 | CI | `.github/workflows/factpy-kernel-tests.yml` still runs `ruff`, `mypy`, unittest, and coverage against `src/kernel`. Scoped decision allows renaming to `factgraph-tests.yml` while updating commands. |
| 8 | README / changelog | README still says `factpy-kernel`, `kernel`, `pip install factpy-kernel`, and links to `src/kernel` docs. CHANGELOG lacks v0.2.0-rc.1 and package-rename migration notes. |
| 9 | v0.1 trap applicability | Allowlist sync applies; test-projection import/path assumptions apply; deny-pattern/private-link gate applies; dry-run cleanup/no re-tag mutation applies; dependency corruption remains a monitored risk; README/changelog projection truth applies. |
| 10 | Dirty handling | Do not mutate/stash/revert dirty docs/notebooks in scoped phase. T11.3 dry-run should run from a clean auxiliary worktree after implementation/archive so the release script preflight sees a clean tracked tree. |
| 11 | Dry-run command | Planned from clean auxiliary worktree: `./scripts/release.sh v0.2.0-rc.1 --source-ref HEAD --dry-run --yes`. |
| 12 | Live publish boundary | No live branch push, tag push, PyPI upload, or GitHub Release in this cycle without separate explicit authorization after dry-run. |
| 13 | Implementation file set | Expected files: `pyproject.toml`, `CHANGELOG.md`, `README.md`, `.github/workflows/factgraph-tests.yml` (rename from old workflow), `scripts/release.sh`, `scripts/project_release_surface.sh`, `scripts/release_surface_allowlist.txt`; no service/agent/runtime feature files. |

## 3.2 Scoped Decisions

| Decision | Lock |
|---|---|
| PyPI package name | Rename to `factgraph`; old `factpy-kernel` package is not updated in T11.3. |
| Version/tag | Use `0.2.0rc1` in metadata and `v0.2.0-rc.1` for release dry-run. |
| Migration docs | README and CHANGELOG must show `pip uninstall factpy-kernel && pip install factgraph`; Python import path unchanged. |
| Shim/deprecation old package | No transitional shim package and no old-package deprecation release in T11.3. |
| Dirty handling | Clean auxiliary worktree dry-run is preferred; no stash/revert without later explicit user action. |
| Release mode | Dry-run first, no live publish / PyPI. |

## 4. Verification Plan

- `git diff --check`.
- Direct projection script checks as needed before full release dry-run.
- Full `scripts/release.sh v0.2.0-rc.1 --source-ref <source> --dry-run --yes`
  after Step 4.6 dirty handling and implementation.
- Verify no remote refs are pushed during dry-run.
- Verify local dry-run refs are cleaned or explicitly recorded if cleanup fails.
- Verify `master` remains sacred.

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [x] Step 4.6 inventory complete.
- [x] Dirty docs/notebooks dry-run handling decision reviewed.
- [x] Projection namespace decision reviewed.
- [x] Release notes / README truth decision reviewed.
- [ ] Dry-run result reviewed.
- [ ] Closure notes filled.
