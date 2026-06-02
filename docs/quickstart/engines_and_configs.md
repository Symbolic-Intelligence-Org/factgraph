# Engines and configs

Rule and RuleExpr declare *what* — engines and configs say *how to compute*. This chapter covers the `engine=` and `config=` parameters that `fg.eval.evaluate(...)` accepts, and the SDK wrappers (`ProbLogConfig`, `PyReasonConfig`) plus the canonical `SemanticsProfile`. It deliberately stops short of the actual `evaluate(...)` call shape, the `head=` parameter, and the returned `EvaluateRow` / `Explanation` rows — those live in `evaluation.md` and `evidence.md`.

The config fields are not arbitrary knobs; each one maps to a real feature of the underlying engine (ProbLog Annotated Disjunctions, PyReason temporal interval annotations, etc.). This chapter spells the mapping out so you can choose values from a position of understanding, not guessing.

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

## 2. `engine=` parameter

```python
engine: Literal["native", "problog", "pyreason", "souffle"] = "native"
```

The four engines and the SDK config wrapper they map to are summarised in §1. `native` and `souffle` do not consume `SemanticsProfile`; `problog` and `pyreason` do. The reconciliation rules between `engine=` and `config=` live in §6.

## 3. `ProbLogConfig` — probabilistic semantics wrapper

`ProbLogConfig` is the SDK ergonomic wrapper for ProbLog. It carries five fields, all of which map to real ProbLog (Sato distribution semantics / De Raedt PLP) concepts.

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

`case_probabilities` is the dict that supplies those probabilities:

| Form | Meaning |
|---|---|
| `case_probabilities={"branch_id_a": 0.7, "branch_id_b": 0.3}` | The `branch_id_*` keys are the branch ids from your `RuleExpr` / OR shape; each value is the probability that branch derives the head when its body matches |
| `case_probabilities={}` *(default)* | All branches default to probability `1.0` — the rule degenerates to deterministic OR (any matching branch implies the head with certainty) |

Validation: every value must be a finite float in `(0, 1]`. Zero is rejected — a 0-probability branch is meaningless (it never derives anything).

Important relationship to **Track 1 Branch identity**: branch ids are first-class anchors in FactGraph (see `Rule.inspect` / `Inference.inspect` `branches` field). `case_probabilities` keys reference those branch ids, so the SDK can lower them to the positional tuple form the adapter expects (`ProbLogRuleExt.case_probabilities: tuple[float, ...]` in branch order).

### 3.3 `uncertainty_projection` — `raw_kind`+`bound` → point-probability projection

ProbLog facts carry point probabilities — `0.5::fact.` — not intervals. But FactGraph assertions carry the canonical `meta["raw_kind"]` + `meta["bound"]` form (see `data_model.md` §2.2):

```python
fg.fields.set(
    User.age, alice, 25,
    meta={"raw_kind": "probabilistic", "bound": [0.7, 0.7]},
)
```

`uncertainty_projection` says: *how do we convert this interval-carrying assertion form into the form the engine needs?*

The schema is a flat dict keyed by `raw_kind` value plus a `fallback` key:

```python
{
    "probabilistic": {"policy": "midpoint"},
    "possibilistic": {"policy": "reject"},
    "fallback": "reject_unconfigured",
}
```

The `policy` value is an enum from `UNCERTAINTY_POLICIES` (`factgraph.core.semantics.profile`):

| Policy | What it does | ProbLog accepts? | PyReason accepts? |
|---|---|---|---|
| `"reject"` | Refuse this `raw_kind`; raise if any assertion carries it. The default for both `probabilistic` and `possibilistic`. | ✓ (rejects at export) | ✓ (rejects at compile) |
| `"lower"` | Project `[lo, hi]` → `lo` (conservative — lowest support) | ✓ | ✓ |
| `"midpoint"` | Project `[lo, hi]` → `(lo + hi) / 2` (most neutral point choice) | ✓ | ✓ |
| `"upper"` | Project `[lo, hi]` → `hi` (optimistic — highest support) | ✓ | ✓ |
| `"identity_probability"` | Pass through only when `raw_kind="probabilistic"` AND `bound[0] == bound[1]` (degenerate / point bound); raises otherwise. Forces the author to assert points explicitly | ✓ | ✓ |
| `"probability_interval"` | Pass the interval through unchanged as a probability interval | ✗ rejected — ProbLog is a point-probability engine | ✓ |
| `"possibility_interval"` | Pass the interval through as a possibility interval | ✗ rejected | ✓ |

The default ProbLog profile (`_default_problog_uncertainty_projection`) **rejects both `probabilistic` and `possibilistic` by default** — the author must opt in by setting an explicit policy. The reasoning: silently converting an interval into a point probability is exactly the kind of "hidden semantic coercion" that produces invisible bugs. The default forces the question to surface.

`probability_interval` and `possibility_interval` are *interval-preserving* policies. ProbLog is point-only — its native form is `0.7::fact.`, no intervals — so it rejects both. PyReason is interval-native (`fact : [0.7, 1.0]`), so it accepts them. The same enum value means different things at different engines, and each engine validates which policies it can handle.

Possibility theory (Dubois & Prade) and probability theory (Kolmogorov) are different mathematical objects; the policy enum is split between them deliberately so the author cannot accidentally cross the boundary.

### 3.4 `fallback` — what to do when an assertion is not configured

Some assertions may have no `raw_kind` at all (a deterministically asserted fact). The `fallback` key inside `uncertainty_projection` (and the top-level `ProbLogConfig.fallback`) decides:

| Fallback | Behavior |
|---|---|
| `"reject_unconfigured"` *(default)* | Raise if an assertion has no policy — force the author to be explicit |
| `"warn_default"` | Emit a warning and project to probability `1.0` |
| `"use_default"` | Silently project to probability `1.0` |

The default is strict because a silent fallback to `1.0` quietly turns an uncertainty-aware computation into a certainty-aware one — a class of bug that is invisible in the output.

### 3.5 `rule_params` and `name`

- **`rule_params: dict[rule_id, dict]`** — per-rule metadata that lowers into the canonical `SemanticsProfile.rule_projection["problog"]`. Currently a forward-compatible slot for upcoming per-rule ProbLog options (the application-layer profile schema already accepts it; future adapter cycles will extend consumption). Empty by default.
- **`name: str | None`** — optional profile label that shows up in `fg.eval.preview_config(...)` and the canonical profile preview. Diagnostic only.

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

### 4.5 `derived_bound` and `head_bound` — head interval annotation

Both fields produce the same engine output: an interval `: [lo, hi]` after the head predicate.

```
derived_user_tag(U, T) : [0.8, 1.0]  <-2  user_tag_seed(U, T)
```

The interval `[0.8, 1.0]` says: *when the body matches, the head holds with certainty bounded below by `0.8` and above by `1.0`*. In PyReason's semantics this is the standard *annotated logic* lower/upper interval — the lower bound is the necessary degree of truth, the upper bound is the possible degree.

| Field | When to use |
|---|---|
| `derived_bound: tuple[float, float] \| None` | The canonical name (matches `SemanticsProfile.rule_projection.pyreason[].derived_bound`) |
| `head_bound: tuple[float, float] \| None` | Equivalent alias kept for ergonomic call sites |

**Mutually exclusive** — passing both raises `PyReasonConfig.derived_bound conflicts with PyReasonConfig.head_bound`. Validation: `0 <= lo <= hi <= 1`.

