# Candidate Protocol v2

Status: implemented (with explicit legacy fallback paths)
Scope: `authoring` / `core.derivation` / `core.store` / `sdk` / `service`

## 1. Chain

This document defines the runtime contract for:

Derivation -> CandidateSet -> Accept -> Ledger

The v2 model separates entity materialization from fact writes and makes
candidate identity/provenance explicit.

## 2. Hard Rules

1. `CandidateSet` carries explicit v2 identity fields:
   - `candidate_id` (`cand_v2:`): per-run handle
   - `candidate_key` (`candk_v2:`): cross-run stable key
   - `candidate_kind`: `fact` or `entity`
2. `candidate_key` is content-addressed and excludes `run_id`.
3. `head` shape drives default materialization when not explicitly set:
   - `EntityType(...)` -> entity/record path
   - `Entity.field(...)` -> fact path
4. Fact payload uses `terms`; `terms[0]` is the subject slot (arg0).
5. Entity candidate only handles identity + `<T>:exists` materialization.
   Field writes are separate fact candidates.
6. Provenance is stored in claim meta rows and is not encoded in `entity_ref`.

## 3. CandidateSet v2

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
  "generated_at": 0,
  "state": "generated",
  "payload": {}
}
```

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
- fact: `pred_id + normalized terms` (candidate refs use upstream `candidate_key`)

Computation order must follow dependency DAG:

- leaf entity candidates first
- dependent fact candidates after upstream entity keys are known

Cycles are rejected before accept.

## 5. Accept Protocol

Single accept:

- entity candidate:
  - validate/merge identity (`resolved_identity` + `identity_override`)
  - require all identity fields before materialization
  - write `<T>:exists` (+ entity registration if new)
- fact candidate:
  - resolve `terms` into `(subject_e_ref, rest_terms)`
  - resolve `candidate_ref` from accepted-in-batch map or ledger trace map
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
- `derivation_id`, `derivation_version`, `run_id`
- `candidate_id`, `candidate_key`, `candidate_kind`
- `support_digest`, `support_kind`
- `accepted_by`, `accepted_at`

Entity accept also writes:

- `materialize_kind=entity`
- `entity_type`
- `entity_ref`
- `identity_override_digest` (when override is used)

## 7. Compatibility and Deprecation

Still supported (explicit compatibility path):

- legacy fact payload (`e_ref + rest_terms`)
- legacy record payload (`materialize_as=record`, roles/id_policy shape)

Behavior:

- compatibility paths emit `LegacyAcceptFallbackWarning`
- v2 paths are selected first when `candidate_kind/terms` or v2 entity payload is present

Migration direction:

- produce v2 candidates from builders/evaluate
- avoid constructing legacy payloads directly in tests/callers
- keep no-head derivations as fact-only compatibility path

