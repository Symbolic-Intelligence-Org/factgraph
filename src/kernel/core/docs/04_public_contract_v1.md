# Public Contract v1（对外稳定约定）

- 范围：`core/service/sdk` 的 v1 外部行为约束
- 状态：`v1`
- 最后更新：2026-03-10

本文档只记录“当前代码已实现且应保持稳定”的对外契约；不记录已移除能力。

## 1. 字符串 DSL 策略（v1）

### 1.1 service / HTTP（rules v1）

入口：

- `service.rules_v1.validate_rule(...)`
- `service.rules_v1.compile_rule_preview(...)`
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

> **post-L SDK ergonomics redesign cross-ref（§5.5.6）：** 自 post-L 重设计起，`FactGraph` 作为 `SDKStore` 的字面别名进入 `kernel.sdk.__all__`,上述 contract 入口同样可通过 `FactGraph.eval.run(...)` / `FactGraph.eval.evaluate(...)` 触达;flat `SDKStore.<method>` 形式仍是 v1 contract 的 foundational anchor,既不被弃用也不会移除。详细 design 由 post-L SDK ergonomics redesign blueprint 记录(internal design record;§5.4 / §5.5)。

字符串 DSL 被显式拒绝，抛 `SDKStoreError`，稳定前缀：

- `string rule DSL is not supported in SDK v1; ...`
- `string derivation DSL is not supported in SDK v1; ...`

## 2. 声明元数据契约（v1）

### 2.1 Entity / schema

SDK 与 authoring schema DSL 当前统一的声明元数据为：

- `version`
- `description`
- `tags`

稳定口径：

- `entity_type` 由 `Entity` 类名推导，不单独要求 `schema_id`
- `Entity.Meta` 只允许 `version / description / tags`
- `description` 的优先级为：`Meta.description > 类 docstring fallback`
- compiler 会校验并保留这些字段到 schema 编译输出

### 2.2 Rule / Derivation

`Rule` / `Derivation` 当前允许的声明元数据：

- `description: str`
- `tags: list[str]`

稳定口径：

- 走 SDK 对象时，`Rule(...)` / `Derivation(...)` 使用顶层参数
- 走 authoring payload 时，使用顶层键 `description` / `tags`
- compiler 会校验并保留这些字段
- 这些字段不改变 `where` 校验、求值、candidate 生成或 accept 语义

兼容说明：

- `Derivation.target` 仍是兼容字段；高层声明推荐以 `head` 为主

## 3. Store.evaluate 模式契约（v1）

允许模式：

- `native`
- `souffle`
- `problog`

已移除别名：

- `mode='python'` -> `ValueError("mode='python' is removed; use mode='native'")`
- `mode='engine'` -> `ValueError("mode='engine' is removed; use mode='souffle'")`

若未注册对应 evaluator：

- 抛 `WhereValidationError`
- 错误消息格式：`"{mode} evaluator not registered; import kernel.adapters.{mode} first"`

## 4. AcceptResult 诊断契约（v1）

来源：

- `kernel.core.derivation.accept.AcceptResult`
- `kernel.core.store._accept.accept_store_candidate(...)`

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

## 5. accept_many 返回契约（v1）

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

## 6. ProjectorAudit 契约（v2）

来源：

- `kernel.core.view.projector.ProjectorAudit`
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

## 7. 兼容面与变更流程

当前兼容入口（保留但不建议新增依赖）：

- `kernel.core.store.api`
- `Store.evaluate_dummy(...)`（deprecated）

变更流程约束：

1. 先更新本文档中的 contract 描述。
2. 同步更新/补充回归测试。
3. 最后修改实现。
