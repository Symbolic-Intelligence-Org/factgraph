# Task Blueprint Audit: FactGraph Policy authoring SDK

- Blueprint: [2026-08-14_factgraph-policy-authoring-sdk.md](./2026-08-14_factgraph-policy-authoring-sdk.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-14 | draft | Blueprint and paired audit created | Q19 is adopted from explicit user direction; implementation waits for scope self-check. |
| 2026-08-14 | scoped | Scope self-check completed | The façade is additive; Q12 is superseded only for canonical `int`/`time` literal operands. No registry, second evaluator, host-language Boolean syntax or native fallback enters scope. |
| 2026-08-14 | implementing | Core and façade implementation started | Literal IR/codec/compiler work and the SDK façade run in parallel but converge on the existing Policy/Query compiler path. |
| 2026-08-14 | implementing | Independent review found owner-loss at Query boundary | A façade port from another draft with the same alias could have been lowered to a structural address before ownership validation. The builder now carries the authored target's opaque owner and rejects cross-draft bind/select with `POLICY_CROSS_DRAFT_HANDLE`; regression added. |
| 2026-08-14 | implementing | Literal and host-language closure hardened | Explicit literal-domain mismatch, symbolic hash use, field-navigation bind, and real three-engine `time` literal regressions now reject or verify permanently. |
| 2026-08-14 | implemented | Final verification and documentation complete | Full application/SDK/export cohort: 706 passed + 175 subtests; notebook executed; changed-code Ruff, targeted mypy and diff check clean; two independent reviews returned CLEAR with no remaining P0/P1/P2. |
| 2026-08-14 | archived | Blueprint/audits archived together | Current behavior is now carried by SDK/application docs and Q19; this blueprint remains historical implementation rationale. |

## Decision Notes

- The façade must compile to the existing typed Policy and Query path; it is not
  an alternate evaluator or Policy registry.
- Q12's literal restriction is the sole intentional semantic expansion. It
  requires protocol-to-Explain-to-portable conformance, not frontend sugar.
- Explicit `draft.all` / `draft.any` are retained because authored topology is
  part of Explain; Python `and` / `or` are rejected rather than approximated.
- Literal support is deliberately narrower than generic scalar values: only
  signed-64-bit `int` / `time` values share the shipped native and portable
  comparison substrate in this slice.
- `AuthoredPolicyTargetV1` retains an in-process owner capability solely to
  prevent same-alias handles from another draft being silently lowered into a
  different Query; it is not a registry or a persistent identity.
