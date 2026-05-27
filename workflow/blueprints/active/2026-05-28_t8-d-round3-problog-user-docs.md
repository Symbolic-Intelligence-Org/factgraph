# Task Blueprint: T8-D Round 3 ProbLog User Docs

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S (docs-only)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t8-d-round3-problog-user-docs.audit.md`
- Trigger: T8-C-1 ProbLog evidence enrichment runtime shipped at `5ffd4850`; audit docs were aligned by `a916a856`. This cycle updates the two user-facing evidence docs to reflect shipped ProbLog row provenance graphs while keeping PyReason and other evidence surfaces deferred.

## 0. Scope Locks

### In scope

This is a docs-only user-facing alignment cycle. Round 3 is **not** a symmetric
native/Souffle Form 1 expansion. It must teach ProbLog row provenance graphs as
a sibling shipped row-level shape.

Candidate scope:

1. Source-backed inventory of the current `docs/official/kernel/quickstart/evidence.md`
   wording around Form 1, ProbLog/PyReason deferred boundaries, and edge-kind
   reservations.
2. Source-backed inventory of the current
   `src/factgraph/sdk/docs/00_user_guide.en.md` evidence summary.
3. `evidence.md` edits only:
   - Section 6 title.
   - A new concise ProbLog provenance-row paragraph.
   - The fallback / adapter-specific graph-shape paragraph.
   - The Current boundaries ProbLog/PyReason line.
   - The `EDGE_DERIVES` / `EDGE_UPDATES` reservation line.
4. SDK guide edit only:
   - Extend the concise row evidence summary to native/Souffle Form 1 plus
     ProbLog row provenance graphs.
   - Keep the full DTO chain delegated to the evidence quickstart.

### Out of scope

- Runtime code changes.
- Test code changes.
- Governance / workflow files.
- Sacred `master` changes.
- Dirty baseline changes. Current observed baseline is `4 M + 1 D + 5 U`.
- Audit module docs; T8-C-1 already aligned
  `src/factgraph/audit/docs/02_evidence_graph.md`.
- User-facing docs beyond the two target files.
- PyReason row evidence, PyReason Form 2, Nemo, C119 full multi-path DAG,
  aggregate envelopes, failed graph, why-not, counterfactual, or match witness.
- T10-2 / T10-3 / C74 / C77 / C78 work.
- D20, service/OpenAPI, Database/view, release, PyPI, or tags.
- Re-teaching ProbLog SDK API / `ProbLogSemantics`.
- Expanding the full `engine_meta["problog"]` schema or dumping JSON/HTML.
- Re-teaching ProbLog `raw_kind` / `bound` assertion annotation syntax.
- Teaching audit/proof-tree converter internals beyond shipped row provenance
  graph behavior.
- Changing the existing 14-key metadata explanation.
- Changing native/Souffle Form 1 ASCII topology or Form 1 semantics.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

1. T8-C-1 runtime behavior differs from audit docs commit `a916a856` or archive
   `5ffd4850`.
2. The file scope needs to exceed `evidence.md` and SDK `00_user_guide.en.md`.
3. A docs edit would imply a new runtime/API contract rather than reflecting
   shipped T8-C-1 behavior.
4. Scope touches runtime, tests, audit module docs, governance, release,
   service/OpenAPI, Database/view, or dirty baseline files.

## 1. Problem

T8-D round 1 documented T8-A metadata validation and T8-B-1 native Form 1.
T8-D round 2 documented Souffle row Form 1 by symmetrically expanding native
wording to native + Souffle. T8-C-1 now shipped ProbLog row-level evidence, but
it is not Form 1: it is a provenance-row graph with `EDGE_DERIVES`,
`PROBLOG_PROVENANCE_KIND`, and namespaced `engine_meta["problog"]`.

The current user docs still group ProbLog with future row-level Form 1 work.
Round 3 must fix that user-facing drift without implying ProbLog uses the
native/Souffle Form 1 `EDGE_SUPPORTS` shape.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-28_t8-c-1-problog-evidence-enrichment-runtime.md` | Shipped runtime source and closure facts. |
| `workflow/blueprints/archive/2026-05-28_t8-c-1-problog-evidence-enrichment-runtime.audit.md` | Audit trail, verification, and deviations. |
| `src/factgraph/audit/docs/02_evidence_graph.md` | Already-aligned audit-module wording source from `a916a856`. |
| `docs/official/kernel/quickstart/evidence.md` | Primary user-facing target. |
| `src/factgraph/sdk/docs/00_user_guide.en.md` | SDK summary target. |
| `workflow/blueprints/archive/2026-05-27_t8-d-round2-souffle-user-docs.md` | Round 2 docs-only cadence and discipline reference. |

## 3. Step 4.6 Source-Backed Inventory

### 3.1 `evidence.md` Edit Inventory

| Location | Current wording | Decision |
|---|---|---|
| `docs/official/kernel/quickstart/evidence.md:260` | `## 6. EvidenceGraph — shipped native and Souffle Form 1 graph (v0.2)` | Edit title to neutral shipped row-level graphs wording, such as `shipped row-level graphs (v0.2)`, so the section can contain both native/Souffle Form 1 and ProbLog provenance-row shapes. |
| `evidence.md:262-281` | Native/Souffle Form 1 intro and ASCII topology. | Preserve the Form 1 paragraph and ASCII `NODE_SEED --supports--> NODE_PREMISE --supports--> NODE_CONCLUSION` block byte-for-byte except wrapping if needed; add a separate ProbLog provenance-row paragraph immediately after it. |
| `evidence.md:283-286` | Rows without native/Souffle support fall back; other adapter rows may use fallback or adapter-specific graph shapes until Form 1 alignment lands. | Remove ProbLog from the fallback implication. New wording should say manually constructed/detached rows still use fallback, ProbLog passed rows now use row provenance graphs, and other unaligned adapters may still fall back. |
| `evidence.md:302` | `ProbLog / PyReason row-level Form 1 alignment is future work.` | Replace with a PyReason-only future boundary. Do not teach ProbLog as Form 1; it is shipped as row provenance evidence. |
| `evidence.md:311-312` | ``EDGE_DERIVES` and `EDGE_UPDATES` are reserved for Form 2 / temporal engine paths. Native and Souffle Form 1 row graphs use `EDGE_SUPPORTS`.` | Match audit docs: native/Souffle use `EDGE_SUPPORTS`, ProbLog row provenance graphs use `EDGE_DERIVES`, and `EDGE_UPDATES` remains reserved for PyReason / Form 2 / temporal paths. |

The new ProbLog paragraph should be concise and user-facing:

- ProbLog passed rows now produce row-level provenance graphs.
- Their proof-trace shape uses `derives` edges, not Form 1 `supports` edges.
- A short ASCII example is useful:
  `NODE_SEED --derives--> NODE_PREMISE --derives--> NODE_CONCLUSION`.
- Top-level metadata remains the same row/result audit context.
- ProbLog trace summary and uncertainty projection details live under
  `engine_meta["problog"]`; do not dump the schema.

### 3.2 SDK User Guide Edit Inventory

`src/factgraph/sdk/docs/00_user_guide.en.md:658-665` currently says native or
Souffle rows produce row-level Form 1 graphs and treats `ProbLog/PyReason Form
1 graphs` as future work.

Decision:

- Keep the concise summary style and quickstart link.
- Preserve native/Souffle Form 1 as the first sentence.
- Add one short sentence for ProbLog row provenance graphs using `derives` edges
  with trace / uncertainty-projection details under `engine_meta["problog"]`.
- Change future work from `ProbLog/PyReason Form 1 graphs` to PyReason-only
  row evidence / Form 1 wording while preserving aggregate, failed-graph, and
  match witness future tracks.

### 3.3 Leave-Alone File Sweep

| File | Finding | Decision |
|---|---|---|
| `src/factgraph/audit/docs/02_evidence_graph.md` | Already aligned by T8-C-1: lines 48-52 teach ProbLog row provenance graphs; lines 126-128 assign `derives` to ProbLog and reserve `updates`; lines 203-208 describe live ProbLog row provenance graphs. | Leave. It is the wording source, not an edit target. |
| `docs/official/kernel/quickstart/namespace-map.md` | ProbLog appears only as semantics / engine naming context. | Leave. No row-evidence boundary. |
| `docs/official/kernel/quickstart/semantics.md` | Teaches `ProbLogSemantics` and `PyReasonSemantics`. | Leave. T10-1 / semantics wrapper docs are separate. |
| `docs/official/kernel/quickstart/assertions.md` | Teaches ProbLog semantic probability annotation context. | Leave. Do not re-teach raw uncertainty carriers here. |
| `docs/official/kernel/quickstart/rules-and-inferences.md` | Lines 620ff discuss high-level engine lifecycle and semantics options. | Leave. No stale row evidence contract. |
| `src/factgraph/sdk/docs/01_concepts.en.md` | ProbLog appears as adapter / semantics concept. | Leave. No row evidence section. |
| `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md` | Mentions ProbLog annotation namespaces and export behavior. | Leave. T10-1 semantics/execution topic, not user evidence summary. |
| `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` | Delegates evidence chain detail to evidence docs; mentions engine support table. | Leave. Existing delegation remains correct. |

### 3.4 Audit Docs Consistency Cross-Check

`src/factgraph/audit/docs/02_evidence_graph.md` is consistent with the planned
user wording:

- Lines 41-45: native/Souffle row explanations are Form 1 with `supports`
  edges.
- Lines 48-52: ProbLog row explanations are provenance-row graphs rather than
  Form 1 graphs, and ProbLog trace / uncertainty-projection details live under
  `engine_meta["problog"]`.
- Lines 126-128: native/Souffle use `supports`, ProbLog uses `derives`, and
  `updates` remains reserved for PyReason / temporal paths.
- Lines 203-208: audit package docs distinguish native/Souffle live Form 1
  row graphs from ProbLog live row-level provenance graphs.

No behavior/doc mismatch found; no stop trigger.

## 4. Step 4.6 Open Questions

| ID | Answer |
|---|---|---|
| Q1 | Yes: exactly `docs/official/kernel/quickstart/evidence.md` and `src/factgraph/sdk/docs/00_user_guide.en.md`. Leave-alone sweep found other ProbLog hits are semantics, annotation, adapter concept, or already-aligned audit docs. |
| Q2 | Edit `evidence.md` §6 only: title line 260; preserve native/Souffle Form 1 body lines 262-281 and add a separate ProbLog paragraph; adjust fallback paragraph lines 283-286; replace deferred boundary line 302; replace edge-kind line 311-312. |
| Q3 | Edit SDK guide lines 658-665 only: keep native/Souffle Form 1 summary, add a concise ProbLog provenance sentence, and remove ProbLog from the future evidence tracks sentence. |
| Q4 | Replace `ProbLog / PyReason row-level Form 1 alignment is future work.` with PyReason-only future wording. ProbLog is shipped as row provenance evidence, not Form 1. |
| Q5 | Match audit docs: native/Souffle row Form 1 graphs use `EDGE_SUPPORTS`; ProbLog row provenance graphs use `EDGE_DERIVES`; `EDGE_UPDATES` remains reserved for PyReason / Form 2 / temporal paths. |
| Q6 | Yes, add one short ASCII line for ProbLog provenance: `NODE_SEED --derives--> NODE_PREMISE --derives--> NODE_CONCLUSION`. It is intentionally separate from the Form 1 `supports` ASCII block. |
| Q7 | Mention only that ProbLog trace summary and uncertainty projection details live under `engine_meta["problog"]`; do not enumerate subkeys or JSON. No audit-module cross-link is needed in the user docs. |
| Q8 | Use docs-only focused baseline plus the direct T8-C-1 sanity test: `tests.test_audit_evidence_graph`, `tests.test_audit_evidence_graph_render`, `tests.application.protocol.test_evaluate_result_dtos`, `tests.test_problog_evidence_graph`, and `tests.test_problog_semantics_profile_migration`; then `git diff --check`, status, and sacred-master check. |
| Q9 | None. T8-C-1 behavior matches audit docs, file scope is exactly two user docs, and no implementation/governance/dirty-baseline change is needed. |

## 5. Existing Invariants To Preserve

- Docs-only: no runtime or test edits.
- T8-C-1 runtime and audit docs are the source of truth; this cycle reflects
  shipped behavior and does not redesign it.
- Native/Souffle Form 1 topology and wording remain valid.
- ProbLog row provenance graph is taught as a sibling row-level evidence shape,
  not as Form 1.
- Top-level row graph metadata remains the same 14-key bridge.
- `run_id` remains envelope-only.
- ProbLog `engine_meta["problog"]` is mentioned but not expanded into a full
  schema.
- T10-1 anti-silent-ignore behavior stays an implementation detail; user docs
  should not teach reject failures as row evidence.
- PyReason, aggregate envelope, C119 multi-path DAG, failed/why-not,
  counterfactual, match witness, and session/signature/ACL evidence channels
  remain future.
- User-facing docs defer detailed SDK/semantics and assertion annotation syntax
  to their existing pages; this cycle should not duplicate them.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains `4 M + 1 D + 5 U`.

## 6. Step 4.6 Inventory Plan

Step 4.6 must run source-backed checks, including:

```bash
rg -n "Form 1|ProbLog|PyReason|EDGE_DERIVES|EDGE_UPDATES|Current boundaries|supports|derives" docs/official/kernel/quickstart/evidence.md
rg -n "row\\.explain\\(\\)\\.evidence|ProbLog|PyReason|Form 1|supports|derives" src/factgraph/sdk/docs/00_user_guide.en.md
rg -n "ProbLog row|EDGE_DERIVES|engine_meta\\[\"problog\"\\]|EDGE_UPDATES|Form 1" src/factgraph/audit/docs/02_evidence_graph.md
rg -n "ProbLog|EvidenceGraph|row-level|Form 1" docs/official/kernel/quickstart src/factgraph/sdk/docs
```

Expected Step 4.6 outputs:

1. Source-backed two-file scope.
2. `evidence.md` line-level edit map.
3. SDK guide line-level edit map.
4. Leave-alone file table.
5. Audit-docs consistency check.
6. Verification baseline plan.

## 7. Proposed Implementation Shape

Candidate split:

1. `docs(quickstart): mark problog row provenance graph shipped`
2. `docs(sdk-guide): mark problog row provenance graph shipped`
3. `docs(blueprint): close T8-D round 3 problog user docs`
4. `docs(blueprint): archive T8-D round 3 problog user docs`

If edits are tiny, the two user-doc commits may be combined if the audit notes
why the quickstart-detail / SDK-summary boundary remains clear.

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed inventory completed.
- [x] Q1-Q9 answered.
- [x] File scope remains exactly the two user-facing docs files.
- [x] Quickstart teaches ProbLog row provenance graphs as shipped but not Form 1.
- [x] SDK guide remains concise and links to quickstart for full detail.
- [x] PyReason and all non-shipped evidence tracks remain deferred.
- [x] Audit module docs, runtime, tests, governance, release, service/OpenAPI,
      Database/view, and dirty-baseline files are untouched.
- [x] Focused docs-only verification passes.
- [x] `git diff --check` clean.
- [x] Dirty baseline and sacred master preserved.

## 9. Verification Commands

Candidate docs-only checks:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.application.protocol.test_evaluate_result_dtos \
  tests.test_problog_evidence_graph \
  tests.test_problog_semantics_profile_migration

git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Implemented and reviewed.

### Cycle chain

| Commit | Stage | Notes |
|---|---|---|
| `e13686db` | Draft | Opened T8-D round 3 ProbLog user-docs alignment cycle. |
| `38ae43a9` | Scoped | Locked two-file user-doc scope and source-backed Q1-Q9 answers. |
| `902f1b76` | Quickstart docs | Updated `evidence.md` to teach ProbLog row provenance graphs as shipped without calling them Form 1. |
| `6098b9a8` | SDK guide docs | Updated SDK guide summary with a concise ProbLog row provenance sentence and PyReason-only future wording. |

### Shipped docs alignment

- Quickstart §6 now uses neutral shipped row-level graph wording.
- Native/Souffle Form 1 text, ASCII topology, and `winning_path_only` wording
  were preserved.
- ProbLog passed rows are taught as row-level provenance graphs with
  `derives` edges, a separate ASCII shape, and high-level
  `engine_meta["problog"]` placement.
- ProbLog was removed from the future boundary; PyReason row-level alignment
  remains future.
- Edge-kind wording now matches audit docs: native/Souffle use `EDGE_SUPPORTS`,
  ProbLog uses `EDGE_DERIVES`, and `EDGE_UPDATES` remains reserved for PyReason
  / Form 2 / temporal paths.
- SDK guide remains a concise summary and still delegates the full DTO chain to
  the evidence quickstart.
- Audit module docs, runtime, tests, governance, release, service/OpenAPI,
  Database/view docs, and dirty-baseline files were not edited.

### Verification

- Focused docs-only baseline plus T8-C-1 sanity:
  `PYTHONPATH=src python -m unittest tests.test_audit_evidence_graph tests.test_audit_evidence_graph_render tests.application.protocol.test_evaluate_result_dtos tests.test_problog_evidence_graph tests.test_problog_semantics_profile_migration`
  ran 67 tests OK.
- `git diff --check` clean.
- Sacred `master` stayed at `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline preserved as `4 M + 1 D + 5 U`.

### Notes

- The wording intentionally uses `row-level alignment` for remaining adapter
  future work because PyReason may ship as Form 2 rather than Form 1.
- User docs mention only that ProbLog trace summary and uncertainty projection
  details live under `engine_meta["problog"]`; the implementation schema stays
  out of user docs.
