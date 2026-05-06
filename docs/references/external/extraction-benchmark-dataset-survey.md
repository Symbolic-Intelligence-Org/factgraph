# Extraction Benchmark Dataset Survey

> 调研日期: 2026-04-13
> 目的: 为 factpy_kernel extraction pipeline 选择公开 benchmark 数据集
> 评估维度: 文档级关系提取、entity resolution、license、和我们 pipeline 的对齐度

---

## 主结论

主 benchmark 用 **Re-DocRED**；端到端 KB population 用 **KnowledgeNet**；科学全文 IE / coreference 用 **SciREX**；多语言补充用 **RED^FM**；新近全文科学文献补充用 **SciER**；**MINE** 仅作探索性补充。

**关键限制**: 所有 Tier 1 数据集都是纯文本 + JSON 标注,没有 PDF/DOCX 原始文件。可以测 extraction (Stage 2) + resolution (Stage 3),但不能直接测 document staging (Stage 1)。

---

## Tier 1 — 主选

### Re-DocRED (EMNLP 2022)

- **来源**: Tsinghua NLP, 修正 DocRED 的 false negative 问题
- **规模**: 4,053 docs, 132K entities, 56K+ relations, 96 Wikidata relation types
- **Entity types**: PER, ORG, LOC, NUM, TIME, MISC
- **Format**: JSON (Wikipedia articles, sentence-split)
- **License**: MIT
- **下载**: `github.com/tonytan48/Re-DocRED`
- **和我们 pipeline 的对齐**: 文档级 RE, 40.7% 跨句关系, multi-mention entities
- **注意**: 应优先于原始 DocRED, 因为修正了大量标注缺失

### KnowledgeNet (EMNLP-IJCNLP 2019)

- **来源**: Diffbot
- **规模**: 13,000+ exhaustive facts, Wikidata entity links
- **Format**: JSON, character-offset spans
- **License**: MIT
- **下载**: `github.com/diffbot/knowledge-net`
- **和我们 pipeline 的对齐**: (subject; property; object) 三元组格式和我们的 extraction 输出直接对齐

### SciREX (ACL 2020)

- **来源**: Allen AI
- **规模**: 438 full-text 论文, 24K entities, 12K relations, coreference clusters
- **Format**: JSONL
- **License**: Apache 2.0
- **下载**: `github.com/allenai/SciREX`
- **和我们 pipeline 的对齐**: 全文提取 + coreference 标注, 直接测 entity resolution

---

## Tier 2 — 补充

### RED^FM (ACL 2023)

- **规模**: 30,892 human-revised instances, 32 relation types, 7 languages
- **License**: CC BY-SA 4.0
- **价值**: 多语言 relation extraction; Polat 2025 用它做 KE benchmark

### SciER (EMNLP 2024)

- **规模**: 106 full-text papers, 24K entities, 12K relations
- **License**: GPL-3.0 (注意: copyleft, 对集成有约束)
- **价值**: 全文科学文献, 现代 JSONL 格式

### MINE Benchmark (KGGen, NeurIPS 2025)

- **规模**: 100 Wikipedia articles, 15 facts/article
- **价值**: 第一个标准化 text-to-KG benchmark, LLM-as-judge scoring
- **地位**: 前沿补充, 尚未形成社区级标准

---

## 行业 benchmark 方法

| 系统 | 评估方法 | 数据集 |
|---|---|---|
| Microsoft GraphRAG | QA-based (LLM-as-judge: comprehensiveness, diversity) | Behind the Tech podcast, AP News, HotpotQA |
| LlamaIndex | 间接 QA (RAGAS answer_relevancy) | 无专用 extraction benchmark |
| KGGen (NeurIPS 2025) | MINE benchmark (信息保留度) | 100 Wikipedia articles |
| Polat 2025 | F1 on triples (RED^FM English test split) | 446 instances |

---

## 评估说明

本调研的数据集来源和学术背景可信(ACL/EMNLP/NeurIPS)。Tier 排序是面向 factpy_kernel pipeline 设计目标的工程视角排序,不是社区共识。当 pipeline 重视跨句推理/coreference/entity linking/全文结构/license 约束时,排序会变化。

---

## 已下载数据

- `tools/datasets/re_docred/dev_revised.json` — Re-DocRED dev set (500 docs)
- `tools/datasets/re_docred/dev_sample_10.json` — 10 样本子集(8-26 entities 梯度分布)
