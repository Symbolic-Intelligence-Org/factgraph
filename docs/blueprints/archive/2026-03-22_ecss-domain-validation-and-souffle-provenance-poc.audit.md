# Task Blueprint Audit: ECSS Domain Validation And Souffle Provenance PoC

- Blueprint: [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](./2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-22 | draft | Mother blueprint created | Recast the 2026-03-22 architectural pivot into an active mother blueprint instead of keeping it as a root-level design memo. |
| 2026-03-22 | scoped | Stage boundary frozen | Locked the current stage to two validation tracks: ECSS domain fit and Souffle provenance feasibility. |
| 2026-03-22 | implementing | First provenance child blueprint activated | `2026-03-22_souffle-provenance-adapter-v0.md` entered implementation as the first concrete adapter-local provenance slice under this mother blueprint. |
| 2026-03-22 | implementing | First provenance child blueprint completed | `2026-03-22_souffle-provenance-adapter-v0.md` delivered adapter-local proof parsing and `-t explain` execution without changing `run_package` or promoting any proof carrier into `core/`. |
| 2026-03-22 | implementing | Package-level provenance caller added | Added `run_package_provenance(...)` as an adapter-local convenience wrapper so ECSS demos can call provenance on exported packages without introducing any new service endpoint or changing `run_package`. |
| 2026-03-22 | implementing | Subproof truncation handling added | Real ECSS provenance output exposed Souffle depth-limited `subproof ...` leaves. Parser now preserves them as adapter-local `node_type="subproof"` leaves instead of failing on truncated proof trees. |
| 2026-03-22 | implementing | Real ECSS provenance validated | Souffle `-t explain` on ESSB-ST-U-007 disposal check rule produces full proof tree via query-bearing `export_runtime_package(query=...)` + `run_package_provenance(...)`. Confirmed: assertion-level source identity (`claim_arg` with assertion ID), chosen assertion selection logic (`chosen_asrt` chain), negation leaves (`NOT better_asrt`), comparison leaves (`920000 >= 900000`), subproof truncation markers (`cand__`, `max_ts__`). Provenance significantly richer than current evidence tree: shows internal Souffle view resolution, assertion competition, and comparison evaluation — none of which the current evidence tree captures. |
| 2026-03-23 | implementing | Notebook validation stays under mother blueprint | Phase 1 remains notebook-scoped domain validation rather than a new implementation slice. Expanded the ECSS demo directly under the mother blueprint to cover composed top-level compliance, explicit non-compliance derivation, and profile-dependent rule branching. |
| 2026-03-23 | implementing | Composed-rule validation closed with explicit Souffle boundary | The ECSS notebook now validates three new slices on real data: (1) top-level compliance via `ruleref` conjunction, (2) explicit non-compliance derivation for a constellation mission, and (3) profile branching (`single` vs `constellation`). Native evaluation succeeds for both top-level outputs. Souffle provenance remains available for flat positive/negative rules but the current query export path still rejects composed `ruleref` queries with `unsupported atom kind: ruleref`; this is now a documented Phase 1 boundary rather than an assumed capability. |
| 2026-03-23 | implementing | Composed-rule provenance boundary closed | Child blueprint `2026-03-23_ruleref-souffle-query-export.md` added registry-backed query export for `ruleref`. Real ECSS `q.essb_u007_overall_compliance` now exports successfully and produces a Souffle proof tree via `run_package_provenance(...)`, closing the last Phase 1 blocker for composed-rule provenance. |
| 2026-03-23 | implementing | Provenance consumer surface child completed | Child blueprint `2026-03-23_provenance-audit-consumer-surface.md` delivered `audit/provenance_trees.jsonl` materialization, reader/query loading, static HTML `Engine Provenance` rendering, and regression coverage. Souffle proof trees now flow through the formal audit package → reader/query → static site pipeline instead of remaining adapter-local demo artifacts. |
| 2026-03-26 | implementing | Provenance coverage and bridge child completed | Child blueprint `2026-03-23_provenance-coverage-and-bridge.md` added `provenance_statuses.jsonl`, candidate-page availability/truncation UX, package-level provenance coverage summary, and landing-page coverage metrics. Souffle provenance is now not only visible, but auditable for presence, absence, and truncation across the whole package. |

## Decision Notes

- 2026-03-22
  - This blueprint is a stage mother blueprint, not a direct implementation slice.
  - Child blueprints remain mandatory for any concrete capability line.
  - Certainty v1, probability lane, and delivery-pipeline polish stay out of scope until domain validation closes the key decision gates.
  - Engine-native provenance necessity is now empirically confirmed on real ECSS data; future explain work should prefer engine provenance consumption over external reconstruction.

| 2026-03-23 | implemented | Mother blueprint closed | All 3 decision gates closed (ECSS fit ✅, evidence sufficiency ✅, provenance necessity ✅). 4 child blueprints delivered and archived. 250 tests green. Retained in `active/` as reference for mid-term directions (ProofNode, three-layer rules) in §5.7. |
