# EvaluationOverlay + Fact Scenario Core(Batch 3 of Round Story Completion Plan)

- Status: scoped
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Parent: [2026-05-05_round-story-completion-plan.md](./2026-05-05_round-story-completion-plan.md) §5.3
- Scope: Batch 3 — generic fact-side overlay container; native-only Fact Overlay Check compatibility path
- Branch: `v0.1-evaluation-overlay-2026-05-05`(off `37ec62b`)
- Related Modules:
  - `src/kernel/application/protocol/derivation_fact_overlay.py`
  - `src/kernel/application/fact_overlay_runtime.py`
  - `src/kernel/application/capability_helpers.py`
  - `src/kernel/application/docs/`
  - `src/kernel/tests/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/archive/2026-05-05_capability-ergonomics.md](../archive/2026-05-05_capability-ergonomics.md)
- Audit Log:
  - [2026-05-05_evaluation-overlay.audit.md](./2026-05-05_evaluation-overlay.audit.md)

## 1. Problem

Current Fact Overlay Check supports only a tuple of `FactValueOverride` actions. That works for Q3 "What if this fact were different?", but it is not enough for Batch 3's round-story scenario needs:

- no first-class scenario container for multiple fact actions;
- no fact add/remove actions;
- no reusable DTO that future Batch 4 ProofFrame and Batch 5 rule-side overlays can name as a shared input concept;
- examples still model overlay as "single replace" even after Batch 2 helper ergonomics.

The danger is v0.1.4-style semantic decomposition: `replace`, `add`, and `remove` may look like one DTO because they share "overlay" vocabulary, but they carry different identity and validation requirements. This batch must explicitly prove they are one crisp fact-side action family before implementation. If not, it must suspend or abandon rather than ship a blurred container.

## 2. Goals

- Freeze an `EvaluationOverlay` protocol shape for fact-side actions.
- Implement the subset of fact-side actions that Step 0.A confirms as one crisp fact-action family:
  - replace: current `FactValueOverride` semantics;
  - add: add an overlay-local projected fact without ledger write;
  - remove: remove a visible projected fact without ledger write.
- Keep `FactOverlayCheckRequest` compatible with current `overlay: tuple[FactValueOverride, ...]` callers while adding the new container path.
- Preserve current capability boundary: native-only, read-only, no ledger writes, no live Store cache contamination, no SDK shell.
- Add protocol/runtime tests and drift gates for action semantics, compatibility, and no-write behavior.

## 3. Non-goals

- No rule-side overlay actions(disable / replace condition / add condition); those start in Batch 5.
- No `kernel.sdk` substrate or SDK shell.
- No overlay persistence, audit JSONL, event log, or reload behavior; Batch 6 owns that.
- No cross-engine overlay semantics; non-native remains `ENGINE_OVERLAY_NOT_SUPPORTED`.
- No ProofFrame recheck output or narrative; Batch 4 owns that.
- No status enum unification across Check / Diagnose / Fact Overlay / Why-not.

## 4. Current Context

- Protocol currently has:
  - `FactValueOverride(asrt_id, pred_id, e_ref, old_fact_tuple, new_fact_tuple, note)`;
  - `FactOverlayCheckRequest(plan, binding, overlay, engine)`;
  - `FactOverlayCheckResult(before, after, diff)`.
- Runtime currently:
  - projects `Store` with `project_view_facts_with_witness(...)`;
  - validates visible `FactValueOverride` rows;
  - applies overlay by copying projected witness rows and replacing matching row tuples;
  - evaluates before / after via native `evaluate_native_where(...)`;
  - does not write ledger or live Store caches.
- Batch 2 added `build_fact_value_override(...)`, which remains valid for replace ergonomics.

## 5. Step 0 Questions

### 5.1 Falsifiability Checklist

Step 0.A must try to falsify the "single EvaluationOverlay fact-action family" idea before any DTO is frozen. Record a yes/no conclusion for each item:

- **Durable identity:** if `add` needs ledger identity, durable event identity, audit persistence, or reload semantics to be meaningful, it does not belong in Batch 3.
- **Layer crossing:** if `remove` needs reverse ledger lookup beyond current projected witness rows to validate intent, it crosses out of projection-local overlay.
- **Single vs multi decomposition:** if an action has materially different semantics across `single` and `multi` fields, it may already be multiple actions.
- **Shared validation:** if `replace` / `add` / `remove` have three or more non-shared validation families, the union is likely a fake common DTO.
- **Group-key behavior:** if group-key preservation cannot be expressed uniformly for projection-local actions, the family is not crisp.
- **No-write invariant:** if any action requires `set_field`, `add_field`, `retract_by_asrt`, ledger append, or live Store cache writes, abandon or split.

Step 0.A output must include a decomposition map:

| Action | single field | multi field | Falsifies single-family? |
|---|---|---|---|
| replace | TBD | TBD | TBD |
| add | TBD | TBD | TBD |
| remove | TBD | TBD | TBD |

If the map does not converge, valid outcomes are:

- abandon Batch 3;
- suspend pending product trigger;
- narrow Batch 3 to a smaller crisp subset, such as `replace + remove`, with audit justification.

### 5.2 Action Identity Questions

- `replace`: uses existing visible `asrt_id`; current `FactValueOverride` can map 1:1.
- `remove`: uses existing visible `asrt_id`; must validate `old_fact_tuple` against current projection.
- `add`: may or may not need an overlay-local id. Step 0 must choose one:
  - caller supplies `overlay_asrt_id`;
  - runtime derives deterministic `overlay:<index>`;
  - runtime generates non-deterministic UUID-like id;
  - no id at all; action is transient and only contributes a projected row.

Decision pressure: if `add` needs durable identity to be inspectable, this likely belongs to Batch 6 persistence, not Batch 3 projection overlay.

### 5.3 Cardinality Questions

- `replace`: current validation already enforces arity and group-key stability.
- `remove`: removing a single projected row is straightforward for `multi`; for `single`, removing the selected active row leaves no visible fact for that predicate/e_ref in the overlay.
- `add` for `multi`: candidate meaning is append projected row.
- `add` for `single`: candidate meanings diverge:
  - Option A: reject add on `single`, require replace;
  - Option B: add shadows current selected row in overlay;
  - Option C: support only when no visible row exists.

This divergence is a falsifiability item, not a minor implementation detail. If `single + add` cannot converge to one definition that does not depend on chosen-policy semantics, then `add` cannot share the same action family in this batch. Batch 3 must then abandon, suspend, or ship only the crisp subset.

### 5.4 Helper Migration Question

Batch 2 shipped `build_fact_value_override(...)`. Step 0 must decide whether Batch 3 also ships new helpers, such as `build_fact_replace_action(...)`, `build_fact_remove_action(...)`, or `build_evaluation_overlay(...)`, or explicitly defers helper migration. The decision must not create SDK shell surface.

## 6. Candidate Shapes(Draft)

Step 0.B must choose among explicit alternatives and record rejected reasons.

### Shape A — Three dataclasses + flat union

```python
@dataclass(frozen=True)
class FactReplaceAction:
    asrt_id: str
    pred_id: str
    e_ref: str
    old_fact_tuple: tuple[Any, ...]
    new_fact_tuple: tuple[Any, ...]
    note: str | None = None

