# Q13 Decision: ScenarioRun v0 capture boundary

- Status: adopted
- Created: 2026-08-13
- Authority: 2026-08-13 user authorization for continuous FactGraph delivery; this is a bounded implementation decision, not approval for a general premise language.
- Depends on: Q5A/Q5B, Q6A/Q6B, Q7, Q11, Q12.
- Downstream: [`ScenarioRun v0 continuous blueprint`](../../../blueprints/active/2026-08-13_factgraph-scenario-run-v0-continuous.md)

## Decision

Keep the existing `fg.eval.evaluate(compiled_query, scenario=...)` path as a
fast, deliberately non-captured compatibility surface.  Add a separate,
explicit `ScenarioRunV0` path for the already admitted replacement-only
Scenario forms:

```text
trusted Query + replacement-only Scenario
  -> captured baseline relation and captured effective relation
  -> detached ScenarioRun evidence / Policy projection / bounded diff
  -> isolated native verification
```

The new path uses the exact same materialized native Query plan twice.  Its
proof receipts are captured in an in-memory private sink: they are never
written to the ledger support sidecar or candidate-support index.

## Public shape

- `fg.eval.run_scenario(compiled_or_targeted_query, scenario)` is the canonical
  low-level entry.
- `fg.query(...).bind(...).select(...).what_if(scenario).run()` is the thin
  Query-first convenience entry.
- `ScenarioRunV0.diff()`, `.explain(side=..., row_capture_digest=...)`, and
  `.verify()` operate only from its captured payload; no current Store fallback
  is permitted.

## Boundaries

- Only Q7/Q11 scalar replacement of existing, visible, single-valued fields;
  native engine, `config=None`, empty premise filters, no expectations.
- No add/delete/mask, relation or entity premise, `not`, closure, as-of time,
  source authority, Policy/rule overlay, operator/action, catalog lookup,
  non-native engine, or generic Scenario Plan.
- `EvaluationRunBundleV0` remains unchanged.  A ScenarioRun uses its proven
  capture/verification primitives internally but never exposes an effective
  synthetic witness as a normal ledger-backed F4 source.
- Detached evidence labels every source as a captured baseline/effective
  relation witness or a `scenario_hypothesis`; it does not claim authority,
  truth, provenance admission, or replay of the historical ledger.

## Acceptance

- [ ] Two effective-relation evaluations capture receipts without Store writes.
- [ ] ScenarioRun is sealed, codec round-trips, and rejects cross-run splice.
- [ ] Detached Explain maps through the authored Policy tree and preserves the
  synthetic-hypothesis boundary.
- [ ] Diff and isolated verification are deterministic and do not consult a
  live Store after capture.
- [ ] Rule and direct Policy (including field comparison/navigation) share the
  same ScenarioRun path.
