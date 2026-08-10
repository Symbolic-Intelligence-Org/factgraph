# Task Blueprint: Meander × FactGraph 统一设计 Review Freeze v0.1.1 文本收敛

- Status: draft
- Created: 2026-08-10
- Last Updated: 2026-08-10
- Authority: task-scoped docs-only blueprint. 本文只约束 O1-01…O1-10 的候选文本收敛；不 adopted 目标设计，不覆盖 shipped 行为，也不授权代码、产品建设或实验。
- Inputs:
  - [`2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md`](../../audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md), Stage 1 commit `e32ec385427a5eabb4645d3a4da06cef3c9fe652`, 394 行，SHA-256 `0d1dfb6a5236d15fc8d9ba8624cdc2317915d3a77dc7e5c0ed042b0e429d9329`
  - [`meander-factgraph-unified-design-review-candidate.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-review-candidate.zh.md), frozen v0.1 predecessor, 2185 行，SHA-256 `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7`
  - [`meander-factgraph-unified-design-adversarial-review-disposition.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md), 381 行，SHA-256 `f8a2fedb48f6f3f1b1e19b41cdd7a5823352a59cc74aa8b1068c10aaa7bc6e14`
  - [`01_执行摘要与最终判决.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/01_执行摘要与最终判决.md>), 186 行，SHA-256 `cc6eb3297a4b33ceebbd675eb896b13519a2f183758ca1a03b7dd9a5acc65f3d`；承重锚点 `:154-168`
  - [`09_实验路线_停止条件与迁移.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/09_实验路线_停止条件与迁移.md>), 227 行，SHA-256 `7f8f73ce18b8e688daa485cf465a06157993a94bef60ed3b4a03f406df2da474`；承重锚点 `:17-30/:98-106/:124-132/:220-225`
  - [`2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md`](../../audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md), independent Step 4.3 artifact on commit `c59bfc77b2a7f316fd750e2d413e979fb532ea63`, 353 行，SHA-256 `0b2702d36310161e7df1c29b1880c7f7d167abc4f528140cda9fe0ebc30146b4`, Git blob `6f17cdfb2f73732e34fa3e07d03f7cbc2a1c8521`
- Outputs / Downstream:
  - completed independent preflight remains on its independent branch until Step 4.9 reconciliation; Step 4.7 consumes the fixed commit/blob above rather than a floating branch
  - future active successor: `workflow/design/design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md`
  - minimal successor cross-link/status update in the disposition and a safely isolated design-point index entry
- Related:
  - [`workflow/CADENCE.md`](../../CADENCE.md)
  - [`workflow/blueprints/README.md`](../README.md)
  - [`workflow/design/README.md`](../../design/README.md)
  - [`workflow/audit/README.md`](../../audit/README.md)
- Branch: `v0.3.0-blueprint-meander-factgraph-unified-design-v0-1-1-2026-08-10`
- Fork Basis: `e32ec385427a5eabb4645d3a4da06cef3c9fe652`
- Related Modules:
  - `(none — docs-only slice; Meander and FactGraph runtime modules remain read-only evidence)`
- Related Repositories:
  - `hnsm-backend@dbe79d705a879dda069a0a19b59071ad340bcc76` — shipped evidence baseline; workflow docs are the only future write target
  - `meander@4ddb8e36f0b7a80e99a7447c719c21b4776d6ca7` — read-only evidence only
  - `meander-agent@e4b044911de5495ffa93edeba933985588b51cfa` — read-only evidence only
  - `factgraph-new@b92d6bf5405be8d15eedea5b97aa7408914e76b9` — read-only compatibility evidence only
- Audit Log:
  - [`2026-08-10_meander-factgraph-unified-design-v0-1-1.audit.md`](./2026-08-10_meander-factgraph-unified-design-v0-1-1.audit.md)

## 1. Problem

Review Freeze v0.1 已经完成冷启动对抗审核和 83 条 finding 的逐项处置，但其正文仍保留几组会误导下一位读者的当前一致性问题：Phase 0/1 的产品门弱于规范研究结论，Agent 被过早写成产品轴和默认 MVP，若干 shipped 描述/代码锚点过强或漂移，审阅状态与术语仍停留在“尚未审阅”。

用户选择 disposition 的 Option 1：只生成 v0.1.1 successor，吸收“下一版候选文本前”必须修正的内容。本任务的难点不是重新设计，而是证明每个 semantic edit atom 都且只属于 O1-01…O1-10，并证明没有借文字修订关闭开放决定、启动产品建设或改变任一仓库运行行为。

## 2. Goals

1. 创建独立、可追溯的 v0.1.1 successor，不原位改写 frozen v0.1。
2. 逐项且仅吸收 Stage 1 audit §4.2 的 O1-01…O1-10。
3. 保持两个独立裁定：architecture `REVISE`；product authorization `STOP-except-discovery`。
4. 保持 16 项 `NEEDS_DECISION`、`32/23/16/10/2` disposition 分布和 candidate/non-authoritative authority 不变。
5. 精确修正 SF-06、SF-07、RR-10 的 shipped 描述与锚点，不把修辞修正写成 shipped capability 或运行时修复。
6. 用 predecessor hash、semantic-edit-atom ledger、semantic diff、path allowlist 和独立 preflight 证明范围没有泄漏。

