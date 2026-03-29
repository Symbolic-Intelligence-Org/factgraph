# Task Blueprint: PyReason Adapter Batch Fix

- Status: implemented
- Created: 2026-03-29
- Last Updated: 2026-03-29
- Related Modules:
  - `src/factpy_kernel/adapters/pyreason/session.py`
  - `src/factpy_kernel/adapters/pyreason/runner.py`
  - `src/factpy_kernel/adapters/pyreason/accept.py`
  - `src/factpy_kernel/adapters/pyreason/provenance.py`
  - `src/factpy_kernel/adapters/pyreason/where_compile.py`
- Audit Log:
  - [2026-03-29_pyreason-adapter-batch.audit.md](./2026-03-29_pyreason-adapter-batch.audit.md)

## 1. Problem

Walkthrough 遗留 5 条 PyReason adapter finding：

- F-PR-2：`_validate_bound` 接受 bool（中）
- F-PR-3：`_resolve_shared_meta` confidence=0.0 不对称（中）
- F-PR-4：`split(":",1)[1]` 假设 pred_id 含冒号（低）
- F-PR-5：`persist_pyreason_annotations` 只用首条 asrt_id（低）
- F-PR-6：`_pred_short_name` / `_parse_edge_component` 三处重复（信息）

## 2. Goals

- F-PR-2：加 bool guard
- F-PR-3：改 `0.0 <` 为 `0.0 <=`
- F-PR-4：3 处 `split` 改用 `_pred_short_name`
- F-PR-5：遍历 `written` 建 asrt_id 映射
- F-PR-6：抽 `_pred_short_name` + `_parse_edge_component` 到 `_helpers.py`

## 3. Acceptance

- [x] `_validate_bound([True, 0.5])` → ValueError
- [x] `_resolve_shared_meta({"confidence": 0.0}, lower_bound=0.5)` → 不报错
- [x] `pred_id="noprefix"` 在 `_extract_derived_facts` 中不抛 IndexError
- [x] 多 written assertion 场景各 annotation 绑定到正确 asrt_id
- [x] `_pred_short_name` / `_parse_edge_component` 只有一份定义（`_helpers.py`）
- [x] 4 个新测试
- [x] 全量回归绿（600 passed）

## 4. Implementation Plan

1. 创建 `_helpers.py` 放 `_pred_short_name` + `_parse_edge_component`
2. `session.py` — F-PR-2 bool guard + F-PR-3 范围修正
3. `runner.py` — F-PR-4 改用 `_pred_short_name` + F-PR-6 删重复
4. `accept.py` — F-PR-5 遍历 written 建映射
5. `provenance.py` — F-PR-6 删重复改 import
6. `where_compile.py` — F-PR-6 删重复改 import
7. 补测试
8. 更新 `03_pyreason_adapter.md`
