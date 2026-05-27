# Task Blueprint: T8-B Native/Souffle Form 1 Topology

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: M/L (scoped to T8-B-1 native Form 1 topology)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-b-form1-topology.audit.md`
- Trigger: T8-A metadata/validation foundation shipped at `40a0ce47`, so T8 split inventory's next recommended evidence implementation lane is T8-B Native/Souffle Form 1 topology.

## 0. Scope Locks

### In scope

This cycle is the second T8 implementation slice. It may land runtime topology
work only after Step 4.6 quantifies the Native/Souffle split and confirms a
manageable tranche.

Candidate scope:

1. Source-backed inventory of candidate evidence tree builders, candidate
   evidence traversal/step surfaces, Souffle provenance converter, and current
   passed-row `EvidenceGraph` construction.
2. Narrowing decision: native-only, Souffle-only, both in one cycle, or split
   into T8-B-1 native and T8-B-2 Souffle.
3. Reuse-before-rewrite mapping from existing candidate evidence helpers to
   §15.2 Form 1 topology.
4. Form 1 topology bridge using existing `NODE_CONCLUSION`,
   `NODE_PREMISE`, `NODE_SEED`, and existing `EDGE_SUPPORTS` direction.
5. Seed reuse strategy for repeated facts inside the shipped tranche.
6. Winning-path-only OR semantics for successful explanations, if the scoped
   tranche touches OR-shaped evidence.
7. Minimal aggregate count-only envelope where the current substrate can
   support C136 without expanding contributor facts.
8. Focused tests for the scoped topology tranche plus regressions for T7
   renderer/DTO behavior and T8-A metadata validation.
9. Audit docs only if the shipped topology changes user-visible audit contract.

### Out of scope

- T8-C engine enrichment, ProbLog, PyReason Form 2, Nemo, or T10 adapter
  semantics.
- T8-D product/user docs unless Step 4.6 finds a narrow docs update required by
  shipped T8-B behavior.
- Failed graph, why-not, counterfactual, match witness output, or D20 API work.
- Changing `EvidenceGraph` DTO schema or adding node/edge kinds.
- Changing the 14-key §10.3 metadata contract or moving `run_id` into graph
  metadata.
- Service / OpenAPI, Database / view runtime, match API, `fg.eval.run`
  deletion, release machinery, PyPI, tags, or dirty-baseline cleanup.
- Rewriting the candidate evidence tree wholesale.
- Weakening T8-A validation gates, changing `_evidence_metadata_for_row_result`
  signature, or bypassing C135 runtime enforcement.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

- T8-B requires `EvidenceGraph` schema changes or new node/edge kinds.
- The native/Souffle tranche cannot reuse existing candidate evidence or
  Souffle converter surfaces and would become a rewrite.
- The selected tranche needs new metadata keys or `run_id` in graph metadata.
- Existing candidate evidence or Souffle tests must regress to land topology.
- T8-A metadata validation must be weakened or bypassed.
- Scope touches dirty baseline, service/OpenAPI, release machinery, match,
  database/view runtime, or adapter topology beyond the scoped Souffle lane.

## 1. Problem

T6 designed Form 1 evidence topology, T7 aligned the audit/rendering bridge, and
T8-A made the row evidence metadata bridge runtime-enforced. The remaining T8-B
question is whether the existing native candidate evidence tree and Souffle
provenance converter can be bridged into the §15.2 Form 1 shape without
rewriting the evidence substrate.

T8-B is not from-zero evidence graph construction. The highest-risk work is
selecting the right tranche size and proving that "reuse before rewrite" is
real for the current codebase.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §15.2 | T8-B row: Native/Souffle success topology, prerequisite, non-goals. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §8 | Form 1 topology, edge direction, seed reuse, OR, and aggregate topology contracts. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` C115/C117/C118/C129/C136 | Commitments for edge direction, 4-layer topology, seed reuse, winning-path-only OR, and aggregate count-only envelope. |
| `workflow/blueprints/archive/2026-05-27_t8-implementation-split-inventory.md` §4.4/§4.5 | T8-B reuse-before-rewrite planning and dependency graph. |
| `workflow/blueprints/archive/2026-05-27_t8-a-metadata-validation-foundation.md` | T8-A shipped metadata/validation invariant that T8-B must preserve. |
| `src/factgraph/core/store/_candidate_evidence_tree.py` | Existing native candidate evidence tree builder helpers. |
| `src/factgraph/core/store/_candidate_evidence_tree_steps.py` | Existing traversal and public candidate evidence step builder. |
| `src/factgraph/adapters/souffle/provenance.py` | Existing Souffle proof tree to `EvidenceGraph` converter. |
| `src/factgraph/audit/evidence_graph.py` | Existing node/edge kinds, DTO validation, roundtrip, and renderer behavior. |
| `src/factgraph/application/protocol/evaluate_result.py` | T8-A metadata gate and current passed-row graph construction. |
| Candidate/Souffle/audit/protocol tests | Existing regression gates and expected new topology test entry points. |

## 3. Draft Source Scan

Draft scan confirms orientation only:

- `EvidenceGraph` already has the 3 node kinds and 3 edge kinds needed by
  Form 1.
- The evidence design already defines Form 1 topology, seed reuse, and
  aggregate count-only boundaries.
- Candidate evidence tree and Souffle converter code already exist and should
  be evaluated as reuse targets before any new construction.
- T8-A validation is now the required metadata foundation for any new graph
  construction path.

This scan is superseded by the source-backed Step 4.6 decisions below.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Should T8-B be native-only, Souffle-only, both in one cycle, or split into T8-B-1 native + T8-B-2 Souffle? | File/test boundaries, LOC estimates, risk comparison, and a selected tranche with rationale. |
| Q2 | How do candidate evidence tree helpers map to §15.2 Form 1 topology? | Reuse / thin-adapter / new-helper table for `_build_support_sections`, `_build_predicate_witness_group`, `_build_assertion_leaf`, traversal, and related helpers. |
| Q3 | Does `souffle_proof_tree_to_evidence_graph(...)` already conform to Form 1? | Source-backed conformance/gap analysis and decision whether Souffle work is hook-up, adapter, or deferred. |
| Q4 | What are the Form 1 node/edge population rules for the selected tranche? | Deterministic rule for `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, and edge direction with §8/C115/C117 anchors. |
| Q5 | What is the seed reuse strategy? | Decision on cross-row or intra-graph seed de-duplication, with §8/C118 anchors and test implications. |
| Q6 | How is winning-path-only OR represented? | Source-backed statement of whether the selected tranche touches OR and how C129 is preserved. |
| Q7 | Where does C136 aggregate count-only envelope live? | Decision on `engine_meta` placement or explicit deferral if aggregate substrate is out of tranche. |
| Q8 | What is the test matrix? | Matrix covering selected native/Souffle topology, seed reuse, OR/aggregate if scoped, and T7/T8-A regressions. |
| Q9 | How should `_build_passed_row_evidence_graph(...)` change? | Direct replacement vs new helper selection vs defer; must preserve T8-A validation gates. |

## 4.1 Final Scoped Decisions

| Decision | Lock |
|---|---|
| Tranche | **T8-B-1 native Form 1 only**. Souffle remains regression-gated and deferred to T8-B-2 / adapter-specific alignment. |
| Class | M/L. Native requires private support plumbing plus topology conversion, but avoids adapter metadata alignment. |
| Runtime boundary | Preserve T8-A metadata gates and `_evidence_metadata_for_row_result(row, result)` signature. No public SDK/API shape change. |
| EvidenceGraph schema | Existing `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, and `EDGE_SUPPORTS` only. `EDGE_DERIVES` / `EDGE_UPDATES` remain Form 2 / temporal reserves. |
| Native support source | Reuse existing `SupportArtifact` / support capture substrate; do not rewrite candidate evidence tree. Existing candidate tree dict helpers are compatibility/readback surfaces, not direct `EvidenceGraph` node emitters. |
| Support carrier | Add private row/result support context only if needed by implementation. Exact private carrier shape is implementation detail, but it must be backward-compatible for direct `EvaluateRow(...)` construction. |
| Seed reuse | Deduplicate seeds **within one row `EvidenceGraph`** by assertion/fact identity. Do not attempt cross-row shared graph objects; each `Explanation` owns an independent graph. |
| OR | Native support capture is already winning-branch-only via selected branch support artifacts. T8-B-1 must expose that boundary on the root conclusion, without rendering failed branches. |
| Aggregates | C136 remains out of T8-B-1 unless current support artifact data already exposes aggregate matched-count details. Do not fabricate aggregate envelopes. |
| Docs | No user-facing docs commit unless the implemented native graph changes audit module user contract. Blueprint closure must record the no-doc or docs decision. |

## 4.2 Q1-Q9 Answers

| Q | Scoped answer |
|---|---|
| Q1 Narrow decision | **Split T8-B into T8-B-1 native and T8-B-2 Souffle.** Native-only touches `evaluate_result.py`, existing native support artifact plumbing, and protocol tests. Souffle-only is smaller at the converter level but does not satisfy row-result Form 1 because its metadata is adapter-local. Combined native+Souffle would mix two metadata/topology problems and remains L. |
| Q2 Reuse mapping | Reuse `SupportArtifact` (`_support.py:96-105`) and support capture (`_support_capture.py:29-91`) as source data. Treat `_candidate_evidence_tree.py` helpers as logic/readback references: `_build_support_sections` (`:103-164`) maps support sections, `_build_predicate_witness_group` (`:167-185`) maps predicate witness grouping, `_build_assertion_leaf` (`:257-280`) maps assertion seed normalization. Build a thin native Form 1 adapter rather than emitting the legacy tree dict shape. |
| Q3 Souffle conformance | Existing `souffle_proof_tree_to_evidence_graph(...)` already emits Form-1-like node kinds and `EDGE_SUPPORTS` (`provenance.py:48-137`; tests `test_souffle_evidence_graph.py:40-89`), but it is not row-result Form 1: metadata is adapter-local (`query`, `rule_count`, `root_relation`, `root_rule_number` at `:131-136`), root meta lacks §4.3 fields, and seed reuse is not C118-complete. Defer. |
| Q4 Node/edge rules | Native Form 1 uses root `NODE_CONCLUSION` for the row claim, `NODE_PREMISE` for selected support atoms/checks, and `NODE_SEED` for predicate assertion witnesses. Edges are `EDGE_SUPPORTS` from child/downstream to parent/upstream per C115 (`evidence-tree...:2259`), matching §4.7 examples (`:623-628`). |
| Q5 Seed reuse | Dedup repeated assertion seeds inside the row graph. C118 says same fact has one `NODE_SEED` with multiple incoming support edges (`evidence-tree...:2262`). Cross-row sharing is not in scope because each row explanation has its own `EvidenceGraph`. |
| Q6 Winning-path-only OR | Native support capture already selects one branch: `_evaluate_where_over_view_with_support(...)` calls `find_winning_branch_index(...)` then builds a support artifact for that branch (`_evaluate.py:224-255`; `_support_capture.py:145-167`). T8-B-1 exposes this as winning-path-only root metadata and does not render failed branches. |
| Q7 Aggregate envelope | Deferred for T8-B-1. C136 requires a specific aggregate premise envelope and matched-count semantics (`evidence-tree...:1879-1953`, `:2264`), but current `NonFactStep` only carries generic `kind/status/details` (`_support.py:47-63`) and support capture does not expose aggregate matched counts. |
| Q8 Tests | Add native Form 1 protocol tests in `tests/application/protocol/test_evaluate_result_dtos.py`; keep T7/T8-A regressions and run `test_candidate_evidence_steps`, `test_souffle_evidence_graph`, audit graph/render tests. Souffle remains regression only. |
| Q9 Replacement strategy | Preserve `_build_passed_row_evidence_graph(...)` as the single validation gate (`evaluate_result.py:819-840`). Delegate internally to a private native Form 1 helper when native support context exists; fallback to the existing single-conclusion graph for detached/manual rows without support. T8-A validation remains before/after graph construction. |

## 4.3 Source-Backed Inventory Highlights

| Area | Evidence | T8-B-1 implication |
|---|---|---|
| Current row graph | `_build_passed_row_evidence_graph(...)` emits one `NODE_CONCLUSION`, no edges, support_kind `evaluate_row` (`evaluate_result.py:819-840`). | Replace internals conditionally; keep function as gate wrapper. |
| Row conversion gap | `_candidate_set_to_evaluate_row(...)` currently copies bindings/raw_kind/bound/evidence_ref only (`evaluate_result.py:527-567`); `CandidateSet` carries `support_digest/support_kind` (`candidates.py:13-30`). | Native topology needs private support context plumbing; current public row fields are insufficient. |
| Store result creation | SDK result builder converts candidates to rows at `sdk/store.py:2691-2732` and already has candidate list in scope. | Implementation can attach private support context without changing public API. |
| Support artifact source | Native evaluation stores support artifacts at `_evaluate.py:238-247`; candidate support backrefs at `:258-289`. | Use existing native witness substrate; no candidate tree rewrite. |
| Winning branch | `find_winning_branch_index(...)` returns first satisfying branch (`_support_capture.py:145-167`); support artifact is built from selected branch only (`:29-91`). | C129 winning-path-only is source-backed. |
| Candidate tree compatibility | Existing tree helper emits legacy dict nodes (`candidate_result`, `support_section`, `predicate_witness_group`, `assertion_fact`) (`_candidate_evidence_tree.py:39-54`, `:103-185`, `:257-280`). | Treat as readback compatibility/regression, not direct EvidenceGraph output. |
| Candidate steps | Step traversal consumes the legacy dict shape (`_candidate_evidence_tree_steps.py:48-116`, `:133-139`, `:231-246`). | Regression gate only; T8-B-1 does not rewrite this surface. |
| Souffle converter | Converter already builds `NODE_CONCLUSION/PREMISE/SEED` and `EDGE_SUPPORTS` (`provenance.py:72-118`). | Structurally close, semantically separate; defer adapter alignment. |
| Edge kinds | Design C115 says Form 1 only `EDGE_SUPPORTS`; `EDGE_DERIVES`/`EDGE_UPDATES` are Form 2 reserves (`evidence-tree...:2259`, `:623-628`). | T8-B-1 must not use derives/updates. |
| Aggregate | C136 locks aggregate as single premise + 0 seed with `contributors.mode="omitted_v1"` (`evidence-tree...:1879-1953`, `:2264`). | Deferred because current support capture lacks matched-count envelope. |
| Baseline focused tests | `PYTHONPATH=src python -m unittest ...` across audit/candidate/Souffle/protocol ran **93 OK**. | Implementation must preserve or improve. |
| Full discover baseline | `PYTHONPATH=src python -m unittest discover tests` ran **2004 tests**, with existing `72 failures / 233 errors` in legacy/frontier/why_not/redesign areas. | Closure must record baseline; not a T8-B gate unless failure set changes in scoped files. |

## 5. Existing Invariants To Preserve

- T8-A metadata validation remains always-on and unweakened.
- `_evidence_metadata_for_row_result(row, result)` keeps its signature and
  `run_id` remains envelope-only.
- `EvidenceGraph` DTO fields, node kinds, edge kinds, validation, JSON
  roundtrip, renderer type guard, and large-graph warning remain compatible.
- Form 1 uses existing `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED` and
  existing edge kinds; no schema expansion without amendment.
- T6 v1 sessionless boundary remains intact: no session ids, session logs,
  `/interactions/{sessionID}`, ACL, signatures, salience, impact, or
  `x-evidence-key`.
- T8-B must be bridge-class work, not a candidate evidence tree rewrite.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains the known four tracked docs/notebooks plus two
  untracked reference directories.

## 6. Step 4.6 Inventory Plan

Step 4.6 must produce source-backed answers for Q1-Q9 and at least:

1. Exact source refs for candidate evidence tree builder helpers and their
   current output shape.
2. Exact source refs for candidate evidence traversal / step builder behavior.
3. Exact source refs for Souffle proof tree converter shape and tests.
4. Exact source refs for current `EvidenceGraph` node/edge constants,
   validation, and render/roundtrip invariants.
5. Exact source refs for current `_build_passed_row_evidence_graph(...)` and
   T8-A validation gates.
6. §8/C115/C117/C118/C129/C136 design anchors for edge direction, Form 1,
   seed reuse, winning-path-only OR, and aggregate count-only envelope.
7. Native-only / Souffle-only / combined / split class and LOC estimates.
8. Reuse-before-rewrite mapping table.
9. Test matrix with existing and new test modules.
10. Docs update decision.
11. Full-discover baseline comparison plan.
12. Dirty/sacred status.
13. Stop/amend findings and final class.

## 7. Proposed Implementation Shape

Implementation shape is intentionally provisional until Step 4.6. If scoped as
M/L rather than full L, likely split:

1. Runtime bridge for the selected native/Souffle tranche.
2. Tests for Form 1 topology plus existing candidate/Souffle/audit/protocol
   regression gates.
3. Docs only if user-facing audit contract changes.
4. Closure / archive.

If Step 4.6 finds both native and Souffle are too large together, narrow before
implementation rather than landing a partial hidden split.

## 8. Acceptance

- [x] Step 4.6 answers Q1-Q9 with source-backed evidence.
- [x] Narrow decision is locked with LOC/test/risk rationale.
- [x] Reuse-before-rewrite mapping is complete.
- [x] Form 1 node/edge/seed/OR/aggregate boundaries are locked for the selected
      tranche or explicitly deferred with rationale.
- [x] T8-A metadata validation and 14-key contract are preserved.
- [x] Existing candidate evidence and Souffle tests remain green or any
      regression causes stop/amend.
- [x] Focused tests cover shipped T8-B behavior.
- [x] No `EvidenceGraph` schema, node/edge kind, service/OpenAPI, release,
      match, database/view, or dirty-baseline changes land.
- [x] `git diff --check` passes.
- [x] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Draft expected checks:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.test_candidate_evidence_steps \
  tests.test_souffle_evidence_graph \
  tests.application.protocol.test_evaluate_result_dtos

PYTHONPATH=src python -m unittest discover tests

ruff check \
  src/factgraph/core/store/_candidate_evidence_tree.py \
  src/factgraph/core/store/_candidate_evidence_tree_steps.py \
  src/factgraph/adapters/souffle/provenance.py \
  src/factgraph/application/protocol/evaluate_result.py \
  tests/test_candidate_evidence_steps.py \
  tests/test_souffle_evidence_graph.py \
  tests/application/protocol/test_evaluate_result_dtos.py

git diff --check
git status --short --branch
```

Step 4.6 must confirm the final suite based on selected tranche.

## 10. Outcome / Deviations

### 10.1 Landed artifacts

| Commit | Role | Notes |
|---|---|---|
| `34dfcd3d` | Draft | T8-B Form 1 topology blueprint pair drafted with Q1-Q9 pending. |
| `31405dea` | Scoped | Source-backed inventory; T8-B narrowed to native Form 1 first tranche. |
| `d1597344` | Runtime | Native row explanations now build Form 1 `EvidenceGraph`s when native support context exists. |
| `31eab30c` | Tests | Protocol and SDK end-to-end Form 1 coverage added. |
| `b99c978a` | Docs | Audit module docs updated for native row Form 1 graphs. |

### 10.2 Runtime outcome

T8-B-1 shipped native row-level Form 1 topology without changing the public row
or result shape. `EvaluateResult` gained a private `_row_support_artifacts`
carrier with `repr=False`, `compare=False`, and `hash=False`, preserving public
`EvaluateResult` display/equality/hash behavior. SDK result construction passes
native `SupportArtifact`s through this private context when a candidate has
`support_kind == "native_binding_v1"`.

`_build_passed_row_evidence_graph(...)` remains the single T8-A validation gate:
it validates the 14-key metadata payload first, then delegates to a private
native Form 1 helper when support context exists, and otherwise keeps the
previous single-conclusion fallback for detached/manual rows. The after-builder
validation in `_explain_live_row(...)` remains in place, so the T8-A C135
runtime invariant is preserved.

The native Form 1 helper reuses `SupportArtifact` instead of rewriting the
candidate evidence tree. It emits:

- root `NODE_CONCLUSION` for the passed row claim,
- selected-branch `NODE_PREMISE` nodes for predicate witnesses and non-fact
  checks,
- assertion `NODE_SEED` nodes for predicate witnesses,
- `EDGE_SUPPORTS` from seed to premise and premise to conclusion.

Seed reuse is intra-graph only: repeated assertion ids create one seed node and
multiple support edges. The root conclusion records winning-path-only OR via
`engine_meta["alternative_paths"] = {"mode": "winning_path_only",
"omitted_count": None}`. Aggregate count-only envelopes remain deferred because
current `NonFactStep` support data does not expose matched-count contributor
state.

### 10.3 Tests and docs

Protocol tests now cover both paths:

- fallback single-conclusion graphs for manual/detached rows without support
  context,
- native Form 1 row graphs with root conclusion, premise nodes, seed nodes,
  `EDGE_SUPPORTS` direction, winning-path-only metadata, quantitative
  explanation envelope, and intra-graph seed reuse.

`tests/sdk/test_rule_expr_evaluate.py` was upgraded from a weak
`assertIsInstance(explanation, Explanation)` check to end-to-end Form 1 graph
assertions. This is a small scope amendment in test coverage only; it strengthens
the SDK regression gate and does not change runtime behavior.

Audit docs were updated because passed native row explanations now expose a
user-visible Form 1 `EvidenceGraph`. The docs distinguish live row-level Form 1
graphs from the older candidate evidence tree readback APIs, and record that
native Form 1 uses `supports` only while `derives` / `updates` remain reserved.

### 10.4 Deviations and implementation observations

- T8-B-1 is native-only. Souffle remains regression-gated and deferred because
  its converter is graph-shaped but adapter-local, not row-result Form 1.
- `tests/sdk/test_rule_expr_evaluate.py` was touched even though it was not in
  the initial scoped file list; the change is a stronger SDK end-to-end
  assertion for the shipped behavior.
- `_pred_id_from_atom_key(...)` and `_atom_index_from_key(...)` depend on the
  current atom-key naming convention and fail safe to `None` for unknown shapes.
  Future support-capture format changes should revisit these helpers.
- `_quantitative_explanation_for_row(...)` intentionally ships only the minimal
  v1 envelope: `mode` is `engine_reported` or `not_applicable`, and
  `decomposition` remains `not_available_v1`. T8-C engine enrichment may extend
  this.
- `evaluate_result.py` now imports the private `SupportArtifact` dataclass from
  `factgraph.core.store._support` for SDK-internal plumbing. This is an
  implementation dependency only and does not expose `SupportArtifact` at the
  SDK boundary.

### 10.5 Verification

Focused verification:

```text
PYTHONPATH=src python -m unittest \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.test_candidate_evidence_steps \
  tests.test_souffle_evidence_graph \
  tests.application.protocol.test_evaluate_result_dtos \
  tests.sdk.test_rule_expr_evaluate
→ 126 OK
```

`ruff check` passed for the touched runtime/test files, and `git diff --check`
is clean.

Full discover was rerun after review raised a possible `234`-error delta. The
current HEAD and scoped `31405dea` auxiliary worktree both report:

```text
Ran 2004 tests
FAILED (failures=72, errors=233)
```

The sorted `ERROR:` / `FAIL:` name lists are identical, so the earlier
`234`-error observation was transient and T8-B introduced no full-discover
failure-name delta.

Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`. Dirty
baseline remains the four tracked docs/notebooks plus two untracked reference
directories.
