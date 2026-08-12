# Task Blueprint: FactGraph managed occurrence address

- Status: draft
- Created: 2026-08-12
- Last Updated: 2026-08-12
- Authority: task-scoped implementation contract for F2A only.
- Inputs:
  - [`2026-08-12_q4a-managed-rule-occurrence-address-decision.md`](../../design/decisions/active/2026-08-12_q4a-managed-rule-occurrence-address-decision.md)
  - [`2026-08-12_q3a-semantic-port-minimum-contract-decision.md`](../../design/decisions/active/2026-08-12_q3a-semantic-port-minimum-contract-decision.md)
- Outputs / Downstream:
  - Application-layer managed occurrence/address values, focused tests and current-truth docs
- Related:
  - [`2026-08-12_factgraph-managed-occurrence-address.audit.md`](./2026-08-12_factgraph-managed-occurrence-address.audit.md)
- Related Modules:
  - `src/factgraph/application/protocol/`
  - `src/factgraph/application/`
- Related Docs:
  - `src/factgraph/application/docs/rule.md`
- Audit Log:
  - [`2026-08-12_factgraph-managed-occurrence-address.audit.md`](./2026-08-12_factgraph-managed-occurrence-address.audit.md)
- Branch: `codex/v0.3.0-f2a-policy-occurrence-address-2026-08-12`
- Base: `8e480daf`

## 1. Problem

F1-lite resolves a Rule's semantic ports, but no value yet combines that
contract with one authored Rule occurrence. Future Policy and Query layers need
stable direct-port addresses without treating lowered aliases or raw
`RulePortRef` values as the public semantic contract.

## 2. Goals

- Bind an F1-lite `ResolvedRuleBundle` to the shipped authored occurrence alias.
- Represent canonical direct-port addresses structurally.
- Resolve an address to the exact execution ref, endpoint and semantic digest.
- Freeze an alias-unique, order-stable semantic address space.
- Preserve the complete shipped Rule/RuleExpr/evaluate/Explain path.

## 3. Non-goals

- Policy AST/compiler, Boolean operators, comparison or unification.
- RuleExpr/lowering or Explain changes.
- Field navigation, synthetic projection head or Query semantics.
- SDK/public dotted-path grammar, service wire or persistence.
- Package, Plan, Meander, Agent or authorization behavior.

## 4. Current Context

- `Rule.as_()` already validates aliases and creates `RuleOccurrence`.
- `RuleOccurrence.port()` already creates the exact execution `RulePortRef`.
- `ResolvedRuleBundle` and `ResolvedRuleContract` provide the trusted Rule,
  endpoint map and contract digest.
- SC-01 and authored-to-lowered lineage remain unresolved beyond the vertical
  probe; this slice must not consume current lowering as a semantic oracle.

## 5. Proposed Shape

```text
ResolvedRuleBundle
  -> managed occurrence(alias)
  -> canonical SemanticPortAddress(alias, port)
  -> resolved semantic ref(address + RulePortRef + endpoint + contract digest)

managed occurrences
  -> immutable SemanticAddressSpace
  -> typed resolve(address)
```

Use one small protocol module for canonical address/reference DTOs and one
application module for managed occurrence/address-space construction and
resolution. Do not add `ResolvedRuleBundle.as_(...)` sugar in this slice; the
runtime constructor remains the single dependency direction and validation
point.

## 6. Boundaries And Invariants

- Reuse shipped `RuleOccurrence` and `RulePortRef`; do not copy their logic.
- Canonical paths are two-part values, never parsed dotted strings.
- Only direct managed Rule ports are addressable.
- Duplicate occurrence aliases reject; occurrence input order is irrelevant.
- The input occurrence collection is copied, sorted and frozen; caller mutation
  cannot change the space or its derived identity.
- Alias rename changes address-space digest.
- Same endpoint does not merge addresses, Vars or occurrences.
- Construction and resolution check that each occurrence Rule still exactly
  matches its semantic contract. Resolved `RulePortRef` values are produced
  internally, never accepted from the caller.
- The caller-inaccessible digest uses a typed/versioned payload containing each
  sorted alias, Rule id/version/content digest and semantic-contract digest.
- Resolution requires the port in both Rule and contract with the same Var;
  unknown alias and unknown port have distinct typed errors.
- Production additions under `src/factgraph/application/**/*.py`, including
  export edits and excluding tests/docs, are capped at 350 lines relative to
  `8e480daf`; deletions do not offset additions.

## 7. Acceptance

- [ ] Same Rule under two aliases has distinct addresses and unchanged contract identity.
- [ ] Address resolution returns exact Rule-owned Var, endpoint and contract digest.
- [ ] Duplicate alias, unknown alias and unknown port fail distinctly.
- [ ] Mismatched Rule/contract and caller collection mutation fail or remain isolated.
- [ ] Same-endpoint/different-Var ports remain separate and create no join.
- [ ] Address-space identity is order-stable and alias-sensitive.
- [ ] Stale Rule/contract is rejected at construction and resolution.
- [ ] Legacy RuleExpr and one evaluate→row→Explain regression remain green.
- [ ] Production line cap holds and application docs state all deferrals.

## 8. Implementation Plan

1. Add canonical address/reference DTOs with typed structural validation.
2. Add managed occurrence and immutable address-space runtime using F1-lite and shipped occurrence APIs.
3. Add the frozen acceptance matrix and legacy compatibility regression.
4. Update application Rule/module docs and exports.
5. Run focused tests, Ruff, targeted mypy and the existing full suite; obtain independent contract and simplicity reviews.

## 9. Docs To Update

- `src/factgraph/application/docs/rule.md`
- `src/factgraph/application/docs/README.md`

## 10. Outcome / Deviations

To be completed at closure.
