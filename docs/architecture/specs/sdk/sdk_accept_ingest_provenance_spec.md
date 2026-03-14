---
doc_type: spec
status: partial
source_of_truth: design
implementation_state: partial
owner: sdk
last_verified: 2026-03-14
---

> Partial status: 本文可作为 SDK 写入入口分层的规范性参考，但具体行为边界仍需结合当前 SDK 文档与代码实现核对。

# FactPy SDK 写入入口分层规范（`accept` / `ingest` / `provenance`）

版本：v1  
状态：已实现（本文保留分层规范口径）  
范围：`SDKStore` 用户友好写入入口与 provenance 校验职责分层，不替代现有 Core Contract / derivation accept 实现

---

## 0. 目标与结论（锁定）

本规范解决的问题是：在 FactPy 中，推导物化（derivation materialization）与外部数据导入（ETL / 人工写入）都需要“写入 ledger + 附带 meta”，但它们不应共享同一套强约束和结果类型。

本规范锁定以下结论：

1. `sdk.accept(CandidateSet)` 保持严格，语义限定为“推导候选物化（derivation accept）”
2. 新增 `sdk.ingest(...)` 作为手工/ETL/外部数据写入口（宽松 meta 语义）
3. 引入 meta key 四层分类（`hard reserved / sensitive semantic / convention / free`）
4. `validate_provenance()` 为独立工具，不作为写入前置条件（默认不阻塞写入）

核心原则：

`写入 ≠ provenance 校验`

这与 FactPy 的整体设计哲学一致：写入层追加证据；语义判断放在 view / policy / audit 层。

---

## 1. 背景与问题定位

### 1.1 现状（代码层面）

当前 `SDKStore.accept(...)` 主要是 `CandidateSet` 的 SDK 包装入口，最终走 derivation accept 路径（推导候选物化），而不是通用“写入任意数据”的入口。

- `src/factpy_kernel/sdk/store.py`
- `src/factpy_kernel/core/store/runtime.py`（兼容入口仍保留在 `core/store/api.py`）
- `src/factpy_kernel/core/derivation/accept.py`

当前 derivation accept 会写入一组带强语义的 meta（如 `derived_rule_id / run_id / support_digest / materialize_id / key_tuple_digest`），并返回 `AcceptResult`（携带 derivation/materialization 语义字段）。

### 1.2 症结

问题不是“accept 太严格”，而是：

- derivation accept 的强契约（正确）与 generic ingest 的需求（也正确）尚未分层
- 容易在 API 认知上把 `accept` 误当作通用写入口

如果强行把 generic ingest 合并到 `accept`：

- `AcceptResult` 对手工数据会充满语义噪音
- 错误信息会混合 derivation 专用约束与 ETL 写入约束
- provenance 字段的下游审计解释会被污染

---

## 2. 分层原则（规范性）

### 2.1 写入入口分层（MUST）

系统必须区分两类写入路径：

1. `accept`（derivation accept path）
2. `ingest`（external/manual ingest path）

两者可以在 SDK 层并列暴露，但不得在 Core 层硬合并为同一语义函数。

### 2.2 provenance 校验分层（MUST）

provenance 校验必须作为独立步骤存在（工具函数或显式校验器），不得默认成为 generic ingest 的前置阻塞条件。

允许上层应用在流程中选择：

- `warn-only`
- `validate-then-ingest`
- `validate+enforce`

### 2.3 系统级保留 meta（MUST）

系统管理的 meta key 必须保持不可由用户手写覆盖（写入时直接报错）。

这是审计可信性与系统幂等/时序戳完整性的底线，不属于 provenance 语义校验范畴。

---

## 3. API 分层规范（SDK 层）

## 3.1 `sdk.accept(...)`（保留现状，严格语义）

### 语义

- `sdk.accept(...)` 的主语义是：接受 `CandidateSet` 并物化到 ledger
- 保持 derivation/materialization 强契约
- 返回 `AcceptResult`（derivation 专用结果类型）

### 约束（MUST）

- `sdk.accept(CandidateSet)` 保持严格，不因 generic ingest 需求而放松
- 不接受普通 `Entity` / `EntitySnapshot` / plain dict 作为 generic ingest 替代路径

### 非目标

- 不作为手工/ETL 通用写入口

---

## 3.2 `sdk.ingest(...)`（新增，generic ingest path）

### 语义

`sdk.ingest(...)` 是“外部数据导入 / 手工录入 / 应用写入”的统一入口。其职责是：

- 写入事实到 ledger（最终仍落到 Core Contract / write_protocol）
- 接收用户提供 meta（经过格式与保留 key 校验）
- 产生 ingest 结果与警告/诊断

