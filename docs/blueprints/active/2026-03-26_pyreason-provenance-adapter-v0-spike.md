# Task Blueprint: PyReason Provenance Adapter V0 Spike

- Status: scoped
- Created: 2026-03-26
- Parent: [2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md](./2026-03-22_ecss-domain-validation-and-souffle-provenance-poc.md)
- Related:
  - [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md) §ADR-8 (adapter-local before core)
  - [Souffle provenance adapter v0](../archive/2026-03-22_souffle-provenance-adapter-v0.md)

## 1. Goal

Verify that factpy can minimally integrate PyReason as a second reasoning engine, and that its explanation trace (`get_rule_trace`) can be stably extracted as an adapter-local carrier — providing the second real constraint source for a future ProofNode v1 decision.

## 2. Non-Goals

- No `ProofNode` v1 design or implementation
- No changes to `core/` contracts
- No audit package integration (`provenance_trees.jsonl` stays Souffle-only)
- No static HTML rendering of PyReason traces
- No complete graph modeling framework
- No multi-scenario productized demo
- No SDK Rule DSL integration for PyReason syntax

## 3. Background

PyReason uses Generalized Annotated Logic Programs (GAPs) over NetworkX graphs with:
- **Interval bounds** `[lower, upper]` instead of Boolean or probability
- **Temporal timesteps** (`<-1` = effect after 1 step)
- **Open-world assumption** (absent fact = `[0,1]` unknown, not false)
- **Event-log trace** (pandas DataFrame), NOT proof trees

This is fundamentally different from Souffle (deterministic, closed-world, proof trees) and provides maximum contrast for evaluating whether a unified provenance abstraction is viable.

## 4. Key Discovery from Research

PyReason's `get_rule_trace(interpretation)` returns two pandas DataFrames:

**nodes_trace columns:**
| Time | Fixed-Point-Op | Node | Label | Old Bound | New Bound | Occurred Due To | Clause-1 | Clause-2 | ... |
|------|---------------|------|-------|-----------|-----------|-----------------|----------|----------|-----|

**This is NOT a proof tree.** It's a chronological event log of every bound change during reasoning. Each row records: which node changed, what predicate, old/new interval, which rule caused it, and which clause groundings.

Implications for ProofNode:
- Cannot assume all engines produce trees
- A unified abstraction must accommodate both "proof tree" (Souffle) and "event log" (PyReason)
- Or: the unified layer is at a higher level (e.g., "per-candidate provenance payload" with engine-specific shape)

## 5. Deliverables

### D1: Minimal PyReason example (`examples/pyreason_spike.py`)

A standalone script (no notebook) that:
1. Builds a small NetworkX graph (3-5 nodes, 3-5 edges)
2. Defines 1-2 rules with temporal propagation (`<-1`)
3. Adds 1-2 initial facts with interval bounds
4. Runs `pr.reason(timesteps=N)` with `atom_trace=True`
5. Prints the interpretation dict and rule trace DataFrames
6. Demonstrates interval propagation over time steps

### D2: Adapter-local trace carrier (`adapters/pyreason/provenance.py`)

New module containing:

```python
@dataclass(frozen=True)
class PyReasonTraceEventV0:
    """Single row from PyReason's rule trace. Adapter-local, NOT a core contract."""
    time: int
    fixpoint_op: int
    component: str           # node or "source->target" for edges
    component_type: str      # "node" or "edge"
    label: str               # predicate name
    old_bound: tuple[float, float]
    new_bound: tuple[float, float]
    occurred_due_to: str     # rule name or "fact"
    clause_groundings: tuple[str, ...]  # Clause-1, Clause-2, ... values

@dataclass(frozen=True)
class PyReasonTraceV0:
    """Complete trace from a PyReason reasoning run."""
    timesteps: int
    node_events: tuple[PyReasonTraceEventV0, ...]
    edge_events: tuple[PyReasonTraceEventV0, ...]
```

Key design decisions:
- Named `TraceEvent`, not `ProofNode` — honest about the data shape
- Adapter-local (in `adapters/pyreason/`), not in `core/`
- Frozen dataclasses, same pattern as `SouffleProofNodeV0`

### D3: Serialization helper

```python
def parse_pyreason_trace(interpretation, nodes_trace_df, edges_trace_df) -> PyReasonTraceV0:
    """Convert PyReason DataFrames to adapter-local trace carrier."""

def pyreason_trace_to_dict(trace: PyReasonTraceV0) -> dict[str, Any]:
    """Serialize to JSON-friendly dict."""
```

### D4: Adapter doc + comparison section (`src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`)

Follows existing adapter docs convention (`adapters/docs/01_souffle_adapter.md`, `02_problog_adapter.md`). Contains:
- PyReason adapter overview (graph input, interval semantics, temporal steps)
- Trace carrier shape (`PyReasonTraceEventV0` / `PyReasonTraceV0`)
- §Souffle vs PyReason provenance comparison section:
  - Shape: tree vs event log
  - Temporal: none vs native timesteps
  - Values: Boolean vs interval
  - World assumption: closed vs open
  - Fields that could unify across engines
  - Fields that are engine-specific and should stay in annotations
  - Updated recommendation on ProofNode v1 timing

## 6. Implementation Plan

```
Step 1: Install + verify PyReason
  - pip install pyreason (manual prerequisite, not added to pyproject.toml)
  - Verify import works on Python 3.10
  - Run a minimal 3-node example
  - NOTE: pyreason is a spike-only dependency; repo pyproject.toml is NOT modified.
    Acceptance does not require clean-env/CI reproducibility for this spike.

Step 2: Build pyreason_spike.py
  - Graph with propagation scenario
  - atom_trace=True
  - Print interpretation + rule trace

Step 3: Create adapters/pyreason/provenance.py
  - PyReasonTraceEventV0, PyReasonTraceV0
  - parse_pyreason_trace
  - pyreason_trace_to_dict

Step 4: Write adapter doc (src/factpy_kernel/adapters/docs/03_pyreason_adapter.md)
  - Includes Souffle vs PyReason provenance comparison as a section

Step 5: Tests (adapter-local only)
  - Trace parsing from synthetic DataFrame
  - Serialization round-trip
  - NOT integration tests with full factpy pipeline
```

## 7. Acceptance Criteria

1. `python examples/pyreason_spike.py` runs successfully on current environment (Python 3.10, with `pip install pyreason` as manual prerequisite)
2. `nodes_trace` / `edges_trace` DataFrames are extracted and printed
3. `PyReasonTraceV0` can be serialized to JSON and deserialized
4. Comparison doc explicitly states "PyReason provenance is an event log, not a proof tree"
5. Comparison doc gives updated recommendation on whether to proceed to ProofNode v1
6. No changes to any file outside `adapters/pyreason/`, `adapters/docs/`, `examples/`, `docs/`, and `tests/`. `pyproject.toml` is NOT modified — pyreason is a manual install prerequisite for this spike only
7. Existing 253 tests unaffected

## 8. Boundary Constraints

- **Adapter-local only**: all new code in `adapters/pyreason/` or `examples/`
- **No core contract changes**: no new fields on `SupportArtifact`, `CandidateSet`, or audit package
- **No SDK integration**: PyReason rules are written in PyReason syntax, not factpy Rule DSL
- **Coexistence**: Souffle adapter completely unaffected
- **NOT frozen**: `PyReasonTraceEventV0` field shapes may change based on spike findings

## 9. Outcome

Fill after implementation:

- Final result:
- Deviations from blueprint:
- Updated ProofNode v1 recommendation:
- Archive notes:
