# Task Blueprint Audit: Diagnose Operation

- Blueprint: [2026-05-04_diagnose-operation.md](./2026-05-04_diagnose-operation.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-04 | draft | Blueprint created | Opened as the second application capability candidate after Check. Purpose is Step 0 only: freeze Diagnose DTO / algorithm / engine boundary before any implementation. |
| 2026-05-04 | draft | Step 0.A source pass opened | Initial anchors recorded from Check protocol/runtime, archived Check blueprint/audit, application common protocol DTOs, baseline P0-3 support artifacts, and engine-extension §6.3 / §6.4 / §6.5. |
| 2026-05-04 | draft | Step 0.A source pass complete | Native primitives + Check runtime fully mapped; Explore-agent reported non-native failure surfaces (souffle / problog / pyreason); cross-engine diagnostic asymmetry confirmed (steeper than Check's); Q1 stance **Hybrid**; Q2–Q5 preliminary stances recorded; **§3.6 second-consumer pressure confirmed but MVP keeps §3.6 deferred** per topic §6.2 wave ordering. Blueprint remains `draft`; no implementation until Step 0.B / 0.C / 0.D complete. |
| 2026-05-04 | draft | Step 0.B DTO contract freeze (with Q1 revision) | Q1 revised from **Hybrid → Sibling**: Hybrid would inherit Check's silent-skip on lookup-miss for non-native engines, violating Diagnose's independent §6.3 Decision #5 binding. 12 sub-decisions D1–D12 frozen across 5 deliverables: Request DTO (D1–D4), Result DTO (D5–D7), Evidence/Payload (D8–D9), Representability (D10–D11), Evidence-miss semantics (D12). Evidence-unavailable maps to `status="unsupported"` per §6.3 line 513 endorsement (NOT broader-than-Check `failed`, NOT a 5th status). Blueprint remains `draft` pending Step 0.C algorithm freeze + 0.D lift. |
| 2026-05-04 | draft | Step 0.C algorithm + drift-prevention freeze | C1–C8 frozen: C1 native algorithm two-phase dispatch (pass/fail classification + atom localization on failed); C2 atom-localizer walk semantics (deliberate initial-env injection, NOT a §7.1 violation because pass/fail already classified); C3 deterministic primary failure selection (most-progressed branch, tie-break by branch_index ascending); C4 non-native algorithm with evidence-miss precedence over no_candidate; C5 RuleRef preflight as Diagnose's own copy; C6 runtime failure propagation (mirror Check C7); C7 §7-Diagnose-1 through §7-Diagnose-7 anti-regression mapping; C8 concrete function decomposition. Blueprint remains `draft` pending Step 0.D lift. |
| 2026-05-04 | draft → scoped | Step 0.D lift complete | Step 0.B/0.C decisions lifted into blueprint §5 (Proposed Shape now contains 8 sub-sections: concept, request DTO, result DTO + nullable matrix, DiagnoseAtomLocator, per-engine representability table, algorithm overview, engine-extension conformance commitments, Q1 supersede record), §7 (Acceptance restructured into 5 sub-sections: Step 0 closure, §7-Diagnose-1–§7-Diagnose-7 anti-regression gates, layer placement, code health, cross-doc updates), §8 (Implementation Plan extended into 8 ordered steps from protocol DTOs through close-out). Blueprint status `draft → scoped`. The Step 0 gate closes here; implementation can begin. |

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

- 2026-05-04 (Step 0.B) — **Q1 supersede: Hybrid → Sibling.** Step 0.A audit's **"Step 0.A pivotal decisions" bullet** recorded **Q1 = Hybrid** as one of two pivotal architectural decisions (with Q4 = native atom-level + non-native coarse-only). Step 0.B sketch surfaced an architectural tension: Hybrid causes Diagnose to call `check_derivation_binding(...)` internally; Check internally silent-skips lookup-miss on non-native engines (`derivation_check_runtime.py:325` `_souffle_check`, `:473` `_problog_pyreason_check` — `if envelope_payload is None: continue`); therefore Diagnose-via-Hybrid would launder Check's grandfathered silent-skip into Diagnose's behavior, violating Diagnose's independent §6.3 Decision #5 binding (per Step 0.A Engine-extension conformance commitments §6.3 sub-bullet). **Q1 = Hybrid is superseded by Q1 = Sibling:** Diagnose owns its full dispatch (representability gate, evaluator dispatch, typed lookup, primary selection, evidence-miss detection); Diagnose does **NOT** call `check_derivation_binding(...)` internally. Duplication with Check's representability gate and RuleRef preflight is accepted as MVP cost; deferral grounding is recorded at D11 (per topic §1.3 working discipline: locally hardcoded stays until §3.6 promotes to declarative form OR a third capability surfaces shared-helper pressure). The Step 0.A entries about Q1 Hybrid (the "extra native eval pass on `failed`" cost analysis, Hybrid-specific framing) are factually stale per this supersede; they remain in the audit as 0.A history but are not the current contract.

- 2026-05-04 (Step 0.B) — **D1 — Request DTO single-plan only.** `DiagnoseRequest` carries a single `CompiledDerivationPlan`. Multi-plan rejection at DTO post_init (Python `TypeError` on unexpected kwargs is the anti-regression gate). Multi-plan is evaluate orchestration's responsibility, not Diagnose's. Mirrors Check 0.B B1.

- 2026-05-04 (Step 0.B) — **D2 — Binding shape.** Binding wire = `BindingItems` typedef from `core/store/_support` (sorted tuple, immutable). DTO post_init validator: `$`-prefix variable name, duplicate-impossible. Mirrors Check 0.B unchanged.

- 2026-05-04 (Step 0.B) — **D3 — Engine literal required.** `engine: Literal["native", "souffle", "problog", "pyreason"]` required field, no default. Mirrors Check 0.B B3.

- 2026-05-04 (Step 0.B) — **D4 — No `diagnostic_mode` field in MVP.** Engine determines diagnostic depth: native → atom-localized; non-native → coarse-only. Reasoning is **Diagnose-side, not §6.4-derived**: §6.4 promotion criterion governs `engine_options` placement only, and §6.4 text does not define what counts as engine option vs capability-interaction field (per Step 0.A §6.4 conformance commitment). A `diagnostic_mode` field on `DiagnoseRequest` would be a capability-interaction field outside §6.4's scope. Diagnose 0.B independently chooses to omit `diagnostic_mode` because MVP has no concrete consumer scenario where user wants explicitly coarse-on-native; engine asymmetry already determines the result shape. v1+ may add `diagnostic_mode` if user-controllable depth becomes needed.

- 2026-05-04 (Step 0.B) — **D5 — Status enum + `failure_kind` field; evidence-unavailable placement.** Status enum stays Check's 4 values verbatim: `passed` / `failed` / `unsupported` / `invalid_request`. New orthogonal field `failure_kind: Literal["no_candidate", "atom_localized"] | None`; populated only when `status = "failed"`, None otherwise.

  **Critical decision (per user 0.B-altitude caution):** evidence-unavailable maps to `status = "unsupported"`. Per §6.3 line 513: *"If missing evidence prevents the capability from answering the request, the result should be classified as unsupported / evidence-unavailable rather than semantic `failed`."* Three concrete options were considered; two are explicitly rejected:

  - **Rejected — Option α: Diagnose `status="failed"` broader than Check's `failed`.** Would require adding `failure_kind="evidence_unavailable"` enum value with `matched_count=None`. Rejected because §6.3 line 513 explicitly says evidence-miss is *"unsupported / evidence-unavailable rather than semantic `failed`"*; broadening `failed` would silently disagree with Check's `failed` semantics (*"evaluated, no semantic match"*) and create cross-capability interface drift.
  - **Rejected — Option β: Add a 5th top-level status (e.g., `evidence_unavailable`).** Would extend the status enum from 4 to 5 values. Rejected because §6.3 line 513 endorses `unsupported`; extending the enum diverges from Check's interface without semantic gain (caller learns the specific case via `errors` either way).
  - **Chosen — Option γ: `status="unsupported"`.** Reuses Check's existing 4-value status enum (interface consistent), §6.3 explicitly endorses, caller learns evidence-miss specifically via `errors` (`EVIDENCE_LOOKUP_MISS` code).

  Implication: Diagnose `status = "failed"` is **NOT broader** than Check's `failed` — both mean *"evaluated, no semantic match."* Evidence-availability problems route to `status = "unsupported"` (alongside Check's pre-existing representability-unsupported case).

- 2026-05-04 (Step 0.B) — **D6 — Result DTO nullable matrix.**

  | status | failure_kind | matched_count | matched_binding | diagnostic_payload | errors |
  |---|---|:---:|:---:|:---:|:---:|
  | `passed` | None | ≥1 | populated | None | empty |
  | `failed` | `no_candidate` | 0 | None | None | empty |
  | `failed` | `atom_localized` | 0 | None | populated | empty |
  | `unsupported` | None | None | None | None | required |
  | `invalid_request` | None | None | None | None | required |

  `unsupported` covers both Check's pre-existing unsupported-by-representability AND Diagnose's evidence-unavailable case (errors carry the specific code: `BINDING_NOT_REPRESENTABLE` / `ENTITY_TARGET_NOT_REPRESENTABLE` / `EVIDENCE_LOOKUP_MISS`). `requested_binding` echoes normalized `BindingItems` when DTO construction succeeds.

- 2026-05-04 (Step 0.B) — **D7 — Errors and warnings reuse.** `ErrorDTO` / `WarningDTO` from `application.protocol.common` (mirrors Check 0.B B7). Error codes are descriptive SCREAMING_SNAKE_CASE, no `DIAGNOSE_` prefix (mirrors Check). Code inventory:
  - **`EVIDENCE_LOOKUP_MISS`** (new — §6.3 evidence-unavailable case under `status = "unsupported"`)
  - Reused from Check: `BINDING_NOT_REPRESENTABLE`, `ENTITY_TARGET_NOT_REPRESENTABLE`, `UNKNOWN_VARIABLE_IN_BINDING`, `REGISTRY_REQUIRED`, `RULE_REF_UNRESOLVABLE`, `MULTI_HEAD_PLAN_NOT_SUPPORTED`

- 2026-05-04 (Step 0.B) — **D8 — `DiagnoseAtomLocator` typed payload class.** New frozen dataclass for the native atom-localized failure case: `DiagnoseAtomLocator(branch_index: int, failed_atom_index: int, attempted_binding: BindingItems)`. 3 required fields, all populated when present. Lives in `kernel.application.protocol/` (concrete filename decided at 0.D lift). **Top-level atom only** in MVP — when failed atom is `not(...)` or compound, `failed_atom_index` points at the top-level atom in `branch[i]`; nested-atom path tracking is deferred to v1+. **DiagnoseAtomLocator is a capability-output payload** (Diagnose-owned, computed by Diagnose runtime from native primitives), **not an engine-native payload**. The `EvidenceEnvelope.engine_payload` typed Union (`SupportArtifact | ProvenanceEnvelope`) is **unchanged** by this addition (per D9); DiagnoseAtomLocator lives in a separate Diagnose-owned slot. Therefore §6.5 (which governs engine-native payload typing) is **not engaged** — see D8.note below for §6.5 scope clarification.

- 2026-05-04 (Step 0.B) — **D8.note — §6.5 scope clarification (refines 0.A §6.5 conformance commitment).** Step 0.A audit's §6.5 conformance commitment described Diagnose as widening the typed Union to 3 members under §6.5 working hypothesis (with conjunctive criterion analysis (a) met / (b) not met). On 0.B re-examination during conformance review, that framing was imprecise: **§6.5 governs the engine-native payload typing for `EvidenceEnvelope.engine_payload`** (per topic §6.5 lines 642–648: *"in-process payload shape"*, *"Engine-native payloads must stay inspectable"*). Members of that Union (`SupportArtifact`, `ProvenanceEnvelope`) are produced **by engine adapters** as proof artifacts. DiagnoseAtomLocator is produced by **Diagnose runtime** from native primitives, not by an engine adapter — it is **capability-output payload**, outside §6.5 scope. The §6.5 trigger analysis (criterion (a) AND (b)) was therefore not applicable; §6.5 working hypothesis is preserved trivially because Diagnose does not modify the engine_payload Union. The 0.A §6.5 conformance entry remains as audit history; its "widening to 3 members" wording is **superseded by this 0.B clarification**. Going forward, §6.5 is engaged only when a new engine-native payload kind is added (i.e., when an adapter starts producing a new proof artifact type).

- 2026-05-04 (Step 0.B) — **D9 — `diagnostic_payload` field placement on `DiagnoseResult`.** Direct field `diagnostic_payload: DiagnoseAtomLocator | None` on `DiagnoseResult`. Populated only when `status = "failed"` AND `failure_kind = "atom_localized"`; None otherwise. **`DiagnoseResult` does NOT reuse Check's `EvidenceEnvelope`** (per Round 2 Check archive integrity preservation; Check's `EvidenceEnvelope` shape unchanged). **`DiagnoseResult` does NOT carry Check's evidence_envelope on `passed`** — this is an **independent UX decision** (not just a Sibling consequence): Diagnose's primary value is the diagnostic answer for failed / unsupported cases; on `passed`, `matched_binding` is sufficient and a caller wanting Check's evidence_envelope can independently call Check. Bundling Check's `EvidenceEnvelope` into `DiagnoseResult` would (a) duplicate retrieval work for callers using both capabilities, and (b) couple `DiagnoseResult` shape to Check's evidence model so future Check evidence-shape evolution would drag Diagnose along. `DiagnoseResult` final field set:
  - `status: Literal["passed", "failed", "unsupported", "invalid_request"]`
  - `requested_binding: BindingItems`
  - `matched_binding: BindingItems | None` (populated on `passed`)
  - `matched_count: int | None`
  - `failure_kind: Literal["no_candidate", "atom_localized"] | None`
  - `diagnostic_payload: DiagnoseAtomLocator | None`
  - `errors: tuple[ErrorDTO, ...]`
  - `warnings: tuple[WarningDTO, ...]`

