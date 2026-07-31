# Q-SAE-9 Decision: Meta 正交属性模型 + Tx 具象化(rev.2)

- Status: **adopted**(2026-07-31 用户批准 rev.2;裁定见 §8;premise_eligible 初始集经 meander 盘点确定、标注可调整)
- Created: 2026-07-31
- Branch: `v0.2.0-design-storage-hardening-2026-07-31`
- Inputs:
  - `workflow/design/design-points/active/storage-hardening-stage-a-slice-3b.zh.md` §4 Q-SAE-9 行
  - `docs/quickstart/data_model.md` §2.1(built-in meta keys)
  - 源码核实:`chosen.py`(`(-ingested_at, asrt_id)` 定序)、`premise_filter.py`(MetaExclusion.key 任意、`absent_ok` —— **缺失有语义**)、`accept.py`(`_resolve_candidate_key_to_entity_ref` 读 candidate_key;`_assert_duplicate_meta_compatible` 在 accept 时读 meta 兼容 —— codex 指出、已核实)
  - meander `auth/context.py`(actor context 按 request/action 共享 —— 批次提升的现实依据)
  - 实测:7 表 8 meta/claim ≈ 3.9KB/claim
  - codex 评审(2026-07-31):区间关联六项脆弱点、跨层 last-wins 反例(absence 语义)、分类维度混杂、chosen 语义变更范围 —— 关键修正,采纳
- Scope: meta 的 schema 属性模型;tx 具象化载体与关联;tombstone 事件;chosen 定序迁移;逐 key 归类表。
- Non-scope: ingest 蒸馏清单(产品决策)、premise SQL 下推(L2)、blob 存储选型。

## 1. 属性模型(rev.2 核心重构:正交属性取代四级枚举)

codex 评审正确指出原 S/J/F/T 单枚举混杂了互相独立的维度(premise 资格 / 运行时读者 / 装载策略 / 存储域 / 索引需求)。采纳,schema 声明改为**五个正交属性**:

| 属性 | 取值 | 决定什么 |
|---|---|---|
| `reader_class` | `ledger` / `runtime` / `audit` | 谁在运行时读它(`audit` = 无运行时读者) |
| `premise_eligible` | bool | 可否被 premise/可见性配置引用(**默认 false;引用未声明 key 即报错** —— 封闭漂移根源) |
| `load_policy` | `eager` / `lazy` | 是否进求值工作集 |
| `storage_scope` | `claim` / `tx_liftable` | 可否提升为 tx 默认(claim 级覆盖仍可用) |
| `query_indexed` | bool | 是否建查询索引(**可查询 ≠ premise 语义** —— 修正原 `version` 误归 J 的错误) |

原 S/J/F/T 保留为**文档层的常用组合速记**,不再是 schema 模型。

## 2. Tx 具象化(rev.2:显式 `tx_ref`,区间方案废弃)

codex 评审列出的区间方案六项脆弱点(重放/导入后物理 seq 不稳、meta-only 事务无 claim 区间、未来多写者交错、tx claim 自包含歧义、tx 内容含区间的循环定义、**Q-SAE-1 per-call 粒度下"1 业务 claim + 1 tx claim"近乎行数翻倍**)全部成立。采纳:

- **`claims` 与 meta event 行显式携带 `tx_ref`**(8 字节/行,相对 ~1KB/claim 可忽略;换来稳定审计、meta-only 事务支持、可迁移性);
- tx 级 S/共享 meta 落在 **tx object**(现有 `db/objects/tx/` 谱系,Stage A 裁定其介质)而非必然一条 tx claim —— 是否同时物化 `__system__.tx` claim 供图内查询,降级为 blueprint 实现选项;
- **与 Q-SAE-1 的强耦合(rev.2 新增)**:per-call 事务粒度会使 tx 元数据条数 ≈ 业务写入条数,批次摊销失效。因此 Q-SAE-1 的裁定必须与本 ADR 联动 —— ✎ 提案:**ingest/批量面走批次 commit(一批 span = 一个 tx),交互式单写维持 per-call** —— 双粒度,由 API 面区分。

## 3. 跨层解析(rev.2:引入 UNSET tombstone)

