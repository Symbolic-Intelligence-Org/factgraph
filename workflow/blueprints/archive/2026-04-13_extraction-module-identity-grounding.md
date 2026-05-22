# Blueprint: Module Identity Grounding (I1+I2 — Prompt-Level)

- Status: implemented
- Created: 2026-04-13
- Kind: **extraction prompt enhancement** (no code contract change)
- Trigger: P0-off adversarial 实验暴露 `Module(name="data-infra team")` entity type misgrounding
- Related Modules:
  - `src/factpy_kernel/agent/extraction/prompts.py`
- Audit Log:
  - [2026-04-13_extraction-module-identity-grounding.audit.md](./2026-04-13_extraction-module-identity-grounding.audit.md)

---

## 0. Scope

**I1**: SYSTEM_PROMPT_TEMPLATE 加 Example 5 — Module name grounding (WRONG: team name as Module / RIGHT: software component)
**I2**: `build_schema_summary` 加 `entity_descriptions` optional 参数,输出 entity type description 行

**不做**: I3 (validation 层 keyword blocklist) — 留作 evidence-driven 后备

## 1. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| MG-01 | 只改 prompt,不改 validation | 根因在 prompt-side misgrounding,不在 validator 漏洞 |
| MG-02 | Example 5 和 Example 3/4 同构(WRONG/RIGHT pattern) | 已验证有效的 prompt 教学模式 |
| MG-03 | `entity_descriptions` 是可选参数,默认 None = backward compatible | 不强制所有 caller 提供 descriptions |
| MG-04 | 不改 schema_ir 结构 | 当前 schema_ir 的 entity dict 没有 description 字段,改 SDK 不在 scope |

## 2. Acceptance Criteria

1. `py_compile` pass
2. 1004 + 3 new tests green
3. P0-off adversarial 重跑: `Module {'name': 'data-infra team'}` 不再出现

## 3. Outcome / Deviations

Implemented as scoped, with no deviations.

- Compile passed for the changed prompt module and tests.
- Regression passed: `1007 passed, 3 skipped, 0 failed`.
- Acceptance #3 passed in Notebook 08 P0-off adversarial verification:
  - `Module {'name': 'data-infra team'}` no longer appeared in either extraction-layer or resolver-layer key census.
  - P0-off extraction output became:
    - `Module {'name': 'Kafka Ingest Pipeline'}`
    - `Module {'name': 'ingest'}`
    - `Module {'name': 'resolve'}`
    - `Module {'name': 'serve'}`
  - This confirms the prompt-level misgrounding fix landed: owner/team mentions stopped being extracted as module identities.
- Carry-forward:
  - The same adversarial run surfaced a cleaner P2 signal than before: `Kafka Ingest Pipeline` and `ingest` survived as separate resolver keys for the same logical module.
  - That is not a deviation in this blueprint's scope; this blueprint fixed type misgrounding, not alias merging.
  - If extraction work continues, the next candidate line is P2 cascaded ER / fuzzy identity matching, now with concrete notebook evidence.
