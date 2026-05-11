# Task Blueprint: Engine Ext Decomposition

- Status: draft
- Created: 2026-05-11
- Last Updated: 2026-05-11
- Related Modules:
  - `src/kernel/sdk/`
  - `src/kernel/application/`
  - `src/kernel/core/store/`
  - `src/kernel/adapters/problog/`
  - `src/kernel/adapters/pyreason/`
  - `src/service/`
- Related Docs:
  - [docs/references/working/design-points/rule-policy-function-tree-and-syntax.zh.md](../../references/working/design-points/rule-policy-function-tree-and-syntax.zh.md)
  - [docs/references/working/design-points/possibility-probability-transmission.zh.md](../../references/working/design-points/possibility-probability-transmission.zh.md)
  - [docs/blueprints/archive/2026-05-11_derivation-mode-to-callsite.md](../archive/2026-05-11_derivation-mode-to-callsite.md)
  - [docs/blueprints/archive/2026-05-11_branch-confidence-decomposition.md](../archive/2026-05-11_branch-confidence-decomposition.md)
- Audit Log:
  - [2026-05-11_engine-ext-decomposition.audit.md](./2026-05-11_engine-ext-decomposition.audit.md)

## 1. Problem

Track 3 is decomposing public rule / derivation surfaces before introducing
`SemanticsProfile`.

A1 removed public `Derivation.mode` because engine choice is call-time
runtime semantics, not rule definition structure. A2 replaced public
`Body` with structure-only `Branch`, removed branch-level `confidence`, and
left `ProbLogRuleExt.branch_probabilities` as the temporary public fallback.

A3 handles the next and largest public-surface shortcut: `engine_ext`.

The current shape lets engine-specific semantics live on standard business
rules:

- `Rule.engine_ext` and `Derivation.engine_ext` are public SDK dataclass
  fields.
- `ProbLogRuleExt(branch_probabilities=...)` carries ProbLog OR-branch
  probabilities.
- `PyReasonRuleExt(timestep_delay=..., body_predicate_bounds=...,
  head_bound=...)` carries PyReason rule delay and interval annotations.
- SDK evaluation extracts `derivation.engine_ext` and forwards it through
  application protocol / core store runtime to adapters.
- Docs currently describe `engine_ext` as definition-time semantics that
  travel with rules / derivations.

That shape conflicts with the Track 3 design principle:

```text
Rule / Derivation = standard business template
Engine Semantics = runtime projection / adapter-specific interpretation
```

`engine_ext` is useful as an internal adapter lowering target, but it should
not remain the preferred public rule contract. Public users should not need to
import adapter-local extension dataclasses to express business rule structure.

## 2. Goals

- Remove public SDK `Rule.engine_ext` and `Derivation.engine_ext`.
- Reject public authoring and service derivation payloads that try to carry
  `engine_ext`.
- Keep standard `Rule` / `Derivation` objects as engine-independent business
  templates.
- Preserve adapter-local extension types as internal transitional lowering
  targets until SemanticsProfile and adapter migrations land.
- Preserve non-public internal bridge paths only where needed to avoid
  rewriting ProbLog / PyReason adapter internals inside A3.
- Update release-facing docs so they no longer teach public
  `Rule(..., engine_ext=...)` / `Derivation(..., engine_ext=...)` syntax.
- Record the temporary public functionality gap explicitly: after A3,
  ProbLog branch weights and PyReason rule intervals/delays will not have a
  durable public SDK rule-definition entry until SemanticsProfile lands.

## 3. Non-goals

- Do not introduce `SemanticsProfile` in A3.
- Do not migrate ProbLog or PyReason adapters to consume SemanticsProfile.
- Do not remove `ProbLogRuleExt`, `PyReasonRuleExt`, or `EngineExtBase` from
  adapter/core internals in this slice unless scope-freeze proves a narrower
  deletion is safe.
- Do not change ProbLog branch-probability math.
- Do not change PyReason rule compilation math, timestep semantics, head
  bounds, or body predicate interval semantics.
- Do not remove the internal `body_confidences` bridge retained by A2.
- Do not touch `condition_weights`; that is Track 3 / A4.
- Do not redesign the SDK call-site shape or projection-inspection API; that
  is Track 3 / E.

## 4. Current Context

