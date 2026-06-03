# Task Blueprint: Eval-row bindings port-map Slice ζ — `{port_name: term}` map shape

- Status: scoped
- Created: 2026-06-03
- Last Updated: 2026-06-03 (Step 4.6.5 pre-impl grep)
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

- G1 — LOCKED by Step 4.2 P1-1: `_bindings_from_candidate(candidate, *, head)` produces `{port_name: term}` Mapping (port_name from `head.ports` keys; term is the typed `{kind, value, tag?}` dict). `CandidateSet` does **not** carry `head`; every production construction site must pass the already-available `head` context.
- G2 — `EvaluateRow.bindings` field shape changes to `Mapping[str, Mapping[str, Any]]` (the outer Mapping keys are port names, inner Mapping is term shape)
- G3 — `_claim_arguments_for_row(row)` returns the new flat shape directly(no `pred_id` / `terms` reconstruction)
- G4 — LOCKED by Step 4.2 P1-2: helpers that compute `row_id_for(run_id, bindings)`, `claim_digest_for(claim_kind, effective_claim_name, bindings)`, and `_row_digest_for(...)` take the schema-version-bump path for the new bindings shape.
- G5 — LOCKED by Step 4.2 P2-1: service JSON wire `"bindings"` keeps the legacy `{pred_id, terms[]}` envelope while in-process `EvaluateRow.bindings` changes to `{port_name: term}`.
- G5b — LOCKED by Step 4.2 P1-3: provenance/evidence paths that still expect `candidate_payload.pred_id` + `candidate_payload.terms` must use a legacy-payload compatibility helper, not `dict(row.bindings)`.
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
- `src/factgraph/application/protocol/evaluate_result.py:630-650` — `_candidate_set_to_evaluate_row` production construction site; currently has no `head` parameter even though callers have `head`
- `src/factgraph/application/protocol/evaluate_result.py:637` — `_bindings_from_candidate(candidate)` — the function that builds the current `{pred_id, terms[]}` shape from `candidate.payload`
- `src/factgraph/application/protocol/evaluate_result.py:927` — ProbLog provenance path passes `dict(row.bindings)` as `candidate_payload`; downstream provenance code expects `pred_id` + `terms`
- `src/service/runtime_v1.py:2468-2488` — service row serializer emits `bindings` and must preserve wire envelope if Step 4.2 locks C2
- `src/factgraph/application/protocol/evaluate_result.py:639` — `claim_digest_for(claim_kind, effective_claim_name, bindings)` consumes bindings in canonical bytes
- `src/factgraph/application/protocol/evaluate_result.py:497` — service-bound bindings inclusion in row dict
- `tests/application/protocol/test_evaluate_result_digests.py` — digest byte-equal fixtures (need decision on whether to update or layer)

## 5. Proposed Shape (Scoped)

### 5.1 New `_bindings_from_candidate(candidate, *, head)`

Step 4.2 P1-1 locks the port-name source. `CandidateSet` does **not** carry a head reference (`core/derivation/candidates.py` only has `target` + `payload`); therefore the protocol helper must accept head context explicitly.

