# Task Blueprint: Slice 3b — Ledger 7→3 表迁移 + claim_meta 事件化 + Meta 分级

- Status: scoped
- Created: 2026-08-01
- Last Updated: 2026-08-01
- Branch: `v0.3.0-impl-storage-hardening-2026-07-31`(与 Stage A 同一 v0.3.0 发布线,per Q-SAE-6 四合同同窗)
- Related Modules:
  - `src/factgraph/core/store/ledger.py`(_DDL 与全部内存索引)/ `database.py` / `runtime.py`
  - `src/factgraph/core/store/premise_filter.py`(两层 last-wins 解析)
  - `src/factgraph/core/policy/chosen.py`(seq 定序迁移)
  - `src/factgraph/core/view/projector.py` + `application/entity_write.py` + `sdk/store.py`(读写面适配)
- Related Docs(约束源,全部 adopted / 权威):
  - [ledger-schema-specification.zh.md](../../design/design-points/active/ledger-schema-specification.zh.md) **§9 七步精简为实施权威**(§9.7 被 Q-SAE-8 supersede,见 §6);§2.1 三表终态
  - [Q-SAE-8](../../design/decisions/active/2026-07-31_q-sae-8-claim-meta-history-decision.md)(事件化 + `(tx_seq, op_ordinal)` + receipt as-of 裁定)
  - [Q-SAE-9](../../design/decisions/active/2026-07-31_q-sae-9-meta-tiering-tx-reification-decision.md)(五正交属性 + tx_ref + UNSET + 逐 key 表 + chosen→seq)
  - Stage A 归档 blueprint §7.1 **三条口径护栏**(Q-SAE-8 只落了 tx_seq 地基;Q-SAE-9 只落介质裁定;Q-SAE-3 附则欠账)
- Audit Log:
  - [2026-08-01_slice-3b-ledger-migration.audit.md](./2026-08-01_slice-3b-ledger-migration.audit.md)

## 1. Problem

Stage A 完成写链与生命周期收敛,但表形态仍是 7 表(3 组内建冗余,实测 ~3.9KB/claim,meta 占 90%),claim_meta 无事件历史(含重复键 append 的序列不可重放),meta 无分级(任意 key 可被一行配置激活为功能性)。Q-SAE-8/9 的 adopted 承诺在此兑现。**alpha 窗口(atomic flip 零数据搬迁)是本 blueprint 的时机前提。**

## 2. Goals

1. 7 表 → 3 表 atomic flip:`claims`(+`tx_ref` 列)+ `claim_meta`(事件化)+ `ledger_meta`;
2. spec §9 七步精简全部落地(revokes-as-claim、ingest_keys 退场、双写退场、rest_terms 收口 —— **per adopted Q-SYS-B §4.2(c) 为 partial:双列引入 + `claim_args` 删除属 3b;`rest_terms` 列保留为 legacy 桥(PyReason adapter)至 Slice 5 三项绑定,不加 blanket enforce;2026-08-02 内联裁定确认**、四列删除、surrogate 删除);
3. claim_meta 事件化:`(tx_seq, op_ordinal)` 全序、last-wins=max、UNSET tombstone、receipt as-of 字段;
4. meta 五正交属性声明入 schema digest + tx-lift 存储(批次默认+claim 覆盖)+ audit 类惰性投影 + `premise_eligible` 封闭集 `{provenance_class, origin_binding}`;
5. chosen 定序 ingested_at → seq(承认为语义变更);
6. tx object 承载批次 S 类 meta(护栏:Stage A 只裁了介质,本处兑现能力);
7. 3b 归属的 Stage A known-gaps:append_meta 链-账本 parity 校验、dbtx_v2 golden fixture、application 调 ledger 私有名转正。

## 3. Non-goals

- L2 / Stage B(驻内存模式不变 —— 内存索引随表形态重构,但仍全量驻留);
- schema-evolution(retire/diff 链,独立 blueprint 排队中);
- meander 侧适配、任何 main 合并、引擎/adapter 行为变更;
- ingest 蒸馏(杠杆 1,产品决策未落);identity 重设计。

## 4. Current Context(实施前 Phase 0 必须逐条重验,不得照抄)

- 7 表 `_DDL` 在 ledger.py;内存索引 `_reset_indexes` 族;premise_filter 单层 last-wins(rows[-1] 语义);chosen 按 `(-ingested_at, asrt_id)`;
- Stage A 已就位的地基:单事务 commit_batch、`(tx_seq)` 提交全序、append_meta/schema tx ops(op 序=输入序 → op_ordinal 免费)、LtHash16-v2(state element = asrt_id‖assertion_digest —— **换表不得改变 digest 语义**)、双粒度提交面;
- **护栏**:凡 Stage A 审计标注"归 3b"的项以 audit 归档记录为准;spec §9.7 的复合 PK 表述已被 Q-SAE-8 supersede。

## 5. Proposed Shape(分 Phase,per-phase 对抗审计节奏沿用 Stage A)