- 2026-05-04 (Step 0.B) — **D10 — Per-engine representability table (locally hardcoded).**

  | Engine | passed | failed.no_candidate | failed.atom_localized | unsupported.representability | unsupported.evidence_unavailable | invalid_request |
  |---|:-:|:-:|:-:|:-:|:-:|:-:|
  | native | ✓ | ✓ | ✓ | n/a | rare | ✓ |
  | souffle | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ |
  | problog | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ |
  | pyreason | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ |

  Per-cell rationale (engine mechanism + code-path citations) is recorded at the **Step 0.A "Cross-engine diagnostic asymmetry" bullet** (q.v.) — it is 0.A-altitude evidence, not re-emitted at 0.B. Representability rules are **locally hardcoded** in Diagnose runtime, not declarative — §3.6 declarative capability matrix remains deferred per topic state.

- 2026-05-04 (Step 0.B) — **D11 — Diagnose runtime dispatch invariants** (0.B altitude — concrete function decomposition + signatures decided at 0.C). Per Q1 Sibling supersede, only the dispatch invariants are committed at 0.B:

  - **Sibling invariant:** Diagnose does NOT call `check_derivation_binding(...)` — primary classification path is Diagnose's own
  - **Per-engine dispatch:** Diagnose has engine-specific entry points (one per engine in `{native, souffle, problog, pyreason}`); concrete function decomposition + signatures + names decided at 0.C
  - **Representability gate:** Diagnose owns its own request-level representability gate per D10 table; gate function shape and name decided at 0.C
  - **Typed lookup:** Diagnose calls `Store._lookup_support_artifact(...)` / `Store._lookup_provenance_envelope(...)` directly (typed internal API; mirrors Check's pattern but Diagnose owns its call site, not via shared helper)
  - **Module location:** Diagnose runtime in `kernel.application/` (filename decided at 0.D lift); no SDK shell

  Code-level duplication with Check's representability gate and RuleRef preflight is **deferred per topic §1.3** — locally hardcoded per-capability stays until §3.6 promotes to declarative form OR a third capability surfaces shared-helper pressure (per topic §1.3 "if a question requires a second consumer to answer responsibly, mark it deferred"). Not because Check did it first, but because §3.6 is currently in `deferred` topic state and Diagnose alone lacks a second consumer to ground a shared helper extraction.

- 2026-05-04 (Step 0.B) — **D12 — Evidence-miss observability semantics.** When the engine returns `CandidateSet` with `support_kind` advertising evidence-bearing payload (e.g., `souffle_witness_v1`, `problog_provenance_v1`, `pyreason_provenance_v1`) but `Store._lookup_support_artifact(...)` / `Store._lookup_provenance_envelope(...)` returns None, Diagnose:
  1. Classifies result with `status = "unsupported"` (per D5; **NOT** `status = "failed"` per §6.3 *"not semantic failure"*)
  2. Sets `failure_kind = None` (failure_kind only fires under `failed`)
  3. Attaches `ErrorDTO(code="EVIDENCE_LOOKUP_MISS", details={"support_kind": ..., "support_digest": ..., "candidate_key": ...})` to `errors`
  4. Optionally attaches `WarningDTO` if multiple candidates share the missing-evidence pattern (signals adapter contract problem worth surfacing)

  This applies uniformly to native + souffle + problog + pyreason; no engine is grandfathered. §6.3 follow-up trace at line 517 binds Check the moment Check's silent-skip path is touched, but that's Check's future obligation; Diagnose is independently bound now per §6.3 Non-Decisions ("does not change Check's current silent-skip MVP behavior" only protects Check, not new capabilities).

- 2026-05-04 (Step 0.B) — **Step 0.C entry point.** Step 0.C should freeze:
  1. Native algorithm: per-branch failed-atom selection rule when multiple branches partially satisfy (deterministic primary)
  2. Non-native algorithm: candidate enumeration → typed lookup → match → primary selection (mirroring Check 0.C C3 where applicable, but Diagnose owns its copy per Sibling pattern)
  3. RuleRef preflight: same pattern as Check's `_ruleref_preflight(...)` — Diagnose owns its own copy, no shared helper extraction in MVP
  4. Drift-prevention §7-style mapping: anti-regression test design for D5 evidence-unavailable-as-unsupported, D8 DiagnoseAtomLocator shape immutability, D9 no-EvidenceEnvelope-reuse, D11 Sibling no-Check-call invariant
  5. Runtime failure mapping: adapter exceptions / evaluator-not-registered → propagate (mirror Check 0.C C7), NOT wrapped into status enum
  6. Concrete dispatch function decomposition: signatures and names for the per-engine entry points (working names from 0.A: `_diagnose_native`, `_diagnose_souffle`, `_diagnose_problog_pyreason`) and the representability gate (`_request_diagnostic_representability_precheck` working name); 0.B D11 only commits dispatch invariants, not specific signatures

  Blueprint stays `draft` until 0.D lift completes.

- 2026-05-04 (Step 0.C) — **C1 — Native algorithm dispatch flow.** Per Q1 Sibling supersede, Diagnose native dispatch follows two phases:

  **Phase 1 — Pass / fail classification (mirrors Check native):**
  - Call `evaluate_native_where(view_facts, body, registry=registry, witness_facts=witness_facts, remember_support_artifact=...)` once
  - Subset-match each returned final binding against `request.binding`
  - On match: `status="passed"`, build `matched_binding` from primary; primary selection sort key `(branch_index, binding_items)` mirrors Check 0.C C4 native sort
  - On no match: proceed to Phase 2

  **Phase 2 — Atom localization (only on failed):**
  - Call `_localize_failed_atom(body, requested_binding, witness_facts, view_facts, rule_ref_resolutions)`
  - Return shape:
    - `DiagnoseAtomLocator` non-None → `status="failed"`, `failure_kind="atom_localized"`, `diagnostic_payload=locator`
    - None → `status="failed"`, `failure_kind="no_candidate"`, `diagnostic_payload=None`

  Diagnose pays Phase 2 cost only on failed cases. Native does not produce evidence-unavailable (D10 cell = "rare"); if in-process artifact write fails, the runtime error propagates per C6 rather than wrapping into `unsupported`.

- 2026-05-04 (Step 0.C) — **C2 — Native atom-localizer walk semantics.** `_localize_failed_atom` walks each branch with user's `requested_binding` as initial env (NOT `envs=[{}]` like Check's enumerate path). This is **deliberate initial-env injection for Diagnose** and is **NOT** a Check §7.1 trap violation:

  - Check §7.1 trap was: passing user partial to `_branch_satisfies` directly → silent-false on incomplete bindings → wrong pass/fail classification (a binding might be unsatisfiable for grounding reasons, not for semantic reasons)
  - Diagnose's case is: user partial is provably non-extending (Phase 1 already classified `failed`); goal is to localize WHERE in body_ir the partial fails to extend, not to classify pass/fail
  - Initial-env injection here is the correct primitive — silent-false trap does not apply at the **result-status** level because pass/fail is already classified by Phase 1

  **Atom-extension primitive (committed; addresses §7.1 risk at the atom-index level).** The atom-localizer **MUST NOT** call `_atom_satisfies` directly with `current_env` — `_ground_terms` returns `None` on missing var, which would silent-false any atom whose vars are not yet bound and produce the **wrong `failed_atom_index`**. Diagnose owns its own atom-extension helper (working name `_extend_env_with_atom`) that **explicitly enumerates** possible extensions for `(atom, current_env, view_facts, witness_facts, rule_ref_resolutions)` and returns `list[dict[str, Any]]`:
  - Empty list (no extensions exist) → atom semantically fails here; record candidate failure point
  - Non-empty list → one or more possible extensions; pick the **first deterministic** extension (extensions sorted by `(sorted(env.items()))` lex order) and continue

  This avoids the §7.1 silent-false trap at the atom-index level: "var not yet bound" is handled by **enumeration** (which may yield extensions), not by `_ground_terms` returning `None` (which would falsely classify the atom as failed).

  **Atom traversal order (committed: canonical body-source-order).** The localizer iterates atoms in **body-source order** via `for atom_index, atom in enumerate(branch)`. This order is determined by `branch_index` and source layout in `plan.body_ir`, **independent** of how `evaluate_native_where` traverses atoms internally. Reported `failed_atom_index` is the source-order index in `branch[i]`. (This decouples C3's `atoms_satisfied` count from any future change in evaluator atom-traversal order — see C3 determinism note.)

  **Per-branch walk:**
  - Filter out branches whose vars are disjoint from user's partial vars (cannot localize because user's bindings don't constrain anything in this branch)
  - For remaining branches: walk atoms in source order; for each atom, call `_extend_env_with_atom(atom, current_env, ...)`:
    - Empty result → record `(atoms_satisfied, branch_index, current_env_at_failure, failed_atom_index)`
    - Non-empty → extend `current_env` to the first deterministic extension and continue
  - First atom whose extension returns empty → candidate failure point

  **Edge case:** if no branch produces a candidate failure point (all branches' vars disjoint from user partial, or all branches extend cleanly through the source-order walk), `_localize_failed_atom` returns `None` → fallback to `failure_kind="no_candidate"`.

- 2026-05-04 (Step 0.C) — **C3 — Native primary failure selection (deterministic).** Among branches with candidate failure points, primary selection sort key:

  `sort key = (-atoms_satisfied, branch_index)`

  - **Most-progressed first** (`-atoms_satisfied`): the branch closest to satisfying user's partial is most diagnostically useful. A branch where atom 4 of 5 fails is more informative than a branch where atom 1 of 5 fails.
  - **Lowest branch_index breaks ties**: deterministic; mirrors Check 0.C C4 pattern (`branch_index` ascending).

  `attempted_binding` field on `DiagnoseAtomLocator` carries the env state at the moment of failure (sorted, normalized to `BindingItems`). It includes user's original requested_binding plus any extensions accumulated during the walk before the failed atom.

  **Determinism source.** C3's sort key relies on (a) C2's body-source-order walk and (b) `_extend_env_with_atom`'s deterministic enumeration (sorted extensions, first picked). Both are independent of `evaluate_native_where`'s internal atom-traversal order. Test fragility risk thereby contained: if `evaluate_native_where` changes traversal tomorrow, `atoms_satisfied` per branch is unaffected because the localizer walks body-source-order via Diagnose's own primitive.

- 2026-05-04 (Step 0.C) — **C4 — Non-native algorithm (souffle / problog / pyreason).** Per Q1 Sibling, Diagnose has its own non-native dispatch (Diagnose does NOT call Check):

  1. Run `evaluate_derivation_plans(DerivationEvaluateRequest(plans=(plan,), engine=engine), store=store, registry=registry)` to get candidates
  2. For each candidate, look up evidence:
     - souffle → `Store._lookup_support_artifact(candidate.support_digest)`
     - problog / pyreason → `Store._lookup_provenance_envelope(candidate.support_digest)`
  3. **Three-bucket classification per candidate:**
     - **Lookup-miss bucket:** lookup returned `None` → record candidate's `support_kind`, `support_digest`, `candidate_key` for `EVIDENCE_LOOKUP_MISS` error
     - **Match bucket:** lookup returned, extracted binding subset-matches `request.binding`
       - souffle binding extraction: `SupportArtifact.binding_items`
       - problog / pyreason binding extraction: head-var positional alignment from `candidate.payload["terms"]` (mirrors Check `_extract_head_var_binding`)
     - **No-match bucket:** lookup returned, extracted binding does NOT subset-match

  **Result classification rule (precedence-ordered):**
  - **Match bucket non-empty** → `status="passed"`, primary selection per Check 0.C C4 (souffle: `(branch_index, binding_items, candidate_key)`; problog/pyreason: `(candidate_key, binding_items)`)
  - **Match bucket empty AND lookup-miss bucket non-empty** → `status="unsupported"` (per D5/D12), `EVIDENCE_LOOKUP_MISS` errors per missing candidate, optional warning if pattern affects ≥2 candidates
  - **All buckets accounted, match empty, lookup-miss empty** → `status="failed"`, `failure_kind="no_candidate"`

  **Why precedence — lookup-miss outranks no_candidate:** evidence-miss is a contract problem (per §6.3 Decision #5); silently demoting it to `no_candidate` would launder Check-style silent-skip into Diagnose, violating the Q1 Sibling rationale.

  Non-native `failure_kind="atom_localized"` never fires per D10 representability table.

- 2026-05-04 (Step 0.C) — **C5 — RuleRef preflight (Diagnose's own copy).** Diagnose owns `_diagnose_ruleref_preflight(body, registry)` mirroring Check's `_ruleref_preflight(...)` (Diagnose does NOT import Check's preflight per Q1 Sibling):

  - Scan body for `("ruleref", rule_id, version, terms)` atoms
  - If ruleref present and `registry is None`: `REGISTRY_REQUIRED` error → `status="invalid_request"`
  - For each ruleref: `registry.resolve(rule_id, version)`; on `RuleCompileError`: `RULE_REF_UNRESOLVABLE` error with `details["reason"]` from exception → `status="invalid_request"`
  - Cycles / version-mismatch are NOT classified at preflight (mirror Check 0.C C5 softening); native eval surfaces them as runtime errors per C6

  Code-level duplication with Check's `_ruleref_preflight` is accepted per Q1 Sibling (D11 invariant); deferred refactor grounded in **two distinct topic rules**: (i) §1.3 anti-flatten / anti-taxonomy / "don't create abstraction only because Check needed local seam once" + (ii) §6.2 wave-ordering second-consumer rule (per topic §6.2 line 411, §3.6 deferral basis). Locally hardcoded stays until **either** §3.6 promotes (engine capability declaration) **or** a third capability surfaces concrete shared-helper pressure (per §6.2 second-consumer trigger). The earlier 0.B D11 phrasing combined these two rules into a single "§1.3" citation; this is precise but compressed — the substantive grounding is the same.

- 2026-05-04 (Step 0.C) — **C6 — Runtime failure mapping** (mirrors Check 0.C C7):

  - **Adapter exceptions during `evaluate_derivation_plans(...)`** → propagate (NOT wrapped into status enum)
  - **Evaluator-not-registered** for engine → propagate as `KeyError` / `ValueError` from `Store.evaluate_engine` (NOT wrapped)
  - **Engine binary unavailable** → propagate from adapter (NOT wrapped)
  - **DTO post_init failure** (e.g., `$`-prefix violation, multi-plan, unexpected kwargs) → `ProtocolShapeError` at construction time
  - **Diagnose-internal invariant violations** (e.g., atom-localizer detects unparseable atom kind) → `DiagnoseRuntimeError(code, path, details)` — narrow class for cases the runtime cannot meaningfully convert into `DiagnoseResult`; mirrors Check's `CheckRuntimeError`

  **Cycles / version-mismatch in RuleRef resolution:** not classified at preflight (per C5); native eval may raise `WhereValidationError` or similar; Diagnose lets these propagate as runtime errors (does NOT wrap into `unsupported` or `invalid_request`).

- 2026-05-04 (Step 0.C) — **C7 — Drift prevention §7-Diagnose mapping.** Each high-risk decision gets an anti-regression test class entry:

  - **§7-Diagnose-1 (D5 evidence-unavailable as `unsupported`, NOT `failed`):** test that engine-output with lookup-miss yields `status="unsupported"` with `EVIDENCE_LOOKUP_MISS` code; the audit forbids `status="failed"` with a hypothetical `failure_kind="evidence_unavailable"` enum value (which doesn't exist in the chosen enum)
  - **§7-Diagnose-2 (D8 / D8.note `DiagnoseAtomLocator` NOT in `EvidenceEnvelope` Union):** test that `EvidenceEnvelope.engine_payload` Union members are exactly `{SupportArtifact, ProvenanceEnvelope}`; `DiagnoseAtomLocator` lives only on `DiagnoseResult.diagnostic_payload`
  - **§7-Diagnose-3 (Q1 Sibling no-Check-call invariant):** static check (test-time assertion; concrete mechanism — AST walk / import-graph / `sys.modules` inspection — chosen at implementation time) that the Diagnose runtime module never imports `check_derivation_binding`, `derivation_check_runtime`, **or any private helper from the Check runtime module** (e.g., `_binding_matches`, `_request_representability_precheck`, `_ruleref_preflight`); banned-symbol list maintained alongside the test, extended when new Check internals appear
  - **§7-Diagnose-4 (C2 native atom-localizer correctness):** test cases verifying first-failed-atom is correctly identified for representative branches; explicitly tests that no successful atom is reported as failed
  - **§7-Diagnose-5 (D10 non-native `atom_localized` never fires):** test that `souffle` / `problog` / `pyreason` responses never include `failure_kind="atom_localized"` regardless of input shape
  - **§7-Diagnose-6 (D12 evidence-miss observable, never silent-skip):** test that an adapter-advertised `support_kind` with `None` lookup surfaces `EVIDENCE_LOOKUP_MISS` error in `DiagnoseResult.errors`, never silent-discards the candidate
  - **§7-Diagnose-7 (status enum invariance, D5):** **type-level invariant test** that `DiagnoseResult.status` Literal contains exactly the 4 Check values — `passed`, `failed`, `unsupported`, `invalid_request` — and no 5th value. Distinct from §7-Diagnose-1 which is a runtime-routing test: §7-Diagnose-1 verifies *behavior* (evidence-miss input routes to `unsupported`); §7-Diagnose-7 verifies *type structure* (Literal exact members). Both kept because they catch different drift modes (logic drift vs type drift).

  Anti-regression test class structure mirrors Check archive's `AntiRegressionTests`.

- 2026-05-04 (Step 0.C) — **C8 — Function decomposition shape** (per 0.B Step 0.C entry-point list item 6; **names + module path + role only — concrete signatures with parameter / return types decided at implementation time per Check 0.C altitude precedent**). The 0.B item 6 wording asked for "signatures and names"; on 0.C re-examination, parameter / return types are implementation-altitude. 0.C commits names + roles; types emerge with the code.

  **Public entry:**
  - `diagnose_derivation_binding` — public entry; takes `request` plus side-channel `store` and optional `registry`; returns `DiagnoseResult`

  **Private gates and preflight:**
  - `_request_diagnostic_representability_precheck` — D10 table check; runs first; returns error tuple if non-native request not representable
  - `_diagnose_ruleref_preflight` — C5 logic; scans body for ruleref atoms; returns error tuple per registry / resolution failures

  **Per-engine dispatchers:**
  - `_diagnose_native` — C1 + C2 + C3 (Phase 1 + Phase 2 + primary selection)
  - `_diagnose_souffle` — C4 + souffle binding extraction (`SupportArtifact.binding_items`)
  - `_diagnose_problog_pyreason` — C4 + payload-term head-var alignment

  **Algorithm helpers:**
  - `_localize_failed_atom` — C2 walk; returns `DiagnoseAtomLocator | None`
  - `_extend_env_with_atom` — C2 atom-extension primitive (sibling to evaluate_where's per-atom logic; explicitly enumerates extensions; handles "var not yet bound" by enumeration, not by `_ground_terms` returning `None`)
  - `_classify_non_native_buckets` — C4 three-bucket split (lookup-miss / match / no-match) per candidate

  **Binding extraction helpers:**
  - `_extract_souffle_binding` — souffle-specific (`SupportArtifact.binding_items`)
  - `_extract_payload_term_binding` — problog / pyreason (head-var positional alignment per Check `_extract_head_var_binding` precedent)

  **Result construction helpers (Diagnose-side copies per Q1 Sibling):**
  - `_diagnose_binding_matches` — subset-match predicate (Diagnose's copy; mirrors Check `_binding_matches` per Q1 Sibling D11 invariant)
  - `_diagnose_invalid_request` — `DiagnoseResult` factory for `status="invalid_request"` paths (mirrors Check `_invalid_request` factory)

  **Narrow exception:**
  - `DiagnoseRuntimeError(ValueError)` mirroring `CheckRuntimeError`

  All in `kernel.application/diagnose_runtime.py`; concrete parameter / return types + LOC-level decomposition decided at implementation time.

- 2026-05-04 (Step 0.C) — **Step 0.D entry point.** Step 0.D should:
  1. Lift Step 0.B/0.C decisions into blueprint §5 Proposed Shape (frozen request/result DTO contract; algorithm overview per engine; representability table; evidence-miss semantics)
  2. Lift drift-prevention §7-Diagnose-1 through §7-Diagnose-7 into blueprint §7 Acceptance (each as a testable anti-regression gate)
  3. Lift implementation steps into blueprint §8 Implementation Plan (per-engine dispatch + helpers + tests, ordered for incremental commits)
  4. Move blueprint status `draft → scoped`

  After 0.D, implementation can begin without re-litigating concept, DTO shape, or algorithm. The Step 0 gate closes when 0.D commits.

- 2026-05-04 (Step 0.D) — **Step 0.D lift complete; status `draft → scoped`.** Blueprint sections §5 / §7 / §8 lifted from Step 0.B (D1–D12) and Step 0.C (C1–C8) decisions:

  - **§5 Proposed Shape** now carries the frozen contract in 8 sub-sections (concept, request DTO, result DTO + nullable matrix, DiagnoseAtomLocator, per-engine representability table, algorithm overview, engine-extension conformance commitments, Q1 supersede record). §5 is the single canonical contract reference for implementation; audit Decision Notes retain the design trace.
  - **§7 Acceptance** restructured into 5 sub-sections: Step 0 closure (paperwork; 0.A/0.B/0.C/0.D checked), §7-Diagnose-1–§7-Diagnose-7 anti-regression gates (mapped to D-decisions per C7), layer placement (application-first), code health (tests + ruff), cross-doc updates (engine-extension topic untouched unless §3.6 promoted; application docs synced; conformance audit at close-out).
  - **§8 Implementation Plan** extended into 8 ordered implementation steps (Step 1 protocol DTOs → Step 2 native MVP → Step 3 native hardening → Step 4 non-native gate → Step 5 souffle → Step 6 problog/pyreason → Step 7 drift-prevention tests → Step 8 close-out + status transition). Step 0 phases retained in §8 for traceability.

  **Cross-consistency check (post-lift):** §5 contract references each D-decision and C-decision; §7 anti-regression gates map each high-risk D-decision to a testable assertion; §8 implementation steps reference both decisions and gates. No D-decision or C-decision was dropped during lift; the Q1 supersede + §6.5 scope clarification (D8.note) are explicitly recorded in §5.7 and §5.8.

  **Status transition:** `draft → scoped`. Step 0 gate closed. Any future change to the §5 contract, §7 acceptance gates, or §8 plan requires a new audit entry + blueprint update before code changes (per Check 0.D precedent).

  Implementation begins at §8 Step 1 (protocol DTOs); no code written yet.
