# Audit Log: session-agent-inventory

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-04-01 | draft | Blueprint created | P2 缺口：rule inventory + candidate rediscovery；从 ephemeral-rule-hardening 完成后自然跟进 |
| 2026-04-01 | scoped | Status advanced to scoped | 两个端点设计冻结：GET /sessions/{id}/rules (FS+ephemeral merge, include_spec 可选) + GET /sessions/{id}/candidates (store.list_candidate_ids 暴露)；AC 7 条；P2-6 并发明确不在此处处理 |
| 2026-04-01 | implementing | Implementation started | 已确认 `_remember_candidate_support_backrefs()` 是唯一漏斗点，`get_candidate_support_kind()` 已存在；本轮只补 `_candidate_pred_index`、session inventory handlers、routes、tests、runtime session docs |
| 2026-04-01 | implemented | Implementation complete | Store 新增 `_candidate_pred_index` 并在 `_remember_candidate_support_backrefs()` 漏斗点写入；新增 `GET /sessions/{id}/rules` 与 `GET /sessions/{id}/candidates` handlers/routes；`02_runtime_sessions.md` 已更新；`test_session_agent_inventory` 11 tests 通过，全量 `python -m unittest discover -s src/factpy_kernel/tests` 754 tests green |
