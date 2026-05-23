# T2.3a — Core AggregateExpr substrate (IR + validation + Python eval + raw resolver)

- Status: implemented
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: task blueprint
- Inputs:
  - Parent essay [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md) §10.6.3 (C99) / §10.6.4 (C100) / §10.6.5 (C101) / §10.6.6 (C102) / §10.6.7 (C103) / §10.6.8 (C104) / §10.6.9 (C105) — 7 commitments lock AggregateExpr semantics.
  - Parent essay §8.8 — per-engine AggregateExpr lowering strategy (deferred to T2.3.c/d adapter sub-slices).
  - Track plan [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md) §1.2 G1-G7, §1.2.6 T2.3 row (S → 可能 M).
  - Archived T2.2 [2026-05-23_t2-2-arith-expr.md](../archive/2026-05-23_t2-2-arith-expr.md) — adapter parity pattern + builtin substrate precedent for arithmetic.
  - Archived T1.1 [2026-05-22_t1-1-rule-class-additive.md](../archive/2026-05-22_t1-1-rule-class-additive.md) — application Rule.where stores core AST atoms.
- Outputs / Downstream:
  - Core IR `AggregateAtom` type + parsing + IR-tuple round-trip.
  - Core validation:filter clause restrictions(C100)+ per-env aggregate-local var scoping(C104)+ numeric target type construct-time(C102 construct half).
  - Python evaluator:5 kinds(`count`/`sum`/`min`/`max`/`mean`)+ `AggregateNoValue` sentinel + empty set(C101)+ runtime numeric target(C102 runtime half)+ result binding(C105)+ **per-env aggregation**(C104 correlated)+ **raw aggregate term resolver in cmp / arith paths**(C101 NoValue propagation through ArithExpr operand).
  - Application Rule serialization:`_serialize_term` + `_collect_term_vars` aware of `AggregateAtom` as Term-position with filter-local var isolation.
  - Foundation for **T2.3b** (SDK ergonomic helpers + bridge passthrough + public docs) follow-up slice.
  - Foundation for **T2.3.c** (Souffle aggregate body wire) + **T2.3.d** (ProbLog findall + list predicates) adapter sub-slices.
- Related:
  - `src/factgraph/core/rules/where_ast.py`
  - `src/factgraph/core/rules/where_ast_validate.py`
  - `src/factgraph/core/rules/where_eval.py`
  - `src/factgraph/application/protocol/rule.py`
- Related Modules:
  - `src/factgraph/core/rules/where_ast.py` — adds `AggregateAtom` type + `_AGGREGATE_KINDS` constant + parse / lower / Term-type extension。
  - `src/factgraph/core/rules/where_ast_validate.py` — adds aggregate filter restrictions + variable scoping algorithm + numeric target construct + `AggregateValidationError` / `AggregateVariableScopeError`。
  - `src/factgraph/core/rules/where_eval.py` — adds **per-env** aggregate evaluator + `AggregateNoValue` sentinel + raw aggregate term resolver invoked from cmp / arith paths。
  - `src/factgraph/application/protocol/rule.py` — extends `_serialize_term` + `_collect_term_vars` for `AggregateAtom` Term-position with filter-local var isolation。
- Audit Log:
  - [2026-05-23_t2-3-aggregate-substrate.audit.md](./2026-05-23_t2-3-aggregate-substrate.audit.md)
- Branch: `v0.2.0-blueprint-t2-3-aggregate-substrate-2026-05-23`

> **Scope split note**:T2.3 was originally drafted as a single ~1160 LOC slice covering substrate + Python eval + SDK ergonomic helpers + bridge passthrough。Step 4.2 review surfaced P0 — agg_* helpers are public SDK API,not "None public API impact"。Slice now scoped as **T2.3a substrate-only**(no SDK ergonomic,no bridge ergonomic,no public docs)。**T2.3b** to follow with SDK helpers + bridge + public export policy。

## 1. Problem

Parent essay §10.6.3-§10.6.9 defines `AggregateExpr` as a **value-producing expression** that appears in comparison atom LHS / RHS,with 5 kinds(`count` / `sum` / `min` / `max` / `mean`),filter clause restrictions,empty-set / `AggregateNoValue` semantics,numeric target type constraints,snapshot semantics,variable scoping rules,and result binding behavior。

Verified shipped substrate(per G2 source-grep audit):

- `src/factgraph/core/rules/where_ast.py:95-96` lists only `_CMP_OPS = {"eq", "ne", "gt", "ge", "lt", "le"}` and `_BUILTIN_TAGS = {"add", "sub", "neg", "addc", "mulc"}` — **no aggregate kinds**。
- `src/factgraph/core/rules/where_ast.py` defines no `AggregateAtom` type。
- `src/factgraph/core/rules/where_ast_validate.py` has no aggregate validation function。
- `src/factgraph/core/rules/where_eval.py` has no aggregate evaluator function。
- `src/factgraph/adapters/{souffle,problog,pyreason}/` adapter modules have no `AggregateAtom` dispatch。

**100% genuinely new substrate**。Unlike T2.2(where ArithExpr substrate was already 5 builtin tags shipped in core/Souffle/Python and only ProbLog parity was missing),T2.3a builds **net-new** core IR + validation + Python eval layers。

**Critical evaluator path clarification**(per Step 4.2 v1 P2):`where_eval.evaluate_where`(`where_eval.py:41-88`)parses AST only for **validation gating**(line 52);**actual execution flows through `_normalize_where` → `_eval_body` using raw tuples**(line 78-79)。So T2.3a evaluator extensions must operate on **raw tuple shapes**,not AST dataclass instances。

## 2. Goals

### 2.1 C99 — Add `AggregateAtom` IR type + parse / lower / tag set

Add to `src/factgraph/core/rules/where_ast.py`:

- New `_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}` constant.
- New `AggregateAtom` frozen dataclass with fields `(kind, target, filter, origin)`:
  - `kind: str` in `_AGGREGATE_KINDS`
  - `target` — `None` for `count`;Term for `sum`/`min`/`max`/`mean`
  - `filter` — list of allowed atom kinds per C100
- IR tuple shape: `(kind, target_term, filter_ir_list)` parses to `AggregateAtom`。
- `parse_where_ir_to_ast` extended to recognize aggregate tags when they appear as **Term values inside CmpAtom IR**(not top-level atoms)。
- `lower_ast_to_where_ir` extended to round-trip `AggregateAtom`。

### 2.2 C99 — `AggregateAtom` as Term-position value within CmpAtom

`AggregateAtom` is NOT a top-level atom。It appears as **`CmpAtom.lhs` or `CmpAtom.rhs` value**。Top-level `where` list contains `CmpAtom("eq"|"gt"|...)` whose one side is `AggregateAtom`。Parent §10.6.3 lock:"agg 自身无 truth value(true/false 来自包裹 comparison 或 eq binding)"。

### 2.3 C100 — Filter clause validation (construct-time)

Add to `src/factgraph/core/rules/where_ast_validate.py`:

- `_validate_aggregate_filter(filter_atoms)` enforcing:
  - Filter is flat `list[Atom]`(no `OrExpr` / no nested aggregation)。
  - Allowed atom kinds in filter top-level:9 scalar kinds(`pred` / `eq` / `ne` / `gt` / `ge` / `lt` / `le` / `in` / `not`)from §10.1。
  - Forbidden in filter top-level:`RuleRefAtom` / nested `AggregateAtom` / `BuiltinAtom` in scalar comparison position。
  - `not` body recursion limit:8 kinds(去 nested `not`)/ no `OrExpr` / no `AggregateAtom` / no `BuiltinAtom` / no `RuleRefAtom`。
  - Violations → `AggregateValidationError` raised construct-time。

### 2.4 C104 — Variable scoping (precise dataflow rule per Step 4.2 v1 P3)

Add to `where_ast_validate.py`:

Aggregate term dataflow contract:

- **`requires` set**:`(vars in target ∩ outer_bound_vars) ∪ (vars in filter ∩ outer_bound_vars)` — only **correlated** vars
- **`binds` set**:`∅` — aggregate term itself does NOT bind any var
- **Result binding**:only via enclosing `CmpAtom("eq", outer_var, aggregate_term)` — the enclosing CmpAtom binds `outer_var`,not the aggregate term itself

Filter-local vars(introduced inside aggregate filter,not in `outer_bound_vars`)are **aggregate-scoped**:

- Filter validates with starting bound vars = `outer_correlated ∪ {filter-local vars bound within filter}`
- Filter-local vars MUST NOT appear in outer `Rule.where` atoms following the aggregate
- Application Rule `_collect_term_vars` MUST NOT collect filter-local vars into outer `seen_vars` / `ports` validation set(detail in §5.4)

Violations → `AggregateVariableScopeError` raised construct-time。

### 2.5 C102 — Numeric target type validation (construct + runtime)

Construct-time(`where_ast_validate.py`):

- For `kind in {"sum", "mean"}`:if `target` is `Const` with non-numeric value(string / bool / None / collection)→ `AggregateValidationError`。
- For `kind in {"sum", "mean"}` with `target` as `Var` → defer to runtime check(static type not known)。
- `count` ignores target type(target = None)。
- `min` / `max` accept numeric **or** orderable;runtime checks defer。

Runtime(`where_eval.py`):

- During aggregate evaluation,for each matched row's target value:
  - `sum` / `mean`:target must be `int` / `float`(not `bool`,not `str`,etc)。Non-numeric → aggregate result is `AggregateNoValue`(per parent §10.6.6 "atom violated 不污染 env,不中断其他 env")。
  - `min` / `max`:target must support `<` comparison;violations → `AggregateNoValue`。

### 2.5b — Target Var binding rule (construct-time, per Step 4.2 v2 P2)

For `kind in {"sum", "min", "max", "mean"}` with `target` as `Var`:

- Target Var **MUST be in** `outer_bound_vars ∪ filter_bound_vars`,where:
  - `outer_bound_vars` = vars bound by Rule.where atoms preceding the aggregate(correlated scope)
  - `filter_bound_vars` = vars bound BY filter atoms(`pred` binding new Var / `eq` with Var on unbound side / `in` declaring Var)
- If target Var is **NOT** in either set → it has no value source at runtime → `AggregateVariableScopeError` raised construct-time。

Examples:

- `agg_sum(Var("$amount"), filter=[PredAtom("Order:exists", [Var("$o")]), CmpAtom("eq", AttrRef-equivalent(Var("$o"), "amount"), Var("$amount"))])` → target `$amount` bound by filter's eq → OK。
- `agg_sum(Var("$amount"), filter=[PredAtom("Order:exists", [Var("$o")])])` → target `$amount` not bound anywhere → **reject construct-time**。
- `agg_sum(Var("$u_balance"), filter=[PredAtom("Order:exists", [Var("$o")])])` where `$u_balance` is outer correlated → OK if `$u_balance` ∈ outer_bound_vars。

### 2.6 C101 — Empty set + `AggregateNoValue` sentinel + propagation via raw resolver

Add to `where_eval.py`:

- Module-level `AggregateNoValue` sentinel:singleton class instance,distinguishable from `None`。
- Empty set behavior(no rows match filter):
  - `count` → returns `0`(int)
  - `sum` → returns `0`(int)
  - `min` / `max` / `mean` → returns `AggregateNoValue`
- `AggregateNoValue` propagation(per Step 4.2 v1 P4 — implement in raw resolver):
  - **Result binding**(C105):`Var("v") == AggregateNoValue` → atom violated,v stays unbound,env unchanged。
  - **Comparison**:`<` / `>` / `==` / `!=` between AggregateNoValue and anything → atom violated。
  - **ArithExpr operand propagation**:if any operand of `add`/`sub`/`addc`/`mulc`/`neg` evaluates to `AggregateNoValue`,the arithmetic result is `AggregateNoValue` and the outer atom is violated。This requires raw resolver invocation from `_eval_arith_atom` operand resolution path(§5.7)。
  - JSON serialization marker:`{"__aggregate_no_value__": true}`(per parent §10.6.5)。

### 2.7 C103 — Snapshot semantics (matched_count = view-projected fact rows)

In Python evaluator,aggregate matching iterates view-projected fact rows in the current evaluator env-list。matched_count = number of envs that satisfy filter,not ledger-raw assertion count。

Per-env aggregation algorithm in §5.5 honors this conceptually:filter applies to the env-derived view,not the ledger。

### 2.8 C105 — Result binding semantics (per-env, per Step 4.2 v1 P1)

For each outer env,compute aggregate result(int / float / `AggregateNoValue`),then:

- For `("eq", Var("v"), aggregate_atom)` pattern(or symmetric):
  - If aggregate_result is `AggregateNoValue` → atom violated,v stays unbound,env unchanged。
  - Elif v is unbound in env → bind v = aggregate_result。
  - Elif v is bound → equality check;mismatch → atom violated。
- For comparison atoms(`gt` / `ge` / `lt` / `le` / `ne` / `eq`)other than binding:
  - If aggregate_result is `AggregateNoValue` → atom violated。
  - Else perform comparison against the other operand。

### 2.9 G7 — Pre-impl precondition checks

Per §5.8 — verify substrate empty + C99-C105 semantic clarity + raw evaluator path correct + no shipped AggregateAtom Term type collision before implementation。

## 3. Non-goals

- **No SDK ergonomic helpers**(`agg_count` / `agg_sum` / `agg_min` / `agg_max` / `agg_mean`)— **deferred to T2.3b**。User-facing usability lands when T2.3b ships SDK helpers + bridge ergonomic。
- **No `_AggregateRef` DSL type**(deferred to T2.3b)。
- **No bridge support for aggregate IR**(deferred to T2.3b,per Step 4.2 v2 P4 correction):**`build_application_rule` does NOT support aggregate-containing IR in T2.3a**。`sdk/dsl/application_rule.py` `_collect_vars_from_term`(`:181`)and var canonicalization(`:250`)don't recognize `AggregateAtom`。**T2.3a supports DIRECT application Rule construction**(via `application/protocol/rule.py` with `AggregateAtom` Term-position arguments),NOT the SDK→application bridge ergonomic path。End-to-end DSL syntax for aggregate requires T2.3b。
- **No SDK / application public docs update**(deferred to T2.3b)— user-facing aggregate usage docs land when SDK ergonomic is shipped。
- **No Souffle aggregate body wire**(deferred to T2.3.c sub-slice)。
- **No ProbLog `findall/3` + list predicates wire**(deferred to T2.3.d sub-slice)。
- **No PyReason aggregate support**(parent essay §8.4 / C95 explicit defer)。
- **No new aggregate kinds beyond 5**(parent essay §10.6.3 fixed set)。
- **No OR group in filter clause**(parent C100)。
- **No nested aggregate**(C100)。
- **No `BuiltinAtom` inside filter scalar comparison position**(C100)。
- **No `RuleRefAtom` inside aggregate filter**(C100 + parent C9)。
- **No nested `not` in `not` body within aggregate filter**(C100)。
- **No implicit cast / parse**(parent §10.5)。
- **No new arithmetic operator integration with aggregate**(`mod` / `%` / `**`)。