## 3. Non-goals

- 不修改 Meander、meander-agent、factgraph-new 或 hnsm-backend 的源码、测试、API、schema、fixture、notebook 或模块 docs。
- 不修改、移动或归档 v0.1 predecessor；其路径、内容和 SHA 在本 slice 全程保持不变。
- 不创建 v0.2 候选，不重写统一架构，不删除 target DTO/阶段/Agent flows。
- 不启动或运行 Gate -1、Plan Lab、Translator benchmark、Policy compiler/UI spike、pilot 或产品实验。
- 不宣称 buyer、workflow、packaging、付费意愿、Translator 质量或市场楔子已经验证。
- 不创建/adopt ADR，不关闭或预选以下 16 项：

```text
PM-03 PM-06
CE-03 CE-05 CE-06 CE-08
SC-01 SC-03 SC-05 SC-12
SF-04
AS-02 AS-06 AS-11
AC-16 AC-24
```

- 不把其余 73 条 finding 或所有 `ACCEPT`/`ACCEPT_WITH_NARROWING` 转成当前 backlog。
- 不实现 RR-01 digest guard/replay，不修 join×Any，不决定 Policy v0、dual-run、tenant、retention、source admission、self-support 或 mandatory Policy completeness。
- 不修改外部 `codex_report/`、`claude_report/` 或任何 Meander 仓库文件。
- 不 stage、restore、格式化或覆盖 112 项 unrelated dirty baseline；不整文件 stage 已混杂修改的 design-point index。
- 不 push、merge、创建 release ref 或修改 sacred branch。

## 4. Current Context

### 4.1 Frozen coordinates and verdicts

| Coordinate | Frozen value |
|---|---|
| Stage 1 audit branch tip / blueprint fork basis | `e32ec385427a5eabb4645d3a4da06cef3c9fe652` |
| v0.1 predecessor SHA | `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7` |
| disposition SHA before implementation | `f8a2fedb48f6f3f1b1e19b41cdd7a5823352a59cc74aa8b1068c10aaa7bc6e14` |
| architecture verdict | `REVISE` |
| product authorization | `STOP-except-discovery` |
| disposition arithmetic | `32 ACCEPT / 23 ACCEPT_WITH_NARROWING / 16 NEEDS_DECISION / 10 DEFER / 2 REJECT = 83` |
| sacred `master` | `854d03b9a960c0be8c6b86cfd6d2b5ae72bc90b0` |
| sacred `v0.1-oss-prep` | local and remote-tracking refs absent; do not create |
| unrelated dirty baseline | exact output of `git status --porcelain=v1 --untracked-files=all`: 112 lines; SHA-256 `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326` |
| Step 4.3 preflight | commit `c59bfc77b2a7f316fd750e2d413e979fb532ea63`; artifact blob `6f17cdfb2f73732e34fa3e07d03f7cbc2a1c8521`; SHA-256 `0b2702d36310161e7df1c29b1880c7f7d167abc4f528140cda9fe0ebc30146b4`; `5 Required / 3 Recommended / 5 Verified / 4 Scoped-detail / 0 Abandonment` |

Stage 2 is skipped because Option 1 closes no load-bearing question and creates no ADR. Stage 3 is skipped because there is no Q-closure chain and the actionable subset occupies one docs-only small-gap bucket. These skips do not waive Step 4.2 review or Step 4.3 independent preflight.

### 4.2 O1-to-section change map

