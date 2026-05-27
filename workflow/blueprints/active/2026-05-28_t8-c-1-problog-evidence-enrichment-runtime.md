# Task Blueprint: T8-C-1 ProbLog Evidence Enrichment Runtime

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: M (runtime implementation)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t8-c-1-problog-evidence-enrichment-runtime.audit.md`
- Trigger: T10-1 shipped C76 ProbLog uncertainty projection at `cde072fa`, and T8-C-1 inventory shipped at `bd5baeec`. This runtime cycle implements the T8-C-1 inventory decisions: trace-payload projection memory, private provenance row context, ProbLog row-result bridge, exact 14-key metadata, and namespaced `engine_meta["problog"]`.

## 0. Scope Locks

### In scope

This is the **T8-C-1 ProbLog runtime implementation cycle**. It must implement
the T8-C-1 inventory's locked plan, not reopen it.

Runtime scope:

1. ProbLog adapter projection decision memory producer:
   - Extend `src/factgraph/adapters/problog/problog_export.py` and
     `src/factgraph/adapters/problog/engine_eval.py` so export-time probability
     projection produces a structured decision table.
   - Record policy, `raw_kind`, `bound`, resolved point probability, source, and
     assertion id where available.
   - Attach the table to `ProvenanceEnvelope.payload`, for example under
     `payload["uncertainty_projections"]`.
2. Private provenance row context plumbing:
   - Add SDK/protocol plumbing parallel to `_row_support_artifacts`, not inside
     `_FORM1_ROW_SUPPORT_KINDS`.
   - `EvaluateResult` may hold a private frozen mapping such as
     `_row_provenance_envelopes`, with public shape, repr/equality/hash behavior,
     and row DTO shape preserved.
3. ProbLog row-result graph bridge:
   - Add a `PROBLOG_PROVENANCE_KIND` row branch inside
     `_build_passed_row_evidence_graph(...)`.
   - Preserve the T8-A validation sequence.
   - Build row-result `EvidenceGraph`s with top-level T8-A 14-key metadata,
     ProbLog trace summary in namespaced `engine_meta["problog"]`, and
     uncertainty projection details under
     `engine_meta["problog"]["uncertainty_projection"]`.
4. Focused tests and audit module docs:
   - Implement the T8-C-1 inventory §3.7 test matrix.
   - Update `src/factgraph/audit/docs/02_evidence_graph.md` to mark ProbLog
     row-result evidence as shipped, with user-facing docs deferred to T8-D
     round 3.

### Out of scope

- User-facing quickstart / SDK guide / `docs/official/kernel/` updates.
- T8-D round 3 docs.
- PyReason, Nemo, aggregate envelope, Form 2, or D11 work.
- C119 full multi-path DAG implementation.
- T10-2 / T10-3 / C74 / C77 / C78 work.
- D20 match witness, failed graph, why-not, counterfactual, service/OpenAPI,
  Database/view, match API, `fg.eval.run`, release, PyPI, tags, or dirty
  baseline cleanup.
- `EvidenceGraph` DTO schema changes.
- Top-level 14-key graph metadata changes.
- `_FORM1_ROW_SUPPORT_KINDS` widening.
- `_WITNESS_BEARING_SUPPORT_KINDS` widening.
- Rewriting `problog_trace_to_evidence_graph(...)` so existing candidate
  converter flat `engine_meta` behavior changes.
- Weakening T8-A 14-key validation or T8-A always-on validation gates.
- Changing T8-B-1 native Form 1 or T8-B-2 Souffle Form 1 behavior.
- Changing T10-1 C76 adapter execution semantics, including default reject.
- Weakening `write_protocol._validate_no_removed_uncertainty_keys` or any C110
  legacy `confidence` rejection behavior.
- Governance/workflow files.
- Sacred `master` changes.
- Dirty baseline changes. Current observed baseline is `4 M + 1 D + 5 U`,
  including the newly observed untracked
  `workflow/design/design-points/active/ledger-schema-specification.zh.md`.
- Reopening T8-C-1 inventory Q1-Q9. If an inventory decision is wrong, stop and
  amend the archived inventory instead of silently diverging.

### Stop / amend triggers

Pause before implementation or stop mid-cycle if:

1. Inventory Q1 trace-payload implementation shows `ProvenanceEnvelope` cannot
   carry the structured projection decision table without changing the envelope
   DTO/schema.
2. Inventory Q2 private row context implementation shows a parallel mapping
   would bypass or weaken T8-A always-on validation gates.
3. Inventory Q3 metadata implementation shows top-level 14-key metadata and
   namespaced ProbLog `engine_meta` conflict, requiring 14-key or
   `EvidenceGraph` DTO changes.
4. Inventory Q4 wrapper strategy proves impossible without changing existing
   `test_problog_evidence_graph.py:67-99` flat converter assertions or
   rewriting `problog_trace_to_evidence_graph(...)`.
5. Inventory Q5 single-path assumption fails because the current candidate path
   actually emits multi-path same-binding evidence requiring C119 in scope.
6. Default `reject` behavior from T10-1 would be converted into an empty,
   degraded, or fallback row evidence graph. `reject` must remain a
   `ProbLogExportError` / execution failure path; if there is no row, there is
   no row evidence graph.
7. Any runtime work requires touching user docs, governance files, sacred
   `master`, or dirty-baseline files.

## 1. Problem

T10-1 shipped C76's ProbLog uncertainty projection execution, and T8-C-1
inventory has locked the evidence enrichment architecture. ProbLog can already
produce adapter-local `EvidenceGraph`s for candidate/provenance readback, but
row-level `EvaluateRow.explain()` still falls back to single-node row evidence.

This cycle implements the first ProbLog row-result bridge without changing the
existing candidate converter surface or the native/Souffle Form 1 path.

The core risk is partial or misleading evidence: projection decisions are lost
after export writes the `.pl` program, row-result graph metadata must remain the
exact T8-A 14-key bridge, and T10-1's explicit reject semantics must not be
silently rendered as a graph.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-27_t8-c-1-problog-evidence-enrichment-inventory.md` | Locked Q1-Q10 architecture, test matrix, and out-of-scope boundaries. |
| `workflow/blueprints/archive/2026-05-27_t10-1-problog-uncertainty-projection.md` | C76 shipped source and anti-silent-ignore behavior. |
| `src/factgraph/adapters/problog/problog_export.py` | Export-time probability projection decision point. |
| `src/factgraph/adapters/problog/engine_eval.py` | ProbLog adapter entry and `ProvenanceEnvelope.payload` assembly. |
| `src/factgraph/adapters/problog/provenance.py` | Existing candidate/readback graph converter and flat `engine_meta` surface to preserve. |
| `src/factgraph/sdk/store.py` | SDK candidate-to-row construction and `_row_support_artifacts` plumbing to mirror privately. |
| `src/factgraph/application/protocol/evaluate_result.py` | T8-A metadata bridge, T8-B row dispatch, and future ProbLog row bridge site. |
| `src/factgraph/audit/docs/02_evidence_graph.md` | Audit module docs to align when runtime behavior ships. |
| `tests/test_problog_evidence_graph.py` | Existing converter regression baseline. |
| `tests/test_problog_semantics_profile_migration.py` | T10-1 uncertainty projection behavior baseline. |
| `tests/application/protocol/test_evaluate_result_dtos.py` | Protocol metadata and row evidence regression surface. |

