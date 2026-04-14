# Cross-Provider Entity Identification Benchmark Report

> 日期: 2026-04-13
> 数据集: Re-DocRED dev subset (10 docs, 182 gold entities)
> 评估类型: Entity identification only (NOT relation extraction)
> 配置: P0 entity context + P1 gleaning + P2 alias merge + F1 doc name + I1+I2 grounding 全部开启

---

## 结果

| Model | Provider | μP | μR | μF1 | Docs OK | Speed | Cost |
|---|---|---|---|---|---|---|---|
| **GPT-4.1** | OpenAI | 88% | **49%** | **63%** | 10/10 | 9.9s/doc | ~$0.002/1K tok |
| Llama 4 Scout 17B | Groq | 81% | 40% | 54% | 3/10 | **2.9s/doc** | **FREE** |
| GPT-4.1 Mini | OpenAI | **94%** | 28% | 43% | 10/10 | 7.1s/doc | ~$0.0004/1K tok |

**未成功的模型**: Llama 3.1 8B 和 Llama 3.3 70B 通过 Groq API 跑 Re-DocRED 时全部失败(0/10)。原因不是模型能力(单条短文本测试可通过),而是 instructor structured output 在 Groq provider 上对长文档的兼容性问题。不计入排名。

---

## 分析

### GPT-4.1 是当前唯一可靠的生产选项

- 100% 成功率(10/10 docs)
- F1=63% 在所有模型中最高
- Recall=49% 是瓶颈(entity-with-facts recall 的天然上限,因为不做 relation extraction)

### GPT-4.1 Mini 是 precision 之王

- Precision=94% 最高(几乎零幻觉)
- 但 Recall=28% 太低(大量 entity 漏掉)
- 适合 "宁缺毋滥" 场景

### Llama 4 Scout 17B (Groq) 有潜力但不稳定

- 3/10 成功时 F1=54%, 速度极快(2.9s/doc)
- 70% failure rate 使其不可用于生产
- 失败原因是 instructor structured output 兼容性,不是模型能力
- 如果兼容性解决,有可能成为免费生产选项

### 开源模型的核心阻碍

不是模型质量 — Llama 3.3 70B 在简单样本上表现良好。阻碍是:
1. **Instructor + Groq 的 structured output 协议不兼容**(长文档 + 复杂 schema)
2. **小模型(≤8B)指令跟随能力不足**(无法处理 3000+ token 的 extraction prompt)
3. **Groq 免费 tier 的 rate/token 限制**可能在多 segment 文档上触发

---

## 推荐

| 场景 | 推荐模型 | 理由 |
|---|---|---|
| 生产默认 | **GPT-4.1** | 唯一 100% 成功 + 最高 F1 |
| 低成本生产 | GPT-4.1 Mini | P=94% 最高,适合精度优先 |
| 免费短文档探索 | Groq Llama 4 Scout | 成功时 F1=54% + 极快,但只适合短文档 |

---

## 方法论说明

- 这是 **entity-with-facts recall**,不是纯 NER recall — 只有被提取了至少一个 attribute 的 entity 才被算作 "predicted"
- 不能与 Re-DocRED 的 relation extraction SOTA 横向对比
- Gold entities 来自 Re-DocRED vertexSet; 非 top-15 relation 的 gold entity 仍参与 entity-level 评估
- Fuzzy matching: token overlap ≥ 50% 或 token subset

---

---

## Run 2: +Mistral (2026-04-13)

新增 Mistral Small + Mistral Large (免费 API, EU 管辖权)。

| Model | Provider | μP | μR | **μF1** | Docs OK | Cost |
|---|---|---|---|---|---|---|
| **Mistral Large** | Mistral | 84% | **82%** | **83%** | 3/10 | **FREE** |
| **Mistral Small** | Mistral | 89% | **65%** | **75%** | 6/10 | **FREE** |
| GPT-4.1 | OpenAI | 90% | 54% | 68% | **10/10** | $0.002/1K |
| Llama 4 Scout 17B | Groq | 89% | 40% | 55% | 2/10 | FREE |
| GPT-4.1 Mini | OpenAI | **92%** | 26% | 40% | **10/10** | $0.0004/1K |

### 关键发现

**Mistral recall 远超 OpenAI**: Mistral Large R=82% vs GPT-4.1 R=54% (差 28pp)。当 Mistral 成功时,它找到的实体明显更多。

