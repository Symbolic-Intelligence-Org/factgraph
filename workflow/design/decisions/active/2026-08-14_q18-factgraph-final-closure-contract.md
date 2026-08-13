# Q18 Decision: FactGraph final Query, Scenario and execution closure

- Status: adopted
- Created: 2026-08-14
- Last Updated: 2026-08-14
- Authority: the user's 2026-08-14 explicit authorization for one continuous,
  no-time-budget final FactGraph implementation. The user delegated internal
  audit/blueprint/implementation transitions for this bounded contract; no
  Meander, Agent, Action or external-service authority is implied.
- Inputs:
  - [Final-closure versus shipped audit](../../../audit/active/2026-08-14_factgraph-final-closure-vs-shipped.md)
  - Q3A/Q4A/Q4B/Q5A/Q5B/Q6A/Q6B/Q7--Q17
  - the working semantic-port, Scenario/Run and premise/effective-view
    design-points, consumed here as candidate input rather than direct authority
- Outputs / Downstream:
  - [FactGraph final closure blueprint](../../../blueprints/active/2026-08-14_factgraph-final-closure.md)
  - a final conformance corpus and implementation/closure audit
- Branch: codex/v0.3.0-factgraph-final-closure-2026-08-14
- Base: 416456445957251b45a6ebbc8fb1f979843bf2ac
- Depends on: Q3A/Q4A/Q4B/Q5A/Q5B/Q6A/Q6B/Q7--Q17

> This is a superseding final-scope decision. It preserves the factual
> observations and compatibility promises of earlier Q decisions, but replaces
> their stated v0 non-scope restrictions where this document says a v1
> capability is required. Earlier v0 protocols remain supported compatibility
> protocols; they are not silently redefined.

## 1. Problem

The F3--F5 implementation has proven the critical pieces independently:
ontology-addressed Rule ports, Policy topology, direct comparison/navigation,
sealed Query projection, native results and captures, and a narrow replacement
Scenario. It has not yet joined them into the product-shaped contract that
Meander needs: a caller declares what to evaluate, what temporary world to
use, what to observe and expect, and which immutable run to explain or replay.

The final FactGraph boundary must be complete enough for Meander to consume as
its load-bearing logical kernel without making FactGraph decide Agent trust,
source authority or product disposition.

## 2. Scope

Q18 closes four mutually linked matrices:

1. Scenario capability and effective-world construction;
2. Query, result, completeness and expectation semantics;
3. execution-run, Explain and replay continuity; and
4. logical evidence and technical-assessment boundaries.

It additionally establishes a portable deterministic profile for native,
Soufflé and ProbLog. It is not a promise that every language feature or proof
model of those engines is equivalent.

## 3. Final capability matrix

### 3.1 Scenario capability

| Capability | Final disposition | Contract |
| --- | --- | --- |
| Existing scalar replacement | supported | Normalized as SET_EFFECTIVE_VALUE; Q7/Q11 remain compatible. |
| New scalar value on an existing entity | supported | SET_EFFECTIVE_VALUE may create a missing non-identity, extensional scalar value. |
| Multi-value add | supported | ENSURE_MEMBER is idempotent and source-order independent. |
| Multi-value exact replacement | supported | SET_EXACT_MEMBERS replaces the effective member set, never list order. |
| Exact absence of a value/assertion | supported | WITHOUT_VALUE / WITHOUT_ASSERTION create an exact local empty/member-absent world and closure for that target. |
| Exact absence of a field/relation/entity | supported | WITHOUT_FIELD / WITHOUT_RELATION / WITHOUT_ENTITY create an exact local empty world and closure for that target. |
| Evidence/admissibility exclusion | supported, separate | EvidenceScope.ignore removes baseline inputs but declares no completeness or absence. |
| New ephemeral entity | supported | CREATE_EPHEMERAL_ENTITY creates a run-scoped identity plus declared facts only. |
| New extensional relation tuple | supported, restricted | Only an Ontology/schema-declared extensional relation may be added; ordinary derived Rule conclusions cannot be injected. |
| Same-value corroboration | rejected | SET remains canonical; source corroboration is a separate Meander concern. |
| Generic symbolic constraints / world synthesis | rejected | A premise must resolve to concrete, grounded extensional operations. |
| Identity mutation | rejected | Identity is immutable; a new entity must use CREATE_EPHEMERAL_ENTITY. |
| Permanent Scenario storage | rejected | Scenario worlds are serializable run artifacts, never ledger writes. |
| Source authority / add-versus-replace decision | Meander-owned | FactGraph receives typed intent/origins, resolves schema/cardinality/conflict only. |

