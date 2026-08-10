# Audit: Meander × FactGraph 统一设计 v0.1.1 文本收敛 vs Shipped / Review Evidence

- Status: complete
- Created: 2026-08-10
- Last Updated: 2026-08-10
- Authority: working triage document; informs but does not lock implementation. 本文只完成 Review Freeze v0.1、shipped 锚点与外部对抗审核的 repo-local intake；不授权生成 v0.1.1、修改代码、启动产品实验或关闭任何 load-bearing decision。
- Inputs:
  - [`meander-factgraph-unified-design-review-candidate.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-review-candidate.zh.md), 2185 行，SHA-256 `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7`
  - [`meander-factgraph-unified-design-adversarial-review-disposition.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md), 381 行，SHA-256 `f8a2fedb48f6f3f1b1e19b41cdd7a5823352a59cc74aa8b1068c10aaa7bc6e14`
  - `/Users/zhenzhili/obsidian_workspace/symb-Intelli./claude_report/` 外部审核包（1 主报告 + 7 维度报告 + 2 攻击案例报告）
  - [`01_执行摘要与最终判决.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/01_执行摘要与最终判决.md>), 186 行，SHA-256 `cc6eb3297a4b33ceebbd675eb896b13519a2f183758ca1a03b7dd9a5acc65f3d`；规范锚点 §“下一次决策门槛” `:152-172`
  - [`09_实验路线_停止条件与迁移.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/09_实验路线_停止条件与迁移.md>), 227 行，SHA-256 `7f8f73ce18b8e688daa485cf465a06157993a94bef60ed3b4a03f406df2da474`；规范锚点 §2 `:17-30`、§6 `:124-132`、§12 `:218-227`
  - 本文 §3.3 所列 shipped 文件的 2026-08-10 Rule 1 完整复读
- Outputs / Downstream:
  - 待另行授权的 docs-only blueprint pair：`workflow/blueprints/active/2026-08-10_meander-factgraph-unified-design-v0-1-1{,.audit}.md`
  - 待独立 preflight 与 scoped anchor 后才可创建的 Review Freeze v0.1.1 successor
- Related:
  - [`workflow/CADENCE.md`](../../CADENCE.md)
  - [`workflow/design/README.md`](../../design/README.md)
  - [`workflow/audit/README.md`](../README.md)
- Source intent: Review Freeze v0.1 的 Option 1——只吸收 disposition §6.1 的当前文字一致性项，保留 v0.1 原文与哈希，不吸收远期 gates/decisions。
- Branch: `v0.3.0-meander-factgraph-unified-design-v0-1-1-audit-2026-08-10`

> **一次性 provenance deviation：** 外部冷启动审核先于 canonical audit branch/template 完成。本文使用既有 `vs-shipped` subtype 回灌其 provenance、完整 finding 集与 Option 1 triage；不创设第四种 audit subtype，不把外部报告变成 adopted authority，也不豁免后续独立 preflight。

## 1. Scope

### 1.1 本次审计回答的问题

1. 当前 Review Freeze v0.1 和 disposition 的确切内容身份是什么；
2. 外部审核包能被仓库内复核到什么程度；
3. Option 1 允许 v0.1.1 修改哪些文字，禁止顺带吸收哪些设计；
4. 在进入 blueprint 之前，哪些 provenance、dirty-worktree 和 sacred-branch 风险必须冻结。

### 1.2 In scope

- 冻结 v0.1、disposition、外部审核包、pinned repositories 与产品调研规范来源；
- 复核 83 个 finding ID 的集合完整性与 disposition 算术；
- 将 disposition §6.1 收敛为一份严格 allowlist；
- 对 SF-06、SF-07、RR-10 的最小 shipped 锚点与 AS-10 的文档状态缺口做定向复核；
- 登记 successor、索引、preflight 与 dirty-worktree 的治理约束。

### 1.3 Out of scope

- 不修改 v0.1 Review Freeze；
- 不生成 v0.1.1 successor；
- 不修改 Meander、meander-agent、factgraph-new 或 hnsm-backend 源码/测试/API/schema；
- 不关闭 16 个 `NEEDS_DECISION` finding，不创建或 adopted ADR；
- 不启动 Gate -1、Plan Lab、Translator benchmark、compiler/UI spike 或任何产品建设；
- 不修改 `codex_report/`、`claude_report/`、旧输入 essays 或 shipped pins；
- 不把 `ACCEPT` 理解为“现在全部回填”，也不改变 disposition 的 `32/23/16/10/2` 分布。

