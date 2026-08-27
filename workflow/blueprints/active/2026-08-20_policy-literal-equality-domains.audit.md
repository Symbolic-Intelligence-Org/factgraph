# Task Blueprint Audit: operator-sensitive Policy literal equality domains

- Blueprint: [2026-08-20_policy-literal-equality-domains.md](./2026-08-20_policy-literal-equality-domains.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-20 | draft | Blueprint created | Q22 implementation scope recorded; unrelated dirty worktree preserved. |
| 2026-08-20 | preflight | Required cross-module preflight completed | PF-R1 through PF-R4 and PF-Rec1 folded into the blueprint. |
| 2026-08-20 | scoped | User authorized execution | The request to execute the repair authorizes the bounded Q22 implementation; no float/UUID/bytes or relationship expansion. |
| 2026-08-20 | implementing | Protocol, authoring and compiler gates changed | Added operator-sensitive literals plus explicit trusted-schema entity-reference resolution; no DTO field or lowering shape changed. |
| 2026-08-20 | verification | Cross-engine and codec coverage passed | 82 focused tests and 34 subtests passed, including real Native/Souffle/ProbLog `eq`/`ne` parity; Ruff and targeted mypy checks passed. |
| 2026-08-20 | regression | Application and SDK suites passed | 779 tests and 877 subtests passed after canonical raw entity-ref token validation was tightened. |
| 2026-08-20 | implemented | Docs and decision surfaces synchronized | Application, SDK and quickstart docs now report the shipped matrix; float64/UUID/bytes remain outside it. |
| 2026-08-27 | migration verification | Q22 focused suite re-run before canonical-base replay | 94 passed, 14 skipped and 31 subtests passed. One parity assertion was capability-blocked because the current Pixi environment has no `problog` package: Native and Soufflé succeeded while the ProbLog frame returned `PORTABLE_ENGINE_UNAVAILABLE`. This is an environment gap, not a Q22 semantic failure; the three-engine gate remains required after replay onto `26a88c` in a complete engine environment. |

## Decision Notes

- PF-R1: entity identity remains an explicit `EntityIdentityEndpoint` path and
  is never reclassified as scalar.
- PF-R2: SDK recomputes entity references from identity using trusted schema;
  caller `encoded_ref` is ignored.
- PF-R3: operator gating applies both inferred Python values and explicit
  `PolicyLiteral` values.
- PF-R4: all DTO field names and old int/time canonical payloads remain stable.
- PF-Rec1: parity covers positive `eq` plus `ne`/ordering/float negative paths;
  replay/bundle/presentation round trips are explicit acceptance gates.
