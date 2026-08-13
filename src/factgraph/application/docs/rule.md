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

Existing Rule and RuleExpr callers do not need a semantic address space and
remain unchanged.

## Managed Policy v0

The application layer now has a deliberately narrow, head-independent Policy
compiler. A Policy names the occurrences in one exact `SemanticAddressSpace`,
combines them with `PolicyAll` / `PolicyAny`, and may explicitly equate two
direct semantic ports with `PolicyUnify` or compare trusted scalar values with
`PolicyCompare`:

```python
from factgraph.application import compile_policy
from factgraph.application.protocol import (
    Policy,
    PolicyAll,
    PolicyOccurrence,
    PolicyUnify,
    SemanticPortAddress,
)

policy = Policy(
    id="same_age",
    version="1",
    when=PolicyAll(
        (
            PolicyOccurrence("person1"),
            PolicyOccurrence("person2"),
            PolicyUnify(
                SemanticPortAddress("person1", "age"),
                SemanticPortAddress("person2", "age"),
            ),
        )
    ),
)
compiled = compile_policy(policy, address_space=addresses)
```

Policy occurrence aliases must exactly cover the address space; unused or
ambient Rules are rejected. Each occurrence appears once, although the same
Rule may be reused under different aliases. All contracts must pin the same
schema digest and still match their Rules when compilation starts.

`PolicyUnify` is equality-only. Its addresses must resolve to the exact same
semantic endpoint on two different occurrences, and it must be scoped directly
inside a `PolicyAll` whose every local DNF branch contains both endpoints. Thus
`a AND (b OR c)` with a Unify between `a` and `b` fails with
`PARTIAL_BRANCH_CONSTRAINT`; placing the Unify inside an explicit
`PolicyAll(a, b, ...)` branch is accepted. This rule applies only to managed
Policy. The existing RuleExpr partial-join lowering remains unchanged.

### Direct comparison and one-hop field navigation

`PolicyCompare` is a direct `PolicyAll` constraint, never a dotted Query path
or a new Rule. Its operands are either direct scalar field addresses or a
strict identity-to-field navigation:

```python
from factgraph.application.protocol import (
    FieldPath,
    PolicyCompare,
    PolicyFieldNavigation,
    SemanticPortAddress,
)

older_age = PolicyFieldNavigation(
    SemanticPortAddress("older", "person"), FieldPath("Person", "age")
)
younger_age = PolicyFieldNavigation(
    SemanticPortAddress("younger", "person"), FieldPath("Person", "age")
)
older_than = PolicyCompare.gt(older_age, younger_age)
```

Compilation requires the same trusted `SchemaIndex` as the managed address
space. Direct operands must be `single` scalar Field endpoints; navigation
starts at an EntityIdentity endpoint and can reach only one known scalar field
of that same entity type. Both sides must have the same scalar domain.
`eq`/`ne` canonicalize operand order; native ordering is deliberately limited
to `int` and `time`. Entity references, multi-value fields, literals,
relationships and multi-hop paths are rejected from Policy logic. The separate
select-side Query navigation described below is not a Policy condition and
never changes a Policy's identity, structure, lineage, or evidence ownership.

Like `PolicyUnify`, a compare is branch-total in its owning `PolicyAll`.
Placing it inside the appropriate branch of `PolicyAny` is valid; placing it
outside a branch where an operand is absent fails with
`PARTIAL_BRANCH_CONSTRAINT` before lowering.

Compilation accepts only managed Rules whose top-level bodies contain
`PredAtom` with ordinary Var/Const terms and non-aggregate
`CmpAtom(eq/ne/gt/ge/lt/le)`. `NotAtom`, `InAtom`,
`BuiltinAtom`, aggregate terms, stale contracts, mixed schema digests, and
compiler-reserved Rule IDs fail with typed `PolicyError` codes. DNF expansion
is checked statically: at most 32 branches compile and larger projections fail
before structural lowering or engine execution.

