# D09 native absence/closure observation probe

This directory is a disposable, native-only diagnostic fixture. It is **not** a
FactGraph public API, Scenario operation, Query form, closure policy, or
negative-fact model.

Run it from the repository root with the pinned test environment:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /Users/zhenzhili/miniforge3/envs/factpy/bin/python -B \
  tools/spikes/d09_native_absence_closure/probe.py --verify
```

The matrix uses the current correlated native condition:

```text
Person:exists(person) AND NOT person:age(person, value)
```

| Cell | Mechanism observed | Native match counts | It does **not** establish |
| --- | --- | --- | --- |
| O1 | one visible `age` row | `0` | `age` is logically false when absent |
| O2 | no `age` row | `1` | a closed-world truth claim |
| O3 | `RemoveFact` removes one sole projected row | `0 → 1` | a public `WITHOUT_FIELD` operation |
| O4 | one of two multi-value rows is removed | `0 → 0` | field-level absence or multivalue Scenario semantics |
| O5 | premise exclusion hides a positive row | `0 → 1` | source authority, factual absence, or masking semantics |
| O6 | ordinary `not_age=True` alongside `age=35` | `0`, positive query `1` | explicit negative-fact semantics |
| O7 | `ReplaceFact(35 → 22)` | `0 → 0` | replace and absence are interchangeable |

The only allowed conclusion is that current native NAF uses the relation made
visible to that evaluation. When O2, O3, and O5 yield the same binding, that
does not make their provenance, authorization, missingness, or world-state
meaning equal.

The governing boundary is [Q17](../../../workflow/design/decisions/active/2026-08-13_q17-d09-native-absence-closure-observation-decision.md).
A future public D09 design must separately decide closure ownership,
`MISSING`/`MASKED`/`NEGATED`/`UNKNOWN` states, Explain disclosure, source
admission order, conflict rules, and cross-engine behavior.
