# T2.3c — Aggregate Souffle adapter wire over T2.3a substrate + T2.3b SDK

- Status: draft
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: task blueprint
- Inputs:
  - Parent essay [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md) §10.6.3 (C99) — 5 aggregate kinds + IR shape;§10.6.4 (C100) — filter restrictions;§10.6.5 (C101) — empty set + `AggregateNoValue`;§10.6.7 (C103) — snapshot semantics;§10.6.8 (C104) — variable scoping;§8.8 — per-engine aggregate lowering策略
  - Track plan [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md) §1.2 G1-G7,§1.2.6 T2.3c row(S — Souffle aggregate body wire,independent from T2.3d ProbLog)
  - Archived T2.3a [2026-05-23_t2-3-aggregate-substrate.md](../archive/2026-05-23_t2-3-aggregate-substrate.md) — substrate IR `AggregateAtom` + `_AGGREGATE_KINDS` + validator + Python eval + application Rule serialization + two-pass var collection。**T2.3a substrate is the foundation T2.3c builds on**
  - Archived T2.3b [2026-05-23_t2-3b-aggregate-sdk-bridge.md](../archive/2026-05-23_t2-3b-aggregate-sdk-bridge.md) — SDK ergonomic + bridge produces aggregate IR(`("eq", lhs, ("sum", target_var, filter_atoms))`shape)consumed by Souffle adapter from this slice forward
  - Archived T2.1 [2026-05-23_t2-1-ne-adapter-dispatch.md](../archive/2026-05-23_t2-1-ne-adapter-dispatch.md) — Souffle raw tuple `ne` dispatch precedent for adapter-only slices
  - Archived T2.2 [2026-05-23_t2-2-arith-expr.md](../archive/2026-05-23_t2-2-arith-expr.md) — adapter-side existing-builtin export pattern;arith atom compile precedent
- Outputs / Downstream:
  - `_compile_atom` dispatch extension recognizing aggregate-tuple in cmp atom LHS/RHS
  - `_compile_aggregate` helper lowering `(kind, target_var, filter_atoms)` to Souffle aggregate body DL syntax
  - `_compile_cmp_side` extension handling aggregate operand
  - `_vars_in_atom` aggregate-aware extension(correlated outer vars only;aggregate-local vars stay private per C104)
  - `_validate_atom_subset` aggregate shape validation extension
  - Test coverage:per-kind compile + correlation pass-through + aggregate-local isolation + empty set + validation rejection
  - Adapter status docs:`application/docs/rule.md` adapter status table flip(Souffle pending → Souffle ✓)
- Related:
  - `src/factgraph/adapters/souffle/where_compile.py`(extended)
  - `src/factgraph/core/rules/where_ast.py`(consumed unchanged — `_AGGREGATE_KINDS` source)
  - `src/factgraph/core/rules/where_ast_validate.py`(consumed unchanged — substrate validator runs upstream)
  - `src/factgraph/core/rules/where_eval.py`(consumed unchanged — Python eval path remains separate)
  - `src/factgraph/sdk/dsl/expr.py`(consumed unchanged — lowering produces aggregate IR)
  - `src/factgraph/sdk/dsl/application_rule.py`(consumed unchanged — bridge validator gate enforces shape before Souffle receives)
- Related Modules:
  - `src/factgraph/adapters/souffle/where_compile.py` — extends `_compile_atom` cmp dispatch + `_compile_cmp_side` + new `_compile_aggregate` helper + `_vars_in_atom` aggregate branch + `_validate_atom_subset` aggregate kinds + `_AGGREGATE_KINDS` import or local constant。
  - `src/factgraph/application/docs/rule.md` — flip adapter status table row "Souffle aggregate dispatch pending T2.3.c" → "Souffle aggregate dispatch ✓"。
- Audit Log:
  - [2026-05-23_t2-3c-aggregate-souffle-wire.audit.md](./2026-05-23_t2-3c-aggregate-souffle-wire.audit.md)
- Branch: `v0.2.0-blueprint-t2-3c-aggregate-souffle-wire-2026-05-23`

> **Cross-slice relationship**:T2.3a shipped(`477fcccb`)the **core substrate**(IR + validation + Python eval + application Rule serialization)。T2.3b shipped(`4e3176d2`)the **SDK ergonomic + bridge**(5 `agg_*` helpers + `_AggregateRef` + DSL→IR lowering + bridge validator gate)。Both deferred Souffle adapter aggregate dispatch to **T2.3c**(this slice)and ProbLog adapter dispatch to **T2.3.d**。T2.3c closes the Souffle path WITHOUT touching T2.3a substrate / T2.3b SDK / T2.3.d ProbLog / PyReason。

