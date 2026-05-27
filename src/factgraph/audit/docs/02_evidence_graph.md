# EvidenceGraph (audit)

- Scope: `src/factgraph/audit/evidence_graph.py`
- Last updated: 2026-05-27
- Audience: developers implementing cross-engine explainability
  consumers in the audit layer

## 1. Role

`EvidenceGraph` is the unified explainability DTO of the `audit`
layer.

Its responsibilities are:

- Hold the shared skeleton produced by converters from engine-native
  provenance carriers
- Provide a unified node / edge / layout entry point for downstream
  renderers
- Give Souffle / ProbLog / PyReason a single consumption abstraction
  without rewriting any engine truth

It currently does not:

- Replace each engine's own provenance carrier
- Replace Souffle's existing `CandidateEvidenceTree`
- Replace `service.static_ui`'s full-page templates
- Act as a user session transcript or cryptographic provenance channel

The v1 audit contract is **sessionless**. An audit record is carried by
three layers:

- `EvaluateResult`: the result envelope with `run_id`, engine identity,
  view/semantics digests, row ids, and result digest
- `Explanation`: the row-bound status envelope returned by `row.explain()`
- `EvidenceGraph.metadata`: a durable graph-local copy of the row/result
  context for passed rows

`run_id` remains envelope-level. It is intentionally not duplicated into
`EvidenceGraph.metadata`; graph-only run grouping is a future design.

Native and Souffle row explanations now use the same DTO family. For passed
native or Souffle `EvaluateRow.explain()` calls, the row-level `EvidenceGraph`
is populated as a Form 1 tree with a root `conclusion`, selected-branch
`premise` nodes, assertion `seed` nodes, and `supports` edges. This is
separate from the older candidate evidence tree and Souffle proof-tree readback
APIs.

## 2. Current data model

The current v1 exposes three frozen dataclasses:

- `EvidenceNode`
  - `node_id`
  - `node_kind`
  - `component`
  - `label`
  - `value_summary`
  - `timestamp`
  - `engine_meta`
- `EvidenceEdge`
  - `edge_id`
  - `from_node_id`
  - `to_node_id`
  - `edge_kind`
  - `rule_label`
  - `engine_meta`
- `EvidenceGraph`
  - `graph_id`
  - `engine`
  - `root_node_id`
  - `nodes`
  - `edges`
  - `support_kind`
  - `layout_hint`
  - `metadata`

`component` is a renderer-facing subject key; it is not guaranteed to
correspond to a single entity identity. Relational expressions such
as `alice→bob` are also allowed as a `component`.

For row-sourced passed explanations, `metadata` carries the current v1
audit bridge keys:

| Key | Meaning |
|---|---|
| `result_id` | owning `EvaluateResult` id |
| `row_id` | explained row id |
| `evidence_ref_id` | row `EvidenceRef.ref_id` |
| `claim_digest` | row claim digest |
| `closed_head_digest` | closed-head digest |
| `expr_digest` | evaluated expression digest |
| `rule_set_digest` | rule set digest |
| `view_snapshot_digest` | database/view snapshot digest |
| `semantics_digest` | semantics profile digest, or `None` |
| `result_digest` | full result digest |
| `engine` | engine id |
| `engine_version` | engine version, or `None` |
| `adapter_version` | adapter version, or `None` |
| `evaluated_at` | JSON-safe evaluated timestamp |

Future metadata keys need an owning blueprint that names the producer,
consumer, and compatibility impact.

## 3. Frozen enumerations

Only the minimal shared enumerations are frozen at v1:

- `layout_hint`
  - `tree`
  - `timeline`
- `node_kind`
  - `conclusion`
  - `premise`
  - `seed`
- `edge_kind`
  - `supports`
  - `derives`
  - `updates`

Native and Souffle Form 1 row graphs use `supports` only. `derives` and
`updates` remain reserved for Form 2 / temporal engine paths. The `dag` layout
and the `rule_fire` node kind are not in v1 scope yet.

## 4. Validation and invariants

`EvidenceGraph` performs minimal structural validation in
`__post_init__`:

- `layout_hint` must be `tree` or `timeline`
- `root_node_id` must exist in `nodes`
- `node_id` must be unique
- `edge_id` must be unique
- Each edge's endpoints must reference existing nodes

`engine_meta` and `metadata` are shallow-frozen via `MappingProxyType`
to prevent consumers from mutating the shared DTO during rendering.

Durable or external graph dictionaries should be reconstructed through
`evidence_graph_from_dict(...)` before rendering. The reference renderer
accepts constructed `EvidenceGraph` instances, not raw dictionaries or
duck-typed stand-ins.

## 5. Current renderer

`audit/evidence_graph.py` currently implements:

- `render_evidence_graph_html(graph)`
  - Dispatches by `layout_hint` to:
    - tree renderer
    - timeline renderer
- tree renderer
  - Entry at `root_node_id`
  - By the current edge `from -> to` child-to-parent convention,
    incoming edges are rendered as child branches
- timeline renderer
  - Currently uses a CSS-grid form:
    - column = timestep
    - row = component
    - cell = stacked event cards

The renderer produces a **standalone HTML fragment**, not a full HTML
page. It is designed to be embedded later by
`service.static_ui`'s candidate evidence page.

The renderer is a reference diagnostic utility. It should be truthful and
boring: display graph data that already exists, never infer missing
provenance, and never invent placeholder nodes for invalid inputs.

Large graph guidance follows the active evidence design:

- more than `250` nodes or more than `500` edges emits a warning banner
- the reference renderer still renders the graph
- the renderer does not truncate solely because the graph is large
- product UIs should provide folding, search, virtualization, or
  progressive disclosure for repeated inspection

## 6. Current boundaries

`EvidenceGraph` is no longer just an in-memory DTO:

- `audit/evidence_graph.py` now provides:
  - the frozen dataclass DTO
  - the standalone HTML fragment renderer
  - `evidence_graph_to_dict(...)` / `evidence_graph_from_dict(...)`
    round-trip helpers
- The audit package can optionally write
  `audit/evidence_graphs.jsonl`
  - One line per `{candidate_id, evidence_graph}`
  - Materialized at export time by the runtime exporter:
    - `souffle`: rebuilt from the proof tree in
      `provenance_trees.jsonl`
    - `pyreason`: converted from the event log in
      `ProvenanceEnvelope.payload`
    - `problog`: converted from the proof trace in
      `ProvenanceEnvelope.payload`
  - `native` and `souffle` row explanations produce live row-level Form 1
    graphs; native candidate readback still keeps the candidate evidence tree /
    summary / narrative DTOs, and Souffle proof-tree readback still uses the
    adapter proof-tree converter
- `AuditQuery.get_candidate_evidence_graph(...)` reads the durable
  graph
- `service.static_ui`'s candidate evidence page now prefers rendering
  the durable `EvidenceGraph`, keeping the Souffle proof-tree
  fallback only for older packages

Boundaries that still hold:

- `EvidenceGraph` is an engine-bound adapter provenance artifact, not
  an explain surface that every candidate must have
- Runtime live `explain-tree` / `explain-summary` /
  `explain-narrative` / `explain-nl` still do not directly support
  `pyreason_provenance_v1` / `problog_provenance_v1`
- `EvidenceGraph` still does not replace engine-native provenance
  carriers; the durable package writes only the converter output
  without flattening engine truth
- The candidate evidence page still keeps the existing Souffle
  provenance-tree section; `EvidenceGraph` is an additional unified
  explain block, not a replacement for the older tree viewer
- Rich adapter topology population and engine-specific enrichment belong
  to future T8 slices
- Witness/assertion-returning match output is a future match/evidence
  seam; this module does not define `.as_assertions()`, `.witnesses()`,
  or view-creation APIs

## 7. Known Issues (confirmed during 2026-03-29 walkthrough)

### ~~F-EG-1 No cycle detection at construction (severity: low)~~ — RESOLVED

Fixed: `EvidenceGraph.__post_init__` adds DFS cycle detection after
endpoint reference validation. Graphs containing cycles raise
`ValueError("cycle detected in EvidenceGraph involving node ...")` at
construction. The render-time `if node_id in ancestry` cut-off
remains as defense in depth.

### ~~F-EG-2 Timeline renderer doesn't render edges (severity: low)~~ — RESOLVED

Fixed: `_render_timeline_card` accepts `incoming_edges` and
`node_by_id` parameters and renders an incoming-edge annotation at
the bottom of each card (`← {edge_kind} · {rule_label} from
{source_label}`). When no edges are present, no edge-note div is
emitted.

### ~~F-EG-3 `evidence_graphs.jsonl` silently overwrites duplicate candidate_id (severity: low)~~ — RESOLVED

Fixed: `reader._read_evidence_graphs()` checks `candidate_id in
result` before assignment and raises `AuditReadError("duplicate
candidate_id in evidence_graphs: ...")` on duplicates.

### ~~F-EG-4 `static_ui._try_build_evidence_graph_from_provenance` bare Exception catch (severity: low)~~ — RESOLVED

Fixed: `except Exception:` narrowed to `except (ValueError, KeyError,
TypeError):`, covering the known failure modes of
`souffle_proof_tree_from_dict` and
`souffle_proof_tree_to_evidence_graph`. Unexpected exceptions such as
`ImportError` and `AttributeError` propagate normally.
