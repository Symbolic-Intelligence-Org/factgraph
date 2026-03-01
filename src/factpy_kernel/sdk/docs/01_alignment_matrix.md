# SDK 能力对齐矩阵（当前实现）

范围：`src/factpy_kernel/sdk`

## 1. 能力矩阵

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| Schema 声明（`Entity/Identity/Field`） | 已实现 | 支持 `dims`、`fact_key`；所有 Entity 自动生成 `<T>:exists`（`is_record` 不再参与语义） |
| Schema 编译/预检辅助 | 已实现 | `build_authoring_schema_from_classes`、`compile_schema_from_classes`、`schema_preflight_from_classes` |
| Store 低层写入（`ref/set/add/retract`） | 已实现 | 立即写 ledger |
| 批处理 staging（`sdk.batch()`） | 已实现 | `preview/commit`、依赖闭包、wire plan 导出/回放 |
| 读取与编辑 facade（`get/find/edit`） | 已实现 | 快照 + 断言级 API + 编辑会话 |
| ingest / provenance 验证 | 已实现 | `sdk.ingest(...)`、`sdk.validate_provenance(...)` |
| 审计查询（`explain_fact/conflicts`） | 已实现 | 冲突组与 chosen 诊断摘要 |
| Rule / Derivation 对象 DSL | 已实现 | `Rule/RuleRef/Derivation/Pred/Not/vars` |
| Registry 封装（`SDKRegistry`） | 已实现 | schema/rule/derivation apply 与查询 |
| Registry 高级入口（`apply_authoring_bundle` / `register_*_spec` / `upsert_schema_ir`） | 已实现 | 面向 authoring 集成与编译后 spec 流程 |

## 2. 关键边界（v1）

| 主题 | 当前行为 |
| --- | --- |
| `vars()` 运行时解包 | 不支持 `with vars() as (a,b)`；支持 `with vars("a","b") as (...)` 或 factory 模式 |
| 字符串 DSL | `sdk.run("...")` / `sdk.evaluate("...")` 不支持 |
| `find` 的 identity 过滤 | 只要传了 identity filter，就必须传全该实体 identity 字段 |
| `find` 的 dims 过滤 | 暂不支持，会抛 `SDKSchemaError` |
| `FieldAssertions.chosen` | 仅适用于无 dims 的 functional 字段 |
| `edit` 行为 | 仅编辑已存在实体，不自动创建；不存在抛 `EntityNotFoundError` |
| `accept` 选项 | SDK facade 仅支持 `approved_by`/`note`/`dry_run`（含 `meta_overrides` 同名键） |
| `explain_fact(*val_atoms)` | `*val_atoms` 走值原子精确匹配过滤，返回 active_claims + chosen_asrt_id |
| `conflicts(pred_id, e_ref)` | 仅返回该冲突组 active_asrt_ids 与 chosen_asrt_id（按活跃断言计算） |
| `RuleRef` 与 `expose` | 自动注册依赖不绕过 `expose=True` 约束；被引用规则未 expose 仍报错 |

## 3. 易混淆点（已按代码确认）

1. `Rule.dependency_rules()` 只收集“直接依赖”规则，不是一次性递归返回全传递依赖。
2. `sdk.run(...)` 只有在未显式传入 `registry` 时，才会自动注册依赖规则。
3. `Field` 作为 Derivation head 调用时，kwargs 规则是“至少一个值为 DSL 值”，不是“全部必须 DSL 值”。
4. 低层 `sdk.set(...)` / `sdk.add(...)` 不做 cardinality 强约束；基数约束主要在 batch/edit/ingest 的 facade 层体现。
5. `find(...)` 无 identity filter 路径默认不回填 identity（`identity_available=False`）。
6. `validate_provenance(dict)` 当前按扁平键校验（如 `derived_rule_id` 顶层键），不自动解包 `{"provenance": {...}}`。

## 4. 明确延期项

| 项目 | 状态 |
| --- | --- |
| `sdk.create(...)` | 延期 |
| `sdk.save(plain_entity)` / `snapshot.to_entity()` | 延期 |
| ingest 正式类型（TypedDict/dataclass） | 延期 |
| `find` 的 dims-aware 过滤 | 延期 |
