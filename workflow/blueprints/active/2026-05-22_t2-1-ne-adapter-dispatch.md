# T2.1 — `ne` adapter dispatch gap close

- Status: scoped
- Created: 2026-05-22
- Last Updated: 2026-05-22
- Track: T2 Atom 语言闭合 + adapter gap(per [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md))
- Related Modules:
  - `src/factgraph/core/rules/where_ast.py` — `_CMP_OPS` already includes `ne`; parser accepts `("ne", lhs, rhs)`.
  - `src/factgraph/core/rules/where_ast_validate.py` — `ne` already validates as a filter comparison, requiring referenced variables to be bound before use.
  - `src/factgraph/adapters/souffle/where_compile.py` — raw tuple adapter has `eq` + `gt/ge/lt/le` dispatch but lacks `ne` in validation, main body compile, `not` body compile, and variable extraction.
  - `src/factgraph/adapters/problog/problog_export.py` — raw tuple adapter has `eq` + `gt/ge/lt/le` dispatch but lacks `ne`.
- Related Docs:
  - parent design essay [`rule-expression-and-proof-attempt.zh.md`](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md) — §10 atom language closure / 9 atom kinds.
  - track plan [`rule-expression-and-proof-track-plan.zh.md`](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md) — §2 T2.1 row.
  - T1.1 archived [`2026-05-22_t1-1-rule-class-additive.md`](../archive/2026-05-22_t1-1-rule-class-additive.md) — new application `Rule` stores core AST atoms.
  - T1.2 archived [`2026-05-22_t1-2-dsl-to-application-rule.md`](../archive/2026-05-22_t1-2-dsl-to-application-rule.md) — DSL bridge remains equality-only for AttrRef canonical forms; non-eq AttrRef compare is explicitly deferred.
- Audit Log:
  - [2026-05-22_t2-1-ne-adapter-dispatch.audit.md](./2026-05-22_t2-1-ne-adapter-dispatch.audit.md)

## 1. Problem

Core rule AST already recognizes `ne` as a comparison operator, but the two adapter emitters that compile raw tuple `where` bodies do not. This creates an inconsistent shipped surface:

- `parse_where_ir_to_ast` can parse `("ne", lhs, rhs)` because `where_ast.py` includes `ne` in `_CMP_OPS`.
- `validate_where_ast` treats `ne` as a filter comparison: it requires all variable operands to be bound before the atom runs and binds no new variables.
- Souffle compilation rejects or fails to compile raw tuple `ne` because `where_compile.py` only dispatches `eq`, `in`, `gt/ge/lt/le`, arithmetic, `not`, and `ruleref`.
- ProbLog export rejects raw tuple `ne` for the same reason.

T2.1 closes this adapter-only gap. It does not expand SDK authoring syntax, application `Rule`, or the broader atom expression language.

## 2. Goals

### 2.1 Souffle raw tuple adapter accepts and emits `ne`

- Add `ne` to `_validate_atom_subset` with the same shape class as ordering comparisons: exactly three tuple fields and at least one variable side.
- Compile main-body `("ne", lhs, rhs)` as a filter, not as an equality binder.
- Compile nested `not` body `("ne", lhs, rhs)` with the same filter semantics.
- Include variables from `ne` in `_vars_in_atom(...)` so query variable extraction and `not` correlation do not silently omit them.
- Reuse the existing comparison side compilation path where possible, but map `ne` to Souffle `!=`.

### 2.2 ProbLog raw tuple adapter accepts and emits `ne`

- Add `ne` support to `_compile_atom(...)`.
- Compile `("ne", lhs, rhs)` to ProbLog/Prolog term disequality using `\=`.
- Preserve the current `eq` behavior (`=`) and ordering comparison behavior (`>`, `>=`, `<`, `=<`).

### 2.3 Dataflow semantics stay filter-only

- `ne` MUST NOT bind unbound variables.
- Any variable operand in `ne` must already be bound by an earlier predicate, equality binding, `in`, or builtin output.
- Error behavior for unbound variables should mirror `gt/ge/lt/le`, with `op="ne"` in runtime/dataflow errors where applicable.

### 2.4 Tests cover adapter gap directly

- Add focused Souffle compile tests for main-body `ne`, `not` body `ne`, and unbound-variable rejection.
- Add focused ProbLog export tests for `ne`.
- Keep tests at adapter compile/export level; no real Souffle or ProbLog binary execution is required.

