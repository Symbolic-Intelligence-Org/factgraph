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
| 2026-08-01 | **Phase 2 blocking fix 实施完成,待轻量 reaudit** | B1 existing 解析排除本批 revocation target,同 tx 逐字重断言生成新 assertion 且字段保持可见；B2 `find_revoker` 预解析 + 同批 target 合并,重复 retract 映射同一 revoker,全命中重放不推进 head；B3 planned-op→canonical term 共用标量归一化,uppercase UUID 在 workspace/attach 均落 lowercase；B4 三种空 batch no-op、fail-closed 首个 op path+原因、shared annotation 单一常量、managed raw entity_ref application/legacy 内容 parity 常驻测试。相关面 **103 passed / 46 subtests**；PR #20/#21/#22 精确专项 **157 passed**；全套件最终 **2753 passed / 32 skipped / 1 approved deselected / 1094 subtests**（首次 migration CLI `generated_at` 跨秒抖动 1 项,单点复跑通过,随后全套 JUnit 0 failures/0 errors）。Phase 3 仍冻结。 |

| 2026-08-01 | **Phase 2 reaudit 通过(Claude,独立验证)→ Phase 3 放行** | 裁决 **pass**(commit `f2325373`)。独立验证:套件 2753/32/1(唯一失败仍为登记基线例外);B1 修复代码与规格逐点吻合(`revocation_targets` 排除集 + existing 解析条件),测试断言严格(head 恰 +1、恰一 active、新 asrt_id、内容保持、result 报新 id);B2 `find_revoker` 预解析 + 同批合并 + 全命中 no-write 断言;B3 跨 runtime UUID 归一化 portability 测试;B4 空批 no-op 测试、fail-closed 诊断带 op path(batch.py:191)、annotation 单源化(`core/protocol/annotation_v1.SHARED_ANNOTATION_KEYS`,两处 import 核实)、157 调用式已录、parity 常驻测试落地。相关面 42 passed 亲跑。**Phase 3 放行**,范围含 bytes/FieldValue 前置项与 12+定义 reject 口径。 |
| 2026-08-01 | **Phase 3 实施完成,待只读审计** | 六个任务提交:`a24d3168` application `FieldValue` additive bytes;`6fc3a70c` `append_meta/schema_change` 规范 tx op(old/new digest only,对应 schema object write-once + replay 连续性);`dd456717` writable attach 写面统一路由 Database;`7b63bba2` create/load owned Database + close/context manager + 12 reject 与定义拆除 + save metadata touch;`cb773192` v0.2 CLI staging/repair-anchor/verified replacement + 完整旧 workspace 默认归档;`8f342ce9` core/store + SDK lifecycle docs/CHANGELOG 诚实化。关键 gate:全套件 **2761 passed / 32 skipped / 1 approved deselected / 1078 subtests**;PR #20/#21/#22 精确专项 **157 passed**;Phase 3 lifecycle/schema/migration 面 **153 passed / 12 skipped / 1 approved deselected / 28 subtests**;implementation ruff 全绿,`git diff --check` 全绿。migration round-trip 保留 claim/arg/revoke 行与裸 UUID ID/meta,迁移后 reopen 校验通过且下一笔写正常推进 `tx_seq=1`。meander 设计快照 `71d26f9` 的 28 个业务 `save_workspace()` 点全为无参且不消费返回值,metadata no-op 化不改控制流;sandbox 继续以目录 copy 运行。Phase 4 未启动。 |

