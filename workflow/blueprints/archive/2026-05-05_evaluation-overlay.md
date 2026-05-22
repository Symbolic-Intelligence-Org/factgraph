# EvaluationOverlay + Fact Scenario Core(Batch 3 of Round Story Completion Plan)

- Status: implemented
- Created: 2026-05-06
- Last Updated: 2026-05-06
- Parent: [2026-05-05_round-story-completion-plan.md](../active/2026-05-05_round-story-completion-plan.md) §5.3
- Scope: Batch 3 — generic fact-side overlay container for replace/remove; native-only Fact Overlay Check compatibility path
- Branch: `v0.1-evaluation-overlay-2026-05-05`(off `37ec62b`)
- Related Modules:
  - `src/kernel/application/protocol/derivation_fact_overlay.py`
  - `src/kernel/application/fact_overlay_runtime.py`
  - `src/kernel/application/capability_helpers.py`
  - `src/kernel/application/docs/`
  - `src/kernel/tests/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/archive/2026-05-05_capability-ergonomics.md](./2026-05-05_capability-ergonomics.md)
- Audit Log:
  - [2026-05-05_evaluation-overlay.audit.md](./2026-05-05_evaluation-overlay.audit.md)

## 1. Problem

Current Fact Overlay Check supports only a tuple of `FactValueOverride` actions. That works for Q3 "What if this fact were different?", but it is not enough for Batch 3's round-story scenario needs:

- no first-class scenario container for multiple fact actions;
- no first-class fact remove action, and no crisp fact add action after Step 0.A;
- no reusable DTO that future Batch 4 ProofFrame and Batch 5 rule-side overlays can name as a shared input concept;
- examples still model overlay as "single replace" even after Batch 2 helper ergonomics.

The danger is v0.1.4-style semantic decomposition: `replace`, `add`, and `remove` may look like one DTO because they share "overlay" vocabulary, but they carry different identity and validation requirements. This batch must explicitly prove they are one crisp fact-side action family before implementation. If not, it must suspend or abandon rather than ship a blurred container.

## 2. Goals

- Freeze an `EvaluationOverlay` protocol shape for the Step 0.A-confirmed fact-side action set.
- Implement the Step 0.A-confirmed fact-side action set:
  - replace: current `FactValueOverride` semantics;
  - remove: remove a visible projected fact without ledger write.
- Keep `FactOverlayCheckRequest` compatible with current `overlay: tuple[FactValueOverride, ...]` callers while adding the new container path.
- Preserve current capability boundary: native-only, read-only, no ledger writes, no live Store cache contamination, no SDK shell.
- Add protocol/runtime tests and drift gates for action semantics, compatibility, and no-write behavior.

## 3. Non-goals

- No rule-side overlay actions(disable / replace condition / add condition); those start in Batch 5.
- No fact-side add action in this batch; Step 0.A found `single + add` would require chosen-policy semantics rather than a crisp projection-local action.
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

Step 0.A tried to falsify the "single EvaluationOverlay fact-action family" idea before any DTO was frozen. Recorded conclusion:

| Item | Conclusion | Notes |
|---|---|---|
| Durable identity | Does not falsify `replace + remove`; falsifies full `replace + add + remove` for this batch | `replace` / `remove` use visible projected `asrt_id`; `add` can be imagined as overlay-local but becomes underspecified for `single` fields before identity choice matters |
| Layer crossing | Does not falsify `replace + remove` | `remove` can validate against current projected witness rows; it does not need reverse ledger lookup if semantics are "hide this visible projected row" |
| Single vs multi decomposition | Falsifies full `replace + add + remove` | `replace` and `remove` have the same row-level meaning for `single` and `multi`; `single + add` diverges into reject / shadow / only-if-empty policy choices |
| Shared validation | Does not falsify narrowed `replace + remove` | Shared families are visible row lookup, stale tuple validation, arity/e_ref validation, duplicate action target detection, and group-key stability where applicable |
| Group-key behavior | Does not falsify narrowed `replace + remove` | `replace` must preserve group-key positions; `remove` deletes a visible row and has no new tuple to preserve; `add` would require additional arity/e_ref/group-key checks but is out of this batch |
| No-write invariant | Does not falsify narrowed `replace + remove` | Both actions can be applied by copying projected witness rows and never calling `set_field`, `add_field`, `retract_by_asrt`, ledger append, or live Store cache writes |

Step 0.A decomposition map:

| Action | single field | multi field | Falsifies single-family? |
|---|---|---|---|
| replace | Replace the currently visible selected projected row tuple; no re-run of chosen policy beyond before/after evaluation over copied witness rows | Replace the matching visible projected row tuple | No |
| add | Diverges: reject, shadow current selected row, or only support no-visible-row case are different semantics | Append an overlay-local projected row | Yes; defer `add` from Batch 3 |
| remove | Hide the currently visible selected projected row; do not reveal older active ledger claims that were not in the projected witness | Hide the matching visible projected row | No |

Step 0.A decision: **narrow Batch 3 to `replace + remove`**.

Rationale: the `add` row in the map fails crispness for `single` fields. Choosing "reject add on single" would ship a multi-only action under a generic fact-action name; choosing "shadow" or "only if no visible row exists" would embed chosen-policy semantics into a projection-local overlay. `replace + remove` remains crisp because both operate only on visible projected rows and never ask the overlay layer to create or persist new fact identity.

### 5.2 Action Identity Questions

- `replace`: uses existing visible `asrt_id`; current `FactValueOverride` can map 1:1.
- `remove`: uses existing visible `asrt_id`; must validate `old_fact_tuple` against current projection.
- `add`: deferred from Batch 3; no action identity choice is frozen. If revisited later, identity must be designed with the same `single + add` decomposition risk in view.

### 5.3 Cardinality Questions

- `replace`: current validation already enforces arity and group-key stability.
- `remove`: removing a single projected row is straightforward for `multi`; for `single`, removing the selected active row leaves no visible fact for that predicate/e_ref in the overlay.
- `add` for `multi`: candidate meaning would be append projected row.
- `add` for `single`: candidate meanings diverge:
  - Option A: reject add on `single`, require replace;
  - Option B: add shadows current selected row in overlay;
  - Option C: support only when no visible row exists.

This divergence is a falsifiability item, not a minor implementation detail. Step 0.A found that `single + add` does not converge without chosen-policy semantics, so `add` is not in the Batch 3 action set.

### 5.4 Helper Migration Question

Batch 2 shipped `build_fact_value_override(...)`. Step 0.B must decide whether Batch 3 also ships new helpers, such as `build_fact_remove_action(...)` or `build_evaluation_overlay(...)`, or explicitly defers helper migration. The decision must not create SDK shell surface.

## 6. DTO Shape Decision

Step 0.A narrowed the action set to `replace + remove`. Step 0.B chose **Shape D: reuse legacy replace DTO + new remove action**.

Selected shape:

```python
@dataclass(frozen=True)
class FactRemoveAction:
    asrt_id: str
    pred_id: str
    e_ref: str
    old_fact_tuple: tuple[Any, ...]
    note: str | None = None

