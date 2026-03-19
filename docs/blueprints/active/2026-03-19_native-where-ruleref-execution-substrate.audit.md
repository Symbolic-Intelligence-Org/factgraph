# Task Blueprint Audit: Native Where RuleRef Execution Substrate

- Blueprint: [2026-03-19_native-where-ruleref-execution-substrate.md](./2026-03-19_native-where-ruleref-execution-substrate.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-03-19 | draft | Blueprint created | Opened an implementation-facing draft to turn the earlier derivation-only capability decision into a shared `native where RuleRef execution substrate` discussion, with `query + derivation` as the first-round owners. |
| 2026-03-19 | draft | Code-scan constraints recorded | Captured the concrete landmines found in the code scan: query/runtime registry drop, split execution paths, OR-branch over-capture, single-support candidate plumbing, and missing registry-backed preflight outside the rule runtime path. |
| 2026-03-19 | draft | Review boundary tightened | Added an explicit first-round extraction boundary for shared semantics: target resolution, expose gate, arity validation, and recursion/cycle guard must move first; trace-specific overlay rewrite and child invocation detail stay in `rule_ir` for now. |
| 2026-03-19 | draft | Registry surface narrowed | Froze a first-round injection shape: SDK execution surfaces should use explicit `RuleRegistry`, service derivation should reuse `override_registry_root` / `session.registry_root`, and both must normalize to `RuleRegistry | None` before entering shared substrate. |
| 2026-03-19 | scoped | Scope freeze completed | Scoped freeze confirmed after settling owner, registry injection surface, extraction boundary, branch-winning deferral, single-support boundary, preflight rule, and sequencing with recursive proof work. |
| 2026-03-19 | implemented | Shared substrate landed | Implemented `query + derivation` native `RuleRef` execution through a shared `ruleref_substrate`, threaded explicit registry context through SDK/service surfaces, and reused shared resolution helpers instead of duplicating `rule_ir` logic. |
| 2026-03-19 | implemented | Docs and targeted tests synced | Updated core/sdk/service/authoring module docs to reflect the new runtime boundary, and verified the first-round contract with targeted `unittest` coverage for query, derivation, runtime service, and existing rule-trace regressions. |

## Decision Notes

- 2026-03-19
  - Ownership rule: this capability must not be scoped as `derivation-only`. `Query` already advertises the same where-language surface, so leaving query behind would preserve a second contract drift.
- 2026-03-19
  - Injection rule: `RuleRef` execution requires explicit registry context. A hidden global registry or bottom-layer silent fallback is treated as an anti-pattern.
- 2026-03-19
  - Safety rule: current OR-branch support capture is not safe to reuse blindly for recursive child-proof capture; winning-branch semantics or a narrower first-round capture boundary must be decided before implementation.
- 2026-03-19
  - Scope rule: first-round implementation should stay inside the existing single-support candidate model unless that model is explicitly redesigned in a separate scope change.
- 2026-03-19
  - Extraction rule: first-round shared substrate is not required to absorb all of `rule_ir`. It must cover target resolution, expose gate, arity validation, and recursion/cycle guard; memo may stay simplified, while overlay rewrite, child invocation capture, and `ruleref_links` remain `rule_ir`-specific for now.
- 2026-03-19
  - Branch rule: first-round should prefer the narrower option in §5.5, namely establishing execution substrate first and deferring multi-branch child-proof capture until winning-branch semantics are explicitly designed.
- 2026-03-19
  - Injection shape rule: SDK runtime execution should take `RuleRegistry`, not `SDKRegistry` or filesystem roots. Service runtime should keep its existing root-based DTO surface and resolve that to `RuleRegistry` before execution.
- 2026-03-19
  - Defaulting rule: auto-registration is acceptable only for SDK object-backed `RuleRef(RuleObj)` dependencies. String-based `RuleRef(rule_id, version)` still requires explicit registry input and should fail fast when absent.
- 2026-03-19
  - Freeze rule: the blueprint is now scoped. First-round implementation should target the frozen `query + derivation` shared substrate shape and should not reopen branch-winning semantics, multi-support, or trace-carrier unification without a new scope update.
- 2026-03-19
  - Outcome rule: first-round implementation is complete once `query + derivation` share the same native `RuleRef` execution substrate, explicit registry injection surfaces are wired end to end, and module docs record that support capture still stops at direct `rule_refs` rather than recursive child-proof handles.
