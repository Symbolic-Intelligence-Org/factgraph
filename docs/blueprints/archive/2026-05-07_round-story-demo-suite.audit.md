# Task Blueprint Audit: Round Story Demo Suite

- Blueprint: [2026-05-07_round-story-demo-suite.md](./2026-05-07_round-story-demo-suite.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-07 | scoped | Blueprint created | User identified that the all-in-one notebook loses the thematic chapter structure that made the archived examples useful. |
| 2026-05-07 | implementing | First-pass shell notebooks landed | Four chapter notebooks shipped as wrappers over `round_story_full_demo._phase_*` helpers (commits `bfe26ef`, `eb4428b`, `94453e0`, `9d7e8c4`, `dae6b6d`). Followed §5 literally. |
| 2026-05-07 | implementing | User reviewed and rejected the shell-style notebooks | Notebook cells called `demo._phase_xxx(...)` instead of the real `kernel.application` / `kernel.audit` APIs. Reading them taught no API usage to the external-integrator audience the demos are for. |
| 2026-05-07 | implementing | Tear-down + inline rewrite | Commit `cba3176` removed all four shell notebooks and the four chapter helpers. Commits `ab85084`, `020f2c0`, `a01c248`, `624ce16` shipped self-contained inline notebooks in the `archive/11_capabilities_e2e_demo.ipynb` style. |
| 2026-05-07 | implemented | Final state | Four self-contained notebooks + retained smoke script + updated README + this blueprint outcome. Unittest, smoke script, and `git diff --check` all green. |

## Decision Notes

### 2026-05-07 — Script vs Notebook Roles (initial scoping)

`round_story_full_demo.py` remains the deterministic smoke harness and source of
truth. Root notebooks become focused presentation chapters that import the
script and run chapter-specific functions.

### 2026-05-07 — Notebook Style Reversal (post-implementation review)

The "import the script" clause from §5 was walked back after a review pass.
Notebooks must directly demonstrate the real API surface — the wrapper layer
defeated the purpose. Reformulated rule: the script is the smoke target,
the notebooks are the API demonstration; both stand independently and the
unittest covers only the script side. The four notebooks now duplicate
~80 lines of fixture setup each, and that is the right tradeoff for the
external-integrator audience.
