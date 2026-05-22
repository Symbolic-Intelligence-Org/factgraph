# Blueprint: Mistral Native Structured Output Client

- Status: implemented with deviations
- Created: 2026-04-13
- Kind: **extraction client layer fix** (provider routing + dependency)
- Trigger: Cross-provider benchmark 确认 Mistral 4/10 failure 根因是 instructor TOOLS mode 触发 parallel tool calling;litellm issue #16148 关闭为 "not planned"
- Related Modules:
  - `src/factpy_kernel/agent/extraction/llm.py` (client 构造)
  - `src/factpy_kernel/agent/extraction/extractor.py` (model 参数透传)
  - `pyproject.toml` (extraction extras 加 `mistralai`)
- Audit Log:
  - [2026-04-13_mistral-native-client.audit.md](./2026-04-13_mistral-native-client.audit.md)

---

## 0. Scope

当 `model` 以 `mistral/` 开头时,绕过 litellm,改用 **Mistral 官方 SDK** + `MISTRAL_STRUCTURED_OUTPUTS` mode 构造 instructor client。消除 parallel tool calling 根因。

**做什么**:
- `llm.py`: `build_default_llm_client(model)` 加 Mistral 分支 — 用 `instructor.from_mistral()` + `mode=Mode.MISTRAL_STRUCTURED_OUTPUTS`
- `extractor.py`: 调用 `build_default_llm_client(model)` 取回 `(client, normalized_model)`;`create()` 始终显式传 `model=normalized_model`
- `pyproject.toml`: `extraction` extras 加 `mistralai>=1,<2`
- 测试: provider routing + model name normalization + mistralai 缺失时 graceful fallback

**不做什么**:
- 不改 prompts / validation / resolution / batch / models
- 不改 OpenAI 路径(仍走 `instructor.from_litellm`)
- 不做 Fix B (`parallel_tool_calls=False` — 太依赖 litellm 版本)
- 不做 Fix C (`Mode.JSON` fallback — schema 约束弱,不是最终方案)

---

## 1. Root Cause

```
用户调用: extract_document(model="mistral/mistral-small-latest", ...)
    → ExtractionAgent.extract_from_segment(...)
        → build_default_llm_client()  # 当前: 无参数,总是 instructor.from_litellm
        → client.create(model="mistral/mistral-small-latest", response_model=..., ...)
            → litellm → Mistral API (TOOLS mode = function calling)
            → Mistral 返回 parallel tool_calls (多个 tool_call in one response)
            → instructor: "does not support multiple tool calls" → retry
            → retry: conversation history 损坏 → Mistral 400: "Not the same number of function calls and responses"
            → 所有 retry 耗尽 → 0 proposals
```

**Fix**: Mistral 路径改用 `instructor.from_mistral(Mistral(), mode=MISTRAL_STRUCTURED_OUTPUTS)` — 用 Mistral SDK 的原生 JSON schema 约束解码,完全绕过 tool calling。

---

## 2. Implementation Constraints (你指出的 3 个坑)

### 坑 1: `from_provider()` 不透传 mode

当前 `instructor 1.15.1` 的 `from_provider()` Mistral 分支没有把 `mode` 透传给 `from_mistral()`。所以不能用 `from_provider(model, mode=Mode.JSON_SCHEMA)`。

**修复**: 直接调 `instructor.from_mistral(client, mode=Mode.MISTRAL_STRUCTURED_OUTPUTS)`,不走 `from_provider`。

### 坑 2: extractor 传 `model="mistral/..."` 会覆盖 SDK 的裸 model name

当前 `extractor.py` line 124 传 `model=effective_config.model` 给 `client.create()`。如果 client 是 Mistral SDK,但 model 名是 `"mistral/mistral-small-latest"`(litellm 格式),会破坏 Mistral SDK 的模型路由。

**修复**: Mistral 路径需要把 `"mistral/mistral-small-latest"` → `"mistral-small-latest"` (strip prefix)。在 `build_default_llm_client` 返回时附带裸 model name,或在 `extractor.py` 做条件 strip。

### 坑 3: `mistralai` 不在当前 extraction extras

`pyproject.toml` line 16 的 `extraction` extras 只有 `instructor` + `litellm`。需要加 `mistralai>=1,<2`。

---

