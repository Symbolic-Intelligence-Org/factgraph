# Explain Layer — Session 被拒方案记录(2026-06-08)

- Status: **archived** — session rejected alternatives / decision record
- Authority: non-authoritative; 历史决策回溯参考,不是当前设计目标
- 权威主文档: [`workflow/design/design-points/active/explain-layer-complete-design.zh.md`](../active/explain-layer-complete-design.zh.md)
- 生成时间: 2026-06-08(从 session transcript 提取)

> **保留价值说明**:
> - `§A`(9 条被拒方案)是本文件唯一保留原因 — 防止 blueprint review 时重复争论已关闭的设计分叉。
> - `§B-§E`(收敛决策 / 实测发现 / shipped 约束 / 开放问题)已合并入主文档,此处仅作历史 transcript extract,不再作为独立设计来源。

---

## §A 被废弃的早期设计(历史参考)

这些方案在本 session 中**曾经讨论但被明确拒绝**,不要重新引入。

### A-1 递归统一 EvidenceNode 树
- **方案**:用单一 `EvidenceNode` 递归类(children 嵌套)表达所有层次(head/rule_expr/rule/atom)
- **拒绝原因**:层级间语义不同,强行统一导致字段名空洞(head 的 `atoms` 是"约束说明"而非推理条件);每层该挂什么字段无法协商一致
- **取代方案**:分层独立类型(`EvidenceGraph / EvidenceTree / EvidenceRule / EvidenceAtom`),各层自带必要字段

### A-2 EvidenceEdge 独立类型
- **方案**:节点 + 边分离的图模型(EvidenceNode + EvidenceEdge)
- **拒绝原因**:边的 `edge_kind` 完全可以从子节点的 `node_kind` 派生;分离带来消费端要同时遍历两个集合的额外负担
- **取代方案**:join 成为 `EvidenceJoin(left: PortRef, right: PortRef, held: bool)`,挂在 `EvidenceTree` 上

### A-3 EvidenceProof + EvidenceTree 双层
- **方案**:`EvidenceTree`(容器,含多个 proof) + `EvidenceProof`(单条路径)
- **拒绝原因**:一层多余;`explain()` 是 per-row,每行即一个 subject,paths 直接就是路径列表
- **取代方案**:`EvidenceTree` 本身即一条路径;多路径 = `EvidenceGraph.paths: tuple[EvidenceTree, ...]`

### A-4 Grounded / Derived 包装器
- **方案**:`support: tuple[Grounded | Derived]`,两个包装类区分来源
- **拒绝原因**:零信息增量——`Grounded` 就是 `Source`,`Derived` 就是内联子证明(v1 不存在)
- **取代方案**:直接 `support: tuple[Source, ...]`;v1 无内联派生

### A-5 Computed verdict 变体(针对 Builtin)
- **方案**:Builtin 结果用第四种 verdict `Computed(value)` 表示
- **拒绝原因**:Builtin 是计算而非判定;结果放 `Builtin.result` 字段;verdict 用 `Holds`(算出)或 `NotReached`(参数未绑定)
- **取代方案**:两态 Holds / NotReached(Builtin 永远不 Fails)

### A-6 Fails 带 reason 字段
- **方案**:`Fails(certainty, reason: str | StructuredReason)`
- **拒绝原因**:reason 完全可以从 form + 操作数现算(Compare 失败→差值;Pred 失败→空 support;Negation 失败→inner holds);存储会与实际值冗余并可能过期
- **取代方案**:`Fails(certainty)` only;reason 由 `__repr__` 现算

### A-7 Site 值对象(atom 位置)
- **方案**:用 `Site(case, cond, pred_or_kind)` 值对象表示 atom 位置
- **拒绝原因**:substrate 已有稳定命名约定 `c{case}.c{cond}:{pred|kind}`;Site 是多余包装
- **取代方案**:直接 `atom_id: str`,格式 `c0.c2:person:age`

### A-8 引擎层内嵌 why_not / proof_step 关系
- **方案**:在 Datalog/ProbLog 程序里手写配套子句
- **拒绝原因**:
  1. 每条业务规则需手写配套子句,主规则改一个条件,配套子句全要同步——脆弱
  2. ProbLog 原生 provenance 本身也只记获胜分支,并未解决穷尽问题
- **取代方案**:Python 侧穷尽探查器,直接遍历 `Rule.when` AST(见主文档 §2)

### A-9 三层统一 verdict 类型 Holds|Fails|NotReached
- **方案**:三层(Atom/Rule/Tree)全部用同一个 `Holds|Fails|NotReached` union 类型
- **拒绝原因**:Rule/Tree 层没有 `support` 概念(那是 atom 层的);payload 不同意味着类型不应统一;穷尽探查器下 Rule/Tree 的 `not_reached` 语义与 atom 层不同(见主文档 §4)
- **取代方案**:Atom 用三态 verdict 类型(带 payload);Rule/Tree 用 `status: Literal["holds","fails","not_reached"]` 字段(无 payload)

---

## §B-§E 已合并内容(历史 transcript extract,非独立设计来源)

`§B`(收敛决策 B-1..B-12)、`§C`(实测发现)、`§D`(shipped 约束)、`§E`(开放问题)均已合并入:
- 主文档 `explain-layer-complete-design.zh.md` §2-§4/§7/§9
- Certainty 引擎映射(B-4)→ 主文档 §9 已决待落地 Certainty 条目
- AND lowering + join 物化(B-6/D)→ 主文档 §7 Shipped Facts
- 被拒方案命名迁移表(B-12)→ 主文档 §12 repr 命名体系

不再需要从本文件读取上述内容。
