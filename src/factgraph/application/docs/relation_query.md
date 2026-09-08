# Published Relation Query V1

- Applicable scope: `src/factgraph/application/protocol/relation_query.py` and
  `src/factgraph/application/relation_query_runtime.py`
- Last updated: 2026-08-30
- Audience: application-layer integration, automation, and RPC bridge authors

Published Relation Query V1 is a narrow application-layer contract for
querying a server-resolved graph of stored relationships. It does not accept a
caller-authored rule AST or arbitrary runtime predicate plan. A published graph
names the stored entity fields, stored ternary relations, and endpoint-
continuous paths that a caller may bind or select; the compiler verifies that
publication against the current `SchemaIndex` before producing an executable
invocation.

This is an advanced `factgraph.application` surface. It is not an SDK Query
builder, Product Rule/Policy target, registry, provider execution mechanism, or
HTTP transport.

## 1. Public entry points

Protocol values are exported from `factgraph.application.protocol`:

- `PublishedEntityFieldV1`
- `PublishedStoredRelationV1`
- `RelationPathStepV1`
- `PublishedRelationPathV1`
- `PublishedRelationGraphV1`
- `RelationQuerySourceV1`
- `RelationQueryBindingV1`
- `RelationQuerySelectionV1`
- `PublishedRelationQueryV1`

Compiler and execution values are exported from `factgraph.application`:

- `compile_published_relation_query(...)`
- `execute_published_relation_query(...)`
- `SealedRelationQueryInvocationV1`
- `ResolvedRelationQuerySelectionV1`
- `RelationQueryResultV1`
- `RelationQueryError`

The supported flow is:

```text
PublishedRelationGraphV1 + bindings + selections
                       │
                       ▼
          compile_published_relation_query
                       │
                       ▼
          SealedRelationQueryInvocationV1
                       │
                       ▼
          execute_published_relation_query
                       │
                       ▼
                RelationQueryResultV1
```

Callers never pass raw `where` IR to execution. The lowered IR and selection
variables are private fields of the sealed compiler product.

## 2. Published graph admission

`PublishedRelationGraphV1` carries a non-empty `publication_id` plus three
keyed inventories:

| Inventory | Required schema match |
|---|---|
| `fields` | stored non-relationship predicate; owner entity, value domain, and cardinality must match |
| `relations` | stored relationship predicate with exactly `(from entity, to entity, value)` arguments; endpoints, value domain, and cardinality must match |
| `paths` | known root entity followed by at most 32 published relation steps |

Field, relation, and path keys must each be unique. Path steps may be
`forward` or `reverse`; after applying direction, every step's starting entity
must equal the previous step's ending entity. A discontinuous path fails
admission rather than being reinterpreted.

The protocol enum reserves node kinds `rule`, `provider`, and `scenario`, but
this compiler admits only `stored_field` fields and `stored_relation`
relations. Reserved non-stored kinds fail with
`QUERY_NODE_KIND_FORBIDDEN`. This prevents a publication from smuggling a Rule,
provider, Scenario, or other executable node into the stored-relation query
lane.

## 3. Sources, bindings, and selections

Every query source addresses one published path:

| `kind` | `position` | `member_key` | Value |
|---|---|---|---|
| `entity` | node position, from `0` through the number of steps | must be absent | encoded entity reference at that node |
| `field` | node position | published field key | stored scalar field value on that node |
| `relation_value` | step position | relation key at that exact step | stored relationship value |

A field source must belong to the entity type at its selected path node. A
relation-value source must name the relation used at that exact step. Position,
member, and endpoint mismatches fail with `INVALID_RELATION_QUERY_SOURCE`.

Bindings support `eq`, `ne`, `gt`, `ge`, `lt`, and `le`:

- Entity bindings require a resolved `EntityRef` of the path node's entity
  type and support only `eq` or `ne`.
- Scalar values are validated against the published schema domain.
- Ordering comparisons are restricted to `int`, `float64`, and `time`.
- One source may appear at most once in `bindings`.

Selections must be non-empty and aliases must be unique. Selection order is
preserved in the sealed selection inventory and each result-row mapping.

`row_limit` is part of the published query and must be within `1..100000`.

## 4. Domain guards and virtual existence

Compilation adds the generated `<EntityType>:exists` predicate for every node
of every used path. These predicates are both native conditions and explicit
`domain_guard_predicate_ids`/`dependency_predicate_ids` in the sealed
invocation.

