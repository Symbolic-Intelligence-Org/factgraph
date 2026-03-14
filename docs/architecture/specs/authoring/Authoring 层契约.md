---
doc_type: spec
status: partial
source_of_truth: design
implementation_state: partial
owner: authoring
last_verified: 2026-03-14
---

> Partial status: 本文定义 authoring 到 canonical IR 的目标契约，但部分 authoring/runtime 细节仍需结合当前实现文档复核。

# Authoring 层契约（Authoring Contract v1）

目标：在 **不绑定具体 DSL 语法**（Python/YAML/UI 表单均可）的前提下，锁定 Authoring 层概念与当前项目 canonical 契约（SchemaIR / Rule / Derivation / Export/Runner）的映射关系，避免后续 parser/UI 先行导致语义分叉。

本文件是 **Authoring 输入层 → Canonical IR** 的规范；执行层权威语义仍以以下文档为准：

- `/Users/zhenzhili/symbolic_agent/docs/architecture/specs/schema/规范.md`（SchemaIR、PredId、IdentityPolicy、group_key_indexes）
- `/Users/zhenzhili/symbolic_agent/docs/architecture/specs/core/断言层 证据层.md`（claim/claim_arg、写入协议、append-only）
- `/Users/zhenzhili/symbolic_agent/docs/architecture/specs/core/视图层.md`（active/chosen、functional/multi/temporal view）
- `/Users/zhenzhili/symbolic_agent/docs/history/design-evolution/规则.md`（Rule/Derivation、CandidateSet、accept）
- `/Users/zhenzhili/symbolic_agent/docs/architecture/specs/runtime/导出与运行.md`（Exporter/Runner、outputs_map）

---

## 1. 范围与非目标（v1）

### 1.0 Python 模块入口（当前实现）

为减少外部调用方直接耦合到底层叶子文件，当前 `factpy_kernel.authoring` 推荐按 4 个高层模块进入：

- `factpy_kernel.authoring.schemas`：schema parse / compile / preflight
- `factpy_kernel.authoring.rules`：rule parse / compile / preflight
- `factpy_kernel.authoring.derivations`：derivation parse / compile / preview
- `factpy_kernel.authoring.registry_workflow`：registry backend、session、publish/workflow/apply、DSL bridge

旧的 `schema_compile.py` / `rule_compile.py` / `preflight.py` / `dsl_bridge.py` / `workflow.py` 等叶子模块仍保留兼容，但不再建议作为新的跨层依赖入口。

### 1.1 本文件覆盖

- Authoring 概念项（Entity / Identity / Field / Rule 意图）的 canonical 映射
- 命名口径（`pred_id` vs `display_name` / `aliases`）
- `fact_key` 与 `group_key_indexes` 的对应关系
- 逻辑语义与物理实现边界（append-only）
- reification 的触发条件与产物要求
- 面向 Authoring preflight / DTO / session DTO 的诊断码建议

### 1.2 本文件不覆盖

- 具体 Python DSL 语法/元类实现
- UI 页面/交互组件实现
- Rule DSL 全量语法细节（以 `/规则.md` 为准）
- 运行时引擎能力扩展（以 Exporter/Runner 文档为准）

---

## 2. 核心原则（Authoring → Canonical）

1. **Authoring 只是意图层**：输入语法不是执行权威；最终以 SchemaIR / Rule 规范为准。
2. **Identity ≠ fact_key**：身份只用于 EntityRef；`fact_key` 只用于字段事实唯一性分组。
3. **逻辑更新 ≠ 物理覆盖**：`functional` 的“替换”是逻辑语义；物理实现必须 append-only（claim/revokes + policy/view）。
4. **Canonical 名称唯一**：执行层只认 canonical `pred_id`；展示名与 alias 不参与写入、冲突组、导出。
5. **n-ary 是一级能力**：reify 由语义需求驱动，而不是因为底层只能二元。

---

## 3. Authoring 概念到 Canonical IR 的映射（硬约束）

### 3.1 `Entity`

Authoring 中的实体声明（类、表单、YAML 节点等）编译为 SchemaIR 的：

- `entity_type`
- `identity_fields`（有序）
- 可选 metadata（owner/security/docstring 等）
- 若存在 reified relation 配置，则生成对应 projection 信息（见 `/规范.md` 的 reify 与 projection 章节）

硬约束：

- `entity_type` 是 canonical 类型名；后续 `EntityRef` 的 `idref_v1:<entity_type>:...` 必须使用该值。
- Authoring 层不得在运行时按数据内容动态改变 `entity_type`。

