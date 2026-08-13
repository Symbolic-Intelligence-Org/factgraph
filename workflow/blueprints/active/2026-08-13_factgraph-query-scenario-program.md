# Task Blueprint: FactGraph Query/Scenario continuous delivery program

- Status: implementing
- Created: 2026-08-13
- Last Updated: 2026-08-13
- Branch: `codex/v0.3.0-factgraph-whatif-v1-continuous-2026-08-13`
- Decision: [Q15 captured Query run](../../design/decisions/active/2026-08-13_q15-captured-evaluation-query-run-v0-decision.md)
- Audit Log: [paired audit](./2026-08-13_factgraph-query-scenario-program.audit.md)

## 1. Program objective

Deliver the remaining **bounded FactGraph-native** Query and Scenario seams as
a few semantic work packages rather than repeatedly restarting a full
micro-slice workflow.  This program begins from Q14 (`ff799f4a`), which already
delivers the minimum unified Query path and replacement-only captured Scenario.

## 2. Work packages

1. **P1 — durable Query/validation**: a detached Query-run façade around the
   already captured F4 bundle, including captured `contains_row` outcomes.
2. **P2 — query-scoped EffectiveSnapshot foundation**: make the existing
   replacement-only Scenario resolver expose a stable pre-evaluation identity
   without claiming a global or historical world snapshot.
3. **P3 — residual semantic gates**: do not implement them speculatively.
   `WITHOUT_*`, absence/closure, relations/new entities, Policy overlays,
   external Operators and cross-engine profiles each require a new decision.

## 3. Continuous-delivery rules

- Each package has one bounded decision and one implementation/review closeout;
  commits inside a package may proceed continuously.
- Stop only for a new semantic fork, a fail-closed/integrity failure, a test
  regression, or an external/cross-repository authorization boundary.
- No package silently widens old v0 wire/digest contracts.  The program does
  not authorize Meander, Translator, Package, source-authority or Action work.

## 4. Immediate P1 boundary

P1 implements Q15 only.  It preserves F4 bundle v0 and ordinary
`eval.evaluate` behavior by introducing a sealed outer artifact.  It must not
make a negative outcome explainable or claim historical replay/authorization.

## 5. P2 entry gate

P2 begins only after the resolver identity is frozen as **query-dependency
scoped**.  It may retain existing replacement semantics but must not introduce
missing-field insertion, delete/mask, negation/closure, relation/new-entity,
Policy-relative premise addressing, source admission, or a generic premise DSL.

## 6. Acceptance

- [x] P1 is implemented, independently reviewed and documented.
- [ ] P2 has an adopted conservative identity contract before implementation.
- [ ] All final package outcomes distinguish shipped capability from remaining
  semantic gates.

## 7. Outcome / deviations

P1 is implemented and independently reviewed. Its outer artifact preserves
ordinary expectation/capture rejection, rechecks bundle selection alias/type
contracts on every detached operation, and rejects in-memory captures that do
not fit the strict durable codec. P2 remains the next bounded package. This
program intentionally replaces repeated per-function approval pauses with
explicit work-package stop conditions; it does not weaken the integrity,
provenance or scope boundaries inherited from Q8–Q14.
