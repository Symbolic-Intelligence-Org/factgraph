# Possibility-Probability Transmission Layer

- Status: working / non-authoritative
- Authority: Design-point research note for future blueprints and module docs. This is not current implementation truth.
- Source / Provenance:
  - User research note, 2026-05-11.
  - PyReason key concepts documentation: https://pyreason.readthedocs.io/en/latest/key_concepts.html
  - ProbLog documentation: https://problog.readthedocs.io/
  - ProbLog PyPI package page: https://pypi.org/project/problog/
  - Dubois, Prade, Sandri, "On Possibility/Probability Transformations": https://link.springer.com/chapter/10.1007/978-94-011-2014-2_10
- Related Current Docs:
  - `src/kernel/adapters/docs/02_problog_adapter.md`
  - `src/kernel/adapters/docs/03_pyreason_adapter.md`
  - `src/kernel/core/annotation/docs/README.md`
  - `src/kernel/core/docs/01_architecture.en.md`
- Related Blueprint:
  - `docs/blueprints/active/2026-05-11_uncertainty-transmission-layer.md`

## 1. Question

FactPy already has engine-specific uncertainty carriers:

- ProbLog consumes fact-level probability.
- PyReason consumes interval bounds over annotated atoms.
- Native / Souffle paths are mostly deterministic and may carry only compatibility confidence.

The design question is not "how do we convert fuzzy / possibility into probability by default?" The sharper question is:

> How do we preserve one source of raw uncertainty while allowing runtime engine adapters to project it into each engine's semantic input format?

The project-specific framing is:

> 形式统一不等于语义统一。

The report's terminology is useful as design input, but it should not be adopted wholesale. FactPy should adapt the idea to existing project boundaries: Annotation Store persistence, engine adapter projection, candidate confidence output, and module docs as current truth.

## 2. Current Source-Grounded Behavior

Current implementation has several partial lanes:

- `problog/semantic/probability`
  - Accepted ProbLog candidates persist probability as the engine-native semantic lane.
  - ProbLog export reads probability in order: `problog/semantic/probability`, `shared/semantic/probability`, then legacy `meta.confidence`.
- `pyreason/semantic/bound_lower` and `pyreason/semantic/bound_upper`
  - PyReason session writes engine-native bounds.
  - The same session derives `shared/derived/confidence` from the lower bound for compatibility.
- `shared/semantic/probability`
  - User-authored `meta={"probability": ...}` is projected into the Annotation Store.
- `meta.confidence`
  - Still exists as a compatibility projection, but it does not itself encode whether the number is probabilistic, possibilistic, or certainty-like.
- `valid_from` / `valid_to`
  - The SDK / write protocol already use these as business valid-time metadata.
- `active_from` / `active_to`
  - The PyReason adapter-local session uses these as integer engine timesteps.

This means the repository already avoids a completely naked scalar in some places, but it does not yet have a unified raw uncertainty contract or an explicit transmission policy surface.

Any implementation should build on these lanes instead of replacing them with a general uncertainty-theory framework.

## 3. Proposed Mental Model

```text
Stored data = raw_kind + bound + provenance
Runtime = SemanticsProfile / transmission policy
Engine input = dynamically generated view
```

The stored assertion should keep raw uncertainty semantics. Projection into engine-specific inputs should happen at runtime, inside or near engine adapters. A projection result should not be written back as the only source of truth, because that freezes one run's interpretation into durable data.

This is semantic-boundary preservation, not semantic flattening. A common carrier can make data easier to route, but it must not imply that a probabilistic interval, a possibilistic bound, a PyReason certainty bound, and an SMT hard constraint have the same meaning.

The cleaner project-specific split is:

```text
Data layer:
  raw_kind
  bound              # one logical field, likely AnnotationRow(kind="json")
  provenance
  valid_from / valid_to

Semantics layer:
  SemanticsProfile
  engine-specific parameters
  uncertainty transmission function
  temporal transmission function

Runtime:
  project source facts into engine-native view
  run engine
  map outputs back into project-level records
```

Under this split, new user-facing data should not need to say `probability`, `bound_lower`, or `bound_upper` just to satisfy a particular engine. Because the project is not online, those do not need to remain parallel public uncertainty write contracts. They should become runtime projection outputs or adapter-internal details.

Storage placement: canonical raw uncertainty should live in the Annotation Store, not in `meta_rows`. A practical first shape is:

```text
shared/semantic/raw_kind  kind=str   value=probabilistic | possibilistic
shared/semantic/bound     kind=json  value=[lower, upper]
```

SDK-facing APIs can accept values through `meta={...}` in Phase 1. Phase 1 should deliberately dual-write: `meta_rows` keep the values available for assertion selection / view ergonomics, while annotation rows carry the canonical semantic copy.

Phase 1 scope should stop at the data contract:

- accept and validate `raw_kind`;
- accept and validate `bound`;
- persist both to `meta_rows`;
- project both to `shared/semantic/*` annotation rows;
- prove `AssertionRecordSet.where(meta=...)` can use them;
- avoid changing ProbLog export, PyReason materialization, candidate confidence, or runtime projection behavior.
- update examples and docs so new uncertainty authoring uses `raw_kind` / `bound`, not `probability`, `bound_lower`, or `bound_upper`.

## 4. Minimal Raw Kinds

Start with two top-level kinds:

```text
probabilistic
possibilistic
```

`probabilistic` is for values with probability, frequency, calibrated statistical estimate, measured error model, or similar semantics.

`possibilistic` is for compatibility, physical allowance, expert uncertainty, necessity/possibility bounds, or other incomplete/imprecise knowledge semantics.

Do not add `DETERMINISTIC` as a third top-level raw kind in the first pass. Deterministic values can be represented as degenerate bounds:

```text
true        -> [1, 1]
false       -> [0, 0]
exact value -> [x, x]
```

## 5. Bound Rule

`bound` must not be treated as a naked interval. Its meaning is constrained by `raw_kind`.

Examples:

- `raw_kind=probabilistic`, `bound=[L, U]`
  - Probability interval, statistical interval, or calibrated probability range.
- `raw_kind=possibilistic`, `bound=[L, U]`
  - Necessity-possibility bound or possibility-compatible range.
- PyReason projection
  - Engine view may emit `[L, U]` as predicate certainty / truth-compatible bound.

The same numeric pair can have different semantics depending on `raw_kind`; the data contract must preserve that boundary.

## 6. Default Projection Direction

### PyReason

- `probabilistic`
  - Project `[p, p]` or `[L, U]` into PyReason bound only under an explicit `probability_as_certainty` heuristic label.
- `possibilistic`
  - Project `[L, U]` as a truth / certainty-compatible bound.

### ProbLog

- `probabilistic`, `[p, p]`
  - Directly emit `p::fact`.
- `probabilistic`, `[L, U]`
  - Require a configured strategy: `lower`, `midpoint`, `upper`, or calibrated projection.
- `possibilistic`
  - Reject by default. Require an explicit possibility-to-probability policy.

### SMT / hard-constraint engines

- `probabilistic`
  - Project as value interval, confidence interval, or explicit hard-threshold constraint, depending on policy.
- `possibilistic`
  - Project as support interval / allowed region.
- Degenerate deterministic
  - Project as exact hard constraint.

## 7. Candidate Built-In Policies

Possible built-ins:

- `conservative_lower`: `p = L`
- `midpoint`: `p = (L + U) / 2`
- `upper`: `p = U`
- `max_entropy` / `insufficient_reason`
- `calibrated_projection`
- `custom_user_policy`

Engineering default should be conservative:

1. Direct ProbLog projection only for probabilistic point bounds.
2. Interval probabilistic projection requires an explicit policy.
3. Possibilistic-to-probabilistic projection rejects unless explicitly configured.
4. `calibrated_projection` is the preferred serious engineering path when a calibrated model or validated conversion exists.

## 8. Minimal Data Contract Sketch

```json
{
  "id": "a1",
  "predicate": "risk",
  "subject": "asset_17",
  "raw_kind": "possibilistic",
  "bound": [0.35, 0.70],
  "source": "expert_or_rule",
  "metadata": {}
}
```

Runtime projection config:

```json
{
  "engine": "problog",
  "projection": "calibrated_projection_v1",
  "fallback": "reject_if_not_probabilistic"
}
```

Semantics profile sketch:

```json
{
  "name": "pyreason_possibilistic_valid_time_v1",
  "engine": "pyreason",
  "uncertainty_projection": {
    "possibilistic": "bound_as_certainty",
    "probabilistic": "probability_as_certainty",
    "fallback": "reject_unconfigured"
  },
  "temporal_projection": {
    "mode": "valid_time_boundaries",
    "input_interval": "valid_from_valid_to",
    "engine_interval": "active_from_active_to",
    "delay_semantics": "next_segment"
  },
  "engine_options": {
    "timesteps": "derived_from_timeline"
  }
}
```

## 8.1 PyReason Temporal Projection

PyReason's timestep model should stay inside the adapter. The stored facts should use business valid time (`valid_from` / `valid_to`), and the PyReason `SemanticsProfile` should derive integer timesteps at runtime.

Suggested projection:

1. Collect all relevant `valid_from` and `valid_to` boundaries from the facts used in the run, plus an explicit query horizon when needed.
2. Sort boundaries into `t0 < t1 < ... < tn`.
3. Treat timestep `i` as the half-open interval `[ti, t(i+1))`.
4. Mark a fact active for every segment covered by its business valid interval.
5. Emit PyReason `active_from` / `active_to` as integer timestep coordinates only in the generated engine view.
6. After inference, map derived facts at timestep `i` back to `[ti, t(i+1))`.

This makes irregular business-time changes natural: timesteps advance when the set of relevant valid-time facts can change. The tradeoff is that `timestep_delay=1` means "next segment", not "one day" or "one hour". If fixed wall-clock duration is needed, the profile should declare a different mode such as `fixed_duration_bucket`.

## 9. Documentation Action Items

If adopted, migrate the durable conclusions into:

- `src/kernel/core/docs/01_architecture.en.md`
  - Canonical raw uncertainty annotation carrier and boundaries.
- `src/kernel/adapters/docs/02_problog_adapter.md`
  - ProbLog projection policy and rejection defaults.
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
  - PyReason bound projection, compatibility labels, and valid-time to timestep projection.
- `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md`
  - User-facing authoring path for `raw_kind`, `bound`, provenance, and business valid-time.
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
  - Clarify `confidence` / `confidence_kind` remains an output summary, not the canonical raw uncertainty store.

## 10. Open Risks

- The existing `meta.confidence` fallback in ProbLog export can still silently treat a compatibility confidence as probability. A future blueprint should decide whether to gate, warn, or keep it as legacy behavior.
- `confidence_kind` currently allows `none|probability|certainty`; it is candidate-output-oriented and should not be overloaded as the stored raw uncertainty kind without a migration plan.
- A calibrated possibility-to-probability projection requires either domain-specific calibration artifacts or a policy registry. A named policy without calibration evidence is only a heuristic.
- SMT projection needs its own engine adapter contract; this note only sketches the direction.

## 11. Compressed Principle

数据层保存 raw uncertainty；transmission 层负责动态解释；推理引擎只消费 projection view。不要把某次 projection 的结果写回唯一真源。
