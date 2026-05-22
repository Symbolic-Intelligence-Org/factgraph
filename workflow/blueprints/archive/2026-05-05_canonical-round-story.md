# Canonical Round Story(Batch 1 of Round Story Completion Plan)

- Status: implemented
- Created: 2026-05-05
- Parent: [2026-05-05_round-story-completion-plan.md](../active/2026-05-05_round-story-completion-plan.md) §5.1
- Scope: Batch 1 — wording alignment only(no algorithm / DTO / capability semantics change)
- Branch: `v0.1-canonical-round-story-2026-05-05`(off `adf8780`)
- Audit Log: [2026-05-05_canonical-round-story.audit.md](./2026-05-05_canonical-round-story.audit.md)

## 1. Problem

4 application capability + 1 evaluator-layer capability(5 shipped capability lines)已 shipped,但 user-facing 入口对它们的叙述**文字不统一**:

- `examples/11_capabilities_e2e_demo.py` 用 `Phase N - Capability:` 句式 + 结果断言句,但**没明示 user 该 capability 答的是哪个 canonical 问题**
- `examples/11_capabilities_e2e_demo.ipynb` 是同一 scenario 的叙事 notebook,但不是 .py 的机械导出;opening list / phase headings / wrap-up bullets 都需要对齐
- `examples/README.md` 第 22 行只列 capability 名,没承载"5 个问题"叙事
- `tutorials/evidence-pipeline.cn.md` §1(大局观)/ §7(Layer 6)/ §8(端到端示例)各自描述 capability 用 ad-hoc 文字,与 demo 不一致
- 没有任何文档单独答"我手上有个 binding,该用 Check 还是 Diagnose 还是 Fact Overlay?"——decision tree 缺位

未来 Batch 4 ProofFrame narrative renderer 与 Batch 5 rule ops 都会消费"5 问题"框架;若入口文字此刻不统一,后续每次扩张都要重排序。

本批允许新增一个短 tutorial decision-tree 文档,因为 master plan §5.1 将其列为 Batch 1 exit criteria;它仍属于 user-facing wording alignment,不引入 capability 语义。

## 2. Goal

把"5 个问题"沉淀为 canonical 叙事,跨所有 user-facing 入口表述一致。

**Canonical wording**(per master plan §5.1,本批不再改):

| # | Question | Capability |
|---|----------|------------|
| Q1 | *Does this binding pass?* | Check |
| Q2 | *Where does this failing binding fail?* | Diagnose |
| Q3 | *What if this fact were different?* | Fact Overlay Check |
| Q4 | *Given a finite candidate universe, who passes / who fails / why?* | Why-not Universe Diagnose |
| Q5 | *In native evaluation, where does the where-body collapse?* | Evaluator Frontier Trace |

中文 tutorial / decision-tree 可使用中文解释,但每个 Q leaf 必须同时保留英文 canonical question 原文,避免 localized paraphrase 成为第二套 canonical source。

## 3. Non-Goals

- ❌ 改 demo 算法 / 改 capability runtime / 改 protocol DTO
- ❌ 在 tutorial 加新 capability 教学段(本批 wording-only)
- ❌ 改 README 整体结构(只改第 22 行 entry)
- ❌ 翻译 / 国际化(decision tree doc 中文,与现 tutorial 同语)
- ❌ 引入新示例 fixture / 多 entity / 多 schema(沿用现 Person fixture)
- ❌ 任何 git push / archive 跨批操作(close-out 才考虑)

## 4. Current Context

### 4.1 Demo .py 当前 phase 文字(`examples/11_capabilities_e2e_demo.py`)

- Module docstring(L1-15):列 capability 名,无"问题"叙事
- `_phase_check`:`"Phase 1 - Check: Alice's actual binding passes."`
- `_phase_diagnose`:`"Phase 2 - Diagnose: Alice age=99 fails at the age atom."`
- `_phase_fact_overlay`:`"Phase 3 - Fact Overlay: Alice age override flips failed to passed."`
- `_phase_why_not`:`"Phase 4 - Why-not: Bob is green; Alice and Carol are age-localized red rows."`
- `_phase_frontier`:`"Phase 5 - Frontier: age=99 collapses after 3 person candidates."`
- 顶部 banner:`"FactPy v0.1 capabilities E2E demo"`

