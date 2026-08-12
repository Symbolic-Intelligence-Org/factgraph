# Application Rule DTO

`factgraph.application.protocol.Rule` is the application-layer Rule DTO
introduced for the rule-expression redesign. It is intentionally below the SDK
surface: SDK authoring remains responsible for ergonomic Python syntax and for
lowering user-facing DSL objects into application protocol objects.

## Shape

The DTO has five fields:

- `id`: stable non-empty rule id.
- `when`: non-empty tuple of core AST atoms from
  `factgraph.core.rules.where_ast`.
- `ports`: explicit mapping from public port names to core `Var` objects.
- `version`: optional non-empty version string.
- `repr`: optional representation template using `%port_name` interpolation.

The accepted `when` atoms are `PredAtom`, `CmpAtom`, `InAtom`, `BuiltinAtom`,
and `NotAtom`. `RuleRefAtom` is rejected because the new paradigm composes
Rules through RuleExpr and port joins, not through rule-reference atoms.
(`AggregateAtom` is a Term, not an Atom, and may only appear nested inside
`CmpAtom` left/right-hand sides — see "Internal Aggregate Terms" below.)

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

- `id`, optional `version`, and optional `repr` are non-empty strings.
- `when` is a non-empty tuple.
- `ports` is a non-empty mapping from string names to core `Var` objects.
- Every port variable appears somewhere in `when`.
- `repr` may only reference declared ports.
- Unsupported atom kinds raise `RuleValidationError`.

The DTO provides positional `atom_ids` using `<rule_id>:atom_<index>`, a
deterministic `content_digest`, shallow container immutability, and
`render_repr(...)` for template rendering.

## Ports and Occurrence Aliases

`ports` is the Rule's explicit public interface. Port keys are public names;
the internal core `Var.name` values are implementation details and do not define
cross-Rule alignment.

T1.4 adds a small occurrence substrate for future RuleExpr joins:

```python
occ = rule.as_("a")
user_port = occ.port("user")
same_user_port = occ.user
```

`rule.as_()` defaults the occurrence alias to `rule.id`; the alias must match
`[A-Za-z][A-Za-z0-9_]*`. If `rule.id` is not identifier-shaped, call
`rule.as_("custom_alias")` explicitly. `RuleOccurrence` and `RulePortRef` are
frozen value objects. They do not compose, join, or evaluate Rules by
themselves; RuleExpr owns those expression-level semantics.

T3 adds the initial RuleExpr authoring and inspect surface. Application `Rule`
objects can compose with `&` and `|`, and `RuleExpr.all(...)` /
`RuleExpr.any(...)` provide factory equivalents. Python boolean contexts are
intentionally rejected for application `Rule` and RuleExpr values; use explicit
`&` / `|` composition instead of `and` / `or`. Joins are explicit:
`a.user.eq(b.user)` constructs a `RuleJoinConstraint`, `(a & b).join(...)`
attaches it to an AND group, and `(a & b).join_by_ports("user")` expands an
explicit port name into pairwise joins. Same-name ports are not auto-joined;
`fg.rules.inspect(expr).unjoined_same_name_ports` exposes discoverability hints.
`fg.rules.inspect(application_rule)` and `fg.rules.inspect(rule_expr)` return a
`RuleExprInspect` authoring projection, while legacy SDK `Rule` / `Inference`
inputs keep their existing dict inspect shape.

Public execution is exposed through the SDK layer, not this protocol module:
`fg.eval.evaluate(rule_expr, head=application_rule, engine=...)` returns an
`EvaluateResult` envelope (per T5 hard-cut). The head may be an inline
application `Rule`, an external application `Rule`, or
`Rule.projection("port", ...)`; the protocol layer supplies the frozen Rule and
RuleExpr values while SDK evaluation owns execution. `fg.rules.inspect(rule)`
returns a `RuleExprInspect` value with closed-head fields for application Rule
inputs; structural RuleExpr inspect does not define closed-head semantics.

## Unified Syntax via SDK DSL Bridge

Use `factgraph.sdk.dsl.build_application_rule(...)` when starting from SDK DSL
objects:

```python
from factgraph.sdk.dsl import build_application_rule, vars

with vars("u") as (u,):
    rule = build_application_rule(
        id="active_user",
        when=[User(u).status == "active"],
        ports={"user": u},
        repr="active user %user",
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

Adapter status: the Python evaluator, Souffle adapter, and ProbLog adapter
support aggregate terms. Souffle `min`/`max`/`mean` emit a
`count : { same_body } > 0` guard so an empty body suppresses the rule branch.
ProbLog lowers aggregates through `findall/3` plus `library(lists)` predicates;
`min`/`max`/`mean` use `L = [_|_]` before list reduction. Both adapter paths
match C101 AggregateNoValue "comparison violated / no env pollution" semantics
without exposing a separate sentinel value. PyReason aggregates are out of
scope per parent essay §10.6.3.

## Managed Semantic Ports

Application Rules remain unchanged and executable without semantic metadata.
Consumers that need stable Ontology addressing can separately resolve every
public Rule port:

```python
from factgraph.application import build_resolved_rule, build_schema_index
from factgraph.application.protocol import (
    SemanticRulePort,
    entity_identity,
    field_endpoint,
)
from factgraph.core.rules.where_ast import PredAtom, Var

