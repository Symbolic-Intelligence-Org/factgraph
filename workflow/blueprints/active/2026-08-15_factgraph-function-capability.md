# Task Blueprint: FactGraph first-class Function capability

- Status: implemented
- Created: 2026-08-15
- Last Updated: 2026-08-15
- Related Modules:
  - `src/factgraph/sdk/product_authoring.py`
  - `src/factgraph/sdk/evaluation_query_builder.py`
  - `src/factgraph/application/goal_plan_v2_runtime.py`
  - `src/factgraph/application/protocol/`
  - `src/factgraph/application/product_explanation_data_v2.py`
- Related Docs:
  - [Q21 Function decision](../../design/decisions/active/2026-08-15_q21-function-capability-boundary-decision.md)
  - [Q20 Product interface](../../design/decisions/active/2026-08-14_q20-factgraph-product-interface-decision.md)
- Audit Log:
  - [2026-08-15_factgraph-function-capability.audit.md](./2026-08-15_factgraph-function-capability.audit.md)

## 1. Problem

FactGraph has first-class Product Rules and Policies, a narrow pre-engine
RelationProvider V1 and several fixed arithmetic builtins, but no public,
sealed Function capability that an Agent/user can author and compose as a peer
Policy node.  Treating a Python callable as a Rule atom or Provider would
violate the adopted peer-only boundary and would not supply a portable
select/Explain/replay contract.

## 2. Goals

- Add immutable Product Function semantic and implementation assets with
  symmetric `build_function` / `function_builder` SDK entry points.
- Add Function occurrences and typed Function ports to Product Policy
  authoring without changing Rule ASTs.
- Materialize deterministic Function results into one sealed internal relation
  and consume that same relation across Native, Souffle and ProbLog.
- Seal Function topology/materialization into V2 run/replay and expose it as
  structured product Explanation data.
- Preserve all existing Rule/Policy/V0/V1/Q20 behavior.

## 3. Non-goals

- Rule-embedded Function calls or Function-embedded Rule/Function calls.
- arbitrary I/O, action tools, MCP calls, network clients or side effects.
- nondeterministic, zero/many-output, aggregate, streaming or asynchronous
  Functions.
- multi-Rule-source Function inputs or Function-to-Function chaining in the
  first slice.
- engine-native ProbLog/Souffle UDF registration as semantic authority.
- Meander catalog/publication/permission implementation.

## 4. Current Context

- `RelationProviderV1` materializes one finite relation before V1 engine
  execution but is not a Policy node and is rejected by Product V2.
- core `BuiltinAtom` has directional dataflow for a fixed arithmetic allowlist,
  while portable V1 rejects generic builtin/code semantics.
- `SemanticEndpoint` and `SemanticAddressSpace` are Rule/schema-only; computed
  Function ports need a Product-level peer address contract.
- Product V2 already seals program/world/profile/assets and offers replay and
  structured result/Explain adapters.

## 5. Proposed Shape

### 5.1 Product asset

`ProductFunctionV1` lives beside the existing Product Rule/Policy envelopes and
owns id/version/AssetMeta, ordered typed input ports, one typed output, a pure
deterministic semantics contract, and a separately pinned implementation
digest. The callable is in-process only and excluded from durable identity;
the builder derives a bounded source/code digest when possible or accepts an
explicit canonical artifact digest.

### 5.2 Policy peer occurrence

`PolicyBuilder.use(ProductFunctionV1).as_(alias)` returns a
`FunctionOccurrenceHandleV1`.  Its `.inputs(...)` connects every input to a
direct scalar port from exactly one Rule occurrence.  Product Policy owns a
sealed Function topology sidecar and an intrinsic V2-only AST marker; controlled
V2 compilation lowers it to an internal synthetic Rule/relation.  Legacy/V1
terminals reject the intrinsic marker even after raw Policy rewrapping.

### 5.3 Internal relation

Each Function occurrence receives a compiler-reserved call-identity entity and
one binary predicate per input/output port, all joined by an opaque call key.
The binary form is accepted by the real ProbLog EDB contract while retaining
typed port identity. A derived execution schema and Rule contract are used only
inside Product V2. They never mutate the SDKStore schema or ledger. Per
side/world, an upstream Rule projection produces finite input rows; the runtime
calls the implementation once per distinct canonical input tuple and inserts
sealed port rows into an isolated Store.

### 5.4 Profiles and replay

Add a deterministic portable V2 profile that returns Native/Souffle/ProbLog
frames over the same world and Function relation.  Native-only V2 remains
supported.  ProbLog point semantics may consume deterministic Function rows,
but the Function itself has no probability or hidden randomness.

