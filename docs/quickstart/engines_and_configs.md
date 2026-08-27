# Engines and configs

Rule/Policy declare *what*; execution semantics say *how to compute*. New
Product V2 code uses target-pinned `fg.execution.*` profile builders. The
older `engine=` / `config=` parameters, `ProbLogConfig`, `PyReasonConfig` and
canonical `SemanticsProfile` remain the legacy `fg.eval.evaluate(...)` path.
These generations are both documented here because their values are not
interchangeable.

The config fields are not arbitrary knobs; each one maps to a real feature of the underlying engine (ProbLog Annotated Disjunctions, PyReason temporal interval annotations, etc.). This chapter spells the mapping out so you can choose values from a position of understanding, not guessing.

## Product V2 execution profiles (recommended)

Every V2 profile is immutable, target-scoped and fully captured for replay:

```python
native = fg.execution.native_deterministic(target=policy).build()
portable = fg.execution.portable_deterministic(target=policy).build()

problog = (
    fg.execution.problog(target=probability_policy, name="risk-v1")
      .fact_semantics(identity_probability=True)
      .for_occurrence(subject, fg.problog.occurrence_semantics())
      .build()
)
```

| V2 profile | Engine frames | Supported semantics |
| --- | --- | --- |
| `native_deterministic_v2` | Native | deterministic Product Rule/Policy/Function |
| `portable_deterministic_v2` | Native, Soufflé, ProbLog | shared positive deterministic subset; all three selected-row sets must match |
| `problog_point_v2` | ProbLog succeeded; Native/Soufflé typed unsupported | point-probability Scenario facts and explicit `WeightedChoice` |

`target=` is the exact Product Rule/Policy, not a registry id. A deterministic
candidate is pinned explicitly with
`.for_target(candidate, side="candidate")`. ProbLog attachments use authored
assets/handles rather than generated branch strings:

- `.for_rule(rule, fg.problog.rule_semantics())`;
- `.for_occurrence(handle, fg.problog.occurrence_semantics())`; and
- `.for_choice(choice, fg.problog.choice_semantics())`.

A Rule-level and occurrence-level attachment may not overlap the same lowering
slot. Choice weights live only in authored `WeightedChoice` arms;
`choice_semantics()` cannot override them. Product Function has deterministic
semantics and no engine-parameter attachment: it is pre-materialized once per
side and all selected engines consume that same relation.

Scenario point probability uses the write-like SDK form:

```python
scenario = (
    fg.scenario()
      .set(
          User.age,
          alice,
          25,
          meta={"raw_kind": "probabilistic", "bound": [0.8, 0.8]},
      )
      .build()
)
```

This metadata is sealed into the V2 effective world. The current ProbLog
boundary exposes its declared Decimal → float64 projection explicitly in
Result/Explain. Native/portable deterministic profiles reject probabilistic
facts rather than dropping the semantics.

V2 profiles accept closed resource/capture fields and version pins, not
arbitrary `engine_options` or generic config dictionaries. A profile change
means a new Run; Explain always describes the profile captured by that Run.

The rest of this chapter describes the legacy `fg.eval.evaluate` configuration
surface.

## 1. Four engines — one-paragraph triangle

```
                                consumes
              ┌─────────────────  SemanticsProfile  ───────────────┐
              │                                                    │
              ▼                                                    ▼
       ┌────────────┐                                       ┌────────────┐
       │  problog   │                                       │  pyreason  │
       │            │                                       │            │
       │ point-prob │                                       │ interval + │
       │ + AD       │                                       │ temporal   │
       └────────────┘                                       └────────────┘

       ┌────────────┐                                       ┌────────────┐
       │   native   │                                       │  souffle   │
       │  (default) │                                       │            │
       │ deterministic                                       │ high-perf  │
       │ SLD        │                                       │ Datalog    │
       └────────────┘                                       └────────────┘
        (no semantics consumption)                  (no semantics consumption)
```

| Engine | What it does | Consumes `SemanticsProfile`? |
|---|---|---|
| `native` *(default)* | Deterministic SLD resolution over the application Rule body. The shipped baseline; no probability, no time. | No |
| `problog` | Probabilistic logic programming (KU Leuven ProbLog). Bodies become Annotated Disjunctions; facts carry point probabilities. Returns weighted derivations. | Yes |
| `pyreason` | Temporal annotated logic with interval bounds (RPI PyReason). Rules carry per-rule timestep delay and per-atom `[lower, upper]` interval annotations. | Yes |
| `souffle` | High-performance Datalog evaluation. Currently a registered engine name; no `SemanticsProfile` lowering. | No |

`fg.eval.evaluate(...)` takes the engine via:

```python
engine: Literal["native", "problog", "pyreason", "souffle"] = "native"
```

`native` and `souffle` do not consume `SemanticsProfile` or any SDK config wrapper. `problog` and `pyreason` do.

**`engine=` and `config=` reconciliation** — three call shapes are accepted:

| Call shape | Behavior |
|---|---|
| only `config=ProbLogConfig(...)` | engine inferred from the wrapper's `.engine` property |
| only `engine="problog"` | runs with the engine's internal defaults (`config=None`) |
| both (`engine=...` + `config=...`) | must agree; mismatch raises `engine='X' does not match semantics.engine='Y'` |

Passing `config=` with `engine="native"` or `"souffle"` raises `engine='<name>' does not consume SemanticsProfile`. Legacy kwargs `semantics_profile=` / `mode=` / `policy=` / `view=` / `temporal_view=` / `engine_options=` are explicitly rejected at the SDK boundary with redirect messages pointing at the new surface.

## 2. Shared meta substrate that configs project

`ProbLogConfig` and `PyReasonConfig` differ in their engine-specific fields, but they share one load-bearing surface: **what they project**. Both configs reach into the ledger and read the assertion-level meta keys an author wrote at `fg.fields.set(...)` time. Those meta keys are the language by which author intent (uncertainty, time) reaches the engine — the configs only decide *how* to project them.

| Meta key | Author writes at | Config that projects it | Engine consumes as |
|---|---|---|---|
| `raw_kind` + `bound` | every write, paired | both configs' `uncertainty_projection` | ProbLog: point probability `0.7::fact.`<br>PyReason: interval `fact : [lo, hi]` |
| `valid_from` / `valid_to` | every write, optional | (PyReason only) `temporal_projection.valid_time_boundaries` / `fact_boundaries` (same substrate, two spellings) | PyReason timestep enumeration |

The deeper design intent: **author intent stays orthogonal to engine choice**. An assertion carries `meta={"raw_kind": "probabilistic", "bound": [0.7, 0.7]}` regardless of which engine will eventually evaluate over it. Switching from ProbLog to PyReason does not require re-writing the ledger; it requires choosing a different `config=` that projects the same meta into the new engine's native form.

### 2.1 `raw_kind` + `bound` — uncertainty carrier

Recap of the write-time form (see [`data_model.md`](data_model.md) §2.2):

```python
fg.fields.set(
    User.age, alice, 25,
    meta={"raw_kind": "probabilistic", "bound": [0.7, 0.7]},
)
```

- `raw_kind` ∈ `{"probabilistic", "possibilistic"}`
- `bound` is `[lower, upper]` with `0 <= lower <= upper <= 1`
- They must be provided together; the ledger rejects half-pairs

**The two `raw_kind` values are different mathematical objects, not different scales of the same thing.** Choosing one over the other changes how `bound` is interpreted, which engines can consume it, and what the projection policies mean.

| `raw_kind` | Theory | `bound = [lower, upper]` means | Use when |
|---|---|---|---|
| `"probabilistic"` | Kolmogorov probability | A confidence interval *around* a probability. The fact's actual probability `p ∈ [lower, upper]`; both endpoints are still probability values that obey the standard axioms (P(A∪B) = P(A) + P(B) − P(A∩B), etc.) | Source is itself a probability — a Bayesian posterior, an empirical frequency, a model's calibrated output |
| `"possibilistic"` | Dubois–Prade possibility theory | A `[necessity, possibility]` pair. `lower = N(fact)` is the *necessary* truth degree (everything below this is definitely true), `upper = Π(fact)` is the *possible* truth degree (everything above this is definitely false). N and Π are dual measures: `N(A) = 1 − Π(¬A)`. They are **not** probabilities and do not have to sum to 1 over a partition. | Source is partial knowledge, linguistic / fuzzy information, or expressing ignorance (e.g. `bound=[0, 1]` is "I don't know"; `bound=[1, 1]` is "definitely true"; `bound=[0, 0]` is "definitely false") |

