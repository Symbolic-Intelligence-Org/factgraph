# Rule-Replay Line Redesign Input Bundle

- **Status:** working / consolidated 2026-05-03
- **Authority:** non-authoritative reference bundle for redesign work on `v0.1-redesign-2026-05-03`. NOT a blueprint, NOT scope, NOT API contract.
- **Lifecycle:** consolidated AFTER 2026-05-03 reset of v0.1.x design probe. Once redesign work picks up specific direction (Check / Overlay / Rechecker / etc),实际 blueprint 在 `docs/blueprints/active/` 起,本 bundle 作为 design input 引用。
- **Trigger:** 用户 2026-05-03 reset v0.1.x design probe 后明确要求"把和这条线相关的所有文档整合到一起,为下一步开发做参照"。

## 这是什么

把 2026-04-30 .. 2026-05-03 之间在 design probe 期间产生的所有相关材料(设计历史 / 能力分层 / 漂移分析 / 设计讨论 / 已废 blueprint / 用户原始 brainstorm)集中到本目录,redesign 时一处可读,**不必再 `git show v0.1.1-evidence-tree-operational-overlay:...` 翻 rollup**。

源材料在 rollup branch (`v0.1.1-evidence-tree-operational-overlay`) 上,本 bundle 是它们在 redesign branch 上的 snapshot。源 rollup 仍 frozen,内容不变。

## 怎么读(按 redesign 实际需求倒推)

### 如果你是 NEXT-SESSION agent,只想 5 分钟知道发生了什么

读两个文件:
1. **`/memory/current.md`** — 当前 redesign branch 状态 + reset note + 新 hard constraint
2. **本 README** — 知道这个 bundle 的存在,需要时再深入

不需要立刻读 bundle 内的所有材料。只在 redesign 实操要触及具体话题(Check 怎么做?fact overlay 怎么做?evidence layering 怎么做?)时再深入。

### 如果你要 redesign 某个具体 capability

按 capability 找入口:

| 如果你在做 | 先读 | 再读 |
|---|---|---|
| **Check operation** (boolean 合规判定) | `40_design-discussion-A-with-decision-1.md` 的 A 段(round 1+2 + 锁定 shape) | `00_brainstorm-original.md` 命题 4 + `10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md` §"Check" |
| **Fact-level overlay** | `40_design-discussion-A-with-decision-1.md` 的 H 段 placeholder | `10_design-history-bprime-bdoubleprime/evidence-tree-proof-recheck-ideas-2026-04-30.md` §6.4 `FactValueOverride` |
| **EvaluationOverlay 多 action 容器** | `40_design-discussion-A-with-decision-1.md` 的 B 段 placeholder | `10_design-history-bprime-bdoubleprime/evidence-tree-proof-recheck-ideas-2026-04-30.md` §6 整章 |
| **ProofFrameRechecker 局部诊断器** | `40_design-discussion-A-with-decision-1.md` 的 C 段 placeholder | `10_design-history-bprime-bdoubleprime/evidence-tree-proof-recheck-ideas-2026-04-30.md` §5 整章 |
| **Status vocabulary + 最小因果识别** | `40_design-discussion-A-with-decision-1.md` 的 D 段 placeholder | `10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md` §"Status Vocabulary" + §"Evidence Comparison" |
| **Lazy why-not / candidate universe** | `40_design-discussion-A-with-decision-1.md` 的 E 段 placeholder | `10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md` §"Lazy Why-Not Trace" |
| **shared_id / library identity** | `40_design-discussion-A-with-decision-1.md` 的 F 段 placeholder | `10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md` §"Condition Ids And Shared Identity" |
| **Add-condition + binding planner** | `40_design-discussion-A-with-decision-1.md` 的 G 段 placeholder | `10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md` §"Adding Conditions And New Variables" |

### 如果你是设计 reviewer,要做 strategic 决策

读三个 synthesis 视角:
1. **`30_drift-analysis-2026-05-02.md`** — 9 维度评分 + 6 结构性 concern + 6 next-step 路径分析
2. **`20_capability-layering-l0-l11.md`** — evidence 能力 L0-L11 分层 + 依赖图
3. **`10_design-history-bprime-bdoubleprime/rule-replay-design-synthesis-2026-05-01.md`** — B'' 全图 + 6 stable design principles

### 如果你想了解为什么会有这个 bundle

读:
- **`60_lessons-learned.md`** — design probe 学到的关键经验(指向 cross-session memory)
- **`50_archived-blueprints/2026-05-02_v0.1.4-param-override.md`** — abandoned 教训:`param_override` 是 4 类不可合并语义
- **`40_design-discussion-A-with-decision-1.md`** Decision 1 段 — strangler migration 在 reset 时 superseded 的 framing

## 目录结构

