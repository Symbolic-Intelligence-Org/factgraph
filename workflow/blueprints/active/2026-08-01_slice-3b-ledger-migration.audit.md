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
| 2026-08-01 | **Phase 0 补钉轮复验:全部闭合;Phase 1 有条件放行 —— 唯一前置 = 用户对 C1 的批准落笔** | 四验证器逐项复现(见下文 §Phase 0 补钉轮复验);残留仅 C1 署名(授权问题非代码缺陷)+ 三项转 Phase 1 gate/纪律 |
| 2026-08-01 | **C1 用户批准;Phase 1 正式放行** | 用户批准 UNSET=SQL NULL 编码,署名补入 spec 裁定行与本表闭环行;Phase 0 全部关闭 |
| 2026-08-01 | **内联裁定(协调方):`tx_ref` ≡ `tx_seq`(INTEGER)** | 兑现 C2 留待的 Phase 1 裁定:claims 与 claim_meta 事件行共用同一引用空间,满足 Q-SAE-9 §2 的 8 字节/行成本口径;canonical `tx_id` 经 tx_seq→tx object 链解析恢复(attach 期索引或按需走链),审计面无损。用户可否决 |
| 2026-08-01 | Phase 1 C0 停点轻核通过 | `3aafbd4b`:读等价 fixture + 生产 `Database.repair` golden,3 文件全新增,`src/` 零差分,既有 fixture 零修改;联跑 4 passed / 3 subtests 亲测复现。完整对抗审计留 Phase 1 边界 |
| 2026-08-01 | **内联裁定(协调方):`claim_meta` 恢复 `kind` 列(六列形态)** | codex C1 前上报冲突①的裁定。决定性依据:dbtx_v2 canonical bytes **本就携带每条 meta 的 kind**(已被 golden 字节钉死)—— 无 kind 列则冷启动读与账本重放不一致,存储对其所总结的链信息有损,且读等价门与公开 `MetaEntry` API(任意 key 的 int/float/bool/time/json/bytes)必破。终态:`claim_meta(asrt_id, key, kind, value, tx_seq, op_ordinal)`,PK 不变 `(asrt_id, key, tx_seq, op_ordinal)`;UNSET tombstone = kind 与 value **双 NULL**(对称保留,用户行两列均 NOT NULL,prepare 边界守卫);kind 不入 fact 身份/digest(digest 输入范围不变)。spec §3.2/§5.2、Q-SYS-B §4.4 标注扩展(kind 恢复;value_tag/namespace/category/origin/derivation 照旧不保留)由 C1 同 commit 修订。用户可否决 |
| 2026-08-01 | **内联裁定(协调方):initial meta 同 op 内 key 唯一,prepare 边界显式拒绝** | codex C1 前上报冲突②的裁定。同 op 内同 key 重复共享 op_ordinal 撞事件 PK,且"同一瞬间两个值"在 Q-SAE-8 全序模型下语义退化 —— 显式拒绝优于静默去重(fail-closed)或第三层序号(为退化用例膨胀 PK)。同 key 连续赋值一律经独立 `append_meta` op(各得 op_ordinal)。约束在输入域,wire format 不变,既有 golden 不受影响;拒绝须覆盖**所有**携带 initial meta 的 op 准备路径(assertion/revocation/其他)并各配负向测试(三侧守卫);CHANGELOG 记 Breaking(此前静默接受)。用户可否决 |
| 2026-08-02 | C1 停点轻核:golden(9 passed/3 subtests 含 C0 门)与读等价 fixture 全绿;全套件 **19 红 = 17 PyReason(未计划)+ 2 migration CLI(C4 已计划)** | 亲测定位:C1 已提交 DDL 为终态双列形(`value`/`value_tag` + CHECK),**`rest_terms` 列已删** —— PyReason edge 2-position 写路径当场断裂;codex 上报文字"删除后 17 项失败"实为当前 HEAD 状态。codex 依纪律停点上报,未 hack 测试 |
| 2026-08-02 | **内联裁定(协调方):rest_terms 冲突采选项 1 = adopted Q-SYS-B §4.2(c) 原样执行;C2 fix-forward 恢复列** | 权威依据亲手核实:Q-SYS-B §4.2 Q15.1 明文锁定"Slice 3b 保留 rest_terms 列作 legacy compatibility;真正 drop 延后 Slice 5 三项绑定(drop 列 + adapter rewrite + ADR-INV9 strict enforce)",且选项表已显式否决 blanket weak enforce(b ✗)与提前 adapter rewrite(a ✗,违反 user reviewer §1.3 第 3 项)。据此:①C2 恢复 `rest_terms` 列(nullable TEXT)入 3 表 claims,双真窗口 = 新路径写 `value`/`value_tag` + `rest_terms=[]`,legacy PyReason adapter 照旧写 2-position;②不加任何 len≤1 runtime enforce(INV-9 enforce 整套归 ADR-INV9);③blueprint §6"INV 族保持"之 INV-9 读作"新路径成立、legacy 路径豁免至 Slice 5"(Q-SYS-B §4.3.2 dual-truth 窗口);④17 项 PyReason 测试须零修改回绿;⑤选项 2(隐藏 meta 兼容事件)否决 —— 未设计的 meta 类型污染 Q-SAE-9 分级与三组测量;选项 4 否决 —— 破坏不退门。C1 记 fix-forward 偏差:超裁 §9.4 全内联,违背 adopted partial 口径,根因是工作包/blueprint"收口"措辞歧义(已由协调方修正 blueprint Goal 2)。用户可否决 |
| 2026-08-02 | Phase 1 C2 三表 claim 统一 | `609317e3`:fix-forward 恢复 nullable `rest_terms`;新 unary 路径以 `value/value_tag` 为权威并写 `[]`,legacy n-ary 路径保留;revokes-as-claim + INV-15 五读面、ingest_keys 表退场而 set/add 语义保持、annotation 双物化退场、四列与 surrogate id 删除;17 项 PyReason 零修改回绿。旧 checkout `3aafbd4b` 实跑捕获 legacy n-ary fixture,未手写期望值 |
| 2026-08-02 | Phase 1 C3 L0 索引重构 | `1438890f`:索引由三表事件重建,物理 `_ClaimMetaEvent(tx_seq, op_ordinal)` 与公开历史投影分层;冷启动/写后/force-replace 保持一致;baseline harness 同 commit 改为按列 introspection 识别 physical meta 表并计入 event objects/index refs |
| 2026-08-02 | Phase 1 C4 v0.2 → 3b 终态迁移 | `5c0c7e31`:弃用会覆盖新 DDL 且破坏 meta 事件序的 SQLite 物理 backup;只读解析 released 七表 v0.2 逻辑快照,在全新三表目标以单次 `commit_batch(tx_seq=0)` 写入 repair anchor。fixture 为测试内合成、schema 忠实且覆盖 n-ary / 同 key 多 meta / revocation / annotation 四特征,另验三表 introspection、open/verify 与后续可写;两项原计划 migration 红转绿 |
| 2026-08-02 | **Phase 1 实施完成,停下待对抗审计** | C0-C4:`3aafbd4b` / `5ba4eeed` / `609317e3` / `1438890f` / `5c0c7e31`;dbtx_v2 serializer/production commit/repair + production repair goldens 与 C0 两组读等价 fixture 全绿且 fixture 零修改;PR #20/#21/#22 精确面 **157 passed**;canonical 全套件 **2788 passed / 32 skipped / 1 deselected / 1098 subtests**。Phase 2 未启动 |
| 2026-08-02 | **Phase 1 对抗审计:0 blocker / 8 serious(去重 6 类)/ 7 minor —— 有条件不放行,补钉轮先行** | 六透镜完整运行(首轮网络故障 2/6,断点续跑补齐 4/6);最高契约与四裁定验实,缺陷集中在 system-claim 解释通道守卫、迁移 annotation 保真、证据完整性;全文见 §Phase 1 对抗审计 |
| 2026-08-02 | **内联裁定(协调方):annotation 不加第 7 列;合同投影 + hidden-key companion 事件分解修复** | 否决 `annotation_refs` 列:列不入 M op 线格式会使 Phase 2 parity、不可篡改性与账本重建开洞。C-1:reload 只对 initial-meta 事件执行 `annotation_v1` 纯函数合同投影,语义仲裁以 pre-flip 等价 fixture 为准;late append 不得启发式投影。C-2:v0.2 `annotation_rows` 是迁移地面真值;合同可再生行按 `(asrt_id,key,namespace,category,kind,value)` 精确跳过,非合同行把 namespace/category 编入 hidden key 并成为链上 M 事件;仅“v0.2 迁移非合同 annotation 撞键”窄域允许 companion event,不扩张一般单物理事件承诺。增补 scope:PyReason/ProbLog live accept 同样写 hidden-key 事件,冷启动无损;ProbLog namespace 必须跨 reload 非空。World 1(late shared meta、源无 annotation)live/reload 均为 `[]`;World 2 合同 `shared/source` 与 custom namespace companion 并存。namespace/category 清理与引擎 annotation 契约重设计登记为 Slice 5 捆绑项。用户可否决 |
| 2026-08-02 | Phase 1 补钉 A-C | `1267d551`:所有公开/通用 claim 写入口 pre-commit 拒绝 `__system__.*`;迁移 annotation skip 改成 per-claim 完整合同 identity;initial-meta 合同投影与 hidden-key companion 统一 live/reload/replay;World 1/2、跨 claim 撞值、ProbLog cold reload 常驻门通过 |
| 2026-08-02 | Phase 1 补钉 D-F 完成,停下待复验 | `claim_args` 严格交叉校验;Ledger `Idempotency` 自动物化 ingest_key 事件;INV-12 Database 本层负向;旧 checkout `3aafbd4b` 实跑生成新增组合过滤 golden,原有 dbtx/read fixtures 零修改;PR 精确面 **157 passed**;canonical **2794 passed / 32 skipped / 1 deselected / 1106 subtests**;ruff + diff-check 全绿 |
| 2026-08-02 | **Phase 1 补钉轮复验:A-F 实质全闭;新增 P1-R1~R4 —— 最后一张 P1-R 补丁卡后关闭 Phase 1** | 双验证器逐项复现;2 个相邻通道 serious(hidden-key 前缀无守卫 → 变砖/伪造)+ Q-SYS-B 增量性违规 + INV-12 半闭;全文见 §Phase 1 补钉轮复验 |
| 2026-08-02 | blueprint lifecycle `scoped` → `implementing`;Phase 1 P1-R 收官实施 | Phase 0/1 已进入代码实施但头部状态滞后,依 lifecycle 规则补正;P1-R 为 Phase 1 最后补丁卡,Phase 2 仍冻结待复验放行 |
| 2026-08-02 | **Phase 1 P1-R 收官卡完成,停下待复验** | `__factgraph_annotation_v1__:` 在 Ledger/Database/SDK 与 write_protocol 的 assertion/revocation/append_meta 通道 pre-commit 拒绝;内部 annotation/迁移以私有 carrier 保留合法通路;畸形持久化 key 统一 fail-closed 为 `LedgerFormatError`;Q-SYS-B 四段原文恢复并以追加警告表达修正;INV-12 write_protocol/entity_write 两层负向门补齐。dbtx_v2+读等价 **7 passed / 3 subtests**,PR 面 **157 passed**,canonical **2822 passed / 32 skipped / 1 deselected / 1106 subtests**,ruff + diff-check 全绿;Phase 2 未启动 |
| 2026-08-02 | **P1-R 收官复验通过;Phase 1 正式关闭,Phase 2 放行** | 手核:四层前缀守卫 + 私有载体类型、Q-SYS-B 增量性恢复(原文逐字回归 + ⚠️ 追加式)、INV-12 两本层负向、套件 2822/32/1/1106 亲测复现;详见 §Phase 1 收官复验 |
| 2026-08-02 | **进程机制建立(用户批准 2026-08-02):桥梁清单 + 收官量化** | 背景 = 用户对项目野蛮生长的担忧;桥梁清单专节立于本 log(B1-B6,新桥同 commit 登记否则视为走私),收官量化行入 blueprint §7;后续 slice 沿用 |
| 2026-08-02 | **六项内联裁定用户追认(2026-08-02)** | ①7 表格式无升级路径 ②`tx_ref`≡`tx_seq` ③`claim_meta` 六列(kind 恢复+双 NULL tombstone)④initial meta 同 op key 唯一 ⑤rest_terms 采 Q-SYS-B §4.2(c) ⑥annotation 合同投影 + hidden-key 事件(含迁移撞键窄域 companion 放宽)—— 全部经用户追认关闭;本表历史行的“用户可否决”标记保留原样(书写时为真),追认状态以本行为准;spec ×3 与 Q-SYS-B ×4 在世署名行已同步更新 |
| 2026-08-02 | Phase 2 前半停点轻核 | `201d89e8`(全序解析/UNSET/统一 effective/窄域 audit API)+ `1c942aea`(adapter 入链/parity/六列篡改检测/migration genesis 收敛);golden 与读等价 fixture 零修改亲核;**B7 桥同 commit 登记 —— 桥梁清单纪律首次自转生效**;专项 253 passed |
| 2026-08-02 | **内联裁定(协调方):as-of 置于 EvidenceEnvelope/audit context 层,`ProofReceipt` 本体保持 as-of-free** | receipt as-of 三角冲突裁定。此解为两条 adopted 约束合力所迫:Q-SAE-8 裁定 1 要求 receipt 携带 as-of 字段,blueprint §6 digest 冻结门禁止 support_digest canonical bytes 变化 —— 唯一同时满足两者的位置是 envelope 层(receipt-as-artifact = envelope + body,字段在 envelope 即为携带)。深层一致性:as-of 是"何时切的证据"= provenance 语境,非 proof 事实身份 —— 与"meta 历史入 tx 链、不入 state_digest"(Q-SAE-7 §4)同一分层逻辑;sidecar 的 digest↔bytes 双射是内容寻址诚实性的完整性资产,多版本寻址 `(support_digest, event_seq)` 会为不随 event_seq 变化的 body 制造纯重复并弱化该双射 —— 否决。执行约束四条:①`ProofReceipt` canonical bytes 字节冻结不动;②`as_of_event_seq` 必须随每一个持久化的 envelope 载体序列化,冷启动 audit 可回读(回路测试:切 receipt → 冷启动 → audit 面读回同一 as-of);**若当前不存在持久化 envelope 载体,停下上报,不得自设新存储位置**;③验证默认 latest-effective 不变(裁定 1 (ii)),as-of 重放仅 audit/explain 面(iii);envelope as-of 校验 fail-closed(event_seq 越 head 或畸形即拒,不静默钳制);④sidecar 维持 support_digest 单址,双射不变量显式断言。用户可否决 |
| 2026-08-02 | Phase 2 receipt as-of 落地(本提交) | 载体盘点确认唯一现成持久化 `EvidenceEnvelope` 载体为 `audit/round_events.jsonl` 的 passed `check_result.result.evidence_envelope`;在该载体序列化 `as_of_event_seq`,冷读后由窄域 audit helper 对当前 Ledger head fail-closed 校验并重放。`ProofReceipt` canonical bytes/support_digest 与 `FileArtifactSidecar` 单址均未改,字面 hex+digest 与碰撞拒绝门新增。`Ledger.latest_event_sequence()` 是 application→core 正常向下的公开只读契约,非临时跨层桥;桥梁清单无新增项。 |
| 2026-08-02 | Phase 2 硬门 fix-forward `67246b67` | 全量 golden 联跑发现前半提交的 parity 校验把 repair-add 漂移行误绑定到 repair op 自身位置;生产 repair fixture 的物理 drift 行 `(tx_ref,op_ordinal)` 可与同 tx 的 repair-remove 位置碰撞。校验改为先按 repair-add 的 assertion 身份验证并消费原物理事件组,再走普通 position-bound ops;既有 production repair fixture 零修改恢复全绿。无协议/DDL/写路径变化。 |
| 2026-08-02 | **Phase 2 实施完成,停下待对抗审计** | `201d89e8` / `1c942aea` / `67246b67` / `77482bba`;Q-SAE-8 全序/UNSET/receipt-as-of/窄域历史、adapter M 入链与六列 parity 全落。dbtx_v2 + pre-flip 读等价 fixture 零修改;Phase 2 精确面 **16 passed / 14 subtests**;PR #20/#21/#22 精确面 **157 passed**;canonical **2832 passed / 32 skipped / 1 deselected / 1122 subtests**(相对 2822/32/1/1106 净增 10 pass / 16 subtests)。Phase 3 未启动。 |
| 2026-08-02 | **Phase 2 对抗审计:0 blocker / 4 类 serious / 7 minor —— 有条件不放行,补钉轮先行** | 三透镜(事件语义/as-of 裁定合规+入链/证据与范围);as-of 合规面满分;serious = append_meta 绕链变砖(第三个假绝对句)、chosen/canon 守卫静默拆除、repair-add 注入洞、私有名触达 0→18 未登记;全文见 §Phase 2 对抗审计 |

