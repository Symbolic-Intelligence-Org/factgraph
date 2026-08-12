# Task Blueprint: FactGraph derivation-output/materialization cleanup

- Status: implementing
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: task-scoped implementation contract for F3C only.
- Inputs:
  - [`2026-08-12_q5c-derivation-output-materialization-boundary-decision.md`](../../design/decisions/active/2026-08-12_q5c-derivation-output-materialization-boundary-decision.md)
  - [`2026-05-25_t5-d18-return-shape-transition.md`](../../design/decisions/active/2026-05-25_t5-d18-return-shape-transition.md)
  - [`2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md`](../../design/decisions/active/2026-05-25_t5-d23-legacy-sdk-hard-cut-plan.md)
  - F3C three-way read-only audit completed 2026-08-12
- Outputs / Downstream:
  - Canonical internal `DerivationOutput` vocabulary
  - Explicit cross-repository Meander migration gate
- Related:
  - [`2026-08-12_factgraph-derivation-output-materialization-cleanup.audit.md`](./2026-08-12_factgraph-derivation-output-materialization-cleanup.audit.md)
- Related Modules:
  - `src/factgraph/core/derivation/candidates.py`
  - active FactGraph read-only evaluation producers/consumers
  - `src/factgraph/sdk/store.py`
  - `src/service/runtime_v1.py`
- Audit Log:
  - [`2026-08-12_factgraph-derivation-output-materialization-cleanup.audit.md`](./2026-08-12_factgraph-derivation-output-materialization-cleanup.audit.md)
- Branch: `codex/v0.3.0-f3c-derivation-output-cleanup-2026-08-12`
- Base: `4024526c`

## 1. Problem

The active evaluation pipeline uses a misleading write-oriented type name.
The public candidate seam also contradicts adopted D18/D23, but is consumed by
shipped Meander and therefore cannot be deleted safely in this local slice.

## 2. Goals

- Remove five proven-dead primary service candidate codecs and the four-helper
  parser chain used only by them.
- Introduce canonical `DerivationOutput` in place, with a direct legacy
  `CandidateSet` alias.
- Move active read-only FactGraph producers, adapters and evaluation consumers
  to the canonical name while preserving all runtime and wire behavior.
- Repair two proven application-wrapper safety gaps without adding an API.
- Make compatibility debt and the later Meander migration gate durable.

## 3. Non-goals

- No public seam deletion or rename, Agent/Meander edit,
  persistence migration, ID/digest change, F4 implementation or new DTO/module.
- No opportunistic cleanup of unrelated uses of “candidate”, including
  governance proposals, search candidates or historical docs.

## 4. Current Context

- D18 §4.3 disallows public candidate compatibility; D23 allows private runtime
  carriers but requires a coherent hard-cut.
- F3B returns `EvaluateResult` and already excludes compiled Query from the
  candidate seam; its review passed 458 tests plus 33 adversarial probes.
- Meander `main@4ddb8e36` calls the seam from
  `rules/accept_candidates.py:80`, `rules/rule_source.py:182`,
  `graph/probabilistic.py:156`, and `graph/self_labels.py:259`.
- Five codec helpers at `service/runtime_v1.py:2505-2640` have zero callers.
- Core/application accept remains live; the HTTP accept route is an intentional
  removed-surface response, not one of the dead codecs.

## 5. Proposed Shape

### Batch A — honest surface quarantine

1. Delete the five primary zero-call codecs and the four parser/normalization
   helpers referenced only by that chain; remove imports made unused by those
   deletions.
2. Keep `fg.eval.evaluate_candidates`, its tests and Meander contract working.
   Mark it temporary cross-repository compatibility debt in current-truth SDK
   docs; do not describe D23 as complete.
3. Keep the service HTTP tombstone and Agent review/accept surface unchanged.

### Batch B — canonical in-process vocabulary

1. Rename the existing dataclass definition in place to `DerivationOutput` and
   define `CandidateSet: TypeAlias = DerivationOutput` in the same module.
2. Migrate active read-only producers and consumers—including engine adapters,
   core evaluation, application evaluation and SDK result conversion—to
   `DerivationOutput`. Compatibility/materialization modules may retain the
   alias where their historic field/wire vocabulary remains authoritative.
3. Repair the application single wrapper to call `Store.accept`; repair batch
   to reject `dry_run=True`, reject multi-output `identity_override`, preserve
   per-item approval/note/actor metadata, and call `Store.accept_many`.
4. Add identity and regression tests proving both names are the same class and
   candidate IDs/keys/content remain byte-identical.
5. Update current-truth core/application/SDK docs. Historical workflow material
   remains untouched except this decision/blueprint pair.

## 6. Boundaries And Invariants

- No change to fields, constructor, equality, payload, ordering, confidence,
  support, `cand_v2`/`candk_v2`, refs, digests, ledger or audit wire.
- No second class, wrapper, coercion or deprecation warning.
- No new public export of `DerivationOutput`; it remains core/application
  substrate in this slice.
- Batch A and B are separate implementation commits and independently tested.
- Stop if the alias changes serialization/identity, requires a datastore
  migration, or forces Meander changes.
- Wrapper fixes preserve Store digest enrichment and fail closed rather than
  simulate unsupported batch dry-run/override semantics.
- F4 consumes result/query fingerprints only, never output/candidate identity.

## 7. Acceptance

- [ ] Five primary service codecs and their four-helper-only chain have no residue.
- [ ] Meander-dependent `evaluate_candidates` remains behaviorally compatible.
- [ ] `CandidateSet is DerivationOutput` and existing constructors still work.
- [ ] Active read-only chains use canonical terminology.
- [ ] Candidate protocol and materialization regression cohorts are unchanged.
- [ ] Single/batch wrapper P1 cases pass focused regression tests.
- [ ] F3A/F3B Query/evaluate/explain cohorts and static checks pass.
- [ ] Current docs state the temporary debt and F4 fingerprint boundary.

## 8. Implementation Plan

1. Land Batch A deletion plus focused service/SDK compatibility tests.
2. Land Batch B alias migration and wrapper safety repairs plus focused tests.
3. Run one cumulative application/SDK/core/adapter/service cohort, Ruff, mypy,
   compile/diff checks and one bounded independent review.
4. Record outcomes, archive the pair, and hand off a separate cross-repository
   Meander materialization migration proposal; do not start it automatically.

## 9. Docs To Update

- `src/factgraph/core/derivation/CANDIDATE_PROTOCOL_V2.md`
- `src/factgraph/application/docs/rule.md`
- `src/factgraph/sdk/docs/03_rules_and_inferences.en.md`
- `src/factgraph/sdk/docs/04_api_surface.en.md`

## 10. Outcome / Deviations

To be completed after implementation and the single cumulative review.
