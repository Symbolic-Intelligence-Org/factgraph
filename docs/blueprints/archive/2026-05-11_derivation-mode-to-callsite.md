# Task Blueprint: Derivation Mode To Call-Site

- Status: implemented
- Created: 2026-05-11
- Last Updated: 2026-05-11
- Related Modules:
  - `src/kernel/sdk/`
  - `src/kernel/authoring/`
  - `src/kernel/application/`
  - `src/kernel/core/store/`
  - `src/service/`
- Related Docs:
  - [docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md](../../references/working/design-points/rule-policy-function-tree-and-syntax.zh.md)
  - [docs/references/working/design-points/possibility-probability-transmission.zh.md](../../references/working/design-points/possibility-probability-transmission.zh.md)
  - [docs/blueprints/archive/2026-05-11_uncertainty-transmission-layer.md](./2026-05-11_uncertainty-transmission-layer.md)
  - [docs/blueprints/archive/2026-05-11_uncertainty-transmission-layer.audit.md](./2026-05-11_uncertainty-transmission-layer.audit.md)
- Audit Log:
  - [2026-05-11_derivation-mode-to-callsite.audit.md](./2026-05-11_derivation-mode-to-callsite.audit.md)

## 1. Problem

The Engine Semantics Unification direction needs public rule and derivation
definitions to behave as standard business templates. Engine selection is
runtime semantics, but `Derivation.mode` currently allows an engine choice to
live on the derivation definition.

That creates the same class of coupling as `Body.confidence`, `engine_ext`, and
`condition_weights`: the logical rule shape starts carrying execution semantics.
If `SemanticsProfile` is introduced before these public surfaces are decomposed,
the old fields will constrain the new design and duplicate engine selection
across definition-time and call-time APIs.

This blueprint is Track 3 / A1. It handles only `Derivation.mode` as the first
small public-surface decomposition slice.

## 2. Goals

- Make the public `Derivation` definition engine-neutral.
- Keep engine selection at the evaluation call site.
- Decide the fate of structured authoring payload `mode` in dict / service paths.
- Preserve the existing runtime engine dispatch behavior once the engine is
  supplied at call time.
- Update affected SDK, authoring, core, adapter, and service docs so they do not
  teach `Derivation(..., mode=...)` as a public contract.

## 3. Non-goals

- Do not introduce `SemanticsProfile` in this slice.
- Do not migrate `Body.confidence` / `body_confidences`.
- Do not migrate `engine_ext`, `ProbLogRuleExt`, or `PyReasonRuleExt`.
- Do not migrate `condition_weights`.
- Do not change ProbLog / PyReason adapter semantics.
- Do not change `engine_options` except where docs need to clarify that it is
  call-time runtime configuration.
- Do not revisit legacy `mode='python'` / `mode='engine'` value errors unless
  tests require touched call-site validation to stay coherent.

## 4. Current Context

### 4.1 Track 3 Roadmap

The source-grounded audit found that Engine Semantics Unification should be
decomposed before adding a large profile abstraction:

```text
A1. Derivation.mode -> call-site engine selection
A2. Body.confidence / body_confidences -> rule_projection.problog branch weights
A3. engine_ext public surface -> internal adapter lowering target
A4. condition_weights -> certainty_projection / rule_projection decision
B.  SemanticsProfile data shape and transmission scaffolding
C.  ProbLog adapter migration
D.  PyReason adapter migration
E.  SDK call-site shape and optional projection inspection API
```

A1 is deliberately small. Its job is to remove the easiest definition-time
engine selector before the larger `engine_ext` and branch-weight migrations.

### 4.2 Current Implementation Entrypoints

- SDK object surface:
  - `src/kernel/sdk/dsl/rule.py`
    - `Derivation.mode` exists on the dataclass.
    - `Derivation.to_authoring_payload()` emits `mode` when present.
- Authoring compiler:
  - `src/kernel/authoring/derivation_compile.py`
    - `_compile_mode(...)` defaults missing mode to `native`.
    - compiled payload always includes `mode`.
