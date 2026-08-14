# Audit: FactGraph product interfaces vs shipped runtime

- Status: complete
- Created: 2026-08-14
- Last Updated: 2026-08-14
- Authority: working triage document. It records the shipped baseline and the
  user-locked Q20 direction; the binding constraints live in Q20.
- Inputs:
  - [Q18 final Query, Scenario and execution closure](../../design/decisions/active/2026-08-14_q18-factgraph-final-closure-contract.md)
  - [Q19 Policy authoring SDK and literal comparison](../../design/decisions/active/2026-08-14_q19-policy-authoring-sdk-literal-comparison-decision.md)
  - the 2026-08-10 Meander product-design session export, used as historical
    rationale rather than an API authority
  - the user's 2026-08-14 locks for product-facing authoring, Scenario metadata,
    execution semantics, structured Explain, and provenance boundaries
- Outputs / Downstream:
  - [Q20 product-interface decision](../../design/decisions/active/2026-08-14_q20-factgraph-product-interface-decision.md)
  - [Q20 implementation blueprint](../../blueprints/active/2026-08-14_factgraph-product-interface.md)
- Related:
  - [Q18 final-closure audit](2026-08-14_factgraph-final-closure-vs-shipped.md)
  - [Q19 authoring audit](../archive/2026-08-14_factgraph-policy-authoring-sdk-vs-shipped.md)
- Branch: `codex/v0.3.0-impl-factgraph-product-interface-2026-08-14`

## 1. Scope

This audit covers the additive product surface above Q18/Q19's sealed runtime:

| Layer | Shipped source reviewed | Why it matters |
| --- | --- | --- |
| Rule/Policy authoring | `src/factgraph/sdk/policy_authoring.py`, `src/factgraph/sdk/evaluation_query_builder.py`, `src/factgraph/sdk/dsl/application_rule.py` | Current Policy draft façade, raw Rule bridge, typed Query ingress. |
| Scenario and execution | `src/factgraph/application/protocol/scenario_v1.py`, `src/factgraph/application/scenario_v1_runtime.py`, `src/factgraph/application/protocol/evaluation_run_v1.py`, `src/factgraph/application/goal_plan_v1_runtime.py`, `src/factgraph/application/portable_evaluation_runtime.py`, `src/factgraph/sdk/semantics.py` | Effective-world, replay, deterministic profile and legacy engine configuration seams. |
| Result and Explain | `src/factgraph/application/protocol/evaluate_result.py`, `src/factgraph/application/explain/evidence_tree.py`, `src/factgraph/application/evaluation_run_v1_runtime.py` | Compatibility V0 renderers versus sealed V1 evidence/projection. |
| Source/write ingress | `src/agent/draft.py`, `src/agent/tools/write.py`, `src/factgraph/core/evidence/write_protocol.py` | Existing flat source convention, rich extraction loss, and semantics/provenance separation. |

Out of scope: Meander `SourceRecord` custody/ACL/retention, AgentPlan translation,
policy publication/registry, generic world synthesis, a global closed world,
arbitrary engine callbacks, general probabilistic parity, and action execution.

## 2. Triage table

| ID | Commitment | State | Shipped evidence / consequence |
| --- | --- | --- | --- |
| A1 | Friendly Rule and Policy construction with asset metadata | (c) shape conflict | Q19 ships `SDKStore.policy()` / `PolicyDraft`, but Rule authoring is still the lower-level `build_application_rule`; neither shares an AssetMeta asset envelope. A symmetric additive façade is required. |
| A2 | Occurrences remain typed, local and non-registered | (a) shipped covers | `PolicyDraft.use(resolved_rule, as_=...)` already checks schema/contract and produces owner-bound handles. Q20 must retain this mechanism while improving names and constructors. |
| A3 | Explicit logical topology plus authored stochastic choice | (d) genuinely new | All/Any and Compare are shipped. Weighted exclusive choice has no current AST, compiler, replay, Explain or engine support. |
| A4 | Scenario `meta={raw_kind,bound,source,note}` has real semantics | (c) shape conflict | Scenario V1 has values and opaque `origin_refs` only. Its effective facts, projected relation and replay payload omit raw semantics/provenance. A façade-only meta argument would silently discard inputs. |
| A5 | Semantic metadata and source metadata have separate authority/digests | (d) genuinely new | Ledger `meta` intermixes annotation, ingestion and raw semantics. It cannot be reused for run-local premises. New typed lanes and a safe provenance reference are required. |
| A6 | ProbLog semantics attach to stable authored anchors | (c) shape conflict | Legacy `ProbLogConfig.case_probabilities` refers to lowered branch ids; `rule_params` has no adapter consumer. Q18 V1 profiles reject all configuration. New V2 profile bindings are required. |
| A7 | Deterministic three-engine profile remains honest | (a) shipped covers | Q18 portable execution already materializes one relation and tests Native/Soufflé/ProbLog canonical selected-row parity. It explicitly excludes probability/config. Q20 must preserve that exclusion. |
| A8 | Scenario fact change + independently compiled candidate Rule/Policy comparison | (a) shipped covers | Q18 Scenario V1 handles ground run-local fact operations; candidate targets handle immutable program comparison. Q20 must not add mutable Rule/Policy patches. |
| A9 | V0 EvaluateResult/Explanation behavior stays available | (a) shipped covers | Live `EvaluateRow.explain()/close()` and outer `Explanation.repr`/`.narrate()` remain. Attachments added by F4/F5 are kw-only and sealed. |
| A10 | Business-facing V1 result/explain read model | (b) small gap | Q18 has sealed `GoalResultV1`, explicit Explain targets, EvidenceGraph and Policy projection, but callers must navigate protocol DTOs and no structured presentation/read facade exists. |
| A11 | Structured explanation data, not prose parsing | (d) genuinely new | Legacy renderers consume only EvidenceTree rules/joins; they are not Policy/Scenario/provenance aware. A machine-readable V1 facade plus pure renderers is required. |
| A12 | Source/provenance handoff without making FactGraph a SourceRecord service | (c) shape conflict | Evidence `Source` is a generic engine-support DTO. Agent drafts have rich extraction data but write only `source/source_loc` strings. A small opaque FactGraph provenance ref is appropriate; SourceRecord lifecycle is not. |
| A13 | Preserve legacy ingest identity | (a) shipped covers | `source`, `source_loc` and `trace_id` participate in current ingestion metadata/idempotency. Q20 must add adapters rather than alter existing ledger write identity. |

## 3. Concrete findings

### 3.1 Authoring and metadata

Q19's `AuthoredPolicyTargetV1` deliberately contains only a Policy and an exact
semantic address space. `PolicyDraft` is graph-scoped because resolving a Rule
occurrence needs the receiving graph's trusted schema and contract; it is not a
registry or publication event. The existing `build_application_rule()` is an
SDK DSL bridge that produces an application Rule but does not produce the
resolved bundle needed by `.use()`.

The user experience gap is therefore naming and an asset envelope, not a reason
to collapse Rule and Policy compilation. Rule construction must resolve a Rule
against a graph; Policy construction must compose already resolved Rules under
local aliases. Both can expose builder/direct convenience forms while retaining
those distinct responsibilities.

### 3.2 Scenario semantics and profile integrity

`ScenarioSpecV1` seals a value and `origin_refs`, while `EffectiveWorldFactV1`
and replay facts only retain typed tuple values and a baseline/scenario origin.
`effective_world_to_relation_v1()` materializes bare projected facts. V1
profiles hard-reject non-null config digests. This is exactly the right V1
deterministic boundary, but it means a user-visible scenario `meta` cannot be
accepted until a parallel protocol carries semantic metadata and provenance
through resolve, capture, engine materialization, replay and Explain.

The legacy `ProbLogConfig` is a compatibility API. Its branch identifiers are
compiler-lowered coordinates, so it cannot become the author-facing anchor for
new Policy/Scenario execution. `rule_params` is not currently consumed by an
adapter and must not be advertised as a V1 mechanism.

### 3.3 Explain/result continuity

The V0 outer `Explanation` still owns lazy `repr` and `narrate`; `EvidenceGraph`
itself never did. Q18 detached V1 Explain has the correct integrity boundary:
it pins a run and explicit target, can expose EvidenceGraph/Policy projection,
and refuses a fabricated zero-row proof. It is not, however, a product-facing
read model. A new facade can make its structured facts easy to consume without
pretending it is a live V0 row or adding an unsafe implicit first-row Explain.

### 3.4 Source/provenance

`EvidenceTree.Source(ref, field, value, meta)` is a generic logical-support
carrier populated by all engines; it is not an external-source record. Agent
`FactDraft` has `source/source_loc` plus `ExtractionProvenance`, but
`draft_to_write_request()` currently degrades the latter to strings and also
emits `confidence`, which the core write protocol rejects. Source content,
access and authority must stay in Meander; FactGraph can safely carry an opaque
pin/reference in a run-local premise and Explain projection.

## 4. Open questions resolved by user lock

| Question | Resolution to lock in Q20 |
| --- | --- |
| Should graph scope mean registration? | No. It is schema/contract authority only; no catalog or durable registration. |
| Is scenario `meta` a free JSON bag? | No. It is the principal SDK spelling but strict-lowers to typed semantic, provenance and display lanes. |
| Should generic engine kwargs sit on `use/all/any`? | No. Stable occurrence/node bindings belong in a sealed run profile; All/Any remain pure logic. |
| Is ordinary Any a probabilistic alternative? | No. A later explicit `WeightedChoice` semantic node models exclusive choices; it is initially ProbLog-only. |
| Should V1 replace V0 result/explain objects? | No. Add product views/data while preserving V0 behavior. |
| Does FactGraph own full SourceRecord? | No. It owns only neutral opaque provenance references and projection. |

## 5. Recommendations for blueprint

1. Add a compact SDK asset layer shared by Rule and Policy builders, preserving
   existing raw and Q19 compatibility paths.
2. Add a parallel V2 Scenario/effective-world/run profile family rather than
   widening sealed V1 DTOs; start with deterministic and exact-point ProbLog.
3. Add strict `ScenarioMeta` lowering and `ProvenanceRefV1` before exposing
   meta in the SDK.
4. Keep portable V1 deterministic; route probability to an explicit
   ProbLog-only profile with typed unsupported results elsewhere.
5. Add V1 product result/explanation data and rendering adapters; preserve
   explicit targets and zero-row evidence constraints.
6. Add a narrow Agent write adapter/diagnostic for provenance handoff and the
   rejected `confidence` key, without implementing Meander SourceRecord.

## 6. Audit completeness checklist

- [x] All in-scope commitments triaged
- [x] User-resolved questions recorded
- [x] Frictions and cross-layer seams enumerated
- [x] Out-of-scope explicit
- [x] Blueprint recommendations provided
