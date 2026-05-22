# Task Blueprint: Capabilities E2E Demo

- Status: implemented
- Created: 2026-05-05
- Last Updated: 2026-05-05
- Related Modules:
  - `examples/`
  - `src/kernel/tests/`
  - `src/kernel/application/`
  - `src/kernel/core/rules/`
- Related Docs:
  - [examples/README.md](../../../examples/README.md)
  - [docs/architecture_principles.md](../../architecture_principles.md)
- Audit Log:
  - [2026-05-05_capabilities-e2e-demo.audit.md](./2026-05-05_capabilities-e2e-demo.audit.md)

## 1. Problem

The redesign line now has five shipped, archived capability surfaces:

- Check
- Diagnose
- Fact Overlay Check
- Why-not Universe Diagnose
- Evaluator Frontier Trace

Each capability has focused tests, but there is no single deterministic example
that composes the current portfolio around one small domain. That leaves a gap
between shipped capability docs and operator-facing understanding, and it misses
a cheap regression surface for integration drift across the five public entry
points.

## 2. Goals

- Add one deterministic `.py` example that demonstrates all five shipped
  capabilities on the same tiny domain fixture.
- Keep the fixture readable: `Person(name, age, region)` with three seeded
  people.
- Make the example assertion-bearing so it can fail loudly when a capability
  contract drifts.
- Add a focused smoke test that imports and runs the demo.
- Update the examples index so the `.py` script is discoverable and the
  notebook-only convention reflects the new dedicated demo script.

## 3. Non-goals

- Do not add a sixth capability.
- Do not change Check, Diagnose, Fact Overlay, Why-not, or Frontier runtime
  contracts.
- Do not add SDK substrate or expand public SDK surface.
- Do not touch release base branches (`v0.1-oss-prep` / `master`).
- Do not make this a notebook; the target is a deterministic script usable by
  tests.

## 4. Current Context

- Check / Diagnose / Fact Overlay / Why-not live in `kernel.application`.
- Evaluator Frontier Trace lives in `kernel.core.rules.frontier`.
- Existing examples are notebooks plus the v0.1 onboarding journey.
- Existing runtime tests already contain small `Person` fixtures that can be
  mirrored without adding new domain abstractions.

## 5. Proposed Shape

Add `examples/11_capabilities_e2e_demo.py` with:

1. Setup: `Person` schema and facts for Alice, Bob, and Carol.
2. Phase 1: Check passes for Alice's actual binding.
3. Phase 2: Diagnose localizes Alice's wrong age to the age atom.
4. Phase 3: Fact Overlay changes Alice's age from 25 to 30 and flips the
   requested binding from failed to passed.
5. Phase 4: Why-not Universe Diagnose partitions an explicit universe into Bob
   as green and Alice / Carol as atom-localized red rows.
6. Phase 5: Evaluator Frontier Trace reports an aggregate failed frontier at
   the age atom for `age == 99`.

The script exposes `run_demo(verbose: bool = True) -> dict[str, str]` and runs it
under `if __name__ == "__main__"`. The return value is intentionally lightweight;
the meaningful regression checks are the assertions inside each phase.

Add `src/kernel/tests/test_examples_capabilities_demo.py` as a smoke test that
loads the script by path and calls `run_demo(verbose=False)`.

## 6. Boundaries And Invariants

- Demo code may call public application runtime entrypoints and the public
  evaluator frontier entrypoint.
- Demo code must not write ledger state during Fact Overlay or Frontier phases
  beyond the initial seed setup.
- Smoke test must not rely on stdout text.
- The example must stay deterministic: no optional engines, randomness, network,
  or wall-clock behavior.
- This demo does not bless application-layer opt-in to Frontier as an
  implementation dependency; it is an example script, not `kernel.application`
  runtime code.

## 7. Acceptance

- [x] `python examples/11_capabilities_e2e_demo.py` runs successfully.
- [x] `python -m unittest src.kernel.tests.test_examples_capabilities_demo` passes.
- [x] Focused capability smoke remains deterministic and assertion-bearing.
- [x] `examples/README.md` lists the demo script.
- [x] No runtime capability contract changes are introduced.
- [x] `python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py` passes.

## 8. Implementation Plan

1. Add the demo script with shared setup helpers and five assertion-bearing
   phases.
2. Add the unittest smoke test that imports the script by path and calls
   `run_demo(verbose=False)`.
3. Update `examples/README.md` to list the dedicated `.py` demo.
4. Run focused demo, smoke test, relevant capability tests, and ruff.
5. Fill Outcome / Deviations and archive the blueprint.

## 9. Docs To Update

- `examples/README.md`

No module docs change is required because this task adds an example and smoke
test without changing public runtime behavior.

## 10. Outcome / Deviations

- 最终落地结果：
  - Added `examples/11_capabilities_e2e_demo.py`, a deterministic
    assertion-bearing script that runs Check, Diagnose, Fact Overlay Check,
    Why-not Universe Diagnose, and Evaluator Frontier Trace on one `Person`
    fixture.
  - Added `src/kernel/tests/test_examples_capabilities_demo.py` as a smoke test
    that imports the script by path and calls `run_demo(verbose=False)`.
  - Updated `examples/README.md` to list the dedicated script and clarify the
    notebook/script convention.
- 与 blueprint 不同的地方：
  - The smoke test loader registers the module in `sys.modules` before executing
    it so Python dataclasses can resolve module annotations under
    `importlib.util.spec_from_file_location`.
- 为什么会有这些调整：
  - Direct script execution already worked; the importlib loader adjustment is a
    test harness requirement for dataclass processing, not a demo contract
    change.
- 归档说明：
  - Blueprint and audit are archived under `docs/blueprints/archive/` after
    focused verification.