## 3. Step 4.6 Inventory Results

Pending Step 4.6. Required source-backed subsections:

### 3.1 Projection Decision Table Schema

Define the decision table schema and payload embedding point. The scoped answer
must cover:

- `schema_version`.
- `asrt_id`.
- `raw_kind`.
- `bound`.
- `policy`.
- `resolved_probability`.
- `source`, such as `uncertainty_projection`, `legacy_probability`, or
  `default`.
- Whether non-raw legacy probability annotations also get decision rows.
- `payload["uncertainty_projections"]` shape and keying.

### 3.2 `_claim_probability(...)` Minimal API Shape

Decide how `_claim_probability(...)` and
`_claim_raw_uncertainty_probability(...)` expose structured decisions while
remaining compatible with existing direct callers and T10-1 tests.

Compare at least:

- return a dataclass / tuple with `value` + decision;
- keep float return and fill a collector/sink;
- another source-backed option.

### 3.3 Private Row Provenance Context Shape

Specify the SDK/protocol private mapping shape, likely
`_row_provenance_envelopes: Mapping[str, ProvenanceEnvelope] | None`, including:

- where SDK constructs it;
- freeze/copy semantics;
- repr/equality/hash behavior;
- why it stays parallel to `_row_support_artifacts`.

### 3.4 Row Dispatch Branch Position

