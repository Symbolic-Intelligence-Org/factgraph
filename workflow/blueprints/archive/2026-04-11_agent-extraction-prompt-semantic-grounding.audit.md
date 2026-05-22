# Audit Log: Agent Extraction Prompt Semantic Grounding fix

## 2026-04-11 — Initial scoped prompt iteration

### Trigger

B3 iteration 4 produced structurally valid drafts but the first human
review pass (86 drafts across 2 samples) found that only 11.6% of drafts
were strictly approvable. The remaining 88.4% were `partial` — the source
text was correctly cited (zero hallucination) but the LLM bound the cited
content to the wrong entity or predicate shape.

Two dominant failure modes surfaced, mutually orthogonal:

- **F-01 (39 of 76 failures = 51%; 45% of all 86 reviewed drafts)**:
  `Document.title` fabrication — LLM synthesizes the title from doc_id
  hashes, body prose, or section headings when the source text does not
  contain an explicit self-referential identifier.
- **F-02 (35 of 76 failures = 46%; 41% of all 86 reviewed drafts)**:
  `module:description` overreach — LLM fills the description field with
  checklists, acceptance bullets, or coverage items instead of
  declarative descriptions of what the module is or does.

See: [review summary 2026-04-11](../../references/working/load-test-2026-04-11/review/review_summary_2026-04-11.md)

The two CORRECT Document drafts on long (SECURITY.md, KP0-04) and the 8
CORRECT Module drafts on medium+long provide a positive template: the
LLM demonstrably knows how to do both correctly when the source text
gives it the right material. The iter 4 `SYSTEM_PROMPT_TEMPLATE` just
doesn't teach it to prefer that material.

### Root cause — prompt-level content guidance gap

Iteration 4's `SYSTEM_PROMPT_TEMPLATE` teaches the LLM:

- Rules 1–6: which predicates and entity types to use (structural filter)
- Rules 7–10: how to shape `field_values` and `entity_identity`
  (structural format)
- Iter 4 Examples 1 & 2: subject/field split and multi-entry overpacking
  (structural error patterns)

But none of the above speak to **which strings from the source text
should become identity values or description values, and when to omit a
specific proposal type** (while still emitting other valid proposals for
the same segment). That is a **content grounding** problem, not a
structural problem. The fix needs content-focused examples.

### Why iter 4's "90% target" miss did not predict this

Iter 4's 90% target was about structural valid rate (rejection shape
count). It was honestly missed (real value ~72% per OBS-01, 76% on a
single lucky run), but even if it had been hit at 90%, that would not
have addressed semantic correctness. Structural validity is a
prerequisite for review, not a sufficient condition for approval.

The B3 review pass is the first time semantic correctness was measured
directly, and it revealed that structural work alone cannot get us to
useful approval rates. Iter 5 is the first iteration framed around the
semantic axis.

### Frozen decisions

| # | Decision | Rationale |
|---|----------|-----------|
| SG-01 | **Core framing**: positive grounding + per-type abstention when grounding for that type is weak. NOT purely prohibitive, and NOT conflated with rule 4's segment-level empty proposals list | Prohibition alone leaves the LLM guessing. The 10 CORRECT drafts from the review give us a positive template to teach. Per-type abstention and rule 4 are distinct contracts: abstaining from one proposal type does NOT force the segment to be skipped entirely when other types could still be emitted |
| SG-02 | Add one new "Semantic Examples" block after iter 4 Examples block. Separate section heading (not "Examples 3/4" inside iter 4 block) | Keeps structural and semantic guidance visually separated. Easier for reviewers (human and LLM) to see they cover different concerns |
| SG-03 | Exactly two wrong/right pairs: (Example 3) Document title grounding, (Example 4) Module description narrowing | Matches the two dominant failure modes. More pairs risk bloat; fewer would leave one mode uncovered |
| SG-04 | Examples use generic predicates `doc:has_topic`, `mod:has_description` (not B3 provisional schema names) | Same precedent as iter 4 PR-03. Prevents overfit; self-detecting if leaked (would show as `schema_pred_id_unknown`) |
| SG-05 | Document grounding rule: title must be a stable identifier that appears **verbatim** in source text. "verbatim" is the canonical keyword | Strongest test of grounding — rules out doc_id (not in text), body prose synthesis (may be verbatim but not an identifier), section-heading paraphrase (not verbatim). Token-by-token testable |
| SG-06 | Module description rule: value must be a **declarative description** of what the module is or does. "declarative" is the canonical keyword | Orthogonal to "task / checklist / acceptance / coverage". A declarative statement makes a claim about current state; a task describes a future action. LLM understands this natively |
| SG-07 | Each pair has: one RIGHT positive-grounding variant, one or more WRONG variants, and one `"(Emit NO <Doc\|Mod> proposal for this segment ...)"` per-type fallback RIGHT block. The fallback text must explicitly call out per-type abstention and distinguish it from rule 4's segment-level empty proposals list | Parallel structure across both example pairs helps the LLM generalize. Two WRONG blocks in Example 3 cover doc_id and body-prose cases; two WRONG blocks in Example 4 cover task and acceptance cases. The entity-type-scoped fallback wording prevents the LLM from over-abstaining (i.e., skipping entire segments when only one entity type lacks grounding) |
| SG-08 | Rules 1–10 verbatim; iter 4 Examples 1 & 2 verbatim. Only the new "Semantic Examples" block is additive | Minimum-diff to working prompt. All existing structural behavior preserved. Regression risk bounded to new block only |
| SG-09 | No validator / schema / response model / staging / user-prompt-template changes. Single-file: `prompts.py` `SYSTEM_PROMPT_TEMPLATE` only | Maximum scope minimization. Any change outside `SYSTEM_PROMPT_TEMPLATE` would invalidate the "prompt-only scoped iteration" framing |
| SG-10 | **No doc_name / filename plumbing**. Tempting but out of scope | Would require changes to `build_messages`, `USER_PROMPT_TEMPLATE`, and potentially runtime session wiring. Introduces a new failure mode (what if doc_name is unhelpful?). Defer to a separate blueprint if iter 5 alone proves insufficient |
| SG-11 | Tests use substring checks on canonical keywords, not exact-string matches | Substring locks in semantic content without blocking future wording tweaks. Exact-string assertions would be too brittle for prompt iteration |
| SG-12 | Extend existing `test_agent_l4c3a_prompts.py` with new `SystemPromptSemanticExamplesTest` class. Existing test classes (incl. iter 4) untouched | Same discoverability pattern as iter 4 PR-11 |
| SG-13 | B3 manifest unchanged. `expected_result: success`, `expected_min_valid_specs: 1` | Iter 5's target is strict semantic approval rate, not structural validity. Manifest captures "≥1 valid draft" which is still the right structural floor |
| SG-14 | Target: combined strict approval rate **≥40%** (from 11.6%). Guardrail: combined salvageable rate **≥95%** (must not regress) | 11.6% → 40% is ~3.5× improvement, realistic for prompt-only scope. Salvageable guardrail catches new hallucination if it emerges |
| SG-15 | Absolute proposal volume may decrease. Decrease + strict-rate increase is a win, NOT a regression | The emit-nothing fallback is expected to reduce total proposals. Measuring volume alone would penalize the taught behavior |

### Explicit non-goals

- Not changing rules 1–10 verbatim
- Not changing iter 4 Examples 1 & 2 verbatim
- Not changing `build_schema_summary`, `USER_PROMPT_TEMPLATE`,
  `build_messages`, or `truncate_prompt_text`
- Not changing validator logic
- Not changing response model (`LLMFactProposal` / `SegmentExtractionResponse`)
- Not changing `test_schema_ir.json`
- Not adding new rules to the numbered rule list
- Not plumbing doc_name / filename into the prompt
- Not expanding the schema (no new entity types, no new predicates)
- Not changing samples_manifest.yaml
- Not adding smart retry / repair / self-correction loops
- Not adding Langfuse trace inspection for prompt diagnosis
- Not provider-specific prompt tuning
- Not rerunning or modifying the 2026-04-11 review packets (frozen evidence)
- Not backfilling archived iter 4 run_records

### Impact on other layers