### 3.2 `Identity(...)`

Authoring 中标记为身份字段的项，编译为 SchemaIR `identity_fields` 的元素。

映射要求：

- 保留声明顺序（order-sensitive）
- 编译时确定 `type_domain`
- 若有默认值策略（如 `default_factory=uuid4`），仅作为 **authoring/write-time policy metadata**；真正写入后仍需按 canonical identity value 落地并参与 `idref_v1`

硬约束：

- Identity 字段 **不得**同时参与字段事实的 `fact_key` 定义（除非它本身是某个 Field 的 value/dim，且按 Field 语义单独声明）
- Identity 字段不直接生成业务谓词 claim（除非额外被声明为 Field）

### 3.3 `Field(...)`

Authoring 中字段声明编译为 SchemaIR `predicates[]` 的一项（或 reify 展开规则的输入）。

至少映射：

- canonical `pred_id`
- `arg_specs`
- `cardinality`
- `group_key_indexes`
- 可选 metadata（`display_name`, `aliases`, `description`, owner metadata）

硬约束：

- Field 不参与 EntityRef 生成（除非同名字段另行声明为 Identity；v1 不推荐这种重叠设计）
- `cardinality` 只能是 `functional|multi|temporal`
- `type_domain` 必须映射到已锁死 Tag 枚举（`entity_ref|string|int|float64|bool|bytes|time|uuid`）

### 3.4 `Field.fact_key`（Authoring 名） → `SchemaIR.group_key_indexes`（Canonical 名）

这是 v1 的关键收口点。

- Authoring 层可用 **`fact_key`** 表达“functional 的唯一性分组维度”（更贴业务语义）
- Canonical SchemaIR 层统一落成 **`group_key_indexes`**

编译规则（硬约束）：

1. 先确定业务谓词参数序列：`[E] + dims + [value]`（见 `/规范.md`）
2. `fact_key` 默认为 `{E}`（即只含主实体）
3. 若声明额外维度（如 `lang` / `source` / `address_type`），这些维度必须是参数序列中的 dims 子集
4. 编译为 `group_key_indexes` 时：
   - 必须包含 `0`（subject / E）
   - 必须包含所有 `fact_key` 对应 dims 的参数位置
   - 必须 **不包含** value 位置
5. `group_key_indexes` 必须升序、0-based、范围合法

语义等价：

- Authoring `fact_key` 是业务建模表达
- SchemaIR `group_key_indexes` 是执行/冲突组/chosen 的 canonical 表达

### 3.5 `Field.name` / `display_name` / `aliases`

为避免当前项目语义分叉，v1 建议在 Authoring 层拆分三类名字：

- `pred_id`（canonical，执行层唯一权威）
- `display_name`（展示名，仅 UI/文档）
- `aliases[]`（兼容旧名/导入映射）

兼容策略（Authoring 输入可支持语法糖）：

- 若 Authoring 提供 `Field(name="has_age")`，v1 将其解释为 **PredId override 的局部字段名片段**，并编译为 canonical `pred_id="<owner>:has_age"`
- 同时建议编译器内部生成显式 metadata：
  - `display_name`（若有）
  - `aliases`（若有）

硬约束：

- claim/view/export/where 执行统一使用 canonical `pred_id`
- `aliases` 只用于 authoring/import 解析映射，不进入冲突组 key，不进入 `EntityRef`

---

## 4. 基数语义（逻辑）与写入语义（物理）的边界

### 4.1 `functional`

逻辑语义：

- 同一 key 组（由 `group_key_indexes` 决定）下最多一个 current value

物理实现（硬约束）：

- 不能就地覆盖历史记录
- 必须通过 append-only 写入 claim/meta（必要时追加 `revokes/2`）并由 active/chosen 推导 current

### 4.2 `multi`

逻辑语义：

- 同一 key 组下允许多个 value 并存

物理实现：

- append-only 写入；删除/撤销仍走统一 revokes 模型

### 4.3 `temporal`

逻辑语义：

- 历史只追加；`record` 输出保留 active 历史；`current` 由 view/policy 规则推导

物理实现：

- 禁止物理覆盖历史
- `current` 不是写入协议行为，而是视图/导出/runner 输出行为（当前项目已通过 `outputs_map` 承载双输出）

---

## 5. Reification（关系实体化）契约（v1）

### 5.1 何时必须 reify（Authoring 语义判断）

