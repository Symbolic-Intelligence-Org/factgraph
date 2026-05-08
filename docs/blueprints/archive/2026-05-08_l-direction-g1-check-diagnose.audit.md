# Audit Log — L Direction G1 (Check + Diagnose SDK Shell)

| Date | Status | Event | Details |
|------|--------|-------|---------|
| 2026-05-08 | draft | Blueprint created | First draft seeded after L direction Step 0 framing rounds (Q1 + Q2 + Q3 + 7 Step 0 questions). Q1 locked option-4 variant: G1-only first, sequential order G1 → G4 → G2 → G3 → G5, each group own blueprint per Batch 8 §5.5.5. Q2 locked A as hard dependency (`build_check_request`, `build_diagnose_request`, `CapabilityHelperError`, `OriginPackageError` only — no internals); B as conditional via §5.2 Step 0 falsifier. Q3 locked `kernel.sdk` namespace continuation; rebrand to `factpy` is independent publish-day or product-naming blueprint, out of L/G1 scope. Principle lock set: `#1`, `#3`, `#4a`, `#5`, `#6`, `#11` (conditional), `#12` (conditional), `#19`, `#P0`, `#P1`. Seven Step 0 questions documented in §5: scenario-vs-per-method API, return shape (B-typed-wrap / raw passthrough / documented passthrough), error mapping, `__all__` exposure, module location, test layout, SDK-side input shape. Non-goals enumerated in §3 cover scenario pre-lock, return-shape pre-lock, README quickstart, A internals, factpy rebrand, G2-G5 work, demo migration. Status remains `draft` pending Step 0 falsifier round; scope-freeze deferred until §5.1–§5.7 are resolved. |
| 2026-05-08 | draft | Self-review revision | Self-review against 5 user-defined criteria. Items 3/4/5 clean (README+factpy explicit forbids in §3 and §6; A+B baseline citation `v0.1-public-surface-helpers-walker-2026-05-08` correct in §1 and §4.5; §7 Acceptance contains only draft-ready items with scoped acceptance properly deferred). Items 1/2 had minor neutrality issues: §5.1 Pro per-method asymmetric (only anti-merge args, no positive features), §5.2/§4.4 had editorial wording leaning B-typed-wrap. Surgical edits applied: §5.1 Pro per-method line restructured to add 3 positive features (explicit per-capability semantics; mirrors application-layer 1:1 split; lower outward commitment, no `FailureExplanation` hybrid type) before citing `#3` as backing principle; §5.2 first tension bullet "natural SDK shape" → "consistent with existing typed-DTO SDK pattern"; §4.4 prior-art table "alignment template" → "alignment reference". Draft now neutral on scenario-vs-per-method and B-wrapped-vs-passthrough decisions; ready for Step 0 falsifier round. |
| 2026-05-08 | draft | §5.1 decision locked | Read-only falsifier pass against scenario-vs-per-method API. Outcome: G1 ships two SDK entrypoints (Check, Diagnose); scenario merge `sdk.explain(...)` rejected for this blueprint, remains future Direction C composition. Five evidence sources cited in §5.1 Decision block: (1) [20_candidates.md §C] `sdk.explain` hypothetical + outward-compat lock-in on ship; (2) [41_application-builders-design-sketch.md §3.1] A's separate-builders rationale via `#3`; (3) [derivation_diagnose.py module docstring] Q1 Sibling decoupling at protocol layer; (4) [derivation_diagnose.py DiagnoseResult docstring] no `EvidenceEnvelope` on Diagnose; (5) [derivation_check.py CheckResult.__post_init__ lines 138-139, 147-148] evidence_envelope only on `passed`, `failed` enforced via active `raise ProtocolShapeError`. Three falsifier requirements evaluated: F1 not satisfied (no source-grounded user workflow), F2 blocked (evidence-on-failure semantics absent at protocol layer AND mechanically rejected at construction), F3 satisfied (per-method composition stays caller-side, mirrors application-layer 1:1). Net: scenario merge would require either (a) internal composition with no outward semantic gain, (b) violating Q1 Sibling, or (c) inventing hybrid evidence-on-failure semantics that application protocol's `__post_init__` actively rejects — turning `#1` layer-inversion concern from abstract to mechanical. §7 acceptance bullet updated: §5.1 done, §5.2-5.7 pending. |
| 2026-05-08 | draft | §5.2 decision locked | Read-only falsifier pass against return-shape (B-typed-wrap / raw passthrough / documented passthrough). Outcome: documented passthrough for both methods — `sdk.check(...) -> CheckResult`, `sdk.diagnose(...) -> DiagnoseResult`; B dependencies inactive for G1 v1 (no `SupportArtifactView` / `AssertionView` / `parse_atom_key` / `WalkerError` remap); `CheckResult` / `DiagnoseResult` may appear as return annotations / imports inside G1 but are NOT re-exported from `kernel.sdk.__all__`; SDK docstrings mention opt-in advanced importable workflow without G1 importing B types; SDK-typed wrappers deferred as future `#P1` trigger. Five evidence sources cited in §5.2 Decision block: (1) [ingest.py:81-86] `ValidationReport` is SDK-owned frozen dataclass for provenance diagnostics, NOT a wrapping precedent over application DTOs; (2) [store.py:773 / 776] `evaluate_compiled` returns `list[CandidateSet]` / `accept` returns `AcceptResult` — SDK has established raw-passthrough precedent for non-SDK types; (3) [01_alignment_matrix.md §3 line 36] `kernel.sdk.__all__` boundary is about exports, not return types; (4) [views.py:495-509] `SupportArtifactView.__init__` requires `frozen_claim_index: Mapping[str, Claim]` (positional, no default) — G1 wrap forces new substrate inside `kernel.sdk`, `#1` violation; (5) [derivation_diagnose.py:80-104] `DiagnoseAtomLocator` has `branch_index` / `failed_atom_index` / `attempted_binding`, NO atom-key string — `parse_atom_key` from B has no input, mechanically moot. Decisive insight: B-typed-wrap is not just outward commitment concern but mechanically blocked (point 4 forces new substrate, point 5 has no input). Three falsifier requirements evaluated: F1 blocked (B-typed-wrap not technically viable today), F2 satisfied (quickstart unchanged, docstring opt-in only), F3 satisfied (`CheckResult` / `DiagnoseResult` appear only as return annotations, not in `__all__`, consistent with `evaluate_compiled` / `accept` precedent). §6 principle table updated: `#11` `.underlying` → Inactive for G1 v1 (resolves 2026-05-08); `#12` Error boundaries → Partial (`OriginPackageError` active per §5.3, `WalkerError` inactive). §7 acceptance updated: §5.1 + §5.2 done, §5.3-5.7 pending. |
| 2026-05-08 | draft | §5.3 decision locked | Read-only falsifier pass against error mapping strategy. Outcome: G1 remaps both `CapabilityHelperError` and `OriginPackageError` to `SDKStoreError` with exception chaining (`raise SDKStoreError(...) from exc`); `path` set per call-site (e.g. `$.check`, `$.diagnose`); `code` optional at Step 0; no new SDK error subclass introduced (no `SDKLoweringError`, no `SDKCapabilityError`); `WalkerError` remap moot per §5.2 lock. Five evidence sources cited in §5.3 Decision block: (1) [errors.py] SDK error hierarchy is intentionally small (8 classes total, no capability-specific family); (2) [00_user_guide.md §9.0 lines 1080+1086] docs classify SDK facade input/constraint failures under `SDKStoreError` with structured `code`/`path`; (3) [store.py:845-848 / 939-940] existing SDK lowering wraps `compile_authoring_rule_v1` / `_derivation_v1` exceptions as `SDKStoreError(...) from exc` — G1 inherits this pattern; (4) [ingest.py:448-453 / query_runtime.py:112-123] SDK/application bridge maps `ErrorDTO` to `SDKStoreError` preserving code+path — established wrap-with-translation pattern; (5) [capability_helpers/errors.py] `CapabilityHelperError(ValueError)` + `OriginPackageError(CapabilityHelperError)` are application-helper errors, not SDK API errors — must be caught at SDK boundary and remapped. Implementation note: single `except CapabilityHelperError as exc:` catches both; `isinstance(exc, OriginPackageError)` differentiates if `code` divergence is needed. Falsifier outcomes: Q1 `OriginPackageError` remap target = `SDKStoreError` (subclass would be unique-to-G1, propagation would leak application types); Q2 walker exceptions moot per §5.2; Q3 zero new SDK error subclasses needed; `#6` minimality satisfied. §6 `#12` row updated: from "Partial" to "Resolved" with both A errors remap to `SDKStoreError`. §7 acceptance updated: §5.1 + §5.2 + §5.3 done, §5.4-5.7 pending. |
| 2026-05-08 | draft | §5.6 decision locked | Read-only falsifier pass against test layout (flat per-method / combined `test_sdk_g1.py` / extend existing / nested `tests/sdk/`). Outcome: flat per-method tests `src/kernel/tests/test_sdk_check.py` + `src/kernel/tests/test_sdk_diagnose.py`; shared fixtures `_sdk_g1_fixtures.py` only on demand (sdk_ prefix added per `test_sdk_*` convention, refines blueprint default `_g1_fixtures.py`); no combined file; no extension of unrelated SDK tests; no nested `tests/sdk/` directory. Five evidence sources cited: (1) [30_recommendation.md §`#19`] flat unittest, flat fixtures, no Hypothesis; (2) [40_walker-mechanism-design-sketch.md §6] B walker tests flat at `test_application_walker.py`, no nested dir; (3) [41_application-builders-design-sketch.md §6] A helper tests flat at `test_application_capability_helpers.py`, no nested dir; (4) repo scan: 8 existing `test_sdk_*.py` files all flat in `src/kernel/tests/`; existing fixture pattern is single `_test_helpers.py`, underscore-prefixed, no nested dirs; (5) §5.6 default in blueprint already pointed here. Per-method beats alternatives: combined would reintroduce surface §5.1 explicitly split; extended dilutes ownership; nested forbidden by `#19` with zero precedent. §7 acceptance updated: §5.1 + §5.2 + §5.3 + §5.4 + §5.5 + §5.6 done; only §5.7 pending. |
| 2026-05-08 | draft | §5.7 decision locked + architectural correction | Read-only falsifier pass against SDK-side input shape. Outcome: G1 accepts SDK `Derivation` only (NOT `Rule`); binding `Mapping[str, Any]` only with `$`-prefixed string keys; engine + registry kwargs match `sdk.evaluate(...)` precedent. Rejected for G1 v1: `Rule` (wrong semantic family — sdk.run path), `CompiledDerivationPlan` (application protocol type, advanced users call A directly), raw derivation/compiled dicts, `BindingItems`, `LogicVar` binding keys. Final signatures: `SDKStore.check(derivation, binding, *, engine="native", registry=None) -> CheckResult` + `SDKStore.diagnose(derivation, binding, *, engine="native", registry=None) -> DiagnoseResult`. **Critical: this lock surfaced an architectural drift** — earlier blueprint sections (§1, §2, §3, §4.4, §5.7, §6) incorrectly cited "SDK `Rule`" / `compile_authoring_rule_v1` / `_compile_rule_input` as G1 lowering target. Corrected: G1 lowering uses `_compile_derivation_input` (store.py:899-940) + `_compiled_derivation_plan_to_application` (store.py:1490+) for `Derivation → CompiledDerivationPlan`. `_compile_rule_input` (store.py:619+) is the `Rule → RuleSpec` path used by `sdk.run(...)`, NOT G1. Five evidence sources: (1) [derivation_check.py:84-94] CheckRequest.plan: CompiledDerivationPlan with single-head requirement; (2) [derivation_diagnose.py:107-127] DiagnoseRequest same shape; (3) [rule.py:129-152] Derivation.to_authoring_payload produces derivation-shaped dict; (4) [store.py:692-717] sdk.evaluate already lowers Derivation via _compile_derivation_input + _compiled_derivation_plan_to_application; (5) [store.py:619-643] _run_rule produces RuleSpec, NOT CompiledDerivationPlan — Rule is wrong type for G1. §1/§2/§3/§4.4/§5.7/§6 text corrections applied as part of this lock and tabulated in §5.7 Decision block (Step 0 architectural refinement, NOT silent fix). §5.1 hypothetical `sdk.explain(rule=...)` preserved verbatim as faithful bundle citation; bundle's loose "rule" language clarified inline. §7 acceptance: ALL 7 §5 falsifier passes complete; blueprint ready to advance `draft → scoped`. |
| 2026-05-08 | scoped | Status transition + review cleanup + §8 fill | Full blueprint review pass identified 7 cleanup items + need to fill §8 Implementation Plan + need to add scoped per-phase acceptance to §7. Cleanups applied: (1) §3 line 28 "No scenario merge pre-lock... Falsifier required (§5.1)" → declarative post-lock language "explicitly rejected per §5.1 falsifier lock"; (2) §3 line 29 "No return-shape pre-lock" → "No B-typed-wrap return shape" with §5.2 lock reference; (3) §3 line 31 "without §5.4 Step 0 lock" → declarative "per §5.4 lock: G1 adds zero new entries"; (4) §5.7 falsifier outcomes table line 425 question column updated from "Rule only? Rule | CompiledDerivationPlan?" to "SDK `Derivation` only? `Derivation \| CompiledDerivationPlan`?" — matches corrected §5.7 sub-question framing; (5) §6 `#19` row line 457 fixture name `_g1_fixtures.py` → `_sdk_g1_fixtures.py` (per §5.6 lock refinement adding `sdk_` prefix); (6) §6 Forbidden line 467 "without §5.4 Step 0 lock" → declarative; (7) §7 line 476 status-progression intro updated to reflect post-scope state. §8 Implementation Plan filled with 4-phase plan (Phase 0 module skeleton + delegation hooks → Phase 1 sdk_check real impl → Phase 2 sdk_diagnose real impl → Phase 3 cross-cutting invariants + docs + close-out → Phase 4 archive + snapshot publish), each phase with explicit scope / acceptance / strict audit / audit-fix discipline per `feedback_audit_cadence_per_phase` and worktree pattern per `feedback_worktree_parallel_implementation`. §7 scoped per-phase acceptance bullets added (10 items, one per phase + audit). §7 scoped invariant tests added (7 items, one per §5.x lock). Status transitioned `draft → scoped` in blueprint header. Implementation kickoff explicitly NOT triggered: worktree NOT created, blueprint stays at `scoped` until user initiates. |
| 2026-05-08 | draft | §5.4 + §5.5 decisions locked | Paired read-only falsifier pass against SDK exposure and module placement. Outcome: G1 adds `SDKStore.check(...)` and `SDKStore.diagnose(...)` instance methods; no new free functions or application DTOs are added to `kernel.sdk.__all__`; implementation lives in flat helper modules `kernel/sdk/check.py` (`sdk_check`) and `kernel/sdk/diagnose.py` (`sdk_diagnose`) with thin `SDKStore` delegate methods in `store.py`. Five evidence threads cited across §5.4/§5.5: (1) [04_api_surface.md §2] SDK product API already includes `SDKStore` methods independently of top-level exports; (2) [sdk/__init__.py] `__all__` exports types/classes/constants, not store-bound free functions; (3) [store.py ingest/validate_provenance] existing SDKStore methods delegate to module-level helpers via local imports; (4) [01_alignment_matrix.md §3] `kernel.sdk.__all__` expresses SDK user-facing exports and must not export application internals; (5) [04_api_surface.md §1] future SDK ergonomic promotions must freeze outward request/result shape and cannot directly re-export application DTOs. Rejected top-level free functions because store-bound operations need `SDKStore` context and no such free-function precedent exists. Rejected `kernel/sdk/g1.py` because "G1" is roadmap taxonomy, not durable module semantics. Rejected direct implementation in `store.py` because `store.py` already delegates specialized logic to helper modules and is large. Flat `kernel/sdk/check.py` + `diagnose.py` chosen for G1; explicit future trigger recorded: G2 Step 0 must re-evaluate migration to a `kernel/sdk/shells/` subpackage before adding the third/fourth SDK shell file. §7 acceptance updated: §5.4 and §5.5 done, §5.6-§5.7 pending. |
| 2026-05-08 | implementing | Phase 0 implemented + audit clean | Commit `f58299c` added flat `kernel/sdk/check.py` and `kernel/sdk/diagnose.py` stubs, `SDKStore.check(...)` / `.diagnose(...)` delegation hooks, and two skeleton tests. Verification: stub tests pass, full kernel suite green, ruff clean, `git diff --check` clean. Strict audit covered module placement, SDKStore method names, no `kernel.sdk.__all__` expansion, no application protocol / walker imports in stubs, flat test names, and delegation pattern; verdict `0 blocker / 0 clarify / 0 minor`. Process note: implementation began from `scoped` before a separate `implementing` header transition; close-out records this as a process correction. |
| 2026-05-08 | implementing | Phase 1 implemented + audit clean | Commit `6852f2d` implemented `SDKStore.check(...)` end-to-end. Behavior: SDK `Derivation` only; `$`-prefixed mapping binding only; existing derivation lowering; single-plan enforcement; registry resolution; A `build_check_request(...)` call; application `check_derivation_binding(...)` dispatch; raw `CheckResult` return; `CapabilityHelperError` / `OriginPackageError` remapped to `SDKStoreError` with chaining. Verification: focused Phase 1 regression 123 tests pass, full kernel suite 1477 pass / 1 skipped, ruff clean, `git diff --check` clean. Strict audit covered all §5 locks relevant to Check; verdict `0 blocker / 0 clarify / 0 minor`. |
| 2026-05-08 | implementing | Phase 2 implemented + audit clean | Commit `73f5410` implemented `SDKStore.diagnose(...)` end-to-end, mirroring Phase 1 with Diagnose-specific runtime and result shape. Behavior: SDK `Derivation` only; `$`-prefixed mapping binding only; existing derivation lowering; single-plan enforcement; registry resolution; A `build_diagnose_request(...)` call; application `diagnose_derivation_binding(...)` dispatch; raw `DiagnoseResult` return; no call to the sibling Check SDK shell. Verification: 17 G1 diagnose tests pass, full kernel suite 1493 pass / 1 skipped, ruff clean. Strict audit covered §5.7 input shape, §5.2 return shape, §5.4 export discipline, §5.5 module placement, §5.3 error remap, A defense-in-depth, and Q1 Sibling; verdict `0 blocker / 0 clarify / 0 minor`. |
| 2026-05-08 | implemented | Phase 3 close-out + cumulative audit | Phase 3 added cross-cutting G1 invariant tests, expanded SDKStore/check/diagnose docstrings, updated `src/kernel/sdk/docs/04_api_surface.md` with `check(...)` / `diagnose(...)`, updated application overview docs to record the Tier 2 → Tier 1 strangler step, left README quickstart untouched, and filled blueprint §9 Outcome. Cumulative audit covered all §5 locks: per-method API, documented passthrough, SDKStoreError remap, zero `__all__` growth, flat modules, flat tests, SDK `Derivation` + mapping binding only, no B walker imports, no audit imports, no A private helper usage. Status moved from `scoped` directly to `implemented` at close-out due to late process correction; no API-shape deviation from the scoped design. |

## Phase 0–3 Final Strict Audit Report (2026-05-08)

**Verdict:** proceed to archive/publish. G1 is implemented and aligned with the scoped blueprint. No blockers, clarifies, or minor follow-ups remain before Phase 4 archive.

| Area | Result |
|---|---|
| §5.1 API shape | `SDKStore.check(...)` and `SDKStore.diagnose(...)` are separate methods; no `SDKStore.explain(...)` shipped. |
| §5.2 return shape | Raw `CheckResult` / `DiagnoseResult` documented passthrough; no SDK wrapper classes; result DTOs are not exported from `kernel.sdk.__all__`. |
| §5.3 error mapping | A helper errors remap to `SDKStoreError` with `__cause__` chaining; no new SDK error subclass. |
| §5.4 exposure | `kernel.sdk.__all__` remains unchanged at 34 entries; G1 ships as `SDKStore` instance methods only. |
| §5.5 module layout | Flat `kernel/sdk/check.py` and `kernel/sdk/diagnose.py`; `SDKStore` methods are thin delegates; no `kernel/sdk/shells/` package. |
| §5.6 tests | Flat `test_sdk_check.py`, `test_sdk_diagnose.py`, and `test_sdk_g1_invariants.py`; no nested `tests/sdk/`. |
| §5.7 input shape | SDK `Derivation` only, `$`-prefixed mapping binding only; `Rule`, `CompiledDerivationPlan`, and tuple-form `BindingItems` rejected at SDK boundary. |
| Layering | Production G1 modules import A public builders and application runtimes; no A private `_binding`, no B walker imports, no `kernel.audit` imports. |
| Docs | SDK API surface and application overview reflect G1; README quickstart intentionally untouched per `#6`. |

**Audit history reconciliation:** Phase 0, Phase 1, and Phase 2 strict audits all returned clean. Phase 3 introduced only cross-cutting tests/docs/close-out changes and did not change runtime behavior beyond docstrings.

**Residual work:** Phase 4 archive + snapshot publish remains pending by design.

---

## Phase 1-3 Reference / Quality Audit Report (2026-05-08)

Cross-cutting verification of Phase 1-3 deliverables (commits `6852f2d` Phase 1, `73f5410` Phase 2, `5922aa7` Phase 3) against (a) reference design bundle at `docs/references/working/post-routemap-direction-selection-input/`, (b) blueprint §5/§6/§7 locks, and (c) code-level hidden risks. Three-round audit per audit plan at `~/.claude/plans/phase-1-3-reference-warm-moth.md`. Auditor: `claude-opus-4-7[1m]` cross-session execution.

### Round 1 — Parallel Discovery (3 Explore agents)

#### Agent A — Design Alignment

**Verdict: 17/17 dimensions aligned. 0 Blocker / 0 Clarify / 1 Minor.**

| Lock / Principle | Status |
|---|---|
| §5.1 per-method API | Aligned — separate `SDKStore.check`/`SDKStore.diagnose`, no `sdk.explain` |
| §5.2 documented passthrough | Aligned — raw `CheckResult`/`DiagnoseResult`, not in `__all__`, no wrapper |
| §5.3 SDKStoreError remap | Aligned at design level (chaining + path) — see B.2 below for completeness gap |
| §5.4 `__all__` boundary | Aligned — length 34 unchanged from `dd8a40c` baseline |
| §5.5 flat module + delegate | Aligned — flat `kernel/sdk/check.py`+`diagnose.py`, mirrors `ingest()` precedent |
| §5.6 per-method tests | Aligned — flat `test_sdk_check.py`+`test_sdk_diagnose.py`+`test_sdk_g1_invariants.py` |
| §5.7 input shape | Aligned — SDK `Derivation` only, `$`-prefixed `Mapping` binding |
| Direction A bridging | Aligned — uses `compile_authoring_derivation_v1` + `_compiled_derivation_plan_to_application` |
| Strangler migration | Aligned — G1 calls A's `build_*_request` |
| `#1` Application-first | Aligned — no substrate in `kernel.sdk` |
| `#3` Heterogeneity | Aligned |
| `#5` Layer isolation | Aligned — no `_binding`/`walker.*`/`audit.*` imports |
| `#6` No outward compat | Aligned — README quickstart untouched, `__all__` unchanged |
| `#11` Inactive | Aligned — no walker import |
| `#12` Resolved | Aligned at design level |
| `#19` Test contract | Aligned — flat unittest, no Hypothesis |
| Docs strangler note | Aligned — `01_overview.md` Tier 2→Tier 1 strangler |

| ID | Severity | Finding |
|---|---|---|
| A.1 | Minor | `00_user_guide.md` lacks dedicated section explaining documented-passthrough semantics + opt-in B walker workflow. Docstring-only documentation. §5.2 lock says "may mention" — not hard requirement. |

#### Agent B — Code Quality + Hidden Risks

**Verdict (post Round 2 deep-dive): 1 Blocker / 0 Clarify / 8 Minor.**

| ID | Severity | Finding | File:line |
|---|---|---|---|
| **B.2** | **Blocker** | `_compiled_derivation_plan_to_application()` raises `ValueError` at `store.py:1617` (`_resolve_engine_ext_for_evaluate_plan`) when caller-supplied `derivation.engine_ext` conflicts with compiled-plan `engine_ext`. G1 call sites at `check.py:62-67` and `diagnose.py:67-72` are NOT wrapped → `ValueError` leaks uncaught, violating §5.3 `SDKStoreError` remap contract. Caller-controllable via `derivation.engine_ext`. | `check.py:62-67`, `diagnose.py:67-72`, `store.py:1617` |
| B.1 | Minor | (Initially candidate Blocker.) Docstrings claim `OriginPackageError` is caught and remapped, but G1 only wraps `build_*_request()`. Round 2 verified: `_reject_sdk_origin` fires ONLY at A's `build_check_request`/`build_diagnose_request` build-time (`capability_helpers/_binding.py:51-88`), NOT from `check_derivation_binding`/`diagnose_derivation_binding` runtime. G1's existing `except CapabilityHelperError` (catches subclass `OriginPackageError`) IS sufficient. **Theoretical — downgraded.** |
| B.3 | Minor (resolved) | Docstring claim verified accurate: `OriginPackageError(CapabilityHelperError)` per `capability_helpers/errors.py:10`; single `except CapabilityHelperError` catches both. |
| B.4 | Minor | `_validate_derivation`/`_validate_binding` byte-identical between `check.py:85-102` and `diagnose.py:90-107` except path strings. Intentional self-containment per §5.5; drift risk if shapes evolve. |
| B.5 | Minor | Multi-head error message `"check derivation must compile to exactly one plan"` lacks `derivation.id` context. Caller debug ergonomics. |
| B.6 | Minor | `sdk: Any` / `registry: Any` in `sdk_check`/`sdk_diagnose` intentionally loose; `store.py` tightens `registry: RuleRegistry \| None`. Asymmetry intentional. |
| B.7 | Minor | Tests do NOT mock runtime to inject `OriginPackageError`. Acceptable given B.1 resolution. |
| B.8 | Minor | `store.py:52` TYPE_CHECKING forward refs work via `from __future__ import annotations`. No explicit runtime-annotation validation test. |
| B.9 | Minor | Static Q1 Sibling check (`test_sdk_g1_invariants.py:275-282`) text-greps; evadable via aliasing or lazy import. AST-based stricter. v1-acceptable. |

**Layer-isolation imports**: ALL G1 imports compliant with §5/§6 locks. NO `_binding`, `walker.*`, `audit.*`, or direct `CheckRequest()` construction.

#### Agent C — Test Contract Completeness

**Verdict (post Round 2 deep-dive): 0 Blocker / 0 Clarify / 12 Minor.** 31 G1 tests + 9 invariant tests reviewed.

| ID | Severity | Finding | Test:line |
|---|---|---|---|
| C.1 | Minor | `LogicVar` binding key rejection not explicitly tested. Coverage by broader shape validation. | test_sdk_check.py:144-151, test_sdk_diagnose.py:173-180 |
| C.2 | Minor | Function-level walker imports (e.g., `from kernel.application.walker.views import parse_atom_key`) would pass current module-level grep. Low risk since walker inactive. | test_sdk_g1_invariants.py:82-88 |
| C.3 | Minor | `EXPECTED_SDK_ALL` hardcoded; manual baseline maintenance. | test_sdk_g1_invariants.py:14-49 |
| C.4 | Minor | `__all__` assertion uses both set equality AND length — redundant. | test_sdk_g1_invariants.py:64-65 |
| C.5 | Minor | Brittle exception-message string assertions. | test_sdk_check.py:119, 160; test_sdk_diagnose.py:148, 189 |
| C.6 | Resolved | Tests observable boundary not implementation detail. |
| C.7 | Minor | Fixture duplication (Person, `_build_sdk`, `_seed_person`, etc.) byte-identical between test files. Per §5.6 "extract on demand", intentional. |
| C.8 | Resolved | Docstring opt-in pointer tested at `test_sdk_g1_invariants.py:104-111`. |
| C.9 | Minor | `engine="pyreason"` not explicitly tested. Tests use `"native"`/`"souffle"`/`"problog"`. |
| C.10 | Minor | Empty binding `{}` not explicitly tested. |
| C.11 | Minor | `test_registry_is_resolved_and_passed_to_runtime` patches both `_resolve_runtime_registry` AND runtime; pure mock test. |
| C.12 | Resolved | `test_sdk_g1_invariants.py:74` covers §5.1 (`hasattr(SDKStore, "explain")` is False; `explain_fact` orthogonal). |

### Round 2 — Targeted Deep-Dive

Focused on candidate Blockers B.1, B.2 + Clarify items B.3, C.6, C.8, C.12.

**Q1 — Where does A's `_reject_sdk_origin` fire?** Investigated `capability_helpers/check.py` (3 calls in `build_check_request` lines 27-30), `capability_helpers/diagnose.py` (3 calls in `build_diagnose_request` lines 27-30), `capability_helpers/_binding.py` (recursive traversal lines 51-88), `derivation_check_runtime.py` (no calls), `diagnose_runtime.py` (no calls).

**B.1 verdict: Theoretical (downgrade Minor).** `OriginPackageError` raised ONLY at build-time. Runtime cannot trigger it. G1's `except CapabilityHelperError` wrap sufficient.

**Q2 — When does `_compiled_derivation_plan_to_application` raise ValueError?** Investigated `store.py:1480-1640`. Found 1 raise site at `store.py:1617` in `_resolve_engine_ext_for_evaluate_plan`: triggers when `explicit_engine_ext != compiled_engine_ext` and both non-None. Both caller-controllable via `derivation.engine_ext`.

**B.2 verdict: Real Blocker (confirmed).** ValueError reachable from caller input; G1 must wrap.

**Clarify resolutions:**
- B.3: docstring accurate (subclass relationship implicit but correct). Resolved.
- C.6: tests observable contract, not implementation detail. Resolved acceptable.
- C.8: docstring presence tested at invariants:104-111. Resolved.
- C.12: test correctly covers §5.1; `explain_fact` orthogonal pre-existing. Resolved.

### Round 3 — Synthesis

**Categorized totals:**

- **Blockers: 1** (B.2 — engine_ext conflict ValueError unhandled at SDK boundary)
- **Clarify: 0** (all resolved by Round 2)
- **Minor: 20** (1 design + 8 code-quality + 12 test-contract; all recorded for future follow-up)

**Net audit verdict: needs-fix (1 Blocker).**

**Recommended actions:**

- **B.2 audit-fix**: wrap `_compiled_derivation_plan_to_application()` calls at `check.py:62-67` and `diagnose.py:67-72` with `try/except ValueError → raise SDKStoreError(..., path="$.check.derivation"/"$.diagnose.derivation") from exc`. Add regression test scenario per Round 2 Q4 (mock `_compiled_derivation_plan_to_application` to raise `ValueError`, assert SDKStoreError remap).
- **Minor items**: defer to follow-up tasks. Several (B.4 fixture extraction, B.9 AST-based Q1 Sibling check, C.1/C.9/C.10 test coverage gaps) align naturally with G2's `kernel/sdk/shells/` migration trigger per §5.5; can be batched at that time.
- **Implementation status**: G1 retains `implemented` status. B.2 is a remap-completeness gap (small audit-fix), not a structural failure invalidating the implementation. Audit-fix lands as polish commit on G1 branch on top of Phase 4 archive.

### Audit-fix landed (2026-05-08)

**B.2 fix:** Wrapped `_compiled_derivation_plan_to_application()` calls at `kernel/sdk/check.py` and `kernel/sdk/diagnose.py` with `try/except ValueError` → `raise SDKStoreError(f"invalid {check|diagnose} input: {exc}", path="$.{check|diagnose}.derivation") from exc`. The `__cause__` chain preserves the original `ValueError` for caller debugging.

**Regression tests added:** `test_engine_ext_conflict_raises_sdk_store_error` in both `test_sdk_check.py` and `test_sdk_diagnose.py`. Each test patches `_compiled_derivation_plan_to_application` to raise a `ValueError` matching the actual `store.py:1617` `_resolve_engine_ext_for_evaluate_plan` error string ("Conflicting engine_ext between explicit derivation and compiled plan"), invokes `sdk.check` / `sdk.diagnose`, and asserts: (a) raised exception is `SDKStoreError`; (b) `path == "$.check.derivation"` / `"$.diagnose.derivation"`; (c) `__cause__` is the original `ValueError`; (d) message preserves "engine_ext" context.

**Verification (post-fix):**

- Focused G1 tests: **39 pass** (up from 37; +2 new B.2 regressions across check + diagnose).
- Full kernel suite: **1501 pass / 1 skipped** (up from 1499; zero regression).
- ruff: clean on all G1 files.
- `git diff --check`: clean.

**Net post-fix verdict: clean.** All §5 locks hold, B.2 remap completeness gap closed, 20 Minor items remain as deferred follow-up (none invalidating shipped behavior).

**Minor items deferred:** A.1 (user guide section), B.1 / B.3 (resolved as theoretical), B.4 (validation duplication — intentional per §5.5), B.5 (error message verbosity), B.6 (type annotation looseness — intentional), B.7 (runtime error mock not needed per B.1 resolution), B.8 (forward ref runtime check), B.9 (AST-based Q1 Sibling check — v1-acceptable text grep), C.1/C.9/C.10 (binding/engine coverage gaps — recommend G2 batch), C.2 (function-level walker import grep gap), C.3 (hardcoded baseline), C.4 (redundant assertion), C.5 (brittle exception messages), C.7 (fixture duplication — intentional per §5.6), C.11 (mock scope note), C.6/C.8/C.12 (resolved acceptable). Several Minor items align with `kernel/sdk/shells/` migration trigger per §5.5 G2 trigger; can be batched at that time.

### Round 4 cross-cutting audit follow-up (2026-05-08)

**New blocker B.1 confirmed:** `_resolve_runtime_registry(...)` can raise `RuleCompileError` through dependency registration (`_register_rule_dependencies(...)` → `RuleRegistry.register(...)`). The calls in `kernel/sdk/check.py` and `kernel/sdk/diagnose.py` ran before the A helper `CapabilityHelperError` wrapper and were not covered by the B.2 ValueError fix. This leaked a non-SDK exception across the G1 SDK boundary, violating §5.3 remap discipline.

**B.1 fix:** Wrapped `_resolve_runtime_registry(...)` in both G1 shells with `try/except RuleCompileError` and re-raised `SDKStoreError(..., path="$.check.dependencies" / "$.diagnose.dependencies") from exc`. This mirrors the B.2 fix shape while keeping dependency-registration failures distinct from derivation-lowering failures.

**Regression tests added:** `test_dependency_rule_compile_error_raises_sdk_store_error` in both `test_sdk_check.py` and `test_sdk_diagnose.py`. Each patches `_resolve_runtime_registry` to raise `RuleCompileError("duplicate rule registration")` and asserts `SDKStoreError`, precise dependency path, preserved `__cause__`, and message context.

**Post-fix note:** Q1 validation-helper extraction, AST-based Q1 Sibling static check, payload-extract wrapping, and brittle message assertions remain deferred design/polish items for G4/G2 follow-up. The B.1 fix is intentionally narrow and does not introduce shared validation refactors.
