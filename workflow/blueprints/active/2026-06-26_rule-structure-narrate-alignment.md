# Task Blueprint: `RuleStructure.narrate()` — 文本层对位 explain narrate

- Status: scoped
- Created: 2026-06-26
- Last Updated: 2026-06-26
- Collaboration: **Codex-impl / Claude-gate / user-merge**(Codex 逐 slice 实现;Claude 逐 slice gate;user merge)
- Related Modules:
  - `src/factgraph/application/protocol/rule_structure.py`(`RuleStructure` / `StructureAtom` — 加 `narrate()` + `repr_text`)
  - `src/factgraph/application/protocol/structure_render.py`(**新** — 平行裸渲染器)
  - `src/factgraph/application/protocol/explanation_render.py`(**只读参照,零改动** — 行型来源)
  - `src/factgraph/application/protocol/evaluate_result.py`(只读参照 — `Explanation.narrate()` 委派形状)
  - `src/factgraph/application/explain/evidence_tree.py`(`Evidence*` — **只读,零改动**)
  - `src/factgraph/application/rule_structure.py`(builder — 填 `StructureAtom.repr_text`)
  - `src/factgraph/sdk/__init__.py`(follow-up 导出)
- Related Docs:
  - design-point [rule-structure-narrate-alignment.zh.md](../../design/design-points/active/rule-structure-narrate-alignment.zh.md)(**权威设计** — §2 决策 / §2.3 裸规则 / §5 slices)
  - decision [2026-06-26_evidencegraph-readonly-and-rule-structure-type.md](../../design/decisions/active/2026-06-26_evidencegraph-readonly-and-rule-structure-type.md)(§4.2 `Evidence*` 零改动 — adopted 约束)
  - 前序 blueprint [2026-06-26_rule-structure-impl.md](./2026-06-26_rule-structure-impl.md)(`RuleStructure` 本体;本任务接续其"文本渲染次要层")
- Audit Log:
  - [2026-06-26_rule-structure-narrate-alignment.audit.md](./2026-06-26_rule-structure-narrate-alignment.audit.md)

## 1. Problem

`RuleStructure` 与 `EvidenceGraph` 已在数据/身份键层逐节点对位,但**文本层**未对位:`RuleStructure.render()` 复用 inspect 一行串,与 explain 的多行 `Explanation.narrate()`(`narrate_evidence`,块状散文 + verdict 图标/状态/certainty)结构正交。需把"同一棵树,display(裸) vs explanation(执行)"延伸到文本层。详见 design-point §1。

## 2. Goals

- 新增 **`RuleStructure.narrate() -> tuple[str, ...]`**:裸散文,逐节点对位 `Explanation.narrate()`(design-point §2.1 / §2.3)。
- 平行渲染器 `structure_render.py`;`explanation_render.py` + `evidence_tree.py` **零改动**(design-point §2.2)。
- 防漂移 = 端到端 parity 测试(display narrate == explain narrate 去运行时尾巴;design-point §4)。

## 3. Non-goals

- 不加第二个文本方法(无 `render_proof`/terse-repr 裸镜像);`render()`/`render_compact()` 不动(design-point §2.1)。
- 不改 `evidence_tree.py`(`Evidence*`)、不改 `explanation_render.py` 输出(decision §4.2 + design-point §2.2)。
- 不路由 `RuleStructure` 进 `narrate_evidence`(verdict 缺失会伪造 `fails`;design-point §2.2)。
- 不做 Timeline 文本对位;Tree-only。

## 4. Current Context(已验,design-point §2 引用 file:line)

- `Explanation.narrate()`(evaluate_result.py:338-346)委派 `narrate_evidence`;`.repr`(:327-336)委派 `walk_evidence`。
- `narrate_evidence`(explanation_render.py:40)硬绑 `EvidenceGraph`;header(:44-60)+ 逐 tree(`_narrate_tree`)+ Derivation(:325-334)+ join(:356-363)+ rule(:366-383)+ atom(:386-389)。
- 每 helper 直读 verdict 侧字段(`rule.status`/`atom.verdict`/`join.status`);`_paths_verdict_status`(:547-553)缺 verdict 时 fall-through `fails`。
- `StructureAtom`(rule_structure.py:104-129)有 `summary`、**无 `repr_text`**;`StructureOccurrence`(:162-179)有 `repr_text`。
- `RuleStructure.render()`(:307-322)= inspect 一行(复用 `rule_expr_inspect` helper)。

