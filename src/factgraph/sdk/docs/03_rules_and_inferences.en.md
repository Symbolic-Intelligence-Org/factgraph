# SDK Rule / Query / Inference DSL

Scope: `src/factgraph/sdk/dsl` + the `eval` and `what_if` namespaces of
`FactGraph` / `SDKStore`. For the introductory walkthrough see
[`00_user_guide.en.md`](00_user_guide.en.md); for the API index see
[`04_api_surface.en.md`](04_api_surface.en.md); for what-if examples
see [`06_what_if_and_proof.en.md`](06_what_if_and_proof.en.md).

In the snippets below, `fg = FactGraph.create(schema_classes=[...])`.
All flat methods are also reachable through namespaces:

| Flat | Namespaced | Namespace |
|---|---|---|
| `fg.run / evaluate / accept / accept_many` | `fg.eval.<verb>` | `eval` |
| `fg.check / diagnose / why_not` | `fg.what_if.<verb>` | `what_if` |
| `fg.check_fact_overlay / recheck_proof_frame` | `fg.what_if.fact_overlay.{check, recheck_proof_frame}` | `what_if.fact_overlay` |
| `fg.check_rule_disable / check_rule_literal_replace / check_rule_add_condition` | `fg.what_if.rule.{disable, literal_replace, add_condition}` | `what_if.rule` |

Both forms have identical semantics. The flat form is permanently
supported.

### Engine runtime options

- Public `Rule` and `Inference` objects are engine-independent business
  templates. They do not carry adapter-specific `engine_ext` parameters.
- `engine_options` is **call-time** runtime configuration passed at
  `evaluate(...)` (e.g. `fg.eval.evaluate(inf, engine_options={"timesteps": 5})`).
  It never enters the `Inference` or the ledger. `engine="native"`
  rejects non-empty `engine_options`.
- Track 2 makes `ProbLogSemantics` and `PyReasonSemantics` the
  preferred public SDK wrappers for engine-specific semantics.
  `SemanticsProfile` remains the advanced/canonical profile shape.
  Public SDK calls reject `mode=` and `semantics_profile=`; use
  `engine=` and `semantics=`, or omit `engine=` when it can be derived
  from the semantics object.
- Track 3-post lets `PyReasonSemantics.branch_bounds` reference branch
  ids from `Branch([...], id="...")` or fallback positional ids such as
  `b0` / `b1`. Branch-specific bounds override the wrapper's global
  `head_bound` for that branch only.

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
- `Rule` is engine-independent public syntax. Adapter-specific rule
  projection is not carried by public `engine_ext` fields.
- `Rule.condition_weights` remains public as certainty/explain
  projection input keyed by `b{branch}.a{atom}`. It is not an engine
  adapter parameter and does not enter `where` execution semantics.
  Future runtime configuration for this lane belongs in
  `SemanticsProfile.certainty_projection`.
- The `row_format` precedence chain (`call-site > SDKStore(default_row_format=...) > FACTPY_ROW_FORMAT > "dict"`) and the `"tuple"` `DeprecationWarning` apply to the **Rule path**. `Query` has its own narrower contract (`"dict"|"instance"`, `"tuple"` rejected) — see §5.
- Resolving to `"tuple"` emits `DeprecationWarning` (prefer `"dict"`).
- `policy=` and `return_display_meta=True` are removed from `run(...)`;
  read-time confidence/display aggregation is not a public SDK surface.

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
- `Branch` branches: `where=[Branch([...], id="seed_path"), Branch([...])]` (Rule/Inference)
- linear arithmetic inside comparisons (for example `age == (2026 - by)`, `x * 2`)
- aggregate helpers for the application Rule bridge:
  `agg_count`, `agg_sum`, `agg_min`, `agg_max`, and `agg_mean`

`Branch` example:

```python
from factgraph.sdk import Branch

where = [
    Branch([User(u), Pred("user:lang_pref", u, lang)], id="declared_pref"),
    Branch([User(u), Pred("user:inferred_lang", u, lang)]),
]
```

Limits:
- path sugar supports only `==`.
- attr-vs-attr comparisons support only `==`, and require schema-aware compilation.
- non-linear multiplication (`x * y`) is unsupported.
- `where` cannot mix `Branch(...)` with bare branches (for example `[Branch([...]), [...]]`).
- `Branch(...)` accepts the branch atom list plus optional keyword-only structural `id=`.
  Probability, confidence, and engine-specific kwargs are rejected.
