# SDK 能力对齐矩阵（当前实现）

更新时间：2026-03-03  
范围：`src/factpy_kernel/sdk`

## 1. 能力矩阵

| 能力 | 状态 | 当前行为 |
| --- | --- | --- |
| Schema 声明（`Entity/Identity/Field`） | 已实现 | `Field.cardinality` 仅 `single|multi`，`Identity(primary_key=...)` 生效 |
| Schema 编译/预检辅助 | 已实现 | `build_authoring_schema_from_classes` / `compile_schema_from_classes` / `schema_preflight_from_classes` |
| 低层写入（`ref/set/add/retract`） | 已实现 | 直接写 ledger；类型校验在 SDK 层完成 |
| 批处理 staging（`sdk.batch()`） | 已实现 | `preview/commit`、依赖闭包、wire plan 导出/回放；context manager 不自动 commit/rollback |
| 读写 facade（`get/find/edit`） | 已实现 | 快照只读；editor 只允许字段写，不允许 identity 写 |
| Assertion 读视图 | 已实现 | `active` / `history` / `.at(t)` / `.version(v)` |
| ingest / provenance | 已实现 | `sdk.ingest(...)`、`sdk.validate_provenance(...)` |
| 审计查询（`explain_fact/conflicts`） | 已实现 | 返回 active 断言相关诊断，结果包含 `chosen_asrt_id`（可能为 `None`） |
| Rule DSL + `sdk.run(rule)` | 已实现 | 支持对象 DSL；`row_format` 仅 Rule 路径可用（优先级：调用参数 > store 默认 > 环境变量 > `"dict"`） |
| Query DSL + `sdk.run(query)` | 已实现 | Query 固定返回 `list[dict]` |
| Derivation + `sdk.evaluate/accept` | 已实现 | `head` 自动决定 fact/entity candidate kind；支持多 head evaluate 展平 |
| Registry（`SDKRegistry`） | 已实现 | schema/rule/derivation 注册与读取接口完整 |

## 2. 硬边界（当前语义）

| 主题 | 当前行为 |
| --- | --- |
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
| Registry 与多 head | `evaluate` 支持多 head；`register_derivation(...)` 仍按单 head 语义 |

## 3. 延期项

| 项目 | 状态 |
| --- | --- |
| `sdk.create(...)` | 延期 |
| `sdk.save(plain_entity)` / `snapshot.to_entity()` | 延期 |
| ingest 正式类型（TypedDict/dataclass） | 延期 |
| Rule/Derivation head 时态写语义（直接产出 `valid_from/valid_to/version`） | 延期 |
| Registry 侧多 head 原生发布语义 | 延期 |
