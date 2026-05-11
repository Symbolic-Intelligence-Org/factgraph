# ReadPolicy Call-Site Migration and ViewSpec Removal from `fg.views`

- **Status:** draft
- **Created:** 2026-05-11
- **Last Updated:** 2026-05-11 (§5.3 LOCKED — L1 in-place at core; `ReadPolicy` enters `kernel.sdk.__all__`)
- **Parent:** post-rc.1 SDK terminology cleanup; no parent blueprint.
- **Related precedents:**
  - [2026-05-11_frozen-assertion-view-model (archived)](../archive/2026-05-11_frozen-assertion-view-model.md) — established `FrozenAssertionView` and the dual-type `fg.views` registry that this blueprint is now disambiguating.
  - [2026-05-10_assertion-selection-crud-ergonomics (archived)](../archive/2026-05-10_assertion-selection-crud-ergonomics.md) — sibling SDK ergonomic cleanup; same iterative-gap cadence.
  - [2026-05-09_post-l-sdk-ergonomics-redesign (archived)](../archive/2026-05-09_post-l-sdk-ergonomics-redesign.md) — closest public-API-shape precedent.
- **Audit Log:** [2026-05-11_readpolicy-call-site-migration.audit.md](./2026-05-11_readpolicy-call-site-migration.audit.md)
- **Baseline:** `ace2563` (`docs(sdk): clarify view projection policy status`), current `origin/master` HEAD; design branch `v0.1-readpolicy-call-site-migration-2026-05-11` forked here.

> **Design-only at draft.** Implementation only after status flips to `scoped`. §0 records the initial direction the 2026-05-11 user–Claude design discussion converged on; the iterative §5.x cycle source-grounds and locks each decision one at a time. Per `feedback_blueprint_workflow`: no Claude plan mode. Per `feedback_iterative_gap_design`: one gap LOCKED at a time with an audit row per lock.

## 0. Initial Direction (pending §5 validation)

The 2026-05-11 design discussion converged on the following direction. Each item is a **working hypothesis** until its corresponding §5.x gate locks it (or rejects and replaces it):

0.1 **`ViewSpec` is removed from the `fg.views` registry.** The registry currently holds two semantically heterogeneous types (`ViewSpec` policy-bag + `FrozenAssertionView` membership); `ViewSpec` migrates out.

0.2 **`fg.views` becomes single-meaning: frozen assertion-id membership only.** Post-migration `fg.views.get(name) → FrozenAssertionView` is the only return type; no `ViewSpec | FrozenAssertionView` union.

0.3 **A new value object replaces `ViewSpec`.** Working name `ReadPolicy` (alternative: `DisplayPolicy`). Final name at §5.1. The value object is constructed and passed; **it is not a registry entry**.

0.4 **`policy=` kwarg replaces `view=`** for projection/display-policy usage on `fg.read.find(...)` and `fg.run(...)`. Final kwarg ergonomics at §5.5.

0.5 **`fg.projections` is NOT introduced.** "Projection" terminology already occupies three kernel-internal meanings (see §4.3); a fourth SDK-surface use would compound the overload.

0.6 **Policy fields are NOT flattened into `find(...)` kwargs.** Identity / field filters on `find(...)` already consume kwargs (e.g. `find(User, source="seed")` where `source` could be a User field); inlining `confidence_strategy=`, `prefer_source=`, `active=` would collide with field filters.

### 0.7 Release-context note: clean cut, no compatibility window

factpy-kernel has **not been publicly released**. `v0.1.0-rc.1` is a release candidate; `v0.1.0rc2` has been version-bumped on `master` (commit `e46bc08`) but not tagged. There is no known downstream consumer to protect.

**Consequence:** this blueprint defaults to **hard cutover** semantics — no `DeprecationWarning` grace period, no `ViewSpec = ReadPolicy` alias, no `view=` kwarg fallback. Old paths are removed or raise immediately with a redirect-to-new-API error. §5.6 holds the exact removal-vs-redirect mechanic; §5.10 confirms the migration ships in the next release without a transitional period.

