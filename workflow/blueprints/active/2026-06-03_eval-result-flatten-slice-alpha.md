# Task Blueprint: Evaluate-result flatten Slice α — Claim/EvidenceRef redundant-field removal with deprecated property fallback

- Status: draft
- Created: 2026-06-03
- Last Updated: 2026-06-03
- Owner: Claude (blueprint) / Codex (impl) — cross-flip per `feedback_design_impl_branch_isolation`
- Related Modules:
  - `src/factgraph/application/protocol/evaluate_result.py` (Claim / EvidenceRef / EvaluateRow definitions)
  - `src/factgraph/sdk/__init__.py` (top-level re-export of Claim / EvidenceRef)
  - `tests/factgraph/application/protocol/test_evaluate_result.py` (DTO invariant tests)
- Related Docs:
  - [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §6 Slice α (parent design)
  - [`docs/quickstart/evaluate_and_evidence.md`](../../../docs/quickstart/evaluate_and_evidence.md) §2.3 / §2.4 (current Claim / EvidenceRef user-facing surface — will get a "deprecated" note added in this slice)
- Audit Log:
  - [2026-06-03_eval-result-flatten-slice-alpha.audit.md](./2026-06-03_eval-result-flatten-slice-alpha.audit.md)

## 1. Problem

Parent design-point §2.2 / §2.3 audit established that `Claim` (5 fields) and `EvidenceRef` (5 fields) carry 4 + 4 fields that are structurally redundant:

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
- G6 — Construction sites in `evaluate_result.py` / adapter `_build_*` paths that currently pass these fields to `Claim(...)` / `EvidenceRef(...)` are updated to drop the redundant kwargs (and to inject the owner resolver instead)
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
        # Computed identically to the previous shipped formula (preserve byte-equality
        # so cross-process consumers that compared ref_ids still see the same value)
        row = self._require_owner()
        return _compute_evidence_ref_id(
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

`_compute_evidence_ref_id(...)` extracts the existing ref-id derivation formula (audit will pin its exact shipped form before extraction).

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

### 5.4 Construction-site updates (codex impl scope)

All `Claim(...)` and `EvidenceRef(...)` construction sites must drop the now-removed kwargs. Codex audit (§audit log Task A2) enumerates the full set; expected sites based on parent design §8 anchors:

- `evaluate_result.py` internal helpers that build rows
- Adapter `_build_*` paths (native / souffle / problog / pyreason)
- Test fixtures that construct standalone Claim/EvidenceRef for unit testing — these need `_row_resolver` provided or accept `DetachedClaimError` / `DetachedEvidenceRefError`

### 5.5 Quickstart docs touch (in this slice)

`docs/quickstart/evaluate_and_evidence.md` §2.3 (Claim DTO) and §2.4 (EvidenceRef DTO) get a **one-line deprecation banner** at the top of each section pointing to the design-point. The full DTO rewrite belongs to Slice γ; this slice only adds the deprecation hint.

## 6. Boundaries And Invariants

- Must preserve:
  - User-facing access paths `row.claim.name` / `.arguments` / `row.evidence_ref.row_id` / `.result_id` / `.ref_id` / `.fact_digest` all continue to return the **byte-equal value** they returned before (only with `DeprecationWarning` emitted)
  - `EvidenceRef.ref_id` formula is preserved bit-for-bit — the shipped derivation logic is extracted to `_compute_evidence_ref_id` (audit Task A1 must confirm the formula before extraction)
  - D17 invariant *semantics* (cross-field equality) — enforced now by structural property delegation instead of frozen-field equality assertions
  - INV-6 application-first — no edits outside `factgraph.application.protocol` (other than test updates)
  - Q-PR1 sacred 5-path 0-diff (`core/store/ledger.py` etc. untouched)
- Explicitly NOT in this slice:
  - Wrapper class removal (Slice γ)
  - SDK re-export changes — `from factgraph.sdk import Claim, EvidenceRef` still works (types unchanged)
- Compatibility constraints:
  - `DeprecationWarning` is emitted at `stacklevel=2` so the user's own callsite is the reported location
  - One full release cycle keeps the deprecated properties; removal scheduled in Slice γ per §5.4 of parent design

## 7. Acceptance

- [ ] All 6 redundant fields removed from `Claim` / `EvidenceRef` frozen field set
- [ ] All 6 deprecated `@property` exist + emit `DeprecationWarning` + return byte-equal values
- [ ] D17 invariant block (`EvaluateRow.__post_init__` L135-138) replaced with resolver injection
- [ ] `_compute_evidence_ref_id(...)` helper extracted; shipped ref-id formula audited and pinned before extraction (audit Task A1)
- [ ] All `Claim(...)` / `EvidenceRef(...)` construction sites in src + tests updated (audit Task A2 enumerates)
- [ ] New tests:
  - [ ] `test_claim_deprecated_name_emits_warning`
  - [ ] `test_claim_deprecated_arguments_emits_warning`
  - [ ] `test_evidence_ref_deprecated_row_id_emits_warning`
  - [ ] `test_evidence_ref_deprecated_result_id_emits_warning`
  - [ ] `test_evidence_ref_deprecated_ref_id_byte_equal_to_pre_alpha`
  - [ ] `test_evidence_ref_deprecated_fact_digest_emits_warning`
  - [ ] `test_standalone_claim_without_resolver_raises_detached_error`
  - [ ] `test_standalone_evidence_ref_without_resolver_raises_detached_error`
- [ ] Existing test suite passes with `pytest -W "ignore::DeprecationWarning::factgraph"` (warnings are emitted but tests don't assert against them unless new)
- [ ] `docs/quickstart/evaluate_and_evidence.md` §2.3 / §2.4 deprecation banner added (1 line each)
- [ ] `src/factgraph/application/protocol/docs/README.md` (or equivalent module-docs entry) — Claim/EvidenceRef field set updated
- [ ] No edits outside `factgraph.application.protocol` (other than test updates + the quickstart doc banner)

## 8. Implementation Plan

Codex implementation order (each step ends with `pytest src/factgraph tests/factgraph -x` clean):

1. **[audit pin]** Read shipped `Claim` / `EvidenceRef` / `EvaluateRow` definitions and locate the `EvidenceRef.ref_id` derivation formula (audit Task A1 — confirms the exact bytes); record the formula in the audit log
2. **[audit pin]** Enumerate all `Claim(...)` / `EvidenceRef(...)` construction sites in `src/factgraph/` and `tests/` (audit Task A2); record full list in audit log
3. **[helper extraction]** Add `_compute_evidence_ref_id(...)` to `evaluate_result.py` using the formula from step 1; **add a unit test** verifying byte-equal output against a hand-picked pre-Slice-α fixture (capture one before applying any other change)
4. **[Claim refactor]** Replace `Claim` class definition with new shape (§5.1) — drop `name` / `arguments` frozen fields, add `_row_resolver` + 2 deprecated properties + `DetachedClaimError`
5. **[EvidenceRef refactor]** Replace `EvidenceRef` class definition (§5.2) — drop `row_id` / `result_id` / `ref_id` / `fact_digest` frozen fields, add `_row_resolver` + 4 deprecated properties + `DetachedEvidenceRefError`
6. **[EvaluateRow invariant reshape]** Update `EvaluateRow.__post_init__` (§5.3) — remove L135-138 cross-field assertions, add resolver injection
7. **[construction-site updates]** Update each site enumerated in step 2 to drop now-removed kwargs and rely on `EvaluateRow.__post_init__` for resolver wiring
8. **[new tests]** Add the 8 acceptance tests listed in §7
9. **[docs banner]** Add 1-line deprecation banner to `docs/quickstart/evaluate_and_evidence.md` §2.3 / §2.4
10. **[module docs sync]** Update `src/factgraph/application/protocol/docs/README.md` Claim/EvidenceRef field set entry (if such an entry exists; audit Task A3 confirms)
11. **[final verification]** Full `pytest` clean; manual grep `grep -nE 'Claim\(name=|EvidenceRef\((ref_id|result_id|row_id|fact_digest)=' src/ tests/` returns zero hits

## 9. Docs To Update

- `docs/quickstart/evaluate_and_evidence.md` §2.3 + §2.4 (deprecation banner only — full rewrite is Slice γ)
- `src/factgraph/application/protocol/docs/README.md` Claim / EvidenceRef field set entry (if present per audit Task A3)
- This blueprint's Outcome / Deviations section (filled at archive time)

## 10. Outcome / Deviations

To be filled at archive time:

- 最终落地结果:
- 与 blueprint 不同的地方:
- 为什么会有这些调整:
- 归档说明:
