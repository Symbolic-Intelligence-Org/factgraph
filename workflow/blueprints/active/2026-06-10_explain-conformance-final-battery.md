# Task Blueprint: Explain Conformance Final — native battery, docs, and full matrix

- Status: scoped
- Created: 2026-06-10
- Last Updated: 2026-06-10
- Type: conformance cleanup / closeout
- Parent: [2026-06-10_explain-conformance-rework.md](./2026-06-10_explain-conformance-rework.md)
- Related Modules:
  - `tests/application/explain/test_prober.py` (native prober unit battery)
  - `tests/sdk/test_explain_conformance_native.py` (native evaluate→explain conformance battery)
  - `src/factgraph/application/explain/docs/README.md` (primary docs sync)
  - `src/factgraph/application/protocol/docs/README.md` (protocol surface docs, if touched)
  - `docs/quickstart/evaluate_and_evidence.md` (known larger stale quickstart; classify scope)
- Audit Log:
  - [2026-06-10_explain-conformance-final-battery.audit.md](./2026-06-10_explain-conformance-final-battery.audit.md)

---

## 1. Problem

Batch A/E/D/B/C closed the conformance audit defects, but the program still
needs closeout:

1. The native conformance tests grew incrementally across batches and need a
   coverage inventory against the audit matrix.
2. Module docs still describe staged S3/S4/S5/S6 boundaries and omit the final
   post-conformance behavior.
3. The parent program needs one final matrix run and explicit closeout evidence
   before it can be marked implemented.

This is a cleanup slice. It must not change source behavior. If the inventory
uncovers a new defect, stop and split a new bugfix batch instead of hiding it
inside final.

## 2. Goals

1. Produce a native conformance battery inventory that maps tests to the audit
   surfaces:
   - repr placeholders and value rendering;
   - atom types (`pred`, compare, builtin/in, `not`);
   - anchoring across inline / projection / external head and OR / join;
   - verdict cascade and true `NotReached`;
   - aggregate support-capture;
   - entity-ref / float64 rendering.
2. Update module docs for the final explain behavior after conformance fixes.
3. Run the full explain/conformance matrix and record command output.
4. Prepare parent program closeout inputs.

## 3. Non-goals

- No source behavior changes.
- No DTO changes.
- No quickstart rewrite unless it is a small targeted stale-reference fix.
  `docs/quickstart/evaluate_and_evidence.md` still has large legacy flat-DAG
  content; if a full rewrite is needed, record it as follow-up rather than
  expanding this cleanup slice.
- No branch push.

## 4. Source Preflight

Confirmed current state:

- Batch C closed in `36abc176`; all conformance bugs from the audit are closed
  by Batch A/E/D/B/C.
- `src/factgraph/application/explain/docs/README.md` still says S3 introduces
  the model, S4 bakes repr, and later slices wire Explanation/adapters. It does
  not describe the final conformance state.
- `src/factgraph/application/protocol/docs/README.md` is closer to current
  shape, but still says adapter rich wiring is deferred in a later note and may
  need a small correction.
- `docs/quickstart/evaluate_and_evidence.md` still contains large legacy
  flat-DAG sections (`EvidenceNode`, `EvidenceEdge`, `root_node_id`, etc.).
  That is likely too large for final cleanup unless narrowly patched.
- Existing test coverage anchors:
  - `tests/application/explain/test_prober.py` covers G1, G2, verdict cascade,
    Batch B rendering, and Batch C NotAtom.
  - `tests/sdk/test_explain_conformance_native.py` covers Batch A row anchoring
    and Batch E aggregate evaluate→explain.
  - adapter tests cover Souffle/ProbLog/PyReason rich evidence.

## 5. Proposed Shape

### 5.1 Battery inventory

Add or update a concise inventory in the final audit log, not necessarily in
source docs, mapping each conformance surface to specific tests. If a high-risk
cell is uncovered but untested, add a test if it is purely coverage and no
behavior change is needed. If adding that test fails, stop and escalate into a
new batch.

### 5.2 Module docs

Update `src/factgraph/application/explain/docs/README.md` to describe final
current behavior:

- paths-model DTOs;
- `probe_native(...)` consuming `RuleExprLoweringPlan`;
- row anchoring via lowered seed vars (SDK-side, Batch A);
- candidate-env backtracking and monotonic witness behavior;
- verdict semantics after Batch D;
- repr rendering after Batch B;
- NotAtom convention after Batch C;
- adapter rich evidence status after S6a/b/c and audit facade cleanup.

Update `src/factgraph/application/protocol/docs/README.md` only if current text
still says adapter rich evidence is deferred.

For `docs/quickstart/evaluate_and_evidence.md`, either:

- apply a very small correction if it is obviously stale and contained; or
- record a follow-up quickstart rewrite in the parent outcome.

### 5.3 Matrix run

Run the final conformance/explain matrix, including at least:

- native prober unit battery;
- native SDK conformance battery;
- protocol evaluate-result DTO/digest tests;
- schema runtime repr tests;
- aggregate support-capture tests;
- Souffle/ProbLog/PyReason evidence tests;
- quick demo if cheap (`examples/explain_layer_demo.py`).

## 6. Boundaries And Invariants

- **INV-no-source-behavior**: final cleanup should not change runtime behavior.
- **INV-no-hidden-defect**: any new failing behavior found during inventory
  becomes a new scoped bugfix batch.
- **INV-doc-truth**: module docs must describe the code now shipped on this
  branch, not the earlier slice roadmap.
- **INV-matrix-record**: parent closeout must record exact matrix commands and
  results.

## 7. Acceptance

- [x] Battery inventory maps conformance surfaces to concrete tests.
- [x] Any uncovered high-risk cells are either covered by new passing tests or
  explicitly deferred with rationale.
- [x] `application/explain/docs/README.md` describes final current behavior.
- [x] `application/protocol/docs/README.md` no longer says adapter rich evidence
  is deferred, if that stale line still exists.
- [x] Quickstart legacy flat-DAG content is classified: tiny patch or follow-up.
- [x] Final matrix passes and commands are recorded.
- [x] No source behavior changes are made unless a new batch is created.

## 8. Implementation Plan

1. Build the test battery inventory from current test files.
2. Run the final matrix once before doc edits to establish current green state.
3. Update module docs and, if safe, narrowly correct protocol docs.
4. Add any purely organizational test coverage if the inventory finds a small
   untested surface that can be covered without behavior changes.
5. Re-run final matrix.
6. Fill final audit outcome and parent program closeout inputs.

## 9. Docs To Update

- `src/factgraph/application/explain/docs/README.md`
- `src/factgraph/application/protocol/docs/README.md` if needed
- possibly `docs/quickstart/evaluate_and_evidence.md` only as a small targeted
  patch or follow-up note

## 10. Outcome / Deviations

Ready for reviewer gate.

Completed in this cleanup:

- native conformance battery inventory;
- `application/explain/docs/README.md` current-state rewrite;
- narrow `application/protocol/docs/README.md` stale adapter dispatch cleanup;
- final matrix run (`144 OK`);
- demo run showing row-anchored friendly evidence.

Deviation / follow-up:

- `docs/quickstart/evaluate_and_evidence.md` still contains broad legacy
  flat-DAG content. It is explicitly deferred to a dedicated quickstart rewrite
  rather than patched piecemeal in this cleanup slice.
