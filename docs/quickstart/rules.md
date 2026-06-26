# Rules: declaring queries and composing them

This chapter covers how to *declare* rules and *compose* them. Executing a rule (engine choice, semantics) is [`engines_and_configs.md`](engines_and_configs.md); the shape of result rows and explanations is [`evaluate_and_evidence.md`](evaluate_and_evidence.md).

Two assets carry the work in this chapter:

| Asset | Role | Triggers evaluation? |
|---|---|---|
| `Rule` | a named query template — `when` body + `ports` head | no (declaration only) |
| `RuleExpr` | AND/OR/join composition over Rules | no (declaration only) |

Two older assets — `Inference` and `Query` — exist but are no longer the primary surface. They are recorded in §6 (History note) with pointers to their current successors.

## 1. Rule + RuleExpr — the one-paragraph triangle

A `Rule` is a *named query template*. It declares what facts must be present (`when`) and what variables it exposes (`ports`). It does not write anything to the ledger and does not run on its own.

A `RuleExpr` glues multiple Rules together with `&` (AND), `|` (OR), and explicit joins on port equality. The composition is still a declaration — only `fg.eval.evaluate(...)` (next chapter) consumes it.

The rest of this chapter is structured as:

- §2 — how to write one `Rule`
- §3 — how to compose Rules into a `RuleExpr`
- §4 — `fg.rules.inspect(...)` and `fg.rules.structure(...)` for structural debugging
- §5 — one-line pointer to the evaluation chapter
- §6 — history note for `Inference` and `Query`

## 2. Rule — the query template

### 2.1 Minimal end-to-end

```python
from factgraph.sdk import (
    Entity, FactGraph, Field, Identity,
    build_application_rule, vars,
)


class User(Entity):
    user_id: str = Identity()
    age: int = Field()
    region: str = Field()


fg = FactGraph.create(schema_classes=[User])
alice = fg.entities.create(User, user_id="u-1")
fg.fields.set(User.age, alice, 25)
fg.fields.set(User.region, alice, "US")

with vars("u", "age") as (u, age):
    adult_in_us = build_application_rule(
        id="adult_in_us",
        version="v1",
        when=[
            User(u),
            User(u).age == age,
            User(u).region == "US",
            age > 18,
        ],
        ports={"user": u, "age": age},
    )
```

`build_application_rule(...)` returns a frozen `Rule`:

- `id` is the stable rule id (see §3.2 — if the id contains characters disallowed in aliases, e.g. `:`, you must wrap with `.as_(alias)` before composing)
- `version` labels the declaration revision
- `when` is the body — a list of atoms saying *what must be matched*
- `ports` is the head — a `{name: Var}` map saying *what is exposed*

The rule is now a reusable value. Running it (`fg.eval.evaluate(adult_in_us, ...)`) is the next chapter; from here on §2 covers only how to *write* the body and head.

### 2.2 `when` atoms

The Entity-DSL syntax is plain Python — Entity classes are callable, and their attribute access returns comparable references.

| Form | Meaning |
|---|---|
| `User(u)` | entity-existence atom — `u` binds to some `User` entity |
| `User(u).age == 25` | field equality to a constant |
| `User(u).age == age` | bind the field to a logic variable |
| `User(u).age == User(u).other_field` | attr-vs-attr equality on the same entity |
| `age > 18` *(pure logic var vs value)* | logic-var comparison — `<` / `<=` / `>=` / `>` / `==` / `!=` all work |
| `Not([User(u).age == minor_age, ...])` | negation — body is a **list** of atoms; the same per-form rules apply inside |
| `total == agg_sum(Order(o).amount, where=[Order(o).buyer == u])` | aggregate appears on a side of the comparison |

**Important constraint — entity-attribute comparison sugar supports only `==`.** Writing `User(u).age > 18` directly raises `DSLToApplicationRuleError`. To filter by other comparisons, bind the field to a logic variable first and compare *that* variable:

```python
with vars("u", "age") as (u, age):
    adult = build_application_rule(
        id="adult",
        when=[User(u), User(u).age == age, age > 18],   # bind, then compare
        ports={"user": u, "age": age},
    )
```

The logic variable does not have to appear in `ports` if it is only used as a comparison bridge — only `ports`-listed vars must appear in `when` (the other direction is not required).

Logic variables come from `vars(...)`, used as a context manager:

```python
with vars("u", "tag") as (u, tag):
    ...
```

Names must be identifiers; `__`-prefixed names are reserved for system temporaries.

The aggregate helpers (`agg_count` / `agg_sum` / `agg_min` / `agg_max` / `agg_mean`) live in `factgraph.sdk.dsl`. They take a keyword-only `where=[...]` for their inner filter — note that this `where=` is the aggregate's filter clause, **not** the rule's body (the rule's body keyword is `when=`).

#### Lower-level `Pred(pred_id, *terms)`

`Pred` is the raw predicate-atom factory:

```python
from factgraph.sdk import Pred
Pred("user:tag_seed", u, tag)
```

It is still importable, but `build_application_rule(when=[Pred(...)])` **rejects raw `Pred` atoms** in the body — the message is *"Pred(...) raw atom is not allowed in new Rule path; use Entity(var).field syntax"*. Two contexts where `Pred` is legitimate:

1. Inside an `Inference` body (history note §6.1) — the legacy DSL path
2. When constructing a low-level `Rule(id=..., when=tuple[PredAtom, ...], ports=...)` directly (§2.6)

For the full Entity-DSL reference and aggregate signatures, see [`docs/official/kernel/quickstart/rules-and-inferences.md`](../official/kernel/quickstart/rules-and-inferences.md) §"Run a Rule" and §"Aggregate helpers in `when` bodies".

### 2.3 `ports` — the head

`ports={"name": Var, ...}` is the rule's external interface. Two constraints:

- `ports` must be non-empty
- every port's `Var` must appear in `when`

Each port has an inferred `port_type`:

| Var role in `when` | inferred `port_type` |
|---|---|
| Appears in the entity slot of `User(u)` | `PortType(kind="entity_ref", entity_type="User")` |
| Appears in the value slot of `User(u).field == v` | `PortType(kind="value", entity_type=None)` |

You can read these back:

```python
adult_in_us.port_types["user"]   # PortType(kind="entity_ref", entity_type="User")
adult_in_us.port_types["age"]    # PortType(kind="value", entity_type=None)
```

`ports` is also the surface that `fg.entities.match(...)` and `RuleExpr.join_by_ports(...)` consume.

**Declaration-time ports vs evaluation-time `head=`**. `Rule.ports` declares *what this rule exposes*. When the rule is executed through a `RuleExpr` with multiple occurrences, the evaluator additionally needs to know *which occurrence's ports are the output answer* — that selection is made at call time via `fg.eval.evaluate(rule_expr, head=<Rule>)`. The `head=` parameter is covered in [`evaluate_and_evidence.md`](evaluate_and_evidence.md) §1.2; for a single-rule `evaluate(rule, head=rule)` it is trivial, but `RuleExpr` composition makes it load-bearing.

### 2.4 `Rule.projection(*port_names)`

A shortcut for a rule whose only job is to *expose* named ports without imposing a body:

```python
from factgraph.sdk import Rule

proj = Rule.projection("user", "tag")
```

This is used by callers like `fg.entities.match(EntityCls, template, ...)` when the template is just "give me snapshots projected on these ports" — see [`three_layer_api.md`](three_layer_api.md) §2.

### 2.5 `repr` and `render_repr`

A rule can carry a human-readable description with `%portname` placeholders:

```python
rule = build_application_rule(
    id="adult_in_us",
    when=[User(u), User(u).age == age, age > 18],
    ports={"user": u, "age": age},
    repr="User %user is %age years old",
)

rule.render_repr({"user": "alice", "age": 25})
# → "User alice is 25 years old"
```

Behavior reference:

- **Default**: `repr=None`. `render_repr()` on a rule with no `repr` returns `""`.
- **Placeholder syntax**: `%<identifier>` where `<identifier>` matches `[A-Za-z_][A-Za-z0-9_]*`. Every placeholder name must reference a declared port — `repr="%foo ..."` with `foo` not in `ports` raises `RuleValidationError: repr references undeclared port: foo` at construction time.
- **No `%` escape**. A `%` followed by anything other than an identifier start is `RuleValidationError: repr contains malformed percent port interpolation`. This means `repr="50% off for %user"` is rejected (the `%5` is malformed), and there is **no `%%` escape** for a literal percent sign — `repr="100%% literal"` raises the same error.
- **`render_repr(bindings)`**: `bindings` may be `None` (treated as `{}`) or a `Mapping[str, Any]`. Placeholders without a binding render as `<portname>`. Extra keys not referenced by any placeholder are silently ignored.

**Where `repr` is consumed.** `repr` is an author-controlled label — the evaluation runtime does **not** automatically render it. It does **not** appear in `EvaluateRow` or in the structured `Explanation.repr` (those are covered in [`evaluate_and_evidence.md`](evaluate_and_evidence.md)) — though the additive `Explanation.narrate()` surface *does* render head/rule `repr` (see `evaluate_and_evidence.md` §4.5); the *schema* `repr` templates that drive explanation atom text are a separate feature, [`schema_definition.md`](schema_definition.md) §1.8. Four actual consumption points:

1. `rule.render_repr(bindings)` — the per-rule render shown above.
2. `fg.rules.inspect(rule_or_expr).render(bindings)` — `RuleExprInspect.render(...)` composes the AST, each occurrence's rendered repr, and the joins into a one-line summary. With more than one occurrence of the same rule, use `alias.portname` qualified keys to disambiguate same-named ports:
   ```python
   info = fg.rules.inspect((adult.as_("a") & adult.as_("b")).join_by_ports("user"))
   info.render({"a.user": "alice", "a.age": 25, "b.user": "alice", "b.age": 30})
   # → 'RuleExprInspect | (a:adult & b:adult).join(1)
   #    | a:adult alice is 25 years old; b:adult alice is 30 years old
   #    | joins a.user = b.user'
   ```
   Bare `portname` keys also work for single-occurrence expressions; the renderer falls back to bare names when no qualified key matches.
3. `RuleExprInspect.render_compact()` — emits only the AST short form (e.g. `'adult'` or `'(a:adult & b:adult).join(1)'`). Does not consume `repr`.
4. Internal carry-over: each closed-head `Rule` produced per evaluation row copies `repr=head.repr` ([`evaluate_result.py:740`](../../src/factgraph/application/protocol/evaluate_result.py)). This is data plumbing — it propagates the template along the closed-head chain but does not surface it to user-visible output on its own.

### 2.6 Direct `Rule(id, when=tuple, ports=...)` — advanced

`Rule` is a frozen dataclass at `factgraph.application.protocol.Rule`. Constructing it directly is supported and produces a fully usable rule (same `port_types` inference, same `render_repr`, same `fg.rules.inspect(...)`, same `RuleExpr` composition). The only difference from `build_application_rule(...)` is that `when` takes already-canonical *core* atoms instead of Entity-DSL forms.

```python
Rule(
    id: str,
    when: tuple[Atom, ...],      # core-level atoms only
    ports: Mapping[str, Var],
    version: str | None = None,
    repr: str | None = None,
)
```

#### Imports

Core atoms are **not** re-exported from `factgraph.sdk`. Import them from `factgraph.core.rules.where_ast`:

```python
from factgraph.core.rules.where_ast import (
    PredAtom, CmpAtom, InAtom, BuiltinAtom, NotAtom,
    AndExpr, OrExpr,        # only needed inside NotAtom.body
    Var, Const,
)
from factgraph.application.protocol import Rule    # or: from factgraph.sdk import Rule
```

#### Working example — same rule as §2.1, written with core atoms

```python
u   = Var(name="u")
age = Var(name="age")

adult_in_us_core = Rule(
    id="adult_in_us_core",
    when=(
        PredAtom(pred_id="User:exists", terms=[u]),
        PredAtom(pred_id="user:age",    terms=[u, age]),
        PredAtom(pred_id="user:region", terms=[u, Const(value="US")]),
        CmpAtom(op="gt", lhs=age, rhs=Const(value=18)),
    ),
    ports={"user": u, "age": age},
    version="v1",
    repr="User %user is %age years old",
)
```

The pred-id convention that `build_application_rule(...)` produces internally:

| Entity-DSL form | core `PredAtom` form |
|---|---|
| `User(u)` | `PredAtom(pred_id="User:exists", terms=[u])` — entity name capitalised, `:exists` suffix |
| `User(u).age == age` | `PredAtom(pred_id="user:age", terms=[u, age])` — entity name lower-cased + `:` + field name |
| `User(u).age == "x"` | `PredAtom(pred_id="user:age", terms=[u, Const(value="x")])` — constants wrapped in `Const` |
| `age > 18` | `CmpAtom(op="gt", lhs=age, rhs=Const(value=18))` — ops: `eq` / `ne` / `gt` / `ge` / `lt` / `le` |
| `Not([User(u).age == minor_age])` | `NotAtom(body=AndExpr(atoms=[PredAtom(...)]))` — body is a `WhereExpr` (`AndExpr` or `OrExpr`), **not** a list |

#### What direct construction rejects

- **SDK DSL atoms in `when`** — `Rule(when=(Pred("user:age", u, age),))` raises `RuleValidationError: when[0] must be one of PredAtom/CmpAtom/InAtom/BuiltinAtom/NotAtom`. Mixing the two surfaces is not allowed; use one path consistently.
- **Empty `when` or empty `ports`** — both raise `RuleValidationError`.
- **`ports` `Var` not appearing in `when`** — same constraint as `build_application_rule(...)`.

#### When to choose direct construction over `build_application_rule(...)`

| Surface | Accepts | When to use |
|---|---|---|
| `build_application_rule(id, when=[Entity-DSL atoms], ports={...})` | SDK DSL atoms + ports | Default for application code. Handles lowering, `Var` canonicalisation, and the Entity-DSL ergonomics. |
| `Rule(id, when=tuple[PredAtom, CmpAtom, ...], ports={...})` | Already-canonical core atoms | When you already hold core atoms — typically because you are composing them from another core-layer source (rule migration / programmatic generation / IR round-trip), or when you need atom shapes the Entity-DSL does not expose (`InAtom`, `BuiltinAtom`, raw `RuleRefAtom`). |

Both paths produce the **same** `Rule` value; downstream APIs (`fg.rules.inspect`, `fg.eval.evaluate`, `RuleExpr` composition, `match`) do not distinguish them.

## 3. RuleExpr — composition

Rules combine into a `RuleExpr` through the bitwise operators `&` / `|`, factory methods, and explicit joins.

### 3.1 AND / OR

```python
from factgraph.sdk import RuleExpr

r1 & r2                          # _AndGroup
r1 | r2                          # _OrGroup
RuleExpr.all(r1, r2, r3)         # AND factory (≥ 2 operands)
RuleExpr.any(r1, r2, r3)         # OR factory  (≥ 2 operands)
```

The result of any of these is again a `RuleExpr`, so the operators chain. Nested
composition is accepted: before evaluation, the application lowers nested
`AND`/`OR` trees to an OR-of-AND normal form. For example, `(a | b) & (c | d)`
evaluates as the four branches `(a & c) | (a & d) | (b & c) | (b & d)`.
Native, ProbLog, and Souffle evaluation all project adapter answers to the
declared `head=` ports; branch-local variables from sibling OR branches are
existential implementation detail, not result columns.

The normalizer has two guardrails:

- If the same occurrence would be copied into multiple expanded branches, the
  copied aliases are made branch-local automatically. User-authored duplicate
  aliases that already collide before normalization still raise `RuleExprError`.
- Expansion is capped at 32 branches. Larger products raise `RuleExprError`
  instead of silently generating a very large query.

### 3.2 Occurrence + alias

If the same `Rule` appears in an expression more than once, each appearance must have an explicit alias. `rule.as_(alias)` returns a `RuleOccurrence`:

```python
left = adult_in_us.as_("left")
right = adult_in_us.as_("right")
both = left & right
```

Alias rules:

- must match `[A-Za-z][A-Za-z0-9_]*`
- must not contain `:` (to avoid collision with predicate-id syntax)
- must be unique within the expression

If you do not call `.as_(...)`, the rule's `id` is used as an implicit alias. Reusing the same rule without an explicit alias raises `RuleExprError`.

### 3.3 Joins

Cross-occurrence equality joins go on `_AndGroup` nodes only. Two ways to express them:

```python
# Explicit constraint:
constraint = rule_a.as_("a").port("user").eq(rule_b.as_("b").port("user"))
joined = (rule_a.as_("a") & rule_b.as_("b")).join(constraint)

# Same-name shorthand:
joined = (rule_a.as_("a") & rule_b.as_("b")).join_by_ports("user")
```

Pieces:

- `.port(name)` returns a `RulePortRef` (carries `occurrence_alias`, `rule_id`, `port_name`, `var`, `port_type`)
- `RulePortRef.eq(other)` returns a `RuleJoinConstraint(left, right, op="eq")`
- `_AndGroup.join(*constraints)` attaches one or more constraints to the AND group
- `_AndGroup.join_by_ports(*names)` is the same but binds every named port across all occurrences in the group

`_OrGroup` rejects `.join(...)` and `.join_by_ports(...)`. Put the join on an
`AND` expression. If that `AND` contains nested `OR` children, the normalizer
carries the join into each expanded branch as long as every branch exposes the
joined port.

```python
# Wrong — RuleExprError:
((r1.as_("a") | r2.as_("b"))).join(constraint)

# Right — join on the surrounding AND; normalization distributes it:
((r1.as_("a") | r2.as_("b")) & r3).join_by_ports("user")
```

### 3.4 `ExplicitBoolError`

Both `Rule` and `RuleExpr` raise `ExplicitBoolError` on Python truthiness:

```python
if rule and other:      # ExplicitBoolError
    ...
```

Message:

> `Rule values do not support Python truthiness; use & or | instead of and/or`

The short reason: Python's `and` / `or` short-circuit and return *one operand*, not a composition — silently dropping a rule. `&` / `|` force the composition to be explicit.

## 4. `fg.rules.inspect` — read-only structural view

`fg.rules` is a frozen namespace that exposes two read-only views — `inspect` (this section) and `structure` (§4.5):

```python
info = fg.rules.inspect(rule_or_expr_or_inference)
```

The returned shape depends on the input:

| Input | Returns |
|---|---|
| application protocol `Rule` (from `build_application_rule`) | `RuleExprInspect` typed object (see below) |
| `RuleExpr` | `RuleExprInspect` typed object |
| Legacy SDK DSL `Rule` or `Inference` (see §6) | a `dict` with `{kind, id, version, heads, branches}` |

When passing an application `Rule` whose `id` contains characters disallowed in aliases (notably `:`, common in pred-id-style ids), wrap it in a `RuleExpr` with an explicit alias first: `fg.rules.inspect(RuleExpr.all(rule.as_("safe_alias")))`. The internal coercion uses `rule.id` as an implicit alias and will raise `RuleExprError` otherwise.

`RuleExprInspect` exposes:

```text
.ast                      -> the canonical RuleExpr AST
.occurrences              -> RuleOccurrence list (one per .as_() in the expression)
.joins                    -> RuleJoinConstraint list (resolved join graph)
.unjoined_same_name_ports -> ports that share a name but were not joined
.ports                    -> PortInspect-typed view of port shapes
.is_closed                -> bool: every port is bound by the body
.unbound_ports            -> tuple[str, ...] of names still open
.render(bindings=None)    -> str: AST + occurrences (with rendered repr) + joins
.render_compact()         -> str: AST short form only (no repr)
```

`.render(bindings)` is the multi-occurrence consumer for `repr` (see §2.5). `.render_compact()` is the AST-only view useful for debugging composition shape.

`is_closed` is the key signal for "is this expression ready to be a closed-head evaluation input" — an open port means there is a `value` port not pinned to a constant in `when`, or an `entity_ref` port without an identifying atom path. Evaluation typically requires a closed head.

`fg.rules.inspect` is read-only — it does not execute the rule and does not touch the ledger.

### 4.5 `fg.rules.structure` — the structure aligned with `explain`

`fg.rules.structure(...)` is the second read-only view. Where `inspect` returns the authored-shape `RuleExprInspect`, `structure` returns a **`RuleStructure`**: the same static structure projected into the **same node shape as the `EvidenceGraph`** that `fg.eval.explain(...)` produces — so the two line up node-for-node.

```python
structure = fg.rules.structure(rule)                  # an application Rule
structure = fg.rules.structure(rule_expr, head=head)  # a RuleExpr needs a closed Rule head
```

It is **engine-neutral** (runs no engine, reads no facts) and a **superset of `inspect`** — it carries the same `.ast` / `.render(bindings)` / `.render_compact()` / `.occurrences` / `.joins` / `.ports` / `.templates` / `.is_closed` / `.unbound_ports`.

On top of the inspect floor, `RuleStructure` carries the explain-aligned tree:

```text
.branches        -> StructureBranch per DNF branch (branch_id "c0", "c1", ...)
  .occurrences   -> StructureOccurrence (occurrence_alias, rule_id, role, atoms)
    .atoms       -> StructureAtom (atom_id, kind, summary, form)
                    form: Fact | Compare | Builtin | Aggregate;
                    terms are FreeVar(name, port_name) | Const  (a FreeVar is a *naked* variable)
  .joins         -> StructureJoin (join_id, left/right StructurePortRef)
  .head_links    -> StructureHeadLink
.head_closure    -> HeadClosure(is_closed, unbound_ports) when a schema is present, else None
```

The `Structure*` node types, `FreeVar`, `Const`, and `HeadClosure` are importable from `factgraph.sdk` (you usually read them off the structure rather than import them).

`RuleStructure.narrate()` gives the static, display-side twin of `Explanation.narrate()`:

```python
for line in structure.narrate():
    print(line)
```

It uses the same branch / occurrence / atom / join ordering as explain narrate and keeps the identity anchors (`[atom_id]`, join expressions, `[head]`). Because it is static, it omits verdicts, icons, certainty/probability, context run tokens, and `produces:` lines; atom terms render as naked variables (`%port` when a port name is known) rather than executed values.

**Alignment with `explain` (对位).** `RuleStructure` and `fg.eval.explain(...).evidence` are **node-identical** on their identity keys — `branch_id ↔ tree_id`, `occurrence_alias`, `atom_id`, `join_id` — because both are projections of the *same* lowering plan (a single source, so they cannot drift). The structure side carries naked variables (`FreeVar`); the explain side carries executed values + verdicts:

```python
structure = fg.rules.structure(expr, head=head)
evidence  = fg.eval.explain(expr, head=head, engine="native").evidence
# same branch_id / occurrence_alias / atom_id / join_id on both;
# structure atoms hold FreeVar terms, evidence atoms hold executed values + verdicts.
```

This holds identically across the relational engines (`native` / `souffle` / `problog`). PyReason timelines are temporal and outside node-identity scope; the static structure is always tree-shaped.

`fg.rules.structure` is a read-only derived view — like `inspect`, it never executes a rule or touches the ledger, and it is never an authoring input. A runnable walkthrough lives in [`examples/rule_structure_demo.ipynb`](../../examples/rule_structure_demo.ipynb).

### History

`fg.rules.save` / `.load` / `.list` / `.get` were removed in Slice 6 (Q8 Phase 2). Persistent rule storage is no longer a `fg.rules` responsibility; rules are in-memory authoring values and live wherever the application code keeps them.

`fg.inferences` is currently an **empty namespace** preserved for forward compatibility (see §6.1). Calling `fg.inferences.<anything>` raises `AttributeError`.

## 5. → evaluation (one-line pointer)

`Rule` and `RuleExpr` are *inputs* to the evaluator. The execution surface lives in the next chapters:

- `fg.eval.evaluate(rule_or_expr_or_inference, ...)` — execution entry, returning `EvaluateResult` (see [`evaluate_and_evidence.md`](evaluate_and_evidence.md))
- `engine=` and `semantics=` (`ProbLogSemantics` / `PyReasonSemantics`) — see [`engines_and_configs.md`](engines_and_configs.md)
- `EvaluateRow` / `Explanation` shapes — see [`evaluate_and_evidence.md`](evaluate_and_evidence.md)
- Candidate-fact accept path (Inference only) — see [`evaluate_and_evidence.md`](evaluate_and_evidence.md)

## 6. History note: `Inference` and `Query`

Two earlier rule-shaped assets are still importable but are no longer the primary surface. They are documented here for orientation; new code should reach for `Rule` + `RuleExpr`.

### 6.1 `Inference` — deferred but available

An `Inference` is a `Rule` plus a head (or `emits` clause). Where a `Rule` only matches existing facts, an `Inference` *proposes* new fact candidates — those candidates enter the ledger through a separate accept step.

Shape:

```python
from factgraph.sdk import Inference, EmitSpec, Pred, vars

with vars("u", "tag") as (u, tag):
    derive_tag = Inference(
        id="drv:user_tag_from_seed",
        version="v1",
        when=[Pred("user:tag_seed", u, tag)],
        emits=EmitSpec("user:tag", [u, tag]),
    )
```

Status:

- **Authoring is available** — `Inference`, `EmitSpec`, `Pred`, `Case`, and `fg.eval.evaluate(inference)` all work. There is no removal date.
- **New code prefers `Rule` + `RuleExpr`** — the new path decouples *matching* from *deriving* and lets you join across rule occurrences cleanly.
- **Track 1 is single-head only** — `Inference(head=[...multi...])` is rejected. For multiple heads, write multiple `Inference` values or compose `Rule`s with `RuleExpr`.
- `Inference` is the only context where raw `Pred(...)` atoms are accepted in the `when` body.

Detailed Inference usage:[`docs/official/kernel/quickstart/rules-and-inferences.md`](../official/kernel/quickstart/rules-and-inferences.md) §"Legacy compatibility: evaluate an Inference".

### 6.2 `Query` — fully deferred

`Query(head, where, on_missing, on_type_mismatch)` was the ad-hoc read template — a "build a query object, run it, get rows" shape.

Status:

- **Fully deferred** — still importable, but the source comment classifies it as "legacy DSL value object for internal tests".
- **Successor is `fg.entities.match(...)`** — instead of constructing a `Query`, express the search as a `Rule` (or `RuleExpr`) and project entity snapshots through `match`.

`fg.entities.match` is documented in [`three_layer_api.md`](three_layer_api.md) §2:

> "Replaces the older `Query` mechanism — instead of constructing a query object you express the search as a rule/condition expression, and `match` returns the entities that satisfy it."

There is no separate Query chapter; the `match` surface absorbs the read-projection role.

## 7. Reference

### 7.1 Types

```python
from factgraph.sdk import (
    Rule,                # frozen dataclass: id, when, ports, version, repr
    RuleExpr,            # composition surface (.all / .any / & / |)
    RuleJoinConstraint,  # join descriptor: left, right, op="eq"
    Pred,                # raw predicate-atom factory (legacy; rejected in build_application_rule when)
    Not,                 # negation: Not([body atoms])
    vars,                # logic-var context: with vars("u", "t") as (u, t):
    build_application_rule,  # primary Rule factory (Entity-DSL → Rule)

    # Inspection result types:
    RuleExprInspect,
    OccurrenceInspect,
    ConditionDescriptor,
    PortInspect,

    # Structure projection types (fg.rules.structure):
    RuleStructure,
    StructureBranch,
    StructureOccurrence,
    StructureAtom,
    StructureJoin,
    StructurePort,
    StructurePortRef,
    StructureHeadLink,

    # History (§6):
    Inference,           # Rule + head/emits, legacy still-usable
    EmitSpec,            # head fact emit: target, vars
    Query,               # ad-hoc read, fully deferred — successor: fg.entities.match
)
```

Indirect types reached through methods:

- `RuleOccurrence` — returned by `rule.as_(alias)`
- `RulePortRef` — returned by `occurrence.port(name)`
- `PortType` — `rule.port_types[name]`

### 7.2 Errors

| Error | Raised by |
|---|---|
| `DSLToApplicationRuleError` | `build_application_rule` lowering or validation failure (raw `Pred` in `when`, OR branch lists, `Case`, bare `AttrRef`, port not in body, ...) |
| `RuleExprError` | `RuleExpr` construction (`.join` on OR group, alias conflict, unknown port name, joins not reachable on AND spine, ...) |
| `RuleValidationError` | Direct `Rule(...)` construction failures (empty `when`, port `Var` not in body, malformed `repr` placeholder, ...) |
| `ExplicitBoolError` | `bool(rule)` / `bool(rule_expr)` — i.e. using Python `and` / `or` |

### 7.3 `fg.rules` and `fg.inferences` namespaces

| Namespace | Method | Status |
|---|---|---|
| `fg.rules` | `.inspect(rule_or_expr_or_inference)` | active |
| `fg.rules` | `.structure(rule_or_expr[, head=])` | active (see §4.5) |
| `fg.rules` | `.save` / `.load` / `.list` / `.get` | **removed** (Slice 6 / Q8 Phase 2) |
| `fg.inferences` | *(no methods)* | reserved for forward compatibility |

### 7.4 Related chapters

- [`schema_definition.md`](schema_definition.md) — Entity / Identity / Field declarations that rule bodies reference
- [`data_model.md`](data_model.md) — the Claim / MetaRow shape that rule matches read from
- [`three_layer_api.md`](three_layer_api.md) — `fg.entities.match(...)` (Query's successor)
- [`engines_and_configs.md`](engines_and_configs.md) — `engine=`, `semantics=`, config
- [`evaluate_and_evidence.md`](evaluate_and_evidence.md) — `fg.eval.evaluate` / `explain`, `EvaluateRow` / `Explanation` shapes
- Legacy long-form Rule / Inference reference: [`docs/official/kernel/quickstart/rules-and-inferences.md`](../official/kernel/quickstart/rules-and-inferences.md)
