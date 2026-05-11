# SDK Rule / Query / Derivation DSL

Scope: `src/kernel/sdk/dsl` + the `eval` and `what_if` namespaces of
`FactGraph` / `SDKStore`. For the introductory walkthrough see
[`00_user_guide.en.md`](00_user_guide.en.md); for the API index see
[`04_api_surface.en.md`](04_api_surface.en.md); for what-if examples
see [`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md).

In the snippets below, `fg = FactGraph.from_schema_classes([...])`.
All flat methods are also reachable through namespaces:

| Flat | Namespaced | Namespace |
|---|---|---|
| `fg.run / evaluate / evaluate_compiled / accept / accept_compiled / accept_many` | `fg.eval.<verb>` | `eval` |
| `fg.check / diagnose / why_not` | `fg.what_if.<verb>` | `what_if` |
| `fg.check_fact_overlay / recheck_proof_frame` | `fg.what_if.fact_overlay.{check, recheck_proof_frame}` | `what_if.fact_overlay` |
| `fg.check_rule_disable / check_rule_literal_replace / check_rule_add_condition` | `fg.what_if.rule.{disable, literal_replace, add_condition}` | `what_if.rule` |

Both forms have identical semantics. The flat form is permanently
supported.

### `engine_ext` vs `engine_options`

- `engine_ext` is **definition-time** semantics that travel with a
  `Rule` or `Derivation` (e.g. `Rule(..., engine_ext=PyReasonRuleExt(...))`).
  It must inherit `EngineExtBase`.
- `engine_options` is **call-time** runtime configuration passed at
  `evaluate(...)` (e.g. `fg.eval.evaluate(deriv, engine_options={"timesteps": 5})`).
  It never enters the `Derivation` or the ledger. `mode="native"`
  rejects non-empty `engine_options`.

## 1. `vars(...)`

Supported:

```python
with vars("p", "c") as (p, c):
    ...
```

```python
with vars() as V:
    p, c = V("p", "c")
```

Unsupported:
- `with vars() as (p, c)` (SDK raises `SDKDSLError` due Python runtime limits)

## 2. Rule DSL

```python
with vars("li", "u", "c") as (li, u, c):
    rule = Rule(
        id="q_user_country",
        version="1.0.0",
        select=[u, c],
        where=[
            LivesIn(li),
            li.user == u,
            li.country == c,
        ],
        expose=True,
    )

rows = sdk.run(rule, row_format="dict")
```

Stable contract:
- `Rule.id/version` must be non-empty strings.
- `Rule.select/where` must be non-empty lists.
- `engine_ext` is available as a definition-time engine semantics carrier and never enters authoring payload serialization.
- The `row_format` precedence chain (`call-site > SDKStore(default_row_format=...) > FACTPY_ROW_FORMAT > "dict"`) and the `"tuple"` `DeprecationWarning` apply to the **Rule path**. `Query` has its own narrower contract (`"dict"|"instance"`, `"tuple"` rejected) — see §5.
- Resolving to `"tuple"` emits `DeprecationWarning` (prefer `"dict"`).

## 3. `where` Syntax and Limits

Supported:
- entity-exists sugar: `LivesIn(li)`
- path equality sugar: `li.user == u`, `li.country == c`
- field predicate sugar: `u.name == nm`, `u.tag == "vip"` (lowered to schema predicates such as `user:name` / `user:tag`)
- attr-vs-attr comparison: `u1.user_id == u2.user_id`
- explicit predicate atom: `Pred("user:tag", u, "vip")`
- rule reference: `RuleRef(...)(...)`
- negation: `Not([...])`
- comparisons: `== != > >= < <=`
- OR branches: `where=[[...], [...]]`
- `Body` branches: `where=[Body([...], confidence=0.9), Body([...], confidence=0.6)]` (Rule/Derivation)
- linear arithmetic inside comparisons (for example `age == (2026 - by)`, `x * 2`)

`Body` example:

```python
from kernel.sdk import Body

where = [
    Body([User(u), Pred("user:lang_pref", u, lang)], confidence=0.9),
    Body([User(u), Pred("user:inferred_lang", u, lang)], confidence=0.6),
]
```

Limits:
- path sugar supports only `==`.
- attr-vs-attr comparisons support only `==`, and require schema-aware compilation.
- non-linear multiplication (`x * y`) is unsupported.
- `where` cannot mix `Body(...)` with bare branches (for example `[Body([...]), [...]]`).
- `Body.confidence` must be in `(0,1]`; if any branch sets confidence, all `Body` branches must set it.
- Query does not support `Body.confidence` (`confidence!=None` fails fast).
- string DSL is unsupported (`sdk.run("...")`, `sdk.evaluate("...")`).

### 3.1 Field Sugar vs `Pred(...)`

For schema-field conditions in `where`, prefer field sugar:

```python
where=[User(u), u.name == nm, u.tag == "vip"]
```

This lowers to the corresponding predicates:

```python
Pred("user:name", u, nm)
Pred("user:tag", u, "vip")
```

Both `single` and `multi` fields support this field-to-value form. For `multi` fields, the semantics are membership: the condition is true when a parallel fact such as `user:tag(u, "vip")` exists.

`Pred(...)` is the low-level explicit-predicate escape hatch. Use it for:

- custom predicates outside schema fields
- temporal / uncertainty / adapter-specific predicates
- migrations or debugging where spelling the predicate id directly matters

Do not confuse field-to-value sugar with attr-vs-attr comparison. `u1.user_id == u2.user_id` follows cross-coordinate `attr_eq` lowering and currently only allows the same entity type, the same field, and a `primary_key` field.

## 4. RuleRef and Dependency Registration

Construction:

```python
RuleRef("q_x", version="1.0.0")
RuleRef(existing_rule_obj)
```

Rules:
- RuleRef target must be `expose=True`, otherwise runtime `RuleCompileError`.
- `RuleRef` is forbidden inside `Not(...)` body (compile-time error).
- `sdk.run(..., registry=None)` auto-registers `RuleRef(RuleObj)` dependencies.
- If `registry` is explicitly provided, SDK does not auto-fill dependencies.

## 5. Query DSL

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    q = Query(
        head=[User(u), User.name(locale=loc, name=nm)],
        where=[User(u), u.locale == loc, u.name == nm],
        on_missing="error",
        on_type_mismatch="error",
    )

rows = sdk.run(q)  # list[dict]
```

Stable contract:
- Query head only supports `Entity(var)` and `Entity.field(...)`.
- Query supports `row_format="dict"|"instance"`; default is `"dict"`.
- `row_format="instance"` is allowed only for a single `Entity(var)` head and returns instance rows (`list[EntitySnapshot|None]`).
- Field projection must resolve to schema `single` fields.
- Unbound variables in `where` fail at construction with `SDKDSLError(code="QUERY_UNBOUND_VAR")`.
- `on_missing` / `on_type_mismatch` only allow `error|skip|null`.
- Invalid Query `row_format`, or incompatible head shape for `instance` mode, raises `SDKStoreError(code="QUERY_INVALID_ROW_FORMAT")`.

## 6. Derivation DSL

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    d = Derivation(
        id="drv.copy_name",
        version="1.0.0",
        where=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

cands = sdk.evaluate(d, mode="native")
res = sdk.accept(cands[0], approved_by="alice")
```

Fields:
- required: `id`, `version`, `where`
- optional: `head`, `target`, `head_vars`, `mode`, `engine_ext`, `status`, `description`, `tags`

Stable contract:
- `head` shape infers candidate kind (fact/entity).
- Multi-head (`head=[H1, H2, ...]`) is supported; `evaluate` returns flattened candidates sharing one `run_id`.
- `Rule/Derivation.where` both support `Body(...)`; Rule path only unwraps atoms and ignores `confidence`.
- `sdk.run(derivation)` is not supported; use `sdk.evaluate(...)`.
- `sdk.run(derivation)` fails with code `QUERY_INVALID_ROW_FORMAT` (error message directs callers to `evaluate()`).

## 7. Compile-Time Hard Constraints (v2)

### 7.1 `head` and primary key

- Any primary-key field in `head` -> compile error.
- Missing entity binding in `where` for implicit primary-key carry -> compile error.
- Multiple same-type bindings in `where` that cannot be disambiguated -> compile error.

### 7.2 Cross-coordinate attr comparison

`u1.user_id == u2.user_id` is legal only when:
- both sides are the same entity type
- both sides use the same field
- that field is declared as `primary_key`

Otherwise, compilation fails (no implicit guessing).

### 7.3 Lowering shape

Valid cross-coordinate primary-key comparison is lowered to shared system vars (`$__pk_N`):

```python
("pred", "user:user_id", ["$u1", "$__pk_0"])
("pred", "user:user_id", ["$u2", "$__pk_0"])
```

System-prefixed temporary names are reserved.

## 8. `evaluate/accept` Runtime Semantics

### 8.1 `sdk.evaluate(...)`

```python
cands = sdk.evaluate(drv, mode="native")
```

- `mode`: `native` (default) / `souffle` / `problog` / `pyreason`.
- SDK lowers `Derivation` DSL objects into compiled plans, then delegates orchestration to application `evaluate_derivation_plans(...)`; SDK remains responsible for mode alias rejection, registry sugar, and outward compatibility.
- Legacy `mode='python'` / `mode='engine'` **values** fail with explicit rename hints (use `mode='native'` / `mode='souffle'` respectively); enforced at `kernel/core/store/_evaluate.py:50,52`.
- `souffle` / `problog` / `pyreason` require registered adapters (for example `import kernel.adapters.souffle`, `import kernel.adapters.problog`, `import kernel.adapters.pyreason`).
- `sdk.evaluate(..., view=...)` is not supported; inference always uses the full active assertion set.
- `engine_options` is call-time engine run-time configuration, for example `sdk.evaluate(drv, mode="pyreason", engine_options={"timesteps": 5})`.
- `engine_options` does not enter `Derivation` or `to_authoring_payload()`; `mode="native"` rejects non-empty `engine_options`.

### 8.2 `CandidateSet` key fields

- `candidate_id`: per-run handle
- `candidate_key`: cross-run stable key
- `candidate_kind`: `fact` / `entity`
- `confidence`: `float | None` (`problog` yields a probability; `pyreason` yields a lower-bound; `native/souffle` return `None`)
- `confidence_kind`: literal `"none"` (native/souffle) / `"probability"` (problog) / `"certainty"` (pyreason); paired with `confidence` to disambiguate the engine semantic. Source: `kernel/core/derivation/candidates.py:10, 27`.
- `confidence` belongs to the probabilistic-engine lane and should not be reused as Scenario A requirement-threshold probability; that path should use fact-backed uncertainty predicates plus the existing comparison syntax.
- `payload`:
  - fact: `{"pred_id": ..., "terms": [...]}`
  - entity: `{"entity_type": ..., "resolved_identity": ..., ...}`

### 8.3 `sdk.accept(...)`

```python
sdk.accept(candidate, approved_by="alice", note="ok", dry_run=False)
```

Accept sugar keys:
- `approved_by`
- `note`
- `dry_run`
- `identity_override` (for incomplete entity identity)
- `meta_overrides` (can carry the same sugar keys)

Parameter boundaries:
- `accept(CandidateSet, ...)` accepts exactly one positional argument; extra positional arguments raise `SDKStoreError`.
- `meta_overrides` only supports `approved_by` / `note` / `dry_run` / `identity_override`; unknown keys fail.
- If the same sugar key is provided in both `meta_overrides` and top-level keyword args, SDK raises duplicate-option error.
- Repeated accept on the same candidate is idempotent no-op (`duplicate`).
- Same claim with different business-semantic meta (for example `confidence`, `source`) is allowed to coexist.
- Within one `run_id` batch, same-claim/different-confidence candidates are usually not expected; coexistence mainly appears across batches/sources.

## 9. Temporal Boundary (Current Status)

Implemented:
- Read-side temporal filtering via `snapshot.assertions.<field>.at(t)` and
  `.version(v)` active shortcuts, plus `AssertionRecordSet` filters such as
  `snapshot.assertions.<field>.history.at(t)`.
- `T1` temporal checks can be expressed via explicit temporal predicates plus the existing comparison syntax:
  - deadline: temporal anchor predicate + `<=` / `<`
  - window membership: temporal anchor predicate + `>=` / `<=`
  - interval relation: helper rule + existing comparisons
- This path requires temporal predicate arguments to use schema tag `"time"` (Python `int`, epoch nanoseconds), not the ISO 8601 read-side convention used by `.at(t)`.
- If a temporal anchor must support explain drill-down, model it as a predicate assertion or at least bind it to a variable so it surfaces through `pred_witnesses` or `non_fact_steps.details.binding`.

Not open yet:
- derivation/runtime `temporal_view` parameter.
- dedicated temporal where atom / temporal builtin tag.
- temporal write semantics in Rule/Derivation head.

Explicit behavior:
- Authoring derivation payload with `temporal_view` fails compile.
- `sdk.evaluate(..., temporal_view=...)` raises `SDKStoreError`.

## 10. Minimal End-to-End Examples

### 10.1 Fact candidate

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    drv = Derivation(
        id="drv.alias",
        version="1.0.0",
        where=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

fact = next(c for c in sdk.evaluate(drv) if c.candidate_kind == "fact")
sdk.accept(fact, approved_by="alice")
```

### 10.2 Entity candidate + dependent facts

```python
with vars("u", "lang") as (u, lang):
    drv = Derivation(
        id="drv.speaks",
        version="1.0.0",
        where=[User(u), Pred("user:lang_pref", u, lang)],
        head=Speaks(user=u, language=lang),
    )

rows = sdk.accept_many(sdk.evaluate(drv), mode="atomic")
```