| 2026-08-01 | **Phase 3 只读审计完成(Claude,四透镜对抗式)** | 裁决 **blocking fixes required(C1-C4)**。已确认:三 lifecycle 行为等价(10 步独立探针序列三路 canonical 投影逐行相等、head 一致 tx_seq=10)、12+定义 reject 全拆(pre-state 逐行核对口径)、save_workspace 字节级 no-op + "不 save=丢弃"消失已在 CHANGELOG/user guide 显式声明、owned Database 语义(幂等 close/context manager/双开显式失败)、bytes 四 lifecycle parity、六项裁决四条约束基本合规(additive v2 + docstring、transition 连续性 fail-closed、digest 分职实测、op 序=输入序 —— Q-SAE-8 地基成立)、迁移 round-trip 五表逐字节 + repair-anchor 审计化 + verified replacement 顺序正确、subtests 1094→1078 逐项归因=适配非弱化、a20e known-failure 锚点逐字节未动、meander 28 处 save 无参兼容。**Blocking(Phase 4 前)**:**C1(blocker)`_prepare_meta_appends` 漏保留键守卫** —— 公开 `append_meta(asrt_id,"assertion_digest"/"schema_digest"/"tx_id",…)` 一次调用使 exactly-one 校验永久 fail-closed 且 **repair 拒收**(Phase 1 F1 同型,新 meta 通道重新引入;断言/撤销侧均有守卫唯此缺失);修法=补 `_reject_reserved_assertion_meta` + 负向测试 + revoker 目标同类评估。**C2(serious)未声明的 v0.2 回归**:lifecycle 内部化使 ingest 的 unmanaged raw e_ref 回退在主 lifecycle 上 fail-closed,CHANGELOG/Deviations 零记录;裁定=**(a) 显式声明**(Breaking + Deviations + docs,幸存面 from_schema_classes 定位),meander 适配若撞上再议扩翻译层。**C3(serious)additive 政策在 Database transition 面零执行** + `SchemaTransitionInput` 公开导出构成绕过通道;裁定=**撤回公开导出**(narrow-public-api),Database 层定位为 policy-free 内部机制层并文档声明,政策门归 schema-evolution blueprint 统一设计;补"SDK 面无法非 additive"负向测试。**C4(serious)迁移 replacement 阶段崩溃恢复**:原 workspace 只存活于隐藏 `.{ws}.legacy-*` sibling,CLI 重跑 not_found/noop 双盲,零找回指引;修法=非隐藏备份命名 + not_found/noop 路径扫描 sibling 输出 recovery 指引 + docs 崩溃恢复段。**C5 打包**:半成品 v0.3 三态误导报错(torn-create 指 recreate 而非 migrate)、workspace_incomplete 取代 noop 死循环、digest 失配诊断失真、revoker 保留键全集、迁移负向测试固化(损坏 ledger/--no-archive/registry-only/bytes+同键多 meta)、报错含完整 CLI 命令并去 "Phase 3" 行话、153 口径补调用式、**meander manifest 断裂点补记**(v0.3 manifest 无 schema_digest → meander `load_migrate_or_create` 解 pin 即 KeyError —— 入 Q-SAE-6 适配队列)。登记 known-gap/后续:append_meta 链-账本 parity 校验空洞(3b/Q-SAE-8 收口)、dbtx_v2 golden fixture(3b)、closed-graph SDK 报错、view-attach 错误分类、dry-run ledger 探测、源侧锁探测、staging sibling 清扫、大库迁移进度+open 成本(Q-SAE-6 评估)、14 个 pre-existing F821(独立小任务)、quickstart load_and_save.md 重写级失真(Phase 4 基线)。 |
| 2026-08-01 | **Phase 3 C1-C5 fix 实施完成,待轻量 reaudit** | C1 meta-append 在 SDK 与 Database 双边拒绝三项 DB-owned key,claim/revoker 共用全集,零写/head 不动/reopen 探针；migration revoker 同步改全集。C2 unmanaged raw e_ref 回归已进 CHANGELOG Breaking、Deviations 与 SDK/application docs,幸存 `from_schema_classes` 面明确。C3 `SchemaTransitionInput` 撤出 `factgraph.sdk` public namespace,SDK 非 additive 尝试零推进,core/store 明定 policy-free mechanism。C4 replacement sibling 改可见命名,not-found/noop 双路发现并输出 `workspace_recovery_required` 候选与人工恢复指引。C5 torn-create/registry-only=`workspace_incomplete`,digest 诊断给 manifest/object 双值,Database.open 三态去 Phase 行话且给完整命令；损坏 ledger/`--no-archive`/registry-only/bytes+同键多 meta/revoker reserved 全部固化。meander manifest `schema_digest` 断裂入适配队列。门禁:Phase 3 精确面 **162 passed / 12 skipped / 1 deselected / 34 subtests**；PR #20/#21/#22 **157 passed**；全套件 **2770 passed / 32 skipped / 1 approved deselected / 1084 subtests**；implementation ruff 与 `git diff --check` 全绿(测试 ruff 仅命中已登记的 pre-existing F821)。Phase 4 仍冻结。 |

| 2026-08-01 | **Phase 3 reaudit 通过(Claude,独立探针)→ Phase 4 放行** | 裁决 **pass**(commit `dd2a2d2d`)。独立验证:套件 2770/32/1;C1 三个保留键 append_meta 全拒、head 不动、close→reopen 通过(变砖路径闭合);C2 CHANGELOG Breaking 明文声明 ingest 收窄(含 `from_schema_classes` 幸存面定位);C3 `SchemaTransitionInput` 已撤出 sdk `__all__`;C4 备份 sibling 改可见命名 `<ws>.legacy-<ts>`,重跑扫描新旧双前缀并输出 `workspace_recovery_required` + recovery_candidates;C5 revoker 保留键全集(database.py:886)+ 迁移负向测试 +183 行落地。**Phase 4(文档诚实化收尾)放行**,基线清单 = 母文档 1 §5.5 措辞、quickstart load_and_save.md(重写级)+ schema_definition.md、closed-graph SDK 报错、view-attach 错误分类直通。 |
| 2026-08-01 | **Phase 4 实施完成,待战役终审** | 四个独立步骤:①`2663b2e0` 将 owned graph close 后 11 个 SDK 写面统一为 `SDKStoreError(code="GRAPH_CLOSED")` + lifecycle 指引,view-attach schema 写错误直接呈现 read-only(不再被 non-additive 包裹);②`91c88449` 母文档 §5.5 改为统一 Database/write-through/single-writer/显式迁移叙事,并保留 Q-SAE-6 pin-first 发布边界;③`2351df00` 重写 `load_and_save.md`,同步 schema/data/rules/API 与 stale load docstring;④CHANGELOG 终稿 + 本 audit 收口。门禁:Phase 4 lifecycle/schema/migration 精确面 **163 passed / 12 skipped / 1 deselected / 45 subtests**;PR #20/#21/#22 精确专项 **157 passed**;全套件 **2771 passed / 32 skipped / 1 approved deselected / 1095 subtests**;implementation ruff、`git diff --check` 全绿。Phase 4 后按指令停止;blueprint Outcome/Deviations 汇总与 `implemented` 状态留给 Claude 终审,未执行 push/merge/tag。 |

| 2026-08-01 | **战役终审完成(Claude,四透镜)→ 待最终 docs 修订后 close-out** | **§7 全部 10 gates 终验 PASS**(逐条证据在案:三 lifecycle 等价独立探针、指纹差分 19 passed、历史区分性、崩溃注入/flock/CAS、迁移 round-trip 31 passed、终态写耗时 1.05ms@100K/1.59ms@1M ratio 1.52)。**零代码缺陷**;待修全为文档/记账(D 清单,见终审 relay):D1 CHANGELOG 漏记 manifest 格式变更(即 meander 断裂点,发布说明必须可见);D2 CHANGELOG Added 补 RevocationInput/fg.commit_changes;D3 `02_readwrite_and_ingest.en.md` §2 仍教已移除的 `ledger_path=`(示例照抄即崩);D4 "load_workspace 校验 manifest" 过诺删除(shipped 打开路径不读 manifest);D5 `04_api_surface` §2.5 补 append_meta 行并删 "retract is the only mutation entry" 误断;D6 sdk README 死指针(docs/official/*);D7 read-after-close 分类缺口入 Known Gaps + CHANGELOG:137 标题句收窄为 write failures;D8 打包(layout 图 db/refs 空目录与 views 惰性注记、memory-mode create_view 拒绝措辞、views→assertion_views 命名、audit log 表格空行合并)。**Consolidation 护栏三条(防 3b 口径漂移,进 Outcome)**:Q-SAE-9 "tx object 承载批次 meta" Stage A 只完成**介质裁定**,承载能力整体属 3b meta 分级;Q-SAE-3 触发线附则**未落 Q-SAE-6**,列为欠账(阈值随 meander 量级评估);F821 实测 **18 处**(tests 10 + src 8),审计过程记录的 14 为过程态。CLAUDE.md 的 docs/README.md 治理指针不可闭合(仓库级既存漂移),migration CLI 无中央索引收录 —— 交用户裁定(恢复索引 vs 修订 CLAUDE.md)。close-out 序列:docs 修订 commit → 勾 §7 → Outcome/Deviations → implemented → 归档。 |

## Phase 2 专项回归精确调用式

```bash
PYTHONPATH=src pytest -q tests/test_premise_admissibility_filter.py tests/test_premise_predicate_allowance.py tests/test_premise_predicate_block.py tests/test_premise_scoped_view.py tests/sdk/test_rule_program_evaluate.py tests/test_audit_evidence_graph.py tests/test_candidate_evidence_steps.py tests/test_core_annotation_evidence.py tests/test_ledger_concurrency.py tests/test_application_entity_view.py tests/test_sdk_assertion_view_unification.py
```

## Phase 3 lifecycle/schema/migration 精确调用式

审计表中 **153 passed / 12 skipped / 1 deselected / 28 subtests** 的精确命令为:

```bash
PYTHONPATH=src pytest -q tests/test_factgraph_workspace_lifecycle.py tests/test_db_attach_lifecycle.py tests/test_application_entity_write.py tests/test_sdk_batch_application_delegate.py tests/test_schema_mutation_lifecycle.py tests/test_schema_field_add_lifecycle.py tests/test_a20e_registry_final_removal.py --deselect=tests/test_a20e_registry_final_removal.py::ServiceRouteRemovalTests::test_service_app_v1_drops_registry_routes
```

## Phase 4 verification + Docs To Update 勾验

Phase 4 运行时精确面沿用 Phase 3 文件集并复跑,结果为
**163 passed / 12 skipped / 1 deselected / 45 subtests**。PR 专项沿用上节
“Phase 2 专项回归精确调用式”,结果 **157 passed**。全套件命令为:

```bash
PYTHONPATH=src python -c 'import sys,types,pytest; sys.modules["readline"]=types.ModuleType("readline"); raise SystemExit(pytest.main(["-q","tests","--ignore=tests/test_pyreason_provenance_v0.py","--deselect=tests/test_a20e_registry_final_removal.py::ServiceRouteRemovalTests::test_service_app_v1_drops_registry_routes"]))'
```

结果:**2771 passed / 32 skipped / 1 approved deselected / 1095 subtests**。
`readline` shim 仅在测试进程的 `sys.modules` 中临时注入,无文件入库。

Blueprint §9 逐项:

- [x] `src/factgraph/core/store/docs/README.md`:commit 协议、LtHash state/history
  双承诺、fail-closed/repair、flock、统一布局、迁移崩溃恢复均已覆盖;
- [x] `src/factgraph/sdk/docs/00_user_guide.en.md` §11:write-through、save
  metadata-only、排他锁、统一 layout、migration/recovery 已覆盖;
- [x] `src/factgraph/sdk/docs/04_api_surface.en.md` §2.1:owned/attached ownership、
  view read-only、save 语义、完整性校验已覆盖,并修正 stale “saved workspace”措辞;
- [x] `docs/quickstart/`:重写 `load_and_save.md`,同步
  `schema_definition.md` 的即时 schema_change 历史语义与 `data_model.md` 的
  v0.3 路径/head metadata;邻接 rules 文档的 stale save 叙事同步清除;
- [x] `docs/README.md`:仓库不存在该文件,本 Phase 未新增 docs 入口,故无需更新。

Phase 4 点名补充项:

- [x] 母文档 `factgraph-storage-architecture-evolution.zh.md` §5.5 已诚实化;
- [x] CHANGELOG 三项 lifecycle 语义变更(write-through/save、single-writer、
  layout+migration)、Database-backed ingest 收窄、迁移与中断恢复指引均齐;
- [x] closed-graph SDK 错误与 view-attach 只读错误有常驻负向测试。

## Deviations

| Date | Deviation | Disposition |
|---|---|---|
| 2026-07-31 | SDK `commit_changes` + `RevocationInput` 导出提前于 Phase 2 落地(blueprint §5 归属双粒度提交面) | 追认保留(与 Phase 1 写链耦合紧密,拆出反而制造中间态);Phase 2 清单对应项标记已完成 |
| 2026-07-31 | application write protocol 的 `FieldValue` 明确是 JSONValue/EntityRef,不承载 `bytes`;SDK batch 对 bytes 因而落 legacy fallback | attach 上禁止 fallback 触 Ledger,改为提交前 fail-closed(零写、head 不动);非 attach 行为不变。**已裁(2026-08-01)**:fail-closed 批准;`FieldValue` bytes 扩展列为 Phase 3 前置(blueprint §5 已注),否则 lifecycle 内部化构成 v0.2 行为回归 |
| 2026-08-01 | `fg.batch` 的 `_reject_attached_write` 于 Phase 2 提前拆除(4cb7a904,批量面交付内含) | 追认保留;**Phase 3 reject 拆除口径更新为 12 call sites + 定义** |
| 2026-08-01 | 非 attach 运行时 managed raw entity_ref 批从 legacy shadow 路径改走 application 委托(4cb7a904 拓宽 `_application_write_value_for_op`),超出"Phase 2 仅落 attach"预裁定字面 | 追认保留 —— parity 探针证明 7 claims 逐行相等,回退反而制造 attach/非 attach 判定分叉;B4 要求把 parity 探针固化为常驻测试 |
| 2026-08-01 | lifecycle 内部化使 ingest 的 unmanaged raw e_ref 回退在 Database-backed create/load/attach 面改为 fail-closed,Phase 3 初稿未声明 | 按 C2 裁定走显式 breaking 声明:CHANGELOG + SDK/application 模块 docs 已定位;`FactGraph.from_schema_classes(...)` 仍为 unmanaged Ledger 兼容面并保留旧回退。若 meander 适配实撞该边界,由后续设计决定是否扩翻译层 |

## Cross-repository adaptation queue

1. **meander manifest schema anchor(Q-SAE-6 发布解 pin 前 blocker)**:meander
   设计快照的 `load_migrate_or_create` 直接读取
   `factgraph_workspace.json["schema_digest"]`;v0.3 manifest 只保留 `db/` 与
   `views/` components,不再含顶层 `schema_digest`,解 pin 后必然 `KeyError`。
   适配必须改从 Database head/content-addressed schema object 获取 schema
   anchor,并在 meander pin 更新前完成。此项只登记,不在 hnsm-backend Phase 3
   fix 内跨仓实现。

## Known Gaps(Phase 1 durability,reaudit 前登记)

1. **macOS fullfsync 未实现**:tx/schema/view object 采用 portable `fsync(file)` + `fsync(parent dir)`；所有 fsync 失败现已显式中止操作,但尚未调用 macOS `F_FULLFSYNC`。是否引入平台特化 durability profile 留后续 design point 裁定。
2. **缺失 tx object 无 re-anchor 路径**:`Database.repair` 必须从可验证的 authoritative head tx object 追加审计事件；若该对象缺失,即使 SQLite ledger 完好也会 fail-closed 且 repair 拒绝。re-anchor/reconstruction 协议另议,不在本 fix commit 自行设计。