`CompiledPolicyV0` pins Policy, address-space, Rule, and semantic-contract
identity. It captures canonical `PolicyStructureV0` directly from authored
`Policy.when` before lowering, including the root, nested All/Any children,
occurrence aliases, Unify endpoints, and Compare operands. The Policy digest seals that structure,
the deterministic branch inventory and bidirectional structural lineage.
DNF-generated aliases retain their authored occurrence alias explicitly;
neither structure nor lineage parses generated names or `repr`. Lineage covers
each authored node and every emitted branch, occurrence, Rule-body atom, Unify
coordinate, and compiler-owned Compare condition. Compare conditions are
sealed separately from reusable Rule bodies. Within a materialized branch the
fixed order is Rule bodies, Policy-owned conditions (including any Policy
navigation lookup), Query bindings, Query-owned navigation lookups, Unify
atoms, then synthetic projection-head links.

This artifact is intentionally not executable by itself. It has no result
head, bindings, assumptions, engine configuration, rows, or explanation. The
following `EvaluationQuery` compiler may attach typed bindings and a synthetic
projection head; execution still remains a later slice.

## EvaluationQuery v0 projection

`EvaluationQuery` describes exact Policy-owned direct-port bindings and ordered
named selections. A selection is either one direct semantic port or one
Query-owned, one-hop identity-to-scalar-field navigation:

```python
from factgraph.application import compile_evaluation_query
from factgraph.application.protocol import (
    EntityRef,
    EvaluationQuery,
    EvaluationQueryBinding,
    EvaluationQueryFieldNavigationV0,
    EvaluationQueryNavigationSelectionV0,
    EvaluationQuerySelection,
    FieldPath,
    SemanticPortAddress,
)

query = EvaluationQuery(
    policy_digest=compiled.policy_digest,
    bindings=(
        EvaluationQueryBinding(
            SemanticPortAddress("person1", "person"),
            EntityRef("Person", {"employee_id": "alice"}),
        ),
    ),
    selections=(
        EvaluationQuerySelection("other", SemanticPortAddress("person2", "person")),
        EvaluationQueryNavigationSelectionV0(
            "other_age",
            EvaluationQueryFieldNavigationV0(
                base=SemanticPortAddress("person2", "person"),
                field=FieldPath("Person", "age"),
            ),
        ),
    ),
)
compiled_query = compile_evaluation_query(
    query,
    compiled_policy=compiled,
    address_space=addresses,
    schema_index=schema_index,
)
```

`bind` is compiled into a typed equality inside every DNF branch; it is not an
assertion, write, or post-filter. A direct `select` maps an output alias to one
exact occurrence port. A navigation `select` maps it to one compiler-owned
field lookup whose base is an identity port and whose field is a same-entity,
single, non-identity scalar. Both direct sources and navigation bases must
exist in every Policy branch. Branch-local sources fail with
`PARTIAL_BRANCH_QUERY_ADDRESS` instead of being ignored or filled with null.
A missing navigated field fact yields no projected row; it is not `null`,
logical `false`, or a completeness claim.

Identity bindings are re-encoded from their identity fields with the trusted
schema; a caller-supplied `EntityRef.encoded_ref` is not trusted. Field bindings
are validated and converted to the canonical storage atom for their schema
domain. Binding order is canonical; selection order remains the output-column
contract and therefore contributes to `query_digest`. A navigation additionally
commits its typed base, `FieldPath`, resolved field predicate and branch source
map to that digest, without changing the compiled Policy digest.

Because shipped Where IR reserves `$`-prefixed strings as variables, v0 rejects
such direct string-field bindings with `QUERY_BINDING_TYPE_MISMATCH`. Identity
strings inside `EntityRef` are safe because they are encoded to an idref first.

`CompiledEvaluationQueryV0` contains the synthetic projection Rule, explicit
per-branch direct/navigation source mappings, normalized bindings and an
engine-neutral lowering plan. The initial execution bridge accepts that exact
artifact through the existing SDK result surface:

```python
result = fg.eval.evaluate(compiled_query, engine="native")
row = result.first()
```

Execution revalidates the artifact and active schema, then executes the stored
plan rather than substituting the validation-time reconstruction. It returns
the existing `EvaluateResult`; raw `DerivationOutput` values remain internal
(`CandidateSet` is a legacy materialization alias). Query rows have kind `projection`, keep
selection order and carry the compiler-known value-domain tags. A non-matching
binding yields a valid empty result and is not interpreted as a false claim.

This first bridge is native-only and accepts no `config`. It captures the live
view digest around evaluation and permits `row.close()` / `row.explain()` only
while that view remains unchanged. Premise filters are rejected because v0
does not yet capture their policy with the view. This is a fail-closed
live-view guard, not an immutable snapshot or historical replay guarantee.

