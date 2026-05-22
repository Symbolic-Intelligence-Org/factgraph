# Task Blueprint Audit: Native Candidate Evidence Tree Winning-Branch Semantics

- Blueprint: [2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md](./2026-03-19_native-candidate-evidence-tree-winning-branch-semantics.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Opened a narrow capability-decision blueprint for `winning-branch semantics` after recursive proof first-round implementation, with scope explicitly limited to OR-of-AND proof-path selection. |
| 2026-03-19 | draft | Freeze framing tightened | Recorded that first-round winning-branch discussion should prefer capture-time narrowing, source-order tie breaking, recoverable branch identity without a required top-level field, and capture-local re-computation as the default provenance route. |
| 2026-03-19 | draft | Provenance gate refined by atom kind | Added an explicit freeze gate that capture-local re-computation must define branch satisfaction per atom kind, rather than treating the existence of a final binding as sufficient proof that every atom in a branch satisfied. |
| 2026-03-19 | draft | Atom-kind satisfaction rules written back | Recorded concrete first-round re-check rules aligned with `where_eval.py`: all atom kinds are rechecked as final-binding boolean consistency filters, with `not` explicitly called out as the only non-fact atom that must revisit `view_facts` / `witness_facts`. |
| 2026-03-19 | scoped | Scope freeze completed | Scoped freeze confirmed after settling winning-branch as a formal proof contract, capture-time narrowing, recoverable branch identity, source-order tie handling, no shadow metadata, and capture-local re-computation with atom-kind satisfaction rules. |
| 2026-03-19 | implemented | Semantics realized through narrowing implementation | The scoped semantics contract was implemented via the dedicated `winning-branch-narrowing` blueprint. Native support capture now narrows to a single adopted branch before artifact emission, and docs were updated to record the new proof contract. |

## Decision Notes

- 2026-03-19
  - Scope rule: this blueprint is not a continuation of execution substrate or recursive DTO design. It starts from the now-implemented recursive proof carrier and only discusses branch-choice semantics.
- 2026-03-19
  - Reality rule: current native support capture still walks all OR branches, while candidate builders still enforce single-support candidate selection. Any winning-branch decision must explicitly account for both facts.
- 2026-03-19
  - Boundary rule: first-round discussion should prefer narrowing at support-artifact capture time rather than tree-readback time; otherwise runtime / audit / static could diverge on proof-path interpretation.
- 2026-03-19
  - Identity rule: first-round should require selected branch identity to be recoverable from the resulting artifact, but should not force a new top-level `branch_index` field unless consumer needs later prove that implicit recovery is insufficient.
- 2026-03-19
  - Tie rule: if multiple branches satisfy the same final binding, first-round should prefer a deterministic source-order win (`lowest branch_index wins`) over treating overlap as an automatic contract violation.
- 2026-03-19
  - Provenance rule: before this blueprint can freeze to `scoped`, it must first confirm how `_support_capture` learns the winning branch. The default first-round assumption is capture-local re-computation from `binding + witness_facts + rule_ref_resolutions`, not widening substrate DTOs.
- 2026-03-19
  - Satisfaction rule: capture-local re-computation must define branch satisfaction separately for `pred`, `ruleref`, and other non-fact atoms. The blueprint should not allow a shortcut rule of “binding exists, therefore branch satisfied.”
- 2026-03-19
  - Re-check rule: the first-round atom-kind rules should mirror `where_eval` semantics but operate only as final-binding consistency checks. `eq` / `ne` / `in` / cmp stay boolean filters, arith atoms become compute-and-check, and `not` reuses negated-body zero-match semantics with access to `view_facts` / `witness_facts`.
- 2026-03-19
  - Freeze rule: the blueprint is now scoped. Follow-on implementation work should stay inside support-capture narrowing and tests, and should not reopen multi-support, substrate DTO widening, or tree taxonomy changes without a new scope update.
- 2026-03-19
  - Outcome rule: this semantics blueprint is now implemented through the dedicated `winning-branch-narrowing` child blueprint. The landed behavior matches the scoped contract: capture-time narrowing, source-order wins, recoverable branch identity, no shadow metadata, and atom-kind capture-local re-computation.
