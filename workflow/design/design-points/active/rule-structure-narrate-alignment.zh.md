# 设计点:`RuleStructure.narrate()` — 文本层对位 explain 的 narrate

- 状态:adopted(header 中性词 `Structure` 已 user 认可 2026-06-26;→ blueprint [2026-06-26_rule-structure-narrate-alignment.md](../../../blueprints/active/2026-06-26_rule-structure-narrate-alignment.md) → Codex 实现)
- 关联:
  - design-point [rule-structure-static-projection.zh.md](./rule-structure-static-projection.zh.md)(`RuleStructure` 类型;其中明确把"文本渲染"列为次要层、非该任务主产物 —— 本设计点接续之)
  - decision [2026-06-26_evidencegraph-readonly-and-rule-structure-type.md](../../decisions/active/2026-06-26_evidencegraph-readonly-and-rule-structure-type.md)(§4.2 `Evidence*` 零改动 / 独立中立类型 —— 本设计点遵守,不放宽)
  - 已发布:`fg.rules.structure` / `RuleStructure`(factgraph PR#17)

## 1. Gap

`RuleStructure` 与 `EvidenceGraph` 已在**数据/身份键**层逐节点对位(`branch_id↔tree_id`/`occurrence_alias`/`atom_id`/`join_id`,经单一来源 `structure_keys.py`)。但**文本**层没对位:`RuleStructure.render()`/`render_compact()` 复用 `RuleExprInspect` 的一行 inspect 串(`"RuleExprInspect | ast | occ; occ | joins ..."`),与 explain 的多行 `Explanation.narrate()`(`narrate_evidence`,块状散文,带 verdict 图标/状态/certainty)结构正交。用户需求:把"同一棵树,display(裸) vs explanation(执行)"从数据层延伸到文本层。

## 2. 决策

### 2.1 只加一个 `narrate()`(不是两个)

explain 侧有 `.repr`(terse 结构行)与 `.narrate()`(prose)两份文本。对**裸结构**而言,terse 那份的裸版本与现有 `render()`/`fg.rules.inspect` 高度重合,价值低;面向人的对位是 prose 那份。按窄公共 API 原则,只新增**一个**方法:

- **`RuleStructure.narrate() -> tuple[str, ...]`** —— 裸散文,逐节点对位 `Explanation.narrate()`。
- 现有 `render()` / `render_compact()`(inspect 一行)**不动**。
- 不引入 `render_proof()` / `explain_repr()` 等;命名与 explain 侧同词(`narrate`),命名本身即对位。terse-repr 的裸镜像若日后确有需求再加。

### 2.2 平行渲染器,不走 `narrate_evidence`,不改 `explanation_render.py`

**不**把 `RuleStructure` 路由进 `narrate_evidence`。硬理由:`_paths_verdict_status` 从 `type(verdict).__name__` 推状态,**verdict 缺失的节点会 fall-through 成伪造的 `fails`/`✗`**(explanation_render.py:547-553),正好违反"display 侧无 verdict"。且其 ~30 个 helper 无 None-guard 地直读 `rule.status`/`atom.verdict`/`join.status`,裸节点喂入即 AttributeError。

故:新建 **`src/factgraph/application/protocol/structure_render.py`**,`narrate_structure(structure) -> tuple[str, ...]` 自成一路;`RuleStructure.narrate()` 薄壳委派(对位 `Explanation.narrate()` 委派 `narrate_evidence` 的方式)。

**`explanation_render.py` 零改动**(不抽共享原语)。其骨架与 verdict token 揉得过紧,抽"共享骨架"得侵入式重构已发布 explain 代码、共享面却小、且威胁 zero-diff。防漂移改用**端到端 parity 测试**(§4),它是行为级保证,强于静态骨架比对,且本就要写。

### 2.3 裸渲染规则(对位骨架,去运行时)

逐行镜像 `narrate_evidence` 的行型,但:

| 槽位 | explain(执行) | display(裸) |
|---|---|---|
| header 前缀词 | `Conclusion` / `NOT concluded`(verdict 派生) | **`Structure`**(中性词:裸树未下任何判断,前两者都不诚实;此行结构上必须存在以锚定树) |
| header 后缀 | ` [row_id]` / ` (failure_class)` | 去 |
| Derivation | `head <= ( a AND b ) [p=…]` | `head <= ( a AND b )`(去 `[p=]`) |
| join 行 | `join: L.port = R.port [status]` | `join: L.port = R.port`(去 `[status]`,**保留** join 身份表达式) |
| occurrence 行 | `{label} [head] ── "{repr}" [status][p]` | `{label} [head] ── "{repr}"`(去 `[status]`/`[p]`;**保留** `[head]` 角色标记) |
| atom 行 | `{icon} {rendered} [atom_id] {status}{certainty}` | `{rendered} [atom_id]`(去 `✓/○/✗` 图标、status 词、certainty;**保留** `[atom_id]` 作对位锚) |
| `produces:` 行 | 执行绑定值 | **整行去**(裸侧只有 FreeVar 名,无值) |
| context/run-token 行 | run_id + status + certainty | **整行去** |
| atom term | `BoundVar.value` | `FreeVar.name`(有 `port_name` 时 `%port`) |

**omit-vs-neutral**:所有 trailing 运行时 token 与两条纯运行时行(`produces:`/context)整去;仅 header 前缀用中性**词** `Structure`(锚定行,删了破坏行数对位);**不**引入中性图标(verdict-icon 槽里任何字形都会被读成判断)。

### 2.4 补 atom 缺口(结构侧字段,非 `Evidence*`)

`StructureAtom` 无 `repr_text`(只有 `summary`);explain 的 atom 行打印 `atom.repr_text or type(form).__name__`。为逐节点文本对位,给 **`StructureAtom` 加 `repr_text: str | None`**(结构侧类型,**不碰** `evidence_tree.py`),builder 用与 `summary` 同源的裸投影填充(FreeVar 名 / `%port`),空回退仍为 `type(form).__name__`。

## 3. 目标格式(对位示例,单分支 atom+join 规则)

```
explain  Explanation.narrate():        display  RuleStructure.narrate():
  Conclusion ── eligible_pair            Structure ── eligible_pair
    Derivation: eligible_pair <= ( a AND b ) [p=0.9]   Derivation: eligible_pair <= ( a AND b )
    join: a.person = b.person [holds]      join: a.person = b.person
    a ── "left ..." [holds]                a ── "left ..."
      ✓ Person:region(alice,US) [a_r] holds   Person:region(%person,%region) [a_r]
    (produces: / context 行)               (无)
```

## 4. 防漂移 = 端到端 parity 测试

`RuleStructure.narrate()` 在 ≥2 fixtures(单分支 atom+join;多分支)上,与同规则执行得到的 `Explanation.narrate()` **逐行比**:display 行 == explain 行去掉运行时尾巴(`[status]`/图标/certainty/`[p=]`)+ 去掉 `produces:`/context 行 + atom term 由值换 FreeVar。此测试即对位契约,也即防漂移。

## 5. Codex slices(narrate-only;Codex-impl / Claude-gate / user-merge)

1. **[S1 follow-up]** `render()`/`render_compact()` 空 `ast` 守卫 → `''`。
2. **[S2]** `StructureAtom.repr_text`(裸)+ builder 填充。
3. **[S3]** `structure_render.py`:`narrate_structure(structure)`(裸散文,§2.3 规则)。
4. **[S4]** `RuleStructure.narrate()` 薄壳委派 S3。
5. **[S5 follow-up]** `factgraph.sdk` 导出 `FreeVar`/`HeadClosure`/`Const`(+ `__all__`)。
6. **[S6 headline gate]** parity 测试(§4)+ `evidence_tree.py` & `explanation_render.py` **zero-diff** + 现有 `Explanation.narrate()`/`.repr` snapshot 不变 + 裸输出正则断言(无 verdict 词/图标/`[p=`/执行值)。
7. **[S7]** docs:quickstart `rules.md` §4.5 增 `narrate()` 对位段 + 模块 docs。

## 6. 约束 / 不变式

- decision §4.2:`Evidence*`(`evidence_tree.py`)**零改动**;`RuleStructure` 仍是独立类型(无共享基类、无 adapter)。
- `explanation_render.py` 输出不变(zero-diff;现有 explain repr/narrate snapshot 通过)。
- `RuleStructure` 仍只读派生、非 authoring 输入(decision §4.1 litmus 不变)。
- Tree-only;pyreason/Timeline 在对位之外。

## 7. Open Q(已解)

- **Q1 ✓**(2026-06-26 user 认可):header 中性词 = **`Structure`**(对位 explain 的 `Conclusion`/`NOT concluded`,但不下判断)。
