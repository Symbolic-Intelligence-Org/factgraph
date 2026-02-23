# 教程 3：Apply Execute 与 Registry（真实写入）

本教程把 dry-run 变成真实执行：将 Authoring 结果写入 file registry，并说明幂等与事务策略参数。

## 1. 准备输入（沿用教程 2 的 schema）

确保存在：

- `/.tutorial_work/authoring_schema.json`（JSON 路径）或
- `/.tutorial_work/schema.py`（DSL 路径）

本教程用 DSL 示例。

## 2. 首次执行 apply-execute

```bash
cd /Users/zhenzhili/symbolic_agent
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl .tutorial_work/schema.py \
  --registry-dir .tutorial_work/registry \
  --apply-request-id tutorial-req-001
```

预期效果：

- 返回 `authoring_publish_workflow_apply_bundle_dto_v1`
- `apply_execute.status = "ok"`
- 创建 registry 文件：
  - `.tutorial_work/registry/registry_manifest.json`
  - `.tutorial_work/registry/authoring_apply_events.jsonl`

建议额外检查这些字段（后续教程会反复用到）：

- `apply_execute.idempotency.apply_request_id`
- `apply_execute.idempotency.plan_digest`
- `apply_execute.transaction.policy`
- `apply_execute.transaction.prevalidate_before_write`

## 3. 幂等重放（replay）

同一个 `apply_request_id` + 同一计划内容（`plan_digest` 相同）再次执行，会 replay：

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl .tutorial_work/schema.py \
  --registry-dir .tutorial_work/registry \
  --apply-request-id tutorial-req-001
```

观察输出中的：

- `apply_execute.idempotency`
- `apply_execute.transaction`

> 设计目标：重复请求可稳定返回，不重复执行写入。

### 3.1 幂等冲突示例（同 request_id + 同 plan_digest，但策略不同）

复用同一个 `apply_request_id`，但切换事务策略，会触发 conflict（不会 replay）：

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl .tutorial_work/schema.py \
  --registry-dir .tutorial_work/registry \
  --apply-request-id tutorial-req-001 \
  --transaction-policy prevalidate_no_partial_strict_v2
```

重点查看：

- `apply_execute.status`
- `apply_execute.idempotency`
- `apply_execute.diagnostics[0].path`

## 4. 事务策略参数（v1 / v2）

### 显式使用 v1（默认值）

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl .tutorial_work/schema.py \
  --registry-dir .tutorial_work/registry \
  --apply-request-id tutorial-req-v1 \
  --transaction-policy best_effort_no_rollback_v1
```

### 使用 v2（当前为最小可执行版）

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl .tutorial_work/schema.py \
  --registry-dir .tutorial_work/registry \
  --apply-request-id tutorial-req-v2 \
  --transaction-policy prevalidate_no_partial_strict_v2
```

请检查输出：

- `apply_execute.transaction.policy`
- `apply_execute.transaction.prevalidate_before_write`
- `apply_execute.transaction.prevalidate_status`
- `apply_execute.transaction.failure_phase`
- `apply_execute.transaction.partial_apply`

> 注意：`v2` 当前是最小可执行版，不等于完整 rollback/compensation 事务（详见教程 6）。

## 5. 未知事务策略（结构化错误）

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl .tutorial_work/schema.py \
  --registry-dir .tutorial_work/registry \
  --transaction-policy unknown_policy_x
```

预期：

- CLI 仍返回 JSON（不是崩溃）
- `apply_execute.status = "error"`
- `transaction.prevalidate_status = "skipped_transaction_policy_unsupported"`
- 不写 registry / 不追加 apply events

## 6. 与 `--safe` 的关系

- `preflight` / `workflow-dry-run` 支持 `--safe`（仅 DSL 输入）
- `apply-execute` **不支持** `--safe`

如果你要先收集 DSL 解析错误，请先运行：

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl .tutorial_work/schema.py \
  --safe
```

## 7. （为教程 4 准备）把 rule / derivation 一并写入 registry

如果你希望教程 4 的 `rule` / `derivation` 查询能返回数据，请先准备教程 2 的 `rule.py` / `derivation.py`，然后执行：

```bash
python -m factpy_kernel.authoring.cli apply-execute \
  --schema-dsl .tutorial_work/schema.py \
  --rule-dsl .tutorial_work/rule.py \
  --derivation-dsl .tutorial_work/derivation.py \
  --registry-dir .tutorial_work/registry \
  --apply-request-id tutorial-req-with-rule-derivation
```

这样 registry 中会同时包含：

- schema entry
- rule versions
- derivation versions
- apply run events

下一步：继续看 [`04-Registry-只读查看与运维命令.md`](./04-Registry-只读查看与运维命令.md)
