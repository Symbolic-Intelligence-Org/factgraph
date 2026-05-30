# Task Blueprint Audit: Slice 6 — Form I Legacy Debt Cleanup

- Blueprint: [2026-05-30_form-i-debt-cleanup.md](./2026-05-30_form-i-debt-cleanup.md)
- Branch: `v0.2.0-blueprint-form-i-debt-2026-05-30`
- Fork point: `fb744d95` (Slice 6 Stage 1 audit head)
- Status: implemented audit log

## Event Log

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-30 | draft | Blueprint created | Drafted from Stage 1 audit `fb744d95`; Stage 2 Q-decision skipped per reviewer verdict because no new design decision is required. Scope is Form I legacy callsite cleanup for live tests, sibling package tests/docs, current docs/tools/tutorials, with dirty/archive/historical carve-outs inherited from Slice 4/5. |
| 2026-05-31 | preflight-amend | Step 4.3 preflight findings applied | Locked the four benchmark scripts plus `tutorials/evidence-pipeline.cn.md` in scope, added explicit sibling package and negative-test file lists, clarified root README Form I + namespace cleanup, and corrected the §7 acceptance total to 26 checkboxes. |
| 2026-05-31 | scoped | Scope freeze accepted | Self-check complete: Stage 1 FI-R1-R5 plus FI-REC1-4 are represented; PF-R1/PF-REC1-4 amendments landed; SF1-SF10 and Non-goals N1-N10 are complete; Step 0-8 has commit-boundary deliverables; duplicate Root README acceptance was removed per reviewer Option A, leaving 25 acceptance checkboxes. |
| 2026-05-31 | implementing-step-0 | Pre-implementation inventory complete | Re-ran tracked-HEAD Form I grep gates on implementation branch; counts match scoped preflight: 63 `tests/` files, 5 sibling package files, 5 tools/tutorial files, 9 example files split into dirty/archival handling, 3 current-doc candidates, and 13 workflow historical/audit files. No new Q-PR1, runtime descriptor, shadow-store, `:exists`, ledger, or adapter scope found. |
| 2026-05-31 | implementing-step-1 | Live core test fixtures migrated | Migrated positive Form I fixtures across `tests/` to shipped descriptors (`Identity()`, `Field()`, and annotation-inferred multi fields). Residual deprecated Form I grep hits are confined to Step 3 semantic-rewrite targets; 62 changed test modules import successfully. |
| 2026-05-31 | implementing-step-2 | Sibling package fixtures migrated | Migrated the five scoped sibling package files to shipped Form I descriptors and current import/namespace surfaces where needed; all four sibling Python modules import successfully, and selected non-legacy behavior tests pass. |
| 2026-05-31 | implementing-step-3 | Negative test semantics rewritten | Rewrote the three semantic targets: `test_sdk_schema_primary_key_required.py` now asserts Form I acceptance plus explicit legacy-kwarg rejection, while `test_application_entity_view.py` and `test_application_schema_runtime.py` use explicit complete identity bundles instead of deleted identity-default behavior. |
| 2026-05-31 | implementing-step-5 | Dirty notebook decision point | Defaulted to untouched per SF6: active dirty notebooks `examples/01_sdk_check_diagnose.ipynb` and `examples/02_overlay_why_not_frontier.ipynb` were not edited; archive dirty notebook `examples/archive/01_sdk_basics.ipynb` remains out of scope per SF7. |
| 2026-05-31 | implementing-step-6 | Regression sweep and final grep gate complete | Imported 67 migrated Python modules, ran 49 representative unittest cases, and completed compileall/diff-check gates; final Form I grep hits are classified as Step 3 negative-test inputs, Step 4 deferred README/tools/tutorials, SF6 dirty notebooks, SF7 archive/historical references, or intentional migration-hint/docs examples. No unclassified live runtime/test hit found. |
| 2026-05-31 | implemented | Outcome complete | Filled §10 Outcome, flipped blueprint/audit status to implemented, and recorded Step 4 docs/tools deferral as carry-forward rather than false-green acceptance; implementation remains unpushed pending user authorization. |

