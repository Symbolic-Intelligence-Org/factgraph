# Task Blueprint: FactGraph F4 replay, detached evidence, and Policy projection

- Status: implementing
- Created: 2026-08-12
- Last Updated: 2026-08-13
- Branch: `codex/v0.3.0-f4-completion-2026-08-12`
- Base: `c09ea303`
- Related Modules:
  - `src/factgraph/application/`
  - `src/factgraph/application/protocol/`
  - `src/factgraph/application/explain/`
  - `src/factgraph/sdk/store.py`
- Related Docs:
  - [`Q6A EvaluationRun anchor boundary`](../../design/decisions/active/2026-08-12_q6a-evaluation-run-anchor-boundary-decision.md)
  - [`Q6B EvaluationRun bundle capture`](../../design/decisions/active/2026-08-12_q6b-evaluation-run-bundle-capture-decision.md)
  - [`F4B1 archived blueprint`](../archive/2026-08-12_factgraph-evaluation-run-bundle-capture.md)
- Audit Log:
  - [`2026-08-12_factgraph-f4-completion.audit.md`](./2026-08-12_factgraph-f4-completion.audit.md)

## 1. Problem

F4A and F4B1 now provide a self-checking Run identity and an opt-in, canonical,
detached bundle containing the exact native plan, effective relation, rows and
ProofReceipts. The remaining F4 work is to verify that captured execution in an
isolated runtime, render one captured row as Store-independent engine evidence,
and project that evidence onto the authored Policy tree without confusing Query
bindings, empty results, authorization or future Scenario semantics.

## 2. Goals

- F4B2: isolated native semantic/support verification from one decoded bundle.
- F4B3: detached, assertion-backed, single-row inner `EvidenceGraph` playback.
- F4C: a readonly, lineage-total Policy explanation view layered over inner evidence.
- Preserve the same Rule → Policy → EvaluationQuery → evaluator path and all
  F3/F4A/F4B1 contracts.

## 3. Non-goals

- No Store/database reads, registry, filesystem, network, Operator or Action.
- No new `EvaluateResult`, recreated source `run_id`, `bundle.replay()` or generic
  `fg.eval.replay()` API.
- No truth interpretation for zero rows and no fabricated failed-row explanation.
- No Scenario/What-if, Policy mutation, UI, Package/catalog or Meander repository.
- No non-native engine, config or premise-policy replay in F4 v0.
- No authentication, signing, encryption, retention or custody service.

## 4. Current Context

- F4A captures canonical `PolicyStructureV0`, total `PolicyLineage`, Rule pins,
  semantic row anchors and a zero-row summary.
- F4B1 captures one dependency-complete effective relation and canonical native
  ProofReceipt per positive row, but honestly declares replay unimplemented and
  authenticity unverified.
- Existing native evaluation materializes intermediate join environments; an
  untrusted bundle therefore requires a pre-execution work bound.
- EvaluationQuery runtime binding atoms are outside authored Policy lineage and
  must never contribute to Policy occurrence status.

## 5. Proposed Shape

### 5.1 F4B2 — isolated verification

`verify_evaluation_run_bundle(bundle) -> EvaluationRunVerificationV0` performs:

1. full F4B1 validation;
2. execution-profile and Where-AST-gate compatibility checks;
3. a conservative, saturating work estimate capped at `100_000`;
4. direct pure native evaluation over the captured relation with `registry=None`;
5. fresh winning-branch selection and fresh ProofReceipt construction;
6. Query projection deduplication using the shipped support-winner rule;
7. unordered semantic-anchor and `(semantic-anchor, support-digest)` multiset
   comparison;
8. a deterministic sealed verification record containing no source Run IDs.

New Query captures publish stable semantic contract pins
`native_where_v1` and `evaluation_query_projection_v0`; legacy evaluation remains
unchanged. Older incomplete-pin bundles may produce only
`matched_unpinned_runtime`. Declared pin or AST-gate mismatch never executes.

### 5.2 F4B3 — detached row evidence

`evaluation_run_bundle_evidence(bundle, *, row_capture_digest)` validates the
whole bundle, resolves exactly one captured row, and builds one engine-centric
`EvidenceGraph` solely from its native plan, ProofReceipt and captured relation.

- `EvidenceAtom.atom_id` is the exact materialized branch condition coordinate.
- Predicate `Source.ref` is the captured assertion ID; metadata retains predicate,
  condition and bundle/row anchors.
