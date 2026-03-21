# Task Blueprint: Rule Condition Weight Metadata

- Status: implemented
- Created: 2026-03-20
- Last Updated: 2026-03-20
- Related Modules:
  - `src/factpy_kernel/sdk/dsl/rule.py`
  - `src/factpy_kernel/authoring/rule_compile.py`
  - `src/factpy_kernel/authoring/preflight.py`
  - `src/factpy_kernel/authoring/registry_fs.py`
  - `src/factpy_kernel/service/rules_v1.py`
  - `src/factpy_kernel/core/rules/rule_ir.py`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/blueprints/active/2026-03-20_certainty-weight-vocabulary.md](./2026-03-20_certainty-weight-vocabulary.md)
  - [src/factpy_kernel/core/docs/01_architecture.md](../../../src/factpy_kernel/core/docs/01_architecture.md)
  - [src/factpy_kernel/authoring/docs/01_overview.md](../../../src/factpy_kernel/authoring/docs/01_overview.md)
  - [src/factpy_kernel/service/docs/04_rules_registry.md](../../../src/factpy_kernel/service/docs/04_rules_registry.md)
- Audit Log:
  - [2026-03-20_rule-condition-weight-metadata.audit.md](./2026-03-20_rule-condition-weight-metadata.audit.md)

## 1. Problem

Parent blueprint §5.2 已冻结：per-condition weight 属于 version-scoped rule metadata，不进入 `where_ast` / `RuleSpec` 逻辑执行面。

当前代码还缺少这条 contract 的稳定落点：

1. `Rule(...)` 和 authoring rule payload 没有 `condition_weights` 字段。
2. `compile_authoring_rule_v1(...)` 只保留 `description / tags` 两类 rule metadata。
3. `FileAuthoringRegistry.register_rule_spec(...)` 的 canonicalization 会把 rule payload 压缩回 `RuleSpec` 逻辑字段，导致连已存在的 `description / tags` 都无法稳定持久化。
4. service `compile-preview` 目前也不会把 rule metadata 完整透传到编译产物。

因此，Child 2 不能只是“新增 `condition_weights` 字段”；它必须同时补齐 **rule metadata carrier**，让 `description / tags / condition_weights` 在 SDK -> authoring compile -> registry -> registry read 路径上稳定 round-trip。

## 2. Goals

- 为 rule asset 定义稳定的 `condition_weights` metadata schema。
- 定义 condition key 与 where atom 位置的关联方式，并在 compiler 中做 shape/ownership 校验。
- 让 rule metadata 在 SDK / authoring / service / registry 路径上稳定保留。
- 保持 `RuleSpec` 和 where evaluator 的执行语义不变。

## 3. Non-goals

- 不把 weight 塞进 `RuleSpec.where`、`where_ast` 或 `where_eval`。
- 不实现 salience / impact / certainty propagation。
- 不引入 rule-level certainty cap。
- 不修改 derivation metadata contract。

## 4. Current Context

- `RuleSpec` 当前只承载逻辑执行最小字段：`rule_id / version / select_vars / where / expose`。
- SDK `Rule` 当前只支持 `description / tags` 两类声明元数据。
- authoring 文档已声明 rule metadata 会被 compiler 保留，但 registry canonicalization 目前与此不一致。
- runtime / preflight 的规则执行只依赖 `RuleSpec`；metadata 不参与 rule rows 计算。

## 5. Proposed Shape

### 5.1 Rule metadata carrier

- rule asset 顶层 metadata 扩展为：
  - `description: str | None`
  - `tags: list[str] | None`
  - `condition_weights: dict[str, float] | None`
- `condition_weights` 是 version-scoped rule metadata；持久化在 compiled rule payload 顶层，不新建 `meta` 包装对象。

### 5.2 Condition key

- `condition_weights` 的 key 采用 **atom-position key**：`b{branch_index}.a{atom_index}`。
- 这是现有 witness key namespace `b{branch}.a{atom}:...` 的稳定前缀，不复用 `pred_id` / `kind` 后缀。
- 一个 key 对应一个 where atom 位置，不区分该 atom 最终是 `pred`、`eq`、`not` 还是 `ruleref`。

### 5.3 Validation semantics

- compiler 负责校验：
  - `condition_weights` 必须是 `dict[str, float]`
  - key 必须对应 lowered `where` 中真实存在的 atom-position key
  - value 必须是 positive finite number
- 默认语义：**unweighted = key absent**，不是 `1.0`
- compiler 不做归一化、不推导默认值、不改写 `where`

### 5.4 Propagation boundary

- SDK `Rule.to_authoring_payload()` 输出 `condition_weights`
- `compile_authoring_rule_v1(...)` 校验并保留 `condition_weights`
- service `compile-preview` 透传 `description / tags / condition_weights`
- registry canonicalization 保留所有 rule metadata；不能再退化成仅 `RuleSpec` 逻辑字段
- preflight / runtime 仍只把 compiled payload 的逻辑字段降到 `RuleSpec`

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `RuleSpec` 仍是纯逻辑执行 contract
  - `where_eval` / `run_rule` 行为不因 weight metadata 改变
  - 现有无 metadata 或无 weight 的规则继续可编译、可注册、可执行
- 明确不做的内容：
  - 不让 `condition_weights` 进入 candidate / support / explain DTO
  - 不在本轮定义 annotation 消费接口
- 兼容性约束：
  - registry 中既有只含逻辑字段的旧 rule payload 仍可读取
  - 新 metadata 仅为 additive 扩展

## 7. Acceptance

- [x] `Rule(...)` / authoring rule payload 支持 `condition_weights`
- [x] compile-preview / registry register/read 能 round-trip `description / tags / condition_weights`
- [x] invalid condition keys 或 invalid weight values 会在 compile 阶段报错并带 path
- [x] `RuleSpec` 执行路径没有新增 metadata 依赖
- [x] 受影响模块 docs 已同步

## 8. Implementation Plan

1. 建立本 child blueprint 并冻结 condition key / propagation 边界。
2. 在 SDK 与 authoring compiler 中加入 `condition_weights` schema、校验和 payload 保留。
3. 修正 service compile-preview 与 registry canonicalization，确保 rule metadata 不被截断。
4. 补 round-trip / validation tests，覆盖 SDK -> compile -> registry -> read 路径。
5. 同步 core/authoring/service/sdk 模块 docs；若实现收口，填写 outcome 并归档。

## 9. Docs To Update

- `src/factpy_kernel/core/docs/01_architecture.md`
- `src/factpy_kernel/authoring/docs/01_overview.md`
- `src/factpy_kernel/service/docs/04_rules_registry.md`
- `src/factpy_kernel/sdk/docs/03_rules_and_derivations.md`

## 10. Outcome / Deviations

- 最终落地结果：`Rule` DSL、authoring compiler、service compile-preview、registry canonicalization/read 已全部支持 version-scoped `condition_weights`；rule asset metadata (`description / tags / condition_weights`) 现在可稳定 round-trip，而 `RuleSpec` 与 where evaluator 继续保持逻辑执行边界。
- 与 blueprint 不同的地方：实现时顺手把 registry canonicalization 的 rule metadata 丢失问题一并修正，并把 service `validate/compile-preview` 的 rule AST 校验面显式收窄为逻辑字段，避免 metadata 被 core AST 当成非法 extra keys。
- 为什么会有这些调整：不修复 metadata carrier，就没有稳定的 `condition_weights` 落点；service 侧若不先剥离 metadata，`description / tags / condition_weights` 也无法通过现有 core rule AST 校验。
- 归档说明：2026-03-20 实现完成，180 tests pass，归档到 `docs/blueprints/archive/`。
