# Blueprint: Agent Layer 4C1 — Deterministic Document Staging

- Status: implemented
- Created: 2026-04-10
- Parent: [2026-04-09_dialog-agent-blueprint-v1.1-delta.md](./2026-04-09_dialog-agent-blueprint-v1.1-delta.md)
- Depends on: Layer 4B Conservative Engine Routing (implemented, archived)
- Related Modules:
  - `src/factpy_kernel/agent/documents/` (新建)
  - `src/factpy_kernel/agent/documents/staging.py` (新建)
  - `src/factpy_kernel/agent/documents/models.py` (新建)
  - `src/factpy_kernel/agent/documents/parsers/` (新建)
  - `src/factpy_kernel/agent/orchestrator.py` (扩展)
  - `src/factpy_kernel/agent/framework.py` (扩展)

---

## 0. 目标与边界

**交付目标**：将输入文档转为可审计的确定性 segment 列表，每段带 doc_id / segment_id / page / offsets / raw_text / structural_clarity。不涉及 LLM、不提取 fact/rule。

**冻结决策**：

| # | 决策 | 理由 |
|---|------|------|
| L4C1-01 | Stage 1 只做确定性分段与 provenance，不做 LLM 提取 | 确定性底座是审计链锚点；LLM 分段不可复现 |
| L4C1-02 | v1 只产出文档 segment DTO，不直接产出 FactDraft | FactDraft 构造是 4C2/4C3 的事；4C1 只做 staging |
| L4C1-03 | v1 只支持单文档输入，不做跨文档去重/消歧 | 跨文档 entity resolution 是独立问题 |
| L4C1-04 | OCR、规则提取、多文档 bundle 明确排除 | 扫描件 OCR / rule extraction / bundle 是后续能力 |

**明确排除**：
- LLM 调用 / schema 约束提取
- FactDraft / RuleDraft 生成
- OCR（扫描件图像→文本）
- 跨文档 entity resolution / 去重
- 多文档批量输入
- 审批 UI（批量 review 是 4C2）

---

## 1. 支持的文档格式

| 格式 | 处理方式 | 依赖 | 优先级 |
|------|---------|------|--------|
| PDF（原生嵌入文本） | PyMuPDF via `pymupdf4llm` | pymupdf + pymupdf4llm | P0 |
| DOCX | python-docx | python-docx | P0 |
| TXT / Markdown | 内置分段 | 无 | P0 |
| PDF（扫描件） | 不支持 | — | 排除（OCR） |
| HTML | 可选 | beautifulsoup4 | P1（后续） |

### 1.1 PyMuPDF 选型理由（对齐 delta §1.1）

- 速度：0.12s（原生 PDF）
- 自托管、零成本、Apache 2.0
- `pymupdf4llm` 直接产出带结构信息的 markdown
- 与 Docling 互补：复杂文档/表格用 Docling，4C1 暂不引入（留给 4C3 的精准提取）

### 1.2 为什么不是 Docling（4C1 阶段）

Docling 需要 GPU + 更重的模型（DocLayNet, TableFormer）。4C1 目标是"分段 + offset"，PyMuPDF 已经足够。Docling 在 4C3 的复杂文档/表格场景再引入。

---

## 2. 数据模型

### 2.1 核心 DTO

