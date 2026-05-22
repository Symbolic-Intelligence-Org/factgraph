# Task Blueprint Audit: certainty-confidence-kind-resolver-v1

- Blueprint: [2026-03-21_confidence-kind-certainty-routing.md](./2026-03-21_confidence-kind-certainty-routing.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-21 | draft→scoped | Blueprint v1 created (post-patch) | Option C: post-evaluation `_mark_certainty_eligible_candidates` with duck typing and dataclasses.replace. |
| 2026-03-21 | scoped | P1 fixes on v1 | P1a: return replaced candidate list. P1b: tighten eligibility with child artifact check. |
| 2026-03-21 | scoped | Blueprint rewritten to resolver architecture | 判定 post-patch 方案为权宜之计。4 个 structural debt：post-creation patch、duck typing、eligibility 重复、SDK/service 不一致。重写为 resolver protocol + shared eligibility + builder 创建时确定 confidence_kind。 |
| 2026-03-21 | scoped | P1+P2 fixes on resolver version | P1: 补完注入链（`runtime_v1 → Store.evaluate → evaluate_store → builders`），明确 Store.evaluate 也要新增参数。修正 §4 current-context：runtime 传 `RuleRegistry`（不是 `FileAuthoringRegistry`）给 evaluate，`FileAuthoringRegistry` 只在 certainty service 使用。P2: SDK parity 改为"deferred"而非"achieved"——core 架构预留 seam，SDK 将来可接入。 |
| 2026-03-21 | implementing | Steps 1-6 complete | resolver + builder + evaluate + Store.evaluate + service injection + _certainty_service refactor。偏差：不吞异常。223 tests green。 |
| 2026-03-21 | implemented | Steps 7-8 complete | 去掉 2 处冗余 manual patch，新增 2 negative tests（225 total）。4 docs synced。 |

## Decision Notes

- Post-patch 方案被放弃：builder→replace pattern 不可扩展到 probability，duck typing 脆弱
- Resolver protocol 放在 core 层（`_confidence_kind_resolver.py`），只依赖 core 类型
- `RuleSpecReader` 是 resolver 依赖的最小接口，不绑定具体 registry 类型
- `check_certainty_artifact_eligibility` 是共享 eligibility helper，routing 和 `_certainty_service.py` 共用
- `materialize_certainty_summary` 保留 `extract_single_referenced_support_tree` 作为 defense-in-depth（不替换）
- SDK 不注入 resolver → 保持 `"none"`，原因是"没有 RuleSpecReader"，不是"SDK 特殊"
- probability 预留 protocol slot，本轮不实现
