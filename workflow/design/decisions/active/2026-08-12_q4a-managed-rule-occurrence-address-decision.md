# Q4A Decision: Managed Rule occurrence and semantic address

- Status: adopted
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: design constraint; locks the smallest authored occurrence/address substrate before any Policy AST or compiler work.
- Inputs:
  - 2026-08-12 user instruction to continue from the completed F1-lite slice on a new isolated branch
  - [`2026-08-12_q3a-semantic-port-minimum-contract-decision.md`](./2026-08-12_q3a-semantic-port-minimum-contract-decision.md)
  - [`2026-08-12_factgraph-semantic-port-foundation-lite.md`](../../../blueprints/archive/2026-08-12_factgraph-semantic-port-foundation-lite.md)
  - [`2026-08-11_meander-factgraph-post-probe-session.md`](../../../memory/session_handoffs/2026-08-11_meander-factgraph-post-probe-session.md) §§3.2, 8.2, 10
  - [`meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md`](../../design-points/active/meander-factgraph-unified-design-review-candidate-v0-1-1.zh.md) §§6.2–6.3; non-authoritative target direction only
- Outputs / Downstream:
  - [`2026-08-12_factgraph-managed-occurrence-address.md`](../../../blueprints/active/2026-08-12_factgraph-managed-occurrence-address.md)
- Related:
  - [`2026-08-11_q2-meander-agent-query-validation-vertical-probe-decision.md`](./2026-08-11_q2-meander-agent-query-validation-vertical-probe-decision.md) §§4.5, 5
- Branch: `codex/v0.3.0-f2a-policy-occurrence-address-2026-08-12`
- Depends on: Q3A

## 1. Inputs

F1-lite established a resolved binding between every managed Rule port, its
exact Rule `Var`, and one Ontology endpoint. The next product requirement is a
stable authored address such as `pair.person1`, where `pair` identifies one use
of a reusable Rule and `person1` identifies one public semantic port.

Most occurrence mechanics already ship: `Rule.as_(...)`, `RuleOccurrence`,
`RulePortRef`, alias uniqueness in `RuleExpr`, and alias-local execution Vars in
lowering. Reimplementing those mechanics inside a new Policy layer would add a
second truth source. Conversely, a raw `RulePortRef` is not a sufficient public
semantic address because it does not carry the resolved endpoint or semantic
contract identity.

The vertical probe left SC-01 (`join × Any`) and authored-to-lowered lineage
only partially resolved. This decision therefore separates the low-risk address
substrate from the higher-risk Policy compiler.

## 2. Scope

This decision locks:

- one managed occurrence formed from a `ResolvedRuleBundle` and an authored
  occurrence alias;
- one canonical structured address `(occurrence_alias, port_name)`;
- one resolved semantic port reference combining that address, the existing
  execution `RulePortRef`, the Ontology endpoint, and semantic-contract digest;
- one immutable occurrence address space with alias uniqueness, deterministic
  identity, typed resolution failures, and lightweight stale-contract checks.

## 3. Non-scope

- Policy id/version, Policy AST, `All`, `Any`, comparison, unification or join.
- RuleExpr/lowering changes, authored-to-lowered lineage, DNF behavior or
  branch identity.
- Field navigation such as `pair.person1.age`; F2A addresses direct Rule ports
  only. Navigation requires Policy-owned lookup/materialization and grants.
- Synthetic heads, Query, `bind`, `select`, `expect`, Evaluate or Explain.
- SDK dotted-string parsing or `endpoint=Person` sugar.
- Persistence, codec, registry, Package, Plan, Meander or Agent contracts.

## 4. Decision

### 4.1 Reuse the shipped occurrence identity

A managed occurrence wraps the existing `RuleOccurrence` and the exact
`ResolvedRuleContract`. Alias syntax and execution port references continue to
come from `Rule.as_(...)` and `RuleOccurrence.port(...)`; no parallel alias or
Var implementation is introduced.

Construction and every later resolution verify that the occurrence's Rule
still exactly matches the contract's Rule id, version, content digest and port
Vars. A resolved reference is always generated from the address space's own
occurrence and contract; callers cannot supply a `RulePortRef` to be decorated
with unrelated semantic metadata.

The same resolved Rule may appear more than once under different aliases. Those
occurrences share a semantic contract but have distinct public addresses and
remain distinct execution occurrences. No equality or join is inferred.

### 4.2 Use a structured canonical address

The canonical address is:

```python
SemanticPortAddress(occurrence_alias="pair", port_name="person1")
```

It is structurally two strings, not a parsed dotted string. Existing Rule port
names are only constrained to be non-empty and may contain a dot, so treating
`"pair.person1"` as canonical would be ambiguous. A future SDK/UI may render or
accept dotted syntax only after defining an identifier/escaping contract.

Lowered aliases such as branch-copy names never become authored addresses.

### 4.3 Resolve addresses without inventing semantics

Resolution returns a value containing:

- the canonical authored address;
- the existing exact `RulePortRef` used by RuleExpr execution;
- the F1-lite Ontology endpoint;
- the exact `semantic_contract_digest`.

