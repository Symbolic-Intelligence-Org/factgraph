# Audit: T8-D Round 5 PyReason Evidence Deferred-State Docs

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/archive/2026-05-28_t8-d-round5-pyreason-evidence-deferred-state-docs.md`
- Stage: implemented
- Class: S (docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | pre-draft | n/a | Dirty-baseline composition observed | User moved `identity-and-data-model-redesign.zh.md` from untracked `workflow/design/design-points/active/` to untracked `workflow/design/design-points/archive/`; numerical dirty baseline remains `4 M + 1 D + 6 U`, and design-point intake remains out of scope. |
| 2026-05-28 | draft | this commit | T8-D round 5 PyReason evidence deferred-state docs blueprint pair drafted | Triggered by T8-D round 4 `06e575dd`, clean PyReason row-evidence boundary source-back, and user direction to document deferred state before D11/Form 2 design. |
| 2026-05-28 | scoped | this commit | Step 4.6 source-backed inventory completed | Implementation narrowed to one docs file: `docs/official/kernel/quickstart/evidence.md`; focused baseline `140 OK`; full discover matched `2038 / 72F / 231E` with `PYTHONPATH=src`. |
| 2026-05-28 | implemented | `61f8b99d` | Step 4.7 implementation accepted | Added a narrow PyReason deferred-state paragraph to `evidence.md`; focused baseline `140 OK`; full discover matched `2038 / 72F / 231E`; sacred and dirty baseline preserved. |

## 2. Draft Source Scan

Read-only orientation findings from the user telegraph and recent session
source-back:

- PyReason row-level evidence is currently safe but not rich temporal evidence.
  It falls back to a single-conclusion `EvidenceGraph` at the row-result
  surface.
- `_validate_row_provenance_envelopes` gates `_row_provenance_envelopes` to
  ProbLog proof traces, so PyReason envelopes should not silently route into
  ProbLog row provenance.
- Form 1 witness support kinds do not include PyReason, so PyReason does not
  enter native/Souffle Form 1 witness rendering.
- `pyreason_trace_to_evidence_graph(...)` exists in the PyReason adapter as an
  advanced helper for trace-to-timeline graph construction.
- D11 / Form 2 schema is explicitly deferred; this docs cycle must not define
  timeline row-evidence schema semantics.
- T8-D round 4 already aligned canonical semantics docs. This cycle should not
  reopen semantics/assertions/rules cleanup.

This draft scan is not a Step 4.6 answer. Step 4.6 must independently verify
line refs, signatures, and target insertion points.

## 2A. Step 4.6 Scoped Findings

- `evidence.md` target: insert a narrow PyReason deferred-state paragraph after
  the single-conclusion fallback paragraph at `docs/official/kernel/quickstart/evidence.md:294-298`.
- Preserve byte-stable sections:
  - Native / Souffle Form 1 row graph wording at `evidence.md:260-281`.
  - T8-D round 3 ProbLog row-provenance wording at `evidence.md:283-292`.
  - Stable graph invariants and current-boundaries list at `evidence.md:300-326`.
  - T8-D round 1 `Inference` / `Branch` stability wording at `evidence.md:328-359`.
- SDK guide decision: no edit. `src/factgraph/sdk/docs/00_user_guide.en.md:678-681`
  already marks PyReason row-level graphs as future evidence tracks and points
  to the evidence quickstart.
- Runtime source-back:
  - Single-conclusion fallback:
    `src/factgraph/application/protocol/evaluate_result.py:857-884`.
  - ProbLog-only row provenance gate:
    `src/factgraph/application/protocol/evaluate_result.py:1221-1240`.
  - Native/Souffle Form 1 row support kinds:
    `src/factgraph/application/protocol/evaluate_result.py:81-82`.
  - PyReason is provenance-bearing but not witness-bearing Form 1:
    `src/factgraph/core/store/_support.py:13-20`.
- Advanced helper source-back:
  `src/factgraph/adapters/pyreason/provenance.py:113-119` has
  `pyreason_trace_to_evidence_graph(trace, *, candidate_id, candidate_payload,
  support_kind="pyreason_provenance_v1")`; `:339-359` validates
  `candidate_payload.pred_id`, `terms`, and at least one entity ref term.
- Form 2 deferred source-back:
  `workflow/design/design-points/active/evidence-tree-rainbird-style-v1.zh.md:2070`,
  `:2095`, `:2270`, and `:2858`.
- Cross-doc promise sweep: no quickstart or SDK promise of PyReason row-level
  timeline evidence. Adapter/audit docs discuss lower-level timeline surfaces
  and remain out of scope.
- Verification:
  - Focused command: `Ran 140 tests in 0.348s — OK`.
  - Bare `python -m unittest discover tests` fails in this environment because
    `factgraph` is not importable without `PYTHONPATH=src`; scoped plan updates
    discovery to `PYTHONPATH=src python -m unittest discover tests`.
  - Corrected full discover: `Ran 2038 tests in 3.310s — FAILED (failures=72,
    errors=231)`, matching the established baseline exactly.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What are exact `evidence.md` line refs and byte-stable preserve ranges? | Answered: target `:294-298`; preserve `:260-292`, `:300-326`, `:328-359`. |
| Q2 | Does `00_user_guide.en.md` need an additional note? | Answered: no; `:678-681` already points to the evidence quickstart and calls PyReason row graphs future evidence tracks. |
| Q3 | What is the exact single-conclusion fallback wording? | Answered: safe single-`NODE_CONCLUSION` row anchor, not a timeline; rich temporal evidence deferred. |
| Q4 | What is the exact advanced helper signature and import path? | Answered: `factgraph.adapters.pyreason.provenance.pyreason_trace_to_evidence_graph(trace, *, candidate_id, candidate_payload, support_kind=...)`. |
| Q5 | Should docs mention D11 or use neutral Form 2 wording? | Answered: neutral "future Form 2 design cycle" wording. |
| Q6 | Is `pyreason_trace_to_evidence_graph(...)` importable without SDK re-export? | Answered: yes, direct adapter import with `PYTHONPATH=src`; no SDK re-export. |
| Q7 | Are there other PyReason timeline promises across docs? | Answered: no quickstart/SDK promise; adapter/audit docs remain out of scope. |
| Q8 | Should implementation use one docs commit or two? | Answered: one docs commit, `evidence.md` only. |
| Q9 | Do any stop/amend triggers fire? | Answered: no. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| T8-D round 3 ProbLog row-provenance docs regress | A shipped evidence user-doc surface becomes less accurate | Identify and preserve the ProbLog section; insert PyReason note additively. |
| T8-D round 1 stability wording regresses | Existing `Inference` / `Branch` compatibility contract weakens | Identify and preserve the stability section byte-stably unless Step 4.6 stops. |
| Form 2 schema details leak into docs | User docs prematurely commit timestep/window/update semantics | Use neutral "future Form 2 design cycle" wording; no schema details. |
| Advanced helper is framed as main quickstart path | Users depend on adapter internals as public row-evidence contract | Mark helper as advanced, adapter-level, and subject to future Form 2 alignment. |
| Helper signature/import path is documented incorrectly | Users copy a broken example | Source-back signature and import path before implementation. |
| PyReason row fallback is described as a bug | User trust is reduced and contract becomes unclear | Use "safe single-conclusion fallback" wording, not "missing/broken timeline". |
| Runtime protocol gate is over-explained | User docs become internal protocol docs | Teach only the user-visible row-evidence behavior; keep protocol details in blueprint. |
| Evidence quickstart reopening expands scope | Docs-only S cycle turns into broad evidence rewrite | Two-file cap; primary edit is a narrow PyReason deferred-state section. |
| T10 inference semantics are conflated with evidence | Users think PyReason inference is incomplete | State that T10 PyReason inference semantics are shipped; only rich row evidence is deferred. |
| Dirty baseline or design-point files are absorbed | Workflow violation | Preserve status baseline and keep design-point intake out of scope. |
| Runtime/tests/governance touched | Workflow violation for docs-only cycle | Status and diff-scope checks before closure. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q9 answered.
- [x] `evidence.md` preserve ranges reviewed.
- [x] Optional SDK guide decision reviewed.
- [x] Advanced helper signature/import path reviewed.
- [x] Form 2 deferred wording reviewed.
- [x] Cross-doc PyReason promise sweep reviewed.
- [x] Focused docs-only verification baseline reviewed.
- [x] Closure notes filled.

## 6. Closure Notes

Implementation:

- `61f8b99d docs(quickstart): clarify PyReason evidence deferred state`
  updated only `docs/official/kernel/quickstart/evidence.md`.
- The inserted paragraph lives after the existing single-conclusion fallback
  wording and leaves the native/Souffle Form 1, ProbLog row-provenance, stable
  graph invariants, current-boundaries, and `Inference` / `Branch` stability
  sections byte-stable.
- The paragraph teaches that PyReason inference, bounds, and temporal
  materialization are shipped, while rich PyReason row-level temporal evidence is
  deferred to a future Form 2 design cycle.
- The paragraph describes current PyReason row evidence as a safe
  single-`NODE_CONCLUSION` row anchor, not a timeline and not proof of
  timestep-by-timestep state changes.
- The paragraph mentions
  `factgraph.adapters.pyreason.provenance.pyreason_trace_to_evidence_graph(...)`
  as an advanced adapter-level helper and explicitly keeps it out of the main
  quickstart path.

Verification:

- `git diff --check` clean.
- Focused docs-only baseline: `Ran 140 tests ... OK`.
- Full discover: `Ran 2038 tests ... FAILED (failures=72, errors=231)`,
  matching the established baseline exactly.
- Sacred `master` remained `562c74195df43e933bed92a3ff25de94dd8ce666`.
- Dirty baseline remained `4 M + 1 D + 6 U`, including untracked design-point
  files.

Scope notes:

- The optional SDK guide edit was declined because the SDK guide already points
  PyReason row-level graph readers to the evidence quickstart as future evidence
  work.
- No runtime, tests, governance, adapter docs, audit docs, or dirty-baseline
  files were changed.
- No Form 2 schema details were introduced; D11 / Form 2 design remains future
  work.
