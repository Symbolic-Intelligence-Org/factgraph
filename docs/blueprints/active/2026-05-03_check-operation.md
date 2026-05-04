# Task Blueprint: Check Operation

- Status: scoped
- Created: 2026-05-03
- Last Updated: 2026-05-04
- Related Modules:
  - `src/kernel/application/protocol/`
  - `src/kernel/application/`
  - `src/kernel/core/rules/`
  - `src/kernel/core/store/`
  - `src/kernel/sdk/` (optional thin shell only; no substrate)
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/rule-replay-line-redesign-input/README.md](../../references/working/rule-replay-line-redesign-input/README.md)
  - [docs/references/working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md](../../references/working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md)
  - [docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md](../../references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md)
- Audit Log:
  - [2026-05-03_check-operation.audit.md](./2026-05-03_check-operation.audit.md)

## 1. Problem

The reset rule-replay redesign line needs a first application-first runtime capability that is small enough to implement safely and meaningful enough to validate the new layering discipline.

The Check operation answers:

> Given a rule/derivation and a complete or partial binding, does any full result binding satisfy the rule under the current store state?

This directly addresses the "boolean compliance check for a specific binding" need captured in the redesign input bundle, without reintroducing the abandoned SDK-first replay substrate. The conceptual + interaction design is resolved in the reference topic doc; this blueprint must turn that resolved concept into a source-backed protocol contract and, only after scope is frozen, implement it through `kernel.application`.

## 2. Goals

- Add an application-first Check capability with protocol DTO(s) and a pure runtime entrypoint.
- Preserve the resolved conceptual contract:
  - Check is evaluate's verify-given dual.
  - Inputs are rule/plan + complete or partial binding + engine; no fact overlay.
  - Runtime dependencies such as `store` and `registry` are side-channel parameters, not request fields.
  - Native Check uses final-result matching from `evaluate_native_where(...)`; direct `_branch_satisfies` is not the MVP contract.
  - Evidence is read-only in the system-state sense: Check may produce a derived EvidenceEnvelope, but must not commit facts, candidates, or assertions.
  - `branch_atom_projection` is a reserved slot and remains `None` in MVP.
- Preserve the concrete Protocol Contract frozen during Step 0.
- Add targeted application protocol/runtime tests for the frozen contract.
- Add SDK delegation only if explicitly kept in scope after Step 0; SDK must remain a thin shell.

## 3. Non-goals

- No fact overlay, fact replacement, or fact mutation what-if.
- No initial-env injection for partial bindings.
- No batch/streaming Check API.
- No fail localization, first-failing-atom diagnostics, Diagnose/Explain operation, or why-not board.
- No implemented branch/atom walkable projection; `branch_atom_projection` remains reserved and `None`.
- No engine extension surface architecture design beyond the minimum contract needed for Check.
- No in-Check caching of RuleRef resolutions or evidence envelopes. If future caching is needed, it belongs behind registry/runtime authority and its key must include rule identity/version plus registry snapshot/generation.
- No persistent audit JSONL replay/check event storage.
- No new SDK substrate. Any SDK method must delegate to application runtime.
- No release-base, `v0.1-oss-prep`, or `master` merge/publish action.

## 4. Current Context

### Application baseline

- `src/kernel/application/` already has the protocol/runtime/executor pattern that new capabilities must follow.
- Existing derivation entrypoint:
  - `evaluate_derivation_plans(request, *, store, registry=None) -> list[CandidateSet]`
- Existing protocol shape:
  - `DerivationEvaluateRequest(plans, run_id, engine)`
- Existing runtime dependency shape:
  - request DTO carries user intent
  - `store` / `registry` are runtime side-channel dependencies

### Check primitives and evidence anchors

Baseline §P0-3 identifies the core anchors:

- `evaluate_native_where(...)`
- `_branch_satisfies(...)`
- `_atom_satisfies(...)`
- `find_winning_branch_index(...)`
- `build_support_artifact_for_binding(...)`
- `BindingItems` / `normalize_binding_items`
- `project_view_facts_with_witness(...)`

Post-topic correction in baseline §P0-3 is binding for this blueprint:

- Direct `_branch_satisfies` primitives are a possible future no-RuleRef fast path, not the MVP contract.
- Native Check requires final-binding enumeration + subset match for both complete and partial binding.
- Non-native engines require evaluate-then-match only where requested bindings are representable by candidate payload / engine output.

