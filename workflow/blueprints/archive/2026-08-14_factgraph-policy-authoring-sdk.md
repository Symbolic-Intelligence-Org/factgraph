# Task Blueprint: FactGraph Policy authoring SDK

- Status: archived
- Created: 2026-08-14
- Last Updated: 2026-08-14
- Related Modules:
  - `src/factgraph/sdk/`
  - `src/factgraph/application/protocol/policy.py`
  - `src/factgraph/application/policy_runtime.py`
  - Query/portable/Explain codec seams that seal Policy structure and conditions
- Related Docs:
  - [Q19 decision](../../design/decisions/active/2026-08-14_q19-policy-authoring-sdk-literal-comparison-decision.md)
  - [Q12 decision](../../design/decisions/active/2026-08-13_q12-policy-comparison-field-navigation-v0-decision.md)
  - [Q18 final closure](../../design/decisions/active/2026-08-14_q18-factgraph-final-closure-contract.md)
  - [vs-shipped audit](../../audit/archive/2026-08-14_factgraph-policy-authoring-sdk-vs-shipped.md)
- Audit Log:
  - [paired audit](./2026-08-14_factgraph-policy-authoring-sdk.audit.md)

## 1. Problem

The current Rule/Policy Query path is robust but asks an SDK author to use
compiler IR and an explicit semantic address space. Add a concise typed
authoring façade without making the engine, Policy semantics or Explain model
less strict.

## 2. Goals

- Let an SDK author compose named Rule occurrences, nested `all`/`any`, typed
  port/navigation comparisons and a tested canonical literal comparison.
- Lower façade objects into the existing Policy/Query compiler and preserve
  PolicyStructure, lineage, capture, Explain and portable engine parity.
- Make misuse fail before evaluation, especially Python Boolean traps.

## 3. Non-goals

- A second evaluator, a string Policy registry, Rule authoring replacement,
  AgentPlan syntax, Meander integration or Actions.
- Unbounded literal domains, implicit coercion, generic Python expressions,
  relationship traversal, NAF, aggregates or engine fallback.

## 4. Current Context

- `SDKStore.query()` and `EvaluationQueryBuilderV1` already provide the one
  target-resolution/compilation/execution path.
- Q12 supplies comparison/navigation conditions, but deliberately excludes
  literal operands.
- Q18 supplies portable all-engine result parity and captured Explain/replay.

## 5. Proposed Shape

1. SDK-only immutable `PolicyDraft` / occurrence / port / navigation /
   constraint handles own ergonomic syntax and exact draft identity.
2. `build()` returns a frozen SDK target containing ordinary Policy and its
   address space; Query unwraps it at the SDK boundary.
3. A narrow canonical literal operand extends only the Policy protocol/compiler
   paths required for Q19, then travels through the existing Query/Run/Explain
   and portable paths.
4. Docs and a runnable tutorial demonstrate the public façade, not raw IR.

## 6. Boundaries And Invariants

- Raw Policy and all legacy V0 DTO/wire identities stay compatible.
- No public dotted-string parser, lookup registry or implicit address fallback.
- Nested topology is preserved and the façade never flattens `all`/`any`;
  existing Policy canonicalization retains deterministic child ordering.
- Every symbolic object rejects Boolean coercion and cross-draft/schema mixing.
- Only a tested three-engine literal domain is supported; unsupported values
  reject before lowering, with no native-only fallback. Q19 freezes that set
  to canonical signed-64-bit `int` and `time` literals.
- Explain remains captured-world-only and a literal compare remains a
  Policy-owned condition, not synthetic Rule evidence.

## 7. Acceptance

- [x] Typed façade produces the same structural Policy IR expected by Q12/Q18.
- [x] Literal-bearing policies have sealed deterministic structure, compiler,
  Explain and replay representations.
- [x] Native/Soufflé/ProbLog real fixtures agree on every supported new form.
- [x] SDK docs/tutorial use the façade; raw IR remains documented as advanced
  application/compiler surface.
- [x] Legacy Query/Policy/Explain/portable cohorts stay green.

## 8. Implementation Plan

1. Freeze Q19/audit scope, protocol literal representation and compatibility
   seams; transition this blueprint to `scoped`.
2. Implement the SDK draft/handle façade and Query-builder unwrapping using the
   existing resolver.
3. Implement canonical literal comparison through protocol, compiler, sealed
   codecs, Explain and portable lowering.
4. Add public docs/tutorial plus focused/real-engine/legacy regression suites.
5. Conduct an independent adversarial review, record outcome, then archive.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`
- a runnable SDK tutorial notebook under `examples/`

## 10. Outcome / Deviations

Implemented on 2026-08-14.

- Added the SDK-owned `PolicyDraft`/typed-handle façade and the frozen
  `AuthoredPolicyTargetV1`. It only unwraps into the existing managed Policy
  target resolver and Query compiler.
- Added canonical, type-directed signed-int64 `int`/`time` `PolicyLiteral`
  operands through Policy structure, lowering, lineage, V0 bundle and V1
  replay/Explain codecs. No legacy no-literal wire identity changed.
- Added façade-owner checks at Query bind/select, explicit Python Boolean/hash
  traps, literal-domain early rejection, and select-only navigation checks.
- Updated application/SDK docs and added
  `examples/08_sdk_policy_authoring.ipynb`, which was executed in the `factpy`
  kernel.

Final verification: `pytest tests/application tests/sdk
tests/test_sdk_find_partial_identity.py tests/test_v1_public_surface_exports.py
-q` reported **706 passed, 175 subtests passed**. Changed-code Ruff, four-module
targeted mypy, `git diff --check`, portable `int`/`time` real-engine fixtures,
and two independent reviews all passed. The public SDK surface intentionally
grew from 152 to 162 names; the pinned export regression now records the ten
Q19 authoring symbols. No push or merge occurred.
