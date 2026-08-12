# Q5B Decision: EvaluationQuery v0 native execution bridge

- Status: adopted
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: design constraint for the F3B implementation slice only.
- Inputs:
  - 2026-08-12 user instruction to continue F3B on the isolated branch
  - [`2026-08-12_q5a-evaluation-query-projection-v0-decision.md`](./2026-08-12_q5a-evaluation-query-projection-v0-decision.md)
  - [`2026-05-25_t5-d18-return-shape-transition.md`](./2026-05-25_t5-d18-return-shape-transition.md)
- Outputs / Downstream:
  - [`2026-08-12_factgraph-evaluation-query-native-execution.md`](../../../blueprints/active/2026-08-12_factgraph-evaluation-query-native-execution.md)
- Branch: `codex/v0.3.0-f3b-evaluation-query-execution-2026-08-12`
- Base: `5a6f4a55`
- Depends on: Q5A / F3A

## 1. Problem

F3A produces a self-checking `CompiledEvaluationQueryV0`, but deliberately
stops before execution. The next useful proof is not another plan inspection:
the exact compiler-issued lowering plan must constrain and project real native
facts through the shipped evaluator.

Returning raw `CandidateSet` values from a new Query API is not acceptable.
D18 classifies them as internal execution artifacts, and Q5A requires later
slices to reuse the existing `EvaluateResult` rather than create a second
rows/fingerprint/explain model.

At the same time, the shipped result envelope does not yet provide F4's
immutable evaluation bundle or snapshot-stable historical Explain. F3B must
therefore expose a useful live execution seam without pretending those later
guarantees already exist.

## 2. Scope

F3B adds one experimental path that does not mutate facts or the ledger:

```python
result = fg.eval.evaluate(compiled_query, engine="native")
```

It:

- revalidates the complete compiler-issued Query artifact immediately before
  execution and matches its schema digest to the receiving FactGraph;
- materializes the exact F3A lowering plan once and invokes the existing native
  `evaluate_derivation_plans` authority;
- keeps `CandidateSet` internal and returns the shipped `EvaluateResult`;
- marks rows as `projection`, retains ordered Query aliases and restores the
  compiler-known value-domain tags on projected terms;
- binds result fingerprints to Query, Policy, address-space, schema and
  occurrence-qualified Rule pins;
- requires the view digest to remain stable across evaluation and makes live
  `row.close()` / `row.explain()` fail closed after the view changes.

## 3. Non-scope

- F4 immutable `FactGraphEvaluationBundle`, durable snapshots, replay or
  historical Explain.
- Query-summary or expectation anchors, `expect`, completeness, limits,
  pagination, truncation or zero-row truth interpretation.
- Souffle, ProbLog or PyReason Query execution; F3B is native-only.
- Query execution config. `config=` is rejected for this native-only slice;
  execution-profile capture remains an F4/F5 concern.
- `evaluate_candidates(compiled_query)`, standalone
  `eval.explain(compiled_query, ...)`, accepting/writing Query candidates, SDK
  Query builders, codecs, persistence, What-if, Meander or Agent APIs.
- Renaming or reinterpreting the older SDK `Query`, application
  `QueryRuntimeRequest`, `match`, Rule or RuleExpr paths.

## 4. Decision

### 4.1 The exact compiled artifact is the execution authority

Execution must not replace the compiler-issued plan with a newly reconstructed
Query or Policy plan. It re-runs F3A's full structural/currentness check (which
recomputes the expected seal for comparison), verifies the active SDK schema
digest, then materializes `compiled_query._lowering_plan` itself.
Any stale Rule, Policy, digest, branch mapping, binding, projection head or plan
splice fails before the engine is invoked.

### 4.2 CandidateSet remains internal; EvaluateResult remains singular

The native evaluator may continue to emit `CandidateSet` internally. The SDK
immediately adapts those candidates into the existing `EvaluateResult`. Query
execution is deliberately excluded from `evaluate_candidates`, because a
synthetic projection candidate must not become an accidental write/accept
surface.

Query rows use the existing `projection` kind. Candidate payload arity and
shape must match the ordered selections, and each result term is retagged from
the compiler-known selection value domain rather than trusting Python runtime
type inference.

### 4.3 Query identity must survive result construction

The Query result `expr_digest` is the protocol-form `sha256:` token of the
compiler-issued `query_digest`; that transitive seal already commits the
format, Policy, address space, schema, bindings and selections. The
`rule_set_digest` commits the sealed `policy_digest` (which transitively covers
occurrence-qualified Rule pins, expression, branches and lineage) plus the
synthetic projection head. Structurally identical plans compiled from different
Policy/Query identities must therefore not collide.

### 4.4 F3B is a stable-live-view contract, not replay

The SDK captures its existing view digest immediately before and after native
evaluation. A change aborts result construction. The resulting digest is reused
as the result anchor rather than recomputed a third time.

`row.close()` and `row.explain()` are permitted only while the current live
view digest still equals the result anchor. After a change, both fail closed.
This prevents an old result fingerprint from being paired with newly read
facts, but does not capture metadata, premise policy or the ledger. Because a
later Explain could otherwise apply a different premise policy, v0 admits only
an empty premise-filter configuration and fails closed if one appears during
execution or before lazy close/explain. F4 must replace this live guard with an
immutable bundle before any durable replay or historical Explain claim.

### 4.5 Native-only is an intentional stop, not inferred parity

`engine=None` and `engine="native"` select the same path. Any other engine and
any non-`None` `config` fail explicitly before materialization. This avoids
silently inheriting current adapter gaps (including schema-less PyReason
projection and incomplete config forwarding) and preserves the staged F5
cross-engine decision.

## 5. Stop Conditions

Stop and split the slice if any of the following becomes necessary:

- changing public `EvaluateResult` / `EvaluateRow` fields or adding a result DTO;
- adding a durable bundle, snapshot store, replay protocol or expectation state;
- modifying an engine adapter or enabling a non-native Query engine;
- making `CandidateSet` a public Query return or accept surface;
- changing legacy Rule/RuleExpr/Inference/Query/Match behavior;
- exceeding 320 added production Python lines relative to `5a6f4a55`.

## 6. Acceptance Criteria

- [ ] A compiled Query executes its exact native plan and returns ordered projection rows.
- [ ] Bindings constrain engine truth; a non-matching bind returns a valid empty result.
- [ ] Execution performs no fact/ledger mutation and invokes the native evaluator once; existing support-artifact caching may still occur.
- [ ] Stale/spliced artifacts and a mismatched Store schema fail before engine invocation.
- [ ] Rows use kind `projection` and compiler-known type tags.
- [ ] Query/Policy identity changes alter the result expression/rule-set anchors.
- [ ] A view change during execution aborts; a later view change blocks close/explain.
- [ ] Non-empty or later-mutated premise filters fail closed in v0.
- [ ] Non-native engines, config, query candidates and standalone Query explain reject explicitly.
- [ ] Legacy evaluation, Explain, Match and old Query regression cohorts remain unchanged.
- [ ] F4 bundle/replay/expect/completeness semantics are not claimed or implemented.

## 7. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | proposed | Execution, result and Explain ownership audited | Existing CandidateSet is internal; full snapshot/replay anchors do not yet exist. |
| 2026-08-12 | adopted | User instructed the team to continue F3B | The slice is a native-only live execution bridge on a new isolated branch. |
| 2026-08-12 | narrowed | Independent semantic and compatibility audits converged | Rejected a public CandidateSet seam; added artifact/schema revalidation, Query fingerprints, projection typing and live-view guards while leaving immutable bundles to F4. |
