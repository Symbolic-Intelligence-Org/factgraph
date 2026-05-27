# Task Blueprint: T8-A Metadata + Validation Foundation

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Class: M (may split to S/M sub-cycles after Step 4.6)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-27_t8-a-metadata-validation-foundation.audit.md`
- Trigger: T8 split inventory archived at `a872fa5b` recommends T8-A as the first evidence implementation slice and identifies metadata builder / sufficiency checker / validation gate / debug assertion as the foundation before T8-B/T8-C topology and enrichment work.

## 0. Scope Locks

### In scope

This cycle is the first T8 implementation slice. It may land one tightly scoped
runtime tranche if Step 4.6 confirms the current file boundaries remain M-class:

1. Source-backed inventory of the current evidence metadata writer,
   row-explain path, minimal graph builder, and `EvidenceGraph` validation.
2. Decision on whether T8-A ships as one blueprint with two commits or splits
   into T8-A-1 / T8-A-2 before implementation.
3. Central metadata builder boundary for the current 14-key §10.3 graph
   metadata contract.
4. Metadata sufficiency checker boundary for graph metadata produced from
   `EvaluateResult` + `EvaluateRow`.
5. Strict graph validation gate boundary around row explanation graph
   construction and unsupported-result fallback.
6. Debug assertion boundary for envelope/row/graph consistency.
7. Focused tests that preserve the exact 14-key metadata set, `run_id`
   envelope-only stance, existing EvidenceGraph validation/roundtrip behavior,
   and row-explain pass/unsupported behavior.
8. Module docs or design docs only if Step 4.6 finds a narrow shipped-contract
   update is needed.

### Out of scope

- T8-B Native/Souffle success topology.
- T8-C engine enrichment, PyReason Form 2, ProbLog enrichment, or T10 adapter
  semantics.
- T8-D product/user documentation beyond a narrow T8-A shipped-contract note.
- Failed graph, why-not, counterfactual, session log, ACL, signature, salience,
  impact, `x-evidence-key`, or D20 match witness API work.
- Changing the 14-key §10.3 metadata contract unless the blueprint is amended.
- Moving `run_id` into `EvidenceGraph.metadata`.
- Service / OpenAPI, Database / view runtime, match API, `fg.eval.run`
  deletion, release machinery, PyPI, tags, or dirty-baseline cleanup.
- Rewriting candidate evidence tree or adapter provenance surfaces.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

- T8-A cannot remain M-class because the metadata builder/checker needs a new
  public schema, durable module boundary, or cross-engine API.
- The 14-key graph metadata set must change.
- `run_id` or session identity must enter graph metadata.
- Strict validation requires graph topology or engine enrichment work that
  belongs to T8-B/T8-C.
- Debug assertion requires always-on behavior that could break existing passed
  explanations in normal runtime.
- Any change touches dirty baseline, service/OpenAPI, release machinery, or
  candidate/adapter evidence tree code.

## 1. Problem

T7 aligned the shipped audit/rendering bridge with T6 §10/§11 and added strict
tests for the current 14-key graph metadata bridge. T8 split inventory then
identified T8-A as the first implementation slice: centralize the metadata
builder, add a reusable sufficiency check, and tighten validation/debug
assertions before topology or engine enrichment work begins.

The current implementation is already functional but localized:
`_evidence_metadata_for_row_result(...)` builds graph metadata inline, row
explanation passes that metadata to `_build_passed_row_evidence_graph(...)`,
and `EvidenceGraph.__post_init__` validates structural graph shape. T8-A should
bridge these surfaces into a clearer foundation without changing public
metadata semantics.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t8-implementation-split-inventory.md` §4.3 | T8-A four-subitem boundary and LOC estimates. |
| `workflow/blueprints/archive/2026-05-27_t8-implementation-split-inventory.md` §4.5 | Dependency graph: T8-A precedes T8-B/T8-C. |
| `workflow/blueprints/archive/2026-05-27_t7-evidence-audit-rendering-bridge.md` §4.2 | T7 12-row contract matrix, especially metadata/validation rows. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §10.3 | Current 14-key graph metadata source of truth. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` §15 | T8-A/B/C/D split proposal and T8-A-first recommendation. |
| `src/factgraph/application/protocol/evaluate_result.py` | `EvaluateResult`, `Explanation`, metadata writer, row explain path, graph builder. |
| `src/factgraph/audit/evidence_graph.py` | `EvidenceGraph` DTO validation and roundtrip/renderer substrate. |
| `tests/application/protocol/test_evaluate_result_dtos.py` | 14-key metadata and `run_id` envelope-only regression anchor. |
| `tests/test_audit_evidence_graph.py` | EvidenceGraph validation and roundtrip regression anchor. |

## 3. Draft Source Scan

Draft scan confirms only orientation:

- `EvaluateResult` validates envelope fields and row identity in
  `evaluate_result.py`.
- `_explain_live_row(...)` derives metadata from one `EvaluateResult` + row
  context and catches `ValueError` from graph construction as an unsupported
  explanation.
- `_evidence_metadata_for_row_result(...)` currently writes the 14 graph
  metadata keys inline.
- `EvidenceGraph.__post_init__` already enforces structural graph constraints.
- T7 tests enforce exact 14-key graph metadata and absent `run_id`.

This scan does not answer the Step 4.6 questions. Step 4.6 must replace it with
source-backed file:line evidence and final scoped decisions.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | Should T8-A ship as one blueprint or split into T8-A-1 / T8-A-2? | One M-class blueprint, implemented as two commits if scope stays inside `evaluate_result.py` + focused tests. |
| Q2 | What is the central metadata builder shape? | Keep the existing private module-level builder path; add a private key-set/checker companion. No class, public method, or cross-module builder. |
| Q3 | What is the metadata sufficiency checker shape? | Private module-level checker; exact-set validation of §10.3 keys plus row/result value consistency; raises `ValueError` so existing unsupported fallback is preserved. |
| Q4 | How should the strict graph validation gate integrate with `_explain_live_row(...)`? | Keep `ValueError -> Explanation(status="unsupported", code="GRAPH_VALIDATION_FAILED")`; run metadata validation inside the graph-builder/row-explain gate. |
| Q5 | How should debug assertion be enabled? | Always-on internal consistency check for evidence graphs returned by the builder, scoped to metadata/envelope consistency only; no env var, no public flag, no Python `assert`. |
| Q6 | Which tests are mandatory before implementation? | Completed in §4.6. |
| Q7 | Are module docs or design docs required in this cycle? | No docs required unless implementation changes user-visible wording; behavior is internal contract hardening. |
| Q8 | What remains deferred to T8-B/T8-C/T8-D? | Completed in §4.8. |
| Q9 | Are there any stop/amend findings from source inventory? | None; class remains M. |

## 4.1 Final Scoped Decisions

| Decision | Scoped lock |
|---|---|
| Cycle shape | Keep T8-A as one M-class blueprint. Implement as A-1 metadata builder/checker and A-2 validation/debug assertion commits. Split into T8-A-1/A-2 only if implementation reveals helper-module or public-schema churn. |
| Central metadata builder | Preserve the existing private module-level `_evidence_metadata_for_row_result(row, result)` caller contract and make it the central builder by adding an internal key tuple/frozenset plus validation helper nearby. Do not introduce `EvidenceMetadataBuilder`, `EvaluateResult.metadata_for(...)`, audit-module builder APIs, or public SDK surface. |
| Metadata sufficiency checker | Add a private module-level checker in `evaluate_result.py` that enforces the exact §10.3 key set and row/result value consistency. It raises `ValueError` with graph-validation wording so `_explain_live_row(...)` keeps the current unsupported fallback. |
| Strict validation gate | Keep `_explain_live_row(...)`'s `ValueError -> GRAPH_VALIDATION_FAILED` behavior. The graph builder / row-explain path becomes the gate; no new `Explanation.status`, error code, or public exception. |
| Debug assertion | Use an always-on internal validation helper, not a Python `assert`, env flag, or test-only helper. Scope is metadata/envelope consistency only, so it does not add topology or engine enrichment. |
| Docs | No public docs or design docs in this cycle unless implementation changes the scoped contract. Current audit docs already say central metadata sufficiency is future T8; this cycle makes that internal foundation real without changing user-facing semantics. |
| T8-B/C/D | Remain deferred. T8-A must not import candidate evidence, adapter provenance, or topology helpers. |
| Dirty baseline | Preserve current 4 modified tracked files plus 2 untracked directories. |

## 4.2 Source-Backed Inventory Results

| # | Item | Result |
|---|---|---|
| 1 | `EvaluateResult` envelope fields | `EvaluateResult` fields are `result_id`, `run_id`, `rows`, `head`, `engine`, `engine_version`, `adapter_version`, `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `semantics_digest`, `evaluated_at`, and `result_digest` at `evaluate_result.py:128-142`; validation for ids/digests/rows is at `:151-181`. |
| 2 | Row explain path | `_explain_live_row(...)` validates row/result types at `evaluate_result.py:553-562`, resolves checked scope and row membership/staleness at `:564-594`, builds metadata at `:596`, calls the graph builder at `:597-599`, converts `ValueError` to `Explanation(status="unsupported", errors[0].code="GRAPH_VALIDATION_FAILED")` at `:600-618`, and returns passed explanation at `:620-630`. |
| 3 | Current metadata writer | `_evidence_metadata_for_row_result(...)` writes the current 14 keys at `evaluate_result.py:823-842`: `result_id`, `row_id`, `evidence_ref_id`, `claim_digest`, `closed_head_digest`, `expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `semantics_digest`, `result_digest`, `engine`, `engine_version`, `adapter_version`, `evaluated_at`. |
| 4 | Current passed-row graph builder | `_build_passed_row_evidence_graph(...)` creates a single `NODE_CONCLUSION` node and copies the provided metadata into `EvidenceGraph(metadata=metadata)` at `evaluate_result.py:800-820`. This is the current single-node T8-A boundary; no topology expansion. |
| 5 | EvidenceGraph structural validation | `EvidenceGraph.__post_init__` freezes metadata and validates `layout_hint`, duplicate node/edge ids, root existence, edge endpoints, and cycles at `evidence_graph.py:74-117`. |
| 6 | Current metadata tests | `test_live_row_explain_returns_passed_explanation` asserts passed explanation shape, exact graph metadata key set, absent `run_id`, and every graph metadata value at `tests/application/protocol/test_evaluate_result_dtos.py:249-341`. |
| 7 | Unsupported graph fallback tests | Existing test injects a failing `graph_builder` and asserts `status="unsupported"`, `GRAPH_VALIDATION_FAILED`, and `evidence is None` at `tests/application/protocol/test_evaluate_result_dtos.py:520-539`. |
| 8 | EvidenceGraph validation / roundtrip tests | Graph validation tests cover valid tree, duplicate node/edge, missing root, endpoint, unsupported layout, mapping freeze, and JSON roundtrip at `tests/test_audit_evidence_graph.py:18-197`; cycle detection continues after `:200`. |
| 9 | Callers/importers | `rg` over `src` and `tests` found `_evidence_metadata_for_row_result(...)` called only by `_explain_live_row(...)` at `evaluate_result.py:596`; `_build_passed_row_evidence_graph(...)` is selected only at `:597`; no external importers were found. `_explain_live_row(...)` is imported by `tests/application/protocol/test_evaluate_result_dtos.py:18` and inspected by quarantine test `tests/sdk/test_t5_why_not_quarantine.py:110`. |
| 10 | Design anchors | §10.3 names the 14 v1 graph metadata fields at `evidence-tree...:2375-2398`; §10.4 defines metadata sufficiency and validation/roundtrip at `:2400-2419`; C134/C135 require graph validation and metadata source-of-truth/debug assertion at `:2781-2782`; §15.2 names T8-A at `:2894`; §15.3 recommends T8-A first at `:2899-2904`. |
| 11 | Docs state | `src/factgraph/audit/docs/02_evidence_graph.md` already records `run_id` envelope-only, §10.3 metadata keys, safe JSON path, large graph warning, and future central metadata sufficiency at lines found by `rg`; no stale user-facing claim requires a docs commit for this internal hardening. |
| 12 | Focused baseline | `PYTHONPATH=src python -m unittest tests.application.protocol.test_evaluate_result_dtos tests.test_audit_evidence_graph tests.test_audit_evidence_graph_render` ran 31 OK during Step 4.6. |
| 13 | Dirty / sacred | `git status --short --branch` shows 4 modified tracked docs/notebooks and 2 untracked directories (`docs/references/working/change-requests-2026-05-27/`, `rainbird-ai sdk code/`). Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`. |
| 14 | Stop/amend findings | None. No service/OpenAPI, release, database/view, match, adapter topology, or dirty-baseline work is needed. Class remains M. |