## 4. Current Context

### 4.1 G2/G3 — `where_ast.py` shipped substrate empty

`src/factgraph/core/rules/where_ast.py:95-96`:

```python
_CMP_OPS = {"eq", "ne", "gt", "ge", "lt", "le"}
_BUILTIN_TAGS = {"add", "sub", "neg", "addc", "mulc"}
```

No aggregate kinds。No `AggregateAtom` dataclass。No aggregate parse branch。

`src/factgraph/core/rules/where_ast.py:31` defines `Term: TypeAlias = Var | Const`。Per Step 4.2 v1 P5,this needs extension to include `AggregateAtom`,but `AggregateAtom.filter: list[Atom]` references `Atom` defined later in the file。Resolved in §5.2 via forward-ref strategy。

`src/factgraph/core/rules/where_ast.py:77` defines `Atom: TypeAlias = PredAtom | RuleRefAtom | CmpAtom | InAtom | BuiltinAtom | NotAtom` — extension NOT needed because `AggregateAtom` is Term-position,not top-level Atom。

### 4.2 G2/G3 — `where_ast_validate.py` shipped validation has no aggregate path

`src/factgraph/core/rules/where_ast_validate.py:33-34` defines `_CMP_OPS` and `_CMP_FILTER_OPS`(same as where_ast.py)。No aggregate validation function exists。

`_validate_builtin_shape(atom)` covers `add`/`sub`/`neg`/`addc`/`mulc`(verified during T2.2 review)。No equivalent `_validate_aggregate_shape`。

`_validate_atom_dataflow` / `_validate_and_dataflow` are existing data flow validators。Aggregate validation integrates via:
- Construct-time:filter restrictions + numeric target + scoping rule(§2.4).
- Dataflow:aggregate term `requires = correlated` / `binds = ∅`(§2.4).

### 4.3 G2/G3 — `where_eval.py` raw tuple evaluator path

`src/factgraph/core/rules/where_eval.py:41-88` `evaluate_where`:

- Line 52:parse AST `parse_where_ir_to_ast(where)` — **only for validation gating**。
- Line 53-57:`validate_where_ast(ast, mode="python", ...)` — validation only。
- Line 61:`bodies = _normalize_where(where)` — raw tuple bodies。
- Line 78-79:`for body in bodies: body_bindings = _eval_body(view_facts, body, ast_gate_on=...)` — **actual execution on raw tuples**。

So T2.3a runtime extensions operate on **raw tuple shapes**,not AST dataclass instances:

- `("eq", "$v", ("agg_sum", "$amount", [...filter_ir...]))` — aggregate appears as Term-position raw tuple inside CmpAtom raw tuple。
- New `_is_aggregate_term(term)` helper in `where_eval.py` recognizes when a term is an aggregate tuple。
- New `_resolve_aggregate_term_for_env(env, aggregate_term, ast_gate_on)` computes aggregate value/NoValue for one outer env(per Step 4.2 v1 P1 per-env semantics)。
- Existing `_eval_cmp_atom` + `_eval_arith_atom` operand resolvers extended to call `_resolve_aggregate_term_for_env` when operand is aggregate tuple。

`_ARITH_KINDS = {"add", "sub", "neg", "addc", "mulc"}`(line 38)— for T2.3a NoValue × ArithExpr propagation,`_eval_arith_atom`'s operand resolver(`_require_resolved_arith` 或类似)gains AggregateNoValue propagation behavior。

### 4.4 G2/G3 — Application Rule serialization needs filter-local var isolation

`src/factgraph/application/protocol/rule.py:170` `_collect_term_vars(term, *, field_name, seen_vars)` currently handles `Var` and `Const`:

- `Var` → `seen_vars.add(term)`
- `Const` → no-op

Per Step 4.2 v1 P3,when extended for `AggregateAtom`:

- Collect target vars(if target is Var)— if Var is in **outer correlated** scope,add to `seen_vars`;otherwise treat as filter-local(do NOT add)。
- Collect filter atom vars **only correlated subset** — filter-local vars do NOT enter `seen_vars`。

