# Task Blueprint Audit: Certainty Summary Explain Delivery

- Blueprint: [2026-03-21_certainty-summary-explain-delivery.md](./2026-03-21_certainty-summary-explain-delivery.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-21 | scoped | Blueprint created | First production consumer for `derive_certainty_summary`. Narrowest delivery surface: runtime explain summary only. Requires Store index extension for `confidence_kind` + service-level condition_weights lookup via support → rule_ref_edges → registry chain. |
| 2026-03-21 | scoped | Review round 1 — 3 issues fixed | P1: single rule_ref_edges[0] replaced with eligibility guard (single structured edge + no nested referenced_support). P1: override_registry_root support added to explain summary dto. P2: service docs added to update list. |
| 2026-03-21 | scoped | Review round 2 — lookup 三态修正 | `_lookup_condition_weights_for_candidate` 返回 `None | {} | {k:v}` 三态；`None` = ineligible/链路不可用 → skip derive → `certainty_summary: null`；`{}` = eligible 但无 weights → all-unweighted summary；有值 dict → weighted summary。修正了 eligibility guard 失败仍会产出 all-unweighted dict 的不一致。 |
| 2026-03-21 | implemented | Delivery surface completed | Store 现在索引 `candidate_id -> confidence_kind`；runtime `explain-summary(kind=\"candidate\")` 会附加 response-level `certainty_summary`；contract tests 与模块文档已同步。 |
| 2026-03-21 | implemented | Implementation deviation recorded | 最终 certainty derivation 改为只消费单条 structured `rule_ref_edge` 指向的唯一 `referenced_support` subtree；原因是 `condition_weights` 属于 child rule metadata，不能直接对整棵 candidate tree 做 namespace-blind 匹配。单条 unresolved child support 也因此统一降级为 `null`。 |

## Decision Notes

- 2026-03-21: Only `explain_runtime_summary` candidate response is extended — audit, static, NL delivery surfaces not included. Rationale: validate one delivery path before widening.
- 2026-03-21: `certainty_summary` is a response-level sibling of `summary`, not nested inside the 12-field core set. This preserves the existing summary contract and makes the extension opt-in for consumers.
- 2026-03-21: `confidence_kind` index added to Store via `_remember_candidate_support` extension (default `"none"` for backward compatibility). This is the minimal change to make confidence_kind queryable by candidate_id at explain time.
- 2026-03-21: condition_weights lookup is service-level (not core). The chain `support → rule_ref_edges → FileAuthoringRegistry` is a query-time composition, not a core Store responsibility.
- 2026-03-21: Graceful degradation: any missing link in the chain results in `certainty_summary: null`, not an error. This prevents the extension from breaking existing explain flows.
- 2026-03-21: **Single rule eligibility guard** — atom key namespace `b{branch}.a{atom}` is per-rule local, no rule ownership metadata. Taking `rule_ref_edges[0]` in multi-rule or recursive-subtree scenarios would mismatch weights. Guard: only produce certainty_summary when exactly 1 structured rule_ref_edge and no nested `referenced_support` nodes. Multi-rule aggregation requires rule/subtree ownership design (deferred).
- 2026-03-21: **override_registry_root in explain summary** — evaluate-time `override_registry_root` is not recorded in candidate backref. Explain summary must accept the same override to read the correct rule payload. Without it, fallback to `session.registry_root` may read wrong payload or degrade to null. This is a known limitation; recording registry_root in backref would be a larger change.
