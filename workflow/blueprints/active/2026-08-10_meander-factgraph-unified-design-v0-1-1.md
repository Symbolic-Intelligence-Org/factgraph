# Task Blueprint: Meander × FactGraph 统一设计 Review Freeze v0.1.1 文本收敛

- Status: draft
- Created: 2026-08-10
- Last Updated: 2026-08-10
- Authority: task-scoped docs-only blueprint. 本文只约束 O1-01…O1-10 的候选文本收敛；不 adopted 目标设计，不覆盖 shipped 行为，也不授权代码、产品建设或实验。
- Inputs:
  - [`2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md`](../../audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md), Stage 1 commit `e32ec385427a5eabb4645d3a4da06cef3c9fe652`, 394 行，SHA-256 `0d1dfb6a5236d15fc8d9ba8624cdc2317915d3a77dc7e5c0ed042b0e429d9329`
  - [`meander-factgraph-unified-design-review-candidate.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-review-candidate.zh.md), frozen v0.1 predecessor, 2185 行，SHA-256 `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7`
  - [`meander-factgraph-unified-design-adversarial-review-disposition.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md), 381 行，SHA-256 `f8a2fedb48f6f3f1b1e19b41cdd7a5823352a59cc74aa8b1068c10aaa7bc6e14`
  - [`01_执行摘要与最终判决.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/01_执行摘要与最终判决.md>), 186 行，SHA-256 `cc6eb3297a4b33ceebbd675eb896b13519a2f183758ca1a03b7dd9a5acc65f3d`
  - [`09_实验路线_停止条件与迁移.md`](</Users/zhenzhili/obsidian_workspace/symb-Intelli./codex_report/09_实验路线_停止条件与迁移.md>), 227 行，SHA-256 `7f8f73ce18b8e688daa485cf465a06157993a94bef60ed3b4a03f406df2da474`
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

用户选择 disposition 的 Option 1：只生成 v0.1.1 successor，吸收“下一版候选文本前”必须修正的内容。本任务的难点不是重新设计，而是证明每个变更 hunk 都且只属于 O1-01…O1-10，并证明没有借文字修订关闭开放决定、启动产品建设或改变任一仓库运行行为。

## 2. Goals

1. 创建独立、可追溯的 v0.1.1 successor，不原位改写 frozen v0.1。
2. 逐项且仅吸收 Stage 1 audit §4.2 的 O1-01…O1-10。
3. 保持两个独立裁定：architecture `REVISE`；product authorization `STOP-except-discovery`。
4. 保持 16 项 `NEEDS_DECISION`、`32/23/16/10/2` disposition 分布和 candidate/non-authoritative authority 不变。
5. 精确修正 SF-06、SF-07、RR-10 的 shipped 描述与锚点，不把修辞修正写成 shipped capability 或运行时修复。
6. 用 predecessor hash、hunk-to-O1 ledger、semantic diff、path allowlist 和独立 preflight 证明范围没有泄漏。

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
| O1-01 | PM-01 | §0.4, §17 intro, Phase 0/1, D01 wording | Phase 0/1 require Gate -1; only separately authorized, budget-capped, disposable discovery work may run in parallel without implying product approval | do not start, move or expand a spike |
| O1-02 | PM-04, CE-11 | Phase -1, §18.7, D01 reference | normatively cite the pinned Gate -1/DoD sources and preserve each metric's own scope | do not merge ≥5, 30%, >50% or 10-offer into one threshold; do not decide packaging |
| O1-03 | PM-02, PM-08 | §0.1, §1.1, §1.3, §9.3 P0 | product axis becomes source-bound case/draft Verify/review; Agent output/intent is one input; P0 is a post-gate Agent/compatibility profile | retain conditional Agent architecture, L0–L3/A0–A2 and target flows; do not call P0 default MVP |
| O1-04 | CE-01 | §0.1, §17 phase scope, §23 | use `smallest coherent review map for the stated scope`; each approved phase bears only its named artifacts/deliverables | do not absorb CE-02, delete types or reorder the architecture |
| O1-05 | terminology hygiene | §22.5 | replace “named blockers before the experiment” with phase-specific required revisions/gates closed at their assigned gate | do not rewrite external severity or review history |
| O1-06 | SF-06 | §9.4 and the corresponding Flow A wording | distinguish governance/validation rejection from graph-write failure; the latter may leave revoked append-only traces but creates no effective Claim state and does not enter evaluation | preserve §2.4 Scenario premise `never written to authoritative ledger` unchanged |
| O1-07 | SF-07 | §2.6 evidence map | governance/write anchors → `ingest.py:1078-1095/1140-1169`; `RuleOccurrence` → `rule.py:238`; `EvidenceTimeline`/`EvidenceGraph` → `evidence_tree.py:143/:155` | references only; no broader shipped claim |
| O1-08 | AS-10 | §16.4–16.6 headings/qualification | §16.4 `SETTLED DIRECTION`; §16.5 `PROVISIONAL`; Verify isolation in §16.6 `SETTLED DIRECTION`, future Decision profile `DEFERRED` | never label them `ADOPTED CONSTRAINT`; do not invent mechanism text |
| O1-09 | RR-10 | §2.6 evidence map and only necessary local clarification | manual Explain for accepted Rule/RuleExpr starts a new `_evaluate`; lowering-plan-backed lazy row Explain has native and Soufflé/ProbLog preferred paths that read the current attached Store/Ledger | no claim that every input/fallback reads live state; no replay/digest implementation |
| O1-10 | successor governance | title/header/Inputs/Outputs/§23 and minimal cross-links | record predecessor/disposition/audit identity, completed review, dual verdict, Option 1-only lineage and still-open decisions | v0.1 remains byte-identical; v0.1.1 remains working/candidate/non-authoritative, not final/adopted |

### 4.3 Artifact and path boundary

The future content commit may write only:

1. `workflow/design/design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md` — new successor;
2. `workflow/design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md` — minimal successor link/status note only;
3. `workflow/design/design-points/README.md` — one safely isolated successor row only, and only if preflight proves that no unrelated dirty hunk enters the index.

The v0.1 predecessor remains at its current active path with the same blob. If the index edit cannot be isolated from the user's existing mixed hunk, implementation stops for coordination rather than staging the whole file. Predecessor archival is a separate lifecycle action outside this blueprint.

Process artifacts—the blueprint pair and later standalone preflight—follow their own cadence commits and are not part of the successor content diff.

## 5. Proposed Shape

### 5.1 Successor, not mutable revision

The implementation copies v0.1 into the new v0.1.1 path, then applies only the mapped corrections. v0.1 remains the exact cold-review object; v0.1.1 records that it is a narrow textual successor. Neither becomes adopted architecture merely by existing in `active/`.

### 5.2 Three edit batches

1. **Product authorization hygiene:** O1-01…O1-05 correct gate precedence, product-axis status, comparison scope and review terminology.
2. **Shipped-fidelity hygiene:** O1-06…O1-09 correct failure semantics, source anchors, section labels and Explain scope.
3. **Lineage hygiene:** O1-10 updates successor metadata and minimal cross-links without changing predecessor bytes or disposition decisions.

These batches are logical review units, not permission to create multiple design variants. They may land in one docs content commit only after scoped status and pre-implementation checks.

### 5.3 Hunk-to-O1 ledger

Before scoped, preflight must define a ledger with one row per expected successor hunk:

```text
successor section | before anchor | intended after meaning | exactly one O1 id | boundary check
```

Every changed hunk must map to exactly one O1 item. An unmapped hunk, a hunk mapped to multiple contradictory purposes, or a new API/DTO/decision/experiment artifact is a scope failure, not an editorial convenience.

### 5.4 Semantic-diff questions

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
- **INV-4 — decisions remain open:** the exact 16-ID set and D01–D18 numbering remain unchanged; no new D/Q identifier is minted.
- **INV-5 — research metrics retain scope:** ≥5 walkthrough/case evidence, customer-defined 30% target, semantic-customization >50% condition and 10-offer condition are not collapsed or generalized.
- **INV-6 — failure lifecycle precision:** governance/validation rejection, write failure with revoked traces, effective Claim state and run-local Scenario premise remain distinct.
- **INV-7 — Explain precision:** manual re-evaluation, lowering-plan-backed preferred live-store paths and captured fallback paths remain distinct; no replay guarantee is inferred.
- **INV-8 — docs-only/cross-repository isolation:** no runtime file in any repository changes; Meander pins are evidence, not write targets.
- **INV-9 — exact content scope:** every successor hunk maps to O1-01…O1-10; the rest of the candidate is copied without semantic edits.
- **INV-10 — dirty preservation:** the 112-line unrelated baseline remains byte-for-byte the same status manifest and is never staged/restored.
- **INV-11 — index safety:** disposition changes are only successor links/status notes; the mixed dirty index file is touched/staged only through an independently verified isolated hunk.
- **INV-12 — cadence:** draft, review, independent preflight, amendment/self-check, scoped anchor, content change, closure and archive remain separate authorization/commit gates; no automatic push/merge.

## 7. Acceptance

All boxes remain open in `draft`.

### 7.1 O1 content acceptance

- [ ] **A-O1-01:** Phase 0/1 are explicitly Gate -1-gated with only the bounded, separately authorized discovery exception.
- [ ] **A-O1-02:** Gate -1/DoD sources are pinned and each quantitative criterion retains its original scope.
- [ ] **A-O1-03:** case/draft review is the provisional product axis, Agent is one input, and P0 is post-gate—not default MVP.
- [ ] **A-O1-04:** `smallest` is scoped to the coherent review map; phase deliverables do not imply full-map implementation.
- [ ] **A-O1-05:** final-verdict wording uses phase-specific revisions/gates rather than surviving blockers.
- [ ] **A-O1-06:** validation rejection and write failure are distinct; revoked traces never become effective Claim state; §2.4 Scenario wording is unchanged.
- [ ] **A-O1-07:** all three shipped anchor groups match the pinned, full-read source files.
- [ ] **A-O1-08:** §16.4–16.6 carry only the allowed settled/provisional/deferred labels.
- [ ] **A-O1-09:** Explain wording exactly describes manual re-evaluation, lowering-plan-backed preferred live reads and fallback limits, without claiming replay safety.
- [ ] **A-O1-10:** successor title/header/lineage/status note name the completed review, dual verdict and Option 1-only scope while preserving v0.1.

### 7.2 Structural and governance acceptance

- [ ] v0.1 path, 2185-line content and SHA remain unchanged.
- [ ] The exact 16 `NEEDS_DECISION` IDs remain present/open; disposition counts remain `32/23/16/10/2`.
- [ ] A hunk-to-O1 ledger accounts for every successor semantic diff; there are no unmapped changes.
- [ ] Changed paths equal the stage-specific allowlist; no `src/`, `tests/`, API, notebook, external-vault or Meander path changes.
- [ ] No new Python/JSON/Mermaid/API signature/DTO/schema/enum/decision identifier or experiment result is introduced by this slice.
- [ ] Disposition changes are link/status-only; any design-point index change is an independently isolated hunk.
- [ ] Independent preflight reports no required amendment or abandonment blocker before scoped.
- [ ] `git diff --check` passes; index is empty after each commit.
- [ ] Sacred refs are unchanged; the unrelated dirty set remains 112 lines with SHA `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326`.
- [ ] Paired audit mirrors every lifecycle event; no push/merge occurs without separate authorization.

## 8. Implementation Plan

Each numbered transition requires a new explicit authorization unless the repository cadence explicitly groups only non-transition checks.

1. **Step 4.1 — draft:** create this blueprint and paired audit in one single-purpose commit.
2. **Step 4.2 — draft review/tightening:** independently attack scope, O1 mapping, file allowlist and acceptance; apply only review-authorized blueprint corrections.
3. **Step 4.3 — independent preflight:** on a separate preflight branch, re-read the actual referenced files at fixed hashes, construct the hunk-to-O1 ledger, check the mixed-index seam and report required/recommended findings.
4. **Steps 4.4–4.5 — amendment/self-check:** apply all required/recommended preflight findings on the blueprint branch; verify no stale or contradictory wording remains.
5. **Step 4.6 — scoped anchor:** change only blueprint/audit lifecycle fields and freeze the exact content/path allowlists.
6. **Step 4.7 — docs content:** copy v0.1 to the successor path; apply O1-01…O1-10; add only the minimal disposition cross-link/status note and a safely isolated index row.
7. **Step 4.7 review:** independently verify predecessor hash, hunk ledger, semantic-diff questions, open-decision set, dual verdict, path allowlist and dirty baseline.
8. **Step 4.8 — closure:** mark implemented only after every acceptance item has evidence; fill Outcome / Deviations without turning the design-point into current truth.
9. **Step 4.9 — archive process artifacts:** archive the blueprint pair and standalone audits per governance. The v0.1 predecessor remains active in this slice; any later design-point lifecycle move is separately authorized.

## 9. Docs To Update

### Future content targets

- `workflow/design/design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md` — mandatory new successor.
- `workflow/design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md` — minimal successor link/status note.
- `workflow/design/design-points/README.md` — one successor row only if its index hunk can be safely isolated from the pre-existing dirty rewrite.

### Process artifacts

- this blueprint and its paired audit log;
- future independent preflight under `workflow/audit/active/`.

No module docs, `docs/README.md`, source repository, external report or v0.1 predecessor update belongs to this slice.

## 10. Outcome / Deviations

To be completed only at Step 4.8:

- final commits and changed paths;
- O1-01…O1-10 evidence table;
- predecessor hash and dual-verdict/open-decision preservation results;
- independent preflight/review results;
- sacred-ref and unrelated-dirty verification;
- deviations from this blueprint, or explicit `none`;
- process-artifact archive status.