The program envelope captures Function assets, occurrence wiring, derived
schema/predicate identities and per-side materializations. Replay verifies the
captures and never calls the implementation.

### 5.5 Explain

Expose `FunctionCallViewV2` records independently of EvidenceGraph availability:
function/call-site identity, typed inputs/output, implementation digest,
materialization digest and status.  EvidenceGraph integration may add an
explicit Function form only when native evidence capture exists; no Source is
fabricated.

## 6. Boundaries And Invariants

- Rule and Function source definitions have no cross-reference field.
- Function implementation receives only canonical scalar Python values.
- All Function inputs are connected exactly once, share one upstream Rule
  occurrence, and are branch-total.
- Output is fresh and directional; binding it as an input is rejected.
- Same input tuple must produce one canonical output; duplicate/conflicting
  results fail closed.
- No callback is invoked during replay.
- Internal predicates use a reserved namespace and never enter the ledger.
- Existing Product Rule/Policy logical identities are byte-stable when no
  Function occurrence is present.

## 7. Acceptance

- [x] Direct and staged Function authoring produce the same sealed asset.
- [x] Product Policy composes peer Rule/Function occurrences and selects a
      Function output without Rule AST mutation.
- [x] Cross-builder, missing-input, wrong-domain, output-as-input and raw legacy
      unwrap paths reject with stable typed codes.
- [x] Scenario changes upstream facts and therefore Function results without
      writing the ledger.
- [x] Native/Souffle/ProbLog deterministic rows agree for the same Function
      materialization.
- [x] Function callable count is unchanged by replay.
- [x] Structured Explain contains sealed Function-call records.
- [x] Q20 application+SDK regressions, ruff, mypy and diff-check pass.
- [x] Affected module docs and a runnable example are synchronized.

## 8. Implementation Plan

1. Add strict Function protocol/SDK assets and authoring tests.
2. Add Function occurrence handles, intrinsic Policy marker and controlled V2
   lowering with legacy fail-closed tests.
3. Add finite input projection/materialization and internal schema execution.
4. Extend V2 run/program capture, replay and structured Explain.
5. Add portable deterministic V2 engine profile and three-engine conformance.
6. Update SDK/application/protocol docs and executable example; run full
   verification and record outcome.

## 9. Docs To Update

- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`
- `src/factgraph/sdk/docs/08_product_scenario_execution_v2.en.md`
- `src/factgraph/application/protocol/docs/README.md`
- `src/factgraph/application/docs/product_result_explain_v2.md`
- `examples/README.md` and Product V2 notebook/example

## 10. Outcome / Deviations

Implemented additively in the Product V2 path. The public asset surface is
`build_function(...)` / `function_builder(...).build(...)`; Policy uses the
same `use(asset).as_(alias)` spelling as Rule and connects typed inputs with
`function_occurrence.inputs(...)`. An intrinsic `PolicyFunctionOccurrenceV1`
survives raw Policy rewrapping and makes all legacy/V1 terminals fail closed.

The initially sketched single wide Function predicate was replaced by one
binary predicate per port plus a shared opaque call identity. This was required
by the real ProbLog EDB contract and lets all three engines consume the same
ordinary relation without adapter UDFs. Function-free Product Policy identities
remain unchanged.

V2 captures definition/asset/topology pins in the replay program and typed
calls in each run side. Replay validates and injects those calls without the
callable. Product Result/Explain exposes the validated definitions and
materializations while keeping `EvidenceGraph` explicitly unavailable when no
native graph was captured.

Verification on 2026-08-15:

- `776 passed, 182 subtests passed` across `tests/application`, `tests/sdk`,
  the V1 public-surface suite and legacy SDK name guard;
- focused Product Function tests cover three real engines, Scenario, replay,
  malformed wiring, callback mutation/nondeterminism and capture tampering;
- Ruff check/format, focused mypy and `git diff --check` are clean; and
- `examples/09_product_scenario_execution_v2.ipynb` was executed in place with
  the `factpy` kernel with no error or unexecuted code cell.

The callable remains trusted in-process code rather than a sandbox. The runtime
detects persistent source-graph mutation but cannot prevent or undo arbitrary
external effects; Action/MCP/tool capabilities remain a separate future
contract. Function-to-Function chaining, multi-source inputs, field-navigation
inputs, WeightedChoice co-location and rich Function EvidenceGraph nodes remain
explicitly outside this first slice.
