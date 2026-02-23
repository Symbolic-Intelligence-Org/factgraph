# SDK Blueprint Alignment Matrix (v1)

Scope: SDK user-facing API alignment against blueprint usage in `/Users/zhenzhili/symbolic_agent/docs/规则.md` and `/Users/zhenzhili/symbolic_agent/docs/设计.md`.

Status baseline (before v1 alignment work):

- Schema declarations (`Entity` / `Identity` / `Field`): implemented
- Runtime store wrapper (`SDKStore`) for write/export/run: implemented
- Registry wrapper (`SDKRegistry`) over authoring registry: implemented
- Blueprint-style object DSL (`Rule` / `Derivation` / `RuleRef` / `vars()`): missing
- Blueprint-style store APIs (`store.run(rule)` / `store.evaluate(derivation)` / `store.accept(..., meta_overrides=...)`): missing

Compatibility target for this alignment pass:

- Prefer Pythonic object APIs over config dicts for common SDK workflows
- Reuse existing authoring/core compile and execution paths; do not fork semantics
- Keep low-level dict/spec APIs available for advanced users and backward compatibility

Support matrix (target after phases 0-7):

| Capability | Blueprint doc usage | SDK object API | Authoring string DSL parser | Notes |
| --- | --- | --- | --- | --- |
| Schema declarations | `Entity/Identity/Field` | Yes | N/A | Existing SDK feature |
| Rule declaration | `Rule(...)` | Yes (new) | Yes | SDK lowers to authoring payload |
| Derivation declaration | `Derivation(...)` | Yes (new) | Yes | SDK lowers to authoring payload |
| Variables | `with vars() as (...)` | Yes (new) | Yes | SDK version builds typed DSL nodes |
| Rule references | `RuleRef(...)(...)` | Yes (new) | Yes (parser patch) | Parser nested-call support added in Phase 6 |
| Pythonic where compare | `li.country == c` | Yes (new) | Partial | Parser remains intentionally conservative for some sugar |
| Pythonic where arithmetic | `age == (2026 - by)` | Yes (new) | Partial (Phase 6 subset) | SDK object DSL is primary path |
| Store run query | `store.run(R)` | Yes (new) | N/A | Uses compiled `RuleSpec` |
| Store evaluate derivation | `store.evaluate(D)` | Yes (new) | N/A | Lowers derivation then calls core |
| Store accept meta overrides | `store.accept(cands, meta_overrides=...)` | Yes (new) | N/A | Wraps `AcceptOptions` |

Assumptions:

- SDK object DSL is the recommended user path; string DSL remains important for CLI/files but may support a narrower sugar subset in v1.
- Parser parity for every blueprint shorthand is not required if SDK object DSL provides the blueprint-equivalent user experience and docs clearly note parser subset limits.
