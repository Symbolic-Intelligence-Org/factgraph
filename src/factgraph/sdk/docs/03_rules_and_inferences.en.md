# SDK Rule / Query / Inference DSL

Scope: `src/factgraph/sdk/dsl` + the `eval` namespace of
`FactGraph` / `SDKStore`. For the introductory walkthrough see
[`00_user_guide.en.md`](00_user_guide.en.md); for the API index see
[`04_api_surface.en.md`](04_api_surface.en.md).

In the snippets below, `fg = FactGraph.create(schema_classes=[...])`.
All flat methods are also reachable through namespaces:

| Public entrypoint | Namespace |
|---|---|
| `fg.entities.match(EntityCls, rule_or_expr, **ports)` | Return snapshots selected by a `Rule` or `RuleExpr` |
| `fg.eval.evaluate(...)` | Evaluate an `Inference`, `Rule`, or `RuleExpr` and return `EvaluateResult` |
| `fg.eval.explain(expr, head=closed_head, ...)` | Replay a closed-head explanation and return `Explanation` |
| `fg.eval.preview_config(...)` | Inspect semantics configuration without running an engine |

Legacy `run`, `accept`, `accept_many`, direct `check` / `diagnose` /
`why_not`, and `what_if.*` shells are not part of the T5 public evidence
path.

## V1 GoalPlan Query / Scenario path

The existing `fg.eval.evaluate(...)`, `EvaluationQueryBuilderV1.evaluate()`,
`capture()`, and V0 Scenario terminals remain compatibility APIs. They do not
silently acquire Scenario algebra, a provider callback, or portable execution.

### SDK-authored Policy targets

For new product code, use the symmetric Rule/Policy builders.  ``AssetMeta``
is a descriptive, separately sealed label; it never changes logical Rule or
Policy identity and it never registers an asset by id:

```python
from factgraph.sdk import AssetMeta, vars

with vars("person", "age") as (person, age):
    person_values = fg.build_rule(
        id="person_values",
        version="1",
        meta=AssetMeta(name="Person values", tags=("demo", "people")),
        when=(Person(person), Person(person).age == age),
        ports={"person": person, "age": age},
        semantic_ports={"person": Person, "age": Person.age},
    )

ranked = fg.policy_builder(
    "ranked_people",
    version="1",
    meta=AssetMeta(name="Rank eligible people", tags=("ranking",)),
)
people = ranked.use(person_values, as_="people")
target = ranked.build(ranked.all(people, people.age >= 18))
```

For a product Rule, `semantic_ports` uses public schema descriptors: an
`Entity` class means its complete identity endpoint and a bound `Field`
descriptor means that scalar field endpoint. The builder still resolves both
against this exact graph and requires matching positive body witnesses. Raw
`SemanticEndpoint` / `SemanticRulePort` inputs remain advanced compatibility
forms; routine SDK code does not need application or core imports.

``fg.rule_builder(...).build(...)`` is the staged form of ``build_rule``.
Likewise, ``fg.build_policy(id=..., build=lambda policy: ...)`` constructs one
``PolicyBuilder`` and calls the callback on that exact builder, preserving the
local ownership of ``use(..., as_=...)`` handles.  The older concise
``fg.policy(...)`` / ``PolicyDraft`` form remains supported for Q19
compatibility and returns an unlabelled ``AuthoredPolicyTargetV1``.

For normal SDK callers, author a managed Policy through a typed draft instead
of constructing `PolicyAll`, `PolicyAny`, `PolicyOccurrence`,
`SemanticAddressSpace`, or `SemanticPortAddress` directly:

```python
review = fg.policy("age_review", version="1")
people = review.use(person_values_rule, as_="people")
other = review.use(person_values_rule, as_="other")

target = review.build(
    review.all(
        people,
        other,
        people.age > 12,
        people.person.field("age") > other.person.field("age"),
    )
)
```

To make alternatives explicit, use each declared occurrence once in its own
branch; the nesting is preserved for Explain rather than flattened:

```python
alternatives = fg.policy("age_band", version="1")
young = alternatives.use(person_values_rule, as_="young")
mature = alternatives.use(person_values_rule, as_="mature")
age_band = alternatives.build(
    alternatives.any(
        alternatives.all(young, young.age < 30),
        alternatives.all(mature, mature.age >= 30),
    )
)
```

`target` is an `AuthoredPolicyTargetV1`: an immutable application `Policy`
and its exact semantic address space. `fg.query(target)` sends that pair to the
existing managed Policy compiler rather than a new evaluator. The same handles can be passed to
`bind` and `select`:

```python
query = (
    fg.query(target)
      .bind(people.person, alice_ref)
      .select("age", people.age)
)
```

`draft.all(...)` and `draft.any(...)` are deliberately explicit and preserve
the authored nesting topology (with deterministic canonical child ordering); do
not use Python `and` / `or`. Symbolic handles
raise in a Python boolean context, so chained comparisons such as
`12 < people.age < 65` also fail loudly. Write
`draft.all(people.age >= 12, people.age < 65)` instead. Entity identity is
also explicit: use `draft.same(left.person, right.person)`, not `==`.

