# Session Handoff — T3 Cycle Complete

Date: 2026-05-24

## Start Here

- Current branch: `v0.2.0-t3-6-docs-and-examples-2026-05-24`
- Current HEAD before this handoff commit: `217de6e2 docs(memory): consolidate T3.6 archive + T3 cycle complete`
- Sacred branch: `master = 562c74195df43e933bed92a3ff25de94dd8ce666`
- Push state: 0 pushes for the local T1/T2 + T3 cycle work in this session.
- Primary repo memory: `workflow/memory/current.md`

## Preserve These Invariants

- Do not modify `master`.
- Do not stash, restore, reset, or otherwise alter the unrelated dirty set.
- Do not auto-push or auto-merge.
- Do not rewrite T3.1-T3.6 archive pairs or paired branch history.
- Keep the six T3 paired branches plus the T3 audit branch stable unless the user explicitly authorizes a follow-up.

Known dirty set to preserve:

- `docs/references/working/design-points/readme.md`
- `examples/01_sdk_check_diagnose.ipynb`
- `examples/02_overlay_why_not_frontier.ipynb`
- `examples/archive/01_sdk_basics.ipynb`
- untracked `rainbird-ai sdk code/`

## Completed State

T1 and T2 are closed. The initial T3 cycle is complete:

- T3.1 Base RuleExpr + Bool Guards — archived at `a0718e85`
- T3.2 Expression-Scope Occurrence Validation — archived at `21fa0914`
- T3.3 Joins + Every-Proof-Path Reach Rule — archived at `1100ea78`
- T3.4 Join By Ports — archived at `02fcaec6`
- T3.5 RuleExpr Inspect — archived at `12bd9221`
- T3.6 Docs and Examples — archived at `96baa609`

T3 cycle span:

- 52 local commits from track plan sync `9c857d0c` through T3.6 archive `96baa609`.
- Four consecutive 0-deviation T3 feat commits: T3.3, T3.4, T3.5, T3.6.
- Later T3 execution lowering remains deferred per D5 §4.8.

## T3 Cycle Cadence Summary

| Slice | Class | Feat | Deviation |
|---|---|---|---|
| T3.1 | M | `e049c93e` | A-fallback `8de03372` mid-impl reactive |
| T3.2 | S | `2a16dd98` | T-1 `RuleOccurrence.__and__` / `__or__` bundled into feat |
| T3.3 | M | `0b80fe9b` | 0 deviation, first preemptive scope-locking success |
| T3.4 | S | `8f248212` | 0 deviation, second consecutive |
| T3.5 | M | `55d9e67b` | 0 deviation, third consecutive + first proactive Step 4.6 A-fallback catch |
| T3.6 | S docs-only | `f8abaad1` | 0 deviation, fourth consecutive + T3 cycle final |

Validated cadence patterns:

- Preemptive scope locking before implementation.
- Executable-quality algorithm and validation-layer specs in blueprints.
- Sibling module isolation for large read-only projection layers (`rule_expr_inspect.py`).
- Step 4.6 proactive grep catch + pre-feat A-fallback amendment.
- Strict docs-only scope discipline with preservation tests.

Permanent lesson sediment is in:

- `workflow/memory/current.md`
- `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/project_rule_expression_progress.md`
- `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/feedback_audit_to_archive_cadence.md`
- `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/MEMORY.md`

## Shipped T3 Surface

T3 now ships the initial RuleExpr authoring, join, inspect, and docs surface:

- Public SDK exports include `RuleExpr`, `RuleExprError`, `ExplicitBoolError`, `RuleJoinConstraint`, `RuleExprInspect`, `OccurrenceInspect`, `AtomDescriptor`, and `PortInspect`.
- Application protocol methods include `Rule.__and__`, `Rule.__or__`, `Rule.__bool__`, `RulePortRef.eq(...)`, and `RuleOccurrence.__and__` / `__or__`.
- Internal RuleExpr substrate includes `_RuleExpr`, `_RuleOperand`, `_AndGroup`, `_OrGroup`, `.join(...)`, `.join_by_ports(...)`, reach validation, and flatten/merge behavior.
- SDK inspect dispatch is three-way: legacy SDK Rule / Inference dict remains dict-shaped, application Rule coerces to inspect, and RuleExpr returns `RuleExprInspect`.
- User-facing docs now cover staged imports, `.eq(...)`, `&` / `|` precedence, bool guards, same-name ports, and inspect return-shape differences.

## Known Open Issues

- `tests.test_public_inference_factgraph_create` has 4 failures + 1 error at T3.5 G7 baseline; unrelated to T3 RuleExpr work. Root causes noted: `meta[confidence]` removal and missing `sdk.inferences` persistence methods.
- pytest SIGSEGV is still a tooling issue; T3 locked unittest fallback throughout. A spawned investigation task was discussed / queued by context but has not been resolved here.
- T3.5-F6 `value_type="unknown"` sentinel for value ports is documented in T3.6 docs; future T1.4 substrate extension could add real value typing.
- T2.3.b1 / T2.3.e Nit remains: `_lower_compare_with_aggregate` non-aggregate side AttrRef / BinaryExpr handling.

## Next-Track Decision Options

No next-track action has been authorized yet. Fresh session should start by reading `workflow/memory/current.md`, then ask the user which path to take.

Options discussed:

1. T3 later tranche — RuleExpr execution lowering / adapter integration. Predicted L-class; warm T3 context, but cross-adapter complexity.
2. T4 — Head + closed-head. Predicted L-class; independent capability track, possibly clustered with T3 later tranche.
3. T5 — EvaluateResult + Semantics + legacy hard-cut + WhyNot. Largest redesign zone; triggers T1.3 final `Rule` flip.
4. Push gate evaluation — 52 T3-cycle commits remain local; reduces local-only risk but crosses explicit push-policy boundary.
5. Pytest SIGSEGV tooling investigation — independent cleanup, not blocking because unittest gates are reliable.
6. Hybrid — push first, then T3 later / T4; or tooling cleanup before the next L-class cycle.

Measured recommendation at handoff time:

- Pause here and resume in a fresh session.
- Decide between push gate and the next L-class arc with full context budget.
- Apply the T3 cadence pattern to the next large slice: preemptive scope lock, Step 4.6 grep, G7 baseline, implementation, Step 4.7 review, closure, archive, memory consolidation.