### 2026-08-02 C 项内联裁定逐字记录

> **【裁定回复:C 项 —— 否决 annotation_refs 列,分解修复】**
>
> **否决第 7 列**:表列不入 M op 线格式 → Phase 2 parity 开洞、不可篡改性缺口、重建不可恢复。与 kind 裁定同源原则:存储与链必须互相可重现。
> **C-1**:reload 侧 annotation 投影改为只作用于 initial-meta 事件(与 live 的 prepare 路径同一 annotation_v1 纯函数契约);语义仲裁 = pre-flip 等价 fixture;World 1 的 live/reload 分裂据此消除。
> **C-2**:迁移以 v0.2 源 annotation_rows 为地面真值:合同可再生者按 (asrt_id, key, namespace/category, kind/value) 精确跳过(与 B 的 per-claim 域一致);非合同者落 hidden-key 事件(namespace/category 入 key 编码,链携带);撞键时允许 companion event —— **单物理事件承诺仅在“v0.2 迁移非合同 annotation 撞键”窄域放宽**,此放宽与范围限定由你在 audit log Session Journal 转录为内联裁定记录(协调方 2026-08-02,用户可否决),连同本裁定全文。
>
> **【C 裁定增补(在前一条裁定之上)】**
>
> **scope 修正**:非合同 annotation 的 hidden-key 编码不只服务迁移 —— **live 引擎写入路径(pyreason/problog accept)同样落 hidden-key 事件**,reload 后 namespace/category 无损回读;
> **新增验证项**:写一个跨 reload 的 ProbLog namespace 回读测试(find_annotations(namespace="problog") 冷启动后必须非空)—— 疑似现有 live bug,先复现再修;
> **Q-SYS-B premise correction**:§4.4 Q15.3 加纯增量标注 —— “'annotation_rows 无写入源'前提不成立:adapters/pyreason/accept.py 与 adapters/problog/accept.py 为现役写入源(2026-08-02 核实)”,连同本裁定入 audit;
> 维度清理(namespace/category 收敛 + 引擎 annotation 契约重设计)**登记为 Slice 5 捆绑项**,3b 不做。
> World 2 期望终态:reload 后 = 合同投影 (source, observed) + companion 的 custom namespace annotation 并存(与 v7 双写语义一致);World 1 期望终态:live 与 reload 均为 [](除非 initial meta 触发合同投影)。两个世界各补回路测试。
> A/B 已完成部分连同 C 一并提交;然后按原补钉包继续 D-F。

