# FactGraph final Query / Scenario closure: final verification

- Status: completed after independent correction and repeat verification
- Date: 2026-08-14
- Branch: `codex/v0.3.0-factgraph-final-closure-2026-08-14`
- Baseline: `416456445957251b45a6ebbc8fb1f979843bf2ac`
- Scope authority: [Q18 final closure contract](../../design/decisions/active/2026-08-14_q18-factgraph-final-closure-contract.md)
- Blueprint: [final closure](../../blueprints/active/2026-08-14_factgraph-final-closure.md)

## Verified delivery

The isolated V1 path joins the established semantic Rule/Policy Query
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
| Provider | One finite pre-engine materialization and sealed receipt attached to a Rule/Policy Query; exact supplied-predicate replacement; no engine-time callback; persistent source-view mutation detected fail-closed. A bare provider is intentionally rejected because it has no independent result shape. |
| Portable profile | Real native, Soufflé and ProbLog execute the same isolated positive relation. Only normalized selected-row parity is claimed; each adapter has succeeded/failed/unsupported frames and no fallback. |
| Run / replay / Explain | Pins program/schema/profile/base/effective worlds and receipts; detached replay uses no Store or provider. A sealed **restricted native Explain context** is revalidated and deterministically recomputed only from the captured relation for an explicit positive row, producing its EvidenceGraph and Policy-node projection. It does not claim that a graph was captured directly, never fabricates negative proof, and leaves summary/zero targets graphless. Portable proof parity remains `not_claimed`. |
| Comparison / ScenarioDiff | Base/candidate targets are independently compiled against one sealed effective world. Both comparison and ScenarioDiff report differences only; causal/evidence relations are `not_claimed`. |

## Commands and results

| Check | Result |
| --- | --- |
| `PYTHONPATH=src /Users/zhenzhili/miniforge3/envs/factpy/bin/python -m pytest tests/application tests/sdk tests/test_sdk_find_partial_identity.py tests/test_v1_public_surface_exports.py -q` | **688 passed, 175 subtests passed** after the Explain and portable-parity corrections |
| Focused Explain / portable / V1 protocol-runtime-SDK corpus | **83 passed, 17 subtests passed** after final type/format hygiene; independent Explain adversarial cohort: **53 passed** |
| `ruff format --check` over all newly added V1 production/test modules and changed files without inherited formatter debt; `ruff check` over modified Python files | passed |
| `/Users/zhenzhili/miniforge3/bin/mypy --follow-imports=skip` over the V1 production protocol/runtime modules | passed, no issues |
| `git diff --check` | passed |
| Independent adversarial review | **CLEAR**: no reproducible P0/P1; additionally covers positive-row EvidenceGraph/Policy overlay, Any branch execution and multiple holding paths, source provenance, context/world/provider/candidate tamper, and detached Store mutation. |

## Explicit non-results / carry-forward

- **Resolved closure correction:** the independent audit correctly found that
  the earlier V1 envelope held only static PolicyStructure/Scenario operations.
  The final implementation seals a restricted native Explain context, validates
  it against the sealed program/target/world pins, then recomputes the graph and
  Policy-node `HOLDS`/`FAILS`/`NOT_REACHED` projection from the captured relation
  only. Repeated tests and a separate adversarial review verify this correction.

- **Resolved portable-parity correction:** a post-closure cross-entity
  `PolicyFieldNavigation` / `PolicyCompare` probe exposed a Soufflé support
  reconstruction defect: two occurrences of the same predicate were collapsed
  by predicate id before hidden bindings were rebuilt. The adapter now keeps
  witnesses keyed by predicate *occurrence* until reconstruction is complete,
  then produces the stable predicate-keyed receipt view. A real Native /
  Soufflé / ProbLog regression covers two distinct `Person` occurrences,
  field navigation and comparison; selected-row parity now passes. This is
  still a narrow positive deterministic profile, never a universal syntax or
  proof-parity claim.

- Whole-repository bare `pytest -q` cannot complete collection in this pinned
  baseline because `src/service/static_ui.py` imports
  `render_evidence_graph_html`, which is absent from
  `src/factgraph/audit/evidence_graph.py`; the same mismatch exists at the
  baseline commit. Unrelated third-party `kg-gen` tests also have independent
  package/import layout errors. This closure does not modify those paths.
- The default Python environment's test process has the pre-existing SIGSEGV
  issue documented by the project. All acceptance evidence above uses the
  pinned `factpy` environment.
- `src/factgraph/sdk/store.py` fails `ruff format --check` both at the
  baseline and this commit. This slice changes only its V1 Query docstring;
  lint passes, but inherited whole-file formatter debt is not claimed as
  fixed or hidden by the V1 result.
- Provider callbacks are trusted same-process extension code. V1 detects a
  persistent source-view mutation and refuses to seal a result; it neither
  sandboxes nor rolls back malicious callback behavior.
- Meander Plan/Package/permissions/Translator/SourceRecord/product verdicts,
  Actions/Decide, global NAF/negative facts, source authority, and proof
  equivalence remain intentionally outside FactGraph V1.
