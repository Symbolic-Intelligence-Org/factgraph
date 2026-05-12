# Task Blueprint Audit: SDK / Service SemanticsProfile Call-Site

- Blueprint: [2026-05-12_sdk-service-semantics-callsite.md](./2026-05-12_sdk-service-semantics-callsite.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seed starts Track 3 / E after D publish. Source audit covers core profile consumption, SDK evaluate rejection, application protocol shape, SDK shell engine naming, service top-level/derivation-level rejection, and docs state. Open G0 questions cover public keyword (`semantics=` vs `semantics_profile=`), `engine=` vs `mode=`, SDK export, service placement, service profile shape, shell profile flow, application protocol placement, and inspection scope. |
| 2026-05-12 | scoped | Scope frozen | Locked D1-D12. Public SDK/service keyword is `semantics=` while `semantics_profile=` remains core/internal and is publicly rejected. Public SDK evaluation uses `engine=` and hard-rejects `mode=`; core `Store.evaluate(mode=...)` remains internal. SDK exports `SemanticsProfile` and adds `fg.eval.inspect_semantics(profile)`. Service accepts top-level inline `semantics` only. Application protocol adds request-level `semantics_profile`. Shells reject profile kwargs in E with UX trade-off recorded. SDK/service reject unsupported engines and profile/engine mismatch. G2 includes public SDK `mode=` to `engine=` test/doc migration. |
| 2026-05-12 | red+guard | Added G1 baseline | Added `test_sdk_service_semantics_callsite` with 22 tests covering SDK export/inspection, public `engine=` + `semantics=` evaluation for ProbLog and PyReason, SDK hard-reject anchors, application request field, service top-level profile acceptance/rejection, shell profile rejection, and core C/D guards. Expected red baseline confirmed: `Ran 22 tests, FAILED (failures=10, errors=12)`. Existing B+C+D focused suites remain green: `Ran 66 tests, OK`. |

## Decision Notes

- 2026-05-12: E is the final Track 3 integration slice. C and D already proved adapter consumption through core `Store.evaluate(..., mode=..., semantics_profile=...)`; E should expose that capability at SDK/service runtime call-sites without moving profile data back onto `Rule` or `Derivation`.
- 2026-05-12: Draft recommendation is `semantics=` as the public SDK/service keyword, while keeping `semantics_profile=` as core/internal unless G0 intentionally aliases it.
- 2026-05-12: Draft recommendation is `engine=` as the public SDK evaluate selector, matching service and the existing Check/Diagnose/Fact Overlay/Why-not shells. Because the project is pre-release, G0 should consider a hard cut from SDK `mode=` rather than carrying a long-term alias.
- 2026-05-12: Draft recommendation is top-level service `semantics` only. Derivation-level `semantics` should keep rejecting because it would reintroduce engine semantics into the rule/derivation definition body.
- 2026-05-12: G0 chose `semantics=` as the only public SDK/service profile keyword. The application/core field remains `semantics_profile` because that boundary is type-aligned with `SemanticsProfile`; SDK maps the short public keyword to the canonical internal field.
- 2026-05-12: G0 chose a hard public SDK cut from `mode=` to `engine=` for `evaluate(...)` and `evaluate_compiled(...)`. Core `Store.evaluate(mode=...)` remains unchanged because C/D adapter consumption and internal tests already use that name.
- 2026-05-12: G0 chose to export `SemanticsProfile` from `kernel.sdk` because the type becomes part of the public SDK call-site in E. A small `fg.eval.inspect_semantics(profile)` helper is included; service inspection endpoints remain out of scope.
- 2026-05-12: G0 chose top-level service `semantics` as an inline JSON dict and continued to reject derivation-level `semantics` / `semantics_profile`. This preserves the Track 3 rule that runtime engine semantics live at the call-site, not in rule/derivation templates.
- 2026-05-12: G0 intentionally kept Check / Diagnose / Fact Overlay / Why-not shells profile-free in E. This creates a temporary UX asymmetry with `fg.eval.evaluate(..., semantics=...)`, but avoids expanding shell proof/counterfactual protocol semantics in the final Track 3 slice. A future shell-profile slice can address that surface explicitly.
- 2026-05-12: G0 locked strict public rejection for profile use with non-consuming engines (`native`, `souffle`) and for profile/engine mismatch. Silent ignore remains forbidden by the A3/C/D precedent.
- 2026-05-12: G0 locked public rejection text anchors for `mode=`, `semantics_profile=`, unsupported engines, and profile/engine mismatch so G1 tests can prevent soft aliases from reappearing.
