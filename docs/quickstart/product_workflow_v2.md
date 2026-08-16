# Complete Product V2 workflow

This is the recommended quickstart for new FactGraph product code. It uses only
the public `factgraph.sdk` authoring/runtime surface and keeps logical assets,
run-local facts, execution semantics, structured results and evidence claims
separate.

For a fully executed notebook with real outputs, see
[`examples/09_product_scenario_execution_v2.ipynb`](../../examples/09_product_scenario_execution_v2.ipynb).

## 1. Connect a Database, declare a schema and seed facts

```python
from pathlib import Path

from factgraph.sdk import (
    AssetMeta,
    Database,
    Entity,
    EntityRef,
    FactGraph,
    Field,
    Identity,
    compile_schema_from_classes,
    outcome_from_run_v2,
    vars,
)


class Person(Entity):
    person_id: str = Identity()
    age: int = Field()
    tags: list[str] = Field()


workspace = Path("data/people-factgraph")

# The SDK-owned connection creates the durable Database and owns its lock.
with FactGraph.create(path=workspace, schema_classes=[Person]) as seed_fg:
    alice_e_ref = seed_fg.entities.create(Person, person_id="alice")
    seed_fg.fields.set(Person.age, alice_e_ref, 30)
    seed_fg.fields.add(Person.tags, alice_e_ref, "baseline")

# Reopen the same durable workspace. The classes must match its schema digest.
fg = FactGraph.load_workspace(workspace, schema_classes=[Person])
alice_e_ref = fg.entities.ref(Person, person_id="alice")
assert fg.fields.get(Person.age, alice_e_ref) == 30

# Query entity-identity binding is explicit and typed.
alice = EntityRef("Person", {"person_id": "alice"})
```

`FactGraph.create(path=...)` and `FactGraph.load_workspace(...)` own the open
`Database`; close `fg` (or use a context manager) to release its exclusive
writer lock. Omitting `path=` is the explicit in-memory form.

When the application already owns the connection, attach instead:

```python
schema_ir = compile_schema_from_classes([Person])
with Database.create("data/caller-owned", schema_ir=schema_ir) as db:
    attached = FactGraph.attach(db, schema_classes=[Person])
    ref = attached.entities.create(Person, person_id="caller-owned")
    attached.close()   # closes only the facade
    head = db.head()   # db remains owned and usable by this context
```

`FactGraph.attach(db, ...)` validates the same schema contract but never takes
ownership of `db`. A view attachment is read-only. These three lifecycles are
connection/ownership choices only; Product Rule, Policy, Query, Scenario,
Result and replay contracts remain the same.

`Identity()` and `Field()` infer their shape from annotations. Do not use the
old `primary_key=` or `cardinality=` constructor keywords. Single `T` fields
are scalar; `list[T]` / `set[T]` / `tuple[T, ...]` fields are multi-valued.

## 2. Build a Product Rule

`build_rule(...)` is the direct form; `rule_builder(...).build(...)` is the
equivalent staged form. Neither call registers a Rule by id. The returned
`ProductRuleV1` already contains the resolved schema/semantic-port contract.

```python
with vars("person", "age") as (person, age):
    person_values = fg.build_rule(
        id="person_values",
        version="1",
        meta=AssetMeta(
            name="Person values",
            description="Expose one person's current age",
            tags=("people", "query"),
        ),
        when=(Person(person), Person(person).age == age),
        ports={"person": person, "age": age},
        semantic_ports={"person": Person, "age": Person.age},
    )
```

`semantic_ports` uses public schema descriptors: an Entity class denotes its
identity endpoint and a bound Field denotes a scalar field endpoint. The Rule
body remains logical; it does not contain Product Functions or engine config.

## 3. Build a Product Function

A Product Function is a peer asset of Rule. The first profile is pure,
deterministic, synchronous, total, has one or more scalar inputs and exactly
one scalar output:

```python
def age_decade(age: int) -> int:
    return age // 10


age_decade_function = fg.build_function(
    id="age_decade",
    version="1",
    meta=AssetMeta(name="Age decade", tags=("computed",)),
    implementation=age_decade,
)

# Equivalent staged form:
# age_decade_function = (
#     fg.function_builder("age_decade", version="1", meta=...)
#       .build(age_decade)
# )
```

Python annotations infer `string`, `int`, `float64` and `bool`. Explicit
`inputs={...}` / `output=...` declarations also accept canonical `time` and
`uuid` domains.

This is not arbitrary tool registration. Function cannot be called by Rule,
cannot call Rule or another Function, and cannot represent an Action/MCP/network
tool. Its Python implementation is trusted in-process code rather than a
sandbox.

## 4. Compose Rule and Function in a Product Policy

`PolicyBuilder.use(...).as_(...)` declares local occurrences. It does not
register global names. Function inputs are Policy-owned directional edges from
direct scalar ports of one Rule occurrence:

```python
ranked = fg.policy_builder(
    "people_by_decade",
    version="1",
    meta=AssetMeta(name="People by decade"),
)
people = ranked.use(person_values).as_("people")
decade = ranked.use(age_decade_function).as_("decade")
decade.inputs(age=people.age)

ranked_people = ranked.build(
    ranked.all(
        people,
        decade,
        people.age >= 18,
        decade.result >= 3,
    )
)
```

