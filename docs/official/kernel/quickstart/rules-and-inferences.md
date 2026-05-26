# Rules and inferences

The previous pages wrote facts directly. Rules and inferences let you describe
patterns over those facts.

A `Rule` asks the graph what is already true. It is a reusable read query over
the current snapshot.

An `Inference` evaluates possible derived rows from existing facts. It does not
write by itself. Evaluation returns an `EvaluateResult`; explicit writes still
go through `fg.write.*` or `fg.batch(...)`.

The short version is:

| Need | Use |
| --- | --- |
| Read matching facts | `Rule` + `fg.eval.evaluate(...)` |
| Propose new facts | `Inference` + `fg.eval.evaluate(...)` |
| Explain evaluated rows | `row.explain()` / `fg.eval.explain(...)` |
| Inspect rule shape | `fg.rules.inspect(...)` |

## Start with facts

Rules and inferences work over facts already in the graph. This example keeps
the schema small: `tag_seed` is a direct fact, and `tag` will be inferred from
it.

```python
from factgraph.sdk import (
    Branch,
    Entity,
    FactGraph,
    Field,
    Identity,
    Inference,
    Pred,
    Query,
    Rule,
    build_application_rule,
    vars,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.tag_seed, alice, "engineer")
```

The predicate id for `User.tag_seed` is `user:tag_seed`. Rule bodies use these
predicate ids to match facts. Later docs cover more advanced authoring patterns;
this page keeps the shape explicit.

## Run a Rule

Use `vars(...)` to create logic variables, `Pred(...)` to match a predicate,
and `Rule(...)` to name the reusable pattern.

```python
with vars("u", "tag") as (u, tag):
    seeded_tags = build_application_rule(
        id="user:tag",
        version="v1",
        where=[User(u), User(u).tag_seed == tag],
        ports={"user": u, "tag": tag},
    )
```

The `where` clause describes what must be found, and `ports` declares what the
rule returns. `build_application_rule(...)` is the canonical SDK bridge that
lowers Entity-DSL atoms into the application protocol `Rule` value. Running
the rule is read-only.

```python
rule_result = fg.eval.evaluate(seeded_tags, head=seeded_tags)

assert rule_result.count() == 1
assert rule_result.first().claim.name == "user:tag"
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()
```

The second assertion matters. The rule found the `tag_seed` fact, but it did
not write a `tag` fact.

## Understanding ports

`ports={...}` is the rule's explicit external interface. Read this section
once; it makes every later cross-rule example readable.

### Three kinds of variables

A `where` body introduces logic variables. The SDK classifies them into
three roles, only one of which is externally visible:

| Kind | Definition | Externally visible? |
| --- | --- | --- |
| free variable | Any variable appearing in `where` | Internal |
| **port** | A free variable explicitly listed in `ports={...}` | ✓ |
| non-port free variable | A free variable not in `ports` | ✗ existential witness only |

Ports are **not collected automatically** — you must declare them
explicitly. The SDK rejects construction if a declared port's `Var` is
not present in `where`, or if `ports` is empty.

```python
with vars("u", "r") as (u, r):
    user_in_region = build_application_rule(
        id="user:region",
        version="v1",
        where=[User(u), User(u).region == r],
        ports={"user": u, "region": r},   # both u and r exposed
    )
```

### Port types are inferred from atoms

`rule.port_types` returns a mapping from port name to a `PortType` with
`kind` (`"entity_ref"` or `"value"`) and `entity_type` (only set when
`kind == "entity_ref"`). Inference is automatic from the body:

- `Entity(var)` in `where` → the port for `var` is `entity_ref` of that entity type;
- `Entity(var).field == value` → the port for `value` is `value`.

```python
assert user_in_region.port_types["user"].kind == "entity_ref"
assert user_in_region.port_types["user"].entity_type == "User"
assert user_in_region.port_types["region"].kind == "value"
assert user_in_region.port_types["region"].entity_type is None
```

### `ports` is not the result shape

`ports` declares what **can** be exposed for cross-rule composition and
result projection. It does not specify what the result rows look like —
that is the head's job (see [Choosing the right head](#choosing-the-right-head)).

You can have a rule with three ports and use it as `head=` to project all
three, or use it inside a `RuleExpr` and only join on one of them. Ports
define the contact surface, not the output.

### `desc` can interpolate port names

A rule's `desc` is a natural-language template. Use `%port_name` to
reference declared ports. Unbound renders fall back to the literal
`<port_name>` placeholder; unknown ports are rejected at construction.

```python
with vars("u", "r") as (u, r):
    described = build_application_rule(
        id="user:region",
        version="v1",
        desc="user %user lives in region %region",
        where=[User(u), User(u).region == r],
        ports={"user": u, "region": r},
    )

assert described.render_desc() == "user <user> lives in region <region>"
assert described.render_desc({"user": "alice", "region": "US"}) == \
    "user alice lives in region US"
```

Referencing a name that is not a declared port raises
`RuleValidationError: desc references undeclared port: <name>` at
construction.

## Composing rules with RuleExpr

A single `Rule` is one read pattern. Real questions usually compose
several rules: "users in a region who placed an order in that same
region." The composition surface is `RuleExpr`, reached through
`rule.as_(...)`, `&` / `|`, and the `.join_by_ports` / `.join`
attachments.

### Setup: two rules with a shared port name

```python
class User(Entity):
    user_id: str = Identity(primary_key=True)
    region: str = Field(cardinality="single")


class Order(Entity):
    order_id: str = Identity(primary_key=True)
    buyer: str = Field(cardinality="single")
    region: str = Field(cardinality="single")


with vars("u", "r") as (u, r):
    user_region = build_application_rule(
        id="user:region",
        version="v1",
        where=[User(u), User(u).region == r],
        ports={"user": u, "region": r},
    )

with vars("o", "r") as (o, r):
    order_region = build_application_rule(
        id="order:region",
        version="v1",
        where=[Order(o), Order(o).region == r],
        ports={"order": o, "region": r},
    )
```

Both rules expose a port called `region`. That naming is intentional —
we want to join on it.

### `rule.as_("alias")` and occurrence ports

Wrap each rule in a `RuleOccurrence` with an alias:

```python
u_ = user_region.as_("u_")
o_ = order_region.as_("o_")
```

The alias must match `[A-Za-z][A-Za-z0-9_]*`. **The default alias is
`rule.id`**, so calling `.as_()` without an argument on a rule whose id
contains `:` (such as `User:exists`) raises
`RuleValidationError: occurrence alias must match [A-Za-z][A-Za-z0-9_]*`.
Always pass an explicit alias for ids that are predicate-shaped.

From an occurrence you can reach a port either by method or attribute
proxy:

```python
ref = u_.port("region")          # -> RulePortRef
same = u_.region                  # __getattr__ proxy, same RulePortRef shape

assert ref.rule_id == "user:region"
assert ref.port_name == "region"
assert ref.port_type.kind == "value"
```

### `&` / `|` and `RuleExpr.all` / `.any`

`&` makes an AND group; `|` makes an OR group. The factory forms
`RuleExpr.all(...)` and `RuleExpr.any(...)` are equivalent:

```python
and_group = u_ & o_                    # same as RuleExpr.all(u_, o_)
or_group  = u_ | o_                    # same as RuleExpr.any(u_, o_)
```

### Same-named ports raise without an explicit join

Composing two rules that share a port name and **not** joining them is
rejected:

```python
# RuleExprError: declared port 'region' is ambiguous across occurrences: o_, u_
fg.eval.evaluate(u_ & o_, head=user_region)
```

The SDK refuses to guess whether you meant the two `region` ports to be
the same value or independent — you must say so explicitly.

### `.join_by_ports("region")` — the common case

When both occurrences have the same port name and you want them bound to
the same value:

```python
expr = (u_ & o_).join_by_ports("region")
result = fg.eval.evaluate(expr, head=user_region)
```

You can pass several port names: `.join_by_ports("region", "city")`.

### `.join(constraint)` — when port names differ

Use an explicit `RulePortRef.eq(...)` constraint when the two ports
have different names, or when you want the constraint expressed
symmetrically:

```python
expr = (u_ & o_).join(u_.region.eq(o_.region))
result = fg.eval.evaluate(expr, head=user_region)
```

