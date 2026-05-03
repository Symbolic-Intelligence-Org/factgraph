# Design History: B → B' → B'' Pivot

- **Status:** working / preserved as design history
- **Why this matters:** redesign 必须知道为什么 evidence 是 read-only(否则会重蹈 B 的覆辙)。这 4 篇文档记录的是 2026-04-30 .. 2026-05-01 期间 design 从 B 到 B'' 的演变,以及为什么 B'' 是当前所有 redesign 工作的非negotiable invariant。

## 4 个文件按时间 + 角色顺序

```
2026-04-30  evidence-tree-context-bprime-2026-04-30.md          B' draft (intervention-protocol-first)
2026-04-30  evidence-tree-proof-recheck-ideas-2026-04-30.md     B' working notes (most concrete spec)
2026-05-01  operational-evidence-tree-rule-replay-design-2026-05-01.md   B'' working notes (pivot crystallized)
2026-05-01  rule-replay-design-synthesis-2026-05-01.md          B'' synthesis (blueprint authors entry)
```

## Pivot 故事(短版)

**B(被否决,从未文档化为正式 draft):** 用户最初直觉是"把 evidence tree 做成可操作 overlay"—— 用户编辑 evidence node,系统局部重计算。

**B'(被推进过,有 1808 行工作笔记):** 试图保留"evidence 可被 typed handle 操作"的 UX 直觉,但显式声明 evidence 不可原地修改;通过 `EvaluationOverlay` + `ProofFrameRechecker` 提供"修改 fact / disable rule + 旧 proof 路径局部诊断 + 完整 re-evaluate"三段式输出。这是 B 的 product 化形态。

**B''(已采纳,成为 v0.1.x 全程 invariant):** 进一步反思后发现 ProofFrameRechecker 仍然依赖"旧 proof 路径还在",在多种 engine native 形态下并不普遍;同时"recheck → 局部重判"和"full evaluate → 权威新结论"之间用户容易混淆。B'' 把 framing 简化:

```
rule operable
evidence read-only
"what if" 全推到 rule 侧
re-evaluate 是唯一权威
```

## 各文件的实际作用(redesign 时怎么读)

### `evidence-tree-context-bprime-2026-04-30.md` (B' draft, 680 行)

- 最简短的 B' 版本:列了 RuleIntervention / IntervenedDerivationEvaluateRequest / apply_intervention_request 等命名
- redesign 不直接用,但记录了"protocol-first intervention"的早期命名,如果新 protocol 想沿用这个命名习惯可参考
- **不读也行**(被 proof-recheck-ideas 和 B'' synthesis 完全覆盖)

### `evidence-tree-proof-recheck-ideas-2026-04-30.md` (B' working notes, 1808 行)

- **最详细的一篇,B' 的核心 spec**
- 包含 `EvaluationOverlay` + `ProofFrameRechecker` + 9 类失败模式 + Status 词汇表的完整设计
- redesign 时如果做 **EvaluationOverlay** / **FactValueOverride** / **Status vocabulary** / **ProofFrameRechecker**,这是首要参考
- B' 的 `ProofFrameRechecker` 在 B'' 中**没被 fully 采纳**(过于复杂),但其失败模式分析(§5.6)对 redesign 仍 valid
- 注意:本文档 framing 是 SDK-side 的,但 redesign 必须搬到 application 层

### `operational-evidence-tree-rule-replay-design-2026-05-01.md` (B'' working notes, 378 行)

- **B'' pivot 的关键文档**
- 显式 reject 了 ProofFrameRechecker,采纳"rule operable + evidence read-only + replay 是唯一权威"
- 包含 B'' 的 11 项 "Suggested First Implementation"(v0.1.x design probe 实际只完成 5/11)
- 包含 "Status Vocabulary"(`derived` / `failed_check` / `below_threshold` / `temporally_unsatisfied` / `unknown` / `unsupported` / `not_materialized`)— **仍是 redesign 的 status 设计起点**
- 包含 "Lazy Why-Not Trace" + "Candidate Universe Boundary" — **仍是 redesign 的 why-not 设计起点**
- 包含 "Adding Conditions And New Variables" — add-condition 设计起点

### `rule-replay-design-synthesis-2026-05-01.md` (B'' synthesis, 较长)

- **redesign blueprint authors 的官方入口**
- 6 stable design principles(rule is operable / evidence is run-derived / patch means recompile / two diff layers / audit events are runtime carriers / candidate universe is boundary)
- 包含 B/B'/B'' 历史对比 + 概念吸收(Parameter Handle / fact what-if vs commit / shared condition identity / rich status vocabulary)
- 包含 market positioning(Decision Assurance / 可审计决策推理工作台,vs IBM ODM / FICO Blaze / Fiddler / Arize)
- redesign 要把整套 framework 重新落地的话,这是**最完整的 design north star**

## Reading suggestion 按 redesign 任务

| Task | 必读 | 选读 |
|---|---|---|
| 起 Check operation 第一稿 | B'' synthesis §6 stable principles + operational §"Check" | proof-recheck-ideas §5(rechecker 不采纳但 failure modes 仍有效) |
| 起 EvaluationOverlay 设计 | proof-recheck-ideas §6 + operational §6.3 v0.1.1 action set | B'' synthesis §"Concepts To Preserve" |
| 起 fact-level overlay | proof-recheck-ideas §5.6.5 fact override active vs witness 警告 | B'' synthesis 整篇做 cross-check |
| 起 Status vocabulary | operational §"Status Vocabulary" | proof-recheck-ideas §5.4 RecheckResult 状态 |
| 起 lazy why-not | operational §"Lazy Why-Not Trace" + §"Candidate Universe Boundary" | proof-recheck-ideas §5.6.6 negation/absence 警告 |
| 起 add-condition | operational §"Adding Conditions And New Variables" | B'' synthesis §"Concepts To Preserve" |
| 起 shared identity | operational §"Condition Ids And Shared Identity" | `feedback_identity_design.md`(memory) |

## 不读这些文档会犯的错(防止重蹈覆辙)

1. **以为 evidence 可以局部修改**(B 错误)→ 读 B'' synthesis §"Evidence Is A Run-Derived View"
2. **以为 ProofFrameRechecker 是必备**(B' 复杂化)→ 读 operational §"Evidence Comparison" 看 B'' 怎么简化
3. **以为多 engine 可以自动统一 evidence**(早期错误)→ 读 B'' synthesis §"Engine Compatibility"
4. **以为 candidate universe 不存在也能做 lazy why-not**(B 时期错觉)→ 读 operational §"Candidate Universe Boundary"
5. **以为可以从 SDK 起 capability 后期再迁 application**(reset 前 strangler 错觉)→ 读 `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_application_first_runtime_authority.md`(reset 后已更新)
