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
  - [`09_实验路线_停止条件与迁移.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/09_实验路线_停止条件与迁移.md>), 227 行，SHA-256 `7f8f73ce18b8e688daa485cf465a06157993a94bef60ed3b4a03f406df2da474`；承重锚点 `:17-30/:124-132/:220-225`
- Outputs / Downstream:
  - future independent preflight: `workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md`
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
| unrelated dirty baseline | 112 porcelain-v1 lines; SHA-256 `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326` |

Stage 2 is skipped because Option 1 closes no load-bearing question and creates no ADR. Stage 3 is skipped because there is no Q-closure chain and the actionable subset occupies one docs-only small-gap bucket. These skips do not waive Step 4.2 review or Step 4.3 independent preflight.

### 4.2 O1-to-section change map

| Work item | Findings | Successor target | Exact correction | Hard boundary |
|---|---|---|---|---|
| O1-01 | PM-01 | §0.4, §17 intro, Phase 0/1, D01 wording | Phase 0/1 require Gate -1；纯设计/审计可继续，但任何并行 experiment/spike 必须由用户另行具名批准、预算封顶、可丢弃、不得被解释为 product approval，也不得倒逼产品继续 | do not start, move or expand a spike；不要把一般“discovery work”当成实现例外 |
| O1-02 | PM-04, CE-11 | Phase -1, §18.7, D01 reference | 规范引用 pinned Gate -1/DoD：8–10 目标账户中的 ≥5 个真实现状 walkthrough；一套合法且 source-aligned 的历史 case bundle；5–10 类人工/native claims；现有 QA/simple rules/LLM judge/FactGraph 四臂比较；standalone concierge 与 evaluator plugin 双报价；reviewer value、数据访问和有成本 pilot 前保持停止。Phase 3 promotion 的 30% 只指至少一家相对 baseline、与付费相关、由客户共同定义指标的改善目标；Phase 3 kill/总停止条件保留完成 10 个带价格/集成投入的报价后 `<3 paid pilot`，并独立保留 `>7 incumbent-sufficient buyers`；Phase 2 Managed Translator kill 的 >50% 只指客户 mapping/ontology 的实施维护工时，Gate C/总停止条件的 >50% 则只指 semantic customization/engineering 且不能形成 reusable vertical pack | 每个条件保持独立 phase/gate 与适用范围；测试双包装不等于裁定 PM-03；不得合成统一阈值 |
| O1-03 | PM-02, PM-08 | §1.1, §1.3, §9.3 P0；§0.1 只在 Agent-axis 精确语句确有需要时改 | product axis becomes source-bound case/draft Verify/review；Agent output/intent is one input；§1.1 从 `SETTLED DIRECTION` 降为 `PROVISIONAL` + `EXPERIMENT REQUIRED` 并明示 Gate -1 未通过；P0 是 post-gate Agent/compatibility profile | retain conditional Agent architecture, L0–L3/A0–A2 and target flows；do not call P0 default MVP |
| O1-04 | CE-01 | §0.1, §17 总前言, §23 | use `smallest coherent review map for the stated scope`；在 §17 总前言一次声明每个获批 phase 只承担其已列 artifacts/deliverables | 除 O1-01 必需的 Phase 0/1 gate 句外，不改写各 phase artifact 清单；不吸收 CE-02、删类型或重排架构 |
| O1-05 | terminology hygiene | §22.5 | replace “named blockers before the experiment” with phase-specific required revisions/gates closed at their assigned gate | do not rewrite external severity or review history |
| O1-06 | SF-06 | §9.4 and the corresponding Flow A wording | 明确 owner 是 shipped Meander Plan ingest/customer ledger：governance-blocked (`ingest.py:1078-1095`) 无 parse/write/evaluation；validation-rejected (`:1116-1131`) 无 graph write/evaluation；successful rollback 后的 terminal `rejected_write_failure` (`:1140-1166`) 可留下 revoked append-only traces，但无 effective Claim state且不进入 evaluation | rollback 自身失败可保留 `ingesting` 等待 recovery，不套用 terminal 结论；target hnsm FactGraph/LegacyV3Adapter 不写、撤销或拒绝 Plan Claim；保留 §2.4 Scenario premise `never written to authoritative ledger` |
| O1-07 | SF-07 | §2.6 evidence map | governance/write anchors → `ingest.py:1078-1095/1140-1169`; `RuleOccurrence` → `rule.py:238`; `EvidenceTimeline`/`EvidenceGraph` → `evidence_tree.py:143/:155` | references only; no broader shipped claim |
| O1-08 | AS-10 | §16.4–16.6 headings/qualification | §16.4 `SETTLED DIRECTION`; §16.5 `PROVISIONAL`; Verify isolation in §16.6 `SETTLED DIRECTION`, future Decision profile `DEFERRED` | never label them `ADOPTED CONSTRAINT`; do not invent mechanism text |
| O1-09 | RR-10 | §2.6 evidence map and only necessary local clarification | `store.py:3020-3045`：manual Explain 对接受的 Rule/RuleExpr 启动新 `_evaluate`；`:3367-3503/:3575`：lowering-plan-backed lazy row Explain 的 native probe 与 Soufflé/ProbLog preferred reach paths 在执行时读当前 attached Store/Ledger（其中 `:3413/:3453` 传入当前 store） | `:3427-3438/:3472-3501` 可回退到 captured artifact/envelope/minimal graph；不得泛化到所有 input/fallback，不实现 replay/digest guard |
| O1-10 | successor governance | title/header/Inputs/Outputs/§23 and minimal cross-links | record predecessor/disposition/audit identity, completed review, dual verdict, Option 1-only lineage and still-open decisions | v0.1 remains byte-identical; v0.1.1 remains working/candidate/non-authoritative, not final/adopted |

### 4.3 Stage-specific branch and path boundary

| Stage / commit purpose | Required branch | Exact allowed paths | Dirty-seam rule |
|---|---|---|---|
| Step 4.2 review tightening | current blueprint branch | this blueprint pair only | no index/source/input edit |
| Step 4.3 independent preflight | `v0.3.0-meander-factgraph-unified-design-v0-1-1-preflight-2026-08-10` forked from the reviewed draft | only `workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md` | preflight branch stays preflight-artifact-only |
| Step 4.4 amendment | blueprint branch | this blueprint pair only | switch off the preflight branch before editing |
| Step 4.5 self-check | blueprint branch | no commit unless self-check finds a tightening; any such commit is blueprint-pair-only | no automatic transition to scoped |
| Step 4.6 scoped anchor | blueprint branch | this blueprint pair only | status/audit event plus separately reviewed minimal cleanup only |
| Step 4.7 docs content | `v0.3.0-impl-meander-factgraph-unified-design-v0-1-1-2026-08-10` forked from the scoped anchor | mandatory successor + disposition §11 link/status note + paired audit event；design-point README one-row hunk is conditional | rules below; no predecessor/runtime/external path |
| Step 4.7 review fix, if any | implementation branch | only paths named by the reviewed finding plus paired audit event | scope expansion returns to blueprint amendment rather than being inferred |
| Step 4.8 closure | implementation branch | this blueprint pair only | fill Outcome and record implementation evidence |
| Step 4.9 preflight reconciliation | implementation branch | import the content-identical standalone preflight artifact only if it is not already reachable | separate single-purpose commit before archive |
| Step 4.9 archive | implementation branch | blueprint pair `active → archive`; vs-shipped + preflight `audit/active → audit/archive`; link-only fixes inside moved artifacts; one isolated row in `workflow/blueprints/archive/INVENTORY.md` | if the dirty INVENTORY row cannot be isolated, stop for coordination; never stage the whole file |

The Step 4.7 content payload is limited to:

1. `workflow/design/design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md` — mandatory new lineage successor;
2. `workflow/design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md` — only append a successor link/status note in §11; header, finding rows, counts and verdicts stay unchanged;
3. `workflow/design/design-points/README.md` — one safely isolated successor row only.

The v0.1 predecessor remains at its current active path with the same blob. v0.1.1 may call itself a lineage successor/revision but must not claim formal design-point `supersedes` status in this slice. Predecessor archival/formal supersession is a separate lifecycle action.

Both mixed files require **two-sided proof** before staging: cached diff contains only the task row; residual unstaged diff preserves the pre-recorded user hunk; post-commit porcelain manifest returns to the exact 112-line baseline. If either the design-point index or archive INVENTORY hunk cannot be isolated, the applicable stage stops for coordination.

The design-point index proof is a precondition to the scoped anchor and no Step 4.7 content write begins without it. The archive INVENTORY proof may be revalidated immediately before Step 4.9, but archive does not begin if it is unsafe.

## 5. Proposed Shape

### 5.1 Successor, not mutable revision

The implementation copies v0.1 into the new v0.1.1 path, then applies only the mapped corrections. v0.1 remains the exact cold-review object; v0.1.1 records that it is a narrow lineage successor/revision, not a formal lifecycle supersession. Neither becomes adopted architecture merely by existing in `active/`.

### 5.2 Three edit batches

1. **Product authorization hygiene:** O1-01…O1-05 correct gate precedence, product-axis status, comparison scope and review terminology.
2. **Shipped-fidelity hygiene:** O1-06…O1-09 correct failure semantics, source anchors, section labels and Explain scope.
3. **Lineage hygiene:** O1-10 updates successor metadata and minimal cross-links without changing predecessor bytes or disposition decisions.

These batches are logical review units, not permission to create multiple design variants. They may land in one docs content commit only after scoped status and pre-implementation checks.

### 5.3 Semantic-edit-atom ledger

Before scoped, preflight must define a ledger with one row per expected semantic edit atom:

```text
change_id | path/section | exact before quote/hash | required after string/regex
O1 id | evidence | forbidden delta
```

Every semantic atom maps to exactly one O1 item. A physical Git hunk may contain several adjacent atoms—for example where O1-01/O1-04 share §17 or O1-07/O1-09 share §2.6—but the union of ledger atoms must cover every added/removed non-context text span. An uncovered span, an atom without one O1 owner, or a new API/DTO/decision/experiment artifact is a scope failure, not an editorial convenience.

### 5.4 Open-decision non-preselection matrix

Preflight and Step 4.7 review must each carry an exact 16-row matrix:

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
- **INV-5 — research gates retain scope:** ≥5 walkthroughs and the lawful source-aligned case bundle are separate; 5–10 claim classes, four comparison arms, dual packaging quotes and reviewer value/data access/cost-bearing pilot retain their distinct source scopes. Phase 3 promotion keeps the relative-to-baseline, payment-relevant, customer-co-defined 30% target; Phase 3 kill/total-stop keeps the completed-10-offer `<3 paid pilot` condition separate from `>7 incumbent-sufficient buyers`; Phase 2 Managed Translator kill keeps mapping/ontology implementation-and-maintenance >50% separate from Gate C/total-stop semantic customization/engineering >50% without a reusable vertical pack.
- **INV-6 — failure lifecycle precision and owner:** shipped Meander Plan ingest/customer ledger owns governance, validation, assertion write and rollback/revocation states. Governance-blocked, validation-rejected, terminal rejected-write-failure after successful rollback, nonterminal rollback failure/recovery, effective Claim state and run-local Scenario premise remain distinct. Target hnsm FactGraph and LegacyV3Adapter do not write/revoke/reject the Plan Claim.
- **INV-7 — Explain precision:** manual re-evaluation, lowering-plan-backed preferred live-store paths and captured fallback paths remain distinct; no replay guarantee is inferred.
- **INV-8 — docs-only/cross-repository isolation:** no runtime file in any repository changes; Meander pins are evidence, not write targets. Preflight fixes each external repo HEAD/status identity, and Step 4.7 review verifies it did not move.
- **INV-9 — exact content scope:** every successor semantic edit atom maps to exactly one of O1-01…O1-10 and covers every added/removed text span; the rest of the candidate is copied without semantic edits.
- **INV-10 — dirty preservation:** the 112-line unrelated baseline remains byte-for-byte the same status manifest and is never staged/restored.
- **INV-11 — mixed-file safety:** disposition changes are confined to a §11 successor link/status note; design-point index and archive INVENTORY are touched/staged only through independently verified isolated rows with cached/residual two-sided proof.
- **INV-12 — cadence:** draft, review, independent preflight, amendment, self-check, scoped anchor, implementation branch/content, review, closure and archive remain separate authorization gates; no automatic push/merge.

## 7. Acceptance

All boxes remain open in `draft`.

### 7.1 O1 content acceptance

- [ ] **A-O1-01:** Phase 0/1 are explicitly Gate -1-gated；唯一实现例外是用户另行具名批准、预算封顶、可丢弃、不代表 product approval 且不得倒逼产品继续的 discovery experiment/spike；纯设计/审计另行表述。
- [ ] **A-O1-02:** Pinned sources/anchors appear in the successor；walkthrough、case bundle、claim classes、four arms、dual quotes、reviewer value/data access/cost-bearing pilot each retain their own scope；Phase 3 promotion retains the relative-to-baseline, payment-relevant, customer-co-defined 30% target；Phase 3 kill/total-stop retains completed-10-offer `<3 paid pilot` separately from `>7 incumbent-sufficient buyers`；Phase 2 Managed Translator mapping/ontology implementation-and-maintenance >50% remains separate from Gate C/total-stop semantic customization/engineering >50% without a reusable vertical pack；testing two packages does not decide PM-03.
- [ ] **A-O1-03:** §1.1 is explicitly `PROVISIONAL` + `EXPERIMENT REQUIRED` rather than `SETTLED DIRECTION`; case/draft review is the provisional product axis, Agent is one input, Gate -1 remains unpassed, and P0 is a post-gate compatibility profile—not default MVP.
- [ ] **A-O1-04:** `smallest` is scoped to the coherent review map; phase deliverables do not imply full-map implementation.
- [ ] **A-O1-05:** final-verdict wording uses phase-specific revisions/gates rather than surviving blockers.
- [ ] **A-O1-06:** successor separately names Meander governance-blocked, validation-rejected, terminal rejected-write-failure after successful rollback, and rollback-failure/recovery states with their pinned anchors；revoked traces never become effective Claim state or evaluation；FactGraph/adapter write ownership does not drift；§2.4 Scenario wording is unchanged.
- [ ] **A-O1-07:** all three shipped anchor groups match the pinned, full-read source files.
- [ ] **A-O1-08:** §16.4 is `SETTLED DIRECTION`; §16.5 is `PROVISIONAL`; §16.6 marks Verify isolation `SETTLED DIRECTION` and future Decision profile `DEFERRED`; none is newly `ADOPTED CONSTRAINT`.
- [ ] **A-O1-09:** Explain wording binds manual re-evaluation to `store.py:3020-3045`, lowering-plan-backed preferred live reads to `:3367-3503/:3575` (including current-store handoff at `:3413/:3453`), and fallbacks to `:3427-3438/:3472-3501`, without claiming all-path live reads or replay safety.
- [ ] **A-O1-10:** successor title/header/Inputs/Outputs/§23 pin predecessor, disposition and Stage 1 audit identities；name the completed review, dual verdict, Option 1-only lineage and exact still-open decision set；v0.1 stays unchanged and no formal `supersedes` claim is made.

### 7.2 Machine-verifiable acceptance

- [ ] v0.1 path, 2185-line content and SHA remain unchanged.
- [ ] Disposition IDs, rows, counts and verdicts remain unchanged at `32/23/16/10/2`; its only diff is a §11 successor link/status note.
- [ ] The semantic-edit-atom ledger's exact before/after guards cover every successor added/removed text span; there are no unmapped changes.
- [ ] `git diff-tree --no-commit-id --name-only -r <commit>` equals the applicable §4.3 stage allowlist; repo-local diff contains no `src/`, `tests/`, API, notebook or predecessor path.
- [ ] Preflight-defined required/forbidden string and regex guards pass, including status labels, code anchors, IDs/counts and absence of newly introduced API/DTO/schema/enum/decision/experiment artifacts.
- [ ] Cached task rows and residual unstaged user hunks for both mixed index files pass the two-sided patch proof.
- [ ] Preflight-pinned Meander/meander-agent/factgraph-new HEAD + status identities are unchanged after Step 4.7.
- [ ] `git diff --check` passes; index is empty after each commit.
- [ ] Sacred refs are unchanged; the unrelated dirty set remains 112 lines with SHA `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326`.
- [ ] Paired audit mirrors every lifecycle event; no push/merge occurs without separate authorization.

### 7.3 Semantic and review acceptance

- [ ] The exact 16-row `NEEDS_DECISION` non-preselection matrix records `answer/preselection introduced = no` for every item with evidence; unchanged IDs/counts alone are insufficient.
- [ ] Independent semantic review answers “no” to all four §5.5 questions and finds no product/authority/owner drift.
- [ ] Every Step 4.3 Required and Recommended finding has an amendment disposition plus independent diff-check; before scoped there are zero unresolved Required findings and zero Abandonment blockers.
- [ ] Any user-side/cross-model Step 4.2 report supplied before preflight has been dispositioned in the paired audit; absence of such a report is stated rather than implied as review evidence.

## 8. Implementation Plan

Each numbered stage transition requires a new explicit authorization. Mechanical checks inside one authorized stage may be batched, but they never authorize the next stage.

1. **Step 4.1 — draft:** create this blueprint and paired audit in one single-purpose commit.
2. **Step 4.2 — draft review/tightening:** independently attack scope, O1 mapping, file allowlist and acceptance; apply only review-authorized blueprint corrections.
3. **Step 4.3 — independent preflight:** on the exact preflight branch in §4.3, re-read the actual referenced files at fixed hashes；freeze external repo status identities；construct the semantic-edit-atom ledger and 16-row non-preselection matrix；pre-register machine guards；check both mixed-file seams；report Required/Recommended/Verified/Scoped-detail/Abandonment findings.
4. **Step 4.4 — preflight amendment:** switch back to the blueprint branch, disposition and apply every Required and Recommended finding in the blueprint pair, and independently diff-check each application.
5. **Step 4.5 — self-check:** in a separately authorized no-commit check, verify all PF findings, atom/decision matrices, internal consistency and stale wording；commit only if a new tightening is required.
6. **Step 4.6 — scoped anchor:** change only blueprint/audit lifecycle fields and freeze the exact content/path allowlists.
7. **Step 4.6.5 — explicit skip check:** because this slice is docs-only and deletes no shipped symbol/API, no deletion grep is applicable；record the skip plus replacement path/semantic-diff guard in the paired audit. Any newly discovered consumer/scope issue returns to amendment rather than proceeding.
8. **Step 4.7 — implementation branch/docs content:** fork `v0.3.0-impl-meander-factgraph-unified-design-v0-1-1-2026-08-10` from the scoped anchor；copy v0.1 to the successor path；apply O1-01…O1-10；append only the disposition §11 cross-link/status note and a safely isolated index row；record the implementation event in the paired audit.
9. **Step 4.7 review:** independently verify predecessor hash, atom ledger, machine guards, four semantic questions, 16-row open-decision matrix, dual verdict, repo/path allowlists, external pins and dirty baseline；any scope expansion returns to blueprint amendment.
10. **Step 4.8 — closure on the implementation branch:** mark implemented only after every acceptance item has evidence；fill Outcome / Deviations without turning the design-point into current truth；record archive readiness, not a completed archive.
11. **Step 4.9 — reconciliation and archive on the implementation branch:** first import the content-identical preflight artifact if necessary；then archive the blueprint pair and the vs-shipped/preflight standalone audits, fix only moved-artifact links, and stage one isolated INVENTORY row. The v0.1 predecessor remains active；any later design-point lifecycle move is separately authorized.

## 9. Docs To Update

### Future content targets

- `workflow/design/design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md` — mandatory new successor.
- `workflow/design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md` — minimal successor link/status note.
- `workflow/design/design-points/README.md` — one successor row only if its index hunk can be safely isolated from the pre-existing dirty rewrite.

### Process artifacts

- this blueprint and its paired audit log;
- future independent preflight under `workflow/audit/active/`;
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
