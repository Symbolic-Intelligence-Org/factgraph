# T4.3 Closed-Head Inspect Utilities + Docs

Status: draft
Class: M
Branch: `v0.2.0-t4-3-closed-head-inspect-docs-2026-05-25`

Lifecycle note: This blueprint follows the T3/T3L/T4 cadence: draft -> draft-amend if needed -> scoped after Step 4.6 grep -> G7 baseline -> feature -> Step 4.7 review/fix if needed -> closure -> archive -> memory consolidation.

## 0. Scope Locks

In scope:

1. Implement D15 closed-head inspect reporting on the existing public `RuleExprInspect` value: `is_closed: bool` and `unbound_ports: tuple[str, ...]`.
2. Compute closed-head status for application `Rule` inspect values returned through `fg.rules.inspect(rule)`.
3. Preserve RuleExpr structural inspection without defining a closed-head guarantee for arbitrary `RuleExpr` values.
4. Use D15 strict v1 closure forms only: direct literal equality for value ports, primary-identity predicate literals for entity-ref ports, projection-head closed-by-construction recognition, and conservative missing-schema handling.
5. Reuse T4.1/T4.2 private substrate where appropriate: declared ports, `Rule.projection(...)` recognizer behavior, and private head metadata boundaries.
6. Pass SDK schema context from `SDKStore.inspect_rule(...)` into application-rule inspection so entity-ref closure can use the existing schema index.
7. Update user-facing docs to describe shipped T4 head execution plus closed-head inspect reporting.

Out of scope:

1. No T5 `EvaluateResult`, Explanation, WhyNot, `row.close()`, public trace, or public evidence surface.
2. No T1.3 final SDK `Rule` flip.
3. No adapter grammar expansion or adapter production file edit.
4. No new public error subclass.
5. No public `expr.declared_ports` export.
6. No public DTO export for closed-head internals, projection internals, or head-link internals.
7. No `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, `CompiledDerivationPlan`, or result-shape change.
8. Public evaluation success remains `list[CandidateSet]`.
9. Legacy SDK `Inference` and derivation-dict evaluation paths remain unchanged.
10. No relaxation of `Rule.where` or `Rule.ports` non-empty invariants.
11. Projection placeholder atoms and D13 head-link metadata must not leak into runtime traces, adapter requests, or public evidence.
12. No general literal-closure algorithm beyond D15 strict v1.
13. No transitive closure inference for value or entity-ref ports.
14. No "must be closed" validation gate; T4.3 reports inspect metadata only.

M-to-L triggers:

1. If implementation needs a new public result object, public evidence shape, or exported closed-head DTO, stop and amend.
2. If implementation needs adapter grammar changes or adapter production edits, stop and amend.
3. If implementation needs a global relaxation of `Rule.where` or `Rule.ports`, stop and amend.
4. If docs require T5 `EvaluateResult`/WhyNot/row-close semantics to explain the feature, stop and split.
5. If schema-runtime integration requires a new schema API rather than using the existing `SchemaIndex`, stop and amend.

## 1. Inputs

Canonical design inputs:

1. `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md` - Stage 1 audit, especially F7/F8/F9 and Q6/Q7/Q8/Q9.
2. `workflow/design/decisions/active/2026-05-25_t4-d15-closed-head-inspect.md` - D15 reviewed clean v2, especially sections 4.1-4.10.
3. `workflow/audit/active/2026-05-25_post-q-t4-head-closed-head-synthesis.md` - Stage 3 synthesis T4.3 slice definition.
4. `workflow/blueprints/archive/2026-05-25_t4-1-head-identity-declared-port-foundation.md` - T4.1 declared-port and identity substrate.
5. `workflow/blueprints/archive/2026-05-25_t4-2-external-projection-head-execution.md` - T4.2 external/projection head execution substrate.
6. T3.5/T3.6 inspect/docs precedent for additive inspect fields and docs-only discipline.

Current shipped source read before draft:

1. `src/factgraph/application/protocol/rule_expr_inspect.py:36-49` - `PortInspect`.
2. `src/factgraph/application/protocol/rule_expr_inspect.py:89-136` - `RuleExprInspect` public fields and `ports` property.
3. `src/factgraph/application/protocol/rule_expr_inspect.py:155-172` - application Rule and RuleExpr inspect entry points.
4. `src/factgraph/sdk/store.py:700-728` - SDK store initialization and `_application_schema_index`.
5. `src/factgraph/sdk/store.py:2102-2111` - `SDKStore.inspect_rule(...)` dispatch.
6. `src/factgraph/application/schema_runtime.py:13-57` - schema identity metadata dataclasses.
7. `src/factgraph/application/schema_runtime.py:82-112` and `:189-222` - `SchemaIndex` construction and identity predicate metadata.
8. `src/factgraph/application/protocol/rule_expr_lowering.py:277-300` - T4.1 `RuleExprHeadValidation`.
9. `src/factgraph/application/protocol/rule_expr_lowering.py:321-363` and `:726-793` - T4.2 materialization and private trace sidecar.
10. `tests/sdk/test_ruleexpr_inspect.py` - existing public inspect tests.
11. `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`, `00_user_guide.en.md`, `01_concepts.en.md`, and `src/factgraph/application/docs/rule.md` - docs surfaces to update.

Pre-draft grep summary:

1. `_validate_rule_expr_head_foundation` has one production SDK caller and helper tests; no hidden T4.3 consumer.
2. `_materialize_branch` / `_materialize_adapter_derivation_plan` have existing protocol/SDK consumers; no T4.3 production owner.
3. `RuleExprHeadValidation.declared_ports` has no production downstream reader beyond existing T4.2 materialization paths.
4. `is_closed`, `unbound_ports`, and `closed_head` have no production implementation owner.
5. `RuleExprInspect` fields remain the only public inspect extension point.
6. T5 guard terms have only pre-existing docs/tests/surfaces; no T4.3 production owner.
7. Adapter guard terms have only existing adapters/tests/docs; no T4.3 adapter target.

## 2. Proposed Shape

### 2.1 Public Inspect Surface

Extend the existing `RuleExprInspect` dataclass with two additive fields:

1. `is_closed: bool = False`
2. `unbound_ports: tuple[str, ...] = ()`

These fields are intentionally added to the existing inspect value instead of introducing a new public DTO. Defaults preserve existing constructor behavior and preserve RuleExpr structural inspect values that do not define a closed-head guarantee.

Application Rule inspect values compute real closed-head status. RuleExpr structural inspect values keep the conservative default: `is_closed=False` and `unbound_ports=()`, because D15 does not define a closed-head guarantee for arbitrary structural RuleExpr inspection without a head context.

### 2.2 Closed-Head Helper

Add a private helper in `rule_expr_inspect.py`, such as:

```python
@dataclass(frozen=True)
class _ClosedHeadInspect:
    is_closed: bool
    unbound_ports: tuple[str, ...]
