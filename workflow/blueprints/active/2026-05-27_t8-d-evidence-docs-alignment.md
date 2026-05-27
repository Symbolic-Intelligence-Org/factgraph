# Task Blueprint: T8-D Evidence Docs Alignment

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S/M (docs-only)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-d-evidence-docs-alignment.audit.md`
- Trigger: T8-A metadata/validation foundation and T8-B-1 native Form 1 topology are now shipped; user-facing quickstart / SDK docs need to reflect the shipped A+B evidence behavior without teaching deferred T8-B-2/T8-C/T8-D+ features.

## 0. Scope Locks

### In scope

This is a docs-only alignment cycle. It may update public quickstart and SDK
docs only after Step 4.6 maps current wording to shipped behavior.

Candidate scope:

1. Source-backed inventory of existing evidence/explanation wording in the
   quickstart and SDK docs.
2. Primary update candidate: `docs/official/kernel/quickstart/evidence.md`.
3. Secondary quickstart candidates only if Step 4.6 finds stale or misleading
   wording: `rules-and-inferences.md`, `semantics.md`, `namespace-map.md`.
4. SDK docs candidates only if Step 4.6 finds stale or missing shipped behavior:
   `00_user_guide.en.md`, `01_concepts.en.md`,
   `03_rules_and_inferences.en.md`, `04_api_surface.en.md`,
   `06_what_if_and_proof.en.md`, `07_walker_and_advanced.en.md`.
5. Shipped behavior that may be taught: T8-A 14-key metadata / `run_id`
   envelope-only / sessionless three-layer audit, T8-B-1 native row Form 1
   topology, intra-graph seed reuse, winning-path-only OR, renderer threshold
   warning, renderer type guard, and graph validation failure semantics.
6. Explicit deferred-boundary markers where existing docs could imply shipped
   adapter Form 1, failed graph / why-not, match witness, cross-row seed reuse,
   session logs, signatures, ACL, salience/impact, `EDGE_DERIVES` /
   `EDGE_UPDATES`, `dag`, or `rule_fire`.

### Out of scope

- Any runtime code changes.
- Any test code changes.
- T8-B-2 Souffle conformance, T8-C engine enrichment, D20 match witness API
  design, failed graph, why-not, counterfactual, service/OpenAPI docs,
  Database/view docs, SDK API surface changes, release machinery, PyPI, tags,
  or dirty-baseline cleanup.
- Updating `src/factgraph/audit/docs/02_evidence_graph.md` unless Step 4.6
  finds a leftover gap; T7 and T8-B-1 already aligned that internal audit
  module doc.
- Teaching behavior that is not currently shipped.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

- The docs gap requires runtime behavior to close.
- Current docs teach deferred behavior as shipped.
- More than five files beyond primary `evidence.md` need non-trivial edits.
- A proposed docs change implies a new runtime/API contract.
- Scope touches runtime/tests, dirty baseline, release machinery, service,
  OpenAPI, Database/view runtime, or adapter implementation.

## 1. Problem

T8-A and T8-B-1 turned several evidence design commitments into shipped
runtime behavior:

- C135 metadata sufficiency is now runtime-enforced.
- Native passed row explanations can now expose multi-node Form 1
  `EvidenceGraph`s.
- C115 edge direction, C118 intra-graph seed reuse, and C129 winning-path-only
  OR are runtime-visible for native row explanations.

The public docs should describe these shipped behaviors accurately while
preserving clear boundaries around adapter Form 1, failed graph / why-not,
match witness, aggregate envelopes, session logs, signatures, ACL, and other
future features.

The risk is not missing runtime. The risk is documentation drift: either
under-teaching behavior that now exists, or over-teaching deferred behavior as
if it were shipped.

## 2. Inputs

| Source | Role |
|---|---|
| `docs/official/kernel/quickstart/evidence.md` | Primary public evidence docs target. |
| `docs/official/kernel/quickstart/rules-and-inferences.md` | Secondary quickstart candidate where RuleExpr / OR context may touch evidence wording. |
| `docs/official/kernel/quickstart/semantics.md` | Secondary quickstart candidate for evidence / semantics boundaries. |
| `docs/official/kernel/quickstart/namespace-map.md` | Secondary quickstart candidate for namespace wording. |
| `src/factgraph/sdk/docs/00_user_guide.en.md` | SDK user-guide evidence mentions. |
| `src/factgraph/sdk/docs/01_concepts.en.md` | SDK concepts evidence mentions. |
| `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` | SDK rules / inference evidence mentions. |
| `src/factgraph/sdk/docs/04_api_surface.en.md` | SDK API surface evidence mentions. |
| `src/factgraph/sdk/docs/06_what_if_and_proof.en.md` | SDK what-if / proof evidence mentions. |
| `src/factgraph/sdk/docs/07_walker_and_advanced.en.md` | SDK advanced evidence mention. |
| `src/factgraph/audit/docs/02_evidence_graph.md` | Already aligned audit-module reference; Step 4.6 should cross-check but avoid duplicate edits by default. |
| T7 / T8-A / T8-B-1 archived blueprints | Shipped evidence behavior and verification source. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §10.3/§11/§12/§15.5 | Design anchor for metadata, rendering, product boundary, and T8-D role. |
| `src/factgraph/application/protocol/evaluate_result.py` | Shipped metadata and native Form 1 behavior source. |
| `src/factgraph/audit/evidence_graph.py` | Shipped graph DTO, renderer, type guard, and threshold behavior source. |

## 3. Draft Source Scan

Draft scan is intentionally shallow:

- The primary likely docs target is the official evidence quickstart.
- Secondary quickstart and SDK docs contain evidence/explanation mentions and
  need source-backed triage before editing.
- `src/factgraph/audit/docs/02_evidence_graph.md` already received T7 and
  T8-B-1 alignment and should be treated as a reference, not a default target.
- T8-D should teach only shipped A+B behavior and mark deferred evidence
  features as boundaries.

This scan does not answer Q1-Q9. Step 4.6 must replace it with per-file
wording evidence and scoped docs decisions.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Which docs files must change and which should remain untouched? | Per-file diagnosis with current wording vs shipped behavior gap. |
| Q2 | What is the shape of the `evidence.md` update? | Add/rewrite/split/inline decision with rationale. |
| Q3 | Should docs show concrete Form 1 JSON / HTML render shape? | Decision that balances useful examples against over-specifying internals. |
| Q4 | How should the 14-key metadata contract be presented? | Full key list vs category summary, with rationale and user-dependency risk. |
| Q5 | How should hard vs soft graph failure be described? | User-facing wording for `GRAPH_VALIDATION_FAILED` vs hard protocol contract violation, or rationale for simplifying. |
| Q6 | Where should deferred boundaries be marked? | Inline vs dedicated section decision with a complete deferred-item map. |
| Q7 | How should quickstart and SDK docs split responsibility? | Duplicate/summary/cross-link decision. |
| Q8 | Should quickstart/SDK docs cross-link to audit module docs? | Link/no-link decision with audience rationale. |
| Q9 | Should docs cite tests or line numbers? | Decision to avoid brittle links or justify stable references. |

## 5. Existing Invariants To Preserve

- Docs-only: no runtime or test edits.
- Do not teach Souffle / ProbLog / PyReason row Form 1 as shipped.
- Do not teach failed graph, why-not, counterfactual, match witness, aggregate
  count-only envelope, cross-row seed dedup, session logs, signatures, ACL,
  salience/impact, `EDGE_DERIVES`, `EDGE_UPDATES`, `dag`, or `rule_fire` as
  shipped.
- Keep native Form 1 wording aligned with shipped runtime: root conclusion,
  selected-branch premises, assertion seeds, `EDGE_SUPPORTS`, intra-graph seed
  reuse, and winning-path-only OR.
- Keep 14-key graph metadata and `run_id` envelope-only boundary accurate.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains the known four tracked docs/notebooks plus two
  untracked reference directories.

## 6. Step 4.6 Inventory Plan

Step 4.6 must produce source-backed answers for Q1-Q9 and at least:

1. `rg` inventory of EvidenceGraph / evidence / explain mentions in the
   candidate docs files.
2. Per-file gap table: current wording, shipped behavior, decision
   (edit / leave / defer).
3. Primary `evidence.md` structure decision.
4. Quickstart secondary file decision.
5. SDK docs file decision.
6. Audit module docs cross-check decision.
7. Native Form 1 example policy.
8. 14-key metadata presentation policy.
9. Deferred-boundary placement map.
10. Verification plan for docs-only cycle.
11. Dirty/sacred status.
12. Stop/amend findings and final class.

## 7. Proposed Implementation Shape

Implementation shape is provisional until Step 4.6. Likely split if scoped:

1. Official quickstart docs, probably centered on `evidence.md`.
2. SDK docs alignment, only for files with real gaps.
3. Closure / archive.

No runtime/test implementation commit is expected.

## 8. Acceptance

- [ ] Step 4.6 answers Q1-Q9 with source-backed evidence.
- [ ] File scope is narrow and justified.
- [ ] Docs teach T8-A / T8-B-1 shipped behavior accurately.
- [ ] Docs do not teach T8-B-2 / T8-C / failed graph / match witness / v2
      features as shipped.
- [ ] Quickstart vs SDK docs roles are clear and not needlessly duplicated.
- [ ] `src/factgraph/audit/docs/02_evidence_graph.md` is left untouched unless
      Step 4.6 finds a concrete leftover gap.
- [ ] No runtime/test/release/dirty-baseline changes land.
- [ ] Focused no-op evidence baseline passes or is recorded as unchanged.
- [ ] `git diff --check` passes.
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

Step 4.6 must confirm whether any additional docs lint/grep verification is
needed based on selected files.

## 10. Outcome / Deviations

Pending implementation / closure.