| Layer | Impact | Reason |
|-------|--------|--------|
| 4C1 (staging) | None | No parsing change |
| 4C2 (bundle) | None | No FactDraftSpec / DraftBundle change |
| 4C3-a (single extract) | Fixed | Prompt template lives here |
| 4C3-b (batch extract) | Fixed transitively | Calls 4C3-a |
| 4C3-c (entity resolution) | None | Operates on validated specs |
| Observability / Langfuse | None | Metrics unchanged |
| Kernel runtime | None | Zero kernel-side change |
| Test suite | +5 tests | `SystemPromptSemanticExamplesTest` |
| B3 harness | None | `run_load_test.py` and `generate_review_packet.py` untouched |

### Relationship to prior archived blueprints

This blueprint is the **direct continuation** of the residual-patterns
fix:

- [`2026-04-11_agent-extraction-prompt-residual-patterns-fix.md`](../archive/2026-04-11_agent-extraction-prompt-residual-patterns-fix.md) (archived)

Key differences from iter 4:

- **PR-01..PR-12** (iter 4) addressed **structural** gaps: wrong output
  format (subject leakage, multi-entry overpacking). Reduced structural
  rejection rate from 43% to ~28% (running mean).
- **SG-01..SG-15** (iter 5) addresses **semantic** gaps: wrong content
  choice (fabricated titles, checklist-as-description). Targets raising
  strict semantic approval rate from 11.6% to ≥40%.

The iteration audit trail is linear:

1. **iter 1** (deps missing) → fix environment
2. **iter 2** (strict-schema crash) → kernel bugfix (archived
   `openai-strict-fix`)
3. **iter 3 structural-alignment** (PS-01..PS-06) → archived
   `prompt-schema-alignment-fix`
4. **iter 4 structural-examples** (PR-01..PR-12) → archived
   `prompt-residual-patterns-fix`
5. **iter 5 semantic-examples** (SG-01..SG-15) → **this blueprint**

Each blueprint narrower in scope than the previous. Iter 5 touches the
same two files iter 4 touched (`prompts.py` + `test_agent_l4c3a_prompts.py`)
with the same shape of change (template edit + new test class).

### Pre-implementation regression baseline

- Full suite: 972 tests, 2 baseline skips (as of iter 4 archived state)
- Target post-implementation: 977 tests, 2 baseline skips (5 new tests in
  `SystemPromptSemanticExamplesTest`)

### B3 iteration 5 expected outcomes

**Primary metric**: combined strict approval rate
- iter 4 baseline: **11.6%** (10/86)
- iter 5 target: **≥40%**
- iter 5 floor: **≥30%** (below this, the blueprint is under-performing
  and iter 6 decisions should revisit examples or consider schema work)

**Secondary metric**: Module strict rate, Document strict rate, per-sample
breakdowns

**Guardrail metrics**:
- Salvageable rate: must stay ≥95% (dropping below this signals new
  hallucination behavior introduced by the fix — would be a regression)
- Pattern A rejection shape: must stay structurally unchanged (iter 5
  does not touch the structural layer; Pattern A rate should be stationary
  modulo OBS-01 variance)

**Expected side effect** (acceptable per SG-15): absolute proposal count
may drop as the LLM learns to omit specific proposal types when
grounding for that type is weak. Note: this is per-type abstention, not
segment-level skipping. A segment with weak Doc grounding but strong
Mod grounding should still produce a Mod proposal.

### Open questions at draft time

- **Q1**: Should Example 3 also include a third WRONG variant showing
  section-heading-as-title (e.g., `title="§1.2 Authentication"`)?
  **Decision**: No, keep it to two WRONG variants. The doc_id and
  body-prose cases cover the dominant medium and long patterns. Adding a
  third would bloat the block without matching a specific observed
  failure mode.