This is why §3.3's `_interval` policies are split into `probability_interval` and `possibility_interval` — the same `[0.3, 0.7]` bound means different things under the two theories, and the engine has to know which. An author writing `raw_kind="possibilistic"` cannot accidentally reach ProbLog's probabilistic surface, because ProbLog has no possibility semantics.

Why a projection is necessary, not optional:

- **ProbLog** is a point-probability engine — facts in its native form look like `0.7::fact.`. A degenerate interval `bound=[0.7, 0.7]` maps naturally to `0.7`; a wider interval `bound=[0.5, 0.9]` has no canonical point representation (lower? upper? midpoint?). Possibility-theoretic assertions (`raw_kind="possibilistic"`) cannot be reinterpreted as probabilistic at all without changing the mathematical object.
- **PyReason** is interval-native — facts in its native form look like `fact : [0.5, 0.9]`. Probability and possibility intervals can both pass through structurally, but the engine still needs to know *which kind* it is dealing with.

The 7-policy enum (`reject` / `lower` / `midpoint` / `upper` / `identity_probability` / `probability_interval` / `possibility_interval`) is shared across both configs — it is the substrate-level grammar for "how do you turn an `(raw_kind, bound)` pair into engine-native form". Each engine validates which policies it can actually realise (ProbLog rejects the two `*_interval` policies; PyReason accepts everything). The per-engine details are in §3.3 (ProbLog) and §4.9 (PyReason).

### 2.2 `valid_from` / `valid_to` — business-time interval

Author writes ISO-8601 markers on the meta to assert *when this fact is valid in business time*:

```python
fg.fields.add(
    User.role, alice, "admin",
    meta={
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_to":   "2026-06-30T23:59:59Z",
    },
)
```

The same keys are consumed in two places:

- **Read-side time-travel**: `snap.field("role").at("2026-03-15T...")` filters assertions by their business-time interval (see [`three_layer_api.md`](three_layer_api.md))
- **PyReason `temporal_projection.valid_time_boundaries` / `fact_boundaries` modes** (§4.8): both modes treat every assertion's business-time interval as a fragment of the timeline that PyReason's timestep enumeration discretises. `fact_boundaries` is the canonical spelling per the adapter docs; `valid_time_boundaries` is the input alias kept for legacy profiles. They share one code path.

A ProbLog evaluation ignores these keys entirely — there is no time dimension in ProbLog's semantics. Writing `valid_from` / `valid_to` is safe regardless of which engine you later choose; only the temporal modes of `PyReasonConfig` read them.

## 3. `ProbLogConfig` — probabilistic semantics wrapper

`ProbLogConfig` is the SDK ergonomic wrapper for ProbLog. Five fields, each mapping either to a ProbLog (Sato distribution semantics / De Raedt PLP) feature or to the shared meta substrate (§2).

### 3.1 Minimal example

```python
from factgraph.sdk import ProbLogConfig

cfg = ProbLogConfig(
    case_probabilities={"seed_path": 0.7, "hint_path": 0.3},
    uncertainty_projection={
        "probabilistic": {"policy": "midpoint"},
        "possibilistic": {"policy": "reject"},
        "fallback": "reject_unconfigured",
    },
    name="my_problog_profile",
)

assert cfg.engine == "problog"   # the wrapper exposes the engine binding
```

`fg.eval.evaluate(rule_or_expr, head=..., config=cfg)` will derive `engine="problog"` from the wrapper (you do not have to pass `engine=` separately).

### 3.2 `case_probabilities` — branch-level Annotated Disjunctions

ProbLog's Annotated Disjunction (AD) form lets one rule head be derived through several alternative bodies, each carrying a probability:

```prolog
0.7::user_tag(U, T) :- user_tag_seed(U, T).
0.3::user_tag(U, T) :- user_tag_hint(U, T).
```

In FactGraph's adapter (`src/factgraph/adapters/problog/problog_export.py:119`), the rule export emits one such annotated clause **per OR branch**:

```
<probability>::rule_body_<idx>(...) :- <compiled body>.
```

`case_probabilities: dict[branch_id, float]` supplies those probabilities. **`branch_id` is the id of an OR branch, not a Rule id.** Where the branch ids come from depends on what you pass to `evaluate(...)`:

| Input | Where `branch_id` comes from |
|---|---|
| Single application `Rule` from `build_application_rule(...)` | **Not applicable** — application Rule is AND-only, has no branches. Passing non-empty `case_probabilities` raises `"single application Rule inputs only accept empty case_probabilities"` |
| `RuleExpr` with `\|` / `RuleExpr.any(...)` operators | The lowering plan's `branch_id` for each OR child (introspectable via `fg.rules.inspect(rule_expr)`) |
| Legacy `Inference` with `Case([...], id="seed_path")` | The `Case.id` you wrote — or the fallback `c0` / `c1` / ... when no id was given |

Values must be finite floats in `(0, 1]`; zero is rejected (a 0-probability branch never derives anything). Default `{}` makes every branch implicit `1.0` — the rule degenerates to deterministic OR.

Unknown `branch_id` raises `unknown branch id <id> for ProbLogConfig.case_probabilities`, so a typo will surface immediately rather than silently fall through.

### 3.3 `uncertainty_projection` + `fallback` — projecting `raw_kind`+`bound` to point probability

§2.1 introduced the substrate. The ProbLog half is which of the 7 policies actually export, plus what to do for assertions that have no `raw_kind` at all:

```python
{
    "probabilistic": {"policy": "midpoint"},
    "possibilistic": {"policy": "reject"},
    "fallback": "reject_unconfigured",
}
```

| Policy | ProbLog behavior |
|---|---|
| `"reject"` | Raise at export. **Default for both `probabilistic` and `possibilistic`** — author must opt in to any projection |
| `"lower"` / `"midpoint"` / `"upper"` | Emit `bound[0]` / `(bound[0]+bound[1])/2` / `bound[1]` |
| `"identity_probability"` | Emit `bound[0]` — only if `raw_kind="probabilistic"` AND `bound[0]==bound[1]`; raises otherwise |
| `"probability_interval"` / `"possibility_interval"` | ✗ rejected at export — ProbLog cannot emit intervals or possibility semantics |

`fallback` (also accessible as `ProbLogConfig.fallback`) handles assertions with no `raw_kind` at all (deterministic facts): `"reject_unconfigured"` (default — raise), `"warn_default"` (warn + project to `1.0`), or `"use_default"` (silently project to `1.0`).

Both defaults are strict on purpose. Silently coercing an interval to a point or a missing `raw_kind` to `1.0` are the kinds of invisible semantic conversion that produce silent bugs; the strict defaults force the question to surface.

### 3.4 `rule_params` and `name`

`rule_params: dict[rule_id, dict]` is a per-rule metadata slot lowered into `SemanticsProfile.rule_projection["problog"]` — forward-compatible for upcoming per-rule ProbLog options; empty by default. `name: str | None` is a diagnostic label surfaced in `fg.eval.preview_config(...)`.

## 4. `PyReasonConfig` — temporal-interval semantics wrapper

PyReason (Aditya Mor et al., RPI) is annotated temporal logic. Every atom and every head can carry a `[lower, upper]` interval, and every rule can carry a timestep delay. `PyReasonConfig` exposes those primitives through eleven fields.

### 4.1 Minimal example

```python
from factgraph.sdk import PyReasonConfig

cfg = PyReasonConfig(
    timestep_delay=2,
    iteration_count=5,
    derived_bound=(0.8, 1.0),
    atom_bounds={"adult_in_us:atom_1": (0.7, 1.0)},  # <rule_id>:atom_<idx>
    case_bounds={"seed_path": (0.9, 1.0), "hint_path": (0.5, 0.9)},
    name="my_pyreason_profile",
)

assert cfg.engine == "pyreason"
```

### 4.2 What PyReason rules look like

To understand each field, look at the actual PyReason rule string the adapter emits ([`src/factgraph/adapters/pyreason/where_compile.py:110`](../../src/factgraph/adapters/pyreason/where_compile.py)):

```
derived_user_tag(U, T) : [0.8, 1.0] <-2  user_tag_seed(U, T) : [0.7, 1.0]
└─────────── head ───────┘ ┌── lo,hi ──┘ ┌  ┌──── body atom ─────┐ ┌── lo,hi ─┐
                           head bound    delay                     body atom bound
```

Each PyReasonConfig field maps to one of these annotations.

### 4.3 `timestep_delay` — the `<-N` operator

`timestep_delay: int >= 0` is the **N** in PyReason's `head <-N body` form. It says: *when the body matches at time `t`, derive the head at time `t + N`*. This is how PyReason expresses temporal precedence — a delay of `0` is "as soon as the body matches" (same timestep), `2` is "two ticks later", etc.

