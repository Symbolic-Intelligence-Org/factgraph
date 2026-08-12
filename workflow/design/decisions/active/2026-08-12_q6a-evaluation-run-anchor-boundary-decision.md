# Q6A Decision: EvaluationRun v0 anchor and query-target boundary

- Status: adopted
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: design constraint for the F4A implementation slice only.
- Inputs:
  - 2026-08-12 user authorization to proceed with the narrow F4 entry slice
  - Q5A / Q5B / Q5C and their independently reviewed implementations
  - 2026-08-12 three-way read-only F4 entry audit
- Outputs / Downstream:
  - [`2026-08-12_factgraph-evaluation-run-anchors.md`](../../../blueprints/active/2026-08-12_factgraph-evaluation-run-anchors.md)
  - F4B snapshot/support capture and detached replay
  - F4C Policy-aware explanation overlay
- Branch: `codex/v0.3.0-f4a-evaluation-run-anchors-2026-08-12`
- Base: `ca12b208`
- Depends on: Q4B / F2B and Q5A-Q5C / F3A-F3C

## 1. Problem

F3A-F3B now compile and execute a Policy-backed `EvaluationQuery` through the
existing evaluator and return the singular `EvaluateResult`. That result is a
live process object: rows are rebound to a result resolver, Explain and close
use callbacks into the current Store, and the view digest proves identity but
does not contain a recoverable snapshot. Its run-local IDs also include random
run identity.

F4 must eventually support replayable runs and Policy-aware Explain, but doing
both at once would silently conflate three different contracts:

1. immutable identity and target anchors;
2. captured data/support sufficient for detached replay;
3. a readonly Policy structure and evaluation overlay for UI/Explain.

F4A closes only the first contract and preserves enough authored structure for
the later two. It must not call a live digest a snapshot or a live callback a
historical explanation.

## 2. Scope

F4A adds an immutable, pure-data `EvaluationRunAnchorV0` to Policy-backed
`EvaluateResult` values. The anchor records:

- original and normalized target identity;
- canonical authored Policy structure, total compiler lineage and exact Rule
  pins through digest-bound values;
- typed bind/select addresses and value digests;
- Query, Policy, address-space and schema digests;
- resolved native execution-profile identity, including known-unpinned version
  fields rather than inventing versions;
- live-view identity and explicit capture/availability classifications;
- a run-local result identity, stable semantic row anchors, and a query-summary
  anchor that also exists for zero-row results.

F4A attaches that value to the existing `EvaluateResult`. It does not replace
the result, eager-explain rows, or create a second execution path.

## 3. Query-target normalization boundary

The desired user surface remains:

```python
query(resolved_rule_or_policy)
```

Rule and Policy are peers at the Query target boundary, not identical semantic
objects. Both must normalize through one Policy -> EvaluationQuery -> evaluator
path. Core execution never looks up a bare string or ambient registry entry.

- A Policy target requires an explicitly resolved Policy context containing its
  immutable Policy, managed Rule occurrences, semantic address space and schema.
- A Rule target requires a trusted `ResolvedRuleBundle`. Its deterministic lift
  uses one occurrence alias `target`, internal Policy id
  `__factgraph_rule_lift__:<rule-id>`, the Rule version, and a root
  `PolicyOccurrence("target")`.
- The Run retains `original_target_kind=rule|policy` and a distinct original
  identity. An implicit Rule lift and a user-authored one-Rule Policy may yield
  equivalent rows but are not the same governance target.
- Package/Meander or an explicit catalog may resolve a versioned string to the
  exact resolved value before calling FactGraph. Mutation of that catalog after
  compilation cannot affect the compiled Query or Run.

F4A's current producer is `policy_direct_v0`; the public Rule/Policy builder is
not added in this slice. The anchor schema nevertheless reserves and validates
both target kinds so the current Policy-only producer cannot become a permanent
architectural fork.

## 4. Decision

### 4.1 EvaluateResult remains the only row envelope

`EvaluateResult` gains one optional `run_anchor` field. Legacy evaluation paths
leave it `None`; successful compiled `EvaluationQuery` execution supplies an
`EvaluationRunAnchorV0`. Result construction revalidates that the anchor matches
the exact result, fingerprint and row inventory. The anchor contains no Store,
callback, schema object, support carrier, `DerivationOutput`, candidate ID or
private resolver.

### 4.2 Policy structure is captured before lowering erases topology

