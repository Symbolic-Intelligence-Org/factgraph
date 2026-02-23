# 教程 12：Cookbook｜排查一次失败的 Apply

本篇按“`apply-execute` 失败了，我要怎么定位”的顺序组织，优先使用现有 CLI / registry / audit 页面，不要求先懂内部实现。

## 目标

给定一次失败请求（`apply_request_id`），快速判断它属于哪类问题：

- `prevalidate_blocked`
- `runtime_partial`
- `idempotency_conflict`
- `transaction_policy` 不受支持

## 1) 先拿到失败结果 JSON

如果你刚执行过命令，先保存 stdout：

```bash
python -m factpy_kernel.authoring.cli apply-execute ... > /tmp/apply_failed.json
cat /tmp/apply_failed.json
```

优先看这些字段：

- `apply_execute.status`
- `apply_execute.transaction.failure_phase`
- `apply_execute.transaction.prevalidate_status`
- `apply_execute.transaction.partial_apply`
- `apply_execute.diagnostics[]`

## 2) 用 registry 查看同一次 apply（如果已写入 run event）

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir /path/to/registry \
  --kind apply-run \
  --id <apply_request_id>
```

重点看：

- `item.status`
- `item.idempotency`
- `item.transaction`

> 注意：某些 prevalidate 阻塞/不支持策略路径不会追加 apply events，这是当前 v1/v2 契约的一部分。

## 3) 判断失败类型（最短规则）

### A. `failure_phase = "prevalidate"`

通常表示：

- 输入 payload/DSL 编译后的内容在 prevalidate 阶段被阻塞
- 或 `transaction_policy` 不支持

下一步：

- 看 `diagnostics[0].code`
- 看 `diagnostics[0].path`
- 如果是 DSL 输入，建议先跑：

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl /path/to/schema.py \
  --safe
```

### B. `failure_phase = "write"`

通常表示：

- registry 写入过程中发生异常（runtime write failure）

下一步：

- 看 `partial_apply`
- 看 `diagnostics_summary` / `diagnostics`
- 看 authoring apply events（如果有）

### C. `status="error"` + `prevalidate_status="skipped_transaction_policy_unsupported"`

表示：

- 传入了未支持的 `--transaction-policy`

下一步：

- 改用 `best_effort_no_rollback_v1` 或 `prevalidate_no_partial_strict_v2`

### D. `status="error"` + idempotency conflict

常见原因：

- 相同 `apply_request_id + plan_digest`，但 `transaction_policy` 不一致

下一步：

- 统一 `--transaction-policy` 或换新的 `apply_request_id`

## 4) 使用 audit static UI 查看失败路径（推荐）

如果你已生成审计站点，并且导入了 `authoring_apply_events.jsonl`：

- 打开：`authoring_apply_events.html`
- 再打开：`authoring_apply_runs/<apply_request_id>.html`

重点看：

- `execution_path`
- `execution_path_label`
- `failure_summary`
- `action_stats`

其中常见 `execution_path`：

- `prevalidate_blocked`
- `runtime_partial`
- `idempotency_conflict`
- `replay`

## 5) 最小排障清单（复制使用）

```text
[Apply Failure Triage]
1. 记录 apply_request_id
2. 看 apply_execute.status / transaction.failure_phase
3. 看 diagnostics[0].code / path
4. 如果有 registry：registry-show --kind apply-run
5. 如果有 audit_site：authoring_apply_runs/<req>.html
6. 判断是否为 replay/conflict/prevalidate/runtime_partial
```

## 6) 关联教程

- CLI 参数与命令：[`09-CLI-命令速查.md`](./09-CLI-命令速查.md)
- 事务策略背景：[`06-事务策略与排障（v1/v2）.md`](./06-事务策略与排障（v1-v2）.md)
- 系统化排障矩阵：[`10-排障手册（CLI-Registry-Audit）.md`](./10-排障手册（CLI-Registry-Audit）.md)

