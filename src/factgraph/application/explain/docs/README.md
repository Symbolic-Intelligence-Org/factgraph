# Application Explain Module

- Scope: `src/factgraph/application/explain`
- Last updated: 2026-06-09
- Audience: developers building explain consumers, adapter writers, and SDK layer maintainers

---

## 1. Scope

`factgraph.application.explain` owns the paths-model evidence tree DTOs and the
native prober. S3 introduces the model and the standalone `probe_native(...)`
engine. `Explanation` wiring, adapter dispatch, and renderer baking are later
slices.

Files:

- `evidence_tree.py` — frozen DTO types for `EvidenceGraph`, `EvidenceTree`,
  `EvidenceRule`, `EvidenceAtom`, verdicts, atom forms, and joins
- `prober.py` — `probe_native(...)` and `ProbeEnv`
- `__init__.py` — re-export surface for application-layer callers and tests

---

## 2. DTO Shape

`EvidenceGraph.paths` is the planned top-level shape. Each path is an
`EvidenceTree` (native/proof engines) or an `EvidenceTimeline` (temporal engines).
S3 does not yet wire this into `Explanation`.

The core tree types are:

- `EvidenceTree(tree_id, status, rules, joins, certainty, metadata)`
- `EvidenceRule(occurrence_alias, rule_id, role, status, ports, atoms)`
- `EvidenceAtom(form, verdict, atom_id, repr_text=None, negated=False, timestep=None)`
- `EvidenceJoin(left, right, status, join_id)`

`role` is either `"head"` or `"body"`. A tree produced by the native prober must
include a separate head rule and one body rule per real `RuleExpr` occurrence.

`Verdict` is one of:

- `Holds(certainty=BOOLEAN_CERTAINTY, support=())`
- `Fails(certainty=BOOLEAN_CERTAINTY)`
- `NotReached(blocked_by=...)`

`NotReached` is reserved for direct unbound-variable dependencies. It is not a
generic “previous atom failed” marker.

---

## 3. Native Prober

```python
def probe_native(
    plan: RuleExprLoweringPlan,
    bindings: Mapping[str, Any] | None,
    view_facts: Mapping[str, Sequence[tuple[Any, ...]]],
    schema_index: object | None = None,
) -> EvidenceProbeResult:
```

S3 consumes `RuleExprLoweringPlan`, not only a flat compiled `where` body. The
lowering plan carries the structure needed for faithful explanation:

- `occurrence_map` and branch `occurrence_aliases` become body `EvidenceRule`
  entries with real occurrence aliases.
- `head_binding` becomes the separate `EvidenceRule(role="head")`.
- `RuleExprJoinMaterialization` becomes `EvidenceJoin`; materialized join atoms
  are evaluated but are not rendered as ordinary body atoms.

The prober keeps a tuple of candidate environments per branch. Bind-producing
atoms expand every current environment; an atom holds if at least one next
environment survives. This prevents the v1 bug where the first failing witness
could hide a later successful witness.

---

## 4. Slice Boundaries

- S3 leaves `EvidenceAtom.repr_text` as `None`; S4 owns renderer baking.
- S3 does not connect `Explanation.evidence`; S5 owns native passed/failed wiring.
- S3 does not dispatch Souffle, ProbLog, or PyReason rich evidence; S6 owns that.
- The legacy `factgraph.audit.evidence_graph` module is not rewritten in S3.

---

## 5. Tests

```bash
PYTHONPATH=src python -m unittest tests.application.explain.test_prober
```

The focused S3 tests lock:

- G1 monotonic witness behavior (`p=[(2,)]` and `p=[(1,), (2,)]` both hold)
- G2 shape preservation (head rule, real body occurrence aliases, non-empty joins)
- OR branches are all returned as paths
- `NotReached` is only emitted for unbound dependencies
