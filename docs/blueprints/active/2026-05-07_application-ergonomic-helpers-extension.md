# Task Blueprint: Application Ergonomic Helpers Extension

- Status: scoped
- Created: 2026-05-07
- Last Updated: 2026-05-07
- Related Modules:
  - `src/kernel/application/capability_helpers/` (Step 0 Round 1: package — supersedes single-file `capability_helpers.py`; see §4.1)
  - `src/kernel/application/__init__.py`
  - `src/kernel/application/docs/`
  - `src/kernel/tests/test_application_proofframe_runtime_native.py` (path-based gate to update in Phase 3 — see §4.1)
  - `src/kernel/tests/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [41_application-builders-design-sketch.md](../../references/working/post-routemap-direction-selection-input/41_application-builders-design-sketch.md)
  - [30_recommendation.md "Direction A — Input shape lock"](../../references/working/post-routemap-direction-selection-input/30_recommendation.md)
  - [50_migration-path.md §8](../../references/working/post-routemap-direction-selection-input/50_migration-path.md)
  - [Capability Ergonomics Batch 2 (archived)](../archive/2026-05-05_capability-ergonomics.md)
  - [Batch 8 Public Surface Decision (archived)](../archive/2026-05-06_public-surface.md)
- Parent: `docs/references/working/post-routemap-direction-selection-input/` (committed at `177b116`)
- Related Blueprint:
  - [2026-05-07_walker-mechanism.md](2026-05-07_walker-mechanism.md) — parallel-safe sibling per [50_ §5](../../references/working/post-routemap-direction-selection-input/50_migration-path.md)
- Audit Log:
  - [2026-05-07_application-ergonomic-helpers-extension.audit.md](2026-05-07_application-ergonomic-helpers-extension.audit.md)

## 1. Problem

Application-layer ergonomic helpers cover only **3 of 8** capability families today (Q3 Fact Overlay, Q4 Why-not, Q5 Frontier — all shipped in Batch 2 capability-ergonomics). The remaining **5 families** require manual DTO construction, sorted-binding boilerplate, and 5 separate `project_<kind>_event_payload` imports:

- Q1 Check
- Q2 Diagnose
- Batch 4 ProofFrame Recheck
- Batch 5 rule overlays (3 sub-builders: rule disable / literal replace / add condition)
- Batch 6 round event payload

Every consumer (current demos, future agent / service / custom integration, future L SDK shells) has to learn each protocol DTO's positional / keyword shape rather than calling a uniform builder per family. The post-Round-Story state (`6b32972`) ships v0.1 public surface (`kernel.sdk`) without evidence / proof / Q1-Q5 / Batch 4-7 exports; A is the additive Tier 2 advanced-importable extension that closes this ergonomic gap **without modifying the SDK**.

## 2. Goals

Extend `kernel.application` capability helpers with **5 new builder families** to reach **8-helper coverage**:

| # | Family | Signature (sketch) | Returns |
|---|---|---|---|
| 1 | Q1 Check | `build_check_request(plan, binding, *, engine="native")` | `CheckRequest` |
| 2 | Q2 Diagnose | `build_diagnose_request(plan, binding, *, engine="native")` | `DiagnoseRequest` |
| 3 | Batch 4 ProofFrame Recheck | `build_proof_frame_recheck_request(support, *, overlay=None)` | `ProofFrameRecheckRequest` |
| 4 | Batch 5 rule overlays (x3) | `build_rule_disable_request` / `build_rule_literal_replace_request` / `build_rule_add_condition_request` (`note=None` passes through to the matching action DTO's existing `note` field) | `RuleDisableRequest` / `RuleLiteralReplaceRequest` / `RuleAddConditionRequest` |
| 5 | Batch 6 round event | `build_round_event_payload(*, kind, request, result)` | capability result payload `dict[str, Any]` (per-kind projector shape, suitable for embedding into a `RoundEvent` row; no named DTO) |

Each builder accepts **application canonical types only** per Direction A — Input shape lock (Gap beta); SDK-to-application lowering bridging is **L's responsibility, not A's**.

## 3. Non-goals

- **No SDK shell.** `kernel.sdk.__all__` is not modified; SDK quickstart, user guide, alignment matrix unchanged. (D2 acceptance gate per Round 6.)
- **No SDK Rule / DSL lowering inside A.** Bridging from SDK Rule / DSL / facade / store / batch / editor / snapshot to application canonical types is L's responsibility per [Gap beta resolution](../../references/working/post-routemap-direction-selection-input/30_recommendation.md).
- **No demo rewrite in A blueprint scope.** `examples/0[1-4]_*.ipynb` and `examples/round_story_full_demo.py` migration is follow-up doc work after A archive, optionally tracked in a separate PR.
- **No release publish.** v0.1 publish is Direction E, user-gated.
- **No L-Full SDK shell.** L is post-A+B v1-ready roadmap target; out of A scope.
- **No service / dialog-agent integration.** Direction D, deferred to v0.2+.
- **No protocol DTO field changes.** A wraps inputs into existing DTOs; does not retype or rename any existing field.

## 4. Current Context

**Source documents (cited throughout this blueprint):**

- [41_application-builders-design-sketch.md](../../references/working/post-routemap-direction-selection-input/41_application-builders-design-sketch.md) — full per-family design sketch including signatures, return types, error semantics, contract test sketches (§6).
- [30_recommendation.md "Direction A — Input shape lock"](../../references/working/post-routemap-direction-selection-input/30_recommendation.md) — Gap beta origin-package rule; per-builder canonical input table; SDK-exclusive types forbidden.
- [50_migration-path.md §8](../../references/working/post-routemap-direction-selection-input/50_migration-path.md) — A blueprint handoff checklist (cited verbatim in §7 below).
- [Capability Ergonomics Batch 2 (archived)](../archive/2026-05-05_capability-ergonomics.md) — §6 helper-layer constraints (no sibling runtime call, no frontier import, no ledger writes); 3 already-shipped builders are template.
- [Batch 8 §5.5.1 Public Surface Decision (archived)](../archive/2026-05-06_public-surface.md) — Tier 2 advanced importable definition.

**Branch state:** Parent `v0.1-public-surface-2026-05-06`; bundle at `177b116`. **Implementation branch / worktree policy (Step 0 process correction, locked 2026-05-07; see audit log):** A implementation lands on a dedicated worktree at `/Users/zhenzhili/hnsm-backend-A`, branch `codex/v0.1-application-helpers-extension-2026-05-07` (created off the Step 0 final commit on parent). Parent branch carries blueprint / scoping docs only — **no `src/` writes on parent**. Worktree (not branch-only) chosen because parent worktree has pre-existing dirty notebook modifications that must not propagate. `codex/` prefix follows current Codex app branch convention; topic retains the `v0.1-<topic>-<date>` semantic from parent's naming. Sacred branches `master` / `v0.1-oss-prep` not touched.

**Step 0 unknowns (resolved before transitioning draft -> scoped):**

- ✓ **Module split** — locked Round 1, 2026-05-07; A2 selected. See §4.1.
- ✓ **Error class layout** — locked Round 2, 2026-05-07; A-R2-2 selected. See §4.1.
- ✓ **Binding normalization** — locked Round 3, 2026-05-07; A-R3-3 refined selected. See §4.1.
- ✓ **Test fixture layout** — locked Round 4, 2026-05-07; A-R4 refined (conservative incremental) selected. See §4.1.

**All Step 0 unknowns resolved.** Status is now `scoped`; implementation starts only in the dedicated A worktree described above.

### 4.1 Step 0 Decisions Locked

**Round 1 — Module split (2026-05-07): A2 selected.** Migrate `src/kernel/application/capability_helpers.py` (currently 292 lines, 3 Batch 2 helpers) to a package:

```text
src/kernel/application/capability_helpers/
  __init__.py          # public re-export, preserves all current import paths
  errors.py            # error class (final name selected Round 2)
  fact_overlay.py      # existing Batch 2 fact overlay helpers (Q3)
  why_not.py           # existing Batch 2 why-not helpers (Q4)
  frontier.py          # existing Batch 2 frontier helpers (Q5)
  check.py             # new — Q1 build_check_request
  diagnose.py          # new — Q2 build_diagnose_request
  proof_frame.py       # new — Batch 4 build_proof_frame_recheck_request
  rule_overlays.py     # new — Batch 5 three sub-builders
  round_events.py      # new — Batch 6 build_round_event_payload