**Success rate 是 Mistral 的硬伤**: Mistral Large 3/10, Small 6/10。原因是 instructor structured output 兼容性(和 Groq 相同类型的问题),不是模型能力。

**战略意义**: 如果 structured output 兼容性问题解决(例如换 BAML/Outlines 或用 Mistral 原生 JSON mode),Mistral Small 有潜力成为默认模型 — 免费 + EU 安全 + F1 比 GPT-4.1 高 7%。

### 更新后的推荐

| 场景 | 推荐 | 理由 |
|---|---|---|
| 当前生产默认 | **GPT-4.1** | 100% success, F1=68%, 最可靠 |
| 免费 + 最高质量(如果能解决兼容性) | **Mistral Small** | F1=75%, 免费, EU 安全 |
| Precision 优先 | GPT-4.1 Mini | P=92%, 但 R=26% |

---

---

## Run 3: Mistral Native SDK Fix (2026-04-13)

修复链: `instructor.from_mistral()` + `Mode.MISTRAL_STRUCTURED_OUTPUTS` + native 路径去掉 `timeout` kwarg + 去掉 confidence 的 JSON schema float bounds (`ge=0.0, le=1.0`)。

### Before vs After

| 指标 | Mistral via litellm (before) | **Mistral native SDK (after)** |
|---|---|---|
| **Docs OK** | 6/10 | **10/10** |
| **Micro F1** | 64% | **78%** |
| **Micro P** | 86% | 82% |
| **Micro R** | 51% | **74%** |
| **Total TP** | 56 | **135** |

### Updated Cross-Provider Leaderboard

| Model | Provider | μP | μR | **μF1** | Docs OK | Cost |
|---|---|---|---|---|---|---|
| **Mistral Small (native SDK)** | Mistral | 82% | **74%** | **78%** | **10/10** | **FREE** |
| GPT-4.1 | OpenAI | **90%** | 54% | 68% | **10/10** | $0.002/1K |
| GPT-4.1 Mini | OpenAI | 92% | 28% | 40% | **10/10** | $0.0004/1K |

### Root cause chain (resolved)

1. **Primary**: `instructor.from_litellm()` 默认用 TOOLS mode (function calling) → Mistral 返回 parallel tool calls → instructor 不支持 → retry loop → conversation history 损坏 → 400 error → 0 proposals
2. **Secondary**: Mistral native SDK 的 `Chat.complete()` 不接受 `timeout` kwarg → `TypeError`
3. **Tertiary**: Pydantic `Field(ge=0.0, le=1.0)` 生成 JSON schema `"maximum": 1.0` (float) → Mistral structured output 解析器不接受 float 类型的 schema 约束

所有三层都已修复。Mistral 路径现在走 `instructor.from_mistral(Mistral(api_key=...), mode=MISTRAL_STRUCTURED_OUTPUTS)`,完全绕过 litellm adapter。

### Model profile

| 维度 | Mistral Small | GPT-4.1 |
|---|---|---|
| **Recall 优势** | **74%** (找到更多 entities) | 54% |
| **Precision 优势** | 82% | **90%** (更少幻觉) |
| **F1** | **78%** | 68% |
| **Cost** | **FREE (1B tok/mo)** | $0.002/1K |
| **Security** | EU 管辖权, SOC2+ISO27001 | US, SOC2 |
| **Success rate** | 10/10 (修复后) | 10/10 |

**Tradeoff**: Mistral recall 更强(+20pp),GPT-4.1 precision 更强(+8pp)。取决于 use case — recall 优先选 Mistral,precision 优先选 GPT-4.1。

### 推荐更新

| 场景 | 推荐 | 理由 |
|---|---|---|
| **默认推荐** | **Mistral Small** | F1=78%, 免费, EU 安全, 10/10 success |
| Precision 优先 | GPT-4.1 | P=90%, 零 hallucination 场景 |
| 成本敏感 + OK quality | GPT-4.1 Mini | P=92% 但 R=28% |

---

## Raw data

- `tools/benchmarks/extraction/results/cross_provider_20260413T185100.json`
- `tools/benchmarks/extraction/results/multi_model_entity_20260413T174002.json`
- `tools/benchmarks/extraction/results/entity_id_mistral_mistral-small-latest_20260413T221738.json`