## 1. Problem

The SDK's `fg.views` namespace currently holds two unrelated concepts behind one CRUD surface:

- **`ViewSpec`** (`src/kernel/core/store/types.py:48`) — a *named read-time policy*: `active` flag, `confidence_strategy` (max / mean / median / prefer_source), `prefer_source` source label. Used by `fg.read.find(..., view=)` to attach `row.confidence` metadata, and by `fg.run(..., view=, return_display_meta=True)` for display aggregation. Behavior is **aggregation + source-preference scoring**, not relational-algebra projection.
- **`FrozenAssertionView`** (`src/kernel/sdk/store.py:67`) — a *named, frozen subset of assertion ids*. Used to bookmark a set of assertion records for later retrieval via `fg.assertions.by_ids(view.asrt_ids)`.

They share `_SDKViewsManager._views` (`src/kernel/sdk/store.py:81`) as one backing dict. `create` / `update` / `get` / `list` all return `ViewSpec | FrozenAssertionView`. A user reading the SDK docs cannot tell which "view" they are creating without inspecting constructor kwargs. The 2026-05-11 design discussion (summarized in audit) confirmed this as the precise pain point.

A simultaneous secondary issue: three SDK docs files (`src/kernel/sdk/docs/00_user_guide.en.md`, `02_readwrite_and_ingest.en.md`, `04_api_surface.en.md`, all touched today by `ace2563` and `4a794f3`) currently teach the dual-type `fg.views` surface, and `examples/05_sdk_assertion_views.ipynb` (added today in `58c07fc`, 368 lines) demonstrates the old syntax. These freshly-shipped docs and examples will need full rewrite at Phase 3, not patching.

## 2. Goals

- **Design-only deliverable at scope-freeze.** Reach `scoped` with: Policy DTO design (§5.1–§5.3), final-state `fg.views` semantics (§5.4), call-site API (§5.5), old-API removal mechanic (§5.6), non-SDK reference sweep plan (§5.7), docs + examples rewrite plan (§5.8), test plan (§5.9), and release checklist (§5.10). No SDK code lands until status is `scoped`.
- **Source-ground every choice.** Same falsifier discipline as G1–G5 + post-L redesign: each §5.x question gets a read-only research pass against the current codebase before locking.
- **Hard cutover by default.** Per §0.7, factpy-kernel is pre-release; no compatibility-grace surface unless §5.x explicitly identifies a non-removable internal consumer.
- **Single-meaning `fg.views`.** Post-migration the namespace exclusively manages frozen assertion-id membership.
- **`policy=` value-object call-site API.** Replace `view=` for policy/display usage on `find(...)` and `run(...)`; reject any named-string fallback at §5.5 to prevent a registry from re-emerging under a new name.

## 3. Non-Goals

- **No `fg.projections` namespace.** Locked at §0.5; source-grounding in §4.3.
- **No flattened policy kwargs on `find(...)` / `run(...)`.** Locked at §0.6.
- **No compatibility-grace alias surface.** Per §0.7 pre-release state; old `ViewSpec`, `view=`, and `fg.views.create(name, ViewSpec(...))` paths are removed or raise immediately. Exact mechanic at §5.6.
- **No `FrozenAssertionView` API change.** Already shipped on `v0.1-frozen-assertion-view-2026-05-11`. The membership side of `fg.views` is treated as fixed; only `ViewSpec` migrates out.
- **No `kernel.core` runtime logic change for `confidence_strategy` / `prefer_source` / `active`.** The fields keep their existing semantics; only their carrier DTO and call-site shape change. Aggregation code paths in `store.py:561` / `:1384` / `:1495` / `:1986` continue to consume the same field values under the new DTO.
- **No `kernel.application.protocol` DTO change unless §5.7 audit requires it.** ViewSpec may have application-layer references; §5.7 scopes the cross-layer sweep.
- **No rule evaluator change.** `kernel.core/view/projector.py` (which independently owns "projection" terminology) is not touched.
- **No SDK code on design branch.** This blueprint branch `v0.1-readpolicy-call-site-migration-2026-05-11` holds **design / blueprint commits only**. All implementation post-scope-freeze happens on the paired impl branch `v0.1-readpolicy-call-site-migration-impl-2026-05-11` (created at design HEAD at scope-freeze time, per `feedback_design_impl_branch_isolation`).

