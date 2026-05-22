# Audit Log: Kernel Extraction Response Model OpenAI-strict fix

## 2026-04-11 — Initial scoped bugfix

### Trigger

B3 real-LLM smoke test on `medium_01_security` (22 segments) hit deterministic `instructor_retry_exhausted` on every segment. Error message from captured LLM exception:

```
litellm.BadRequestError: OpenAIException -
Invalid schema for function 'SegmentExtractionResponse':
In context=('properties', 'field_values', 'items'), array schema missing items.
```

### Root cause

`src/factpy_kernel/agent/extraction/llm.py` declares **two** fields that serialize to permissive JSON schemas incompatible with OpenAI strict function-calling mode:

**Problem A — `list[tuple[str, Any]]` (field_values)**:
Pydantic serializes this using `prefixItems` (JSON Schema 2020-12), which OpenAI strict rejects. The inner `Any` → `{}` also violates "every schema must have explicit type". Observed as the first B3 error surface.

**Problem B — `dict[str, Any]` (entity_identity)**:
Pydantic serializes this to `{"type": "object", "additionalProperties": true}`. OpenAI strict requires `additionalProperties: false` on every object schema — `true` means "can contain any unenumerable properties", which is uncapturable in strict mode. This would be the **second failure surface** after Problem A is fixed, because OpenAI returns the first structural error it hits and `field_values` comes before `entity_identity` in traversal order.

Both problems share the same root class: **raw permissive schemas are incompatible with OpenAI strict mode**.

### Why the bug was latent (both problems)

`test_agent_l4c3a_extractor.py:54` mocks `build_default_llm_client` with `_FakeClient(lambda kwargs: kwargs)` that echoes Pydantic-validated kwargs back. The real OpenAI JSON-schema validation path was never exercised by any existing test.

Additionally: inspecting `model.model_json_schema()` (raw Pydantic output) is **not sufficient** to catch Problem B. Raw Pydantic inspection is not the API-boundary artifact — OpenAI's strict mode applies its own transformation (`openai.pydantic_function_tool`) that reshapes the schema before the request is sent. The CI guard test must therefore validate the **strict-transformed schema**, which is what would actually be rejected by the API. This is what BF-04's revision captures.

### Frozen decisions

| # | Decision | Rationale |
|---|----------|-----------|
| BF-01 | **Reframed**: Replace all permissive object schemas (`tuple[str, Any]`, `dict[str, Any]`, raw `Any`) with typed Pydantic sub-models | Root cause is "raw permissive object schemas incompatible with OpenAI strict", not just the tuple variant. Fixing only one guarantees surfacing the next problem on rerun |
| BF-02 | All new sub-models (`_LLMFieldValue`, `_LLMIdentityEntry`) are private and not exported | Keeps 4C3-a external contract unchanged |
| BF-03 | Extend `_normalize_field_values` with dict-form and attr-based handlers | Single chokepoint already exists; purely additive backward-compatible extension |
| BF-04 | **Revised**: Guard test inspects `openai.pydantic_function_tool(model_cls)["function"]["parameters"]` — the actual strict-mode schema sent to the API — not raw Pydantic output | Raw Pydantic output misses `additionalProperties: true` leaks; the guard must validate the real API-boundary artifact |
| BF-05 | All `value` fields in sub-models constrained to `str \| int \| float \| bool \| None` | OpenAI strict rejects `Any`; these 4 primitives cover all existing type_domain values at the LLM boundary |
| BF-06 | Do not rename `LLMFactProposal` or `SegmentExtractionResponse` | Minimal diff; narrow scope |
| BF-07 | **New**: `entity_identity` in the response model becomes `list[_LLMIdentityEntry]` (entries with `name: str, value: str\|int\|float\|bool\|None`), symmetric with `field_values` | `dict[str, Any]` is not expressible in OpenAI strict mode. A typed list of name/value entries is the minimal compatible shape |
| BF-08 | **New**: Add `_normalize_entity_identity` helper to `validation.py`; called from `validate_proposal` before `_validate_entity_identity` | Mirrors the `_normalize_field_values` pattern. Accepts dict form (back-compat for mocks), list-of-dict form (LLM JSON shape), list-of-attr-object form (Pydantic instance form), rejects anything else |
| BF-09 | **New**: Guard test asserts every object in the strict schema has `additionalProperties: false` | Canonical way to detect Problem B and any future leak of the same class. Single assertion catches the entire family of bugs |

