# 教程 9：CLI 命令速查（Reference）

本页是 `factpy_kernel.authoring.cli` 的速查表。目标是减少在教程 1–8 与契约文档之间来回跳转。

> 命令默认在项目根目录执行：`/Users/zhenzhili/symbolic_agent`

## 0. 命令入口

```bash
python -m factpy_kernel.authoring.cli --help
```

当前子命令（以实际 `--help` 为准）：

- `preflight`
- `workflow-dry-run`
- `apply-execute`
- `registry-list`
- `registry-show`

---

## 1. `preflight`

用于：只做 preflight（不写 registry）。

### 1.1 JSON 输入

```bash
python -m factpy_kernel.authoring.cli preflight \
  --authoring-schema /path/to/authoring_schema.json \
  --rule-request /path/to/rule_request.json \
  --derivation-request /path/to/derivation_request.json
```

### 1.2 DSL 输入

```bash
python -m factpy_kernel.authoring.cli preflight \
  --schema-dsl /path/to/schema.py \
  --rule-dsl /path/to/rule.py \
  --derivation-dsl /path/to/derivation.py
```

### 1.3 `--safe`（仅 DSL）

```bash
python -m factpy_kernel.authoring.cli preflight \
  --schema-dsl /path/to/schema.py \
  --safe
```

说明：

- `--safe` 仅对 DSL 输入有效
- safe 模式会把 parser/结构错误写入 canonical diagnostics，而不是直接抛异常终止 CLI

### 1.4 输出重点字段（最小）

- `authoring_session_dto_version`
- `status`
- `sections`
- `diagnostics_contract`

---

## 2. `workflow-dry-run`

用于：构建并返回 `session + publish_plan + apply_result(dry-run)`，不写 registry。

### 2.1 JSON 输入

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --authoring-schema /path/to/authoring_schema.json
```

### 2.2 DSL 输入

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl /path/to/schema.py \
  --rule-dsl /path/to/rule.py \
  --derivation-dsl /path/to/derivation.py
```

Derivation DSL 语义提醒（重要）：

- 新示例推荐使用蓝图风格 `head + materialize_as`（compile/preflight 会基于 `SchemaIR` 做 schema-aware lowering）。
- 当前实现仍兼容 `target + head_vars`（`select` 为兼容别名），适合排查 canonical payload。
- lowering 后 `head_vars` 仍按目标谓词 `target` 的 `arg_specs` **位置顺序**映射；`arg0` 必须是实体槽位（变量名不要求固定为 `"$E"`，但值必须是 `entity_ref`）。
- `target` 指向业务谓词（GNF 事实谓词），不是实体字段平铺结构。

### 2.3 DSL + `--safe`

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl /path/to/schema.py \
  --safe
```

### 2.4 输出重点字段（最小）

- `authoring_publish_workflow_bundle_dto_version`
- `kind = "authoring_publish_workflow_bundle"`
- `session`
- `publish_plan`
- `apply_result`

---

## 3. `apply-execute`

用于：真实执行 authoring apply，写入 file registry 与 apply events。

### 3.1 JSON 输入

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --authoring-schema /path/to/authoring_schema.json \
  --registry-dir /path/to/registry \
  --apply-request-id req-001
```

### 3.2 DSL 输入

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl /path/to/schema.py \
  --rule-dsl /path/to/rule.py \
  --derivation-dsl /path/to/derivation.py \
  --registry-dir /path/to/registry \
  --apply-request-id req-001
```

### 3.3 事务策略

```bash
# v1（默认）
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl /path/to/schema.py \
  --registry-dir /path/to/registry \
  --transaction-policy best_effort_no_rollback_v1

# v2（当前最小可执行版）
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl /path/to/schema.py \
  --registry-dir /path/to/registry \
  --transaction-policy prevalidate_no_partial_strict_v2
```

Derivation DSL 示例（推荐写法）：

```python
Derivation(
    head=Person.country(person=E, country=country),
    materialize_as="fact",
    body=[Pred("person:country", "$E", "$country")]
)
```

### 3.4 `--safe` 限制（重要）

- `apply-execute` **不支持** `--safe`
- 如需 safe diagnostics，请先执行：
  - `workflow-dry-run --safe`

### 3.5 输出重点字段（最小）

- `apply_execute.status`
- `apply_execute.idempotency`
- `apply_execute.transaction`
- `apply_execute.diagnostics`

常用排障字段：

- `transaction.policy`
- `transaction.prevalidate_status`
- `transaction.failure_phase`
- `transaction.partial_apply`

---

## 4. `registry-list`

用于：列出 registry 中的 IDs 或版本列表（只读）。

### 4.1 基本用法

```bash
python -m factpy_kernel.authoring.cli registry-list \
  --registry-dir /path/to/registry \
  --kind rule_ids
```

### 4.2 支持的 `--kind`

- `rule_ids`
- `derivation_ids`
- `apply_run_ids`
- `rule_versions`（需要 `--id`）
- `derivation_versions`（需要 `--id`）

### 4.3 版本列表示例

```bash
python -m factpy_kernel.authoring.cli registry-list \
  --registry-dir /path/to/registry \
  --kind rule_versions \
  --id rules.country_rows
```

### 4.4 输出重点字段（最小）

- `kind = "authoring_registry_list_result"`
- `list_kind`
- `count`
- `items`

---

## 5. `registry-show`

用于：查看 registry 中某个对象（只读）。

### 5.1 支持的 `--kind`

- `manifest`
- `schema`
- `rule`
- `derivation`
- `apply-run`

### 5.2 常见示例

```bash
# manifest
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir /path/to/registry \
  --kind manifest

# schema entry
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir /path/to/registry \
  --kind schema

# rule latest
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir /path/to/registry \
  --kind rule \
  --id rules.country_rows \
  --latest

# derivation latest
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir /path/to/registry \
  --kind derivation \
  --id drv.country \
  --latest

# apply run
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir /path/to/registry \
  --kind apply-run \
  --id req-001
```

### 5.3 参数约束（常见错误）

- `--kind rule_versions / derivation_versions` 时，`registry-list` 必须带 `--id`
- `--kind rule / derivation` 时：
  - `--latest` 与 `--version` 二选一
- `--kind apply-run` 时：
  - 需要 `--id`
  - 不支持 `--version`
  - 不支持 `--latest`

### 5.4 输出重点字段（`apply-run`）

- `kind = "authoring_registry_show_result"`
- `show_kind = "apply-run"`
- `item.kind = "authoring_apply_execute_run"`
- `item.apply_request_id`
- `item.idempotency`
- `item.transaction`

---

## 6. 输入组合规则（必须遵守）

- **不要混用** JSON payload 输入与 DSL 输入（同一次命令）
  - 即不要同时传：
    - `--authoring-schema` 与 `--schema-dsl`
    - `--rule-request` 与 `--rule-dsl`
    - `--derivation-request` 与 `--derivation-dsl`
- `preflight / workflow-dry-run / apply-execute` 至少要有一类输入（JSON 或 DSL）

---

## 7. 常见命令模板（复制即用）

### 7.1 快速 dry-run（DSL）

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl .tutorial_work/example_project/authoring/schema.py \
  --rule-dsl .tutorial_work/example_project/authoring/rule.py \
  --derivation-dsl .tutorial_work/example_project/authoring/derivation.py
```

### 7.2 真正 apply（DSL + v1）

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl .tutorial_work/example_project/authoring/schema.py \
  --rule-dsl .tutorial_work/example_project/authoring/rule.py \
  --derivation-dsl .tutorial_work/example_project/authoring/derivation.py \
  --registry-dir .tutorial_work/example_project/registry \
  --apply-request-id example-req-001 \
  --transaction-policy best_effort_no_rollback_v1
```

### 7.3 查看 apply run

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir .tutorial_work/example_project/registry \
  --kind apply-run \
  --id example-req-001
```

---

## 8. 下一步

- 想按“故障现象”排查：看 [`10-排障手册（CLI-Registry-Audit）.md`](./10-排障手册（CLI-Registry-Audit）.md)
- 想看完整可复制样板：看 [`07-完整示例项目模板（可复制运行）.md`](./07-完整示例项目模板（可复制运行）.md)
