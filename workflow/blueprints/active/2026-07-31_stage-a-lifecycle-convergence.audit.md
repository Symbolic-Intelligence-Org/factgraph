# Audit Log: Stage A — Lifecycle 收敛 + 写链加固 + 双承诺指纹

- Blueprint: [2026-07-31_stage-a-lifecycle-convergence.md](./2026-07-31_stage-a-lifecycle-convergence.md)

## Adopted Conclusions(引用来源 → 本任务采用)

| 来源 | 采用结论 |
|---|---|
| Q-SAE-6 adopted | v0.3.0 载体;pin-first 发布时序(meander 侧先 pin v0.2 SHA) |
| Q-SAE-7 adopted | 双承诺(LtHash state_digest + tx delta 链);fail-closed + repair;meta 入链不入 state digest |
| Q-SAE-8 adopted | (tx_seq, op_ordinal) 事件序 —— 本 blueprint 只落 tx_seq 基础(单事务提交序),event 化在 3b |
| Q-SAE-9 adopted | 双粒度提交面(裁定 1);tx object 承载批次 meta(默认执行项);tx_ref 列留 3b |
| 设计文档 §2 | 现状锚点(14 reject、绕链漏洞、O(N) digest、head 覆盖写)全部 2026-07-31 逐行核实 |
| codex 评审 2026-07-31 | 发布顺序反转、单事务原子化、AUTOINCREMENT 每表独立(tx_seq 需显式分配) |

## Session Journal

| Date | Event | Notes |
|---|---|---|
| 2026-07-31 | blueprint created at `scoped` | scope 由 adopted ADR 锁定,无 draft 探索期;内联裁定:Q-SAE-2 = migration CLI(opt-in),异议窗口至 Phase 3 前 |
| 2026-07-31 | **Phase 0 baseline exception 登记**(Claude 裁定,已核实) | codex 完成 39 文件 surgical sync 至 `b92d6bf5`;全套件 **2725 passed / 32 skipped / 1 failed**。唯一失败 = `src/service/static_ui.py:23` 导入已退役符号 `render_evidence_graph_html` —— 经 `git show HEAD` 核实该符号在 **sync 之前的 HEAD 即已缺失**(既存跨层漂移,非 Phase 0 引入),service 层在本 blueprint 模块边界外。裁定:登记为 baseline exception,Phase 0 验收基线 = 上述数字;漂移修复拆为独立任务(task_b3c98818),不扩本 blueprint。附注:时间戳测试单次抖动(复跑通过,记录在案);本机 readline segfault 经外部只读 shim 规避(环境项,不入库,已核实无 shim 文件混入工作树) |

| 2026-07-31 | **Phase 1 只读审计完成(Claude,四透镜对抗式)** | 裁决 **pass-with-fixes**。已确认:单事务原子性(数据+head CAS+LtHash 状态同 BEGIN IMMEDIATE)、LtHash 为正宗 Meta LtHash16 谱系(1024×16bit,SHAKE-256 XOF,群律经 200 轮乱序暴力试验+794 子集无碰撞验证)、门禁全为真实测试(真子进程 os._exit 崩溃注入于事务中途、真双进程 flock、真 SQL 层 CAS)、性能复现(1.28ms@100K/1.48ms@1M,ratio 1.32,对照 v0.2 的 303ms→3218ms)。**Blocking fixes(Phase 2 前)**:F1 `__system__.` 断言侧无守卫→digest 不对称→合法 API 提交后 workspace 变砖(INV-10 违反;探针实测复现;含 same-batch 撤销缝隙与带点/不带点判定双标,统一为 INV-13 公式);F2 state_digest 仅绑 asrt_id 不绑内容(UPDATE 篡改 Alice→Mallory 实测不可检出)——违背 Q-SAE-7 裁定 1 对抗性完整性定位,element 改 `asrt_id‖assertion_digest`、scheme 升 `lthash16-v2`(预发布零兼容负担,此为最后廉价窗口);F3 legacy ledger 写模式打开无 flock + 内存索引校验→双句柄 double-revoke 持久损坏且 repair 拒收(裁定:**写模式拒开** legacy,报错指向 Phase 3 migrate 流程);F4 tx object fsync 失败被静默吞 + macOS fullfsync 姿态零记录 + tx object 缺失时 ledger 完好也无恢复路径(最低要求:fsync 失败停止静默 + known-gap 登记;re-anchor 流程另议)。**Deviations 登记**:SDK `commit_changes`/`RevocationInput` 公开面提前落地(属 Phase 2 双粒度清单)——追认保留,记为提前量。非阻塞建议:带种子随机序列差分测试、半成品 workspace 报错指引、deselect 节点 id 逐字记录(= `tests/test_a20e_registry_final_removal.py::ServiceRouteRemovalTests::test_service_app_v1_drops_registry_routes`)、lthash docstring 前置条件。 |
| 2026-07-31 | **Phase 1 blocking fix 实施完成,待轻量 reaudit** | F1 统一 `__system__.` 守卫并封住 same-batch target；F2 state element 升 `lthash16-v2(asrt_id,assertion_digest)` 且 open 重算 claim 内容；F3 legacy file/direct durable Ledger injection/v0.2 scheme 全部拒绝写开并指向 Phase 3 migration；F4 file+directory fsync 失败显式中止。新增 200 步固定种子随机差分及四项负向探针。提交前 gate:`2741 passed / 32 skipped / 1 approved deselected`;100K/1M median `1.31ms/1.91ms`,ratio `1.46`。Phase 2 仍冻结。 |
| 2026-07-31 | **Phase 1 reaudit 通过(Claude,独立探针)→ Phase 2 放行** | 裁决 **pass**(commit `bfdacfd7`)。独立验证:套件 2741/32/1(唯一失败仍为登记基线例外);F1a `__system__.evil` 提交被拒(明确报错)、F1b `__system__x` 无点变体两侧一致(提交+reopen 均通过,缝隙闭合);F2 直接 UPDATE 篡改 Alice→Mallory → reopen `DatabaseIntegrityError: assertion_digest does not match factual content`(精确到 asrt_id);F3 legacy 裸 ledger 写模式拒开且报错指向 Phase 3 migrate flow;F4 代码级核实文件+目录 fsync 均显式抛错,残留 suppress 仅锁释放/tmp 清理(合法 best-effort),两条 known-gap 已登记。性能复跑两档中位 1.23ms/1.22ms,平坦,内容绑定零回归。 |
| 2026-07-31 | **Phase 2 实施完成,待只读审计** | 六提交:`3d7254df` planned-op→Database DTO 翻译器；`1ba7a207` `apply_write_plan` 单次 `commit_changes` + shared annotation 读面等价；`1e4d5fee` attach `entities.create/delete` 入链；`4cb7a904` in-memory/Wire batch 一批一 tx；`3c012e47` ingest-key 幂等命中改走 Ledger 索引(O(1),禁止全量 meta 扫描探针)；`3ec09863` attach 不可翻译 batch fail-closed。实体 gate:create/delete 各仅推进一个 `tx_seq`,同批 tx_id 一致,delete 后 state_digest 回到初始空集,close→reopen 通过；batch gate:多 entity 与 WireBatchPlan 各仅推进一个 tx,同一 wire 重放返回原 IDs 且不推进 head；view-attached create/delete/batch 均只读失败。PR #20/#21/#22 专项 **157 passed**；全套件基线口径(`tests/`,排除 pandas 环境文件并精准 deselect static_ui 已登记节点)**2749 passed / 32 skipped / 1 approved deselected / 1094 subtests**。Phase 3 未启动。 |

| 2026-08-01 | **Phase 2 只读审计完成(Claude,四透镜对抗式)** | 裁决 **pass-with-fixes**。已确认:双路径 ledger 内容等价(10 claims+1 revoke 深探针,claims/claim_args/meta_rows 含序/annotation_rows/revokes 剔除 asrt_id/ingested_at/DB-owned 三键后逐行相等)、**绕链封死**(patch 注爆 set_field/append_assertion 等全部直写口,attach create/delete 零触发 —— 设计文档 §2.2 核心漏洞正式闭合)、一批一 tx、INV-12 三查+同批重复拒绝、零写入错误路径、meta 保序(Q-SAE-8 前置)、annotation 读面等价、PR #20/#21/#22 面零回归(premise 90 + evidence 164 亲跑全绿)、新测试为真门禁(tx_seq 精确 +1、tx_id 集合等式、digest 回空精确值、find_meta 注爆探针)。**Blocking fixes(Phase 3 前)**:B1 同批 "revoke X + 逐字重断言" 静默丢字段 —— ingest-key 幂等归并查预提交状态、不感知本批 revocation targets,重断言被归并到即将撤销的 assertion(applied 还报告已撤销 id),**静默数据丢失**(双探针复现);修法 = existing 解析排除本批 revocation 目标集。B2 retract 幂等语义分歧 —— legacy 对已撤销目标幂等 no-op(返回既有 revoker),新路径硬拒绝整批失败;含 retract 的 wire 重放在 attach 非幂等,**违反 blueprint §6 的 INV-14 承诺**;修法 = 翻译层 retract 幂等预解析(find_revoker 命中 → existing_revoker,剔除出 revocation_inputs)。B3 WireBatch attach 绕过标量归一化 —— 同一 wire plan workspace 成功(uuid 归一小写)/attach 报错,破坏 wire 重放跨 runtime 可移植;修法 = attach wire 路径复用 plan 级归一化 + parity 测试。**B4 打包(随 fix commit)**:空 attach batch 假 fail-closed 报错(early-return 空结果)、fail-closed 诊断信息带首个不可表示 op 的 path+原因、`_SHARED_ANNOTATION_KEYS` 双源复制合一(import 单一权威表)、157 口径补记精确 pytest 调用式、非 attach entity_ref parity 探针固化为测试。**Deviation 追认二则(见下表)**。非阻塞留后:op_index 失败定位(docstring 或全行 failed)、混合 can_apply 批形状文档化、application 调 ledger 私有名转正(Phase 4/3b)、stray tx object 并入 known-gap。 |

## Deviations

| Date | Deviation | Disposition |
|---|---|---|
| 2026-07-31 | SDK `commit_changes` + `RevocationInput` 导出提前于 Phase 2 落地(blueprint §5 归属双粒度提交面) | 追认保留(与 Phase 1 写链耦合紧密,拆出反而制造中间态);Phase 2 清单对应项标记已完成 |
| 2026-07-31 | application write protocol 的 `FieldValue` 明确是 JSONValue/EntityRef,不承载 `bytes`;SDK batch 对 bytes 因而落 legacy fallback | attach 上禁止 fallback 触 Ledger,改为提交前 fail-closed(零写、head 不动);非 attach 行为不变。**已裁(2026-08-01)**:fail-closed 批准;`FieldValue` bytes 扩展列为 Phase 3 前置(blueprint §5 已注),否则 lifecycle 内部化构成 v0.2 行为回归 |
| 2026-08-01 | `fg.batch` 的 `_reject_attached_write` 于 Phase 2 提前拆除(4cb7a904,批量面交付内含) | 追认保留;**Phase 3 reject 拆除口径更新为 12 call sites + 定义** |
| 2026-08-01 | 非 attach 运行时 managed raw entity_ref 批从 legacy shadow 路径改走 application 委托(4cb7a904 拓宽 `_application_write_value_for_op`),超出"Phase 2 仅落 attach"预裁定字面 | 追认保留 —— parity 探针证明 7 claims 逐行相等,回退反而制造 attach/非 attach 判定分叉;B4 要求把 parity 探针固化为常驻测试 |

## Known Gaps(Phase 1 durability,reaudit 前登记)

1. **macOS fullfsync 未实现**:tx/schema/view object 采用 portable `fsync(file)` + `fsync(parent dir)`；所有 fsync 失败现已显式中止操作,但尚未调用 macOS `F_FULLFSYNC`。是否引入平台特化 durability profile 留后续 design point 裁定。
2. **缺失 tx object 无 re-anchor 路径**:`Database.repair` 必须从可验证的 authoritative head tx object 追加审计事件；若该对象缺失,即使 SQLite ledger 完好也会 fail-closed 且 repair 拒绝。re-anchor/reconstruction 协议另议,不在本 fix commit 自行设计。
