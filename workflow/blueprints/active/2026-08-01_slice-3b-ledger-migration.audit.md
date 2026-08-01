# Audit Log: Slice 3b — Ledger 7→3 表迁移 + claim_meta 事件化 + Meta 分级

- Blueprint: [2026-08-01_slice-3b-ledger-migration.md](./2026-08-01_slice-3b-ledger-migration.md)

## Adopted Conclusions(引用来源 → 本任务采用)

| 来源 | 采用结论 |
|---|---|
| spec §9(权威) | 七步精简逐条落地;§9.7 复合 PK 被 Q-SAE-8 supersede(事件化 PK 含序) |
| Q-SAE-8 adopted | `(tx_seq, op_ordinal)` 全序、last-wins=max、UNSET、receipt as-of(默认 latest-effective / as-of 归 audit)、meta 历史窄域接口 |
| Q-SAE-9 adopted | 五正交属性入 digest、`premise_eligible` 封闭集 `{provenance_class, origin_binding}`、tx_ref 列、tx-lift + 两层 last-wins、audit 类惰性、chosen→seq(语义变更)、S 禁覆盖 + event_time、三组对照测量 |
| Stage A §7.1 护栏 | Q-SAE-8 只有 tx_seq 地基已交付;Q-SAE-9 只有介质裁定已交付 —— 其余在本 blueprint 兑现,不得当作已有 |
| Stage A known-gaps(3b 归属) | append_meta 链-账本 parity、dbtx_v2 golden fixture、application 调 ledger 私有名转正 |
| Stage A 教训 | 新写通道三侧守卫 checklist;blueprint 引用 ADR 承诺表逐行转录;golden 先于动表 |

## Session Journal

| Date | Event | Notes |
|---|---|---|
| 2026-08-01 | blueprint created at `scoped` | scope 由 adopted ADR + spec §9 锁定;Phase 0 把 golden fixture 与 spec 修订前置为安全网;内联裁定待办:migration CLI 对 3b 前 v0.3 工作区的升级路径(§7 倒数第二条)在 Phase 1 前由协调方裁定 |
| 2026-08-01 | **内联裁定:3b 前 v0.3(7 表)工作区无升级路径** | v0.3.0 未发布,7 表格式零真实消费者 —— migrate-workspace CLI 目标改为 v0.2 → 3b 终态直达;Stage A 期间产生的 7 表 dev 工作区显式拒绝 + 指引(重建或从 v0.2 源重迁移)。为一个从未发布的中间格式造迁移器是浪费 |
| 2026-08-01 | Phase 0 dbtx_v2 golden fixture | `af7b92ab`;A/R-only 链与含 append_meta/schema_change 的链均冻结每环 canonical bytes、tx_id 与 genesis→head 推进序列;协议代码零改动 |
| 2026-08-01 | Phase 0 current-context re-anchor | 基于 `af7b92ab` 逐项重 grep blueprint §4;结果与 blueprint 描述一致,证据清单见下文 |

## Phase 0 adopted commitments worklist(verbatim)

以下清单逐行转录 adopted ADR 的承诺与 gates;勾选表示实施 Phase 已完成,**不是**表示 Stage A 已有。

### Q-SAE-8 §1 Decision

- [ ] **claim_meta 事件化:每行是一个不可变 meta event,PK `(asrt_id, key, event_seq)`;last-wins = 组内 `max(event_seq)`。**
- [ ] 采用 **`(tx_seq, op_ordinal)` 二元组**:`tx_seq` = 提交序(Stage A 后一次 commit = 一个事务,天然全序);`op_ordinal` = 本次 commit 内按输入顺序的操作序号(覆盖"一次调用同 key 多次赋值"的次序);
- [ ] 全部读取入口(premise filter、AssertionMeta 投影、reload、导出)统一按此二元组字典序解析;
- [ ] reload/导出/迁移**保序不变量**:落库即定序,任何重建路径不得重排;
- [ ] 失败回滚:事务失败则该 `tx_seq` 下全部事件不存在(原子性由 Stage A 追加项 (a) 保证)—— 无部分序号泄漏。