```python
from dataclasses import dataclass, field
from typing import Literal
import time


@dataclass(frozen=True)
class DocumentSource:
    """
    文档来源登记。只读。

    doc_id 是内容哈希，保证同一文档不重复入库。
    doc_name 仅供展示，不参与幂等性判断。
    """
    doc_id: str                              # sha256(文档二进制内容) hex prefix
    doc_name: str                            # 原始文件名
    doc_type: Literal["pdf", "docx", "txt", "md"]
    byte_size: int                           # 原始字节数
    ingested_at: int                         # epoch_nanos


@dataclass(frozen=True)
class DocumentSegment:
    """
    预处理阶段输出的确定性文本段。

    确定性约束：对同一 (doc_id, parser_version, config) 的输入，
    必须产出相同的 segment 列表（相同顺序、相同 offset、相同 clarity 评分）。
    """
    segment_id: str                          # doc_id[:8] + "_" + zero-padded index
    doc_id: str                              # references DocumentSource.doc_id
    segment_index: int                       # 0-based 文档内顺序
    section_label: str | None                # "Article 3.2" / "第五条" 等章节标签
    page_number: int | None                  # PDF 页码（其他格式 None）
    char_offset_start: int                   # 在全文提取文本中的字符起始偏移
    char_offset_end: int                     # 字符结束偏移（不含）
    raw_text: str                            # 对应的原始文本片段
    structural_clarity: float                # [0, 1] 结构清晰度评分
    pattern_type: Literal[
        "if_then",                           # 明确的条件-结论结构
        "entity_relation",                   # 实体关系陈述
        "definition",                        # 定义句
        "narrative",                         # 叙述性，结构不明确
    ]
    parser_version: str                      # 产出此 segment 的 parser 版本标识


@dataclass(frozen=True)
class StagingResult:
    """文档 staging 的完整结果。"""
    source: DocumentSource
    segments: tuple[DocumentSegment, ...]
    total_chars: int                         # 全文提取后的字符总数
    high_clarity_count: int                  # structural_clarity >= 0.7 的段数
    parser_name: str                         # "pymupdf" / "python_docx" / "txt"
    parser_version: str
    staged_at: int                           # epoch_nanos
```

### 2.2 StagingError

```python
@dataclass
class StagingError:
    """文档 staging 失败（不抛异常）。"""
    doc_name: str
    error_kind: str                          # "unsupported_format" | "parse_failure" | "empty_document"
    error_message: str
```

---

## 3. Parser 接口

### 3.1 抽象接口

```python
from typing import Protocol


class DocumentParser(Protocol):
    """确定性文档解析器接口。无 LLM 调用。"""

    parser_name: str                         # "pymupdf" / "python_docx" / "txt"
    parser_version: str                      # 语义化版本

    def can_parse(self, doc_type: str) -> bool:
        """是否支持此文档类型。"""
        ...

    def parse(
        self,
        source: DocumentSource,
        content: bytes,
    ) -> list[DocumentSegment]:
        """
        解析文档内容为 segment 列表。

        确定性要求：
        - 对同一 (source, content, parser_version) 输入必须产出相同输出
        - segment_index 从 0 递增，与文档内顺序一致
        - char_offset 在全文提取文本上连续（允许 gap 但不允许重叠）

        失败时 raise ParseError。
        """
        ...
```

### 3.2 具体 parser 实现

**PyMuPDFParser** (`documents/parsers/pdf.py`):
```python
class PyMuPDFParser:
    parser_name = "pymupdf"
    parser_version = "0.1.0"

    def parse(self, source, content):
        # 1. 用 pymupdf4llm 打开 content (bytes → BytesIO → Document)
        # 2. 逐页提取 markdown + 页码映射
        # 3. 按段落分段（pymupdf4llm 的 chunk 语义）
        # 4. 对每段计算 char_offset（累积偏移）
        # 5. 检测 section_label（启发式：# 标题 / 第 X 条 / Article X 等）
        # 6. 计算 structural_clarity + pattern_type
        ...
```

**PythonDocxParser** (`documents/parsers/docx.py`):
```python
class PythonDocxParser:
    parser_name = "python_docx"
    parser_version = "0.1.0"

    def parse(self, source, content):
        # 1. python-docx 打开 content
        # 2. 遍历 paragraphs + tables
        # 3. section_label 从 heading style 提取
        # 4. char_offset 按拼接顺序累积
        ...
```

**PlainTextParser** (`documents/parsers/txt.py`):
```python
class PlainTextParser:
    parser_name = "txt"
    parser_version = "0.1.0"

    def parse(self, source, content):
        # 1. decode content (utf-8, fallback to latin-1)
        # 2. 按空行分段
        # 3. section_label = None
        # 4. char_offset 自然对应原文位置
        ...
```

---

## 4. structural_clarity 评分规则

### 4.1 v1 启发式（L4C1-05 冻结）

