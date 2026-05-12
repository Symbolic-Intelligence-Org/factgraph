# Task Blueprint Audit: SDK / Service SemanticsProfile Call-Site

- Blueprint: [2026-05-12_sdk-service-semantics-callsite.md](./2026-05-12_sdk-service-semantics-callsite.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed starts Track 3 / E after D publish. Source audit covers core profile consumption, SDK evaluate rejection, application protocol shape, SDK shell engine naming, service top-level/derivation-level rejection, and docs state. Open G0 questions cover public keyword (`semantics=` vs `semantics_profile=`), `engine=` vs `mode=`, SDK export, service placement, service profile shape, shell profile flow, application protocol placement, and inspection scope. |

## Decision Notes

- 2026-05-12: E is the final Track 3 integration slice. C and D already proved adapter consumption through core `Store.evaluate(..., mode=..., semantics_profile=...)`; E should expose that capability at SDK/service runtime call-sites without moving profile data back onto `Rule` or `Derivation`.
- 2026-05-12: Draft recommendation is `semantics=` as the public SDK/service keyword, while keeping `semantics_profile=` as core/internal unless G0 intentionally aliases it.
- 2026-05-12: Draft recommendation is `engine=` as the public SDK evaluate selector, matching service and the existing Check/Diagnose/Fact Overlay/Why-not shells. Because the project is pre-release, G0 should consider a hard cut from SDK `mode=` rather than carrying a long-term alias.
- 2026-05-12: Draft recommendation is top-level service `semantics` only. Derivation-level `semantics` should keep rejecting because it would reintroduce engine semantics into the rule/derivation definition body.
