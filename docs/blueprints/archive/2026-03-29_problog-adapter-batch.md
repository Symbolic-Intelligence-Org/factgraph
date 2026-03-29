# Task Blueprint: ProbLog Adapter Batch Fix

- Status: implemented
- Created: 2026-03-29
- Last Updated: 2026-03-29
- Related Modules:
  - `src/factpy_kernel/adapters/problog/engine_eval.py`
  - `src/factpy_kernel/adapters/problog/problog_import.py`
  - `src/factpy_kernel/adapters/problog/accept.py`
  - `src/factpy_kernel/adapters/problog/problog_export.py`
  - `src/factpy_kernel/adapters/problog/provenance.py`
- Audit Log:
  - [2026-03-29_problog-adapter-batch.audit.md](./2026-03-29_problog-adapter-batch.audit.md)

## 1. Problem

Walkthrough 遗留 5 条 ProbLog adapter finding：

- F-PL-1：所有 candidates 共享同一 trace_dict（中）
- F-PL-2：`_split_result_line` rsplit 冒号分隔可能误切（低）
- F-PL-3：`persist_problog_annotations` 只用首条 asrt_id（低）
- F-PL-4：`_claim_probability` bool-only raises 而非 fallback（低）
- F-PL-5：`_split_top_level_args` 重复实现（信息）

## 2. Goals

- F-PL-1：deepcopy trace_dict per candidate
- F-PL-2：colon path 加 float-match 前置检查（已有，增加注释说明 rsplit 安全性）
- F-PL-3：遍历 written 建 asrt_id 映射（同 F-PR-5 模式）
- F-PL-4：`raise` → `return 1.0` fallback
- F-PL-5：抽 `_split_top_level_args` 到 `_parsing.py`

## 3. Acceptance

- [x] trace_dict 不跨 candidate 共享（deepcopy）
- [x] colon path 有 float-match guard（已有）+ 注释说明
- [x] 多 written assertion 场景各 annotation 绑定到正确 asrt_id
- [x] bool-only confidence fallback 到 1.0
- [x] `_split_top_level_args` 只有一份定义（`_parsing.py`）
- [x] 4 个新测试（实际 3 个新 test methods + 1 个在已有 class 内）
- [x] 全量回归绿（604 passed）

## 4. Implementation Plan

1. 创建 `_parsing.py` 放 `_split_top_level_args`
2. `engine_eval.py` — F-PL-1 deepcopy
3. `problog_import.py` — F-PL-2 注释 + F-PL-5 删重复
4. `accept.py` — F-PL-3 遍历 written
5. `problog_export.py` — F-PL-4 fallback
6. `provenance.py` — F-PL-5 删重复改 import
7. 补测试
8. 更新 `02_problog_adapter.md`
