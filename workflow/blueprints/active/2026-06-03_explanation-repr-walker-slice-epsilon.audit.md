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
| 2026-06-03 | draft | Step 4.2 review + tightening | Folded P1-P4: `Explanation.repr` is a computed property rather than constructor field; shipped `status == "passed" iff evidence is not None` invariant preserved; failed explanations without evidence render failure summaries instead of graph-walking atoms; walker renders `NODE_CONCLUSION` from existing node `value_summary` / `label` rather than requiring `head`; service wire default is no change unless preflight finds an explicit Explanation serializer. Status remains `draft`. |
| 2026-06-03 | draft | Step 4.4 preflight amendment | Folded Step 4.3 preflight findings from `v0.2.0-explanation-repr-walker-preflight-2026-06-03@5be22c0b`: PF-R1/PF-R2 confirmed, PF-r1 parent-design `row.repr` wording carry-forward, PF-r2 protocol-helper export scope lock, docs cascade refresh, and Step 4.6.5 grep requirements. Status remains `draft`. |
| 2026-06-03 | draft | Step 4.5 self-check PASS | Verified PF coverage, G/N consistency, stale wording cleanup, Step 4.6.5 grep plan, Q-PR1 boundary, and dirty-baseline preservation. No amendment required. |
| 2026-06-03 | scoped | Step 4.6 scope freeze | Status changed `draft` → `scoped`. Scope frozen with PF-R1/PF-R2 confirmed, PF-r1/PF-r2 carry-forward/export locks, tight-gate D6 cadence, and no abandonment blockers. |

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
| 2026-06-03 | Step 4.2 P1 — failed graph walk conflicts with shipped invariant | `Explanation.__post_init__` currently enforces `status == "passed" iff evidence is not None`, so a failed explanation cannot carry an `EvidenceGraph` without an explicit invariant change. Slice ε preserves that invariant by default: passed explanations walk evidence; failed explanations with no evidence produce deterministic failure summary lines. Atom-level `unsupport` rendering remains gated on Step 4.3 proving a safe failed+evidence path. |
| 2026-06-03 | Step 4.2 P2 — `repr` must be computed property, not constructor field | A dataclass field named `repr` would either become a constructor argument or block lazy property semantics. Slice ε instead adds an internal `_repr_cache` field and a public `@property repr`, preserving existing `Explanation(...)` construction sites. |
| 2026-06-03 | Step 4.2 P3 — walker must not require `head` | `Explanation` carries `row` and `evidence`, not `EvaluateResult` / `head`. η builders already put row/result rendering into `NODE_CONCLUSION.value_summary`; the walker should render existing node labels/summaries first and treat row as optional context. |
| 2026-06-03 | Step 4.2 P4 — service wire default remains unchanged | `src/service/runtime_v1.py` serializes `EvaluateResult` / rows, not `Explanation.repr` today. Step 4.3 still audits service paths, but default scope is no wire addition unless an explicit Explanation serializer is found. |
| 2026-06-03 | Step 4.3 PF-R1/PF-R2 confirmed | Preflight re-read `evaluate_result.py:291-292`, active failed Explanation constructors, and 7 active `Explanation(...)` construction sites. No new Required expansion is needed: failed repr remains summary-only and `repr` remains a computed property with no constructor argument. |
| 2026-06-03 | Step 4.3 PF-r1 — parent design wording carry-forward | Parent design has stale `row.repr` wording in the Slice epsilon area. This slice implements `Explanation.repr` only; `EvaluateRow.repr` remains out of scope. Parent-design wording sync is deferred like η D7. |
| 2026-06-03 | Step 4.3 PF-r2 — export scope lock | `walk_evidence(...)` defaults to protocol-layer helper exposure. No SDK `__all__` change is planned unless implementation discovers a concrete user-facing need. This preserves the export discipline validated in α/β/γ/ζ. |

## Cross-flip checkpoints (per [[feedback_audit_to_archive_cadence]] + Slice η D6 lock)

- [x] Step 4.1 blueprint draft (Claude — Slice 4/5 default)
- [x] Step 4.2 review + tightening (Codex per Slice 4/5 default)
- [x] Step 4.3 preflight on independent branch `v0.2.0-explanation-repr-walker-preflight-2026-06-03`
- [x] Step 4.4 preflight amendment
- [x] Step 4.5 self-check
- [x] Step 4.6 scope freeze
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
