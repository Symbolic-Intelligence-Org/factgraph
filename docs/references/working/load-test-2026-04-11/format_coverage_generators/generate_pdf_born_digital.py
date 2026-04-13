"""
B3 format coverage — born-digital PDF generator (one-shot)

Reads `samples/medium/medium_01_security.md` and renders it as a PDF with
a real Unicode text layer, so pymupdf / pymupdf4llm can extract text cleanly.

Uses reportlab's Platypus flowables + STSong-Light CJK font to handle
Chinese content. STSong-Light is a reportlab built-in CID font — no TTF
file is required on the system.

Output: samples/medium/medium_04_pdf_security.pdf

Purpose: exercise the 4C1 PDF parser path (pymupdf4llm) on a born-digital
PDF that is the same content as `medium_01_security.md` (already tested in
iter 5 at the MD level), enabling clean cross-format comparison.

This is a one-shot generator, not reusable tooling. It lives next to the
B3 format coverage plan as provenance for the generated binary. The binary
itself lives in gitignored `samples/`.

Usage:
    /Users/zhenzhili/miniforge3/bin/python \\
        docs/references/working/load-test-2026-04-11/format_coverage_generators/generate_pdf_born_digital.py

Idempotent: overwrites output file if it already exists.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

LOAD_TEST_DIR = Path(__file__).parent.parent
SRC_MD = LOAD_TEST_DIR / "samples" / "medium" / "medium_01_security.md"
OUT_PDF = LOAD_TEST_DIR / "samples" / "medium" / "medium_04_pdf_security.pdf"


def _escape_xml(text: str) -> str:
    """reportlab Paragraph content is parsed as XML. Escape metacharacters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main() -> int:
    if not SRC_MD.exists():
        print(f"ERROR: source MD not found: {SRC_MD}", file=sys.stderr)
        return 1

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)

    # Register CJK font (built-in reportlab CID font; no external TTF needed)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    md_text = SRC_MD.read_text(encoding="utf-8")
    lines = md_text.split("\n")

    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="medium_01_security (B3 format coverage PDF)",
        author="B3 format coverage generator",
    )

    styles = getSampleStyleSheet()
    style_body = ParagraphStyle(
        name="BodyCJK",
        parent=styles["Normal"],
        fontName="STSong-Light",
        fontSize=10,
        leading=14,
    )
    style_h1 = ParagraphStyle(
        name="H1CJK",
        parent=styles["Heading1"],
        fontName="STSong-Light",
        fontSize=16,
        leading=20,
        spaceBefore=12,
        spaceAfter=10,
    )
    style_h2 = ParagraphStyle(
        name="H2CJK",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=13,
        leading=17,
        spaceBefore=10,
        spaceAfter=8,
    )
    style_h3 = ParagraphStyle(
        name="H3CJK",
        parent=styles["Heading3"],
        fontName="STSong-Light",
        fontSize=11,
        leading=15,
        spaceBefore=8,
        spaceAfter=6,
    )
    style_bullet = ParagraphStyle(
        name="BulletCJK",
        parent=style_body,
        leftIndent=20,
        bulletIndent=10,
    )

    flowables: list = []
    for raw in lines:
        line = raw.rstrip()
        if not line:
            flowables.append(Spacer(1, 0.08 * inch))
            continue
        escaped = _escape_xml(line)
        if line.startswith("# "):
            flowables.append(Paragraph(escaped[2:], style_h1))
        elif line.startswith("## "):
            flowables.append(Paragraph(escaped[3:], style_h2))
        elif line.startswith("### "):
            flowables.append(Paragraph(escaped[4:], style_h3))
        elif line.startswith("- ") or line.startswith("* "):
            flowables.append(Paragraph("• " + escaped[2:], style_bullet))
        else:
            flowables.append(Paragraph(escaped, style_body))

    doc.build(flowables)
    print(f"OK: wrote {OUT_PDF}")
    print(f"  size: {OUT_PDF.stat().st_size} bytes")
    print(f"  source: {SRC_MD}")
    print(f"  source size: {SRC_MD.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