`sdk.ingest(...)` 不承担 derivation accept 的物化幂等/审计强契约。

### 推荐签名（草案）

```python
class SDKStore:
    def ingest(
        self,
        data: Any,  # v1 具体形态见 3.2.4
        *,
        meta: dict[str, Any] | None = None,
        allow_sensitive_meta: bool = False,
    ) -> "IngestResult":
        ...
```

说明：

- `allow_sensitive_meta=False`：默认对 sensitive semantic keys 给出警告（不阻塞）
- provenance 校验是否执行由调用方显式决定（通过独立 `sdk.validate_provenance(...)`），不内嵌在 `ingest` 决策参数中

### `IngestResult`（建议）

`IngestResult` 应与 `AcceptResult` 分离，避免 derivation 语义污染。

建议最小字段：

```python
@dataclass(frozen=True)
class IngestResult:
    written_assertion_ids: list[str]
    skipped_count: int
    duplicate_count: int
    warnings: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]]
    diagnostics_contract_version: int = 1
```

说明：

- 不携带 `materialize_id / support_digest / key_tuple_digest` 等 derivation 专用字段
- 诊断结构可复用现有 `code/severity/path/message/data` 形状

### 与 `sdk.batch()` / `sdk.edit()` 的关系（MUST）

`sdk.ingest()` 与 `sdk.batch()` / `sdk.edit()` 是并列写入入口，不互相取代。

- `sdk.batch()`：
  - 适合“构造对象图 -> `preview()` -> 一次性落盘”
  - 核心价值是 `preview()`、wire plan、可回放/可审计计划
- `sdk.edit()`：
  - 适合“按 identity 编辑已存在实体/record”
  - 核心价值是显式编辑会话（context manager）与局部修改
- `sdk.ingest()`：
  - 适合“我有一批外部数据，直接写入”
  - 也适合“我只有 `EntitySnapshot.ref` + `AssertionRecord.asrt_id`，但拿不到 record identity（如 `uid`）”的修改路径
    （典型写法：`retract + set` / `retract + add`）
  - 核心价值是简单、数据导向、meta 语义宽松（但保留 key 和敏感语义仍有边界）

三者底层都必须收敛到同一条 Core Contract 写入路径（见下一节）。

### 3.2.1 与现有 Core Contract 的关系（MUST）

`sdk.ingest(...)` 不引入第二套写入模型，最终必须展开为以下 Core 写入路径之一：

- `sdk.set(...)`
- `sdk.add(...)`
- `sdk.retract(...)`
- `sdk.batch(...)`（若选择先编译计划再落盘）

实现职责分层说明（SHOULD）：

- SDK 层校验：以用户体验为主（path-aware diagnostics，如 `items[2].meta.ingested_at`）
- Core / `write_protocol` 层校验：作为最终契约防线（支持绕过 SDK 的调用路径）

### 3.2.2 provenance 不是 ingest 前置条件（MUST）

`sdk.ingest(...)` 对 `meta` 默认只做：

- 格式校验
- 保留 key 校验
- sensitive key 告警（如存在）

行为约定（实现建议，SHOULD）：

- `warning` 不阻塞写入
- 仅 `error` 级 diagnostics 触发 collect-and-stop（整批不写入）

不得要求用户提供 `derived_rule_id / run_id / support_digest` 等 derivation provenance 字段。

### 3.2.3 敏感 meta 的处理（SHOULD）

若用户在 `sdk.ingest(...)` 中显式写入 sensitive semantic keys，系统应：

- 默认发出警告（warning）
- 不阻塞写入（除非上层流程在 `ingest` 前调用 `validate_provenance()` 并自行拦截）

建议告警 code 示例：

- `ingest_sensitive_meta_key_present`
- `ingest_sensitive_meta_looks_derivation_like`

### 3.2.4 `data` 输入形态（分阶段落地建议）

为降低实现复杂度，建议分阶段定义：

#### v1（MVP）

- 接受“规范化事实写入项”列表（fact writes）
- 或作为薄封装，仅支持对现有 `sdk.batch` / `sdk.set/add/retract` 的组合回放

#### v2

- 增加 plain `Entity(...)` / detached 对象图导入（若届时 `sdk.save(...)` 语义已明确）

备注：

本规范先锁定职责与 meta/provenance 语义，不强制 `data` 的最终对象形状在 v1 一次到位。

补充适用边界（来自真实场景验证）：

- 当调用方持有的是 `EntitySnapshot.ref` 和 `AssertionRecord.asrt_id`，但无法取到 record 的 identity 字段时，
  `sdk.ingest(retract/set)` 是可行路径。