## 1. Problem

Parent essay §10.6.3 (C99) defines 5 aggregate kinds(`count` / `sum` / `min` / `max` / `mean`)as value-producing expressions that appear inside comparison atoms(eq / ne / gt / ge / lt / le)。Parent essay §8.8 + §1718 promises Souffle adapter wires native `count` / `sum` / `min` / `max` / `mean` aggregate body lowering with **filter clause embedding**(~150 lines)。

**Current state**(verified 2026-05-23 by G2 source-grep on `src/factgraph/adapters/souffle/`):

- `rg "AggregateAtom|_AGGREGATE_KINDS|aggregate" src/factgraph/adapters/souffle/` returns **0 hits**。Souffle adapter has zero aggregate handling。
- `where_compile.py:434` `_compile_atom` dispatch only recognizes 9 atom kinds(`pred` / `eq` / `ne` / `in` / `gt`/`ge`/`lt`/`le` / `_ARITH_KINDS` / `not`)。An aggregate-shaped cmp atom RHS/LHS triggers the line 626 fallback `WhereValidationError(f"unsupported atom kind: {kind}")`if the tuple's first element isn't a recognized kind。
- `where_compile.py:905` `_compile_cmp_side` only handles `_is_var(term)`(emits `to_number(v_<name>)`)or literal(emits via `_literal_to_cmp_int_text`)。Aggregate tuple operand not handled。
- `where_compile.py:1139` `_vars_in_atom` only extracts vars from 8 known kinds + arith。Aggregate not handled。
- `where_compile.py:679` `_validate_atom_subset` rejects aggregate kinds via fallback at line 731。

**T2.3a substrate**(`477fcccb`)is the upstream truth:`AggregateAtom` IR + `_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}` + per-env Python evaluator + filter restriction validator + application Rule serialization。**T2.3b SDK**(`4e3176d2`)produces aggregate-shaped IR via the bridge `build_application_rule(...)` path:

```python
# Bridge output IR shape (from T2.3b lowering):
("eq", "$total", ("sum", "$_agg1", [
    ("pred", "User:exists", ["$u"]),
    ("pred", "Order:exists", ["$o"]),
    ("pred", "order:buyer", ["$o", "$u"]),
    ("pred", "order:amount", ["$o", "$_agg1"]),
]))
```

The aggregate tuple `("sum", "$_agg1", [...filter...])` appears as cmp atom RHS(or LHS for symmetric cases)。Souffle adapter from T2.3c forward must recognize this shape and emit Souffle DL like:

```souffle
v_total = to_string(sum to_number(v__agg1) : { User_exists(v_u), Order_exists(v_o), order_buyer(v_o, v_u), order_amount(v_o, v__agg1) })
```

(precise Souffle DL syntax locked in §5.3 per Souffle 2.x aggregator language reference;`to_string(...)` wraps the numeric aggregate output for symbol-typed `v_total` binding consistent with `_compile_arith_atom` precedent at line 1103)。

**T2.3c scope:adapter wire only**。No SDK / substrate / ProbLog / PyReason touch。

## 2. Goals

### 2.1 C99 — Add `_AGGREGATE_KINDS` visibility in Souffle adapter

Import `_AGGREGATE_KINDS` from `factgraph.core.rules.where_ast`(preferred — single source of truth)OR define a private adapter-local constant mirroring the substrate set(decision in §5.1 — defaults to import per single-source-of-truth)。

### 2.2 C99 — Extend `_compile_atom` cmp dispatch for aggregate-RHS/LHS

In the `kind in {"eq", "ne", "gt", "ge", "lt", "le"}` branches of `_compile_atom`,detect when `lhs` or `rhs` is an aggregate tuple(`isinstance(side, tuple) and side[0] in _AGGREGATE_KINDS`)and route to `_compile_aggregate` for that side's compile。

### 2.3 C99 — Add `_compile_aggregate` helper

New helper `_compile_aggregate(aggregate, var_symbols, outer_bound_vars, pred_arities, pred_type_domains, in_rel_values, ast_gate_on)` lowers `(kind, target_var, filter_atoms)` to Souffle aggregate body DL:

```
<kind> [<target_term>] : { <filter_body> }
```

where:
- `<kind>` ∈ {count, sum, min, max, mean}
- `<target_term>` is `to_number(v_<target_var>)` for numeric aggregates(sum/min/max/mean);**absent** for count
- `<filter_body>` is comma-separated Souffle DL of compiled filter atoms

### 2.4 C100 + C104 — Filter atom recursive compile with scope isolation

Filter atoms compile via the same `_compile_atom` machinery but with a **scoped bound-var set**:

- Outer `bound_vars` accessible as **correlated outer vars**(read-only)
- Aggregate-local new vars(introduced inside filter)bind to a **local copy** of `bound_vars` that does NOT leak back to outer
- Per C100,filter atom kinds restricted to pred / eq / ne / gt / ge / lt / le / in / **not**(no Rule reference / no RuleExpr / no nested aggregate / no ArithExpr — but T2.3a substrate validator upstream already rejects these,so Souffle adapter trusts the IR shape)

### 2.5 C101 — Empty set + `AggregateNoValue` Souffle representation

Souffle's native aggregators return:
- `count` over empty body → `0`(matches C101 expected value)
- `sum` over empty body → `0`(matches C101 expected value)
- `min` / `max` / `mean` over empty body → **Souffle warning + 0**(does NOT match C101 `AggregateNoValue` semantics)

**Resolution**:Souffle compile output emits the aggregate as-is(empty min/max/mean returns 0 in Souffle);**runtime semantic gap** is documented as a known deviation in §10.4 follow-up。T2.3c does NOT introduce sentinel handling at Souffle DL layer;upstream `AggregateNoValue` semantics are honored by the Python evaluator path,not the Souffle path。This matches parent essay §8.9 "Aggregate Empty Set Behavior Convergence" expected deferral。

### 2.6 Var extraction — `_vars_in_atom` aggregate-aware

Extend `_vars_in_atom` to walk aggregate tuples:
- For `kind in _AGGREGATE_KINDS` directly(if aggregate ever surfaces as a standalone — not expected in valid IR but defensive)
- For cmp atoms containing aggregate-tuple sides:`_vars_in_atom` of cmp recurses into the aggregate's filter atoms via `_vars_in_atom` to **collect correlated outer vars** referenced inside filter

Per C104:**only outer-correlated vars** flow to outer `vars_in_atom` result;**aggregate-local vars** stay local。Algorithm:

```python
def _aggregate_outer_vars(aggregate_tuple, outer_var_universe):
    # outer_var_universe is the set of vars known at the enclosing scope
    # aggregate-local vars are introduced inside filter and excluded
    local_vars = set()
    referenced_vars = set()
    for filter_atom in aggregate_tuple[2]:
        for var in _vars_in_atom(filter_atom, include_not_body_vars=True):
            referenced_vars.add(var)
        # find which vars this atom introduces (binds) — must subtract from outer
        # simplification: rely on the universe set — anything in referenced_vars
        # that is in outer_var_universe is a correlated outer var
    return referenced_vars & outer_var_universe
```