### 4.2 Demo .ipynb(575 lines,nbformat 4)

由 .py 派生,markdown cells 与 .py phase 句式应保持一致。

### 4.3 README L22(`examples/README.md`)

```
| 11 | `11_capabilities_e2e_demo.ipynb` (+ `.py` smoke target) | — (native) | general | Check / Diagnose / Fact Overlay Check / Why-not Universe Diagnose / Evaluator Frontier Trace on one Person fixture |
```

Covers 列 5 capability 名,无 question wording。

### 4.4 Tutorial 待 align 三段

- `tutorials/evidence-pipeline.cn.md` §1(L7-50)大局观
- 同文件 §7(L231-414)Layer 6 — Capability Lines(4 application + 1 evaluator)
- 同文件 §8(L415-438)端到端示例

预期改动:仅引入 Q1-Q5 canonical wording,不增 / 不删示例,不改技术内容。

### 4.5 Smoke test 现状

`src/kernel/tests/test_examples_capabilities_demo.py` import demo by path 并 call `run_demo(verbose=False)`;算法 / 断言 / 输出结构不动,仅文字层 edit 不会影响其结果。

## 5. Design

### 5.1 Canonical question 渲染规则

每个 user-facing 入口在描述 capability 时,**必须**先给出"Q# question"再给具体输出/示例。具体 binding:

- **Demo .py**:每 phase 第一行 `_announce` 先打 `f"Q{n}: {question_text}"`,再打具体结果断言句
- **Demo .ipynb**:opening list / phase markdown headings / wrap-up bullets 同步 Q1-Q5 canonical wording;保存输出不作为 canonical source,不要求重跑 notebook
- **README L22**:Covers 列改为 `Q1 Check / Q2 Diagnose / Q3 Fact Overlay / Q4 Why-not / Q5 Frontier`(短版,完整 question wording 在 demo / tutorial)
- **Tutorial §1**:加 "5 个问题" 表(Q1-Q5),作为整文档 entry framing;英文 canonical question 原文 + 中文说明并列
- **Tutorial §7**:每个 capability 子标题前加 `(Qn) <English canonical question>` 引述,原中文解释保留
- **Tutorial §8**:端到端示例段开头明示 demo 串了 Q1-Q5;编号列表也加 Q label

### 5.2 capability-decision-tree.cn.md 形态

新增 `tutorials/capability-decision-tree.cn.md`,极简,目标读者:已读完 evidence-pipeline.cn.md §7 但仍在选 capability 的人。结构:

```
# 我该用哪个 Capability?

## 一句话决定树

- 想知道"这条 binding 通不通"?       → Q1 Check — Does this binding pass?
- 通不过,想知道"卡在哪条 atom"?     → Q2 Diagnose — Where does this failing binding fail?
- 想知道"如果某 fact 改了会不会通"? → Q3 Fact Overlay Check — What if this fact were different?
- 给一组候选 binding,想知道"谁通谁不通,不通的为什么"?
                                        → Q4 Why-not Universe Diagnose — Given a finite candidate universe, who passes / who fails / why?
- native engine evaluate 失败时,想看"where-body 在哪 atom 坍塌"?
                                        → Q5 Evaluator Frontier Trace — In native evaluation, where does the where-body collapse?

## 何时不在 5 个里

- ……(列 4-5 个非本批 future trigger:scenario / rule ops / persistence / diff)
```

≤120 行,显式标"future capability 出现时本表会扩"。

### 5.3 不改的边界

- 5.1-5.2 之外**全部其他**文档 / 代码不动
- 不动 application protocol(`kernel.application.protocol.*`)
- 不动 demo fixture 形状 / 断言数量 / phase 调用顺序
- 不动 tutorial §2-§6 / §9-§15 / §覆盖检查表
- 不动其他 examples notebook(01 / 02 / 05 / 06 / 10)

## 6. Implementation Plan

| # | Action | 文件 | 类型 |
|---|--------|------|------|
| 1 | 编辑 demo `.py` 5 phase `_announce`(第一行 Q# 问题,第二行原结果句保留)+ module docstring 加"5 问题"块 | `examples/11_capabilities_e2e_demo.py` | edit |
| 2 | 镜像更新 .ipynb markdown cells(每 phase 前的 markdown 加 Q# heading)+ phase 4 已有 print 同步 | `examples/11_capabilities_e2e_demo.ipynb` | edit |
| 3 | 改 README L22 Covers 列为 `Q1 Check / Q2 Diagnose / Q3 Fact Overlay / Q4 Why-not / Q5 Frontier` | `examples/README.md` | edit |
| 4 | Tutorial §1 加 "5 个问题" 表(对应 Q1-Q5 + capability 名 + 一行 verb)| `tutorials/evidence-pipeline.cn.md` | edit |
| 5 | Tutorial §7 每 capability 子标题前加 `(Qn) <canonical question>` 引述 | 同上 | edit |
| 6 | Tutorial §8 加 1-2 行 prologue 显式说明 demo 串 Q1-Q5 | 同上 | edit |
| 7 | 写 `tutorials/capability-decision-tree.cn.md`(≤120 行) | new file | create |
| 8 | `python examples/11_capabilities_e2e_demo.py` —— 验证 verbose 输出 5 行 Q# 都 emit | run | verify |
| 9 | `python -m unittest src.kernel.tests.test_examples_capabilities_demo` —— 1 OK | run | verify |
| 10 | `git status --short` 应为 5 个 edit + 1 new + `M memory/current.md` | run | verify |
| 11 | Commit:`docs(round-story): canonical 5-question wording across demo/readme/tutorials`| git | commit |
| 12 | Blueprint outcome 填,status `draft → scoped → implementing → implemented`;archive | self | close |

## 7. Acceptance Criteria

1. Demo `run_demo(verbose=True)` 输出 stream 中 5 行 `Q1:`/`Q2:`/`Q3:`/`Q4:`/`Q5:` 各 emit 一次,wording 与 §2 表 verbatim 一致
2. Demo .ipynb 渲染时 opening list / 每 phase 上方 markdown cell / wrap-up bullets 含 `Q# <English question>` canonical wording
3. `examples/README.md` L22 Covers 列含 `Q1` ... `Q5` 字样,共 5 处
4. `tutorials/evidence-pipeline.cn.md` §1 / §7 / §8 各处保留 §2 英文 canonical question 原文;中文说明只能作为解释,不能替代 canonical source
5. `tutorials/capability-decision-tree.cn.md` 存在;≤120 行;5 个 question 各占一支决策树叶;每支同时含 Q label + 英文 canonical question
6. `python -m unittest src.kernel.tests.test_examples_capabilities_demo` 仍 1 OK
7. `python -m ruff check src/kernel examples/11_capabilities_e2e_demo.py` clean(若 demo 改动产生 lint error 必须 fix)
8. 最终 commit 后工作树仅 expected sync(`M memory/current.md`)
9. 不改任何 `src/kernel/**/*.py` 算法码 / DTO 字段(grep 检查 `git diff --stat src/` 应为空)
10. Master plan §5.1 entry/exit gate 全过(blueprint Outcome 引用此清单)

## 8. Outcome

- 最终落地结果:Q1-Q5 canonical wording now appears in the demo script, demo notebook opening/phase/wrap-up markdown, examples index, tutorial §1/§7/§8, and the new short `tutorials/capability-decision-tree.cn.md`.
- 与 blueprint 不同的地方:pre-implementation review tightened wording boundaries before the bulk edit:the batch now says "4 application + 1 evaluator" instead of "5 application + 1 evaluator";Chinese docs carry the English canonical question verbatim next to Chinese explanation;the notebook is treated as bespoke narrative markdown rather than a .py mirror.
- 为什么会有这些调整:the tightening prevents capability ownership drift and avoids localized paraphrases becoming a second canonical source.
- 归档说明:Batch 1 implemented as wording-only;no `src/` changes;focused demo, unit, JSON, ruff, and diff hygiene checks passed.
