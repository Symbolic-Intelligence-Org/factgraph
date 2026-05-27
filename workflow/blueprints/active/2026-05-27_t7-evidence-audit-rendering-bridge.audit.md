# Audit: T7 Evidence Audit + Rendering Bridge

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t7-evidence-audit-rendering-bridge.md`
- Stage: draft
- Class: M/L
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current 4 modified tracked files plus untracked `rainbird-ai sdk code/`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T7 blueprint pair drafted | Triggered by user selection after T6 design published and T11.2.10 OR match runtime completed. |

## 2. Draft Source Scan

Read-only draft scan findings:

- `src/factgraph/audit/evidence_graph.py` already contains the primary runtime
  artifacts: `EvidenceNode`, `EvidenceEdge`, `EvidenceGraph`,
  `evidence_graph_to_dict(...)`, `evidence_graph_from_dict(...)`, and
  `render_evidence_graph_html(...)`.
- `EvidenceGraph` construction already validates enum layout, duplicate
  node/edge ids, root membership, edge endpoints, and graph cycles.
- The renderer already has `tree` and `timeline` dispatch paths.
- T6 `evidence-tree-rainbird-style-v1.zh.md` §10 and §11 now define the
  design-side audit and renderer contracts that T7 should compare against.
- The initial scan did not answer Q1-Q8. Those answers must be produced in
  Step 4.6 with source-backed file:line refs.

## 3. Step 4.6 Inventory Plan

| # | Item | Status |
|---|---|---|
| 1 | `EvidenceGraph` DTO fields, immutability, validation, and roundtrip refs | Pending |
| 2 | Renderer entrypoints, layouts, unsupported layout, and HTML behavior refs | Pending |
| 3 | Minimal / empty / invalid / large graph current behavior | Pending |
| 4 | `EvaluateResult`, `Explanation`, and metadata bridge field refs | Pending |
| 5 | Audit module docs gap list against T6 §10/§11 | Pending |
| 6 | Existing focused test coverage map | Pending |
| 7 | T6 §10/§11 shipped / partial / missing matrix | Pending |
| 8 | T8-A/B/C/D T7-in vs T7-out mapping | Pending |
| 9 | D1-D20 triggered item scan | Pending |
| 10 | Test matrix and test file plan | Pending |
| 11 | Verification commands and known unrelated full-discover state | Pending |
| 12 | Dirty baseline and sacred master preservation | Pending |
| 13 | Stop/amend findings | Pending |

## 4. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Does current `EvidenceGraph` DTO + JSON roundtrip + renderer fully cover T6 §10 sessionless three-layer metadata contract? | Pending Step 4.6 |
| Q2 | Is there runtime layered consistency checking between `EvaluateResult`, row `Explanation`, and `EvidenceGraph.metadata`; if not, where should it live? | Pending Step 4.6 |
| Q3 | Does `render_evidence_graph_html(...)` implement the §11 `>250` node / `>500` edge warning or handoff path? | Pending Step 4.6 |
| Q4 | What is current minimal / empty / invalid / unsupported render behavior, and does it match §11? | Pending Step 4.6 |
| Q5 | Which T8-A/B/C/D slices, if any, are bridge-class T7 scope? | Pending Step 4.6 |
| Q6 | Which D1-D20 items are triggered by T7? | Pending Step 4.6 |
| Q7 | What must change in `src/factgraph/audit/docs/02_evidence_graph.md`? | Pending Step 4.6 |
| Q8 | What exact tests cover metadata consistency, roundtrip, threshold warning, fallback cases, and relevant regressions? | Pending Step 4.6 |

## 5. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| T7 expands into T8 graph construction | L-class implementation drift | Explicitly map T8-A/B/C/D to T7-in or T7-out. |
| Runtime bridge breaks existing graph dict compatibility | Audit package regression | Inventory current dict shape and add roundtrip regression tests if touched. |
| Session/audit v2 features leak into v1 | Violates T6 sessionless boundary | Keep session logs, signatures, ACL, and interactions out of scope. |
| Renderer starts making product UI promises | Overclaims reference renderer | Lock reference-vs-product boundary from §11. |
| Metadata checks are placed at the wrong layer | Confusing or duplicated invariants | Source-map `EvaluateResult`, `Explanation`, and graph metadata first. |
| Full test discovery failures obscure T7 signal | Closure ambiguity | Record focused results and full-discover status separately. |

## 6. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q8 answered.
- [ ] Runtime bridge changes reviewed, if any.
- [ ] Tests reviewed.
- [ ] Docs/design updates reviewed.
- [ ] Closure notes filled.

## 7. Closure Notes

Pending implementation.