```

The helper evaluates only application `Rule` values and uses D15 strict v1 semantics:

1. Empty port sets are impossible under shipped `Rule.ports` validation, so no special empty-head path is added.
2. For value ports, a port is closed only by a direct user-authored equality atom in `head.where`: `CmpAtom("eq", Var(port), Const(value))` or `CmpAtom("eq", Const(value), Var(port))`.
3. For entity-ref ports, a port is closed only when every primary identity field for the port's entity type has a user-authored identity `PredAtom(identity_predicate_id, [Var(port), Const(value)])`.
4. Missing schema index, missing entity type metadata, or missing identity predicate metadata is conservative: the entity-ref port is reported unbound.
5. Projection rules recognized by the T4.2 projection recognizer are reported closed by construction with no unbound ports. D12 validation still owns evaluation-time projected-port validity.
6. The helper operates on user-authored `head.where` atoms, not on D13 runtime-augmented head-port link atoms.

No helper result is exported from `__all__`.

### 2.3 SDK Schema Context

`SDKStore.inspect_rule(...)` should pass `self._application_schema_index` into the application-rule inspect helper. Direct protocol-level helper calls without schema context remain conservative for entity-ref closure.

This is an inspect-only schema read. It must not affect evaluation, materialization, write planning, or adapter behavior.

### 2.4 Error And Warning Buckets

T4.3 does not add new public error or warning types.

1. Inspecting unsupported object types continues to use the existing SDK inspect bucket.
2. Malformed application protocol values continue to use existing `RuleExprError` / `RuleValidationError` buckets from construction or inspection validation.
3. Open heads are not errors. They are reported with `is_closed=False` and `unbound_ports`.
4. Future "must be closed" caller gates belong to T5 and may later raise `RuleExprError`; T4.3 only reports inspect metadata.

### 2.5 Docs Update

Update docs in the T3.6/T3L.3 style:

1. `03_rules_and_inferences.en.md`: add a compact RuleExpr head inspection subsection covering `is_closed`, `unbound_ports`, value closure, entity-ref closure, projection closure, and missing-schema conservatism.
2. `00_user_guide.en.md`: update quick reference now that T4.2 external/projection heads have shipped and T4.3 exposes closed-head inspect reporting.
3. `01_concepts.en.md`: update the public surface table for inspect metadata.
4. `application/docs/rule.md`: align application-protocol docs with T4 head behavior without promising T5 evaluation results.

Docs must not mention public `EvaluateResult`, WhyNot, Explanation, public trace/evidence DTOs, or `row.close()`.

## 3. Code Changes

Production targets:

1. `src/factgraph/application/protocol/rule_expr_inspect.py`
   - Add `is_closed` and `unbound_ports` to `RuleExprInspect`.
   - Add private closed-head helper(s).
   - Update `_inspect_application_rule(...)` to compute closed-head fields.
   - Leave `_inspect_rule_expr(...)` structural defaults conservative.
2. `src/factgraph/sdk/store.py`
   - Pass `_application_schema_index` into `_inspect_application_rule(...)`.
3. Docs files listed in section 2.5.

Test targets:

1. Extend `tests/sdk/test_ruleexpr_inspect.py` for public SDK inspect behavior.
2. Add a focused protocol test file if helper-level coverage becomes clearer there, e.g. `tests/application/protocol/test_rule_expr_closed_head_inspect.py`.

Files intentionally not touched:

1. Adapter production files.
2. `CandidateSet`, `SupportArtifact`, `EvidenceEnvelope`, and evaluation result DTO definitions.
3. T4.1/T4.2 materialization behavior except via read-only helper reuse.
4. Legacy SDK `Inference` and derivation-dict evaluation paths.

## 4. Tests

Required focused tests:

1. Application Rule with a value port closed by `Var == Const` returns `is_closed=True` and `unbound_ports=()`.
2. Application Rule with a value port closed by `Const == Var` also closes.
3. Application Rule with a value port referenced only by field predicates, builtins, membership, negation, or non-literal equality remains open.
4. Entity-ref port closes when all primary identity predicates bind the entity ref variable to literals.
5. Compound primary identity requires all primary-key identity predicates; missing one reports the port in `unbound_ports`.
6. Missing schema metadata leaves entity-ref ports unbound without raising.
7. Projection Rule inspect reports closed by construction and does not treat placeholder atoms as runtime proof.
8. RuleExpr structural inspect exposes the fields but does not claim a closed-head guarantee.
9. Existing RuleExpr inspect tests remain green and constructor compatibility is preserved.
10. Docs grep confirms no T5 public result/evidence claims.

Preservation gates:

1. G7 baseline command from T4.2, expected 155 tests OK before feature work.
2. Post-feature preservation command must increase or preserve test count.
3. Focused RuleExpr suites must include T3L/T4 tests and the new T4.3 inspect tests.
4. Touched-file ruff must be clean.

## 5. Risks

1. **Schema context boundary**: entity-ref closure depends on schema identity metadata. SDK inspect has schema context; direct protocol helpers may not. Missing schema must remain conservative.
2. **Public DTO boundary**: adding fields to `RuleExprInspect` is public. Defaults and tests must preserve existing inspect callers.
3. **RuleExpr structural ambiguity**: arbitrary RuleExpr inspect is not head inspect. T4.3 must avoid falsely claiming structural expressions are closed heads.
4. **Projection standalone semantics**: exact T4.2 projection sugar may be closed by construction, but D12 projected-port validation remains evaluation-time.
5. **Docs scope creep**: docs must describe inspect metadata only and must not pre-announce T5 `EvaluateResult`, WhyNot, Explanation, or row-close behavior.

## 6. Verification Gates

G7 baseline command:

```bash
PYTHONPATH=src python -m unittest \
  tests.application.protocol.test_rule \
  tests.application.protocol.test_rule_expr \
  tests.sdk.test_ruleexpr_inspect \
  tests.sdk.test_rule_naming \
  tests.application.protocol.test_rule_aggregate \
  tests.test_branch_identity_rule_inspect \
  tests.application.protocol.test_rule_expr_lowering \
  tests.application.protocol.test_rule_expr_lowering_adapter \
  tests.sdk.test_rule_expr_evaluate \
  tests.application.protocol.test_rule_expr_head_validation \
  -v
