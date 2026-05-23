# T2.3 — AggregateExpr substrate (IR + Python eval + SDK ergonomic)

- Status: draft
- Created: 2026-05-23
- Last Updated: 2026-05-23
- Authority: task blueprint
- Inputs:
  - Parent essay [rule-expression-and-proof-attempt.zh.md](../../design/design-points/active/rule-expression-and-proof-attempt.zh.md) §10.6.3 (C99) / §10.6.4 (C100) / §10.6.5 (C101) / §10.6.6 (C102) / §10.6.7 (C103) / §10.6.8 (C104) / §10.6.9 (C105) — 7 commitments lock AggregateExpr semantics.
  - Parent essay §8.8 — per-engine AggregateExpr lowering strategy (deferred to T2.3b/c sub-slices).
  - Track plan [rule-expression-and-proof-track-plan.zh.md](../../design/design-points/active/rule-expression-and-proof-track-plan.zh.md) §1.2 G1-G7, §1.2.6 T2.3 row(S → 可能 M).
  - Archived T2.2 [2026-05-23_t2-2-arith-expr.md](../archive/2026-05-23_t2-2-arith-expr.md) — adapter parity pattern + builtin substrate precedent for arithmetic.
  - Archived T1.1 [2026-05-22_t1-1-rule-class-additive.md](../archive/2026-05-22_t1-1-rule-class-additive.md) — application Rule.where stores core AST atoms.
- Outputs / Downstream:
  - Core IR `AggregateAtom` type + parsing + IR-tuple round-trip.
  - Core validation:filter clause restrictions(C100)+ variable scoping(C104)+ numeric target type construct-time(C102 construct half).
  - Python evaluator:5 kinds(`count`/`sum`/`min`/`max`/`mean`)+ `AggregateNoValue` sentinel + empty set(C101)+ runtime numeric target(C102 runtime half)+ result binding(C105).
  - SDK DSL ergonomic helpers:`agg_count` / `agg_sum` / `agg_min` / `agg_max` / `agg_mean`.
  - DSL → application Rule bridge:passthrough via existing `lower_where` + `parse_where_ir_to_ast`.
  - Foundation for T2.3b (Souffle aggregate body wire) + T2.3c (ProbLog findall + list predicates) follow-up slices.
- Related:
  - `src/factgraph/core/rules/where_ast.py`
  - `src/factgraph/core/rules/where_ast_validate.py`
  - `src/factgraph/core/rules/where_eval.py`
  - `src/factgraph/sdk/dsl/expr.py`
  - `src/factgraph/sdk/dsl/application_rule.py`
  - `src/factgraph/application/protocol/rule.py`
- Related Modules:
  - `src/factgraph/core/rules/where_ast.py` — needs new `AggregateAtom` type + parse / lower + tag set.
  - `src/factgraph/core/rules/where_ast_validate.py` — needs aggregate filter restrictions + variable scoping + numeric target type construct-time validation.
  - `src/factgraph/core/rules/where_eval.py` — needs aggregate evaluator function + `AggregateNoValue` sentinel + runtime numeric target check.
  - `src/factgraph/sdk/dsl/expr.py` — needs 5 ergonomic helper functions (`agg_count` / `agg_sum` / `agg_min` / `agg_max` / `agg_mean`) + IR shape returned by each helper.
  - `src/factgraph/sdk/dsl/application_rule.py` — bridge passthrough (existing `lower_where` + `parse_where_ir_to_ast` chain should automatically handle new aggregate IR once `where_ast.py` parses it).
  - `src/factgraph/application/protocol/rule.py` — T1.1 allowed atom kinds may need `AggregateAtom` added to allowlist(or aggregate becomes a value-producing form embedded inside `CmpAtom` and NOT a top-level atom — clarified in §5).
- Audit Log:
  - [2026-05-23_t2-3-aggregate-substrate.audit.md](./2026-05-23_t2-3-aggregate-substrate.audit.md)
- Branch: `v0.2.0-blueprint-t2-3-aggregate-substrate-2026-05-23`

## 1. Problem

Parent essay §10.6.3-§10.6.9 defines `AggregateExpr` as a **value-producing expression** that appears in comparison atom LHS / RHS, with 5 kinds (`count` / `sum` / `min` / `max` / `mean`), filter clause restrictions, empty-set / `AggregateNoValue` semantics, numeric target type constraints, snapshot semantics, variable scoping rules, and result binding behavior.

Verified shipped substrate (per G2 source-grep audit):

- `src/factgraph/core/rules/where_ast.py:95-96` lists only `_CMP_OPS = {"eq", "ne", "gt", "ge", "lt", "le"}` and `_BUILTIN_TAGS = {"add", "sub", "neg", "addc", "mulc"}` — **no aggregate kinds**.
- `src/factgraph/core/rules/where_ast.py` defines no `AggregateAtom` type (only `PredAtom` / `RuleRefAtom` / `CmpAtom` / `InAtom` / `BuiltinAtom` / `NotAtom`).
- `src/factgraph/core/rules/where_ast_validate.py` has no aggregate validation function.
- `src/factgraph/core/rules/where_eval.py` has no aggregate evaluator function.
- `src/factgraph/adapters/{souffle,problog,pyreason}/` adapter modules have no `AggregateAtom` dispatch.

**100% genuinely new substrate.** Unlike T2.2 (where ArithExpr substrate was already 5 builtin tags shipped in core/Souffle/Python and only ProbLog parity was missing), T2.3 has **nothing to build on** — every layer needs aggregate support added net-new.

## 2. Goals

### 2.1 C99 — Add `AggregateAtom` IR type + parse / lower / tag set

Add to `src/factgraph/core/rules/where_ast.py`:

- New `_AGGREGATE_KINDS = {"count", "sum", "min", "max", "mean"}` constant.
- New `AggregateAtom` frozen dataclass with fields `(kind, target, filter, origin)`:
  - `kind: str` in `_AGGREGATE_KINDS`
  - `target: Term | None`(`count` has `target=None`;`sum`/`min`/`max`/`mean` carry a numeric/orderable target term)
  - `filter: list[Atom]`(flat list of allowed atom kinds per C100)
- IR tuple shape: `(kind, target_term, filter_ir_list)` parses to `AggregateAtom`.
- `parse_where_ir_to_ast` extended to recognize aggregate tags.
- `lower_ast_to_where_ir` extended to round-trip `AggregateAtom`.

### 2.2 C99 — `AggregateExpr` as value-producing expression in comparison LHS/RHS

`AggregateAtom` is NOT a top-level atom. It appears as **`CmpAtom.lhs` or `CmpAtom.rhs` value** (mirrors `BuiltinAtom` value-producing pattern from T2.2). Top-level `where` list contains `CmpAtom("eq"|"gt"|...)` whose one side is `AggregateAtom`. Parent §10.6.3 lock: "agg 自身无 truth value(true/false 来自包裹 comparison 或 eq binding)".

To represent this, `CmpAtom.lhs` / `.rhs` Term type is extended to allow `AggregateAtom` value (in addition to `Var` / `Const`). This is consistent with how T2.2 ArithExpr `BuiltinAtom` appears in comparison sides — but T2.2 used multi-atom lowering (BuiltinAtom + CmpAtom). T2.3 should clarify whether aggregate uses same multi-atom pattern or embedded-value pattern. **Resolved in §5.1**.

### 2.3 C100 — Filter clause validation (construct-time)

Add to `src/factgraph/core/rules/where_ast_validate.py`:

- `_validate_aggregate_filter(filter_atoms)` enforcing:
  - Filter is flat `list[Atom]` (no `OrExpr` / no nested aggregation).
  - Allowed atom kinds in filter top-level: `pred` / `eq` / `ne` / `gt` / `ge` / `lt` / `le` / `in` / `not`(9 scalar kinds from §10.1).
  - Forbidden in filter top-level: `RuleRefAtom` / nested `AggregateAtom` / `BuiltinAtom`(ArithExpr) in scalar comparison position.
  - `not` body recursion limit: `not` body may contain `pred` / `eq` / `ne` / `gt` / `ge` / `lt` / `le` / `in`(8 kinds);**no** nested `not`,**no** `OrExpr`,**no** `AggregateAtom`,**no** `BuiltinAtom`,**no** `RuleRefAtom`.
  - Violations → `AggregateValidationError` raised construct-time.

### 2.4 C104 — Variable scoping validation (construct-time)

Add to `where_ast_validate.py`:

- `_validate_aggregate_scoping(aggregate_atom, outer_bound_vars)` enforcing:
  - Filter atoms may reference **correlated** vars(already bound in outer Rule.where context)— OK.
  - Filter atoms may introduce **aggregate-local** vars(first appearance in filter)— **do not leak** to outer env.
  - Detect leak attempts:if filter introduces a Var name that does not appear in outer Rule.where context AND the test asserts that name is bound outside the aggregate after the aggregate → reject.
  - Violations → `AggregateVariableScopeError` raised construct-time.

Note:specific algorithm tightened in §5.

### 2.5 C102 — Numeric target type validation (construct + runtime)

Construct-time(`where_ast_validate.py`):

- For `kind in {"sum", "mean"}`:if `target` is `Const` with non-numeric value(string / bool / None / collection)→ `AggregateValidationError`.
- For `kind in {"sum", "mean"}` with `target` as `Var` or `AttrRef`-equivalent → defer to runtime check(static type not known).
- `count` ignores target type(target = None).
- `min` / `max` accept numeric **or** orderable types statically;runtime checks defer.

Runtime(`where_eval.py`):

- During aggregate evaluation,for each matched row's target value:
  - `sum` / `mean`:target must be `int` / `float`(not `bool`,not `str`,etc).Non-numeric → atom violated,not process exception(parent §10.6.6 explicit "不污染 env,不中断其他 env").
  - `min` / `max`:target must support `<` comparison;violations → atom violated.

