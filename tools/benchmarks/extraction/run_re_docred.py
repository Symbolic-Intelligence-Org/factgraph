#!/usr/bin/env python3
"""Re-DocRED subset harness v1 — entity identification evaluation.

SCOPE LIMITATION: This is NOT relation extraction evaluation.
The current agent.extraction extract_document() extracts entity attributes
(name, description), not entity-to-entity relation triples.
Results measure entity discovery / grounding quality only and CANNOT be
compared to Re-DocRED relation extraction SOTA.

Evaluates: Does extract_document() correctly identify the entities
mentioned in Re-DocRED documents?

Gold: Re-DocRED vertexSet (canonical entity names)
Predicted: extract_document().entities (entity census from extracted facts)
Note: predicted entities are derived from extracted facts, so this measures
"entity-with-facts recall", not pure NER recall.

Usage:
    python tools/benchmarks/extraction/run_re_docred.py
    python tools/benchmarks/extraction/run_re_docred.py --samples 5
    python tools/benchmarks/extraction/run_re_docred.py --model gpt-4o
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from kernel.sdk import Entity, Field, Identity, compile_schema_from_classes
from agent.extraction import extract_document, ExtractionDocumentError
from agent.extraction.models import ExtractionConfig

# ── Paths ──
DATASET_DIR = _REPO_ROOT / "tools" / "datasets" / "re_docred"
SAMPLE_PATH = DATASET_DIR / "dev_sample_10.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


# ── Entity classes matching Re-DocRED's 6 types ──
class Person(Entity):
    name: str = Identity(primary_key=True)
    description: str = Field(cardinality="single", description="Brief description of this person.")

class Organization(Entity):
    name: str = Identity(primary_key=True)
    description: str = Field(cardinality="single", description="Brief description of this organization.")

class Location(Entity):
    name: str = Identity(primary_key=True)
    description: str = Field(cardinality="single", description="Brief description of this location.")

class TimePeriod(Entity):
    value: str = Identity(primary_key=True)
    description: str = Field(cardinality="single", description="Description of this time reference.")

class NumericValue(Entity):
    value: str = Identity(primary_key=True)
    description: str = Field(cardinality="single", description="Description of this numeric value.")

class MiscEntity(Entity):
    name: str = Identity(primary_key=True)
    description: str = Field(cardinality="single", description="Brief description of this entity.")


SCHEMA_CLASSES = [Person, Organization, Location, TimePeriod, NumericValue, MiscEntity]

ENTITY_DESCRIPTIONS = {
    "Person": "A named individual (person, historical figure, fictional character).",
    "Organization": "A named organization, company, team, political party, or institution.",
    "Location": "A named geographic or administrative location (city, country, region, building).",
    "TimePeriod": "A date, year, time period, or temporal expression.",
    "NumericValue": "A numeric value, quantity, or measurement.",
    "MiscEntity": "A named entity that doesn't fit other categories (works, events, awards, concepts).",
}

REDOCRED_TYPE_MAP = {
    "PER": "Person",
    "ORG": "Organization",
    "LOC": "Location",
    "TIME": "TimePeriod",
    "NUM": "NumericValue",
    "MISC": "MiscEntity",
}


# ── Re-DocRED document → plain text ──
def doc_to_text(doc: dict) -> str:
    lines = []
    for sent in doc.get("sents", []):
        lines.append(" ".join(sent))
    return "\n".join(lines)


# ── Gold entity extraction ──
def extract_gold_entities(doc: dict) -> list[dict[str, str]]:
    """Extract unique gold entities from Re-DocRED vertexSet."""
    entities = []
    seen = set()
    for vertex in doc.get("vertexSet", []):
        if not vertex:
            continue
        canonical_name = vertex[0]["name"].lower().strip()
        raw_type = vertex[0].get("type", "MISC")
        mapped_type = REDOCRED_TYPE_MAP.get(raw_type, "MiscEntity")
        key = (mapped_type, canonical_name)
        if key not in seen:
            seen.add(key)
            entities.append({"type": mapped_type, "name": canonical_name})
    return entities


# ── Predicted entity extraction ──
def extract_predicted_entities(result) -> list[dict[str, str]]:
    """Extract unique entities from extraction result."""
    entities = []
    for entity in result.entities:
        etype = entity.get("entity_type", "?")
        identity = entity.get("identity", {})
        name = (identity.get("name") or identity.get("value") or "").lower().strip()
        if name:
            entities.append({"type": etype, "name": name})
    return entities


# ── Entity matching ──
def entity_matches(pred: dict, gold: dict) -> bool:
    """Check if predicted entity fuzzy-matches a gold entity.

    Matches on name token overlap (>= 50%), type-agnostic for now
    (because our pipeline may classify differently than Re-DocRED).
    """
    p_tokens = set(pred["name"].split())
    g_tokens = set(gold["name"].split())

    if not p_tokens or not g_tokens:
        return False

    # Exact match
    if pred["name"] == gold["name"]:
        return True

    # Token subset: shorter is subset of longer
    shorter, longer = (p_tokens, g_tokens) if len(p_tokens) <= len(g_tokens) else (g_tokens, p_tokens)
    if shorter and shorter.issubset(longer):
        return True

    # Token overlap >= 50%
    overlap = len(p_tokens & g_tokens) / max(len(p_tokens), len(g_tokens))
    return overlap >= 0.5


# ── Evaluation ──
@dataclass
class DocResult:
    title: str
    gold_entities: int
    predicted_entities: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    total_facts: int
    duration_ms: int
    gold_entity_names: list[str]
    predicted_entity_names: list[str]
    matched_names: list[str]
    missed_names: list[str]
    error: str | None = None


def evaluate_doc(doc: dict, model: str) -> DocResult:
    title = doc.get("title", "?")
    text = doc_to_text(doc)
    content = text.encode("utf-8")

    gold = extract_gold_entities(doc)

    start = time.monotonic()
    try:
        result = extract_document(
            content=content,
            doc_name=f"{title}.txt",
            schema_classes=SCHEMA_CLASSES,
            model=model,
            entity_descriptions=ENTITY_DESCRIPTIONS,
            enable_gleaning=True,
            enable_alias_merge=True,
            max_batch_size=1000,
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
    except ExtractionDocumentError as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return DocResult(
            title=title, gold_entities=len(gold), predicted_entities=0,
            true_positives=0, false_positives=0, false_negatives=len(gold),
            precision=0.0, recall=0.0, f1=0.0, total_facts=0,
            duration_ms=elapsed_ms,
            gold_entity_names=[g["name"] for g in gold],
            predicted_entity_names=[], matched_names=[], missed_names=[g["name"] for g in gold],
            error=f"{exc.stage}: {exc}",
        )

    predicted = extract_predicted_entities(result)

    # Match: for each gold entity, check if any predicted entity matches
    matched_gold = set()
    matched_pred = set()
    matches = []

    for gi, g in enumerate(gold):
        for pi, p in enumerate(predicted):
            if pi in matched_pred:
                continue
            if entity_matches(p, g):
                matched_gold.add(gi)
                matched_pred.add(pi)
                matches.append(g["name"])
                break

    tp = len(matched_gold)
    fp = len(predicted) - len(matched_pred)
    fn = len(gold) - len(matched_gold)

    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    missed = [g["name"] for gi, g in enumerate(gold) if gi not in matched_gold]

    return DocResult(
        title=title,
        gold_entities=len(gold),
        predicted_entities=len(predicted),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        total_facts=len(result.facts),
        duration_ms=elapsed_ms,
        gold_entity_names=[g["name"] for g in gold],
        predicted_entity_names=[p["name"] for p in predicted],
        matched_names=matches,
        missed_names=missed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-DocRED entity identification benchmark")
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--dataset", type=str, default=str(SAMPLE_PATH))
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set.")
        return 1

    with open(args.dataset) as f:
        docs = json.load(f)
    docs = docs[:args.samples]
    model = args.model or os.environ.get("FACTPY_EXTRACTION_MODEL") or ExtractionConfig().model

    print("Re-DocRED subset harness v1 — ENTITY IDENTIFICATION (not relation extraction)")
    print(f"  Model: {model}")
    print(f"  Samples: {len(docs)}")
    print(f"  Schema: 6 entity types (attribute extraction only, no relationships)")
    print(f"  Eval: entity-level P/R/F1 (entity-with-facts, not pure NER)")
    print()

    results: list[DocResult] = []
    for i, doc in enumerate(docs):
        title = doc.get("title", "?")[:35]
        print(f"  [{i+1}/{len(docs)}] {title}...", end=" ", flush=True)
        r = evaluate_doc(doc, model)
        if r.error:
            print(f"ERROR: {r.error}")
        else:
            print(f"P={r.precision:.0%} R={r.recall:.0%} F1={r.f1:.0%} "
                  f"(TP={r.true_positives} gold={r.gold_entities} pred={r.predicted_entities} "
                  f"facts={r.total_facts}) {r.duration_ms}ms")
        results.append(r)

    # ── Aggregate ──
    valid = [r for r in results if not r.error]
    if not valid:
        print("\nAll documents failed.")
        return 1

    total_tp = sum(r.true_positives for r in valid)
    total_pred = sum(r.predicted_entities for r in valid)
    total_gold = sum(r.gold_entities for r in valid)
    total_fp = sum(r.false_positives for r in valid)
    total_fn = sum(r.false_negatives for r in valid)

    macro_p = sum(r.precision for r in valid) / len(valid)
    macro_r = sum(r.recall for r in valid) / len(valid)
    macro_f1 = sum(r.f1 for r in valid) / len(valid)

    micro_p = total_tp / total_pred if total_pred else 0.0
    micro_r = total_tp / total_gold if total_gold else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0

    avg_duration = sum(r.duration_ms for r in valid) / len(valid)

    print(f"\n{'='*70}")
    print(f"ENTITY IDENTIFICATION RESULTS — Re-DocRED subset harness v1")
    print(f"{'='*70}")
    print(f"  NOTE: This is entity-with-facts recall, NOT relation extraction.")
    print(f"  Do NOT compare these numbers to Re-DocRED relation SOTA.")
    print(f"")
    print(f"  Model:           {model}")
    print(f"  Documents:       {len(valid)}/{len(docs)} succeeded")
    print(f"")
    print(f"  Micro P/R/F1:    {micro_p:.1%} / {micro_r:.1%} / {micro_f1:.1%}")
    print(f"  Macro P/R/F1:    {macro_p:.1%} / {macro_r:.1%} / {macro_f1:.1%}")
    print(f"  Total:           {total_tp} TP / {total_pred} predicted / {total_gold} gold")
    print(f"  Avg duration:    {avg_duration:.0f}ms / doc")

    # ── Per-doc table ──
    print(f"\n{'Title':<38} {'P':>5} {'R':>5} {'F1':>5} {'TP':>4} {'Pred':>5} {'Gold':>5} {'Facts':>5} {'ms':>6}")
    print("-" * 85)
    for r in results:
        if r.error:
            print(f"{r.title[:37]:<38} {'ERR':>5}")
        else:
            print(f"{r.title[:37]:<38} {r.precision:>4.0%} {r.recall:>4.0%} {r.f1:>4.0%} "
                  f"{r.true_positives:>4} {r.predicted_entities:>5} {r.gold_entities:>5} "
                  f"{r.total_facts:>5} {r.duration_ms:>6}")

    # ── Missed entities sample ──
    print(f"\nMost commonly missed entities (top 10):")
    all_missed = Counter()
    for r in valid:
        for name in r.missed_names:
            all_missed[name] += 1
    for name, count in all_missed.most_common(10):
        print(f"  {name} (missed in {count} doc(s))")

    # ── Save results ──
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    result_path = RESULTS_DIR / f"entity_id_{model.replace('/', '_')}_{ts}.json"
    with open(result_path, "w") as f:
        json.dump({
            "meta": {
                "model": model,
                "samples": len(docs),
                "harness_version": "v1",
                "eval_type": "entity_identification_only",
                "note": "entity-with-facts recall, NOT relation extraction or pure NER",
                "timestamp": ts,
            },
            "aggregate": {
                "micro_precision": micro_p,
                "micro_recall": micro_r,
                "micro_f1": micro_f1,
                "macro_precision": macro_p,
                "macro_recall": macro_r,
                "macro_f1": macro_f1,
                "total_tp": total_tp,
                "total_predicted": total_pred,
                "total_gold": total_gold,
                "avg_duration_ms": avg_duration,
            },
            "per_doc": [asdict(r) for r in results],
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved: {result_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
