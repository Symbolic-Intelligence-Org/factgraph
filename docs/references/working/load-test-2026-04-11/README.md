# Agent 真实文档负载测试 (B3)

- Created: 2026-04-11
- Scope: Agent Layer 4C 全链路（stage → extract → batch → resolve → bundle → commit）
- Related Modules:
  - `src/factpy_kernel/agent/documents/` (4C1/4C2)
  - `src/factpy_kernel/agent/extraction/` (4C3-a/b/c)
  - `src/factpy_kernel/agent/observability/` (Langfuse)
- Not a blueprint: 这是一轮验证工作，不经过 draft → scoped → implementing 流程

---

## 0. 目的

Agent 主线到 Layer 4C3-c + Langfuse 最小接入为止，全部功能已闭环。但我们还没有**真实文档跑批的失败模式数据**。本次验证的目的是：

1. 在真实文档上跑完 **stage → extract → batch → resolve → bundle → commit** 全链路
2. 收集失败分布、置信度分布、人工审批通过率
3. 识别出"需要修复的真实问题"，每个问题再决定是否开修复蓝图
4. **不是为了给 agent 加新功能**——是为了校准已有能力

**非目标**：
- 不做性能优化（除非发现明显 bug）
- 不改 agent 主合同
- 不验证 kernel 生产化（那是 C1 线）
- 不做并发/压力测试（顺序跑批）

---

## 1. 样本集

### 1.1 覆盖要求

**格式覆盖**：
- PDF（原生文本）: 3 份
- DOCX: 2 份
- TXT / Markdown: 2 份
- PDF（扫描件，预期失败）: 1 份 → 用来验证 `unsupported_format` 路径

**长度覆盖**：
- 短（< 5 segments / < 2 pages）: 2 份
- 中（5–30 segments / 2–10 pages）: 4 份
- 长（30+ segments / 10+ pages）: 2 份

**领域覆盖**（建议，非强制）：
- 法规/合同类（if-then 结构清晰）: 3 份
- 技术规范（entity_relation 为主）: 2 份
- 叙述性文档（narrative 为主，用来看 structural_clarity 低分场景）: 2 份
- 扫描件: 1 份

**总计**: 8 份 + 1 份失败样本 = **9 份**

### 1.2 目录结构

```
docs/references/working/load-test-2026-04-11/
├── README.md                      # 本文件
├── samples/                       # 样本集（不入 git，.gitignore）
│   ├── short/
│   │   ├── short_01_pdf.pdf
│   │   └── short_02_txt.txt
│   ├── medium/
│   │   ├── medium_01_regulation.pdf
│   │   ├── medium_02_contract.docx
│   │   ├── medium_03_spec.md
│   │   └── medium_04_narrative.pdf
│   ├── long/
│   │   ├── long_01_policy.pdf
│   │   └── long_02_handbook.docx
│   └── expected_failure/
│       └── scanned_01.pdf         # OCR 不支持，用来验证失败路径
├── samples_manifest.yaml           # 样本元数据 + 期望行为
├── run_records/                   # 每次跑批的 JSON 记录
│   └── <timestamp>_<sample_id>.json
├── report/                        # 最终报告
│   └── load_test_report_<date>.md
└── run_load_test.py               # 跑批脚本入口（见 §5）
```

### 1.3 samples_manifest.yaml 格式

```yaml
# samples_manifest.yaml
# 样本集的元数据，供跑批脚本读取

schema_version: "v1"
manifest_version: "2026-04-11"

# 测试用的 schema_ir 文件路径
schema_ir_path: "./test_schema_ir.json"

# 测试用的 AgentScope 配置
scope:
  agent_id: "b3_load_test"
  max_batch_size: 100
  min_confidence: 0.0
  require_source: false
  allowed_entity_types: null   # 允许全部
  allowed_pred_ids: null

# LLM 配置
extraction_config:
  model: "gpt-4o-mini"
  max_retries: 2
  temperature: 0.0
  max_text_chars: 4000
  timeout_seconds: 30.0

samples:
  - sample_id: "short_01_pdf"
    path: "samples/short/short_01_pdf.pdf"
    doc_type: "pdf"
    length_class: "short"
    domain: "regulation"
    expected_result: "success"   # success | empty | staging_error | extraction_error
    expected_min_valid_specs: 1
    notes: "Short PDF with clear if-then clauses"

  - sample_id: "scanned_01"
    path: "samples/expected_failure/scanned_01.pdf"
    doc_type: "pdf"
    length_class: "short"
    domain: "scanned"
    expected_result: "staging_error"
    expected_error_kind: "empty_document"
    notes: "Scanned PDF with no extractable text; should fail staging"
```

### 1.4 样本集不入 git

`samples/` 目录加到 `.gitignore`。理由：
- 可能包含 PII / 版权内容
- 每个开发者自己准备样本
- `samples_manifest.yaml` 入 git 作为结构约定
- 样本选择经验通过 report 沉淀

---

## 2. 观测指标

### 2.1 Per-sample 指标

对每份样本记录：

**Staging 层**:
- `stage_success`: bool
- `stage_error_kind`: str | null
- `total_segments`: int
- `high_clarity_count`: int
- `avg_structural_clarity`: float
- `parser_name`, `parser_version`: str

**Extraction 层**（来自 `BatchExtractionResult.metrics`）:
- `total_segments`: int
- `success_segment_count`: int
- `error_segment_count`: int
- `total_proposal_count`: int
- `total_valid_count`: int
- `total_rejection_count`: int
- `batch_duration_ms`: int
- `batch_cap_reached`: bool
- **Per-segment error breakdown**: `{error_kind: count}`
- **Rejection breakdown**: `{reason: count}`（schema_* / scope_* / spec_construction）

**Resolution 层**（来自 `ResolutionStats`）:
- `input_spec_count`: int
- `output_spec_count`: int
- `merge_count`: int
- `unique_entity_count`: int
- `unique_fact_count`: int
- `resolution_duration_ms`: int

**Bundle / Commit 层**（来自 `BundleCommitResult`）:
- `bundle_created`: bool
- `committed_count`: int
- `failed_count`: int
- `failed_breakdown`: `{error_kind: count}`

**人工审批**（跑完后手工补充）:
- `reviewed_count`: int
- `approved_count`: int
- `rejected_count`: int
- `human_approval_rate`: float
- `review_notes`: str

**总体**:
- `total_duration_ms`: int
- `expected_result_matches`: bool
- `deviation_notes`: str

### 2.2 聚合指标（跨样本）

- **Stage success rate**: staged / total samples
- **Extraction success rate**: segments with ExtractionResult / total segments
- **LLM error distribution**: { llm_unavailable, llm_timeout, retry_exhausted, config_invalid, dependency_missing }
- **Rejection cause distribution**: { schema_*, scope_*, spec_construction }
- **Merge efficiency**: avg(merge_count / input_spec_count)
- **Human approval rate**: approved / reviewed (across all samples)
- **Avg structural_clarity**: 对 high_clarity_count 的分布

---

## 3. 失败分类

每个观察到的问题分入以下类别之一：

| 类别 | 描述 | 示例 |
|------|------|------|
| **schema** | 规则本身的 schema 表达能力不足 | 文档中的 fact 无法映射到任何 pred_id |
| **scope** | Scope 配置把合理 fact 挡在门外 | min_confidence 过高，大量 proposal 被拒 |
| **LLM** | LLM 本身的行为（幻觉、遗漏、格式错误）| 生成了 schema 外的 entity_type；超时 |
| **resolution** | 去重/合并策略的边界问题 | 不同大小写的 identity 被视为不同 entity |
| **bundle/commit** | 下游提交路径的问题 | confirmed draft → write 时 e_ref 编码失败 |
| **staging** | 文档解析层问题 | 中文 PDF 字符切分异常 |
| **observability** | Tracing / metrics 不足以诊断 | Langfuse trace 字段缺失关键信息 |
| **other** | 不在以上分类 | — |

