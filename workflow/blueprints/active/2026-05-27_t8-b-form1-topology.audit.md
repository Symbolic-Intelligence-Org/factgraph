# Audit: T8-B Native/Souffle Form 1 Topology

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-b-form1-topology.md`
- Stage: closure
- Class: M/L (scoped to T8-B-1 native Form 1 topology)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current four modified tracked docs/notebooks plus two untracked reference directories
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-B Form 1 topology blueprint pair drafted | Triggered by T8-A completion; Q1-Q9 intentionally pending for source-backed Step 4.6. |
| 2026-05-27 | scoped | this commit | Step 4.6 inventory completed | T8-B narrowed to T8-B-1 native Form 1; Souffle deferred to T8-B-2 / adapter-specific alignment. |
| 2026-05-27 | implementation | `d1597344` | Native Form 1 runtime bridge landed | Private support context plumbing plus native Form 1 graph helper; T8-A gates preserved. |
| 2026-05-27 | implementation | `31eab30c` | Native Form 1 tests landed | Protocol coverage plus SDK end-to-end assertion upgrade. |
| 2026-05-27 | implementation | `b99c978a` | Audit docs updated | Native row explanations documented as live row-level Form 1 graphs. |
| 2026-05-27 | closure | this commit | Cycle closure recorded | Focused 126 OK; full-discover scoped/current failure names identical at 72 failures / 233 errors. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8-A is complete and archived at `40a0ce47`; C135 metadata validation is now
  runtime-enforced and must not be weakened.
- T8 split inventory identifies T8-B as the next evidence implementation lane
  and recommends reuse-before-rewrite for candidate evidence and Souffle
  converter surfaces.
- `EvidenceGraph` already contains the node/edge kind vocabulary required by
  Form 1.
- Candidate evidence tree and Souffle evidence graph code already exist, so
  the core Step 4.6 task is tranche selection and reuse mapping, not proving
  that a substrate exists.

This draft scan is not a Step 4.6 answer. It intentionally avoids choosing
native-only vs Souffle-only vs combined scope before source-backed inventory.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Should T8-B be native-only, Souffle-only, both, or split into T8-B-1/T8-B-2? | **Answered:** split; implement T8-B-1 native first. |
| Q2 | How do candidate evidence helpers map to Form 1 topology? | **Answered:** reuse SupportArtifact/support capture; candidate tree helpers are compatibility/readback references; add thin native adapter. |
| Q3 | Does the Souffle converter already conform to Form 1? | **Answered:** structurally close but not row-result Form 1; defer. |
| Q4 | What are node/edge population rules for the selected tranche? | **Answered:** root conclusion, selected-branch premises, assertion seeds, `EDGE_SUPPORTS` child-to-parent only. |
| Q5 | What is the seed reuse strategy? | **Answered:** intra-graph seed dedup only. |
| Q6 | How is winning-path-only OR represented? | **Answered:** native support artifacts already select the winning branch; expose boundary, no failed branches. |
| Q7 | Where does C136 aggregate count-only envelope live? | **Answered:** deferred for T8-B-1 because current support artifact lacks aggregate matched-count envelope. |
| Q8 | What is the test matrix? | **Answered:** protocol native Form 1 tests + audit/candidate/Souffle/T8-A regressions. |
| Q9 | How should `_build_passed_row_evidence_graph(...)` change? | **Answered:** keep as validation gate wrapper, delegate to private native helper when support context exists, fallback to current single-node graph. |

## 4. Step 4.6 Inventory Results

### 4.1 Narrowing Decision

Chosen tranche: **T8-B-1 native Form 1 topology**.

| Option | File/test boundary | Estimate | Decision |
|---|---|---:|---|
| Native-only | `evaluate_result.py` private support plumbing + native Form 1 helper; protocol tests; candidate/audit regressions. | M/L, ~350-800 LOC across runtime+tests | **Select**. It uses shipped native `SupportArtifact` and keeps adapter semantics out. |
| Souffle-only | `adapters/souffle/provenance.py` + Souffle tests. | S/M if converter-only, M if row-result integration is required | Defer. Converter is graph-shaped but not row-result metadata/topology complete. |
| Combined native+Souffle | Native support plumbing plus Souffle adapter alignment. | L, likely 700-1500+ LOC | Reject for this cycle; mixes row-result and adapter-local semantics. |
| Split T8-B-1/T8-B-2 | Native first, Souffle follow-up. | M/L + later S/M-M | **Chosen**. Preserves ship discipline and lets Souffle conformance be reviewed independently. |

### 4.2 Reuse-Before-Rewrite Map

| Surface | Source refs | Current shape | T8-B-1 use |
|---|---|---|---|
| Native support artifact | `core/store/_support.py:96-105`; `core/store/_support_capture.py:29-91` | Typed `SupportArtifact` with binding items, predicate witnesses, non-fact steps, rule refs. | **Reuse** as topology source. |
| Winning branch capture | `_support_capture.py:145-167`; `_evaluate.py:224-255` | First satisfying branch selected; only selected branch materialized into support. | **Reuse** for C129 winning-path-only boundary. |
| Candidate evidence tree root/support sections | `_candidate_evidence_tree.py:12-54`, `:103-164` | Legacy dict tree with `candidate_result` / `support_section`. | **Reference / regression**, not direct EvidenceGraph output. |
| Predicate witness group | `_candidate_evidence_tree.py:167-185` | Groups assertion ids under `predicate_witness_group`. | **Thin-adapter concept** for premise-to-seed grouping. |
| Assertion leaf | `_candidate_evidence_tree.py:257-280` | Normalizes asrt_id, pred_id, e_ref, claim_args, optional fact_meta. | **Thin-adapter concept** for seed metadata. |
| Candidate evidence steps | `_candidate_evidence_tree_steps.py:48-116`, `:133-139`, `:231-246` | Traverses legacy dict tree into user-facing step list. | **Regression only**; no rewrite. |
| Souffle converter | `adapters/souffle/provenance.py:48-137` | Already emits EvidenceGraph tree with Souffle-local metadata. | **Defer** adapter alignment; keep regression tests. |

### 4.3 Design Anchors

| Contract | Source | Scoped interpretation |
|---|---|---|
| Edge direction / edge kinds | `evidence-tree...:2259`, `:623-628` | Form 1 uses only `EDGE_SUPPORTS`, from child/downstream to parent/upstream. |
| Four-layer topology | `evidence-tree...:2261`, `:287-293`, `:300-320`, `:393-407` | T8-B-1 implements root conclusion + premise + seed layers for native passed rows; no richer topology. |
| Seed reuse | `evidence-tree...:2262` | Dedup repeated fact/assertion seeds within one row graph. |
| OR | `evidence-tree...:376-391`, `:2261` | Root declares winning-path-only; do not show failed branches. |
| Aggregate | `evidence-tree...:1879-1953`, `:2264`, `:2783` | Deferred until matched-count aggregate substrate exists. |
| T8-B row | `evidence-tree...:2895` | Native/Souffle slice is split; native satisfies first bridge tranche. |

### 4.4 Current Row/Support Plumbing

- `_candidate_set_to_evaluate_row(...)` currently copies candidate bindings,
  quantitative carrier, and evidence ref only (`evaluate_result.py:527-567`).
  It does **not** carry `support_digest` / `support_kind` from
  `CandidateSet` (`core/derivation/candidates.py:13-30`).
- SDK `EvaluateResult` construction has both candidate list and row conversion
  in scope (`sdk/store.py:2691-2732`), so a private support context can be
  attached without changing public row/result API.
- Native support artifacts are stored before candidate support backrefs are
  remembered (`core/store/_evaluate.py:238-289`), and `Store` already exposes
  internal lookup by support digest (`core/store/runtime.py:101-134`).
- `_build_passed_row_evidence_graph(...)` is the existing T8-A validation gate
  and must remain the single wrapper (`evaluate_result.py:819-840`).

### 4.5 Verification Baseline

- Focused baseline:
  `PYTHONPATH=src python -m unittest tests.test_audit_evidence_graph tests.test_audit_evidence_graph_render tests.test_candidate_evidence_steps tests.test_souffle_evidence_graph tests.application.protocol.test_evaluate_result_dtos`
  → **93 OK**.
- Full discover baseline:
  `PYTHONPATH=src python -m unittest discover tests`
  → **2004 tests**, **72 failures**, **233 errors**. Categories match existing
  legacy/frontier/why_not/redesign-invariant failures recorded before this
  cycle; no T8-B code has run yet.
- Dirty/sacred status: branch ahead origin by 1 draft commit; sacred master
  remains `562c74195df43e933bed92a3ff25de94dd8ce666`; dirty baseline remains
  four tracked modified docs/notebooks plus two untracked reference dirs.

## 5. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Combined native+Souffle scope is too large | Cycle may balloon beyond L | Compare native-only, Souffle-only, both, and split options with file/test/LOC estimates. |
| Reuse-before-rewrite becomes a rewrite | Breaks T8 split intent and raises regression risk | Map every reused helper before implementation. |
| T8-B needs new graph schema | Violates Form 1 / T7 compatibility | Stop if new node/edge kind or DTO field is required. |
| T8-A validation gate is bypassed | Breaks C135 runtime invariant | Explicitly trace `_build_passed_row_evidence_graph(...)` strategy. |
| Aggregate or OR semantics become hidden scope | Semantic drift | Lock OR and C136 boundaries before code. |
| Dirty baseline edited accidentally | Workflow violation | Status checks before commit/closure. |

## 6. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q9 answered.
- [x] Narrowed implementation tranche locked.
- [x] Reuse-before-rewrite map complete.
- [x] Tests and verification gates locked.
- [x] Closure notes filled.

## 7. Closure Notes

T8-B shipped as **T8-B-1 native Form 1 topology**.

Landed chain:

```text
34dfcd3d  docs(blueprint): draft T8-B form1 topology
31405dea  docs(blueprint): scope T8-B form1 topology
d1597344  feat(protocol): build native form1 row evidence
31eab30c  test(protocol): cover native form1 row evidence
b99c978a  docs(audit): document native form1 row evidence
```

Runtime outcome:

- Native passed row explanations now emit live row-level Form 1
  `EvidenceGraph`s when private native support context exists.
- `_build_passed_row_evidence_graph(...)` remains the single metadata
  validation gate and falls back to the previous single-conclusion graph for
  detached/manual rows without support context.
- The private `_row_support_artifacts` carrier preserves public
  `EvaluateResult` representation, equality, and hash behavior.
- Native Form 1 uses existing `NODE_CONCLUSION`, `NODE_PREMISE`, `NODE_SEED`,
  and `EDGE_SUPPORTS` only. `EDGE_DERIVES` and `EDGE_UPDATES` remain reserves.
- Intra-graph seed reuse and C129 winning-path-only OR are now runtime-visible
  for native row explanations.
- C136 aggregate count-only envelope and Souffle row-result alignment remain
  deferred.

Test/docs outcome:

- Focused T8-B suite: 126 OK.
- SDK end-to-end rule-expression evaluation assertion was upgraded from weak
  `Explanation` instance checking to Form 1 graph shape checking.
- Audit docs now distinguish live native row Form 1 graphs from candidate
  evidence tree readback APIs.

Full-discover note:

- Review initially observed a possible 234-error run. Closure reran current
  HEAD and scoped `31405dea` in an auxiliary worktree.
- Both runs report `Ran 2004 tests` and `FAILED (failures=72, errors=233)`.
- Sorted `ERROR:` / `FAIL:` names are identical, so T8-B introduced no
  full-discover failure-name delta.

Scope preservation:

- No `EvidenceGraph` schema change.
- No new node/edge kind.
- No public SDK/API shape change.
- No T8-A validation weakening.
- No candidate evidence tree rewrite.
- No Souffle/ProbLog/PyReason adapter topology change.
- No service/OpenAPI/release/match/database/view/dirty-baseline touch.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
