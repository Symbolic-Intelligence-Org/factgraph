# Audit Log: Souffle Provenance Adapter V0

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-03-22 | scoped | Blueprint created | Based on Souffle provenance PoC results: disposal flat check + recursive passivation with negation both verified on Souffle 2.5 `-t explain`. JSON output confirmed parseable. 5 anti-debt boundaries defined. |
| 2026-03-22 | scoped | P1 fix: runner contract | Changed from modifying `run_package` return type to standalone `run_provenance_explain()` function. `run_package` signature/return completely unchanged. Prevents wave to engine_eval.py callers. |
