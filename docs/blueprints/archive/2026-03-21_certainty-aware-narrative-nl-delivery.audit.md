# Task Blueprint Audit: Certainty-Aware Narrative/NL Delivery

- Blueprint: [2026-03-21_certainty-aware-narrative-nl-delivery.md](./2026-03-21_certainty-aware-narrative-nl-delivery.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-21 | scoped | Blueprint created | Scope: runtime narrative + NL only. Additive `certainty_lines` section + 5th NL paragraph. No audit/static/probability/ranking. Shared helper extraction from explain-summary. |
| 2026-03-21 | scoped | Review round 1 — 3 issues fixed | P2: helper 改为接收预建 tree_dict 避免重复构建。P2: certainty_lines 首行显式标注 scope 为 "eligible child-proof subtree"。P3: NL 签名不变，只消费 narrative.certainty_lines，删除多余 certainty_summary 入参。 |
| 2026-03-21 | implemented | Implementation complete | Added `_compute_certainty_summary_from_tree(...)` to runtime service; candidate narrative now emits additive `certainty_lines`; candidate NL now appends a 5th certainty paragraph when narrative carries certainty lines; full suite now `209` tests green. |
| 2026-03-21 | implemented | Docs aligned | Updated runtime queries/views, annotation prototype docs, and core architecture doc to reflect that certainty is now consumed by runtime summary, narrative, and NL delivery without widening the core 12-field summary set. |

## Decision Notes

- 5 轴全部选 A（最窄），确保本轮只扩消费面不增语义
- `certainty_summary` 作为 keyword-only optional 参数只传入 narrative；NL 不接收，只消费 narrative 输出
- `certainty_lines` key 只在 `certainty_summary is not None` 时出现，不是空 list
- `certainty_lines` 首行显式标注 "eligible child-proof subtree" scope，避免误读为 full candidate certainty
- 共享 helper `_compute_certainty_summary_from_tree` 接收预建 tree_dict，避免在 narrative/NL 路径重复 `_get_candidate_tree`
- 本轮仍不触碰 runtime HTML、audit package、static site 和 probability lane；这些留给后续独立 slice