## 2. Frozen baseline

### 2.1 Repository and sacred refs

| Object | Frozen state | Audit meaning |
|---|---|---|
| hnsm-backend shipped/design baseline | `dbe79d705a879dda069a0a19b59071ad340bcc76` | provenance-anchor commit 的 parent；不是本轮实现改动 |
| provenance anchor | `cb9dfd55ed710b9aa84e90eec210bd0e8d06b357` | 只新增 v0.1 与 disposition 两份输入 |
| Meander | `4ddb8e36f0b7a80e99a7447c719c21b4776d6ca7` | 外部审核与当前复核 pin 一致 |
| meander-agent | `e4b044911de5495ffa93edeba933985588b51cfa` | 外部审核与当前复核 pin 一致 |
| factgraph-new | `b92d6bf5405be8d15eedea5b97aa7408914e76b9` | 外部审核与当前复核 pin 一致 |
| sacred `master` | `854d03b9a960c0be8c6b86cfd6d2b5ae72bc90b0` | Stage 1 操作前后保持不变 |
| sacred `v0.1-oss-prep` | `MISSING_LOCAL_REF`; remote-tracking ref 亦不存在 | 不伪称已验证、不擅自创建 |

### 2.2 Review inputs

| Input | Lines | SHA-256 | Branch reachability |
|---|---:|---|---|
| Review Freeze v0.1 | 2185 | `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7` | anchored by `cb9dfd55` |
| Disposition matrix | 381 | `f8a2fedb48f6f3f1b1e19b41cdd7a5823352a59cc74aa8b1068c10aaa7bc6e14` | anchored by `cb9dfd55` |

旧 v0.1 必须保持字节不变。若后续流程获批，v0.1.1 应作为 successor 新文件出现，并在 Inputs 中引用 predecessor SHA；不得原位覆盖旧审核对象。

### 2.3 External audit manifest

| File | Lines | Bytes | SHA-256 |
|---|---:|---:|---|
| `2026-08-10_meander-factgraph统一设计对抗审核报告.zh.md` | 458 | 61,495 | `8ac1c7638a82f0a26a5ba2f4a722255370424086f506727af1a8108aa6a41166` |
| `dim1_product-market.zh.md` | 335 | 33,808 | `bdf840bfa593f4603f48101ecd463e44f546316eb8653e8b3b2627282e3ba34d` |
| `dim2_semantic-core.zh.md` | 284 | 36,839 | `5056a8bed0b7f71d9dec2ea9f4c84c9fd445159802652fdcfd3e6ea536438c05` |
| `dim3_shipped-fidelity.zh.md` | 266 | 32,308 | `5245e7be4b74827abf9c05ea9e5af8313e4ce41b565fbf0bca3c301b14ce4b48` |
| `dim4_agent-authority-security.zh.md` | 299 | 43,762 | `9bde0d28e400117c039eb3345b7d3f9124518e1d685224b652ba7878c26a8349` |
| `dim5_run-replay-persistence.zh.md` | 299 | 38,769 | `f0283b50b5b6d0b9b851e751b0dd5fa9a050a7b8a82746feeb442331d1dc9e5c` |
| `dim6_ui-failure-semantics.zh.md` | 200 | 28,085 | `33a1b46c6c3e560288b7480f4aa2eeb6c04b9b79c55db289d5bdf509b3e13310` |
| `dim7_complexity-economics.zh.md` | 348 | 38,560 | `c94da00e5f67ebfab08f0b4b3d321b98ef9a4247462006a8804011a802a8e7c4` |
| `attack_cases_01-13.zh.md` | 299 | 37,564 | `c008adddc7c208960f3cb07e31227bafb87c84a6adae13b79fcfa5951ca58dd9` |
| `attack_cases_14-25.zh.md` | 243 | 38,282 | `1bfead11fbe67b847bdabc12a19f9799147febf738da585d5a113e92c48fd603` |
| **Total** | **3031** | **389,472** | per-file identity above |

### 2.4 Normative product-gate inputs

