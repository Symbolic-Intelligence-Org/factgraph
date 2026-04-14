# `extract_document()` 使用手册

面向产品使用者。本文档介绍**如何调用** extraction 管道的 Python 产品 API。管道本身的实现口径(Scope / Responsibilities / Non-responsibilities / Limitations)见同目录 [README.md](./README.md);HTTP 端点契约见 [../../../service/docs/05_extraction.md](../../../service/docs/05_extraction.md)。

## 0. 安装

```bash
pip install -e ".[extraction,documents]"
```

提供至少一个 LLM provider key:

```bash
export MISTRAL_API_KEY="..."   # 默认推荐(免费 + F1 78%)
# 或
export OPENAI_API_KEY="..."
```

如果项目里用 `.env`,注意 `KEY = "value"`(带空格等号)**不是 POSIX shell 语法**,`source .env` 会报错;需要用 `awk -F ' = '` 解析后手动 `export`。

## 1. 最小示例

```python
from factpy_kernel.sdk import Entity, Field, Identity
from factpy_kernel.agent.extraction import extract_document

class Module(Entity):
    name: str = Identity(primary_key=True)
    description: str = Field(cardinality="single")

with open("readme.md", "rb") as f:
    result = extract_document(
        content=f.read(),
        doc_name="readme.md",
        schema_classes=[Module],
        model="mistral/mistral-small-latest",
    )

for fact in result.facts:
    print(fact.entity_type, fact.entity_identity, fact.pred_id, fact.field_values)
```

一个函数调用完成:`compile_schema_from_classes → DocumentStaging → BatchExtractor(+ gleaning) → EntityResolver(+ alias merge)`。

## 2. 两个入口

| 函数 | 何时用 |
|---|---|
| `extract_document(schema_classes=[...])` | 你在 Python 里用 `Entity` 子类定义 schema;API 内部会帮你 compile |
| `extract_document_from_ir(schema_ir={...})` | 你已经持有 pre-compiled Schema IR(dict);HTTP handler 走这条 |

两者之后的管道完全一致。

## 3. 参数语义

```python
extract_document(
    *,
    content: bytes,                                  # 必填:文档原始 bytes
    doc_name: str,                                   # 必填:人类可读文件名(走 F1 passthrough 进 prompt)
    schema_classes: list[type],                      # 必填:Entity 子类列表
    model: str | None = None,                        # 见 §4
    temperature: float | None = None,
    timeout_seconds: float | None = None,
    entity_descriptions: dict[str, str] | None = None,  # 见 §5
    allowed_entity_types: frozenset[str] | None = None, # 见 §6
    allowed_pred_ids: frozenset[str] | None = None,     # 见 §6
    enable_gleaning: bool = True,                    # 见 §7
    enable_alias_merge: bool = True,                 # 见 §7
    max_batch_size: int = 1000,
    require_source: bool = True,
    extraction_config: ExtractionConfig | None = None,
)
```

### §4 `model` / `temperature` / `timeout_seconds`

三者都遵循 **call-time 优先级链**:

1. 函数显式传参 → 最高
2. `extraction_config` 里的对应字段 → 次高
3. 环境变量 `FACTPY_EXTRACTION_MODEL` / `FACTPY_EXTRACTION_TEMPERATURE` / `FACTPY_EXTRACTION_TIMEOUT`
4. 硬编码默认:`gpt-4.1` / `0.0` / `30.0`

已验证模型(2026-04-13 benchmark):

| Model | F1 | 可靠性 | 成本 | 推荐场景 |
|---|---|---|---|---|
| `mistral/mistral-small-latest` | **78%** | 10/10 | **免费** | 默认推荐 |
| `gpt-4.1` | 68% | 10/10 | $0.002/1K tok | precision 优先 / 零 hallucination 场景 |
| `gpt-4.1-mini` | 40% | 10/10 | $0.0004/1K tok | 成本敏感且能接受低 recall |

Mistral 路径会自动走 `instructor.from_mistral()` + `Mode.MISTRAL_STRUCTURED_OUTPUTS`,绕开 litellm 的 parallel tool calling bug。

### §5 `entity_descriptions`

为 entity type 注入 1 句话语义描述,帮 LLM 区分软件组件 / 文档 / 团队 / 角色等容易混淆的概念。

```python
entity_descriptions = {
    "Module": "A software component or service, not a team or a role.",
    "Document": "A written artifact with a stable identifier (file name / doc id).",
}
```

**何时用**:当你的 schema 里有抽象名词(Module / Component / Service),且文档里出现了类似组织名 / 团队名会被混淆时。

**何时不用**:schema entity 语义本来就很具体(Person / Country / Regulation),不需要额外澄清。

### §6 `allowed_entity_types` / `allowed_pred_ids`

不传就自动从 compiled `schema_ir` 推导(95% 情况都不需要传)。

手动传只在:想在同一个 schema 里**切一个子集**出来走当次调用(例如只抽 `Regulation` + `Requirement`,忽略 `Organization`)。

### §7 `enable_gleaning` / `enable_alias_merge`

| 开关 | 默认 | 打开后 |
|---|---|---|
| `enable_gleaning` | `True` | batch pass 1 结束后,对低 yield segment 做二次扫描;新增 facts 进 `aggregated_specs` 但不回写 pass-1 metrics |
| `enable_alias_merge` | `True` | resolver 在 exact dedupe 前做一层保守 token-subset alias canonicalization(仅单字符串 identity field) |

关掉的场景:

- `enable_gleaning=False`:想**精确复现** pass-1 only 的基准行为;或 LLM 免费 tier 被限速严重,想减一半 API 调用
- `enable_alias_merge=False`:想看 resolver **没做合并前**的原始 specs(调试用)

## 4. 返回值结构

```python
@dataclass(frozen=True)
class ExtractionDocumentResult:
    doc_name: str                            # 你传入的 doc_name
    doc_id: str                              # staging 基于内容 hash 派生的稳定 id
    entities: tuple[dict, ...]               # 按 (entity_type, identity) 聚合后的 census
    facts: tuple[FactDraftSpec, ...]         # resolved 后的完整 fact specs
    metrics: BatchExtractionMetrics          # pass-1 only metrics
    merge_events: tuple[MergeEvent, ...]     # resolver 合并事件(含 alias_merge bool)
    gleaning_segments_reexamined: int        # second pass 覆盖的 segment 数
    staging_segments: int                    # staging 产出的总 segment 数
    model: str                               # 最终使用的 normalized model 名(Mistral 会去掉 `mistral/` 前缀)
```

读 facts:

```python
for spec in result.facts:
    print(spec.entity_type)          # 例如 "Regulation"
    print(spec.entity_identity)      # 例如 {"title": "Regulation (EU) 2022/2554"}
    print(spec.pred_id)              # 例如 "Regulation:summary"
    print(list(spec.field_values))   # 例如 [("string", "Sets out uniform requirements for ...")]
    print(spec.confidence)           # 0.0-1.0 或 None
```

`entities[]` 里每条是 `{"entity_type": ..., "identity": {...}, "fact_count": N}`。

## 5. 常见失败模式

所有失败都抛 `ExtractionDocumentError(stage, detail, message)`,`stage ∈ {"staging", "extraction", "resolution"}`。

### 5.1 `stage="staging"`

`staging` 阶段抛 `StagingError`,通常:

- 文件格式不支持
- PDF 破损 / 加密
- 空文档

诊断:换一个已知能 parse 的 .md 小文件冒烟;确认 `.[documents]` extras 已装(`pip install -e ".[documents]"`)。

### 5.2 `stage="extraction"`,message 含 `Unauthorized`

LLM provider 认证失败。最常见的是**脚本 / notebook 进程没有把 env var 读进来**:

```bash
# 确认 env 真的在当前 shell 里
echo "MISTRAL=${#MISTRAL_API_KEY} OPENAI=${#OPENAI_API_KEY}"
# 若都是 0,从 .env 手动 export(见 §0 陷阱)
```

### 5.3 `stage="resolution"`,message 含 `specs must be non-empty list`

上游 extraction 产出了 0 条 valid proposal,resolver 拒绝空输入。常见原因:

- 文档内容和 `schema_ir` 完全不匹配(例如 schema 定义的是代码模块,文档是厨房菜谱)
- LLM 免费 tier 被限速,所有 segment 都退化到 retry 耗尽
- 模型能力不足(`gpt-4.1-mini` 在长文档上 recall 只有 28%)

诊断:先用 `examples/dora_pdf_extract.py --max-segments 2` 跑短样本确认链路;再检查 `valid_count / proposal_count` 比例;再考虑换更强的模型。

## 6. 已知限制

这些是当前 schema / prompt 设计的真实边界,调用方需要知道,但**不会在本轮修**:

- **`title` 既是 Identity 又是 Field 时 LLM 会混淆**:Entity 子类用 `Identity(primary_key=True)` 标注 `title` 字段后,schema 会同时导出 `title` 为 identity 和为一个普通 predicate。英文里"Title III"(章节标题)会被 LLM 塞进 `.title` 条目,造成语义污染。DORA RTS PDF 实跑实测:27/109 facts 在 `.title` 上存在这种污染。**缓解**:避免用 `title` 作为 identity field 名;改用 `name` / `id` / `ref` 等不容易在 prose 里撞车的词。
- **`.exists` unary predicate 噪声较高**:schema compile 会为每个 entity 自动生成 unary `{entity_type}:exists`,LLM 会大量产出这种 fact(DORA 实测 26/109)。对下游有用度低,但**不是错**。如果要过滤:在读 `result.facts` 时 `if not spec.pred_id.endswith(":exists")`。
- **staging 对规整 PDF 会切得过细**:DORA RTS PDF 22 页产生 801 个 segment,均值 158 字符。对 LLM 而言每段信息量过少;在脚本/notebook 层要按 `min_chars` 过滤后再送 extraction(参考 `examples/dora_pdf_extract.py`)。
- **Mistral 免费 tier 有速率上限**:10+ 段的文档连续抽取可能触发 rate limit;表现为 `instructor_retry_exhausted`。短期规避:加 sleep、减段数、或切 OpenAI。

## 7. 何时用这个 API、何时用 HTTP

| 场景 | 推荐 |
|---|---|
| 同进程脚本 / notebook / 本地 CLI | 直接用 `extract_document()` |
| 前端 / 跨服务调用 / 需要 auth 边界 | 走 `POST /v1/extraction/documents`([契约](../../../service/docs/05_extraction.md)) |
| 需要复用已编译 schema IR 的长流程 | `extract_document_from_ir(schema_ir=...)` |

## 8. 相关文档

- [README.md](./README.md):extraction 模块实现口径(Scope / Responsibilities)
- [../../../service/docs/05_extraction.md](../../../service/docs/05_extraction.md):HTTP 端点 DTO 契约
- [../../documents/docs/README.md](../../documents/docs/README.md):staging 层格式支持与 segmentation 策略
- [../../../../docs/references/cross-provider-entity-benchmark-report.md](../../../../docs/references/cross-provider-entity-benchmark-report.md):模型推荐依据(Mistral Small F1=78%)
- `examples/09_dora_document_extraction.ipynb`:DORA 端到端 real-LLM 交互式 demo
- `examples/dora_pdf_extract.py`:真实 PDF 的 CLI 调用样例
