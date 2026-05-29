# Audit: Identity-as-Claim design-points vs Shipped Runtime

- Status: skeleton (Phase 1 inventory only — Phases 2-4 deferred to subsequent commits)
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

## 5. Findings(Phase 2-4 填入,本 commit 留空 placeholder)

> ⏳ Phase 2-4 待填:5-state 分类后的 finding 列表(F1, F2, ...),按 I-series(invariant)/ A-series(architecture)/ D-series(discrepancy)/ N-series(non-discrepancy)分桶。

## 6. Commitment Triage(Phase 2-4 填入)

> ⏳ Phase 2-4 待填:design-points 各设计 commitment vs shipped 的 5-state 分类表;按以下 5 桶:
> - (a) shipped covers — honors design intent
> - (b) small gap — minor mv / rename / metadata sync
> - (c) shape conflict — semantic or structural mismatch requires decision
> - (d) genuinely new — no shipped equivalent
> - (e) deferred-aligned — design defers + shipped honors

## 7. Stage 2 Questions(Phase 4 浮 + 填入)

> ⏳ Phase 4 待浮:每个 load-bearing Q 一条,blocking 具体 drift row;每个将成为 `workflow/design/decisions/active/2026-05-29_qN-<topic>-decision.md` 的 input。

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

**等 user review + "可以推进" 才进入 Phase 2 I-series triage**。

Phase 1 → Phase 2 转换前,user review 应确认:
1. §2 scope 边界对(in scope / out of scope 没漏关键设计点)
2. §3 canonical sources 引用 line ranges 准确
3. §4 shipped baseline 描述无事实错误(尤其 ledger 7-table + n-ary rest_terms framing)
4. §4.10 coverage check 同意 Phase 2 时 re-read 的文件列表