| File | Lines | SHA-256 | Exact load-bearing anchors |
|---|---:|---|---|
| `codex_report/01_执行摘要与最终判决.md` | 186 | `cc6eb3297a4b33ceebbd675eb896b13519a2f183758ca1a03b7dd9a5acc65f3d` | `:154-168`: Gate -1、Translator/Vertical/independent-product gates；尤其 `:156` 的 ≥5 walkthrough/case bundle/四臂/双报价，以及 `:168` 的 10-offer 与 >50% 条件 |
| `codex_report/09_实验路线_停止条件与迁移.md` | 227 | `7f8f73ce18b8e688daa485cf465a06157993a94bef60ed3b4a03f406df2da474` | `:17-30`: Phase -1 DoD；`:124-132`: customer-defined 30% target、10-offer stop；`:220-225`: 总停止判决与 >50% 适用范围 |

这些外部研究输入以内容哈希而非绝对路径作为本轮身份。v0.1.1 可以规范引用其 gate/DoD，但不得把本地摘要升级为更高 authority，也不得把 30% 与 50% 泛化成一个统一阈值。

## 3. Evidence method and limits

### 3.1 Finding completeness

外部审核包中的正式 finding 集经独立枚举后恰为 83 条且无重复：

- PM-01…PM-10（10）；
- SC-01…SC-12（12）；
- SF-01…SF-08（8）；
- AS-01…AS-11（11）；
- RR-01…RR-11（11）；
- UI-01…UI-10（10）；
- CE-01…CE-11（11）；
- AC-01…AC-05、AC-16、AC-18、AC-21、AC-22、AC-24（10）。

`AC-17` 只被交叉引用，不是独立 finding。83 个 ID 与 disposition 的 83 行一一相等；其处置算术为：

```text
ACCEPT                  32
ACCEPT_WITH_NARROWING   23
NEEDS_DECISION          16
DEFER_TO_PHASE_GATE     10
REJECT_AS_MISREAD        2
TOTAL                   83
```

双裁定必须保持分离：架构为 `REVISE`；产品授权为 `STOP-except-discovery`。二者不能平均为总分，也不构成实现授权。

### 3.2 External-evidence limits

- 外部主报告自述 28 个子代理、约 290 万 tokens、18 条高严重度独立验证；目录未保留 18 份验证原始输出和完备性批评员原稿，因此本文只把这些数字称为报告自述。
- 主报告自述的 18 条验证分布为 `CONFIRMED 12 / PLAUSIBLE 5 / REFUTED 1`；65 条 MEDIUM/LOW 未逐条对抗验证。
- 外部报告没有记录被审候选 SHA，且报告间存在 2185/2186 行漂移；外部行号只作导航，当前 v0.1 身份只由本审计冻结的 SHA 确定。
- SHA 证明内容完整性，不证明作者身份、研究方法或结论正确性。
- 外部绝对路径不是长期可移植证据。本轮用 manifest + repo-local disposition 固定边界，不把十份报告未经授权整体 vendoring 进仓库。

### 3.3 Current-session Rule 1 full reads

在本 audit row 起草/修订期间，实际承重的四份 shipped 文件已按 Rule 1 完整逐行复读；不是只读 grep/head/tail：

| Repository pin | File | Lines | SHA-256 | Full-read owner |
|---|---|---:|---|---|
| Meander `4ddb8e36f0b7a80e99a7447c719c21b4776d6ca7` | `src/meander/plans/ingest.py` | 1390 | `84ccc1160d406312c9c9c0c6a985380af61889460f15e652524b62579d41f60d` | primary drafter |
| hnsm `dbe79d705a879dda069a0a19b59071ad340bcc76` | `src/factgraph/application/protocol/rule.py` | 677 | `e975e44ff52b6899930044911bfc4813dc9eda9907769c4ffdfd87567caece41` | primary drafter |
| hnsm `dbe79d705a879dda069a0a19b59071ad340bcc76` | `src/factgraph/application/explain/evidence_tree.py` | 602 | `9993390b0af57158e77ef5b6e9730a3a5a61cfad866062cb7a70fb1c45a8dfe8` | primary drafter |
| hnsm `dbe79d705a879dda069a0a19b59071ad340bcc76` | `src/factgraph/sdk/store.py` | 5160 | `e4dd5fdc302f9d099ac5aee0024f89b1623e77b11df16186a7ba7b525c514e70` | independent full-file reader; primary drafter separately spot-checked load-bearing regions |