### Resolved conceptual contract

The topic doc is `cited` by this blueprint and is the authority for conceptual + interaction decisions. The blueprint must not re-litigate the concept. It must freeze concrete protocol details.

Resolved constraints include:

- `CheckResult.status` conceptual values: `passed`, `failed`, `unsupported`, `invalid_request`.
- Future `BranchAtomProjection.projection_status` values: `available`, `partial`, `unsupported`; not implemented in MVP.
- RuleRef resolution belongs to the application runtime via `registry` side-channel. `CheckRequest` must not carry registry or precomputed resolutions.
- Multi-branch matches are normal `passed`; Check returns deterministic primary-only evidence plus `matched_count`.
- Unexpected runtime / engine failures must not be collapsed into `unsupported` or `invalid_request`.

## 5. Proposed Shape

Step 0 froze the MVP protocol contract. Audit log Step 0.B / Step 0.C is the
source of truth for field semantics, algorithms, and drift-prevention tests.
Implementation may refine class/function names but must not change this
contract without updating the blueprint and audit first.

- `src/kernel/application/protocol/derivation_check.py`
  - `CheckRequest`-style frozen DTO:
    - single `CompiledDerivationPlan`
    - exactly one head (`len(plan.heads) == 1`); multi-head plans are evaluate orchestration input and are rejected at DTO construction
    - `binding: BindingItems` with Check-specific `$`-prefixed variable validation
    - required `engine: Literal["native", "souffle", "problog", "pyreason"]`
    - no request-level `engine_options`, identity/query/run fields, store, registry, or precomputed RuleRef resolutions
  - `CheckResult`-style frozen DTO:
    - `status: Literal["passed", "failed", "unsupported", "invalid_request"]`
    - normalized `requested_binding: BindingItems`
    - `matched_count: int | None`
    - `matched_binding: BindingItems | None`
    - `evidence_envelope: EvidenceEnvelope | None`
    - `errors: tuple[ErrorDTO, ...]`
    - `warnings: tuple[WarningDTO, ...]`
  - `EvidenceEnvelope`-style frozen DTO:
    - `engine`
    - `support_kind`
    - `support_digest`
    - `branch_index: int | None`
    - `engine_payload: SupportArtifact | ProvenanceEnvelope`
    - `branch_atom_projection: None = None`
- `src/kernel/application/derivation_check_runtime.py`
  - pure runtime function, expected shape:
    - `check_derivation_binding(request, *, store, registry=None) -> CheckResult`
  - native path uses final-result matching from `evaluate_native_where(...)`
  - non-native path uses request-level representability precheck and then `evaluate_derivation_plans(...)`
  - uses application/current-store projection APIs, not SDK state
- `src/kernel/application/__init__.py` and `src/kernel/application/protocol/__init__.py`
  - exports added in the same change as the protocol/runtime implementation
- tests under `src/kernel/tests/`
  - protocol shape tests
  - runtime behavior tests
  - SDK delegate tests only if SDK shell is in scope

Layer placement is not negotiable: substrate starts in `kernel.application`.

## 6. Boundaries And Invariants

- **Application-first:** no new runtime substrate under `kernel.sdk`.
- **Intent-only request DTO:** no `store`, no `registry`, no precomputed `rule_ref_resolutions`.
- **No silent partial failure:** user partial binding must never be passed directly into `_branch_satisfies`.
- **Evidence read-only:** Check may create a derived EvidenceEnvelope; it must not commit facts/candidates/assertions.
- **Representability gate:** any non-native request that cannot be represented from candidate payload / engine output returns `unsupported`.
- **Deterministic primary:** primary result selection must have a stable sort key.
- **Outcome purity:** status is outcome/capability/request-shape only; multi-branch topology must not become a status.
- **Layer 3 reserved slot:** `branch_atom_projection=None` means projection not implemented, not degraded evidence.
- **Runtime errors:** unexpected engine/runtime failures propagate through the runtime error channel, not through `unsupported` or `invalid_request`.

## 7. Acceptance

