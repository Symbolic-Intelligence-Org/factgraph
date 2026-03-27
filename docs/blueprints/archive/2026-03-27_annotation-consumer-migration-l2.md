# Task Blueprint: Annotation Consumer Migration (L2)

- Status: implemented
- Created: 2026-03-27
- Last Updated: 2026-03-27
- Parent Blueprint:
  - [2026-03-27_multi-engine-semantic-delivery.md](./2026-03-27_multi-engine-semantic-delivery.md) (L2)
- Related Modules:
  - `src/factpy_kernel/adapters/souffle/package.py` — audit package 写出入口
  - `src/factpy_kernel/audit/reader.py` — audit package 读取
  - `src/factpy_kernel/audit/assertions.py` — assertion detail/index 构建
  - `src/factpy_kernel/audit/static_ui.py` — static HTML 生成
  - `src/factpy_kernel/core/store/ledger.py` — annotation_rows 源
- Related Docs:
  - [2026-03-26_assertion-annotation-store-decision.md](./2026-03-26_assertion-annotation-store-decision.md)
  - [src/factpy_kernel/adapters/docs/03_pyreason_adapter.md](../../../src/factpy_kernel/adapters/docs/03_pyreason_adapter.md)
- Audit Log:
  - [2026-03-27_annotation-consumer-migration-l2.audit.md](./2026-03-27_annotation-consumer-migration-l2.audit.md)

## 1. Problem

Annotation Store 已落地（`annotation_rows` in Ledger），`write_protocol` 已双写 `shared/*` annotations，PyReason 已通过 `persist_pyreason_annotations()` 写入 `pyreason/semantic/*`。但当前没有任何 consumer 读 `annotation_rows`——所有 downstream 面（audit export、static HTML、service API、evidence tree）仍然只读 `meta_rows`。

这意味着 annotation 数据虽然被持久化了，但对用户不可见。

## 2. Goals

**最小迁移切片**——按母蓝图 Gate 2 的 acceptance criteria：

1. Audit package 导出包含 `assertion_annotations.jsonl`
2. Static HTML 增加引擎语义面板（至少展示 `pyreason/semantic/bound_lower` + `bound_upper`）
3. 至少一个 downstream consumer 优先读 `annotation_rows` 而非 `meta_rows`

## 3. Non-goals

- 不一次迁移所有 12 个 meta_rows consumer
- 不删除 `meta_rows`（继续双写，继续作为 legacy compatibility layer）
- 不改 certainty v1（frozen contracts #1-#16）
- 不改 confidence 在 CandidateSet/accept 中的传播路径
- 不改 Souffle provenance / rule export 语义，只扩 audit package artifact set
- 不碰 ProbLog export

## 4. Current Context

### Consumer 盘点（按优先级排序）

**L2 需要改动的模块链**（写出 → 读取 → 构建 → 渲染）：

| Layer | File | 当前行为 | L2 改动 |
|-------|------|---------|---------|
| 写出 | `adapters/souffle/package.py` | 导出 meta_* TSV + manifest | 新增 `assertion_annotations.jsonl` 写出 + manifest key |
| 读取 | `audit/reader.py` | 读取 manifest 中的已知 artifact | 新增 `assertion_annotations` artifact 读取（可选 key） |
| 构建 | `audit/assertions.py` | 从 TSV 构建 assertion index | 将 annotation 数据并入 assertion detail |
| 渲染 | `audit/static_ui.py` | 渲染 assertion detail 页面 | 消费 assertion detail 中的 annotation view |

**不应该在 L2 碰的**：

| Consumer | 理由 |
|----------|------|
| `runtime_v1.py` | API 返回面变更影响外部契约 |
| `accept.py` | 核心 accept 路径，frozen 边界 |
| `canon.py` | 映射解析，牵动面太广 |
| `certainty` | 16 frozen contracts |

## 5. Proposed Shape

### Step 1: `package.py` — 新增 `assertion_annotations.jsonl` 写出

`adapters/souffle/package.py` 的 audit package 导出路径新增：
- 从 Ledger 读取 `annotation_rows`（所有 namespace）
- 序列化为 `assertion_annotations.jsonl`（一行一条 AnnotationRow）
- 在 manifest 的 `paths.audit_files` 中注册该 artifact

每行格式：
```json
{"asrt_id": "A1", "namespace": "pyreason", "category": "semantic", "key": "bound_lower", "kind": "float", "value": 0.6, "origin": "observed", "derivation": null}
```

**additive** 改动——不删除现有 meta TSV export，只加一个新 artifact。

### Step 2: `reader.py` + `assertions.py` — 读取并构建 annotation detail

- `audit/reader.py`：新增 `assertion_annotations` 作为可选 audit file key。如果 package 中不含该文件（旧 package），返回空 list。
- `audit/assertions.py`：`load_assertion_index()` 将 annotation 数据按 `asrt_id` 分组，并入每条 assertion 的 detail dict（新增 `annotations` 字段）。

### Step 3: `static_ui.py` — 消费 annotation detail 渲染引擎语义面板

在 assertion detail 页面，如果该 assertion 的 `annotations` 字段包含 `pyreason/semantic/*` 条目，展示一个引擎语义面板：

```
引擎语义（PyReason）
  bound: [0.6, 0.9]
  active_from: 3
```

渲染逻辑消费 Step 2 构建的 annotation detail，不直接读 JSONL 或 Ledger。

### Step 4: 验证 Gate 2

- audit package 包含 `assertion_annotations.jsonl` ✓
- static HTML 展示 bound interval ✓
- 至少一个 consumer 不依赖 `meta_rows.confidence` → audit/assertions.py 直接读 annotation data ✓

## 6. Boundaries And Invariants

- `meta_rows` 继续存在，继续双写，不做 breaking change
- 所有不在 Step 1-2 列出的 consumer 保持现状
- annotation 消费不改变 fact 的 accept/reject 语义
- 新增的导出是 additive，不替换现有 audit 导出格式

## 7. Acceptance

- [ ] Audit package 包含 `assertion_annotations.jsonl`
- [ ] Static HTML 展示 `pyreason/semantic/*` annotation（bound interval 至少）
- [ ] 至少一个 consumer 路径优先读 `annotation_rows`
- [ ] 现有测试全绿（不回归）
- [ ] 新增测试覆盖 annotation export + HTML 渲染

## 8. Implementation Plan

1. `adapters/souffle/package.py`: 新增 `assertion_annotations.jsonl` 写出 + manifest key
2. `audit/reader.py`: 新增 `assertion_annotations` artifact 读取（可选 key，向后兼容）
3. `audit/assertions.py`: 将 annotation 数据并入 assertion detail（`annotations` 字段）
4. `audit/static_ui.py`: 消费 assertion detail 的 `annotations` 字段渲染引擎语义面板
5. 测试：audit export 包含 annotation JSONL + assertion detail 包含 annotations + HTML 渲染验证
6. 文档更新

## 9. Docs To Update

- `src/factpy_kernel/audit/docs/01_overview.md`（如果存在）
- Adapter docs
- L2 blueprint audit log

## 10. Outcome / Deviations

任务完成后填写。
