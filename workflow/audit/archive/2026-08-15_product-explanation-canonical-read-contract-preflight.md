# Preflight: Product Explanation Canonical Read Contract

- Status: complete
- Created: 2026-08-15
- Last Updated: 2026-08-15
- Authority: working triage document; surfaces blueprint-vs-shipped drift
  before scoped implementation. It does not create evidence or change the
  adopted Q-R5 boundary.
- Inputs:
  - [Product Explanation canonical-read blueprint](../../blueprints/archive/2026-08-15_product-explanation-canonical-read-contract.md)
  - adopted Q-R5 CompletedRunRecord/data-first Explain boundary (external
    Meander design input, not shipped by this FactGraph slice)
  - shipped Product Result/Explain sources re-read on 2026-08-15
- Outputs / Downstream:
  - strict Product DTO wire allowlist and read-projection digest boundary
- Related:
  - [Q20 Product interface decision](../../design/decisions/active/2026-08-14_q20-factgraph-product-interface-decision.md)
- Blueprint: [2026-08-15_product-explanation-canonical-read-contract.md](../../blueprints/archive/2026-08-15_product-explanation-canonical-read-contract.md)
- Branch: `v0.3.0-impl-meander-agent-query-validation-vertical-probe-2026-08-11`

> This preflight was voluntary for a narrowly additive public read-projection
> slice. It stayed on the already active non-sacred shared implementation
> branch to avoid moving concurrent R3a work; that branch-layout deviation is
> recorded in the consuming blueprint outcome.

## 1. Preflight scope

The following shipped sources were re-read before scoping:

- `src/factgraph/application/product_explanation_data_v2.py`
- `src/factgraph/application/product_result_views_v2.py`
- `src/factgraph/sdk/product_evaluation_outcome.py`
- `tests/application/test_product_views_v2.py`
- `tests/sdk/test_product_evaluation_outcome_v2.py`
- `src/factgraph/application/docs/product_result_explain_v2.md`

Baseline focused verification was green: `12 passed` for the Product
application and SDK outcome facade tests.

## 2. 5-bucket findings

| ID | Classification | Finding | Required disposition |
| --- | --- | --- | --- |
| PF-1 | Required amendment before scoped | A generic dataclass serializer would accept attacker-injected rich dataclasses after hostile mutation. | Accept only the two Product presentation modules plus the exact nested `GoalTechnicalAssessmentV1` DTO; reject every other rich object. |
| PF-2 | Required amendment before scoped | `content_digest` could be mistaken for a run seal or authentication token. | Define it only as SHA-256 over the canonical Product read projection and document that it grants no run/source/user authenticity. |
| PF-3 | Recommended amendment before scoped | A JSON-safe result must not leak tuples or `MappingProxyType`, and returning internal containers would weaken immutability. | `to_dict()` returns detached ordinary dict/list/scalar values and strict JSON encoding uses `allow_nan=False`. |
| PF-4 | Recommended amendment before scoped | Embedding `content_digest` inside the bytes it hashes creates a recursive or ambiguous identity. | Keep digest outside `to_dict()`; expose it as a property over the exact `to_canonical_bytes()` result. |
| PF-5 | Verified assumption | Existing `EvidenceSupportViewV2` already enforces graph-bearing states versus reason-bearing graphless states. | Serialize the existing closed state unchanged; do not invent another availability union. |
| PF-6 | Verified assumption | Product V2 Explain already exposes Scenario provenance, probability materialization, choice and Function captures even when graph is unavailable. | The strict projector must preserve all these captured sections. |
| PF-7 | Verified assumption | R3a's identity-only anchor implementation does not need to change for this slice. | Do not edit `evaluate_result.py`, anchor/runtime execution, Store, or Query execution bridge files. |
| PF-8 | Scoped-detail item | A graph-available example cannot honestly use the currently graph-unavailable Product V2 Native/ProbLog adapter. | Demonstrate a sealed V1 detached-Native Product adapter for graph-present and a sealed V2 observation for graph-unavailable. |

### 2.1 Required amendment before scoped

- PF-1 and PF-2.

### 2.2 Recommended amendment before scoped

- PF-3 and PF-4.

### 2.3 Verified assumptions

- PF-5, PF-6 and PF-7.

### 2.4 Scoped-detail items

- PF-8.

### 2.5 Abandonment blockers

- None.

## 3. Cross-slice contract preservation

- Existing V0/V1/V2 run and result DTOs remain unchanged.
- Existing Product facade types and renderer behavior remain compatible.
- R3a identity-only anchors and execution paths remain outside the diff.
- EvidenceGraph remains a sanitized logical projection, not a source database.

## 4. Findings summary table

| Bucket | Count | Items |
| --- | --- | --- |
| Required | 2 | PF-1, PF-2 |
| Recommended | 2 | PF-3, PF-4 |
| Verified | 3 | PF-5, PF-6, PF-7 |
| Scoped-detail | 1 | PF-8 |
| Abandonment | 0 | — |

## 5. Recommended Step 4.4 amendment actions

- Restrict projection to field-validated Product DTOs and the exact nested
  technical-assessment DTO.
- Define `content_digest` as read-projection identity only and keep it outside
  the bytes it hashes.
- Require detached standard JSON containers and strict finite numbers.
- Use two real examples rather than claiming V2 evidence that is not captured.

## 6. Acceptance for this preflight

- [x] All blueprint-referenced shipped state re-read
- [x] Findings classified into five buckets
- [x] Critical serializer and availability findings spot-checked
- [x] No abandonment blocker surfaced
- [x] Cross-slice contracts preserved

### Spot checks

1. `EvidenceSupportViewV2.__post_init__` rejects graphless available states and
   rejects graphs on unavailable states; therefore `graph=None` is not the
   availability authority.
2. `EvaluationExplanationDataV2` and
   `EvaluationRunV2ExplanationDataV2` already contain the desired data-first
   sections and renderer methods; an additive serializer is sufficient.
3. `ExecutionViewV2` contains a nested `GoalTechnicalAssessmentV1`, while the
   remaining reachable structured payload is composed of Product read DTOs,
   primitives, tuples and mappings.  This defines the narrow serializer
   allowlist.

### Conclusion

No abandonment blocker remains.  PF-1 through PF-4 must be reflected in the
scoped implementation; PF-5 through PF-8 confirm the planned boundary.