| Work item | Findings | Successor target | Exact correction | Hard boundary |
|---|---|---|---|---|
| O1-01 | PM-01 | §0.4, §17 intro, Phase 0/1, D01 wording | Phase 0/1 require Gate -1；纯设计/审计可继续，但任何并行 experiment/spike 必须由用户另行具名批准、预算封顶、可丢弃、不得被解释为 product approval，也不得倒逼产品继续 | do not start, move or expand a spike；不要把一般“discovery work”当成实现例外 |
| O1-02 | PM-04, CE-11 | Phase -1, §18.7, D01 reference | 规范引用 pinned Gate -1/DoD：8–10 目标账户中的 ≥5 个真实现状 walkthrough；一套合法且 source-aligned 的历史 case bundle；5–10 类人工/native claims；现有 QA/simple rules/LLM judge/FactGraph 四臂比较；standalone concierge 与 evaluator plugin 双报价；reviewer value、数据访问和有成本 pilot 前保持停止。Phase 3 promotion 的 30% 只指至少一家相对 baseline、与付费相关、由客户共同定义指标的改善目标；Phase 3 kill/总停止条件保留完成 10 个带价格/集成投入的报价后 `<3 paid pilot`，并独立保留 `>7 incumbent-sufficient buyers`；Phase 2 Managed Translator kill 的 >50% 只指客户 mapping/ontology 的实施维护工时（report09 `:98-106`），Gate C/总停止条件的 >50% 则只指 semantic customization/engineering 且不能形成 reusable vertical pack | 每个条件保持独立 phase/gate 与适用范围；双报价只是实验臂，不排除 OEM，不要求唯一赢家，standalone/embedded/OEM/both/neither 仍由 PM-03 决定；`:98-106` 只是 research evidence coordinate，不升级该报告 authority 或授权实验；不得合成统一阈值 |
| O1-03 | PM-02, PM-08 | §1.1, §1.3, §9.3 P0；§0.1 只在 Agent-axis 精确语句确有需要时改 | product axis becomes source-bound case/draft Verify/review；Agent output/intent is one input；§1.1 从 `SETTLED DIRECTION` 降为 `PROVISIONAL` + `EXPERIMENT REQUIRED` 并明示 Gate -1 未通过；P0 是 post-gate Agent/compatibility profile | retain conditional Agent architecture, L0–L3/A0–A2 and target flows；do not call P0 default MVP |
| O1-04 | CE-01 | §0.1, §17 总前言, §23 | use `smallest coherent review map for the stated scope`；在 §17 总前言一次声明每个获批 phase 只承担其已列 artifacts/deliverables | 除 O1-01 必需的 Phase 0/1 gate 句外，不改写各 phase artifact 清单；不吸收 CE-02、删类型或重排架构 |
| O1-05 | terminology hygiene | §22.5 | replace “named blockers before the experiment” with phase-specific required revisions/gates closed at their assigned gate | do not rewrite external severity or review history |
| O1-06 | SF-06 | §9.4 and the corresponding Flow A wording | 分层写清 shipped owner：Meander `PlanStore` 记录 Plan lifecycle；Meander graph-service orchestration 发起 write/rollback/recovery；相邻 shipped FactGraph ledger 保存 assertion/retract 历史。governance-blocked (`ingest.py:1078-1095`) 无 parse/write/evaluation；validation-rejected (`:1116-1131`) 无 graph write/evaluation。terminal `rejected_write_failure` 必须再分两类，且两类都保留 terminal PlanStore audit/lifecycle record：`PlanWriteFailure` 表示 in-request rollback 已成功，可能留下 revoked append-only traces，但无 effective Claim state且不进入 evaluation；第二次 `WriteBoundaryError` 在首个 write 前失败，根本没有写入（`:89-92/:183-213/:1140-1166`） | `create_ingesting` 后、terminal record 前的任何 unexpected failure 都可能留下 nonterminal `ingesting` 等待 recovery，不限于 rollback failure；明确包含 rollback/正常写入后的 `save_workspace()`、`record_accepted()` 与其他 wrapper-caught failure（`:280-293/:429-446/:1168-1169/:1333-1383`）。不能声称所有 `ingesting` 都无 effective facts：graph write 已持久化而 terminal status 失败时，facts 可暂时存在并由 recovery 撤销；“可能留下 revoked traces”只在两个 terminal 分支之间区分，不排除 nonterminal/recovery 路径产生 assertion/retract history。target hnsm FactGraph/LegacyV3Adapter 不是 shipped Plan lifecycle writer；保留 §2.4 Scenario premise `never written to authoritative ledger` |
| O1-07 | SF-07 | §2.6 evidence map | governance/write anchors → `ingest.py:1078-1095/1140-1169`; `RuleOccurrence` → `rule.py:238`; `EvidenceTimeline`/`EvidenceGraph` → `evidence_tree.py:143/:155` | references only; no broader shipped claim |
| O1-08 | AS-10 | §16.4–16.6 headings/qualification | §16.4 `SETTLED DIRECTION`，但立即限定 settled 的只有 source content 的 minimum disclosure 与 Meander access-control boundary；tenant keying 与 retention/erasure/legal-hold/replay precedence 仍分别由 CE-05/CE-06/AS-02 保持开放。§16.5 `PROVISIONAL`; Verify isolation in §16.6 `SETTLED DIRECTION`, future Decision profile `DEFERRED` | never label them `ADOPTED CONSTRAINT`; do not invent mechanism text or imply tenant/retention decisions are closed |
| O1-09 | RR-10 | §2.6 evidence map and only necessary local clarification | `store.py:3020-3045`：manual Explain 对接受的 Rule/RuleExpr 启动新 `_evaluate`；builder dispatch `:3367-3381`；native current-ledger probe `:3565-3595`，实际 projection `:3575`；Soufflé preferred current-store `:3413-3424`，`self._store` handoff `:3414`；ProbLog preferred current-store `:3453-3469`，`self._store` handoff `:3454` | Soufflé captured/minimal fallback `:3427-3438`；ProbLog hybrid fallback `:3472-3501`，captured proof trace 在 `:3488` 注入 callback，并由 `:3518-3536` 查询 current ledger certainty。不得称任何 fallback fully frozen/replay-safe，不得泛化到 all-path live read，也不实现 replay/digest guard |
| O1-10 | successor governance | title/header/Inputs/Outputs/§23 and minimal cross-links | record predecessor/disposition/audit identity, completed review, dual verdict, Option 1-only lineage and still-open decisions | v0.1 remains byte-identical; v0.1.1 remains working/candidate/non-authoritative, not final/adopted |

### 4.3 Stage-specific branch and path boundary

| Stage / commit purpose | Required branch | Exact allowed paths | Dirty-seam rule |
|---|---|---|---|
| Step 4.2 review tightening | current blueprint branch | this blueprint pair only | no index/source/input edit |
| Step 4.3 independent preflight | `v0.3.0-meander-factgraph-unified-design-v0-1-1-preflight-2026-08-10` at `c59bfc77b2a7f316fd750e2d413e979fb532ea63`, forked from the reviewed draft | only `workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md`, blob `6f17cdfb2f73732e34fa3e07d03f7cbc2a1c8521` | complete; branch stays preflight-artifact-only |
| Step 4.4 amendment | blueprint branch | this blueprint pair only | switch off the preflight branch before editing |
| Step 4.5 self-check | blueprint branch | no commit unless self-check finds a tightening; any such commit is blueprint-pair-only | no automatic transition to scoped |
| Step 4.6 scoped anchor | blueprint branch | this blueprint pair only | status/audit event plus separately reviewed minimal cleanup only |
| Step 4.7 docs content | `v0.3.0-impl-meander-factgraph-unified-design-v0-1-1-2026-08-10` forked from the scoped anchor | mandatory successor + disposition §11 link/status note + paired audit event；design-point README one-row hunk is conditional | consume the ledger/matrix/guards only from `git show c59bfc77b2a7f316fd750e2d413e979fb532ea63:workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md`; no predecessor/runtime/external path |
| Step 4.7 review fix, if any | implementation branch | only paths named by the reviewed finding plus paired audit event | scope expansion returns to blueprint amendment rather than being inferred |
| Step 4.8 closure | implementation branch | this blueprint pair only | fill Outcome and record implementation evidence |
| Step 4.9 preflight reconciliation | implementation branch | inspect the exact audit path in the implementation-branch tree: if absent, import exactly blob `6f17cdfb2f73732e34fa3e07d03f7cbc2a1c8521` from preflight commit `c59bfc77b2a7f316fd750e2d413e979fb532ea63`; if present and exact, skip import; if present but nonexact, stop and return to amendment/coordination without overwrite, repair or archive; global object/ref reachability is not sufficient | any import is a separate single-purpose commit before archive; byte/content identity is mandatory and mismatch is fail-closed |
| Step 4.9 archive | implementation branch | blueprint pair `active → archive`; vs-shipped + preflight `audit/active → audit/archive`; link-only fixes inside moved artifacts; one isolated row in `workflow/blueprints/archive/INVENTORY.md` | if the dirty INVENTORY row cannot be isolated, stop for coordination; never stage the whole file |

The Step 4.7 content payload is limited to:

1. `workflow/design/design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md` — mandatory new lineage successor;
2. `workflow/design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md` — only append a successor link/status note in §11; header, finding rows, counts and verdicts stay unchanged;
3. `workflow/design/design-points/README.md` — one safely isolated successor row only.

The v0.1 predecessor remains at its current active path with the same blob. v0.1.1 may call itself a lineage successor/revision but must not claim formal design-point `supersedes` status in this slice. Predecessor archival/formal supersession is a separate lifecycle action.

Both mixed files require **two-sided proof** before staging: cached diff contains only the task row; residual unstaged diff preserves the pre-recorded user hunk; post-commit `git status --porcelain=v1 --untracked-files=all` manifest returns to the exact 112-line baseline. If either the design-point index or archive INVENTORY hunk cannot be isolated, the applicable stage stops for coordination.

The preflight fixed the current seam recipe, not a future write authorization:

- design-point index: index/HEAD blob `5f2bd2cfc523ac6eb574f882f2e751207f7d76bc`, current worktree blob `fb40a7d9dbc126af3c1ac5aa8f52a281f5a21ac9`, worktree SHA-256 `f844703b0fba74ba7b783db37a392a7c71c23794281b6c20cdc37f5f24cb9c76`; the tested zero-context candidate insertion is immediately after the unchanged active-table separator (HEAD/worktree line 33) and before the first row;
- archive INVENTORY: index/HEAD blob `0d5ec4281b6a3106353fc5c2b42c5a19a9ab260b`, current worktree blob `de79dc2839768008203c4363dc9b3bba59ae925b`, worktree SHA-256 `6d91f834d7ec88c3bd3aefd7249ff729a842190c86d84ff9bc44e20ea363a464`; the tested zero-context candidate insertion is immediately after the unchanged table separator (HEAD/worktree line 10) and before the first row.

At the applicable stage, revalidate both index/worktree identities first, then require both index-side `git apply --cached --check --unidiff-zero` and worktree-side `git apply --check --unidiff-zero`, a cached diff containing only the task row, a residual diff preserving the user hunk and the exact post-commit unrelated manifest. Any identity drift or failed isolation stops the stage; these pins never authorize staging the whole file.

