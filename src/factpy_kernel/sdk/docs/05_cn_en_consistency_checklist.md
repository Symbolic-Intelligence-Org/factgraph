# SDK 中英一致性检查表

更新时间：2026-03-03  
基线目录：`src/factpy_kernel/sdk/docs`

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
| `00_user_guide(.en)` | 已对齐 | 已按 `single|multi`、`active/history/at/version`、Query/Derivation 现状更新 |
| `01_alignment_matrix(.en)` | 已对齐 | 旧接口边界统一移除，硬约束与延期项一致 |
| `02_readwrite_and_ingest(.en)` | 已对齐 | ingest 去重、meta 规则、读写边界一致 |
| `03_rules_and_derivations(.en)` | 已对齐 | Rule/Query/Derivation 语义、编译期硬错误、`temporal_view` 拒绝一致 |
| `04_api_surface(.en)` | 已对齐 | 顶层导出、错误码、方法索引一致 |

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
  - Query 固定返回 `list[dict]`
  - field head 仅支持 `single` 字段
- 协议与写入：
  - `sdk_batch_plan_v1` 无 `dims/fact_key`
  - `ingest_key` 含 `valid_from/valid_to/version`

## 4. 同步规则（持续维护）

每次 SDK 行为变更时：

1. 同 PR 更新中文文档与英文文档，不分先后，但必须同批提交。  
2. 若行为存在“已实现/未实现”边界，必须在 `00` 与 `03` 同时标注。  
3. 若导出面变化（`__all__` 或公开方法），同步更新 `04` 中英文。  
4. 若 breaking change 涉及语义边界，同步更新 `01` 中英文与本检查表。  
5. PR 描述建议附一句：`CN/EN docs synced`。  
