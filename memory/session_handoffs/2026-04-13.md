# Session Handoff — 2026-04-13 (Session 3)

Supersedes: `docs/session_handoff_2026-03-30.md` (Session 2 — PyReason/ProbLog explain + examples reorg)

---

## 1. Current Stage

This session delivered **three major capability lines** building on the Session 2 baseline (636 tests, 76 frozen contracts):

1. **Agent layer complete (L1→L4C)** — 39 source files + 39 test files. ReadReviewOrchestrator facade with 51 public methods covering session management, document staging, LLM extraction, batch processing, entity resolution, bundle review + commit, rule authoring, engine routing, and Langfuse observability.

2. **Extraction improvement line (P0→P2 + F1 + I1+I2)** — five incremental blueprints on the extraction layer:
   - P0: entity context header injection (cross-segment awareness)
   - P1: gleaning / second-pass extraction (low-yield segment re-examination)
   - F1: source_doc_name passthrough (human-readable name in LLM prompt)
   - I1+I2: Module identity grounding (Example 5 + entity type descriptions)
   - P2: cascaded ER fuzzy identity alias merge (token-subset matching)

3. **B3 load test harness** — full runner with --commit mode, 10-sample manifest, CommitStack, 4-call orchestrator sequence. Commit path blocked on canonical validator (documented, carry-forward points to `compile_schema_from_classes`).

4. **Notebook 08** — agent document workflow flagship demo with real OpenAI LLM extraction, adversarial identity fragmentation diagnostics.

5. **Research report** — `agentic-document-extraction-research.md`: comprehensive ADE survey covering cost/speed/reliability, technology selection (6 layers), CTO perspective.

**Current position:** Agent layer fully operational. Extraction line at P2 (alias merge). 1012 tests green. All blueprints archived. Working tree clean.

**Prior handoff:** `docs/session_handoff_2026-03-30.md` (Session 2) — HEAD `f987e3c`, 636 tests, 76 frozen contracts.

---

## 2. Capability Baseline

### Core Store & Ledger (carried from Session 2 + expanded)

Append-only assertion ledger with SQLite backing. Expanded write/query surface, concurrency guards. Candidate evaluation with deterministic `chosen` selection. Evidence tree with 4-layer explain pipeline (raw → summary → narrative → NL).

### Evidence Tree & Explain (carried from Session 2)

Node kinds: witness-bearing, proof-bearing (ProbLog), structural/constraint/terminal/degraded. `CandidateProvenanceTimeline` for PyReason. Three-layer explain architecture intact.

### Agent Layer (NEW this session)

Full agent stack in `src/factpy_kernel/agent/`:

| Sub-module | Role |
|---|---|
| `session.py` | AgentSession + bind_runtime_session + RuntimeBootstrapSpec |
| `orchestrator.py` | ReadReviewOrchestrator — 51 public methods, single facade |
| `tools/` | LocalRuntimeAPI, WriteTools, KGReadTools, ExplainTools, EvaluateTools, RuleTools, EngineRoutingAdvisor |
| `documents/` | DocumentStaging (pdf/docx/txt/md parsers), BundleManager, DraftManager, structural clarity |
| `extraction/` | ExtractionAgent (real LLM), BatchExtractor, EntityResolver |
| `observability/` | Langfuse tracer + NoOp tracer |
| `recovery.py` | AgentCheckpointStore, CandidatePayloadCache |
| `framework.py` | Layer1AgentSkeleton, tool registry, optional dependency probes |

### Extraction Improvements (NEW this session)

| Improvement | Status | Effect |
|---|---|---|
| P0 entity context | `implemented` | valid 7→9, rejections 1→0 |
| P1 gleaning | `implemented with deviations` | +1 gleaning spec |
| F1 doc name | `implemented` | Document entity coverage restored |
| I1+I2 module grounding | `implemented` | `data-infra team` misgrounding eliminated |
| P2 alias merge | `implemented with deviations` | resolver alias merge functional (LLM variance prevents stable notebook verification) |

