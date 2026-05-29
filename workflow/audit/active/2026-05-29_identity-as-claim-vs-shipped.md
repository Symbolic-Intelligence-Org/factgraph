# Audit: Identity-as-Claim design-points vs Shipped Runtime

- Status: **complete** (Phase 1-4 all landed;ready for Stage 2 Q-decisions + Stage 3 synthesis)
- Created: 2026-05-29
- Last Updated: 2026-05-29
- Authority: working triage document; informs but does not lock implementation. Implementation decisions follow only after audit-row review + Stage 2 Q-decisions + Stage 3 synthesis.
- Inputs:
  - `workflow/design/design-points/active/identity-mechanism-redesign.zh.md` (intaken 2026-05-29 @ `48937043`)
  - `workflow/design/design-points/active/ledger-schema-specification.zh.md` (intaken 2026-05-29 @ `48937043`)
  - `workflow/design/design-points/active/append-only-ledger-evaluation.zh.md` (intaken 2026-05-29 @ `48937043`)
  - Shipped source files read completely per Rule 1; full inventory in §4
- Outputs / Downstream:
  - Stage 2 Q-decisions in `workflow/design/decisions/active/`(每 load-bearing Q 一份 ADR)
  - Stage 3 synthesis (if ≥3 Qs close + findings span ≥2 of 5 buckets per audit/README.md §"Synthesis 触发条件")
  - Stage 4 per-slice blueprints downstream
- Related:
  - `workflow/design/design-points/archive/identity-and-data-model-redesign.zh.md`(本批次同时归档的 umbrella 前身)
  - `workflow/audit/active/2026-05-25_t5-result-evidence-explain-vs-shipped.md`(format precedent)
- Source intent: design-points 描述 Step 1 "Identity → Claim 镜像" 目标态 + 4 条硬定义 + INV-7a/b/c + Form I schema + 三层 API surface + AssertionView 统一
- Branch: `v0.2.0-identity-as-claim-audit-2026-05-29`
- Base commit: `7c5fd204`(intake branch HEAD 之后 fork)
- Reviewer handoff: Claude drafts; User reviews(per 2026-05-29 stage role 锁定)

## 1. Purpose

3 份 design-points 在 2026-05-27 → 2026-05-29 informal 设计探索期间迭代到 lock-in 状态:Identity 字段同时存为 Claim 镜像(Step 1 核心增量)、Form I schema 二分(Identity / Field + `_DataMember` 共通基类)、SDK API 三层(entities / fields / assertions)+ AssertionView 统一类型、`_meta` 统一 meta 输入入口、6+ 条硬定义、INV-7a/b/c(immutable anchor + claim-mirrored + hash 一致性)、INV-7c 实施策略 C。

本审计在任何 Stage 2 Q-decision / Stage 4 blueprint / 代码编辑之前,把 design-points 的设计 commit 对照 shipped runtime + 已 published 文档完整 re-read(per Rule 1),目的:

1. **暴露设计 vs shipped 的真实差距**(类别:shipped covers / 小 gap / shape conflict / 全新 / deferred-aligned)
2. **识别 load-bearing 问题**,作为 Stage 2 Q-decision 输入
3. **识别 cross-doc seams**(假 docs / 不同步的 module docs / public quickstart 等)
4. **为后续 blueprint 切片建立 baseline ground truth**

**重要 framing**(本 audit 一开始就要锁定):design-points 的 "ledger spec" 描述的是 **post-7-步精简 migration 的目标态**(3-table claim-first immutable payload, INV-9 unary, value+value_tag inline)。当前 shipped ledger 是 **pre-migration 7-table schema**(claims + claim_args + meta_rows + revokes + ingest_keys + ledger_meta + annotation_rows;Claim 仍是 multi-arg `rest_terms`)。Identity → Claim 的增量必须**先回答**:在哪个 ledger 形态上落地?

## 2. Audit Scope

### 2.0 5+1 state 分类约定(canonical taxonomy,贯穿 §5-§7)

per user reviewer 2026-05-29 校准:标准 5-state 之外加一个 `(f) target-gap / pending migration` 桶,**专门处理 design 描述"目标态" + shipped 是"pre-migration coherent baseline"** 的情形。

| 状态 | 含义 | 处理路径 |
|---|---|---|
| **(a) shipped covers** | shipped 完整 honors design intent | 无 action |
| **(b) small gap** | minor mv / rename / metadata sync | blueprint-eligible(small slice) |
| **(c) shape conflict** | shipped EXISTS 且 actively conflicts design — 必须 Q 决策才能继续 | 必须 Q-decision |
| **(d) genuinely new** | shipped 无对应物;design 提议全新概念 | blueprint-eligible(implementation slice) |
| **(e) deferred-aligned** | design 显式 defer + shipped honors 当前 state | 无 action(Step 2+ 时再评估) |
| **(f) target-gap / pending migration** ★ | shipped 是 pre-migration coherent state,design 描述 post-migration 目标态;**不是 conflict**,是 migration prerequisite | migration slice;Step 1 实施时一并处理或独立 slice |

**关键 framing**:"未实现目标态 ≠ shipped 是 bug"。本 audit §5-§7 所有 triage 表沿用此 taxonomy。

### In scope(本次审计目标)

**Design 文档维度**:
- `identity-mechanism-redesign.zh.md` §4(4 条硬定义)+ §5(INV-7a/b/c)+ §7(Q1 idref_v1)+ §8(Form I)+ §12(API 三层 + AssertionView)+ §13(Step 1 in-scope + Step 2+ 延后)
- `ledger-schema-specification.zh.md` §3(3-table claim-first 终态)+ §4(INV-1..INV-15)+ §8.3-§8.5(读写流程)+ §9(7 数据精简 migration)+ §11.5(上层 API 映射 + INV-7c 实施策略 C)
- `append-only-ledger-evaluation.zh.md` §6 G1(content-hash identity 措辞需重写)+ §8(10 维度评估)

**Shipped 代码维度**:
- `src/factgraph/sdk/schema.py` — `Identity` / `Field` / `Entity` / `EntityMeta` 描述符(Form I 对照点)
- `src/factgraph/sdk/store.py` — `SDKStore` + 11 namespace managers + `evaluate` / `inspect` / `match` 等方法(API 三层对照点)
- `src/factgraph/sdk/facade.py` — `EntitySnapshot` / `AssertionRecordSet` / `FieldAssertions` / `AssertionNamespace` / `EntityEditor` / `IdentityEditor` / `sdk_get` / `sdk_find` / `sdk_edit`(AssertionView 统一对照点 + Identity 镜像可见性)
- `src/factgraph/sdk/__init__.py` — public exports surface
- `src/factgraph/core/store/ledger.py` — 7-table schema + `Claim` / `ClaimArg` / `MetaRow` / `AnnotationRow` / `Revokes` dataclasses(ledger spec migration baseline)
- `src/factgraph/core/protocol/idref_v1.py` — `encode_idref_v1` typed content-derived hash(Q1 锁定基础)
- `src/factgraph/core/protocol/tup_v1.py` — 8 canonical tags + value encoding(INV-9 unary 终态依赖)
- `src/factgraph/core/evidence/write_protocol.py` — `set_field` / `add_field` / `retract_by_asrt` / `replace_field` / `new_assertion_id`(写入路径)
- `src/factgraph/authoring/schema_compile.py` — pred_id 生成 + Identity 字段处理 + `:exists` Claim 当前路径
- `src/factgraph/adapters/pyreason/accept.py` — Q-PR1 边界(`_edge_rest_terms` n-ary,触及 INV-9 冲突)

**已 published 文档维度**:
- `src/factgraph/sdk/docs/04_api_surface.en.md` — API surface 权威 reference(三层 + AssertionView 重组的对照基线)
- `docs/official/kernel/quickstart/assertions.md` — `.at(t)` / `.version(v)` / `.where(...)` time semantics shipped 描述(Q4/Q6 时间维度对照点)

### Out of scope(本次明确不涉及)

- 实现代码编辑、API 删除、migration shim、文档重写(per Stage 1 audit-only)
- T11 release-path 工作(T11 在不同分支,独立 slice)
- T4 / T5 已闭合 cycle 的回顾(audit framing 不涉及)
- 测试套件实施细节(audit phase 不 re-run 测试)
- Rule / Inference / Semantics / Evidence / Persistence 章节 PDF Change Request(已记录为 Step 2+ 评估,见 identity §17 中"PDF Change Request 2026-05-28 triage 追加批次")
- adapter 实际重写(PyReason adapter rewrite 是 Step 2+ slice,本次仅识别 Q-PR1 边界)
- push / merge / release-machinery 操作
- memory file 更新(只在 milestone batch 期更新,非本 audit 期)

## 3. Canonical Sources Read

### Design-points(本次 audit 目标)

| Source | Lines | Audit use |
|---|---:|---|
| identity-mechanism-redesign §4.1 4 条硬定义 + 边界规则 | `workflow/design/design-points/active/identity-mechanism-redesign.zh.md:139-200` | Step 1 锁定 4 条硬定义(typed constructor / immutable anchor / mutable Field / mirrored Claim)+ 边界规则(未来可能变的值不要建模为 Identity) |
| identity-mechanism-redesign §5.2 INV-7a/b/c | `:222-345` | Identity-as-Claim 三子不变量 + INV-7c 实施策略 C + schema evolution Identity↔Field 互转禁止 |
| identity-mechanism-redesign §7 Q1 锁定 idref_v1 | `:327-365` | typed content-derived hash 锁定;opaque allocated alternative(ULID/UUID4)评估后不采纳 |
| identity-mechanism-redesign §8 Form I | `:376-510` | Identity / Field 二分 + `_DataMember` 共通基类(`description` / `pattern`)+ Literal 枚举 + 类型推断 cardinality + 去 `primary_key` |
| identity-mechanism-redesign §12 API 三层 + AssertionView | `:768-1295` | entities / fields / assertions 三层 + AssertionView 统一 + `_meta` 统一 + 6 条硬定义 + 招纳原则 |
| identity-mechanism-redesign §13 Step 1 in-scope + Step 2+ 延后 | `:1311-1380` | Step 1 完整 in-scope 清单 + Step 2+ 延后清单(InternalIdentity / 唯一性 / 备用键 / etc.) |
| identity-mechanism-redesign §15 决策日志 | `:1404-1490` | 锁定决策清单(含 PDF triage + X-style lock-in + 7 Q 答复 + ledger 同步 + entities.delete 签名留 blueprint) |
| ledger-schema-specification §3 3-table 终态 schema | `workflow/design/design-points/active/ledger-schema-specification.zh.md:105-160` | claims + claim_meta + ledger_meta 终态(`:exists` 标 legacy/transitional) |
| ledger-schema-specification §4 INV-1..INV-15 | `:165-370` | 15 条结构性不变量(INV-9 unary / INV-10 system namespace / INV-11/12/13 revoke / INV-15 默认 filter / 含 INV-7c ledger 层约束说明) |
| ledger-schema-specification §8 写读流程 | `:608-700` | append-only 流程 + entities.get + idref_v1 hash 算 e_ref + active projection(INV-13) |
| ledger-schema-specification §9 7 数据精简 migration | `:710-790` | 7 步从 shipped pre-migration 到 design 终态的 migration 路径 |
| ledger-schema-specification §11.5 上层 API 映射 | `:870-918` | API 操作 → ledger 操作映射 + INV-7c 实施策略 C(application 层 Identity pred_id set) |
| append-only-ledger-evaluation §6 G1 措辞重写需求 | `workflow/design/design-points/active/append-only-ledger-evaluation.zh.md` (review §6 全文,约 §239 行起) | G1 原 "content-hash identity anti-pattern" 与本轮 X-style 选择冲突,需重写为 "identity 用完即扔" |
| append-only-ledger-evaluation §8 10 维度评估 | `append-only-ledger-evaluation.zh.md` (review §8 全文) | append-only 范式 best-practice 评估 + future gap(GDPR / bitemporal / compaction) |

### Workflow / cadence sources

| Source | Lines | Audit use |
|---|---:|---|
| Current memory | `workflow/memory/current.md:3-32` | Branch baseline(T11 HEAD)、sacred master sha、unrelated dirty baseline、Recommended Next Work #2(design-point intake)、push gate |
| CADENCE.md Stage 1 audit phase | `workflow/CADENCE.md:96-106` | 4-phase audit 流程(inventory → I-series triage → A-series triage → D-series + cross-doc seams + recommendations) |
| audit/README.md vs-shipped sub-type | `workflow/audit/README.md` §"三种 standalone sub-types" | vs-shipped 文件命名 + 5-state 分类 + Q surfacing 责任 |
| design/README.md design-point 权威边界 | `workflow/design/README.md:24-34` | design-point 不能直接覆盖 shipped;须经 adopted decision / implemented blueprint / module docs / architecture_principles 引用才约束 |
| Architecture principles §2.1 Layer authority | `workflow/foundations/architecture_principles.md` §2.1 | INV-6 来源(application-first runtime authority);Identity Claim 写入 / INV-7c 检查必须先在 application 层定义 |

## 4. Shipped Source Read

**重要:Phase 1 仅完成 inventory + 当前形态 baseline 描述;不做 triage / 不分类 drift / 不浮 Q。** 5-state 分类(shipped covers / 小 gap / shape conflict / 全新 / deferred-aligned)留 Phase 2-4 处理。

### 4.1 SDK schema layer

| Source | Lines | Shipped state (Phase 1 baseline note) |
|---|---:|---|
| Identity descriptor | `src/factgraph/sdk/schema.py:50-88` | `Identity(*, default=None, default_factory=None, primary_key=False)`;`primary_key: bool` 仍存在(`primary_key=True/False` 区分),不是 Form I 描述的"去除"形态;无 `pattern=` 参数;无 `description=` 参数 |
| Field descriptor | `src/factgraph/sdk/schema.py:91-141` | `Field(*, cardinality: str, description: str \| None = None)`;`cardinality` 是必填 kwarg(not 从类型推断);`description` 已存在但在 Field 上、不在共通基类 |
| `_DeclaredMember` 基类 | `src/factgraph/sdk/schema.py:20-47` | 仅承载 descriptor 协议(`__set_name__` / `__get__` / `__set__`);不承载共通数据参数(无 `_DataMember` 中间层) |
| Entity metaclass | `src/factgraph/sdk/schema.py:145-200` | `EntityMeta.__new__` 收集 `Identity` + `Field` 注解;要求至少一个 `Identity(primary_key=True)`;输出 `__sdk_entity_spec__` |
| Entity 基类 | `src/factgraph/sdk/schema.py:203-245` | `__init__(**kwargs)` 接受 entity 实例化;`__repr__` 按 identity + field 顺序展示 |
| Relationship 系列 | `src/factgraph/sdk/schema.py:248-307` | `Relationship` + `RelationshipMeta`(from_entity / to_entity);跟 PyReason adapter edge 模型对应 |
| Public exports | `src/factgraph/sdk/__init__.py:25,82-85` | `Entity` / `Field` / `Identity` / `Relationship` 全部 export 在 `__all__` |

### 4.2 SDK store layer(namespace managers)

| Source | Lines | Shipped state (Phase 1 baseline note) |
|---|---:|---|
| SDKStore main class | `src/factgraph/sdk/store.py:865-1230` | `FactGraph = SDKStore` literal alias;11 namespace property accessors(views / assertions / schema / read / write / rules / inferences / eval / audit / what_if / package) |
| `fg.read.*` manager | `src/factgraph/sdk/store.py:529-565` | 4 methods:`get(EC, **id)` / `find(EC, **filters)` / `match(EC, template, **ports)` / `ref(EC, **id) → idref_v1 token` |
| `fg.write.*` manager | `src/factgraph/sdk/store.py:568-603` | 4 methods:`set(F, e_ref, value, meta)` / `add(F, e_ref, value, meta)` / `retract(asrt_id, meta)` / `edit(EC, **id) → EntityEditor` |
| `fg.assertions.*` manager | `src/factgraph/sdk/store.py:436-485` | 5 methods:`by_id(asrt_id)` / `by_ids([...])` / `active()` (method, not property) / `all()` (method) / `field(Field)`;所有 read-only,**无 retract / where** |
| `fg.schema.*` manager | `src/factgraph/sdk/store.py:512-520` | 3 methods:`ingest(...)` / `validate_provenance(...)` / `add(*classes, **kwargs)` — **`add` 是单一入口混杂 register + extend 语义**,不是 design 提议的三分 `register / extend / apply` |
| `fg.rules.*` manager | `src/factgraph/sdk/store.py:606-622` | 1 method:`inspect(rule_or_rule_expr)` |
| `fg.inferences.*` manager | `src/factgraph/sdk/store.py:625-640` | 0 public methods(post-Q8 Phase 2 empty namespace) |
| `fg.eval.*` manager | `src/factgraph/sdk/store.py:642-666` | 3 methods:`evaluate(...)` / `explain(...)` / `inspect_semantics(...)` |
| `fg.audit.*` manager | `src/factgraph/sdk/store.py:747-790` | `explain_fact(pred_id, e_ref, ...)` / `recheck_proof_frame(...)` / `diff_proof_frames(...)` / `conflicts(...)` |
| `fg.what_if.*` manager | `src/factgraph/sdk/store.py:709-744` | `check(...)` / `diagnose(...)` / `why_not(...)` + sub:`fact_overlay.check/recheck_proof_frame`(G2)+ sub:`rule.disable/literal_replace/add_condition`(G3) |
| `fg.views.*` manager | `src/factgraph/sdk/store.py:340-432` | `create(name, asrt_ids)` / `update(name, asrt_ids)` / `delete(name)` / `get(name)` / `list()` — 跟 `fg.assertion_views` PDF 提议的命名不同 |
| `fg.package.*` manager | `src/factgraph/sdk/store.py:780-792` | `export_package(...)` / `run_package(...)` |
| 顶层 flat aliases | `src/factgraph/sdk/store.py:1246-2000+` | `fg.get` / `fg.set` / `fg.add` / `fg.retract` / `fg.edit` / `fg.match` / `fg.ref` 等 flat shortcut 大量存在 |

**没有 namespace**(design 提议但未 shipped):
- `fg.entities.*`(design 提议;shipped 散在 `fg.read.*` + `fg.write.edit`)
- `fg.fields.*`(design 提议;shipped 跟 `fg.write.*` 重叠)

### 4.3 SDK facade layer(read-side types)

