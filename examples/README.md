# Examples Index

Current public notebook set for the SDK, explain, and agent surfaces.
Historical numbering is preserved; there is no standalone public `03` notebook in the current set.
Its certainty / evidence-tree deep-dive content is now folded into notebooks `04` and `07`.
Notebook `08` was added later as the agent-layer flagship and is the only notebook that performs real LLM calls.

## Learning Path

| # | Notebook | Adapter | Domain | Covers |
|---|----------|---------|--------|--------|
| 01 | `01_sdk_basics.ipynb` | — | general | Entity / Schema / Store / CRUD / Batch / Edit / Ingest |
| 02 | `02_rules_and_derivations.ipynb` | — (native) | general | Rule DSL / Query / Derivation / Accept / Registry |
| 04 | `04_ecss_souffle_compliance.ipynb` | **Souffle** | **ECSS** | compliance rules / certainty / audit package / static site / proof tree |
| 05 | `05_dora_pyreason_propagation.ipynb` | **PyReason** | **DORA** | boolean propagation / temporal reasoning / adapter-local session |
| 06 | `06_problog_probabilistic.ipynb` | **ProbLog** | general | probabilistic reasoning / ProbLogRuleExt / persist annotations |
| 07 | `07_evidence_graph_multi_engine.ipynb` | **all three** | general | **evidence tree + certainty + probability + timeline + cross-engine comparison** |
| 08 | `08_agent_document_workflow.ipynb` | **real OpenAI LLM** | agent | **Agent layer end-to-end: 4C1 staging / 4C3a–c extraction + resolve / 4C2 bundle review + commit / real SQLite ledger** |
| 09 | `09_dora_document_extraction.ipynb` | **real Mistral / OpenAI LLM** | **DORA** | `extract_document()` product API: schema compile → staging → batch extraction + gleaning → alias merge, one function call end-to-end |

Companion CLI script (no notebook runtime):

- `dora_pdf_extract.py` — run `extract_document()` against a real regulatory PDF from the command line; writes a JSON result file next to the input
- `dora_schema_ir.json` — pre-compiled schema IR that notebook 09 and the CLI script share

## Notebook 07 — Flagship Demo

Notebook 07 is the comprehensive three-engine demo. It covers:
- Evidence tree node hierarchy (candidate_result → support → witness / proof)
- Certainty propagation (condition_weights + confidence → bottleneck vs additive)
- ProbLog proof tree (`proof_goal` / `proof_leaf` + probability pipeline)
- PyReason timeline (`chains` + `events` + bounds + timeline NL)
- Cross-engine comparison inside one shared session
- Full explain pipeline for each engine: raw carrier → summary → narrative → NL

ProbLog and PyReason sections use mocked runners; the entire framework pipeline is real.

## Prerequisites

- Notebooks 01–02 require only `factpy_kernel` (no external engines).
- Notebook 04 (Souffle): requires `souffle` CLI on PATH.
- Notebook 05 (PyReason): requires `pyreason==3.0.0` on Python 3.10. Graceful fallback if not installed.
- Notebook 06 (ProbLog): requires `problog` CLI. Graceful fallback if not installed.
- Notebook 07: uses mocked ProbLog / PyReason runners and therefore runs without external engine installs.
- Notebook 08 (Agent layer): requires `OPENAI_API_KEY` environment variable and a Jupyter kernel that has `factpy_kernel` installed with its extraction extras. The cleanest way to set that up is to activate the kernel's Python environment and run, from the repo root:

      pip install -e '.[extraction]'

  This pulls in both the core dependencies (`pydantic>=2`, `diskcache>=5`) and the LLM extras (`instructor>=1.6`, `litellm>=1.50`). Unlike notebooks 06 / 07, this notebook performs real LLM calls at `temperature=0.0`. Re-runs will produce slightly different extraction counts per OBS-01 variance (B3 iter 4 addendum); `committed_count > 0` is the stable guarantee. The notebook fails loudly at pre-flight (cell §0) if any required package is missing or `OPENAI_API_KEY` is unset — restart the kernel after installing.

## Conventions

- Implementation truth lives in `src/factpy_kernel/*/docs/`, not here.
- Notebooks are the canonical examples — no `.py` file pairs.
- `archive/` contains historical spike/reference files (not user-facing).

## Archive

`archive/` contains files preserved for historical reference:
- `pyreason_spike.py` — standalone PyReason provenance event log exploration
- `souffle_provenance_v0_demo.py` — minimal Souffle proof JSON parsing
- `pyreason_integration_demo.py` — adapter-local PyReason E2E (superseded by 05)
