"""Current SDK schema transitions validate durable anchors, without a registry."""

import sqlite3
from pathlib import Path

import pytest

from factgraph.core.schema.schema_ir import canonicalize_schema_ir_jcs, schema_digest
from factgraph.core.store.database import (
    resolve_database_workspace_paths,
    validate_schema_object_for_workspace,
)
from factgraph.sdk import (
    Entity,
    FactGraph,
    Field,
    Identity,
    SchemaConflictError,
    SchemaNonAdditiveError,
    SDKStoreError,
    compile_schema_from_classes,
)


class Account(Entity):
    account_id: str = Identity()


def _person(*, nickname=False):
    annotations = {"person_id": str, "name": str}
    namespace = {"__annotations__": annotations, "person_id": Identity(), "name": Field()}
    if nickname:
        annotations["nickname"] = str
        namespace["nickname"] = Field()
    return type("Person", (Entity,), namespace)


def _seed(workspace):
    person = _person()
    graph = FactGraph.create(schema_classes=[person], path=workspace)
    ref = graph.entities.create(person, person_id="alice")
    graph.fields.set(person.name, ref, "Alice")
    return graph, person


def _persisted_metadata(workspace):
    """Observe committed v0.3 anchors through an independent read-only connection."""
    assertions = resolve_database_workspace_paths(workspace).assertions
    connection = sqlite3.connect(f"{assertions.as_uri()}?mode=ro", uri=True)
    try:
        return dict(connection.execute("SELECT key, value FROM ledger_meta"))
    finally:
        connection.close()


@pytest.mark.parametrize("change", ["field", "entity"])
def test_schema_apply_persists_new_anchor_and_reopens_without_explicit_save(tmp_path: Path, change):
    workspace = tmp_path / "workspace"
    graph, person = _seed(workspace)
    addition = _person(nickname=True) if change == "field" else Account
    classes = [addition] if change == "field" else [person, addition]
    head_before = _persisted_metadata(workspace)
    old_digest = schema_digest(graph.schema_ir)
    try:
        result = graph.schema.apply(addition)
        assert result.old_digest == old_digest
        assert result.new_digest != old_digest
        assert graph.ledger.get_ledger_meta("schema_digest") == result.new_digest
        assert validate_schema_object_for_workspace(workspace, graph.schema_ir) == result.new_digest
        head_after = _persisted_metadata(workspace)
        assert head_after["head_tx_id"] != head_before["head_tx_id"]
        assert int(head_after["head_tx_seq"]) == int(head_before["head_tx_seq"]) + 1
        assert head_after["schema_digest"] == result.new_digest
    finally:
        graph.close()

    with pytest.raises(SDKStoreError, match="schema"):
        FactGraph.load_workspace(workspace, schema_classes=[person])
    loaded = FactGraph.load_workspace(workspace, schema_classes=classes)
    try:
        assert schema_digest(loaded.schema_ir) == result.new_digest
        assert loaded.ledger.get_ledger_meta("schema_digest") == result.new_digest
        assert (
            validate_schema_object_for_workspace(workspace, loaded.schema_ir) == result.new_digest
        )
        assert _persisted_metadata(workspace) == head_after
        row = loaded.entities.get(classes[0], person_id="alice")
        assert row is not None
        assert row.name == "Alice"
    finally:
        loaded.close()


@pytest.mark.parametrize("change", ["field", "entity"])
@pytest.mark.parametrize("damage", ["missing", "mismatched_content"])
def test_schema_apply_rejects_bad_current_anchor_without_a_transition(
    tmp_path: Path, change, damage
):
    workspace = tmp_path / "workspace"
    graph, person = _seed(workspace)
    paths = resolve_database_workspace_paths(workspace)
    old_schema = canonicalize_schema_ir_jcs(graph.schema_ir)
    old_digest = schema_digest(graph.schema_ir)
    anchor = paths.schema_objects / f"{old_digest.removeprefix('sha256:')}.json"
    assert anchor.exists()
    head_before = _persisted_metadata(workspace)
    transactions_before = {path.name: path.read_bytes() for path in paths.tx_objects.iterdir()}
    assert transactions_before
    if damage == "missing":
        anchor.unlink()
        message = "workspace schema object missing"
    else:
        anchor.write_bytes(canonicalize_schema_ir_jcs(compile_schema_from_classes([Account])))
        message = "workspace schema object invalid: schema object filename/content digest mismatch"
    schemas_before = {path.name: path.read_bytes() for path in paths.schema_objects.iterdir()}
    try:
        with pytest.raises(SDKStoreError) as caught:
            graph.schema.apply(_person(nickname=True) if change == "field" else Account)
        # Single-class schema.apply preserves its existing SDK error wrapper.
        # The cause identifies the anchor refusal, not a declaration conflict.
        error_type = SchemaNonAdditiveError if change == "field" else SchemaConflictError
        assert type(caught.value) is error_type
        assert caught.value.code == (
            "SCHEMA_NON_ADDITIVE" if change == "field" else "SCHEMA_CONFLICT"
        )
        assert str(caught.value).startswith(f"schema mutation is non-additive: {message}. ")
        assert type(caught.value.__cause__) is SDKStoreError
        assert str(caught.value.__cause__) == message
        assert canonicalize_schema_ir_jcs(graph.schema_ir) == old_schema
        assert graph.ledger.get_ledger_meta("schema_digest") == old_digest
        assert _persisted_metadata(workspace) == head_before
        assert {
            path.name: path.read_bytes() for path in paths.tx_objects.iterdir()
        } == transactions_before
        assert {
            path.name: path.read_bytes() for path in paths.schema_objects.iterdir()
        } == schemas_before
        row = graph.entities.get(person, person_id="alice")
        assert row is not None
        assert row.name == "Alice"
    finally:
        graph.close()
