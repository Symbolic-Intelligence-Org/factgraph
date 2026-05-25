# D15 Decision: T4 Closed-Head Validator + Inspect Utilities

- Status: proposed
- Created: 2026-05-25
- Last Updated: 2026-05-25
- Authority: proposed design constraint; locks T4 closed-head validation and inspect placement.
- Inputs:
  - Stage 1 audit `workflow/audit/active/2026-05-25_t4-head-closed-head-vs-shipped.md` Q6, Q7, Q8, Q9, F7, F8, F9, and §6 C72 triage.
  - D11 `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md` §4.1, §4.5, §4.6, and §4.7.
  - D12 `workflow/design/decisions/active/2026-05-25_t4-d12-declared-port-namespace.md` §4.1-§4.8.
  - D13 `workflow/design/decisions/active/2026-05-25_t4-d13-external-head-body-semantics.md` §4.4, §4.8, and §4.9.
  - D14 `workflow/design/decisions/active/2026-05-25_t4-d14-rule-projection-sugar.md` §4.4-§4.9.
  - Parent design `workflow/design/design-points/active/rule-expression-and-proof-attempt.zh.md` §5.10.1 and C72.
  - Shipped `src/factgraph/application/protocol/rule_expr_inspect.py:36-135`, `:155-172`, `:189-228`, and `:243-257`.
  - Shipped `src/factgraph/sdk/store.py:392-399` and `:2099-2111`.
  - Shipped `src/factgraph/sdk/schema.py:50-88` and `:155-199`.
  - Shipped `src/factgraph/application/schema_runtime.py:13-57`, `:82-111`, `:189-222`, and `:260-341`.
- Outputs / Downstream:
  - Stage 3 T4 synthesis.
  - T4 implementation slice(s) for inspect DTO extension and private closed-head validator.
  - Future T5 manual explain / row.close work consumes the same private validator.
- Related:
  - `workflow/design/decisions/active/2026-05-25_t4-d11-scope-head-identity-boundary.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d12-declared-port-namespace.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d13-external-head-body-semantics.md`
  - `workflow/design/decisions/active/2026-05-25_t4-d14-rule-projection-sugar.md`
- Branch: `v0.2.0-t4-head-closed-head-audit-2026-05-25`
- Depends on: D11-D14 reviewed.

> ADR 4-state lifecycle: `proposed` -> `adopted` (current binding constraint, stays in `active/`) -> `superseded` or `withdrawn` (moves to `archive/`). Transitions are explicit; no `adopted` -> `proposed` re-opening.

## 1. Inputs

Parent C72 wants:

```python
inspect = fg.rules.inspect(head_rule)
inspect.unbound_ports
inspect.is_closed
```

as a read-only precheck for future manual closed-head explain. It explicitly says these utilities live on inspect output, not on `Rule` or RuleExpr values.

Stage 1 audit found schema substrate for primary identity metadata, but no shipped closed-head algorithm or inspect fields. D15 decides the strict v1 algorithm and where the public inspect fields live.

## 2. Scope

This decision locks:

- v1 closed-head accepted forms;
- literal term definition and equality direction;
- entity-ref primary identity closure using schema metadata;
- compound primary identity behavior;
- missing schema metadata behavior;
- inspect field placement for `is_closed` and `unbound_ports`;
- private validator reuse boundary for future T5;
- error buckets for closed-head failures.

## 3. Non-Scope

This decision does not lock:

- `EvaluateResult`, `EvaluateRow`, `row.close()`, `Explanation`, or WhyNot;
- public `fg.eval.explain(...)` behavior;
- evidence narrative rendering;
- transitive equality closure;
- general field literal closure;
- cross-port equality closure;
- adapter grammar changes;
- new public error subclasses.

## 4. Decision

### 4.1 Closed-head v1 accepts exactly two direct closure forms

D15 adopts parent C72's strict v1 rule.

A head port is closed only when one of these direct patterns is present in the head body:

1. value port literal binding;
2. entity-ref port primary identity literal binding.

D15 rejects broader inference:

- no transitive equality closure;
- no cross-port equality closure;
- no general field literal closure;
- no aggregate-derived closure;
- no closure through negated atoms, `InAtom`, or `BuiltinAtom`.

This keeps `is_closed=True` conservative.

### 4.2 Literal means direct `Const` on an equality or identity predicate

For value ports, D15 recognizes a direct equality:

```python
CmpAtom("eq", Var("p"), Const(value))
CmpAtom("eq", Const(value), Var("p"))
```

Only `CmpAtom.op == "eq"` counts. `ne`, `gt`, `in`, builtin arithmetic, and equality to another `Var` do not count.

The literal side must be a `Const`. D15 does not inspect nested structures inside `Const.value`; it treats the `Const` wrapper as the AST literal boundary.

### 4.3 Value ports close by direct equality to a literal

For `PortType(kind="value")`, a port is closed when its port `Var` appears in a direct equality to a `Const` anywhere in the positive top-level head body.

Examples accepted:

```python
CmpAtom("eq", status, Const("active"))
CmpAtom("eq", Const("active"), status)
```

Examples rejected for v1:

```python
CmpAtom("eq", status, other_var)
CmpAtom("eq", other_var, Const("active"))
InAtom(status, [Const("active")])
NotAtom(...)
BuiltinAtom(...)
```

The second rejected example is transitive closure and remains v2 territory.

### 4.4 Entity-ref ports close by complete primary identity literal binding

For `PortType(kind="entity_ref", entity_type=...)`, D15 uses the SDK/application schema index.

An entity-ref port is closed when every primary-key identity field for the entity type has a direct identity predicate literal in the head body:

```python
PredAtom(identity_predicate_id, [entity_ref_var, Const(value)])
```

where `identity_predicate_id` comes from `SchemaIndex.entities[entity_type].identity_predicates[field_name].pred_id` for each `IdentityFieldInfo(primary_key=True)`.

Closure checks operate on the user-authored `head.where` atoms, not on D13 runtime-augmented head-port link atoms, which link variables rather than literals.

For compound primary identity, all primary-key fields must be present. If one primary-key identity field is missing, the entity-ref port is unbound.

Non-primary identity fields are not required for closedness.

### 4.5 Missing schema metadata is conservative

Closed-head inspect needs schema context for entity-ref primary identity closure.

If schema metadata is missing or incomplete:

- inspect marks the affected entity-ref port unbound;
- a future "must be closed" validation gate using the same helper raises `RuleExprError` with a schema-metadata message;
- value-port closure can still be computed without schema metadata.

That future gate belongs to T5 caller paths such as manual explain or `row.close()` if adopted; D15 owns only the reusable validator and inspect reporting.

This avoids false `is_closed=True` while keeping read-only inspect useful.

### 4.6 Projection heads are closed by construction after D12 validation

D14 projection heads have no user-authored body constraints.

After D12 validates every projected port name against the branch-total declared-port map, projection heads are closed by construction:

- `unbound_ports == ()`;
- `is_closed == True`;
- D13 head-port links bind each projected output to expression sources.

If D12 projection validation fails, the projection head is invalid rather than merely open.

### 4.7 Inspect fields live on the public inspect DTO, not on Rule or RuleExpr

D15 extends the inspect output surface with:

```python
is_closed: bool
unbound_ports: tuple[str, ...]
```

The fields live on the public inspect DTO returned by `fg.rules.inspect(...)` for application `Rule` / head inspections. They do not become properties on `Rule`, RuleExpr, or SDK legacy `Rule` objects.

Implementation may extend the existing `RuleExprInspect` DTO because shipped SDK inspection already returns `RuleExprInspect` for application `Rule` values. It must preserve existing structural fields (`ast`, `occurrences`, `joins`, `unjoined_same_name_ports`, and `ports`).

For RuleExpr structural inspection, D15 does not define a closed-head guarantee. The closed-head invariant applies to inspect values for application head Rules.

### 4.8 Closed-head validation is private and reusable

Implementation should centralize the algorithm in a private helper used by:

- SDK/application rule inspection;
- future T5 manual explain closed-head prechecks;
- future `row.close()` implementation if T5 adopts it.

The helper may return an internal shape equivalent to:

```python
ClosedHeadStatus(is_closed: bool, unbound_ports: tuple[str, ...])
```

but D15 does not export that helper or DTO publicly.

### 4.9 D15 keeps the T4/T5 boundary closed

D15 does not ship:

- `fg.eval.explain(...)`;
- `row.close()`;
- `EvaluateResult`;
- `Explanation`;
- evidence graphs or narratives;
- WhyNot behavior.

It only defines the inspect utility and private validation substrate that T5 can reuse.

### 4.10 Closed-head failures use existing error buckets

Read-only inspect should not raise merely because a head is open; it reports `is_closed=False` and `unbound_ports`.

Validation gates that require a closed head use `RuleExprError` for:

- non-closed head;
- unsupported closure pattern;
- missing schema primary identity metadata;
- malformed closed-head input after `Rule` construction.

Public SDK call-shape errors remain `SDKStoreError`. `Rule` construction errors remain `RuleValidationError`. D15 does not add a new public error subclass.

