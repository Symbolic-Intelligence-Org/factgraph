"""Layer 4C1 pdf parser tests."""

from __future__ import annotations

import unittest

from agent.documents.models import DocumentSource
from agent.documents.parsers.pdf import PyMuPDFParser, pdf_parser_available
from agent.documents.parsers.base import ParseError


class AgentLayer4C1PdfParserAvailabilityTests(unittest.TestCase):
    def test_missing_optional_dependency_surfaces_as_unsupported(self) -> None:
        parser = PyMuPDFParser()
        source = DocumentSource(
            doc_id="pdf123456789abcd",
            doc_name="sample.pdf",
            doc_type="pdf",
            byte_size=0,
            ingested_at=1,
        )
        if pdf_parser_available():
            self.skipTest("pdf optional dependencies available; unsupported path not applicable")
        with self.assertRaises(ParseError) as ctx:
            parser.parse(source, b"%PDF-1.4")
        self.assertEqual(ctx.exception.kind, "unsupported_format")


@unittest.skipUnless(pdf_parser_available(), "pymupdf+pymupdf4llm optional dependencies unavailable")
class AgentLayer4C1PdfParserTests(unittest.TestCase):
    def test_parse_simple_pdf(self) -> None:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Article 3.2\nIf user is vip then notify.")
        payload = doc.tobytes()
        doc.close()

        parser = PyMuPDFParser()
        source = DocumentSource(
            doc_id="pdf123456789abcd",
            doc_name="sample.pdf",
            doc_type="pdf",
            byte_size=len(payload),
            ingested_at=1,
        )
        segments = parser.parse(source, payload)
        self.assertTrue(segments)
        self.assertEqual(segments[0].page_number, 1)


if __name__ == "__main__":
    unittest.main()