### 3.2 Query, result and expectation

| Capability | Final disposition | Contract |
| --- | --- | --- |
| Resolved Rule and direct Policy target | supported | They share one Query target layer; a Rule uses deterministic sealed lift. |
| Finite materialized relation target | supported | A relation provider materializes typed tuples before engine execution. |
| Pure Compute and bounded Lookup provider | supported, restricted | Both return a sealed finite relation/receipt before engine execution; no engine calls arbitrary code. |
| Direct entity/match compatibility | supported | Existing match/read surfaces stay intact; an equivalent relation target is available without forcing all reads through Policy. |
| Bind/select/field navigation/Policy comparison | supported | Existing structured semantic-address contracts remain the only canonical form. |
| Result modes | supported | rows, exists, count and set are separately typed result summaries. |
| Expectations | supported | contains-row, exists, count, exact-set and exact-local-absence operate on normalized selected rows/world targets. |
| Bag / duplicate-sensitive semantics | rejected | The portable engines expose set semantics; no implicit bag claim is made. |
| Completeness | supported | complete, incomplete, unsupported and resource-limited are distinct. Zero rows never mean false. |
| Implicit first row / implicit projection | rejected | Explain, close and expectation targets always name an explicit row, selection or summary. |
| String DSL / ambient Policy registry | rejected | The API remains typed/resolved; publication lookup belongs above FactGraph. |

### 3.3 Run, Explain and replay

| Capability | Final disposition | Contract |
| --- | --- | --- |
| Pinned execution plan | supported | Target, schema/address-space, compiled policy, selections, expectations, Scenario world and profile are sealed together. |
| Baseline/effective Scenario comparison | supported | Same plan/profile executes against both worlds and yields program/result differences. |
| Immutable Policy/rule comparison | supported | Base and candidate targets are independently compiled and pinned; no mutable Policy patch. |
| Native, Soufflé, ProbLog result parity | supported, narrow profile | Each receives the identical materialized effective relation and canonical Query lowering. |
| Detached replay | supported | Re-executes only from captured inputs/profile; no live Store/current-latest fallback. |
| Explain continuity | supported | Explain consumes the exact captured run and explicit row/summary target; it never reruns against mutable current state. |
| Common proof equality | rejected | Engine evidence stays engine-specific; FactGraph projects it onto the same Policy structure where mapping is valid. |
| General historical ledger replay | rejected | A captured world proves reproducibility of its captured inputs, not full ledger history or source truth. |

### 3.4 Evidence and assessment

| Capability | Final disposition | Contract |
| --- | --- | --- |
| Policy/effective-world/execution evidence | supported | A Scenario/variant envelope composes existing EvidenceGraph/Policy structure with operation provenance and run pins. |
| Result/expectation/completeness/parity axes | supported | FactGraph emits typed technical assessment axes, not one overloaded boolean. |
| Translation confidence, source authority, Agent contract, review/block decision | Meander-owned | Meander adds these outer assessment axes and product disposition. |
| Formal proof of external operator internals | rejected | Provider evidence proves input/output receipt only unless the provider supplies its own structured subtrace. |
| Action authorization/side effects | rejected | Action remains a separate Decide/PEP/executor path. |

## 4. Decision

### 4.1 One immutable QueryPlan v1

A Query builder may still expose fluent convenience methods, but its terminal
artifact is one immutable QueryPlanV1. It contains a resolved Rule, Policy or
materialized-relation target; ordered bind/select inventory; typed result mode
and expectations; an optional ScenarioSpecV1; an exact execution profile; and,
when requested, an immutable candidate target for comparison.

The existing TargetedCompiledEvaluationQueryV0, EvaluationRunBundleV0,
CapturedEvaluationQueryRunV0 and ScenarioRunV0 remain readable and retain
their old seals. QueryPlanV1 is a new, explicitly versioned protocol rather
than an in-place widening of those wire shapes.

### 4.2 ScenarioSpec v1 and resolver ownership

ScenarioSpecV1 is an unordered collection of caller-declared premise
statements. Each statement has an opaque premise id, a typed grounded target,
an operation kind, a canonical value or relation tuple where applicable, and
opaque caller origin references.

