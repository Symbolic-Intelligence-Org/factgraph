# SDK 能力对齐矩阵（当前实现）

更新时间：2026-05-09 (post-L SDK ergonomics redesign)
范围：`src/kernel/sdk`

> **post-L taxonomy note：** v0.1 SDK 顶层入口为 `FactGraph` (`SDKStore` 字面别名),通过 8 个 taxonomy namespace + 2 个 sub-namespace 暴露既有 30 个 flat 方法。flat 形式 (`sdk.<method>(...)` / `SDKStore.<method>(...)`) 作为 foundational API 永久支持。详见 [04_api_surface.md §0](04_api_surface.md)。

## 1. Layer Ownership

| 层 | 当前职责 |
| --- | --- |
| `kernel.application` | canonical Python runtime authority；拥有 read/write/query/ingest/compiled derivation runtime DTO 与 executor |
| `kernel.sdk` | Python product surface；拥有 schema/DSL authoring、`SDKStore` facade、snapshot/editor/batch outward objects、compatibility errors |
| `kernel.core` | ledger/store/rules/evidence 等低层语义内核 |
| `service` / `agent` | delivery / product consumers；production runtime code 不新增 SDK runtime import |

## 2. 能力矩阵

| 能力 | 状态 | 当前行为 / owner |
| --- | --- | --- |
| Schema 声明（`Entity/Identity/Field`） | 已实现 | SDK authoring surface |
| Schema 编译/预检辅助 | 已实现 | SDK authoring helper；`compile_schema_from_classes` 可作为 authoring import 使用 |
| 低层写入（`ref/set/add/retract`） | 已实现 | SDK convenience API；直接写 ledger，保留 outward compatibility |
| 批处理 staging（`sdk.batch()`） | 已实现 | SDK owns staging/wire/facade；application owns write planning/apply when operations fit application protocol |
| 读写 facade（`get/find/edit`） | 已实现 | SDK owns snapshot/editor outward shape；application owns read DTO hydration/write planner |
| Assertion 读视图 | 已实现 | SDK facade shape |
| ingest / provenance | 已实现 | SDK owns descriptor parsing, diagnostics and outward `IngestResult`; application owns normalized ingest executor for cache-resolvable items |
| 审计查询（`explain_fact/conflicts`） | 已实现 | SDK facade over audit/core read helpers |
| Rule DSL + `sdk.run(rule)` | 已实现 | SDK owns DSL/lowering; core/application execute runtime-normalized pieces |
| Query DSL + `sdk.run(query)` | 已实现 | SDK owns `Query` DSL and outward row shape; application owns query runtime executor |
| Derivation + `sdk.evaluate/accept` | 已实现 | SDK owns DSL sugar and compatibility; application owns compiled derivation evaluate/accept orchestration |
| Registry（`SDKRegistry`） | 已实现 | SDK authoring-adjacent facade; application contracts do not accept `SDKRegistry` objects |

## 3. 硬边界（当前语义）

| 主题 | 当前行为 |
| --- | --- |
| SDK product surface | `kernel.sdk.__all__` 只表达 SDK user-facing surface / compatibility aliases，不导出 application internals |
| Application protocol | 不接 SDK facade object、SDK `Field` descriptor 或 SDK DSL object |
| service / agent imports | production SDK imports 由 `test_sdk_consumer_boundary.py` 守护；当前唯一允许项是 agent extraction 的 `compile_schema_from_classes` authoring helper |
| 旧字段语义 | `functional/temporal/dims/fact_key` 已移除 |
| `vars()` | 不支持 `with vars() as (a,b)`；支持命名模式与 factory 模式 |
| 字符串 DSL | `sdk.run("...")` / `sdk.evaluate("...")` 不支持 |
| `find(...)` | 不支持 `temporal_view`；identity 过滤一旦使用必须传全 identity 字段 |
| Assertion 视图 | 不再提供 `.chosen`；仅 `active/history/at/version` |
| `sdk.run(...)` 分发 | 支持 Rule / Query；传 Derivation 直接报错并提示用 `evaluate()` |
| `sdk.evaluate(...)` 参数 | `temporal_view` 已移除并显式报错 |
| Rule `row_format` 细节 | `"tuple"` 仍可用但会触发 `DeprecationWarning`；推荐统一 `"dict"` |
| `SDKBatchTx` 上下文 | `with sdk.batch() as tx:` 的 `__exit__` 不自动提交也不自动回滚，必须显式 `commit()` |
| wire 导出约束 | `BatchPlan.export()/to_json()` 禁止 raw `idref_v1` 字符串值，实体引用应通过同 tx 句柄表达 |
| `single` 字段语义 | `single` 是读取侧单值视图；写入不会自动清理旧断言 |
| Derivation `head` 语义 | `head` 中出现 `primary_key` 字段是编译期硬错误 |
| 跨坐标属性比较 | 仅允许同实体类型、同 `primary_key` 字段的 `==`；否则编译期错误 |
| RuleRef 约束 | 被引用规则必须 `expose=True`；`RuleRef` 不允许在 `Not(...)` 体内 |
| Query head 约束 | 仅 `Entity(var)` 或 `Entity.field(...)`；字段投影仅支持 `single` 字段 |
| Registry 与多 head | `evaluate` 支持多 head；`register_derivation(...)` 仍按单 head语义 |

## 4. 延期项

| 项目 | 状态 |
| --- | --- |
| `sdk.create(...)` | 延期 |
| `sdk.save(plain_entity)` / `snapshot.to_entity()` | 延期 |
| ingest 正式类型（TypedDict/dataclass） | 延期 |
| Rule/Derivation head 时态写语义（直接产出 `valid_from/valid_to/version`） | 延期 |
| Registry 侧多 head 原生发布语义 | 延期 |
| SDK god files 物理拆分(`store.py` / `batch.py` / `facade.py`) | 延期；本轮完成 runtime delegation,未做行数收缩 |
| 完整 exception hierarchy 迁移 | 延期；application runtime 使用 DTO error shape,SDK product-domain errors 保留 |
