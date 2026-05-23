# T2.3d — Aggregate ProbLog adapter wire over T2.3a substrate + T2.3b SDK

- Status: implemented
- Created: 2026-05-23
- Last Updated: 2026-05-23 (Step 4.8 closure)
- Authority: task blueprint
- Inputs:
  - Parent essay [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md) §10.6.3 (C99) — aggregate value expression shape;§10.6.4 (C100) — aggregate filter restrictions;§10.6.5 (C101) — empty set + `AggregateNoValue`;§10.6.7 (C103) — projected-view snapshot semantics;§10.6.8 (C104) — variable scoping;§8.8 + §1719 — ProbLog lowering via `findall/3` + list predicates.
  - Track plan [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md) §1.2 G1-G7,§1.2.6 T2.3d row(S-class narrow adapter slice).
  - Archived T2.3a [2026-05-23_t2-3-aggregate-substrate.md](../archive/2026-05-23_t2-3-aggregate-substrate.md) — substrate IR `AggregateAtom`, validator, Python eval, and application Rule serialization consumed unchanged.
  - Archived T2.3b [2026-05-23_t2-3b-aggregate-sdk-bridge.md](../archive/2026-05-23_t2-3b-aggregate-sdk-bridge.md) — SDK helpers and bridge produce aggregate IR consumed by this adapter.
  - Archived T2.3c [2026-05-23_t2-3c-aggregate-souffle-wire.md](../archive/2026-05-23_t2-3c-aggregate-souffle-wire.md) — Souffle aggregate wire precedent and `extract_where_variables(...)` aggregate behavior consumed unchanged.
  - Archived T2.1 [2026-05-23_t2-1-ne-adapter-dispatch.md](../archive/2026-05-23_t2-1-ne-adapter-dispatch.md) — ProbLog `ne` term-inequality dispatch precedent.
  - Archived T2.2 [2026-05-23_t2-2-arith-expr.md](../archive/2026-05-23_t2-2-arith-expr.md) — ProbLog arithmetic builtin export via `is/2`.
- Outputs / Downstream:
  - `src/factgraph/adapters/problog/problog_export.py` aggregate-aware `_compile_atom(...)` cmp dispatch for aggregate tuple operands.
  - New aggregate compile helpers using `findall/3`, `length/2`, `sum_list/2`, `min_list/2`, `max_list/2`, and derived mean via `sum_list` + `length` + `is/2`.
  - Conditional generated-program directive `:- use_module(library(lists)).` when aggregate lowering is used.
  - Adapter-side aggregate shape validation for structural cases the exporter cannot compile.
  - Tests proving 5 aggregate kinds, empty-set behavior, aggregate-local isolation, `not` filter recursion, two-aggregate comparisons, and malformed aggregate rejection.
  - Docs status flip: `application/docs/rule.md` + `sdk/docs/03_rules_and_inferences.en.md` mark ProbLog aggregate adapter support as shipped.
- Related:
  - `src/factgraph/adapters/problog/problog_export.py`
  - `tests/test_problog_export.py`
  - `src/factgraph/application/docs/rule.md`
  - `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
  - `src/factgraph/adapters/souffle/where_compile.py` (read-only dependency for `extract_where_variables`)
- Related Modules:
  - `src/factgraph/adapters/problog/problog_export.py` — extends `_compile_atom(...)` dispatch at `:208-301`, `_compile_body(...)` at `:202-205`, and helper term conversion at `:315-343`.
  - `tests/test_problog_export.py` — extends current ProbLog export tests; existing `ne` tests at `:118-141` and arithmetic tests at `:143-168` are the local style precedent.
  - `src/factgraph/application/docs/rule.md` — flips ProbLog aggregate status row currently deferred at `:101-102`.
  - `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` — flips §3.2 ProbLog adapter row currently deferred at `:188`.
- Audit Log:
  - [2026-05-23_t2-3d-aggregate-problog-wire.audit.md](./2026-05-23_t2-3d-aggregate-problog-wire.audit.md)
- Branch: `v0.2.0-blueprint-t2-3d-aggregate-problog-wire-2026-05-23`

> **Cross-slice relationship**:T2.3a shipped the aggregate substrate,T2.3b shipped SDK authoring,T2.3c shipped Souffle adapter support。T2.3d closes the ProbLog adapter path only。No SDK,core,application Rule,or Souffle code changes are in scope。

## 1. Problem

Parent essay §8.8 says ProbLog has no single native aggregate operator and should lower aggregate expressions through `findall/3` plus list predicates:

- `findall(TargetExpr, BodyConjunction, List)`
- `length(List, Count)` for count
- `sum_list(List, Sum)` for sum
- `min_list(List, Min)` / `max_list(List, Max)` for min/max
- `mean` derived from `sum_list` + `length` + `Mean is Sum / Count`

The same parent section records empty-set convergence:

- count/sum empty set returns `0`
- min/max/mean empty set behaves as `AggregateNoValue`, which means enclosing comparison/binding does not fire and does not pollute the environment

Current shipped state:

- `problog_export.py:208-301` `_compile_atom(...)` supports `pred`, `eq`, `ne`, `gt/ge/lt/le`, arithmetic builtins, `in`, and `not`, but no aggregate operands inside cmp atoms.
- `problog_export.py:238-252` currently passes cmp operands through `_to_problog_term(...)`, so an aggregate tuple operand falls to `_to_problog_literal(...)` and becomes a quoted JSON-ish/string literal, not a semantic aggregate.
- `problog_export.py:289-299` `not` recursively compiles body atoms via `_compile_atom(...)`; aggregate support should be inherited inside `not` bodies once `_compile_atom(...)` is aggregate-aware.
- `export_problog(...)` imports `extract_where_variables` from Souffle at `problog_export.py:12` and uses it at `:44-47`; after T2.3c this extractor excludes aggregate-local vars from query vars. This behavior is a required precondition for T2.3d.
- `sdk/docs/03_rules_and_inferences.en.md:188` still says `ProbLog adapter | Deferred to T2.3.d`.
- `application/docs/rule.md:101-102` still says ProbLog aggregate projection remains deferred.

T2.3d must make SDK-authored aggregate IR exportable through ProbLog without touching the already-shipped SDK/substrate/Souffle layers.

## 2. Goals

### 2.1 C99 — Recognize aggregate tuple operands in ProbLog cmp atoms

Extend `_compile_atom(...)` branches for `eq`, `ne`, `gt`, `ge`, `lt`, and `le` so either lhs or rhs may be an aggregate tuple:

```python
("eq", "$total", ("sum", "$_agg1", [ ... filter atoms ... ]))
("gt", ("count", None, [ ... filter atoms ... ]), 3)
("eq", ("sum", "$_agg1", [...]), ("sum", "$_agg2", [...]))
```

Aggregate remains a **term-position value expression**, not a top-level atom kind。

### 2.2 C99 / §8.8 — Add `_compile_aggregate_parts(...)` for ProbLog

Add a helper that returns a sequence of prerequisite goals plus the aggregate result variable:

```python
def _compile_aggregate_parts(aggregate, ctx) -> tuple[list[str], str]:
    ...
```

The helper compiles `(kind, target_var, filter_atoms)` into deterministic fresh variables:

| Kind | ProbLog goals |
|---|---|
| `count` | `findall(1, (<filter>), L), length(L, Result)` |
| `sum` | `findall(Target, (<filter>), L), sum_list(L, Result)` |
| `min` | `findall(Target, (<filter>), L), L = [_|_], min_list(L, Result)` |
| `max` | `findall(Target, (<filter>), L), L = [_|_], max_list(L, Result)` |
| `mean` | `findall(Target, (<filter>), L), L = [_|_], sum_list(L, Sum), length(L, Count), Result is Sum / Count` |

For min/max/mean, `L = [_|_]` is the C101 empty-set guard. Empty list makes the enclosing rule body fail, matching `AggregateNoValue` violated-comparison/no-env-pollution semantics.

When any aggregate expression is compiled, the generated ProbLog program MUST include:

```prolog
:- use_module(library(lists)).
```

G7 precondition execution on 2026-05-23 confirmed the local ProbLog binary has `length/2` but does not expose `sum_list/2`, `min_list/2`, or `max_list/2` without `library(lists)`; the same smoke passes with the directive. Non-aggregate exports should avoid adding this directive so existing exact-output tests and non-aggregate programs remain stable.

### 2.3 C100 — Compile aggregate filter atoms recursively with local scope

Aggregate filter atoms use the same raw tuple atom language as the outer ProbLog body:

- `pred`
- `eq`
- `ne`
- `gt/ge/lt/le`
- `in`
- `not`

The helper compiles filter atoms via the same `_compile_atom(...)` logic but with an aggregate-local context:

- outer variables are visible as correlated inputs
- filter-introduced variables stay local to the `findall/3` goal
- aggregate target vars are local variables inside `findall/3`

No explicit bound-var state is required in ProbLog, because Prolog unification and goal order handle variable flow. Structural validation still rejects malformed aggregate shapes and unsupported filter atom kinds before emitting code.

### 2.4 C101 — Encode `AggregateNoValue` as goal failure for min/max/mean

ProbLog has no sentinel value in this adapter path. The adapter represents `AggregateNoValue` by making the enclosing rule body fail:

```prolog
findall(Target, (Body), L),
L = [_|_],
min_list(L, Min),
...
```

For empty aggregate result:

- `count` emits 0 through `length([], 0)`
- `sum` emits 0 through `sum_list([], 0)` per SWI-Prolog `library(lists)` standard behavior, inherited by ProbLog's Prolog runtime.
- `min/max/mean` fail at `L = [_|_]`, so no answer row is produced

This mirrors T2.3c's Souffle guard semantics while using idiomatic Prolog list predicates.

### 2.5 C104 — Preserve aggregate-local variable isolation

`extract_where_variables(...)` is the query variable source for ProbLog export. T2.3c changed it so aggregate operands contribute ZERO outer vars; that is now a cross-adapter contract.

T2.3d must not reintroduce aggregate-local variables into query heads. Tests must prove an aggregate-local `$o` / `$_agg1` in a filter does not appear in `% query_vars=[...]`, `rule_body_N(...)`, `answer(...)`, or `query(answer(...))`.

### 2.6 Adapter-side structural validation

Add or reuse a helper that rejects uncompileable aggregate shapes:

- tuple arity must be 3
- kind must be one of `count/sum/min/max/mean`
- count target must be `None`
- numeric aggregate target must be `$`-prefixed variable token
- filter must be non-empty list
- filter atom kind must be C100 list: `pred/eq/ne/gt/ge/lt/le/in/not`
- nested aggregate inside aggregate filter rejected
- malformed filter atoms rejected

This validation is not a substitute for T2.3a semantic validation. It is the exporter safety net for raw rule specs and direct tests that call `export_problog(...)` without the application bridge.

### 2.7 Docs status flip

Update:

- `src/factgraph/application/docs/rule.md` — ProbLog aggregate adapter no longer deferred; document `findall/3` + list predicate lowering and empty min/max/mean guard.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` — §3.2 table row `ProbLog adapter | Deferred to T2.3.d` flips to supported.

No `sdk/docs/04_api_surface.en.md` update is expected because T2.3d adds no new public SDK symbol.

## 3. Non-goals

- No SDK helper changes (`src/factgraph/sdk/dsl/expr.py` 0 diff).
- No bridge changes (`src/factgraph/sdk/dsl/application_rule.py` 0 diff).
- No core substrate changes (`where_ast.py`, `where_ast_validate.py`, `where_eval.py`, `application/protocol/rule.py` 0 diff).
- No Souffle adapter changes (`src/factgraph/adapters/souffle/where_compile.py` 0 diff).
- No PyReason aggregate support.
- No new aggregate kinds.
- No nested aggregate support.
- No arithmetic expression inside aggregate filter beyond what T2.3a/T2.3b already allow. If malformed raw tuple arithmetic appears in filter, exporter rejects it as unsupported filter atom kind.
- No ProbLog probability semantics changes.
- No full ProbLog runtime query execution requirement; export-level tests are sufficient for S-class unless G7 discovers a local ProbLog binary and a cheap smoke is available.