### Q-SAE-8 §5 验收 gates

1. [ ] 重放等价:含重复键 append_meta 的序列在新表可完整重放,读输出与 6 表现状逐字节等价(含一次调用内多次同键赋值);
2. [ ] premise filter 差分测试:重分类全路径 + revoker 对称可采性;
3. [ ] reload 保序:落库 → 冷启动 → 导出 → 再导入,event 序不变;
4. [ ] 若 (iii) 采纳:as-of 重放正确性(任取历史时点,effective meta 与当时实测一致)。

### Q-SAE-8 §6 裁定

- codex 评审:Q-SYS-B supersede、全局序分配、receipt 语义三分、(b) 拒绝理由不成立 —— **全部采纳**(拒绝结论保留、理由重写);
- [ ] **裁定 1(用户 2026-07-31)**:receipt 承诺语义 = **事件化后 receipt 携带 as-of(event_seq)字段;v0.3 验证默认按 (ii) 最新 effective(现行为);(iii) as-of 重放作为 audit/explain 面能力**;
- [ ] **裁定 2(用户 2026-07-31)**:meta 历史读取 = **v0.3 不出通用 SDK API,保留窄域 audit/debug 接口**。

### Q-SAE-9 §1 五个正交属性

| 属性 | 取值 | 决定什么 |
|---|---|---|
| `reader_class` | `ledger` / `runtime` / `audit` | 谁在运行时读它(`audit` = 无运行时读者) |
| `premise_eligible` | bool | 可否被 premise/可见性配置引用(**默认 false;引用未声明 key 即报错** —— 封闭漂移根源) |
| `load_policy` | `eager` / `lazy` | 是否进求值工作集 |
| `storage_scope` | `claim` / `tx_liftable` | 可否提升为 tx 默认(claim 级覆盖仍可用) |
| `query_indexed` | bool | 是否建查询索引(**可查询 ≠ premise 语义** —— 修正原 `version` 误归 J 的错误) |

- [ ] 原 S/J/F/T 保留为**文档层的常用组合速记**,不再是 schema 模型。

### Q-SAE-9 §2 Tx 具象化

- [ ] **`claims` 与 meta event 行显式携带 `tx_ref`**(8 字节/行,相对 ~1KB/claim 可忽略;换来稳定审计、meta-only 事务支持、可迁移性);
- [ ] tx 级 S/共享 meta 落在 **tx object**(现有 `db/objects/tx/` 谱系,Stage A 裁定其介质)而非必然一条 tx claim —— 是否同时物化 `__system__.tx` claim 供图内查询,降级为 blueprint 实现选项;
- [ ] **与 Q-SAE-1 的强耦合(rev.2 新增)**:per-call 事务粒度会使 tx 元数据条数 ≈ 业务写入条数,批次摊销失效。因此 Q-SAE-1 的裁定必须与本 ADR 联动 —— ✎ 提案:**ingest/批量面走批次 commit(一批 span = 一个 tx),交互式单写维持 per-call** —— 双粒度,由 API 面区分。

### Q-SAE-9 §3 跨层解析

- [ ] 引入显式 **`UNSET` tombstone meta event**(Q-SAE-8 的 event 形态之一,共用 `(tx_seq, op_ordinal)` 序);
- [ ] 统一解析器:effective(asrt, key) = 按事件序取组内最新事件;`UNSET` → 视同缺失;无 claim 级事件 → 取 tx 默认;
- [ ] 该解析器**对普通 claim 与 revoker 对称适用**(premise filter 的 revoker 对称可采性要求)。

### Q-SAE-9 §4 逐 key 归类表

| key | reader_class | premise_eligible | load | storage_scope | 备注 |
|---|---|---|---|---|---|
| seq / tx_ref | ledger | — | eager | 列(非 meta) | 永不覆盖 |
| ingested_at | ledger | false | eager | tx_liftable | = 提交时间,禁覆盖;回填走独立 `event_time` key |
| trace_id | audit | false | lazy | tx_liftable | **不与 tx_id 合并**(trace 跨 tx、tx 可无 trace —— codex 修正,采纳);可存为 tx 默认 |
| valid_from / valid_to | runtime | false | eager | claim | business-time 选择 |
| raw_kind / bound | runtime | false | eager | claim | 不确定性载体 |
| candidate_key / candidate_kind | **runtime** | false | eager | claim | candidate 解析读取(修正:非 T) |
| derived_rule_id / *_version | **runtime** | false | eager | claim | accept 去重依赖(修正:非 T) |
| note | **runtime** | false | eager | claim | duplicate-compat 检查读取(修正:非 T —— 直觉最意外的一项,已核实) |
| candidate_id | audit | false | lazy | claim | 暂 T,blueprint 复核 |
| source / origin_binding | audit→ | **声明后 true** | 随声明 | tx_liftable | premise 引用前必须声明 |
| approved_by | runtime | 声明后 true | eager | claim | 有运行时兼容检查,非纯 T |
| actor_* / tenant_id / request_id | audit | 默认 false | lazy | **tx_liftable** | 按 request 共享(meander context.py),批次提升;逐 key 声明升级 |
| version | audit | 声明后 true | lazy | claim | `query_indexed=true`;**可查询≠premise**(修正) |

### Q-SAE-9 §5 chosen 定序迁移

- [ ] `(-ingested_at, asrt_id)` → `(-seq)`。codex 修正成立:差异**不限于同刻写入**(锁前采样时钟、时钟回拨、导入乱序都可使时间序≠提交序)。定性为**语义变更**而非等价重构:gate 增加"较早采样时间、较晚提交"用例;迁移说明写入 CHANGELOG。

### Q-SAE-9 §6 后果与测量

- [ ] codex 修正成立:原"3.9KB→1KB"混算了 3b 与本 ADR 的收益。harness 改为**三组对照**:① 7 表现状;② 3 表无分层;③ 3 表+分层(tx 提升 + lazy)。按 meander 实际批次大小分布测(批次越小,tx 摊销越差 —— 与 §2 双粒度裁定联动)。

### Q-SAE-9 §7 验收 gates

1. [ ] premise filter 差分测试(最高优先):统一解析器(含 UNSET、tx 默认继承、revoker 对称)vs 现行单层 last-wins,逐字节等价 + absence 语义专项(absent_ok 全路径);
2. [ ] INV-15:tx 物化物(若含 `__system__.tx` claim)五读面不外泄;
3. [ ] chosen:语义变更用例集(时间倒挂、同刻、导入);
4. [ ] 三组对照 bytes/claim + 求值工作集(lazy 生效验证:audit 类不进投影);
5. [ ] `narrate()`/explain 无可观察回归。

### Q-SAE-9 §8 裁定

- codex 评审:`tx_ref` 取代区间、正交属性拆维、UNSET tombstone、逐 key 修正(candidate/derived/note 非 T)、chosen 语义变更定性、actor 非 S、trace_id 不合并、version 条件 J、S 禁覆盖 + `event_time` —— **全部采纳**;
- [ ] **裁定 1(用户 2026-07-31)**:双粒度事务采纳(批量面批次 commit / 交互面 per-call)—— **Q-SAE-1 就此一并裁定**,无需独立 ADR;
- [ ] 默认执行(未单独呈批,可推翻):`__system__.tx` claim v0.3 不物化进图,仅存 tx object;
- [ ] **裁定 3(用户 2026-07-31,经 meander 盘点)**:`premise_eligible` 初始声明集 = **`{provenance_class, origin_binding}`** —— meander 全部三个 premise 配置点(state.py MetaExclusion + PredicatePremiseAllowance、accreditation/effect.py PredicatePremiseBlock)仅引用此两 key(经 plan_semantics 常量,literal 已核实)。用户注:此集可调整,不做刚性承诺。

### Stage A archive §7.1 三条口径护栏(verbatim)

- Q-SAE-8 只落 tx_seq 地基 + op 保序(**事件化/(tx_seq,op_ordinal)/tombstone 归 3b**);
- Q-SAE-9 只兑现双粒度提交面 + tx object **介质裁定**(**"承载批次 meta"的能力、tx_ref 列、meta 正交属性、UNSET 全部归 3b**);
- Q-SAE-3 触发线附则**未落 Q-SAE-6,欠账在案**。

## Phase 0 current-context anchor checklist(`af7b92ab`)

- [x] **7 表 `_DDL`**:`src/factgraph/core/store/ledger.py:100-178`;表定义分别为 `claims:101-107`、`claim_args:109-115`、`meta_rows:117-123`、`revokes:125-129`、`ingest_keys:131-135`、`ledger_meta:137-140`、`annotation_rows:160-171`。
- [x] **内存索引 `_reset_indexes` 族**:`ledger.py:1025-1054`;claims `1026-1030`、claim_args `1032-1033`、meta `1035-1041`、annotations `1043-1047`、revokes `1049-1052`、ingest_keys `1054`;对应 meta/annotation clear helpers 在 `1056-1070`。
- [x] **单层 premise last-wins**:`src/factgraph/core/store/premise_filter.py:316-413`;global exclusion、predicate allowance、predicate block 分别在 `339`、`377`、`412` 读取 `rows[-1].value`;冷启动由 `ledger.py:1157-1162` 的 `meta_rows ORDER BY id` 恢复写入序。
- [x] **chosen 定序**:`src/factgraph/core/policy/chosen.py:11-23`;`22` 为 `(-ingested_at, asrt_id UTF-8 bytes)` 排序;`86-97` 要求恰有一条 `ingested_at` time/int meta。
- [x] **单事务 `commit_batch`**:`ledger.py:315-330` 的 `_write_session` 执行 `BEGIN IMMEDIATE`/`COMMIT`/异常 `ROLLBACK`;`332-472` 的 `commit_batch` 在同一 session 内完成 head CAS、assertion/revocation/meta rows 与 ledger metadata,仅在提交后更新内存索引。
- [x] **`tx_seq` 提交全序**:`src/factgraph/core/store/database.py:965-1039`;父 head 在 `965` 读取,`1032` 分配 `parent.tx_seq + 1`,并在 `1033-1039` 进入 dbtx_v2 canonical tx id;`ledger.py:414-425` CAS 封闭并发窗口。
- [x] **append_meta/schema_change op 保序地基**:`database.py:982-1030`;`_prepare_meta_appends:1276-1291` 按输入迭代并 append,protocol operations 按 assertions `986-997`、revocations `998-1010`、meta appends `1011-1018`、isolated schema transition `1022-1030` 构造;`_normalize_tx_operations:2128-2134` 不重排输入;`1105-1121` 按该列表写 tx object。此项只证明 Stage A 的 op-order/tx_seq 地基,不表示 event PK 或 `op_ordinal` 已落库。
- [x] **LtHash16-v2 state element**:`database.py:1959-1966` 明确为 domain prefix + `_str_field(asrt_id)` + `_str_field(assertion_digest)`;增删调用分别在 `987-1002`;3b 不得改变此 digest 语义。
- [x] **双粒度提交面**:`src/factgraph/application/entity_write.py:257-277` 的交互 `apply_write_plan` 以单 plan 委托;`307-365` 的 `apply_write_plans` 展平一批 plan,`378-461` 最终只在 `445` 调用一次 `database.commit_changes`;SDK batch 接线在 `src/factgraph/sdk/batch.py:591-605`;公开交互/批量入口在 `src/factgraph/sdk/store.py:2234-2261`。

结论:blueprint §4 的当前上下文描述均被当前 HEAD 代码证实,无偏差需停线。

## Deviations

(none yet)
