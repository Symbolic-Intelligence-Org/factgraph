# Task Blueprint Audit: PyReason Global State Isolation & Exception Cleanup

- Blueprint: [2026-03-29_pyreason-global-state-isolation.md](./2026-03-29_pyreason-global-state-isolation.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-29 | draft | Blueprint created | F-PR-1 fix scope recorded. |
| 2026-03-29 | scoped | Scope frozen | Lock + try/finally in runner.py only; no API changes. |
| 2026-03-29 | implementing | runner.py changes applied | User applied 3 code changes: import threading, _PYREASON_LOCK, with+try/finally. |
| 2026-03-29 | implementing | Tests added | 4 new tests in test_pyreason_runner.py: lock type, lock held, reset on exception, lock released. |
| 2026-03-29 | implementing | Docs synced | 03_pyreason_adapter.md: added §5B.3, resolved F-PR-1 in §8. |
| 2026-03-29 | implemented | Regression passed | 584 tests, 0 failures. |

## Decision Notes

- Use `threading.Lock` (not `RLock`) — reentrance would indicate a bug.
- Lock scope: from first `pr.reset()` through final `pr.reset()` in `finally`. `build_pyreason_graph()` stays outside lock.
- First `pr.reset()` before `try` block — if it throws, `finally` should not retry reset.