codex 构造的反例成立:premise 语义中"缺失"与"存在但值不同"不等价(`absent_ok` 显式存在),claim 层写普通值**无法删除**继承的 tx 默认。采纳:

- 引入显式 **`UNSET` tombstone meta event**(Q-SAE-8 的 event 形态之一,共用 `(tx_seq, op_ordinal)` 序);
- 统一解析器:effective(asrt, key) = 按事件序取组内最新事件;`UNSET` → 视同缺失;无 claim 级事件 → 取 tx 默认;
- 该解析器**对普通 claim 与 revoker 对称适用**(premise filter 的 revoker 对称可采性要求)。

## 4. 逐 key 归类表(rev.2:按 codex 逐键核实修正)

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

## 5. chosen 定序迁移(rev.2:承认为语义变更)

`(-ingested_at, asrt_id)` → `(-seq)`。codex 修正成立:差异**不限于同刻写入**(锁前采样时钟、时钟回拨、导入乱序都可使时间序≠提交序)。定性为**语义变更**而非等价重构:gate 增加"较早采样时间、较晚提交"用例;迁移说明写入 CHANGELOG。

## 6. 后果与测量(rev.2:三组对照)

codex 修正成立:原"3.9KB→1KB"混算了 3b 与本 ADR 的收益。harness 改为**三组对照**:① 7 表现状;② 3 表无分层;③ 3 表+分层(tx 提升 + lazy)。按 meander 实际批次大小分布测(批次越小,tx 摊销越差 —— 与 §2 双粒度裁定联动)。

## 7. 验收 gates

1. premise filter 差分测试(最高优先):统一解析器(含 UNSET、tx 默认继承、revoker 对称)vs 现行单层 last-wins,逐字节等价 + absence 语义专项(absent_ok 全路径);
2. INV-15:tx 物化物(若含 `__system__.tx` claim)五读面不外泄;
3. chosen:语义变更用例集(时间倒挂、同刻、导入);
4. 三组对照 bytes/claim + 求值工作集(lazy 生效验证:audit 类不进投影);
5. `narrate()`/explain 无可观察回归。

## 8. 评审整合记录 + 待用户拍板

- codex 评审:`tx_ref` 取代区间、正交属性拆维、UNSET tombstone、逐 key 修正(candidate/derived/note 非 T)、chosen 语义变更定性、actor 非 S、trace_id 不合并、version 条件 J、S 禁覆盖 + `event_time` —— **全部采纳**;
- **裁定 1(用户 2026-07-31)**:双粒度事务采纳(批量面批次 commit / 交互面 per-call)—— **Q-SAE-1 就此一并裁定**,无需独立 ADR;
- 默认执行(未单独呈批,可推翻):`__system__.tx` claim v0.3 不物化进图,仅存 tx object;
- **裁定 3(用户 2026-07-31,经 meander 盘点)**:`premise_eligible` 初始声明集 = **`{provenance_class, origin_binding}`** —— meander 全部三个 premise 配置点(state.py MetaExclusion + PredicatePremiseAllowance、accreditation/effect.py PredicatePremiseBlock)仅引用此两 key(经 plan_semantics 常量,literal 已核实)。用户注:此集可调整,不做刚性承诺。

## 9. 附注:与"物理双库"构想的关系(用户 2026-07-31 提出)

用户原始构想为两个数据库:活跃库(推理用)+ ledger 库(trace/身份,推理无关)。本 ADR 以**逻辑分离**实现同一意图:`load_policy=eager` 的数据(claims + runtime meta)= "活跃库",`load_policy=lazy` + tx object + blob 引用 = "ledger 库" —— 求值工作集只装前者。保持**单一物理事务域**的理由:① 一次 commit 同时落事实与 trace,跨库无法共享事务边界(Stage A 刚修好的原子性会被重新打破);② receipt 完整性横跨两类数据;③ SQLite 跨 attach 库的事务在 WAL 模式下无掉电原子性保证。**物理分离的门留着**:audit 类数据只经窄域 audit 接口访问(Q-SAE-8 裁定 2),该接口就是将来物理搬迁(归档库/独立库)的天然接缝 —— 届时是受控改动,不是重构。
