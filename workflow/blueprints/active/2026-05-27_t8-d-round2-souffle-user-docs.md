# Task Blueprint: T8-D Round 2 Souffle User Docs

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S (docs-only, pending Step 4.6)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-d-round2-souffle-user-docs.audit.md`
- Trigger: T8-B-2 Souffle row Form 1 conformance shipped at `5fcf7722`; T8-B-2 scoped Q8 and closure registered a T8-D round 2 follow-up for user-facing Souffle docs.

## 0. Scope Locks

### In scope

This is a docs-only alignment cycle and a narrow mirror of T8-D first round.
Step 4.6 must confirm exact wording gaps before edits. Candidate scope:

1. Source-backed inventory of the current user-facing docs wording around native
   Form 1, Souffle, row explanations, and deferred adapter behavior.
2. Primary target: `docs/official/kernel/quickstart/evidence.md`.
3. Secondary target: `src/factgraph/sdk/docs/00_user_guide.en.md`.
4. Symmetric expansion of shipped row Form 1 wording from native-only to native
   + Souffle where T8-B-2 made the behavior identical.
5. Removal of Souffle from deferred row-level Form 1 boundary wording while
   preserving ProbLog / PyReason as future T8-C.
6. Preservation of T8-D first-round discipline: no full JSON/HTML dump, no
   source/test line refs in user docs, no audit-module cross-link, quickstart
   owns detail, SDK guide stays summary + link.

### Out of scope

- Any runtime code changes.
- Any test code changes.
- T8-C engine enrichment, ProbLog row Form 1, PyReason row Form 1, aggregate
  count-only envelope, D20 match witness, failed graph, why-not,
  counterfactual, service/OpenAPI docs, Database/view docs, release machinery,
  PyPI, tags, or dirty-baseline cleanup.
- Audit module docs; T8-B-2 already aligned
  `src/factgraph/audit/docs/02_evidence_graph.md`.
- Any content beyond symmetric native -> native + Souffle user-doc alignment.
- Changing the existing 14-key metadata explanation, hard/soft failure
  explanation, ASCII topology shape, or deferred boundary list except for
  moving Souffle from future row-level Form 1 to shipped row-level Form 1.
- Touching dirty baseline files.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

- T8-B-2 Souffle row Form 1 behavior is not shape-equivalent to native and
  requires Souffle-specific user-facing explanation.
- The file scope must exceed the two T8-D first-round user-facing docs files.
- Any docs change would imply a new runtime/API contract.
- Scope touches runtime, tests, audit module docs, release machinery, service,
  OpenAPI, Database/view docs, or dirty baseline.

## 1. Problem

T8-D first round documented T8-A metadata validation and T8-B-1 native Form 1
row evidence. T8-B-2 then shipped Souffle row Form 1 through the same
row-result helper shape. User-facing docs now need a small follow-up so they do
not keep teaching Souffle row-level Form 1 as future work.

The risk is scope creep. This cycle should not introduce new evidence design or
expand into T8-C. It should only reflect the shipped Souffle row-level behavior
and keep the same user-facing boundaries as T8-D first round.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t8-d-evidence-docs-alignment.md` | First-round T8-D pattern and scope discipline. |
| `workflow/blueprints/archive/2026-05-27_t8-d-evidence-docs-alignment.audit.md` | First-round audit / Q1-Q9 pattern. |
| `workflow/blueprints/archive/2026-05-27_t8-b-2-souffle-form1-conformance.md` | Shipped Souffle row Form 1 behavior source. |
| `workflow/blueprints/archive/2026-05-27_t8-b-2-souffle-form1-conformance.audit.md` | T8-B-2 closure and verification source. |
| `docs/official/kernel/quickstart/evidence.md` | Primary user-facing evidence docs target. |
| `src/factgraph/sdk/docs/00_user_guide.en.md` | SDK user-guide summary target. |
| `src/factgraph/audit/docs/02_evidence_graph.md` | Already-aligned audit-module reference; not a default edit target. |

## 3. Draft Source Scan

Draft orientation only:

- `docs/official/kernel/quickstart/evidence.md` currently contains native-only
  Form 1 wording and still mentions Souffle row-level Form 1 as future work.
- `src/factgraph/sdk/docs/00_user_guide.en.md` currently contains a concise
  native-only Form 1 summary.
- T8-B-2 archive records that Souffle row explanations now use the same
  `_build_form1_evidence_graph(...)` row-result path as native.
- Audit module docs were already updated by T8-B-2 and should be used as a
  wording reference, not edited by default.

This scan does not answer Q1-Q8. Step 4.6 must replace it with source-backed
line refs and exact edit decisions.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Is the file scope exactly `evidence.md` + SDK `00_user_guide.en.md`? | Per-file diagnosis for target and non-target docs, with edit/leave decision. |
| Q2 | Which exact `evidence.md` locations need native -> native + Souffle expansion? | Line refs and a narrow edit map. |
| Q3 | Which exact SDK user-guide locations need native -> native + Souffle expansion? | Line refs and a narrow edit map. |
| Q4 | How should the "Current boundaries" deferred row-level Form 1 line change? | Wording decision that removes Souffle but keeps ProbLog/PyReason deferred. |
| Q5 | Does the existing ASCII Form 1 topology remain valid for Souffle? | Source-backed yes/no and decision to preserve or amend. |
| Q6 | Does the `winning_path_only` marker apply to Souffle user docs? | Source-backed yes/no and wording decision. |
| Q7 | What verification is appropriate for docs-only round 2? | Focused no-op baseline / `git diff --check` plan. |
| Q8 | Should user docs mention Souffle proof-tree converter boundary? | In-cycle vs omit/leave-to-audit-docs decision. |

## 5. Existing Invariants To Preserve

- Docs-only: no runtime or test edits.
- Keep quickstart / SDK user-facing docs aligned with shipped native + Souffle
  row-level Form 1 only.
- Do not teach ProbLog / PyReason row-level Form 1 as shipped.
- Do not teach aggregate envelope, failed graph, why-not, counterfactual, match
  witness, cross-row seed dedup, sessions/interactions, signatures, ACL,
  `x-evidence-key`, salience, impact, `EDGE_DERIVES`, `EDGE_UPDATES`, `dag`,
  or `rule_fire` as shipped.
- Preserve T8-D first-round metadata, failure-mode, and topology explanations
  except where "native" must become "native and Souffle".
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains `4 M + 1 D + 3 U` and must not be touched.

## 6. Step 4.6 Inventory Plan

Step 4.6 must produce:

1. Per-file wording refs for `evidence.md` and SDK `00_user_guide.en.md`.
2. Leave-alone check for nearby docs if grep finds relevant mentions.
3. Source-backed shipped-behavior refs from T8-B-2 archive.
4. Exact two-file edit plan or stop/amend if more files are needed.
5. Deferred boundary edit plan.
6. Verification plan and dirty/sacred status.

## 7. Proposed Implementation Shape

Implementation is intentionally narrow and pending Step 4.6:

1. Quickstart docs commit: native -> native + Souffle wording in the existing
   EvidenceGraph section, and deferred boundary update.
2. SDK docs commit: concise summary wording update, avoiding duplication.
3. Closure / archive.

## 8. Acceptance

- [ ] Step 4.6 answers Q1-Q8 with source-backed evidence.
- [ ] File scope is exactly the two user-facing docs files or the cycle is
      amended before edits.
- [ ] Quickstart no longer teaches Souffle row-level Form 1 as future work.
- [ ] SDK user guide summarizes native + Souffle without duplicating
      quickstart detail.
- [ ] ProbLog / PyReason and all other deferred items remain marked future.
- [ ] No runtime, test, audit-module docs, release, service/OpenAPI,
      Database/view, or dirty-baseline files are touched.
- [ ] Focused no-op baseline and `git diff --check` pass.
- [ ] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Draft expected checks:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.application.protocol.test_evaluate_result_dtos

git diff --check
git status --short --branch
```

Step 4.6 must confirm final commands after source-backed inventory.

## 10. Outcome / Deviations

Pending scoped inventory / implementation / closure.
