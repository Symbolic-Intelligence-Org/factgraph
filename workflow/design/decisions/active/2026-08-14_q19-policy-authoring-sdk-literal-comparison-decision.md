# Q19 Decision: Policy authoring SDK and literal comparison

- Status: adopted
- Created: 2026-08-14
- Last Updated: 2026-08-14
- Authority: the user's 2026-08-14 explicit adoption of a user-facing Policy
  authoring layer, including natural port comparisons, literal comparison and
  nested `all`/`any`, on an isolated branch.
- Inputs:
  - [Policy authoring SDK versus shipped audit](../../../audit/active/2026-08-14_factgraph-policy-authoring-sdk-vs-shipped.md)
  - [Q12](2026-08-13_q12-policy-comparison-field-navigation-v0-decision.md)
  - [Q18](2026-08-14_q18-factgraph-final-closure-contract.md)
- Outputs / Downstream:
  - [Policy authoring SDK blueprint](../../../blueprints/active/2026-08-14_factgraph-policy-authoring-sdk.md)
- Branch: `codex/v0.3.0-policy-authoring-sdk-2026-08-14`
- Base: `a6ed84c1`

> Q19 supersedes only Q12's literal-operand restriction and its corresponding
> literal non-goal. Q12's typed addressing, branch-total lowering, ownership
> of Policy conditions, evidence guarantees and all other exclusions remain in
> force. Q18's portable-profile and no-string-registry boundaries also remain
> in force.

## 1. Problem

FactGraph can execute a direct, structured Policy but its author must currently
construct compiler IR (`PolicyAll`, `PolicyOccurrence`, semantic addresses and
an address space) directly. That is correct infrastructure, not a usable SDK
for people, Meander or an AgentPlan compiler. It obscures a simple declarative
question such as "employees over 12 whose linked age exceeds another person's".

## 2. Decision

### 2.1 One façade, one compiler

FactGraph gains an SDK-owned Policy draft façade. It is a typed authoring
adapter, not a new DSL, AST authority, registry or evaluator:

```python
review = fg.policy("age_review", version="1")
people = review.use(person_rule, as_="people")
other = review.use(person_rule, as_="other")

policy = review.build(
    review.all(
        people,
        other,
        people.age > 12,
        people.person.field("age") > other.person.field("age"),
        review.any(
            review.all(...),
            review.all(...),
        ),
    )
)

run = (
    fg.query(policy)
      .bind(people.person, alice)
      .select("age", people.age)
      .plan()
      .run()
)
```

`build()` returns one frozen SDK Policy target containing the ordinary Policy
and its exact SemanticAddressSpace. `fg.query(target)` unwraps it only at the
SDK boundary and delegates to the existing Policy target resolver and Query
compiler. Raw application Policy values remain supported unchanged.

### 2.2 Authoring syntax and ownership

- `draft.use(resolved_rule, as_="alias")` declares one occurrence and produces
  typed port handles. The same resolved rule may be used under multiple aliases.
- `occurrence.port("name")` is the universal, canonical escape hatch;
  `occurrence.name` is only an ergonomic alias for safe, unambiguous Python
  identifiers. Navigation uses `entity_port.field("field")`.
- `draft.all(...)` and `draft.any(...)` are explicit and recursively nestable.
  They preserve the written topology; they never flatten or reorder author
  structure beyond existing canonical child validation.
- Scalar `>`, `>=`, `<`, `<=`, `==` and `!=` produce typed compare constraints.
  `draft.same(left_entity, right_entity)` is the explicit entity-identity
  unification operation; entity comparison operators are rejected.
- Query `bind` and `select` accept façade handles and lower them to the same
  structured addresses/navigation that the compiler already accepts.

### 2.3 Literal operand contract

`people.age > 12` is a real Policy semantic extension. It creates an immutable
canonical `PolicyLiteral` operand; it is committed by Policy node identity,
Policy structure, compiled policy digest, condition lineage, captured replay
program and Explain projection.

The SDK derives the literal's scalar domain from the compared resolved endpoint
and validates its exact canonical value before Policy construction. Raw IR may
construct a literal only with an explicit domain. The initial supported value
set is deliberately just canonical `int` and `time` literals, each represented
by a non-Boolean signed 64-bit integer. They support equality and ordering.
String, bool, UUID, bytes and float literals remain rejected until a later
slice supplies their canonical codec, lowering, replay and real all-engine
tests. `None`, bool-as-int, non-finite float values, entity references and
multi-value endpoints reject before execution.

### 2.4 Host-language safety

Every symbolic handle, constraint and expression rejects truth-value testing.
Therefore Python `and`, `or`, `not`, ternary conditions and chained comparisons
fail loudly rather than lose an authored branch. `is` is never logical equality.
Façade values are not hash keys. Authors write:

```python
review.all(people.age >= 12, people.age < 65)
```

rather than `12 <= people.age < 65` or Python `and`.

### 2.5 Explain, portability and compatibility

The façade introduces no special Explain path. An authored constraint is the
existing Policy condition; its leaf remains visible in the same Policy topology
and captured native Explain path. The portable deterministic profile receives
the identical lowered comparison in native, Soufflé and ProbLog and compares
only canonical selected-row sets; it does not claim proof-format equality.

Existing raw Policy, Query, F3/F4/Q18 DTOs and V0 wire contracts remain
unchanged. New literal-bearing shapes use parallel versioned structure/lineage
forms where widening a historical V0 DTO would alter its seal.

## 3. Non-goals

- A Policy catalog, string lookup, ambient registry or bare `fg.query("id")`.
- Rule authoring redesign or a generic Python expression language.
- `and`/`or`/`not`, chained comparison, Python `is`, implicit coercion or
  automatic semantic repair.
- Entity comparison operators, relationship traversal, multi-hop navigation,
  aggregates, NAF, arbitrary Compute/Lookup code or Action execution.
- A new evaluator, native fallback, bag semantics, or full cross-engine proof
  parity.
- Meander policy assignment, Agent authorization, source authority or UI.

## 4. Acceptance criteria

- [ ] SDK authors can construct nested All/Any policies from resolved Rule
  occurrences without importing Policy IR or SemanticAddressSpace.
- [ ] Port/navigation comparison and a canonical integer literal lower through
  one existing compiler/evaluator path with deterministic structure/lineage.
- [ ] Misuse of host Boolean syntax, cross-draft handles, unknown ports and
  invalid literals fails loudly before evaluation.
- [ ] `fg.query(built_policy)` accepts façade handles in bind/select and raw
  Policy compatibility stays intact.
- [ ] Native, Soufflé and ProbLog have real conformance fixtures for supported
  façade comparison forms, without fallback.
- [ ] Detached Explain/replay expose literal compare topology and reject tamper;
  legacy V0 artefacts remain readable.

## 5. Decision record

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-14 | adopted | User-facing authoring form selected | Explicit nesting plus natural comparison is adopted; literals are treated as a semantic, auditable extension rather than convenience syntax. |
| 2026-08-14 | scoped | Literal envelope frozen | Q19 starts with only canonical `int` and `time` literals, the minimum portable surface that covers `people.age > 12` without untested coercion. |
