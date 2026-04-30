# Task Blueprint: Runtime Authority Cleanup (sdk ↔ application)

- Status: implemented
- Created: 2026-04-28
- Last Updated: 2026-04-28
- Related Modules:
  - `src/kernel/sdk/`(当前 runtime authority + ergonomic facade 混合;含 god files `batch.py 1838` / `store.py 1499`)
  - `src/kernel/application/`(当前 partial canonical Python runtime + 部分 protocol)
  - `src/service/`(当前依赖 SDK + application 混合,本 blueprint 后改为依赖 application)
  - `src/agent/`(也消费 SDK + application;依赖方向需重审)
- Related Docs:
  - [docs/blueprints/active/2026-04-27_oss-prep-v0.1.md](./2026-04-27_oss-prep-v0.1.md)(OS-prep blueprint,scoped phase 因本 blueprint hold)
  - [docs/blueprints/archive/2026-04-27_kernel-namespace-split.md](../archive/2026-04-27_kernel-namespace-split.md)(namespace 已稳定,本 blueprint 在此基础上整理 layer 责任)
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/bridges/factpy-kernel-report-audit-2026-04-20.md](../../references/bridges/factpy-kernel-report-audit-2026-04-20.md)(audit 报告点名 god files / 边界靠自律)
- Audit Log:
  - [2026-04-28_runtime-authority-cleanup.audit.md](./2026-04-28_runtime-authority-cleanup.audit.md)

## 1. Problem

namespace split(2026-04-27 commit `81c6f77`)把 4 个 packages 边界划清,但 **kernel 内部 sdk ↔ application 的 runtime authority 仍模糊**。当前是用户 framing 中最差的 option 3:两层并存,各自一半 authority,所有边界模糊。

具体症状:

- `kernel/sdk/` 既是**用户 ergonomic API**(Entity / Field / Identity / DSL builder)又是 **runtime authority**(SDKStore.evaluate / batch / store / facade)
- `kernel/application/` 也是 partial runtime(entity_view / entity_write / schema_runtime / protocol/)
- 已存在 `test_sdk_batch_application_delegate.py` / `test_sdk_facade_application_delegate.py` —— SDK partially delegates to application,但**公开 API 仍以 SDK 为准**,delegation 是隐藏实现细节
- `service` / `agent` 依赖混合(SDK + application),不清楚谁是 canonical
- 新 runtime 能力默认加到 SDK(因为"方便用"),进一步扩 SDK god files

**OS publish 是 deadline**:OS v0.1 publish 瞬间 SDK 公开 surface = v0.1 contract。若 v0.2 才动 runtime authority,SDKStore.evaluate / batch / 等每个 API 都是 breaking change + 6-12 月 deprecation cycle。**修这件事的窗口只有 OS v0.1 publish 前**。

本 blueprint 的目标是:把 runtime authority 从 SDK 迁到 application,SDK 改成 thin product surface,使 OS v0.1 publish 时 SDK contract 已经是干净的 ergonomic facade。

**Measured Facts**(2026-04-28 code survey,确认成本曲线):

- **`application -> sdk` 反向依赖 = 0**(application 模块不 import 任何 sdk;升格无需 untangle 反向引用)
- **`sdk -> application` 已存在**,集中在 runtime-bearing 文件:`sdk/store.py` / `sdk/batch.py` / `sdk/facade.py`(增量推进,不是从零起步)。这次 cleanup 的 framing 是 **complete partial migration**,不是 fresh contract design from scratch:
  - `sdk/batch.py` 已 import `apply_write_plan` / `plan_write_command` / application protocol DTO,`BatchPlan` 已持有 `_application_plans_by_handle_id: dict[int, EntityWritePlan]`
  - `sdk/facade.py` 已 import `execute_read_request` / `hydrate_entity` / `EntitySnapshotDTO` / `FieldAssertionsDTO`
  - `sdk/store.py` 已用 `build_schema_index(...)` 建 application schema index
  - `application/protocol/{common,entity_read,entity_write,schema_runtime}.py` 已存在一组可复用 DTO / error shape
- **`application` 主 runtime 文件 3 个,public symbols 21**:`application/schema_runtime.py` / `application/entity_view.py` / `application/entity_write.py`(已是干净小模块,升格成本低)
- **SDK god / runtime files 行数**:`sdk/batch.py 1838` / `sdk/store.py 1499` / `sdk/facade.py 927` / `sdk/ingest.py 598` / `sdk/query_runtime.py 357`(混合 runtime impl + ergonomic surface,需拆分)

成本曲线证明:**继续 forward(扶正 application + 做薄 SDK)显著便宜于 reverse(把 application runtime 撤回 SDK 或合并第三个新模块)**。本 blueprint 走 forward 路线。

## 2. Goals

- **Position 落地**:`application` = canonical Python runtime authority;`sdk` = product surface(ergonomic API / DSL / authoring shell);`service` 依赖 application 而非 SDK;新 runtime 能力默认进 application/core,SDK 包 ergonomic wrapper
- **god files 拆分作为前置子任务**:`sdk/batch.py 1838` / `sdk/store.py 1499` / 可能 `sdk/facade.py` 不能整块搬到 application(否则 application 接 god files);先在 SDK 内拆 ergonomic surface vs 真正 runtime impl,再把 runtime impl 搬到 application
- **service 依赖收紧**:`service/` 的 import 全部审一遍;runtime ops 改用 application 接口;SDK 仅在确实需要 ergonomic 形态时引用
- **agent 依赖收紧**:同 service,agent 也走 application(若调用 runtime 而非 ergonomic 形态)
- **delegation tests 重新评估**:`test_sdk_*_application_delegate.py` 系列测试当前测的是"SDK 调 application",cleanup 后这层 delegation 仍存在(SDK facade 调 application);测试 still valid 但语义可能需更新(从"hidden implementation detail"变"explicit facade pattern")
- **1023 tests 仍全绿**
- **kernel 内文档同步**:application docs 升级为 canonical runtime contract 描述;SDK docs 改为 ergonomic / authoring 描述
- **不阻塞 OS-prep**:本 cleanup 主要影响 OS-prep 尚未 scoped 的 #2 PyPI policy 与 #11 README OS 形态;与已 scoped 的 #1 single distribution / #3 4 namespaces public / #6 PyReason license / #9 repo cleanup 正交