## 4. Current Context

### 4.1 ProbLog exporter dispatch

- `src/factgraph/adapters/problog/problog_export.py:23-89` `export_problog(...)` validates rule spec, normalizes where bodies, calls `extract_where_variables(...)`, emits EDB facts, emits `rule_body_N(...)`, `answer(...)`, and `query(...)`.
- `problog_export.py:44-47` wraps `extract_where_variables(where)` errors into `ProbLogExportError`.
- `problog_export.py:202-205` `_compile_body(...)` joins `_compile_atom(atom)` with commas.
- `problog_export.py:208-301` `_compile_atom(...)` is the single dispatch point for raw where atoms.

### 4.2 Existing atom support

- `problog_export.py:213-236` `pred` emits `edb_fact(_, pred_id, subject, value)` for arity 1/2.
- `problog_export.py:238-241` `eq` emits `lhs = rhs`.
- `problog_export.py:243-246` `ne` emits `lhs \= rhs` (T2.1 term inequality).
- `problog_export.py:248-252` `gt/ge/lt/le` emit Prolog numeric comparisons.
- `problog_export.py:254-277` arithmetic builtins emit `is/2` (T2.2).
- `problog_export.py:279-287` `in` emits disjunction of equality alternatives.
- `problog_export.py:289-299` `not` emits `\+(...)` with recursive `_compile_atom(...)`.
- `problog_export.py:301` unsupported atom kind raises `ProbLogExportError`.

### 4.3 Term conversion

- `problog_export.py:315-318` `_to_problog_term(...)` maps `$var` to Prolog var and non-vars to literal.
- `problog_export.py:321-324` `_to_problog_arith_output(...)` requires `$` var output.
- `problog_export.py:327-333` `_to_problog_arith_term(...)` allows `$` vars and integer literals only.
- `problog_export.py:335-340` `_to_problog_var(...)` normalizes `$foo` to `V_FOO`.
- `problog_export.py:343-355` `_to_problog_literal(...)` quotes strings, emits ints/floats, and JSON-encodes unknown values.

Current aggregate tuple operands therefore fall through to literal encoding unless `_compile_atom(...)` intercepts them.

### 4.4 Tests and gate state

- `tests/test_problog_export.py:118-141` cover `ne` top-level and nested under `not`.
- `tests/test_problog_export.py:143-168` cover arithmetic builtins.
- `tests/test_problog_engine_eval.py` import path currently passes after ProbLog hygiene and fixture cleanup.
- `sdk/docs/03_rules_and_inferences.en.md:188` has the row that must flip for ProbLog aggregate support.
- `application/docs/rule.md:101-102` has the deferred ProbLog aggregate note that must flip.

### 4.5 Parent and track-plan context

- Parent essay §1711 says AggregateExpr for ProbLog is not implemented and requires `findall/3` + list predicates.
- Parent essay §1719 estimates ProbLog AggregateExpr dispatch at ~150 LOC.
- Parent essay §1793-1799 gives the concrete ProbLog strategy and derived mean.
- Parent essay §1807-1814 requires empty-set convergence.
- Track plan §1.2.6 classifies T2.3c/T2.3d adapter wires as narrow S-class slices if no cross-engine semantic decision appears.
- `workflow/memory/current.md` records T2.3.d as the next recommended slice and requires user-drafts pattern after T2.3c cross-flip cost.

## 5. Proposed Shape

### 5.1 Add aggregate detection helpers

Preferred helper:

```python
_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}
_AGGREGATE_FILTER_ATOM_KINDS = {"pred", "eq", "ne", "gt", "ge", "lt", "le", "in", "not"}

def _is_aggregate(value: Any) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 3
        and isinstance(value[0], str)
        and value[0] in _AGGREGATE_KINDS
    )
```

Do not import private constants from Souffle adapter. ProbLog can mirror the small aggregate-kind set locally or import from core `where_ast`; implementation may choose the simpler lint-clean path. If mirrored locally, add tests proving all five kinds.

### 5.2 Compile context and fresh variable allocation

Current `_compile_atom(atom)` has no context. T2.3d needs deterministic fresh list/result variables for aggregate lowering.