The design-point index proof is a precondition to the scoped anchor and no Step 4.7 content write begins without it. The archive INVENTORY proof may be revalidated immediately before Step 4.9, but archive does not begin if it is unsafe.

## 5. Proposed Shape

### 5.1 Successor, not mutable revision

The implementation copies v0.1 into the new v0.1.1 path, then applies only the mapped corrections. v0.1 remains the exact cold-review object; v0.1.1 records that it is a narrow lineage successor/revision, not a formal lifecycle supersession. Neither becomes adopted architecture merely by existing in `active/`.

### 5.2 Three edit batches

1. **Product authorization hygiene:** O1-01…O1-05 correct gate precedence, product-axis status, comparison scope and review terminology.
2. **Shipped-fidelity hygiene:** O1-06…O1-09 correct failure semantics, source anchors, section labels and Explain scope.
3. **Lineage hygiene:** O1-10 updates successor metadata and minimal cross-links without changing predecessor bytes or disposition decisions.

These batches are logical review units, not permission to create multiple design variants. They may land in one docs content commit only after scoped status and pre-implementation checks.

### 5.3 Semantic-edit-atom ledger and comparator

The fixed preflight artifact at commit `c59bfc77b2a7f316fd750e2d413e979fb532ea63` defines 41 semantic-edit atoms with executable `B-LIT/B-RE` before anchors and `LIT/RE/ALL/ANY/DISTINCT` after guards:

```text
change_id | path/section | exact before quote/hash | required after string/regex
O1 id | evidence | forbidden delta
```

Every semantic atom maps to exactly one O1 item. A physical Git hunk may contain several adjacent atoms—for example where O1-01/O1-04 share §17 or O1-07/O1-09 share §2.6—but the union of ledger atoms must cover every added/removed non-context text span. Step 4.7 evidence records `successor line + byte/substring span -> one change_id`; unchanged/context text is not an atom scan domain. An uncovered span, an atom without one O1 owner, or a new API/DTO/decision/experiment artifact is a scope failure, not an editorial convenience.

Because the successor is a new repository path copied from the 2185-line predecessor, ordinary commit diff treats the whole file as added and is **not** the semantic comparator. Semantic coverage uses normalized predecessor-content → successor-content comparison, operationally equivalent to `git diff --no-index -- <frozen-predecessor> <successor>`; exit status `1` means the expected content difference exists and is not itself a check failure. Repository commit diff is used separately for the stage path allowlist. Negative checks for newly introduced API/DTO/schema/enum/decision/experiment artifacts inspect only added semantic spans from this normalized comparator, never the full copied successor.

### 5.4 Open-decision non-preselection matrix

The fixed preflight carries the prospective exact 16-row matrix. Step 4.7 review must construct a fresh exact 16-row matrix against the actual successor semantic diff:

```text
finding id | disposition accurate question | adjacent successor loci
answer/preselection introduced? (must be no) | evidence
```

The matrix is semantic, not a count-only check. It must prove that unchanged disposition IDs/counts have not hidden an answer in nearby successor wording, especially for PM-03, CE-03/05/06/08, SF-04, AS-02/06/11 and AC-16/24.

### 5.5 Semantic-diff questions

Independent review must answer “no” to all four:

1. Does the successor close or preselect any of the 16 `NEEDS_DECISION` items?
2. Does it start or claim passage of any gate, experiment, benchmark or pilot?
3. Does it add or promise any API, schema, implementation or cross-repository mutation?
4. Does it weaken `STOP-except-discovery` or turn `REVISE` into architecture approval?

Any “yes” prevents scope freeze or content acceptance.

## 6. Boundaries And Invariants

