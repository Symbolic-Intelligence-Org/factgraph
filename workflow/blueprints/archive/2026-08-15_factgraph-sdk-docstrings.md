# Task Blueprint: FactGraph public SDK docstrings

- Status: superseded
- Created: 2026-08-15
- Last Updated: 2026-08-15
- Related Modules:
  - `src/factgraph/sdk/store.py`
  - `src/factgraph/sdk/product_authoring.py`
  - `src/factgraph/sdk/product_scenario_execution.py`
  - `src/factgraph/sdk/evaluation_query_builder.py`
  - `src/factgraph/sdk/product_evaluation_outcome.py`
- Audit Log:
  - [2026-08-15_factgraph-sdk-docstrings.audit.md](./2026-08-15_factgraph-sdk-docstrings.audit.md)

## 1. Problem

Public SDK docstrings currently mix one-line summaries, internal blueprint
history, implementation commentary and several incompatible styles. New
Product V2 entry points often omit parameter, return, error and side-effect
contracts, making IDE help weaker than the public quickstart.

## 2. Goals

- Adopt Google-style docstrings for public user entry points.
- Add FactGraph-specific Notes for ledger effects, user-code execution,
  source/evidence authority, replay and V0/V1/V2 boundaries.
- Keep examples short and route full workflows to the quickstart.
- Preserve runtime behavior and public signatures exactly.

## 3. Scope

- FactGraph lifecycle and high-frequency namespace entry points.
- Product Rule/Function/Policy builders and occurrence composition.
- Query bind/select/plan terminals.
- Scenario and execution-profile builders.
- Product Outcome/Explain/replay facade.

Private helpers and low-level protocol DTOs only receive docstring changes when
needed to explain a public return type.

## 4. Style Contract

1. One imperative/behavioral summary line.
2. Optional short context paragraph.
3. `Args`, `Returns`, `Raises`, `Examples`, `Notes` only when meaningful.
4. Type annotations remain authoritative; prose explains semantics.
5. Stable error codes are named where users can act on them.
6. No internal blueprint references or implementation-line citations in
   outward help text.

## 5. Acceptance

- [x] Scoped public callables have a summary and applicable Google sections.
- [x] Product Function, Scenario, Query and Outcome side effects/boundaries are
      explicit.
- [x] `help(...)`/`inspect.getdoc(...)` smoke tests pin representative APIs.
- [x] Runtime signatures and behavior are unchanged.
- [x] Focused Product tests, Ruff, mypy and diff-check pass.

## 6. Outcome / Deviations

Implemented the Google-style contract across graph lifecycle and write
namespaces, Product Rule/Function/Policy authoring, Query, Scenario/profile,
and Product Result/Explain/replay entry points. The SDK module documentation
now records the style and FactGraph-specific `Notes` requirements.

Verification on the integrated Product worktree:

- public docstring smoke: 2 passed, 38 subtests;
- application + SDK compatibility cohort: 779 passed, 220 subtests;
- Ruff check, focused mypy and `git diff --check`: passed.

No public signature or runtime behavior was intentionally changed. Full
tutorials remain in `docs/quickstart` rather than being duplicated into
docstrings.

Post-delivery review found that this acceptance scope covered representative
entry points rather than every object exported by ``factgraph.sdk``. The
complete-surface census and remediation supersede this blueprint:
[2026-08-15_factgraph-sdk-docstrings-complete-surface.md](./2026-08-15_factgraph-sdk-docstrings-complete-surface.md).