## Phase 0 adopted commitments worklist(verbatim)

以下清单逐行转录 adopted ADR 的承诺与 gates;勾选表示实施 Phase 已完成,**不是**表示 Stage A 已有。

### Q-SAE-8 §1 Decision

- [x] **claim_meta 事件化:每行是一个不可变 meta event,PK `(asrt_id, key, event_seq)`;last-wins = 组内 `max(event_seq)`。**
- [x] 采用 **`(tx_seq, op_ordinal)` 二元组**:`tx_seq` = 提交序(Stage A 后一次 commit = 一个事务,天然全序);`op_ordinal` = 本次 commit 内按输入顺序的操作序号(覆盖"一次调用同 key 多次赋值"的次序);
- [x] 全部读取入口(premise filter、AssertionMeta 投影、reload、导出)统一按此二元组字典序解析;
- [x] reload/导出/迁移**保序不变量**:落库即定序,任何重建路径不得重排;
- [x] 失败回滚:事务失败则该 `tx_seq` 下全部事件不存在(原子性由 Stage A 追加项 (a) 保证)—— 无部分序号泄漏。

### Q-SAE-8 §4 后果

- spec 修订面:claim_meta 表定义(+event_seq)、§9.7、INV 族("immutable"从表级降为行级);**Q-SYS-B §4.4 对应条款按本 ADR supersede 标注**;
- 与 Q-SAE-9 咬合:J 类 claim 覆盖行与 tombstone 事件(Q-SAE-9 定义)都是本 ADR 的 meta event,共用 `(tx_seq, op_ordinal)` 序;
- meta 历史入 `tx_id` 链、不入 `state_digest`(Q-SAE-7 §4 已裁)。

### Q-SAE-8 §5 验收 gates

1. [x] 重放等价:含重复键 append_meta 的序列在新表可完整重放,读输出与 6 表现状逐字节等价(含一次调用内多次同键赋值);
2. [x] premise filter 差分测试:重分类全路径 + revoker 对称可采性;
3. [x] reload 保序:落库 → 冷启动 → 导出 → 再导入,event 序不变;
4. [x] 若 (iii) 采纳:as-of 重放正确性(任取历史时点,effective meta 与当时实测一致)。

### Q-SAE-8 §6 裁定

- codex 评审:Q-SYS-B supersede、全局序分配、receipt 语义三分、(b) 拒绝理由不成立 —— **全部采纳**(拒绝结论保留、理由重写);
- [x] **裁定 1(用户 2026-07-31)**:receipt 承诺语义 = **事件化后 receipt 携带 as-of(event_seq)字段;v0.3 验证默认按 (ii) 最新 effective(现行为);(iii) as-of 重放作为 audit/explain 面能力**;
- [x] **裁定 2(用户 2026-07-31)**:meta 历史读取 = **v0.3 不出通用 SDK API,保留窄域 audit/debug 接口**。

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
| T2 / C1 | `b6ff1a8a`:保留 UNSET=SQL NULL,明确记为 2026-08-01 内联裁定编码(**用户批准 2026-08-01**,署名同步补入 spec 裁定行)|
| T3 / C2 | `b6ff1a8a`:`tx_seq` 仅定为 Q-SAE-8 提交序;与 Q-SAE-9 `tx_ref` 关系留 Phase 1 裁定 |
| B1 / D1 | `5d9e7463`:SQLite/durable 改 N=5 中位数+抖动带;tx-object 是唯一 byte-exact 分量 |
| B2 / D2 | `5d9e7463`:删除 8-row 硬断言;projected Ledger rows、persisted physical rows、eager workset 分名报告 |
| D3 | batch=1 的 3,000-commit interactive 摊销基线已在 7 表翻转前落数 |
| D4 | cold attach 后 eager projection rows、resident row objects、meta/annotation index references 已入 group 1 基线 |
| D5 | Frozen method 明记 `_ledger_for_attach` private dependency 与 alias/update 约束;同时记录 workset 所依赖的 `_meta_*` / `_anno_*` adapter 更新纪律 |
| B3/B4 minor | spec 历史“仅 2 个原语”行加 ⚠️;`idx_claim_meta_key_value` 注释收窄为候选过滤,组内 max 才决定 effective |
| 额外 minor | read suite 措辞从“all supported filter shapes”收窄为代表性 shapes,不再过诺 |

补钉期间未修改 `src/`、DDL 或生产写路径;readline shim 仅在测试进程内注入,无文件落盘。Phase 1 仍须协调方复验放行。

## Phase 0 补钉轮复验(2026-08-01,Claude 定向四验证器 + 独立复跑)

**结论:G1-G3 / T1 / T3 / B1-B2 及 D1-D5 全部闭合(逐项复现验证);T2/C1 部分闭合 —— 裁定记录存在但未署名,待用户批准/否决。**

复现要点(全部亲测或验证器落盘证据):
- commit-path golden 真走生产入口(`Database.create` + `commit_changes`,即 SDK/application 层同一入口;monkeypatch 生产 id 源 `_new_assertion_id`),断言**落盘读回**的 tx object 字节与 ledger_meta head 三元组(含逐环 state_digest);fixture 同时钉住"append_meta/schema_change 不动 LtHash state"的不变量;3 项变异探针(tx 字节/state_digest/repair canonical)全部红显,control 全绿;
- Q-SAE-8 §4 三行与 ADR 源**字节级一致**;Q-SYS-B 标注纯增量且正确切分 supersede 范围;本审计的"Phase 0 对抗审计"节在补钉范围内字节未动;闭环表无过诺;
- 基线双 profile 复跑:tx 字节精确复现(803,893 / 1,429,893,各 5/5 样本一致),sqlite 中位数落在记录带内,workset 计数精确复现(27,000 / 159,000);第 9 物理行溯源 = `trace_id` 经 `SHARED_ANNOTATION_KEYS` 复制物化入 annotation_rows;batch=1 摊销恶化(267.964→476.631 B/claim)与 Q-SAE-9 §6 预期一致;
- canonical 套件 2773/32/1/1098 逐字复现,跑前跑后工作树零污染;六 commit 全部 scope-clean;`src/` 零差分;未 push。

残留处置:
1. repair 生产路径组装未 golden(三 op 字节布局已钉,序列化器级)→ **转 Phase 1 gate**:首 commit 补生产 repair golden,或将 repair 重放纳入读等价 differential;
2. harness `physical_meta_rows` 枚举三个表名,换表若改名会静默少计 → **转 Phase 1 纪律**:DDL 变更同 commit 由 introspection 派生或扩表名元组;
3. 抖动带为 5 样本观测 min/max 而非上界 → **Phase 4 对照纪律:中位数对中位数,带仅作背景;sub-1% 差异视为噪声**;
4. CI ruff 范围不含 tests/benchmarks 新文件(既有范围,两文件本轮 ruff 全绿)→ 留待未来 hygiene slice。

**放行裁定:Phase 1 有条件放行。唯一前置 = 用户对 C1(UNSET=SQL NULL)批准落笔(署名补入 spec 裁定行与本文件闭环表);若否决,回退表示中立措辞后放行。**

## Phase 1 implementation evidence(2026-08-02,待对抗审计)

### Commit chain

| Slice | Commit | Evidence |
|---|---|---|
| C0 flip 前捕获 | `3aafbd4b` | 7 表完整逻辑序列的 Ledger/premise/chosen/projector 读面 fixture;真实 `Database.repair` tx object/head golden |
| C1 DDL + 基础写入 | `5ba4eeed` | 三表 `_DDL`;claims `tx_ref=tx_seq`;六列 claim_meta 事件表;kind/value 双 NULL tombstone 约束;initial meta 同 op key 唯一;七表 v0.3 dev workspace 显式拒绝+指引 |
| C2 七步精简 | `609317e3` | revokes-as-claim、ingest_keys/claim_args/annotation_rows/revokes 表退场、双写退场、rest_terms adopted compatibility 窗口、INV-15 与 digest 门 |
| C3 索引重构 | `1438890f` | L0 三表全量驻留索引按物理事件重建;event 对象保留 `(tx_seq, op_ordinal)`;harness workset adapter 同步 |
| C4 migration + 收尾门 | `5c0c7e31` | v0.2 七表逻辑快照直达三表 repair anchor;合成、schema 忠实、四特征俱全的七表 CLI round-trip;全部专项与 canonical suite 归零 |

### Phase-boundary gates

- **dbtx_v2 字节不漂移**:`tests/test_dbtx_v2_golden.py` + `tests/test_slice3b_phase1_read_equivalence.py::test_production_repair_tx_object_and_head_are_frozen` 全绿;Phase 0 后所有 `tests/golden/dbtx_v2/*` 与 `tests/golden/slice3b_phase1/*` fixture 零修改。终态 SHA-256 分别为 `430924a0…`,`04aac99b…`,`72820ab…`,`583b3053…`,`d80ed7d…`,`61a81da…`,`a72224d5…`。
- **最高契约——读逐字节等价**:`test_all_read_surfaces_match_the_pre_flip_golden` 与旧 checkout 实跑捕获的 `test_legacy_nary_read_surfaces_match_the_pre_flip_golden` 全绿;覆盖 Ledger 全部代表性公开读面、premise filter、chosen、projector,system claims 过滤后相等。
- **INV-15 + digest 冻结**:`test_inv15_system_revocation_is_hidden_except_exact_id_audit_lookup` 覆盖 Ledger factual scans 与 SDK canonical scans 不外泄、精确 id audit lookup 可达;meta/annotation 与 premise/projector 面由两组 pre-flip 读等价 golden 承载。`test_system_claims_do_not_change_support_or_view_digest_inputs` 对 support/view_snapshot 逐字节字面值;LtHash element 仍为 `asrt_id‖assertion_digest`,dbtx production head golden 同时钉住 state_digest。
- **INV 族映射**:INV-1/5/11 由三表仅 append factual/system claim + 单事务 commit/read-rebuild 门覆盖;INV-2 由 Database 服务端 `_new_assertion_id()` UUID4 hex 生成边界与 production id monkeypatch gates 保持;INV-3 由 `test_batch_failure_rolls_back_facts_and_head_together` 与 commit-path golden 保持;INV-4 由 dbtx_v2/read goldens及 `tup_v1` 既有协议套件保持;INV-7c 由全套件 identity retract guards 保持;INV-9 新路径 unary 与 legacy n-ary 豁免分别由 `test_new_workspace_has_exact_three_table_shape_and_tx_refs` / `test_legacy_nary_claim_uses_rest_terms_carrier` 覆盖;INV-10 由既有三侧 system/reserved 守卫及 initial-meta 负向门保持;INV-12 由 SDK 与 Database 本层 revoke-of-revoke 负向分支覆盖;INV-13 由 active factual 差集、set-after-revoke 与 premise/projector 等价门覆盖;INV-14 由 application retract replay/idempotency 全套件回归保持;INV-15 如上一条。
- **atomic flip / migration 边界**:新建工作区直接得到且仅得到 `claims`,`claim_meta`,`ledger_meta`,无 alpha 数据搬迁;七表 v0.3 `db/assertions.db` 两种入口均 fail-closed 并给 rebuild / 原 v0.2 `migrate-workspace` 指引;CLI 使用测试内合成、schema 忠实且四特征俱全的 v0.2 fixture 直达三表并通过 open+verify,迁移后下一写 `tx_seq=1`。
- **专项回归**:golden/read/atomic/migration 联跑 `28 passed / 3 subtests`;PR #20/#21/#22 精确调用式:`PYTHONPATH=src pytest -q tests/test_premise_admissibility_filter.py tests/test_premise_predicate_allowance.py tests/test_premise_predicate_block.py tests/test_premise_scoped_view.py tests/sdk/test_rule_program_evaluate.py tests/test_audit_evidence_graph.py tests/test_candidate_evidence_steps.py tests/test_core_annotation_evidence.py tests/test_ledger_concurrency.py tests/test_application_entity_view.py tests/test_sdk_assertion_view_unification.py`,结果 **157 passed**。原 Phase-boundary “ruff 全绿”记录不实:`actual_claim_args` 为 F841 死代码;补钉 D 改为与 `rest_terms` 严格交叉校验后,implementation+本轮测试 ruff 与 `git diff --check` 才实际全绿。
- **canonical suite**:`PYTHONPATH=src` + process-only readline shim + `--ignore=tests/test_pyreason_provenance_v0.py` + 唯一 approved deselect,结果 **2788 passed / 32 skipped / 1 deselected / 1098 subtests**。相对 C3 的 2785,净增 3 pass = 两项计划内 migration failure 闭合 + 一项 released 七表 fixture 新门禁。

Phase 2 保持冻结;以上仅声明 Phase 1 物理事件地基与表形态完成,不把 Phase 2 的 UNSET 统一解析、receipt as-of、append_meta parity/audit API 或 Phase 3 的 meta 分级当作已交付。

## Phase 1 对抗审计(2026-08-02,Claude 六透镜完整运行 + 独立复跑)

**结论:0 blocker / 8 serious(去重后 6 类)/ 7 minor —— 有条件不放行 Phase 2,补钉轮先行。**

**验实的合格面(全部经复现,非空心)**:读等价最高契约成立 —— legacy n-ary fixture 经审计侧在 3aafbd4b 旧代码上**字节级复产**(sha256 939decab…,与入库 fixture 及 HEAD 输出三方一致),既有 fixture 零修改属实;digest 冻结门的字面量经旧代码重算相符(support/view_snapshot);LtHash 全族函数 AST 级字节相同;INV-15 五读面结构排除 + 对抗探针无泄漏;变异探针能杀死等价门;七步精简与四项内联裁定实质忠实落地(revokes-as-claim 物理核验、rest_terms §4.2(c) 无走私 enforce、initial-meta 三侧守卫齐、tx_ref≡tx_seq 已断言);全套件 2788/32/1/1098 与 PR 面 157 passed 复现;未 push;Phase 3 面零渗漏;benchmark 在两个中间 commit 复证"不崩不谎"。