```

**Import path preservation contract:** `__init__.py` re-exports every public symbol so:

- `from kernel.application.capability_helpers import build_fact_value_override` keeps working
- `from kernel.application import build_fact_value_override` keeps working

**Known follow-up — path-based test gate to update:** [src/kernel/tests/test_application_proofframe_runtime_native.py:410-414](../../../src/kernel/tests/test_application_proofframe_runtime_native.py) currently asserts `ProofFrame` / `proofframe` strings are NOT present in `src/kernel/application/capability_helpers.py` as a single-file gate. After A2 migration:

1. The path `capability_helpers.py` becomes a package directory; the bare-`Path(...).read_text()` call breaks.
2. The assertion is **intentionally superseded** by Phase 3 (Batch 4 ProofFrame Recheck builder lands in `proof_frame.py`).

Test must be **rewritten or removed** as part of Phase 3 acceptance — recorded as known supersede, not a regression.

**Rationale:** Batch 2 archive's single-file `capability_helpers.py` was the right scope for 3 helpers; 8-helper coverage shifts the trade-off toward per-capability separation. This is scope evolution, not a principle violation.

---

**Round 2 — Error class layout (2026-05-07): A-R2-2 selected.** Reuse existing `class CapabilityHelperError(ValueError)` (currently in [src/kernel/application/capability_helpers.py:29](../../../src/kernel/application/capability_helpers.py), used by 7 Batch 2 helper validation calls) and add a new subclass for SDK-package origin rejection:

```python
class CapabilityHelperError(ValueError):
    """Base for all capability helper input validation errors."""

class OriginPackageError(CapabilityHelperError):
    """Raised when an SDK-package object (Rule, Derivation, EntitySnapshot,
    SDKStore, SDKBatchTx, ...) is passed to a builder that requires
    application canonical types per Gap β origin-package rule."""
```

**Convention:**

- Existing 7 helper input validation calls (`"store must be Store"`, `"field must be FieldPath"`, etc.) continue raising `CapabilityHelperError` — **no behavior change**
- New SDK-package origin rejection raises `OriginPackageError` — distinguishable so future L SDK shells can `except OriginPackageError` to detect missing lowering
- Both classes live in `capability_helpers/errors.py` per §4.1 Round 1 layout
- `CapabilityHelperError` re-export preserved at package `__init__.py`; `OriginPackageError` newly exported

**Why not `TypeError` for origin rejection:** Existing precedent (`raise CapabilityHelperError("store must be Store")`) treats origin-shape mismatches as validation, not Python type errors. Keeping `OriginPackageError` in the `CapabilityHelperError` tree honors that precedent while preserving subclass-level dispatch for L bridging.

---

**Round 3 — Binding normalization (2026-05-07): A-R3-3 refined selected.** `binding` parameter for `build_check_request` and `build_diagnose_request` accepts both canonical forms:

```python
binding: Mapping[str, Any] | BindingItems
```

**Normalization contract:**

| Input form | Helper behavior |
|---|---|
| `Mapping[str, Any]` | Sort keys lexicographically; produce canonical `BindingItems` tuple-of-`(key, value)` pairs |
| `BindingItems` (tuple of pairs, sorted canonical form) | Validate shape (each item is `tuple[str, Any]`); validate sortedness (lexicographic on key) and non-duplicate keys; pass through unchanged |

**Helper-level validation (raises `CapabilityHelperError`):**

- `binding` must be `Mapping[str, Any]` or valid `BindingItems` — otherwise raise
- Keys must be non-empty `str` — otherwise raise
- `BindingItems` form: duplicate keys raise (impossible in `Mapping`; in tuple form means caller passed non-canonical input)
- `BindingItems` form: unsorted input raises (no silent re-sort — `BindingItems` represents the canonical sorted form, caller must canonicalize before passing)
- SDK-origin objects in keys or values raise `OriginPackageError(CapabilityHelperError)` per §4.1 Round 2

**Helper allows (no validation):**

- `None` values — binding overlay scenarios may legitimately bind to None
- Empty binding — zero-variable plans exist

**Validation deferred to runtime (NOT helper):**

- `$` prefix convention for binding variable names — handled at `kernel.core.store._support.normalize_binding_items` / protocol layer
- Variable name matching against `plan` expected variables — handled by capability runtime
- Value type matching plan's expected variable types — handled by capability runtime

**Why dual-form:** Existing application DTO fields are `BindingItems` typed (e.g., [`FactOverlayCheckRequest.binding`](../../../src/kernel/application/protocol/derivation_fact_overlay.py)). Rejecting `BindingItems` would reject the canonical application type, violating Gap β. `Mapping[str, Any]` is the convenience form per [41_ §3](../../references/working/post-routemap-direction-selection-input/41_application-builders-design-sketch.md); both are application canonical.

---

**Round 4 — Test fixture layout (2026-05-07): A-R4 refined (conservative incremental) selected.** Existing [`src/kernel/tests/test_application_capability_helpers.py`](../../../src/kernel/tests/test_application_capability_helpers.py) (~460 lines, Batch 2/3 helper tests with shared schema/store fixtures) is **NOT split**. New family tests are flat per-family files alongside it:

```text
src/kernel/tests/test_application_capability_helpers.py     # existing — untouched
src/kernel/tests/test_capability_helpers_check.py           # new — Phase 1 (Q1)
src/kernel/tests/test_capability_helpers_diagnose.py        # new — Phase 2 (Q2)
src/kernel/tests/test_capability_helpers_proof_frame.py     # new — Phase 3 (Batch 4)
src/kernel/tests/test_capability_helpers_rule_overlays.py   # new — Phase 4 (Batch 5)
src/kernel/tests/test_capability_helpers_round_events.py    # new — Phase 5 (Batch 6)
src/kernel/tests/test_capability_helpers_invariants.py      # new — Phase 6 cross-cutting
```

**Decisions:**

- **Existing test file preserved.** Splitting Batch 2/3 helper tests for source-mirror symmetry would create unrelated churn (~460 lines movement, shared fixture extraction). A's scope is **additive** (5 new families), not reorganizational.
- **New family tests follow `test_capability_helpers_<family>.py` naming.** Discovery-friendly: `grep test_capability_helpers_check` finds Q1's tests; each file owns its family's `test_*` functions and local fixtures.
- **`test_capability_helpers_invariants.py` is Phase 6 cross-cutting.** Tests origin-package rule (`OriginPackageError` raised on SDK-package inputs), SDK import audit (grep / import-graph), `from kernel.application.capability_helpers import ...` path stability, etc. Doesn't duplicate per-family validation.
- **Path-based gate replacement (Phase 3 implementation note):** [test_application_proofframe_runtime_native.py:410-414](../../../src/kernel/tests/test_application_proofframe_runtime_native.py) currently asserts `ProofFrame` strings absent from `capability_helpers.py` (single-file gate). After Phase 3 lands `proof_frame.py` builder, this gate is **replaced with a package-aware boundary test** (e.g., walks `capability_helpers/` package; asserts `proof_frame.py` does not import `proofframe_runtime` sibling internals) — **not just removed**. Replacement happens in Phase 3 as part of acceptance.

**Why not full per-family split:** Existing test file's shared fixtures (schema, store, FieldPath, etc.) are reused across Batch 2/3 helper tests. Splitting would duplicate fixtures or extract them to a `conftest.py` — both add churn for zero design value. The 5 new family files don't need those exact fixtures (they target new builders); each new file declares its own minimal fixtures.

---

**Step 0 complete.** All 4 Round decisions locked: A2 module split (Round 1), A-R2-2 error class layout (Round 2), A-R3-3 refined binding normalization (Round 3), A-R4 refined test fixture layout (Round 4). Plus Step 0 process correction: branch / worktree discipline locked. Status is `scoped`; implementation starts only after the A worktree is created from this parent commit.

## 5. Proposed Shape

Per [41_ §1-§5](../../references/working/post-routemap-direction-selection-input/41_application-builders-design-sketch.md). Cross-cutting shape:

- Each builder is a **pure function** (no I/O, no global state) returning a frozen DTO.
- **Input shape:** application canonical types per Gap beta; SDK-exclusive types raise `OriginPackageError(CapabilityHelperError)` at the function boundary (origin-package check, not name match). See §4.1 Round 2.
- **Determinism:** binding normalization (per §4.1 Round 3) accepts dual-form `Mapping[str, Any] | BindingItems`; sorts keys lexicographically; both forms produce equivalent canonical DTO output (Gap epsilon contract test).
- **No silent side effects:** no ledger writes, no sibling runtime call, no frontier import (Batch 2 §6 helper-layer constraints).
- **Error class:** existing 7 helpers continue raising `CapabilityHelperError(ValueError)` for value/type validation (unchanged). New SDK-package origin rejection raises `OriginPackageError(CapabilityHelperError)` per §4.1 Round 2.
- **Cross-cutting invariants honored:** `#1` application-first authority, `#4a` canonical input-minimal, `#5` layer isolation (no `kernel.sdk` import), `#6` no outward compat, `#9` no observable cache, `#19` test contract, `#P0` conflict resolution, `#P1` carve-out flow.

