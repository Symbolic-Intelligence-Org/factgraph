# Q21 Decision: first-class Function capability boundary

- Status: adopted
- Created: 2026-08-15
- Last Updated: 2026-08-15
- Authority: adopted design constraint for Product Function authoring,
  composition, execution, replay and Explain.
- Inputs:
  - [Q20 product-interface decision](./2026-08-14_q20-factgraph-product-interface-decision.md)
  - the user's 2026-08-15 lock that Rule and Function are fully peer nodes
  - [Q21 implementation blueprint](../../blueprints/active/2026-08-15_factgraph-function-capability.md)
- Branch: `codex/v0.3.0-impl-factgraph-product-interface-2026-08-14`

## 1. Decision

`FunctionCapability` is a first-class peer of `RuleCapability`.  Neither may
embed, invoke or reference the other, and one Product Function may not embed
another Product Function.  `Policy` is the sole composition owner: it places
Rule and Function occurrences in one declarative topology and connects typed
ports through authored bindings/unification.

The capability grammar becomes:

~~~
RelationCapability ::= RuleCapability
                     | FunctionCapability
                     | StoredRelationCapability
                     | ProviderRelationCapability
~~~

Function inputs and outputs are directional contract modes.  Query binding or
selection never reverses them.  Compilation must prove every required input is
bound, every selected output is branch-total, the dependency graph is acyclic,
and all executed calls fit finite cardinality/time budgets.

## 2. First implementation slice

The first shipped Function profile is deliberately narrow:

- pure, deterministic, exactly-one scalar result per input tuple;
- canonical typed scalar inputs and one named scalar output;
- ordinary Python function authoring with a derived or explicit implementation
  digest;
- pure deterministic behavior is a required contract: no I/O, Store/Rule/Policy
  access, randomness or nested Product capability call. In-process Python is
  trusted rather than sandboxed; persistent source-view mutation is detected,
  but arbitrary external effects cannot be prevented or rolled back;
- one Function occurrence may consume typed ports from one Rule occurrence in
  this first slice; broader multi-source and Function-to-Function graph
  scheduling remains a later additive slice;
- engine-neutral execution materializes a finite sealed relation before the
  final query program; replay uses the captured relation and never reinvokes
  Python.

The restriction to one upstream Rule occurrence is an implementation bound,
not a semantic reclassification: both nodes remain peers and the dependency is
owned by Policy.

## 3. Public authoring

Product SDK exposes symmetric direct/builder forms:

~~~
fg.build_function(...)
fg.function_builder(...).build(implementation, inputs=..., output=...)
~~~

`PolicyBuilder.use(...).as_(...)` accepts Product Rule and Product Function
assets.  Function inputs are connected on the Function occurrence handle and
lower to Policy-owned typed edges; no Rule AST is modified.

## 4. Execution and evidence

The canonical implementation is pre-engine materialization:

1. evaluate the upstream Rule relation against the captured side world;
2. canonicalize and de-duplicate Function input tuples;
3. invoke the pinned pure implementation under bounded failure semantics;
4. validate and seal Function outputs and a materialization receipt;
5. execute the final Native/Souffle/ProbLog program against the same captured
   world plus the sealed synthetic relation;
6. replay from sealed program/world/materialization without invoking Python.

Structured Explain exposes Function occurrence identity, typed inputs/outputs,
implementation and materialization digests and execution status.  It does not
misclassify a pure Function result as an external Source.

## 5. Rejected alternatives

- Function atoms inside Rule bodies: rejected because they erase peer
  ownership and mix logical derivation with executable-code scheduling.
- Rule calls from Function implementations: rejected because the Function
  would become an evaluator and bypass Policy governance.
- direct engine UDFs as canonical semantics: rejected because ProbLog Python
  externs and Souffle C++ functors have different runtime and purity contracts.
- arbitrary Provider callbacks as Function: rejected because Provider returns
  a finite relation under a different effect/receipt contract.

## 6. Acceptance criteria

- [x] Rule and Function assets remain separately identifiable and sealed.
- [x] Neither asset contains a reference to or nested invocation of the other.
- [x] Policy is the only Function-occurrence composition ingress.
- [x] Missing/wrong/unbound Function inputs fail before final engine execution.
- [x] Native, Souffle and ProbLog consume the same captured Function relation.
- [x] Replay performs zero Python Function invocations.
- [x] Structured Explain exposes Function materialization without fabricating
      external-source evidence.

## 7. Decision record

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-15 | adopted | User locked peer-only Rule/Function design | Direct implementation and testing authorized for the bounded first slice. |
| 2026-08-15 | implemented | Bounded Product Function slice verified | Direct/staged authoring, intrinsic Policy topology, sealed pre-engine materialization, Native/Soufflé/ProbLog portable execution, detached replay and structured Explain are green. |
