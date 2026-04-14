"""Run DORA extraction on a regulatory PDF.

Minimal end-to-end demo of `extract_document()` against real PDFs.

Usage:
    python demo/dora_pdf_extract.py path/to/dora.pdf
    python demo/dora_pdf_extract.py path/to/dora.pdf --max-segments 80 --gleaning

Prerequisites:
    pip install -e ".[extraction,documents]"
    export MISTRAL_API_KEY=...   # or OPENAI_API_KEY with --model gpt-4.1
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from factpy_kernel.sdk import Entity, Field, Identity
from factpy_kernel.sdk.compile import compile_schema_from_classes
from factpy_kernel.agent.documents import DocumentStaging, StagingError
from factpy_kernel.agent.session import AgentScope
from factpy_kernel.agent.extraction.batch import BatchExtractor
from factpy_kernel.agent.extraction.extractor import ExtractionAgent
from factpy_kernel.agent.extraction.models import BatchExtractionConfig, BatchExtractionError, ExtractionConfig
from factpy_kernel.agent.extraction.resolution import EntityResolver, ResolutionConfig, ResolutionError


class Regulation(Entity):
    title: str = Identity(primary_key=True)
    summary: str = Field(cardinality="single", description="What this regulation or article requires.")
    scope: str = Field(cardinality="single", description="Who or what this regulation applies to.")


class Organization(Entity):
    name: str = Identity(primary_key=True)
    role: str = Field(cardinality="single", description="Role: financial entity, ICT provider, regulator, or supervisory authority.")
    description: str = Field(cardinality="single", description="Brief description.")


class Requirement(Entity):
    name: str = Identity(primary_key=True)
    description: str = Field(cardinality="single", description="What must be done to comply.")
    category: str = Field(cardinality="single", description="Category: ICT risk management, incident reporting, resilience testing, third-party risk, or information sharing.")


class ICTService(Entity):
    name: str = Identity(primary_key=True)
    provider: str = Field(cardinality="single", description="Organization that provides this ICT service.")
    criticality: str = Field(cardinality="single", description="Criticality: critical, important, or standard.")


class Risk(Entity):
    name: str = Identity(primary_key=True)
    description: str = Field(cardinality="single", description="Description of this ICT-related risk.")
    mitigation: str = Field(cardinality="single", description="Required mitigation measure.")


SCHEMA_CLASSES = [Regulation, Organization, Requirement, ICTService, Risk]
ENTITY_DESCRIPTIONS = {
    "Regulation": "A specific DORA article, chapter, or regulatory provision.",
    "Organization": "A financial entity, ICT provider, regulator, or supervisory authority.",
    "Requirement": "A compliance requirement imposed by DORA. NOT a general description.",
    "ICTService": "A specific ICT service or system used by financial entities.",
    "Risk": "An ICT-related operational risk identified in the document.",
}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Run DORA extraction on a regulatory PDF.")
    ap.add_argument("pdf", nargs="?", default=None, help="Path to PDF (default: demo sample)")
    ap.add_argument("--max-segments", type=int, default=40, help="Max segments to process (0 = all)")
    ap.add_argument("--min-chars", type=int, default=80, help="Skip segments shorter than this")
    ap.add_argument("--model", default="mistral/mistral-small-latest")
    ap.add_argument("--gleaning", action="store_true")
    ap.add_argument("--output", default=None, help="Output JSON path (default: ./<pdf_stem>_result.json)")
    args = ap.parse_args()

    if args.pdf is None:
        print("Usage: python demo/dora_pdf_extract.py <path-to-pdf>")
        return 1
    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return 1
    content = pdf_path.read_bytes()
    print(f"PDF: {pdf_path.name}  ({len(content):,} bytes)")

    schema_ir = compile_schema_from_classes(SCHEMA_CLASSES)
    allowed_entity_types = frozenset(e["entity_type"] for e in schema_ir["entities"])
    allowed_pred_ids = frozenset(p["pred_id"] for p in schema_ir["predicates"])

    staging = DocumentStaging().stage_document(doc_name=pdf_path.name, content=content)
    if isinstance(staging, StagingError):
        print(f"STAGING FAILED: {staging.error_message}")
        return 1
    all_segs = list(staging.segments)
    # Keep only segments with real prose content.
    filtered = [s for s in all_segs if len(s.raw_text) >= args.min_chars]
    if args.max_segments > 0:
        subset = filtered[: args.max_segments]
    else:
        subset = filtered
    print(f"Staging: {len(all_segs)} total, {len(filtered)} after min-chars filter, using {len(subset)}")

    scope = AgentScope(
        agent_id="extract_document",
        allowed_entity_types=allowed_entity_types,
        allowed_pred_ids=allowed_pred_ids,
        max_batch_size=1000,
        require_source=True,
    )
    config = ExtractionConfig(model=args.model, temperature=0.0, timeout_seconds=60.0, max_retries=2)
    extractor = BatchExtractor(
        extraction_agent=ExtractionAgent(config=config),
        batch_config=BatchExtractionConfig(
            enable_entity_context=True,
            enable_gleaning=args.gleaning,
            gleaning_yield_threshold=0,
        ),
    )

    t0 = time.time()
    batch = extractor.extract_batch(
        segments=subset,
        schema_ir=schema_ir,
        scope=scope,
        source_doc_name=pdf_path.name,
        entity_descriptions=ENTITY_DESCRIPTIONS,
    )
    t_ext = time.time() - t0

    if isinstance(batch, BatchExtractionError):
        print(f"EXTRACTION FAILED: {batch.error_message}")
        return 2

    m = batch.metrics
    print()
    print(f"Extraction: {t_ext:.1f}s")
    print(f"  segments processed: {m.total_segments}")
    print(f"  proposals={m.total_proposal_count}  valid={m.total_valid_count}  rejected={m.total_rejection_count}")
    print(f"  gleaning re-examined: {batch.gleaning_segments_reexamined}")

    specs = list(batch.aggregated_specs)
    if not specs:
        print("No valid specs — nothing to resolve.")
        return 3

    resolver = EntityResolver(config=ResolutionConfig(enable_dedupe=True, enable_alias_merge=True))
    resolved = resolver.resolve_batch(specs)
    if isinstance(resolved, ResolutionError):
        print(f"RESOLUTION FAILED: {resolved.error_message}")
        return 4

    print(f"  resolved specs: {len(resolved.resolved_specs)}  merges: {len(resolved.merge_events)}")
    print()

    # Tally
    by_type: dict[str, dict[str, int]] = {}
    for spec in resolved.resolved_specs:
        name = next(iter(spec.entity_identity.values())) if spec.entity_identity else "?"
        d = by_type.setdefault(spec.entity_type, {})
        d[str(name)] = d.get(str(name), 0) + 1

    for etype in sorted(by_type):
        rows = by_type[etype]
        print(f"[{etype}] {len(rows)} unique entities")
        for name, cnt in sorted(rows.items(), key=lambda kv: -kv[1])[:15]:
            print(f"   - {name}  ({cnt} facts)")
        if len(rows) > 15:
            print(f"   ... +{len(rows) - 15} more")
        print()

    # Dump facts
    out = Path(args.output) if args.output else Path.cwd() / f"{pdf_path.stem}_result.json"
    out.write_text(json.dumps({
        "doc_name": pdf_path.name,
        "model": args.model,
        "segments_processed": len(subset),
        "entities_by_type": {k: list(v.keys()) for k, v in by_type.items()},
        "facts": [
            {
                "entity_type": f.entity_type,
                "entity_identity": f.entity_identity,
                "pred_id": f.pred_id,
                "field_values": list(f.field_values),
                "confidence": f.confidence,
            } for f in resolved.resolved_specs
        ],
        "metrics": {
            "total_segments": m.total_segments,
            "total_proposal_count": m.total_proposal_count,
            "total_valid_count": m.total_valid_count,
            "total_rejection_count": m.total_rejection_count,
            "batch_duration_ms": m.batch_duration_ms,
        },
    }, indent=2, default=str))
    print(f"Wrote: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
