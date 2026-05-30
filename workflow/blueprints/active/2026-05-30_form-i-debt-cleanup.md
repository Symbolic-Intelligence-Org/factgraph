# Slice 6 — Form I Legacy Debt Cleanup

- Status: draft
- Created: 2026-05-30
- Last Updated: 2026-05-31(preflight amend for PF-R1/PF-REC1-4)
- Slice: Post-Slice 5 housekeeping for Slice 1 Form I hard-removal debt
- Class: S-M(test/docs/example cleanup; no runtime semantics)
- Related Modules:
  - `tests/`
  - `src/service/tests/`
  - `src/domains/ecss/tests/`
  - `src/agent/extraction/docs/`
  - `tools/benchmarks/`
  - `README.md`
  - `tutorials/`
  - `examples/`
  - `src/factgraph/sdk/docs/`
- Related Docs:
  - Stage 1 audit: `workflow/audit/active/2026-05-30_form-i-debt-vs-shipped.md` @ `fb744d95`
  - ADR-FI: `workflow/design/decisions/active/2026-05-29_q-fi-form-i-decision.md`
  - Slice 1 blueprint: `workflow/blueprints/active/2026-05-29_slice-1-form-i-schema.md`
  - Slice 4 archive: `workflow/blueprints/archive/2026-05-30_slice-4-docs-polish.md`
  - Slice 5 archive: `workflow/blueprints/archive/2026-05-30_exists-removal.md`
- Audit Log:
  - [2026-05-30_form-i-debt-cleanup.audit.md](./2026-05-30_form-i-debt-cleanup.audit.md)
- Branch: `v0.2.0-blueprint-form-i-debt-2026-05-30`
- Fork point: `fb744d95` (Slice 6 Stage 1 audit head)
- Stage 2: skipped per Stage 1 review; no new design decision, policies inherit Slice 4/5 dirty/archive/historical locks.

## 1. Problem

Slice 1 hard-removed legacy Form I constructor shapes:

- `Identity(primary_key=...)`
- `Identity(default=...)`
- `Identity(default_factory=...)`
- `Field(cardinality=...)`
- legacy `allow_identity_defaults=True`

The shipped runtime already enforces the hard removal in `src/factgraph/sdk/schema.py`, but Stage 1 audit `fb744d95` found broad callsite debt in tests, sibling package tests/docs, current repo docs, tools, tutorials, and examples. Slice 5 Step 6 surfaced one import-time failure in `tests/test_application_rule_disable_runtime_native.py`; the audit proved that failure is representative, not isolated.

Current effects:

- live test modules can fail at import time before their assertions run;
- sibling package tests under `src/service` / `src/domains` also fail when imported;
- the root `README.md` still presents stale Form I and stale namespace examples as current truth;
- negative tests such as `tests/test_sdk_schema_primary_key_required.py` still assert pre-Form-I semantics and need semantic rewrite, not mechanical substitution.

This slice is housekeeping only: bring current live surfaces into alignment with already-shipped Form I behavior while preserving historical/archive material and dirty user notebooks unless explicitly authorized.

## 2. Goals

- G1 Migrate live positive test fixtures from deprecated Form I constructor shapes to shipped `Identity()` / `Field()` forms.
- G2 Rewrite negative tests that assert old primary-key/default/cardinality semantics into current Form I rejection tests.
- G3 Include sibling package tests/current docs that import or document `factgraph.sdk`.
- G4 Update current docs/tutorials/tools that present deprecated Form I as current truth, including root `README.md`.
- G5 Preserve migration examples, historical decision records, archive examples, heritage docs, and known historical audit references unless explicitly classified as current truth.
- G6 Preserve dirty notebook baseline; do not auto-overwrite dirty active notebooks.
- G7 Keep runtime descriptor behavior unchanged.
- G8 Preserve Q-PR1 sacred paths, sacred branches, and dirty baseline.

## 3. Non-Goals

