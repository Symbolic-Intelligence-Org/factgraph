# Preflight: Meander × FactGraph 统一设计 Review Freeze v0.1.1 文本收敛

- Status: complete
- Created: 2026-08-10
- Last Updated: 2026-08-10
- Authority: working triage document; surfaces blueprint-vs-shipped drift before scoped anchor per CADENCE Step 4.3. Does not lock implementation; findings feed back into Step 4.4 amendment.
- Inputs:
  - [`2026-08-10_meander-factgraph-unified-design-v0-1-1.md`](../../blueprints/archive/2026-08-10_meander-factgraph-unified-design-v0-1-1.md), reviewed Step 4.2 blueprint at commit `b392f45f2a9762c7d9225b73acb59077474ffea0`, 276 lines, SHA-256 `dbdf3be726dd3b395f01a7a2f58d8e50e3c56eb795c9ec9da65498faca7bd6eb`
  - [`2026-08-10_meander-factgraph-unified-design-v0-1-1.audit.md`](../../blueprints/archive/2026-08-10_meander-factgraph-unified-design-v0-1-1.audit.md), 83 lines, SHA-256 `5fa8972f0e5dc1580eaea9f471510ea15d4e8a76b906c63520e29e4a9be03f58`
  - [`2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md`](./2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md), Stage 1 audit, 394 lines, SHA-256 `0d1dfb6a5236d15fc8d9ba8624cdc2317915d3a77dc7e5c0ed042b0e429d9329`
  - [`meander-factgraph-unified-design-review-candidate.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-review-candidate.zh.md), frozen v0.1 predecessor, 2185 lines, SHA-256 `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7`
  - [`meander-factgraph-unified-design-adversarial-review-disposition.zh.md`](../../design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md), 381 lines, SHA-256 `f8a2fedb48f6f3f1b1e19b41cdd7a5823352a59cc74aa8b1068c10aaa7bc6e14`
  - shipped/source and research inputs listed in §1.2, all re-read at preflight-row-drafting time
- Outputs / Downstream:
  - Step 4.4 amendment commit on `v0.3.0-blueprint-meander-factgraph-unified-design-v0-1-1-2026-08-10`
  - 本文留在 `workflow/audit/active/`，直到 consuming blueprint 于 Step 4.9 归档；跨分支消费与最终导入受 PF-R05 的 fixed commit/blob 约束
- Related:
  - [`workflow/CADENCE.md`](../../CADENCE.md)
  - [`workflow/templates/audit/preflight.md`](../../templates/audit/preflight.md)
- Blueprint: [`2026-08-10_meander-factgraph-unified-design-v0-1-1.md`](../../blueprints/archive/2026-08-10_meander-factgraph-unified-design-v0-1-1.md)
- Branch: `v0.3.0-meander-factgraph-unified-design-v0-1-1-preflight-2026-08-10` (independent from blueprint branch)

> 本 preflight 是 REQUIRED：该 slice 同时涉及 historical-design compatibility、跨 Meander/FactGraph 的 architecture-facing shipped 描述精确性以及 pre-release verification。它只审计文本收敛蓝图，不授权 successor 写入、实验、代码、ADR、产品建设、push 或 merge。

## 1. Preflight scope

### 1.1 授权边界与方法

本轮只执行 CADENCE Step 4.3。审阅对象固定为 Step 4.2 commit `b392f45f2a9762c7d9225b73acb59077474ffea0`；预检分支只允许新增本文。方法包括：

1. 完整复读 frozen v0.1、Stage 1 audit、disposition 与 reviewed blueprint；
2. 完整复读四份承重 shipped 源码，共 7829 行，并复核实际对象和 handoff 行；
3. 将 O1-01…O1-10 拆成 41 个单一 owner 的 semantic-edit atoms；
4. 对 16 个 `NEEDS_DECISION` 逐行做相邻文本 non-preselection 审查；
5. 对 mixed dirty files 做不写入 worktree 的 synthetic patch 双面校验；
6. 由三个相互独立的只读审阅分别攻击 atom coverage、开放决定和 shipped/governance 事实，主审再复核承重源码区间。

用户在 Step 4.3 开始前没有提供新的 user-side/cross-model Step 4.2 report。此前同一模型内的三路独立审阅只算 internal independent review，不冒充 cross-model evidence；该缺席还必须在 Step 4.4 paired audit 中显式记录。

### 1.2 Re-read manifest

| Class | Repository / path | Pinned identity | Full-read result |
|---|---|---|---|
| Blueprint | `workflow/blueprints/active/2026-08-10_meander-factgraph-unified-design-v0-1-1.md` | 276 lines；SHA `dbdf3be726dd3b395f01a7a2f58d8e50e3c56eb795c9ec9da65498faca7bd6eb` | reviewed exact Step 4.2 object |
| Frozen design | `workflow/design/design-points/active/meander-factgraph-unified-design-review-candidate.zh.md` | 2185 lines；SHA `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7` | byte identity retained |
| Disposition | `workflow/design/design-points/active/meander-factgraph-unified-design-adversarial-review-disposition.zh.md` | 381 lines；SHA `f8a2fedb48f6f3f1b1e19b41cdd7a5823352a59cc74aa8b1068c10aaa7bc6e14` | `32/23/16/10/2`; dual verdict retained |
| Stage 1 audit | `workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md` | 394 lines；SHA `0d1dfb6a5236d15fc8d9ba8624cdc2317915d3a77dc7e5c0ed042b0e429d9329` | O1-01…O1-10 re-read |
| Meander shipped | `/Users/zhenzhili/meander-latest-stack/meander/src/meander/plans/ingest.py` | repo `4ddb8e36f0b7a80e99a7447c719c21b4776d6ca7`; 1390 lines；SHA `84ccc1160d406312c9c9c0c6a985380af61889460f15e652524b62579d41f60d` | full read; lifecycle anchors rechecked |
| hnsm shipped | `src/factgraph/application/protocol/rule.py` | source baseline `dbe79d705a879dda069a0a19b59071ad340bcc76`; 677 lines；SHA `e975e44ff52b6899930044911bfc4813dc9eda9907769c4ffdfd87567caece41` | full read; `RulePortRef:218`, `RuleOccurrence:238` |
| hnsm shipped | `src/factgraph/application/explain/evidence_tree.py` | source baseline `dbe79d705a879dda069a0a19b59071ad340bcc76`; 602 lines；SHA `9993390b0af57158e77ef5b6e9730a3a5a61cfad866062cb7a70fb1c45a8dfe8` | full read; `EvidenceTimeline:143`, `EvidenceGraph:155` |
| hnsm shipped | `src/factgraph/sdk/store.py` | source baseline `dbe79d705a879dda069a0a19b59071ad340bcc76`; 5160 lines；SHA `e4dd5fdc302f9d099ac5aee0024f89b1623e77b11df16186a7ba7b525c514e70` | full read; manual/native/fallback paths rechecked |
| Research | `codex_report/01_执行摘要与最终判决.md` | 186 lines；SHA `cc6eb3297a4b33ceebbd675eb896b13519a2f183758ca1a03b7dd9a5acc65f3d` | full read |
| Research | `codex_report/09_实验路线_停止条件与迁移.md` | 227 lines；SHA `7f8f73ce18b8e688daa485cf465a06157993a94bef60ed3b4a03f406df2da474` | full read; missing `:98-106` anchor found |

External evidence repositories were read-only and clean at row drafting:

| Repository | HEAD | `git status --porcelain=v1 --untracked-files=all` |
|---|---|---|
| Meander | `4ddb8e36f0b7a80e99a7447c719c21b4776d6ca7` | 0 lines；SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| meander-agent | `e4b044911de5495ffa93edeba933985588b51cfa` | 0 lines；SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| factgraph-new | `b92d6bf5405be8d15eedea5b97aa7408914e76b9` | 0 lines；SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

Local governance coordinates at row drafting:

- preflight branch fork: `b392f45f2a9762c7d9225b73acb59077474ffea0`;
- sacred `master`: `854d03b9a960c0be8c6b86cfd6d2b5ae72bc90b0`;
- `v0.1-oss-prep`: local and remote-tracking refs absent; do not create;
- unrelated dirty baseline: exactly 112 lines and SHA-256 `c058409c63252bf1c0c8289a58133b551ca49ec112296ad8b4d5d7500b1be326` when and only when measured with `git status --porcelain=v1 --untracked-files=all`;
- index: empty before this artifact is staged.

## 2. 5-bucket findings

### 2.1 Required amendment before scoped

#### PF-R01 — 语义差分与 dirty manifest 的机器验证合同不充分

Blueprint 先把 2185 行 predecessor 复制为新 path，再要求 ledger 覆盖 successor 的 added/removed spans。普通 repository Git diff 会把整个新文件视为新增，无法证明哪 41 个 atom 实际改变了语义。同时，在排除本文这个唯一 in-scope artifact 后，blueprint 固定的 112-line unrelated dirty baseline 只有 `--untracked-files=all` 能复现；默认 porcelain 折叠为 41 行。本文未提交时的 raw counts 会分别多 1，不能被误写成 baseline drift。

Step 4.4 必须明确：

- semantic coverage 比较 frozen predecessor **内容**与 successor 内容，规范操作等价于 `git diff --no-index <predecessor> <successor>`；
- repository commit diff 只证明 path allowlist，不承担 predecessor→successor semantic coverage；
- new API/DTO/schema/enum/decision/experiment absence 只检查 predecessor→successor 的 added semantic lines，不能 grep 全文；
- 所有 112-line baseline checks 固定使用 `git status --porcelain=v1 --untracked-files=all`，再计算 manifest hash。

#### PF-R02 — O1-02 缺失 Translator 50% kill 条件的 pinned research anchor

Blueprint O1-02、INV-5 和 acceptance 使用“Phase 2 Managed Translator mapping/ontology 实施与维护工时 `>50%`”条件，但 Inputs 对 report 09 只 pin `:17-30/:124-132/:220-225`。该条件实际在 report 09 `:98-106`，具体语句位于 `:103`。

Step 4.4 必须把 `:98-106` 加入 report 09 的承重锚点；该动作只补证据坐标，不提升 research summary 的 authority，也不启动 Translator 实验。

#### PF-R03 — O1-06 将多个不同写入失败路径压成了不完整的状态模型

Reviewed blueprint 对 governance-blocked 和 validation-rejected 的方向正确，但对 write/recovery 的文字仍不够精确：

- terminal `rejected_write_failure` 包含两种不同事实：
  1. `PlanWriteFailure`：graph write 失败，in-request rollback 成功；append-only ledger **可能**留下 revoked traces，但无 effective Plan fact；
  2. 第二次 `WriteBoundaryError`：write boundary 在首个 write 前拒绝，两次尝试后终止，**根本没有写入**。
- 非 terminal `ingesting` 不只来自 rollback 自身失败。`create_ingesting` 之后未被局部 catch 的异常均由 receiver wrapper 记录并留给 recovery；已确认包括 rollback 后 `save_workspace()` 失败（`ingest.py:280-293`）、正常 write 后的 `save_workspace()` 失败、`record_accepted()` 失败（`:1168-1169`）以及其他 post-create-ingesting unexpected exception（`:429-446`）。
- owner 需要分层写清：Meander `PlanStore` 记录 Plan lifecycle；Meander graph-service orchestration 调用 write/rollback/recovery；相邻 shipped FactGraph ledger 保存事实与 retract 历史。target hnsm FactGraph 与 `LegacyV3Adapter` 不是 shipped Plan lifecycle 的写入主体。

Step 4.4 必须同步修正 §4.2 O1-06、INV-6、A-O1-06 和 atom guards。承重范围至少为 `ingest.py:89-92/:183-213/:280-293/:429-446/:1078-1095/:1116-1131/:1133-1169/:1333-1383`。不得把“可留 revoked traces”写成所有 terminal write failure 的共同必然后果，也不得把所有非 terminal `ingesting` 简化为 rollback failure。

#### PF-R04 — O1-09 的 handoff 行号偏一，ProbLog fallback 也不是完全冻结路径

`store.py:3413/:3453` 是函数调用起始行；当前 `self._store` 实参实际位于 `:3414/:3454`。更稳妥的承重范围是 Soufflé `:3413-3424` 与 ProbLog `:3453-3469`。

此外，ProbLog captured-envelope fallback 在 `:3488` 注入 `_problog_input_certainty_for_goal`，该 callback 于 `:3518-3536` 查询当前 ledger。它因此是“captured proof trace + current-ledger certainty callback”的 hybrid fallback，不是完全冻结、可安全 replay 的 captured artifact。Step 4.4 必须同步修正 O1-09、INV-7、A-O1-09 与 atom guard，并继续禁止 all-path-live、fully-frozen 或 replay-safe 主张。

#### PF-R05 — preflight input 的跨分支可达性与 absent cross-model evidence 尚未闭合

本文位于独立 preflight branch；未来 Step 4.7 implementation branch 按 blueprint 从 scoped blueprint anchor fork，因此不会自然包含本文。但 Step 4.7 必须消费本文的 atom ledger、16-row matrix 和 guards。仅在 Step 4.9 才“import if necessary”会让实现审阅依赖一个未固定的 branch tip。

Step 4.4 必须：

1. pin 本 preflight 的 exact commit 和 artifact blob SHA；
2. 规定 Step 4.7 通过固定对象读取，例如 `git show <preflight-commit>:workflow/audit/active/2026-08-10_meander-factgraph-unified-design-v0-1-1-preflight.md`，而非浮动 branch name；
3. Step 4.9 只导入与该 blob content-identical 的 artifact；
4. 在 paired audit 显式记录“Step 4.3 前没有收到 user-side/cross-model report”；internal same-model reviews 不计作替代证据。

### 2.2 Recommended amendment before scoped

#### PF-Rec01 — 限定 §16.4 `SETTLED DIRECTION` 的适用范围

AS-10 要求的标签可以保留，但 frozen §16.4 同时触及 source disclosure、tenant、retention/expiry、UI/export。CE-05、CE-06、AS-02 仍然开放。Step 4.4 宜明确：settled 的只是 source content 的最小披露与 Meander access-control 边界；tenant keying、retention/erasure/legal-hold/replay precedence 仍开放。不能用一个 heading 标签隐式关闭三项决定。

#### PF-Rec02 — PM-03 guard 保留 OEM 与 `both/neither`

Gate -1 的 standalone concierge / evaluator plugin 双报价只是两个实验臂，不穷尽 packaging 决定。PM-03 的准确问题还包括 OEM，并允许 standalone/embedded/both/neither。Step 4.4 宜在 O1-02 guard 明确“双报价不排除 OEM，也不要求唯一赢家”。

#### PF-Rec03 — 固化 mixed-file seam 的当前证据与重验证条件

只写入临时 patch 的双面 check 已证明存在可隔离位置，但这不是未来无条件许可：

- `workflow/design/design-points/README.md`：index/HEAD blob `5f2bd2cfc523ac6eb574f882f2e751207f7d76bc`；当前 worktree blob `fb40a7d9dbc126af3c1ac5aa8f52a281f5a21ac9`，SHA-256 `f844703b0fba74ba7b783db37a392a7c71c23794281b6c20cdc37f5f24cb9c76`；安全候选位置是 active table 尾部、未改 header 前，不邻接用户 dirty candidate row。
- `workflow/blueprints/archive/INVENTORY.md`：index/HEAD blob `0d5ec4281b6a3106353fc5c2b42c5a19a9ab260b`；当前 worktree blob `de79dc2839768008203c4363dc9b3bba59ae925b`，SHA-256 `6d91f834d7ec88c3bd3aefd7249ff729a842190c86d84ff9bc44e20ea363a464`；候选位置为未改表头分隔线后、用户 2026-08-08 rows 前。

Step 4.4 宜把这些仅作为 seam recipe/pin；Step 4.7/4.9 必须先重验 base/worktree blob，再做 cached synthetic patch、cached-only task row、residual user hunk 和 post-commit 112-line manifest 四重证明。任一 identity 漂移或 isolation check 失败即停。

### 2.3 Verified assumptions

#### PF-V01 — Option 1 仍是可执行的 docs-only slice

41 个 atoms 均能唯一落到 O1-01…O1-10；未发现必须新增 API、DTO、schema、ADR、decision、experiment artifact 或运行时代码的内容。Abandonment blocker 为 0。

#### PF-V02 — 双裁定与开放决定尚未被 blueprint 预选

Architecture `REVISE` 与 product `STOP-except-discovery` 仍分离。16 个 `NEEDS_DECISION` 均未被 O1 的拟议文字回答；CE-05/CE-06/AS-02 只有 §16.4 状态标签的局部误读风险，已列 PF-Rec01。

#### PF-V03 — 四份 shipped source pins 与核心对象成立

四文件当前 hashes/lines 与 Stage 1 evidence 一致；hnsm 三份源码相对 `dbe79d705a879dda069a0a19b59071ad340bcc76` 无变化。`RuleOccurrence:238`、`EvidenceTimeline:143`、`EvidenceGraph:155`、manual Explain `:3020-3045`、native preferred/fallback 大边界均成立；本 preflight 只收紧其中两个 handoff 与 hybrid fallback 的表述。

#### PF-V04 — 外部仓库仍只读且 pins 未漂移

Meander、meander-agent、factgraph-new 三个 HEAD 均与 blueprint pin 一致，完整 untracked status 均为空。没有运行测试、写入 repo 或更新 dependency。

#### PF-V05 — mixed seams 当前存在可验证的隔离方案

针对两个 mixed files 的 zero-context synthetic patch 已分别通过 index-side 和 worktree-side `git apply --check --unidiff-zero`；临时 patch 已删除，worktree 未被该检查修改。该结论只证明“当前有候选 seam”，不替代实际 stage 前重验。

### 2.4 Scoped-detail items

#### PF-S01 — implementation guard 使用 exact quote/heading，不使用 successor 行号

Successor 在前部插入 metadata/gate 文本后行号必漂移。Step 4.7 应使用 predecessor 中唯一 exact quote 或 section heading 作为 before guard；本文行号只供导航。

#### PF-S02 — actual successor 必须重新跑 16-row matrix

§4 的 `No` 只证明 reviewed blueprint 没有 prospective preselection。Step 4.7 review 必须针对实际 predecessor→successor semantic diff 逐行复跑，尤其检查 §9.4、§16.4、Phase 0/1、D01 与 §18.7。

#### PF-S03 — 共享 hunk 不得合并 semantic ownership

§0.1、§17、D01、§2.6 和 §23 会出现多个 O1 atom 共用物理 hunk；每个 added/removed semantic span 仍需恰好一个 owner。物理相邻不允许把 gate、product axis、shipped fidelity 或 lineage 合并成一个模糊修改。

#### PF-S04 — negative guards 只约束新增完成态语义

Predecessor 本身已有 illustrative API/DTO/Plan/Experiment 字样。检查应针对 semantic diff 新增行以及 exact protected strings/hashes，不对完整 successor 作误报式关键词封禁。

### 2.5 Abandonment blockers

`0`。没有证据要求放弃 Option 1、修改 frozen predecessor、改变双裁定或转向运行时实现。

## 3. Semantic-edit-atom ledger

记号：`P` 是 frozen predecessor。Target 中的 `exact` backtick text 按 case-sensitive `B-LIT` 匹配；`exact regex` 按 `B-RE` 匹配。After guard 使用以下唯一语法：`LIT("...")` 是 case-sensitive literal；`RE(/.../i)` 是显式 regex；`ALL[g1; g2]` 要求全部命中；`ANY[g1; g2]` 要求至少一个命中；`DISTINCT[g1; g2]` 还要求两个子 guard 命中不同的 Markdown list item、table cell 或 paragraph。没有 bare token，也不赋予 `/` 隐含语义。

After guard 的扫描域不是整个 successor section，而是 normalized predecessor→successor semantic diff 中**归属于该 change_id 的 added spans**，按文档顺序拼接。Step 4.7 evidence 必须记录 `successor line + byte/substring span -> one change_id`；一个 semantic span 恰有一个 owner，context/unchanged lines 不进入扫描域。共享物理 hunk 不扩大扫描域。每个 atom 只有一个 O1 owner。

| change_id | Target / exact before anchor | Required after guard | Owner | Evidence | Forbidden delta |
|---|---|---|---|---|---|
| AT-0101-01 | P §0.4 exact `Passing the architecture gate cannot substitute for passing the product gate.` | `ALL[LIT("Gate -1"); LIT("Phase 0"); LIT("Phase 1"); LIT("pure design"); LIT("audit"); LIT("separately named user authorization"); LIT("budget-capped"); LIT("disposable"); LIT("not product approval"); LIT("must not force product continuation")]` | O1-01 | audit `:173`; disposition `:77/:117/:256` | 不宣称 gate 已通过/启动 spike |
| AT-0101-02 | P §17 exact `This is a risk-first candidate sequence, not an implementation authorization.` | `ALL[LIT("Gate -1"); LIT("Phase 0"); LIT("Phase 1"); LIT("separately named"); LIT("budget-capped"); LIT("disposable"); LIT("not product approval"); LIT("Phase 2"); LIT("ADR"); LIT("blueprint"); LIT("user authorization")]` | O1-01 | audit `:173`; disposition `:117` | 不移除 Phase 2+ gate |
| AT-0101-03 | P exact heading `### Phase 0: freeze coordinates and fixtures` | `ALL[LIT("Entry"); LIT("Gate -1"); LIT("passed")]` | O1-01 | audit `:173`; report09 `:32` | 不把 docs/fixtures 当绕门理由 |
| AT-0101-04 | P exact heading `### Phase 1: three disposable spikes in parallel` | `ALL[LIT("Entry"); LIT("Gate -1"); LIT("passed"); LIT("§0.4"); LIT("separately named")]` | O1-01 | disposition `:256/:261` | 不自动授权 spikes |
| AT-0101-05 | P D01 exact `any product build beyond fixtures` | `ALL[LIT("Phase 0"); LIT("Phase 1"); LIT("product build"); LIT("§0.4"); LIT("discovery-parallel")]` | O1-01 | audit `:173`; disposition `:117` | 不把一般 discovery 变实现例外 |
| AT-0102-01 | P header exact `Product research package:` | `ALL[LIT("cc6eb3297a4b33ceebbd675eb896b13519a2f183758ca1a03b7dd9a5acc65f3d"); LIT(":154-168"); LIT("7f8f73ce18b8e688daa485cf465a06157993a94bef60ed3b4a03f406df2da474"); LIT(":17-30"); LIT(":98-106"); LIT(":124-132"); LIT(":220-225")]` | O1-02 | audit `:94-99`; report09 `:103` | 不提升 summary authority |
| AT-0102-02 | P Phase -1 exact `Use the source-bound reviewer prototype and baseline ablation defined by the research package.` | `ALL[LIT("8–10"); ANY[LIT("≥5"); LIT("at least 5")]; LIT("walkthrough"); LIT("lawful"); LIT("source-aligned"); LIT("historical case bundle"); LIT("5–10"); LIT("manual"); LIT("native"); LIT("claim")]` | O1-02 | report01 `:154-156`; report09 `:17-30` | walkthrough 与 case bundle 不合并 |
| AT-0102-03 | P Phase -1 exact `Use the source-bound reviewer prototype and baseline ablation defined by the research package.` | `ALL[LIT("QA"); LIT("simple rules"); LIT("LLM judge"); LIT("FactGraph"); LIT("standalone concierge"); LIT("evaluator plugin"); LIT("reviewer value"); LIT("data access"); LIT("cost-bearing pilot"); LIT("STOP-except-discovery"); LIT("OEM"); LIT("both/neither"); LIT("does not decide PM-03")]` | O1-02 | audit `:174`; report01 `:156`; disposition PM-03 | 双报价不预选包装 |
| AT-0102-04 | P §18.7 exact `These override architecture elegance and aggregate scores:` | `ALL[LIT("Phase 3 promotion"); LIT("relative to baseline"); LIT("payment-relevant"); LIT("customer-co-defined"); LIT("30%")]` | O1-02 | report09 `:124` | 不泛化成全局 kill threshold |
| AT-0102-05 | P §18.7 exact `These override architecture elegance and aggregate scores:` | `DISTINCT[ALL[LIT("10"); LIT("priced"); LIT("integration"); LIT("<3"); LIT("paid pilot")]; ALL[LIT(">7"); LIT("incumbent")]]` | O1-02 | report01 `:168`; report09 `:128-129/:223` | 两条件不得合成一项 |
| AT-0102-06 | P §18.7 exact `These override architecture elegance and aggregate scores:` | `ALL[LIT("Phase 2"); LIT("Managed Translator"); LIT("mapping"); LIT("ontology"); LIT("implementation"); LIT("maintenance"); LIT(">50%")]` | O1-02 | report09 `:98-106` | 不泛化到所有 semantic engineering |
| AT-0102-07 | P §18.7 exact `These override architecture elegance and aggregate scores:` | `ALL[LIT("Gate C"); LIT("total stop"); LIT("semantic customization"); LIT("engineering"); LIT(">50%"); LIT("cannot form a reusable vertical pack")]` | O1-02 | report01 `:166-168`; report09 `:220-225` | 不与 Translator 50% 合并 |
| AT-0102-08 | P D01 exact `Product wedge and product gate evidence` | `ALL[LIT("Gate -1"); ANY[LIT("definition of done"); LIT("DoD")]; LIT("does not decide PM-03")]` | O1-02 | audit `:174`; disposition `:119-120/:249` | 不预选 packaging |
| AT-0103-01 | P §0.1 exact `in which an Agent only declares what it wants checked` | `ALL[LIT("source-bound case or draft"); LIT("Agent output or intent"); LIT("one possible input")]` | O1-03 | audit `:175`; disposition `:118` | 保留 conditional Agent chain |
| AT-0103-02 | P exact heading regex `^### 1\.1 Product core — .*SETTLED DIRECTION.*, conditional on product gate$` | `ALL[LIT("PROVISIONAL"); LIT("EXPERIMENT REQUIRED"); LIT("Gate -1"); ANY[LIT("not passed"); LIT("unpassed"); LIT("has not passed")]]` | O1-03 | audit `:175`; disposition `:118` | 不写 settled/adopted axis |
| AT-0103-03 | P thesis exact `A source-bound Verify and review layer that turns Agent output or intent into a versioned, challengeable, replayable assessment under operator-owned policy and evidence rules.` | `ALL[LIT("source-bound case or draft"); LIT("Agent output or intent"); LIT("one possible input"); LIT("operator-owned")]` | O1-03 | disposition `:80/:118` | 不删除 conditional Verify architecture |
| AT-0103-04 | P §1.1 exact `help a reviewer understand or challenge an Agent case.` | `LIT("source-bound case or draft")` | O1-03 | audit `:175` | 不把 Query/What-if 变通用产品 |
| AT-0103-05 | P exact heading regex `^### 1\.3 Initial implementation cell — .*PROVISIONAL.*$` | `ALL[LIT("post-gate"); LIT("Agent/compatibility"); LIT("PROVISIONAL")]` | O1-03 | audit `:175`; disposition `:124` | 不称 default MVP |
| AT-0103-06 | P §1.3 exact `The first production-compatible cell is deliberately narrow:` | `ALL[LIT("post-Gate -1"); LIT("Agent/compatibility profile"); LIT("deliberately narrow")]` | O1-03 | audit `:175` | 不宣称 production authorization |
| AT-0103-07 | P §1.3 exact `Parallel experiments may test L0 Translator + A0 and L1 explicit validation + A0.` | `ALL[LIT("post-Gate -1 by default"); LIT("§0.4"); LIT("separately named"); LIT("budget-capped"); LIT("disposable"); LIT("not product approval")]` | O1-03 | disposition `:118/:124`; O1-01 gate precedence | 不造第二套 exception，也不静默删除 §0.4 exception |
| AT-0103-08 | P §9.3 exact `This is closest to shipped v3 and is the default MVP candidate.` | `ALL[LIT("post-gate"); LIT("Agent/compatibility profile"); LIT("not the default MVP")]` | O1-03 | audit `:175`; disposition `:124` | 不改变 P0 技术形状 |
| AT-0104-01 | P §0.1 exact `the smallest end-to-end product and technical architecture` | `LIT("the smallest coherent review map for the stated scope")` | O1-04 | audit `:176`; disposition `:132` | Agent clause 归 O1-03 |
| AT-0104-02 | P §17 exact `This is a risk-first candidate sequence, not an implementation authorization.` | `LIT("Each authorized phase is bounded by its listed artifacts/deliverables and does not authorize the full review map.")` | O1-04 | audit `:176` | 不重写 phase artifact lists |
| AT-0104-03 | P §23 exact `the smallest coherent cross-project candidate` | `LIT("the smallest coherent review map for the stated scope")` | O1-04 | audit `:176` | 版本号归 O1-10 |
| AT-0105-01 | P §22.5 exact `REVISE     promising, but named blockers must be repaired before the experiment` | `ALL[LIT("REVISE"); LIT("phase-specific"); LIT("required revisions/gates"); LIT("assigned gate")]` | O1-05 | audit `:177`; disposition `:81/:244` | 不改外部 severity/history |
| AT-0106-01 | P §9.4 exact `SHIPPED ingress and governance state machine` + exact `-> blocked/rejected: audit state only; no Claim write/evaluation` | `ALL[LIT("governance-blocked"); LIT("validation-rejected"); LIT("PlanWriteFailure"); LIT("successful rollback"); LIT("rejected_write_failure"); LIT("revoked traces may remain"); LIT("no effective Claim state"); LIT("no evaluation"); LIT("second WriteBoundaryError"); LIT("no write"); LIT("ingesting"); LIT("recovery-needed"); LIT("unexpected post-create"); LIT("not limited to rollback failure")]` | O1-06 | ingest `:89-92/:183-213/:280-293/:429-446/:1078-1169/:1333-1383` | revoked trace 不是所有 terminal 的必然后果 |
| AT-0106-02 | P §9.4 exact `The adapter consumes only an already accepted PlanRecord and its existing assertion refs.` | `ALL[LIT("Meander PlanStore"); LIT("Plan lifecycle"); LIT("Meander graph service"); LIT("write"); LIT("rollback"); LIT("recovery"); LIT("FactGraph ledger"); LIT("target hnsm FactGraph"); LIT("LegacyV3Adapter"); LIT("do not own"); LIT("do not write"); LIT("do not revoke"); LIT("do not reject")]` | O1-06 | ingest ranges in AT-0106-01 | 不改变 Scenario §2.4 lifecycle |
| AT-0106-03 | P Flow A exact regex `B -->.*blocked or rejected.*Existing audit state only; no claims/evaluation` | `ALL[LIT("governance blocked"); LIT("validation rejected"); LIT("rolled-back write failure"); LIT("no-write boundary failure"); LIT("ingesting"); LIT("recovery-needed")]` | O1-06 | audit `:178`; disposition `:169` | 五类结果不得压回一个 rejected edge |
| AT-0107-01 | P §2.6 exact `Governance gate precedes accepted-plan assertion writes` | `ALL[LIT("ingest.py"); LIT("1078-1095"); LIT("1140-1169")]` | O1-07 | audit `:179`; O1-06 owns wider lifecycle ranges | references only |
| AT-0107-02 | P §2.6 exact `Current Rule, occurrence and port substrate` | `ALL[LIT("RulePortRef"); LIT(":218"); LIT("RuleOccurrence"); LIT(":238")]` | O1-07 | audit `:153/:179` | 不扩 Rule capability |
| AT-0107-03 | P §2.6 exact `Readonly RuleStructure/EvidenceGraph substrate` | `ALL[LIT("EvidenceTimeline"); LIT(":143"); LIT("EvidenceGraph"); LIT(":155"); LIT("RuleStructure"); LIT(":229")]` | O1-07 | audit `:154/:179` | references only |
| AT-0108-01 | P exact heading `### 16.4 Source retention and privacy` | `ALL[LIT("SETTLED DIRECTION"); ANY[LIT("minimum disclosure"); LIT("minimal disclosure")]; LIT("access control"); LIT("tenant keying remains open"); LIT("retention/erasure/legal-hold/replay precedence remain open")]` | O1-08 | audit `:180`; disposition AS-10; PF-Rec01 | 不关闭 CE-05/06、AS-02；不写 adopted |
| AT-0108-02 | P exact heading `### 16.5 PolicyQueryContract as an information boundary` | `RE(/^### 16\.5 .*PROVISIONAL.*$/i)` | O1-08 | audit `:180` | 不新增机制 |
| AT-0108-03 | P exact heading `### 16.6 TOCTOU and Decision isolation` | `ALL[LIT("Verify isolation"); LIT("SETTLED DIRECTION"); LIT("future Decision profile"); LIT("DEFERRED")]` | O1-08 | audit `:180`; disposition AS-10 | 两种状态不得合并 |
| AT-0109-01 | P §2.6 exact `Manual Explain re-evaluates; native lazy probe can read live ledger` | `ALL[LIT("manual Explain"); LIT("re-evaluates"); LIT("current attached Store/Ledger"); LIT("preferred live-store path"); LIT("captured proof trace"); LIT("current-ledger certainty callback"); LIT("hybrid fallback"); LIT("3020-3045"); LIT("3414"); LIT("3454"); LIT("3427-3438"); LIT("3472-3501"); LIT("3488"); LIT("3518-3536"); LIT("3575")]` | O1-09 | audit `:181`; disposition RR-10; shipped full read | 不写 all-path live、fully frozen、replay-safe |
| AT-0110-01 | P title exact `# Design-Point: Meander × FactGraph 统一设计候选 v0.1（Adversarial Review Freeze）` | `ALL[LIT("v0.1.1"); ANY[LIT("Option 1"); LIT("text convergence")]; ANY[LIT("lineage successor"); LIT("lineage revision")]]` | O1-10 | audit `:182` | 不称 v0.2/final/adopted |
| AT-0110-02 | P header exact `- Inputs:` | `ALL[LIT("meander-factgraph-unified-design-review-candidate.zh.md"); LIT("574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7"); LIT("meander-factgraph-unified-design-adversarial-review-disposition.zh.md"); LIT("f8a2fedb48f6f3f1b1e19b41cdd7a5823352a59cc74aa8b1068c10aaa7bc6e14"); LIT("2026-08-10_meander-factgraph-unified-design-v0-1-1-vs-shipped.md"); LIT("0d1dfb6a5236d15fc8d9ba8624cdc2317915d3a77dc7e5c0ed042b0e429d9329")]` | O1-10 | audit `:71-74/:182` | 不改 disposition intake identity |
| AT-0110-03 | P Outputs exact `Independent cold-start adversarial review of this candidate; no review result exists yet` | `ALL[LIT("completed"); LIT("architecture"); LIT("REVISE"); LIT("product authorization"); LIT("STOP-except-discovery"); LIT("Option 1")]` | O1-10 | audit `:127/:182`; disposition `:32-37` | 不平均裁定/转授权 |
| AT-0110-04 | P exact `this is a review-frozen candidate, not an adopted architecture and not current product behavior.` | `ALL[ANY[LIT("narrow lineage successor"); LIT("narrow lineage revision")]; LIT("frozen v0.1"); LIT("not formal supersedes")]` | O1-10 | blueprint current §5.1 | predecessor 不移动/改字节 |
| AT-0110-05 | P exact heading `## 23. Review-freeze status note` + exact opening `This v0.1 deliberately freezes the smallest coherent cross-project candidate that covers:` | `ALL[LIT("v0.1.1"); LIT("PM-03"); LIT("PM-06"); LIT("CE-03"); LIT("CE-05"); LIT("CE-06"); LIT("CE-08"); LIT("SC-01"); LIT("SC-03"); LIT("SC-05"); LIT("SC-12"); LIT("SF-04"); LIT("AS-02"); LIT("AS-06"); LIT("AS-11"); LIT("AC-16"); LIT("AC-24")]` | O1-10 | audit `:186-197` | 不回答/改名/新增 D/Q |
| AT-0110-06 | P final exact `Those are the points the next adversarial review and experiments are intended to kill or preserve.` | `ALL[LIT("completed adversarial review"); LIT("did not close"); LIT("assigned decisions/gates/experiments"); LIT("REVISE"); LIT("STOP-except-discovery"); LIT("Option 1")]` | O1-10 | disposition `:353-360` | 不宣称验证通过 |

Ledger completion rule: every predecessor→successor added/removed non-context span must map to exactly one row above. Context-only relocation is not allowed as a way to hide an unmapped semantic change.

## 4. Open-decision non-preselection matrix

本表回答的是 reviewed blueprint 的 prospective effect；Step 4.7 必须对实际 successor 重跑。

| Finding | Accurate open question | Adjacent successor loci | Answer/preselection introduced? | Evidence / guard |
|---|---|---|---|---|
| PM-03 | standalone、embedded/incumbent evaluator、OEM、both/neither 中哪种包装获得证据 | §0.1/§1.1/§13.2/Phase -1/§18.7/D01 | No | disposition `:119/:249/:333`; PF-Rec02 keeps OEM/both/neither |
| PM-06 | freshness 独立状态、policy owner/version/disposition 与 replay pin | §10.4/§14.1/§16.1/D08/D10 | No | disposition `:122/:262/:293`; source-aligned ≠ freshness validated |
| CE-03 | 同名 old/new evaluator 双跑 topology、projection、pins、artifact owner、rollback | §2.2/§9.4/Phase 3/§17.1 J2；尚无 assigned D | No | O1-06 only corrects shipped ingest owner; do not route into D10 |
| CE-05 | credential-derived tenant isolation for artifact/cache/index/export/store | §4.1/§10.4/§16.3–16.4/Phase 3；尚无 tenant D | No | PF-Rec01 prevents §16.4 status smuggling |
| CE-06 | retention、erasure、legal hold、replay degradation/precedence/UI | §12.4/§16.1/§16.4/Phase 4/D10 | No | settled scope limited; mechanism remains open |
| CE-08 | cross-repo fixture/schema canonical owner、version pin、joint CI anchor | Inputs/Phase 0/§17.1 J1 | No | docs provenance is not future fixture ownership |
| SC-01 | asymmetric join×Any: branch-scoped or reject-on-partial | §6.2–6.3/Phase 1–2/§18.3/D03 | No | construction allowed; lowering semantics untested/unset |
| SC-03 | Policy v0 may compose which NotAtom/aggregate managed Rules | §6.3/Phase 1–2/§18.3/D03 | No | conditional Policy target ≠ capability decision |
| SC-05 | semantic digest endpoint-local or whole ontology; migration behavior | §6.1/§16.1/Phase 2/D02 | No | no digest mechanism added |
| SC-12 | DNF over-limit as publication vs request failure; static/runtime budget/result axis | §6.6–6.7/§14.1/Phase 2/§18.3/D06 | No | no failure-axis choice added |
| SF-04 | package-name conflict requires dual venv/IPC/batch topology | §2.2/§9.4/Phase 3/§17.1 J2；尚无 assigned D | No | separate row retained from CE-03; do not route into D10 |
| AS-02 | tenant credential scope/cache key/unified deny/404 across all artifacts | §4.1/§10.4/§16.3–16.4/Phase 3；尚无 tenant D | No | PF-Rec01; separate row retained from CE-05 |
| AS-06 | widen-review behavior and caller/reviewer dual view of mandatory Policy/Explanation | §6.4/§9.1/§11.2/§16.5/D05/D07 | No | §16.5 remains PROVISIONAL |
| AS-11 | SourceLocator round-trip/admission executor and handoff to premise policy | §8.1/§10.4–10.5/§11.2/§16.1/D08 | No | Plan Claim write owner ≠ Source admission executor |
| AC-16 | lineage identity comparison that reliably excludes self-support | §5.1/§7.1/§11.2/§15.3/§18.1/D08 | No | source-bound/aligned does not implement lineage check |
| AC-24 | mandatory Policy enumeration, fail-closed omissions and per-unit partial failure | §9.1/§9.3/§11.2/§12.3/§14.1/D07 | No | A0/A1 floor ≠ completeness mechanism |

Guard: CE-03/SF-04 and CE-05/AS-02 share problem neighborhoods but remain four independent finding rows; no de-duplication by cluster.

## 5. Machine and semantic guards

### 5.1 Exact identity guards

- predecessor path remains present, 2185 lines, SHA `574677ddd30d2a7ec8933785cbcb258a8758c793bd34c115ea138162aa9df6c7`;
- disposition retains exact 83 IDs, `32/23/16/10/2`, `REVISE`, `STOP-except-discovery`; its implementation diff is §11 link/status only;
- successor is `Status: working`, candidate/non-authoritative, v0.1.1 narrow lineage revision, never `final`, adopted architecture or formal `supersedes`;
- exact open set remains `PM-03 PM-06 CE-03 CE-05 CE-06 CE-08 SC-01 SC-03 SC-05 SC-12 SF-04 AS-02 AS-06 AS-11 AC-16 AC-24`;
- D01–D18 numbering stays exact; no D19 or new Q identifier;
- §2.4 exact invariant “Scenario premise -> never written to authoritative ledger” remains semantically unchanged;
- external repo HEAD/status table in §1.2 remains exact;
- sacred refs and dirty manifest remain exact using `--untracked-files=all`.

### 5.2 Content guards

- §1.1 contains `PROVISIONAL` and `EXPERIMENT REQUIRED`, not settled/adopted product axis;
- Phase 0/1 cannot start without Gate -1 except separately named, budget-capped, disposable user-authorized experiment; that exception is not product approval;
- Gate -1 evidence conditions retain independent scopes; PM-03 remains open including OEM/both/neither;
- Meander failure lifecycle distinguishes governance blocked, validation rejected, two terminal write-failure facts and nonterminal recovery-needed cases;
- §16.4 settled label is locally scoped and cannot imply tenant/retention decisions;
- Explain wording uses `self._store` at `:3414/:3454` and names the ProbLog hybrid callback;
- new API/DTO/schema/enum/decision/experiment artifact check applies only to predecessor→successor semantic additions.

### 5.3 Required semantic review answers

Independent Step 4.7 review must answer `No` to all four:

1. Does the successor close or preselect any of the 16 `NEEDS_DECISION` items?
2. Does it start or claim passage of any gate, experiment, benchmark or pilot?
3. Does it add or promise any API, schema, implementation or cross-repository mutation?
4. Does it weaken `STOP-except-discovery` or turn `REVISE` into architecture approval?

Any `Yes`, uncovered atom, broken pin or unisolatable dirty seam returns to blueprint amendment; it is not a review-fix convenience.

## 6. Cross-slice contract preservation

| Contract | Preflight result |
|---|---|
| Frozen predecessor | Verified byte-identical at fixed SHA; no mutation/move/archive authorized |
| Dual verdict | Verified separate; no product authorization inferred from architecture feasibility |
| 16 open decisions | Verified prospectively unselected; actual successor recheck required |
| Scenario premise lifecycle | Protected exact semantic invariant; O1-06 cannot rewrite it |
| Shipped vs target boundary | Required owner tightening in PF-R03; target hnsm/adapter remain non-writers of shipped Plan lifecycle |
| Explain live/fallback boundary | Required hybrid-path tightening in PF-R04; replay safety remains unimplemented |
| Sacred branches | `master` fixed; `v0.1-oss-prep` absent; no push/merge/create authorized |
| Dirty worktree | 112-line full-untracked manifest fixed; mixed seams are conditional, not pre-authorized |
| Stage transitions | Step 4.3 only; Step 4.4 needs separate authorization and occurs on blueprint branch |

## 7. Findings summary

| Bucket | Count | Items |
|---|---:|---|
| Required | 5 | PF-R01…PF-R05 |
| Recommended | 3 | PF-Rec01…PF-Rec03 |
| Verified | 5 | PF-V01…PF-V05 |
| Scoped-detail | 4 | PF-S01…PF-S04 |
| Abandonment | 0 | — |

该 `5/3/5/4/0` 分布高于模板给出的 healthy heuristic；没有为了凑数合并不同 failure domain。五个 Required 分别约束验证合同、研究证据、ingest lifecycle、Explain fidelity 与跨分支审计链，均有独立证据和不同的 Step 4.4 落点。

## 8. Recommended Step 4.4 amendment actions

| Finding | Blueprint-pair amendment |
|---|---|
| PF-R01 | Amend §4.1, §5.3, §6/INV-9, §7.2, §8, INV-10 and paired audit: separate predecessor→successor semantic comparator from repo path diff; fix every dirty command to `--untracked-files=all` and exclude the in-scope artifact when comparing the unrelated baseline |
| PF-R02 | Amend Inputs, O1-02 evidence, INV-5 and acceptance to pin report09 `:98-106` |
| PF-R03 | Amend O1-06, INV-6, A-O1-06 and ledger requirements with two terminal write-failure facts, broader nonterminal recovery causes and three-layer owner wording |
| PF-R04 | Amend O1-09, INV-7, A-O1-09 and guards to `self._store:3414/:3454` and ProbLog hybrid fallback `:3488/:3518-3536` |
| PF-R05 | Amend Inputs/downstream/Step 4.7/4.9 and paired audit to pin this preflight commit+blob, define fixed cross-branch consumption/import, and record absent user-side report |
| PF-Rec01 | Qualify §16.4 settled scope without deciding tenant/retention/replay questions |
| PF-Rec02 | Preserve OEM and both/neither in PM-03 non-preselection guard |
| PF-Rec03 | Add current mixed-seam pins/recipes and mandatory immediately-before-use revalidation |

Step 4.4 applies these changes only to the blueprint pair on its own branch. It must not edit this preflight, the successor, frozen design-point, disposition, indexes, source or external reports.

## 9. Acceptance for this preflight

- [x] All blueprint-referenced shipped state re-read per Rule 1
- [x] Findings classified into 5 buckets
- [x] At least 2 critical findings spot-checked independently
- [x] Semantic-edit-atom ledger constructed with one owner per atom
- [x] Exact 16-row non-preselection matrix constructed
- [x] External HEAD/status and dirty baseline identities fixed
- [x] Mixed-file seams checked without modifying their worktree content
- [x] No abandonment blocker surfaced
- [x] Cross-slice contract preservation verified
- [x] Only the standalone preflight artifact belongs to this branch/stage

## 10. Result

**Preflight result: AMEND BLUEPRINT BEFORE SCOPED.**

Option 1 remains viable and docs-only, but the reviewed blueprint cannot advance to Step 4.6 as written. Five Required and three Recommended findings must first be dispositioned in a separately authorized Step 4.4 amendment. 本结论不创建 successor，不批准实验或实现，也不改变 `REVISE / STOP-except-discovery`。