Key design decisions:
- P0 entity context is opt-out (default on); P1 gleaning and P2 alias merge are opt-in (default off)
- Entity key for alias matching uses `(entity_type, tuple(sorted(identity.items())))` — same as resolver's `_compute_entity_key`
- Alias match: same entity_type + single string identity field + token-subset (conservative v1)
- Canonical key = first seen
- `segment_results` / `per_segment_metrics` reflect pass 1 only; gleaning additions appear in `aggregated_specs` + `gleaning_segments_reexamined`

### B3 Load Test Harness (NEW this session)

`docs/references/working/load-test-2026-04-11/`: full runner with `--commit` mode, CommitStack (13-component dependency tree), CP-14 filter, 10-sample manifest (smoke-4), canonical schema fixture. B3 `--commit` blocked at `open_runtime_session` on 3rd canonical validator rule (`group_key_indexes`). Carry-forward: use `compile_schema_from_classes` instead of hand-written JSON.

### Notebook 08 (NEW this session)

`examples/08_agent_document_workflow.ipynb`: 32-cell flagship demo. Real OpenAI LLM extraction, compile_schema_from_classes, adversarial identity fragmentation diagnostic (§10.5), P0-off control experiment. Requires `OPENAI_API_KEY` + `pip install -e '.[extraction]'`.

### SDK, Adapters, Annotation, Audit (carried from Session 2)

Unchanged. SDK DSL, Souffle/ProbLog/PyReason adapters, annotation system, audit package — all stable.

---

## 3. Git State

- **Branch:** `master`
- **HEAD:** `5d06663`
- **Working tree:** clean (0 uncommitted changes)

### This session's commits (chronological)

| Hash | Description |
|---|---|
| `3b2cecf` | feat: core/service infrastructure — ledger, runtime session, auth, evidence tree |
| `15f8c11` | feat: agent layer complete — L1 through L4C + extraction improvements P0–P2 |
| `74c0f85` | docs: agent layer + extraction improvement blueprints (all archived) |
| `6e1ea38` | feat: B3 load test harness + commit-path + schema-canonicalization blueprints |
| `fba82e0` | feat: notebook 08 — agent document workflow flagship (real LLM end-to-end) |
| `b8647e6` | docs: research report, remaining blueprints, project documentation |
| `5d06663` | chore: misc — launch config, scripts, ephemeral-rule-hardening blueprint |

---

## 4. Blueprint Status Summary

### Active Blueprints

| File | Status | Notes |
|---|---|---|
| `2026-03-22_architectural-decisions-v2.md` | landed | Design-phase decisions (reference) |
| `2026-03-28_evidence-graph-unified-explain.md` | landed | Parent blueprint for explain architecture |
| `2026-03-29_dialog-agent-blueprint-v1.md` | draft | Dialog agent — untouched this session |
| `2026-03-30_problog-candidate-evidence-tree.md` | implemented | ProbLog tree explain |
| `2026-03-30_pyreason-runtime-explain-timeline.md` | implemented | PyReason timeline explain |
| `2026-03-31_ontology-feasibility-analysis.md` | draft | Ontology feasibility |
| `2026-03-31_ontology-integration-concept.md` | draft | Ontology integration concept |
| `2026-04-03_market-alignment-guide.md` | scoped | Market alignment guide |
| `2026-04-09_dialog-agent-blueprint-v1.1-delta.md` | draft | Dialog agent v1.1 delta |

### Key Archived Blueprints (This Session)

Agent layer (16 blueprints):
- session-agent-inventory, layer1-control-plane-mvp, layer2-read-first-agent, layer3a-structured-write, w2a-exact-retract, layer4a-native-rule-authoring, layer4b-conservative-engine-routing, layer4c1-document-staging, layer4c2-draft-bundle-review, layer4c3a-single-segment-extraction, layer4c3b-batch-extraction, layer4c3c-entity-resolution, langfuse-minimal-observability, extraction-prompt-schema-alignment-fix, extraction-prompt-residual-patterns-fix, extraction-prompt-semantic-grounding

B3 load test (2 blueprints):
- load-test-runner-commit-path (`implemented with deviations`), b3-schema-canonicalization (`implemented with deviations`)