## 3. Non-goals

- **不**改 kernel namespace 结构(4 packages 已稳定,不再动)
- **不**做 OS-prep 范围内的工作(LICENSE / 包名 / CI gate / OpenAPI / etc. 都留给 OS-prep)
- **不**加新 feature(extraction precision、agent capabilities 等)
- **不**碰 god files 内部业务逻辑 —— 只做 ergonomic-vs-runtime 拆分,不做语义改动
- **不**做 D2(language-agnostic minimal engine)演进 —— 那是另一条 blueprint;本轮只整 Python layer 内的 authority,但 application DTO 命名应避免把后续 D2 路径彻底堵死
- **不**冻结 SDK 公开 API —— v0.1 是 "试水",API surface 不承诺 stable

## 4. Current Context

- **HEAD**:`81c6f77`(namespace-split squash merge);新分支待建(暂定 `runtime-authority-cleanup`,从 master 起)
- **Test 基线**:1023 tests 全绿(分 5 个目录;namespace-split 后建立)
- **CI 基线**:已修(commit `30a29b0`),5 段 unittest discover + 全 extras install
- **SDK 现状**(`src/kernel/sdk/`,15 .py 文件 + dsl/ + docs/):
  - **Ergonomic / authoring surface**:`schema.py 421` (`Entity` / `Field` / `Identity` / `Relationship` schema builder);`vars` / `Body` / `Pred` / `Rule` / `Derivation` / `Query`(DSL,在 `dsl/` 内);`compile.py`(class world → schema IR);`registry.py 226`(`SDKRegistry` authoring-adjacent facade);`errors.py` / `error_codes.py`(outward SDK exception/error-code surface,具体 runtime error origin 见 §5.2 E)
  - **Runtime impl(应迁出)**:`SDKStore`(`store.py 1499`)/ `batch.py 1838` / `ingest.py` / `facade.py` / `query_runtime.py` / `query_lower.py`
  - **god files**:`batch.py 1838` / `store.py 1499`(audit 报告 2026-04-20 点名)
- **Application 现状**(`src/kernel/application/`):
  - `entity_view.py` / `entity_write.py` / `schema_runtime.py` / `protocol/`(entity_read / entity_write / schema_runtime / common 协议)
  - 已 partial canonical runtime;但缺少 query / batch / ingest / facade 对应面
- **Delegation tests 现状**:
  - `src/kernel/tests/test_sdk_batch_application_delegate.py`
  - `src/kernel/tests/test_sdk_facade_application_delegate.py`
  - 验证 SDK 已 partially 通过 application 实现;cleanup 后变为"SDK facade 显式调 application"
- **service / agent 依赖现状**(2026-04-28 `rg "from kernel\.sdk|import kernel\.sdk" src/service src/agent`):
  - 除 `src/agent/extraction/docs/USAGE.md` 的 markdown example 外,现状是 **13 import lines / 9 files**
  - production 仅 1 行:`src/agent/extraction/api.py` 使用 `compile_schema_from_classes`(authoring helper)
  - 其余 12 行在 service / agent tests,多为 `SDKStore` / schema / DSL fixtures
  - 结论:方向大致已对;I 的工作主要是 reaffirm + 个别小调,不是大规模 consumer migration
- **5 工程 trap**(继承 namespace-split lessons,记录在 `~/.claude/.../memory/feedback_refactor_execution_traps.md`):
  - Bash tool 实际是 zsh,`for f in $VAR` 不 word-split → 用 `while IFS= read -r f`
  - macOS BSD sed 不支持 `\b` word boundary
  - Pre-flight 命令必须实际执行 + 输出验证
  - 搬走 X.py 必扫源 package 的 `__init__.py` re-export
  - 跨包搬迁文件相对 import 必须改绝对
- **OS-prep 依赖**:本 blueprint hold OS-prep blueprint 的 scoped phase implementation;cleanup implemented 后主要 unblock #2 PyPI policy 与 #11 README OS 形态,其余已 scoped 决议不反向依赖 SDK/application 内部拆分

## 5. Proposed Shape

> **此处内容是 scoped / decision-phase 形态**:核心 position 与边界已 stake,但具体迁移粒度 / 拆分策略 / 顺序 / 测试影响仍需在 decision phase 逐项收口。

### 5.1 已 stake 的 position

| 维度 | 决议 |
|---|---|
| Runtime authority | `application` |
| Product surface(ergonomic / DSL / authoring) | `sdk` |
| Service 依赖 | `application`(SDK 仅在 ergonomic 场景) |
| Agent 依赖(runtime ops) | `application` |
| 新 runtime 能力默认归属 | `application/core` 先,SDK 包 wrapper |

**模块级归属表**(2026-04-28 v2 patch;基于 code survey 落地;灰区项见 §5.2):

| 类别 | 必须留 SDK | 必须进 application | 灰区(待 §5.2 决议) |
|---|---|---|---|
| Schema authoring | `Entity` / `Field` / `Identity` / `Relationship` | — | — |
| Rule / Derivation / Query DSL | `Rule` / `Derivation` / `Query` / `Body` / `Pred` / `vars` / `RuleRef` | — | — |
| Compile helpers | `sdk/compile.py`(class world → schema IR) | — | — |
| Outward Python facade | `SDKStore` / `SDKBatchTx` / `EntitySnapshot` / `EntityEditor` / `FieldAssertions`(改薄) | — | — |
| Schema runtime | — | `application/schema_runtime.py`(已在) | — |
| Entity read/write runtime | — | `application/entity_view.py` / `application/entity_write.py`(已在) | — |
| Query runtime | — | canonical query DTO / result(**重建,非 git mv** — 详 §5.2 B) | — |
| Ingest runtime | — | normalized ingest contract(**重建,非 git mv** — 详 §5.2 C) | — |
| Evaluate / accept / explain | — | runtime orchestration(从 SDKStore 抽出 — 详 §5.2 D) | 公开 API 形态(K.3 head 字段约束作输入) |
| Errors | — | runtime error 原类 | SDK re-export 兼容范围(详 §5.2 E + J) |
| Registry | `SDKRegistry` 留 sdk | — | `RegistryProtocol` 抽象接口归属(详 §5.2 F) |
| Package export / run | — | — | service / tools 调用面后定(详 §5.2 G) |
| Views(`_SDKViewsManager`) | 留 sdk(in-memory facade,未形成 runtime seam) | — | 是否升级到 application(详 §5.2 H) |

