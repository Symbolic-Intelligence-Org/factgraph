# Task Blueprint: Eval-row inline Claim/EvidenceRef Slice gamma — wrapper removal + row evidence fields

- Status: draft
- Created: 2026-06-03
- Last Updated: 2026-06-03 (Step 4.1 draft)
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
  - [`src/factgraph/sdk/docs/03_rules_and_inferences.en.md`](../../../src/factgraph/sdk/docs/03_rules_and_inferences.en.md)
  - [`src/service/docs/03_runtime_queries_policy.md`](../../../src/service/docs/03_runtime_queries_policy.md)
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
- G2 — Resolve the `repr` question before implementation: user-requested gamma scope mentions `repr` flattening, while parent design §3.3 / §3.7 says `repr` is view-level and should not live on `EvaluateRow`.
- G3 — Remove or deprecate `Claim` and `EvidenceRef` wrapper classes according to a locked SDK compatibility policy.
- G4 — Remove active construction of `Claim(...)` and `EvidenceRef(...)` from production/test row construction paths after the locked policy is applied.
- G5 — Update `EvaluateRow` digest and evidence helper paths so `row.digest` equals former `row.claim.digest` and `row.closed_head_digest` equals former `row.evidence_ref.closed_head_digest`.
- G6 — Update `Explanation` from `claim: Claim | None` to the locked parent-design shape (`row: EvaluateRow | None` preferred), including validation and serialization behavior.
- G7 — Update service row/result JSON projection without confusing application-protocol `Claim` with ledger `factgraph.core.store.ledger.Claim`.
- G8 — Update SDK/protocol exports, `__all__` guards, docs, and tests so public shape reflects the wrapper-removal decision.
- G9 — Preserve D19/D17 compatibility contracts that remain meaningful: row digest bytes, closed-head digest, result/evidence metadata identity, and cross-process `(result_id, row_id)` row handle semantics.
- G10 — Keep Q-PR1 sacred paths 0-diff and preserve dirty baseline entries.

## 3. Non-goals

- N1 — Do not implement query-style `head.id` / predicate-id decoupling (Slice delta).
- N2 — Do not simplify `row.bindings` into `{port_name: term}` (Slice zeta).
- N3 — Do not implement EvidenceGraph 3-tier hierarchy (Slice eta).
- N4 — Do not implement `Explanation.repr` evidence walker (Slice epsilon).
- N5 — Do not change `ResultFingerprint` / `engine_meta` from Slice beta except access-path updates required by this slice.
- N6 — Do not alter ledger-layer `factgraph.core.store.ledger.Claim`; same-name ledger Claim remains a separate layer.
- N7 — Do not change service HTTP wire shape unless Step 4.3 explicitly locks wire compatibility updates.
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

## 5. Proposed Shape (Draft, Not Yet Locked)

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

Open tension: user prompt includes `repr` flattening, but parent design says `repr` is view/presentation and should move to `Explanation` / Slice epsilon rather than become `EvaluateRow.repr`. Step 4.2/4.3 must lock one of:

- Option R1 — **No `EvaluateRow.repr` in Slice gamma** (parent design default). Keep only `kind` / `digest` / `closed_head_digest` on row; docs say `Claim.repr` compatibility is removed/deferred to Slice epsilon.
- Option R2 — **Add `EvaluateRow.repr` now** (user prompt literal scope). Requires explicit rationale why row now owns a view field despite parent design §3.7.
- Option R3 — **Temporary deprecated `row.repr` compatibility only**. Higher confusion risk; likely not preferred unless preflight finds heavy user-facing docs/tests depend on `Claim.repr`.

Default draft bias: **R1**, because it preserves the parent design boundary and keeps Slice epsilon meaningful.

### 5.2 Claim / EvidenceRef compatibility strategy

Open Q: "wrapper class撤销" can mean several levels:

- Option C1 — Remove SDK/protocol exports immediately; no `Claim` / `EvidenceRef` import compatibility. Cleanest, largest breaking change.
- Option C2 — Keep deprecated SDK/protocol aliases or compatibility proxy classes for one release cycle. Smaller break, but contradicts "wrapper class removal" unless the alias is clearly documented as compatibility-only.
- Option C3 — Keep `row.claim` / `row.evidence_ref` deprecated properties returning lightweight view objects while removing constructor use. Highest backward compatibility, but risks keeping wrapper abstraction alive.

Step 4.3 preflight must enumerate active import/access consumers before locking. Default draft bias: **C2 or C3 until preflight proves import/access surface is small enough for C1**.

### 5.3 Explanation shape

Parent design §4.1 target:

```python
@dataclass(frozen=True)
class Explanation:
    status: ExplanationStatus
    row: EvaluateRow | None
    evidence: EvidenceGraph | None
    repr: tuple[str, ...] | None
    result_id: str | None
    failure_class: ExplanationFailureClass | None
    checked_scope: Mapping[str, Any] | None
    suggested_next_steps: tuple[str, ...]
    errors: tuple[ErrorDTO, ...]
    warnings: tuple[WarningDTO, ...]
```

Slice gamma should update `Explanation.claim` to `Explanation.row` only if Step 4.3 confirms the cascade is bounded. If `Explanation.repr` walker scope leaks into Slice epsilon/eta, gamma should keep `repr` as deferred placeholder and not implement the walker.