- **Q2**: Should the "(Emit NO proposal)" fallback be capitalized
  differently, e.g., `# (SKIP)` to make it visually distinctive?
  **Decision**: Use `(Emit NO Doc proposal for this segment. ...)` prose
  format with explicit **entity-type scoping**. Do NOT cite rule 4 as
  "parallel wording" — rule 4 is segment-level ("return an empty
  proposals list") while iter 5's abstention is per-entity-type.
  Conflating the two would teach the LLM to skip entire segments
  whenever one entity type lacks grounding, which is wrong. The fallback
  prose explicitly distinguishes: "if the same segment contains valid
  material for other entity types, still emit those proposals".
- **Q3**: Should iter 5 examples reference rule 4 explicitly?
  **Decision — revised from an earlier draft**. The earlier draft said
  "each emit-nothing fallback mentions 'per rule 4' to ground the
  instruction in existing prompt structure". That phrasing conflated
  per-type abstention with rule 4's segment-level empty proposals list
  and is corrected by the P1 fix. The current fallback text references
  rule 4 only to **distinguish** the two concerns: "Rule 4's empty
  proposals list only applies when no valid proposals of any type can
  be made for the segment". Rule 4 is named for disambiguation, not
  for parallel authority.
- **Q4**: Should we genericize the Module entity name too (e.g.,
  `Thing identity=[thing_name:string]`)? **Decision**: No — using `Mod`
  is close enough to `Module` to be readable, and making it fully
  generic (`Thing`) would reduce the LLM's ability to map the example to
  real modules. `Doc` and `Mod` are the right abstraction level.

### Status transitions

- 2026-04-11 — draft created based on B3 review summary 2026-04-11
- 2026-04-11 — scoped. Two user review findings closed:
  - **[P1]** abstention granularity was narrowed from segment-level to
    per-entity-type. Fallback RIGHT blocks in Example 3 and Example 4
    now explicitly say "Per-type abstention: if the same segment contains
    valid material for other entity types, still emit those — do NOT
    skip the entire segment. Rule 4's empty proposals list only applies
    when no valid proposals of any type can be made for the segment."
    Applied across 9 locations in blueprint + 5 locations in audit log.
  - **[P2]** F-01 / F-02 denominators in blueprint §0 and audit log
    trigger section were corrected. "39/86 = 45% of failures" was wrong
    (86 is all reviewed drafts, not failures). Now shows both
    "39 of 76 failures = 51%" (primary) and "45% of all 86 reviewed
    drafts" (secondary).
  - **[nit]** Audit SG-07 row wording refined from `"(Emit NO proposal)"
    fallback RIGHT block` to `"(Emit NO <Doc|Mod> proposal ...)"` per-type
    fallback RIGHT block, for consistency with the corrected SG-01 / SG-11
    wording.
- 2026-04-11 — **implemented with deviations**. Code patches applied to `prompts.py` + `test_agent_l4c3a_prompts.py` by reviewer; module docs note added. Full regression **977 tests, 2 skipped** (target met per SG-12). B3 canonical runs executed on both samples via conservative gate (medium first, long second); gate ruled out Reading B (segment-level over-abstention). Iter 5 review packets generated into `review/iter5/` with iter 5 context blocks in headers. Human review pass completed on 37 drafts (1 medium + 36 long). Strict approval rate **16.2%** missed SG-14 target of ≥40% by 23.8pp; salvageable guardrail **100%** held. Primary F-01 goal (Document title grounding) succeeded on long (Document strict rate 5.6% → 33.3%, +27.7pp). F-02 (`module:description` narrowing) rate-wise succeeded (WRONG_ARG rate 81% → 21% among Modules). **Two new failure classes introduced not anticipated in blueprint**: F-03 Module routing breadth (0 → 17 Module WRONG_ENTITY on long; file paths, HTTP headers, stdlib classes, hazard IDs misrouted to Module) and F-04 Document OVERGENERAL (3 drafts on long, minor). Reviewer chose Option β (B3 sample expansion) as next direction, deferring iter 6 prompt work until F-03 can be tested across more documents. Iter 5 `SYSTEM_PROMPT_TEMPLATE` retained — no rollback. Full outcome details in blueprint §8 and in `review/iter5/review_summary_iter5_2026-04-11.md`.
- 2026-04-11 — **archived**. Blueprint + audit log moved from `docs/blueprints/active/` to `docs/blueprints/archive/`. Historical rationale only from this point; iter 5 state is the current `SYSTEM_PROMPT_TEMPLATE` baseline for any future iteration.

### Review notes

The blueprint is proposed as a **single** iteration. If the user chooses
to split it (e.g., Document grounding first, module narrowing second),
the split should be recorded here as a status transition. The current
draft treats them as a single atomic prompt iteration because both fixes
share the same single file edit and the same test class.
