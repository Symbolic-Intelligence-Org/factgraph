# Task Blueprint Audit: FactGraph first-class Function capability

- Blueprint: [2026-08-15_factgraph-function-capability.md](./2026-08-15_factgraph-function-capability.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-15 | draft | Blueprint created | Peer-only Rule/Function design and bounded first slice recorded. |
| 2026-08-15 | scoped | User authorized direct implementation and testing | Continuous-delivery authorization covers draft-to-scoped transition; preflight findings PF-1 through PF-6 are incorporated. |
| 2026-08-15 | implementation | Product Function authoring and intrinsic Policy topology landed | Symmetric direct/staged asset builders, Rule/Function peer occurrences, typed inputs/output, legacy/V1 fail-closed marker and asset/topology seals added. |
| 2026-08-15 | implementation | Sealed pre-engine execution and replay landed | Per-port binary relations, side-specific materializations, portable Native/Soufflé/ProbLog profile, program/call capture and zero-callback replay added. |
| 2026-08-15 | implementation | Structured Result/Explain and tutorial landed | Function definition/call views are data-first; no EvidenceGraph is fabricated. The Product V2 notebook executes the real three-engine path. |
| 2026-08-15 | verification | Blueprint completed | 776 tests + 182 subtests green; Ruff, mypy, diff-check and fully executed factpy notebook green. |
| 2026-08-15 | implemented | Product Function slice closed | Public SDK, execution, replay, structured Explain, documentation and verification criteria are complete. |
| 2026-08-15 | archived | Blueprint pair archived | Product implementation was independently reverified before worktree integration. |

## Decision Notes

- Rule and Function are fully peer Product assets; Policy is the sole
  composition layer.
- First slice permits one upstream Rule occurrence per Function occurrence and
  one deterministic scalar output. This bounds planner complexity without
  weakening the peer-only architecture.
- Canonical execution is sealed pre-engine relation materialization; native
  engine callbacks are not the semantic authority.
- Existing Q20/V0/V1 paths remain unchanged for Function-free targets.
- The Product Function DTOs live in `sdk/product_authoring.py` beside the
  existing Product Rule/Policy assets, avoiding a circular AssetMeta module;
  this is a file-placement choice only, not a merged semantic type.
- The real ProbLog EDB path rejected a single wide Function predicate. The
  final portable representation is one binary predicate per typed port joined
  by a compiler-reserved call identity; this preserves one logical
  materialization while satisfying all adapters.
- Function calls materialize the complete upstream Rule occurrence relation
  before the final Query's bind/filter. Structured Explain therefore exposes
  the side's full sealed call inventory; product consumers match calls by typed
  inputs/output rather than assuming ordinal row correspondence.
