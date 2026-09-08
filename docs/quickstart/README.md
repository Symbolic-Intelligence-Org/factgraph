# FactGraph quickstart

This directory documents two intentionally different generations of the
public Python surface. New product code should start with the Product V2 path;
the legacy pages remain useful when maintaining `fg.eval.evaluate(...)` code.

## Recommended path for new code

1. [Schema definition](schema_definition.md) — declare `Entity`, `Identity`,
   and `Field` values.
2. [Three-layer API](three_layer_api.md) — create entities and write/read
   fields and assertions.
3. [Complete Product V2 workflow](product_workflow_v2.md) — author Product
   Rules, Policies, Product Functions and Queries; apply Scenario overlays;
   choose deterministic/portable/ProbLog execution; consume structured
   Result/Explain data; and replay a sealed run.
4. [Load and save](load_and_save.md) — use in-memory, attached, or durable
   workspaces.

The runnable companions are:

- [`examples/09_product_scenario_execution_v2.ipynb`](../../examples/09_product_scenario_execution_v2.ipynb)
  for the complete authoring, Scenario, execution and replay journey; and
- [`examples/10_structured_explanation_contract.ipynb`](../../examples/10_structured_explanation_contract.ipynb)
  for the canonical business/UI Explain projection, including one real
  EvidenceGraph-present path and one explicitly unavailable path.

Both execute the real public SDK and engines rather than using mock output.

## Reference chapters

| Chapter | Current role |
| --- | --- |
| [Data model](data_model.md) | Ledger claims, metadata, uncertainty pairs and append-only retraction |
| [Rules](rules.md) | Rule/RuleExpr history plus the current Product Rule/Policy/Function authoring bridge |
| [Engines and configs](engines_and_configs.md) | Product V2 execution profiles and legacy V0 `ProbLogConfig` / `PyReasonConfig` |
| [Evaluation and evidence](evaluate_and_evidence.md) | Product V2 Outcome/Explain/replay plus legacy `EvaluateResult` / `Explanation` |
| [Capabilities](capabilities.md) | Runtime schema-capability introspection |

## Current default vocabulary

- **Product Rule** — a resolved logical relation with `id`, `version`,
  `AssetMeta`, typed ports and a graph-bound semantic contract.
- **Product Function** — a pure deterministic scalar computation asset. It is
  a Policy peer of Rule, never a Rule builtin or an action tool.
- **Product Policy** — the only composition owner for Rule occurrences,
  Function occurrences, `all` / `any`, comparisons, unification and explicit
  `WeightedChoice` topology.
- **Query** — typed `bind` and ordered `select` intent over a resolved Product
  Rule/Policy target.
- **Scenario** — a run-local fact overlay. It can add/set/remove effective
  facts with strict semantic/provenance metadata, but cannot patch Rules or
  Policies.
- **Execution profile** — a target-pinned, sealed choice of deterministic,
  portable deterministic, or ProbLog point semantics. It is not an arbitrary
  engine kwargs dictionary.
- **Product outcome** — named baseline/effective/candidate ResultViews,
  row-explicit structured Explain data and detached replay over one sealed
  `EvaluationRunV2`. Explain exposes JSON-safe `to_dict()`, canonical bytes
  and a read-projection digest; business code branches on the structured
  evidence `state` and `reason_code`, never on rendered prose.

## Compatibility boundary

The following APIs are still supported but are not the default teaching path:

- `fg.eval.evaluate(..., engine=..., config=...)` returns legacy
  `EvaluateResult` / `EvaluateRow` / `Explanation` values;
- `ProbLogConfig` and `PyReasonConfig` configure that legacy evaluation path;
- V1 `native_deterministic_profile_v1()` and
  `portable_deterministic_profile_v1()` create sealed GoalPlan V1 runs; and
- `fg.policy(...)` / `PolicyDraft` remains the Q19 concise Policy façade.

Do not pass V2 Scenario/profile values to legacy/V1 terminals. Unsupported
cross-generation combinations fail closed instead of silently dropping
metadata, probability, Function or `WeightedChoice` semantics.
