# SDK 中英一致性检查表

更新时间：2026-03-03  
基线目录：`src/kernel/sdk/docs`

本文件用于确认中文与英文 SDK 文档是否同时反映当前代码行为。

## 1. 检查范围

- 主指南：
  - `00_user_guide.md`
  - `00_user_guide.en.md`
- 专项文档：
  - `01_alignment_matrix.md`
  - `01_alignment_matrix.en.md`
  - `02_readwrite_and_ingest.md`
  - `02_readwrite_and_ingest.en.md`
  - `03_rules_and_derivations.md`
  - `03_rules_and_derivations.en.md`
  - `04_api_surface.md`
  - `04_api_surface.en.md`

## 2. 本轮对齐结论（2026-03-03）

| 文档组 | 结论 | 说明 |
| --- | --- | --- |
| `00_user_guide(.en)` | 已对齐 | 主指南口径统一到 `00_user_guide.md`：row_format、时态读视图、Derivation 边界一致 |
| `01_alignment_matrix(.en)` | 已对齐 | 增补 `row_format` 优先级/弃用、batch context manager、wire 导出约束 |
| `02_readwrite_and_ingest(.en)` | 已对齐 | ingest 去重、meta 规则、batch/edit retract 参数形态与 context 语义一致 |
| `03_rules_and_derivations(.en)` | 已对齐 | Rule/Query/Derivation 语义、`accept` 参数边界、`temporal_view` 拒绝一致 |
| `04_api_surface(.en)` | 已对齐 | 顶层导出、错误码、方法签名与关键边界一致 |

## 3. 关键语义核对清单

以下语义在中英文文档中都应保持一致：

- Schema：
  - `Field.cardinality` 仅 `single|multi`
  - `Identity(primary_key=...)` 有效
  - `dims/fact_key` 已移除
- Read facade：
  - `find(...)` 不支持 `temporal_view`
  - `FieldAssertions` 仅 `active/history/at/version`（无 `.chosen`）
- Rule/Derivation：
  - `head` 中 primary_key 字段编译期报错
  - 跨坐标属性比较仅允许同实体同 primary_key 字段
  - `sdk.evaluate(..., temporal_view=...)` 显式报错
- Query：
  - Query 默认返回 `list[dict]`
  - Query 支持 `row_format="instance"`（仅单个 `Entity(var)` head）
  - field head 仅支持 `single` 字段
  - 非法 Query `row_format` 或 instance/head 不匹配时报 `QUERY_INVALID_ROW_FORMAT`
- 协议与写入：
  - `sdk_batch_plan_v1` 无 `dims/fact_key`
  - wire 导出不接受 raw `idref_v1` 字符串值
  - `ingest_key` 含 `valid_from/valid_to/version`
  - batch handle 撤销参数名为 `assertion_id`；edit `FieldEditor` 为 `asrt_id`
- 运行时行为：
  - `row_format` 优先级：调用参数 > store 默认 > `FACTPY_ROW_FORMAT` > `"dict"`
  - `row_format="tuple"` 触发 `DeprecationWarning`
  - `SDKBatchTx` context manager 不自动 commit/rollback

## 4. 同步规则（持续维护）

每次 SDK 行为变更时：

1. 同 PR 更新中文文档与英文文档，不分先后，但必须同批提交。  
2. 若行为存在“已实现/未实现”边界，必须在 `00` 与 `03` 同时标注。  
3. 若导出面变化（`__all__` 或公开方法），同步更新 `04` 中英文。  
4. 若 breaking change 涉及语义边界，同步更新 `01` 中英文与本检查表。  
5. PR 描述建议附一句：`CN/EN docs synced`。  
