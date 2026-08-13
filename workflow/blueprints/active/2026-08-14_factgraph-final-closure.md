# Task Blueprint: FactGraph final Query / Scenario closure

- Status: scoped
- Created: 2026-08-14
- Last Updated: 2026-08-14
- Branch: codex/v0.3.0-factgraph-final-closure-2026-08-14
- Related Modules:
  - src/factgraph/application/protocol/
  - src/factgraph/application/*scenario*, *query*, *evaluation_run*
  - src/factgraph/sdk/evaluation_query_builder.py
  - src/factgraph/sdk/store.py
  - src/factgraph/core/store/_evaluate.py
  - src/factgraph/adapters/native/, souffle/, problog/
- Related Docs:
  - [Q18 final closure contract](../../design/decisions/active/2026-08-14_q18-factgraph-final-closure-contract.md)
  - [Final-closure audit](../../audit/active/2026-08-14_factgraph-final-closure-vs-shipped.md)
- Audit Log:
  - [paired audit](./2026-08-14_factgraph-final-closure.audit.md)

## 1. Problem

The existing F3--F5 pieces have separately correct v0 contracts but cannot yet
serve as the complete FactGraph substrate for the next Meander/Agent phase.
Most importantly, Scenario is only scalar replacement, Query is native-only,
and capture/Explain/replay cannot describe one portable baseline/effective
run.

## 2. Goals

- Deliver Q18's four capability matrices as one coherent v1 surface.
- Preserve every existing v0 wire, digest and public behavior through explicit
  compatibility adapters.
- Execute a bounded positive deterministic Query profile through native,
  real Soufflé and real ProbLog against the same sealed relation.
- Capture enough material for detached replay and explicit Policy-aware Explain
  without claiming source authority or engine-proof equality.
- End with a conformance corpus, exhaustive boundary tests and one final
  independent audit-ready delivery report.

## 3. Non-goals

- Meander Plan/Translator, Package/registry publication, agent permissions,
  SourceRecord resolution, product disposition, UI, MCP and Action/Decide.
- Closed-world public negation, signed-negative facts, generic symbolic
  constraints, minimal world repair, identity mutation, temporal history, or
  permanent Scenario storage.
- Universal engine equivalence, engine proof equivalence, arbitrary callbacks
  during engine evaluation, remote I/O, or automatic fallback.
- Any modification to master, user dirty worktree contents, or external
  services/credentials.

## 4. Current Context

- F3 establishes sealed Policy/query compilation and direct semantic addresses.
- F4 establishes native anchors/bundles and detached evidence.
- F5 establishes contain-row observation, immutable Policy comparison/
  navigation, a query-scoped effective relation and a narrow captured Scenario.
- Q17 demonstrates that native NAF is an observation, not a safe public
  absence contract.
- Q18 turns those pieces into an explicit final v1 boundary rather than
  retroactively widening a v0 wire protocol.

## 5. Proposed Shape

### 5.1 Protocol layer

Add independent v1 protocol values:

- ScenarioSpecV1, grounded premise statements and canonical resolved operations;
- EffectiveWorldV1, with separate semantic-world and resolution-evidence
  digests;
- QueryPlanV1, result mode/expectation inventory and optional immutable
  candidate target;
- ExecutionProfileV1 and PortableProfileV1;
- EvaluationRunV1, per-engine result frames, parity, replay material and
  explicit row/summary anchors;
- Scenario/variant explanation envelopes; and
- FactGraph technical assessment axes.

The values use strict canonical codecs and no live Store/object references.
Q7/Q11/ScenarioRunV0 are translated at the boundary rather than widened.

### 5.2 Resolver and query execution

The resolver produces baseline/effective frozen projected relations after all
schema, groundness, cardinality, conflict and dependency checks. It owns
synthetic witness identity and origin labelling. The engine facade accepts
only the resolved relation, materialized lowering and pinned profile.

QueryPlanV1 retains one compiler/lowering path. A Rule is sealed-lifted, a
Policy remains direct, and a RelationProvider first produces a finite typed
relation receipt. Results are normalized before modes, expectations and parity
are calculated.

### 5.3 Portable engines

Create an adapter-neutral effective-relation materialization seam. Native,
Soufflé and ProbLog must read the same finite relation and return canonical
selected rows. The portable compiler rejects any profile/atom/provider form
outside Q18 before an adapter is invoked.

### 5.4 Run/evidence boundary

EvaluationRunV1 stores both sides when Scenario/variant comparison applies.
It carries no current Store fallback. Native proof receipts and external
adapter evidence remain labelled, then project onto the authored Policy
structure only where exact lineage exists. Replay verifies/calls only captured
inputs. Assessment reports technical axes without product verdicts.

## 6. Boundaries And Invariants

- Scenario operation order cannot change world identity or output.
- Every operation is grounded, extensional and schema-valid; conflicts are
  typed failures before execution.
- Scenario.without creates exact local closure for its target; EvidenceScope
  ignore only excludes baseline input. A separately typed query-local absence
  check may use that exact closure against the sealed relation; neither becomes
  a global negative fact, and portable Rule/Policy NAF is rejected.
- Every negative expectation outcome proves complete enumeration or remains
  unresolved.
- No result row becomes an Explain target by position/implicit first-row.
- A candidate Policy is an independent immutable target, never an overlay.
- External providers are materialized before engine execution and cannot write.
- The only parity claim is normalized row equivalence in the declared portable
  profile. Engine evidence is not made artificially identical.
- Existing Query/Scenario v0 behavior remains available and must pass its
  legacy regressions.

## 7. Acceptance

- [ ] Scenario v1 supports every Q18-supported premise operation, conflicts
  and exact boundary rejection.
- [ ] QueryPlan v1 supports Rule/Policy/provider targets, all result modes and
  all Q18 expectation forms with independent completeness state.
- [ ] Effective-world and Policy-variant executions capture baseline/effective
  differences and explicit anchors.
- [ ] Native, Soufflé and ProbLog all execute the portable corpus against the
  exact captured world with no fallback.
- [ ] Replay/explain read no mutable Store; mutation and splice probes fail
  closed.
- [ ] Assessment/evidence boundaries are typed and module docs are clear.
- [ ] Focused legacy cohorts and the new conformance corpus pass; lint/type/
  diff checks pass; final audit documents any unrelated baseline failure.

## 8. Implementation Plan

1. Establish the v1 protocol/codec family and compatibility bridges. Add the
   capability-matrix test skeleton before executor changes.
2. Implement the Scenario v1 resolver: grounded operation normalization,
   conflict algebra, effective-world construction, origins and masks.
3. Implement QueryPlan v1 modes, expectations, relation-provider materializing
   boundary and immutable target-variant comparison.
4. Refactor the evaluator seam so native, Soufflé and ProbLog execute sealed
   effective relations. Implement the portable compiler/capability gate and
   normalized-row parity comparison.
5. Implement EvaluationRun v1 capture, detached replay, explicit Explain
   anchors, Scenario/variant evidence envelopes and technical assessment.
6. Build and run the real-engine conformance corpus, adversarial splice/
   mutation/absence tests and legacy regressions. Update module docs and
   conclude with a final audit/closure report.

The user has explicitly authorized these bounded internal steps to proceed
continuously. A newly discovered semantic conflict that Q18 cannot resolve is
the only reason to stop and request a decision.

## 9. Docs To Update

- src/factgraph/application/docs/rule.md
- src/factgraph/application/protocol/docs/README.md
- src/factgraph/sdk/docs/03_rules_and_inferences.en.md
- src/factgraph/sdk/docs/04_api_surface.en.md
- src/factgraph/sdk/docs/06_what_if_and_proof.en.md
- src/factgraph/adapters/docs/01_souffle_adapter.md
- src/factgraph/adapters/docs/02_problog_adapter.md
- workflow design/decision and final closure audit

## 10. Outcome / Deviations

In progress. This section will list the exact protocol versions, real-engine
conformance results, rejected cells, compatibility proof, audit findings and
any explicit Q18-consistent narrowing.
