# Task Blueprint Audit: Capabilities E2E Demo

- Blueprint: [2026-05-05_capabilities-e2e-demo.md](./2026-05-05_capabilities-e2e-demo.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-05 | scoped | Blueprint created | Scope freezes simple `Person` schema plus `.py` demo and smoke test. |
| 2026-05-05 | implementation | Demo script added | `examples/11_capabilities_e2e_demo.py` demonstrates all five shipped capabilities on one fixture. |
| 2026-05-05 | implementation | Smoke test added | `src/kernel/tests/test_examples_capabilities_demo.py` imports and runs the demo without relying on stdout. |
| 2026-05-05 | verification | Focused verification passed | Demo script, smoke test, six related suites, and ruff passed. |
| 2026-05-05 | close-out | Blueprint marked implemented | Outcome / Deviations filled before archive. |

## Decision Notes

### 2026-05-05 — Simple schema selected

The demo uses a single `Person(name, age, region)` entity because the objective is
to demonstrate cross-capability composition, not RuleRef or multi-entity domain
complexity. A richer schema would obscure the five capability contracts being
shown.

### 2026-05-05 — Dedicated `.py` demo accepted

Existing examples are notebook-first, but this task deliberately adds a
deterministic assertion-bearing script. The script doubles as documentation and a
smoke-test target, which is not a good fit for notebook-only examples.

### 2026-05-05 — Importlib dataclass loader adjustment

The demo ran correctly as a script, but the smoke test initially failed when
loading it via `importlib.util.spec_from_file_location` because the module was
not registered in `sys.modules` before dataclass processing. The smoke test now
registers the module before `exec_module(...)`; this keeps the demo contract
unchanged while making the test loader faithful.

### 2026-05-05 — Verification

Commands run:

- `python examples/11_capabilities_e2e_demo.py`
- `python -m unittest src.kernel.tests.test_examples_capabilities_demo`
- `python -m unittest src.kernel.tests.test_application_check_runtime src.kernel.tests.test_application_diagnose_runtime_native src.kernel.tests.test_application_fact_overlay_runtime_native src.kernel.tests.test_application_why_not_runtime src.kernel.tests.test_core_rules_frontier src.kernel.tests.test_examples_capabilities_demo`
- `python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py`
