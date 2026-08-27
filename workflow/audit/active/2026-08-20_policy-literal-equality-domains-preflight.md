# Preflight: operator-sensitive Policy literal equality domains

- Status: complete
- Created: 2026-08-20
- Last Updated: 2026-08-20
- Authority: working triage document; surfaces blueprint-vs-shipped drift before scoped anchor per CADENCE Step 4.3. Does not lock implementation; findings feed back into Step 4.4 amendment.
- Inputs:
  - [Implementing blueprint](../../blueprints/active/2026-08-20_policy-literal-equality-domains.md)
  - [Q22 decision](../../design/decisions/active/2026-08-20_q22-policy-literal-equality-domain-decision.md)
  - [Stage 1 audit](./2026-08-20_policy-literal-equality-domain-vs-shipped.md)
  - shipped Policy protocol, SDK authoring, compiler, replay/bundle and Product V2 presentation paths
- Outputs / Downstream:
  - scoped blueprint and paired audit above
- Related:
  - [Q19 decision](../../design/decisions/active/2026-08-14_q19-policy-authoring-sdk-literal-comparison-decision.md)
- Blueprint: [operator-sensitive Policy literal equality domains](../../blueprints/active/2026-08-20_policy-literal-equality-domains.md)
- Branch: `v0.3.0-impl-meander-agent-query-validation-vertical-probe-2026-08-11`

> Preflight is required because this slice changes one public protocol value
> across SDK authoring, compiler, replay/bundle and Explain presentation.

## 1. Preflight scope

The complete Policy protocol and authoring modules plus the compiler's complete
comparison/structure/lineage flow were re-read. Strict V1 operand wire,
generic bundle DTO wire, Product V2 operand presentation, and their focused
tests were re-read as the serialization consumers. Engine equality and ordering
semantic units were rechecked in Native, Souffle and ProbLog.

## 2. 5-bucket findings

### 2.1 Required amendment before scoped

- **PF-R1 — entity endpoint shape:** `_resolve_compare_operand` currently
  accepts Field/Function scalar endpoints only. Entity-reference literal
  support must add an explicit `EntityIdentityEndpoint` branch and must not
  widen relationship fields or scalar metadata.
- **PF-R2 — untrusted encoded reference:** SDK `EntityRef.encoded_ref` is
  intentionally non-authoritative elsewhere. The authoring path must normalize
  identity and recompute the idref through the active `SchemaIndex`.
- **PF-R3 — two authoring ingress forms:** operator-sensitive gating must cover
  both raw Python literals and caller-created `PolicyLiteral`; otherwise an
  explicit string literal could still reach forbidden ordering.
- **PF-R4 — compatibility surface:** `PolicyLiteral` participates in node IDs,
  structure digests, V1 program wire, generic bundle wire and Product V2
  presentation. Existing field names and int/time payloads must remain exact.

### 2.2 Recommended amendment before scoped

- **PF-Rec1 — proof shape:** add positive equality parity for all three new
  domains, negative `ne`/ordering/float tests, and explicit replay/bundle/view
  round trips rather than relying only on generic serializer inspection.

### 2.3 Verified assumptions

- **PF-V1:** compiler ordering is already operator-sensitive and existing
  `CmpAtom` equality lowering is domain-agnostic.
- **PF-V2:** bundle wire already accepts string and bool dataclass fields; no
  new arbitrary JSON or DTO discriminator is required.
- **PF-V3:** existing int/time node identity derives from the unchanged
  `(literal, domain, value)` tuple, so additive domains need not perturb old
  digests.

### 2.4 Scoped-detail items

- **PF-S1:** use a stable compiler error for entity-ref endpoint type mismatch
  and cover it directly.

### 2.5 Abandonment blockers

None.

## 3. Cross-slice contract preservation

| Contract | Verification |
|---|---|
| Q19 canonical/sealed literal identity | Preserve fields and old domain/value canonicalization. |
| Q12 branch-total comparison ownership | No change to `_validate_constraints`. |
| Q21 Function directionality | Function scalar endpoints remain unchanged; no Function/entity-reference widening. |
| Q20 V2-only topology | WeightedChoice/Function markers and profile gates remain unchanged. |
| Shared dirty worktree | No cleanup, branch rewrite, commit or push. |

## 4. Findings summary table

| Bucket | Count | Items |
|---|---:|---|
| Required | 4 | PF-R1–PF-R4 |
| Recommended | 1 | PF-Rec1 |
| Verified | 3 | PF-V1–PF-V3 |
| Scoped-detail | 1 | PF-S1 |
| Abandonment | 0 | — |

## 5. Step 4.4 amendment actions

All findings are incorporated into blueprint §5–§8 and the paired audit
decision notes. No open preflight choice remains.

## 6. Acceptance for this preflight

- [x] All in-scope comparison and serialization paths re-read
- [x] Findings classified into 5 buckets
- [x] Entity endpoint and untrusted encoded-ref findings spot-checked
- [x] No abandonment blocker surfaced
- [x] Cross-slice preservation recorded