Rich comparisons are a bounded convenience, not a dynamically typed formula
language. Direct scalar ports and one-hop same-entity field navigation support
`==`, `!=`, `>`, `>=`, `<`, and `<=`. Literal operands currently support only
canonical signed-int64 `int` and `time` values, so `people.age > 12` is valid
while strings, booleans, floats, UUIDs, bytes, `None`, entity references, and
literal-vs-literal comparisons reject. There is intentionally no global
`fg.compare(...)`: the handle provides the schema domain, Policy draft owner,
and semantic address that make a comparison meaningful.

### Explicit exclusive stochastic topology

``all(...)`` and ``any(...)`` are always deterministic logical nodes.  Do not
put weights or generic engine settings on either one.  A categorical model is
an explicit product-builder sidecar instead:

```python
key = ranked.use(person_values, as_="key")
declared = ranked.use(person_values, as_="declared")
inferred = ranked.use(person_values, as_="inferred")

source = ranked.weighted_choice(
    id="eligibility_source",
    on=(key.person,),
    choices=(
        ranked.choice("declared", probability="0.7", when=ranked.all(declared)),
        ranked.choice("inferred", probability="0.3", when=ranked.all(inferred)),
    ),
)
target = ranked.build(ranked.all(key, source))
```

Weights are canonical decimal strings, not floats; every positive arm must
sum exactly to ``"1"`` and the ordered ``on=`` semantic-port key must occur in
every logical arm.  This is an exclusive choice (future V2 ProbLog annotated
disjunction), not a synonym for ``any(...)`` or a model of independent causes.
Until the V2 ProbLog terminal is selected, all legacy compilation/evaluation,
capture, Scenario-v0 and V1-plan terminals fail closed with
``WEIGHTED_CHOICE_V2_ONLY`` rather than silently treating it as ordinary OR.

For the Q18 V1 path, start with a resolved Rule, an advanced managed `Policy`,
or the SDK-authored target above; declare structured `bind` / ordered `select`
intent, then call the new terminal `.plan(...)`:

```python
from factgraph.sdk import (
    ExistsExpectationV1,
    GoalPlanFailureV1,
    GoalPlanRunV1,
    native_deterministic_profile_v1,
)

invocation = (
    fg.query(target, address_space=addresses)
      .bind(person_address, alice_ref)
      .select("age", age_address)
      .plan(
          result_mode="rows",
          expectations=(ExistsExpectationV1("person_is_found", True),),
          profile=native_deterministic_profile_v1(),
      )
)
outcome = invocation.run()
if isinstance(outcome, GoalPlanFailureV1):
    # A resolver/provider/capability failure is typed; it is never a false
    # zero-row answer.
    raise RuntimeError(outcome.code)
assert isinstance(outcome, GoalPlanRunV1)
run = outcome.run
```

`plan()` returns an immutable V1 plan/invocation. `run()` captures the current
admitted relation once, resolves an optional `ScenarioSpecV1`, and produces a
sealed `EvaluationRunV1`; `outcome.replay()` then reads only its captured
inputs. The V1 modes are `"rows"`, `"exists"`, `"count"`, and `"set"`; all
row modes have set semantics, so duplicate proof paths never inflate a count.

Use typed V1 expectations rather than the legacy `.expect_contains(...)`:

- `ContainsRowExpectationV1` over a `GoalRowExpectationV1` of `GoalValueV1`
  values;
- `ExistsExpectationV1`, `CountEqExpectationV1`, and
  `SetEqualsExpectationV1` over the complete normalized row set; and
- `ExactLocalAbsenceExpectationV1` only for the exact closure target created
  by the same Scenario. A zero Query row is not a negative fact.

### Scenario / What-if

`ScenarioSpecV1` is a collection of grounded, typed operations such as
`ScenarioSetEffectiveValueV1`, `ScenarioEnsureMemberV1`,
`ScenarioSetExactMembersV1`, `ScenarioWithoutFieldV1`,
`ScenarioWithoutValueV1`, `ScenarioEnsureRelationV1`,
`ScenarioWithoutRelationV1`, `ScenarioWithoutEntityV1`, and
`ScenarioWithoutAssertionV1`, and `ScenarioCreateEphemeralEntityV1`. Values are expressed as
`ScenarioValueV1(tag, value)` and every operation may carry opaque
`origin_refs`.

The ergonomic form is either `query.plan(scenario=scenario)` or
`query.what_if(scenario).plan()`. Both lead to the same V1 plan; the latter
only freezes the Scenario argument earlier. Scenario resolution is
deterministic, operates on a captured relation, and never writes the ledger.
`EvidenceScopeV1` only removes admitted baseline assertion ids. It is not a
closure declaration and cannot prove absence. Only a `ScenarioWithout*`
operation provides exact local closure for its own explicit target.

### Providers, Policy variants, and portable engines

Rule and Policy are the V1 logical Query targets. Attach a
`RelationProviderV1` to one through `.using(provider)` (or the explicit
`ProviderQueryTargetV1(base, provider)` wrapper); `fg.query(provider)` is
rejected before compilation because a provider has no independent head,
projection or semantic address space. A provider receives a sealed
`ProviderRequestV1`, returns finite typed `ProviderRelationRowV1` values in a
`ProviderMaterializationV1`, and is invoked exactly once before Scenario
resolution and before an engine runs. It replaces only its declared supplied
predicate subset. It is not an arbitrary engine functor: implicit engine-time
network access, untyped outputs, and a claim that FactGraph proved provider
internals are outside the contract. An in-process provider callback is trusted
code, not a sandbox; V1 detects a persistent source-view change across the
callback and fails closed, but cannot undo a malicious write. Use
`provider_binding_slot_v1` to name a provider's required structured Query
binding without introducing a dotted address grammar.

Pass an independently compiled Rule or Policy as `candidate=` to compare it
with the primary target on the same resolved effective world. This is an
immutable comparison, not a Policy mutation or publication operation.

`native_deterministic_profile_v1()` is the zero-config native profile.
`portable_deterministic_profile_v1()` requires the declared positive,
deterministic subset to execute in native, real Soufflé, and real ProbLog with
no fallback. It compares only normalized selected-row sets; it does not claim
that their proof/evidence structures are equivalent. Unsupported syntax or an
unavailable engine yields a typed assessment/frame instead of falling back.

Detached V1 Explain always requires an explicit `ExplainTargetV1` that names
one row or summary anchor. It never chooses a first row implicitly. For an
explicit positive row, a sealed restricted native Explain context is used to
re-execute only the captured relation and verify the sealed result before
returning an `EvidenceGraph` and `EvaluationRunPolicyProjectionV1`. This is
native inner evidence only: portable proof parity remains `not_claimed`.
Summary/zero-row targets have no graph or negative proof; missing context,
ambiguous hidden witnesses and any pin/replay mismatch fail closed. The
captured relation, Scenario resolution, engine pins, and provider receipts are
replayable; ordinary current-store evaluation and the older V0 capture codecs
remain separate contracts.

When a Scenario was explicit, `outcome.scenario_diff` is available without a
second evaluation. It compares only sealed input/world pins and normalized row
sets. A difference is not an EvidenceGraph explanation and is never a causal
attribution to one premise or rule node.

### Engine runtime options

- Public `Rule` and `Inference` objects are engine-independent business
  templates. They do not carry adapter-specific `engine_ext` parameters.
- Public `evaluate(...)` rejects `engine_options=` and `registry=`.
  Runtime-specific semantics are expressed through `config=`.
- Track 2 makes `ProbLogConfig` and `PyReasonConfig` the
  preferred public SDK wrappers for engine-specific semantics.
  `SemanticsProfile` remains the advanced/canonical profile shape.
  Public SDK calls reject `mode=` and `semantics_profile=`; use
  `engine=` and `config=`, or omit `engine=` when it can be derived
  from the semantics object.
- Track 3-post lets `PyReasonConfig.case_bounds` reference branch
  ids from `Case([...], id="...")` or fallback positional ids such as
  `c0` / `c1`. Case-specific bounds override the wrapper's global
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
with vars("u", "nm") as (u, nm):
    rule = build_application_rule(
        id="user:name",
        version="1.0.0",
        where=[
            User(u),
            User(u).name == nm,
        ],
        ports={"user": u, "name": nm},
    )

result = sdk.eval.evaluate(rule, head=rule)
```

Stable contract:
- `Rule.id/version` must be non-empty strings.
- `Rule.ports/where` must be non-empty lists.
- `Rule` is engine-independent public syntax. Adapter-specific rule
  projection is not carried by public `engine_ext` fields.
- `Rule.condition_weights` remains public as certainty/explain
  projection input keyed by `c{case}.c{condition}`. It is not an engine
  adapter parameter and does not enter `where` execution semantics.
  Future runtime configuration for this lane belongs in
  `SemanticsProfile.certainty_projection`.
- Public rule evaluation returns `EvaluateResult`; row-format dispatch was
  removed from the T5 SDK surface.
- `policy=` and display-meta aggregation are not public SDK evaluation inputs.

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
- OR branches: `where=[[...], [...]]` (Inference only — application `Rule` is AND-only)
- `Case` branches: `when=[Case([...], id="seed_path"), Case([...])]` (Inference only)
- linear arithmetic inside comparisons (for example `age == (2026 - by)`, `x * 2`)
- aggregate helpers for the application Rule bridge:
  `agg_count`, `agg_sum`, `agg_min`, `agg_max`, and `agg_mean`

`Case` example:

```python
from factgraph.sdk import Case

where = [
    Case([User(u), Pred("user:lang_pref", u, lang)], id="declared_pref"),
    Case([User(u), Pred("user:inferred_lang", u, lang)]),
]
```

Limits:
- path sugar supports only `==`.
- attr-vs-attr comparisons support only `==`, and require schema-aware compilation.
- non-linear multiplication (`x * y`) is unsupported.
- `where` cannot mix `Case(...)` with bare branches (for example `[Case([...]), [...]]`).
- `Case(...)` accepts the branch atom list plus optional keyword-only structural `id=`.
  Probability, confidence, and engine-specific kwargs are rejected.
- `fg.rules.inspect(rule_or_inference)` exposes explicit branch ids, positional fallback ids (`c0`, `c1`, ...), and atom ids such as `c0.c0`.
- string DSL is unsupported (`sdk.run("...")`, `sdk.eval.evaluate("...")`).

### 3.1 Field Sugar vs `Pred(...)`

For schema-field conditions in `where`, prefer field sugar:

```python
when=[User(u), u.name == nm, u.tag == "vip"]
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

Do not confuse field-to-value sugar with attr-vs-attr comparison. `u1.user_id == u2.user_id` follows cross-coordinate `attr_eq` lowering and only allows the same entity type and the same Identity field.

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

`agg_count(when=[...])` has no target. `agg_sum`, `agg_min`, `agg_max`, and
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

RuleExpr is the application-rule composition surface. Top-level
`factgraph.sdk.Rule` is the application protocol Rule. `ApplicationRule`
remains a transition alias, but new code should import `Rule`:

```python
from factgraph.sdk import Rule, RuleExpr, build_application_rule, vars
```

`factgraph.sdk.Rule` and `factgraph.application.protocol.Rule` are the same
runtime type.

### Building operands

Prefer the bridge for user-facing examples:

```python
from factgraph.sdk import build_application_rule, vars

with vars("u") as (u,):
    active_user = build_application_rule(
        id="active_user",
        when=[User(u), User(u).status == "active"],
        ports={"user": u},
        repr="active user %user",
    )

with vars("u") as (u,):
    assigned_owner = build_application_rule(
        id="assigned_owner",
        when=[User(u), User(u).role == "owner"],
        ports={"user": u},
        repr="assigned owner %user",
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
- `is_closed`
- `unbound_ports`
- `render(bindings=None)`
- `render_compact()`

`OccurrenceInspect.ports` is a tuple of local port name strings. In contrast,
`RuleExprInspect.ports` is a tuple of `PortInspect` descriptors aggregated
across inspected occurrences. For value ports, `value_type="unknown"` means the
current application `PortType` substrate does not carry concrete value type
metadata.

`render()` and `render_compact()` are deterministic authoring narratives. They
do not read the ledger and are not proof explanations.

For application `Rule` inputs, `RuleExprInspect.is_closed` reports whether every
declared head port is bound by the strict closed-head inspect subset, and
`unbound_ports` lists the remaining port names. Value ports close only through a
direct equality to a literal `Const`. Entity-ref ports close only when every
primary identity predicate binds that entity variable to a literal in the
user-authored `head.where`. If schema identity metadata is unavailable, entity
ports are reported unbound. `Rule.projection(...)` heads inspect as closed by
construction. Structural RuleExpr inspect exposes the fields for shape
consistency but does not define closed-head semantics.

### Static RuleStructure

`fg.rules.structure(...)` returns an immutable `RuleStructure` for application
`Rule` and RuleExpr inputs:

```python
rule_structure = fg.rules.structure(active_user)
expr_structure = fg.rules.structure(expr, head=Rule.projection("user"))
```

For RuleExpr inputs, `head=` is required because the lowering plan must know the
result head. The SDK method is a thin shell over application
`assemble_static_structure(...)`.

`RuleStructure` is engine-neutral, read-only derived data. It is not accepted as
authoring input and does not evaluate or derive facts. It carries the authored
inspect floor (`ast`, `occurrences`, `joins`, `ports`, `templates`,
`port_visibility`, `render(...)`, `render_compact()`) and DNF branches with
plan-derived identity keys. Those branch keys line up with explain evidence:
`branch_id` ↔ `EvidenceTree.tree_id`, `occurrence_alias`, `atom_id`, and
`join_id`. Runtime-only fields such as verdicts, certainty, support, and
timestep stay on `EvidenceGraph`, not `RuleStructure`.

`RuleStructure.narrate()` renders the same tree as static prose aligned to
`Explanation.narrate()`. It keeps branch, join, head, and atom identity anchors
but omits runtime verdict/status/probability/context/`produces:` text. Atom
terms are naked variables (`FreeVar`, rendered as `%port` when available) rather
than executed values.

### RuleExpr execution

`fg.eval.evaluate(...)` also accepts application `Rule` and RuleExpr values
when you provide an application `Rule` as `head=`:

```python
result = fg.eval.evaluate(expr, head=active_user, engine="native")
```

The public success shape is `EvaluateResult`. A single application `Rule`
input is treated like a one-rule RuleExpr:

```python
result = fg.eval.evaluate(active_user, head=active_user)
```

For execution, application `Rule` ids that are not valid default occurrence
aliases are internally evaluated with a stable `head` occurrence alias.

The supplied `head=` may be an inline rule occurrence, an external application
head with an ordinary body, or `Rule.projection("port", ...)` for projected
ports. External head bodies are conjoined with each RuleExpr branch. Projection
placeholder atoms are validation-only and are not materialized as filters.

Supported engines are `native`, `souffle`, `problog`, and the current PyReason
pred-only subset. PyReason rejects RuleExpr joins, source non-pred atoms, and
aggregate-containing branches before adapter invocation with `SDKStoreError`
guidance that names the engine, unsupported feature, rejection source, and
known alternative engines.

### Unified resolved Query target (v1)

For new callers, `fg.query(...)` is the compact entry point over the same
compiled Query path. It accepts a semantically resolved Rule bundle, an
advanced Policy plus its exact `SemanticAddressSpace`, or an
`AuthoredPolicyTargetV1` returned by `fg.policy(...).build(...)`:

```python
compiled = (
    fg.query(resolved_rule)
      .bind(SemanticPortAddress("target", "person"),
            EntityRef("Person", {"employee_id": "alice"}))
      .select(
          "age",
          EvaluationQueryFieldNavigationV0(
              base=SemanticPortAddress("target", "person"),
              field=FieldPath("Person", "age"),
          ),
      )
      .compile()
)
result = fg.eval.evaluate(compiled, engine="native")
```

The Rule form deterministically lifts one `target` occurrence into the internal
Policy `__factgraph_rule_lift__:<rule-id>`; it does not make a Rule and Policy
the same authored object. For a direct advanced Policy use
`fg.query(policy, address_space=addresses)`. For an SDK-authored target use
`fg.query(target)` without `address_space=`; its typed handles lower to the
same structured addresses. `bind` accepts only a structured direct address or
a direct typed handle. `select` additionally accepts a typed one-hop field
handle and lowers it to the narrow structured
`EvaluationQueryFieldNavigationV0`: exactly one identity-to-same-entity,
single non-identity scalar-field lookup. The lookup is Query-owned projection
plumbing, not a `PolicyFieldNavigation`; it changes the Query digest but not
Policy structure, lineage, or digest. Missing field evidence produces no row,
never `null` or `false`. The builder delegates all of this to the existing
`EvaluationQuery` compiler. Its sole
result-observation extension is
`expect_contains(expectation_id, /, **selected_values)`: values name existing
selections, are schema-normalized like `bind`, and observe the completed row
set without changing the Policy, query digest, lowering plan or rows. Native
success reports `satisfied` for a matching row and `not_satisfied` for a
complete live enumeration without one. That result-local
`complete_native_enumeration_v0` basis is neither closed-world truth nor an F4
historical completeness claim. `underdetermined` and `unsupported` remain
explicit future-profile states. An expected Query rejects `capture=` and
`scenario=` because current F4/F5A contracts do not seal expectation inventory.

For a durable record of that exact observation, use the separate terminal
capture entrance rather than widening ordinary `evaluate`:

```python
captured = (
    fg.query(resolved_rule)
      .select("age", SemanticPortAddress("target", "age"))
      .expect_contains("alice_age", age=22)
      .capture()
)
assert captured.expectation_results[0].status == "satisfied"
assert captured.verify().matched
detached = type(captured).from_bytes(captured.to_bytes())
evidence = detached.explain(
    row_capture_digest=detached.bundle.rows[0].row_capture_digest,
)
```

`CapturedEvaluationQueryRunV0` wraps — but does not modify — the existing F4
bundle. It seals that bundle, the original targeted-Query wrapper, the ordered
compiled `contains_row` inventory and outcomes; decode, `verify()` and
`explain()` recompute outcomes from captured typed rows. It is digest-sealed,
caller-custodied cleartext rather than authenticated or historical truth. A
`not_satisfied` outcome only describes the captured native enumeration and has
no negative EvidenceGraph: `explain()` accepts a real positive
`row_capture_digest` only. The captured form is native-only and has no
Scenario, config, premise-filter, paging, generic expectation or Operator
surface. Its inventory is bounded to 64 expectations.
It has no string lookup, registry, Package, generic `expect`, modes,
empty-select existence, relationship/multi-hop traversal, Operator, or
non-native configuration surface. Navigation is not accepted in `bind` or
Policy authoring. Ordinary capture/evidence remains the existing F4 path;
the Run anchor records whether its source was a direct Policy or a Rule lift.

A direct Policy may itself contain the narrow application-level
`PolicyCompare` constraint. Its operands are direct scalar
`SemanticPortAddress` values, a structured `PolicyFieldNavigation` from an
identity port to one scalar field, or a canonical `PolicyLiteral("int" |
"time", value)` paired with one semantic scalar operand. That navigation is
compiled and evidenced as Policy-owned lookup/compare conditions; it is not
accepted by `.bind(...)` or `.select(...)`. The SDK draft façade is preferred
for new caller code. See `src/factgraph/application/docs/rule.md` for the
exact schema, branch-total, literal, and cross-engine limits.

`builder.evaluate(scenario=...)` forwards either the existing narrow
`ScenarioFieldSubstitutionV0(...)` operation or the atomic
`ScenarioFieldSubstitutionSetV0((...))` form. Both retain the no-anchor,
no-bundle, no-live-Explain boundary.

### Low-level compiled EvaluationQuery execution (v0)

The initial Policy-query bridge accepts an application-compiled
`CompiledEvaluationQueryV0` on the same result surface:

```python
result = fg.eval.evaluate(compiled_query, engine="native")
for row in result:
    print(row.bindings)       # ordered named selections
    explanation = row.explain()
