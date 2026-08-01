from __future__ import annotations

import dataclasses
import base64
import hashlib
import json
import tempfile
import unittest
import zlib
from pathlib import Path
from typing import Any
from unittest.mock import patch

from factgraph.core.policy.chosen import compute_chosen_for_predicate
from factgraph.core.store.database import (
    AssertionInput,
    Database,
    MetaAppendInput,
    MetaEntry,
    RevocationInput,
    SchemaTransitionInput,
    assertion_digest_for,
    resolve_database_workspace_paths,
)
from factgraph.core.store.ledger import AnnotationRow, Claim, ClaimArg, Ledger, MetaRow
from factgraph.core.store.premise_filter import MetaExclusion, premise_scoped_ledger
from factgraph.core.view.projector import (
    project_view_facts,
    project_view_facts_with_audit,
    project_view_facts_with_witness,
)


_GOLDEN_ROOT = Path(__file__).with_name("golden") / "slice3b_phase1"
_READ_FIXTURE = _GOLDEN_ROOT / "read_equivalence_v1.json"
_REPAIR_FIXTURE = _GOLDEN_ROOT / "production_repair_v1.json"
_FIXED_DB_ID = "db:slice3b-phase1-read-equivalence"
_FIXED_TIME_NS = 1_788_307_200_000_000_000
_IDS = (
    "asrt:11111111111111111111111111111111",
    "asrt:22222222222222222222222222222222",
    "asrt:33333333333333333333333333333333",
    "asrt:44444444444444444444444444444444",
)
_ROGUE_ID = "asrt:55555555555555555555555555555555"
_MISSING_ID = "asrt:ffffffffffffffffffffffffffffffff"