### AND-spine reachable: joins must attach to AND groups

`.join_by_ports(...)` and `.join(...)` only attach to AND groups:

- `single_occurrence.join(...)` raises `AttributeError` — a single
  occurrence is not a group;
- `(u_ | o_).join(...)` raises
  `RuleExprError: RuleExpr joins must be attached to AND groups; distribute joins into OR branches`.

When you need a path-dependent join, distribute it manually across the
OR branches. Each branch carries its own `.join_by_ports(...)` (or
`.join(...)`) instead of trying to lift the constraint over an OR
boundary.

### End-to-end cross-rule example

```python
fg = FactGraph.create(schema_classes=[User, Order])

alice = fg.read.ref(User, user_id="alice"); fg.write.set(User.region, alice, "US")
bob   = fg.read.ref(User, user_id="bob");   fg.write.set(User.region, bob,   "DE")

o1 = fg.read.ref(Order, order_id="o1"); fg.write.set(Order.region, o1, "US")
o2 = fg.read.ref(Order, order_id="o2"); fg.write.set(Order.region, o2, "DE")
o3 = fg.read.ref(Order, order_id="o3"); fg.write.set(Order.region, o3, "DE")

u_ = user_region.as_("u_")
o_ = order_region.as_("o_")
expr = (u_ & o_).join_by_ports("region")

result = fg.eval.evaluate(expr, head=user_region)
# 2 user rows: alice has matching o1 in US; bob has matching o2 and o3 in DE
assert result.count() == 2
```

## Choosing the right head

`fg.eval.evaluate(expr, head=rule)` projects evaluation results through
`head`. The rule passed as `head=` has two invariants:

1. **`head.id` must be a real predicate id.** The result row's
   `claim.name` equals `head.id`.
2. **`len(head.ports)` must equal that predicate's `arg_specs` count.**
   Otherwise the runtime raises
   `WhereValidationError: head_vars length must match target arg_specs`.

In practice this means:

| Head rule port count | Use a head whose id is |
| --- | --- |
| 1 | the entity existence predicate (`Entity:exists`) |
| 2 | a field predicate (`entity:field`) |
| 3+ | not directly supported; restructure the head |

The simplest pattern is `head=rule` itself when the rule's id already
matches a real predicate with matching arity:

```python
with vars("u",) as (u,):
    user_exists = build_application_rule(
        id="User:exists",      # 1-arg predicate
        version="v1",
        where=[User(u)],
        ports={"user": u},      # 1 port matches arg arity
    )

result = fg.eval.evaluate(user_exists, head=user_exists)
assert result.first().claim.name == "User:exists"
```

For two-port rules use a two-arg field predicate id:

```python
with vars("u", "r") as (u, r):
    user_region = build_application_rule(
        id="user:region",      # 2-arg predicate (user_ref, region_string)
        version="v1",
        where=[User(u), User(u).region == r],
        ports={"user": u, "region": r},
    )

first = fg.eval.evaluate(user_region, head=user_region).first()
assert first.claim.name == "user:region"
```

### Cross-rule expressions pick one occurrence as head

When you evaluate a multi-rule expression, `head=` is **one** of the
rules involved. Use either rule's underlying template; the SDK matches
it against the in-expression occurrence by content digest:

```python
u_ = user_region.as_("u_")
o_ = order_region.as_("o_")
expr = (u_ & o_).join_by_ports("region")

# either of these is valid:
result_u = fg.eval.evaluate(expr, head=user_region)   # rows keyed by user:region
result_o = fg.eval.evaluate(expr, head=order_region)  # rows keyed by order:region
```

Passing a head Rule that shares an id with an in-expression occurrence
but has a different `content_digest` raises
`RuleExprError: head rule '<id>' matches an expression occurrence with a different content digest`.

### `Rule.projection(*names)` is not an evaluate head

The protocol exports `Rule.projection("a", "b", ...)`, which constructs
a synthetic projection rule whose id is `__factgraph_projection__<hash>`.
**This is not usable as an `evaluate` head in v0.2** — the runtime
raises `WhereValidationError: target predicate not found: __factgraph_projection__<hash>`.

