#!/usr/bin/env python3
"""Multi-model entity identification benchmark on Re-DocRED.

Runs the entity identification harness across multiple OpenAI model tiers
and produces a comparison report.

SCOPE: Entity identification only (not relation extraction).
See run_re_docred.py header for full scope limitation statement.

Usage:
    python tools/benchmarks/extraction/run_multi_model_entity_benchmark.py
    python tools/benchmarks/extraction/run_multi_model_entity_benchmark.py --samples 5
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

# ── Models to benchmark ──
# Ordered by expected capability tier (cheapest → most expensive)
MODELS = [
    ("gpt-4.1-nano",  "Tier 0 — nano",         "~$0.0001/1K tok"),
    ("gpt-4o-mini",   "Tier 1 — 4o lightweight", "~$0.00015/1K tok"),
    ("gpt-4.1-mini",  "Tier 2 — 4.1 lightweight","~$0.0004/1K tok"),
    ("gpt-3.5-turbo", "Tier 3 — legacy",         "~$0.0005/1K tok"),
    ("gpt-4o",        "Tier 4 — 4o mid-range",   "~$0.0025/1K tok"),
    ("gpt-4.1",       "Tier 5 — 4.1 flagship",   "~$0.002/1K tok"),
    ("gpt-4-turbo",   "Tier 6 — 4 turbo",        "~$0.01/1K tok"),
]


# ── Entity classes (same as run_re_docred.py) ──
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
    "PER": "Person", "ORG": "Organization", "LOC": "Location",
    "TIME": "TimePeriod", "NUM": "NumericValue", "MISC": "MiscEntity",
}


def doc_to_text(doc: dict) -> str:
    return "\n".join(" ".join(s) for s in doc.get("sents", []))


def extract_gold_entities(doc: dict) -> list[dict[str, str]]:
    entities, seen = [], set()
    for vertex in doc.get("vertexSet", []):
        if not vertex:
            continue
        name = vertex[0]["name"].lower().strip()
        mapped = REDOCRED_TYPE_MAP.get(vertex[0].get("type", "MISC"), "MiscEntity")
        key = (mapped, name)
        if key not in seen:
            seen.add(key)
            entities.append({"type": mapped, "name": name})
    return entities


def extract_predicted_entities(result) -> list[dict[str, str]]:
    entities = []
    for e in result.entities:
        identity = e.get("identity", {})
        name = (identity.get("name") or identity.get("value") or "").lower().strip()
        if name:
            entities.append({"type": e.get("entity_type", "?"), "name": name})
    return entities


def entity_matches(pred: dict, gold: dict) -> bool:
    p_tokens = set(pred["name"].split())
    g_tokens = set(gold["name"].split())
    if not p_tokens or not g_tokens:
        return False
    if pred["name"] == gold["name"]:
        return True
    shorter, longer = (p_tokens, g_tokens) if len(p_tokens) <= len(g_tokens) else (g_tokens, p_tokens)
    if shorter and shorter.issubset(longer):
        return True
    return len(p_tokens & g_tokens) / max(len(p_tokens), len(g_tokens)) >= 0.5


@dataclass
class ModelResult:
    model: str
    tier: str
    cost_hint: str
    docs_ok: int
    docs_total: int
    micro_p: float
    micro_r: float
    micro_f1: float
    macro_p: float
    macro_r: float
    macro_f1: float
    total_tp: int
    total_pred: int
    total_gold: int
    total_facts: int
    avg_duration_ms: float
    per_doc: list[dict]
    error: str | None = None


def run_model(model_name: str, tier: str, cost_hint: str, docs: list, schema_classes: list) -> ModelResult:
    per_doc = []
    for doc in docs:
        title = doc.get("title", "?")
        text = doc_to_text(doc)
        gold = extract_gold_entities(doc)

        start = time.monotonic()
        try:
            result = extract_document(
                content=text.encode("utf-8"),
                doc_name=f"{title}.txt",
                schema_classes=schema_classes,
                model=model_name,
                entity_descriptions=ENTITY_DESCRIPTIONS,
                enable_gleaning=True,
                enable_alias_merge=True,
                max_batch_size=1000,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            predicted = extract_predicted_entities(result)
            facts = len(result.facts)
        except (ExtractionDocumentError, Exception) as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            per_doc.append({
                "title": title, "gold": len(gold), "pred": 0, "tp": 0,
                "precision": 0.0, "recall": 0.0, "f1": 0.0, "facts": 0,
                "duration_ms": elapsed, "error": str(exc),
            })
            continue

        matched_gold, matched_pred = set(), set()
        for gi, g in enumerate(gold):
            for pi, p in enumerate(predicted):
                if pi in matched_pred:
                    continue
                if entity_matches(p, g):
                    matched_gold.add(gi)
                    matched_pred.add(pi)
                    break

        tp = len(matched_gold)
        precision = tp / len(predicted) if predicted else 0.0
        recall = tp / len(gold) if gold else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        per_doc.append({
            "title": title, "gold": len(gold), "pred": len(predicted),
            "tp": tp, "precision": precision, "recall": recall, "f1": f1,
            "facts": facts, "duration_ms": elapsed, "error": None,
        })

    valid = [d for d in per_doc if d["error"] is None]
    if not valid:
        return ModelResult(
            model=model_name, tier=tier, cost_hint=cost_hint,
            docs_ok=0, docs_total=len(docs),
            micro_p=0, micro_r=0, micro_f1=0,
            macro_p=0, macro_r=0, macro_f1=0,
            total_tp=0, total_pred=0, total_gold=0, total_facts=0,
            avg_duration_ms=0, per_doc=per_doc,
            error="All docs failed",
        )

    total_tp = sum(d["tp"] for d in valid)
    total_pred = sum(d["pred"] for d in valid)
    total_gold = sum(d["gold"] for d in valid)
    total_facts = sum(d["facts"] for d in valid)
    micro_p = total_tp / total_pred if total_pred else 0
    micro_r = total_tp / total_gold if total_gold else 0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0
    macro_p = sum(d["precision"] for d in valid) / len(valid)
    macro_r = sum(d["recall"] for d in valid) / len(valid)
    macro_f1 = sum(d["f1"] for d in valid) / len(valid)
    avg_dur = sum(d["duration_ms"] for d in valid) / len(valid)

    return ModelResult(
        model=model_name, tier=tier, cost_hint=cost_hint,
        docs_ok=len(valid), docs_total=len(docs),
        micro_p=micro_p, micro_r=micro_r, micro_f1=micro_f1,
        macro_p=macro_p, macro_r=macro_r, macro_f1=macro_f1,
        total_tp=total_tp, total_pred=total_pred, total_gold=total_gold,
        total_facts=total_facts, avg_duration_ms=avg_dur, per_doc=per_doc,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--dataset", type=str, default=str(SAMPLE_PATH))
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set.")
        return 1

    with open(args.dataset) as f:
        docs = json.load(f)
    docs = docs[:args.samples]

    print("=" * 80)
    print("MULTI-MODEL ENTITY IDENTIFICATION BENCHMARK")
    print("Re-DocRED subset harness v1 — ENTITY IDENTIFICATION ONLY")
    print("=" * 80)
    print(f"  Samples: {len(docs)} documents")
    print(f"  Models:  {len(MODELS)}")
    print(f"  Config:  P0 entity context ON, P1 gleaning ON, P2 alias merge ON")
    print(f"  Eval:    entity-with-facts P/R/F1 (NOT relation extraction)")
    print()

    results: list[ModelResult] = []
    for model_name, tier, cost in MODELS:
        print(f"── {model_name} ({tier}) ──")
        r = run_model(model_name, tier, cost, docs, SCHEMA_CLASSES)
        if r.error:
            print(f"  FAILED: {r.error}")
        else:
            print(f"  Micro P/R/F1: {r.micro_p:.0%} / {r.micro_r:.0%} / {r.micro_f1:.0%}")
            print(f"  {r.total_tp} TP / {r.total_pred} pred / {r.total_gold} gold / {r.total_facts} facts")
            print(f"  Avg: {r.avg_duration_ms:.0f}ms/doc  |  {r.docs_ok}/{r.docs_total} succeeded")
        print()
        results.append(r)

    # ── Comparison table ──
    print("=" * 100)
    print("COMPARISON TABLE")
    print("=" * 100)
    print(f"{'Model':<18} {'Tier':<25} {'μP':>5} {'μR':>5} {'μF1':>5} {'TP':>4} {'Pred':>5} "
          f"{'Gold':>5} {'Facts':>5} {'ms/doc':>7} {'Cost':>18}")
    print("-" * 100)
    for r in results:
        if r.error:
            print(f"{r.model:<18} {r.tier:<25} {'FAILED':>5}")
        else:
            print(f"{r.model:<18} {r.tier:<25} {r.micro_p:>4.0%} {r.micro_r:>4.0%} {r.micro_f1:>4.0%} "
                  f"{r.total_tp:>4} {r.total_pred:>5} {r.total_gold:>5} {r.total_facts:>5} "
                  f"{r.avg_duration_ms:>6.0f}ms {r.cost_hint:>18}")

    # ── Best in class ──
    valid = [r for r in results if not r.error]
    if valid:
        best_f1 = max(valid, key=lambda r: r.micro_f1)
        best_p = max(valid, key=lambda r: r.micro_p)
        best_r = max(valid, key=lambda r: r.micro_r)
        fastest = min(valid, key=lambda r: r.avg_duration_ms)
        most_facts = max(valid, key=lambda r: r.total_facts)

        print(f"\n  Best F1:        {best_f1.model} ({best_f1.micro_f1:.0%})")
        print(f"  Best Precision: {best_p.model} ({best_p.micro_p:.0%})")
        print(f"  Best Recall:    {best_r.model} ({best_r.micro_r:.0%})")
        print(f"  Fastest:        {fastest.model} ({fastest.avg_duration_ms:.0f}ms/doc)")
        print(f"  Most facts:     {most_facts.model} ({most_facts.total_facts} facts)")

    # ── Save ──
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    path = RESULTS_DIR / f"multi_model_entity_{ts}.json"
    with open(path, "w") as f:
        json.dump({
            "meta": {
                "harness": "Re-DocRED subset v1",
                "eval_type": "entity_identification_only",
                "samples": len(docs),
                "models": len(MODELS),
                "timestamp": ts,
            },
            "results": [asdict(r) for r in results],
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