## 3. Non-goals

- No SDK DSL syntax change. In particular, T1.2's deferred `User(u).score > 0.5` / non-eq AttrRef compare remains deferred.
- No change to `factgraph.sdk.dsl.build_application_rule(...)`.
- No change to `factgraph.application.protocol.Rule`.
- No new atom kinds beyond existing core `ne`.
- No ArithExpr or AggregateExpr work; those remain T2.2 and T2.3.
- No PyReason adapter support; the track plan explicitly defers PyReason atom-language parity.
- No runtime engine invocation tests that require external Souffle or ProbLog executables.
- No broad refactor of adapter comparison compilation unless needed to avoid duplicating unsafe logic.

## 4. Current Context

### 4.1 Core AST already ships `ne`

`src/factgraph/core/rules/where_ast.py:95` has:

```python
_CMP_OPS = {"eq", "ne", "gt", "ge", "lt", "le"}
```

The parser path accepts `ne` as a native `CmpAtom`.

### 4.2 Core validator treats `ne` as a filter

`src/factgraph/core/rules/where_ast_validate.py:33-34` defines the comparison operator sets, and `src/factgraph/core/rules/where_ast_validate.py:383-385` currently handles `ne` filter dataflow:

```python
if atom.op in _CMP_FILTER_OPS or atom.op == "ne":
    req = _term_requires(atom.lhs) | _term_requires(atom.rhs)
    return _StepEffect(requires=req, binds=set(), references=set(req))
```

This is the semantic lock for this slice: `ne` behaves like `gt/ge/lt/le` for dataflow, not like `eq`.

### 4.3 Souffle adapter gap

`src/factgraph/adapters/souffle/where_compile.py` currently has separate branches for:

- `kind == "eq"` in `_compile_atom(...)` at `where_compile.py:477`
- `kind in {"gt", "ge", "lt", "le"}` in `_compile_atom(...)` at `where_compile.py:525`
- `kind == "eq"` in `_validate_atom_subset(...)` at `where_compile.py:684`
- `kind in {"gt", "ge", "lt", "le"}` in `_validate_atom_subset(...)` at `where_compile.py:704`
- `kind == "eq"` in `_compile_not_body_atom(...)` at `where_compile.py:933`
- `kind in {"gt", "ge", "lt", "le"}` in `_compile_not_body_atom(...)` at `where_compile.py:979`
- `kind == "eq"` in `_vars_in_atom(...)` at `where_compile.py:1102`
- `kind in {"gt", "ge", "lt", "le"}` in `_vars_in_atom(...)` at `where_compile.py:1112`

None include `ne`.

### 4.4 ProbLog adapter gap

`src/factgraph/adapters/problog/problog_export.py:208` dispatches all raw tuple atoms through `_compile_atom(...)`. It currently compiles:

- `eq` as `lhs = rhs` at `problog_export.py:238-241`
- `gt/ge/lt/le` as `>`, `>=`, `<`, `=<` at `problog_export.py:243-247`
- `not` recursively through `_compile_atom(...)` at `problog_export.py:259-269`

There is no `ne` branch.

### 4.5 T1.2 boundary

T1.2 intentionally deferred non-equality AttrRef canonical syntax because the SDK DSL lowering path would need temp vars and `CmpAtom` IR connection work. T2.1 must not undo that boundary by expanding SDK-level authoring. It only makes already-valid raw/core `ne` portable to Souffle and ProbLog.

## 5. Proposed Shape

### 5.1 Souffle comparison dispatch

Add a helper or small branch that treats `ne` as a filter comparison:

```python
if kind in {"ne", "gt", "ge", "lt", "le"}:
    # require any variable side to already be bound
    # assert comparison variable type domains where relevant
    # compile sides through the existing comparison-side path
    # map ne -> "!="
```

The implementation may either extend the existing ordering-comparison branch to include `ne` or add an adjacent `ne` branch. The invariant matters more than the shape: `ne` must not share the `eq` binding branch.

### 5.2 Souffle validation

`_validate_atom_subset(...)` should accept `ne` with the same tuple shape rule as ordering comparisons:

- `("ne", lhs, rhs)` only.
- At least one side must be a variable.
- Literal-vs-literal `ne` remains invalid at adapter subset validation level, matching current comparison subset behavior.

### 5.3 Souffle `not` body and variable extraction

