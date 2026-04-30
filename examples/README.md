# Examples Index

Examples are split into two tiers:

- **Kernel examples** demonstrate the v0.1 kernel package surface.
- **Private monorepo examples** use `service.*`, `agent.*`, `domains.*`, external engines, or real API keys and are not part of the v0.1 kernel-only wheel.

The public release projection currently does not include notebooks. These files remain monorepo validation and demo material until an examples add-back pass verifies them for the public repository.

## Default-Wheel Kernel Examples

These notebooks use only the default `kernel` package surface.

| # | Notebook | Adapter | Domain | Covers |
|---|----------|---------|--------|--------|
| 01 | `01_sdk_basics.ipynb` | — | general | Entity / Schema / Store / CRUD / Batch / Edit / Ingest |
| 02 | `02_rules_and_derivations.ipynb` | — (native) | general | Rule DSL / Query / Derivation / Accept / Registry |
| 10 | `10_v01_onboarding_journey.ipynb` | — (native) | general | end-to-end v0.1 journey: ref -> set/add -> get -> query -> derive/accept -> export/read audit package + evidence tree |

## Kernel Optional-Engine Examples

These notebooks stay under the `kernel.*` namespace but require optional local engines.

| # | Notebook | Adapter | Domain | Covers |
|---|----------|---------|--------|--------|
| 05 | `05_dora_pyreason_propagation.ipynb` | **PyReason** | **DORA** | boolean propagation / temporal reasoning / adapter-local session |
| 06 | `06_problog_probabilistic.ipynb` | **ProbLog** | general | probabilistic reasoning / ProbLogRuleExt / persist annotations |

## Private Monorepo Examples

These examples use monorepo-only packages or real external services. They are useful for private development and demos, but they should not be presented as v0.1 kernel-only wheel examples.

| # | Notebook / Script | Adapter | Domain | Covers |
|---|-------------------|---------|--------|--------|
| 03 | `03_dora_minimal_evidence_tree.ipynb` | — (native) | **DORA** | source-backed definitions -> candidate finding -> evidence tree / summary / narrative / HTML |
| 04 | `04_ecss_souffle_compliance.ipynb` | **Souffle** | **ECSS** | compliance rules / certainty / audit package / static site / proof tree |
| 07 | `07_evidence_graph_multi_engine.ipynb` | **all three** | general | evidence tree + certainty + probability + timeline + cross-engine comparison |
| 08 | `08_agent_document_workflow.ipynb` | **real OpenAI LLM** | agent | Agent layer end-to-end: staging / extraction + resolve / bundle review + commit / real SQLite ledger |
| 09 | `09_dora_document_extraction.ipynb` | **real Mistral / OpenAI LLM** | **DORA** | `extract_document()` product API: schema compile -> staging -> batch extraction + gleaning -> alias merge |
| CLI | `dora_pdf_extract.py` | real document parser / LLM stack | **DORA** | command-line wrapper around `extract_document()` for regulatory PDFs |

Companion data:

- `dora_schema_ir.json` — pre-compiled schema IR that notebook 09 and the CLI script share.

## Notebook 03 — Minimal Evidence Tree Demo

Notebook 03 is the meeting-friendly evidence-tree entry point for private monorepo demos. It uses public DORA / EUR-Lex source anchors, derives one narrow review finding with the native engine, and then shows:

- the candidate result under review
- the `RuleRef` branch that forms the rule chain
- the source-backed assertion leaves
- deterministic summary / narrative / HTML views over the same tree

It does not make a real-entity compliance decision and does not require external engines, API keys, LLMs, or network access at runtime, but it still depends on monorepo delivery helpers outside the v0.1 kernel-only wheel.

## Notebook 07 — Flagship Demo

Notebook 07 is the comprehensive three-engine private monorepo demo. It covers:

- Evidence tree node hierarchy (candidate_result -> support -> witness / proof)
- Certainty propagation (condition_weights + confidence -> bottleneck vs additive)
- ProbLog proof tree (`proof_goal` / `proof_leaf` + probability pipeline)
- PyReason timeline (`chains` + `events` + bounds + timeline NL)
- Cross-engine comparison inside one shared session
- Full explain pipeline for each engine: raw carrier -> summary -> narrative -> NL

ProbLog and PyReason sections use mocked runners; the framework pipeline is real.

## Prerequisites

- Notebooks 01-02 and 10 require only `kernel` (no external engines).
- Notebook 03 requires monorepo delivery helpers outside the v0.1 kernel-only wheel.
- Notebook 04 (Souffle): requires `domains.ecss`, `service.static_ui`, and `souffle` CLI on PATH.
- Notebook 05 (PyReason): requires `pyreason==3.0.0` on Python 3.10. Graceful fallback if not installed.
- Notebook 06 (ProbLog): requires `problog` CLI. Graceful fallback if not installed.
- Notebook 07: uses mocked ProbLog / PyReason runners but depends on monorepo runtime helpers.
- Notebook 08 (Agent layer): requires `OPENAI_API_KEY` and the private monorepo agent/extraction stack.
- Notebook 09 and `dora_pdf_extract.py`: require the private agent/document extraction stack plus the configured document parser and LLM provider keys.

## Conventions

- Public kernel implementation truth lives in `src/kernel/**/docs/`.
- `agent`, `service`, and `domains` examples are private monorepo companions unless a future release-surface blueprint explicitly adds them.
- Notebooks are the canonical examples; no `.py` file pairs are maintained except dedicated CLI scripts.
- `archive/` contains historical spike/reference files.

## Archive

`archive/` contains files preserved for historical reference:

- `pyreason_spike.py` — standalone PyReason provenance event log exploration
- `souffle_provenance_v0_demo.py` — minimal Souffle proof JSON parsing
- `pyreason_integration_demo.py` — adapter-local PyReason E2E (superseded by 05)
