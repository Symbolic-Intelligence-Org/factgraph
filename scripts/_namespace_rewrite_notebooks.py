"""One-shot namespace rewrite for examples/*.ipynb (rewrite + check modes).

Apply Blueprint §5.3 rewrite rules (import + quoted-string + naked-dotted +
bare-string) to all 8 in-scope notebooks. Run once during kernel namespace
split atomic commit. Delete in OS-prep cleanup or keep as historical artifact.

Modes:
  default          rewrite cell sources in-place, write back to disk,
                   report substitutions made and post-rewrite residual
                   (post-rewrite residual = sanity check that rewrite rules
                   are complete; should be 0)

  --check          read disk content as-is, count `factpy_kernel` substring
                   in code+markdown cell sources, exit 1 if any.
                   THIS IS THE SOURCE-OF-TRUTH for "is the notebook clean
                   on disk" (no in-memory rewrite is performed).

Outputs are NOT scanned in either mode (runtime artifacts refresh on next
notebook execution; legacy strings in old outputs would otherwise produce
false-positive validation failures).

Blueprint: docs/blueprints/active/2026-04-27_kernel-namespace-split.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import nbformat

NOTEBOOKS = [
    "examples/01_sdk_basics.ipynb",
    "examples/02_rules_and_derivations.ipynb",
    "examples/04_ecss_souffle_compliance.ipynb",
    "examples/05_dora_pyreason_propagation.ipynb",
    "examples/06_problog_probabilistic.ipynb",
    "examples/07_evidence_graph_multi_engine.ipynb",
    "examples/08_agent_document_workflow.ipynb",
    "examples/09_dora_document_extraction.ipynb",
]

# Order is significant within each pass group: specific moved files >
# sub-namespace > catch-all. See Blueprint §5.3 for rationale.
REWRITES: list[tuple[str, str]] = [
    # === Pass 1: specific moved files (from/import) ===
    (r"\bfrom factpy_kernel\.tests\._test_helpers\b", "from kernel.tests._test_helpers"),
    (r"\bimport factpy_kernel\.tests\._test_helpers\b", "import kernel.tests._test_helpers"),
    # === Pass 2: sub-namespace (from/import) ===
    # === Pass 3: catch-all (from/import) ===
    (r"\bfrom factpy_kernel\.", "from kernel."),
    (r"\bimport factpy_kernel\.", "import kernel."),
    # === Pass 4: quoted-string runtime targets (double-quote) ===
    (r'"factpy_kernel\.tests\._test_helpers', '"kernel.tests._test_helpers'),
    (r'"factpy_kernel\.', '"kernel.'),
    # === Pass 5: quoted-string runtime targets (single-quote) ===
    (r"'factpy_kernel\.tests\._test_helpers", "'kernel.tests._test_helpers"),
    (r"'factpy_kernel\.", "'kernel."),
    # === Pass 6: naked dotted refs (no prefix — markdown table cells,
    #     inline backticks, code comments) ===
    (r"\bfactpy_kernel\.tests\._test_helpers\b", "kernel.tests._test_helpers"),
    (r"\bfactpy_kernel\.", "kernel."),
    # === Pass 7: bare-string prose (must be LAST — after all dotted forms
    #     have been rewritten) ===
    # Risk: may incorrectly rewrite prose where `factpy_kernel` referred to
    # the monolithic project name; manual review of notebook 08 cell 3
    # recommended after script run.
    (r"\bfactpy_kernel\b", "kernel"),
]

REWRITE_CELL_TYPES = {"code", "markdown"}


def rewrite_text(s: str) -> tuple[str, int]:
    new = s
    total = 0
    for pat, repl in REWRITES:
        new, n = re.subn(pat, repl, new)
        total += n
    return new, total


def count_residual(nb) -> int:
    """Count `factpy_kernel` substring in code+markdown cell sources only."""
    return sum(
        cell.source.count("factpy_kernel")
        for cell in nb.cells
        if cell.cell_type in REWRITE_CELL_TYPES
    )


def process_notebook_rewrite(nb_path: Path) -> tuple[int, int]:
    """Apply rewrite rules in-place, write back, return (subs_made, post_rewrite_residual).

    Post-rewrite residual is a sanity check: should be 0 if REWRITES is complete.
    """
    nb = nbformat.read(nb_path, as_version=4)
    subs = 0
    for cell in nb.cells:
        if cell.cell_type not in REWRITE_CELL_TYPES:
            continue
        new_src, n = rewrite_text(cell.source)
        if n:
            cell.source = new_src
            subs += n
    if subs:
        nbformat.write(nb, nb_path)
    residual = count_residual(nb)
    return subs, residual


def process_notebook_check(nb_path: Path) -> int:
    """Read disk content as-is, count residual without rewriting.

    THIS IS THE SOURCE-OF-TRUTH for "is the notebook clean on disk".
    Does NOT call rewrite_text — that would mask uncommitted residuals.
    """
    nb = nbformat.read(nb_path, as_version=4)
    return count_residual(nb)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="Don't rewrite; report disk-truth residual factpy_kernel in cell sources, exit 1 if any.",
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    if args.check:
        grand_residual = 0
        for rel in NOTEBOOKS:
            path = repo_root / rel
            if not path.exists():
                print(f"[skip] not found: {rel}")
                continue
            residual = process_notebook_check(path)
            print(f"[check] {rel}: residual={residual}")
            grand_residual += residual
        print(f"\nTotal disk-truth residual: {grand_residual}")
        if grand_residual > 0:
            print("\nFAIL: residual `factpy_kernel` in cell sources on disk.", file=sys.stderr)
            return 1
        return 0
    else:
        grand_subs = 0
        grand_residual = 0
        for rel in NOTEBOOKS:
            path = repo_root / rel
            if not path.exists():
                print(f"[skip] not found: {rel}")
                continue
            subs, residual = process_notebook_rewrite(path)
            verb = "wrote" if subs else "clean"
            print(f"[{verb}] {rel}: subs={subs} post-rewrite-residual={residual}")
            grand_subs += subs
            grand_residual += residual
        print(f"\nTotal substitutions: {grand_subs}")
        print(f"Total post-rewrite residual: {grand_residual}")
        if grand_residual > 0:
            print(
                "\nWARN: rewrite rules incomplete — some `factpy_kernel` survived rewrite.",
                file=sys.stderr,
            )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