完整复读后，Option 1 会引用的具体锚点如下：

| Concern | Independently rechecked evidence |
|---|---|
| governance/write boundary | Meander `plans/ingest.py:1078-1095` 是 governance gate；`:1140-1169` 是 graph-write 到 accepted transition；`:1158-1166` 明示 write-failure rollback/revocation 与无有效事实状态的区别 |
| occurrence anchor | hnsm `application/protocol/rule.py:218-238`：`:218` 是 `RulePortRef`，`:238` 才是 `RuleOccurrence` |
| evidence type anchor | hnsm `application/explain/evidence_tree.py:143-160`：`EvidenceTimeline` 在 `:143`，`EvidenceGraph` 在 `:155` |
| manual/live Explain scope | hnsm `sdk/store.py:3020-3045` 的 manual Explain 重新 evaluate；Soufflé/ProbLog 首选 reach builders 在 `:3413`/`:3453` 传入 `self._store`；native probe 在 `:3575` 从 live ledger 投影 facts |

四份文件合计 7829 行。完整复读没有发现推翻 SF-06/SF-07/RR-10 的反例；同时没有把这些局部结论扩张为对整个 target architecture 的 shipped 证明。后续 blueprint 仍须把独立 preflight 设为 required，并在 preflight-row drafting 时按当时固定的文件/hash 再读；Stage 1 full read 与 Step 4.3 independent preflight 不能互相替代。

## 4. Triage table

### 4.1 `(a) shipped covers` — 保留，不改代码

| ID | Commitment | Evidence/status | Option 1 action |
|---|---|---|---|
| A-01 | v0.1 对 shipped continuity 的主体描述仍是基线，不因 wording 修订改写运行时 | 外部 shipped-fidelity 报告给出 24 锚点 `21 yes / 3 partial / 0 no`；本审计只独立复核与 Option 1 相关的 3 组 partial/范围低描述 | 只刷新锚点和精确措辞；不改 shipped claim、代码或迁移语义 |
| A-02 | Review Freeze 的 candidate/non-authoritative authority 不变 | `workflow/design/README.md` 明定 design-point 不能直接覆盖 shipped 行为 | v0.1.1 继续显式声明非 adopted、非实现授权 |
| A-03 | disposition 的 `32/23/16/10/2` 与双裁定保持 | 83 行与外部 ID 集精确相等 | 不重算、不升降 finding、不把 ACCEPT 变 backlog |

### 4.2 `(b) small gap` — Option 1 唯一内容 allowlist