```python
def compute_structural_clarity(text: str) -> tuple[float, str]:
    """
    返回 (clarity_score, pattern_type)。
    v1 用正则 + 关键词启发式，不用 LLM。
    """
    # 1. if-then 模式检测
    if_then_patterns = [
        r"if\s+.+\s+then\s+",
        r"当\s*.+\s*时",
        r"若\s*.+\s*则",
        r"shall\s+.+\s+when",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in if_then_patterns):
        return (0.9, "if_then")

    # 2. 定义句检测
    definition_patterns = [
        r"^.+\s+(means|refers to|is defined as)\s+",
        r"^.+\s*[::]\s*指\s*",
    ]
    if any(re.search(p, text, re.IGNORECASE) for p in definition_patterns):
        return (0.7, "definition")

    # 3. 实体关系句（主谓宾）
    # 启发式：短句（<100 字）含明确动词
    if len(text) < 100 and _has_clear_verb(text):
        return (0.5, "entity_relation")

    # 4. 叙述性（默认）
    return (0.2, "narrative")
```

### 4.2 为什么 v1 不做更复杂的评分

- NLP-based 评分需要模型依赖（spaCy/stanza），增加部署复杂度
- structural_clarity 在 4C1 只是 "给 4C3 的 LLM 精炼做优先级排序"，不是硬约束
- 4C3 的 LLM 精炼阶段才真正决定提取质量，4C1 评分是粗筛

### 4.3 section_label 检测启发式

```python
SECTION_PATTERNS = [
    r"^#{1,6}\s+(.+)$",                      # Markdown heading
    r"^(Article\s+\d+(?:\.\d+)*)",           # Article 3.2
    r"^(第\s*[一二三四五六七八九十百零\d]+\s*(?:条|章|节))",  # 第五条
    r"^(Section\s+\d+(?:\.\d+)*)",           # Section 4.1
]
```

---

## 5. DocumentStaging — Orchestration 层

### 5.1 DocumentStaging 类

```python
class DocumentStaging:
    """
    文档 staging 编排层。
    组合 DocumentSource 构造 + parser 选择 + StagingResult 产出。

    不依赖 AgentSession。这是纯粹的 document processing 层。
    """

    def __init__(self, parsers: list[DocumentParser] | None = None) -> None:
        """
        parsers: 自定义 parser 列表；None 时使用依赖感知的内置注册。

        内置注册策略（L4C1-12 冻结）：
        - PlainTextParser: 始终注册（无第三方依赖）
        - PyMuPDFParser: 仅当 pymupdf 和 pymupdf4llm 均可 import 时注册
        - PythonDocxParser: 仅当 python-docx 可 import 时注册

        缺依赖 → 该 parser 不注册 → 对应格式视为 unsupported。
        不新增 error kind；stage_document 对缺依赖格式返回
        StagingError(error_kind="unsupported_format", ...)。
        """
        ...

    def stage_document(
        self,
        *,
        doc_name: str,
        content: bytes,
        doc_type: str | None = None,
    ) -> StagingResult | StagingError:
        """
        1. 计算 doc_id = sha256(content)[:16]
        2. 推断 doc_type（from doc_name extension or explicit）
        3. 选择 parser: 遍历 parsers, 找 can_parse(doc_type) == True
           - 无匹配 parser → StagingError("unsupported_format")
        4. 构造 DocumentSource
        5. parser.parse(source, content)
        6. 包装为 StagingResult

        不抛异常。所有失败返回 StagingError。
        """
        ...

    def list_supported_formats(self) -> list[str]:
        """
        返回当前 DocumentStaging 实例能实际解析的 doc_type 列表。
        只包含已注册 parser（即依赖可用的 parser）支持的格式。

        示例：
        - 未装 pymupdf → 返回不含 "pdf"
        - 全部依赖可用 → ["txt", "md", "pdf", "docx"]
        """
        ...
```

### 5.2 确定性保证

同一 `(content, parser_version)` 必须产出相同 StagingResult：
- `doc_id` 从 content 计算 → 确定
- `segments` 由 parser 产出 → parser 承诺确定性
- `staged_at` 不影响结构（仅时间戳）
- 测试通过 `hash_segments(result.segments) == hash_segments(re_staged.segments)` 验证

