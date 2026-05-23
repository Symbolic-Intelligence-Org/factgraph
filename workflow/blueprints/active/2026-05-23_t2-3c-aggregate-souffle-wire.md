# T2.3c — Aggregate Souffle adapter wire over T2.3a substrate + T2.3b SDK

- Status: scoped
- Created: 2026-05-23
- Last Updated: 2026-05-23 (Step 4.6 scoped anchor — v6 review passed 0 findings)
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
  - `_vars_in_atom` aggregate operand contributes **ZERO** outer-var(query-variable set unaffected by aggregate filter atoms;correlated outer vars contributed by their original outer-scope atom;aggregate-local vars stay private per C104)
  - `_infer_var_type_domains` aggregate-filter recursion(walks filter atoms for type-domain inference;marks aggregate `target_var` as int per C102)— separate concern from `_vars_in_atom`(different consumer / different algorithm,per §2.6b)
  - `_validate_atom_subset` aggregate shape validation extension(structural,mandatory regardless of `FACTPY_WHERE_AST_VALIDATE` gate state)
  - Test coverage:per-kind compile + correlation pass-through + aggregate-local isolation + empty-set guard + validation rejection + gate-off validation
  - Adapter status docs:`application/docs/rule.md` adapter status table flip(Souffle pending → Souffle ✓)+ `sdk/docs/03_rules_and_inferences.en.md` §3.2 adapter status table row flip(mandatory per P4 v2)
- Related:
  - `src/factgraph/adapters/souffle/where_compile.py`(extended)
  - `src/factgraph/application/docs/rule.md`(extended — adapter status flip)
  - `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`(extended — §3.2 row flip,P4 v2 mandatory)
  - `src/factgraph/core/rules/where_ast.py`(consumed unchanged — `_AGGREGATE_KINDS` source)
  - `src/factgraph/core/rules/where_ast_validate.py`(consumed unchanged — substrate validator runs upstream)
  - `src/factgraph/core/rules/where_eval.py`(consumed unchanged — Python eval path remains separate)
  - `src/factgraph/sdk/dsl/expr.py`(consumed unchanged — lowering produces aggregate IR)
  - `src/factgraph/sdk/dsl/application_rule.py`(consumed unchanged — bridge validator gate enforces shape before Souffle receives)
- Related Modules:
  - `src/factgraph/adapters/souffle/where_compile.py` — extends `_compile_atom` cmp dispatch + `_compile_cmp_side` + new `_compile_aggregate` helper(with empty-set guard for min/max/mean per P0 v2 lock)+ `_vars_in_atom` aggregate branch(zero outer contribution per P1 v2 fix)+ `_validate_atom_subset` aggregate kinds(gate-on-and-off per P5 v2)+ `_AGGREGATE_KINDS` import or local constant。
  - `src/factgraph/application/docs/rule.md` — flip adapter status table row "Souffle aggregate dispatch pending T2.3.c" → "Souffle aggregate dispatch ✓" + brief empty-set guard explanation。
  - `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` — flip §3.2 adapter status row "Souffle adapter | Deferred to T2.3.c" → "Souffle adapter | Supported(empty min/max/mean follows C101 via count > 0 guard,branch does not fire)"(P4 v2 mandatory)。
- Audit Log:
  - [2026-05-23_t2-3c-aggregate-souffle-wire.audit.md](./2026-05-23_t2-3c-aggregate-souffle-wire.audit.md)
- Branch: `v0.2.0-blueprint-t2-3c-aggregate-souffle-wire-2026-05-23`

> **Cross-slice relationship**:T2.3a shipped(`477fcccb`)the **core substrate**(IR + validation + Python eval + application Rule serialization)。T2.3b shipped(`4e3176d2`)the **SDK ergonomic + bridge**(5 `agg_*` helpers + `_AggregateRef` + DSL→IR lowering + bridge validator gate)。Both deferred Souffle adapter aggregate dispatch to **T2.3c**(this slice)and ProbLog adapter dispatch to **T2.3.d**。T2.3c closes the Souffle path WITHOUT touching T2.3a substrate / T2.3b SDK / T2.3.d ProbLog / PyReason。

## 1. Problem

Parent essay §10.6.3 (C99) defines 5 aggregate kinds(`count` / `sum` / `min` / `max` / `mean`)as value-producing expressions that appear inside comparison atoms(eq / ne / gt / ge / lt / le)。Parent essay §8.8 + §1718 promises Souffle adapter wires native `count` / `sum` / `min` / `max` / `mean` aggregate body lowering with **filter clause embedding**(~150 lines)。

**Current state**(verified 2026-05-23 by G2 source-grep on `src/factgraph/adapters/souffle/`,P3 v2-corrected):

- `rg "AggregateAtom|_AGGREGATE_KINDS|aggregate" src/factgraph/adapters/souffle/` returns **0 hits**。Souffle adapter has zero aggregate handling。
- `where_compile.py:434` `_compile_atom` dispatch recognizes 9 atom kinds(`pred` / `eq` / `ne` / `in` / `gt`/`ge`/`lt`/`le` / `_ARITH_KINDS` / `not`)。Aggregate is NOT a top-level atom kind;it lives INSIDE a cmp atom's lhs/rhs as a tuple operand。
- **Current actual failure path when SDK-produced aggregate IR reaches Souffle adapter**(P3 v2 verified):cmp dispatch routes lhs/rhs through `_compile_cmp_side`(line 905-908)→ `_literal_to_cmp_int_text`(line 911-924)or eventually `_literal_to_text`(line 1106-1113)→ raises `WhereValidationError("unsupported literal type")` because aggregate tuple is neither `bool` / `int` / `str`。Verified 2026-05-23 by user-side reproduction at v1 Step 4.2 review。
- Original v1 wording incorrectly claimed line 731 "unsupported atom kind" fallback — that fires only if aggregate were a top-level atom kind,which it is not。Corrected at v2。
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
- Per C100,filter atom kinds restricted to pred / eq / ne / gt / ge / lt / le / in / **not**。**Structural enforcement at adapter regardless of gate state**(v4/v5 lock):adapter rejects non-C100 filter atom kinds(`_ARITH_KINDS` / nested aggregate / future top-level kinds outside list)because compile path itself cannot proceed — `_ARITH_KINDS` would emit var-binding clauses Souffle aggregate body slots cannot accept;nested aggregate would recurse undefined。T2.3a substrate validator also enforces semantically when `FACTPY_WHERE_AST_VALIDATE=1`(defense-in-depth);adapter is **only safety net** when gate OFF。Deeper semantic checks(RuleRef object shape / RuleExpr AST nesting / C102 numeric runtime / C104 binding-order)remain upstream-only per §5.7.5 Layer 1 / Layer 2 split。

