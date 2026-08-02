from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from factgraph.core.store.database import (
    AssertionInput,
    Database,
    DatabaseError,
    MetaAppendInput,
    MetaEntry,
    RevocationInput,
)
from factgraph.core.store.ledger import (
    AnnotationRow,
    Claim,
    Ledger,
    LedgerAssertionWrite,
    LedgerFormatError,
    LedgerRevocationWrite,
    MetaRow,
    Revokes,
    _ANNOTATION_COMPAT_PREFIX,
    _annotation_storage_key,
)
from factgraph.sdk import Entity, FactGraph, Field, Identity, SDKStoreError


_TARGET_ID = "asrt:11111111111111111111111111111111"
_NEW_ID = "asrt:22222222222222222222222222222222"
_REVOKER_ID = "asrt:33333333333333333333333333333333"


class ReservedMetaPerson(Entity):
    person_id: str = Identity()
    name: str = Field()


def _schema_ir() -> dict:
    return {
        "schema_ir_version": "v1",
        "entities": [
            {
                "entity_type": "Person",
                "identity_fields": [{"name": "person_id", "type_domain": "string"}],
            }
        ],
        "predicates": [
            {
                "pred_id": "person:name",
                "arg_specs": [
                    {"name": "person", "type_domain": "entity_ref"},
                    {"name": "name", "type_domain": "string"},
                ],
                "group_key_indexes": [0],
            }
        ],
        "projection": {"entities": ["Person"], "predicates": ["person:name"]},
        "protocol_version": {
            "idref_v1": "idref_v1",
            "tup_v1": "tup_v1",
            "export_v1": "export_v1",
        },
        "generated_at": "2026-08-02T00:00:00Z",
    }


def _reserved_keys() -> tuple[str, str]:
    well_formed = _annotation_storage_key(
        AnnotationRow(
            _TARGET_ID,
            "forged",
            "source",
            "forged-key",
            "str",
            "forged-value",
            "observed",
        )
    )
    return _ANNOTATION_COMPAT_PREFIX + "_w", well_formed


def _ledger_snapshot(ledger: Ledger) -> tuple[object, ...]:
    return (
        tuple(ledger.claims),
        tuple(ledger.meta_rows),
        tuple(ledger.annotation_rows),
        tuple(ledger.revokes),
        ledger.get_ledger_meta("head_tx_id"),
    )


def _seed_ledger(path: Path) -> Ledger:
    ledger = Ledger(path)
    ledger.append_assertion(
        claim=Claim(_TARGET_ID, "person:name", "idref_v1:Person:alice", []),
        claim_args=[],
        meta_rows=[],
        asrt_id=_TARGET_ID,
    )
    return ledger


@pytest.mark.parametrize("reserved_key", _reserved_keys(), ids=("malformed", "well-formed"))
@pytest.mark.parametrize(
    "channel",
    (
        "append_assertion",
        "append_revocation",
        "append_meta",
        "commit_batch_assertion",
        "commit_batch_revocation",
        "commit_batch_meta",
    ),
)
def test_ledger_public_meta_channels_reject_reserved_annotation_namespace(
    reserved_key: str,
    channel: str,
) -> None:
    with TemporaryDirectory() as raw_tmp:
        path = Path(raw_tmp) / "ledger.db"
        ledger = _seed_ledger(path)
        before = _ledger_snapshot(ledger)
        forbidden = MetaRow(_NEW_ID, reserved_key, "str", "forged")

        def attempt() -> None:
            if channel == "append_assertion":
                ledger.append_assertion(
                    claim=Claim(_NEW_ID, "person:name", "idref_v1:Person:bob", []),
                    claim_args=[],
                    meta_rows=[forbidden],
                    asrt_id=_NEW_ID,
                )
            elif channel == "append_revocation":
                ledger.append_revocation(
                    revokes=Revokes(_REVOKER_ID, _TARGET_ID),
                    meta_rows=[MetaRow(_REVOKER_ID, reserved_key, "str", "forged")],
                    revoker_asrt_id=_REVOKER_ID,
                )
            elif channel == "append_meta":
                ledger.append_meta([MetaRow(_TARGET_ID, reserved_key, "str", "forged")])
            elif channel == "commit_batch_assertion":
                ledger.commit_batch(
                    assertions=(
                        LedgerAssertionWrite(
                            claim=Claim(_NEW_ID, "person:name", "idref_v1:Person:bob", []),
                            claim_args=(),
                            meta_rows=(forbidden,),
                        ),
                    ),
                    revocations=(),
                    expected_head_tx_id=None,
                    head_tx_id="tx:must-not-commit",
                    metadata={"head_tx_seq": "1"},
                )
            elif channel == "commit_batch_revocation":
                ledger.commit_batch(
                    assertions=(),
                    revocations=(
                        LedgerRevocationWrite(
                            revokes=Revokes(_REVOKER_ID, _TARGET_ID),
                            meta_rows=(MetaRow(_REVOKER_ID, reserved_key, "str", "forged"),),
                        ),
                    ),
                    expected_head_tx_id=None,
                    head_tx_id="tx:must-not-commit",
                    metadata={"head_tx_seq": "1"},
                )
            else:
                ledger.commit_batch(
                    assertions=(),
                    revocations=(),
                    meta_appends=(MetaRow(_TARGET_ID, reserved_key, "str", "forged"),),
                    expected_head_tx_id=None,
                    head_tx_id="tx:must-not-commit",
                    metadata={"head_tx_seq": "1"},
                )

        with pytest.raises(ValueError, match="reserved annotation storage namespace"):
            attempt()
        assert _ledger_snapshot(ledger) == before
        ledger.close()

        reopened = Ledger(path)
        assert _ledger_snapshot(reopened) == before
        reopened.close()


