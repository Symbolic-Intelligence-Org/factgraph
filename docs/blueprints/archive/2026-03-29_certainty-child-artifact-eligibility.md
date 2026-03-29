# Task Blueprint: Certainty Child Artifact Eligibility Guard

- Status: implemented
- Created: 2026-03-29
- Last Updated: 2026-03-29
- Related Modules:
  - `src/factpy_kernel/core/store/_confidence_kind_resolver.py`
- Related Docs:
  - [core/docs/01_architecture.md](../../src/factpy_kernel/core/docs/01_architecture.md)
- Audit Log:
  - [2026-03-29_certainty-child-artifact-eligibility.audit.md](./2026-03-29_certainty-child-artifact-eligibility.audit.md)

## 1. Problem

`check_certainty_artifact_eligibility()` 在 `child_artifact_lookup()` 返回 `None` 时仍返回 eligible edge。原因是 line 49 的 `child is not None and len(child.rule_ref_edges) > 0` 短路求值：`child is None` 时整个条件为 `False`，不触发 reject，函数直接 `return edge`。

缺失 child artifact 被当作 leaf child（无 further rule_ref_edges）处理，在 sidecar 未就绪或延迟加载场景下会错误标记 `confidence_kind="certainty"`。

Identified as F-CORE-3 (severity: MEDIUM) in the 2026-03-29 walkthrough audit.

## 2. Goals

- `child_support_digest is not None` 且 lookup 返回 `None` 时，eligibility 明确返回 `None`（ineligible）
- 现有 leaf child / non-leaf child 路径行为保持不变
- 拆分 compound condition 为两个独立 guard

## 3. Non-goals

- 不改 caller 协议（`CertaintyConfidenceKindResolver.resolve()` 和 `_certainty_service._lookup_condition_weights_for_candidate()`）
- 不做 F-CORE-4 的诊断增强
- 不改 certainty materializer

## 4. Current Context

- 入口：`_confidence_kind_resolver.py:48-50`
- compound condition `child is not None and ...` 在 child=None 时短路
- callers：`_confidence_kind_resolver.py:69` 和 `_certainty_service.py:36-39`

## 5. Proposed Shape

拆 line 49 为两个独立 guard：先检 `child is None → return None`，再检 `len(child.rule_ref_edges) > 0 → return None`。

## 6. Boundaries And Invariants

- 不改 caller 接口
- 不改 `RuleRefEdge` 或 `SupportArtifact` 类型
- 不扩到 sidecar 预加载机制

## 7. Acceptance

- [x] `child_support_digest is not None` + lookup returns `None` → returns `None`
- [x] `child_support_digest is not None` + child is leaf → returns edge
- [x] `child_support_digest is not None` + child has rule_ref_edges → returns `None`
- [x] 3 个新直接测试覆盖
- [x] 没有越过 blueprint 明示的边界
- [x] `01_architecture.md` F-CORE-3 marked RESOLVED

## 8. Implementation Plan

1. [`_confidence_kind_resolver.py`] 拆 compound condition 为两个 guard（hook-restricted）
2. [`test_certainty_explain_contracts.py`] 新增 3 个 `check_certainty_artifact_eligibility` 直接测试
3. [`01_architecture.md`] F-CORE-3 标为 RESOLVED

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`（resolve F-CORE-3）

## 10. Outcome / Deviations

- 最终落地结果：
  - `_confidence_kind_resolver.py` 将 compound condition 拆为两个独立 guard
  - `child_artifact_lookup()` 返回 `None` 时，`check_certainty_artifact_eligibility()` 明确返回 `None`
  - 现有 leaf child / non-leaf child 行为保持不变
  - `test_certainty_explain_contracts.py` 新增 3 个直接测试：missing child / leaf child / non-leaf child
  - `01_architecture.md` 已将 F-CORE-3 标记为 RESOLVED
  - 593 tests green（590 baseline + 3 new）
- 与 blueprint 不同的地方：无偏离
- 归档说明：实现提交后归档
