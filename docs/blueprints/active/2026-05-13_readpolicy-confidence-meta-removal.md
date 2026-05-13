# Task Blueprint: ReadPolicy and Legacy Confidence Meta Removal

- Status: scoped
- Created: 2026-05-13
- Last Updated: 2026-05-13
- Related Modules:
  - `src/kernel/sdk/` (public `ReadPolicy` export, `find(policy=...)`, `run(policy=..., return_display_meta=...)`, `AssertionMeta.confidence`, assertion filtering)
  - `src/kernel/core/evidence/` (write meta normalization and rejected-key policy)
  - `src/kernel/core/view/` (display confidence projection / aggregation)
  - `src/kernel/core/mapping/` (`max_confidence` tie-break reads legacy `meta.confidence`)
  - `src/service/` (runtime `view-facts.policy` wire shape)
  - `src/kernel/core/derivation/` (candidate confidence carriers to preserve)
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/archive/2026-05-13_confidence-evidence-meta-release-cleanup.md](../archive/2026-05-13_confidence-evidence-meta-release-cleanup.md)
  - [docs/blueprints/archive/2026-05-11_frozen-assertion-view-model.md](../archive/2026-05-11_frozen-assertion-view-model.md)
  - [src/kernel/sdk/docs/00_user_guide.en.md](../../../src/kernel/sdk/docs/00_user_guide.en.md)
  - [src/kernel/core/docs/01_architecture.en.md](../../../src/kernel/core/docs/01_architecture.en.md)
  - [src/service/docs/03_runtime_queries_policy.md](../../../src/service/docs/03_runtime_queries_policy.md)
- Audit Log:
  - [2026-05-13_readpolicy-confidence-meta-removal.audit.md](./2026-05-13_readpolicy-confidence-meta-removal.audit.md)

## 1. Problem

`ReadPolicy` is a leftover from the earlier view mechanism. After the frozen
assertion view model and the confidence/evidence meta release cleanup, its
remaining implementation value is narrow: read-time display aggregation of
legacy assertion `meta.confidence` into row-level `confidence` fields and
`return_display_meta` summaries.

At the same time, user-authored uncertainty has moved to the canonical
`meta={"raw_kind": ..., "bound": [...]}` pair and shared annotation rows
`shared/semantic/raw_kind` plus `shared/semantic/bound`. Generic
`meta.confidence` is no longer a ProbLog probability source, PyReason bound
source, shared semantic annotation, or default candidate evidence tree carrier.
Keeping `ReadPolicy` and first-class assertion `confidence` now leaves a small
legacy/display lane that competes with the current uncertainty contract.

This blueprint evaluates and plans a hard cut before release:

- remove `ReadPolicy`
- remove read/display confidence aggregation
- reject new user-authored `meta.confidence` / `meta.confidence_source`
- keep raw metadata as the generic escape hatch
- preserve engine/candidate/certainty internal confidence carriers

## 2. Goals

- Remove `ReadPolicy` from the public SDK and core DTO surface.
- Remove `policy=` support from SDK read/display call sites and service
  `view-facts`.
- Remove `return_display_meta` as a confidence display summary surface.
- Reject new user-authored assertion meta keys `confidence` and
  `confidence_source`, using the same hard-cut style as removed uncertainty
  keys `probability`, `bound_lower`, and `bound_upper`.
- Remove first-class `AssertionMeta.confidence` and
  `AssertionRecordSet.where(confidence=...)`; any raw value with that key is
  only reachable through `record.meta.raw["confidence"]`.
- Remove display confidence aggregation code paths:
  `aggregate_confidence`, `project_display_facts`,
  `_build_entity_confidence_by_ref`, `_build_rule_display_meta`,
  `_collect_confidence_rows_by_e_ref`, and row `confidence` attachment.
- Remove or reject schema/runtime behavior that depends on new
  `meta.confidence` writes, especially `tie_break.mode == "max_confidence"`.
- Keep engine-facing `CandidateSet.confidence` / `confidence_kind`,
  ProbLog/PyReason adapter outputs, and certainty explain internals intact.
- Update SDK, core, service, and official docs so raw uncertainty is explained
  only through `raw_kind` / `bound` and engine semantics wrappers.

## 3. Non-goals

- Do not remove `CandidateSet.confidence` or `CandidateSet.confidence_kind`.
  Those are internal/session compatibility carriers from the 2026-05-13
  confidence/evidence cleanup.
- Do not change ProbLog / PyReason / certainty scoring semantics.
- Do not change `SemanticsProfile`, `ProbLogSemantics`, or
  `PyReasonSemantics`.
- Do not decide whether `evaluate(view=...)` should consume
  `FrozenAssertionView`. Fact-universe scoping for inference evaluation is an
  independent design problem and belongs in a separate blueprint.
- Do not invent a replacement read-display policy in this slice.

## 4. Current Context

- Current `ReadPolicy` DTO lives in `src/kernel/core/store/types.py` and is
  exported by `kernel.sdk`.