The current projector derives entity-domain rows from complete chosen Identity
Claim bundles. All typed Identity values must reconstruct the same
content-derived `e_ref`; partial, revoked, or mismatched bundles produce no
row. Persisted legacy `:exists` Claims are not consulted. Consequently a
relationship edge cannot make an otherwise nonexistent intermediate entity
joinable merely by mentioning its encoded reference.

## 5. Store and durability boundary

V1 execution is native and operates on the current projection of an
application `Store`. The shipped SDK `Relationship` type is a compile-level
schema declaration: it does not provide relationship CRUD. Canonical v0.3
Database/application entity and field writes remain unary and accept at most
one value term after the subject.

Consequently the current stored ternary relation facts come from an unmanaged
in-memory Store or compatible legacy/imported n-ary data populated below the
SDK facade. Published Relation Query V1 does not add a durable relationship
writer, migrate a workspace, or widen `Database.commit_changes(...)` to
persist ternary assertions. Publication admission and query execution are
read/compile capabilities over relation facts already present in that Store.

## 6. Compiler seal

`compile_published_relation_query(query, schema_index=...)` returns a
`SealedRelationQueryInvocationV1` containing:

- `query_digest`
- `graph_digest`
- `schema_digest`
- `publication_id`
- `row_limit`
- sorted dependency and domain-guard predicate ids
- ordered resolved selection metadata

The query digest commits to the graph and schema digests, publication id, row
limit, dependencies, guards, resolved selections, selection variables, and
lowered native conditions. Reconstructing or replacing private compiler fields
without a matching digest is rejected by the value's invariant check.

The seal is an integrity check for an in-process compiler product. It is not an
authentication signature, authorization decision, historical snapshot, or
public wire codec.

## 7. Execution

`execute_published_relation_query(invocation, store=..., schema_index=...)`:

1. accepts only a `SealedRelationQueryInvocationV1`;
2. rechecks the invocation digest invariant;
3. requires trusted `Store` and `SchemaIndex` values;
4. rejects a runtime schema digest different from the compiler pin;
5. projects the Store's current view, including virtual entity-domain rows;
6. evaluates the private native conditions; and
7. returns `RelationQueryResultV1(query_digest, rows)`.

Rows are a tuple of dictionaries keyed by selection alias. Entity selections
contain encoded entity-reference strings; scalar selections retain their
validated values.

The row limit is fail-closed: when the complete result contains more rows than
the published limit, execution raises `RELATION_QUERY_ROW_LIMIT_EXCEEDED` and
returns no truncated prefix. V1 provides neither pagination nor partial
results.

## 8. Errors

`RelationQueryError` is a `ValueError` with four structured attributes:
`code`, `stage`, `path`, and `details`. `stage` is one of
`graph_admission`, `query_compile`, or `query_execute`.

| Code | Boundary |
|---|---|
| `INVALID_RELATION_QUERY` | compiler input is not `PublishedRelationQueryV1` |
| `INVALID_QUERY_SCHEMA` | compiler schema input is not `SchemaIndex` |
| `PUBLISHED_RELATION_GRAPH_MISMATCH` | published field/relation/path does not match the schema |
| `QUERY_NODE_KIND_FORBIDDEN` | graph contains a non-stored node kind |
| `RELATION_PATH_DISCONTINUITY` | adjacent path endpoints do not connect |
| `UNPUBLISHED_RELATION_PATH` | a binding or selection names an unpublished path |
| `INVALID_RELATION_QUERY_SOURCE` | source kind, member, position, endpoint, or operator is invalid |
| `RELATION_QUERY_BINDING_TYPE_MISMATCH` | scalar binding does not match its published type |
| `INVALID_SEALED_RELATION_QUERY` | executor input is not the compiler product |
| `INVALID_RELATION_QUERY_RUNTIME` | Store or SchemaIndex runtime input is invalid |
| `RELATION_QUERY_SCHEMA_DRIFT` | execution schema differs from the compiler pin |
| `RELATION_QUERY_ROW_LIMIT_EXCEEDED` | complete native result is larger than `row_limit` |

Protocol-shape failures such as duplicate aliases, duplicate binding sources,
an empty selection list, or a row limit outside `1..100000` raise
`ProtocolShapeError` while constructing the frozen DTO, before graph admission.

## 9. Verification anchors

- `tests/application/protocol/test_relation_query.py`
- `tests/test_virtual_entity_domain_projection.py`

These tests cover forward and reverse multi-hop paths, typed comparisons,
schema admission, forbidden node kinds, domain guards, phantom intermediate
entities, row-limit rejection, and compiler-product tamper detection.
