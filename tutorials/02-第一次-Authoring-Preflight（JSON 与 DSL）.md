# 教程 2：第一次 Authoring Preflight（JSON 与 DSL）

本教程演示两条输入路径：

- **JSON Authoring payload**
- **Python DSL（AST parser-first）**

目标是得到稳定的 `authoring_session_dto_v1` / `workflow dry-run` 输出。

---

## A. 使用 JSON Authoring payload 做 preflight

### 1) 创建最小 schema 文件

文件：`/Users/zhenzhili/symbolic_agent/.tutorial_work/authoring_schema.json`

```json
{
  "entities": [
    {
      "entity_type": "Person",
      "identity_fields": [
        {"name": "source_id", "type_domain": "string"}
      ],
      "fields": [
        {
          "py_name": "country",
          "name": "country",
          "type_domain": "string",
          "cardinality": "functional"
        }
      ]
    }
  ]
}
```

### 2) 执行 preflight

```bash
cd /Users/zhenzhili/symbolic_agent
python -m factpy_kernel.authoring.cli preflight \
  --authoring-schema .tutorial_work/authoring_schema.json
```

预期输出（示意）：

```json
{
  "authoring_session_dto_version": "authoring_session_dto_v1",
  "status": "ok",
  "sections": {
    "schema_preflight": {
      "status": "ok"
    }
  }
}
```

### 3) 执行 workflow dry-run（不写 registry）

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --authoring-schema .tutorial_work/authoring_schema.json
```

这会返回：

- `session`
- `publish_plan`（dry-run）
- `apply_result`（dry-run）

建议额外关注这些字段（后续排障会用到）：

- `status`
- `summary`
- `diagnostics_contract`
- `publish_plan.actions[]`

---

## B. 使用 Python DSL（Schema）做 preflight

> 当前实现是 **AST parser-first**：解析源码，不执行用户代码。

### 1) 创建 DSL 文件

文件：`/Users/zhenzhili/symbolic_agent/.tutorial_work/schema.py`

```python
class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional")
    tags: str = Field(cardinality="multi", aliases=["labels"], display_name="Tags")
```

### 2) 执行 preflight

```bash
python -m factpy_kernel.authoring.cli preflight \
  --schema-dsl .tutorial_work/schema.py
```

### 3) 使用 safe 模式（适合编辑器/用户输入）

如果 DSL 有语法/结构错误，`--safe` 不会让 CLI 直接失败，而是把错误写进 canonical diagnostics：

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl .tutorial_work/schema.py \
  --safe
```

你会在输出中看到类似：

- `phase = "schema.dsl_parse"`
- `code`（canonical）
- `path`
- `dsl_error_kind`
- `details`

### 4) 故意制造一个 DSL 错误（验证 safe 模式）

新建 `/.tutorial_work/schema_bad.py`：

```python
class Person(Entity):
    source_id: str = Identity()
    age: int = Field(cardinality="functional", bad_kw=True)
```

运行：

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl .tutorial_work/schema_bad.py \
  --safe
```

预期在 `sections.schema_preflight.diagnostics[0]` 看到：

- `phase = "schema.dsl_parse"`
- `dsl_error_kind = "structure"`
- `details.dsl_error_detail_code = "unsupported_keywords"`

---

## C. （可选）Rule / Derivation DSL 示例

你也可以为 `workflow-dry-run` 同时提供 `rule_dsl` 与 `derivation_dsl`：

```python
# .tutorial_work/rule.py
country_rows = Rule(
    version="v1",
    select=["E", "C"],
    body=[Pred("person:country", "$E", "$C")],
    public=True
)
```

```python
# .tutorial_work/derivation.py
country_drv = Derivation(
    head=Person.country(person=E, country=country),
    materialize_as="fact",
    body=[Pred("person:country", "$E", "$country")],
    mode="python",
    temporal_view="record"
)
```

说明（重要）：

- 推荐使用蓝图风格 `head=... + materialize_as`；当前 compile/preflight 会基于 `SchemaIR` 做 schema-aware lowering。
- 对 `head=Person.country(person=E, country=country), materialize_as="fact"`，会 lowering 到目标谓词 `person:country` 与位置映射 `head_vars=["$E", "$country"]`。
- `head_vars`（`select` 仍兼容但不推荐）语义仍是按目标谓词 `arg_specs` **位置顺序**逐位对应，不是“实体字段平铺投影”。

运行：

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl .tutorial_work/schema.py \
  --rule-dsl .tutorial_work/rule.py \
  --derivation-dsl .tutorial_work/derivation.py
```

## D. （可选）JSON `rule_request` / `derivation_request` 示例

如果你不使用 DSL，也可以直接给 CLI 传 JSON 请求（有利于调试字段兼容性）。

文件：`/.tutorial_work/rule_request.json`

```json
{
  "payload": {
    "rule_id": "rules.country_rows",
    "version": "v1",
    "select_vars": ["$E", "$C"],
    "where": [["pred", "person:country", ["$E", "$C"]]],
    "expose": true
  }
}
```

文件：`/.tutorial_work/derivation_request.json`

```json
{
  "payload": {
    "derivation_id": "drv.country",
    "target_pred_id": "person:country",
    "head_vars": ["$E", "$C"],
    "where": [["pred", "person:country", ["$E", "$C"]]],
    "mode": "python",
    "temporal_view": "record"
  }
}
```

运行：

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --authoring-schema .tutorial_work/authoring_schema.json \
  --rule-request .tutorial_work/rule_request.json \
  --derivation-request .tutorial_work/derivation_request.json
```

下一步：继续看 [`03-Apply-Execute-与-Registry.md`](./03-Apply-Execute-与-Registry.md)