## 6. Boundaries And Invariants

- **Layer boundary:** `kernel.application` must not import `kernel.sdk`, directly or transitively, for these helpers.
- **Runtime boundary:** helpers construct DTOs and normalize application-canonical inputs; they do not call sibling capability runtimes.
- **Store boundary:** helpers do not write to the ledger or mutate `Store`. Reads are allowed only when declared by the specific builder contract.
- **Frontier boundary:** helpers do not import or call frontier internals unless the existing Batch 2 helper already declared that read-only behavior.
- **Public-surface boundary:** no new `kernel.sdk.__all__` export, no SDK docs, no README quickstart change, no outward compatibility promise.
- **Shape boundary:** SDK-exclusive objects (`Rule`, `Derivation`, `EntitySnapshot`, `SDKStore`, `SDKBatchTx`, etc.) are rejected at this layer with `OriginPackageError(CapabilityHelperError)` per §4.1 Round 2. Future L SDK shells are responsible for SDK-to-application lowering and may catch `OriginPackageError` to detect bridging gaps.
- **Migration boundary:** Existing `capability_helpers.py` migrates to a package per §4.1; `__init__.py` re-exports all public symbols so `from kernel.application.capability_helpers import ...` and `from kernel.application import ...` paths remain stable. Path-based test gates that read `capability_helpers.py` as a single file (see §4.1) must be rewritten or removed in their corresponding phase.