Extraction improvements (5 blueprints):
- P0 extraction-entity-context-injection (`implemented`), P1 extraction-gleaning-second-pass (`implemented with deviations`), F1 extraction-source-doc-name-passthrough (`implemented`), I1+I2 extraction-module-identity-grounding (`implemented`), P2 extraction-cascaded-er-fuzzy-identity (`implemented with deviations`)

Kernel/infrastructure (2 blueprints):
- kernel-extraction-response-model-openai-strict-fix, kernel-p0-production-readiness

### Full Archive Inventory

`docs/blueprints/archive/README.md` — 168 entries (includes all newly archived blueprints from this session).

---

## 5. Test Baseline

- **Total:** 1012 passed, 3 skipped, 1 warning, 4 subtests passed
- **Command:** `/Users/zhenzhili/miniforge3/envs/factpy/bin/python -m pytest src/factpy_kernel/tests/ -x -q`
- **Warning:** DeprecationWarning on `evaluate_dummy` (expected, non-blocking)
- **Skipped:** 3 (env-specific, not regressions)

Tests added this session: +376 (from 636 → 1012):
- 39 agent test files covering L1–L4C + extraction + observability
- P0: +10 tests (entity context header + build_messages injection)
- P1: +15 tests (gleaning loop + config + format)
- F1: +2 tests (source_doc_name passthrough)
- I1+I2: +3 tests (module grounding example + entity descriptions)
- P2: +5 tests (alias merge + config + MergeEvent flag)
- Core/service infrastructure: +10 tests (ledger concurrency, session schema, auth, etc.)

---

## 6. Key Implementation Files

### New/Changed Files This Session

| File | Role |
|---|---|
| `src/factpy_kernel/agent/` (39 files) | **NEW** — Full agent layer |
| `src/factpy_kernel/agent/extraction/prompts.py` | SYSTEM_PROMPT_TEMPLATE (10 rules + 5 examples) + schema summary + entity context + gleaning context |
| `src/factpy_kernel/agent/extraction/batch.py` | BatchExtractor with entity context injection + gleaning second-pass |
| `src/factpy_kernel/agent/extraction/resolution.py` | EntityResolver with exact dedupe + alias merge |
| `src/factpy_kernel/agent/extraction/extractor.py` | ExtractionAgent (real LLM via instructor/litellm) |
| `src/factpy_kernel/agent/orchestrator.py` | ReadReviewOrchestrator — 51 public methods |
| `src/factpy_kernel/core/store/ledger.py` | Expanded ledger write/query surface |
| `src/factpy_kernel/service/runtime_v1.py` | Expanded session management + schema readback |
| `src/factpy_kernel/service/auth.py` | **NEW** — Authentication module |
| `docs/references/working/load-test-2026-04-11/run_load_test.py` | B3 runner with --commit mode |
| `examples/08_agent_document_workflow.ipynb` | **NEW** — Agent flagship demo (32 cells) |
| `docs/references/agentic-document-extraction-research.md` | **NEW** — ADE research survey |

### Module Docs (Implementation Truth)

| File | Scope |
|---|---|
| `src/factpy_kernel/agent/docs/README.md` | Agent layer overview — all sub-modules |
| `src/factpy_kernel/agent/extraction/docs/README.md` | Extraction layer — ExtractionAgent, BatchExtractor, EntityResolver, P0–P2 |
| `src/factpy_kernel/agent/documents/docs/README.md` | Document staging — parsers, segmentation, clarity |
| `src/factpy_kernel/agent/observability/docs/README.md` | Observability — Langfuse tracer |
| `src/factpy_kernel/core/docs/01_architecture.md` | Core store, node_kind taxonomy, summary contract |
| `src/factpy_kernel/service/docs/03_runtime_queries_views.md` | Runtime queries including timeline + explain |

---

## 7. Frozen Contracts

Prior contracts 1–76 remain frozen (from Session 2). This session adds:

77. **Agent layer zero-diff principle** — during B3/extraction work, `src/factpy_kernel/agent/` code is NOT modified by runner-side changes; runner is the integration surface
78. **`ReadReviewOrchestrator` single facade** — all agent actions go through this class; no direct tool instantiation in user code
79. **`AgentSession.bind_runtime_session`** — the single state transition that makes a session commit-capable; requires runtime_session_id + bootstrap_spec + burr_db_path
80. **`CommitStack` 13-component dependency tree** — CP-13 from commit-path blueprint; `_build_commit_stack` constructs all components in correct order
81. **CP-14 filter retained** — strips `_`-prefixed top-level schema keys before `open_dto`; defensive, not to be removed
82. **`compile_schema_from_classes` is canonical-by-construction** — use this, not hand-written JSON, for canonical SchemaIR
83. **Per-segment extraction isolation** — each segment gets independent LLM call; cross-segment context comes from P0 entity accumulator, not shared LLM state
84. **P0 entity context is opt-out** (`enable_entity_context=True` default) — strictly additive; P1 gleaning and P2 alias merge are opt-in (`False` default) because they have cost/behavior trade-offs
85. **`segment_results` / `per_segment_metrics` = pass 1 only** — gleaning additions appear only in `aggregated_specs` + `gleaning_segments_reexamined`
86. **Entity key consistency** — `batch.py` accumulator and `resolution.py` dedupe use identical `(entity_type, sorted(identity.items()))` key computation
87. **P2 alias match: token-subset only** — conservative v1; same entity_type + single string identity field + shorter tokens ⊂ longer tokens; no edit distance, no embedding
88. **SYSTEM_PROMPT_TEMPLATE Example 3/4/5 grounding rules** — Document title = verbatim stable identifier; Module description = declarative only; Module name = software component only (not team/org/person)
89. **`source_doc_name` fallback** — `build_messages` uses `source_doc_name if source_doc_name else segment.doc_id`; callers that don't pass it get hash (backward compatible)
90. **B3 `test_schema_ir.json` immutable** — SC-03; provisional schema never modified
91. **Three empty B3 commit tempdirs** — left on disk per reviewer instruction; not to be deleted

**Total: 91 frozen contracts.** Do NOT reopen without explicit user approval.

---

## 8. Known Gaps / Risk Assessment

### B3 `--commit` mode blocked (P1, carry-forward)
- **Exists:** Runner wiring, CommitStack, 4-call orchestrator, CP-14, canonical fixture
- **Missing:** `test_schema_ir_canonical.json` doesn't satisfy all canonical validator rules (3 rules discovered, unknown count remaining)
- **Resolution:** Use `compile_schema_from_classes` (proven in Notebook 08) instead of hand-written JSON

### P2 alias merge LLM variance (P2, known limitation)
- **Exists:** Token-subset alias matching in EntityResolver, 5 deterministic tests green
- **Missing:** Notebook 08 real-LLM behavioral verification didn't stably reproduce alias split (OBS-01 variance)
- **Resolution:** Future verification should use deterministic resolver fixtures or frozen extraction checkpoints

### Pre-accept candidate payload not reconstructable (P2, structural — carried from Session 2)
- **Exists:** Live explain only works for accepted candidates
- **Missing:** Persistent payload index for pre-accept candidates

### SDK lacks runtime explain surface (P3, gap — carried from Session 2)
- **Exists:** `sdk.evaluate()/accept()/export_package()`
- **Missing:** `sdk.explain_tree()/explain_summary()/explain_nl()`

### Extraction coverage: Document entity (improved, not fully solved)
- **Exists:** F1 passes human-readable `source_doc_name`; I1+I2 adds Module identity grounding
- **Missing:** Document extraction still depends on text containing a "verbatim stable identifier" per Example 3; documents without filename-like strings produce no Document entities
- **Next:** Consider relaxing Example 3 to accept section headings, or adding document-level pre-extraction summary

### I3 validation-layer semantic guards (shelved)
- **Decision:** Not implemented. Prompt-side grounding (I1+I2) is the current strategy
- **Trigger to reopen:** If Module name misgrounding recurs stably after I1+I2, with clear pattern

---

## 9. Collaboration Protocol