- N1 Change `Identity` / `Field` runtime descriptor semantics.
- N2 Add compatibility aliases for `primary_key`, `default`, `default_factory`, or `cardinality`.
- N3 Touch Q-PR1 sacred paths.
- N4 Touch shadow store, `:exists`, ledger schema, PyReason adapters, or other carry-forward runtime work.
- N5 Auto-edit dirty notebooks.
- N6 Rewrite archive examples, `workflow/heritage/*`, archived blueprints, archived design-points, or historical audit rows.
- N7 Require absolute zero grep across historical/migration examples.
- N8 Push, PR creation, or master merge.
- N9 Memory consolidation.
- N10 Treat mechanical substitution as sufficient for negative tests.

## 4. Current Context

### 4.1 Stage 1 Audit Summary

Stage 1 audit `fb744d95` ran against committed HEAD, not the dirty working tree.

| Deprecated shape | HEAD hits | Blueprint implication |
|---|---:|---|
| `Identity(...primary_key...)` | 252 | Primary live-test/docs debt plus many historical references. |
| `Identity(...default=...)` | 46 | Some current negative docs plus live tests and archive/historical material. |
| `Identity(...default_factory=...)` | 41 | Mostly historical/archive, plus one live test fixture. |
| `Field(...cardinality=...)` | 336 | Broad live fixture debt plus valid migration-hint text. |
| `allow_identity_defaults=True` | 11 | 8 live test callsites plus historical blueprint/design text. |

Tracked file buckets with at least one hit:

| Bucket | Files | Draft disposition |
|---|---:|---|
| `tests/` | 63 | In scope. |
| `src/` | 7 | In scope for sibling tests/current docs; preserve `src/factgraph/sdk/schema.py` migration hints. |
| current docs (`README.md`, `docs/official`, `src/factgraph/sdk/docs`) | 3 | In scope if current truth; preserve migration examples/negative wording. |
| `examples/` | 9 | Dirty active notebooks decision point; archive examples out of scope. |
| tools/tutorial/reference docs | 12+ | Current tools/tutorials in scope; historical references classified. |
| active workflow/audit/decision/design docs | 11 | Historical/current-status classification required. |

### 4.2 Verified Runtime State

| Surface | Current state | Evidence |
|---|---|---|
| `Identity()` constructor | Rejects all legacy kwargs with `SDKSchemaError`. | `src/factgraph/sdk/schema.py:97-113` |
| `Field()` constructor | Rejects all legacy kwargs with `SDKSchemaError`. | `src/factgraph/sdk/schema.py:143-156` |
| `Field(cardinality=...)` text in runtime | Intentional migration hint, not stale current usage. | `src/factgraph/sdk/schema.py:152-153` |

### 4.3 Representative Live Failures

| File | Failure |
|---|---|
| `tests/test_application_rule_disable_runtime_native.py:34` | Import fails on `Identity(primary_key=True)`. |
| `tests/test_application_entity_view.py:20` | Import fails on `Identity(primary_key=True)`. |
| `src/service/tests/test_runtime_query_policy.py:11` | Import fails on `Identity(primary_key=True)`. |

### 4.4 Dirty Baseline

Known dirty baseline remains outside automatic migration:

- `docs/references/working/design-points/readme.md`
- `examples/01_sdk_check_diagnose.ipynb`
- `examples/02_overlay_why_not_frontier.ipynb`
- `examples/archive/01_sdk_basics.ipynb`
- deleted `workflow/working/.gitkeep`
- untracked `docs/references/working/change-requests-2026-05-27/`
- untracked `rainbird-ai sdk code/`

## 5. Proposed Shape

### 5.1 Live Positive Test Fixture Migration

Migrate live positive fixtures from:

```python
user_id: str = Identity(primary_key=True)
name: str = Field(cardinality="single")
tags: str = Field(cardinality="multi")
```

to shipped Form I:

```python
user_id: str = Identity()
name: str = Field()
tags: list[str] = Field()
```

