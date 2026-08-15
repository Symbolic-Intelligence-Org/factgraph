# Runtime capabilities introspection

`fg.meta.capabilities()` returns the set of enumeration values the runtime currently accepts at API boundaries — for callers that need to discover supported field shapes programmatically (e.g. UI form builders, schema migration tools, codegen).

```python
from factgraph.sdk import FactGraph

fg = FactGraph.create(schema_classes=[...])
caps = fg.meta.capabilities()
```

## 1. Returned shape

`caps` is a frozen `MappingProxyType` of `frozenset[str]` values:

```python
{
    "value_kinds":   frozenset({"scalar", "entity_ref"}),
    "scalar_tags":   frozenset({"string", "int", "float64", "bool", "bytes", "time", "uuid"}),
    "cardinalities": frozenset({"single", "multi"}),
}
```

| Key | What it lists | Where each value applies |
|---|---|---|
| `value_kinds` | High-level field-value kinds | `Field.value_kind` on the schema-runtime DTO (see [`schema_definition.md`](schema_definition.md)) |
| `scalar_tags` | Primitive type tags for scalar literals | the `tag` field on a `literal` typed term (see [`evaluate_and_evidence.md`](evaluate_and_evidence.md) §2.2 bindings) |
| `cardinalities` | Field cardinality values | `Field.cardinality` on the schema-runtime DTO |

## 2. Immutability

- The outer mapping is `MappingProxyType` — mutating it raises `TypeError`.
- Every value is a `frozenset` — `.add(...)` / `.remove(...)` raise `AttributeError`.
- `fg.meta` itself is a read-only namespace — `fg.meta.foo = ...` raises `FrozenSnapshotError`.

The intent: callers can cache and share the result across threads / processes without defensive copying.

## 3. What it is *not*

- Not a contract for future SDK versions — values may grow when new types ship; consume the result, don't hardcode against it.
- Not an exhaustive feature flag — only enumeration-style boundaries are reported. Cross-cutting capabilities (engine support, transaction modes, etc.) are not in scope here.
- Not a constraint schema — there's no `constraint_kinds` key today because the runtime has no declarative constraint system; if one ships, it will appear in `capabilities()` then.
- Not a registry of Product Rules, Policies or Functions. Those are immutable
  graph-bound assets returned directly by builders; Product Function is not a
  remotely discoverable or callable tool registry.
- Not an execution-support matrix. Native/Soufflé/ProbLog support, Scenario
  uncertainty and `WeightedChoice` are selected by a target-pinned Product V2
  execution profile and fail closed when unsupported.

## 4. Use it for

```python
# Generate a form field selector for an unknown schema
caps = fg.meta.capabilities()
for tag in sorted(caps["scalar_tags"]):
    render_radio_button(tag)

# Validate user-supplied schema input before passing to the runtime
if user_field["cardinality"] not in caps["cardinalities"]:
    raise ValueError(f"unsupported cardinality: {user_field['cardinality']!r}")
```

## 5. Related

- [`schema_definition.md`](schema_definition.md) — where `value_kind` / `cardinality` are declared on a `Field`
- [`evaluate_and_evidence.md`](evaluate_and_evidence.md) §2.2 — where `scalar_tags` appear inside `row.bindings` typed-term dicts
- [`product_workflow_v2.md`](product_workflow_v2.md) — Product assets, execution profiles and structured Result/Explain
