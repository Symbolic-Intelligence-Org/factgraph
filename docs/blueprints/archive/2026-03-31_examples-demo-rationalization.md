# Task Blueprint: Examples Demo Rationalization

- Status: implemented
- Created: 2026-03-31
- Last Updated: 2026-03-31
- Related Modules:
  - `examples/*.ipynb`
  - `examples/README.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
- Audit Log:
  - [2026-03-31_examples-demo-rationalization.audit.md](./2026-03-31_examples-demo-rationalization.audit.md)

## 1. Problem

Current example notebooks no longer satisfy a consistent demo standard:

- the learning path references a missing `03_certainty_and_evidence_tree.ipynb`
- several notebooks mix explanatory prose into runtime `print(...)` output
- some printed lines are hard-coded scene summaries rather than values derived from real notebook objects
- the flagship three-engine demo should remain truthful and internally coherent as the explain surfaces evolve

## 2. Goals

- restore a coherent examples learning path
- move non-runtime explanatory text into markdown where appropriate
- keep printed output grounded in real evaluated / accepted / explained objects
- preserve each notebook's role while improving cross-notebook consistency

## 3. Non-goals

- redesign notebook domains from scratch
- replace real engine execution with fake string-only walkthroughs
- turn every notebook into the same comprehensive demo
- change implementation truth outside the notebook/docs layer unless required for demo correctness

## 4. Current Context

- current example index lives in `examples/README.md`
- notebook `07_evidence_graph_multi_engine.ipynb` is the flagship cross-engine demo
- notebooks `05` and `06` still carry fallback / expected-behavior prose inside code-cell prints
- notebooks `02` and `04` still reference a missing `03_certainty_and_evidence_tree.ipynb`
- current implementation truth for explain surfaces lives under `src/factpy_kernel/*/docs/`

## 5. Proposed Shape

- fix the broken learning-path references first
- rationalize notebook `07` as the canonical flagship demo:
  - explanatory scene-setting moves into markdown
  - printed values remain derived from runtime objects / explain responses
- clean `05` and `06` so fallback / expectations are documented in markdown, not mixed into runtime output
- do a lighter consistency pass on `04` where prints still restate hard-coded facts
- update `examples/README.md` so notebook purposes and prerequisites match the final set

## 6. Boundaries And Invariants

- Must keep notebook outputs truthful to actual notebook state.
- Must not claim an engine/runtime capability that the current codebase does not implement.
- Must preserve the distinction between:
  - real evaluated data printed from objects
  - explanatory prose in markdown
- If `03` is not restored as a notebook, all stale references to it must be removed or redirected.

## 7. Acceptance

- [x] examples learning path no longer references missing notebooks
- [x] notebook markdown carries the necessary explanatory prose
- [x] printed outputs are derived from real notebook objects / responses rather than static scene text
- [x] flagship demo remains logically coherent across all three engines
- [x] `examples/README.md` is synchronized with the final notebook set

## 8. Implementation Plan

1. Audit the current examples set, missing `03` references, and notebook-specific role boundaries.
2. Repair the learning-path/documentation layer (`examples/README.md`, stale next/prereq links).
3. Refactor `07_evidence_graph_multi_engine.ipynb` so explanatory prose moves to markdown and printed outputs remain object-derived.
4. Refactor `05_dora_pyreason_propagation.ipynb` and `06_problog_probabilistic.ipynb` to separate fallback/prose from runtime output.
5. Do a consistency pass on `04_ecss_souffle_compliance.ipynb` for hard-coded summary prints.
6. Re-validate notebook JSON integrity and update this blueprint outcome.

## 9. Docs To Update

- `examples/README.md`

## 10. Outcome / Deviations

- `examples/README.md` now documents the active notebook set truthfully, including the fact that there is no standalone public `03` notebook and that its certainty / evidence-tree material lives in `04` and `07`.
- Stale `03` references were removed from notebook `02` and notebook `04`, restoring a coherent learning path.
- Notebook `07` was refactored so scene-setting prose moved into markdown and printed output stays grounded in runtime data from native, ProbLog, and PyReason explain calls.
- Notebooks `05` and `06` were cleaned so fallback / expected behavior text lives in markdown, while code-cell output is reserved for real runtime values or real exception surfaces.
- Notebook `04` was tightened so the seeded scenario and fallback behavior are explained in markdown instead of mixed into code-cell narration.
- Validation used notebook JSON parsing, per-cell Python compilation, stale-reference grep checks, and a pure-string `print(...)` scan across the active notebook set.
