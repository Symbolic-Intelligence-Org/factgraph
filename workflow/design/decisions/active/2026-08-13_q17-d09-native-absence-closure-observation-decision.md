# Q17 Decision: D09 native absence/closure observation protocol

- Status: adopted
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Authority: the user's 2026-08-13 authorization for project-level continuous
  FactGraph delivery, limited to a disposable observation protocol. This is not
  authority to adopt public absence, closure, premise, or Explain semantics.
- Inputs:
  - [Archived Query/Scenario program](../../../blueprints/archive/2026-08-13_factgraph-query-scenario-program.md)
  - [Q16 query-scoped EffectiveSnapshot v1](./2026-08-13_q16-query-effective-snapshot-v1-decision.md)
  - Current native evaluator, premise filter, and Fact Overlay runtime.
- Outputs / Downstream:
  - [D09 native absence/closure observation blueprint](../../../blueprints/active/2026-08-13_factgraph-d09-native-absence-closure-observation.md)
- Related:
  - Candidate design discussion: [premise-effective-view-and-scenario-resolution.zh.md](../../design-points/active/premise-effective-view-and-scenario-resolution.zh.md)
  - Candidate unified-design discussion: [meander-factgraph-unified-design-review-candidate.zh.md](../../design-points/active/meander-factgraph-unified-design-review-candidate.zh.md)
- Branch: `codex/v0.3.0-factgraph-whatif-v1-continuous-2026-08-13`
- Depends on: Q7, Q11, Q15, Q16.

> Q17 adopts only a reproducible, native-observation protocol. It does not
> adopt D09's production operation, admissibility, closure, authorization,
> error, Scenario, Query, or Explain semantics. D09 remains open.

## 1. Scope

Freeze one disposable native-only fixture matrix around the existing correlated
negation-as-failure (NAF) behavior:

```text
Person:exists(person) AND NOT person:age(person, value)
```

The probe observes the relation visible to the existing evaluator. It records
what happens when that relation is present, empty, partially removed, premise
filtered, supplemented by an ordinary `not_age` predicate, or value-replaced.

## 2. Non-scope

- No `WITHOUT_*`, `absent`, closure-scope, generic premise/claim, source
  authority, Scenario operation, DTO, SDK/API, Meander, Agent, or export.
- No changes to `src/factgraph/**`, existing Query/Scenario contracts,
  EvidenceGraph, Explain, replay, or the archived P1/P2 program.
- No claim that native NAF is closed-world truth, an explicit negative fact,
  a source-authority decision, or cross-engine behavior.

## 3. Decision

### 3.1 Observation cells

The probe must run the following current-engine observations using real Store,
projector, native evaluator, premise filter, and Fact Overlay code:

| Cell | Fixture/operation | Required observed outcome |
| --- | --- | --- |
| O1 | `age=35` is present in the base relation | NAF does not match |
| O2 | no `age` row is present | NAF matches |
| O3 | one visible `age` row is removed by existing `RemoveFact` | overlay before fails; after matches |
| O4 | two multi-value rows exist and only one is removed | overlay remains failed |
| O5 | an `age` row is hidden by the existing premise filter | unfiltered NAF does not match; filtered NAF matches |
| O6 | `age=35` and ordinary `not_age=True` both exist | NAF remains blocked; positive `not_age` query matches |
| O7 | `age=35` is value-replaced with `age=22` | overlay remains failed |

O3 and O5 may produce the same native binding as O2. That equality is an
observation of the current evaluated relation, **not** an equivalence of
provenance, authorization, missingness, masking, or world state.

### 3.2 Interpretation boundary

The only permitted conclusion is: the current native evaluator retains an
outer binding when the correlated nested body has no match in the evaluated
relation. It has no public state that distinguishes `MISSING`, `MASKED`,
`NEGATED`, `UNKNOWN`, or a closed-world absence assertion.

### 3.3 Stop rule

Any need for a public operation, source change, cross-engine statement, or
stateful Explain claim stops this work package. A future D09 decision must
first define closure ownership, effective-view state/provenance, explicit
negative predicates and conflicts, source admission order, disclosure, and
the support matrix.

## 4. Rejected alternatives

### Option A: promote `RemoveFact` to `WITHOUT_FIELD`

- **Why rejected**: `RemoveFact` targets one existing assertion id. O4 proves
  that it is not field-level absence, and it has no closure or provenance
  contract.

### Option B: treat a premise-filtered fact as physically absent

- **Why rejected**: the filter controls admissibility of an evaluated view;
  it does not decide factual truth, source authority, or a public masking
  state.

### Option C: infer a negative fact from a predicate called `not_age`

- **Why rejected**: names do not create signed-predicate semantics. The
  predicate is ordinary positive data unless a future decision defines more.

## 5. Supporting evidence

- Native `NotAtom` retains an outer environment only when its nested body has
  no match: `src/factgraph/core/rules/where_eval.py` (`_eval_not_atom` and
  `_exists_not_body`).
- The validator requires a correlated outer binding for `not`:
  `src/factgraph/core/rules/where_ast_validate.py` (`_validate_not_dataflow`).
- A premise exclusion makes an assertion unavailable both as a support and as
  a negation blocker: `src/factgraph/core/store/premise_filter.py` module
  contract and `premise_scoped_ledger`.
- Existing `RemoveFact` skips one projected assertion-id row:
  `src/factgraph/application/fact_overlay_runtime.py`
  (`_apply_fact_overlay_projection`).
- The archived program explicitly reserves absence/closure for a new decision:
  [program §2 P3](../../../blueprints/archive/2026-08-13_factgraph-query-scenario-program.md#2-work-packages).
- Q16 explicitly excludes absence, closure, delete/mask, and generic premise
  semantics: [Q16 §3](./2026-08-13_q16-query-effective-snapshot-v1-decision.md#3-non-scope).

## 6. Consequences

### 6.1 Downstream unblocking

This closes only the question of what the current native runtime visibly does.
It provides fixtures for a future D09 decision; it does not unblock public
absence semantics.

### 6.2 Required follow-up actions

The blueprint must keep the fixture runner non-public, preserve the seven
cells, and report `observed-only`, `inconclusive`, or `contradicted` without
turning any result into a public capability claim.

## 7. Acceptance criteria

- [x] All seven cells execute against existing native components without mocks.
- [x] The runner and its test make no change under `src/factgraph/**`.
- [x] Output explicitly distinguishes an observed empty relation from a
  semantic absence/negative-fact conclusion.
- [x] D09 remains explicitly open after the probe closes.

## 8. Decision record

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | adopted | Observation protocol frozen | The user's continuous-delivery authority permits a disposable diagnostic, not an absence/closure product decision. |
| 2026-08-13 | implemented | Observation protocol executed | O1–O7 are frozen in a non-public runner and direct test. The result is observed-only; it does not adopt a public absence or closure contract. |