| Work item | Finding(s) | Exact gap | Allowed v0.1.1 correction | Explicit boundary |
|---|---|---|---|---|
| O1-01 | PM-01 | §0.4/§17 只让 Phase 2+ 明确受产品门约束，Phase 0/1 可被误读为绕门 | Phase 0/1 也以 Gate -1 为前置；唯一例外是用户另行明确批准、预算封顶、可丢弃且不得倒逼产品结论的 discovery-parallel experiment | 不移动或启动任何 spike |
| O1-02 | PM-04, CE-11 | Phase -1/§18.7 的本地定性摘要弱于调研 Gate -1/DoD | 规范引用 `codex_report/01` Gate -1 与 `codex_report/09` §2；保留 ≥5 walkthrough、合法 case bundle、四臂、双报价、有成本 pilot，以及各自适用的 30%/50%/10-offer 口径 | 不把 30% 或 50% 变成统一阈值；不替 PM-03 决定 packaging |
| O1-03 | PM-02, PM-08 | D01/wedge 开放时，§1.1 仍把 Agent 轴产品核心标成 settled，P0 又被称为 default MVP | 产品轴改为 source-bound case/draft Verify/review；Agent output/intent 只是输入类别之一；§1.1 降为 provisional/experiment-required；§1.3/P0 改称 post-gate Agent/compatibility cell/profile | 保留 Agent-specific target flows、L0–L3 与 A0–A2，不删除技术探索 |
| O1-04 | CE-01 | `smallest` 未限定比较范围，可能把完整 target review map 误作一次实现负担 | 限定为 `smallest coherent review map for the stated scope`；声明每个获批 phase 只以其列明 artifact/deliverable 为边界 | 不吸收 CE-02 burden ledger，不删类型、不重排架构 |
| O1-05 | terminology hygiene | §22.5 的 `named blockers before the experiment` 与“0 BLOCKER 存活”混用 | 改为 `named phase-specific required revisions/gates close by their assigned gate` | 不修改外部历史报告，不重定 severity |
| O1-06 | SF-06 | rejected write-failure 可能有 revoked append-only traces，`no Claim write` 过强 | 区分 blocked/validation-rejected 与 write-failure；统一为无有效 Claim 状态/不进入 evaluation，后者可有 revoked traces | 不改 §2.4 的 run-local Scenario `never written` |
| O1-07 | SF-07 | §2.6 三组行号漂移 | 刷新 governance/write、RuleOccurrence、EvidenceTimeline/EvidenceGraph 锚点到 §3.3 所列位置 | 只改引用，不扩写 shipped 结论 |
| O1-08 | AS-10 | §16.4–16.6 缺 v0.1 自己要求的状态标签 | §16.4 `SETTLED DIRECTION`；§16.5 `PROVISIONAL`；§16.6 Verify 隔离为 `SETTLED DIRECTION`、future Decision profile 仍 `DEFERRED` | 没有真实 adopted ADR，不得伪标 `ADOPTED CONSTRAINT` |
| O1-09 | RR-10 | §2.6 只说 native lazy probe 读 live ledger，低描述 lowering-plan-backed Soufflé/ProbLog 首选路径 | 明写 manual `fg.eval.explain(expr, head=...)` 对其接受的 Rule/RuleExpr 发起一次新 `_evaluate`；对 lowering-plan-backed Rule/RuleExpr 的 lazy row Explain，native probe 与 Soufflé/ProbLog 首选 reach builder 在执行时读取当前 attached Store/Ledger，并引用 `:3020-3045/:3367-3503/:3575` | 不泛化为所有输入或 fallback：无 lowering plan 或 reach 失败时可退回 evaluation-time captured artifact/envelope/minimal graph；不顺手实现 RR-01 digest guard/replay |
| O1-10 | successor metadata/governance | v0.1 header 仍写“no review result exists yet”，且 successor 需要明确 lineage | v0.1.1 title/header/Inputs/Outputs/§23 机械更新；引用 v0.1 SHA、disposition 与本 audit；声明只吸收 Option 1 | predecessor 字节不变；不把 metadata 更新扩成 v0.2 |

### 4.3 `(c) shape conflict` — 保持 open，禁止进入 v0.1.1

16 个 `NEEDS_DECISION` finding 保持原状态：

```text
PM-03 PM-06
CE-03 CE-05 CE-06 CE-08
SC-01 SC-03 SC-05 SC-12
SF-04
AS-02 AS-06 AS-11
AC-16 AC-24
```

这包括 packaging、join×Any、Rule capability、digest、dual-run、tenant、retention/replay、source admission、self-support、mandatory completeness 等承重分叉。Option 1 不创建 ADR、不补 D 编号，也不通过 wording 预选答案。

### 4.4 `(d) genuinely new` — 后续 phase/gate 才可能承重

Translator protocol、Policy compiler/evaluator contracts、Run/replay、Scenario、Assessment/UI、L1/MCP、A1、L0 Translator 与 cross-repository migration 的实现均是未来能力。它们可以留在 conditional target architecture 中供评审，但不能因本轮文本收敛变成已授权 MVP、blueprint 或 shipped capability。

### 4.5 `(e) deferred-aligned` — 原样后置

`DEFER_TO_PHASE_GATE` 的 10 项继续按 disposition 所列 Gate -1/Phase 1/2/3/6/7 关闭；`REJECT_AS_MISREAD` 的 CE-10 与 AS-04 不进入 Option 1 backlog。任何未列入 §4.2 allowlist 的 `ACCEPT`/`ACCEPT_WITH_NARROWING` 也仍按各自 phase gate 后置，不因处置标签而自动回填。

## 5. Open questions and cadence routing

### 5.1 No new ADR in Option 1

本 slice 不回答 load-bearing question，只纠正已由 disposition 收窄后的授权与文档一致性。因此 CADENCE Stage 2 ADR 可显式跳过；16 个 `NEEDS_DECISION` 仍开放。

### 5.2 No post-Q synthesis