That resolved value is a runtime-private carrier rather than a publicly
constructible protocol DTO. Only the canonical address is public input to the
resolver; this avoids presenting shape validation as proof that a caller-built
endpoint/digest pairing is authentic.

Resolution does not navigate fields, materialize predicates, compare values or
modify the Rule. Unknown aliases and unknown ports fail with distinct typed
errors. A legacy Rule without a resolved semantic contract cannot enter this
managed address space, while its existing RuleExpr behavior remains unchanged.

### 4.4 Freeze one address-space identity

The address space copies the input collection, rejects aliases duplicated by
string value equality across the whole space, and freezes occurrences sorted by
authored alias. Its digest is caller-inaccessible and derived from a typed,
versioned canonical payload containing a format tag and, for each occurrence,
the alias, Rule id/version/content digest and semantic-contract digest. Input
order and later mutation of the caller collection do not change the space or
digest; renaming an alias does. Endpoint details are not duplicated because the
semantic-contract digest already commits to them.

This is an in-process authored-address identity, not yet a Policy digest,
authorization credential, persistence format or compatibility promise.

### 4.5 Keep stale checks lightweight

Building an occurrence and resolving an address reuses F1-lite's exact Rule ↔
contract staleness check. No Schema reconstruction, deep AST audit or external
contract verification is added.

Address resolution requires the authored alias to identify exactly one stored
occurrence and the port to exist in both that occurrence's Rule and semantic
contract with the same Var. Unknown alias and unknown port are separate typed
failures. The resulting reference contains only the address, internally derived
`RulePortRef`, endpoint and semantic-contract digest; it does not duplicate
Rule or Schema records.

## 5. Rejected Alternatives

### Option A: Implement complete Policy AST and compiler now

- **Why rejected**: SC-01 remains unresolved and current RuleExpr lowering
  cannot be treated as the intended Policy semantics. It would also combine
  address identity, Boolean grammar, lineage and execution in one slice.

### Option B: Expose `RulePortRef` directly as the Policy address

- **Why rejected**: it lacks the Ontology endpoint and semantic-contract
  identity and may be confused with compiler-private execution coordinates.

### Option C: Make dotted strings canonical

- **Why rejected**: current public port-name validation permits dots, making
  split-on-dot parsing ambiguous and unsafe as a durable contract.

## 6. Supporting Evidence

- `src/factgraph/application/protocol/rule.py`: shipped Rule occurrence, alias
  validation and port-reference behavior.
- `src/factgraph/application/protocol/rule_expr.py`: shipped expression-scope
  alias uniqueness and explicit join semantics.
- `src/factgraph/application/protocol/rule_expr_lowering.py`: existing
  alias-local execution variables and branch-copy aliases.
- `src/factgraph/application/protocol/semantic_port.py` and
  `src/factgraph/application/semantic_port_runtime.py`: F1-lite exact semantic
  contract and staleness check.
- Vertical-probe final disposition: SC-01 and authored-node lineage remain
  `PARTIAL / UNRESOLVED`; the experiment does not adopt a production compiler.

## 7. Consequences

### 7.1 Downstream unblocking

F2B can compose managed occurrences without inventing its own alias, semantic
port or contract identity. F3 Query work can later refer to the same structured
address type.

### 7.2 Required follow-up actions

Before F2B implements `Policy/All/Any/Unify/Compare`, a separate decision must:

- choose or explicitly exclude asymmetric `join × Any` semantics;
- define managed Rule body capability admission;
- require total authored-to-lowered lineage;
- assign DNF-limit and synthetic namespace failures to a stage/owner.

## 8. Acceptance Criteria

- [ ] Same Rule under two aliases yields distinct addresses and one shared
      semantic-contract identity without implicit equality.
- [ ] Canonical resolution returns the Rule-owned Var, exact endpoint and
      semantic-contract digest.
- [ ] Duplicate aliases and unknown alias/port fail with typed errors.
- [ ] Occurrence/contract mismatch and caller-side collection mutation cannot
      splice or alter resolved identity.
- [ ] Address-space digest is input-order stable and alias-sensitive.
- [ ] Legacy Rule/RuleExpr behavior is unchanged.
- [ ] No Policy AST, lowering, Query, Evaluate, Explain or SDK surface is added.
- [ ] Added production Python lines relative to `8e480daf` stay at or below 350.

## 9. Decision Record

| Date | Stage | Event | Notes |
|---|---|---|---|
| 2026-08-12 | proposed | F2 source review completed | Three independent reviews found that shipped occurrence mechanics should be reused and full Policy compilation is premature. |
| 2026-08-12 | adopted | User authorized the next bounded implementation | Scope narrowed to F2A occurrence/address substrate; F2B remains separately gated. |
| 2026-08-12 | adopted | Independent contract amendments incorporated | Exact occurrence/contract consistency, internally derived refs, copy/freeze identity and unique typed resolution were added before scoping. |
| 2026-08-12 | adopted | Implementation trust boundary clarified | Independent review found a public resolved DTO could be forged structurally; the verified carrier was made runtime-private rather than adding a heavier construction-token mechanism. |