### 4.1 Track 3 Roadmap

```text
A1. Derivation.mode -> call-site engine selection        done
A2. Body.confidence + Body -> Branch                     done
A3. engine_ext public surface -> internal adapter target this blueprint
A4. condition_weights -> certainty_projection decision
B.  SemanticsProfile data shape and transmission scaffolding
C.  ProbLog adapter migration
D.  PyReason adapter migration
E.  SDK call-site shape and optional projection inspection API
```

### 4.2 Source Audit Summary

The initial A3 audit found 33 Python files that mention `engine_ext`,
`EngineExtBase`, `ProbLogRuleExt`, `PyReasonRuleExt`, or their concrete
engine fields.

Layer findings:

| Layer | Current shape | A3 implication |
| --- | --- | --- |
| SDK DSL | `Rule.engine_ext` and `Derivation.engine_ext` public fields in `src/kernel/sdk/dsl/rule.py` | Primary public surface to remove |
| SDK evaluation | `SDKStore.evaluate(...)` extracts `getattr(derivation, "engine_ext", None)` and passes it to `_compiled_derivation_plan_to_application(...)` | Must stop sourcing engine semantics from rule objects |
| SDK shells | Check / Diagnose / Fact Overlay / Why-not shells pass `getattr(derivation, "engine_ext", None)` | Must align with SDK evaluate behavior |
| Application protocol | `CompiledDerivationPlan.engine_ext: EngineExtBase | None` validates and forwards typed extensions | Candidate internal bridge to retain until B/C/D |
| Core store runtime | `evaluate_store(...)` and `Store.evaluate_engine(...)` accept `engine_ext` and forward to adapters | Candidate internal bridge to retain |
| Service runtime | `_resolve_runtime_derivation_engine_ext(...)` resolves compiled `engine_ext`, with ProbLog `body_confidences` bridge | Public DTO should reject `engine_ext`; internal bridge may stay |
| Authoring compile | No explicit `engine_ext` handling; SDK `to_authoring_payload()` already omits it | A3 should reject user-authored `engine_ext` rather than silently ignoring it |
| ProbLog adapter | `ProbLogRuleExt.branch_probabilities` plus `resolve_problog_engine_ext(...)` and `legacy_body_confidences` conflict detection | Keep as internal target in A3; public replacement comes later |
| PyReason adapter | `PyReasonRuleExt.timestep_delay`, `body_predicate_bounds`, `head_bound`; `where_compile.py` uses duck-typed `engine_ext` accessors | Keep as internal target in A3; public replacement comes later |
| Docs | SDK docs teach `engine_ext` as definition-time semantics; PyReason docs teach `Rule(..., engine_ext=PyReasonRuleExt(...))` | G3 docs sync must remove public teaching and mark internals transitional |

Key asymmetry:

- Authoring serialization already omits SDK `engine_ext`.
- Runtime object evaluation still uses SDK object `engine_ext`.
- Service runtime cannot construct adapter dataclasses from JSON today, but it
  can still silently ignore or internally forward compiled `engine_ext`.

This means A3 is more about public-surface removal and rejection barriers than
about adapter algorithm changes.

## 5. Proposed Shape

### 5.0 Draft Decisions

The draft direction is:

| ID | Draft decision |
| --- | --- |
| D1 | Remove public SDK `Rule.engine_ext`. |
| D2 | Remove public SDK `Derivation.engine_ext`. |
| D3 | Do not keep a public `engine_ext` alias or tombstone field on SDK rule objects. |
| D4 | Add explicit authoring compile rejection for payload key `engine_ext`, redirecting to future SemanticsProfile. |
| D5 | Add explicit service request rejection for top-level and derivation-level `engine_ext`, redirecting to future SemanticsProfile. |
| D6 | Retain `EngineExtBase`, `CompiledDerivationPlan.engine_ext`, core `evaluate(..., engine_ext=...)`, and adapter-local ext dataclasses as internal transitional bridges for this slice. |
| D7 | Retain `ProbLogRuleExt.branch_probabilities` and `PyReasonRuleExt` internals, but remove release-facing docs that present them as the public SDK rule-definition entry. |
| D8 | Accept a temporary public functionality gap: engine-specific rule projection has no durable public SDK entry between A3 and SemanticsProfile B/C/D. |

