# SDK Authoring API (v1)

This folder documents the user-facing SDK style for schema/rule/derivation authoring.

Guiding principle:

- Prefer normal Python objects and operators for common flows (`Rule`, `Derivation`, `vars`, comparisons)
- Keep dict/spec payload APIs available for advanced workflows and tooling compatibility
- Reuse authoring/core compile paths so runtime semantics stay consistent

Quick summary:

- Schema declarations: `Entity`, `Identity`, `Field`
- Rule/Derivation object DSL: `Rule`, `Derivation`, `RuleRef`, `vars(...)`
- Store facade: `SDKStore.run(rule)`, `SDKStore.evaluate(derivation)`, `SDKStore.accept(cands, meta_overrides=...)`
- Registry facade: `SDKRegistry.register_rule(rule)`, `SDKRegistry.register_derivation(derivation)`

Important v1 note (`vars()` runtime limitation):

- Runtime SDK object DSL cannot infer variable names from `with vars() as (p, c):` without AST parsing.
- Use `with vars("p", "c") as (p, c):` (recommended), or `with vars() as V: p, c = V("p", "c")`.
- The string-based Authoring DSL parser still supports `with vars() as (...)` because it parses source AST.

See `/Users/zhenzhili/symbolic_agent/src/factpy_kernel/sdk/docs/rules_and_derivations.md` for examples and support limits.
