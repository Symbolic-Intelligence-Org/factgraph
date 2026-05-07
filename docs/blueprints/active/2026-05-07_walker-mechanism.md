# Task Blueprint: Walker Mechanism

- Status: draft
- Created: 2026-05-07
- Last Updated: 2026-05-07
- Related Modules:
  - `src/kernel/application/`
  - `src/kernel/application/docs/`
  - `src/kernel/audit/` (B3 reserved future only)
  - `src/kernel/tests/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [40_walker-mechanism-design-sketch.md](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md)
  - [50_migration-path.md §8](../../references/working/post-routemap-direction-selection-input/50_migration-path.md)
  - [Batch 8 Public Surface Decision (archived)](../archive/2026-05-06_public-surface.md)
  - [EntitySnapshot prior art](../../../src/kernel/sdk/facade.py)
- Parent: `docs/references/working/post-routemap-direction-selection-input/` (committed at `177b116`)
- Related Blueprint:
  - [2026-05-07_application-ergonomic-helpers-extension.md](2026-05-07_application-ergonomic-helpers-extension.md) — parallel-safe sibling per [50_ §5](../../references/working/post-routemap-direction-selection-input/50_migration-path.md)
- Audit Log:
  - [2026-05-07_walker-mechanism.audit.md](2026-05-07_walker-mechanism.audit.md)

## 1. Problem

Existing application / audit DTOs expose ergonomic friction at three sites:

1. **IR body iteration** on `RuleSpec.where` / `CompiledDerivationPlan.body_ir` requires raw tuple unpacking (`kind, *args = atom_tuple`), and these sources are mutable `list[Any]` that need a construction-time snapshot for safe iteration.
2. **Evidence cross-referencing** between `SupportArtifact.pred_witnesses` / `meta_witnesses` and ledger `Claim` lookup requires manual atom-key string parsing (`"pred:owner.path:asrt_id"`) and ledger boilerplate.
3. **`ProofFrameDiff.frame_deltas` / `atom_deltas` queries** require nested loops with manual filter-by-status-change-kind logic and manual flatten across frames.

These are the ~4-5 raw-tuple objects identified in Round 2 prior-art audit (most application / audit DTOs are already structured frozen dataclasses). Direct attribute access (e.g., `support.pred_witnesses[0].asrt_ids`) continues to work; B adds a wrapper-view layer (per `#8`) **without modifying any existing DTO**.

## 2. Goals

Add a walker mechanism in `kernel.application.walker` (with future `kernel.audit.walker` reserved as B3-future) covering:

**B1 — IR walker + collection protocol (mandatory):**

- `IRBodyWalker(rule_spec.where | plan.body_ir)` — construction-time snapshot via `tuple(source)`; iteration exposes `atom.kind` / `atom.pred_id` / `atom.args` / `atom.branch_index` / `atom.atom_index`.
- `FrozenTupleView(tuple)` / `frozen_collection(tuple)` with `.filter` / `.find` / `.first` / `.require_key` / `.require_position` (find returns `View | None`; require_* raise on miss).

**B2 — Evidence cross-reference + per-DTO wrapper views (mandatory):**

- `parse_atom_key(key) -> AtomKeyView`
- `SupportArtifactView(support, frozen_claim_index, frozen_meta_index=None)` exposing `.pred_witnesses` (`FrozenTupleView`), `.meta_witnesses`, `.lookup_assertion(asrt_id) -> AssertionView`
- `ProofFrameView(frame)` per Round 6 design
- `ProofFrameDiffView(diff)` per Round 7 (filter `frame_deltas` by `frame_status_change` kind; flatten `atom_deltas` across frames; final method names locked at this blueprint's Step 0)

**B3 — Audit / store walker (deferred / future-only, NOT B1/B2 acceptance):**

- Reserved as future scope; documented in [40_ §3](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md) as future-only. Reactivation requires real audit / ledger streaming consumer with bounded-stream contract per `#14`.

## 3. Non-goals

- **No B3 in this blueprint scope.** Audit / store stream walker is documented as reserved future contract; not implemented. B3 contract test sketches in 40_ §6 are NOT acceptance for this blueprint.
- **No SDK shell.** `kernel.sdk.__all__` is not modified; SDK examples / quickstart / user guide unchanged. (D2 acceptance gate per Round 6.)
- **No DTO mutation.** Walker views never modify existing tuple fields; never attach methods to `SupportArtifact.pred_witnesses` / etc. Direct tuple access continues to work.
- **No ledger / store hot path change.** Walker views read frozen indices passed at construction; do not call `Store.get_*` lazily inside iteration.
- **No demo rewrite in B blueprint scope.** Demo migration is follow-up doc work after B archive.
- **No release publish.** Direction E, user-gated.
- **No L-Full SDK shell.** Post-A+B v1-ready roadmap target.
- **No alias for `.underlying`.** No `.source` / `.carrier` / `.raw` (collide with provenance / evidence-carrier vocabulary per Round 4).

## 4. Current Context

**Source documents (cited throughout this blueprint):**

- [40_walker-mechanism-design-sketch.md](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md) — full design sketch (§1-§5 architecture; §4 walker invariants `#7`-`#19` operationalized; §6 contract test sketch).
- [50_migration-path.md §8](../../references/working/post-routemap-direction-selection-input/50_migration-path.md) — B blueprint handoff checklist (cited verbatim in §7 below).
- [Batch 8 §5.5.1 Public Surface Decision (archived)](../archive/2026-05-06_public-surface.md) — Tier 2 advanced importable definition.
- EntitySnapshot prior art at [src/kernel/sdk/facade.py:102-217](../../../src/kernel/sdk/facade.py) — wrapper-view template. **Caveats per Round 6:** no `_underscore` mutable internal exposure; no SDK private import; no observable cache; `WalkerFrozenError` is walker-layer, not SDK `FrozenSnapshotError` reuse.

**Branch state:** `v0.1-public-surface-2026-05-06`; bundle at `177b116`. Sacred branches `master` / `v0.1-oss-prep` not touched.

**Step 0 unknowns (resolved before transitioning draft -> scoped):**

- Module split: `kernel.application.walker` flat module vs subpackage (`walker/ir.py` / `walker/views.py`)
- Error class layout: `WalkerError` parent + `WalkerLookupError` / `WalkerParseError` / `WalkerReferenceError` / `WalkerSnapshotError` / `UnboundedStreamError` / `WalkerFrozenError` subclasses
- Final method names for `ProofFrameDiffView` (sketch names recorded in Round 7; final lock at Step 0)
- Test fixture layout

These are blueprint-scoped decisions.

## 5. Proposed Shape

Per [40_ §1-§5](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md). Highlights:

- **Construction-time snapshot** for mutable-source DTO walkers (e.g., `RuleSpec.where`, `CompiledDerivationPlan.body_ir`): `tuple(source)` on init; iteration is over the snapshot.
- **Wrapper-view pattern** (Round 6 + Round 7): per-DTO views (`SupportArtifactView`, `ProofFrameView`, `ProofFrameDiffView`) wrap, never modify; tuple fields not extended with methods.
- **Escape hatch:** every walker exposes `.underlying` (no `.source` / `.carrier` / `.raw` aliases).
- **Exact-access vocabulary:** `find(key | position) -> View | None`, `require_key(key) -> View` (raise on miss), `require_position(int) -> View` (raise on miss).
- **Future stream walker bound contract** (`#14`): if B3 later introduces `StreamWalker`, construction must satisfy at least one of `limit: positive int` / `snapshot=True + max_snapshot_items: positive int` / `source.bounded_size_hint() -> non-negative int`; otherwise raise `UnboundedStreamError`.
- **Equality / hash** (`#17`): views use structural equality where defined; identity is not stable; `.underlying` is excluded from equality / hash; walker instances themselves use default object identity.
- **Single-thread instances** (`#15`): walker not thread-safe; `MappingProxyType(dict(...))` for shallow read-only mapping exposure (per `#11` augmentation).
- **No observable cache** (`#9`): `.stats` returns counters only; no DTO-content cache that would skew equality / traversal results / error timing / memory lifecycle (the 5 protected dimensions per Round 5 minimal verification).

## 6. Boundaries And Invariants

- **B1/B2 only:** B3 audit / store stream walker is future-only. B1/B2 do not implement `StreamWalker`, `on_progress`, stream snapshot machinery, or bound enforcement tests.
- **Layer boundary:** `kernel.application` walker code must not import `kernel.sdk`. Future B3 audit walker code, if reactivated, lives under `kernel.audit` and does not import application walker types.
- **DTO boundary:** existing DTO fields remain unchanged; no tuple field gains methods; direct tuple access continues to work.
- **Store boundary:** B2 cross-reference helpers operate over frozen claim/meta indices passed at construction; no lazy store hot-path reads inside iteration.
- **Public-surface boundary:** no new `kernel.sdk.__all__` export, no SDK docs, no README quickstart change, no outward compatibility promise.
- **Syntax boundary:** `.underlying`, `find`, `require_key`, and `require_position` are the accepted vocabulary. `.source`, `.carrier`, `.raw`, `get`, and `at` remain forbidden for the walker surface.

## 7. Acceptance

Per [50_ §8 "B blueprint must cite / check"](../../references/working/post-routemap-direction-selection-input/50_migration-path.md):

- [ ] B1 + B2 shipped per scope above; B3 reserved (not implemented)
- [ ] No removal of direct tuple access on existing DTOs; `support.pred_witnesses[0].asrt_ids` continues to work after B archives
- [ ] No `kernel.sdk.__all__` modification; no SDK examples / quickstart / user guide change
- [ ] No demo rewrite in this blueprint scope
- [ ] Proposed Shape / Non-goals sections reference all walker invariants `#7`-`#19` operationalized in [40_ §4](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md)
- [ ] Contract tests per [40_ §6](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md) all pass:
  - Common contract: `.underlying` escape; `WalkerError` hierarchy; `find` / `require_key` / `require_position` semantics; equality / hash; no observable cache
  - Behavior-specific: IR walker atom unpacking; `FrozenTupleView` `.filter` / `.find` / `.first`; `SupportArtifactView` `.lookup_assertion`; `ProofFrameView`; `ProofFrameDiffView` filter-by-status-change-kind / flatten-atom-deltas
  - **Future-B3:** reserved StreamWalker / bound contract sketches in 40_ §6 are documented but **NOT executed** (not blueprint acceptance)
- [ ] B3 (audit / store stream walker) explicit non-goal documented
- [ ] grep / import-graph static audit: walker module does not import `kernel.sdk`
- [ ] Round 6 EntitySnapshot caveats honored: no `_underscore` exposure; no SDK private import; no observable cache; walker-layer error classes (not SDK reuse)

## 8. Implementation Plan

| Phase | Sub-batch | New module(s) | Tests added |
|---|---|---|---|
| 1 | B1 IR walker | `kernel/application/walker/ir.py` (or flat per Step 0) | `test_walker_ir.py` |
| 2 | B1 frozen tuple wrapper | `kernel/application/walker/views.py` (or shared) | `test_frozen_tuple_view.py` |
| 3 | B2 atom-key parser + SupportArtifactView + AssertionView | extend `walker/views.py` | `test_walker_support_view.py` |
| 4 | B2 ProofFrameView | same | `test_walker_proof_frame_view.py` |
| 5 | B2 ProofFrameDiffView (Round 7) | same | `test_walker_proof_frame_diff_view.py` |
| 6 | Cross-cutting invariants test sweep | n/a | error-hierarchy, equality/hash, B3-reserved bound contract documentation, single-thread docs-only invariant, no-cache (`#7`-`#19`) |
| 7 | B3 reserved-future contract documentation | docstring + reference to [40_ §3](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md) only; **no impl** | n/a |

Per phase:

1. Write test (red)
2. Implement walker / view (green)
3. Run full test suite + audit log entry
4. Update `kernel/application/__init__.py` to export the new walker / view name (Tier 2 advanced importable)
5. Move to next phase

## 9. Docs To Update

- `src/kernel/application/docs/README.md`
- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- B3 future only: `src/kernel/audit/docs/README.md` and audit docs are updated only if B3 is reactivated
- Audit log for this blueprint
- `docs/README.md` only if the blueprint introduces a new durable docs entry outside existing module docs

## 10. Outcome / Deviations

任务完成后填写：

- 最终落地结果：
- 与 blueprint 不同的地方：
- 为什么会有这些调整：
- 归档说明：
