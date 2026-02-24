# 15) SDK 快速开始（Python 直接定义）速记

本页是 `15-SDK-快速开始（Python 直接定义）.md` 的教程索引占位与速记版，用于文档测试与跳转。

完整内容请看源码教程文件：
- `tutorials/15-SDK-快速开始（Python 直接定义）.md`

如果你要使用新的 `sdk.batch` staging 语法，请继续看：
- `16-SDK-Batch-staging（sdk.batch）.md`
- `17-SDK-Batch-staging（语义与契约-v0）.md`

## 关键对象与入口（速记）

- `class Person(Entity)`
- `SDKStore`
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