### 2.5 C101 — Empty set + `AggregateNoValue` Souffle representation(v2 lock — implement guard now)

**Locked at v2 per user direction**(P0 Blocker resolution):no `AggregateNoValue` sentinel object in Souffle DL;instead `AggregateNoValue` is represented by **rule branch not firing**,which matches C101 "comparison violated / no env pollution" exactly。

**Algorithm per kind**:

| Kind | Empty-set guard | Rationale |
|---|---|---|
| `count` | None — emit aggregate directly | Empty=0 is a legal C101 value(matches "count int legal value" row of C101 table) |
| `sum` | None — emit aggregate directly | Empty=0 is a legal C101 value(matches "sum numeric legal value" row) |
| `min` | **`count : { same_body } > 0,`** prefix | Empty would be Souffle warning + 0,which conflicts with C101 `AggregateNoValue`;guard forces branch to fail when body empty,honoring C101 "comparison violated" |
| `max` | **`count : { same_body } > 0,`** prefix | Same as `min` |
| `mean` | **`count : { same_body } > 0,`** prefix | Same as `min` |

**Souffle DL emit shape for min/max/mean cmp**:

```souffle
count : { <same_body> } > 0, <kind> <target_expr> : { <body> } <op> <other_side>
```

Two Souffle body clauses comma-joined:guard clause first(count of body > 0)+ value clause second(aggregate cmp)。Both must hold for the enclosing rule branch to fire。

**Souffle DL emit shape for count/sum cmp**:

```souffle
<kind> [<target_expr>] : { <body> } <op> <other_side>
```

Single clause(no guard prefix)。

**Eq binding variant**:`v_total = <aggregate_expr>` where `<aggregate_expr>` follows the same per-kind rule。For min/max/mean,the guard clause precedes the binding clause:

```souffle
count : { <same_body> } > 0, v_total = <kind> <target_expr> : { <body> }
```

**Result return type**:`_compile_aggregate(...)` returns a string that may contain comma-joined Souffle clauses(1 clause for count/sum,2 clauses for min/max/mean)。Caller's atom-join with `", "` naturally accommodates this — a single "atom slot" contributing 1+ Souffle clauses to the body。

**Verification requirement**(P4 v4 wording — future tense,not yet confirmed):Souffle is expected to treat commas as conjunction at body-atom level;`v_total = count : { body } > 0, mean ... : { body }` should parse as two body atoms,not as nested expression syntax。**MUST be verified at Step 4.7 impl-time round-trip test against Souffle binary**(per §8 step 11 Souffle binary smoke)。If verification fails(e.g.,Souffle requires explicit grouping or different conjunction syntax),implement (A-fallback)deviation per CADENCE and document in §10 Outcome at closure。

**Two-aggregate cmp**(e.g., `("eq", agg_left, agg_right)`):each side independently determined。If either side is min/max/mean,its guard prefix prepends。Multiple guards comma-joined。Per-side body may differ;each guard uses its own body。

**C103 snapshot semantics preserved**:`count : { body }` operates on the same projected view as the value aggregate(Souffle clause is shared body),satisfying parent essay §10.6.7 matched_count parity。

### 2.6 Var extraction — `_vars_in_atom` aggregate-aware(v3 P1 fix — aligned with §5.5)

**v1/v2 wrong algorithm removed**(§2.6 v1 originally specified an outer_var_universe intersection;that algorithm was based on a false assumption about `extract_where_variables` filtering against outer scope — see P1 v2 in audit log)。

**v3 correct algorithm**(matches §5.5 precise impl):

Extend `_vars_in_atom` so that when a cmp atom contains an aggregate-tuple operand on lhs or rhs,the **aggregate side contributes ZERO outer vars** to the result。

Rationale per C104:
- **Correlated outer vars** referenced inside aggregate filter(e.g., `$u` referenced inside `order:buyer($o, $u)` while `$u` was bound by an outer `User($u)`)are contributed by their **original outer-scope binding atom**(`User($u)`)independently;the aggregate-filter reference does NOT re-introduce them。Ignoring the aggregate side at `_vars_in_atom` is correct because outer scope already accounts for those vars。
- **Aggregate-local vars**(both `target_var` like `$_agg1` and filter-introduced vars like `$o`)are private per C104。They MUST NOT enter the outer query variable set or witness layout(per `where_compile.py:188-195` `extract_where_variables` direct union + `:217-237` `build_query_witness_layout`)。
- **Result-binding var** of the enclosing cmp atom(e.g., `$total` from `("eq", "$total", aggregate)`)is captured by the existing non-aggregate-side branch of `_vars_in_atom`,not by the aggregate-side walk。

Algorithm shape(implemented in §5.5):

```python
elif _is_aggregate(side):
    pass  # zero contribution; aggregate's own scope is closed at this layer
```

Precise impl + correctness argument in §5.5 v2(P1 fix)。

### 2.6b Type domain inference — `_infer_var_type_domains` aggregate-aware(v3 P2 fix)

`where_compile.py:829-861` `_infer_var_type_domains` currently scans top-level atoms only(`pred` / `_ARITH_KINDS` / `not` body)。It does NOT recurse into cmp atom operands or aggregate filter atoms。

**Gap**:if aggregate filter contains numeric compare(C100-allowed),e.g.

```python
("eq", "$result", ("sum", "$_agg1", [
    ("pred", "Order:exists", ["$o"]),
    ("pred", "order:amount", ["$o", "$_agg1"]),
    ("gt", "$_agg1", 5),     # filter-internal numeric cmp; needs type domain for $_agg1
]))
```

the type domain for `$_agg1` won't be inferred because `order:amount` pred is inside the aggregate filter,not at top level。Subsequent `_assert_cmp_var_allowed` call for the `gt` would see `$_agg1` with no/unknown type domain and raise unexpectedly。

**v3 fix**:extend `_infer_var_type_domains` to recurse into aggregate filter atoms:

```python
def _infer_var_type_domains(body, pred_type_domains):
    out: dict[str, set[str]] = {}

    def add_from_pred_atom(atom):
        # existing logic unchanged

    def walk_atom(atom):
        if atom[0] == "pred":
            add_from_pred_atom(atom)
        elif atom[0] in _ARITH_KINDS:
            for term in atom[1:]:
                if _is_var(term):
                    out.setdefault(term, set()).add("int")
        elif atom[0] == "not":
            for branch in _normalize_not_body_subset(atom[1]):
                for not_atom in branch:
                    walk_atom(not_atom)
        elif atom[0] in {"eq", "ne", "gt", "ge", "lt", "le"}:
            # NEW v3: descend into aggregate operands
            for side in (atom[1], atom[2]):
                if _is_aggregate(side):
                    walk_aggregate(side)
            # numeric cmp also implies int type for var sides (defensive — outer
            # binding atom likely already contributed, but explicit infer
            # consistency).
            if atom[0] in {"gt", "ge", "lt", "le"}:
                for side in (atom[1], atom[2]):
                    if _is_var(side):
                        out.setdefault(side, set()).add("int")

    def walk_aggregate(aggregate):
        _, target_var, filter_atoms = aggregate
        if target_var is not None and isinstance(target_var, str) and target_var.startswith("$"):
            out.setdefault(target_var, set()).add("int")  # numeric aggregate target_var
        for filter_atom in filter_atoms:
            walk_atom(filter_atom)

    for atom in body:
        walk_atom(atom)
    return out
```

