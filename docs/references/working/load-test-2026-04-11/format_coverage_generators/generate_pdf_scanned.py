"""
B3 format coverage — scanned (image-only) PDF generator (one-shot)

Reads `samples/medium/medium_01_security.md` and renders it as a sequence
of PNG images (one per page), then embeds the images into a PDF with NO
TEXT LAYER via pymupdf. This simulates a scanned / OCR'd document and
trips the B3 pipeline's extraction failure path:

    pymupdf4llm extracts no text from image-only PDFs →
    staging returns empty or error →
    run_record marks staging.success = false OR zero segments

Output: samples/short/short_04_scanned_security.pdf

Purpose: exercise the 4C1 failure path on a format that has ZERO
extractable text layer. This is the negative test case required by the
B3 README §1.1 sample plan (1 scanned PDF expected failure).

Design notes:
  - Content is identical to medium_01_security.md (same as medium_04 PDF)
    so the failure case can be directly compared against the success case
    at analysis time.
  - CJK characters are rendered using the first available system TTF that
    supports them. Fallback order: PingFang → Hiragino → Helvetica → PIL
    default. If only latin fonts are available, Chinese characters render
    as boxes — that is fine for the failure test because we only care
    about "no text layer", not glyph fidelity.
  - File size will be larger than the source MD (several hundred KB) due
    to embedded PNG pages. Still classified as "short" length class
    because extraction should produce zero segments.

This is a one-shot generator, not reusable tooling. It lives next to the
B3 format coverage plan as provenance for the generated binary.

Usage:
    /Users/zhenzhili/miniforge3/bin/python \\
        docs/references/working/load-test-2026-04-11/format_coverage_generators/generate_pdf_scanned.py

Idempotent: overwrites output file if it already exists.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pymupdf  # type: ignore
from PIL import Image, ImageDraw, ImageFont

LOAD_TEST_DIR = Path(__file__).parent.parent
SRC_MD = LOAD_TEST_DIR / "samples" / "medium" / "medium_01_security.md"
OUT_PDF = LOAD_TEST_DIR / "samples" / "short" / "short_04_scanned_security.pdf"

# Page + image settings (US-Letter-ish at ~100 DPI)
PAGE_W = 800
PAGE_H = 1000
MARGIN = 50
LINE_HEIGHT = 18
FONT_SIZE = 13

SYSTEM_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _load_font() -> ImageFont.ImageFont:
    """Load the first available system TTF that supports Unicode."""
    for path in SYSTEM_FONT_CANDIDATES:
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), FONT_SIZE)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_line(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    """Soft-wrap a line to fit within max_width pixels."""
    if not text:
        return [""]
    # Greedy wrap character-by-character (works for both CJK and latin).
    # For a scanned-PDF failure test, wrap fidelity does not need to be perfect.
    out: list[str] = []
    buf = ""
    for ch in text:
        candidate = buf + ch
        # textlength is available on PIL ImageFont (Pillow ≥9)
        try:
            width = font.getlength(candidate)  # type: ignore[attr-defined]
        except Exception:
            # Older PIL: use getsize
            width = font.getsize(candidate)[0]  # type: ignore[attr-defined]
        if width > max_width and buf:
            out.append(buf)
            buf = ch
        else:
            buf = candidate
    if buf:
        out.append(buf)
    return out or [""]


def _render_lines_to_images(lines: list[str], font: ImageFont.ImageFont) -> list[Image.Image]:
    """Paginate lines across PIL images, soft-wrapping as needed."""
    images: list[Image.Image] = []
    current = Image.new("RGB", (PAGE_W, PAGE_H), "white")
    draw = ImageDraw.Draw(current)
    y = MARGIN
    max_text_width = PAGE_W - 2 * MARGIN

    for line in lines:
        wrapped = _wrap_line(line, font, max_text_width)
        for sub in wrapped:
            if y + LINE_HEIGHT > PAGE_H - MARGIN:
                images.append(current)
                current = Image.new("RGB", (PAGE_W, PAGE_H), "white")
                draw = ImageDraw.Draw(current)
                y = MARGIN
            draw.text((MARGIN, y), sub, fill="black", font=font)
            y += LINE_HEIGHT

    images.append(current)
    return images


def main() -> int:
    if not SRC_MD.exists():
        print(f"ERROR: source MD not found: {SRC_MD}", file=sys.stderr)
        return 1

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)

    md_text = SRC_MD.read_text(encoding="utf-8")
    lines = md_text.split("\n")

    font = _load_font()
    images = _render_lines_to_images(lines, font)

    # Build an image-only PDF via pymupdf
    pdf = pymupdf.open()
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        page = pdf.new_page(width=PAGE_W, height=PAGE_H)
        page.insert_image(pymupdf.Rect(0, 0, PAGE_W, PAGE_H), stream=png_bytes)

    pdf.save(str(OUT_PDF))
    pdf.close()

    print(f"OK: wrote {OUT_PDF}")
    print(f"  size: {OUT_PDF.stat().st_size} bytes")
    print(f"  pages: {len(images)}")
    print(f"  source: {SRC_MD}")
    print(f"  source size: {SRC_MD.stat().st_size} bytes")
    print(f"  expected B3 behavior: pymupdf4llm extracts empty → staging zero segments or error")
    return 0


if __name__ == "__main__":
    sys.exit(main())
