# Task Blueprint Audit: EvidenceGraph 3-tier hierarchy Slice η

- Blueprint: [2026-06-03_evidence-graph-3tier-slice-eta.md](./2026-06-03_evidence-graph-3tier-slice-eta.md)
- Parent design: [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.9 + §6 Slice η
- Predecessors: Slice α / β / γ / ζ archived and pushed
- Fork base: `b4d80f13` (Slice ζ memory HEAD)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | draft | Blueprint pair created | Initial scope recorded on `v0.2.0-blueprint-evidence-graph-3tier-2026-06-03` (fork from `b4d80f13`). Tight gates locked by default because η changes evidence semantics across engines rather than mechanically folding DTO fields. |

## Decision Notes

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | Tight gates default | η touches evidence graph semantics, row evidence builders, renderers, tests, and docs. It must not batch Step 4.7/4.8 reports. |
| 2026-06-03 | Existing node/edge vocabulary remains valid | Backward compatibility and ProbLog/PyReason provenance paths still need `NODE_PREMISE`, `EDGE_DERIVES`, and `EDGE_UPDATES`; η adds layered vocabulary rather than deleting legacy graph concepts. |
| 2026-06-03 | ProbLog layering is the highest-risk Step 4.3 focus | Native/Souffle Form 1 can map witnesses to atoms directly; ProbLog has an adapter-native proof graph that must preserve trace detail while gaining row-level hierarchy. |

## Cross-flip checkpoints

- [x] Step 4.1 blueprint draft (Codex)
- [ ] Step 4.2 review + tightening
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