- SDK evaluation:
  - `src/kernel/sdk/store.py`
    - `_resolve_compiled_derivation_mode(...)` uses call-site `mode` when
      supplied, otherwise uses modes embedded in compiled plans.
    - mixed embedded modes require explicit call-site mode.
- Application protocol/runtime:
  - `src/kernel/application/protocol/derivation.py`
    - `DerivationEvaluateRequest.engine` is already the runtime engine field.
  - `src/kernel/application/derivation_runtime.py`
    - evaluates every compiled plan using `request.engine`.
- Core runtime:
  - `src/kernel/core/store/_evaluate.py`
  - `src/kernel/core/store/runtime.py`
    - `Store.evaluate(..., mode=...)` and `Store.evaluate_engine(...)` are
      already call-time dispatch surfaces.
- Service runtime:
  - `src/service/runtime_v1.py`
    - `evaluate_runtime_derivation(...)` currently calls `Store.evaluate` with
      `mode=compiled["mode"]`.
    - Verified during source audit: service is currently D5b, not D5a. It does
      not yet use a request-level engine field for derivation evaluation.

### 4.3 Related Design Notes

- `rule-policy-function-tree-and-syntax.zh.md` now recommends no engine field on
  `Derivation`; call-site `engine/profile` should outrank policy default and
  system default.
- `possibility-probability-transmission.zh.md` separates logical structure,
  data-level raw uncertainty, and runtime `SemanticsProfile`.

## 5. Proposed Shape

### 5.0 Scope Freeze Decisions

The A1 slice locks the following decisions:

| ID | Decision | Locked Shape |
| --- | --- | --- |
| D1 | SDK `Derivation.mode` field | Remove directly from the public SDK dataclass. No compatibility shim is required because the project is pre-release. |
| D2 | SDK object `to_authoring_payload()` emission | Stop emitting `payload["mode"]` from `Derivation` objects. This follows from D1. |
| D3 | Structured authoring dict `mode` key | Reject `mode` inside derivation authoring payloads with a clear redirect to call-site engine selection. |
| D4 | Compiled payload `mode` key | Keep a runtime-internal default `mode="native"` in compiled payloads only where needed for minimal internal compatibility. It is no longer sourced from user derivation definitions. |
| D5 | Service engine source | Rewire runtime derivation evaluation to use request-level engine selection. Application protocol already has `DerivationEvaluateRequest.engine`; service v1 should use a top-level request field rather than `compiled["mode"]`. |

D5 implementation detail: the service endpoint currently receives a raw DTO,
not `DerivationEvaluateRequest` directly. The scoped implementation should add a
small service-local resolver for top-level engine selection. Prefer `engine` as
the request key if feasible; allow or reject top-level `mode` explicitly during
implementation scoping, but do not allow `derivation.mode`.

### 5.1 User-Facing Shape

Preferred direction:

```python
drv = Derivation(
    id="drv.risk_review",
    version="1.0.0",
    where=[Branch([Asset(a), Risk.score(a, "risk_high")])],
    head=ReviewRequired(asset=a),
)

candidates = fg.rules.evaluate(drv, mode="pyreason")
```

Definition-time engine selection should disappear from documented public
`Derivation(...)` shape. The call-site field may still be named `mode` in A1 to
keep scope small; a future SemanticsProfile/API-shape blueprint can decide
whether to rename it to `engine`.

Draft implementation choices to validate before scoping:

- `Derivation(...)` object definitions do not accept `mode`.
- Structured derivation dicts do not accept `mode`.
- Evaluation calls supply engine selection.
- Internals may keep a default `native` compiled mode only as a private bridge
  while call sites are rewired.

The cleaner target is:

```text
Derivation payload:
  id / version / where / head / target / head_vars

Evaluate request:
  engine or mode
  engine_options
  future profile / semantics
```

## 6. Boundaries And Invariants

- `Rule` / `Derivation` remain business logic templates, not engine execution
  profiles.
- Call-site engine selection remains supported for `native`, `souffle`,
  `problog`, and `pyreason`.
- `engine_options` stays call-time only and must not enter `Derivation`.
- No adapter output should change in this slice for equivalent call-site engine
  selections.