For multi-value legacy fields, choose the annotation that preserves the test's asserted behavior (`list[T]`, `tuple[T, ...]`, `set[T]`, or `frozenset[T]`), not a blind `str = Field()`.

### 5.2 Sibling Package Test / Doc Migration

Include current sibling package tests/docs that import or document `factgraph.sdk`:

- `src/service/tests/test_problog_candidate_evidence_tree.py`
- `src/service/tests/test_problog_semantic_annotation_l4.py`
- `src/service/tests/test_runtime_query_policy.py`
- `src/domains/ecss/tests/test_phase3_contracts_v1.py`
- `src/agent/extraction/docs/USAGE.md`

These are not archive material; they can fail under the shipped descriptor behavior and should be brought current.

### 5.3 Negative Test Semantic Rewrite

Negative tests must be rewritten semantically.

Examples:

- old "at least one primary identity" tests should become "all Identity fields are accepted as Form I anchors" positive tests or explicit rejection tests for `primary_key=`;
- tests that assert old error strings like `Identity(primary_key=True)` should assert current migration hints or Form I rejection messages;
- `allow_identity_defaults=True` tests should be rewritten to current explicit-identity requirements or removed if they only tested deleted protocol fields.

Known semantic-rewrite targets from preflight:

- `tests/test_sdk_schema_primary_key_required.py`
- `tests/test_application_entity_view.py`
- `tests/test_application_schema_runtime.py`

Mechanical substitution alone is not acceptable for this class.

### 5.4 Current Docs / Tutorials / Tools

Migrate current truth surfaces:

- root `README.md` quickstart, including both Form I declarations and current namespace calls (`fg.entities.*` / `fg.fields.*`);
- `tutorials/evidence-pipeline.cn.md`;
- `tools/benchmarks/bench_scenario_a_audit_delivery_shape.py`;
- `tools/benchmarks/extraction/run_cross_provider_benchmark.py`;
- `tools/benchmarks/extraction/run_multi_model_entity_benchmark.py`;
- `tools/benchmarks/extraction/run_re_docred.py`;
- `src/agent/extraction/docs/USAGE.md`.

Preserve valid current negative wording and migration examples:

- `docs/official/kernel/quickstart/schema.md` statements that `Identity(default=...)` is not Form I;
- `src/factgraph/sdk/docs/04_api_surface.en.md` Old/New migration examples.

### 5.5 Dirty Notebook Decision Point

Do not edit dirty active notebooks by default. Step 5 records one of:

- untouched by default; or
- per-file user authorization received and exact notebook diff reviewed.

### 5.6 Historical / Archive Carve-Outs

Historical references may remain when they are clearly one of:

- migration examples;
- removed-surface error-message examples;
- historical design/audit/problem statements;
- archived examples or heritage material;
- active decision docs describing historical Slice 1/Slice 2 reasoning.

Final grep gates must classify remaining hits instead of demanding global zero across the whole repository.

## 6. Boundaries And Invariants

### 6.1 Scope Freeze

| SF | Lock | Source |
|---|---|---|
| SF1 | Runtime descriptor behavior is already shipped; no changes to `Identity` / `Field` semantics. | FI-V1 / FI-A1 |
| SF2 | Q-PR1 sacred paths remain 0 diff. | FI-V5 |
| SF3 | Live positive tests and sibling package tests migrate to shipped Form I. | FI-R1 / FI-R2 |
| SF4 | Negative tests are rewritten semantically, not mechanically substituted. | FI-R5 |
| SF5 | Current docs/tutorials/tools migrate; migration examples and historical notes may remain with explicit classification. | FI-R3 / FI-REC1-4 |
| SF6 | Dirty notebooks are not auto-overwritten; per-file authorization required. | FI-S1 / FI-A4 |
| SF7 | `examples/archive/*`, `workflow/heritage/*`, archived blueprints, and archived design-points are out of scope unless linked by active current docs. | FI-S2 / FI-A3 |
| SF8 | No shadow-store, `:exists`, Q-PR1, ledger schema, adapter, or unrelated runtime work. | FI-A2 |
| SF9 | `src/factgraph/sdk/schema.py` migration hint text is valid and should not be "cleaned" just to satisfy grep. | FI-V2 |
| SF10 | Sacred branches, dirty baseline, no-push gate, and memory-consolidation gate remain inherited from Slice 4/5. | Cadence inheritance |

