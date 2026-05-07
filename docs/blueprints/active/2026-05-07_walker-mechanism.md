# Task Blueprint: Walker Mechanism

- Status: scoped
- Created: 2026-05-07
- Last Updated: 2026-05-07
- Related Modules:
  - `src/kernel/application/walker/` (Step 0 Round 1: package — `__init__.py` / `errors.py` / `keys.py` / `ir.py` / `views.py`; see §4.1)
  - `src/kernel/application/__init__.py`
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

**Branch state:** Parent `v0.1-public-surface-2026-05-06`; bundle at `177b116`. **Implementation branch / worktree policy (Step 0 process correction, locked 2026-05-07; see audit log):** B implementation lands on a dedicated worktree at `/Users/zhenzhili/hnsm-backend-B`, branch `codex/v0.1-walker-mechanism-2026-05-07` (created off the Step 0 final commit on parent). Parent branch carries blueprint / scoping docs only — **no `src/` writes on parent**. Worktree (not branch-only) chosen because parent worktree has pre-existing dirty notebook modifications that must not propagate. `codex/` prefix follows current Codex app branch convention; topic retains the `v0.1-<topic>-<date>` semantic from parent's naming. Sacred branches `master` / `v0.1-oss-prep` not touched.

**Step 0 unknowns (resolved before transitioning draft -> scoped):**

- ✓ **Module split** — locked Round 1, 2026-05-07; B2 selected. See §4.1.
- ✓ **Error class layout** — locked Round 2, 2026-05-07; B-R2-2 (lightweight variant) selected. See §4.1.
- ✓ **`ProofFrameDiffView` method names** — locked Round 3, 2026-05-07; B-R3-1 refined (minimal) selected. See §4.1.
- ✓ **Test fixture layout** — locked Round 4, 2026-05-07; B-R4-1 selected. See §4.1.

**All Step 0 unknowns resolved.** Status is now `scoped`; implementation starts only in the dedicated B worktree described above.

### 4.1 Step 0 Decisions Locked

**Round 1 — Module split (2026-05-07): B2 selected.** Create new package:

```text
src/kernel/application/walker/
  __init__.py          # public re-export
  errors.py            # WalkerError hierarchy (subclass set finalized Round 2)
  keys.py              # parse_atom_key + AtomKeyView
  ir.py                # IRBodyWalker (B1)
  views.py             # FrozenTupleView + per-DTO views
                       #   (SupportArtifactView / ProofFrameView /
                       #    ProofFrameDiffView / AssertionView)
                       #   covers B1 frozen tuple + B2 wrapper views
```

**B3 remains future-only.** No `walker/stream.py` or audit-walker module is created in this blueprint scope.

**Layering rationale:**

- `errors.py` separated to stabilize the `WalkerError` family before view/walker modules import from it
- `keys.py` separated so atom-key parsing logic is not entangled with view classes
- `ir.py` (walker) and `views.py` (per-DTO wrapper views) are two distinct abstractions per `#8`; keeping them in one file inflates cognitive load without shared utility
- `views.py` houses both `FrozenTupleView` and per-DTO wrappers because per-DTO views compose `FrozenTupleView` for tuple field exposure

**Future per-DTO split deferred:** if `views.py` grows beyond ~500 lines or a per-DTO view becomes substantially heavy, a follow-up refactor can split per-DTO modules (`views/support.py` / `views/proof_frame.py` / etc.). Not in current scope.

---

**Round 2 — Error class layout (2026-05-07): B-R2-2 (lightweight variant) selected.** Ship `WalkerError(Exception)` + 6 subclasses, with `UnboundedStreamError` exported now but dormant until B3:

```python
class WalkerError(Exception):
    """Base for all walker-layer errors."""

class WalkerLookupError(WalkerError):
    """Raised by find / require_key / require_position on miss in raise-mode."""

class WalkerParseError(WalkerError):
    """Raised by parse_atom_key on malformed atom key."""

class WalkerReferenceError(WalkerError):
    """Raised by SupportArtifactView.lookup_assertion on missing claim ref."""

class WalkerSnapshotError(WalkerError):
    """Raised when construction-time snapshot integrity is violated."""

class WalkerFrozenError(WalkerError):
    """Raised on attempt to mutate a frozen view."""

class UnboundedStreamError(WalkerError):
    """Reserved for future B3 StreamWalker construction without bound (#14).

    NOTE: B1/B2 has no raise site for this error. Exported now to keep the
    finalized hierarchy coherent with bundle 40_ §4 / `#12` / `#14`;
    remains dormant until B3 reactivation introduces walker/stream.py."""
```

**Convention:**

- 5 active subclasses (`WalkerLookupError`, `WalkerParseError`, `WalkerReferenceError`, `WalkerSnapshotError`, `WalkerFrozenError`) — actually raised in B1/B2 code
- 1 dormant subclass (`UnboundedStreamError`) — exported but no raise site in B1/B2; bound contract per `#14` is documented in 40_ §4 and `walker/__init__.py` docstring, but not enforced via runtime check
- Parent `WalkerError(Exception)` because walker errors span lookup / parse / state / reference / frozen semantics — not all are value-validation
- All 7 classes live in `walker/errors.py` per §4.1 Round 1 layout, re-exported at `walker/__init__.py`

**B1/B2 explicit non-raise on `UnboundedStreamError`:** B1/B2 does NOT implement `StreamWalker`, does NOT test bound enforcement, does NOT raise `UnboundedStreamError`. The class is a hierarchy placeholder only — exported to honor bundle's documented `#12` / `#14` contract.

**Why not extend `ValueError`:** The application convention from A (`CapabilityHelperError(ValueError)`) is single-class; walker has 6 subclasses with distinct semantics (lookup vs parse vs reference vs state vs frozen). `Exception` parent matches SDK convention (`class SDKError(Exception)`).

---

**Round 3 — `ProofFrameDiffView` method names (2026-05-07): B-R3-1 refined (minimal) selected.** Final method signatures, no invented enum:

```python
class ProofFrameDiffView:
    """Wrapper view over ProofFrameDiff (kernel/audit/proof_frame_diff.py)."""

    def frames_with_status_change(self) -> FrozenTupleView[FrameDelta]:
        """Frames whose `frame_status_change` is not None
        (status transitioned between rounds)."""

    def iter_atom_deltas(
        self, *, kind: AtomDeltaKind | None = None
    ) -> Iterator[AtomDelta]:
        """Flatten `atom_deltas` across all frames. If `kind` given,
        filter to that AtomDeltaKind. AtomDeltaKind is the existing
        Literal['atom_added', 'atom_removed', 'atom_verdict_changed']
        from kernel.audit.proof_frame_diff."""

    def frames_with_atom_verdict_changes(self) -> FrozenTupleView[FrameDelta]:
        """Frames carrying any atom_delta with kind='atom_verdict_changed'."""
```

**Decisions:**

- **No new enum invented.** [`AtomDeltaKind`](../../../src/kernel/audit/proof_frame_diff.py) already exists as `Literal["atom_added", "atom_removed", "atom_verdict_changed"]`; reuse it. `FrameStatusChangeKind` does **NOT** exist;`FrameStatusChange(before, after)` is a typed dataclass and consumers can inspect `.before` / `.after` directly when fine-grained filtering is needed.
- **Minimal first:** `frames_with_status_change()` returns ALL frames with non-None `frame_status_change`. Before/after fine-filter (`before=`, `after=` kwargs) deferred until a real consumer asks for it — adding kwargs later is non-breaking.
- **`iter_atom_deltas(kind=None)` returns `Iterator`** (lazy), not `FrozenTupleView`, because cross-frame flatten size is unknown a priori. If perf telemetry shows materialization is acceptable, an `atom_deltas_view() -> FrozenTupleView` companion can be added later as non-breaking addition.
- **`frames_with_atom_verdict_changes()` is a derived helper** — implementable as `tuple(f for f in frame_deltas if any(d.kind == "atom_verdict_changed" for d in f.atom_deltas))`. Kept as a named method because the use case is common (Round 7 sketch) and the comprehension is awkward to inline.
- All three return values use `FrameDelta` / `AtomDelta` from `kernel.audit.proof_frame_diff` directly — element-level wrapping unnecessary because both are already frozen dataclasses with structured access.

**Why not before/after fine-filter at v1:** `FrameStatusChange.before` and `.after` each have 4 possible values (`"still_valid"` / `"invalidated"` / `"unknown"` / `None`), so a `before=` / `after=` kwargs API would have 4×4 = 16 meaningful combinations × wildcard-vs-exact match semantics. Designing this without a real consumer signal risks wrong abstraction. Defer to follow-up when a use case names the exact filter shape needed.

---

**Round 4 — Test fixture layout (2026-05-07): B-R4-1 selected.** Greenfield walker has no existing tests; flat per-component layout follows §4.1 Round 1 source split:

```text
src/kernel/tests/test_walker_errors.py             # Phase 0 — WalkerError hierarchy + dormant UnboundedStreamError
src/kernel/tests/test_walker_keys.py               # Phase 3 — parse_atom_key + AtomKeyView
src/kernel/tests/test_walker_ir.py                 # Phase 1 — IRBodyWalker
src/kernel/tests/test_walker_views_frozen_tuple.py # Phase 2 — FrozenTupleView standalone
src/kernel/tests/test_walker_views_support.py      # Phase 3 — SupportArtifactView + AssertionView
src/kernel/tests/test_walker_views_proof_frame.py  # Phase 4 — ProofFrameView
src/kernel/tests/test_walker_views_proof_frame_diff.py  # Phase 5 — ProofFrameDiffView per §4.1 Round 3
src/kernel/tests/test_walker_invariants.py         # Phase 6 — cross-cutting #7-#19
```

**Decisions:**

- **Per-component flat naming** matches existing `src/kernel/tests/` convention (e.g., `test_application_proofframe_runtime_native.py`). Discovery-friendly: `grep test_walker_views_support` finds B2 SupportArtifactView tests directly.
- **`test_walker_invariants.py` covers cross-cutting `#7`-`#19`:** `.underlying` consistency / `WalkerError` hierarchy import / single-thread docstring contract / no-cache `.stats` audit / B3-reserved (`UnboundedStreamError` no-raise grep audit) / equality / hash conventions.
- **Greenfield => no migration cost.** Unlike A (which preserves existing `test_application_capability_helpers.py` per its own §4.1 Round 4 conservative incremental decision), B has zero existing walker tests, so per-component split incurs no rearrangement churn.

---

**Step 0 complete.** All 4 Round decisions locked: B2 module split (Round 1), B-R2-2 lightweight error class layout (Round 2), B-R3-1 refined `ProofFrameDiffView` method names (Round 3), B-R4-1 test fixture layout (Round 4). Plus Step 0 process correction: branch / worktree discipline locked. Status is `scoped`; implementation starts only after the B worktree is created from this parent commit.

## 5. Proposed Shape

Per [40_ §1-§5](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md). Highlights:

- **Construction-time snapshot** for mutable-source DTO walkers (e.g., `RuleSpec.where`, `CompiledDerivationPlan.body_ir`): `tuple(source)` on init; iteration is over the snapshot.
- **IR atom view shape (Phase 1 decision):** `IRBodyWalker` exposes a single frozen `IRAtomView` (`kind` / `pred_id` / `args` / `branch_index` / `atom_index` / `key` / `.underlying`) rather than per-kind subclasses (`IRPredAtomView`, `IREqAtomView`, etc.). Per-kind subclasses are deferred until a consumer needs kind-specific methods beyond the common surfaced fields.
- **Wrapper-view pattern** (Round 6 + Round 7): per-DTO views (`SupportArtifactView`, `ProofFrameView`, `ProofFrameDiffView`) wrap, never modify; tuple fields not extended with methods.
- **Escape hatch:** every walker exposes `.underlying` (no `.source` / `.carrier` / `.raw` aliases).
- **Exact-access vocabulary:** `find(key | position) -> View | None`, `require_key(key) -> View` (raise on miss), `require_position(int) -> View` (raise on miss).
- **Future stream walker bound contract** (`#14`): if B3 later introduces `StreamWalker`, construction must satisfy at least one of `limit: positive int` / `snapshot=True + max_snapshot_items: positive int` / `source.bounded_size_hint() -> non-negative int`; otherwise raise `UnboundedStreamError`.
- **Equality / hash** (`#17`): views use structural equality where defined; identity is not stable; `.underlying` is excluded from equality / hash; walker instances themselves use default object identity.
- **Single-thread instances** (`#15`): walker not thread-safe; `MappingProxyType(dict(...))` for shallow read-only mapping exposure (per `#11` augmentation).
- **No observable cache** (`#9`): `.stats` returns counters only; no DTO-content cache that would skew equality / traversal results / error timing / memory lifecycle (the 5 protected dimensions per Round 5 minimal verification).

## 6. Boundaries And Invariants

- **B1/B2 only:** B3 audit / store stream walker is future-only. B1/B2 do not implement `StreamWalker`, `on_progress`, stream snapshot machinery, or bound enforcement tests. `UnboundedStreamError` is exported per §4.1 Round 2 as a dormant placeholder (no B1/B2 raise site) to keep the `WalkerError` hierarchy coherent with bundle's `#12` / `#14`.
- **Layer boundary:** `kernel.application` walker code must not import `kernel.sdk`. Future B3 audit walker code, if reactivated, lives under `kernel.audit` and does not import application walker types.
- **DTO boundary:** existing DTO fields remain unchanged; no tuple field gains methods; direct tuple access continues to work.
- **Store boundary:** B2 cross-reference helpers operate over frozen claim/meta indices passed at construction; no lazy store hot-path reads inside iteration.
- **Public-surface boundary:** no new `kernel.sdk.__all__` export, no SDK docs, no README quickstart change, no outward compatibility promise.
- **Syntax boundary:** `.underlying`, `find`, `require_key`, and `require_position` are the accepted vocabulary. `.source`, `.carrier`, `.raw`, `get`, and `at` remain forbidden for the walker surface.

## 7. Acceptance

Per [50_ §8 "B blueprint must cite / check"](../../references/working/post-routemap-direction-selection-input/50_migration-path.md):

- [ ] B1 + B2 shipped per scope above; B3 reserved (not implemented)
- [ ] Error class hierarchy per §4.1 Round 2 shipped at `walker/errors.py`: `WalkerError(Exception)` + 6 subclasses (`WalkerLookupError`, `WalkerParseError`, `WalkerReferenceError`, `WalkerSnapshotError`, `WalkerFrozenError`, dormant `UnboundedStreamError`); all 7 classes re-exported via `walker/__init__.py`
- [ ] `UnboundedStreamError` has no B1/B2 raise site (verified via grep audit); class definition only, no behavior
- [ ] Test fixture layout per §4.1 Round 4 shipped: 8 flat per-component files at `src/kernel/tests/`: `test_walker_errors.py` / `_keys.py` / `_ir.py` / `_views_frozen_tuple.py` / `_views_support.py` / `_views_proof_frame.py` / `_views_proof_frame_diff.py` / `_invariants.py`
- [ ] No removal of direct tuple access on existing DTOs; `support.pred_witnesses[0].asrt_ids` continues to work after B archives
- [ ] No `kernel.sdk.__all__` modification; no SDK examples / quickstart / user guide change
- [ ] No demo rewrite in this blueprint scope
- [ ] Proposed Shape / Non-goals sections reference all walker invariants `#7`-`#19` operationalized in [40_ §4](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md)
- [ ] Contract tests per [40_ §6](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md) all pass:
  - Common contract: `.underlying` escape; `WalkerError` hierarchy; `find` / `require_key` / `require_position` semantics; equality / hash; no observable cache
  - Behavior-specific: IR walker atom unpacking; `FrozenTupleView` `.filter` / `.find` / `.first`; `SupportArtifactView` `.lookup_assertion`; `ProofFrameView`; `ProofFrameDiffView` per §4.1 Round 3 — `frames_with_status_change()` / `iter_atom_deltas(kind=None)` / `frames_with_atom_verdict_changes()`
  - **Future-B3:** reserved StreamWalker / bound contract sketches in 40_ §6 are documented but **NOT executed** (not blueprint acceptance)
- [ ] B3 (audit / store stream walker) explicit non-goal documented
- [ ] grep / import-graph static audit: walker module does not import `kernel.sdk`
- [ ] Round 6 EntitySnapshot caveats honored: no `_underscore` exposure; no SDK private import; no observable cache; walker-layer error classes (not SDK reuse)

## 8. Implementation Plan

| Phase | Sub-batch | New module(s) | Tests added |
|---|---|---|---|
| 0 | Create package skeleton per §4.1 + ship `errors.py` per §4.1 Round 2 (`WalkerError(Exception)` + 6 subclasses including dormant `UnboundedStreamError`) | `kernel/application/walker/__init__.py` + `errors.py` (full 7-class hierarchy) + `keys.py` (skeleton) + `ir.py` (skeleton) + `views.py` (skeleton) | `test_walker_errors.py`: hierarchy import test — `from kernel.application.walker import WalkerError, WalkerLookupError, WalkerParseError, WalkerReferenceError, WalkerSnapshotError, WalkerFrozenError, UnboundedStreamError` all resolve |
| 1 | B1 IR walker | `kernel/application/walker/ir.py` | `test_walker_ir.py` |
| 2 | B1 frozen tuple wrapper | `kernel/application/walker/views.py` (`FrozenTupleView` first; per-DTO views in later phases) | `test_walker_views_frozen_tuple.py` |
| 3 | B2 atom-key parser + SupportArtifactView + AssertionView | `kernel/application/walker/keys.py` + extend `walker/views.py` | `test_walker_keys.py` + `test_walker_views_support.py` |
| 4 | B2 ProofFrameView | extend `walker/views.py` | `test_walker_views_proof_frame.py` |
| 5 | B2 ProofFrameDiffView (Round 7) | extend `walker/views.py` | `test_walker_views_proof_frame_diff.py` |
| 6 | Cross-cutting invariants test sweep | n/a | `test_walker_invariants.py`: error-hierarchy, equality/hash, B3-reserved bound contract documentation, single-thread docs-only invariant, no-cache (`#7`-`#19`) |
| 7 | B3 reserved-future contract documentation | docstring in `walker/__init__.py` + reference to [40_ §3](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md) only; **no impl** | n/a |

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
