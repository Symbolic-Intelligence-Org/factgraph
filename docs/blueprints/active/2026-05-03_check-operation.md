# Task Blueprint: Check Operation

- Status: draft
- Created: 2026-05-03
- Last Updated: 2026-05-03
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
  - Native complete binding may use `_branch_satisfies`; native partial binding must enumerate full bindings before subset matching.
  - Evidence is read-only in the system-state sense: Check may produce a derived EvidenceEnvelope, but must not commit facts, candidates, or assertions.
  - `branch_atom_projection` is a reserved slot and remains `None` in MVP.
- Freeze a concrete Protocol Contract during Step 0 before moving to `scoped`.
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

- Direct primitives are safe only for native complete-binding verification.
- Native partial binding requires final-binding enumeration + subset match.
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

This blueprint has a mandatory contract-freezing Step 0.

The likely landing shape is:

- `src/kernel/application/protocol/derivation_check.py`
  - request DTO
  - result DTO
  - evidence envelope DTO or equivalent JSON-compatible envelope
  - status literals / validation helpers if needed
- `src/kernel/application/derivation_check_runtime.py`
  - pure runtime function, likely:
    - `check_derivation_binding(request, *, store, registry=None) -> CheckResult`
  - uses application/current-store projection APIs, not SDK state
- `src/kernel/application/__init__.py` and `src/kernel/application/protocol/__init__.py`
  - exports only after Step 0 freezes names
- tests under `src/kernel/tests/`
  - protocol shape tests
  - runtime behavior tests
  - SDK delegate tests only if SDK shell is in scope

Step 0 may revise file names / DTO names. The layer placement is not negotiable: substrate starts in `kernel.application`.

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

- [ ] Step 0 freezes the Protocol Contract before status moves from `draft` to `scoped`.
- [ ] Check protocol DTO(s) live under `kernel.application.protocol`.
- [ ] CheckRequest DTO schema rejects `store`, `registry`, and precomputed `rule_ref_resolutions` fields.
- [ ] Check runtime lives under `kernel.application` and takes dependencies via explicit side-channel parameters.
- [ ] Complete native binding pass/fail behavior is covered by tests.
- [ ] Partial native binding pass/fail and multi-match behavior are covered by tests.
- [ ] Tests prove partial binding is not evaluated by directly calling `_branch_satisfies` on the partial input.
- [ ] Deterministic primary selection is covered by tests, including OR branch order.
- [ ] RuleRef with/without registry behavior is covered by tests.
- [ ] Invalid binding shape (for example illegal variable name or wrong binding container type) maps to `status="invalid_request"`.
- [ ] Native evidence envelope is inspectable / serializable and preserves support metadata.
- [ ] EvidenceEnvelope round-trips engine-native payload without flattening away engine-specific fields.
- [ ] Non-native representability boundary is covered by tests for at least the scoped engine set.
- [ ] `branch_atom_projection=None` is tested as "projection not implemented", not "evidence degraded".
- [ ] Affected application docs are updated.
- [ ] If an SDK shell is added, SDK docs/tests prove it is a delegate and not a substrate.
- [ ] No release-base / publish / projection action is performed.

## 8. Implementation Plan

1. **Step 0 — Source-backed Protocol Contract spike (draft gate)**
   - Read current `kernel.application` protocol/runtime patterns.
   - Read current native candidate/evidence construction path.
   - Freeze request DTO shape:
     - rule reference shape
     - binding wire shape and normalization
     - engine field
     - optional identity/query/run fields, or explicit non-decision
     - engine_options decision
   - Freeze result DTO shape:
     - status-by-field nullable matrix
     - errors/warnings convention
     - EvidenceEnvelope field name and nesting
     - native_payload inspectable/serializable contract
     - `branch_atom_projection=None` reserved slot
   - Freeze algorithms:
     - native complete path
     - native partial enumeration + subset-match path
     - deterministic primary sort key
     - RuleRef resolution and failure behavior
     - non-native representability rule for the scoped engine set
   - Freeze runtime failure mapping and test matrix.
   - Freeze drift-prevention mechanisms:
     - review topic doc §7.1-§7.6 one by one
     - record each prevention/detection decision in the audit log
     - include explicit anti-regression tests for every trap kept in scope
   - Update audit with final Step 0 decisions.

2. **Step 1 — Protocol DTO(s)**
   - Add protocol module(s) and exports.
   - Add protocol shape / validation tests.

3. **Step 2 — Native runtime MVP**
   - Implement application runtime for native complete + partial Check.
   - Build derived EvidenceEnvelope from selected primary full binding.
   - Add native runtime tests.

4. **Step 3 — RuleRef and deterministic primary hardening**
   - Add RuleRef tests and exact invalid_request details.
   - Add multi-branch/multi-match deterministic tests.

5. **Step 4 — Scoped engine boundary**
   - Implement non-native behavior only for the engine set frozen by Step 0.
   - If representability cannot be proven for an engine/binding shape, return `unsupported`.
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