person, age = Var("$person"), Var("$age")
resolved = build_resolved_rule(
    id="person_age",
    when=(
        PredAtom("Person:exists", [person]),
        PredAtom("person:age", [person, age]),
    ),
    ports={
        "person": SemanticRulePort(person, entity_identity("Person")),
        "age": SemanticRulePort(age, field_endpoint("Person", "age")),
    },
    schema_index=build_schema_index(schema_ir),
)
```

Each mapping entry carries three coordinates: its logical port name, exact
internal Rule `Var`, and canonical endpoint. `resolved.rule` is an ordinary
Rule whose ports are still Vars. `resolved.contract` is a copied and frozen
in-process binding to that Rule content and the trusted `SchemaIndex` digest.

Resolution requires exact coverage of `Rule.ports`. Entity identity endpoints
need a top-level positive unary entity-exists predicate; scalar field endpoints
need a top-level positive binary field predicate with the port Var in value
position. Negative and aggregate-local predicates are not witnesses. Different
Vars may target the same endpoint and remain distinct—resolution never inserts
equality or a join.

The managed subset currently supports complete entity identities and scalar
fields only. Entity-reference fields, relationships, derived/intermediate
ports, partial semantic coverage, and automatic endpoint inference are not
supported. A legacy Rule using those forms is still valid; it simply cannot
receive this semantic contract.

The contract has one conservative digest over typed Rule, whole-schema, Var,
and endpoint coordinates. Any schema-digest change invalidates it. It is not a
persisted or externally authenticated contract, and this module does not
rebuild Schema IR, verify untrusted rehydration, or define endpoint-local
compatibility. `assert_rule_contract_current(...)` only detects subsequent
in-process Rule drift.

The application layer accepts symbolic endpoints, not SDK Entity classes or
Field descriptors. A future SDK adapter may let authors write
`endpoint=Person` or `endpoint=Person.age`, but must immediately lower those
values to `EntityIdentityEndpoint("Person")` or
`FieldEndpoint(FieldPath("Person", "age"))` before calling this layer. That
ergonomic API is not shipped in F1-lite.

## Managed Occurrences And Direct-Port Addresses

A resolved Rule can be used more than once without losing its semantic
contract. Each use receives an authored alias and therefore a distinct direct-
port address:

```python
from factgraph.application import SemanticAddressSpace, manage_rule_occurrence
from factgraph.application.protocol import SemanticPortAddress

pair1 = manage_rule_occurrence(resolved, "pair1")
pair2 = manage_rule_occurrence(resolved, "pair2")
addresses = SemanticAddressSpace((pair1, pair2))

person = addresses.resolve(
    SemanticPortAddress(occurrence_alias="pair1", port_name="person")
)
```

`person.execution_ref` is the existing RuleExpr `RulePortRef` created from the
stored occurrence. `person.endpoint` and `person.semantic_contract_digest` come
from that occurrence's exact F1-lite contract. The resolved value is a private
runtime carrier, not a publicly constructible protocol DTO: callers provide
only the structured address and cannot submit an execution ref for decoration.

The canonical address is the structured pair `(occurrence_alias, port_name)`.
It is not a dotted string: current Rule port names may themselves contain dots,
so parsing `"pair.person"` would need a future identifier/escaping contract.
Lowered aliases created for DNF branches are compiler-private and never become
authored addresses.

The address space copies, sorts, and freezes its occurrence collection. Its
derived digest binds every authored alias to the exact Rule and semantic-
contract digests. Input order is irrelevant, while renaming an alias changes
the address-space identity. Construction and resolution repeat the lightweight
Rule/contract staleness check.

This is only the direct-port addressing substrate. It does not implement a
Policy AST, Boolean composition, joins, field navigation, Query `bind/select`,
synthetic projection heads, Evaluate, Explain, persistence, or an SDK/Agent
wire format. Existing Rule and RuleExpr callers do not need a semantic address
space and remain unchanged.

## Bridge Rejections

The new application Rule path rejects legacy SDK authoring forms that are still
accepted by the legacy SDK Rule surface:

- bare attribute comparisons such as `u.status == "active"`
- two-line legacy forms such as `User(u), u.status == "active"`
- raw `Pred(...)` atoms
- raw rule-reference atoms
- OR-shaped when bodies
- anonymous `User(...)` variables declared as public ports

## Immutability

`Rule` is a frozen dataclass and stores `when` as a tuple and `ports` as a
mapping proxy. This is shallow/container immutability. Core AST atoms currently
contain mutable list fields such as `PredAtom.terms`; this DTO does not
deep-freeze or clone those shipped core types.