- Because the project is not online, no long compatibility period is required;
  however, all removals must be explicit and tested.
- Existing unrelated notebook changes in the worktree are out of scope.
- Archived examples under `examples/archive/` are not part of this slice unless
  active docs link to them as current guidance.

## 7. Acceptance

- [x] SDK public docs no longer describe `Derivation(..., mode=...)`.
- [x] SDK `Derivation(...)` no longer exposes a public `mode` field.
- [x] SDK `Derivation.to_authoring_payload()` no longer emits definition-time
      mode.
- [x] Structured derivation payloads reject `mode` with a call-site redirect.
- [x] SDK object path evaluates through call-site `mode` only.
- [x] Service runtime derivation evaluation uses a request-level engine/mode
      resolver instead of `compiled["mode"]`.
- [x] Existing call-site `evaluate(..., mode="native"|"souffle"|"problog"|"pyreason")`
      behavior remains covered.
- [x] Non-native examples use call-site engine selection.
- [x] No `SemanticsProfile`, `engine_ext`, `body_confidences`, or
      `condition_weights` migration is included.
- [x] Affected module docs are updated.

## 8. Implementation Plan

Scoped sequence:

1. Add failing tests for D1-D5:
   - SDK object rejects or cannot accept `Derivation(mode=...)`;
   - SDK object payload has no `mode`;
   - structured derivation dict rejects `mode`;
   - service request-level engine selection still reaches non-native evaluation;
   - service rejects `derivation.mode`.
2. Remove SDK `Derivation.mode` and its payload emission.
3. Update authoring compiler to reject user-supplied derivation `mode` while
   retaining internal `native` default if needed by downstream compiled-plan
   code.
4. Rewire service runtime derivation evaluation to resolve engine selection from
   the request level, not from the compiled derivation.
5. Update active docs and examples that currently show `Derivation(..., mode=...)`.
6. Run focused SDK / authoring / service / adapter regression tests.
7. Fill Outcome / Deviations and archive.

## 9. Docs To Update

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/adapters/docs/02_problog_adapter.md`
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/core/docs/04_public_contract_v1.md`
- `src/kernel/core/docs/04_service_layer.md`
- `src/kernel/authoring/docs/01_overview.md`
- `src/service/docs/03_runtime_queries_policy.md`
- `docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md`
  if the final A1 decision differs from the current recommendation.

## 10. Outcome / Deviations

最终落地结果：

- SDK `Derivation` definitions no longer expose or emit definition-time
  `mode`.
- Structured authoring derivation payloads reject `mode` with a call-site
  engine-selection redirect.
- Compiled derivation payloads retain an internal default `mode="native"` only
  as a downstream compatibility bridge.
- SDK call-site `evaluate(..., mode=...)` remains the engine selection surface
  for `native`, `souffle`, `problog`, and `pyreason`.
- Service runtime derivation evaluation now reads top-level `engine`, rejects
  `derivation.mode`, and no longer dispatches from `compiled["mode"]`.
- Release-facing SDK / adapter docs now teach call-site engine selection.

与 blueprint 不同的地方：

- The scoped D5 wording allowed implementation to either accept or reject
  top-level service `mode`. The implementation rejects top-level service
  `mode` and accepts only top-level `engine`.
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md` and most docs listed in
  §9 did not need edits because they already used call-site engine selection or
  did not teach `Derivation(..., mode=...)`.

为什么会有这些调整：

- Rejecting service top-level `mode` keeps the service DTO aligned with
  `DerivationEvaluateRequest.engine` and avoids extending `mode` semantics
  before the broader `SemanticsProfile` API shape is designed.
- Keeping compiled `mode="native"` minimizes downstream churn while removing
  user-authored definition-time engine selection.

归档说明：

- A1 closed as the first Track 3 public-surface decomposition slice.
- Deferred slices remain unchanged: `Body.confidence` / `body_confidences`,
  `engine_ext`, `condition_weights`, `SemanticsProfile`, and adapter migration.
- Known standalone import-order noise in audit/provenance tests is pre-existing
  and was not changed by this slice.
