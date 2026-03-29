# Task Blueprint: Core + Audit Batch Fix

- Status: implemented
- Created: 2026-03-29
- Last Updated: 2026-03-29
- Related Modules:
  - `src/factpy_kernel/core/store/_certainty_materializer.py`
  - `src/factpy_kernel/core/store/_confidence_kind_resolver.py`
  - `src/factpy_kernel/audit/evidence_graph.py`
  - `src/factpy_kernel/audit/reader.py`
  - `src/factpy_kernel/audit/static_ui.py`
- Audit Log:
  - [2026-03-29_core-audit-batch.audit.md](./2026-03-29_core-audit-batch.audit.md)

## 1. Problem

Walkthrough 遗留 5 条 finding（均低严重级别），横跨 core certainty 路径和 audit evidence graph：

- F-CORE-4：certainty 物化与 resolver 的 9 条 return None/"none" 路径无诊断注释
- F-CORE-5：`probability=0.0` 被拒绝是刻意设计但未在文档说明
- F-EG-1：evidence graph 构造时无环检测
- F-EG-3：`evidence_graphs.jsonl` 重复 candidate_id 静默覆盖
- F-EG-4：`_try_build_evidence_graph_from_provenance` 裸 Exception 捕获

## 2. Goals

- F-CORE-4：给所有 return None/"none" 路径加 inline 注释
- F-CORE-5：在文档中记录 `(0,1]` 是刻意设计
- F-EG-1：`__post_init__` 加 DFS 环检测
- F-EG-3：重复 candidate_id raise AuditReadError
- F-EG-4：收窄 except 为 `(ValueError, KeyError, TypeError)`

## 3. Non-goals

- 不做 F-EG-2（timeline edge 渲染，留下一轮）
- 不改 certainty materializer 或 resolver 的控制流
- 不改 probability 校验逻辑

## 4. Acceptance

- [x] F-CORE-4：9 条早返路径均有 inline 注释
- [x] F-CORE-5：01_architecture.md 补充设计说明
- [x] F-EG-1：有环 graph → ValueError
- [x] F-EG-3：重复 candidate_id → AuditReadError
- [x] F-EG-4：except 收窄
- [x] 3 个新测试
- [x] 全量回归绿（596 passed）

## 5. Implementation Plan

1. `_certainty_materializer.py` — 加注释
2. `_confidence_kind_resolver.py` — 加注释
3. `01_architecture.md` — F-CORE-4 标 RESOLVED + F-CORE-5 补设计说明标 RESOLVED
4. `evidence_graph.py` — 加环检测
5. `reader.py` — 加重复检测
6. `static_ui.py` — 收窄 except
7. `02_evidence_graph.md` — F-EG-1/3/4 标 RESOLVED
8. 补测试

## 6. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/audit/docs/02_evidence_graph.md`