These are not yet scope-frozen. G0 should decide whether D6 stays broad or is
narrowed further for specific layers.

### 5.1 User-Facing Shape After A3

Preferred public syntax remains engine-independent:

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

fg.eval.evaluate(drv, mode="problog")
```

Not allowed after A3:

```python
Rule(..., engine_ext=PyReasonRuleExt(...))
Derivation(..., engine_ext=ProbLogRuleExt(...))
{"engine_ext": {...}, ...}
```

Future target shape is intentionally not implemented in A3:

```python
fg.rules.evaluate(
    drv,
    engine="problog",
    semantics=SemanticsProfile(
        rule_projection=...,
    ),
)
```

## 6. Boundaries And Invariants

Draft invariants to tighten at scope-freeze:

- Public SDK:
  - `Rule` dataclass fields do not include `engine_ext`.
  - `Derivation` dataclass fields do not include `engine_ext`.
  - `Rule(..., engine_ext=...)` and `Derivation(..., engine_ext=...)` raise
    `TypeError` or a more specific SDK validation error.
  - `to_authoring_payload()` continues not to emit `engine_ext`.
- Public payloads:
  - authoring derivation payloads with `engine_ext` reject with redirect text
    to future SemanticsProfile.
  - service top-level `engine_ext` rejects.
  - service `derivation.engine_ext` rejects.
- Internal bridges:
  - `EngineExtBase` remains available for adapter internals unless G0 narrows
    this.
  - `CompiledDerivationPlan.engine_ext` remains available for adapter internals
    unless G0 narrows this.
  - ProbLog `legacy_body_confidences` remains available as retained by A2.
  - PyReason rule compilation behavior remains unchanged in internal tests.
- Docs:
  - Release-facing docs no longer teach `engine_ext` as public SDK syntax.
  - Remaining `engine_ext` mentions are limited to internal bridge,
    rejection, historical archive, or future-migration context.

## 7. Acceptance

Draft gates for G0 to make exact:

- [ ] Red baseline covers `Rule` / `Derivation` public `engine_ext` fields.
- [ ] Red baseline covers `Rule(..., engine_ext=...)` and
      `Derivation(..., engine_ext=...)` constructor rejection.
- [ ] Red baseline covers authoring payload `engine_ext` rejection.
- [ ] Red baseline covers service top-level and derivation-level
      `engine_ext` rejection.
- [ ] Guard tests prove adapter-local `ProbLogRuleExt` / `PyReasonRuleExt`
      still exist as internal transitional targets.
- [ ] Guard tests prove A2 `body_confidences` internal bridge still works.
- [ ] Targeted ProbLog tests still pass.
- [ ] Targeted PyReason tests still pass, or any moved public tests are
      explicitly rewritten as adapter-internal tests.
- [ ] No `SemanticsProfile` implementation appears in A3.
- [ ] Release-facing docs stale-syntax grep is clean for public
      `Rule(..., engine_ext=...)` / `Derivation(..., engine_ext=...)`.

## 8. Implementation Plan

Expected cadence, matching A1/A2:

1. G0 scope-freeze:
   - lock D1-D8;
   - decide exactly how much of D6 internal bridge remains;
   - tighten §6 / §7 into testable form;
   - record scope-freeze in audit.
2. G1 red baseline:
   - add forward-failing public-surface tests;
   - add passing guards for retained adapter internals.
3. G2 implementation:
   - remove SDK `engine_ext` fields from `Rule` / `Derivation`;
   - stop SDK evaluate and SDK shells from reading object-level
     `engine_ext`;
   - reject public authoring / service payload `engine_ext`;
   - keep internal adapter bridges needed by D6.
4. G3 docs sync:
   - update SDK, core, adapter, authoring, and service docs;
   - run stale-syntax grep gate over release-facing docs.
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
- `src/kernel/adapters/docs/03_pyreason_adapter.md`
- `src/kernel/authoring/docs/README.md`
- `src/kernel/authoring/docs/01_overview.md`
- `src/kernel/core/docs/01_architecture.en.md`
- `src/kernel/core/docs/04_public_contract_v1.md`
- `src/service/docs/`

## 10. Outcome / Deviations

Task completion will fill:

- Final landed behavior:
- Deviations from blueprint:
- Rationale for deviations:
- Archive notes:
