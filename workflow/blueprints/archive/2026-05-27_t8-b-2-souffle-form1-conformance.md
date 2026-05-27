# Task Blueprint: T8-B-2 Souffle Form 1 Conformance

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: S/M
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-b-2-souffle-form1-conformance.audit.md`
- Trigger: T8-B-1 native Form 1 topology shipped at `9e9a7f49`; T8-D A+B docs shipped at `22891808`; T8-B scoped inventory deferred Souffle row-result Form 1 alignment to T8-B-2.

## 0. Scope Locks

### In scope

This cycle is the Souffle lane follow-up to T8-B-1. Step 4.6 verified that
Souffle row support artifacts mirror the native support artifact shape closely
enough for a bridge-class implementation. The scoped implementation is a
shared Form 1 row-result bridge, not a rewrite of the Souffle proof-tree
converter.

Final scope:

1. Source-backed inventory of Souffle `SupportArtifact` creation, current
   Souffle proof-tree converter, T8-B-1 native dispatch, and SDK support
   artifact plumbing.
2. Extend the T8-B-1 Form 1 helper to accept both native and Souffle
   witness-bearing support artifacts.
3. Souffle row-result Form 1 `EvidenceGraph` support using the existing
   `SupportArtifact` shape and §10.3 metadata bridge.
4. SDK/protocol support-artifact plumbing extension with an explicit allowlist
   for native and Souffle witness-bearing support kinds, while
   preserving native handling unchanged.
5. Focused tests for Souffle row Form 1, plus regressions for T8-A metadata,
   T8-B-1 native Form 1, Souffle converter, audit graph/render, candidate
   evidence, and non-Souffle adapter evidence tests.
6. Audit module docs only if shipped Souffle row behavior changes the
   user-visible audit contract.

### Out of scope

- ProbLog / PyReason Form 1 or engine enrichment; those remain T8-C.
- T10 semantics adapter execution.
- T8-D user-facing quickstart / SDK docs round 2; record as a follow-up if
  Souffle behavior ships.
- D20 match witness, failed graph, why-not, or counterfactual surfaces.
- Aggregate count-only envelope unless Step 4.6 finds an already-shipped
  matched-count substrate.
- `EvidenceGraph` DTO schema changes or new node/edge kinds.
- Changing the §10.3 14-key metadata contract or moving `run_id` into graph
  metadata.
- Service / OpenAPI, Database / view runtime, match API, `fg.eval.run`
  deletion, release machinery, PyPI, tags, or dirty-baseline cleanup.
- Rewriting candidate evidence tree or Souffle converter wholesale.
- Weakening T8-A validation gates or changing
  `_evidence_metadata_for_row_result(...)` signature.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

- Souffle `SupportArtifact` structure is not native-like enough for a
  bridge-class implementation.
- The cycle needs `EvidenceGraph` schema changes, new node/edge kinds, new
  metadata keys, or `run_id` in graph metadata.
- Existing native Form 1 behavior or T8-A metadata validation must regress.
- Existing `tests/test_souffle_evidence_graph.py` must regress to land the
  row-result path.
- Scope touches ProbLog, PyReason, T8-C, D20, dirty baseline, service/OpenAPI,
  release machinery, Database/view, match, or user-facing T8-D docs.

## 1. Problem

T8-B-1 shipped native row-level Form 1 evidence graphs and deliberately deferred
Souffle row-result conformance. Souffle already has a candidate-side proof-tree
to `EvidenceGraph` converter, and reviewer due diligence found that current
Souffle support artifacts may mirror the native support artifact shape.

The risk is under-scoping or over-scoping: Souffle row explanations may require
only a small dispatch/plumbing extension, or they may require adapter-specific
metadata alignment that should remain a separate tranche. Step 4.6 must verify
the actual shipped substrate before choosing a strategy.

## 2. Inputs

| Source | Role |
|---|---|
| `src/factgraph/adapters/souffle/engine_eval.py` | Souffle `SupportArtifact` construction site. |
| `src/factgraph/core/store/_support.py` | `SupportArtifact` dataclass and `SOUFFLE_WITNESS_KIND`. |
| `src/factgraph/adapters/souffle/provenance.py` | Existing Souffle proof-tree to `EvidenceGraph` converter. |
| `tests/test_souffle_evidence_graph.py` | Existing Souffle converter regression baseline. |
| `src/factgraph/application/protocol/evaluate_result.py` | T8-A metadata gate, T8-B-1 native dispatch, Form 1 helper, and metadata bridge. |
| `src/factgraph/sdk/store.py` | Current `_row_support_artifacts_for_candidates(...)` support-kind filter. |
| `workflow/blueprints/archive/2026-05-27_t8-b-form1-topology.md` §4.4/§4.6 | T8-B-1 scoped Souffle deferral and conformance finding. |
| `workflow/blueprints/archive/2026-05-27_t8-a-metadata-validation-foundation.md` | C135 runtime-enforced metadata foundation. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §8.13 / §10.3 / §15.2 | C115/C117/C118/C129/C136, 14-key metadata, and T8-B design source. |

## 3. Draft Source Scan

Draft orientation only, to be verified by Step 4.6:

- T8-B-1 currently dispatches Form 1 graph construction only for native support
  artifacts.
- `sdk/store.py` currently filters row support artifacts to native support
  kind only.
- Souffle has two relevant surfaces: row-evaluation support artifacts and the
  older proof-tree converter.
- Reviewer due diligence found a likely native-like Souffle `SupportArtifact`
  construction path in `engine_eval.py`, but the Step 4.6 inventory must verify
  exact fields, kind names, atom-key conventions, and metadata implications
  before implementation.

This scan does not answer Q1-Q9.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Which strategy should T8-B-2 use: trivial extension, dedicated Souffle helper, or converter reuse? | Three-option comparison with file/test/LOC estimates, risks, and selected strategy. |
| Q2 | Do native Form 1 `engine_meta` fields apply to Souffle support artifacts? | Per-field compatibility table for premise/seed/root metadata and decision on same-shape vs Souffle-specific additions. |
| Q3 | What is the role of `souffle_proof_tree_to_evidence_graph(...)` after row-result conformance? | Keep/migrate/defer decision with candidate-side vs row-result boundary. |
| Q4 | How should SDK support plumbing admit Souffle artifacts? | Allowlist/denylist/other strategy with rationale and native regression implications. |
| Q5 | How should `_build_passed_row_evidence_graph(...)` dispatch after Souffle support lands? | Dispatch strategy and trace showing T8-A validation gates are preserved. |
| Q6 | What is the test matrix? | Souffle row Form 1 tests plus Souffle converter, native Form 1, T8-A, audit/render, candidate, PyReason, and ProbLog regressions. |
| Q7 | Are audit module docs updated in this cycle? | Docs/no-docs decision based on shipped user-visible audit contract. |
| Q8 | Does Souffle shipping trigger a T8-D round 2 user-docs follow-up? | In-cycle vs follow-up decision with rationale. |
| Q9 | Are there stop/amend findings? | None or explicit scope amendment trigger. |

### 4.1 Final Scoped Decisions

| Decision | Lock |
|---|---|
| Class | S/M. Souffle row support artifacts are native-like; implementation should be a narrow dispatch / allowlist / test / audit-doc update, not a new evidence topology tranche. |
| Strategy | Use the shared Form 1 row-result helper path for native + Souffle. Do not add a dedicated Souffle helper and do not migrate the proof-tree converter. |
| Runtime surface | `evaluate_result.py` + `sdk/store.py` only, unless implementation finds a scoped helper import cleanup is necessary. |
| Test surface | `tests/application/protocol/test_evaluate_result_dtos.py` for Souffle row Form 1 protocol coverage; existing Souffle converter, native SDK Form 1, T8-A, candidate, audit/render, PyReason, and ProbLog tests remain regression gates. |
| Docs surface | `src/factgraph/audit/docs/02_evidence_graph.md` only. User-facing quickstart / SDK docs are a T8-D round 2 follow-up. |
| Metadata | Preserve the exact §10.3 graph metadata bridge. No new metadata keys and no `run_id` in graph metadata. |
| Topology | Use existing `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, and `EDGE_SUPPORTS`. No new node/edge kind. |

### 4.2 Source-Backed Inventory

| Area | Source evidence | Scoped implication |
|---|---|---|
| Souffle artifact creation | `engine_eval.py:400-431` builds `native_like = build_support_artifact_for_binding(...)`, then returns `SupportArtifact(kind=SOUFFLE_WITNESS_KIND, root_result_kind=native_like.root_result_kind, binding_items=native_like.binding_items, pred_witnesses=native_like.pred_witnesses, non_fact_steps=native_like.non_fact_steps, rule_refs=native_like.rule_refs, rule_ref_edges=native_like.rule_ref_edges)`. | Souffle row artifacts mirror native internal shape; only `kind` differs. |
| Souffle witness facts | `engine_eval.py:447-460` creates witness facts using `make_pred_atom_key(selected_branch_index, atom_index, pred_id)` and `ProjectedFact(asrt_id=..., fact_tuple=...)`. | T8-B-1 `_pred_id_from_atom_key(...)`, `_atom_index_from_key(...)`, and seed construction can consume Souffle keys. |
| Winning branch | `engine_eval.py:356-380` groups witness rows, selects the lowest branch index, and builds one support artifact for that selected branch. | Souffle row artifacts are already winning-branch only for row-result support. |
| Support kind contract | `_support.py:13` defines `SOUFFLE_WITNESS_KIND`; `_support.py:16-18` includes native + Souffle in `_WITNESS_BEARING_SUPPORT_KINDS`; `_support.py:96-127` validates shared `SupportArtifact` fields. | Use an explicit native + Souffle allowlist; do not broaden to arbitrary kinds. |
| Native support builder | `_support_capture.py:29-91` builds native `SupportArtifact(kind="native_binding_v1", ...)` from the same binding/witness structures. | Shared helper path is source-backed; no rewrite of evidence capture is needed. |
| Core support backref | `_evaluate.py:265-289` remembers support backrefs for witness-bearing kinds after handling degraded/provenance kinds separately. | Core already treats Souffle as witness-bearing for backrefs; SDK row plumbing is the missing filter. |
| T8-B-1 dispatch | `evaluate_result.py:839-847` validates metadata, fetches `result._row_support_artifacts[row.row_id]`, dispatches if present, otherwise falls back to the single-conclusion graph. | Preserve wrapper and fallback; extend helper acceptance, not public API shape. |
| T8-B-1 helper | `evaluate_result.py:866-997` builds Form 1 from `SupportArtifact.pred_witnesses` and `.non_fact_steps`; current early reject is `support_artifact.kind != "native_binding_v1"` at `:872-873`. | The narrow runtime change is the support-kind acceptance and naming/wording around the shared helper. |
| Metadata validation | `evaluate_result.py:1024-1071` builds and validates exact §10.3 graph metadata; `_explain_live_row(...)` validates returned graph metadata at `:633-638`. | T8-A gates remain unchanged and cover Souffle dispatch automatically if wrapper is preserved. |
| SDK filter | `sdk/store.py:2741-2753` collects row support artifacts but currently skips all non-native support kinds at `:2747-2749`. | Replace native-only check with explicit native + Souffle allowlist. |
| Souffle proof-tree converter | `provenance.py:48-137` converts `SouffleProofTreeV0` to `EvidenceGraph` with adapter-local engine metadata and graph metadata (`query`, `rule_count`, `root_relation`, `root_rule_number`). | Keep as candidate/proof-tree path; it is not the row-result §10.3 metadata bridge. |
| Souffle converter tests | `tests/test_souffle_evidence_graph.py:40-137` asserts current proof-tree converter shape and renderer compatibility. | Regression gate; no migration in T8-B-2. |
| Native Form 1 tests | `tests/application/protocol/test_evaluate_result_dtos.py:443-497` covers native Form 1 topology and seed reuse; `tests/sdk/test_rule_expr_evaluate.py:72-101` covers SDK end-to-end native Form 1. | Preserve as regressions and add Souffle protocol coverage beside them. |
| Audit docs | `src/factgraph/audit/docs/02_evidence_graph.md:41-45`, `:119-121`, and `:195-197` currently say native row explanations produce Form 1 graphs. | Update to native + Souffle row explanations; keep candidate/proof-tree readback boundary clear. |

### 4.3 Q1-Q9 Answers

| Q | Answer |
|---|---|
| Q1 strategy | Select option (a): extend the shared Form 1 row-result path. Estimate: ~60-160 runtime LOC, ~100-220 test LOC, ~10-30 audit docs LOC. Option (b), dedicated Souffle helper, is ~180-350 runtime LOC and duplicates native logic without a data-shape need. Option (c), converter reuse, is ~250-500 LOC and mismatches row-result inputs and §10.3 metadata because `souffle_proof_tree_to_evidence_graph(...)` takes `SouffleProofTreeV0` and emits adapter-local graph metadata. |
| Q2 engine_meta | Same shape works for row-result Form 1. Root fields (`rule_id`, `is_head`, `explained_claim_ref`, `quantitative_explanation`, `alternative_paths`, `bindings`, `desc_template`, `content_digest`, `version`, `raw_kind`, `bound`, `support_root_result_kind`) come from `row`, `result`, and shared `SupportArtifact` fields. Premise fields (`atom_id`, `pred_id`, `atom_index`, `parent_rule_id`, `reason.kind`, `reason.pred_id`, `reason.asrt_ids`, `raw_kind`, `bound`) are supported because Souffle witness artifacts use the same `PredWitness` shape and `make_pred_atom_key(...)`. Seed fields use the same `asrt_id` leaves. Do not add Souffle-specific row-result `engine_meta` fields in T8-B-2. |
| Q3 converter role | Keep `souffle_proof_tree_to_evidence_graph(...)` as the candidate/proof-tree converter. It remains a regression-protected adapter-side path. Row-result evidence uses `SupportArtifact` + §10.3 metadata and should not migrate through this converter. |
| Q4 SDK plumbing | Use an explicit allowlist for `"native_binding_v1"` and `SOUFFLE_WITNESS_KIND`. Avoid a denylist or broad witness-bearing pass-through because future adapter kinds may not be Form 1-compatible. Native regression is preserved by keeping the native kind in the allowlist and reusing the existing lookup/type check. |
| Q5 dispatch | Keep `_build_passed_row_evidence_graph(...)` as wrapper: validate metadata first, look up row support artifact, dispatch to shared Form 1 helper when support exists, fallback to single-conclusion graph when absent. T8-A gates remain: `_evidence_metadata_for_row_result(...)` build/freeze/validate, wrapper entry validation before dispatch, and `_explain_live_row(...)` after-builder-return validation. |
| Q6 tests | Add protocol tests for Souffle row Form 1 graph: support kind, node kinds, edge direction, 14-key metadata, `run_id` absence, `winning_path_only`, and seed reuse. Preserve existing `test_souffle_evidence_graph`, native Form 1 SDK/protocol tests, T8-A metadata tests, audit/render tests, candidate evidence tests, PyReason and ProbLog tests. |
| Q7 audit docs | Yes. Update audit module docs because row-level audit behavior changes from native-only Form 1 to native + Souffle Form 1. Do not update user-facing quickstart / SDK docs in this runtime cycle. |
| Q8 T8-D round 2 | Record a follow-up T8-D round 2 for user-facing quickstart / SDK docs after Souffle ships. Keeping it out of T8-B-2 avoids docs scope creep. |
| Q9 stop/amend | No stop/amend finding. Source inventory confirms a bridge-class path; class narrows to S/M. |

