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

## Deviations

| Date | Deviation | Disposition |
|---|---|---|
| 2026-07-31 | SDK `commit_changes` + `RevocationInput` 导出提前于 Phase 2 落地(blueprint §5 归属双粒度提交面) | 追认保留(与 Phase 1 写链耦合紧密,拆出反而制造中间态);Phase 2 清单对应项标记已完成 |

## Known Gaps(Phase 1 durability,reaudit 前登记)

1. **macOS fullfsync 未实现**:tx/schema/view object 采用 portable `fsync(file)` + `fsync(parent dir)`；所有 fsync 失败现已显式中止操作,但尚未调用 macOS `F_FULLFSYNC`。是否引入平台特化 durability profile 留后续 design point 裁定。
2. **缺失 tx object 无 re-anchor 路径**:`Database.repair` 必须从可验证的 authoritative head tx object 追加审计事件；若该对象缺失,即使 SQLite ledger 完好也会 fail-closed 且 repair 拒绝。re-anchor/reconstruction 协议另议,不在本 fix commit 自行设计。
