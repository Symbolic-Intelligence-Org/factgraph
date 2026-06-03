# Task Blueprint Audit: Explanation.repr walker Slice ε — layered EvidenceGraph → multi-line NL

- Blueprint: [2026-06-03_explanation-repr-walker-slice-epsilon.md](./2026-06-03_explanation-repr-walker-slice-epsilon.md)
- Parent design: [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.7 + §4.7 + §6 Slice ε + §7.3 D21 close
- Predecessors: α / β / γ / ζ / η (all archived)
- Hard-dependency: η layered EvidenceGraph (now in `evidence_graph.py:14-29` with 6+7 vocabulary)
- Fork base: `77cf9762` (Slice η memory commit HEAD)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | draft | Blueprint pair created | Initial scope recorded on `v0.2.0-blueprint-explanation-repr-walker-2026-06-03` (fork from `77cf9762`). Tight gates default per Slice η §10 D6 lock — evidence-model slices require behavior-change + state-transition individual report boundaries. ε hard-depends on η layered EvidenceGraph vocabulary (verified at `evidence_graph.py:14-29`). |

## Decision Notes

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | Walker location locked at `factgraph.application.protocol.explanation_render` (new module) | Per parent design §4.7. Keeps walker close to Explanation DTO; protocol-layer authority. |
| 2026-06-03 | Tight gates default per Slice η §10 D6 lock | ε is evidence-model continuation; behavior-change + state-transition individual reports required unless user explicitly changes cadence policy. |
| 2026-06-03 | Stage 1 audit doc deferred per Slice 4/5 precedent | Stage-0 source audit folded into parent design + this blueprint draft + Step 4.3 preflight will verify Rule 1 fresh reads. |
| 2026-06-03 | Edge-kind-to-connector mapping derives from parent §4.7 example | Standard "因为... 所以..." NL connectors for η 4 new edges + 3 legacy fallback edges. |
| 2026-06-03 | Lazy cache via `_repr_cache` internal field | Frozen dataclass + `object.__setattr__` cache pattern reused from Slice α `EvaluateRow._result_resolver` precedent. |
| 2026-06-03 | Walker direction follows η PF-R1 shipped lock | Walker DFS uses `adjacency[edge.to_node_id].append(edge.from_node_id)` — children iterated from root via existing shipped pattern. No new direction logic. |
| 2026-06-03 | `unsupported` / `invalid_request` → `repr is None` invariant | Walker has no graph to walk; honest "None" beats fabricated empty tuple or placeholder. |

## Cross-flip checkpoints (per [[feedback_audit_to_archive_cadence]] + Slice η D6 lock)

- [x] Step 4.1 blueprint draft (Claude — Slice 4/5 default)
- [ ] Step 4.2 review + tightening (Codex per Slice 4/5 default)
- [ ] Step 4.3 preflight on independent branch `v0.2.0-explanation-repr-walker-preflight-2026-06-03`
- [ ] Step 4.4 preflight amendment
- [ ] Step 4.5 self-check
- [ ] Step 4.6 scope freeze
- [ ] Step 4.6.5 pre-impl grep
- [ ] Step 4.7 implementation on `v0.2.0-impl-explanation-repr-walker-2026-06-03` (individual report per D6)
- [ ] Step 4.8 closure (individual report per D6)
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

### Task A7 findings

_(Empty — Step 4.3 fills.)_

### Task A8 findings

_(Empty — Step 4.3 fills.)_
