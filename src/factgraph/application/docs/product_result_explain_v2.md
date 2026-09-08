# Product Result and Explain Views V2

- Scope: `src/factgraph/application/product_result_views_v2.py` and
  `src/factgraph/application/product_explanation_data_v2.py`
- Audience: Product Python integration code that needs immutable presentation
  data from a sealed FactGraph evaluation run; this is not an Agent, Meander,
  or MCP API

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

# Product code opens the facade and obtains a detached JSON-safe projection.
# FactGraph does not establish an Agent, Meander, or MCP adapter, route, or
# wire contract here; any future external integration must adapt this shape
# under its own contract.
wire = data.to_dict()
canonical = data.to_canonical_bytes()
projection_digest = data.content_digest
# Rendered text is display-only and is not part of the digest.
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
# `data.asset`, `data.choice`, and `data.functions` expose their sealed captures.
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
- `functions` — replay-validated Product Function definition pins and the
  selected side's typed pre-engine calls/materialization digests. This section
  may contain the complete upstream occurrence materialization rather than
  only calls matching the selected row; it never contains executable Python;
  and
- `boundaries` — explicit `not_claimed` proof-parity, negative-proof, source
  authority and action-authorization boundaries.

`narrate_evaluation_explanation_v2(...)`,
`render_evaluation_explanation_text_v2(...)`, `data.narrate()` and
`data.render_text()` are pure, lossy display helpers. Product code must not
parse their prose.

## Canonical read projection

Both `EvaluationExplanationDataV2` and
`EvaluationRunV2ExplanationDataV2` expose the same serialization operations:

```python
wire = data.to_dict()
canonical = data.to_canonical_bytes()
assert wire["$schema"] == "factgraph.product_explanation"
assert wire["schema_version"] == 2
if wire["source_protocol"] == "evaluation_run_v1":
    protocol_section = wire["execution"]
elif wire["source_protocol"] == "evaluation_run_v2":
    protocol_section = wire["profile"]
else:
    raise ValueError("unsupported Product Explain source protocol")
assert isinstance(protocol_section, dict)
assert data.content_digest.startswith("sha256:")
```

`to_dict()` returns newly detached ordinary dictionaries, arrays and JSON
scalar values. It never returns dataclasses, tuples or mapping proxies. It
rejects malformed, cyclic, unbounded, or non-UTF-8 dynamic values with the
typed serialization error rather than emitting a partial projection. It never
invokes a Store, source resolver, evaluator, replay, Function callable or
renderer. `to_canonical_bytes()` uses strict UTF-8 JSON with sorted keys,
compact separators and non-finite floats disabled. `content_digest` is the
SHA-256 token of exactly those bytes and is deliberately not embedded in the
wire it hashes.

Adding or changing a top-level wire field requires an explicit schema-version
decision and an update to the canonical digest fixture; consumers must not
silently reinterpret an old version under the same projection identity.

The digest identifies the Product *read projection only*. It is not the sealed
run digest, a signature, source authentication, admission decision, access
grant or user authorization. Consumers that persist the projection should
store its schema/version, source protocol, bytes and digest alongside the
authoritative run/record reference rather than substituting one identity for
the other.

Evidence availability remains an ordinary required structured section:

```python
evidence = wire["evidence"]
graph_bearing_states = {
    "native_detached_recomputed",
    "portable_native_inner_not_parity",
    "problog_trace_captured",
}
if evidence["state"] in graph_bearing_states:
    graph = evidence["graph"]
    assert graph is not None
    render_graph(graph)
else:
    assert evidence["graph"] is None
    render_availability(evidence["state"], evidence["reason_code"])
```

Business code must inspect `state` and `reason_code`; only the three listed
states are graph-bearing. `graph is None` alone is not a conclusion, an empty
proof or a negative result.

The set above is the closed projection schema, not a claim that every engine
currently emits every graph-bearing state. This slice executes a V1 Native
graph-present example and a V2 graph-unavailable example; it does not claim a
V2 ProbLog graph capture, R3e coordinate capture, or F4C attribution support.

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

For a V2 Product Function, the validated replay-program capture exposes the
Function id/version/signature/implementation and asset-binding pins, ordered
typed ports, and Rule-port input edges. The run side independently exposes
each materialized call key, typed input/output values, and materialization
digest. Replay consumes these sealed calls and never invokes the callable.
The Function capture is structured explanation data even when
`evidence.graph is None`; no `EvidenceTree.Source` or Policy proof node is
invented merely to make a renderer look complete.

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

## Runnable structured-consumption example

[`examples/10_structured_explanation_contract.ipynb`](../../../../examples/10_structured_explanation_contract.ipynb)
runs one sealed V1 Native path with a sanitized EvidenceGraph and one Product
V2 Native observation with a typed unavailable reason. It validates canonical
bytes/digests and shows a UI branch that consumes only structured state while
keeping narration display-only.