Define the `_build_passed_row_evidence_graph(...)` branch order. The branch must
preserve the existing metadata validation before dispatch, avoid widening
`_FORM1_ROW_SUPPORT_KINDS`, and keep native/Souffle Form 1 behavior unchanged.

### 3.5 ProbLog Row Graph Builder Location

Decide the builder function shape and location, likely a new
`_build_problog_provenance_row_evidence_graph(...)` beside
`_build_form1_evidence_graph(...)` in `evaluate_result.py`.

The scoped answer must explain how it reuses or wraps
`problog_trace_to_evidence_graph(...)` while preserving the existing converter's
flat candidate/readback behavior.

### 3.6 Namespaced `engine_meta` Field Set

Define exact row-result namespaced fields:

- `engine_meta["problog"]["trace_summary"]`.
- `engine_meta["problog"]["uncertainty_projection"]`.
- Any per-node / per-edge namespaced subfields.

The scoped answer must explain where current converter metadata keys
`event_count`, `answer_count`, `root_goal`, and `answer_probability` move.

### 3.7 Audit Docs Update Scope

Identify the exact `src/factgraph/audit/docs/02_evidence_graph.md` sections to
change. The draft expectation is:

- Mark ProbLog row-result evidence as shipped once runtime lands.
- Explain it remains provenance-row evidence using `EDGE_DERIVES`, not Form 1
  `EDGE_SUPPORTS`.
- Explain namespaced ProbLog `engine_meta`.
- Keep user-facing docs deferred to T8-D round 3.

### 3.8 Test Matrix

Turn the inventory §3.7 sketch into concrete test files/functions. Required
coverage:

1. Existing `tests.test_problog_evidence_graph` converter regressions unchanged.
2. Row-result ProbLog `EvaluateRow.explain()` returns multi-node ProbLog
   evidence rather than single-node fallback.
3. Row-result graph top-level metadata is exactly the T8-A 14-key set and
   excludes ProbLog adapter-local keys.
4. Row-result graph support kind remains `PROBLOG_PROVENANCE_KIND`; edge kind
   remains `EDGE_DERIVES`.
5. Namespaced `engine_meta["problog"]` contains trace summary and no new generic
   flattened ProbLog keys.
6. Midpoint/lower/upper uncertainty projection fixtures record export-time
   projection decision metadata.
7. Default `reject` remains a semantics execution error, not a row evidence
   graph.
8. T8-A/T8-B/T8-D/T10-1 regressions.

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | What is the projection decision table schema? | Exact fields, version marker, keying, and payload embedding point. |
| Q2 | How should `_claim_probability(...)` expose structured decisions? | Compare float+collector, return-object, and any discovered alternative; preserve existing direct callers. |
| Q3 | What private row provenance context field should `EvaluateResult` use? | Field name, type, freeze/copy behavior, repr/equality/hash stance, and SDK construction path. |
| Q4 | Where exactly should `_build_passed_row_evidence_graph(...)` branch? | Branch order and T8-A gate trace. |
| Q5 | What is the complete namespaced `engine_meta` field set? | Root/node/edge `engine_meta["problog"]` keys, trace summary shape, uncertainty projection subkeys, and compatibility rationale. |
| Q6 | What audit docs change is required? | Exact section/table edits and wording boundary for user docs defer. |
| Q7 | What implementation commit split should be used? | Dependency-ordered commit list and file/test scope per commit. |
| Q8 | How is anti-silent-ignore enforced at row bridge level? | Reject path behavior and any additional tests/assertions. |
| Q9 | Does this unblock T8-D round 3? | Expected answer: yes after runtime ships, but user docs remain a separate follow-up cycle. |
| Q10 | Are there stop/amend findings? | None or explicit trigger with next action. |

## 5. Existing Invariants To Preserve

- T8-C-1 inventory Q1-Q10 remain the source of truth unless this runtime cycle
  stops and explicitly amends the archive.
- T8-A top-level 14-key metadata and `run_id` envelope-only behavior remain
  unchanged.
- T8-A metadata validation gates remain always-on.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1 row evidence remain
  unchanged.
- T8-D round 2 user docs continue to mark ProbLog/PyReason row-level evidence
  as deferred until a runtime T8-C behavior ships and a later docs cycle aligns
  user-facing text.
- T10-1 anti-silent-ignore behavior remains intact:
  - SDK default is reject.
  - Adapter reject raises `ProbLogExportError`.
  - Direct `SemanticsProfile` / direct helper paths default to reject.