```
head(...) <-0 body(...)     # default: derive head in same timestep as body match
head(...) <-3 body(...)     # derive head 3 timesteps after body match
```

The default is `0`. Validation: must be non-negative `int`; `bool` rejected.

### 4.4 `iteration_count` — global simulation timesteps

`iteration_count: int >= 1` is the **total number of inference rounds** PyReason will run. PyReason is a fixpoint engine over time — each timestep propagates the rule set once. After `iteration_count` rounds, evaluation stops and the current bounds are reported as the answer.

| Value | Effect |
|---|---|
| `1` *(default)* | One round — equivalent to one-shot derivation |
| `N > 1` | N propagation rounds — needed for chained temporal rules where one rule's head feeds another rule's body |

`iteration_count` and any timestep count derived from `temporal_projection` (§4.8) must agree; passing both raises `Conflicting PyReason timesteps between SemanticsProfile.iteration_count and SemanticsProfile.temporal_projection.<mode>`.

### 4.5 Interval bounds — head / body atom / per-branch

PyReason's `: [lo, hi]` interval annotation can land at three positions in the emitted rule string. Four config fields supply them:

```
derived(...) : [head_lo, head_hi]  <-N  user:age(U, A) : [atom_lo, atom_hi], ...
         ▲                                          ▲
         head bound (derived_bound / head_bound)    body atom bound (atom_bounds)
         or per-branch override (case_bounds)
```

