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
| 2026-08-01 | Phase 0 seven-table baseline(initial) | `benchmarks/slice3b_storage_baseline.py`;3,000 claims、8 projected Ledger meta rows/claim、3 claims/tx 的 current-layout 首轮基线;单样本 SQLite 口径随后被补钉轮 N=5 方法取代 |
| 2026-08-01 | **Phase 0 对抗审计:0 blocker / 8 serious / 7 minor —— 有条件不放行,先走补钉轮** | 四透镜(golden 完整性/转录保真/基线方法学/纪律锚点)+ 独立全套件复跑(2772/32/1 + 1097 subtests 逐字复现);裁定与发现全文见下文 §Phase 0 对抗审计 |
| 2026-08-01 | Phase 0 补钉 A/B/C | `6ef6579a` 增加 production commit-path + repair golden;`b6ff1a8a` 补 Q-SAE-8 §4 逐行转录、Q-SYS-B supersede 与 C1/C2 内联裁定落笔 |
| 2026-08-01 | Phase 0 production golden 混合序加固 | `c1a06555`;同一 production commit 字面钉死 assertion → revocation → append_meta 顺序,schema_change 依生产约束独立成环 |
| 2026-08-01 | Phase 0 baseline 补测 | `5d9e7463`;harness v2 改为 N=5 中位数+抖动带、tx-object 唯一字节精确分量、projected/persisted/workset 分名;补 batch=1 与冷 attach 驻留指标 |
| 2026-08-01 | Phase 0 补钉 canonical gate | `PYTHONPATH=src` + process-only readline shim + ignore pyreason binary failure + deselect static-ui known failure:`2773 passed / 32 skipped / 1 deselected / 1098 subtests`;相对进入补钉轮净增 1 test + 1 subtest |

## Phase 0 adopted commitments worklist(verbatim)

以下清单逐行转录 adopted ADR 的承诺与 gates;勾选表示实施 Phase 已完成,**不是**表示 Stage A 已有。

### Q-SAE-8 §1 Decision

- [ ] **claim_meta 事件化:每行是一个不可变 meta event,PK `(asrt_id, key, event_seq)`;last-wins = 组内 `max(event_seq)`。**
- [ ] 采用 **`(tx_seq, op_ordinal)` 二元组**:`tx_seq` = 提交序(Stage A 后一次 commit = 一个事务,天然全序);`op_ordinal` = 本次 commit 内按输入顺序的操作序号(覆盖"一次调用同 key 多次赋值"的次序);
- [ ] 全部读取入口(premise filter、AssertionMeta 投影、reload、导出)统一按此二元组字典序解析;
- [ ] reload/导出/迁移**保序不变量**:落库即定序,任何重建路径不得重排;
- [ ] 失败回滚:事务失败则该 `tx_seq` 下全部事件不存在(原子性由 Stage A 追加项 (a) 保证)—— 无部分序号泄漏。

### Q-SAE-8 §4 后果

- spec 修订面:claim_meta 表定义(+event_seq)、§9.7、INV 族("immutable"从表级降为行级);**Q-SYS-B §4.4 对应条款按本 ADR supersede 标注**;
- 与 Q-SAE-9 咬合:J 类 claim 覆盖行与 tombstone 事件(Q-SAE-9 定义)都是本 ADR 的 meta event,共用 `(tx_seq, op_ordinal)` 序;
- meta 历史入 `tx_id` 链、不入 `state_digest`(Q-SAE-7 §4 已裁)。

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

## Phase 0 measurement baseline:group 1(current seven-table)

### Frozen method

- Harness:`benchmarks/slice3b_storage_baseline.py`(`slice3b_storage_baseline_v2`,commit `5d9e7463`)。
- Invocations:
  - batch profile:`PYTHONPATH=src python benchmarks/slice3b_storage_baseline.py --claims 3000 --batch-sizes 3 --repeats 7 --storage-runs 5`;
  - interactive profile:`PYTHONPATH=src python benchmarks/slice3b_storage_baseline.py --claims 3000 --batch-sizes 1 --repeats 7 --storage-runs 5`。
