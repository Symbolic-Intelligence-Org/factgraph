# Task Blueprint Audit: FactGraph final Query / Scenario closure

- Blueprint: [2026-08-14_factgraph-final-closure.md](./2026-08-14_factgraph-final-closure.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-08-14 | draft | Compact final-closure blueprint created | Q18 provides the four matrices and explicit rejected/Meander-owned cells. |
| 2026-08-14 | scoped | User delegated bounded continuous execution | The final closure contract is the sole scope authority; internal stages do not need separate user pauses. |
| 2026-08-14 | implemented | Q18 V1 closure verified | Parallel protocols/runtime/SDK surface delivered; final verification and independent adversarial review are recorded in the paired final report. |
| 2026-08-14 | verification correction | Inherited formatter debt recorded | `sdk/store.py` fails formatter at both baseline and closure; this slice changes only its V1 docstring, so the final report narrows its formatter claim rather than formatting an unrelated legacy file. |
| 2026-08-14 | verification reopening | Contract audit found a P1 Explain gap | Existing V1 Explain exposes only captured Policy structure / Scenario operations, not the native EvidenceGraph or Policy `HOLDS`/`FAILS`/`NOT_REACHED` projection required by Q18. The blueprint returns to `implementing` until a sealed detached native-evidence overlay and its adversarial verification land. |
| 2026-08-14 | contract correction | Provider wording narrowed to implemented semantics | `RelationProviderV1` is a typed pre-engine relation input attached to a Rule/Policy target. A bare provider has no projection/head/address-space contract; composite `ProviderQueryTargetV1(base, provider)` is the supported Query identity. |
| 2026-08-14 | verification closure | Explain P1 remediated and independently reverified | V1 now seals a restricted native Explain context, revalidates it against the program/target/world pins, and recomputes a positive-row EvidenceGraph plus Policy `HOLDS`/`FAILS`/`NOT_REACHED` projection against captured data only. The final application/SDK corpus passed 687 tests and 175 subtests; independent adversarial review was CLEAR. |
| 2026-08-14 | portable-parity correction | Soufflé occurrence identity repaired | A final cross-entity `PolicyFieldNavigation` / `PolicyCompare` probe found same-predicate witnesses being collapsed before Soufflé support-binding reconstruction. The adapter now retains predicate-occurrence identity until reconstruction is complete; real Native/Soufflé/ProbLog parity passes, and the repeat corpus passed 688 tests and 175 subtests. |

## Decision Notes

- Preserve all F3--F5 v0 artifacts as compatibility contracts. New semantics
  require new v1 protocols rather than field additions to historical seals.
- Portable execution is a deliberately positive deterministic profile with
  result parity, not a claim of universal engine or proof equivalence.
- Q17's observation supports rejecting implicit portable NAF; it does not
  authorize public negative facts or closure policy.
- Any capability that cannot be implemented exactly will be recorded as a
  Q18-consistent explicit rejection in the final matrix, never silently left
  as an accidental gap.
