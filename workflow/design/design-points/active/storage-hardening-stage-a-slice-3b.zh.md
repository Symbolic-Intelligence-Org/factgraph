# Design-Point: Storage Hardening — Stage A(Lifecycle 收敛)+ Slice 3b(7→3 表)实施收敛

- Status: draft
- Created: 2026-07-31
- Last Updated: 2026-07-31
- Authority: candidate design / non-authoritative reference. **Not current behavior.** 仅当被 adopted decision、implemented blueprint、module docs 或 `workflow/foundations/architecture_principles.md` 引用时才构成约束。
- Inputs:
  - [`factgraph-storage-architecture-evolution.zh.md`](factgraph-storage-architecture-evolution.zh.md)(母文档 1:四阶段路线 + §7 五步联合 update plan;本文档只消费其 Stage A,不重写)
  - [`ledger-schema-specification.zh.md`](ledger-schema-specification.zh.md)(母文档 2:claim-first 3 表终态 spec v2,已被 5 个 adopted ADR 锁定;本文档只消费其 §9 七步精简 = Slice 3b,不重写)
  - 2026-07-31 对 factgraph main `b92d6bf5`(含 PR #15–#22)的六读者调研 + 逐点人工复核(§2 全部差量的出处)
  - 2026-07-31 对 meander `origin/feat/mvp-overhaul` 的 factgraph 使用形态审计(§2.4 / §6)
- Outputs / Downstream:
  - decisions(2026-07-31 已出草案,proposed for user review):
    - [`2026-07-31_q-sae-6-release-target-decision.md`](../../decisions/active/2026-07-31_q-sae-6-release-target-decision.md)
    - [`2026-07-31_q-sae-7-data-digest-contract-decision.md`](../../decisions/active/2026-07-31_q-sae-7-data-digest-contract-decision.md)
    - [`2026-07-31_q-sae-8-claim-meta-history-decision.md`](../../decisions/active/2026-07-31_q-sae-8-claim-meta-history-decision.md)
    - [`2026-07-31_q-sae-9-meta-tiering-tx-reification-decision.md`](../../decisions/active/2026-07-31_q-sae-9-meta-tiering-tx-reification-decision.md)
  - (拟)decisions:Q-SAE-1 / Q-SAE-2(§4,随 Stage A blueprint 一并裁)
  - (拟)blueprints:`stage-a-lifecycle-convergence`、`slice-3b-ledger-migration`(§5;命名承母文档 1 §5.4 预定)
- Related:
  - `identity-mechanism-redesign.zh.md`(INV-7a/b/c 在迁移中必须保持)
  - `append-only-ledger-evaluation.zh.md`(背景评估,不驱动本文档)

## §1 目的与范围

### 1.1 目的

把两份母文档中已设计完毕但零消费的前两步(Stage A + Slice 3b)收敛成**一个可在约一个月内交付的实施战役**,并针对 2026-06-02 设计基线与当前 main(`b92d6bf5`)之间的漂移做逐点重校。母文档的设计结论不在此重写 —— 本文档只做三件事:差量重校(§2)、裁定队列(§4)、实施切分(§5)。

### 1.2 范围内

1. **Stage A — Lifecycle 收敛**:所有写路径统一经 `Database.commit_changes`/tx 链;SDK lifecycle(`create`/`load_workspace`)内部改为 `Database.create/open + attach`;拆除全部 `_reject_attached_write`;`save_workspace` 退化为 metadata 更新;v0.2 workspace 一次性迁移通道。**对抗审查(§3.4)追加的四项硬内容**:(a) 一次 `commit_changes` = 一个 SQLite 事务(现状:N 个独立事务 + 2 次文件写,崩溃产生孤儿 claims,database.py:419-458)、head 移入 `ledger_meta` 共享事务边界;(b) workspace 打开持 OS 排他锁(flock),把未声明的单进程假设变成显式失败;(c) commit 前 head CAS 校验(现状 last-writer-wins 覆盖写,database.py:832-835);(d) **`DBDATA_V1` digest 合同更换**(见 §4 Q-SAE-7)—— 与 schema flip 同属 alpha 免费窗口,错过同价。
2. **Slice 3b — 7 表 → 3 表**:按 spec §9 七步精简执行 atomic schema flip(`claims` + `claim_meta` + `ledger_meta`),drop `claim_args`/`meta_rows`/`annotation_rows`/`revokes`/`ingest_keys`,revokes 改 `__system__.revokes` Claim,ledger 层放弃 idempotency(上移 SDK)。
3. 两者之间的硬顺序:**Stage A 先、Slice 3b 后**(母文档 1 §7.1:否则 `entities.create/delete` 完整性漏洞被原样搬进新 ledger)。

### 1.3 非目标(显式排除)

- **Stage B / Stage C**(SQL 读路径 / lazy materialize):不进本战役。本文档只为其定义**可测触发线**(§4 Q-SAE-3 处置),到线后另开 design→decision→blueprint 链路。
- **eval 层性能修复**(PR #22 follow-up:`_selected_program_view_facts` 无条件重算、三遍 support walk):独立小 blueprint,与存储战役并行,不入本 scope。
- Identity 机制重设计、GDPR escape hatch、bitemporal 扩展(`append-only-ledger-evaluation` G2 等):不动。
- SDK 公开 API 面扩张:遵守 narrow-public-api 原则,本战役不新增公开 API,只收敛内部 lifecycle。

## §2 基线差量重校(2026-06-02 设计基线 → 2026-07-31 main `b92d6bf5`)

> 母文档的 file:line 引用全部基于 2026-06-02 的树。以下为逐点复核后的差量;**实施 blueprint 起草时必须以本节为准,不得直接照抄母文档行号。**

### 2.1 `_reject_attached_write` 调用点:11 → 14

母文档 1 §2 清单为 11 处。当前 main 为 **14 处**(store.py:406/426/440/610/683/873/886/1340/2162/2174/2189/2219/2583,另 :1734 为定义)。新增者含 `fg.assertions.append_meta`(:683)等。Stage A "拆除全部 reject" 的工作清单以 14 处为准,blueprint 起草时需再次 grep 确认。

### 2.2 完整性漏洞仍在(已复核)

`fg.entities.create`(store.py:1101)与 `fg.entities.delete`(store.py:1202)**仍不在** reject 清单,attach 模式下绕过 `Database.commit_assertions`:落库但 `db/refs/head.txt` 不推进、tx 链无对应对象、`db.head()` 与 ledger 内容不一致。此为 Stage A 最高优先修复项,且是 Slice 3b 的阻塞前提。

### 2.3 新增的存储层消费方:PR #15–#22(母文档基线之后落地)

2026-06-25 之后 main 合入了 `evaluate_candidates(rule_expr)`(#15)、actor_meta(#16)、premise admissibility filter(#20)、`premise_scoped_view`(#21)、program evidence(#22)。其中对本战役有直接约束的:

- **#22 `rule_program_runtime.py` 直接触碰 store 内部**:`sdk.store._remember_support_artifact`、`sdk.store.explain_support`(每次求值 9 调用 / 3 distinct digest)、`_support_artifacts`。Slice 3b 改表时**不动 support artifact 存储**(它在 sidecar/内存,不在 7 表内),但 Stage A 改 lifecycle 时必须保证 attach 路径下这些内部件可用(现状:attach 运行时 sidecar kwargs 被拒 —— 该不对称在 Stage A 一并拆除)。
- **#20/#21 premise 过滤走 `premise_scoped_ledger`**:读路径包装器,依赖 Ledger 内存索引形状。Slice 3b 若改动内存索引结构(见 §3.2),此两处是回归测试重点。

### 2.4 meander 使用形态(母文档未覆盖,本文档新增的设计输入)

对 `origin/feat/mvp-overhaul` 审计:

- meander **只用** `FactGraph.create(path=)` / `load_workspace`,attach 零使用;
- `fg.save_workspace()` 共 **28 个调用点**(governance/graph/plans/auth/web 全模块),基本每写必快照 —— 每次为 O(整库) 的 sqlite3 backup;
- meander 自身代码注释记录的伤口:`load_workspace` 不接受 `artifact_store_root`(meander `graph/workspace.py:57-58`),重载的 workspace 配不了 sidecar。

**推论**:Stage A 完成(写穿即持久、`save_workspace` 退化为 no-op 级 metadata 更新)后,meander 侧 28 处调用自动变廉价、且可在其后续版本中整批删除;sidecar 参数不对称随 lifecycle 收敛自然消失。此为本战役对 meander 业务开发的直接收益,见 §6。

### 2.5 时机窗口(本战役"现在做"的决定性论据)

spec §9 的 atomic schema flip(drop 7 表 + create 3 表 + 代码重写,**无数据搬迁**)依赖 alpha 状态 —— 无值得保全的持久业务数据。meander 业务开发启动 = 数据开始积累 = 窗口开始关闭。Slice 3b 的实施成本在窗口内是"schema flip",窗口外是"数据迁移工程"。

### 2.6 推理/查询服务的数据触点图(本战役为何对其低风险 + 两个真实耦合)

> 本节回应的问题:本战役不能被单纯看作"数据库对接改动"—— 推理与查询服务全部坐在数据层之上。

**绝缘契约(核心安全属性)**:推理/查询在运行时**从不读 SQL** —— 引擎取数走 `project_view_facts_with_witness`(逐 schema predicate 从 **Ledger 内存索引** 物化,projector.py:132-157),查询走 `find_*` 内存索引,premise 过滤走 `premise_scoped_ledger` 内存包装。SQL 只在冷启动被读一次。因此 7→3 表翻转的**唯一**必须保持的契约是:**Ledger 读 API(`find_claims`/`find_meta`/`claims` 流等)对同一逻辑写入序列的输出逐字节等价**。表怎么变,这层不变,推理/查询就不变。当前"全量驻内存"模式(本战役显式不动)恰好构成这道绝缘层。

**但有两个真实耦合,不可当作纯存储改动**:

1. **Revokes-as-Claim 的读面可见性(INV-11 × INV-15)**:撤销改为 `__system__.revokes` Claim 后,system claim 进入 claims 流。spec 已预设 INV-15(普通 SDK 读取表面默认 filter `__system__.*`,spec :153)+ INV-10(user 写入路径拒绝,spec §4.7),但**每一个读面都必须实际实施该 filter**,漏掉任何一个,推理引擎就会把撤销记录当作事实吃进去。必须逐面枚举验收(§7 gate 7):view projection、`premise_scoped_ledger`(#20/#21)、`find_*`、assertion views、program evidence witness 采集(#22)。
2. **ingest_keys 撤表 = 幂等语义搬家**:ledger 层放弃 idempotency 后,重试/去重语义上移 SDK/API 层。meander 的 ingest 面(`plans/ingest.py`、`bulk_ingest.py`)依赖重复抑制 —— 新层的幂等行为必须与旧 ingest_keys 语义等价(§7 gate 8)。

## §3 目标态(引用母文档,只列落点)

### 3.1 Stage A 终态(承母文档 1 §3.1)

- `Database.commit_changes(assertions, revocations)` 统一写入口(含 `RevocationInput` DTO);
- `planned_ops_to_inputs` 翻译器;`apply_write_plan` 改为 plan → 翻译 → `db.commit_changes`;
- `FactGraph.create/load_workspace` 内部 = `Database.create/open + attach`;attach 成为 SDK lifecycle 的 **superset**(反转现状的 ergonomic-poor subset);
- 14 处 reject 全拆;`entities.create/delete` 纳入统一写链;
- `save_workspace` 退化为 metadata 时间戳更新;workspace 双格式收敛为 Database 格式,一次性 migration 通道(§4 Q-SAE-2);
- docstring/quickstart 措辞按母文档 1 §5.5 诚实化。

### 3.2 Slice 3b 终态(承母文档 2 §2/§9)

- 3 表:`claims(seq, asrt_id, pred_id, e_ref, value, value_tag)` + `claim_meta(asrt_id, key, value)` + `ledger_meta(key, value)`;
- 三组内建冗余消失:`rest_terms`↔`claim_args`、白名单 meta↔`annotation_rows`、ingest_key↔`ingest_keys`;
- revokes 改 `__system__.revokes` 特殊 Claim(ADR-SYS-B 已采纳);
- ledger 层放弃 idempotency,幂等上移 SDK/API 层;
- 12 条结构不变量(INV-1/2/3/5 长期承诺族)+ INV-7c 全程保持;
- 内存索引(`ledger.py` `_reset_indexes` 十余个 dict)**随表形态同步重构但不改变"全量驻内存"模式** —— 驻内存模式的改变属 Stage B,非本战役;
- **Ledger 读 API 等价性是 Slice 3b 的最高契约**(§2.6 绝缘契约):同一逻辑写入序列 → `find_*`/`claims` 流输出逐字节等价(system claims 经 INV-15 filter 后)。

### 3.3 数据规模前瞻约束(大数据量的"提前考虑"落点)

> 本战役不解决大数据量驻内存问题(那是 Stage B/C),但必须**为它设计**,并**测量它**。

**前置框架:推理必然 load,架构变量是"工作集 = f(什么)"。** Bottom-up Datalog 求值要求 EDB 对引擎可用,四引擎无一例外(native = Python dict;souffle = 物化 `.facts` 文件 → 子进程,adapters/souffle/package.py:203;problog = program 导出;pyreason = 图结构)。**没有任何 Stage 消除"load 才能推理"** —— 各 Stage 改变的只是工作集的定义域:

| 层 | 工作集 | 归属 |
|---|---|---|
| L0(现状) | 整个 ledger 常驻内存 + 每次 eval 对**全 schema predicates** 物化(projector 逐 pred 全量) | 本战役不动 |
| L1 | 规则体静态分析 → 只 load 被引用 predicates 的事实,瞬时驻留、用毕丢弃(`bulk_load_claims(pred_ids)`) | Stage C(母文档 1 §3.3) |
| L2 | goal 绑定下推 → 只 load 与本次求值目标相关的事实切片(e_ref/premise-scoped SQL pushdown,magic-sets 家族) | **母文档未覆盖 —— 已知设计缺口** |

关键推论:对 meander 的 per-plan 求值形态,L1 的天花板仍是"被引用谓词的全量事实" —— 世界图无界增长时 L1 同样触墙;只有 L2 让工作集正比于 **case** 而非 **ledger**。L2 需要独立 design-point(Stage C 之后或与其合并设计),本战役只登记缺口、不展开。另一条绕墙路径是应用层分片(世界图 = 多张有界 case 图而非一张无界大图),归属 meander 侧数据形态决策(§8 量级评估 item)。

**引擎侧调研结论(2026-07-31,三引擎并行调研,详见 session 记录)**:souffle/problog/pyreason 均**无 evaluation 级数据库内推理** —— souffle `IO=sqlite` 与 problog `library(db)` 都是 IO 级(装载边界取数,求值仍在引擎进程内存);pyreason 连 IO 级都没有(论文宣称的 Neo4j 直连三年未落地,已核实为零代码)。引擎侧 goal-directed 对我们的规则形态也不可用:souffle magic-set 明文跳过含否定的依赖链,而我们 view 层根部即含 `!revokes` 型否定。**因此 L2 的归属裁定为:factgraph 自己的检索层(Ledger/投影层的 goal/e_ref/premise SQL 下推),引擎无关** —— 引擎经现有 adapter 接口收到"已裁小的 EDB"即可,R1(witness 回读)/R3(premise 语义单实现)/R4(digest 载体)契约全部不动。两个佐证:souffle 的 `<rel>` view 可挂任意 SELECT,证明引擎不关心 EDB 从哪来;problog 的 goal-directed grounding + 绑定键下推(`SELECT ... WHERE key=?`)证明按需检索形状真实可行 —— **借鉴其模式,不复用其实现**(problog db 库为无测试 demo 级代码)。souffle `IO=sqlite` 保留为将来可选的序列化优化项(与 `-t explain` 的组合未经验证,低优先)。

**产业对照(2026-07-31 调研,RDFox/Stardog/Ontop/GraphDB/VLog + SQL 递归谱系)**:"先 load 进内存再推理"在产业界**不是**统一答案,而是四条路线,恰好逐一映射到本文档的框架上:① **全内存物化**(RDFox:官方定性 main-memory store、持久化不扩容、45–85 B/fact 紧凑编码、4TB 机器吃 92 亿 triples;souffle 同阵营)= 我们的 L0,其可活的前提是 RDFox 式**双向增量维护**(B/F→FBF 算法,删 5000 triples 增量维护 0.42–0.6s)—— 即 L0 路线的解药正是 R8;② **磁盘存储 + 查询时改写**(Stardog:RocksDB 盘存、不物化推理、仅 schema 驻内存、中间结果 off-heap + 磁盘 spill,10 亿 triples 只需 64GB RAM;Ontop 更极端:零装载,SPARQL+本体编译成 SQL 下推源库,代价是表达力锁死 OWL 2 QL 无递归)= 我们的 L2 的工业验证;③ **写时物化落盘**(GraphDB:装载时前向链、闭包写盘上索引,75 亿语句 86GB RAM/720GB 磁盘,删除靠 smooth delete)= factgraph 的 accept-物化车道同族;④ **VLog(on-disk EDB + in-memory IDB,列式 ∆-table,以 RDFox 6%–46% 的内存物化其同机 OOM 的数据集)= 本文档 Stage B/C + L2 的最接近已发表蓝本**。共同不变式:所有物化系统的**派生事实(IDB)必须驻 RAM**,无一支持推理期溢写;所有商业系统共享"schema 常驻、实例数据不要求全量驻留"。SQL 递归 CTE 谱系祛魅:三大引擎(SQLite/PG/DuckDB)仅覆盖正线性递归,无相互递归、无分层否定工效、无证明树,且**递归状态本身无 out-of-core 承诺**(DuckDB 424 节点图 union table 膨胀 6 亿行 OOM);无可采购的成熟 Datalog-in-SQL 引擎(LogicBlox 已 legacy)。souffle 架构参照一则:其 provenance 以求值期最小高度注记(1.31× 开销)+ 查询时 top-down 惰性重建 witness —— 与我们 PR#22 的 eager 冻结语义是不同需求下的相反取舍,留作 explain 性能优化参照。

**统一数据库的裁定**:三引擎的数据模型互不兼容(souffle = 扁平关系元组;problog = 带概率注解的 Prolog 项;pyreason = 带区间注解的属性图),不存在"一个引擎可原生共读的数据库 schema" —— 强行统一即最小公分母,直接破坏 R1/R3/R4。**统一点 = ledger 本身(3b 后的 3 表)+ 求值时的逐引擎投影层**(即现行 adapter 形态);L2 落地后各投影吃的是"已裁小的同一份账本切片"。PyReason 输入面已对安装版 3.0.0 逐 API 核实:仅 `load_graphml` / `load_graph(nx.DiGraph)` / `load_inconsistent_predicate_list` / `add_rule(s)` / `add_fact` 五通道;**无 DataFrame 载入**(pandas 仅出现在输出侧 `get_rule_trace` 与内部绘图死代码)、**零 Neo4j 代码** —— "支持 DataFrame/Neo4j 载入"的说法不成立,Neo4j 路径实为用户自行导出 GraphML 的 ETL。

三条硬约束:

1. **3b 的 DDL 必须面向 Stage B 的查询设计索引**。schema flip 现在免费、以后昂贵 —— 所以新 3 表的索引不按"紧凑落盘"设计,按母文档 1 §3.2 的 Tier 1/2 查询清单设计(Tier 1:exists / get-by-id / `fields.get` / `assertions.by_id`;Tier 2:`entities.where` / `assertions.where` / snapshot lazy field)。spec 已含 `idx_claims_pred_id` 与 `__system__.revokes` partial index(spec :125);blueprint 起草时逐条映射 Tier 1/2 → 索引,缺一不可。这是"大量数据提前考虑"最实质的一步:**让未来的 SQL 读路径不需要再改表**。
2. **合成规模基准 harness(本战役新增交付物)**:构造 100K / 1M claims 合成 ledger,测四条曲线 —— 冷启动加载时长、进程 RSS、单次 eval 的 view projection 耗时、单笔写事务耗时 —— 在 Slice 3b **前后各测一次**。三个用途:(a) 3b 的 neutral-or-better 验收门(§7 gate 9);(b) 直接产出 Stage B 触发线的真实数字(Q-SAE-3 处置需要的数据);(c) 把"忐忑"换成曲线 —— 墙在哪里、离墙多远,量化可见。
3. **预期收益与预期不变,分开说清**:
   - 3b 在规模上**主动改善**的:冷启动行数下降(`claim_args` 逐参数行展开塌回 claims、annotation/meta 双写消失、ingest_keys 撤表)→ 加载更快、内存重复更少;
   - 3b **不改变**的:全量驻内存本身、eval 每次对全 schema predicates 的物化(projector 逐 pred 全量)—— 这两堵墙只有 Stage B/C 能移。**若 meander 近期预期数据量级触墙,应凭 harness 数字把 Stage B 提前为独立战役,而不是把它偷渡进本战役。**

### 3.4 目标架构对抗审查结论(2026-07-31,三透镜:规模 I/O / 语义 / 产品负载;三者均判 survives-with-caveats)

目标架构命题("盘上账本 + 按需切片 + 瞬时工作集 + 增量失效")**方向存活,强形式被逐条拒斥**。要点:

**存活的**:① Slice 3b + alpha 窗口(三透镜一致;且 3 表对 L2 下推友好 —— INV-9 unary 后对象位落 value 列,spec 已含相应索引);② SQLite 作底座(实测全部墙都在我们的 Python 合同里:SQLite 单笔写 0.06ms、1M 行 175MB、热切片 1.78ms);③ 绝缘契约与瞬时引擎车道(单进程形态下真实有效);④ T4 选对了热循环(reevaluate 确为 O(plans×batches) 实测热点,且定向重估所需的 proof 足迹数据已在 meander evaluation_store 里)。

**被击穿、必须改写的**:
1. **写墙在 `DBDATA_V1`,不在 SQLite**(FATAL→Q-SAE-7):"写维度独立扩展"在现行合同下不成立。
2. **多进程一致性为零**(FATAL→§1.2 Stage A 追加 b/c):进程私有索引无失效、head 无 CAS;web 多 worker = 静默旧读/分叉 head。多 worker 服务形态必须显式裁定(进程亲和路由 vs 单写者常驻),不得留白。
3. **切片 × 闭世界否定/聚合不健全**(FATAL):切空 ≠ 真空,遗漏的 defeater 使 `not` 静默成立、聚合算错(反例:`sole_owner(X) :- owns(X,A), not owns(Y,A)`,join 变量是 value 非 e_ref)。**健全片段可精确刻画**:positive body + e_ref 共位否定(spec 把 revoke 的 e_ref 钉为被撤 claim 的 e_ref,恰使 `!revokes` 守卫 e_ref-bounded)+ 无聚合。L2 design-point 必须以"谓词可切性分类"开篇;此前禁用"working set ∝ case"作为已论证性质,诚实措辞 = "∝ case 的可切部分 + 否定/聚合谓词全量"。
4. **T6 在 meander 现实中无 case 边界**(FATAL):meander 是单一 domain workspace,plans 绑定共享实体、trace 重估有意不带 source 过滤、learning 读全世界。T6 降格为"未来产品决策的可能性",不得作为架构承重;case 分片需要先发明 case 生命周期 + 共享实体归属规则。
5. **T4 需按触发面分治**(SERIOUS):trace 面 head-skip 已存在(no-op);accreditation/policy 面**不写 ledger**(premise block 是内存过滤),head-based skip 会错误跳过 —— skip 键必须是跨三 store 的复合版本向量 `(head_tx_id, premise_scope_digest, rule_set_digest)`;撤销 delta 必须按被撤 asrt_id 解引用(`__system__.revokes` 与任何 plan 谓词交集为空,naive 交集 = 永不因撤回重估);向被 not 谓词**添加**事实必须失效。
6. **T5 对主导读负载空转**(SERIOUS):meander 产品语义明确禁止 plan 评估消费全局物化结论(policy-scoping 正确性,evaluate.py:13-15);且 accept-lane 无失效支付者(无 TMS,撤前提后陈旧结论双向污染)。收益声明限定 display/audit 读面;评估路径要受益需 policy-scope-aware 物化(新设计)。
7. **R4 digest 拆双轨**(SERIOUS):world-anchor(head_tx_id 链,O(1) 可比)+ slice-digest(goal 相对,标注切片规格);gate 7 的 digest oracle 仅 L0 模式有效。
8. **Postgres 可移植性只覆盖 3 表 schema**(SERIOUS):提交协议全是 POSIX 文件公民(tx object 文件、head.txt rename、sidecar、整目录拷贝语义)。措辞降级,或 Stage A 即把 tx/head/schema-object 抽象为"可入表"的键值。
9. **产品主导增长轴在 T1–T6 疆域之外**(SERIOUS):meander 的 plan evaluation history(O(plans×batches) 追加完整 proof JSON,存 meander app DB)与 sandbox 整目录拷贝预览 —— 归 meander 侧治理,§8 量级评估必须单列。
10. 高频小求值实际只有 in-process native 一条车道(souffle spawn 53ms / problog 248ms 实测):native 为高频重估默认车道**明文写死**,souffle/problog 定位批处理车道(一次 spawn 摊销多 plan)。

## §4 裁定队列(Q-SAE 六问的本战役处置)✎ 待逐项确认

> 每项裁定确认后落为 `workflow/design/decisions/active/` 独立 ADR,再开 blueprint。以下为**提案**,非结论。

| Q | 问题 | 本战役处置提案 | 去向 |
|---|---|---|---|
| Q-SAE-1 | tx 颗粒度(per-call vs session-boundary) | **per-call**:与现状逐笔 `BEGIN IMMEDIATE` 写穿语义对齐,不引入新的可见性问题;session-boundary 推迟到 Stage B 与 lazy 读一起议 | ADR,Stage A 前置 |
| Q-SAE-2 | v0.2 workspace 迁移(auto vs CLI) | **CLI**(opt-in `migrate-workspace`,沿既有先例);auto-migration 在 alpha 无必要 | ADR,Stage A 内 |
| Q-SAE-3 | eager/lazy 切换阈值 | **本战役不裁**。改为定义 Stage B 触发线:ledger claims 行数 / 冷启动加载时长 / 进程 RSS 三指标,阈值待与 meander 实测数据一起定 | 记录进 ADR-Q-SAE-6 附则,不单开 |
| Q-SAE-4 | native engine fact-source 抽象 spike | **推迟**(Stage C 前置,与本战役无关) | 不裁 |
| Q-SAE-5 | durable view × lazy 交互 | **推迟**(同上) | 不裁 |
| Q-SAE-6 | release 落点(v0.2.x vs v0.3) | **v0.3.0 提案**:Stage A 改 lifecycle 语义 + Slice 3b 换表是双重 breaking,不宜落 patch line;v0.2.x 保持冻结 | ADR,战役第一个裁定 |
| **Q-SAE-7(新,对抗审查产出)** | `DBDATA_V1` data_digest 合同:全量 active 集排序哈希使**每笔写 O(ledger)**(实测 ~58ms@100K / ~700ms@1M claims,SQLite 本身仅 0.06ms —— 写墙在我们的 Python 合同,不在 SQLite),且 `tx_id` 把该 digest 烧进哈希链,以后再改 = 协议断裂 | **换成可增量维护的承诺**(Merkle/累加式,或 head 链只承诺 delta),与 Slice 3b 同窗执行;tx 协议预留 digest-scheme 版本位 | ADR,**与 Q-SAE-6 同为战役首批裁定** |
| **Q-SAE-8(新)** | `append_meta` 同键多行历史(premise 重分类的语义基座,premise_filter last-wins)与 3 表 spec 的 `claim_meta(asrt_id,key)` 复合 PK + immutable 直接相撞 —— 含重复键 append 的写入序列在 3 表上**无法重放** | 二选一:`claim_meta` 加 seq 列弃复合 PK 保历史;或废除 append_meta 面(breaking,入 v0.3 清单)并把重分类改走 revoke+新 claim | ADR,Slice 3b 前置 |
| **Q-SAE-9(新,2026-07-31 账本轻量化讨论产出)** | meta 分级 + tx 具象化(Datomic reified-tx 移植)。**分类判据 = 读者契约,非 key 气质**(2026-07-31 与用户共同裁定):**S 结构**(读者=账本机器:seq/tx 指针/ingested_at/trace_id → 每批次一条 `__system__.tx` claim,复用 INV-10 命名空间;**chosen 定序由 ingested_at 改 seq**,已核实 chosen.py 现按 ingested_at 选胜者 —— 它今天是功能性的,改 seq 后才真正退役为描述性)、**J 辖域**(读者=premise/可见性配置:source/approved_by/version/origin_binding → 批次默认 + claim 覆盖,last-wins 跨层;**premise 配置只准引用 schema 已声明为 J 的 key,未声明即报错** —— 已核实 MetaExclusion.key 现为任意字符串,任何 key 可被一行配置激活为可采性判据,此为分类漂移的根源,必须封闭)、**F 语义**(读者=固定运行时机制:valid_from/to、raw_kind+bound → claim 级)、**T 纯迹**(无运行时读者:note/candidate_*/derived_* → claim 级,**惰性装载,不进求值工作集** —— 直接服务 L2 工作集缩减;derived_* 若 recheck/dedup 有依赖则逐 key 升 F,blueprint 时核)。分级写进 schema 声明、入 digest 锁。实测 8 行 meta/claim ≈ 3.9KB/claim,分层后 ≈ 1KB(~4×);配合 ingest 蒸馏("蒸馏非令牌化":规则引用的标量留真值,bulk 负载哈希引用)总增长降一个数量级。**与 Q-SAE-7/8 同窗强制**:claim_meta 形态必须在 3b 落地前定,否则两次迁移 | 与 3b 同窗裁定;J 类跨层 last-wins 与 premise filter 的等价性是最难部分,需专门 differential test | ADR,Slice 3b 前置 |

## §5 实施切分

### 5.1 Blueprint 拆分(命名承母文档 1 §5.4 预定)

1. `stage-a-lifecycle-convergence` — 先行,含 migration CLI 与 docstring 诚实化;
2. `slice-3b-ledger-migration` — 紧随,含 atomic flip + 七步精简 + 回归门(§2.3 两处消费方)。

两 blueprint 各配 sibling audit log,按 per-phase 只读审计节奏推进(每阶段实现后 doc-only 严格审计 + fix commit,再进下一阶段)。

### 5.2 分支纪律

- 本设计分支:`v0.2.0-design-storage-hardening-2026-07-31`(doc-only);
- 实施分支:`v0.2.0-impl-storage-hardening-<date>`(scope-freeze 时 rebase 到设计分支上);
- factgraph 发布:按 surgical checkout runbook 走 `feature/...` 分支,**不合 main**,user merge。

### 5.3 时间框架

用户裁定:全战役(Stage A + Slice 3b)目标 **一个月内**交付(Claude Code 协助实施)。母文档的周数估算不再作为排期依据,仅保留其阶段间依赖顺序。

## §6 meander 对接面(Stage A 落地后的收益清单)

| meander 现状 | Stage A 后 |
|---|---|
| 28 处 `fg.save_workspace()` 每写必整库快照 | 写穿即持久,调用变 metadata no-op;后续版本可整批删除 |
| `load_workspace` 无 `artifact_store_root`,重载配不了 sidecar | lifecycle 收敛后参数不对称消失 |
| attach 零使用(因其为 ergonomic-poor subset) | attach 成 superset 后,meander 可按需迁移到 Database-owned lifecycle(非强制) |
| `deploy.yml` 无 `ref` 检出 sister repos(永远 default branch) | **风险项**:v0.3.0 breaking 落 main 时 meander 必须同步适配,发布时序需与 meander 侧协调(同 PR #22 教训) |

## §7 验收 gates(两 blueprint 共用)

1. 全套件零回归(base 对照运行);
2. attach/create/load_workspace 三 lifecycle 行为等价性测试(同一操作序列 → 同一 ledger 内容 + 同一 head);
3. `entities.create/delete` 经 tx 链:写后 `db.head()` 与 ledger 内容一致性断言;
4. INV 族保持:spec §12 结构不变量 + INV-7c 逐条测试映射;
5. §2.3 两处新消费方(premise 过滤、program evidence)专项回归;
6. migration CLI:v0.2 workspace 样本 → 新格式 round-trip 校验;
7. **INV-15 读面逐点枚举**(§2.6 耦合 1):view projection / `premise_scoped_ledger` / `find_*` / assertion views / program evidence witness 采集,五面各有一条 `__system__.revokes` 不外泄断言;推理侧增加端到端门:同一规则集在 3b 前后 `support_digest` / `view_snapshot_digest` 逐字节一致(digest 按 canonical fact bytes 计算,与表布局无关 —— 若不一致即读面泄漏或投影漂移);
8. **幂等语义搬家等价**(§2.6 耦合 2):旧 ingest_keys 语义下的重复写序列,在新 SDK 层幂等下产生相同 ledger 终态;
9. **规模基准 neutral-or-better**(§3.3):100K/1M 合成 ledger 四曲线,3b 后冷启动/RSS 不劣于 3b 前,预期改善需记录实测数字。

## §8 Open Items

- [ ] Q-SAE-1/2/6 三项裁定确认(§4)→ 落 ADR;
- [ ] **meander 预期数据量级评估**(trace ingest 速率 × plan 数 × 保留期 → claims 增长曲线):决定 Stage B 是"到线再议"还是需凭 §3.3 harness 数字提前立项;
- [ ] Stage B 触发线三指标的具体阈值(由 §3.3 harness 实测数据填充);
- [ ] meander 发布时序协调方式(§6 风险项);
- [ ] `2026-05-20_db-attach-lifecycle` blueprint 归档(文档合并事故清理,与本战役并行的独立小项);
- [ ] PR #22 eval-perf follow-up blueprint(范围外,另开);
- [ ] **L2 goal-scoped loading design-point**(§3.3 登记的缺口:goal 绑定下推 / e_ref-premise SQL pushdown;Stage C 设计时必须一并议,否则 lazy 化只到 predicate 粒度)。**归属已裁:factgraph 检索层、引擎无关**(§3.3 引擎侧调研结论;引擎经现有 adapter 契约收已裁小的 EDB);
- [ ] **meander 求值失效策略**(eval 层近期杠杆,与存储无关、可先行:head-unchanged skip —— 无写入不重估;delta-predicate 交集失效 —— trace ingest 只重估谓词/实体相交的 plans;直接针对 `reevaluate_open_plans` 热循环)。
