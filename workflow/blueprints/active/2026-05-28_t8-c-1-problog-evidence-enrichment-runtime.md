# Task Blueprint: T8-C-1 ProbLog Evidence Enrichment Runtime

- Status: implemented
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

### 3.1 Projection Decision Table Schema

Source facts:

- `export_problog(...)` normalizes the C76 projection once at
  `src/factgraph/adapters/problog/problog_export.py:44-55`.
- Each active claim calls `_claim_probability(...)` at `problog_export.py:95-99`
  before the `.pl` line stores only `_format_probability(prob)`.
- Raw uncertainty policy is applied in `_claim_raw_uncertainty_probability(...)`
  at `problog_export.py:203-265`.
- `_attach_problog_provenance(...)` constructs the `ProvenanceEnvelope.payload`
  from `trace_dict` at `src/factgraph/adapters/problog/engine_eval.py:173-203`.
- `ProvenanceEnvelope.payload` is already an arbitrary `dict[str, Any]` per
  `src/factgraph/core/store/_support.py:147-162`, so no envelope DTO/schema
  change is needed.

Scoped schema:

```python
payload["uncertainty_projections"] = {
    "schema_version": 1,
    "decisions_by_asrt_id": {
        "<asrt_id>": {
            "asrt_id": "<asrt_id>",
            "source": "uncertainty_projection" | "legacy_probability" | "default",
            "raw_kind": "probabilistic" | "possibilistic" | None,
            "bound": [lower, upper] | None,
            "policy": "reject" | "lower" | "midpoint" | "upper" | "identity_probability" | None,
            "resolved_probability": float,
        },
    },
}
```

Rules:

- `uncertainty_projection` decisions are recorded only for raw
  `shared/semantic/raw_kind` + `shared/semantic/bound` carriers that reach
  `_claim_raw_uncertainty_probability(...)`.
- Existing `problog/semantic/probability` and `shared/semantic/probability`
  point carriers may record `source="legacy_probability"` so row evidence can
  distinguish raw projection from pre-projected point probability.
- Claims with no probability annotation may record `source="default"` and
  `resolved_probability=1.0` only if tests need to explain why the ProbLog line
  received `1.0`; otherwise the implementation may omit default rows to keep
  metadata compact. The scoped implementation should choose one behavior and
  test it.
- `reject` decisions do not produce row evidence because export raises
  `ProbLogExportError` before candidates and rows exist.

### 3.2 `_claim_probability(...)` Minimal API Shape

| Option | Shape | Risk | Decision |
|---|---|---|---|
| A. Change `_claim_probability(...)` to return a decision object | Existing direct callers and tests must unwrap `.resolved_probability`; T10-1 already fixed direct-call compatibility once. | Medium. Reopens the same direct-call surface that Step 4.7 protected in T10-1. | Reject. |
| B. Keep `_claim_probability(...) -> float` and add an optional collector/sink | Existing callers still get `float`; export can pass a dict that `_claim_probability(...)` fills with decision dicts keyed by `asrt_id`. | Low/medium. Side-effect API needs careful tests, but preserves all direct callers. | **Selected.** |
| C. Add a new public-ish `_claim_probability_decision(...)` helper and make `_claim_probability(...)` a wrapper | Clear separation, but larger refactor of `_claim_raw_uncertainty_probability(...)` and tests. | Medium. More code churn than needed for first bridge. | Defer unless B becomes awkward during implementation. |

Scoped answer: future implementation should keep `_claim_probability(...)`
returning `float` and add an optional keyword-only decision sink, for example
`projection_decisions: dict[str, dict[str, Any]] | None = None`. The sink is
filled only after probability validation succeeds. This preserves:

- direct helper tests in `tests/test_problog_export.py` that call
  `_claim_probability(...)` without projection plumbing;
- T10-1 tests in `tests/test_problog_semantics_profile_migration.py`;
- `export_problog(...)`'s current writer loop, which only needs the point
  probability at `problog_export.py:95-104`.

### 3.3 Private Row Provenance Context Shape

Source facts:

- `EvaluateResult` already has private `_row_support_artifacts` with
  `repr=False`, `compare=False`, and `hash=False` at
  `src/factgraph/application/protocol/evaluate_result.py:156-184`.
- `EvaluateResult.__post_init__` validates and freezes row support artifacts at
  `evaluate_result.py:215-220`.
- SDK row construction happens at `src/factgraph/sdk/store.py:2693-2736`.
- `_row_support_artifacts_for_candidates(...)` only admits
  `_FORM1_ROW_SUPPORT_KINDS` at `sdk/store.py:2742-2754`.

Scoped field:

```python
_row_provenance_envelopes: Mapping[str, ProvenanceEnvelope] | None = field(
    default=None,
    repr=False,
    compare=False,
    hash=False,
)
```

Implementation policy:

- Add `_validate_row_provenance_envelopes(...)` beside
  `_validate_row_support_artifacts(...)`.
- Validate keys are known `row_id`s.
- Validate values are `ProvenanceEnvelope`.
- Freeze with `MappingProxyType`.
- SDK adds `_row_provenance_envelopes_for_candidates(candidates, rows)` parallel
  to `_row_support_artifacts_for_candidates(...)`.
- That SDK helper should accept only `candidate.support_kind ==
  PROBLOG_PROVENANCE_KIND`, then look up `store._lookup_provenance_envelope(...)`
  using `candidate.support_digest`.
- Do not widen `_FORM1_ROW_SUPPORT_KINDS`; ProbLog is provenance-bearing, not a
  witness-bearing Form 1 support kind.

### 3.4 Row Dispatch Branch Position

Source facts:

- `_explain_live_row(...)` builds metadata at `evaluate_result.py:635`, calls
  the builder at `:637-638`, and revalidates an `EvidenceGraph` at `:639-640`.
- `_build_passed_row_evidence_graph(...)` currently validates metadata before
  dispatch at `evaluate_result.py:841-847`.
- Native/Souffle Form 1 dispatch starts at `evaluate_result.py:847-849`.

Scoped branch order:

```python
_validate_evidence_metadata_for_row_result(metadata, row, result)
provenance_envelope = result._row_provenance_envelopes.get(row.row_id)
if provenance_envelope is not None:
    return _build_problog_provenance_row_evidence_graph(row, result, metadata, provenance_envelope)
support_artifact = result._row_support_artifacts.get(row.row_id)
if support_artifact is not None:
    return _build_form1_evidence_graph(row, result, metadata, support_artifact)
return single_node_fallback
```

Rationale:

- This follows the reviewer telegraph: the new provenance branch is after the
  T8-A metadata validation and before `_build_form1_evidence_graph(...)`.
- Native/Souffle rows do not receive `_row_provenance_envelopes`, so Form 1
  behavior remains unchanged.
- If an impossible future row has both a ProbLog provenance envelope and a
  support artifact, the provenance mapping is a narrower row-context signal and
  should win only after validating that the envelope is ProbLog-shaped.

### 3.5 ProbLog Row Graph Builder Location

Scoped builder:

```python
def _build_problog_provenance_row_evidence_graph(
    row: EvaluateRow,
    result: EvaluateResult,
    metadata: Mapping[str, Any],
    provenance_envelope: ProvenanceEnvelope,
) -> EvidenceGraph:
    ...
```

Location: `src/factgraph/application/protocol/evaluate_result.py`, beside
`_build_form1_evidence_graph(...)`.

Implementation strategy:

1. Validate `provenance_envelope.engine == "problog"` and
   `payload_type == "proof_trace"`.
2. Convert or parse the envelope payload into the existing ProbLog trace model.
3. Call `problog_trace_to_evidence_graph(...)` for topology and adapter truth.
4. Return a row-result wrapper graph:
   - `graph_id=f"{result.result_id}:{row.row_id}"`.
   - `engine=result.engine`.
   - `support_kind=PROBLOG_PROVENANCE_KIND`.
   - `metadata=metadata`.
   - same nodes/edges/topology as converter, but row-result `engine_meta`
     normalized to `engine_meta["problog"]`.

