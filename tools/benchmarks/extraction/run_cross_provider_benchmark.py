#!/usr/bin/env python3
"""Cross-provider entity identification benchmark.

Compares OpenAI vs Groq (Llama) models on Re-DocRED entity identification.
Reuses the same evaluation logic as run_re_docred.py.

Usage:
    python tools/benchmarks/extraction/run_cross_provider_benchmark.py
    python tools/benchmarks/extraction/run_cross_provider_benchmark.py --samples 5
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

from kernel.sdk import Entity, Field, Identity
from agent.extraction import extract_document, ExtractionDocumentError
from agent.extraction.models import ExtractionConfig

DATASET_DIR = _REPO_ROOT / "tools" / "datasets" / "re_docred"
SAMPLE_PATH = DATASET_DIR / "dev_sample_10.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

# ── Models ──
MODELS = [
    # (model_id, display_name, provider, cost_hint, env_key)
    ("gpt-4.1-mini",  "GPT-4.1 Mini",    "OpenAI", "~$0.0004/1K", "OPENAI_API_KEY"),
    ("gpt-4.1",       "GPT-4.1",         "OpenAI", "~$0.002/1K",  "OPENAI_API_KEY"),
    ("groq/llama-3.1-8b-instant",                   "Llama 3.1 8B (Groq)",   "Groq", "FREE", "GROQ_API_KEY"),
    ("groq/meta-llama/llama-4-scout-17b-16e-instruct", "Llama 4 Scout 17B (Groq)", "Groq", "FREE", "GROQ_API_KEY"),
    ("groq/llama-3.3-70b-versatile",                "Llama 3.3 70B (Groq)",  "Groq", "FREE", "GROQ_API_KEY"),
]

# ── Schema ──
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
    "Location": "A named geographic or administrative location.",
    "TimePeriod": "A date, year, time period, or temporal expression.",
    "NumericValue": "A numeric value, quantity, or measurement.",
    "MiscEntity": "A named entity that doesn't fit other categories.",
}
REDOCRED_TYPE_MAP = {
    "PER": "Person", "ORG": "Organization", "LOC": "Location",
    "TIME": "TimePeriod", "NUM": "NumericValue", "MISC": "MiscEntity",
}


def doc_to_text(doc):
    return "\n".join(" ".join(s) for s in doc.get("sents", []))

def extract_gold_entities(doc):
    entities, seen = [], set()
    for vertex in doc.get("vertexSet", []):
        if not vertex: continue
        name = vertex[0]["name"].lower().strip()
        mapped = REDOCRED_TYPE_MAP.get(vertex[0].get("type", "MISC"), "MiscEntity")
        if (mapped, name) not in seen:
            seen.add((mapped, name))
            entities.append({"type": mapped, "name": name})
    return entities

def extract_predicted_entities(result):
    entities = []
    for e in result.entities:
        identity = e.get("identity", {})
        name = (identity.get("name") or identity.get("value") or "").lower().strip()
        if name:
            entities.append({"type": e.get("entity_type", "?"), "name": name})
    return entities

def entity_matches(pred, gold):
    p_tokens = set(pred["name"].split())
    g_tokens = set(gold["name"].split())
    if not p_tokens or not g_tokens: return False
    if pred["name"] == gold["name"]: return True
    shorter, longer = (p_tokens, g_tokens) if len(p_tokens) <= len(g_tokens) else (g_tokens, p_tokens)
    if shorter and shorter.issubset(longer): return True
    return len(p_tokens & g_tokens) / max(len(p_tokens), len(g_tokens)) >= 0.5


@dataclass
class ModelResult:
    model: str
    display: str
    provider: str
    cost: str
    docs_ok: int
    docs_total: int
    micro_p: float
    micro_r: float
    micro_f1: float
    total_tp: int
    total_pred: int
    total_gold: int
    total_facts: int
    avg_ms: float
    error: str | None = None


def run_model(model_id, display, provider, cost, env_key, docs):
    if not os.environ.get(env_key):
        return ModelResult(model=model_id, display=display, provider=provider, cost=cost,
                           docs_ok=0, docs_total=len(docs), micro_p=0, micro_r=0, micro_f1=0,
                           total_tp=0, total_pred=0, total_gold=0, total_facts=0, avg_ms=0,
                           error=f"{env_key} not set")

    results = []
    for doc in docs:
        title = doc.get("title", "?")
        gold = extract_gold_entities(doc)
        text = doc_to_text(doc)

        start = time.monotonic()
        try:
            result = extract_document(
                content=text.encode("utf-8"),
                doc_name=f"{title}.txt",
                schema_classes=SCHEMA_CLASSES,
                model=model_id,
                entity_descriptions=ENTITY_DESCRIPTIONS,
                enable_gleaning=True,
                enable_alias_merge=True,
                max_batch_size=1000,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            predicted = extract_predicted_entities(result)
            facts = len(result.facts)
        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            results.append({"gold": len(gold), "pred": 0, "tp": 0, "facts": 0, "ms": elapsed, "err": str(exc)[:80]})
            continue

        matched_gold, matched_pred = set(), set()
        for gi, g in enumerate(gold):
            for pi, p in enumerate(predicted):
                if pi in matched_pred: continue
                if entity_matches(p, g):
                    matched_gold.add(gi)
                    matched_pred.add(pi)
                    break

        results.append({"gold": len(gold), "pred": len(predicted), "tp": len(matched_gold),
                        "facts": facts, "ms": elapsed, "err": None})

    valid = [r for r in results if r["err"] is None]
    if not valid:
        return ModelResult(model=model_id, display=display, provider=provider, cost=cost,
                           docs_ok=0, docs_total=len(docs), micro_p=0, micro_r=0, micro_f1=0,
                           total_tp=0, total_pred=0, total_gold=0, total_facts=0, avg_ms=0,
                           error="All docs failed")

    tp = sum(r["tp"] for r in valid)
    pred = sum(r["pred"] for r in valid)
    gold = sum(r["gold"] for r in valid)
    facts = sum(r["facts"] for r in valid)
    p = tp / pred if pred else 0
    r = tp / gold if gold else 0
    f1 = 2*p*r/(p+r) if (p+r) > 0 else 0

    return ModelResult(model=model_id, display=display, provider=provider, cost=cost,
                       docs_ok=len(valid), docs_total=len(docs),
                       micro_p=p, micro_r=r, micro_f1=f1,
                       total_tp=tp, total_pred=pred, total_gold=gold, total_facts=facts,
                       avg_ms=sum(r["ms"] for r in valid)/len(valid))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=10)
    args = parser.parse_args()

    with open(SAMPLE_PATH) as f:
        docs = json.load(f)
    docs = docs[:args.samples]

    print("=" * 90)
    print("CROSS-PROVIDER ENTITY IDENTIFICATION BENCHMARK")
    print("Re-DocRED subset — ENTITY IDENTIFICATION ONLY (not relation extraction)")
    print("=" * 90)
    print(f"  Samples: {len(docs)} | Config: P0+P1+P2+F1+I1+I2 all ON")
    print()

    results = []
    for model_id, display, provider, cost, env_key in MODELS:
        print(f"  Running {display}...", end=" ", flush=True)
        r = run_model(model_id, display, provider, cost, env_key, docs)
        if r.error:
            print(f"FAILED: {r.error}")
        else:
            print(f"P={r.micro_p:.0%} R={r.micro_r:.0%} F1={r.micro_f1:.0%} "
                  f"({r.docs_ok}/{r.docs_total} ok, {r.avg_ms:.0f}ms/doc)")
        results.append(r)

    print(f"\n{'='*90}")
    print(f"{'Model':<30} {'Provider':<8} {'μP':>5} {'μR':>5} {'μF1':>5} "
          f"{'TP':>4} {'Pred':>5} {'Gold':>5} {'Facts':>5} {'ms/doc':>8} {'Cost':>14} {'OK':>5}")
    print("-" * 90)
    for r in results:
        if r.error:
            print(f"{r.display:<30} {r.provider:<8} {'FAILED':>5} — {r.error}")
        else:
            print(f"{r.display:<30} {r.provider:<8} {r.micro_p:>4.0%} {r.micro_r:>4.0%} {r.micro_f1:>4.0%} "
                  f"{r.total_tp:>4} {r.total_pred:>5} {r.total_gold:>5} {r.total_facts:>5} "
                  f"{r.avg_ms:>7.0f}ms {r.cost:>14} {r.docs_ok:>2}/{r.docs_total}")

    valid = [r for r in results if not r.error]
    if valid:
        best = max(valid, key=lambda r: r.micro_f1)
        fastest = min(valid, key=lambda r: r.avg_ms)
        cheapest_good = max([r for r in valid if r.cost == "FREE"], key=lambda r: r.micro_f1, default=None)
        print(f"\n  Best F1:       {best.display} ({best.micro_f1:.0%})")
        print(f"  Fastest:       {fastest.display} ({fastest.avg_ms:.0f}ms/doc)")
        if cheapest_good:
            print(f"  Best free:     {cheapest_good.display} ({cheapest_good.micro_f1:.0%})")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%S")
    path = RESULTS_DIR / f"cross_provider_{ts}.json"
    with open(path, "w") as f:
        json.dump({"meta": {"samples": len(docs), "timestamp": ts},
                   "results": [asdict(r) for r in results]}, f, indent=2)
    print(f"\n  Results saved: {path}")


if __name__ == "__main__":
    main()