Recommended shape:

```python
@dataclass
class _CompileContext:
    next_id: int = 1
    requires_lists: bool = False

    def fresh(self, prefix: str) -> str:
        ...
```

Fresh variables MUST use a reserved non-user prefix that cannot collide with `_to_problog_var("$...")` output. Lock the shape as `Agg{Prefix}{N}` after stripping non-alphanumeric prefix characters, for example `AggList1`, `AggResult2`, `AggSum3`, `AggCount4`. Do not emit `V_...` names for adapter-generated variables; `V_` is reserved for user IR variables converted by `_to_problog_var(...)`.

Then:

```python
def _compile_body(body: list[Any]) -> str:
    ctx = _CompileContext()
    return ", ".join(_compile_atom(atom, ctx=ctx) for atom in body)
```

Tests that call `_compile_atom(...)` directly should keep working by allowing `ctx: _CompileContext | None = None` and constructing a local context if absent.

`export_problog(...)` should use one context for all compiled rule bodies, precompile those bodies before final line emission, and insert `:- use_module(library(lists)).` after the generated header when `ctx.requires_lists` becomes true. This keeps aggregate exports executable while preserving existing non-aggregate output.

### 5.3 Aggregate compile algorithm

Pseudo-code:

```python
def _compile_aggregate_parts(aggregate: tuple[Any, ...], *, ctx: _CompileContext) -> tuple[list[str], str]:
    kind, target_var, filter_atoms = aggregate
    _validate_aggregate_shape(aggregate)
    ctx.requires_lists = True

    list_var = ctx.fresh("List")
    result_var = ctx.fresh("Result")
    filter_goal = _compile_aggregate_filter(filter_atoms, ctx=ctx)

    if kind == "count":
        return [f"findall(1, ({filter_goal}), {list_var})", f"length({list_var}, {result_var})"], result_var

    target = _to_problog_arith_term(target_var)
    goals = [f"findall({target}, ({filter_goal}), {list_var})"]
    if kind == "sum":
        goals.append(f"sum_list({list_var}, {result_var})")
    elif kind == "min":
        goals.extend([f"{list_var} = [_|_]", f"min_list({list_var}, {result_var})"])
    elif kind == "max":
        goals.extend([f"{list_var} = [_|_]", f"max_list({list_var}, {result_var})"])
    elif kind == "mean":
        sum_var = ctx.fresh("Sum")
        count_var = ctx.fresh("Count")
        goals.extend([
            f"{list_var} = [_|_]",
            f"sum_list({list_var}, {sum_var})",
            f"length({list_var}, {count_var})",
            f"{result_var} is {sum_var} / {count_var}",
        ])
    return goals, result_var
```

`sum_list([], 0)` is locked as standard SWI-Prolog `library(lists)` behavior. The implementation must emit `:- use_module(library(lists)).` for aggregate programs; if Step 4.7 integration against an actual ProbLog binary still shows non-standard behavior with the directive present, treat that as a deviation in §10 Outcome and amend before implementation continues. Do not leave the empty-sum semantics open in the implementation plan.

### 5.4 Cmp dispatch composition

For cmp atom with aggregate side:

```python
goals, agg_var = _compile_aggregate_parts(agg, ctx=ctx)
other_term = _to_problog_term(other) or _to_problog_arith_term(other)
comparison = f"{agg_var} {op} {other_term}"
return ", ".join([*goals, comparison])
```

Cases:

| Case | Output |
|---|---|
| `("$total" == agg_sum(...))` | `findall(..., L), sum_list(L, R), V_TOTAL = R` |
| `(agg_count(...) > 3)` | `findall(1, Body, L), length(L, R), R > 3` |
| `(agg_min(...) == "$x")` where `$x` is variable | `findall(...), L = [_|_], min_list(L, R), R = V_X` |
| two aggregates | goals for left + goals for right + `R_LEFT <op> R_RIGHT` |

Unlike Souffle, ProbLog variables are not symbol-domain strings, so there is no `to_string(...)` wrapper. The adapter emits native Prolog variables and numeric literals directly.

### 5.5 Filter compilation