---

## 6. Orchestrator 扩展

```python
class ReadReviewOrchestrator:
    # ... existing methods ...

    # ── Layer 4C1: Document Staging ──

    def stage_document(
        self,
        *,
        doc_name: str,
        content: bytes,
        doc_type: str | None = None,
    ) -> StagingResult | StagingError:
        """
        将文档送入 staging 层。不写入 ledger。

        返回 StagingResult（segments 可用于后续 4C2/4C3 消费）
        或 StagingError（解析失败）。

        不 checkpoint（staging 不影响 agent session state）。
        """
        ...

    def list_supported_document_formats(self) -> list[str]:
        """列出支持的文档格式。"""
        ...
```

### 6.1 为什么不 checkpoint

StagingResult 是纯函数输出，不影响 AgentSession 或 DraftManager 状态。4C1 不持久化 staging 结果——调用方负责保留（或传给 4C2）。

### 6.2 不写入 ledger

4C1 只做 staging。DocumentSource 和 segments 不入 ledger。Ledger 写入是 4C2（DraftBundle commit）的事。

---

## 7. Tool Registry 扩展

Layer 4B 注册了 31 个 tool。Layer 4C1 追加：

```python
# 扩展 build_layer3a_tool_registry()

"stage_document":                      → orchestrator.stage_document
"list_supported_document_formats":     → orchestrator.list_supported_document_formats
```

Layer 4C1 总计 33 个 tool（31 Layer 4B + 2 Layer 4C1）。

---

## 8. 实现顺序

```
Step 1: 数据模型
        → DocumentSource / DocumentSegment / StagingResult / StagingError
        → 纯 dataclass
        → 单测：序列化 / 哈希 / 字段验证

Step 2: DocumentParser Protocol + PlainTextParser
        → 最简单的 parser 先做，建立模式
        → 单测：确定性、offset 正确性

Step 3: structural_clarity + section_label 启发式
        → 纯函数
        → 单测：多种文本类型

Step 4: PyMuPDFParser
        → 依赖 pymupdf (pyproject.toml 加依赖)
        → 单测：多种 PDF 样本、多页、带章节的 PDF

Step 5: PythonDocxParser
        → 依赖 python-docx
        → 单测：heading / paragraph / table

Step 6: DocumentStaging 类
        → parser 注册 + 路由 + 错误处理
        → 单测：格式推断、确定性、错误分支

Step 7: Orchestrator 扩展
        → stage_document / list_supported_document_formats
        → 集成测试：端到端 staging 多格式文档

Step 8: Tool Registry 扩展
        → 33 tool 全量注册验证
```

---

## 9. 目录结构增量

```
src/factpy_kernel/agent/
  ├── documents/                    # (新建) 文档处理子包
  │   ├── __init__.py
  │   ├── models.py                 # DocumentSource / DocumentSegment / StagingResult / StagingError
  │   ├── staging.py                # DocumentStaging 类
  │   ├── clarity.py                # structural_clarity + section_label 启发式
  │   └── parsers/
  │       ├── __init__.py
  │       ├── base.py               # DocumentParser Protocol
  │       ├── txt.py                # PlainTextParser
  │       ├── pdf.py                # PyMuPDFParser
  │       └── docx.py               # PythonDocxParser
  ├── orchestrator.py               # (扩展) +stage_document +list_supported_document_formats
  ├── framework.py                  # (扩展) tool registry 33 tools
  └── __init__.py                   # (扩展) export 新数据结构

src/factpy_kernel/tests/
  ├── test_agent_l4c1_models.py            # (新建)
  ├── test_agent_l4c1_clarity.py           # (新建)
  ├── test_agent_l4c1_txt_parser.py        # (新建)
  ├── test_agent_l4c1_pdf_parser.py        # (新建)
  ├── test_agent_l4c1_docx_parser.py       # (新建)
  └── test_agent_l4c1_staging.py           # (新建) 端到端
```

### 9.1 pyproject.toml 依赖变更

```toml
# optional dependencies
documents = [
    "pymupdf>=1.24",
    "pymupdf4llm>=0.0.17",
    "python-docx>=1.1",
]
```

4C1 作为可选依赖组。base agent 安装不强制引入 pymupdf/python-docx。

---

## 10. 验收标准

1. **DocumentSource doc_id 幂等**：同一 bytes 两次 stage 产生相同 doc_id
2. **Segments 确定性**：同一 (content, parser_version) 两次 stage 产生相同 segment 序列（包括 offset、clarity、pattern_type）
3. **PyMuPDFParser**：多页原生 PDF 正确分段，char_offset 连续不重叠
4. **PythonDocxParser**：heading style 正确提取为 section_label
5. **PlainTextParser**：按空行分段，offset 对应原文位置
6. **structural_clarity**：if-then 句 ≥ 0.7；叙述句 ≤ 0.3
7. **section_label**：识别 `# 标题` / `Article 3.2` / `第五条` 三种模式
8. **StagingError 不抛异常**：unsupported format / parse failure / empty doc 均返回 StagingError
8a. **依赖感知注册（L4C1-12）**：未安装 pymupdf/pymupdf4llm 时 list_supported_document_formats 不返回 "pdf"；stage_document 对 PDF 输入返回 StagingError(error_kind="unsupported_format")；不新增 error kind
9. **L4C1-01**：无任何 LLM 调用
10. **L4C1-02**：不产出 FactDraft
11. **Tool 数量**：33 个
12. **单测 + 集成测试**覆盖

---

## 11. 已知约束

1. **PyMuPDF 不支持扫描件 OCR**：扫描件 PDF 会产出空文本或乱码。parse 时检测 `total_chars < threshold` → 返回 StagingError("empty_document")，明确提示不支持。
2. **DOCX 表格扁平化**：table → 按 cell 顺序拼接为段落。复杂表格结构丢失（4C3 可引入 Docling 补齐）。
3. **中文 PDF 的字符切分**：pymupdf4llm 可能在 CJK 文本上产生非预期的空格。raw_text 保留原始值，不做后处理。
4. **structural_clarity 是启发式**：不是语义分析。对"隐含条件-结论"结构（如隐含主语的祈使句）会低估。
5. **parser_version 必须稳定**：bump parser_version 会让所有旧文档的确定性约束失效。升级 parser 时应保留旧版本兼容。
6. **跨文档 entity 不去重**：v1 不检查同一 entity 是否已在其他文档出现过。这是 4C2/4C3 的事。
7. **byte_size 计算基于输入 bytes**：如果调用方传入 content 是 BytesIO.read() 的结果，byte_size 与磁盘文件一致；如果调用方预处理过（如解压），byte_size 是预处理后的值。

---

## 12. Outcome / Deviations

### Outcome

- 新增 `agent/documents/` 子包：`models.py` / `clarity.py` / `staging.py` / `parsers/`，落地 Layer 4C1 的确定性 document staging
- `ReadReviewOrchestrator` 扩展了 `stage_document()` 与 `list_supported_document_formats()`；`build_layer3a_tool_registry()` 从 31 tools 扩展到 33 tools
- 新增 `agent/documents/docs/README.md`，并同步更新 `agent/docs/README.md` 与仓库 `docs/README.md`
- 新增 Layer 4C1 定向测试：models / clarity / txt parser / pdf parser / docx parser / staging；相关 Layer 3A/W2a/4A/4B registry 断言同步更新

### Deviations

1. PDF parser 当前在依赖感知注册时要求 `pymupdf4llm` 可用，但实际 v1 分段实现为了保持 offset 计算简单稳定，使用的是 PyMuPDF block text 提取而不是直接消费 `pymupdf4llm` 的 chunk 输出；`pymupdf4llm` 仍保留为 4C1 的合同依赖，以便后续复杂 PDF 结构抽取继续对齐 blueprint 方向。
2. 由于当前环境未安装 `pymupdf4llm`，PDF 正向解析测试以 dependency-gated skip 形式落地；同时通过 `DocumentStaging` 的 `unsupported_format` 路径验证了缺依赖合同。
