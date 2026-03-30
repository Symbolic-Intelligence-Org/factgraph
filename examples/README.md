# Examples Index

7 notebooks covering the full SDK capability set, ordered for progressive learning.

## Learning Path

| # | Notebook | Adapter | Domain | Covers |
|---|----------|---------|--------|--------|
| 01 | `01_sdk_basics.ipynb` | — | general | Entity/Schema/Store/CRUD/Batch/Edit/Ingest |
| 02 | `02_rules_and_derivations.ipynb` | — (native) | general | Rule DSL / Query / Derivation / Accept / Registry |
| 03 | `03_certainty_and_evidence_tree.ipynb` | — | general | condition_weights / confidence / evidence tree / explain |
| 04 | `04_ecss_souffle_compliance.ipynb` | **Souffle** | **ECSS** | compliance rules / proof tree / audit package / static site |
| 05 | `05_dora_pyreason_propagation.ipynb` | **PyReason** | **DORA** | boolean propagation / temporal reasoning / adapter-local session |
| 06 | `06_problog_probabilistic.ipynb` | **ProbLog** | general | probabilistic reasoning / ProbLogRuleExt / persist_annotations |
| 07 | `07_evidence_graph_multi_engine.ipynb` | multi | general | EvidenceGraph IR / tree + timeline layout / architecture |

## Prerequisites

- Notebooks 01–03 and 07 require only `factpy_kernel` (no external engines).
- Notebook 04 (Souffle): requires `souffle` CLI on PATH.
- Notebook 05 (PyReason): requires `pyreason==3.0.0` on Python 3.10. Graceful fallback if not installed.
- Notebook 06 (ProbLog): requires `problog` CLI. Graceful fallback if not installed.

## Conventions

- Implementation truth lives in `src/factpy_kernel/*/docs/`, not here.
- Notebooks are the canonical examples — no `.py` file pairs.
- `archive/` contains historical spike/reference files (not user-facing).

## Archive

`archive/` contains files preserved for historical reference:
- `pyreason_spike.py` — standalone PyReason provenance event log exploration
- `souffle_provenance_v0_demo.py` — minimal Souffle proof JSON parsing
- `pyreason_integration_demo.py` — adapter-local PyReason E2E (superseded by 05)
