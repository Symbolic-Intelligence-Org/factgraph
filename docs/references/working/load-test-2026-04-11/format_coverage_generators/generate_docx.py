"""
B3 format coverage — DOCX generator (one-shot)

Reads `samples/medium/medium_03_audit_report.md` and converts to a .docx
file using python-docx. Headings become real DOCX headings, paragraphs
become real paragraphs, bullets/numbered lists become real list items.

Markdown tables are rendered as plain-text rows (python-docx table support
is limited and parser-test does not require faithful table fidelity — the
4C1 DOCX parser path cares about paragraph structure, not table cells).

Output: samples/medium/medium_05_docx_audit.docx

Purpose: exercise the 4C1 DOCX parser path (python-docx) on mixed-content
audit/reference material. This sample was chosen over the blueprint
candidate (medium_02_blueprint_backref) to extend content surface —
audit content has tables, bullet lists, and mixed narrative, which stress
DOCX parsing differently from structured blueprint prose.

This is a one-shot generator, not reusable tooling. It lives next to the
B3 format coverage plan as provenance for the generated binary.

Usage:
    /Users/zhenzhili/miniforge3/bin/python \\
        docs/references/working/load-test-2026-04-11/format_coverage_generators/generate_docx.py

Idempotent: overwrites output file if it already exists.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document

LOAD_TEST_DIR = Path(__file__).parent.parent
SRC_MD = LOAD_TEST_DIR / "samples" / "medium" / "medium_03_audit_report.md"
OUT_DOCX = LOAD_TEST_DIR / "samples" / "medium" / "medium_05_docx_audit.docx"


_BULLET_RE = re.compile(r"^\s*[-*]\s+")
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def main() -> int:
    if not SRC_MD.exists():
        print(f"ERROR: source MD not found: {SRC_MD}", file=sys.stderr)
        return 1

    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()

    # Basic core metadata so DOCX readers don't show "Untitled"
    doc.core_properties.title = "medium_03_audit_report (B3 format coverage DOCX)"
    doc.core_properties.author = "B3 format coverage generator"

    md_text = SRC_MD.read_text(encoding="utf-8")
    lines = md_text.split("\n")

    in_code_block = False
    code_buffer: list[str] = []

    def flush_code_block() -> None:
        """Emit accumulated code block as a single monospace paragraph."""
        if not code_buffer:
            return
        para = doc.add_paragraph("\n".join(code_buffer), style="No Spacing")
        for run in para.runs:
            run.font.name = "Courier New"
        code_buffer.clear()

    for raw in lines:
        line = raw.rstrip()

        # Fenced code block boundary
        if line.startswith("```"):
            if in_code_block:
                flush_code_block()
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_buffer.append(raw)
            continue

        if not line:
            # Empty line ends any implicit paragraph
            continue

        # Heading
        h = _HEADING_RE.match(line)
        if h:
            level = len(h.group(1))
            text = h.group(2)
            # python-docx heading levels: 1..9; cap at 4 for sanity
            doc.add_heading(text, level=min(level, 4))
            continue

        # Bullet list
        if _BULLET_RE.match(line):
            text = _BULLET_RE.sub("", line)
            doc.add_paragraph(text, style="List Bullet")
            continue

        # Numbered list
        if _NUMBERED_RE.match(line):
            text = _NUMBERED_RE.sub("", line)
            doc.add_paragraph(text, style="List Number")
            continue

        # Tables: render as plain paragraph (pipe-separated)
        if line.startswith("|"):
            doc.add_paragraph(line)
            continue

        # Block quotes
        if line.startswith("> "):
            para = doc.add_paragraph(line[2:])
            para.paragraph_format.left_indent = None  # python-docx default indent
            continue

        # Default: body paragraph
        doc.add_paragraph(line)

    # Flush any trailing code block (rare but safe)
    flush_code_block()

    doc.save(str(OUT_DOCX))
    print(f"OK: wrote {OUT_DOCX}")
    print(f"  size: {OUT_DOCX.stat().st_size} bytes")
    print(f"  source: {SRC_MD}")
    print(f"  source size: {SRC_MD.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
