# FactGraph Final Closure: design versus shipped audit

- Status: completed
- Created: 2026-08-14
- Authority: input to Q18 and the final FactGraph closure blueprint; it is not
  itself an implementation authorization.
- Scope: the four capability matrices requested by the user: Scenario,
  Query/Result/Expectation, Run/Explain/Replay, and Evidence/Assessment.
- Baseline: 416456445957251b45a6ebbc8fb1f979843bf2ac on
  codex/v0.3.0-factgraph-final-closure-2026-08-14.
- Design inputs: the three working design-points on semantic ports,
  Scenario/Run, and premise/effective-view resolution; their candidate status
  is consumed only through Q18.

## 1. Audit conclusion

The shipped F3--F5 chain is a reliable substrate, not the completed product
contract. It already provides: ontology-addressed Policy ports, Boolean
Policy topology, direct comparison and one-hop field navigation, a sealed
Query projection, native rows, contains-row observations, narrow scalar
replacement Scenarios, Policy-aware Explain, and native detached captures.

It deliberately does not provide a generic Scenario algebra, portable
multi-engine execution, a full expectation/completeness model, policy-variant
comparison, or a single run artifact spanning baseline/effective/explain/
replay. Treating its v0 restrictions as the final design would silently
abandon the user-approved Query/Scenario direction.

## 2. Evidence read at audit time

| Area | Shipped evidence | Finding |
| --- | --- | --- |
| Query target/compiler | application/evaluation_query_target_runtime.py; application/evaluation_query_runtime.py | Small extension seam; target and projection seals already exist. |
| Scenario input/world | application/protocol/evaluation_scenario.py; query_effective_snapshot_runtime.py | Shape conflict: v0 is explicitly replacement-only and couples public identity to legacy adapters. |
| Native execution/capture | sdk/store.py; core/store/_evaluate.py; application/evaluation_run_bundle_runtime.py | Reusable substrate; effective relation injection and detached capture already exist. |
| Policy Explain | application/policy_explanation_runtime.py; evaluation_run_evidence_runtime.py | Reusable inner evidence, but no Scenario/variant root or cross-engine contract. |
| Soufflé/ProbLog | adapters/souffle/engine_eval.py; adapters/problog/engine_eval.py | Genuine new integration: both execute Store-backed plans, neither accepts a sealed effective relation or produces the Query run contract. |
| Absence/closure | Q17 plus native NotAtom observation | Genuine semantic decision required; observed native NAF is not a public absence contract. |
| Assessment | EvaluateResult and expectation runtime | Shape conflict: current local result fields cannot be presented as a product verdict. |

## 3. Capability triage

| Matrix cell | Shipped state | Q18 disposition |
| --- | --- | --- |
| Typed Rule/Policy target, bind, select, Policy compare/navigation | covered | Preserve as the Query core. |
| Scenario replace | covered narrowly | Compatibility path; normalize into the new Scenario v1 resolver. |
| Add, exact-set, mask/delete, new entity/relation, conflict algebra | absent | Implement in the FactGraph Scenario v1 resolver. |
| Source authority, admission, Translator ambiguity | absent by design | Explicitly Meander-owned; FactGraph receives already-addressed premise origins only. |
| Rule/Policy change | absent | Implement immutable base/candidate target comparison; no mutable overlay. |
| Native Query result/capture/explain | covered | Preserve and adapt behind a v1 run facade. |
| Soufflé/ProbLog Query effective-world execution | absent | Implement only the portable positive deterministic profile and prove parity. |
| General NAF/closed-world proof | absent | Reject from portable v1; expose a typed closure-required/unsupported result rather than guessing. |
| Exists/count/set/bag expectations and completeness | partial contains-row only | Implement finite complete-enumeration Query v1 forms. |
| Cross-engine logical proof equality | absent | Do not claim it; normalize rows and retain engine-specific evidence. |
| Product assessment/disposition/authority | absent by design | Keep Meander-owned; FactGraph publishes technical axes only. |

## 4. Load-bearing constraints

1. Meander never resolves add/replace/remove against storage. FactGraph resolves,
   normalizes and rejects conflicts before it executes.
2. A Scenario is a run-local effective world, never a ledger mutation and never
   a claim that caller input is true.
3. Scenario exact absence and evidence exclusion are different. A Scenario
   WITHOUT creates a local exact-empty target and closure; EvidenceScope ignore
   merely excludes baseline evidence and cannot prove absence. Neither is a
   global negative fact. General Rule/Policy negation stays outside the
   portable v1 profile.
4. A run pins target, schema/address space, effective relation, execution
   profile and selection/expectation inventory. Explain and replay consume
   those pins; no current-latest fallback is allowed.
5. Zero rows are not false. An unsatisfied expectation is valid only when
   complete enumeration is established for that exact run.
6. Rule changes use a separate immutable Policy/Rule target. There is no
   mutable Policy patch, source-authority decision, or hypothetical ledger
   write.
7. Portable parity means normalized result equivalence for a declared,
   deterministic positive profile across native, Soufflé and ProbLog. It never
   means that all three engines have identical proof or general language
   semantics.

## 5. Risk register

| ID | Risk | Control in final closure |
| --- | --- | --- |
| R1 | v0 and v1 identities get conflated | Keep all v0 DTOs/wires byte-compatible; v1 has a distinct protocol and adapters. |
| R2 | Scenario absence is confused with evidence exclusion | Separate exact local closure from EvidenceScope ignore; no implicit global NAF claim. |
| R3 | External engines read the live Store instead of the pinned world | Materialize a sealed effective relation before every engine call; test mutation isolation. |
| R4 | Query expectation turns empty enumeration into false | Carry completeness separately and require it for negative outcomes. |
| R5 | Policy variants become mutable/unauditable | Base and candidate are independently compiled/pinned immutable targets. |
| R6 | Evidence turns engine-specific traces into fake common proof | Preserve engine evidence and use Policy structure only as a projection layer. |

## 6. Recommendation

Adopt one final closure contract, Q18, and implement only the supported
portable profile plus explicit typed rejections. The resulting artifact may
be called complete because every capability cell is either implemented,
compatibility-preserved, explicitly rejected, or documented as Meander-owned;
it must not claim universal Datalog/ProbLog equivalence, source authority, or
Action authorization.

## 7. Implementation verification outcome

Q18 has now been implemented as a parallel V1 contract on its isolated branch.
The final surface covers the supported Scenario algebra, Rule/Policy Query
targets, constrained providers, all declared result/expectation modes,
immutable candidate comparison, captured Scenario diff, explicit detached
Explain/replay, and native/Soufflé/ProbLog selected-row parity. It preserves
the earlier V0 Query/Scenario/Run protocols rather than mutating them.

The final closure test command passed **680 tests and 175 subtests** in the
pinned FactGraph environment. Static format/lint/type/diff checks also passed,
and an independent adversarial review found no remaining reproducible P0/P1.
The bare repository-wide test command remains blocked during collection by a
baseline `service.static_ui` import of missing
`factgraph.audit.evidence_graph.render_evidence_graph_html`, plus independent
third-party test package layout errors. Neither source path changed on this
branch; this is recorded as an unrelated carry-forward rather than silently
fixed in the FactGraph closure.