FactGraph owns this pipeline:

1. pin baseline admissibility/view and target dependencies;
2. resolve entity, field, relation, cardinality and value domains against the
   trusted schema;
3. reject unresolved, derived, identity-mutating, non-grounded or conflicting
   statements;
4. canonicalize the operation set and retain all premise origins;
5. construct immutable baseline/effective finite relations;
6. seal separate semantic-world and resolution-evidence digests; then
7. execute only the fully resolved world.

Partially resolved worlds cannot execute. Baseline multi-value/cardinality
ambiguity is a typed resolver failure, not source-priority selection. FactGraph
does not look up SourceRecords or decide which caller origin is authoritative.

### 4.3 Absence and closure

OMITTED, MISSING, EXCLUDED, EMPTY_BY_SCENARIO and NEGATED are distinct states.
EvidenceScope.ignore yields EXCLUDED only: it changes admissible baseline
evidence and cannot prove absence. In contrast, Scenario.without yields an
exact EMPTY_BY_SCENARIO target and a closure declaration only for that exact
field/member/relation/entity target. It does not create a permanent negative
fact or a global closed world.

The portable deterministic profile remains positive and does not expose
general Rule/Policy NAF. It does support one separately typed, query-local
exact-absence check: an exact Scenario closure may prove that the exact
grounded field/member/relation/entity target has no tuple in this captured
effective world. It is checked against the sealed relation, not inferred from
an engine's general closed-world behavior, and all three engines must first
pass the same conformance cell. A target that requires broader negation returns
a typed CLOSURE_REQUIRED or PORTABLE_NEGATION_UNSUPPORTED assessment before
execution. Explicit signed predicates and published global closure policy are
reserved for a future independently authorized contract.

### 4.4 Rule and Policy changes

Rules and Policies are immutable values. A what-if rule change is expressed as
a separately compiled candidate Rule/Policy target, not as a mutation or
in-place overlay. Comparison executes base and candidate against one identical
effective world/profile and returns:

- structure/program difference;
- normalized result difference; and
- separately scoped evidence for explicit selected rows.

It does not infer minimal repair, change policy publication, or authorize a
candidate Policy.

### 4.5 Relation providers

Rule, Policy and RelationProvider participate in one Query-target interface:
they expose typed input/output ports and a version/digest contract. They are
not declared semantically identical.

ComputeProvider is deterministic, side-effect-free computation with fully
bound inputs. LookupProvider is a bounded read that materializes a finite
typed relation and receipt before lowering/execution. Both are converted to a
sealed relation snapshot before the native, Soufflé or ProbLog engine sees
them. Providers may not perform writes, open implicit network calls during
engine evaluation, leak untyped values, or claim FactGraph proof of their
internal implementation.

### 4.6 Portable execution profile

PortableProfileV1 means:

- the same QueryPlanV1, resolved Scenario world and canonical tuple codec;
- the same positive deterministic Rule/Policy lowering;
- native, real Soufflé and real ProbLog executions with no silent fallback;
- normalized row-set comparison and typed per-engine status; and
- a fail-closed incompatibility result for unsupported constructs.

It includes positive predicate atoms, safe typed equality/order comparisons,
Policy All/Any/Unify/Compare, finite extensional relations, and the separately
typed exact-local-absence check described in §4.3. It excludes general public
Rule/Policy negation, aggregates, recursion whose engines disagree under the
declared profile, probabilistic facts/confidence semantics, arbitrary external
functors, engine-specific configuration, bag semantics and fallback execution.

One engine may be selected for a non-portable execution profile, but that run
must say portable_parity=not_requested rather than imply parity.

### 4.7 Result, completeness and expectations

Query results model row enumeration, existence, count and set separately.
An execution can report a complete enumeration only if the selected profile
ran to its bounded completion without truncation/resource failure. Expectations
are evaluated over the captured normalized selected rows and must retain:

- expected operand inventory;
- outcome;
- completeness basis;
- explicit matching/nonmatching row references where applicable; and
- an expectation digest.

An absent row becomes not_satisfied only under complete enumeration. Otherwise
it is unresolved or unsupported, never false.

### 4.8 Run, Explain, replay and evidence

EvaluationRunV1 seals:

- QueryPlanV1 and target pins;
- baseline/effective world and resolution evidence digests;
- exact execution profile/config/engine-adapter versions;
- per-engine normalized results and parity assessment;
- result mode/completeness/expectations;
- captured relation and permitted provider receipts; and
- explicit row/summary anchors for Explain.

Replay validates the codec and re-executes only against captured relation data.
It fails explicitly on missing profile/adapter/material and never falls back to
the current Store, latest Policy, current schema or current configuration.

EvidenceGraph remains the inner logical evidence type. EvaluationRunV1 adds
the Policy structure, operation envelope and engine evidence reference around
it. Logical Policy nodes can only be HOLDS, FAILS or NOT_REACHED. A zero-row
summary is not a synthetic failed node or negative proof.

### 4.9 Assessment boundary

FactGraph exposes typed technical axes:

- contract validity;
- Scenario resolution and exact-local closure;
- per-engine execution;
- portable parity;
- result completeness;
- expectation status;
- Explain/replay availability; and
- capability rejection.

It does not emit supported/valid product verdicts, Translator confidence,
SourceRecord authority, tenant policy, human review or enforcement action.
Those form Meander's outer assessment.

## 5. Rejected alternatives

### Reuse v0 Scenario DTOs as the generic contract

- **Why rejected**: their identity and compatibility behavior were designed
  around visible scalar replacement and cannot honestly represent add/mask/
  relation/entity operations.

### Let Meander translate premises into assertion-level overlays

- **Why rejected**: it duplicates cardinality, identity, conflict and snapshot
  resolution outside the FactGraph owner.

### Treat all engine outputs or proofs as interchangeable

- **Why rejected**: result parity is meaningful in a restricted profile;
  proof/provenance structures differ and must remain labelled.

### Make external providers ordinary arbitrary engine predicates

- **Why rejected**: it makes snapshots, replay, timeout/error semantics and
  source custody engine-dependent and unauditable.

### Add closed-world semantics by interpreting zero results

- **Why rejected**: zero rows, masked rows and incomplete enumeration are
  different claims. Closure needs an explicit future policy contract.

## 6. Consequences

### 6.1 Earlier decisions

Q7/Q11/Q13/Q16 v0 values remain compatibility surfaces. Q8/Q9/Q12/Q14/Q15
remain the compiler/query/evidence substrate. Their prior exclusions of
generic Scenario, expectation modes, portable execution and provider targets
are superseded only for the new v1 protocols described here. Q17's native NAF
observation remains evidence, while its lack of a public semantic contract is
resolved here by rejecting public portable NAF rather than promoting it.

### 6.2 Meander boundary

Meander can make an L3 Plan compile to QueryPlanV1, but it must separately
handle policy publication/Package lookup, Agent permissions, SourceRecord
resolution, translation/abstention, product assessment, UI and Actions.
FactGraph intentionally accepts neither raw agent text nor tenant authority.

### 6.3 Required implementation form

The implementation must use new v1 protocols/adapters where semantics widen,
preserve v0 byte/digest behavior, provide exhaustive conformance fixtures,
and reject any final-matrix cell that it cannot support exactly. It may not
rename a deferred/rejected cell as implicitly supported.

## 7. Acceptance criteria

- [ ] All four matrices have tests proving each supported cell and each
  rejected/Meander-owned boundary.
- [ ] Scenario resolution is deterministic, canonical, non-persistent,
  conflict-total and usable without Meander.
- [ ] Rule, Policy and materialized relation providers run through QueryPlanV1
  without a second evaluator or string address grammar.
- [ ] Native, real Soufflé and real ProbLog agree on the declared portable
  corpus or the run fails with an explicit incompatibility/parity outcome.
- [ ] Each execution/run captures exact inputs; Explain/replay never reads
  current mutable Store state.
- [ ] Zero-result, incomplete-result, unsupported and not-satisfied states
  remain distinguishable through Result, Expectation and Assessment.
- [ ] Policy variant comparison is immutable and keeps base/candidate evidence
  and row anchors separate.
- [ ] Existing v0 Query, F4 and Scenario codec/behavior cohorts remain
  compatible.
- [ ] Module docs and final capability tables distinguish shipped support from
  rejected and Meander-owned capabilities.

## 8. Decision record

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-14 | adopted | User authorized final FactGraph closure | Replaces fragmented v0 non-scope boundaries with one explicit complete/rejected matrix. |
