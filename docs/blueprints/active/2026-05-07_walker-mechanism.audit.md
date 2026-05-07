# Task Blueprint Audit: Walker Mechanism

- Blueprint: [2026-05-07_walker-mechanism.md](2026-05-07_walker-mechanism.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-07 | draft | Blueprint created | Drafted from `post-routemap-direction-selection-input` bundle (committed at `177b116` on `v0.1-public-surface-2026-05-06`). Primary design sketch: [40_walker-mechanism-design-sketch.md](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md). Contract test sketch: [40_ §6](../../references/working/post-routemap-direction-selection-input/40_walker-mechanism-design-sketch.md). Handoff checklist: [50_migration-path.md §8](../../references/working/post-routemap-direction-selection-input/50_migration-path.md). Scope: B1 IR walker + frozen tuple wrapper + B2 evidence cross-reference + per-DTO wrapper views (`SupportArtifactView` / `ProofFrameView` / `ProofFrameDiffView`); B3 audit / store stream walker is reserved future-only (NOT B1/B2 acceptance). Honors 11 walker invariants `#7`-`#19` operationalized in 40_ §4. Parallel-safe sibling: [2026-05-07_application-ergonomic-helpers-extension.md](2026-05-07_application-ergonomic-helpers-extension.md) per [50_ §5](../../references/working/post-routemap-direction-selection-input/50_migration-path.md). |

| 2026-05-07 | draft | Step 0 Round 1 — Module split locked | B2 selected: create new `kernel.application.walker` package with `__init__.py` / `errors.py` / `keys.py` / `ir.py` / `views.py`. `errors.py` separated to stabilize `WalkerError` family before downstream imports;`keys.py` separated to keep atom-key parsing out of view classes;`ir.py` (walker) and `views.py` (per-DTO wrapper views) reflect two distinct abstractions per `#8`. B3 remains future-only — no `walker/stream.py` or audit-walker module created. Future per-DTO views split deferred until `views.py` grows or a per-DTO view becomes heavy. See blueprint §4.1. |
| 2026-05-07 | draft | Step 0 Round 2 — Error class layout locked | B-R2-2 (lightweight variant) selected: ship `WalkerError(Exception)` + 6 subclasses in `walker/errors.py` — 5 active (`WalkerLookupError` / `WalkerParseError` / `WalkerReferenceError` / `WalkerSnapshotError` / `WalkerFrozenError`) with concrete raise sites in B1/B2 code, plus 1 dormant (`UnboundedStreamError`) exported now but no B1/B2 raise site. Dormant export honors bundle's `#12` / `#14` documented hierarchy: omitting it would leave a doc-vs-module gap; class is no-cost since it has no behavior. B1/B2 explicit non-raise: no `StreamWalker` impl, no bound enforcement tests, no `UnboundedStreamError` raise path — class purely placeholder for B3 reactivation. Parent `WalkerError(Exception)` because walker errors span lookup / parse / state / reference / frozen semantics, matching SDK convention (`SDKError(Exception)`). See blueprint §4.1 Round 2. |
| 2026-05-07 | draft | Step 0 Round 3 — `ProofFrameDiffView` method names locked | B-R3-1 refined (minimal) selected: final signatures `frames_with_status_change() -> FrozenTupleView[FrameDelta]` / `iter_atom_deltas(*, kind: AtomDeltaKind \| None = None) -> Iterator[AtomDelta]` / `frames_with_atom_verdict_changes() -> FrozenTupleView[FrameDelta]`. Reuse existing `AtomDeltaKind` `Literal[...]` from `kernel.audit.proof_frame_diff` (no invented enum); `FrameStatusChangeKind` does NOT exist and was not invented. Drift fix: my Round 3 initial recommendation invented `FrameStatusChangeKind` — corrected per user code-reality verification. Minimal first: before/after fine-filter on `frames_with_status_change` deferred to follow-up when a real consumer signals; `iter_atom_deltas` returns lazy `Iterator` since cross-frame flatten size is unknown a priori. See blueprint §4.1 Round 3. |
| 2026-05-07 | draft | Step 0 process correction — Branch / worktree discipline locked | Parent `v0.1-public-surface-2026-05-06` carries shared blueprint / scoping docs only — **no `src/` implementation writes on parent**. B implementation isolated to a dedicated worktree at `/Users/zhenzhili/hnsm-backend-B`, branch `codex/v0.1-walker-mechanism-2026-05-07` (created off the Step 0 final commit). Worktree (not branch-only) chosen because parent worktree has 6 pre-existing dirty notebook modifications that should not propagate to implementation worktrees; `git switch` would carry them across. `codex/` prefix follows current Codex app branch convention; topic retains `v0.1-<topic>-<date>` semantic from parent's naming. Discipline written into audit log + blueprint §4 Branch state now (not deferred to implementation start) per user request to prevent verbal-only policy. Alt-A (rewind Round 1-3 to branch from `66f5231`) explicitly rejected: current changes are blueprint-doc-only, zero `src/` pollution so far, so shared-parent-anchor-then-worktree is lowest cost with cleanest boundary. |
| 2026-05-07 | draft | Step 0 Round 4 — Test fixture layout locked | B-R4-1 selected: greenfield walker, 8 flat per-component test files at `src/kernel/tests/`: `test_walker_errors.py` / `_keys.py` / `_ir.py` / `_views_frozen_tuple.py` / `_views_support.py` / `_views_proof_frame.py` / `_views_proof_frame_diff.py` / `_invariants.py`. Layout mirrors §4.1 Round 1 source split. `test_walker_invariants.py` covers cross-cutting `#7`-`#19`. Rationale: B is greenfield (zero existing walker tests), so per-component split has no migration cost. See blueprint §4.1 Round 4. **All 4 Step 0 rounds + process correction now locked; next entry transitions the blueprint to scoped.** |
| 2026-05-07 | scoped | Status transition `draft → scoped` | All 4 Step 0 Round decisions + process correction locked. Implementation can begin in the dedicated worktree at `/Users/zhenzhili/hnsm-backend-B` on branch `codex/v0.1-walker-mechanism-2026-05-07` (created off this commit on parent `v0.1-public-surface-2026-05-06`). Parent branch carries no further `src/` writes for B. Phase 0 (package skeleton + `errors.py` 7-class hierarchy) is the first implementation step in the worktree. |
| 2026-05-07 | implementing | Phase 1 local decision — single `IRAtomView` | Resolved the 40_ deferred question "one `IRAtomView` union type or one class per kind" at implementation time: Phase 1 uses one frozen `IRAtomView` with common surfaced fields (`kind` / `pred_id` / `args` / `branch_index` / `atom_index` / `key` / `.underlying`). Per-kind subclasses are deferred until a real consumer needs kind-specific behavior. Rationale: active blueprint Phase 1 acceptance only requires common traversal fields; adding empty per-kind classes now would create placeholder surface without behavior. |
| 2026-05-07 | implementing | Phase 2 local decision — `FrozenTupleView` semantics | Locked local semantics before implementation: `.first()` returns `None` on empty (aligned with `find = may miss -> None`); `require_key(value, *, key=extractor)` is exact-access and raises `WalkerLookupError` on miss, with default extractor checking `.key` / `.pred_atom_key` / `.step_key` / `.atom_key` / `.asrt_id` / `.id`; `.filter(...)` eagerly materializes a new `FrozenTupleView` because Phase 2 is DTO-backed small collection adapter, not B3 stream walker. |
| 2026-05-07 | implementing | Phase 0/1/2 strict audit | Multi-agent audit per plan [phase1-2-recursive-bunny.md](file:///Users/zhenzhili/.claude/plans/phase1-2-recursive-bunny.md). Round 1: 3 parallel Explore agents (Design alignment / Code quality / Cross-cutting invariants & test coverage) over commits `e4afe7d` / `088f195` / `f64e399` (~1003 lines code+tests). Round 2: synthesis + spot-verification of 2 BLOCKER claims, both downgraded after verification (single-thread docstring missing but impl is single-thread; determinism test missing but impl is trivially deterministic via tuple snapshot). Round 3: 13 findings total (0 blocker / 8 clarify / 5 minor); recommendation **PROCEED to Phase 3**. Full report at `## Phase 0/1/2 Audit Report (2026-05-07)` below. **No code files modified during audit (doc-only).** |
| 2026-05-07 | implementing | Phase 3 local decisions + blueprint wording drift fix | Locked atom-key grammar as `b{branch}.a{atom}:{payload}` with syntactic `parse_atom_key(...) -> AtomKeyView(kind="unknown")`; `SupportArtifactView` contextualizes keys with `.as_pred()` / `.as_step()`. `SupportArtifactView` requires caller-provided frozen claim index, defensively wraps indexes with `MappingProxyType(dict(...))`, and performs no live store reads. `AssertionView` is independently importable and snapshots mutable `Claim.rest_terms` while leaving `.underlying` as original `Claim` escape hatch. Blueprint wording drift fixed: `SupportArtifact` has `.non_fact_steps`, not `.meta_witnesses`. |
| 2026-05-07 | implementing | Phase 3 strict-audit fixes | Follow-up to read-only Phase 3 strict audit: fixed construction-time snapshot drift by deep-freezing assertion surfaces (`Claim.rest_terms` and `MetaRow.value`) at `SupportArtifactView` construction, while keeping `AssertionView` independently constructible with the same freezer. Added `AtomKeyView` constructor validation, malformed claim-row snapshot errors, meta-index defensive-copy regression, locator-preservation regression, direct DTO tuple access regression, and module-doc convention updates. |
| 2026-05-07 | implementing | Phase 1/2 strict-audit fixes | Follow-up to read-only Phase 1/2 strict audit: restored `#9` lazy traversal by changing `IRBodyWalker` to snapshot source only and build `IRAtomView` objects during traversal / lookup; moved recursive freezing into shared `walker/_freeze.py`; added set freezing + unhashable / recursive-value snapshot errors; tightened empty `pred` / `ruleref` id validation; froze `IRBodyWalker` instances; extended `FrozenTupleView.find(predicate=None, **attrs)` to match `.filter(...)`; formalized the `#17` `FrozenTupleView` content-wrapper carve-out in the blueprint. |
| 2026-05-07 | implementing | Phase 4 — ProofFrameView implemented | Added `ProofFrameView(ProofFrameRecheckResult)` as the Phase 4 per-DTO wrapper view. It exposes `status`, recursively frozen `binding_items`, `atom_verdicts` as `FrozenTupleView[ProofFrameAtomVerdict]`, and `.underlying` as the original DTO escape hatch. Kept Phase 4 independent from `SupportArtifactView` / claim lookup: callers join explicitly if needed. |
| 2026-05-07 | implementing | Phase 4 strict-audit fix | Follow-up to read-only Phase 4 strict audit: removed `source_id` constructor arg + property from `ProofFrameView` (drift from locked single-arg design); tightened `atom_verdicts` type hint to `FrozenTupleView[ProofFrameAtomVerdict]`; updated application overview docs (`55` -> `56`, walker entries, Phase 4 test list). Focused regression: 106 tests pass. |
| 2026-05-07 | implementing | Phase 5 — ProofFrameDiffView implemented | Added `ProofFrameDiffView(ProofFrameDiff)` as the final B2 per-DTO wrapper view. It exposes real DTO fields only (`round_a_id`, `round_b_id`, `frame_deltas`, `warnings`, `.underlying`) plus the three Round 3 locked helpers: `frames_with_status_change()`, `iter_atom_deltas(kind=None)`, and `frames_with_atom_verdict_changes()`. No B3 stream walker or live audit query introduced. Focused regression: 115 tests pass. |
| 2026-05-07 | implementing | Phase 5 strict-audit fix | Follow-up to read-only Phase 5 strict audit: fixed `ProofFrameDiffView.__hash__` for valid `FrameIdentity.binding_items` containing nested JSON dict/list values by adding a construction-time frozen frame-delta surface; added nested JSON regression coverage. Minor delete-guard / forbidden-alias sweeps deferred to Phase 6 common invariants. Focused regression: 116 tests pass. |
| 2026-05-07 | implementing | Phase 6 — Cross-cutting invariant sweep | Added `test_walker_invariants.py` covering frozen set/delete guards, `.underlying` escape hatch, forbidden aliases (`source` / `carrier` / `raw` / `get` / `at`), source-id scope, `.stats` absence, static no-`kernel.sdk` imports, dormant `UnboundedStreamError` no-raise audit, deterministic observable surfaces, and module docstring contracts for single-thread and B3 future-only posture. Pickling remains explicitly out of contract. Focused regression: 126 tests pass. |
| 2026-05-07 | implementing | Phase 7 — B3 reserved-future docs | Completed final doc-only phase: expanded `walker/__init__.py` module docstring and walker module README with B3 reactivation triggers, `40_` cross-reference, future `kernel.audit.walker` placement, bounded-stream contract, and dormant `UnboundedStreamError` posture. No implementation added. |

## Decision Notes

- Step 0 Round 1 (2026-05-07): Module split locked as B2 (subpackage layout). See §4.1 in blueprint for full layout, layering rationale, and future-split deferral.
- Step 0 Round 2 (2026-05-07): Error class layout locked as B-R2-2 (lightweight variant) — `WalkerError(Exception)` + 6 subclasses (5 active in B1/B2 + 1 dormant `UnboundedStreamError` for hierarchy coherence with bundle `#12` / `#14`). See §4.1 Round 2 in blueprint.
- Step 0 Round 3 (2026-05-07): `ProofFrameDiffView` method names locked as B-R3-1 refined (minimal). Reuse existing `AtomDeltaKind`; no invented enums. See §4.1 Round 3 in blueprint.
- Step 0 process correction (2026-05-07): Branch / worktree discipline locked. B implementation isolated to `/Users/zhenzhili/hnsm-backend-B` on `codex/v0.1-walker-mechanism-2026-05-07` (off Step 0 final commit on parent). Parent branch carries doc-only changes; no `src/` writes on parent. Worktree (not branch-only) chosen because parent has 6 dirty notebook modifications that must not propagate. See blueprint §4 Branch state.
- Step 0 Round 4 (2026-05-07): Test fixture layout locked as B-R4-1 — 8 flat per-component test files mirroring §4.1 Round 1 source split. Greenfield => no migration cost. See §4.1 Round 4 in blueprint.
- **Step 0 complete (2026-05-07):** All 4 Round decisions + process correction locked. Status is now `scoped`; create B worktree at `/Users/zhenzhili/hnsm-backend-B` from this parent commit before any implementation.
- Phase 1 local decision (2026-05-07): `IRBodyWalker` ships one frozen `IRAtomView` rather than per-kind atom view subclasses. This resolves the remaining 40_ IR-view-shape question without expanding scope; per-kind subclasses stay deferred until a consumer requires kind-specific methods.
- Phase 2 local decision (2026-05-07): `FrozenTupleView.first()` returns `None` on empty; `require_key(value, *, key=extractor)` uses default key-like attribute fallback but accepts caller extractor override; `.filter(...)` is eager and returns a new `FrozenTupleView`.
- Phase 0/1/2 audit (2026-05-07): no blockers detected; 8 clarify + 5 minor findings; recommendation **PROCEED to Phase 3**. One formal `#P1` carve-out requested for FrozenTupleView equality semantics (class-specific application of `#17`). See `## Phase 0/1/2 Audit Report (2026-05-07)` below for full findings table, aligned contracts, test coverage assessment, and follow-up bucketing.
- Phase 3 local decision (2026-05-07): atom-key parsing is syntactic first, with semantic contextualization in `SupportArtifactView`; assertion hydration is DTO-backed through caller-provided frozen indexes, never through live store lookup. Blueprint wording corrected from `.meta_witnesses` to actual `SupportArtifact.non_fact_steps`.
- Phase 3 strict-audit fix (2026-05-07): assertion hydration now snapshots and recursively freezes surfaced assertion data at `SupportArtifactView` construction time. `lookup_assertion(...)` remains lazy at the view-object level but reads pre-frozen data, preserving `#10` determinism while avoiding live store reads.
- Phase 1/2 strict-audit fix (2026-05-07): `IRBodyWalker` snapshots source at construction and builds `IRAtomView` lazily during traversal / lookup; `FrozenTupleView.find(...)` now mirrors `.filter(predicate=None, **attrs)`; `FrozenTupleView` equality/hash carve-out formally recorded under `#17`.
- Phase 4 implementation decision (2026-05-07): `ProofFrameView` remains a single-argument wrapper over real `ProofFrameRecheckResult` fields only (`status` / `binding_items` / `atom_verdicts` / `.underlying`). No `ProofAtomView`, no `SupportArtifactView` join, and no claim/meta index constructor arguments.
- Phase 4 strict-audit fix (2026-05-07): `ProofFrameView` implementation now matches the single-argument Phase 4 lock exactly; `source_id` remains available on generic `FrozenTupleView` / `SupportArtifactView` but is not part of `ProofFrameView`.
- Phase 5 implementation decision (2026-05-07): `ProofFrameDiffView` follows the Phase 4 single-argument / real-fields-only pattern. `frame_deltas` and `warnings` are shallow `FrozenTupleView` wrappers over already-validated DTO tuples. Equality/hash excludes `.underlying`; warning DTOs keep their original objects in `.warnings`, while hash surface uses frozen warning details so `WarningDTO.details` dicts do not make the view unhashable.
- Phase 5 strict-audit fix (2026-05-07): `FrameIdentity.binding_items` is `BindingJSON`, and its `JSONValue` leaves can be dict/list. The view still exposes raw `FrameDelta` objects via `.frame_deltas`, but equality/hash now use a private construction-time `_frame_delta_surface` that recursively freezes binding JSON values. This corrects the original Phase 5 design miss that treated validated JSON as automatically hash-safe.
- Phase 6 invariant-sweep decision (2026-05-07): cross-view determinism is tested over observable surfaced behavior, not necessarily object identity or class-level `__eq__` for every wrapper. `IRBodyWalker` is a walker instance, so determinism is its traversal sequence; `SupportArtifactView` determinism is tuple access plus assertion lookup. Pickling / cross-process serialization remains out of contract.
- Phase 7 doc-only close (2026-05-07): B3 remains reserved future-only. Reactivation requires a real audit / ledger streaming consumer and the bounded-stream construction contract from `#14`; implementation belongs in future `kernel.audit.walker` (plus stream primitives only if needed), not current application walker B1/B2.

## Phase 5 Audit Report (2026-05-07)

### Summary

Strict audit of current uncommitted Phase 5 `ProofFrameDiffView` implementation. Four read-only lanes were requested; agent limits required old agents to be closed, then four Phase 5 lanes ran. Verdict before this fix: **needs fix before commit / Phase 6** because `ProofFrameDiffView.__hash__` failed for a valid `ProofFrameDiff` with nested JSON binding values in `FrameIdentity.binding_items`.

### Findings table

| # | Severity | File:line | Description | Recommendation |
|---|---|---|---|---|
| P5-F1 | blocker | `walker/views.py:456`, `walker/views.py:469`, `audit/proof_frame_diff.py:19`, `audit/proof_frame_diff.py:363` | `ProofFrameDiffView._surface()` used raw `FrameDelta` objects. Valid `FrameIdentity.binding_items` may contain JSON dict/list leaves, making `hash(ProofFrameDiffView(...))` raise `TypeError`. | Keep `.frame_deltas` as shallow `FrozenTupleView[FrameDelta]`, but use a private frozen frame-delta surface for equality/hash; add regression with nested JSON binding values. |
| P5-F2 | minor / Phase 6 | `walker/views.py:407`, `test_walker_views_proof_frame_diff.py:157` | `__delattr__` frozen guard exists but focused Phase 5 tests only cover assignment mutation. | Defer to Phase 6 common invariant tests across walker views. |
| P5-F3 | minor / Phase 6 | `2026-05-07_walker-mechanism.md:236`, `test_walker_views_proof_frame_diff.py:163` | Phase 5 forbidden-alias test omits `.get` / `.at` despite syntax-boundary wording. | Defer to Phase 6 common syntax-boundary invariant sweep. |

### No-Issue Checks

- Locked helpers match the Step 0 Round 3 design: `frames_with_status_change()`, `iter_atom_deltas(kind=None)`, and `frames_with_atom_verdict_changes()`.
- Constructor is single-argument `ProofFrameDiffView(diff)`.
- No invented enum; implementation reuses existing `AtomDeltaKind`.
- No `source_id` on `ProofFrameDiffView`.
- No B3 stream walker or live audit query expansion.
- `.frame_deltas` / `.warnings` remain `FrozenTupleView` wrappers, and `.underlying` remains the original `ProofFrameDiff` escape hatch.
- `WarningDTO.details` hashability is handled through `_warning_surface`.
- `kernel.application.__all__` exports `ProofFrameDiffView` and module docs describe Phase 5 as implemented.

### Fix Verification

- Added construction-time `_frame_delta_surface` for hash/equality over nested `FrameIdentity.binding_items` JSON values.
- Added focused regression `test_hash_with_nested_json_binding_values`.
- Focused regression passed: 116 tests across walker Phase 0-5 tests, capability helpers, and ProofFrame runtime tests.

## Phase 4 Audit Report (2026-05-07)

### Summary

Strict audit of committed Phase 4 HEAD `fa133c1` (`feat(walker): B Phase 4 — ProofFrameView`). Audit used 2 parallel explorer lanes (design alignment + code quality) plus local coverage/docs/layering checks due agent thread limit. Verdict: **needs fix before Phase 5** because `ProofFrameView` drifted from the locked single-argument / real-fields-only surface by adding `source_id`.

### Findings table

| # | Severity | File:line | Description | Recommendation |
|---|---|---|---|---|
| P4-F1 | blocker | `walker/views.py:303`, `test_walker_views_proof_frame.py:43` | `ProofFrameView` accepted and exposed `source_id`, despite locked `ProofFrameView(frame)` shape and real DTO fields only | Remove `source_id` constructor arg, slot, property, inner `FrozenTupleView(..., source_id=...)`, and test assertion |
| P4-F2 | minor | `walker/views.py:338` | `atom_verdicts` property returned `FrozenTupleView[Any]` while docs describe `FrozenTupleView[ProofFrameAtomVerdict]` | Import `ProofFrameAtomVerdict` and tighten return annotation |
| P4-F3 | minor | `application/docs/01_overview.md`, `application/docs/01_overview_en.md` | Application overview docs under-reported exported surface (`55` instead of `56`), omitted `ProofFrameView`, and omitted `test_walker_views_proof_frame.py` | Update count, walker entry list, and focused test list |

### No-Issue Checks

- `ProofFrameView` otherwise uses real `ProofFrameRecheckResult` fields only: `status`, `binding_items`, `atom_verdicts`, and `.underlying`.
- No `ProofAtomView`, no `SupportArtifactView` join, no claim/meta index constructor path.
- `binding_items` are recursively frozen for surfaced reads and hashing.
- Frozen guard is present; no `.source`, `.carrier`, or `.raw` aliases.
- Exports exist in both `kernel.application.walker` and `kernel.application`.

### Verification

- Focused regression passed: 106 tests across walker Phase 0-4 tests, capability helpers, and ProofFrame runtime tests.
- Forbidden SDK import grep returned no matches.
- Stale `ProofFrameView future/not implemented` grep returned no current stale text.

## Phase 0/1/2 Audit Report (2026-05-07)

### Summary

Multi-agent audit of B Phase 0/1/2 commits (`e4afe7d` / `088f195` / `f64e399`, ~1003 lines code+tests across `walker/{__init__,errors,ir,views,keys}.py` + 3 test files). **No blockers detected.** 8 of 10 design contracts ALIGNED; 1 DRIFT (`errors.py` docstring wording vs blueprint §4.1 Round 2 phrasing); 2 design clarifications (intentional class-specific divergence in `find` signatures + FrozenTupleView equality). 11 code quality findings (0 blocker / 6 clarify / 5 minor). 7 cross-cutting invariant checks (5 PASS / 1 missing docstring contract / 1 design clarify). All blueprint §7 acceptance items for Phase 0–2 covered by tests; 1 missing determinism contract test (downgraded from BLOCKER after verifying impl is trivially deterministic via tuple snapshot).

### Findings table

| # | Severity | File:line | Description | Recommendation |
|---|---|---|---|---|
| F1 | clarify | `walker/errors.py:5-7` | Docstring says "5 B1/B2 subclasses with planned raise sites in later phases" but only 3 (`WalkerFrozenError` / `WalkerLookupError` / `WalkerSnapshotError`) actually have raise sites in Phase 0–2; `WalkerParseError` + `WalkerReferenceError` are Phase 3 scope | Refresh docstring to distinguish the 3 active vs 2 reserved-for-Phase-3; natural fit when Phase 3 lands those raise sites |
| F2 | clarify | `walker/__init__.py` + `ir.py` + `views.py` module docstrings | Walker invariant `#15` single-thread contract not mentioned in any walker module docstring; impl IS single-thread (GIL + no threading primitives + no shared mutable state) but contract is implicit | Add explicit "Walker instances are single-thread; do not share between threads" line in `walker/__init__.py` module docstring (or per-class where applicable) |
| F3 | clarify | `walker/errors.py` end | No `__all__` declared in `errors.py` — inconsistent with `ir.py` and `views.py` which both declare `__all__` | Add `__all__ = [...]` listing the 7 error classes alphabetically |
| F4 | clarify | `walker/views.py:149-153` (`_default_key`) | Returns the attr value as-is including `None` if the attr exists with `None` value; `require_key(value=None)` would then match items whose key attr happens to be `None` | Document the behavior or filter `None` values from valid keys (decide which is correct semantics) |
| F5 | clarify | `walker/views.py:137-143` | FrozenTupleView equality on `_items` (which IS the underlying tuple) differs from IRAtomView pattern (which excludes `.underlying`); justified because items ARE the content (no surface/underlying split), but blueprint `#17` phrasing is ambiguous; this is a class-specific application | Document divergence in `views.py` docstring; **formal `#P1` carve-out request** (see Carve-outs below) |
| F6 | clarify | `walker/ir.py:247` | `_build_atom_view` missing return type annotation; all other helpers in `ir.py` (e.g. `_snapshot_branches`, `_freeze_ir_value`, `_as_tuple`) have annotations | Add `-> IRAtomView` |
| F7 | clarify | `walker/ir.py:13-18` (IRAtomView docstring) | Wording on equality/hash is ambiguous; current docstring describes `.underlying` as escape hatch but doesn't explicitly state both equality and hash exclude it | Reword to "is excluded from equality and hash comparisons; serves as an escape hatch for the underlying frozen snapshot" |
| F8 | clarify | `walker/ir.py:217-230` (`_snapshot_atom`) | Validates only `pred` and `ruleref` kinds; other kinds (e.g. `nonsynth`, future kinds) silently pass unvalidated | Document forward-compat intent or add validation for known kind set |
| M1 | minor | `walker/ir.py:186` (`_snapshot_branches` early-return) | Empty source returns `()` correctly via early guard; `all(_is_atom(item) for item in [])` returns vacuous-true, so removing the guard would silently treat empty as "flat AND". Fragile if reordered | Add comment at line 186 explaining why early return is needed |
| M2 | minor | `walker/views.py:110-115` (`require_position` bool exclusion) | Rejects `bool` (since `isinstance(True, int) is True`) but error message just says "non-negative int" — bool exclusion intent not surfaced | Clarify message: `"position must be non-negative int (not bool): {position!r}"` |
| M3 | minor | `walker/views.py:81-96` (`filter()`) | Propagates `source_id` to returned view (line 96), but docstring (line 86) doesn't mention it | Add docstring line: "Preserves `source_id` in the returned view" |
| M4 | minor | `walker/ir.py:234-244` (`_freeze_ir_value`) | Recurses without depth bound or cycle detection — circular IR values would infinite-loop or hit Python recursion limit | Document precondition (IR values must be acyclic) or add depth guard with `WalkerSnapshotError` raise |
| M5 | minor | `test_walker_ir.py` + `test_walker_views_frozen_tuple.py` | Determinism contract test missing — no test traverses walker twice and compares output (impl IS trivially deterministic via tuple snapshot, but explicit test guards against future regressions) | Add `test_traverse_twice_yields_identical_sequence` to both test files (natural fit for Phase 6 invariants sweep) |

**Total: 13 findings (0 blocker / 8 clarify / 5 minor).**

### Aligned contracts (no drift)

Verified ALIGNED by Agent A (Design alignment):

- A1: `walker/` package layout matches §4.1 Round 1 (5 files: `__init__.py` / `errors.py` / `keys.py` / `ir.py` / `views.py`)
- A2: `WalkerError(Exception)` parent (NOT `ValueError`) per §4.1 Round 2 — confirmed at `errors.py:21`
- A3: 5 active subclasses defined per §4.1 Round 2
- A4: `UnboundedStreamError` defined; **no raise site in Phase 0–2 production code** (grep confirmed)
- A6: `IRBodyWalker` construction-time snapshot via `_snapshot_branches → tuple(...)` (`ir.py:183-196`)
- A7: `IRAtomView` frozen via `__slots__` + post-init lock; `__setattr__` raises `WalkerFrozenError` (`ir.py:20-60`)
- A8: `.underlying` escape only — no `.source` / `.carrier` / `.raw` / `.get` / `.at` aliases on walker public API
- A9–A10: `find` / `require_key` / `require_position` vocabulary on both `IRBodyWalker` and `FrozenTupleView`; `find` returns `View | None`, `require_*` raises `WalkerLookupError`
- A11: IRAtomView equality / hash on surface tuple (excludes `.underlying`) (`ir.py:90-106`)
- A12–A14: Phase 2 local decisions all honored — `.first() → None` on empty, `require_key(value, *, key=extractor)` keyword-only, `.filter()` eager
- A15: Default key extractor chain matches locked order (`key` / `pred_atom_key` / `step_key` / `atom_key` / `asrt_id` / `id`)

Verified PASS by Agent C (Cross-cutting invariants):

- `#5` Layer isolation: no `kernel.sdk` import in walker package or tests
- `#7` Vocabulary purity: no forbidden aliases on walker public API (only in docs as forbidden examples)
- `#8` DTO non-mutation: walker views don't mutate underlying (no `.append` / `.extend` / `del` / attribute assignment)
- `#9` No observable cache: no `@cache` / `@lru_cache` / `@cached_property` / `_cache` / `.stats` field
- `#17` Equality / hash consistency: equal objects hash equal in both classes

### Test coverage assessment

| Phase | Test file | Tests | Coverage vs blueprint §7 acceptance |
|---|---|---|---|
| Phase 0 | `test_walker_errors.py` | 6 | All §7 bullets covered (hierarchy import, subclass extension, parent-not-ValueError, raise/catch for 5 active, `__all__` set, re-export identity); Agent C minor: explicit `UnboundedStreamError` no-raise grep deferred to Phase 6 invariants sweep |
| Phase 1 | `test_walker_ir.py` | 14 | All §7 bullets covered (atom unpacking flat AND + OR-of-AND, `.underlying` escape, find/require_* semantics, snapshot errors, frozen view, equality/hash exclusion); M5: determinism contract test missing |
| Phase 2 | `test_walker_views_frozen_tuple.py` | 14 | All §7 bullets covered (`.filter` predicate + attr-kwargs, `.find`, `.first` None on empty, `.require_position`, `.require_key` with default + override, no forbidden aliases, structural equality/hash); Phase 2 local decisions all tested; M5: determinism implicit but not explicit |

### Pre-Phase-3 recommendation

**PROCEED to Phase 3** (`keys.py` + `SupportArtifactView` / `AssertionView`).

No blockers. Suggested follow-up bucketing:

- **Fix together with Phase 3:** F1 (`errors.py` docstring) — Phase 3 will land `WalkerParseError` + `WalkerReferenceError` raise sites, so docstring needs update anyway.
- **Quick polish before / during Phase 3:** F2 (single-thread docstring), F3 (`errors.py` `__all__`).
- **Defer to Phase 6 (cross-cutting invariants test sweep):** F5 (FrozenTupleView equality `#P1` carve-out), M5 (determinism contract test), Phase 6-reserved items (`UnboundedStreamError` no-raise grep, `.stats` access test, pickling rejection test).
- **Inline polish anytime:** F4, F6, F7, F8, M1–M4.

### Carve-out request

- **F5**: FrozenTupleView equality on `.underlying` (which IS items) is intentional class-specific application of `#17` rather than a violation. Recommend formal `#P1` carve-out at the next blueprint update — wording suggestion: "FrozenTupleView is a content-equality wrapper, not a surface/underlying view; `#17` `.underlying` exclusion principle applies only to walker classes with a separate surface representation (e.g. `IRAtomView`). For content-equality views, equality is defined over the underlying tuple itself."

### Audit method

- **Round 1 — Parallel exploration (3 Explore agents):** Design alignment / Code quality / Cross-cutting invariants & test coverage. Each agent received self-contained prompt with blueprint sections + code paths and produced a citation-grounded findings set.
- **Round 2 — Synthesis + spot-verification:** Direct synthesis (no Plan agent — given findings volume, direct synthesis was efficient). Spot-verified 2 BLOCKER claims via `grep -in "thread\|concurrent" walker/*.py` (confirmed 0 matches → `#15` docstring genuinely missing) and `grep -n "def test_"` on test_walker_ir.py (confirmed no `test_traverse_twice` method). Both BLOCKERs downgraded after verifying impl is structurally compliant; only docs/tests gaps.
- **Round 3 — Doc-only deliverable:** This report. **No code files modified during audit.**

Plan: [/Users/zhenzhili/.claude/plans/phase1-2-recursive-bunny.md](file:///Users/zhenzhili/.claude/plans/phase1-2-recursive-bunny.md).
