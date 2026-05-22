# Audit Log: Cascaded ER — Fuzzy Identity Alias Merge (P2)

## 2026-04-13 — draft

### Trigger

I1+I2 (Module identity grounding) 修复后,P0-off adversarial 实验的 resolver 后 key census:
- `Module {'name': 'Kafka Ingest Pipeline'}` — 4 specs
- `Module {'name': 'ingest'}` — 1 spec
- `Module {'name': 'resolve'}` — 2 specs
- `Module {'name': 'serve'}` — 2 specs

`Kafka Ingest Pipeline` 和 `ingest` 是同一逻辑模块的两种表述,resolver 未合并。三点 P2 证据标准全部满足。

### Evidence chain

| 条件 | 满足? | 证据 |
|---|---|---|
| 同一逻辑实体被抽成 ≥2 个不同 identity key | ✅ | `Kafka Ingest Pipeline` + `ingest` |
| 人工可验证是同一实体 | ✅ | adversarial 文本明确写 "Kafka Ingest Pipeline" = "ingest" |
| Resolver 后仍未合并 | ✅ | post-resolver unique keys = 4 > expected 3 |

### Status transitions

- 2026-04-13 — draft created
- 2026-04-13 — **scoped** (5 ER decisions frozen, implementation approved)
- 2026-04-13 — implementing (`resolution.py` + resolver tests landed; compile passed)
- 2026-04-13 — implemented with deviations (`1012 passed, 3 skipped, 0 failed`; final notebook verification did not re-surface the alias split at extraction time)
- 2026-04-13 — archived

### Outcome

The resolver-side alias merge shipped, but the final notebook behavioral gate was not fully satisfiable on a single real-LLM rerun.

- Exact result of the final P0-off adversarial rerun with `enable_alias_merge=True`:
  - extraction layer keys: `Kafka Ingest Pipeline`, `resolve`, `serve`
  - resolver layer keys: `Kafka Ingest Pipeline`, `resolve`, `serve`
  - `merge_events`: empty
- This did NOT indicate a resolver regression. Instead, upstream extraction normalized the alias before resolution, so the resolver alias path was never exercised in that run.
- Full regression and deterministic resolver tests remained green, and those tests do exercise the alias path directly.
- The blueprint is therefore archived as `implemented with deviations`, with the deviation located in behavioral verification stability rather than code correctness.
