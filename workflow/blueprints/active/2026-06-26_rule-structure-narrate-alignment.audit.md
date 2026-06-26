# Task Blueprint Audit: `RuleStructure.narrate()` — 文本层对位 explain narrate

- Blueprint: [2026-06-26_rule-structure-narrate-alignment.md](./2026-06-26_rule-structure-narrate-alignment.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-26 | scoped | Blueprint created (scoped) | Consumes design-point rule-structure-narrate-alignment (adopted; header 词 `Structure` user-认可) + decision 2026-06-26_evidencegraph-readonly-and-rule-structure-type §4.2. 由 design 工作流(4 agents,explanation_render.py file:line 已验)收敛。Collaboration: Codex-impl / Claude-gate / user-merge. |

## Decision Notes

### 2026-06-26 — scope freeze

- **Upstream lock**:design-point §2(决策)+ §2.3(裸规则表)+ decision §4.2(`Evidence*` 零改动)为 adopted 约束;本 blueprint 不得偏离。
- **两处用户裁决(本轮)**:
  - **单方法**:只加 `narrate()`,**不**加第二个文本方法(`render_proof`/terse-repr 裸镜像);用户直觉"应该只有一个 narrate"+ 窄公共 API 原则。terse 裸镜像若日后需求再开。
  - **平行渲染器 + 不改 `explanation_render.py`**:用户将 line-grammar 方法交 Claude 判断;裁为平行渲染器、`explanation_render.py` 零改动,防漂移用端到端 parity 测试(行为级,强于静态骨架比对;且本就要写)。理由:`narrate_evidence` helper 把骨架与 verdict token 揉紧,抽共享原语需侵入式重构已发布 explain 代码、共享面小、威胁 zero-diff gate。
  - **header 中性词 `Structure`**(2026-06-26 user 认可):`Conclusion`/`NOT concluded` 皆 verdict 派生,裸树未下判断,不诚实;`Structure` 中性且锚定行不可省(否则破坏行数对位)。
- **Scope frozen to**:7-slice 计划(§8)。`evidence_tree.py`(`Evidence*`)+ `explanation_render.py` 输出**零改动** —— 任一 slice 若似需改这两者,即 scope breach → 停 + escalate。
- **关键技术风险(gate 重点关注)**:parity 测试要逐行映射 `narrate_evidence` 的非平凡分支 —— 单/多 tree 时 Derivation 是否包含、`omit_label` 退化头==体情形、multi-path probability 行。Codex S6 须覆盖这些;gate 须独立验证 display 行确能 == explain 行去尾,而非测试被弱化以迁就。
- **Cadence**:Codex 逐(批)slice 实现;Claude 按对应 Acceptance gate(独立复验,不贴 Codex 自报)+ 回归,再进下一;user merge;发布沿用 PR#17 外科式(src + tests + quickstart docs;模块 docs/examples 留 hnsm)。

### Gate log (append per slice)

| Date | Slice | Codex result | Claude gate verdict | Notes |
| --- | --- | --- | --- | --- |
| 2026-06-26 | F1-F4 (gate 2) | golden tuple parity(atom 期望脱离被测对象)+ 注入回归测试 + aggregate `Aggregate` form 投影 + body-repr label 镜像 explain + `NoneType` fallback 守卫 + runtime-free denylist 从 explanation 派生 | **GO-for-user-merge** | 独立复验(非贴自报):**B1 已解** — golden 是字面 tuple(test:34/47/67),我**独立注入**(c0:atom:2 + 自定值 + 内联深替换,非 Codex helper)→ `narrate()!=golden` 测试会红 + 注入值浮现 ⇒ 自指缺陷真修复,测试能拦泄漏。**B 已解**:aggregate 裸出 `%total equals count(...)`,`form.right is Aggregate`,无原始 tuple。**C 已解**:body 带 repr 时 label = 裸 rule_id(镜像 explain),无 Member/Peer 泄漏。**E 已解**:`NoneType` fallback 守卫。**A 改进**:runtime-free 从 explanation 绑定派生。zero-diff 仍空;**unittest 13/13**;**广回归 107/107**(test_rule_structure + ruleexpr_inspect + rule_expr_evaluate + explain_conformance_native)。**新非阻塞 follow-up**:`sdk.Aggregate` 未导出(Const/FreeVar 已导出),建议补齐 term-type 导出一致性。判定:**GO**,可 user-merge + 发布(沿用 PR#17 外科式)。 |
| 2026-06-26 | S1-S7 (gate 1) | narrate_structure 平行渲染器 + `StructureAtom.repr_text` + `narrate()` + 空-ast 守卫 + sdk 导出 + parity/runtime-free 测试 + docs | **FIX-FIRST**(1 blocking) | 独立复验(非贴自报,含对抗工作流 4 agents):**PASS** — zero-diff(`evidence_tree.py`+`explanation_render.py` 空,且有测试内 git-diff 守卫)、canonical fact/compare 形状 faithful 裸对位(原始行亲眼:`us equals us`→`%region equals us`)、runtime-free、`Const`/`FreeVar`/`HeadClosure` 导出且 forms 实际用之(无 `where_ast.Const` 泄漏)、render/compact 仅加空-ast 守卫、line-shape 覆盖完整(每个 narrate emitter mirror-naked 或正确省略)、no-reverse-edge、unittest 10/10、negation/in/addc-builtin 形状 faithful、S7 docs(quickstart §4.5)。 **BLOCKING B1**:parity 测试(设计 §4 钦定的 headline 防漂移 gate)在 atom 行**自指**——`_normalized_explain_narrate`(test:407-421)的 atom 期望行从被测 structure 自身 `repr_text` 重建,assertEqual 等于 structure 跟自身拷贝比 atom 内容;运行时值若被写进某 atom 会同时骗过 parity + (denylist) runtime-free。assertIn 字面钉只护 1 fixture 的 2 个 atom,新 atom/规则无保护 → 设计核心保证未兑现。**工作流给的修法有误**(“保留 explain 的 atom 文本再 assertEqual”——执行值 `alice/us` ≠ 裸 `%user/%region`,会 false-fail);正解:golden 期望行(独立于被测对象)+ runtime-free 改为从 explanation 实际绑定派生禁词(排除 const)。 **越界真实缺陷(非阻塞,出 §7 fixtures)**:**C(我独立确认)** body occurrence 带 `repr=` → structure 印模板 `"Member %user in %region"` vs explain 印裸 `left_region` → 对位断裂(公共 API 可达,未测);**B(工作流复现+builder 读确认)** aggregate atom 裸文本泄漏原始 IR tuple `('count',None,[...]) >= 1`(`Aggregate` 分支 rule_structure.py:359-363 存在但 `_atom_form` 未触达,被包成 `Const`→`str(tuple)`,:370-371);**E** 全空 fallback 印 `"NoneType"`(builder 不可达,cosmetic)。 **判定**:B1 必须先修(headline gate);建议同 slice 修 B(aggregate fixture + 渲染)+ 定 C(对齐 explain body-label)。不 merge,待 Codex 修复后再 gate。 |
