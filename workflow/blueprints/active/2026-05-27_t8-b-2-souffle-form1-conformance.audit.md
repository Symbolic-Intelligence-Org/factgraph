# Audit: T8-B-2 Souffle Form 1 Conformance

- Status: scoped
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-b-2-souffle-form1-conformance.md`
- Stage: scoped
- Class: S/M
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current four modified tracked docs/notebooks plus three untracked reference directories
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-B-2 Souffle Form 1 conformance blueprint pair drafted | Triggered by T8-B-1 native lane completion; Q1-Q9 intentionally pending for source-backed Step 4.6. |
| 2026-05-27 | scoped | this commit | Step 4.6 source-backed inventory completed | Souffle support artifacts verified native-like; scoped strategy is shared Form 1 helper + explicit native/Souffle allowlist; class narrowed to S/M. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8-B-1 shipped native row Form 1 at `9e9a7f49` and T8-D documented the
  native shipped subset at `22891808`.
- T8-B scoped inventory deferred Souffle row-result alignment because the
  existing converter looked graph-shaped but adapter-local.
- Reviewer due diligence found that Souffle row support artifacts may be
  native-like internally even though their kind is `SOUFFLE_WITNESS_KIND`.
- Current implementation likely has three possible strategies: extend the
  native Form 1 helper, add a dedicated Souffle helper, or keep using/migrate
  the proof-tree converter.

This draft scan is not a Step 4.6 answer. It intentionally avoids selecting a
strategy before source-backed inventory verifies exact data shape and metadata
semantics.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which strategy should T8-B-2 use: trivial extension, dedicated helper, or converter reuse? | Answered: shared Form 1 helper extension; dedicated helper and converter reuse rejected. |
| Q2 | Do native Form 1 `engine_meta` fields apply to Souffle support artifacts? | Answered: yes for row-result Form 1; no Souffle-specific row-result fields in T8-B-2. |
| Q3 | What is the future role of `souffle_proof_tree_to_evidence_graph(...)`? | Answered: keep as candidate/proof-tree converter; do not migrate row-result path. |
| Q4 | How should SDK support plumbing admit Souffle artifacts? | Answered: explicit allowlist for native + `SOUFFLE_WITNESS_KIND`. |
| Q5 | How should `_build_passed_row_evidence_graph(...)` dispatch after Souffle support lands? | Answered: preserve wrapper and T8-A validation gates; dispatch shared helper when support exists. |
| Q6 | What is the test matrix? | Answered: Souffle row Form 1 protocol tests plus Souffle converter/native/T8-A/audit/render/candidate/PyReason/ProbLog regressions. |
| Q7 | Are audit module docs updated in this cycle? | Answered: yes, audit module docs only. |
| Q8 | Does Souffle shipping trigger a T8-D round 2 user-docs follow-up? | Answered: yes as follow-up, not in-cycle. |
| Q9 | Are there stop/amend findings? | Answered: none. |

## 4. Step 4.6 Inventory Results

### 4.1 Source-Backed Findings

| Finding | Evidence | Result |
|---|---|---|
| Souffle artifacts mirror native shape | `engine_eval.py:400-431` builds a `native_like` artifact through `build_support_artifact_for_binding(...)` and copies `root_result_kind`, `binding_items`, `pred_witnesses`, `non_fact_steps`, `rule_refs`, and `rule_ref_edges` into `SupportArtifact(kind=SOUFFLE_WITNESS_KIND, ...)`. | Reviewer due-diligence finding verified. |
| Souffle witness atom keys use native convention | `engine_eval.py:447-460` uses `make_pred_atom_key(selected_branch_index, atom_index, pred_id)` and `ProjectedFact(asrt_id=...)`. | T8-B-1 atom key parsers and seed construction are compatible. |
| Souffle support is winning-branch only | `engine_eval.py:356-380` selects the lowest branch index for each binding and builds support from that selected branch. | C129 `winning_path_only` marker is valid for row-result Souffle Form 1. |
| Souffle kind is witness-bearing | `_support.py:13` defines `SOUFFLE_WITNESS_KIND`; `_support.py:16-18` includes native + Souffle in `_WITNESS_BEARING_SUPPORT_KINDS`. | Use explicit allowlist; do not accept arbitrary future kinds. |
| Core already records Souffle support backrefs | `_evaluate.py:265-289` remembers support backrefs for witness-bearing kinds after handling degraded/provenance paths. | SDK row support filtering is the main missing bridge. |
| T8-B-1 helper is kind-gated only | `evaluate_result.py:866-997` consumes shared `SupportArtifact` fields, with current native-only reject at `:872-873`. | Extend acceptance rather than duplicating helper. |
| SDK row support filter is native-only | `sdk/store.py:2741-2753` skips `candidate.support_kind != "native_binding_v1"`. | Replace with explicit native + Souffle allowlist. |
| Souffle proof-tree converter is separate | `provenance.py:48-137` consumes `SouffleProofTreeV0` and emits adapter-local graph metadata (`query`, `rule_count`, `root_relation`, `root_rule_number`). | Keep converter for candidate/proof-tree readback; row-result path uses §10.3 metadata. |

### 4.2 Strategy Decision

| Option | Estimate | Risk | Decision |
|---|---:|---|---|
| (a) Extend shared Form 1 helper | ~60-160 runtime LOC; ~100-220 test LOC; ~10-30 audit docs LOC | Low; relies on verified native-like artifact shape and keeps single row-result implementation path. | **Selected.** |
| (b) Dedicated Souffle helper | ~180-350 runtime LOC; ~120-260 test LOC | Duplicates native helper and increases divergence risk without a data-shape reason. | Rejected. |
| (c) Converter reuse / migration | ~250-500 runtime LOC plus broader tests | Mismatched input (`SouffleProofTreeV0`) and adapter-local metadata; risks regressing candidate/proof-tree converter. | Rejected. |

### 4.3 Engine Meta Compatibility

| Field family | Compatibility result |
|---|---|
| Root identity / claim / digests | Same row/result DTO path; §10.3 metadata remains unchanged. |
| Root `alternative_paths` | Valid for Souffle because the support artifact is built from selected branch support only. |
| Root bindings and support kind | Same `binding_items`; `support_kind` naturally becomes `souffle_witness_v1`. |
| Root `support_root_result_kind` | Same `root_result_kind` copied from the native-like artifact. |
| Premise atom id / index / pred id | Same `make_pred_atom_key(...)` convention as native; existing parsers can consume it. |
| Predicate witness reason | Same `PredWitness` shape and `asrt_ids` list. |
| Seed nodes | Same assertion-id leaf semantics from `ProjectedFact(asrt_id=...)`. |
| Non-fact steps | Same generic `NonFactStep` shape; aggregate count-only envelope remains deferred. |

### 4.4 Verification Baseline

Focused baseline:

```text
Ran 110 tests in focused T8-B-2 baseline; OK.
```

Full discover baseline:

```text
Ran 2004 tests; FAILED (failures=72, errors=233).
```

The full discover result matches the T8-B-1 closure baseline (`2004 tests`,
`72 failures`, `233 errors`); no Step 4.6 delta was observed.

## 5. Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Souffle support artifact is less native-like than expected | Trivial extension becomes unsafe | Cleared by `engine_eval.py:400-431`; copied fields mirror native artifact. |
| Native `engine_meta` shape is not semantically correct for Souffle | Shared helper may overstate behavior | Cleared for row-result Form 1 by compatibility table; no Souffle-specific row-result fields in scope. |
| Existing Souffle converter is confused with row-result path | Candidate-side behavior may regress or user-facing claims may drift | Mitigated by keeping converter as candidate/proof-tree path and regression gate. |
| SDK plumbing becomes broad allow-any-support | Future unsupported adapter artifacts may be rendered incorrectly | Mitigated by explicit native + Souffle allowlist. |
| T8-A validation gate is bypassed | Breaks C135 runtime invariant | Mitigated by preserving `_build_passed_row_evidence_graph(...)` wrapper and validation order. |
| T8-D docs expand into this runtime cycle | Scope creep | Mitigated by audit-docs-only in-cycle; user-facing docs are follow-up T8-D round 2. |

## 6. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q9 answered.
- [x] Strategy and class locked.
- [x] Test matrix and verification gates locked.
- [ ] Closure notes filled.

## 7. Closure Notes

Pending inventory / implementation / closure.
