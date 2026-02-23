# Fact Store

This package provides utilities for loading fact data from external sources into canonical
`Instance` objects.

## CSVProvider (predicate schema based)

`CSVProvider` works with predicate schemas from `symir.ir.fact_schema` (Fact/Rel). It returns
canonical `Instance` objects, one per CSV row.

You can pass either a `FactLayer` or a `FactView` to `CSVProvider`. If you pass a view, it is
stored as the default filter; calling `query()` with no arguments will use that view.

`CSVProvider` also supports optional datatype casting via `datatype_cast`:

- `none` (default): keep all values as strings
- `coerce`: best-effort cast for `int/float/bool`, otherwise keep string
- `strict`: cast must succeed for supported types, unknown datatypes are errors
- bool values accepted in cast mode: `true/false/1/0/yes/no` (case-insensitive)

`CSVSource.schema` requires a `Fact/Rel` object.

```python
from pathlib import Path
from symir.ir.fact_schema import Entity, Value, Fact, Rel, FactLayer
from symir.fact_store.provider import CSVProvider, CSVSource

person = Fact(
    "person",
    [Entity("Name", "string"), Value("address", "string")],
)
city = Fact(
    "city",
    [Entity("Name", "string"), Value("Country", "string")],
)
lives_in = Rel("lives_in", sub=person, obj=city, props=[Value("since", "int")])

schema = FactLayer([person, city, lives_in])
sources = [
    CSVSource(schema=person, file="people.csv", columns=["Name", "address"]),
    CSVSource(schema=city, file="cities.csv", columns=["Name", "Country"]),
    # For rels, columns map to rel signature: sub_*/obj_* endpoint keys + props.
    CSVSource(schema=lives_in,
        file="lives_in.csv",
        columns=["sub_Name", "obj_Name", "since"],
    ),
]

provider = CSVProvider(
    schema=schema,
    base_path=Path("data"),
    sources=sources,
    datatype_cast="coerce",
)
instances = provider.query(schema.view(schema.predicates()))

# Or pass a view directly and call query() without arguments.
view = schema.view([person, city])
provider_from_view = CSVProvider(schema=view, base_path=Path("data"), sources=sources)
instances = provider_from_view.query()
```

Each CSV row becomes one `Instance`. If you need richer provenance (source, trace ids, etc.),
attach metadata at ingestion time.

Runtime behavior summary:

- `query(view=None, filt=None)` resolves predicates from explicit `view`, default view, or full schema.
- each allowed predicate must have a matching `CSVSource`.
- missing mapping error format: `Missing CSV source mapping for schema_id: <id> (name=<predicate_name>).`
- CSV headers are normalized with `strip()`.
- values are read by `columns` order and then mapped to predicate signature order.
- row probability uses `prob_column` when present, otherwise provider probability defaults.
- `CSVSource.schema` must be a predicate schema object (`Fact`/`Rel`), not a raw schema id string.
- `CSVProvider` indexes source mappings by `source.schema.schema_id` internally.

For rel schemas, mapping is strictly by `Rel.signature` order (not by header name):

```python
lives_in = Rel("lives_in", sub=person, obj=city, props=[Value("since", "int")])
[arg.name for arg in lives_in.signature]
# -> ["sub_Name", "obj_Name", "since"]
```

So `columns=["person", "city", "since_col"]` is valid and maps positionally:

- `person -> sub_Name`
- `city -> obj_Name`
- `since_col -> since`

For composite endpoint keys, rel signature expands accordingly, e.g.
`["sub_Name", "sub_Address", "obj_Name", ...]`, and CSV columns must follow that order.

Common setup error:

- `TypeError: unhashable type: 'list'` usually means schema objects were used as dict keys in custom code.
- fix: key custom maps by `schema.schema_id` (string), not by schema object instances.

## RelBuilder (match facts + rows)

Use `RelBuilder` when you need to create relations by matching existing fact instances.
`rows` is a list of dicts. CSV is just one source for those rows.
`CSVProvider.query(...)` does not run this join automatically; call `provider.build_relations(...)`.

