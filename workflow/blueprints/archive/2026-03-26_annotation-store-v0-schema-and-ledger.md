# Task Blueprint: Annotation Store V0 Schema And Ledger

- Status: implemented
- Created: 2026-03-26
- Last Updated: 2026-03-26
- Parent Blueprint:
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md)
- Related Modules:
  - `src/factpy_kernel/core/store/ledger.py`
  - `src/factpy_kernel/core/evidence/write_protocol.py`
  - `src/factpy_kernel/core/mapping/canon.py`
  - `src/factpy_kernel/core/view/projector.py`
  - `src/factpy_kernel/core/docs/01_architecture.md`
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [2026-03-22_architectural-decisions-v2.md](./2026-03-22_architectural-decisions-v2.md)
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md)
- Audit Log:
  - [2026-03-26_annotation-store-v0-schema-and-ledger.audit.md](./2026-03-26_annotation-store-v0-schema-and-ledger.audit.md)

## 1. Problem

Decision blueprint 已冻结 `Annotation Store` 的语义边界，但当前代码里还没有 durable carrier：

- `claims` / `claim_args` / `meta_rows` / `revokes` 已存在
- `annotation_rows` 尚不存在
- assertion-level engine-native semantics 仍缺 durable 存储入口
- 旧 consumer 仍直接读 `meta_rows`

如果没有这一层，`confidence` 仍会继续承担错误的“统一真值”角色，PyReason/ProbLog 等引擎的 assertion-level 原生语义也无法零损失持久化。

## 2. Goals

- 新增 `annotation_rows` durable shape，与 `claims` / `meta_rows` 平行
- 只支持 `assertion` subject（`asrt_id`）
- 支持 assertion-level annotation 的写入与读取
- 明确 `meta_rows` 的 legacy projection 策略，使旧 consumer 继续可用
- 为后续 PyReason / ProbLog assertion semantics 落地准备最小 ledger 接口

## 3. Non-goals

- 不做 provenance payload 改造
- 不做 rule builder / `engine_ext` 实现
- 不做 run-level / rule-level / provenance-level annotation
- 不做 UI / audit package / static HTML 消费切换
- 不迁移历史 `meta_rows` 数据
- 不删除旧 consumer 对 `meta_rows` 的读取路径

## 4. Current Context

- 当前 durable fact carrier 仍是 `claims + meta_rows`
- [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md) 已冻结：
  - `confidence` 是 derived summary
  - engine-native truth semantics 属于 assertion annotation
  - Annotation Store 初版只覆盖 assertion-level
  - `meta_rows` 保留为 legacy compatibility layer
- 当前 [write_protocol.py](../../../src/factpy_kernel/core/evidence/write_protocol.py) 只会写 `meta_rows`
- 当前 canonical / view / runtime surface 仍直接读取 `meta_rows` 中的 `confidence`、`source` 等字段

## 5. Proposed Shape

### 5.1 Durable shape

在现有 ledger 旁新增 `annotation_rows`，逻辑上与 `meta_rows` 分离：

```text
claims
claim_args
meta_rows            # legacy compatibility / historical path
annotation_rows      # new canonical annotation carrier
revokes
```

初版 `AnnotationRow` 结构遵循父 decision blueprint：

- `asrt_id`
- `namespace`
- `category`
- `key`
- `kind`
- `value`
- `origin`
- `derivation`

### 5.2 Write path

- 新的 assertion-level semantics 进入 `annotation_rows`
- `meta_rows` 不再是新语义的 canonical 落点
- 对旧 surface 仍需要的字段，采用明确的 legacy projection：
  - 例如 `shared/derived/confidence` 可投影到 `meta_rows.confidence`
  - projection 是 compatibility 行为，不是 canonical truth storage

### 5.3 Read path

初版提供最小读接口：

- 按 `asrt_id` 读取 annotation rows
- 按 `(namespace, category, key)` 过滤
- 为后续 consumer 保留 direct-read 能力

旧 surface 本轮继续读 `meta_rows`，不强制迁移。

### 5.4 Scope freeze

本轮只做 assertion-level store/ledger 形状，不触碰：

- provenance envelope
- rule extension payload
- `engine_options`
- audit package JSONL / static renderer

## 6. Boundaries And Invariants

- 必须保持的边界：
  - `Annotation Store` 是独立层，不是 `meta_rows` 的别名
  - `confidence` 的 canonical 语义留在 annotation `shared/derived`
  - `meta_rows` 保留为 compatibility layer
  - 初版只支持 `assertion` subject
  - `kind` 复用现有 `MetaRow.kind` 体系：`str | int | float | bool | time | json`
- 明确不做的内容：
  - 不做 candidate/provenance annotation
  - 不把 rule/run 参数写入 `annotation_rows`
  - 不引入新的 value kind（如 `interval`）
- 兼容性约束：
  - 旧 consumer 不应因 `annotation_rows` 引入而失效
  - 兼容投影必须显式、可追踪，不允许隐式把 annotation 再次混回“万能 meta”

## 7. Acceptance

- [ ] `annotation_rows` durable shape 已在 ledger 中落地
- [ ] assertion-level annotation 有最小写入/读取路径
- [ ] legacy projection 策略已冻结并在代码中体现
- [ ] 旧 `meta_rows` consumer 保持兼容
- [ ] 受影响模块 docs 已同步
- [ ] 如有新文档入口，`docs/README.md` 已更新

## 8. Implementation Plan

1. ~~[ledger] 新增 `annotation_rows` durable shape、row type、基本读写接口~~ — **done** (Step 1)
2. ~~[write_protocol] 引入 assertion annotation 写入入口，并冻结与 `meta_rows` projection 的关系~~ — **done** (Step 2)
3. ~~[read side] 补最小 assertion-level annotation read path，供后续 consumer 使用~~ — **done** (`find_annotations()` in Step 1)
4. ~~[compat] 明确并实现 legacy `meta_rows` projection 的最小策略~~ — **done** (dual-write in Step 2)
5. ~~[tests/docs] 补 round-trip / backward-compat tests，并更新 core docs~~ — **done** (51 new tests + docs updated)

## 9. Docs To Update

- ~~`src/factpy_kernel/core/docs/01_architecture.md`~~ — done (§4 四层架构 + §5.1 双写链路)
- `src/factpy_kernel/service/docs/03_runtime_queries_views.md` — 本轮未触及 runtime-facing read semantics，不更新
- `docs/README.md` — 本轮无新 durable docs 入口，不更新

## 10. Outcome / Deviations

- 最终落地结果：
  - `AnnotationRow` dataclass + `annotation_rows` SQLite table（含 upsert 语义）
  - `append_assertion(..., annotation_rows=...)` 原子写入
  - `append_annotations()` 独立追加
  - `find_annotations()` 任意组合过滤
  - `write_protocol` 白名单双写（shared/source + shared/derived → annotation_rows + meta_rows）
  - 51 个新测试（`test_annotation_store.py` 35 + `test_write_protocol_annotations.py` 16）
  - `01_architecture.md` 更新（四层架构 + 双写链路）
- 与 blueprint 不同的地方：
  - Step 3 和 Step 4 的目标在 Step 1/2 实施过程中自然完成，未单独成步
  - `find_annotations()` 支持任意组合过滤（超出 blueprint 最小要求），由用户在 Step 1 实施时扩展
  - 内存索引增加了 `_anno_by_identity` upsert 机制（blueprint 未预设），由用户根据 `INSERT OR REPLACE` 语义需要增加
  - `append_assertion` 允许占位空 `asrt_id`（minor compat fix，blueprint 未预设）
- 为什么会有这些调整：
  - Step 3/4 并入：`find_annotations()` 是 Step 1 的自然产物；双写是 Step 2 的直接实现
  - upsert 机制：`UNIQUE` 约束要求内存索引也做替换，否则会有残影
- 归档说明：本蓝图可归档。后续 PyReason `pyreason/semantic` annotation 由引擎 adapter 蓝图承载。
