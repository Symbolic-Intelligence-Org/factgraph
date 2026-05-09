# SDK 中英一致性检查表

更新时间：2026-05-09 (post-L SDK ergonomics redesign)
基线目录：`src/kernel/sdk/docs`

本文件用于确认中文与英文 SDK 文档是否同时反映当前代码行为。

> **post-L 一致性扩展项：** 自 post-L SDK ergonomics redesign 起,CN/EN 文档需同时呈现 taxonomy form (`FactGraph.<namespace>.<method>(...)`)与 flat form (`sdk.<method>(...)` / `SDKStore.<method>(...)`),并且都以 foundational API 标注 flat 形式 ——既不被弃用也不会移除。新增条目:CN 与 EN 的 taxonomy intro 段落必须包含 `FactGraph` 入口、8 top-level + 2 sub-namespace 列表、与 flat-form-as-foundational-API 说明。详见 [post-L SDK ergonomics redesign blueprint](../../../../docs/blueprints/active/2026-05-09_post-l-sdk-ergonomics-redesign.md) §5.5 / §5.5.6。

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

## 2. 本轮对齐结论（2026-04-28）

| 文档组 | 结论 | 说明 |
| --- | --- | --- |
| `00_user_guide(.en)` | 未改 | SDK outward examples 没变；本轮不触碰 user guide |
| `01_alignment_matrix(.en)` | 已对齐 | 增补 SDK product surface vs application runtime authority、deferred god-file split/error hierarchy |
| `02_readwrite_and_ingest(.en)` | 已对齐 | 增补 ingest 委托 application executor 与 cache-miss fallback 说明 |
| `03_rules_and_derivations(.en)` | 已对齐 | 增补 Query / compiled Derivation runtime delegation 说明 |
| `04_api_surface(.en)` | 已对齐 | 增补 SDKStore facade vs application runtime authority 说明 |
| `README.md` | 已对齐 | 入口 framing 改为 SDK product surface,链接 application runtime docs |

## 3. 关键语义核对清单

以下语义在中英文文档中都应保持一致：

- Layer authority：
  - `kernel.application` 是 canonical Python runtime authority
  - `kernel.sdk` 是 Python product surface / authoring DSL / outward facade
  - SDK docs 不把 application internal DTO 暴露成 SDK public API
- Schema：
  - `Field.cardinality` 仅 `single|multi`
  - `Identity(primary_key=...)` 有效
  - `dims/fact_key` 已移除
- Read facade：
  - `find(...)` 不支持 `temporal_view`
  - `FieldAssertions` 仅 `active/history/at/version`（无 `.chosen`）
- Query / Derivation：
  - Query runtime 由 application executor 承接,SDK 保留 DSL lowering 与 outward row shape
  - Derivation evaluate/accept orchestration 由 application executor 承接,SDK 保留 DSL sugar 与 compatibility checks
  - `head` 中 primary_key 字段编译期报错
  - 跨坐标属性比较仅允许同实体同 primary_key 字段
  - `sdk.evaluate(..., temporal_view=...)` 显式报错
- 协议与写入：
  - ingest 预检与 outward `IngestResult` 留 SDK
  - cache-resolvable ingest set/add/retract 委托 application `apply_ingest_request(...)`
  - cache miss 保守回退 legacy SDK 写入路径
  - `sdk_batch_plan_v1` 无 `dims/fact_key`
  - wire 导出不接受 raw `idref_v1` 字符串值
- 运行时行为：
  - `row_format` 优先级：调用参数 > store 默认 > `FACTPY_ROW_FORMAT` > `"dict"`
  - `row_format="tuple"` 触发 `DeprecationWarning`
  - `SDKBatchTx` context manager 不自动 commit/rollback

## 4. 同步规则（持续维护）

每次 SDK 行为变更时：

1. 同 PR 更新中文文档与英文文档，不分先后，但必须同批提交。
2. 若行为存在“已实现/未实现”边界，必须在 `00` 与相关专题文档同时标注。
3. 若导出面变化（`__all__` 或公开方法），同步更新 `04` 中英文。
4. 若 breaking change 涉及语义边界，同步更新 `01` 中英文与本检查表。
5. 若 runtime authority 或 adapter boundary 变化，同步更新 application docs 与 SDK docs。
6. PR 描述建议附一句：`CN/EN docs synced`。