**Serious(去重编号,→ 补钉轮)**:

| # | 发现 | 处置 |
|---|---|---|
| P1-S1 | **Ledger prepare 边界收下它无法忠实索引的 `__system__.*` claim**:经 `Ledger.append_assertion`/公开 `write_protocol.set_field` 伪造 `__system__.revokes` → 活跃撤销**仅在 reload 后生效**(live/reload 分裂);不支持的 system pred **先 commit 后 raise → 工作区永久变砖**。Stage A F1/C1 同型洞(新解释通道未配三侧守卫) | 补钉 A(最重) |
| P1-S2 | **C4 迁移静默丢 v0.2 annotation**:`_annotation_compatibility_meta_rows` 的 skip-set 以 (key,kind,value) 全工作区池化、无 asrt_id —— 与**任意其他 claim** 的 meta 行撞值即被丢;`--no-archive` 下不可恢复 | 补钉 B |
| P1-S3 | **reload 侧 shared-annotation 投影是启发式而非事件重放**:迁移会捏造 v0.2 源中不存在的 annotation;自定义 namespace 的 annotation reload 后变形为 `shared` | 补钉 C(回路保真裁定) |
| P1-S4 | INV-15 证据句过诺:所点名测试未测 meta/annotation 面(实际由等价 golden 承载) | 补钉 F |
| P1-S5 | audit"ruff 全绿"不实:C1 引入 F841 死代码(ledger.py:849 `actual_claim_args`),CI 门 28→29;伴生:`append_assertion` 对 `claim_args` 参数只验形不落库不交叉校验,静默丢弃 | 补钉 D |
| P1-S6 | **spec §9.6 ingest_keys 退场仅部分交付却无 partial 标注、无 Deviations 记录** —— rest_terms 事故同型(完成度过诺);伴生 minor:无 ingest_key meta 行时 Idempotency 参数失忆(7 表时代 ingest_keys 表独立记忆) | 补钉 E |

**Minor ×7**:组合过滤读分支未入等价 fixture(探针已证当前字节相等);Idempotency 失忆(并入 S6);INV 映射缺 INV-2/3/4/13 + blueprint §12 指针过期;kind 恢复在三处文档误署"用户裁定"(实为协调方内联裁定、否决权仍开);spec §3.4 仍写 kind"消失"与六列自矛盾;INV-12 新守卫分支缺本层负向测试;迁移 late-append shared-key meta 被制造成 annotation 的表面变化无记录。另:audit"真实七表 fixture"措辞过诺(实为测试内合成、四特征俱全)。

**放行裁定:Phase 1 补钉轮完成并复验后放行 Phase 2。** P1-S1 为最高优先(伪造通道 + 变砖通道);P1-S2/S3 涉迁移数据保真;S4-S6 为证据完整性。

## Phase 1 补钉轮复验(2026-08-02,Claude 双验证器 + 独立复跑)

**结论:A-F 全部实质闭合(逐项复现);发现 2 个相邻通道新 serious + 1 个 moderate 文档纪律违规 —— 收官前需最后一张小补丁卡(P1-R 组),完成后 Phase 1 关闭、放行 Phase 2。**

**闭合证据(要点)**:A = 14/14 伪造尝试跨 7 通道全部 pre-commit 拒绝、零残留零变砖、内部 retract 发射三层(write_protocol/Database/SDK)live+reload 均正常;B = per-claim 身份(含 asrt_id),变异探针证明旧池化逻辑丢行、新逻辑保真;C = ①-④ 全验(reload 仅投影 initial-meta 事件、World 1/2 探针双侧一致、迁移以源 annotation_rows 为地面真值、ProbLog 跨 reload 回读修复于 Ledger+Database 两层、companion 单事件且 tx_seq 锚定);D = claim_args 死代码变承重交叉校验(不匹配即拒且零写入);E = Idempotency 仅传参数即物化 ingest_key 事件,同句柄+冷启动双侧去重探针通过;F = 组合过滤 golden 经 `git archive` 3aafbd4b 字节级复产(sha256 645182e5…)、PR 面精确调用式已入本 log 且复跑 157 passed、署名清扫全对(仅 C1 为用户批准,其余全为协调方+否决权开放);套件 2794/32/1/1106 双方独立逐字复现;协调方全部审计节字节未动;fixture 仅新增零修改;未 push。

**新发现(→ P1-R 补丁卡)**:

| # | 发现 | 处置 |
|---|---|---|
| P1-R1(serious) | **公开 meta 通道不拒绝 `__factgraph_annotation_v1__:` 前缀** —— 垃圾载荷 hidden-key 经 `fg.assertions.append_meta`/`commit_changes(meta_appends)`/`Ledger.append_meta` 提交成功后**每次 open 必炸**(UnicodeDecodeError @ ledger.py:452-470)= commit-then-brick 同类;基线期即存在,非本轮引入 | R-a |
| P1-R2(serious) | **格式良好 hidden-key 经公开通道 = annotation 伪造 + live/reload 分裂**(live 不可见,冷启动后凭空出现伪造 problog annotation)—— 三侧守卫 checklist 第四次同型:hidden-key 编码开了新的被解释 key 命名空间但公开通道未封 | R-a |
| P1-R3(moderate) | **Q-SYS-B 增量性违规**:4 处原始段落被删除/改写而非标注(§4.4.2 前提行、§4.4.2 kind bullet、§4.7.2 表头、§7.4 carry-forward),且替换文自称"纯增量标注"名不副实;历史文本仅存 git | R-b |
| P1-R4(moderate) | INV-12 两处新守卫分支(write_protocol.retract_by_asrt:178、entity_write:1128)仍无本层负向测试(原 minor 只闭一半) | R-c |
| note | hidden-key M 事件不在 tx object JSON;**adapter annotation 持久化路径 tx_seq 越 head 且无 tx object(未真正入链)**;commit_batch meta 索引与 reload annotation 索引瞬态不对称(仅迁移使用) | **Phase 2 具名 gate:全部 meta-event 写者过 tx 协议 + parity 校验覆盖 hidden-key** |
| note | 转录 commit 归属与计划不符(C 裁定全文落在 48881bd5);blueprint 头部 Status/Last Updated 未更新 | R-d 顺手 |

## Phase 1 收官复验(P1-R,2026-08-02,Claude 手核)

