# Preflight Audit: Eval-row inline Claim/EvidenceRef Slice gamma

- Branch: `v0.2.0-eval-row-inline-claim-evidence-ref-preflight-2026-06-03`
- Forked from blueprint HEAD: `1c65fafd`
- Blueprint: [`workflow/blueprints/active/2026-06-03_eval-row-inline-claim-evidence-ref-slice-gamma.md`](../../blueprints/active/2026-06-03_eval-row-inline-claim-evidence-ref-slice-gamma.md)
- Parent design: [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md)
- Method: Step 4.3 independent preflight; Rule 1 fresh reads for A1-A8; no source edits

## 1. Executive Finding Table

| Bucket | Count | Findings |
| --- | ---: | --- |
| Required | 4 | PF-R1 `repr` stays out of `EvaluateRow`; PF-R2 C1 immediate wrapper removal is viable and should be locked; PF-R3 `Explanation.row` direct-reference cascade is required; PF-R4 service JSON keeps wire-compatible nested `claim` / `evidence_ref` while in-process wrappers disappear |
| Recommended | 2 | PF-r1 ledger `Claim` false-positive carve-outs; PF-r2 SDK/protocol export count and detached-error removal must be explicit |
| Verified | 8 | PF-v1..PF-v8 source anchors, Q-PR1, fork, parent design tension, docs/test scope |
| Scoped-detail | 2 | PF-s1 implementation ordering; PF-s2 docs wording split between in-process DTO and service wire |
| Abandonment | 0 | No abandonment blocker |

Healthy distribution after Step 4.4 fold should be 4R / 2r / 8v / 2s / 0A. The Required count is at the top of the healthy band because gamma is the first slice that removes exported SDK/protocol DTO names.

## 2. Required Findings

### PF-R1 — `Claim.repr` does not become `EvaluateRow.repr`

Preflight confirms the draft's R1 default should be locked.

Source reads:

- `src/factgraph/application/protocol/evaluate_result.py:745-752` builds `Claim(repr=f"{effective_claim_name}{dict(bindings)!r}", digest=...)`
- `src/factgraph/application/protocol/evaluate_result.py:606-612` includes `row.claim.repr` in row digest canonical bytes and row/evidence metadata
- `src/factgraph/application/protocol/evaluate_result.py:1027` / `:1161` use `row.claim.repr` as `EvidenceNode.value_summary`
- `src/service/runtime_v1.py:2473-2487` serializes nested service JSON `claim.repr`

Conclusion:

- `repr` is a compatibility/rendering value derived from `(result.head.id, row.bindings)`, not a fundamental row datum.
- Adding `EvaluateRow.repr` would contradict parent design §3.3/§3.7 and create a view field on the row.
- Step 4.7 should add helper(s) such as `_claim_repr_for_row_result(row, result)` and use them for digest/wire/metadata compatibility, but **not** add a row field.

Step 4.4 blueprint amendment:

- Lock Option R1.
- Remove R2/R3 as implementation candidates unless a future Slice epsilon revisits view rendering.
- Acceptance: no `EvaluateRow.repr` field after implementation; old `Claim.repr` references are replaced by helper-derived compatibility values or removed.

### PF-R2 — C1 immediate wrapper removal is viable and should be locked

A1/A2/A3 grep found protocol-wrapper usage is bounded:

Active protocol wrapper construction:

- production pair: `src/factgraph/application/protocol/evaluate_result.py:745-752`
- protocol fixture pair: `tests/application/protocol/test_evaluate_result_dtos.py:96-104`
- detached-property fixture pair: `tests/application/protocol/test_evaluate_result_dtos.py:283-304`

Active protocol-wrapper exports/import assertions:

- `src/factgraph/application/protocol/__init__.py:20-28` + `:163-171`
- `src/factgraph/sdk/__init__.py:35-41` + `:99-105`
- `tests/sdk/test_evaluate_result_exports.py:8-26`

Active `row.claim` / `row.evidence_ref` consumers are concentrated in:

- `src/factgraph/application/protocol/evaluate_result.py`
- `src/service/runtime_v1.py:2473-2487`
- `src/factgraph/sdk/store.py:2500-2515`
- `tests/application/protocol/test_evaluate_result_dtos.py`
- `tests/sdk/test_rule_expr_evaluate.py:225-228`
- `tests/test_pyreason_e2e.py:139-142`
- `tests/test_problog_engine_eval.py:96`
- public docs listed in §4

