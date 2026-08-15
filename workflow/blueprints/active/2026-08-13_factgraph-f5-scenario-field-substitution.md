# Task Blueprint: FactGraph F5A Scenario field substitution

- Status: implemented
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Branch: `codex/v0.3.0-f5-scenario-v0-2026-08-13`
- Related Modules:
  - `src/factgraph/application/protocol/`
  - `src/factgraph/application/derivation_runtime.py`
  - `src/factgraph/core/store/_evaluate.py`
  - `src/factgraph/sdk/store.py`
- Related Docs:
  - [`Q7 Scenario field substitution`](../../design/decisions/active/2026-08-13_q7-scenario-field-substitution-v0-decision.md)
  - [`Q6B bundle capture`](../../design/decisions/active/2026-08-12_q6b-evaluation-run-bundle-capture-decision.md)
- Audit Log:
  - [`2026-08-13_factgraph-f5-scenario-field-substitution.audit.md`](./2026-08-13_factgraph-f5-scenario-field-substitution.audit.md)

## 1. Problem

FactGraph has a Policy-backed typed Query and one native execution path, but
has no safe way to ask a direct, bounded hypothetical without mutating the
ledger or allowing existing live Explain to misrepresent a hypothetical value
as an asserted fact.

## 2. Goals

- Add the Q7 replacement-only Scenario DTO and resolution/result-diff values.
- Execute baseline and effective Query relations through the same private
  materialized native evaluator path.
- Preserve ledger, support-sidecar and candidate-index state; fail closed on
  unsupported shapes and view changes.
- Leave Scenario Explain/capture/replay and all broader premise algebra out.

## 3. Non-goals

- General What-if, world synthesis, Policy/rule mutation, multi-premise
  composition, field-navigation syntax, temporal/as-of/versioned or historical
  fact semantics, SourceRecord, Meander/UI/Agent work. An ordinary scalar
  `time` field value is not temporal history and remains in this v0 shape.
- Changing normal Query/F4 anchor/bundle/Explain behavior.

## 4. Proposed shape

`ScenarioFieldSubstitutionV0` is accepted only as `scenario=` on
`fg.eval.evaluate(compiled_query, ...)`.  A resolver captures the exact
dependency relation once, replaces one existing visible scalar field in an
immutable copy with a synthetic hypothesis witness, then invokes the existing
native evaluation plumbing twice (baseline/effective).  The public effective
`EvaluateResult` carries only a typed Scenario summary/diff and explicitly
disables live evidence/capture capabilities.

## 5. Boundaries and invariants

- One direct entity/field/value premise; no list ordering or conflict algebra.
- Native/config-none/empty premise filters only; no registry or external
  Operator path.
- Base relation and effective relation are copied/frozen, dependency-complete
  and never written to the ledger.
- A synthetic hypothesis id is an execution witness, not an asserted source.
- No capture or Explain until a separately-designed virtual-premise evidence
  contract exists.

## 6. Acceptance

- [x] Q7 acceptance criteria are covered by focused tests.
- [x] The normal Query and F4 suites remain green.
- [x] Module docs distinguish field substitution from full Scenario/What-if.
- [x] No non-goal public surface appears in source/export checks.

## 7. Implementation plan

1. Add protocol/runtime resolution DTOs and a private effective-relation
   execution seam.
2. Wire the narrow `scenario=` keyword through compiled Query evaluation.
3. Add adversarial and regression tests, then update application/protocol docs.
4. Run the focused and integrated suites; request one final combined F4/F5
   independent review before lifecycle closure.

## 8. Outcome / deviations

Implemented as the deliberately narrow `ScenarioFieldSubstitutionV0` contract.
The effective relation is in-memory only, uses the same materialized native
Query evaluator as its baseline, and cannot create a Run anchor, bundle,
ledger-backed Explain/close result, support-sidecar record or candidate-support
index entry.  The final three-way independent review found and verified fixes
for three pre-closure P1s: silent non-Query `scenario=` consumption,
Scenario/result splice integrity, and a private effective-relation seam that
could otherwise retain support provenance.

Verification recorded at closure: focused Scenario/protocol/runtime tests
`73 passed, 29 subtests`; application/SDK cohort `518 passed, 159 subtests`;
the cohort plus the effective-relation runtime test file `527 passed, 159
subtests`; targeted Ruff and `git diff --check` passed.  The broad repository
collection remains unavailable because of pre-existing `service.static_ui`
and `third_party/kg-gen` collection faults outside this slice; neither surface
changed here.  General Scenario algebra, overlays, persistence, replay,
evidence, UI and Meander/Agent integration remain explicitly deferred.
