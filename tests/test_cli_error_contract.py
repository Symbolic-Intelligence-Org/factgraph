"""The v0.2 legacy schema loader keeps its closed error-JSON decode contract.

``_load_v02_schema_ir`` reads a closed on-disk format: the v0.2 workspace
schema object.  Its ``try`` block is a decode boundary whose failure family is
``json.loads``'s own ``ValueError`` (``JSONDecodeError``); the non-object root
is raised into that same family so both malformed JSON and a non-object root
leave through one handler and one closed CLI payload
(``kind="legacy_schema_unreadable"``, ``message="failed to read v0.2 schema
object: <reason>"``).  The cases below pin that payload for both members of the
family plus the positive control.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factgraph.cli import _load_v02_schema_ir
from factgraph.sdk import compile_schema_from_classes
from tests._t3_error_contract_fixtures import Person


def _load(tmp_path: Path, text: str):
    registry = tmp_path / "registry"
    (registry / "schema").mkdir(parents=True)
    (registry / "schema" / "schema_ir.json").write_text(text, encoding="utf-8")
    return _load_v02_schema_ir(
        workspace=tmp_path / "workspace",
        manifest={},
        legacy_registry_dir=registry,
    )


@pytest.mark.parametrize("root", ["[]", '"schema"', "3", "null", "true"])
def test_non_object_schema_root_reports_the_unreadable_payload(tmp_path, capsys, root):
    assert _load(tmp_path, root) is None
    payload = json.loads(capsys.readouterr().err)
    assert payload["status"] == "error"
    assert payload["kind"] == "legacy_schema_unreadable"
    assert payload["message"] == "failed to read v0.2 schema object: schema root must be object"


def test_malformed_json_shares_the_same_unreadable_payload(tmp_path, capsys):
    assert _load(tmp_path, "{not json") is None
    payload = json.loads(capsys.readouterr().err)
    assert payload["kind"] == "legacy_schema_unreadable"
    assert payload["message"].startswith("failed to read v0.2 schema object: ")


def test_object_schema_root_is_loaded_with_its_digest(tmp_path, capsys):
    schema_ir = compile_schema_from_classes([Person], generated_at="2026-08-13T00:00:00Z")
    loaded = _load(tmp_path, json.dumps(schema_ir))
    assert capsys.readouterr().err == ""
    assert loaded is not None
    payload, digest = loaded
    assert payload == json.loads(json.dumps(schema_ir))
    assert isinstance(digest, str) and digest