Function output is directional: use it in Policy comparisons or Query
`select`, never in Query `bind`. Multiple independent Function occurrences may
read the same Rule occurrence. Function-to-Function chaining, field-navigation
inputs and multiple source occurrences are intentionally rejected in this
first slice.

For deterministic alternatives, use explicit nested `ranked.all(...)` and
`ranked.any(...)`. Do not use Python `and` / `or`, chained comparisons, or
implicit entity `==`; symbolic handles fail loudly in Python boolean contexts.

## 5. Build a typed Query and choose execution

```python
profile = fg.execution.portable_deterministic(
    target=ranked_people,
    name="people-by-decade-portable-v2",
).build()

query = (
    fg.query(ranked_people)
      .bind(people.person, alice)
      .select("age", people.age)
      .select("decade", decade.result)
)
```

The Product V2 deterministic profiles are:

| Builder | Contract |
| --- | --- |
| `fg.execution.native_deterministic(target=...)` | Native-only deterministic execution |
| `fg.execution.portable_deterministic(target=...)` | Native + real Soufflé + real ProbLog; all must succeed with the same normalized selected rows |

Portable parity is result-row parity only. It does not claim that three
engines produce identical proofs or internal traces.

## 6. Add a run-local Scenario

Scenario uses write-like `set` / `add` / `set_exact` / `without` methods but
never writes the ledger:

```python
scenario = (
    fg.scenario()
      .set(
          Person.age,
          alice_e_ref,
          35,
          premise_id="reviewed-age",
          meta={
              "source": {
                  "ref": "operator:case-42",
                  "locator": {"kind": "opaque", "opaque_ref": "review-form"},
                  "origin_role": "scenario_hypothesis",
              },
              "note": "What if Alice's reviewed age is 35?",
          },
      )
      .build()
)

raw_run = query.plan(profile=profile, scenario=scenario).run()
```

Scenario metadata has separate lanes:

- `raw_kind` + `bound` changes evaluator-visible fact semantics;
- `source` / `sources` becomes safe opaque provenance references;
- `note` / `labels` is display/audit annotation; and
- FactGraph adds run-local origin/witness metadata itself. Callers cannot claim
  ledger authority for a synthetic premise.

Rule/Policy change is not a Scenario operation. Author an independent candidate
target and pin it with
`profile_builder.for_target(candidate, side="candidate")`.

## 7. Consume Result and structured Explain data

The raw `EvaluationRunV2` is the sealed replay carrier. Open the user-facing
facade explicitly:

```python
outcome = outcome_from_run_v2(raw_run)
baseline = outcome.baseline
effective = outcome.effective

row = effective.rows[0]              # the caller explicitly chooses a row
explanation = outcome.explain(row)    # no implicit first-row Explain

# Canonical business/API projection.
explain_wire = explanation.to_dict()
canonical_bytes = explanation.to_canonical_bytes()
projection_digest = explanation.content_digest

assert explain_wire["$schema"] == "factgraph.product_explanation"
assert explain_wire["schema_version"] == 2
assert explain_wire["source_protocol"] == "evaluation_run_v2"

# Dispatch the source protocol before reading protocol-specific sections.
if explain_wire["source_protocol"] == "evaluation_run_v1":
    protocol_section = explain_wire["execution"]
elif explain_wire["source_protocol"] == "evaluation_run_v2":
    protocol_section = explain_wire["profile"]
else:
    raise ValueError("unsupported Product Explain source protocol")
assert isinstance(protocol_section, dict)

# Availability is data. A null graph is never interpreted on its own.
evidence = explain_wire["evidence"]
graph_bearing_states = {
    "native_detached_recomputed",
    "portable_native_inner_not_parity",
    "problog_trace_captured",
}
if evidence["state"] in graph_bearing_states:
    graph = evidence["graph"]
    assert graph is not None
else:
    assert evidence["graph"] is None
    print(evidence["reason_code"])

print(explanation.render_text())      # display-only prose

function_view = explanation.functions.occurrences[0]
alice_call = next(
    call for call in function_view.calls
    if call.inputs[0].value == 35
)
assert alice_call.output.value == 3
assert function_view.callable_capture == "not_captured"
```

Structured Result/Explain contains sealed identities, selected observations,
Scenario facts and provenance lanes, execution/profile state, assets,
`WeightedChoice` topology when present, and Product Function definition/call
materializations. `to_dict()` returns a detached JSON-safe projection;
`to_canonical_bytes()` is its deterministic compact UTF-8 JSON encoding.
`content_digest` is SHA-256 over exactly those bytes. It is useful for
read-model equality and caching, but is not a run seal, signature, source
attestation or authorization grant. Business code should parse the structured
projection, not `render_text()` or `narrate()`.

Function materializes the complete upstream Rule occurrence relation before
the final Query binding/filter. Its call inventory can therefore contain calls
unrelated to the selected row; match calls by typed inputs/output instead of
ordinal position.

Current Product V2 Function/ProbLog Explain does not fabricate an
`EvidenceGraph`. When no graph was captured, `explanation.evidence.graph` is
`None` with a typed unavailable reason. The only graph-bearing states are
`native_detached_recomputed`, `portable_native_inner_not_parity`, and
`problog_trace_captured`; always inspect `evidence.state` and
`evidence.reason_code`, and do not treat `graph is None` as a failed logical
conclusion or negative proof. This is different from a sealed V1 Native
detached Explain path that can expose a sanitized graph.

The focused executable companion
[`examples/10_structured_explanation_contract.ipynb`](../../examples/10_structured_explanation_contract.ipynb)
shows both availability branches and verifies the canonical bytes/digest
relationship. The complete workflow notebook remains
[`examples/09_product_scenario_execution_v2.ipynb`](../../examples/09_product_scenario_execution_v2.ipynb).

## 8. Detached replay

```python
report = outcome.replay()
assert report.status == "matched"
```

Replay consumes only the sealed program/profile/world/materialization payload.
It does not read the live ledger, invoke a provider, resolve a current asset or
call the Python Function again. `matched` is deterministic replay of that
capture, not artifact authentication or proof that external data was true.

## 9. Probabilistic Scenario facts

Probability is an explicit non-portable profile, not an option on
`all(...)`, `any(...)`, Rule or Function:

```python
probability_policy = fg.policy_builder("probabilistic_age", version="1")
subject = probability_policy.use(person_values).as_("subject")
probability_target = probability_policy.build(probability_policy.all(subject))

probability_scenario = (
    fg.scenario()
      .set(
          Person.age,
          alice_e_ref,
          35,
          premise_id="probabilistic-age",
          meta={
              "raw_kind": "probabilistic",
              "bound": [0.8, 0.8],
              "source": {
                  "ref": "model:risk-v3",
                  "locator": {"kind": "opaque", "opaque_ref": "prediction-7"},
                  "origin_role": "imported_record",
              },
          },
      )
      .build()
)

probability_profile = (
    fg.execution.problog(target=probability_target, name="risk-v3")
      .fact_semantics(identity_probability=True)
      .for_occurrence(subject, fg.problog.occurrence_semantics())
      .build()
)

probability_run = (
    fg.query(probability_target)
      .bind(subject.person, alice)
      .select("age", subject.age)
      .plan(profile=probability_profile, scenario=probability_scenario)
      .run()
)
probability_outcome = outcome_from_run_v2(probability_run)
```

ProbLog is currently the only V2 engine that executes point-probability facts.
Native and Soufflé appear as typed `unsupported` frames; there is no fallback.
The result/explanation exposes both the submitted canonical decimal and the
sealed `problog_float64_v1` projection used by the adapter. A declared `p=0`
is explicitly captured as `omitted_zero` and produces no row.

## 10. Explicit `WeightedChoice`

`any(...)` is logical OR and never accepts weights. An exclusive categorical
choice is authored explicitly:

```python
choice_policy = fg.policy_builder("source_choice", version="1")
key = choice_policy.use(person_values).as_("key")
declared = choice_policy.use(person_values).as_("declared")
inferred = choice_policy.use(person_values).as_("inferred")

source_choice = choice_policy.weighted_choice(
    id="source",
    on=(key.person,),
    choices=(
        choice_policy.choice(
            "declared", probability="0.7", when=choice_policy.all(declared)
        ),
        choice_policy.choice(
            "inferred", probability="0.3", when=choice_policy.all(inferred)
        ),
    ),
)
choice_target = choice_policy.build(choice_policy.all(key, source_choice))

choice_profile = (
    fg.execution.problog(target=choice_target, name="exclusive-source-v1")
      .fact_semantics(identity_probability=True)
      .for_choice(source_choice, fg.problog.choice_semantics())
      .build()
)
```

Weights are canonical decimal strings and sum exactly to `"1"`. This lowers
to one ProbLog annotated disjunction; it is not independent branch probability.
The first slice supports one `WeightedChoice` per Policy and does not combine
it with Product Function topology.

## 11. Compatibility and safety boundaries

- `fg.eval.evaluate(..., config=ProbLogConfig(...))` is the legacy V0 engine
  configuration path; it is not a V2 profile.
- Provider remains a typed finite relation input attached to a Rule/Policy
  Query. It is not a Product Function and cannot be a bare Query target.
- Scenario changes extensional effective facts, not Rule/Policy assets.
- Product Functions are trusted in-process Python. FactGraph detects a
  persistent source-graph mutation but cannot undo external side effects.
- `EvidenceGraph`, provenance reference and source authority are separate:
  a structured Function call or Scenario premise is not automatically an
  external authoritative source or a proof.
- Product V2 integrity digests detect inconsistent mutation/splicing; they are
  not signatures or remote-runtime attestation.

## 12. Continue reading

- [Rules](rules.md) for the Rule/RuleExpr and Product authoring details.
- [Engines and configs](engines_and_configs.md) for V2 profiles and legacy
  engine config separation.
- [Evaluation and evidence](evaluate_and_evidence.md) for the V2/legacy result
  and Explain contracts.
- [Load and save](load_and_save.md) for durable workspace ownership.