```

The SDK executes the exact compiler-issued plan and returns `EvaluateResult`;
it does not expose the intermediate `DerivationOutput`. No `head=` is needed because
the artifact already contains its synthetic projection head. Bindings constrain
engine truth and selections only project, so a non-matching bind returns an
empty result rather than a failed/false claim.

This v0 execution path is deliberately native-only and rejects `config=`,
`evaluate_candidates(compiled_query)` and standalone
`eval.explain(compiled_query, ...)`. `row.close()` and `row.explain()` are live
helpers: they fail closed if the FactGraph view has changed since evaluation.
Premise exclusions, allowances and predicate blocks are not yet captured with
that live view, so a non-empty or later-changed premise policy also fails closed.
Each ordinary successful compiled Query result carries `result.run_anchor`, a pure-data
identity anchor for the exact target, Query, Policy structure/lineage, Rule
pins, direct/navigation bind/select intent, execution profile, view, result
and rows. Its semantic
row anchors exclude random run ids; its query-summary anchor also covers a
zero-row result without interpreting it as false. `row.explain()` includes the
Run anchor digest in `checked_scope`.

The anchor explicitly reports identity-only capture, digest-only live-view
guarding and replay unavailable. By default it contains no detached snapshot
or support material. A native compiled Query may opt in atomically:

```python
from factgraph.application import (
    evaluation_run_bundle_bytes,
    evaluation_run_bundle_from_bytes,
)

result = fg.eval.evaluate(compiled_query, capture="run_bundle_v0")
assert result.run_bundle is not None
payload = evaluation_run_bundle_bytes(result.run_bundle)
detached_bundle = evaluation_run_bundle_from_bytes(payload)
```

The bounded canonical bundle contains the exact native plan, schema, Query
values, dependency-complete effective relation, typed rows, F4A anchor and
canonical ProofReceipts. It is sensitive cleartext under caller-managed
custody, with unverified authenticity. Decode and inspection do not consult the
Store, but the artifact deliberately has no `replay()` or detached `explain()`
method and reports replay not implemented. Non-fact logical verification,
historical replay, persistence, completeness, truncation and expectation
semantics remain later slices.

#### Narrow scenario field substitution (v0)

`scenario=` adds one deliberately narrow, read-only What-if form to the same
compiled Query call surface.  It substitutes one visible, single-valued,
non-identity scalar field for one existing entity in the exact Query dependency
relation, then evaluates both the unchanged and effective relations:

```python
from factgraph.sdk import EntityRef, FieldPath, ScenarioFieldSubstitutionV0

result = fg.eval.evaluate(
    compiled_query,
    scenario=ScenarioFieldSubstitutionV0(
        entity=EntityRef("Person", {"employee_id": "alice"}),
        field=FieldPath("Person", "age"),
        value=22,
        premise_id="review-age-hypothesis",
    ),
)

assert result.scenario is not None
print(result.scenario.result_diff)
```

This is not a general Scenario, claim overlay, rule override, persistence, or
replay API.  The field must be schema-owned and directly relevant to the
compiled Query; the entity must already be active and visible; and exactly one
visible fact for that field must exist.  All other shapes fail closed.
An ordinary scalar `time` value is allowed, but temporal/as-of/versioned and
historical-fact semantics are not part of this v0 contract.

Scenario execution is native-only, rejects `config=`, non-empty premise policy,
and **any** `capture=` argument (including `capture=None`).  It intentionally
does not attach a Run anchor or bundle.  Its rows cannot be closed and their
explanations are reported unsupported: the current evidence model would
otherwise make a hypothetical value look like a ledger fact.  The returned
`result.scenario` records the canonical operation, base/effective relation
identities, and a semantic result diff.  Its effective-view digest identifies
the scenario relation; it is not a historical ledger snapshot.

#### Atomic scenario field-substitution set (v0)

`ScenarioFieldSubstitutionSetV0` groups at least two of the same direct scalar
field substitutions into one atomic hypothetical relation:

```python
from factgraph.sdk import ScenarioFieldSubstitutionSetV0

scenario = ScenarioFieldSubstitutionSetV0((
    ScenarioFieldSubstitutionV0(EntityRef("Person", {"employee_id": "alice"}), FieldPath("Person", "age"), 35, "alice-age"),
    ScenarioFieldSubstitutionV0(EntityRef("Person", {"employee_id": "bob"}), FieldPath("Person", "score"), 11, "bob-score"),
))
result = builder.evaluate(scenario=scenario)
```

FactGraph resolves every member against one dependency-complete baseline before
either native evaluation, rejects any invalid member or duplicate canonical
`(entity_ref, field)` target, and then evaluates the baseline and complete
effective relation exactly once each. Input order does not change the
resolution identity. This remains a replacement-only Scenario—not a general
What-if, fact overlay, rule/policy override, source claim, or replay surface.
The same `capture=`, expectation, anchor, bundle, `close()`, and live
`explain()` exclusions apply.

### Captured replacement-only ScenarioRun (v0)

The non-captured `builder.evaluate(scenario=...)` compatibility route above is
not the audit surface. Use the terminal Query builder when a caller needs a
sealed, detached baseline/effective record:

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

assert run.verify().matched
diff = run.diff()
evidence = run.explain(
    side="effective",
    row_capture_digest=run.effective.rows[0].row_capture_digest,
)
```

`ScenarioRunV0` runs the exact same materialized native Query plan once over
the frozen baseline relation and once over the atomic effective replacement
relation. It captures receipts without writing the Store support sidecar or
candidate indexes. `run.to_bytes()` / `ScenarioRunV0.from_bytes(...)` preserve
a strict bounded record which can be inspected, explained and verified without
a live Store. Detached Explain projects the captured row through the authored
Policy tree; its source metadata explicitly distinguishes
`captured_baseline_relation_witness`, `captured_effective_relation_witness`,
and `scenario_hypothesis`.

The captures contain typed cleartext under caller-managed custody and are only
digest-sealed, not authenticated. They do not prove premise truth, ledger
authority or a historical replay. This v0 remains native-only and accepts only
the existing Q7/Q11 scalar replacement forms: no expectations, config,
premise filters, add/delete/mask, Policy overlay, Operator/action, as-of time,
or general Scenario language.

### Rule and RuleExpr snapshot matching

`fg.entities.match(EntityCls, template, **port_constraints)` is the read-side
runtime for application rules. It returns distinct snapshots of `EntityCls`
selected by a `Rule` or `RuleExpr`.

```python
users = fg.entities.match(User, user_region, region="US")
```

The runtime resolves the projected entity from exactly one entity-ref port of
the requested class. Entity-ref constraints accept either an `idref_v1` token
or an `EntitySnapshot`; value constraints use ordinary Python values. A value
constraint may also reference a field descriptor on the projected entity class:

```python
same_region = fg.entities.match(User, user_region, region=User.region)
```

OR `RuleExpr` works when each branch exposes the same constrained ports:

```python
users = fg.entities.match(User, tagged_users | regional_users, marker="US")
```

The runtime distributes constraints into each OR branch, unions branch results,
and returns each projected snapshot once.

Runtime limits:

- `Rule` and `RuleExpr` (`&` / `RuleExpr.all(...)`, `|` /
  `RuleExpr.any(...)`) are supported.
- Ports constrained by kwargs must be declared in every OR branch.
- Result rows are snapshots, not witness assertions or `EvaluateResult` rows.
- Method-level `view=` is rejected; attach a durable Database view and call
  `fg.entities.match(...)` on the attached runtime.

## 4. RuleRef and Dependency Registration

Construction:

```python
RuleRef("q_x", version="1.0.0")
RuleRef(existing_rule_obj)
```

Rules:
- RuleRef target must be `expose=True`, otherwise runtime `RuleCompileError`.
- `RuleRef` is forbidden inside `Not(...)` body (compile-time error).
- `fg.eval.evaluate(...)` auto-registers `RuleRef(RuleObj)` dependencies for
  in-memory rule values.
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

my_rule = Rule(id="rule_alice", when=[...], ports={"x": x})
rule_result = fg.eval.evaluate(my_rule)

my_inference = Inference(id="drv.copy_name", version="1.0.0", when=[...], head=...)
result = fg.eval.evaluate(my_inference)
```

`fg.rules.inspect(rule_or_inference)` is the only remaining structural inspection
API on the `fg.rules.*` namespace.

When the graph is workspace-backed, factual and schema writes are durable when
their calls return. `fg.save_workspace()` only touches lifecycle metadata;
`FactGraph.load_workspace("./workspace", schema_classes=[User])` opens the
durable Database. User code constructs Rule/Inference values in memory afresh
each session.

## 5. Query DSL

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    q = Query(
        head=[User(u), User.name(locale=loc, name=nm)],
        when=[User(u), u.locale == loc, u.name == nm],
        on_missing="error",
        on_type_mismatch="error",
    )

snapshot_rows = sdk.read.find(User)
```

Stable contract:
- Query remains importable as a legacy DSL value object for internal tests and
  future read-projection work.
- T5 public runtime does not expose `sdk.run(...)`; use `sdk.read.find(...)`
  for simple snapshot reads, `sdk.read.match(...)` for application-rule
  snapshot reads, or `sdk.eval.evaluate(Rule(...))` for replay-anchored rule
  evaluation.

## 6. Inference DSL

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    inf = Inference(
        id="drv.copy_name",
        version="1.0.0",
        when=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

result = sdk.eval.evaluate(inf, engine="native")
row = result.first()
if row is not None:
    explanation = row.explain()
```

Fields:
- required: `id`, `version`, `when`
- optional: `head`, `emits`, `status`, `description`, `tags`

Stable contract:
- `head` shape infers candidate kind (fact/entity).
- Public SDK `Inference` is single-head. Multi-head (`head=[H1, H2, ...]`) is rejected in Track 1; define one inference per head.
- `Inference.when` supports `Case(...)`; it unwraps to normalized OR-branch structure. Application `Rule.when` is AND-only (use `RuleExpr` `&` / `|` for multi-rule composition).
- `sdk.run(inference)` was removed; use `sdk.eval.evaluate(...)`.

## 7. Compile-Time Hard Constraints (v2)

### 7.1 `head` and primary key

- Any primary-key field in `head` -> compile error.
- Missing entity binding in `where` for implicit primary-key carry -> compile error.
- Multiple same-type bindings in `where` that cannot be disambiguated -> compile error.

### 7.2 Cross-coordinate attr comparison

`u1.user_id == u2.user_id` is legal only when:
- both sides are the same entity type
- both sides use the same field
- that field is an Identity field

Otherwise, compilation fails (no implicit guessing).

### 7.3 Lowering shape

Valid cross-coordinate Identity comparison is lowered to shared system vars (`$__identity_N`):

```python
("pred", "user:user_id", ["$u1", "$__identity_0"])
("pred", "user:user_id", ["$u2", "$__identity_0"])
```

System-prefixed temporary names are reserved.

## 8. `evaluate` Runtime Semantics

### 8.1 `sdk.eval.evaluate(...)`

```python
result = sdk.eval.evaluate(inf, engine="native")
```

- `engine`: `native` (default) / `souffle` / `problog` / `pyreason`.
- SDK lowers `Inference` DSL objects into compiled plans, then delegates orchestration to application `evaluate_derivation_plans(...)`; SDK returns the T5 `EvaluateResult` envelope.
- Legacy `mode='python'` / `mode='engine'` **values** fail with explicit rename hints (use `mode='native'` / `mode='souffle'` respectively); enforced at `factgraph/core/store/_evaluate.py:50,52`.
- `souffle` / `problog` / `pyreason` require registered adapters (for example `import factgraph.adapters.souffle`, `import factgraph.adapters.problog`, `import factgraph.adapters.pyreason`).
- `sdk.eval.evaluate(..., view=...)` and `sdk.eval.evaluate(..., policy=...)` are
  not supported; inference always uses the full active assertion set.
- `engine_options=` and `registry=` are rejected at the public boundary.
- RuleExpr execution uses the same public entrypoint as inference evaluation:
  `sdk.eval.evaluate(expr, head=application_rule, engine=...)` returns
  `EvaluateResult`. `head=` is required and must be an application `Rule`;
  legacy SDK `Rule` / `Inference` objects are rejected as heads.

### 8.2 `EvaluateResult` key fields

- `result_id` identifies the evaluation envelope.
- `fingerprint.run_id` and `fingerprint.result_digest` identify the concrete
  run and content-addressed result.
- `fingerprint.expr_digest`, `fingerprint.rule_set_digest`,
  `fingerprint.view_snapshot_digest`, and `fingerprint.config_digest` are
  replay anchors.
- `engine_meta["engine_version"]` and `engine_meta["adapter_version"]` carry
  optional engine provenance.
- `rows` is a tuple-like sequence of `EvaluateRow` values.
- Each row exposes `bindings`, `claim`, `raw_kind`, `bound`, and an
  row-owned evidence fields.
- `row.explain()` returns an `Explanation`.
- `row.close()` returns a closed application `Rule` that can be passed to
  `fg.eval.explain(expr, head=closed_head, ...)`.

`DerivationOutput` is the canonical internal engine-output artifact. The legacy
`CandidateSet` name remains a direct alias for materialization and wire
compatibility. Public code should use `EvaluateResult`, `EvaluateRow`,
`row.explain()`, and `row.close()`.

`evaluate_candidates(...)` is a temporary cross-repository compatibility seam
for shipped Meander consumers, not the target SDK design. It remains read-only,
does not accept `CompiledEvaluationQueryV0`, and should not be adopted by new
callers. Its removal requires a coordinated Meander migration.

For the full envelope chain (`EvaluateResult` direct fields plus
`ResultFingerprint` / `engine_meta`, `EvaluateRow` data + methods,
row digest / closed-head digest invariants, `Explanation` status / failure_class enum values,
and runnable passed / failed examples), see
[`docs/official/kernel/quickstart/evidence.md`](../../../../docs/official/kernel/quickstart/evidence.md).

## 9. Temporal Boundary (Current Status)

Implemented:
- Read-side temporal filtering via `snapshot.assertions.<field>.at(t)` and
  canonical `_meta={"version": v}` metadata filters, plus `AssertionRecordSet`
  filters such as `snapshot.assertions.field(...).all.at(t)`.
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
- `sdk.eval.evaluate(..., temporal_view=...)` raises `SDKStoreError`.

## 10. Minimal End-to-End Examples

### 10.1 Fact candidate

```python
with vars("u", "loc", "nm") as (u, loc, nm):
    inf = Inference(
        id="drv.alias",
        version="1.0.0",
        when=[User(u), u.locale == loc, u.name == nm],
        head=User.name(locale=loc, name=nm),
    )

result = sdk.eval.evaluate(inf)
row = result.first()
assert row is not None
explanation = row.explain()
```

### 10.2 Entity candidate + dependent facts

```python
with vars("u", "lang") as (u, lang):
    inf = Inference(
        id="drv.speaks",
        version="1.0.0",
        when=[User(u), Pred("user:lang_pref", u, lang)],
        head=Speaks(user=u, language=lang),
    )

result = sdk.eval.evaluate(inf)
for row in result:
    closed = row.close()
    replay = sdk.eval.explain(inf, head=closed)
```