### 2.6 C101 — Empty set + `AggregateNoValue` sentinel

Add to `where_eval.py`:

- New module-level `AggregateNoValue` sentinel:singleton class instance,distinguishable from `None`.
- Empty set behavior(no rows match filter):
  - `count` → returns `0`(int)
  - `sum` → returns `0`(int)
  - `min` / `max` / `mean` → returns `AggregateNoValue`
- `AggregateNoValue` propagation:
  - Result binding(C105):`Var("v") == AggregateNoValue` → atom violated,v stays unbound.
  - Comparison(`<` / `>` / `==` / `!=` between AggregateNoValue and anything)→ atom violated.
  - `ArithExpr` operand is `AggregateNoValue` → result also `AggregateNoValue`(propagation per parent §10.6.5).
  - JSON serialization marker:`{"__aggregate_no_value__": true}`(per parent §10.6.5).

### 2.7 C103 — Snapshot semantics (matched_count = view-projected fact rows)

In Python evaluator,aggregate matching iterates **view-projected fact rows** within the current evaluator context.matched_count = number of rows that satisfy the filter,not ledger-raw assertion count.

For this S-class slice scope:since Python evaluator does not yet ship multi-row aggregation harness, the implementation uses the env-list iteration mechanism already in place for atom evaluation.parent §10.6.7 lock is honored conceptually;exact semantics depend on Python eval harness extensions(may surface during impl).

### 2.8 C105 — Result binding semantics

Add to `where_eval.py`:

- For `("eq", Var("v"), aggregate_atom)` pattern(or symmetric):
  - Compute aggregate result(int / float / `AggregateNoValue`).
  - If result is `AggregateNoValue` → atom violated,v stays unbound,env unchanged.
  - Elif v is unbound in env → bind v = result.
  - Elif v is bound → equality check;mismatch → atom violated.
- For comparison atoms(`gt` / `ge` / `lt` / `le` / `ne` / `eq`)other than binding:
  - Compute aggregate result.
  - If result is `AggregateNoValue` → atom violated.
  - Else perform comparison.

### 2.9 SDK DSL ergonomic helpers

Add to `src/factgraph/sdk/dsl/expr.py`:

- 5 helper functions:
  ```python
  def agg_count(target=None, *, where: list[Any]) -> AggregateExprRef: ...
  def agg_sum(target, *, where: list[Any]) -> AggregateExprRef: ...
  def agg_min(target, *, where: list[Any]) -> AggregateExprRef: ...
  def agg_max(target, *, where: list[Any]) -> AggregateExprRef: ...
  def agg_mean(target, *, where: list[Any]) -> AggregateExprRef: ...
  ```
- Returns a DSL-side `AggregateExprRef` value that supports comparison dunders(`==` / `>` / etc)to produce `CompareExpr` with aggregate ref as operand.
- DSL → IR lowering:`AggregateExprRef` lowers to IR tuple shape that `parse_where_ir_to_ast` parses back to `AggregateAtom`.
- `lower_where` chain handles aggregate ref naturally(no special-case if helper produces lowerable form).

### 2.10 Bridge passthrough verification

`src/factgraph/sdk/dsl/application_rule.py:build_application_rule` chain:

- Existing `lower_where(dsl_where) → IR tuples → parse_where_ir_to_ast → core AST` should automatically handle aggregate IR once where_ast supports it.
- Verify no changes needed beyond ensuring `AggregateAtom` flows through `_serialize_atom` for `content_digest`(in T1.1 application Rule).Add `AggregateAtom` serialization branch if missing.

### 2.11 Application Rule allowlist (T1.1 cross-slice contract)

T1.1 archived blueprint locks allowed atom kinds for `Rule.where`:`PredAtom` / `CmpAtom` / `InAtom` / `BuiltinAtom` / `NotAtom`(reject `RuleRefAtom`).

T2.3 design:**`AggregateAtom` does NOT appear as top-level `Rule.where` element** — it only appears as `CmpAtom.lhs` / `.rhs` value(per C99 "agg 自身无 truth value")。So T1.1 allowlist **does not need extension**.But `CmpAtom` lhs/rhs Term type extension to allow `AggregateAtom` is required.

## 3. Non-goals

- **No Souffle aggregate body wire**(deferred to T2.3b sub-slice).Souffle has native `count`/`sum`/`min`/`max`/`mean` aggregate syntax;wire is ~150 LOC per parent §8.8 plus tests.
- **No ProbLog `findall/3` + list predicates wire**(deferred to T2.3c sub-slice).ProbLog needs `findall(...,List)` + `length(List,Count)` / `sum_list` / `min_list` / `max_list` + custom mean(`sum/count + div`)+ AggregateNoValue handling;~150 LOC plus tests.
- **No PyReason aggregate support**(parent essay §8.4 / C95 explicit defer — Form 2 independent design).
- **No new aggregate kinds beyond 5**(parent essay §10.6.3 explicit fixed set;`any` / `all` / `isSubset` / `join` / `first` / `last` are listed as v1.x extension candidates in parent §10.2).
- **No OR group in filter clause**(parent C100 explicit flat list).
- **No nested aggregate**(aggregate within aggregate filter)— C100 explicit.
- **No `BuiltinAtom`(ArithExpr)inside filter scalar comparison position** — C100 explicit "filter atoms 必须纯 scalar 比较,LHS/RHS 仅 Var / Literal / AttrRef".
- **No `RuleRefAtom` inside aggregate filter** — C100 + parent C9.
- **No nested `not` in `not` body within aggregate filter** — C100 explicit recursion limit.
- **No `AggregateExpr` ArithExpr coupling**(e.g.,`agg_sum(x) + 1 > 5` lowering)beyond what existing `BuiltinAtom` ArithExpr lowering handles naturally。If `agg_sum(...) + 1` requires special lowering,defer.
- **No implicit cast / parse**(string-to-numeric)for sum/mean target — parent §10.5 explicit v1.x deferred。
- **No `mod` / `%` / `**` operator integration with aggregate** — out of T2.3 scope。

## 4. Current Context

### 4.1 G2/G3 — `where_ast.py` shipped substrate empty

`src/factgraph/core/rules/where_ast.py:95-96`:

```python
_CMP_OPS = {"eq", "ne", "gt", "ge", "lt", "le"}
_BUILTIN_TAGS = {"add", "sub", "neg", "addc", "mulc"}
```

No aggregate kinds.No `AggregateAtom` dataclass.No aggregate parse branch.

`src/factgraph/core/rules/where_ast.py:77` defines `Atom: TypeAlias = PredAtom | RuleRefAtom | CmpAtom | InAtom | BuiltinAtom | NotAtom` — extension point for adding `AggregateAtom` to the alias(but per §2.11 aggregate appears as Term-position value within `CmpAtom`,not as top-level Atom — so this alias may not need extension).

`src/factgraph/core/rules/where_ast.py:31` defines `Term: TypeAlias = Var | Const` — this **does** need extension to include `AggregateAtom` (or a wrapper type) for aggregate-in-comparison positioning.Tightened in §5.1.

### 4.2 G2/G3 — `where_ast_validate.py` shipped validation has no aggregate path

`src/factgraph/core/rules/where_ast_validate.py:33-34` defines `_CMP_OPS` and `_CMP_FILTER_OPS`(same as where_ast.py).No aggregate validation function exists.

`_validate_builtin_shape(atom)`(verified during T2.2 review,line ~254-278)covers `add`/`sub`/`neg`/`addc`/`mulc`.No equivalent `_validate_aggregate_shape`。

`_validate_atom_dataflow` / `_validate_and_dataflow` are existing data flow validators for bound var tracking.New aggregate validation needs to integrate with these for `C104` variable scoping checks.

### 4.3 G2/G3 — `where_eval.py` shipped evaluator has no aggregate path

`src/factgraph/core/rules/where_eval.py:38` defines `_ARITH_KINDS = {"add", "sub", "neg", "addc", "mulc"}`(verified during T2.2 review).No `_AGGREGATE_KINDS` exists.

`_eval_arith_atom` exists for arithmetic;no `_eval_aggregate_atom` exists.

Evaluator iterates env-list pattern(`for env in envs`)for each atom.Aggregate evaluation needs different shape:single aggregate execution **scans the env-list to collect matched rows**,then reduces to scalar/NoValue,then dispatches per result binding mode.Integration shape clarified in §5.4.

### 4.4 G2/G3 — `sdk/dsl/expr.py` shipped DSL has no aggregate helpers

`src/factgraph/sdk/dsl/expr.py` contains `BinaryExpr` for arithmetic(line ~134),`CompareExpr`(line ~195),`ExistsAtom`(line ~175),`AttrRef`(line ~101 with `entity_type`).No aggregate helper functions.

`Not(...)` helper(`expr.py:263+`)is the precedent shape:user-callable function returning a DSL expression object that participates in lowering.Aggregate helpers should follow this pattern.

### 4.5 G2/G3 — `sdk/dsl/application_rule.py` bridge handles existing IR

`src/factgraph/sdk/dsl/application_rule.py:build_application_rule(...)` lowers DSL → IR tuples via `lower_where`,then parses IR tuples → core AST via `parse_where_ir_to_ast`.

**This passthrough chain handles new IR kinds automatically once `lower_where` produces them and `parse_where_ir_to_ast` parses them.** No new bridge-level code expected unless:

- Aggregate IR shape requires a new lowering branch in `lower_where_atom`(if aggregate is a top-level "atom-like" wrapper),or
- Pre-lowering reject of legacy forms misclassifies aggregate(unlikely — `agg_count(...)` doesn't look like `Pred(...)` or `RuleRefAtom`).

`application_rule.py:_serialize_atom` covers `PredAtom`/`CmpAtom`/`InAtom`/`BuiltinAtom`/`NotAtom`.If `AggregateAtom` is serialized via `_serialize_term`(as `CmpAtom.lhs` value),a new `_serialize_term` branch is needed.

### 4.6 G2/G3 — `application/protocol/rule.py` allowlist

T1.1 archived `application/protocol/rule.py:_ALLOWED_ATOM_TYPES = (PredAtom, CmpAtom, InAtom, BuiltinAtom, NotAtom)`(T1.1 §2 + §3 lock).

**Per §2.11 and §5.1 decision**:T2.3 places `AggregateAtom` as `CmpAtom.lhs`/`.rhs` value,NOT as top-level Atom.So `_ALLOWED_ATOM_TYPES` extension is **not required** — only `_collect_term_vars` and `_serialize_term` need awareness of `AggregateAtom` as a Term-position value.

### 4.7 Parent essay C99-C105 semantic lock summary

All 7 commitments in parent §10.6.3-§10.6.9 are **fully specified semantically**:

- C99 (§10.6.3):5 kinds + value-producing position + no truth value.
- C100 (§10.6.4):filter restrictions + `not` body recursion limits + error class.
- C101 (§10.6.5):empty set + `AggregateNoValue` + propagation + JSON marker.
- C102 (§10.6.6):numeric target construct + runtime + count/min/max relaxations.
- C103 (§10.6.7):matched_count = view-projected.
- C104 (§10.6.8):correlated vs aggregate-local var scoping + error class.
- C105 (§10.6.9):result binding 3-branch(NoValue / unbound / bound).

**No load-bearing decision is needed** — implementation is direct translation of parent essay semantics.G7 precondition §5.8 #5 explicitly verifies this.

## 5. Proposed Shape

### 5.1 AggregateAtom as Term-position value within CmpAtom

**Design choice**:`AggregateAtom` is not a top-level Atom kind.Top-level `Rule.where` list contains `CmpAtom` whose `lhs` or `rhs` carries an `AggregateAtom` value.

Rationale:
- Parent essay §10.6.3 "agg 自身无 truth value(true/false 来自包裹 comparison 或 eq binding)"。
- Mirrors T2.2 pattern where `BuiltinAtom` ArithExpr lowering produced multi-atom emission(BuiltinAtom + CmpAtom)。But aggregate is structurally different:**a single aggregate is computed once over the env-list**,not lowered to multiple atoms。Embedding-as-Term is more natural.
- Keeps T1.1 `_ALLOWED_ATOM_TYPES` allowlist unchanged。

**Term type extension**:

```python
# where_ast.py
Term: TypeAlias = Var | Const | AggregateAtom  # extended from current Var | Const
```

This is a backward-compatible extension(existing `_parse_term` / `_lower_term` handle Var/Const;new AggregateAtom branch added).

**IR tuple shape for aggregate**:

```python
# aggregate as Term value inside CmpAtom IR tuple
("eq", Var("$v"), ("agg_sum", "$amount", [("pred", "Order:exists", ["$o"]), ...]))
```

`parse_where_ir_to_ast` extended:if RHS of CmpAtom is a tuple with `tag in _AGGREGATE_KINDS`,parse as `AggregateAtom`。

### 5.2 AggregateAtom dataclass

```python
# where_ast.py
@dataclass(frozen=True)
class AggregateAtom:
    kind: str  # in _AGGREGATE_KINDS
    target: Term | None  # None for "count"; Term for sum/min/max/mean
    filter: list[Atom]  # flat list of allowed atom kinds per C100
    origin: Origin | None = None
```

Validation deferred to where_ast_validate.py(C100 + C102 construct).

### 5.3 Filter validation algorithm (C100)

```python
# where_ast_validate.py
_AGGREGATE_FILTER_TOP_LEVEL_ALLOWED = {"pred", "eq", "ne", "gt", "ge", "lt", "le", "in", "not"}
_AGGREGATE_FILTER_NOT_BODY_ALLOWED = _AGGREGATE_FILTER_TOP_LEVEL_ALLOWED - {"not"}  # no nested not

def _validate_aggregate_atom(atom: AggregateAtom, *, outer_bound_vars: set[str]) -> None:
    # kind check
    if atom.kind not in _AGGREGATE_KINDS:
        raise AggregateValidationError(...)
    # target type construct-time(C102 construct)
    if atom.kind in {"sum", "mean"} and isinstance(atom.target, Const):
        if not isinstance(atom.target.value, (int, float)) or isinstance(atom.target.value, bool):
            raise AggregateValidationError(...)
    # filter top-level kind check
    for f in atom.filter:
        kind = _get_atom_kind(f)
        if kind not in _AGGREGATE_FILTER_TOP_LEVEL_ALLOWED:
            raise AggregateValidationError(...)
        # not body recursion limit
        if isinstance(f, NotAtom):
            _validate_aggregate_not_body(f.body)
    # variable scoping(C104)
    _validate_aggregate_scoping(atom, outer_bound_vars)


def _validate_aggregate_not_body(body) -> None:
    # body is AndExpr or list[Atom]
    # disallow: nested not, AggregateAtom, BuiltinAtom, RuleRefAtom, OrExpr
    ...


def _validate_aggregate_scoping(atom: AggregateAtom, outer_bound: set[str]) -> None:
    # collect filter vars
    filter_vars = ...
    # aggregate-local vars = filter_vars - outer_bound
    local_vars = filter_vars - outer_bound
    # outer atoms after aggregate should not reference local_vars
    # (this check happens in _validate_and_dataflow at AggregateAtom position)
    ...
```

### 5.4 Python evaluator algorithm

```python
# where_eval.py
class _AggregateNoValueSentinel:
    """Singleton marker for empty min/max/mean and propagation."""
    def __repr__(self) -> str: return "AggregateNoValue"

AggregateNoValue = _AggregateNoValueSentinel()


def _eval_aggregate_atom_value(
    aggregate: AggregateAtom,
    envs: list[dict[str, Any]],
    *,
    ast_gate_on: bool,
) -> int | float | _AggregateNoValueSentinel:
    """Evaluate aggregate over the current env-list, returning scalar or NoValue."""
    # 1. Apply filter to envs, collect rows that match.
    matched_envs = _apply_filter(aggregate.filter, envs, ast_gate_on=ast_gate_on)
    # 2. Extract target values from matched_envs.
    if aggregate.kind == "count":
        return len(matched_envs)
    target_values = [_resolve_term(env, aggregate.target) for env in matched_envs]
    # 3. Empty set handling(C101)
    if not target_values:
        if aggregate.kind == "sum":
            return 0
        return AggregateNoValue
    # 4. Runtime numeric target check(C102 runtime)
    if aggregate.kind in {"sum", "mean"}:
        for v in target_values:
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                return AggregateNoValue  # atom violated, per C102
    # 5. Reduce per kind.
    if aggregate.kind == "sum":
        return sum(target_values)
    if aggregate.kind == "mean":
        return sum(target_values) / len(target_values)
    if aggregate.kind == "min":
        try:
            return min(target_values)
        except TypeError:
            return AggregateNoValue  # orderable check failure
    if aggregate.kind == "max":
        try:
            return max(target_values)
        except TypeError:
            return AggregateNoValue
    raise WhereValidationError(f"unsupported aggregate kind: {aggregate.kind}")


def _eval_cmp_atom_with_aggregate(env, atom: CmpAtom, ...) -> list[dict]:
    # Compute aggregate result if lhs or rhs is AggregateAtom.
    # Apply C105 result binding logic.
    ...
```

Integration with main evaluator:`_eval_cmp_atom` (existing)dispatches to `_eval_cmp_atom_with_aggregate` when either operand is `AggregateAtom`.

### 5.5 SDK DSL ergonomic helpers

```python
# sdk/dsl/expr.py
@dataclass(frozen=True)
class _AggregateRef:
    kind: str
    target: Any  # LogicVar / AttrRef / Const-like
    filter: list[Any]  # DSL atoms

    # comparison dunders (== / != / > / >= / < / <=) return CompareExpr(op, self, other)
    def __eq__(self, other): return CompareExpr("eq", self, other)
    def __ne__(self, other): return CompareExpr("ne", self, other)
    def __gt__(self, other): return CompareExpr("gt", self, other)
    def __ge__(self, other): return CompareExpr("ge", self, other)
    def __lt__(self, other): return CompareExpr("lt", self, other)
    def __le__(self, other): return CompareExpr("le", self, other)


def agg_count(*, where: list[Any]) -> _AggregateRef:
    return _AggregateRef(kind="count", target=None, filter=where)


def agg_sum(target: Any, *, where: list[Any]) -> _AggregateRef:
    return _AggregateRef(kind="sum", target=target, filter=where)


# similar for agg_min / agg_max / agg_mean
```

DSL lowering(in `lower_where_atom` or `_lower_compare`):when CompareExpr lhs/rhs is `_AggregateRef`, lower target + filter atoms recursively, emit IR tuple `(kind, target_lowered, filter_ir_list)` as Term value in CmpAtom IR tuple.

### 5.6 Bridge passthrough verification

`application_rule.py:_serialize_term` needs new branch for `AggregateAtom`(content_digest correctness):

```python
def _serialize_term(term):
    if isinstance(term, Var): return _serialize_var(term)
    if isinstance(term, Const): return _serialize_const(term)
    if isinstance(term, AggregateAtom):  # NEW
        return {"type": "AggregateAtom", "kind": term.kind, "target": _serialize_term(term.target) if term.target else None, "filter": [_serialize_atom(a) for a in term.filter]}
    raise RuleValidationError(...)
```

`_collect_term_vars` similarly needs `AggregateAtom` branch:collect vars from `target` + `filter`,but ONLY the filter-internal local vars are aggregate-scoped(per C104).Cross-check with where_ast_validate's scoping rules.

### 5.7 Application Rule untouched(per T1.1 contract)

`application/protocol/rule.py` `_ALLOWED_ATOM_TYPES` **stays as-is**:`(PredAtom, CmpAtom, InAtom, BuiltinAtom, NotAtom)`。`AggregateAtom` is Term-position,not top-level Atom.

### 5.8 G7 pre-impl precondition

Before implementation:

1. `_BUILTIN_TAGS` in `where_ast.py:96` does NOT contain `count`/`sum`/`min`/`max`/`mean`(verify substrate empty).
2. `where_ast.py` does NOT define `AggregateAtom` type(verify type empty).
3. `where_ast_validate.py` has NO aggregate validation function(verify validator empty).
4. `where_eval.py` has NO aggregate evaluator(verify eval empty).
5. C99-C105 are unambiguously implementable(no load-bearing decision pending):re-read parent §10.6.3-§10.6.9 + §8.8 lowering for-strategy — confirm semantic completeness。If any C-commitment surfaces ambiguity(e.g.,"how exactly is correlated var detection algorithm shaped"),**escalate slice from S to M**, open Stage 2 decision doc for that point.

If any check #1-4 fails(substrate not actually empty)→ amend blueprint。
If check #5 surfaces ambiguity → escalate to M class.

### 5.9 Tests structure

```
tests/core/rules/test_aggregate_substrate.py  (new ~250 LOC)
- TestAggregateAtomIR:parse / lower / round-trip for 5 kinds
- TestAggregateFilterValidation:reject OR / nested aggregate / BuiltinAtom in filter / RuleRefAtom / nested not
- TestAggregateVariableScoping:correlated OK / aggregate-local doesn't leak
- TestAggregateNumericTargetConstruct:reject string Const for sum/mean
- TestAggregateNoValue:empty set count/sum → 0;min/max/mean → NoValue;JSON marker

tests/core/rules/test_aggregate_eval.py  (new ~250 LOC)
- TestAggregateEval5Kinds:happy path for count/sum/min/max/mean over non-empty matched rows
- TestAggregateNoValuePropagation:NoValue in comparison / NoValue in ArithExpr operand
- TestAggregateRuntimeNumericTarget:matched row with non-numeric target → atom violated (not exception)
- TestAggregateResultBinding:Var unbound → bind;Var bound → equality check;NoValue → atom violated
- TestAggregateInComparison:agg_sum(...) > 100 / agg_count(...) == 5 / agg_mean(...) <= 50

tests/sdk/dsl/test_aggregate_ergonomic.py  (new ~150 LOC)
- TestAggCountHelper:agg_count(where=[...]) lowers to IR
- TestAggSumHelper / TestAggMinHelper / TestAggMaxHelper / TestAggMeanHelper
- TestAggregateInBuildApplicationRule:bridge passthrough produces Rule with aggregate in CmpAtom Term
- TestAggregateBridgeContentDigest:content_digest deterministic across processes
```

Estimated test LOC ~650.

### 5.10 Size estimate

| Component | Est. LOC |
|---|---|
| `where_ast.py` AggregateAtom + parse + lower + Term extension | ~100 |
| `where_ast_validate.py` validation(filter + scoping + numeric construct) | ~150 |
| `where_eval.py` evaluator + AggregateNoValue + integration | ~150 |
| `sdk/dsl/expr.py` 5 helpers + _AggregateRef + comparison dunders | ~80 |
| `sdk/dsl/application_rule.py` _serialize_term branch + _collect_term_vars branch | ~30 |
| Tests | ~650 |
| **Total** | **~1160 LOC** |

This is **above the S-class ~300 LOC guideline by ~4x**.But:
- No load-bearing decision(parent essay locks all semantics)
- No public API rename or replacement
- Pure additive net-new substrate
- Structurally a single coherent slice(IR + validation + eval + ergonomic + bridge passthrough)

**S-class with documented size override**.If user disagrees,escalate to M with formal acknowledgment(but no decision doc Q needed)。

If escalation requested(P-finding during Step 4.2 review),scope can be split:
- **T2.3.a**:IR + validation + Python eval + tests(~400 LOC)
- **T2.3.b**:SDK ergonomic + bridge passthrough + tests(~250 LOC)
- T2.3.c:Souffle wire(future)
- T2.3.d:ProbLog wire(future)

## 6. Boundaries And Invariants

- **Substrate-only invariant**:T2.3 ships IR + validation + Python eval + SDK ergonomic + bridge passthrough。Souffle/ProbLog adapter wires are explicit Non-goals(deferred to T2.3b/T2.3c sub-slices).
- **AggregateExpr-as-Term invariant**:`AggregateAtom` is `CmpAtom.lhs`/`.rhs` value,**never** top-level `Rule.where` Atom。T1.1 `_ALLOWED_ATOM_TYPES` unchanged。
- **Semantic-lock invariant**:C99-C105 semantics fully translate from parent essay §10.6.3-§10.6.9 without modification or relaxation。
- **NoValue isolation invariant**:`AggregateNoValue` propagation never raises Python exception;always returns NoValue or causes atom violation per parent §10.6.5。
- **Filter-only-9-kinds invariant**:filter clause top-level atoms restricted to 9 scalar kinds(pred / eq / ne / gt / ge / lt / le / in / not);`not` body further restricted to 8 kinds(no nested not)。
- **Variable scoping invariant**:aggregate-local vars do NOT leak to outer Rule.where context per C104。
- **Adapter-deferral invariant**:adapter wires(Souffle / ProbLog)stay 0 LOC change in T2.3 — verified by scope diff。
- **Cross-slice contract invariant**:T1.1 application Rule allowlist unchanged;T1.2 bridge passthrough unchanged(only `_serialize_term` / `_collect_term_vars` gain AggregateAtom branch);T2.1 ne dispatch unchanged;T2.2 ArithExpr unchanged。

## 7. Acceptance

- [ ] G1/G4 traceability:every §2 goal cites C99-C105。
- [ ] G7 pre-impl precondition runs and is recorded in audit log **before** code implementation(per T2.2 / fixture cleanup timing improvement)。
- [ ] G7 #5 ambiguity check:if C99-C105 ambiguity surfaces during precondition → escalate S → M with decision doc and pause impl。
- [ ] `where_ast.py` adds `AggregateAtom` type + `_AGGREGATE_KINDS` constant + parse / lower extension。
- [ ] `where_ast.py` Term TypeAlias extended to include `AggregateAtom`。
- [ ] `where_ast_validate.py` enforces filter clause flat list + 9-kind allowlist + `not` body recursion limit + variable scoping + construct-time numeric target type with `AggregateValidationError` / `AggregateVariableScopeError`。
- [ ] `where_eval.py` evaluates 5 aggregate kinds + `AggregateNoValue` sentinel + empty set behavior + runtime numeric target check + result binding 3-branch logic。
- [ ] `sdk/dsl/expr.py` provides 5 ergonomic helpers(`agg_count` / `agg_sum` / `agg_min` / `agg_max` / `agg_mean`)returning `_AggregateRef` with comparison dunders。
- [ ] `sdk/dsl/application_rule.py` `_serialize_term` and `_collect_term_vars` recognize `AggregateAtom`(content_digest determinism + var collection correctness)。
- [ ] T1.1 `application/protocol/rule.py:_ALLOWED_ATOM_TYPES` unchanged(verified by scope diff)。
- [ ] Tests:`tests/core/rules/test_aggregate_substrate.py` + `tests/core/rules/test_aggregate_eval.py` + `tests/sdk/dsl/test_aggregate_ergonomic.py` all pass。
- [ ] Cross-slice non-regression:T1.1 + T1.2 + T2.1 + ProbLog hygiene + T2.2 + fixture cleanup tests all pass(70+ tests baseline)。
- [ ] Ruff clean on all touched source + test files。
- [ ] No Souffle / ProbLog / PyReason adapter files changed(scope diff verifies)。
- [ ] Sacred `master 562c7419` unchanged。
- [ ] Dirty 4 M + 1 untracked preserved。

## 8. Implementation Plan

1. **G7 pre-impl precondition**:run §5.8 checks 1-5;if any fail,amend blueprint before code(escalate to M if #5 surfaces ambiguity)。Record result in audit log **before** impl commit。
2. **IR layer**:add `AggregateAtom` to `where_ast.py` + extend Term TypeAlias + parse / lower branches + `_AGGREGATE_KINDS` constant。
3. **Validation layer**:add aggregate validators to `where_ast_validate.py`(filter + scoping + numeric construct + `not` body recursion)。
4. **Evaluator layer**:add `_eval_aggregate_atom_value` to `where_eval.py` + `AggregateNoValue` sentinel + comparison integration。
5. **SDK ergonomic**:add 5 helpers to `sdk/dsl/expr.py` + `_AggregateRef` dataclass + DSL lowering branch。
6. **Bridge integration**:extend `_serialize_term` + `_collect_term_vars` in `sdk/dsl/application_rule.py`。
7. **Tests**:add 3 test files per §5.9。
8. **Run gates**:
   - `PYTHONPATH=src python -m unittest tests.core.rules.test_aggregate_substrate tests.core.rules.test_aggregate_eval tests.sdk.dsl.test_aggregate_ergonomic`
   - Cross-slice non-regression
   - `python -m ruff check ...`
9. **Fill §10 Outcome** with exact LOC,test outcomes,deviations,follow-up。

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md` — add `Aggregate substrate` section explaining how aggregates appear in `CmpAtom.lhs`/`.rhs` and how `AggregateNoValue` behaves.
- Track plan §1.2.5 retroactive labeling table — add T2.3 row after archive(memory consolidation slice).
- No user-facing public docs(SDK quickstart)— aggregate user-facing path lands when T2.3.b SDK ergonomic + bridge are complete and surfaces are confirmed usable.

## 10. Outcome / Deviations

- Pending.
