# Public Contract v1（对外稳定约定）

- 范围：`core/service/sdk` 的 v1 外部行为约定（中文优先）
- 状态：`v1`（当前用于约束 SDK/API thin-slice）
- 最后更新：2026-02-28

本文档的目标是把“对外 contract”从口头共识变成**可测试事实**。实现与回归测试应同时维护。

## 1. 字符串 DSL 策略（v1）

### 1.1 总策略（v1）

- **默认不支持字符串 DSL**（规则/派生式字符串表达式）
- v1 对外入口以 **对象 DSL / 结构化 IR（dict/list/tuple）** 为主
- 原因：避免字符串 parser 能力不一致把已收口的 core 语义风险重新引入接口层

### 1.2 service / HTTP（rules v1）

适用入口：

- `factpy_kernel.service.rules_v1.validate_rule(...)`
- `factpy_kernel.service.rules_v1.compile_rule_preview(...)`
- `src/factpy_kernel/service/app_v1.py` 的 `/v1/rules/*` 路由（透传 `service.rules_v1`）

若检测到字符串 DSL，返回错误 envelope（`ok=false`）并使用稳定 `kind`：

- `errors[*].kind = "string_dsl_unsupported"`

当前覆盖路径：

- `$.rule`（整个 rule 是字符串）
- `$.rule.where`（where 字段是字符串）

### 1.3 SDK（Python）

适用入口：

- `SDKStore.run(...)`
- `SDKStore.evaluate(...)`

字符串 DSL 在 SDK v1 中显式拒绝，抛出 `SDKStoreError`（稳定 message 前缀）：

- `string rule DSL is not supported in SDK v1; ...`
- `string derivation DSL is not supported in SDK v1; ...`

说明：SDK 目前不是统一 diagnostics envelope；因此字符串 DSL 策略在 SDK 层以 **异常消息契约** 体现。

## 2. `AcceptResult` 诊断 contract（v1）

来源：

- `factpy_kernel.core.derivation.accept.AcceptResult`
- `factpy_kernel.core.store._accept.accept_store_candidate(...)`

### 2.1 版本字段（稳定）

- `AcceptResult.diagnostics_contract_version == 1`

### 2.2 `DiagItem` 形状（稳定）

`AcceptResult.diagnostics` 中每项均为对象，包含字段：

- `code: str`
- `severity: "info" | "warning" | "error"`
- `path: str | None`
- `message: str`
- `data: dict[str, Any]`

### 2.3 关键 code（v1 已使用）

接受元数据 digest（store 层）：

- `accept_meta_schema_digest_unavailable`
- `accept_meta_policy_digest_unavailable`

record staging / 冲突 / 恢复（accept + record_staging）：

- `RECORD_REJECT_ABORTED`
- `RECORD_COMMITTED_DIGEST_CONFLICT`
- `RECORD_MARKER_CONFLICT_COMMITTED_AND_ABORTED`
- `RECORD_MARKER_CONFLICT_MULTI_COMMITTED`
- `RECORD_MARKER_CONFLICT_MULTI_ABORTED`
- `RECORD_MARKER_CONFLICT_COMMITTED_AND_INFLIGHT_MISMATCH`
- `RECORD_MARKER_CONFLICT_ROLES_COUNT_EXPECTED_MISMATCH`
- `ACCEPT_RECORD_RECOVERED_PARTIAL`

说明：

- 允许新增 code，但已有 code 的语义不应在 v1 内静默改变。
- 若新增字段或破坏性变更，需要 bump `diagnostics_contract_version`。

## 3. `ProjectorAudit` contract（v1）

来源：

- `factpy_kernel.core.view.projector.ProjectorAudit`
- `project_view_facts_with_audit(...) -> (facts, ProjectorAudit)`

### 3.1 版本字段（稳定）

- `ProjectorAudit.contract_version == 1`

### 3.2 字段与语义（当前）

- `legacy_record_total`
- `legacy_record_by_pred`
- `legacy_exists_without_roles_total`
- `legacy_exists_without_roles_by_pred`
- `marker_conflict_total`
- `marker_conflict_by_reason`
- `committed_hidden_count_mismatch_total`
- `committed_hidden_count_mismatch_by_pred`

### 3.3 计数口径（稳定约定）

- 以 **record 组** 为计数单位（不是 claim 行）
- `legacy_record_*` 以 `exists` claim 为计数单位（无 `record_digest` 的 legacy record）
- `marker_conflict_*` 按 `record_staging` resolver 的 `reason` 聚合
- `committed_hidden_count_mismatch_*` 仅统计 “committed 且 `roles_count_expected` 存在但不匹配” 导致的隐藏

### 3.4 审计不变式（测试锁定）

- `legacy_record_total == sum(legacy_record_by_pred.values())`
- `marker_conflict_total == sum(marker_conflict_by_reason.values())`
- `committed_hidden_count_mismatch_total == sum(committed_hidden_count_mismatch_by_pred.values())`

## 4. `legacy_record_visibility` 参数语义（v1）

适用入口：

- `project_view_facts(...)`
- `project_view_facts_with_audit(...)`

取值：

- `allow`（默认）：legacy record 可见（保持兼容）
- `audit`：与 `allow` **结果集一致**，仅用于显式观测模式
- `deny`：仅隐藏 legacy record 组（不影响非 record materialize）

## 5. 对应回归测试（必须随 contract 维护）

- `src/factpy_kernel/tests/test_public_contract_v1.py`
- `src/factpy_kernel/tests/test_view_projector_audit_v1.py`

约束：

- 修改对外字段/错误格式前，必须先更新本文档与回归测试，再改实现。
