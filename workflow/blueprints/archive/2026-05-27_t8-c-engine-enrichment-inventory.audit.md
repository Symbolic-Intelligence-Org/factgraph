# Audit: T8-C Engine Enrichment Inventory

- Status: implemented
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/archive/2026-05-27_t8-c-engine-enrichment-inventory.md`
- Stage: archived
- Class: S/M (design-only planning inventory)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current `4 M + 1 D + 3 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | `e3bb4ecc` | T8-C inventory blueprint pair drafted | Triggered after T8-B-2 + T8-D round 2 completed native/Souffle loop; Q1-Q12 intentionally pending for Step 4.6. |
| 2026-05-27 | scoped | `17d07d48` | Step 4.6 source-backed inventory completed | Verified ProbLog/PyReason are provenance-bearing, mapped T10 dependency per C-id, selected blueprint-only split plan. |
| 2026-05-27 | closure | `d6b4eed3` | T8-C inventory cycle closed | Design-only cycle; no runtime/test/docs implementation. |

## 2. Step 4.6 Inventory Results

Read-only findings:

- ProbLog/PyReason SupportArtifact-free finding verified by `rg 'SupportArtifact\(' src/factgraph/adapters/problog/` and `rg 'SupportArtifact\(' src/factgraph/adapters/pyreason/`, both with no matches.
- `_support.py:17-20` separates witness-bearing native/Souffle support from provenance-bearing PyReason/ProbLog support.
- ProbLog current graph converter is adapter trace/provenance: `adapters/problog/provenance.py:187-297`, with adapter-local metadata at `:291-296`, `EDGE_DERIVES`, and tests at `tests/test_problog_evidence_graph.py:45-110`.
- PyReason current graph converter is timeline/event provenance: `adapters/pyreason/provenance.py:113-245`, with adapter-local metadata at `:237-244`, `EDGE_UPDATES`, and tests at `tests/test_pyreason_evidence_graph.py:15-185`.
- Current row-result metadata bridge remains T8-A's 14-key gate at `evaluate_result.py:59-75` and `:1027-1075`; T8-C planning does not widen `_FORM1_ROW_SUPPORT_KINDS` at `:76-77`.
- T10 dependencies are per-engine, not one global blocker: C76 gates ProbLog; C74/C77/C78 gate PyReason Form 2.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Which architecture path should T8-C use? | Answered: adapter-side metadata bridge / provenance row bridge; split by engine. |
| Q2 | What is the current ProbLog adapter evidence shape? | Answered: adapter trace graph, not §10.3 row-result graph. |
| Q3 | What is the current PyReason adapter evidence shape? | Answered: timeline graph, Form 2 still sketch/deferred. |
| Q4 | How do T10 C74 / C76 / C77 / C78 affect T8-C? | Answered with 4x2 dependency matrix. |
| Q5 | Should T8-C split into ProbLog and PyReason sub-cycles? | Answered: yes, T8-C-1 ProbLog then T8-C-2 PyReason. |
| Q6 | Is PyReason Form 2 temporal in T8-C-2 scope or deferred? | Answered: deferred until D11/Form 2 design and PyReason T10 locks. |
| Q7 | Is C119 ProbLog multi-path DAG in first ProbLog scope or deferred? | Answered: defer full multi-path from first ProbLog tranche unless adapter inventory proves ready. |
| Q8 | Does T8-C handle C136 aggregate envelope? | Answered: no, defer/separate. |
| Q9 | What is the engine-meta extension policy? | Answered: per-engine namespaced fields inside `engine_meta`; no flattening or top-level metadata keys. |
| Q10 | Is Nemo in any T8-C scope? | Answered: no, D13 deferred. |
| Q11 | What durable output shape should this cycle produce? | Answered: Option B blueprint-only split plan. |
| Q12 | Are there stop/amend findings? | Answered: none for planning; implementation is gated. |

## 4. Risk Register

| Risk | Impact | Step 4.6 result |
|---|---|---|
| Reviewer SupportArtifact-free finding is accepted without verification | Wrong architecture path | Mitigated: independently verified with grep and `_support.py` taxonomy. |
| T8-C starts runtime work inside planning cycle | Scope creep | Mitigated: no runtime/test/user-doc edits; blueprint/audit only. |
| T10 dependency is described too broadly | Blocks useful engine-local planning or starts work too early | Mitigated: C76 gates ProbLog; C74/C77/C78 gate PyReason. |
| PyReason Form 2 sketch is treated as implementation-ready | Premature temporal schema commitment | Mitigated: D11 / §8.11 defer PyReason Form 2. |
| Engine-specific metadata is flattened into generic fields | Violates §15.2 non-goal | Mitigated: scoped policy is per-engine namespaced `engine_meta`, no top-level graph metadata changes. |
| Dirty baseline is touched | Workflow violation | Mitigated: staged files limited to active blueprint/audit pair. |

## 5. Verification

```bash
PYTHONPATH=src python -m unittest \
  tests.test_problog_evidence_graph \
  tests.test_pyreason_evidence_graph \
  tests.test_audit_evidence_graph
# Ran 19 tests in 0.004s - OK

git diff --check
# OK

git status --short --branch
# ahead by scoped planning commits; dirty baseline preserved as 4 M + 1 D + 3 U
```

## 6. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q12 answered.
- [x] Output shape selected.
- [x] Closure notes filled.

## 7. Closure Notes

Closed as implemented design-only planning.

Key decisions:

- Reviewer SupportArtifact-free finding was source-backed verified, not assumed.
- T8-C cannot reuse the T8-B witness-bearing Form 1 helper path directly.
- Future T8-C implementation should use an adapter-side metadata bridge /
  provenance row bridge, preserving adapter converter boundaries and T8-A
  row-result metadata gates.
- T8-C splits into T8-C-1 ProbLog and T8-C-2 PyReason.
- T8-C-1 starts only after C76 or a ProbLog-specific semantics blueprint locks
  probability producer/consumer fields.
- T8-C-2 waits for D11/Form 2 plus C74/C77/C78 locks.
- Engine-specific fields should be namespaced inside `engine_meta`; no
  flattening into generic root fields and no top-level graph metadata changes.

Verification:

- Focused no-op baseline: 19 OK.
- `git diff --check`: clean.
- Dirty baseline preserved as `4 M + 1 D + 3 U`.
- Sacred master unchanged at `562c74195df43e933bed92a3ff25de94dd8ce666`.
