# Audit Log: Explain Conformance Batch D2 — exhaustive verdict track after upstream failure

Paired with [2026-06-10_explain-conformance-batch-d2-exhaustive-verdict.md](./2026-06-10_explain-conformance-batch-d2-exhaustive-verdict.md).

---

## A. Trigger (2026-06-10)

Post-closure design verification found a residual mismatch between Batch D and
the governing design:

- `explain-layer-complete-design.zh.md` §307: the prober is exhaustive and does
  not voluntarily skip later branches/rules/atoms.
- §308: `NotReached` is triggered only by unbound variables. An earlier
  `Fails` does not trigger later `NotReached`; if later atom dependencies are
  bound, the prober continues evaluating.

User chose option A: change code to align with §308 before archiving the
conformance program.

## B. Source Preflight

Read targets:

- `src/factgraph/application/explain/prober.py`
- `src/factgraph/application/explain/docs/README.md`
- `workflow/design/design-points/active/explain-layer-complete-design.zh.md`

Confirmed:

- `_probe_branch(...)` has `initial_bindings`, `envs`,
  `last_non_empty_envs`, and `failed_upstream`.
- `_probe_atom(...)` has verdict-only mode:
  `failed_upstream and not envs`.
- In verdict-only mode, `_probe_atom(...)` may compute a downstream verdict
  from `verdict_envs`, but returns the original empty candidate env tuple.
- `_probe_branch(...)` updates `last_non_empty_envs` only from returned
  candidate envs, so explanation envs freeze after the first failure.
- The module docs still describe "last row-anchored prefix environment" rather
  than exhaustive explanation-track advancement.

## C. Locked Scope

- Edit target: `src/factgraph/application/explain/prober.py`.
- Docs target: `src/factgraph/application/explain/docs/README.md`.
- Tests: `tests/application/explain/test_prober.py` and/or
  `tests/sdk/test_explain_conformance_native.py`.
- Optional demo expectation update: `examples/explain_layer_demo.py`.

Non-targets:

- seed builder / lowering seed mapping;
- DTOs and EvidenceGraph schema;
- adapter converters;
- support-capture aggregate resolver;
- value rendering and NotAtom rendering except as affected by new tests.

## D. Open Implementation Questions for Scope Review

1. **Return shape**: use a third return value from `_probe_atom(...)`
   (`next_verdict_envs`) or a small internal result object.
2. **Predicate key guard**: exact helper for deciding when a bind-producing
   predicate has enough row-anchored input to run in failed-upstream verdict
   mode. Default recommendation: require the first predicate variable/key term
   to be bound; if not, return `NotReached`.
3. **Failed filter env retention**: when a filter evaluates to `Fails`, keep
   the pre-filter explanation envs for later independent atoms.
4. **NotReached env retention**: when an atom is `NotReached`, keep current
   explanation envs for later independent atoms.

These are implementation-shape questions, not scope blockers. The semantic
requirements are locked by blueprint §5-§7.

## E. Required Gate Evidence

Reviewer gate must include:

- design §308 repro: failed senior filter followed by region predicate and
  region comparison now yields `Fails`, then `Holds`, then `Holds`;
- order-independence probe;
- true-unbound dependency remains `NotReached`;
- no branch resurrection;
- multi-entity no-leak probe;
- G1 monotonic regression;
- Batch A/B/C/E regression cohort;
- docs updated to exhaustive wording.

## F. Implementation Outcome

Pending.
