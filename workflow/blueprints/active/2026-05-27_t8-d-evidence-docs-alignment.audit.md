# Audit: T8-D Evidence Docs Alignment

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-d-evidence-docs-alignment.md`
- Stage: closure
- Class: S/M (docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current four modified tracked docs/notebooks plus two untracked reference directories
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-D evidence docs alignment blueprint pair drafted | Triggered by shipped T8-A + T8-B-1 behavior; Q1-Q9 intentionally pending for source-backed Step 4.6. |
| 2026-05-27 | scoped | this commit | Step 4.6 docs inventory completed | Scope narrowed to `evidence.md` + `00_user_guide.en.md`; all other candidate docs leave-alone. |
| 2026-05-27 | implementation | `518c4e51` | Evidence quickstart aligned | T8-A metadata and T8-B-1 native Form 1 shipped behavior documented. |
| 2026-05-27 | implementation | `6a890e8e` | SDK user guide aligned | Concise native Form 1 evidence summary plus quickstart link. |
| 2026-05-27 | closure | this commit | Cycle closure recorded | Docs-only scope preserved; focused no-op baseline 36 OK. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8-A and T8-B-1 are both archived and published on this branch.
- The official evidence quickstart is the likely primary user-facing doc.
- SDK docs contain several evidence/explanation mentions and need per-file
  triage before any edit.
- Audit module docs were aligned by T7 and T8-B-1 and should be used as a
  reference rather than edited by default.

This draft scan is not a Step 4.6 answer. It intentionally avoids choosing
file scope or wording strategy before source-backed inventory.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which docs files must change and which should remain untouched? | **Answered:** edit `evidence.md` + `00_user_guide.en.md`; leave other candidates. |
| Q2 | What is the shape of the `evidence.md` update? | **Answered:** narrow §1/§5 notes plus §6 rewrite. |
| Q3 | Should docs show concrete Form 1 JSON / HTML render shape? | **Answered:** no full JSON/HTML; conceptual graph shape only. |
| Q4 | How should the 14-key metadata contract be presented? | **Answered:** full key list as v1 bridge, with DTO-first warning. |
| Q5 | How should hard vs soft graph failure be described? | **Answered:** user-facing soft `GRAPH_VALIDATION_FAILED`, hard protocol violation only as internal/advanced caveat. |
| Q6 | Where should deferred boundaries be marked? | **Answered:** dedicated §6 current-boundaries block. |
| Q7 | How should quickstart and SDK docs split responsibility? | **Answered:** quickstart owns detail; SDK guide summarizes and links. |
| Q8 | Should quickstart/SDK docs cross-link to audit module docs? | **Answered:** no direct user-facing link to module-implementer docs. |
| Q9 | Should docs cite tests or line numbers? | **Answered:** no; source refs stay in blueprint/audit. |

## 3.1 Step 4.6 Inventory Results

File scope:

| File | Decision | Evidence |
|---|---|---|
| `docs/official/kernel/quickstart/evidence.md` | Edit | §6 lines 244-269 still says graph interior is intentionally opaque and full graph tutorial is pending. |
| `src/factgraph/sdk/docs/00_user_guide.en.md` | Edit | Lines 644-656 summarize evidence path but do not mention native Form 1 or graph metadata boundary. |
| `docs/official/kernel/quickstart/rules-and-inferences.md` | Leave | Lines 752-758 only summarize evaluate/explain and link evidence docs. |
| `docs/official/kernel/quickstart/semantics.md` | Leave | Evidence mentions are workflow-only; no topology claim. |
| `docs/official/kernel/quickstart/namespace-map.md` | Leave | Namespace map should stay surface-oriented. |
| `src/factgraph/sdk/docs/01_concepts.en.md` | Leave | Conceptual mentions are correct and high-level. |
| `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` | Leave | Lines 557-575 already delegate full envelope chain to `evidence.md`. |
| `src/factgraph/sdk/docs/04_api_surface.en.md` | Leave | API surface docs should not teach graph topology. |
| `src/factgraph/sdk/docs/06_what_if_and_proof.en.md` | Leave | Workflow-only path remains correct. |
| `src/factgraph/sdk/docs/07_walker_and_advanced.en.md` | Leave | Advanced note points to public DTOs without stale topology. |
| `src/factgraph/audit/docs/02_evidence_graph.md` | Leave | Already aligned at lines 41-45, 80-101, 119-121, 168-174, 195-219. |

Shipped behavior refs:

- Metadata keys: `evaluate_result.py:59-75`.
- Soft graph validation failure: `evaluate_result.py:635-657`.
- Native Form 1 dispatch: `evaluate_result.py:839-847`.
- Native Form 1 node/edge shape: `evaluate_result.py:866-980`.
- Metadata validation: `evaluate_result.py:1049-1071`.
- Renderer type guard: `evidence_graph.py:120-128`.
- Large graph warning: `evidence_graph.py:471-486`.

Focused no-op baseline:

```text
PYTHONPATH=src python -m unittest \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.application.protocol.test_evaluate_result_dtos
→ 36 OK
```

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Docs teach deferred behavior as shipped | Users depend on unavailable adapter/failed-graph/match-witness behavior | Build explicit shipped/deferred map before editing. |
| File scope balloons | Docs-only cycle becomes broad rewrite | Per-file triage and stop if more than five secondary files need non-trivial edits. |
| Quickstart over-specifies internals | Users depend on implementation-only `engine_meta` details | Decide example granularity before implementation. |
| SDK docs duplicate quickstart heavily | Drift risk between public docs surfaces | Lock quickstart vs SDK role split. |
| Runtime/test edit temptation | Violates T8-D docs-only purpose | Stop if any docs gap requires code/test changes. |
| Dirty baseline edited accidentally | Workflow violation | Status checks before commit/closure. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q9 answered.
- [x] File scope locked.
- [x] Shipped/deferred evidence behavior map complete.
- [x] Docs-only boundary preserved.
- [x] Closure notes filled.

## 6. Closure Notes

T8-D shipped as a docs-only A+B evidence alignment cycle.

Landed chain:

```text
14d1129f  docs(blueprint): draft T8-D evidence docs alignment
df20a64e  docs(blueprint): scope T8-D evidence docs alignment
518c4e51  docs(quickstart): align evidence with native form1 graphs
6a890e8e  docs(sdk): summarize native form1 evidence
```

Docs outcome:

- `evidence.md` no longer describes `EvidenceGraph` as intentionally opaque.
  It now teaches native row Form 1 as the shipped shape:
  `NODE_SEED --supports--> NODE_PREMISE --supports--> NODE_CONCLUSION`.
- The metadata bridge is complete but user-safe: all 14 shipped v1 keys are
  represented through prose grouping, and users are directed to typed DTO fields
  instead of metadata set equality.
- The quickstart documents `GRAPH_VALIDATION_FAILED` as the soft unsupported
  path and treats non-`EvidenceGraph` builder returns as internal protocol
  contract violations.
- The quickstart records the full deferred boundary map for adapter Form 1,
  aggregates, failed/why-not/counterfactual graphs, match witness output,
  cross-row seed reuse, sessions/signatures/ACL/x-evidence-key/salience/impact,
  `EDGE_DERIVES`/`EDGE_UPDATES`, `dag`, and `rule_fire`.
- The SDK user guide adds only an eight-line summary and links to the
  quickstart, avoiding duplication.

Verification:

- Focused no-op evidence baseline: 36 OK.
- `git diff --check` clean.
- Changed implementation files since scoped: exactly `evidence.md` and
  `00_user_guide.en.md`.

Scope preservation:

- No runtime/test/release/audit-module docs changes.
- No `src/factgraph/audit/docs/02_evidence_graph.md` edit.
- No SDK API, service/OpenAPI, Database/view, dirty-baseline, or sacred-master
  changes.
