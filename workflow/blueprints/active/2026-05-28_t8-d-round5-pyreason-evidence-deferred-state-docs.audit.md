# Audit: T8-D Round 5 PyReason Evidence Deferred-State Docs

- Status: draft
- Created: 2026-05-28
- Last Updated: 2026-05-28
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-28_t8-d-round5-pyreason-evidence-deferred-state-docs.md`
- Stage: draft
- Class: S (docs-only)
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current observed `4 M + 1 D + 6 U`
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-28 | pre-draft | n/a | Dirty-baseline composition observed | User moved `identity-and-data-model-redesign.zh.md` from untracked `workflow/design/design-points/active/` to untracked `workflow/design/design-points/archive/`; numerical dirty baseline remains `4 M + 1 D + 6 U`, and design-point intake remains out of scope. |
| 2026-05-28 | draft | this commit | T8-D round 5 PyReason evidence deferred-state docs blueprint pair drafted | Triggered by T8-D round 4 `06e575dd`, clean PyReason row-evidence boundary source-back, and user direction to document deferred state before D11/Form 2 design. |

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

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | What are exact `evidence.md` line refs and byte-stable preserve ranges? | Pending Step 4.6. |
| Q2 | Does `00_user_guide.en.md` need an additional note? | Pending Step 4.6. |
| Q3 | What is the exact single-conclusion fallback wording? | Pending Step 4.6. |
| Q4 | What is the exact advanced helper signature and import path? | Pending Step 4.6. |
| Q5 | Should docs mention D11 or use neutral Form 2 wording? | Pending Step 4.6. |
| Q6 | Is `pyreason_trace_to_evidence_graph(...)` importable without SDK re-export? | Pending Step 4.6. |
| Q7 | Are there other PyReason timeline promises across docs? | Pending Step 4.6. |
| Q8 | Should implementation use one docs commit or two? | Pending Step 4.6. |
| Q9 | Do any stop/amend triggers fire? | Pending Step 4.6. |

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

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q9 answered.
- [ ] `evidence.md` preserve ranges reviewed.
- [ ] Optional SDK guide decision reviewed.
- [ ] Advanced helper signature/import path reviewed.
- [ ] Form 2 deferred wording reviewed.
- [ ] Cross-doc PyReason promise sweep reviewed.
- [ ] Focused docs-only verification baseline reviewed.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending implementation.
