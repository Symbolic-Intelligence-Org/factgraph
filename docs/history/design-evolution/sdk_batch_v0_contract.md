---
doc_type: history
status: archived
source_of_truth: historical
implementation_state: legacy
owner: sdk/batch
last_verified: 2026-03-14
---

> Archived note: 本文保存 `sdk.batch` 的 v0 语义与契约草案。当前 batch 语义请以 `src/factpy_kernel/sdk/docs/00_user_guide.md`、`src/factpy_kernel/sdk/docs/02_readwrite_and_ingest.md` 和 [16-SDK-Batch-staging（sdk.batch）.md](/Users/zhenzhili/symbolic_agent/docs/guides/tutorials/16-SDK-Batch-staging%EF%BC%88sdk.batch%EF%BC%89.md) 为准。

# SDK Batch Staging v0 Contract

本篇是 `16-SDK-Batch-staging（sdk.batch）.md` 的补充材料，面向“语义边界/契约实现”而不是快速上手。
如果你只需要最短路径示例，请先看 `16`；如果你需要确认保证项、排序、wire 计划、retract 边界，请看本篇。

## 0. 目标与硬约束

本设计引入 `SDKStore` 上层的 staging + flush “编译前端”，用于更自然的数据构造与批量导入。

硬约束（必须）：

1. 对象/batch 层是 `SDKStore` 之上的 staging + flush 编译前端，不引入第二套写入模型。
2. 所有写入语义以 Core Contract 为准：`sdk.ref / sdk.set / sdk.add / sdk.retract`。
3. 必须可展开、可预览、可回放、可等价测试：`preview()` 输出的计划（plan）可一一映射为 Core Contract 调用序列；`commit()` 必须执行与 `preview()` 等价的序列。

非目标（v1）：

- ORM identity map / lazy loading（跨 tx）
- 自动从 store 读取并回填普通 `Entity(...)` 可变对象实例（ORM 风格 hydration）
- ACID 事务承诺（跨进程/跨存储）
- 替代 Core Contract
- 推理/规则层语义增强

补充说明（避免误解）：

- 当前 SDK 已提供显式读写 facade：`sdk.get / sdk.find / sdk.edit`
- 其读取结果是只读快照（`Snapshot`），不是可变 ORM 实例；写入通过显式 `edit(...)` 会话或 `sdk.batch(...)`

## 1. API（最小闭环）

```python
sdk = SDKStore.from_schema_classes([Person, Company, Employment])

with sdk.batch(
    meta={"trace_id": "...", "source": "...", "ingested_at": "...", "confidence": 0.98}
) as tx:
    alice = tx.entity(Person, source_system="HR", source_id="u_1")
    alice.country.set("de")
    alice.name_by_lang.set("Alice", dims={"lang": "en"}, meta={"field_source": "legal_name"})

    google = tx.entity(Company, source_system="HR", source_id="c_GOOG")
    google.sector.set("Tech")

    job = tx.entity(Employment, uid="...")  # record / relation node
    job.employee.set(alice)
    job.employer.set(google)
    job.since.set(2010)
    job.title.set("Staff Engineer")

    plan = tx.preview()     # 纯函数语义：不写入，可重复调用
    res = tx.commit()       # 执行与 plan 等价的 Core 调用序列
```

可选高级接口（v1 可部分延期）：

- `tx.preview(objects=[job], include_deps=False)`
- `tx.commit(include_deps=True)`（默认 True）
- `tx.save(handle, include_deps=True)`（便捷入口；当前仅接受 `ManagedEntityHandle`，内部等价 `commit(objects=[handle], ...)`）

## 2. Batch 语义边界

`batch` 承诺：

- 共享 meta（batch meta 自动传播）
- 批量 flush（统一生成 plan 并提交）
- 确定性 preview（顺序稳定、结果可复用）

实现现状（v0，避免误解）：

- `tx.save(...)` 当前是“立即提交便捷方法”，不是“登记到 tx 等待稍后统一 commit”
- `tx.save(...)` 当前仅接受 `tx.entity(...)` 返回的 handle，不接受普通 `Entity(...)` 对象
- “plain Entity 对象图 -> staging 编译保存”属于后续易用层增强方向，不属于 v0 契约

`batch` 不承诺：

- 跨进程/跨存储 ACID
- 读写隔离、并发冲突控制（由底层 store/ledger 决定）

可承诺（v1）：单次 `commit()` 的“逻辑原子性”

- 若 commit 失败，必须返回未写入的 plan（或失败点前后切分）与结构化错误清单（带 staging path）
- 文档不使用 “ACID” 字样

## 3. Identity（对象身份）与幂等

对象身份只取决于 identity，不取决于 Python 对象实例。

允许的 identity 形式（v0）：

