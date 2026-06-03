# Evaluation Result And Evidence

Evaluation is read-only. `fg.eval.evaluate(...)` returns an `EvaluateResult`
envelope; rows on the envelope expose claims, evidence references, and the
explanation pipeline.

The canonical workflow is:

```python
result = fg.eval.evaluate(rule, head=rule)   # → EvaluateResult
row = result.first()                         # → EvaluateRow
explanation = row.explain()                  # → Explanation
```

| Surface | Returns | Purpose |
| --- | --- | --- |
| `fg.eval.evaluate(expr, head=rule, ...)` | `EvaluateResult` | Read-only evaluation envelope |
| `result[i]` / `result.first()` / `iter(result)` | `EvaluateRow` | Access one derived fact |
| `row.explain()` | `Explanation` | Live row-bound explanation (主路径) |
| `row.close()` | application `Rule` | Closed head for cross-session replay |
| `fg.eval.explain(expr, head=closed_head, ...)` | `Explanation` | Manual / advanced replay path |
| `fg.eval.preview_config(profile)` | preview | Inspect a semantics profile shape |

The rest of this page walks through each DTO in the chain.

## 1. `EvaluateResult` — the envelope

`EvaluateResult` is a frozen dataclass with 7 direct public fields, one
`ResultFingerprint` sub-object, one `engine_meta` mapping, and 7 row-access
forms.
The fields fall into four roles:

| Role | Fields |
| --- | --- |
| Envelope identity | `result_id` (`evalr_v1:...`), `fingerprint.run_id` (`run_v1:...`), `fingerprint.result_digest` (`sha256:...`) |
| Replay anchors | `fingerprint.expr_digest`, `fingerprint.rule_set_digest`, `fingerprint.view_snapshot_digest`, `fingerprint.config_digest` (or `None`) |
| Engine provenance | `engine` (`"native"` / `"problog"` / `"pyreason"`), `engine_meta["engine_version"]` (or `None`), `engine_meta["adapter_version"]` (or `None`) |
| Evaluation context | `head` (the closed application `Rule`), `evaluated_at` (`datetime` UTC), `rows` (`tuple[EvaluateRow, ...]`) |

Row access:

```python
result = fg.eval.evaluate(rule, head=rule)

len(result)            # row count
bool(result)           # True iff non-empty
result.count()         # explicit row count
result.exists()        # explicit non-empty check
result.first()         # first row or None
result[0]              # row by index → EvaluateRow
for row in result:     # iteration over rows
    ...
```

Identity and replay anchors are content-addressed digests. Two `EvaluateResult`
values with matching `fingerprint.expr_digest`,
`fingerprint.rule_set_digest`, `fingerprint.view_snapshot_digest`, and
`fingerprint.config_digest` evaluated the same logical query against the same
snapshot under the same semantics — they are replay-equivalent regardless of
when they ran.

The evidence audit channel is sessionless. `run_id` identifies the evaluation
envelope and lives at `EvaluateResult.fingerprint.run_id`; it is intentionally
not copied into an `EvidenceGraph`. Passed row graphs keep a durable row/result metadata bridge
instead: result id, row id, evidence ref id, claim and closed-head digests,
expression/rule/view/semantics/result digests, engine identity/version, adapter
version, and evaluated timestamp. Prefer the typed DTO fields above for
application logic; graph metadata is the audit bridge, not the primary SDK
branching surface.

## 2. `EvaluateRow` — one derived fact

`EvaluateRow` is frozen with row-owned conclusion/evidence fields and 2 live methods:

| Kind | Member | Purpose |
| --- | --- | --- |
| data | `row_id` (`run_v1:...`) | Stable id within `run_id` |
| data | `bindings` | Frozen `Mapping[str, Any]` keyed by head port name |
| data | `kind` | One of four row conclusion roles |
| data | `digest` | `sha256:` digest of the row claim content |
| data | `closed_head_digest` | Closed-head replay digest |
| data | `raw_kind` | `"probabilistic"` / `"possibilistic"` / `None` |
| data | `bound` | `(lower, upper)` tuple of floats, or `None` |
| method | `row.explain()` | Build `Explanation` for this row |
| method | `row.close()` | Build closed-head application `Rule` |

Both methods are **live-only**. They need the row to still know its owning
`EvaluateResult`. A row reconstructed from JSON or extracted into a
detached variable raises `DetachedRowError`:

```python
from dataclasses import replace

detached = replace(row, _result_resolver=None)
detached.explain()   # → DetachedRowError
detached.close()     # → DetachedRowError
```

`DetachedRowError` is a **Python programming error**, not a failure
classification. It indicates the row was constructed or transferred in a
way that broke its `_result_resolver` linkage (e.g., reconstructing from
JSON without re-binding to a result). It is **not** a `status="failed"`
outcome, has no `failure_class`, and should not be caught as a business
case. Code that needs cross-session explanation should use
`fg.eval.explain(expr, head=closed_head, ...)` with an explicit closed
head — see §5 below.

`row.bindings` maps each head port name to its typed term dict. Use
`result.head.id` for the head predicate id, `row.digest` for the row claim
digest, and `row.close()` when you need a replayable closed-head rule.

`raw_kind` and `bound` carry quantitative uncertainty propagated from the
ledger and engine adapters. The invariant `raw_kind is None ⇒ bound is None`
holds; the reverse pairing is enforced by the protocol. This is the
read-side projection of the same single-source contract documented at
[Raw uncertainty: raw_kind and bound](assertions.md#raw-uncertainty-raw_kind-and-bound)
on the write side — same two fields, never duplicated, never normalized to
a single number.

## 3. Row conclusion fields

| Field | Purpose |
| --- | --- |
| `kind` | One of four `ClaimKind` values |
| `digest` | `sha256:` digest of the claim content |

The four `ClaimKind` values:

- `fact_triple` — a derived `(pred_id, *terms)` ground fact
- `rule_head` — a rule's head shape (post-projection but not a fact)
- `aggregate_result` — a Count / Sum / Min / Max / Mean result
- `projection` — a port-projection over evaluation rows

`row.digest` is the row claim digest. The old result-side `Claim` wrapper has
been removed; ledger `Claim` records remain a separate persistence-layer type.

## 4. Closed-head digest — durable evidence identity

`row.closed_head_digest` is the durable closed-head replay digest that ties a row
to its explanation context. Service JSON may still expose an `evidence_ref`
compatibility dictionary, but in-process rows no longer carry an `EvidenceRef`
wrapper.

| Field | Tied to |
| --- | --- |
| `row_id` | Stable row id within the result |
| `digest` | Row claim digest |
| `closed_head_digest` | Digest of the closed head used for this row |

Invariants on a live row:

```python
assert row.row_id
assert row.digest
assert row.closed_head_digest
```

The digest fields are not the public explanation entry point. Use
`row.explain()` on the live row; row-local identity, stale detection, and durable
audit linking use `row_id`, `digest`, and `closed_head_digest`.

## 5. `Explanation` — derivation analysis

`Explanation` is a frozen envelope describing whether and how a
row's claim is supported. It is **terminal**: an Explanation has data
attributes only, no chainable `.explain()` method of its own. Read it by
branching on `status`, or read the computed `repr` property for deterministic
multi-line text.

The 4 `status` values:

| Status | Meaning | `evidence` | `failure_class` |
| --- | --- | --- | --- |
| `passed` | Derivation succeeded | `EvidenceGraph` | `None` |
| `failed` | Business failure: binding does not hold | `None` | one of 5 classes |
| `unsupported` | Engine technically cannot answer (non-business) | `None` | `None` |
| `invalid_request` | Input shape was rejected | `None` | `None` |

The 5 `failure_class` values (only when `status == "failed"`):

| Class | When |
| --- | --- |
| `no_matching_row` | Closed head matches no row in the result |
| `closed_head_false` | Closed head present, but underlying facts changed |
| `stale_row` | Row's view snapshot is no longer current |
| `row_not_in_result` | Row id not present in the linked result |
| `insufficient_closed_bindings` | Closed head is not fully closed for replay |

Protocol-enforced invariants:

- `status == "passed"` ⇔ `evidence is not None`
- `status == "failed"` ⇒ `failure_class` is set
- `status in {"unsupported", "invalid_request"}` ⇒ `errors` is non-empty
- `raw_kind is None` ⇒ `bound is None`

`Explanation` fields and computed properties:

| Field | Populated when | Purpose |
| --- | --- | --- |
| `status` | always | One of the 4 values above |
| `evidence` | `status == "passed"` | The `EvidenceGraph` derivation tree |
| `row` | `passed` (also possible on others) | The `EvaluateRow` being explained |
| `result_id` | always (required when passed) | Links to `EvaluateResult` |
| `failure_class` | `status == "failed"` | Diagnostic class |
| `checked_scope` | `failed` / `unsupported` | Replay context that was checked |
| `suggested_next_steps` | typically `failed` / `unsupported` | UX hint strings |
| `errors` | `unsupported` / `invalid_request` (non-empty) | `ErrorDTO` tuple with `.code` / `.message` |
| `warnings` | any status | Non-blocking `WarningDTO` tuple |
| `repr` | computed | Multi-line text for passed explanations and deterministic failed summaries; `None` for unsupported / invalid request |

Passed example:

```python
result = fg.eval.evaluate(rule, head=rule)
row = result.first()
e = row.explain()

assert e.status == "passed"
assert e.evidence is not None       # an EvidenceGraph
assert e.row is row
assert e.failure_class is None
assert e.errors == ()
assert e.repr is not None           # tuple[str, ...]
```

Failed example (state changed between `evaluate` and `explain`):

```python
result = fg.eval.evaluate(rule, head=rule)
row = result.first()
closed_head = row.close()

# Mutate the ledger so the closed head's facts no longer hold.
# (`fg.fields.set` writes to an unattached SDKStore; on a `FactGraph.attach(db, ...)`
# read-only runtime it raises `SDKStoreError` and you would mutate the underlying
# `Database` directly instead.)
fg.fields.set(User.name, alice, "Bob")

e = fg.eval.explain(rule, head=closed_head)

assert e.status == "failed"
assert e.failure_class == "closed_head_false"
assert e.evidence is None
assert e.repr[0] == "NOT concluded"
# UX hint for the caller
assert e.suggested_next_steps == (
    "Re-evaluate with a closed head that matches at least one result row.",
)
```

`row.explain()` is the row-bound 主路径; `fg.eval.explain(expr,
head=closed_head, ...)` is the advanced / cross-session manual path that
requires the caller to supply a fully closed head.

If the graph itself is malformed or its row/result metadata no longer matches
the explanation context, the normal user-facing outcome is
`Explanation(status="unsupported")` with an error code
`GRAPH_VALIDATION_FAILED`. A non-`EvidenceGraph` value returned by an internal
custom graph builder is a protocol contract violation and is not normal
application flow.

## 6. `EvidenceGraph` — complete row-evidence structure

When `status == "passed"`, `explanation.evidence` is an `EvidenceGraph`. This
section is the full DTO reference: the three nested dataclasses, the constant
enumerations, the 9 constructor checks and allowed graph shapes, the per-engine
variations, and a complete walkthrough showing what a user actually receives.

`EvidenceGraph` lives at `src/factgraph/audit/evidence_graph.py` and is the
shared cross-engine explainability representation that audit-layer consumers
read. It is part of the public read surface; **construct it via engine
adapters or protocol bridges, not by hand**.

`EvidenceGraph` is the **read-time, audit-layer** representation surfaced by
`row.explain()`. The kernel substrate also maintains an internal
`candidate_evidence_tree` (12-field summary + `node_kind` / `support_kind`
taxonomies) used by service / runtime-explain consumers. The two shapes
are intentionally distinct — `EvidenceGraph` is the public audit surface,
and `candidate_evidence_tree` is an advanced substrate not exposed
through the SDK. See `src/factgraph/audit/docs/02_evidence_graph.md` for
the audit-layer contract and `src/factgraph/audit/docs/03_audit_package_contract.md`
for the durable JSONL audit-package format that consumes both.

### 6.1 The three nested DTOs

`EvidenceGraph` is a frozen container of two frozen sub-types (`EvidenceNode`
and `EvidenceEdge`) plus three string-constant enumerations. All three classes
are importable from `factgraph.audit`:

```python
from factgraph.audit import (
    EvidenceGraph, EvidenceNode, EvidenceEdge,
    LAYOUT_TREE, LAYOUT_TIMELINE,
    NODE_CONCLUSION, NODE_PREMISE, NODE_SEED, NODE_RULE_EXPR, NODE_RULE, NODE_ATOM,
    EDGE_SUPPORTS, EDGE_DERIVES, EDGE_UPDATES, EDGE_DERIVED_BY, EDGE_USES,
    EDGE_HAS_ATOM, EDGE_SUPPORTED_BY,
)
```

#### `EvidenceGraph` (8 fields)

| Field | Type | Default | Role |
| --- | --- | --- | --- |
| `graph_id` | `str` | — | Stable cross-process graph identifier |
| `engine` | `str` | — | `"native"` / `"souffle"` / `"problog"` / `"pyreason"` |
| `root_node_id` | `str` | — | Root conclusion node id; must be in `nodes` |
| `nodes` | `tuple[EvidenceNode, ...]` | — | Frozen node tuple, unique `node_id`s |
| `edges` | `tuple[EvidenceEdge, ...]` | — | Frozen edge tuple, unique `edge_id`s |
| `support_kind` | `str` | — | See §6.3 per-engine table for the 5 shipped values |
| `layout_hint` | `str` | `"tree"` | One of `LAYOUT_TREE` / `LAYOUT_TIMELINE` |
| `metadata` | `Mapping[str, Any]` | `{}` | Row-result metadata bridge (per T8-A 14-key) |

#### `EvidenceNode` (7 fields)

| Field | Type | Default | Role |
| --- | --- | --- | --- |
| `node_id` | `str` | — | Within-graph stable identifier |
| `node_kind` | `str` | — | One of `NODE_CONCLUSION` / `NODE_PREMISE` / `NODE_SEED` / `NODE_RULE_EXPR` / `NODE_RULE` / `NODE_ATOM` |
| `component` | `str` | — | Component identity (`rule_id` / `pred_id` / `atom_id`) |
| `label` | `str` | — | Human-readable label |
| `value_summary` | `str` | — | Pre-rendered value text |
| `timestamp` | `int \| None` | `None` | Form 2 timeline index; always `None` for Form 1 |
| `engine_meta` | `Mapping[str, Any]` | `{}` | Per-engine namespaced debug fields |

#### `EvidenceEdge` (6 fields)

| Field | Type | Default | Role |
| --- | --- | --- | --- |
| `edge_id` | `str` | — | Within-graph stable identifier |
| `from_node_id` | `str` | — | Premise / child / downstream endpoint |
| `to_node_id` | `str` | — | Conclusion / parent / upstream endpoint |
| `edge_kind` | `str` | — | One of `EDGE_SUPPORTS` / `EDGE_DERIVES` / `EDGE_UPDATES` / `EDGE_DERIVED_BY` / `EDGE_USES` / `EDGE_HAS_ATOM` / `EDGE_SUPPORTED_BY` |
| `rule_label` | `str \| None` | `None` | Optional rule reference for the edge |
| `engine_meta` | `Mapping[str, Any]` | `{}` | Per-engine namespaced debug fields |

Edge direction is `from = premise/child/downstream`, `to = conclusion/parent/upstream` — read as **"from supports to"**.

#### Constants — three enumerations

```python
# Layout hints — graph shape
LAYOUT_TREE = "tree"            # Form 1 (native / Souffle / ProbLog)
LAYOUT_TIMELINE = "timeline"    # Form 2 (PyReason — future)

# Node kinds — what each point represents
NODE_CONCLUSION = "conclusion"  # The conclusion the graph proves
NODE_PREMISE = "premise"        # Intermediate premises
NODE_SEED = "seed"              # Ledger assertion witnesses (chain start)
NODE_RULE_EXPR = "rule_expr"    # RuleExpr composition layer
NODE_RULE = "rule"              # Rule occurrence
NODE_ATOM = "atom"              # Rule-body atom/check

# Edge kinds — relation between two nodes
EDGE_SUPPORTS = "supports"      # Form 1: premise -> conclusion
EDGE_DERIVES = "derives"        # ProbLog provenance: seed/premise -> derived
EDGE_UPDATES = "updates"        # Form 2 reserved (PyReason temporal — future)
EDGE_DERIVED_BY = "derived_by"  # rule_expr -> conclusion
EDGE_USES = "uses"              # rule -> rule_expr
EDGE_HAS_ATOM = "has_atom"      # atom -> rule
EDGE_SUPPORTED_BY = "supported_by"  # seed/proof node -> atom
```

### 6.2 Constructor checks and graph-shape guarantees

The three dataclasses are frozen; their constructors enforce 9 checks at
construction time. Violating any raises `ValueError`:

1. **`layout_hint` enumeration** — must be one of `LAYOUT_TREE` / `LAYOUT_TIMELINE`.
2. **`node_kind` enumeration** — must be one of the six node constants above.
3. **`edge_kind` enumeration** — must be one of the seven edge constants above.
4. **Unique node ids** — `nodes` must not contain duplicate `node_id` values.
5. **Unique edge ids** — `edges` must not contain duplicate `edge_id` values.
6. **Root in nodes** — `root_node_id` must equal some `node.node_id`.
7. **Edge endpoints in nodes** — every edge's `from_node_id` and `to_node_id` must equal some `node.node_id`.
8. **DAG (cycle-free)** — DFS over the reverse-adjacency graph rejects any cycle.
9. **Mapping immutability** — `engine_meta` and `metadata` are wrapped in `MappingProxyType`; mutation attempts raise `TypeError`.

Allowed graph shapes and runtime conventions (not checked at construction):

- **Case convergence allowed** — repeated support for the same assertion may converge on a single `NODE_SEED` rather than duplicating it. This is a permitted shape, not a required one; producers may also choose to duplicate seeds.
- **Renderer input guard** — `render_evidence_graph_html(...)` accepts a constructed `EvidenceGraph` only; raw dicts and duck-typed stand-ins are rejected.
- **Large graph warning** — more than 250 nodes or more than 500 edges emits a warning banner. The reference renderer still renders the graph; it does not truncate or reject solely because the graph is large.

### 6.3 Per-engine variations

Each engine produces a differently-shaped `EvidenceGraph`. The triplet
`support_kind` + `layout_hint` + primary `edge_kind` is the canonical
identifier:

| Engine | `support_kind` | `layout_hint` | Primary `edge_kind` | Form | Status |
| --- | --- | --- | --- | --- | --- |
| Native | `"native_binding_v1"` | `"tree"` | `EDGE_DERIVED_BY` / `EDGE_USES` / `EDGE_HAS_ATOM` / `EDGE_SUPPORTED_BY` | layered Form 1 | shipped |
| Souffle | `"souffle_witness_v1"` | `"tree"` | `EDGE_DERIVED_BY` / `EDGE_USES` / `EDGE_HAS_ATOM` / `EDGE_SUPPORTED_BY` | layered Form 1 | shipped |
| ProbLog | `"problog_provenance_v1"` | `"tree"` | row shell + `EDGE_DERIVES` trace | layered row provenance | shipped |
| PyReason (adapter-only) | `"pyreason_provenance_v1"` | `"timeline"` | `EDGE_UPDATES` | Form 2 sketch | advanced / row-level deferred |
| Detached or unaligned row | `"evaluate_row"` | `"tree"` | `EDGE_DERIVED_BY` / `EDGE_USES` | minimal rule shell fallback | shipped |

The next three subsections give the concrete graph shape per engine.

#### 6.3.1 Native and Souffle — layered Form 1

For native or Souffle passed rows with support context, this graph now exposes
the current Form 1 shape:

```text
NODE_SEED --supported_by--> NODE_ATOM --has_atom--> NODE_RULE --uses--> NODE_RULE_EXPR --derived_by--> NODE_CONCLUSION
```

The root `NODE_CONCLUSION` represents the row claim. `NODE_RULE_EXPR` and
`NODE_RULE` expose the rule-expression and rule occurrence layers. `NODE_ATOM`
nodes represent the selected native or Souffle support atoms/checks. `NODE_SEED`
nodes represent ledger assertion witnesses. If the same assertion id supports
multiple atoms in one row graph, the graph reuses one `NODE_SEED` and adds
multiple `supported_by` edges.

For OR-shaped native or Souffle evaluation, the graph is
**winning-path-only**: it shows the selected successful branch, not every
possible or failed branch. The root metadata exposes that boundary with
`alternative_paths.mode` set to
`"winning_path_only"`. Other engine metadata fields are implementation
details; do not write SDK code that depends on their full shape.

#### 6.3.2 ProbLog — layered row shell with preserved `EDGE_DERIVES` trace

ProbLog passed rows now produce a row-level shell and preserve the adapter proof
trace below the shell's synthetic row atom. The row shell uses
`derived_by` / `uses` / `has_atom` / `supported_by`; the proof-trace subtree
still uses `derives` edges:

```text
NODE_SEED --derives--> NODE_PREMISE --derives--> NODE_CONCLUSION(trace root)
       --supported_by--> NODE_ATOM --has_atom--> NODE_RULE --uses--> NODE_RULE_EXPR --derived_by--> NODE_CONCLUSION(row root)
```

The exact frame hierarchy comes from the ProbLog proof trace. Top-level graph
metadata still mirrors the same row/result audit context. ProbLog adapter
metadata is split across nodes and edges: the root node carries `trace_summary`
and `uncertainty_projection` under `root.engine_meta["problog"]`, and each edge
carries per-edge details under `edge.engine_meta["problog"]["trace_edge"]`.

#### 6.3.3 PyReason — adapter-level only; row-result is the fallback

Rows without native or Souffle support context, including manually
constructed/detached rows, keep a minimal row shell with `NODE_CONCLUSION`,
`NODE_RULE_EXPR`, and `NODE_RULE`. They do not fabricate `NODE_ATOM` with
`atom_status="support"` unless real atom evidence exists. ProbLog passed rows
use the provenance graph described above. PyReason and other unaligned adapter rows may still use
fallback or adapter-specific graph shapes until their row-level alignment lands.

For PyReason specifically, inference, bounds, and temporal materialization are
available through the PyReason evaluation path, but rich row-level temporal
evidence is deferred to a future Form 2 design cycle. Today, PyReason rows that
do not have row-level aligned provenance use the safe single-`NODE_CONCLUSION`
fallback graph. Treat that graph as a row anchor, not as a timeline and not as a
proof of timestep-by-timestep state changes. Advanced users who already have a
PyReason trace payload can build an adapter-level timeline graph with
`factgraph.adapters.pyreason.provenance.pyreason_trace_to_evidence_graph(...)`;
that helper is not the main quickstart path and may evolve with the future
Form 2 design.

### 6.4 Current boundaries

- PyReason row-level Form 1 alignment is future work.
- Aggregate count-only envelopes are future work; current native non-fact
  checks do not expose the matched-count contributor envelope.
- Failed graph, why-not, and counterfactual trees are future evidence tracks.
- Match witness / assertion-returning output is a future match/evidence seam.
- Cross-row seed de-duplication is not a v1 contract; each row explanation owns
  its graph.
- Session logs, `/interactions/{sessionID}`, signatures, ACL, `x-evidence-key`,
  salience, and impact remain outside the sessionless v1 audit channel.
- Native and Souffle Form 1 row graphs use the layered edge kinds. ProbLog row
  provenance graphs use a layered row shell plus preserved `EDGE_DERIVES` trace
  edges. `EDGE_UPDATES` remains reserved for PyReason / Form 2 / temporal
  engine paths.
- `dag` layout and `rule_fire` node kind are not in v1 scope.

### 6.5 Complete walkthrough

A passing row gives you a real `EvidenceGraph`. This is a full read-side
walkthrough:

```python
from factgraph.audit import (
    EvidenceGraph,
    NODE_CONCLUSION, NODE_PREMISE, NODE_SEED, NODE_RULE_EXPR, NODE_RULE, NODE_ATOM,
    EDGE_SUPPORTS, EDGE_DERIVES, EDGE_DERIVED_BY, EDGE_USES, EDGE_HAS_ATOM, EDGE_SUPPORTED_BY,
)

result = fg.eval.evaluate(rule, head=rule)
row = result.first()
explanation = row.explain()

assert explanation.status == "passed"
graph = explanation.evidence
assert isinstance(graph, EvidenceGraph)

# 1. Graph-level identity and envelope
print(graph.graph_id)         # format: f"{result.result_id}:{row.row_id}"
print(graph.engine)           # "native" / "souffle" / "problog" / "pyreason"
print(graph.support_kind)     # one of the 5 values in the §6.3 table
print(graph.layout_hint)      # "tree" (Form 1) or "timeline" (Form 2)
print(f"nodes={len(graph.nodes)} edges={len(graph.edges)}")

# 2. Find the root conclusion
root = next(n for n in graph.nodes if n.node_id == graph.root_node_id)
assert root.node_kind == NODE_CONCLUSION
print(f"Conclusion: {root.label} = {root.value_summary}")

# 3. Walk the support / provenance chain
#    Edge direction: from = premise/seed, to = conclusion/premise
node_by_id = {n.node_id: n for n in graph.nodes}
for edge in graph.edges:
    src = node_by_id[edge.from_node_id]
    dst = node_by_id[edge.to_node_id]
    print(f"  {edge.edge_kind}: {src.label} -> {dst.label}")

# 4. List the seed assertions
for node in graph.nodes:
    if node.node_kind == NODE_SEED:
        print(f"  Seed: {node.component} -> {node.label}")

# 5. Per-engine namespaced debug metadata is on nodes/edges, not on the
#    top-level graph. ProbLog row provenance splits the placement:
#    - root node carries trace_summary + uncertainty_projection under
#      root.engine_meta["problog"]
#    - every edge carries per-edge trace details under
#      edge.engine_meta["problog"]["trace_edge"]
if graph.engine == "problog":
    root_problog = root.engine_meta.get("problog", {})
    if root_problog:
        print(f"Root ProbLog summary/projection: {root_problog}")
    for edge in graph.edges:
        edge_problog = edge.engine_meta.get("problog", {})
        if edge_problog:
            print(f"  edge ProbLog trace: {edge_problog}")
```

Native engine sample output:

```text
graph_id: evalr_v1:abc...:run_v1:def...
engine: native
support_kind: native_binding_v1
layout_hint: tree
nodes=4 edges=3
Conclusion: user:tag = ("alice", "engineer")
  supports: User(u-1).tag_seed -> rule.tags_from_seed
  supports: rule.tags_from_seed -> user:tag
  Seed: User.tag_seed -> "engineer"
```

What changes per engine:

- **Native / Souffle**: `edge_kind` is `supports`; `support_kind` is the witness id; no `timestamp` on nodes.
- **ProbLog**: `edge_kind` is `derives`; `support_kind` is `problog_provenance_v1`; ProbLog summary/projection metadata is on the root node under `root.engine_meta["problog"]` (with `trace_summary` and `uncertainty_projection`), and per-edge trace details are on edges under `edge.engine_meta["problog"]["trace_edge"]`. The graph's top-level `metadata` continues to carry the row/result audit context.
- **PyReason (row-result)**: a single `NODE_CONCLUSION`, no edges; `support_kind` is `"evaluate_row"`. The rich adapter-level timeline graph (`pyreason_trace_to_evidence_graph(...)`) is not returned by `row.explain().evidence` today — see §6.3.3.
- **Detached / no support context**: same fallback shape as PyReason row-result; one conclusion node, no edges, `support_kind="evaluate_row"`.

For deeper traversal helpers and renderer integration, see the
`src/factgraph/audit/` module docs.

## 7. Stability of `Inference` and `Case`

Application `Rule` (built via `build_application_rule(...)`) plus
`RuleExpr` composition is the **preferred read-pattern surface for new
code** in v0.2. `Inference` and `Case` (legacy DSL) remain available as
the **compatibility surface**: they produce the same `EvaluateResult` /
`EvaluateRow` / `Explanation` shapes documented in §§1–5 and
share the same lower evaluation pipeline (`SemanticsProfile`, engine
adapters, evidence runtime).

The design has committed to retiring `Case` from user-facing layers and
folding `Inference` into a `RuleExpr`-based runtime entry in a later
cycle:

> 在新 user-facing 表达层 (`Rule` / `RuleExpr`),`Case` 不出现 …
> 与 Inference 关系: 新设计 = **解耦** — Inference 是运行时入口,接受 RuleExpr
> — `workflow/design/design-points/archive/rule-expression-and-proof-attempt.zh.md` §3.10

Until that migration spec is locked by a future blueprint:

- No `DeprecationWarning` is raised; no public symbol is removed.
- `Inference(..., when=[Case([...], id="...")])` remains stable for
  current use and continues to be exercised by tests and adapters.
- `Case` is not a stand-alone user-facing concept — it is the OR-body
  primitive inside `Inference` only. `build_application_rule(...)`
  rejects `Case` because application `Rule` bodies are AND-only;
  multi-pattern composition belongs at the `RuleExpr` level (`&` / `|`
  operators on application `Rule` values).
- New quickstart examples and SDK docs introduce application `Rule`
  first; `Inference` is shown for cases that need the legacy
  `Case`-list OR-body syntax (e.g. for compatibility with engine
  adapters that historically consumed it).

## A note on naming collisions

`result[i].explain()` is the subscript form of `row.explain()` — the dot is
on the row obtained by indexing, not on `result` or on the returned
`Explanation`. `EvaluateResult` itself has no `.explain()` method, and
`Explanation` itself has no `.explain()` method either. Only `EvaluateRow`
and `fg.eval` expose the explanation entry points.

## Cross-references

- For the `fg.eval` namespace surface, see [namespace-map.md](namespace-map.md).
- For Rule and Inference construction, see [rules-and-inferences.md](rules-and-inferences.md).
- For semantics profiles (`raw_kind` / `bound` origination), see [semantics.md](semantics.md).
