# Examples Index

These examples exercise the v0.1 `factpy-kernel` package surface. Default-wheel notebooks and scripts run on a stock `pip install factpy-kernel` install. Notebooks 05 and 06 additionally use optional local engines; both have graceful fallback if the engine is not installed.

## Default-Wheel Kernel Examples

These notebooks use only the default `kernel` package surface.

| # | Notebook | Adapter | Domain | Covers |
|---|----------|---------|--------|--------|
| 01 | `01_sdk_basics.ipynb` | — | general | Entity / Schema / Store / CRUD / Batch / Edit / Ingest |
| 02 | `02_rules_and_derivations.ipynb` | — (native) | general | Rule DSL / Query / Derivation / Accept / Registry |
| 10 | `10_v01_onboarding_journey.ipynb` | — (native) | general | end-to-end v0.1 journey: ref -> set/add -> get -> query -> derive/accept -> export/read audit package + evidence tree |

## Default-Wheel Kernel Scripts

These scripts are deterministic and assertion-bearing, so they can double as
smoke checks while staying readable as examples.

| # | Script | Adapter | Domain | Covers |
|---|--------|---------|--------|--------|
| 11 | `11_capabilities_e2e_demo.ipynb` (+ `.py` smoke target) | — (native) | general | Check / Diagnose / Fact Overlay Check / Why-not Universe Diagnose / Evaluator Frontier Trace on one Person fixture |

## Kernel Optional-Engine Examples

These notebooks stay under the `kernel.*` namespace but require optional local engines.

| # | Notebook | Adapter | Domain | Covers |
|---|----------|---------|--------|--------|
| 05 | `05_dora_pyreason_propagation.ipynb` | **PyReason** | **DORA** | boolean propagation / temporal reasoning / adapter-local session |
| 06 | `06_problog_probabilistic.ipynb` | **ProbLog** | general | probabilistic reasoning / ProbLogRuleExt / persist annotations |

## Prerequisites

- Notebooks 01, 02, and 10, plus script 11, require only `kernel` (no external engines).
- Notebook 05 (PyReason): requires `pyreason==3.0.0` on Python 3.10. Graceful fallback if not installed.
- Notebook 06 (ProbLog): requires `problog` CLI. Graceful fallback if not installed.

## Conventions

- Public kernel implementation truth lives in `src/kernel/**/docs/`.
- Notebooks are the canonical narrative examples. Dedicated `.py` scripts are used only
  for assertion-bearing demos or CLI-style examples.