```
rule-replay-line-redesign-input/
├── README.md                                                    # 本文档
├── 00_brainstorm-original.md                                    # 用户 chat 提供的原始 brainstorm
├── 10_design-history-bprime-bdoubleprime/                       # B → B' → B'' pivot 历史
│   ├── README.md                                                # pivot 故事 + 阅读建议
│   ├── evidence-tree-context-bprime-2026-04-30.md               # B' 草案
│   ├── evidence-tree-proof-recheck-ideas-2026-04-30.md          # B' 工作笔记(EvaluationOverlay / ProofFrameRechecker / FactValueOverride 起源)
│   ├── operational-evidence-tree-rule-replay-design-2026-05-01.md  # B'' 工作笔记(rule operable + evidence read-only 锁定)
│   └── rule-replay-design-synthesis-2026-05-01.md               # B'' 全图 synthesis,blueprint authors 入口点
├── 20_capability-layering-l0-l11.md                             # evidence 能力 L0-L11 分层(reset 后 framing 仍 valid)
├── 30_drift-analysis-2026-05-02.md                              # design landscape drift + 现实评估
├── 40_design-discussion-A-with-decision-1.md                    # A 方向 round 1+2 讨论 + Decision 1 历史 framing
├── 50_archived-blueprints/                                      # 4 个 abandoned blueprint 全文
│   ├── 2026-05-01_rule-replay-with-evidence-diff.md             # v0.1.1 abandoned impl
│   ├── 2026-05-01_rule-replay-with-evidence-diff.audit.md
│   ├── 2026-05-02_v0.1.2-rule-module-ir.md                      # v0.1.2 abandoned impl
│   ├── 2026-05-02_v0.1.2-rule-module-ir.audit.md
│   ├── 2026-05-02_v0.1.3-disable-condition.md                   # v0.1.3 abandoned impl
│   ├── 2026-05-02_v0.1.3-disable-condition.audit.md
│   ├── 2026-05-02_v0.1.4-param-override.md                      # v0.1.4 abandoned (Step 0 negative-result)
│   └── 2026-05-02_v0.1.4-param-override.audit.md
└── 60_lessons-learned.md                                        # 经验小结 + 指向 cross-session memory
```

## 关键 reset 后 framing 调整(读这些材料前必看)

材料是 reset 之前(v0.1.x design probe 期间)产出的。应用时注意以下 framing 已变:

| 之前 framing | reset 后调整 |
|---|---|
| "Decision 1 = strangler migration"(在 SDK 试,后期下沉到 application) | **superseded**。新 hard constraint:每一个 capability 必须从 day 1 在 application 起 DTO + pure fn,SDK 只 shell 无 substrate |
| "v0.1.x preview surface 不能浪费,要保留兼容性" | **superseded**。preview line 按定义无用户承诺,可以推倒。design probe 已 reset |
| "evidence vision L0-L11 是设计 framing,L4-L11 是 v0.2 候选" | **仍 valid**,但 L0-L3 的 v0.1.x impl 已 reset;新 redesign 的 L0-L3 应直接在 application 层从 day 1 立 DTO |
| "rule replay = 通过 SDK `replay_with_patch` 暴露" | **superseded**。新 redesign 的 replay capability 从 day 1 走 application protocol DTO |
| "B'' pivot rule operable + evidence read-only" | **仍 valid**(B'' 设计正确性与 impl 反思无关;reset 只是改变 layer placement,不改 design philosophy) |
| "Module identity = owner/path-scoped(not pure content hash)" | **仍 valid**(见 `feedback_identity_design.md`) |
| "ConditionModule.atom 必须递归 immutable" | **仍 valid**(见 `feedback_invariant_defense_in_depth.md`) |
| "candidate_key 是 cross-run identity,不能用 candidate_id" | **仍 valid** |
| "locator stability invariant — disable / replace 不能位移 b{branch}.a{atom}" | **仍 valid** |

## 不在本 bundle 中的相关材料

- **Cross-session memory**(在 `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/` 外部 store):
  - `feedback_invariant_defense_in_depth.md`
  - `feedback_narrow_public_api.md`
  - `feedback_identity_design.md`
  - `feedback_refactor_execution_traps.md`
  - `feedback_blueprint_workflow.md`
  - `project_application_first_runtime_authority.md`(reset 后已更新,新 hard constraint)
  - `project_release_branch_invariants.md`(release base sacred)
  - `project_atom_key_format.md`
- **Old impl code**(在 rollup branch 上,git-accessible):
  - `git show v0.1.1-evidence-tree-operational-overlay:src/kernel/sdk/replay.py`
  - `git show v0.1.1-evidence-tree-operational-overlay:src/kernel/sdk/replay_runtime.py`
  - `git show v0.1.1-evidence-tree-operational-overlay:src/kernel/authoring/module_ir.py`
  - `git show v0.1.1-evidence-tree-operational-overlay:src/kernel/core/rules/where_eval.py`(disabled_locators threading 版本)
  - `git show v0.1.1-evidence-tree-operational-overlay:src/kernel/core/store/_support_capture.py`(disabled_locators threading 版本)
  - 测试文件:replay_substrate / replay_runtime / candidate_diff / evidence_comparison / journey 共 5+ 个

读 old impl 前先读本 bundle 的 architectural 材料,**不要直接 copy old impl 到 redesign branch**(那会再次落入 SDK-substrate 陷阱)。

## 当 bundle 不再需要时

- 当 redesign 已经把所有相关 capability 都 ship 完(或显式 abandoned),本 bundle 可以归到 `docs/blueprints/archive/redesign-2026-05-03-input/` 或类似位置
- 当某个具体 capability 起正式 blueprint,blueprint 应在 §Related Docs 中 cite 本 bundle 内对应章节
- 不要从本 bundle 升级到 active blueprint —— blueprints 必须按 `docs/blueprints/AGENTS.md` 流程独立创建
