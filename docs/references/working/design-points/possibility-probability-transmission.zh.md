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

The same split also addresses scattered engine-specific rule parameters. Earlier designs considered attaching engine annotations directly to `Rule` / `Derivation` structure paths:

```python
Derivation(
    id="drv.popular",
    version="1.0.0",
    where=[Branch([User(u), Pred("user:active", u)])],
    head=User.popular(value="true"),
    annotations=[
        EngineAnnotation(
            engine="problog",
            target=Path.branch(0),
            kind="probability",
            value=0.9,
        ),
        EngineAnnotation(
            engine="pyreason",
            target=Path.body_atom(0, 1),
            kind="interval_threshold",
            value=(0.5, 1.0),
        ),
        EngineAnnotation(
            engine="pyreason",
            target=Path.head(0),
            kind="interval",
            value=(0.8, 0.9),
        ),
    ],
)
```

That shape correctly identifies the attachment problem, but it makes rule definitions heavy. The preferred direction is:

```text
Standard Rule Template:
  logical structure only

SemanticsProfile:
  path-targeted engine annotations and transmission functions
```

In other words, path-targeted annotations can exist as internal profile data, but the public rule definition should not carry ProbLog branch probability, PyReason body thresholds, PyReason head intervals, or timestep configuration.

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

Concrete Phase 1 write shape:

```python
fg.data.write(
    Risk.score,
    asset_ref,
    "risk_high",
    meta={
        "raw_kind": "possibilistic",
        "bound": [0.35, 0.70],
        "source": "expert_review",
        "valid_from": "2026-01-01T00:00:00Z",
    },
)
```

Expected persistence after Phase 1:

```text
meta_rows:
  raw_kind = "possibilistic"
  bound = [0.35, 0.70]
  source = "expert_review"
  valid_from = "2026-01-01T00:00:00Z"

annotation_rows:
  shared/source/source = "expert_review"
  shared/semantic/raw_kind = "possibilistic"
  shared/semantic/bound = [0.35, 0.70]
```

`meta_rows` are intentionally kept in the first slice because SDK assertion views already use them for `AssertionRecordSet.where(meta=...)`, `.at(...)`, `.version(...)`, and review / retract selection ergonomics. Annotation rows carry the semantic copy used by audit and future engine projection.

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

Phase 1 validation recommendation:

```text
raw_kind:
  required when bound is present
  str
  allowed values: probabilistic | possibilistic

bound:
  required when raw_kind is present
  JSON list, length = 2
  values are numeric and not bool
  0.0 <= lower <= upper <= 1.0
```

This makes `raw_kind` and `bound` a semantic pair. Allowing one without the other would reintroduce naked scores or untyped intervals.

Degenerate deterministic values should stay a value-level convention, not a third top-level raw kind in Phase 1:

```text
true-like      -> raw_kind=<chosen lane>, bound=[1, 1]
false-like     -> raw_kind=<chosen lane>, bound=[0, 0]
exact score x  -> raw_kind=<chosen lane>, bound=[x, x]
```

The lane still matters. `bound=[1, 1]` under `probabilistic` means probability-one under the chosen data source semantics; under `possibilistic` it means fully possible / compatible. Consumers must not infer a universal deterministic logic from the pair alone.

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
  "version": "1",
  "uncertainty_projection": {
    "possibilistic": {
      "policy": "bound_as_certainty"
    },
    "probabilistic": {
      "policy": "probability_as_certainty",
      "label": "heuristic"
    },
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

SemanticsProfile should be runtime/deployment configuration, not stored assertion data. Recommended fields:

```text
name
engine
version
engine_options
uncertainty_projection
temporal_projection
rule_projection
certainty_projection
output_readback
fallback
```

Field intent:

- `engine`: selected runtime adapter (`native`, `problog`, `pyreason`, etc.).
- `engine_options`: direct adapter options such as timeout or timesteps.
- `uncertainty_projection`: maps `raw_kind + bound` into engine-native input.
- `temporal_projection`: maps business valid time into engine-native time coordinates.
- `rule_projection`: optional adapter-specific rule-shape projections such as ProbLog branch weights or PyReason body/head intervals. This may use path-targeted entries internally, but must not become public `Branch(probability=...)` / `engine_ext=...` rule syntax.
- `certainty_projection`: future runtime configuration home for retained certainty/explain lanes such as `condition_weights`.
- `output_readback`: maps engine output back to candidate summaries, annotations, and business-time intervals.
- `fallback`: global reject / warn / default behavior for unconfigured cases.

Track 3 / B implementation note: the current code now contains
`kernel.core.semantics.SemanticsProfile` as a frozen core value object
with shape validation and `inspect_semantics_profile(...)`. This is
scaffolding only: SDK / service runtime calls reject `semantics=` and
`semantics_profile=`, and ProbLog / PyReason adapter consumption remains
deferred to Track 3 / C and D.

Important separation:

```text
Rule / Derivation:
  logical structure and materialization target

Data:
  raw_kind / bound / valid_from / valid_to

SemanticsProfile:
  how this run consumes raw data and rule structure for a selected engine
```

Possible path-targeted `rule_projection` sketch:

```json
{
  "rule_projection": {
    "problog": [
      {
        "target": "branch:0",
        "kind": "branch_weight",
        "value": 0.9
      }
    ],
    "pyreason": [
      {
        "target": "body_atom:0:1",
        "kind": "interval_threshold",
        "value": [0.5, 1.0]
      },
      {
        "target": "head:0",
        "kind": "interval",
        "value": [0.8, 0.9]
      }
    ]
  }
}
```

This keeps the structure-path idea available for engines that need it while preventing public business rules from accumulating engine-specific knobs.

Runtime heaviness risk:

`evaluate(...)` may become heavier if it must combine a view, raw uncertainty annotations, temporal projection, rule projection, and engine options every time. If this becomes material, introduce an inspection / preprocess step:

```python
projection = fg.rules.project(drv, profile=profile)
projection.inspect()
candidates = fg.rules.evaluate_projection(projection)
```

The first implementation should not add this API until profiling or user workflow pressure justifies it, but the design should avoid making projection results canonical stored facts.

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

Open temporal design details:

- A run horizon is required when the final segment would otherwise be open-ended.
- Missing `valid_from` should either be rejected for temporal projection or mapped through an explicit profile default. Silent defaulting would make replay ambiguous.
- `valid_to` should remain exclusive, matching current assertion view behavior.
- Multiple input facts covering the same timestep should keep their separate assertion identity; temporal projection should not merge facts before engine materialization.
- Readback should record enough profile metadata to explain why a derived fact is valid over a returned interval.

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
- `confidence_kind` currently allows `none|probability|certainty`; it is candidate-output-oriented and should not be overloaded as the stored raw uncertainty kind.
- A calibrated possibility-to-probability projection requires either domain-specific calibration artifacts or a policy registry. A named policy without calibration evidence is only a heuristic.
- SMT projection needs its own engine adapter contract; this note only sketches the direction.
- Phase 1 exact `where(meta={"bound": [...]})` filtering is useful for assertion selection but not enough for range queries. Range-aware uncertainty selection should be a separate design.

## 11. Compressed Principle

数据层保存 raw uncertainty；transmission 层负责动态解释；推理引擎只消费 projection view。不要把某次 projection 的结果写回唯一真源。
