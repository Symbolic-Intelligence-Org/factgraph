# Annotation

- Scope: `src/factgraph/core/annotation`
- Status: experimental / internal API
- Already consumed internally by factgraph/core/store; breaking changes
  are not allowed, but the public API is not promised
- Last updated: 2026-04-27

## 1. Module boundary

This directory carries the internal semantic capability of the
"Souffle annotation kernel prototype".

The current goal is not to provide a stable public API, but to
distill validated annotation logic into a maintainable internal
implementation site.

## 2. Current capabilities

- `_min_max.py`
  - `min-max` path-confidence propagation corresponding to
    `Workload A`
  - Produces conclusions with `confidence`, `min_support_depth`,
    `support_path`
- `_evidence.py`
  - Structural candidates / direct evidence / provenance
    reconstruction and `max` aggregation helpers, corresponding to
    `Workload C`
  - Currently implements prototype-level raw-candidate and
    provenance capabilities; Top-K still lives in the benchmark
    harness
- `_certainty.py`
  - First-consumer prototype for the certainty-weight vocabulary
  - Consumes `confidence_kind="certainty"`, rule metadata
    `condition_weights`, and the candidate evidence tree
  - `condition_weights` is certainty/explain projection input, not an
    engine adapter parameter and not `where` execution semantics.
    Future runtime configuration for this lane belongs in
    `SemanticsProfile.certainty_projection`.
  - Producer routing for `confidence_kind="certainty"` is not
    implemented inside annotation; it is decided by core
    `store._confidence_kind_resolver` at candidate creation time
  - Produces `CertaintySummary` / `ConditionImpact`, used to derive
    candidate-level certainty summaries
  - Supports two aggregation strategies (`AGGREGATION_STRATEGIES`):
    - `"bottleneck"` (default): `impact = weight × confidence`,
      `aggregate = min(impacts)`
    - `"additive"`: `impact = (weight / Σweights) × confidence`,
      `aggregate = sum(impacts)`
  - The `CertaintySummary.aggregation` field identifies the strategy
    in use
  - `ConditionImpact.impact` semantics shift with the strategy:
    bottleneck = absolute weighted impact; additive = normalized
    contribution
  - `rank_certainty_conditions(conditions, aggregate_certainty, *, aggregation=...)`
    → `list[RankedCondition]`
    - Sorted by impact ascending (weighted first → unweighted last)
    - Bottleneck mode: `is_bottleneck=True` when condition impact ==
      aggregate_certainty (all ties marked)
    - Additive mode: `is_bottleneck=False` (additive has no
      bottleneck concept)
    - narrative / NL consume the ranked view; they don't sort
      themselves
  - Currently only the certainty lane is implemented;
    `probability` / `none` return `None` directly
  - Current production consumers:
    - runtime candidate explain delivery:
      - response-level sibling `certainty_summary` on
        `queries/explain-summary`
      - additive `certainty_lines` on `queries/explain-narrative`
      - additive certainty paragraph on `queries/explain-nl`
    - audit package + static site delivery:
      - `export_package` precomputes and writes
        `certainty_summaries.jsonl`
      - `AuditQuery.get_candidate_certainty_summary(candidate_id)`
        reads the materialized value
      - `AuditQuery.get_candidate_evidence_tree_narrative(candidate_id)`
        accepts a certainty_summary and produces a narrative with
        `certainty_lines`
      - the static-site candidate evidence page renders the
        certainty section
  - The runtime / audit / static surfaces share a single certainty
    derivation chain:
    - Derivation occurs only when the candidate tree resolves to a
      unique child-rule `referenced_support` subtree
    - `condition_weights` is queried from the single
      `rule_ref_edge -> rule_ref_id@version -> registry rule payload`
      corresponding to that subtree
    - Multi-rule, recursive nested subtree, unresolved child
      support, or missing registry chain → graceful degrade to
      `certainty_summary=null`
- `types.py`
  - Holds only the minimal shared base types
  - Does not introduce a general annotation algebra in the first
    prototype round

## 3. Relationship with the benchmark

- External benchmark / reference harness
  - Continues as the oracle / golden reference implementation
- `src/factgraph/core/annotation/*`
  - Acts as the new prototype implementation

The two must remain independent so that the same code does not
simultaneously serve as "reference truth" and "candidate
implementation".

## 4. Invariants

- Does not enter the formal `Store.evaluate(...)` public contract
- Does not own `confidence_kind` producer routing; annotation only
  consumes the determined semantic lane
- Does not modify the stable structure of `CandidateSet`
- Does not write certainty summary back to `CandidateSet`,
  `ProofReceipt`, or the core 12-field summary of the evidence
  tree
- Structured `certainty_summary` is exposed only as a
  response-level sibling, not embedded in the core 12-field summary
  set
- Runtime narrative / NL may consume the derived certainty summary
  and present it as additive `certainty_lines` / a certainty
  paragraph
- The audit package may materialize `certainty_summary` (export-time
  precomputation) but does not export `condition_weights` itself

## 5. Certainty V1 Contract (frozen)

**Status: v1 is frozen. Semantic changes require a blueprint;
direct iteration is not allowed.**

### 5.1 Frozen contract

The following contract is stable; further changes are limited to
bug fixes / performance / docs clarification:

- **Producer contract**
  - `native` path only
  - Auto-marked only at create time by
    `CertaintyConfidenceKindResolver`
  - Eligible only on a child-proof subtree (single structured
    `rule_ref_edge` + no nested `referenced_support`)
- **Evidence tree carrier contract**
  - `assertion_fact.confidence` — adapter/runtime-owned confidence when
    available; generic assertion `meta.confidence` is not lifted
  - `predicate_witness_group.condition_confidence = max(child confidences)`
  - The tree is only a carrier; it does not bake in scoring
    semantics
- **Summary contract**
  - `bottleneck` = default strategy:
    `impact = weight × confidence`, `aggregate = min(impacts)`
  - `additive` = explain-time optional strategy:
    `impact = (weight / Σweights) × confidence`,
    `aggregate = sum(impacts)`
  - `ConditionImpact.impact` semantics shift with the strategy
  - `CertaintySummary` shape: `confidence_kind`, `condition_count`,
    `weighted_condition_count`, `conditions`, `aggregate_certainty`,
    `aggregation`
- **Delivery contract**
  - runtime summary / narrative / NL support both strategies (via
    the `certainty_aggregation` query option)
  - narrative: `certainty_lines` (ranked by impact ascending) +
    `certainty_bottleneck` (machine-readable, bottleneck only)
  - NL: weakest-condition sentence (bottleneck only)
  - audit / static: always use the default `bottleneck`
  - export-time materialization: `certainty_summaries.jsonl`

### 5.2 Change thresholds

The following changes require a new blueprint:

- `CertaintySummary` shape
- `certainty_summary` response shape
- evidence-tree carrier fields (`confidence` /
  `condition_confidence`)
- resolver eligibility rules
- aggregation formula or strategy
- audit / static certainty contract

### 5.3 Non-goals (explicitly deferred)

The following are not in v1 scope; they are not omissions:

- chain / recursive certainty propagation (the eligibility guard
  returns `null` when nested `referenced_support` is encountered)
- leaf min / weighted-mean aggregation
- probability explainability
- additive-strategy parity in audit / static
- engine parity (`souffle` / `problog`)
- SDK certainty auto-routing parity
- rule cap / threshold / optional conditions
- `Workload B` temporal semantics

### 5.4 Test baseline

- 234 tests all green
- Key contract tests: auto-routing e2e, fact-confidence
  propagation, bottleneck vs additive, ranking / narrative / NL
  wording, audit / static round-trip
- Changing semantics requires updating the blueprint first, not
  changing test expectations first

## 6. Provenance Summary Schema

The prototype currently keeps two **domain-specific** provenance
summary shapes; field names are deliberately not unified across
them, by design.

### 6.1 `_min_max.py`

`build_min_max_provenance_entries(...)` produces:

```json
{
  "candidate": {
    "source": "e000",
    "target": "e002"
  },
  "support_path": [
    "e000 -[0.900000]-> e001",
    "e001 -[0.800000]-> e002"
  ]
}
```

Field conventions:

- `candidate.source / candidate.target`
  - Source / target endpoints of the graph-path problem
- `support_path`
  - List of edge-path strings
  - Format fixed as `"X -[0.900000]-> Y"`
  - Edge weights are 6-decimal floats

### 6.2 `_evidence.py`

`build_max_evidence_provenance(...)` produces:

```json
{
  "candidate": {
    "subject": "ent001",
    "relation": "indirect_dependency",
    "object": "ent003"
  },
  "direct_evidence": ["claim0001"],
  "struct_support": [
    "ent001 -[depends_on]-> ent002",
    "ent002 -[depends_on]-> ent003"
  ]
}
```

Field conventions:

- `candidate.subject / candidate.relation / candidate.object`
  - Candidate primary key for the relational-triple problem
- `direct_evidence`
  - List of `claim_id`
- `struct_support`
  - List of structural-support chain strings
  - Format fixed as `"X -[relation]-> Y"`
  - Bracketed content is the relation name, not a numeric weight

### 6.3 Why `candidate` field names are not unified

- `_min_max.py` expresses graph-path conclusions whose primary key
  is naturally `(source, target)`
- `_evidence.py` expresses relational-triple conclusions whose
  primary key is naturally `(subject, relation, object)`

The prototype keeps this distinction explicit to avoid introducing
an unnecessary abstraction layer in the name of "field
unification". If this work later moves into formal runtime, we will
decide whether a unified carrier is needed based on actual call
sites.
