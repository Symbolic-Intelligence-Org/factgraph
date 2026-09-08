# Core Policy

- Applicable scope: `src/factgraph/core/policy` and premise admissibility in
  `src/factgraph/core/store/premise_filter.py`
- Last updated: 2026-08-03
- Audience: maintainers of active-state, chosen-value, and evaluation-premise
  policy

This package turns the append-only Ledger history into evaluation-visible
state. It does not write claims, metadata, schema, or transaction objects.

## Active and Chosen State

`active.is_active(...)` treats an assertion as active only when no active
`__system__.revokes` claim targets it. System claims remain available to exact
id audit lookup but are excluded from factual scans and digest inputs.

For a single-cardinality predicate, `chosen.choose_one(...)` selects the active
claim with the greatest durable `claims.seq`. Sample time (`ingested_at`) and
assertion id no longer participate. This intentionally makes commit order win
for inverted clocks, equal timestamps, and imported histories. Multi-cardinality
predicates retain every active claim.

## Premise Admissibility

Premise filtering is an evaluation-only view. Ordinary query, audit, history,
and diagnosis reads remain unfiltered. Global `MetaExclusion`, per-predicate
`PredicatePremiseAllowance`, and per-predicate `PredicatePremiseBlock` all read
the shared effective metadata resolver; they do not implement their own row
ordering.

Effective metadata has two layers. Claim events are ordered by
`(tx_seq, op_ordinal)` and last-wins per `(asrt_id, key)`; an UNSET tombstone
makes the key absent. If no claim event exists, a canonical tx-level default
from the claim's `tx_ref` may supply the value. The same rule applies to factual
claims and revokers.

Premise keys are schema-closed. A configuration key is legal only when it is
one of the pinned built-ins (`provenance_class`, `origin_binding`) or its Schema
IR `meta_keys` declaration sets `premise_eligible=true`. A schema transition is
validated against the live premise configuration before commit, so removing
eligibility fails without leaving a temporarily invalid runtime.

`load_policy="lazy"` is a storage/workset choice, not a semantic choice. Lazy
keys stay visible through the effective resolver and premise policy while their
events and projections remain outside the eager in-memory indexes.

## Boundaries

- Policy consumes stable Ledger read APIs and never reaches into SQLite.
- `query_indexed=true` is representable in Schema IR but has no dedicated v0.3
  policy or physical-index consumer.
- Metadata history and as-of replay belong to the narrow audit/debug surface;
  evaluation always uses the latest effective state.
- Schema authoring, keyed IR diff, and retired-key policy belong to the separate
  schema-evolution blueprint.

## Test Entry Points

- `tests/test_premise_admissibility_filter.py`
- `tests/test_premise_predicate_allowance.py`
- `tests/test_premise_predicate_block.py`
- `tests/test_premise_scoped_view.py`
- `tests/test_slice3b_phase2_meta_events.py`
- `tests/test_slice3b_phase3_meta_policy.py`
- `tests/test_slice3b_phase3_tx_lift.py`
- `tests/test_slice3b_phase3_chosen_seq.py`
