# Task Blueprint: factgraph Namespace Test Coverage

- Status: scoped
- Created: 2026-05-14
- Last Updated: 2026-05-14
- Related Modules:
  - `src/factgraph/sdk/`
  - `tests/`
  - `docs/official/kernel/quickstart/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/official/kernel/quickstart/namespace-map.md](../../official/kernel/quickstart/namespace-map.md)
  - `docs/references/working/factgraph-namespace-test-proposals/`
    (review-only proposed tests)
  - [2026-05-14_factgraph-dual-repo-workflow.md](./2026-05-14_factgraph-dual-repo-workflow.md)
- Audit Log:
  - [2026-05-14_factgraph-namespace-test-coverage.audit.md](./2026-05-14_factgraph-namespace-test-coverage.audit.md)

## 1. Problem

The public SDK surface has moved toward the `FactGraph` / `fg.<namespace>` user
model documented in `docs/official/kernel/quickstart/namespace-map.md`.

Existing tests include namespace-shape and lifecycle coverage, but much of the
older SDK and capability test suite still exercises the flat `SDKStore(...)`
surface directly. That leaves two risks:

1. namespace manager regressions can hide behind flat-method coverage;
2. public examples may drift from what release tests actually exercise.

The goal is to audit and close material gaps without mechanically rewriting the
entire test suite.

## 2. Goals

- Build an explicit coverage matrix for the public `FactGraph` / `fg.*`
  entrypoints listed in `docs/official/kernel/quickstart/namespace-map.md`.
- Identify namespace paths that are public, release-facing, and not already
  materially covered.
- Produce review-only proposed test files in a separate working-reference
  directory before changing the real root `tests/` suite.
- Keep focused flat `SDKStore(...)` tests where they intentionally validate
  compatibility, lower-level behavior, or delegation.
- Preserve the factgraph package rename already present on this feature branch:
  tests import from `factgraph.*`, not `kernel.*`.
- Prefer small public-flow tests over broad duplicate copies of existing flat
  tests.

## 3. Non-goals

- Do not remove `SDKStore` compatibility tests wholesale.
- Do not change SDK runtime behavior unless a test exposes a real bug.
- Do not move tests between release groups in this slice.
- Do not modify existing root `tests/` files during the proposal/review phase.
- Do not fix unrelated agent/service/domain tests unless they directly block
  the namespace coverage work.
- Do not expand the dual-repo workflow blueprint.

## 4. Current Context

- Current feature branch already moved the public package from `src/kernel` to
  `src/factgraph` and root release tests to `tests/`.
- `src/factgraph/sdk/store.py` exposes `FactGraph = SDKStore`.
- Namespace managers exist for schema, read, write, rules, inferences, eval,
  what-if, audit, package, and views.
- Initial ad hoc audit found:
  - 32 test files still instantiate `SDKStore(...)`.
  - 8 test files use `FactGraph.create(...)`,
    `FactGraph.from_schema_classes(...)`, or `FactGraph.load(...)`.
  - 6 test files use `fg.<namespace>.*` directly.
  - Existing coverage is strongest for workspace lifecycle, schema mutation,
    schema field-add, namespace shape, and alias parity.
  - Existing coverage is weaker for public namespace flows around audit,
    package, what-if, and some eval/read/write compatibility paths.

## 5. Proposed Shape

First perform a test-coverage audit against
`docs/official/kernel/quickstart/namespace-map.md`:

- enumerate every documented public namespace and method;
- map each entry to existing root test coverage;
- classify coverage as real public-flow, delegation/shape only, flat
  compatibility only, docs-only, or missing;
- propose focused additions only after the audit is reviewed.

Where existing tests already cover a namespace deeply, do not duplicate them.
Instead, record the existing owner file in the audit and leave it in place.

After the gap list is reviewed and this blueprint moves to `scoped`, create a
review packet under:

```text
docs/references/working/factgraph-namespace-test-proposals/
```

That packet should contain proposed `test_*.py` files and a short `README.md`
mapping each proposed file to the audited gap it covers. These files are review
artifacts only: they are not part of unittest discovery and are not release-gate
truth until explicitly migrated into root `tests/` after review.

Scope-freeze accepts proposal coverage for these gap groups:

- **Stale / contradictory:** propose tests or test edits that resolve
  `fg.assertions.active()`, `fg.assertions.all()`, and direct
  `fg.assertions.field(Field)` coverage against the documented namespace.
- **Missing entirely:** propose focused namespace tests for
  `fg.schema.validate_provenance(...)`, `fg.write.edit(...)`,
  `fg.eval.accept_many(...)`, `fg.audit.explain_fact(...)`,
  `fg.audit.conflicts(...)`, and `fg.package.run_package(...)`.
- **Flat-only:** propose namespace smoke tests for `fg.schema.ingest(...)`,
  `fg.write.retract(...)`, `fg.eval.accept(...)`,
  `fg.what_if.diagnose(...)`, `fg.what_if.why_not(...)`, and
  `fg.audit.diff_proof_frames(...)`.

Scope-freeze defers these groups unless review explicitly asks for them:

- **NS shape only:** alias/shape coverage exists and behavior is covered by
  flat tests, so direct namespace behavior tests are not part of this packet.
- **Light NS:** already has at least one namespace exerciser; no expansion in
  this pass.

## 6. Boundaries And Invariants

- `FactGraph.load(...)` is the workspace loader. There is no public `fg.load`.
- `fg.rules.load(...)` and `fg.inferences.load(...)` load saved authoring
  assets, not workspaces.
- `FactGraph` remains a literal alias of `SDKStore` in this slice.
- Flat `SDKStore(...)` tests remain valid when they test lower-level behavior
  or compatibility.
- Public tests must import from `factgraph.*`, not `kernel.*`.
- Namespace coverage should be release-facing and live under root `tests/`.
- Internal-only agent/service/domain test cleanup is out of scope.
- No test or runtime code changes occur while this blueprint is in `draft`.
- Proposed tests must first land under
  `docs/references/working/factgraph-namespace-test-proposals/` for external
  review. Root `tests/` changes require a later explicit decision.
- Review-proposal files may be executable Python test files, but their location
  marks them as working reference material, not active suite membership.
- `docs/official/kernel/quickstart/namespace-map.md` is the method-inventory
  authority for this slice. Any package-name wording cleanup inside that doc is
  a separate docs hygiene task.

## 7. Acceptance

- [x] A coverage matrix is recorded in the audit log using
      `namespace-map.md` as the complete namespace source.
- [x] Public namespace gaps are classified before any test edits begin.
- [x] Scope-freeze identifies which gaps, if any, will receive new focused
      tests.
- [x] Proposed additions/changes are first represented as review-only files
      under `docs/references/working/factgraph-namespace-test-proposals/`.
- [x] No existing root `tests/` file is changed before review acceptance.
- [x] No broad mechanical rewrite from `SDKStore(...)` to
      `FactGraph.create(...)` is proposed without a specific coverage reason.

## 8. Implementation Plan

1. Extract the documented public namespace surface from
   `docs/official/kernel/quickstart/namespace-map.md`.
2. Audit `tests/` for all `SDKStore(...)`, `FactGraph.*`, and `fg.*` namespace
   uses; record a matrix in the audit log.
3. Identify gaps that matter for public release behavior.
4. Review the gap list before moving this blueprint from `draft` to `scoped`.
5. Only after scope-freeze, create review-only proposed test files under
   `docs/references/working/factgraph-namespace-test-proposals/`.
6. After external review, decide which proposal files migrate into root
   `tests/` and which remain as references or are discarded.

## 9. Docs To Update

- No module docs update expected for test-only coverage.
- If a real behavior bug is found and fixed, update affected
  `src/factgraph/*/docs/` entries before archive.

## 10. Outcome / Deviations

Task completion will fill:

- final namespace coverage matrix;
- tests added or updated;
- any deliberately deferred namespace areas;
- verification commands and results;
- archive notes.
