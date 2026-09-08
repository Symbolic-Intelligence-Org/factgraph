from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factgraph.application.derivation_check_runtime import check_derivation_binding
from factgraph.application.protocol import (
    CheckRequest,
    CompiledDerivationPlan,
    CompiledHeadCall,
)
from factgraph.audit import load_audit_package
from factgraph.audit.meta_history import (
    MetaHistoryError,
    effective_meta_at_receipt,
    receipt_as_of_event_seq,
)
from factgraph.audit.round_events import (
    finalize_round,
    project_check_event_payload,
    record_round_event,
    start_round,
)
from factgraph.core.store._artifact_sidecar import FileArtifactSidecar
from factgraph.core.store._support import (
    ProofReceipt,
    compute_support_digest,
    support_artifact_bytes,
)
from factgraph.core.store.database import AssertionInput, Database, MetaAppendInput, MetaEntry
from factgraph.core.store.runtime import Store


_ASSERTION_ID = "asrt:11111111111111111111111111111111"
_PROOF_BODY_HEX = (
    "7b2262696e64696e67223a5b5b2224646f63222c22642d31225d2c5b22247269736b"
    "222c2268696768225d5d2c226b696e64223a226e61746976655f62696e64696e675f76"
    "31222c226e6f6e5f666163745f7374657073223a5b5d2c22707265645f7769746e6573"
    "736573223a5b5d2c22726f6f745f726573756c745f6b696e64223a2266616374222c22"
    "72756c655f7265665f6564676573223a5b5d2c2272756c655f72656673223a5b5d7d"
)
_PROOF_BODY_DIGEST = "sha256:06a1621a5ba049ece2dc821f1c657fce2c9ef6838a3e6c10106325b8f7833d11"


class Slice3bReceiptAsOfTests(unittest.TestCase):
    def test_receipt_envelope_persists_and_replays_its_cold_as_of_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp, patch(
            "factgraph.core.store.database._new_assertion_id",
            side_effect=[_ASSERTION_ID],
        ):
            root = Path(raw_tmp)
            workspace = root / "workspace"
            package_dir = _minimal_audit_package(root / "audit-package")
            db = Database.create(workspace, schema_ir=_schema_ir())
            assertion = db.commit_assertions(
                (
                    AssertionInput(
                        "person:name",
                        (("entity_ref", "idref_v1:Person:alice"), ("string", "Alice")),
                        (
                            MetaEntry("provenance_class", "str", "observed"),
                            MetaEntry("ingested_at", "time", 1),
                        ),
                    ),
                )
            ).assertions[0]
            store = Store(_schema_ir(), ledger=db._ledger_for_attach())
            request = CheckRequest(
                plan=CompiledDerivationPlan(
                    derivation_id="receipt.as_of",
                    version="1.0",
                    body_ir=[("pred", "person:name", ["$person", "$name"])],
                    heads=(
                        CompiledHeadCall(
                            target_pred_id="person:name",
                            head_var_names=("$person", "$name"),
                        ),
                    ),
                ),
                binding=(("$person", "idref_v1:Person:alice"),),
                engine="native",
            )

            result = check_derivation_binding(request, store=store)
            envelope = result.evidence_envelope
            assert envelope is not None
            self.assertEqual(envelope.as_of_event_seq, (1, 0))

            db.commit_changes(
                assertions=(),
                revocations=(),
                meta_appends=(
                    MetaAppendInput(
                        assertion.asrt_id,
                        "provenance_class",
                        "str",
                        "agent",
                    ),
                ),
            )
            self.assertEqual(
                db._ledger_for_attach().effective_meta_rows(
                    asrt_id=assertion.asrt_id,
                    key="provenance_class",
                )[0].value,
                "agent",
            )

            recorder = start_round("receipt-round", event_ts=100)
            record_round_event(
                recorder,
                kind="check_result",
                payload=project_check_event_payload(request, result),
                event_ts=101,
            )
            finalize_round(recorder, package_dir, event_ts=102)
            db.close()

            reopened = Database.open(workspace, schema_ir=_schema_ir())
            try:
                cold_event = load_audit_package(package_dir).round_events[1]
                cold_envelope = cold_event.payload["result"]["evidence_envelope"]
                assert isinstance(cold_envelope, dict)
                self.assertEqual(cold_envelope["as_of_event_seq"], [1, 0])
                self.assertEqual(
                    receipt_as_of_event_seq(reopened._ledger_for_attach(), cold_envelope),
                    envelope.as_of_event_seq,
                )
                self.assertEqual(
                    effective_meta_at_receipt(
                        reopened._ledger_for_attach(),
                        asrt_id=assertion.asrt_id,
                        envelope=cold_envelope,
                    )["provenance_class"],
                    "observed",
                )
            finally:
                reopened.close()

    def test_receipt_as_of_rejects_malformed_and_future_boundaries(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        try:
            ledger = db._ledger_for_attach()
            for malformed in (None, [0], [-1, 0], [True, 0], "0:0"):
                with self.subTest(malformed=malformed), self.assertRaises(MetaHistoryError):
                    receipt_as_of_event_seq(
                        ledger,
                        {"as_of_event_seq": malformed},
                    )
            with self.assertRaisesRegex(MetaHistoryError, "beyond ledger head"):
                receipt_as_of_event_seq(ledger, {"as_of_event_seq": [1, 0]})
        finally:
            db.close()

    def test_proof_body_bytes_and_single_address_sidecar_remain_frozen(self) -> None:
        receipt = ProofReceipt(
            kind="native_binding_v1",
            root_result_kind="fact",
            binding_items=(("$doc", "d-1"), ("$risk", "high")),
            pred_witnesses=(),
        )
        self.assertEqual(support_artifact_bytes(receipt).hex(), _PROOF_BODY_HEX)
        self.assertEqual(compute_support_digest(receipt), _PROOF_BODY_DIGEST)

        with tempfile.TemporaryDirectory() as raw_tmp:
            sidecar = FileArtifactSidecar(raw_tmp)
            sidecar.write_support(_PROOF_BODY_DIGEST, receipt)
            sidecar.write_support(_PROOF_BODY_DIGEST, receipt)
            payloads = list((Path(raw_tmp) / "support" / "sha256").glob("*.json"))
            self.assertEqual(
                [path.name for path in payloads if not path.name.endswith(".meta.json")],
                [f"{_PROOF_BODY_DIGEST.removeprefix('sha256:')}.json"],
            )
            different = ProofReceipt(
                kind="native_binding_v1",
                root_result_kind="fact",
                binding_items=(("$doc", "d-2"), ("$risk", "high")),
                pred_witnesses=(),
            )
            with self.assertRaisesRegex(ValueError, "support_digest collision"):
                sidecar.write_support(_PROOF_BODY_DIGEST, different)


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


def _minimal_audit_package(package_dir: Path) -> Path:
    audit_dir = package_dir / "audit"
    audit_dir.mkdir(parents=True)
    audit_files = {
        "run_ledger": "audit/run_ledger.jsonl",
        "candidate_ledger": "audit/candidate_ledger.jsonl",
        "accept_write_ledger": "audit/accept_write_ledger.jsonl",
        "accept_failed": "audit/accept_failed.jsonl",
        "mapping_resolution": "audit/mapping_resolution.json",
        "decision_log": "audit/decision_log.jsonl",
    }
    for key, rel in audit_files.items():
        path = package_dir / rel
        path.write_text("{}" if key == "mapping_resolution" else "", encoding="utf-8")
    (package_dir / "manifest.json").write_text(
        json.dumps(
            {"package_kind": "audit", "paths": {"audit_files": audit_files}},
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return package_dir


if __name__ == "__main__":
    unittest.main()
