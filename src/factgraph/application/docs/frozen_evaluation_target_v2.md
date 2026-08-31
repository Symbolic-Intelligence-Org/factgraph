# Frozen Evaluation Target V2

`FrozenEvaluationTargetV2` is FactGraph's internal, restart-safe persistence
boundary for a compiled deterministic Product Policy and its branch-aware Input
Cases. It is application/runtime material, not a public Meander request DTO and
not an authoring format.

## Boundary

A carrier contains the complete material required to instantiate a published
Input Case after process restart:

- the compiled `ProductPolicyV1` and `CompiledPolicyV0` material;
- its semantic address space and resolved evaluation target;
- the normalized execution-relevant schema snapshot;
- all compiled Input Case applicability, binding and result mappings;
- compiler/runtime ABI identifiers and a digest over the complete material.

A schema, Rule or Policy pin by itself is not executable material. Decode never
looks up a latest schema or Policy, calls `compile_policy`, or interprets
authored semantics again. Missing material, an unknown record or carrier
version, ABI mismatch, non-canonical bytes, or any stale digest fails closed.

The first carrier version accepts deterministic `ProductPolicyV1` targets only.
Weighted choices and Function occurrences are rejected rather than partially
restored. Supporting those Product arms requires a new reviewed carrier version
and explicit executable-material inventory.

## Closed codec and canonicality

The codec is a closed union. Record decode is limited to a fixed in-module class
inventory; it never imports a class named by the payload, invokes pickle, or
constructs an arbitrary Python object. The sealed evaluation replay program has
its own closed structural union. Query-derived targets explicitly encode typed
`Var` values (including `Origin`) and `PortType` values; every unknown
structural type is rejected.

Canonical JSON uses sorted object keys and compact UTF-8 encoding. Sets are
sorted by canonical encoded bytes. Mapping iteration order is intentionally
retained as an explicit pair sequence because compiled Rule port order is
execution material. Two maps with different insertion order are therefore
different frozen material; decode must reproduce the exact sequence and
`to_bytes()` must replay the original bytes.

## Runtime use

Runtime may only:

1. decode and validate the carrier;
2. select one published `case_key`;
3. fill its exact typed values and optional result keys;
4. build one `ProductEvaluationInvocationV2`.

Case applicability and semantic mappings are fixed at compilation time. A
missing value rejects instantiation; it cannot become an empty binding or an
unconstrained query. Query and Reasoning use the same Product invocation
boundary. One invocation may still execute its configured
baseline/effective/candidate sides.

`BranchWitnessV2` remains provider-neutral. It retains compiled Branch,
evaluation-side, row, proof and evidence-reference identities before row
deduplication. Product consumers may map that immutable identity through their
own frozen source map, but FactGraph does not acquire Business Policy keys or
matched/unknown/inapplicable product states.

The cross-Run source-map key is compiled Branch identity plus evaluation side
and row identity. Proof and evidence-reference identities belong to the
individual execution and must be retained and internally consistent, but are
not required to repeat when the same frozen target is executed in a new Run.

Whole-invocation limits are supplied separately through
`ProductInvocationAggregateLimitsV2`. They accumulate timeout, rows, units,
evidence, capture and Scenario usage across all sides without changing the
meaning or digest of the existing per-side `EvaluationExecutionProfileV2`.
