# Application Rule DTO

`factgraph.application.protocol.Rule` is the application-layer Rule DTO
introduced for the rule-expression redesign. It is intentionally below the SDK
surface: SDK authoring remains responsible for ergonomic Python syntax and for
lowering user-facing DSL objects into application protocol objects.

## Shape

The DTO has five fields:

- `id`: stable non-empty rule id.
- `where`: non-empty tuple of core AST atoms from
  `factgraph.core.rules.where_ast`.
- `ports`: explicit mapping from public port names to core `Var` objects.
- `version`: optional non-empty version string.
- `desc`: optional description template using `%port_name` interpolation.

The accepted `where` atoms are `PredAtom`, `CmpAtom`, `InAtom`, `BuiltinAtom`,
and `NotAtom`. `RuleRefAtom` is rejected because the new paradigm composes
Rules through RuleExpr and port joins, not through rule-reference atoms.

## Layer Boundary

This DTO does not accept SDK DSL objects such as `LogicVar`, `ExistsAtom`,
`AttrRef`, or `CompareExpr`. The dependency direction stays:

```text
sdk -> application -> core
```

The SDK owns ergonomic authoring syntax such as `User(u).field == value`
and lowers that syntax into the core AST shape consumed here through
`factgraph.sdk.dsl.build_application_rule(...)`.

## Validation

Construction validates the DTO shape:

- `id`, optional `version`, and optional `desc` are non-empty strings.
- `where` is a non-empty tuple.
- `ports` is a non-empty mapping from string names to core `Var` objects.
- Every port variable appears somewhere in `where`.
- `desc` may only reference declared ports.
- Unsupported atom kinds raise `RuleValidationError`.

The DTO provides positional `atom_ids` using `<rule_id>:atom_<index>`, a
deterministic `content_digest`, shallow container immutability, and
`render_desc(...)` for template rendering.

## Unified Syntax via SDK DSL Bridge

Use `factgraph.sdk.dsl.build_application_rule(...)` when starting from SDK DSL
objects:

```python
from factgraph.sdk.dsl import build_application_rule, vars

with vars("u") as (u,):
    rule = build_application_rule(
        id="active_user",
        where=[User(u).status == "active"],
        ports={"user": u},
        desc="active user %user",
    )
```

T1.2 supports six equality-only / bare-existence forms:

- `User(u)`
- `User(u).user_id == "u-2"`
- `User(u).status == "active"`
- `User(...).name == "alice"`
- `LivesIn(li).user == User(u)`
- `LivesIn(li).country == country`

The bridge emits the required `EntityType:exists` predicate for unified field
syntax, including cross-entity references such as
`LivesIn(li).user == User(u)`.

## Internal Aggregate Terms

The application DTO can store core `AggregateAtom` values in comparison or
arithmetic term position. Direct application-rule construction may use the core
AST shape. SDK authors should prefer the aggregate helpers exposed from
`factgraph.sdk.dsl` (`agg_count`, `agg_sum`, `agg_min`, `agg_max`, `agg_mean`)
through `build_application_rule(...)`.

Aggregate terms do not extend the top-level atom allowlist. `AggregateAtom`
stays value-producing and must be wrapped by an enclosing comparison or
arithmetic atom. Port validation treats aggregate target variables as visible,
keeps aggregate-filter-local variables private, and rejects ports that reference
only aggregate-local filter variables.

Adapter status: the Python evaluator and the Souffle adapter both support
aggregate terms (Souffle aggregate body wire shipped in T2.3c). For Souffle,
`count` and `sum` use native empty-set behavior (empty = 0, matching C101
legal values); `min`/`max`/`mean` emit a `count : { same_body } > 0` guard
clause so an empty body suppresses the rule branch (matching C101
AggregateNoValue "comparison violated / no env pollution" semantics — no
separate sentinel value). ProbLog adapter projection (`findall/3` + list
predicates) remains deferred to T2.3.d. PyReason aggregates are out of
scope per parent essay §10.6.3.

## Bridge Rejections

The new application Rule path rejects legacy SDK authoring forms that are still
accepted by the legacy SDK Rule surface:

- bare attribute comparisons such as `u.status == "active"`
- two-line legacy forms such as `User(u), u.status == "active"`
- raw `Pred(...)` atoms
- raw rule-reference atoms
- OR-shaped where bodies
- anonymous `User(...)` variables declared as public ports

## Immutability

`Rule` is a frozen dataclass and stores `where` as a tuple and `ports` as a
mapping proxy. This is shallow/container immutability. Core AST atoms currently
contain mutable list fields such as `PredAtom.terms`; this DTO does not
deep-freeze or clone those shipped core types.