- Entity：以 schema identity 字段集合为准（常见是 `(Type, source_system, source_id)`）
- Record/Relation：v0 允许 `uid`；也允许 source-based identity（若 schema 声明）

Record/Relation identity 优先级（v0 约定）：

1. 若 schema 中存在 `source_system/source_id` 且用户提供二者，优先按 source-based identity 归并（更利于 ETL 幂等）
2. 否则使用用户提供的 identity 字段（如 `uid`）

同一 tx 内规则（写死）：

- `tx.entity(Type, same identity...)` 必须返回同一个 staging handle（identity map within tx）
- functional 字段重复 `set`：后写覆盖前写（last-write-wins）
- multi 字段重复 `add`：按 `(pred, E, O, dims)` 去重（保持一次写入）

跨 tx 幂等：

- 对象层不承诺；沿用底层 dedup/id_policy 策略
- 文档明确：`uid` 默认不保证跨 tx 幂等，ETL 场景应优先 source/keys 身份

## 4. 依赖闭包（include_deps）

默认：`include_deps=True`

含义：

- 若对象 A 的字段引用对象 B（例如 `job.employee.set(alice)`），则 preview/commit 默认自动包含 B（闭包保存）
- 计划输出按拓扑顺序：先输出被引用对象的 `RefOp` / 字段 op，再输出引用边/record

`include_deps=False`：

- 只处理显式指定 objects（或 tx 内显式 save 的对象），不做依赖闭包
- 若存在未满足依赖，preview/commit 必须失败并给出 staging path（例如 `job.employee`）

依赖定义（v0）：

- 字段值是 staging handle（`ManagedEntityHandle`）或 `EntityRef` 时视为依赖
- 普通标量值不构成依赖

## 5. meta 合并（写死算子）

合并算子（写死）：

`effective_meta = batch_meta ⊕ entity_meta ⊕ field_op_meta ⊕ commit_meta`

冲突策略（写死）：

- 同 key：后者覆盖前者
- v0 默认不做智能合并/聚合
- 未来若支持 `tags/labels` 聚合，必须白名单声明并显式启用

## 6. 错误时机与错误形状

立即报错（操作时）：

- 字段不存在/不可写
- cardinality 不匹配（functional 用 add；multi 用 set）
- dims 缺失/多余/不匹配
- 本地可判定的类型错误

字段基数规则（v0 强制）：

- `functional` 只允许 `set(...)`
- `multi` 只允许 `add(...)`（以及对历史断言做 `retract(...)`）

延迟报错（preview/commit）：

- 依赖闭包失败
- 全局冲突/策略约束（chosen/current 等）
- 底层写入错误（ledger/store）

错误必须包含 staging path：

- 例如：`job.employee`
- 例如：`alice.name_by_lang[lang=en]`

## 7. 顺序确定性（必须）

同一输入必须产生同一 plan（便于回放与 snapshot test）。

排序规则（v0）：

1. 实体：按首次出现顺序（creation index）
2. 实体内字段：按 schema 声明顺序（若不可得则按字段名排序 fallback）
3. 同字段多操作：按操作追加顺序（op index）
4. 依赖拓扑：在满足上述稳定顺序的前提下进行稳定拓扑排序（同层保留原顺序）

## 8. Plan 形状与 Core Contract 等价

`preview()` 输出 `BatchPlan`，其中每个 op 都能一一映射为 Core Contract 调用。

最小 op 集（v0）：

- `RefOp(type, identity) -> EntityRef`
- `SetOp(pred, E, value, dims, meta)`
- `AddOp(pred, E, value, dims, meta)`
- `RetractOp(assertion_id, meta)`（retract v1：仅显式 `assertion_id`）

`RefOp`（写死要求）：

- `RefOp` 必须显式存在，且先于该实体的任何字段 op
- `commit()` 可内部 memoize `EntityRef`，但语义上必须与 plan 中 `RefOp` 顺序一致
- 不允许“隐式 ref”绕过 plan（避免不可审计行为）

等价性（硬约束）：

- `commit()` 必须执行与 `preview()` 同输入、同排序、同 meta merge 的 op 序列
- 必须有测试：`apply(plan)` 与 `commit()` 在 ledger 中产生的 assertion 集合一致

## 9. PoC 实现策略（低风险）

不修改现有 `Entity` / `Field` descriptor 语义。

新增最小组件：

- `SDKBatchTx`
- `ManagedEntityHandle`
- `ManagedFieldHandle`
- `BatchPlan` + `Op` 数据结构

实现原则：

- `tx.entity(...)` 只创建/返回 handle，并注册 identity map
- `handle.<field>` 返回 field proxy（通过 `__getattr__` 或预生成属性）
- `preview()` 编译 staging graph -> `BatchPlan(ops=[...])`
- `commit()` 逐条调用 `sdk.ref/set/add/retract`

