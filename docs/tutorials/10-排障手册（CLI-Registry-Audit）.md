# 教程 10：排障手册（CLI / Registry / Audit）

本手册按“**症状 → 检查命令 → 关键字段 → 常见原因 → 下一步**”组织，适合快速定位问题。

> 默认工作目录示例：`/Users/zhenzhili/symbolic_agent/.tutorial_work/...`

## 0. 先确认你在看哪一层

排障时建议按顺序检查：

1. **CLI 输出 JSON**
2. **registry（`registry-show --kind apply-run`）**
3. **authoring apply events（`authoring_apply_events.jsonl` / audit page）**
4. **audit static UI detail 页**

这样可以减少“页面显示问题”和“执行语义问题”混在一起。

---

## 1. 症状：`apply-execute` 返回 `status=error`

### 快速检查命令

```bash
python -m factpy_kernel.authoring.cli apply-execute ... > /tmp/apply_result.json
cat /tmp/apply_result.json
```

或如果已写入 registry：

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir /path/to/registry \
  --kind apply-run \
  --id <apply_request_id>
```

### 关键字段

- `apply_execute.status`
- `apply_execute.diagnostics[]`
- `apply_execute.transaction.failure_phase`
- `apply_execute.transaction.prevalidate_status`
- `apply_execute.transaction.partial_apply`

### 常见原因

- Authoring payload/DSL 编译或 prevalidate 失败
- `transaction_policy` 不受支持
- registry 写入失败（runtime write failure）

### 下一步

- 若 `failure_phase = "prevalidate"`：优先看 `diagnostics[]`
- 若 `failure_phase = "write"`：看 `authoring_apply_events.jsonl` 中 blocked action event，或看 audit detail 页中的 `failure_summary`

---

## 2. 症状：重复执行后结果“不是 replay”

### 快速检查命令

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir /path/to/registry \
  --kind apply-run \
  --id <apply_request_id>
```

### 关键字段

- `item.idempotency.apply_request_id`
- `item.idempotency.plan_digest`
- `item.transaction.policy`
- `item.status`

### 常见原因

- 同一 `apply_request_id` 但计划内容变化（`plan_digest` 不同）
- 同一 `apply_request_id + plan_digest`，但 `transaction_policy` 变化（会 conflict，不 replay）

### 下一步

- 对比两次命令的：
  - DSL/JSON 输入
  - `--transaction-policy`
- 如果希望 replay，必须保证 request + plan + policy 都一致

---

## 3. 症状：`registry-show --kind rule/derivation` 查不到对象

### 快速检查命令

```bash
python -m factpy_kernel.authoring.cli registry-list --registry-dir /path/to/registry --kind rule_ids
python -m factpy_kernel.authoring.cli registry-list --registry-dir /path/to/registry --kind derivation_ids
```

### 关键字段

- `items`（为空表示确实未写入）

### 常见原因

- 你在 `apply-execute` 时只传了 schema，没有传 `--rule-dsl` / `--derivation-dsl`
- `rule_request` / `derivation_request` preflight 失败，未进入写入

### 下一步

- 使用教程 3 的“附加步骤”重新执行一次包含 rule/derivation 的 `apply-execute`

---

## 4. 症状：`audit_site` 有页面，但 `runs/decisions` 基本为空

### 快速检查命令

查看你生成 audit package 的脚本。

### 关键点

- 是否使用的是空 `Store(schema_ir=...)`
- 是否实际执行过 `evaluate/run/accept`

### 常见原因

- 教程示例构造的是空 store（这是故意的），只用于展示 authoring apply events 接入审计页面

### 下一步

- 如果你只关心 authoring apply 排障，这不算问题
- 如果你要看业务 run/decision，需要先运行推理链路再导出 audit package

---

## 5. 症状：`authoring_apply_runs/<req>.html` 页面找不到

### 快速检查命令

```bash
ls /path/to/audit_site/authoring_apply_runs
```

### 关键点

- audit package 中是否包含 `authoring_apply_events.jsonl`
- `render_audit_static_site(...)` 是否在复制 events 文件之后执行

### 常见原因

- 忘记把 registry 中的 `authoring_apply_events.jsonl` 复制到 audit package 根目录
- `apply-execute` 实际未成功写入 registry events

### 下一步

检查：

```bash
ls /path/to/registry/authoring_apply_events.jsonl
ls /path/to/audit_pkg/authoring_apply_events.jsonl
```

---

## 6. 症状：DSL 输入报错（尤其是 parser 结构错误）

### 快速检查命令（建议 safe）

```bash
python -m factpy_kernel.authoring.cli workflow-dry-run \
  --schema-dsl /path/to/schema.py \
  --safe
```

### 关键字段

- `sections.*.diagnostics[0].phase`（如 `schema.dsl_parse`）
- `dsl_error_kind`（`syntax|structure|input_type`）
- `path`
- `details.dsl_error_detail_code`

### 常见原因

- helper 调用参数类型错误（例如 `In("$R", "bad")`）
- 使用了不支持的 helper
- DSL 中包含不支持的关键字参数

### 下一步

- 先修 parser 错误，再运行 `preflight` 或 `workflow-dry-run`（非 safe）

---

## 7. 症状：v2 事务策略行为与“严格 no-partial”预期不一致

### 快速检查命令

```bash
python -m factpy_kernel.authoring.cli registry-show \
  --registry-dir /path/to/registry \
  --kind apply-run \
  --id <apply_request_id>
```

### 关键字段

- `item.transaction.policy`
- `item.transaction.prevalidate_before_write`
- `item.transaction.failure_phase`
- `item.transaction.partial_apply`

### 常见原因（当前版本特性）

- `prevalidate_no_partial_strict_v2` 当前是**最小可执行版**
- 未实现 rollback/compensation
- 在极端 runtime 写失败路径中，严格 no-partial 仍无法完全保证

### 下一步

- 先按 v1/v2 当前契约理解行为（参见教程 6）
- 若场景对严格事务有强要求，需要进入后续 v2+ 设计/实现阶段

---

## 8. 症状：CLI 返回错误码，但看不到 JSON stdout

### 快速检查

- 错误码 `2`：通常是 CLI 参数/调用方式错误（`AuthoringCLIError`）
- 错误码 `1`：通常是未捕获异常路径（较少见）

### 常见原因

- 参数缺失（例如 `registry-show --kind rule` 但没给 `--id`）
- 非法组合（例如 `apply-execute --safe`）

### 下一步

先运行：

```bash
python -m factpy_kernel.authoring.cli <subcommand> --help
```

再对照教程 9 的参数约束部分修正命令。

---

## 9. 执行路径速查（建议打印保存）

当你排障一次 `apply-execute` 时，建议固定记录：

- 命令（完整）
- `apply_request_id`
- `transaction_policy`
- `apply_execute.status`
- `transaction.failure_phase`
- `transaction.partial_apply`
- `diagnostics[0].code` / `path`
- `registry-show --kind apply-run` 输出片段
- `authoring_apply_runs/<req>.html` 路径

常见 `execution_path` 值（机器字段）：

- `success`
- `replay`
- `idempotency_conflict`
- `prevalidate_blocked`
- `runtime_partial`

---

## 10. 关联教程

- CLI 参数与命令组合：[`09-CLI-命令速查.md`](./09-CLI-命令速查.md)
- 事务策略背景与限制：[`06-事务策略与排障（v1/v2）.md`](./06-事务策略与排障（v1-v2）.md)
- 完整样板：[`07-完整示例项目模板（可复制运行）.md`](./07-完整示例项目模板（可复制运行）.md)
