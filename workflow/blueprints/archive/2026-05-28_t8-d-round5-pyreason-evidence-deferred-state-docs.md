# Task Blueprint: T8-D Round 5 PyReason Evidence Deferred-State Docs

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S (docs-only)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/archive/2026-05-28_t8-d-round5-pyreason-evidence-deferred-state-docs.audit.md`
- Trigger: T8-D round 4 shipped at `06e575dd`, closing canonical
  semantics user docs for ProbLog C76 and PyReason C74/C77/C78. Follow-up
  source-back found PyReason row-evidence boundaries are clean but not
  user-facing: `_validate_row_provenance_envelopes` gates row provenance to
  ProbLog proof traces, Form 1 support kinds do not include PyReason, and
  PyReason rows currently fall back to a single-conclusion `EvidenceGraph`.
  Rich PyReason temporal row evidence remains deferred to a future Form 2
  design cycle. The adapter-level
  `pyreason_trace_to_evidence_graph(...)` helper exists as an advanced
  importable escape hatch, but quickstart docs do not yet set user
  expectations.

## 0. Scope Locks

### In scope

This is a docs-only user-facing contract clarification. File scope is capped at
two files.

1. `docs/official/kernel/quickstart/evidence.md` as the primary target:
   - Add a narrow PyReason deferred-state section.
   - Teach that rich PyReason row-evidence timeline graphs are deferred to a
     future Form 2 design cycle.
   - Teach that current `row.evidence` for PyReason rows is a
     single-conclusion graph: degenerate, safe, and intentionally not a
     timeline.
   - Mention `pyreason_trace_to_evidence_graph(...)` as an advanced importable
     for users who already have a PyReason trace payload and need timeline-style
     graph construction before the row-level Form 2 bridge ships.
   - Preserve T8-D round 3 ProbLog row-provenance wording and T8-D round 1
     stability wording.
2. `src/factgraph/sdk/docs/00_user_guide.en.md` only if Step 4.6 finds a
   remaining user-guide gap after T8-D round 4:
   - Add a short note that PyReason row evidence is currently a safe
     single-conclusion fallback and rich timeline row evidence is deferred.
   - Point to the evidence quickstart for details.

### Out of scope

- T8-C-2 runtime or protocol bridge work.
- Runtime changes in `evaluate_result.py`, candidate evidence tree builders, or
  PyReason / ProbLog adapters.
- Form 2 schema definition. This cycle must not define timestep, time-window,
  bound-update, component-identity, or producer/consumer contract details.
- `EvidenceGraph` DTO, 14-key metadata, `_FORM1_ROW_SUPPORT_KINDS`,
  `_WITNESS_BEARING_SUPPORT_KINDS`, or `_PROVENANCE_BEARING_SUPPORT_KINDS`.
- `_validate_row_provenance_envelopes` protocol-gate behavior changes.
- T10 runtime behavior, including T10-1, T10-2-A, T10-2-B, T10-3-A, and
  T10-3-B.
- T8-D round 1/2/3/4 shipped teaching regression.
- Rewriting T8-D round 3 ProbLog row-provenance docs; this cycle may only add a
  PyReason deferred-state note nearby if Step 4.6 confirms the insertion point.
- T8-D round 1 `evidence.md` stability wording for `Inference` / `Branch`.
- ProbLog uncertainty projection teaching; T8-D round 4 already shipped it.
- PyReason canonical semantics teaching; T8-D round 4 already shipped it.
- `rules-and-inferences.md`; T8-D round 4 already cleaned up
  `Inference` / `Query` teaching.
- `assertions.md`; T8-D round 4 already added the T10-1 note.
- Adapter module docs: `src/factgraph/adapters/docs/02_problog_adapter.md` and
  `src/factgraph/adapters/docs/03_pyreason_adapter.md`.
- Audit module docs or other quickstart files.
- Runtime, tests, governance, release machinery, sacred `master`, or dirty
  baseline files.
- Dirty baseline `4 M + 1 D + 6 U`, including untracked design-point files.
- Claim-first ledger design discussion or design-point intake.
- D11 Form 2 design cycle; it remains a separate future design cycle.
- Reopening the current archive lockout set: T10-1, T8-C-1 inventory,
  T8-C-1 runtime, T8-D round 3, memory compaction, T10-2 inventory, T10-2-A,
  T10-2-B, T10-3 inventory, T10-3-A, T10-3-B, and T8-D round 4. If source-back
  contradicts any archive, stop and amend the relevant archive instead of
  silently diverging.

### Stop / amend triggers

Pause and amend before implementation if Step 4.6 shows:

1. `evidence.md` already contains PyReason evidence teaching that conflicts
   with this deferred-state plan, such as an implicit row-level timeline
   promise.
2. The planned insertion would disturb T8-D round 3 ProbLog row-provenance docs
   or T8-D round 1 `Inference` / `Branch` stability wording.
3. `pyreason_trace_to_evidence_graph(...)` has a different signature or import
   path from the planned teaching.
4. `00_user_guide.en.md` already contains or implies PyReason timeline row
   evidence after T8-D round 4.
5. Form 2 schema details begin to leak into docs.
6. Runtime, tests, governance, sacred, dirty-baseline, or untracked
   design-point files need edits.
7. File scope exceeds two files.
8. Cross-doc grep finds broader user-facing PyReason timeline promises that
   cannot be handled within this narrow docs cycle.

## 1. Problem

PyReason semantics are now complete for T10, and T8-D round 4 teaches the public
canonical semantics API. PyReason evidence is a different surface: rich
row-level temporal evidence is intentionally still deferred to a future Form 2
design cycle. Current row-level evidence for PyReason rows is safe but
degenerate: a single-conclusion `EvidenceGraph`, not a timeline.

Without a user-facing note, users can reasonably infer that PyReason
`row.evidence` has timeline semantics because the adapter has a timeline graph
helper and T10 temporal modes now ship. This cycle closes that expectation gap
without implementing T8-C-2 or defining Form 2.

## 2. Inputs

| Source | Role |
|---|---|
| `workflow/blueprints/archive/2026-05-28_t8-d-round4-pyreason-problog-canonical-user-docs.md` | Immediate predecessor; canonical semantics docs are complete. |
| `src/factgraph/application/protocol/evaluate_result.py` | Source for row-evidence protocol gate and single-conclusion fallback. |
| `src/factgraph/core/store/_support.py` | Source for Form 1 / witness / provenance support-kind partitioning. |
| `src/factgraph/adapters/pyreason/provenance.py` | Source for `pyreason_trace_to_evidence_graph(...)` advanced helper. |
| `docs/official/kernel/quickstart/evidence.md` | Primary user-facing target. |
| `src/factgraph/sdk/docs/00_user_guide.en.md` | Optional secondary target if Step 4.6 finds a user-guide gap. |
| `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md` or current location | Design source for Form 2 deferred-state statements, if present. |

## 3. Step 4.6 Source-Backed Inventory

### 3.1 `evidence.md` Current PyReason Surface

`docs/official/kernel/quickstart/evidence.md` already has broad PyReason
boundary wording, but not enough user-facing specificity for the row-evidence
fallback:

| Lines | Current state | Step 4.7 decision |
|---|---|---|
| `:260-281` | Native / Souffle Form 1 row graph contract. | Preserve byte-stably. |
| `:283-292` | T8-D round 3 ProbLog row-provenance graph contract and `engine_meta["problog"]`. | Preserve byte-stably. |
| `:294-298` | Single-`NODE_CONCLUSION` fallback paragraph says PyReason and other unaligned adapter rows may still use fallback or adapter-specific graph shapes. | Expand additively with a PyReason-specific deferred-state paragraph immediately after this paragraph. |
| `:300-310` | Stable graph invariants. | Preserve. |
| `:312-326` | Current boundaries say PyReason row-level Form 1 alignment is future work and `EDGE_UPDATES` remains reserved for PyReason / Form 2 / temporal engine paths. | Keep stable; the new paragraph should clarify PyReason without changing these bullets. |
| `:328-359` | T8-D round 1 stability of `Inference` and `Branch`. | Preserve byte-stably. |

Step 4.6 decision: `evidence.md` needs one narrow PyReason paragraph near
`:294-298`. Do not rewrite the ProbLog section or §7 stability section.

### 3.2 SDK User Guide Need

`src/factgraph/sdk/docs/00_user_guide.en.md:648-681` already says:

- PyReason / ProbLog adapters may produce engine-native evidence and carrier
  data (`:648-651`).
- The public path is `EvaluateResult` plus `Explanation` (`:658-666`).
- Native / Souffle and ProbLog row-evidence shapes are summarized
  (`:672-677`).
- PyReason row-level graphs are future evidence tracks and the guide points to
  the evidence quickstart for full boundaries (`:678-681`).

Step 4.6 decision: do **not** edit the SDK guide in this cycle. Once
`evidence.md` has the precise PyReason deferred-state paragraph, the existing
guide pointer is sufficient and avoids a second implementation file.

### 3.3 User-Facing Fallback Wording

Accepted wording shape for Step 4.7:

- PyReason inference and temporal semantics are shipped.
- At the row-level evidence surface, rich PyReason temporal explanation is
  intentionally deferred to a future Form 2 design cycle.
- For now, PyReason rows that do not have row-level aligned provenance use the
  safe single-`NODE_CONCLUSION` graph fallback. That graph is a row anchor, not
  a timeline and not a proof of timestep-by-timestep state changes.
- This does not affect PyReason evaluation results, bounds, or temporal
  materialization; it only describes the current `row.explain().evidence`
  shape.

Runtime source-back:

- `_build_passed_row_evidence_graph(...)` creates the fallback single-node
  graph when neither a provenance envelope nor a support artifact exists at
  `src/factgraph/application/protocol/evaluate_result.py:857-884`.
- `_validate_row_provenance_envelopes(...)` accepts only ProbLog proof traces at
  `src/factgraph/application/protocol/evaluate_result.py:1221-1240`.
- `_FORM1_ROW_SUPPORT_KINDS` is native + Souffle at
  `src/factgraph/application/protocol/evaluate_result.py:81-82`.
- Store support partitioning keeps PyReason in provenance-bearing support kinds
  but not witness-bearing Form 1 support kinds at
  `src/factgraph/core/store/_support.py:13-20`.

### 3.4 Advanced Escape Hatch

`pyreason_trace_to_evidence_graph(...)` is advanced importable directly from
the adapter:

```python
from factgraph.adapters.pyreason.provenance import pyreason_trace_to_evidence_graph
```

Source-backed signature at `src/factgraph/adapters/pyreason/provenance.py:113-119`:

```python
pyreason_trace_to_evidence_graph(
    trace: PyReasonTraceV0,
    *,
    candidate_id: str,
    candidate_payload: Mapping[str, Any],
    support_kind: str = "pyreason_provenance_v1",
) -> EvidenceGraph
```

`candidate_payload` must include `pred_id`, `terms`, and at least one
`entity_ref` term, per `src/factgraph/adapters/pyreason/provenance.py:339-359`.

Step 4.6 decision: mention the helper as an advanced adapter-level importable,
not the main quickstart path. Do not provide a full code sample in the
quickstart; one sentence is enough.

### 3.5 Form 2 / D11 Reference Strategy

Use neutral user-facing wording: "future Form 2 design cycle". Do not mention
D11 in user docs.

Internal source-back:

- `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md:2070`
  says Form 2 PyReason temporal topology is sketch-only.
- `:2095` says detailed Form 2 schema, including timestep / time-window /
  bound-update semantics, is fully deferred.
- `:2270` lists the Form 2 PyReason temporal full schema as deferred.
- `:2858` records the D11 boundary: v1 implementation slices stay Form 1 /
  default tree only and require timestamp/component semantics before timeline
  producers emit.

### 3.6 Cross-Doc Promise Sweep

Sweep result:

- Quickstart docs do not promise PyReason row-level timeline evidence. The only
  quickstart mention is future-track wording in `evidence.md:297-325`.
- SDK guide does not promise PyReason row-level timeline evidence. It lists
  PyReason row-level graphs as future tracks and points to the evidence
  quickstart at `src/factgraph/sdk/docs/00_user_guide.en.md:678-681`.
- Adapter docs contain detailed PyReason provenance/timeline material, including
  `pyreason_trace_to_evidence_graph(...)` in
  `src/factgraph/adapters/docs/03_pyreason_adapter.md`. That is adapter-module
  documentation and remains out of this user quickstart cycle.
- Audit docs mention PyReason evidence graph / timeline consumption, especially
  `src/factgraph/audit/docs/02_evidence_graph.md`; audit module docs remain out
  of scope.

No stop/amend trigger fires. The user-facing quickstart contract can be fixed
within `evidence.md` only.

### 3.7 Leave-Alone Table

| File / area | Decision |
|---|---|
| `src/factgraph/sdk/docs/00_user_guide.en.md` | Leave alone; existing pointer to evidence quickstart is sufficient after primary doc update. |
| `docs/official/kernel/quickstart/semantics.md` | Leave alone; T8-D round 4 canonical semantics docs are complete. |
| `docs/official/kernel/quickstart/assertions.md` | Leave alone; T8-D round 4 ProbLog raw-uncertainty note is complete. |
| `docs/official/kernel/quickstart/rules-and-inferences.md` | Leave alone; T8-D round 4 cleanup is complete. |
| Adapter docs | Leave alone; named future adapter-docs alignment work. |
| Audit docs | Leave alone; module docs, not quickstart contract. |
| Runtime / tests | Leave alone for implementation; run tests only as no-op verification. |
| Untracked design-point files | Leave alone; design-point intake remains out of scope. |
| Other quickstart pages | Leave alone. |

## 4. Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | What are the exact `evidence.md` line refs for PyReason mentions or absence, and which existing sections are byte-stable protected? | Answered: `:294-298` is the insertion point; preserve `:260-292`, `:300-326`, and `:328-359`. |
| Q2 | Does `00_user_guide.en.md` need a short PyReason evidence note after T8-D round 4? | Answered: no; `:678-681` already lists PyReason row-level graphs as future evidence tracks and points to the evidence quickstart. |
| Q3 | What exact user-facing wording explains the single-conclusion fallback? | Answered: safe single-`NODE_CONCLUSION` row anchor, not a timeline; rich temporal evidence deferred. |
| Q4 | What is the exact `pyreason_trace_to_evidence_graph(...)` import path/signature, and how should it be framed? | Answered: import from `factgraph.adapters.pyreason.provenance`; signature source-backed at `provenance.py:113-119`; frame as advanced adapter-level helper. |
| Q5 | Should user docs mention D11, or use neutral "future Form 2 design cycle" wording? | Answered: use neutral Form 2 wording; keep D11 only in blueprint/audit. |
| Q6 | Is `pyreason_trace_to_evidence_graph(...)` advanced importable without SDK re-export? | Answered: yes; direct import with `PYTHONPATH=src` succeeded and signature matched source. No SDK re-export needed. |
| Q7 | Do other docs implicitly promise PyReason row-evidence timeline support? | Answered: no quickstart/SDK promise. Adapter/audit docs discuss lower-level timeline surfaces and remain out of scope. |
| Q8 | What implementation split is appropriate: one docs commit or two? | Answered: one implementation commit, `evidence.md` only. |
| Q9 | Do any stop/amend triggers fire? | Answered: no. |

## 5. Existing Invariants To Preserve

- T8-A 14-key metadata and `run_id` envelope-only behavior.
- T8-B-1 native Form 1 and T8-B-2 Souffle Form 1.
- T8-C-1 ProbLog row-provenance graphs and `engine_meta["problog"]`.
- T8-D round 1 native Form 1 user docs.
- T8-D round 2 Souffle Form 1 user docs.
- T8-D round 3 ProbLog row-provenance user docs in `evidence.md`.
- T8-D round 4 canonical semantics user docs in `semantics.md`,
  `assertions.md`, `rules-and-inferences.md`, and SDK guide.
- T10-1 / T10-2-A / T10-2-B / T10-3-A / T10-3-B runtime behavior.
- `_validate_row_provenance_envelopes` protocol-gate behavior.
- `_FORM1_ROW_SUPPORT_KINDS`, `_WITNESS_BEARING_SUPPORT_KINDS`, and
  `_PROVENANCE_BEARING_SUPPORT_KINDS`.
- Single-conclusion fallback behavior in row evidence.
- `pyreason_trace_to_evidence_graph(...)` signature and import path.
- D11 / Form 2 schema remains fully deferred.
- `Inference`, `Query`, `Branch`, and `Pred` DSL runtime classes remain
  implemented.
- C110 / C119 / C136 / D11 / D13 / Nemo / Form 2 deferred state.
- Archive lockout set named in §0 remains locked.
- Sacred `master = 562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline `4 M + 1 D + 6 U`.