以下情形应优先 reify：

- 关系本身需要身份/生命周期（可独立被引用、审计、撤销）
- 关系需要挂属性（例如 `since/title/source/confidence`）
- 需要把同一关系实例作为多个规则/决策的主语对象

### 5.2 reify 的 canonical 产物（SchemaIR / 写入侧必须可用）

Authoring 层若声明 reified relation / relation-entity，SchemaCompiler 必须在 SchemaIR 中生成：

- record entity type（例如 `Employment`）
- `<T>:exists`（record existence predicate）
- 角色谓词（role predicates，如 `employment:employee`, `employment:employer`）
- 属性谓词（如 `employment:since`, `employment:title`）
- （若允许 fact materialize）projection 信息：`projection_pred_id`, `projection_arg_order`

硬约束：

- accept 写回与 FactCompiler 必须复用同一组 canonical 谓词名；禁止重复发明

---

## 6. Rule / Derivation 的 Authoring 契约边界（v1）

Authoring 层可表达规则/推导意图，但 canonical 执行契约仍由 `RuleSpec` / where DSL / CandidateSet 决定。

建议收口：

- Authoring Rule 的 where/constraint 语义最终编译为当前 where DSL 子集（`pred/eq/in/cmp/not` 等）
- 蓝图风格 where 语法（`with vars()`, `RecordType(r)`, `r.field == x`）在 v1 已支持**最小子集**：
  - parser 负责语法形状解析（record constructor + path `==`）
  - compile/preflight 在有 `SchemaIR` 时会做 **schema-aware lowering**，把 sugar 原子映射到真实 record exists/role `pred_id`（不依赖命名约定）
  - 当前子集边界：仅支持 record constructor 与 path `==`；更复杂 PathExpr/运算仍未实装
- `temporal_view` 必须显式选择（默认 `record`）
- Authoring 层若选择 `temporal_view="current"`，但 where 未引用 temporal 谓词，应允许 preflight 给出 warning（当前已实现）
- Derivation 的当前最小 Authoring 执行入口（已实装）为 `target_pred_id/target` + `head_vars`（`select` 仅兼容别名）
- `head_vars` 必须按目标谓词 `target_pred_id` 的 `arg_specs` **位置顺序**逐位对应；`arg0` 为实体槽位，必须绑定一个可解码为 `entity_ref` 的值（变量名不要求固定为 `"$E"`）
- `target_pred_id` 指向 GNF 业务谓词目标（fact target），不是实体字段平铺结构
- 蓝图中的用户友好 `head=...` 已在 v2 成为主路径：
  - `head=Person.field(...)`：fact candidate 路径（schema-aware lowering → `target_pred_id + head_vars`）
  - `head=EntityType(...)`：entity candidate 路径（拆分为 `entity + dependent facts`）
  - `materialize_as` / `id_policy` 已从用户语法移除
- 仍未完全对齐蓝图的部分（后续补齐）：
  - keyed head 的更完整执行模型（当前内部仍会 lowering 为 position-based `head_vars`）

推荐实践（v1 当前阶段）：

- 新示例默认使用 `head`；把 `target + head_vars/select` 视为兼容输入。
- 若需要排查 canonical payload/执行映射，再显式查看 lowering 后的 `target_pred_id + head_vars`。

---

## 7. Authoring Diagnostics / Warnings 契约（对齐现有 preflight/DTO）

### 7.1 现有已落地（可复用）

`authoring_preflight_v1` / `authoring_ui_dto_v1` 当前已支持：

- 结构化 `diagnostics[]`: `phase/code/path/message/severity`
- `warnings[]`
- session 级聚合（`authoring_session_dto_v1`）
- 代码侧 canonical diagnostics registry（code + phase，`factpy_kernel/authoring/diagnostic_codes.py`）作为实现与测试的唯一基准

Canonical diagnostics `code` 列表（v1，已实装）：

- `authoring_schema_compile_error`
- `authoring_schema_dsl_parse_error`
- `schema_validation_error`
- `empty_predicates`
- `registry_rule_error`
- `rule_spec_error`
- `rule_compile_error`
- `authoring_rule_compile_error`
- `authoring_rule_dsl_parse_error`
- `derivation_preview_error`
- `authoring_derivation_compile_error`
- `authoring_derivation_dsl_parse_error`
- `publish_blocked_section_error`
- `publish_blocked_missing_or_invalid_section`
- `apply_blocked_action`
- `apply_blocked_actions_present`
- `apply_prevalidate_blocked_action`
- `apply_prevalidate_blocked_actions_present`
- `preview_truncated`
- `souffle_binary_missing`
- `temporal_current_no_pred_refs`
- `temporal_current_no_temporal_schema_predicates`
- `temporal_current_no_temporal_where_predicates`
- `publish_skipped_unsupported_section`
- `apply_skipped_action`
- `apply_skipped_actions_present`

