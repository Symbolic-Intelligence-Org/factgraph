# Core 开发进度与路线图

- 范围：`src/kernel/core`
- 最后更新：2026-05-06(post Round Story Completion routemap closure @ `6b32972`)
- 基线：以当前源码行为为准（非历史版本）

## 0. Post-Routemap 状态(2026-05-06)

Round Story Completion routemap(2026-05-05 → 2026-05-06,9 大批 + 3 子批)闭环 @ `6b32972`。Routemap 主要在 `kernel.application/` + `kernel.audit/` 加新 capabilities;`kernel.core/` 在 routemap 期间的扩展受限于 application-first invariant,仅做 native evaluator 形参扩展支持上层新 capabilities。

详细 closure narrative + deferred items 记录在 monorepo 内的 round-story-completion-plan master plan §10 Outcome;本 kernel-only 包不含 routemap blueprints。

## 1. 当前状态快照

已完成的结构性工作：

- `Store` 公共入口已收口到 `runtime/evaluation/queries/builders`
- `Store.evaluate` 模式覆盖 `native | souffle | problog | pyreason` 四引擎
- `mode='python'|'engine'` 已移除并提供明确报错
- `core` 与 `adapters` 通过 `register_engine_evaluator` 解耦
- `Ledger` 采用 SQLite 真相 + 内存读缓存的 write-through 模式
- `project_view_facts_with_audit` 使用 `ProjectorAudit(contract_version=2)`
- `accept_many` 支持 `atomic` / `best_effort` 与候选依赖拓扑排序
- where AST gate 已接入（`FACTPY_WHERE_AST_VALIDATE`）
- `evaluate_where(...)` 形参已就绪 `disabled_locators` + `literal_replacements` + `added_conditions`(支持 Batch 5a/5b/5c rule actions native 评估)
- `where_ast_validate.atom_binds_new_variables(...)` 用于 add-condition 校验
- 上层声明元数据已统一为 `version / description / tags`；core 明确保持非语义边界

## 2. 已完成里程碑

### M1. Store 边界收口（完成）

结果:`runtime.py` 管门面 / `evaluation.py` 管 evaluate 主流程 / `queries.py` 管查询 facade / `builders.py` 管 candidate 构建。

### M2. Engine 注入解耦（完成）

结果:core 无需静态 import adapter;`souffle/problog/pyreason` 在适配器 import 时自注册 evaluator。

### M3. Ledger 持久化（完成）

结果:SQLite 持久化表 + 索引建立;append 事务写入与读缓存同步;账本可内存模式或文件模式运行。

### M4. Accept 批处理能力（完成）

结果:引入 `accept_many_candidate_sets(...)`;支持依赖拓扑排序、循环检测、atomic 回滚。

### M5. Projector 审计接口（完成）

结果:`project_view_facts_with_audit(...)` 返回审计结构;审计字段聚焦 active / selected / policy-drop 统计。

### M6. where_eval rule-action 形参扩展(完成,routemap-window)

结果:`evaluate_where(...)` 增加 `disabled_locators` + `literal_replacements` + `added_conditions` 形参;新增私有 helper `_apply_literal_replacements` + `_apply_added_conditions`;支持 Batch 5a/5b/5c rule action capabilities 的 native 评估,无需 application 层重写 native engine。AST validator `atom_binds_new_variables(...)` 用于 add-condition 校验。

## 3. 当前主要风险

1. 兼容层仍存在:`store.api`、`Store.evaluate_dummy`、`store/_*.py`,需逐步收敛。
2. `accept_many` 的状态机复杂度已上升,但文档示例仍不够系统。
3. 文件型 ledger 的多进程一致性边界未定义。
4. **新增 post-routemap:** native evaluator 形参表面随 rule actions 扩张(`disabled_locators` / `literal_replacements` / `added_conditions`),需关注 future rule actions 引入新形参的 signature drift gate(per Batch 5a/b/c precedent —— `evaluate_native_where(...)` signature hard-stable,扩展走 `evaluate_where(...)` 私有形参)。

## 4. 下一阶段优先级

### P1. 兼容入口收敛

目标:对 `evaluate_dummy` 给出明确下线计划;将新代码路径完全收敛到 `runtime/evaluation/queries/builders`。

### P1. accept_many 契约强化

目标:明确各 `state/error.code` 的调用方建议;增加 atomic 回滚与 blocked dependency 的固定示例。

### P1. ledger 运行边界定义

目标:明确单进程缓存模型是当前保证范围;若扩展多进程,先给出刷新/失效协议。

### P2. 规则与引擎语义一致性治理

目标:新 where 能力保持 native 与 adapter 行为一致;对关键路径补 parity 回归样例。特别 Batch 5a/b/c rule actions 目前仅 native 实现,non-native engines 行为仍通过 adapter 自身处理 / explicit unsupported 报错。

### P2. 性能基线制度化

目标:固定 benchmark 场景与记录格式;让性能改动具备可追踪前后对比。

### P3(post-routemap reactivation triggers)

下列方向在 routemap 中显式 deferred,触发条件满足时会牵动 core 调整:

- Batch 4 ProofFrame symmetric `rule_refs` hardening —— 当前 RuleRef-bearing artifacts 在 ProofFrame Rechecker 中返回 `unsupported`-equivalent;hardening 后可能影响 `kernel.core.store._support` 的 ruleref 反向传播。
- Frontier event family / rule action event kinds —— 持久化 reactivation 不直接动 core,但 round events 形参扩展(per Batch 6 §5.5.4)可能触动 audit-side schema。
- L5 cross-run aggregation —— Batch 7 §5.5.3 #11 reactivation 需 module-mapping 机制,可能要求 core 暴露 `module_id` 推导接口。
- Multi-action rule runtime / variable binding planner / RuleRef-recursive overlay —— 这些 reactivation 都会动 `evaluate_where(...)` 形参 + AST validator surface。

## 5. 执行原则

1. 先稳语义,再做性能。
2. 先收敛兼容面,再扩 API 面。
3. 对外契约变更必须先改文档,再改实现,再补回归。
4. **(post-routemap)** Application-first runtime authority 不动:新 capability 仍 DTO + pure fn 在 `kernel.application/`,core 仅暴露稳定 substrate(per `project_application_first_runtime_authority.md` memory anchor)。
