# Task Blueprint Audit: Eval-row bindings port-map Slice ζ — `{port_name: term}` map shape

- Blueprint: [2026-06-03_eval-row-bindings-port-map-slice-zeta.md](./2026-06-03_eval-row-bindings-port-map-slice-zeta.md)
- Parent design: [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.6 + §6 Slice ζ
- Predecessors: Slice α (archived) + Slice β (archived) + Slice γ (archived)
- Fork base: `0719ace6` (Slice γ Step 4.9 archive HEAD)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | draft | Blueprint pair created | Initial scope recorded on `v0.2.0-blueprint-eval-row-bindings-port-map-2026-06-03` (fork from `0719ace6`). Hybrid cadence default per [[feedback_hybrid_cadence_sequential_mechanical_slices]] — ζ is mechanical surface-organization slice following β pattern. Escalation to tight gates reserved for Step 4.3 if novel concerns surface (byte-equal load-bearing / wire-compat wide / bit-stable ID dependencies). |
| 2026-06-03 | draft | Step 4.2 review + tightening | Folded P1-1/P1-2/P1-3/P2-1/P2-2: explicit `head` context is required for port-name bindings; canonical bytes use v2 schema labels; service wire preserves legacy bindings envelope; provenance paths need legacy candidate payload helper; D19 wording clarified as algorithm-stable but schema-version-evolving. Status remains `draft`. |
| 2026-06-03 | draft | Step 4.4 preflight amendment | Folded Step 4.3 preflight `9d0e1186`: PF-R1 row-derived ProbLog provenance helper; PF-R2 construction sites that can pass `head`; PF-R3 exact v2 schema labels; PF-r1/PF-r2 transition helpers; PF-s1/PF-s2/PF-s3 carve-outs. Status remains `draft`; 0 abandonment. |
| 2026-06-03 | draft | Step 4.5 self-check PASS | Verified G/N/acceptance consistency, removed stale draft wording, confirmed PF-R/PF-r/PF-s coverage, Q-PR1 0-diff, dirty baseline preservation, and 0 abandonment. |
| 2026-06-03 | scoped | Step 4.6 scope freeze | Status `draft` → `scoped`; scope frozen with Step 4.2 locks, Step 4.4 PF-R1/PF-R2/PF-R3 + PF-r1/PF-r2 + PF-s1/PF-s2/PF-s3, and hybrid cadence retained for Step 4.6.5/4.7. |
| 2026-06-03 | scoped | Step 4.6.5 pre-impl grep PASS | Re-ran constructor, `row.bindings`, legacy `pred_id`/`terms`, and v1/v2 canonical-label greps across `src/`, `tests/`, `docs/`, and `workflow/`. No new production N-findings beyond Step 4.4 scope: construction remains SDK/service/protocol-test; row-derived legacy payload users remain service wire + ProbLog row evidence graph; direct candidate-payload and ledger/core hits remain carve-outs. Status remains `scoped`; no implementation started. |

## Decision Notes

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | `ResultFingerprint` sub-object pattern reused — `{port_name: term}` map is direct shape, no nested wrapper | Parent design §3.6 specifies the simple map shape; no sub-object needed. |
| 2026-06-03 | §5.3 canonical bytes Q draft bias = Option A (schema version bump) | Parent design intent is evolved DTO surface; byte-equal contract isn't load-bearing across shape evolution. Step 4.3 preflight may force Option B if cross-process consumers depend on bit-stable IDs. |
| 2026-06-03 | §5.4 service wire draft bias = C2 (wire-envelope preservation) | Slice γ PF-R4 precedent: in-process DTO shape changes,service JSON wire keys stable. Step 4.3 confirms. |
| 2026-06-03 | Stage 1 audit doc deferred per Slice 4/5 precedent | Stage-0 source audit folded into parent design + this blueprint draft. Step 4.2 reviewer verifies via Rule 1 fresh reads. |
| 2026-06-03 | Hybrid cadence default | ζ pattern matches β (mechanical surface fold); per [[feedback_hybrid_cadence_sequential_mechanical_slices]] 4.4→4.6.5 can fast-track; 4.7 + 4.8 individual reports. Step 4.3 escalation rule if novel concerns. |
| 2026-06-03 | Step 4.2 P1-1 — explicit `head` context required | `CandidateSet` carries `target` + `payload`, not `head`; `_candidate_set_to_evaluate_row(...)` currently lacks a `head` parameter even though SDK/service construction callers have `head` in scope. Step 4.7 must pass `head` (or equivalent port context) into `_bindings_from_candidate(...)`; implementation must not invent `candidate.head`. |
| 2026-06-03 | Step 4.2 P1-2 — canonical bytes schema bump locked | Changing `row.bindings` shape changes canonical bytes. The slice locks v2 schema labels for `row_id_for`, `claim_digest_for`, and `_row_digest_for(...)`; `evidence_ref_id_for(...)` remains v1 and changes only derivatively through row id / row digest. D19 algorithm discipline remains unchanged. |
| 2026-06-03 | Step 4.2 P1-3 — provenance helper needed | `_build_problog_provenance_row_evidence_graph(...)` passes `dict(row.bindings)` to `problog_trace_to_evidence_graph(...)`; downstream `_resolve_candidate_info(...)` and `_candidate_binding_from_payload(...)` require `candidate_payload.pred_id` + `candidate_payload.terms`. Row-owned port-map bindings must therefore be converted back to a legacy candidate payload for provenance/wire compatibility paths. |
| 2026-06-03 | Step 4.2 P2-1 — service wire C2 locked | Following Slice γ PF-R4, in-process DTO shape changes but service JSON `"bindings"` remains the legacy `{pred_id, terms[]}` envelope unless a separate API-breaking slice changes OpenAPI semantics. |
| 2026-06-03 | Step 4.2 P2-2 — `D19 unchanged` wording narrowed | The digest algorithm remains stable, but row/claim/row-digest payload schema labels intentionally change. Acceptance now says algorithm stable, schema-version-evolving, avoiding a false byte-equal promise. |
| 2026-06-03 | Step 4.4 PF-R1/PF-s1/PF-s2 — helper scope narrowed | Preflight distinguished row-derived legacy-payload users from direct candidate-payload users. The mandatory helper applies to service row serializer and ProbLog row evidence graph. PyReason provenance, core candidate timeline, service candidate evidence tree, and direct candidate-payload endpoints remain out of row-derived migration scope unless a future grep finds a row-derived caller. |
| 2026-06-03 | Step 4.4 PF-R2 — construction-site list locked | Active row construction sites are `sdk/store.py`, `service/runtime_v1.py`, and one protocol test harness. All can pass existing `head` context to `_candidate_set_to_evaluate_row(...)`; no hidden production constructor was found. |
| 2026-06-03 | Step 4.4 PF-R3 — exact v2 labels recorded | Step 4.7 must use `evaluate_row_id_v2`, `evaluate_claim_v2`, and `evaluate_row_digest_v2`; `evaluate_evidence_ref_v1` stays unchanged. |
| 2026-06-03 | Step 4.4 PF-r1/PF-r2 — transition helpers kept | `_binding_value_for_head_port(...)` keeps dual-shape fallback during ζ; `_claim_arguments_for_row(row)` remains pass-through as a named row-argument seam. |

## Cross-flip checkpoints (per [[feedback_audit_to_archive_cadence]] + Slice α/β/γ precedents)

- [x] Step 4.1 blueprint draft (Claude — Slice 4/5 default after γ inversion)
- [x] Step 4.2 review + tightening (Codex per Slice 4/5 default)
- [x] Step 4.3 preflight on independent branch `v0.2.0-eval-row-bindings-port-map-preflight-2026-06-03`
- [x] Step 4.4 preflight amendment
- [x] Step 4.5 self-check
- [x] Step 4.6 scope freeze
- [x] Step 4.6.5 pre-impl grep
- [ ] Step 4.7 implementation on `v0.2.0-impl-eval-row-bindings-port-map-2026-06-03`
- [ ] Step 4.8 closure
- [ ] Step 4.9 archive

## Pre-Impl Audit Tasks (Step 4.3 to verify)

(Listed in blueprint §9; codex fills findings here under each `### Task A<n> findings` heading.)

### Task A1 findings

_(Empty — Step 4.3 fills.)_

### Task A2 findings

_(Empty — Step 4.3 fills.)_

### Task A3 findings

_(Empty — Step 4.3 fills.)_

### Task A4 findings

_(Empty — Step 4.3 fills.)_

### Task A5 findings

_(Empty — Step 4.3 fills.)_

### Task A6 findings

_(Empty — Step 4.3 fills.)_
