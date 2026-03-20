# Task Blueprint Audit: Candidate Evidence Tree Provenance / Source Taxonomy

- Blueprint: [2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md](./2026-03-19_candidate-evidence-tree-provenance-source-taxonomy.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Opened a narrow post-recursive-proof capability line to decide whether `candidate_evidence_tree` needs a formal provenance/source taxonomy beyond the current implicit combination of `node_kind`, `support_kind`, and `witness_status`. |
| 2026-03-20 | scoped | Freeze decisions made | Inventoried all 12 node kinds, concluded zero new fields needed; `node_kind` promoted to formal provenance-role carrier. Assertion-origin taxonomy explicitly deferred. |
| 2026-03-20 | implemented | Doc promotion complete | `node_kind → provenance role category` mapping written to core/docs/01_architecture.md, service/docs/03_runtime_queries_views.md, audit/docs/01_overview.md. All 6 acceptance criteria checked. |

## Decision Notes

- 2026-03-19: This slice is intentionally narrower than engine witness parity and narrower than finer snippet/span provenance.
- 2026-03-19: `rainbird-evidence-chain-compare.md` is used only as an external design reference for source taxonomy, not as current implementation truth.
- 2026-03-19: The line must not reopen already-frozen recursive proof, winning-branch, or unresolved taxonomy contracts.
- 2026-03-20: Scope narrowed from "source taxonomy" to "provenance-role taxonomy". The distinction: provenance role = structural proof role (what `node_kind` already encodes); assertion-origin = deeper lifecycle provenance (direct write / derivation accept / import), which requires `assertion_lookup` callback extension and is out of scope.
- 2026-03-20: Rainbird reference adoption boundary — adopted the principle that tree nodes should carry explicit source categorization; did NOT adopt Rainbird's 6-type source enum as our vocabulary (our `node_kind` taxonomy maps differently). Did NOT adopt Rainbird's certainty-weighted salience model (deferred to separate capability line).
- 2026-03-20: The only `node_kind` ambiguity identified is `rule_ref` (shared between legacy flat and structured edge). Resolved by documenting that consumers distinguish via `ruleref_atom_key` field presence, rather than splitting the node_kind or adding `source_kind`.
