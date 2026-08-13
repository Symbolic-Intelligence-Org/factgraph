# Q14 Decision: EvaluationQuery field-navigation selection v0

- Status: adopted
- Created: 2026-08-13
- Authority: the user's 2026-08-13 authorization for project-level continuous
  FactGraph delivery. This is a bounded implementation decision, not an
  authorization or Agent-contract decision.
- Depends on: Q5A/Q5B, Q6A/Q6B, Q8, Q12 and Q13.
- Downstream: [Query field-navigation continuous blueprint](../../../blueprints/active/2026-08-13_factgraph-query-field-navigation-continuous.md)

## 1. Problem

The current Query contract can project only a directly addressable Rule port.
That keeps the initial API narrow, but it makes a common read-only target
awkward: given an identity selected by a Policy or lifted Rule, project one
known scalar field from that entity. The already-shipped `PolicyFieldNavigation`
cannot be reused: it is authored business logic and participates in Policy
structure, lineage and evidence, whereas this operation is Query projection
plumbing.

## 2. Decision

### 2.1 Public query-owned value

`EvaluationQueryFieldNavigationV0` is a structured source accepted only by
`EvaluationQueryBuilderV1.select()` and the underlying `EvaluationQuery`:

```python
EvaluationQueryFieldNavigationV0(
    base=SemanticPortAddress("younger", "person"),
    field=FieldPath("Person", "age"),
)
```

It permits exactly one lookup from an `EntityIdentity` base port to a known,
single-valued scalar field of the same entity type. Dotted strings,
`PolicyFieldNavigation`, relationship traversal, identity fields, multi-value
fields, multi-hop paths and navigation in `bind()` are rejected.

The lookup has ordinary inner-relation semantics: if the field fact is absent,
that branch produces no projected row. It is neither `null`, logical `false`,
nor a complete-result claim.

### 2.2 Compiler, identity and integrity boundary

Every navigation source must resolve in every compiled Policy DNF branch before
the engine runs. The compiler seals source kind, base address, `FieldPath`,
resolved field predicate, scalar domain, branch source map and selection order
into the Query digest and derives deterministic branch-private lookup variables.

Existing direct `EvaluationQuerySelection` and
`EvaluationRunSelectionV0` DTOs remain unchanged. New parallel navigation
selection DTOs form sealed unions at the Query and EvaluationRun boundaries, so
historical direct-only anchor/bundle wire shapes and digests remain stable.

### 2.3 Lowering and evidence ownership

The only permitted generated order is:

```text
Rule bodies -> Policy conditions -> Query value bindings
            -> Query-navigation lookups -> joins -> projection-head links
```

Navigation lookups are Query-owned trace materialization. They must not alter a
Policy's authored structure, Policy digest or Policy lineage, and live or
detached evidence must classify them outside Policy lineage rather than as Rule
body atoms or Policy conditions.

### 2.4 Existing captured and Scenario paths

EvaluationRun anchors, bundles, detached evidence and isolated verification
must carry the new selection union and reject malformed/hybrid payloads. Q13
ScenarioRun receives the lookup through the same native Query plan; replacing
the navigated field must show an effective-side `scenario_hypothesis` source,
not an ordinary captured ledger witness.

## 3. Non-scope

- Authorization, Package/registry, Agent plan, Meander API/UI or SourceRecord.
- Generic QueryPlan/GoalPlan, operators, external lookups, actions or match
  unification.
- Navigation in `bind`, general scenario/premise algebra, completeness,
  pagination, non-native engines, historical replay and negative proof.
- Any change to authored Policy grammar or Policy-owned comparison/navigation.

## 4. Rejected alternatives

### Reuse `PolicyFieldNavigation`

Rejected because it would falsely make a caller's projection request look like
authored business logic, contaminating Policy identity and Explain ownership.

### Add optional fields to historic selection DTOs

Rejected because anchors and bundles use sealed dataclass payloads; defaulted
fields would still alter legacy serialized forms.

### Treat a missing field as a nullable projected value

Rejected because the native relational evaluator has no such field-null
contract, and it would blur absent evidence with a proven false value.

## 5. Acceptance criteria

- [ ] Rule lifts and direct Policies can project one valid navigation source.
- [ ] All invalid shapes and partial branches reject before evaluator entry.
- [ ] Navigation changes the Query digest but not the Policy digest/structure/
  lineage; direct-only legacy forms remain stable.
- [ ] Lowering, live Explain, captured bundle evidence and isolated verification
  preserve the Query-owned partition.
- [ ] `expect_contains` normalizes a navigated scalar selection correctly.
- [ ] Q13 ScenarioRun re-evaluates a navigated replacement and labels effective
  evidence as `scenario_hypothesis`.

## 6. Decision record

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-13 | adopted | Scope frozen | Continuous-delivery authorization is consumed only for the bounded read-only Query projection slice. |