### 5.2 子决策 / scoping log

> v2 patch(2026-04-28):基于 code survey,把原来 A-J 的泛化决策项重写为更具体的 sub-decisions,并新增 K(primitive contract traps)。未 scoped 项带 pre-scoping default;已 scoped 项标明对应 decision pass。

| # | 决策项 | 输入 / 待决候选 | Default / scoped status |
|---|---|---|---|
| A | SDKStore / batch / facade 拆分边界(含 delegation tests 重写) | `sdk/batch.py 1838` / `sdk/store.py 1499` / `sdk/facade.py 927` 内 ergonomic API vs runtime impl 划分;`test_sdk_batch_application_delegate.py` 当前断言 `_application_*` 私有字段,`test_sdk_facade_application_delegate.py` 已主要测 outward behavior | **Scoped:见 §5.2.2**;拆分,不整块搬;ergonomic 留 sdk,runtime 进 application;tests 从"hidden delegation"改为"explicit facade pattern",禁止继续断言 `_application_*` 私有字段,改测 outward 行为 |
| B | Query contract 重建 | application canonical query DTO / result / executor 形态;SDK 适配回 `EntitySnapshot` / `FieldAssertions`;policy(missing / type-mismatch) | **Scoped:见 §5.2.1**;重建 contract,不能 git mv `sdk/query_runtime.py 357`;application 不返回 SDK facade types |
| C | Ingest contract 重建 | application normalized ingest contract;provenance / dedup / warnings;SDK 适配 descriptor 心智;`sdk/ingest.py` 写入路径调 `sdk.set` / `sdk.add` / `sdk.retract` 拆解 | **Scoped:见 §5.2.1**;重建 contract,不能 git mv `sdk/ingest.py 598`;application 拥 raw,SDK 包 outward |
| D | Derivation / evaluate / accept runtime owner | runtime orchestration 从 SDKStore 抽出 → application;K.3 三个 head 字段(head / target / head_vars + `_heads` 私有)作为 contract 设计**约束** | **Scoped:见 §5.2.1**;进 application;K.3 在本轮不修 primitive 语义,仅记录约束 |
| E | Errors 体系归属 | runtime error 原类归属;SDK 是否 re-export(及范围)。输入清单:`SDKError` / `SDKSchemaError` / `SDKStoreError` / `SDKRegistryError` / `SDKDSLError` 是 SDK/product-domain errors;`EntityNotFoundError` / `CardinalityError` 是 runtime-visible 候选;`FrozenSnapshotError` / `EditorClosedError` 当前由 SDK facade/editor 触发,需逐类判断 | **Scoped:见 §5.2.2**;application 拥 runtime-visible error 原类或 DTO error shape;SDK re-export 用户可见错误类。默认保留 SDK/product-domain errors 在 SDK;`EntityNotFoundError` / `CardinalityError` 优先评估迁 application;`FrozenSnapshotError` / `EditorClosedError` 只有在对应 snapshot/editor runtime 责任迁出时才迁 |
| F | Registry owner | `SDKRegistry` 当前在 sdk;`RegistryProtocol` 抽象接口归属;接入面 | **Scoped:见 §5.2.2**;`SDKRegistry` 留 sdk;本 cleanup 不新增 `RegistryProtocol`。application contract 接 compiled runtime inputs,不是 SDK registry object |
| G | Package export / run owner | `export_package` / `run_package` runtime owner;service / tools 调用面 | **Scoped:见 §5.2.2**;adapter/service delivery owner 保持现状;SDKStore wrappers 是 compatibility convenience,不作为 canonical runtime authority |
| H | Views owner | `_SDKViewsManager` 是否升级到 application | **Scoped:见 §5.2.2**;留 sdk(in-memory named-view facade);`ViewSpec` 值对象继续来自 core,application 可接 normalized view value 但不拥有 named-view registry |
| I | service / agent 依赖切换 | service / agent 内每个 `from kernel.sdk` 的去向;envelope 契约是否受影响。实测:13 Python import lines / 9 Python files excluding markdown;plus 1 markdown example。production 仅 `src/agent/extraction/api.py` 的 `compile_schema_from_classes`,其余 12 行是 tests | **Scoped + verified**(commit 3 boundary guard);runtime ops 不得新增 SDK production import;当前唯一 production import 是 authoring helper。域外 SDK consumers(`domains/ecss/sdk_helpers.py`,`kernel/adapters/pyreason/*`)超 §5.2 I scope,见 audit Decision 13 |
| J | Compatibility strategy(SDK 旧 import paths) | 保留 re-export 的范围 + deprecate 周期;OS v0.1 publish 前是否清干净 | **Scoped:见 §5.2.2**;SDK top-level exports 保留 product surface;不 re-export application internals。迁出的用户可见 runtime errors 可通过 SDK aliases 兼容;export/run wrappers 与 G 同期标注 stable/deprecated |
| K | Rule / Query / Derivation primitive contract traps | K.1 Query 缺 id / version(asymmetry vs Rule / Derivation);K.2 where validation 时机不一致(Rule / Derivation lazy,Query eager);K.3 Derivation 三个 head 字段(head / target / head_vars + `_heads` 私有) | 仅作 application runtime contract 设计**约束**记录;除非 query / evaluate 迁移必须触碰,实现留给后续 primitive-contract blueprint |

#### 5.2.1 Decision phase pass 1:B + C + D contract design(scoped)

本轮只收口 contract 形状,不实施代码迁移。原则:application 接收 **runtime-normalized payload**,不接收 SDK DSL / facade objects;SDK 保留 outward ergonomic API 与兼容 adapter。

重要 framing:这是 **complete partial migration**,不是 fresh design。现有 application protocol 已提供 `EntitySnapshotDTO` / `FieldAssertionsDTO` / `EntityWritePlan` / `ErrorDTO` / `WarningDTO` / `FieldPath` / `EntityRef` 等基础形状;SDK `batch.py` / `facade.py` / `store.py` 已局部持有或调用这些 application contracts。B+C+D 设计阶段要复用并补齐这些 seam,避免重复发明第二套 DTO。

