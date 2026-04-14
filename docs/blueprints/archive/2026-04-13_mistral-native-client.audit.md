# Audit Log: Mistral Native Structured Output Client

## 2026-04-13 — draft

### Trigger

Cross-provider benchmark + 三轮子代理调研确认根因:
1. instructor TOOLS mode 触发 Mistral parallel tool calling → retry loop → 400 → 0 proposals
2. litellm 不支持 Mistral JSON_SCHEMA mode (issue #16148, closed as not planned)
3. validator tag fallback 已证明不是 success rate 根因(另一个蓝图已归档)

### Key evidence
- instructor GitHub issue #724: Mistral parallel tool calls not supported
- litellm GitHub issue #16148: json_schema response_format not supported for Mistral
- 当前 instructor 1.15.1 的 from_provider() 不透传 mode(本地代码验证)
- Mistral SDK 的 structured outputs mode 绕过 tool calling(Mistral 官方文档确认)

### Implementation constraints (reviewer identified)
1. from_provider() 不透传 mode → 直接用 from_mistral()
2. extractor 传 litellm 格式 model name 会覆盖 SDK → 需要 strip prefix
3. mistralai 不在 extraction extras → 需要加依赖

### Status transitions

- 2026-04-13 — **draft v1** (6 MC decisions)
- 2026-04-13 — **scope check v1**: 2× P1 + 1× P2 + 1× OQ:
  1. P1: `mistralai>=1.0` 不能避免 2.x → 改为 `>=1,<2`
  2. P1: 测试面缺 extractor-level model name 断言 → 补 `test_extractor_passes_normalized_model_to_create`
  3. P2: scope 和 sketch 对 `model=` 传递策略矛盾 → 冻结为"始终显式传 `model=normalized_model`"
  4. OQ: 空 MISTRAL_API_KEY 路径 → 改为 key 缺失时直接 fallback,不创建空 key SDK client
- 2026-04-13 — **draft v2** (6 MC decisions updated, all 4 findings addressed)
- 2026-04-13 — **scope check v2**: 1× P2 (依赖约束 2 处旧值 `>=1.0` 未更新到 `>=1,<2`) → 统一修正
- 2026-04-13 — **scoped** (6 MC decisions frozen, all constraints consistent)
- 2026-04-13 — **implementing**: 3 层 bug 逐层修复:
  1. `instructor.from_mistral()` + `MISTRAL_STRUCTURED_OUTPUTS` — 绕过 parallel tool calling
  2. native 路径不传 `timeout` — Mistral SDK 不接受此 kwarg
  3. `confidence` Field 去掉 `ge/le` — JSON schema float bounds 不被 Mistral 解析器接受
- 2026-04-13 — **implemented with deviations** (10/10 success, F1=78%, 2 个实施偏差记录在 §6)
