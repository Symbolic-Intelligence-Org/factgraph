# Task Blueprint: Result-fingerprint fold Slice β — EvaluateResult provenance digest + engine-meta sub-object folding

- Status: scoped
- Created: 2026-06-03
- Last Updated: 2026-06-03 (Step 4.6 scope freeze)
- Owner: Claude (blueprint) / Codex (impl) — cross-flip per Slice 4/5 precedent ([`workflow/CADENCE.md`](../../CADENCE.md):268)
- Related Modules:
  - `src/factgraph/application/protocol/evaluate_result.py` (EvaluateResult definition + `result_digest_for(...)` helper)
  - `src/factgraph/sdk/__init__.py` (top-level re-export — add `ResultFingerprint`)
  - `src/factgraph/application/protocol/__init__.py` (protocol re-export — add `ResultFingerprint`)
  - `src/factgraph/sdk/store.py` (EvaluateResult construction site at `_evaluate(...)`)
  - `src/service/runtime_v1.py` (EvaluateResult production construction + JSON serialization — N-1/N-2 pattern from Step 4.3 PF-R1/PF-R2)
  - `tests/application/protocol/test_evaluate_result_dtos.py` (EvaluateResult invariant tests)
  - `tests/application/protocol/test_evaluate_result_digests.py` (digest helper byte-equal tests)
  - `tests/sdk/test_evaluate_result_exports.py` (SDK re-export test)
  - `tests/sdk/test_rule_expr_evaluate.py` (active SDK result digest/config assertions)
  - `tests/test_db_attach_lifecycle.py` (active view snapshot digest assertion)
  - `tests/test_problog_semantics_profile_migration.py` (active result wire-key assertions)
  - `tests/test_sdk_find_partial_identity.py` (SDK `__all__` count/surface guard — `ResultFingerprint` add must be intentional)
- Related Docs:
  - [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.1 + §3.2 + §6 Slice β (parent design)
  - [`docs/quickstart/evaluate_and_evidence.md`](../../../docs/quickstart/evaluate_and_evidence.md) (EvaluateResult field-shape rewrite per Slice α PF-R3 pattern)
  - [`docs/official/kernel/quickstart/evidence.md`](../../../docs/official/kernel/quickstart/evidence.md) (official quickstart envelope/fingerprint wording)
  - [`docs/official/kernel/quickstart/namespace-map.md`](../../../docs/official/kernel/quickstart/namespace-map.md) (rule-set digest wording)
  - [`src/factgraph/sdk/docs/03_rules_and_inferences.en.md`](../../../src/factgraph/sdk/docs/03_rules_and_inferences.en.md) (SDK docs replay anchors)
  - [`src/service/docs/03_runtime_queries_policy.md`](../../../src/service/docs/03_runtime_queries_policy.md) (service JSON wire fields; must stay flat but be explained as wire compatibility)
- Audit Log:
  - [2026-06-03_result-fingerprint-fold-slice-beta.audit.md](./2026-06-03_result-fingerprint-fold-slice-beta.audit.md)

## 1. Problem

Parent design-point §2.4 audit established that `EvaluateResult` carries 7 digest/id fields with **no independent logical consumer** — they are always packed together into metadata snapshots ([`evaluate_result.py:1251`](../../../src/factgraph/application/protocol/evaluate_result.py), [`:1337`](../../../src/factgraph/application/protocol/evaluate_result.py), [`sdk/store.py:2527`](../../../src/factgraph/sdk/store.py)). The shipped fields:

- `expr_digest` / `rule_set_digest` / `view_snapshot_digest` / `config_digest` — 4 provenance digests
- `result_digest` — 1 master digest
- `run_id` — 1 identifier (audit/provenance bundle, not independently consumed)
- `engine_version` / `adapter_version` — 2 engine-version fields, also bundle-style consumption

Slice β folds these 8 fields into 2 sub-objects (no behavior change, only surface organization):

- **ResultFingerprint** (new frozen DTO): 6 fields (the 4 provenance digests + `result_digest` + `run_id`)
- **`engine_meta: Mapping[str, Any]`** (new field on EvaluateResult): `engine_version` + `adapter_version` (extensible Mapping for future engine metadata)

Slice β is the 2nd slice per parent design §6 ordering (α → **β** → γ → ζ → η → ε → δ) — low-risk, cosmetic surface organization, no semantic change. Wrapper classes (`EvaluateResult`) remain. Per parent design §3.1: EvaluateResult user-facing surface 13 direct public fields → 7 direct public fields + 2 sub-objects.

## 2. Goals

- G1 — Add new `ResultFingerprint` frozen DTO with 6 fields (`expr_digest` / `rule_set_digest` / `view_snapshot_digest` / `config_digest` / `result_digest` / `run_id`)
- G2 — Remove `expr_digest` / `rule_set_digest` / `view_snapshot_digest` / `config_digest` / `result_digest` / `run_id` / `engine_version` / `adapter_version` from `EvaluateResult` frozen field set (8 fields total)
- G3 — Add `EvaluateResult.fingerprint: ResultFingerprint` + `EvaluateResult.engine_meta: Mapping[str, Any]` new frozen fields
- G4 — Add 8 deprecated `@property` on `EvaluateResult` for each removed field (emit `DeprecationWarning`; delegate to `self.fingerprint.X` or `self.engine_meta.X`)
- G5 — Existing user code accessing `result.expr_digest` / `.rule_set_digest` / `.view_snapshot_digest` / `.config_digest` / `.result_digest` / `.run_id` / `.engine_version` / `.adapter_version` continues to work (emits `DeprecationWarning`)
- G6 — `result_digest_for(...)` shipped helper at [`evaluate_result.py:565-612`](../../../src/factgraph/application/protocol/evaluate_result.py) **preserves byte-equal output** for equivalent inputs (canonical bytes for `evaluate_result_digest_v1` unchanged)
- G7 — All `EvaluateResult(...)` construction sites updated to drop removed kwargs and pass `fingerprint=` + `engine_meta=`
- G8 — Internal compatibility paths (digest helpers, service serializer, etc.) updated to use direct sub-object access, not deprecated properties
- G9 — Test coverage for deprecated-property emission + sub-object access + byte-equal digest preservation
- G10 — Result construction order remains valid: primitive inputs are used to compute `result_id`, row digests, and `result_digest` before constructing the complete `ResultFingerprint`; no digest helper may depend on deprecated `EvaluateResult` properties
- G11 — `engine_meta` is normalized + validated, not a loose arbitrary Mapping: required keys `engine_version` / `adapter_version` are present with values `str | None` (extras allowed for future metadata)
- G12 — Service runtime production construction and service serializer both updated while preserving INV-6 and flat JSON wire compatibility

## 3. Non-goals

- N1 — Removing `EvaluateResult` itself or any other DTO wrapper (Slice α already keeps wrappers; γ removes Claim/EvidenceRef; EvaluateResult removal is out of scope for the whole parent design)
- N2 — Touching Slice α DTOs (`Claim` / `EvidenceRef`) — those are already in `implemented` archive state
- N3 — Wrapper removal of Claim / EvidenceRef (that is Slice γ)
- N4 — `bindings` shape simplification (Slice ζ)
- N5 — `EvidenceGraph` 3-tier hierarchy (Slice η)
- N6 — `Explanation.repr` walker (Slice ε)
- N7 — query-style `head.id` decoupling (Slice δ)
- N8 — Changing `evaluate_result_digest_v1` canonical byte format — Slice β is field-organization only, not algorithm change
- N9 — Breaking SDK/service wire shape — JSON output of service serializer must keep the same flat digest fields for backward compat (parallel to Slice α §5.7 N-1)

## 4. Current Context

- Current implementation entry:
  - EvaluateResult class: [`src/factgraph/application/protocol/evaluate_result.py:206-289`](../../../src/factgraph/application/protocol/evaluate_result.py) — 13 user-facing + 4 internal fields
  - EvaluateResult `__post_init__`: [`:241-279`](../../../src/factgraph/application/protocol/evaluate_result.py) — currently validates 7 digest/id fields + 2 engine version fields directly
  - `result_digest_for(...)` helper: [`:565-612`](../../../src/factgraph/application/protocol/evaluate_result.py) — public symbol, takes 7 digest/id + 2 engine version inputs as kwargs, produces `evaluate_result_digest_v1` canonical bytes
  - SDK store construction site: [`src/factgraph/sdk/store.py:2697-2725`](../../../src/factgraph/sdk/store.py) area — Slice α already touched `_row_digest_for(...)` here
  - Service production construction site: [`src/service/runtime_v1.py:2328-2395`](../../../src/service/runtime_v1.py) `_evaluate_result_from_candidates(...)` — required PF-R1 scope from Step 4.3 preflight
  - Service serializer: [`src/service/runtime_v1.py:2445-2462`](../../../src/service/runtime_v1.py) `_evaluate_result_to_dict(...)` — required N-2 analog to Slice α service serializer preservation
- Current known constraints:
  - D19 digest source-of-truth ([`workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md`](../../design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md)) — digest **algorithm** unchanged; field **location** changes only (parent design §7.6 partial-supersede)
  - Q-PR1 sacred 5-path 0-diff vs `4c472b50` — must preserve through all Slice β commits (`evaluate_result.py` is **not** sacred path; safe to edit; ledger / write_protocol / pyreason adapter etc. untouched)
  - INV-6 (application-first runtime authority) — core protocol edits inside `factgraph.application.protocol`; service runtime construction is a legacy production construction path that must follow the protocol DTO shape, not an authority shift; service serializer is downstream projection preserving flat wire JSON
  - Slice α impl branch state: `v0.2.0-impl-eval-result-flatten-2026-06-03 @ 64651454` archived; Slice β builds on top — fork base is `64651454`
- Current related historical blueprints / decisions:
  - Slice α archived: [`workflow/blueprints/archive/2026-06-03_eval-result-flatten-slice-alpha.md`](../archive/2026-06-03_eval-result-flatten-slice-alpha.md) — establishes deprecated-property + internal-compatibility-inventory + service-serializer N-1 pattern that Slice β reuses
  - D17 (parent design §7.6): partial supersede continues — β does not touch D17's Claim/EvidenceRef territory (that was α + future γ)
  - D19: digest algorithm preservation contract holds — β preserves `evaluate_result_digest_v1` canonical bytes

## 5. Proposed Shape

### 5.1 ResultFingerprint — new frozen DTO

```python
@dataclass(frozen=True)
class ResultFingerprint:
    expr_digest: str
    rule_set_digest: str
    view_snapshot_digest: str
    config_digest: str | None
    result_digest: str
    run_id: str

    def __post_init__(self) -> None:
        _require_sha256_token(self.expr_digest, field_name="ResultFingerprint.expr_digest")
        _require_sha256_token(self.rule_set_digest, field_name="ResultFingerprint.rule_set_digest")
        _require_sha256_token(self.view_snapshot_digest, field_name="ResultFingerprint.view_snapshot_digest")
        if self.config_digest is not None:
            _require_sha256_token(self.config_digest, field_name="ResultFingerprint.config_digest")
        _require_sha256_token(self.result_digest, field_name="ResultFingerprint.result_digest")
        _require_token_prefix(self.run_id, prefix=_RUN_ID_PREFIX, field_name="ResultFingerprint.run_id")
```

No `_resolver` pattern needed — ResultFingerprint is **fully self-contained** (unlike Slice α's Claim/EvidenceRef which delegated to row context). It is a pure data sub-object owned by EvaluateResult.

### 5.2 EvaluateResult — new field set

```python
@dataclass(frozen=True)
class EvaluateResult:
    result_id: str
    rows: tuple[EvaluateRow, ...]
    head: Rule
    engine: str
    evaluated_at: object
    fingerprint: ResultFingerprint                       # new — folds 6 fields
    engine_meta: Mapping[str, Any]                       # new — folds engine_version + adapter_version (and extensible)
    # 4 internal plumbing fields unchanged: _schema_index, _row_close_builder, _row_support_artifacts, _row_provenance_envelopes
```

Net field count: 13 direct public fields → 7 direct public fields + 2 sub-objects + 4 internal fields. `__post_init__` validates `fingerprint` is a `ResultFingerprint` instance. It also normalizes `engine_meta` with `_freeze_mapping(...)` (or equivalent immutable copy) and validates at least the required keys `engine_version` and `adapter_version` are present with values `str | None`; extra keys are allowed for future engine metadata, but the two compatibility keys are not optional.

### 5.3 Deprecated `@property` for 8 removed fields

```python
@property
def expr_digest(self) -> str:
    _warn_deprecated_result_field("expr_digest", "EvaluateResult.fingerprint.expr_digest")
    return self.fingerprint.expr_digest

# similar for rule_set_digest / view_snapshot_digest / config_digest / result_digest / run_id

@property
def engine_version(self) -> str | None:
    _warn_deprecated_result_field("engine_version", 'EvaluateResult.engine_meta["engine_version"]')
    return _engine_meta_optional_str(self.engine_meta, "engine_version")

@property
def adapter_version(self) -> str | None:
    _warn_deprecated_result_field("adapter_version", 'EvaluateResult.engine_meta["adapter_version"]')
    return _engine_meta_optional_str(self.engine_meta, "adapter_version")
```

Simpler than Slice α's resolver pattern because EvaluateResult is itself the container — direct `self.fingerprint.X` / validated `self.engine_meta[...]` access; no `_row_resolver` indirection; no `DetachedXError` case (standalone EvaluateResult always has its sub-object). Do **not** use raw `.get(...)` in deprecated properties because that would silently hide missing or invalid compatibility keys.

### 5.4 `result_digest_for(...)` helper — compatibility shape

The shipped helper at [`evaluate_result.py:565-612`](../../../src/factgraph/application/protocol/evaluate_result.py) takes 12 explicit kwargs and produces `evaluate_result_digest_v1` canonical bytes. **Byte payload must remain identical** for equivalent inputs (D19 contract preservation).

Two options for Step 4.7:

- **Option α-style explicit-context preservation**: keep the helper signature as-is (12 kwargs); Slice β's deprecated properties + sub-object access pattern remains internal to EvaluateResult construction. The helper continues to be the canonical digest-bytes builder. This is the lower-risk path.
- **Option helper-renamed-to-sub-object-input**: refactor `result_digest_for(..., fingerprint_inputs: ResultFingerprintInputs, engine_meta: Mapping)` style. Higher refactor risk; recommends Step 4.4 evaluator preflight.

Step 4.2 review chooses. Default lock: **Option α-style** — keep existing helper signature. Implementation may add a thin wrapper only if construction-site ergonomics demand, but the public helper remains the canonical byte builder and its input validation remains source-of-truth.

### 5.4.1 Construction-order lock (Step 4.2 P1)

`ResultFingerprint` includes `result_digest`, and `result_digest_for(...)` requires `result_id`, `run_id`, row digests, engine versions, and the four provenance digests. Existing construction first computes primitive values, then `result_id`, rows/row digests, then `result_digest`, and only then can the complete container exist. Slice β must preserve this ordering:

1. compute primitive digest/version values (`run_id`, provenance digests, engine versions, head identifiers);
2. compute `result_id` with `result_id_for(...)`;
3. construct rows and row digests using explicit context, not deprecated properties;
4. compute `result_digest` with the unchanged `result_digest_for(...)`;
5. construct `fingerprint=ResultFingerprint(..., result_digest=result_digest, run_id=run_id)`;
6. construct `EvaluateResult(..., fingerprint=fingerprint, engine_meta=...)`.

Do **not** require `ResultFingerprint` as an input to `result_id_for(...)` or `result_digest_for(...)`; that introduces a circular construction dependency and risks helper rewrites that would violate D19 byte-equal preservation.

### 5.5 Construction-site updates

All `EvaluateResult(...)` construction sites must drop the 8 now-removed kwargs and pass `fingerprint=ResultFingerprint(...)` + `engine_meta={...}`. Step 4.3 preflight will enumerate the concrete pairs; expected from Slice α precedent:

- Production: [`src/factgraph/sdk/store.py:2697-2725`](../../../src/factgraph/sdk/store.py) `_evaluate(...)` (already touched by Slice α PF-R1)
- Production: [`src/service/runtime_v1.py:2328-2395`](../../../src/service/runtime_v1.py) `_evaluate_result_from_candidates(...)` (Step 4.3 PF-R1 critical catch; service-side EvaluateResult construction, not serializer)
- Test fixtures: `tests/application/protocol/test_evaluate_result_dtos.py` (Slice α touched 2 fixture pairs; β may have parallel sites)
- Test digests: `tests/application/protocol/test_evaluate_result_digests.py` (byte-equal preservation tests)
- SDK export guard: `tests/test_sdk_find_partial_identity.py` currently asserts `len(factgraph.sdk.__all__) == 64`; adding `ResultFingerprint` is an intentional public SDK surface expansion and must update this guard (and its positive membership assertion) rather than treating the count failure as drift.

### 5.6 Internal compatibility inventory (parallel to Slice α §5.6)

Normal internal operations must not emit user-facing deprecation warnings just because they need digest/id values. Step 4.3 preflight enumerates the clusters; expected:

- Metadata snapshot consumer at [`evaluate_result.py:1251-1267`](../../../src/factgraph/application/protocol/evaluate_result.py) (`_evidence_metadata_payload_for_row_result`) — currently bundles the digest/id/version fields into dict for audit/provenance. Step 4.7 should rewrite to read from `result.fingerprint.X` / validated `result.engine_meta[...]` directly.
- Checked-scope consumer at [`evaluate_result.py:1337-1353`](../../../src/factgraph/application/protocol/evaluate_result.py) (`_checked_scope_for_row_result`) — currently reads `config_digest`, `expr_digest`, `rule_set_digest`, and `view_snapshot_digest` directly.
- SDK store metadata snapshot at [`src/factgraph/sdk/store.py:2527-2539`](../../../src/factgraph/sdk/store.py) (`_manual_explain_checked_scope`) — same pattern.
- result-digest construction path: `result_digest_for(...)` itself takes individual kwargs; internal caller sites read from new fingerprint sub-object inputs without deprecated property access.

### 5.7 Quickstart docs touch (PF-R3 pattern)

Required docs cascade:

- `docs/quickstart/evaluate_and_evidence.md`
- `docs/official/kernel/quickstart/evidence.md`
- `docs/official/kernel/quickstart/namespace-map.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/service/docs/03_runtime_queries_policy.md`

The in-process docs (`docs/quickstart`, official quickstart, SDK docs) get:

- Active frozen fields shown as `result_id`, `rows`, `head`, `engine`, `evaluated_at`, `fingerprint`, `engine_meta`
- Deprecated compatibility properties shown explicitly (`expr_digest` / `rule_set_digest` / `view_snapshot_digest` / `config_digest` / `result_digest` / `run_id` / `engine_version` / `adapter_version`)
- New `ResultFingerprint` field tree added with its 6 fields
- SDK import comments updated to reflect deprecated properties

The service policy doc keeps flat JSON fields where it documents HTTP/service wire payloads, but it must label those as wire-compatibility fields backed by `EvaluateResult.fingerprint` / `engine_meta`, not direct in-process frozen fields.

### 5.8 Service runtime scope (N-1/N-2 analog)

Step 4.3 preflight split service work into two concrete duties:

- **N-1 service production construction** — `src/service/runtime_v1.py:2328-2395` `_evaluate_result_from_candidates(...)` must construct `ResultFingerprint` and validated `engine_meta` after computing `result_digest`, following §5.4.1 ordering.
- **N-2 service serializer** — `src/service/runtime_v1.py:2445-2462` `_evaluate_result_to_dict(...)` must preserve the JSON wire shape (flat digest/version fields) while reading from sub-objects internally.

This does not violate INV-6: service construction is an existing legacy construction path following the application protocol DTO shape; it is not substrate authority and does not introduce SDK reverse-dependency.

## 6. Boundaries And Invariants

- Must preserve:
  - User-facing access paths `result.expr_digest` / `.rule_set_digest` / `.view_snapshot_digest` / `.config_digest` / `.result_digest` / `.run_id` / `.engine_version` / `.adapter_version` continue to return **byte-equal value** (only with `DeprecationWarning` emitted)
  - **`evaluate_result_digest_v1` canonical bytes preserved** — D19 contract, the digest payload schema is the contract surface, not the field organization of the EvaluateResult container
  - Service JSON wire shape preserved (flat digest fields in JSON output)
  - Service production construction may be updated only to follow the new application-protocol DTO shape; no new service authority over digest semantics
  - Slice α's resolver pattern + Claim/EvidenceRef deprecated properties untouched (β is independent surface)
  - INV-6 application-first — substrate authority unchanged
  - Q-PR1 sacred 5-path 0-diff (`evaluate_result.py` not on sacred path; safe to edit)
- Explicitly NOT in this slice:
  - Wrapper class removal (Slice γ)
  - SDK re-export removal — `from factgraph.sdk import EvaluateResult` still works; **add** `from factgraph.sdk import ResultFingerprint` for user access to new sub-object
  - Silent `engine_meta` drift — missing `engine_version` / `adapter_version` keys or non-`str | None` values are invalid protocol shape, not compatibility defaults
  - Changing canonical bytes schema name from `evaluate_result_digest_v1`
- Compatibility constraints:
  - `DeprecationWarning` at `stacklevel=2` per Slice α precedent (user callsite is reported)
  - One full release cycle for deprecated properties; removal scheduled for a future fold-completion slice (not γ — γ is Claim/EvidenceRef wrapper removal, β properties remain until later)

### 6.1 Cadence path locks (per user 2026-06-03)

- **§5.4 deprecation strategy — local Q fold**: locked on this blueprint branch via Step 4.2 review + Step 4.4 amendment fold per Slice α precedent. Single-Q consolidation; no separate Q-decision doc. Escalation rule: if Step 4.2 surfaces public-compat or cross-slice impact for §5.4, escalate to dedicated Q-decision doc before scoped anchor.
- **Other 6 §5 Qs explicitly deferred**: §5.1 (raw_kind/bound placement), §5.3 (query-style arity), §5.5 (closed_head_digest), §5.6 (`:exists` Claim/RowKind), §5.7 (auto-prepend). All deferred until before Slice γ; not in Slice β scope. §5.2 (ResultFingerprint sub-object vs Mapping) is **the Q this slice locks** — picks **Option A sub-object** per parent design tentative answer (type safety + IDE hints + style consistency with other application protocol DTOs).
- **Stage 1 audit doc deferred per Slice 4/5 precedent** ([`workflow/CADENCE.md`](../../CADENCE.md):268). Stage-0 source audit folded into parent design + this blueprint draft. No separate `workflow/audit/active/2026-06-03_result-fingerprint-fold-vs-shipped.md`. Step 4.2 reviewer verifies via Rule 1 fresh reads.

## 7. Acceptance

- [ ] New `ResultFingerprint` frozen DTO defined with 6 fields + `__post_init__` validation
- [ ] `EvaluateResult` direct public field set reorganized: 13 → 7 + `fingerprint: ResultFingerprint` + `engine_meta: Mapping[str, Any]`
- [ ] `engine_meta` normalized/validated: required keys `engine_version` and `adapter_version` present with `str | None` values; deprecated properties do not use raw `.get(...)`
- [ ] 8 deprecated `@property` exist on `EvaluateResult` + emit `DeprecationWarning` + return byte-equal values
- [ ] `result_digest_for(...)` shipped helper preserved byte-equal output (test against pre-Slice-β fixture)
- [ ] `evaluate_result_digest_v1` canonical bytes unchanged for equivalent inputs (D19 contract)
- [ ] Construction order preserves primitive → `result_id` → rows/row digests → `result_digest` → `ResultFingerprint` → `EvaluateResult`; no circular helper dependency
- [ ] All `EvaluateResult(...)` construction sites updated (Step 4.3 enumerates) — drop 8 removed kwargs + pass `fingerprint=...` + `engine_meta=...`
- [ ] Service production construction `_evaluate_result_from_candidates(...)` updated as an explicit construction site, not left to serializer-only work
- [ ] Internal compatibility paths (metadata snapshot consumers in `evaluate_result.py` + `sdk/store.py`) do not emit deprecation warnings during normal `EvaluateResult` construction
- [ ] Service serializer `_evaluate_result_to_dict(...)` preserves JSON wire shape (flat digest fields) without internal warnings
- [ ] Active docs cascade updated: quickstart field tree + official evidence quickstart + namespace-map + SDK rules docs + service runtime policy wire-shape note
- [ ] New tests:
  - [ ] `test_result_fingerprint_field_set`
  - [ ] `test_evaluate_result_deprecated_expr_digest_emits_warning`
  - [ ] `test_evaluate_result_deprecated_rule_set_digest_emits_warning`
  - [ ] `test_evaluate_result_deprecated_view_snapshot_digest_emits_warning`
  - [ ] `test_evaluate_result_deprecated_config_digest_emits_warning`
  - [ ] `test_evaluate_result_deprecated_result_digest_emits_warning`
  - [ ] `test_evaluate_result_deprecated_run_id_emits_warning`
  - [ ] `test_evaluate_result_deprecated_engine_version_emits_warning`
  - [ ] `test_evaluate_result_deprecated_adapter_version_emits_warning`
  - [ ] `test_result_digest_for_byte_equal_to_pre_beta_fixture`
  - [ ] `test_evaluate_result_construction_with_fingerprint_kwarg`
- [ ] Existing test suite passes with `PYTHONPATH=src python -m pytest -W "ignore::DeprecationWarning::factgraph" tests/application/protocol tests/sdk/test_evaluate_result_exports.py tests/sdk/test_rule_expr_evaluate.py tests/test_db_attach_lifecycle.py tests/test_problog_semantics_profile_migration.py`
- [ ] SDK `from factgraph.sdk import ResultFingerprint` works; SDK `__all__` includes `ResultFingerprint`
- [ ] `tests/test_sdk_find_partial_identity.py` updated for the intentional SDK `__all__` count increase + positive `ResultFingerprint` membership assertion
- [ ] No edits outside `factgraph.application.protocol` except (Step 4.3/4.6.5-enumerated) scoped service serializer, tests, and docs consumers
- [ ] Q-PR1 5-path 0-diff vs `4c472b50` preserved (sacred contract)

## 8. Implementation Plan

Codex implementation order (each step ends with targeted `PYTHONPATH=src python -m pytest tests/application/protocol tests/sdk/test_evaluate_result_exports.py -x` clean):

1. **[audit pin]** Re-read shipped `EvaluateResult` definition + `result_digest_for(...)` helper; confirm anchors match blueprint §4
2. **[audit pin]** Enumerate all `EvaluateResult(...)` construction sites in `src/factgraph/` + `src/service/` + `tests/`; compare against Step 4.3 PF-R1/PF-r1 expectations
3. **[ResultFingerprint definition]** Add `ResultFingerprint` frozen DTO + `__post_init__` validation; add unit test for field set; export from `application/protocol/__init__.py`
4. **[EvaluateResult field reshape]** Replace `EvaluateResult` class definition with new shape (§5.2) — drop 8 frozen fields, add `fingerprint` + validated immutable `engine_meta` fields, update `__post_init__` to validate new shape
5. **[8 deprecated @property]** Add deprecated properties for `expr_digest` / `rule_set_digest` / `view_snapshot_digest` / `config_digest` / `result_digest` / `run_id` / `engine_version` / `adapter_version` per §5.3
6. **[construction order + byte-equal preservation]** Preserve §5.4.1 ordering and verify `result_digest_for(...)` byte output unchanged via pre-Slice-β fixture test (capture before step 4)
7. **[construction-site updates]** Update each site enumerated in step 2 — `sdk/store.py` `_evaluate(...)` + `service/runtime_v1.py` `_evaluate_result_from_candidates(...)` + test fixtures + test digests; construct `ResultFingerprint` only after `result_digest` is available
8. **[internal compatibility paths]** Rewrite metadata snapshot consumers in `evaluate_result.py` + `sdk/store.py` to read from `self.fingerprint.X` / `self.engine_meta.X` directly
9. **[service runtime]** Update `src/service/runtime_v1.py` `_evaluate_result_from_candidates(...)` + `_evaluate_result_to_dict(...)` per §5.8
10. **[SDK + protocol re-export]** Add `ResultFingerprint` to `factgraph.application.protocol.__all__` + `factgraph.sdk.__all__`
11. **[new tests]** Add the acceptance tests listed in §7, including engine-meta validation, SDK `__all__` guard updates, and active SDK test coverage from PF-r1
12. **[quickstart docs rewrite]** Update `docs/quickstart/evaluate_and_evidence.md` per §5.7 (similar to Slice α PF-R3 pattern)
13. **[docs cascade]** Update the named PF-R3 docs cascade; Step 4.6.5 may still add further docs consumers if deletion-grep finds them
14. **[final verification]** Targeted pytest clean; manual grep `grep -nE 'EvaluateResult\((expr_digest|rule_set_digest|view_snapshot_digest|config_digest|result_digest|run_id|engine_version|adapter_version)=' src/ tests/` returns zero hits

## 9. Docs To Update

- `docs/quickstart/evaluate_and_evidence.md` — EvaluateResult field-shape rewrite (active vs deprecated) + new `ResultFingerprint` tree
- `docs/official/kernel/quickstart/evidence.md` — envelope/fingerprint wording
- `docs/official/kernel/quickstart/namespace-map.md` — `rule_set_digest` wording
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` — replay anchors / envelope identity wording
- `src/service/docs/03_runtime_queries_policy.md` — flat service JSON fields preserved as wire compatibility backed by fingerprint/engine_meta
- Any additional active docs consumers found at Step 4.6.5 grep (Slice α N-2 precedent)
- This blueprint's Outcome / Deviations section (filled at archive time)

## 10. Outcome / Deviations

To be filled at archive time:

- 最终落地结果:
- 与 blueprint 不同的地方:
- 为什么会有这些调整:
- 归档说明:
