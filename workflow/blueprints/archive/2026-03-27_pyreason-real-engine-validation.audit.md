# Task Blueprint Audit: PyReason Real-Engine Validation

- Blueprint: [2026-03-27_pyreason-real-engine-validation.md](./2026-03-27_pyreason-real-engine-validation.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-27 | draft | Blueprint created | L1 child blueprint opened under `multi-engine-semantic-delivery`. Initial blocker is local `pyreason` import failure caused by `numba` cache runtime error. |
| 2026-03-27 | draft | Current environment reproduced | Local package set is `pyreason==3.0.0`, `numba==0.64.0`, `llvmlite==0.46.0`. Plain `import pyreason` fails with `RuntimeError: cannot cache function 'Interpretation._init_reverse_neighbors' ... no locator available ...`. |
| 2026-03-27 | draft | Diagnostic monkeypatch narrowed the blocker | Monkeypatching `numba.njit` to strip `cache=True` allows `import pyreason` and lets `SDKStore.evaluate(Derivation(mode=\"pyreason\"))` reach `run_pyreason()`. The real call then spends more than `60s` in `pyreason.reason()` / `numba` / `llvmlite` compilation, so the operator path is still unvalidated. |
| 2026-03-27 | scoped | Fallback rejected; environment gate made explicit | `NUMBA_DISABLE_JIT=1` is not viable: `import pyreason` then fails with `TypeError: Interval.__new__() takes from 3 to 4 positional arguments but 6 were given`. Current preferred unblock is an external validated environment, not a repository-side shim. |
| 2026-03-27 | implemented | **ROOT CAUSE FOUND + GATE PASSED** | 144 stale `.nbi`/`.nbc` cache files in `pyreason/cache/` from a previous numba version. `rm -rf pyreason/cache/` resolved import. Full real-engine chain ran: evaluate (166.6s first JIT) → 2 CandidateSet → accept (1 assertion) → persist (6 annotations). No code changes. Same package set (`pyreason==3.0.0` / `numba==0.64.0` / `llvmlite==0.46.0`). |

## Decision Notes

- Root cause was stale numba cache, not version incompatibility.
- Same package set works after cache clear.
- 166.6s first-run time is numba JIT compilation; subsequent runs use fresh cache.
- No repository-side workaround needed.
