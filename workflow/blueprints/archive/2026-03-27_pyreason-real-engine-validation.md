# Task Blueprint: PyReason Real-Engine Validation

- Status: implemented
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Parent Blueprint:
  - [2026-03-27_multi-engine-semantic-delivery.md](./2026-03-27_multi-engine-semantic-delivery.md) (L1)
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/sdk/store.py`
  - `examples/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [src/factpy_kernel/adapters/docs/03_pyreason_adapter.md](../../../src/factpy_kernel/adapters/docs/03_pyreason_adapter.md)
- Audit Log:
  - [2026-03-27_pyreason-real-engine-validation.audit.md](./2026-03-27_pyreason-real-engine-validation.audit.md)

## 1. Problem

PyReason execution surface is only validated through mocked runner tests. The mother blueprint's Gate 1 requires a real-engine run, but the current local environment has not produced a stable operator path:

- plain `import pyreason` fails with a `numba` cache runtime error
- a diagnostic monkeypatch that strips `cache=True` allows import, but the real execution-surface call then stalls inside `pyreason -> numba -> llvmlite` compilation
- `NUMBA_DISABLE_JIT=1` is not a viable fallback because `pyreason` then fails import with an interval type error

## 2. Goals

- Reproduce and document the current real-engine blocker precisely.
- Determine whether the blocker can be resolved without changing repository code.
- Run at least one real `mode="pyreason"` evaluation path end-to-end if the environment can be unblocked safely.
- Record the validated path, remaining environment prerequisites, and any repo/docs changes required.

## 3. Non-goals

- No expansion of PyReason rule semantics.
- No new engine surface design work beyond what is needed to validate execution.
- No ProbLog work.
- No UI/audit consumer work.

## 4. Current Context

- Mocked execution-surface coverage is green (`467` tests at session start).
- Mother blueprint Gate 1 requires real import + evaluate + accept + annotation persist.
- Current local package set on 2026-03-27:
  - `pyreason==3.0.0`
  - `numba==0.64.0`
  - `llvmlite==0.46.0`
- Current local failure reproduced on 2026-03-27:
  - plain import:
    - `RuntimeError: cannot cache function 'Interpretation._init_reverse_neighbors': no locator available for file '/Users/zhenzhili/miniforge3/lib/python3.10/site-packages/pyreason/scripts/interpretation/interpretation.py'`
  - diagnostic import workaround:
    - monkeypatching `numba.njit` to drop `cache=True` allows `import pyreason`
    - the real `SDKStore.evaluate(Derivation(mode="pyreason"))` path reaches `run_pyreason()` and then spends more than `60s` inside `pyreason.reason()` / `numba` / `llvmlite` compilation
  - rejected fallback:
    - `NUMBA_DISABLE_JIT=1` changes the failure into `TypeError: Interval.__new__() takes from 3 to 4 positional arguments but 6 were given`
- Workspace currently has unrelated user changes in:
  - `examples/dora_compliance_demo.ipynb`
  - `.claude/launch.json`

## 5. Proposed Shape

- First treat this as an environment-validation task, not a code feature task.
- Establish whether the fix belongs to:
  - runtime environment procedure,
  - local dependency patch,
  - or repository-side compatibility shim.
- Current provisional conclusion:
  - repo-side compatibility glue is not justified yet
  - the next unblock should be an external validated PyReason environment with a known-good `numba` / `llvmlite` pair
- Only after a validated environment exists should we re-run the minimal real-engine derivation on the existing execution surface.

## 6. Boundaries And Invariants

- Do not mutate unrelated workspace files.
- Do not broaden scope into semantic-delivery consumer work.
- Prefer environment/procedure fixes over repository code changes when the root cause is external.
- Any repo-side workaround must be documented as compatibility glue, not re-framed as engine semantics.
- Do not turn a diagnostic monkeypatch into a productized path unless no external environment fix is available.

## 7. Acceptance

- [ ] Real `import pyreason` outcome is documented and reproducible.
- [ ] A chosen unblock path is justified (or the task is explicitly blocked on environment constraints).
- [ ] If unblocked, at least one real `mode="pyreason"` evaluate → accept → persist path is executed.
- [ ] Adapter docs are updated if operator prerequisites or caveats changed.

## 8. Implementation Plan

1. Reproduce the import/runtime failure and inspect the exact `numba`/package interaction.
2. Evaluate unblock options in order of least invasiveness: env flag/procedure, local patch, repo workaround.
3. Use a diagnostic-only monkeypatch to determine whether the shared execution surface reaches the real engine and where it blocks.
4. If a validated environment becomes available, run a minimal real-engine execution-surface scenario and record the result.

## 9. Docs To Update

- `src/factpy_kernel/adapters/docs/03_pyreason_adapter.md` if environment prerequisites or caveats change
- L1 blueprint audit log

## 10. Outcome / Deviations

**GATE 1: PASSED** (2026-03-27)

**Root cause**: 144 stale numba cache files (`.nbi`/`.nbc`) in `pyreason/cache/` directory, left over from a previous numba version. These caused `RuntimeError: cannot cache function ... no locator available`.

**Fix**: `rm -rf /path/to/site-packages/pyreason/cache/` — no code changes required.

**Real-engine validation result** (same `pyreason==3.0.0` / `numba==0.64.0` / `llvmlite==0.46.0`):

| Step | Result | Time |
|------|--------|------|
| `import pyreason` | ✓ | 2.8s |
| `Store.evaluate(mode="pyreason")` | ✓ 2 CandidateSet | 166.6s (first JIT) |
| `Store.accept()` | ✓ 1 written assertion | <1s |
| `persist_pyreason_annotations()` | ✓ 6 annotations | <1s |
| Persisted annotation keys | `['active_from', 'bound_lower', 'bound_upper']` | — |

**Notes**:
- 166.6s is first-run JIT compilation overhead; subsequent runs use cache and are fast
- 2 candidates produced (one per seeded user entity)
- Confidence = 1.0 (EDB default bound per D9)
- The `Ledger.__del__` TypeError on exit is a known benign teardown race, not a functional issue

**No deviations from blueprint scope.**