## Decision Notes

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-30 | Fork blueprint from Stage 1 audit head `fb744d95`. | The audit is the binding input and already passed reviewer verification. |
| 2026-05-30 | Skip Stage 2 Q-decision. | Reviewer agreed the slice has no new design tension; dirty/archive/historical policies inherit from Slice 4/5. |
| 2026-05-30 | Keep Slice 6 housekeeping-only. | Runtime descriptor behavior already shipped; the slice migrates stale callsites and current docs without changing semantics. |
| 2026-05-30 | Negative tests require semantic rewrite. | Stage 1 FI-R5 showed primary-key/default/cardinality tests can become meaningless if mechanically substituted. |
| 2026-05-30 | Dirty notebooks remain protected. | Active dirty notebooks contain stale Form I but must not be overwritten without per-file user authorization. |
| 2026-05-30 | Historical/archive references remain classified carve-outs. | Global zero grep across historical material would erase useful decision/audit context and violate Slice 4/5 precedent. |
| 2026-05-31 | Step 0 inventory matches scoped preflight. | Exact implementation-branch inventory remains: 63 live `tests/` files; sibling files `src/service/tests/test_problog_candidate_evidence_tree.py`, `src/service/tests/test_problog_semantic_annotation_l4.py`, `src/service/tests/test_runtime_query_policy.py`, `src/domains/ecss/tests/test_phase3_contracts_v1.py`, `src/agent/extraction/docs/USAGE.md`; tools/tutorial files `tools/benchmarks/bench_scenario_a_audit_delivery_shape.py`, `tools/benchmarks/extraction/run_cross_provider_benchmark.py`, `tools/benchmarks/extraction/run_multi_model_entity_benchmark.py`, `tools/benchmarks/extraction/run_re_docred.py`, and `tutorials/evidence-pipeline.cn.md`. |
| 2026-05-31 | Step 0 negative-test inventory is explicit. | Semantic rewrite targets remain `tests/test_sdk_schema_primary_key_required.py`, `tests/test_application_entity_view.py`, and `tests/test_application_schema_runtime.py`; eight `allow_identity_defaults=True` callsites are confined to the latter two files. |
| 2026-05-31 | Dirty/archive/historical carve-outs remain unchanged. | Dirty active notebooks are `examples/01_sdk_check_diagnose.ipynb` and `examples/02_overlay_why_not_frontier.ipynb`; archive example hits remain under `examples/archive/*`; 13 active workflow/audit/design hits are historical/audit/decision records for final-grep classification, not implementation edits. |
| 2026-05-31 | Step 1 kept negative semantics deferred. | `tests/test_sdk_schema_primary_key_required.py` remains untouched for Step 3, while `tests/test_application_entity_view.py` and `tests/test_application_schema_runtime.py` only had import-blocking positive descriptors migrated; their `allow_identity_defaults=True` behavior remains deferred to the Step 3 semantic rewrite. |
| 2026-05-31 | Step 1 included one live-test namespace collateral fix. | `tests/test_sdk_redesign_namespace_shape.py` had an import-time blocker from removed `_SDKReadManager` / `_SDKWriteManager` names after its Form I fixture migration; the test was minimally aligned to the current shipped `entities` / `fields` / `assertions` / `rules` / `inferences` namespaces without touching runtime. |
| 2026-05-31 | Step 2 limited sibling cleanup to Form I/import viability. | `src/service/tests/test_problog_semantic_annotation_l4.py` still contains older candidate-envelope / `accept` behavior expectations that are not Form I debt; Step 2 verifies import viability and leaves broader semantic modernization out of this housekeeping slice. |
| 2026-05-31 | Step 3 residual grep is intentional negative coverage. | Remaining deprecated Form I strings in live tests are only the rejection inputs inside `tests/test_sdk_schema_primary_key_required.py`; all `allow_identity_defaults=True` callsites were removed from live tests. |
| 2026-05-31 | Step 6 final grep gate classified all residual hits. | Live migrated tests and sibling modules are clean except intentional `assertRaises` inputs in `tests/test_sdk_schema_primary_key_required.py`; Step 4-deferred current docs/tools/tutorials remain carry-forward; dirty notebooks and archive/historical material remain carve-outs per SF6/SF7; `src/factgraph/sdk/schema.py` and SDK docs hits are migration-hint/example text. |
| 2026-05-31 | Step 6 confirms `allow_identity_defaults=True` live cleanup complete. | Remaining hits are only audit/blueprint/design historical records; there are no live test or runtime callsites. |

## Review Checklist

Reviewer should verify before scope flip:

- [x] Stage 1 audit `fb744d95` findings are represented in goals, non-goals, scope freeze, acceptance, and implementation plan.
- [x] Stage 2 skip rationale is explicit and defensible.
- [x] Negative-test semantic rewrite is separated from positive fixture migration.
- [x] Sibling package paths are explicitly in scope.
- [x] Root `README.md` stale current truth is explicitly in scope.
- [x] Dirty notebook and archive/historical locks are explicit.
- [x] Q-PR1 sacred paths remain no-touch.
- [x] Implementation steps are commit-boundary sized.
