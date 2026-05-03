# Conceptual + Interaction Design Discussions

- **Status:** working / venue established 2026-05-03
- **Authority:** non-authoritative。每个 topic doc 是该 topic conceptual + interaction 设计的 source-of-truth(在被对应 blueprint 吸收前)
- **Why this exists:** baseline (`70_codebase-baseline-...md`) 只描述当前代码,blueprint 只描述代码落地。两者之间需要一个 venue 解决"这条 capability **概念上是什么** / 消费者**怎么交互**"。

## 何时新增 topic

- baseline doc 某个 capability section 的 "Open conceptual + interaction questions" 需要回答
- input bundle 已有的 design history / discussion(`10_*` / `40_*`)对某个 capability 不够具体,或需要从 reset-after framing 重新立
- **不**在以下情况新增:
  - 具体代码设计(那是 blueprint)
  - 通用 redesign 流程说明(在 main README)
  - 已经在 baseline `Integration anchors` 节涵盖的 architectural fact

## Topic doc 命名 + 建议结构

- 命名:`<topic-kebab-case>.md`(例:`check-operation-conceptual-interaction.md`)
- 建议 sections(可按 topic 增减,但不要让 doc 退化为代码提案):
  - Status / authority / 关联 baseline section / 关联 blueprint(若已起)
  - **概念定义** — this capability **是什么**;在 B'' framing("rule operable + evidence read-only")的位置
  - **交互定义** — 消费者**给什么、拿什么**;最小输入 / 最小输出;是否需要 partial / streaming
  - **边界决议** — 状态词汇 / engine / persistence / identity / failure mode set 等(由 baseline open questions 抽出)
  - **未决项** — 仍需后续讨论的部分(明确标 unresolved)
  - **与 baseline / blueprint 的对接说明** — baseline 哪些 anchor 被 topic 决议触发回填;blueprint 何时引用本 doc

## Lifecycle

- `draft` → `discussed` → `resolved` → `cited`(被 blueprint §4 Current Context 引用)
- `resolved` 后不可静默改动;若反思要变,起新 doc 或写 explicit supersede note(参考 input bundle `40_design-discussion-A-with-decision-1.md` 的 supersede 风格)
- topic doc **不**升级为 blueprint(blueprint 走 `docs/blueprints/active/` 流程独立创建,引用本 doc)

## 关系图

```
input bundle 左半边(10/20/30/40/50/60)  ← design history + landscape + lessons
baseline 右半边(70)                       ← current code state + open questions
conceptual + interaction venue(80,本目录)← 桥接两边,回答"概念 + 交互"
blueprints(docs/blueprints/active/)       ← 落地代码,引用以上三方
```

## 当前 topic 列表

(空 — 第一个 topic 在第一个 capability 进入概念 + 交互讨论时新增)