@dataclass(frozen=True)
class EvaluationOverlay:
    fact_actions: tuple[FactValueOverride | FactRemoveAction, ...]
```

Selection rationale:

- preserves `FactValueOverride` as the exact replace action already accepted by callers and tested by runtime;
- introduces only one new action DTO for the only new crisp behavior, `remove`;
- keeps compatibility normalization small: a legacy `tuple[FactValueOverride, ...]` can normalize to `EvaluationOverlay(fact_actions=legacy_tuple)`;
- avoids a duplicate `FactReplaceAction` that would have to be kept behaviorally identical to `FactValueOverride`.

### Shape A — Two dataclasses + flat union

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
class FactRemoveAction:
    asrt_id: str
    pred_id: str
    e_ref: str
    old_fact_tuple: tuple[Any, ...]
    note: str | None = None

@dataclass(frozen=True)
class EvaluationOverlay:
    fact_actions: tuple[FactReplaceAction | FactRemoveAction, ...]
```

Rejected reason: clear naming, but duplicates `FactValueOverride` as `FactReplaceAction` without adding behavior.

### Shape B — Typed buckets

```python
@dataclass(frozen=True)
class EvaluationOverlay:
    replaces: tuple[FactReplaceAction, ...] = ()
    removes: tuple[FactRemoveAction, ...] = ()
```

Rejected reason: buckets are over-structured for two row actions and would force a separate ordering/conflict policy.

### Shape C — Single polymorphic action

```python
@dataclass(frozen=True)
class FactOverlayAction:
    kind: Literal["replace", "remove"]
    asrt_id: str
    pred_id: str
    e_ref: str
    old_fact_tuple: tuple[Any, ...]
    new_fact_tuple: tuple[Any, ...] | None
    note: str | None = None
```

Rejected reason: nullable `new_fact_tuple` and kind-specific validation recreate part of the v0.1.4 merged-param smell.

### Shape D — Reuse legacy replace DTO + new remove action

```python
@dataclass(frozen=True)
class EvaluationOverlay:
    fact_actions: tuple[FactValueOverride | FactRemoveAction, ...]
```

Selected with accepted risk: `FactValueOverride` remains semantically named as "override" rather than the more general "replace action". That is preferable to duplicate replace DTOs in Batch 3.

## 7. Compatibility Path Decision

Step 0.B chose **Path 1: keep `FactOverlayCheckRequest.overlay` and widen the accepted type**:

```python
overlay: tuple[FactValueOverride, ...] | EvaluationOverlay
```

Selected path rationale:

- preserves the public request field name;
- preserves existing replace-only callers;
- makes new protocol truth explicit in the DTO annotation;
- keeps runtime normalization local and testable.

1. `FactOverlayCheckRequest.overlay: tuple[FactValueOverride, ...] | EvaluationOverlay`
   - selected; preserves field name and makes accepted type explicit.
2. Add `FactOverlayCheckRequestV2(plan, binding, evaluation_overlay, engine)`
   - rejected; keeps old DTO exact but introduces parallel request types and migration burden.
3. Runtime accepts both shapes while protocol annotation remains narrow
   - rejected; avoids typing churn but creates undocumented magic and weak protocol truth.
4. Rename current path to `EvaluationOverlayCheckRequest` and keep old name as alias
   - rejected; cleaner long-term naming but too much compatibility churn for Batch 3.

Rejected path remains rejected: adding a second optional field to `FactOverlayCheckRequest`, because it creates mutually-exclusive intent fields and weakens request minimality.

Helper migration decision: ship application-layer `build_fact_remove_action(...)` and `build_evaluation_overlay(...)`; keep `build_fact_value_override(...)` as the replace helper. Do not add `build_fact_replace_action(...)` in Batch 3, and do not create SDK shell surface.

## 8. Legacy Compatibility Requirement

- `FactValueOverride` remains exported and accepted.
- Existing replace-only callers must not need code changes unless Step 0 chooses a V2-only path and records a migration reason.
- Runtime normalization, if chosen, must be observable in tests and docs.

## 9. Boundaries And Invariants

- Fact Overlay Check remains native-only.
- Overlay execution remains read-only; no `set_field`, `add_field`, `retract_by_asrt`, ledger append, or Store support/provenance cache writes.
- Fact actions operate on projected rows, not authored SDK objects.
- Group-key positions must not change for replace; remove has no replacement tuple and must target a visible row.
- Non-native engines still return `unsupported`.
- `FactValueOverride` compatibility must be covered by tests.
- No SDK files should change.

## 10. Acceptance(Draft)

- [x] Step 0.A records the falsifiability checklist conclusion for each item.
- [x] Step 0.A records the `replace/add/remove × single/multi` decomposition map.
- [x] Step 0.A explicitly chooses ship / narrow / suspend / abandon.
- [x] Step 0.B chooses one candidate shape from §6 and records at least one rejected reason for each other shape.
- [x] Step 0.B chooses one compatibility path from §7 and records at least one rejected reason for each other path.
- [x] Step 0.B decides helper migration scope for Batch 2 helpers.
- [x] `EvaluationOverlay` and fact action DTOs have frozen protocol tests.
- [x] `FactValueOverride` compatibility path remains green.
- [x] Runtime supports the action set chosen by Step 0.A over projected witness rows.
- [x] Native before/after/diff semantics remain unchanged for existing replace-only callers.
- [x] Each shipped action has focused native examples that affect pass/fail results.
- [x] Empty overlay behavior remains `invalid_request`.
- [x] Non-native engine behavior remains `unsupported`.
- [x] No ledger writes and no live Store cache writes are tested for each shipped action.
- [x] `src/kernel/application/docs/01_overview.md` and `_en.md` updated.
- [x] `python -m unittest src.kernel.tests.test_application_fact_overlay_protocol src.kernel.tests.test_application_fact_overlay_runtime_native` passes.
- [x] `python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py` passes.
- [x] `git diff --stat -- src/kernel/sdk` is empty.

## 11. Implementation Plan(Draft)

1. Step 0.A: complete falsifiability checklist + decomposition map; decide ship / narrow / suspend / abandon. Done: narrow to `replace + remove`.
2. Step 0.B: choose candidate shape + compatibility path; record rejected alternatives. Done: Shape D + Path 1; helpers are `build_fact_remove_action(...)` and `build_evaluation_overlay(...)`.
3. Protocol tests for new DTOs and `FactOverlayCheckRequest` compatibility.
4. Runtime normalization from legacy `FactValueOverride` tuple to `EvaluationOverlay`.
5. Projection apply function supports the action set chosen by Step 0.A with validation.
6. Runtime tests for replace compatibility, remove pass/fail, no-write/no-cache invariants.
7. Docs update.
8. Close-out: outcome, archive, inventory.

## 12. Docs To Update

- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`

No `docs/README.md` update expected unless this batch adds a new durable top-level docs entry.

## 13. Outcome / Deviations

任务完成后填写:

- 最终落地结果:新增 `EvaluationOverlay` + `FactRemoveAction`;`FactOverlayCheckRequest.overlay` 接受 legacy `tuple[FactValueOverride, ...]` 或 `EvaluationOverlay`;runtime 归一后支持 projected-row replace/remove;新增 application helpers `build_fact_remove_action(...)` 与 `build_evaluation_overlay(...)`;module docs 已更新;focused tests、ruff、SDK diff guard、full kernel unittest 通过。
- 与 blueprint 不同的地方:Step 0.A 将原 master-plan 预期的 fact-side add 从 Batch 3 中移除,最终 action set 为 `replace + remove`。
- 为什么会有这些调整:`single + add` 无法在不选择 reject/shadow/only-if-empty policy 的情况下得到 projection-local 语义;继续实现会重现 v0.1.4 merged semantic trap。
- 归档说明:实现完成后移至 `docs/blueprints/archive/2026-05-05_evaluation-overlay.{md,audit.md}`,并更新 archive inventory。