`CompiledPolicyV0` must retain a canonical `PolicyStructureV0` derived directly
from authored `Policy.when`. It records root, node kind, child topology,
occurrence aliases and Unify endpoints. Its digest is included in the compiled
Policy seal. It is never reconstructed from RuleExpr `repr`, lowered aliases or
EvidenceTree paths.

The existing `PolicyLineage` remains the total authored-to-lowered bridge.
`EvidenceGraph` / `EvidenceTree` remain inner engine evidence and are unchanged
by F4A.

### 4.3 Stable row and zero-row anchors are separate from run IDs

Existing `run_id`, `result_id` and `row_id` remain run-local. A semantic row
anchor commits Query identity, claim/binding content, closed-head identity and
certainty without the random run ID. Identical duplicate rows may intentionally
share that semantic anchor; ordinal remains a run-local observation, not a
semantic identity.

The query-summary anchor commits the Query and the sorted multiset of semantic
row anchors. It exists when there are zero rows but carries
`truth_interpretation=not_asserted`. Empty therefore never means false.
Ordering and completeness remain explicitly `unspecified` / `unknown`.

### 4.4 F4A is identity-only and non-replayable

The anchor states:

- `capture_level=identity_only`;
- `view_capture=digest_only_live_guard`;
- `replay_availability=not_available`;
- `explain_availability=live_recomputable_while_current`;
- `completeness=unknown` and `ordering=unspecified`.

It has no `replay()` method and no decode/load contract. Digest seals prove
in-process consistency, not authentication. Cross-trust codecs, exact snapshot
contents, support/provenance capture, execution-profile version closure,
retention and detached Explain belong to F4B.

### 4.5 Explain receives the Run anchor without changing evidence semantics

For an anchored Query row, `Explanation.checked_scope` includes the Run anchor
digest. The existing live view and premise guards remain authoritative. A stale
run stays unsupported under the current Explanation error-envelope contract;
F4A never falls back to current facts and calls that historical Explain.

## 5. Non-scope

- Durable codec, persistence, Run repository, snapshot resolver, replay,
  historical/detached Explain or cross-process authentication.
- Policy registry, Package persistence, Meander API, string lookup or `latest`.
- Public `query(rule_or_policy)` builder implementation; its normalization
  contract is fixed here, not shipped here.
- Expectation algebra, completeness/limits/pagination, Scenario/What-if,
  ScenarioDiff or zero-row truth interpretation.
- Policy-aware status aggregation or UI. F4C owns the outer
  `PolicyStructure + EvaluationOverlay + ProvenanceIndex` projection.
- Non-native Query engines, config support, SourceRecord admission, Actions or
  authorization.

## 6. Stop Conditions

Stop and split if implementation requires:

- serializing live callbacks, Store/schema objects or derivation/candidate IDs;
- a second result envelope or second evaluator;
- treating `row_id` as a stable semantic target;
- claiming replay from a view digest without captured snapshot contents;
- reconstructing Policy topology from RuleExpr, names, `repr` or evidence;
- changing EvidenceGraph/EvidenceTree semantics or legacy evaluate/Explain;
- adding a registry, repository, Scenario or non-native engine;
- more than 500 gross added production Python lines relative to `ca12b208`.

## 7. Acceptance Criteria

- [ ] Compiled Policy seal includes exact canonical authored Policy structure.
- [ ] Query results carry a self-checking pure-data Run anchor; legacy results do not.
- [ ] Anchor commits target, Policy/lineage/rules, bind/select, profile, view and result.
- [ ] Semantic row anchors are independent of random run IDs; duplicates are explicit.
- [ ] Zero-row results have a summary anchor without a row or truth claim.
- [ ] Splicing target/structure/query/result/row/profile fields fails closed.
- [ ] Query row Explain includes the matching Run anchor digest in checked scope.
- [ ] No replay, codec, registry or Policy-overlay claim leaks into F4A.
- [ ] F3A-F3C and legacy evaluation/Explain cohorts remain green.

## 8. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | proposed | Three read-only F4 audits converged | Identity, snapshot/replay and scope were audited independently. |
| 2026-08-12 | adopted | User authorized direct execution on a new branch | F4A is limited to in-process immutable anchors; no push or merge is authorized. |
| 2026-08-12 | narrowed | Red team separated anchors, replay and Policy overlay | Authored Policy topology became a load-bearing F4A capture; detached replay remains F4B and Policy-aware Explain remains F4C. |

