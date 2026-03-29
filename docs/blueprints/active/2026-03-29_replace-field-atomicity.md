# Task Blueprint: replace_field Atomicity Fix

- Status: implemented
- Created: 2026-03-29
- Last Updated: 2026-03-29
- Related Modules:
  - `src/factpy_kernel/core/evidence/write_protocol.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [core/docs/01_architecture.md](../../src/factpy_kernel/core/docs/01_architecture.md)
- Audit Log:
  - [2026-03-29_replace-field-atomicity.audit.md](./2026-03-29_replace-field-atomicity.audit.md)

## 1. Problem

`replace_field()` 先调 `retract_by_asrt()` 再调 `set_field()`。一旦 `set_field()` 在 meta/annotation 校验阶段失败，旧断言已被 revoke 且 append-only ledger 不可回退，导致数据丢失。

Identified as F-CORE-1 (severity: MEDIUM) in the 2026-03-29 walkthrough audit.

## 2. Goals

- 确保 `set_field()` 的所有 validation 在 `retract_by_asrt()` 之前完成
- 校验失败时旧断言保持 active（不被 revoke）
- 成功替换时行为与现有 API 完全兼容

## 3. Non-goals

- 不改 `set_field()`、`retract_by_asrt()`、`add_field()` 的实现
- 不扩到 ledger 事务系统
- 不改 `probability=0.0` validation 规则（F-CORE-5 是独立 finding）
- 不改 public API signatures

## 4. Current Context

- 当前实现入口：`write_protocol.replace_field()` at line 210-227
- 当前已知约束：
  - `replace_field` 只做了 `_validate_write_inputs` 两次（lines 218-219），但 `set_field` 内部还有 `_normalize_meta`、`_compute_ingest_key`、`_meta_rows_for_claim`、`_annotation_rows_for_claim` 等验证步骤
  - `retract_by_asrt` 和 `set_field` 各在独立的 ledger transaction 中执行
- 当前相关历史蓝图：无

## 5. Proposed Shape

新增 `_preflight_new_assertion()` — 运行 `set_field()` 的所有 validation 步骤但不做任何 DB 写入。在 `replace_field()` 中，先调 preflight，再调 retract + set。

```python
def _preflight_new_assertion(ledger, pred_id, e_ref, rest_terms, meta):
    """Dry-run set_field validation. Raises before any DB writes."""
    _validate_write_inputs(ledger, pred_id, e_ref, rest_terms)
    meta_dict = _normalize_meta(meta)
    ingest_key = _compute_ingest_key(pred_id, e_ref, rest_terms, meta_dict)
    _meta_rows_for_claim("_preflight_", meta_dict, ingest_key, 0)
    _annotation_rows_for_claim("_preflight_", meta_dict)
```

Preflight 用 sentinel 值（`"_preflight_"` asrt_id, `0` ingested_at）构造临时行对象做校验，然后丢弃。`set_field()` 之后会用真实值重做（幂等校验）。

## 6. Boundaries And Invariants

- 必须保持的边界：`replace_field` public signature 不变；`set_field`/`retract_by_asrt` 实现不变
- 明确不做的内容：不改 ledger transaction 机制；不做补偿回退
- 兼容性约束：所有 62 frozen contracts + F-PR-1 lock contract 不受影响

## 7. Acceptance

- [x] `set_field()` 校验失败时，旧断言仍保持 active
- [x] 成功替换时行为与现有 API 保持兼容
- [x] 增加针对 invalid meta / invalid probability 的回归测试
- [x] 没有越过 blueprint 明示的边界
- [x] 受影响模块 docs 已同步（F-CORE-1 marked resolved）

## 8. Implementation Plan

1. [`write_protocol.py`] 新增 `_preflight_new_assertion()`，在 `replace_field()` 中 retract 之前调用
2. [`test_write_protocol_annotations.py`] 新增 3 个 atomicity 测试
3. [`01_architecture.md`] 将 F-CORE-1 标为 RESOLVED

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`（resolve F-CORE-1）

## 10. Outcome / Deviations

- 最终落地结果：
  - `write_protocol.py` 新增 `_preflight_new_assertion()` 预校验函数
  - `replace_field()` 在 `retract_by_asrt()` 之前调用 preflight，确保 meta/annotation 校验失败时旧断言不被 revoke
  - 3 个新测试覆盖：invalid confidence 保留旧断言、invalid probability 保留旧断言、valid replacement 回归
  - 587 tests green（584 existing + 3 new）
  - `01_architecture.md` F-CORE-1 标记为 RESOLVED
- 与 blueprint 不同的地方：无偏离
- 归档说明：等待 commit 后归档
