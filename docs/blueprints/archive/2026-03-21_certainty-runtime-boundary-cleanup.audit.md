# Task Blueprint Audit: certainty-runtime-boundary-cleanup

- Blueprint: [2026-03-21_certainty-runtime-boundary-cleanup.md](./2026-03-21_certainty-runtime-boundary-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-21 | draft→scoped | Blueprint created | Scope: extract certainty helpers from runtime_v1.py to service/_certainty_service.py, add archive index. Baseline: 1824 lines runtime_v1.py, 212 tests, import graph clean. |
| 2026-03-21 | scoped | P1+P2 fixes applied | P1: 补 test import 迁移（§5.4 + plan step 3）。P2: 冻结 `_compute_all_certainty_summaries` 的 `get_candidate_tree: Callable` contract + 反向依赖禁止（acceptance 条目）。 |
| 2026-03-21 | implementing | Steps 1-3 complete | `_certainty_service.py` 新建，3 函数迁出，test import 迁移。偏差：`FileAuthoringRegistry` import 保留在 runtime_v1.py（非 certainty 消费者 `_load_registered_rules` 仍需要）。212 tests green。 |
| 2026-03-21 | implemented | Steps 4-5 complete | `docs/blueprints/archive/README.md` inventory table（83 条）。`service/docs/01_overview.md` 新增 `_certainty_service.py` 模块条目。 |

## Decision Notes

- `_lookup_condition_weights_for_candidate` 依赖 `FileAuthoringRegistry`，不可下沉 core — 确认留在 service 层（新模块）
- 参数从 `RuntimeSession` 改为 `store + registry_root`：降低耦合但不改行为
- archive index 选择追加到既有 `docs/blueprints/archive/README.md`，不新建文件
