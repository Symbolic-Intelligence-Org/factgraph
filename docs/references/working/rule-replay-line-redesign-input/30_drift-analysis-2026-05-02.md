# Design Landscape Synthesis (2026-05-02)

- Status: working / one-shot analytical review
- Authority: non-authoritative per `docs/references/README.md` §3.5; this document is analytical reference material only and not implementation truth nor API contract.
- Companion: [README.md](./README.md)
- Source-checked against: kernel @ `575b84e` (v0.1.x rollup including v0.1.1 + v0.1.2 + v0.1.3, plus 8 archives + evidence-vision bundle + design-landscape bundle)
- Methodology: Three parallel sub-agent extractions (v0.1.x design line / pre-OSS original vision / architecture & governance) + direct cross-reference against shipped `src/kernel/` and `src/agent/` code.

## 0. Executive summary

The project's declared design is **bigger and older** than what shipped. The v0.1.x line we just spent 6 weeks on is a coherent slice of the original vision — but it's a *narrow* slice. The original 2026-03-22 ADR positions factpy as **"auditable reasoning framework, not reasoning engine"**; the actual feature work since OSS prep has shifted center of gravity toward **"rule operability product on a kernel-only OSS surface"**. Two of the three pre-OSS product strands (dialog agent, ontology integration) sit at zero or partial implementation; the third (rule-side reasoning over operable bodies) drove all v0.1.x work.

There is no architectural rot. The four-layer data architecture (Claim/Annotation/Provenance/View) is intact; layer split between `core` / `application` / `sdk` / `audit` / `authoring` / `adapters` / `service` is enforced; release-surface governance (projection allowlist, denylist, default-deny) is mature. What's missing is **product-shape validation**: the L0-L11 evidence layering exists only in this session's design exploration document; cross-engine evidence translation has been technically withdrawn once already and remains aspirational; the conversational interface that the original design centered on has 2390 LOC of monorepo-private control plane but no visible LLM-backed user surface; the compliance market gaps that the 2026-04-03 alignment guide flagged (rule lifecycle metadata, closure reason library, alert state machine) are still all gaps.

The honest summary: **architecture is sound and disciplined; foundation is intact; recent product work is real but narrow; the original product vision is approximately 25-35% implemented; "Decision Assurance" market positioning is unvalidated**. The strategic question is no longer "what's the next feature" — it's "is the current narrow slice the right slice, and what would force-validate that?"

## 1. Methodology and scope

This document was produced by three parallel sub-agent extractions and one cross-reference pass against shipped code. Specifically:

- **Sub-agent A** read the v0.1.x design line: 4 archived blueprints (rule-replay, module-ir, disable-condition, param-override) + 5 OSS-prep family blueprints + 2 reference bundles (rule-replay, evidence-vision). Output: structured extraction of stated problem / goals / non-goals / invariants / outcome / deviations / architecture decisions per blueprint.
- **Sub-agent B** read pre-OSS active drafts: 2 landed pre-OSS architecture decisions (architectural-decisions-v2, evidence-graph-unified-explain) + 5 product/concept drafts (dialog-agent v1, ontology-feasibility, ontology-integration, market-alignment, dialog-agent v1.1-delta) + 3 reference docs (cross-domain-compliance, esa-positioning, product-readiness-audit). Output: original vision per document + cross-cutting observations on what survived / was abandoned / has stalled.
- **Sub-agent C** read architecture and governance docs: `architecture_principles.md`, `AGENTS.md`, `docs/blueprints/AGENTS.md`, plus per-module docs in `src/kernel/{core,application,sdk,audit,authoring,adapters}/docs/`. Output: layer responsibilities, governance rules, release surface governance, blueprint workflow rules, per-engine adapter boundaries, audit package contract.
- **Cross-reference**: I directly checked `src/agent/`, `src/service/`, `src/domains/`, `src/kernel/adapters/` for actual implementation depth, and grepped for evidence of pre-OSS vision items (ontology, closure_reason, dialog state machine, etc.).

The document is structured as: declared landscape → shipped reality → drift analysis → unproven assumptions → structural concerns → realistic evaluation → implications. Each section produces specific claims, not summaries.

## 2. The complete declared design landscape

### 2.1 The framework thesis (architecturedecisions-v2 ADR)

**Source**: `docs/blueprints/active/2026-03-22_architectural-decisions-v2.md` (status `landed`, supersedes 3 earlier 2026-03-15 blueprints)

**Statement**: "factpy is **auditable reasoning framework**, not reasoning engine." Code structure expresses this: schema, metadata, audit, render are the body; reasoning engines (Souffle / ProbLog / PyReason) are plugins. Framework value statement: "regardless of which reasoning engine you use, we make the reasoning process auditable."

**Implication for product shape**: The product's center of gravity should be **audit + provenance + cross-engine consistency**, not engine capability per se. Customers buy because their AI/ML/rules system needs auditable provenance trails, not because they need yet another rule engine.

### 2.2 The four-layer data architecture

**Source**: ADR §3 + core docs `01_architecture.md` lines 89-106 (updated 2026-03-26)

| Layer | Backing | Responsibility |
|---|---|---|
| **Claim Store** | SQLite `claims` + `claim_args` | Facts (pred_id + args). Append-only, identity-stable. |
| **Annotation Store** | SQLite `annotation_rows` (canonical) + `meta_rows` (legacy compat dual-write) | Fact-level metadata: source, engine truth, derived summary, operational state. Organized by `namespace` × `category`. |
| **Provenance Store** | Audit package JSONL | Inference process: proof tree (Souffle) / event log (PyReason) / probability trace (ProbLog). |
| **Evidence/Audit View** | Read-only synthesis | Merges Claim + Annotation + Provenance into navigable views. **Never persistent entity.** |

**Invariants**:
- Fact metadata does not know about evidence tree
- Provenance does not know about evidence tree
- No reverse references → no cycles
- Evidence is always a derived view, never independently mutable
- Provenance comes from engines, not reconstructed outside

**Implication**: This is the deepest architectural claim. Almost everything else (B'' pivot, layer split, audit package contract) follows from it. Any future capability that wants to write to "evidence" actually needs to write to one of the three real layers and have evidence re-derive from it.

