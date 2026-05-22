# Task Blueprint: Candidate Confidence Kind

- Status: implemented
- Created: 2026-03-20
- Last Updated: 2026-03-20
- Parent: [2026-03-20_certainty-weight-vocabulary.md](./2026-03-20_certainty-weight-vocabulary.md)
- Related Modules:
  - `src/factpy_kernel/core/derivation/candidates.py`
  - `src/factpy_kernel/core/store/_evaluate.py`
  - `src/factpy_kernel/core/store/_builders.py`
  - `src/factpy_kernel/core/store/runtime.py`
  - `src/factpy_kernel/core/derivation/accept.py`
  - `src/factpy_kernel/core/view/projector.py`
  - `src/factpy_kernel/core/view/confidence.py`
  - `src/factpy_kernel/core/mapping/canon.py`
  - `src/factpy_kernel/adapters/problog/problog_import.py`
  - `src/factpy_kernel/service/runtime_v1.py`
  - `src/factpy_kernel/sdk/store.py`
- Audit Log:
  - [2026-03-20_candidate-confidence-kind.audit.md](./2026-03-20_candidate-confidence-kind.audit.md)

## 1. Problem

`CandidateSet.confidence: float | None` 存在但语义未标注。ProbLog 产出的是概率值，native/Souffle 不产出 confidence，未来 certainty engine 可能产出 certainty-weighted 值。消费方（summary / narrative / NL / audit / mapping）无法区分这些语义，导致解释和聚合逻辑存在潜在混淆。

## 2. Goals

- 为 `CandidateSet` 增加 additive `confidence_kind` 字段
- 枚举 `"none" | "probability" | "certainty"`
- 所有 candidate 生产路径正确写入 `confidence_kind`
- 所有 candidate 消费路径正确传播 `confidence_kind`
- 向后兼容：现有无 `confidence_kind` 的 candidate 默认 `"none"`

## 3. Non-goals

- 不修改 `confidence` 字段本身的类型或默认值
- 不实现 certainty propagation
- 不修改 where evaluator 执行语义
- 不让 `confidence_kind` 影响 evaluate / accept / chosen 的执行行为（它是 value-semantics 标注，不是执行控制）

## 4. Impact Analysis

### 4.1 Production Sites（写入 confidence_kind）

| 路径 | 文件 | 当前 confidence | confidence_kind 应写入 |
|---|---|---|---|
| `make_candidate()` | `candidates.py:237` | 参数传入 | 新参数，default `"none"` |
| `candidates_from_bindings()` | `_builders.py:64` | 不传 confidence | `"none"` |
| `entity_candidates_from_bindings()` | `_builders.py:174` | 不传 confidence | `"none"` |
| `evaluate_dummy()` | `runtime.py:278` | 不传 confidence | `"none"` |
| ProbLog `parse_problog_output()` | `problog_import.py:73` | `replace(candidate, confidence=prob)` | 需同时 `replace(..., confidence_kind="probability")` |

### 4.2 Propagation Sites（复制/重建 candidate 时须保留）

| 路径 | 文件 | 当前行为 |
|---|---|---|
| `_with_candidate_run_id()` | `sdk/store.py:1314` | 复制 confidence | 须同时复制 confidence_kind |
| `_candidate_from_dict()` | `runtime_v1.py:1255-1277` | 从 dict 反序列化 | 须读取 confidence_kind |

### 4.3 Serialization Sites

| 路径 | 文件 | 当前行为 |
|---|---|---|
| `_candidate_to_dict()` | `runtime_v1.py:1243-1252` | 序列化为 API dict | 须写入 confidence_kind |
| `_metadata_from_candidate_set()` | `accept.py:775` | 写入 ledger meta | confidence_kind 进 meta（additive） |

### 4.4 Consumption Sites（读取 confidence 语义时可感知 confidence_kind）

| 路径 | 文件 | 影响 |
|---|---|---|
| `aggregate_confidence()` | `confidence.py:20-43` | 未来可按 kind 选择聚合策略；第一轮不改行为 |
| `_resolve_candidates_from_ledger()` | `canon.py:233-245` | 未来可按 kind 区分；第一轮不改行为 |
| `_read_confidence_row()` | `confidence.py:46-59` | 不变 |
| annotation `_min_max.py` | `core/annotation/_min_max.py` | internal prototype，不改 |
| evidence tree summary/narrative/NL | `core/store/_candidate_evidence_tree_*.py` | 第一轮不改；future: summary 可包含 confidence_kind |

## 5. Implementation Plan

### Phase 1: Core dataclass

1. `candidates.py`: 增加 `confidence_kind: str = "none"` 字段
2. `candidates.py` `__post_init__`: 增加 `confidence_kind` 校验（必须在 `{"none", "probability", "certainty"}` 中）
3. `candidates.py` `make_candidate()`: 增加 `confidence_kind` 参数，default `"none"`

### Phase 2: Production sites

4. `_builders.py`: `candidates_from_bindings()` 和 `entity_candidates_from_bindings()` 传 `confidence_kind="none"`（显式）
5. `runtime.py`: `evaluate_dummy()` 传 `confidence_kind="none"`
6. `problog_import.py`: `replace(candidate, confidence=prob, confidence_kind="probability")`

### Phase 3: Propagation + serialization

7. `sdk/store.py` `_with_candidate_run_id()`: 复制 `confidence_kind`
8. `runtime_v1.py` `_candidate_to_dict()`: 写入 `confidence_kind`
9. `runtime_v1.py` `_candidate_from_dict()`: 读取 `confidence_kind`（default `"none"`）
10. `accept.py` `_metadata_from_candidate_set()`: 写入 `confidence_kind` 到 ledger meta（additive）

### Phase 4: Tests + docs

11. 新增测试：验证 confidence_kind 校验、ProbLog 路径写入 `"probability"`、序列化 round-trip
12. 更新 `core/docs/01_architecture.md` CandidateSet 相关描述

## 6. Boundaries And Invariants

- `confidence_kind` 不影响 evaluate / accept / chosen 的执行行为
- `confidence_kind` 不进入 `candidate_key` 或 `candidate_id` 计算
- `confidence_kind` 不进入 `support_digest` 计算
- 现有 `confidence: float | None = None` 不变
- 向后兼容：任何不传 `confidence_kind` 的调用路径默认 `"none"`

## 7. Acceptance

- [x] `CandidateSet` 增加 `confidence_kind` 字段，带校验
- [x] `make_candidate` 接受 `confidence_kind` 参数
- [x] ProbLog 路径写入 `confidence_kind="probability"`
- [x] native / Souffle 路径写入 `confidence_kind="none"`
- [x] SDK candidate 复制保留 `confidence_kind`
- [x] service 序列化/反序列化 round-trip 正确
- [x] accept 路径写入 ledger meta
- [x] 全量测试通过 + 新增 confidence_kind 测试
- [x] core docs 更新

## 8. Outcome / Deviations

- 最终落地结果：
  - `CandidateSet`、`make_candidate()` 与 candidate production/propagation/serialization 路径现已统一支持 additive `confidence_kind`，枚举为 `"none" | "probability" | "certainty"`。
  - native / Souffle deterministic candidate 路径现显式写入 `confidence_kind="none"`；ProbLog 在回填 `candidate.confidence` 时同步写入 `confidence_kind="probability"`。
  - `accept` 现会把 `confidence_kind` 作为 claim meta 持久化；runtime candidate DTO 也已支持序列化、反序列化与 legacy missing-field fallback。
  - `sdk.validate_provenance(...)` / provenance coercion 与 write-protocol meta kind map 已同步纳入 `confidence_kind`。
- 与 blueprint 不同的地方：
  - 文档同步范围略宽于原计划；除 `core/docs/01_architecture.md` 外，还同步了 runtime service DTO 文档、service overview、ProbLog adapter 文档和 `CANDIDATE_PROTOCOL_V2.md`。
- 为什么会有这些调整：
  - `confidence_kind` 直接进入 runtime candidate DTO 与 accepted claim meta；若只更新 core 文档，会在 service/adapters/protocol 文档之间留下不一致。
- 归档说明：
  - 代码、测试与文档已对齐；该 child slice 已完成，可归档到 `docs/blueprints/archive/`。