## 4. Current Context

### 4.1 `fg.views` registry today (HEAD `ace2563`)

`_SDKViewsManager` at `src/kernel/sdk/store.py:73`–`:141`:

- Backing storage: single dict `_views`, initialized with `{"default": ViewSpec()}` (line 81). `default` is a built-in entry; `delete("default")` raises `SDKStoreError("cannot delete built-in view: default")`.
- `create(name, view_spec=..., *, asrt_ids=..., asrts=...)` dispatches to `_build_view_entry`, which produces either a `ViewSpec` or a `FrozenAssertionView` depending on which kwarg arrived.
- `update(name, ...)` — same dispatch.
- `delete(name)` — works for both types; refuses `default`.
- `get(name) → ViewSpec | FrozenAssertionView` — union return type.
- `list() → dict[str, ViewSpec | FrozenAssertionView]` — union value type.

The union return type and dual-mode constructor are the visible surface of the conceptual collision.

### 4.2 `ViewSpec` today (`src/kernel/core/store/types.py:48`–`:59`)

Frozen dataclass, three fields:

| Field | Type / domain | Semantics |
|---|---|---|
| `active` | `bool` (default `True`) | Whether the policy is applied. |
| `confidence_strategy` | `"max" \| "mean" \| "median" \| "prefer_source"` (default `"max"`) | How to aggregate confidence across multiple history rows backing the same coordinate. |
| `prefer_source` | `str \| None` (default `None`) | Source label preferred when `confidence_strategy == "prefer_source"`. |

Validation in `__post_init__`. No method behavior. All three fields are **read-time aggregation / source-preference policy**; none of them is "projection" in the relational-algebra sense.

### 4.3 "projection" terminology occupation (kernel-internal)

`projection` is already heavily used in the kernel for three distinct concepts:

| Existing use | Location | Meaning |
|---|---|---|
| `ViewProjectionError` + projection logic | `src/kernel/core/view/projector.py` | Query-time claim/argument → row projection. |
| `_validate_projection` + `projection` sub-key in schema IR | `src/kernel/core/schema/schema_ir.py` | Schema IR's `projection` field for predicate cardinality. |
| "annotation projection" | `src/kernel/tests/test_write_protocol_annotations.py` | Write-protocol annotation projection (e.g. `set_field` projection). |

Adding `fg.projections` as a fourth, SDK-surface meaning would force any reader of kernel source to disambiguate four "projection"s in their head. Rejected at §0.5.

### 4.4 `view=` call-site consumers

- `fg.read.find(..., view=)` — drives confidence aggregation via `_build_entity_confidence_by_ref` (`src/kernel/sdk/store.py:561`, `:1986`).
- `fg.run(rule, view=, return_display_meta=True)` — display-metadata aggregation (`src/kernel/sdk/store.py:1384`, `:1495`).

`view=` accepts either a `ViewSpec` instance or a registered name resolved via `_SDKViewsManager._views.get`.

### 4.5 Recent neighbor work (timeline)

| Date | Commit | Touched surface |
|---|---|---|
| 2026-05-11 (today) | `ace2563` | 3 SDK docs files — added current-status disclaimer on view/projection policy. |
| 2026-05-11 | `4a794f3` | 5 SDK docs files — updated assertion-selection syntax (frozen-view side). |
| 2026-05-11 | `58c07fc` | Added `examples/05_sdk_assertion_views.ipynb` (368 lines) teaching the old dual-type syntax. |
| 2026-05-11 | `e46bc08` | Bumped version to `0.1.0rc2` on `master`. |
| 2026-05-11 | `004d074` | Archived frozen-assertion-view-model blueprint. |
| 2026-05-10 | (multiple) | Primary identity pair shipped; assertion-selection CRUD ergonomics shipped. |
| 2026-05-10 | `1aa157c` | `v0.1.0-rc.1` tagged on `release/0.1.x`. |

The disclaimer added in `ace2563` is intentionally minimal — it acknowledges the collision but does not migrate. This blueprint replaces those paragraphs wholesale at Phase 3.

### 4.6 Pre-release status (impact on design defaults)

- `release/0.1.x` HEAD `1aa157c` was tagged `v0.1.0-rc.1` on 2026-05-10.
- `master` HEAD `ace2563` already carries `chore(release): bump version to 0.1.0rc2` (`e46bc08`).
- No PyPI publish, no GitHub Release announcement.
- No external downstream consumer is known.

**Consequence (carries §0.7):** hard cutover is the default. Surface compatibility is not a hard constraint.

### 4.7 Out-of-SDK ViewSpec references (preliminary; full sweep at §5.7)

Preliminary inspection indicates `ViewSpec` is referenced in:

- `src/kernel/core/store/types.py` — definition site.
- `src/kernel/sdk/store.py` — registry + dispatch.
- `src/kernel/application/protocol/` — possible application-layer DTO (audit at §5.7).
- `src/service/runtime_v1.py` — likely service-layer consumer (audit at §5.7).
- `src/kernel/tests/` — multiple test files.
- Various SDK docs.

§5.7 sweeps the actual counts and decides which references must change vs. which are internal-only and stay.

## 5. Iterative Gaps

Per `feedback_iterative_gap_design`: one §5.x LOCKED at a time; audit-log row per lock; semantic contract not literal strings; user–Claude review loop per gap.

| # | Gap | Primary decision points |
|---|---|---|
| §5.1 | **Policy DTO naming. — LOCKED** | DTO name = `ReadPolicy`. Semantic boundary locked (see §5.1 subsection below). Module location + `__all__` export NOT decided here — see §5.3. |
| §5.2 | **Policy DTO field set. — LOCKED** | `ReadPolicy` carries 3 fields: `respect_revocations` (renamed from misnomer `active`), `confidence_strategy`, `prefer_source`. Future fields DEFERRED. Single consumer `kernel/sdk/store.py:2070` migrates with the rename. See §5.2 subsection below. |
| §5.3 | **DTO module location + public export. — LOCKED** | `ReadPolicy` defined at `kernel/core/store/types.py` (in-place replace of `ViewSpec`); enters `kernel.sdk.__all__` (35 → 36); `ConfidenceStrategy` stays core-only (not exported). See §5.3 subsection below. |
| §5.4 | **`fg.views` final semantics.** | Post-migration union → single `FrozenAssertionView` return. Decide built-in `default` entry: keep as empty `FrozenAssertionView(name="default", asrt_ids=frozenset())` vs drop the built-in entirely. |
| §5.5 | **`policy=` call-site API.** | `find(..., policy=...)` and `run(..., policy=...)` accept Policy DTO value-object only? Accept inline dict (`policy={"confidence_strategy": "max"}`)? Accept named-string (which would resurrect the registry under a new name — **default reject** per §0.3)? Type-validation behavior on invalid input. |
| §5.6 | **Old API removal mechanic.** | Per §0.7 default = hard cut. Old `ViewSpec` import: removed entirely vs raise on construction. Old `fg.views.create(name, ViewSpec(...))`: `TypeError` vs `SDKStoreError` with redirect message. Old `view=` kwarg on `find` / `run`: raise vs silent ignore. Final error texts for each path. |
| §5.7 | **Non-SDK ViewSpec reference sweep.** | Full grep of `ViewSpec` across `src/kernel/application/protocol/`, `src/service/`, `src/kernel/audit/`, `src/kernel/tests/`. For each reference: keep (internal-only) vs migrate (cross-layer) vs delete (dead). |
| §5.8 | **Docs + examples rewrite.** | SDK docs touched by `ace2563` + `4a794f3`. The new `examples/05_sdk_assertion_views.ipynb` (`58c07fc`, 368 lines) added today with old syntax — must be rewritten or retired. Doc-URL strategy for §5.6 redirect messages. |
| §5.9 | **Test coverage plan.** | Policy DTO contract tests (3 fields × validation paths). `policy=` kwarg behavior on `find` / `run`. Removal-redirect tests for each §5.6 deprecated path. Existing ViewSpec test sweep — delete vs rewrite. |
| §5.10 | **Release checklist.** | Confirm next release (rc.2 successor or rc.3) ships the migration. Per §0.7 no compat-window discussion needed; this gap is purely a checklist confirmation (`kernel.sdk.__all__` diff, allowlist sync, deny-pattern grep updates per `feedback_release_workflow_traps`). |

§5.1 is the first gap; subsequent gaps proceed in numerical order unless a downstream dependency forces reordering.

### §5.1 LOCKED — Policy DTO name = `ReadPolicy`

**Final DTO name:** `ReadPolicy`.

**Semantic boundary (locked verbatim):**

> `ReadPolicy` names the read-time resolution/display policy applied after facts are read, not graph membership. It replaces the old `ViewSpec` name for this policy surface; `view` remains reserved for assertion-membership views.

**What this gap locks:**

- The Python class name for the new DTO is `ReadPolicy`.
- The `policy=` kwarg on `find(...)` / `run(...)` carries a `ReadPolicy` value (final call-site shape at §5.5).
- The semantic boundary forbids using `ReadPolicy` as a successor to "view" naming; `view` / `fg.views` stay exclusively about frozen assertion-id membership.
- `ReadPolicy` is positioned to absorb future read-time resolution/display fields (e.g., `tie_breaker`, `merge_rule`, `confidence_propagation`) under one DTO rather than splitting into per-concern policy classes; whether any such field actually ships is **out of scope** for §5.1 and gated by §5.2.

**What this gap does NOT lock:**

- Module location and import path of `ReadPolicy` → §5.3.
- Field set (which of `active` / `confidence_strategy` / `prefer_source` carry over, and which new fields ship) → §5.2.
- Whether `ReadPolicy` is exported from `kernel.sdk.__all__` → §5.3.
- Call-site form of `policy=` (value-only vs inline-dict vs named-string) → §5.5.
- Old `ViewSpec` removal mechanic → §5.6.

**Why `ReadPolicy` (rejection rationale for the 4 alternatives):**

- `DisplayPolicy` rejected: narrows scope to display surfaces, but `active` and future `tie_breaker` / `merge_rule` are read-time resolution, not display. Lock-in risk of forcing future fields to break out into separate policy classes.
- `AggregationPolicy` rejected: only covers `confidence_strategy`; cannot account for `active`.
- `ResolutionPolicy` rejected: "resolution" overlaps with conflict resolution and identity resolution, both already domain terms in the kernel.
- `ReadDisplayPolicy` rejected: hybrid naming signals fuzzy scope; verbose; inconsistent with factpy short-name style (`SDKStore`, `BatchTx`, `EntitySnapshot`).

### §5.2 LOCKED — Field set: 3 fields, `active` renamed to `respect_revocations`, future fields deferred

**Final `ReadPolicy` shape:**

```python
@dataclass(frozen=True)
class ReadPolicy:
    respect_revocations: bool = True
    confidence_strategy: ConfidenceStrategy = "max"
    prefer_source: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.respect_revocations, bool):
            raise ValueError("ReadPolicy.respect_revocations must be bool")
        if self.confidence_strategy not in {"max", "mean", "median", "prefer_source"}:
            raise ValueError(
                "ReadPolicy.confidence_strategy must be one of: max, mean, median, prefer_source"
            )
        if self.prefer_source is not None and (
            not isinstance(self.prefer_source, str) or not self.prefer_source
        ):
            raise ValueError("ReadPolicy.prefer_source must be non-empty string or None")
```

**Misnomer migration (recorded verbatim):**

> `ViewSpec.active` was a misnomer. In runtime it controlled whether revoked claims are skipped during confidence/display aggregation. The new field is `ReadPolicy.respect_revocations`.

**Source-grounded consumer audit:**

`view_spec.active` has exactly one runtime consumer: `src/kernel/sdk/store.py:2070`:

```python
if view_spec.active and ledger.has_active_revocation(claim.asrt_id):
    continue
```

This call site migrates to `policy.respect_revocations` during Phase 2 implementation. No other production code reads `.active` on a `ViewSpec`. (Test references separately handled at §5.9.)

**What this gap locks:**

- **A — Field-name carry-over with `active` rename.** `active` → `respect_revocations` (positive-boolean, default `True`). `confidence_strategy` and `prefer_source` keep names + defaults verbatim.
- **B — `__post_init__` validation form.** Mirror existing ViewSpec validation: bool type check; Literal membership check; non-empty-string-or-None check. Error message prefix swaps to `ReadPolicy.<field>`.
- **C — Dataclass decorator.** `@dataclass(frozen=True)`, no `slots=True`, no `kw_only=True`. (Matches existing ViewSpec shape; no metaclass churn.)
- **D — `ConfidenceStrategy` type alias position.** Stays at `kernel.core.store.types` line 14. Independent of `ReadPolicy`'s eventual location (§5.3). `kernel/core/view/confidence.py` continues to import it unchanged. `ReadPolicy` imports `ConfidenceStrategy` from `kernel.core.store.types` regardless of §5.3 outcome.
- **E — Future-fields DEFER list + reopen trigger.** DEFERRED fields: `tie_breaker`, `merge_rule`, `confidence_propagation`, and any other field not in the 3-field set above. **Reopen trigger**: a concrete use case + a separate scoped blueprint (or a §5 amendment to this blueprint). No speculative field placeholders.

**Docs implication (cross-reference for §5.8):**

`respect_revocations` must be documented as a first-class, prominent field — not hidden as an "advanced option" — because it directly teaches the relationship between `retract` and read/display confidence. §5.8 docs rewrite plan inherits this constraint.

**What this gap does NOT lock:**

- DTO module location and import path → §5.3.
- Whether `ReadPolicy` enters `kernel.sdk.__all__` → §5.3.
- Call-site shape of `policy=` (value-only vs inline-dict vs named-string) → §5.5.
- Old `ViewSpec` import / construction removal mechanic → §5.6.
- Test coverage for the rename + revocation-respect behavior → §5.9.

### §5.3 LOCKED — `ReadPolicy` at `kernel/core/store/types.py`; re-exported from `kernel.sdk.__all__`

**Location:** `ReadPolicy` is defined at `kernel/core/store/types.py`, **in-place replacing** the existing `ViewSpec` class. No new module is created. (`kernel/sdk/types.py` is not introduced.)

**Public export:**

- `ReadPolicy` enters `kernel.sdk.__all__`. Surface size: **35 → 36**. Users import as `from kernel.sdk import ReadPolicy`.
- `ConfidenceStrategy` stays at `kernel.core.store.types:14` and is **NOT** added to `kernel.sdk.__all__`. Users who need the literal type for type-hinting can `from kernel.core.store.types import ConfidenceStrategy`, but typical usage is the string literal `"max"` / `"mean"` / `"median"` / `"prefer_source"` directly. Honors `feedback_narrow_public_api` (current scope does not explicitly require user-facing access to the alias).

**Clarifying note (locked verbatim):**

> `ReadPolicy` is a core value object re-exported by the SDK, not an SDK-only facade type. Core projector and service runtime may consume it directly; user-facing examples should import it from `kernel.sdk`.

This locks the **implementation/user-entry split**: the source location (`kernel/core/store/types.py`) is for internal consumers (`kernel/core/view/projector.py`, `kernel/sdk/store.py`, `src/service/runtime_v1.py`); user-facing docs and examples must import from `kernel.sdk` and must not reference `kernel.core.store.types` as a user entry point.

**Rationale recap (source-grounded):**

- `project_display_facts(ledger, view_spec)` at `kernel/core/view/projector.py:205` is a **core-layer** function with two callers (`kernel/sdk/store.py:2005`, `src/service/runtime_v1.py:852,866`). Moving `ReadPolicy` to SDK would require either inline-kwargs signature pollution, a single-consumer Protocol type, or relocating the projector function down to SDK — all worse than letting core continue to define the DTO.
- `ReadPolicy` is a 3-primitive frozen value object; substrate-shape, not SDK-shell-shape.
- Existing `from kernel.core.store.types import ViewSpec` consumers (service runtime + projector) become `from kernel.core.store.types import ReadPolicy` — minimum mechanical churn for the §5.7 sweep.
- `ConfidenceStrategy` is a `Literal` `TypeAlias`; users virtually never need to import the alias name because string literals already type-check against it.

**Implementation cross-references (for Phase 2 after scope-freeze):**

| Path | Change scope |
|---|---|
| `kernel/core/store/types.py` | Replace `ViewSpec` class with `ReadPolicy` class (per §5.1 + §5.2). |
| `kernel/core/view/projector.py:12, 205-212` | Import swap; signature `view_spec: ViewSpec` → `policy: ReadPolicy`; isinstance check class swap; field access `.active` → `.respect_revocations`. |
| `kernel/sdk/store.py:38, 81, 89-93, 109-113, 134, 140, 565, 1389, 1428, 1445, 1461, 2005, 2066, 2070` | Import swap + all type annotations + `.active` → `.respect_revocations` at line 2070. `default` entry handling is §5.4. |
| `kernel/sdk/__init__.py` | Add `ReadPolicy` to `__all__`; surface 35 → 36. |
| `src/service/runtime_v1.py:56, 110, 127, 189, 2614, 2634, 2656, 2663` | Import swap + 9-site type substitution. Parse/serialize body changes (`_parse_view_spec`, `_view_spec_to_dict`, `_resolve_runtime_view_spec`) are §5.7. |

**What this gap does NOT decide:**

- `fg.views` post-migration semantics + `default` entry handling → §5.4.
- Call-site form of `policy=` → §5.5.
- Old `ViewSpec` removal mechanic (exception type, redirect text, where the now-unused name disappears from) → §5.6.
- Service-runtime ViewSpec parse/serialize rewrite (the body of `_parse_view_spec`/`_view_spec_to_dict`) → §5.7.

## 6. Invariants

Placeholder; locked at scope-freeze after §5.1–§5.10 finalize.

## 7. Implementation Gates

Placeholder; locked at scope-freeze.

## 8. Risks

- **`kernel.application.protocol` ViewSpec coupling (§5.7).** If application protocol DTOs expose ViewSpec, migration crosses the application layer; would force cross-blueprint coordination with `project_application_first_runtime_authority`.
- **`src/service/runtime_v1.py` ViewSpec consumption (§5.7).** Service-layer Dialog Agent may consume ViewSpec; service-side migration may be needed in the same slice.
- **Saved-graph / replay serialization.** If ViewSpec is part of an export-package or saved-graph format, replay compatibility may surface (audit at §5.7).
- **Newly-added `examples/05_sdk_assertion_views.ipynb` churn (`58c07fc`, 2026-05-11).** Notebook was added today with old syntax; rewrite is in the same week as creation. §5.8 must decide whether to keep or retire.
- **`ace2563` disclaimer text contradicts target state.** Three SDK docs files now teach "current status: ViewSpec is legacy projection-policy". Once migration ships, those paragraphs must be replaced wholesale, not amended.

## 9. Open Questions

Tracked in §5; each is locked one at a time per `feedback_iterative_gap_design`.

## 10. Outcome

Placeholder; populated at implementation close-out (status flips `implemented`).