1. **Blueprint-driven workflow** — one blueprint per task, draft → scoped → implementing → implemented → archived
2. **Hook restriction** — non-`.md` edits in `src/factpy_kernel/` blocked by pre-commit hook; provide code as text for user to apply
3. **Scope discipline** — each blueprint does ONE thing; no scope creep
4. **Contract-first** — freeze decisions before implementation
5. **Docs sync** — update module docs at implementation close
6. **Commit conventions** — `fix:` / `feat:` / `docs:` / `chore:` prefixes; `Co-Authored-By` trailer
7. **Decision-only blueprints** — design phase decisions stay in `active/` as reference
8. **Archive inventory** — maintain `docs/blueprints/archive/README.md`
9. **Evidence-driven P2** — don't open capability lines without concrete failure evidence (3-point standard: different identity keys + human-verifiable + resolver didn't merge)
10. **Three-layer explain architecture** — engine-native provenance → runtime contract → EvidenceGraph (carried from Session 2)
11. **Runtime explain is engine-appropriate** — do not force all engines into one contract shape (carried from Session 2)
12. **Extraction test strategy** — deterministic unit tests for code correctness; real-LLM notebook runs for behavioral signal (accept OBS-01 variance)

---

## 10. What the Next Agent Should Do

### First action

```bash
/Users/zhenzhili/miniforge3/envs/factpy/bin/python -m pytest src/factpy_kernel/tests/ -x -q
```
Expected: **1012 passed, 3 skipped**, 1 warning, 4 subtests passed. HEAD: `5d06663`.

### Recommended next direction

The extraction line is at a natural pause point (P0-P2 all closed). Natural next directions:

1. **B3 commit path unblock** — use `compile_schema_from_classes` (proven in Notebook 08) to generate canonical SchemaIR for B3 runner, bypassing the hand-written fixture that failed on 3 validator rules
2. **Dialog agent (v1 + v1.1-delta)** — two active blueprints in `docs/blueprints/active/` waiting for implementation; would use the ReadReviewOrchestrator facade
3. **Pre-accept candidate payload index** — enables live explain before accept; unblocks interactive decision workflows
4. **SDK explain surface** — expose explain through SDK, eliminating service-layer dependency

### What NOT to do

- Do not reopen any of 91 frozen contracts
- Do not open P2 without new identity fragmentation evidence (the shelved evidence standard applies)
- Do not add I3 (validation-layer keyword blocklist) without stable post-I1+I2 recurrence evidence
- Do not force PyReason into `CandidateEvidenceTree` — it uses `CandidateProvenanceTimeline`
- Do not hand-write canonical SchemaIR JSON — use `compile_schema_from_classes`
- Do not modify `test_schema_ir.json` (SC-03 immutable)
- Do not use `segment.doc_id` for LLM prompt `Document:` field — use `source_doc_name` parameter
- Do not run Notebook 08 without `OPENAI_API_KEY` + `pip install -e '.[extraction]'` in the factpy env
- Do not expect P2 alias merge to trigger on every real-LLM run — OBS-01 variance means the LLM may normalize aliases itself

---

## 11. Minimal Startup Reading List

1. **This handoff** (`docs/session_handoff_2026-04-13.md`)
2. `src/factpy_kernel/agent/docs/README.md` — agent layer overview
3. `src/factpy_kernel/agent/extraction/docs/README.md` — extraction layer (P0–P2 implementation truth)
4. `src/factpy_kernel/core/docs/01_architecture.md` — core store, node_kind taxonomy
5. `src/factpy_kernel/service/docs/03_runtime_queries_views.md` — runtime queries + explain
6. `docs/references/agentic-document-extraction-research.md` — ADE research survey (context for extraction decisions)
7. `docs/references/working/load-test-2026-04-11/commit_path_plan_2026-04-11.md` — B3 commit line status + carry-forward
8. `examples/08_agent_document_workflow.ipynb` — agent flagship demo (code reference for extraction pipeline)
9. `docs/blueprints/active/2026-03-29_dialog-agent-blueprint-v1.md` — dialog agent (next potential line)
10. `docs/blueprints/archive/README.md` — full archive inventory (168 entries)
11. `docs/session_handoff_2026-03-30.md` — prior handoff (Session 2 baseline, contracts 1–76)
