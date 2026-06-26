# Task Blueprint Audit: 实现 `fg.rules.structure` + `RuleStructure`

- Blueprint: [2026-06-26_rule-structure-impl.md](./2026-06-26_rule-structure-impl.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-06-26 | scoped | Blueprint created (scoped) | Consumes adopted decision 2026-06-26_evidencegraph-readonly-and-rule-structure-type (§4) + design-point rule-structure-static-projection (§3 contract). Collaboration: Codex-impl / Claude-gate / user-merge. |

## Decision Notes

### 2026-06-26 — scope freeze

- **Upstream lock**: decision §4.1 (EvidenceGraph 只读派生定位 + 机械明线) + §4.2 (独立中立类型 / 共享 backbone / `Evidence*` 零改动 / Tree-only) are adopted constraints; this blueprint must not deviate. The full `RuleStructure` field-level contract is the design-point §3.2 draft, to be finalized in-impl (slice 2).
- **Scope frozen to**: the 8-slice plan (§8). `Evidence*` (`evidence_tree.py`) is strictly read-only/unchanged — if any slice appears to need an `Evidence*` change, that is a scope breach → stop + escalate (it would mean the "don't mix" decision is being violated).
- **Collaboration cadence**: Codex implements each slice; Claude gates against the matching Acceptance item (verify + regression) before the next slice; user merges at scoped-unit completion. Per `feedback_no_autonomous_code_edits` + `feedback_push_master_gate`, Claude does not modify shipped `src/` autonomously and does not auto-push.
- **Open items carried from design-point** (resolve during impl, record here):
  - Q2: exact home of `assemble_static_structure` + prober split granularity (slice 1/3).
  - Q3: `fg.rules.structure` return shape (direct `RuleStructure` vs wrapper) (slice 5).
  - Q4: pyreason/Timeline cross-model mapping — out of scope here; documented as a boundary (slice 8).

### Gate log (append per slice)

<!-- | Date | Slice | Codex result | Claude gate verdict | Notes | -->
