# Task Blueprint Audit: Why-not Universe Diagnose Capability

- Blueprint: [2026-05-05_why-not-universe-diagnose-capability.md](./2026-05-05_why-not-universe-diagnose-capability.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-05 | draft | Blueprint created | Opened as Why-not Step 0 spike only on `v0.1-why-not-step0-2026-05-05`, cut from Fact Overlay shipped HEAD `f484367`. |
| 2026-05-05 | draft | Step 0.A source pass drafted | Read shipped capability archives, L6 / lazy why-not reference material, current native evaluator surface, current adapter surfaces, and engine-extension §6.6. Preliminary finding: finite candidate-universe carrier board can be crisp, but true near-miss / exclusion-reason Why-not is not crisp without evaluator or adapter trace work. |
| 2026-05-05 | draft | Step 0.A Shape A-prime addendum recorded | Added Universe-carrier plus inline Diagnose as a third candidate shape. This preserves finite-universe boundedness while returning row-level diagnostics in one application call without a new evaluator hook. |
| 2026-05-05 | draft | Step 0.B DTO crispness decision recorded | Chose Shape A-prime as Why-not Universe Diagnose. Froze request/result/red-row DTO shape, selected Why-not-owned row diagnostics instead of nested `DiagnoseResult`, and left true near-miss Shape B outside capability scope. |
| 2026-05-05 | draft | Step 0.C algorithm and drift gates frozen | Froze dispatcher order, green/red partition algorithm, row Diagnose mapping, three-value top-level status, row diagnostic taxonomy, all-engine support gate, and fourteen §7-WhyNot drift gates. |
| 2026-05-05 | draft → scoped | Step 0.D lift complete | Renamed blueprint from Step 0 spike to Why-not Universe Diagnose capability, lifted Step 0 decisions into §5 / §7 / §8, and authorized implementation only through the scoped plan. |
| 2026-05-05 | scoped | Step 1 protocol DTOs complete | Added Why-not protocol DTOs and protocol-layer tests for request shape, finite universe validation, top-level result matrix, row diagnostics, protocol-owned DTO boundaries, and static literal invariants. |

## Decision Notes

- 2026-05-05: This blueprint started in `draft`. No code implementation was authorized until Step 0 answered whether Why-not had a crisp application DTO shape or should be abandoned / superseded.

- 2026-05-05: Branch context is `v0.1-why-not-step0-2026-05-05`, cut from `v0.1-fact-overlay-2026-05-04` at `f484367`. The existing working-tree-only `memory/current.md` modification is unrelated and intentionally not part of this blueprint.

- 2026-05-05 (Step 0.A) — **Source-pass file coverage.**
  - `docs/blueprints/archive/2026-05-03_check-operation.md` — first application-first DTO + runtime pattern; explicit binding Check; representability-gated multi-engine path.
  - `docs/blueprints/archive/2026-05-04_diagnose-operation.md` — Diagnose Sibling pattern, native atom-localization boundary, non-native coarse classification, and no exhaustive Why-not scope.
  - `docs/blueprints/archive/2026-05-04_fact-overlay-capability.md` — third capability, local gate discipline, native-only support accepted when the gate remains self-contained.
  - `docs/references/working/rule-replay-line-redesign-input/20_capability-layering-l0-l11.md` — L6 documented as lazy why-not / candidate-universe board, deferred, and requiring new evaluator hook to capture near-misses.
  - `docs/references/working/rule-replay-line-redesign-input/10_design-history-bprime-bdoubleprime/operational-evidence-tree-rule-replay-design-2026-05-01.md` — lazy why-not carrier pattern: explicit finite candidate universe, green = evaluate output, red carriers = universe minus green, red opened later through check/replay.
  - `docs/references/working/rule-replay-line-redesign-input/40_design-discussion-A-with-decision-1.md` — Why-not depends on candidate universe and Check; explicit open questions for universe source, status vocabulary, cost model, UI hook, and audit carrier persistence.
  - `docs/references/working/rule-replay-line-redesign-input/80_conceptual-interaction-design/engine-extension-surface-architecture.md` §6.6 — local capability gates remain working hypothesis until a concrete trigger shows the declarative shape is grounded.
  - `src/kernel/core/rules/where_eval.py` — native evaluator walks env sets and returns only successful final bindings; intermediate rejected envs are not captured.
  - `src/kernel/core/rules/ruleref_substrate.py` — `NativeWhereEvaluation` exposes only `bindings`, `rule_refs`, and `rule_ref_resolutions`; no failed-branch or near-miss payload.
  - `src/kernel/application/diagnose_runtime.py` — native atom localization is a capability-owned bounded walker for one requested binding, not a general candidate-universe trace source.
  - `src/kernel/core/store/_evaluate.py` — native store evaluation turns successful bindings into candidates/support; empty successful binding output returns no candidates.
  - `src/kernel/adapters/souffle/engine_eval.py` — adapter materializes successful query bindings / support rows into candidates; no failed candidate trace is returned through the engine evaluation contract.
  - `src/kernel/adapters/problog/engine_eval.py` — adapter parses successful ProbLog output into candidates and attaches success provenance; no failed universe carrier surface exists.
  - `src/kernel/adapters/pyreason/engine_eval.py` — adapter derives candidates from result session facts and attaches success provenance; event trace is candidate provenance, not a failed-candidate universe API.

- 2026-05-05 (Step 0.A) — **Shape split.** The source material uses "Why-not" for at least three related operations:
  1. **Lazy candidate-universe carrier board:** caller provides explicit finite candidate bindings; runtime computes green/red by set difference against evaluate output; red rows are minimal carriers for later per-binding Check/Diagnose.
  2. **Universe carrier plus inline Diagnose:** caller provides explicit finite candidate bindings; runtime computes green/red by set difference, then runs bounded Diagnose for each red binding and inlines row-level diagnostic payload.
  3. **True near-miss / exclusion-reason Why-not:** runtime reports almost-matches, rejected branches, failed atom reasons, attempted bindings, and ranked exclusion reasons.

  These are not the same DTO. The first can be made crisp if the universe is explicit. The second is also crisp if Step 0.B accepts Sibling-with-Diagnose composition or freezes a Why-not-owned diagnostic row DTO. The third is the high-signal L6 evaluator pressure point but is not supported by current evaluator/adapter outputs.

- 2026-05-05 (Step 0.A) — **Crispness criterion #1: request DTO field enumerability.** Shape A and Shape A-prime can plausibly enumerate fields as `plan`, `candidate_universe`, and `engine`, where `candidate_universe` is a tuple of normalized head bindings. Shape B cannot yet enumerate fields without a vague `mode`, `depth`, or `search_budget`. A `search_budget` field is treated as a warning light unless Step 0.B defines the bounded search space independently.

- 2026-05-05 (Step 0.A) — **Crispness criterion #2: result DTO status/payload.** Shape A can return green/red carrier summaries, but this is closer to candidate review than full Why-not. Shape A-prime can enumerate `WhyNotRedRow(binding, diagnose)` if nesting `DiagnoseResult` is accepted, or a copied Why-not-owned row diagnostic if Step 0.B rejects nested capability DTOs. Shape B lacks a grounded payload taxonomy: terms like `exclusion_reasons` or `near_misses` would be placeholders unless Step 0.B defines typed reason rows from current source behavior.

- 2026-05-05 (Step 0.A) — **Crispness criterion #3: runtime without new evaluator hook.** This is the likely blocker for Shape B, not Shape A-prime. `evaluate_native_where(...)` returns successful final bindings only. It does not retain failed env frontiers, rejected atom rows, or branch near-miss ranking. Diagnose's `_localize_failed_atom(...)` can explain one requested binding after failure. Shape A-prime can therefore run Diagnose over an explicit red set without a new hook, but it does not recover evaluator-global near-misses. True Shape B still appears to require evaluator-trace architecture before implementation.

- 2026-05-05 (Step 0.A) — **Crispness criterion #4: engine support gate readability.** Shape A can likely keep a local gate because every engine already produces success candidates and red is a set difference over an explicit universe. Shape A-prime can likely inherit Diagnose's gate per red row: native may atom-localize, while non-native remains coarse or unsupported according to Diagnose's existing representability and evidence-lookup semantics. Shape B does not keep the gate local-readable: native needs new failed-frontier capture; Souffle would need failed query / witness instrumentation; ProbLog and PyReason would need adapter-specific failed-proof or event interpretation beyond current success provenance. That is §6.7-level pressure, not another simple local gate.

- 2026-05-05 (Step 0.A) — **Shape A-prime composition caveat.** Step 0.B must decide whether `WhyNotRedRow` may directly nest `DiagnoseResult`, or whether Why-not must define its own row diagnostic DTO and copy only stable fields. Direct nesting is faster and preserves Diagnose semantics exactly, but it couples two application protocol DTOs. A copied row DTO is more work but keeps Why-not's result contract fully capability-owned.

- 2026-05-05 (Step 0.A) — **Preliminary recommendation.** Do not scope true near-miss Why-not implementation from this blueprint unless Step 0.B can identify a bounded no-new-hook algorithm. Treat Shape A-prime as the leading application-capability candidate because it keeps finite-universe boundedness, avoids `search_budget`, and returns useful row-level diagnostics in one call. If the desired product is only pure Shape A, supersede or rename this blueprint so it does not overclaim L6 near-miss Why-not. If the desired capability is true near-miss / exclusion reasons, abandon this blueprint as a capability and open an evaluator architecture blueprint first.

- 2026-05-05 (Step 0.B) — **D1 Shape selection.** Choose **Shape A-prime: Universe carrier plus inline Diagnose**. Pure Shape A is crisp but too low-signal because the "why" is deferred to caller-side per-row calls. Shape B is high-signal but not crisp against current evaluator/adapter outputs because it requires failed-frontier / near-miss trace data that current surfaces do not expose.

- 2026-05-05 (Step 0.B) — **D2 Request DTO freeze.** The request DTO is `WhyNotUniverseRequest(plan, candidate_universe, engine)`. `plan` is a single `CompiledDerivationPlan` with exactly one head. `candidate_universe` is a tuple of normalized `BindingItems` representing complete head bindings; each binding must use exactly the head variable names. `engine` is required and has no default. The DTO has no `store`, `registry`, `search_budget`, `limit`, `mode`, `diagnostic_mode`, `engine_options`, `run_id`, query handle, precomputed candidates, or precomputed green set.

- 2026-05-05 (Step 0.B) — **D3 Candidate universe semantics.** The universe is explicit, finite, and set-like. Duplicate universe bindings are invalid. Empty universe is allowed and produces a completed empty board. Body-only variables are invalid in the universe because the board claims completeness only over head/select identity.

- 2026-05-05 (Step 0.B) — **D4 Result DTO freeze.** The result DTO is `WhyNotUniverseResult(status, requested_universe, green, red, errors, warnings)`. Top-level `status` is `completed`, `unsupported`, or `invalid_request`. `green` is a tuple of derived universe bindings. `red` is a tuple of `WhyNotRedRow`. Top-level non-completed statuses are reserved for request-wide failures before board assembly; Step 0.C later refined row-level invalid diagnostics into runtime invariant errors.

- 2026-05-05 (Step 0.B) — **D5 Row DTO freeze.** `WhyNotRedRow(binding, diagnostic)` carries the red binding and a `WhyNotRowDiagnostic`. Initial Step 0.B framing said the row would copy Diagnose's stable status payload. Step 0.C later narrowed this to red-row-only fields: `status`, `failure_kind`, `diagnostic_granularity`, `atom_locator`, `errors`, and `warnings`.

- 2026-05-05 (Step 0.B) — **D6 Nested DiagnoseResult rejected.** The runtime may call `diagnose_derivation_binding(...)`, but the result protocol does not nest `DiagnoseResult`. It maps Diagnose's fields into Why-not-owned DTOs and maps `DiagnoseAtomLocator` to `WhyNotAtomLocator(branch_index, failed_atom_index, attempted_binding)`. Rationale: keep Why-not's protocol capability-owned while preserving Diagnose semantics exactly enough for row diagnostics.

- 2026-05-05 (Step 0.B) — **D7 Runtime composition.** Choose **Sibling-with-Diagnose mapping**. Why-not may call Diagnose for each red binding because the finite universe bounds the outer loop and Diagnose bounds each row. Why-not does not call Check, does not import Check runtime/protocol DTOs, and does not add evaluator hooks.

- 2026-05-05 (Step 0.B) — **D8 Engine support gate.** The board can be computed when the selected engine can evaluate the plan and expose candidate bindings comparable with the explicit universe. Red-row diagnostics inherit Diagnose semantics through mapping: native can atom-localize; souffle/problog/pyreason can return coarse failed or unsupported classifications according to Diagnose's current representability and evidence lookup rules. Row-level unsupported does not make the top-level result unsupported. §6.6 local-gate working hypothesis still stands; §6.7 is not opened by Step 0.B.

- 2026-05-05 (Step 0.B) — **D9 Shape B disposition.** True near-miss / exclusion-reason Why-not remains outside this application-capability scope. If the product requirement is evaluator-global "almost matched" ranking or exclusion reasons independent of a supplied universe, open an evaluator architecture blueprint first.

- 2026-05-05 (Step 0.C) — **C1 Top-level status set.** Use a Why-not-specific three-value top-level status: `completed`, `unsupported`, and `invalid_request`. Do not reuse Check / Diagnose `passed` / `failed` vocabulary at the board level. Why-not answers whether the universe board was assembled, not whether one binding passed.

- 2026-05-05 (Step 0.C) — **C2 Empty universe policy.** Empty universe is valid and returns `completed` with empty `green` and `red`. This differs from Fact Overlay's empty overlay rejection because an empty universe is data, not a missing action.

- 2026-05-05 (Step 0.C) — **C3 Engine support matrix.** Choose all-engine support with diagnostic richness tiers, not native-only. Native can produce atom-localized red rows through Diagnose. Souffle / ProbLog / PyReason can still return useful boards and coarse / unavailable row diagnostics when candidate binding extraction is representable. Top-level `unsupported` is reserved for engine / plan shapes where the board cannot be assembled at all.

- 2026-05-05 (Step 0.C) — **C4 Green/red algorithm.** Evaluate the plan once through the selected engine, extract comparable head bindings from derived candidates, then compute `green` and `red` by set intersection / difference against the explicit universe. Output order follows the requested universe order. The partition invariant is: `green ∩ red = ∅` and `green ∪ red = requested_universe`.

- 2026-05-05 (Step 0.C) — **C5 Candidate binding extraction.** Green extraction must use head-binding semantics compatible with Check / Diagnose. Fact targets align plan head variables to candidate payload terms. Entity targets are supported only when the engine candidate payload can expose the requested head binding. Candidate payloads that cannot represent complete head bindings make the board top-level `unsupported`.

- 2026-05-05 (Step 0.C) — **C6 Row diagnostic taxonomy refinement.** Refine Step 0.B's row diagnostic shape to red-row-only fields. `WhyNotRowDiagnostic` has `status`, `failure_kind`, `diagnostic_granularity`, `atom_locator`, `errors`, and `warnings`. It does not expose `matched_binding` because red rows cannot have matched bindings. `diagnostic_granularity` is `atom_localized`, `coarse`, or `unavailable`.

- 2026-05-05 (Step 0.C) — **C7 Diagnose mapping.** `failed.no_candidate` maps to `failed` / `no_candidate` / `coarse`; `failed.atom_localized` maps to `failed` / `atom_localized` / `atom_localized` with `WhyNotAtomLocator`; `unsupported` maps to row-level `unsupported` / `unavailable`. Diagnose `passed` and `invalid_request` are runtime invariant errors because Why-not has already classified the binding as red and validated the request shape.

- 2026-05-05 (Step 0.C) — **C8 Runtime composition and protocol boundary.** Runtime may import and call Diagnose to construct row diagnostics, but the protocol must not import or expose Diagnose DTOs. Runtime must not call Check. This is the Why-not variant of Sibling discipline: runtime composition is allowed only behind a capability-owned output contract.

- 2026-05-05 (Step 0.C) — **C9 No evaluator hook.** Implementation must not modify or depend on new `evaluate_native_where(...)` trace or callback output. True near-miss / exclusion-reason work remains evaluator architecture scope.

- 2026-05-05 (Step 0.C) — **C10 Drift gates.** Step 0.C lifts fourteen §7-WhyNot gates into blueprint acceptance, covering intent-only DTO shape, no budget escape fields, universe validity, duplicate guard, empty universe behavior, status matrix, partition invariant, protocol ownership, runtime composition boundary, row status constraints, diagnostic richness, engine support, no evaluator hook, and no ledger write.

- 2026-05-05 (Step 0.D) — **Lift complete; status `draft -> scoped`.** Step 0 decisions now live in the canonical blueprint sections:
  - **§5 Proposed Shape** contains the authoritative Why-not Universe Diagnose contract: capability shape, request/result/row DTOs, runtime composition, engine support gate, algorithm, and status/mapping freeze.
  - **§7 Acceptance** contains Step 0 closure, §7-WhyNot-1 through §7-WhyNot-14 anti-regression gates, layer placement, code health, and cross-doc acceptance.
  - **§8 Implementation Plan** contains complete Step 0 history plus five ordered implementation steps: protocol DTOs, runtime MVP board assembly, Sibling-with-Diagnose row diagnostics, drift-prevention named gates, and close-out.

  The active files were renamed from `2026-05-05_why-not-step0.*` to `2026-05-05_why-not-universe-diagnose-capability.*` because the spike has selected a scoped capability. Implementation may begin, but any future change to §5 contract, §7 gates, or §8 plan requires a new audit entry before code changes.

- 2026-05-05 (Step 1) — **Protocol DTO implementation.** Added `src/kernel/application/protocol/derivation_why_not.py` with the frozen Step 0 DTO set:
  - `WhyNotUniverseRequest(plan, candidate_universe, engine)`
  - `WhyNotUniverseResult(status, requested_universe, green, red, errors, warnings)`
  - `WhyNotRedRow(binding, diagnostic)`
  - `WhyNotRowDiagnostic(status, failure_kind, diagnostic_granularity, atom_locator, errors, warnings)`
  - `WhyNotAtomLocator(branch_index, failed_atom_index, attempted_binding)`

  The protocol layer enforces the Step 0 shape decisions where possible: request fields are intent-only; candidate universes are explicit finite complete-head bindings; duplicate universe entries are rejected; empty universe is accepted; top-level status is the Why-not-specific three-value set; completed results enforce ordered green/red partition coverage; non-completed results require empty boards and batch errors; row diagnostics allow only failed/coarse, failed/atom-localized, or unsupported/unavailable shapes.

- 2026-05-05 (Step 1) — **Protocol ownership boundary.** The Why-not protocol exports only Why-not-owned row and locator DTOs. It does not import or expose `DiagnoseResult`, `DiagnoseAtomLocator`, Check DTOs, `EvidenceEnvelope`, `SupportArtifact`, or `ProvenanceEnvelope`. Tests also keep `WhyNotAtomLocator` out of `EvidenceEnvelope.engine_payload`, preserving the §6.5 capability-output boundary.

- 2026-05-05 (Step 1) — **Verification.**
  - `python -m unittest src.kernel.tests.test_application_why_not_protocol` — 59 tests OK.
  - `python -m unittest src.kernel.tests.test_application_check_protocol src.kernel.tests.test_application_diagnose_protocol src.kernel.tests.test_application_fact_overlay_protocol src.kernel.tests.test_application_why_not_protocol` — 165 tests OK.
  - `python -m unittest src.kernel.tests.test_application_diagnose_protocol src.kernel.tests.test_application_fact_overlay_protocol src.kernel.tests.test_application_why_not_protocol` — 143 tests OK.
  - `python -m ruff check src/kernel/application/protocol/derivation_why_not.py src/kernel/application/protocol/__init__.py src/kernel/tests/test_application_why_not_protocol.py` — clean.
  - `python -m pytest ...` currently exits with code `-1` and no output even for pre-existing Diagnose protocol tests; use the repository's documented `unittest` path for this step.