**Two responsibilities added**:
- Aggregate filter atoms walked recursively for type domain contributions(includes pred atoms that contribute correlated outer var types AND aggregate-local var types)
- Aggregate `target_var` explicitly marked `int` type domain(numeric aggregate target per C102)

**Note on scope**:type domains for aggregate-local vars(`$o`, `$_agg1`)enter the same `out` dict alongside outer vars,but downstream `_compile_aggregate` uses `local_bound_vars` for binding tracking。Type domain dict is **flat**(no scope marker);aggregate-local var symbols are unique(SDK uses `$_agg<N>` prefix),so no name collision with outer。Adapter relies on this naming convention(documented in §6 invariant I11)。

### 2.7 Validation — `_validate_atom_subset` aggregate shape

In `_validate_atom_subset` cmp branch(`kind in {"eq", "ne", "gt", "ge", "lt", "le"}`),allow aggregate-tuple operand。Aggregate-tuple shape validation:

- `isinstance(aggregate, tuple) and len(aggregate) == 3`
- `aggregate[0] in _AGGREGATE_KINDS`
- `aggregate[1]` is either `None`(count) OR a `$`-prefixed var string(numeric aggregates)
- `aggregate[2]` is a list of valid filter atoms(each recursively validates via `_validate_atom_subset`)

Note:T2.3a upstream validator `validate_where_ast` already enforces filter restrictions(C100)at the substrate layer。Souffle adapter validator only checks **shape**(tuple structure),trusting upstream for **semantic** restrictions。This is defense-in-depth without re-implementing T2.3a substrate logic。

### 2.8 Tests — acceptance suite with discriminator design

Per T2.3b cross-flip inversion lesson(reviewer must verify each acceptance test discriminates the intended algorithm branch),acceptance includes 21+ tests targeting specific algorithm decisions:

1. Each of 5 aggregate kinds compiles to correct Souffle DL syntax(5 tests — §7.1 per-kind discriminators)
2. Aggregate in eq RHS binds outer var(§7.2)
3. Aggregate in gt cmp(no binding,just filter)(§7.3)
4. Correlated outer var pass-through + aggregate-local NOT in extract(§7.4)
5. Aggregate-local var isolation — TRUE C104 discriminator via `ne` bound-required atom(§7.5,P2 v2 fix)
6. Filter with `not` body — compiles correctly nested inside aggregate body(§7.6)
7. Validation rejects malformed aggregate shape(§7.7 — 2 tests)
8. **min/max/mean guard prefix emit shape + to_string/to_number wrapping**(§7.8 — 4 tests + 1 negative discriminator for count/sum;P0 v2 lock + P3 v3 wrapping lock)
9. **min empty-set branch-not-firing runtime**(§7.9 — 1 optional Souffle-binary integration test)
10. **Adapter validation regardless of gate state**(§7.10 — 2 tests,P5 v2 lock)
10b. **Adapter rejects non-C100 filter atom kinds regardless of gate**(§7.10b — 2 tests,P1 v4 lock)
11. **Type domain inference inside aggregate filter**(§7.11 — 2 tests,P2 v3 lock)

Detailed in §7。

### 2.9 G7 pre-impl precondition checks

Recorded BEFORE implementation per T2.2/T2.3a/T2.3b discipline。Detailed in §5.6。

## 3. Non-goals

- **T2.3.d ProbLog aggregate wire** — separate slice;ProbLog uses `findall/3` + list predicates,fundamentally different lowering algorithm
- **PyReason aggregate** — out of scope(parent essay §10.6.3 line 1711 marks N/A;PyReason is Form 2 only)
- **T2.3a substrate changes** — IR / validator / Python eval / application Rule all consumed unchanged
- **T2.3b SDK changes** — `_AggregateRef` / 5 helpers / lowering / bridge validator gate all consumed unchanged
- **Aggregate-in-arith-atom** — deferred Nit from T2.3b(`_lower_compare_with_aggregate` non-aggregate side limitation);T2.3.b1/T2.3.e candidate
- **Nested aggregate support** — out of scope for ANY future expansion in T2.3c。Adapter rejects nested aggregate(aggregate appearing inside another aggregate's filter)as **structural invalid input** at `_validate_atom_subset`(mandatory regardless of gate state per §5.7.5 Layer 1 / I10 v5)。T2.3a substrate validator also rejects upstream when gate ON(defense-in-depth)。Adapter is only safety net when gate OFF。
- **New aggregate kinds beyond 5** — locked at parent essay C99
- **New filter atom kinds beyond C100** — pred / eq / ne / gt / ge / lt / le / in / not list locked
- **Witness layout for aggregate result** — aggregates produce derived numeric values;no rule occurrence witness
- **Souffle `mean` derived fallback** — assumes native Souffle 2.x `mean` aggregator support;if impl reveals unsupported,(A-fallback) deviation per CADENCE
- **Souffle DL sentinel object for AggregateNoValue** — v2 lock per P0 resolution:no sentinel value object;empty-set semantic enforced via `count > 0` guard clause on min/max/mean(see §2.5)。Branch-not-firing represents C101 violated comparison。
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
- `src/factgraph/adapters/souffle/where_compile.py:1139-1173` `_vars_in_atom(...)` — var extraction(outer-scope query var set);T2.3c extends cmp branches so **aggregate operand contributes ZERO outer vars**(per §5.5 v2 + §2.6 v3)。Correlated outer vars are bound by their original outer-scope atom independently;aggregate-local vars stay private per C104。
- `src/factgraph/adapters/souffle/where_compile.py:829-861` `_infer_var_type_domains(...)` — type domain inference(value types for cmp safety);T2.3c extends to **recurse into aggregate filter atoms** AND mark aggregate `target_var` as int(per §2.6b v3 P2)。Separate concern from `_vars_in_atom`(outer-scope membership);different consumer / different algorithm。
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

### 5.3 `_compile_aggregate` helper(v2 — includes empty-set guard for min/max/mean)

```python
_AGGREGATE_GUARD_KINDS = {"min", "max", "mean"}

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

    # Value clause per kind
    if kind == "count":
        value_clause = f"count : {{ {body} }}"
    else:
        target_sym = _symbol_for_var(var_symbols, target_var)
        target_expr = f"to_number({target_sym})"
        value_clause = f"{kind} {target_expr} : {{ {body} }}"

    # Per §2.5: min/max/mean require count > 0 guard prefix
    # to honor C101 AggregateNoValue via branch-not-firing semantics
    if kind in _AGGREGATE_GUARD_KINDS:
        guard_clause = f"count : {{ {body} }} > 0"
        return f"{guard_clause}, {value_clause}"

    return value_clause
```

**Return shape**:`_compile_aggregate(...)` returns a **bare numeric aggregate expression**(without `to_string` wrap)。Caller(`_compile_atom` cmp branch / `_compile_cmp_side`)decides wrap based on context — see §5.3.5 for the precise rule。1 Souffle clause for count/sum or 2 comma-joined clauses for min/max/mean(guard + value)。The guard clause's body is **identical** to the value clause's body — guarantees C103 snapshot parity since both aggregates operate on the same projected view。

### 5.3.5 to_string / to_number wrapping rules(v3 P3 lock)

Aggregate expressions return **numeric**(per Souffle aggregator return type)。Souffle var symbols are **symbol-typed**(strings)by default(per `_compile_arith_atom:1103` precedent storing arith results via `to_string(...)`)。The boundary between these two domains MUST be locked precisely to avoid impl-time guessing:

| Caller context | DL emit shape | Rationale |
|---|---|---|
| **eq binding to unbound var**:`("eq", "$X", aggregate)` with `$X` not in `bound_vars` | `v_X = to_string(<aggregate_expr>)` | Symbol-domain binding;`$X` joins `bound_vars` with symbol type;`to_string` matches `_compile_arith_atom:1103` precedent |
| **eq filter with bound var**:`("eq", "$X", aggregate)` with `$X` in `bound_vars` | `<aggregate_expr> = to_number(v_X)` | Numeric eq filter;aggregate stays numeric,bound var gets `to_number` coercion per `_compile_cmp_side:907` precedent |
| **eq filter with int literal**:`("eq", aggregate, 100)` | `<aggregate_expr> = 100` | Numeric eq;literal stays as integer literal;no coercion |
| **eq filter with two aggregates**:`("eq", agg_left, agg_right)` | `<agg_left_expr> = <agg_right_expr>` | Numeric eq;both sides aggregate(both already numeric) |
| **numeric cmp(`gt`/`ge`/`lt`/`le`)with var**:e.g.,`("gt", aggregate, "$X")` with `$X` bound | `<aggregate_expr> > to_number(v_X)` | Numeric cmp filter;var gets `to_number` per `_compile_cmp_side` |
| **numeric cmp with int literal**:`("gt", aggregate, 5)` | `<aggregate_expr> > 5` | Numeric cmp;literal stays as integer per `_literal_to_cmp_int_text` |
| **numeric `ne`**:e.g.,`("ne", aggregate, 5)` | `<aggregate_expr> != 5` | Same as gt/ge/lt/le family;numeric filter |
| **`in` aggregate**:not valid IR | N/A | `in` operand must be a Var per `_validate_atom_subset:706`;aggregate not allowed |

**Eq binding decision discriminator**:`bound_vars` set state determines whether eq emits binding(symbol domain via `to_string`)or filter(numeric domain raw)。Same dispatch as existing eq branch at `where_compile.py:477-504`:

```python
if kind == "eq":
    _, lhs, rhs = atom
    lhs_is_var = _is_var(lhs)
    rhs_is_var = _is_var(rhs)
    lhs_is_agg = _is_aggregate(lhs)
    rhs_is_agg = _is_aggregate(rhs)

    # Aggregate path — exactly one side is aggregate
    if rhs_is_agg and lhs_is_var:
        agg_expr = _compile_aggregate(aggregate=rhs, ...)
        if lhs not in bound_vars:
            bound_vars.add(lhs)
            return f"{var_symbols[lhs]} = to_string({agg_expr})"  # symbol binding
        return f"{agg_expr} = to_number({var_symbols[lhs]})"      # numeric filter
    # symmetric for lhs_is_agg and rhs_is_var
    # ... numeric literal cases per table above

    # Existing non-aggregate eq path unchanged
```

**Why this matters**:without this lock,impl might inconsistently apply `to_string` everywhere(breaking numeric cmp)or never(breaking symbol binding)。`_compile_aggregate` returns bare numeric to keep the wrapper decision at the call site where context(binding vs filter)is known。

**Filter atom compile within aggregate** uses a separate function `_compile_filter_atom_within_aggregate` that mirrors `_compile_atom` but:
- Operates on `local_bound_vars`(scope isolation — see §2.4)
- Rejects filter-kind atoms outside C100 list(though T2.3a upstream already rejects;defense-in-depth at adapter shape layer per §5.7.5 gate-off behavior)
- Does NOT emit witness symbols for filter pred atoms(aggregate body has no rule-level witness)
- Returns single-clause DL text

Alternative:if reusing `_compile_atom` directly is cleaner with a `within_aggregate=True` flag,acceptable per impl choice。Impl may pick the cleaner factoring。

**Two-aggregate cmp edge case**:if both sides of cmp atom are aggregate(`("eq", agg_left, agg_right)`),each `_compile_aggregate` call independently emits its own guard if needed。Result:up to 2 guard clauses + 1 cmp expression:

```souffle
count : { body_left } > 0, count : { body_right } > 0, min ... : { body_left } = max ... : { body_right }
```

All guards must hold,plus the value cmp。Conjunction semantics handle this naturally。

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

### 5.5 `_vars_in_atom` aggregate-aware extension(v2 fix — P1 Blocker resolution)

**v1 algorithm was false** — `extract_where_variables`(line 188-195)does NOT filter against outer scope;it directly unions `_vars_in_atom` results into the query variable set。Returning all aggregate filter vars would leak `$o` / `$_agg1` into query vars and witness layout(`build_query_witness_layout` line 217-237)。

**v2 algorithm — aggregate vars contribute ZERO to outer extract**:

```python
def _vars_in_atom(atom: tuple[Any, ...], *, include_not_body_vars: bool) -> list[str]:
    kind = atom[0]
    found: set[str] = set()
    # ... existing kinds for pred/eq/in/etc. ...
    elif kind in {"eq", "ne", "gt", "ge", "lt", "le"}:
        _, lhs, rhs = atom
        for side in (lhs, rhs):
            if _is_var(side):
                found.add(side)
            # NOTE: aggregate-tuple side contributes NO outer vars.
            # Correlated outer vars referenced inside aggregate filter are bound
            # by their original outer-scope atom (e.g., `User(u)` binds `$u`
            # via an earlier atom in the same where). The aggregate-filter
            # reference does NOT re-introduce them; ignoring the aggregate side
            # entirely is correct because outer scope already accounts for
            # those vars via their canonical bindings.
            # Aggregate-local vars (target_var + filter-introduced vars) are
            # private per C104 and MUST stay out of the outer extract.
            elif _is_aggregate(side):
                pass  # zero contribution; aggregate's own scope is closed
    # ... rest of existing kinds ...
    return sorted(found)
```

**Correctness argument**:

1. **Correlated outer vars** referenced inside aggregate filter are by definition pre-bound by an outer atom(per C104 — T2.3a substrate validator rejects aggregates whose filter references unbound vars before scoped-anchor)。Those outer atoms contribute the vars to `_vars_in_atom` independently;ignoring the aggregate-side reference does not lose them。
2. **Aggregate-local vars**(both target_var like `$_agg1` and filter-introduced vars like `$o`)are private per C104;they MUST NOT enter the outer query variable set or witness layout。Returning zero from aggregate side guarantees this。
3. **Result-binding var**(e.g., `$total` from `("eq", "$total", aggregate)`)is the lhs/rhs **non-aggregate** var of the cmp atom — already captured by the existing `_is_var(side)` branch above。

**Compile-time consequence**:within aggregate body compile(`_compile_aggregate` `local_bound_vars`),correlated outer vars must already be in `var_symbols` and `outer_bound_vars` from preceding outer atoms。Aggregate-local vars are introduced into `local_bound_vars` only;they do not propagate back to `outer_bound_vars`(scope isolation — see §2.4)。`var_symbols` is a shared dict but aggregate-local var names are unique(SDK uses `$_agg<N>` prefix per T2.3b lowering)so symbol collision is not a concern。

**Witness layout consequence**:`build_query_witness_layout`(line 217-237)iterates top-level atoms — aggregate-internal pred atoms do NOT appear at top level,so no aggregate-internal pred contributes a witness column。This is correct:aggregate produces a derived numeric value,not a matched fact row;no witness needed。Confirmed by §6 invariant I6 + §3 Non-goals "Witness extension for aggregate result vars"。

### 5.6 G7 pre-implementation preconditions

Recorded BEFORE implementation per established discipline。To be verified on impl branch fork:

1. **T2.3a substrate present**:`AggregateAtom` at `where_ast.py:75` + `_AGGREGATE_KINDS` at `where_ast.py:102` + `validate_where_ast(...)` with aggregate filter restriction(C100)at `where_ast_validate.py`。
2. **T2.3b SDK lowering present**:`_AggregateRef` at `sdk/dsl/expr.py:209` + `_lower_compare_with_aggregate` at `:459` produces aggregate IR of shape `("eq", lhs, ("sum", target_var, filter_atoms))`(verified via T2.3b acceptance tests)。
3. **Souffle aggregate dispatch empty**(this slice's add point):`rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate" src/factgraph/adapters/souffle/` returns 0 hits。
4. **ProbLog aggregate dispatch empty**(T2.3.d boundary intact):`rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate" src/factgraph/adapters/problog/` returns 0 hits。
5. **PyReason aggregate dispatch empty**(out-of-scope intact):`rg "AggregateAtom\|_AGGREGATE_KINDS\|aggregate" src/factgraph/adapters/pyreason/` returns 0 hits。
6. **Souffle end-to-end smoke**(round-trip from T2.3b SDK):invoke `build_application_rule(...)` with `agg_sum(...)` example,resulting application Rule's `where` IR passes to current Souffle adapter `compile_where_to_query_dl(...)` → should raise `WhereValidationError("unsupported literal type")` at `_literal_to_text` line 1106-1113 because the aggregate tuple inside cmp atom's lhs/rhs operand is neither bool/int/str(reaches `_literal_to_text` via `_compile_cmp_side` line 905-908 → `_literal_to_cmp_int_text` line 911-924 → fallback)。Verified 2026-05-23 by user-side reproduction at v1 review。This confirms the precondition gap T2.3c fills。

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

### 5.7.5 Gate-off behavior(P5 v2 resolution + P1 v4 clarification)

`FACTPY_WHERE_AST_VALIDATE=0` disables the upstream T2.3a substrate validator(`_where_ast_gate_enabled` at `where_compile.py:136-138`)。When the gate is OFF,malformed aggregate IR can reach Souffle adapter without upstream semantic validation。Adapter-side `_validate_atom_subset` is the only safety net in that mode。

**Two layers of adapter aggregate validation**(P1 v4 lock):

1. **Structural/operational validation — MANDATORY regardless of gate state**:checks that the adapter literally cannot compile to valid Souffle DL without。These are NOT semantic restrictions;the adapter must reject these inputs because the compile path has no defined behavior。
2. **Semantic validation — upstream-only,not adapter**:checks that are about meaning/design intent;upstream T2.3a substrate validator owns these。If gate OFF,user opts out。

**Layer 1 — Adapter MUST validate regardless of gate state**:

| Check | Required at adapter | Rationale |
|---|---|---|
| Aggregate kind ∈ `_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}` | YES — `WhereValidationError("unsupported aggregate kind: ...")` | No Souffle DL emit path for unknown kind |
| Tuple arity == 3(`(kind, target_var, filter_atoms)`)| YES — `WhereValidationError("aggregate atom must be (kind, target_var, [filter_atoms])")` | Compile path destructures via 3-tuple unpacking |
| `target_var` shape:`None` for kind=="count",`$`-prefixed string otherwise | YES — `WhereValidationError("count target_var must be None")` / `WhereValidationError("numeric aggregate target_var must be $-prefixed variable")` | `_symbol_for_var` requires `$`-prefixed token;count has no target term in Souffle DL |
| `filter_atoms` is `list` | YES — `WhereValidationError("aggregate filter must be list")` | Compile path iterates filter atoms |
| Each `filter_atom` is well-formed via recursive `_validate_atom_subset` | YES — recurse;sub-atom errors propagate with path context | Filter atoms compile via same atom dispatch;malformed sub-atoms break compile |
| Nested aggregate(filter_atom is itself aggregate) | YES — `WhereValidationError("aggregate not allowed inside aggregate filter")` | Souffle aggregate body cannot nest aggregate |
| **Filter atom kind ∈ {pred / eq / ne / gt / ge / lt / le / in / not}(C100 list)** | **YES regardless of gate** — `WhereValidationError("<kind> not allowed inside aggregate filter (C100)")` | **Structural**: `_ARITH_KINDS` top-level atoms compile via `_compile_arith_atom` which has no defined behavior inside aggregate body;Souffle DL aggregate body atom slots only accept relational/filter clauses。Same for any future top-level atom kinds outside C100。Validating at adapter regardless of gate is mandatory because the compile path itself cannot proceed otherwise。|

**Why filter-kind validation is structural at adapter**(not just defense-in-depth):

`_ARITH_KINDS` top-level atoms(`add` / `sub` / `neg` / `addc` / `mulc`)compile via `_compile_arith_atom`(line 1060-1103)which emits `<z> = to_string(<expr>)` — a **var-binding clause**,not a relational/filter clause。Souffle aggregate body slots accept only relational atoms(`relation(args)`)or filter atoms(`expr <op> expr` / `!relation(...)`)。Var-binding-via-arith inside aggregate body is undefined。If gate OFF and filter contains `("add", ...)`,`_compile_filter_atom_within_aggregate` would either crash on dispatch or emit malformed DL。Adapter MUST reject upfront。

Similarly,top-level filter kinds outside C100 list(any future kinds added without adapter awareness)would have undefined behavior inside aggregate body — reject upfront。

**Layer 2 — Adapter does NOT re-implement these semantic checks**(upstream-only):

- C100 filter restriction *outside* the kind-list constraint(e.g.,RuleRef object semantics,RuleExpr nesting at AST layer)— substrate validator enforces;adapter doesn't see these as kind-list violations because RuleRef / RuleExpr are not raw-tuple-atom forms that reach Souffle adapter at all。If gate OFF and substrate produces malformed shape,adapter's structural shape checks catch it。
- C102 numeric target type runtime check — substrate validator + Python eval;adapter cannot type-check generic var types。
- C104 binding-order scoping(correlated var must be pre-bound before aggregate appearance)— substrate validator;deferred upstream-only(adapter does not re-implement binding-order analysis,which is a flow-state semantic check rather than structural compile gate)。
- C103 snapshot semantics — substrate evaluator concern,not adapter compile。

**Test §7.10 + §7.10b verify both layers**(see §7)。

## 6. Boundaries And Invariants

### 6.1 What MUST change

- `src/factgraph/adapters/souffle/where_compile.py` — dispatch + helpers + var extraction + validation extensions for aggregate
- `src/factgraph/application/docs/rule.md` — adapter status table flip(Souffle row pending → Souffle row ✓)
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` — §3.2 adapter status table row flip(P4 v2 lock — mandatory because T2.3b shipped this row pointing to T2.3.c)

### 6.2 What MUST NOT change (cross-slice contract preservation)

- `src/factgraph/core/rules/where_ast.py` — T2.3a substrate IR;0 diff
- `src/factgraph/core/rules/where_ast_validate.py` — T2.3a substrate validator;0 diff
- `src/factgraph/core/rules/where_eval.py` — T2.3a Python evaluator;0 diff
- `src/factgraph/application/protocol/rule.py` — T2.3a application Rule serialization;0 diff
- `src/factgraph/sdk/dsl/expr.py` — T2.3b SDK ergonomic;0 diff
- `src/factgraph/sdk/dsl/application_rule.py` — T2.3b bridge validator gate;0 diff
- `src/factgraph/sdk/dsl/__init__.py` — T2.3b exports;0 diff
- `src/factgraph/sdk/docs/04_api_surface.en.md` — T2.3b API surface table;0 diff(adapter wire doesn't add new public symbols)
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md` — **EXCEPT** §3.2 adapter status table row "Souffle adapter" which MUST flip per §6.1 P4 v2 lock。Rest of file:0 diff。
- `src/factgraph/adapters/problog/` — T2.3.d boundary;0 diff
- `src/factgraph/adapters/pyreason/` — PyReason out-of-scope;0 diff

### 6.3 Invariants

- I1 — Aggregate IR shape consumed unchanged from T2.3b output:`(kind, target_var, filter_atoms)` 3-tuple
- I2 — `_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}` consistent with substrate
- I3 — Aggregate-local var isolation(C104):vars introduced inside filter do NOT bind in outer scope
- I4 — Correlated outer var pass-through(C104):outer-bound vars referenced in filter pass through transparently
- I5 — Filter atom kinds restricted to C100 list(pred/eq/ne/gt/ge/lt/le/in/not);**adapter enforces this structural kind-list inside aggregate filter regardless of `FACTPY_WHERE_AST_VALIDATE` gate state**(P1 v4 lock — `_ARITH_KINDS` and other non-C100 kinds compile to clauses Souffle aggregate body slots cannot accept,so adapter rejection is structural not semantic)。T2.3a substrate also enforces this upstream as a semantic check when gate ON;adapter is defense-in-depth + only safety net when gate OFF。
- I6 — Aggregate target var is aggregate-local(not in `_vars_in_atom` outer result)
- I7 — count aggregate has `target_var = None`(no target term in Souffle DL)
- I8 — Aggregate result type:numeric;Souffle DL wraps with `to_string(...)` only for **eq binding to unbound var**(symbol-domain target);numeric cmp / eq filter / aggregate-vs-aggregate paths leave aggregate raw numeric(per §5.3.5 v3 lock table)
- I9 — Empty-set semantics for min/max/mean enforced via `count : { same_body } > 0` guard clause prefix(v2 P0 lock);count/sum native empty=0 matches C101 directly;`AggregateNoValue` represented by branch-not-firing(comparison violated / no env pollution)— no separate Souffle sentinel object
- I10 — Adapter-side aggregate validation in `_validate_atom_subset` is mandatory regardless of `FACTPY_WHERE_AST_VALIDATE` gate state(P5 v2 + P1 v4 lock)。**Layer 1**(structural,mandatory regardless of gate):aggregate kind ∈ `_AGGREGATE_KINDS` / tuple arity / target_var shape / filter_atoms list / recursive shape / no nested aggregate / **filter atom kind ∈ C100 list per I5**。**Layer 2**(deeper semantic checks deferred upstream-only):C100 semantics OUTSIDE the kind-list constraint(RuleRef object semantics,RuleExpr nesting at AST layer)/ C102 runtime numeric target type / C104 binding-order scoping / C103 snapshot semantics — adapter does NOT re-implement these because they're not structurally compile-blocking。See §5.7.5 for full Layer 1 / Layer 2 table。
- I11 — Aggregate-local var naming convention:T2.3b SDK lowering uses `$_agg<N>` prefix for aggregate target vars;`_infer_var_type_domains` flat dict relies on this to avoid name collision with outer-scope vars(per §2.6b v3 P2)。Adapter does NOT defensively rename;if SDK ever changes naming,T2.3c must update。

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

### 7.5 Aggregate-local var isolation discriminator(1 test — P2 v2 fix)

**v1 used `("pred", "user:exists", ["$o"])` as the leak detector,but `pred` binds new vars(`where_compile.py:466 bound_vars.add(term)`)so the test would NOT discriminate** — pred would simply bind `$o` regardless of leak state。

**v2 fix per reviewer suggestion:use a bound-required atom**(`ne`):

```python
# Filter introduces $o ONLY inside aggregate; outer scope should NOT see $o.
where = [
    ("eq", "$total", ("sum", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),
    ])),
    # `ne` requires lhs var to be already-bound (where_compile.py:888-893);
    # if $o leaked into outer bound_vars, this would compile successfully.
    # If $o is correctly aggregate-local, this raises WhereValidationError.
    ("ne", "$o", "blocked"),
]
# Discriminator: assertRaises(WhereValidationError) due to "$o not bound before filter"
# If impl accidentally binds $o outer-side, the test FAILS (no error raised).
```

This is the **TRUE C104 isolation discriminator** — analogous to T2.3b's TRUE self-ensure test。Test uses `assertRaises(WhereValidationError)` explicitly,verifying the error message contains "ne variable must be bound before filter: $o"(matches `_compile_ne_filter` error at `where_compile.py:891-893`)。

**Symmetric tests for `extract_where_variables` outer scope**(P1 v2 fix complement):

```python
where = [
    ("pred", "User:exists", ["$u"]),
    ("eq", "$total", ("sum", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:buyer", ["$o", "$u"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),
    ])),
]
# Discriminator: extract_where_variables(where) == ["$total", "$u"] (sorted)
# $o and $_agg1 are aggregate-local → MUST NOT appear in result
# $u is contributed by the outer User(u) predicate, not by the aggregate-filter
# reference (per P1 v2 fix: aggregate side contributes ZERO to outer extract)
assert extract_where_variables(where) == ["$total", "$u"]
```

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

### 7.8 Empty-set guard discriminator for min/max/mean(4 tests — P0 v2 lock + P3 v3 wrapping)

Per §2.5 v2 lock + §5.3.5 v3 to_string/to_number rules,min/max/mean compile MUST prefix `count : { same_body } > 0,` guard。Discriminator tests verify **both** the guard prefix **and** the to_string/to_number wrapping per §5.3.5 table:

```python
# Test (a) — eq binding to unbound var: to_string wrap (symbol binding)
where = [
    ("eq", "$min_amount", ("min", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),
    ]))
]
compiled = compile_where_to_query_dl(where=where, schema_ir=..., ...)
# Discriminator: compiled DL contains
#   - "count : { ... } > 0"                                (guard clause)
#   - "v_min_amount = to_string(min to_number(v__agg1) : { ... })"   (binding via to_string)
# joined by comma. Verifies BOTH guard prefix AND symbol-binding to_string wrap.

# Test (b) — numeric cmp (gt) with int literal: NO to_string, raw numeric aggregate
where = [
    ("gt", ("max", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),
    ]), 5)
]
# Discriminator: compiled contains
#   - "count : { ... } > 0"                                (guard clause)
#   - "max to_number(v__agg1) : { ... } > 5"               (raw numeric cmp, no to_string)
# If impl wraps aggregate in to_string for numeric cmp, this fails.

# Test (c) — eq binding for mean: to_string wrap + guard
where = [
    ("eq", "$avg", ("mean", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),
    ]))
]
# Discriminator: "count : { ... } > 0, v_avg = to_string(mean to_number(v__agg1) : { ... })"

# Test (d) — eq filter with bound var: aggregate numeric vs to_number(var)
where = [
    ("pred", "User:exists", ["$u"]),
    ("eq", "$u", ("min", "$_agg1", [...])),  # $u already bound by outer pred
]
# Discriminator: compiled contains
#   - "count : { ... } > 0"                                (guard clause)
#   - "min to_number(v__agg1) : { ... } = to_number(v_u)"  (numeric filter, no to_string)
# Verifies the bound-var branch of §5.3.5 eq decision tree.
```

**Discriminator strength**:if implementation drops the `_AGGREGATE_GUARD_KINDS` branch,tests (a)-(d) all fail(guard missing)。If impl confuses to_string/to_number boundary,(a)/(c) catch wrong-symbol-binding and (b)/(d) catch wrong-numeric-cmp。Symmetric negative test for count/sum:

```python
# Test (e) — count emits NO guard (empty-set = 0 is legal C101 value)
where = [("eq", "$cnt", ("count", None, [("pred", "Order:exists", ["$o"])]))]
# Discriminator: compiled does NOT contain "count : { ... } > 0," prefix;
# emits "v_cnt = to_string(count : { ... })" only.
# If impl accidentally adds guard to count/sum, this test fails.
```

### 7.9 Empty-set runtime branch-not-firing(1 integration test if Souffle binary available)

```python
# Build a rule with min over an empty entity set; expect NO query row emitted.
# (Requires Souffle binary; gated via @unittest.skipUnless or similar.)
where = [
    ("eq", "$min_amount", ("min", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),
    ]))
]
# Facts: empty Order:exists (no orders).
# Discriminator: query result is empty (branch not firing per C101 violated cmp).
# If guard missing: Souffle would emit row with min=0 (warning), wrongly passing.
```

This test is optional in impl if Souffle binary integration is gated behind a separate test target;the DL emit-shape tests 7.8(a)-(c)provide sufficient discriminator coverage at the unit-test layer。

### 7.10 Adapter validation regardless of gate state(2 tests — P5 v2)

```python
# Test (a) — adapter rejects unknown aggregate kind with gate ON
os.environ["FACTPY_WHERE_AST_VALIDATE"] = "1"
where = [("eq", "$x", ("bogus_kind", "$y", []))]
# Discriminator: assertRaises(WhereValidationError) — "unsupported aggregate kind: bogus_kind"

# Test (b) — adapter rejects unknown aggregate kind with gate OFF (no upstream check)
os.environ["FACTPY_WHERE_AST_VALIDATE"] = "0"
where = [("eq", "$x", ("bogus_kind", "$y", []))]
# Discriminator: assertRaises(WhereValidationError) — SAME error, adapter is safety net.
```

### 7.10b Adapter rejects non-C100 filter atom kinds regardless of gate(2 tests — P1 v4 lock)

Structural validation:`_ARITH_KINDS` top-level atoms compile to var-binding clauses,which Souffle aggregate body slots do not accept。Adapter MUST reject these inside aggregate filter regardless of gate state(per §5.7.5 Layer 1 structural validation)。

```python
# Test (a) — gate ON: arith atom in aggregate filter rejected
os.environ["FACTPY_WHERE_AST_VALIDATE"] = "1"
where = [("eq", "$result", ("sum", "$_agg1", [
    ("pred", "Order:exists", ["$o"]),
    ("pred", "order:amount", ["$o", "$_agg1"]),
    ("add", "$x", "$y", "$z"),  # ArithExpr not allowed in C100 filter
]))]
# Discriminator: assertRaises(WhereValidationError) — "add not allowed inside aggregate filter (C100)"
# T2.3a upstream validator catches this first;adapter is redundant guard

# Test (b) — gate OFF: SAME rejection at adapter (only safety net)
os.environ["FACTPY_WHERE_AST_VALIDATE"] = "0"
where = [("eq", "$result", ("sum", "$_agg1", [
    ("pred", "Order:exists", ["$o"]),
    ("pred", "order:amount", ["$o", "$_agg1"]),
    ("add", "$x", "$y", "$z"),
]))]
# Discriminator: assertRaises(WhereValidationError) — SAME error.
# CRITICAL: if adapter does NOT enforce filter-kind restriction at validation,
# compile path crashes or emits malformed DL when gate OFF.
```

**Why these tests matter**:without P1 v4 lock,gate-off would let `add`/`sub`/etc. reach `_compile_filter_atom_within_aggregate` which would either:
- Dispatch to `_compile_arith_atom` emitting `v_z = to_string(...)` inside aggregate body(Souffle parse error);or
- Hit fallback `WhereValidationError("unsupported atom kind")` but at the wrong point in the call stack(error message obscured)

Either way,adapter behavior is undefined。v4 P1 mandates explicit validation upfront。

### 7.11 Type domain inference inside aggregate filter(2 tests — P2 v3 lock)

Verifies `_infer_var_type_domains` walks aggregate filter atoms,so `_assert_cmp_var_allowed` works for aggregate-internal cmp。

```python
# Test (a) — aggregate target_var gets int type domain
where = [
    ("eq", "$result", ("sum", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),
    ]))
]
# Discriminator: inferred type domains include $_agg1 with at least the
# pred-derived type AND explicit "int" from aggregate target classification.
domains = _infer_var_type_domains(where[0]_body, schema_pred_types)
assert "$_agg1" in domains
# Either pred-derived (e.g., "number") or "int" — at minimum non-empty.

# Test (b) — filter-internal numeric cmp uses correctly inferred type
where = [
    ("eq", "$result", ("sum", "$_agg1", [
        ("pred", "Order:exists", ["$o"]),
        ("pred", "order:amount", ["$o", "$_agg1"]),
        ("gt", "$_agg1", 5),  # filter-internal cmp; requires $_agg1 in type domain
    ]))
]
# Discriminator: compile succeeds (no "unknown type" error from _assert_cmp_var_allowed).
# If v3 P2 fix is missing, this test fails with WhereValidationError on $_agg1 type.
compiled = compile_where_to_query_dl(where=where, ...)
assert "count : { ... } > 0" in compiled or "sum" in compiled  # min/max/mean → guard
```

## 8. Implementation Plan

1. Record G7 precondition results on impl branch BEFORE code edits(per T2.2/T2.3a/T2.3b discipline)。Single audit log doc-only commit。
2. Import `_AGGREGATE_KINDS` from `factgraph.core.rules.where_ast`(or define adapter-local mirror if lint flags;see §5.1)。
3. Add `_is_aggregate(term)` helper at module level(below `_is_atom`)。
4. Extend `_validate_atom_subset` cmp branch to accept aggregate operand;recurse into filter atoms;enforce C100 filter kind restriction per §5.7.5 Layer 1(P1 v4 — mandatory regardless of gate state)。
5. Extend `_vars_in_atom` cmp branches(eq / ne / gt / ge / lt / le)to treat aggregate operand as **ZERO outer var contribution**(per §5.5 v2 + §2.6 v3)。Do NOT walk aggregate filter atoms here。Correlated outer vars are contributed by their original outer-scope atom independently;aggregate-local vars(target_var + filter-introduced)stay private per C104。
5b. Extend `_infer_var_type_domains`(`where_compile.py:829-861`)to walk aggregate filter atoms recursively for type inference per §2.6b v3 P2。This is a separate concern from `_vars_in_atom`:type domains track value types for cmp safety,not outer-scope membership。Mark aggregate `target_var` as `int` type explicitly(per C102 numeric target)。
6. Add `_compile_aggregate(...)` helper per §5.3 algorithm + §2.5 empty-set guard(min/max/mean prefix `count > 0`)。Return **bare numeric aggregate expression** per §5.3.5 v3 lock。
7. Extend `_compile_cmp_side` per §5.4(aggregate-aware via context kwarg);wrapping decisions(to_string / to_number / raw)applied per §5.3.5 table at call site,not inside `_compile_aggregate`。
8. Wire `_compile_atom` cmp branches(`eq` / `gt`/`ge`/`lt`/`le`)to recognize aggregate operand and route to `_compile_cmp_side` with aggregate context;`ne` route similarly extends `_compile_ne_filter`。Eq branch uses §5.3.5 v3 lock table to decide binding(`to_string` wrap)vs filter(`to_number` / raw)based on `bound_vars` state of non-aggregate side。
9. Write tests `tests/adapters/souffle/test_aggregate_compile.py` per §7 (or extend existing test file)。
10. Update docs(both mandatory per P4 v2 lock):
    - `application/docs/rule.md` adapter status table:Souffle row pending → ✓ + empty-set note。
    - `sdk/docs/03_rules_and_inferences.en.md` §3.2 adapter status row:Deferred → Supported + brief empty-set explanation。
11. Run gates:
    - `PYTHONPATH=src python -m unittest tests.adapters.souffle.test_aggregate_compile tests.adapters.souffle.test_where_compile`(or equivalent existing Souffle suite name)
    - Cross-slice non-regression sweep:T2.3a + T2.3b + T2.1 + T2.2 relevant suites
    - `python -m ruff check src/factgraph/adapters/souffle/ tests/adapters/souffle/`
    - **Souffle binary smoke**(if available):run a small end-to-end aggregate query against actual Souffle binary to verify(a)guard prefix syntax parses,(b)empty-set branch-not-firing behavior。If Souffle binary unavailable in dev env,defer to CI(per existing Souffle test gating convention)。
12. Fill §10 Outcome with exact LOC,test outcomes,empty-set guard implementation status,any Souffle syntax/runtime deviations discovered at impl-time(particularly `mean` aggregator support if version-pinned),follow-up sketch(T2.3.d ProbLog,T2.3.b1/T2.3.e Nit)。

## 9. Docs To Update(v2 P4 lock — both mandatory)

- **`src/factgraph/application/docs/rule.md`** — adapter status table row "Souffle aggregate dispatch pending T2.3.c" → "Souffle aggregate dispatch ✓"。Brief note on min/max/mean empty-set guard semantics(branch-not-firing per C101)。
- **`src/factgraph/sdk/docs/03_rules_and_inferences.en.md`** — §3.2 adapter status table row "Souffle adapter | Deferred to T2.3.c" → "Souffle adapter | Supported(empty min/max/mean follows C101 via `count > 0` guard,branch does not fire)"。**Mandatory in T2.3c** — T2.3b shipped this table row with explicit "Deferred to T2.3.c" pointer;if T2.3c does not flip it,docs become stale immediately upon ship。

## 10. Outcome / Deviations

- Pending。
