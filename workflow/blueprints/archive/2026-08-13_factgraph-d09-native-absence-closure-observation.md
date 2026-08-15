# Task Blueprint: FactGraph D09 native absence/closure observation

- Status: implemented
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Authority: bounded, disposable native-observation task. It may measure
  current behavior but cannot define public semantic behavior.
- Inputs:
  - [Q17 D09 native absence/closure observation protocol](../../design/decisions/active/2026-08-13_q17-d09-native-absence-closure-observation-decision.md)
  - Existing native evaluator, premise-filter and Fact Overlay implementations.
- Outputs / Downstream:
  - A reproducible tool/test fixture matrix and its observed-only closeout.
- Related:
  - [Archived Query/Scenario program](../archive/2026-08-13_factgraph-query-scenario-program.md)
  - [Q16 EffectiveSnapshot](../../design/decisions/active/2026-08-13_q16-query-effective-snapshot-v1-decision.md)
- Related Modules:
  - `tools/spikes/d09_native_absence_closure/`
  - `tests/application/test_d09_native_absence_closure_spike.py`
- Audit Log:
  - [paired audit](./2026-08-13_factgraph-d09-native-absence-closure-observation.audit.md)

## 1. Problem

The product design needs to know whether a future `WITHOUT_FIELD` or closure
concept can reuse the current engine. Existing names such as `RemoveFact`,
premise exclusion, and `not` are easy to over-read. The current semantics must
be measured before any public Scenario or Query surface is considered.

## 2. Goals

- Freeze and execute Q17's seven native observation cells.
- Preserve raw, inspectable results and an explicit interpretation boundary.
- Make the matrix cheap to rerun after future engine changes.

## 3. Non-goals

- Define or ship absence, closure, masking, signed predicates, source
  authority, generic premises, or a What-if operation.
- Change runtime code, exports, docs/API behavior, Query/Scenario, Explain,
  replay, Meander, or any non-native engine.

## 4. Current context

- The archived P1/P2 program makes P3 a semantic stop line.
- Current native `not` is correlated NAF over an evaluated relation.
- Existing Fact Overlay and premise filtering can construct meaningful
  observational contrasts without adding a public API.

## 5. Proposed shape

Create one standalone runner under `tools/spikes/` and one direct test that
loads it. The runner creates ephemeral in-memory Stores, uses existing
projector/evaluator/Fact Overlay/premise-filter paths, returns canonical
cell-level observations, and self-verifies them. Its README is the only new
documentation surface.

## 6. Boundaries and invariants

- `src/factgraph/**`, public exports, DTOs, SDK/API docs, and existing tests
  outside the new direct test remain unchanged.
- The tool cannot emit a public `MISSING`, `MASKED`, `NEGATED`, or `UNKNOWN`
  status. It may use those words only in explanatory prose as **unmapped**.
- `RemoveFact` and premise filtering must be reported as distinct mechanisms
  even when native bindings coincide.
- No standalone preflight is required: this is additive tool/test code with no
  public or cross-module protocol change. If that stops being true, stop and
  create the required preflight instead.

## 7. Acceptance

- [ ] O1–O7 run via existing native components and match Q17's observed matrix.
- [ ] A direct test and the runner's `--verify` route agree.
- [ ] No production source or public contract changes occur.
- [ ] README and closeout state that D09 remains open.

## 8. Implementation plan

1. Add a reproducible native fixture runner plus its concise boundary README.
2. Add a direct test that loads the runner and freezes all seven observations.
3. Run focused and application/SDK regressions, inspect scope, then fill the
   observed-only outcome and archive this blueprint pair.

## 9. Docs to update

- `tools/spikes/d09_native_absence_closure/README.md`
- This blueprint and its paired audit only. No public docs entry is created.

## 10. Outcome / deviations

- Final result: `observed-only`. The runner uses current Store, schema
  projector, correlated native evaluator, premise-filter wrapper and Fact
  Overlay routes to confirm O1–O7 exactly as frozen by Q17.
- Verification: runner `--verify`; direct probe test; application/SDK suite
  `590 passed, 172 subtests`; tool/test Ruff; tool/test mypy; and diff check
  all passed.
- Scope proof: no file under `src/factgraph/**`, no public export, DTO, SDK/API
  documentation, Query/Scenario, Explain, replay, Meander, or adapter was
  changed by this blueprint.
- Important conclusion: O2, O3 and O5 can all result in a native match, but
  their mechanisms remain separately asserted and do not imply equivalent
  factual, authorization, provenance, `MISSING`, `MASKED`, `NEGATED`,
  `UNKNOWN`, or closed-world semantics.
- Deviation: none. A standalone preflight was deliberately not created because
  this remained a non-public additive tool/test task; the paired audit records
  that condition.
- Next boundary: D09 remains open. Any public `WITHOUT_FIELD`, closure scope,
  source/premise algebra, explicit negative predicate, Explain state, or
  cross-engine design requires a new decision and blueprint.