### 6.2 Per-Commit Ritual

Each implementation commit must verify:

- current branch is the implementation branch for this blueprint;
- sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`;
- Q-PR1 sacred paths are 0 diff;
- dirty baseline is unchanged;
- `git diff --check` is clean;
- no push unless the user explicitly authorizes it.

## 7. Acceptance

### 7.1 Live Tests / Imports

- [ ] Step 0 records the exact tracked file list for deprecated Form I shapes.
- [ ] Live positive fixtures in `tests/` import successfully after migration.
- [ ] Sibling package tests under `src/service/tests/` and `src/domains/ecss/tests/` import successfully after migration.
- [ ] Tests under `tests/application` and `tests/sdk` that rely on multi-value fields preserve their intended cardinality through annotations.
- [ ] `allow_identity_defaults=True` live tests are rewritten to current explicit-identity behavior.
- [ ] Negative tests assert current Form I rejection semantics and migration hints.
- [ ] Representative migrated test modules run through direct smoke or unittest invocation.
- [ ] No Q-PR1 path is touched by test migration.

### 7.2 Current Docs / Tools

- [ ] Root `README.md` quickstart uses Form I and current canonical namespaces.
- [ ] Root `README.md` quickstart uses Form I and current namespace calls (`fg.entities.*` / `fg.fields.*`).
- [ ] `tutorials/evidence-pipeline.cn.md` and `src/agent/extraction/docs/USAGE.md` no longer present deprecated Form I as current truth.
- [ ] The four in-scope benchmark scripts import successfully or have documented carry-forward blockers.
- [ ] Valid migration examples / negative docs remain classified rather than rewritten blindly.
- [ ] `src/factgraph/sdk/schema.py` migration-hint text remains intact unless a reviewer explicitly authorizes wording polish.

### 7.3 Dirty / Archive / Historical Discipline

- [ ] Dirty active notebooks are untouched by default or edited only with explicit per-file authorization.
- [ ] Archive examples remain untouched unless explicitly brought in scope.
- [ ] Historical workflow/design/audit references remain preserved unless they claim current shipped truth.
- [ ] Final grep gate lists remaining carve-out hits by category.
- [ ] No shadow-store, `:exists`, Q-PR1, ledger schema, or adapter work lands.
- [ ] Sacred branches and dirty baseline are preserved.

### 7.4 Final Checks

- [ ] Target migrated tests/import probes pass.
- [ ] `python -m compileall -q src` clean.
- [ ] `git diff --check` clean.
- [ ] Q-PR1 sacred paths 0 diff against `00488a6e..HEAD`.
- [ ] `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- [ ] §10 Outcome filled with final grep/carve-out counts and carry-forward list.

## 8. Implementation Plan

### Step 0 — Pre-Implementation Inventory Freeze

- Re-run the five Stage 1 grep patterns against implementation-branch HEAD.
- Produce exact file lists for:
  - positive live fixtures;
  - negative tests requiring semantic rewrite;
  - sibling package tests/docs;
  - current docs/tutorials/tools;
  - dirty notebooks;
  - archive/historical carve-outs.
- Confirm no Q-PR1, shadow-store, `:exists`, ledger schema, or adapter work is needed.
- If a blocker appears, pause for blueprint amendment.

**Output**: append inventory rows to audit log Decision Notes, or fold them into Step 1 audit row if trivial. Step 0 does not modify runtime/test files.

### Step 1 — Live Core Test Fixture Migration

Migrate positive fixtures in `tests/`, including root test files and `tests/application` / `tests/sdk` subtrees. Preserve multi-value behavior through type annotations.

### Step 2 — Sibling Package Tests And Docs

Migrate in-scope sibling surfaces:

- `src/service/tests/test_problog_candidate_evidence_tree.py`
- `src/service/tests/test_problog_semantic_annotation_l4.py`
- `src/service/tests/test_runtime_query_policy.py`
- `src/domains/ecss/tests/test_phase3_contracts_v1.py`
- `src/agent/extraction/docs/USAGE.md`

### Step 3 — Negative Test Semantic Rewrite

Rewrite tests that intentionally exercise deleted Form I behavior:

- primary-key-required tests;
- default/default_factory rejection tests;
- `Field(cardinality=...)` rejection tests;
- `allow_identity_defaults=True` deleted-protocol tests.

Known files:

- `tests/test_sdk_schema_primary_key_required.py`
- `tests/test_application_entity_view.py`
- `tests/test_application_schema_runtime.py`

This step should make assertions meaningful under shipped Form I rather than replacing old syntax mechanically.

### Step 4 — Current Docs / Tools / Tutorial Migration

Migrate current truth docs and executable examples:

- root `README.md`;
- `tutorials/evidence-pipeline.cn.md`;
- `tools/benchmarks/bench_scenario_a_audit_delivery_shape.py`;
- `tools/benchmarks/extraction/run_cross_provider_benchmark.py`;
- `tools/benchmarks/extraction/run_multi_model_entity_benchmark.py`;
- `tools/benchmarks/extraction/run_re_docred.py`;
- any current package docs surfaced by inventory.

Do not rewrite valid migration examples or historical notes.

### Step 5 — Dirty Notebook Decision Point

Default: record dirty notebooks as intentionally untouched. If the user explicitly authorizes a notebook, perform per-file diff review and migrate only that notebook.

### Step 6 — Regression Sweep And Final Grep Gate

- Run target import/test smoke commands.
- Run final grep gate for all five deprecated patterns.
- Classify remaining hits into accepted carve-outs or blockers.
- Run `compileall`, `git diff --check`, Q-PR1 diff check, sacred/dirty checks.

### Step 7 — Outcome And Implemented Anchor

- Fill §10 Outcome.
- Flip blueprint status to `implemented`.
- Add audit log `implemented` row.

### Step 8 — Archive Cadence

- Move blueprint + audit to `workflow/blueprints/archive/`.
- Update archive `INVENTORY.md`.
- Add audit log `archived` row.
- No push unless user authorizes.

## 9. Docs To Update

Expected:

- `README.md`
- `tutorials/evidence-pipeline.cn.md`
- `src/agent/extraction/docs/USAGE.md` if in scope
- `tools/benchmarks/bench_scenario_a_audit_delivery_shape.py`
- `tools/benchmarks/extraction/run_cross_provider_benchmark.py`
- `tools/benchmarks/extraction/run_multi_model_entity_benchmark.py`
- `tools/benchmarks/extraction/run_re_docred.py`

Likely no-change / classified:

- `docs/official/kernel/quickstart/schema.md` negative current wording
- `src/factgraph/sdk/docs/04_api_surface.en.md` migration examples
- historical `workflow/design/*` and `workflow/audit/*` references

## 10. Outcome / Deviations

Task completion section. Fill during close.

### 10.1 Final Landing Result

TBD. Should summarize acceptance totals: live tests/imports, docs/tools, dirty/archive/historical discipline, and final checks (per §7: 8 + 6 + 6 + 6 = 26 checkboxes).

### 10.2 Deviations And Amendments

TBD.

### 10.3 Scope Freeze Verification

TBD.

### 10.4 Test Migration Result

TBD.

### 10.5 Docs / Tools Landed

TBD.

### 10.6 Dirty Notebook Handling

TBD.

### 10.7 Final Grep Gate

TBD.

### 10.8 Q-PR1 / Sacred / Dirty Preservation

TBD.

### 10.9 Carry-Forward Dependencies

TBD.

### 10.10 Archive Cadence

TBD.