```

Expected G7 baseline: 155 tests OK from the T4.2 final preservation gate.

Post-feature gates:

1. Run the same preservation command; expected count increases with T4.3 tests.
2. Run focused inspect/RuleExpr tests.
3. Run touched-file ruff for production and test files edited by T4.3.
4. Do not use broad pytest in this environment; continue unittest fallback per SIGSEGV lock.
5. Continue excluding `tests.test_public_inference_factgraph_create` until the pre-existing failure is separately resolved.

## 7. Diagnostics And Rollback

Diagnostics:

1. Inspect output itself is the diagnostic surface: `is_closed` plus `unbound_ports`.
2. Open heads do not raise.
3. Missing schema metadata is visible as unbound entity-ref ports.
4. Projection heads that do not match the exact T4.2 recognizer are not treated as projection sugar by inspect.

Rollback:

1. Revert the inspect field additions and helper wiring.
2. Revert SDK schema-index passing to application inspect.
3. Revert docs updates.
4. No data migrations, adapter changes, or result-shape migrations are expected.

## 8. Reviewer Focus

1. Verify D15 strict closure forms are implemented exactly and do not grow into general proof search.
2. Verify entity-ref closure uses user-authored head atoms and schema identity metadata, not D13 runtime head-link atoms.
3. Verify RuleExpr structural inspect does not claim a closed-head guarantee.
4. Verify `RuleExprInspect` additions are backwards-compatible.
5. Verify docs do not mention T5 result/evidence surfaces.
6. Verify no adapter production files are touched.
7. Verify `Rule.projection(...)` placeholder atoms do not become closure proof for non-projection rules.
8. Verify G7 and focused test counts are recorded in the paired audit.

## 9. Implementation Plan

1. Complete Step 4.6 grep after draft review and lock scope.
2. Record G7 baseline at 155 tests OK.
3. Implement inspect fields and private closed-head helper.
4. Wire SDK schema index into application-rule inspect.
5. Add focused tests for D15 closure forms and docs guards.
6. Update docs within the bounded T4.3 docs surface.
7. Run preservation and focused gates.
8. Fill section 10 after Step 4.7 review.

## 10. Outcome

Pending.
