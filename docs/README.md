# FactGraph documentation

This directory contains the public, task-oriented FactGraph documentation.
New Python product code should begin with the
[quickstart index](quickstart/README.md) and follow the Product V2 path.

## Start here

- [FactGraph quickstart](quickstart/README.md) — ordered learning path and
  compatibility map.
- [Complete Product V2 workflow](quickstart/product_workflow_v2.md) — schema,
  Product Rule/Function/Policy, typed Query, Scenario, execution profiles,
  structured Result/Explain and replay in one tutorial. The Explain chapter
  includes the JSON-safe canonical projection, evidence availability states
  and read-projection digest for Product integration. FactGraph does not yet
  ship an Agent, Meander, or MCP handoff for this projection.
- [Structured Explanation notebook](../examples/10_structured_explanation_contract.ipynb)
  — an executed graph-present/graph-unavailable consumption example.
- [Security](SECURITY.md) — secret handling and reporting guidance.

Maintainer-facing implementation contracts live beside their modules under
`src/factgraph/*/docs/`. Cross-project coordination and internal workflow state
are maintained outside this product repository.