It is reserved for `RuleExpr` inspection and mocked-evaluation tests
only. Use the field-predicate or existence-predicate head pattern
instead.

## Use Query for one-off projections

`Query` remains a DSL value object for internal and future read-projection
work, but the T5 public runtime path no longer exposes `fg.eval.run(...)`.
Use `fg.read.find(...)` for snapshot reads or an application `Rule` with
`fg.eval.evaluate(...)` when you need replay anchors and evidence.

```python
with vars("u", "tag") as (u, tag):
    seeded_tag_query = Query(
        head=[User(u), User.tag_seed(value=tag)],
        where=[User(u), u.tag_seed == tag],
    )


snapshot = fg.read.get(User, user_id="u-1")
assert snapshot is not None
assert snapshot.tag_seed == "engineer"
```

Queries are read-time projections. They are useful for one-off shapes. Rules
and inferences remain Python value objects; keep reusable definitions in code
or application configuration.

## Evaluate an Inference

An inference can use the same body and propose a new target predicate.

```python
with vars("u", "tag") as (u, tag):
    tags_from_seed = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[
            Branch(
                [Pred("user:tag_seed", u, tag)],
                id="seed_path",
            )
        ],
        target="user:tag",
        head_vars=[u, tag],
    )
```

`fg.eval.evaluate(...)` returns an `EvaluateResult`. It is read-only.

```python
result = fg.eval.evaluate(tags_from_seed)

assert result.count() == 1
row = result.first()
assert row is not None
assert row.claim.name == "user:tag"
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()
```

The row says "this inference can derive `user:tag` for this user with this
value." It has not changed the graph.

## Explain a row

```python
explanation = row.explain()
closed_head = row.close()
manual = fg.eval.explain(tags_from_seed, head=closed_head)

assert explanation.status == "passed"
assert manual.status == "passed"
```

Use explicit write APIs when you want to persist new facts.

## Inspect rule shape

`fg.rules.inspect(...)` shows the structure of a rule or inference without
executing it.

```python
inspected = fg.rules.inspect(tags_from_seed)

assert inspected["kind"] == "Inference"
assert inspected["id"] == "inf.tags_from_seed"
assert inspected["branches"][0]["id"] == "seed_path"
assert inspected["branches"][0]["fallback_id"] == "b0"
assert inspected["branches"][0]["atom_count"] == 1
```

Branch ids are structural names. Use explicit branch ids when a rule has
meaningful pathways that you may want to inspect or configure later. If you do
not provide an id, the SDK still exposes a fallback id such as `b0`.

## RuleRef composes in-memory rules

`RuleRef` is a lower-level body atom used when one rule body depends on another
rule. It is not a persistence handle and it does not read from a filesystem
registry.

In the quickstart, keep the model simple:

- `Rule` reads.
- `Inference` proposes.
- `EvaluateResult` rows wait for review.
- explicit writes persist changes.
- Keep reusable rule/inference definitions in Python code and pass the value
  objects directly to runtime methods.

## Where semantics engines fit

The default examples here use the native evaluation path. FactGraph also has
semantics options for engines such as ProbLog and PyReason. Those options
change how an inference is evaluated; they do not change the basic lifecycle:

```text
Inference -> evaluate -> EvaluateResult rows -> explain/close -> explicit writes if needed
```

Learn the lifecycle first. Engine-specific semantics are an advanced topic.

## Stability of `Inference` and `Branch`

Application `Rule` (built via `build_application_rule(...)`) is the
preferred read-pattern surface for new code in v0.2. `Inference` and
`Branch` remain available as the compatibility surface: same
`EvaluateResult` / `EvaluateRow` / `Explanation` shapes, same lower
evaluation pipeline. The design has committed to retiring `Branch` from
user-facing layers and folding `Inference` into a `RuleExpr`-based
runtime entry in a later cycle, but the migration spec is pending a
future blueprint and **no `DeprecationWarning` is raised in v0.2**.

For the full positioning (invariants, what to use for new code, why
`build_application_rule` rejects `Branch`), see
[`evidence.md` §7 Stability of `Inference` and `Branch`](evidence.md).

## Complete example

