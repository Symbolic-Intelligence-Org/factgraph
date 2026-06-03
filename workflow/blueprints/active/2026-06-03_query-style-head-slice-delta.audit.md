# Task Blueprint Audit: Query-style head Slice δ — `rule.id` decouple + arity opt-in

- Blueprint: [2026-06-03_query-style-head-slice-delta.md](./2026-06-03_query-style-head-slice-delta.md)
- Parent design: [`evaluate-result-flatten-and-query-style.zh.md`](../../design/design-points/active/evaluate-result-flatten-and-query-style.zh.md) §3.8 + §6 Slice δ
- Predecessors: α / β / γ / ζ / η / ε (all archived)
- Fork base: `dd65e776` (Slice ε Step 4.9 archive HEAD)
- **δ is the last slice in parent design chain**

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-03 | draft | Blueprint pair created | Initial scope recorded on `v0.2.0-blueprint-query-style-head-2026-06-03` (fork from `dd65e776`). Tight gates default — δ relaxes shipped strict invariant `rule.id` must match schema predicate. Cross-engine + backward compat scope must be enumerated at Step 4.3 preflight. Open Q G6 (arity mismatch severity Option A/B/C) was pending at draft and resolved by Step 4.2 Option A lock below. |
| 2026-06-03 | draft | Step 4.2 review + tightening | Folded P1-P5: locked G6 to Option A strict reject for matched-predicate arity mismatch; recorded that native free-form heads need a distinct query-style candidate construction branch because `candidates_from_bindings(...)` is schema-bound; expanded cross-engine scope to Souffle/ProbLog strict lookup sites; added service/runtime compiled-plan compatibility surface; confirmed `Rule` DTO already accepts arbitrary non-empty ids. Status remains `draft`. |
| 2026-06-03 | draft | Step 4.4 preflight amendment | Folded Step 4.3 preflight findings from `v0.2.0-query-style-head-preflight-2026-06-03@46e179d3`: native/Souffle/ProbLog runtime/import strict lookup paths are in scope; query-style candidates require a distinct helper/branch; `candidate_kind="fact"` + fact-like payload remains the δ compatibility default; service/runtime `target_pred_id` / `head_vars` keys are preserved; PyReason fact-conversion and read/query lookups are carved out. Status remains `draft`. |
| 2026-06-04 | draft | Step 4.5 self-check PASS | Verified PF-R1/PF-R2/PF-R3/PF-R4 + PF-r1/PF-r2/PF-r3 coverage across §5/§7/§8/§9; confirmed N9/N10 carve-outs, G6 Option A, CandidateSet compatibility payload, and service/runtime wire-key preservation are internally consistent. No stale blockers found; Q-PR1 and dirty-baseline boundaries remain preserved. |
| 2026-06-04 | scoped | Step 4.6 scope freeze | Status flipped `draft` → `scoped`. Scope frozen with native/Souffle/ProbLog opt-in schema lookup, query-style candidate helper/branch, `candidate_kind="fact"` compatibility payload, service/runtime wire-key preservation, PyReason/read-query exclusions, and strict-error docs cascade. |
| 2026-06-04 | scoped | Step 4.6.5 pre-impl grep amendment | Re-ran `find_schema_pred`, strict-error text, candidate-construction, and wire-key greps. No new production head-validation sites beyond PF-R1. Folded one active agent test expectation, broader docs wording cascade, and N11 test-local fake evaluator carve-out. Status remains `scoped`; no code implementation started. |

## Decision Notes

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-06-03 | Tight gates default | δ relaxes shipped strict invariant with cross-engine impact. Following Slice γ wrapper-removal pattern (also strict-invariant relaxation) over Slice ζ surface-fold pattern. |
| 2026-06-03 | G6 arity mismatch severity Option A locked at Step 4.2 | Strict reject preserves backward compat and avoids silent breakage for existing schema-backed `id="entity:field"` users. Query-style relaxation applies when `head.id` has no schema predicate match; matched-predicate heads remain opt-in to schema arity validation. Parent Option B/C remain future policy work. |
| 2026-06-03 | Stage 1 audit doc deferred per Slice 4/5 precedent | Stage-0 source audit folded into parent design + this blueprint draft + Step 4.3 preflight verifies via Rule 1 fresh reads. |
| 2026-06-03 | Cross-engine path verification critical at Step 4.3 A1 | Shipped `_evaluate.py:148-157` is native-only. Step 4.2 fresh read found Souffle (`engine_eval.py:118-127`) and ProbLog (`engine_eval.py:68-75`, `problog_import.py:110-119`) duplicate strict schema lookup/arity checks; PyReason fact conversion remains schema-backed and needs classification. |
| 2026-06-03 | δ closes parent design chain | After δ implemented + archived, evaluate-result-flatten parent design 7 slices (α-δ) all complete. Per `design/README.md` 三条件 (all questions closed / all impl-eligible content shipped / no active blueprints depend), design-point candidate for archive. |
| 2026-06-03 | Step 4.2 P2 — query-style candidates need a distinct builder branch | `candidates_from_bindings(...)` requires `schema_pred` / `arg_specs` / `group_key_indexes` and emits fact-shaped payloads. Free-form heads need a query-style branch derived from `head.ports` / `head_vars`; weakening the existing helper would risk schema-backed candidate regressions. |
| 2026-06-03 | Step 4.2 P5 — Rule DTO already permits free-form ids | `Rule.__post_init__` only requires `id` be a non-empty string. δ implementation should not touch Rule validation unless Step 4.3 finds a separate issue. |
| 2026-06-03 | Step 4.3 PF-R1 — cross-engine strict sites locked | Preflight confirmed native `_evaluate.py`, Souffle `engine_eval.py`, ProbLog runtime `engine_eval.py`, and ProbLog import `problog_import.py` all enforce strict schema lookup/arity. δ implementation scope includes all four. |
| 2026-06-03 | Step 4.3 PF-R2/PF-R3 — compatibility payload default | Because `CandidateSet(candidate_kind="fact")` canonical content requires `terms`, δ keeps `candidate_kind="fact"` and fact-like `{"pred_id": head.id, "terms": ...}` payloads for query-style candidates. New candidate kinds are deferred unless a later PF expands scope. |
| 2026-06-03 | Step 4.3 PF-r1/PF-r2 — exclusions | PyReason materialized fact conversion, `_queries.py`, and service read-query lookups are not derivation-head validation and stay out of scope unless implementation proves otherwise. |
| 2026-06-04 | Step 4.6.5 N-1/N-2/N-3 fold | N-1: `src/agent/tests/test_agent_l4a_workflow.py` still asserts the old free-form missing-predicate failure. N-2: docs strict-predicate wording is broader than PF-r3's four exact lines. N-3: `src/domains/ecss/tests/test_evidence_tree_explain_contracts.py` fake evaluators are schema-backed test fixtures and stay carved out unless tests prove otherwise. |

## Cross-flip checkpoints (per [[feedback_audit_to_archive_cadence]] + Slice η D6 lock)

- [x] Step 4.1 blueprint draft (Claude — Slice 4/5 default)
- [x] Step 4.2 review + tightening (Codex per Slice 4/5 default)
- [x] Step 4.3 preflight on independent branch `v0.2.0-query-style-head-preflight-2026-06-03`
- [x] Step 4.4 preflight amendment
- [x] Step 4.5 self-check
- [x] Step 4.6 scope freeze
- [x] Step 4.6.5 pre-impl grep
- [ ] Step 4.7 implementation on `v0.2.0-impl-query-style-head-2026-06-03` (individual report per D6)
- [ ] Step 4.8 closure (individual report per D6) + note δ closes parent design chain
- [ ] Step 4.9 archive
- [ ] **Post-δ**: consider archiving parent design-point per `design/README.md` 三条件

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
