# Task Blueprint Audit: Eval-row bindings port-map Slice ζ — `{port_name: term}` map shape

- Blueprint: [2026-06-03_eval-row-bindings-port-map-slice-zeta.md](./2026-06-03_eval-row-bindings-port-map-slice-zeta.md)
- Parent design: [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.6 + §6 Slice ζ
- Predecessors: Slice α (archived) + Slice β (archived) + Slice γ (archived)
- Fork base: `0719ace6` (Slice γ Step 4.9 archive HEAD)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | draft | Blueprint pair created | Initial scope recorded on `v0.2.0-blueprint-eval-row-bindings-port-map-2026-06-03` (fork from `0719ace6`). Hybrid cadence default per [[feedback_hybrid_cadence_sequential_mechanical_slices]] — ζ is mechanical surface-organization slice following β pattern. Escalation to tight gates reserved for Step 4.3 if novel concerns surface (byte-equal load-bearing / wire-compat wide / bit-stable ID dependencies). |

## Decision Notes

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | `ResultFingerprint` sub-object pattern reused — `{port_name: term}` map is direct shape, no nested wrapper | Parent design §3.6 specifies the simple map shape; no sub-object needed. |
| 2026-06-03 | §5.3 canonical bytes Q draft bias = Option A (schema version bump) | Parent design intent is evolved DTO surface; byte-equal contract isn't load-bearing across shape evolution. Step 4.3 preflight may force Option B if cross-process consumers depend on bit-stable IDs. |
| 2026-06-03 | §5.4 service wire draft bias = C2 (wire-envelope preservation) | Slice γ PF-R4 precedent: in-process DTO shape changes,service JSON wire keys stable. Step 4.3 confirms. |
| 2026-06-03 | Stage 1 audit doc deferred per Slice 4/5 precedent | Stage-0 source audit folded into parent design + this blueprint draft. Step 4.2 reviewer verifies via Rule 1 fresh reads. |
| 2026-06-03 | Hybrid cadence default | ζ pattern matches β (mechanical surface fold); per [[feedback_hybrid_cadence_sequential_mechanical_slices]] 4.4→4.6.5 can fast-track; 4.7 + 4.8 individual reports. Step 4.3 escalation rule if novel concerns. |

## Cross-flip checkpoints (per [[feedback_audit_to_archive_cadence]] + Slice α/β/γ precedents)

- [x] Step 4.1 blueprint draft (Claude — Slice 4/5 default after γ inversion)
- [ ] Step 4.2 review + tightening (Codex per Slice 4/5 default)
- [ ] Step 4.3 preflight on independent branch `v0.2.0-eval-row-bindings-port-map-preflight-2026-06-03`
- [ ] Step 4.4 preflight amendment
- [ ] Step 4.5 self-check
- [ ] Step 4.6 scope freeze
- [ ] Step 4.6.5 pre-impl grep
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