- `sdk.edit()` 在该场景不适用，因为它要求完整 identity（如 `uid` / `source_id`）。
- 这类场景常见于 `sdk.find(...)` 返回的 snapshot：v1 保证 `.ref` 可用，但不保证总能恢复 identity 字段。

---

## 3.3 `sdk.validate_provenance(...)`（独立工具）

### 语义

用于按约定标准校验 provenance 信息完整性/格式，不写入 ledger。

### 推荐签名（草案）

```python
class SDKStore:
    def validate_provenance(
        self,
        obj: Any,  # 例如 meta dict / CandidateSet / assertion row DTO
        *,
        standard: str = "derivation_v1",
    ) -> "ValidationReport":
        ...
```

### 返回（建议）

```python
@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    warnings: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    diagnostics_contract_version: int = 1
```

### `derivation_v1`（建议校验项）

至少覆盖：

- `derived_rule_id`（非空 string）
- `derived_rule_version`（非空 string）
- `run_id`（非空 string）
- `support_digest`（`sha256:` 前缀）
- `support_kind`（受支持枚举）

可选（warn-only）：

- `schema_digest`
- `policy_digest`

说明：

- `validate_provenance()` 是审计/治理工具，不决定写入是否发生（默认）
- 调用方可在业务层自行决定“有 error 则不调用 `ingest`”

---

## 4. meta key 分类规范（四层分类）

本规范将 meta key 按“权限边界 + 下游解读语义”划分为四层。

### 4.1 `hard reserved`（系统保留，MUST 拦截）

定义：

- 系统自动注入 / 系统维护的 key
- 用户手写必须报错

当前已知（与现有 `write_protocol` 对齐）：

- `ingested_at`
- `ingest_key`
- `revoked_asrt_id`

建议新增（实现时需同步更新 `write_protocol` 的保留 key 集合，见 5.2）：

- `meta_origin`（建议新增，系统管理）

### 4.2 `sensitive semantic`（敏感语义 key）

定义：

- 用户可写（不属于 hard reserved）
- 但 explain/audit/export 会按约定语义解读
- 可能影响审计可信性与 provenance 展示

典型键（含 derivation/materialization 语义）：

- `derived_rule_id`
- `derived_rule_version`
- `run_id`
- `support_digest`
- `support_kind`
- `materialize_id`
- `materialize_kind`
- `key_tuple_digest`
- `cand_key_digest`
- `schema_digest`
- `policy_digest`

规范要求：

- `sdk.ingest(...)` 默认 warning，不默认报错
- audit/explain 层不得把这些字段一律视为“可信系统推导来源”（见第 5 节）

### 4.3 `convention keys`（约定 key）

定义：

- 用户可写
- 系统会使用/展示其中一部分（如 dedup、审计展示、追踪）
- 但不绑定 derivation provenance 语义

典型键：

- `source`
- `source_loc`
- `trace_id`
- `confidence`
- `approved_by`
- `note`

说明：

- `convention` 不代表“全都影响 dedup”
- 见第 4.5 节的第二维度分类

### 4.4 `free keys`（自由 key）

定义：

- 用户完全自定义
- 系统不做固定语义解读（除通用序列化/展示）

示例：

- `biz_unit`
- `import_file`
- `operator_comment`
- `campaign_id`

### 4.5 第二维度：`dedup-affecting`（是否影响 ingest_key）

除四层分类外，文档必须额外标注哪些 key 会参与写入幂等/去重（`ingest_key`）计算。

当前（与现有 `write_protocol` 实现对齐）参与 `ingest_key` 的 meta 字段为：

- `source`
- `source_loc`
- `trace_id`

说明（MUST）：

- `dedup-affecting` 是独立维度，不等同于 `convention`
- 文档和 API 说明必须清楚告知：修改这些 key 会改变 dedup 行为

参考实现位置：

- `src/factpy_kernel/core/evidence/write_protocol.py`

---

## 5. 审计 / explain 的 provenance 可信性规范

## 5.1 问题

若用户通过 `ingest` 写入 sensitive semantic keys（例如 `derived_rule_id`），下游 `audit/explain` 可能误将其渲染为“系统推导 provenance”，造成审计链污染。

## 5.2 规范要求（SHOULD，推荐升级为 MUST）

audit/explain 在解读 sensitive semantic keys 时，应区分：

- `system-derived provenance`
- `user-declared provenance`
- `unknown provenance`

推荐实现方式（强烈建议）：

- 引入系统管理 meta key：`meta_origin`
- 由系统写入路径自动注入（用户不可覆盖）

