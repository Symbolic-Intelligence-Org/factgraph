# Task Blueprint: Branch Confidence Decomposition

- Status: draft
- Created: 2026-05-11
- Last Updated: 2026-05-11
- Related Modules:
  - `src/kernel/sdk/`
  - `src/kernel/authoring/`
  - `src/kernel/core/store/`
  - `src/kernel/adapters/problog/`
  - `src/service/`
- Related Docs:
  - [docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md](../../references/working/design-points/rule-policy-function-tree-and-syntax.zh.md)
  - [docs/references/working/design-points/possibility-probability-transmission.zh.md](../../references/working/design-points/possibility-probability-transmission.zh.md)
  - [docs/blueprints/archive/2026-05-11_derivation-mode-to-callsite.md](../archive/2026-05-11_derivation-mode-to-callsite.md)
  - [docs/blueprints/archive/2026-05-11_derivation-mode-to-callsite.audit.md](../archive/2026-05-11_derivation-mode-to-callsite.audit.md)
- Audit Log:
  - [2026-05-11_branch-confidence-decomposition.audit.md](./2026-05-11_branch-confidence-decomposition.audit.md)

## 1. Problem

Track 3 is decomposing public rule / derivation surfaces before introducing
`SemanticsProfile`. A1 removed `Derivation.mode` because engine selection is
runtime semantics, not rule definition structure.

A2 handles the next scattered engine-specific public surface:

- `Body.confidence` is a branch-level SDK DSL parameter that feeds ProbLog
  branch probability.
- `body_confidences` is a generic-looking compiled / authoring field, but the
  narrow audit found only the ProbLog adapter consumes it.
- `ProbLogRuleExt.branch_probabilities` is a parallel public path for the same
  engine concept and already conflicts with `body_confidences`.

The current shape is misleading in two ways:

1. The public name `Body` does not describe the structure it represents. It is
   a branch alternative in a rule / derivation `where`, not the whole rule body.
2. The public parameter `confidence` looks like a general confidence carrier,
   but its effective use is ProbLog branch probability.

The source audit makes the boundary clear:

- `body_confidences` has about 81 references across core IR, SDK plumbing,
  authoring validation, service pass-through, docs, and tests.
- `Body` has about 112 literal references across source and examples.
- Native, Souffle, and PyReason do not consume `body_confidences`.
- The only real consumer is the ProbLog bridge in
  `kernel/adapters/problog/rule_ext.py`, where the parameter is already named
  `legacy_body_confidences`.

Because the project is pre-release, A2 should take the clean public-surface cut:
rename `Body` to `Branch`, remove branch-level `confidence`, reject public
`body_confidences`, and leave the internal ProbLog bridge in place only until
the later SemanticsProfile / ProbLog migration slices.

## 2. Goals

- Rename public SDK `Body` to `Branch`.
- Remove public SDK `Body.confidence` / `Branch.confidence`.
- Keep `Branch` as pure branch structure with no engine-specific parameters.
- Reject user-authored `body_confidences` in authoring and service request
  payloads.
- Preserve internal compiled `body_confidences` only as a temporary ProbLog
  adapter bridge where existing internals still need it.
- Leave `ProbLogRuleExt.branch_probabilities` as the temporary public fallback
  for ProbLog branch probabilities until A3 / Phase C.
- Update active docs so user-facing rule examples teach `Branch([...])` and
  do not teach branch probability through `Body(..., confidence=...)`.

## 3. Non-goals

- Do not introduce `SemanticsProfile`.
- Do not migrate or remove `engine_ext` / `ProbLogRuleExt.branch_probabilities`;
  that is A3 scope.
- Do not change ProbLog mathematical semantics or adapter output.
- Do not change Native, Souffle, or PyReason adapter behavior.
- Do not remove the internal `body_confidences` IR field in this slice.
- Do not rename or redesign branch fields beyond removing `confidence`.
- Do not perform the broader rule syntax / policy / function tree redesign.

## 4. Current Context

### 4.1 Track 3 Roadmap

