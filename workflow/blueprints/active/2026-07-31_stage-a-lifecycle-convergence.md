# Task Blueprint: Stage A — Lifecycle 收敛 + 写链加固 + 双承诺指纹

- Status: scoped
- Created: 2026-07-31
- Last Updated: 2026-07-31
- Branch: `v0.3.0-impl-storage-hardening-2026-07-31`(impl;设计基线 = `v0.2.0-design-storage-hardening-2026-07-31` @ 2aae8622)
- Related Modules:
  - `src/factgraph/core/store/database.py` / `ledger.py` / `runtime.py`
  - `src/factgraph/sdk/store.py`(lifecycle 面 + 14 处 `_reject_attached_write`)
  - `src/factgraph/application/entity_write.py` / `workspace_runtime.py`
- Related Docs(约束源,全部 adopted):
  - [storage-hardening-stage-a-slice-3b.zh.md](../../design/design-points/active/storage-hardening-stage-a-slice-3b.zh.md)(§1.2/§2/§3.1/§3.4/§7)
  - [Q-SAE-6](../../design/decisions/active/2026-07-31_q-sae-6-release-target-decision.md) / [Q-SAE-7](../../design/decisions/active/2026-07-31_q-sae-7-data-digest-contract-decision.md) / [Q-SAE-8](../../design/decisions/active/2026-07-31_q-sae-8-claim-meta-history-decision.md) / [Q-SAE-9](../../design/decisions/active/2026-07-31_q-sae-9-meta-tiering-tx-reification-decision.md)
- Audit Log:
  - [2026-07-31_stage-a-lifecycle-convergence.audit.md](./2026-07-31_stage-a-lifecycle-convergence.audit.md)

## 1. Problem

写路径分裂(SDK 直达 ledger vs Database tx 链)造成:attach 模式下 `entities.create/delete` 绕链的完整性漏洞、meander 28 处每写整库快照、workspace 双格式互斥、以及 O(ledger) 的写指纹。设计阶段已完成(四 ADR adopted),本 blueprint 是 v0.3.0 战役的第一实施单元。

## 2. Goals

1. 所有写路径统一经 `Database.commit_changes`;
2. 一次 commit = 一个 SQLite 事务(数据 + head + digest 状态同事务);
3. 双承诺指纹落地(LtHash `state_digest` + tx 历史链),写成本 O(delta);
4. SDK lifecycle 内部化为 `Database.create/open + attach`,拆除 14 处 reject,`save_workspace` 退化为 metadata 更新;
5. 双粒度提交面(批量 batch commit / 交互 per-call);
6. flock 单进程锁 + head CAS;
7. v0.2 workspace 一次性迁移 CLI。

## 3. Non-goals

- Slice 3b 的 schema flip(claims 表仍为现行形态;`tx_ref` 列、claim_meta 事件化、UNSET tombstone 属 3b blueprint);
- meta 正交属性的 schema 声明面(3b);
- L2 / Stage B / eval 层性能(独立线);
- meander 侧适配(其 pin 与适配按 Q-SAE-6 时序另行推进);
- 任何 factgraph main 合并动作。

## 4. Current Context

- **本地 `src/factgraph` 停在 2026-06-25 同步点;实施基线必须是 factgraph main `b92d6bf5`(含 PR #20/#21/#22)→ Phase 0 先做 surgical sync**(沿用 c1d122b0/97db6f6c 的 chore(sync) 先例);
- 现状锚点(全部 2026-07-31 逐行核实):reject 14 处(store.py:406/426/440/610/683/873/886/1340/2162/2174/2189/2219/2583 + 定义 :1734);`entities.create`(:1101)/`delete`(:1202)不在其中;commit_assertions 跨 N 事务 + 2 文件写(database.py:419-458);O(N) digest(:408-410/:550-556/:109-116);head 覆盖写(:832-835);
- 实测基线:digest 3218ms@1M;SQLite 单笔写 0.06ms;冷启动 5.2s+779MB@1M。

## 5. Proposed Shape(分阶段,每阶段后按 per-phase audit 节奏走)

- **Phase 0 — 基线同步**:hnsm-backend `src/factgraph` surgical sync 至 `b92d6bf5`;全套件绿(`PYTHONPATH=src pytest`,排除本机 pandas 损坏的 `test_pyreason_provenance_v0.py`)。
- **Phase 1 — 写链原子化 + 双承诺指纹**(Q-SAE-7 全部):`commit_changes(assertions, revocations)` 统一入口(RevocationInput DTO);单事务批量写(ledger `_write_session` 批量化);head 迁入 `ledger_meta`;LtHash state_digest(增量维护,状态同事务持久化);tx 链输入改为本笔 delta 规范化字节 + `digest_scheme` 版本位;open 时 fail-closed 校验 + 独立 `repair` 流程;flock + head CAS。
- **Phase 2 — 写路径收编**:`planned_ops_to_inputs` 翻译器;`apply_write_plan` → plan → 翻译 → `db.commit_changes`;`entities.create/delete` 入链;批量/交互双粒度提交面(批量面一批 = 一 tx)。
- **Phase 3 — Lifecycle 内部化**:`FactGraph.create/load_workspace` 内部 = `Database.create/open + attach`;拆 14 处 reject;`save_workspace` → metadata 时间戳;workspace 格式收敛 + `migrate-workspace` CLI(Q-SAE-2 按设计文档提案:CLI,opt-in —— 本 blueprint 内联裁定,如有异议在 Phase 3 前提出);**前置项(Phase 2 审计裁定 2026-08-01)**:application `FieldValue` 扩展承载 `bytes`(additive DTO 扩展,application-first)—— 否则 lifecycle 内部化使 bytes 字段(tup_v1 一等 tag)在全部生命周期不可写,构成对 v0.2 的行为回归;扩展落地后撤销 Phase 2 的 attach-bytes fail-closed 挡板;**commit 协议扩展(Phase 3 裁决 2026-08-01,Q-SAE-7 §1/§4 命令内容,blueprint 原漏写)**:①`commit_changes` 增 meta-append 与 schema-transition 输入;②规范化 `append_meta`/`schema_change` tx operations(v2 格式 additive 扩展,canonicalizer docstring 记录,既有 fixture 链必须仍可 replay);③schema op 承诺 old/new digest,replay 按 transition 链验证连续性(additive-only schema 政策不变,schema object 仍 write-once);④meta 不动 `state_digest`、schema transition 只动 history/head schema(Q-SAE-7 §4 原样);⑤内部创建的 Database 由 FactGraph 拥有(幂等 `close()`/context-manager,先查既有 SDK 面再添新 API),`attach(db)` 仍调用者管理;⑥v0.3 不设只读打开通道,文档写明写者独占、双开显式失败(meander 适配注记:多 worker 部署需单写者安排,随 Q-SAE-6 时序处理)。注:append_meta tx op 同时是 Q-SAE-8 `(tx_seq, op_ordinal)` 事件化的地基,本就在 3b 关键路径上;
- **Phase 4 — 文档诚实化 + 收尾**:store.py:2578 stale docstring、母文档 1 §5.5 措辞、模块 docs(core/store + sdk)、CHANGELOG。

## 6. Boundaries And Invariants

- INV-1 append-only、INV-5 可重建、INV-7c、INV-10/11/12/14/15 全程保持;
- `explain()`/evidence/premise filter 行为零回归(PR #20/#21/#22 面专项回归,设计文档 §2.3);
- Ledger 读 API 输出逐字节等价(§2.6 绝缘契约);
- 发布纪律:factgraph 发布走 `feature/...` surgical checkout,**绝不合 main**,user merge;
- Phase 之间:doc-only 严格审计 + fix commit,才进下一 Phase。

## 7. Acceptance(gates 汇总自设计文档 §7 + ADR)

- [ ] 全套件零回归(Phase 0 基线对照);
- [ ] 三 lifecycle 行为等价(同操作序列 → 同 ledger 内容 + 同 head);
- [ ] `entities.create/delete` 经 tx 链:写后 `db.head()` 与 ledger 一致性断言;
- [ ] 指纹差分:增量 state_digest == 全量重算(含撤销后重断言;revoke-of-revoke 按 INV-12 拒绝);
- [ ] 历史区分性:不同历史同终集 → tx 链头不同、state_digest 相同;
- [ ] harness:写耗时曲线平坦(100K/1M);
- [ ] 崩溃注入:commit 中途 kill → open fail-closed → repair 可恢复;
- [ ] flock:双进程打开同 workspace,第二个显式失败;head CAS:并发 commit 一胜一败,无分叉;
- [ ] migration CLI:v0.2 workspace 样本 round-trip;
- [ ] 受影响模块 docs 已同步。

## 8. Implementation Plan

1. [Phase 0] surgical sync → 独立 chore(sync) commit;
2. [Phase 1] database.py/ledger.py:单事务批量写 + head 入 ledger_meta;
3. [Phase 1] LtHash 模块(core/protocol 下,纯函数 + 状态编解码)+ commit 集成 + fail-closed/repair;
4. [Phase 2] entity_write.py 翻译器 + 写路径切换 + entities.create/delete 收编;
5. [Phase 3] sdk/store.py lifecycle 内部化 + reject 拆除 + save_workspace 退化 + migration CLI;
6. [Phase 4] docs + CHANGELOG。

每步一个 commit;Phase 边界处停下走 audit。

## 9. Docs To Update

- `src/factgraph/core/store/docs/README.md`(commit 协议、双承诺、锁语义)
- `src/factgraph/sdk/docs/00_user_guide.en.md` §11 + `04_api_surface.en.md` §2.1(lifecycle 叙事反转)
- `docs/quickstart/` 相关节(§5.5 诚实化)
- `docs/README.md`(如有新文档入口)
