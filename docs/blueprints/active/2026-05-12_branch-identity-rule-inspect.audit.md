# Task Blueprint Audit: Branch Identity, Rule Inspect, And Single-Head Cleanup

- Blueprint: [2026-05-12_branch-identity-rule-inspect.md](./2026-05-12_branch-identity-rule-inspect.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-12 | draft | Blueprint created | Draft seeded after Track 3 completion and post-Track-3 semantics API direction note. Source audit found `Branch` has no identity, SDK/authoring lowering erases Branch wrapper metadata, public multi-head is a SDK expansion convenience while capability shells already reject multi-head, and PyReason branch compilation already emits per-branch rule names. |
| 2026-05-12 | scoped | G0 scope-freeze locked | Locked D1-D10: `Branch([...], id=...)` optional keyword-only identity, fallback `b{idx}` inspect ids, Python-identifier id regex, pure `fg.rules.inspect(rule_or_derivation)` return shape, P1a inspect-only metadata, public multi-head hard-cut at construction plus register/evaluate boundaries, positional-only `condition_weights`, unchanged authoring payloads, Rule+Derivation inspect support, and release docs migration from multi-head accepted to single-head required. |

## Decision Notes

- 2026-05-12 (draft): This blueprint is intentionally draft-only. It records the branch identity / inspect / single-head problem created by the next public semantics simplification, but does not yet choose syntax, metadata persistence, or enforcement scope.
- 2026-05-12 (draft): The source audit confirms branch identity cannot be treated as a trivial field add. Current lowering paths erase wrapper metadata in SDK object lowering, authoring DSL parse, and store payload construction. G0 must decide whether identity is inspect-only or carried through authoring/compiled structures.
- 2026-05-12 (draft): Single-head cleanup is included because PyReason branch-bound public semantics become simpler when `head_bound` has one target. Existing capability shells already enforce single-head, while public register/evaluate docs still advertise multi-head acceptance.
- 2026-05-12 (G0): P1a inspect-only metadata is deliberately narrow. Track 2 can resolve public branch ids to positional branch indexes at the SDK boundary before constructing internal semantics/profile shapes; Track 1 does not need authoring payload, rule IR, compiled plan, registry, or adapter propagation.
- 2026-05-12 (G0): Public multi-head is hard-cut with defense in depth because the current implementation already expands SDK multi-head before authoring compile and all capability shells require single-head plans. The cut removes stale public surface rather than removing an actually supported shell capability.
- 2026-05-12 (G0): `condition_weights` remains positional (`b0.a0`) because A4 retained it as certainty/explain projection input. Branch identity should not become an implicit certainty key migration in Track 1.