- **Phase 0 — 安全网先行**:①dbtx_v2 golden fixture(A/R-only 链 + 含 M/S 链,字节级钉死 —— **在动任何表之前**);②现状锚点全量重 grep;③spec claim_meta 节按 Q-SAE-8 修订(事件化 + supersede 标注);④三组对照测量的**第一组基线**(7 表现状 bytes/claim + 读面基准)。
- **Phase 1 — 3 表 atomic flip(最重)**:新 `_DDL`(claims 含 `tx_ref`;claim_meta 事件行;ledger_meta);七步精简 §9.1-9.6 落地(revokes-as-claim 含 INV-15 五读面过滤、ingest_keys 退场保 Ledger 索引幂等语义、双写退场);内存索引重构;**最高契约:Ledger 读 API 输出逐字节等价**(§2.6 绝缘契约,含 system claims 过滤后)。
- **Phase 2 — claim_meta 事件化语义**:`(tx_seq, op_ordinal)` 全序解析统一全部读取入口;UNSET tombstone(revoker 对称);重复键序列重放等价;receipt as-of 字段(验证默认 latest-effective,as-of 归 audit 面);append_meta 链-账本 parity 校验(known-gap 收口);meta 历史窄域 audit 接口。
- **Phase 3 — Meta 分级**:五正交属性入 schema 声明与 digest;`premise_eligible` 封闭(未声明 key 引用即报错,初始集两 key);tx-lift 存储(批次默认 + claim 覆盖,两层 last-wins 与 premise filter 逐字节等价 differential);audit 类惰性投影(不进求值工作集);chosen→seq(语义变更用例:时间倒挂/同刻/导入);tx object 承载批次 meta;S 类禁覆盖 + `event_time` 回填通道。
- **Phase 4 — 测量 + docs 收尾**:三组对照(7 表基线 / 3 表 / 3 表+分级)bytes/claim 与按 meander 批次分布的摊销;模块 docs(core/store、premise、policy)、spec 终态对齐、CHANGELOG。

## 6. Boundaries And Invariants

- INV 族全程保持(INV-1/5/7c/9/10/11/12/14/15);spec §12 结构不变量逐条测试映射;
- **digest 语义冻结**:`support_digest`/`view_snapshot_digest`(canonical fact bytes)与 LtHash state element 定义不因换表而变 —— 3b 前后同一逻辑世界同 digest(gate);
- premise filter 语义:单层→两层解析必须 differential 逐字节等价(含 revoker 对称、absent_ok、UNSET);
- PR #20/#21/#22 面专项回归(精确调用式沿用 audit log 记录);
- 发布纪律与 Stage A 相同(feature 分支、不合 main、user merge);Phase 间停下走审计;
- **新写通道三侧守卫 checklist**(Stage A 教训 F1/C1 同型洞):任何新增写入口必须同时配断言/撤销/meta 三侧守卫并有负向测试。

## 7. Acceptance

- [ ] 全套件基线不退(2771/32/1 起点;known deselect 唯一);
- [ ] Ledger 读 API 逐字节等价(同逻辑写序列,7 表 vs 3 表,全读 API 对照);
- [ ] `__system__.revokes` INV-15 五读面不外泄 + 推理端 digest 一致门(support/view_snapshot 逐字节);
- [ ] 重复键 append_meta 序列重放等价;UNSET/tombstone 全路径;
- [ ] premise filter differential(两层 vs 单层)逐字节等价;
- [ ] chosen seq 迁移语义变更用例集通过并入 CHANGELOG;
- [ ] dbtx_v2 golden fixture 常驻(Phase 0 建立,全程不破);
- [ ] 三组对照测量落数(预期 ~3.9KB → ~1KB 量级,实测为准);
- [ ] atomic flip 无数据搬迁(alpha);migration CLI 对 3b 前 v0.3 工作区的升级路径裁定并实现或显式拒绝+指引;
- [ ] 受影响模块 docs + spec 修订同步。

## 8. Implementation Plan

1. [Phase 0] goldens + 锚点重验 + spec 修订 + 基线测量(独立 commit);
2. [Phase 1] 新 DDL + 七步精简 + 索引重构 + 读等价 gate;
3. [Phase 2] 事件序解析统一 + UNSET + as-of + parity 校验 + audit 接口;
4. [Phase 3] 属性声明 + premise 封闭 + tx-lift + 惰性投影 + chosen 迁移;
5. [Phase 4] 三组测量 + docs/spec/CHANGELOG。

每步一 commit;Phase 边界停下,Claude 对抗审计放行。

## 9. Docs To Update

- `ledger-schema-specification.zh.md`(claim_meta 事件化修订 + §9.7 supersede 标注 + 终态对齐)
- `src/factgraph/core/store/docs/README.md`(表形态、事件序、meta 分级)
- premise/policy 相关模块 docs;CHANGELOG(chosen 语义变更、ingest_keys 退场等 Breaking 项)
