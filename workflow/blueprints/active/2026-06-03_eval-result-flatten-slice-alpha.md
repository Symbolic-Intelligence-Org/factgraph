# Task Blueprint: Evaluate-result flatten Slice α — Claim/EvidenceRef redundant-field removal with deprecated property fallback

- Status: draft
- Created: 2026-06-03
- Last Updated: 2026-06-03
- Owner: Claude (blueprint) / Codex (impl) — cross-flip per `feedback_design_impl_branch_isolation`
- Related Modules:
  - `src/factgraph/application/protocol/evaluate_result.py` (Claim / EvidenceRef / EvaluateRow definitions)
  - `src/factgraph/sdk/__init__.py` (top-level re-export of Claim / EvidenceRef)
  - `tests/application/protocol/test_evaluate_result_dtos.py` (DTO invariant tests + row/explain fixtures)
  - `tests/application/protocol/test_evaluate_result_digests.py` (digest helper tests)
  - `tests/sdk/test_evaluate_result_exports.py` (SDK export smoke tests)
- Related Docs:
  - [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §6 Slice α (parent design)
  - [`docs/quickstart/evaluate_and_evidence.md`](../../../docs/quickstart/evaluate_and_evidence.md) §2.3 / §2.4 / §9.1 (current Claim / EvidenceRef user-facing surface — gets deprecation notes plus active-field / deprecated-property shape rewrite in this slice)
- Audit Log:
  - [2026-06-03_eval-result-flatten-slice-alpha.audit.md](./2026-06-03_eval-result-flatten-slice-alpha.audit.md)

## 1. Problem

Parent design-point §2.2 / §2.3 audit established that `Claim` (5 fields) and `EvidenceRef` (5 fields) carry 2 + 4 fields that are structurally redundant:

- `Claim.name` == `EvaluateResult.head.id`
- `Claim.arguments` ≈ `EvaluateRow.bindings`
- `EvidenceRef.row_id` == `EvaluateRow.row_id` (D17 invariant, enforced [evaluate_result.py:135-136](../../../src/factgraph/application/protocol/evaluate_result.py))
- `EvidenceRef.fact_digest` == `Claim.digest` (D17 invariant, enforced [evaluate_result.py:137-138](../../../src/factgraph/application/protocol/evaluate_result.py))
- `EvidenceRef.result_id` == parent `EvaluateResult.result_id`
- `EvidenceRef.ref_id` is derivable from the other four fields (composite hash; no independent consumer per design-point §2.3)

Slice α is the lowest-risk slice (parent §6 ordering: α → β → γ → ζ → η → ε → δ) — it removes these 6 redundant fields from the frozen DTO field set while preserving the **same user-facing access paths** through deprecated `@property` fallbacks, leveraging an internal owner-resolver pattern identical to the shipped `EvaluateRow._result_resolver` ([evaluate_result.py:126](../../../src/factgraph/application/protocol/evaluate_result.py)). Wrapper classes (`Claim` / `EvidenceRef`) remain. Surface-shape removal of the wrappers themselves is Slice γ (out of scope here).

## 2. Goals

- G1 — Remove `Claim.name`, `Claim.arguments`, `EvidenceRef.row_id`, `EvidenceRef.result_id`, `EvidenceRef.ref_id`, `EvidenceRef.fact_digest` from the frozen `@dataclass` field set
- G2 — Add internal owner-resolver fields (`Claim._row_resolver`, `EvidenceRef._row_resolver`) following the same `compare=False, hash=False, repr=False` pattern as `EvaluateRow._result_resolver`
- G3 — Add deprecated `@property` for each removed field name (emit `DeprecationWarning` on access; resolve via owner resolver chain)
- G4 — Update D17 invariant validation at `EvaluateRow.__post_init__` ([:135-138](../../../src/factgraph/application/protocol/evaluate_result.py)) — replace field-equality checks with no-op (the fields no longer exist as frozen state; the invariant is satisfied tautologically by the resolver chain)
- G5 — Existing user code accessing `row.claim.name` / `row.claim.arguments` / `row.evidence_ref.row_id` / `.result_id` / `.ref_id` / `.fact_digest` continues to work (emits `DeprecationWarning`)
- G6 — Construction sites enumerated by Step 4.3 preflight (`evaluate_result.py:582-596`, `test_evaluate_result_dtos.py:92-105`, `test_evaluate_result_dtos.py:228-240`) are updated to drop the redundant kwargs (and to rely on resolver injection instead)
- G7 — Test coverage updated for both the deprecated-property emission and the resolver wiring

## 3. Non-goals

- N1 — **Removing `Claim` / `EvidenceRef` wrapper classes themselves** (that is Slice γ — §6 of parent design)
- N2 — Flattening fields onto `EvaluateRow` (`row.kind` / `row.digest` / `row.closed_head_digest` direct access — also Slice γ)
- N3 — Removing the `Claim.kind` / `Claim.repr` / `Claim.digest` fields (kept — non-redundant per audit)
- N4 — Removing the `EvidenceRef.closed_head_digest` field (kept — non-redundant per audit)
- N5 — `ResultFingerprint` sub-object (Slice β)
- N6 — `bindings` shape simplification (Slice ζ)
- N7 — `EvidenceGraph` 3-tier hierarchy (Slice η)
- N8 — query-style `head.id` decoupling (Slice δ)
- N9 — User-facing breaking change at this slice (warnings only)

## 4. Current Context

- Current implementation entry:
  - Claim class: [`src/factgraph/application/protocol/evaluate_result.py:85-99`](../../../src/factgraph/application/protocol/evaluate_result.py)
  - EvidenceRef class: [`:102-115`](../../../src/factgraph/application/protocol/evaluate_result.py)
  - EvaluateRow D17 invariant block: [`:128-147`](../../../src/factgraph/application/protocol/evaluate_result.py) — specifically lines 135-138 (the two cross-field equality assertions)
  - EvaluateRow resolver pattern (template for new Claim/EvidenceRef resolvers): [`:126`](../../../src/factgraph/application/protocol/evaluate_result.py) + [`:149-152`](../../../src/factgraph/application/protocol/evaluate_result.py)
  - EvaluateResult row-binding order: [`:213-236`](../../../src/factgraph/application/protocol/evaluate_result.py) — currently checks `row.evidence_ref.result_id` before rebinding rows with `_result_resolver`; Slice α must rewrite this path to avoid deprecated-property access before owner binding
  - Row digest helper: [`:432-458`](../../../src/factgraph/application/protocol/evaluate_result.py) — currently reads `row.claim.arguments`, `row.claim.name`, and `row.evidence_ref.{fact_digest,result_id,row_id}`; Slice α must rewrite this helper to avoid warning-emitting deprecated properties and to preserve byte-identical row digests via explicit context
  - SDK top-level re-export: [`src/factgraph/sdk/__init__.py:33-49`](../../../src/factgraph/sdk/__init__.py)
- Current known constraints:
  - D17 invariant (parent ADR `2026-05-25_t5-d17-result-row-dto-foundation.md`) — this slice does not violate it because the cross-field equalities still hold at runtime through the resolver chain; only the frozen-field enforcement form changes
  - Q-PR1 sacred 5-path 0-diff (per [`project_db_view_audit_complete_2026_05_20`](../../../.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_db_view_audit_complete_2026_05_20.md) / parent design §7.5) — `evaluate_result.py` is **not** on the sacred path; safe to edit. `core/store/ledger.py` is sacred and untouched here
  - INV-6 (application-first runtime authority) — all edits inside `factgraph.application.protocol` + tests; no substrate up-cast, no SDK reverse-dependency
- Current related historical blueprints / decisions:
  - `workflow/design/decisions/active/2026-05-25_t5-d17-result-row-dto-foundation.md` (D17 — partial supersede direction recorded in parent design §7.6; this slice **does not** formally supersede D17 — that is Slice γ's job)
  - `workflow/design/decisions/active/2026-05-25_t5-d19-digest-source-of-truth.md` (D19 — digest algorithm unchanged here; field location unchanged here)

## 5. Proposed Shape

### 5.1 Claim — new field set + resolver

```python
@dataclass(frozen=True)
class Claim:
    kind: ClaimKind
    repr: str
    digest: str
    _row_resolver: Callable[[], "EvaluateRow"] | None = field(
        default=None, repr=False, compare=False, hash=False
    )

    def __post_init__(self) -> None:
        if self.kind not in _CLAIM_KINDS:
            raise ProtocolShapeError("Claim.kind must be one of fact_triple, rule_head, aggregate_result, projection")
        _require_non_empty_str(self.repr, field_name="Claim.repr")
        _require_sha256_token(self.digest, field_name="Claim.digest")
        if self._row_resolver is not None and not callable(self._row_resolver):
            raise ProtocolShapeError("Claim._row_resolver must be callable or None")

    # Deprecated property fallbacks (Slice α)
    @property
    def name(self) -> str:
        warnings.warn(
            "Claim.name is deprecated; use EvaluateResult.head.id "
            "(Slice α of evaluate-result-flatten design)",
            DeprecationWarning, stacklevel=2,
        )
        row = self._require_owner()
        return row._require_live_result().head.id

    @property
    def arguments(self) -> Mapping[str, Any]:
        warnings.warn(
            "Claim.arguments is deprecated; use EvaluateRow.bindings "
            "(Slice α of evaluate-result-flatten design)",
            DeprecationWarning, stacklevel=2,
        )
        return self._require_owner().bindings

    def _require_owner(self) -> "EvaluateRow":
        if self._row_resolver is None:
            raise DetachedClaimError(
                "Claim deprecated-field access requires owner resolver; "
                "Claim was constructed standalone (e.g., in a test that bypasses EvaluateRow)"
            )
        return self._row_resolver()
```

Net field count: 5 → 3 frozen + 1 internal resolver.

### 5.2 EvidenceRef — new field set + resolver

```python
@dataclass(frozen=True)
class EvidenceRef:
    closed_head_digest: str
    _row_resolver: Callable[[], "EvaluateRow"] | None = field(
        default=None, repr=False, compare=False, hash=False
    )

    def __post_init__(self) -> None:
        _require_sha256_token(self.closed_head_digest, field_name="EvidenceRef.closed_head_digest")
        if self._row_resolver is not None and not callable(self._row_resolver):
            raise ProtocolShapeError("EvidenceRef._row_resolver must be callable or None")

    # Deprecated property fallbacks (Slice α)
    @property
    def row_id(self) -> str:
        warnings.warn(...DeprecationWarning, stacklevel=2)
        return self._require_owner().row_id

    @property
    def result_id(self) -> str:
        warnings.warn(...DeprecationWarning, stacklevel=2)
        return self._require_owner()._require_live_result().result_id

    @property
    def fact_digest(self) -> str:
        warnings.warn(...DeprecationWarning, stacklevel=2)
        return self._require_owner().claim.digest

    @property
    def ref_id(self) -> str:
        warnings.warn(...DeprecationWarning, stacklevel=2)
        # Computed identically to the shipped evidence_ref_id_for(...) formula
        # (preserve byte-equality so cross-process consumers that compared ref_ids
        # still see the same value)
        row = self._require_owner()
        return evidence_ref_id_for(
            result_id=row._require_live_result().result_id,
            row_id=row.row_id,
            fact_digest=row.claim.digest,
            closed_head_digest=self.closed_head_digest,
        )

    def _require_owner(self) -> "EvaluateRow":
        if self._row_resolver is None:
            raise DetachedEvidenceRefError(...)
        return self._row_resolver()
```

Net field count: 5 → 1 frozen + 1 internal resolver.

Step 4.3 preflight PF-v4 confirmed the ref-id derivation formula is already centralized as `evidence_ref_id_for(result_id, row_id, fact_digest, closed_head_digest)` in [`evaluate_result.py:413-429`](../../../src/factgraph/application/protocol/evaluate_result.py) and exported from the module. Slice α should preserve or wrap that shipped helper; it does **not** need to rediscover or extract a new formula.

### 5.3 EvaluateRow — invariant block reshape

The two cross-field equality assertions ([:135-138](../../../src/factgraph/application/protocol/evaluate_result.py)) are replaced with **resolver wiring**:

```python
def __post_init__(self) -> None:
    _require_non_empty_str(self.row_id, field_name="EvaluateRow.row_id")
    object.__setattr__(self, "bindings", _freeze_mapping(self.bindings, field_name="EvaluateRow.bindings"))
    if not isinstance(self.claim, Claim):
        raise ProtocolShapeError("EvaluateRow.claim must be Claim")
    if not isinstance(self.evidence_ref, EvidenceRef):
        raise ProtocolShapeError("EvaluateRow.evidence_ref must be EvidenceRef")

    # Inject row resolver into claim and evidence_ref so deprecated properties resolve.
    # Use object.__setattr__ because Claim/EvidenceRef are frozen.
    _row_self_ref: Callable[[], "EvaluateRow"] = lambda: self
    object.__setattr__(self.claim, "_row_resolver", _row_self_ref)
    object.__setattr__(self.evidence_ref, "_row_resolver", _row_self_ref)

    # raw_kind / bound validation unchanged
    if self.raw_kind is None:
        if self.bound is not None:
            raise ProtocolShapeError(...)
    else:
        if self.raw_kind not in _RAW_KINDS:
            raise ProtocolShapeError(...)
        object.__setattr__(self, "bound", _validate_bound(self.bound))

    if self._result_resolver is not None and not callable(self._result_resolver):
        raise ProtocolShapeError(...)
```

The cross-field equality is now **structurally tautological** (the deprecated properties literally return `row.row_id` / `row.claim.digest`), so D17 holds without an explicit assertion.

Step 4.2 review tightening: this rewrite must also update `EvaluateResult.__post_init__`
([`evaluate_result.py:213-236`](../../../src/factgraph/application/protocol/evaluate_result.py)).
The shipped container currently checks `row.evidence_ref.result_id` before it binds
rows through `_result_resolver`; after Slice α, that access path is deprecated and
requires a live owner chain. Therefore the implementation must remove the pre-bind
`row.evidence_ref.result_id` equality check and bind rows first. D17 result ownership
semantics become structural through the bound owner resolver, and regression coverage
must assert that `result[0].evidence_ref.result_id` returns `result.result_id` with a
`DeprecationWarning`.

### 5.4 Row digest compatibility (Step 4.2 P1)

The shipped `_row_digest_for(row)` helper ([`evaluate_result.py:432-458`](../../../src/factgraph/application/protocol/evaluate_result.py))
currently reads fields that become deprecated properties in Slice α:

- `row.claim.arguments`
- `row.claim.name`
- `row.evidence_ref.fact_digest`
- `row.evidence_ref.result_id`
- `row.evidence_ref.row_id`

Implementation must not compute row/result digests by calling warning-emitting
deprecated properties. Replace `_row_digest_for(...)` with an explicit-context helper
(name left to implementation, but shape must be equivalent):

```python
def _row_digest_for(
    row: EvaluateRow,
    *,
    result_id: str,
    claim_name: str,
) -> str:
    ...
```

or another shape that supplies the same non-deprecated inputs. The byte payload must
match shipped `evaluate_row_digest_v1` for equivalent rows; tests must verify byte
equality against a pre-Slice-α fixture. This is separate from
`evidence_ref_id_for(...)` because `result_digest_for(...)` consumes row digests
before an `EvaluateResult` can bind row owner resolvers. Step 4.3 PF-R1 also pinned the concrete ordering callsite at [`src/factgraph/sdk/store.py:2705-2706`](../../../src/factgraph/sdk/store.py), where `_row_digest_for(row)` is evaluated before `EvaluateResult(...)` construction.

### 5.5 Construction-site updates (codex impl scope)

All `Claim(...)` and `EvidenceRef(...)` construction sites must drop the now-removed kwargs. Step 4.3 PF-r1 narrowed the direct protocol-constructor scope to the concrete pairs below:

- Production: [`evaluate_result.py:582-596`](../../../src/factgraph/application/protocol/evaluate_result.py) (`_candidate_set_to_evaluate_row(...)`)
- Test fixture: [`tests/application/protocol/test_evaluate_result_dtos.py:92-105`](../../../tests/application/protocol/test_evaluate_result_dtos.py)
- Test fixture / invariant failure: [`tests/application/protocol/test_evaluate_result_dtos.py:228-240`](../../../tests/application/protocol/test_evaluate_result_dtos.py)
- Digest tests under `tests/application/protocol/` — update all `_row_digest_for(...)` callsites to the explicit-context helper from §5.4

Adapter paths are indirect through `_candidate_set_to_evaluate_row(...)`; Step 4.7 should still grep for drift, but direct adapter `_build_*` constructor edits are not expected unless Step 4.6.5 finds new construction sites.

### 5.6 Internal compatibility inventory (Step 4.3 PF-r2)

Normal internal operations must not emit user-facing deprecation warnings merely because they need compatibility values. Step 4.7 must handle these internal access clusters using direct row/result context or helper functions rather than treating deprecated properties as normal internal APIs:

- D17 checks: [`evaluate_result.py:135-138`](../../../src/factgraph/application/protocol/evaluate_result.py)
- `EvaluateResult` pre-bind result check: [`evaluate_result.py:223-224`](../../../src/factgraph/application/protocol/evaluate_result.py)
- Row digest payload: [`evaluate_result.py:442`](../../../src/factgraph/application/protocol/evaluate_result.py), [`:445`](../../../src/factgraph/application/protocol/evaluate_result.py), [`:450-452`](../../../src/factgraph/application/protocol/evaluate_result.py)
- Explanation paths using `row.evidence_ref.ref_id`: [`evaluate_result.py:628`](../../../src/factgraph/application/protocol/evaluate_result.py), [`:643`](../../../src/factgraph/application/protocol/evaluate_result.py), [`:664`](../../../src/factgraph/application/protocol/evaluate_result.py), [`:683`](../../../src/factgraph/application/protocol/evaluate_result.py)
- Anchor comparison: [`evaluate_result.py:848-851`](../../../src/factgraph/application/protocol/evaluate_result.py)
- Evidence graph labels / metadata: [`evaluate_result.py:872`](../../../src/factgraph/application/protocol/evaluate_result.py), [`:1006`](../../../src/factgraph/application/protocol/evaluate_result.py), [`:1013`](../../../src/factgraph/application/protocol/evaluate_result.py), [`:1160`](../../../src/factgraph/application/protocol/evaluate_result.py)
- Existing protocol tests that intentionally assert old access paths: `tests/application/protocol/test_evaluate_result_dtos.py:455`, `:485`, `:647`, `:656`, `:665`, `:707`, `:956`

### 5.7 Quickstart docs touch (in this slice)

Step 4.3 PF-R3 confirmed a one-line banner is insufficient because `docs/quickstart/evaluate_and_evidence.md` currently lists the old complete frozen field shapes at §2.3 / §2.4 and in the §9.1 SDK import comments. Step 4.7 docs work must include:

- A deprecation note at the top of §2.3 and §2.4.
- A `Claim` field tree that shows active frozen fields as `kind`, `repr`, `digest`, with `name` and `arguments` explicitly labeled as deprecated compatibility properties.
- An `EvidenceRef` field tree that shows active frozen field `closed_head_digest`, with `ref_id`, `result_id`, `row_id`, and `fact_digest` explicitly labeled as deprecated compatibility properties.
- §9.1 SDK import comments updated so they no longer present the deprecated properties as frozen DTO fields.

The full wrapper removal / row-level field rewrite remains Slice γ; this slice only makes the current compatibility shape truthful.

## 6. Boundaries And Invariants

- Must preserve:
  - User-facing access paths `row.claim.name` / `.arguments` / `row.evidence_ref.row_id` / `.result_id` / `.ref_id` / `.fact_digest` all continue to return the **byte-equal value** they returned before (only with `DeprecationWarning` emitted)
  - Byte-equal `row_digest` and `result_digest` for equivalent rows; internal digest helpers must avoid deprecated-property access
  - `EvidenceRef.ref_id` formula is preserved bit-for-bit via shipped `evidence_ref_id_for(...)`; Step 4.7 may keep the helper name, wrap it, or alias it, but must not change bytes
  - D17 invariant *semantics* (cross-field equality) — enforced now by structural property delegation instead of frozen-field equality assertions
  - INV-6 application-first — no edits outside `factgraph.application.protocol` (other than test updates)
  - Q-PR1 sacred 5-path 0-diff (`core/store/ledger.py` etc. untouched)
- Explicitly NOT in this slice:
  - Wrapper class removal (Slice γ)
  - SDK re-export changes — `from factgraph.sdk import Claim, EvidenceRef` still works (types unchanged)
- Compatibility constraints:
  - `DeprecationWarning` is emitted at `stacklevel=2` so the user's own callsite is the reported location
  - One full release cycle keeps the deprecated properties; removal scheduled in Slice γ per §5.4 of parent design

### 6.1 Cadence path locks (per user 2026-06-03)

- **§5.4 deprecation strategy — local Q fold**: locked on this blueprint branch via Step 4.2 review + Step 4.4 amendment, not via a separate Q-decision doc. The blueprint's draft answer (single-release-cycle DeprecationWarning, removal in Slice γ) is treated as the local implementation policy for Slice α. **Escalation rule**: if Step 4.2 reviewer surfaces public-compat or cross-slice impact tied to this Q, escalate to a single Q-decision doc (e.g., `workflow/design/decisions/active/2026-06-XX_q-eval-result-deprecation-strategy-decision.md`) before the scoped anchor. The closure §10 must record this consolidation as `single-Q local lock consolidated on blueprint branch`.
- **Other 6 §5 Qs explicitly deferred**: §5.1 (raw_kind/bound row vs Claim placement), §5.2 (ResultFingerprint sub-object vs Mapping), §5.3 (query-style head arity check policy), §5.5 (closed_head_digest row vs EvidenceRef-lite tradeoff), §5.6 (`:exists` Claim vs RowKind), §5.7 (auto-prepend `:exists` coupling). None are load-bearing for Slice α field-removal scope. They will be addressed before Slice γ (parent design §6 ordering).
- **Stage 1 audit doc deferred per Slice 4/5 precedent** ([`workflow/CADENCE.md`](../../CADENCE.md) L268). Stage-0 source audit is considered folded into the parent design-point ([`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §1-§4 friction analysis + §8 file:line anchors) and into this Step 4.1 draft. **No separate** `workflow/audit/active/2026-06-03_eval-result-flatten-vs-shipped.md` is produced at this time. **Step 4.2 reviewer responsibility**: verify the folded audit claims via Rule 1 fresh reads (file:line precision against shipped code). **Escalation rule**: if Step 4.2 finds source grounding insufficient, supplement with a preflight/audit artifact at Step 4.3 — do **not** regress to a formal standalone Stage 1 audit doc (per user lock 2026-06-03; tightening forward, not backward).

## 7. Acceptance

- [ ] All 6 redundant fields removed from `Claim` / `EvidenceRef` frozen field set
- [ ] All 6 deprecated `@property` exist + emit `DeprecationWarning` + return byte-equal values
- [ ] D17 invariant block (`EvaluateRow.__post_init__` L135-138) replaced with resolver injection
- [ ] `EvaluateResult.__post_init__` no longer reads deprecated `EvidenceRef.result_id` before owner binding; `result[0].evidence_ref.result_id` returns `result.result_id` with `DeprecationWarning`
- [ ] `_row_digest_for` / replacement helper preserves byte-identical `evaluate_row_digest_v1` without reading deprecated properties internally
- [ ] `evidence_ref_id_for(...)` shipped ref-id formula preserved byte-for-byte; any wrapper/alias decision keeps the existing public helper usable
- [ ] All Step 4.3 enumerated `Claim(...)` / `EvidenceRef(...)` construction sites updated (`evaluate_result.py:582-596`, `test_evaluate_result_dtos.py:92-105`, `:228-240`); Step 4.6.5 grep confirms no drift
- [ ] Internal compatibility paths listed in §5.6 do not emit deprecation warnings during normal construction, digesting, explaining, or evidence metadata creation
- [ ] New tests:
  - [ ] `test_claim_deprecated_name_emits_warning`
  - [ ] `test_claim_deprecated_arguments_emits_warning`
  - [ ] `test_evidence_ref_deprecated_row_id_emits_warning`
  - [ ] `test_evidence_ref_deprecated_result_id_emits_warning`
  - [ ] `test_evidence_ref_deprecated_ref_id_byte_equal_to_pre_alpha`
  - [ ] `test_evidence_ref_deprecated_fact_digest_emits_warning`
  - [ ] `test_standalone_claim_without_resolver_raises_detached_error`
  - [ ] `test_standalone_evidence_ref_without_resolver_raises_detached_error`
- [ ] Existing test suite passes with `python -m pytest -W "ignore::DeprecationWarning::factgraph" tests/application/protocol tests/sdk/test_evaluate_result_exports.py` (warnings are emitted but tests don't assert against them unless new)
- [ ] `docs/quickstart/evaluate_and_evidence.md` §2.3 / §2.4 / §9.1 updated with deprecation notes plus active-field / deprecated-property shapes
- [ ] No `src/factgraph/application/protocol/docs/README.md` update unless a module-docs subtree appears before Step 4.6.5 (Step 4.3 PF-v7 found none)
- [ ] No edits outside `factgraph.application.protocol` (other than test updates + the quickstart docs field-shape rewrite)

## 8. Implementation Plan

Codex implementation order (each step ends with targeted `python -m pytest tests/application/protocol tests/sdk/test_evaluate_result_exports.py -x` clean; run the broader suite only after the targeted cohort is green):

1. **[audit pin]** Re-read shipped `Claim` / `EvidenceRef` / `EvaluateRow` definitions and `evidence_ref_id_for(...)`; record that the ref-id formula is already centralized and exported
2. **[audit pin]** Re-run construction-site grep for `Claim(...)` / `EvidenceRef(...)` in `src/factgraph/application/protocol/evaluate_result.py`, `tests/application/protocol/`, and `tests/sdk/`; compare against Step 4.3 PF-r1 before editing
3. **[ref-id preservation]** Preserve shipped `evidence_ref_id_for(...)` byte output. If a private wrapper/alias is introduced for naming consistency, add a unit test verifying byte-equal output against a hand-picked pre-Slice-α fixture
4. **[Claim refactor]** Replace `Claim` class definition with new shape (§5.1) — drop `name` / `arguments` frozen fields, add `_row_resolver` + 2 deprecated properties + `DetachedClaimError`
5. **[EvidenceRef refactor]** Replace `EvidenceRef` class definition (§5.2) — drop `row_id` / `result_id` / `ref_id` / `fact_digest` frozen fields, add `_row_resolver` + 4 deprecated properties + `DetachedEvidenceRefError`
6. **[EvaluateRow / EvaluateResult invariant reshape]** Update `EvaluateRow.__post_init__` (§5.3) and `EvaluateResult.__post_init__` (§5.3 Step 4.2 tightening) — remove L135-138 cross-field assertions, add row resolver injection, and remove the pre-bind `row.evidence_ref.result_id` read
7. **[digest compatibility]** Update `_row_digest_for` or replacement helper per §5.4 so row/result digests preserve shipped bytes without using deprecated properties internally
8. **[construction-site updates]** Update each site enumerated in step 2 to drop now-removed kwargs and rely on `EvaluateRow.__post_init__` / `EvaluateResult.__post_init__` for resolver wiring
9. **[internal compatibility paths]** Update the §5.6 clusters so normal construction, digesting, explaining, stale-row checks, and evidence metadata creation use direct context/helpers rather than deprecated-property access
10. **[new tests]** Add the 8 acceptance tests listed in §7 plus row/result digest byte-equality coverage from §5.4 and no-internal-warning coverage from §5.6
11. **[quickstart docs rewrite]** Update `docs/quickstart/evaluate_and_evidence.md` §2.3 / §2.4 / §9.1 per §5.7
12. **[module docs check]** Do not create `src/factgraph/application/protocol/docs/README.md`; only update module docs if a subtree appears before Step 4.6.5
13. **[final verification]** Targeted pytest clean; manual grep `grep -nE 'Claim\(name=|EvidenceRef\((ref_id|result_id|row_id|fact_digest)=' src/ tests/` returns zero hits

## 9. Docs To Update

- `docs/quickstart/evaluate_and_evidence.md` §2.3 + §2.4 + §9.1 (deprecation notes plus active-field / deprecated-property shape rewrite)
- `src/factgraph/application/protocol/docs/README.md` — no action expected because Step 4.3 PF-v7 found no module-docs subtree; revisit only if Step 4.6.5 finds drift
- This blueprint's Outcome / Deviations section (filled at archive time)

## 10. Outcome / Deviations

To be filled at archive time:

- 最终落地结果:
- 与 blueprint 不同的地方:
- 为什么会有这些调整:
- 归档说明:
