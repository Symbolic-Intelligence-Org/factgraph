# Task Blueprint: Diagnose Operation

- Status: scoped
- Created: 2026-05-04
- Last Updated: 2026-05-04
- Related Modules:
  - `src/kernel/application/protocol/`
  - `src/kernel/application/`
  - `src/kernel/core/rules/`
  - `src/kernel/core/store/`
  - `src/kernel/sdk/` (optional thin shell only; no substrate)
- Related Docs:
  - [docs/architecture_principles.md](../../architecture_principles.md)
  - [docs/references/working/rule-replay-line-redesign-input/README.md](../../references/working/rule-replay-line-redesign-input/README.md)
  - [docs/references/working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md](../../references/working/rule-replay-line-redesign-input/70_codebase-baseline-2026-05-03.md)
  - [docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md](../../references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/check-operation-conceptual-interaction.md)
  - [docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md](../../references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md)
  - [docs/blueprints/archive/2026-05-03_check-operation.md](../archive/2026-05-03_check-operation.md)
- Audit Log:
  - [2026-05-04_diagnose-operation.audit.md](./2026-05-04_diagnose-operation.audit.md)

## 1. Problem

Check operation answers whether a requested binding passes, fails, is unsupported, or is invalid. It intentionally does not explain why a failed / unsupported / evidence-unavailable outcome happened.

The redesign line now needs a second explanatory application capability to test whether the engine-extension decisions are usable outside Check. Diagnose is the candidate second consumer: it should inspect a Check-like question and return bounded diagnostic information without becoming full Explain, Why-not, UI projection, or fact-overlay replay.

This blueprint is opened in `draft` to run Step 0. No implementation may start until Step 0 freezes an application DTO shape and this blueprint moves to `scoped`.

## 2. Goals

- Run a source-backed Step 0 for an application-first Diagnose capability.
- Decide whether Diagnose is a sibling of Check, a wrapper around Check, or a narrower post-Check diagnostic operation.
- Freeze an application protocol shape before implementation:
  - request DTO fields;
  - result status vocabulary;
  - diagnostic evidence / payload shape;
  - error and warning policy;
  - engine representability boundaries.
- Use Diagnose as the second explanatory consumer that may pressure `engine-extension-surface-architecture.md` §3.6, without prematurely introducing an engine capability declaration system.
- Fill baseline P1/P2 anchors only where Diagnose actually needs them.

## 3. Non-goals

- No code implementation while status is `draft`.
- No fact overlay, fact replacement, or what-if mutation.
- No broad Explain surface, natural-language narrative, UI tree, or audit report renderer.
- No exhaustive Why-not / counterfactual search.
- No shared branch/atom projection contract unless Step 0 proves Diagnose cannot work without it.
- No request-level `engine_options` unless §6.4 promotion criteria are met.
- No new `EnginePayload`, payload registry, or JSON envelope unless §6.5 migration triggers are met.
- No engine capability declaration matrix unless Diagnose creates concrete second-consumer pressure and the topic doc is updated first.
- No SDK substrate. Any SDK shell, if ever added, must be a thin delegate after application runtime exists.
- No release-base, `v0.1-oss-prep`, `master`, publish, or projection action.

## 4. Current Context

### Application-first baseline

- New runtime capabilities must start in `kernel.application.protocol` and `kernel.application`.
- Check established the current template:
  - intent-only request DTO;
  - runtime side-channel `store` / `registry`;
  - status vocabulary owned by application;
  - engine-native evidence preserved as typed payload;
  - no SDK shell by default.

### Check anchors

- `CheckRequest(plan, binding, engine)` is the closest existing request shape.
- `CheckResult.status` distinguishes:
  - `passed`
  - `failed`
  - `unsupported`
  - `invalid_request`
- Check intentionally has no fail localization, first-failing atom, all matches list, or branch/atom projection.
- Check MVP currently skips lookup-to-`None` evidence misses; engine-extension §6.3 records that future changes touching that path must surface the miss observably.

### Engine-extension anchors

- §6.3 resolved the minimum engine adapter contract:
  - normalized `CandidateSet`;
  - truthful support/provenance references;
  - capability-specific binding extractability;
  - observable evidence miss policy.
- §6.4 resolved engine options placement lightly:
  - plan-level by default;
  - request-level options require the promotion criterion.
- §6.5 resolved payload typing as a working hypothesis:
  - typed Union remains default;
  - migration requires a concrete trigger.
- §3.6 engine capability declaration remains deferred. Diagnose may become the second consumer that grounds it, but that decision must be made explicitly in the topic doc before implementation depends on it.

## 5. Proposed Shape

This contract is **frozen by Step 0** (0.A pivotal decisions / 0.B DTO freeze / 0.C algorithm freeze; see audit Decision Notes for the full trace including Q1 supersede Hybrid → Sibling and §6.5 scope clarification).

### 5.1 Concept

Diagnose answers "why did this binding fail" — the explanatory dual to Check (which answers "did it pass / fail / unsupported / invalid"). Diagnose owns its own dispatch chain through engine-specific entry points; it does **NOT** call `check_derivation_binding(...)` internally (Q1 Sibling supersede; §6.3 evidence-miss observability would otherwise be laundered through Check's grandfathered silent-skip).

### 5.2 Request DTO (`DiagnoseRequest`)

- Single `CompiledDerivationPlan` (multi-plan rejected at DTO post_init); D1
- `binding: BindingItems` (sorted tuple, immutable; `$`-prefix variable name validator); D2
- `engine: Literal["native", "souffle", "problog", "pyreason"]` required, no default; D3
- **NO** `engine_options`, `diagnostic_mode`, `store`, `registry`, `query_id`, `run_id`, or precomputed resolutions; D4 + Sibling invariant. Runtime side-channel kwargs `store` and optional `registry` are passed to the runtime entry, not the DTO.

### 5.3 Result DTO (`DiagnoseResult`)

| Field | Type |
|---|---|
| `status` | `Literal["passed", "failed", "unsupported", "invalid_request"]` (Check's 4 values; D5) |
| `requested_binding` | `BindingItems` (echo) |
| `matched_binding` | `BindingItems \| None` (populated only on `passed`) |
| `matched_count` | `int \| None` |
| `failure_kind` | `Literal["no_candidate", "atom_localized"] \| None` (populated only on `failed`; D5) |
| `diagnostic_payload` | `DiagnoseAtomLocator \| None` (populated only on `failed` + `atom_localized`; D9) |
| `errors` | `tuple[ErrorDTO, ...]` (D7) |
| `warnings` | `tuple[WarningDTO, ...]` |

**Nullable matrix (D6):**

| status | failure_kind | matched_count | matched_binding | diagnostic_payload | errors |
|---|---|:-:|:-:|:-:|:-:|
| `passed` | `None` | ≥1 | populated | `None` | empty |
| `failed` | `no_candidate` | 0 | `None` | `None` | empty |
| `failed` | `atom_localized` | 0 | `None` | populated | empty |
| `unsupported` | `None` | `None` | `None` | `None` | required |
| `invalid_request` | `None` | `None` | `None` | `None` | required |

### 5.4 `DiagnoseAtomLocator` (typed payload class; D8)

Frozen dataclass:
- `branch_index: int` — which OR-branch was inspected
- `failed_atom_index: int` — source-order index of the failing atom in `branch[i]`
- `attempted_binding: BindingItems` — env state at the moment of failure (sorted, normalized)

Top-level atom only in MVP (nested-atom path tracking deferred to v1+). **Capability-output payload** (Diagnose-runtime-computed); **NOT** an engine-native payload — does **NOT** join the `EvidenceEnvelope.engine_payload` Union (D8.note §6.5 scope clarification; §6.5 governs engine-adapter-produced proof artifacts only).

### 5.5 Per-engine representability table (D10; locally hardcoded)

| Engine | passed | failed.no_candidate | failed.atom_localized | unsupported.representability | unsupported.evidence_unavailable | invalid_request |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| native | ✓ | ✓ | ✓ | n/a | rare | ✓ |
| souffle | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ |
| problog | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ |
| pyreason | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ |

Per-cell rationale: see audit Step 0.A "Cross-engine diagnostic asymmetry" bullet. §3.6 declarative capability matrix remains deferred (topic state); rules locally hardcoded in Diagnose runtime.

### 5.6 Algorithm overview (per engine)

**Native (C1 + C2 + C3):**
- **Phase 1 — pass / fail classification:** call `evaluate_native_where(...)`, subset-match each final binding against `request.binding`; on match → `passed` (primary sort `(branch_index, binding_items)` mirrors Check); on no match → Phase 2.
- **Phase 2 — atom localization (only on failed):** call `_localize_failed_atom(body, requested_binding, witness_facts, view_facts, rule_ref_resolutions)`. The walker uses Diagnose's own `_extend_env_with_atom` atom-extension primitive (explicit enumeration; **NOT** `_atom_satisfies` directly — `_ground_terms` would silent-false unbound vars and corrupt `failed_atom_index`). Walks atoms in body-source order. Primary failure selection sort key `(-atoms_satisfied, branch_index)`: most-progressed branch wins, lowest branch_index breaks ties. Returns `DiagnoseAtomLocator` or `None` (None → fallback `failure_kind="no_candidate"`).

**Non-native (souffle / problog / pyreason; C4):**
- Run `evaluate_derivation_plans(DerivationEvaluateRequest(plans=(plan,), engine=engine), store=store, registry=registry)`.
- For each candidate, look up evidence (souffle: `Store._lookup_support_artifact(...)`; problog/pyreason: `Store._lookup_provenance_envelope(...)`).
- Three-bucket classification per candidate: lookup-miss / match / no-match.
- **Result classification (precedence-ordered):**
  - Match bucket non-empty → `passed`, primary per Check 0.C C4 sort
  - Match empty AND lookup-miss bucket non-empty → `unsupported` with `EVIDENCE_LOOKUP_MISS` errors per missing candidate
  - All buckets accounted, no match, no lookup-miss → `failed` + `failure_kind="no_candidate"`
- **Lookup-miss outranks no_candidate:** evidence-miss is a contract problem per §6.3 Decision #5; never silent-skip.

### 5.7 Engine-extension conformance commitments

- **§6.3 (adapter contract):** Diagnose enforces evidence-miss observability without Check's grandfather clause. Lookup-miss surfaces as `status="unsupported"` with `EVIDENCE_LOOKUP_MISS` error, never silent-skipped (D12).
- **§6.4 (engine options):** No request-level `engine_options`. Any `diagnostic_mode` field would be capability-interaction, not engine-config; D4 omits it for MVP because no concrete consumer pressure.
- **§6.5 (engine-native payload typing):** Working hypothesis preserved. `DiagnoseAtomLocator` is capability-output, outside §6.5 scope (D8.note); `EvidenceEnvelope.engine_payload` Union unchanged.
- **§3.6 (engine capability declaration):** Topic state remains `deferred`. Diagnose confirms second-consumer pressure but Step 0 does not promote; MVP locally hardcoded per D10.

### 5.8 Q1 supersede record

Step 0.A audit recorded **Q1 = Hybrid** (Diagnose calls `check_derivation_binding(...)` for pass / fail + dispatches to lower-primitive walk on failed). Step 0.B superseded with **Q1 = Sibling** because Hybrid would launder Check's grandfathered silent-skip on lookup-miss, violating Diagnose's independent §6.3 binding. **Diagnose Sibling invariant** — runtime never imports `check_derivation_binding`, `derivation_check_runtime`, or any private helper from Check (`_binding_matches`, `_request_representability_precheck`, `_ruleref_preflight`); enforced by §7-Diagnose-3 banned-symbol test.

## 6. Boundaries And Invariants

- **Application-first:** no runtime substrate in `kernel.sdk`.
- **No implementation before Step 0:** this blueprint remains `draft` until request/result DTO shape is frozen.
- **No hidden engine abstraction:** do not introduce §3.6 capability declaration by accident.
- **No semantic flattening:** engine-native payloads remain inspectable and typed per §6.5.
- **No silent evidence miss:** if Diagnose touches evidence lookup, missing payload must be observable per §6.3.
- **No request-level engine options by symmetry:** §6.4 promotion criteria must be met first.
- **No Explain / Why-not scope creep:** Diagnose MVP must stay bounded to source-backed diagnostic classification.

## 7. Acceptance

### 7.1 Step 0 closure (paperwork)

- [x] Step 0.A source pass recorded in the audit log
- [x] Step 0.B freezes request / result DTO shape before implementation
- [x] Step 0.C freezes algorithm and engine representability boundaries
- [x] Step 0.D lifts Step 0 decisions into this blueprint and moves status to `scoped`

### 7.2 §7-Diagnose-N anti-regression gates (per audit C7)

Each gate maps to a concrete D-decision and gets a focused test class entry:

- [ ] **§7-Diagnose-1** (D5 evidence-unavailable as `unsupported`, NOT `failed`): test that engine-output with lookup-miss yields `status="unsupported"` with `EVIDENCE_LOOKUP_MISS` code; never `status="failed"` with a hypothetical `failure_kind="evidence_unavailable"`
- [ ] **§7-Diagnose-2** (D8 / D8.note `DiagnoseAtomLocator` NOT in `EvidenceEnvelope` Union): test that `EvidenceEnvelope.engine_payload` Union members are exactly `{SupportArtifact, ProvenanceEnvelope}`; `DiagnoseAtomLocator` lives only on `DiagnoseResult.diagnostic_payload`
- [ ] **§7-Diagnose-3** (Q1 Sibling no-Check-call invariant): static check that the Diagnose runtime module never imports `check_derivation_binding`, `derivation_check_runtime`, or any private helper from Check (`_binding_matches`, `_request_representability_precheck`, `_ruleref_preflight`); banned-symbol list maintained alongside the test
- [ ] **§7-Diagnose-4** (C2 native atom-localizer correctness): test cases verifying first-failed-atom is correctly identified for representative branches; explicitly tests that no successful atom is reported as failed; explicitly tests that `_atom_satisfies` is NOT called directly (silent-false trap avoidance per `_ground_terms` returning `None` on missing var)
- [ ] **§7-Diagnose-5** (D10 non-native `atom_localized` never fires): test that souffle / problog / pyreason responses never include `failure_kind="atom_localized"` regardless of input shape
- [ ] **§7-Diagnose-6** (D12 evidence-miss observable, never silent-skip): test that an adapter-advertised `support_kind` with `None` lookup surfaces `EVIDENCE_LOOKUP_MISS` error in `DiagnoseResult.errors`, never silent-discards the candidate
- [ ] **§7-Diagnose-7** (status enum invariance, D5): type-level invariant test that `DiagnoseResult.status` Literal contains exactly the 4 Check values (`passed`, `failed`, `unsupported`, `invalid_request`) and no 5th value

### 7.3 Layer placement (application-first)

- [ ] Protocol DTOs (`DiagnoseRequest`, `DiagnoseResult`, `DiagnoseAtomLocator`) live in `kernel.application.protocol/`
- [ ] Runtime function `diagnose_derivation_binding` and helpers live in `kernel.application/`
- [ ] No SDK substrate; SDK shell only added if explicitly scoped in a follow-up
- [ ] Diagnose runtime takes runtime dependencies (`store`, `registry`) through side-channel kwargs, not DTO fields

### 7.4 Code health

- [ ] Tests cover protocol shape, status semantics, nullable matrix per D6, evidence-miss observability, per-engine representability boundaries
- [ ] `python -m ruff check src/kernel` clean
- [ ] Full kernel test suite green (target: prior baseline + ~50 new Diagnose tests, mirroring Check's volume)

### 7.5 Cross-doc updates

- [ ] Engine-extension topic doc updated only if Diagnose promotes §3.6 from `deferred` (otherwise topic doc untouched per Step 0 commitment)
- [ ] Application module docs (`src/kernel/application/docs/01_overview.md` + `_en.md`) updated to list Diagnose runtime
- [ ] Conformance audit confirms implementation aligns with §5 frozen contract; documented in close-out

## 8. Implementation Plan

**Step 0 phases (complete; lifted into §5 / §7 above and audit Decision Notes):**

1. **Step 0.A — Source pass + structural decisions** (complete; audit dated `2026-05-04 (Step 0.A)`)
2. **Step 0.B — DTO contract freeze** (complete; audit dated `2026-05-04 (Step 0.B)`; Q1 supersede Hybrid → Sibling + §6.5 scope clarification landed here)
3. **Step 0.C — Algorithm + drift-prevention freeze** (complete; audit dated `2026-05-04 (Step 0.C)`; C2 atom-localizer primitive `_extend_env_with_atom` committed)
4. **Step 0.D — Lift to blueprint + scoped** (this lift; audit row added below)

**Implementation steps (ordered for incremental commits, mirroring Check archive's commit cadence):**

5. **Step 1 — Protocol DTOs.** Implement `DiagnoseRequest`, `DiagnoseResult`, `DiagnoseAtomLocator`, status / failure_kind Literal types, errors enum, nullable matrix validators per D6. Add focused protocol-shape tests covering D1–D9 invariants (target: ~20 protocol tests).

6. **Step 2 — Native runtime MVP.** Implement `diagnose_derivation_binding` public entry, `_request_diagnostic_representability_precheck` (D10 native cells), `_diagnose_ruleref_preflight` (C5), `_diagnose_native` (C1 Phase 1 + Phase 2), `_localize_failed_atom` (C2 walk), `_extend_env_with_atom` (C2 atom-extension primitive — explicit enumeration, NOT `_atom_satisfies` direct call). Cover native `atom_localized` + `no_candidate` + `invalid_request` paths.

7. **Step 3 — Native hardening.** RuleRef happy-path coverage, deterministic primary selection per C3 (`(-atoms_satisfied, branch_index)` sort); §7-Diagnose-4 anti-regression test class.

8. **Step 4 — Non-native representability gate.** Extend `_request_diagnostic_representability_precheck` for souffle / problog / pyreason per D10; cover `unsupported.representability` path; §7-Diagnose-5 anti-regression class.

9. **Step 5 — Souffle dispatch.** `_diagnose_souffle` (C4 + souffle binding extraction via `SupportArtifact.binding_items`), `_classify_non_native_buckets` three-bucket logic, lookup-miss precedence over `no_candidate`. §7-Diagnose-6 anti-regression for souffle path.

10. **Step 6 — ProbLog / PyReason dispatch.** `_diagnose_problog_pyreason` (C4 + payload-term head-var alignment), reuse three-bucket classifier. §7-Diagnose-6 anti-regression for problog / pyreason paths.

11. **Step 7 — Drift-prevention test pass.** Land remaining §7-Diagnose-1 / §7-Diagnose-2 / §7-Diagnose-3 / §7-Diagnose-7 tests; static check for §7-Diagnose-3 (banned-symbol list). Confirm all 7 anti-regression gates pass.

12. **Step 8 — Close-out.** Application docs sync (`src/kernel/application/docs/01_overview.md` + `_en.md`), conformance audit (compare implementation against §5 contract; record in audit), §10 Outcome filled. If audit identifies drift, fix before status `scoped → implemented`.

After Step 8 the blueprint moves `scoped → implemented` and is ready for archive (status → `archived` + move to `docs/blueprints/archive/`).

## 9. Docs To Update

Expected if implementation proceeds:

- `src/kernel/application/docs/README.md`
- `src/kernel/application/docs/01_overview.md`
- `src/kernel/application/docs/01_overview_en.md`
- `docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md` if §3.6 is promoted or revised
- SDK docs only if a future SDK shell is explicitly scoped

## 10. Outcome / Deviations

Task is in draft. Outcome is pending Step 0 and implementation.