### 2.3 The seven-layer code split

**Source**: `architecture_principles.md` lines 24-37 + per-module docs

| Layer | Owns | Forbidden |
|---|---|---|
| `kernel.core` | Ledger, store, rules, derivation, evidence, policy, mapping, annotation. Low-level semantic kernel. | SDK / authoring / adapter / service knowledge. |
| `kernel.application` | Canonical Python runtime authority: protocol DTO, schema runtime, entity hydration/write, query/ingest/derivation execution. | Importing SDK; HTTP delivery; package export. |
| `kernel.sdk` | Python product surface: schema/DSL authoring (`Entity` / `Field` / `Rule` / `Derivation`), `SDKStore` facade, snapshot/editor/batch outward objects, compatibility errors. | Re-exporting `application` internals; new runtime-authoritative logic. |
| `kernel.authoring` | Schema/rule/derivation preflight + compile, registry workflow, internal module IR substrate (v0.1.2). | Runtime fact persistence; HTTP routing. |
| `kernel.audit` | Consume exported audit packages; query DTO; evidence graph DTO + JSON renderer. | Live runtime fact query; package export; static site rendering (delegated to `service.static_ui`); ECSS row assembly (delegated to `domains.ecss.compliance`). |
| `kernel.adapters` | Per-engine evaluation registration: Souffle / ProbLog / PyReason. Where IR compilation, provenance trace parsing. | Cross-engine semantic unification beyond evidence graph DTO. |
| `service` / `agent` | HTTP/BFF delivery; conversational orchestration. | New SDK runtime imports in production code. |

**Enforcement**: Strict. SDK calls application but application does NOT import SDK (architecture_principles.md line 35). `test_sdk_consumer_boundary.py` actively prevents new production SDK runtime imports. Allowlist of one exception: `agent.extraction.api.compile_schema_from_classes` for schema authoring helper.

**Implication**: This split is the real structural work. It survives v0.1.x without modification. New runtime work goes to `core` or `application`; new ergonomics goes to `sdk`; new authoring goes to `authoring`. The split prevents the kind of "everything is in `sdk/store.py`" rot that god files would cause.

### 2.4 The B'' pivot

**Source**: `docs/references/working/rule-replay/rule-replay-design-synthesis-2026-05-01.md` + evidence-vision synthesis §0

**Pivot statement**:
- **Rule / derivation is operable.** Users patch atoms, disable conditions, build variants.
- **Evidence is read-only and run-derived.** No write surface, no in-place mutation.

**Why pivot was needed**: Earlier drafts (B / B') considered making the evidence tree itself the operable surface — users would edit evidence, partial proof would re-evaluate. The branch name `evidence-tree-operational-overlay` is the historical fossil of that idea. B'' inverted it: keep evidence read-only and immutable; push all "what if" operations to the rule side instead.

**v0.1.x enforcement**: All three implemented patches (rule-replay / module-IR / disable-condition) reaffirm the invariant in their non-goals. v0.1.4 abandoned because forcing distinct semantic families (atom replace vs condition_weights vs adapter thresholds) into one "param_override" name would have crossed the same kind of boundary at a different layer.

**Implication**: The pivot is a *load-bearing constraint*, not a stylistic preference. Reversing it (L11 in the evidence layering) would invalidate every v0.1.x and v0.2 minor invariant. It's correctly marked design-reserved for v2.0 at earliest.

### 2.5 Multi-engine adapter strategy

**Source**: ADR §5 + adapter docs `01_souffle_adapter.md`, `02_problog_adapter.md`, `03_pyreason_adapter.md`

**Position**: Schema unified + audit unified + rules NOT unified. Each engine is plug-in via registration, evaluated through the shared `Store.evaluate(mode="...")` dispatch (except PyReason which has adapter-local session for write).

| Engine | Status | Provenance form | Witness |
|---|---|---|---|
| Native (in core) | Production | `native_binding_v1` | Always available |
| Souffle | Production | `souffle_witness_v1` | Partial via Datalog `_w` rewriting (adapter-level, not official Soufflé proof tree); degraded path: `engine_no_witness_v1` + zero digest |
| ProbLog | Production | `problog_provenance_v1` | ProvenanceEnvelope + projectable `candidate_evidence_tree` |
| PyReason | **"spike, execution-surface V1"** (adapter docs line 5) | `pyreason_provenance_v1` | Event log via `get_rule_trace`; not proof tree |

**Critical constraint surfaced earlier**: 2026-03-28 evidence-graph-unified-explain *explicitly withdrew* the originally-planned unified ProofNode tree because real engine samples showed Souffle (proof tree) and PyReason (event log) are fundamentally different semantic shapes. The replacement is per-engine envelope + `EvidenceGraph` DTO that can render as tree or timeline depending on `layout_hint`, but the adapter doesn't claim to translate semantics across engines.

**Implication**: The "multi-engine" claim is *operational* (you can dispatch to any of them) but *not semantic* (their evidences don't unify). The "cross-engine evidence translation" deferred item in the v0.2 list inherits this difficulty — it's not a "we just haven't built it yet" item, it's a "we previously tried and consciously stepped back" item.

### 2.6 Three-product surface

The project actually has three different product surfaces:

| Surface | What | Where | Status |
|---|---|---|---|
| **`factpy-kernel` OSS** | Kernel-only Python package, 261 files projected via `scripts/project_release_surface.sh` | Future public `Symbolic-Intelligence-Org/factpy-kernel` repo | RC verdict `conditional pass` (`bf652a1`); no PyPI upload yet; no public push yet |
| **Monorepo full** | Kernel + agent + service + domains + tools | Private `Symbolic-Intelligence-Org/hnsm-backend` | Current development source of truth |
| **Agent + extraction + ECSS demo** | Conversational interface + document extraction + ECSS compliance demo | `src/agent/` + `src/agent/extraction/` + `src/domains/ecss/` (monorepo-private) | Partial implementation — see §3 |

**Implication**: When discussing "the product," the speaker means one of three things. The OSS surface is what the world sees; the monorepo is what the team works in; the agent surface is what original product vision called for. Drift analysis below requires distinguishing them.

### 2.7 The original product vision (pre-OSS)

**Source**: dialog-agent v1 / v1.1-delta + ontology integration concept + market-alignment guide

The pre-OSS vision had **three product strands**:

1. **Conversational knowledge entry agent** (dialog-agent-blueprint-v1, v1.1-delta):
   - Three modes: conversational fact/rule entry, document extraction (PDF/DOCX → rules), intelligent engine routing
   - Tech stack: PydanticAI (provider routing), Burr (state machine + SQLite persistence), Instructor (structured output), Langfuse (LLM audit trace), PyMuPDF + Docling (PDF → MD with offset tracking)
   - Layered execution: control plane → read-first → minimal write → rules + docs + routing → advanced
   - Target user: **non-technical domain experts** (not Python rule authors)
   - Status: v1 → v1.1 delta both `draft`, never scoped

2. **Ontology-flavored knowledge modeling** (ontology-feasibility + ontology-integration-concept):
   - Class hierarchies, property characteristics, instance classification, property chains
   - Implemented as auto-generated Souffle/Datalog rules (Route A — sugar on existing engines)
   - Explicitly NOT a separate OWL reasoner (Route B deferred)
   - Status: both `draft`, no implementation

3. **Compliance market alignment** (market-alignment-guide + cross-domain-compliance-framing + esa-positioning):
   - Target markets: AML/KYC, ECSS aerospace, financial crime
   - Differentiator: formal provenance trees that no competitor offers (vs IBM ODM / FICO Blaze / Pega / Fiddler / Arize / Rainbird / Credo AI)
   - Honest gaps identified: rule lifecycle metadata (timestamps), decision replay/what-if, closure reason library, alert/case lifecycle state machine
   - Status: `draft`, used as orienting guidance, not implementation trigger

**Implication**: The original vision is a complete product (knowledge engineering + reasoning + audit). v0.1.x has implemented one slice (rule replay = decision replay/what-if from market alignment), partially started another (agent control plane in monorepo), and not touched the rest.

### 2.8 v0.1.x feature line (rule-replay + module-IR + disable-condition)

**Source**: 4 archived blueprints (rule-replay, module-ir, disable-condition, param-override) + rule-replay reference bundle

Three implemented patches form a coherent layer of "rule body operability":

| Patch | Substrate | Public surface | Test gain |
|---|---|---|---|
| v0.1.1 rule-replay | `kernel.sdk.replay`, `kernel.sdk.replay_runtime` | `SDKStore.replay_with_patch(derivation, *, locator, new_atom)` + `ReplayResult` / `CandidateDiff` / `EvidenceComparison` | 709 → 777 (+68) |
| v0.1.2 module-IR | `kernel.authoring.module_ir` | `ConditionModule` / `ModuleBodyIR` / `ModuleLoweringMap` / `support_key_to_module_id` + `ReplayResult.{original,variant}_module_map` | 776 → 806 (+30) |
| v0.1.3 disable-condition | `kernel.core.rules.where_eval` + `_support_capture` overlay | `replay_with_patch(..., action="disable")` + `ReplayResult.disabled_locators` | 806 → 818 (+12) |
| v0.1.4 param-override | (none, Step 0 negative result) | (none) | (no change) |

**Net new product capability over 6 weeks**: three operations on one rule's body atoms (replace / disable / inspect-module-mapping), plus a structured way to compare results.

### 2.9 v0.2 evidence-vision roadmap (L0-L11)

**Source**: `docs/references/working/evidence-vision/evidence-vision-synthesis-2026-05-02.md` (created earlier this session)

| Layer | Status |
|---|---|
| L0 structured evidence data | ✅ pre-v0.1 |
| L1 shallow metadata diff | ✅ v0.1.1 |
| L2 reverse-mapping evidence → rule module | ✅ v0.1.2 |
| L3 locator stability under disable | ✅ v0.1.3 |
| L4 per-frame proof tree diff | ❌ deferred |
| L5 cross-run module aggregation | ❌ deferred |
| L6 lazy why-not / candidate-universe board | ❌ deferred |
| L7 cross-engine evidence translation | ❌ deferred |
| L8 audit JSONL replay persistence | ❌ deferred |
| L9 interactive UI | ⚠️ data present, frontend empty |
| L10 sidecar annotation | ❌ not designed |
| L11 mutable evidence | ❌ design-reserved by B'' |

**Recommended phasing in that doc**: L8 first (highest leverage, unblocks L4/L5/L9), then L4 + L5 in parallel, then L9. L6/L7 are large v0.2-minor candidates. L10 is independent and B''-compatible. L11 is off-limits.

**Caveat**: The L0-L11 layering was constructed in one sitting during this session (after the user noted that "evidence completion" was a multi-part topic). It has NOT been validated by implementation contact. L4 / L5 might collapse together once attempted. L8 might split. The taxonomy is a tool for avoiding v0.1.4-style "this is one thing" failures, not a proven decomposition.

## 3. The shipped reality

This section catalogs what code actually exists, separated by surface.

### 3.1 What's in `factpy-kernel` OSS projection (kernel only)

Per `scripts/project_release_surface.sh` + allowlist:

- 261 files projected from `src/kernel/` (excluding `kernel.tests`, generated caches, bytecode, internal `AGENTS.md`)
- Public top-level imports: `kernel`, `kernel.sdk`, `kernel.application`, `kernel.audit`, `kernel.authoring`
- `kernel.adapters` available but adapter usage requires explicit `import kernel.adapters.{souffle,problog,pyreason}` to register evaluator
- Wheel entries: 156 kernel non-test
- Smoke verified: install → import → README quickstart prints `Alice` → audit optional-domain raises correctly
- License: Apache-2.0; deps don't carry AGPL surface (PyMuPDF AGPL is private agent concern, not in kernel)

This is the world-visible product. The strategic question for OSS adopters reading this projection is: "what can I do with kernel-only?" Answer: write entities, declare rules/derivations, evaluate via `Store.evaluate(mode=...)`, accept candidates, export audit package, replay rules with patches, disable conditions, inspect evidence reverse-mapped to rule modules. Substantial. But notably missing: any conversational interface, any LLM-assisted entry, any persistent rule lifecycle, any case management.

### 3.2 What's in monorepo private (agent / service / domains / tools)

Per direct ls + grep against `src/`:

- **`src/agent/`** — 2390 LOC across 8 files (`__init__.py`, `framework.py`, `session.py`, `orchestrator.py`, `draft.py`, `candidate_cache.py`, `recovery.py`, `errors.py`) + `extraction/` + `documents/` + `observability/` + 41 test files
  - Imports check: agent production code does NOT import `kernel.application` (zero matches); imports `kernel.sdk` only via tests + the registered `agent.extraction.api.compile_schema_from_classes` exception
  - Has dependency-status detection for PydanticAI + Langfuse (`framework.py:25,27`) — implies optional integration, not core dependency
  - Has `candidate_cache.py` (148 LOC) — matches v1.1-delta design's `CandidatePayloadCache` requirement
  - Has `orchestrator.py` (951 LOC) — substantial
  - Has `recovery.py`, `session.py`, `framework.py` — control plane + lifecycle as v1.1 layered execution model called for
  - **Status**: Layer 1 control plane (per v1.1-delta phasing) appears largely landed, Layer 2-5 (read tools / write / rules / advanced) probably not. No conversational LLM logic visible from file names alone.

- **`src/service/`** — `app_v1.py`, `runtime_v1.py`, `rules_v1.py`, `registry_v1.py`, `auth.py`, `static_ui.py`, `_certainty_service.py`, `_common.py`, `_registry_io.py`
  - Imports check: production service code does NOT import `kernel.sdk` (boundary guard works)
  - HTTP routing for runtime / rules / registry / auth; static site rendering; certainty service
  - Mature; existed before v0.1.x line

- **`src/domains/ecss/`** — ECSS aerospace compliance domain bundle
  - `vcd.py`, `temporal.py`, `uncertainty.py`, `sdk_helpers.py`, `compliance.py`
  - Imports `kernel.sdk` (allowed as domain facade) + `kernel.audit.assertions`
  - Mature; ECSS validation PoC was 2026-03-22

- **`tools/benchmarks/`** — benchmarks for adapter performance + tests

- **`src/kernel/adapters/{souffle,problog,pyreason}/`** — all four adapters present and registered
  - Souffle is most mature
  - ProbLog has provenance + projectable evidence tree
  - PyReason marked "spike" / execution-surface V1; no candidate evidence tree projection yet

### 3.3 What exists but isn't connected

- Agent layer has substantial control plane (2390 LOC) but appears **not connected to any conversational LLM frontend** — no chat UI, no slash command interface, no session-resume web view. PydanticAI / Langfuse availability detection is there but actual usage from agent code into those libraries is not visible from grep alone.
- Service layer has HTTP routes but no client-side application using them visible in the repo.
- ECSS domain has compliance row assembly but the full compliance demo workflow is referenced in `factpy_esa_demo.pptx` (a PowerPoint deck, not running code).
- Cross-engine evidence translation (v0.1.2 deferred → v0.2 candidate) — `EvidenceGraph` DTO exists; converters per engine exist; but actual "compare PyReason evidence to Souffle evidence for same query" is not exercised anywhere.

### 3.4 What's documented but not implemented

- **Ontology integration** (Phase 1 schema layer): zero implementation. Grep for `ontology:`, `parent_entity_type`, `ontology_rule` returns nothing. Two drafts in active/ since 2026-03-31, never moved past `draft`.
- **Rule lifecycle metadata** (`registered_at`, `last_modified`, `last_executed`): zero implementation. Market-alignment-guide flagged this as compliance market gap on 2026-04-03; no work done since.
- **Closure reason library + reason code matching + feedback loop**: zero implementation. Same source, same gap status.
- **Alert/case lifecycle state machine** (`pending → investigating → escalated → closed`): zero implementation. Same.
- **Decision replay/what-if** as customer-facing feature: v0.1.x rule-replay implements the *mechanism*; the *workflow* (CandidateReview vocabulary, review session, decision state, notes per binding) does not exist.
- **Most of evidence layering L4-L11**: by definition, deferred.

### 3.5 Test surface and baselines

- Kernel test baseline: 818 / 1 skip (current rollup, post-v0.1.3)
- Pre-v0.1.x baseline: 776 / 1 skip
- Test growth in v0.1.x: +42 tests (rule-replay + module-IR + disable-condition + replay journey)
- Agent test files: 41 (separate test suite)
- Across all 5 segments (kernel + agent + service + domains + tools): historical 1097 tests / 3 skips at v0.1 RC (`bf652a1`); not repeatedly verified post-rule-replay across all 5 segments

## 4. Drift analysis

Each entry below states the original intent, the current reality, and whether the gap is principled drift or accidental drift.

### 4.1 Framework-vs-product framing

**Original intent (2026-03-22 ADR)**: "factpy is auditable reasoning framework, not reasoning engine." Code structure is "schema, metadata, audit, render are the body; reasoning engines are plugins." Customer value = audit infrastructure, not feature parity with rules engines.

**Current reality**: 6 weeks of v0.1.x work were entirely about rule operability — replay / module IR / disable-condition. This is *product* work on the rule side (a specific engine surface), not *framework* work on cross-engine audit. The OSS projection is a Python library; its public surface is rule authoring + evaluation + replay; "auditable reasoning framework" is in the docs but the visible value proposition is "rules engine with replay."

**Verdict — drift, partly principled**: The B'' pivot is a principled choice (push operability to rule side). But the ADR's *framework* framing implied that audit + cross-engine + provenance trail were the customer value. v0.1.x has not advanced cross-engine, has not advanced audit (no L8 persistence), has not added new provenance carriers. The pivot delivered rule-side product features at the cost of advancing the framework framing. The drift is not failure — it's a strategic narrowing — but it has gone unnamed.

### 4.2 Multi-engine claim vs native-only execution

**Original intent (ADR §5)**: Multi-engine architecture: Souffle (deterministic Datalog), ProbLog (probabilistic), PyReason (graph + temporal). Schema unified, audit unified, rules NOT unified. Per-candidate engine-specific provenance envelope.

**Current reality**: All four adapters exist and register. But:
- v0.1.x rule-replay is **explicitly native-only** (`replay_runtime.py` rejects engine_ext + non-native mode)
- v0.1.x module-IR substrate doesn't even attempt to be cross-engine
- v0.1.x disable-condition is "native-only by Step 0 design"
- PyReason adapter is marked "spike" + "execution-surface V1" in adapter docs
- "Cross-engine evidence translation" was already withdrawn once (2026-03-28 evidence-graph blueprint stepped back from unified ProofNode tree)
- The same item is now in v0.2 deferred list as if it's a "we'll do it later" thing, when historically it's a "we tried and stepped back" thing

**Verdict — drift, accidentally**: The multi-engine claim survives in adapter docs and ADR but has degraded in actual feature surface. The recently-shipped capabilities are native-only by design. Customers reading "factpy supports Souffle, ProbLog, PyReason" will believe they get parity; in practice they get Souffle for explicit Datalog work, ProbLog for probability, PyReason for time-windowed reasoning, and rule-replay only for native. This is fine for engineering; it's a real claim/reality gap for marketing.

### 4.3 Dialog agent vision vs control-plane reality

**Original intent (2026-03-29 dialog-agent-blueprint-v1 + 2026-04-09 v1.1-delta)**: Three-mode conversational agent (chat fact entry / document extraction / engine routing) targeting non-technical domain experts. Tech stack: PydanticAI + Burr + Instructor + Langfuse. Layered execution: control → read → write → generate.

**Current reality (`src/agent/`, monorepo-private)**: 2390 LOC across orchestrator (951), framework (378), session (254), draft (252), candidate_cache (148), recovery (184), errors (41). Has dependency-status detection for PydanticAI + Langfuse. Does NOT import them in production code paths visible from grep. Looks like Layer 1 (control plane) is mostly there; Layers 2-5 are not — no LLM-driven slot filling, no document extraction with offset tracking, no schema discovery dialog state machine.

**Verdict — drift, principled but underdeclared**: It's reasonable that during OSS prep work the conversational layer was deprioritized — OSS surface is kernel-only, agent is monorepo-private. But the dialog-agent drafts have been in `draft` status for 4-5 months without movement, and the original vision had the agent as the *primary* user surface for non-technical experts. Without it, the kernel-only surface only serves Python-fluent rule authors. The drift is principled (focus before scaling) but the implication — "we serve developers, not domain experts, until further notice" — has not been declared anywhere.

### 4.4 Ontology integration vs zero implementation

**Original intent (2026-03-31)**: Add ontology-flavored features (class inheritance, property characteristics, instance classification) as Route A — Datalog sugar on existing Souffle engine. Phase 1 schema layer first.

**Current reality**: Both ontology drafts (`feasibility-analysis`, `integration-concept`) sit at `draft` in active/. Zero ontology imports in `src/`. No `parent_entity_type` field on Entity. No auto-generated subclass_of rules.

**Verdict — drift, accidental**: 4+ months of zero progress on a `draft` blueprint is functionally an undeclared abandonment. Either it should be moved to scoped+implementing on a real branch, or it should be moved to abandoned/superseded with explicit reason. Sitting in `draft` indefinitely is a tombstone.

### 4.5 Compliance market gaps unaddressed

**Original intent (2026-04-03 market-alignment-guide)**: Honest assessment identified four absent abilities critical to compliance market: rule lifecycle metadata, decision replay/what-if, closure reason library, alert/case lifecycle.

**Current reality**:
- Decision replay/what-if: **partially addressed** by v0.1.1 rule-replay (the mechanism is there; the workflow vocabulary like CandidateReview is not)
- Rule lifecycle metadata: **zero progress**
- Closure reason library: **zero progress**
- Alert/case lifecycle: **zero progress**

**Verdict — drift, accidentally**: One of four was addressed (and only partially). The market-alignment-guide explicitly said this should drive prioritization; v0.1.x prioritization went elsewhere (rule operability mechanism, not workflow). The compliance market story remains under-built.

### 4.6 Evidence layering (L0-L11) maturity gap

**Original intent (`evidence-vision-synthesis-2026-05-02.md`)**: Layered v0.2 roadmap with L4-L10 as deferred candidate scope; L11 design-reserved.

**Current reality**: Only L0-L3 implemented. L4-L10 are the entire forward roadmap and have been promised in this session's design exploration but not started.

**Verdict — drift not yet committed**: The layering was created two days ago. It's premature to call this drift, but the document's recommended phasing (L8 → L4/L5 → L9) is on no roadmap and committed to no branch. The synthesis itself acknowledges that "the layering was constructed in one sitting" — it is design speculation, not an implementation backlog.

### 4.7 Drift summary table

| Dimension | Original framing | Current state | Drift type |
|---|---|---|---|
| Framework vs product | "Auditable reasoning framework" | Rule operability product | Principled but undeclared |
| Multi-engine | 4 engines as plugins, parity | Native-only for v0.1.x; cross-engine stepped back | Accidentally undeclared |
| Dialog agent | Primary UX for non-technical users | Control plane partially built, no LLM connection | Principled but undeclared |
| Ontology | Phase 1 schema layer first | Zero implementation in 4+ months | Accidentally undeclared |
| Compliance market gaps | 4 named gaps to drive priority | 1 partially addressed, 3 untouched | Accidentally drifted |
| Evidence layering | L0-L11 in v0.2 roadmap | Only L0-L3 done, rest is paper | Not yet committed |

The pattern: drift is real, mostly *accidental* (not deliberate strategic redirection), and *undeclared* in current memory or docs. The recently-saved release-branch invariant memory is good at preventing future accidents on release; nothing equivalent prevents accidental scope drift.

## 5. Unproven assumptions

These are claims the design rests on but has not validated.

### 5.1 The B'' pivot delivers usable UX

**Claim**: Pushing all "what if" operations to rule side (and keeping evidence read-only) gives users a complete enough interaction model.

**Why unproven**: No real user has used v0.1.x. The interactive UI scenario the user described earlier in this session ("see evidence tree → click condition → see proof state → export → annotate") explicitly maps to L4 / L5 / L8 / L9 / L10 — five capabilities all in deferred state. Until any of those exist, the B'' claim is paper-only. The user might still want to mutate evidence directly even after they've tried the rule-side path; we don't know.

**Validation cost**: 1 real user × 1 real workflow × 2 weeks. Not prohibitive, but requires either letting the OSS preview ship or running a friendly user through a private deployment.

### 5.2 Module identity (`mod_v1:<sha>`) survives scaling

**Claim**: Owner/path-scoped module ids are stable across runs and avoid accidental cross-rule sharing.

**Why partially proven**: Implementation locks the invariant (immutable ConditionModule.atom + immutable ModuleLoweringMap) and tests cover the single-rule case. But cross-rule sharing via `shared_id` is a designed-but-unused field on `ConditionModule`. Library identity (multiple rules referencing one shared condition) is documented as design-reserved. Once L3 is actually exercised (sometime in v0.2), assumptions about owner/path scoping might break — e.g., if same rule is loaded under two different owners (versioning, cloning, snapshotting), what happens to shared_id?

**Validation cost**: Real cross-rule sharing scenario or a substantial blueprint that exercises shared_id in practice.

### 5.3 "Decision Assurance" market positioning

**Claim**: Formal provenance trees are a real differentiator vs IBM ODM / FICO Blaze / Pega / Fiddler / Arize / Rainbird / Credo AI. No competitor offers this. Market wants it.

**Why partially proven**: The competitive landscape claim (no formal provenance in competitors) is from the 2026-04-03 market-alignment-guide based on competitor research. The "market wants it" claim relies on FCA enforcement signals and Reddit AML community discussion — real market signals, but not validated by any actual customer commitment. ECSS / ESA validation is in progress (Christophe Honvault feedback was positive on explainability) but ECSS is a *validation vector*, not a paying market.

**Validation cost**: One real customer interview (compliance officer, internal auditor, AI governance role) demonstrating they would buy provenance trail capability if it were ready. Or one paid pilot.

### 5.4 Cross-engine evidence translation feasibility

**Claim**: Eventually, PyReason / Souffle / ProbLog evidence will be translatable to a unified comparison surface (L7 in evidence layering).

**Why almost certainly false in current form**: The 2026-03-28 evidence-graph blueprint *already withdrew* the unified ProofNode tree based on "two real engine samples" showing fundamental shape differences (proof tree vs event log vs probability trace). The same difficulty hasn't gone away. L7 in the evidence layering inherits this difficulty. Best case: L7 becomes "side-by-side rendering of engine-native shapes" rather than "unified semantic representation." That's much less than the original L7 framing implies.

**Recommendation embedded here**: When L7 reaches Step 0, accept that it's a rendering / juxtaposition problem, not a semantic translation problem.

### 5.5 v0.1.x preview is product-complete enough to ship

**Claim**: v0.1.1 + v0.1.2 + v0.1.3 form a coherent OSS preview with sufficient capability to give users a usable taste.

**Why unproven**: The capabilities are: write entities, declare rules, evaluate, accept, audit, replay-with-patch, disable-condition, inspect module mapping. That's a lot, but it's all developer-facing. There's no demo notebook for v0.1.2 module IR or v0.1.3 disable. Demo notebook 12 (rule-replay) was the only one made. The "kernel-first README" pitch sells well to Python developers familiar with rules engines; how it lands with non-developer compliance audiences is unknown.

**Validation cost**: One demo notebook for v0.1.3 + one tutorial for "decide if I can replay this rule modification" + one user interview. Mostly write work, not code.

## 6. Structural concerns

These are possible failure modes that don't show up at any single blueprint level.

### 6.1 Foundation / feature inversion risk

The four-layer data architecture (Claim/Annotation/Provenance/View) is the project's deepest claim. v0.1.x added 7 commits across 6 weeks; **none of them touched the foundation**. All decoration on the View layer + execution layer.

This is fine *if* the foundation is right. It's a problem *if* we discover (under real user load) that one of the four layers is misshapen — at that point, every v0.1.x decoration sits on top of a broken layer. The risk is deferred but not absent.

The earlier withdrawal of unified ProofNode tree (2026-03-28) is an example of this: a foundation decision had to be revised based on real engine sample contact. We may have similar foundation revisions coming once real user contact happens with the View / Annotation Store.

### 6.2 Evidence read-only invariant relies on convention

The B'' pivot is enforced by *not exporting a write API*. There's no type-system or compile-time check that prevents a future PR from adding `EvidenceMutableView.set(...)`. The defense-in-depth memory file (`feedback_invariant_defense_in_depth.md`) covers individual data structure mutability (frozen storage); it does not cover module-level write-API additions.

Mitigation: A test that asserts no symbol named `*_set_*` or `*write*` appears in `kernel.audit.__all__`. Or a CI check that flags any new public function in audit/sdk that mutates state derived from an audit package. Currently none of these exist.

### 6.3 The "preview not stable + no users + no release" stuck state

Stated explicitly:
- v0.1.x is not release-stable per user judgment
- Real user feedback is the right input for v0.2 priorities
- Without release, real user feedback won't come
- Without v0.2 priorities, internal work continues to feel like governance
- Governance work isn't progress, by user's own diagnosis

This is a circular dependency. Breaking it requires one of:
- Letting v0.1.x ship despite "not stable" judgment (accept some risk)
- Getting friendly users via private deployment / paid pilot (not a session task)
- Committing to a hard scope without user input (accept the design-only risk)
- Accepting that the project is at natural rest and pivoting effort elsewhere

The user's earlier diagnosis ("default A: real user feedback; B: only L8 if forced") is correct framing. The structural problem is that "default A" is not enactable from inside a coding session.

### 6.4 L0-L11 evidence layering created mid-session

The `evidence-vision-synthesis-2026-05-02.md` was constructed in one sitting, two days ago, as a way to organize forward thinking after v0.1.4 abandonment showed that "evidence completion" might be multi-part. It is **post-hoc taxonomy without implementation contact**.

Likely failure modes:
- L4 (per-frame proof diff) and L5 (cross-run aggregation) might collapse into one capability once attempted
- L8 (audit JSONL persistence) might split (replay-only vs general audit extension)
- L7 (cross-engine translation) will probably need to be re-scoped to "rendering juxtaposition" per §5.4
- L9 (interactive UI) is not really a kernel layer at all — it's a separate product category that might want its own repo
- L10 (sidecar annotation) is currently undefined in any source — claiming it as a layer is aspirational

The taxonomy is useful as a *thinking tool* for blueprint scoping. It is **not** an implementation backlog and should not be treated as one without a fresh Step 0 spike per layer.

### 6.5 Adapter heterogeneity bounds the cross-engine claim

Three engines, three fundamentally different output shapes:

| Engine | Output | Native semantics |
|---|---|---|
| Souffle | proof tree (recursive structure) | Closed-world Datalog with grounded justifications |
| PyReason | event log (DataFrame rows over time) | Open-world graph annotations with timestep updates |
| ProbLog | probability trace + most-likely-explanation | Probabilistic logic with weighted facts and rules |

The 2026-03-28 evidence-graph blueprint already learned this lesson and downgraded "unified tree" to "engine-native envelope + render hint." The downgrade is correct but means: when customers ask "show me how PyReason and Souffle agree about this query," the answer is "they don't reason in the same way; here are the two engine views side by side." That's defensible but doesn't match the elevator pitch of "multi-engine reasoning."

Structural implication for v0.2: **don't promise cross-engine semantic comparison**. Promise cross-engine deployment + per-engine provenance + side-by-side rendering. The first promise is achievable; the second is what's being shipped; the third is what L7 will actually deliver.

### 6.6 Agent layer half-built creates abandonment risk

`src/agent/` has 2390 LOC of substantial control plane (orchestrator, session, framework, draft, recovery, candidate_cache). Its intended completion target (per dialog-agent-v1.1-delta) requires PydanticAI + Burr + Instructor + Langfuse and Layers 2-5 of execution model.

If no one finishes it within ~3-6 months, the half-built control plane will rot:
- Tests will start failing as kernel surfaces evolve
- Agent-side assumptions about kernel APIs will go stale
- The cost to "pick it up where it was left" goes up exponentially
- Eventually it's cheaper to delete the 2390 LOC and start over

Either commit to finishing it or start the abandonment conversation. Neither has happened.

## 7. Realistic evaluation

This section grades the design by dimension. Grades are per "how well does this dimension hold up to honest scrutiny."

| Dimension | Grade | Why |
|---|---|---|
| **Layer split coherence** | 9/10 | Strict, enforced by tests, architecture_principles.md is authoritative, no significant rot. SDK→application boundary holds. Only soft spot: ECSS domain crosses into kernel.sdk (allowed but tracked). |
| **Four-layer data architecture** | 8/10 | Foundational and sound. Annotation Store dual-write to legacy meta_rows is technical debt with no deprecation timeline. Minor risk on Annotation Store taxonomy as new assertion-origin types come in. |
| **B'' pivot integrity** | 8/10 | Principled, well-documented, code-enforced via no-write-surface, but enforcement is by convention not type system. Defense-in-depth applies to data structures (good); not to module-level write API additions (gap). |
| **Release surface governance** | 9/10 | Mature: projection allowlist + denylist + script + clean venv smoke + manifest verification. Default-deny posture. Private monorepo as source of truth, public repo as projection only. |
| **Blueprint workflow** | 9/10 | State machine clear; archive rules clear; reconstructed entries handled separately. Step 0 spike pattern proved its value (caught v0.1.4 negative result before code waste). The 5 stale `draft` blueprints (4+ months no progress) are workflow drift but not workflow flaw. |
| **v0.1.x rule operability surface** | 8/10 | Three patches, all close-out done with full Outcome sections. 818 tests passing. Locator stability invariants well-understood. RuleRef-bound replay properly excluded. Minor weakness: only one demo notebook (rule-replay); no notebook for module-IR or disable-condition. |
| **Multi-engine claim vs reality** | 5/10 | Adapters all present and registered. But v0.1.x is native-only by design; cross-engine evidence translation already stepped back once and remains aspirational. PyReason marked "spike" / "execution-surface V1." Customer-facing claim is more confident than reality warrants. |
| **Original framework framing ("auditable reasoning framework")** | 6/10 | Still in ADR. Still in docs. But 6 weeks of work shifted center of gravity to rule operability product. Drift is principled but undeclared in public-facing materials. README still uses framework framing; recent capabilities are product features. |
| **Conversational UX coverage** | 3/10 | Original vision required this; agent layer has 2390 LOC of control plane but no LLM-backed user surface; PydanticAI + Burr + Instructor + Langfuse all detected as optional, not integrated. Half-built; risk of abandonment. |
| **Ontology integration** | 1/10 | Two drafts in active/ for 4+ months. Zero code. Functionally abandoned but not officially. |
| **Compliance market gaps coverage** | 3/10 | 1 of 4 (decision replay/what-if mechanism via v0.1.1) partially addressed. Rule lifecycle metadata, closure reason library, alert/case lifecycle all zero progress. The 2026-04-03 market-alignment-guide identified these as priority drivers; that didn't translate into roadmap influence. |
| **Evidence layering (L0-L11) maturity** | L0-L3: 9/10 (proven, shipped). L4-L11: 2/10 (paper-only taxonomy created mid-session). | Foundation done; everything above it is design speculation. |
| **"Decision Assurance" market positioning** | 5/10 | Differentiator claim (no competitor offers formal provenance trees) is plausible per competitor analysis. ESA / ECSS validation in progress as research credibility. Real customer demand validation: zero. |
| **Test discipline** | 9/10 | 818 / 1 skip on kernel; Step 0 spike pattern catches scope errors before code; review cycles found and fixed P1/P2 issues twice in v0.1.2 alone; journey tests lock acceptance gates. |
| **Documentation discipline** | 8/10 | Per-module docs reflect current implementation truth; architecture_principles.md is stable; AGENTS.md is clear. Minor weakness: 4-5 stale `draft` blueprints + 1 stale `landed` pre-OSS file create noise. |

### Aggregate honest scoring by category

- **Engineering & architecture quality**: 8-9/10 (genuinely strong; this is where the project shines)
- **v0.1.x product surface**: 7-8/10 (real capability, narrow scope, well-tested)
- **Original full-product completeness**: 25-35% per evidence-vision count, lower (15-20%) if you weight by what original vision considered primary surface (conversational UX)
- **Market validation**: 2-3/10 (positioning is plausible but not validated by any customer commitment)
- **Drift management**: 4-5/10 (drift is happening accidentally; release invariant memory was added recently and is good; broader scope-drift detection has no equivalent)

## 8. Implications for next steps

### 8.1 If you ship v0.1.x as-is

**Risk profile**: Moderate.
- Engineering quality is high; technical risk of OSS readers having a bad install experience is low (smoke verified).
- Customer-facing risk: pitch ("auditable reasoning framework") and product surface ("kernel for Python rule authors with replay capability") may not align with what attracts the right early users.
- Honest framing: "v0.1.x is a kernel-first preview for Python developers building rules engines who need formal provenance + replay. Conversational UX, document extraction, ontology, multi-engine evidence translation are roadmap items."

**What should land first**: README rewrite that honestly states the audience and what's not yet supported. The current README sells "kernel-first external reader framing" but doesn't differentiate "if you want to write Python rules" from "if you want to extract rules from documents conversationally."

### 8.2 If you commit to L8 (audit JSONL persistence)

**Risk profile**: Low-moderate.
- Scope is well-bounded (5-7 rounds per evidence-vision phasing).
- Step 0 must answer: where the engine-neutral export owner lives, JSONL row schema, version field, backward compat with audit packages without replay events.
- Direct deliverable: replay sessions can be reloaded and re-inspected from disk alone. Unblocks L4 historical diff, L5 cross-run aggregation, L9 UI loading.
- Compatible with B''. Compatible with release invariant (internal capability addition, no release base touch).

**What's NOT solved by this**: Real user signal. L8 is engineering on top of unvalidated product direction. If real users want something else (e.g., conversational UX or rule lifecycle metadata), L8 is the wrong investment.

### 8.3 If you pivot back to dialog agent

**Risk profile**: Substantial.
- 2390 LOC of half-built control plane to either complete or replace
- PydanticAI + Burr + Instructor + Langfuse stack to actually integrate (not just detect)
- Layers 2-5 of v1.1-delta execution model to implement (read tools, fact write, rules+docs+routing, advanced)
- Estimated 10-20 rounds depending on how aggressive Layer 2-5 scoping is
- Original target user (non-technical domain expert) would actually be served

**What this would change**: Product story shifts from "kernel for Python rule authors" to "conversational rules engine for compliance officers." Different market, different go-to-market, different success metric.

### 8.4 If you pivot to ontology integration

**Risk profile**: Moderate.
- Phase 1 schema layer (class inheritance, instance classification) is well-scoped per 2026-03-31 ontology-integration-concept
- Implementation is "Datalog sugar on Souffle" (Route A), not new engine
- Adds vocabulary that academic / standards-body audiences (ESA, ECSS, OWL community) recognize
- Doesn't directly address compliance market gaps

**What this would change**: Product positioning gains semantic-web vocabulary. May or may not help with paying market.

### 8.5 If you accept strategic pause + real user test

**Risk profile**: The lowest of the options, but requires patience.
- v0.1.x is preview-shape, not release-shape, but is *useful enough to demo*
- Identify 1-3 friendly users (existing contacts in compliance / aerospace / financial regulation)
- Run a 2-4 week design partner engagement
- The user-driven feedback determines v0.2 priority — not the deferred list
- Internal session work in the meantime: maintenance, demo notebooks, archive cleanup, pyreason adapter Outcome doc completion, careful drafting of replacement README that sets right expectations

**What this delivers**: Real signal. The session loop becomes "respond to user feedback" instead of "find the next plausible patch."

### 8.6 Synthesis recommendation

**The honest pick depends on whether you have access to friendly users in the next 4-6 weeks:**
- **If yes**: 8.5 (strategic pause + real user test). This is the highest-leverage path because it converts paper assumptions to validated direction.
- **If no, and engineering progress is necessary**: 8.2 (L8 audit JSONL persistence). It's the most architecturally valuable deferred candidate, scope-bounded, doesn't require user signal.
- **If you want to validate the original product vision**: 8.3 (dialog agent), but this is a 10-20 round commitment with go-to-market implications, not a tactical session decision.
- **8.1 (ship as-is) and 8.4 (ontology pivot) are weaker picks** in current state.

This document does not pick for you. It frames the question.

## 9. What this document explicitly does NOT do

- Does not commit any of the next-step options to a branch or schedule
- Does not propose any change to `v0.1-oss-prep` or `master` (release branches frozen)
- Does not lock down API signatures or implementation details
- Does not validate market positioning — that requires real customer contact
- Does not predict what real user feedback will say
- Does not declare any pre-OSS blueprint officially abandoned (those drafts are user-judgment items)
- Does not address L11 (mutable evidence) beyond noting it's design-reserved

## 10. Appendix: source provenance

- Sub-agent A extraction archived as part of session transcript; covered all v0.1.x archived blueprints + 2 reference bundles
- Sub-agent B extraction archived as part of session transcript; covered all pre-OSS active drafts + 3 reference docs
- Sub-agent C extraction archived as part of session transcript; covered architecture principles + AGENTS.md + per-module docs across 6 modules
- Cross-reference checks (this session): direct grep of `src/agent/`, `src/service/`, `src/domains/`, `src/kernel/adapters/` for implementation depth + cross-layer import patterns
- Session memory consulted: `MEMORY.md` index + 4 feedback memory files + 2 project memory files (per `~/.claude/projects/-Users-zhenzhili-hnsm-backend/memory/`)
- Code state checked against: rollup branch `v0.1.1-evidence-tree-operational-overlay` @ `575b84e` (= v0.1.1 + v0.1.2 + v0.1.3 stack + 8 archives + evidence-vision bundle)

When this synthesis becomes stale (next major scope decision, real customer contact, or 2-3 month interval), re-run the same three-sub-agent extraction + cross-reference + drift analysis methodology.
