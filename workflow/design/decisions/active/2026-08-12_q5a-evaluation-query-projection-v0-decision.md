# Q5A Decision: EvaluationQuery v0 typed binding and projection

- Status: adopted
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: design constraint for the F3A implementation slice only.
- Inputs:
  - 2026-08-12 user instruction to continue the next FactGraph implementation item on an isolated branch
  - [`2026-08-12_q4b-managed-policy-v0-decision.md`](./2026-08-12_q4b-managed-policy-v0-decision.md)
  - [`2026-08-11_meander-factgraph-post-probe-session.md`](../../../memory/session_handoffs/2026-08-11_meander-factgraph-post-probe-session.md) §§3.2–3.3, 6.4, 8.2
- Outputs / Downstream:
  - [`2026-08-12_factgraph-evaluation-query-projection.md`](../../../blueprints/active/2026-08-12_factgraph-evaluation-query-projection.md)
- Branch: `codex/v0.3.0-f3-policy-query-projection-2026-08-12`
- Base: `afdd9e7e`
- Depends on: Q4B / F2B

## 1. Problem

F2B deliberately produces a head-independent `CompiledPolicyV0`. The shipped
RuleExpr evaluator still requires callers to invent a `head=Rule`, and its
projection helper discovers sources by unqualified same-name ports. That cannot
express `younger -> pair.person2` and is ambiguous when multiple occurrences
expose the same port name.

The repository also still ships an older ad-hoc `QueryRuntimeRequest` and SDK
`Query`. Reusing the bare name or silently changing those semantics would create
a second migration problem rather than close the Policy chain.

## 2. Scope

F3A adds only:

- `EvaluationQuery`, carrying an exact compiled-Policy digest, typed direct-port
  bindings and ordered named selections;
- deterministic validation against the exact `SemanticAddressSpace` and trusted
  `SchemaIndex` used by the Policy;
- explicit per-DNF-branch binding and projection sources;
- a `CompiledEvaluationQueryV0` containing a trusted synthetic projection head
  and engine-neutral `RuleExprLoweringPlan` ready for a later execution slice.

## 3. Non-scope

- Engine execution, `EvaluateResult`, rows, config, snapshot or lazy Explain.
- `expect`, completeness, limits, pagination or zero-row interpretation.
- Premise/What-if, field navigation, Compare or rule overlays.
- SDK sugar, wire codec, persistence, Package, Plan, Meander or Agent APIs.
- Renaming, removing or redefining the shipped ad-hoc Query surfaces.

## 4. Decision

### 4.1 Query addresses exact Policy-owned direct ports

`EvaluationQuery.policy_digest` must match the supplied `CompiledPolicyV0`.
Every bind/select source is a structured `SemanticPortAddress`; dotted strings
are never parsed. The supplied address-space digest, every current Rule/contract
pin and the trusted schema digest must match the compiled Policy.

Bindings are canonical and order-insensitive. Selections preserve caller order
because that order is the result-column contract. Output aliases, binding
addresses and selection sources are unique. Selection is always explicit; v0
does not infer all ports.

### 4.2 Bind constrains truth; select only projects

An identity endpoint accepts an `EntityRef` of the exact entity type and
recomputes its encoded identity from the trusted schema, ignoring any supplied
`encoded_ref`. A field endpoint accepts a scalar validated and canonicalized by
its schema type and field constraints.

Each bind becomes `eq(alias_local_var, canonical_constant)` inside every DNF
branch. It is not a Python post-filter. Each selection maps one output alias to
one exact occurrence-local variable in every branch and contributes only the
synthetic head link.

Both bind and select must be branch-total. A source absent from any Policy DNF
branch is a typed compile failure rather than a constraint silently omitted from
that branch.

### 4.3 Query projection extends, but does not reinterpret, RuleExpr lowering

The existing trusted `Rule.projection(...)` namespace supplies the synthetic
head, closing AC-21 without reviving the legacy `__query__:*` namespace.
RuleExpr lowering gains private explicit binding/head-link metadata. Legacy
callers leave it empty and retain their exact canonical key and same-name
projection behavior.

The explicit head-link mapping is also the sole source used by Explain probe
seeding for query plans; Explain must not rediscover query intent by matching
names. F3A records this mapping but does not claim that durable or historical
Explain is implemented.

### 4.4 The compiled result is pre-execution only

`CompiledEvaluationQueryV0` pins normalized query intent, Policy/address/schema
identity, branch sources, projection head and the full engine-neutral lowering
plan. It has no rows, config or snapshot and cannot be represented as a
completed evaluation. F4/F5 must consume this exact artifact and return the
existing `EvaluateResult` rather than create a second result model.

## 5. Stop Conditions

Stop and split the slice if any of the following becomes necessary:

- changing the public `EvaluateResult`/`EvaluateRow`/Explain contract;
- adding engine execution or Store/SDK dispatch;
- defining `expect`, completeness, What-if or field navigation;
- changing legacy RuleExpr canonical keys or projection behavior;
- exceeding 650 added production Python lines relative to `afdd9e7e`. The
  original 500-line stop was reached before review-discovered artifact-integrity,
  generated-variable-collision and projection-namespace guards could be added;
  the 150-line increase is reserved for those guards and does not authorize a
  wider product or execution surface.

## 6. Acceptance Criteria

- [ ] Exact Policy/address/schema pins and stale contracts fail closed.
- [ ] Entity and scalar bindings are schema-typed and storage-canonical.
- [ ] Bind/select resolve to exact authored and lowered occurrences in every branch.
- [ ] Branch-local sources, duplicates and ambiguous shapes fail distinctly.
- [ ] Renamed ordered selections produce exact explicit head links.
- [ ] Query digest is stable under binding order and changes with value/source/selection order.
- [ ] Materialized native structure contains binding atoms and explicit head links without execution.
- [ ] Query-aware probe seeds use explicit sources, not same-name inference.
- [ ] Legacy Query and RuleExpr lowering/evaluate/Explain regressions remain unchanged.
- [ ] No runtime config, rows, expectation, What-if, SDK or Meander surface is added.

## 7. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | proposed | Source and runtime audit completed | Existing Query is a separate ad-hoc path; projection is same-name based; EvaluateResult/Explain require a later execution integration. |
| 2026-08-12 | adopted | User authorized the next isolated implementation item | F3A is limited to typed bind/select and an engine-neutral pre-execution artifact. |
| 2026-08-12 | amended | Adversarial review activated the original line stop | Cap raised from 500 to 650 only for fail-closed compiled-artifact integrity, execution-variable collision and projection-namespace guards; scope remains unchanged. |
