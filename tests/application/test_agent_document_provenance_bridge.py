"""Focused bridge coverage without importing Agent's service-facing facade."""

from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

from factgraph.application.protocol.scenario_v2 import lower_scenario_meta_v2


def _load_document_models() -> type:
    """Load the leaf document model under a private package namespace.

    The wide ``agent`` facade currently imports the known base-mismatched
    service static-UI path.  This leaf bridge has no runtime/service dependency
    and should remain testable without concealing that unrelated failure.
    """

    agent_root = Path(__file__).resolve().parents[2] / "src" / "agent"
    package_name = "_agent_document_provenance_bridge_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(agent_root)]
    sys.modules[package_name] = package
    documents_name = f"{package_name}.documents"
    documents = types.ModuleType(documents_name)
    documents.__path__ = [str(agent_root / "documents")]
    sys.modules[documents_name] = documents

    for module_name, module_path in (
        (f"{package_name}.errors", agent_root / "errors.py"),
        (f"{documents_name}.models", agent_root / "documents" / "models.py"),
    ):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return sys.modules[f"{documents_name}.models"].ExtractionProvenance


ExtractionProvenance = _load_document_models()


def _provenance(
    segment_id: str,
    *,
    document_id: str = "doc_1",
    start: int = 0,
    end: int = 10,
    raw_text: str | None = None,
    merged_from: tuple[object, ...] = (),
):
    return ExtractionProvenance(
        source_document_id=document_id,
        segment_id=segment_id,
        char_offset_start=start,
        char_offset_end=end,
        raw_text=raw_text or f"text-{segment_id}",
        extraction_method="llm_refined",
        merged_from=merged_from,
    )


class AgentDocumentProvenanceBridgeTests(unittest.TestCase):
    def test_merged_extraction_provenance_lowers_to_private_factgraph_refs(self) -> None:
        third = _provenance("seg_3", start=20, end=30, raw_text="third secret text")
        second = _provenance("seg_2", start=10, end=20, raw_text="second secret text")
        root = _provenance(
            "seg_1",
            raw_text="first secret text",
            merged_from=(second, third),
        )

        refs = root.to_factgraph_provenance_refs()

        self.assertEqual(len(refs), 3)
        self.assertEqual(tuple(item.origin_role for item in refs), ("agent_extraction",) * 3)
        self.assertEqual(refs[0].locator.kind, "opaque")
        self.assertEqual(refs[0].locator.opaque_ref, "chars:0-10")
        self.assertEqual(refs[1].locator.opaque_ref, "chars:10-20")
        self.assertEqual(
            refs[0].content_digest,
            "sha256:" + sha256(b"first secret text").hexdigest(),
        )
        expected_source_ref = (
            "agent-document:"
            + sha256(
                json.dumps(
                    {"document_id": "doc_1", "segment_id": "seg_1"},
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
        )
        self.assertEqual(refs[0].source_ref, expected_source_ref)

        bridge_wire = json.dumps([item.to_wire() for item in refs], sort_keys=True)
        for raw_text in ("first secret text", "second secret text", "third secret text"):
            self.assertNotIn(raw_text, bridge_wire)
        self.assertNotIn("doc_1", bridge_wire)
        self.assertTrue(all(item.admission_ref is None for item in refs))

        # The bridge values are the exact closed objects accepted by Scenario
        # metadata; no Agent-specific source carrier crosses this boundary.
        scenario_meta = lower_scenario_meta_v2({"sources": refs})
        self.assertEqual(scenario_meta.provenance, refs)

        # The bridge is read-only: the Agent-owned checkpoint carrier, which
        # remains responsible for its legacy source/source_loc mirror, is intact.
        self.assertEqual(root.source_segment_ids(), ("seg_1", "seg_2", "seg_3"))
        self.assertEqual(root.to_checkpoint()["raw_text"], "first secret text")

    def test_merged_sources_with_same_local_segment_id_from_different_documents_survive(
        self,
    ) -> None:
        other_document = _provenance(
            "same-segment",
            document_id="doc_2",
            raw_text="second document text",
        )
        same_local_segment = _provenance(
            "same-segment",
            document_id="doc_1",
            raw_text="first document text",
            merged_from=(other_document,),
        )

        refs = same_local_segment.to_factgraph_provenance_refs()

        self.assertEqual(len(same_local_segment.all_sources()), 2)
        self.assertEqual(len(refs), 2)
        self.assertNotEqual(refs[0].source_ref, refs[1].source_ref)
        self.assertEqual(
            tuple(item.content_digest for item in refs),
            (
                "sha256:" + sha256(b"first document text").hexdigest(),
                "sha256:" + sha256(b"second document text").hexdigest(),
            ),
        )


if __name__ == "__main__":
    unittest.main()
