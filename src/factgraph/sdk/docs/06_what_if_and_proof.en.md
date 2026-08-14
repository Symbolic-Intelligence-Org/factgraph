# Evidence, Replay, And Captured ScenarioRun

## V1 Scenario / GoalPlan path

The V0 paths below remain compatibility contracts. The current general
FactGraph What-if surface is the separately versioned terminal
`fg.query(...).what_if(ScenarioSpecV1).plan(...).run()` path documented in
[`03_rules_and_inferences.en.md`](03_rules_and_inferences.en.md). It returns
`GoalPlanRunV1`, whose durable `EvaluationRunV1` captures both baseline and
effective worlds.

```python
outcome = (
    fg.query(resolved_rule)
      .bind(person_address, alice)
      .select("age", age_address)
      .what_if(scenario_spec)
      .plan()
      .run()
)

assert isinstance(outcome, GoalPlanRunV1)
scenario_diff = outcome.scenario_diff       # captured-only; no re-evaluation
replay = outcome.replay()                   # no Store/provider callback
explanation = outcome.explain(explicit_target)
```

`ScenarioSpecV1` supports the finite Q18 algebra: scalar set, member
ensure/exact-set/removal, constrained extensional relation changes, ephemeral
entity creation/removal, and the SDK/debug exact assertion removal form. It
is always resolved against one admitted input relation before execution;
`EvidenceScopeV1` remains a separate admission filter, not a deletion or
absence statement. `ScenarioWithout*` only creates exact local closure for its
resolved target. It is neither a ledger mutation nor a global negative fact.

`scenario_diff` reports sealed input/world pins, operation references and
normalized selected-row differences. It deliberately labels evidence and
causality `not_claimed`; use an explicit row Explain for a positive observed
conclusion, and never interpret a zero-row summary as proof of negation.

The portable V1 profile can replay a captured positive deterministic world in
native, Soufflé and ProbLog. It compares selected-row sets only, records
per-engine succeeded/failed/unsupported frames, and never falls back to native
when an external adapter cannot execute the contract.

T5 removed the public candidate-universe and `what_if.*` evidence shells from
the SDK user path. The supported evidence workflow is:

```python
result = fg.eval.evaluate(inference)
row = result.first()
assert row is not None

explanation = row.explain()
closed_head = row.close()
manual = fg.eval.explain(inference, head=closed_head)
```

- `EvaluateResult` is the public evaluation envelope.
- `EvaluateRow` carries bindings, row-owned conclusion/evidence digests, and
  raw quantitative carriers.
- `row.explain()` returns an `Explanation`; read `explanation.repr` for
  deterministic multi-line text when a rendered summary is needed.
- `row.close()` returns a closed application `Rule` for manual replay.
- `fg.eval.explain(expr, head=closed_head)` replays a closed-head explanation.

Persisted-fact inspection remains under `fg.audit.*`.

## Captured Query observation

For a native resolved Query that has `expect_contains(...)` observations, use
the terminal `.capture()` form when those observations must travel with the
detached evidence record:

```python
captured = (
    fg.query(resolved_rule)
      .select("age", SemanticPortAddress("target", "age"))
      .expect_contains("alice_age", age=22)
      .capture()
)
captured.verify()
captured.explain(row_capture_digest=captured.bundle.rows[0].row_capture_digest)
```

This returns `CapturedEvaluationQueryRunV0`, not `EvaluateResult`. It wraps an
unmodified F4 bundle and seals the original targeted Query wrapper plus ordered
compiled observation inventory/outcomes. It is detached and caller-custodied,
but not authenticated, historical replay, source validation or a negative
proof: a `not_satisfied` observation has no EvidenceGraph. The old
`eval.evaluate(targeted_query, capture="run_bundle_v0")` rejection remains
intentional; use `.capture()` for this one bounded combination.

## Captured replacement-only ScenarioRun

`fg.what_if.*` remains removed. The existing Q7/Q11
`evaluate(..., scenario=...)` compatibility route remains supported but
non-captured. The one supported **captured/detached** What-if-shaped API is the
terminal native Query form for the same bounded scalar replacement grammar:

```python
run = (
    fg.query(resolved_rule)
      .bind(SemanticPortAddress("target", "person"), alice)
      .select("age", SemanticPortAddress("target", "age"))
      .what_if(ScenarioFieldSubstitutionV0(
          EntityRef("Person", {"employee_id": "alice"}),
          FieldPath("Person", "age"),
          35,
          "review-age",
      ))
      .run()
)

run.diff()
run.verify()
run.explain(side="effective", row_capture_digest=run.effective.rows[0].row_capture_digest)
```

This returns `ScenarioRunV0`, not `EvaluateResult`. It retains sealed,
caller-custodied baseline/effective captures and offers detached diff,
verification, and authored-Policy evidence projection without reading the
live Store after capture. Effective synthetic witnesses are marked
`scenario_hypothesis`, never ordinary ledger witnesses. The record is
digest-sealed but not authenticated, a historical replay, or proof that a
caller-declared premise is true. General premises, source authority,
add/delete/mask, temporal overlays, actions, operators, and generic Scenario
plans remain outside this API.

Internally, admission first resolves a `QueryEffectiveSnapshotV1`: an identity
for the exact Query-dependency relation before either side is evaluated. It
deliberately excludes the result diff and is not a global ledger/history
snapshot, a source-authority claim, or an additional public What-if API.
Existing `ScenarioRunV0` capture and Q7/Q11 compatibility values retain their
previous result-aware identities and witness labels.