## 4.3 Candidate Shapes Considered

### Central metadata builder (Q2)

| Candidate | Pros | Cons | Decision |
|---|---|---|---|
| A. Keep private module-level builder `_evidence_metadata_for_row_result(row, result)` and add nearby internal constants/checker | Minimal churn; preserves existing private call path; no new public surface; easiest backward compatibility; keeps source of truth near `EvaluateResult` and row context | Name remains "for row result" rather than generic future builder; T8-B/C may later need a broader builder | **Selected** for T8-A. Future T8-B/C can generalize only after topology/enrichment scope exists. |
| B. New `EvidenceMetadataBuilder` class | Extensible and testable as a unit; could carry future contexts | Premature abstraction; likely accidental public-ish API; unnecessary for one current caller | Rejected. |
| C. Method on `EvaluateResult` or `EvaluateRow` | Discoverable from envelope/row objects | Public shape drift; couples DTO API to audit internals; hard to revise | Rejected. |
| D. Move builder into `factgraph.audit` | Seems aligned with `EvidenceGraph` ownership | Would introduce application-protocol -> audit helper dependency beyond current DTO imports and obscure live result context ownership | Rejected for T8-A. |

### Metadata sufficiency checker (Q3)

| Candidate | Pros | Cons | Decision |
|---|---|---|---|
| A. Private module-level checker in `evaluate_result.py`, exact key set + value consistency, raises `ValueError` | Fits existing `_explain_live_row` unsupported fallback; no public surface; directly testable through row explain and private builder paths | Private helper is not reusable outside this module without future refactor | **Selected**. |
| B. Public/dataclass validator object | Stronger named contract for future graph builders | Adds public or semi-public API before T8-B/C know their needs | Rejected. |
| C. Test-only assertion helper | Zero runtime risk | Does not enforce C134/C135 at runtime; too weak for T8-A | Rejected. |
| D. `ProtocolShapeError` checker | Matches protocol DTO validation style | Would bypass existing `ValueError -> unsupported` graph validation fallback unless more control flow changed | Rejected. |