### 4.4 Engine Metadata Compatibility Table

| Field family | Native source | Souffle source | Decision |
|---|---|---|---|
| Root row identity / claim | `row.row_id`, `row.evidence_ref_id`, `row.claim_digest`, `result.closed_head_digest` | Same row/result DTO path after SDK candidate conversion | Same shape. |
| Root `alternative_paths` | T8-B-1 constant `{"mode": "winning_path_only", "omitted_count": None}` | Souffle support capture selects one branch before artifact construction (`engine_eval.py:356-380`) | Same marker is accurate. |
| Root bindings | `support_artifact.binding_items` | Copied from `native_like.binding_items` (`engine_eval.py:423-431`) | Same shape. |
| Root `support_root_result_kind` | `support_artifact.root_result_kind` | Copied from `native_like.root_result_kind` | Same shape. |
| Premise atom id / index | `PredWitness.pred_atom_key`, parsed by `_pred_id_from_atom_key(...)` and `_atom_index_from_key(...)` | Souffle witness facts use `make_pred_atom_key(...)` (`engine_eval.py:447-460`) | Same parser path. |
| Premise reason | `PredWitness.asrt_ids` and `pred_id` | Same `PredWitness` dataclass copied from `native_like.pred_witnesses` | Same `predicate_witness` reason shape. |
| Seed identity | `asrt_id` leaves from witness facts | Souffle witness facts carry `ProjectedFact(asrt_id=...)` | Same seed node semantics. |
| Non-fact steps | `NonFactStep(kind/status/details)` | Copied from `native_like.non_fact_steps`; C136 aggregate remains deferred | Same generic non-fact handling; no aggregate envelope in T8-B-2. |

### 4.5 Test Matrix And Verification

| Area | Test command / file |
|---|---|
| Souffle row Form 1 | Extend `tests/application/protocol/test_evaluate_result_dtos.py`. |
| Native Form 1 regression | `tests/application/protocol/test_evaluate_result_dtos.py` and `tests/sdk/test_rule_expr_evaluate.py`. |
| Souffle converter regression | `tests.test_souffle_evidence_graph`. |
| Audit/render regression | `tests.test_audit_evidence_graph`, `tests.test_audit_evidence_graph_render`. |
| T8-A metadata regression | `tests.application.protocol.test_evaluate_result_dtos`. |
| Match/read regression | `tests.test_sdk_read_match_runtime`. |
| Candidate evidence regression | `tests.test_candidate_evidence_steps`. |
| Adapter non-scope regressions | `tests.test_pyreason_evidence_graph`, `tests.test_problog_evidence_graph`. |

Focused baseline after Step 4.6 inventory:

```text
PYTHONPATH=src python -m unittest \
  tests.test_souffle_evidence_graph \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.application.protocol.test_evaluate_result_dtos \
  tests.test_sdk_read_match_runtime \
  tests.test_candidate_evidence_steps \
  tests.test_pyreason_evidence_graph \
  tests.test_problog_evidence_graph

Ran 110 tests; OK.
```

Full discover baseline after Step 4.6 inventory:

```text
PYTHONPATH=src python -m unittest discover tests

Ran 2004 tests; FAILED (failures=72, errors=233).
```

This matches the T8-B-1 recorded baseline (`2004 tests`, `72 failures`,
`233 errors`), so Step 4.6 found no new discovery delta.

## 5. Existing Invariants To Preserve

- T8-A 14-key metadata and `run_id` envelope-only validation remains
  always-on.
- `_evidence_metadata_for_row_result(row, result)` keeps its signature.
- T8-B-1 native Form 1 behavior and SDK end-to-end assertions do not regress.
- `_build_passed_row_evidence_graph(...)` remains the single row graph
  validation/dispatch wrapper unless Step 4.6 explicitly amends it.
- `EvidenceGraph` DTO fields, node kinds, edge kinds, roundtrip, renderer type
  guard, and large-graph warning remain compatible.
- Form 1 uses existing `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`, and
  `EDGE_SUPPORTS`; no schema expansion.
- T6 v1 sessionless boundary remains intact: no session ids, session logs,
  `/interactions/{sessionID}`, ACL, signatures, salience, impact, or
  `x-evidence-key`.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains the known four modified tracked docs/notebooks, the
  local deleted `workflow/working/.gitkeep`, and three untracked reference /
  design files or directories. The `.gitkeep` deletion is a pre-existing
  working tree state, not introduced or staged by this cycle.

## 6. Step 4.6 Inventory Plan

Step 4.6 must produce source-backed answers for Q1-Q9 and at least:

1. Exact source refs for Souffle support artifact creation and fields.
2. Exact source refs for `SOUFFLE_WITNESS_KIND` and native support kind usage.
3. Exact source refs for T8-B-1 native Form 1 helper and dispatch.
4. Exact source refs for SDK support artifact filtering/plumbing.
5. Exact source refs for current Souffle proof-tree converter shape and tests.
6. Per-field `engine_meta` compatibility table.
7. Strategy comparison for trivial extension vs dedicated helper vs converter
   reuse.
8. Test matrix and verification commands.
9. Audit docs update / T8-D follow-up decision.
10. Full-discover baseline comparison against the T8-B-1 recorded
    baseline (`2004 tests`, `72 failures`, `233 errors`).
11. Dirty/sacred status.
12. Stop/amend findings and final class.

## 7. Proposed Implementation Shape

Step 4.6 narrowed implementation to a shared row-result Form 1 bridge:

1. Runtime bridge:
   - Import / reuse the existing Souffle witness kind constant.
   - Replace the native-only support artifact row plumbing check with an
     explicit allowlist for native + Souffle witness-bearing kinds.
   - Extend or rename the T8-B-1 private Form 1 helper so it accepts both
     support kinds without changing `EvidenceGraph` schema or graph metadata.
   - Keep `_build_passed_row_evidence_graph(...)` as the single wrapper and
     keep the T8-A validation gate before dispatch.
2. Focused tests:
   - Add Souffle row Form 1 protocol tests for node kinds, edge direction,
     support kind, 14-key metadata, `run_id` absence, `winning_path_only`, and
     seed reuse.
   - Preserve native Form 1, T8-A validation, Souffle converter, candidate
     evidence, and SDK end-to-end regressions.
3. Audit docs:
   - Update only `src/factgraph/audit/docs/02_evidence_graph.md` to reflect
     that native and Souffle row explanations now produce live row-level
     Form 1 graphs.
   - Leave quickstart / SDK user docs to a future T8-D round 2.
4. Closure / archive.

## 8. Acceptance

- [x] Step 4.6 answers Q1-Q9 with source-backed evidence.
- [x] Souffle strategy is selected with file/test/LOC/risk rationale.
- [x] T8-A metadata validation and 14-key contract are preserved.
- [x] T8-B-1 native Form 1 behavior does not regress.
- [x] Existing Souffle converter tests remain green or any regression causes
      stop/amend.
- [x] Focused tests cover any shipped Souffle row Form 1 behavior.
- [x] No `EvidenceGraph` schema, node/edge kind, metadata-contract, T8-C,
      service/OpenAPI, release, match, database/view, or dirty-baseline changes
      land.
- [x] `git diff --check` passes.
- [x] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Draft expected checks:

```bash
PYTHONPATH=src python -m unittest \
  tests.test_souffle_evidence_graph \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.application.protocol.test_evaluate_result_dtos \
  tests.test_sdk_read_match_runtime \
  tests.test_candidate_evidence_steps \
  tests.test_pyreason_evidence_graph \
  tests.test_problog_evidence_graph

PYTHONPATH=src python -m unittest discover tests

ruff check \
  src/factgraph/adapters/souffle/engine_eval.py \
  src/factgraph/adapters/souffle/provenance.py \
  src/factgraph/application/protocol/evaluate_result.py \
  src/factgraph/sdk/store.py \
  tests/test_souffle_evidence_graph.py \
  tests/application/protocol/test_evaluate_result_dtos.py

git diff --check
git status --short --branch
```

Step 4.6 must confirm final commands after strategy selection.

## 10. Outcome / Deviations

### 10.1 Landed Artifacts