- `fg.rules.inspect(rule_or_inference)` exposes explicit branch ids, positional fallback ids (`b0`, `b1`, ...), and atom ids such as `b0.a0`.
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

### 3.2 Aggregate Helpers for Application Rules

Aggregate helpers are available from `factgraph.sdk.dsl` for
`build_application_rule(...)`:

```python
from factgraph.sdk import build_application_rule, vars
from factgraph.sdk.dsl import agg_sum

with vars("u", "o", "total") as (u, o, total):
    rule = build_application_rule(
        id="user_order_total",
        where=[
            User(u),
            total == agg_sum(Order(o).amount, where=[Order(o).buyer == u]),
            total > 100,
        ],
        ports={"user": u, "total": total},
    )
```

`agg_count(where=[...])` has no target. `agg_sum`, `agg_min`, `agg_max`, and
`agg_mean` require a target, usually a schema field reference such as
`Order(o).amount`. Aggregate filters may correlate with variables bound outside
the aggregate, but variables introduced only inside the filter remain local to
the aggregate and cannot be exposed as application Rule ports.

Adapter status:

| Engine/layer | Aggregate status |
|---|---|
| Python application Rule evaluator | Supported |
| SDK `build_application_rule(...)` bridge | Supported |
| Souffle adapter | Supported (empty `min`/`max`/`mean` follow C101 via `count > 0` guard, branch does not fire) |
| ProbLog adapter | Supported (`findall/3` + `library(lists)` predicates; empty `min`/`max`/`mean` use `L = [_|_]` guard, branch does not fire) |
| PyReason adapter | Out of scope |

## 3.3 RuleExpr Authoring Surface

RuleExpr is the application-rule composition surface. During the staged T1.3/T3
period, top-level `factgraph.sdk.Rule` remains the legacy SDK Rule. Use
`ApplicationRule` for direct application DTO imports, or use
`build_application_rule(...)` when starting from SDK DSL syntax:

```python
from factgraph.sdk import ApplicationRule, RuleExpr, build_application_rule, vars
```

`factgraph.sdk.ApplicationRule` and `factgraph.application.protocol.Rule` are
the same runtime type. The final top-level `Rule` name flip is deferred to T5.

### Building operands

Prefer the bridge for user-facing examples:

```python
from factgraph.sdk import build_application_rule, vars

with vars("u") as (u,):
    active_user = build_application_rule(
        id="active_user",
        where=[User(u), User(u).status == "active"],
        ports={"user": u},
        desc="active user %user",
    )

with vars("u") as (u,):
    assigned_owner = build_application_rule(
        id="assigned_owner",
        where=[User(u), User(u).role == "owner"],
        ports={"user": u},
        desc="assigned owner %user",
    )
```

Occurrence aliases identify each use of a rule inside an expression:

```python
a = active_user.as_("a")
b = assigned_owner.as_("b")
```

If a rule appears more than once in one RuleExpr, use explicit aliases for each
occurrence.

### Composition, precedence, and bool guards

Use `&` and `|` for RuleExpr construction:

```python
expr = (a & b) | c      # explicit OR of an AND group and c
expr = a & (b | c)      # explicit AND with an OR branch
```

Python `&` binds tighter than `|`, so `a & b | c` is parsed as `(a & b) | c`.
Use parentheses for every mixed AND/OR expression.

Do not use Python boolean operators:

```python
expr = a and b          # raises ExplicitBoolError because Python evaluates bool(a) for short-circuit
if expr:                # raises ExplicitBoolError
    ...
```

Use explicit optional checks when needed:

```python
if expr is None:
    ...
```

### Explicit joins

RuleExpr joins bind occurrence ports. Initial T3 syntax is explicit `.eq(...)`,
not Python `==`, so T1.4 `RulePortRef` value equality remains intact:

```python
expr = (a & b).join(a.user.eq(b.user))
```

`.join(...)` is AND-only. It is not available on a single `Rule` /
`RuleOccurrence`, and OR groups reject it with guidance to attach joins inside
AND branches. Same-occurrence joins such as `a.user.eq(a.user)` are rejected.

### Explicit-name joins

Same-name ports do not auto-join. If both `a` and `b` expose a `user` port,
`a & b` is still unjoined until you say how they relate.

Use either direct constraints:

```python
expr = (a & b).join(a.user.eq(b.user))
```

or explicit-name expansion:

```python
expr = (a & b).join_by_ports("user")
```

`.join_by_ports("user")` expands the requested port name pairwise across
reachable AND operands. The method reports missing names, names present on
fewer than two occurrences, duplicate requested names, and invalid name shapes.
It is still explicit authoring, not silent same-name-port joining.

Inspect unjoined same-name hints:

```python
hints = fg.rules.inspect(a & b).unjoined_same_name_ports
# [{"port_name": "user", "occurrences": ("a", "b")}]
```

### Inspect return shapes

`fg.rules.inspect(...)` is intentionally polymorphic:

```python
legacy_payload = fg.rules.inspect(legacy_rule)       # dict
legacy_inf     = fg.rules.inspect(legacy_inference)  # dict
rule_view      = fg.rules.inspect(active_user)       # RuleExprInspect
expr_view      = fg.rules.inspect(expr)              # RuleExprInspect
```

Legacy SDK `Rule` / `Inference` inputs keep the existing dict payload. Application
`Rule` and RuleExpr inputs return `RuleExprInspect`.

`RuleExprInspect` exposes:

- `ast`
- `occurrences`
- `joins`
- `unjoined_same_name_ports`
- `templates`
- `port_visibility`
- `ports`
- `render(bindings=None)`
- `render_compact()`

`OccurrenceInspect.ports` is a tuple of local port name strings. In contrast,
`RuleExprInspect.ports` is a tuple of `PortInspect` descriptors aggregated
across inspected occurrences. For value ports, `value_type="unknown"` means the
current application `PortType` substrate does not carry concrete value type
metadata.

`render()` and `render_compact()` are deterministic authoring narratives. They
do not read the ledger and are not proof explanations.

### RuleExpr execution

`fg.eval.evaluate(...)` also accepts application `Rule` and RuleExpr values
when you provide an application `Rule` as `head=`:

```python
candidates = fg.eval.evaluate(expr, head=active_user, engine="native")
```

The public success shape is the existing `list[CandidateSet]`; no RuleExpr
result wrapper or public trace DTO is returned. A single application `Rule`
input is treated like a one-rule RuleExpr:

```python
candidates = fg.eval.evaluate(active_user, head=active_user)
```

The supplied `head=` must already be an inline/projected rule occurrence in the
expression. External head body concatenation is not public in this tranche; add
the head rule as an expression occurrence and pass that same application `Rule`
as `head=`.

Supported engines are `native`, `souffle`, `problog`, and the current PyReason
pred-only subset. PyReason rejects RuleExpr joins, source non-pred atoms, and
aggregate-containing branches before adapter invocation with `SDKStoreError`
guidance that names the engine, unsupported feature, rejection source, and
known alternative engines.

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
- `RuleRef` is a where-clause carrier. It is not a persistence handle;
  SavedRule/SavedInference persistence was removed by Q8 Phase 2.

## 4.1 In-memory Rule and Inference Values

> Q8 Phase 2 (Slice 6) removed the SavedRule/SavedInference persistence layer.
> `fg.rules.save / load / list / get`, `fg.inferences.save / load / list / get`,
> `SavedRuleRef`, and `SavedInferenceRef` are no longer part of the SDK.
> Rules and inferences are used as in-memory value objects:

```python
fg = FactGraph.create(schema_classes=[User], path="./workspace")

my_rule = Rule(rule_id="rule_alice", version="1.0.0", select_vars=["x"], where=[...])
rows = fg.eval.run(my_rule)

my_inference = Inference(id="drv.copy_name", version="1.0.0", where=[...], head=...)
candidates = fg.eval.evaluate(my_inference)
```

`fg.rules.inspect(rule_or_inference)` is the only remaining structural inspection
API on the `fg.rules.*` namespace.

When the graph is workspace-backed, `fg.save()` persists the ledger plus the
schema IR. `FactGraph.load("./workspace", schema_classes=[User])` restores the
workspace; user code constructs Rule/Inference values in memory afresh each
session.

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

