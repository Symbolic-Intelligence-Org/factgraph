# Audit: T8-B Native/Souffle Form 1 Topology

- Status: draft
- Created: 2026-05-27
- Last Updated: 2026-05-27
- Branch: `v0.2.0-t11-1-attach-view-scope-2026-05-26`
- Blueprint: `workflow/blueprints/active/2026-05-27_t8-b-form1-topology.md`
- Stage: draft
- Class: L unless narrowed during Step 4.6
- Sacred branch: `master` must remain at `562c74195df43e933bed92a3ff25de94dd8ce666`
- Dirty baseline: preserve current four modified tracked docs/notebooks plus two untracked reference directories
- Ownership: Codex owner, Claude reviewer (cross-flip)

## 1. Event Log

| Date | Stage | Commit | Event | Notes |
|---|---|---|---|---|
| 2026-05-27 | draft | this commit | T8-B Form 1 topology blueprint pair drafted | Triggered by T8-A completion; Q1-Q9 intentionally pending for source-backed Step 4.6. |

## 2. Draft Source Scan

Read-only orientation findings:

- T8-A is complete and archived at `40a0ce47`; C135 metadata validation is now
  runtime-enforced and must not be weakened.
- T8 split inventory identifies T8-B as the next evidence implementation lane
  and recommends reuse-before-rewrite for candidate evidence and Souffle
  converter surfaces.
- `EvidenceGraph` already contains the node/edge kind vocabulary required by
  Form 1.
- Candidate evidence tree and Souffle evidence graph code already exist, so
  the core Step 4.6 task is tranche selection and reuse mapping, not proving
  that a substrate exists.

This draft scan is not a Step 4.6 answer. It intentionally avoids choosing
native-only vs Souffle-only vs combined scope before source-backed inventory.

## 3. Open Questions Register

| ID | Question | Status |
|---|---|---|
| Q1 | Should T8-B be native-only, Souffle-only, both, or split into T8-B-1/T8-B-2? | Pending Step 4.6. |
| Q2 | How do candidate evidence helpers map to Form 1 topology? | Pending Step 4.6. |
| Q3 | Does the Souffle converter already conform to Form 1? | Pending Step 4.6. |
| Q4 | What are node/edge population rules for the selected tranche? | Pending Step 4.6. |
| Q5 | What is the seed reuse strategy? | Pending Step 4.6. |
| Q6 | How is winning-path-only OR represented? | Pending Step 4.6. |
| Q7 | Where does C136 aggregate count-only envelope live? | Pending Step 4.6. |
| Q8 | What is the test matrix? | Pending Step 4.6. |
| Q9 | How should `_build_passed_row_evidence_graph(...)` change? | Pending Step 4.6. |

## 4. Draft Risk Register

| Risk | Impact | Step 4.6 check |
|---|---|---|
| Combined native+Souffle scope is too large | Cycle may balloon beyond L | Compare native-only, Souffle-only, both, and split options with file/test/LOC estimates. |
| Reuse-before-rewrite becomes a rewrite | Breaks T8 split intent and raises regression risk | Map every reused helper before implementation. |
| T8-B needs new graph schema | Violates Form 1 / T7 compatibility | Stop if new node/edge kind or DTO field is required. |
| T8-A validation gate is bypassed | Breaks C135 runtime invariant | Explicitly trace `_build_passed_row_evidence_graph(...)` strategy. |
| Aggregate or OR semantics become hidden scope | Semantic drift | Lock OR and C136 boundaries before code. |
| Dirty baseline edited accidentally | Workflow violation | Status checks before commit/closure. |

## 5. Review Checklist

- [ ] Step 4.2 review complete.
- [ ] Step 4.6 source-backed inventory complete.
- [ ] Q1-Q9 answered.
- [ ] Narrowed implementation tranche locked.
- [ ] Reuse-before-rewrite map complete.
- [ ] Tests and verification gates locked.
- [ ] Closure notes filled.

## 6. Closure Notes

Pending inventory / implementation / closure.