@pytest.mark.parametrize("reserved_key", _reserved_keys(), ids=("malformed", "well-formed"))
@pytest.mark.parametrize("channel", ("assertion", "revocation", "append_meta"))
def test_database_meta_channels_reject_reserved_annotation_namespace(
    reserved_key: str,
    channel: str,
) -> None:
    with TemporaryDirectory() as raw_tmp:
        workspace = Path(raw_tmp) / "workspace"
        db = Database.create(workspace, schema_ir=_schema_ir())
        target = db.commit_changes(
            assertions=(
                AssertionInput(
                    "person:name",
                    (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                ),
            ),
            revocations=(),
        ).assertions[0].asrt_id
        before_head = db.head()
        before_rows = _ledger_snapshot(db._ledger)

        def attempt() -> None:
            if channel == "assertion":
                db.commit_changes(
                    assertions=(
                        AssertionInput(
                            "person:name",
                            (("entity_ref", "idref_v1:Person:bob"), ("string", "Bob")),
                            (MetaEntry(reserved_key, "str", "forged"),),
                        ),
                    ),
                    revocations=(),
                )
            elif channel == "revocation":
                db.commit_changes(
                    assertions=(),
                    revocations=(
                        RevocationInput(
                            target,
                            (MetaEntry(reserved_key, "str", "forged"),),
                        ),
                    ),
                )
            else:
                db.commit_changes(
                    assertions=(),
                    revocations=(),
                    meta_appends=(
                        MetaAppendInput(target, reserved_key, "str", "forged"),
                    ),
                )

        with pytest.raises(DatabaseError, match="reserved annotation storage namespace"):
            attempt()
        assert db.head() == before_head
        assert _ledger_snapshot(db._ledger) == before_rows
        db.close()

        reopened = Database.open(workspace, schema_ir=_schema_ir())
        assert reopened.head() == before_head
        assert _ledger_snapshot(reopened._ledger) == before_rows
        reopened.close()


@pytest.mark.parametrize("reserved_key", _reserved_keys(), ids=("malformed", "well-formed"))
@pytest.mark.parametrize("channel", ("assertion", "revocation", "append_meta"))
def test_sdk_meta_channels_reject_reserved_annotation_namespace(
    reserved_key: str,
    channel: str,
) -> None:
    with TemporaryDirectory() as raw_tmp:
        workspace = Path(raw_tmp) / "workspace"
        fg = FactGraph.create(schema_classes=[ReservedMetaPerson], path=workspace)
        e_ref = fg.entities.create(ReservedMetaPerson, person_id="alice")
        target = fg.fields.set(ReservedMetaPerson.name, e_ref, "Alice")
        before_head = fg._database.head()
        before_rows = _ledger_snapshot(fg.ledger)

        def attempt() -> None:
            if channel == "assertion":
                fg.fields.set(
                    ReservedMetaPerson.name,
                    e_ref,
                    "Mallory",
                    meta={reserved_key: "forged"},
                )
            elif channel == "revocation":
                fg.assertions.retract(target, meta={reserved_key: "forged"})
            else:
                fg.assertions.append_meta(target, reserved_key, "forged")

        with pytest.raises(SDKStoreError, match="reserved annotation storage namespace"):
            attempt()
        assert fg._database.head() == before_head
        assert _ledger_snapshot(fg.ledger) == before_rows
        fg.close()

        reopened = FactGraph.load_workspace(workspace, schema_classes=[ReservedMetaPerson])
        assert reopened._database.head() == before_head
        assert _ledger_snapshot(reopened.ledger) == before_rows
        reopened.close()


def test_internal_annotation_storage_path_round_trips_through_reserved_namespace() -> None:
    with TemporaryDirectory() as raw_tmp:
        path = Path(raw_tmp) / "ledger.db"
        ledger = _seed_ledger(path)
        annotation = AnnotationRow(
            _TARGET_ID,
            "problog",
            "derived",
            "proof",
            "json",
            {"rule": "r1"},
            "derived",
            "problog:proof",
        )
        ledger.append_annotations([annotation])
        assert ledger.find_annotations(asrt_id=_TARGET_ID, namespace="problog") == [annotation]
        ledger.close()

        reopened = Ledger(path)
        assert reopened.find_annotations(asrt_id=_TARGET_ID, namespace="problog") == [annotation]
        reopened.close()


def test_malformed_persisted_annotation_key_fails_closed_as_ledger_format_error() -> None:
    with TemporaryDirectory() as raw_tmp:
        path = Path(raw_tmp) / "ledger.db"
        ledger = _seed_ledger(path)
        ledger.close()
        with sqlite3.connect(path) as conn:
            conn.execute(
                "INSERT INTO claim_meta "
                "(asrt_id, key, kind, value, tx_seq, op_ordinal) VALUES (?, ?, ?, ?, ?, ?)",
                (_TARGET_ID, _ANNOTATION_COMPAT_PREFIX + "_w", "str", "forged", 1, 0),
            )

        with pytest.raises(
            LedgerFormatError,
            match="malformed annotation compatibility storage key",
        ):
            Ledger(path)
