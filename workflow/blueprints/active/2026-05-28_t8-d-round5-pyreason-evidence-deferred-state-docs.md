# Task Blueprint: T8-D Round 5 PyReason Evidence Deferred-State Docs

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Class: S (docs-only)
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Owner: Codex
- Reviewer: Claude (cross-flip)
- Related audit: `workflow/blueprints/active/2026-05-28_t8-d-round5-pyreason-evidence-deferred-state-docs.audit.md`
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

## 3. Step 4.6 Source-Backed Inventory Skeleton

### 3.1 `evidence.md` Current PyReason Surface

Step 4.6 must grep `evidence.md` for `PyReason`, `row.evidence`,
`timeline`, `Form 2`, `Inference`, `Branch`, and `ProbLog`. It must answer:

- Whether any PyReason evidence teaching already exists.
- Which T8-D round 3 ProbLog row-provenance lines must remain byte-stable.
- Which T8-D round 1 stability lines must remain byte-stable.
- The smallest insertion point for a PyReason deferred-state note.

### 3.2 SDK User Guide Need

Step 4.6 must grep `src/factgraph/sdk/docs/00_user_guide.en.md` for
`PyReason`, `evidence`, `row.evidence`, `timeline`, and
`pyreason_trace_to_evidence_graph`. It must decide whether this cycle remains
one-file (`evidence.md` only) or uses the optional second file.

### 3.3 User-Facing Fallback Wording

Draft wording should be plain and non-alarming:

- PyReason row evidence currently returns a single-conclusion graph at the
  row-result surface.
- That fallback is intentional and safe; it does not claim temporal explanation
  detail.
- Rich temporal row evidence is deferred to a future Form 2 design cycle.
- T10 PyReason inference semantics are unaffected; this is only the row
  evidence explanation surface.

### 3.4 Advanced Escape Hatch

Step 4.6 must source-back the exact import path and signature for
`pyreason_trace_to_evidence_graph(...)`, including required parameters such as
`candidate_id` and `candidate_payload` if present. Docs should mark it as:

- Advanced.
- Adapter-level.
- Not the main quickstart path.
- Potentially subject to future Form 2 design alignment.

### 3.5 Form 2 / D11 Reference Strategy

Default wording should say "future Form 2 design cycle" rather than expose
internal D11 details. Step 4.6 may cite internal design docs in the blueprint,
but user-facing docs should avoid committing schema details.

### 3.6 Cross-Doc Promise Sweep

Step 4.6 must grep quickstart docs, SDK guide, adapter docs, and audit/module
docs for PyReason evidence or timeline promises. If promises are broader than
this cycle can safely clarify within two files, stop and amend.

### 3.7 Leave-Alone Table

Step 4.6 must list files that remain untouched:

- T8-D round 4 semantics/assertions/rules docs.
- Adapter module docs.
- Audit module docs.
- Runtime and tests.
- Four untracked design-point files.
- Other quickstart pages.

## 4. Open Questions

| ID | Question | Required answer shape |
|---|---|---|
| Q1 | What are the exact `evidence.md` line refs for PyReason mentions or absence, and which existing sections are byte-stable protected? | Line refs plus preserve list. |
| Q2 | Does `00_user_guide.en.md` need a short PyReason evidence note after T8-D round 4? | Yes/no plus line refs. |
| Q3 | What exact user-facing wording explains the single-conclusion fallback? | Wording draft. |
| Q4 | What is the exact `pyreason_trace_to_evidence_graph(...)` import path/signature, and how should it be framed? | Signature ref plus wording draft. |
| Q5 | Should user docs mention D11, or use neutral "future Form 2 design cycle" wording? | Decision. |
| Q6 | Is `pyreason_trace_to_evidence_graph(...)` advanced importable without SDK re-export? | Source-backed yes/no. |
| Q7 | Do other docs implicitly promise PyReason row-evidence timeline support? | Grep report. |
| Q8 | What implementation split is appropriate: one docs commit or two? | Source-backed decision. |
| Q9 | Do any stop/amend triggers fire? | Trigger-by-trigger assessment. |

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
python -m unittest discover tests
git diff --check
git status --short --branch
git rev-parse master
```

## 7. Implementation Split

Candidate chain:

1. `docs(quickstart): clarify PyReason evidence deferred state`
   - Edit `docs/official/kernel/quickstart/evidence.md`.
2. Conditional: `docs(sdk-guide): note PyReason evidence deferred state`
   - Only if Step 4.6 decides the SDK guide needs a note.
3. `docs(blueprint): close T8-D round 5 PyReason evidence docs`
4. `docs(blueprint): archive T8-D round 5 PyReason evidence docs`

If Step 4.6 selects one implementation file only, keep one implementation
commit. If it selects two files, keep two small commits so evidence quickstart
and SDK guide review separately.

## 8. Acceptance Checklist

- [ ] Step 4.2 review completed.
- [ ] Step 4.6 source-backed inventory completed.
- [ ] Q1-Q9 answered.
- [ ] `evidence.md` PyReason deferred-state section shipped.
- [ ] Optional SDK guide decision implemented or explicitly declined.
- [ ] Current PyReason `row.evidence` single-conclusion fallback documented
      without implying a bug or timeline support.
- [ ] Future Form 2 design cycle deferred state documented without schema
      details.
- [ ] `pyreason_trace_to_evidence_graph(...)` advanced escape hatch documented
      only if source-backed and framed as non-main-path.
- [ ] T8-D round 3 ProbLog row-provenance docs preserved.
- [ ] T8-D round 1 `Inference` / `Branch` stability wording preserved.
- [ ] T8-D round 4 canonical semantics docs preserved.
- [ ] No runtime, tests, governance, adapter docs, audit docs, or dirty-baseline
      files touched.
- [ ] File scope stayed at two files or fewer for implementation.
- [ ] Focused docs-only baseline passes.
- [ ] Full discover compared against `2038 tests / 72 failures / 231 errors`.
- [ ] `git diff --check` clean.
- [ ] Sacred master and dirty baseline preserved.

## 9. Verification Commands

```bash
PYTHONPATH=src python -m unittest tests.test_pyreason_engine_eval tests.test_pyreason_rule_ext tests.test_pyreason_evidence_graph tests.test_pyreason_semantics_profile_migration tests.test_problog_semantics_profile_migration tests.test_audit_evidence_graph
python -m unittest discover tests
git diff --check
git status --short --branch
git rev-parse master
```

## 10. Outcome / Deviations

Pending Step 4.6 / implementation / closure.