Successful compiled Query results also expose `result.run_anchor`, an immutable
`EvaluationRunAnchorV0`. It commits the original/normalized Policy target,
Policy structure and lineage, Rule pins, direct/navigation bind/select intent, native execution
profile, view/result identity, stable semantic row anchors and a query-summary
anchor. The summary exists for zero rows but explicitly makes no truth claim;
completeness is unknown and ordering is unspecified. Existing run/result/row
ids remain run-local. Repeated equivalent runs may share semantic row and
summary anchors while retaining different run ids.

The row anchor calls the existing projection-head scope pin
`head_scope_digest`; it does not claim to contain the digest of the run-local
closed Rule produced later by `row.close()`.

This anchor is `identity_only`, uses a `digest_only_live_guard`, and declares
replay `not_available`. It contains no Store callback, schema object, support
carrier or derivation/candidate identity, and has no `replay()` API. A caller
may instead opt in during execution with `capture="run_bundle_v0"`. The result's
`run_bundle` then contains the exact native plan, canonical schema, normalized
Query values, dependency-complete effective relation (including empty
relations), typed rows and canonical ProofReceipts. The evaluator and capture
path share one privately captured immutable relation; public evaluation APIs
do not expose that raw relation or a callback.

`evaluation_run_bundle_bytes(...)` and
`evaluation_run_bundle_from_bytes(...)` provide a strict, bounded canonical
codec. Decoding is detached from the originating Store and validates component
seals, row/anchor agreement, receipt structure and witness resolution. The
bundle is sensitive cleartext with caller-managed custody, declares
`authenticity="unverified"` and `replay_availability="not_implemented"`, and
has no `replay()` or detached `explain()` method. In particular, F4B1 does not
re-evaluate non-fact conditions.

F4B2 adds a separate, Store-independent verification operation:

```python
verification = verify_evaluation_run_bundle(bundle)
```

It validates the complete bundle, checks the captured native/Query semantic
contract pins, rejects a conservative work estimate above 100,000, executes
the captured native plan once over only the captured effective relation, and
compares both semantic-row and ProofReceipt multisets. The returned
`EvaluationRunVerificationV0` is a deterministic content-sealed verification
record, not an `EvaluateResult`: it has no source `run_id`, `result_id` or
`row_id` and never recreates the old Run. A matching record means only that the
current verifier reproduced the bundle's captured input; source authenticity
and business truth remain unverified.

New compiled EvaluationQuery runs publish semantic pins `native_where_v1` and
`evaluation_query_projection_v0`. Older bundles whose engine/adapter pins are
absent can still produce `matched_unpinned_runtime`, explicitly a weaker,
provisional match. A declared pin, config, engine or Where-AST-gate mismatch
returns `runtime_incompatible` without evaluator execution; oversized work is
similarly `resource_rejected`. Zero rows remain an empty semantic multiset, not
false. The verifier grammar and work estimator handle the captured native IR
forms, including negation and aggregates, but current Policy v0 admission does
not expose every such form through public EvaluationQuery authoring; this is
not a claim that those authoring restrictions were widened.

F4B3 can separately play back the captured evidence for exactly one positive
row, without consulting the originating Store:

```python
evidence = evaluation_run_bundle_evidence(
    bundle,
    row_capture_digest=bundle.rows[0].row_capture_digest,
)
```

This returns one engine-centric `EvidenceGraph` for the ProofReceipt-selected
branch. Predicate support uses captured assertion IDs, while Query binding,
Query-navigation lookup, and projection-head atoms are explicitly marked as
outside authored Policy lineage.
It reports captured evidence only: authenticity remains unverified and logical
verification is not performed. It does not call an evaluator, fabricate evidence
for empty results, inspect unselected OR branches, or produce an `Explanation`.
Callers that need a current-runtime semantic check may independently pair it with
`verify_evaluation_run_bundle(...)`; the playback operation does not depend on or
consume that verification record.

F4C then projects that unchanged, detached engine evidence onto the authored
Policy topology. It is deliberately a separate readonly view rather than a new
`Explanation` field or a replacement for the engine's `EvidenceGraph`:

```python
from factgraph.application import project_policy_explanation_v0

policy_view = project_policy_explanation_v0(
    bundle.run_anchor,
    evidence,
    semantic_row_anchor_digest=(
        bundle.run_anchor.row_anchors[0].semantic_anchor_digest
    ),
)
```

`PolicyExplanationViewV0` uses the compiler-issued `PolicyStructureV0` and
`PolicyLineage` rather than generated alias parsing. It maps direct body atoms
and structured joins to their exact authored occurrence/unify nodes, then folds
the authored `All`/`Any` tree. Query-binding, Query-navigation lookup, and
synthetic projection-head atoms remain visible in the inner evidence but are
listed as outside Policy lineage;
they never change a Policy node state. The projection is total-or-error: it
rejects incomplete, duplicate, stale, or internally contradictory evidence
(including a body-rule status that disagrees with its atoms), rather than showing
a partial Policy view. It carries assertion-source locators through from the
inner graph, remains `authenticity="unverified"`, and has no authorization,
Scenario, replay, or live-`row.explain()` integration. The projector is a pure
value transformation: it does not create, bind, or change a live Explain
lifecycle, although it may consume any `EvidenceGraph` that satisfies its
anchor and lineage checks. Empty runs have no Policy view—an empty result is
still not a false result.

The older ad-hoc `QueryRuntimeRequest` and SDK `Query` remain unchanged.
Non-native engines, standalone Query explain integration, candidate acceptance,
literals, relationship/multi-hop navigation, general expectation modes,
completeness, What-if, bundle persistence, Package, and Agent/Meander wire
formats remain later slices.

### Unified resolved Query target v1

The SDK additionally exposes one narrow convenience entry point that makes a
resolved Rule and a managed Policy peers **at Query invocation time**, without
making them the same authored object:

```python
compiled = (
    fg.query(resolved_rule)
      .bind(SemanticPortAddress("target", "person"),
            EntityRef("Person", {"employee_id": "alice"}))
      .select("age", SemanticPortAddress("target", "age"))
      .compile()
)
result = fg.eval.evaluate(compiled, capture="run_bundle_v0")
```

`resolved_rule` must be a `ResolvedRuleBundle`, not a bare `Rule`. The facade
deterministically lifts it to a one-occurrence Policy with alias `target` and
normalized id `__factgraph_rule_lift__:<rule-id>`. A Policy can be queried
directly only with its exact semantic address space:

```python
compiled = (
    fg.query(policy, address_space=addresses)
      .bind(SemanticPortAddress("person1", "person"), alice)
      .select("other_age", SemanticPortAddress("person2", "age"))
      .compile()
)
```

The facade delegates all bind/select, branch-total, value-normalization and
lowering checks to `EvaluationQuery`; it creates neither a second compiler nor
a second evaluator/result model. Its small in-process wrapper seals the existing
compiled Query together with a separately sealed source target. Consequently a
Rule-lift Run anchor reports `original_target_kind="rule"` and
`normalization_kind="rule_lift_v0"`; a direct Policy keeps
`policy_direct_v0`. The underlying Query digest and lowering plan do not change
because of this provenance label.

String policy ids, registries, Packages, dotted field paths, bare Rules,
Policy without `address_space=`, generic `expect`, modes, empty-select existence,
and external Operators are deliberately not accepted by this v1 facade.
`.select(...)` accepts only a direct `SemanticPortAddress` or the structured,
select-only `EvaluationQueryFieldNavigationV0` described above; it does not
admit navigation in `bind`, Policy logic, or a generic traversal language.
`ScenarioFieldSubstitutionV0` and the explicit atomic
`ScenarioFieldSubstitutionSetV0` may be forwarded through `.evaluate(scenario=...)`.
Both retain the no-anchor/no-bundle/no-live-evidence boundary; neither is a
general What-if language.

F5B1 adds one result-observation extension:

```python
result = (
    fg.query(resolved_rule)
      .select("age", SemanticPortAddress("target", "age"))
      .expect_contains("alice_age", age=22)
      .evaluate()
)
outcome = result.expectation_results[0]
```

