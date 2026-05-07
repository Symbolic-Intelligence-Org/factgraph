# Task Blueprint: Application Ergonomic Helpers Extension

- Status: draft
- Created: 2026-05-07
- Last Updated: 2026-05-07
- Related Modules:
  - `src/kernel/application/capability_helpers.py`
  - `src/kernel/application/__init__.py`
  - `src/kernel/application/docs/`
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
| 4 | Batch 5 rule overlays (x3) | `build_rule_disable_request` / `build_rule_literal_replace_request` / `build_rule_add_condition_request` | `RuleDisableRequest` / `RuleLiteralReplaceRequest` / `RuleAddConditionRequest` |
| 5 | Batch 6 round event | `build_round_event_payload(*, kind, request, result)` | `RoundEventPayload` |

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

**Branch state:** `v0.1-public-surface-2026-05-06`; bundle committed at `177b116`. Sacred branches `master` / `v0.1-oss-prep` not touched.

**Step 0 unknowns (resolved before transitioning draft -> scoped):**

- Module split: single `capability_helpers.py` extension vs per-family submodules
- Binding normalization exact behavior (duplicate-key detection; None-value handling)
- Error class layout (`HelperInputError` reuse vs new family-specific subclasses)
- Test fixture layout (extend `test_capability_helpers.py` vs new files per family)

These are blueprint-scoped decisions, not bundle-revision questions.

## 5. Proposed Shape

Per [41_ §1-§5](../../references/working/post-routemap-direction-selection-input/41_application-builders-design-sketch.md). Cross-cutting shape:

- Each builder is a **pure function** (no I/O, no global state) returning a frozen DTO.
- **Input shape:** application canonical types per Gap beta; SDK-exclusive types raise the Step 0-selected typed helper / domain error or `TypeError` at the function boundary (origin-package check, not name match).
- **Determinism:** binding normalization sorts keys deterministically; same inputs -> same DTO output (Gap epsilon contract test).
- **No silent side effects:** no ledger writes, no sibling runtime call, no frontier import (Batch 2 §6 helper-layer constraints).
- **Error class:** invalid input raises a typed helper / domain error, or `TypeError` if Step 0 chooses that convention for origin-package rejection; never raw `ValueError`.
- **Cross-cutting invariants honored:** `#1` application-first authority, `#4a` canonical input-minimal, `#5` layer isolation (no `kernel.sdk` import), `#6` no outward compat, `#9` no observable cache, `#19` test contract, `#P0` conflict resolution, `#P1` carve-out flow.

## 6. Boundaries And Invariants

- **Layer boundary:** `kernel.application` must not import `kernel.sdk`, directly or transitively, for these helpers.
- **Runtime boundary:** helpers construct DTOs and normalize application-canonical inputs; they do not call sibling capability runtimes.
- **Store boundary:** helpers do not write to the ledger or mutate `Store`. Reads are allowed only when declared by the specific builder contract.
- **Frontier boundary:** helpers do not import or call frontier internals unless the existing Batch 2 helper already declared that read-only behavior.
- **Public-surface boundary:** no new `kernel.sdk.__all__` export, no SDK docs, no README quickstart change, no outward compatibility promise.
- **Shape boundary:** SDK-exclusive objects (`Rule`, `Derivation`, `EntitySnapshot`, `SDKStore`, `SDKBatchTx`, etc.) are rejected at this layer. Future L SDK shells are responsible for SDK-to-application lowering.

## 7. Acceptance

Per [50_ §8 "A blueprint must cite / check"](../../references/working/post-routemap-direction-selection-input/50_migration-path.md):

- [ ] All 5 new builders shipped, exported from `kernel.application` (Tier 2 advanced importable)
- [ ] All builders accept application canonical types only; SDK-package inputs raise the Step 0-selected typed helper / domain error or `TypeError` (origin-package rule, not name match)
- [ ] No `kernel.sdk.__all__` modification; no SDK examples / quickstart / user guide change
- [ ] No demo rewrite in this blueprint scope; demo migration tracked separately after archive
- [ ] No SDK Rule lowering inside A; bridging deferred to L
- [ ] Proposed Shape / Non-goals sections reference `#1`, `#5`, `#6`, plus Batch 2 §6 helper-layer constraints
- [ ] Contract tests per [41_ §6](../../references/working/post-routemap-direction-selection-input/41_application-builders-design-sketch.md) all pass:
  - Determinism (same input -> same DTO)
  - Equivalence to manual DTO construction
  - SDK-package input rejection (origin-package rule)
  - Sorted-keys-only binding normalization
  - No-side-effect (no ledger / no frontier / no sibling)
- [ ] grep / import-graph static audit clean: no transitive SDK reach
- [ ] All 8 capability families now have an importable builder (3 prior shipped + 5 new = **8-helper coverage target met**)

## 8. Implementation Plan

Phased per family. Each phase = one builder + tests + audit log entry; never batch.

| Phase | Family | Module target | Tests added |
|---|---|---|---|
| 1 | Q1 Check `build_check_request` | `kernel/application/capability_helpers.py` (or sibling per Step 0) | `test_build_check_request.py` |
| 2 | Q2 Diagnose `build_diagnose_request` | same | `test_build_diagnose_request.py` |
| 3 | Batch 4 ProofFrame Recheck | same | `test_build_proof_frame_recheck.py` |
| 4 | Batch 5 rule overlays (3 sub) | same | `test_build_rule_overlay_requests.py` |
| 5 | Batch 6 round event payload | same | `test_build_round_event_payload.py` |
| 6 | Cross-cutting test sweep | n/a | grep audit + import-graph review + origin-package runtime check |

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
