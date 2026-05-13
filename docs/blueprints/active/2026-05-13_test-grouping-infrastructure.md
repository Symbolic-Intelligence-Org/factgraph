# Task Blueprint: Test Grouping Infrastructure

- Status: draft
- Created: 2026-05-13
- Last Updated: 2026-05-13
- Related Modules:
  - `src/kernel/tests/`
  - `scripts/release.sh`
  - `scripts/project_release_surface.sh`
  - `scripts/release_surface_allowlist.txt`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
- Audit Log:
  - [2026-05-13_test-grouping-infrastructure.audit.md](./2026-05-13_test-grouping-infrastructure.audit.md)

## 1. Problem

`src/kernel/tests/` now contains 149 `test_*.py` files that serve different purposes:

- kernel public runtime verification;
- adapter conformance;
- capability / audit / explain behavior;
- release packaging checks;
- service/session boundary checks;
- official docs and demo/onboarding checks.

The current release workflow is conservative: the projected release surface includes a subset of kernel tests and `scripts/release.sh` runs unittest discovery over all projected `src/kernel/tests/test_*.py` files. That is safe, but it does not express which tests belong to which CI or release environment.

The immediate need is to let release/build environments run the right tests without moving 149 files or rewriting the existing release projection in one risky step.

## 2. Goals

- Introduce list-based test groups under `scripts/test_groups/`.
- Keep every existing test file in its current path for now.
- Start with a small number of practical groups, not a highly fragmented taxonomy.
- Add a runner that executes one named group consistently.
- Add a drift invariant: every `src/kernel/tests/test_*.py` file must appear in at least one group file.
- Document the grouping rubric so new tests can be placed intentionally.
- Keep the existing release workflow compatible while creating a path to differentiated CI environments.

## 3. Non-goals

- Do not move test files into new directories in this slice.
- Do not delete tests.
- Do not rewrite CI workflows broadly in this slice.
- Do not change runtime code.
- Do not change release projection semantics beyond optional documentation or future follow-up recommendations.
- Do not split every adapter into separate group files in the first iteration unless audit shows that the combined adapter group is too large to use.

## 4. Current Context

- `pyproject.toml` publishes only `kernel*` packages and excludes `kernel.tests*`.
- `scripts/project_release_surface.sh` deny-lists `src/service/*`, `src/agent/*`, and `src/domains/*`.
- `scripts/release.sh` verifies the staging projection with:

  ```bash
  PYTHONPATH=src python -m unittest discover -s src/kernel/tests -p "test_*.py"
  ```

- `scripts/release_surface_allowlist.txt` currently allowlists 107 kernel test files.
- Local audit found 149 `src/kernel/tests/test_*.py` files.
- The current allowlist already excludes many service/docs/recent blueprint tests, but it still includes at least one demo/onboarding file:
  - `src/kernel/tests/test_v01_onboarding_journey.py`
- `src/kernel/tests/test_wheel_kernel_only_packaging.py` is release-relevant, but belongs to a packaging/build group rather than the kernel runtime unit group.

## 5. Proposed Shape

### 5.1 Group Files

Create `scripts/test_groups/` with one text file per initial group. Each file contains repository-relative test paths, one path per line. Blank lines and `#` comments are ignored.

Initial groups:

| Group | Intended environment | Criteria |
| --- | --- | --- |
| `kernel_core` | minimal kernel runtime release gate | SDK/core/schema/read/write/assertions/rules/inferences/workspace behavior that must hold for every kernel release |
| `kernel_capabilities` | full kernel capability gate | what-if, diagnose, proof frame, audit/explain, capability helpers, and related public capability surfaces |
| `kernel_adapters` | adapter conformance gate | ProbLog, PyReason, Souffle, engine projection, adapter provenance, adapter-specific semantics |
| `packaging` | build/release packaging gate | wheel/projection/package-boundary checks |
| `service_boundary` | service integration gate | tests importing `service.*`, runtime sessions, service auth, service route contracts |
| `docs_and_demos` | documentation/demo hardening gate | official docs baseline, examples, onboarding journeys |

Groups may overlap. A group means "this CI environment should run this file", not "this file has only one conceptual owner".

### 5.2 Runner

Add a small shell runner:

```bash
scripts/run_test_group.sh kernel_core
scripts/run_test_group.sh packaging
scripts/run_test_group.sh kernel_adapters
```

Runner behavior:

- resolve `scripts/test_groups/<name>.txt`;
- ignore blank and comment lines;
- fail clearly if the group does not exist;
- execute listed files via `PYTHONPATH=src python -m unittest`;
- preserve unittest output without hiding failures.

### 5.3 Drift Invariant Test

Add a small test or script-level check that verifies:

- every `src/kernel/tests/test_*.py` appears in at least one `scripts/test_groups/*.txt`;
- every listed test path exists;
- group files do not include non-test files;
- no group file includes duplicate entries.

This invariant prevents new tests from silently falling out of all environments.

### 5.4 Release Interpretation

Recommended initial release usage:

- minimal build env: `kernel_core` + `packaging`;
- full kernel env: `kernel_core` + `kernel_capabilities` + `kernel_adapters` + `packaging`;
- non-kernel release-adjacent envs: `service_boundary`, `docs_and_demos`.

This blueprint does not immediately change `scripts/release.sh`; it prepares the explicit grouping surface first.

## 6. Boundaries And Invariants

- Test grouping is list-based only in this slice.
- Existing test file paths remain unchanged.
- Every current test must be assigned to at least one group before implementation closes.
- Overlap is allowed and intentional.
- `test_wheel_kernel_only_packaging.py` stays release-relevant, but belongs to `packaging`, not `kernel_core`.
- Service-importing tests are not part of minimal kernel runtime release verification.
- Docs/demo tests are not part of minimal kernel runtime release verification.
- Adapter tests are kernel-relevant but should run in the adapter group, not the minimal build group.
- The grouping rubric is current operational truth for CI/test environment placement.

## 7. Acceptance

- [ ] `scripts/test_groups/README.md` documents the grouping rubric and how to choose a group for new tests.
- [ ] Initial group files exist for `kernel_core`, `kernel_capabilities`, `kernel_adapters`, `packaging`, `service_boundary`, and `docs_and_demos`.
- [ ] `scripts/run_test_group.sh <group>` runs the selected group.
- [ ] The runner supports comments and blank lines in group files.
- [ ] A drift invariant verifies that every `src/kernel/tests/test_*.py` file is listed in at least one group.
- [ ] A drift invariant verifies that every listed test path exists.
- [ ] No test files are moved in this slice.
- [ ] Existing full unittest discovery remains possible.
- [ ] A short recommendation is recorded for which groups belong in release build versus full verification.

## 8. Implementation Plan

1. Audit all 149 test files and classify them into the six initial groups.
2. Add a G1 red/guard baseline for test group invariants:
   - group files expected but absent;
   - every test must be represented in at least one group;
   - listed paths must exist.
3. Add `scripts/test_groups/*.txt` and `scripts/test_groups/README.md`.
4. Add `scripts/run_test_group.sh`.
5. Run representative group commands:
   - `scripts/run_test_group.sh packaging`
   - `scripts/run_test_group.sh kernel_core`
6. Run full invariant check.
7. Document any ambiguous files in the audit log.

## 9. Docs To Update

- `scripts/test_groups/README.md`
- `docs/README.md` only if the test grouping docs become a durable top-level docs entry.

## 10. Outcome / Deviations

Task completion will fill:

- final group layout;
- files deliberately assigned to multiple groups;
- files moved out of the minimal release/build environment;
- any scope deviations;
- archive notes.