### Debug assertion enablement (Q5)

| Candidate | Pros | Cons | Decision |
|---|---|---|---|
| A. Always-on internal validation helper, raising `ValueError` inside the existing graph gate | Enforces C135 in normal runtime; preserves unsupported fallback; no env/config state | Could reject custom internal graph builders that return incomplete metadata | **Selected**, scoped to metadata/envelope consistency only. Existing graph-builder injection is private/test-facing and should obey the contract. |
| B. Python `assert` | Simple and obviously debug-like | Disabled under optimization; not reliable contract enforcement | Rejected. |
| C. Env-var / explicit debug flag | Avoids runtime breakage | Adds configuration surface and inconsistent behavior | Rejected. |
| D. Test-only helper | No runtime risk | Does not deliver T8-A validation foundation | Rejected. |

## 5. Existing Invariants To Preserve

- `EvidenceGraph.metadata` remains the exact current §10.3 14-key set for
  passed row graphs unless this blueprint is amended.
- `run_id` remains envelope-only and absent from `EvidenceGraph.metadata`.
- `EvidenceGraph` structural validation, JSON roundtrip, renderer type guard,
  and large-graph warning remain compatible with T7 behavior.
- Existing row explanations continue to produce `status="passed"` with an
  `EvidenceGraph` for valid rows and `status="unsupported"` when graph
  construction fails validation.
- T8-A does not add graph topology beyond the current single-node passed-row
  graph.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains the current modified docs/notebooks plus untracked
  reference material.

## 6. Step 4.6 Inventory Plan

Filled in §4.2. Original planned checks:

1. Exact source refs for `EvaluateResult` fields, validation, and row binding.
2. Exact source refs for `_explain_live_row(...)`, graph-builder injection,
   `ValueError` unsupported fallback, and passed explanation construction.
3. Exact source refs for `_evidence_metadata_for_row_result(...)` and the
   14-key writer.
4. Exact source refs for `_build_passed_row_evidence_graph(...)` and its
   current graph metadata copy.
5. Exact source refs for `EvidenceGraph.__post_init__` structural validation.
6. Current tests that enforce 14-key metadata, `run_id` absence, graph
   validation, roundtrip, and unsupported graph construction behavior.
7. Current callers/importers of `_evidence_metadata_for_row_result(...)` and
   `_build_passed_row_evidence_graph(...)`.
8. Metadata builder/checker candidate shapes with pros/cons and hidden public
   surface risk.
9. Debug assertion candidate shapes with runtime risk.
10. T8-A single-cycle vs split decision.
11. Test matrix and expected files.
12. Docs/design update decision.
13. Stop/amend findings and final class.

## 7. Proposed Implementation Split

Scoped implementation split:

1. **Runtime A-1**: add internal metadata key constants and private checker in
   `evaluate_result.py`; keep `_evidence_metadata_for_row_result(...)` as the
   builder entry and preserve the 14-key result exactly.
2. **Runtime A-2**: wire strict metadata/envelope consistency validation into
   `_build_passed_row_evidence_graph(...)` / `_explain_live_row(...)` without
   changing `ValueError -> unsupported` semantics.
3. **Tests**: extend `tests/application/protocol/test_evaluate_result_dtos.py`
   for positive checker behavior, missing/extra/wrong metadata rejection, and
   unchanged unsupported fallback; preserve existing audit graph tests.
4. **Closure**: no docs commit by default; record no-doc rationale and focused
   verification.

## 7.1 Test Matrix

| T8-A subitem | Existing coverage | New / extended coverage |
|---|---|---|
| Central metadata builder | Exact 14 keys and values at `test_evaluate_result_dtos.py:249-341` | Keep set equality; add direct/private-path or row-explain regression if implementation exposes a narrower helper. |
| Metadata sufficiency checker | No reusable checker coverage today | Missing key rejects, extra key rejects, wrong value rejects; all surface as `Explanation(status="unsupported", code="GRAPH_VALIDATION_FAILED")` when reached through `_explain_live_row(...)`. |
| Strict graph validation gate | Graph structural tests at `test_audit_evidence_graph.py:18-197`; unsupported fallback test at `test_evaluate_result_dtos.py:520-539` | Ensure metadata checker failures use the same unsupported fallback and do not return partial evidence. |
| Debug assertion consistency | Current value assertions in passed explanation test | Add mismatch path using injected graph builder returning an `EvidenceGraph` with inconsistent metadata. |
| Backward compatibility | Existing row explain pass / fail / stale / unsupported tests | Focused suite remains green; no external callers of private builder were found. |

## 8. Acceptance

- [x] Step 4.6 answers Q1-Q9 with source-backed evidence.
- [x] T8-A single-cycle vs split decision is locked.
- [x] Metadata builder/checker shape is locked without changing the current
      14-key metadata contract.
- [x] `run_id` remains envelope-only.
- [x] Strict validation/debug behavior is implemented or explicitly deferred
      with rationale.
- [x] Focused tests cover all implemented T8-A behavior and existing T7
      metadata/validation regressions.
- [x] T8-B/T8-C/T8-D and D-series non-goals remain deferred.
- [x] No service/OpenAPI, release, match, database/view, adapter topology, or
      dirty-baseline changes are made.
- [x] `git diff --check` passes.
- [x] Sacred master and dirty baseline are preserved.

## 9. Verification Commands

Draft expected checks:

```bash
PYTHONPATH=src python -m unittest tests.application.protocol.test_evaluate_result_dtos tests.test_audit_evidence_graph tests.test_audit_evidence_graph_render
PYTHONPATH=src python -m unittest tests.test_pyreason_evidence_graph tests.test_souffle_evidence_graph tests.test_problog_evidence_graph
ruff check src/factgraph/application/protocol/evaluate_result.py src/factgraph/audit/evidence_graph.py tests/application/protocol/test_evaluate_result_dtos.py tests/test_audit_evidence_graph.py
git diff --check
git status --short --branch
```

Step 4.6 must confirm the final focused suite based on scoped file set.

## 10. Outcome / Deviations

### 10.1 Landed artifacts

| Commit | Stage | Result |
|---|---|---|
| `1ad49592` | draft | Created the T8-A metadata/validation foundation blueprint pair with Q1-Q9 pending for source-backed inventory. |
| `35d6fe61` | scoped | Completed Step 4.6 inventory, selected a private module-level builder/checker shape, and kept T8-A as one M-class blueprint split into A-1/A-2 implementation commits. |
| `b78a4091` | runtime A-1 | Added the central metadata payload helper, exact §10.3 key constants, and private metadata checker while preserving `_evidence_metadata_for_row_result(row, result)`. |
| `916f0813` | runtime A-2 | Wired metadata/envelope consistency validation into the row explanation graph gate and passed-row graph builder. |
| `406a7001` | tests | Added metadata gate tests for missing, extra, and wrong metadata while preserving existing fallback behavior. |

### 10.2 Runtime outcome

T8-A shipped the metadata/validation foundation without changing public API
shape. `evaluate_result.py` now has a private §10.3 metadata key tuple and set,
plus `_evidence_metadata_payload_for_row_result(...)` as the single source of
truth for graph metadata. `_evidence_metadata_for_row_result(row, result)` keeps
its existing signature and now follows a build -> freeze -> validate path.

The checker is deliberately private and exact: it rejects missing keys, extra
keys, and per-key value drift by regenerating the expected payload from the same
`EvaluateResult` + row context. That regenerate-and-compare shape keeps value
consistency DRY: future field maintenance happens in one payload helper instead
of two parallel maps.

### 10.3 C135 runtime invariant

C135 moved from design commitment to runtime-enforced invariant. The graph
metadata set remains the exact 14-key §10.3 contract, `run_id` remains
envelope-only, and row graph metadata is validated against the same
row/result context that produced the explanation envelope.

The validation is always-on and internal. It does not use Python `assert`, an
environment flag, a public validator object, or a new SDK/audit API surface.

### 10.4 Failure semantics

The existing `ValueError -> Explanation(status="unsupported",
code="GRAPH_VALIDATION_FAILED")` behavior is preserved. A builder that raises
`ValueError`, or returns a structurally valid `EvidenceGraph` with bad
metadata, still becomes an unsupported explanation with no partial graph.

Non-`EvidenceGraph` builder returns remain hard protocol violations. The new
`isinstance(evidence, EvidenceGraph)` guard avoids reclassifying that path as a
soft graph-validation failure; `Explanation.__post_init__` continues to raise
`ProtocolShapeError` for invalid evidence object shape as it did before T8-A.

### 10.5 Verification

Focused verification passed:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.protocol.test_evaluate_result_dtos \
  tests.test_audit_evidence_graph \
  tests.test_audit_evidence_graph_render
# 34 OK

PYTHONPATH=src python -m unittest \
  tests.test_pyreason_evidence_graph \
  tests.test_souffle_evidence_graph \
  tests.test_problog_evidence_graph
# 9 OK

ruff check \
  src/factgraph/application/protocol/evaluate_result.py \
  src/factgraph/audit/evidence_graph.py \
  tests/application/protocol/test_evaluate_result_dtos.py \
  tests/test_audit_evidence_graph.py
# clean

git diff --check
# clean
```

Sacred `master` remained `562c74195df43e933bed92a3ff25de94dd8ce666`.
The dirty baseline remained the four modified tracked docs/notebooks plus two
untracked reference directories.

### 10.6 Deviations and non-goals

No docs commit was needed: the shipped behavior is internal contract hardening
for the already documented §10.3 metadata bridge and does not change user-facing
audit, SDK, or renderer semantics.

No T8-B/T8-C/T8-D work landed. The cycle did not import candidate evidence tree
or adapter provenance code, did not add richer graph topology, did not change
`EvidenceGraph` schema, did not change service/OpenAPI, and did not touch
release machinery, match, database/view runtime, or the dirty baseline.