```python
from factgraph.sdk import (
    Branch,
    Entity,
    FactGraph,
    Field,
    Identity,
    Inference,
    Pred,
    Query,
    Rule,
    build_application_rule,
    vars,
)


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")


fg = FactGraph.create(schema_classes=[User])

alice = fg.read.ref(User, user_id="u-1")
fg.write.set(User.tag_seed, alice, "engineer")

with vars("u", "tag") as (u, tag):
    seeded_tags = build_application_rule(
        id="user:tag",
        version="v1",
        where=[User(u), User(u).tag_seed == tag],
        ports={"user": u, "tag": tag},
    )

rule_result = fg.eval.evaluate(seeded_tags, head=seeded_tags)

assert rule_result.count() == 1

with vars("u", "tag") as (u, tag):
    seeded_tag_query = Query(
        head=[User(u), User.tag_seed(value=tag)],
        where=[User(u), u.tag_seed == tag],
    )

snapshot = fg.read.get(User, user_id="u-1")
assert snapshot is not None
assert snapshot.tag_seed == "engineer"

with vars("u", "tag") as (u, tag):
    tags_from_seed = Inference(
        id="inf.tags_from_seed",
        version="v1",
        where=[Branch([Pred("user:tag_seed", u, tag)], id="seed_path")],
        target="user:tag",
        head_vars=[u, tag],
    )

result = fg.eval.evaluate(tags_from_seed)

assert result.count() == 1
assert tuple(fg.read.get(User, user_id="u-1").tag) == ()

fg.write.add(User.tag, alice, "engineer")
assert tuple(fg.read.get(User, user_id="u-1").tag) == ("engineer",)

inspected = fg.rules.inspect(tags_from_seed)

assert inspected["kind"] == "Inference"
assert inspected["branches"][0]["id"] == "seed_path"
assert inspected["branches"][0]["fallback_id"] == "b0"
```

## Syntax checklist

- Use `vars(...)` to create logic variables for DSL bodies.
- Use `Pred("entity:field", ...)` for explicit predicate literals inside
  `Inference` bodies.
- Use `Branch([...], id="...")` inside `Inference` bodies when branch identity
  matters; application `Rule` accepts only AND-flat bodies.
- Use `build_application_rule(id=..., where=[Entity(var), ...], ports={...})`
  to construct application `Rule` values via the canonical SDK bridge.
- Declare `ports={...}` explicitly; the SDK does not auto-collect them.
  Inspect inferred port types via `rule.port_types`.
- Use `desc="...%port_name..."` for natural-language templates;
  `rule.render_desc(bindings)` substitutes values, unknown ports are
  rejected at construction.
- Use `rule.as_("alias")` to obtain a `RuleOccurrence` for composition.
  Pass an explicit alias when the rule id is predicate-shaped (contains
  `:`), because the default alias is the id itself.
- Compose with `R1 & R2` / `R1 | R2` (or `RuleExpr.all(...)` /
  `RuleExpr.any(...)`).
- Resolve same-named ports with `.join_by_ports("name", ...)` or use
  `.join(occ_a.port.eq(occ_b.port))` for explicit cross-port equality.
  Same-named ports without an explicit join raise
  `RuleExprError: declared port ... is ambiguous across occurrences`.
- `.join(...)` attaches only to AND groups; distribute path-dependent
  joins manually across OR branches.
- `head=rule` requires `rule.id` to be a real predicate with matching
  arg arity. `Rule.projection(...)` is not an evaluate head in v0.2.
- Evaluate rules with `fg.eval.evaluate(rule, head=rule)`; evaluation does not write.
- Use read APIs for ad-hoc projections; public `fg.eval.run(...)` was removed.
- Use `Inference(id=..., where=[...], target=..., head_vars=[...])` for
  proposed facts.
- Evaluate inferences with `fg.eval.evaluate(inference)`; evaluation does not
  write.
- Explain rows with `row.explain()` or replay with
  `fg.eval.explain(expr, head=row.close())`.
- Inspect rule or inference structure with `fg.rules.inspect(...)`.
- `RuleRef` is a body-composition tool, not a persistence handle.
- Rule and inference persistence handles were removed; runtime methods consume
  in-memory value objects directly.
- Semantic engines are evaluation configuration; the evaluate/explain lifecycle
  stays the same.
