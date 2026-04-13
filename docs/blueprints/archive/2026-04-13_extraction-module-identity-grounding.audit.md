# Audit Log: Module Identity Grounding (I1+I2)

## 2026-04-13 — draft → scoped

### Trigger

P0-off adversarial 实验(`enable_entity_context=False, enable_gleaning=False`)跑 adversarial 文本,LLM 提出 `Module(name="data-infra team")`。人工判定: 这是 entity type misgrounding(team mention 错提为 Module identity),不是 identity fragmentation。

诊断根因链:
1. SYSTEM_PROMPT_TEMPLATE 有 Example 3 (Document title grounding) 和 Example 4 (Module description narrowing),但无 Module NAME grounding example
2. `build_schema_summary` 输出 `- Module identity=[name:string]` 不含 type description
3. LLM 不知道 "Module" = 软件组件,把 team 名当 Module.name

### Status transitions

- 2026-04-13 — draft → **scoped** (4 MG decisions frozen, plan approved)
- 2026-04-13 — implementing (prompt patch + prompt tests landed; compile passed)
- 2026-04-13 — implemented (`1007 passed, 3 skipped, 0 failed`; P0-off adversarial verification removed `Module(name=\"data-infra team\")`)
- 2026-04-13 — archived

### Outcome

Acceptance closed cleanly.

- The prompt-side diagnosis held: once Example 5 and optional entity type descriptions were added, the `data-infra team` owner mention stopped being extracted as `Module.name`.
- No code contract changes were needed; the entire change stayed inside prompt construction and prompt tests.
- The same behavioral verification also exposed a new follow-up signal outside this blueprint's scope: `Kafka Ingest Pipeline` and `ingest` remained as separate resolver keys in the P0-off adversarial run.
- This blueprint therefore closes as implemented, while carrying forward a stronger P2 candidate than the team-name misgrounding that originally triggered it.