@dataclass(frozen=True)
class FactAddAction:
    overlay_asrt_id: str
    pred_id: str
    e_ref: str
    fact_tuple: tuple[Any, ...]
    note: str | None = None

@dataclass(frozen=True)
class FactRemoveAction:
    asrt_id: str
    pred_id: str
    e_ref: str
    old_fact_tuple: tuple[Any, ...]
    note: str | None = None

@dataclass(frozen=True)
class EvaluationOverlay:
    fact_actions: tuple[FactReplaceAction | FactAddAction | FactRemoveAction, ...]
```

Trade-off: clear per-action fields and validation; flat action order is natural. Risk: union can hide that actions are not a true family.

### Shape B — Typed buckets

```python
@dataclass(frozen=True)
class EvaluationOverlay:
    replaces: tuple[FactReplaceAction, ...] = ()
    adds: tuple[FactAddAction, ...] = ()
    removes: tuple[FactRemoveAction, ...] = ()
```

Trade-off: explicit action categories and simpler per-bucket validation. Risk: action order is lost unless explicitly declared irrelevant.

### Shape C — Single polymorphic action

```python
@dataclass(frozen=True)
class FactOverlayAction:
    kind: Literal["replace", "add", "remove"]
    asrt_id: str | None
    pred_id: str
    e_ref: str
    old_fact_tuple: tuple[Any, ...] | None
    new_fact_tuple: tuple[Any, ...] | None
    note: str | None = None