Why wrap instead of rewrite:

- Existing candidate converter flat assertions live at
  `tests/test_problog_evidence_graph.py:67-99`.
- Existing converter graph metadata is adapter-local at
  `src/factgraph/adapters/problog/provenance.py:291-296`.
- Row-result top-level metadata must be T8-A 14-key metadata from
  `evaluate_result.py:59-75`.
- A wrapper lets future row evidence use the converter as topology substrate
  while preserving candidate/readback behavior.

### 3.6 Namespaced `engine_meta` Field Set

Current converter fields:

- Graph metadata at `src/factgraph/adapters/problog/provenance.py:291-296`:
  `event_count`, `answer_count`, `root_goal`, `answer_probability`.
- Node flat `engine_meta` at `provenance.py:244-256`: `goal`, `goal_name`,
  `goal_args`, `call_started_seconds`, `location`, `result_terms`,
  `bindings_text`, `elapsed_seconds`, `event_status`, `synthetic_goal`,
  `answer_probability`.
- Edge flat `engine_meta` at `provenance.py:275-279`: `parent_goal`,
  `child_goal`, `parent_location`.

Scoped row-result shape:

Root node:

```python
engine_meta={
    "problog": {
        "trace_summary": {
            "event_count": <int>,
            "answer_count": <int>,
            "root_goal": <str>,
            "root_answer_probability": <float | None>,
        },
        "trace": { ... namespaced former flat node fields ... },
        "uncertainty_projection": {
            "schema_version": 1,
            "decision_count": <int>,
            "decisions_by_asrt_id": {...},
        },
    }
}
```

Non-root nodes:

```python
engine_meta={
    "problog": {
        "trace": { ... namespaced former flat node fields ... },
        "uncertainty_projection": <decision | None>,
    }
}
```

Edges:

```python
engine_meta={
    "problog": {
        "trace_edge": {
            "parent_goal": ...,
            "child_goal": ...,
            "parent_location": ...,
        }
    }
}
```

The implementation may attach per-node projection decisions only when a trace
node can be tied to an assertion id, for example by an `edb_fact(...)` goal.
The root summary must still include aggregate projection count / decisions so
projection memory is not lost when no individual node match is available.

### 3.7 Audit Docs Update Scope

Source facts:

- The intro currently says only native and Souffle row explanations produce
  live row-level graphs at `src/factgraph/audit/docs/02_evidence_graph.md:41-46`.
- Frozen enumeration text says native/Souffle row graphs use `supports`, while
  `derives` and `updates` are reserved at `02_evidence_graph.md:120-122`.
- Current boundaries list durable package converter behavior for `problog` at
  `02_evidence_graph.md:186-195`, and row explanations for native/Souffle at
  `:196-199`.
- Boundary text still says runtime live explain paths do not directly support
  `problog_provenance_v1` at `:210-212`.

Scoped docs edits after runtime ships:

- Update §1 to say native/Souffle row explanations produce Form 1 graphs, and
  ProbLog row explanations produce provenance-row graphs using ProbLog trace
  topology.
- Update §3 enumeration text: `supports` remains native/Souffle Form 1;
  ProbLog row evidence uses `derives`; `updates` remains PyReason/timeline.
- Update §6 current boundaries to add ProbLog row explanations as live
  row-level provenance graphs and keep candidate/service audit-package
  converter behavior separate.
- Remove `problog_provenance_v1` from the "runtime live explain does not
  directly support" line once the bridge ships.
- Mention namespaced `engine_meta["problog"]` at audit-module level only.
- Do not update user-facing quickstart or SDK guide in this cycle.

### 3.8 Test Matrix

Future implementation should add or update tests in this shape:

| Area | Candidate test |
|---|---|
| Existing converter regression | Keep `tests.test_problog_evidence_graph` unchanged; it protects flat candidate/readback shape. |
| Projection decision producer | Add `tests/test_problog_semantics_profile_migration.py` tests proving `export_problog(...)` emits decision payload when given a sink or return wrapper, while `_claim_probability(...)` direct callers still return `float`. |
| Row provenance context validation | Add protocol DTO tests that unknown row ids or non-`ProvenanceEnvelope` mapping values raise `ProtocolShapeError`. |
| Row bridge topology | Add a protocol or SDK test where a ProbLog candidate with `PROBLOG_PROVENANCE_KIND` yields `EvaluateRow.explain().evidence` with multiple nodes/`EDGE_DERIVES`, not single-node fallback. |
| 14-key metadata | Assert exact T8-A metadata keys and absence of ProbLog adapter-local top-level keys. |
| Namespaced engine_meta | Assert root/node/edge `engine_meta` only exposes `problog` namespace for row-result graph, including `trace_summary` and projection decision metadata. |
| Reject anti-silent-ignore | Keep/extend T10-1 test proving default reject raises before rows exist; assert no row evidence graph is produced for reject. |
| Horizontal regressions | Run native/Souffle Form 1 protocol tests, T10-1 ProbLog tests, audit evidence graph tests, and full discover. |

## 4. Open Questions For Step 4.6

| ID | Question | Required scoped output |
|---|---|---|
| Q1 | What is the projection decision table schema? | Use `payload["uncertainty_projections"] = {"schema_version": 1, "decisions_by_asrt_id": {...}}`; each decision records `asrt_id`, `source`, `raw_kind`, `bound`, `policy`, and `resolved_probability`. Raw C76 decisions use `source="uncertainty_projection"`. Legacy point probability and default `1.0` may be recorded with `source="legacy_probability"` / `"default"` if implementation chooses compact-vs-complete behavior and tests it. |
| Q2 | How should `_claim_probability(...)` expose structured decisions? | Keep `_claim_probability(...) -> float`; add optional keyword-only decision sink. Reject return-object as unnecessary direct-caller churn. Defer a separate `_claim_probability_decision(...)` helper unless the sink becomes awkward in implementation. |
| Q3 | What private row provenance context field should `EvaluateResult` use? | Add `_row_provenance_envelopes: Mapping[str, ProvenanceEnvelope] | None` with `repr=False`, `compare=False`, `hash=False`, validation/freeze in `__post_init__`, and SDK helper parallel to `_row_support_artifacts_for_candidates(...)` that admits only `PROBLOG_PROVENANCE_KIND`. |
| Q4 | Where exactly should `_build_passed_row_evidence_graph(...)` branch? | After `_validate_evidence_metadata_for_row_result(...)`, check `_row_provenance_envelopes` first, then Form 1 `_row_support_artifacts`, then single-node fallback. The provenance branch must validate ProbLog envelope shape before building. |
| Q5 | What is the complete namespaced `engine_meta` field set? | Root `engine_meta["problog"]` contains `trace_summary`, `trace`, and `uncertainty_projection`; non-root nodes contain namespaced `trace` plus per-node projection decision when linkable; edges contain `engine_meta["problog"]["trace_edge"]`. Former top-level graph metadata keys move under `trace_summary`. Former flat node/edge keys move under `trace` / `trace_edge`. |
| Q6 | What audit docs change is required? | Update `src/factgraph/audit/docs/02_evidence_graph.md` §1, §3, and §6 only. Mark ProbLog row-result evidence as shipped provenance-row evidence using `EDGE_DERIVES`, document namespaced `engine_meta["problog"]`, keep candidate converter/readback distinct, and defer user docs to T8-D round 3. |
| Q7 | What implementation commit split should be used? | Keep draft §7 split: projection decision producer, private row provenance context, row bridge, tests, audit docs, closure, archive. Commits 2+3 may combine only if audit explains partial-ship control. |
| Q8 | How is anti-silent-ignore enforced at row bridge level? | Reject remains export/evaluation failure: no candidates, no rows, no row evidence. Add/keep tests that default reject raises `ProbLogExportError` / SDK error before `EvaluateResult`; do not add fallback empty evidence for reject. |
| Q9 | Does this unblock T8-D round 3? | Yes, after runtime and audit docs ship. User-facing quickstart / SDK guide remain an independent T8-D round 3 follow-up and are out of this cycle. |
| Q10 | Are there stop/amend findings? | None. `ProvenanceEnvelope.payload` can hold dict data; private row context can preserve T8-A gates; wrapper namespacing avoids candidate converter changes; C119 remains deferred. |

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

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed inventory completed.
- [x] Q1-Q10 answered.
- [x] Projection decision memory producer shipped.
- [x] Private row provenance context shipped.
- [x] ProbLog row-result bridge shipped.
- [x] Namespaced `engine_meta["problog"]` shipped.
- [x] Focused tests cover the T8-C-1 matrix.
- [x] Audit module docs updated.
- [x] Anti-silent-ignore behavior preserved.
- [x] T8-A/T8-B/T8-D/T10-1 invariants preserved.
- [x] `git diff --check` clean.
- [x] Focused tests pass.
- [x] Full discover run and delta explained against baseline
  `2011 tests / 72 failures / 231 errors`.
- [x] Dirty baseline and sacred master preserved.

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

Implemented and reviewed. Cycle chain:

1. `29f32cb1` draft blueprint/audit.
2. `6ac4f2cb` source-backed scoped plan.
3. `bc0b0b96` projection decision table producer.
4. `70f305be` private row provenance context.
5. `b3ec909b` ProbLog row-result provenance bridge.
6. `22a06ea5` focused row bridge tests.
7. `a916a856` audit docs alignment.
8. `73c26f5f` lazy import fix for the ProbLog row bridge.

Shipped behavior:

- ProbLog export now records probability/projection decisions in
  `ProvenanceEnvelope.payload["uncertainty_projections"]` without changing
  `_claim_probability(...) -> float` or direct helper call compatibility.
- `EvaluateResult` now carries private frozen `_row_provenance_envelopes`
  parallel to `_row_support_artifacts`; `_FORM1_ROW_SUPPORT_KINDS` and
  `_WITNESS_BEARING_SUPPORT_KINDS` were not widened.
- Passed ProbLog rows now build row-result provenance `EvidenceGraph`s using
  the existing ProbLog trace topology, `EDGE_DERIVES`, exact T8-A 14-key
  top-level metadata, and namespaced `engine_meta["problog"]`.
- Existing candidate/readback converter behavior remains flat and unchanged;
  `provenance.py` and `tests/test_problog_evidence_graph.py` were not touched.
- Audit module docs now mark ProbLog row-result provenance graphs as shipped;
  user-facing docs remain deferred to T8-D round 3.

Verification:

- Focused suite:
  `tests.test_problog_evidence_graph`,
  `tests.test_problog_semantics_profile_migration`,
  `tests.test_problog_export`,
  `tests.test_audit_evidence_graph`,
  `tests.application.protocol.test_evaluate_result_dtos`, and
  `tests.sdk.test_rule_expr_evaluate`: 117 OK.
- Full discover: `2013 tests / 72 failures / 231 errors`, compared with the
  T10-1 baseline `2011 tests / 72 failures / 231 errors`; no failure/error
  composition regression was introduced.
- `ruff check` on touched source files passed.
- `git diff --check` clean.
- Sacred `master` stayed at `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline preserved as `4 M + 1 D + 5 U`.

Deviations and future pings:

- A real protocol/adapter import cycle appeared after the row bridge was added;
  `73c26f5f` resolved it with a lazy import inside the private builder.
- The implementation chose compact projection recording: default `1.0`
  probability rows are not emitted as `source="default"` decisions.
- Projection decisions are carried at the graph root only; per-node projection
  attachment remains a future enrichment if UI needs it.
- `trace_summary.uncertainty_projection_decision_count` duplicates the nested
  projection `decision_count` as a convenience summary.
- The row builder passes `dict(row.bindings)` as the candidate payload to the
  existing converter. The focused fixture validates this path; future broader
  fixture shapes should source-back the fallback behavior before relying on it.
- Full discover total increased by 2 while four focused test methods were
  added; failures and errors remained exactly stable, so no silent regression
  was found.