## 6. Inventory Plan

```bash
rg -n "PyReason|pyreason|row\\.evidence|timeline|Form 2|Inference|Branch|ProbLog" docs/official/kernel/quickstart/evidence.md
rg -n "PyReason|pyreason|evidence|row\\.evidence|timeline|pyreason_trace_to_evidence_graph" src/factgraph/sdk/docs/00_user_guide.en.md docs/official/kernel/quickstart src/factgraph/adapters/docs src/factgraph/audit/docs
rg -n "_validate_row_provenance_envelopes|_build_passed_row_evidence_graph|_FORM1_ROW_SUPPORT_KINDS|_WITNESS_BEARING_SUPPORT_KINDS|_PROVENANCE_BEARING_SUPPORT_KINDS" src/factgraph/application/protocol src/factgraph/core/store
rg -n "def pyreason_trace_to_evidence_graph|candidate_id|candidate_payload" src/factgraph/adapters/pyreason/provenance.py
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph
PYTHONPATH=src python -m unittest discover tests
git diff --check
git status --short --branch
git rev-parse master
```

## 7. Implementation Split

Candidate chain:

1. `docs(quickstart): clarify PyReason evidence deferred state`
   - Edit `docs/official/kernel/quickstart/evidence.md`.
2. `docs(blueprint): close T8-D round 5 PyReason evidence docs`
3. `docs(blueprint): archive T8-D round 5 PyReason evidence docs`

Step 4.6 selects one implementation file only: `evidence.md`. The SDK guide
already points to the evidence quickstart for these boundaries.

## 8. Acceptance Checklist

- [x] Step 4.2 review completed.
- [x] Step 4.6 source-backed inventory completed.
- [x] Q1-Q9 answered.
- [x] `evidence.md` PyReason deferred-state section shipped.
- [x] Optional SDK guide decision implemented or explicitly declined.
- [x] Current PyReason `row.evidence` single-conclusion fallback documented
      without implying a bug or timeline support.
- [x] Future Form 2 design cycle deferred state documented without schema
      details.
- [x] `pyreason_trace_to_evidence_graph(...)` advanced escape hatch documented
      only if source-backed and framed as non-main-path.
- [x] T8-D round 3 ProbLog row-provenance docs preserved.
- [x] T8-D round 1 `Inference` / `Branch` stability wording preserved.
- [x] T8-D round 4 canonical semantics docs preserved.
- [x] No runtime, tests, governance, adapter docs, audit docs, or dirty-baseline
      files touched.
- [x] File scope stayed at two files or fewer for implementation.
- [x] Focused docs-only baseline passes.
- [x] Full discover compared against `2038 tests / 72 failures / 231 errors`.
- [x] `git diff --check` clean.
- [x] Sacred master and dirty baseline preserved.

## 9. Verification Commands

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph
PYTHONPATH=src python -m unittest discover tests
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Implemented in `61f8b99d docs(quickstart): clarify PyReason evidence deferred state`.

Outcome:

- Added one narrow PyReason paragraph to `docs/official/kernel/quickstart/evidence.md`
  after the existing single-conclusion fallback paragraph.
- Documented that PyReason inference, bounds, and temporal materialization are
  available through the PyReason evaluation path, while rich row-level temporal
  evidence remains deferred to a future Form 2 design cycle.
- Documented the current safe single-`NODE_CONCLUSION` fallback as a row anchor,
  not a timeline and not proof of timestep-by-timestep state changes.
- Mentioned `factgraph.adapters.pyreason.provenance.pyreason_trace_to_evidence_graph(...)`
  as an advanced adapter-level helper, not the main quickstart path, and noted it
  may evolve with future Form 2 design.

Verification:

- Focused docs-only baseline: `Ran 140 tests ... OK`.
- Full discover: `Ran 2038 tests ... FAILED (failures=72, errors=231)`,
  matching the established baseline exactly.
- `git diff --check` clean.
- Sacred `master` remained `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remained `4 M + 1 D + 6 U`.

Deviations / notes:

- The optional SDK guide edit was explicitly declined at Step 4.6 because
  `src/factgraph/sdk/docs/00_user_guide.en.md:678-681` already points PyReason
  row-level evidence readers to the evidence quickstart as a future evidence
  track.
- Implementation file scope was stricter than the two-file cap: only
  `docs/official/kernel/quickstart/evidence.md` changed.
- No Form 2 schema details were introduced; D11 / Form 2 design remains a
  separate future design cycle.
