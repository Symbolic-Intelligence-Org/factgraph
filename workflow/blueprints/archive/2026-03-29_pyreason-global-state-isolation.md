# Task Blueprint: PyReason Global State Isolation & Exception Cleanup

- Status: implemented
- Created: 2026-03-29
- Last Updated: 2026-03-29
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/runner.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [adapters/docs/03_pyreason_adapter.md](../../src/factpy_kernel/adapters/docs/03_pyreason_adapter.md)
- Audit Log:
  - [2026-03-29_pyreason-global-state-isolation.audit.md](./2026-03-29_pyreason-global-state-isolation.audit.md)

## 1. Problem

`run_pyreason()` mutates PyReason's process-global singleton (`pr.reset()` → `pr.load_graph()` → `pr.reason()` → `pr.reset()`) without any concurrency protection. Additionally, if any call between the first and final `pr.reset()` throws an exception, the cleanup reset never executes, leaving global state dirty for subsequent calls.

Identified as F-PR-1 (severity: HIGH) in the 2026-03-29 walkthrough audit.

## 2. Goals

- Serialize concurrent `run_pyreason()` calls via `threading.Lock`
- Guarantee `pr.reset()` cleanup via `try/finally` even on exception
- Add targeted tests verifying lock acquisition and exception-safe cleanup

## 3. Non-goals

- No API signature changes to `run_pyreason()` or `pyreason_engine_eval()`
- No subprocess isolation (would be a separate, larger effort)
- No changes to ProbLog or Souffle adapters
- No changes to `engine_eval.py` or `__init__.py`

## 4. Current Context

- 当前实现入口：`run_pyreason()` at `runner.py:353-426`
- 当前已知约束：PyReason `import pyreason as pr` is a lazy import inside function body (line 363); PyReason library maintains process-global state
- 当前相关历史蓝图：无（this is a new fix identified in the walkthrough audit）
- 参考模式：`service/runtime_v1.py` uses `threading.RLock` for session management; `store/ledger.py` uses `@contextmanager` transaction pattern

## 5. Proposed Shape

Add a module-level `_PYREASON_LOCK = threading.Lock()` in `runner.py`. Wrap the global state mutation section (lines 397-417) in `with _PYREASON_LOCK:` + `try/finally`:

- `build_pyreason_graph()` stays outside lock (pure NetworkX)
- First `pr.reset()` inside lock, before `try` (if it throws, no work done)
- All `pr.*` calls + `_extract_derived_facts()` inside `try` block
- Final `pr.reset()` in `finally` block
- `return PyReasonRunResult(...)` outside lock (local variables only)

## 6. Boundaries And Invariants

- 必须保持的边界：`run_pyreason()` public signature unchanged; 62 frozen contracts unaffected
- 明确不做的内容：不做 subprocess isolation、不改 engine_eval.py、不改其他 adapters
- 兼容性约束：Lock is non-reentrant (`threading.Lock`, not `RLock`); reentrance would indicate a bug

## 7. Acceptance

- [x] `run_pyreason()` acquires `_PYREASON_LOCK` for all `pr.*` global state mutations
- [x] `pr.reset()` guaranteed to run via `finally` even on exception
- [x] 4 new tests: lock type, lock held during reason, reset on exception, lock released after exception
- [x] 没有越过 blueprint 明示的边界
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. [`runner.py`] Add `import threading` and `_PYREASON_LOCK = threading.Lock()`. Restructure lines 396-417 into `with _PYREASON_LOCK:` + `try/finally`.
2. [`test_pyreason_runner.py`] Add `LockAndCleanupTests` class with 4 test methods using `unittest.mock` to mock PyReason.
3. [`03_pyreason_adapter.md`] Add §5B.3 thread safety documentation. Update F-PR-1 in §8 as resolved.

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md`

## 10. Outcome / Deviations

- 最终落地结果：
  - `runner.py` 新增 `_PYREASON_LOCK = threading.Lock()` 模块级锁
  - `run_pyreason()` 的 `pr.*` 全局状态操作段改为 `with _PYREASON_LOCK:` + `try/finally`
  - `build_pyreason_graph()` 保持在锁外（纯 NetworkX）
  - 4 个新测试覆盖：锁类型、执行期锁持有、异常后 reset、异常后锁释放
  - 584 tests green（580 existing + 4 new）
  - `03_pyreason_adapter.md` 新增 §5B.3 thread safety 文档，F-PR-1 标记为 RESOLVED
- 与 blueprint 不同的地方：无偏离
- 归档说明：等待 commit 后归档