- C110 legacy uncertainty-key rejection remains intact.
- Existing `problog_trace_to_evidence_graph(...)` candidate/readback flat
  `engine_meta` behavior remains protected.
- `EvidenceGraph` DTO schema and node/edge kind vocabulary remain unchanged.
- `_FORM1_ROW_SUPPORT_KINDS` and `_WITNESS_BEARING_SUPPORT_KINDS` remain
  unchanged.
- C119 full multi-path DAG and C136 aggregate envelope remain deferred.
- Sacred `master` remains `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remains untouched; current observed baseline is `4 M + 1 D +
  5 U`.

## 6. Step 4.6 Inventory Plan

Step 4.6 must produce:

1. Source-backed projection decision schema and API plan.
2. Source-backed private row provenance context shape.
3. Row dispatch gate trace and branch order.
4. ProbLog row graph builder location and wrapping strategy.
5. Namespaced `engine_meta["problog"]` schema.
6. Audit docs edit map.
7. Concrete test matrix.
8. Stop/amend assessment.

Suggested verification commands:

```bash
rg -n "_claim_probability|_claim_raw_uncertainty_probability|_DEFAULT_UNCERTAINTY_PROJECTION" src/factgraph/adapters/problog/problog_export.py
rg -n "ProvenanceEnvelope|_remember_provenance_envelope|_provenance_envelopes|explain_provenance" src/factgraph/core/store/runtime.py src/factgraph/core/store/_support.py
rg -n "_row_support_artifacts|_row_support_artifacts_for_candidates|_row_provenance" src/factgraph/sdk/store.py src/factgraph/application/protocol/evaluate_result.py
rg -n "_build_passed_row_evidence_graph|_build_form1_evidence_graph|_FORM1_ROW_SUPPORT_KINDS" src/factgraph/application/protocol/evaluate_result.py
rg -n "engine_meta|trace_summary|uncertainty_projection|ProbLog|problog" src/factgraph/audit/docs/02_evidence_graph.md
```

## 7. Proposed Implementation Split

Candidate commit split:

1. `feat(problog): emit projection decision table`
   - `_claim_probability(...)` / export-time projection memory.
   - `ProvenanceEnvelope.payload["uncertainty_projections"]` attachment.
2. `feat(protocol): add private row provenance context`
   - `EvaluateResult._row_provenance_envelopes`.
   - SDK result construction plumbing.
3. `feat(protocol): bridge problog provenance to row evidence`
   - `_build_passed_row_evidence_graph(...)` provenance branch.
   - New ProbLog row-result builder/wrapper.
   - Namespaced `engine_meta["problog"]`.
4. `test(problog): cover problog row evidence bridge`
   - Implement the 7-class matrix plus regressions.
5. `docs(audit): mark problog row evidence shipped`
   - Audit module docs only.
6. `docs(blueprint): close T8-C-1 problog evidence enrichment runtime`
7. `docs(blueprint): archive T8-C-1 problog evidence enrichment runtime`

If implementation proves smaller, commits 2 and 3 may be combined only if the
audit records why partial-ship risk remains controlled.

## 8. Acceptance Checklist

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed inventory completed.
- [ ] Q1-Q10 answered.
- [ ] Projection decision memory producer shipped.
- [ ] Private row provenance context shipped.
- [ ] ProbLog row-result bridge shipped.
- [ ] Namespaced `engine_meta["problog"]` shipped.
- [ ] Focused tests cover the T8-C-1 matrix.
- [ ] Audit module docs updated.
- [ ] Anti-silent-ignore behavior preserved.
- [ ] T8-A/T8-B/T8-D/T10-1 invariants preserved.
- [ ] `git diff --check` clean.
- [ ] Focused tests pass.
- [ ] Full discover run and delta explained against baseline
  `2011 tests / 72 failures / 231 errors`.
- [ ] Dirty baseline and sacred master preserved.

## 9. Verification Commands

Candidate verification after implementation:

```bash
PYTHONPATH=src python -m unittest tests.test_problog_evidence_graph tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph tests.application.protocol.test_evaluate_result_dtos
PYTHONPATH=src python -m unittest discover tests
ruff check src/factgraph/adapters/problog/problog_export.py src/factgraph/adapters/problog/engine_eval.py src/factgraph/adapters/problog/provenance.py src/factgraph/application/protocol/evaluate_result.py src/factgraph/sdk/store.py
git diff --check
git status --short --branch
```

## 10. Outcome / Deviations

Pending Step 4.6 inventory / implementation.
