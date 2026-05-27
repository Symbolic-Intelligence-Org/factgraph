# Audit: T8-D Round 3 ProbLog User Docs

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t8-d-round3-problog-user-docs.md`
- Stage: draft
- Class: S (docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 5 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | draft | this commit | T8-D round 3 ProbLog user-docs blueprint pair drafted | Triggered by T8-C-1 runtime `5ffd4850`; Q1-Q9 pending for Step 4.6. |

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
| Q1 | Is the file scope exactly two user docs? | Pending Step 4.6. |
| Q2 | What is the `evidence.md` edit map? | Pending Step 4.6. |
| Q3 | What is the SDK guide edit map? | Pending Step 4.6. |
| Q4 | How should the deferred boundary change? | Pending Step 4.6. |
| Q5 | How should the edge-kind reservation line change? | Pending Step 4.6. |
| Q6 | Should the quickstart add a ProbLog ASCII topology example? | Pending Step 4.6. |
| Q7 | How much `engine_meta["problog"]` detail should user docs teach? | Pending Step 4.6. |
| Q8 | What verification baseline is appropriate? | Pending Step 4.6. |
| Q9 | Are any stop/amend triggers hit? | Pending Step 4.6. |

## 4. Risk Register

| Risk | Impact | Step 4.6 / implementation check |
|---|---|---|
| ProbLog is documented as Form 1 | User docs overstate the shipped topology and edge semantics | Step 4.6 must teach provenance-row graph as sibling shape. |
| `EDGE_DERIVES` remains documented as reserved | User docs contradict T8-C-1 shipped row provenance behavior | Edge-kind line must match audit docs. |
| `engine_meta["problog"]` schema is fully dumped | User docs become implementation docs and drift risk increases | Mention only trace summary / uncertainty projection at a high level. |
| SDK guide duplicates quickstart detail | Future user-doc drift | Preserve quickstart-detail / SDK-summary split. |
| Audit docs are edited again | Scope duplicates T8-C-1 completed audit alignment | Treat audit docs as wording source unless Step 4.6 finds a gap. |
| PyReason / aggregate / C119 / failed evidence enters scope | S-cycle grows into evidence design work | Keep non-shipped tracks deferred. |
| Dirty baseline is touched | Workflow violation | Stage only blueprint/docs target files. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q9 answered.
- [ ] Two-file scope locked.
- [ ] Quickstart / SDK implementation complete.
- [ ] Focused docs-only verification complete.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending Step 4.6 / implementation / closure.
