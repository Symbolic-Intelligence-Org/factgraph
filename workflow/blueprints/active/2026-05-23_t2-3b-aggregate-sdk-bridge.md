# T2.3b — Aggregate SDK ergonomic + bridge support over T2.3a substrate

- Status: draft
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: task blueprint
- Inputs:
  - Parent essay [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md) §10.6.3 (C99) — 5 aggregate kinds + SDK ergonomic user-facing pattern (`agg_sum`, etc.)
  - Track plan [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md) §1.2 G1-G7,§1.2.5 T2.3a row(S — shipped `477fcccb`),§1.2.6 T2.3b future row
  - Archived T2.3a [2026-05-23_t2-3-aggregate-substrate.md](../archive/2026-05-23_t2-3-aggregate-substrate.md) — substrate IR + validation + per-env eval + raw resolver + application Rule serialization + two-pass var collection。**T2.3a is the foundation T2.3b builds on**
  - Archived T1.2 [2026-05-22_t1-2-dsl-to-application-rule.md](../archive/2026-05-22_t1-2-dsl-to-application-rule.md) — DSL→application Rule bridge precedent;`build_application_rule` shape + `_collect_vars_from_term` + `_canonicalize_vars` baseline
- Outputs / Downstream:
  - 5 user-facing SDK helper functions:`agg_count` / `agg_sum` / `agg_min` / `agg_max` / `agg_mean`
  - `_AggregateRef` DSL value type with comparison dunders(syntactic sugar only;does NOT bypass T2.3a validation)
  - DSL→IR lowering branch for `_AggregateRef` → raw aggregate tuple
  - Bridge support:`_collect_vars_from_term` + `_canonicalize_vars` aggregate-aware extension(consistent with T1.2 + T2.3a two-pass)
  - SDK user-facing docs explaining aggregate usage + **explicit "Souffle/ProbLog adapter aggregate dispatch deferred to T2.3.c/T2.3.d"**
- Related:
  - `src/factgraph/sdk/dsl/expr.py`
  - `src/factgraph/sdk/dsl/application_rule.py`
  - `src/factgraph/sdk/dsl/__init__.py`(if helpers exposed)
  - `src/factgraph/application/protocol/rule.py`(consumed unchanged)
  - `src/factgraph/core/rules/where_ast.py`(consumed unchanged)
  - `src/factgraph/core/rules/where_ast_validate.py`(consumed unchanged)
  - `src/factgraph/core/rules/where_eval.py`(consumed unchanged)
- Related Modules:
  - `src/factgraph/sdk/dsl/expr.py` — adds `_AggregateRef` DSL class + 5 helper functions + DSL→IR lowering branch in `lower_where_atom` or `_lower_compare`。
  - `src/factgraph/sdk/dsl/application_rule.py` — extends `_collect_vars_from_term` + `_canonicalize_vars` for `AggregateAtom` Term-position(per T1.2 + T2.3a consistency)。
  - `src/factgraph/sdk/dsl/__init__.py` — re-export 5 `agg_*` helpers + `_AggregateRef`(or leave un-exported and require explicit `from factgraph.sdk.dsl.expr import agg_count`,per narrow_public_api;decision in §5.2)。
  - `src/factgraph/application/docs/rule.md` — extended with **end-to-end SDK aggregate usage example** + explicit "Python eval works;Souffle/ProbLog adapter support pending T2.3.c/d"。
- Audit Log:
  - [2026-05-23_t2-3b-aggregate-sdk-bridge.audit.md](./2026-05-23_t2-3b-aggregate-sdk-bridge.audit.md)
- Branch: `v0.2.0-blueprint-t2-3b-aggregate-sdk-bridge-2026-05-23`

> **Cross-slice relationship**:T2.3a shipped(`477fcccb`)the **core aggregate substrate**(IR + validation + per-env Python eval + raw resolver + application Rule serialization)but explicitly **deferred SDK ergonomic + bridge** to T2.3b。T2.3a verified via direct application Rule construction with `AggregateAtom` Term-position;**no SDK-side ergonomic path landed yet**。T2.3b closes this user-facing surface gap WITHOUT touching adapters(Souffle / ProbLog aggregate wires remain T2.3.c / T2.3.d)。

## 1. Problem

Parent essay §10.6.3 (C99) describes user-facing aggregate authoring shapes:

```python
where=[
    User(u),
    Var("total") == agg_sum(Order(o).amount, where=[Order(o).buyer == u]),
    Var("total") > 1000,
]
```

T2.3a substrate(`477fcccb`)landed **C99-C105 semantic core**:

- IR `AggregateAtom(kind, target, filter)` + `_AGGREGATE_KINDS` + parse / lower(`where_ast.py:75-102` + `:236+`)
- Validator(`where_ast_validate.py`)— filter restrictions(C100),scoping(C104),target binding rule(P2 §2.5b),numeric target construct(C102)
- Python evaluator(`where_eval.py`)— per-env aggregate computation(C104 correlated),`AggregateNoValue` sentinel(C101),runtime numeric check(C102 runtime),result binding 3-branch(C105),raw aggregate term resolver in cmp/arith paths(C101 NoValue propagation)
- Application Rule(`application/protocol/rule.py`)— serialization for `content_digest` + two-pass var collection(target ALWAYS + filter correlated subset + aggregate-local-only isolated)

**But T2.3a explicitly excluded**:
- **SDK ergonomic helpers**(`agg_count` / `agg_sum` / `agg_min` / `agg_max` / `agg_mean`)
- **`_AggregateRef` DSL type** with comparison dunders
- **DSL → IR lowering** for SDK-authored aggregate
- **Bridge support**(`build_application_rule` does NOT recognize aggregate-containing IR via T2.3a closure;`_collect_vars_from_term` `:181` + `_canonicalize_vars` `:188` don't know `AggregateAtom`)
- **Public docs** for SDK aggregate usage
- **Souffle / ProbLog adapter wires**(deferred to T2.3.c / T2.3.d)

T2.3b closes **(a)-(e)** above but NOT(f)。Users will be able to write `agg_sum(...)` via SDK DSL and have it flow through `build_application_rule` → application Rule with `AggregateAtom` Term-position → T2.3a Python eval works。Souffle / ProbLog execution still unsupported until T2.3.c / T2.3.d。

## 2. Goals

### 2.1 C99 — Add `_AggregateRef` DSL value type(SDK-side proxy)

Add to `src/factgraph/sdk/dsl/expr.py`:

```python
@dataclass(frozen=True)
class _AggregateRef:
    """SDK-side proxy for aggregate expression. Lowers to core AggregateAtom IR.

    Underscore prefix marks it as internal — user code constructs via agg_* helpers.
    """
    kind: str  # in {"count", "sum", "min", "max", "mean"}
    target: Any  # DSL term: LogicVar / Const-like / None (for count)
    filter: tuple[Any, ...]  # DSL atom tuple (frozen for immutability)

    def __eq__(self, other) -> CompareExpr: return CompareExpr("eq", self, other)
    def __ne__(self, other) -> CompareExpr: return CompareExpr("ne", self, other)
    def __gt__(self, other) -> CompareExpr: return CompareExpr("gt", self, other)
    def __ge__(self, other) -> CompareExpr: return CompareExpr("ge", self, other)
    def __lt__(self, other) -> CompareExpr: return CompareExpr("lt", self, other)
    def __le__(self, other) -> CompareExpr: return CompareExpr("le", self, other)
```

**Invariant**:`_AggregateRef` is **pure syntactic sugar**。It does NOT define validation behavior;all validation comes from T2.3a substrate when lowered IR reaches `parse_where_ir_to_ast` + `validate_where_ast`(implicit via `build_application_rule` chain)。

### 2.2 C99 — Add 5 SDK ergonomic helper functions

```python
def agg_count(*, where: list[Any]) -> _AggregateRef:
    """Count of rows matching filter (per outer env)."""
    return _AggregateRef(kind="count", target=None, filter=tuple(where))


def agg_sum(target: Any, *, where: list[Any]) -> _AggregateRef:
    """Sum of target values from rows matching filter (per outer env)."""
    return _AggregateRef(kind="sum", target=target, filter=tuple(where))


def agg_min(target: Any, *, where: list[Any]) -> _AggregateRef:
    """Minimum of target values from rows matching filter (per outer env)."""
    return _AggregateRef(kind="min", target=target, filter=tuple(where))


def agg_max(target: Any, *, where: list[Any]) -> _AggregateRef:
    """Maximum of target values from rows matching filter (per outer env)."""
    return _AggregateRef(kind="max", target=target, filter=tuple(where))


def agg_mean(target: Any, *, where: list[Any]) -> _AggregateRef:
    """Arithmetic mean of target values from rows matching filter (per outer env)."""
    return _AggregateRef(kind="mean", target=target, filter=tuple(where))
```

**Naming + export policy decision(per user Step 4.2 review focus area 1)**:

- 5 function names(`agg_count` / `agg_sum` / `agg_min` / `agg_max` / `agg_mean`)— **match parent essay §10.6.3 verbatim**。No alternative naming considered;parent essay is authoritative for user-facing name conventions。
- Exposed at `factgraph.sdk.dsl.expr` module level(callable via `from factgraph.sdk.dsl.expr import agg_sum`)
- **Promoted into `factgraph.sdk.dsl` package `__init__.py` `__all__`** alongside `Not` / `Pred` / `vars`(per existing function-helper pattern at `sdk/dsl/expr.py:276+`)。Decision rationale:
  - `Not` / `Pred` helpers ARE exposed via `factgraph.sdk.dsl` per `dsl/__init__.py` re-export
  - `agg_*` helpers are equivalent ergonomic DSL surface
  - Not promoting would be inconsistent with `Not` / `Pred` precedent
- **Not promoted to `factgraph.sdk.__init__.py` `__all__` top-level**(per `feedback_narrow_public_api` — top-level `factgraph.sdk` exports should stay minimal;DSL helpers naturally live in `factgraph.sdk.dsl` sub-namespace)
- This is **purely additive** — no rename / replacement of any existing API。**Does NOT trigger M-class decision per §1.2.4 trigger conditions**(verified in §5.6)

### 2.3 C99 — DSL → IR lowering for `_AggregateRef`

Add lowering branch in `lower_where_atom` or `_lower_compare`:

- When user writes `Var("total") == agg_sum(target, where=[...])`,this produces `CompareExpr("eq", Var("total"), _AggregateRef(kind="sum", target=..., filter=[...]))`
- Lowering recognizes `_AggregateRef` as Term-position value
- Recursively lowers `target` + `filter` atoms via existing `lower_term` / `lower_where_atom` paths
- Emits IR tuple shape `(kind_str, target_lowered, filter_ir_list)` as Term-position value within outer CmpAtom IR tuple

**Result**:final IR tuple for the example is

```python
("eq", "$total", ("sum", ("attr_ref", "$o", "amount"), [...filter IR...]))
```

`parse_where_ir_to_ast` then parses the inner `("sum", ...)` tuple as `AggregateAtom` per T2.3a `_parse_aggregate_term`(`where_ast.py:241+`)。

### 2.4 Bridge support — `_collect_vars_from_term` + `_canonicalize_vars` aggregate-aware

Extend `src/factgraph/sdk/dsl/application_rule.py:_collect_vars_from_term`(`:181`):

```python
def _collect_vars_from_term(term, out):
    if isinstance(term, Var):
        out[term.name] = term
        return
    if isinstance(term, Const):
        return
    if isinstance(term, AggregateAtom):  # NEW per T2.3b
        # Match T2.3a application Rule two-pass semantics:
        # target Vars ALWAYS collected;filter Vars require correlated subset filtering
        # but bridge does not yet know `outer_seen_vars` context.
        #
        # Resolution: bridge collects ALL vars within aggregate Term (target + filter).
        # T2.3a application Rule.__post_init__ then runs its independent two-pass
        # algorithm and filters out aggregate-local-only vars before ports validation.
        # This is consistent because:
        # - Bridge is upstream of application Rule construction
        # - Application Rule has its own defense-in-depth (T2.3a v3 P1 algorithm)
        # - Aggregate-local-only vars getting collected here is harmless;they get
        #   filtered out at application Rule's Pass 2 before ports validation
        if term.target is not None:
            _collect_vars_from_term(term.target, out)
        for f_atom in term.filter:
            _collect_vars_from_atom(f_atom, out)  # reuses existing atom traversal
        return
    # ... existing branches ...
```

Extend `_canonicalize_vars` / `_canonicalize_expr`(`:188-193`)similarly:

```python
def _canonicalize_term(term, vars_by_name):
    if isinstance(term, Var):
        return vars_by_name.get(term.name, term)
    if isinstance(term, Const):
        return term
    if isinstance(term, AggregateAtom):  # NEW per T2.3b
        new_target = _canonicalize_term(term.target, vars_by_name) if term.target else None
        new_filter = [_canonicalize_atom(a, vars_by_name) for a in term.filter]
        return AggregateAtom(
            kind=term.kind,
            target=new_target,
            filter=new_filter,
            origin=term.origin,
        )
    # ... existing branches ...
```

**Consistency check(per user Step 4.2 review focus area 3)**:
- T1.2 bridge canonicalization unifies LogicVar instances → core Var by name → so `Var(name="$o")` from filter atoms unifies with same-named outer Vars
- T2.3a application Rule two-pass independently isolates filter-local-only vars from ports
- Bridge collecting ALL aggregate Vars is **safe** because application Rule's downstream Pass 2 filters them

### 2.5 Public docs — SDK aggregate usage + adapter status

Extend `src/factgraph/application/docs/rule.md`:

- **End-to-end aggregate usage example** showing user-facing pattern:
  ```python
  with vars("u", "o", "total") as (u, o, total):
      rule = build_application_rule(
          id="active_users_with_high_spend",
          where=[
              User(u).status == "active",
              total == agg_sum(Order(o).amount, where=[Order(o).buyer == u]),
              total > 1000,
          ],
          ports={"user": u},
      )
  ```
- **Adapter status explicit**(per user Step 4.2 review focus area 4):
  - "Python evaluator supports aggregate execution per env(T2.3a)"
  - "Souffle aggregate body wire **NOT YET LANDED**(deferred to T2.3.c)"
  - "ProbLog `findall/3` + list predicates wire **NOT YET LANDED**(deferred to T2.3.d)"
  - "PyReason aggregate **OUT OF SCOPE**(parent essay §8.4 / C95)"
- Note that **`_AggregateRef` is internal type**;user code uses `agg_*` helpers,not direct construction

### 2.6 G7 pre-impl precondition checks

Per user Step 4.2 review focus area 5:**G7 must verify SDK aggregate IR can be parsed/validated/evaluated by T2.3a substrate,but adapters remain unsupported**。Detailed in §5.6。

## 3. Non-goals

- **No new aggregate kinds beyond 5**(T2.3a / parent §10.6.3 fixed set;parent essay extension candidates `any` / `all` / etc are v1.x+)
- **No core IR changes**(`where_ast.py` `_AGGREGATE_KINDS` / `AggregateAtom` / parse / lower all T2.3a-frozen)
- **No validator changes**(`where_ast_validate.py` T2.3a-frozen — filter restrictions / scoping / target binding / numeric construct all preserved as defense)
- **No Python evaluator changes**(`where_eval.py` T2.3a-frozen — per-env aggregate / NoValue / raw resolver all preserved)
- **No application Rule changes**(`application/protocol/rule.py` T2.3a-frozen — two-pass algorithm / serialization preserved)
- **No Souffle aggregate body wire**(deferred to T2.3.c per blueprint cross-slice + Track plan §1.2.6)
- **No ProbLog `findall/3` + list predicates wire**(deferred to T2.3.d)
- **No PyReason aggregate support**(parent essay §8.4 / C95 explicit)
- **No SDK top-level `__all__` promotion**(`agg_*` helpers go in `factgraph.sdk.dsl` namespace,not `factgraph.sdk` top-level — per narrow_public_api)
- **No M-class decision doc**(no load-bearing decision triggered;naming follows parent essay verbatim,export policy follows existing `Not`/`Pred` precedent)
- **No SDK Quickstart user-facing docs**(application/docs/rule.md is the appropriate landing layer per T1.1 / T2.3a precedent;wider user-facing quickstart deferred until adapter wires ship)

## 4. Current Context

### 4.1 G2 — T2.3a substrate landed verified

`src/factgraph/core/rules/where_ast.py`:

- Line 75:`class AggregateAtom` frozen dataclass
- Line 96:`Term: TypeAlias = Var | Const | AggregateAtom`(Strategy A restructure complete)
- Line 102:`_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}`
- Line 236+:`_parse_aggregate_term(raw, *, path)` recognizes aggregate tuples within CmpAtom IR

`src/factgraph/core/rules/where_ast_validate.py` (T2.3a) — filter restrictions / scoping / target binding rule / numeric target construct + `AggregateValidationError` / `AggregateVariableScopeError` all shipped。

`src/factgraph/core/rules/where_eval.py` (T2.3a) — per-env aggregate evaluator + `AggregateNoValue` + raw aggregate resolver in cmp/arith paths + all helpers aggregate-aware。

`src/factgraph/application/protocol/rule.py:185+` (T2.3a) — `isinstance(term, AggregateAtom)` branches in `_serialize_term` + `_collect_term_vars` + `_validate_aggregate_term` + two-pass algorithm。

### 4.2 G2 — SDK DSL expr.py current shape

`src/factgraph/sdk/dsl/expr.py`:

- Line 134:`class BinaryExpr` for arith
- Line 205:`class CompareExpr` for comparisons (op / left / right)
- Line 217:`class HeadCall`
- Line 235:`build_entity_dsl_call`(EntityMeta dispatch)
- Line 276:`def Not(body)` — **precedent for function-helper exposing DSL value**
- Line 288:`def Pred(pred_id, *terms)` — **another precedent**
- **No `agg_*` helpers shipped**(verified by `grep "^def agg_" src/factgraph/sdk/` returning empty)
- **No `_AggregateRef` type shipped**

### 4.3 G2 — Bridge `_collect_vars_from_term` + `_canonicalize_vars` baseline

`src/factgraph/sdk/dsl/application_rule.py`:

- Line 54:`where_expr = _canonicalize_vars(parse_where_ir_to_ast(where_ir))`(canonicalization runs post-parse,sees core AST including `AggregateAtom`)
- Line 159-174:`_collect_vars_from_atom` walks Atom variants;**no `AggregateAtom` branch**(would only encounter via Term-position in `CmpAtom.lhs`/`.rhs`)
- Line 181:`def _collect_vars_from_term(term, out)` — currently handles `Var`(stores into `out`)and `Const`(no-op)。**No `AggregateAtom` branch**
- Line 188-193:`_canonicalize_vars(expr)` + `_canonicalize_expr(expr, vars_by_name)` — recursive on WhereExpr structure。**Needs new Term-canonical branch for AggregateAtom**

**Without T2.3b extension**:if user constructs IR with aggregate in CmpAtom Term and feeds to `build_application_rule`,then:
- `parse_where_ir_to_ast` succeeds(T2.3a)
- `_canonicalize_vars` walks WhereExpr → CmpAtom → `_canonicalize_term(term)` for lhs/rhs → falls through to "unsupported term" or silently passes through unchanged depending on implementation
- `_collect_vars_from_term` similarly drops aggregate Vars
- Bridge canonicalization incomplete;Var identity may not unify across outer / aggregate filter scopes

T2.3b extends these helpers to recurse into `AggregateAtom` Term properly。

### 4.4 G2 — `agg_*` namespace clean

`grep "^def agg_\|^agg_count\|^agg_sum" src/factgraph/sdk/` returns empty。No name collision risk。

### 4.5 G2 — `Not` / `Pred` export pattern as precedent

`Not` and `Pred` are function-helpers in `expr.py` and re-exported via `factgraph.sdk.dsl.__init__`。`agg_*` should follow same pattern:`expr.py` definition + `__init__.py` re-export。

## 5. Proposed Shape

### 5.1 `_AggregateRef` SDK DSL value type

Per §2.1 — frozen dataclass with 5-op comparison dunders。Underscore prefix marks internal status;user code goes through `agg_*` helpers。

**Does NOT bypass T2.3a validation**(per user Step 4.2 review focus area 2):

- `_AggregateRef` only carries DSL atoms in `filter` and DSL Term in `target`。It does NOT run any validation。
- All validation happens when IR reaches `parse_where_ir_to_ast` → `validate_where_ast` → application Rule `__post_init__`(all T2.3a layers)。
- Construct time:`agg_sum(target, where=[...])` returns `_AggregateRef` no questions asked。
- Validation time:`build_application_rule(..., where=[..., agg_sum(target, where=[...]) compared, ...], ...)`triggers:
  - `lower_where` → IR tuples(T2.3b lowering)
  - `parse_where_ir_to_ast` → core AST(T2.3a)
  - `validate_where_ast` → C100 filter restrictions / C104 scoping / P2 target binding / C102 numeric construct(T2.3a)
  - `application Rule.__post_init__` → two-pass var collection + serialization(T2.3a)
  - **All T2.3a invariants enforced through this path**

### 5.2 5 helpers — name + export

Per §2.2 — 5 `agg_*` helpers exposed at `factgraph.sdk.dsl.expr` + re-exported at `factgraph.sdk.dsl.__init__`(following `Not` / `Pred` precedent)。

**Export decision rationale**:
- Parent essay §10.6.3 example uses `agg_sum(...)` etc bare — implying these should be top-level callable in dsl namespace
- `Not(body)` precedent in same file — same pattern
- NOT in `factgraph.sdk` top-level `__all__` — narrow_public_api keeps top-level minimal

### 5.3 DSL → IR lowering

Per §2.3 — new branch in lowering chain。

Existing `_lower_compare`(`expr.py:357+`)handles `CompareExpr` containing AttrRef / Var / Const operands。Extend to handle `_AggregateRef` operand:

```python
def _lower_compare(expr: CompareExpr, bindings, *, temp_seq) -> list:
    # ... existing AttrRef / Var / Const handling ...

    # NEW: aggregate operand handling
    if isinstance(expr.left, _AggregateRef) or isinstance(expr.right, _AggregateRef):
        # Lower aggregate Term to IR tuple recursively
        # Then emit outer CmpAtom IR tuple with aggregate tuple as Term value
        return _lower_compare_with_aggregate(expr, bindings, temp_seq=temp_seq)

    # ... rest of existing logic ...


def _lower_aggregate_ref(ref: _AggregateRef, bindings, *, temp_seq) -> tuple:
    """Lower _AggregateRef to ('kind', target_lowered, filter_ir_list) tuple."""
    target_lowered = _lower_term(ref.target, bindings) if ref.target else None
    filter_ir = []
    for atom in ref.filter:
        # Reuse existing atom lowering(handles ExistsAtom / CompareExpr / etc)
        filter_ir.extend(_lower_atom(atom, bindings, temp_seq=temp_seq))
    return (ref.kind, target_lowered, filter_ir)


def _lower_compare_with_aggregate(expr, bindings, *, temp_seq) -> list:
    """Lower CompareExpr where one or both operands are _AggregateRef."""
    if isinstance(expr.left, _AggregateRef):
        left_term = _lower_aggregate_ref(expr.left, bindings, temp_seq=temp_seq)
    else:
        left_term = _lower_term(expr.left, bindings)

    if isinstance(expr.right, _AggregateRef):
        right_term = _lower_aggregate_ref(expr.right, bindings, temp_seq=temp_seq)
    else:
        right_term = _lower_term(expr.right, bindings)

    # Emit outer CmpAtom IR
    return [(expr.op, left_term, right_term)]
```

**Filter atom lowering**:reuses existing `_lower_atom` for `ExistsAtom` / `CompareExpr` / etc。If filter atom contains `_AggregateRef`(nested aggregate)— **parent C100 prohibits nested aggregation**;T2.3a validator catches this construct-time。T2.3b lowering does NOT need explicit reject(layered defense)。

### 5.4 Bridge `_collect_vars_from_term` + `_canonicalize_vars` extension

Per §2.4 — extend both functions for `AggregateAtom` Term-position。

**Var collection — ALL vars within aggregate Term collected here(target + filter)**。Rationale documented in §2.4:bridge is upstream;T2.3a application Rule's Pass 2 filters out aggregate-local-only vars before ports validation。Bridge over-collecting is safe and consistent with defense-in-depth。

**Canonicalization — recursive into AggregateAtom**:target term + filter atoms。Preserves Var name unification across outer / aggregate scopes(per T1.2 baseline pattern)。

### 5.5 Public docs

Per §2.5 — extend `application/docs/rule.md` with:
- End-to-end example using `agg_sum(...)`
- Adapter status table:Python eval ✓ / Souffle deferred T2.3.c / ProbLog deferred T2.3.d / PyReason out-of-scope
- Note `_AggregateRef` is internal;use `agg_*` helpers

### 5.6 G7 pre-impl precondition

Before code changes,verify:

1. **T2.3a substrate landed**:`grep "_AGGREGATE_KINDS\|class AggregateAtom" src/factgraph/core/rules/where_ast.py` returns non-empty;`_parse_aggregate_term` exists in `where_ast.py`。
2. **SDK aggregate ergonomic empty**(this slice's scope to add):`grep "^def agg_\|^class _AggregateRef" src/factgraph/sdk/dsl/expr.py` returns empty。
3. **Bridge currently lacks aggregate-aware extension**:`_collect_vars_from_term` and `_canonicalize_vars/expr` in `sdk/dsl/application_rule.py` do NOT recognize `AggregateAtom`(verified by inspection — would need new branches per §2.4)。
4. **Adapter aggregate dispatch still absent**:`grep "AggregateAtom\|_AGGREGATE_KINDS" src/factgraph/adapters/{souffle,problog,pyreason}/` returns empty(per T2.3a Non-goal + Track plan)。
5. **Round-trip smoke check**:directly construct an `AggregateAtom` IR tuple,parse via `parse_where_ir_to_ast`,validate via `validate_where_ast`,evaluate via Python `where_eval` — **all succeed**。Confirms T2.3a substrate is healthy for T2.3b to layer SDK ergonomic over。If smoke fails → T2.3a regression or undocumented limitation → STOP and amend blueprint。
6. **Naming + export policy double-check**:no `agg_*` collisions in `factgraph.sdk` namespace;`Not` / `Pred` export precedent applies cleanly(check `factgraph/sdk/dsl/__init__.py` for existing pattern)。

**If check #1-4 fail → amend blueprint。**
**If check #5 fails → STOP impl,amend blueprint(possibly T2.3a regression bug — escalate to T2.3a re-open if needed)。**
**If check #6 surfaces naming conflict → load-bearing decision triggers M-class escalation,open Stage 2 decision doc。**

### 5.7 M-class trigger gate(per user Step 4.2 review focus area 1)

Per Track plan §1.2.4,T2.3b would upgrade S → M if any of these triggers fire:

| Trigger | T2.3b status | Resolution |
|---|---|---|
| Cross-file commitment mismatch | None — all 7 commitments already shipped in T2.3a substrate;T2.3b only exposes via SDK | NO |
| PENDING项 must resolve first | None — C99 already locked + T2.3a shipped | NO |
| Sub-slice count > Track plan §2 prediction × 2 | Track plan §1.2.6 lists T2.3a/b/c/d as 4 sub-slices,within prediction | NO |
| Public API rename / replacement ≥ 3 caller sites | **NO** — `agg_*` are NEW functions,not rename/replacement | NO |
| Design vs shipped ≥ 3 commitments conflict | None — purely additive over T2.3a | NO |
| Cite drift > 30% | TBD by reviewer's Step 4.2 spot-check | TBD |

**Conclusion**:**T2.3b does NOT trigger M-class escalation**。S-class lightweight cadence applies。

### 5.8 Size estimate

| Component | Est. LOC |
|---|---|
| `expr.py`:`_AggregateRef` class + 5 helpers + dunders | ~80 |
| `expr.py`:`_lower_aggregate_ref` + `_lower_compare_with_aggregate` lowering branch | ~50 |
| `application_rule.py`:`_collect_vars_from_term` AggregateAtom branch | ~20 |
| `application_rule.py`:`_canonicalize_term` AggregateAtom branch | ~30 |
| `sdk/dsl/__init__.py`:re-export 5 helpers | ~10 |
| `application/docs/rule.md`:SDK aggregate usage section + adapter status | ~80 |
| Tests | ~200 |
| **Total** | **~470 LOC** |

**S-class compliant**(within ~300 LOC core + ~200 tests = ~500 budget)。More compact than T2.3a(~1280 LOC)because design space is bounded — only exposing T2.3a substrate via SDK ergonomic + bridge,no new semantic choices。

## 6. Boundaries And Invariants

- **Substrate-frozen invariant**:T2.3a substrate(core IR / validation / Python eval / application Rule)is **UNTOUCHED in T2.3b**。All scope diff for T2.3a files must be 0 LOC verified by acceptance scope diff。
- **DSL-only-via-helpers invariant**:user code does NOT directly construct `_AggregateRef`(underscore prefix indicates internal)。Public API surface is the 5 `agg_*` functions only。
- **Bridge defense-in-depth invariant**:T2.3a application Rule Pass 2 algorithm runs independently of bridge collection。Bridge over-collecting filter-local vars is safe because application Rule filters them out before ports validation。
- **No bypass invariant**:`_AggregateRef` cannot bypass T2.3a validation。All validation triggers via lowered IR → `parse_where_ir_to_ast` + `validate_where_ast` + application Rule `__post_init__` chain。
- **Adapter-deferral invariant**:Souffle / ProbLog adapter aggregate dispatch UNCHANGED — verified by scope diff in §7。
- **Cross-slice contract invariant**:
  - T1.1 `_ALLOWED_ATOM_TYPES` unchanged
  - T1.2 bridge core unchanged except `_collect_vars_from_term` / `_canonicalize_vars` gain `AggregateAtom` branches(additive)
  - T2.1 ne adapter dispatch unchanged
  - T2.2 ArithExpr substrate unchanged
  - T2.3a substrate UNCHANGED(all 5 layers frozen)
  - ProbLog hygiene boundary unchanged
  - fixture cleanup unchanged
- **No M-class trigger invariant**:T2.3b stays S-class per §5.7 trigger analysis;Stage 2 decision doc NOT opened。

## 7. Acceptance

- [ ] G1/G4 traceability:every §2 goal cites C99 / §10.6.3 or specific user-facing rationale
- [ ] G7 pre-impl precondition runs and is recorded in audit log **before** code implementation(per T2.2 / fixture cleanup / T2.3a timing improvement)
- [ ] G7 #5 smoke check passes:direct AggregateAtom IR tuple round-trip through parse → validate → eval succeeds(confirms T2.3a substrate healthy)
- [ ] G7 #6 naming + export collision check passes:no `agg_*` conflicts;`Not`/`Pred` precedent applies
- [ ] `_AggregateRef` class added to `sdk/dsl/expr.py` with 5 helpers + comparison dunders
- [ ] `factgraph.sdk.dsl` namespace exposes 5 `agg_*` helpers(re-export via `__init__.py`)
- [ ] DSL → IR lowering branch handles `_AggregateRef` operand in `CompareExpr` lhs / rhs
- [ ] Bridge `_collect_vars_from_term` recognizes `AggregateAtom` Term-position(recursive into target + filter)
- [ ] Bridge `_canonicalize_vars/expr/term` recursively canonicalizes within `AggregateAtom` Term
- [ ] **End-to-end smoke**:user code `build_application_rule(where=[..., total == agg_sum(target, where=[...]), ...], ports={...})` produces valid application Rule with `AggregateAtom` Term-position;Python eval gives correct per-env aggregate result
- [ ] **T2.3a validation triggers via SDK path**:invalid aggregate via SDK helper raises `AggregateValidationError` / `AggregateVariableScopeError` from T2.3a validator(filter restrictions / scoping / target binding / numeric construct)
- [ ] **Application Rule two-pass isolation still works**:filter-local-only var in SDK-authored aggregate does NOT enter ports validation set via bridge over-collection
- [ ] `application/docs/rule.md` extended with SDK aggregate usage example + explicit adapter status(Souffle/ProbLog deferred,PyReason out-of-scope)
- [ ] **Scope diff verifies T2.3a substrate files 0-touch**:`where_ast.py` / `where_ast_validate.py` / `where_eval.py` / `application/protocol/rule.py` all 0 lines changed by T2.3b
- [ ] **Scope diff verifies adapter files 0-touch**:`src/factgraph/adapters/{souffle,problog,pyreason}/` all 0 lines changed
- [ ] Cross-slice non-regression:T1.1 + T1.2 + T2.1 + ProbLog hygiene + T2.2 + fixture cleanup + T2.3a tests all pass(85+ tests baseline from T2.3a)
- [ ] Ruff clean on touched source + test files
- [ ] Sacred `master 562c7419` unchanged
- [ ] Dirty 4 M + 1 untracked preserved
- [ ] **No M-class escalation triggered**(per §5.7 trigger gate confirmation)

## 8. Implementation Plan

1. **G7 pre-impl precondition**:run §5.6 checks 1-6;record in audit log **before** impl commit(per T2.2 / fixture cleanup / T2.3a timing improvement)。If check #1-4 fail → amend blueprint。If check #5 fails → STOP,investigate T2.3a regression。If check #6 surfaces naming conflict → M-class escalation。
2. **SDK ergonomic layer**:add `_AggregateRef` class + 5 `agg_*` helpers to `sdk/dsl/expr.py`(reuse `Not`/`Pred` pattern)。
3. **DSL → IR lowering**:add `_lower_aggregate_ref` + extend `_lower_compare` to handle `_AggregateRef` operand。
4. **Bridge layer**:extend `_collect_vars_from_term` + `_canonicalize_term` in `application_rule.py` for `AggregateAtom` Term-position。
5. **SDK __init__ re-export**:add 5 helpers to `factgraph.sdk.dsl.__init__.py` `__all__`(following `Not`/`Pred` precedent)。
6. **Docs**:extend `application/docs/rule.md` with SDK aggregate usage section + adapter status table。
7. **Tests**:add new test file(or extend existing T2.3a tests):
   - `_AggregateRef` construction + dunders produce CompareExpr correctly
   - 5 helper functions return `_AggregateRef` with correct shape
   - DSL → IR lowering produces correct tuple shape
   - Bridge `build_application_rule(where=[...agg_sum(...)...])` produces valid application Rule
   - Invalid filters trigger T2.3a `AggregateValidationError`(filter restrictions)
   - Invalid scoping triggers T2.3a `AggregateVariableScopeError`(filter-local leak)
   - Filter-local-only var in SDK-authored aggregate NOT in ports
   - End-to-end Python eval gives correct per-env aggregate result(use T2.3a per-env correlated test pattern adapted to SDK)
8. **Run gates**:
   - `PYTHONPATH=src python -m unittest tests.sdk.dsl.test_aggregate_ergonomic tests.sdk.dsl.test_application_rule tests.application.protocol.test_rule_aggregate tests.core.rules.test_aggregate_eval`
   - Cross-slice non-regression
   - `python -m ruff check src/factgraph/sdk/dsl/ tests/sdk/dsl/`
9. **Fill §10 Outcome** with exact LOC,test outcomes,deviations,follow-up sketch(T2.3.c Souffle / T2.3.d ProbLog)。

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md` — extend with **SDK aggregate usage end-to-end example** + **adapter status table**(Python ✓ / Souffle deferred T2.3.c / ProbLog deferred T2.3.d / PyReason out-of-scope)+ note `_AggregateRef` internal status。
- Track plan §1.2.5 retroactive table — add T2.3b row after archive(via memory consolidation slice or batch labeling)。
- No SDK Quickstart user-facing docs change(application/docs/rule.md is the appropriate landing layer per T1.1 / T2.3a precedent;wider quickstart deferred until adapter wires ship)。

## 10. Outcome / Deviations

- Pending。