## 3. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| MC-01 | 用 `instructor.from_mistral()` + `Mode.MISTRAL_STRUCTURED_OUTPUTS`,不用 `from_provider()` | 坑 1: from_provider 不透传 mode |
| MC-02 | `build_default_llm_client(model: str)` 返回 `(client, normalized_model)` tuple。**Caller 始终显式传 `model=normalized_model` 给 `create()`**,不依赖 client 默认 model | 坑 2: Mistral 路径需要裸 model name;显式传优于隐式默认(统一两条路径的调用约定) |
| MC-03 | OpenAI 路径不变(仍走 `instructor.from_litellm`) | 不影响现有 10/10 success rate |
| MC-04 | Mistral model name normalization: strip `"mistral/"` prefix | `"mistral/mistral-small-latest"` → `"mistral-small-latest"` |
| MC-05 | `MISTRAL_API_KEY` 缺失时: Mistral 分支 **不走**(不创建空 key 的 SDK client),直接 fallback 到 litellm。`mistralai` 包缺失时: 同样 fallback 到 litellm | 空 key 走 SDK 会在运行时 401;fail fast 不如 graceful fallback 有用 |
| MC-06 | `pyproject.toml` extraction extras 加 `mistralai>=1,<2` | Pin 到 1.x;2.0.0 有 breaking change(instructor issue #2137) |

---

## 4. Implementation Sketch

### 4.1 `llm.py`

```python
def build_default_llm_client(model: str = "") -> tuple[Any, str]:
    """Build Instructor client + normalized model name.
    
    Returns (client, model_name) where model_name is the provider-native
    model identifier (e.g. "mistral-small-latest" not "mistral/mistral-small-latest").
    """
    instructor = import_module("instructor")
    
    if model.startswith("mistral/"):
        bare_model = model[len("mistral/"):]
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            # No key → fall back to litellm (may hit parallel tool call bug on complex docs)
            litellm = import_module("litellm")
            return instructor.from_litellm(litellm.completion), model
        try:
            mistralai = import_module("mistralai")
            from instructor import Mode
            mistral_client = mistralai.Mistral(api_key=api_key)
            client = instructor.from_mistral(
                mistral_client,
                mode=Mode.MISTRAL_STRUCTURED_OUTPUTS,
            )
            return client, bare_model
        except ImportError:
            # mistralai not installed → fall back to litellm
            litellm = import_module("litellm")
            return instructor.from_litellm(litellm.completion), model
    
    litellm = import_module("litellm")
    return instructor.from_litellm(litellm.completion), model
```

### 4.2 `extractor.py`

调用处改为:

```python
if self._llm_client is None:
    try:
        llm_client, effective_model_name = build_default_llm_client(effective_config.model)
    except ImportError as exc:
        return self._return_result(segment, ExtractionError(...))
else:
    llm_client = self._llm_client
    effective_model_name = effective_config.model

# ...

response = llm_client.chat.completions.create(
    model=effective_model_name,  # ← 裸 model name,不是 litellm prefix
    response_model=response_model,
    ...
)
```

### 4.3 `pyproject.toml`

```toml
extraction = ["instructor>=1.6", "litellm>=1.50", "mistralai>=1,<2"]
```

### 4.4 测试

- `test_build_default_llm_client_mistral_returns_native_client` — mock mistralai, 验证返回 Mistral client
- `test_build_default_llm_client_mistral_strips_prefix` — 验证 model name normalization ("mistral/mistral-small-latest" → "mistral-small-latest")
- `test_build_default_llm_client_mistral_fallback_when_sdk_missing` — mock ImportError, 验证 fallback to litellm + 返回原始 model name
- `test_build_default_llm_client_mistral_fallback_when_key_missing` — unset MISTRAL_API_KEY, 验证 fallback to litellm
- `test_build_default_llm_client_openai_unchanged` — 验证 OpenAI 路径不受影响
- `test_extractor_passes_normalized_model_to_create` — patch `build_default_llm_client` 返回 `(fake_client, "mistral-small-latest")`, 断言 `fake_client.create()` 收到 `model="mistral-small-latest"` (不是 `"mistral/mistral-small-latest"`)

---

## 5. Acceptance Criteria

1. Mistral Small 在 Re-DocRED 10 docs 上 success rate 从 6/10 显著提升(目标 ≥ 8/10)
2. GPT-4.1 行为完全不变(10/10 success)
3. `mistralai` 缺失时不 crash,fallback 到 litellm
4. Regression: 1014+ tests green

---

## 6. Outcome / Deviations

### Result
- **Regression**: 1015 passed, 3 skipped
- **Mistral Small Re-DocRED**: 10/10 success (was 6/10), F1=78% (was 64%)
- **GPT-4.1 unchanged**: 10/10 success, F1=68%
- **Mistral Small 现在是 F1 最高的模型** (78% vs GPT-4.1 的 68%),且完全免费

### Deviations (2 个实施中发现的必要偏差)

1. **`timeout` kwarg 过滤**: Mistral native SDK 的 `Chat.complete()` 不接受 `timeout` 参数。extractor.py 在 native Mistral 路径不传 `timeout`。这不在原始蓝图 scope 里,是实施中发现的 Mistral SDK 接口限制。
2. **`confidence` JSON schema float bounds 移除**: `build_response_model` 里 `confidence` 字段的 `ge=0.0, le=1.0` 生成 `"maximum": 1.0` (float),Mistral structured output 解析器不接受。移除了 schema 层约束,保留运行时校验(`_normalize_confidence`)。

### Final status: **implemented with deviations**