| 决策项 | Scoped contract | SDK 责任 | 不在本轮修 |
|---|---|---|---|
| B Query contract | application 新增 canonical query protocol + executor。输入是 SDK-independent query runtime request:query id/version(or digest),where IR,select vars,return contract,missing/type-mismatch policy,registry。输出是 canonical query result rows,entity slot 使用 `EntitySnapshotDTO` / `FieldAssertionsDTO` 等 application DTO,不得返回 SDK `EntitySnapshot` / `FieldAssertions`。 | SDK `Query` / `row_format` / `return_mode="instance"` 仍是 product surface。SDK adapter 负责把 `Query` 降成 application request,把 application result 适配回现有 outward `dict` / `EntitySnapshot` / instance 形态,并保留现有 error code 语义。 | 不把 `sdk/query_runtime.py` 原样搬入 application;不在本轮补 Query primitive id/version 稳定语义(K.1),只让 application request 为后续 id/version 预留字段。 |
| C Ingest contract | application 新增 normalized ingest protocol + executor。输入是 SDK-independent ingest items:`set` / `add` 用 `FieldPath` + encoded target ref + application value/meta;`retract` 用 assertion id。输出是 structured result DTO(写入 ids / skipped / duplicate / warnings / diagnostics),dedup 与 collect-and-stop 语义归 application。 | SDK `ingest(data=...)` 继续接受现有 descriptor 心智(`field` 为 SDK `Field`,`e_ref` 字符串等),只做 adapter:field → `FieldPath`,SDK value → application value,application result → 现有 `IngestResult`。 | 不全面 PROV 化;不把 ingest 变成 package/import 产品;不顺手修 ledger ingest atomicity。provenance validation 只保留现有 `derivation_v1` 最小字段语义;authoring artifact format / schema migration 与完整 provenance model 另开 blueprint。 |
| D Derivation / evaluate / accept owner | application 新增 derivation runtime orchestration:接收 compiled derivation plan(s),调用 core `evaluate_store` / `Store.accept` / `Store.accept_many`,返回 core `CandidateSet` / `AcceptResult`。application 是 compiled runtime owner;core 仍是算法与 ledger owner。 | SDK 继续接受 `Derivation` object / authoring payload / keyword sugar,并负责 lower 成 compiled plan(s)。`view` / `temporal_view` rejection、multi-head shared `run_id` outward 行为、accept keyword sugar 保持在 SDK adapter。 | 不重写 core evaluate / accept 算法;不修 primitive head 三形态(K.3),但 application compiled plan 必须显式容纳 `head` 与 `target_pred_id/head_vars` 两条路径,避免迁移时压平语义。 |

**B+C+D 共同边界**:

- application 新增模块不得 import `kernel.sdk.*`;验证命令:`rg "kernel\\.sdk|from \\.sdk|from kernel\\.sdk" src/kernel/application`
- SDK adapter 可以 import application,但 adapter 之外不再新增 runtime authority
- application protocol DTO 使用 dataclass + `ProtocolShapeError` 风格,沿用 `protocol/common.py` 的 `ErrorDTO` / `WarningDTO` 形态
- query / ingest error code 需要保持 outward compatibility;原 SDK exception 是否 re-export 属于 E/J 收尾决策
- implementation phase 前不新增第三个 runtime package;若发现 contract 需要抽 shared authoring lowerer,优先放 `kernel.authoring` 或保持 SDK adapter,不得绕回 SDK runtime authority

#### 5.2.2 Decision phase pass 2:A + E + F + G + H + I + J scoping(scoped)

本轮收口 B+C+D 之后的拆分、兼容与灰区 owner。原则:不新增第三个 runtime package,不把 adapter/service delivery 能力误归为 application runtime authority,也不把 SDK outward lifecycle objects 过早迁出。

