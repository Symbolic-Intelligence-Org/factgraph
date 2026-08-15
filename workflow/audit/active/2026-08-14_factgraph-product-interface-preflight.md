# Preflight: FactGraph product interface

- Status: complete
- Created: 2026-08-14
- Authority: independent source/contract readback of the Q20 draft decision and
  blueprint before implementation scope is anchored.
- Inputs:
  - [Q20 decision](../../design/decisions/active/2026-08-14_q20-factgraph-product-interface-decision.md)
  - [Q20 blueprint](../../blueprints/archive/2026-08-14_factgraph-product-interface.md)
  - Q18/Q19 source and protocol contracts
- Branch: `codex/v0.3.0-impl-factgraph-product-interface-2026-08-14`

## 1. Readback scope

Independent reads covered the existing Policy façade/compiler, Rule semantic
resolution, Scenario V1 resolver/world capture, V1 run/replay/profile, portable
runtime, legacy ProbLog configuration, V0/V1 Explain, generic evidence sources,
and Agent draft/write protocol.

## 2. Findings

| ID | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| PF-1 | Required amendment | A friendly Rule builder cannot return a bare Rule: `.use`/`query` need a resolved bundle and Q19 owner-bound Policy callback handles cannot cross drafts. | Applied in Q20 §4.1 and blueprint §5.1. |
| PF-2 | Required amendment | Descriptor digest alone permits target/metadata splice. | Applied: asset descriptor/binding digest, raw absent state, side-specific candidate capture. |
| PF-3 | Required amendment | WeightedChoice lacked a precise arm/key/probability/engine lowering contract and conflicted with `for_choice` as a second source of weights. | Applied: bounded decimal-string weights, exclusive container/arms, branch-total key, annotated-disjunction lowering; profile only activates/validates. |
| PF-4 | Required amendment | Existing compiler ingress resolves Policy before V1 terminals, so a choice sidecar could otherwise be silently lost. | Applied: choice is V2-only target; legacy/V1 terminals reject before execution. |
| PF-5 | Required amendment | Scenario V1 collapses metadata and cannot carry it through materialization/replay. Operation-specific metadata, baseline capture and merge/conflict rules were unspecified. | Applied in Q20 §4.3: parallel V2, closed provenance grammar, per-member restriction, semantic/evidence lanes. |
| PF-6 | Required amendment | V1 result/run require native canonical output and omit certainty, so a ProbLog-only profile needs a parallel result/run carrier and explicit result-mode boundary. | Applied: EvaluationRunV2, canonical ProbLog frame, rows+certainty only, typed unsupported Native/Soufflé. |
| PF-7 | Required amendment | Profile body/attachments must replay as canonical material and candidate target attachment inheritance was ambiguous. | Applied: V2 canonical profile bytes, closed stable attachment union, side-specific candidate pins, overlap rejection. |
| PF-8 | Required amendment | Explain/source proposal could reclassify generic evidence source metadata or fabricate native evidence for ProbLog. | Applied: closed evidence-support union, sanitized product source view, captured baseline/synthetic distinction, raw-text ban. |
| PF-9 | Required amendment | Agent write currently emits a rejected `confidence` metadata key; it must not become an implicit probability conversion. | Applied: workflow-only confidence, legacy source/idempotency preservation, no generic provenance meta. |

## 3. Verified assumptions

- Q19 owner-bound handles, semantic address-space and Query compiler form a
  reusable identity chain; no second compiler is needed.
- Q18 deterministic portable profile and V1 native Explain are valid, frozen
  foundations but intentionally exclude V2 probability semantics.
- Existing `PolicyRulePin`/lineage can anchor durable profile attachments when
  augmented by target side identity.

## 4. Self-check result

All required amendments PF-1 through PF-9 are represented in Q20 §4 and
blueprint §§5–8. No abandonment blocker was found. The user's explicit
continuous-delivery authorization covers the draft→scoped implementation
transition for this bounded Q20 slice.
