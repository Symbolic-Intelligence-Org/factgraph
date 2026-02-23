# 教程 11：Cookbook｜从 DSL 到 Apply（最短任务流）

本篇按“我要把一组 DSL 定义落到 registry”来组织，不讲完整原理，只给最短任务路径。

## 目标

- 输入：`schema.py` / `rule.py` / `derivation.py`
- 输出：
  - registry 写入成功
  - `apply_request_id` 可查询
  - 可在 audit static UI 看到 apply detail

## 1) 准备文件（最小示例）

目录（示例）：

- `/Users/zhenzhili/symbolic_agent/.tutorial_work/cookbook_apply/authoring/`
  - `schema.py`
  - `rule.py`
  - `derivation.py`

`schema.py`

```python
class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional")
```

`rule.py`

```python
country_rows = Rule(
    version="v1",
    select=["E", "C"],
    body=[Pred("person:country", "$E", "$C")],
    public=True
)
```

`derivation.py`

```python
country_drv = Derivation(
    head=Person.country(person=E, country=country),
    materialize_as="fact",
    body=[Pred("person:country", "$E", "$country")],
    mode="python",
    temporal_view="record"
)
```

说明（避免误解）：推荐写法是 `head + materialize_as`。当前 compile 会把 `head=Person.country(...)` lowering 成目标谓词 `person:country` 与位置映射 `head_vars=["$E", "$country"]`；这个 `head_vars` 语义仍是按 `arg_specs=[E,country]` 位置对应，不是 `Person` 实体字段列表。

## 2) 先做 dry-run（推荐）

```bash
cd /Users/zhenzhili/symbolic_agent
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl .tutorial_work/cookbook_apply/authoring/schema.py \
  --rule-dsl .tutorial_work/cookbook_apply/authoring/rule.py \
  --derivation-dsl .tutorial_work/cookbook_apply/authoring/derivation.py
```

检查：

- `kind = "authoring_publish_workflow_bundle"`
- `status` 为 `ok` 或 `warning`

## 3) 执行 apply（写 registry）

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl .tutorial_work/cookbook_apply/authoring/schema.py \
  --rule-dsl .tutorial_work/cookbook_apply/authoring/rule.py \
  --derivation-dsl .tutorial_work/cookbook_apply/authoring/derivation.py \
  --registry-dir .tutorial_work/cookbook_apply/registry \
  --apply-request-id cookbook-apply-001 \
  --transaction-policy best_effort_no_rollback_v1
```

检查：

- `apply_execute.status = "ok"`
- `apply_execute.idempotency.apply_request_id = "cookbook-apply-001"`
- `apply_execute.transaction.prevalidate_before_write = true`

## 4) 验证 registry 写入

```bash
python -m factpy_kernel.authoring.cli registry-list \
  --registry-dir .tutorial_work/cookbook_apply/registry \
  --kind apply_run_ids
```

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir .tutorial_work/cookbook_apply/registry \
  --kind apply-run \
  --id cookbook-apply-001
```

## 5) 常见失败与快速处理

- DSL parser 错误：先改用 `workflow-dry-run --safe`
- `status=error`：优先看 `apply_execute.diagnostics[]`
- replay/conflict 不符合预期：查看 `idempotency.plan_digest` 与 `transaction.policy`

## 6) 关联教程

- CLI 参数细节：[`09-CLI-命令速查.md`](./09-CLI-命令速查.md)
- 事务/排障：[`06-事务策略与排障（v1/v2）.md`](./06-事务策略与排障（v1-v2）.md)
- 完整样板：[`07-完整示例项目模板（可复制运行）.md`](./07-完整示例项目模板（可复制运行）.md)
