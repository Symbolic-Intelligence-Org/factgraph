# Task Blueprint Audit: Runtime Authority Cleanup (sdk ↔ application)

- Blueprint: [2026-04-28_runtime-authority-cleanup.md](./2026-04-28_runtime-authority-cleanup.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-04-28 | draft | Blueprint created | 紧接 OS-prep blueprint scoped phase 暂停而创建。Position 已 stake(application = canonical Python runtime;sdk = product surface)。Scope 起点是 namespace-split blueprint §10 audit 报告点名的 SDK god files + audit 报告 2026-04-20 的"边界靠自律"结论 + OS-prep blueprint Decision 11 的"OS publish 前必须解决 runtime authority 模糊"分析。当前形态是 DRAFT:position 锁,§5.2 sub-decisions(10 项)+ §5.3 推荐起步顺序未 scoped。 |
| 2026-04-28 | draft (v2 patch) | code survey + 防回退条款 + sub-decision K | 用户完成 code survey,确认 Decision 1 在成本曲线上为最便宜路径(`application -> sdk` 反向依赖 = 0;`sdk -> application` 已存在;application 干净小模块 3 文件 / 21 symbol)。基于 survey patch:§1 加 Measured Facts;§5.1 加模块级 boundary table;§5.2 把 A-J 重写为具体 sub-decisions 并新增 K(primitive contract traps);§5.3 letters 重映射;§6 加 Decision 6(防回退条款)+ Trap 6(query / ingest 不能 git mv)。审计 Decision 6 记录全部 v2 patch 决策依据。Position stake 与 Decision 1-5 不动。 |
| 2026-04-28 | draft (v3 patch) | 4 项审查修正 | 用户 v2 review 提出 4 项修正:(P1-1) §4 SDK 现状把 `compile.py` / `registry.py` 错列为 runtime impl,与 §5.1 boundary table 互相矛盾 → 移到 ergonomic / authoring surface;(P1-2) §4 service / agent 依赖现状不基于数据校准 → 改成"以 `rg` 清单校准,不预判依赖密度",清单作为 §5.2 sub-decision I 的 evidence;(P2) §6 Trap 6 + §5.2 C 的行号引用会腐化 → 改成符号 / 路径引用 + `rg` 验证命令;(P3) §5.3 docs 同步不应单列末位 → 改成"贯穿 contract design 与 consumer migration"。Position stake / Decision 1-6 / sub-decision A-K 内容不动。v3 完成后用户支持把 status 推到 `scoped`。 |
| 2026-04-28 | draft → scoped | Status transition | v3 通过用户 review,无 blocking findings。Scoped 进入条件已满足:§5.1 模块级 boundary table 落地;§5.2 11 项 sub-decisions(A-K)带 pre-scoping default;§5.3 推荐起步顺序定型(B+C+D contract design → A → I → E → J → F+G+H 灰区,docs 横跨);§6 Trap 6 + Decision 6 防回退条款写硬。Acceptance(§7)/ Implementation Plan(§8)/ Docs To Update(§9)在后续 decision phase 内逐项 scope 时填具体值。本地文件未 commit — 用户要求 OSS-prep 与 runtime cleanup 多个 untracked blueprint 保持分开,等正式启动 cleanup 分支再 commit。 |
| 2026-04-28 | scoped | Wording cleanup | 按后续核验修正文档状态口径:blueprint §5 从 DRAFT 形态改为 scoped / decision-phase 形态;§7/§8/§9 从"待 scoped 时具体化"改为"待 decision phase 逐项具体化";Decision 3 补记原 draft 阶段 10 项 sub-decisions 后续在 v2 扩展为 11 项 A-K,避免与 scoped row 产生歧义。无 scope expansion。 |
| 2026-04-28 | decision phase | Pass 1:B+C+D contract design scoped | 按 §5.3 推荐顺序先收口 B(Query) / C(Ingest) / D(Derivation evaluate/accept) contract。结论:application 接收 runtime-normalized payload,不接 SDK DSL / facade objects;SDK 保留 ergonomic surface 与 compatibility adapter。Blueprint 新增 §5.2.1,把 §5.2 表格 B/C/D 标成 scoped,并把 §7 Acceptance / §8 Implementation Plan / §9 Docs To Update 的 B+C+D 首批内容具体化。仍只动本地 untracked blueprint/audit 文件,不改代码,不 stage,不 commit。 |
| 2026-04-28 | decision phase (v4 patch) | Round 2 cross-check corrections applied | 采纳交叉核验的 Tier 1+2 high-value corrections,并做本地复核:application public symbols 仍为 21(不改);cleanup framing 改成 complete partial migration;补 `batch.py` / `facade.py` / `store.py` partial migration inventory;扩大 Trap 6 grep;修正 service/agent import 数字为 13 import lines / 9 files excluding markdown,production 仅 `compile_schema_from_classes`;G/J 与 OS-prep #2/#11 关系收紧;commit plan 改为 4-commit squashable stack。拒绝/弱化 3 个误判:不加横切 logging/metrics/deprecation 分类;不改 application symbol count;不写 OS-prep 全量 auto-unhold。 |
| 2026-04-28 | decision phase | Pass 2:A+E+F+G+H+I+J owner/compat scoped | 按用户指示执行 A,继续逐项 scope §5.2。实测确认:`SDKStore.export_package/run_package` 只是 adapter wrapper,service/runtime 直接调 adapter;`_SDKViewsManager` 是 SDKStore-local in-memory named-view manager;`SDKRegistry` 是 authoring-adjacent SDK facade,无现成 `RegistryProtocol`;service/agent production SDK import 仅 extraction 的 `compile_schema_from_classes` authoring helper。Blueprint 新增 §5.2.2,把 A/E/F/G/H/I/J 标成 scoped,并补 §7/§8 acceptance/plan。无生产代码改动。 |
| 2026-04-28 | implementation branch | Shape audit pass 1:B+C+D file shape scoped | 在 `runtime-authority-cleanup` branch 上只读核验 `sdk/query_runtime.py` / `sdk/ingest.py` / `sdk/store.py` / `sdk/batch.py` / `sdk/facade.py` 与 `application/protocol/*`。Blueprint 新增 §5.2.3,明确 commit 1 是 application contract pure add:`protocol/query.py` + `query_runtime.py`,`protocol/ingest.py` + `ingest_runtime.py`,`protocol/derivation.py` + `derivation_runtime.py`,以及 narrow exports。结论:复用既有 entity read/write/schema/common DTO;SDK adapter 切换留 commit 2;不得把 SDK `QueryPlan` / `ReturnContractEntry` / `Field` descriptor / `Derivation` DSL object 带入 application protocol。 |
| 2026-04-28 | implementation phase | Commit 3:service/agent boundary guard + audit close | service/agent SDK imports 实测:13 Python import lines / 9 Python files excluding markdown;plus 1 markdown example。production 仅 1 行 authoring helper(`src/agent/extraction/api.py:compile_schema_from_classes`),其余 12 行在 tests。新增 `test_sdk_consumer_boundary.py` 守护 production allowlist;§5.2 I 升为 Scoped+verified。out-of-scope consumers(`domains/ecss/sdk_helpers.py`,`kernel/adapters/pyreason/*`)记录 Decision 13。 |
| 2026-04-28 | implemented | Commit 4:docs alignment + status implemented | application docs 升级为 canonical Python runtime authority;SDK docs 改为 product surface / adapter framing;`docs/architecture_principles.md` 加 Layer authority;`memory/current.md` 更新 1093-test baseline。Blueprint status `scoped` -> `implemented`;§10 Outcome / Deviations 填写完成。OS-prep #2/#7/#11 wait-for-cleanup-implementation gate 已解,但 OS-prep blueprint 不在本 commit 修改。 |

## Decision Notes

### 关键决策(2026-04-28 draft)

1. **Position stake:application = canonical Python runtime;sdk = product surface**
   - **Why**:
     - 命名:application 指 application protocol(OSI layer 7 隐喻),适合 canonical runtime contract;SDK 指 developer kit,ergonomic-first
     - 已半程在那条路:`test_sdk_*_application_delegate.py` 系列表明 SDK 已 partially delegate to application;反向 reverse 比 finish forward 贵
     - 与已 scoped 的 D1 kernel 定义("面向 Python 接入方的可审计推理 substrate")契合 — Python-facing substrate 需要一层 canonical runtime contract
     - 与 audit 报告 2026-04-20 点名的 god files(sdk/batch.py 1838 / sdk/store.py 1499)成因一致 — SDK 装了不该装的 runtime 责任
     - OS publish 前 lock 这个 position,v0.1 SDK 公开 API 即是干净 facade,长期 contract 稳
   - **影响**:
     - service / agent 长期依赖目标改为 application(SDK 仅 ergonomic 场景)
     - 新 runtime 能力默认进 application/core,SDK 包 wrapper
     - SDK god files 必须先在内部拆 ergonomic vs runtime,再把 runtime 搬 application(防止 application 接 god files)
     - delegation tests(`test_sdk_*_application_delegate.py`)语义从 hidden implementation → explicit facade pattern

2. **走法 A:暂停 OS-prep,串行做本 cleanup,完了回 OS-prep**
   - **Why(对比 B 并行 v0.2 / C 双 blueprint 并行)**:
     - B(v0.2 才做):OS v0.1 publish 后 SDK API 即 contract,v0.2 迁移变 breaking change,需 6-12 月 deprecation cycle;比"现在做"显著更贵
     - C(双 blueprint 并行):两个 blueprint 都会动 SDK / application module docs / pyproject extras,merge 冲突 + 决议依赖会乱;不如串行
     - A:OS publish 推迟 ~1-2 周(同 namespace-split 量级),换一次性付清技术债
   - **影响**:
     - OS-prep blueprint 保持 status `scoped`,但 implementation hold;cleanup 完成后先回到受 SDK public surface 影响最大的 #2 PyPI policy / #11 README OS 形态
     - cleanup 完成前不推 #2 / #11 的最终发布口径(避免在不稳定 SDK / application 边界上做公开承诺);已 scoped 的 #1 / #3 / #6 / #9 与本 cleanup 正交

3. **Draft 阶段不预先决定 §5.2 内 sub-decisions**
   - **Why**:核心 position 已锁,但具体迁移粒度 / 拆分策略 / 顺序 / 测试影响等是 scoping 阶段产物;draft 单方面预设会过早收紧
   - **影响**:§5 Proposed Shape 只列 position + sub-decision 矩阵 + 推荐起步顺序;具体方案在后续阶段填入
   - **后续修正**:初版 draft 为 10 项 sub-decisions;v2 patch 新增 K(primitive contract traps)后扩展为 11 项 A-K,并在 scoped transition row 中冻结为 11 项。

4. **明确 non-goals 防止 scope creep**
   - **Why**:本 blueprint 容易被"顺便重构 god file 内部业务" / "顺便做 D2 演进" / "顺便处理 OS-prep 项" 等扩大
   - **影响**:§3 显式列 6 类 non-goal;尤其 god file 内部业务逻辑不动(只重组 module 结构),D2(language-agnostic)留给后续

5. **工程 trap 提前纳入 §6 Boundaries(继承 namespace-split lessons)**
   - **Why**:5 工程 trap(zsh for-in / BSD sed `\b` / pre-flight 实跑 / __init__ re-exports / 跨包相对 import)已被记录到 user-level memory;本 blueprint 实施期适用,不该再踩
   - **影响**:§6 已列 trap checklist

6. **v2 patch(2026-04-28):code survey 验证 + 防回退条款 + Trap 6 + sub-decision K**

   v2 patch round 把 Decision 1 的 position stake 用代码 survey 数据落地,并加防回退条款 + 工程 trap + primitive trap fold。Position stake 与 Decision 1-5 不动。

   **Survey 数据**(进 §1 Problem Measured Facts 段):
   - `application -> sdk` 反向依赖 = 0(application 不 import sdk,无需 untangle)
   - `sdk -> application` 集中在 runtime-bearing 文件 `sdk/{store,batch,facade}.py`(已部分存在,增量推进)
   - `application` 主 runtime 文件 3 个,public symbols 21(干净小模块)
   - SDK god / runtime files 行数:`batch.py 1838` / `store.py 1499` / `facade.py 927` / `ingest.py 598` / `query_runtime.py 357`

   **为什么 forward 比 reverse 更便宜**:
   - 反向依赖 = 0 → application 无需 untangle SDK 引用
   - sdk → application 已部分存在 → 增量推进,不是从零起步
   - `application` 已是干净小模块 → 升格成本低
   - 合并第三个新模块需重命名 + 双向迁移 + 重新分类,远贵于 forward
   - 结论:走 forward(扶正 application + 做薄 SDK)而非 reverse(application 撤回 SDK)或 merge(第三模块)

   **三个收紧点**(进 §5.1 boundary table + §5.2 sub-decisions B / C / H):
   - **query**:`sdk/query_runtime.py:14` 直接返回 `EntitySnapshot` / `FieldAssertions`(SDK facade 类型)→ application 必须重建 canonical query DTO,SDK 适配回 outward types,**不能 git mv**
   - **ingest**:`sdk/ingest.py:219` 还在调 `sdk.set/add/retract`,input contract 也是 SDK descriptor 心智 → 必须先抽 application normalized ingest contract,**不能 git mv**
   - **views**:`_SDKViewsManager` 当前只是 in-memory facade,未形成清晰 runtime seam → 留 sdk,本轮不升级到 application

   **Decision 6 实体内容(防回退条款)**(进 §6 Boundaries):
   - 新 runtime 能力默认进入 `application/core`;SDK 只能提供 ergonomic wrapper / compatibility facade
   - 任何新增 runtime 逻辑若直接落入 sdk,必须在 blueprint / audit log 中显式说明理由
   - 违反此约束的 PR 不得 merge,直到 audit log 补记
   - **Why**:Decision 1 锁了 position stake,但没锁后续行为的默认入口。没有此条防回退条款,半年后 SDK 又会重新长成 god files。

   **Trap 6**(进 §6 Boundaries trap checklist):
   - query / ingest 等 SDK runtime helper 不允许 `git mv` 搬迁到 application
   - 必须先在 application 定义 canonical contract / DTO / error model,SDK 适配为 outward facade
   - 反例:`sdk/query_runtime.py:14`(返回 SDK facade types)、`sdk/ingest.py:219`(调 `sdk.set/add/retract`)

   **T1 / T6 / T9 fold 为 §5.2 sub-decision K**:
   - K.1:Query 缺 id / version(asymmetry vs Rule / Derivation)
   - K.2:where validation 时机不一致(Rule / Derivation lazy,Query eager)
   - K.3:Derivation 三个 head 字段(head / target / head_vars + `_heads` 私有)
   - **Why fold 而非 shelve**:Query 会进入 application contract 设计,K.1 / K.2 不能完全 shelve;K.3 影响 evaluate / accept contract 设计
   - **Why 不本轮硬修 primitive 语义**:本轮硬修会把 runtime authority cleanup 变成 primitive semantics cleanup,scope 超
   - **处理方式**:仅作 application runtime contract 设计**约束**记录;除非 query / evaluate 迁移必须触碰,实现留给后续 primitive-contract blueprint
   - **影响**:§5.2 K 行 pre-scoping default 锁定为"约束记录,不本轮实现"

7. **Decision phase pass 1:B+C+D contract design**

   按 §5.3 推荐顺序,先收口 contract,暂不拆 god files、不迁 service/agent、不改代码。

   **B Query contract**:
   - **Why**:`sdk/query_runtime.py` 直接 import / 返回 `EntitySnapshot` 与 `FieldAssertions`,如果原样迁入 application,只是把 SDK facade 语义换目录。
   - **Decision**:application 新增 SDK-independent query request/result DTO + executor。输入包含 query id/version(or digest)、where IR、select vars、return contract、missing/type-mismatch policy、registry;输出 canonical rows,entity slot 使用 application `EntitySnapshotDTO` / `FieldAssertionsDTO`,不得返回 SDK facade types。
   - **SDK responsibility**:SDK `Query` DSL、`row_format`、`return_mode="instance"` 留 product surface;SDK adapter 负责 Query → application request 与 application result → outward `dict` / `EntitySnapshot` / instance。
   - **Non-goal**:不在本轮补 Query primitive id/version 稳定语义(K.1),但 application request 预留字段,避免之后再破 contract。

   **C Ingest contract**:
   - **Why**:`sdk/ingest.py` 仍通过 `sdk.set` / `sdk.add` / `sdk.retract` 闭环写入,说明 write choreography 归属仍在 SDK。
   - **Decision**:application 新增 normalized ingest request/result DTO + executor。`set` / `add` item 使用 `FieldPath` + encoded target ref + application value/meta;`retract` item 使用 assertion id。dedup、skipped、warnings、diagnostics / collect-and-stop 语义归 application。
   - **SDK responsibility**:SDK `ingest(data=...)` 继续接受现有 descriptor 心智,只做 adapter:SDK `Field` → `FieldPath`,SDK value → application value,application result → 现有 `IngestResult`。
   - **Non-goal**:不全面 PROV 化,不把 ingest 做成 package/import 产品,不顺手修 ledger ingest atomicity。provenance validation 只保留现有 `derivation_v1` 最小字段语义。

   **D Derivation / evaluate / accept owner**:
   - **Why**:当前 `SDKStore.evaluate` 主要承担 authoring payload lowering + compiled plan orchestration;底层算法已在 core `evaluate_store` / `Store.accept`。
   - **Decision**:application 接管 compiled derivation plan(s) 的 evaluate / accept orchestration,返回 core `CandidateSet` / `AcceptResult`;core 继续是算法与 ledger owner。
   - **SDK responsibility**:SDK 继续接受 `Derivation` object / authoring payload / keyword sugar,并 lower 成 compiled plan(s)。`view` / `temporal_view` rejection、multi-head shared `run_id` outward 行为、accept keyword sugar 留 SDK adapter。
   - **Non-goal**:不重写 core evaluate / accept 算法;不修 primitive head 三形态(K.3),但 application compiled plan contract 必须显式容纳 `head` 与 `target_pred_id/head_vars` 两条路径。

8. **Decision phase pass 2:A/E/F/G/H/I/J owner + compatibility scoping**

   **A SDKStore / batch / facade split**
   - **Why**:Round 2 code check shows SDK already partially uses application,so the implementation should complete partial migration without moving SDK outward classes into application.
   - **Decision**:`SDKStore` / `SDKBatchTx` / `EntitySnapshot` / `EntityEditor` / `FieldAssertions` remain SDK outward facade. Runtime-bearing slices move behind application contracts from B/C/D. `test_sdk_batch_application_delegate.py` must stop asserting `_application_*` private fields and switch to outward behavior.
   - **Non-goal**:No wholesale `store.py` / `batch.py` / `facade.py` move;no algorithm rewrite.

   **E Errors**
   - **Why**:Not all user-visible errors imply application ownership. Snapshot/editor lifecycle errors are tied to SDK outward objects unless those objects move.
   - **Decision**:Three-way split:SDK/product-domain errors stay SDK;`EntityNotFoundError` / `CardinalityError` are runtime-visible candidates for application owner or DTO shape;`FrozenSnapshotError` / `EditorClosedError` stay SDK unless snapshot/editor ownership changes. SDK aliases may preserve imports.

   **F Registry**
   - **Why**:`SDKRegistry` wraps authoring registry APIs and SDK DSL payload conversion;no `RegistryProtocol` exists today.
   - **Decision**:`SDKRegistry` stays SDK. application contracts accept compiled/runtime-normalized inputs or core registry objects,not `SDKRegistry`. Any shared registry abstraction is a later authoring/registry blueprint.

   **G Package export / run**
   - **Why**:Current SDK methods are thin wrappers around adapter export/run;service runtime calls adapters directly. Package export/run are delivery/tooling surfaces,not Python runtime authority.
   - **Decision**:Keep canonical owner in adapters/service delivery. SDK wrappers may remain compatibility convenience;J/OS-prep #11 decides docs status(stable vs advanced compatibility vs deprecated).

   **H Views**
   - **Why**:`_SDKViewsManager` is local in-memory name registry;`ViewSpec` itself already belongs to core.
   - **Decision**:Named view manager stays SDK. application may accept normalized `ViewSpec`,but does not own named-view registry.

   **I service / agent imports**
   - **Why**:Measured production import surface is already low;rewriting tests for purity would create churn without runtime authority value.
   - **Decision**:No broad migration. Production runtime imports from SDK remain disallowed;the one production `compile_schema_from_classes` use is authoring helper and allowed. Tests may continue using SDK fixtures while new runtime tests cover application path.

   **J Compatibility**
   - **Why**:OS publish makes top-level SDK imports a practical contract even if v0.1 is not stable.
   - **Decision**:`kernel.sdk.__all__` remains product-surface only,plus explicit compatibility aliases for user-visible errors if needed. Do not re-export application internals from SDK. Document canonical owner when aliases exist.

9. **Implementation branch shape audit pass 1:B+C+D file shape**

   在进入生产代码前,先把实际 file shape 与 commit boundary 写回 blueprint,避免把 commit 1 做成半迁移半重构。

   **Code evidence**:
   - `application/protocol/entity_read.py` / `entity_write.py` / `schema_runtime.py` / `common.py` 已提供 read/write/ref/diagnostics primitives,新增 query / ingest / derivation protocol 必须复用这些基础 DTO。
   - `sdk/query_runtime.py` 当前 executor 接 SDK `QueryPlan` / `ReturnContractEntry`,并返回 SDK `EntitySnapshot` / `FieldAssertions`;application query contract 必须只接 `where_ir` 与 SDK-independent return-slot shape。
   - `sdk/ingest.py` 当前 validation/coercion 绑定 SDK `Field` descriptor,写入闭环走 `sdk.set/add/retract`;application ingest contract 只能接 normalized items,SDK descriptor parsing 留 adapter。
   - `SDKStore.evaluate(...)` 当前混合 SDK lowering 与 compiled plan orchestration;application derivation runtime 只接 compiled plans,SDK `Derivation` DSL / keyword sugar 留 adapter。

   **Decision**:
   - commit 1 只新增 application protocol / executor surface + narrow exports,不切 SDK god files。
   - commit 2 再切 SDK adapters,并用 `python -c "from kernel.sdk import *"` 与 outward behavior tests 证明 public API 稳定。
   - 若 implementation 发现 application protocol 必须接 SDK-only type,先更新 blueprint/audit,不得以 convenience 为由突破 runtime authority boundary。

### 未决问题(scoping 时讨论)

- §5.2 A-J 已完成 scoped pass;K 已作为 B+D 的设计约束记录,实现留后续 primitive-contract blueprint
- 实现期仍需为 B/C/D/A 写具体 module split 文件清单与 PR commit boundary;若发现 F/G/H 必须进入 application,先更新 blueprint/audit
- E(errors) 已有三档归属,但实现期仍需逐类选择 alias vs subclass vs DTO error mapping,不得改变 outward error code 字符串
- §5.3 推荐起步顺序已调整为 B+C+D contract design → A 拆分 → I import reaffirm → E errors → J+G compatibility → F+H灰区
- Acceptance(§7)/ Implementation Plan(§8)/ Docs To Update(§9)已填 pass 1 + pass 2 首批内容;后续 implementation phase 再填 Outcome / Deviations

### Decision 13 — out-of-scope SDK consumers after §5.2 I close

- `src/domains/ecss/sdk_helpers.py` production-imports `SDKStore` / `SDKStoreError` and uses SDKStore as a domain ergonomic facade while performing writes through core write protocol. This is outside §5.2 I, which is limited to service / agent consumers, and remains consistent with the audit-delivery contract boundary.
- `src/kernel/adapters/pyreason/runner.py` and `src/kernel/adapters/pyreason/rule_ext.py` production-import SDK DSL types(`Rule`, `LogicVar`, `HeadCall`, `PredAtom`, `Pred`). These DSL classes are currently sole-owned by SDK; the adapter coupling is a primitive-contract issue, not a service / agent runtime authority issue.
- Disposition:do not fix in this cleanup blueprint. Record as a future K(primitive contract traps) hook, likely solved by moving lower-level DSL primitives to core/authoring or by introducing a runtime protocol that adapters can consume without importing SDK product-surface modules.

### Decision 14 — implementation complete and close-out facts

- Commit chain implemented:
  - commit 1:application protocol / executor surface pure add(query / ingest / derivation)
  - commit 2a:application parity fixes(no SDK changes)
  - commit 2b:derivation SDK adapter switch + batch delegate test rewrite
  - commit 2c:query SDK adapter switch + SDK query policy tests
  - commit 2d:ingest SDK adapter switch with identity-cache fallback
  - commit 3:service/agent SDK production import boundary guard
  - commit 4:docs alignment + blueprint implemented status
- Outcome snapshot:
  - application:15 files / 3385 LOC / 29 public symbols
  - `sdk/query_runtime.py`:357 -> 297 lines after adapter rewrite and dead-code removal
  - `sdk/ingest.py`:598 -> 797 lines due application delegate + identity-cache fallback + legacy fallback
  - validation baseline:1093 tests across 5 segments
- Deviations intentionally accepted:
  - SDK god file physical split deferred;runtime delegation completed,but `sdk/store.py` / `sdk/batch.py` / `sdk/facade.py` remain large outward facade files
  - full exception hierarchy rewrite deferred;application uses DTO/error shape for runtime paths and SDK product-domain errors remain SDK-owned
  - CI import-boundary gate deferred to OS-prep #8;unittest/pre-flight guard exists in `test_sdk_consumer_boundary.py`
- K primitive-contract traps remain deferred:
  - Query id/version asymmetry
  - where validation timing differences
  - Derivation head/target/head_vars normalization
  - PyReason adapter coupling to SDK DSL primitives
- OS-prep unblock signal:
  - Runtime-authority implementation no longer blocks OS-prep #2 PyPI policy, #7 OpenAPI yaml or #11 README OS framing.
  - OS-prep files are intentionally not modified in this commit;unblock should be recorded by a separate OS-prep patch.

### 执行约束(继承自 namespace-split blueprint)

- 工程 trap checklist:见 §6 Boundaries
- archived blueprints 一字不改
- 1023 tests 不可回退
- Bash tool 实际是 zsh,所有循环用 `while IFS= read -r f`
- macOS BSD sed 不支持 `\b`
- 4-commit squashable stack + PR + merge 模式;commit 2 必须是 pure refactor with stable public API,并通过 `python -c "from kernel.sdk import *"` 与 import-graph diff
- pre-flight git status clean(开 branch 前)

### OS-prep blueprint 关系

- OS-prep blueprint(`docs/blueprints/active/2026-04-27_oss-prep-v0.1.md`)scoped phase implementation 已 hold(见其 audit log Decision 11)
- 本 blueprint implemented 后,先回 OS-prep 未 scoped 的 #2 PyPI policy / #11 README OS 形态;已 scoped 的 #1 single dist / #3 4 namespaces public / #6 PyReason license / #9 repo cleanup 与本 cleanup 正交
- 本 blueprint 不允许偷渡 OS-prep 范围内的工作(LICENSE / 包名 / CI gate / OpenAPI / etc.)
