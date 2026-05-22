# Task Blueprint Audit: Test Grouping Infrastructure

- Blueprint: [2026-05-13_test-grouping-infrastructure.md](./2026-05-13_test-grouping-infrastructure.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-13 | draft | Blueprint created | Captures list-based test grouping before any file moves. |

## Decision Notes

- Initial direction: use list-based grouping first and defer physical test file moves.
- Initial group count is intentionally small: `kernel_core`, `kernel_capabilities`, `kernel_adapters`, `packaging`, `service_boundary`, `docs_and_demos`.
- Groups are allowed to overlap because they represent CI environment membership, not exclusive taxonomy.
- Drift invariant is required: every `src/kernel/tests/test_*.py` must appear in at least one group.
- `test_wheel_kernel_only_packaging.py` is release-relevant but belongs to the packaging/build group, not the minimal kernel runtime group.
- `test_v01_onboarding_journey.py` is a demo/onboarding hardening test and should not be in the minimal kernel build environment.

## Audit Notes

Initial local checks:

- `src/kernel/tests` contains 149 `test_*.py` files.
- `scripts/release_surface_allowlist.txt` currently includes 107 kernel test files.
- `pyproject.toml` publishes `kernel*` and excludes `kernel.tests*`.
- `scripts/project_release_surface.sh` deny-lists `src/service/*`, `src/agent/*`, and `src/domains/*`.
