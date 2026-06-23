# Application Explain Module

- Scope: `src/factgraph/application/explain`
- Last updated: 2026-06-22
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

`Holds.support` carries the provenance `Source`(s) backing the atom. The reach
(souffle/problog via `diagnostic_assemble`) and native (`prober`) paths populate
it for holding **Fact** atoms — one `Source` per matched EDB fact (a stable `ref`,
a readable `value`, and `{engine, predicate}` `meta`). Compare / Builtin / Aggregate
atoms have no backing fact, so their support stays empty.

`Fails.support` symmetrically carries the *refuting* fact(s) for a failing Fact
atom — the actual EDB fact(s) that share the atom's owner key but carry a different
value (`meta["role"]="refuting"`, `meta["actual"]` = the actual terms); e.g.
`project:active(P1, False)` behind a failed `== True`, or `assignment:user(AP1,
Alice)` behind a failed `== Carol`. A pure absence (no fact for that owner) and
unary existence facts keep empty support. `NotReached` carries none.

`NotReached` is reserved for direct unbound-variable dependencies. It is not a
generic "previous atom failed" marker. After an upstream failure, the prober
keeps two tracks: the branch candidate envs stay empty so the failed branch does
not resurrect, while a row-anchored explanation track continues advancing
exhaustively. Later atoms whose input dependencies are bound still report their
own `Holds` or `Fails`; only genuinely unbound dependencies report
`NotReached`.

---

## 3. Native Prober

```python
def probe_native(
    plan: RuleExprLoweringPlan,
    bindings: Mapping[str, Any] | None,
    view_facts: Mapping[str, Sequence[tuple[Any, ...]]],
    schema_index: object | None = None,
    *,
    rules_by_id: Mapping[str, Any] | None = None,
    subject_binding: Mapping[str, Any] | None = None,
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

The seed (a row's port bindings, or a closed head's pins on the failure path) is
expanded **transitively** over the branch join / head-link eq-atoms before
probing (`transitively_expand_seed`): an occurrence-local variable reached only
through a cross-occurrence join is pinned to the value its join partner carries,
so a non-holding subject's culprit is attributed to the failing occurrence atom
rather than to a head-link the prober reaches last. Purely existential joins
(neither endpoint seeded) stay free. On a holding row the expansion is an
identity extension, so the holding result is unchanged.

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
- **Souffle** uses a dedicated reach-chain row explain path for supported
  lowered rule expressions. The static lowering plan supplies branch and
  condition structure; the Souffle reach output supplies row-specific witness
  bindings and failure values. Unsupported S1 shapes
  such as `ruleref`, recursion, and aggregates degrade to the existing
  ProofReceipt/minimal row paths rather than the shared diagnostic companion.
- **ProbLog** uses a dedicated reach-chain row explain path for supported
  lowered rule expressions. The reach program queries each branch prefix to
  recover per-condition weighted model counts, row-specific witness bindings,
  and failure values. Candidate proof-trace conversion remains as a fallback
  and adapter-level provenance surface.
- **PyReason** converters produce `EvidenceTimeline` paths with timestep-aware
  events and possibilistic certainty.

All engines return the paths model. There is no production flat-DAG evidence
builder left in this layer.

---

## 6. Closed-Head-False (Full-Coverage Failure Explain)

When `fg.eval.explain(expr, head=closed_head)` matches no result row (the closed
head's pinned subject does not hold), the SDK does NOT fall back to a head-only
probe. It lowers the FULL expr body against the closed head, extracts the head
pins as a seed (`pin_specs_for_closed_head` → `SDKStore._pin_bindings_for_closed_head`,
minting entity idrefs via the same `_ref` path the EDB uses, so the seed is
byte-identical to engine facts — seed-parity), and routes that pin-seeded body
plan through the same per-engine evidence builders the holding path uses:

- **souffle / problog** → the engine-own reach-chain builder
  (`*_reach_explain_to_evidence_graph`), seeded by the pins. Cross-occurrence join
  failures are folded into each branch's tree status (`_fold_join_status`), so a
  composite that fails only on a join — e.g. a same-project constraint where every
  occurrence holds individually — is reported `fails`, not `holds`. OR composites
  yield one tree per branch; the graph aggregates (all branches fail → failed).
- **native / pyreason / reach-unsupported fallback** → the pin-seeded native
  prober (never the minimal head-only graph, which would drop body coverage).

The probe is labelled `probe_kind="structural_reachability"`: a non-holding
conclusion has no derived weighted-model-count, so the verdicts are the objective
structural reachability of each atom/join, not a fabricated probabilistic score.
`Explanation.status="failed"` always carries a non-empty evidence graph
(enforced by `Explanation.__post_init__`).

Known limits / per-engine nuances:

- **souffle large composites**: `fg.eval.explain(...)` first runs the
  witness-building souffle evaluate, which raises when a witness relation arity
  exceeds the souffle limit (22). This is pre-existing — it constrains HOLDING
  souffle explain of large composites too — and independent of this path; large
  composites are explained under problog/native.
- **native vs reach downstream display**: after the culprit atom fails, the native
  prober shows the occurrence's remaining atoms with their threaded per-atom
  verdicts (often `Holds`), whereas the reach engines show them `NotReached`
  (derivation-flow). Culprit attribution is identical on both.
- **head-port links** hold by construction under the consistent pin seed and are
  not folded into tree status (see `prober._fold_join_status`); a broken seed
  invariant would need them folded + surfaced.
- **bare single-rule heads** route via `head.as_("head")` (a single rule's body is
  the head structurally); the full-body lowering applies to `RuleExpr` composites.

---

## 7. Test Entry Points

```bash
PYTHONPATH=src python -m unittest tests.application.explain.test_prober
PYTHONPATH=src python -m unittest tests.sdk.test_explain_conformance_native
PYTHONPATH=src python -m pytest tests/sdk/test_explain_composite_closed_head_false.py
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
