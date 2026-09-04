# Semantic Value Candidates and Revision Guard

- Scope: `factgraph.application.protocol.semantic_candidates`,
  `factgraph.application.semantic_candidate_runtime` and the optional Product
  V2 expected-view guard
- Audience: integrations that must validate a small batch of supplied scalar
  values against one current projected FactGraph view before execution

## Purpose and ownership

FactGraph owns a product-neutral, read-only candidate module. Given explicit
semantic endpoints and typed supplied values, it returns canonical values that
exist in one projected view. It does not know Operations, Policies, Agents,
authorization subjects, caller intent or which candidate a product should use.

The SDK entry point is:

```python
result = graph.resolve_semantic_candidates(request)
```

`request` is `SemanticValueCandidateBatchRequestV1`; callers construct its
items with `SemanticValueCandidateRequestV1`. Each item contains:

- a unique, non-empty `correlation_key` of at most 256 characters;
- an existing `EntityIdentityEndpoint` or `FieldEndpoint`;
- one exactly typed `str`, `int`, `float` or `bool` supplied value;
- matching mode `exact` or `unicode_casefold_v1`;
- `suggestion_limit` from 0 through 5.

One batch contains 1 through 128 items. `unicode_casefold_v1` accepts strings
only. An Entity identity endpoint must have one identity field; a Field endpoint
must name a single-valued scalar field. Composite identities, collections and
unsupported domains fail rather than being approximated.

## Matching and canonical values

FactGraph reads candidate values from `project_view_facts(...)`, so ordinary
projected-view and schema semantics remain authoritative. Results contain
public scalar values only—never entity refs, ledger rows, database keys or
semantic addresses.

For each item:

1. Canonical typed equality is evaluated first. A match is returned in
   `exact_matches`; normalized matching and suggestions remain empty.
2. If exact matching is empty and mode is `unicode_casefold_v1`, strings are
   normalized with outer whitespace removal, Unicode NFC and case folding.
3. Distinct normalized canonical values are returned in deterministic encoded
   value order, with at most five values and `matches_truncated` when more exist.
4. Only when equality matching is empty may normalized-prefix suggestions be
   returned, up to `suggestion_limit`, with `suggestions_truncated` when needed.

Suggestions are not matches and FactGraph never chooses or substitutes one.
Callers define their own closed selection rule. Exact and normalized result
groups expose the value as stored in FactGraph, so a caller can seal that
canonical value rather than the supplied spelling.

## Batch evidence and errors

`SemanticValueCandidateBatchResultV1` binds:

- the exact `request_digest`;
- one `view_snapshot_digest` shared by every item;
- correlation-keyed match/suggestion groups and truncation flags;
- an `evidence_digest` over the request digest, view digest and complete result.

DTO constructors reject malformed shapes with `SemanticCandidateShapeError`.
Runtime failures use `SemanticCandidateRuntimeError.code`, including:

- `VIEW_CHANGED_DURING_CANDIDATE_CAPTURE`;
- `COMPOSITE_IDENTITY_UNSUPPORTED`;
- `SEMANTIC_CANDIDATE_ENDPOINT_UNSUPPORTED`;
- `SEMANTIC_CANDIDATE_TYPE_MISMATCH`.

The runtime computes the projected-view digest immediately before and after the
whole batch capture. A mismatch returns
`VIEW_CHANGED_DURING_CANDIDATE_CAPTURE`; no partial batch is returned.

## Product V2 expected-view guard

`ProductEvaluationInvocationV2` and the SDK Product V2 query builder accept an
optional `expected_view_snapshot_digest`. Before execution-world capture,
FactGraph compares the current view digest with that expected digest. A mismatch
fails with `V2_EXPECTED_VIEW_MISMATCH` before reading the execution world. The
existing post-capture check remains and reports
`V2_VIEW_CHANGED_DURING_CAPTURE` if the view changes during capture.

This protocol provides an optimistic **revision guard**, not shared snapshot
consistency and not a database transaction spanning candidate lookup and later
execution. Callers that need resolution against changed data must create a new
candidate request; they must not relabel old evidence or silently downgrade to
unchecked execution.

## Contract version and stability

`SEMANTIC_CANDIDATE_RESOLVER_CONTRACT_DIGEST_V1` identifies the closed matching
and guard contract. Integrations that freeze resolver behavior should pin and
verify this value before accepting candidate results. Adding matching modes,
value domains, endpoint kinds or different canonicalization requires a new
version/digest rather than adapter inference.