- **INV-1 — predecessor integrity:** v0.1 remains at SHA `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7` before and after every commit.
- **INV-2 — authority:** v0.1.1 remains `Status: working`, candidate/non-authoritative, not current behavior; no new target claim is called adopted/shipped/implemented.
- **INV-3 — verdict separation:** architecture `REVISE` and product `STOP-except-discovery` remain separate.
- **INV-4 — decisions remain open:** the exact 16-ID set and D01–D18 numbering remain unchanged; the 16-row semantic matrix shows no answer/preselection; no new D/Q identifier is minted.
- **INV-5 — research gates retain scope:** ≥5 walkthroughs and the lawful source-aligned case bundle are separate; 5–10 claim classes, four comparison arms, dual packaging quotes and reviewer value/data access/cost-bearing pilot retain their distinct source scopes. Phase 3 promotion keeps the relative-to-baseline, payment-relevant, customer-co-defined 30% target; Phase 3 kill/total-stop keeps the completed-10-offer `<3 paid pilot` condition separate from `>7 incumbent-sufficient buyers`; Phase 2 Managed Translator kill keeps mapping/ontology implementation-and-maintenance >50% (report09 `:98-106`) separate from Gate C/total-stop semantic customization/engineering >50% without a reusable vertical pack. Dual quotes neither exclude OEM nor select standalone/embedded/both/neither; PM-03 remains open.
- **INV-6 — failure lifecycle precision and owner:** Meander `PlanStore` owns Plan lifecycle records; Meander graph-service orchestration initiates write/rollback/recovery; the adjacent shipped FactGraph ledger stores assertion/retract history. Governance-blocked and validation-rejected remain pre-write/pre-evaluation. Both terminal `rejected_write_failure` branches retain a terminal PlanStore audit/lifecycle record while having no effective Claim state or evaluation: successful rollback after `PlanWriteFailure` may leave revoked traces, whereas a second `WriteBoundaryError` performs no write. This distinction between the two terminal branches does not exclude assertion/retract history in nonterminal/recovery paths. Any unexpected post-`create_ingesting` failure before terminal recording may remain nonterminal `ingesting` for recovery, not only rollback failure, and such a state may temporarily coexist with written facts. Target hnsm FactGraph and LegacyV3Adapter are not shipped Plan lifecycle writers. Run-local Scenario premise remains distinct and is never written to the authoritative ledger.
- **INV-7 — Explain precision:** manual re-evaluation, lowering-plan-backed preferred current-store paths, captured-only/minimal fallbacks and the ProbLog captured-trace + current-ledger-certainty hybrid fallback remain distinct; no all-path-live, fully-frozen or replay guarantee is inferred.
- **INV-8 — docs-only/cross-repository isolation:** no runtime file in any repository changes; Meander pins are evidence, not write targets. Preflight fixes each external repo HEAD/status identity, and Step 4.7 review verifies it did not move. The preflight branch ref remains pinned at `c59bfc77b2a7f316fd750e2d413e979fb532ea63` until its exact artifact blob is present in the implementation-branch tree at Step 4.9. A present-but-nonexact artifact is a fail-closed mismatch: stop and return to amendment/coordination; never overwrite, repair or archive it in place.
- **INV-9 — exact content scope:** every successor semantic edit atom maps to exactly one of O1-01…O1-10 and covers every atom-owned added/removed span under the normalized predecessor→successor content comparator; repository diff separately enforces the path allowlist. The rest of the candidate is copied without semantic edits, and negative new-artifact checks scan only added semantic spans. Step 4.7 consumes the ledger/matrix/guards only from preflight commit `c59bfc77...`, blob `6f17cdfb...`.
- **INV-10 — dirty preservation:** the exact `git status --porcelain=v1 --untracked-files=all` 112-line unrelated baseline remains byte-for-byte the same status manifest and is never staged/restored. Before commit, only previously clean/task-new in-scope paths may be removed by exact allowlist when comparing the unrelated manifest; pre-existing mixed dirty paths are never filtered wholesale and instead require the INV-11 cached/residual proof. After each commit, the raw full-untracked manifest returns to exactly 112 lines and the frozen SHA.
- **INV-11 — mixed-file safety:** disposition changes are confined to a §11 successor link/status note; design-point index and archive INVENTORY are touched/staged only through the pinned-and-revalidated zero-context rows with cached synthetic-patch, cached-task-only, residual-user-hunk and post-commit 112-line proofs.
- **INV-12 — cadence:** draft, review, independent preflight, amendment, self-check, scoped anchor, implementation branch/content, review, closure and archive remain separate authorization gates; no automatic push/merge.

## 7. Acceptance

All boxes remain open in `draft`.

### 7.1 O1 content acceptance

- [ ] **A-O1-01:** Phase 0/1 are explicitly Gate -1-gated；唯一实现例外是用户另行具名批准、预算封顶、可丢弃、不代表 product approval 且不得倒逼产品继续的 discovery experiment/spike；纯设计/审计另行表述。
- [ ] **A-O1-02:** Pinned sources/anchors, including report09 `:98-106`, appear in the successor；walkthrough、case bundle、claim classes、four arms、dual quotes、reviewer value/data access/cost-bearing pilot each retain their own scope；Phase 3 promotion retains the relative-to-baseline, payment-relevant, customer-co-defined 30% target；Phase 3 kill/total-stop retains completed-10-offer `<3 paid pilot` separately from `>7 incumbent-sufficient buyers`；Phase 2 Managed Translator mapping/ontology implementation-and-maintenance >50% remains separate from Gate C/total-stop semantic customization/engineering >50% without a reusable vertical pack；dual quotes do not exclude OEM or decide standalone/embedded/both/neither under PM-03.
- [ ] **A-O1-03:** §1.1 is explicitly `PROVISIONAL` + `EXPERIMENT REQUIRED` rather than `SETTLED DIRECTION`; case/draft review is the provisional product axis, Agent is one input, Gate -1 remains unpassed, and P0 is a post-gate compatibility profile—not default MVP.
- [ ] **A-O1-04:** `smallest` is scoped to the coherent review map; phase deliverables do not imply full-map implementation.
- [ ] **A-O1-05:** final-verdict wording uses phase-specific revisions/gates rather than surviving blockers.
- [ ] **A-O1-06:** successor separately names governance-blocked、validation-rejected、`PlanWriteFailure` + successful-rollback terminal、second-`WriteBoundaryError` no-write terminal and the broader post-`create_ingesting` recovery-needed nonterminal class with their pinned anchors；both terminal branches retain terminal PlanStore audit/lifecycle records but have no effective Claim state or evaluation；among those two terminal branches only rollback-success may retain revoked traces, without excluding assertion/retract history in nonterminal/recovery paths；PlanStore / graph-service orchestration / adjacent ledger ownership is explicit；target hnsm/adapter ownership does not drift；§2.4 Scenario wording is unchanged.
- [ ] **A-O1-07:** all three shipped anchor groups match the pinned, full-read source files.
- [ ] **A-O1-08:** §16.4 is `SETTLED DIRECTION` only for minimum source disclosure and Meander access-control boundary；tenant keying and retention/erasure/legal-hold/replay precedence explicitly remain open under CE-05/CE-06/AS-02；§16.5 is `PROVISIONAL`; §16.6 marks Verify isolation `SETTLED DIRECTION` and future Decision profile `DEFERRED`; none is newly `ADOPTED CONSTRAINT`.
- [ ] **A-O1-09:** Explain wording separates manual re-evaluation `store.py:3020-3045`；builder dispatch `:3367-3381`；native current-ledger probe `:3565-3595` with projection `:3575`；Soufflé preferred current-store `:3413-3424` with `self._store :3414`；Soufflé captured/minimal fallback `:3427-3438`；ProbLog preferred current-store `:3453-3469` with `self._store :3454`；and ProbLog hybrid fallback `:3472-3501` with callback injection `:3488` and current-ledger lookup `:3518-3536`, without claiming all-path live reads, fully frozen fallback or replay safety.
- [ ] **A-O1-10:** successor title/header/Inputs/Outputs/§23 pin predecessor, disposition and Stage 1 audit identities；name the completed review, dual verdict, Option 1-only lineage and exact still-open decision set；v0.1 stays unchanged and no formal `supersedes` claim is made.

### 7.2 Machine-verifiable acceptance

- [ ] v0.1 path, 2185-line content and SHA remain unchanged.
- [ ] Disposition IDs, rows, counts and verdicts remain unchanged at `32/23/16/10/2`; its only diff is a §11 successor link/status note.
- [ ] Normalized predecessor-content → successor-content comparison, operationally equivalent to `git diff --no-index -- <frozen-predecessor> <successor>` (where exit `1` means a diff was produced), assigns every added/removed semantic span to exactly one of the preflight's 41 atoms and passes its exact before/after guards; there are no unmapped spans.
- [ ] `git diff-tree --no-commit-id --name-only -r <commit>` separately equals the applicable §4.3 section stage allowlist; repo-local commit diff contains no `src/`, `tests/`, API, notebook or predecessor path.
- [ ] Preflight-defined required/forbidden guards pass, including status labels, code anchors and IDs/counts; absence of newly introduced API/DTO/schema/enum/decision/experiment artifacts is checked only over normalized added semantic spans, not the full copied successor.
- [ ] Immediately before each mixed-file use, the recorded index/worktree blob identities still match; cached synthetic patch passes; cached diff contains only the task row; residual unstaged diff preserves the user hunk; post-commit unrelated manifest returns to 112 lines.
- [ ] Step 4.7 reads the ledger, matrix and guards from `git show c59bfc77b2a7f316fd750e2d413e979fb532ea63:workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md`; `git rev-parse` resolves that path to blob `6f17cdfb2f73732e34fa3e07d03f7cbc2a1c8521`, content SHA-256 is `0b2702d36310161e7df1c29b1880c7f7d167abc4f528140cda9fe0ebc30146b4`, and the protecting preflight branch ref remains pinned until Step 4.9 proves exact blob presence in the implementation-branch tree, whether through an exact pre-existing path or the separately committed import.
- [ ] Step 4.9 reconciliation is three-state and fail-closed: absent path imports the exact blob in its own commit; present exact blob skips import; present nonexact blob stops for amendment/coordination and is neither overwritten, repaired nor archived.
- [ ] Preflight-pinned Meander/meander-agent/factgraph-new HEAD + status identities are unchanged after Step 4.7.
- [ ] `git diff --check` passes; index is empty after each commit.
- [ ] Sacred refs are unchanged. Before commit, filtering is limited to previously clean/task-new exact in-scope paths; pre-existing mixed dirty paths retain their residual proof. After commit, raw `git status --porcelain=v1 --untracked-files=all` yields exactly 112 lines with SHA `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326`.
- [ ] Paired audit mirrors every lifecycle event; no push/merge occurs without separate authorization.

### 7.3 Semantic and review acceptance

- [ ] The exact 16-row `NEEDS_DECISION` non-preselection matrix records `answer/preselection introduced = no` for every item with evidence; unchanged IDs/counts alone are insufficient.
- [ ] Independent semantic review answers “no” to all four §5.5 questions and finds no product/authority/owner drift.
- [ ] Every Step 4.3 Required and Recommended finding has an amendment disposition plus independent diff-check; before scoped there are zero unresolved Required findings and zero Abandonment blockers.
- [ ] The paired audit states that no **additional** user-side/cross-model Step 4.2 report was supplied before preflight; this does not erase the already dispositioned 28-agent adversarial review, and internal same-model reviews are not relabelled as cross-model evidence.

## 8. Implementation Plan

Each numbered stage transition requires a new explicit authorization. Mechanical checks inside one authorized stage may be batched, but they never authorize the next stage.

1. **Step 4.1 — draft:** create this blueprint and paired audit in one single-purpose commit.
2. **Step 4.2 — draft review/tightening:** independently attack scope, O1 mapping, file allowlist and acceptance; apply only review-authorized blueprint corrections.
3. **Step 4.3 — independent preflight (complete):** fixed artifact commit `c59bfc77b2a7f316fd750e2d413e979fb532ea63` re-read the actual referenced files, froze external identities, constructed the 41-atom ledger and exact 16-row prospective matrix, checked both mixed seams and returned `5 Required / 3 Recommended / 5 Verified / 4 Scoped-detail / 0 Abandonment`.
4. **Step 4.4 — preflight amendment:** switch back to the blueprint branch, disposition and apply every Required and Recommended finding in the blueprint pair, and independently diff-check each application. This does not modify or import the fixed preflight artifact.
5. **Step 4.5 — self-check:** in a separately authorized no-commit check, verify all PF findings, atom/decision matrices, internal consistency and stale wording；commit only if a new tightening is required.
6. **Step 4.6 — scoped anchor:** change only blueprint/audit lifecycle fields and freeze the exact content/path allowlists.
7. **Step 4.6.5 — explicit skip check:** because this slice is docs-only and deletes no shipped symbol/API, no deletion grep is applicable；record the skip plus replacement path/semantic-diff guard in the paired audit. Any newly discovered consumer/scope issue returns to amendment rather than proceeding.
8. **Step 4.7 — implementation branch/docs content:** fork `v0.3.0-impl-meander-factgraph-unified-design-v0-1-1-2026-08-10` from the scoped anchor；verify and consume the fixed preflight through `git show c59bfc77b2a7f316fd750e2d413e979fb532ea63:workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md` without merging/cherry-picking its branch；copy v0.1 to the successor path；apply O1-01…O1-10；append only the disposition §11 cross-link/status note and a safely isolated index row；record the implementation event in the paired audit.
9. **Step 4.7 review:** independently verify predecessor hash, fixed preflight commit/blob/content SHA, 41-atom guards, normalized semantic comparator, four semantic questions, fresh 16-row open-decision matrix, dual verdict, repo/path allowlists, external pins and dirty baseline；any scope expansion returns to blueprint amendment.
10. **Step 4.8 — closure on the implementation branch:** mark implemented only after every acceptance item has evidence；fill Outcome / Deviations without turning the design-point into current truth；record archive readiness, not a completed archive.
11. **Step 4.9 — reconciliation and archive on the implementation branch:** first inspect `HEAD:workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md`; global object/ref reachability is irrelevant. If the path is absent, import exact blob `6f17cdfb2f73732e34fa3e07d03f7cbc2a1c8521` in a preflight-only commit；if present and exact, skip import；if present but nonexact, stop and return to amendment/coordination without overwriting, repairing or archiving it. Only after exact presence is proven may a second single-purpose commit archive the blueprint pair and the vs-shipped/preflight standalone audits, fix only moved-artifact links, and stage one isolated INVENTORY row. The v0.1 predecessor remains active；any later design-point lifecycle move is separately authorized.

## 9. Docs To Update

### Future content targets

- `workflow/design/design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md` — mandatory new successor.
- `workflow/design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md` — minimal successor link/status note.
- `workflow/design/design-points/README.md` — one successor row only if its index hunk can be safely isolated from the pre-existing dirty rewrite.

### Process artifacts

- this blueprint and its paired audit log;
- fixed independent preflight at commit `c59bfc77b2a7f316fd750e2d413e979fb532ea63`, consumed cross-branch at Step 4.7 and imported by exact blob before Step 4.9 archive;
- Step 4.9 moves the blueprint pair and both standalone audits to their archive directories;
- `workflow/blueprints/archive/INVENTORY.md` receives one isolated archive row only at Step 4.9.

No module docs, `docs/README.md`, source repository, external report or v0.1 predecessor update belongs to this slice.

## 10. Outcome / Deviations

To be completed only at Step 4.8:

- final commits, per-path line counts and changed paths;
- O1-01…O1-10 evidence table;
- predecessor hash and dual-verdict/open-decision preservation results;
- independent preflight/review results and per-PF alignment;
- acknowledged baseline failures, or explicit `none`;
- sacred-ref and unrelated-dirty verification;
- deviations from this blueprint, or explicit `none`;
- archive intent/readiness. Actual archive completion is recorded by the Step 4.9 paired-audit event after the move.
