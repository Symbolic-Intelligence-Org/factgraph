# ReadPolicy Call-Site Migration and ViewSpec Removal from `fg.views`

- **Status:** implemented
- **Created:** 2026-05-11
- **Last Updated:** 2026-05-11 (implemented; Phase 4 verification complete; ready to archive)
- **Parent:** post-rc.1 SDK terminology cleanup; no parent blueprint.
- **Related precedents:**
  - [2026-05-11_frozen-assertion-view-model (archived)](../archive/2026-05-11_frozen-assertion-view-model.md) — established `FrozenAssertionView` and the dual-type `fg.views` registry that this blueprint is now disambiguating.
  - [2026-05-10_assertion-selection-crud-ergonomics (archived)](../archive/2026-05-10_assertion-selection-crud-ergonomics.md) — sibling SDK ergonomic cleanup; same iterative-gap cadence.
  - [2026-05-09_post-l-sdk-ergonomics-redesign (archived)](../archive/2026-05-09_post-l-sdk-ergonomics-redesign.md) — closest public-API-shape precedent.
- **Audit Log:** [2026-05-11_readpolicy-call-site-migration.audit.md](./2026-05-11_readpolicy-call-site-migration.audit.md)
- **Baseline:** `ace2563` (`docs(sdk): clarify view projection policy status`), current `origin/master` HEAD; design branch `v0.1-readpolicy-call-site-migration-2026-05-11` forked here.

> **Implemented.** This blueprint removed `ViewSpec` from the SDK/service view surface, introduced `ReadPolicy` as the call-site read/display policy value object, and narrowed `fg.views` to frozen assertion-id membership. §10 records final outcome and deviations.

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
| §5.8 | **Docs + examples rewrite. — LOCKED** | 5 SDK docs + 1 service doc (renamed to `03_runtime_queries_policy.md`) + `examples/05_sdk_assertion_views.ipynb` rewritten as ~5-commit per-layer batch. `respect_revocations` taught in `01_concepts` + referenced in `02_readwrite`. No doc URL in error messages. **Phase 4 grep gate** enforces release-facing-doc cleanliness with archive/migration exemptions. See §5.8 subsection below. |
| §5.9 | **Test coverage plan. — LOCKED** | T-NEW 6 groups (DTO / `policy=` surface / `fg.views` single-meaning / `view=` redirect guards / service runtime new shape / **absence invariant**). T-SWEEP 4 existing files case-by-case rewrite. 2 new test files + 1 reuse. **CI-b independent grep gate script** `scripts/check_legacy_view_syntax.sh`; release integration deferred to §5.10. See §5.9 subsection below. |
| §5.10 | **Release checklist. — LOCKED** | Target = `0.1.0rc3` (separated from already-tagged-semantic rc.2 which holds frozen-assertion-view). `__all__` 35 → 36 (only `ReadPolicy` added). `scripts/check_legacy_view_syntax.sh` is **manual-only** (Phase 4 verification calls it; `release.sh` unmodified). No `BREAKING CHANGE:` commit footer. See §5.10 subsection below. |

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

### §5.8 LOCKED — Docs + examples rewrite plan; Phase 4 grep gate enforces release-facing cleanliness

**Release-facing principle (locked verbatim):**

> Release-facing docs and examples must present `fg.views` only as frozen assertion membership and `ReadPolicy` only as call-site `policy=...`. They must not preserve `ViewSpec` as a documented compatibility path.

This principle governs all D1–D8 decisions below; it is the acceptance gate for §5.8.

**Inventory (8 files containing `ViewSpec` / `view_spec` / `view=`):**

| Category | File | Decision |
|---|---|---|
| SDK docs | `src/kernel/sdk/docs/00_user_guide.en.md` | Rewrite (D7c commit 3). |
| SDK docs | `src/kernel/sdk/docs/01_concepts.en.md` | Rewrite (D7c commit 1) — **owns** `respect_revocations` primary teaching + `default` anti-misread note. |
| SDK docs | `src/kernel/sdk/docs/02_readwrite_and_ingest.en.md` | Rewrite (D7c commit 2) — references `respect_revocations` from retract section. |
| SDK docs | `src/kernel/sdk/docs/03_rules_and_derivations.en.md` | Rewrite (D7c commit 2) — teaches `policy=` on `run` + `return_display_meta` invariant. |
| SDK docs | `src/kernel/sdk/docs/04_api_surface.en.md` | Rewrite (D7c commit 2) — updates `__all__` table (35 → 36, `ReadPolicy` added). |
| Example | `examples/05_sdk_assertion_views.ipynb` | **D1a**: rewrite to one notebook teaching both frozen views and `ReadPolicy`. |
| Example | `examples/archive/02_rules_and_derivations.ipynb` | **D2a**: not touched (archive semantics). |
| Service docs | `src/service/docs/03_runtime_queries_views.md` | **D3**: rename to `src/service/docs/03_runtime_queries_policy.md` + rewrite (D7c commit 5). |

**D1 — `examples/05_sdk_assertion_views.ipynb`:** rewrite, single notebook, teaches `fg.views.create(name, asrt_ids=...)` (frozen membership) **and** `fg.read.find(policy=ReadPolicy(...))` (read-time policy). Old `view=` patterns removed wholesale.

**D2 — `examples/archive/02_rules_and_derivations.ipynb`:** not modified. Archived directory is a frozen-in-time historical record; touching it breaks archive semantics.

**D3 — Service doc filename:** rename to `src/service/docs/03_runtime_queries_policy.md` (not generic `03_runtime_queries.md`). Rationale (locked): "the doc's focus remains the policy/display behavior of runtime queries, not a generic runtime-queries overview." Rewrite removes the five deleted RPC endpoints; documents wire-level `policy=` payload, `respect_revocations` field, and the absence of `view_name` registry lookup.

**D4 — No doc URL in §5.6 error messages:** error redirects are text-only (e.g., `"view= was renamed to policy=; pass policy=ReadPolicy(...) instead"`). Pre-release means no published doc URL; relative paths are noise in production stack traces.

**D5 — `respect_revocations` docs-prominence:**

- **Primary teaching**: `01_concepts.en.md` — introduces "retract ↔ confidence aggregation" as a conceptual relationship (Phase 3 must add a section explaining: `retract` does not delete history rows; `respect_revocations=True` skips revoked rows during confidence aggregation; `respect_revocations=False` includes them).
- **Application reference**: `02_readwrite_and_ingest.en.md` — retract section cross-references the policy semantic.
- **Forbidden**: hiding `respect_revocations` in an "advanced" / "optional" section. The field is concept-level, not advanced.

**D6 — `default` anti-misread note (per §5.4):**

Two locations:

- `_SDKViewsManager` class docstring in `src/kernel/sdk/store.py` (IDE-visible).
- `01_concepts.en.md` views section (systematic-reader-visible).

Both sites carry the verbatim §5.4 note: "The name `default` is no longer reserved by `fg.views`. If users create a frozen assertion view named `default`, it has no special behavior; it is just another frozen assertion-id selection."

**D7 — Rewrite cadence (5-commit per-layer batch):**

| Commit | Files |
|---|---|
| 1 | `01_concepts.en.md` (concepts layer; owns D5 primary + D6 docs note). |
| 2 | `02_readwrite_and_ingest.en.md` + `03_rules_and_derivations.en.md` + `04_api_surface.en.md` (read/write + rule eval + surface layer). |
| 3 | `00_user_guide.en.md` (top-level guide; cross-references previous commits). |
| 4 | `examples/05_sdk_assertion_views.ipynb` (D1a rewrite). |
| 5 | `src/service/docs/03_runtime_queries_views.md` → `03_runtime_queries_policy.md` (D3 rename + rewrite). |

**D8 — Phase 4 grep gate (release-facing cleanliness):**

Phase 4 verification must include a regex/grep check across release-facing docs and examples that **fails** on any of the following patterns appearing outside the exemption set:

- `ViewSpec` — old class name.
- `view_spec` — old variable / wire-field convention.
- `view=` with a policy/named-view payload (e.g., `view="..."`, `view=ViewSpec(...)`, `view=...preferred...`).
- `fg.views.create(...)` with a `ReadPolicy` or `ViewSpec` payload (post-§5.4 semantic violation — `fg.views` accepts only `asrt_ids=` / `asrts=`).

**Reference command** (implementation freedom on exact pattern; lock is the gate semantic):

```bash
rg "ViewSpec|view_spec|view=.*preferred|fg\.views\.create\(.*ReadPolicy|fg\.views\.create\(.*ViewSpec" \
   src/kernel/sdk/docs src/service/docs examples/05_sdk_assertion_views.ipynb
```

**Exemption set (allowed locations for these patterns):**

- `docs/blueprints/archive/**` — historical design records.
- `examples/archive/**` — archived examples.
- `**/archive/**` — any other archive directory.
- This blueprint itself (`docs/blueprints/active/2026-05-11_readpolicy-call-site-migration.md` + paired audit) and any companion migration-context note that explicitly documents `ViewSpec` as **the removed legacy**, not as a supported syntax.
- Test files at `src/kernel/tests/` and `src/service/tests/` that specifically verify rejection of old syntax (§5.9 scope).

**What this gap does NOT decide:**

- Specific paragraph-level rewrites of each doc file — Phase 3 implementation.
- Test docstring rewrites → §5.9.
- Whether commit messages contain `BREAKING CHANGE:` markers → §5.10 release checklist.

### §5.9 LOCKED — Test coverage plan; independent grep gate script; absence invariant

**Absence invariant (locked verbatim):**

> Tests must assert absence of `ViewSpec` from release-facing SDK imports and examples, not only runtime behavior.

This invariant elevates the cleanup from "behavior still works under new names" to "old names are gone from importable surface and release-facing materials". It surfaces in three places:

- T-NEW-6 below: pytest-level import-error assertions.
- The CI-b grep gate script: filesystem-level scan over docs/examples.
- §5.8 D8 grep gate (already locked): same content, packaged as the §5.8 acceptance gate.

**Source-grounded existing test inventory** (HEAD `ace2563`):

| File | `view=` / `ViewSpec` / `fg.views.` occurrences | Disposition |
|---|---|---|
| `src/kernel/tests/test_sdk_frozen_view_read_runtime_boundaries.py` | 12 | Rewrite (T-SWEEP). |
| `src/kernel/tests/test_walker_invariants.py` | 7 | Case-by-case sweep (T-SWEEP). |
| `src/kernel/tests/test_sdk_frozen_assertion_view.py` | 5 | Keep frozen-view tests; remove ViewSpec dispatch; extend for T-NEW-3. |
| `src/domains/ecss/tests/test_phase3_contracts_v1.py` | 3 | Case-by-case sweep (T-SWEEP). |
| `src/service/tests/*` | **0** | No existing service test exercises the 5 removed RPC endpoints; T-NEW-5 adds new coverage. |

**T-NEW — six test groups (all in scope):**

| Group | Coverage | New file or extend? |
|---|---|---|
| **T-NEW-1** | `ReadPolicy` DTO contract: 3 fields × validation paths; default construction equals `(respect_revocations=True, confidence_strategy="max", prefer_source=None)`; `__post_init__` error prefix is `ReadPolicy.<field>`; frozen-dataclass behavior (setattr rejection, hashable, equality). | New `test_sdk_read_policy.py`. |
| **T-NEW-2** | `policy=` P1 acceptance + rejection: `ReadPolicy` accepted; `None` accepted (mirroring current `view=None`); `dict` / `str` / `FrozenAssertionView` / other types rejected; covers both `find` and `run`; `evaluate(policy=...)` always raises. | New `test_sdk_read_policy.py`. |
| **T-NEW-3** | `fg.views` post-migration single-meaning: empty `_views` initial state; `get("default")` / `delete("default")` raise missing-view; `create("default", asrt_ids=[...])` allowed; `view_spec=` parameter rejected; return types narrowed to `FrozenAssertionView`; zero or two payloads on `create` both raise. | Extend `test_sdk_frozen_assertion_view.py`. |
| **T-NEW-4** | `view=` removal redirect guards (§5.6): R3 `find(view=anything)` raises including `view=None`; R4 `run(view=anything)` raises via tombstone sentinel including `view=None`; R5 `evaluate(view=...)` raises via combined guard; `run(rule)` without view/policy succeeds (tombstone does not affect default call). | New `test_sdk_read_policy.py`. |
| **T-NEW-5** | Service runtime new shape + removal verification: `query_view_facts` accepts inline `dto["policy"]` and `respect_revocations` field; `dto["policy"]` absent or `null` → no display_facts; 5 deleted endpoints dispatch returns "method not registered" (or service-impl-equivalent); `_parse_read_policy` rejects `{"active": true}` wire input (field rename); `_read_policy_to_dict` emits `respect_revocations` (not `active`). | New `test_runtime_query_policy.py`. |
| **T-NEW-6** | **Absence invariant** (per locked verbatim above): `from kernel.sdk import ViewSpec` raises `ImportError`; `from kernel.core.store.types import ViewSpec` raises `ImportError`. These are runtime import-level static assertions complementing the CI-b grep gate. | New `test_sdk_read_policy.py`. |

**T-SWEEP — existing test file rewrite (case-by-case during Phase 1 test scaffolding):**

| File | Sweep approach |
|---|---|
| `test_sdk_frozen_view_read_runtime_boundaries.py` | Boundary semantic still exists (`fg.views` frozen vs `policy=` call-site); rewrite each test to its new equivalent. Old "ViewSpec passed at `view=`" → new "ReadPolicy passed at `policy=`"; old "FrozenAssertionView rejected at `view=`" → new "FrozenAssertionView rejected at `policy=`". |
| `test_walker_invariants.py` | Case-by-case: if a test specifically exercises `view=` semantics, rewrite to `policy=`; if `view=` is incidental scaffolding, remove the kwarg. Preserve walker-invariant assertions. |
| `test_sdk_frozen_assertion_view.py` | Keep FrozenAssertionView-only tests intact; remove tests asserting `ViewSpec` dispatch in `_build_view_entry`; add T-NEW-3 tests under same file. |
| `test_phase3_contracts_v1.py` | Domain contract sweep: if contract relies on `fg.views.<view spec>` shape, rewrite to new shape (`policy=` at the consuming call site, not at the contract definition); if contract no longer applicable post-migration, delete with audit note. |

**T-FILE — test file organization:**

| Action | File | Owns |
|---|---|---|
| **New** | `src/kernel/tests/test_sdk_read_policy.py` | T-NEW-1, T-NEW-2, T-NEW-4, T-NEW-6. |
| **New** | `src/service/tests/test_runtime_query_policy.py` | T-NEW-5. |
| **Extend** | `src/kernel/tests/test_sdk_frozen_assertion_view.py` | T-NEW-3 (lives with FrozenAssertionView theme). |

**T-CI — independent grep gate script (Q4 LOCKED as CI-b):**

| Aspect | Locked decision |
|---|---|
| Location | **New file** `scripts/check_legacy_view_syntax.sh` — independent script. |
| Content | Implements the §5.8 D8 grep contract: fail on `ViewSpec`, `view_spec`, `view=<policy/named-view-payload>`, or `fg.views.create(...)` with `ReadPolicy`/`ViewSpec` payload, scanning release-facing locations; honor §5.8 exemption set (archive/**, this blueprint, test files asserting rejection). |
| Release integration | **Deferred to §5.10**. §5.9 does NOT modify `scripts/release.sh`. |
| Rationale (locked verbatim) | "The grep gate targets legacy SDK docs / examples / service docs syntax — it is repo hygiene, not necessarily a release-script main-path step. Keep `release.sh` stable; let the independent script be reusable in Phase 4, release checklist, and CI; allowlist tuning should not require editing the release script." |

**Why CI-b (not CI-a integrated into `release.sh`):**

- `scripts/release.sh` should remain stable; quickly-changing semantic grep contracts do not belong in its main path (per `feedback_release_workflow_traps`).
- Independent script is reusable: Phase 4 manual verification, release checklist (§5.10), CI workflow, ad-hoc author review.
- Future allowlist adjustments (e.g., adding a new archive subdirectory) should not entail editing the release script.

**What this gap does NOT decide:**

- Whether `scripts/check_legacy_view_syntax.sh` is invoked from `scripts/release.sh` or only manually → §5.10 release-checklist integration decision.
- Whether T-NEW-6 absence-invariant tests get a dedicated test file or live within `test_sdk_read_policy.py` → implementation freedom; current default groups them with `test_sdk_read_policy.py`.
- Per-test assertion text and fixture shape → Phase 1 test-scaffolding implementation.
- T-SWEEP per-test delete-vs-rewrite individual decisions → Phase 1 implementation.

### §5.10 LOCKED — Release target rc.3; manual grep gate; no BREAKING CHANGE footer

**Target version (locked verbatim):**

> Next release target is `0.1.0rc3`. This migration is kept out of the already-published `0.1.0rc2` meaning so release notes can describe it as a separate API cleanup.

**RC-line separation rationale:**

- `rc.2` (master commit `e46bc08`) carries the **frozen-assertion-view model** shipment (closed by `004d074` archive). Its release-note semantic is already established.
- This migration is a **public-API cleanup of a different concept** (`ViewSpec` → `ReadPolicy`, `view=` → `policy=`, service runtime wire shape). Bundling it into rc.2 would overload that RC's release-note narrative.
- An extra `chore(release): bump version to 0.1.0rc3` commit at the start of Phase 2 is the minimum cost for clean release-note separation.
- Pre-release per §0.7 means rc.3 needs no SemVer-compat negotiation; clean separation is the only motivation.

**`kernel.sdk.__all__` diff (Phase 4 verification gate):**

| Aspect | Locked contract |
|---|---|
| Surface count | **35 → 36** (rc.2 baseline 35 → rc.3 target 36). |
| Net change | Exactly one entry added: `"ReadPolicy"`. |
| Net removed | **Zero.** No public name leaves `__all__` (`ViewSpec` was never in `__all__`; cf. `project_post_l_redesign_published`). |
| Verification command | `git diff <rc.2-base>..HEAD -- src/kernel/sdk/__init__.py` must show one-line addition only inside `__all__`; no other public-name churn. |
| Allowlist sync (per `feedback_release_workflow_traps` trap 1) | If `scripts/release.sh` consults a `kernel.sdk.__all__` allowlist file, that file is updated to include `ReadPolicy` before Phase 4. |

**Grep gate integration (C-ii LOCKED — manual-only):**

`scripts/check_legacy_view_syntax.sh` (per §5.9 LOCKED) is invoked **manually** at Phase 4 verification. `scripts/release.sh` is **not modified** by this blueprint. Phase 4 acceptance gate explicitly requires the grep gate to pass (`exit 0`) against the implementation HEAD.

Rejected C-i (integration into `release.sh`) per the §5.9 CI-b rationale: the grep gate targets quickly-changing semantic-doc hygiene and does not belong in the stable release main path. Rejected C-iii (GitHub Actions workflow) as over-engineering for pre-release without active CI on this repo.

**Commit-message convention (D1 LOCKED — no BREAKING CHANGE footer):**

Migration commits use the existing factpy convention (`feat(scope):`, `fix(scope):`, `docs(scope):`, `chore(release):`). **No `BREAKING CHANGE:` footer** is added. Rationale:

- `git log` shows no historical use of `BREAKING CHANGE:` footers in this repo; introducing a new commit-message convention is a cross-blueprint decision, out of scope here.
- All Phase 2 commits land before any rc.3 tag; SemVer major-version is not affected.
- Pre-release per §0.7 makes Conventional-Commits BREAKING-CHANGE signaling redundant.

**Release-trap verification (per `feedback_release_workflow_traps` — Phase 4 acceptance):**

| Trap (from memory) | Applicability | Phase 4 verification action |
|---|---|---|
| Allowlist sync after deletions | **Applies** — `ViewSpec` class removal + 5 service RPC endpoints removal. | Dry-run `scripts/release.sh --dry-run`; confirm allowlist files do not reference removed symbols (`ViewSpec`, `_resolve_runtime_view_spec`, `create_runtime_view`, `update_runtime_view`, `delete_runtime_view`, `get_runtime_view`, `list_runtime_views`). |
| Test-projection imports of excluded modules | **Applies** — service test-projection must not import removed dispatch entries. | Confirm any test-projection allowlist excludes references to the removed service symbols above. |
| Deny-pattern grep on private path refs | **Applies (defensive check)** — verify `ReadPolicy` is not accidentally matched by a deny-pattern that targeted `View*` or similar prefix. | Dry-run release with implementation tree; observe deny-pattern grep stage exits clean. |
| Same-day re-tag needs tag + milestone deletion | Not applicable — rc.3 is a fresh tag (not a re-tag). | n/a |
| typing-extensions corruption | Not applicable — no typing-extensions operations. | n/a |
| EN README projection | Not applicable — README not touched by this migration. | n/a |

**Implementation cross-references (Phase 2 + Phase 4):**

| Action | Location |
|---|---|
| `chore(release): bump version to 0.1.0rc3` commit | At start of Phase 2 implementation (after scope-freeze, before any code-change commit). |
| Grep gate invocation | Phase 4 verification step; `bash scripts/check_legacy_view_syntax.sh` must exit 0. |
| `__all__` diff verification | Phase 4 `git diff` step against rc.2 base. |
| Release-trap dry-run | Phase 4 `scripts/release.sh --dry-run` before any real tag. |

**What this gap does NOT decide:**

- rc.3 tag timestamp / GitHub Release page creation timing → release-time editorial decision (per `project_v0_1_0_rc1_published`-style deferral).
- rc.3 release-note copy → release-time editorial work.
- Whether to publish to PyPI at rc.3 or continue holding (per rc.1 precedent) → release-time decision.
- Order of Phase 1-4 commits inside the impl branch → Phase 2 implementation plan (§8 placeholder).

## 6. Invariants

Eight groups, derived from §5.1–§5.10 LOCKED. Every invariant is git-diff-checkable, grep-checkable, or test-checkable.

### 6.1 ReadPolicy DTO form invariants (from §5.1, §5.2, §5.3)

- **I1.1** `ReadPolicy` is the sole post-migration name for the read-time resolution/display policy DTO.
- **I1.2** `ReadPolicy` is defined as a frozen dataclass at `src/kernel/core/store/types.py`, **in-place** at the location previously occupied by `ViewSpec`. No new module is created for this DTO.
- **I1.3** `ReadPolicy` carries exactly 3 fields: `respect_revocations: bool = True`, `confidence_strategy: ConfidenceStrategy = "max"`, `prefer_source: str | None = None`. No additional fields ship in this blueprint; future-field expansion requires a separate scoped blueprint or a §5 amendment.
- **I1.4** `ReadPolicy.__post_init__` mirrors the (pre-migration) `ViewSpec.__post_init__` validation with error-message prefixes renamed to `ReadPolicy.<field>`. Type contracts: `respect_revocations` must be `bool`; `confidence_strategy` must be in `{"max","mean","median","prefer_source"}`; `prefer_source` must be `None` or non-empty `str`.
- **I1.5** `ConfidenceStrategy` type alias stays at `src/kernel/core/store/types.py:14`; not moved, not duplicated, **not** added to `kernel.sdk.__all__`.

### 6.2 Semantic boundary invariants (from §5.1 + §5.3 verbatim clauses)

- **I2.1** *(verbatim, §5.1)*: `ReadPolicy` names the read-time resolution/display policy applied after facts are read, **not graph membership**. It replaces the old `ViewSpec` name for this policy surface; `view` remains reserved for assertion-membership views.
- **I2.2** *(verbatim, §5.3)*: `ReadPolicy` is a core value object **re-exported by the SDK**, not an SDK-only facade type. Core projector and service runtime may consume it directly; user-facing examples should import it from `kernel.sdk`.
- **I2.3** The word `view` (kwarg / namespace / DTO field) is exclusively reserved for assertion-membership semantics in the post-migration surface.

### 6.3 `fg.views` single-meaning invariants (from §5.4)

- **I3.1** `fg.views` carries only `FrozenAssertionView` entries. `get` / `create` / `update` return `FrozenAssertionView`; `list()` returns `dict[str, FrozenAssertionView]`. No union return types.
- **I3.2** `_SDKViewsManager._views` initial state is `{}`. No built-in entries.
- **I3.3** *(verbatim, §5.4)*: The name `"default"` is **no longer reserved** by `fg.views`. If users create a frozen assertion view named `"default"`, it has no special behavior; it is just another frozen assertion-id selection.
- **I3.4** `create(name, ...)` / `update(name, ...)` accept exactly one payload from `{asrt_ids=Iterable[str], asrts=Iterable[Any]}`; **no `view_spec=` parameter exists**. Zero or two payloads raise.
- **I3.5** `delete(name)` carries no `"default"` special-case; missing-name raises a generic missing-view error.

### 6.4 `policy=` call-site value-only invariants (from §5.5)

- **I4.1** `policy=` is the only accepted read/display policy kwarg on `find(...)` and `run(...)`: `policy: ReadPolicy | None = None`. Any `view=` keyword that remains in the physical signature exists only as a tombstone redirect and is never accepted.
- **I4.2** `dict`, `str`, `FrozenAssertionView`, and all other types **raise** on `policy=`. No named-string policy registry exists anywhere in the post-migration SDK or service surface (falsifier baseline against §0.3 + §0.5).
- **I4.3** `policy=None` semantic = "no policy applied". `find(policy=None)` returns rows without `row.confidence`; `run(policy=None)` without `return_display_meta` is normal eval.
- **I4.4** *(verbatim, §5.5)*: `fg.run(rule, return_display_meta=True, policy=None)` is **invalid** because display metadata requires a `ReadPolicy`. Callers must pass `policy=ReadPolicy(...)` when requesting display metadata. The implication `return_display_meta=True ⇒ policy is not None` is the locked semantic.
- **I4.5** `evaluate(...)` rejects any `policy=` kwarg via the §5.6 R5 combined check.

### 6.5 Old-API removal redirect invariants (from §5.6)

- **I5.1** `ViewSpec` class is **not importable** from any kernel module post-migration. Both `from kernel.sdk import ViewSpec` and `from kernel.core.store.types import ViewSpec` raise Python's standard `ImportError`.
- **I5.2 — R3** `find(view=<anything>)` raises a redirect-bearing `SDKStoreError` via the `if "view" in filter_kwargs: raise` early guard. The guard fires before any entity-field filter validation so `view` never enters the filter dispatch.
- **I5.3 — R4** *(verbatim, §5.6)*: `fg.run(..., view=...)` receives an **explicit tombstone guard**, not a bare Python `TypeError`. The guard must reject even `view=None` when supplied explicitly, and point callers to `policy=ReadPolicy(...)`. Implementation must distinguish omitted `view` from explicitly supplied `view=None`; a sentinel is the expected implementation shape, but its name and scope are implementation details.
- **I5.4 — R5** `evaluate(...)` combined guard: `if "view" in kwargs or "policy" in kwargs: raise`. Single raise, combined message.
- **I5.5** All R1–R5 error texts are locked at **semantic level only**; literal strings are implementation freedom. The `run(view=None)` tombstone test (per I5.3) is the discriminating gate — any implementation that silently accepts `view=None` violates I5.3.

### 6.6 Service runtime symmetry invariants (from §5.7)

- **I6.1** *(verbatim, §5.7)*: Service runtime must **not** keep a named policy registry after SDK removes one. A service-level policy registry would recreate the same ambiguity that this blueprint removes from `fg.views`. `RuntimeSession.views` field is removed entirely.
- **I6.2** The 5 wire-level RPC endpoints (`create_runtime_view`, `update_runtime_view`, `delete_runtime_view`, `get_runtime_view`, `list_runtime_views`) are **removed entirely**. No equivalent endpoints replace them.
- **I6.3** `_resolve_runtime_view_spec` function is removed entirely. No name-lookup dispatch survives; `query_view_facts` accepts inline `dto["policy"]` only.
- **I6.4** Wire-level DTO key for the policy payload is `policy` (not `view`). `view_name` key is removed entirely. No name-lookup fallback at the wire layer.
- **I6.5** Wire-level DTO field inside the policy object is `respect_revocations` (not `active`). `_parse_read_policy` rejects `{"active": ...}` input; `_read_policy_to_dict` emits `respect_revocations`.
- **I6.6** Sessions start with no policy registry whatsoever; `"default"` is not initialized at the service layer.

### 6.7 Concept-cleanliness invariants (from §5.8 + §5.9)

- **I7.1** *(verbatim, §5.8)*: Release-facing docs and examples must present `fg.views` only as frozen assertion membership and `ReadPolicy` only as call-site `policy=...`. They must **not** preserve `ViewSpec` as a documented compatibility path.
- **I7.2** Phase 4 grep gate (§5.8 D8 + §5.9 CI-b) fails on `ViewSpec`, `view_spec`, `view=<policy/named-view payload>`, or `fg.views.create(...)` with `ReadPolicy`/`ViewSpec` payload appearing in release-facing locations. **Forbidden matches are old syntax presented as supported usage.** Explicit rejection / migration notes may mention old syntax only when the same sentence or block marks it unsupported and points to `policy=ReadPolicy(...)`. Exemption set: `archive/**`, this blueprint + paired audit, test files asserting rejection.
- **I7.3** *(verbatim, §5.9)*: Tests must assert **absence of `ViewSpec`** from release-facing SDK imports and examples, **not only runtime behavior**. T-NEW-6 pytest tests assert `ImportError` on both `from kernel.sdk import ViewSpec` and `from kernel.core.store.types import ViewSpec`.
- **I7.4** `respect_revocations` is documented as a **first-class** field: primary teaching in `01_concepts.en.md` (retract ↔ confidence relationship) + application reference in `02_readwrite_and_ingest.en.md` retract section. **Forbidden** from "advanced" / "optional" sections.

### 6.8 Release identification invariants (from §5.10)

- **I8.1** *(verbatim, §5.10)*: Next release target is `0.1.0rc3`. This migration is kept out of the already-published `0.1.0rc2` meaning so release notes can describe it as a separate API cleanup.
- **I8.2** `kernel.sdk.__all__` net change is exactly **35 → 36**: one entry added (`"ReadPolicy"`); zero removed.
- **I8.3** No `BREAKING CHANGE:` footer in commit messages (repo has no historical use; cross-blueprint convention introduction is out of scope here).

## 7. Implementation Gates

Five phase blocks (Phase 0 = pre-implementation, Phase 1–4 = execution). Each gate carries a concrete verification command, file artifact, or test assertion.

### Phase 0 — Pre-implementation (scope-freeze)

- **G0.1** All 10 §5 gaps LOCKED. ✅ (confirmed by scope-freeze commit).
- **G0.2** §6 invariants finalized in blueprint body. ✅ (this section).
- **G0.3** Paired impl branch `v0.1-readpolicy-call-site-migration-impl-2026-05-11` created at design HEAD per `feedback_design_impl_branch_isolation`. Verification: `git branch --list v0.1-readpolicy-call-site-migration-impl-2026-05-11` returns the branch.
- **G0.4** Status flipped `draft → scoped` in blueprint header. Verification: `grep "^- \*\*Status:\*\* scoped" docs/blueprints/active/2026-05-11_readpolicy-call-site-migration.md`.

### Phase 1 — Test scaffolding (red baseline)

- **G1.1** New `src/kernel/tests/test_sdk_read_policy.py` contains T-NEW-1 + T-NEW-2 + T-NEW-4 + T-NEW-6. Verification: file exists; pytest collects test functions covering all 4 groups; **explicit `run(view=None)` tombstone test** present (I5.3 discriminating gate).
- **G1.2** New `src/service/tests/test_runtime_query_policy.py` contains T-NEW-5. Verification: file exists; tests cover inline `dto["policy"]`, 5 removed endpoints raising "method not registered", wire-field `respect_revocations` rename.
- **G1.3** Existing `src/kernel/tests/test_sdk_frozen_assertion_view.py` extended with T-NEW-3 (single-meaning + default-not-reserved).
- **G1.4** T-SWEEP triage completed for 4 existing test files; per-test delete/rewrite decisions recorded in audit before Phase 2 starts. Verification: audit row "T-SWEEP triage complete" + per-file commit on impl branch.
- **G1.5** Red baseline confirmed:
  ```bash
  python -m pytest \
    src/kernel/tests/test_sdk_read_policy.py \
    src/service/tests/test_runtime_query_policy.py \
    src/kernel/tests/test_sdk_frozen_assertion_view.py \
    -x --tb=short
  ```
  shows the expected red baseline (`ReadPolicy` undefined, service registry still present). If Phase 1 includes T-SWEEP rewrites of any of the 4 existing test files prior to Phase 2, those files are added to the focused red/green suite.

### Phase 2 — Implementation (code changes)

- **G2.0** `chore(release): bump version to 0.1.0rc3` is the **first commit** on the impl branch in Phase 2 (per I8.1). Verification:
  ```bash
  git log --reverse --oneline <scope-freeze-commit>..HEAD | head -1
  ```
  must show `chore(release): bump version to 0.1.0rc3`.

- **G2.1** Core layer changes:
  - `src/kernel/core/store/types.py`: `ViewSpec` class replaced with `ReadPolicy` class (per I1.2–I1.4 + I5.1).
  - `src/kernel/core/view/projector.py`: import swap; signature `policy: ReadPolicy`; isinstance check swap; field access `.active` → `.respect_revocations`.
  - Verification: `python -c "from kernel.sdk import ReadPolicy; ReadPolicy()"` succeeds; `python -c "from kernel.core.store.types import ViewSpec"` raises `ImportError` (per I5.1).

- **G2.2** SDK layer changes (`src/kernel/sdk/store.py` + `src/kernel/sdk/__init__.py`):
  - All §5.3 + §5.4 + §5.5 + §5.6 cross-refs implemented (see each LOCKED subsection).
  - Sentinel introduced for R4 tombstone (per I5.3; name + scope is implementation freedom).
  - `kernel.sdk.__all__` 35 → 36 with `"ReadPolicy"` added (per I8.2).
  - Verification: T-NEW-1 / T-NEW-2 / T-NEW-3 / T-NEW-4 / T-NEW-6 all green.

- **G2.3** Service layer changes (`src/service/runtime_v1.py`):
  - All §5.7 S2 deep-migration cross-refs implemented.
  - `_parse_read_policy` + `_read_policy_to_dict` renamed with wire-field rename (per I6.5).
  - 5 RPC endpoints + `RuntimeSession.views` + `_resolve_runtime_view_spec` removed (per I6.1–I6.6).
  - Verification: T-NEW-5 green.

- **G2.4** Full kernel + service + ECSS test suites green: `python -m pytest src/kernel/tests src/service/tests src/domains/ecss/tests` (pre-existing Problog cold-import circularity acceptable per primary-anchor precedent).

### Phase 3 — Documentation + examples rewrite (§5.8 D7c 5-commit batch)

- **G3.1** Commit 1: `01_concepts.en.md` rewrites views chapter; primary teaching of `respect_revocations` (per I7.4); §5.4 anti-misread note (per I3.3).
- **G3.2** Commit 2: `02_readwrite_and_ingest.en.md` + `03_rules_and_derivations.en.md` + `04_api_surface.en.md` rewritten (`__all__` table 35 → 36 per I8.2; `return_display_meta` invariant per I4.4).
- **G3.3** Commit 3: `00_user_guide.en.md` top-level walkthrough updated.
- **G3.4** Commit 4: `examples/05_sdk_assertion_views.ipynb` integral rewrite (D1a).
- **G3.5** Commit 5: `src/service/docs/03_runtime_queries_views.md` renamed to `src/service/docs/03_runtime_queries_policy.md` (D3) + rewrite. **Stale-link gate** (Phase 4 enforcement):
  ```bash
  rg "03_runtime_queries_views\.md|runtime_queries_views" src docs examples
  ```
  must return zero matches outside `archive/**` and historical-note paths.
- **G3.6** `_SDKViewsManager` class docstring carries §5.4 anti-misread note (per I3.3 + I7).

### Phase 4 — Verification + close-out

- **G4.1** `bash scripts/check_legacy_view_syntax.sh` exits 0 against impl HEAD (per I7.2). Script honors §5.8 exemption set (`archive/**`, this blueprint + paired audit, T-NEW-6 tests). Forbidden-match definition: old syntax presented as **supported** usage (per I7.2 sentence-or-block clause).
- **G4.2** SDK `__all__` diff:
  ```bash
  git diff <scope-freeze-commit>..HEAD -- src/kernel/sdk/__init__.py
  ```
  shows exactly one-line addition `"ReadPolicy",` inside `__all__`; no other public-name churn (per I8.2). `<scope-freeze-commit>` is the impl-branch base, not the `v0.1.0-rc.2` tag (rc.2 may carry unrelated history).
- **G4.3** Release dry-run:
  ```bash
  ./scripts/release.sh v0.1.0-rc.3 \
    --source-ref v0.1-readpolicy-call-site-migration-impl-2026-05-11 \
    --dry-run \
    --yes
  ```
  passes:
  - Allowlist sync: no references to removed symbols (`ViewSpec`, `_resolve_runtime_view_spec`, 5 removed RPC endpoint names).
  - Test-projection imports: no references to removed dispatch entries.
  - Deny-pattern grep: `ReadPolicy` not erroneously matched.
- **G4.4** Absence-invariant gates triple-checked:
  - T-NEW-6 pytest tests pass (I5.1 + I7.3).
  - `bash scripts/check_legacy_view_syntax.sh` exit 0 (I7.2).
  - Stale-link gate from G3.5 exit 0.
- **G4.5** Full test suite green: `python -m pytest src/kernel/tests src/service/tests src/domains/ecss/tests -x` (carrying pre-existing Problog cold-import circularity per primary-anchor precedent).
- **G4.6** Status flipped `scoped → implemented`. Audit close-out row added.
- **G4.7** Blueprint files moved `docs/blueprints/active/` → `docs/blueprints/archive/` per blueprint convention.

## 8. Risks

- **`kernel.application.protocol` ViewSpec coupling (§5.7).** If application protocol DTOs expose ViewSpec, migration crosses the application layer; would force cross-blueprint coordination with `project_application_first_runtime_authority`.
- **`src/service/runtime_v1.py` ViewSpec consumption (§5.7).** Service-layer Dialog Agent may consume ViewSpec; service-side migration may be needed in the same slice.
- **Saved-graph / replay serialization.** If ViewSpec is part of an export-package or saved-graph format, replay compatibility may surface (audit at §5.7).
- **Newly-added `examples/05_sdk_assertion_views.ipynb` churn (`58c07fc`, 2026-05-11).** Notebook was added today with old syntax; rewrite is in the same week as creation. §5.8 must decide whether to keep or retire.
- **`ace2563` disclaimer text contradicts target state.** Three SDK docs files now teach "current status: ViewSpec is legacy projection-policy". Once migration ships, those paragraphs must be replaced wholesale, not amended.

## 9. Open Questions

Tracked in §5; each is locked one at a time per `feedback_iterative_gap_design`.

## 10. Outcome

### Final landed decision

Ship a hard pre-release cutover from `ViewSpec`/`view=` policy usage to
`ReadPolicy`/`policy=...`, while keeping `fg.views` exclusively for named
frozen assertion-id membership.

### Final landed behavior

- `ReadPolicy` replaces `ViewSpec` as the read-time display/confidence policy
  DTO. It is defined in `src/kernel/core/store/types.py`, re-exported from
  `kernel.sdk`, and added as the only new SDK export (`__all__` 35 → 36).
- `ReadPolicy` has exactly three fields:
  `respect_revocations=True`, `confidence_strategy="max"`, and
  `prefer_source=None`. The old `active` field name is removed.
- `fg.read.find(...)` and `fg.run(...)` accept `policy=ReadPolicy(...)` or
  `policy=None`; dict/string/named-policy and `FrozenAssertionView` payloads
  are rejected. `fg.run(..., return_display_meta=True)` requires a non-None
  `ReadPolicy`.
- `ViewSpec` is no longer importable. `find(view=...)`, `run(view=...)`
  (including explicit `view=None`), and `evaluate(..., view=.../policy=...)`
  reject with redirect/unsupported semantics.
- `fg.views` stores only `FrozenAssertionView` entries. It has no built-in
  `default`, does not reserve the name `"default"`, and `create/update` accept
  only `asrt_ids=` or `asrts=`.
- Service runtime mirrors the SDK cutover: no `RuntimeSession.views`, no 5
  runtime view lifecycle endpoints, no `view_name` lookup, and inline
  `dto["policy"]` with `respect_revocations` for `view-facts`.
- SDK docs, service docs, OpenAPI, and
  `examples/05_sdk_assertion_views.ipynb` now teach frozen assertion views and
  `ReadPolicy` as separate concepts. `scripts/check_legacy_view_syntax.sh`
  enforces the release-facing absence gate.

### Deviations from draft

- The initial draft framed `ViewSpec` removal from `fg.views`; the locked
  design expanded that into a full service-runtime deep migration so the HTTP
  surface would not retain a named policy registry after the SDK removed one.
- §5.2 renamed the old `active` field to `respect_revocations` after
  source-grounding showed its only runtime consumer was revocation-aware
  confidence/display aggregation, not policy lifecycle.
- §5.6 chose an explicit `run(..., view=...)` tombstone sentinel rather than
  relying on Python's bare unexpected-keyword `TypeError`, because the old
  `run(view=..., return_display_meta=True)` copy path was common enough to
  deserve a redirect-bearing error.
- G3.5 updated adjacent live docs and OpenAPI in addition to renaming the
  service DTO narrative, because the 5 removed runtime-view routes and the
  `view_name`/`view` wire fields were still referenced there.

### Deferred design questions

- Named policy registry, if users need reusable policy values in the future.
- Additional `ReadPolicy` fields such as `tie_breaker`, `merge_rule`, or
  `confidence_propagation`.
- Dynamic predicate views, `FrozenAssertionView` API changes, or any
  unification of frozen assertion membership with rule/runtime assertion
  universe scoping.
- Full OpenAPI field-level schemas for all runtime DTOs.

### Verification summary

- Critical invariant tests: 11 passed, including `ViewSpec` absence and the
  discriminating `run(view=None)` tombstone gate.
- Focused ReadPolicy/runtime suites: 67 passed in Phase 2; `test_runtime_query_policy`
  remains 18/18 green after close-out.
- Kernel unittest discovery: 1848 tests OK, 1 skipped.
- Release dry-run: `./scripts/release.sh v0.1.0-rc.3 --source-ref
  v0.1-readpolicy-call-site-migration-impl-2026-05-11 --dry-run --yes`
  passed projection and 1630 projected tests, then cleaned local dry-run refs.
- `scripts/check_legacy_view_syntax.sh` passed.
- Stale service-doc link gate for `03_runtime_queries_views.md` /
  `runtime_queries_views` passed across release-facing scopes.
- Service/ECSS standalone discovery still hits the pre-existing
  audit/application circular import when run in isolation; this is the same
  carried-forward environment noise already recorded during G2.4 and does not
  affect the full kernel discovery result.

### Archive notes

Implemented locally on
`v0.1-readpolicy-call-site-migration-impl-2026-05-11`; archive after final
review and commit.