## 5. Rejected Alternatives

### Option A: Put `is_closed` and `unbound_ports` on `Rule`

- **Why rejected**: parent C72 explicitly says inspect-only. `Rule` has no schema context and should remain a pure DTO.

### Option B: Put `is_closed` and `unbound_ports` on RuleExpr

- **Why rejected**: parent C72 says not on RuleExpr. Closed-head is a head Rule utility, not an authoring expression operator.

### Option C: Add public `ClosedHeadStatus` DTO

- **Why rejected**: T4 needs inspect fields, not a new public status object. A private helper output is enough and preserves narrow-public-api discipline.

### Option D: Treat general field literal constraints as entity-ref closure

- **Why rejected**: C72 v1 explicitly rejects general field literal closure. A field filter can constrain candidates without uniquely identifying the entity.

### Option E: Accept transitive equality closure

- **Why rejected**: transitive equality requires a broader equality graph and could accept cases C72 reserves for v2.

### Option F: Accept cross-port equality closure

- **Why rejected**: two unbound ports equal to each other are still not literal-bound.

### Option G: Treat missing schema metadata as closed when a predicate name looks like an identity field

- **Why rejected**: would make closedness depend on naming heuristics. D15 requires schema metadata for entity-ref identity closure.

### Option H: Block T4 on T5 explain/result design

- **Why rejected**: C72 inspect utilities can be decided and implemented without `EvaluateResult`, `Explanation`, `row.close()`, or WhyNot.

## 6. Supporting Evidence

- Shipped `RuleExprInspect` exposes structural inspect data but no closed-head fields.
- Shipped SDK `rules.inspect(...)` dispatches application `Rule` values through the same inspect DTO family.
- SDK schema declarations record `Identity(primary_key=True)`.
- Application `SchemaIndex` stores `IdentityFieldInfo.primary_key` and identity predicate metadata.
- Parent C72 accepts only value literal equality and entity-ref primary identity literal binding in v1.
- D14 projection heads are closed by construction after D12 validation.
- D11/D6 already provide the relevant error buckets.
- T5 owns evidence/result/explain surfaces and remains out of D15 scope.

## 7. Consequences

### 7.1 Downstream unblocking

D15 completes T4 Stage 2 decision coverage:

- Q6 closed-head algorithm and schema input;
- Q7 inspect field placement;
- Q8 error bucket for non-closed / unsupported / schema-missing cases;
- Q9 T4/T5 boundary.

Stage 3 synthesis can now classify all T4 audit findings and define implementation slices.

### 7.2 Implementation constraints

Future implementation should:

- add inspect fields without removing existing inspect fields;
- pass SDKStore schema index into closed-head inspection for application Rules;
- keep application-layer validator private;
- treat open heads as inspect data, not inspect exceptions;
- use `RuleExprError` only when a caller requires a closed head;
- keep projection heads closed by construction after D12 validation;
- avoid implementing `fg.eval.explain(...)` or `row.close()`.

### 7.3 Stage 3 gating

Stage 3 synthesis must ensure closed-head implementation blueprints test:

- value port direct `Var == Const` and `Const == Var`;
- value port transitive equality rejection;
- entity-ref primary identity direct predicate closure;
- compound primary identity requiring all primary-key fields;
- missing primary identity schema metadata conservative behavior;
- projection head closed-by-construction behavior;
- inspect open-head reporting without raising;
- no T5 result/explain/evidence surface.

## 8. Acceptance Criteria

- [ ] `is_closed` and `unbound_ports` live on inspect output, not on `Rule` or RuleExpr.
- [ ] Value ports close only through direct equality to `Const`.
- [ ] Entity-ref ports close only through all primary-key identity predicates bound to `Const`.
- [ ] Compound primary identity requires every primary-key field.
- [ ] General field literal, transitive equality, and cross-port equality remain open.
- [ ] Missing schema metadata is conservative and cannot produce `is_closed=True`.
- [ ] Projection heads are closed by construction after D12 validation.
- [ ] Inspect reports open heads without raising.
- [ ] D15 does not introduce T5 result/explain/evidence surfaces.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-05-25 | proposed | Decision drafted | T4 Stage 1 audit Q6/Q7/Q8/Q9 and parent C72 mapped to D15. D15 locks a strict v1 closed-head algorithm, inspect-only public fields, private reusable validator, and T4/T5 boundary. |
| 2026-05-25 | proposed-amend | Claude Step 4.2 v1 follow-up | WC1 closed-head invariant wording fixed; WC2 user-authored head body closure scope and WC3 future T5 gate relationship clarified. |
