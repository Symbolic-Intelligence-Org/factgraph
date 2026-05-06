# Examples

The current v0.1 demo journey is shipped as one canonical executable script
plus a chaptered Jupyter notebook suite that imports from it. The script is
the behavioral source of truth (the unittest in
`src/kernel/tests/test_examples_round_story_full_demo.py` asserts on it);
the notebooks are the readable walkthrough.

## Canonical script

```bash
python examples/round_story_full_demo.py
```

`round_story_full_demo.py` runs every phase end-to-end with a deterministic
fixture and asserts on the aggregate `EXPECTED_PHASE_SUMMARY` contract. Use
it for smoke verification or as the single source to read when you want the
full story in one place.

## Chaptered notebook suite

Each chapter imports `round_story_full_demo` and walks one section of the
script with prose explanations. Read them in order — later chapters reuse
fixtures and results from earlier ones.

| # | Notebook | Topic |
|---|----------|-------|
| 1 | [`01_sdk_check_diagnose.ipynb`](01_sdk_check_diagnose.ipynb) | SDK schema authoring, Q1 Check, Q2 Diagnose |
| 2 | [`02_overlay_why_not_frontier.ipynb`](02_overlay_why_not_frontier.ipynb) | Q3 Fact Overlay, Q4 Why-not Universe, Q5 Frontier Trace |
| 3 | [`03_proofframe_rule_overlays.ipynb`](03_proofframe_rule_overlays.ipynb) | Batch 4 ProofFrame Rechecker + Batch 5a/b/c rule overlays |
| 4 | [`04_round_persistence_diff.ipynb`](04_round_persistence_diff.ipynb) | Batch 6 round events + Batch 7 ProofFrame diff |

Each notebook ends with an aggregate-status assertion that matches the
smoke-test contract, so any drift in the underlying capabilities surfaces
the same way in the notebook and in CI.

## Public-surface boundary (Batch 8)

The demos exercise the v0.1 public-surface decision verbatim:

- `kernel.sdk` is the product surface (schema authoring + ledger).
- `kernel.application.*` and `kernel.audit.*` are advanced-importable
  Python APIs — every Q1–Q5 capability, the ProofFrame rechecker, the three
  rule overlays, the round recorder, and the ProofFrame diff are imported
  directly from these packages.
- v0.1 ships **no** SDK shells or service routes for Batch 3–7. The script
  and notebooks deliberately demonstrate the advanced-importable path;
  there is no "wrapped" surface to wait for.

## Historical examples

`examples/archive/` retains earlier sectional notebooks and scripts (the
pre-routemap onboarding journey, the original capabilities demo, the
all-in-one round-story wrapper, and earlier evidence-pipeline material).
They are kept for reference when reading older blueprints, but they are not
the recommended current journey.
