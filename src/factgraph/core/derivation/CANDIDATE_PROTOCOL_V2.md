# Candidate Protocol v2

Status: implemented (strict v2, legacy fallback removed)
Scope: `authoring` / `core.derivation` / `core.store` / `sdk` / `service`

## 1. Chain

This document defines the persisted compatibility contract for:

Derivation -> DerivationOutput -> optional CandidateSet-compatible materialization -> Ledger

The v2 model separates entity materialization from fact writes and makes
candidate identity/provenance explicit.

`DerivationOutput` is the canonical in-process read-only type.
`CandidateSet` is a direct type alias retained for this materialization and
persisted v2 vocabulary; it is not a second DTO or a public evaluation result.
The candidate-named fields and digest prefixes below remain byte-stable.

## 2. Hard Rules

1. `DerivationOutput` (and its `CandidateSet` compatibility alias) carries
   explicit v2 identity fields:
   - `candidate_id` (`cand_v2:`): per-run handle
   - `candidate_key` (`candk_v2:`): cross-run stable key
   - `candidate_kind`: `fact` or `entity`
   - for native derivation candidates, `candidate_id` can now be used as an in-process backref handle to recover `support_digest` via `Store.get_candidate_support_digest(...)`
2. `candidate_key` is content-addressed and excludes `run_id`.
3. `head` shape drives candidate kind:
   - `EntityType(...)` -> entity path
   - `Entity.field(...)` -> fact path
4. Fact payload uses `terms`; `terms[0]` is the subject slot (arg0).
   `pred_id` is normally explicit and falls back to `candidate_set.target` when omitted.
5. Entity candidate only handles identity + `<T>:exists` materialization.
   Field writes are separate fact candidates.
6. Provenance is stored in claim meta rows and is not encoded in `entity_ref`.

## 3. DerivationOutput / CandidateSet-compatible v2 payload

Shared top-level fields:

```json
{
  "candidate_id": "cand_v2:...",
  "candidate_key": "candk_v2:...",
  "candidate_kind": "fact|entity",
  "target": "...",
  "derivation_id": "...",
  "derivation_version": "...",
  "run_id": "...",
  "support_digest": "sha256:...",
  "support_kind": "native_binding_v1|none",
  "generated_at": 0,
  "state": "generated",
  "confidence": null,
  "confidence_kind": "none|probability|certainty",
  "payload": {}
}
```

Support fields:

- `support_digest`
  - content digest for the candidate's support/provenance carrier
  - for native derivation candidates this is the digest of an evaluate-time captured internal support artifact
- `support_kind`
  - `native_binding_v1`: native derivation support captured from evaluate-time binding/witness summary
  - `none`: no support artifact captured for this candidate path yet; compatibility/engine paths may still emit this value
- `confidence`
  - optional narrow numeric value carried by the candidate
  - current writers either leave it `null` or write an engine-specific value (for example ProbLog probability)
- `confidence_kind`
  - additive semantic discriminator for `confidence`
  - `none`: no modeled numeric semantics on this candidate
  - `probability`: the numeric value is probabilistic
  - `certainty`: reserved for future certainty-weighted reasoning paths
  - does not enter `candidate_key`, `candidate_id`, or `support_digest` computation

Entity payload:

```json
{
  "entity_type": "User",
  "identity_fields": ["source_system", "source_id"],
  "identity_types": {"source_system": "string", "source_id": "string"},
  "resolved_identity": {"source_system": "APP"},
  "missing_identity_fields": ["source_id"],
  "proposed_entity_ref": null
}
```

Fact payload:

```json
{
  "pred_id": "user:name",
  "terms": [
    {"kind": "candidate_ref", "candidate_key": "candk_v2:..."},
    {"kind": "literal", "tag": "string", "value": "Alice"}
  ]
}
```

Dependency edges are derived from `terms[*].candidate_ref`.
No standalone `dependencies` field is used.

## 4. Key Algorithms

`candidate_key` input:

- constant domain tag
- `derivation_id`
- `derivation_version`
- `candidate_kind`
- canonicalized candidate content

Canonical content:

- entity: `entity_type + identity_fields + identity_types + resolved_identity + missing_identity_fields + proposed_entity_ref`
- fact: `(pred_id or target fallback) + normalized terms` (candidate refs use upstream `candidate_key`)

Computation order must follow dependency DAG:

- leaf entity candidates first
- dependent fact candidates after upstream entity keys are known

Cycles are rejected before accept.

## 5. Accept Protocol

Single accept:

- entity candidate:
  - validate/merge identity (`resolved_identity` + `identity_override`)
  - require all identity fields before materialization
  - write `<T>:exists` materialization claim when absent (no separate entity registry row)
- fact candidate:
  - resolve `terms` into `(subject_e_ref, rest_terms)`
  - resolve `candidate_ref` from accepted-in-batch map or active ledger entity claims keyed by `candidate_key`
  - write fact claim

`identity_override` constraints:

1. only `missing_identity_fields` are allowed
2. sending any already-resolved identity field is conflict (even same value)
3. unknown identity field names are rejected

Batch accept:

```python
accept_many(
  requests,
  mode="atomic" | "best_effort",   # default: atomic
  idempotent_duplicate_ok=True
)
```

- Execution order: topological by `candidate_ref` edges
- `atomic`: any non-allowed failure triggers rollback for prior writes in batch
- `best_effort`: failed nodes stay failed; dependents become `BLOCKED_DEPENDENCY`

Returned per-candidate states:

- `ACCEPTED`
- `DUPLICATE`
- `BLOCKED_DEPENDENCY`
- `FAILED_VALIDATION`
- `FAILED_RUNTIME`

## 6. Provenance Meta Contract

Every accepted claim writes derivation metadata including:

- `source=derivation.accept`
- `source_loc`, `trace_id`
- `derived_rule_id`, `derived_rule_version`
- `derivation_id`, `derivation_version`, `run_id`
- `key_tuple_digest`, `cand_key_digest`
- `candidate_id`, `candidate_key`, `candidate_kind`
- `support_digest`, `support_kind`
- `accepted_at`

Conditionally included fields:

- `confidence_kind` (currently always written by derivation accept; defaults to `"none"` for legacy candidate payloads)
- `schema_digest`, `policy_digest` when available from store metadata
- `confidence` when the candidate carries it
- `approved_by` / `accepted_by` only when `options.approved_by` is supplied
- `note` only when `options.note` is supplied

Entity accept also writes:

- `entity_type`
- `entity_ref`
- `identity_override_digest` (when override is used)

## 7. Strictness and Migration

No legacy candidate payloads are accepted:

- fact candidates must use v2 `terms`; `pred_id` may be omitted and will default to `candidate_set.target`
- entity candidates must use the v2 identity payload

Authoring/user syntax:

- `materialize_as` is removed from user-facing derivation DSL
- `id_policy` is removed from user-facing derivation DSL
- no-head derivations (`target_pred_id + head_vars`) remain fact-only compatibility path
- primary_key fields in `head` are compile-time hard errors
- `temporal_view` entry points are removed and fail explicitly
- cross-coordinate attribute compare is restricted to same identity field comparisons

Schema/protocol breakings relevant to migration:

- `Field.dims` removed
- `Field.fact_key` removed
- `Field.cardinality` enum changed from `functional|multi|temporal` to `single|multi`
- `Identity()` fields form the immutable anchor bundle for cross-coordinate joins
- `sdk_batch_plan_v1` wire payload no longer carries `dims` / `fact_key`
- write idempotency (`ingest_key`) includes business-temporal meta (`valid_from`/`valid_to`/`version`) in addition to source/trace material

For the full upgrade checklist, see:

- `src/factgraph/sdk/docs/03_rules_and_derivations.md` (section 6.3)
- `src/factgraph/sdk/docs/03_rules_and_derivations.en.md` (section 6.3)
