# Task Blueprint Audit: EvidenceGraph 3-tier hierarchy Slice η

- Blueprint: [2026-06-03_evidence-graph-3tier-slice-eta.md](./2026-06-03_evidence-graph-3tier-slice-eta.md)
- Parent design: [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.9 + §6 Slice η
- Predecessors: Slice α / β / γ / ζ archived and pushed
- Fork base: `b4d80f13` (Slice ζ memory HEAD)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | draft | Blueprint pair created | Initial scope recorded on `v0.2.0-blueprint-evidence-graph-3tier-2026-06-03` (fork from `b4d80f13`). Tight gates locked by default because η changes evidence semantics across engines rather than mechanically folding DTO fields. |
| 2026-06-03 | draft | Step 4.2 review + tightening | Folded P1-P5: service wire defaults to C2 preservation; PyReason fallback default separated from optional minimal L1/L2 decision; fallback graphs cannot fabricate support atoms; Form 1 atom_index source must be verified; per-engine fill capability table added to acceptance. Status remains `draft`. |

## Decision Notes

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | Tight gates default | η touches evidence graph semantics, row evidence builders, renderers, tests, and docs. It must not batch Step 4.7/4.8 reports. |
| 2026-06-03 | Existing node/edge vocabulary remains valid | Backward compatibility and ProbLog/PyReason provenance paths still need `NODE_PREMISE`, `EDGE_DERIVES`, and `EDGE_UPDATES`; η adds layered vocabulary rather than deleting legacy graph concepts. |
| 2026-06-03 | ProbLog layering is the highest-risk Step 4.3 focus | Native/Souffle Form 1 can map witnesses to atoms directly; ProbLog has an adapter-native proof graph that must preserve trace detail while gaining row-level hierarchy. |
| 2026-06-03 | Step 4.2 P1 — service wire defaults to C2 preservation | Following Slice γ/ζ wire precedent, η node/edge additions are in-process first. Step 4.3 must prove a Required consumer need before expanding service JSON node_kind/edge_kind wire shape or adding reverse mapping to legacy wire shape. |
| 2026-06-03 | Step 4.2 P2 — PyReason fallback default clarified | Rich PyReason Form 2 timeline hierarchy remains out of η. Step 4.3 may only consider a minimal L1/L2 shell if it does not depend on D11 timeline semantics. |
| 2026-06-03 | Step 4.2 P3/P4/P5 — semantic honesty and per-engine fill locks | Fallback graphs must not invent supported atoms; Form 1 atom_index source must be source-verified; acceptance now requires parent §3.9.4 per-engine capability verification. |

## Cross-flip checkpoints

- [x] Step 4.1 blueprint draft (Codex)
- [x] Step 4.2 review + tightening
- [ ] Step 4.3 preflight on independent branch `v0.2.0-evidence-graph-3tier-preflight-2026-06-03`
- [ ] Step 4.4 preflight amendment
- [ ] Step 4.5 self-check
- [ ] Step 4.6 scope freeze
- [ ] Step 4.6.5 pre-impl grep
- [ ] Step 4.7 implementation on `v0.2.0-impl-evidence-graph-3tier-2026-06-03`
- [ ] Step 4.8 closure
- [ ] Step 4.9 archive

## Pre-Impl Audit Tasks

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

### Task A7 findings

_(Empty — Step 4.3 fills.)_