class Slice3bReadEquivalenceGoldenTests(unittest.TestCase):
    """Freeze logical reads before the seven-table to three-table atomic flip."""

    maxDiff = None

    def test_all_read_surfaces_match_the_pre_flip_golden(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            database, _workspace = _build_repaired_workspace(Path(raw_tmp))
            try:
                actual = _canonical_json_bytes(_read_snapshot(database))
                _assert_compressed_golden(actual, _READ_FIXTURE)
            finally:
                database.close()

    def test_production_repair_tx_object_and_head_are_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            database, workspace = _build_repaired_workspace(Path(raw_tmp))
            try:
                head = database.head()
                paths = resolve_database_workspace_paths(workspace)
                tx_path = paths.tx_objects / f"{head.tx_id.removeprefix('tx:')}.json"
                tx_bytes = tx_path.read_bytes()
                actual = _canonical_json_bytes({
                    "fixture_version": 1,
                    "tx_id": head.tx_id,
                    "tx_object_sha256": hashlib.sha256(tx_bytes).hexdigest(),
                    "tx_object_base64": base64.b64encode(tx_bytes).decode("ascii"),
                    "head_metadata": database._ledger_for_attach().get_ledger_meta_snapshot(
                        ("head_tx_id", "head_tx_seq", "head_state_digest")
                    ),
                })
                _assert_compressed_golden(actual, _REPAIR_FIXTURE)
            finally:
                database.close()


def _build_repaired_workspace(raw_tmp: Path) -> tuple[Database, Path]:
    workspace = raw_tmp / "workspace"
    with (
        patch("factgraph.core.store.database._new_db_id", return_value=_FIXED_DB_ID),
        patch("factgraph.core.store.database._new_assertion_id", side_effect=_IDS),
        patch("factgraph.core.store.database.time.time_ns", return_value=_FIXED_TIME_NS),
    ):
        database = Database.create(workspace, schema_ir=_schema_ir(version=1))
        created = database.commit_changes(
            assertions=(
                AssertionInput(
                    pred_id="person:name",
                    fact_tuple=(
                        ("entity_ref", "idref_v1:Person:alice"),
                        ("string", "Alice"),
                    ),
                    meta=(
                        MetaEntry("ingested_at", "time", 100),
                        MetaEntry("source", "str", "phase1-capture"),
                        MetaEntry("trace_id", "str", "trace-old"),
                        MetaEntry("provenance_class", "str", "allowed"),
                    ),
                ),
                AssertionInput(
                    pred_id="person:name",
                    fact_tuple=(
                        ("entity_ref", "idref_v1:Person:alice"),
                        ("string", "Alicia"),
                    ),
                    meta=(
                        MetaEntry("ingested_at", "time", 200),
                        MetaEntry("source", "str", "phase1-capture"),
                        MetaEntry("provenance_class", "str", "review"),
                    ),
                ),
                AssertionInput(
                    pred_id="person:alias",
                    fact_tuple=(
                        ("entity_ref", "idref_v1:Person:alice"),
                        ("string", "Ally"),
                    ),
                    meta=(
                        MetaEntry("ingested_at", "time", 150),
                        MetaEntry("source", "str", "phase1-capture"),
                        MetaEntry("provenance_class", "str", "blocked"),
                    ),
                ),
            ),
            revocations=(),
        )
        if tuple(row.asrt_id for row in created.assertions) != _IDS[:3]:
            raise AssertionError("deterministic assertion ids drifted")

        revoked = database.commit_changes(
            assertions=(),
            revocations=(
                RevocationInput(
                    _IDS[0],
                    meta=(
                        MetaEntry("source", "str", "phase1-capture"),
                        MetaEntry("trace_id", "str", "trace-revoke"),
                        MetaEntry("reason", "str", "superseded"),
                    ),
                ),
            ),
        )
        if revoked.revocations[0].revoker_asrt_id != _IDS[3]:
            raise AssertionError("deterministic revoker id drifted")

        database.commit_changes(
            assertions=(),
            revocations=(),
            meta_appends=(
                MetaAppendInput(_IDS[1], "provenance_class", "str", "blocked"),
                MetaAppendInput(_IDS[1], "provenance_class", "str", "allowed"),
            ),
        )
        database.commit_changes(
            assertions=(),
            revocations=(),
            schema_transition=SchemaTransitionInput(
                old_schema_digest=database.schema_digest,
                new_schema_ir=_schema_ir(version=2),
            ),
        )
        pre_repair_head = database.head()
        database.close()

        rogue_fact = (
            ("entity_ref", "idref_v1:Person:rogue"),
            ("string", "Rogue"),
        )
        rogue_user_meta = (
            MetaEntry("ingested_at", "time", 300),
            MetaEntry("source", "str", "phase1-repair-injection"),
            MetaEntry("provenance_class", "str", "allowed"),
        )
        rogue_digest = assertion_digest_for(
            pred_id="person:alias",
            fact_tuple=rogue_fact,
            schema_digest=pre_repair_head.schema_digest,
            meta=rogue_user_meta,
        )
        paths = resolve_database_workspace_paths(workspace)
        drift_ledger = Ledger(paths.assertions)
        drift_ledger.append_assertion(
            claim=Claim(
                asrt_id=_ROGUE_ID,
                pred_id="person:alias",
                e_ref=rogue_fact[0][1],
                rest_terms=[rogue_fact[1]],
            ),
            claim_args=(
                ClaimArg(_ROGUE_ID, 0, "Rogue", "string"),
            ),
            meta_rows=[
                *(MetaRow(_ROGUE_ID, row.key, row.kind, row.value) for row in rogue_user_meta),
                MetaRow(_ROGUE_ID, "schema_digest", "str", pre_repair_head.schema_digest),
                MetaRow(_ROGUE_ID, "assertion_digest", "str", rogue_digest),
                MetaRow(_ROGUE_ID, "tx_id", "str", pre_repair_head.tx_id),
            ],
            annotation_rows=[
                AnnotationRow(
                    _ROGUE_ID,
                    "shared",
                    "source",
                    "source",
                    "str",
                    "phase1-repair-injection",
                    "observed",
                )
            ],
            asrt_id=_ROGUE_ID,
        )
        drift_ledger.close()

        return (
            Database.repair(
                workspace,
                schema_ir=_schema_ir(version=2),
                reason="slice3b-phase1-production-repair-golden",
            ),
            workspace,
        )


def _read_snapshot(database: Database) -> dict[str, Any]:
    ledger = database._ledger_for_attach()
    all_ids = (*_IDS, _ROGUE_ID, _MISSING_ID)
    scoped = premise_scoped_ledger(
        ledger,
        MetaExclusion("provenance_class", frozenset({"blocked"})),
    )
    schema_ir = _schema_ir(version=2)
    facts_with_audit, audit = project_view_facts_with_audit(ledger, schema_ir)
    return {
        "fixture_version": 1,
        "database_head": database.head(),
        "ledger": {
            "claims": ledger.claims,
            "claim_args": ledger.claim_args,
            "meta_rows": ledger.meta_rows,
            "annotation_rows": ledger.annotation_rows,
            "revokes": ledger.revokes,
            "get_claim": {asrt_id: ledger.get_claim(asrt_id) for asrt_id in all_ids},
            "find_claims": {
                "all": ledger.find_claims(),
                "by_predicate": ledger.find_claims(pred_id="person:name"),
                "by_entity": ledger.find_claims(e_ref="idref_v1:Person:alice"),
                "by_both": ledger.find_claims(
                    pred_id="person:alias", e_ref="idref_v1:Person:alice"
                ),
            },
            "find_claim_args": {
                "all": ledger.find_claim_args(),
                "by_assertion": ledger.find_claim_args(asrt_id=_IDS[1]),
                "by_index": ledger.find_claim_args(idx=0),
                "by_tag": ledger.find_claim_args(tag="string"),
            },
            "find_meta": {
                "all": ledger.find_meta(),
                "by_assertion": ledger.find_meta(asrt_id=_IDS[1]),
                "duplicate_key": ledger.find_meta(
                    asrt_id=_IDS[1], key="provenance_class"
                ),
                "by_kind": ledger.find_meta(kind="time"),
            },
            "find_annotations": {
                "all": ledger.find_annotations(),
                "by_assertion": ledger.find_annotations(asrt_id=_IDS[1]),
                "by_namespace": ledger.find_annotations(namespace="shared"),
                "by_category": ledger.find_annotations(category="source"),
                "by_key": ledger.find_annotations(key="trace_id"),
            },
            "active_revocation": {
                asrt_id: ledger.has_active_revocation(asrt_id) for asrt_id in all_ids
            },
            "find_revoker": {asrt_id: ledger.find_revoker(asrt_id) for asrt_id in all_ids},
            "ledger_meta": {
                key: ledger.get_ledger_meta(key)
                for key in (
                    "db_id",
                    "schema_digest",
                    "head_tx_id",
                    "head_tx_seq",
                    "head_state_digest",
                    "digest_scheme",
                    "missing",
                )
            },
            "ledger_meta_snapshot": ledger.get_ledger_meta_snapshot(
                (
                    "db_id",
                    "schema_digest",
                    "head_tx_id",
                    "head_tx_seq",
                    "head_state_digest",
                    "digest_scheme",
                    "missing",
                )
            ),
        },
        "premise_filter": {
            "claims": scoped.claims,
            "claim_args": scoped.claim_args,
            "meta_rows": scoped.meta_rows,
            "annotation_rows": scoped.annotation_rows,
            "revokes": scoped.revokes,
            "get_claim": {asrt_id: scoped.get_claim(asrt_id) for asrt_id in all_ids},
            "active_revocation": {
                asrt_id: scoped.has_active_revocation(asrt_id) for asrt_id in all_ids
            },
            "find_revoker": {asrt_id: scoped.find_revoker(asrt_id) for asrt_id in all_ids},
        },
        "chosen": {
            pred["pred_id"]: [
                {"group_key": list(group_key), "asrt_id": asrt_id}
                for group_key, asrt_id in sorted(
                    compute_chosen_for_predicate(ledger, pred).items(),
                    key=lambda item: repr(item[0]),
                )
            ]
            for pred in schema_ir["predicates"]
        },
        "projector": {
            "facts": project_view_facts(ledger, schema_ir),
            "witness": project_view_facts_with_witness(ledger, schema_ir),
            "facts_with_audit": facts_with_audit,
            "audit": audit,
            "premise_filtered_facts": project_view_facts(scoped, schema_ir),
        },
    }


def _schema_ir(*, version: int) -> dict[str, Any]:
    predicates = [
        {
            "pred_id": "person:name",
            "arg_specs": [
                {"name": "person", "type_domain": "entity_ref"},
                {"name": "name", "type_domain": "string"},
            ],
            "cardinality": "single",
            "group_key_indexes": [0],
        },
        {
            "pred_id": "person:alias",
            "arg_specs": [
                {"name": "person", "type_domain": "entity_ref"},
                {"name": "alias", "type_domain": "string"},
            ],
            "cardinality": "multi",
            "group_key_indexes": [0],
        },
    ]
    if version == 2:
        predicates.append(
            {
                "pred_id": "person:status",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "status", "type_domain": "string"},
                ],
                "cardinality": "single",
                "group_key_indexes": [0],
            }
        )
    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [{"name": "person_id", "type_domain": "string"}],
            }
        ],
        "predicates": predicates,
        "projection": {
            "entities": ["Person"],
            "predicates": [row["pred_id"] for row in predicates],
        },
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": f"2026-08-01T12:00:0{version}Z",
    }


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, bytes):
        return {"$bytes_hex": value.hex()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            _jsonable(value),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _assert_compressed_golden(actual: bytes, path: Path) -> None:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    self_described = zlib.decompress(
        base64.b64decode(fixture["canonical_zlib_base64"].encode("ascii"))
    )
    if len(self_described) != fixture["canonical_size"]:
        raise AssertionError(f"golden size metadata drifted: {path.name}")
    if hashlib.sha256(self_described).hexdigest() != fixture["canonical_sha256"]:
        raise AssertionError(f"golden digest metadata drifted: {path.name}")
    if actual != self_described:
        raise AssertionError(
            f"canonical read bytes differ from {path.name}: "
            f"expected sha256={fixture['canonical_sha256']}, "
            f"actual sha256={hashlib.sha256(actual).hexdigest()}"
        )


if __name__ == "__main__":
    unittest.main()
