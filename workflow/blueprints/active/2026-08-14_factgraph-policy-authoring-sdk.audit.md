# Task Blueprint Audit: FactGraph Policy authoring SDK

- Blueprint: [2026-08-14_factgraph-policy-authoring-sdk.md](./2026-08-14_factgraph-policy-authoring-sdk.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-14 | draft | Blueprint and paired audit created | Q19 is adopted from explicit user direction; implementation waits for scope self-check. |
| 2026-08-14 | scoped | Scope self-check completed | The façade is additive; Q12 is superseded only for canonical `int`/`time` literal operands. No registry, second evaluator, host-language Boolean syntax or native fallback enters scope. |

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