| 决策项 | Scoped decision | Rationale / evidence | 不在本轮修 |
|---|---|---|---|
| A SDKStore / batch / facade 拆分 | `SDKStore` / `SDKBatchTx` / `EntitySnapshot` / `EntityEditor` / `FieldAssertions` 继续是 SDK outward facade。runtime-bearing slices 按 B/C/D target surface 抽入 application:query executor、normalized ingest executor、compiled derivation evaluate/accept orchestration、entity read/write already-partial delegates。`sdk/store.py` 最终只组合 schema authoring、facade methods、compat wrappers 与 outward errors。`sdk/batch.py` 保留 staging / wire / ergonomic handle UX,application 承接 write-plan execution。`sdk/facade.py` 保留 outward snapshot/editor classes,application 承接 read DTO hydration. | `batch.py` 已持有 `EntityWritePlan`;`facade.py` 已调用 `execute_read_request` / `hydrate_entity`;`store.py` 已持有 application schema index。拆分是 completing partial migration。`test_sdk_batch_application_delegate.py` 当前断言 `_application_*` 私有字段,需改 outward behavior tests。 | 不整块搬 `store.py` / `batch.py` / `facade.py`;不改算法语义;不把 SDK outward class 名字迁入 application。 |
| E Errors | 三档归属:1) SDK/product-domain 留 SDK:`SDKError` / `SDKSchemaError` / `SDKStoreError` / `SDKRegistryError` / `SDKDSLError`;2) runtime-visible 候选迁 application 或 application error DTO:`EntityNotFoundError` / `CardinalityError`;3) snapshot/editor lifecycle tied errors 条件迁移:`FrozenSnapshotError` / `EditorClosedError` 只有 snapshot/editor ownership 迁出时才迁,本轮默认留 SDK。SDK top-level 可 re-export aliases 保持用户 import 兼容。 | `FrozenSnapshotError` 由 SDK `EntitySnapshot` / assertion namespace read-only 行为触发;`EditorClosedError` 由 SDK editor lifecycle 触发。它们不应被粗暴归为 application runtime errors。 | 不做全局 exception hierarchy rewrite;不改变现有 outward error code 字符串。 |
| F Registry | `SDKRegistry` 留 SDK,作为 authoring-adjacent product facade over `kernel.authoring.FileAuthoringRegistry`。本 cleanup 不新增 `RegistryProtocol`。application runtime contract 接 compiled rule/derivation/query inputs 或 core `RuleRegistry`,不接 `SDKRegistry` object。若未来 service/application 都需要 registry abstraction,另开 authoring/registry blueprint。 | 当前 `SDKRegistry` 主要包装 authoring publish/apply/read APIs,并把 SDK `Rule` / `Derivation` payload 编译成 authoring specs;没有现成 `RegistryProtocol`。强行抽 protocol 会扩大 scope。 | 不迁 `SDKRegistry`;不抽新 protocol;不改 registry storage format。 |
| G Package export / run | `export_package` / `run_package` canonical owner 保持 adapter/service delivery surface:adapter `kernel.adapters.souffle.package.export_package`,runner `kernel.adapters.souffle.runner.run_package`,service `export_runtime_package`。`SDKStore.export_package(...)` / `SDKStore.run_package(...)` 保留 compatibility convenience,但不作为 application runtime authority。J 决议时决定它们在 v0.1 README/API surface 中标 stable、advanced compatibility,还是 deprecate。 | `SDKStore` 当前只是薄 wrapper:`export_package(self._store, ...)` / `run_package(...)`;service/runtime 直接调用 adapter export/run。把它们迁 application 会混淆 runtime authority 与 package delivery。 | 不改 exporter / runner 行为;不更名 output dirs;不把 audit/static delivery塞进 application。 |
| H Views | `_SDKViewsManager` 留 SDK。`ViewSpec` 作为 core value object 继续可被 application read/evaluate contracts 接收,但 named-view registry(`sdk.views.create/update/delete/list`)不升级到 application。 | `_SDKViewsManager` 是 SDKStore-local in-memory name registry;不持久化,也不是跨 consumer runtime seam。 | 不新增 application views registry;不改变 view semantics。 |
| I service / agent imports | production runtime code 不再新增 SDK runtime imports。当前 production 仅 `src/agent/extraction/api.py` 使用 `compile_schema_from_classes`,属 authoring helper,允许保留并登记在 boundary guard allowlist。service production 应保持 0 个 `kernel.sdk` runtime imports;service/agent tests 可继续用 SDK fixtures,但新 runtime-facing tests 优先覆盖 application path。 | 实测为 13 Python import lines / 9 Python files excluding markdown;plus 1 markdown example。production 1 行 authoring helper + 12 行 tests。commit 3 新增 `test_sdk_consumer_boundary.py` 守护 production allowlist。consumer migration 不是主工作量。 | 不为测试纯度重写所有 fixtures;不迁 extraction schema authoring helper;不把域外 consumers(domains/ecss,pyreason adapter)纳入 §5.2 I。 |
| J Compatibility | `kernel.sdk.__all__` 继续表达 SDK product surface,保留 `Entity` / `Field` / `Identity` / `Relationship` / DSL / `SDKStore` / `SDKRegistry` / outward errors / ingest result。不得从 SDK re-export application internals。迁入 application 的用户可见 runtime errors 可用 SDK aliases 保持 import 兼容,并在 docs 中标明 canonical owner。G 的 export/run wrappers 若保留,需在 OS-prep #11 README/API docs 中明确 stable vs advanced compatibility vs deprecated。 | v0.1 不承诺 stable,但 OS publish 会让 top-level imports 形成事实 contract;J 要防止 application internal DTO 被 SDK 当便利出口重新暴露。 | 不在本 cleanup 设计完整 deprecation policy;不删除现有 public imports,除非实现期发现从未文档化且无测试依赖。 |

**Pass 2 共同边界**:

- A/E/J 的目标是保持 outward compatibility,不是扩大 SDK public API。
- F/G/H 默认不进入 application,除非 implementation phase 发现 B/C/D contract 无法不依赖它们;若发生,必须先更新本 blueprint/audit。
- I 的 production import acceptance 用 `rg "from kernel\\.sdk|import kernel\\.sdk" src/service src/agent` 复核;允许项必须逐条解释为 authoring/ergonomic,不是 runtime authority。
- 任何 re-export / alias 都必须有 owner 注释或 docs 说明,防止用户把 compatibility path 误读成 canonical owner。

#### 5.2.3 Implementation shape audit pass 1:B + C + D file shape(scoped)

本轮在 `runtime-authority-cleanup` branch 上只读核验 B(Query) / C(Ingest) / D(Derivation) 相关代码,不改生产代码。结论:implementation phase 的 commit 1 应是 **application contract pure add / narrow export update**,不是从 SDK god files 里搬逻辑。commit 2 以后再把 SDK adapter 切到这些 contracts。

**已存在可复用 application protocol inventory**:

- `src/kernel/application/protocol/entity_read.py`:已有 `EntitySnapshotDTO` / `FieldAssertionsDTO` / `AssertionRecordDTO` / `EntityReadRequest` / `EntityReadResponse`;query entity-slot result 必须复用这些 DTO,不得返回 SDK `EntitySnapshot` / `FieldAssertions`
- `src/kernel/application/protocol/entity_write.py`:已有 `EntityWriteCommand` / `FieldMutation` / `EntityWritePlan` / `EntityWriteResult`;ingest normalized write path 应复用 write-plan primitives,避免发明第二套 write DTO
- `src/kernel/application/protocol/schema_runtime.py`:已有 `EntitySelector` / `EntityRef` / `FieldPath`;query / ingest target refs 与 field refs 应落到这些 application value shapes
- `src/kernel/application/protocol/common.py`:已有 `JSONValue` / `ProtocolShapeError` / `ErrorDTO` / `WarningDTO`;新增 protocol DTO 沿用这一层的 validation / diagnostics 风格

**Commit 1 候选文件集合**(pure add + explicit exports):

| Area | Candidate files | Commit 1 只做 |
|---|---|---|
| Query | `src/kernel/application/protocol/query.py`;`src/kernel/application/query_runtime.py` | 定义 SDK-independent `QueryRuntimeRequest` / row result DTO / executor skeleton。request 接 `where_ir`、return slot contract、missing/type-mismatch policy、optional query id/version;entity result slot 使用 `EntitySnapshotDTO`。不接 SDK `QueryPlan` / `ReturnContractEntry` / `Query` DSL。 |
| Ingest | `src/kernel/application/protocol/ingest.py`;`src/kernel/application/ingest_runtime.py` | 定义 normalized ingest request/result DTO 与 bulk executor seam。`set` / `add` item 复用 `FieldPath` + encoded target ref + application value/meta;`retract` item 使用 assertion id;执行侧复用 `plan_write_command` / `apply_write_plan`。SDK descriptor parsing 不进入 application。 |
| Derivation | `src/kernel/application/protocol/derivation.py`;`src/kernel/application/derivation_runtime.py` | 定义 compiled derivation plan request shape 与 evaluate/accept orchestration seam。plan shape 必须保留 `head` 与 `target_pred_id/head_vars` 两条路径,并支持 multi-head plan list。SDK `Derivation` object / authoring payload lowering 不进入 application。 |
| Exports | `src/kernel/application/protocol/__init__.py`;`src/kernel/application/__init__.py` | 只导出稳定的 application runtime protocol / executor symbols;不得把 SDK compatibility aliases 或 outward facade types 重新暴露出来。 |

**Query shape audit**:

- 当前 `sdk/query_runtime.py` 在 executor 内部做 `lower_query_rule_ast_to_ir(...)`,再调用 `project_view_facts(...)` / `evaluate_native_where(...)` / hydrate。application contract 应接已经 runtime-normalized 的 `where_ir`;SDK adapter 或 future neutral authoring lowerer 负责从 SDK `Query` / `QueryPlan` 产出 `where_ir`。
- 当前 hydrate result 是 SDK `EntitySnapshot` / `FieldAssertions`;application executor 应改为 `EntitySnapshotDTO` / `FieldAssertionsDTO`,SDK adapter 再映射回 outward `EntitySnapshot`、dict row 或 `return_mode="instance"`。
- `query_id` / `version` 只作为 optional contract slots 预留;不在本 blueprint 修 K.1 的 primitive identity 语义。

**Ingest shape audit**:

- 当前 `sdk/ingest.py` 的 validation / coercion 仍依赖 SDK `Field` descriptor、`sdk._schema_pred_for_field(...)`、`sdk._rest_terms_for_field(...)`;这些属于 SDK adapter,不应进入 application。
- 当前写入闭环直接调用 `sdk.retract(...)` / `sdk.set(...)` / `sdk.add(...)`;application ingest executor 应接 normalized items,并在 application 内部落到 existing entity-write plan/apply path。
- result 需要保留现有 `written` / `skipped` / `duplicate` / warnings / diagnostics / collect-and-stop outward semantics;SDK `IngestResult` 可以继续作为 adapter result。

**Derivation shape audit**:

- 当前 `SDKStore.evaluate(...)` 混合了 SDK authoring payload lowering、mode/engine options sugar、compiled plan orchestration、multi-head shared `run_id`、core `evaluate_store(...)` 调用。application 只接 compiled plan(s),不接 SDK DSL object。
- application derivation runtime 应拥有 compiled plan orchestration、multi-plan shared run id、body confidence validation、core `evaluate_store(...)` / `Store.accept(...)` / `Store.accept_many(...)` 调用;SDK 保留 `view` / `temporal_view` rejection、keyword sugar 与 outward compatibility wrapper。
- multi-head regression coverage 仍需新增:single-head via `target=`,multi-head via `head=[HeadCall, HeadCall]`,以及 `_heads` 私有 normalization outward 行为。

**Implementation constraints from this shape audit**:

- commit 1 不修改 `sdk/store.py` / `sdk/query_runtime.py` / `sdk/ingest.py` / `sdk/batch.py` / `sdk/facade.py`,除非仅为 import smoke 暴露 application symbols 所需的 narrow export update
- commit 2 才切 SDK adapter,且必须保持 `python -c "from kernel.sdk import *"` 与现有 SDK outward tests 语义
- 若 implementation 发现 query / ingest 必须复用 SDK-only DSL type,先回到 blueprint/audit 更新 scope,不得把 SDK type 直接带进 application protocol

### 5.3 推荐起步顺序(scoping 时讨论)

> v2 patch(2026-04-28):letters 重映射后调整顺序;原则不变 — design contracts before splitting,split before consumer migration,errors / compat 收尾,灰区最后。

1. **B + C + D contract design**(canonical query / ingest / derivation contract)—— 基于 §5.2.1 已落地的 contract shape recap 与 partial migration inventory(~1,800 LOC 边界面:`query_runtime.py 357` + `store.py`/`facade.py` boundary slices + `application/protocol` 629),不依赖 god file 内部业务逻辑;先勾出 application 公开 API 形态,后续拆分有 target;K.1 / K.2 / K.3 作为输入约束。预估 4-6h design pass,不是 2-4h small audit
2. **A(SDKStore / batch / facade 拆分)**—— 基于 B + C + D 的 contract design,逐文件 dissect SDK god files;含 delegation tests 重写
3. **I(service / agent 依赖切换)**—— A 完成后,external consumers 改 import(以 §4 列出的 `rg` 清单为 evidence)。commit 3 实测无 production runtime migration 需求,并以 `test_sdk_consumer_boundary.py` 守住唯一 authoring-helper allowlist
4. **E(errors 体系归属)**—— A + I 完成后,runtime error class 与 SDK re-export 范围明朗
5. **J + G(publish-facing compatibility)**—— 决定 SDK 旧 import paths、package export / run helpers 是否保留、是否 deprecate、哪些路径标 stable
6. **F + H(灰区)**—— 按 pre-scoping default 收口,或在 cleanup 完成后单独评估

> **Docs 同步贯穿全程**:application docs 升级与 SDK docs 降级**不单列阶段** — 与 contract design(B+C+D)同步 prototype,在 consumer migration(I)同步 finalize;具体清单见 §9 Docs To Update。

## 6. Boundaries And Invariants

- **必须保持**:
  - 1023 tests 仍全绿(`test_sdk_*_application_delegate.py` 可能 rewrite,但总数不可减),且不降低 SDK / application path coverage
  - 4 packages namespace 不动(kernel / agent / service / domains)
  - kernel 内核心语义(core / adapters / audit / authoring / domains)不动
  - OS-prep blueprint 已 scoped 的决策不动(#1 single dist / #3 4 ns public 分层 / #6 PyReason BSD-2 / #9 repo 清理)
- **明确不做**:
  - 不改 god file 内部业务逻辑(拆分只重组 module 结构,不动算法)
  - 不加新 feature
  - 不动 namespace 结构
  - 不冻结 SDK / application 公开 API(v0.1 不承诺 stable)
- **防回退条款(Decision 6,本 blueprint scoped 起生效)**:
  - 新 runtime 能力默认进入 `application/core`;SDK 只能提供 ergonomic wrapper / compatibility facade
  - 任何新增 runtime 逻辑若直接落入 sdk,必须在 blueprint / audit log 中显式说明理由
  - 违反此约束的 PR 不得 merge,直到 audit log 补记
  - **Why**:Decision 1 锁了 position stake,但没锁后续行为的默认入口。没有此条防回退条款,半年后 SDK 又会重新长成 god files。
- **工程 trap checklist**(执行期遵守):
  - 用 `while IFS= read -r f`,**不要** `for f in $VAR`
  - macOS BSD sed 不依赖 `\b` word boundary
  - Pre-flight 命令实际执行 + 输出验证
  - 搬迁文件必扫源 package `__init__.py` re-export
  - 跨包搬迁文件相对 import 必须改绝对
  - **Trap 6**(query / ingest 迁移特别约束):query / ingest 等 SDK runtime helper **不允许** `git mv` 搬迁到 application。必须先在 application 定义 canonical contract / DTO / error model,SDK 改成 outward facade 适配 — 否则只是把 SDK 形状的逻辑挪到 application 目录里,authority 没真正迁。具体反例(以符号引用,避免行号腐化):
    - `sdk/query_runtime.py` 的 hydrate 路径 `from .facade import EntitySnapshot, FieldAssertions` 并直接构造 / 返回这些 SDK facade types
    - `sdk/ingest.py` 的写入路径直接调用 `sdk.set` / `sdk.add` / `sdk.retract`
    - 验证命令:`rg "EntitySnapshot|FieldAssertions" src/kernel/sdk/query_runtime.py` / `rg "sdk\\.(set|add|retract)" src/kernel/sdk/ingest.py`
    - 扩展边界扫描:`rg -l "kernel\\.sdk\\.facade|EntitySnapshot|FieldAssertions" src/kernel/sdk/`。期望结果只能落在 outward SDK facade / docs / compatibility adapter,不得出现在 application-owned runtime impl
- **OS-prep 关系**:本 blueprint implemented 后,回到 OS-prep 未 scoped 的 #2 PyPI policy / #11 README OS 形态;已 scoped 的 #1 single dist / #3 4 namespaces public / #6 PyReason license / #9 repo cleanup 与本 cleanup 正交。不允许在本 blueprint 内偷渡 OS-prep 决策

## 7. Acceptance

Decision phase pass 1(B+C+D)与 pass 2(A/E/F/G/H/I/J)已收口。K 仍作为 primitive contract design constraint,不在本 blueprint 实现 primitive semantics cleanup。

- [x] application API surface 设计文档落地(canonical runtime contract),明确 query / ingest / derivation runtime 不返回 SDK facade types。
- [x] Query runtime contract 落地:application 新增 SDK-independent query request/result DTO + executor;SDK `Query` adapter 保留现有 outward `dict` / `EntitySnapshot` / `instance` 行为(commit 2c)。
- [x] Ingest runtime contract 落地:application 新增 normalized ingest request/result DTO + executor;SDK `ingest(...)` 对 cache-resolvable set/add/retract 委托 application,cache miss 保守 fallback(commit 2d)。
- [x] Derivation runtime contract 落地:application 接管 compiled derivation evaluate / accept orchestration;SDK 保留 DSL lowering、keyword sugar 与 outward compatibility(commit 2b)。
- [x] Derivation contract 覆盖 single-head / multi-head shared run_id / `_heads` normalization outward 行为;新增 application parity tests 与 SDK outward tests(commit 2a/2b)。
- [x] Implementation shape follows §5.2.3:commit 1 只新增 application protocol / executor surface + narrow exports,不切 SDK god files。
- [ ] sdk/batch.py / sdk/store.py / sdk/facade.py 物理拆分与行数下降未达成;本轮改为 runtime delegation 收口,见 §10 Deviations。
- [x] application 接收 runtime impl:query / ingest / compiled derivation evaluate/accept / existing read-write planner 均有 application executor。
- [x] SDK 改成 product facade / adapter,公开 API 形态稳定;`from kernel.sdk import *` smoke 通过。
- [ ] error ownership 完整迁移未达成;application runtime 使用 DTO/error shape,SDK product-domain errors 保留,见 §10 Deviations。
- [x] `SDKRegistry` 留 SDK;application runtime contracts 不接 `SDKRegistry` object,只接 compiled/runtime-normalized inputs。
- [x] `SDKStore.export_package(...)` / `SDKStore.run_package(...)` canonical owner 保持 adapter/service delivery surface;SDK wrappers 仍是 compatibility convenience,docs 中不声明为 application runtime authority。
- [x] `_SDKViewsManager` 留 SDK;application 只接 `ViewSpec` / normalized view value,不拥有 named-view registry。
- [x] service / agent production SDK imports 实测仅 1 行(`src/agent/extraction/api.py:compile_schema_from_classes`,authoring helper);由 `src/kernel/tests/test_sdk_consumer_boundary.py` allowlist 守护。
- [x] delegation tests 重新评估并 rewrite:`test_sdk_batch_application_delegate.py` 不再断言 `_application_*` 私有字段,改测 outward 行为(commit 2b)。
- [x] SDK top-level `__all__` 只暴露 product surface / compatibility aliases,未 re-export application internals。
- [x] kernel docs 同步:application docs 升级为 canonical runtime;sdk docs 重写为 product surface / adapter。
- [ ] import-boundary validation 部分落地:unittest guard 已有;CI import-boundary gate 留 OS-prep #8,见 §10 Deviations。
- [x] SDK public import smoke 通过:`python -c "from kernel.sdk import *; from kernel.application import *"`。
- [x] tests 全绿:1093 tests across 5 segments。
- [x] OS-prep #2 PyPI policy / #7 OpenAPI yaml / #11 README OS 形态可在 new runtime authority framing 下继续收口;不在本 blueprint 修改 OS-prep 文件。

## 8. Implementation Plan

Decision phase pass 1(B+C+D)与 pass 2(A/E/F/G/H/I/J)把 contract-first 顺序和 owner 灰区具体化如下。

预期分阶段:
1. **Decision phase**:B+C+D 已完成 pass 1 contract scoping;A/E/F/G/H/I/J 已完成 pass 2 owner/compat scoping;K 仅作为设计约束记录。B/C/D design phase 收口前需要独立 reviewer pass,防止把 SDK 现有 outward shape 误当 application runtime contract
2. **Design phase B(Query)**:定义 application query protocol / executor / SDK adapter 形状;明确 `Query` DSL lowering 留 SDK adapter,application 只吃 normalized request
3. **Design phase C(Ingest)**:定义 application ingest protocol / executor / result DTO;明确 encoded target ref + `FieldPath` contract,SDK descriptor 只做 adapter
4. **Design phase D(Derivation)**:定义 application compiled derivation plan(s) + evaluate/accept orchestration;保留 core algorithm owner 与 SDK sugar owner
5. **Design phase A**:基于 B+C+D target surface 写 god file 拆分边界文档;`SDKStore`/batch/facade outward classes 留 SDK,runtime slices 抽 application
6. **Compatibility phase E/F/G/H/I/J**:按 §5.2.2 锁定 errors / registry / export-run / views / service-agent imports / SDK `__all__` owner,避免实现期临时扩 scope
7. **Refactor phase**:按 §5.3 推荐起步顺序实施 — contract design → god file 拆分 → 模块迁移 → SDK facade 收尾 → service/agent 改造(I) → tests rewrite
8. **Docs phase**:application docs 升级 + sdk docs 重写 + module 边界文档同步
9. **Validation phase**:1023 tests 全绿 + import grep 实证 + `python -c "from kernel.sdk import *"` smoke + examples
10. **Commit / PR mode**:用 4-commit squashable stack,而不是一个巨型 atomic commit:
   - commit 1:application contract / protocol surface
   - commit 2:pure refactor split with stable public API;用 `python -c "from kernel.sdk import *"` + import-graph diff 验证无 outward break
   - commit 3:consumer boundary guard(service / agent production import allowlist) + audit close
   - commit 4:docs + validation cleanup

## 9. Docs To Update

Decision phase pass 1(B+C+D)明确首批 docs 更新目标;consumer migration(I)后再 finalize import 示例与 service/agent 口径。

预期范围:
- `src/kernel/application/docs/{README,01_overview,01_overview_en}.md`(升级为 canonical runtime;新增 query / ingest / derivation runtime contract 段)
- `src/kernel/sdk/docs/{README,00_user_guide,00_user_guide.en,01_alignment_matrix,01_alignment_matrix.en,02_readwrite_and_ingest,02_readwrite_and_ingest.en,03_rules_and_derivations,03_rules_and_derivations.en,04_api_surface,04_api_surface.en,05_cn_en_consistency_checklist}.md`(降级为 ergonomic surface;明确 query / ingest / evaluate / accept 是 SDK wrapper)
- `src/kernel/AGENTS.md`(描述新 layer 责任)
- `docs/architecture_principles.md`(可能需补 layer authority 段)
- `README.md` / `README.en.md`(import 示例可能需调整,尤其 path B 的 Python API 示例)
- `examples/` 内 notebooks(若 import 改变)
- `memory/current.md`(实施完后更新)
- 本 blueprint audit log

## 10. Outcome / Deviations

Status moved to `implemented` on 2026-04-28. Blueprint remains under `active/`; archive is deferred until the OS v0.1 path finishes using this cleanup as input.

### 最终落地结果

- `kernel.application` is now the canonical Python runtime authority for:
  - entity read/hydration
  - entity write planning/apply
  - SDK-independent query runtime
  - normalized ingest runtime
  - compiled derivation evaluate/accept orchestration
- `kernel.sdk` remains the Python product surface:
  - schema / DSL authoring
  - `SDKStore` facade
  - snapshot/editor/batch outward objects
  - user-facing compatibility errors and result objects
- SDK adapters now delegate runtime paths to application:
  - commit 2b:derivation evaluate adapter
  - commit 2c:query adapter
  - commit 2d:ingest adapter with identity-cache fallback
  - existing read/write delegates retained and documented
- service/agent production SDK import surface is guarded:
  - current allowlist contains only `src/agent/extraction/api.py:compile_schema_from_classes`
  - `src/kernel/tests/test_sdk_consumer_boundary.py` prevents new production SDK runtime imports
- Docs updated:
  - application docs now describe canonical runtime authority
  - SDK docs now describe product surface / adapter role
  - `docs/architecture_principles.md` records layer authority as durable guidance
  - `memory/current.md` updated for session continuity

Completion snapshot:

- application:15 files / 3385 LOC / 29 public symbols
- SDK runtime file changes:
  - `sdk/query_runtime.py`:357 -> 297 lines after adapter rewrite and dead-code removal
  - `sdk/ingest.py`:598 -> 797 lines after application delegate + cache/legacy fallback
  - `sdk/store.py` / `sdk/batch.py` / `sdk/facade.py` remain large outward facade files
- validation baseline:1093 tests across 5 segments

### 与 blueprint 不同的地方

- **God file physical split deferred**:the original acceptance wanted `sdk/store.py` / `sdk/batch.py` / `sdk/facade.py` line-count reduction and no file over 800 LOC. Implementation completed runtime delegation without physically splitting these outward facade files. Large-file cleanup remains future internal-quality work, not runtime-authority scope.
- **Error hierarchy migration partial**:application runtime paths use DTO/error shapes for query / ingest / derivation; SDK product-domain errors(`SDKError` / `SDKSchemaError` / `SDKStoreError` / `SDKRegistryError` / `SDKDSLError`) remain SDK-owned. Full exception hierarchy rewrite is deferred.
- **Import-boundary enforcement partial**:pre-flight/test guard landed in `test_sdk_consumer_boundary.py`; CI-level import-boundary gate is deferred to OS-prep #8 quality gates.
- **K primitive-contract traps deferred**:Query id/version asymmetry,where validation timing,Derivation head/target/head_vars normalization,PyReason adapter SDK DSL coupling all remain future primitive-contract work.

### 为什么会有这些调整

- Code survey showed the high-value cleanup was completing partial migration, not mechanically shrinking SDK files.
- SDK facade objects are still the correct outward product surface, so line-count refactors would have added churn without changing runtime authority.
- Full exception hierarchy and primitive DSL ownership are broader public-contract changes; forcing them into this cleanup would expand scope beyond OS-prep unblock needs.

### 后续解锁

- OS-prep #2 PyPI policy, #7 OpenAPI yaml and #11 README OS framing are no longer blocked on runtime-authority implementation.
- Runtime-authority cleanup does not modify OS-prep blueprint files; OS-prep unblock should be recorded in a separate OS-prep patch.
