# Task Blueprint Audit: Candidate Evidence Tree Provenance / Source Taxonomy

- Blueprint: [2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md](./2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Opened a narrow post-recursive-proof capability line to decide whether `candidate_evidence_tree` needs a formal provenance/source taxonomy beyond the current implicit combination of `node_kind`, `support_kind`, and `witness_status`. |

## Decision Notes

- 2026-03-19: This slice is intentionally narrower than engine witness parity and narrower than finer snippet/span provenance.
- 2026-03-19: `rainbird-evidence-chain-compare.md` is used only as an external design reference for source taxonomy, not as current implementation truth.
- 2026-03-19: The line must not reopen already-frozen recursive proof, winning-branch, or unresolved taxonomy contracts.