Reads `head.ports` (the rule's port names in declared order) + candidate payload terms, zips them into `{port_name: term}` map. `term` dict keeps existing `{kind, value, tag?}` typed shape.

```python
def _bindings_from_candidate(candidate: CandidateSet, *, head: Rule) -> Mapping[str, Mapping[str, Any]]:
    port_names = tuple(head.ports.keys())
    terms = _legacy_terms_from_candidate(candidate)
    if len(port_names) != len(terms):
        raise ProtocolShapeError(...)
    return _freeze_mapping({name: term for name, term in zip(port_names, terms)})
```

`_candidate_set_to_evaluate_row(...)` must accept `head: Rule` (or an equivalent locked port-name context) and production callers in `sdk/store.py` and `src/service/runtime_v1.py` must pass their already-available `head`.

### 5.2 `_claim_arguments_for_row(row)` simplification

Step 4.2 locks keeping `_claim_arguments_for_row(row)` as a trivial pass-through compatibility helper for this slice. Post-ζ, it returns `row.bindings` directly with no shape change. Deleting the helper is deferred because service/wire/provenance compatibility code still benefits from one named row-argument access point during the transition.

### 5.3 Canonical bytes — LOCKED schema-version bump

`row_id_for(run_id, bindings)` and `claim_digest_for(...)` compute canonical bytes including bindings shape. Changing bindings shape **breaks byte-equal contract** with α/β/γ row digests.

Step 4.2 P1-2 locks **Option A — schema version bump**:

- `row_id_for` canonical bytes schema `evaluate_row_id_v1` → `evaluate_row_id_v2`.
- `claim_digest_for` canonical bytes schema `evaluate_claim_v1` → `evaluate_claim_v2`.
- `_row_digest_for(...)` canonical bytes schema `evaluate_row_digest_v1` → `evaluate_row_digest_v2` because it embeds both `row.bindings` and claim arguments.
- `evidence_ref_id_for(...)` formula remains named `evaluate_evidence_ref_v1`; its output changes derivatively through `row_id` / `row.digest`, not because the evidence-ref payload schema changes.
- D19 digest **algorithm** remains the same (`canonical_bytes_for_evaluate` + SHA-256 token/hex discipline); the payload schema version changes intentionally.

Rejected alternative:

- Option B — split in-memory `{port_name: term}` from canonical legacy `{pred_id, terms[]}`. Rejected for ζ because it would keep the old Datalog payload shape alive in row identity while presenting a different public DTO shape.

### 5.4 Legacy payload compatibility helper

Step 4.2 P2-1 locks C2 service wire preservation, and Step 4.2 P1-3 extends the same helper to provenance paths.

Add a helper such as:

```python
def _legacy_candidate_payload_for_row_result(row: EvaluateRow, result: EvaluateResult) -> Mapping[str, Any]:
    return {
        "pred_id": result.head.id,
        "terms": tuple(row.bindings[port_name] for port_name in result.head.ports),
    }
```

Use this helper for:

- `src/service/runtime_v1.py` row serializer `"bindings"` key, preserving the legacy `{pred_id, terms[]}` wire envelope.
- `_build_problog_provenance_row_evidence_graph(...)`, because `problog_trace_to_evidence_graph(...)` calls `_resolve_candidate_info(...)` and `_candidate_binding_from_payload(...)`, both of which require `candidate_payload.pred_id` and `candidate_payload.terms`.

The in-process `row.bindings` remains `{port_name: term}`; only compatibility/wire/provenance payload helpers reconstruct the legacy envelope.

Step 4.3 PF-R1/PF-s1/PF-s2 narrows this scope:

- Required row-derived users: service row serializer and ProbLog row evidence graph.
- Not row-derived users: PyReason provenance, core candidate provenance timeline, service candidate evidence tree, and direct candidate-payload endpoints. They still consume legacy `pred_id` + `terms`, but from independent candidate payloads, not from `EvaluateRow.bindings`.

### 5.5 Construction-site list (Step 4.3 PF-R2)

All active row-construction sites can pass `head`:

| Site | Change |
| --- | --- |
| `src/factgraph/sdk/store.py:2691` | pass local `head` into `_candidate_set_to_evaluate_row(...)` |
| `src/service/runtime_v1.py:2359` | pass local `head` from `_head_rule_for_compiled_plans(...)` |
| `tests/application/protocol/test_evaluate_result_dtos.py:993` | pass test `head` from `_result_parts()` |

No hidden production row constructor was found in Step 4.3.

### 5.6 Canonical version labels (Step 4.3 PF-R3)

Step 4.7 exact schema labels:

| Helper | Current | Target |
| --- | --- | --- |
| `row_id_for(...)` | `evaluate_row_id_v1` | `evaluate_row_id_v2` |
| `claim_digest_for(...)` | `evaluate_claim_v1` | `evaluate_claim_v2` |
| `_row_digest_for(...)` | `evaluate_row_digest_v1` | `evaluate_row_digest_v2` |
| `evidence_ref_id_for(...)` | `evaluate_evidence_ref_v1` | unchanged |

`evidence_ref_id_for(...)` output may change because `row_id` and `row.digest` change, but its own payload schema label remains v1.

### 5.7 Transition helpers (Step 4.3 PF-r1/PF-r2)

- Keep `_binding_value_for_head_port(...)` dual-shape fallback during ζ. Production rows should be port maps, but the fallback protects detached/test rows and makes `row.close()` migration less brittle.
- Keep `_claim_arguments_for_row(row)` as a pass-through helper for this slice. It remains a named seam for service wire `claim.arguments`, `_row_digest_for(...)`, and tests.

### 5.8 Docs cascade

3 docs likely affected:
- `docs/quickstart/evaluate_and_evidence.md` §2.2 bindings explanation
- `docs/official/kernel/quickstart/evidence.md` direct row-bindings wording
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
- §5.3 schema version bump and §5.4 legacy payload preservation are locked by Step 4.2 review; Step 4.3 verified no additional consumers require a different path.

## 7. Acceptance Criteria (Draft)

- [x] Step 4.2 review has locked §5.3 (Option A schema bump) and §5.4 legacy payload preservation.
- [x] Step 4.3 preflight has enumerated `row.bindings` consumers + wire-compat scope + docs cascade.
- [ ] `_bindings_from_candidate(candidate)` produces `{port_name: term}` map shape.
- [ ] `EvaluateRow.bindings["<port_name>"]` returns the corresponding term dict directly.
- [ ] Canonical bytes decision applied consistently (`row_id_for` + `claim_digest_for` + `_row_digest_for` use v2 schema labels).
- [ ] Service JSON wire preserves locked compatibility (C2 wire-envelope preservation) via the legacy payload helper.
- [ ] ProbLog row evidence graph uses helper reconstruction and no longer passes `dict(row.bindings)` when the callee expects `pred_id` + `terms`.
- [ ] PyReason/core candidate provenance and service candidate evidence tree paths are left out of row-derived migration scope unless a new row-derived caller appears.
- [ ] D19 digest algorithm unchanged (only canonical bytes payload schema labels evolve under Option A).
- [ ] No `pred_id` / `terms` keys in `row.bindings` after implementation.
- [ ] Q-PR1 5-path 0-diff vs `4c472b50` preserved.
- [ ] Dirty baseline preserved.

## 8. Implementation Plan (Tentative)

1. Step 4.2 — Draft review + tightening on blueprint branch. **Required focus**: §5.3 canonical bytes Q + §5.4 wire compat Q + helper port-name source confirmation. Completed with P1-1/P1-2/P1-3/P2-1/P2-2 tightening.
2. Step 4.3 — Independent preflight branch `v0.2.0-eval-row-bindings-port-map-preflight-2026-06-03`; produce 5-bucket finding table; enumerate consumers + wire compat + docs.
3. Step 4.4 — Fold preflight findings into blueprint. Completed with PF-R1/PF-R2/PF-R3 + PF-r1/PF-r2 + PF-s1/PF-s2/PF-s3.
4. Step 4.5 — Self-check.
5. Step 4.6 — Scope freeze (`draft` → `scoped`).
6. Step 4.6.5 — Pre-impl grep (port-name source / bindings consumers / `pred_id` / `terms` legacy keys).
7. Step 4.7 — Implementation on `v0.2.0-impl-eval-row-bindings-port-map-2026-06-03` — DTO + helpers + production construction + service serializer + tests + docs.
8. Step 4.8 — Closure.
9. Step 4.9 — Archive.

## 9. Pre-Impl Audit Tasks for Step 4.3

- A1 — Confirm port-name source — `CandidateSet` does not carry head; verify every `_candidate_set_to_evaluate_row(...)` caller can pass `head` and no hidden construction site is missed.
- A2 — Enumerate `row.bindings` consumers — production + tests + docs + wire payload
- A3 — Search for legacy `bindings["pred_id"]` / `bindings["terms"]` access in src + tests + docs
- A4 — Confirm canonical bytes version bump blast radius — `row_id_for`, `claim_digest_for`, `_row_digest_for`, fixtures, docs, and any test vectors.
- A5 — Service/provenance legacy payload compat scope — `_evaluate_row_to_dict(...)` bindings key handling plus row-derived ProbLog provenance. PyReason/core/service candidate-payload paths are carve-outs unless row-derived callers appear.
- A6 — Docs cascade — quickstart + SDK + service + openapi

## 10. Outcome / Deviations

Pending.

## 11. Deferred / Carry-Forward

- D1 — EvidenceGraph 3-tier hierarchy → Slice η
- D2 — Explanation.repr walker → Slice ε
- D3 — query-style head decoupling → Slice δ
