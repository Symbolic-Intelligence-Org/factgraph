# FactGraph final Query / Scenario closure: final verification

- Status: completed
- Date: 2026-08-14
- Branch: `codex/v0.3.0-factgraph-final-closure-2026-08-14`
- Baseline: `416456445957251b45a6ebbc8fb1f979843bf2ac`
- Scope authority: [Q18 final closure contract](../../design/decisions/active/2026-08-14_q18-factgraph-final-closure-contract.md)
- Blueprint: [final closure](../../blueprints/active/2026-08-14_factgraph-final-closure.md)

## Verified delivery

The isolated V1 path now joins the established semantic Rule/Policy Query
compiler to a new grounded Scenario resolver, a restricted finite relation
provider, an isolated execution relation, typed result/expectation assessment,
sealed EvaluationRun, explicit detached Explain/replay, immutable candidate
comparison, and a non-causal Scenario diff. It does not change V0 Query,
ScenarioRun, bundle, EvaluateResult, or legacy SDK evaluation semantics.

### Capability evidence

| Contract area | Verified outcome |
| --- | --- |
| Scenario / effective world | Canonical order-independent operations; scalar/set/relation/entity/assertion removal; exact local closure; conflict and identity-mutation rejection; scope-ignore remains admission-only. |
| Query / expectation | Structured Rule/Policy target lift, one-hop navigation, rows/exists/count/set, typed complete/underdetermined/unsupported expectations, explicit local absence. |
| Provider | One finite pre-engine materialization and sealed receipt; exact supplied-predicate replacement; no engine-time callback; persistent source-view mutation detected fail-closed. |
| Portable profile | Real native, Soufflé and ProbLog execute the same isolated positive relation. Only normalized selected-row parity is claimed; each adapter has succeeded/failed/unsupported frames and no fallback. |
| Run / replay / Explain | Pins program/schema/profile/base/effective worlds and receipts; detached replay uses no Store or provider; Explain requires an explicit row or summary target and does not fabricate negative proof. |
| Comparison / ScenarioDiff | Base/candidate targets are independently compiled against one sealed effective world. Both comparison and ScenarioDiff report differences only; causal/evidence relations are `not_claimed`. |

## Commands and results

| Check | Result |
| --- | --- |
| `PYTHONPATH=src /Users/zhenzhili/miniforge3/envs/factpy/bin/python -m pytest tests/application tests/sdk tests/test_sdk_find_partial_identity.py tests/test_v1_public_surface_exports.py -q` | **680 passed, 175 subtests passed** |
| Focused V1 protocol/runtime/SDK corpus | **79 passed, 3 subtests passed** after final ScenarioDiff/public-surface integration |
| Scoped `ruff format --check` and `ruff check` over every new/changed V1 production/test module | passed |
| `mypy --follow-imports=skip` over the nine V1 production protocol/runtime modules | passed, no issues |
| `git diff --check` | passed |
| Independent adversarial review | **CLEAR**: no reproducible P0/P1; includes invocation/payload splice, capture race, forged absence closure, provider mutation, identity mutation, candidate union, and portable partial-frame probes. |

## Explicit non-results / carry-forward

- Whole-repository bare `pytest -q` cannot complete collection in this pinned
  baseline because `src/service/static_ui.py` imports
  `render_evidence_graph_html`, which is absent from
  `src/factgraph/audit/evidence_graph.py`; the same mismatch exists at the
  baseline commit. Unrelated third-party `kg-gen` tests also have independent
  package/import layout errors. This closure does not modify those paths.
- The default Python environment's test process has the pre-existing SIGSEGV
  issue documented by the project. All acceptance evidence above uses the
  pinned `factpy` environment.
- Provider callbacks are trusted same-process extension code. V1 detects a
  persistent source-view mutation and refuses to seal a result; it neither
  sandboxes nor rolls back malicious callback behavior.
- Meander Plan/Package/permissions/Translator/SourceRecord/product verdicts,
  Actions/Decide, global NAF/negative facts, source authority, and proof
  equivalence remain intentionally outside FactGraph V1.