建议枚举值：

- `derivation.accept`
- `derivation.accept.record_stage`
- `sdk.ingest`
- `sdk.core_write`（可选，直接 `sdk.set/add/retract`）
- `unknown`（兼容旧数据展示时的推断值，不回写）

这样 audit/explain 才能在展示时做可靠标注，而不是仅凭 `derived_rule_id` 等字段存在与否进行推断。

## 5.3 向后兼容（旧数据）

对历史数据（尚无 `meta_origin`）：

- 若存在 sensitive semantic keys，应标记为 `unknown provenance` 或 `user-declared (unverified)`
- 不得无条件显示为“系统推导来源”

---

## 6. 统一入口方案评估（为何不推荐 `sdk.accept(...)` 重载）

可行但不推荐的方案：

```python
sdk.accept(candidate_set, ...)  # derivation path
sdk.accept(entity_list, ...)    # ingest path
```

不推荐原因：

1. `accept` 在当前术语中已强绑定 `CandidateSet` 物化
2. 重载会增加调试成本（同名入口，多语义分发）
3. 错误信息与结果类型更难直观理解

推荐方案（本规范）：

- `sdk.accept(...)`：仅 derivation accept
- `sdk.ingest(...)`：generic ingest
- `sdk.validate_provenance(...)`：独立校验工具

---

## 7. 与现有系统的一致性（设计哲学对齐）

本规范与 FactPy 现有设计哲学一致：

- 写入层：追加证据（append-only）
- view/policy 层：决定 `active/chosen/current`
- audit/explain 层：解释来源与可追溯性

因此 provenance 校验应是“解释/治理层面的能力”，而不是 generic ingest 的默认写入前提。

---

## 8. 分阶段落地建议（实现顺序）

### v1（建议优先）

1. 文档化本规范（本文件）
2. 在文档/API 中明确 `sdk.accept` 为 `CandidateSet` 专用 accept
3. 增加 meta key 分类说明（尤其 sensitive / convention / dedup-affecting）
4. 增加 `validate_provenance()` 纯工具（先支持 `meta dict` 校验即可）

### v2

1. `sdk.ingest(...)` MVP（先支持事实写入项）
2. `IngestResult` 结果类型
3. ingest 对 sensitive meta 默认 warnings

正式类型固化时机（建议标准）：

- 至少两个不同调用场景已使用 `sdk.ingest(...)`
- 调用方在真实使用中不再需要修改 item dict 结构
- 届时再将 `fact write item` 固化为 TypedDict/Dataclass（避免过早设计）

### v3

1. audit/explain 引入 `meta_origin` 可信性标注
2.（可选）`sdk.ingest(...)` 支持 plain `Entity(...)` / detached 对象图
3. 与未来 `sdk.save(plain_entity)` / `EntitySnapshot.to_entity()` 语义协同

---

## 9. 非目标（当前规范不解决）

- 放松 `sdk.accept(CandidateSet)` 的 derivation 强契约
- 把 generic ingest 与 derivation accept 合并成同一结果类型
- 一次性定义 plain `Entity(...)` 回写（`sdk.save(...)`）的完整语义
- 替换现有 `sdk.ref/set/add/retract` 或 `sdk.batch(...)`

---

## 10. 最小示例（规范表达）

### 10.1 推导物化（严格 accept）

```python
cands = sdk.evaluate(...)
report = sdk.validate_provenance(cands[0], standard="derivation_v1")  # 可选
res = sdk.accept(cands[0])  # 严格 derivation path
```

### 10.2 手工 / ETL 导入（generic ingest）

```python
res = sdk.ingest(
    data=[
        # v1 最小可落地形态建议：规范化 fact write item 列表（例如 set/add/retract 的结构化项）
        ...
    ],
    meta={"source": "CSV", "trace_id": "import-2026-01-01"},
)
```

### 10.3 手写 sensitive semantic key（允许但默认告警）

```python
res = sdk.ingest(
    data=[...],
    meta={
        "source": "ETL",
        "derived_rule_id": "manual_override",  # sensitive semantic key
    },
)
# -> 写入成功 + warnings（默认）
```

---

## 11. 术语表（便于实现对齐）

- `derivation accept`：将 `CandidateSet` 物化到 ledger 的严格路径
- `generic ingest`：手工/ETL/外部数据写入路径
- `provenance validation`：对 provenance 字段完整性/格式的校验（不写入）
- `sensitive semantic key`：可写但会被下游审计/解释层按特定语义解读的 meta key
- `dedup-affecting key`：参与 `ingest_key` 计算、影响写入幂等/去重的 meta key
