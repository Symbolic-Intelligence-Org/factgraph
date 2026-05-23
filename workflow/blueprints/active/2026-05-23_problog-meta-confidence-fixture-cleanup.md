# ProbLog meta-confidence fixture cleanup

- Status: scoped
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: task blueprint
- Inputs:
  - `src/factgraph/core/evidence/write_protocol.py:39`, `:252-264`, `:268-278`, `:281-315` — canonical enforcement that removed `meta[confidence]` and accepts paired `raw_kind` / `bound`.
  - Archived ProbLog hygiene [2026-05-23_problog-import-cycle-hygiene.md](../archive/2026-05-23_problog-import-cycle-hygiene.md) §10.2 / §10.4 — import cycle fixed; `meta[confidence]` fixture drift surfaced as follow-up.
  - Archived T2.2 [2026-05-23_t2-2-arith-expr.md](../archive/2026-05-23_t2-2-arith-expr.md) §10 — full ProbLog export gate still blocked by 6 `meta[confidence]` baseline errors.
  - Track plan [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md) §1.2 G1-G7 and S-class lightweight policy.
- Outputs / Downstream:
  - `tests.test_problog_export` full module gate no longer fails on removed `meta[confidence]` fixture inputs.
  - Future ProbLog-facing slices do not need to repeat the same baseline acknowledgment in closure §10.
- Related:
  - `tests/test_problog_export.py`
  - `tests/test_problog_engine_eval.py`
  - `src/factgraph/core/evidence/write_protocol.py`
- Related Modules:
  - `tests/test_problog_export.py` — stale ProbLog export fixtures use removed `meta[confidence]`.
  - `tests/test_problog_engine_eval.py` — stale ProbLog engine evaluator fixtures use removed `meta[confidence]`.
  - `src/factgraph/core/evidence/write_protocol.py` — source of truth for current write-time metadata validation.
- Audit Log:
  - [2026-05-23_problog-meta-confidence-fixture-cleanup.audit.md](./2026-05-23_problog-meta-confidence-fixture-cleanup.audit.md)
- Branch: `v0.2.0-blueprint-problog-meta-confidence-fixture-cleanup-2026-05-23`

## 1. Problem

ProbLog-related test gates now execute far enough to hit stale fixture inputs:

- `tests/test_problog_export.py:30` writes `meta={"source": "test", "confidence": 0.25}`.
- `tests/test_problog_export.py:223` writes `meta={"confidence": 0.5}`.
- `tests/test_problog_engine_eval.py:43` writes `meta={"source": "test", "confidence": 1.0}`.
- `tests/test_problog_engine_eval.py:50` writes `meta={"source": "test", "confidence": 1.0}`.

Those inputs violate current write protocol. `src/factgraph/core/evidence/write_protocol.py:39` lists `confidence` as a removed uncertainty meta key, and `src/factgraph/core/evidence/write_protocol.py:268-278` raises:

```text
meta[confidence] was removed. Use raw_kind / bound for uncertainty inputs.
```

The fixture drift has already been acknowledged in prior closures:

- ProbLog hygiene recorded that the import cycle was fixed and the remaining failure is stale `meta[confidence]` fixture data (`workflow/blueprints/archive/2026-05-23_problog-import-cycle-hygiene.md:285-308`).
- T2.2 recorded 6 full-module `tests.test_problog_export` errors caused by the same baseline (`workflow/blueprints/archive/2026-05-23_t2-2-arith-expr.md:245-256`).

This slice updates only the stale ProbLog test fixtures to current uncertainty metadata shape. It does not change write protocol semantics or ProbLog adapter behavior.

## 2. Goals

### 2.1 Hygiene driver — migrate stale ProbLog export fixtures

Replace removed `meta[confidence]` inputs in `tests/test_problog_export.py` with current metadata that preserves each test's intent:

- shared default fixture keeps `source` metadata and no uncertainty field unless the test explicitly needs uncertainty metadata.
- `test_claim_probability_ignores_meta_confidence` is rewritten to assert that generic shared `confidence` annotation remains ignored without calling removed `meta[confidence]` input.

### 2.2 Hygiene driver — migrate stale ProbLog engine evaluator fixtures

Replace removed `meta[confidence]` inputs in `tests/test_problog_engine_eval.py` with current deterministic fixture metadata so evaluator tests can reach their intended assertions.

### 2.3 G1/G4 — Preserve enforcement truth

Do not relax or edit `write_protocol.py`. The canonical rule is already correct: removed uncertainty keys are rejected and paired `raw_kind` / `bound` is the accepted uncertainty input path.

### 2.4 G5 — Keep scope test-only

This is a fixture cleanup. Any newly surfaced failure outside removed `meta[confidence]` fixture inputs must be recorded in §10 and handled separately unless it is directly caused by the fixture migration.

## 3. Non-goals

- No change to `src/factgraph/core/evidence/write_protocol.py`.
- No change to ProbLog adapter export/evaluation semantics.
- No change to SDK, application protocol, or evidence write APIs.
- No broad migration of every test suite that still contains historical `confidence` language. This slice only targets ProbLog gates repeatedly blocked in prior closures.
- No rewrite of probability annotation semantics. Existing `problog/semantic/probability` and `shared/semantic/probability` tests remain authoritative.
- No cleanup of unrelated `meta[confidence]` occurrences in PyReason, SDK, schema, or archived historical tests.

## 4. Current Context

### 4.1 G2/G3 — Write protocol rejects removed keys and accepts raw uncertainty pair

`src/factgraph/core/evidence/write_protocol.py:39` includes `confidence` and `confidence_source` in `_REMOVED_UNCERTAINTY_META_KEYS`.

`src/factgraph/core/evidence/write_protocol.py:252-264` normalizes metadata and calls removed-key validation before raw uncertainty normalization.

`src/factgraph/core/evidence/write_protocol.py:268-278` raises the specific `meta[confidence] was removed. Use raw_kind / bound for uncertainty inputs.` error.

`src/factgraph/core/evidence/write_protocol.py:281-315` accepts paired `raw_kind` / `bound`, validates `raw_kind in {"probabilistic", "possibilistic"}`, and normalizes `bound` to a two-element float list.

Reference tests already prove the canonical accepted path:

- `tests/test_write_protocol_annotations.py:189-218` verifies `meta={"raw_kind": "probabilistic", "bound": [0.2, 0.8]}` is projected to shared semantic annotations and meta rows.
- `tests/test_write_protocol_annotations.py:220-232` verifies integer bounds normalize to floats.
- `tests/test_sdk_assertion_record_set.py:189-216` verifies SDK metadata filtering over `raw_kind` and `bound`.

### 4.2 G2/G3 — Stale ProbLog export fixtures

`tests/test_problog_export.py:21-32` defines `_make_sdk(...)`, and `tests/test_problog_export.py:30` uses removed `meta[confidence]`. This helper is used by multiple export tests and causes 5 of the currently observed 6 full-module errors.

`tests/test_problog_export.py:208-238` defines `test_claim_probability_ignores_meta_confidence(...)`, and `tests/test_problog_export.py:223` uses removed `meta[confidence]`. This causes the sixth full-module error.

### 4.3 G2/G3 — Stale ProbLog engine fixtures

`tests/test_problog_engine_eval.py:34-52` defines `_make_sdk(...)`, and lines `43` and `50` use removed `meta[confidence]` in two seed facts. Once the export module gate is clean, these engine evaluator tests should not reintroduce the same fixture baseline.

### 4.4 G2/G3 — Prior closure evidence

ProbLog hygiene closure records the same failure mode and explicitly recommends a follow-up hygiene slice at `workflow/blueprints/archive/2026-05-23_problog-import-cycle-hygiene.md:285-308`.

T2.2 closure records the same full-module failure at `workflow/blueprints/archive/2026-05-23_t2-2-arith-expr.md:245-256`.