- Current SDK read/display call sites:
  - `fg.read.find(..., policy=ReadPolicy(...))` attaches row-level
    `confidence`.
  - `fg.run(rule, policy=ReadPolicy(...), return_display_meta=True)` returns
    `display_meta` shaped as `confidence`, `confidence_strategy`, and
    `source_breakdown`.
  - `fg.run(query, policy=...)` already rejects.
  - `fg.eval.evaluate(..., policy=...)` already rejects.
- Current service call site:
  - `project_runtime_view_facts(session_id, {"policy": {...}})` parses
    inline ReadPolicy shape and switches to display projection.
- Current write behavior:
  - `meta.confidence` is accepted as a float in `(0, 1]`.
  - `meta.confidence_source` is accepted as a string.
  - `meta.confidence` is not in `_SHARED_ANNOTATION_WHITELIST`.
  - `raw_kind` / `bound` are the canonical user-authored raw uncertainty
    inputs.
- Current accept behavior:
  - `_build_base_write_meta(...)` does not write candidate `confidence` or
    `confidence_kind` into assertion meta.
  - service candidate DTOs omit `confidence` / `confidence_kind` by default,
    but accept parsing still tolerates legacy echo payloads.
- Additional current dependency:
  - `core.mapping.canon` supports `tie_break.mode == "max_confidence"` by
    reading `meta.confidence`.
- Verified baseline command:
  - `PYTHONPATH=src python -m unittest kernel.tests.test_confidence_evidence_meta_release_cleanup kernel.tests.test_sdk_read_policy service.tests.test_runtime_query_policy`
  - Result: 60 tests OK on 2026-05-13.

### 4.1 Reference Counts From Draft Survey

Survey commands were run on 2026-05-13 from the repository root.

| Pattern family | Approximate hit count | Notes |
| --- | ---: | --- |
| `ReadPolicy` / `confidence_strategy` / `return_display_meta` | ~204 | concentrated in SDK store, service runtime, SDK docs, official docs, and `test_sdk_read_policy` |
| `meta={...confidence...}` / `meta=.*confidence` | ~46 | mostly test fixtures and tutorials |
| secondary hooks (`AssertionMeta`, `.where(confidence=...)`, `aggregate_confidence`, `project_display_facts`, `max_confidence`) | ~59 | implementation and docs surface requiring explicit cleanup |

## 5. Proposed Shape

### 5.1 Public SDK

- Remove `ReadPolicy` from `kernel.sdk.__all__`.
- Remove `ReadPolicy` import/export from `kernel.sdk`.
- Remove `ReadPolicy` from `kernel.core.store.types`.
- `fg.read.find(..., policy=...)` rejects with a clear removal error:
  `ReadPolicy was removed. Use raw_kind / bound for uncertainty inputs.`
- `fg.read.find(..., view=...)` continues to reject, but its message must no
  longer point to `policy=ReadPolicy(...)`.
- `fg.run(..., policy=...)` rejects for all dispatch paths.
- `fg.run(..., return_display_meta=True)` rejects because display meta is
  removed with ReadPolicy.
- `fg.run(..., view=...)` continues to reject, but its message must no longer
  point to `policy=ReadPolicy(...)`.
- `fg.eval.evaluate(..., policy=...)` continues to reject. The message can
  mention that `policy` was removed / was never accepted for inference.

### 5.2 Assertion Metadata

- Add `confidence` and `confidence_source` to the removed user-authored meta
  key set, or equivalent hard-cut validation path.
- Remove `confidence` and `confidence_source` from convention meta key lists
  and mapped first-class meta kind tables where they only support new writes.
- Raw meta rows with key `confidence`, when present, must remain readable
  through raw meta row APIs and `AssertionMeta.raw`.
- Remove `AssertionMeta.confidence`.
- Remove `.where(confidence=...)` from `AssertionRecordSet`.
- Keep `record.meta.raw` as the raw escape hatch for old rows.

### 5.3 Display Projection

- Remove `kernel.core.view.confidence` if no remaining internal users exist.
- Remove `project_display_facts(...)` or reduce `core.view.projector` to active
  fact projection only.
- Remove SDK helpers that build confidence display metadata:
  - `_build_entity_confidence_by_ref`
  - `_build_rule_display_meta`
  - `_collect_confidence_rows_by_e_ref`
  - `_build_source_breakdown` if it becomes unused
- Remove row-level `confidence` attachment from `find(...)`.

### 5.4 Service Runtime

- Remove inline `policy` parsing for runtime view-facts.
- Remove `_parse_read_policy(...)` and `_read_policy_to_dict(...)`.
- `view-facts` should reject `policy`, `view`, and `view_name` as unsupported
  fields.
- `view-facts` should always return active projected facts through the current
  projection path, not display-confidence projection.

### 5.5 Mapping Tie-break

- Remove or reject `tie_break.mode == "max_confidence"` because new
  `meta.confidence` writes are removed.
- Update validation and docs/tests so the supported tie-break set no longer
  includes `max_confidence`.

### 5.6 Preservation Boundary