本 slice 没有 Q closure chain；Option 1 的 **actionable subset** 只落在一个 docs-only small-gap bucket，其余 findings 维持 open/deferred/refuted。因此 Stage 3 synthesis 可跳过；本文自身即为 blueprint 的审计输入，不冒充 post-Q synthesis。

### 5.3 Required later gates

后续每一步均需新的明确“可以推进”或等价授权：

1. blueprint draft + paired audit log；
2. independent preflight；
3. preflight amendment/self-check；
4. scoped anchor；
5. v0.1.1 docs implementation；
6. closure；
7. archive；
8. push/merge/canonical integration。

## 6. Frictions and preservation locks

### F-01 — mixed dirty index

`workflow/design/design-points/README.md` 在 Stage 1 前已是一个混合大 hunk，除本项目两行外还包含用户既有 active-table 重写与 archive batch。`workflow/blueprints/archive/INVENTORY.md` 也已 dirty。后续不得 `git add` 整份文件；blueprint/preflight 必须选择最小 index-only hunk、等待上游用户改动先落地，或显式记录无法安全更新的阻塞。

### F-02 — predecessor/successor lifecycle

v0.1 是已审计的 frozen input；v0.1.1 应作为 active successor，并在 Inputs 引 predecessor。若按 design-point supersession 归档 v0.1，必须保持旧文件内容与 SHA 不变，使用 `git mv`，同步修正最小 cross-link；不能通过改写旧文件伪造连续版本。

### F-03 — full-source preflight remains mandatory

本 intake 已完成 §3.3 四份承重文件的 Rule 1 完整复读，但不能替代未来 implementation preflight 在其自身固定输入、hash 与时间点上的独立完整复核。docs-only 不等于免审；由于这是 architecture-facing 且要求 exact Review Freeze fidelity，后续 preflight 作为 required，而不是 optional convenience。

### F-04 — unrelated dirty preservation

Stage 1 provenance anchor 后、本文尚未加入 index 时，排除本文这一项 in-scope untracked artifact 后，unrelated dirty baseline 恰为 112 行；`git status --porcelain=v1 --untracked-files=all` 的精确输出 SHA-256 为 `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326`，index 为空。该基线包含既有 notebooks、workflow archive moves、design/decision edits、examples、test/vendor folders 与 session records；精确 manifest 如下。后续各 commit 必须继续用 pathspec allowlist，并在本文提交后证明 status 输出仍为同一 112 行、同一 hash；不得误 stage、restore 或改写其中任何一项。

