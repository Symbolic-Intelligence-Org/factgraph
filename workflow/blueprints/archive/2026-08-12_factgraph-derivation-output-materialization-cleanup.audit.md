# Task Blueprint Audit: FactGraph derivation-output/materialization cleanup

- Status: archived
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: paired blueprint audit log
- Inputs:
  - [`2026-08-12_factgraph-derivation-output-materialization-cleanup.md`](./2026-08-12_factgraph-derivation-output-materialization-cleanup.md)
- Outputs / Downstream:
  - (none)
- Related:
  - [`2026-08-12_q5c-derivation-output-materialization-boundary-decision.md`](../../design/decisions/active/2026-08-12_q5c-derivation-output-materialization-boundary-decision.md)
- Blueprint: [`2026-08-12_factgraph-derivation-output-materialization-cleanup.md`](./2026-08-12_factgraph-derivation-output-materialization-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | draft | Three bounded read-only audits completed | Candidate inventory, public/accept surface and minimal migration design converged. |
| 2026-08-12 | scoped | User authorized the next isolated step | Lightweight path skips a separate preflight because three independent audits already cover the deletion, type migration and cross-layer risks. |
| 2026-08-12 | scoped | Cross-repository dependency narrowed Batch A | Meander `main@4ddb8e36` has four live `evaluate_candidates` consumers; deletion is deferred to a cross-repository migration. |
| 2026-08-12 | implementing | Scoped contract entered implementation | User's instruction to continue covers the two bounded batches; no additional product surface is authorized. |
| 2026-08-12 | implementing | Batch A removed dead service codecs | Five primary codecs and their four-helper-only parser chain were deleted; the HTTP tombstone and active materialization paths remain. |
| 2026-08-12 | implementing | Batch B introduced canonical `DerivationOutput` vocabulary | The class remains in the historical module with a direct `CandidateSet` alias; active read-only producers/consumers migrated while persisted identifiers and wire keys stayed unchanged. |
| 2026-08-12 | corrected | Meander regression refined the single-item write seam | Cross-repository tests proved compiler derivation identity and authored/business attribution are legitimately distinct. A private Store-owned accept-time enrichment helper preserves both; direct `Store.accept` remains strict. |
| 2026-08-12 | verified | Cumulative local and cross-repository cohorts passed | FactGraph: 645 tests + 96 subtests; Meander: 27 focused compatibility tests; Ruff and diff checks clear. Mypy reports the same 107 pre-existing errors as the F3B base comparison. |
| 2026-08-12 | review | Bounded independent review returned CLEAR | Review repeated 153 tests + 7 subtests, six Meander surface tests, Ruff and diff checks; P0/P1=0. One non-blocking note narrowed serialization claims to durable v2 wire/ledger compatibility and one-way old-pickle readability. User-side review remains pending. |
| 2026-08-12 | review | User-side independent review returned CLEAR | Full suite: 2,968 passed / 1 failed / 32 skipped; 30/30 valid adversarial probes; Ruff and diff checks clear; P0/P1=0. The sole P2 is the pre-existing `render_evidence_graph_html` service import failure, reproduced at base `4024526c` and outside F3C. |
| 2026-08-12 | implemented | F3C acceptance criteria closed | Canonical output terminology, byte-stable v2 compatibility, Meander seam, dual-identity attribution, batch guards and F4 boundary all passed independent review. |
| 2026-08-12 | archived | Blueprint pair archived | Current implementation truth remains in the updated core/application/adapter/SDK docs; no Meander migration or unrelated base fix was started. |

## Decision Notes

- Batch A removes five zero-call primary service codecs and their four-helper-only
  parser chain. The HTTP tombstone and all Agent/core materialization paths remain.
- Batch B changes canonical Python terminology, not persisted candidate protocol.
- `evaluate_candidates` is temporary compatibility debt, not a newly endorsed
  public design. Current public API coherence and D23 completion are not claimed.
- Batch B repairs Store-digest bypass and dropped batch intent without creating
  or renaming a public materialization surface. Digest enrichment records
  accept-time Store context and does not claim an evaluation-time snapshot.
- The application attribution helper consumes a rule identity supplied by an
  already-authorized resolver; it performs no authorization decision itself.
- F4 is barred from using output/candidate identity as a durable anchor.