### 3.1 问题记录结构

每个问题按以下结构记录到 report：

```
### P-<nn>: <short title>
- **Category**: schema / scope / LLM / resolution / bundle-commit / staging / observability / other
- **Severity**: P0 / P1 / P2 / P3
- **Sample(s)**: [sample_id, ...]
- **Description**: 具体现象
- **Evidence**:
  - run_record: <path>
  - langfuse_trace_id: <id if any>
- **Hypothesis**: 根因猜测
- **Proposed fix**: 修复方向（不是最终方案）
- **Requires blueprint**: Yes / No（小 fix 可直接改）
```

---

## 4. 跑批记录格式

见 [run_record_template.json](./run_record_template.json)（本目录内）。

每次跑单个样本产出一个 JSON 文件，文件名 `<timestamp>_<sample_id>.json`，存到 `run_records/`。

---

## 5. 跑批脚本入口

见 [run_load_test.py](./run_load_test.py)（本目录内）。

### 5.1 使用

```bash
# 跑单个样本
python run_load_test.py --manifest samples_manifest.yaml --sample short_01_pdf

# 跑全部样本
python run_load_test.py --manifest samples_manifest.yaml --all

# dry-run（不 commit 到 ledger）
python run_load_test.py --manifest samples_manifest.yaml --all --dry-run
```

### 5.2 前置要求

- `pymupdf` + `pymupdf4llm` + `python-docx` + `instructor` + `litellm` 全部安装
- `OPENAI_API_KEY` 或其他 provider key 配置在环境变量
- 可选：`LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` 接入观测
- 测试用的 `schema_ir` 和 `AgentSession` bootstrap

---

## 6. 执行步骤

1. **准备样本集**：按 §1.1 收集 9 份文档，放入 `samples/` 对应子目录
2. **填写 samples_manifest.yaml**：根据 §1.3 格式，逐条填 metadata 和 expected_result
3. **准备 schema_ir**：写一份足够覆盖样本内容的 schema，放到 manifest 指定路径
4. **配置环境变量**：`OPENAI_API_KEY`，可选 Langfuse keys
5. **首次 dry-run**：`python run_load_test.py --manifest ... --all --dry-run`
   - 验证脚本可以跑完所有样本
   - 不实际 commit，快速发现脚本 bug
6. **正式跑批**：去掉 `--dry-run`
7. **人工审批**：对每个 bundle 走 review/approval 流程，记录 approved/rejected 分布
8. **写 report**：按 [report_template.md](./report_template.md) 整理观察
9. **问题分类**：每个发现的问题按 §3 归类，决定是否需要开修复蓝图

---

## 7. 产出物

完成时应有以下产出：

1. `samples_manifest.yaml` + 9 份样本文件（本地，不入 git）
2. `run_records/*.json`（9 个 JSON 跑批记录，入 git）
3. `report/load_test_report_<date>.md`（1 份报告，入 git）
4. 问题清单（可能触发的修复蓝图 list，写在 report 里）

---

## 8. 退出条件

B3 完成的标准：

- [ ] 9 份样本全部跑完（含 1 份预期失败）
- [ ] 每份样本都有 run_record JSON
- [ ] report 已写，含 §3 分类的问题列表
- [ ] 每个 P0/P1 问题都有明确的后续动作（修复蓝图或直接改）
- [ ] 至少 1 份样本走完了完整的 stage → extract → batch → resolve → bundle → commit 链路并成功 commit

**非退出条件**（不强制）：
- 不要求所有样本 committed_count > 0
- 不要求 LLM error_count == 0
- 不要求 merge_count > 0