- [x] Step 0 freezes the Protocol Contract before status moves from `draft` to `scoped`.
- [ ] Check protocol DTO(s) live under `kernel.application.protocol`.
- [ ] CheckRequest DTO schema rejects `store`, `registry`, and precomputed `rule_ref_resolutions` fields.
- [ ] CheckRequest rejects multi-head plans with `ProtocolShapeError`.
- [ ] Check runtime lives under `kernel.application` and takes dependencies via explicit side-channel parameters.
- [ ] Complete native binding pass/fail behavior is covered by tests.
- [ ] Partial native binding pass/fail and multi-match behavior are covered by tests.
- [ ] Tests prove partial binding is not evaluated by directly calling `_branch_satisfies` on the partial input.
- [ ] Deterministic primary selection is covered by tests, including OR branch order.
- [ ] RuleRef with/without registry behavior is covered by tests.
- [ ] Malformed CheckRequest DTO shape (wrong container type, $-prefix violation, missing required field, malformed BindingItems structure) raises `ProtocolShapeError` at DTO construction; **not** converted to `status="invalid_request"` (per existing `application.protocol.common` convention).
- [ ] Semantically invalid but well-shaped request (unknown variable in rule body or RuleRef without registry) maps to `status="invalid_request"` with `errors` populated.
- [ ] Native evidence envelope is inspectable / serializable and preserves support metadata.
- [ ] EvidenceEnvelope round-trips engine-native payload without flattening away engine-specific fields.
- [ ] Non-native representability boundary is covered by tests for at least the scoped engine set.
- [ ] `branch_atom_projection=None` is tested as "projection not implemented", not "evidence degraded".
- [ ] Affected application docs are updated.
- [ ] If an SDK shell is added, SDK docs/tests prove it is a delegate and not a substrate.
- [ ] No release-base / publish / projection action is performed.

## 8. Implementation Plan

1. **Step 0 — Source-backed Protocol Contract spike (complete)**
   - Contract is frozen in audit log Step 0.A / Step 0.B / Step 0.C.
   - Blueprint status moved from `draft` to `scoped` after Step 0.D lift.

2. **Step 1 — Protocol DTO(s)**
   - Add `derivation_check` protocol module and exports.
   - Add request/result/envelope DTOs per §5.
   - Validate `$`-prefixed binding keys and malformed DTO shape via existing `ProtocolShapeError` conventions.
   - Add protocol shape / validation tests, including rejection of `store`, `registry`, and precomputed RuleRef resolutions in the request surface.

3. **Step 2 — Native runtime MVP**
   - Implement native Check through unified `evaluate_native_where(...)` final-binding flow.
   - Treat complete binding as exact subset-match; treat partial binding as subset-match over enumerated final bindings.
   - Build derived EvidenceEnvelope only for the selected `passed` primary full binding.
   - Add native runtime tests.

4. **Step 3 — RuleRef and deterministic primary hardening**
   - Add RuleRef tests and `invalid_request` details:
     - `REGISTRY_REQUIRED`
     - `RULE_REF_UNRESOLVABLE`
     - `RULE_REF_VERSION_MISMATCH` only when source-stable
     - `RULE_REF_CYCLE`
   - Add explicit deterministic primary sorting:
     - native / souffle: `(branch_index, binding_items, candidate_key_or_empty)`
     - problog / pyreason: `(candidate_key, binding_items)`
   - Add multi-branch/multi-match deterministic tests.

5. **Step 4 — Scoped engine boundary**
   - Implement Option IV representability-gated multi-engine behavior.
   - Perform request-level representability precheck before non-native evaluation.
   - Delegate representable non-native requests through `evaluate_derivation_plans(...)`.
   - Implement per-engine match extraction:
     - native bypasses extraction and uses final bindings directly
     - souffle uses `SupportArtifact.binding_items`
     - problog / pyreason use `plan.heads[0].head_var_names + CandidateSet.payload` for head-only bindings
   - Return `unsupported` only when the question is not representable for the engine/output shape; return `failed` when it is representable and no match exists.
   - Add tests for supported and unsupported boundaries.

6. **Step 5 — Optional SDK delegate**
   - Only if kept in scope after Step 0.
   - Add thin SDK method delegating to application runtime.
   - Add SDK delegate tests.

7. **Step 6 — Docs and close-out**
   - Update application module docs.
   - Update SDK docs only if SDK shell is added.
   - Fill Outcome / Deviations.
   - Archive blueprint after implementation.

## 9. Docs To Update

- `src/kernel/application/docs/README.md`
- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- `src/kernel/sdk/docs/00_user_guide.md` only if SDK shell is added
- `src/kernel/sdk/docs/00_user_guide.en.md` only if SDK shell is added

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
