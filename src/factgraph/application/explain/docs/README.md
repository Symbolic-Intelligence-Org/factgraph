# Application Explain Module

- Scope: `src/factgraph/application/explain`
- Last updated: 2026-06-10
- Audience: developers building explain consumers, adapter writers, SDK layer maintainers, and test authors

---

## 1. Scope

`factgraph.application.explain` owns the paths-model evidence DTOs and the
native prober. The module is the canonical application-layer shape for rich
explanation evidence.

Files:

- `evidence_tree.py` — frozen DTO types for `EvidenceGraph`, `EvidenceTree`,
  `EvidenceTimeline`, `EvidenceRule`, `EvidenceAtom`, verdicts, atom forms, and
  joins.
- `prober.py` — `probe_native(...)`, `ProbeEnv`, native atom probing, row
  anchoring, and native `repr_text` baking.
- `__init__.py` — re-export surface for application-layer callers and tests.

The legacy flat-DAG evidence model (`EvidenceNode`, `EvidenceEdge`,
`root_node_id`) is gone from production explain paths. The audit namespace is a
thin compatibility facade over the paths model.

---

## 2. DTO Shape

`EvidenceGraph.paths` is the top-level evidence shape. Each path is either:

- `EvidenceTree` for native/Souffle/ProbLog style proof trees; or
- `EvidenceTimeline` for temporal engines such as PyReason.

Core tree DTOs:

- `EvidenceTree(tree_id, status, rules, joins, certainty, metadata)`
- `EvidenceRule(occurrence_alias, rule_id, role, status, ports, atoms)`
- `EvidenceAtom(form, verdict, atom_id, repr_text, negated=False, timestep=None)`
- `EvidenceJoin(left, right, status, join_id)`

`role` is either `"head"` or `"body"`. Native trees include a separate head
rule and one body rule per real `RuleExpr` occurrence.

`Verdict` is one of:

- `Holds(certainty=BOOLEAN_CERTAINTY, support=())`
- `Fails(certainty=BOOLEAN_CERTAINTY)`
- `NotReached(blocked_by=...)`

`NotReached` is reserved for direct unbound-variable dependencies. It is not a
generic "previous atom failed" marker. After an upstream failure, the prober may
still compute downstream verdicts from the last row-anchored prefix
environment, but it does not resurrect the failed branch's candidate envs.

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

The prober consumes `RuleExprLoweringPlan`, not only a flat compiled `where`
body. The lowering plan carries the structure needed for faithful explanation:

- `occurrence_map` and branch `occurrence_aliases` become body `EvidenceRule`
  entries with real occurrence aliases.
- `head_binding` becomes the separate `EvidenceRule(role="head")`.
- `RuleExprJoinMaterialization` becomes `EvidenceJoin`; materialized join atoms
  are evaluated but are not rendered as ordinary body atoms.

The prober keeps a tuple of candidate environments per branch. Bind-producing
atoms expand every current environment; an atom holds if at least one next
environment survives. This prevents first-witness short-circuit bugs where a
failed witness hides a later successful witness.

SDK row explanations seed the prober with lowered seed variables derived from
the same lowering plan. This covers inline, projection, and external heads, plus
branch-specific aliases for OR and join-heavy rule expressions. The seed builder
lives outside this module, but `probe_native(...)` depends on receiving the
lowered variable names it actually evaluates.

---

## 4. Repr Text

`repr_text` is baked during native probing. The prober uses schema metadata when
available and falls back to stable default text otherwise.

Fact atoms:

- `PredicateInfo.repr` templates support `%CLS`, `%ENT`, and `%FLD`.
- `%ENT` uses `render_entity_repr(...)` and can recover encoded entity refs from
  visible identity facts.
- `%FLD`, compare operands, builtin operands, and fact fallback text share the
  same term renderer, so entity refs and float64 values display consistently.

Compare and builtin atoms use the default rendering table in `prober.py`.
True-unbound values render as `<unbound>` rather than lowered internal variable
names.

Not atoms follow the same structural convention as Souffle evidence:

- `EvidenceAtom.negated=True`;
- `repr_text` starts with `!`;
- one atom renders as `!a`;
- an AND body renders as `!(a && b)`;
- an OR-of-AND body renders as `!((a && b) || c)`.

NotAtom truth is still owned by the evaluation/prober verdict path. The negation
flag and repr text are display metadata.

---

## 5. Engine Shapes

- **Native** uses `probe_native(...)` for passed rows and closed-head-false
  failures.
- **Souffle** converters produce `EvidenceTree` paths with head/body rules and
  atom support.
- **ProbLog** converters produce one `EvidenceTree` per answer/proof path and
  probabilistic certainty.
- **PyReason** converters produce `EvidenceTimeline` paths with timestep-aware
  events and possibilistic certainty.

All engines return the paths model. There is no production flat-DAG evidence
builder left in this layer.

---

## 6. Test Entry Points

```bash
PYTHONPATH=src python -m unittest tests.application.explain.test_prober
PYTHONPATH=src python -m unittest tests.sdk.test_explain_conformance_native
```

The focused native prober tests lock:

- G1 monotonic witness behavior;
- G2 head/body occurrence and join shape;
- exhaustive OR paths;
- true `NotReached` behavior;
- downstream verdict cascade after upstream failure;
- schema-driven Fact/Compare/Builtin repr baking;
- entity-ref and float64 value display;
- NotAtom `negated=True` and `!<inner>` text.

The SDK conformance tests lock evaluate→explain seams:

- inline/projection/external head row anchoring;
- OR and join row anchoring;
- aggregate evaluate→explain behavior.
