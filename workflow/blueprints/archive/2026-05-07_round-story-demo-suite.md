# Task Blueprint: Round Story Demo Suite

- Status: implemented
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

- [x] The root all-in-one notebook is removed or archived.
- [x] The new notebooks are thematic. (See §6 deviation: they do **not**
      import the script — they call the real `kernel.application` /
      `kernel.audit` APIs inline. The original "import the script" clause was
      walked back deliberately.)
- [x] `python examples/round_story_full_demo.py` passes.
- [x] `python -m unittest src.kernel.tests.test_examples_round_story_full_demo`
      passes.
- [x] `git diff --check` passes.
- [x] No SDK/service/release-surface expansion is introduced.

## 6. Outcome / Deviations

**Final landed shape:**

- `examples/round_story_full_demo.py` retained as the integrated end-to-end
  smoke target. Unittest asserts on `run_demo()` returning
  `EXPECTED_PHASE_SUMMARY`.
- Four chaptered notebooks shipped at `examples/0[1-4]_*.ipynb`, each
  self-contained: imports `kernel.application` / `kernel.audit` /
  `kernel.sdk` directly, defines the fixture inline, asserts on every
  capability call result.
- Original root all-in-one notebook archived at
  `examples/archive/round_story_full_demo.ipynb`.
- `examples/README.md` rewritten as the chaptered index.

**Deviation from §4/§5 ("notebooks import the script"):**

A first-pass implementation followed §5 literally: notebooks imported
`round_story_full_demo` and called `demo._phase_xxx(...)` wrappers. That
version was reviewed and rejected — the wrapper layer hid every real API
call (`check_derivation_binding`, `recheck_proof_frame`, `start_round`,
etc.) inside the script's phase functions, so reading a notebook taught no
API usage. External integrators (the demo audience) would see only
`demo._phase_check(fixture)` and not how to construct a `CheckRequest` or
consume the `SupportArtifact`.

The four notebooks were torn down (commit `cba3176`) and rewritten in the
inline style of `examples/archive/11_capabilities_e2e_demo.ipynb`: every
notebook imports the real APIs, builds the fixture inline, and asserts on
the result of each capability call. The script was retained for the e2e
smoke contract but no longer participates in notebook content.

**Why the deviation:** the §5 "import the script" clause was a
reduce-duplication instinct that traded away the notebooks' actual purpose
(API usage demonstration). Self-contained notebooks duplicate ~80 lines of
fixture setup across four files; that duplication is acceptable because each
notebook now stands alone as a complete demo of a topic, which is what
"each ipynb is a focused topic" actually requires.

**Commits (in order):**

- `bfe26ef` — first-pass: 4 chapter helpers added to script (later removed)
- `eb4428b`, `94453e0`, `9d7e8c4`, `dae6b6d` — first-pass shell notebooks
- `a42d268` — archive root all-in-one notebook
- `cb0ca48` — first-pass README index
- `cba3176` — **revert**: drop shell notebooks + chapter helpers
- `ab85084`, `020f2c0`, `a01c248`, `624ce16` — inline rewrite of 01–04
- (this commit) — README + blueprint outcome update

**No public-surface change** — `kernel.sdk`, `kernel.application`, and
`kernel.audit` continue to expose exactly what they exposed before this
blueprint. Per the v0.1 Batch 8 decision, the notebooks demonstrate the
advanced-importable path verbatim.
