# Task Blueprint Audit: Why-not Step 0 Spike

- Blueprint: [2026-05-05_why-not-step0.md](./2026-05-05_why-not-step0.md)

## Event Log

| Date | Stage | Event | Notes |
| --- | --- | --- | --- |
| 2026-05-05 | draft | Blueprint created | Opened as Why-not Step 0 spike only on `v0.1-why-not-step0-2026-05-05`, cut from Fact Overlay shipped HEAD `f484367`. |
| 2026-05-05 | draft | Step 0.A source pass drafted | Read shipped capability archives, L6 / lazy why-not reference material, current native evaluator surface, current adapter surfaces, and engine-extension §6.6. Preliminary finding: finite candidate-universe carrier board can be crisp, but true near-miss / exclusion-reason Why-not is not crisp without evaluator or adapter trace work. |
| 2026-05-05 | draft | Step 0.A Shape A-prime addendum recorded | Added Universe-carrier plus inline Diagnose as a third candidate shape. This preserves finite-universe boundedness while returning row-level diagnostics in one application call without a new evaluator hook. |

## Decision Notes

- 2026-05-05: This blueprint starts and remains in `draft`. No code implementation is authorized. The task is explicitly Step 0 only: determine whether Why-not has a crisp application DTO shape or should be abandoned / superseded.

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