### Explicit non-goals

- Not changing `FactDraftSpec.field_values` or `FactDraftSpec.entity_identity` external types
- Not changing `validate_proposal` signature
- Not changing Instructor / LiteLLM pins
- Not adding "strict vs loose mode" runtime toggle
- Not covering Anthropic / Gemini quirks (separate B3 will surface those)
- Not reviewing other Layer-4 response models (none currently have permissive-schema problems on LLM response paths — verified by grep for `dict[str, Any]` and `tuple[str, Any]` in the extraction package)
- Not supporting LLM-emitted duplicate identity names (_normalize_entity_identity rejects them)

### Audit trail of related decisions

- Original design: Layer 4C3-a blueprint §3.2 (archived 2026-04-10) showed `list[tuple[str, Any]]` for `field_values` and `dict[str, Any]` for `entity_identity` as the response model shape. Both were implemented faithfully. The bug is in the **design decision**, not the implementation.
- The L4C3a blueprint's audit decision L4C3a-16 froze "Response model 动态构造 Literal[entity_type/pred_id]" but did not constrain the types of `field_values` or `entity_identity`. That dual gap is what this bugfix closes.
- No existing Layer-4 blueprint promised to test the real OpenAI JSON-schema path. L4C3a's test strategy (§9 of the archived blueprint) explicitly relied on mock LLM clients for unit tests.
- The scope of this bugfix was initially drafted narrower (field_values only) but was expanded during review on 2026-04-11 after the reviewer pointed out the symmetric Problem B in `entity_identity`. The scope expansion did not add new files or change the overall shape of the fix — it extended the same pattern to a second field.

### Impact on other layers

| Layer | Impact | Reason |
|-------|--------|--------|
| 4C1 (staging) | None | No change to document staging |
| 4C2 (bundle) | None | No change to FactDraftSpec / DraftBundle |
| 4C3-a (single extract) | Fixed | This is the layer with the bug |
| 4C3-b (batch extract) | Fixed transitively | Calls 4C3-a |
| 4C3-c (entity resolution) | None | Operates on FactDraftSpec |
| Langfuse observability | None | Metrics unchanged |
| Kernel runtime | None | Zero kernel-side change |

### Regression expectation

- Prior baseline: 942 tests (1 skipped)
- New tests: 17 total
  - `OpenAIStrictSchemaGuardTest`: 5 tests (conditionally skipped if `openai` not installed)
  - `NormalizeFieldValuesAcceptsObjectFormTest`: 5 tests (unconditional)
  - `NormalizeEntityIdentityTest`: 7 tests (unconditional)
- Post-fix expectation: 959 total tests
  - 1 baseline skip (pymupdf4llm)
  - 0-5 env-dependent skips (OpenAI guard class skipped if `openai` not installed)
- Mock-based 4C3-a tests must continue passing unchanged (BF-03 and BF-08 are additive)

### B3 re-run expectation

After the fix:
- `instructor_retry_exhausted` should **no longer** be the bulk error mode on any segment
- No more `BadRequestError: Invalid schema` messages in the error samples — strict-mode validation should pass cleanly
- Remaining failures on `medium_01_security` (if any) will be **different** error classes: schema rejections, scope rejections, LLM hallucinations that fail `validate_proposal`, etc. Those become the next diagnostic signal
- Either: runner produces `valid_count > 0` (real extraction succeeds), or a new, informative failure class surfaces
- Both outcomes are valid B3 progress; the current deterministic block is the specific problem this bugfix resolves

### Why not a bigger blueprint

Per user direction: "这是个真实的生产阻断 bug，不是 B3 本身的问题... `方案 A` 最稳, 内部改动小, 外部合同不变". Scope is narrow enough that a full draft → scoped → implementing → implemented → archived cycle with interactive review would be over-engineering. This single scoped bugfix page is the minimum viable audit trail.
