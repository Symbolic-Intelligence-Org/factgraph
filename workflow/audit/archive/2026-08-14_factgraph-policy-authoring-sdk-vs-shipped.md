# Audit: Policy authoring SDK versus shipped runtime

- Status: complete
- Created: 2026-08-14
- Last Updated: 2026-08-14
- Authority: working triage document; informs but does not lock implementation.
- Inputs:
  - [Q12 Policy comparison and field navigation v0](../../design/decisions/active/2026-08-13_q12-policy-comparison-field-navigation-v0-decision.md)
  - [Q18 FactGraph final Query, Scenario and execution closure](../../design/decisions/active/2026-08-14_q18-factgraph-final-closure-contract.md)
  - the user's 2026-08-14 request for an ergonomic, nested Policy authoring surface with natural comparisons and literal operands
- Outputs / Downstream:
  - [Q19 Policy authoring SDK and literal comparison](../../design/decisions/active/2026-08-14_q19-policy-authoring-sdk-literal-comparison-decision.md)
  - [Policy authoring SDK blueprint](../../blueprints/archive/2026-08-14_factgraph-policy-authoring-sdk.md)
- Related:
  - Q12's compiler/evidence compatibility contract remains authoritative except where Q19 explicitly supersedes its literal restriction.
- Source intent: turn the existing typed Rule/Policy Query execution substrate into an ergonomic SDK authoring surface without creating a second Policy language or evaluator.
- Branch: `codex/v0.3.0-policy-authoring-sdk-2026-08-14`

## 1. Scope

Read in full:

| Layer | File | Finding |
| --- | --- | --- |
| Public Query ingress | `src/factgraph/sdk/store.py` | `fg.query(...)` is the stable execution entry, but accepts compiler-level Policy plus address space. |
| Query builder | `src/factgraph/sdk/evaluation_query_builder.py` | Structured bind/select/plan compilation is already sealed and must be reused. |
| Target resolution | `src/factgraph/application/evaluation_query_target_runtime.py` | Rule lift and direct Policy resolution are trusted, typed paths; no string registry exists. |
| Policy IR | `src/factgraph/application/protocol/policy.py` | All/Any/Unify/Compare/navigation are complete compiler IR; compare operands exclude literals. |
| Policy compiler | `src/factgraph/application/policy_runtime.py` | Direct scalar/navigation comparisons lower into Policy-owned conditions with lineage and Explain ownership. |

Out of scope: Rule authoring redesign, Policy catalog/lookup, Agent authorization,
Meander syntax, Actions, generic expression evaluation, a second evaluator, and
loosening the portable deterministic profile.

## 2. Triage table

| ID | Intent | State | Evidence / disposition |
| --- | --- | --- | --- |
| A-01 | One typed Rule/Policy Query execution path | shipped covers | Existing target resolver and EvaluationQueryBuilderV1 are the only compiler/execution route. |
| A-02 | Nested logical topology whose Explain preserves authored shape | shipped covers | `PolicyAll`/`PolicyAny`, PolicyStructure and the detached Explain projection already preserve topology. |
| I-01 | Structured ports rather than strings | shipped covers | SemanticAddressSpace and SemanticPortAddress are sealed compiler contracts. |
| I-02 | Direct scalar and one-hop field-navigation compare | shipped covers | Q12 compiler/lowering/evidence path exists; branch-total guards are active. |
| D-01 | A normal SDK author should not manually build `PolicyOccurrence`, `PolicyAll`, or an address space | genuinely new | Add a thin SDK façade that emits the existing IR; do not change the evaluator. |
| D-02 | `people.age > 12` | shape conflict | Q12 explicitly rejects literal operands. A new canonical literal IR and compiler/evidence/replay coverage are required; façade-only sugar would be dishonest. |
| D-03 | Natural Python syntax must not silently reinterpret Boolean logic | genuinely new | Symbolic handles/nodes must reject truthiness, `and/or/not`, chained comparisons and cross-draft mixing fail loudly. |
| N-01 | `fg.query("policy-name")` / ambient policy registry | deferred-aligned | Q18 rejects string DSL and registry lookup; retain typed resolved values. |
| N-02 | Bare relation provider as a logical target | deferred-aligned | Q18 restricts providers to a typed input attached to a Rule/Policy target. |

## 3. Open questions resolved by Q19

1. **Does SDK syntax create another Policy semantics?** No. It compiles to the
   current Policy IR and the existing target resolver; no new evaluator exists.
2. **Can a literal be a mere convenience value?** No. It becomes a sealed,
   typed Policy operand with compiler, lineage, Explain, replay and three-engine
   conformance coverage.
3. **Should `and`/`or` be overloaded?** No. Python consumes them before a DSL
   can preserve topology. The SDK uses explicit, nestable `draft.all(...)` and
   `draft.any(...)`.

## 4. Frictions and boundaries

- Python's `==`, `and`, `or`, `not`, chained comparisons and `is` have host
  language behavior that cannot be made silently logical. The façade must
  reject misuse rather than approximate it.
- A raw `Policy` must remain supported as the application/compiler contract;
  the façade is additive and does not rename or migrate it.
- Literal support must remain finite, canonical and type-directed. No implicit
  string/number coercion, `None`, NaN/Infinity, entity identity comparison or
  relation traversal is admissible.

## 5. Blueprint recommendations

1. Add SDK-owned typed draft/occurrence/port/navigation/constraint handles.
2. Reuse target resolution and Query compilation by unwrapping a frozen SDK
   Policy target into `(Policy, SemanticAddressSpace)` at the SDK boundary.
3. Add one narrow canonical Policy literal extension, including all integrity
   and detached Explain/replay codecs it changes.
4. Prove exact IR lowering, Python trap rejection, real native/Soufflé/ProbLog
   parity, Explain topology and legacy raw-IR compatibility.

## 6. Audit completeness checklist

- [x] All in-scope rows triaged
- [x] Literal-Q12 conflict surfaced
- [x] Python-host-language frictions enumerated
- [x] Out-of-scope items explicit
- [x] Blueprint recommendations provided

## 7. Implementation disposition

Q19 consumed the three genuinely new rows without widening the execution
authority:

- D-01 is the SDK `PolicyDraft`/typed-handle façade. Its frozen target enters
  the existing managed Policy resolver and Query compiler, with no catalog or
  second evaluator.
- D-02 is the sealed, canonical signed-int64 `int`/`time` `PolicyLiteral`
  operand. It has compiler/lineage/Explain/replay coverage and real
  Native/Soufflé/ProbLog selected-row-set fixtures.
- D-03 is fail-loud host-language behavior plus target-owner validation at
  bind/select. Python Boolean/hash traps, unsupported literals, cross-draft
  handles and select-only navigation all reject before evaluation.

The resulting SDK tutorial is executable. The final application/SDK/export
cohort reported 706 passed + 175 subtests, and two independent reviews returned
CLEAR. The consuming blueprint is ready for archive; this audit moves with it.
