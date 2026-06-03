# Task Blueprint: Eval-row bindings port-map Slice ζ — `{port_name: term}` map shape

- Status: draft
- Created: 2026-06-03
- Last Updated: 2026-06-03 (Step 4.1 draft)
- Owner: Claude (blueprint draft) / Codex (review + impl) — Slice 4/5 cross-flip per [[feedback_audit_to_archive_cadence]]; hybrid cadence default per [[feedback_hybrid_cadence_sequential_mechanical_slices]] unless Step 4.3 surfaces novel concerns
- Fork base: `0719ace6` (Slice γ Step 4.9 archive HEAD)
- Parent design: [`workflow/design/design-points/active/evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.6 + §6 Slice ζ
- Predecessors:
  - [`2026-06-03_eval-result-flatten-slice-alpha.md`](../archive/2026-06-03_eval-result-flatten-slice-alpha.md) — owner-resolver pattern + `_claim_arguments_for_row(row)` helper
  - [`2026-06-03_result-fingerprint-fold-slice-beta.md`](../archive/2026-06-03_result-fingerprint-fold-slice-beta.md) — `ResultFingerprint` sub-object
  - [`2026-06-03_eval-row-inline-claim-evidence-ref-slice-gamma.md`](../archive/2026-06-03_eval-row-inline-claim-evidence-ref-slice-gamma.md) — wrapper removal; `EvaluateRow` 现在直接 owns `kind/digest/closed_head_digest`
- Related Modules:
  - `src/factgraph/application/protocol/evaluate_result.py` (EvaluateRow bindings field + `_bindings_from_candidate(...)` production + `row_id_for(...)` + `claim_digest_for(...)` + `_claim_arguments_for_row(...)` helper)
  - `src/factgraph/sdk/store.py` (potential EvaluateRow construction site)
  - `src/service/runtime_v1.py` (service JSON wire reads `row.bindings`)
  - `tests/application/protocol/test_evaluate_result_dtos.py` + `tests/application/protocol/test_evaluate_result_digests.py`
  - `tests/sdk/test_evaluate_result_exports.py` + integration tests reading bindings shape
- Related Docs:
  - `docs/quickstart/evaluate_and_evidence.md` (§2.2 bindings explanation)
  - `docs/api/openapi.yaml` (if bindings schema is exposed in wire)
  - SDK + service docs that show example bindings payload

## 1. Problem

Parent design §3.6 audit established that shipped `row.bindings` is the wrong shape for user ergonomics:

Current shape:
```python
row.bindings = {
    "pred_id": "user:region",
    "terms": [
        {"kind": "entity_ref", "value": "idref_v1:User:..."},
        {"kind": "literal", "tag": "string", "value": "US"},
    ],
}
```

Target shape per parent design §3.6:
```python
row.bindings = {
    "user":   {"kind": "entity_ref", "value": "idref_v1:User:..."},
    "region": {"kind": "literal", "tag": "string", "value": "US"},
}
```

User wants `row.bindings["user"]` direct access, not positional `terms[i]` lookup. `pred_id` 从 bindings 移除 —— 它已经在 `EvaluateResult.head.id` 里(post-γ;直接 `result.head.id`)。

Slice ζ is surface organization only — same data, different key/value layout. Not a semantic change. Parent §6 ordering recommends ζ low-risk after wrapper removal.

## 2. Goals

- G1 — `_bindings_from_candidate(candidate)` produces `{port_name: term}` Mapping (port_name from `head.ports` keys; term is the typed `{kind, value, tag?}` dict)
- G2 — `EvaluateRow.bindings` field shape changes to `Mapping[str, Mapping[str, Any]]` (the outer Mapping keys are port names, inner Mapping is term shape)
- G3 — `_claim_arguments_for_row(row)` returns the new flat shape directly(no `pred_id` / `terms` reconstruction)
- G4 — Helpers that compute `row_id_for(run_id, bindings)` and `claim_digest_for(claim_kind, effective_claim_name, bindings)` 走 schema version bump path (see §5.3 open Q)
- G5 — Service JSON wire `"bindings"` key reflects new shape **OR** keeps legacy `{pred_id, terms[]}` wire envelope while in-process shape changes (Step 4.3 preflight decides per Slice α/β/γ wire-compat precedent)
- G6 — Docs cascade(quickstart + SDK + service)展示新 shape
- G7 — Test coverage:new shape construction + access ergonomics + byte stability decision verified
- G8 — Q-PR1 sacred 5-path 0-diff preserved

## 3. Non-goals

- N1 — Wrapper class addition (Slice γ removed Claim/EvidenceRef wrappers; ζ does not introduce new wrappers)
- N2 — EvidenceGraph 3-tier hierarchy (Slice η)
- N3 — `Explanation.repr` walker (Slice ε)
- N4 — Query-style `head.id` decoupling (Slice δ)
- N5 — Change term shape internals (`{kind, value, tag?}` typed dict stays the same; only the **outer Mapping organization** changes)
- N6 — Sacred-path edits (`write_protocol.py` / `ledger.py` / `_builders.py` / `adapters/pyreason/` / `accept.py`)
- N7 — Dirty baseline files
- N8 — Push or merge to sacred branches

## 4. Current Source Anchors (Step 4.1 fresh read)

- `src/factgraph/application/protocol/evaluate_result.py:86-89` — `EvaluateRow` definition with `bindings: Mapping[str, Any]` field
- `src/factgraph/application/protocol/evaluate_result.py:377-...` — `row_id_for(run_id, bindings)` canonical bytes helper
- `src/factgraph/application/protocol/evaluate_result.py:447` — `_claim_arguments_for_row(row)` returns `row.bindings` directly(post-Slice-α helper)
- `src/factgraph/application/protocol/evaluate_result.py:630-650` — `_candidate_set_to_evaluate_row` production construction site
- `src/factgraph/application/protocol/evaluate_result.py:637` — `_bindings_from_candidate(candidate)` — the function that builds the current `{pred_id, terms[]}` shape
- `src/factgraph/application/protocol/evaluate_result.py:639` — `claim_digest_for(claim_kind, effective_claim_name, bindings)` consumes bindings in canonical bytes
- `src/factgraph/application/protocol/evaluate_result.py:497` — service-bound bindings inclusion in row dict
- `tests/application/protocol/test_evaluate_result_digests.py` — digest byte-equal fixtures (need decision on whether to update or layer)

## 5. Proposed Shape (Draft, Not Yet Locked)

### 5.1 New `_bindings_from_candidate(candidate)`

Reads `head.ports` (the rule's port names in declared order) + candidate's resolved term values, zips them into `{port_name: term}` map. `term` dict keeps existing `{kind, value, tag?}` typed shape.

```python
def _bindings_from_candidate(candidate: CandidateSet) -> Mapping[str, Mapping[str, Any]]:
    port_names = tuple(candidate.head.ports.keys())  # or via head argument; preflight confirms source
    terms = candidate.resolved_terms  # current shipped path
    if len(port_names) != len(terms):
        raise ProtocolShapeError(...)
    return _freeze_mapping({name: term for name, term in zip(port_names, terms)})
```

Source of port names: needs Step 4.3 preflight confirmation (candidate may not directly carry head; lookup via parent context).

### 5.2 `_claim_arguments_for_row(row)` simplification

Post-ζ:`_claim_arguments_for_row(row)` returns `row.bindings` directly with no shape change. Helper might become trivial-pass-through, OR can be deleted entirely. Step 4.2 review locks.

### 5.3 Canonical bytes byte-equal — OPEN Q (Step 4.2 / 4.3 must lock)

`row_id_for(run_id, bindings)` and `claim_digest_for(...)` compute canonical bytes including bindings shape. Changing bindings shape **breaks byte-equal contract** with α/β/γ row digests.

Two paths for Step 4.2 to decide:

- **Option A — schema version bump**: `row_id_for` canonical bytes schema `evaluate_row_id_v1` → `_v2` (and similarly for `claim_digest_for`). Row digests / row IDs are intentionally different from pre-ζ for the new shape. **Clean break**.
- **Option B — split in-memory vs canonical**: keep canonical bytes computed from legacy `{pred_id, terms[]}` shape; expose new shape only on `row.bindings` field. Split between in-memory + canonical. Preserves byte-equal contract.

Default draft bias: **Option A — schema version bump** (parent design intent for evolved DTO surface;byte-equal contract isn't load-bearing across protocol shape evolution). Step 4.3 preflight may surface evidence forcing Option B if there are cross-process consumers expecting bit-stable IDs across ζ.

### 5.4 Service JSON wire

Per Slice α/β/γ N-1 service-wire precedent: in-process shape changes but service wire **may stay legacy** for HTTP consumer compatibility. Step 4.3 preflight decides:
- C1 — service wire reflects new shape (breaking change for HTTP API consumers)
- C2 — service wire keeps legacy `{pred_id, terms[]}` wire envelope; serializer reconstructs legacy shape from new in-process map

Default draft bias: **C2 — wire envelope preservation** per Slice γ PF-R4 precedent.

### 5.5 Docs cascade

3 docs likely affected:
- `docs/quickstart/evaluate_and_evidence.md` §2.2 bindings explanation
- SDK docs that show bindings example payload
- service docs / openapi.yaml if bindings schema is published

Step 4.3 preflight enumerates exact files.

## 6. Cadence Path Locks

- **Hybrid cadence default** per [[feedback_hybrid_cadence_sequential_mechanical_slices]] — ζ is mechanical surface-organization slice following β-pattern; 4.4→4.6.5 fast-track allowed; 4.7 + 4.8 individual reports.
- **Escalation to tight gates** if Step 4.3 preflight surfaces novel concerns:
  - byte-equal contract impact unexpectedly load-bearing (forcing Option B)
  - wire-compat impact wider than Slice γ N-1 N-2 pattern
  - cross-process consumer enumeration finds bit-stable ID dependencies
- Stage-0 source audit folded into this Step 4.1 draft per Slice α/β/γ precedent. No separate `workflow/audit/active/2026-06-03_eval-row-bindings-port-map-vs-shipped.md`.
- §5.3 schema version bump Q is **the load-bearing decision** for Step 4.2 review.

## 7. Acceptance Criteria (Draft)

- [ ] Step 4.2 review has locked §5.3 (Option A schema bump vs Option B split-canonical).
- [ ] Step 4.3 preflight has enumerated `row.bindings` consumers + wire-compat scope + docs cascade.
- [ ] `_bindings_from_candidate(candidate)` produces `{port_name: term}` map shape.
- [ ] `EvaluateRow.bindings["<port_name>"]` returns the corresponding term dict directly.
- [ ] Canonical bytes decision applied consistently (`row_id_for` + `claim_digest_for` schema version per Option A, OR canonical computation uses legacy shape per Option B).
- [ ] Service JSON wire preserves locked compatibility (C1 reflect-new or C2 wire-envelope-preservation).
- [ ] D19 digest algorithm unchanged (only canonical bytes payload shape evolves under Option A).
- [ ] No `pred_id` / `terms` keys in `row.bindings` after implementation.
- [ ] Q-PR1 5-path 0-diff vs `4c472b50` preserved.
- [ ] Dirty baseline preserved.

## 8. Implementation Plan (Tentative)

1. Step 4.2 — Draft review + tightening on blueprint branch. **Required focus**: §5.3 canonical bytes Q + §5.4 wire compat Q + helper port-name source confirmation.
2. Step 4.3 — Independent preflight branch `v0.2.0-eval-row-bindings-port-map-preflight-2026-06-03`; produce 5-bucket finding table; enumerate consumers + wire compat + docs.
3. Step 4.4 — Fold preflight findings into blueprint.
4. Step 4.5 — Self-check.
5. Step 4.6 — Scope freeze (`draft` → `scoped`).
6. Step 4.6.5 — Pre-impl grep (port-name source / bindings consumers / `pred_id` / `terms` legacy keys).
7. Step 4.7 — Implementation on `v0.2.0-impl-eval-row-bindings-port-map-2026-06-03` — DTO + helpers + production construction + service serializer + tests + docs.
8. Step 4.8 — Closure.
9. Step 4.9 — Archive.

## 9. Pre-Impl Audit Tasks for Step 4.3

- A1 — Confirm port-name source — does `CandidateSet` carry head reference,or does production path pass head separately?
- A2 — Enumerate `row.bindings` consumers — production + tests + docs + wire payload
- A3 — Search for legacy `bindings["pred_id"]` / `bindings["terms"]` access in src + tests + docs
- A4 — Determine canonical bytes schema version impact — does any external consumer depend on bit-stable row_id / row_digest across ζ?
- A5 — Service wire compat scope — `_evaluate_row_to_dict(...)` bindings key handling
- A6 — Docs cascade — quickstart + SDK + service + openapi

## 10. Outcome / Deviations

Pending.

## 11. Deferred / Carry-Forward

- D1 — EvidenceGraph 3-tier hierarchy → Slice η
- D2 — Explanation.repr walker → Slice ε
- D3 — query-style head decoupling → Slice δ