| Commit | Role | Notes |
|---|---|---|
| `6f3f20c7` | Draft | Opened T8-B-2 Souffle Form 1 conformance cycle with Q1-Q9 pending. |
| `5f67b109` | Scoped | Verified Souffle support artifacts are native-like and selected shared Form 1 helper extension. |
| `08afd76c` | Runtime | Extended row-level Form 1 evidence to Souffle via protocol-local support-kind allowlist and SDK plumbing. |
| `2a90c338` | Tests | Added Souffle row Form 1 protocol tests for topology, 14-key metadata, `run_id` absence, `winning_path_only`, and seed reuse. |
| `8eae09d1` | Audit docs | Updated audit module docs from native-only row Form 1 to native + Souffle row Form 1 while preserving proof-tree readback boundary. |

### 10.2 Runtime Outcome

T8-B-2 shipped the scoped option (a) trivial extension. `_build_native_form1_evidence_graph(...)`
was renamed to `_build_form1_evidence_graph(...)`, and its body stayed unchanged
apart from accepting the protocol-local `_FORM1_ROW_SUPPORT_KINDS` allowlist.
This confirms the Step 4.6 source finding that Souffle `SupportArtifact`s mirror
the native support shape.

The runtime intentionally defines `_FORM1_ROW_SUPPORT_KINDS` in
`evaluate_result.py` instead of importing core `_WITNESS_BEARING_SUPPORT_KINDS`.
The two sets are equal today, but they model different layers: core
"witness-bearing support" vs protocol "row Form 1 evidence-ready support". Future
adapter witness kinds may be witness-bearing without being row Form 1-ready.

T8-A metadata validation gates are preserved:

- `_evidence_metadata_for_row_result(...)` still builds, freezes, and validates
  the 14-key graph metadata payload.
- `_build_passed_row_evidence_graph(...)` still validates metadata before any
  support-artifact dispatch.
- `_explain_live_row(...)` still validates returned `EvidenceGraph.metadata`
  before producing a passed explanation.

### 10.3 Tests And Docs

`tests/application/protocol/test_evaluate_result_dtos.py` now covers Souffle row
Form 1 support kind, node kinds, `EDGE_SUPPORTS` direction, exact 14-key graph
metadata, `run_id` absence, `alternative_paths.mode == "winning_path_only"`,
and intra-graph seed reuse. Existing native Form 1 and SDK end-to-end assertions
remain unchanged.

`src/factgraph/audit/docs/02_evidence_graph.md` now says native and Souffle row
explanations produce live row-level Form 1 graphs. It also preserves the
candidate/proof-tree boundary: Souffle proof-tree readback still uses the
adapter proof-tree converter. User-facing quickstart / SDK docs remain a T8-D
round 2 follow-up.

### 10.4 Verification

Focused T8-B-2 suite:

```text
PYTHONPATH=src python -m unittest \
  tests.test_souffle_evidence_graph \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render \
  tests.application.protocol.test_evaluate_result_dtos \
  tests.test_sdk_read_match_runtime \
  tests.test_candidate_evidence_steps \
  tests.test_pyreason_evidence_graph \
  tests.test_problog_evidence_graph

Ran 112 tests; OK.
```

Additional gates:

```text
ruff check src/factgraph/application/protocol/evaluate_result.py \
  src/factgraph/sdk/store.py \
  tests/application/protocol/test_evaluate_result_dtos.py

All checks passed.

git diff --check

clean
```

Full discovery:

```text
PYTHONPATH=src python -m unittest discover tests

Ran 2004 tests; FAILED (failures=72, errors=233).
```

This matches the T8-B-1 baseline and shows no T8-B-2 regression delta.

### 10.5 State Notes

No `EvidenceGraph` schema, node/edge kind, metadata-contract, T8-C, service,
OpenAPI, release, match, database/view, quickstart/SDK user-doc, or dirty
baseline files were changed.

Dirty baseline at closure is `4 M + 1 D + 3 U`:

- four modified tracked docs/notebooks,
- deleted `workflow/working/.gitkeep`,
- untracked `docs/references/working/change-requests-2026-05-27/`,
- untracked `rainbird-ai sdk code/`,
- untracked `workflow/design/design-points/active/identity-and-data-model-redesign.zh.md`.

The untracked identity/data-model artifact moved into active design-point
location during the environment/session, but it remains untracked and untouched
by this cycle.