## 6. Inference DSL

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    inf = Inference(
        id="drv.copy_name",
        version="1.0.0",
        where=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

cands = sdk.evaluate(inf, engine="native")
res = sdk.accept(cands[0], approved_by="alice")
```

Fields:
- required: `id`, `version`, `where`
- optional: `head`, `target`, `head_vars`, `status`, `description`, `tags`

Stable contract:
- `head` shape infers candidate kind (fact/entity).
- Public SDK `Inference` is single-head. Multi-head (`head=[H1, H2, ...]`) is rejected in Track 1; define one inference per head.
- `Rule/Inference.where` both support `Branch(...)`; it unwraps to normalized OR-branch structure.
- `sdk.run(inference)` is not supported; use `sdk.evaluate(...)`.
- `sdk.run(inference)` fails with code `QUERY_INVALID_ROW_FORMAT` (error message directs callers to `evaluate()`).

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
cands = sdk.evaluate(inf, engine="native")
```

- `engine`: `native` (default) / `souffle` / `problog` / `pyreason`.
- SDK lowers `Inference` DSL objects into compiled plans, then delegates orchestration to application `evaluate_derivation_plans(...)`; SDK remains responsible for mode alias rejection, registry sugar, and outward compatibility.
- Legacy `mode='python'` / `mode='engine'` **values** fail with explicit rename hints (use `mode='native'` / `mode='souffle'` respectively); enforced at `factgraph/core/store/_evaluate.py:50,52`.
- `souffle` / `problog` / `pyreason` require registered adapters (for example `import factgraph.adapters.souffle`, `import factgraph.adapters.problog`, `import factgraph.adapters.pyreason`).
- `sdk.evaluate(..., view=...)` and `sdk.evaluate(..., policy=...)` are
  not supported; inference always uses the full active assertion set.
- `engine_options` is call-time engine run-time configuration, for example `sdk.evaluate(inf, engine="pyreason", engine_options={"timesteps": 5})`.
- `engine_options` does not enter `Inference` or `to_authoring_payload()`; `mode="native"` rejects non-empty `engine_options`.
- RuleExpr execution uses the same public entrypoint as inference evaluation:
  `sdk.evaluate(expr, head=application_rule, engine=...)` returns
  `list[CandidateSet]`. `head=` is required and must be an application `Rule`;
  legacy SDK `Rule` / `Inference` objects are rejected as heads.

### 8.2 `CandidateSet` key fields

- `candidate_id`: per-run handle
- `candidate_key`: cross-run stable key
- `candidate_kind`: `fact` / `entity`
- `confidence` / `confidence_kind`: internal/session output carriers only.
  ProbLog and PyReason may set them on `CandidateSet`, but service DTOs do not
  expose them by default and `accept(...)` does not persist them as assertion
  meta.
- Candidate `confidence` is not the canonical raw uncertainty carrier.
  User-authored raw uncertainty belongs on facts as
  `meta={"raw_kind": ..., "bound": [...]}` and is persisted to
  `shared/semantic/raw_kind` plus `shared/semantic/bound`.
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
- Same claim with different business-semantic meta such as `source` is
  allowed to coexist.
- Legacy candidate confidence differences alone do not affect duplicate
  detection.

## 9. Temporal Boundary (Current Status)

Implemented:
- Read-side temporal filtering via `snapshot.assertions.<field>.at(t)` and
  `.version(v)` active shortcuts, plus `AssertionRecordSet` filters such as
  `snapshot.assertions.field(...).all().at(t)`.
- `T1` temporal checks can be expressed via explicit temporal predicates plus the existing comparison syntax:
  - deadline: temporal anchor predicate + `<=` / `<`
  - window membership: temporal anchor predicate + `>=` / `<=`
  - interval relation: helper rule + existing comparisons
- This path requires temporal predicate arguments to use schema tag `"time"` (Python `int`, epoch nanoseconds), not the ISO 8601 read-side convention used by `.at(t)`.
- If a temporal anchor must support explain drill-down, model it as a predicate assertion or at least bind it to a variable so it surfaces through `pred_witnesses` or `non_fact_steps.details.binding`.

Not open yet:
- inference/runtime `temporal_view` parameter.
- dedicated temporal where atom / temporal builtin tag.
- temporal write semantics in Rule/Inference head.

Explicit behavior:
- Authoring inference payload with `temporal_view` fails compile.
- `sdk.evaluate(..., temporal_view=...)` raises `SDKStoreError`.

## 10. Minimal End-to-End Examples

### 10.1 Fact candidate

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    inf = Inference(
        id="drv.alias",
        version="1.0.0",
        where=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

fact = next(c for c in sdk.evaluate(inf) if c.candidate_kind == "fact")
sdk.accept(fact, approved_by="alice")
```

### 10.2 Entity candidate + dependent facts

```python
with vars("u", "lang") as (u, lang):
    inf = Inference(
        id="drv.speaks",
        version="1.0.0",
        where=[User(u), Pred("user:lang_pref", u, lang)],
        head=Speaks(user=u, language=lang),
    )

rows = sdk.accept_many(sdk.evaluate(inf), mode="atomic")
```