Conclusion:

- C2/C3 would prolong the wrapper abstraction after the slice whose purpose is wrapper removal.
- The active source/test/docs surface is large enough to require care but small enough to migrate directly.
- Lock **C1 immediate removal** for in-process protocol/SDK shape:
  - no exported protocol `Claim` / `EvidenceRef`
  - no exported SDK `Claim` / `EvidenceRef`
  - no `DetachedClaimError` / `DetachedEvidenceRefError`
  - no `row.claim` / `row.evidence_ref` compatibility properties

Step 4.4 blueprint amendment:

- Promote C1 from candidate to locked outcome.
- Move C2/C3 to rejected/deferred alternatives.
- Add explicit SDK `__all__` count update expectation: current 65 should decrease by 4 if `Claim`, `EvidenceRef`, `DetachedClaimError`, and `DetachedEvidenceRefError` are removed. Step 4.7 must verify exact count after implementation.

### PF-R3 — `Explanation.row` cascade is required and larger than the draft describes

Fresh reads:

- `src/factgraph/application/protocol/evaluate_result.py:352-389` currently validates `claim`, `row_id`, `evidence_ref_id`, `raw_kind`, and `bound`
- `src/factgraph/application/protocol/evaluate_result.py:779-837` constructs `Explanation(...)` in four live-row paths
- `src/factgraph/sdk/store.py:2493-2515` constructs manual explain fallback/wrapper `Explanation(...)`
- `tests/application/protocol/test_evaluate_result_dtos.py:773-845` has multiple direct `Explanation(...)` fixtures
- `docs/quickstart/evaluate_and_evidence.md:298-386` documents `Explanation.claim`, `row_id`, `evidence_ref_id`, `raw_kind`, and `bound`
- `docs/official/kernel/quickstart/evidence.md:206-226` documents `claim` in `Explanation`

Conclusion:

- Gamma should not merely rename `claim` to `row`; it should make `row` the carrier for `row_id`, `raw_kind`, `bound`, digest, and closed-head evidence fields.
- Parent design §4.1 direct-reference shape should be locked: `Explanation.row: EvaluateRow | None`.
- Top-level `row_id`, `evidence_ref_id`, `raw_kind`, and `bound` become redundant. If kept, they must be explicitly wire-compat only; default preflight recommendation is to remove them from in-process `Explanation`.

Step 4.4 blueprint amendment:

- Add Required lock: in-process `Explanation` holds `row`, `evidence`, `result_id`, failure/errors fields; no `claim`, `row_id`, `evidence_ref_id`, `raw_kind`, or `bound` direct fields unless preflight review finds a separate service-wire need.
- Add acceptance: passed explanations require `row` and `evidence`; failed explanations may carry `row` for stale-row / row-not-in-result paths, or `None` for closed-head-false paths.

### PF-R4 — Service JSON wire must stay flat/nested for compatibility, while in-process wrappers disappear

Fresh reads:

- `src/service/runtime_v1.py:2447-2464` serializes flat result fields from Slice beta's `fingerprint`/`engine_meta`
- `src/service/runtime_v1.py:2468-2489` serializes rows with nested `"claim": {...}` and `"evidence_ref": {...}` dictionaries
- `src/service/runtime_v1.py:76` imports ledger `Claim` for candidate payload paths; this is unrelated to protocol wrapper removal

Conclusion:

- Do **not** remove service JSON keys just because in-process protocol wrappers disappear.
- Service wire can preserve nested `claim` / `evidence_ref` payloads by computing values from `row.kind`, `row.digest`, `row.closed_head_digest`, `result.result_id`, `row.row_id`, `result.head.id`, and `_claim_arguments_for_row(row)`.
- This mirrors Slice beta: service wire stayed flat while in-process `EvaluateResult` folded fields.

Step 4.4 blueprint amendment:

- Add explicit N/Goal split: in-process DTO shape changes; service JSON wire keys remain unless a separate wire-breaking decision is made.
- Add acceptance: `_evaluate_row_to_dict(...)` contains no `row.claim` / `row.evidence_ref` reads but still emits compatible nested dictionaries.

## 3. Recommended Findings

### PF-r1 — Ledger `Claim` false positives must be carved out explicitly

A1/A3 grep produced many `Claim(...)` / `Claim` hits that are ledger-layer and out of scope:

- `src/factgraph/core/evidence/write_protocol.py:141`
- `src/factgraph/core/store/database.py:530`
- `src/factgraph/core/store/ledger.py:390`, `:521`, `:1071`
- `src/service/runtime_v1.py:76`, `:2133`, `:2139`, `:2234`
- `tests/test_annotation_store.py`, `tests/test_walker_*`, `tests/test_ledger_concurrency.py`, retract/identity guard tests
- docs under `docs/quickstart/data_model.md`, read/write/entity docs, and service docs that discuss ledger Claims

Recommendation:

- Step 4.4 should add a carve-out table: ledger `Claim` is not in scope, even if grep says `Claim`.
- Step 4.6.5 grep should use either import-aware filtering or bucket protocol vs ledger hits manually.

### PF-r2 — SDK/protocol export and `__all__` count impact must be exact

Current source:

- `src/factgraph/sdk/__init__.py` exports `Claim`, `EvidenceRef`, `DetachedClaimError`, `DetachedEvidenceRefError`
- `src/factgraph/application/protocol/__init__.py` exports the same symbols
- `tests/test_sdk_find_partial_identity.py:139-145` currently asserts `len(sdk_module.__all__) == 65` and positive membership for `ResultFingerprint`

Recommendation:

- If PF-R2 C1 is adopted, Step 4.7 should remove four SDK exports and update `__all__` expected count from 65 to 61, unless implementation discovers another public symbol replacement.
- Protocol export tests should assert absence or use updated exported symbols; do not leave stale import comments.

## 4. Verified Findings

- PF-v1 — Blueprint fork is correct: preflight branch forked from `1c65fafd`.
- PF-v2 — Q-PR1 sacred path check remains empty at preflight start.
- PF-v3 — Current `Claim` and `EvidenceRef` class anchors match draft: `evaluate_result.py:95` and `:127`.
- PF-v4 — Current `EvaluateRow` still owns `claim` / `evidence_ref` wrappers: `evaluate_result.py:165-171`.
- PF-v5 — Current `Explanation` still owns `claim: Claim | None`: `evaluate_result.py:352-355`.
- PF-v6 — Parent-design tension is real: parent §3.3 excludes row `repr`, while user gamma scope mentioned repr flattening.
- PF-v7 — Service has protocol row projection and ledger Claim imports in the same file; layer separation is required.
- PF-v8 — No abandonment blocker: all issues are implementation-scope tightening, not slice cancellation.

## 5. Scoped Details

### PF-s1 — Implementation order

Recommended Step 4.7 order:

1. Add row fields (`kind`, `digest`, `closed_head_digest`) and direct helpers.
2. Update row construction (`_candidate_set_to_evaluate_row`) and digest helpers.
3. Update `Explanation` shape and live-row constructors.
4. Update service row serializer preserving wire keys.
5. Update SDK/protocol exports and export tests.
6. Update active tests.
7. Update docs.

### PF-s2 — Docs wording split

Docs need two simultaneous messages:

- in-process DTO: `Claim` / `EvidenceRef` wrappers are removed; row owns the useful data
- service JSON: nested `claim` / `evidence_ref` payloads may remain as wire compatibility dictionaries, not DTO objects

## 6. Blueprint Amendment Checklist

- [ ] Lock R1: no `EvaluateRow.repr`; add helper-derived compatibility values where needed.
- [ ] Lock C1: immediate in-process wrapper removal; reject C2/C3 for this slice.
- [ ] Add PF-R3 `Explanation.row` cascade and redundant-field removal.
- [ ] Add PF-R4 service wire compatibility split.
- [ ] Add ledger `Claim` carve-out table.
- [ ] Add SDK/protocol export count expectations.
- [ ] Refresh acceptance criteria and Step 4.6.5 grep plan.

## 7. Sacred State Snapshot

- Sacred master: must remain `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Q-PR1 5 sacred paths: 0-diff vs `4c472b50`.
- Dirty baseline: preserved; preflight writes only this artifact.
- Push: none.
