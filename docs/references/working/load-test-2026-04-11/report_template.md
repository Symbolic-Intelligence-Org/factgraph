# B3 真实文档负载测试报告

- Date: `<YYYY-MM-DD>`
- Author: `<your name>`
- Related: [README.md](./README.md)
- Run records: [run_records/](./run_records/)

---

## 0. TL;DR

*一句话结论：agent 在真实文档上跑批的可用性如何，下一步修什么。*

示例：
> 8/9 样本成功走完 stage → extract → resolve → commit 链路；主要问题集中在 schema 覆盖面不足（P1×2）和 LLM 对 narrative 类文档的幻觉（P2×3）。scanned PDF 按预期失败。建议下一步开两个修复蓝图：schema 扩展 + extraction prompt 调优。

---

## 1. 跑批概览

| # | Sample | Length | Format | Domain | Staging | Extract | Resolve | Commit | Review | Outcome |
|---|--------|--------|--------|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | short_01_pdf | short | PDF | regulation | ✓ | ✓ (valid=18/23) | ✓ (merged=3) | ✓ (14/15) | 12/15 approved | match |
| 2 | short_02_txt | short | TXT | regulation | ✓ | ... | ... | ... | ... | ... |
| 3 | medium_01_regulation | medium | PDF | regulation | ✓ | ... | ... | ... | ... | ... |
| 4 | medium_02_contract | medium | DOCX | contract | ✓ | ... | ... | ... | ... | ... |
| 5 | medium_03_spec | medium | MD | spec | ✓ | ... | ... | ... | ... | ... |
| 6 | medium_04_narrative | medium | PDF | narrative | ✓ | ... | ... | ... | ... | ... |
| 7 | long_01_policy | long | PDF | regulation | ✓ | ... | ... | ... | ... | ... |
| 8 | long_02_handbook | long | DOCX | spec | ✓ | ... | ... | ... | ... | ... |
| 9 | scanned_01 | short | PDF | scanned | ✗ empty_document | — | — | — | — | match (expected fail) |

---

## 2. 聚合指标

### 2.1 Staging

- Total samples: 9
- Staging success: 8/9 (88.9%)
- Expected failures matched: 1/1
- Unexpected staging failures: 0

**Pattern type distribution**（跨所有成功 staged 样本）:
- if_then: N
- entity_relation: N
- definition: N
- narrative: N

### 2.2 Extraction

- Total segments processed: N
- Segment success rate: N%
- Total LLM proposals: N
- Valid specs: N
- Rejected proposals: N (N%)
- batch_cap_reached events: 0

**Per-segment error distribution**:
| kind | count |
|------|------:|
| llm_unavailable | 0 |
| llm_timeout | 0 |
| instructor_retry_exhausted | 0 |
| config_invalid | 0 |
| dependency_missing | 0 |
| unexpected | 0 |
| batch_cap_reached | 0 |

**Rejection distribution**:
| reason | count | share |
|--------|------:|------:|
| schema_entity_type_unknown | N | N% |
| schema_pred_id_unknown | N | N% |
| schema_field_type_mismatch | N | N% |
| scope_entity_type_denied | N | N% |
| scope_pred_id_denied | N | N% |
| scope_min_confidence | N | N% |
| scope_max_batch_size | N | N% |
| spec_construction_failure | N | N% |

### 2.3 Resolution

- Total input specs: N
- Total output specs: N
- Total merge events: N
- Avg merge rate: (merge_count / input_spec_count) = N%
- Unique entity count (aggregate): N
- Unique fact count (aggregate): N

### 2.4 Commit

- Total drafts attempted: N
- Committed: N
- Write failures: N
- Write failure breakdown: { shape: N, runtime: N }

### 2.5 Human review

- Total bundles reviewed: N
- Drafts approved: N
- Drafts rejected: N
- Overall human approval rate: N%

### 2.6 Latency

- Avg batch_duration_ms per sample: N
- Avg resolution_duration_ms per sample: N
- Avg total run_duration_ms per sample: N
- Max sample duration: N ms (sample_id)

### 2.7 Langfuse 观测覆盖

- Samples with Langfuse traces: N/9
- Single-segment traces emitted: N
- Batch traces emitted: N
- Resolution traces emitted: N
- Missing trace fields encountered: <list>

---

## 3. 观察到的问题

每个问题按 README.md §3 的分类记录。

### P-01: `<short title>`

- **Category**: schema | scope | LLM | resolution | bundle-commit | staging | observability | other
- **Severity**: P0 | P1 | P2 | P3
- **Sample(s)**: [sample_id, ...]
- **Description**: 具体现象，包括在哪个 segment / proposal 上出现
- **Evidence**:
  - run_record: `run_records/<filename>.json`
  - langfuse_trace_id: `<id if any>`
- **Hypothesis**: 根因猜测
- **Proposed fix**: 修复方向（不是最终方案）
- **Requires blueprint**: Yes / No

### P-02: `<short title>`

（继续...）

---

## 4. Deviations from expectations

对所有 `outcome.matches_expectation == false` 的样本，记录偏差：

### D-01: `<sample_id>` — `<expected>` vs `<actual>`

- **Expected**: success (min 5 valid specs)
- **Actual**: success (2 valid specs)
- **Root cause snippet**: 大部分 proposal 被 rejection_reason=schema_pred_id_unknown 拒绝
- **Severity**: P2
- **Cross-reference**: P-01, P-04

---

## 5. 按类别的问题汇总

```
schema:         N problems (P1×1, P2×2)
scope:          N problems
LLM:            N problems (P2×3)
resolution:     N problems
bundle/commit:  N problems
staging:        N problems
observability:  N problems
other:          N problems
```

---

## 6. 建议的后续动作

### 6.1 需要开修复蓝图的

- [ ] **<Blueprint title>** — 对应 P-01, P-04（schema 扩展）
- [ ] **<Blueprint title>** — 对应 P-02（extraction prompt 调优）

### 6.2 可以直接改的小 fix

- [ ] `<file>:<line>` — 对应 P-07
- [ ] `<file>:<line>` — 对应 P-08

### 6.3 暂不处理（记录即可）

- **P-09**: 已知 4C3-b 约束（非 bug）
- **P-10**: 预期行为，文档说明即可

### 6.4 观测改进

- Langfuse trace 是否缺少某些关键字段？
- 需要新增的 attribute？

---

## 7. 退出条件核对

参照 [README.md](./README.md) §8:

- [ ] 9 份样本全部跑完
- [ ] 每份样本都有 run_record JSON
- [ ] 本报告已完成 §1-§6
- [ ] 每个 P0/P1 问题都有明确后续动作
- [ ] 至少 1 份样本成功走完完整链路并 commit

---

## 8. 附录

### 8.1 环境信息

- Python version: `<version>`
- Agent package version / commit: `<hash>`
- LLM provider + model: `<e.g. OpenAI gpt-4o-mini>`
- Langfuse version: `<version or "not installed">`
- Running host: `<laptop / CI / ...>`

### 8.2 非确定性说明

即使 `temperature=0.0`，LLM 输出仍可能不同（provider 内部状态 / model version 更新）。本报告基于 `<date>` 当日的跑批，未来重跑可能出现不同 proposal。
