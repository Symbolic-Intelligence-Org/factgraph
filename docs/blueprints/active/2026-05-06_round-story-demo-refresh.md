# Task Blueprint: Round Story Demo Refresh

- Status: scoped
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Related Modules:
  - `examples/`
  - `src/kernel/application`
  - `src/kernel/audit`
  - `src/kernel/tests`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/kernel/application/docs/01_overview.md](../../../src/kernel/application/docs/01_overview.md)
  - [src/kernel/audit/docs/01_overview.md](../../../src/kernel/audit/docs/01_overview.md)
  - [src/kernel/sdk/docs/04_api_surface.md](../../../src/kernel/sdk/docs/04_api_surface.md)
- Audit Log:
  - [2026-05-06_round-story-demo-refresh.audit.md](./2026-05-06_round-story-demo-refresh.audit.md)

---

## 1. Problem

Existing demos are section-oriented and partly predate the round-story routemap. They remain useful as historical examples,but the root `examples/` directory no longer has a single current demo that shows the full latest flow from SDK setup through application capabilities,audit round persistence,and ProofFrame diff.

## 2. Goals

- Create a canonical `round_story_full_demo.py` + notebook pair.
- Archive all existing root examples under `examples/archive/` instead of deleting them.
- Make the script deterministic and assertion-bearing so it works as a smoke target.
- Keep the demo default-wheel and native-engine only.
- Keep Batch 8 public boundary clear:advanced capabilities are imported from `kernel.application` / `kernel.audit`,not via new SDK shells or service routes.

## 3. Non-goals

- No SDK shell,service route,release projection,or allowlist expansion.
- No optional PyReason / ProbLog runtime dependency in the new canonical demo.
- No new capability behavior or protocol change.
- No attempt to execute archived notebooks.

## 4. Current Context

- `examples/11_capabilities_e2e_demo.py` already covers Q1-Q5.
- `examples/12_evidence_diff_demo.py` covers a minimal audit ProofFrame diff.
- Batch 4/5a/5b/5c application capabilities and Batch 6/7 audit features are shipped but not presented in one end-to-end demo.

## 5. Proposed Shape

- Move current root examples into `examples/archive/`.
- Add `examples/archive/README.md` to describe archived examples as historical/sectional.
- Add `examples/round_story_full_demo.py` as the source-of-truth executable.
- Add `examples/round_story_full_demo.ipynb` as a readable wrapper over the script.
- Rewrite `examples/README.md` to point at the new demo and archive.

## 6. Boundaries And Invariants

- The demo must not mutate the ledger during overlay/rule what-if phases.
- The script is authoritative;the notebook imports and runs it rather than forking behavior.
- Existing root examples are archived,not deleted.
- No code outside examples/tests/docs is changed.

## 7. Acceptance

- [ ] `python examples/round_story_full_demo.py` passes.
- [ ] `python -m unittest src.kernel.tests.test_examples_round_story_full_demo` passes.
- [ ] The new demo returns the expected compact phase summary.
- [ ] `examples/README.md` has no stale root links to archived examples.
- [ ] `git diff --check` passes.
- [ ] No SDK/service/release-surface expansion is introduced.

## 8. Implementation Plan

1. Archive existing root demos under `examples/archive/`.
2. Build the canonical Python demo by composing existing application/audit APIs.
3. Add a notebook wrapper that imports the Python demo.
4. Add a smoke test for the Python demo.
5. Update examples documentation.
6. Run verification,fill outcome,archive this blueprint.

## 9. Docs To Update

- `examples/README.md`
- `examples/archive/README.md`
- `docs/blueprints/archive/README.md`

## 10. Outcome / Deviations

To be filled after implementation.