Default: `None` — no head bound annotation in the emitted rule (head holds at PyReason's default `[1, 1]` when the body matches).

### 4.6 `atom_bounds` — body atom interval annotation

`atom_bounds: dict[atom_id, (lo, hi)]` annotates *individual body atoms* with intervals. Keys use the canonical atom-id form `<rule_id>:atom_<index>`, where `<index>` is the position of the atom in the rule's `when` tuple (0-based):

```python
PyReasonConfig(
    atom_bounds={
        "adult_in_us:atom_1": (0.7, 1.0),    # atom #1 in rule "adult_in_us" must hold at >= 0.7
        "adult_in_us:atom_2": (0.9, 1.0),    # atom #2 in same rule must hold at >= 0.9
    },
)
```

Engine output (for `adult_in_us` rule):

```
derived(...) <-0 user:age(U, A) : [0.7, 1.0], user:region(U, R) : [0.9, 1.0]
```

The position-based key is more precise than a pred-id-based one — the same predicate can appear multiple times in a body (different variable bindings) and each occurrence can be constrained independently. SDK rejects any key not matching `<rule_id>:atom_<digit>` with `PyReasonConfig.atom_bounds keys must use <rule_id>:atom_<index>`.

This is how you say "this rule only fires when these specific body atoms match *with sufficient certainty*". Atoms without an explicit bound are not annotated (PyReason treats them at default `[1, 1]`).

### 4.7 `case_bounds` — per-branch head interval

`case_bounds: dict[branch_id, (lo, hi)]` overrides the head bound *per OR branch*. Same shape as ProbLog's `case_probabilities`: branch-id keys, interval values. The adapter looks up the branch's id in `case_bounds`; if found, that interval overrides `derived_bound` / `head_bound` for that branch only.

Use this when different evidence paths to the same head carry different certainty (e.g. an authoritative source path with `[0.95, 1.0]` and a heuristic path with `[0.5, 0.8]`).

### 4.8 `temporal_projection` — how time is discretized

`temporal_projection: dict` controls PyReason's timestep enumeration. Five modes:

| Mode | Meaning |
|---|---|
| `{"mode": "none"}` *(default)* | No temporal projection; `iteration_count` alone controls timesteps |
| `{"mode": "fixed_timesteps", "timesteps": N}` | Run N explicit timesteps. N must be positive int |
| `{"mode": "valid_time_boundaries", "universe": [start, end]}` | Derive timesteps from the `valid_from` / `valid_to` boundaries of assertions, clipped to `universe` |
| `{"mode": "fact_boundaries", "universe": [start, end]}` | Same shape as `valid_time_boundaries` but driven by the `ingested_at` meta key (fact arrival time) instead of business-time validity |
| `{"mode": "time_binned", "universe": [start, end], "bin_size": ...}` | Map a real-time universe into discrete bins. `bin_size` accepts the short forms `1d` / `1h` / `15m` / `1m` |

`valid_time_boundaries` / `fact_boundaries` / `time_binned` all need a `universe` of `[start, end]` ISO timestamps; assertions outside the universe are clipped. The choice between them comes down to *which timeline drives the discretisation*: business-time validity (`valid_time_boundaries`), arrival time (`fact_boundaries`), or fixed wall-clock bins (`time_binned`).

Validation pathing surfaces in error messages as `SemanticsProfile.temporal_projection.<mode>.<field>` so you can trace which projection rule rejected your config.

### 4.9 `uncertainty_projection`, `rule_params`, `name`, `fallback`

- **`uncertainty_projection`** — same role as on ProbLog (§3.3): convert assertion-level `raw_kind`+`bound` into engine-native form. PyReason is interval-native, so the most common policy is identity (pass `[lo, hi]` through unchanged) — but you can still configure strict / lenient handling per `raw_kind`.
- **`rule_params: dict[rule_id, dict]`** — same role as on ProbLog: per-rule metadata, lowered into `SemanticsProfile.rule_projection["pyreason"]`. Forward-compatible slot.
- **`name` / `fallback`** — same shape and semantics as on ProbLog (§3.5, §3.4).

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

This split (`SemanticsProfile` canonical / `ProbLogConfig` + `PyReasonConfig` ergonomic) is the same SDK-shadow / application-DTO pattern documented at [`docs/quickstart/rules.md`](rules.md) §2.6 for Rule vs the lower-level data shape. The SemanticsProfile naming is benign — application takes a neutral name, SDK takes the user-facing engine-specific names. (Compare the deferred Rule-namespace redesign discussed in [`workflow/design/design-points/active/rule-namespace-rulespec-redesign.zh.md`](../../workflow/design/design-points/active/rule-namespace-rulespec-redesign.zh.md) §2.2, where the same pattern is *not* yet applied.)

## 6. `engine=` and `config=` reconciliation

Three call shapes are accepted:

### 6.1 Only `config=` — engine inferred

```python
fg.eval.evaluate(rule, head=rule, config=ProbLogConfig(...))
# engine derived as "problog" from the wrapper
```

`config.engine` (a read-only property on the wrapper) supplies the engine. You do not have to pass `engine=` redundantly.

### 6.2 Only `engine=` — no semantics

```python
fg.eval.evaluate(rule, head=rule, engine="problog")
# semantics_profile = None — ProbLog runs without a profile
```

Legal for `problog` / `pyreason` (they run with their internal defaults) and the only legal form for `native` / `souffle` (which do not consume profiles at all).

### 6.3 Both — they must agree

```python
fg.eval.evaluate(rule, head=rule, engine="problog", config=ProbLogConfig(...))
# OK — engine and wrapper agree
```

Mismatch raises:

```
SDKStoreError: engine='problog' does not match semantics.engine='pyreason'
SDKStoreError: SemanticsProfile.engine='pyreason' does not match engine='problog'
```

### 6.4 Rejected legacy kwargs

The following kwargs are explicitly rejected with a redirect message:

| Old kwarg | Replacement |
|---|---|
| `semantics_profile=` | `config=` |
| `mode=` | `engine=` |
| `policy=` | (removed; not accepted for inference evaluation) |
| `view=` | `FactGraph.attach(db, view=view)` |
| `temporal_view=` | active/history views on read APIs |
| `engine_options=` | `config=` (or engine-specific configuration) |

## 7. `fg.eval.preview_config(...)` — inspect-only

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

## 8. → evaluation (next chapter)

This chapter stops at *what* engines and configs are. The actual call:

```python
result = fg.eval.evaluate(rule_or_expr, head=<Rule>, engine=..., config=...)
```

— with its `head=` parameter, returned `EvaluateResult` shape, row iteration, and explain integration — lives in `evaluation.md`. The shape of `EvaluateRow` / `Explanation` / claim payloads lives in `evidence.md`.

## 9. Reference

### 9.1 Types

```python
from factgraph.sdk import (
    ProbLogConfig,        # 5 fields, lowers to SemanticsProfile(engine="problog")
    PyReasonConfig,       # 11 fields, lowers to SemanticsProfile(engine="pyreason")
    SemanticsProfile,     # canonical DTO (factgraph.core.semantics.profile.SemanticsProfile)
)
```

### 9.2 Errors

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

### 9.3 Related chapters

- [`rules.md`](rules.md) — declarations that `evaluate(...)` consumes
- [`data_model.md`](data_model.md) §2.2 — the `raw_kind` / `bound` meta keys that `uncertainty_projection` projects
- `evaluation.md` *(next chapter)* — actual `fg.eval.evaluate(...)` call, `head=`, returned `EvaluateResult`
- `evidence.md` *(later chapter)* — `EvaluateRow` / `Explanation` / claim payload shapes
- Adapter docs:
  - [`src/factgraph/adapters/problog/`](../../src/factgraph/adapters/problog/) — `rule_ext.py`, `problog_export.py`
  - [`src/factgraph/adapters/pyreason/`](../../src/factgraph/adapters/pyreason/) — `rule_ext.py`, `where_compile.py`, `engine_eval.py`

### 9.4 Engine reference

External references for the engine semantics this chapter describes:

- **ProbLog** — *De Raedt, Kimmig, Toivonen (2007).* "ProbLog: A Probabilistic Prolog and its Application in Link Discovery." KU Leuven; Annotated Disjunctions follow the Sato distribution semantics
- **PyReason** — *Mor, Aditya, Tartaglione, Brik, Shakarian (2023).* "PyReason: Software for Open World Temporal Logic." Annotated logic with `[lower, upper]` intervals plus rule timestep delays
- **Souffle** — *Jordan, Scholz, Subotić (2016).* "Soufflé: On Synthesis of Program Analyzers." CAV 2016. Compiled Datalog
- **Native** — FactGraph's deterministic SLD evaluator; no external reference
