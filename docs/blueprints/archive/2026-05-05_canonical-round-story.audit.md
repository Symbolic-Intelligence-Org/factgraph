# Canonical Round Story — Audit Log

- Blueprint: [2026-05-05_canonical-round-story.md](./2026-05-05_canonical-round-story.md)
- Parent plan: [2026-05-05_round-story-completion-plan.md](../active/2026-05-05_round-story-completion-plan.md) §5.1

## Event Log

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-05-05 | draft | Blueprint created | Batch 1 of round story completion plan;wording-only alignment of 5 canonical questions across demo (.py + .ipynb) / examples/README.md / tutorials/evidence-pipeline.cn.md (§1/§7/§8) + new short capability-decision-tree.cn.md;branch `v0.1-canonical-round-story-2026-05-05` cut off `adf8780`(Batch 0 final) |
| 2026-05-05 | scoped | Scope approved | Draft reviewed against master plan §5.1;accepted as wording-only with no algorithm / DTO / runtime changes;implementation may begin |
| 2026-05-05 | implementing | Scope wording tightened before bulk edits | Subagent review surfaced wording risks:capability count boundary, bilingual canonical wording, notebook-not-derived assumption, and final worktree acceptance;blueprint tightened while preserving master plan §5.1 decision-tree deliverable |
| 2026-05-05 | implemented | Canonical wording implemented | Q1-Q5 wording aligned across demo script, notebook markdown, examples README, evidence tutorial §1/§7/§8, and new capability decision tree;focused verification passed;no `src/` diff |

## Decision Notes

### 2026-05-05 — Batch Origin

Master plan §5.1 entry criteria 全满足:Batch 0 闭环(`adf8780`),工作树仅 `M memory/current.md` lightweight sync。Branch 按 §7.2 命名规范新开,off Batch 0 final state。本批 scope **严格 wording-only**,任何越界(改 demo 算法 / 改 protocol / 加新 capability 段)即违反 master plan §5.1 exit criteria。

### 2026-05-05 — Canonical Wording 复用 Master Plan

5 个 question 文字直接复用 master plan §5.1 表,本 blueprint **不重新定义**;若 wording 需调,master plan 须先改。这是为了让"canonical"不被多源稀释。

### 2026-05-05 — capability-decision-tree.cn.md 选择新建而非合入 evidence-pipeline.cn.md

evidence-pipeline.cn.md 已 ~830 行,内容是 reference-style(逐层讲机理)。decision tree 是 task-style(给定问题选 capability),目标读者与切入点不同。合入会拖累 reference doc 阅读节奏;独立短文(≤120 行)更易消费。

### 2026-05-05 — Pre-Implementation Review Tightening

Subagent review found four wording/scope risks before implementation:the draft said "5 application capability + 1 evaluator-layer" while Q5 is the evaluator-layer line;Chinese tutorial acceptance could accidentally allow localized paraphrases to drift from the English canonical source;the notebook is a bespoke narrative notebook rather than a mechanical .py mirror;and final worktree acceptance needed to mean after the implementation commit.

Decision:use "4 application capability + 1 evaluator-layer capability(5 shipped capability lines)" as ownership wording;require Chinese docs to carry the English canonical question verbatim next to Chinese explanation;align notebook opening list / phase headings / wrap-up bullets rather than assuming `_announce` parity;clarify final worktree acceptance as post-commit. The new decision-tree document remains in scope because master plan §5.1 explicitly lists it as an exit criterion.