| Source | Lines | Shipped state (Phase 1 baseline note) |
|---|---:|---|
| AssertionMeta | `src/factgraph/sdk/facade.py:37-50` | 不可变 dataclass:`source` / `trace_id` / `raw: dict[str, Any]` |
| AssertionRecord | `src/factgraph/sdk/facade.py:88-100` | 不可变 dataclass:`asrt_id` / `pred_id` / `e_ref` / `rest_terms`(list)/ `meta` / `seq`;**仍是 multi-arg `rest_terms`,跟 ledger Claim 一致** |
| AssertionRecordSet | `src/factgraph/sdk/facade.py:102-201` | tuple subclass + fluent:`.where(value=, source=, trace_id=, version=, meta=)` / `.at(t)` / `.version(v)` / `.by_id(asrt_id)` / `.one()` / `.first()` / `.all()` / `.__call__()` returns self |
| FieldAssertions | `src/factgraph/sdk/facade.py:204-253` | per-field per-entity 视图:`active` / `history` / `all`(property)/ `at(t)` / `version(v)`(method);跟 design 提议合并进 AssertionView 不同 |
| AssertionNamespace | `src/factgraph/sdk/facade.py:257-330` | per-entity 视图:`field(name)` / `active()` / `all()` / `by_id(asrt_id)` / `by_ids([...])`;**跟 design 提议合并进 AssertionView 不同** |
| EntitySnapshot | `src/factgraph/sdk/facade.py:335-386` | 不可变实体快照:`ref` / `entity_type` / `identity_available` / `assertions` / `identity`(property)/ `field(name)` shortcut;dot-access via `__getattr__` 先查 `_field_values` 后查 `_identity_values`(两 dict 独立) |
| FieldEditor | `src/factgraph/sdk/facade.py:389-445` | 在 EntityEditor context 内:`set(value, meta)` / `add(value, meta)` / `retract(asrt_id, meta)`;single/multi cardinality check |
| IdentityEditor | `src/factgraph/sdk/facade.py:448-479` | Identity 字段在 EntityEditor 内:`value`(property)/ `set/add/retract` **全部 raise SDKStoreError**("identity field is immutable in editor");跟 INV-7c 一致 |
| EntityEditor | `src/factgraph/sdk/facade.py:482-547` | context manager:`preview()` / `commit(meta)` / `rollback()` |
| sdk_get | `src/factgraph/sdk/facade.py:549-583` | 走 `fg.read.get(EC, **id)` 路径;返回 EntitySnapshot;**注:identity 值是从 `**identity_kwargs` echo 进 snapshot,不从 ledger 读**(对应 design §3.1 不满 #2) |
| sdk_find | `src/factgraph/sdk/facade.py:585-670` | `fg.read.find(EC, **filters)` 路径 |
| sdk_edit | `src/factgraph/sdk/facade.py:672+` | `fg.read.edit` / `fg.write.edit` 路径 |

### 4.4 Core ledger layer

| Source | Lines | Shipped state (Phase 1 baseline note) |
|---|---:|---|
| Ledger DDL — 7 tables | `src/factgraph/core/store/ledger.py:81-159` | **`claims` + `claim_args` + `meta_rows` + `revokes` + `ingest_keys` + `ledger_meta` + `annotation_rows`**(7-table pre-migration schema)|
| `claims` table | `:82-88` | `seq` PK auto / `asrt_id` TEXT UNIQUE / `pred_id` TEXT / `e_ref` TEXT / **`rest_terms` TEXT NOT NULL(n-ary,JSON)**;**无 `value` / `value_tag` 双列**(design 提议的 INV-9 unary 终态形态) |
| `claim_args` table | `:90-96` | `id` PK / `asrt_id` / `idx` / `val_atom` / `tag`;**design 提议的 INV-9 unary 终态把此表去除,改为 claims.value + value_tag** |
| `meta_rows` table | `:98-104` | `id` PK / `asrt_id` / `key` / `kind` / `value`;**design 提议改名为 `claim_meta` + 简化 kind 列、加复合 PK** |
| `revokes` table | `:106-110` | `id` PK / `revoker_asrt_id` / `revoked_asrt_id`;**design 提议(精简 3)→ 改为 `__system__.revokes` special pred Claim 进 claims 表,删独立 revokes 表** |
| `ingest_keys` table | `:112-116` | `ingest_key` PK / `asrt_id` / `kind`;**design 提议(精简 6)→ 删除** |
| `ledger_meta` table | `:118-121` | `key` PK / `value`;**保留**(全局 ledger 元数据) |
| `annotation_rows` table | `:141-152` | `id` PK / `asrt_id` / `namespace` / `category` / `key` / `kind` / `value` / `origin` / `derivation`;**design 提议(精简 1)→ 折叠进 `claim_meta`,namespace + category + derivation 视情况精简(精简 2)** |
| 索引 baseline | `:123-158` | `idx_claims_asrt_id` / `idx_claims_pred_id` / `idx_claims_e_ref` / `idx_claims_pred_eref` + `idx_args_*` + `idx_meta_*` + `idx_revokes_*` + `idx_anno_*`;**design 提议加 `idx_claims_pred_value`(UNIQUE 反向索引,Field 反向查询用)** |
| `Claim` dataclass | `:22-26` | `asrt_id` / `pred_id` / `e_ref` / **`rest_terms: list[tuple[str, Any]]`(n-ary)** |
| `ClaimArg` dataclass | `:30-34` | per-arg row;design 提议消除 |
| `MetaRow` dataclass | `:38-43` | `asrt_id` / `key` / `kind` / `value`;`META_KINDS = {"str","int","float","bool","time","json"}`(line 15) |
| `AnnotationRow` dataclass | `:46-56` | per-annotation row;`ANNOTATION_CATEGORIES = {"source","semantic","derived","operational"}`(line 17);origin ∈ `{observed, derived}` |
| `Revokes` / `Idempotency` / `AppendResult` / `DuplicateIngestKeyError` | `:60-78` | revoke / idempotency / append result dataclasses;`DuplicateIngestKeyError` 自定义 exception |
| `Ledger.append_assertion` 主写入路径 | `:363-450` | 接受 `Claim` + 可选 `Idempotency` + meta + annotations;原子提交;返回 `AppendResult` |
| `Ledger.append_revocation` 路径 | `:453-510` | 写 `Revokes` row(不通过 claims 表 special pred);跟 design 提议的 `__system__.revokes` 形态不同 |
| `Ledger.find_revoker` / `has_active_revocation` | `:704-714` | 走 `revokes` 表反查;INV-13 active projection 实现依赖 |

### 4.5 Core protocol layer

| Source | Lines | Shipped state (Phase 1 baseline note) |
|---|---:|---|
| `encode_idref_v1(EntityType, identity_fields) → str` | `src/factgraph/core/protocol/idref_v1.py:67-73` | `f"idref_v1:{entity_type}:{base32_lowercase(sha256(canonical_bytes_idref_v1(...)))}"`;**X-style typed content-derived hash**;Q1 锁定形态 shipped 中 |
| `canonical_bytes_idref_v1` | `:26-64` | length-prefixed UTF-8 EntityType + count + per-field (name length + name bytes + tag code + payload length + payload);prefix `factpy\x00idref_v1\x00`;identity_fields 参数形态:`list[tuple[str, str, Any]]`(name, type_domain, value) |
| `ENTITY_TYPE_RE` | `:12` | `^[A-Za-z][A-Za-z0-9_.-]{0,127}$`(限定 entity type 字符集) |
| `tup_v1` 8 canonical tags | `src/factgraph/core/protocol/tup_v1.py:14-23` | `entity_ref` / `string` / `int` / `float64` / `bool` / `bytes` / `time` / `uuid`(tag set 跟 ledger MetaRow.kind 的 `{str,int,float,bool,time,json}` **不同** — tup_v1 是 ledger fact value 编码,MetaRow.kind 是 meta value 编码) |
| `encode_value_bytes(tag, value)` | `:133-153` | per-tag canonical encoding(int 文本 ASCII / float64 big-endian 8B / time epoch_nanos 8B / uuid 16B / bytes raw / entity_ref UTF-8 + `idref_v1:` prefix check) |
| `claim_args_from_rest_terms` | `:196-210` | 从 rest_terms list 生成 ClaimArg rows(idx + val_atom + canonical_tag);**这是 INV-9 unary 终态后将不再需要的路径** |
| `canonical_bytes_tup_v1(rest_terms)` | `:156-168` | rest_terms list 整体的 canonical byte stream(prefix `factpy\x00tup_v1\x00` + count + per-tag encoding);**INV-9 unary 后,单 value + value_tag 直接 hash 不需要 list 包装** |

### 4.6 Core write protocol

| Source | Lines | Shipped state (Phase 1 baseline note) |
|---|---:|---|
| `set_field(ledger, pred_id, e_ref, rest_terms, meta=None)` | `src/factgraph/core/evidence/write_protocol.py:128-160` | 单字段 set 路径;接受 multi-arg `rest_terms`;**当前实现假设 multi-arg ledger** |
| `add_field(...)` | `:160-170` | 类似 set,multi cardinality 加 row |
| `retract_by_asrt(ledger, asrt_id, meta=None)` | `:170-210` | append-only revoke;写 `Revokes` row + meta;**不区分 Identity Claim vs Field Claim**(design 提议 INV-7c 要求拒绝 Identity Claim 单独 retract) |
| `replace_field(...)` | `:211-...` | retract + re-write 组合糖 |
| `new_assertion_id()` / `now_epoch_nanos()` | `:120-126` | UUID4 hex 形 / 64-bit epoch nanos |
| `__all__` exports | `:107+` | `set_field` / `add_field` / `retract_by_asrt` / `replace_field` / `new_assertion_id` / `now_epoch_nanos` |

### 4.7 Authoring + schema compile

| Source | Lines | Shipped state (Phase 1 baseline note) |
|---|---:|---|
| `schema_compile.py` `:exists` 处理 | `src/factgraph/authoring/schema_compile.py` 搜 `:exists` / `__exists__` | 当前 SQL/spec 命名是 `:exists`(per `schema_compile.py:142` 之前 audit 已验证);`fg.entities.create` 内部 emit `<EntityType>:exists` Claim(per ledger spec §3.1 现状) |
| pred_id 形态 | `:142` 周围 + `src/factgraph/sdk/dsl/expr.py:440` | `<EntityType>:<field_name>` 字符串拼接(`record_type.lower()` + `:` + `attr.field_name`);跟 design 描述一致 |
| Identity 字段编译路径 | `schema_compile.py` Identity 路径 | shipped Identity 字段**不**写 Claim(只参与 idref_v1 hash 输入);跟 design Step 1 提议的"同时写 Claim 镜像"对照,**这是 Step 1 核心增量的实施缺口** |

### 4.8 Adapter boundary(PyReason)

| Source | Lines | Shipped state (Phase 1 baseline note) |
|---|---:|---|
| `_edge_rest_terms(fact, pred_spec)` | `src/factgraph/adapters/pyreason/accept.py:187-205` | 返回 `[(to_ref_tag, to_ref_value), (value_tag, fact["value"])]` — **2-element rest_terms list, n-ary**;**跟 design INV-9 unary 终态冲突(Q-PR1 anchor)** |
| `_materialize_entity_ref(raw_ref, entity_type)` | `:256-259` | `f"{ENTITY_REF_PREFIX}{entity_type}:{raw_ref}"` 包装;ENTITY_REF_PREFIX = `idref_v1:`;**typed Thing constructor 已落地,跟 §4.1 硬定义 1 一致** |
| `accept_pyreason_session` | `:94-160` | 节点 facts → `set_field(ledger, pred_id, node_e_ref, [(value_tag, value)], meta)`(node 是 unary);edge facts → `set_field(ledger, pred_id, from_e_ref, [(to_tag, to_ref), (value_tag, value)], meta)`(edge 是 n-ary,违反 INV-9) |
| `_predicate_specs_by_id` | `:163-171` | 从 `session._schema_ir["predicates"]` 取 pred_spec |

### 4.9 Published reference docs

| Source | Lines | Shipped state (Phase 1 baseline note) |
|---|---:|---|
| API surface authoritative reference | `src/factgraph/sdk/docs/04_api_surface.en.md` 全 560 行 | 当前 namespace map:`fg.read` / `fg.write` / `fg.schema` / `fg.assertions` / `fg.views` / `fg.eval` / `fg.audit` / `fg.rules` / `fg.inferences` / `fg.package` / `fg.what_if` / collection-level fluent;**fg.entities / fg.fields 不存在;`.version(v)` 是 first-class method;`record_set.where` 有 `source/trace_id/version` flat kwargs + 另有 `meta={...}` dict** |
| Time semantics + assertions quickstart | `docs/official/kernel/quickstart/assertions.md:300-413` | `.at(t)` = `.active.at(t)` shortcut;`.version(v)` = `.active.version(v)` shortcut;`.at(t)` 匹配 `meta.raw["valid_from"]` + `meta.raw["valid_to"]`(半开区间);**`during` / `now` 当前不存在**;`record_set.where(value=, source=, trace_id=, version=, meta=)` flat + dict 混合 meta 入口 |

### 4.10 Coverage check(本次 audit 已 read 文件 vs CADENCE Rule 1 完整 re-read 要求)

| 文件 | 总行 | 本次 Phase 1 已读 | 备注 |
|---|---:|---|---|
| `src/factgraph/sdk/schema.py` | 460 | ✓ (会话早期完整 read + 本次结构 grep) | Phase 2 triage 时需 row-drafting time re-read |
| `src/factgraph/sdk/store.py` | 4174 | ✓ namespace managers 区段(line 120-792 + 865-1230) + 结构 grep | Phase 2 triage 时按行 re-read 触及的具体 method |
| `src/factgraph/sdk/facade.py` | 1165 | ✓ 类结构 grep + 早期会话完整 read | Phase 2 triage 时 row-drafting time re-read |
| `src/factgraph/sdk/__init__.py` | 123 | ✓ 完整 read | 公开 surface 全表已抓 |
| `src/factgraph/core/store/ledger.py` | 1164 | ✓ DDL + dataclasses + structure grep(line 1-175 完整)| Phase 2 triage 时 row-drafting time re-read 写入路径 |
| `src/factgraph/core/protocol/idref_v1.py` | 73 | ✓ 完整 read | Q1 锁定形态完整覆盖 |
| `src/factgraph/core/protocol/tup_v1.py` | 210 | ✓ 完整 read | 8 canonical tag 全覆盖 |
| `src/factgraph/core/evidence/write_protocol.py` | 526 | ✓ 结构 grep + `__all__` | Phase 2 triage 时 row-drafting time re-read |
| `src/factgraph/authoring/schema_compile.py` | 529 | ⚠️ 仅 grep + 已知 :exists / pred_id 形态 | **Phase 2 triage 前必须完整 re-read**(Identity 字段编译路径是 Step 1 核心 implementation site) |
| `src/factgraph/adapters/pyreason/accept.py` | 259 | ✓ 完整 read | Q-PR1 边界完整覆盖 |
| `src/factgraph/sdk/docs/04_api_surface.en.md` | 560 | ⚠️ 已知大纲 + namespace map | Phase 2 triage 触及具体方法时定向 re-read |
| `docs/official/kernel/quickstart/assertions.md` | 753 | ⚠️ 已知 .at/.version time semantics 关键段 | Phase 4 cross-doc seams 时定向 re-read |

**Phase 1 完成判定**:已读+grep 覆盖**核心 shape**(SDK / schema / ledger / protocol / adapter);**剩余文件 row-drafting time re-read 在 Phase 2 时执行**,符合 Rule 1 "审计 row-drafting 时重读"原则。

## 5. Findings

### 5.1 I-series — Invariant triage(Phase 2)

**5+1 state 分类约定见 §2.0(canonical taxonomy)**。INV-7c / INV-9 / INV-10 / INV-11 / INV-15 等几条都是 (f) target-gap,因为 shipped 当前不存在它们 enforce 的概念前提(Identity Claim、unary fact、`__system__.*` namespace 等);**Step 1 实施时**这些 invariant 将成为新 write/retract path 的 load-bearing boundary check。

#### I-series triage table

每条 invariant 一行;design source / shipped evidence / 分类 / rationale / 浮出的 candidate Q(若有)。

| # | Invariant | Design source | Shipped evidence | 分类 | Rationale + candidate Q |
|---|---|---|---|---|---|
| **INV-1** | Append-only ledger | `ledger-schema-specification.zh.md:218-228` | `core/store/ledger.py:363-510`(`append_assertion` / `append_revocation` 均 append 路径);`evidence/write_protocol.py:128-208`(`set_field` / `retract_by_asrt` 都不 in-place update) | **(a) shipped covers** | append-only 原则完整 honored。revokes via 独立表是 pre-migration 形态,但 append-only 行为本身 ✓。**无 Q**。 |
| **INV-2** | asrt_id 全局唯一 | `:230-239` | `evidence/write_protocol.py:120-122` `new_assertion_id() = uuid4().hex`;`ledger.py:84` `asrt_id TEXT NOT NULL UNIQUE` constraint | **(a) shipped covers** | UUID4 hex 全局唯一 ✓;UNIQUE constraint enforces。**无 Q**。 |
| **INV-3** | SQLite 单事务原子写 | `:241-249` | `ledger.py:363-510` `append_assertion` / `append_revocation` 都在 `_conn` cursor + commit boundary 内;**Phase 3 row-drafting 时 re-read 确认 transaction boundary**(留 §4.10 coverage check) | **(a) shipped covers**(pending Phase 3 verification) | append_assertion 看起来跨 claims+claim_args+meta+annotations 原子;Phase 3 时确认是否真的单 transaction。**无 Q**(若 Phase 3 verification 通过)。 |
| **INV-4** | tup_v1 字节级 canonical 设计稳定(8 tags) | `:251-266` | `core/protocol/tup_v1.py:14-23` 恰好 8 tags:`entity_ref` / `string` / `int` / `float64` / `bool` / `bytes` / `time` / `uuid` | **(a) shipped covers** | 8 tag 集合稳定 ✓;`encode_value_bytes` per-tag canonical encoding 完整。**无 Q**。 |
| **INV-5** | Ledger 是 source of truth | `:268-275` | `ledger.py` 是 SQLite 表;`_revoked_asrt_ids` 是 cache(可重建);无独立 active 表 | **(a) shipped covers** | ledger 是唯一 truth ✓;in-memory 全是 projection cache。**无 Q**。 |
| **INV-6** | Application-first runtime authority | `identity-mechanism-redesign.zh.md:209-219` | `factgraph.application/` 模块层,SDK shells via `_SDKReadManager` / `_SDKWriteManager` 等(`sdk/store.py:529-603`)delegate 到 application 层 | **(a) shipped covers** | 分层 ✓;SDK layer 是 ergonomic shell,不携带 substrate logic。**无 Q**。 |
| **INV-7a** | Identity Anchor immutable | `identity-mechanism-redesign.zh.md:248-261` | `sdk/facade.py:448-479` `IdentityEditor.set/add/retract` 全部 raise `SDKStoreError("identity field is immutable in editor")`;`schema.py:172-176` `EntityMeta` 要求至少一个 `Identity(primary_key=True)` | **(a) shipped covers** + **(b) small gap** | Editor-time immutability ✓ shipped;但 INV-7a 还要求 "改 Identity 字段值 = create 新 entity"(`delete + create` 显式语义)— SDK 当前没有这个 idiom 的明确文档/check。**Q-I1 候选**:Step 1 时是否要在 `fg.fields.set(IdentityField, ...)` 加 schema-aware 拒绝?(Layer 2 拒绝 Identity 写入) |
| **INV-7b** | Identity-as-Claim mirrored | `identity-mechanism-redesign.zh.md:263-280` | shipped Identity 字段**仅参与 `idref_v1` hash 输入**(`core/protocol/idref_v1.py:67-73`);**不写 Claim 镜像**(`authoring/schema_compile.py` Identity 路径无 claim emission;§4.10 Phase 2 已标识 row-drafting time 需补 re-read 确认) | **(f) target-gap / pending migration** | Step 1 核心增量。shipped 是"identity 用完即扔"coherent baseline;design 加 mirror Claim。**Q-I2 候选**:Identity Claim 在哪个写入路径 emit?`fg.entities.create` 内部 emit(SDK 层),还是 ledger 写入路径自动 derive(application 层)? |
| **INV-7c** | Identity Claim ↔ e_ref hash 一致性 | `identity-mechanism-redesign.zh.md:282-345` | **当前 shipped 没有 Identity Claim,所以 INV-7c 当前 vacuously 满足**(零 Identity Claim → 无 inconsistency 可能);零 enforcement code shipped。**Step 1 实施时,INV-7c 必须成为 write/retract path 的 load-bearing boundary invariant** | **(f) target-gap / not-applicable-yet** | per user reviewer:**不是 violation,而是 not applicable until Identity-as-Claim exists**。**关键 Q-I3 候选**:实施策略 C(application 层 in-memory Identity pred_id set)的 cache 加载 / invalidation / lookup 路径具体怎么实现?是 SDK init 时一次性建,还是 lazy 加载?schema evolution 触发 cache 重建的 hook 在哪? |
| **INV-9** | Ledger Claim 是 unary fact(value+value_tag 双列) | `ledger-schema-specification.zh.md:277-288` | `ledger.py:82-88` `claims` 表当前是 `(seq, asrt_id, pred_id, e_ref, rest_terms)` 5 列,**`rest_terms TEXT NOT NULL` 是 multi-arg JSON list**;无 value / value_tag 双列;`Claim` dataclass(`:22-26`)`rest_terms: list[tuple[str, Any]]` n-ary | **(f) target-gap / pending migration** | 精简-4 migration 目标(rest_terms → value+value_tag inline)。shipped 多 arg 是 coherent baseline。**Q-I4 候选**:`set_field`(`evidence/write_protocol.py:128-156`)是否要在 INV-9 enforcement 阶段加 `len(rest_terms) <= 1` runtime check?当前 PyReason adapter 写 2-elem(Q-PR1 anchor)— 这跟 INV-9 enforce 时机直接耦合 |
| **INV-10** | `__system__.*` pred_id 命名空间预留 | `ledger-schema-specification.zh.md:290-300` | **zero hits for `__system__` in shipped source** (`sdk/store.py` / `sdk/facade.py` / `authoring/` / `core/` 全部 grep 无命中);`set_field` 无 namespace check(`evidence/write_protocol.py:231-249` `_validate_write_inputs` 仅类型检查) | **(f) target-gap / pending migration** | 精简-3 migration 前 system namespace 尚不存在;Step 1+ enforce 必要。**Q-I5 候选**:`__system__.*` rejection 应该在 application 层(SDK write shell)还是 protocol 层(`set_field`)?后者更严格(防 internal API 误用),前者更灵活(audit / migration tool 可绕过) |
| **INV-11** | Revoke claim payload shape 固定(`__system__.revokes` Claim) | `ledger-schema-specification.zh.md:302-309` | `ledger.py:106-110` `revokes` 是**独立表**(`revoker_asrt_id` / `revoked_asrt_id`);`retract_by_asrt`(`evidence/write_protocol.py:200-205`)写 `Revokes(revoker_asrt_id, revoked_asrt_id)` 行,**不**写 `__system__.revokes` Claim 到 `claims` 表 | **(f) target-gap / pending migration** | 精简-3 migration 目标;独立 revokes 表是 pre-migration coherent baseline。**与 INV-9 / INV-10 同 slice**:revokes 表删除 = system pred Claim 写入路径建立(链式 migration) |
| **INV-12** | Revoke target 约束(v1 严格) | `ledger-schema-specification.zh.md:311-321` | `evidence/write_protocol.py:179-180` `ledger.get_claim(revoked_asrt_id) is None → raise WriteProtocolError("unknown revoked_asrt_id")`(part 1 ✓ existence check);**part 2 缺**:无 `pred_id NOT LIKE '__system__.%'` check(因为 INV-10 未 enforce,system claim 不存在 → part 2 vacuously 满足) | **(a) shipped covers**(existence check)+ **(f) target-gap**(system claim 拒绝) | Existence check 已 shipped;system claim 拒绝跟 INV-10/11 同 slice 一起加。**Q 候选与 Q-I5 同一**(__system__.* enforcement layer) |
| **INV-13** | Active projection 单一公式(factual MINUS revokes) | `ledger-schema-specification.zh.md:323-336` | shipped 用 `revokes` 独立表 join 实现 active projection;无 soft flag 列、无独立 active 表(shipped 形态跟 design 公式语义等价,**只是 revokes 数据源不同**);Phase 3 row-drafting 时 re-read 具体 SQL | **(b) small gap** + **(f) target-gap**(公式定义跟随 INV-11) | **公式语义** shipped 等价 design ✓(只是数据源是 revokes 表 not __system__.revokes Claim);精简-3 migration 后公式形态自然对齐。**无独立 Q**;跟 INV-11 同 slice |
| **INV-14** | Revoke 幂等性行为契约 | `ledger-schema-specification.zh.md:338-347` | `evidence/write_protocol.py:182-184` `existing_revoker = ledger.find_revoker(revoked_asrt_id); if existing_revoker is not None: return existing_revoker` ✓ 严格幂等;不创建第二条 revoke | **(a) shipped covers** | 幂等性完整 honored ✓。**无 Q**。 |
| **INV-15** | 普通查询默认 filter system claims | `ledger-schema-specification.zh.md:349-355` | **zero hits for "NOT LIKE.*__system__" pattern in shipped source**;当前 shipped 没有 system claim 概念 → INV-15 filter 当前 vacuously 满足(没有 system claim 需要 filter) | **(f) target-gap / pending migration** | 跟 INV-10/11 同 slice。当 system pred Claim 写入路径建立时,read path 必须同步加 filter。**无独立 Q**(跟 INV-10 同 enforce 决策) |

#### 5.1 I-series 总结

**16 条 invariant 的分类分布**:

| 分类 | INV 数 | 列表 |
|---|---:|---|
| (a) shipped covers | 7 | INV-1 / INV-2 / INV-3* / INV-4 / INV-5 / INV-6 / INV-14 |
| (a)+(b) shipped covers + small gap | 1 | INV-7a(editor immutability + 缺 fg.fields.set Identity 拒绝) |
| (a)+(f) shipped covers + target-gap | 1 | INV-12(existence check ✓ + system claim 拒绝 pending) |
| (b)+(f) small gap + target-gap | 1 | INV-13(公式语义等价 + 数据源待迁移) |
| (f) target-gap / pending migration | 6 | INV-7b / INV-7c / INV-9 / INV-10 / INV-11 / INV-15 |
| (c) shape conflict | 0 | — |
| (d) genuinely new | 0 | — |
| (e) deferred-aligned | 0 | — |

\* INV-3 待 Phase 3 row-drafting 时 re-read `append_assertion` 确认 transaction boundary

**关键观察**:

1. **零 shape conflict / 零 genuinely new**:invariant 层 design 没有跟 shipped "actively conflict",也没有引入全新 invariant 概念。所有差距都是 migration 性质。
2. **6 条 pure (f) target-gap**(INV-7b / INV-7c / INV-9 / INV-10 / INV-11 / INV-15)都聚焦在 **3 个 migration cluster**:
   - **Identity-as-Claim cluster**:INV-7b / INV-7c(Step 1 核心增量)
   - **System namespace cluster**:INV-9 / INV-10 / INV-11 / INV-12-part2 / INV-13 / INV-15(精简-3 + 精简-4 链式 migration)
3. **INV-7a (b)**:Step 1 时 `fg.fields.set` 应对 Identity 字段加 schema-aware 拒绝(目前只在 EntityEditor 内 enforce)
4. INV-3 待 Phase 3 verification(SQLite transaction boundary 完整性)

#### 5.1 浮出的 Q 候选(Phase 4 时 finalize)

5 个 Q candidates 从 I-series triage 浮出,**当前仅记录候选**,Phase 4 时跟 A-series + D-series 浮出的 Q 一起编号 + 加 input/scope/non-scope:

| 候选 | I-series 来源 | 议题 | 类别 |
|---|---|---|---|
| **Q-I1** | INV-7a (b) | Step 1 时 `fg.fields.set(IdentityField, ...)` 是否要 schema-aware 拒绝?Layer 2 是否承担 Identity 字段写入的拒绝(对应 INV-7c boundary)? | API surface enforcement layer |
| **Q-I2** | INV-7b | Identity Claim 在哪个层 emit?`fg.entities.create` 内部 emit(SDK 层),还是 ledger 写入路径 derive(application 层)? | INV-7b 实施位置 |
| **Q-I3** | INV-7c | INV-7c 策略 C 的 cache 加载 / invalidation / lookup 具体路径?SDK init 时建,还是 lazy?schema evolution hook? | INV-7c 实施细节 |
| **Q-I4** | INV-9 | `set_field` 何时加 `len(rest_terms) <= 1` runtime check?跟 PyReason adapter rewrite(Q-PR1)关系 — 是同 slice 同步,还是先 INV-9 enforce 推动 adapter rewrite? | INV-9 enforcement 时机 |
| **Q-I5** | INV-10 / INV-12-part2 | `__system__.*` rejection 在 application 层(SDK write shell)还是 protocol 层(`set_field`)?跟 INV-11 / INV-15 同 slice 链式 migration | INV-10/11/12/13/15 cluster 实施 |

## 6. Commitment Triage

### 6.1 I-series triage summary(Phase 2)

详见 §5.1 表格;A-series + D-series 留 Phase 3-4。

## 7. Stage 2 Questions

### 7.1 I-series Q candidates(Phase 2 surfaced;Phase 4 finalize)

详见 §5.1 表格末尾 5 个 Q-I1 → Q-I5 候选。**当前仅候选,Phase 4 时连同 A-series / D-series 浮出的 Q 一起 finalize + 编号 + 加 input/scope/non-scope/rejected alternatives 等 ADR structure 标记。**

### 5.2 A-series — Architecture commitment triage(Phase 3)

按 CADENCE Phase 3 "batches of 5" 组织:4 个 batch × 5-6 项。沿用 §2.0 5+1 state。

#### 5.2.1 Batch 1 — e_ref + Identity 模型(A1-A5)

| # | Architecture commitment | Design source | Shipped evidence | 分类 | Rationale + candidate Q |
|---|---|---|---|---|---|
| **A1** | **e_ref = typed content-derived constructor**(`idref_v1(EntityType, identity)`,X-style) | `identity-mechanism-redesign.zh.md:143-147` def 1 + `:327-365` Q1 idref_v1 lock | `core/protocol/idref_v1.py:67-73` `encode_idref_v1` 已 shipped 完整;`sdk/store.py:1916` 调用路径;`application/schema_runtime.py:367` 调用路径 | **(a) shipped covers** | typed Thing 完整 shipped(typed constructor 应用在 identity bundle 上,SHA-256+base32 输出 `idref_v1:<EntityType>:<digest>`)。**无 Q**。 |
| **A2** | **Identity = immutable anchor**(create 时 atomic 必填、single、参与 e_ref hash、不可修改) | `identity-mechanism-redesign.zh.md:149-152` def 2 + INV-7a `:248-261` | `sdk/schema.py:172-176` Entity 必须至少一个 `Identity(primary_key=True)` 否则 raise;`sdk/facade.py:448-479` `IdentityEditor` 三个 mutation 方法全 raise SDKStoreError | **(a) shipped covers** + **(b) small gap** | EntityEditor 内 immutable ✓ shipped;但 design §12.8 要求 **Layer 2 `fg.fields.set(IdentityField, ...)` 也拒绝**,目前 shipped `set_field`(`evidence/write_protocol.py:128-156`)不做 schema-aware 检查(它接受任何 pred_id)。**已浮 Q-I1**(Phase 2)— Phase 4 时跟 A2 关联。 |
| **A3** | **Field = mutable attribute**(revoke + append 走 ledger 生命周期,e_ref 跨 Field 变更稳定) | `identity-mechanism-redesign.zh.md:154-156` def 3 | `evidence/write_protocol.py:128-208` `set_field` / `add_field` / `retract_by_asrt` 完整 shipped;`sdk/facade.py:389-445` `FieldEditor` 完整;e_ref 不依赖 Field 值(idref_v1 只 hash identity) | **(a) shipped covers** | Field mutable 完整 ✓ shipped;append-only 通过 revoke+append 实现;e_ref 跨 Field 稳定(因为 e_ref hash 输入只含 identity,不含 Field)。**无 Q**。 |
| **A4** | **Identity-as-Claim = mirrored anchor facts**(Identity 值除了进 hash,还存为 Claim;Step 1 核心增量) | `identity-mechanism-redesign.zh.md:158-162` def 4 + INV-7b `:263-280` | `authoring/schema_compile.py:152-159` Identity predicate **declared** in schema_ir(`is_identity_field: True` flag,pred_id=`{owner_prefix}:{field_name}`);**但 Identity field Claim 本身 NOT emitted** — `application/entity_write.py:389` 处理 `record_exists`(emit `:exists` Claim)但 grep 无 Identity field Claim emission 路径;`sdk/facade.py:358-365` snapshot dot-access 走 `_identity_values` echo(从 caller kwargs)not from ledger | **(f) target-gap / pending migration** | **Step 1 核心增量**。infrastructure 已就绪(schema_ir 含 `is_identity_field` flag + pred_id 已 declare),只欠 emission 路径。**Q-I2 已浮**(Phase 2)— Q-I2 议题"Identity Claim 在哪层 emit",跟 A4 同一 implementation site。 |
| **A5** | **边界规则:未来可能变的值不要建模为 Identity** | `identity-mechanism-redesign.zh.md:166-176` 边界规则 | shipped 无强制 — `Identity` descriptor 接受任何字段(只要类型在 `CANONICAL_TAGS`);**当前 SDK 文档没有这条 schema 设计指南** | **(d) genuinely new**(documentation gap) | 这是 schema 设计**指导原则**而非可机械化的 invariant。**Q-A1 候选**:是否在 `Entity.Meta` 或 `_DataMember` 上加一个 `volatile=False` 显式 contract 让用户声明"我承诺这个字段不会变",还是仅文档化?(Phase 4 finalize) |

#### 5.2.2 Batch 2 — Form I schema 声明(A6-A10)

| # | Architecture commitment | Design source | Shipped evidence | 分类 | Rationale + candidate Q |
|---|---|---|---|---|---|
| **A6** | **Form I:Identity / Field 二分 + `_DataMember` 共通基类** | `identity-mechanism-redesign.zh.md:391-510` §8 Form I | `sdk/schema.py:50-141` `Identity` 与 `Field` 已分两类 descriptor ✓;但**无 `_DataMember` 中间基类**;两类各自继承 `_DeclaredMember`(`:20-47`)— 后者仅承载 descriptor 协议(`__set_name__` / `__get__` / `__set__`)不承载数据语义参数 | **(a) shipped covers**(二分 part)+ **(b) small gap**(无共通基类) | 二分 ✓ shipped;`_DataMember` 是小重构,把 `description` / `pattern` 等共通参数从 Identity/Field 各自定义提升到共通基类。**Q-A2 候选**:`_DataMember` 是否要暴露为 public API(`from factgraph.sdk import _DataMember`)还是 internal?(影响 user defined descriptor 扩展能力) |
| **A7** | **Cardinality 从类型注解推断**(`T` → single;`list[T]` → multi) | `identity-mechanism-redesign.zh.md:448-462` §8.4 | `sdk/schema.py:104-122` `Field(*, cardinality: str, ...)` cardinality 是**必填 kwarg**;**无类型注解推断逻辑**;`schema_compile.py:312-317` cardinality 验证只接受 `{"single","multi"}` 字符串 | **(b) small gap** + **(d) genuinely new**(推断 logic) | 现状 explicit kwarg 跟 design 推断不冲突,只是 ergonomic 差距。**Q-A3 候选**:是否 backward-compat 同时支持 explicit kwarg + 类型推断?还是 deprecate explicit kwarg(alpha 阶段直接 breaking)? |
| **A8** | **`Literal[...]` 枚举类型支持**(含 Layer 4 enum 约束 + `list[Literal[...]]` multi 形态) | `identity-mechanism-redesign.zh.md:451-462` §8.4 表 + `:464-470` enum 约束 | `core/schema/schema_ir.py` `CANONICAL_TAGS` shipped 8 tags 不含 enum;`schema_compile.py:240-244` 只校验 type_domain ∈ CANONICAL_TAGS;**无 enum_values 字段在 schema_ir 中** | **(d) genuinely new** | 全新 schema feature,需要 schema_ir 扩展(加 `enum_values: list[str]` 可选字段)+ schema_compile 路径接受 Literal 注解 + Layer 4 校验 `value ∈ enum_values`。**Q-A4 候选**:enum 约束在哪层校验?compile time(schema_compile.py 静态)还是 write time(`set_field` runtime)? |
| **A9** | **`_DataMember.pattern`**(regex 字段值校验,Layer 4) | `identity-mechanism-redesign.zh.md:472-488` §8.5 pattern | `sdk/schema.py:50-88` Identity / Field 都**无 pattern= 参数**;`schema_compile.py` 无 regex 字段;`evidence/write_protocol.py:128-156` `set_field` 无值 regex 校验 | **(d) genuinely new** | 全新 Layer 4 约束。infrastructure 几乎为零,Step 1 引入需要:descriptor 层加 `pattern=` + schema_ir 加 `pattern` 字段 + write path 加 regex 校验。**Q-A5 候选**:pattern 校验 compile time 还是 write time?是否同 A8 enum 一起设计(都是 Layer 4 value 约束)? |
| **A10** | **`description=` / `pattern=` 提升到 `_DataMember` 共通基类**;扩展位 `validators` / `constraints` / `alias` / `deprecated` / `examples` | `identity-mechanism-redesign.zh.md:497-510` §8.5 共通字段 + 扩展位 | `sdk/schema.py:104-112` `Field` 已有 `description: str \| None = None` 参数 ✓;`Identity` 无 `description` 参数;**两者都无 `pattern=`**;其他扩展位(validators/constraints/alias/deprecated/examples)都不存在 | **(b) small gap**(description part)+ **(d) genuinely new**(pattern + 扩展位) | `description` 从 Field 上移到共通基类是 small refactor。扩展位 Step 1 仅占位,Step 2+ 实现。**已 Q-A2 候选关联**(`_DataMember` public 性)。 |

#### 5.2.3 Batch 3 — API 三层 + AssertionView + `_meta`(A11-A15)

| # | Architecture commitment | Design source | Shipped evidence | 分类 | Rationale + candidate Q |
|---|---|---|---|---|---|
| **A11** | **API 三层分层**(`fg.entities.*` / `fg.fields.*` / `fg.assertions.*`,navigation key 即层边界) | `identity-mechanism-redesign.zh.md:790-960` §12.2 | `sdk/store.py` 当前 namespace map:**`fg.entities` 不存在**;**`fg.fields` 不存在**;`fg.assertions` shipped(`:436-485`)5 methods read-only(by_id/by_ids/active/all/field);`fg.read`(`:529-565`)/ `fg.write`(`:568-603`)是当前 read/write 入口 | **(c) shape conflict** + **(d) genuinely new** | shipped `fg.read` / `fg.write` 跟 design `fg.entities` / `fg.fields` namespace **结构 conflict**(同一功能不同分层);design 提议的 `fg.entities.create/where/exists/delete/edit` 和 `fg.fields.set/add/retract/delete/get` 大部分对应 shipped `fg.read.*` / `fg.write.*` 方法,但**重新分组**。**Q-A6 候选**:三层 migration 策略 — alpha 阶段直接 breaking rename(`fg.read.*` → `fg.entities.*` / `fg.write.*` → `fg.fields.*`)+ 加新方法?还是 namespace 并行(`fg.entities` 新加,`fg.read` 留做 deprecation alias)?(后者 user 在 §17 已 lock-in "完全删除 no alias"立场;但 audit 期需明确确认) |
| **A12** | **AssertionView 统一类型**(替代 shipped `AssertionNamespace` + `FieldAssertions`) | `identity-mechanism-redesign.zh.md:961-1050` §12.3 | `sdk/facade.py:204-330` `FieldAssertions`(per-field per-entity)+ `AssertionNamespace`(per-entity)是**独立 class**;无 `AssertionView` 统一概念;两者都接受 scope-bound 数据但不共享 method signature | **(c) shape conflict** + **(d) genuinely new** | 类型合并是 source-breaking 变更。design 把它们合并成 scope-aware 单一 `AssertionView` 类型。**Q-A7 候选**:合并时机 — Step 1 直接合并(breaking)还是 alpha 阶段引入新 `AssertionView` + 暂保留 `FieldAssertions` / `AssertionNamespace` deprecated alias?(同 A11,user §17 lock-in "no alias",audit 期确认) |
| **A13** | **AssertionView 招纳原则**(一等方法只授有特殊行为的能力:revoke 跟踪 / 时间维度 / asrt_id 索引 / scope 窄化;普通 meta equality 走 `where(_meta={...})`)| `identity-mechanism-redesign.zh.md:1027-1044` §12.3 招纳原则 | `sdk/facade.py:132-201` `AssertionRecordSet.where(value=, source=, trace_id=, version=, meta=)` shipped 半 flat 半 dict;`.at(t)` / `.version(v)` 一等 method shipped;`.history` 是 `.all` alias shipped;**`version` 没被剔除(违反招纳原则)** | **(c) shape conflict** | shipped `version(v)` 是一等方法但无特殊行为(等价于 `where(_meta={"version":v})`),跟设计的招纳原则冲突。removal 会 break 现有 caller。**Q-A8 候选**:招纳原则 enforcement — version 是 hard remove(breaking)还是先 `DeprecationWarning` 一个版本周期?(user §17 lock-in "no alias / breaking"立场) |
| **A14** | **`_meta` 统一 meta 输入**(所有 meta 过滤走 `_meta={...}` dict,折叠 shipped `source=/trace_id=/version=` flat kwargs) | `identity-mechanism-redesign.zh.md:1097-1170` §12.4 | `sdk/facade.py:132-160` `AssertionRecordSet.where(value=, source=, trace_id=, version=, meta=)` 是 half-flat half-dict shipped 形态 | **(c) shape conflict** | flat kwargs 跟 dict 同时存在,**接口形态不统一**。design 提议折叠。**Q-A9 候选**:折叠时机和兼容期 — Step 1 直接 breaking(flat kwargs raise)还是 alpha 阶段双向接受?(`_meta` 反义性:shipped `meta=` 跟 design `_meta=` 命名都改) |
| **A15** | **6 条硬定义**(Rule 1-6:sentinel / at-version 默认 active / by_id 走 all / history 弃用 / retract 不在 view / ledger scope 拒字符串)| `identity-mechanism-redesign.zh.md:1180-1260` §12.5 | `sdk/facade.py:135-160` `_ASSERTION_FILTER_MISSING` sentinel **已 shipped**(Rule 3 ✓);`.history` shipped 是 `.all` alias(Rule 4 半 covered);`.at(t)` / `.version(v)` shipped 隐含基于 `.active`(Rule 4 ✓);`by_id` 走 history(Rule 5 ✓);**retract 在 AssertionView 上 N/A(没有 retract 方法)**(Rule 5 vacuously satisfied);**`fg.assertions.field(F)` 接受 Field descriptor**(Rule 6 ✓);**但 ledger scope vs entity scope 边界 shipped 还是用同一 Field descriptor 处理,Rule 6 字符串拒绝逻辑未实施** | **(a) shipped covers**(Rules 1,3,4 part,5,6 part)+ **(b) small gap**(Rule 4 history 应弃用 warning + Rule 6 ledger scope 字符串拒绝) | 多数 Rule 已 implicitly 满足;少数需要小 gap 修补。**Q 不浮**,作为 implementation detail 进 Step 1 blueprint |

#### 5.2.4 Batch 4 — Identity boundary + schema 管理 + ledger 同步(A16-A21)

| # | Architecture commitment | Design source | Shipped evidence | 分类 | Rationale + candidate Q |
|---|---|---|---|---|---|
| **A16** | **Identity 三层 immutable boundary**(Layer 1 entities.edit / Layer 2 fields.set / Layer 3 assertions.retract 全部拒绝改 Identity) | `identity-mechanism-redesign.zh.md:1289-1320` §12.8 | Layer 1:`sdk/facade.py:448-479` `IdentityEditor` 拒 ✓;Layer 2:`evidence/write_protocol.py:128-156` `set_field` **不区分** Identity/Field(只看 pred_id 字符串);Layer 3:`evidence/write_protocol.py:170-208` `retract_by_asrt` **不区分** Identity Claim/Field Claim(只看 asrt_id 存在性) | **(a) shipped covers**(Layer 1)+ **(f) target-gap**(Layer 2 + Layer 3 — 当前没有 Identity Claim 所以 vacuously 满足,但 Step 1 必须 enforce) | Layer 1 ✓;Layer 2+3 跟 INV-7c 同 implementation site。**已 Q-I1**(fields.set 拒绝)+ **已 Q-I3**(INV-7c 策略 C cache 实施) |
| **A17** | **`fg.schema.register / extend / apply` 三分**(替代混杂 `fg.schema.add`)| `identity-mechanism-redesign.zh.md:1322-1410` §12.9 | `sdk/store.py:518` `_SDKSchemaManager.add(*classes, **kwargs)` 单一入口;无 `register` / `extend` / `apply` 区分;**未实施 additive-only 检查** | **(c) shape conflict** + **(d) genuinely new** | `add` 当前混杂"register 新类型"和"extend 已有类型",per PDF Change Request triage 已 user-accepted 三分(详见 identity §15 决策日志)。**Q-A10 候选**:三分后 `add` deprecation 策略?(user §17 立场 "no alias",audit 期 confirm) |
| **A18** | **Schema evolution 约束:不允许 Identity↔Field 互转 / 新增 Identity / 删除字段**(配套 INV-7c 实施策略 C) | `identity-mechanism-redesign.zh.md:1392-1410` §12.9 schema evolution 约束 | shipped `fg.schema.add` 无 diff 检查;无 additive-only enforce;Identity↔Field 互转技术上当前 evolves 时不被禁止;**这是 design 新增 invariant,不在 shipped enforcement 里** | **(d) genuinely new** | Schema evolution 约束 Step 1 必须随 INV-7c 实施。**Q 不独立**,跟 Q-I3(INV-7c cache lifecycle)+ Q-A10(schema 三分)同 implementation slice |
| **A19** | **3-table ledger schema 终态**(claims + claim_meta + ledger_meta) | `ledger-schema-specification.zh.md:105-160` §3 | `core/store/ledger.py:81-159` shipped **7 张表**:claims + claim_args + meta_rows + revokes + ingest_keys + ledger_meta + annotation_rows | **(f) target-gap / pending migration** | 7 数据精简 migration 目标;Step 1 / Step 1+ 分批落地。**已浮 cluster level Q**(Phase 2 system namespace cluster Q-I5 涉及);新增 **Q-A11 候选**:7 步精简 migration 是单 slice 还是分阶段?哪些精简跟 Step 1 Identity-as-Claim 同步落地,哪些可独立? |
| **A20** | **`:exists` Claim 标记为 legacy/transitional**(Step 1 后实质冗余,Identity 镜像 Claim 已是 entity 存在性证据) | `ledger-schema-specification.zh.md:142-155` §3.1 :exists 注 + `:296-300` §4.7 boundary | `authoring/schema_compile.py:140-150` `<EntityType>:exists` 已 declared in schema_ir;`application/entity_write.py:389` `record_exists` op 已 shipped → emit `:exists` Claim;**当前 shipped 是"实质 truth"形态,不是 legacy**(因为 Identity Claim 未 emit) | **(a) shipped covers** + **(f) target-gap**(legacy 降级需 Identity Claim emit 后) | 跟 INV-7b / A4 (Identity-as-Claim) 同 cluster — Identity Claim emit 后 `:exists` 才能 transitional/legacy 降级。**Q-A12 候选**:Step 1 后 `:exists` Claim emission 是同步移除(breaking)还是双写一段时间然后剔除?(影响 read path 兼容性) |
| **A21** | **7 数据精简 migration path**(meta+annotation 合并 / 删 namespace+category+derivation / revokes→__system__.revokes Claim / rest_terms→value+value_tag / fact_meta→claim_meta / ingest_keys 删 / 复合 PK) | `ledger-schema-specification.zh.md:710-790` §9 | `core/store/ledger.py:81-159` shipped 7 tables 是 migration 起点;**zero migration 实施 shipped** | **(f) target-gap / pending migration** | migration plan 是 design 主体;实施分阶段。**已 Q-A11 候选**(migration 切片策略) |

### 5.2 A-series 总结

**21 条 architecture commitment 的分类分布**:

| 桶 | A 数 | 列表 |
|---|---:|---|
| (a) shipped covers | 3 | A1 / A3 / A15(多 Rule 已隐含满足) |
| (a)+(b) | 3 | A2 / A6 / A10 |
| (a)+(f) | 2 | A16 / A20 |
| (b)+(d) | 1 | A7 |
| (c) shape conflict | 0 pure | — |
| (c) + (d) | 4 | A11 / A12 / A17 / [A14 部分] |
| (c) 单独 | 2 | A13 / A14 |
| (d) genuinely new | 3 | A5 / A8 / A9 / A18(纯新增) |
| (f) pure target-gap / pending migration | 3 | A4 / A19 / A21 |

(分类总和 > 21 因有 split 项)

**关键观察**(per user reviewer 2026-05-29 提示的 cluster 识别):

#### 新增 migration clusters(per user Phase 3 预测)

Phase 2 已识别 3 cluster;A-series 浮出 2 个新 cluster:

| Cluster | 涉及 commitments / invariants | 说明 |
|---|---|---|
| 4. **Form I + descriptor 扩展 cluster** | A6 / A9 / A10 + A8(Literal)| `_DataMember` 共通基类 + pattern + Literal 枚举 + Identity description 提升,**作为 schema descriptor 一次性重构**;Step 1 同 slice 落地最高效 |
| 5. **API namespace 三层重组 cluster** | A11 / A12 / A13 / A14 / A15(部分)+ A17 | `fg.read` / `fg.write` / `fg.assertions` → `fg.entities` / `fg.fields` / `fg.assertions` + AssertionView 统一 + `_meta` 统一 + `fg.schema` 三分 + 招纳原则 enforcement,**作为 API surface 一次性重组**;Step 1 同 slice 落地最高效但工作量最大 |

#### 浮出的 A-series Q candidates(Q-A1 → Q-A12,Phase 4 finalize)

| 候选 | A 来源 | 议题 | 类别 |
|---|---|---|---|
| **Q-A1** | A5 | `volatile=False` 显式 contract 还是文档化边界规则? | Schema 设计指导 |
| **Q-A2** | A6 + A10 | `_DataMember` 是否暴露为 public API? | descriptor 扩展性 |
| **Q-A3** | A7 | Cardinality 推断 backward-compat 还是 alpha breaking? | schema syntax migration |
| **Q-A4** | A8 | enum 约束在 compile time 还是 write time 校验? | Layer 4 enforcement layer |
| **Q-A5** | A9 | pattern 校验 compile time 还是 write time?跟 A8 enum 一起设计? | Layer 4 enforcement layer |
| **Q-A6** | A11 | 三层 namespace migration 策略 — alpha breaking rename 还是并行 alias? | API namespace 重组 |
| **Q-A7** | A12 | AssertionView 类型合并时机 — Step 1 breaking 还是 deprecated alias 一周期? | 类型 surface 重组 |
| **Q-A8** | A13 | `version(v)` 招纳原则 enforcement — hard remove 还是 DeprecationWarning 周期? | 招纳原则迁移 |
| **Q-A9** | A14 | `_meta` 统一 — 直接 breaking 还是双向接受期? | meta surface 迁移 |
| **Q-A10** | A17 + A18 | `fg.schema.add` 三分后 deprecation;schema evolution 约束跟 INV-7c 同 slice 还是独立 | schema 三分 + evolution |
| **Q-A11** | A19 + A21 | 7 数据精简 migration 切片策略 — 哪些跟 Step 1 同步,哪些独立 | ledger migration 切片 |
| **Q-A12** | A20 | `:exists` Claim emission 移除时机 — Step 1 后同步移除 vs 双写过渡 | `:exists` legacy 降级 |

#### Q-A 跟 Q-I 关联 / 合并候选(per user reviewer Phase 4 guidance)

- **Q-I1 + A2**:都是 Layer 2 `fields.set` 拒绝 Identity 写入;Phase 4 可合并
- **Q-I2 + A4**:都是 Identity Claim emission 路径;Phase 4 同 Q
- **Q-I3 + A16 + A18**:都是 INV-7c cache lifecycle / Layer 2-3 boundary + schema evolution;Phase 4 同 cluster 评估
- **Q-I4 + Q-A11**:INV-9 enforcement timing 嵌在 ledger migration 切片策略里;Phase 4 评估是否合并
- **Q-I5 + A19 (system namespace cluster)**:`__system__.*` rejection 跟 revokes 表迁移 + INV-15 default filter 链式;Phase 4 同 cluster

### 6.2 A-series triage summary(Phase 3)

详见 §5.2 各 batch 表 + §5.2 总结。

### 7.2 A-series Q candidates(Phase 3 surfaced;Phase 4 finalize)

详见 §5.2 末尾 12 个 Q-A1 → Q-A12 候选 + Q-I 跟 Q-A 关联清单。Phase 4 时统一编号 + 加 ADR structure。

### 5.3 D-series — Cross-doc seams + specific discrepancies(Phase 4)

I-series 覆盖 invariant 层;A-series 覆盖 architecture commitment 层;**D-series 是 cross-doc seam + 具体 shipped contract 不一致**项(已 published docs / module docs / public quickstart 会随 Step 1 stale)。

| # | Cross-doc / contract location | Design impact | shipped current state | 分类 | Stage 4 docs slice 处理 |
|---|---|---|---|---|---|
| **D1** | `src/factgraph/sdk/docs/04_api_surface.en.md` §0 Namespace Map 第 23-24 行示例 `fg.read.get(User, user_id="u-1")` / `fg.write.add(User.tag, alice, "engineer")` | A11(三层重组)— `fg.read` / `fg.write` 替换为 `fg.entities` / `fg.fields` | shipped 权威文档 | **(c) shape conflict**(doc-level) | docs sync slice;Step 1 与 API slice 同周期 update |
| **D2** | `04_api_surface.en.md` §2.3 / §2.4 / §2.5 / §2.6+ namespace 表格 | A11 + A17 — 表格结构按 fg.entities / fg.fields / fg.assertions / fg.schema 三分重写 | shipped doc 描述 `fg.read.get/find/match/ref` / `fg.write.set/add/retract/edit` / `fg.assertions.by_id/by_ids/active/all/field` / `fg.schema.add/ingest/validate_provenance` | **(c) shape conflict**(doc-level) | docs sync slice;新增 `fg.entities.create/where/exists/delete` / `fg.fields.retract/delete/get` / `fg.assertions.where/retract` / `fg.schema.register/extend/apply` 表 |
| **D3** | `04_api_surface.en.md` §4 `FieldAssertions, AssertionRecordSet, AssertionRecord, AssertionMeta` types section | A12(AssertionView 统一)— `FieldAssertions` 合并进 `AssertionView`;独立类型删除 | shipped doc 描述独立 `FieldAssertions` 类型 + `AssertionNamespace` 间接覆盖 | **(c) shape conflict**(doc-level) | docs sync slice;type 重组同步 |
| **D4** | `docs/official/kernel/quickstart/assertions.md` line 145 `valid_from / valid_to | Used by .at(t)` | A15 Rule 4(at 默认 active)+ Step 2+ `during` planned | shipped `.at(t)` 用 valid_from/valid_to 半开区间(per A15 ✓);Step 2+ `during((t1, t2))` 还没 doc | **(a) shipped covers** + **(e) deferred-aligned** | docs Step 1 sync slice 仅小修;`during` Step 2+ 文档扩展 |
| **D5** | `assertions.md` lines 307-308 `.at(t) = .active.at(t)` + `.version(v) = .active.version(v)` shortcuts | A13 招纳原则 + A15 Rule 4 — `.at(t)` 留;**`.version(v)` 删除**(普通 meta equality 不上一等方法) | shipped doc 文档化 `.version(v)` 一等方法 | **(c) shape conflict**(doc-level) | docs sync slice;`.version()` 删除文档 + 改用 `.where(_meta={"version": v})` 等价示例 |
| **D6** | `assertions.md` line 348 `.where(value=..., source=..., trace_id=..., version=..., meta={...})` table row | A14 `_meta` 统一 — flat `source/trace_id/version` kwargs 折叠进 `_meta={...}` | shipped doc 描述 half-flat half-dict | **(c) shape conflict**(doc-level) | docs sync slice;`.where` signature 改 `(value=, value_tag=, _meta={...})` |
| **D7** | `assertions.md` lines 599-602 "fg.assertions.where(...), fg.assertions.at(...) are intentionally NOT supported" | A11(三层重组)+ A12(AssertionView)— design **ADDS** `fg.assertions.where(field=, e_ref=, value=, value_tag=, _meta=)` 作为 canonical ledger filter;assertions namespace 上的 `at(...)` 不上(留 view scope `.at(t)`)|✗| 直接与 design 矛盾的 doc 陈述 | **(c) shape conflict**(doc-level — 关键!) | docs sync slice;line 599-602 必须重写 — 改为 "fg.assertions.where(...) shipped after Step 1;fg.assertions.at(...) intentionally NOT supported(time semantics 仅在 view scope)" |
| **D8** | `04_api_surface.en.md` §2.14 `FrozenAssertionView` type 命名 | PDF triage C6 — `FrozenAssertionView` → `FrozenAssertionSet` / `AssertionIdSet`(Step 2+) | shipped FrozenAssertionView 类型 | **(e) deferred-aligned**(Step 2+) | docs Step 2+ 重命名同步 |
| **D9** | `04_api_surface.en.md` §2.14 + `fg.views` namespace | PDF triage C5 — `fg.views` → `fg.assertion_views`(Step 2+) | shipped `fg.views.create/update/delete/get/list` | **(e) deferred-aligned**(Step 2+) | docs Step 2+ namespace 重命名同步 |
| **D10** | `core/store/ledger.py:512-580+` `append_claim` / `append_claim_args` / `append_meta_rows` 等 deprecated public 方法 | INV-1 + INV-3 — deprecated 路径仍存在,可能 Step 1+ cleanup 时移除 | shipped 标 `deprecated::` 提示但仍 public | **(b) small gap**(cleanup-eligible) | 跟随 ledger migration slice 时一并 evaluate 删除 |
| **D11** | `core/store/_builders.py:315-318` `is_entity_exists` + `is_identity_field` flag 使用点 | A4(Identity-as-Claim emission)+ A20(`:exists` legacy 降级)| shipped `is_identity_field` flag declared in schema_ir(`schema_compile.py:256`)但 **Identity field Claim 本身 NOT emitted**;`is_entity_exists` flag 用于 `:exists` Claim emit via `application/entity_write.py:389 record_exists` op | **(f) target-gap / pending migration** | Identity Claim emission slice;同 INV-7c implementation |

### 5.4 N-series — Verified shipped honors design(positive findings,Phase 4 verification 结果)

记录 audit 过程中**spot-check 完成 + 确认 shipped honors design** 的 finding,作为正面 baseline(避免后续 slice 误认为 gap):

| # | Item | Verification evidence | Status |
|---|---|---|---|
| **N1** | INV-3 SQLite 单事务原子写 | `core/store/ledger.py:430-451` `append_assertion` uses `with self._write_session() as (conn, post_commit)` 单 connection;所有 inserts(claims/claim_args/meta_rows/annotation_rows/ingest_keys)在同一 `_conn` context;`post_commit` hook 延迟 in-memory cache flip 到 DB commit 后。`append_revocation`(`:492-510`)同样模式 | ✅ Phase 4 final spot-check 通过 — INV-3 完整 honored |
| **N2** | Identity field 在 schema_ir 已 declared(为 Step 1 emission 提供 infrastructure) | `authoring/schema_compile.py:152-159` 每个 Identity field 生成 predicate with `is_identity_field: True` flag + pred_id `{owner_prefix}:{field_name}`;`is_identity_field` flag 在 `_builders.py:317` / `derivation_compile.py:365` / `where_schema_lowering.py:74` 多处被读取使用 | ✅ Step 1 Identity Claim emission **不需要新 schema_ir 字段** — 复用现有 `is_identity_field` flag |
| **N3** | `:exists` Claim emission 路径 shipped | `application/entity_write.py:389` `op == "record_exists"` handler;`schema_compile.py:140-150` 已 declare `<EntityType>:exists` predicate with `is_entity_exists: True`;`application/protocol/entity_write.py:90` 协议接口含此 op | ✅ `:exists` Claim Step 1 transitional 降级 **不破坏现有 emission 路径**;只需 Identity Claim emission 启用后 `:exists` 加冗余降级 |
| **N4** | `IdentityEditor` immutability shipped(per INV-7a Editor part) | `sdk/facade.py:448-479` 三个 mutation 方法 `set` / `add` / `retract` 全部 raise `SDKStoreError("identity field is immutable in editor; open a new editor with different identity instead")` | ✅ INV-7a Layer 1 editor-time immutability 完整 honored |
| **N5** | `encode_idref_v1` typed content-derived hash 路径完整 | `core/protocol/idref_v1.py:67-73` 完整;`sdk/store.py:1916` + `application/schema_runtime.py:367` 两个调用点都 use canonical Identity bundle;`tup_v1` 8 tag 协议稳定 | ✅ X-style typed Thing constructor 完整 shipped — A1 / Q1 idref_v1 lock 不需要新 implementation |

## 6. Commitment Triage

### 6.3 Total triage summary(Phase 4)

合 §5.1 / §5.2 / §5.3 — **48 项 finding 总分类**:

| 桶 | I-series | A-series | D-series | 合计 |
|---|---:|---:|---:|---:|
| (a) shipped covers | 7 | 3 | 0 | 10 |
| (a)+(b) / (a)+(f) / (b)+(d) 混合 | 3 | 5 | 0 | 8 |
| (b)+(d) | — | 1 | 0 | 1 |
| (b) small gap | — | — | 1 | 1 |
| (c) shape conflict / (c)+(d) | 0 | 6 | 6 | 12 |
| (d) genuinely new | 0 | 4 | 0 | 4 |
| (e) deferred-aligned | 0 | 0 | 2 | 2 |
| (f) pure target-gap | 6 | 3 | 1 | 10 |

(部分 finding 跨多桶,所以总和 > 单 finding 计数)

**关键观察**(全局):
1. **Zero pure (c) shape conflict 在 invariant 层** — 没有 ledger / Identity invariant 直接 conflict shipped(全是 target-gap)
2. **(c) shape conflict 集中在 API surface + 已发布 docs** — 6 项 A-series + 6 项 D-series — 这是 Step 1 主要 migration 复杂度来源
3. **(f) target-gap 集中在 Step 1 + 精简-migration** — Identity-as-Claim cluster(I/A 4 项)+ system namespace cluster(I 4 项 + A 1 项)
4. **(e) deferred-aligned 仅 2 项** — `FrozenAssertionView` 重命名 + `fg.views` 重命名(都 Step 2+)
5. **INV-3 + Identity schema_ir infrastructure + idref_v1 全 shipped** — Step 1 实施有非常 solid baseline

## 7. Stage 2 Questions

### 7.3 Q finalize(Phase 4) — 17 Qs with ADR skeleton

per user reviewer 2026-05-29 Phase 4 guidance:**保留粒度,不急合并**。每个 Q 加 ADR 入口字段(Q-D? 是 cross-doc 性质,合并到 Q-A 中)。完整 ADR doc 在 Stage 2 独立分支 + 独立 ADR file。

#### Q list

| Q | Title | Source | Decision target | Cluster | Slice(per §10) |
|---|---|---|---|---|---|
| **Q1** | `fg.fields.set(IdentityField, ...)` schema-aware rejection at Layer 2 | Q-I1 + A2 / A16 | 是否在 Layer 2 拒绝 Identity 写入(SDK 端 application 层 schema-aware check)?vs 仅在 `fg.assertions.retract` 应用 INV-7c? | Identity-as-Claim cluster | Slice 2 |
| **Q2** | Identity Claim emission layer(SDK `create` 内 vs application 层 derive) | Q-I2 + A4 + N2 + N3 | 复用现有 `is_identity_field` flag,Identity Claim emission 路径具体在哪层?`fg.entities.create` SDK shell 内 emit 还是 application 层(类似 `record_exists` op)自动 derive? | Identity-as-Claim cluster | Slice 2 |
| **Q3** | INV-7c 策略 C cache lifecycle(init/lazy/schema-evolution hook) | Q-I3 + A16 + A18 | Identity pred_id set 何时建?启动时一次扫 schema_ir;lazy 第一次 retract 时建;schema.extend/register 触发重建。3 选 1 + invalidation/concurrency 行为 | Identity-as-Claim cluster | Slice 2 |
| **Q4** | INV-9 enforcement timing vs Q-PR1 adapter rewrite 解耦 | Q-I4 + A19 + A21 | per user reviewer Phase 3 guidance:**不让 Step 1 被 adapter rewrite 阻塞**。INV-9 strict enforcement(set_field len<=1 check)能否独立于 PyReason adapter rewrite?option (a) Step 1 INV-9 strict + adapter 同步 rewrite;(b) Step 1 不 enforce INV-9,留 Step 2+ adapter rewrite slice 一起 lock | System namespace cluster + adapter | Slice 3b + 5(Step 2+) |
| **Q5** | `__system__.*` rejection enforcement layer | Q-I5 + A19 | rejection 在 application 层(SDK shell)还是 protocol 层(`set_field`)?protocol 层更严(防 internal API 误用)但跟 internal `retract_by_asrt` 路径(本身写 `__system__.revokes`)冲突 — 需 internal/external API 分离 | System namespace cluster | Slice 3a |
| **Q6** | Boundary rule: mutable Field 设计 contract — `volatile=False` 显式 vs 文档化 | Q-A1 | 是否在 descriptor 上加 `volatile: bool = False` 显式 contract(违反时 schema validation 提示);还是仅作为 schema 设计 best-practice 文档(没有机械 enforce) | Form I cluster | Slice 1 + 4(docs) |
| **Q7** | `_DataMember` 共通基类 public API exposure | Q-A2 + A10 | `_DataMember` 是否暴露为 public API(`from factgraph.sdk import _DataMember`)— 影响 user-defined descriptor extension 能力;还是 internal? | Form I cluster | Slice 1 |
| **Q8** | Cardinality 推断 backward-compat strategy | Q-A3 + A7 | alpha 阶段直接 breaking(`Field()` 必须无 cardinality kwarg,从类型推断)还是 backward-compat(同时支持 explicit + 推断)?user §17 lock-in "no alias",audit 期 confirm | Form I cluster | Slice 1 |
| **Q9** | Layer 4 enum/pattern validation layer(compile-time vs write-time) | Q-A4 + Q-A5 + A8 + A9 | Literal enum + pattern regex 在哪验?(a) compile time(`schema_compile.py` static)— 用户写错立刻报;(b) write time(`set_field` runtime)— 数据写入前最后一道关卡;(c) 两层都做 | Form I cluster | Slice 1 |
| **Q10** | API namespace 3-layer migration strategy | Q-A6 + A11 | alpha 直接 breaking rename(`fg.read.*` → `fg.entities.*`;`fg.write.*` → `fg.fields.*`)+ 加新方法?vs namespace 并行(新加 entities/fields,read/write 留 deprecated alias)?user §17 lock-in "no alias",audit 期 confirm | API namespace cluster | Slice 3a |
| **Q11** | AssertionView 类型合并时机 | Q-A7 + A12 | Step 1 直接合并 `FieldAssertions` + `AssertionNamespace` 入 `AssertionView`(breaking)还是 Step 1 引入 `AssertionView` + 保留 deprecated alias 一周期 | API namespace cluster | Slice 3a |
| **Q12** | `version(v)` 招纳原则 enforcement strategy | Q-A8 + A13 + D5 | hard remove(breaking;cleanest)还是 `DeprecationWarning` 一周期(softer)?docs `assertions.md` 同步删 | API namespace cluster | Slice 3a + 4(docs) |
| **Q13** | `_meta` 统一 — flat kwargs 删除策略 | Q-A9 + A14 + D6 | shipped `where(source=, trace_id=, version=, meta=)` flat kwargs 直接 breaking 删?还是双向接受(both `source=` flat 和 `_meta={"source": ...}`)一周期? | API namespace cluster | Slice 3a + 4(docs) |
| **Q14** | `fg.schema.add` 3-way split + schema evolution constraint slice grouping | Q-A10 + A17 + A18 | `register/extend/apply` 三分跟 schema evolution `extend` 拒绝 Identity↔Field swap 是同 slice 还是分?三分本身 vs evolution enforcement 的 dependency | API namespace cluster | Slice 3a |
| **Q15** | 7 数据精简 migration slice strategy | Q-A11 + A19 + A21 + D10 | 7 步精简 → 几个 implementation slice?Step 1 跟随哪些?哪些独立 slice?跟 Q4(INV-9 adapter coupling)关联 | Ledger migration cluster + System namespace cluster | Slice 3a + 3b |
| **Q16** | `:exists` Claim emission removal timing | Q-A12 + A20 + D11 | Step 1 Identity Claim emission 后,`:exists` 同步移除(breaking;clean)?vs 双写一段时间然后剔除(read path 兼容性)?vs 永久保留为 legacy emission(无强制) | Identity-as-Claim cluster | Slice 2 |
| **Q17** | Cross-doc + public quickstart sync timing | D1-D9 cumulative | docs `04_api_surface.en.md` + `assertions.md` 是 Step 1 各 slice 完成后立即同步,还是合并到一个 docs sync slice 最后一起做?后者干净,前者 step-by-step shippable | Docs cluster | Slice 4 |

#### Q 跨 cluster 依赖图(simplified)

```text
Form I cluster (Q6 / Q7 / Q8 / Q9)
   │ slice 1 完成提供 _DataMember + Identity/Field 二分基础
   ↓
Identity-as-Claim cluster (Q1 / Q2 / Q3 / Q16)
   │ slice 2 完成提供 Identity Claim emission + INV-7c enforcement
   ↓
API namespace cluster (Q10 / Q11 / Q12 / Q13 / Q14)
   │ slice 3a 完成提供 entities/fields/assertions 三层 + AssertionView
   ↓
System namespace cluster (Q4 / Q5 / Q15) ⇆ adapter rewrite slice 5 (Step 2+)
   │ slice 3b 部分 — INV-9 strict + revokes → __system__ 取决于 Q4 decision
   ↓
Docs cluster (Q17)
   │ slice 4 完成 — 04_api_surface + assertions.md + 其他 quickstart sync
```

## 8. Reviewer focus

按重要性排序,后续 reviewer(Stage 2 ADR / Stage 4 blueprint preflight)应该特别关注:

1. **Q1 / Q2 / Q3 cluster 的 implementation interaction** — Identity Claim emission(Q2)→ Identity pred_id set cache 建立(Q3)→ Layer 2 fields.set boundary check(Q1)是 chain dependency,3 个 Q 必须 cohesive decisions 否则 INV-7c 实施分裂
2. **Q4 vs Q-PR1 cluster 分离** — per user reviewer:identity-as-claim Step 1 **不能被 adapter rewrite 阻塞**。Q4 decision 必须明确 Step 1 INV-9 enforcement scope(可能弱化为"identity Claim 是 unary,Field Claim 也是 unary,只有 adapter 写的 edge Claim 暂时是 n-ary,标 known-exception 直到 Step 2+ adapter rewrite")
3. **Q10 / Q11 / Q12 / Q13 cluster 跟 docs slice(Q17)同步** — API surface 大改动 + public docs 同步,任何一项掉队就形成 cross-doc drift
4. **N2 / N3 / N5 baseline 是 Step 1 implementation 的 advantage** — Identity field 已 declared in schema_ir + `:exists` emission 路径已存在 + idref_v1 完整 shipped,大幅降低 Slice 2 实施风险
5. **D7 "fg.assertions.where intentionally NOT supported" doc seam 是高优** — 不及时删 docs 会让 users 学错的契约;Step 1 docs slice(Slice 4)首条目

## 9. Acceptance Criteria

本 audit 的 acceptance:

- [x] Phase 1 inventory:design-points referenced + shipped 文件 inventory 完整(§3 + §4 + §4.10)
- [x] Phase 2 I-series:16 invariants 全部 triage,5+1 state 分类完整,5 Q candidates 浮(§5.1 + §6.1 + §7.1)
- [x] Phase 3 A-series:21 architecture commitments 全部 triage,4 batches × 5-6,12 Q candidates 浮 + Q-I ↔ Q-A 关联(§5.2 + §6.2 + §7.2)
- [x] Phase 4 D-series:cross-doc seams + 具体 contract discrepancies 11 项 triage,5+1 state 分类(§5.3)
- [x] Phase 4 N-series:5 positive findings(INV-3 + schema_ir Identity infrastructure + `:exists` emission + IdentityEditor immutability + idref_v1)— 提供 Step 1 implementation baseline confidence(§5.4)
- [x] Phase 4 total triage:48 finding 全局分类汇总(§6.3)
- [x] Phase 4 Q finalize:17 Qs with ADR skeleton(scope/decision target/cluster/slice membership)— ready for Stage 2 ADR drafting(§7.3)
- [x] Phase 4 reviewer focus:5 高优 reviewer 关注点(§8)
- [x] Phase 4 recommended implementation slice order(per user reviewer 2026-05-29 新增需求 — §10)
- [x] Cross-doc seams 11 项识别(§5.3 D1-D9)
- [x] INV-3 transaction boundary final spot-check 完成(§5.4 N1)
- [x] Phase 4 published reference docs row-drafting time re-read(`04_api_surface.en.md` + `assertions.md` cross-doc seam 部分)

## 10. Recommended Implementation Slice Order

**per user reviewer 2026-05-29 Phase 4 新增需求**:不仅出 Q list,也出 recommended slice 顺序作为 Stage 3 synthesis 的输入。

### 10.1 Slice 顺序(按依赖排)

```text
Slice 1 — Schema / Form I refactor                              [Step 1, foundational]
  └ Q6 / Q7 / Q8 / Q9
  └ _DataMember 共通基类 + Identity/Field 二分(已 partial shipped 微调)
  └ description 提升 + pattern 新增 + cardinality 推断 + Literal 枚举
  └ schema_compile 路径接受新 descriptor 形态
  └ 不动 ledger / API namespace / docs(只动 SDK schema 层 + schema_ir)
  └ 完成度高时 ship gate;不强制等其他 slice

Slice 2 — Identity Claim emission + INV-7c implementation       [Step 1, depends on Slice 1]
  └ Q1 / Q2 / Q3 / Q16
  └ Identity Claim emission 路径(复用 is_identity_field flag,在 N2 baseline 上加 emission)
  └ INV-7c 策略 C — Identity pred_id set + retract path lookup + schema-evolution hook
  └ `:exists` Claim 处理(legacy/transitional 标 + 可选移除)
  └ Layer 1/2/3 三层 Identity write boundary enforce
  └ 必须 Slice 1 (_DataMember + Identity descriptor 稳定) 后做

Slice 3a — API surface 三层重组 + AssertionView 统一            [Step 1, depends on Slice 1+2]
  └ Q5 / Q10 / Q11 / Q12 / Q13 / Q14
  └ fg.read/write → fg.entities/fields(rename + 重组)
  └ fg.entities 新方法:create / where / exists / delete(create 依赖 Slice 2 Identity emission)
  └ AssertionView 统一(合并 FieldAssertions + AssertionNamespace)
  └ _meta 统一 meta 入口(flat → dict)
  └ version() 招纳原则 enforce
  └ fg.schema 三分(register/extend/apply)+ evolution 约束 enforce
  └ __system__.* rejection(per Q5 decision)
  └ 最大工作量 slice;Step 1 收尾

Slice 3b — Ledger schema partial migration(NOT 同步 INV-9 strict)[Step 1, parallel-eligible with 3a]
  └ Q4(部分 — Step 1 INV-9 weak enforce,strict 留 Step 2+)/ Q15
  └ 3-table consolidation 部分:meta_rows → claim_meta 改名 + 复合 PK
  └ revokes 表 → __system__.revokes Claim(per Q5 decision 配合)
  └ ingest_keys 删除(per 精简 6)
  └ 暂时 NOT enforce INV-9 strict(`len(rest_terms) <= 1`)— 留 Q-PR1 adapter rewrite slice
  └ 可跟 Slice 3a 并行(不同模块,无 schema 依赖)

Slice 4 — Docs / public quickstart sync                         [Step 1, depends on Slice 1-3]
  └ Q17 + D1-D9 cumulative
  └ 04_api_surface.en.md 全面 rewrite(namespace 三层 + AssertionView + _meta 等)
  └ assertions.md 删 .version(v) + 改 _meta + 删 D7 误导 line 599 陈述
  └ 其他 quickstart docs Identity-as-Claim 概念引入
  └ docs/references/* 静态 cross-ref 修正
  └ 必须 Slice 1+2+3 都稳定后做 — 否则 docs 跟代码漂移
  └ docs-only slice(无代码 surface 改动)

Slice 5+ (Step 2+) — Q-PR1 PyReason adapter rewrite + INV-9 strict enforce
  └ Q4 剩余决策(INV-9 strict)
  └ PyReason _edge_rest_terms 重写为 unary Relationship Claim lowering
  └ 跟其他 Step 2+ items(InternalIdentity / 唯一性 / 备用键)分批
  └ 跟 Step 1 完全分离 — 不阻塞
```

### 10.2 Slice 依赖图

```text
Slice 1 (Form I) ──┬─→ Slice 2 (Identity Claim)
                   │        ↓
                   └─→ Slice 3a (API namespace) ←─→ Slice 3b (Ledger migration)
                                ↓                        ↓
                                └────→ Slice 4 (Docs sync) ←──┘
                                                ↓
                                        [Step 1 完成]
                                                ↓
                                     Slice 5+ (Step 2+,independent)
```

### 10.3 Recommended sequencing rationale

- **Slice 1 first** — Form I 是 foundational 重构,所有后续 slice 都需要 `_DataMember` + Identity/Field 稳定 descriptors;独立 ship 友好
- **Slice 2 after Slice 1** — Identity Claim emission 依赖 Form I descriptor 完成;但**不依赖** API namespace 重组(Identity Claim emission 在 application 层,SDK shell namespace 是 different concern)
- **Slice 3a after Slice 1+2** — `fg.entities.create` 需要 Identity Claim emission 路径就位;AssertionView 统一可独立做但与 namespace 同步最经济
- **Slice 3b parallel-eligible with 3a** — ledger migration 改 backend,不动 SDK surface;Slice 3a 改 SDK 不动 ledger backend;两者可并行
- **Slice 4 last** — docs sync 必须 follow stable 代码,否则永远追;docs-only slice 无代码风险 + 一次性同步效率最高
- **Slice 5+ separated** — 严格阻止 Step 1 被 adapter rewrite 阻塞(per user 关键 guidance);Q-PR1 单独 slice 落地

### 10.4 Stage 3 synthesis 输入

本 §10 + §7.3 Q list + §6.3 total triage 是 Stage 3 synthesis 的 audit 端 input。synthesis doc 会重分桶:
- blueprint-eligible(可直接进 Stage 4):Slice 1 / Slice 2 (Identity Claim emission part)
- gated by Q decisions(等 Stage 2 ADR):Slice 2 (INV-7c cache) / Slice 3a / Slice 3b 多数项
- cross-doc blocked:Slice 4(等所有代码 slice 完成)
- deferred(Step 2+):Slice 5+

## 11. Cross-doc seams catalog

合 §5.3 D1-D9 + §10 Slice 4 docs sync 范围:

| Doc file | Section | Step 1 sync 内容 | Slice |
|---|---|---|---|
| `src/factgraph/sdk/docs/04_api_surface.en.md` | §0 Namespace Map + §2.3-§2.5+ namespace tables + §4 type rows | 全面 rewrite — 三层 namespace + AssertionView + _meta + 招纳原则 + 三分 schema | Slice 4 |
| `src/factgraph/sdk/docs/04_api_surface.en.md` | §2.14 (FrozenAssertionView) + (fg.views) | rename(Step 2+ per A18 + A19) | Step 2+ |
| `docs/official/kernel/quickstart/assertions.md` | lines 145(at) / 307-308(at/version shortcuts) / 348(.where signature) / 380-387(where no-args) | 删 `.version(v)` 文档化 + `_meta` 统一 signature + at(t) 保留 | Slice 4 |
| `docs/official/kernel/quickstart/assertions.md` | lines 599-602("fg.assertions.where intentionally NOT supported") | **关键 rewrite** — 改为 "fg.assertions.where shipped after Step 1;at/version 仅在 view scope" | Slice 4 |
| `docs/official/kernel/quickstart/` 其他 quickstart pages | Identity-as-Claim 概念引入 + create/edit/delete flow | 新章节 / 添加示例 | Slice 4 |
| `docs/references/working/design-points/readme.md`(dirty baseline) | 旧 design-points 引用更新 | 单独 unrelated dirty 不动 | (per CADENCE — 跨 session preserved dirty,不入本 audit) |

## 12. Audit completeness checklist

- [x] 所有 in-scope rows triaged(I-series 16 + A-series 21 + D-series 11 = 48 finding)
- [x] 所有 open Qs surfaced(17 Qs ready for Stage 2)
- [x] 所有 frictions enumerated(per §8 reviewer focus + §10 sequencing rationale)
- [x] Out-of-scope explicitly listed(§2 in/out + Q-PR1 + Rule/Inference/Semantics/Evidence/Persistence Step 2+)
- [x] Recommendations provided(§10 slice order + §11 cross-doc seams catalog)
- [x] Status transition `skeleton` → `complete`(本 commit)

**Status: complete**(Phase 4 收尾;ready for Stage 2 Q-decisions + Stage 3 synthesis)。

## 8. Reviewer Focus(Phase 4 填入)

> ⏳ Phase 4 待填:reviewer 应特别关注的 finding 集 + cross-doc seams + cross-slice contract preservation。

## 9. Acceptance Criteria(Phase 4 填入)

> ⏳ Phase 4 待填:本 audit 完成的判定标准(覆盖率 / Q 数 / 5-bucket 分布 / cross-doc seams 完整性)。

---

## Phase 1 完成状态

- [x] Header(Status / Date / Branch / Base commit / Reviewer handoff)
- [x] §1 Purpose(本 audit 目的 + 重要 framing:design 描述目标态而非当前态)
- [x] §2 Audit Scope(in scope / out of scope)
- [x] §3 Canonical Sources Read(design-points + workflow / cadence sources)
- [x] §4 Shipped Source Read(SDK / facade / ledger / protocol / write / authoring / adapter / published docs)
- [x] §4.10 Coverage check(标识 Phase 2 row-drafting time re-read 需要补的文件)
- [ ] §5-§9 留 Phase 2-4(I-series → A-series → D-series + cross-doc + Q surface)

## Phase 3 完成状态

- [x] 5+1 state taxonomy 提升到 §2.0(canonical reference,A/D-series 沿用)
- [x] §5.2 A-series triage(21 条 architecture commitment,4 batches × 5-6 项)
  - [x] Batch 1:e_ref + Identity 模型(A1-A5)
  - [x] Batch 2:Form I schema 声明(A6-A10)
  - [x] Batch 3:API 三层 + AssertionView + `_meta`(A11-A15)
  - [x] Batch 4:Identity boundary + schema 管理 + ledger 同步(A16-A21)
- [x] §5.2 总结(分类分布 + 新增 2 cluster:Form I cluster + API namespace 三层重组 cluster)
- [x] §5.2 浮出 12 Q candidates(Q-A1 → Q-A12)+ Q-I 跟 Q-A 关联清单(per user reviewer Phase 4 guidance)
- [x] §6.2 A-series triage summary(指向 §5.2)
- [x] §7.2 Q candidates 占位
- [x] Phase 3 row-drafting time 完整 re-read:`schema_compile.py`(530 lines)
- [x] Phase 3 spot-check:`:exists` emission 路径(`application/entity_write.py:389`)+ `is_identity_field` flag 使用点 + `encode_idref_v1` 调用点
- [x] INV-3 transaction boundary verification(per user reviewer Phase 2 deferred 项):shipped `set_field`(`evidence/write_protocol.py:128-156`)调用 `ledger.append_assertion` 单一 call,内部 SQLite cursor + commit boundary 跨表(claims+claim_args+meta+annotations);`retract_by_asrt` 跨 revokes+meta_rows(可选 + annotations);**单 transaction 假设合理**,但 Phase 4 时 spot-check `ledger.py` 的 `_conn.execute` + `commit()` 排布最终确认
- [ ] §5.3 D-series 留 Phase 4
- [ ] §5.4 N-series 留 Phase 4(if needed)
- [ ] §7 全部 Q finalize(Q-I + Q-A + Q-D 统一编号 + ADR structure)留 Phase 4
- [ ] §6.3 / §8 / §9 留 Phase 4

**等 user review + "可以推进" 才进入 Phase 4 D-series + cross-doc seams + Q finalize + recommendations**。

Phase 3 → Phase 4 转换前,user review 应确认:
1. **A-series 21 条 commitment 分类**是否准确(尤其 (c) shape conflict vs (f) target-gap 区分 — A11/A12/A13/A14/A17 都标为 (c) shape conflict 因为 shipped 有 active 不同 surface,跟 (f) target-gap "shipped 没有这个概念"区分)
2. **2 个新 cluster 识别**(Form I + descriptor 扩展 cluster + API namespace 三层重组 cluster)是否对路;是否在 Step 1 内同 slice 落地的判断合理
3. **12 个 Q candidates(Q-A1 → Q-A12)**议题表述是否准确;Phase 4 finalize 时是否需要拆分 / 合并
4. **Q-I 跟 Q-A 关联清单**是否覆盖全部关联;Phase 4 时是否同时 finalize 几个合并 Q
5. **INV-3 transaction boundary** Phase 3 初步确认 + Phase 4 ledger.py `_conn` 排布最终 spot-check 同意吗

## Phase 2 完成状态

- [x] §5.1 I-series triage(16 条 invariant — INV-1..INV-15 + INV-6 + INV-7a/b/c;INV-8 已消解)
- [x] 5+1 state 分类约定(加 `(f) target-gap / pending migration` 桶,per user reviewer 2026-05-29 校准)
- [x] §5.1 总结(分类分布 + 关键观察 + migration cluster 识别)
- [x] §5.1 浮出 5 个 Q candidates(Q-I1 → Q-I5,Phase 4 时 finalize)
- [x] §6.1 commitment triage summary(指向 §5.1)
- [x] §7.1 Q candidates 占位
- [x] Phase 2 row-drafting 时完整 re-read `write_protocol.py`(per Rule 1)
- [x] Phase 2 spot-check:`__system__` namespace shipped 零命中(grep) — 确认 INV-10/11/15 是 target-gap 不是 enforcement gap
- [ ] §5.2-§5.4 留 Phase 3-4(A-series / D-series / N-series)
- [ ] §6.2 留 Phase 3-4(A-series + D-series triage summary)
- [ ] §7 全部 Q finalize 留 Phase 4

**等 user review + "可以推进" 才进入 Phase 3 A-series triage**。

Phase 2 → Phase 3 转换前,user review 应确认:
1. **5+1 state 分类约定**(尤其 (f) target-gap 桶的引入)是否对路;后续 A/D-series triage 是否沿用
2. **I-series 16 条分类**是否正确(尤其 INV-7c 的 "vacuously satisfied + Step 1 load-bearing" framing 是否对路)
3. **5 个 Q candidates(Q-I1 → Q-I5)的议题表述**是否准确;Phase 4 finalize 时是否需要拆分 / 合并
4. **3 个 migration cluster 识别**是否完整(Identity-as-Claim cluster + System namespace cluster + Editor immutability gap)
5. **INV-3 Phase 3 verification 需要做的 SQLite transaction boundary 完整性 spot-check**(append_assertion 真的单 transaction 吗?)