`_compile_aggregate_filter(filter_atoms, ctx)`:

- validates C100 filter atom kinds
- compiles each filter atom via `_compile_atom(atom, ctx=ctx)`
- joins them with `, `
- uses existing `not` recursion (`\+(...)`) for filter not bodies

The filter shares the outer Prolog variable namespace. This is safe because Prolog goal scope naturally captures correlated variables by name while variables introduced only inside `findall/3` remain local to the findall template/body.

### 5.6 Structural validation

Add `_validate_aggregate_shape(...)` analogous to T2.3c but local to ProbLog:

```python
def _validate_aggregate_shape(aggregate):
    if not tuple len 3: raise ProbLogExportError(...)
    if kind not in _AGGREGATE_KINDS: raise ProbLogExportError(...)
    if count target is not None: raise
    if numeric target not "$" var: raise
    if filter not non-empty list: raise
    for filter_atom:
        if _is_aggregate(filter_atom): raise
        if filter_atom[0] not in _AGGREGATE_FILTER_ATOM_KINDS: raise
```

If a cmp operand is any tuple, route it to aggregate validation. Raw top-level atoms are not valid term operands; unknown tuple kinds should fail as `unsupported aggregate kind` rather than being quoted as literals.

### 5.7 Empty-set semantics

ProbLog expected behavior:

- `findall(..., Body, [])` succeeds with empty list if no solutions
- `length([], Count)` binds `Count = 0`
- `sum_list([], Sum)` binds `Sum = 0`
- `[] = [_|_]` fails

Thus:

- count/sum empty set remains a legal `0`
- min/max/mean empty set fails before `min_list/max_list/mean` computation
- enclosing comparison/binding fails, matching C101

### 5.8 S-class trigger analysis

| Trigger | T2.3d reality | Fire? |
|---|---|---|
| Public API impact | None; adapter export behavior + docs only | NO |
| Cross-commitment Q load-bearing | None expected; C99-C105 already locked by T2.3a | NO |
| Cross-engine semantic decision | None; mirrors T2.3c semantics in ProbLog syntax | NO |
| Public API rename | None | NO |
| Size budget | Estimated 250-450 LOC code + tests after T2.3c calibration | Within S with size caution |
| Substrate or SDK change | None | NO |

G7 discovered that the local ProbLog binary requires `:- use_module(library(lists)).` before `sum_list/2`, `min_list/2`, and `max_list/2` are available. This is now locked as a narrow S-class amendment: aggregate exports conditionally include the directive. If implementation discovers that the directive is insufficient or cannot represent the locked semantics without a broader runtime helper, pause and amend; if that changes semantics, escalate to M. `sum_list([], 0)` itself is not an open design choice.

### 5.9 G7 pre-implementation checks

Must be run and recorded in the audit log **before code edits**:

1. T2.3a substrate exists: `AggregateAtom`, `_AGGREGATE_KINDS`, validation, Python eval.
2. T2.3b SDK bridge can produce aggregate IR.
3. T2.3c `extract_where_variables(...)` excludes aggregate-local vars and remains importable from ProbLog.
4. ProbLog aggregate dispatch currently absent: `rg "AggregateAtom|_AGGREGATE_KINDS|aggregate|findall|sum_list|min_list|max_list" src/factgraph/adapters/problog/problog_export.py` has no semantic aggregate dispatch hits.
5. Current ProbLog exporter **silently mishandles** aggregate IR rather than rejecting it: aggregate tuple operands flow through `_to_problog_term:315-318` to `_to_problog_literal:343-355`, where unknown tuple values are JSON-encoded and quoted as Prolog atom literals such as `'["sum","$_agg1",[...]]'`. G7 smoke MUST reproduce this specific output shape to confirm the precondition gap and motivate cmp-branch aggregate routing.
6. Local Python/ProbLog test environment supports import of `tests.test_problog_export` after prior hygiene/fixture cleanup.
7. If a ProbLog binary is available cheaply, smoke `findall/3`, `sum_list/2`, `min_list/2`, `max_list/2`, `length/2`; if not available, record that this S-class slice verifies exported program text only. If list predicates require `library(lists)`, record that and keep the directive requirement in scope.

## 6. Boundaries And Invariants

- I1 — Aggregate is term-position only; no top-level aggregate atom kind.
- I2 — ProbLog aggregate lowering uses `findall/3` + list predicates; no custom runtime module.
- I2a — Aggregate exports include `:- use_module(library(lists)).` exactly when aggregate lowering requires list predicates; non-aggregate exports stay unchanged.
- I3 — min/max/mean empty set uses list non-empty guard `L = [_|_]` and fails the enclosing body.
- I4 — count/sum empty set returns 0.
- I5 — `not` in aggregate filter compiles through existing `\+(...)` recursion.
- I6 — Aggregate-local variables do not enter query variables because `extract_where_variables(...)` comes from T2.3c and is consumed unchanged.
- I7 — No SDK/core/application/Souffle changes.
- I8 — Adapter validation rejects unsupported aggregate kinds and unsupported filter atom kinds before emission.
- I9 — Docs row flips are mandatory because T2.3b/T2.3c docs currently point to T2.3.d for ProbLog support.
- I10 — Adapter-generated fresh variables use `Agg{Prefix}{N}` names, never `_to_problog_var(...)` / `V_...` names, so user variables such as `$agg_list_1` cannot collide with aggregate helper variables.

## 7. Acceptance

Minimum tests:

1. `count` aggregate exports `findall(1, (...), L)` + `length(L, R)`.
2. `sum` aggregate exports `findall(Target, (...), L)` + `sum_list(L, R)`.
3. `min` aggregate exports `L = [_|_]` guard + `min_list(L, R)`.
4. `max` aggregate exports `L = [_|_]` guard + `max_list(L, R)`.
5. `mean` aggregate exports `L = [_|_]`, `sum_list`, `length`, and `R is Sum / Count`.
6. Aggregate export includes `:- use_module(library(lists)).`; non-aggregate export does not gain this directive.
7. Empty-set guard is present for min/max/mean and absent for count/sum.
8. Aggregate in eq binding compiles as goals + `V_TOTAL = R`.
9. Aggregate in numeric comparison compiles as goals + `R > 3` or equivalent.
10. Two-aggregate comparison compiles both aggregate goal sequences and compares result vars.
11. Aggregate filter with `not` body exports nested `\+(...)`.
12. Aggregate-local vars do not appear in `% query_vars=...` or rule head variables.
13. Unknown aggregate kind rejects with `ProbLogExportError`.
14. Malformed target shape rejects.
15. Unsupported filter atom kind rejects.
16. Existing `ne` and arithmetic ProbLog tests still pass.
17. Full `tests.test_problog_export` passes.
18. Relevant cross-slice tests pass: T2.3a/T2.3b/T2.3c/Souffle unaffected.
19. Ruff clean on touched files.

## 8. Implementation Plan

1. Fork impl branch from scoped anchor.
2. Run and record §5.9 G7 precondition checks in audit log before code edits.
3. Add local aggregate constants + `_validate_aggregate_shape(...)`.
4. Add `_CompileContext` or equivalent fresh-var allocator.
5. Update `_compile_body(...)` / `_compile_atom(...)` signatures to thread context while preserving direct `_compile_atom(...)` tests.
5b. Update `export_problog(...)` to precompile rule bodies with a shared context and conditionally emit `:- use_module(library(lists)).` when aggregate lowering sets `ctx.requires_lists`.
6. Add `_compile_aggregate_parts(...)` using `findall/3` + list predicates.
7. Extend cmp branches for aggregate operands.
8. Ensure `not` recursion shares the context.
9. Add tests in `tests/test_problog_export.py` or a new focused `tests/test_problog_aggregate_export.py`.
10. Update `application/docs/rule.md` and `sdk/docs/03_rules_and_inferences.en.md`.
11. Run gates from §7.
12. If implementation deviates from list predicate assumptions, update blueprint/audit first.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md` — ProbLog adapter row: deferred → supported via `findall/3` + list predicates; empty min/max/mean guarded by non-empty-list check.
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` — §3.2 ProbLog adapter row: deferred → supported.

