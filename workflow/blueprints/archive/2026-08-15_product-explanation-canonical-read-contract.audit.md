# Task Blueprint Audit: Product Explanation Canonical Read Contract

- Blueprint: [2026-08-15_product-explanation-canonical-read-contract.md](./2026-08-15_product-explanation-canonical-read-contract.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-15 | draft | Blueprint created | Reuses adopted Q-R5 and the shipped Q20 Product V2 facade; scope excludes the active R3a core path. |
| 2026-08-15 | preflight | Independent shipped-source preflight completed | PF-1 through PF-8 close the serializer allowlist, digest meaning, detached JSON shape, and real graph-present/graph-unavailable examples. |
| 2026-08-15 | scoped | Preflight amendments and self-check passed | PF-1 through PF-4 were folded into the blueprint; PF-5 through PF-8 verify the implementation boundary. |
| 2026-08-15 | implementing | User authorized implementation | Additive Product Explain serialization begins without touching R3a core files. |
| 2026-08-15 | implemented | Canonical Product Explain read contract landed | Both facade variants expose strict JSON-safe projection/bytes/digest; graph-present and graph-unavailable paths, Function capture, docs and executed notebook are verified. |
| 2026-08-15 | archived | Blueprint closure archived | Blueprint, paired audit and standalone preflight moved to their archive locations after module docs, executable example and verification were completed. |
| 2026-08-16 | post-archive integration correction | Clean-target acceptance found PF-1 was not actually enforced | The delivered module-name predicate admitted spoofed dataclasses and runtime annotation evaluation. The feature target replaces it with the exact reachable DTO identity closure, JSON-only dynamic values, bounded cycle-safe traversal, reserved-envelope checks, and adversarial regressions. This appends the finding; it does not rewrite the 2026-08-15 preflight history. |

## Decision Notes

- Keep FactGraph's existing `EvaluationExplanationDataV2` and
  `EvaluationRunV2ExplanationDataV2`; do not introduce a version-inverted
  generic `ExplanationDataV1`.
- The canonical contract is a typed Product DTO plus a deterministic wire
  projection. `to_dict()` is the JSON-safe accessor, not an unversioned bag of
  arbitrary fields.
- Meander owns the later `ExplanationReadModelV1` business join and source
  redaction layer.
- Evidence availability remains typed and independent from graph presence.
- R3a identity-only anchors are not Product V2 runs and are outside this
  implementation slice.
- The serializer allowlist contains Product read DTO modules and the exact
  nested `GoalTechnicalAssessmentV1`; arbitrary dataclasses fail closed.
- Post-archive integration correction (2026-08-16): the preceding module-level
  wording was insufficient as an implementation gate. The target uses exact
  concrete DTO identities derived from the two facade annotations, resolves
  only those hints at import time, and never admits a runtime-selected
  dataclass through an `Any`/`object` value.
- `content_digest` is the digest of canonical read-projection bytes only and
  is not embedded recursively in that projection.
