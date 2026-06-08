# Application Explain Module

- Scope: `src/factgraph/application/explain`
- Last updated: 2026-06-08
- Audience: developers building explain consumers, adapter writers, and SDK layer maintainers

---

## 1. Scope

`factgraph.application.explain` owns the **paths-model evidence tree types** and the
**native prober**. It is the canonical implementation site for all explain-layer
DTOs. The `factgraph.audit.evidence_graph` module is a thin re-export from this
package.

Files:

- `evidence_tree.py` — all frozen DTO types + serialization
- `prober.py` — `probe_native(...)` + `ProbeEnv`
- `__init__.py` — flat re-export of everything in `__all__`

---

## 2. Responsibilities

### 2.1 Core DTO types (`evidence_tree.py`)

#### `EvidenceGraph`

Top-level explain output. Contains one or more proof paths:

```python
@dataclass(frozen=True)
class EvidenceGraph:
    graph_id: str
    engine: str
    layout_hint: str                              # LAYOUT_TREE | LAYOUT_TIMELINE
    subject_binding: Mapping[str, Any]
    paths: tuple[EvidenceTree | EvidenceTimeline, ...]
    certainty: Certainty | None
    metadata: Mapping[str, Any]
```

`paths` replaces the old `nodes`/`edges`/`root_node_id`/`support_kind` fields.
Each element of `paths` is an independent derivation path.

Constants: `LAYOUT_TREE = "tree"`, `LAYOUT_TIMELINE = "timeline"`.

#### `EvidenceTree`

A proof-tree path through one derivation branch:

```python
@dataclass(frozen=True)
class EvidenceTree:
    tree_id: str
    status: str                                   # "holds" | "fails" | "not_reached"
    rules: tuple[EvidenceRule, ...]
    joins: tuple[EvidenceJoin, ...]
    certainty: Certainty | None
    metadata: Mapping[str, Any]
```

#### `EvidenceTimeline`

A timeline path for temporal engines (PyReason):

```python
@dataclass(frozen=True)
class EvidenceTimeline:
    timeline_id: str
    status: str
    events: tuple[...]
    certainty: Certainty | None
    metadata: Mapping[str, Any]
```

#### `EvidenceRule`

One rule occurrence within a tree. Carries the atoms (conditions) of that rule:

```python
@dataclass(frozen=True)
class EvidenceRule:
    occurrence_alias: str
    rule_id: str
    role: str                                     # "head" | "body"
    status: str                                   # "holds" | "fails" | ...
    ports: Mapping[str, Any]                      # port_name → bound value
    atoms: tuple[EvidenceAtom, ...]
```

#### `EvidenceAtom`

A single condition atom. The `form` field describes the syntactic shape;
`verdict` describes the runtime outcome:

```python
@dataclass(frozen=True)
class EvidenceAtom:
    form: AtomForm                                # Fact | Compare | Builtin | Aggregate
    verdict: Verdict                              # Holds | Fails | NotReached
    atom_id: str
    repr_text: str | None                         # baked renderer hint, or None
```

#### `EvidenceJoin`

Cross-path join link (future; currently always empty in practice).

#### `EvidenceProbeResult`

Output of `probe_native(...)`:

```python
@dataclass(frozen=True)
class EvidenceProbeResult:
    paths: tuple[EvidenceTree, ...]
    certainty: Certainty | None
```

---

### 2.2 AtomForm types

| Type | Fields | Meaning |
|---|---|---|
| `Fact(predicate, terms)` | `predicate: str`, `terms: tuple[BoundVar \| Const, ...]` | Predicate match condition |
| `Compare(op, left, right)` | `op: str`, `left`, `right: BoundVar \| Const` | Comparison filter |
| `Builtin(kind, operands)` | `kind: str`, `operands: tuple` | Built-in operation |
| `Aggregate(kind, body_terms, head_terms)` | `kind: str`, `body_terms`, `head_terms` | Aggregation (count/sum/etc.) |

Term types:
- `BoundVar(name, value, bound_by)` — a bound variable; `name` includes the `$` prefix; `value` is the resolved runtime binding
- `Const(value)` — a literal constant

---

### 2.3 Verdict types

| Type | Fields | Meaning |
|---|---|---|
| `Holds(certainty, support)` | `certainty: Certainty`, `support: tuple[Source, ...]` | Condition satisfied |
| `Fails(certainty)` | `certainty: Certainty` | Condition not satisfied |
| `NotReached(blocked_by)` | `blocked_by: str \| None` | Not evaluated (dependency not bound) |

`Certainty(lower, upper, kind)` carries a probability interval. `BOOLEAN_CERTAINTY = Certainty(1.0, 1.0, "boolean")` is used for native/souffle deterministic paths.

`Source(ref, field, value, meta)` carries a ledger or trace reference that backs a `Holds` verdict.

`PortRef(rule_occurrence_alias, port_name)` identifies a binding source by rule + port.

---

### 2.4 Serialization

```python
evidence_graph_to_dict(graph: EvidenceGraph) -> dict[str, Any]
evidence_graph_from_dict(d: dict[str, Any]) -> EvidenceGraph
```

Round-trip helpers for durable storage and wire transfer.
These are re-exported from `factgraph.application.explain` and from `factgraph.audit.evidence_graph`.

---

### 2.5 Native prober (`prober.py`)

```python
def probe_native(
    plan: Any,                                    # CompiledDerivationPlan
    bindings: Mapping[str, Any] | None,           # closed head bindings
    view_facts: Mapping[str, list[tuple[Any, ...]]],
    schema_index: Any | None = None,              # ApplicationSchemaIndex for repr_text
) -> EvidenceProbeResult:
```

Probes every normalized OR branch of a native plan against the given `view_facts` without short-circuiting. Returns all branches as `EvidenceTree` paths — including failing ones. Used by S5's `_explain_live_row` for the `closed_head_false` status path and by `check_derivation_binding` internally.

`ProbeEnv` is the mutable traversal environment used internally by `probe_native`. It is exposed in `__all__` for adapter/test use.

---

### 2.6 `repr_text` baking (S4 invariant)

For `EvidenceAtom` objects produced by the prober, `repr_text` is baked at construction time via `_bake_repr_text(form, schema_index)`:

- `Compare` / `Builtin` atoms: always non-None (default renderer table)
- `Fact` atoms with schema: uses `Field.repr` template if available; falls back to `_fact_fallback_repr`
- `Fact` atoms without schema: `_fact_fallback_repr(form)` uses `BoundVar.value` to produce `"predicate(val1, val2)"`
- `Aggregate` and other atoms: `repr_text = None`

**INV-reprtext-fact-always**: after S4, `repr_text` is always non-None for `Fact`/`Compare`/`Builtin` atoms.

---

## 3. Non-responsibilities

- This module does not own `Explanation` or `EvaluateResult` protocol DTOs (those are in `protocol/evaluate_result.py`)
- This module does not own the schema IR or `render_entity_repr` (those are in `schema_runtime.py`)
- This module does not own the ProbLog / PyReason / Souffle adapter converters (those are in `adapters/*`)
- This module does not contain the SDK-layer `SDKStore.explain()` surface
- `EvidenceTimeline` events have no behavior-level spec in v1; event shape is adapter-defined

---

## 4. Limitations & Compatibility

- `EvidenceGraph.paths` is the only layout. The old `nodes`/`edges`/`root_node_id`/`support_kind` fields were removed in S3 (2026-06-08); `factgraph.audit.evidence_graph` no longer exports `EvidenceNode`, `EvidenceEdge`.
- `EvidenceJoin` is a reserved forward-compat type; current prober always produces `joins=()`.
- `probe_native` does not accept non-native plans; plan is assumed to be a `CompiledDerivationPlan` from the native engine.
- `EvidenceProbeResult` is not the same as `EvidenceGraph`; callers wrap it with `EvidenceGraph(paths=probe_result.paths, ...)`.
- `evidence_graph_from_dict` / `evidence_graph_to_dict` are round-trip only; they do not perform semantic validation beyond structural shape.

---

## 5. Test Entry Points

```bash
# Evidence graph DTO shape + serialization
python -m pytest tests/test_audit_evidence_graph.py
python -m pytest tests/test_audit_evidence_graph_render.py  # walk_evidence renderer

# Adapter evidence graph output (paths model)
python -m pytest tests/test_problog_evidence_graph.py
python -m pytest tests/test_pyreason_evidence_graph.py
python -m pytest tests/test_souffle_evidence_graph.py

# explain dispatch + invariant (via evaluate_result surface)
python -m pytest tests/application/protocol/test_evaluate_result_dtos.py
python -m pytest tests/application/protocol/test_explanation_render.py
```

---

## 6. Related Historical Blueprints

- `workflow/blueprints/archive/2026-06-08_explain-layer-s3-prober.md` — prober main body + paths model (S7 merged in)
- `workflow/blueprints/archive/2026-06-08_explain-layer-s4-repr-baking.md` — `repr_text` baking + `_fact_fallback_repr`
- `workflow/blueprints/active/2026-06-08_explain-layer.md` — parent program (S0–S6 overview)
