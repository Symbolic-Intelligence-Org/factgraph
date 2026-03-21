# Task Blueprint: certainty-runtime-boundary-cleanup

- Status: implemented
- Created: 2026-03-21
- Last Updated: 2026-03-21
- Related Modules:
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/core/store/_certainty_materializer.py`
  - `docs/blueprints/archive/`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
- Audit Log:
  - [2026-03-21_certainty-runtime-boundary-cleanup.audit.md](./2026-03-21_certainty-runtime-boundary-cleanup.audit.md)

## 1. Problem

8 个 certainty-related blueprint 连续落地后，`runtime_v1.py`（1824 行）仍保留 3 个 certainty helper：

- `_lookup_condition_weights_for_candidate` (lines 1130-1189)
- `_compute_certainty_summary_from_tree` (lines 1192-1210)
- `_compute_all_certainty_summaries` (lines 1213-1227)

这些函数与 `runtime_v1.py` 的主职责（session lifecycle / endpoint orchestration）无关，增加了文件认知负荷。如果下一步推进 salience/ranking，新代码会继续堆叠到同一文件。

此外，42 对已归档 blueprint 未在任何文档中枚举，不可追溯。

## 2. Goals

- 把 certainty helper 从 `runtime_v1.py` 提取到 service 层专用模块，瘦身 ~100 行
- 补 blueprint archive index，让归档 blueprint 可追溯
- 验证并记录 import boundary 无 violation

## 3. Non-goals

- 不做 `runtime_v1.py` 非 certainty 部分的 helper extraction
- 不新增跨包依赖边（core→authoring、adapters→service 等）
- 不修改任何 public API / DTO shape
- 不修改测试行为或新增功能测试
- 不做泛化的 structural-hygiene 清扫

## 4. Current Context

- 当前实现入口：
  - `runtime_v1.py` 的 `explain_runtime_summary`、`explain_runtime_narrative`、`explain_runtime_nl`、`query_runtime_package` 都调用 certainty helper
  - `_certainty_materializer.py`（core 层）已持有 `materialize_certainty_summary`、`extract_single_referenced_support_tree`、`certainty_summary_to_dict`
- 当前已知约束：
  - `_lookup_condition_weights_for_candidate` 依赖 `FileAuthoringRegistry`（authoring 包），不能下沉到 core 层
  - service→authoring 的 import 是合法方向（已有 registry_fs、derivation_compile、rules 三条）
  - import graph 当前无 violation（已验证）
- 当前相关历史蓝图：
  - `certainty-summary-explain-delivery`（引入 runtime explain certainty helper）
  - `certainty-aware-narrative-nl-delivery`（引入共享 helper + pre-built tree）
  - `certainty-audit-static-delivery`（引入 materializer extraction + export threading）

## 5. Proposed Shape

### 5.1 Extract `service/_certainty_service.py`

新建 `src/factpy_kernel/service/_certainty_service.py`，迁入：

- `_lookup_condition_weights_for_candidate(store, candidate_id, tree_dict, *, registry_root)`
  - 依赖 `Store`（core）+ `FileAuthoringRegistry`（authoring）— 合法 service 层 import
- `_compute_certainty_summary_from_tree(store, candidate_id, tree_dict, *, registry_root)`
  - 改为接受 `store` + `registry_root` 而非 `RuntimeSession`，降低耦合
- `_compute_all_certainty_summaries(store, *, registry_root, get_candidate_tree)`
  - `get_candidate_tree: Callable[[str], dict[str, Any] | None]` — 由 caller 在 runtime_v1.py 绑定为 `lambda cid: _get_candidate_tree(session, cid)`
  - 新模块不 import `runtime_v1`，不反向依赖 session lifecycle

`runtime_v1.py` 的 4 个 caller（explain-summary / narrative / NL / export）改为从 `_certainty_service` import。

### 5.4 Test import 迁移

`test_certainty_explain_contracts.py` 当前直接 `from factpy_kernel.service.runtime_v1 import _lookup_condition_weights_for_candidate`。迁移后改为 `from factpy_kernel.service._certainty_service import _lookup_condition_weights_for_candidate`。`runtime_v1.py` 不保留兼容 re-export（内部 helper 不承诺跨模块稳定）。

### 5.2 Import boundary 文档化

在 blueprint outcome 中记录当前 import boundary 验证结果：
- core → {core} only
- adapters → {core} only
- authoring → {core} only
- audit → {core, adapters} only
- service → {core, authoring, adapters, audit}

### 5.3 Blueprint archive index

在 `docs/blueprints/archive/README.md` 追加 inventory table，枚举所有已归档 blueprint（date / name / status / summary）。

## 6. Boundaries And Invariants

- 必须保持的边界：
  - 不新增任何跨包 import 方向（当前合法方向见 §5.2）
  - `_certainty_materializer.py` 不 import authoring 或 service
  - `_certainty_service.py` 只 import core + authoring（与 runtime_v1.py 相同的合法方向）
- 明确不做的内容：
  - 不改 `_certainty_materializer.py` 的 public API
  - 不改 `package.py` 的 `export_package` contract
  - 不改 `runtime_v1.py` 的任何 endpoint 签名或行为
  - 不动非 certainty helper（如 rule-trace、evidence-tree、view 相关 helper）
- 兼容性约束：
  - 212 tests 全绿（行为不变）

## 7. Acceptance

- [ ] `_certainty_service.py` 持有全部 certainty helper，`runtime_v1.py` 无 certainty 计算逻辑
- [ ] `runtime_v1.py` 行数减少 ~100 行
- [ ] certainty helper 不再依赖 `RuntimeSession`（改为 `store` + `registry_root`）
- [ ] `_compute_all_certainty_summaries` 接受 `get_candidate_tree: Callable[[str], dict | None]`，不 import `runtime_v1`
- [ ] `_certainty_service.py` 不 import `runtime_v1`（无反向依赖）
- [ ] `test_certainty_explain_contracts.py` import 已迁移到 `_certainty_service`
- [ ] import graph 无新 violation（已有方向保持不变）
- [ ] 212 tests 全绿
- [ ] `docs/blueprints/archive/README.md` 包含完整 inventory table
- [ ] 受影响模块 docs 已同步

## 8. Implementation Plan

1. [service/_certainty_service.py] 新建模块，迁入 3 个函数：
   - `_lookup_condition_weights_for_candidate(store, candidate_id, tree_dict, *, registry_root)` — 签名不变
   - `_compute_certainty_summary_from_tree(store, candidate_id, tree_dict, *, registry_root)` — 参数从 `RuntimeSession` 改为 `store + registry_root`
   - `_compute_all_certainty_summaries(store, *, registry_root, get_candidate_tree)` — 参数从 `RuntimeSession` 改为 `store + registry_root + get_candidate_tree callable`
2. [service/runtime_v1.py] 4 个 caller 改为 import from `_certainty_service`，export caller 绑定 `get_candidate_tree=lambda cid: _get_candidate_tree(session, cid)`，删除原函数定义
3. [tests/test_certainty_explain_contracts.py] 更新 import：`from factpy_kernel.service._certainty_service import _lookup_condition_weights_for_candidate`
4. [tests] 运行 212 tests，确认全绿
5. [docs/blueprints/archive/README.md] 追加 inventory table
6. [service/docs] 同步 service 模块文档（如需要）

## 9. Docs To Update

- `docs/blueprints/archive/README.md`（inventory table）
- `src/factpy_kernel/service/docs/01_overview.md`（若 service 模块列表需更新）

## 10. Outcome / Deviations

- 最终落地结果：
  - `service/_certainty_service.py` — 持有 3 个 certainty helper（`_lookup_condition_weights_for_candidate`、`_compute_certainty_summary_from_tree`、`_compute_all_certainty_summaries`）
  - `runtime_v1.py` — 删除 3 个函数定义，4 个 caller 改为 import from `_certainty_service`
  - `_compute_certainty_summary_from_tree` — 参数从 `RuntimeSession` 改为 `store + registry_root`
  - `_compute_all_certainty_summaries` — 参数改为 `store + registry_root + get_candidate_tree callable`
  - `test_certainty_explain_contracts.py` — import 迁移到 `_certainty_service`
  - `docs/blueprints/archive/README.md` — 83 条 inventory table
  - `service/docs/01_overview.md` — 新增 `_certainty_service.py` 模块条目
- 与 blueprint 不同的地方：
  - `FileAuthoringRegistry` import 保留在 `runtime_v1.py`：`_load_registered_rules` 仍依赖它，不在本次 scope 内删除
- 为什么会有这些调整：
  - `_load_registered_rules` 是非 certainty 的 registry 消费者，不在本 blueprint scope
- 归档说明：可归档到 `docs/blueprints/archive/`
