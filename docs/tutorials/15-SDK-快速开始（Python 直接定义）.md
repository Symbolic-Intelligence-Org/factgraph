# 15) SDK 快速开始（Python 直接定义）速记

本页是 `15-SDK-快速开始（Python 直接定义）.md` 的教程索引占位与速记版，用于文档测试与跳转。

完整内容请看源码教程文件：
- `tutorials/15-SDK-快速开始（Python 直接定义）.md`
  - 本轮已补充 `materialize_as="record"` / `head=RecordType(...)` 常见报错排查（`record exists predicate not found ...`、record role kwargs 约束、registry schema fallback 提示）
  - 本轮新增 `sdk.get / sdk.find / sdk.edit` 读写 facade（只读快照 `assertions` + context manager 编辑会话）

如果你要使用新的 `sdk.batch` staging 语法，请继续看：
- `16-SDK-Batch-staging（sdk.batch）.md`
- `17-SDK-Batch-staging（语义与契约-v0）.md`

## 关键对象与入口（速记）

- `class Person(Entity)`
- `SDKStore`
- `sdk.get / sdk.find / sdk.edit`
- `SDKRegistry`
- `compile_schema_from_classes`
- `schema_preflight_from_classes`
- `build_authoring_schema_from_classes`
- `apply_schema_classes`

## 普通 Entity 与 batch handle（重要）

- `Person(...)` / `Company(...)`：创建普通内存对象，字段写法是 `obj.field = value`
- `tx.entity(Person, ...)`：创建 `sdk.batch` 托管对象，字段写法可用 `.set/.add/.retract`

示例：

```python
alice = Person(source_id="u-001")
alice.country = "de"  # 普通对象赋值

with sdk.batch(meta={"trace_id": "demo"}) as tx:
    a = tx.entity(Person, source_id="u-001")
    a.country.set("de")  # batch staging 写法
```

## 新增：读取 / 编辑 Facade（速记）

- `sdk.get(EntityType, **identity)`：按 identity 取单个只读快照（不存在返回 `None`）
- `sdk.find(EntityType, **filters)`：按当前视图过滤（`multi` 字段按“包含值”匹配）
- `sdk.edit(EntityType, **identity)`：context manager 编辑；无异常自动 commit
- 边界：`sdk.edit(...)` 需要完整 identity；若只有 `snapshot.ref + asrt_id`（拿不到 record 的 `uid` 等 identity），改用 `sdk.ingest(...)` 的 `retract + set/add`

```python
alice = sdk.get(Person, source_id="u-001")
print(alice.ref, alice.country)
print(alice.identity_available, alice.identity)
print(alice.assertions.country.chosen)

rows = sdk.find(Person, country="de")
print(rows)  # EntitySnapshot(...) 列表（可读 repr）
print(rows[0].name)  # functional -> 单值；multi -> tuple
print(rows[0].assertions.name.history)  # 断言级历史（含 revoked）

with sdk.edit(Person, source_id="u-001") as user:
    user.country.set("fr")
```

速记规则：

- `snapshot.<field>`：当前视图值（用于“像读对象一样看结果”）
- `snapshot.assertions.<field>.active/history/chosen`：断言级信息（`chosen` 仅适用于无 dims 的 functional 字段）
- `snapshot` 是只读；要修改用 `sdk.edit(...)`
- `.ref` 一定可用；`sdk.find(...)` 返回的 snapshot 不保证总能恢复 identity 字段（如某些 record 的 `.uid`）
- `snapshot.identity_available=True` 时，可尝试 `sdk.edit(Type, **snapshot.identity)`；否则优先走 `sdk.ingest(...)`

对象类型速记（避免混淆）：

- `sdk.get/find -> EntitySnapshot`：只读看结果（不可写）
- `sdk.edit -> EntityEditor`：编辑已存在实体（无异常自动 commit）
- `sdk.batch + tx.entity -> batch handle`：构造对象图 / preview / wire plan
- `vars(...)`：规则 DSL 符号对象（不是 store 里的实体）
