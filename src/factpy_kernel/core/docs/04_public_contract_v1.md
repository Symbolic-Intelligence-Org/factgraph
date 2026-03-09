# Public Contract v1（对外稳定约定）

- 范围：`core/service/sdk` 的 v1 外部行为约束
- 状态：`v1`
- 最后更新：2026-03-06

本文档只记录“当前代码已实现且应保持稳定”的对外契约；不记录已移除能力。

## 1. 字符串 DSL 策略（v1）

### 1.1 service / HTTP（rules v1）

入口：

- `factpy_kernel.service.rules_v1.validate_rule(...)`
- `factpy_kernel.service.rules_v1.compile_rule_preview(...)`
- `app_v1` 下 `/v1/rules/*` 路由

若请求使用字符串 DSL，返回：

- `ok=false`
- `errors[*].kind="string_dsl_unsupported"`

当前覆盖：

- `$.rule` 为字符串
- `$.rule.where` 为字符串

### 1.2 SDK（Python）

入口：

- `SDKStore.run(...)`
- `SDKStore.evaluate(...)`

字符串 DSL 被显式拒绝，抛 `SDKStoreError`，稳定前缀：

- `string rule DSL is not supported in SDK v1; ...`
- `string derivation DSL is not supported in SDK v1; ...`

## 2. Store.evaluate 模式契约（v1）

允许模式：

- `native`
- `souffle`
- `problog`

已移除别名：

- `mode='python'` -> `ValueError("mode='python' is removed; use mode='native'")`
- `mode='engine'` -> `ValueError("mode='engine' is removed; use mode='souffle'")`

若未注册对应 evaluator：

- 抛 `WhereValidationError`
- 错误消息格式：`"{mode} evaluator not registered; import factpy_kernel.adapters.{mode} first"`

## 3. AcceptResult 诊断契约（v1）

来源：

- `factpy_kernel.core.derivation.accept.AcceptResult`
- `factpy_kernel.core.store._accept.accept_store_candidate(...)`

### 3.1 版本字段

- `AcceptResult.diagnostics_contract_version == 1`

### 3.2 AcceptResult 字段

稳定字段：

- `run_id`
- `accepted_count`
- `skipped_count`
- `written_assertions`
- `skipped_reason_counts`
- `diagnostics`
- `diagnostics_contract_version`
- `entity_ref`
- `candidate_id`
- `candidate_key`

### 3.3 `diagnostics[*]` 形状

每项为对象，字段：

- `code: str`
- `severity: "info" | "warning" | "error"`
- `path: str | None`
- `message: str`
- `data: dict[str, Any]`

### 3.4 当前稳定 code（已在 store accept 路径使用）

- `accept_meta_schema_digest_unavailable`
- `accept_meta_policy_digest_unavailable`

说明：

- 可新增 code。
- 若出现破坏性字段变更，需 bump `diagnostics_contract_version`。

## 4. accept_many 返回契约（v1）

来源：

- `Store.accept_many(...)`
- `accept_many_candidate_sets(...)`

每个返回项形状：

- `candidate_id: str`
- `candidate_key: str`
- `state: str`
- `entity_ref: str | None`
- `error: None | {code: str, message: str, diagnostics?: list[dict]}`

当前 `state` 集合（实现侧已使用）：

- `ACCEPTED`
- `DUPLICATE`
- `FAILED_VALIDATION`
- `FAILED_RUNTIME`
- `BLOCKED_DEPENDENCY`

典型 `error.code`：

- `ATOMIC_ROLLBACK`
- `ATOMIC_ABORTED`
- `BLOCKED_DEPENDENCY`
- `DUPLICATE_NOT_ALLOWED`
- 或来自异常前缀（例如 `IDENTITY_INCOMPLETE`, `INVALID_TERM`）

前置失败说明：

- `mode` 非 `atomic|best_effort` 时，当前实现直接抛 `WriteProtocolError`，不会返回逐项结果
- 候选依赖图存在环时，当前实现直接抛 `WriteProtocolError("CANDIDATE_DEPENDENCY_CYCLE: ...")`，不会返回逐项结果

## 5. ProjectorAudit 契约（v2）

来源：

- `factpy_kernel.core.view.projector.ProjectorAudit`
- `project_view_facts_with_audit(...)`

版本：

- `ProjectorAudit.contract_version == 2`

字段：

- `predicate_count: int`
- `active_claim_count: int`
- `selected_claim_count: int`
- `selected_by_pred: dict[str, int]`
- `dropped_by_policy_count: int`

说明：

- `project_view_facts(...)` 不带审计字段。
- `project_view_facts_with_audit(...)` 返回 `(facts, audit)`。
- 当前 projector 不支持 `legacy_record_visibility` 参数。

## 6. 兼容面与变更流程

当前兼容入口（保留但不建议新增依赖）：

- `factpy_kernel.core.store.api`
- `Store.evaluate_dummy(...)`（deprecated）

变更流程约束：

1. 先更新本文档中的 contract 描述。
2. 同步更新/补充回归测试。
3. 最后修改实现。
