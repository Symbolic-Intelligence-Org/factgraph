# Application Protocol — V0 EvaluateResult and V1 GoalPlan / Run Surface

- Scope: `src/factgraph/application/protocol/evaluate_result.py`,
  `explanation_render.py`, and the private R3d receipt-inventory DTOs
- Last updated: 2026-08-30
- Audience: SDK layer maintainers, adapter writers, and test authors

This document covers the V0 evaluate-result / explain slice and the separate
Q18 V1 GoalPlan / Scenario / EvaluationRun protocol family. The published
stored-relation query DTOs in `relation_query.py` are documented with their
compiler/runtime boundary in
`src/factgraph/application/docs/relation_query.md`. Other protocol files
(`derivation.py`, `entity_read.py`, etc.) are covered by the application
overview doc at `src/factgraph/application/docs/01_overview_en.md`.

---

## 1. Scope

`evaluate_result.py` owns:

- `EvaluateRow` — one result row from a derivation evaluation run
- `EvaluateResult` — the full evaluation envelope (rows + head + fingerprint)
- `ResultFingerprint` — immutable digest bundle for reproducibility
- `Explanation` — the output of `EvaluateRow.explain()`
- `explain_row(row, result)` dispatch logic (internal entry point `_explain_live_row`)
- Evidence builder dispatch: SDK prober graph builder → protocol fallback paths-model graph

`explanation_render.py` owns:

- `walk_evidence(graph, ...)` — deterministic text rendering over `EvidenceGraph(paths=...)`

`captured_receipt_evidence.py` owns an application-internal R3d trio:
`CapturedReceiptConditionV0`, `CapturedReceiptBranchV0`, and
`CapturedReceiptEvidenceV0`.  They are immutable nested-sealed inventory
records for one selected native receipt branch only.  Their approved builder
first takes a fully validated canonical bundle snapshot, then selects a row;
the DTOs themselves have no codec or Store/ledger/cache/sidecar/registry/
evaluator behavior.  They carry no values, source metadata, certainty,
Policy/Rule attribution, verdict, `EvidenceGraph`, or `Explanation`.  Their
seals are integrity checks, not authenticity, source/admission/governance,
authorization, business truth, proof parity, verification, or replay.  Fixed
`unverified`, `not_performed`, and `not_claimed` labels are availability
boundaries, not falsehood.  This private detail is deliberately not imported
by `factgraph.application` or `factgraph.application.protocol`, and is not a
Product, SDK, Meander, Agent, or MCP contract.

---

## 2. Responsibilities

### 2.1 `EvaluateRow`

A single row from a derivation evaluation. Carries the bound head values
and row-level digests.

```python
@dataclass(frozen=True)
class EvaluateRow:
    row_id: str
    bindings: Mapping[str, Any]               # {port_name: term_value}
    kind: ClaimKind                           # "fact_triple" | "rule_head" | "aggregate_result" | "projection"
    digest: str                               # sha256 claim digest
    closed_head_digest: str                   # sha256 closed-head digest
    certainty: Certainty | None               # boolean/probabilistic/possibilistic interval
```

The `explain()` method returns an `Explanation` via `_explain_live_row(self, result)`.
The `close()` method returns a closed `Rule` from the row bindings.

`EvaluateRow` is live (attached to a result resolver) or detached. Calling
`explain()` on a detached row raises `DetachedRowError`.

---

### 2.2 `ResultFingerprint`

Immutable digest bundle stamped at evaluation time:

```python
@dataclass(frozen=True)
class ResultFingerprint:
    expr_digest: str
    rule_set_digest: str
    view_snapshot_digest: str
    config_digest: str | None
    result_digest: str
    run_id: str
```

All digests are SHA-256 tokens. `config_digest` is `None` when no
`SemanticsProfile` was used (native default semantics).

---

### 2.3 `EvaluateResult`

The full evaluation envelope:

```python
@dataclass(frozen=True)
class EvaluateResult:
    result_id: str
    rows: tuple[EvaluateRow, ...]
    head: Rule
    engine: str
    evaluated_at: object
    fingerprint: ResultFingerprint
    engine_meta: Mapping[str, Any]
    run_anchor: EvaluationRunAnchorV0 | None = None
    run_bundle: EvaluationRunBundleV0 | None = None
    scenario: ScenarioResolutionV0 | ScenarioFieldSubstitutionSetResolutionV0 | None = None
```

Private fields (not compared / not repr'd):
- `_schema_index` — `ApplicationSchemaIndex` for explain repr baking
- `_row_close_builder` — injected by SDK for entity-ref aware row closing
- `_row_support_artifacts` — `{row_id: ProofReceipt}` for native/souffle Form 1 rows
- `_row_provenance_envelopes` — `{row_id: ProvenanceEnvelope}` for ProbLog/PyReason rows
- `_scenario_resolution_digest_pin` — private result-local seal that prevents
  later substitution of different Scenario metadata

Iteration / indexing:
- `result[i]` → `EvaluateRow`
- `for row in result:` iterates rows
- `result.first()` → `EvaluateRow | None`
- `result.exists()` → `bool`
- `result.count()` → `int`

**Deprecated flat properties** (emit `DeprecationWarning`; use `fingerprint.*` or `engine_meta.*` instead):

| Deprecated property | Replacement |
|---|---|
| `result.run_id` | `result.fingerprint.run_id` |
| `result.engine_version` | `result.engine_meta["engine_version"]` |
| `result.adapter_version` | `result.engine_meta["adapter_version"]` |
| `result.rule_set_digest` | `result.fingerprint.rule_set_digest` |
| `result.view_snapshot_digest` | `result.fingerprint.view_snapshot_digest` |
| `result.config_digest` | `result.fingerprint.config_digest` |
| `result.result_digest` | `result.fingerprint.result_digest` |

`result.expr_digest` was removed entirely in Cleanup-β (2026-06-08) — use `result.fingerprint.expr_digest`.

Compiled native `EvaluationQuery` execution always attaches the identity-only
`run_anchor`. With the explicit `capture="run_bundle_v0"` option it also
attaches `run_bundle`, a strict canonical and size-bounded detached audit
artifact. The bundle captures sensitive typed values, exact plan/schema,
effective dependency relations, rows and ProofReceipts. It is integrity-sealed
but not authenticated, has caller-managed custody, and exposes neither replay
nor detached Explain. Ordinary evaluation leaves `run_bundle=None`; capture
cannot be added post hoc.

An `EvaluationQuery` selection can also be a sealed
`EvaluationQueryNavigationSelectionV0`: one Query-owned identity-to-same-entity
single scalar-field lookup. Its parallel `EvaluationRunNavigationSelectionV0`
keeps historical direct-selection anchor/bundle shapes unchanged. The lookup is
recorded as Query-owned materialization outside Policy lineage. Live Explain
uses the exact native `ProofReceipt` binding inventory for its base identity;
if that receipt is unavailable, it fails closed rather than guessing from a
projected scalar value. Captured detached evidence likewise labels the lookup
outside Policy lineage.

The only exception is a Scenario compiled Query result. It has either the
single-field `ScenarioResolutionV0` or the atomic multi-field
`ScenarioFieldSubstitutionSetResolutionV0` in `scenario`, but it **must not**
carry a run anchor or run bundle. Its fingerprint's view-identity position is
the sealed run-local effective-relation identity, not a claim of a ledger
snapshot. `EvaluateResult` also privately pins the attached Scenario-resolution
digest, so a later `dataclasses.replace()` cannot attach metadata that describes
a different hypothetical result. Scenario rows deliberately reject `close()`
and return an unsupported result from `explain()`: the existing
live-EvidenceGraph contract refers to asserted ledger facts and is not valid
evidence for a hypothetical replacement. See
`src/factgraph/application/docs/rule.md` for the replacement-only scope.

The internal resolver also returns a parallel `QueryEffectiveSnapshotV1` for
its caller. It has pre-evaluation, Query-dependency-relation identity only and
is intentionally not embedded in `EvaluateResult`, ScenarioRun v0 wire, or a
public replay codec. Its digest excludes the later result diff; the legacy
Scenario DTOs above intentionally do not. See the application Rule contract
for its non-global/non-historical boundary.

`ScenarioRunV0` is a separate protocol value rather than a wider
`EvaluateResult` variant. It is entered explicitly through
`fg.eval.run_scenario(compiled_or_targeted_query, scenario)` or the terminal
Query builder form `.what_if(scenario).run()`. It seals two opaque,
Scenario-framed captures (baseline and effective), their exact shared Query
contract, a resolver-produced premise binding inventory, public typed row
summaries and the result multiset diff. Its `.diff()`, `.verify()` and
`.explain(side=..., row_capture_digest=...)` are detached: they never consult
a current Store after capture. The generic `EvaluationRunBundleV0` decoder
does not accept the framed bytes, because Scenario-aware evidence must relabel
synthetic witnesses as `scenario_hypothesis` rather than ordinary
`captured_witness` sources. This sealed capture is not authenticated,
historical replay, or a claim that the caller-declared premise is true.

The separate F4C `PolicyExplanationViewV0` is intentionally not an
`Explanation` field and is not produced by `EvaluateRow.explain()`. Its normal
composition projects detached F4B3 evidence through a matching
`EvaluationRunAnchorV0`; as a pure value projector, it may also consume another
`EvidenceGraph` that satisfies the same anchor and lineage checks. It does not
create, attach, or change live-Explain lifecycle semantics. See
`src/factgraph/application/docs/rule.md` for that readonly, total-or-error
composition contract. This preserves the existing lazy live-Explain behavior.

---

### 2.4 `Explanation`

The output of `EvaluateRow.explain()`:

```python
@dataclass(frozen=True)
class Explanation:
    status: ExplanationStatus                    # "passed" | "failed" | "unsupported" | "invalid_request"
    evidence: EvidenceGraph | None
    row: EvaluateRow | None
    result_id: str | None
    failure_class: ExplanationFailureClass | None
    checked_scope: Mapping[str, Any] | None
    suggested_next_steps: tuple[str, ...]
    errors: tuple[ErrorDTO, ...]
    warnings: tuple[WarningDTO, ...]
```

**S5 evidence invariant** (locked 2026-06-09):

```
status in {"passed", "failed"}  ↔  evidence is not None
status in {"unsupported", "invalid_request"}  ↔  evidence is None
```

`Explanation.__post_init__` enforces this invariant via `ProtocolShapeError`.

Status semantics:

| Status | Meaning |
|---|---|
| `"passed"` | Row passed; `evidence` is a complete `EvidenceGraph(paths=...)` |
| `"failed"` | Logical failure with probe evidence; `evidence` is a probe-result `EvidenceGraph` |
| `"unsupported"` | Request context is invalid (stale row, protocol error); `evidence=None` |
| `"invalid_request"` | Malformed input; `evidence=None` |

`failure_class` is set only when `status == "failed"`:

| Value | Trigger |
|---|---|
| `"closed_head_false"` | Derivation head does not hold; `probe_native` result attached |

Stale rows and rows that no longer belong to their result are protocol/request
problems, not logical failures. They return `status="unsupported"`,
`evidence=None`, and an `ErrorDTO` (`STALE_ROW` or `ROW_NOT_IN_RESULT`).

`Explanation.repr` property returns text lines from `walk_evidence(...)` for
`passed`/`failed` status; returns `None` for `unsupported`/`invalid_request`.

---

### 2.5 Evidence builder dispatch

`_explain_live_row` is protocol-only. It does not import the store or the native
prober directly. The SDK attaches a private row graph builder to native
`EvaluateResult` objects; that builder closes over the lowering plan and
projected view facts and calls `probe_native(...)`.

1. **Native passed row**:
   - `EvaluateRow.explain()` uses the SDK-attached graph builder.
   - The builder returns the prober's paths-model `EvidenceGraph`, including
     head/body rules, atom verdicts, joins, and baked `repr_text`.

2. **Native closed-head false**:
   - `fg.eval.explain(..., head=closed_head)` calls `probe_native(...)` even
     when no result row matches.
   - Returns `status="failed"` with `failure_class="closed_head_false"` and
     non-empty probe evidence.

3. **Protocol fallback**:
   - If no SDK graph builder is attached, protocol builds a minimal paths-model
     `EvidenceGraph` with a single head rule.
   - This fallback preserves the evidence invariant without resurrecting the
     removed flat-DAG model.

4. **Adapter rich rows**:
   - Souffle, ProbLog, and PyReason rows use SDK-attached builders over
     `_row_support_artifacts` / `_row_provenance_envelopes`.
   - Those builders return the same paths-model evidence graph shape as native
     explain paths.

All returned graphs have `metadata` matching the v1 row-result key set:
`result_id`, `row_id`, `evidence_ref_id`, `claim_digest`, `closed_head_digest`,
`expr_digest`, `rule_set_digest`, `view_snapshot_digest`, `config_digest`,
`result_digest`, `engine`, `engine_version`, `adapter_version`, `evaluated_at`.

---

### 2.6 `walk_evidence`

```python
def walk_evidence(
    graph: EvidenceGraph,
    *,
    row: object | None = None,
    status: str = "passed",
    failure_class: str | None = None,
) -> tuple[str, ...]:
```

Walks an `EvidenceGraph(paths=...)` and produces deterministic plain-text lines.
Used by `Explanation.repr`. Each path in `graph.paths` is rendered recursively:
- `EvidenceTree` → rule/atom lines with repr_text and verdict
- `EvidenceTimeline` → event lines

---

## 2.7 Q18 V1 GoalPlan / Scenario / EvaluationRun

The following protocol modules form a new, independently versioned contract:

- `goal_plan_v1.py` — immutable target, result-mode, expectation, selected-row,
  summary-anchor, and technical-assessment DTOs;
- `scenario_v1.py` — grounded Scenario declaration, exact-local closure,
  evidence-admission scope, resolved operations, and frozen effective world;
- `relation_provider_v1.py` — one restricted pre-engine finite-relation
  materialization boundary; and
- `evaluation_run_v1.py` — execution profile, per-engine frame, sealed replay
  payload/program envelope, explicit Explain target, and completed Run.

They do not revise V0 `EvaluateResult`, `EvaluationRunBundleV0`,
`CapturedEvaluationQueryRunV0`, or `ScenarioRunV0`. A caller may retain those
values and their original codecs while separately creating a `GoalPlanV1`.

### 2.7.1 GoalPlan, modes, and expectations

`GoalPlanV1` seals an exact target pin, compiler-owned Query digest, ordered
typed selections, one of `rows` / `exists` / `count` / `set`, optional
Scenario/profile digests, a typed expectation inventory, and an optional
independent Rule/Policy candidate pin. It has no current Store, adapter,
source-authority, or product-verdict reference.

`GoalResultV1` is a canonical **set** of `GoalResultRowV1` values. A proof
path is not a second row. Result completeness is independently one of
`complete`, `incomplete`, `resource_limited`, `unsupported`, or `unknown`.
`exists=false`, absent `contains_row`, and a count/set expectation can be
`not_satisfied` only when their required enumeration is complete. Otherwise
the expectation outcome remains `underdetermined` or `unsupported`.

`ExactLocalAbsenceExpectationV1` is different: it names an
`ExactLocalClosureTargetV1` created by the same resolved Scenario. Its outcome
is checked against the sealed effective relation rather than inferred from an
empty selected result or from engine negation.

`GoalTechnicalAssessmentV1` reports technical axes (contract, Scenario
resolution/closure, execution, parity, completeness, expectation, Explain,
replay, and capability). It never means `SUPPORTED`, `VALID`, source-authoritative,
or approved in a product sense.

### 2.7.2 Scenario and evidence admission

`ScenarioSpecV1` is an unordered tuple of typed, grounded premise operations.
The resolver validates every entity/field/relation/value/cardinality condition,
canonicalizes the whole set, retains opaque origin references, and either emits
one immutable baseline/effective-world pair or a typed failure. It never
partially applies a scenario or writes a premise into the ledger.

`EvidenceScopeV1` only removes named baseline assertion ids from admission.
It has no negative or closure semantics. `ScenarioWithout*` operations instead
create exact local closure for their exact field/member/relation/entity/assertion
target. Generic `NotAtom`, global closed-world reasoning, signed negative
facts, and source-priority selection are outside this protocol.

### 2.7.3 Provider boundary and profiles

Rule and Policy are the only logical Query targets.  `RelationProviderV1` is
attached to one of those targets through the composite
`ProviderQueryTargetV1(base, provider)` / SDK `.using(provider)` form; a bare
provider has neither a head, projection nor address space and is rejected
before compilation.  A provider can be `compute` or `lookup`, but both must
materialize one finite typed relation and receipt **before** the evaluator sees
a world.
`ProviderRequestV1` binds the provider digest, required structured Query
bindings, dependency/supplied predicate inventory, and an opaque request
digest. `ProviderMaterializationV1` replaces exactly the provider's declared
predicate subset; an explicit empty output is therefore meaningful. Provider
code is not treated as a FactGraph proof.

The callback receives no Store argument, but an in-process callback remains
trusted code rather than a sandbox. The GoalPlan runtime pins the source view
immediately before and after materialization and rejects a persistent change;
this detects a callback that mutates the captured world, but it is not a
rollback or authorization mechanism.

`EvaluationExecutionProfileV1` has a zero-config native deterministic form or
the strict portable deterministic form. The portable form attempts native,
real Soufflé, and real ProbLog over the same declared positive subset with no
fallback. Per-engine outputs remain separate `succeeded`/`failed`/`unsupported`
frames; only three successful matching normalized selected-row sets may be
called equivalent.

### 2.7.4 Run, replay, Explain, and candidate comparison

`EvaluationRunV1` seals the primary plan/profile, baseline/effective world
captures, canonical and per-engine results, technical assessments, optional
candidate-effective result, and a bounded replay payload. The payload has a
strict codec and contains relation facts, schema/program envelope, allowed
provider receipts, and exact world/closure pins. Integrity seals detect
inconsistent mutation/splicing; they are not artifact authentication.

`replay_evaluation_run_v1(...)` reads only this capture and re-executes the
sealed program/relation. It does not call a provider or access the current
Store. A re-execution mismatch is a typed replay observation, not hidden
fallback or proof of an external cause.

`ExplainTargetV1` must name a side plus one exact row or summary anchor.
`explain_evaluation_run_v1(...)` never selects a first row by position. The
Run captures a bounded native Explain context (pinned target, lineage, Rule
pins and restricted lowering material). For an explicit positive row it
lazily re-executes Native **only over the sealed captured relation**, verifies
the sealed result again, and returns an inner `EvidenceGraph` plus an
`EvaluationRunPolicyProjectionV1` that projects the authored Policy nodes as
`holds` / `fails` / `not_reached`. This is native inner evidence, not
Soufflé/ProbLog proof parity (`proof_parity="not_claimed"`). A summary,
including a zero-row summary, has `logical_conclusion="not_claimed"` and no
graph or negative proof. Older context-less captures remain
`engine_evidence="not_captured"`; ambiguous projected row witnesses, pin or
context mismatches, and replay-result mismatches fail closed rather than
selecting an arbitrary proof.

`compare_policy_variants_v1(...)` compares independently pinned primary and
candidate compiled programs on the same effective world. It returns structural
and normalized row-set differences only; it deliberately makes no causal
attribution to a Rule, fact, provider, or Scenario operation.

`diff_scenario_run_v1(...)` is available only for a Run that sealed an
explicit `ScenarioSpecV1`. It derives baseline/effective world pins, resolved
operation references, and normalized selected-row-set differences from that
Run's capture. It makes neither an EvidenceGraph claim nor a causal claim;
ordinary Query runs cannot obtain a Scenario diff merely because the V1 Run
shape always has baseline/effective sides.

### 2.8 Product V2 Function capability

`ProductFunctionV1` is a Product asset parallel to `ProductRuleV1`; neither
type may contain or call the other. Policy is the only composition layer. An
intrinsic `PolicyFunctionOccurrenceV1` retains the Function identity, typed
ports and Rule-port input edges in the authored AST. Legacy/V1 Policy
compilation rejects this marker with `FUNCTION_V2_ONLY`, including after an
ordinary `Policy` rewrap. Only the controlled Product V2 compiler may lower it
to an internal relation-backed Rule occurrence.

The first Function protocol is deliberately narrow: at least one ordered
scalar input, one fresh scalar output, synchronous trusted in-process Python,
and pure deterministic total semantics. Inputs must be direct scalar ports of
one Rule occurrence and are branch-total. Function-to-Function edges, field
navigation, output binding, Rule-body calls, nested calls, actions, aggregate,
streaming and asynchronous output are outside the contract.

Each Function occurrence derives a reserved call-identity entity and one
binary predicate per input/output port. Per run side, V2 first evaluates the
upstream Rule projection over the sealed source world, invokes the callable
once per distinct typed input row, validates one typed output, and inserts the
port facts into an isolated execution Store. These reserved predicates never
enter the ledger. `portable_deterministic_v2` executes Native, Soufflé and
ProbLog against this same materialized relation and claims only normalized
selected-row parity, never proof parity.

`EvaluationFunctionCallV2` and `EvaluationFunctionMaterializationV2` seal each
side's call key, typed inputs/output, definition/implementation pins and
materialization digest. The V2 replay-program envelope separately seals the
Function definition, asset descriptor/binding, topology, internal schema and
compiled-program association. Detached replay validates both captures,
injects the captured relation and never receives or invokes executable code.
The structured Product Result/Explain adapters expose these definition and
call records; they do not fabricate an EvidenceGraph when native Function
evidence was not captured.

An in-process callable is trusted code, not a sandbox. V2 detects a persistent
source-view change around invocation and fails closed, but it cannot roll back
an external side effect. The durable implementation digest is caller-supplied
or derived at authoring time; the callable itself is never a replay artifact.

---

## 3. Non-responsibilities

- `evaluate_result.py` does not own adapter converters (`problog_trace_to_evidence_graph` etc.)
- `evaluate_result.py` does not own the prober (`probe_native`); SDK graph builders call it
- `evaluate_result.py` does not own the SDK `EvaluateResult` → `fg.eval.evaluate()` wrapper
- `explanation_render.py` does not produce HTML; it produces plain text
- Adapter converters are outside this module; SDK graph builders dispatch to
  them and pass paths-model graphs back through the protocol surface.

---

## 4. Limitations & Compatibility

- The `expr_digest` flat property was **permanently removed** in Cleanup-β (2026-06-08).  
  All callers must migrate to `result.fingerprint.expr_digest`.
- Other deprecated flat properties (`run_id`, `engine_version`, etc.) still exist but emit `DeprecationWarning`. They will be removed in a future slice.
- Native passed rows and native closed-head-false failures are backed by the
  prober. Souffle, ProbLog, and PyReason rich evidence is wired through
  adapter-specific SDK builders.
- `_row_provenance_envelopes` and `_row_support_artifacts` are private fields and are not part of the stable contract for external callers.
- V1 engine pins are sealed declarations, not a runtime environment attestation.
- V1 replay is relation/program replay. It is not historical ledger replay,
  artifact authentication, provider re-invocation, or an authorization decision.

---

## 5. Test Entry Points

```bash
# Core DTO shape + explain invariant + Cleanup-β
python -m pytest tests/application/protocol/test_evaluate_result_dtos.py

# walk_evidence renderer
python -m pytest tests/application/protocol/test_explanation_render.py

# Adapter dispatch (Souffle / ProbLog / PyReason rich provenance)
python -m pytest tests/test_souffle_evidence_graph.py
python -m pytest tests/test_problog_provenance_v0.py
python -m pytest tests/test_pyreason_provenance_v0.py

# SDK exports / fingerprint
python -m pytest tests/sdk/test_evaluate_result_exports.py

# Q18 V1 protocol/runtime/export smoke tests
python -m pytest tests/application/protocol/test_goal_plan_v1.py
python -m pytest tests/application/protocol/test_evaluation_run_v1.py
python -m pytest tests/application/test_evaluation_run_v1_runtime.py
python -m pytest tests/test_v1_public_surface_exports.py
```

---
