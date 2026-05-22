# Task Blueprint Audit: Rule Engine Ext Alignment

- Blueprint: [2026-03-28_rule-engine-ext-alignment.md](./2026-03-28_rule-engine-ext-alignment.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-28 | draft | Blueprint created | Opened after handoff `2026-03-28-e` and ADR review showed `PyReasonRuleDef` had become an implementation drift from the intended `Rule.engine_ext` carrier. |
| 2026-03-28 | scoped | Scope frozen for implementation | Limit the slice to `Rule.engine_ext`, PyReason compile/run compatibility, test/example migration, and module-doc sync. |
| 2026-03-28 | implemented | Code, docs, and compatibility path landed | Shared `Rule.engine_ext` is now the preferred carrier; PyReason wrapper remains compatibility-only; targeted and full regressions passed. |
| 2026-03-28 | archived | Blueprint archived | Implementation complete; active blueprint area returned to decision/reference material only. |

## Decision Notes

- This slice restores architectural alignment by moving the preferred definition-time engine carrier onto shared `Rule`, while keeping `PyReasonRuleDef` as a compatibility shim.
- The compatibility wrapper was intentionally not removed; preserving it avoids breaking adapter-local call sites while moving repo truth to `Rule.engine_ext`.