```text
 M .claude/launch.json
 M examples/04_round_persistence_diff.ipynb
 M examples/05_sdk_assertion_views.ipynb
 M examples/06_workspace_lifecycle_v030.ipynb
 M examples/aml_compliance_manual_demo.ipynb
 M examples/rule_composition_demo.ipynb
 M examples/rule_structure_demo.ipynb
 D workflow/blueprints/active/2026-03-31_ontology-feasibility-analysis.audit.md
 D workflow/blueprints/active/2026-03-31_ontology-feasibility-analysis.md
 M workflow/blueprints/active/2026-03-31_ontology-integration-concept.md
 M workflow/blueprints/active/2026-04-03_market-alignment-guide.md
 D workflow/blueprints/active/2026-06-26_rule-structure-impl.audit.md
 D workflow/blueprints/active/2026-06-26_rule-structure-impl.md
 D workflow/blueprints/active/2026-06-26_rule-structure-narrate-alignment.audit.md
 D workflow/blueprints/active/2026-06-26_rule-structure-narrate-alignment.md
 M workflow/blueprints/archive/INVENTORY.md
 M workflow/design/decisions/active/2026-06-26_evidencegraph-readonly-and-rule-structure-type.md
 M workflow/design/design-points/README.md
 D workflow/design/design-points/active/rule-structure-narrate-alignment.zh.md
 D workflow/design/design-points/active/rule-structure-static-projection.zh.md
?? .vscode/launch.json
?? examples/explain_complex_engines_demo.ipynb
?? examples/meander_test.ipynb
?? meander-agent-test/meander_agent_smoke_test.ipynb
?? "rainbird-ai sdk code/sdk-demo-main/.eslintrc.cjs"
?? "rainbird-ai sdk code/sdk-demo-main/.gitignore"
?? "rainbird-ai sdk code/sdk-demo-main/.prettierrc"
?? "rainbird-ai sdk code/sdk-demo-main/README.md"
?? "rainbird-ai sdk code/sdk-demo-main/index.html"
?? "rainbird-ai sdk code/sdk-demo-main/init.js"
?? "rainbird-ai sdk code/sdk-demo-main/jsconfig.json"
?? "rainbird-ai sdk code/sdk-demo-main/package.json"
?? "rainbird-ai sdk code/sdk-demo-main/src/App.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/App.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/assets/favicon-96x96.png"
?? "rainbird-ai sdk code/sdk-demo-main/src/assets/image.png"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Autocomplete/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Autocomplete/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Button/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Button/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Error/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Input/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Input/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Label/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Label/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Loading/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/NotImplemented/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Select/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/common/Select/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/forms/QueryForm/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/forms/QueryForm/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/forms/QuestionForm/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/forms/QuestionForm/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/forms/SessionForm/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/forms/SessionForm/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/index.js"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/rainbird/Interact/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/rainbird/Interact/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/rainbird/Query/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/rainbird/Result/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/rainbird/Result/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/rainbird/Start/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/wrappers/InteractionWrapper/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/components/wrappers/QueryWrapper/index.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/src/hooks/index.js"
?? "rainbird-ai sdk code/sdk-demo-main/src/hooks/useGoal.js"
?? "rainbird-ai sdk code/sdk-demo-main/src/hooks/useInteractState.js"
?? "rainbird-ai sdk code/sdk-demo-main/src/hooks/useSession.js"
?? "rainbird-ai sdk code/sdk-demo-main/src/index.css"
?? "rainbird-ai sdk code/sdk-demo-main/src/main.jsx"
?? "rainbird-ai sdk code/sdk-demo-main/vite.config.js"
?? "rainbird-ai sdk code/sdk-demo-main/yarn.lock"
?? "rainbird-ai sdk code/sdk-go-master/.gitignore"
?? "rainbird-ai sdk code/sdk-go-master/.gitlab-ci.yml"
?? "rainbird-ai sdk code/sdk-go-master/LICENSE"
?? "rainbird-ai sdk code/sdk-go-master/README.md"
?? "rainbird-ai sdk code/sdk-go-master/answer.go"
?? "rainbird-ai sdk code/sdk-go-master/answer_test.go"
?? "rainbird-ai sdk code/sdk-go-master/client.go"
?? "rainbird-ai sdk code/sdk-go-master/client_test.go"
?? "rainbird-ai sdk code/sdk-go-master/cmd/rb/README.md"
?? "rainbird-ai sdk code/sdk-go-master/cmd/rb/main.go"
?? "rainbird-ai sdk code/sdk-go-master/constants.go"
?? "rainbird-ai sdk code/sdk-go-master/evidence.go"
?? "rainbird-ai sdk code/sdk-go-master/go.mod"
?? "rainbird-ai sdk code/sdk-go-master/go.sum"
?? "rainbird-ai sdk code/sdk-go-master/interaction.go"
?? "rainbird-ai sdk code/sdk-go-master/options.go"
?? "rainbird-ai sdk code/sdk-go-master/question.go"
?? "rainbird-ai sdk code/sdk-go-master/question_test.go"
?? "rainbird-ai sdk code/sdk-go-master/session.go"
?? "rainbird-ai sdk code/sdk-go-master/session_test.go"
?? workflow/audit/active/2026-08-08_active-design-point-governance-vs-shipped.md
?? workflow/blueprints/archive/2026-03-31_ontology-feasibility-analysis.audit.md
?? workflow/blueprints/archive/2026-03-31_ontology-feasibility-analysis.md
?? workflow/blueprints/archive/2026-06-26_rule-structure-impl.audit.md
?? workflow/blueprints/archive/2026-06-26_rule-structure-impl.md
?? workflow/blueprints/archive/2026-06-26_rule-structure-narrate-alignment.audit.md
?? workflow/blueprints/archive/2026-06-26_rule-structure-narrate-alignment.md
?? workflow/design/decisions/active/2026-08-08_q1-exists-authority-drift-decision.md
?? workflow/design/design-points/active/premise-effective-view-and-scenario-resolution.zh.md
?? workflow/design/design-points/active/rule-addressing-semantic-ports-and-evaluation-target.zh.md
?? workflow/design/design-points/active/scenario-plan-what-if-run-and-policy-aware-explain.zh.md
?? workflow/design/design-points/archive/rule-structure-narrate-alignment.zh.md
?? workflow/design/design-points/archive/rule-structure-static-projection.zh.md
?? workflow/memory/session_exports/2026-08-10_meander-product-design_thread-019fdbfb/README.md
?? workflow/memory/session_exports/2026-08-10_meander-product-design_thread-019fdbfb/conversation.md
?? workflow/memory/session_exports/2026-08-10_meander-product-design_thread-019fdbfb/manifest.json
?? workflow/memory/session_exports/2026-08-10_meander-product-design_thread-019fdbfb/messages.jsonl
?? workflow/memory/session_exports/2026-08-10_meander-product-design_thread-019fdbfb/thread_snapshot.json
?? workflow/memory/session_handoffs/2026-07-10_meander-design-consolidation.md
?? workflow/memory/session_handoffs/2026-07-16_hypothesis-mechanism-campaign.md
```