## 5. Proposed Shape

裸规则表、目标格式、`Structure` header 词、atom `repr_text` 缺口见 **design-point §2.3 / §3 / §2.4**(权威)。要点:

- 单方法 `narrate() -> tuple[str,...]`,薄壳委派 `structure_render.narrate_structure(structure)`。
- 行型镜像 `narrate_evidence` 但去 trailing 运行时 token + 去 `produces:`/context 行;header 前缀中性词 `Structure`;atom term 由 `FreeVar.name`/`%port`。
- 保留对位锚:`[atom_id]`、join 身份表达式、`[head]` 角色标记、occurrence repr 标签。
- `StructureAtom` 加 `repr_text: str | None`(结构侧;builder 同 `summary` 源裸投影填充)。

## 6. Boundaries And Invariants

- decision §4.2:`Evidence*` 零改动;`RuleStructure` 独立类型(无共享基类/无 adapter)。
- `explanation_render.py` 输出不变(zero-diff;现有 explain narrate/repr snapshot 通过)。
- decision §4.1:`RuleStructure` 只读派生、非 authoring;`core/`/推导链不接受(前序机械守卫已覆盖,本任务不回退)。
- Tree-only;pyreason/Timeline 在对位之外。

## 7. Acceptance

- [ ] `RuleStructure.narrate()` 在 ≥2 fixtures(单分支 atom+join;多分支)上,与同规则 `Explanation.narrate()` 逐行对位:display 行 == explain 行去 `[status]`/图标/certainty/`[p=]` + 去 `produces:`/context + atom term 值换 FreeVar。
- [ ] 裸输出无 verdict 词 / 无 `✓○✗` / 无 `[p=` / 无执行值(正则断言)。
- [ ] `evidence_tree.py` + `explanation_render.py` **未改动**(git diff 空);现有 `Explanation.narrate()`/`.repr` snapshot **byte 不变**。
- [ ] `render()`/`render_compact()` 行为不变(空 `ast` → `''` 守卫除外)。
- [ ] `from factgraph.sdk import FreeVar, HeadClosure, Const` 成功(+ `__all__`)。
- [ ] 受影响 docs 同步(quickstart `rules.md` §4.5 + 模块 docs)。

## 8. Implementation Plan(Codex 逐 slice;Claude 逐 slice gate)

> 对应 design-point §5。

1. **[S1 follow-up]** `RuleStructure.render()`/`render_compact()` 空 `ast` 守卫 → `''`。
2. **[S2]** `StructureAtom.repr_text: str | None`(rule_structure.py)+ builder(application/rule_structure.py)同 `summary` 源裸投影填充(FreeVar 名 / `%port`;空回退 `type(form).__name__`)。
3. **[S3]** **新** `src/factgraph/application/protocol/structure_render.py`:`narrate_structure(structure) -> tuple[str,...]`(design-point §2.3 规则)。
4. **[S4]** `RuleStructure.narrate()` 薄壳委派 S3。
5. **[S5 follow-up]** `factgraph.sdk` 导出 `FreeVar`/`HeadClosure`/`Const`(+ `__all__`;确认源模块)。
6. **[S6 headline gate]** parity 测试(§7 第 1 项)+ zero-diff(`evidence_tree.py` & `explanation_render.py`)+ 现有 explain snapshot 不变 + 裸输出正则断言。
7. **[S7]** docs:quickstart `rules.md` §4.5 增 `narrate()` 对位段 + 模块 docs(`sdk/docs`、`application/protocol`/`explain/docs`)。

> Codex 每完成一(批)slice,Claude 按对应 Acceptance gate(验证 + 回归),再进下一;scoped-unit 完成后 user merge。发布到 factgraph 时:src/ 代码 + tests + quickstart docs 带走,模块 docs/examples 留 hnsm 侧(沿用 PR#17 外科式)。

## 9. Docs To Update

- `docs/quickstart/rules.md` §4.5(`fg.rules.structure`)— 增 `narrate()` 对位段。
- 模块 docs:`src/factgraph/sdk/docs/*`(rule/api 面)、`application/protocol` 或 `explain/docs/README.md`(narrate 对位不变式 + 平行渲染器定位)。

## 10. Outcome / Deviations

任务完成后填写:

- 最终落地结果:
- 与 blueprint 不同的地方:
- 为什么会有这些调整:
- 归档说明:
