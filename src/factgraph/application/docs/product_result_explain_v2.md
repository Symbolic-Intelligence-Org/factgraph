# Product Result and Explain Views V2

- Scope: `src/factgraph/application/product_result_views_v2.py` and
  `src/factgraph/application/product_explanation_data_v2.py`
- Audience: product/UI/Agent integration code that needs immutable presentation
  data from a sealed FactGraph evaluation run

## Purpose

`ResultViewV2` and `EvaluationExplanationDataV2` are read-only presentation
adapters. They neither evaluate a Query nor accept a `Store`, resolver,
callback, or source record. The V1 adapter reports
`source_protocol="evaluation_run_v1"`; it does not rewrite, re-seal, or imply
that the source run is an `EvaluationRunV2`. The separate V2 adapter opens
only `EvaluationRunV2` and reports `source_protocol="evaluation_run_v2"`.
The shapes remain distinct because V2 engine observations are not V1 canonical
result rows or V1 Explain anchors.

```python
from factgraph.application import (
    evaluation_explanation_data_v2_from_run,
    result_view_v2_from_run,
)

result = result_view_v2_from_run(run, side="effective")
row_target = result.rows[0].to_explain_target()  # caller selected this row
data = evaluation_explanation_data_v2_from_run(run, target=row_target)

# UI/Agent consumes data.identity/data.policy/data.scenario/data.evidence.
# Rendered text is display-only.
text = data.render_text()
```

For a V2 engine observation, select a row explicitly and use the V2 target
that row mints:

```python
from factgraph.application import (
    evaluation_explanation_data_v2_from_evaluation_run_v2,
    result_view_v2_from_evaluation_run_v2,
)

result = result_view_v2_from_evaluation_run_v2(run_v2, side="effective")
row = result.rows[0]  # the caller deliberately selected this observation
data = evaluation_explanation_data_v2_from_evaluation_run_v2(
    run_v2,
    target=row.to_explain_target(),
)

# Row identity/observation digests and `row.point_probability` remain
# structured data.  For ProbLog, inspect
# `result.probability_materialization` / `data.probability_materialization`
# for the declared decimal and its explicit float64 engine projection.
# `data.scenario` carries captured world/fact/provenance lanes; `data.profile`,
# `data.asset`, and `data.choice` expose their sealed captures.
```

## Explicit target and proof rules

- `result_view_v2_from_run(..., side=...)` requires a named run side.
- `RowViewV2.to_explain_target()` names only that row's sealed anchor. There is
  no implicit "first row" operation and no V0-style `close()` method.
- `SummaryViewV2.to_explain_target()` is valid for a zero or nonzero result
  summary, but always carries `negative_proof="not_claimed"`. A summary is not
  converted into an absence proof.
- If a detached native evidence recomputation is unavailable, Explain returns
  an explicit `EvidenceSupportViewV2(state="not_available", reason_code=...)`;
  it never manufactures an evidence graph.
- V2 only permits a row-observation target (`EvaluationRunV2ExplainTarget`),
  bound to `run_digest + side + engine + observation_digest`. It has no V1
  summary target and makes no absence-proof claim.
- A V2 ProbLog point observation produces
  `EvidenceSupportViewV2(state="not_available",
  reason_code="PROBLOG_V2_EVIDENCE_GRAPH_NOT_CAPTURED", graph=None)`. Its
  point probability, its `problog_float64_v1` materialization, world, Scenario
  provenance, profile semantics and choice attachment states are structured
  data; they are not a synthetic
  `EvidenceGraph`.

## Structured sections and renderers

`EvaluationExplanationDataV2` contains independent machine-readable sections:

- `identity` and `query_descriptor` — sealed run/target/query identity and
  selection shape, never a raw Agent prompt;
- `outcome` and `execution` — observation, completeness, engine frames and
  technical assessment;
- `policy` — captured authored topology and, when present, projected node
  states;
- `scenario` — captured V1 operation identities and premise/witness refs;
- `evidence` — a closed evidence-support state and a sanitized graph only when
  evidence exists;
- `comparison` — non-causal sealed candidate/scenario comparison data when it
  is available; and
- `boundaries` — explicit `not_claimed` proof-parity, negative-proof, source
  authority and action-authorization boundaries.

`narrate_evaluation_explanation_v2(...)`,
`render_evaluation_explanation_text_v2(...)`, `data.narrate()` and
`data.render_text()` are pure, lossy display helpers. Product code must not
parse their prose.

## V1 compatibility capture markers

The V1 adapter never guesses V2-only information. V2 semantic-model,
profile-attachment, asset-descriptor, choice-topology, probability-observation,
Scenario metadata and provenance lanes show
`CaptureStateViewV2(state="not_captured", ...)` (or `not_applicable`) instead
of an empty reconstructed value.

Conversely, the V2 adapter exposes only material actually captured by
`EvaluationRunV2`: asset descriptor/binding, selected world facts and their
semantic/provenance lanes, execution profile and attachment pins, and (for a
successful ProbLog frame) the declared-decimal-to-float64 probability
materialization. For a V2 `WeightedChoice`, the validated replay-program
capture may also expose the sealed authored topology (selection key, arms,
weights, and condition ids). It is never reconstructed from a live Policy or
an engine proof; an absent capture remains explicitly `not_captured`.

## Evidence source and provenance boundary

`evidence_graph_view_v2_from_graph(...)` converts a generic
`EvidenceTree.Source` into `EvidenceSourceViewV2`. It allowlists a small set of
logical support metadata such as `source_kind`, `premise_ids` and
`scenario_operation_digests`; unknown metadata is omitted and only its key is
reported. A generic source is not a source record and is never reclassified as
one.

An *explicitly supplied* closed provenance descriptor may be displayed as an
`OpaqueProvenanceDescriptorV2`. The adapter uses structural inspection of the
closed `ProvenanceRefV1` wire/attribute shape and has no import-time dependency
on that protocol. It carries opaque ids/locators/digests only — not raw source
content, ACLs, tenant data, credentials, or admission decisions.