R-a:四层守卫亲核(ledger `_ANNOTATION_COMPAT_PREFIX` + 私有载体 `_AnnotationStorageMetaRow` 区分内部写者;write_protocol:267 / sdk/store:742 / database:2701 公开通道拒绝),新负向测试 64 passed / 21 subtests;R-b:Q-SYS-B 四处历史原文逐字恢复 + ⚠️ 追加式修正(diff 亲核,增量性回归);R-c:write_protocol / entity_write 两处本层 INV-12 负向测试落地;R-d:blueprint 头部推进 `implementing`。canonical 套件 **2822/32/1/1106** 亲测复现(相对 2794 净增 28);golden 零修改;暂存空;未 push。

**裁定:P1-R 全闭 —— Phase 1 正式关闭,Phase 2 放行。** Phase 2 具名 gate(复验期立):①全部 meta-event 写者过 tx 协议(adapter annotation 持久化路径现状 = tx_seq 越 head 且无 tx object,未真正入链);②parity 校验覆盖 hidden-key 事件;③commit_batch meta 索引 vs reload annotation 索引的瞬态不对称随事件解析统一收敛。

## Phase 2 implementation evidence(2026-08-02,待对抗审计)

### Commit chain

| Commit | Evidence |
|---|---|
| `201d89e8` | `_meta_history_events` + `_effective_meta_events` 建立唯一 `(tx_seq,op_ordinal)` 解析器;premise/AssertionMeta/reload/export/dedup 等读者统一收口;双 NULL UNSET 私有载体与窄域 `factgraph.audit.meta_history` |
| `1c942aea` | Database-backed PyReason/ProbLog annotation 写者改走 dbtx_v2 M op;append_meta 六列链-账本 parity + hidden-key 载荷校验;v0.2 migration genesis 改用 A/R/M 标准操作;新增 adapter production golden,B7 同 commit 登记 |
| `67246b67` | repair-add parity 按 assertion 身份消费 drift 原物理事件组,修复 repair op position 碰撞;生产 repair golden 零修改回绿 |
| `77482bba` | `EvidenceEnvelope.as_of_event_seq`;既有 round-event envelope 持久化/冷读;audit fail-closed as-of 重放;`ProofReceipt` canonical body 与 sidecar 单址冻结门 |

### Phase-boundary gates

- **全序/last-wins 单源**:`Ledger._effective_meta_events(...)` 以 `(tx_seq,op_ordinal)` 字典序选每 `(asrt_id,key)` 的 max;所有公开/兼容投影只消费该 resolver。重复 key、同 tx 多 M op、冷启动、canonical export/import 均由 `tests/test_slice3b_phase2_meta_events.py` 覆盖。
- **UNSET + 三侧守卫**:双 NULL 仅私有 `_MetaUnsetInput`/`_MetaTombstone` 可达,通用 Database/Ledger meta 输入拒绝伪造;断言与 revoker 对称 tombstone 后 effective 缺失,premise exclusion/allowance `absent_ok` 分支均有负向门。DDL CHECK 与 dbtx M 解码保持 kind/value 双 NULL 对称。
- **全部持久化写者过 tx**:Database-backed adapter annotation 产生 append_meta tx object且 head 连续推进;现成 `adapter_annotation_commit.json` production golden 钉住链字节。仅 unmanaged `from_schema_classes` compatibility 保留 B7 明列 direct fallback,不冒充已拆桥。
- **append_meta parity**:open/repair 对 tx 链与物理 claim_meta 的 `asrt_id/key/kind/value/tx_seq/op_ordinal` 全列比对;hidden-key 解码载荷同样受保护;六列逐一篡改与 well-formed annotation payload 替换均 fail-closed。repair-add 是唯一 sanctioned 链外事实锚,按其原物理事件组验证。
- **receipt as-of**:盘点确认当前唯一持久化 `EvidenceEnvelope` 载体是 `audit/round_events.jsonl` 的 passed Check envelope。运行时盖 `(tx_seq,op_ordinal)` 边界、round event 写入 JSON pair、冷启动 audit 回读同值;畸形/越 head 均拒绝且不钳制。普通 proof verification 未改,仍按 latest-effective;历史重放仅 `factgraph.audit.meta_history`。
- **digest 冻结**:`ProofReceipt` 字面 canonical hex 与 `support_digest=sha256:06a1621a…` 新门钉死;sidecar 仍仅以 support_digest 单址,同址异 bytes 碰撞拒绝。adapter M/UNSET 不改变 LtHash state element、support/view snapshot 定义;既有 dbtx/read goldens零修改。
- **回归证据**:Phase 2/golden 精确面 `16 passed / 14 subtests`;PR #20/#21/#22 原精确命令 `157 passed`;canonical 命令 `PYTHONPATH=src` + process-only readline shim + approved ignore/deselect 得 **2832 passed / 32 skipped / 1 deselected / 1122 subtests**。changed-file ruff 与 `git diff --check` 全绿。

Phase 3 保持冻结;本节只声明 Q-SAE-8/Phase 2 承诺完成,不把 Q-SAE-9 两层 tx-lift、属性声明、premise_eligible 封闭或惰性分级当作已有。

## 桥梁清单(Bridge Inventory,2026-08-02 用户批准建立)

规则:3b 收官时冻结本表;Slice 5 blueprint 开工以此为验尸单;**新桥必须同 commit 登记入表,否则审计视为走私**;拆桥时表内所列测试一并删除。

| # | 桥 | 引入点 | 守卫 | 死期归属 | 拆除时同删测试 |
|---|---|---|---|---|---|
| B1 | `claims.rest_terms` legacy 列(PyReason 2-position 载体) | C2 `609317e3`(Q-SYS-B §4.2(c)) | 新路径写 `[]`;无 blanket enforce(设计如此) | **Slice 5 三项绑定**(drop 列 + adapter rewrite + ADR-INV9) | legacy n-ary 读等价 fixture 及用例;PyReason 专项中依赖 2-position 的部分 |
| B2 | hidden-key annotation 编码(`__factgraph_annotation_v1__:` 事件) | 补钉 `1267d551`(C 裁定) | 前缀保留四层守卫 + 解码 fail-closed(`8c193e10` 已落地) | **Slice 5**(namespace/category 收敛 + 引擎 annotation 契约重设计) | World 1/2 回路、ProbLog cold-reload 门、reserved-namespace 负向组(契约重设计后重写) |
| B3 | `ingest_key` 兼容事件 + `Idempotency` 参数 + 两 helper | C2(§9.6 partial)+ 补钉 E 自动物化 | 参数与显式 meta 不匹配即拒 | 随 caller 改写另行完成 —— **归属待裁**(Slice 5 候选) | `test_idempotency_is_materialized_and_survives_reload` |
| B4 | v0.2 七表迁移走廊(逻辑快照解析器 + migrate CLI v0.2 路径) | C4 `5c0c7e31` + 补钉 B/C | staging→verified replacement→可见归档 | **待发布裁定**(Q-SAE-6 时序定 v0.2 支持窗口) | test_a20e 迁移用例 + 合成七表 fixture |
| B5 | deprecated `Ledger.append_claim` 兼容入口 | 3b 前(pre-existing) | A 项 system-pred 守卫已覆盖 | 待裁(caller 清点后) | 对应兼容用例 |
| B6 | `_ledger_for_attach` 等私有名跨层调用(sdk×2、benchmark×1)+ tests→`_enc*` reach-through | Stage A / Phase 0 | audit 冻结方法节同 commit 更新纪律 | **3b 自身 Goal 7**(Phase 2-4 内转正) | 无(转正即改引用) |
| B7 | unmanaged `Store` adapter annotation 直写 fallback | Phase 2 meta-event writer 收编 | attach/Database-backed lifecycle 一律经 dbtx_v2 M op;仅 `from_schema_classes` 无 Database runtime 保留 direct Ledger compatibility | **随 unmanaged lifecycle 去留裁定移除或 Database 化** | adapter managed-path tx-object golden + unmanaged adapter compatibility tests |

## Phase 2 对抗审计(2026-08-02,Claude 三透镜 + 独立复跑)

**结论:0 blocker / 去重后 4 类 serious / 7 minor —— 有条件不放行 Phase 3,补钉轮先行。**

**验实的合格面**:as-of 裁定四条执行约束全 PASS(ProofReceipt 七键序列化未动、digest 字面量原样、envelope 生产路径回路含冷启动、fail-closed 三层无钳制、sidecar 双射、adapter 真入链 tx object 亲验、新 golden 变异探针红显、B7 围栏、parity UPDATE/INSERT/DELETE 三方向全拦);统一解析包内全量覆盖(前 rows[-1] 三站点、AssertionMeta、reload、导出、chosen、canon、accept、_queries、package_export 全走 effective 语义);UNSET 六通道伪造负向全拒、intra-tx 混序探针正确;Q-SAE-8 §5 四 gate 落位;repair-add 位置修正(67246b67)在 pre-fix checkout 复现 3 红、HEAD 转绿;勾选无过打;Phase 3 零走私(chosen 排序未动);套件 2832/32/1/1122 三方独立复现;协调方审计节字节未动。

**Serious(去重 →补钉轮)**:

| # | 发现 | 处置 |
|---|---|---|
| P2-S1 | **`Ledger.append_meta` 仍是绕链公开写者(经 `fg.ledger` 可达),managed 工作区直写 M 事件无 tx object —— Phase 2 新 parity 门使之成为无恢复 commit-then-brick**(实测 open 炸且 **repair 也炸**:repair 只赦免漂移 claim,无漂移 M 事件通道);audit:405"全部持久化写者过 tx"为**战役第三个假绝对句**;未守卫亦未登记桥 | 补钉 A |
| P2-S2 | **chosen/canon 的 ingested_at 重复守卫被统一解析静默拆除**:pre-Phase-2 重复行 → ViewProjectionError fail-closed;HEAD → last-wins **静默翻转评估可见的胜者**(实测投影翻转);`Database.commit_changes(meta_appends)` 对 `_SYSTEM_MANAGED_META_KEYS` 无守卫;未披露未测试;Phase2→3 窗口弱于 7 表基线 | 补钉 B |
| P2-S3 | **repair-add 漂移位置组接受注入 meta 事件**:`_verified_assertion_digest` 只按 `rows[:tx_row_index]` 重算,注入行按 rowid 恒排 `tx_id` 标记后被静默排除 —— 实测伪造 `origin_binding`(premise_eligible 键!)开库通过并改变评估可见性;与 audit:406 表述相悖 | 补钉 C |
| P2-S4 | **跨层私有名触达 0→18/27 站点**(`_effective_meta_rows` 族被 adapters/audit/sdk/application 全面消费,audit/meta_history 还 import 了 `_normalize_event_sequence`),B6 未刷新 —— Goal 7 要求 Phase 2-4 内**退休**该债务类,实际膨胀 | 补钉 D(倾向直接转正) |

**Minor ×7**:①迁移 genesis 改 A/R/M 后 docstring(database.py:823-829)与 CHANGELOG:29 仍称 repair anchor(被本范围证伪);②predicate-block 路径无 UNSET 差分;③16/14 精确面无调用式记录(157 面教训重演);④worklist 反向漏勾(Q-SAE-9 §2.1/§3.1/§3.3 已交付未勾);⑤souffle `_build_fact_rows` 改发 effective-only 事实集 —— 方向正确但落在 blueprint §3 非目标面(引擎行为变更),未披露未钉测;⑥`find_meta` 兼容投影墓碑盲,与 SDK docstring"完整历史可审计"相悖;⑦"再导入"腿实为 parse-only(无真回写),gate 措辞应如实。另 note:src/service 三处 raw first-wins 残留(包外,挂 known-gap);premise_filter 模块级 docstring 一行过期;UNSET 现无公开 API(与披露一致)。

**放行裁定:Phase 2 补钉轮(A-E)完成并复验后关闭 Phase 2、放行 Phase 3。** 第七项内联裁定(as-of envelope 层)追认待用户。

## Deviations

- **C1 `rest_terms` 暂时超裁后 fix-forward**:`5ba4eeed` 曾删除 `rest_terms`,与 adopted Q-SYS-B §4.2(c) 不符;`609317e3` 恢复 compatibility 列并以旧 checkout 实跑 fixture/17 项 PyReason 零修改证明终态闭合。根因与裁定见 Session Journal;无终态 scope 偏差。
- **Q-SYS-B Q15.3 annotation 前提修正**:现役 PyReason/ProbLog accept 仍著述 namespace/category;按 2026-08-02 内联裁定,3b 不增加未入链物理列,而用 initial-meta 合同投影 + hidden-key M companion 事件保持 live/reload/replay。仅 v0.2 迁移非合同 annotation 撞键允许同逻辑 key companion event;维度清理与引擎契约重设计捆绑到 Slice 5。
- **§9.6 partial**:物理 `ingest_keys` 表已退场,但 `claim_meta.ingest_key` 事件、`Idempotency` 参数、计算/lookup compatibility helper 尚在。此前 3 表仅在 caller 同时传 ingest_key meta 时记忆;只传 `Idempotency` 会在同句柄下一调用及 reload 失忆,而 7 表独立表会记住。本补钉令 Ledger 参数总是物化匹配事件,恢复兼容语义;正式删参数/helper 留后续 caller 改写。
