# Task Blueprint: Candidate Support Digest Collision Check

- Status: implemented
- Created: 2026-03-29
- Last Updated: 2026-03-29
- Related Modules:
  - `src/factpy_kernel/core/store/runtime.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [core/docs/01_architecture.md](../../src/factpy_kernel/core/docs/01_architecture.md)
- Audit Log:
  - [2026-03-29_candidate-support-digest-collision.audit.md](./2026-03-29_candidate-support-digest-collision.audit.md)

## 1. Problem

`Store._remember_candidate_support()` 对同一 `candidate_id` 的重注册静默忽略 `support_digest` 差异。与 `_remember_support_artifact()` 和 `_remember_provenance_envelope()` 的 collision raise 模式不一致，可能掩盖 re-evaluate 或跨引擎 candidate_id 碰撞 bug。

Identified as F-CORE-2 (severity: MEDIUM) in the 2026-03-29 walkthrough audit.

## 2. Goals

- 同一 `candidate_id` + 不同 `support_digest` 明确报 `ValueError`
- 同一 `candidate_id` + 相同 `support_digest` 保持幂等（不报错，保留首次 kind 值）
- 与 `_remember_support_artifact` / `_remember_provenance_envelope` 的 collision 模式对齐

## 3. Non-goals

- 不改 `_remember_support_artifact` 或 `_remember_provenance_envelope`
- 不改 `_evaluate.py` 中的 caller 逻辑
- 不改 public API signatures
- 不扩到 candidate deduplication 或清理机制

## 4. Current Context

- 当前实现入口：`runtime.py:159-181`
- 当前已知约束：re-registration path (lines 175-178) 用 `setdefault` 保留首次 kind 值但不校验 digest
- 参考模式：`_remember_support_artifact` (line 115) 和 `_remember_provenance_envelope` (line 148) 均在 collision 时 raise

## 5. Proposed Shape

在 line 175 的 `if candidate_id in self._candidate_support_index:` 块内，取出已有 digest 做比对。不等则 raise `ValueError`，等则继续 `setdefault` + return。

## 6. Boundaries And Invariants

- 必须保持的边界：public API 不变；caller 不需要改动
- 明确不做的内容：不做 candidate 级别的 upsert/replace 机制
- 兼容性约束：所有现有 callers 目前只注册一次，不会触发新 raise

## 7. Acceptance

- [x] 同一 `candidate_id` + 相同 `support_digest` 幂等
- [x] 同一 `candidate_id` + 不同 `support_digest` 明确 `ValueError`
- [x] 3 个新测试覆盖
- [x] 没有越过 blueprint 明示的边界
- [x] 受影响模块 docs 已同步（F-CORE-2 marked resolved）

## 8. Implementation Plan

1. [`runtime.py`] 在 `_remember_candidate_support` 的 re-registration path 加 digest 比对 + raise
2. [`test_evidence_tree_explain_contracts.py`] 新增 3 个 collision/idempotency 测试
3. [`01_architecture.md`] 将 F-CORE-2 标为 RESOLVED

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`（resolve F-CORE-2）

## 10. Outcome / Deviations

- 最终落地结果：
  - `runtime.py` 在 `_remember_candidate_support()` 的重注册分支新增 `support_digest` 比对
  - 相同 digest 保持幂等；不同 digest 明确抛 `ValueError`
  - `test_evidence_tree_explain_contracts.py` 新增 3 个覆盖 first registration / idempotent same digest / different digest raise 的测试
  - `01_architecture.md` 已将 F-CORE-2 标记为 RESOLVED
  - 590 tests green（587 baseline + 3 new）
- 与 blueprint 不同的地方：无偏离
- 归档说明：实现提交后归档