## 7. Acceptance

Per [50_ §8 "A blueprint must cite / check"](../../references/working/post-routemap-direction-selection-input/50_migration-path.md):

- [ ] All 5 new builders shipped, exported from `kernel.application` (Tier 2 advanced importable)
- [ ] All builders accept application canonical types only; SDK-package inputs raise `OriginPackageError(CapabilityHelperError)` (origin-package rule per §4.1 Round 2, not name match)
- [ ] Error class layout (per §4.1 Round 2) shipped: `CapabilityHelperError(ValueError)` unchanged at `errors.py`; `OriginPackageError(CapabilityHelperError)` newly exported from package `__init__.py`
- [ ] No `kernel.sdk.__all__` modification; no SDK examples / quickstart / user guide change
- [ ] No demo rewrite in this blueprint scope; demo migration tracked separately after archive
- [ ] No SDK Rule lowering inside A; bridging deferred to L
- [ ] Proposed Shape / Non-goals sections reference `#1`, `#5`, `#6`, plus Batch 2 §6 helper-layer constraints
- [ ] Contract tests per [41_ §6](../../references/working/post-routemap-direction-selection-input/41_application-builders-design-sketch.md) all pass:
  - Determinism (same input -> same DTO)
  - Equivalence to manual DTO construction
  - SDK-package input rejection (origin-package rule)
  - Binding normalization per §4.1 Round 3: dual-form `Mapping[str, Any] | BindingItems` accepted; `Mapping` sorted lexicographically; `BindingItems` validated for sortedness + non-duplicate keys (raise on violation, no silent re-sort); `None` values + empty binding allowed; `OriginPackageError` raised for SDK-origin objects in keys/values
  - No-side-effect (no ledger / no frontier / no sibling)
