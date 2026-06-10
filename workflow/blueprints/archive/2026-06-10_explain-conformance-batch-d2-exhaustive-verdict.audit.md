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

## E. Scope Review (2026-06-10)

Verdict: APPROVED; moved to `scoped`.

Reviewer locks:

1. The leakage guard and design §305 `NotReached` must be implemented as one
   dependency check, not two competing concepts. Input dependency bound means
   the atom may be evaluated with pinned row-anchored envs. Input dependency
   unbound means `NotReached(blocked_by=...)`.
2. Predicate free-enumeration risk is the subject/key position. For
   field/identity/exists-style predicates, `term0` is the entity subject. If
   that subject variable is unbound after upstream failure, return
   `NotReached`, not an unconstrained fact scan.
3. Unknown predicate shapes must fail closed to `NotReached`.
4. Dual-track semantics remain locked: candidate envs stay empty after failure;
   explanation envs may advance exhaustively.

## F. Required Gate Evidence

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

## G. Implementation Outcome

Implemented in `d4747a88`.

Implementation choices:

- `_probe_atom(...)` returns `(evidence_atom, candidate_envs,
  explanation_envs)`. This makes the dual-track split explicit.
- Candidate envs remain empty after an upstream failure, preserving
  no-resurrection.
- Explanation envs advance exhaustively when `_extend_env_with_atom(...)`
  succeeds, remain at the previous envs after a pinned `Fails`, and remain
  unchanged after `NotReached`.
- `_missing_verdict_dependencies(...)` implements the unified §305 / leakage
  guard. Predicate atoms check the subject/key position (`term0`) in
  failed-upstream verdict mode; an unbound key returns `NotReached` rather than
  scanning all facts.

Tests / verification:

- Codex focused: `tests.application.explain.test_prober` → `21 OK`.
- Codex focused + native conformance:
  `tests.application.explain.test_prober tests.sdk.test_explain_conformance_native`
  → `31 OK`.
- Codex broader cohort including protocol/digest/schema/adapters/aggregate and
  rule-expr tests → `166 OK`.
- Demo run showed the senior path as `Fails → Holds → Holds`.

Reviewer gate:

- §308 senior repro passed: `30 >= 65` Fails, then region predicate Holds, then
  region comparison Holds.
- Order-independence probe passed.
- True unbound dependency remains `NotReached`.
- Key-unbound predicate no-leak probe passed; no unrelated entity facts leaked.
- No-resurrection passed; failed branch remains `status="fails"`.
- G1 monotonic and Batch A/B/C/E regressions passed.
- Design conformance for §307-308 is now satisfied.