- Preserve `CandidateSet.confidence` and `CandidateSet.confidence_kind`.
- Preserve service accept parsing of legacy candidate `confidence` /
  `confidence_kind` unless a later blueprint removes it. This is candidate
  DTO compatibility, not assertion meta.
- Preserve certainty explain internals that operate on candidate support /
  engine carriers. Do not lift generic assertion `meta.confidence` back into
  evidence trees.
- Preserve annotation-domain algorithms where `confidence` is part of
  algorithm-local row data, not assertion `meta.confidence`.

## 6. Boundaries And Invariants

- `raw_kind` and `bound` remain the only user-authored raw uncertainty write
  input.
- `confidence` remains allowed as an internal field name inside engine,
  candidate, certainty, annotation, and audit data structures where it is not
  assertion user meta.
- Raw meta rows must not be promoted back into first-class confidence fields.
- Public removal errors must not point users to a replacement that does not
  exist.
- `view=` rejection remains in place for `find`, `run`, and `evaluate`.
- Inference fact-universe scoping with `FrozenAssertionView` remains out of
  scope.

## 7. Acceptance

- [ ] `from kernel.sdk import ReadPolicy` fails.
- [ ] `from kernel.core.store.types import ReadPolicy` fails.
- [ ] `fg.read.find(..., policy=...)` rejects with a removal message.
- [ ] `fg.run(..., policy=...)` rejects with a removal message.
- [ ] `fg.run(..., return_display_meta=True)` rejects with a removal message.
- [ ] Runtime `view-facts` rejects inline `policy`.
- [ ] `fg.write.set(..., meta={"confidence": 0.5})` rejects with a clear
      message pointing to `raw_kind` / `bound` for uncertainty.
- [ ] `fg.write.set(..., meta={"confidence_source": "x"})` rejects with a
      clear removed-key message.
- [ ] Manually seeded ledger meta rows with key `confidence` remain visible
      through `record.meta.raw["confidence"]`.
- [ ] `AssertionMeta` has no first-class `confidence` attribute.
- [ ] `AssertionRecordSet.where(confidence=...)` is removed or rejects as an
      unsupported keyword.
- [ ] `max_confidence` tie-break is removed or rejected.
- [ ] No test fixture uses user-authored `meta.confidence` as inert seed data;
      any remaining `confidence` references are engine/candidate,
      certainty/annotation-local, or explicit raw-readback guards.
- [ ] `CandidateSet.confidence` / `confidence_kind` tests still pass.
- [ ] ProbLog / PyReason / certainty tests that assert engine carrier behavior
      still pass.
- [ ] No stale `ReadPolicy` public docs remain in SDK, service, or official
      quickstart docs.
- [ ] Affected module docs are synced.
- [ ] No new durable docs entry is needed in `docs/README.md`; if that changes,
      update it.

## 8. Implementation Plan

1. Add red/guard tests for the removal contract:
   `ReadPolicy` imports fail, `policy=` call sites reject,
   `return_display_meta=True` rejects, `meta.confidence` /
   `meta.confidence_source` writes reject, raw readback survives, and
   `CandidateSet` carriers survive.
2. Remove `ReadPolicy` DTO and exports from `kernel.core.store.types` and
   `kernel.sdk`.
3. Remove SDK read/display policy paths and helper functions from
   `src/kernel/sdk/store.py`.
4. Remove display projection / confidence aggregation from
   `src/kernel/core/view/`.
5. Reject `confidence` and `confidence_source` in write protocol and ingest
   metadata validation.
6. Remove `AssertionMeta.confidence` and
   `AssertionRecordSet.where(confidence=...)`.
7. Remove or reject `max_confidence` tie-break in mapping/canonical selection.
8. Remove service runtime `policy` parsing / serialization and update
   `view-facts` behavior.
9. Migrate tests that used `meta={"confidence": 1.0}` as inert fixture data to
   `meta={"source": "test"}` or to `raw_kind` / `bound` when uncertainty is
   relevant.
10. Update SDK, core, service, official quickstart, and adapter docs.
11. Run targeted suites, then broader kernel/service discovery as appropriate.

## 9. Docs To Update

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/01_concepts.en.md`
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/kernel/sdk/docs/03_rules_and_inferences.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/core/docs/02_quality_assessment.en.md`
- `src/kernel/core/docs/04_service_layer.md`
- `src/kernel/core/annotation/docs/README.md`
- `src/kernel/adapters/docs/02_problog_adapter.md`
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
- `src/service/docs/01_overview.md`
- `src/service/docs/02_runtime_sessions.md`
- `src/service/docs/03_runtime_queries_policy.md`
- `src/service/docs/06_frontend_integration.md`
- `src/service/docs/README.md`
- `docs/official/kernel/quickstart/read-write.md`
- `docs/official/kernel/quickstart/assertions.md`
- `docs/official/kernel/quickstart/namespace-map.md`

## 10. Outcome / Deviations

Fill this section after implementation:

- Final result:
- Deviations from the blueprint:
- Reason for any adjustments:
- Archive notes:
