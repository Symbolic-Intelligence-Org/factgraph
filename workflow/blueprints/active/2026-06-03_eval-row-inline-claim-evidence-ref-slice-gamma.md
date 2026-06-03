# Task Blueprint: Eval-row inline Claim/EvidenceRef Slice gamma — wrapper removal + row evidence fields

- Status: implemented
- Created: 2026-06-03
- Last Updated: 2026-06-03 (Step 4.8 closure)
- Owner: Claude/Codex cross-flip; tighter gates than Slice beta because this is a breaking SDK/protocol surface slice
- Fork base: `e2f7f655` (Slice beta Step 4.9 archive HEAD)
- Parent design: [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.3-§3.5 + §4.1 + §4.5 + §6 Slice gamma
- Predecessors:
  - [`2026-06-03_eval-result-flatten-slice-alpha.md`](../archive/2026-06-03_eval-result-flatten-slice-alpha.md) — deprecated `Claim.name` / `Claim.arguments` and 4 `EvidenceRef` mirror fields
  - [`2026-06-03_result-fingerprint-fold-slice-beta.md`](../archive/2026-06-03_result-fingerprint-fold-slice-beta.md) — folded result-level digest/version fields into `ResultFingerprint` + `engine_meta`
- Related Modules:
  - `src/factgraph/application/protocol/evaluate_result.py` (`Claim`, `EvidenceRef`, `EvaluateRow`, `Explanation`, row/evidence digest helpers)
  - `src/factgraph/application/protocol/__init__.py` (protocol re-exports)
  - `src/factgraph/sdk/__init__.py` (SDK public re-exports and `__all__` count)
  - `src/factgraph/sdk/store.py` (evaluate/explain row access paths, manual explanation metadata)
  - `src/service/runtime_v1.py` (EvaluateRow JSON projection; ledger `Claim` name collision must remain out of scope)
  - `tests/application/protocol/test_evaluate_result_dtos.py`
  - `tests/application/protocol/test_evaluate_result_digests.py`
  - `tests/sdk/test_evaluate_result_exports.py`
  - `tests/test_sdk_find_partial_identity.py` (SDK `__all__` guard)
- Related Docs:
  - [`docs/quickstart/evaluate_and_evidence.md`](../../../docs/quickstart/evaluate_and_evidence.md)
  - [`docs/official/kernel/quickstart/evidence.md`](../../../docs/official/kernel/quickstart/evidence.md)
  - [`docs/official/kernel/quickstart/namespace-map.md`](../../../docs/official/kernel/quickstart/namespace-map.md)
  - [`docs/official/kernel/quickstart/rules-and-inferences.md`](../../../docs/official/kernel/quickstart/rules-and-inferences.md)
  - [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml)
  - [`src/factgraph/audit/docs/02_evidence_graph.md`](../../../src/factgraph/audit/docs/02_evidence_graph.md)
  - [`src/factgraph/sdk/docs/01_concepts.en.md`](../../../src/factgraph/sdk/docs/01_concepts.en.md)
  - [`src/factgraph/sdk/docs/03_rules_and_inferences.en.md`](../../../src/factgraph/sdk/docs/03_rules_and_inferences.en.md)
  - [`src/factgraph/sdk/docs/04_api_surface.en.md`](../../../src/factgraph/sdk/docs/04_api_surface.en.md)
  - [`src/factgraph/sdk/docs/06_what_if_and_proof.en.md`](../../../src/factgraph/sdk/docs/06_what_if_and_proof.en.md)
  - [`src/service/docs/03_runtime_queries_policy.md`](../../../src/service/docs/03_runtime_queries_policy.md)
  - [`src/service/docs/06_frontend_integration.md`](../../../src/service/docs/06_frontend_integration.md)
- Audit Log:
  - [2026-06-03_eval-row-inline-claim-evidence-ref-slice-gamma.audit.md](./2026-06-03_eval-row-inline-claim-evidence-ref-slice-gamma.audit.md)

## 1. Problem

Slices alpha and beta removed the obvious duplication around `Claim.name` / `Claim.arguments`, `EvidenceRef.ref_id` / `result_id` / `row_id` / `fact_digest`, and `EvaluateResult` provenance digests. The current row surface still has two wrapper DTOs:

```text
EvaluateRow
├── row_id
├── bindings
├── raw_kind / bound
├── claim: Claim
│   ├── kind
│   ├── repr
│   └── digest
└── evidence_ref: EvidenceRef
    └── closed_head_digest
```

After Slice alpha, `Claim` now carries only `kind`, `repr`, and `digest` as active fields; `EvidenceRef` carries only `closed_head_digest` as an active field. The remaining wrapper shape still forces users to switch mental layers (`row.claim.digest`, `row.evidence_ref.closed_head_digest`) for row-owned data. It also keeps `Claim` and `EvidenceRef` as SDK/protocol exported classes even though parent design §3.4/§3.5 says those wrappers should disappear after the row becomes self-describing.

Slice gamma is the breaking wrapper-removal slice. It should flatten the useful row/evidence fields into `EvaluateRow`, update `Explanation` away from `Explanation.claim`, and decide the public compatibility strategy for `Claim` / `EvidenceRef` imports and `row.claim` / `row.evidence_ref` accessors.

## 2. Goals

- G1 — Add row-owned fields to `EvaluateRow`: `kind`, `digest`, and `closed_head_digest` per parent design §3.3.
- G2 — LOCKED by Step 4.4 PF-R1: do **not** add `EvaluateRow.repr`; derive compatibility `claim.repr` values through helper logic until Slice epsilon ships `Explanation.repr` + walker.
- G3 — LOCKED by Step 4.4 PF-R2: immediate in-process wrapper removal (C1). Remove protocol/SDK `Claim` / `EvidenceRef` exports, detached wrapper errors, and `row.claim` / `row.evidence_ref` properties.
- G4 — Remove active construction of `Claim(...)` and `EvidenceRef(...)` from production/test row construction paths after the locked policy is applied.
- G5 — Update `EvaluateRow` digest and evidence helper paths so `row.digest` equals former `row.claim.digest` and `row.closed_head_digest` equals former `row.evidence_ref.closed_head_digest`.
- G6 — LOCKED by Step 4.4 PF-R3: update `Explanation` from `claim: Claim | None` to a direct `row: EvaluateRow | None` reference per parent design §4.1, and remove redundant in-process `row_id` / `evidence_ref_id` / `raw_kind` / `bound` direct fields.
- G7 — LOCKED by Step 4.4 PF-R4: update service row/result JSON projection without confusing application-protocol `Claim` with ledger `factgraph.core.store.ledger.Claim`; preserve service JSON nested `claim` / `evidence_ref` dictionaries as wire compatibility while sourcing values from row-owned fields.
- G8 — Update SDK/protocol exports, `__all__` guards, docs, and tests so public shape reflects the wrapper-removal decision.
- G9 — Preserve D19/D17 compatibility contracts that remain meaningful: row digest bytes, closed-head digest, result/evidence metadata identity, and cross-process `(result_id, row_id)` row handle semantics.
- G10 — Keep Q-PR1 sacred paths 0-diff and preserve dirty baseline entries.

## 3. Non-goals

- N1 — Do not implement query-style `head.id` / predicate-id decoupling (Slice delta).
- N2 — Do not simplify `row.bindings` into `{port_name: term}` (Slice zeta).
- N3 — Do not implement EvidenceGraph 3-tier hierarchy (Slice eta).
- N4 — Do not implement `Explanation.repr` evidence walker (Slice epsilon).
- N5 — Do not change `ResultFingerprint` / `engine_meta` from Slice beta except access-path updates required by this slice.
- N6 — Do not alter ledger-layer `factgraph.core.store.ledger.Claim`; same-name ledger Claim remains a separate layer. This slice resolves the cross-layer `Claim` name friction described in [`rule-namespace-rulespec-redesign.zh.md`](../../design/design-points/active/rule-namespace-rulespec-redesign.zh.md) §3.5/§4.6 via protocol-wrapper removal, not via that design-point's `ResultClaim` rename path.
- N7 — Do not change service HTTP wire shape. Step 4.4 PF-R4 locks preservation of nested service JSON `claim` / `evidence_ref` dictionaries as compatibility payloads, even though in-process DTO wrappers are removed.
- N8 — Do not touch Q-PR1 sacred paths: `write_protocol.py`, `ledger.py`, `_builders.py`, `adapters/pyreason/`, `application/accept.py`.
- N9 — Do not touch accumulated dirty baseline files.
- N10 — Do not execute release scripts, push branches, or touch sacred master.
- N11 — Do not decide cross-slice public compatibility beyond this wrapper-removal slice unless escalated to a separate decision doc.

## 4. Current Source Anchors (Step 4.1 Fresh Read)

- `src/factgraph/application/protocol/evaluate_result.py:95` — `class Claim`
- `src/factgraph/application/protocol/evaluate_result.py:127` — `class EvidenceRef`
- `src/factgraph/application/protocol/evaluate_result.py:165-171` — `EvaluateRow` currently carries `claim: Claim` and `evidence_ref: EvidenceRef`
- `src/factgraph/application/protocol/evaluate_result.py:352-355` — `Explanation` currently carries `claim: Claim | None`
- `src/factgraph/application/protocol/evaluate_result.py:589` / `:612` / `:1317` / `:1411` — active `row.evidence_ref.closed_head_digest` consumers
- `src/factgraph/sdk/__init__.py:35-41` + `:99-105` — SDK exports `Claim`, `EvidenceRef`, `EvaluateRow`, `Explanation`, `ResultFingerprint`
- `src/factgraph/application/protocol/__init__.py:20-28` + `:163-171` — protocol exports `Claim`, `EvidenceRef`, detached errors, `EvaluateRow`, `Explanation`
- `tests/sdk/test_evaluate_result_exports.py:8-26` — SDK export assertions for `Claim` and `EvidenceRef`
- `tests/application/protocol/test_evaluate_result_dtos.py:279-304` — post-Slice-alpha field shape + detached deprecated property tests
- `docs/quickstart/evaluate_and_evidence.md:155-268` — current public docs still explain `EvaluateRow.claim`, `Claim`, and `EvidenceRef`
- `src/service/runtime_v1.py:21` / `:76` — service imports protocol `EvaluateRow`/`ResultFingerprint` and ledger `Claim`; Step 4.3 must separate those layers precisely

## 5. Proposed Shape (Locked by Step 4.4)

### 5.1 EvaluateRow target

Draft target from parent design §3.3:

```python
@dataclass(frozen=True)
class EvaluateRow:
    row_id: str
    bindings: Mapping[str, object]
    kind: RowKind
    digest: str
    closed_head_digest: str
    raw_kind: Literal["probabilistic", "possibilistic"] | None
    bound: tuple[float, float] | None
    _result_resolver: Callable[[], EvaluateResult] | None = field(default=None, compare=False, repr=False)
```

Step 4.4 PF-R1 locks Option R1:

- `EvaluateRow` gets `kind`, `digest`, and `closed_head_digest`.
- `EvaluateRow` does **not** get `repr`.
- Former `Claim.repr` compatibility values are derived where needed by a helper such as `_claim_repr_for_row_result(row, result)` from the same source inputs currently used by production construction (`result.head.id` / effective claim name + `row.bindings`).
- Slice epsilon owns the user-facing `Explanation.repr` field and evidence walker.

Rejected alternatives:

- R2 (`EvaluateRow.repr` now) — rejected because it moves a view/rendering concern onto the row data DTO and contradicts parent design §3.3/§3.7.
- R3 (`row.repr` temporary compatibility) — rejected because it creates a confusing one-release view field without the walker.

### 5.2 Claim / EvidenceRef compatibility strategy

Step 4.4 PF-R2 locks C1 immediate in-process wrapper removal:

- remove in-process protocol classes `Claim` and `EvidenceRef`;
- remove SDK/protocol exports for `Claim`, `EvidenceRef`, `DetachedClaimError`, and `DetachedEvidenceRefError`;
- remove `row.claim` and `row.evidence_ref` compatibility properties;
- update export guards: `tests/test_sdk_find_partial_identity.py` currently expects `len(sdk_module.__all__) == 65`; expected count is **61** after the four exported names are removed, unless Step 4.7 introduces another intentional replacement symbol.

Rejected alternatives:

- C2 (deprecated SDK/protocol aliases) — rejected because the active consumer surface is bounded and the slice purpose is wrapper removal.
- C3 (deprecated `row.claim` / `row.evidence_ref` properties) — rejected because it preserves the wrapper abstraction after the removal slice.

### 5.3 Explanation shape

Parent design §4.1 target for the eventual post-gamma/epsilon shape:

```python
@dataclass(frozen=True)
class Explanation:
    status: ExplanationStatus
    row: EvaluateRow | None
    evidence: EvidenceGraph | None
    result_id: str | None
    failure_class: ExplanationFailureClass | None
    checked_scope: Mapping[str, Any] | None
    suggested_next_steps: tuple[str, ...]
    errors: tuple[ErrorDTO, ...]
    warnings: tuple[WarningDTO, ...]
```

Step 4.4 PF-R3 expands and locks the data-bearing part of this change: `Explanation.claim` becomes a direct `Explanation.row: EvaluateRow | None` reference, not a set of inlined `row_id` / `row_bindings` / `row_digest` fields. The in-process `Explanation` also drops redundant direct fields that are now available through `row`: `row_id`, `evidence_ref_id`, `raw_kind`, and `bound`.

`Explanation.repr` is **not** added in gamma. The field and the walker ship together in Slice epsilon; adding a field that always returns `None` would create a half-implemented user-facing surface.

Cross-process semantics: an `Explanation` remains standalone-serializable through its inline `row` plus `result_id`; callers that need to re-locate the row use `(result_id, row.row_id)` per parent design §4.5.

### 5.4 Row digest and evidence identity

The following identities remain locked after Step 4.4 preflight amendment:

- `row.digest` == former `row.claim.digest`
- `row.closed_head_digest` == former `row.evidence_ref.closed_head_digest`
- `evidence_ref_id_for(result_id, row_id, row.digest, row.closed_head_digest)` remains bit-for-bit compatible for any compatibility path needing old `ref_id`
- cross-process row handle is `(result_id, row_id)` per parent design §4.5

### 5.5 Service wire

Service serializer keeps flat/nested JSON keys for wire compatibility while reading new row fields internally. Step 4.4 PF-R4 locks the split:

- in-process application protocol removes `Claim` / `EvidenceRef` wrappers;
- service JSON still emits nested `"claim": {...}` and `"evidence_ref": {...}` dictionaries;
- `_evaluate_row_to_dict(...)` must contain no `row.claim` / `row.evidence_ref` reads after implementation;
- values for the wire dictionaries are computed from `row.kind`, `row.digest`, `row.closed_head_digest`, `result.result_id`, `row.row_id`, `result.head.id`, and helper-derived arguments/repr/ref-id.

### 5.6 SDK and protocol exports

Locked exported symbol change:

- remove `Claim`, `EvidenceRef`, `DetachedClaimError`, and `DetachedEvidenceRefError` from protocol exports and SDK exports;
- update SDK export tests to assert removal or absence;
- update `tests/test_sdk_find_partial_identity.py` exact `__all__` count from 65 to 63. Step 4.7 implementation corrected Step 4.4 PF-r2: the SDK only exported `Claim` and `EvidenceRef`; `DetachedClaimError` and `DetachedEvidenceRefError` were protocol exports only, so SDK count drops by 2, not 4.

### 5.7 Ledger Claim carve-outs (PF-r1)

The following are **not** protocol wrapper hits and must remain out of scope:

| Area | Examples | Why excluded |
| --- | --- | --- |
| Core ledger/write path | `src/factgraph/core/evidence/write_protocol.py`, `src/factgraph/core/store/database.py`, `src/factgraph/core/store/ledger.py` | Q-PR1 / ledger `Claim` shape (`asrt_id`, `pred_id`, `e_ref`, `rest_terms`) |
| Service candidate payloads | `src/service/runtime_v1.py` ledger `Claim` import and `_candidate_payload_from_claim(...)` | service reads ledger claims for candidate payloads; not application-protocol wrappers |
| Ledger/application tests | annotation store, walker views, ledger concurrency, retract/identity guard tests | test ledger Claim behavior, not evaluate-result Claim wrappers |
| Ledger docs | `docs/quickstart/data_model.md`, read/write/entity docs | document ledger Claims and identity/existence Claims |

### 5.8 Step 4.6.5 docs cascade extension (N-1)

Mandatory pre-impl grep confirmed no new production-code scope beyond Step 4.4 PF-R1/PF-R2/PF-R3/PF-R4. It did surface additional active documentation that references protocol `Claim` / `EvidenceRef` / `row.claim` / `row.evidence_ref` shapes and must be included in the Step 4.7 docs cascade:

- `docs/api/openapi.yaml` — service wire payload schema keeps nested `claim` / `evidence_ref` keys while data source changes.
- `docs/official/kernel/quickstart/rules-and-inferences.md` — row/claim wording needs migration to row-owned fields.
- `src/factgraph/audit/docs/02_evidence_graph.md` — EvidenceRef/ref-id wording needs migration to row-owned digest/closed-head digest language.
- `src/factgraph/sdk/docs/01_concepts.en.md`, `src/factgraph/sdk/docs/04_api_surface.en.md`, and `src/factgraph/sdk/docs/06_what_if_and_proof.en.md` — SDK result-row surface needs wrapper-removal wording.
- `src/service/docs/06_frontend_integration.md` — frontend integration sample keeps wire-compatible nested dictionaries but must not imply in-process wrappers remain.

These docs are scoped as N-1 because they are documentation cascade only. They do not add implementation authority, do not change service wire compatibility, and do not alter PF-r1 ledger Claim carve-outs.

## 6. Cadence Path Locks

- Slice gamma uses the full tight cadence, not Slice beta fast-track. Reason: public SDK exported classes, `Explanation` shape, docs, service projection, and cross-process identity are all affected.
- Stage 0 source audit is folded into this Step 4.1 draft, following Slice alpha/beta precedent, but Step 4.3 independent preflight is mandatory.
- Step 4.2 review must specifically test the parent-design conflict around `repr`, the SDK export strategy, and service wire compatibility.
- Step 4.6.5 pre-impl grep is mandatory because this is a remove/drop slice over shipped DTO classes.
- Step 4.7 should use a multi-commit pattern if implementation crosses protocol + SDK/export + service + docs boundaries.

## 7. Acceptance Criteria (Draft)

- [x] Step 4.4 PF-R1 has locked no `EvaluateRow.repr`; former `Claim.repr` values are helper-derived compatibility values only.
- [x] Step 4.3 preflight has enumerated all `Claim` / `EvidenceRef` imports, constructors, row accessors, and docs references across `src/`, `tests/`, and active docs.
- [x] `EvaluateRow` exposes `kind`, `digest`, and `closed_head_digest` directly.
- [x] Production row construction no longer needs active `Claim(...)` or `EvidenceRef(...)` wrapper construction.
- [x] `Explanation` no longer requires `claim: Claim | None`; it directly holds `row: EvaluateRow | None` per parent design §4.1 and removes redundant direct `row_id` / `evidence_ref_id` / `raw_kind` / `bound` fields.
- [x] Service runtime reads row-owned fields directly, contains no `row.claim` / `row.evidence_ref` reads, and still emits wire-compatible nested `claim` / `evidence_ref` dictionaries.
- [x] SDK/protocol export tests reflect immediate wrapper removal; `sdk.__all__` expected count is 63 after Step 4.7 corrected PF-r2's SDK export overcount.
- [x] Step 4.7 docs cascade updates all Related Docs including Step 4.6.5 N-1 additions, while preserving ledger-Claim docs outside protocol-wrapper scope.
- [x] D19/D17 identity checks pass: row digest, closed-head digest, and any compatibility `ref_id` formula remain stable where required.
- [x] Q-PR1 5 sacred paths remain 0-diff vs `4c472b50`.
- [x] Dirty baseline entries are preserved.

## 8. Implementation Plan

1. Step 4.2 — Draft review + tightening on blueprint branch. Required focus: `repr` decision, SDK export strategy, service wire strategy, `Explanation` cascade, parent-design line conflicts.
2. Step 4.3 — Independent preflight branch `v0.2.0-eval-row-inline-claim-evidence-ref-preflight-2026-06-03`; produce 5-bucket finding table.
3. Step 4.4 — Fold preflight Required/Recommended findings into blueprint branch.
4. Step 4.5 — Self-check for stale boilerplate, open-question disposition, and G/N/acceptance consistency.
5. Step 4.6 — Scope freeze (`draft` → `scoped`).
6. Step 4.6.5 — Mandatory pre-impl grep over deletion targets:
   - `\bClaim\b` / `\bEvidenceRef\b` imports/constructors, bucketed as protocol-wrapper vs ledger Claim false positives
   - `\.claim\b` / `\.evidence_ref\b`
   - `claim\.kind|claim\.repr|claim\.digest`
   - `evidence_ref\.closed_head_digest`
   - `Explanation\(.*claim=`
   - `row_id=|evidence_ref_id=|raw_kind=|bound=` within `Explanation(...)` construction sites
7. Step 4.7 — Implementation on `v0.2.0-impl-eval-row-inline-claim-evidence-ref-2026-06-03`, likely multi-commit:
   - protocol DTO reshape + construction paths
   - SDK/protocol export + service wire + tests
   - docs cascade, including Step 4.6.5 N-1 active docs additions
8. Step 4.8 — Closure (`scoped` → `implemented`) with Outcome / Deviations.
9. Step 4.9 — Archive blueprint/audit and preflight artifact; update archive inventory.

## 9. Pre-Impl Audit Tasks for Step 4.3

- A1 — Enumerate active constructors:
  - `rg -n 'Claim\(|EvidenceRef\(' src/factgraph src/service tests docs`
- A2 — Enumerate accessors:
  - `rg -n '\.claim\b|\.evidence_ref\b|claim\.kind|claim\.repr|claim\.digest|evidence_ref\.closed_head_digest' src/factgraph src/service tests docs`
- A3 — Enumerate imports/exports:
  - `rg -n 'Claim|EvidenceRef|DetachedClaimError|DetachedEvidenceRefError' src/factgraph/application/protocol/__init__.py src/factgraph/sdk/__init__.py tests docs`
- A4 — Verify `Explanation` cascade:
  - `rg -n 'Explanation\(|\.claim\b|claim:' src/factgraph src/service tests docs`
- A5 — Verify service layer name collision:
  - distinguish `factgraph.application.protocol.evaluate_result.Claim` from `factgraph.core.store.ledger.Claim`
- A6 — Verify digest/ref-id compatibility:
  - re-read `claim_digest_for(...)`, `closed_head_digest_for(...)`, `evidence_ref_id_for(...)`, row digest helper, evidence metadata builder
- A7 — Verify docs cascade:
  - quickstart, official kernel quickstart, SDK docs, service policy/frontend docs, audit docs, OpenAPI schema, namespace-map
- A8 — Verify SDK `__all__` and import count impacts.

## 10. Outcome / Deviations

Implemented in `5c9447e9` on `v0.2.0-impl-eval-row-inline-claim-evidence-ref-2026-06-03`.

### Outcome

| Area | Result |
| --- | --- |
| Protocol DTO shape | `Claim` / `EvidenceRef` in-process wrappers removed; `EvaluateRow` owns `kind`, `digest`, and `closed_head_digest`. |
| Explanation shape | `Explanation` now carries `row: EvaluateRow | None` and no longer exposes direct `claim`, `row_id`, `evidence_ref_id`, `raw_kind`, or `bound` fields. |
| Service wire | `src/service/runtime_v1.py` no longer reads `row.claim` / `row.evidence_ref` while preserving nested JSON `claim` / `evidence_ref` compatibility dictionaries. |
| SDK/protocol exports | `Claim` and `EvidenceRef` removed from SDK exports; protocol exports also remove detached wrapper errors. `sdk.__all__` is now 63. |
| Docs cascade | Active quickstart, official, SDK, service, audit, and OpenAPI docs updated, including Step 4.6.5 N-1 additions. |

### Verification

- `compileall` over changed code/test modules passed.
- Focused protocol/SDK/service test cohorts passed.
- Full test suite passed: `2454 passed, 32 skipped, 1044 subtests passed`.
- Q-PR1 5 sacred paths remain 0-diff vs `4c472b50`.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline entries remain preserved.

### Deviations

- Step 4.7 corrected Step 4.4 PF-r2's SDK export-count assumption. The SDK exported only `Claim` and `EvidenceRef`, not detached wrapper errors, so the final SDK `__all__` count is 65 → 63 rather than 65 → 61.
- Step 4.7 surfaced one additional docs cascade file, `src/factgraph/sdk/docs/06_what_if_and_proof.en.md`, beyond the Step 4.6.5 N-1 list. The change was docs-only and aligned with the same wrapper-removal cascade, so it was folded into the implementation and recorded here rather than split into a new scope amendment.
- No service wire-shape deviation: nested JSON `claim` / `evidence_ref` dictionaries remain compatibility payloads even though in-process wrappers were removed.

## 11. Deferred / Carry-Forward

- D1 — Query-style head/predicate decoupling stays in Slice delta.
- D2 — Bindings shape simplification stays in Slice zeta.
- D3 — EvidenceGraph layered hierarchy stays in Slice eta.
- D4 — `Explanation.repr` field + walker stay in Slice epsilon; gamma must not add a placeholder field that always returns `None`.
- D5 — Any decision to keep long-term `Claim` / `EvidenceRef` compatibility aliases beyond one release cycle requires a separate decision record.
