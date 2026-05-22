# Audit Log: Souffle Provenance Adapter V0

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-03-22 | scoped | Blueprint created | Based on Souffle provenance PoC results: disposal flat check + recursive passivation with negation both verified on Souffle 2.5 `-t explain`. JSON output confirmed parseable. 5 anti-debt boundaries defined. |
| 2026-03-22 | scoped | P1 fix: runner contract | Changed from modifying `run_package` return type to standalone `run_provenance_explain()` function. `run_package` signature/return completely unchanged. Prevents wave to engine_eval.py callers. |
| 2026-03-22 | implementing | Implementation started | Scope locked to adapter-local parser/runner helper, tests, standalone example, and adapter docs. No core/service/audit contract changes. |
| 2026-03-22 | implementing | Naming boundary tightened | Adapter-local dataclasses are named `SouffleProofNodeV0` / `SouffleProofTreeV0` to keep the V0 suffix explicit and avoid premature abstraction drift. |
| 2026-03-22 | implemented | Adapter-local provenance helper landed | Added `adapters/souffle/provenance.py`, targeted unit tests, and a standalone passivation demo. Verified that `run_package` stayed unchanged and existing Souffle witness tests still pass. |
