# Task Blueprint: T8-D Round 3 ProbLog User Docs

- Status: draft
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

Pending Step 4.6. Required subsections:

### 3.1 `evidence.md` Edit Inventory

Source-back the five current wording locations:

1. Section 6 title.
2. Form 1 intro / native-Souffle body.
3. Fallback / adapter-specific graph paragraph.
4. Current boundaries ProbLog/PyReason line.
5. `EDGE_DERIVES` / `EDGE_UPDATES` reservation line.

### 3.2 SDK User Guide Edit Inventory

Source-back the concise evidence summary around `row.explain().evidence` and
the future evidence tracks sentence.

### 3.3 Leave-Alone File Sweep

Verify nearby quickstart / SDK docs do not require edits:

- `src/factgraph/audit/docs/02_evidence_graph.md`
- `docs/official/kernel/quickstart/namespace-map.md`
- `docs/official/kernel/quickstart/semantics.md`
- `docs/official/kernel/quickstart/assertions.md`
- `docs/official/kernel/quickstart/rules-and-inferences.md`
- `src/factgraph/sdk/docs/01_concepts.en.md`
- `src/factgraph/sdk/docs/02_readwrite_and_ingest.en.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`

### 3.4 Audit Docs Consistency Cross-Check

Cross-check planned user wording against `a916a856` audit docs:

- Native/Souffle row graphs remain Form 1 with `EDGE_SUPPORTS`.
- ProbLog row graphs are provenance-row graphs with `EDGE_DERIVES`.
- `EDGE_UPDATES` remains reserved for PyReason / Form 2 / temporal paths.
- ProbLog details are namespaced under `engine_meta["problog"]`.

## 4. Step 4.6 Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | Is the file scope exactly two user docs? | Yes/no with source-backed leave-alone rationale. |
| Q2 | What is the `evidence.md` edit map? | Five location table with line refs and narrow wording decisions. |
| Q3 | What is the SDK guide edit map? | Line refs and concise summary wording decision. |
| Q4 | How should the deferred boundary change? | Remove ProbLog from future row evidence without teaching ProbLog Form 1. |
| Q5 | How should the edge-kind reservation line change? | Match audit docs: native/Souffle `supports`, ProbLog `derives`, PyReason `updates` future. |
| Q6 | Should the quickstart add a ProbLog ASCII topology example? | Yes/no with rationale; if yes, keep it short and distinct from Form 1. |
| Q7 | How much `engine_meta["problog"]` detail should user docs teach? | Likely one sentence only; no full schema dump. |
| Q8 | What verification baseline is appropriate? | Docs-only focused baseline plus `git diff --check` and status checks. |
| Q9 | Are any stop/amend triggers hit? | None or explicit trigger with next action. |

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

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed inventory completed.
- [ ] Q1-Q9 answered.
- [ ] File scope remains exactly the two user-facing docs files.
- [ ] Quickstart teaches ProbLog row provenance graphs as shipped but not Form 1.
- [ ] SDK guide remains concise and links to quickstart for full detail.
- [ ] PyReason and all non-shipped evidence tracks remain deferred.
- [ ] Audit module docs, runtime, tests, governance, release, service/OpenAPI,
      Database/view, and dirty-baseline files are untouched.
- [ ] Focused docs-only verification passes.
- [ ] `git diff --check` clean.
- [ ] Dirty baseline and sacred master preserved.

## 9. Verification Commands

Candidate docs-only checks:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.application.protocol.test_evaluate_result_dtos \
  tests.test_problog_evidence_graph

git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending Step 4.6 / implementation / closure.