`expect_contains` is not a Rule condition, a Policy node, a post-filter or an
authorization decision.  Each expected keyword must name an already-selected
alias and is normalized using the same schema-aware contract as `bind`.  It
does not alter the Policy digest, Query digest, projection head, lowered plan
or returned rows; its separate digest is committed by the targeted-Query
wrapper.  A matching row is `satisfied`.  A non-match is `not_satisfied` only
when this exact native live-view execution has the result-local
`complete_native_enumeration_v0` basis; it proves neither closed-world truth,
source authority/freshness, historical snapshot, replayability nor
cross-engine equivalence. `underdetermined` and `unsupported` remain explicit
DTO states for incomplete/unsupported future execution profiles.

F4's Run summary remains `not_asserted`/`unknown`/`unspecified`; it is not
reinterpreted as the expectation basis. An expected Query rejects `capture=`
and `scenario=` because their current contracts do not seal the expectation
inventory. Generic expect/exists/count/set/bag modes, negative evidence and
expectation Explain remain later work. A matching row may still use ordinary
live `row.explain()`; a non-match does not fabricate an EvidenceGraph.

### Captured EvaluationQuery observation v0

`EvaluationQueryBuilderV1.capture()` is the detached counterpart for a
targeted native Query, including its bounded compiled `contains_row`
observations:

```python
captured = (
    fg.query(resolved_rule)
      .select("age", SemanticPortAddress("target", "age"))
      .expect_contains("alice_age", age=22)
      .capture()
)
```

It returns `CapturedEvaluationQueryRunV0`, an outer protocol record containing
one unmodified `EvaluationRunBundleV0`, the exact targeted-wrapper digest, the
ordered compiled expectation inventory and outcomes recomputed from the sealed
rows. It does not attach expectations to `EvaluateResult` or change the
ordinary `evaluate(..., capture=...)` rejection. `to_bytes()` and
`from_bytes()` use a bounded strict canonical codec; detached `verify()`
reuses F4 isolated verification, while `explain(row_capture_digest=...)`
reuses detached positive-row playback and the authored Policy projection.

The record is digest-sealed but not authenticated, contains caller-managed
typed values, and says nothing about source authority or historical truth.
`not_satisfied` means only no matching row in this exact complete native
capture. It has no negative EvidenceGraph; callers may explain a real captured
row only. The v0 inventory is capped at 64 and excludes Scenario, config,
premise filtering, paging, generic expectation grammar, Operators and Actions.

### Scenario field substitution v0

`ScenarioFieldSubstitutionV0` is the first deliberately narrow Scenario
operation.  It is **not** a general What-if/Premise API.  It is supplied to the
same compiled Query call, rather than to a second evaluator:

```python
from factgraph.application.protocol import (
    EntityRef,
    FieldPath,
    ScenarioFieldSubstitutionV0,
)

result = fg.eval.evaluate(
    compiled_query,
    scenario=ScenarioFieldSubstitutionV0(
        entity=EntityRef("Person", {"employee_id": "alice"}),
        field=FieldPath("Person", "age"),
        value=22,
        premise_id="review-age-hypothesis",
    ),
)
```

The runtime re-materializes the entity identity through the trusted schema,
requires a complete active identity bundle, and allows only exactly one current
visible, scalar, `single`, non-identity field fact.  Its predicate must be an
exact dependency of the already materialized Query plan.  Missing values,
multi-value/relationship/identity fields, field-navigation syntax, policy or
rule overlays, and premise filtering all fail closed.

An ordinary scalar `time` field can be replaced under the same value contract.
That does not provide temporal/as-of/versioned or historical-fact semantics;
those remain out of scope.

The normal materialized native evaluator runs twice over immutable in-memory
relations: once for the baseline and once after replacing that one projected
row with a synthetic hypothesis witness.  Neither relation writes the ledger,
proof sidecar, or candidate-support index.  `result.scenario` reports the
typed old/new values, relation identities and a stable row-multiset diff.  A
same-value replacement is still a new effective source, so it records
`semantic_value_changed=False` and `effective_source_changed=True`.

Scenario rows intentionally have no ledger-backed `close()` or `explain()`;
the former raises `DetachedRowError` and the latter returns an unsupported
`Explanation`.  Scenario also rejects every `capture=` use and never attaches
an F4 anchor or bundle.  Current F4 proof receipts describe asserted ledger
facts, so presenting them as evidence for a hypothetical value would be false
provenance.  The separate `ScenarioRunV0` contract below is the only captured
exception; general replay, multi-premise truth algebra, and a general
`ScenarioPlan` remain future contracts.

### Atomic Scenario field-substitution set v0

`ScenarioFieldSubstitutionSetV0` is the only multi-member extension. It holds
at least two of the already narrow direct field substitutions; it does not add
facts, delete facts, change Rules/Policies, navigate ports, or admit arbitrary
premise logic:

```python
scenario = ScenarioFieldSubstitutionSetV0((
    ScenarioFieldSubstitutionV0(EntityRef("Person", {"employee_id": "alice"}), FieldPath("Person", "age"), 35, "alice-age"),
    ScenarioFieldSubstitutionV0(EntityRef("Person", {"employee_id": "bob"}), FieldPath("Person", "score"), 11, "bob-score"),
))
result = fg.eval.evaluate(compiled_query, scenario=scenario)
```

Before either evaluator call, FactGraph derives one dependency-complete baseline
relation, re-materializes each entity through the trusted schema, validates all
fields and values, and rejects duplicate `premise_id` or canonical
`(entity_ref, predicate)` targets. It then applies every replacement to one
immutable effective relation. Input order is therefore not semantic and a bad
member produces no partial result. The native evaluator runs exactly twice:
once for baseline and once for the complete effective relation.

`result.scenario.operations` exposes canonical operation metadata plus the
set-level relation/diff digest. These are integrity identifiers, not an
authenticated artifact, ledger snapshot, source-truth claim, or provenance.
Like the single form, the set rejects every `capture=` use, has no Run anchor
or bundle, and rows cannot `close()` or live-`explain()`. An F5B1 expected Query
rejects **all** Scenario forms, including this set.

### Captured ScenarioRun v0

The older `fg.eval.evaluate(compiled_query, scenario=...)` route above remains
a deliberately non-captured compatibility result: it has no Run anchor,
bundle, detached evidence or verification surface. A caller that needs an
auditable, detached What-if result must explicitly enter the distinct
`ScenarioRunV0` lifecycle through the same resolved Query:

```python
from factgraph.sdk import ScenarioRunV0

run = (
    fg.query(resolved_rule)
      .bind(SemanticPortAddress("target", "person"), alice)
      .select("age", SemanticPortAddress("target", "age"))
      .what_if(ScenarioFieldSubstitutionV0(alice, FieldPath("Person", "age"), 35, "review-age"))
      .run()
)

diff = run.diff()
verification = run.verify()
payload = run.to_bytes()
detached = ScenarioRunV0.from_bytes(payload)
explanation = detached.explain(
    side="effective",
    row_capture_digest=detached.effective.rows[0].row_capture_digest,
)
```

`ScenarioRunV0` evaluates the *same exact materialized native Query plan*
twice over a frozen dependency-complete baseline relation and one effective
replacement relation. It retains two private receipt captures, a sealed
premise-to-witness inventory, a typed public row summary, and a semantic
result-multiset diff. After capture, `.diff()`, `.verify()`, `.explain()` and
codec decode never read a live Store. The isolated verifier checks the
captured native relations and receipts; it does not establish that the premise
is true or that the historical ledger is authoritative.

The generic `EvaluationRunBundleV0` codec intentionally cannot decode a
ScenarioRun capture frame. Scenario-aware evidence is the only route that
opens it, and labels sources as either a captured baseline/effective relation
witness or `scenario_hypothesis`. A synthetic effective witness is therefore
never exposed as F4's normal `captured_witness`. This is a protocol/API
boundary, not encryption or authentication: payloads contain typed captured
values under caller-managed custody, and digest sealing only detects
inconsistent tampering/splicing.

The captured form admits only the Q7/Q11 replacement grammar: native engine,
no config, empty ledger premise policy, no expected Query, and one existing
visible single-valued scalar field per atomic member. It does not introduce
general fact add/remove/mask, negation, temporal/as-of semantics, Policy or
Rule overlay, Operator/action execution, source authority, persistence,
historical ledger replay, or a general Scenario language.

Compiled Policy/Query and Run-anchor values are compiler-issued, in-process
artifacts. Their integrity checks detect inconsistent splicing; they are not
authentication or a MAC. Any future codec or rehydration path must recompile
from authenticated source inputs or add an explicit artifact-authentication
contract.

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