- Environment:macOS 14.4.1 arm64;Python 3.10.11;SQLite 3.45.3。
- Batch profiles:meander read-only probe found one `plan.ingest` request_id group containing 3 claims,故主 profile 为 1,000 commits × 3 claims;另以 3,000 commits × 1 claim 固定 interactive 摊销基线。`--batch-sizes` 继续接受可复跑的逗号分隔分布。
- Meta input profile 固定为 5 entries/claim(`ingested_at`,`provenance_class`,`origin_binding`,`trace_id`,`request_id`);输出分三种口径,不做 8-row 硬断言:
  - **projected**:`Ledger.find_meta()` / `find_annotations()` 可见的 read projection;
  - **persisted physical**:SQLite `meta_rows` / `annotation_rows` / 后续 `claim_meta` 的实际行数;
  - **eager workset**:cold `Database.open` + attach 后驻留的 meta-bearing row objects 与 index references。
- Size method:每个 profile 独立创建 **5 组**同 schema 的 empty/filled Database;checkpoint WAL;exclude `-wal`/`-shm`/writer lock;逐组 subtract empty workspace 固定 schema/genesis 成本。SQLite allocation 与 durable total 报中位数、min/max 抖动带及相对中位数最大偏差;**只有 content-addressed tx-object delta 要求五组逐字节相等**,是唯一 byte-exact 分量。Phase 4 groups 2/3 必须复用此方法。
- Read method:第一组 filled workspace 关闭后 cold reopen/attach,再做 warm-up + GC 后 7-repeat median;3,000-claim premise scan 对每条 assertion 执行 global exclusion + predicate allowance + predicate block;chosen projects 300 groups × 10 versions;Ledger suite 覆盖公开 read method/property 的代表性 filter shapes(point methods use 256 ids),**不宣称穷尽每个参数组合**。
- Harness private dependency:`Database._ledger_for_attach` 用于取得 attach 后 Ledger;其转正时必须保留 alias,或在同一 commit 更新 harness。workset 还读取当前 `_meta_*` / `_anno_*` 内存索引;3b 重构这些索引时必须同 commit 更新计数 adapter,不得静默丢指标。

### Storage result

| Profile | Commits | SQLite median[min,max] | SQLite B/claim | dbtx_v2 exact | tx B/claim | Durable median[min,max] | Durable B/claim |
|---|---:|---:|---:|---:|---:|---:|---:|
| batch=3 | 1,000 | 10,612,736 [10,600,448, 10,653,696] B | 3,537.579 | 803,893 B | 267.964 | 11,416,629 [11,404,341, 11,457,589] B | 3,805.543 |
| batch=1 | 3,000 | 10,620,928 [10,555,392, 10,633,216] B | 3,540.309 | 1,429,893 B | 476.631 | 12,050,821 [11,985,285, 12,063,109] B | 4,016.940 |

SQLite 最大偏差(batch=3 / batch=1)分别为中位数的 0.385951% / 0.617046%;durable total 分别为 0.358775% / 0.543830%。两组各 5 次 tx-object delta 均逐字节一致。batch=1 相对 batch=3 每 claim 增加 208.667 B tx-object 摊销,这正是 Q-SAE-9 §6 要冻结的 interactive 成本。

Schema introspection returned exactly the current seven tables:`annotation_rows`,`claim_args`,`claims`,`ingest_keys`,`ledger_meta`,`meta_rows`,`revokes`。

### Meta projection / persistence / eager workset(cold attach)

两种 batch profile 的 claim/meta 内容相同,下列计数完全一致:

| Metric | Rows / references | Per claim | 语义 |
|---|---:|---:|---|
| projected Ledger meta rows | 24,000 | 8.0 | `find_meta()` 的稳定读投影;不是 physical 总行数 |
| projected annotation rows | 3,000 | 1.0 | `find_annotations()` 的兼容投影 |
| persisted `meta_rows` | 24,000 | 8.0 | SQLite physical |
| persisted `annotation_rows` | 3,000 | 1.0 | SQLite physical;与 meta projection 有共享数据的重复物化 |
| **persisted physical meta-bearing total** | **27,000** | **9.0** | 当前 7 表物理成本;不是 8 |
| **eager projection meta-bearing rows** | **27,000** | **9.0** | cold attach 后 `_meta_rows_data` + `_annotation_rows_data` 全驻留 |
| resident meta index references | 144,000 | 48.0 | row list + 六族 meta lookup 中的引用数 |
| resident annotation index references | 15,000 | 5.0 | row list + 四族 annotation lookup 中的引用数 |
| **resident meta index references total** | **159,000** | **53.0** | 引用计数,不是 distinct Python object 数 |

这组 workset 是 Q-SAE-9 §7.4 的 group 1 锚点:Phase 4 的 3-table+tiering 必须证明 audit/lazy 类不再进入 eager projection,并用同名字段呈现降幅。

### Read result(median)

| Profile | premise filter(3 × 3,000) | chosen(3,000;300 × 10) | Ledger representative read suite |
|---|---:|---:|---:|
| batch=3 | 7.937334 ms | 9.353000 ms | 1.297375 ms |
| batch=1 | 8.772667 ms | 9.259625 ms | 1.413084 ms |

Batch=3 Ledger read API case timings(ms):

| Case | Median | Case | Median |
|---|---:|---|---:|
| `get_claim_256` | 0.078625 | `find_claims_all` | 0.024500 |
| `find_claims_pred` | 0.024375 | `find_claims_e_ref` | 0.004333 |
| `find_claims_pred_e_ref` | 0.009375 | `find_claim_args_all` | 0.015750 |
| `find_claim_args_asrt` | 0.009792 | `find_claim_args_filtered` | 0.190875 |
| `find_meta_all` | 0.077292 | `find_meta_asrt` | 0.008750 |
| `find_meta_asrt_key` | 0.009000 | `find_meta_key_kind` | 0.350500 |
| `find_annotations_all` | 0.009708 | `find_annotations_asrt` | 0.005542 |
| `find_annotations_ns_category` | 0.005708 | `find_annotations_key` | 0.233666 |
| `has_active_revocation_256` | 0.066583 | `find_revoker_256` | 0.071042 |
| `claims_property` | 0.014083 | `claim_args_property` | 0.014208 |
| `meta_rows_property` | 0.070750 | `annotation_rows_property` | 0.016125 |
| `revokes_property` | 0.003833 | `get_ledger_meta` | 0.042792 |
| `get_ledger_meta_snapshot` | 0.064708 | | |

## Phase 0 对抗审计(2026-08-01,Claude 四透镜 + 独立复跑)

**实质合格项(亲手/透镜复现)**:golden 为入库字面量、非自我实现(4 项变异探针 —— canonical 字节翻转/输入漂移/head 序列漂移/tx_id 翻转 —— 全部红显,control 全绿);序列化器即生产函数(`_tx_id_for_v2` → commit_changes/repair 同源);锚点 9/9 与 blueprint §4 精确相符(含 audit 清单对"op_ordinal 未落"的正确对冲);全套件 2772/32/1 + 1097 subtests 独立逐字复现,跑后工作树零污染;基线算术全部自洽,tx-object 字节(803,893)逐字节复现;spec 修订无 Q-SAE-9 Phase 3 溢出;readline shim 零落盘;未 push、无遗留物、blueprint 本体未动。

**Serious ×8**(G=golden,T=转录,B=基线):

| # | 发现 | 归属 |
|---|---|---|
| G1 | golden 只钉序列化器契约,未走生产 commit 路径:op 组装序(assertions→revocations→meta→schema)、tx_seq 推导、MetaEntry 类型分支全部未钉 —— Phase 1/2 重构组装可漂字节而 golden 全绿 | 补钉轮 A1 |
| G2 | repair 族 3/7 op(`repair_add`/`repair_remove`/`repair`,均为真实入链 op,database.py:673-705)零 golden 覆盖;**缺口源头在 blueprint §5 与工作包,非 codex 偏差** | 补钉轮 A2 |
| G3 | head_state_digest / LtHash 状态累积完全不在 fixture 内 —— "head 推进"仅指 tx_id 序列;3b 重写的正是状态存储 | 补钉轮 A1 |
| T1 | worklist 自称 verbatim 却整节丢失 Q-SAE-8 §4 —— Q-SYS-B §4.4 supersede 标注承诺无任何载体且未执行(该 ADR 自 2026-05-29 未动)—— 历史同型失败复发 | 补钉轮 B1/B2 |
| T2 | UNSET=SQL NULL 是两 ADR 均未裁的存储编码决策,经 doc-only "转录" commit 走私入 spec(Q-SAE-8 明示 tombstone 形态 non-scope) | 裁定 C1 |
| T3 | spec:180 把 tx_seq 预裁为 meta event 的"稳定 tx reference",越过 Q-SAE-9 §2 留白 | 裁定 C2 |
| B1 | SQLite 字节不可复现(6 跑 5 值,±0.77%,根因 uuid4 asrt_id 的索引页分裂),audit 以三位小数冻结单样本且无方差声明;tx-object 字节是唯一字节精确分量 | 补钉轮 D1 |
| B2 | 硬编码 8-meta 断言(harness:61,353-358)与"同一可执行跑三组"自相矛盾 —— 第 3 组分级的设计目标恰是改变该剖面 | 补钉轮 D2 |

**Minor ×7**:混合 scope commit(1373c1c5 bench+audit);spec:894 "仅 2 个原语"历史行漏 ⚠️ 标注;spec:171 索引注释超出 (key,value) 索引在事件史下的实际能力;harness 依赖私有 `_ledger_for_attach`(本 blueprint 自己要转正的名字);batch=1 摊销无基线(诚实披露的 n=1 点估计);"all supported filter shapes" 超述(find_meta 两条索引路径未测);求值工作集指标缺失(Q-SAE-9 §7.4 gate 需要)。另记:canonical 套件跑法(readline stub + ignore + deselect)只存在于归档 audit prose,无 pytest 配置载体,有漂移风险。

**裁定:有条件不放行 Phase 1。** 关键时序约束:D 组基线补测(中位数重基线/batch=1/工作集指标)必须在动表**之前**完成 —— 翻转落地后补 7 表基线需回老 checkout,成本陡增。补钉轮(A/B/D + C 裁定落笔)完成并复验后放行 Phase 1。

## Phase 0 补钉轮实施闭环(待对抗复验)

| 审计项 | 闭环证据 |
|---|---|
| G1 + G3 | `6ef6579a` + `c1a06555`:确定 UUID 序列下走 `Database.create` + production `commit_changes`;同批钉死 assertion → revocation(`MetaEntry` meta)→ append_meta,schema_change 独立成环;逐环比较持久化 tx-object bytes、tx_id、head_tx_id/head_tx_seq/head_state_digest 字面 fixture |
| G2 | `6ef6579a`:`repair_add` / `repair_remove` / `repair` 三 tag canonical bytes + tx_id + head progression fixture |
| A3 minor | B 链新增 observed kind 上界断言,与 A 链对称;repair 链也有同构上下界 |
| T1 | `b6ff1a8a`:Q-SAE-8 §4 三行逐字补入 worklist;Q-SYS-B §4.4 加 Q-SAE-8 supersede 标注 |
| T2 / C1 | `b6ff1a8a`:保留 UNSET=SQL NULL,明确记为 2026-08-01 内联裁定编码 |
| T3 / C2 | `b6ff1a8a`:`tx_seq` 仅定为 Q-SAE-8 提交序;与 Q-SAE-9 `tx_ref` 关系留 Phase 1 裁定 |
| B1 / D1 | `5d9e7463`:SQLite/durable 改 N=5 中位数+抖动带;tx-object 是唯一 byte-exact 分量 |
| B2 / D2 | `5d9e7463`:删除 8-row 硬断言;projected Ledger rows、persisted physical rows、eager workset 分名报告 |
| D3 | batch=1 的 3,000-commit interactive 摊销基线已在 7 表翻转前落数 |
| D4 | cold attach 后 eager projection rows、resident row objects、meta/annotation index references 已入 group 1 基线 |
| D5 | Frozen method 明记 `_ledger_for_attach` private dependency 与 alias/update 约束;同时记录 workset 所依赖的 `_meta_*` / `_anno_*` adapter 更新纪律 |
| B3/B4 minor | spec 历史“仅 2 个原语”行加 ⚠️;`idx_claim_meta_key_value` 注释收窄为候选过滤,组内 max 才决定 effective |
| 额外 minor | read suite 措辞从“all supported filter shapes”收窄为代表性 shapes,不再过诺 |

补钉期间未修改 `src/`、DDL 或生产写路径;readline shim 仅在测试进程内注入,无文件落盘。Phase 1 仍须协调方复验放行。

## Deviations

(none yet)