| Field | Lands at | Key shape | Notes |
|---|---|---|---|
| `derived_bound: tuple[float, float] \| None` | head `: [lo, hi]` (single, all branches) | no key | Canonical name. Default `None` — no annotation (head at PyReason's `[1, 1]`) |
| `head_bound: tuple[float, float] \| None` | head `: [lo, hi]` (single, all branches) | no key | Equivalent alias. **Mutually exclusive** with `derived_bound` — passing both raises `PyReasonConfig.derived_bound conflicts with PyReasonConfig.head_bound` |
| `atom_bounds: dict[atom_id, (lo, hi)]` | body atom `: [lo, hi]` | `<rule_id>:atom_<index>` | Position-based key — same predicate at different positions is constrained independently. SDK rejects keys not matching the format |
| `case_bounds: dict[branch_id, (lo, hi)]` | head `: [lo, hi]`, per OR branch | branch_id (same source as `case_probabilities`; see §3.2) | Overrides `derived_bound` / `head_bound` for that branch only. Use when different evidence paths carry different certainty |

All four require `0 <= lo <= hi <= 1`. Atoms / branches without an explicit bound are not annotated — PyReason treats them at the default `[1, 1]`.

Interpretation: in PyReason's annotated logic, the lower bound is the *necessary* degree of truth and the upper is the *possible* degree (the probability vs possibility distinction from §2.1 carries through to how `[lo, hi]` is read). `[1, 1]` = "definitely true", `[0, 0]` = "definitely false", `[0, 1]` = "unknown".

### 4.6 `temporal_projection` — discretising the timeline

`temporal_projection: dict` controls PyReason's timestep enumeration. The mode chooses *which timeline drives the discretisation* — pulling from the `valid_from`/`valid_to` substrate covered in §2.2:

| Mode | Drives discretisation by | Required fields |
|---|---|---|
| `{"mode": "none"}` *(default)* | nothing — `iteration_count` alone controls timesteps | — |
| `{"mode": "fixed_timesteps", "timesteps": N}` | explicit positive `int` | `timesteps` |
| `{"mode": "fact_boundaries", "universe": [start, end]}` | author-written `valid_from` / `valid_to` (§2.2). Canonical spelling | ISO `universe` |
| `{"mode": "valid_time_boundaries", "universe": [start, end]}` | same substrate as `fact_boundaries` — kept as legacy input alias; same code path | ISO `universe` |
| `{"mode": "time_binned", "universe": [start, end], "bin_size": ...}` | wall-clock bins; `bin_size` accepts `1d` / `1h` / `15m` / `1m` | `universe` + `bin_size` |

Both `fact_boundaries` and `valid_time_boundaries` are valid-time-driven; the adapter handles them in one branch and preserves whichever spelling you wrote. `time_binned` is for *uniform wall-clock discretisation* independent of any assertion's validity interval. All three modes clip assertions outside their `universe`.

Validation pathing surfaces in error messages as `SemanticsProfile.temporal_projection.<mode>.<field>` so you can trace which projection rule rejected your config.

### 4.7 `uncertainty_projection`, `rule_params`, `name`, `fallback`

- **`uncertainty_projection`** — same substrate as ProbLog's (§2.1, §3.3): projects `raw_kind`+`bound` into engine-native form. The full 7-policy enum:

  | Policy | PyReason behavior |
  |---|---|
  | `"reject"` | Raise if any assertion carries this `raw_kind` |
  | `"lower"` / `"midpoint"` / `"upper"` | Collapse the interval to a point at the chosen position |
  | `"identity_probability"` | Pass `bound[0]` through (only if `raw_kind="probabilistic"` and bound is degenerate) |
  | `"probability_interval"` | Pass the interval through unchanged — PyReason's most natural mode for `raw_kind="probabilistic"` |
  | `"possibility_interval"` | Pass the interval through as a possibility-theoretic interval — PyReason's natural mode for `raw_kind="possibilistic"` |

  PyReason accepts all 7 because its native form is intervals. The point-collapse policies are still legal — sometimes you want to project away the interval width even on an interval engine.
- **`rule_params: dict[rule_id, dict]`** — same role as on ProbLog: per-rule metadata, lowered into `SemanticsProfile.rule_projection["pyreason"]`. Forward-compatible slot.
- **`name` / `fallback`** — same shape and semantics as on ProbLog (§3.3 / §3.4).

## 5. `SemanticsProfile` — the canonical DTO (advanced)

`SemanticsProfile` is the application-protocol canonical form that both SDK wrappers ultimately lower into. You can use it directly:

```python
from factgraph.sdk import SemanticsProfile

profile = SemanticsProfile(
    name="my_profile",
    engine="problog",
    uncertainty_projection={...},
    rule_projection={"problog": [...]},
)
```

### 5.1 When to use `SemanticsProfile` directly vs the SDK wrappers

| Use case | Surface |
|---|---|
| Authoring a profile from Python code | `ProbLogConfig` / `PyReasonConfig` (ergonomic, named fields) |
| Loading a profile from JSON / cross-tool exchange | `SemanticsProfile` (canonical, serialisable) |
| Constructing engine-specific options not exposed by the wrapper (`engine_options` escape hatch) | `SemanticsProfile` |
| Multi-engine pipeline that shares profile fragments | `SemanticsProfile` |

### 5.2 Field layout

```text
SemanticsProfile(
    name:                  str,             # required label
    engine:                str,             # "problog" | "pyreason"
    version:               str,             # protocol version (default supported)
    engine_options:        dict,            # raw passthrough to the adapter
    iteration_count:       int | None,
    uncertainty_projection: dict,
    temporal_projection:   dict,            # default {"mode": "none"}
    rule_projection:       dict[bucket, list[dict]],
    certainty_projection:  dict,
    output_readback:       dict,
    fallback:              str,             # default "reject_unconfigured"
)
```

`certainty_projection` is the slot reserved for Track 3 / B certainty migration (per `condition_weights` decomposition) — currently empty by default. `output_readback` is the slot for engine-specific output coercion rules. Neither is exercised by the current SDK wrappers; they exist for the canonical profile schema completeness.

### 5.3 Pattern parallel

This split (`SemanticsProfile` canonical / `ProbLogConfig` + `PyReasonConfig` ergonomic) is the same SDK-shadow / application-DTO pattern documented at [`docs/quickstart/rules.md`](rules.md) §2.6 for Rule vs the lower-level data shape. The SemanticsProfile naming is benign — application takes a neutral name, SDK takes the user-facing engine-specific names.

## 6. `fg.eval.preview_config(...)` — inspect-only

`preview_config` takes a `SemanticsProfile`, `ProbLogConfig`, or `PyReasonConfig` and returns a structural dict — what the canonical profile looks like, what engine it binds, and (for SDK wrappers) the lowered profile preview. It does not run any evaluation and does not touch the ledger.

```python
preview = fg.eval.preview_config(cfg)
# {
#   "name": ...,
#   "engine": "problog",
#   "uncertainty_projection": {...},
#   "rule_projection": {...},
#   "semantics_type": "ProbLogConfig",        # only for SDK wrappers
#   "lowered_profile": {...},                  # canonical preview
#   ...
# }
```

Use it to verify your config lowers to what you expect before running a long evaluation.

## 7. → evaluation (next chapter)

The recommended Product V2 call is:

```python
run = fg.query(policy).select("value", handle.value).plan(
    profile=portable,
    scenario=scenario,
).run()
```

See [`product_workflow_v2.md`](product_workflow_v2.md) and
[`evaluate_and_evidence.md`](evaluate_and_evidence.md). The legacy call is:

```python
result = fg.eval.evaluate(rule_or_expr, head=<Rule>, engine=..., config=...)
```

Its `head=`, returned `EvaluateResult`, row iteration and legacy Explain are
documented in [`evaluate_and_evidence.md`](evaluate_and_evidence.md).

## 8. Reference

### 8.1 Types

```python
from factgraph.sdk import (
    # Product V2 builders are reached through fg.execution / fg.problog.
    ProbLogConfig,        # 5 fields, lowers to SemanticsProfile(engine="problog")
    PyReasonConfig,       # 11 fields, lowers to SemanticsProfile(engine="pyreason")
    SemanticsProfile,     # canonical DTO (factgraph.core.semantics.profile.SemanticsProfile)
)
```

### 8.2 Errors

| Error | Trigger |
|---|---|
| `evaluate(...): engine= must be one of: native, problog, pyreason, souffle` | `engine=` value not in the allowed set |
| `engine='<name>' does not consume SemanticsProfile` | `config=` passed with `engine="native"` / `engine="souffle"` |
| `engine='X' does not match semantics.engine='Y'` | Both `engine=` and `config=` passed with mismatched engine binding |
| `SemanticsProfile.engine='X' does not match engine='Y'` | Same condition, raw `SemanticsProfile` form |
| `PyReasonConfig.derived_bound conflicts with PyReasonConfig.head_bound` | Both alias fields set; pick one |
| `ProbLogConfig.<field> must be ...` / `PyReasonConfig.<field> must be ...` | Per-field validation; check the wrapper docstring |
| `Conflicting PyReason timesteps between SemanticsProfile.iteration_count and SemanticsProfile.temporal_projection.<mode>` | `iteration_count` and `temporal_projection.timesteps` disagree |
| `uncertainty_projection.<raw_kind>.policy=reject for asrt_id=...` | An assertion carries `raw_kind=X` and the projection policy is `"reject"` |
| `uncertainty_projection has no policy for raw_kind=...` | An assertion's `raw_kind` is not configured and `fallback="reject_unconfigured"` |
| `evaluate() does not accept semantics_profile= / mode= / policy= / view= / temporal_view= / engine_options=` | Legacy kwarg redirected to the new surface |

### 8.3 Related chapters

- [`rules.md`](rules.md) — declarations that `evaluate(...)` consumes
- [`product_workflow_v2.md`](product_workflow_v2.md) — current profile,
  Scenario, Product Function and replay path
- [`data_model.md`](data_model.md) §2.2 — the `raw_kind` / `bound` meta keys that `uncertainty_projection` projects
- [`evaluate_and_evidence.md`](evaluate_and_evidence.md) — Product V2 outcome
  plus legacy `fg.eval.evaluate(...)`, `EvaluateRow` and `Explanation`
- Adapter docs:
  - [`src/factgraph/adapters/problog/`](../../src/factgraph/adapters/problog/) — `rule_ext.py`, `problog_export.py`
  - [`src/factgraph/adapters/pyreason/`](../../src/factgraph/adapters/pyreason/) — `rule_ext.py`, `where_compile.py`, `engine_eval.py`

### 8.4 Engine reference

External references for the engine semantics this chapter describes:

- **ProbLog** — *De Raedt, Kimmig, Toivonen (2007).* "ProbLog: A Probabilistic Prolog and its Application in Link Discovery." KU Leuven; Annotated Disjunctions follow the Sato distribution semantics
- **PyReason** — *Mor, Aditya, Tartaglione, Brik, Shakarian (2023).* "PyReason: Software for Open World Temporal Logic." Annotated logic with `[lower, upper]` intervals plus rule timestep delays
- **Souffle** — *Jordan, Scholz, Subotić (2016).* "Soufflé: On Synthesis of Program Analyzers." CAV 2016. Compiled Datalog
- **Native** — FactGraph's deterministic SLD evaluator; no external reference