```python
from symir.fact_store.rel_builder import RelBuilder

builder = RelBuilder(
    rel=lives_in,
    match_keys=["person", "city"],
    match_props=["since"],
    key_mode="partial",
    multi="cartesian",
)

rel_source = CSVSource(schema=lives_in,
    file="lives_in.csv",
    columns=["person", "city", "since"],
    prob_column="prob",
)

facts = provider.query(schema.view([person, city]))
rels = provider.build_relations(
    builder=builder,
    facts=facts,
    source=rel_source,
    maps={"person": "person_name", "city": "city_name"},
)
```

Notes:

- `columns` are logical row keys consumed by `RelBuilder`.
- `maps` maps logical keys to CSV column names.
- `CSVSource` (`file/columns/prob_column`) is IO configuration only.
- `RelBuilder` (`match_keys/key_mode/match_props/multi`) controls matching behavior.
- If `match_keys` is omitted, the builder expects `sub_<Key>` / `obj_<Key>` columns by default.
- default `sub_<Key>` / `obj_<Key>` matching is case-sensitive.
- `match_keys` list form works only for single-key endpoints.
- list-form `match_keys` supports optional `"<row_key>:<key_field>"` syntax (single-key endpoints only).
- For composite endpoint keys, use dict form:

```python
builder = RelBuilder(
    rel=lives_in,
    match_keys={
        "sub": {"Name": "person_name", "Address": "person_address"},
        "obj": {"Name": "city_name"},
    },
)
```

- `key_mode="strict"` requires all endpoint key fields in each row.
- `key_mode="partial"` allows missing keys and performs partial filtering.
- `match_props` changes relation dedup identity, not fact endpoint matching.
- `match_props=None` disables dedup inside the builder.
- `multi="error"` fails on multi-match; `multi="cartesian"` emits cartesian combinations.

`RelBuilder` can also run directly on in-memory rows (non-CSV sources):

```python
from symir.fact_store.rel_builder import RelBuilder, ROW_PROB_KEY

rows = [{"sub_Name": "alice", "obj_Name": "berlin", "since": 2020, ROW_PROB_KEY: 0.8}]
builder = RelBuilder(rel=lives_in, key_mode="strict")
rels = builder.build(facts=facts, rows=rows, registry=schema, datatype_cast="coerce")
```

Common errors:

- `SchemaError: match_keys list requires single key per endpoint.`
- use dict-form `match_keys` when either endpoint has composite key fields.
- `SchemaError: Missing obj key fields in row: [...]`
- add missing key columns, switch to `key_mode="partial"`, or change endpoint `key_fields`.

## CsvFactStore (mapping schema based)

`CsvFactStore` is a separate loader that uses the lightweight mapping schema in
`symir.ir.schema`. It yields `IRAtom` objects for rule evaluation and is kept for
backwards compatibility with the older CSV mapping format.

## Neo4jComponent (non-invasive)

`Neo4jComponent` is an optional writer for Neo4j. It does not change existing provider flows.
You can use it in two modes:

- example-style import (`schema + nodes + rels`)
- project-native import (`FactSchema/FactView + Instance` list)

```python
from symir.fact_store.neo4j_component import Neo4jCfg, Neo4jComponent

cfg = Neo4jCfg(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="your-password",
    database="neo4j",
)
writer = Neo4jComponent(cfg)
```

Example-style import (similar to `example_neo4j.txt`):

```python
schema = {"nodes": {"Person": ["name"], "Company": ["name"]}}
nodes = {"Person": ["alice"], "Company": ["openai"]}
rels = {("Person", "works_at", "Company"): [("alice", "openai")]}
writer.import_graph(schema=schema, nodes=nodes, rels=rels)
```

Project-native import:

```python
instances = provider.query(schema.view([person, company, lives_in]))
writer.import_instances(schema=schema, instances=instances)
```

Render first, execute later:

```python
script = writer.render_cypher_for_instances(schema=schema, instances=instances)
print(script)
writer.execute_cypher(script)
```

Notes:

- `import_instances(...)` first renders Cypher via `CypherRenderer`, then executes those statements.
- live execution requires `neo4j` Python driver (`pip install neo4j`).
- you can inject a custom `runner` into `Neo4jComponent` for testing or external transaction management.