`_compile_not_body_atom(...)` must support `ne` so nested negation bodies can compile raw tuple disequality.

`_vars_in_atom(..., include_not_body_vars=...)` must count variables in `ne`, including variables nested inside `not` body when requested. This prevents query/correlation extraction drift.

### 5.4 ProbLog export

`_compile_atom(...)` should map:

```python
if kind == "ne":
    return f"{_to_problog_term(atom[1])} \\= {_to_problog_term(atom[2])}"
```

The implementation should keep `eq` separate for readability because `=` and `\=` have different Prolog semantics and should not be collapsed into a generic operator table without tests.

`\\=` is intentionally **term inequality / cannot-unify**, not arithmetic inequality (`=\\=`) or structural identity inequality (`\\==`). This matches the current raw where term model for ground filters: variables and literals are rendered as Prolog terms, not numeric expression trees. If future numeric type mixing needs value-level arithmetic disequality, that belongs in T2.2/T2.3 expression work rather than this adapter gap close.

## 6. Boundaries And Invariants

- **Filter-only invariant**: `ne` never binds variables.
- **Bound-before-filter invariant**: every variable operand in `ne` must already be bound when the atom compiles.
- **Adapter-only invariant**: no SDK DSL, application protocol, or core AST shape changes.
- **No external binary invariant**: tests validate emitted adapter code strings and local validation behavior, not external engine execution.
- **Existing equality invariant**: `eq` must keep current binder behavior in Souffle and unification behavior in ProbLog.
- **Existing ordering comparison invariant**: `gt/ge/lt/le` behavior must not change.
- **ProbLog term-inequality invariant**: ProbLog `ne` uses `\=` term inequality. It is considered aligned with Souffle `!=` for ground term filters, while numeric type-mixing differences are explicit follow-up territory.

## 7. Acceptance

- [ ] Souffle `_validate_atom_subset` accepts `("ne", "$x", "blocked")` and rejects malformed `ne` shapes.
- [ ] Souffle main-body compile emits `V0 != "blocked"` or equivalent valid Souffle disequality for a bound `$x`.
- [ ] Souffle compile rejects unbound `ne` variable operands with an error that identifies `ne`.
- [ ] Souffle `not` body compile accepts `ne` and emits disequality inside the generated auxiliary relation.
- [ ] Souffle variable extraction includes variables from top-level `ne` and `ne` inside `not` bodies when `include_not_body_vars=True`.
- [ ] ProbLog export emits `\=` for raw tuple `ne`.
- [ ] ProbLog nested `not` body export recursively emits `\+(V_X \= 'blocked')` or equivalent formatting for raw tuple `("not", [("ne", "$x", "blocked")])`.
- [ ] Existing `eq` tests and ordering-comparison tests continue to pass.
- [ ] Targeted tests pass:
  - `PYTHONPATH=src python -m unittest tests.test_souffle_witness_where_compile_v1 tests.test_problog_export`
  - `python -m ruff check src/factgraph/adapters/souffle/where_compile.py src/factgraph/adapters/problog/problog_export.py tests/test_souffle_witness_where_compile_v1.py tests/test_problog_export.py`

## 8. Implementation Plan

1. Update `src/factgraph/adapters/souffle/where_compile.py` validation for `ne`.
2. Update Souffle main-body comparison compilation so `ne` is filter-only and emits `!=`.
3. Update Souffle `not` body compilation for `ne`.
4. Update Souffle `_vars_in_atom(...)` for `ne`.
5. Update `src/factgraph/adapters/problog/problog_export.py` to emit `\=`.
6. Add/extend adapter tests:
   - Souffle main-body `ne` happy path.
   - Souffle unbound `ne` rejection.
   - Souffle `not` body `ne`.
   - Souffle variable extraction coverage if not already covered by compile output.
   - ProbLog `ne` string export.
7. Run targeted tests and ruff.
8. Close blueprint with exact files changed and any deviations.

## 9. Docs To Update

- No user-facing module docs are expected unless implementation discovers an existing adapter/operator reference table that omits `ne`.
- If such a table exists, update it in the same implementation commit and cite the path in §10.
- Track plan update is not expected because T2.1 already names Souffle + ProbLog `ne` dispatch; update only if implementation scope changes.

## 10. Outcome / Deviations

To be filled after implementation:

- Final landed behavior:
- Tests run:
- Deviations from blueprint:
- Known follow-up:
- Archive note:
