# Task Blueprint Audit: Certainty / Weight Vocabulary

- Blueprint: [2026-03-20_certainty-weight-vocabulary.md](./2026-03-20_certainty-weight-vocabulary.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-20 | draft | Blueprint created | Opened after Rainbird comparison review identified certainty/weight as the largest structural gap across Result/Evidence Tree/Salience layers. Triggered by: salience/impact freeze (`69d45d9`), Rainbird comparison update, and session handoff recommendation. |
| 2026-03-20 | scoped | All 5 discussion axes frozen | §5.1: `confidence` + `confidence_kind` (枚举 `none\|probability\|certainty`); §5.2: weight in rule metadata, not where_ast; §5.3: rule-level cap deferred; §5.4: deterministic = `"none"` not 1.0; §5.5: annotation prototype is consumer not owner. Three child blueprints identified. |
| 2026-03-20 | implementing | Child 1 completed | `candidate-confidence-kind` implemented and archived. `CandidateSet.confidence_kind` field landed with full production/propagation/serialization coverage. 175 tests pass. |
| 2026-03-20 | implementing | Child 2 completed | `rule-condition-weight-metadata` implemented and archived. Rule asset metadata now preserves `description / tags / condition_weights` across SDK -> authoring compile -> service compile-preview -> registry register/read. 180 tests pass. |
| 2026-03-20 | implementing | Child 3 completed | `certainty-propagation-prototype` implemented and archived. Annotation prototype now consumes `confidence_kind="certainty"` + `condition_weights` + evidence tree to derive per-condition weighted impact and bottleneck certainty summary. 194 tests pass. |
| 2026-03-20 | implemented | Parent archived | All three child slices completed; certainty/weight vocabulary parent blueprint marked implemented and moved to archive. |

## Decision Notes

- 2026-03-20: This blueprint was opened because certainty/weight vocabulary is a cross-cutting prerequisite that blocks multiple deferred capability lines (salience/impact, confidence semantic separation, rule-level cap). It is not a single feature but a vocabulary/contract design problem.
- 2026-03-20: `confidence_kind` enum deliberately excludes `"score"` to prevent re-introducing semantic ambiguity through a catch-all bucket. The enum is `none | probability | certainty` only.
- 2026-03-20: Per-condition weight belongs to rule metadata, not rule IR. Rationale: rule IR is the logical execution contract; weight is value semantics. Coupling them would drag all engines into weight-understanding obligation.
- 2026-03-20: "deterministic ≠ certainty=1.0" is a critical semantic distinction. Deterministic engines have no uncertainty model at all, not a model that happens to output 1.0. This prevents downstream salience calculations from confusing "no model" with "maximum certainty".
- 2026-03-20: Annotation prototype is explicitly positioned as first consumer, not contract owner. The vocabulary is a core-level, engine-neutral contract; annotation prototype validates it but does not define it.
- 2026-03-20: Rule-level certainty cap is deferred until confidence_kind and per-condition weight are stable. When revisited, cap should also land in rule metadata, not where_ir.
