# Overview of the Application Module (`factpy_kernel`)

* Scope: `src/factpy_kernel/application`
* Last updated: 2026-03-10
* Target readers: developers who need to understand the middle layer of the entity-centric runtime, the SDK delegation boundary, and the subsequent service integration entry points

## 1. Module Responsibilities

`application` is a **neutral runtime layer above core**.

It is responsible for extracting the entity-centric runtime mechanisms that were previously scattered across the SDK facade into a set of shared capabilities, so that:

* `sdk` can continue to provide the Python authoring / facade experience
* `service` can directly depend on neutral read/write/query/projection capabilities

It is currently responsible for:

* protocol DTOs
* schema runtime indexing and selector/ref resolution
* entity hydration / read requests
* entity write planning / apply
* read/write delegation handoff points for the SDK facade

It is currently not responsible for:

* replacing the Python facade surface of `SDKStore` / `SDKBatchTx`
* HTTP / session / registry routing
* the complete implementation of graph projection / relationship family / binding
* unified middle-layer handling for query lowering/runtime hydration

## 2. Current Module Structure

* `protocol/`

  * canonical DTOs for the application layer
* `schema_runtime.py`

  * `SchemaIndex`, field types, selector/ref resolution
* `entity_view.py`

  * entity hydration, `execute_read_request(...)`
* `entity_write.py`

  * write planning, `apply_write_plan(...)`
* `__init__.py`

  * currently exported middle-layer entry points

## 3. Currently Implemented Capabilities

### 3.1 protocol

Currently defined:

* common DTOs
* schema runtime DTOs
* entity read DTOs
* entity write DTOs

Boundaries:

* uses `dataclass(frozen=True)`
* the protocol layer only accepts JSON-safe values and structured `EntityRef` / `EntitySelector`
* does not bring SDK descriptor / metaclass semantics into the middle layer

### 3.2 schema runtime

Currently implemented:

* `build_schema_index(...)`
* `resolve_selector(...)`
* `materialize_identity(...)`
* `field_predicate(...)`
* `field_value_type(...)`
* `encode_entity_ref(...)`
* `entity_type_from_ref(...)`

It provides a unified schema runtime index for the read/write path, no longer relying on the internal indices of `SDKStore`.

### 3.3 entity view

Currently implemented:

* `hydrate_entity(...)`
* `hydrate_entities(...)`
* `execute_read_request(...)`

Implementation approach:

* based on `Store + Ledger + project_view_facts(...)`
* restores canonical identity from identity predicates
* outputs `EntitySnapshotDTO`, current field values, and assertions/history

### 3.4 entity write

Currently implemented:

* `plan_write_command(...)`
* `apply_write_plan(...)`

Current capabilities include:

* target selector resolution
* dependency entity ref resolution
* `set/add/retract` planning
* `record_exists` / identity materialization
* single-target application-level apply

## 4. Relationship with Other Layers

* `core`

  * `application` directly depends on lower-level primitives such as `Store`, `Ledger`, `projector`, and the write protocol
* `sdk`

  * the SDK facade has already begun delegating to `application`
  * the SDK remains responsible for facade compatibility and Python ergonomics
* `service`

  * in the future, it should depend directly on `application` rather than on `SDKStore`
* `frontend`

  * does not depend directly on `application`
  * should obtain capabilities through `service` DTOs

## 5. Current SDK Delegation Status

### 5.1 Read side

The SDK currently delegates the following read capabilities to `application`:

* `sdk_get(...)`
* `sdk_find(...)`
* `_build_snapshot(...)`

Compatibility strategy:

* the outward shape of the SDK remains unchanged
* the `entity_ref` field is still presented as an encoded ref string
* `FieldAssertions` / `AssertionRecord` still retain SDK facade types
* filtering semantics are still conservatively retained in the SDK adaptation layer

### 5.2 Write side

The SDK currently delegates the following main batch-write path to `application`:

* `SDKBatchTx.preview()`
* `BatchPlan.apply()`

The current strategy is conservative delegation:

* when the entire batch of staged writes can be expressed by the application protocol, it goes through the application planner/apply path
* otherwise, the entire batch falls back to the legacy batch path

## 6. Current Conservative Boundaries

The following boundaries are still retained and are intentionally not crossed by the current implementation:

* SDK batch delegation to `application` only happens when the entire batch of staged writes can be expressed by the application protocol
* if the batch contains raw `entity_ref` tokens, `bytes`, non-JSON-safe meta, or values that the application planner cannot represent stably, the entire batch falls back to legacy
* `BatchPlan.ops` / `export()` / `to_json()` / `WireBatchPlan.apply()` retain legacy semantics
* `entity_write.py` currently uses single-target `EntityWriteCommand` as the canonical planner and does not directly express multi-root atomic batch
* temporal read/write has not yet been unified at the application layer

## 7. Currently Unfinished Parts

The following capabilities have not yet been implemented in the `application` layer:

* `query_view.py`
* `authoring_normalize.py`
* `graph_projection.py`
* `binding.py`

This means that the current “core migration objective” has already been validated as complete, but the subsequent phases of the Blueprint have not yet been implemented.

## 8. Current Test Entry Points

The following command can be used for core regression:

```bash
PYTHONPATH=src python -m unittest \
  factpy_kernel.tests.test_application_protocol \
  factpy_kernel.tests.test_application_schema_runtime \
  factpy_kernel.tests.test_application_entity_view \
  factpy_kernel.tests.test_application_entity_write \
  factpy_kernel.tests.test_sdk_facade_application_delegate \
  factpy_kernel.tests.test_sdk_batch_application_delegate \
  factpy_kernel.tests.test_phase3_contracts_v1
```

These tests cover:

* application protocol / schema runtime / read / write
* SDK read delegation
* SDK batch write delegation
* post-migration facade compatibility

## 9. Related Documents

* [blueprints/README.md](/Users/zhenzhili/symbolic_agent/docs/blueprints/README.md)

  * task blueprint workflow, state machine, and archive rules
* [application_projection_blueprint.md](/Users/zhenzhili/symbolic_agent/docs/blueprint_history/application_projection_blueprint.md)

  * historical architecture blueprint, migration phases, and later planning
* [application_protocol_spec.md](/Users/zhenzhili/symbolic_agent/docs/blueprint_history/application_protocol_spec.md)

  * historical application protocol draft
* [frontend_entity_ui_design.md](/Users/zhenzhili/symbolic_agent/docs/blueprint_history/frontend_entity_ui_design.md)

  * historical entity/rule UI target expression for graph projection
