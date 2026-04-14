from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from factpy_kernel.agent.extraction import ExtractionDocumentError, ExtractionDocumentResult
from factpy_kernel.agent.extraction.metrics import BatchExtractionMetrics
from factpy_kernel.service.app_v1 import app


def _fake_result() -> ExtractionDocumentResult:
    return ExtractionDocumentResult(
        doc_name="note.txt",
        doc_id="doc-1",
        entities=(
            {
                "entity_type": "Module",
                "identity": {"name": "ingest"},
                "fact_count": 1,
            },
        ),
        facts=(),
        metrics=BatchExtractionMetrics(
            doc_id="doc-1",
            total_segments=1,
            success_segment_count=1,
            error_segment_count=0,
            total_proposal_count=1,
            total_valid_count=1,
            total_rejection_count=0,
            batch_started_at_ns=1,
            batch_finished_at_ns=2,
            batch_duration_ms=1,
            per_segment_metrics=(),
        ),
        merge_events=(),
        gleaning_segments_reexamined=0,
        staging_segments=1,
        model="mistral/mistral-small-latest",
    )


class ExtractionHttpApiTests(unittest.TestCase):
    def test_extract_document_endpoint_success(self) -> None:
        with patch.dict(os.environ, {"FACTPY_KERNEL_AUTH_DISABLED": "true"}, clear=False):
            with patch(
                "factpy_kernel.service.extraction_v1.extract_document_from_ir",
                return_value=_fake_result(),
            ):
                with TestClient(app) as client:
                    resp = client.post(
                        "/v1/extraction/documents",
                        files={"file": ("note.txt", b"hello", "text/plain")},
                        data={"options": json.dumps({"schema_ir": {"entities": [], "predicates": []}})},
                    )

        body = resp.json()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["errors"], [])
        self.assertEqual(body["meta"], {})
        self.assertEqual(body["result"]["doc_name"], "note.txt")
        self.assertEqual(body["result"]["model"], "mistral/mistral-small-latest")

    def test_extract_document_endpoint_invalid_json_options(self) -> None:
        with patch.dict(os.environ, {"FACTPY_KERNEL_AUTH_DISABLED": "true"}, clear=False):
            with TestClient(app) as client:
                resp = client.post(
                    "/v1/extraction/documents",
                    files={"file": ("note.txt", b"hello", "text/plain")},
                    data={"options": "{not-json"},
                )

        body = resp.json()
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(body["ok"])
        self.assertEqual(body["errors"][0]["path"], "options")
        self.assertEqual(body["meta"], {})

    def test_extract_document_endpoint_missing_schema_ir(self) -> None:
        with patch.dict(os.environ, {"FACTPY_KERNEL_AUTH_DISABLED": "true"}, clear=False):
            with TestClient(app) as client:
                resp = client.post(
                    "/v1/extraction/documents",
                    files={"file": ("note.txt", b"hello", "text/plain")},
                    data={"options": json.dumps({})},
                )

        body = resp.json()
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(body["ok"])
        self.assertEqual(body["errors"][0]["path"], "options.schema_ir")
        self.assertEqual(body["meta"], {})

    def test_extract_document_endpoint_staging_failure(self) -> None:
        with patch.dict(os.environ, {"FACTPY_KERNEL_AUTH_DISABLED": "true"}, clear=False):
            with patch(
                "factpy_kernel.service.extraction_v1.extract_document_from_ir",
                side_effect=ExtractionDocumentError(
                    "staging",
                    object(),
                    "Staging failed: unreadable document",
                ),
            ):
                with TestClient(app) as client:
                    resp = client.post(
                        "/v1/extraction/documents",
                        files={"file": ("note.txt", b"hello", "text/plain")},
                        data={"options": json.dumps({"schema_ir": {"entities": [], "predicates": []}})},
                    )

        body = resp.json()
        self.assertEqual(resp.status_code, 500)
        self.assertFalse(body["ok"])
        self.assertEqual(body["errors"][0]["details"]["stage"], "staging")
        self.assertEqual(body["meta"], {})

    def test_extract_document_endpoint_requires_auth(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FACTPY_KERNEL_API_KEYS": "valid-key",
                "FACTPY_KERNEL_AUTH_DISABLED": "false",
            },
            clear=False,
        ):
            with TestClient(app) as client:
                resp = client.post(
                    "/v1/extraction/documents",
                    files={"file": ("note.txt", b"hello", "text/plain")},
                    data={"options": json.dumps({"schema_ir": {"entities": [], "predicates": []}})},
                )

        self.assertEqual(resp.status_code, 401)