Canonical diagnostics `phase` 列表（v1，已实装）：

- `schema.authoring_compile`
- `schema.dsl_parse`
- `schema.validate`
- `schema.preflight`
- `rule.dsl_parse`
- `rule.registry`
- `rule.parse`
- `rule.preflight`
- `rule.compile`
- `rule.authoring_compile`
- `derivation.preview.env`
- `derivation.preview`
- `derivation.authoring_compile`
- `derivation.dsl_parse`
- `publish.plan`
- `publish.apply`

Canonical `diagnostics_contract` 片段（嵌入 `authoring_ui_dto_v1` / `authoring_session_dto_v1` 顶层，v1，已实装）：

```json
{
  "diagnostics_contract": {
    "diagnostics_contract_version": "authoring_diagnostics_contract_v1",
    "codes": [
      "authoring_schema_compile_error",
      "authoring_schema_dsl_parse_error",
      "schema_validation_error",
      "registry_rule_error",
      "rule_spec_error",
      "rule_compile_error",
      "authoring_rule_compile_error",
      "authoring_rule_dsl_parse_error",
      "derivation_preview_error",
      "authoring_derivation_compile_error",
      "authoring_derivation_dsl_parse_error",
      "publish_blocked_section_error",
      "publish_blocked_missing_or_invalid_section",
      "apply_blocked_action",
      "apply_blocked_actions_present",
      "apply_prevalidate_blocked_action",
      "apply_prevalidate_blocked_actions_present",
      "empty_predicates",
      "preview_truncated",
      "souffle_binary_missing",
      "temporal_current_no_pred_refs",
      "temporal_current_no_temporal_schema_predicates",
      "temporal_current_no_temporal_where_predicates",
      "publish_skipped_unsupported_section",
      "apply_skipped_action",
      "apply_skipped_actions_present"
    ],
    "phases": [
      "schema.authoring_compile",
      "schema.dsl_parse",
      "schema.validate",
      "schema.preflight",
      "rule.dsl_parse",
      "rule.registry",
      "rule.parse",
      "rule.preflight",
      "rule.compile",
      "rule.authoring_compile",
      "derivation.preview.env",
      "derivation.preview",
      "derivation.authoring_compile",
      "derivation.dsl_parse",
      "publish.plan",
      "publish.apply"
    ]
  }
}
```

Canonical `authoring_publish_plan_dto_v1` 片段（dry-run only，最小必备字段，v1，已实装）：

```json
{
  "authoring_publish_plan_dto_version": "authoring_publish_plan_dto_v1",
  "kind": "authoring_publish_plan",
  "mode": "dry_run_only",
  "status": "warning",
  "summary": {
    "action_count": 1,
    "planned_count": 1,
    "blocked_count": 0,
    "skipped_count": 0
  }
}
```

Canonical `authoring_apply_result_dto_v1` 片段（dry-run only，最小必备字段，v1，已实装）：

```json
{
  "authoring_apply_result_dto_version": "authoring_apply_result_dto_v1",
  "kind": "authoring_apply_result",
  "mode": "dry_run_only",
  "status": "warning",
  "summary": {
    "action_count": 1,
    "would_apply_count": 1,
    "blocked_count": 0,
    "skipped_count": 0
  }
}
```

Canonical `authoring_publish_workflow_bundle_dto_v1` 片段（dry-run only，session→plan→apply 聚合，v1，已实装）：

```json
{
  "authoring_publish_workflow_bundle_dto_version": "authoring_publish_workflow_bundle_dto_v1",
  "kind": "authoring_publish_workflow_bundle",
  "mode": "dry_run_only",
  "status": "warning",
  "summary": {
    "session_status": "warning",
    "publish_plan_status": "warning",
    "apply_result_status": "warning"
  }
}
```

Canonical `authoring_apply_execute_result_dto_v1` 片段（apply execute，最小必备字段，v1，已实装）：

```json
{
  "authoring_apply_execute_result_dto_version": "authoring_apply_execute_result_dto_v1",
  "kind": "authoring_apply_execute_result",
  "mode": "apply_execute_v1",
  "status": "warning",
  "idempotency": {
    "apply_request_id": "req-123",
    "plan_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "replayed": false
  },
  "transaction": {
    "policy": "best_effort_no_rollback_v1",
    "rollback_supported": false,
    "rollback_attempted": false,
    "prevalidate_before_write": true,
    "prevalidate_status": "passed",
    "writes_started": true,
    "failure_phase": "none",
    "partial_apply": false
  },
  "summary": {
    "action_count": 2,
    "applied_count": 1,
    "noop_count": 1,
    "blocked_count": 0,
    "skipped_count": 0
  }
}
```

硬约束（已实装）：

- 相同 `apply_request_id` 若命中已记录 run event 且 `plan_digest` 相同，则返回 replay（`idempotency.replayed=true`），不得重复执行 action。
- 相同 `apply_request_id` 若 `plan_digest` 不同，则返回 `status="error"`（`$.idempotency.apply_request_id` 诊断），不得执行 action。
- `authoring_apply_execute_run` event 必须记录 `apply_request_id` 与 `plan_digest`，并应携带 `idempotency` 与 `transaction` 摘要；`authoring_apply_execute_action` event 必须记录 `apply_request_id` 以便 audit 聚合。
- runtime 写入失败导致 action blocked 时，仍必须追加 `authoring_apply_execute_action(status="blocked")` event（含 `reason_code`、`diagnostics_summary` 与 `diagnostics`）；prevalidate 阻塞 / replay / idempotency conflict 不追加新 events（v1，已实装）。
- event 追加顺序（v1，已实装）：同一 `apply_request_id` 下先写全部 `authoring_apply_execute_action` events，最后写单条 `authoring_apply_execute_run` event。
- `apply_execute_v1` 在执行前必须执行 prevalidate（`transaction.prevalidate_before_write=true`）；若 prevalidate 阻塞，则不得执行任何 write action（`transaction.partial_apply=false`，且可返回 prevalidate 诊断）。
- `apply_execute_v1` 事务语义为 `best_effort_no_rollback_v1`：不提供回滚；仅当 prevalidate 通过后执行阶段发生写入失败时，若前序 action 已写入而后续 action 阻塞，必须显式返回 `transaction.partial_apply=true`。
- `transaction.rollback_attempted`（v1）必须恒为 `false`；`transaction.failure_phase` 仅允许 `none|idempotency_conflict|prevalidate|write`。

事务语义 v2（最小实现 + 扩展预留）：

- 候选策略名：`prevalidate_no_partial_strict_v2`
- 已实现输入位：`apply_execute_options.transaction_policy`（未指定时仍默认 v1，不得改变当前默认行为）
- 目标语义：在进入 write 阶段前完成全部 prevalidate；一旦进入 write 阶段，要求所有 action 都必须可执行，否则整次 apply 拒绝（不允许 `partial_apply=true`）
- 与 v1 的关系：v1 继续保留为 `best_effort_no_rollback_v1`；v2 为显式 opt-in，不得 silent 升级替换 v1
- 与 v1 的兼容项（已实现）：`apply_request_id`/`plan_digest` 幂等与 replay/conflict 判定规则保持不变；若相同 `apply_request_id` 但 `transaction_policy` 不同，必须返回 conflict（不得 replay）
- v2 当前最小实现（已实装）：复用 v1 的 prevalidate + 执行路径，并在结果中显式标记 `transaction.policy="prevalidate_no_partial_strict_v2"`
- v2 当前限制（已实装）：尚未提供 rollback/compensation；若执行阶段发生不可预期 runtime 写失败且已产生前序写入，仍可能出现 `partial_apply=true`，必须返回 error 并附带 v2 strict violation 诊断细节（实现级细节，后续可升级为专用 code）
- v2 硬约束（当前最小实现仍满足）：prevalidate 阻塞必须返回 `transaction.failure_phase="prevalidate"`、`transaction.writes_started=false`、`transaction.partial_apply=false`
- rollback/compensation 仍未承诺；若未来引入，需要新增事务策略名与 diagnostics code/phase，并更新本节 canonical 片段
- v2 建议预留 diagnostics code（当前最小实现尚未使用，仍不在 canonical `code` 列表中）：
  - `apply_v2_prevalidate_blocked_actions_present`
  - `apply_v2_partial_apply_forbidden`
  - `apply_v2_transaction_policy_unsupported`
- v2 建议继续复用 `phase="publish.apply"`；若新增 phase（如 `publish.apply.v2`），需先 bump `authoring_diagnostics_contract` 并更新 canonical `diagnostics_contract` 片段
- v2 专用预留 codes 仍为 spec-only：在引入对应专用诊断前不得把上述预留 codes 加入 canonical `code` 列表，避免 UI/客户端误判为已实装能力

Canonical `authoring_publish_workflow_apply_bundle_dto_v1` 片段（session→plan→apply dry-run→apply execute 聚合，v1，已实装）：

```json
{
  "authoring_publish_workflow_apply_bundle_dto_version": "authoring_publish_workflow_apply_bundle_dto_v1",
  "kind": "authoring_publish_workflow_apply_bundle",
  "mode": "apply_execute_v1",
  "status": "warning",
  "summary": {
    "session_status": "warning",
    "publish_plan_status": "warning",
    "apply_dry_run_status": "warning",
    "apply_execute_status": "warning",
    "apply_execute_partial_apply": false
  }
}
```

CLI 集成（v1，已实装）：

- `factpy_kernel.authoring.cli` 提供 `preflight` / `workflow-dry-run` / `apply-execute`
- `factpy_kernel.authoring.cli` 提供 `registry-list` / `registry-show` 只读入口（registry fs backend）
- 支持 JSON payload 输入（`--authoring-schema` / `--rule-request` / `--derivation-request`）
- 支持 DSL 文件输入（`--schema-dsl` / `--rule-dsl` / `--derivation-dsl`）
- `--safe` 当前仅用于 DSL 输入的 `preflight` / `workflow-dry-run`（parser 错误落 canonical diagnostics；`apply-execute` 不支持 `--safe`）
- `apply-execute` 输出 `authoring_publish_workflow_apply_bundle_dto_v1`，其中 `apply_execute.transaction.prevalidate_before_write` 必须为 `true`（v1，已实装）
- `apply-execute` 支持 `--transaction-policy`；当前 `best_effort_no_rollback_v1` 与 `prevalidate_no_partial_strict_v2` 可执行，其他未知值必须返回结构化错误（不写 registry、不追加 apply events）
- `registry-list` / `registry-show` 输出只读 JSON（不执行写入）；`registry-show rule|derivation` 需给 `--latest` 或 `--version`
- `registry-list --kind apply_run_ids` 返回按 `apply_request_id` 排序的 run event 请求 id 列表（每个请求仅最近一次 run event）
- `registry-show --kind apply-run --id <apply_request_id>` 可读取最近一次匹配的 `authoring_apply_execute_run` event（只读）

现有 warning/code 示例（已实装）：

- `empty_predicates`
- `souffle_binary_missing`
- `temporal_current_no_pred_refs`
- `temporal_current_no_temporal_schema_predicates`
- `temporal_current_no_temporal_where_predicates`
- `preview_truncated`

### 7.2 v1 建议预留（尚未实装）

为后续 DSL/Editor 实装建议预留 code（不要求本轮实现）：

- `authoring.fact_key_invalid`
- `authoring.fact_key_refs_unknown_dim`
- `authoring.pred_id_alias_conflict`
- `authoring.identity_field_overlaps_fact_key`
- `authoring.reify_missing_role_field`
- `authoring.display_name_conflicts_alias`

建议路径口径：

- schema 概念层：`$.entities[i]...` / `$.predicates[i]...`
- authoring 输入层（DSL/表单）：`$.entity_defs[i]...` / `$.rule_defs[i]...`
- 若来自 parser，可加 `source_span`（后续版本）

---

## 8. 版本化与兼容策略（Authoring Contract v1）

- 本文件定义的是 **语义映射契约 v1**，不是具体 DSL 语法版本
- 后续新增 DSL 语法糖（例如 decorator / class syntax）只要编译结果满足本契约，不构成不兼容变更
- 以下变更视为不兼容（需 bump contract version）：
  - `fact_key -> group_key_indexes` 映射规则变化
  - `pred_id` canonical 命名口径变化
  - `functional/multi/temporal` 逻辑语义变化
  - reify canonical 产物命名规则变化

---

## 9. Golden Fixtures（引用）

本契约的示例与回归基线见：

- `/Users/zhenzhili/symbolic_agent/docs/architecture/specs/authoring/Authoring 层契约 fixtures.md`

这些 fixtures 仅用于固定语义映射与诊断/DTO 契约；**不是** DSL 实现样例代码的权威格式。
