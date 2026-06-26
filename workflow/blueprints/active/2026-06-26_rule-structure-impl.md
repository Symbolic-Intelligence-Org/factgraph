# Task Blueprint: 实现 `fg.rules.structure` + `RuleStructure`(引擎中立规则结构投影)

- Status: scoped
- Created: 2026-06-26
- Last Updated: 2026-06-26
- Collaboration: **Codex-impl / Claude-gate / user-merge**(Codex 按本 blueprint 逐 slice 实现;Claude 逐 slice gate;user merge)
- Related Modules:
  - `src/factgraph/application/protocol/rule_expr_lowering.py`(`RuleExprLoweringPlan` 骨架 + 身份键来源)
  - `src/factgraph/application/explain/prober.py`(key-minting;拆出 plan-skeleton)
  - `src/factgraph/application/explain/evidence_tree.py`(`Evidence*` — **只读引用,零改动**)
  - `src/factgraph/application/protocol/rule_expr_inspect.py`(inspect floor — 超集目标)
  - `src/factgraph/sdk/store.py`(`fg.rules.*` SDK surface)
- Related Docs:
  - decision [2026-06-26_evidencegraph-readonly-and-rule-structure-type.md](../../design/decisions/active/2026-06-26_evidencegraph-readonly-and-rule-structure-type.md)(adopted — §4 约束)
  - design-point [rule-structure-static-projection.zh.md](../../design/design-points/active/rule-structure-static-projection.zh.md)(§3 类型契约 + §5 slices 草图)
- Audit Log:
  - [2026-06-26_rule-structure-impl.audit.md](./2026-06-26_rule-structure-impl.audit.md)

## 1. Problem

消费者需要规则的静态结构作为**数据**,不运行 explain,且与 explain `EvidenceGraph` **逐节点对位**。今天 `RuleExprInspect` 走未-DNF 作者树(不带 plan 键、无法对位),`EvidenceGraph` 引擎污染且是运行时输出。详见 design-point §1。

## 2. Goals

- 实现引擎中立 **`RuleStructure`** 类型(design-point §3.2 契约)+ **`fg.rules.structure(rule) -> RuleStructure`**。
- `RuleStructure` ≥ `RuleExprInspect` 全部内容;与 `EvidenceGraph` **按 plan 身份键节点恒等对位**(`branch_id↔tree_id`/`occurrence_alias`/`atom_id`/`join_id`)。
- 遵守 adopted decision §4.1(EvidenceGraph 只读定位 + 机械明线)+ §4.2(独立中立类型 + 共享 backbone + `Evidence*` 零改动 + Tree-only)。

## 3. Non-goals

- 不改 `evidence_tree.py`(`Evidence*`)及其消费者(decision §4.2)。
- 不做 Timeline 投影;pyreason cross-model 映射另议(decision §3、design-point Q4)。
- 不让 `EvidenceGraph`/`RuleStructure` 可操作 / 作 authoring 输入(decision §4.1 litmus)。
- 文本渲染(`render`/`render_compact`/未来 `describe`)是次要层,非本任务主产物。

## 4. Current Context

- `fg.rules.inspect`(`store.py:2348`)→ `RuleExprInspect`(未-DNF 作者树)。
- `RuleExprLoweringPlan`(`rule_expr_lowering.py:124`)引擎无关;DNF `branches`(`branch_id="c{idx}"`,`:962`)、`occurrence_map`、join/head-link materializations(`:148-182`)。
- `EvidenceGraph`(`evidence_tree.py:154`)从 plan 装配;`paths` = 每分支一棵 `EvidenceTree`(`tree_id=branch_id`)。
- 身份键全部为 plan 的确定性函数(`prober.py:124,138,1097` / `diagnostic_assemble.py:111`)。

## 5. Proposed Shape

类型契约、层级对应、`FreeVar`、`HeadClosure`、字段定义见 **design-point §3.2–§3.4**(权威草案,Codex 据此定稿)。约束见 **decision §4**。要点:

- 独立 `Structure*` 家族(`RuleStructure` / `StructureBranch` / `StructureOccurrence` / `StructureAtom` / `StructureJoin` / `StructurePort` / `StructurePortRef` / `StructureHeadLink` / `HeadClosure` / `FreeVar`),**不复用、不改** `Evidence*`。
- 从 `RuleExprLoweringPlan` 投影;复用与 prober/assembler **相同**的身份键铸造。
- cut line:无 `status`/`verdict`/`certainty`/`timestep`/`support`/`blocked_by`。
- 裸变量 = `FreeVar(name, port_name)`;atom form 结构化(`Fact|Compare|Builtin|Aggregate`)。
- inspect-floor 兼容:扁平派生属性(`occurrences`/`joins`/`ports`/`templates`/`port_visibility`/`is_closed`/`unbound_ports`/`render`/`render_compact`)。
- `is_closed`/`unbound_ports` 经 `HeadClosure | None`(schema 在场才算,否则 None;兼容属性默认 `False`/`()`)。
- 丢弃死字段 `PortInspect.field`/`value_type`。

## 6. Boundaries And Invariants

- decision §4.1:`EvidenceGraph`/`RuleStructure` 只读派生;**`core/`/推导链任何函数不接受 `EvidenceGraph` 或 `RuleStructure` 参数**(机械守卫)。
- decision §4.2:`Evidence*` 零改动;**节点恒等对位不变式**(对位键来自单一 plan ⇒ 无漂移)。
- 兼容:`RuleExprInspect` + `fg.rules.inspect` 行为不变。
- 范围:Tree-only;pyreason/Timeline 在节点恒等对位之外。

## 7. Acceptance

- [ ] `RuleStructure` 携带 ≥ `RuleExprInspect` 全部内容;现有 `fg.rules.inspect` 调用方不受影响。
- [ ] `fg.rules.structure(rule)` 与 `fg.eval.explain(<同规则>).evidence` 在 `branch_id`/`occurrence_alias`/`atom_id`/`join_id` 上**节点恒等**(native / souffle / problog)。
- [ ] `evidence_tree.py`(`Evidence*`)及其消费者**未改动**。
- [ ] 机械守卫/测试:`core/`/推导链无函数接受 `EvidenceGraph` 或 `RuleStructure`。
- [ ] pyreason explain 仍工作;Timeline 文档化为节点恒等对位之外。
- [ ] 受影响模块 docs 已同步;如有新持久入口,`docs/README.md` 已更新。

## 8. Implementation Plan(Codex 逐 slice;Claude 逐 slice gate)

1. **[prober.py]** 抽出纯 "skeleton-from-plan" 的身份键铸造(`branch_id`/`occurrence_alias`/`atom_id`/`join_id`),使运行时 assemble 与静态投影**单一来源**(防漂移)。
2. **[application/protocol]** 定义 `Structure*` dataclasses + `FreeVar`(frozen,引擎中立),按 design-point §3.2。
3. **[application]** `assemble_static_structure(plan[, schema_index]) -> RuleStructure`:投影 plan;`HeadClosure` 经 `_inspect_closed_head`(有 schema 才算,否则 None);丢死字段。
4. **[coverage]** inspect-floor 派生属性(§5)+ `HeadClosure` 兼容属性。
5. **[sdk/store.py]** `fg.rules.structure(rule)` 薄壳(application-first)。
6. **[guard]** 机械守卫/测试:`core/`/推导链不收 `EvidenceGraph`/`RuleStructure`。
7. **[tests]** 节点恒等对位测试(structure vs explain,native/souffle/problog)+ inspect-floor parity 测试。
8. **[docs]** 模块 docs:`RuleStructure` 契约 + 节点恒等对位不变式 + EvidenceGraph 只读定位/litmus/Tree-only 边界。

> Codex 每完成一个 slice,Claude 按对应 Acceptance 项 gate(验证 + 回归),再进下一 slice;scoped-unit 完成后 user merge。

## 9. Docs To Update

- `src/factgraph/application/explain/docs/README.md`(或 protocol docs 入口)— `RuleStructure` 契约、节点恒等对位不变式、EvidenceGraph 只读定位 + litmus + Tree-only/Timeline 边界。
- `docs/README.md`(如新增持久 docs 入口)。

## 10. Outcome / Deviations

任务完成后填写:

- 最终落地结果:
- 与 blueprint 不同的地方:
- 为什么会有这些调整:
- 归档说明:
