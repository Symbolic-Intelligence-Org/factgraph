# Blueprint: Extraction Product API — Env Config + High-Level Interface

- Status: implemented with deviations
- Created: 2026-04-13
- Kind: **extraction layer product interface** (new public API + config externalization)
- Trigger: Benchmark 确认 gpt-4.1 为最佳模型 + 当前调用需要 7 个对象手动组装,不适合产品化
- Related Modules:
  - `src/factpy_kernel/agent/extraction/models.py` (default model change)
  - `src/factpy_kernel/agent/extraction/extractor.py` (thread `entity_descriptions`)
  - `src/factpy_kernel/agent/extraction/batch.py` (thread `entity_descriptions`)
  - `src/factpy_kernel/agent/extraction/api.py` (**新文件**)
  - `src/factpy_kernel/agent/extraction/__init__.py` (导出)
- Audit Log:
  - [2026-04-13_extraction-product-api.audit.md](./2026-04-13_extraction-product-api.audit.md)

---

## 0. Scope

两层改进:

**Layer 1 — ExtractionConfig 默认模型升级 + `entity_descriptions` 透传**:
- `ExtractionConfig.model` 默认值从 `"gpt-4o-mini"` 改为 `"gpt-4.1"`(纯常量,不含 env 逻辑)
- `entity_descriptions` 参数透传: `extract_from_segment` + `extract_batch` 各加 optional param,线程到 `build_schema_summary`

**Layer 2 — `extract_document()` 高层 API**:
一个函数封装完整的 staging → extraction → resolution 链路。env 变量解析在此函数内部做(call-time,非 import-time)。

```python
from factpy_kernel.agent.extraction import extract_document

result = extract_document(
    content=open("readme.pdf", "rb").read(),
    doc_name="readme.pdf",
    schema_classes=[Document, Module],
    entity_descriptions={"Module": "A software component..."},
)
print(result.facts)
print(result.entities)
```

**做什么**:
- `models.py`: `ExtractionConfig.model` 默认值改为 `"gpt-4.1"`(1 行)
- `extractor.py`: `extract_from_segment` 加 `entity_descriptions` 参数,透传到 `build_schema_summary`(~5 行)
- `batch.py`: `extract_batch` 加 `entity_descriptions` 参数,透传到两处 `extract_from_segment`(~5 行)
- `api.py`: 新文件,`extract_document()` + `ExtractionDocumentResult`(~130 行)
- `__init__.py`: 导出新 API(+3 行)
- 测试: env config tests + API 集成 tests + `_FakeExtractionAgent` 签名更新

**不做什么**:
- 不改 prompts.py / validation.py / resolution.py / DocumentStaging
- 不做 HTTP endpoint(service 层的事)
- 不做 provider 抽象(litellm 已覆盖)
- 不做 commit pathway(extract_document 止于 resolution)
- 不做 async 版本

---

## 1. Scope Check v1 Findings (Fixed)

### P1-1: `entity_descriptions` 无路径注入 prompt

**问题**: v1 blueprint 接受 `entity_descriptions` 参数但不改 extraction 内部。`ExtractionAgent.extract_from_segment` 在 `extractor.py:88` 硬编码 `build_schema_summary(schema_ir)`,无法接收 `entity_descriptions`。

**修复**: 扩展 scope — 把 `entity_descriptions` 参数透传到 `extract_from_segment` → `build_schema_summary`。和 P0 的 `prior_entity_context` / F1 的 `source_doc_name` 完全同构的"可选参数透传"模式。`extractor.py` 和 `batch.py` 现在在 scope 内(各加 ~5 行)。

### P1-2: Import-time env 解析

**问题**: v1 blueprint 用 `os.environ.get(...)` 做 dataclass field 默认值,在 module import time 求值。如果 `.env` 在 import 之后加载,env 变量无效。

**修复**: `ExtractionConfig` 保持纯 dataclass,默认值是简单常量 `"gpt-4.1"`,不含任何 env 逻辑。Env 解析移到 `extract_document()` 内部(call-time):

```python
def extract_document(..., model: str | None = None, ...):
    effective_model = (
        model                                                    # 1. 显式 scalar 参数
        or (extraction_config.model if extraction_config else None)  # 2. caller 传入的 config 对象
        or os.environ.get("FACTPY_EXTRACTION_MODEL")             # 3. env 变量(ambient)
        or ExtractionConfig().model                              # 4. 硬编码默认
    )
```

优先级: **显式 scalar > extraction_config > env > default**。Caller input(无论是 scalar 还是 config 对象)始终优先于 ambient env。Call-time 求值,`.env` loading 顺序不影响。

### P1-3: AgentScope 默认值不安全

**问题**: `AgentScope` 默认 `max_batch_size=10`, `require_source=False`。如果 `extract_document` 静默使用这些默认值,长文档会在 10 specs 后截断,且 provenance 不被要求。

**修复**: `extract_document` 显式参数化 + 产品安全默认值:

```python
def extract_document(
    ...,
    max_batch_size: int = 1000,         # 产品默认: 不截断常规文档
    require_source: bool = True,        # 产品默认: 要求 extraction provenance
    ...,
)
```

内部构造 `AgentScope` 时使用这些参数值,不依赖 `AgentScope` 的类级默认值。

---

## 2. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| API-01 | `ExtractionConfig.model` 默认值改为 `"gpt-4.1"` 纯常量。**不在 dataclass 里做 env 解析** | Scope check P1-2: import-time env 不可靠;env 逻辑属于 API 层 |
| API-02 | 优先级链: **显式 scalar > extraction_config > env > default**。Env 解析在 `extract_document()` call-time 做。支持 `FACTPY_EXTRACTION_MODEL` / `FACTPY_EXTRACTION_TEMPERATURE` / `FACTPY_EXTRACTION_TIMEOUT` | Scope check v3 P1-1: caller input(config 对象)必须优先于 ambient env;env 只在 caller 不传时生效 |
| API-03 | `extract_document` 不管 commit — 只做 extraction + resolution | Commit 需要 runtime session + orchestrator,属于更上层 workflow |
| API-04 | `allowed_entity_types` / `allowed_pred_ids` 自动从 schema_ir 推导。**不过滤 `:exists` predicates** — 全量 schema_ir 传给 extractor,scope 也包含全部 pred_ids | Scope check v3 P1-2: 过滤 `:exists` 会导致 scope 和 response model 不一致;v1 直接用全量 schema,不引入 filtered schema 层 |
| API-05 | `enable_gleaning=True`, `enable_alias_merge=True` 默认开启 | 产品接口给最佳默认配置 |
| API-06 | `max_batch_size=1000`, `require_source=True` 产品安全默认值 | Scope check P1-3: 不继承 AgentScope 的内部默认值 |
| API-07 | `entity_descriptions` 透传到 `ExtractionAgent.extract_from_segment` → `build_schema_summary` | Scope check P1-1: 和 P0/F1 同构的参数透传 |
| API-08 | `ExtractionDocumentResult` 是 frozen dataclass | 不可变,和现有 extraction models 一致 |
| API-09 | `extract_document` 在 staging/batch/resolution 失败时 raise `ExtractionDocumentError`(不返回 union) | 产品 API 用 try/except,不用 isinstance 判断;`ExtractionDocumentError` 携带 `stage` 字段标识失败阶段 + `detail` 字段携带底层 error object |
| API-10 | `extract_document` 内部始终传 `source_doc_name=doc_name` 给 `extract_batch` | 确保 F1 修复不被回退;LLM prompt 看到人类可读文件名而非 hash |

---

## 3. Implementation

### 3.1 `models.py` — 默认模型升级 (1 行)

```python
# 原: model: str = "gpt-4o-mini"
# 改: model: str = "gpt-4.1"
```

不加 env 逻辑。纯常量改动。

### 3.2 `extractor.py` — thread `entity_descriptions` (~5 行)

签名加参数:
```python
def extract_from_segment(
    self, *, segment, schema_ir, scope, config=None,
    prior_entity_context="", source_doc_name=None,
    entity_descriptions=None,          # ← 新增
):
```

内部 `build_schema_summary` 调用改为:
```python
schema_summary = build_schema_summary(schema_ir, entity_descriptions=entity_descriptions)
```

### 3.3 `batch.py` — thread `entity_descriptions` (~5 行)

`extract_batch` 签名加参数:
```python
def extract_batch(
    self, *, segments, schema_ir, scope, batch_config=None,
    source_doc_name=None,
    entity_descriptions=None,          # ← 新增
):
```

两处 `extract_from_segment` 调用(pass 1 + gleaning)各加 `entity_descriptions=entity_descriptions`。

### 3.4 `api.py` — 新文件 (~150 行)

```python
class ExtractionDocumentError(Exception):
    """Raised when extract_document fails at any pipeline stage."""
    def __init__(self, stage: str, detail: object, message: str) -> None:
        self.stage = stage      # "staging" | "extraction" | "resolution"
        self.detail = detail    # StagingError | BatchExtractionError | ResolutionError
        super().__init__(message)

@dataclass(frozen=True)
class ExtractionDocumentResult:
    doc_name: str
    doc_id: str
    entities: tuple[dict[str, object], ...]
    facts: tuple[FactDraftSpec, ...]
    metrics: BatchExtractionMetrics
    merge_events: tuple[MergeEvent, ...]
    gleaning_segments_reexamined: int
    staging_segments: int
    model: str

def extract_document(
    *,
    content: bytes,
    doc_name: str,
    schema_classes: list[type],
    model: str | None = None,
    temperature: float | None = None,
    timeout_seconds: float | None = None,
    entity_descriptions: dict[str, str] | None = None,
    allowed_entity_types: frozenset[str] | None = None,
    allowed_pred_ids: frozenset[str] | None = None,
    enable_gleaning: bool = True,
    enable_alias_merge: bool = True,
    max_batch_size: int = 1000,
    require_source: bool = True,
    extraction_config: ExtractionConfig | None = None,
) -> ExtractionDocumentResult:
```

**Config 解析在函数体内(call-time, API-02 优先级: scalar > config > env > default)**:
```python
effective_model = (
    model                                                        # 1. 显式 scalar
    or (extraction_config.model if extraction_config else None)   # 2. caller config
    or os.environ.get("FACTPY_EXTRACTION_MODEL")                 # 3. ambient env
    or ExtractionConfig().model                                  # 4. 硬编码默认
)
# temperature / timeout_seconds 同理,但 temperature 需要 `is not None` 判断(0.0 是合法值)
```

**Pipeline 调用(API-09 error contract + API-10 source_doc_name)**:
```python
# Staging
staging = DocumentStaging().stage_document(doc_name=doc_name, content=content)
if hasattr(staging, "error_kind"):
    raise ExtractionDocumentError("staging", staging, f"Staging failed: {staging.error_message}")

# Extraction — 显式传 source_doc_name=doc_name (API-10, 保持 F1 修复)
batch = extractor.extract_batch(
    segments=list(staging.segments),
    schema_ir=schema_ir,
    scope=scope,
    source_doc_name=doc_name,                    # ← API-10: F1 不回退
    entity_descriptions=entity_descriptions,     # ← API-07: 透传到 prompt
)
if isinstance(batch, BatchExtractionError):
    raise ExtractionDocumentError("extraction", batch, f"Extraction failed: {batch.error_message}")

# Resolution
resolved = resolver.resolve_batch(list(batch.aggregated_specs))
if isinstance(resolved, ResolutionError):
    raise ExtractionDocumentError("resolution", resolved, f"Resolution failed: {resolved.error_message}")
```

### 3.5 `__init__.py` — 导出 (+3 行)

### 3.6 测试

- `_FakeExtractionAgent` 两处签名加 `entity_descriptions=None`
- `test_agent_l4c3a_models.py`: 默认模型 = "gpt-4.1" 测试
- `test_agent_extraction_api.py` (新文件): extract_document 全链路 mock 测试 + env 解析测试 + scope auto-derive 测试 + 返回值结构测试

---

## 4. Non-goals

- 不做 HTTP endpoint / REST API
- 不做 provider 抽象
- 不做 commit pathway
- 不做 async 版本
- 不改 prompts.py / validation.py / resolution.py / DocumentStaging 内部

---

## 5. Acceptance Criteria

1. `ExtractionConfig().model == "gpt-4.1"`(默认值已升级)
2. `os.environ["FACTPY_EXTRACTION_MODEL"] = "gpt-4o"` → `extract_document(...)` 使用 gpt-4o(call-time env 解析)
3. `extract_document(content=..., doc_name="readme.md", schema_classes=[Doc, Mod])` 返回 `ExtractionDocumentResult` 且 `len(result.facts) > 0`
4. `result.entities` 包含去重后的 entity census
5. 不传 `max_batch_size` / `require_source` → 默认 `1000` / `True`(不继承 AgentScope 的 10/False)
6. `entity_descriptions={"Module": "..."}` 透传到 LLM prompt(schema summary 里出现 description 行)
7. Staging/extraction/resolution 失败 → raise `ExtractionDocumentError`,`stage` 字段标识阶段,`detail` 携带底层 error(API-09)
8. LLM prompt 中 `Document:` 字段显示 `doc_name`(人类可读),不显示 `doc_id` hash — F1 不回退(API-10)
9. Regression: 1012 + ~8 new tests green

---

## 6. Outcome / Deviations

- 最终落地结果：
  - `ExtractionConfig.model` 默认值已升级为 `gpt-4.1`
  - `entity_descriptions` 已透传到 `ExtractionAgent.extract_from_segment(...)` 与 `BatchExtractor.extract_batch(...)`
  - 新增高层 API `[extract_document](/Users/zhenzhili/hnsm-backend/src/factpy_kernel/agent/extraction/api.py)`，封装 schema compile → staging → extraction → resolution，并导出 `ExtractionDocumentResult` / `ExtractionDocumentError`
  - 全量回归通过：`1012 passed, 3 skipped, 0 failed`
  - 真 LLM behavioral verification 通过：对 `README.md -- Project Alpha` 样本运行 `extract_document(...)`，返回 `ExtractionDocumentResult`，`model='gpt-4.1'`，`staging_segments=7`，`gleaning_segments_reexamined=2`，`len(facts)=16`，`len(entities)=6`，且 `Document.title` 使用人类可读的 `README.md` 而非 hash
- 与 blueprint 不同的地方：
  - §3.6 里计划的专用 API tests (`test_agent_extraction_api.py` + 默认模型单测) 本轮没有补上；验证依赖 compile check、既有全量 regression，以及 1 次真 LLM 端到端 behavioral run
- 为什么会有这些调整：
  - 这轮实现先沿用已有 extraction test 面覆盖回归风险，把新增产品 API 的正确性用真实调用直接打通；专用 API tests 未影响本次功能落地，但与原 blueprint 测试面承诺不完全一致
- 归档说明：
  - 以 **implemented with deviations** 归档
  - 当前模块 truth 已写入 `src/factpy_kernel/agent/extraction/docs/README.md`
  - 观察到一个当前边界行为：若 extraction 产出 0 valid specs，`extract_document(...)` 会因 resolver 空输入而抛出 `ExtractionDocumentError(stage=\"resolution\")`；这与 API-09 failure contract 一致，但不是“空结果成功”语义