```text
A1. Derivation.mode -> call-site engine selection        done
A2. Body.confidence / body_confidences + Body -> Branch  this blueprint
A3. engine_ext public surface -> internal adapter target
A4. condition_weights -> certainty_projection decision
B.  SemanticsProfile data shape and transmission scaffolding
C.  ProbLog adapter migration
D.  PyReason adapter migration
E.  SDK call-site shape and optional projection inspection API
```

### 4.2 Source Audit Summary

Two related entities currently exist:

| Entity | Current role | Audit result |
| --- | --- | --- |
| `Body.confidence` | SDK DSL branch probability shorthand | Public ProbLog-specific shortcut |
| `body_confidences` | Compiled / authoring list field | Generic type, ProbLog-only consumer |

Layer findings:

- SDK:
  - `src/kernel/sdk/dsl/body.py` defines `Body` and validates
    `confidence`.
  - `src/kernel/sdk/store.py` contains wrapper coercion / merge / validation
    plumbing for `body_confidences`.
- Core IR:
  - `src/kernel/core/store/types.py` exposes `body_confidences` on
    `RuleSpec` and `DerivationSpec`.
  - `src/kernel/core/derivation/candidates.py` mirrors validation-related
    paths.
- Authoring:
  - `src/kernel/authoring/derivation_compile.py` validates
    `body_confidences` as probability-shaped values.
  - `src/kernel/authoring/rule_dsl_parse.py` normalizes `Body(...)` wrappers.
- Adapter:
  - `src/kernel/adapters/problog/rule_ext.py` is the only real consumer and
    calls the path `legacy_body_confidences`.
  - The same adapter detects conflicts between
    `engine_ext.branch_probabilities` and `body_confidences`.
- Service:
  - `src/service/runtime_v1.py` passes compiled `body_confidences` to the
    ProbLog bridge but does not own independent semantics.
- Docs:
  - Current authoring docs already describe `body_confidences` as a ProbLog
    example, despite the engine-neutral field name.

## 5. Proposed Shape

### 5.0 Draft Decisions

These are draft decisions. They should be converted to locked decisions at
scope-freeze if source audit and red-baseline tests confirm the surface.

| ID | Draft Decision | Current Direction |
| --- | --- | --- |
| D1 | SDK `Body.confidence` | Hard remove. No deprecation shim because the project is pre-release. |
| D2 | Public branch wrapper name | Rename `Body` to `Branch`; do not keep a public `Body` alias. |
| D2a | SDK DSL file name | Rename `src/kernel/sdk/dsl/body.py` to `src/kernel/sdk/dsl/branch.py`. |
| D3 | `Branch` parameters | `Branch` represents branch structure only; no `confidence`, `engine_*`, or adapter-specific kwargs. |
| D4 | Internal `body_confidences` IR | Retain as an internal ProbLog bridge for this slice, matching the existing `legacy_body_confidences` adapter naming. |
| D5 | Authoring payload `body_confidences` | Reject public `body_confidences` with a redirect to future `SemanticsProfile.rule_projection.problog` or temporary `ProbLogRuleExt.branch_probabilities`. |
| D6 | Service request `body_confidences` | Reject public top-level / derivation-level request payload `body_confidences`; service may still pass internal compiled values where they exist. |
| D7 | ProbLog branch probability transition | After A2, the only public branch-probability fallback is `ProbLogRuleExt.branch_probabilities` until A3 / Phase C replaces it with SemanticsProfile projection. |
| D8 | Absence invariant | `from kernel.sdk import Body` should fail; `Branch` is the sole public SDK name. |

### 5.1 User-Facing Shape

Preferred public syntax after A2:

```python
from kernel.sdk import Branch, Derivation, Pred

drv = Derivation(
    id="drv.user_tag",
    version="1.0.0",
    where=[
        Branch([Pred("user:tag_seed", u, tag)]),
        Branch([Pred("user:tag_hint", u, tag)]),
    ],
    target="user:tag",
    head_vars=[u, tag],
)
```

Not allowed after A2:

```python
Body([Pred("user:tag_seed", u, tag)], confidence=0.9)
Branch([Pred("user:tag_seed", u, tag)], confidence=0.9)
{"body_confidences": [0.9, 0.6], ...}
```

Temporary ProbLog fallback until A3 / Phase C:

```python
from kernel.adapters.problog.rule_ext import ProbLogRuleExt

drv = Derivation(
    id="drv.user_tag",
    version="1.0.0",
    where=[
        Branch([Pred("user:tag_seed", u, tag)]),
        Branch([Pred("user:tag_hint", u, tag)]),
    ],
    target="user:tag",
    head_vars=[u, tag],
    engine_ext=ProbLogRuleExt(branch_probabilities=(0.9, 0.6)),
)
```

This fallback is explicitly transitional. A3 owns public `engine_ext`
decomposition; Phase B/C owns the future SemanticsProfile / ProbLog projection
path.

## 6. Boundaries And Invariants

- Public SDK exports `Branch`, not `Body`.
- Public SDK `Branch` has no `confidence` field.
- `from kernel.sdk import Body` is an absence invariant and should fail.
- `Body([...])` should not appear in release-facing docs or active examples.
- `Branch([...], confidence=...)` should fail explicitly.
- User-authored authoring payloads reject `body_confidences`.
- Service runtime request DTOs reject top-level and derivation-level
  `body_confidences`.
- Existing ProbLog branch-probability behavior remains reachable through
  `ProbLogRuleExt.branch_probabilities`.
- Native, Souffle, and PyReason behavior should be unchanged for equivalent
  branch structure.
- Internal `body_confidences` may remain in compiled IR only as a temporary
  bridge; it must not be documented as a public contract.
- Existing unrelated notebook changes in the worktree are out of scope.

## 7. Acceptance

- [ ] Red baseline tests cover the current public `Body` export,
      `Body.confidence`, public `body_confidences`, and service request
      acceptance.
- [ ] SDK public `Branch` exists and can be imported from `kernel.sdk`.
- [ ] SDK public `Body` cannot be imported from `kernel.sdk`.
- [ ] SDK `Branch([...])` lowers to the same branch structure as old
      `Body([...])` without confidence.
- [ ] SDK `Branch([...], confidence=...)` rejects.
- [ ] SDK / authoring public payloads reject `body_confidences`.
- [ ] Service runtime rejects top-level `body_confidences`.
- [ ] Service runtime rejects `derivation.body_confidences`.
- [ ] ProbLog branch probabilities still work through
      `ProbLogRuleExt.branch_probabilities`.
- [ ] No `SemanticsProfile`, `engine_ext` public migration, or adapter
      semantic rewrite is included.
- [ ] Release-facing docs and active examples no longer teach `Body(...)` or
      `Body(..., confidence=...)`.
- [ ] Affected module docs are updated.

## 8. Implementation Plan

Draft sequence:

1. G0 scope-freeze:
   - refine source audit into locked D1-D8 decisions;
   - tighten acceptance gates into exact tests;
   - record scope-freeze in audit.
2. G1 red baseline:
   - add tests proving current `Body` / `confidence` / `body_confidences`
     public surfaces still exist;
   - keep production code unchanged.
3. G2 implementation:
   - rename `body.py` to `branch.py`;
   - replace public `Body` export with `Branch`;
   - remove `confidence` validation and wrapper collection from SDK paths;
   - reject public `body_confidences` in authoring and service DTO paths;
   - preserve internal ProbLog bridge only where still needed.
4. G3 docs sync:
   - update SDK, authoring, core, adapter docs and active examples;
   - run stale-syntax grep gates for `Body(` and `body_confidences` in
     release-facing docs.
5. G4 close-out:
   - fill Outcome / Deviations;
   - mark blueprint implemented;
   - archive blueprint pair and update archive inventory.

## 9. Docs To Update

Expected active docs to inspect:

- `src/kernel/sdk/docs/00_user_guide.en.md`
- `src/kernel/sdk/docs/03_rules_and_derivations.en.md`
- `src/kernel/sdk/docs/04_api_surface.en.md`
- `src/kernel/adapters/docs/02_problog_adapter.md`
- `src/kernel/authoring/docs/README.md`
- `src/kernel/authoring/docs/01_overview.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/core/docs/04_public_contract_v1.md`
- `src/service/docs/`
- active examples / notebooks if they are current guidance and not archived.

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