## 10. 最小测试矩阵（v0）

1. 基础 ETL：2 entity + 1 record + batch meta
2. functional 覆盖：同字段多次 `set`，后者生效
3. multi 去重：重复 `add` 不重复写
4. 依赖闭包：`commit(job)` 自动包含依赖对象
5. `include_deps=False`：缺依赖时报错（带 path）
6. meta merge：batch/entity/field/commit 覆盖顺序
7. `preview == commit` 等价：比对 ledger 结果
8. 顺序稳定：同输入多次 `preview()` 输出一致
9. 错误路径：dims/type/cardinality 错误带 path
10. demo 可读性：示例可运行

## 11. PoC 骨架建议（最小接口）

建议 PoC 先实现以下接口（其余先留空）：

- `SDKStore.batch(*, meta: dict[str, Any] | None = None) -> SDKBatchTx`
- `SDKBatchTx.entity(entity_cls: type[Entity], **identity_values: Any) -> ManagedEntityHandle`
- `SDKBatchTx.preview(*, objects: list[ManagedEntityHandle] | None = None, include_deps: bool = True, commit_meta: dict[str, Any] | None = None) -> BatchPlan`
- `SDKBatchTx.commit(*, objects: list[ManagedEntityHandle] | None = None, include_deps: bool = True, commit_meta: dict[str, Any] | None = None) -> BatchCommitResult`
- `ManagedFieldHandle.set(value: Any, *, dims: dict[str, Any] | list[Any] | tuple[Any, ...] | None = None, meta: dict[str, Any] | None = None) -> ManagedEntityHandle`
- `ManagedFieldHandle.add(value: Any, *, dims: dict[str, Any] | list[Any] | tuple[Any, ...] | None = None, meta: dict[str, Any] | None = None) -> ManagedEntityHandle`

建议的最小 plan 数据结构：

- `BatchPlan`
  - `ops: list[BatchOp]`
  - `warnings: list[str]`（v0 可空）
- `RefOp`
  - `handle_id`, `entity_type`, `identity_values`, `path`
- `SetOp`
  - `handle_id`, `field_name`, `value_kind` (`scalar|handle|entity_ref`), `value`, `dims`, `meta`, `path`
- `AddOp`
  - 同上

## 12. Retract (v1) 边界（强制）

1. `ManagedFieldHandle.retract(...)` 仅支持显式撤销：
   `retract(assertion_id: str, meta: dict | None = None)`。
2. 不支持按值撤销：不提供 `retract(value=..., dims=...)` 等隐式查找/策略相关语义。
3. 排序规则固定：同一实体内 `ref` 在前，随后是所有 `set/add`，最后是所有 `retract`。
4. 幂等/去重固定：
   - 同一 tx 内重复撤销同一 `assertion_id`：仅保留一条 retract op，后写 meta 覆盖前写。
   - 若同一 `assertion_id` 出现在不同字段 handle 上：直接报错（避免 owner/path 语义分叉）。
5. wire retract 仍受 `schema_digest` gate 与 `(pred_id, field_name, entity_type)` 校验约束，避免 schema 漂移误写。

## 13. 实现现状与下一步优化方向（非 v0 契约）

本节用于说明潜在易用层增强方向，不构成 v0 契约承诺。

### 当前现状（已实现）

- `tx.entity(...)` 返回 staging handle，是 batch API 的主入口
- `tx.save(handle, ...)` 是便捷提交方法（等价 `commit(objects=[handle], ...)`）
- 普通 `Entity(...)` 对象仅用于内存构造/赋值，不会自动注册到 tx

### 下一步优化方向（建议）

1. 提供更明确的命名，降低 `tx.save(...)` 歧义
   - 例如新增 `tx.commit_object(handle, ...)` / `tx.commit_handle(handle, ...)`
   - 保留 `tx.save(...)` 作为兼容别名（或在文档中弱化）
2. 增加 plain `Entity` 对象图编译入口（不替代现有 handle API）
   - 例如 `tx.stage(obj)` / `tx.import_entity(obj)` / `tx.save_entity(obj)`
   - 语义仍必须编译成同一套 `preview/commit/wire` 计划
   - 必须保留可预览、可导出、可回放、等价测试约束
3. 增强错误信息与教学提示
   - 对 `tx.save(plain_entity)` 报错给出“请改用 tx.entity(...) 或未来对象图入口”的明确建议
4. 在 `get/find/edit` 之上补充更细粒度检视辅助（可选）
   - 例如 `get_assertion/find_assertions/inspect_entity/inspect_record`
   - 用于 notebook/ETL 调试闭环，但不引入第二套读取语义
