# Task Blueprint: Round Story Demo Suite

- Status: scoped
- Created: 2026-05-07
- Last Updated: 2026-05-07
- Related Modules:
  - `examples/`
  - `src/kernel/tests`
- Related Docs:
  - [docs/blueprints/archive/2026-05-06_round-story-demo-refresh.md](../archive/2026-05-06_round-story-demo-refresh.md)
  - [src/kernel/application/docs/01_overview.md](../../../src/kernel/application/docs/01_overview.md)
  - [src/kernel/audit/docs/01_overview.md](../../../src/kernel/audit/docs/01_overview.md)
- Audit Log:
  - [2026-05-07_round-story-demo-suite.audit.md](./2026-05-07_round-story-demo-suite.audit.md)

---

## 1. Problem

The initial round-story refresh produced one all-in-one notebook. That is useful
as a smoke harness, but it is not the right learning shape. The archived
examples had clearer topical structure: each notebook had a focused theme and
showed one part of the system.

## 2. Goals

- Keep `round_story_full_demo.py` as the assertion-bearing smoke harness.
- Replace the root all-in-one notebook with focused thematic notebooks.
- Keep every notebook backed by the Python script so behavior does not fork.
- Make `examples/README.md` present the new notebooks as a chaptered current
  journey rather than one giant example.

## 3. Non-goals

- No public API changes.
- No SDK shell, service route, release projection, or dependency expansion.
- No attempt to revive optional PyReason / ProbLog examples as current root
  demos.
- No behavior change to application or audit modules.

## 4. Proposed Shape

Root `examples/` should contain:

- `round_story_full_demo.py` as the testable smoke harness.
- `01_sdk_check_diagnose.ipynb`
- `02_overlay_why_not_frontier.ipynb`
- `03_proofframe_rule_overlays.ipynb`
- `04_round_persistence_diff.ipynb`
- `README.md`

Historical examples stay under `examples/archive/`.

## 5. Acceptance

- [ ] The root all-in-one notebook is removed or archived.
- [ ] The new notebooks are thematic and import the script instead of forking
      behavior.
- [ ] `python examples/round_story_full_demo.py` passes.
- [ ] `python -m unittest src.kernel.tests.test_examples_round_story_full_demo`
      passes.
- [ ] `git diff --check` passes.
- [ ] No SDK/service/release-surface expansion is introduced.

## 6. Outcome / Deviations

To be filled after implementation.