- Non-fact steps retain their exact condition key and captured status.
- Authored Unify materializations become structured `EvidenceJoin` values.
- Query binding/head-link evidence may remain visible as engine evidence, but is
  explicitly outside Policy lineage.
- No row selector means no evidence; zero-row bundles cannot produce failed evidence.
- Playback reports captured evidence and does not claim logical verification;
  callers may pair it with the independent F4B2 record.

### 5.3 F4C — authored Policy projection

`project_policy_explanation_v0(run_anchor, evidence, *, semantic_row_anchor_digest)`
returns a separate `PolicyExplanationViewV0`; it does not mutate or replace the
inner `EvidenceGraph`.

- `PolicyLineage.body_atom` locates authored atoms by exact branch, lowered
  occurrence and lowered index.
- `PolicyLineage.unify` locates joins by exact structured endpoints.
- `PolicyStructureV0` alone supplies authored All/Any topology.
- Runtime Query atoms, synthetic head atoms and unmatched evidence are recorded
  as outside Policy lineage and never folded into occurrence status.
- Node states are `holds | fails | not_reached | not_applicable | indeterminate`;
  `approved` is forbidden because logical truth is not authorization.
- Projection is total-or-error: missing, duplicate or inconsistent lineage yields
  no partial Policy view and never destroys the valid inner evidence.
- A positive row requires a holding Policy root. Empty results have no Policy view.

The detached public composition is:

```python
verification = verify_evaluation_run_bundle(bundle)
evidence = evaluation_run_bundle_evidence(
    bundle,
    row_capture_digest=bundle.rows[0].row_capture_digest,
)
policy_view = project_policy_explanation_v0(
    bundle.run_anchor,
    evidence,
    semantic_row_anchor_digest=bundle.run_anchor.row_anchors[0].semantic_anchor_digest,
)
```

## 6. Boundaries And Invariants

- Any match means only “this verifier reproduced the captured input”; source and
  business truth remain unverified.
- Invalid bundle shape raises `ProtocolShapeError` before any evaluator call.
- Runtime incompatibility or resource rejection emits a typed non-executed record.
- F4B2 invokes the evaluator at most once and never touches a Store or support cache.
- Comparison preserves duplicate multiplicity but ignores result order and old row IDs.
- F4B3 provenance uses assertion identities from ProofReceipt, never `repr` parsing.
- F4C maps exact lineage coordinates; generated alias parsing and positional `zip`
  inference are forbidden.
- Structural Policy nodes aggregate child state but do not duplicate descendant sources.
- Production gross-addition stops: F4B2 `<=1,050` (amended on 2026-08-13 solely
  for independently discovered resource-gate and typed, fail-closed
  receipt-validation corrections), F4B3 `<=650`, F4C `<=980` (including its
  public exports).

## 7. Acceptance

- [ ] New Query bundles carry complete stable runtime pins; legacy paths do not change.
- [ ] F4B2 verifies positive, zero-row, OR, negation, aggregate and typed-value cases.
- [ ] Pin/gate mismatch and work-budget overflow execute the evaluator zero times.
- [ ] Semantic drift and support drift are distinct, deterministic verdicts.
- [ ] Repeated verification yields the same verification digest without source Run IDs.
- [ ] F4B3 builds detached row evidence after the originating Store is changed/destroyed.
- [ ] Every predicate support source resolves to a captured assertion ID.
- [ ] F4C handles occurrence, All, Any, nested structures and Unify by total lineage.
- [ ] Query binding/head atoms do not affect authored occurrence status.
- [ ] Zero-row bundles do not become false/failed Policy explanations.
- [ ] Legacy Rule/RuleExpr evaluate and Explain behavior remains green.
- [ ] Application/SDK tests, lint, type checks and adversarial probes pass.
- [ ] Module documentation distinguishes verification, playback and Policy projection.

## 8. Implementation Plan

1. Add runtime pins, the F4B2 DTO/verifier, work estimator and focused tests.
2. Add F4B3 detached evidence builder and assertion-backed provenance tests.
3. Add F4C Policy projection DTO/projector and composition tests.
4. Run the integrated application/SDK cohort, static checks and targeted attacks.
5. Submit one combined read-only external review package; only then close/archive.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- public application/protocol exports
- this blueprint/audit outcome after review

## 10. Outcome / Deviations

Pending implementation and combined independent review.