Implementation note:since application Rule does not know `outer_bound_vars` at `_collect_term_vars` time(it's called during construction of frozen Rule),actual implementation uses a two-pass:

- Pass 1:collect ALL vars from outer atoms first(non-aggregate top-level atoms)。This becomes `outer_bound_vars` snapshot。
- Pass 2:process aggregate Term-position atoms with `outer_bound_vars` context;only correlated subset enters `seen_vars`。

Alternative simpler impl:`AggregateAtom._collect_correlated_vars(outer_bound_vars: set[Var]) -> set[Var]` helper method,called in pass-2。Details in §5.6。

`_serialize_atom` / `_serialize_term` handle PredAtom/CmpAtom/InAtom/BuiltinAtom/NotAtom/Var/Const。`AggregateAtom` Term-position serialization extension:

- `_serialize_term(term)` new branch for `AggregateAtom`:returns `{"type": "AggregateAtom", "kind": ..., "target": ..., "filter": [..]}` with deterministic filter ordering(maintains user-written order — no reordering)。
- `_collect_term_vars` new branch per above。

### 4.5 G2/G3 — Application Rule allowlist unchanged

`src/factgraph/application/protocol/rule.py:_ALLOWED_ATOM_TYPES = (PredAtom, CmpAtom, InAtom, BuiltinAtom, NotAtom)`(T1.1 archived lock)。

T2.3a places `AggregateAtom` as `CmpAtom.lhs`/`.rhs` Term value,NOT as top-level Atom。**`_ALLOWED_ATOM_TYPES` not extended**。Verified by §6 invariants + §7 acceptance scope diff check。

### 4.6 Parent essay C99-C105 semantic lock summary

All 7 commitments in parent §10.6.3-§10.6.9 are **fully specified semantically**。**No load-bearing decision needed** — implementation is direct translation of parent essay semantics。G7 precondition §5.8 explicitly verifies this。

## 5. Proposed Shape

### 5.1 AggregateAtom as Term-position value within CmpAtom

**Design choice**:`AggregateAtom` is not a top-level Atom kind。Top-level `Rule.where` list contains `CmpAtom` whose `lhs` or `rhs` carries an `AggregateAtom` value。

Rationale:
- Parent essay §10.6.3 "agg 自身无 truth value(true/false 来自包裹 comparison 或 eq binding)"。
- Keeps T1.1 `_ALLOWED_ATOM_TYPES` allowlist unchanged。
- Mirrors arithmetic-in-comparison pattern but with single-value-per-env compute(not multi-atom emit like T2.2 ArithExpr lowering)。

**IR tuple shape for aggregate inside CmpAtom**:

```python
# count
("eq", Var("$v"), ("count", None, [filter_ir_atoms]))
# sum/min/max/mean
("gt", ("sum", "$amount", [filter_ir_atoms]), 100)
# binding pattern
("eq", "$v", ("sum", "$amount", [filter_ir_atoms]))
```

### 5.2 Term type extension via forward-ref strategy(Step 4.2 v1 P5)

Current `Term: TypeAlias = Var | Const`(`where_ast.py:31`)defined BEFORE `Atom` and `AggregateAtom`。Two acceptable strategies:

**Strategy A — Restructure type alias definitions(preferred)**:

Move `Term` and `Atom` aliases to AFTER all dataclass definitions:

```python
# where_ast.py
@dataclass(frozen=True)
class Var: ...

@dataclass(frozen=True)
class Const: ...

@dataclass(frozen=True)
class PredAtom: ...
# ... other atom types ...

@dataclass(frozen=True)
class AggregateAtom:
    kind: str
    target: "Term | None"  # forward ref to Term defined below
    filter: "list[Atom]"   # forward ref to Atom defined below
    origin: Origin | None = None

# Type aliases at end
Term: TypeAlias = Var | Const | AggregateAtom
Atom: TypeAlias = PredAtom | RuleRefAtom | CmpAtom | InAtom | BuiltinAtom | NotAtom
```

**Strategy B — String forward refs in AggregateAtom**:

Keep current alias order;use string forward refs in AggregateAtom fields(`target: "Term"`,`filter: "list[Atom]"`)。

**Implementation chose Strategy A**(restructure)— cleaner runtime semantics,no string forward-ref。If Strategy A causes other test breakage during impl,fall back to Strategy B with explicit `__future__ import annotations` reliance and document deviation。

### 5.3 Filter validation algorithm (C100, precise)

```python
# where_ast_validate.py additions
_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}
_AGGREGATE_FILTER_TOP_LEVEL_ALLOWED = {"pred", "eq", "ne", "gt", "ge", "lt", "le", "in", "not"}
_AGGREGATE_FILTER_NOT_BODY_ALLOWED = _AGGREGATE_FILTER_TOP_LEVEL_ALLOWED - {"not"}


def _validate_aggregate_atom_shape(atom: "AggregateAtom") -> None:
    # kind check
    if atom.kind not in _AGGREGATE_KINDS:
        raise AggregateValidationError(f"unsupported aggregate kind: {atom.kind}")
    # target shape per kind
    if atom.kind == "count":
        if atom.target is not None:
            raise AggregateValidationError("count target must be None")
    else:
        if atom.target is None:
            raise AggregateValidationError(f"{atom.kind} target must not be None")
    # numeric target construct-time (C102 construct half)
    if atom.kind in {"sum", "mean"} and isinstance(atom.target, Const):
        val = atom.target.value
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise AggregateValidationError(f"{atom.kind} target Const must be int/float, got {type(val).__name__}")
    # filter top-level kind check
    for idx, f_atom in enumerate(atom.filter):
        kind = _get_atom_kind(f_atom)
        if kind not in _AGGREGATE_FILTER_TOP_LEVEL_ALLOWED:
            raise AggregateValidationError(f"filter[{idx}] kind not allowed in aggregate filter: {kind}")
        if isinstance(f_atom, NotAtom):
            _validate_aggregate_not_body(f_atom.body, parent_idx=idx)


def _validate_aggregate_not_body(body, *, parent_idx: int) -> None:
    # body is AndExpr or list of Atoms; iterate atoms
    atoms = body.atoms if hasattr(body, "atoms") else body
    for idx, b_atom in enumerate(atoms):
        kind = _get_atom_kind(b_atom)
        if kind not in _AGGREGATE_FILTER_NOT_BODY_ALLOWED:
            raise AggregateValidationError(
                f"filter[{parent_idx}].not.body[{idx}] kind not allowed: {kind} (nested not / aggregate / arith forbidden)"
            )


class AggregateValidationError(WhereASTValidationError): ...
class AggregateVariableScopeError(WhereASTValidationError): ...
```

### 5.4 Variable scoping algorithm (C104, precise)

Aggregate term dataflow:

```python
# AggregateAtom helper / where_ast_validate.py
def _aggregate_correlated_requires(
    agg: "AggregateAtom",
    outer_bound_vars: set[str],
) -> set[str]:
    """Vars in target ∪ filter that are bound outside the aggregate (correlated)."""
    target_vars = _collect_vars_in_term(agg.target) if agg.target else set()
    filter_vars = set()
    for f_atom in agg.filter:
        filter_vars |= _collect_vars_in_atom(f_atom)
    return (target_vars | filter_vars) & outer_bound_vars


def _aggregate_local_vars(
    agg: "AggregateAtom",
    outer_bound_vars: set[str],
) -> set[str]:
    """Vars introduced inside filter that are NOT in outer scope (aggregate-local)."""
    filter_vars = set()
    for f_atom in agg.filter:
        filter_vars |= _collect_vars_in_atom(f_atom)
    return filter_vars - outer_bound_vars


def _validate_aggregate_scoping(
    agg: "AggregateAtom",
    outer_bound_vars: set[str],
    *,
    subsequent_atoms: list,  # outer atoms following this aggregate
) -> None:
    """Aggregate-local vars must NOT appear in outer atoms following this aggregate."""
    local_vars = _aggregate_local_vars(agg, outer_bound_vars)
    for s_atom in subsequent_atoms:
        s_vars = _collect_vars_in_atom(s_atom)
        leaked = local_vars & s_vars
        if leaked:
            raise AggregateVariableScopeError(
                f"aggregate-local vars leak into outer scope: {sorted(leaked)}"
            )
```

**Application Rule contract**(applied in `application/protocol/rule.py`):

- `_collect_term_vars(term, *, field_name, seen_vars)` for `AggregateAtom` Term:
  - Collect target vars `→ seen_vars`(target is in outer scope or filter-local;if in outer scope it's correlated and should appear elsewhere too — safe to add;if filter-local it's an error caught by where_ast_validate scoping check before this layer runs)
  - Collect ONLY correlated filter vars `→ seen_vars`
  - Filter-local vars from filter atoms NOT added(per validation guarantee they don't leak)

### 5.5 Per-env aggregate evaluator (C104 + C105 correlated, Step 4.2 v1 P1)

```python
# where_eval.py additions
class _AggregateNoValueSentinel:
    def __repr__(self) -> str: return "AggregateNoValue"
    def __reduce__(self): return (_aggregate_no_value_marker, ())

AggregateNoValue = _AggregateNoValueSentinel()
_aggregate_no_value_marker = lambda: AggregateNoValue


def _is_aggregate_term(term: Any) -> bool:
    """Check if a raw tuple term is an aggregate term."""
    return (
        isinstance(term, tuple)
        and len(term) == 3
        and term[0] in _AGGREGATE_KINDS
    )


def _resolve_aggregate_term_for_env(
    env: dict[str, Any],
    aggregate_term: tuple[str, Any, list[Any]],
    view_facts: dict[str, list[tuple[Any, ...]]],
    *,
    ast_gate_on: bool,
) -> Any:
    """Compute aggregate result for one outer env (per-env correlated semantics).

    Returns int/float scalar or AggregateNoValue.
    """
    kind, target, filter_atoms = aggregate_term

    # Seed evaluation with the current outer env so correlated vars are bound.
    # Run filter atoms over view_facts starting from [env] env-list.
    matched_envs = _eval_body(view_facts, filter_atoms, ast_gate_on=ast_gate_on, initial_envs=[env])

    if kind == "count":
        return len(matched_envs)

    if not matched_envs:
        # Empty set behavior (C101)
        if kind == "sum":
            return 0
        return AggregateNoValue  # min/max/mean

    target_values = []
    for m_env in matched_envs:
        v = _resolve_term_in_env(m_env, target)
        target_values.append(v)

    # Runtime numeric target check (C102 runtime) for sum/mean
    if kind in {"sum", "mean"}:
        for v in target_values:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return AggregateNoValue

    if kind == "sum":
        return sum(target_values)
    if kind == "mean":
        return sum(target_values) / len(target_values)
    if kind == "min":
        try: return min(target_values)
        except TypeError: return AggregateNoValue
    if kind == "max":
        try: return max(target_values)
        except TypeError: return AggregateNoValue
    raise WhereValidationError(f"unsupported aggregate kind: {kind}")
```

`_eval_body(view_facts, body, ast_gate_on, initial_envs=...)` — existing `_eval_body` may not support `initial_envs` parameter。If not,extend it to accept an initial env list(default `[{}]`),so filter atoms can be evaluated starting from the correlated env。

### 5.6 Raw aggregate term resolver in cmp / arith paths (Step 4.2 v1 P2 + P4)

`_eval_cmp_atom`(or whatever name handles comparison atoms in raw evaluator)— for each env:

```python
def _resolve_cmp_operand_for_env(env, operand, view_facts, ast_gate_on):
    if _is_aggregate_term(operand):
        return _resolve_aggregate_term_for_env(env, operand, view_facts, ast_gate_on=ast_gate_on)
    # existing var / const resolution
    return _resolve_term_in_env(env, operand)


# In comparison evaluator
def _eval_cmp_atom(view_facts, atom, env, *, ast_gate_on):
    op, lhs, rhs = atom
    lhs_val = _resolve_cmp_operand_for_env(env, lhs, view_facts, ast_gate_on)
    rhs_val = _resolve_cmp_operand_for_env(env, rhs, view_facts, ast_gate_on)
    # NoValue handling (C101 + C105)
    if lhs_val is AggregateNoValue or rhs_val is AggregateNoValue:
        return []  # atom violated for this env
    # eq with one side Var(unbound) → binding; existing behavior
    # other comparison ops → numeric compare
    ...
```

`_eval_arith_atom` operand resolver(per Step 4.2 v1 P4 — NoValue × ArithExpr):

```python
def _resolve_arith_operand_for_env(env, operand, view_facts, ast_gate_on):
    if _is_aggregate_term(operand):
        return _resolve_aggregate_term_for_env(env, operand, view_facts, ast_gate_on=ast_gate_on)
    # existing var / const resolution
    return _resolve_term_in_env(env, operand)


# In arith evaluator (existing _eval_arith_atom)
def _eval_arith_atom(view_facts, atom, envs, *, ast_gate_on):
    kind = atom[0]
    out = []
    for env in envs:
        # resolve operands per env (may produce AggregateNoValue)
        if kind == "add":
            _, z, x, y = atom
            x_val = _resolve_arith_operand_for_env(env, x, view_facts, ast_gate_on)
            y_val = _resolve_arith_operand_for_env(env, y, view_facts, ast_gate_on)
            if x_val is AggregateNoValue or y_val is AggregateNoValue:
                continue  # atom violated for this env
            result = x_val + y_val
            new_env = {**env, z: result}
            out.append(new_env)
        # similar for sub/neg/addc/mulc with aggregate-term aware operand resolution
        ...
    return out
```

**Key invariant**:NoValue never leaks as a Python exception。It causes atom violation(env excluded from output)per parent §10.6.5 / C101。

### 5.6b — Full where_eval.py helper coverage (Step 4.2 v2 P3)

Aggregate-term-aware extension MUST cover all raw-tuple helpers that touch term values, not just cmp/arith resolvers:

| Helper | Location | Aggregate-term-aware required because |
|---|---|---|
| `_eval_cmp_atom` operand resolver | `where_eval.py` cmp path | Operand may be aggregate tuple → resolve per env(§5.5)|
| `_eval_arith_atom` operand resolver | `where_eval.py` arith path | Operand may be aggregate tuple → resolve + NoValue propagation(§5.6)|
| `_validate_atom` | `where_eval.py:355` | Validates atom shape during evaluation prep;must recognize aggregate as Term-position(not unsupported kind)|
| `_validate_arith_atom` | `where_eval.py` arith validator | When ArithExpr operand is aggregate tuple, validate the aggregate tuple shape recursively or accept it as deferred-eval-time |
| `_term_known_for_plan` | `where_eval.py:891` | Planner asks "is this term known at this point?" Aggregate tuple is known **per env at evaluation time**;planner must NOT treat aggregate as never-known or always-known |
| `_atom_eval_score` | `where_eval.py:991` | Planner orders atoms by cost;aggregate atom is expensive(scans filter)— must score appropriately,not 0-cost |
| `_vars_in_atoms` | `where_eval.py:1067` | Used for not-body correlation + query var extraction;aggregate tuple's correlated vars(target ∪ filter ∩ outer)must be returned;filter-local vars must NOT |

Implementation contract:each helper gains an `_is_aggregate_term(term)` check + delegate to aggregate-aware branch。Without these,planner may misorder, not-body correlation may drop aggregate-internal vars, validation may reject aggregate tuples as unknown kind。

### 5.7 Application Rule serialization branches(two-pass filter-local var isolation per Step 4.2 v1 P3 + v2 P1)

`application/protocol/rule.py` Rule `__post_init__` revised to **two-pass algorithm**(per Step 4.2 v2 P1 — explicit outer_vars context,no "trust constructor" punt):

```python
def __post_init__(self):
    # ... existing 5-field validation ...

    # Pass 1: collect outer_seen_vars from non-aggregate top-level atoms.
    # Iterate self.where (top-level CmpAtom / PredAtom / InAtom / BuiltinAtom / NotAtom).
    # For each top-level atom, collect Var occurrences EXCLUDING any AggregateAtom Term-position values
    # (we don't peek inside aggregates at this pass).
    outer_seen_vars: set[Var] = set()
    for idx, atom in enumerate(self.where):
        _collect_non_aggregate_atom_vars(
            atom, field_name=f"where[{idx}]", seen_vars=outer_seen_vars
        )

    # Pass 2: process AggregateAtom Term-position values inside CmpAtom atoms.
    # Only correlated vars (target/filter ∩ outer_seen_vars) flow into the final seen_vars set;
    # filter-local vars stay isolated within the aggregate.
    seen_vars: set[Var] = set(outer_seen_vars)
    for idx, atom in enumerate(self.where):
        _collect_aggregate_term_correlated_vars(
            atom,
            field_name=f"where[{idx}]",
            outer_seen_vars=outer_seen_vars,
            seen_vars=seen_vars,
        )

    # ports validation now uses seen_vars (outer + aggregate-correlated)
    # Filter-local vars are not in seen_vars → ports cannot reference them.
    # ... ports validation against seen_vars ...


def _collect_non_aggregate_atom_vars(atom, *, field_name, seen_vars):
    """Collect Var occurrences from an atom, EXCLUDING AggregateAtom Term-position values.

    Treats AggregateAtom-typed terms as opaque (not recursed into) during pass 1.
    """
    if isinstance(atom, PredAtom):
        for term in atom.terms:
            if isinstance(term, Var):
                seen_vars.add(term)
            # Const ignored
            # AggregateAtom in pred terms is forbidden by validator (aggregate is CmpAtom-only)
    elif isinstance(atom, CmpAtom):
        for term in [atom.lhs, atom.rhs]:
            if isinstance(term, Var):
                seen_vars.add(term)
            # AggregateAtom in CmpAtom Term-position: SKIPPED in pass 1
            # (handled in pass 2 via _collect_aggregate_term_correlated_vars)
    # ... similar for InAtom / BuiltinAtom / NotAtom ...


def _collect_aggregate_term_correlated_vars(atom, *, field_name, outer_seen_vars, seen_vars):
    """Pass 2: walk atom for AggregateAtom Term-position values; collect ONLY correlated vars."""
    if isinstance(atom, CmpAtom):
        for term in [atom.lhs, atom.rhs]:
            if isinstance(term, AggregateAtom):
                _collect_correlated_from_aggregate(
                    term,
                    field_name=field_name,
                    outer_seen_vars=outer_seen_vars,
                    seen_vars=seen_vars,
                )
    # NotAtom body / other atoms with potential nested CmpAtom: recurse similarly


def _collect_correlated_from_aggregate(agg, *, field_name, outer_seen_vars, seen_vars):
    """Collect target vars always + correlated filter vars; filter-local non-target vars isolated.

    Per Step 4.2 v3 P1 — distinguish outer bound/order semantics (validator job) from
    Rule seen_vars/ports semantics (this function's job):

    - **Target Vars are collected always** because target is the "input to aggregate from
      outside the filter scope" — the user expression that produces values for reduction.
      If target Var is correlated to outer, it's reachable from outer ports.
      If target Var is filter-bound (e.g., `agg_sum($amount, where=[..eq $amount..])`),
      collection through target reflects that target is the aggregation expression;
      whether ports reference target Var directly is the user's choice.
    - **Filter Vars are collected only if correlated** to outer (filter_vars ∩ outer_seen_vars).
      Filter-local-only vars (introduced + bound inside filter, never seen in outer or in
      target) are aggregate-local and never enter seen_vars.
    """
    target_vars = _collect_vars_in_term_or_aggregate(agg.target) if agg.target else set()
    filter_vars: set[Var] = set()
    for f_atom in agg.filter:
        _collect_non_aggregate_atom_vars(f_atom, field_name=f"{field_name}.filter", seen_vars=filter_vars)
    # Target vars: collect ALL (per v3 P1)
    seen_vars |= target_vars
    # Filter vars: collect only correlated subset
    correlated_filter = filter_vars & outer_seen_vars
    seen_vars |= correlated_filter
    # Aggregate-local-only vars (filter_vars - outer_seen_vars - target_vars) are isolated.


def _serialize_term(term):
    if isinstance(term, Var): return _serialize_var(term)
    if isinstance(term, Const): return _serialize_const(term)
    if isinstance(term, AggregateAtom):  # NEW
        return _serialize_aggregate_atom(term)
    raise RuleValidationError(...)


def _serialize_aggregate_atom(atom: AggregateAtom) -> dict:
    return {
        "type": "AggregateAtom",
        "kind": atom.kind,
        "target": _serialize_term(atom.target) if atom.target else None,
        "filter": [_serialize_atom(a) for a in atom.filter],  # preserves user-written order for canonical digest
    }
```

**Two-pass guarantee**(per Step 4.2 v2 P1 + v3 P1 refinement):

- Pass 1 collects outer Var occurrences,treating AggregateAtom Term-position values as opaque(NOT recursed)。This gives clean `outer_seen_vars` set。
- Pass 2 walks aggregate Term-position values with `outer_seen_vars` context and collects(per v3 P1):
  - **Target Vars ALWAYS**:`target_vars` added to `seen_vars` unconditionally(target is "aggregate external input")
  - **Filter correlated subset only**:`filter_vars ∩ outer_seen_vars` added to `seen_vars`
  - **Aggregate-local-only filter Vars**(`filter_vars - outer_seen_vars - target_vars`)NEVER enter `seen_vars`
- ports validation against `seen_vars`(after pass 2)can reference target Vars + outer + correlated filter Vars,but cannot reference aggregate-local-only Vars。

**This is NOT "trust the constructor"** — application Rule itself enforces the isolation rule。`where_ast_validate._validate_aggregate_scoping` provides additional defense for AST-validation path,but application Rule's own pass-2 algorithm is independently correct。

If `where_ast_validate` is bypassed(e.g., direct application Rule construction without going through `lower_ast_to_where_ir → parse_where_ir_to_ast → validate_where_ast`),application Rule still correctly isolates filter-local vars。Validator(at AST layer)additionally rejects aggregate-local vars referenced by subsequent outer atoms construct-time — that's an extra check at AST layer,not the only line of defense。

### 5.8 G7 pre-impl precondition

Before implementation:

1. **Substrate empty**:`_BUILTIN_TAGS` in `where_ast.py:96` does NOT contain `count`/`sum`/`min`/`max`/`mean`;`where_ast.py` does NOT define `AggregateAtom`;`where_ast_validate.py` has NO aggregate validation;`where_eval.py` has NO aggregate evaluator;adapter dispatch has NO aggregate branches。
2. **Raw evaluator path**:verify `where_eval.evaluate_where:78-79` does indeed call `_eval_body(view_facts, body, ...)` with raw tuple `body`,not AST dataclass。
3. **`_eval_body` extensibility**:verify whether `_eval_body` accepts `initial_envs` parameter — if not,plan §5.5 extension to add it。
4. **Type alias restructure(§5.2 Strategy A)** — verify no existing code relies on `Term` being defined at current line 31 position(grep `from .where_ast import Term` and equivalent)。
5. **C99-C105 unambiguity**:re-read parent §10.6.3-§10.6.9 + §8.8 — confirm semantic completeness。**If ambiguity surfaces,escalate slice from S to M,open Stage 2 decision doc for that point,pause impl**。

If any check #1-4 fails → amend blueprint。
If check #5 surfaces ambiguity → escalate to M class with decision doc。

### 5.9 Tests structure

```
tests/core/rules/test_aggregate_substrate.py  (new ~250 LOC)
- TestAggregateAtomIR:parse / lower / round-trip for 5 kinds
- TestAggregateFilterValidation:reject OR / nested aggregate / BuiltinAtom in filter / RuleRefAtom / nested not
- TestAggregateVariableScoping:correlated OK / aggregate-local doesn't leak (validator raises AggregateVariableScopeError)
- TestAggregateNumericTargetConstruct:reject string Const for sum/mean
- TestAggregateTermInCmpAtom:CmpAtom with AggregateAtom Term-position parses correctly
- TestAggregateNoValueRepr:singleton identity + JSON marker

tests/core/rules/test_aggregate_eval.py  (new ~300 LOC)
- TestAggregateEvalCount:per-env count over filter, correlated outer var (per Step 4.2 v1 P1)
  - Two outer envs (e.g., user u-1 and user u-2) get DIFFERENT counts of their respective orders
- TestAggregateEvalSum:per-env sum
- TestAggregateEvalMin / Max / Mean:per-env reduce
- TestAggregateEvalEmptySet:count/sum → 0; min/max/mean → NoValue
- TestAggregateEvalRuntimeNumericTarget:non-numeric matched row → NoValue (not exception)
- TestAggregateNoValueInComparison:NoValue gt/lt/eq → atom violated for that env, other envs OK
- TestAggregateNoValueInArith:NoValue add/sub/addc/mulc operand → atom violated, env excluded (per Step 4.2 v1 P4)
- TestAggregateResultBinding:Var unbound → bind; Var bound → equality check; NoValue → violated

tests/application/protocol/test_rule_aggregate.py  (new ~150 LOC)
- TestApplicationRuleAcceptsAggregateTerm:Rule with CmpAtom(Var, AggregateAtom) accepts
- TestApplicationRuleAggregateContentDigest:deterministic across processes; filter order preserved
- TestApplicationRuleFilterLocalVarIsolation:validator rejects leaked filter-local vars before application Rule construction
- TestApplicationRuleAggregateTermInPort:aggregate-local vars NOT in ports
```

Estimated test LOC ~700。

### 5.10 Size estimate

| Component | Est. LOC |
|---|---|
| `where_ast.py` AggregateAtom + parse + lower + Term restructure | ~100 |
| `where_ast_validate.py` validation(filter + scoping + numeric construct + error classes) | ~180 |
| `where_eval.py` per-env evaluator + AggregateNoValue + raw resolver in cmp/arith paths + `_eval_body` extension(if needed) | ~250 |
| `application/protocol/rule.py` _serialize_term + _collect_term_vars branches + helper | ~50 |
| Tests | ~700 |
| **Total** | **~1280 LOC** |

**Still over S-class ~300 LOC guideline by 4x**,but:

- **Public API impact:None**(no SDK helpers — explicit T2.3b deferral)— now genuinely true unlike v0 draft。
- **No load-bearing decision**(parent essay locks C99-C105)。
- **No public API rename / replacement**。
- **Pure additive net-new substrate**。
- **Coherent single-purpose slice**:if further split,would fragment the IR + validation + per-env eval + resolver coupling that must land together for correctness。

**S-class with documented size override**。Reviewer may further P-find a split into T2.3a.1(IR + validation,~280 LOC)+ T2.3a.2(Python eval + raw resolver,~350 LOC)+ T2.3a.3(application Rule serialization + tests integration)。Drafter's view:these are not independently shippable — IR without evaluator is dead substrate;evaluator without IR can't construct;application Rule serialization without validator can't accept。Tests span all。Coherence > size。

## 6. Boundaries And Invariants

- **Substrate-only invariant**:T2.3a ships core IR + validation + Python eval + raw resolver in cmp/arith paths + application Rule serialization branches。**No SDK ergonomic helpers,no DSL `_AggregateRef` type,no bridge ergonomic,no public docs update**(all T2.3b)。
- **AggregateExpr-as-Term invariant**:`AggregateAtom` is `CmpAtom.lhs`/`.rhs` Term value,**never** top-level `Rule.where` Atom。T1.1 `_ALLOWED_ATOM_TYPES` unchanged。
- **Semantic-lock invariant**:C99-C105 semantics fully translate from parent essay §10.6.3-§10.6.9 without modification or relaxation。
- **Per-env aggregation invariant**:aggregate computation runs **per outer env**(correlated semantics per C104),NEVER as a global env-list reduce。
- **NoValue isolation invariant**:`AggregateNoValue` propagation NEVER raises Python exception。NoValue causes atom violation(env excluded from output)or result binding rejection per parent §10.6.5 / C101 / C105。
- **NoValue × ArithExpr invariant**:NoValue as ArithExpr operand causes the arithmetic atom to be violated for that env(not a process exception)。Implemented in raw resolver invocation from `_eval_arith_atom` operand resolution。
- **Filter-local var isolation invariant**(defense-in-depth per v3):aggregate-local-only Vars(introduced + bound inside aggregate filter,not in outer scope,not in target)do NOT leak to outer Rule.where atoms or ports。**Application Rule independently enforces this in its own two-pass collection algorithm**(`Rule.__post_init__` Pass 1 treats AggregateAtom as opaque;Pass 2 collects target_vars + correlated_filter_vars only)。AST validator(`where_ast_validate._validate_aggregate_scoping`)additionally rejects aggregate-local Vars referenced by subsequent outer atoms at construct-time。**Application Rule's defense does NOT rely on validator pre-check** — it is independently correct even when validator is bypassed(e.g., direct AggregateAtom instantiation that skips `parse_where_ir_to_ast`)。
- **Filter-only-9-kinds invariant**:filter clause top-level atoms restricted to 9 scalar kinds(pred / eq / ne / gt / ge / lt / le / in / not);`not` body further restricted to 8 kinds(去 nested not)。
- **Raw-tuple-evaluator invariant**:T2.3a evaluator extensions operate on raw tuple shapes,not AST dataclass instances(per Step 4.2 v1 P2)。AST is parsed only for validation gating in `evaluate_where`。
- **Adapter-deferral invariant**:adapter wires(Souffle / ProbLog)stay 0 LOC change in T2.3a — verified by scope diff。Deferred to T2.3.c / T2.3.d。
- **SDK-deferral invariant**:no SDK helpers,no DSL `_AggregateRef`,no `sdk/dsl/expr.py` change — deferred to T2.3b。Verified by scope diff。
- **Cross-slice contract invariant**:
  - T1.1 application Rule `_ALLOWED_ATOM_TYPES` unchanged(AggregateAtom is Term-position,not top-level Atom)。
  - **T1.2 SDK bridge intentionally UNTOUCHED in T2.3a**(`sdk/dsl/expr.py` + `sdk/dsl/application_rule.py` 0-touch);aggregate-containing IR is **unsupported via `build_application_rule` in T2.3a**(`_collect_vars_from_term` `:181` + var canonicalize `:250` don't recognize AggregateAtom)。Aggregate bridge support is **deferred to T2.3b**。Application Rule internal helpers(`_serialize_term` / `_collect_term_vars` in `application/protocol/rule.py`)gain AggregateAtom branch ONLY for **direct application Rule construction** path(per §5.7)。
  - T2.1 ne adapter dispatch unchanged。
  - T2.2 ArithExpr `_BUILTIN_TAGS` unchanged;`_eval_arith_atom` operand resolver gains aggregate-aware branch(per v1 P4)— additive,not breaking。

## 7. Acceptance

- [ ] G1/G4 traceability:every §2 goal cites C99-C105。
- [ ] G7 pre-impl precondition runs and is recorded in audit log **before** code implementation。
- [ ] G7 #5 ambiguity check:if C99-C105 semantic ambiguity surfaces during precondition → escalate S → M with decision doc and pause impl。
- [ ] `where_ast.py` adds `AggregateAtom` type + `_AGGREGATE_KINDS` constant + parse / lower / Term restructure。
- [ ] `where_ast.py` Term TypeAlias extended to include `AggregateAtom`(Strategy A restructure)。
- [ ] `where_ast_validate.py` enforces filter clause flat list + 9-kind allowlist + `not` body recursion limit + variable scoping + construct-time numeric target type with `AggregateValidationError` / `AggregateVariableScopeError`。
- [ ] `where_eval.py` evaluates 5 aggregate kinds **per-env**(verify two outer envs get different aggregate results per C104 correlated)+ `AggregateNoValue` sentinel + empty set behavior + runtime numeric target check + result binding 3-branch logic。
- [ ] `where_eval.py` raw aggregate term resolver invoked from cmp / arith paths;NoValue × ArithExpr propagation via raw resolver(test:`agg_sum(empty) + 1 > 5` → atom violated for that env)。
- [ ] `application/protocol/rule.py` `_serialize_term` and `_collect_term_vars` recognize `AggregateAtom`(content_digest determinism + filter-local var isolation)。
- [ ] T1.1 `application/protocol/rule.py:_ALLOWED_ATOM_TYPES` unchanged(verified by scope diff)。
- [ ] `sdk/dsl/expr.py` unchanged(verified by scope diff;no agg_count helper landed here)。
- [ ] `sdk/dsl/application_rule.py` unchanged(verified by scope diff;no DSL_AggregateRef lowering)。
- [ ] Tests:`tests/core/rules/test_aggregate_substrate.py` + `tests/core/rules/test_aggregate_eval.py` + `tests/application/protocol/test_rule_aggregate.py` all pass。
- [ ] **Per-env correlated test**:two outer envs (e.g., user u-1 + 3 orders / user u-2 + 5 orders) produce count=3 / count=5 respectively;NOT a merged count=8。
- [ ] **NoValue × ArithExpr test**:`agg_sum(empty_set) + 1 > 5` → atom violated for the env that hit empty;Python exception NOT raised。
- [ ] **Filter-local var isolation test**:validator raises `AggregateVariableScopeError` when filter introduces var that subsequent outer atom references。
- [ ] **Application Rule filter-local var isolation test**(per Step 4.2 v2 P1):construct Rule with `ports={"u": aggregate_local_var}` → reject;ports can only reference outer or aggregate-correlated/target vars,never aggregate-local-only。
- [ ] **Target-only outer Var ports reference test**(per Step 4.2 v3 P1):construct Rule where target Var `$amount` only appears in aggregate target(not in other outer atoms),AND $amount is outer-bound per P2 §2.5b → ports `{"amount": $amount}` is **valid**(target Vars are always collected into seen_vars per v3 P1 algorithm)。Validator additionally enforces binding-order requirement at AST layer。
- [ ] **Target Var binding rule test**(per Step 4.2 v2 P2):`agg_sum(target=Var("$unbound_amount"), filter=[PredAtom("Order:exists", ...)])` where target Var is bound neither outer nor in filter → reject with `AggregateVariableScopeError`。
- [ ] **All where_eval.py aggregate-aware helpers covered**(per Step 4.2 v2 P3):tests verify `_validate_atom` / `_term_known_for_plan` / `_atom_eval_score` / `_vars_in_atoms` produce correct behavior on aggregate-containing atoms。
- [ ] Cross-slice non-regression:T1.1 + T1.2 + T2.1 + ProbLog hygiene + T2.2 + fixture cleanup tests all pass(70+ tests baseline)。
- [ ] Ruff clean on all touched source + test files。
- [ ] No Souffle / ProbLog / PyReason adapter files changed(scope diff)。
- [ ] No SDK files changed(scope diff:`sdk/dsl/expr.py` / `sdk/dsl/application_rule.py` / `sdk/__init__.py` 0 lines)。
- [ ] `build_application_rule(...)` aggregate path **NOT tested as supported**(per Step 4.2 v2 P4)— T2.3a only tests **direct application Rule construction** with aggregate Term-position;bridge ergonomic path defers to T2.3b。
- [ ] Sacred `master 562c7419` unchanged。
- [ ] Dirty 4 M + 1 untracked preserved。

## 8. Implementation Plan

1. **G7 pre-impl precondition**:run §5.8 checks 1-5;record in audit log **before** impl commit。If check #1-4 fail → amend blueprint。If check #5 surfaces ambiguity → escalate to M with decision doc。
2. **IR layer**:add `AggregateAtom` to `where_ast.py` + Term restructure(Strategy A)+ `_AGGREGATE_KINDS` + parse / lower branches。
3. **Validation layer**:add aggregate validators to `where_ast_validate.py`(filter restrictions + scoping + numeric construct + `not` body recursion + error classes)。
4. **Evaluator layer**:add `_AggregateNoValueSentinel` + `_is_aggregate_term` + `_resolve_aggregate_term_for_env`(per-env)+ extend `_eval_cmp_atom` and `_eval_arith_atom` operand resolution to invoke aggregate resolver。Verify `_eval_body` accepts `initial_envs` or extend it。
5. **Application Rule serialization**:extend `_serialize_term` + `_collect_term_vars` + helper for filter-local var handling。
6. **Tests**:add 3 test files per §5.9 — including per-env correlated test + NoValue × ArithExpr test + filter-local var isolation test。
7. **Run gates**:
   - `PYTHONPATH=src python -m unittest tests.core.rules.test_aggregate_substrate tests.core.rules.test_aggregate_eval tests.application.protocol.test_rule_aggregate`
   - Cross-slice non-regression
   - `python -m ruff check ...`
8. **Fill §10 Outcome** with exact LOC,test outcomes,deviations,T2.3b follow-up sketch。

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md` — add **internal note** about AggregateAtom Term-position semantics + filter-local var validator dependency。User-facing aggregate syntax docs deferred to T2.3b。
- No SDK docs change(SDK 0-touch in T2.3a)。
- Track plan §1.2.5 retroactive labeling table — add T2.3a row after archive(via memory consolidation slice or batch labelling)。

## 10. Outcome / Deviations

- **Implemented in** `b94576f5` (`feat(rules): add AggregateExpr substrate`) after G7 precondition record `f3d217a3`。
- **Landed code**:
  - `src/factgraph/core/rules/where_ast.py`: `AggregateAtom`, `_AGGREGATE_KINDS`, raw parse/lower, and `Term = Var | Const | AggregateAtom` restructure.
  - `src/factgraph/core/rules/where_ast_validate.py`: aggregate validation, filter restrictions, scoping, target binding rule, numeric construct checks, `AggregateValidationError`, and `AggregateVariableScopeError`.
  - `src/factgraph/core/rules/where_eval.py`: per-env aggregate evaluation, `AggregateNoValue`, raw aggregate resolver in comparison/arithmetic paths, and aggregate-aware helper coverage.
  - `src/factgraph/application/protocol/rule.py`: direct-construction aggregate term serialization and two-pass port visibility (target vars always; correlated filter vars only; aggregate-local-only vars isolated).
  - `src/factgraph/application/docs/rule.md`: internal substrate note; no SDK/public aggregate syntax docs.
  - Tests: `tests/core/rules/test_aggregate_substrate.py`, `tests/core/rules/test_aggregate_eval.py`, `tests/application/protocol/test_rule_aggregate.py`.
- **Verification**:
  - G7 precondition checks 1-5 passed and were recorded before implementation in `f3d217a3`; no S→M escalation or decision doc was needed.
  - T2.3a + cross-slice gate: `PYTHONPATH=src python -m unittest tests.core.rules.test_aggregate_substrate tests.core.rules.test_aggregate_eval tests.application.protocol.test_rule_aggregate tests.application.protocol.test_rule tests.sdk.dsl.test_application_rule tests.test_souffle_witness_where_compile_v1 tests.test_problog_export tests.test_problog_engine_eval tests.test_capability_helpers_round_events` → 85 tests passed.
  - Ruff clean on touched source/test files.
  - Scope diff verified SDK files and adapter files 0-touch.
  - Sacred `master` stayed at `562c74195df43e933bed92a3ff25de94dd8ce666`; unrelated dirty set preserved.
- **Deviations**:
  - None from the scoped T2.3a blueprint. `_eval_body(initial_envs=...)` was an expected implementation extension from G7 check #3, not a scope change.
  - No unrelated baseline drift surfaced.
- **Follow-up**:
  - T2.3b: SDK ergonomic helpers + aggregate bridge support + public docs/export policy.
  - T2.3c/d: Souffle aggregate body wire and ProbLog `findall` / list-predicate adapter dispatch.
  - Track plan / memory consolidation should add T2.3a after archive.
