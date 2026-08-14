# Product Scenario and execution-profile construction (V2)

- Applicable scope: `factgraph.sdk`
- Status: additive V2 construction surface; V0/V1 compatibility is unchanged

## Purpose

V2 separates a run-local Scenario's engine-visible fact semantics from its
non-engine provenance and display annotations.  It also represents execution
semantics as an immutable profile rather than a generic engine-options dict.
The SDK entry points construct strict values, then the V2 Query terminal
captures/resolves/runs them against one sealed world.

```python
from factgraph.sdk import EntityRef

alice_e_ref = fg.entities.ref(Person, person_id="alice")  # managed e_ref for Scenario fields
alice = EntityRef("Person", {"person_id": "alice"})  # typed EntityRef for Query binds

scenario = (
    fg.scenario()
      .set(
          Person.risk_flag,
          alice_e_ref,
          True,
          meta={
              "raw_kind": "probabilistic",
              "bound": [0.8, 0.8],
              "source": {
                  "ref": "operator:case-42",
                  "locator": {"kind": "line_span", "line_start": 10, "line_end": 10},
                  "origin_role": "operator_input",
              },
              "note": "run-local hypothesis",
          },
      )
      .build()
)
```

`fg.scenario()` never writes to the ledger. Its normal field-input spelling is
a managed `e_ref` string (from `fg.entities.ref(...)` or
`fg.entities.create(...)`), as `alice_e_ref` above. This is distinct from a
typed `EntityRef`, which is the normal value for `fg.query(...).bind(...)`.
For interop the Scenario builder also accepts an `EntityRef` or a snapshot
exposing `.ref`; it validates the entity type and preserves a supplied
`EntityRef` (including one without an `encoded_ref`) rather than resolving it
through the managed ledger. It does not turn either spelling into a source
record. It offers:

- `set(Field, entity, value, *, meta=None, premise_id=None)` for a
  single-value field;
- `add(Field, entity, value, *, meta=None, premise_id=None)` for a multi-value
  field;
- `set_exact(Field, entity, values, *, member_meta=None, premise_id=None)` for
  the complete member set of a multi-value field; and
- `without(Field, entity, value=_UNSET, *, meta=None, premise_id=None)` to
  mask a field or, with `value=`, one multi-value member.

`set_exact` takes one `member_meta` entry per input value.  This prevents an
ambiguous probability or provenance annotation from being copied onto a
different member after canonical ordering.  There is no generic `origin_refs`
escape hatch on this product surface.

A Scenario only describes run-local fact operations: `set`, `add`,
`set_exact`, and `without`. It cannot add, remove, or patch a Rule or Policy;
author a separate immutable target when logical comparison is required.

The captured `outcome.effective.scenario.world.facts` collection is the
effective fact world, not a source-ledger `Field` getter: it distinguishes
baseline support from Scenario-synthetic facts. To inspect how a Scenario
changed that world, use `world.operation_evidence`: its metadata bindings
retain each premise and provenance, while `synthetic_witness_ids` and
`masked_witness_ids` identify the materialized overlay and replaced support.

## Strict Scenario metadata

Only these keys are accepted in `meta=`: `raw_kind`, `bound`, `source`,
`sources`, `note`, and `labels`.

- The only engine-visible fact semantic is
  `raw_kind="probabilistic", bound=[p, p]`, where `p` is a finite canonical
  point decimal in `[0, 1]`.  This is the declared V2 fact semantic; it does
  not by itself claim that every engine evaluates arbitrary-precision Decimal.
- `source` is shorthand for one closed `ProvenanceRefV1`; it can be either a
  `ProvenanceRefV1` object or exactly the closed wire shape shown above.
  Bare strings, arbitrary nested source dictionaries, `confidence`, raw source
  text, authority, and ACL data are rejected.
- `note` and `labels` are presentation/evidence data, not engine semantics.
- `without(...)` accepts provenance/display metadata but rejects fact
  semantics: a mask is not a new probabilistic fact.

The currently supported ProbLog adapter explicitly crosses a float64 boundary.
For every successful ProbLog V2 frame, the sealed
`probability_materialization` capture records each declared decimal, its exact
float64 hex representation, its shortest float64/ProbLog text, and whether it
was emitted.  `EvaluationRunV2ResultView.probability_materialization` and
`EvaluationRunV2ExplanationDataV2.probability_materialization` expose that
same structured capture.  A row's `point_probability` is therefore an engine
observation, not an implicit assertion that it equals the submitted Decimal.
A declared `0` remains in the sealed Scenario world but is explicitly marked
`omitted_zero` and omitted from the generated ProbLog EDB, so it produces no
effective observation.

For advanced callers, `ProvenanceLocatorV1` and `ProvenanceRefV1` are exported
from `factgraph.sdk`.  They are neutral opaque references, not a SourceRecord
or permission system.

## V2 execution profiles

Profiles are explicit, detached and target-scoped.  A Policy occurrence or
choice handle alone does not identify its final Policy digest, so `target=` is
required when a builder starts:

```python
profile = (
    fg.execution.problog(target=ranked_policy, name="risk-v1")
      .fact_semantics(identity_probability=True)
      .for_occurrence(older, fg.problog.occurrence_semantics())
      .for_rule(eligible_rule, fg.problog.rule_semantics())
      .for_choice(source_choice, fg.problog.choice_semantics())
      .build()
)
```

`target` must be the exact `ProductRuleV1` or `ProductPolicyV1` built by the
product authoring API.  The profile records a `target_pins` inventory even
when it has no attachments, then each attachment refers to one of those pins.
An occurrence must belong to the selected policy; a rule attached to a policy
must occur in that policy; and a choice must be one of that policy's authored
`WeightedChoice` topologies.  The profile has no target registry or lowered
branch-name input.

A Rule-level attachment and an occurrence-level attachment for that same Rule
in the same Policy target side are rejected.  They would otherwise create two
semantic owners for one compiler lowering slot.
The complete tutorial intentionally combines an occurrence attachment for
`person_values` with a Rule-level attachment for a *different*
`direct_person_values` Rule; it never uses both attachment kinds for one Rule.

For a deterministic primary/candidate comparison, pin the independently
authored candidate explicitly. The candidate must preserve the primary
Query's typed bind/select shape; it is not a mutable patch of the primary
Policy:

```python
comparison_profile = (
    fg.execution.native_deterministic(target=primary_policy)
      .for_target(candidate_policy, side="candidate")
      .build()
)

run = (
    fg.query(primary_policy)
      .bind(older.person, alice)  # `alice` is an EntityRef
      .select("age", older.age)
      .plan(
          scenario=deterministic_scenario,  # built with managed `alice_e_ref`
          profile=comparison_profile,
          candidate=candidate_policy,
      )
      .run()
)
```

The sealed run exposes named `baseline`, `effective`, and
`candidate_effective` ResultViews through `outcome_from_run_v2(run)`. The
primary and candidate effective views retain separate target/side captures,
while their captured semantic world can be the same Scenario world.

Use `fg.execution.native_deterministic(target=...)` for deterministic V2.
It builds immediately after `.build()` and rejects probability attachments.
Use `fg.execution.problog(target=...)` for the declared-point ProbLog model; it
requires an explicit `.fact_semantics(identity_probability=True)` before
`.build()`.  Both factories accept only named resource/capture bounds and
engine/adapter version pins.  They do not accept arbitrary `engine_options`
or a generic configuration dictionary.

`fg.problog.rule_semantics()`, `occurrence_semantics()`, and
`choice_semantics()` return the closed V2 attachment markers.  In particular,
`choice_semantics()` accepts no probability override: arm weights stay in the
authored `WeightedChoice` topology.

The initial ProbLog V2 profile pins Native and Soufflé environments as part of
the declared matrix, but does not claim they execute point-probability logic.
A V2 run represents their current state explicitly rather than falling back to
deterministic truth.

## V2 Query terminal

Pass the detached profile to the normal Query builder.  The original product
Rule/Policy wrapper is retained until the invocation seals its asset and
authoring binding; callers do not re-register a target by name.

```python
raw_run = (
    fg.query(ranked_policy)
      .bind(older.person, alice)  # typed EntityRef for Query binding
      .select("person", older.person)
      .plan(scenario=scenario, profile=profile)
      .run()
)
```

`scenario` is optional for V2: `.plan(profile=profile)` selects an explicit
empty/no-overlay V2 world.  This supports a deterministic V2 baseline or a
WeightedChoice-only ProbLog query without silently falling back to V1.  A V2
Scenario always requires a V2 profile; V1 Scenario/profile values, providers,
V0/V1 expectations, and V1 evidence scopes are rejected on this terminal.

## Product outcome facade

`.run()` intentionally continues to return the raw, sealed `EvaluationRunV2`:
it is the durable replay carrier and existing low-level integrations can retain
it unchanged.  Product/UI/Agent code can open the thin read facade explicitly:

```python
from factgraph.sdk import outcome_from_run_v2

outcome = outcome_from_run_v2(raw_run)
baseline = outcome.baseline
effective = outcome.effective
candidate = outcome.candidate_effective  # `None` when no candidate was planned

# The caller deliberately names a row; there is no first-row convenience.
explain_data = outcome.explain(effective.rows[0])
# Passing effective.rows[0].to_explain_target() is equivalent.

replay_report = outcome.replay()
```

`ProductEvaluationOutcomeV2.from_run(raw_run)` is the equivalent classmethod.
The facade retains `.run` as the exact original sealed carrier. Its named side
properties expose `EvaluationRunV2ResultView` values, including sealed row
identity/observation digests and point-probability observations when present.
For ProbLog, the view also exposes the explicit `problog_float64_v1`
materialization capture rather than disguising the engine's float conversion.
It has no
implicit truth value, `close()` method, ordinal Explain target, or synthesized
negative proof. `outcome.explain(...)` accepts only a caller-selected V2 row
view or its explicit target; ProbLog Explain stays data-first and reports an
unavailable EvidenceGraph rather than manufacturing one.

## Compatibility boundary

`fg.eval.evaluate(...)`, legacy `ProbLogConfig`, V0 Scenario calls, and V1
GoalPlan profiles remain separate compatibility surfaces.  Passing a V2
Scenario/profile to a V1 terminal is rejected rather than silently lowering
metadata or probability semantics.  V2 profile construction does not execute
an engine by itself.

## Runnable end-to-end tutorial

[`examples/09_product_scenario_execution_v2.ipynb`](../../../../examples/09_product_scenario_execution_v2.ipynb)
exercises the complete product flow against the real SDK/runtime: direct and
staged product Rule/Policy builders, `AssetMeta`, typed comparisons,
deterministic Scenario CRUD, an independently authored candidate Policy
comparison over one shared Scenario world, Native and ProbLog profiles,
`WeightedChoice`, sealed V2 Result/Explain views, declared-decimal →
`problog_float64_v1` materialization (including explicit `p=0` omission), and
detached replay. It also asserts the explicit current boundaries: Native and
Soufflé have `unsupported` V2 probability frames and a V2 EvidenceGraph is
reported unavailable when it was not captured rather than reconstructed.