## 5. Proposed Shape

### 5.1 Export fixture migration

Update the shared `_make_sdk(...)` helper in `tests/test_problog_export.py` to remove `confidence` from generic `meta`.

The tests that assert deterministic export should still verify that no stale `0.25` fallback appears; the fixture no longer needs to write removed metadata to prove that canonical probability annotations are preferred or absent.

### 5.2 Generic confidence fallback test rewrite

`test_claim_probability_ignores_meta_confidence(...)` should stop using `set_field(..., meta={"confidence": 0.5})`.

Preferred replacement: create the claim with allowed metadata, then append a raw legacy/shared `confidence` annotation row as the test already does. This preserves the intended assertion that generic confidence is not a ProbLog probability fallback, without violating the current write protocol.

### 5.3 Engine evaluator fixture migration

Update `tests/test_problog_engine_eval.py:_make_sdk(...)` seed facts to use allowed deterministic metadata, likely `meta={"source": "test"}`. These tests assert engine options, evaluator registration, body probability extension behavior, and provenance support; they do not require user-authored uncertainty inputs.

### 5.4 G7 pre-impl precondition

Before implementation, verify:

1. `tests/test_problog_export.py` has exactly two removed `meta[confidence]` fixture input sites.
2. `tests/test_problog_engine_eval.py` has exactly two removed `meta[confidence]` fixture input sites.
3. `write_protocol.py` still rejects removed `confidence` and accepts paired `raw_kind` / `bound`.
4. Existing canonical `raw_kind` / `bound` tests still pass.

If any check fails, amend this blueprint before code changes.

## 6. Boundaries And Invariants

- **Test-only invariant**: implementation should touch only ProbLog tests unless G7 precondition proves the fixture list is incomplete.
- **Enforcement invariant**: `write_protocol.py` removed-key validation stays unchanged.
- **Adapter invariant**: no ProbLog adapter code changes.
- **Probability semantics invariant**: `problog/semantic/probability` and `shared/semantic/probability` remain the only probability fallback sources exercised by these tests.
- **No broad confidence cleanup invariant**: generic uses of "confidence" outside the targeted ProbLog fixture inputs stay out of scope.

## 7. Acceptance

- [ ] G7 pre-impl precondition runs and is recorded in the audit log before test edits.
- [ ] `rg 'meta=\\{[^\\n]*confidence' tests/test_problog_export.py tests/test_problog_engine_eval.py` returns no matches after implementation.
- [ ] `PYTHONPATH=src python -m unittest tests.test_problog_export` passes fully.
- [ ] `PYTHONPATH=src python -m unittest tests.test_problog_engine_eval` passes fully, or any new unrelated baseline is documented in §10 with evidence.
- [ ] `PYTHONPATH=src python -m unittest tests.test_problog_export tests.test_problog_engine_eval` passes fully, or any new unrelated baseline is documented in §10 with evidence.
- [ ] `PYTHONPATH=src python -m unittest tests.test_write_protocol_annotations tests.test_sdk_assertion_record_set` keeps passing the canonical metadata reference tests.
- [ ] `python -m ruff check tests/test_problog_export.py tests/test_problog_engine_eval.py` passes.
- [ ] No production source files are changed.

## 8. Implementation Plan

1. Run G7 pre-impl precondition checks from §5.4.
2. Edit only the targeted ProbLog test fixtures.
3. Run the acceptance test gates.
4. If the full ProbLog gates expose a new unrelated baseline, document it in §10 and stop scope expansion.
5. Fill §10 with exact changes and test outcomes.
6. Archive the blueprint pair after `Status: implemented`.

## 9. Docs To Update

- No user-facing docs update expected; this is test fixture hygiene.
- `workflow/memory/current.md` and external memory consolidation should happen after this slice, together with T2.1 / ProbLog hygiene / T2.2 / this cleanup summary.

## 10. Outcome / Deviations

- Pending.
