# Audit: T8-D Round 3 ProbLog User Docs

- Status: implemented
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/archive/2026-05-28_t8-d-round3-problog-user-docs.md`
- Stage: implemented
- Class: S (docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 5 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | `e13686db` | T8-D round 3 ProbLog user-docs blueprint pair drafted | Triggered by T8-C-1 runtime `5ffd4850`; Q1-Q9 pending for Step 4.6. |
| 2026-05-28 | scoped | `38ae43a9` | Source-backed inventory and Q1-Q9 completed | File scope locked to `evidence.md` + SDK `00_user_guide.en.md`; planned user wording treats ProbLog as shipped row provenance evidence, not Form 1. |
| 2026-05-28 | implementation | `902f1b76` | Quickstart docs aligned | `evidence.md` now teaches ProbLog row provenance graphs as shipped and removes ProbLog from future row evidence boundaries. |
| 2026-05-28 | implementation | `6098b9a8` | SDK guide aligned | SDK guide now summarizes ProbLog row provenance graphs while keeping PyReason and other evidence tracks future. |
| 2026-05-28 | closure | pending | Closure recorded | Verification 67 OK, `git diff --check` clean, dirty baseline preserved. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8-C-1 runtime shipped ProbLog row-result provenance graphs, not Form 1.
- T8-C-1 audit docs already distinguish native/Souffle `supports` Form 1 from
  ProbLog `derives` provenance-row graphs.
- The evidence quickstart still appears to group ProbLog with future row-level
  Form 1 alignment and reserved `EDGE_DERIVES`.
- The SDK user guide still appears to group ProbLog/PyReason Form 1 graphs as
  future evidence tracks without mentioning shipped ProbLog provenance rows.
- Audit module docs should be reference-only for this round because `a916a856`
  already aligned them.

This draft scan is not a Step 4.6 answer. Step 4.6 must verify line refs,
two-file scope, and audit-doc wording consistency before implementation.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Is the file scope exactly two user docs? | Answered: yes, `evidence.md` and SDK `00_user_guide.en.md`; other ProbLog hits are semantics/annotation/adapter concept or already-aligned audit docs. |
| Q2 | What is the `evidence.md` edit map? | Answered: §6 title, new ProbLog provenance paragraph, fallback paragraph, deferred boundary line, and edge-kind reservation line. |
| Q3 | What is the SDK guide edit map? | Answered: lines 658-665 concise summary only. |
| Q4 | How should the deferred boundary change? | Answered: remove ProbLog from future row evidence while not calling ProbLog Form 1. |
| Q5 | How should the edge-kind reservation line change? | Answered: native/Souffle `supports`, ProbLog `derives`, PyReason `updates` future. |
| Q6 | Should the quickstart add a ProbLog ASCII topology example? | Answered: yes, one short `derives` line distinct from Form 1. |
| Q7 | How much `engine_meta["problog"]` detail should user docs teach? | Answered: one high-level mention of trace summary and uncertainty projection; no schema dump. |
| Q8 | What verification baseline is appropriate? | Answered: focused docs-only suite plus T8-C-1 ProbLog sanity test, `git diff --check`, status, and sacred check. |
| Q9 | Are any stop/amend triggers hit? | Answered: none. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| ProbLog is documented as Form 1 | User docs overstate the shipped topology and edge semantics | Step 4.6 completed: teach provenance-row graph as sibling shape. |
| `EDGE_DERIVES` remains documented as reserved | User docs contradict T8-C-1 shipped row provenance behavior | Step 4.6 completed: edge-kind line will match audit docs. |
| `engine_meta["problog"]` schema is fully dumped | User docs become implementation docs and drift risk increases | Step 4.6 completed: mention only trace summary / uncertainty projection at a high level. |
| SDK guide duplicates quickstart detail | Future user-doc drift | Step 4.6 completed: preserve quickstart-detail / SDK-summary split. |
| Audit docs are edited again | Scope duplicates T8-C-1 completed audit alignment | Step 4.6 completed: audit docs are wording source only. |
| PyReason / aggregate / C119 / failed evidence enters scope | S-cycle grows into evidence design work | Step 4.6 completed: keep non-shipped tracks deferred. |
| Dirty baseline is touched | Workflow violation | Step 4.6 completed: only blueprint/audit files touched so far. |

## 5. Review Checklist

- [x] Step 4.2 review complete.
- [x] Step 4.6 source-backed inventory complete.
- [x] Q1-Q9 answered.
- [x] Two-file scope locked.
- [x] Quickstart / SDK implementation complete.
- [x] Focused docs-only verification complete.
- [x] Closure notes filled.

## 6. Closure Notes

T8-D round 3 completed as a docs-only follow-up to T8-C-1 runtime:

- Implementation touched exactly two user-facing docs files:
  `docs/official/kernel/quickstart/evidence.md` and
  `src/factgraph/sdk/docs/00_user_guide.en.md`.
- Quickstart §6 now teaches native/Souffle Form 1 and ProbLog row provenance as
  sibling shipped row-level graph shapes.
- ProbLog is explicitly not Form 1: it uses a separate `derives` ASCII block
  and `EDGE_DERIVES` wording.
- ProbLog was removed from the future row-evidence boundary; PyReason and other
  non-shipped evidence tracks remain future.
- SDK guide stays concise and delegates details to the quickstart.
- Audit module docs were not edited because `a916a856` already aligned them.
- Verification: five-module focused baseline 67 OK, `git diff --check` clean,
  dirty baseline still `4 M + 1 D + 5 U`, sacred master unchanged.

Notes:

- Future adapter wording uses "row-level alignment" rather than "Form 1
  alignment" where PyReason might ship as Form 2.
- User docs mention `engine_meta["problog"]` only at high level; no schema dump
  was added.
