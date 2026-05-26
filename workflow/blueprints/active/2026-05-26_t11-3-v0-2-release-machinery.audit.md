# Audit: T11.3 v0.2.0 Release Machinery

- Status: draft
- Created: 2026-05-26
- Last Updated: 2026-05-26
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-26_t11-3-v0-2-release-machinery.md`
- Stage: draft
- Class: L (release machinery; may narrow after Step 4.6)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: four tracked docs/notebooks plus untracked Rainbird reference
  remain from T11.2.5; T11.3 must decide release-dry-run handling before running
  `scripts/release.sh`.
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-26 | draft | TBD | T11.3 blueprint pair drafted | Release machinery cycle after T11.2.6 pushed; current release tooling still contains old `src/kernel` assumptions. |

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
- [ ] Step 4.6 inventory complete.
- [ ] Dirty docs/notebooks dry-run handling decision reviewed.
- [ ] Projection namespace decision reviewed.
- [ ] Release notes / README truth decision reviewed.
- [ ] Dry-run result reviewed.
- [ ] Closure notes filled.