No new durable SDK API surface docs in `04_api_surface.en.md`.

## 10. Outcome

Implemented in:

| Commit | Purpose |
|---|---|
| `c3127703` | G7 precondition record + scoped amendment for conditional `:- use_module(library(lists)).` |
| `a33b876e` | Main ProbLog aggregate wire implementation, tests, and docs flip |
| `d7e2a650` | Step 4.7 follow-up: remove unused `_is_aggregate` helper |

### 10.1 Landed behavior

- `src/factgraph/adapters/problog/problog_export.py` now recognizes aggregate tuple operands in `eq`, `ne`, `gt`, `ge`, `lt`, and `le` cmp atoms.
- Aggregate lowering emits `findall/3` plus list predicates:
  - `count`: `findall(1, (...), L)` + `length(L, R)`
  - `sum`: `findall(Target, (...), L)` + `sum_list(L, R)`
  - `min` / `max`: non-empty-list guard `L = [_|_]` + `min_list` / `max_list`
  - `mean`: non-empty-list guard + `sum_list` + `length` + `R is Sum / Count`
- Aggregate exports conditionally include `:- use_module(library(lists)).`; non-aggregate exports do not gain the directive.
- Aggregate filter atoms compile through the same `_compile_atom(...)` path, including existing `not` recursion.
- Adapter-side structural validation rejects unknown aggregate kinds, malformed targets, malformed filters, unsupported filter atom kinds, and nested aggregates before emission.
- Query-variable extraction continues to come from T2.3c and excludes aggregate-local variables from exported heads.
- `src/factgraph/application/docs/rule.md` and `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` now mark ProbLog aggregate support as shipped.

### 10.2 Verification

Verification performed before closure:

```text
PYTHONPATH=src python -m unittest tests.test_problog_export
→ Ran 26 tests — OK

Cross-slice sweep:
PYTHONPATH=src python -m unittest \
  tests.test_problog_export \
  tests.test_problog_engine_eval \
  tests.test_souffle_aggregate_compile \
  tests.sdk.dsl.test_aggregate_ergonomic \
  tests.sdk.dsl.test_application_rule \
  tests.core.rules.test_aggregate_substrate \
  tests.core.rules.test_aggregate_eval \
  tests.application.protocol.test_rule \
  tests.application.protocol.test_rule_aggregate
→ Ran 114 tests — OK

python -m ruff check src/factgraph/adapters/problog/problog_export.py tests/test_problog_export.py
→ All checks passed
```

Local ProbLog binary smoke also passed after the G7 amendment:

- generated aggregate program included `:- use_module(library(lists)).`
- `problog <generated-file>` returned 0
- output included `answer(1,'Alice',...)`

Claude Step 4.7 review independently ran a broader relevant sweep:

- 26 T2.3d tests pass
- 124 cross-slice tests pass
- ruff clean
- 0 Blocker / 0 Required findings
- 1 Worth-considering finding: unused `_is_aggregate` helper, resolved by `d7e2a650`

### 10.3 Deviations and amendments

- **G7 amendment**: local ProbLog exposed `length/2` but not `sum_list/2`, `min_list/2`, or `max_list/2` without `library(lists)`. The blueprint was amended in `c3127703` before code edits. This did not change semantics; it added the conditional generated-program directive required to execute the locked list-predicate strategy.
- **Dead helper cleanup**: the first implementation included an unused `_is_aggregate(...)` helper. Step 4.7 review flagged it as Worth-considering; `d7e2a650` removed it rather than documenting it as future-use surface.
- **No baseline drift surfaced**: unlike prior ProbLog hygiene and fixture slices, T2.3d did not uncover a new unrelated failing test baseline.
- **No schema `number` vs `int` issue applies here**: ProbLog export is untyped at this layer and did not reuse the Souffle type-domain checks that exposed the earlier "number" / "int" note.

### 10.4 Archive readiness

The blueprint is ready for Step 4.9 archive:

- Status is `implemented`
- §10 Outcome is complete
- Audit log has closure event and decision note
- implementation and Step 4.7 follow-up are committed
- sacred `master` remained unchanged
- unrelated dirty set remained preserved
