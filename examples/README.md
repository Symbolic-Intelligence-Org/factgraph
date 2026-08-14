# Examples

The current v0.1 demo journey ships as a chaptered notebook suite plus a
single canonical executable script:

- The **notebooks** are the readable, self-contained walkthrough — each one
  imports the real `kernel.application` / `kernel.audit` / `kernel.sdk`
  APIs directly, builds its own fixture inline, and asserts on the result
  of every capability call. There is no demo helper module to import; what
  you read is what you would write.
- The **script** is the integrated end-to-end smoke target. The unittest in
  `src/kernel/tests/test_examples_round_story_full_demo.py` asserts on its
  `EXPECTED_PHASE_SUMMARY` contract.

## Chaptered notebook suite

Read them in order — later chapters build on the capabilities introduced in
earlier ones, but each notebook stands on its own (no cross-notebook state).

| # | Notebook | Topic |
|---|----------|-------|
| 1 | [`01_sdk_check_diagnose.ipynb`](01_sdk_check_diagnose.ipynb) | SDK schema authoring, Q1 Check, Q2 Diagnose |
| 2 | [`02_overlay_why_not_frontier.ipynb`](02_overlay_why_not_frontier.ipynb) | Q3 Fact Overlay, Q4 Why-not Universe, Q5 Frontier Trace |
| 3 | [`03_proofframe_rule_overlays.ipynb`](03_proofframe_rule_overlays.ipynb) | Batch 4 ProofFrame Rechecker + Batch 5a/b/c rule overlays |
| 4 | [`04_round_persistence_diff.ipynb`](04_round_persistence_diff.ipynb) | Batch 6 round events + Batch 7 ProofFrame diff |
| 5 | [`05_sdk_assertion_views.ipynb`](05_sdk_assertion_views.ipynb) | SDK assertion records, frozen assertion views, by-id readback, and precise retract |

Every code cell asserts on the structured result it produced, so any drift
in the underlying capabilities surfaces the next time the notebook is run.

## V1 Query / Scenario walkthrough

[`07_v1_query_scenario_closure.ipynb`](07_v1_query_scenario_closure.ipynb)
is a self-contained FactGraph V1 tutorial. It demonstrates the common
`fg.query(...).bind(...).select(...).plan().run()` path for Rule and Policy
targets, Scenario effective worlds, explicit detached Explain/replay,
expectations, providers, candidate comparison, and the
`portable_deterministic_v1` Native/Soufflé/ProbLog profile.

The portable cells make a deliberately narrow claim: canonical selected-row
set parity for the supported positive deterministic fragment. They do not
claim cross-engine proof, provenance, certainty, or arbitrary-language
equivalence. The final cross-entity field-navigation/comparison example is
included specifically to exercise two occurrences of the same predicate.

## Canonical script

```bash
python examples/round_story_full_demo.py
```

`round_story_full_demo.py` runs every phase end-to-end against the same
fixture shape as the notebooks and asserts on the aggregate
`EXPECTED_PHASE_SUMMARY`. Use it for smoke verification, or as the single
source to read when you want the full story in one place.

## Public-surface boundary

The demos exercise the v0.1 public-surface decision and the later SDK shell
facades:

- `kernel.sdk` is the product surface (schema authoring + ledger).
- `FactGraph` / `SDKStore` expose narrow SDK shells for Check, Diagnose,
  Fact Overlay, Why-not, ProofFrame Recheck, the three rule overlays, and
  ProofFrame Diff.
- `kernel.application.*` and `kernel.audit.*` remain advanced-importable
  Python APIs. The notebooks may import them directly when they demonstrate
  lower-level audit or round-persistence machinery, but new product examples
  should prefer the `FactGraph` namespace when an SDK shell exists.
- Runtime service routes remain narrower than the Python SDK. Do not infer an
  HTTP route from an SDK shell unless `src/service/docs/` documents it.

## Historical examples

`examples/archive/` retains earlier sectional notebooks and scripts (the
pre-routemap onboarding journey, the original capabilities demo, the
all-in-one round-story wrapper, and earlier evidence-pipeline material).
They are kept for reference when reading older blueprints, but they are not
the recommended current journey.
