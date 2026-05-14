# Task Blueprint Audit: factgraph Namespace Test Coverage

- Blueprint: [2026-05-14_factgraph-namespace-test-coverage.md](./2026-05-14_factgraph-namespace-test-coverage.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-14 | draft | Blueprint created | Captures test coverage audit for the public `FactGraph` / `fg.*` namespace model. |
| 2026-05-14 | draft | Draft corrected | No test or runtime code changes while draft. Complete namespace source is `docs/official/kernel/quickstart/namespace-map.md`. |
| 2026-05-14 | draft | Coverage matrix filled | Method-level audit done against full namespace surface. 6 Missing + 6 Flat-only + 7 NS-shape-only + 9 Light-NS + 2 Stale-conflict gaps recorded. No test or runtime edits. |
| 2026-05-14 | draft | Review-packet workflow recorded | Proposed test additions will be written under `docs/references/working/factgraph-namespace-test-proposals/` first, not directly into root `tests/`. |
| 2026-05-14 | scoped | Scope frozen after self-review | Review packet will cover Stale-conflict, Missing, and Flat-only groups. NS-shape-only and Light-NS groups are deferred. Root `tests/` remain untouched. |
| 2026-05-14 | scoped | Review packet created | Added `README.md`, `stale-conflict.md`, `missing.md`, and `flat-only.md` under `docs/references/working/factgraph-namespace-test-proposals/`. |
| 2026-05-14 | scoped | Review Python proposals added | Added review-only `.py` migration candidates: `test_sdk_fg_assertions_namespace.py`, `test_factgraph_namespace_missing.py`, and `test_factgraph_namespace_flat_only.py`. Direct `PYTHONPATH=src python <file>` sanity runs passed for all three. |

## Decision Notes

- Initial scope is test-only unless the audit exposes a real runtime bug.
- Keep `SDKStore(...)` tests where they validate compatibility, lower-level
  behavior, or delegation.
- Do not mechanically rewrite all old flat SDK tests.
- `FactGraph.load(...)` is the workspace load API; `fg.rules.load(...)` and
  `fg.inferences.load(...)` are authoring-asset load APIs. There is no target
  `fg.load(...)` API in this slice.
- The complete namespace inventory must be derived from
  `docs/official/kernel/quickstart/namespace-map.md`, not from an ad hoc list.
- Test additions and changes must first be authored as review-only proposal
  files under `docs/references/working/factgraph-namespace-test-proposals/`.
  Root `tests/` edits are deferred until after external review.
- Self-review note: `namespace-map.md` still contains several legacy
  `kernel.*` package-name references on this branch. That does not block this
  scope because the file is used here as the method-inventory authority; package
  wording cleanup belongs to a separate docs hygiene task.

## Initial Audit Notes

- `SDKStore(...)` appears in 32 root test files.
- `FactGraph.create(...)`, `FactGraph.from_schema_classes(...)`, or
  `FactGraph.load(...)` appears in 8 root test files.
- Direct `fg.<namespace>.*` usage appears in 6 root test files.
- Existing coverage owners identified so far:
  - `tests/test_sdk_redesign_namespace_shape.py` covers namespace manager shape.
  - `tests/test_sdk_redesign_alias_parity.py` covers representative namespace
    aliases and flat parity.
  - `tests/test_factgraph_workspace_lifecycle.py` covers `FactGraph.create`,
    `FactGraph.load`, `fg.save`, `fg.rules.*`, `fg.inferences.*`,
    `fg.package.export_package`, `fg.views.*`, and representative `fg.eval.*`.
  - `tests/test_schema_mutation_lifecycle.py` covers `fg.schema.add`,
    `fg.rules.list/get`, `fg.inferences.list/get`, and mutation preservation.
  - `tests/test_schema_field_add_lifecycle.py` covers field-add behavior through
    `FactGraph.create`, `FactGraph.load`, `fg.schema.add`, and authoring refs.

## Coverage Matrix

Derived from `docs/official/kernel/quickstart/namespace-map.md`. Method-level
audit against `tests/` on this feature branch (`factgraph` package, post-rename).

### Classification key

- **NS+** — Namespace form exercised in a real public-flow test (not just
  shape/parity).
- **NS shape** — Namespace presence verified only by alias-parity,
  namespace-shape, or redesign-invariants probes; behavior path not exercised
  through the manager.
- **Flat** — Namespace form not exercised, but the flat `SDKStore`/`fg.*`
  counterpart is tested.
- **Missing** — Neither the namespace form nor an obvious flat counterpart is
  exercised by any test.
- **Stale** — Doc/manager say the method ships, but an existing test asserts
  the opposite. Real audit finding, not a coverage gap to fill blindly.

Test-file ownership only lists release-relevant exercisers; namespace-shape
files (`test_sdk_redesign_namespace_shape.py`,
`test_sdk_redesign_alias_parity.py`, `test_sdk_redesign_invariants.py`) appear
for **NS shape** rows.

### FactGraph entry points

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `FactGraph.create(...)` | NS+ | `test_factgraph_workspace_lifecycle`, `test_public_inference_factgraph_create`, `test_schema_mutation_lifecycle`, `test_schema_field_add_lifecycle` | All `path=` / class-first paths exercised. |
| `FactGraph.load(...)` | NS+ | `test_factgraph_workspace_lifecycle`, `test_schema_mutation_lifecycle`, `test_schema_field_add_lifecycle` | Workspace digest validation covered through field-add and mutation lifecycle. |
| `FactGraph.from_schema_classes([...])` | NS+ | `test_factgraph_workspace_lifecycle`, `test_public_inference_factgraph_create`, `test_sdk_frozen_view_surface`, plus shape probes | Lower-level constructor; widely instantiated. |
| `fg.save(path=None)` | NS+ | `test_factgraph_workspace_lifecycle`, `test_schema_mutation_lifecycle`, `test_schema_field_add_lifecycle` | Both no-arg and rebinding paths exercised. |
| `fg.batch(meta=None)` | NS+ light | `test_factgraph_workspace_lifecycle` | Only one exerciser; multi-write batch lifetime is not deeply tested at the namespace surface. |
| `fg.store` | NS+ light | `test_schema_mutation_lifecycle` | Advanced accessor; minimal coverage. |
| `fg.ledger` | NS+ | `test_factgraph_workspace_lifecycle`, `test_schema_field_add_lifecycle`, `test_schema_mutation_lifecycle` | |
| `fg.schema_ir` | NS+ | same as above | |

### `fg.schema`

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.schema.add(...)` | NS+ | `test_schema_mutation_lifecycle`, `test_schema_field_add_lifecycle` | Returns `SchemaAddResult`; destructive-change rejection tested. |
| `fg.schema.ingest(...)` | Flat | `test_sdk_ingest_application_delegate` (flat `sdk.ingest`) | Manager method exists at `store.py:267` and delegates to flat. No namespace-form test. |
| `fg.schema.validate_provenance(...)` | Missing | (none) | No coverage on either namespace or flat form. |

### `fg.read`

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.read.ref(...)` | NS shape | `test_sdk_redesign_alias_parity` | Otherwise exercised only as flat `sdk.ref(...)` across many tests. |
| `fg.read.get(...)` | NS+ | `test_schema_mutation_lifecycle`, `test_sdk_frozen_view_read_runtime_boundaries`, `test_schema_field_add_lifecycle`, alias parity | Real behavior coverage. |
| `fg.read.find(...)` | NS+ | `test_sdk_frozen_view_read_runtime_boundaries`, `test_sdk_read_policy`, alias parity | |

### `fg.write`

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.write.set(...)` | NS+ | `test_schema_field_add_lifecycle`, `test_schema_mutation_lifecycle` | |
| `fg.write.add(...)` | NS+ light | `test_schema_field_add_lifecycle` | Only one namespace-form exerciser. |
| `fg.write.retract(...)` | Flat | `test_sdk_batch_primary_identity`, `test_sdk_frozen_assertion_view`, `test_sdk_assertion_record_set`, `test_sdk_set_add_application_delegate` (all flat `sdk.retract`) | No namespace-form test. |
| `fg.write.edit(...)` | Missing | (none) | No namespace test, no flat `.edit(` instance call observed in `tests/`. Manager method exists at `store.py:353`. |

### `fg.assertions`

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.assertions.by_id(...)` | NS+ | `test_sdk_fg_assertions_namespace` | |
| `fg.assertions.by_ids(...)` | NS+ | `test_sdk_fg_assertions_namespace` | |
| `fg.assertions.field(Field)` | Stale-ish gap | `test_sdk_fg_assertions_namespace` (only via legacy `FieldAssertions`/`AssertionRecordSet` flows; no direct `.field(` namespace call) | Manager method ships at `store.py:230`, `namespace-map.md` documents it; no test exercises `fg.assertions.field(...)`. |
| `fg.assertions.active()` | **Stale conflict** | `test_sdk_fg_assertions_namespace:61-66` | Test asserts `hasattr(sdk.assertions, "active") is False`, but the manager defines `def active(self)` at `store.py:216` and `namespace-map.md` documents it. Either the manager grew past the test, or the namespace doc over-promised. **Audit decision required before any test edits.** |
| `fg.assertions.all()` | **Stale conflict** | same | Same conflict pattern (manager has `def all(self)` at `store.py:221`; test asserts absent). |

### `fg.views`

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.views.create(...)` | NS+ | `test_factgraph_workspace_lifecycle`, `test_schema_mutation_lifecycle`, `test_sdk_frozen_view_read_runtime_boundaries`, `test_sdk_frozen_assertion_view`, `test_sdk_fg_assertions_namespace` | |
| `fg.views.update(...)` | NS+ light | `test_sdk_frozen_assertion_view` | One exerciser only. |
| `fg.views.delete(...)` | NS+ light | `test_sdk_frozen_assertion_view` | One exerciser only. |
| `fg.views.get(...)` | NS+ | `test_factgraph_workspace_lifecycle`, `test_schema_mutation_lifecycle`, `test_sdk_frozen_assertion_view` | |
| `fg.views.list()` | NS+ | `test_factgraph_workspace_lifecycle`, `test_sdk_frozen_assertion_view` | |

### `fg.rules`

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.rules.inspect(...)` | NS+ | `test_factgraph_workspace_lifecycle`, `test_public_inference_factgraph_create`, `test_schema_mutation_lifecycle`, `test_branch_identity_rule_inspect` | Rule / Inference / Query all exercised. |
| `fg.rules.save(...)` | NS+ | `test_factgraph_workspace_lifecycle`, `test_schema_mutation_lifecycle`, `test_schema_field_add_lifecycle` | |
| `fg.rules.load(...)` | NS+ | same as save | Round-trip in mutation lifecycle. |
| `fg.rules.list()` | NS+ light | `test_schema_mutation_lifecycle` | One exerciser only. |
| `fg.rules.get(...)` | NS+ light | `test_schema_mutation_lifecycle` | One exerciser only; returns latest `SavedRuleRef`. |

### `fg.inferences`

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.inferences.save(...)` | NS+ | `test_factgraph_workspace_lifecycle`, `test_schema_field_add_lifecycle`, `test_schema_mutation_lifecycle` | |
| `fg.inferences.load(...)` | NS+ | same | |
| `fg.inferences.list()` | NS+ light | `test_schema_mutation_lifecycle` | |
| `fg.inferences.get(...)` | NS+ light | `test_schema_mutation_lifecycle` | |

### `fg.eval`

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.eval.run(...)` | NS+ | `test_factgraph_workspace_lifecycle`, `test_schema_mutation_lifecycle`, `test_schema_field_add_lifecycle` | |
| `fg.eval.evaluate(...)` | NS+ | `test_factgraph_workspace_lifecycle`, `test_schema_mutation_lifecycle`, `test_schema_field_add_lifecycle`, `test_branch_identity_rule_inspect`, `test_public_inference_factgraph_create`, `test_pyreason_branch_bounds_carrier` | Plus flat `store.evaluate(...)` in ProbLog / PyReason semantics-profile tests. |
| `fg.eval.accept(...)` | Flat | `test_pyreason_e2e` only (flat `sdk.accept(...)`) | No namespace-form test; weakest acceptance coverage on the public surface. |
| `fg.eval.accept_many(...)` | Missing | (none) | No namespace and no flat exerciser. |
| `fg.eval.inspect_semantics(...)` | NS+ | `test_pyreason_branch_bounds_carrier`, `test_public_inference_factgraph_create` | Wrapper + profile shape both covered. |

### `fg.what_if` and sub-namespaces

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.what_if.check(...)` | NS shape | `test_sdk_redesign_invariants` | Behavior covered through flat `sdk.check(...)` in `test_sdk_check`. |
| `fg.what_if.diagnose(...)` | Flat | `test_sdk_diagnose` (flat `sdk.diagnose(...)`) | No namespace-form test. |
| `fg.what_if.why_not(...)` | Flat | `test_sdk_why_not` (flat `sdk.why_not(...)`) | No namespace-form test. |
| `fg.what_if.fact_overlay.check(...)` | NS shape | `test_sdk_redesign_alias_parity`, `test_sdk_redesign_invariants`, `test_sdk_redesign_namespace_shape` | Behavior covered through flat `check_fact_overlay(...)` in `test_sdk_fact_overlay`. |
| `fg.what_if.fact_overlay.recheck_proof_frame(...)` | NS shape | same redesign probes | Behavior covered through flat `recheck_proof_frame(...)` in `test_sdk_proof_frame`, `test_sdk_g2_invariants`, `test_application_proofframe_runtime_native`. |
| `fg.what_if.rule.disable(...)` | NS shape | redesign probes | Behavior covered through flat `check_rule_disable(...)` in `test_sdk_rule_disable`. |
| `fg.what_if.rule.literal_replace(...)` | NS shape | redesign probes | Behavior covered through flat `check_rule_literal_replace(...)` in `test_sdk_rule_literal_replace`. |
| `fg.what_if.rule.add_condition(...)` | NS shape | redesign probes | Behavior covered through flat `check_rule_add_condition(...)` in `test_sdk_rule_add_condition`. |

### `fg.audit`

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.audit.explain_fact(...)` | Missing | (none) | `namespace-map.md` calls this the public bridge into evidence. **Highest-signal public gap.** Manager method at `store.py:601`. |
| `fg.audit.conflicts(...)` | Missing | (none) | No exerciser observed in `tests/`. |
| `fg.audit.diff_proof_frames(...)` | Flat | `test_audit_proof_frame_diff`, `test_sdk_g5_invariants`, `test_sdk_proof_frame_diff`, `test_sdk_redesign_invariants` (all flat `sdk.diff_proof_frames(...)`) | No namespace-form test. |

### `fg.package`

| Surface | Class | Tests | Notes |
| --- | --- | --- | --- |
| `fg.package.export_package(...)` | NS+ | `test_factgraph_workspace_lifecycle` (namespace) + `test_souffle_witness_where_compile_v1` (flat) | |
| `fg.package.run_package(...)` | Missing | (none) | Manager method at `store.py:631`; no exerciser. |

## Summary

### Quantitative

- Tests under `tests/` (root release suite): 123.
- Tests using `FactGraph.*` or `fg.*` namespace form: **8**.
- Tests that still instantiate only `SDKStore(...)` (no `FactGraph` /
  no `fg.` namespace use): **31** (one of them,
  `test_sdk_fg_assertions_namespace.py`, still exercises namespace via
  `sdk.assertions.*` despite the `SDKStore(...)` constructor).
- All tests import from `factgraph.*`; no leftover `from kernel.*` imports
  (factgraph-rename appears clean on this branch).

### Coverage hot spots

The bulk of namespace-form behavior coverage concentrates in three files:

- `test_factgraph_workspace_lifecycle.py`
- `test_schema_mutation_lifecycle.py`
- `test_schema_field_add_lifecycle.py`

Plus three pure namespace-shape / alias-parity / invariants files:

- `test_sdk_redesign_namespace_shape.py`
- `test_sdk_redesign_alias_parity.py`
- `test_sdk_redesign_invariants.py`

### Gap classes

1. **Missing entirely** (no test reaches the surface in any form)
   - `fg.schema.validate_provenance(...)`
   - `fg.write.edit(...)`
   - `fg.eval.accept_many(...)`
   - `fg.audit.explain_fact(...)`
   - `fg.audit.conflicts(...)`
   - `fg.package.run_package(...)`

2. **Flat-only** (namespace path not exercised, flat is)
   - `fg.schema.ingest(...)`
   - `fg.write.retract(...)`
   - `fg.eval.accept(...)`
   - `fg.what_if.diagnose(...)`
   - `fg.what_if.why_not(...)`
   - `fg.audit.diff_proof_frames(...)`

3. **NS shape only** (no behavior path through the manager)
   - `fg.read.ref(...)`
   - `fg.what_if.check(...)`
   - `fg.what_if.fact_overlay.check(...)`
   - `fg.what_if.fact_overlay.recheck_proof_frame(...)`
   - `fg.what_if.rule.disable(...)`
   - `fg.what_if.rule.literal_replace(...)`
   - `fg.what_if.rule.add_condition(...)`

4. **Light NS coverage** (single exerciser, may regress silently)
   - `fg.batch(meta=...)`, `fg.store`
   - `fg.write.add(...)`
   - `fg.views.update(...)`, `fg.views.delete(...)`
   - `fg.rules.list()`, `fg.rules.get(...)`
   - `fg.inferences.list()`, `fg.inferences.get(...)`

5. **Stale / contradictory** (doc + manager say method ships; test asserts
   absent)
   - `fg.assertions.active()`
   - `fg.assertions.all()`
   - (Likely the same root cause: `test_sdk_fg_assertions_namespace.py:61-66`
     pre-dates the manager methods landing.)

   Also flagged: `fg.assertions.field(Field)` ships but has no direct
   namespace-form test, only field-assertion record flows.

### Scoped proposal packet

Accepted for review-only proposal files:

- Resolve `fg.assertions.{active,all}` stale conflict first, and add direct
  `fg.assertions.field(Field)` coverage in the same proposal area.
- Add focused namespace-form proposals for the **Missing** group:
  `fg.schema.validate_provenance(...)`, `fg.write.edit(...)`,
  `fg.eval.accept_many(...)`, `fg.audit.explain_fact(...)`,
  `fg.audit.conflicts(...)`, and `fg.package.run_package(...)`.
- Add focused namespace-form proposals for the **Flat-only** group:
  `fg.schema.ingest(...)`, `fg.write.retract(...)`, `fg.eval.accept(...)`,
  `fg.what_if.diagnose(...)`, `fg.what_if.why_not(...)`, and
  `fg.audit.diff_proof_frames(...)`.

Deferred:

- **NS shape only** group: behavior is covered, alias parity holds, and direct
  namespace behavior tests would mostly duplicate existing flat contract suites.
- **Light NS** group: already has at least one namespace-form exerciser; expand
  only if external review asks for stricter release-gate coverage.

### Out of scope confirmation

- 31 SDKStore-only tests are not part of this slice's gap list; many test
  lower-level behavior intentionally (e.g. `test_sdk_assertion_record_set`,
  `test_sdk_error_hierarchy`, application-delegate tests).
- Internal `kernel.audit.round_events` / walker / agent / service / domain
  tests remain out of scope per blueprint §3.