### 5.4 Row digest and evidence identity

The following identities must remain true unless Step 4.3 raises a Required contrary finding:

- `row.digest` == former `row.claim.digest`
- `row.closed_head_digest` == former `row.evidence_ref.closed_head_digest`
- `evidence_ref_id_for(result_id, row_id, row.digest, row.closed_head_digest)` remains bit-for-bit compatible for any compatibility path needing old `ref_id`
- cross-process row handle is `(result_id, row_id)` per parent design §4.5

### 5.5 Service wire

Service serializer likely needs to keep flat JSON keys for wire compatibility while reading new row fields internally. Step 4.3 must inspect `_evaluate_row_to_dict` / `_evaluate_result_to_dict` and distinguish:

- application-protocol `EvaluateRow` fields this slice changes
- ledger `Claim` objects in service candidate paths that are **not** this protocol wrapper
- wire payload fields that should remain stable even if in-process DTOs flatten

### 5.6 SDK and protocol exports

Expected exported symbol change is a central risk:

- If `Claim` / `EvidenceRef` are removed from SDK `__all__`, update `tests/test_sdk_find_partial_identity.py` count and public import docs intentionally.
- If compatibility aliases remain, tests must assert deprecation warnings or compatibility-only status.
- `DetachedClaimError` / `DetachedEvidenceRefError` likely disappear or become compatibility-only depending on C1/C2/C3.

## 6. Cadence Path Locks

- Slice gamma uses the full tight cadence, not Slice beta fast-track. Reason: public SDK exported classes, `Explanation` shape, docs, service projection, and cross-process identity are all affected.
- Stage 0 source audit is folded into this Step 4.1 draft, following Slice alpha/beta precedent, but Step 4.3 independent preflight is mandatory.
- Step 4.2 review must specifically test the parent-design conflict around `repr`, the SDK export strategy, and service wire compatibility.
- Step 4.6.5 pre-impl grep is mandatory because this is a remove/drop slice over shipped DTO classes.
- Step 4.7 should use a multi-commit pattern if implementation crosses protocol + SDK/export + service + docs boundaries.

## 7. Acceptance Criteria (Draft)

- [ ] Step 4.2 review has locked the `repr` handling decision (R1/R2/R3).
- [ ] Step 4.3 preflight has enumerated all `Claim` / `EvidenceRef` imports, constructors, row accessors, and docs references across `src/`, `tests/`, and active docs.
- [ ] `EvaluateRow` exposes `kind`, `digest`, and `closed_head_digest` directly.
- [ ] Production row construction no longer needs active `Claim(...)` or `EvidenceRef(...)` wrapper construction after the locked compatibility policy is applied.
- [ ] `Explanation` no longer requires `claim: Claim | None`; new row/inline shape is validated and documented.
- [ ] Service runtime reads row-owned fields directly while preserving any locked wire-compatible payload keys.
- [ ] SDK/protocol export tests reflect the locked `Claim` / `EvidenceRef` compatibility policy.
- [ ] D19/D17 identity checks pass: row digest, closed-head digest, and any compatibility `ref_id` formula remain stable where required.
- [ ] Q-PR1 5 sacred paths remain 0-diff vs `4c472b50`.
- [ ] Dirty baseline entries are preserved.

## 8. Implementation Plan

1. Step 4.2 — Draft review + tightening on blueprint branch. Required focus: `repr` decision, SDK export strategy, service wire strategy, `Explanation` cascade, parent-design line conflicts.
2. Step 4.3 — Independent preflight branch `v0.2.0-eval-row-inline-claim-evidence-ref-preflight-2026-06-03`; produce 5-bucket finding table.
3. Step 4.4 — Fold preflight Required/Recommended findings into blueprint branch.
4. Step 4.5 — Self-check for stale boilerplate, open-question disposition, and G/N/acceptance consistency.
5. Step 4.6 — Scope freeze (`draft` → `scoped`).
6. Step 4.6.5 — Mandatory pre-impl grep over deletion targets:
   - `\bClaim\b` / `\bEvidenceRef\b` imports/constructors
   - `\.claim\b` / `\.evidence_ref\b`
   - `claim\.kind|claim\.repr|claim\.digest`
   - `evidence_ref\.closed_head_digest`
   - `Explanation\(.*claim=`
7. Step 4.7 — Implementation on `v0.2.0-impl-eval-row-inline-claim-evidence-ref-2026-06-03`, likely multi-commit:
   - protocol DTO reshape + construction paths
   - SDK/protocol export + service wire + tests
   - docs cascade
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
  - quickstart, official kernel quickstart, SDK docs, service policy docs, namespace-map
- A8 — Verify SDK `__all__` and import count impacts.

## 10. Outcome / Deviations

Pending.

## 11. Deferred / Carry-Forward

- D1 — Query-style head/predicate decoupling stays in Slice delta.
- D2 — Bindings shape simplification stays in Slice zeta.
- D3 — EvidenceGraph layered hierarchy stays in Slice eta.
- D4 — `Explanation.repr` walker stays in Slice epsilon unless the `repr` open question is explicitly escalated.
- D5 — Any decision to keep long-term `Claim` / `EvidenceRef` compatibility aliases beyond one release cycle requires a separate decision record.