- [ ] grep / import-graph static audit clean: no transitive SDK reach
- [ ] Module split A2 (per §4.1) shipped: `capability_helpers.py` migrated to package; `__init__.py` re-exports all public symbols; `from kernel.application.capability_helpers import ...` and `from kernel.application import ...` paths verified equivalent to pre-A state for Batch 2 helpers
- [ ] Path-based test gate at [test_application_proofframe_runtime_native.py:410-414](../../../src/kernel/tests/test_application_proofframe_runtime_native.py) **replaced with a package-aware boundary test** in Phase 3 (intentional supersede per §4.1 Round 1 + Round 4) — not just removed
- [ ] Test fixture layout per §4.1 Round 4 shipped: existing `test_application_capability_helpers.py` untouched; 5 new family files (`test_capability_helpers_<family>.py`) + 1 cross-cutting file (`test_capability_helpers_invariants.py`)
- [ ] All 8 capability families now have an importable builder (3 prior shipped + 5 new = **8-helper coverage target met**)

## 8. Implementation Plan

Phased per family. Each phase = one builder + tests + audit log entry; never batch.

| Phase | Family | Module target | Tests added |
|---|---|---|---|
| 0 | Migrate `capability_helpers.py` to package per §4.1 + ship error classes per §4.1 Round 2 | `kernel/application/capability_helpers/__init__.py` + `errors.py` (`CapabilityHelperError` moved from old single file + new `OriginPackageError(CapabilityHelperError)`) + `fact_overlay.py` + `why_not.py` + `frontier.py` (move Batch 2 helpers, **no behavior change**) | re-run existing Batch 2 helper tests; verify import paths unchanged; verify `from kernel.application.capability_helpers import CapabilityHelperError, OriginPackageError` resolves |
| 1 | Q1 Check `build_check_request` | `kernel/application/capability_helpers/check.py` | `test_capability_helpers_check.py` |
| 2 | Q2 Diagnose `build_diagnose_request` | `kernel/application/capability_helpers/diagnose.py` | `test_capability_helpers_diagnose.py` |
| 3 | Batch 4 ProofFrame Recheck | `kernel/application/capability_helpers/proof_frame.py` | `test_capability_helpers_proof_frame.py`; **replace** `test_application_proofframe_runtime_native.py:410-414` with package-aware boundary test per §4.1 Round 1 + Round 4 (not just remove) |
| 4 | Batch 5 rule overlays (3 sub) | `kernel/application/capability_helpers/rule_overlays.py` | `test_capability_helpers_rule_overlays.py`; verify `note=None` pass-through and raw SDK-origin rejection before action DTO construction |
| 5 | Batch 6 round event payload | `kernel/application/capability_helpers/round_events.py` | `test_capability_helpers_round_events.py` |
| 6 | Cross-cutting invariants | n/a | `test_capability_helpers_invariants.py`: grep audit + import-graph review + origin-package runtime check + `OriginPackageError` raise verification + import path stability check |

Per phase:

1. Write test (red)
2. Implement builder (green)
3. Run full test suite + audit log entry
4. Update `kernel/application/__init__.py` to export the new builder name (Tier 2 advanced importable)
5. Move to next phase

**Static / structural checks per [41_ §6](../../references/working/post-routemap-direction-selection-input/41_application-builders-design-sketch.md):**

- grep audit: no `from kernel.sdk` import in the helper module
- import-graph review: no transitive SDK reach
- origin-package check: builder rejects SDK-package inputs at runtime

## 9. Docs To Update

- `src/kernel/application/docs/README.md`
- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- Audit log for this blueprint
- `docs/README.md` only if the blueprint introduces a new durable docs entry outside existing module docs

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