(Precise impl in §5.5;simplification:rely on caller's outer_var_universe knowledge instead of re-deriving binding order inside aggregate)

### 2.7 Validation — `_validate_atom_subset` aggregate shape

In `_validate_atom_subset` cmp branch(`kind in {"eq", "ne", "gt", "ge", "lt", "le"}`),allow aggregate-tuple operand。Aggregate-tuple shape validation:

- `isinstance(aggregate, tuple) and len(aggregate) == 3`
- `aggregate[0] in _AGGREGATE_KINDS`
- `aggregate[1]` is either `None`(count) OR a `$`-prefixed var string(numeric aggregates)
- `aggregate[2]` is a list of valid filter atoms(each recursively validates via `_validate_atom_subset`)

Note:T2.3a upstream validator `validate_where_ast` already enforces filter restrictions(C100)at the substrate layer。Souffle adapter validator only checks **shape**(tuple structure),trusting upstream for **semantic** restrictions。This is defense-in-depth without re-implementing T2.3a substrate logic。

### 2.8 Tests — acceptance suite with discriminator design

Per T2.3b cross-flip inversion lesson(reviewer must verify each acceptance test discriminates the intended algorithm branch),acceptance includes 11 tests targeting specific algorithm decisions:

1. Each of 5 aggregate kinds compiles to correct Souffle DL syntax(5 tests — one per kind discriminator)
2. Aggregate in eq RHS binds outer var
3. Aggregate in gt cmp(no binding,just filter)
4. Correlated outer var referenced in filter — passes through to outer scope
5. Aggregate-local var introduced in filter — does NOT leak to outer scope(discriminator for C104 isolation)
6. Filter with `not` body — compiles correctly nested inside aggregate body
7. Validation rejects malformed aggregate shape

Detailed in §7。

### 2.9 G7 pre-impl precondition checks

Recorded BEFORE implementation per T2.2/T2.3a/T2.3b discipline。Detailed in §5.6。

## 3. Non-goals

- **T2.3.d ProbLog aggregate wire** — separate slice;ProbLog uses `findall/3` + list predicates,fundamentally different lowering algorithm
- **PyReason aggregate** — out of scope(parent essay §10.6.3 line 1711 marks N/A;PyReason is Form 2 only)
- **T2.3a substrate changes** — IR / validator / Python eval / application Rule all consumed unchanged
- **T2.3b SDK changes** — `_AggregateRef` / 5 helpers / lowering / bridge validator gate all consumed unchanged
- **Aggregate-in-arith-atom** — deferred Nit from T2.3b(`_lower_compare_with_aggregate` non-aggregate side limitation);T2.3.b1/T2.3.e candidate
- **Nested aggregate** — T2.3a validator rejects upstream;Souffle adapter trusts upstream
- **New aggregate kinds beyond 5** — locked at parent essay C99
- **New filter atom kinds beyond C100** — pred / eq / ne / gt / ge / lt / le / in / not list locked
- **Witness layout for aggregate result** — aggregates produce derived numeric values;no rule occurrence witness
- **Souffle `mean` derived fallback** — assumes native Souffle 2.x `mean` aggregator support;if impl reveals unsupported,(A-fallback) deviation per CADENCE
- **AggregateNoValue Souffle DL sentinel** — Souffle's native empty-set behavior(min/max/mean → 0)deviates from C101 `AggregateNoValue`;documented as known semantic gap,not addressed at Souffle DL layer(see §2.5 + §10.4 follow-up)
- **Witness extension for aggregate result vars** — `pred_witness_symbols` / `WitnessLayout` unchanged(witnesses are for matched fact rows,not aggregate-derived numbers)
- **M-class decision doc** — no public-API rename / no cross-engine semantic decision / no load-bearing Q;S-class trigger analysis in §5.7 confirms

## 4. Current Context

### 4.1 G2 source-grep audit

Verified 2026-05-23 on local branch `v0.2.0-blueprint-t2-3c-aggregate-souffle-wire-2026-05-23 @ 1666ffd3`(branched from `1666ffd3` repo memory sync covering T2.3b archive)。

| Search | Result | Implication |
|---|---|---|
| `rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate" src/factgraph/adapters/souffle/` | 0 hits | Souffle adapter has zero aggregate handling(G7 precondition #1 met) |
| `where_ast.py:75` `class AggregateAtom` | Present(T2.3a) | Substrate IR landed |
| `where_ast.py:102` `_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}` | Present(T2.3a) | Importable single source of truth |
| `where_ast_validate.py` `validate_where_ast(...)` with aggregate filter restriction(C100) | Present(T2.3a) | Substrate validator runs upstream of Souffle adapter |
| `sdk/dsl/expr.py:209` `class _AggregateRef` + helpers | Present(T2.3b) | SDK lowering produces aggregate IR for Souffle to consume |
| `sdk/dsl/application_rule.py` `validate_where_ast(..., initial_bound_vars=...)` gate | Present(T2.3b) | Bridge validator gate enforces aggregate IR shape before Souffle receives |
| `rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate" src/factgraph/adapters/problog/` | (expected 0;will verify at G7) | T2.3.d boundary intact |
| `rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate" src/factgraph/adapters/pyreason/` | (expected 0;will verify at G7) | PyReason out-of-scope intact |

### 4.2 G3 file:line citations of touch points

- `src/factgraph/adapters/souffle/where_compile.py:20` `_ARITH_KINDS = {"add", "sub", "neg", "addc", "mulc"}` — module-level constant pattern;T2.3c adds `_AGGREGATE_KINDS` import OR mirrors locally
- `src/factgraph/adapters/souffle/where_compile.py:434-626` `_compile_atom(...)` — dispatch; aggregate-RHS/LHS handling enters via `eq` / `ne` / `gt`/`ge`/`lt`/`le` branches
- `src/factgraph/adapters/souffle/where_compile.py:506-512` `kind == "ne"` route — T2.1 precedent for cmp-style filter dispatch
- `src/factgraph/adapters/souffle/where_compile.py:561-567` `kind in _ARITH_KINDS` route — T2.2 precedent for value-producing expression dispatch
- `src/factgraph/adapters/souffle/where_compile.py:679-731` `_validate_atom_subset(...)` — atom shape validation;T2.3c extends to recognize aggregate operand inside cmp
- `src/factgraph/adapters/souffle/where_compile.py:905-908` `_compile_cmp_side(...)` — currently handles var(via `to_number(...)`)+ literal;T2.3c extends to handle aggregate-tuple
- `src/factgraph/adapters/souffle/where_compile.py:1060-1103` `_compile_arith_atom(...)` — value-producing arith pattern;reference precedent for `to_string(...)` binding cast
- `src/factgraph/adapters/souffle/where_compile.py:1139-1173` `_vars_in_atom(...)` — var extraction;T2.3c extends to walk aggregate filter atoms(correlated outer vars only)
- `src/factgraph/adapters/souffle/where_compile.py:1176` `_symbol_for_var(...)` — symbol mapping helper(reused)

### 4.3 Souffle native aggregator syntax(Souffle 2.x language reference)

Souffle native aggregators(verified per Souffle 2.x documentation):

| Aggregator | Syntax | Empty set result |
|---|---|---|
| `count` | `count : { body }` | `0` |
| `sum` | `sum X : { body }` where X is numeric expression | `0` |
| `min` | `min X : { body }` where X is comparable | warning,returns `0`(numeric)/ empty string(symbolic) |
| `max` | `max X : { body }` where X is comparable | warning,returns `0` / empty string |
| `mean` | `mean X : { body }` where X is numeric | warning,returns `0` |

Body is comma-separated atoms.Inner vars are aggregate-local;outer-referenced vars are correlated。

## 5. Proposed Shape

### 5.1 `_AGGREGATE_KINDS` source decision

**Decision**:import from substrate single source of truth。

```python
from factgraph.core.rules.where_ast import _AGGREGATE_KINDS
```

Rationale:single source of truth;avoid drift if substrate adds future kinds(though parent essay locks at 5)。Underscore-prefix `_AGGREGATE_KINDS` is internal,but cross-module import within `factgraph` package is acceptable(same package family,not external API)。If linting flags the underscore import,fallback to defining adapter-local mirror constant with an explicit comment pointing to substrate `_AGGREGATE_KINDS` and an invariant check that the two sets match at import time。

### 5.2 `_compile_atom` cmp dispatch extension

In the `kind in {"eq", "gt", "ge", "lt", "le"}` branches(and `"ne"` route via `_compile_ne_filter`),detect aggregate operand:

```python
def _is_aggregate(term: Any) -> bool:
    return (
        isinstance(term, tuple)
        and len(term) >= 1
        and isinstance(term[0], str)
        and term[0] in _AGGREGATE_KINDS
    )
```

Branch behavior:
- `eq` with aggregate RHS:bind LHS var to aggregate result(via `to_string(...)` wrap)
- `eq` with aggregate LHS:symmetric(bind RHS var)
- `gt`/`ge`/`lt`/`le` with aggregate side:emit `<aggregate-body> <op> <other-side>` filter
- `ne` with aggregate side:T2.3c follows T2.1 `_compile_ne_filter` precedent extended for aggregate operand;`!=` filter

### 5.3 `_compile_aggregate` helper

```python
def _compile_aggregate(
    *,
    aggregate: tuple[Any, ...],
    var_symbols: dict[str, str],
    outer_bound_vars: set[str],
    pred_arities: dict[str, int],
    pred_type_domains: dict[str, list[str]],
    var_type_domains: dict[str, set[str]],
    in_rel_values: dict[str, tuple[str, ...]],
    ast_gate_on: bool,
) -> str:
    kind, target_var, filter_atoms = aggregate
    # Local scope for aggregate body: outer vars accessible read-only,
    # aggregate-local vars introduced in filter do NOT escape
    local_bound_vars = set(outer_bound_vars)
    body_terms: list[str] = []
    for filter_atom in filter_atoms:
        # Recurse via _compile_atom with local_bound_vars;
        # filter atoms bind into local_bound_vars only
        body_terms.append(
            _compile_filter_atom_within_aggregate(
                atom=filter_atom,
                var_symbols=var_symbols,
                local_bound_vars=local_bound_vars,
                pred_arities=pred_arities,
                pred_type_domains=pred_type_domains,
                var_type_domains=var_type_domains,
                in_rel_values=in_rel_values,
                ast_gate_on=ast_gate_on,
            )
        )
    body = ", ".join(body_terms)
    if kind == "count":
        return f"count : {{ {body} }}"
    # sum / min / max / mean
    target_sym = _symbol_for_var(var_symbols, target_var)
    target_expr = f"to_number({target_sym})"
    return f"{kind} {target_expr} : {{ {body} }}"
```

**Filter atom compile within aggregate** uses a separate function `_compile_filter_atom_within_aggregate` that mirrors `_compile_atom` but:
- Operates on local_bound_vars(scope isolation)
- Rejects filter-kind atoms outside C100 list(though T2.3a upstream already rejects)
- Does NOT emit witness symbols for filter pred atoms(aggregate body has no rule-level witness)
- Returns DL text comma-separated

Alternative:if reusing `_compile_atom` directly is cleaner with a `within_aggregate=True` flag,acceptable per impl choice。Impl may pick the cleaner factoring。

### 5.4 `_compile_cmp_side` extension

```python
def _compile_cmp_side(
    term: Any,
    var_symbols: dict[str, str],
    kind: str,
    *,
    aggregate_compile_context: dict[str, Any] | None = None,
) -> str:
    if _is_aggregate(term):
        if aggregate_compile_context is None:
            raise WhereValidationError(f"{kind} aggregate operand requires compile context")
        return _compile_aggregate(aggregate=term, **aggregate_compile_context)
    if _is_var(term):
        return f"to_number({_symbol_for_var(var_symbols, term)})"
    return _literal_to_cmp_int_text(term, kind)
```

Context kwarg threads through aggregate body compile dependencies(var_symbols,bound_vars,pred_arities,etc.)。`_compile_atom` cmp branches pass an `aggregate_compile_context` dict when calling `_compile_cmp_side`。

### 5.5 `_vars_in_atom` aggregate-aware extension

```python
def _vars_in_atom(atom: tuple[Any, ...], *, include_not_body_vars: bool) -> list[str]:
    kind = atom[0]
    found: set[str] = set()
    # ... existing kinds ...
    elif kind in {"eq", "ne", "gt", "ge", "lt", "le"}:
        _, lhs, rhs = atom
        for side in (lhs, rhs):
            if _is_var(side):
                found.add(side)
            elif _is_aggregate(side):
                # walk aggregate filter atoms; aggregate result var (target_var)
                # is aggregate-local — exclude.
                # filter vars include both correlated outer (return) and
                # aggregate-local (exclude). Discrimination:
                # - vars introduced by filter atoms (typically via predicate
                #   first occurrence) → local
                # - vars referenced by filter atoms that also appear in
                #   outer scope → correlated outer (return)
                # T2.3c simplification: return ALL vars referenced in filter;
                # caller (extract_where_variables) filters against outer scope
                # via subset intersection.
                kind_inner, target_var_inner, filter_atoms = side
                for filter_atom in filter_atoms:
                    for var in _vars_in_atom(filter_atom, include_not_body_vars=True):
                        found.add(var)
                # explicitly exclude target_var (aggregate-local result binding)
                if isinstance(target_var_inner, str) and target_var_inner.startswith("$"):
                    found.discard(target_var_inner)
    # ... rest of existing kinds ...
    return sorted(found)
```

**Simplification rationale**:`_vars_in_atom` returns ALL referenced vars(except target_var which is provably aggregate-local)。Upstream consumer `extract_where_variables(where)` already does scope analysis at the where-level;intersecting with outer-scope known vars filters aggregate-local introductions。This avoids re-implementing binding-order analysis in the var-extraction helper。

### 5.6 G7 pre-implementation preconditions

Recorded BEFORE implementation per established discipline。To be verified on impl branch fork:

1. **T2.3a substrate present**:`AggregateAtom` at `where_ast.py:75` + `_AGGREGATE_KINDS` at `where_ast.py:102` + `validate_where_ast(...)` with aggregate filter restriction(C100)at `where_ast_validate.py`。
2. **T2.3b SDK lowering present**:`_AggregateRef` at `sdk/dsl/expr.py:209` + `_lower_compare_with_aggregate` at `:459` produces aggregate IR of shape `("eq", lhs, ("sum", target_var, filter_atoms))`(verified via T2.3b acceptance tests)。
3. **Souffle aggregate dispatch empty**(this slice's add point):`rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate" src/factgraph/adapters/souffle/` returns 0 hits。
4. **ProbLog aggregate dispatch empty**(T2.3.d boundary intact):`rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate" src/factgraph/adapters/problog/` returns 0 hits。
5. **PyReason aggregate dispatch empty**(out-of-scope intact):`rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate" src/factgraph/adapters/pyreason/` returns 0 hits。
6. **Souffle end-to-end smoke**(round-trip from T2.3b SDK):invoke `build_application_rule(...)` with `agg_sum(...)` example,resulting application Rule's `where` IR can be parsed via current Souffle adapter's `_normalize_where_subset` → should raise `WhereValidationError(f"unsupported atom kind: {kind}")` at line 731 because aggregate is not yet a recognized kind shape inside cmp。This confirms the precondition gap T2.3c fills。

### 5.7 S-class trigger analysis

Per Track plan §1.2.4:

| Trigger | T2.3c reality | Fire? |
|---|---|---|
| Public API impact | None — adapter-internal change only;no public-facing API rename/add/remove | NO |
| Cross-commitment Q load-bearing | None — parent C99/C100/C101/C104 already locked at T2.3a;T2.3c only wires Souffle | NO |
| Design vs shipped ≥ 3 commitments conflict | None — additive over T2.3a substrate + T2.3b SDK | NO |
| Sub-slice count | Track plan §1.2.6 lists T2.3a/b/c/d;T2.3c is 3rd | Within prediction |
| Cross-file commitment mismatch ≥ 2 files | None — touches `where_compile.py` only + docs;all consistent with T2.3a/T2.3b/T2.1/T2.2 patterns | NO |
| Public API rename ≥ 3 caller sites | None — no API surface change | NO |
| Size budget(S ≤ ~300 LOC + ~200 tests ≈ ~500) | ~150 LOC impl + ~150 LOC tests = ~300 LOC | Within budget |
| Cross-engine semantic decision | None — Souffle wire only,ProbLog separated to T2.3.d | NO |

**Conclusion**:S-class lightweight applies。No Stage 2 decision doc opened。

## 6. Boundaries And Invariants

### 6.1 What MUST change

- `src/factgraph/adapters/souffle/where_compile.py` — dispatch + helpers + var extraction + validation extensions for aggregate
- `src/factgraph/application/docs/rule.md` — adapter status table flip(Souffle row pending → Souffle row ✓)

### 6.2 What MUST NOT change (cross-slice contract preservation)

- `src/factgraph/core/rules/where_ast.py` — T2.3a substrate IR;0 diff
- `src/factgraph/core/rules/where_ast_validate.py` — T2.3a substrate validator;0 diff
- `src/factgraph/core/rules/where_eval.py` — T2.3a Python evaluator;0 diff
- `src/factgraph/application/protocol/rule.py` — T2.3a application Rule serialization;0 diff
- `src/factgraph/sdk/dsl/expr.py` — T2.3b SDK ergonomic;0 diff
- `src/factgraph/sdk/dsl/application_rule.py` — T2.3b bridge validator gate;0 diff
- `src/factgraph/sdk/dsl/__init__.py` — T2.3b exports;0 diff
- `src/factgraph/sdk/docs/` — T2.3b SDK docs;0 diff
- `src/factgraph/adapters/problog/` — T2.3.d boundary;0 diff
- `src/factgraph/adapters/pyreason/` — PyReason out-of-scope;0 diff

### 6.3 Invariants

- I1 — Aggregate IR shape consumed unchanged from T2.3b output:`(kind, target_var, filter_atoms)` 3-tuple
- I2 — `_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}` consistent with substrate
- I3 — Aggregate-local var isolation(C104):vars introduced inside filter do NOT bind in outer scope
- I4 — Correlated outer var pass-through(C104):outer-bound vars referenced in filter pass through transparently
- I5 — Filter atom kinds restricted to C100 list(pred/eq/ne/gt/ge/lt/le/in/not);T2.3a substrate enforces upstream,Souffle adapter trusts
- I6 — Aggregate target var is aggregate-local(not in `_vars_in_atom` outer result)
- I7 — count aggregate has `target_var = None`(no target term in Souffle DL)
- I8 — Aggregate result type:numeric;Souffle DL wraps with `to_string(...)` for symbol-typed outer var binding consistency with `_compile_arith_atom` precedent
- I9 — Empty-set semantic gap acknowledged but NOT addressed at Souffle DL layer(documented as follow-up;Python evaluator path remains semantic source-of-truth for `AggregateNoValue`)

## 7. Acceptance

Per T2.3b cross-flip inversion lesson — acceptance tests MUST DISCRIMINATE algorithm branches。Each test is paired with the algorithm decision it discriminates。

### 7.1 Per-kind compile discriminator(5 tests)

For each kind ∈ {count, sum, min, max, mean}:

```python
# Test: agg_<kind>(Order(o).amount, where=[Order(o)]) compiles to expected Souffle DL
where = [
    ("eq", "$result", (<kind>, "$_agg1" if <kind> != "count" else None, [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),  # absent for count
    ]))
]
compiled = compile_where_to_query_dl(where, ...)
# Discriminator: expects EXACTLY the kind string + body
# If impl mismaps kind (e.g., maps "sum" to "mean"), this test fails.
```

Critical:each kind gets its own test(no shared parametric test that could mask kind→syntax map errors)。

### 7.2 Aggregate-in-eq RHS binds outer var(1 test)

```python
where = [
    ("pred", "User:exists", ["$u"]),
    ("eq", "$total", ("sum", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:buyer", ["$o", "$u"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),
    ])),
]
# Discriminator: $total must appear in extract_where_variables result
# and bound after eq atom compile.
```

### 7.3 Aggregate-in-gt cmp filter(1 test)

```python
where = [
    ("pred", "User:exists", ["$u"]),
    ("gt", ("count", None, [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:buyer", ["$o", "$u"]),
    ]), 5),
]
# Discriminator: emits `count : { ... } > 5` filter clause, no binding.
```

### 7.4 Correlated outer var pass-through(1 test)

```python
where = [
    ("pred", "User:exists", ["$u"]),
    ("eq", "$total", ("sum", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:buyer", ["$o", "$u"]),  # $u correlated from outer
        ("pred", "order:amount", ["$o", "$_agg1"]),
    ])),
]
# Discriminator: extract_where_variables includes $u and $total; $o and $_agg1 NOT included.
# If impl leaks aggregate-local $o into outer, this test fails.
```

### 7.5 Aggregate-local var isolation discriminator(1 test)

```python
# Filter introduces $o ONLY inside aggregate; outer scope should NOT see $o.
where = [
    ("eq", "$total", ("sum", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),
    ])),
    # If $o leaked, subsequent atom would think $o is bound
    ("pred", "user:exists", ["$o"]),  # SHOULD raise — $o not bound at outer
]
# Discriminator: expect WhereValidationError or compile failure due to $o unbound outer.
# If impl accidentally binds $o outer-side, this test passes wrongly (no error).
```

This is the **TRUE C104 isolation discriminator** — analogous to T2.3b's TRUE self-ensure test。Without explicit aggregate-local isolation,this case would silently bind $o outer。

### 7.6 Filter `not` body inside aggregate(1 test)

```python
where = [
    ("eq", "$count", ("count", None, [
        ("pred", "Order:exists", ["$o"]),
        ("not", [("pred", "order:cancelled", ["$o"])]),
    ])),
]
# Discriminator: emits `count : { Order_exists(v_o), !order_cancelled_<hash>(v_o) }`
# Verifies filter `not` recursion works inside aggregate body.
```

### 7.7 Validation rejects malformed aggregate(2 tests)

```python
# (a) aggregate kind not in _AGGREGATE_KINDS
where = [("eq", "$x", ("bogus", "$y", []))]
# Discriminator: _validate_atom_subset raises WhereValidationError on unknown kind.

# (b) aggregate tuple wrong arity
where = [("eq", "$x", ("sum",))]
# Discriminator: _validate_atom_subset raises on shape mismatch.
```

## 8. Implementation Plan

1. Record G7 precondition results on impl branch BEFORE code edits(per T2.2/T2.3a/T2.3b discipline)。Single audit log doc-only commit。
2. Import `_AGGREGATE_KINDS` from `factgraph.core.rules.where_ast`(or define adapter-local mirror if lint flags;see §5.1)。
3. Add `_is_aggregate(term)` helper at module level(below `_is_atom`)。
4. Extend `_validate_atom_subset` cmp branch to accept aggregate operand;recurse into filter atoms。
5. Extend `_vars_in_atom` cmp branches(eq / ne / gt / ge / lt / le)to walk aggregate filter atoms;explicitly exclude target_var。
6. Add `_compile_aggregate(...)` helper per §5.3 algorithm。
7. Extend `_compile_cmp_side` per §5.4(aggregate-aware via context kwarg)。
8. Wire `_compile_atom` cmp branches(`eq` / `gt`/`ge`/`lt`/`le`)to recognize aggregate operand and route to `_compile_cmp_side` with aggregate context;`ne` route similarly extends `_compile_ne_filter`。
9. Write tests `tests/adapters/souffle/test_aggregate_compile.py` per §7 (or extend existing test file)。
10. Update `application/docs/rule.md` adapter status table:Souffle row pending → ✓。
11. Run gates:
    - `PYTHONPATH=src python -m unittest tests.adapters.souffle.test_aggregate_compile tests.adapters.souffle.test_where_compile`(or equivalent existing Souffle suite name)
    - Cross-slice non-regression sweep:T2.3a + T2.3b + T2.1 + T2.2 relevant suites
    - `python -m ruff check src/factgraph/adapters/souffle/ tests/adapters/souffle/`
12. Fill §10 Outcome with exact LOC,test outcomes,deviations(particularly the `AggregateNoValue` empty-set gap),follow-up sketch(T2.3.d ProbLog,T2.3.b1/T2.3.e Nit)。

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md` — adapter status table row "Souffle aggregate dispatch pending T2.3.c" → "Souffle aggregate dispatch ✓"(plus brief note on Souffle empty-set semantic gap if reviewer wants explicit acknowledgment)。
- (Optional)`src/factgraph/sdk/docs/03_rules_and_inferences.en.md` aggregate status table row — Souffle row flip per §10.4 follow-up decision。Decision deferred to closure。

## 10. Outcome / Deviations

- Pending。
