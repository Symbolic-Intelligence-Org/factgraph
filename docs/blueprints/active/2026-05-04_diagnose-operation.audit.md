# Task Blueprint Audit: Diagnose Operation

- Blueprint: [2026-05-04_diagnose-operation.md](./2026-05-04_diagnose-operation.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-04 | draft | Blueprint created | Opened as the second application capability candidate after Check. Purpose is Step 0 only: freeze Diagnose DTO / algorithm / engine boundary before any implementation. |
| 2026-05-04 | draft | Step 0.A source pass opened | Initial anchors recorded from Check protocol/runtime, archived Check blueprint/audit, application common protocol DTOs, baseline P0-3 support artifacts, and engine-extension §6.3 / §6.4 / §6.5. |
| 2026-05-04 | draft | Step 0.A source pass complete | Native primitives + Check runtime fully mapped; Explore-agent reported non-native failure surfaces (souffle / problog / pyreason); cross-engine diagnostic asymmetry confirmed (steeper than Check's); Q1 stance **Hybrid**; Q2–Q5 preliminary stances recorded; **§3.6 second-consumer pressure confirmed but MVP keeps §3.6 deferred** per topic §6.2 wave ordering. Blueprint remains `draft`; no implementation until Step 0.B / 0.C / 0.D complete. |

## Decision Notes

- 2026-05-04: Diagnose starts as a `draft` blueprint because the application DTO shape is not frozen. Per application-first hard constraint, implementation cannot begin until Step 0 answers "what is the application DTO shape?"
- 2026-05-04: Initial positioning: Diagnose is expected to be a sibling application capability to Check, not an SDK extension and not an Explain / Why-not / UI projection feature.
- 2026-05-04: Step 0.A initial source anchors:
  - `CheckRequest` / `CheckResult` / `EvidenceEnvelope` show the closest existing request/result/evidence pattern.
  - `check_derivation_binding(...)` shows final-result matching, representability precheck, and typed evidence lookup boundaries.
  - `ErrorDTO` / `WarningDTO` are the current application error/warning carriers.
  - baseline P0-3 records support/provenance data contracts and the partial-binding silent-false trap.
  - engine-extension §6.3 requires observable evidence misses for new capabilities.
  - engine-extension §6.4 blocks request-level engine options unless promotion criteria are met.
  - engine-extension §6.5 keeps typed Union as payload default unless a concrete migration trigger appears.
- 2026-05-04: Open Step 0.A question: does Diagnose create enough second-consumer pressure to promote §3.6 engine capability declaration, or can MVP stay locally hardcoded like Check?
- 2026-05-04 (Step 0.A): Source-pass file coverage:
  - `src/kernel/application/derivation_check_runtime.py` — Check primitive sequence, representability gate, primary selection, typed lookup helpers
  - `src/kernel/application/derivation_runtime.py` — evaluate executor, plan dispatch, run_id propagation
  - `src/kernel/core/rules/ruleref_substrate.py:32` — `evaluate_native_where(...)` returning `NativeWhereEvaluation(bindings, rule_refs, rule_ref_resolutions)`
  - `src/kernel/core/store/_support_capture.py:240` — `_branch_satisfies` (per-branch verifier); `:263` — `_atom_satisfies` (8-kind dispatch); `:431` — `_ground_terms` (silent-false on missing var)
  - `src/kernel/core/store/_support.py:97` `SupportArtifact`; `:148` `ProvenanceEnvelope`
  - `src/kernel/core/store/runtime.py:119` `_lookup_support_artifact`; `:152` `_lookup_provenance_envelope` (typed internal API)
  - `docs/references/working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md` §P0-3 (Check operation hook + 5-input set + silent-false trap)
  - Explore-agent on `src/kernel/adapters/{souffle,problog,pyreason}/` — failure surfaces, evidence retention on success vs failure paths
- 2026-05-04 (Step 0.A) — **Layer placement (application-first reaffirmation):** Diagnose runtime function lives in `kernel.application/` (filename TBD in Step 0.B; pattern mirrors `derivation_check_runtime.py`). Diagnose request/result DTOs live in `kernel.application.protocol/` (filename TBD). Internal helpers (representability gate, primary selection, etc.) live alongside the runtime, **not** in `kernel.sdk/`. **No SDK shell** in MVP per `feedback_narrow_public_api`; any future SDK shell is a thin delegate after application API is self-sufficient. Any new typed payload (Q3 native atom-level dimension) lives in `kernel.application.protocol/` or `kernel.core.store._support`-adjacent (concrete location decided in Step 0.B; must not introduce SDK substrate).
- 2026-05-04 (Step 0.A) — **Q1 recommendation: Hybrid.** Diagnose internally calls `check_derivation_binding(...)` for the pass / fail / unsupported / invalid_request classification, then on `failed` dispatches to a lower-primitive walk for "why failed?" diagnostic detail. **Wrapper alone cannot reach atom-level info** because `CheckResult` discards per-branch state on `failed` (line 194-203 of `derivation_check_runtime.py` returns `evidence_envelope=None`). **Sibling alone duplicates** Check's representability gate, RuleRef preflight, primary selection. Hybrid pays one extra native eval pass on `failed` cases; acceptable for MVP, revisit in Step 0.B if cost matters or if Diagnose gains its own `_request_*_precheck` helper that supersets Check's.
- 2026-05-04 (Step 0.A) — **Cross-engine diagnostic asymmetry (per-engine MVP scope):**
  - **native:** per-atom localizer feasible via `_atom_satisfies` walk over `evaluate_native_where` bindings — full atom-level diagnosis MVP-scoped
  - **souffle:** `witness_ids_by_atom_key` retains per-atom witness IDs on successful path, but discarded on failure path (`adapters/souffle/engine_eval.py:164-165`); failed-path per-atom would require §3.4 adapter contract change — coarse-only for MVP
  - **problog:** trace `fail_event` exists in `provenance.py:70` parser but only attached to successful candidates' EvidenceGraph; failed-path provenance needs new `FailureProvenanceEnvelope` — coarse-only for MVP
  - **pyreason:** bottom-up engine, no proof for false conclusions; per-atom diagnosis inherently infeasible without engine instrumentation — coarse-only for MVP and likely v1+ as well
- 2026-05-04 (Step 0.A) — **Check archive integrity preserved:** Q1 Hybrid means Diagnose calls `check_derivation_binding(...)` for pass / fail classification. This call is **read-only** with respect to Check's contract:
  - `CheckResult` shape unchanged; Diagnose builds its own result DTO independently
  - `EvidenceEnvelope` shape unchanged; Diagnose's per-failed-case payload (when applicable) is a Diagnose-owned DTO, not added to `EvidenceEnvelope`
  - Check runtime function signature and behavior unchanged
  - No fields, statuses, or anti-patterns from Check archive blueprint §6 / Check topic doc §7 are reopened
  - In particular: Check's "no fail-localization on `failed`" decision (Check topic §3.8 / archive §6) holds. Diagnose-side fail localization is a **separate capability's** behavior, not a Check extension; the Check `cited` archived status is preserved.
- 2026-05-04 (Step 0.A) — **Q2 preliminary (request DTO):** Check-shaped (`plan + binding + engine`, side-channel `store + registry`), plus an optional `diagnostic_mode` discriminator only if MVP needs to return more than one diagnostic shape. To be frozen in Step 0.B.
- 2026-05-04 (Step 0.A) — **Q3 preliminary (status vocabulary dimensions):** Check's 4 statuses (`passed`, `failed`, `unsupported`, `invalid_request`) inherited unchanged. Diagnose introduces additional dimensions for `failed`-class differentiation:
  - **No-candidate dimension:** evaluated, no candidate
  - **Native atom-localized dimension:** native only — per-branch failed atom located
  - **Evidence-unavailable dimension:** engine advertised support but lookup returned None (per §6.3 must be observable, not silent-skip; consistent with §6.3 follow-up trace at line 517)
  Concrete status names and result-DTO field shapes are **0.B altitude** per Check 0.A vs 0.B precedent (Check 0.A committed only the `extract_match_binding` seam name; status enum members appeared at Check 0.B B6). 0.A names dimensions, not specific tokens.
- 2026-05-04 (Step 0.A) — **Q4 preliminary (granularity):** per-engine asymmetric — native atom-level, souffle / problog / pyreason coarse-only in MVP. Souffle's success-path per-atom info recorded as v1+ candidate; failed-path souffle / problog / pyreason atom info requires adapter contract changes (§3.4).
- 2026-05-04 (Step 0.A) — **Q5 preliminary (representability seam):** Diagnose has its own representability gates derived from per-engine failure-surface findings (cross-engine asymmetry bullet above): native passes all atom-level and coarse questions; souffle / problog / pyreason support coarse questions only in MVP. The gate function shape and name are **0.B altitude** (Check 0.A only committed the `extract_match_binding` seam name). Gates are locally hardcoded per engine for MVP — **not** because Check did so first, but because (a) §3.6 is currently in `deferred` topic state and (b) Diagnose alone lacks a second consumer of representability declarations to ground a declarative matrix.
- 2026-05-04 (Step 0.A) — **Q6 §3.6 trigger judgment:** Diagnose **CONFIRMS** concrete second-consumer pressure on engine-extension §3.6. The pressure is structural: Diagnose's per-engine diagnostic boundaries differ along multiple independent dimensions — per-atom localization availability, per-branch localization availability, evidence-miss surfacing semantics, coarse-only fallback behavior. Per-engine asymmetry is preserved and not reduced to a uniform grid (per §1.3 anti-flatten discipline).

  **Two distinct decisions, kept apart:**
  - **Topic-doc state of §3.6:** unchanged this round. Diagnose Step 0 has no authority to promote §3.6 from `deferred`; topic-doc promotion (open §6.6 to advance §3.6 vs leave it deferred) belongs to a separate post-ship decision.
  - **Diagnose MVP implementation:** locally hardcodes per-engine representability rules (mirrors Check pattern), **not** because §3.6 is deferred but because introducing a declarative capability matrix would itself require §3.6 to be promoted first.

  When the post-ship §6.6 round opens, the topic-doc text would record Diagnose as the second consumer that grounds §3.6 promotion. Until then, both Check and Diagnose hardcode locally.
- 2026-05-04 (Step 0.A) — **Engine-extension conformance commitments:**
  - **§6.3 (adapter contract):** Diagnose runtime, as a new capability, is bound by §6.3 Decision #5 (evidence-miss is observable contract problem, not silent-skip) without the Check MVP grandfather clause from §6.3 Non-Decisions. **Note:** §6.3 follow-up trace at line 517 places the same enforcement obligation on Check the moment Check's lookup-to-`None` paths are touched — so the §6.3 boundary binds Check and Diagnose symmetrically going forward; Diagnose is not uniquely "first" in any architectural sense, just the first new capability after Check. Diagnose's `failed`-class evidence-unavailable dimension must surface evidence-availability problems through warnings / errors in the result DTO, not silent-skip.
  - **§6.4 (engine options):** Diagnose request DTO does NOT add request-level `engine_options`. §6.4's promotion criterion governs the addition of `engine_options` to a request DTO. Any `diagnostic_mode` field (if added in Step 0.B) is a capability-interaction field on the Diagnose request DTO, not an `engine_options` field; therefore §6.4 promotion criterion is not engaged. The classification "capability interaction, not engine configuration" is a Diagnose Step 0 assertion — §6.4 text itself does not define what counts as engine option vs capability field, so the boundary is asserted by Diagnose, not affirmed by §6.4.
  - **§6.5 (payload typing):** Diagnose's native atom-level dimension implies one new typed payload kind (concrete shape and name decided in Step 0.B). §6.5 migration trigger (lines 652–658) has **two conjunctive criteria**: (a) a capability beyond Check needs to consume engine payloads in a way Check did not, **AND** (b) "local typed unions no longer express the shared contract clearly." Diagnose meets (a). Criterion (b) is **NOT** met: a 3-member typed Union (existing two members + one Diagnose-side payload) still expresses each engine payload type explicitly. Therefore **§6.5 working hypothesis remains intact**; widening from 2 to 3 members is default behavior under the working hypothesis, not a migration choice. Re-evaluate criterion (b) only if union widening starts to obscure the shared contract (per §6.5 line 658 wording "no longer express the shared contract clearly"); no specific member-count threshold is imposed here.
- 2026-05-04 (Step 0.A) — **Step 0.A pivotal decisions** (per Check 0.A altitude precedent of one structural decision + one named seam): **Q1 = Hybrid** (architectural composition: Diagnose calls `check_derivation_binding(...)` for pass / fail and dispatches to lower-primitive walk on `failed`) **AND Q4 = native atom-level + non-native coarse-only** (per-engine MVP scope). All other Step 0.A entries are conformance commitments to existing topic-doc decisions (§6.3 / §6.4 / §6.5) or preliminary stances frozen at 0.B altitude (Q2 request DTO / Q3 status vocabulary / Q5 representability seam shape).
- 2026-05-04 (Step 0.A) — **Step 0.B entry point:** Step 0.B should freeze:
  1. request DTO shape including any `diagnostic_mode` field
  2. result DTO shape and concrete status vocabulary names (covering Q3 dimensions)
  3. concrete shape and name for the new typed payload kind (Q3 native atom-localized dimension)
  4. per-engine representability table grounding `_request_diagnostic_representability_precheck` (working name) shape and location
  5. evidence-unavailable status semantics per §6.3 observability rule
  Blueprint stays `draft` until Step 0.D lifts these decisions into §5 / §7 / §8 and moves status to `scoped`.