## 7. Recommendations for the docs-only blueprint

1. 文件 allowlist 只包括：新 blueprint pair、独立 preflight、v0.1.1 successor、旧 v0.1 的字节不变 lifecycle move、disposition 的最小 successor cross-link/status note，以及能安全隔离的最小索引项。
2. 内容 allowlist 只包括 §4.2 的 O1-01…O1-10；每项在 blueprint acceptance 中一一对应。
3. 明确 non-goals：所有代码、测试、API/schema、83 finding 的其余内容、任何产品/spike 运行、任何 adopted ADR。
4. preflight 必须重新计算 predecessor/successor SHA、逐项核对 Option 1 diff，并完整重读其实际使用的 shipped evidence files。
5. implementation review 应使用语义 diff + exact predecessor hash 检查，证明 v0.1 未被静默覆盖且 v0.1.1 没吸收 phase-gated内容。

## 8. Audit method notes

- 使用 canonical `vs-shipped` subtype 承接外部审核回灌，是一次 retroactive provenance deviation；没有新增 subtype。
- 分支名遵循仓库 `v<version>-<topic>-audit-<date>` 规范；最初的桌面环境 `codex/` namespace 已在下一提交前纠正，未推送旧 ref。
- v0.1 与 disposition 原为工作区 untracked direct inputs；用精确 pathspec 在 `cb9dfd55` 固定。没有 stage 混合 dirty README/INVENTORY 或其他用户文件。
- Stage 2/3 跳过理由见 §5；不影响后续 blueprint/preflight 的完整 cadence。
- 本次 Stage 1 依据用户“可以推进选项 1”一次性完成 provenance anchor + repo-local intake，没有按 CADENCE Stage 1 的内部 batch 逐批交付用户 review；这是 docs-only retroactive intake 的明确 cadence deviation。它只覆盖 Stage 1，不构成下一阶段预授权。
- 本文不把外部“未找到”升级成市场不存在，也不把哈希、finding 数或多代理规模当作需求/正确性的替代证据。

## 9. Audit completeness checklist

- [x] v0.1、disposition、外部审核包与 repo pins 已冻结
- [x] 83 个正式 finding 的集合、计数与 disposition 算术已复核
- [x] 架构 `REVISE` 与产品 `STOP-except-discovery` 双裁定保持分离
- [x] Option 1 allowlist 与明确 non-goals 已逐项列出
- [x] SF-06/SF-07/RR-10 的四份实际承重 shipped 文件已完整复读；AS-10 文档缺口已复核
- [x] 外部证据、行数漂移、原始验证缺失与非可移植路径限制已记录
- [x] unrelated dirty、sacred refs 与 branch/provenance anchor 已记录
- [x] Stage 2/3 跳过理由和后续逐阶段授权门已记录
- [x] 本 intake 未修改 Review Freeze、shipped code 或用户其余 dirty 文件

## 10. Stage 1 result

Stage 1 结论：**Option 1 可以进入 docs-only blueprint 起草，但不能自动跨门。** 其唯一合法内容范围是 §4.2 的十项；旧 v0.1 保持 exact SHA，v0.1.1 必须是显式 successor。进入 blueprint draft 前仍需用户下一次明确授权。
