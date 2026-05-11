# ReadPolicy Call-Site Migration and ViewSpec Removal from `fg.views`

- **Status:** draft
- **Created:** 2026-05-11
- **Last Updated:** 2026-05-11 (§5.7 LOCKED — service runtime S2 deep migration; policy registry removed; wire renames)
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
| §5.4 | **`fg.views` final semantics. — LOCKED** | `default` entry dropped (not built-in, not reserved); `_views` starts `{}`; `create/update` accept only `asrt_ids=` / `asrts=` (no `view_spec=`); return types narrow to `FrozenAssertionView` / `dict[str, FrozenAssertionView]`. See §5.4 subsection below. |
| §5.5 | **`policy=` call-site API. — LOCKED** | `policy: ReadPolicy \| None = None` on `find` / `run`; `policy=None` skips policy (mirrors current `view=None`); `dict` / `str` / `FrozenAssertionView` rejected; `evaluate(policy=...)` rejected; `return_display_meta=True` requires non-`None` policy. See §5.5 subsection below. |
| §5.6 | **Old API removal mechanic. — LOCKED** | `ViewSpec` class deleted; `find` adds `"view" in filter_kwargs` guard; `run` adds **tombstone sentinel** `view: Any = _MISSING` rejecting even `view=None`; `evaluate` uses combined `view`/`policy` rejection. Error texts at semantic level only. See §5.6 subsection below. |
| §5.7 | **Non-SDK ViewSpec reference sweep. — LOCKED** | Service runtime **S2 deep migration**: remove `RuntimeSession.views` + 5 RPC endpoints + `_resolve_runtime_view_spec` + `"default"` + `view_name` lookup; rename `_parse_view_spec` / `_view_spec_to_dict` to `_parse_read_policy` / `_read_policy_to_dict`; wire DTO key `view` → `policy`, wire field `active` → `respect_revocations`. Groups A/B covered by §5.6 / §5.3 / §5.2 cross-refs. See §5.7 subsection below. |
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

### §5.4 LOCKED — `fg.views` narrowed to frozen assertion membership; `default` entry removed

**Registry state and dispatch surface (locked):**

| Aspect | Locked decision |
|---|---|
| `_views` initial value | `{}` (no built-in entry; was `{"default": ViewSpec()}`) |
| `"default"` name reservation | **None.** Users may freely create a frozen view named `"default"`. |
| `create(name, ...)` payload | Accepts only `asrt_ids=Iterable[str]` or `asrts=Iterable[Any]`, mutually exclusive (exactly one). The `view_spec=` parameter is **removed**. |
| `update(name, ...)` payload | Same shape as `create`. |
| `delete(name)` | Drops the entry if present; otherwise raises a generic missing-view error. The previous `default`-special-case branch is removed entirely. |
| `get(name) -> FrozenAssertionView` | Union narrowed; no `ViewSpec` return path. |
| `list() -> dict[str, FrozenAssertionView]` | Union narrowed. |
| `_views: dict[str, FrozenAssertionView]` | Storage type narrowed. |
| `_build_view_entry` | ViewSpec dispatch branch removed; returns `FrozenAssertionView`. |
| `_normalize_view_name` | Unchanged (only does empty-string validation; no reservation logic was ever there). |

**Anti-misread note (locked verbatim):**

> The name "default" is no longer reserved by `fg.views`. If users create a frozen assertion view named "default", it has no special behavior; it is just another frozen assertion-id selection.

This note exists to prevent future doc / test authors from re-introducing a "built-in default" semantic by accident.

**Error-text scope:**

Error messages on missing entries (`get` / `delete` on a non-existent name) are locked at the **semantic** level only — "view not found" — not at the literal string. Implementation may emit `"view not found: <name>"` or any equivalent phrasing; tests pin behavior (missing-key vs present-key), not exact wording.

**User-visible behavior diff under §0.7 hard cut:**

- A fresh `FactGraph` has `fg.views.list() == {}` (was `{"default": <ViewSpec>}`).
- `fg.views.get("default")` raises missing-view (was: returned the baseline `ViewSpec`).
- `fg.views.create("default", asrt_ids=[...])` is **allowed** (was: blocked because `default` already existed).
- `fg.views.delete("default")` raises missing-view when the name does not exist (was: raised `"cannot delete built-in view: default"`).

**Why `default` removal (not "keep as empty FrozenAssertionView" / "reserve the name"):**

- A `FrozenAssertionView(name="default", asrt_ids=frozenset())` is semantically degenerate — an empty bookmark teaches nothing and serves no read path.
- The current `default` entry's only real role is **baseline policy lookup** for `view="default"` / `view=None`. That role is taken over by inline `ReadPolicy()` construction at call sites (per §5.3 + the §5.5 working hypothesis); no registry slot needs to carry it.
- Reserving the name `"default"` without a built-in value preserves a future-language hook with no concrete current use; honors `feedback_narrow_public_api` (do not occupy surface for hypotheticals).

**Service-runtime symmetry (out of scope here):**

`src/service/runtime_v1.py` carries a parallel `views={"default": ViewSpec()}` initialization (line 189), a `delete_runtime_view` `default` guard (line 924), and a fallback at `session.views["default"]` (line 2631). All three are **out of scope for §5.4**; they belong to §5.7 (non-SDK reference sweep) and are decided there.

**What this gap does NOT decide:**

- `view=` → `policy=` kwarg migration on `find` / `run` → §5.5.
- Old `view=` kwarg removal mechanic and error text → §5.6.
- Service-runtime `default` handling — keep symmetry, change semantics, or drop → §5.7.
- Test coverage for the registry narrowing → §5.9.

### §5.5 LOCKED — `policy: ReadPolicy | None` value-only; `return_display_meta` requires non-`None` policy

**Type signature (locked):**

```python
def find(
    self,
    entity_cls: type[Entity],
    *,
    policy: ReadPolicy | None = None,
    limit: int | None = None,
    **filter_kwargs: Any,
): ...

def run(
    self,
    rule_or_query: Any,
    *,
    policy: ReadPolicy | None = None,
    return_display_meta: bool = False,
    row_format: str | None = None,
    registry: RuleRegistry | None = None,
): ...
```

**Accepted payloads on `policy=`:**

- `ReadPolicy` instance → applied as policy.
- `None` → no policy applied (default).
- Anything else → raises `SDKStoreError`.

**Explicitly rejected payload types** (semantic-level lock; literal error text is implementation freedom):

- `dict` — would require duplicate validation of `ReadPolicy.__post_init__`; breaks typed-DTO boundary; produces two error chains. Construct `ReadPolicy(...)` explicitly.
- `str` — would resurrect a named-policy registry, violating §0.3 (no registry) and §0.5 (no `fg.projections` equivalent). This is the strongest rejection: any future amendment that re-introduces `policy="name"` lookup must re-litigate §0.3 + §0.5 as a falsifier baseline.
- `FrozenAssertionView` — cross-namespace error; frozen views live in `fg.views`, policies in `policy=` kwargs. Error message should make the redirect explicit (`fg.views` carries frozen membership; pass `policy=ReadPolicy(...)` here).

**`policy=None` semantic** (mirrors current `view=None`):

- `fg.read.find(User, policy=None)` → returns rows; **does not attach `row.confidence`**.
- `fg.run(rule, policy=None)` (without `return_display_meta`) → normal rule eval; no display metadata.
- `fg.run(rule, policy=None, return_display_meta=True)` → **invalid; raises** (see invariant below).

**`return_display_meta` invariant (locked verbatim):**

> `fg.run(rule, return_display_meta=True, policy=None)` is invalid because display metadata requires a `ReadPolicy`. Callers must pass `policy=ReadPolicy(...)` when requesting display metadata.

Source-ground for this invariant: the existing guard at `src/kernel/sdk/store.py:1506-1507`:

```python
if view_spec is None:
    raise SDKStoreError("return_display_meta requires view to be provided", path="$.run.return_display_meta")
```

Post-migration becomes:

```python
if policy is None:
    raise SDKStoreError("return_display_meta requires policy", path="$.run.return_display_meta")
```

The literal text changes; the semantic invariant — `return_display_meta=True ⇒ policy is not None` — is the lock.

**`evaluate(...)` behavior** (mechanical parallel; no new design):

`evaluate(...)` currently rejects any `view=` kwarg (`src/kernel/sdk/store.py:1565`: "derivation evaluation always uses active projection"). Post-migration mirror: `evaluate(...)` rejects any `policy=` kwarg with semantically equivalent message. No new decision; locked here for §5.6 / §5.9 implementation cross-reference.

**Helper-function shape** (implementation freedom; not locked):

`_resolve_view_spec` at `src/kernel/sdk/store.py:1542-1554` currently dispatches across `ViewSpec` / `FrozenAssertionView` / `str` / `None`. Post-migration the logic collapses to "None passthrough + isinstance check". Whether this remains a `_resolve_policy` helper or is inlined at `find` / `run` call sites is an implementation choice — §5.5 does not lock the call-graph.

**Implementation cross-references (Phase 2):**

| Path | Change |
|---|---|
| `src/kernel/sdk/store.py:565` | `find` signature: `view: ViewSpec \| str \| None` → `policy: ReadPolicy \| None`. |
| `src/kernel/sdk/store.py:577-585` | `_resolve_view_spec` call swapped or inlined; `view_spec=resolved_view` → `policy=resolved_policy` in `_build_entity_confidence_by_ref`. |
| `src/kernel/sdk/store.py:1389` | `run` signature: `view` → `policy`. |
| `src/kernel/sdk/store.py:1428, 1445, 1461, 1483` | All `_run_dispatch_*` and `_run_rule` `view_spec` param → `policy`. |
| `src/kernel/sdk/store.py:1506-1507` | `return_display_meta` guard: rephrase to reference `policy` (semantic invariant locked above; literal string free). |
| `src/kernel/sdk/store.py:1542-1554` | `_resolve_view_spec` simplified or inlined. |
| `src/kernel/sdk/store.py:1565` | `evaluate` rejection: mirror as `policy=` rejection. |

**What this gap does NOT decide:**

- Old `view=` kwarg removal mechanic (raise vs silent ignore) and exact error redirect text → §5.6.
- Old `ViewSpec` import / construction removal → §5.6.
- Service-runtime call-site migration (its parallel `view=` API surface) → §5.7.
- Tests for each rejection path (`dict` / `str` / `FrozenAssertionView`) and the `return_display_meta` + `policy=None` invariant → §5.9.

### §5.6 LOCKED — Old-API removal; explicit redirects on `find` / `run` / `evaluate`; `run` uses tombstone sentinel

**Decision matrix per old path:**

| Path | Mechanic |
|---|---|
| R1 — `ViewSpec` class at `kernel/core/store/types.py:47-59` | **Deleted entirely.** No `__getattr__` shim. `from kernel.core.store.types import ViewSpec` raises Python's standard `ImportError`. |
| R2 — `fg.views.create(name, ViewSpec(...))` / `view_spec=` kwarg | Already removed by §5.4 (param dropped from signature) + R1 (constructor name gone). No additional handling. |
| R3 — `fg.read.find(..., view=...)` | **Explicit guard in `find` body.** `find` keeps its `**filter_kwargs`; guard runs before filter validation: `if "view" in filter_kwargs: raise SDKStoreError(...)`. |
| R4 — `fg.run(..., view=...)` | **Explicit tombstone-sentinel guard.** `run` does not have `**kwargs`; `view` is preserved as a keyword-only parameter with a sentinel default `_MISSING`. Guard rejects **any** explicit pass including `view=None`. |
| R5 — `evaluate(..., view=...)` / `evaluate(..., policy=...)` | **Combined check in evaluate body**: `if "view" in kwargs or "policy" in kwargs: raise SDKStoreError(...)`. evaluate retains `**kwargs`; both names rejected with one combined message. |

**R4 tombstone-sentinel pattern (locked verbatim):**

> `fg.run(..., view=...)` receives an explicit tombstone guard, not a bare Python `TypeError`. The guard must reject even `view=None` when supplied explicitly, and point callers to `policy=ReadPolicy(...)`.

Implementation pattern:

```python
# kernel/sdk/store.py — module-level sentinel
_VIEW_TOMBSTONE = object()

def run(
    self,
    obj: Any,
    *,
    row_format: str | None = None,
    policy: ReadPolicy | None = None,
    view: Any = _VIEW_TOMBSTONE,
    return_display_meta: bool = False,
    registry: RuleRegistry | None = None,
):
    if view is not _VIEW_TOMBSTONE:
        raise SDKStoreError(
            "view= was renamed to policy= for read/display policy; "
            "pass policy=ReadPolicy(...) instead",
            path="$.run.view",
        )
    ...
```

The sentinel name (`_VIEW_TOMBSTONE` here) is **implementation freedom**; the **semantic contract** is locked: `run(view=anything-at-all)` raises, including `run(view=None)`, distinguishing "user explicitly passed `view`" from "user did not pass `view`".

**Why R4 needs a sentinel, not a regular default:**

- A default of `view: Any = None` cannot distinguish `run(rule)` (no `view` passed) from `run(rule, view=None)` (user explicitly passed `view=None`).
- The §5.6 contract requires the explicit-pass case to raise; the no-pass case must succeed silently.
- Sentinel `_MISSING` (any unique module-level object) provides the distinction.

**Why R4 redirect, not Python `TypeError` (rejected alternative R4-a):**

- `run` is a high-frequency surface that users routinely copy from old docs and examples (e.g., `fg.run(rule, view="preferred_names", return_display_meta=True)`).
- Python's bare `TypeError: run() got an unexpected keyword argument 'view'` names the parameter but does not point to `policy=ReadPolicy(...)`.
- R3 (`find`) already commits to explicit redirect; R4 keeps symmetry.

**Error-text scope** (per §5.4 / §5.5 precedent):

All R1–R5 error texts are locked at the **semantic** level only; literal strings are implementation freedom.

| Path | Semantic contract (locked) | Literal (free) |
|---|---|---|
| R1 | "`ViewSpec` is no longer importable; the replacement is `ReadPolicy`." | Python standard `ImportError` is acceptable; the redirect to `ReadPolicy` lives in docs, not in the import-time message. |
| R3 | "`view=` was renamed to `policy=`." | Any phrasing of the rename + suggested replacement. |
| R4 | "`view=` was renamed to `policy=` for read/display policy." | Same. |
| R5 | "`evaluate()` does not accept `view=` or `policy=`; derivation evaluation always uses active projection." | Any phrasing covering the two-rejection semantic in one message. |

**Implementation cross-references (Phase 2):**

| File:line | Change |
|---|---|
| `src/kernel/core/store/types.py:47-59` | **R1**: delete `ViewSpec` class block. |
| `src/kernel/sdk/store.py:561` (`find`) | **R3**: add early-body guard `if "view" in filter_kwargs: raise SDKStoreError(...)`. |
| `src/kernel/sdk/store.py:1384` (`run` signature) | **R4**: declare `view: Any = _VIEW_TOMBSTONE` keyword-only param; module-level `_VIEW_TOMBSTONE = object()`; guard inside `run` body. |
| `src/kernel/sdk/store.py:1565` (`evaluate`) | **R5**: replace single-key `"view"` check with combined `"view" or "policy" in kwargs` rejection. |

**What this gap does NOT decide:**

- Service-runtime mirror removal (`src/service/runtime_v1.py` parallel `view=` surface, 9 sites) → §5.7.
- Service-runtime parse/serialize body rewrite (`_parse_view_spec`, `_view_spec_to_dict`, `_resolve_runtime_view_spec`) → §5.7.
- Test coverage for each R1–R5 redirect path (including `run(view=None)` tombstone behavior) → §5.9.
- Documentation rewrite of any examples currently teaching the old `view=` patterns → §5.8.

### §5.7 LOCKED — Service runtime S2 deep migration; policy registry removed; wire-level renames

**Inventory recap (full non-SDK non-test production-code sweep at HEAD `ace2563`):**

Three groups, 31 lines total:

| Group | Path | Lines | Disposition |
|---|---|---|---|
| **A** | `src/kernel/core/store/types.py` | 4 (48, 55, 57, 59) | Covered by §5.6 R1 (class deletion). |
| **B** | `src/kernel/core/view/projector.py` | 6 (12, 207, 211-212, 216, 234-235) | Covered by §5.3 type-swap + §5.2 field-rename cross-refs. Mechanical. |
| **C** | `src/service/runtime_v1.py` | 21 across 11 logical sites | **LOCKED here as S2 deep migration.** |

`src/kernel/application/protocol/`, `src/kernel/audit/`, and `src/domains/ecss/` (non-test) carry **zero** `ViewSpec` references — confirmed by exhaustive grep.

**S2 deep migration — defensive note (locked verbatim):**

> Service runtime must not keep a named policy registry after SDK removes one. A service-level policy registry would recreate the same ambiguity that this blueprint removes from `fg.views`.

If a future need for named policies at the wire level emerges, it must be a **new product-level feature scoped in its own blueprint**, not a residual of this migration.

**S2 — removed entirely (no replacement):**

| Path:line | Element removed |
|---|---|
| `src/service/runtime_v1.py:110` | `RuntimeSession.views: dict[str, ViewSpec]` field. |
| `src/service/runtime_v1.py:127` | `RuntimeSession` constructor `views=` parameter. |
| `src/service/runtime_v1.py:189` | Default initialization `views={"default": ViewSpec()}`. |
| `src/service/runtime_v1.py:886-899` | `create_runtime_view` RPC endpoint. |
| `src/service/runtime_v1.py:902-915` | `update_runtime_view` RPC endpoint. |
| `src/service/runtime_v1.py:918-933` | `delete_runtime_view` RPC endpoint (including the `"default"` special-case guard). |
| `src/service/runtime_v1.py:935-945` | `get_runtime_view` RPC endpoint. |
| `src/service/runtime_v1.py:947-958` | `list_runtime_views` RPC endpoint. |
| `src/service/runtime_v1.py:2614-2631` | `_resolve_runtime_view_spec(session, dto)` function — entire body removed; name-lookup dispatch and `session.views["default"]` fallback are both gone. |

**S2 — renamed and refactored:**

| Path:line | Change |
|---|---|
| `src/service/runtime_v1.py:56` | Import: `from kernel.core.store.types import ViewSpec` → `from kernel.core.store.types import ReadPolicy`. |
| `src/service/runtime_v1.py:846-872` (`query_view_facts` flow) | Replace `_resolve_runtime_view_spec(session, dto)` call with `_parse_read_policy(dto.get("policy"), path="$.policy")`. Response continues to emit policy summary via `_read_policy_to_dict`. The `view_name` branch and `session.views[...]` fallback paths disappear. Existing display-fact projection call (`project_display_facts(...)`) continues to consume the resulting `ReadPolicy` (per §5.3 mechanical type swap). |
| `src/service/runtime_v1.py:2634-2660` | Function rename `_parse_view_spec` → `_parse_read_policy`. Drop the `isinstance(value, ViewSpec)` passthrough branch (wire input is always JSON dict). Rename incoming JSON field `active` → `respect_revocations` (wire-level rename). Construct `ReadPolicy(...)` instead of `ViewSpec(...)`. |
| `src/service/runtime_v1.py:2663-2668` | Function rename `_view_spec_to_dict` → `_read_policy_to_dict`. Rename emitted JSON key `active` → `respect_revocations`. |

**Wire-level DTO breaking changes (`feedback_narrow_public_api` aside; pre-release per §0.7):**

| Layer | Before | After |
|---|---|---|
| DTO field carrying policy object | `dto["view"]` | `dto["policy"]` |
| DTO field for named-policy lookup | `dto["view_name"]` | **Removed** — name-lookup no longer supported at the wire level. |
| DTO field inside policy object | `"active": bool` | `"respect_revocations": bool` |
| RPC method names | `create_runtime_view`, `update_runtime_view`, `get_runtime_view`, `list_runtime_views`, `delete_runtime_view` | **All five removed.** No replacement; per the defensive note above, no equivalent endpoints are introduced. |

**Why S2 (not S1 shallow rename):**

- **Architectural symmetry**: SDK §5.4 dropped policy registry; service runtime is a thin RPC over SDK semantics; retaining a registry only at the service layer would create a hidden second "registry world" the next ergonomics fix would have to dismantle again.
- **`feedback_narrow_public_api`**: removing 5 RPC endpoints is a public-surface contraction, aligned with narrow-API discipline; no current scope requires named-policy wire ergonomics.
- **§0.7 pre-release**: wire-level breaking changes are cheapest now. Postponing means baking a deprecated registry into RC artifacts.
- **`default` parity with §5.4**: keeping service `"default"` would force a permanent SDK-vs-service ghost where SDK forgot `default` but service remembers it.
- **`view_name` lookup parity with §5.5**: §5.5 P1 rejected `str` named-string on `policy=`; the wire `view_name` is the same mistake under a different transport.

**Implementation cross-references (Phase 2) — Group C summary:**

The 11 logical service sites collapse into:

1. **5 RPC endpoint definitions removed** (create/update/delete/get/list).
2. **1 query-flow refactor** (`query_view_facts`): inline policy parse instead of registry resolve.
3. **2 helper function renames + signature/wire rename** (`_parse_view_spec` → `_parse_read_policy`, `_view_spec_to_dict` → `_read_policy_to_dict`).
4. **1 RuntimeSession field removal** (with constructor + default-init cascade).
5. **1 dead helper removal** (`_resolve_runtime_view_spec`).
6. **1 import swap** (`ViewSpec` → `ReadPolicy`).

**What this gap does NOT decide:**

- Service-runtime tests sweep — including the 5 removed-endpoint tests that must be deleted and the `query_view_facts` policy-inline tests that must be updated → §5.9.
- Wire-level documentation (if any external service contract docs exist beyond `src/service/docs/` directory contents) → §5.8.
- Whether `_parse_read_policy` should be split out into a shared validation utility re-used between `ReadPolicy.__post_init__` and the wire-parser → implementation-detail freedom, not §5.7-locked.

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