```

Trade-off: compact surface. Risk: many nullable fields and kind-specific rules recreate the v0.1.4 merged-param smell.

### Shape D — Narrow subset

```python
@dataclass(frozen=True)
class EvaluationOverlay:
    fact_actions: tuple[FactReplaceAction | FactRemoveAction, ...]
```

Trade-off: abandons or defers `add` if it fails crispness. Risk: does not fully satisfy master plan §5.3 unless audit records why `add` is not crisp.

## 7. Compatibility Paths(Draft)

Step 0.B must choose one:

1. `FactOverlayCheckRequest.overlay: tuple[FactValueOverride, ...] | EvaluationOverlay`
   - preserves field name; changes accepted type.
2. Add `FactOverlayCheckRequestV2(plan, binding, evaluation_overlay, engine)`
   - keeps old DTO exact; introduces parallel DTO and migration burden.
3. Runtime accepts both shapes while protocol annotation remains narrow
   - avoids typing churn; risks undocumented magic and weak protocol truth.
4. Rename current path to `EvaluationOverlayCheckRequest` and keep old name as alias
   - clean long-term naming; broad compatibility churn.

Rejected path by default unless Step 0 proves otherwise: adding a second optional field to `FactOverlayCheckRequest`, because it creates mutually-exclusive intent fields and weakens request minimality.

## 8. Legacy Compatibility Requirement

- `FactValueOverride` remains exported and accepted.
- Existing replace-only callers must not need code changes unless Step 0 chooses a V2-only path and records a migration reason.
- Runtime normalization, if chosen, must be observable in tests and docs.

## 9. Boundaries And Invariants

- Fact Overlay Check remains native-only.
- Overlay execution remains read-only; no `set_field`, `add_field`, `retract_by_asrt`, ledger append, or Store support/provenance cache writes.
- Fact actions operate on projected rows, not authored SDK objects.
- Group-key positions must not change for replace/remove; add must preserve tuple arity and e_ref position.
- Non-native engines still return `unsupported`.
- `FactValueOverride` compatibility must be covered by tests.
- No SDK files should change.

## 10. Acceptance(Draft)

- [ ] Step 0.A records the falsifiability checklist conclusion for each item.
- [ ] Step 0.A records the `replace/add/remove × single/multi` decomposition map.
- [ ] Step 0.A explicitly chooses ship / narrow / suspend / abandon.
- [ ] Step 0.B chooses one candidate shape from §6 and records at least one rejected reason for each other shape.
- [ ] Step 0.B chooses one compatibility path from §7 and records at least one rejected reason for each other path.
- [ ] Step 0 decides helper migration scope for Batch 2 helpers.
- [ ] `EvaluationOverlay` and fact action DTOs have frozen protocol tests.
- [ ] `FactValueOverride` compatibility path remains green.
- [ ] Runtime supports the action set chosen by Step 0.A over projected witness rows.
- [ ] Native before/after/diff semantics remain unchanged for existing replace-only callers.
- [ ] Each shipped action has focused native examples that affect pass/fail results.
- [ ] Empty overlay behavior remains `invalid_request`.
- [ ] Non-native engine behavior remains `unsupported`.
- [ ] No ledger writes and no live Store cache writes are tested for each shipped action.
- [ ] `src/kernel/application/docs/01_overview.md` and `_en.md` updated.
- [ ] `python -m unittest src.kernel.tests.test_application_fact_overlay_protocol src.kernel.tests.test_application_fact_overlay_runtime_native` passes.
- [ ] `python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py` passes.
- [ ] `git diff --stat -- src/kernel/sdk` is empty.

## 11. Implementation Plan(Draft)

1. Step 0.A: complete falsifiability checklist + decomposition map; decide ship / narrow / suspend / abandon.
2. Step 0.B: choose candidate shape + compatibility path; record rejected alternatives.
3. Protocol tests for new DTOs and `FactOverlayCheckRequest` compatibility.
4. Runtime normalization from legacy `FactValueOverride` tuple to `EvaluationOverlay`.
5. Projection apply function supports the action set chosen by Step 0.A with validation.
6. Runtime tests for replace compatibility, add pass/fail, remove pass/fail, no-write/no-cache invariants.
7. Docs update.
8. Close-out: outcome, archive, inventory.

## 12. Docs To Update

- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`

No `docs/README.md` update expected unless this batch adds a new durable top-level docs entry.

## 13. Outcome / Deviations

任务完成后填写:

- 最终落地结果:
- 与 blueprint 不同的地方:
- 为什么会有这些调整:
- 归档说明:
