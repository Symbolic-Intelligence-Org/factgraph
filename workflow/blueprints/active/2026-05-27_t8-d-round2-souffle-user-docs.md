# Task Blueprint: T8-D Round 2 Souffle User Docs

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S (docs-only)
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

## 3. Step 4.6 Source-Backed Inventory

### Shipped Behavior Source

T8-B-2 records the required shipped behavior:

- Souffle row artifacts mirror native support shape: the T8-B-2 audit says
  `engine_eval.py:400-431` builds a native-like artifact and copies
  `root_result_kind`, `binding_items`, `pred_witnesses`, `non_fact_steps`,
  `rule_refs`, and `rule_ref_edges`
  (`workflow/blueprints/archive/2026-05-27_t8-b-2-souffle-form1-conformance.audit.md:63`).
- Souffle witness atom keys use the native convention
  (`...t8-b-2-souffle-form1-conformance.audit.md:64`).
- Souffle support is winning-branch only, so `winning_path_only` is valid for
  row-result Souffle Form 1
  (`...t8-b-2-souffle-form1-conformance.audit.md:65`).
- The selected implementation was the shared Form 1 helper extension, not a
  dedicated Souffle helper or converter reuse
  (`...t8-b-2-souffle-form1-conformance.audit.md:47-51`,
  `:76-78`, `:138-143`).
- T8-B-2 explicitly keeps `souffle_proof_tree_to_evidence_graph(...)` as the
  candidate/proof-tree converter and not the row-result path
  (`...t8-b-2-souffle-form1-conformance.audit.md:49`, `:70`,
  `:156`, `:382-385`).
- T8-B-2 closure says protocol tests now cover Souffle row Form 1 support kind,
  node kinds, `EDGE_SUPPORTS` direction, exact 14-key metadata, `run_id`
  absence, `alternative_paths.mode == "winning_path_only"`, and seed reuse
  (`...t8-b-2-souffle-form1-conformance.md:376-379`).

### File Inventory

| File | Current wording | Decision |
|---|---|---|
| `docs/official/kernel/quickstart/evidence.md` | §6 title and body are native-only at lines 260-285; Current boundaries line 301 still says Souffle / ProbLog / PyReason row-level Form 1 alignment is future work; line 311 says Native Form 1 row graphs use `EDGE_SUPPORTS`. | **Edit.** This is the primary user-facing Form 1 section and contains the stale Souffle deferred claim. |
| `src/factgraph/sdk/docs/00_user_guide.en.md` | Lines 658-663 summarize native-only Form 1 and treat adapter Form 1 graphs as future. | **Edit.** Keep concise SDK summary, expanding native -> native + Souffle and linking to quickstart. |
| `docs/official/kernel/quickstart/rules-and-inferences.md` | Lines 619-625 discuss high-level engine lifecycle only. | Leave. No Form 1 topology or stale Souffle evidence boundary. |
| `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` | Lines 572-575 delegate the full evidence envelope chain to `evidence.md`. | Leave. Existing handoff remains correct. |
| `src/factgraph/audit/docs/02_evidence_graph.md` | Lines 41-45 and 196-199 already say native + Souffle row explanations produce Form 1 and preserve the Souffle proof-tree converter boundary. | Leave. T8-B-2 already aligned audit-module docs. |
| Other grep hits (`namespace-map.md`, audit overview/API docs) | High-level cross-engine or audit-module mentions; no user-facing row-level Form 1 deferred claim found. | Leave. Editing would exceed the narrow mirror cycle. |

## 4. Step 4.6 Q1-Q8 Answers

| ID | Answer |
|---|---|
| Q1 file scope | Exactly two implementation files: `docs/official/kernel/quickstart/evidence.md` and `src/factgraph/sdk/docs/00_user_guide.en.md`. Other files either delegate to `evidence.md`, discuss high-level engine lifecycle, or are already-aligned audit-module docs. |
| Q2 `evidence.md` edit map | Narrow §6 edits only: title line 260 native -> native + Souffle; lines 263-285 native/support-context wording -> native or Souffle row support; preserve ASCII topology at 266-268; line 276 winning-path wording -> native or Souffle; line 301 remove Souffle from deferred row-level Form 1; line 311 Native -> Native and Souffle. |
| Q3 SDK user-guide edit map | Lines 658-663 only: native passed rows -> native or Souffle passed rows; keep the concise shape summary and quickstart link; change "adapter Form 1 graphs" future wording so Souffle is no longer classified as future. |
| Q4 deferred boundary | Replace exactly `Souffle / ProbLog / PyReason row-level Form 1 alignment is future work.` with `ProbLog / PyReason row-level Form 1 alignment is future work.` Preserve the other Current boundaries bullets byte-for-byte unless wrapping changes are unavoidable. |
| Q5 ASCII topology | Yes, preserve. T8-B-2 selected the shared Form 1 helper and records existing `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, and `EDGE_SUPPORTS` topology with no new node/edge kind (`...t8-b-2-souffle-form1-conformance.md:140`, `:238-239`). |
| Q6 `winning_path_only` | Yes. T8-B-2 records Souffle support as selected-branch only and explicitly validates `alternative_paths.mode == "winning_path_only"` for Souffle row Form 1 (`...t8-b-2-souffle-form1-conformance.audit.md:65`; `...t8-b-2-souffle-form1-conformance.md:376-379`). |
| Q7 verification | Use the T8-D first-round focused no-op baseline: `PYTHONPATH=src python -m unittest tests.test_audit_evidence_graph tests.test_audit_evidence_graph_render tests.application.protocol.test_evaluate_result_dtos`, then `git diff --check` and `git status --short --branch`. |
| Q8 proof-tree boundary | Omit from user docs. Audit docs already state the candidate/proof-tree converter boundary (`src/factgraph/audit/docs/02_evidence_graph.md:196-199`). User docs should focus on row-level evidence now shipped for native + Souffle, not audit-module implementer separation. |

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

## 6. Step 4.6 Inventory Outcome

Step 4.6 completed with no stop trigger:

1. File scope is exactly the two T8-D first-round user-facing docs files.
2. Leave-alone checks found no non-target user docs requiring edits.
3. T8-B-2 source refs confirm Souffle row Form 1 uses the native-compatible
   shared helper path.
4. Deferred boundary edit is a single-item removal: Souffle leaves future work;
   ProbLog / PyReason remain future work.
5. ASCII topology and `winning_path_only` wording remain valid for Souffle.
6. Verification baseline ran clean at 38 OK:
   `PYTHONPATH=src python -m unittest tests.test_audit_evidence_graph tests.test_audit_evidence_graph_render tests.application.protocol.test_evaluate_result_dtos`.
   The count grew from the earlier T8-D round because later protocol tests were
   added; the no-op baseline remains green.

## 7. Proposed Implementation Shape

Implementation is intentionally narrow:

1. Quickstart docs commit: native -> native + Souffle wording in the existing
   EvidenceGraph section, and deferred boundary update.
2. SDK docs commit: concise summary wording update, avoiding duplication.
3. Closure / archive.

## 8. Acceptance

- [x] Step 4.6 answers Q1-Q8 with source-backed evidence.
- [x] File scope is exactly the two user-facing docs files or the cycle is
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

Step 4.6 confirmed the focused baseline command above; implementation/closure
also runs `git diff --check` and dirty/sacred status checks.

## 10. Outcome / Deviations

Pending scoped inventory / implementation / closure.
