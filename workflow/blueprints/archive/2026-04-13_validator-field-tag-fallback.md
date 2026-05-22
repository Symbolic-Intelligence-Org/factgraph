# Blueprint: Validator Field Tag Fallback (Mistral Compatibility Fix)

- Status: implemented
- Created: 2026-04-13
- Kind: **validation layer tolerance fix**
- Trigger: Benchmark 诊断发现 Mistral 14/14 proposals 被 `schema_field_type_mismatch` 拒绝 — Mistral 在 `field_values[].tag` 里写 arg name ("description") 而非 type_domain ("string")
- Related Modules:
  - `src/factpy_kernel/agent/extraction/validation.py`
- Audit Log:
  - [2026-04-13_validator-field-tag-fallback.audit.md](./2026-04-13_validator-field-tag-fallback.audit.md)

---

## 0. Scope

在 `_validate_field_types` 的 tag 匹配逻辑中加一层 fallback: 如果 `tag != type_domain`,检查 `tag` 是否是对应 arg_spec 的 `name`。如果是,将 tag 修正为 `type_domain` 并继续 validation。

**做什么**:
- `validation.py` 的 `_validate_field_types` 加 ~8 行 fallback 逻辑
- `test_agent_l4c3a_validation.py` 加 2 个定向单测(fallback 通过 + 非法 tag 仍拒绝)

**不做什么**: 不改 prompts / extractor / batch / models / resolution。不改 ExtractionRejection reasons。不放松任何其他 validation。

**副作用声明**: `_validate_field_types()` 从"纯校验"变成"校验 + 原地规范化"。这在当前调用链中是安全的:
- `field_values` 来自 `_normalize_field_values()` 返回的新 list(非原始 proposal)
- 修正后的 `field_values` 直接喂给 `FactDraftSpec`,不回写 LLM response
- 函数语义变更应在此处明确记录,因为函数名("validate")不暗示修改能力

## 1. Root Cause

```
Schema summary 里 LLM 看到:
  - person:description subject=person:entity_ref field_values=[description:string]

GPT-4.1 输出:  tag="string"   (type_domain — 正确)
Mistral 输出:  tag="description" (arg name — 语义正确但格式错)
```

Rule 10 说 `tag = type_domain`。GPT-4.1 遵守了,Mistral 没有。但 Mistral 的 proposal 内容(entity_type, identity, pred_id, value)全部正确。只是 tag 字段用了 arg name 而不是 type_domain。

## 2. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| TF-01 | Fallback 逻辑在 `_validate_field_types` 里,不在 `_normalize_field_values` 里 | Normalization 不应该查 schema;validation 已经有 schema 上下文 |
| TF-02 | Fallback 只对 tag == arg_spec.name 的情况生效,不做 fuzzy match | 最保守;只修 "写了 name 而不是 type_domain" 这一种 systematic error |
| TF-03 | Fallback 时修正 `field_values` 的 tag 为正确的 type_domain,然后继续正常 validation | 后续 `_validate_type_domain` 用修正后的 tag 做类型检查 |
| TF-04 | 不改 SYSTEM_PROMPT_TEMPLATE | prompt 规则 (Rule 10) 仍然说 tag = type_domain;fallback 是 safety net |

## 3. Implementation

`validation.py` `_validate_field_types` (line 198-201):

```python
# 原:
    for (tag, value), spec in zip(field_values, rest_specs, strict=True):
        type_domain = spec.get("type_domain", "")
        if tag != type_domain:
            return f"field tag '{tag}' does not match expected type_domain '{type_domain}'"

# 改:
    for idx, ((tag, value), spec) in enumerate(zip(field_values, rest_specs, strict=True)):
        type_domain = spec.get("type_domain", "")
        if tag != type_domain:
            # Fallback: some models write arg name instead of type_domain
            arg_name = spec.get("name", "")
            if tag == arg_name and type_domain:
                field_values[idx] = (type_domain, value)
                tag = type_domain
            else:
                return f"field tag '{tag}' does not match expected type_domain '{type_domain}'"
```

注意: `field_values` 是 `list[tuple[str, Any]]`,可以 in-place 修改(它是 `_normalize_field_values` 返回的新 list,不是原始 proposal)。

## 4. Acceptance Criteria

1. Mistral Small 在 Re-DocRED 上的 success rate 从 6/10 显著提升
2. GPT-4.1 行为不变(它的 tag 已经是 type_domain,不触发 fallback)
3. Regression: 1012+ tests green
4. `_validate_field_types` 对非 name 也非 type_domain 的 tag 仍然拒绝

## 5. Outcome

- **实现于**: `validation.py` line 198-208 + `test_agent_l4c3a_validation.py` 2 tests
- **Regression**: 1014 passed, 3 skipped
- **Validator audit**: 代码审计确认 fallback 实现正确(无 bug,无跨 arg 误判,in-place mutation 安全)
- **Benchmark 结论**: Fallback 解决了 tag 格式问题,但**不是 Mistral success rate 的根因**。根因是 instructor TOOLS mode 触发 parallel tool calling(另开蓝图 `mistral-native-client`)
- **Final status**: **implemented**
