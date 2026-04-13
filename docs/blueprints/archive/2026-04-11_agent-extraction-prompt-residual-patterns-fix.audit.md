# Audit Log: Agent Extraction Prompt Residual Patterns fix

## 2026-04-11 — Initial scoped prompt iteration

### Trigger

B3 iteration 3 (post prompt/schema alignment fix) ran both samples to
completion and produced the **first valid extractions** (0% → 57%
combined valid rate). However PS-06's enriched diagnostic surfaced two
distinct residual rejection patterns that the PS-01..PS-06 fix did not
cover:

- **Pattern A — subject leakage** (41/112, long_01 only): `got 2, expected 1`
  for `document:mentions`. LLM includes the subject entity_ref in
  `field_values` as an extra entry.
- **Pattern B — multi-entry overpacking** (7/112, medium_01 only):
  `got 3/4, expected 1` for `document:mentions` and `module:description`.
  LLM splits a single string slot into multiple tagged entries when a
  segment enumerates several items.

See: [B3 iteration 3 report](../../references/working/load-test-2026-04-11/report/load_test_report_2026-04-11_iter3.md)

### Root cause — prompt pattern recognition gap (not structural)

The PS-01..PS-06 fix gave the LLM the **structural** contract in plain
text:
- Rule 7: schema summary format (`subject=arg0:X field_values=[arg1:Y, ...]`)
- Rule 8: how to map proposal fields
- Rule 9: length contract + "do not include subject"
- Rule 10: tag == type_domain

But rule 9's prohibition ("Do NOT include the subject entity in
`field_values`") is a **text statement without a concrete example**. A
pretrained LLM's "unpack all args" habit wins against a pure text
prohibition roughly 40% of the time on long_01. Similarly, nothing in
rules 7–10 says "emit one proposal per fact, even if the source contains
multiple facts" — so the LLM's default enumeration-bundling behavior
wins on medium_01.

The fix adds one **Examples** section with two wrong/right pairs, one
per pattern. No new numbered rules — rules 1–10 stay verbatim. Just
paired demonstrations.

### Why iteration 3 hid these patterns

Iteration 2 had zero valid extractions and 100% uniform
`schema_field_type_mismatch` rejections — the LLM didn't even know the
shape of `field_values`, so all failures looked identical. Iteration 3
fixed the "shape completely unknown" problem, and the residual
rejections became informative: now we can see the LLM getting **near**
the right shape but missing in two specific ways.

This is the expected B3 progression: each fix reveals the next blocker,
and each blocker is narrower than the last.

### Frozen decisions

| # | Decision | Rationale |
|---|----------|-----------|
| PR-01 | Add one "Examples" section after rules 7–10, before the Schema: placeholder. No new numbered rules | Examples are more effective than prose for pattern-driven LLMs; keeps the rule count linear (1–10) |
| PR-02 | Exactly two wrong/right pairs: one for Pattern A, one for Pattern B | Matches the observed residual patterns; more examples risk bloating the prompt and introducing new failure modes |
| PR-03 | Examples use a generic `doc:has_topic` predicate, not `document:mentions` | Decouples examples from the B3 provisional schema; prevents overfit; also makes example-predicate leakage self-detecting in iter 4 (would surface as `schema_pred_id_unknown`) |
| PR-04 | JSON-like fragments in examples, not full Pydantic response bodies | Keeps each example ≤12 lines; the LLM needs to see the shape, not a complete round-trip |
| PR-05 | Explicit "WRONG:" and "RIGHT:" labels with one-line explanatory comments | Labels give the LLM a classifier signal; comments give a causal signal |
| PR-06 | For Pattern B, the RIGHT side shows **three separate proposals** for one source segment | Makes "N facts → N proposals" explicit rather than leaving it to inference |
| PR-07 | Rules 1–10 stay verbatim | No regression risk; iteration 3 rules were correct, they just needed backup examples |
| PR-08 | No validator changes (no logic, no message, no detail string) | Validator is doing its job; PS-06's enriched detail is already sufficient for diagnosis |
| PR-09 | No schema IR changes, response model changes, or staging changes | Out of scope |
| PR-10 | Tests use substring checks, not exact-string matches | Exact-string match is too brittle for prompt iteration; substring locks in semantic content without blocking wording tweaks |
| PR-11 | Extend existing `test_agent_l4c3a_prompts.py`, add new `SystemPromptExamplesTest` class | Same discoverability pattern as PS-01..PS-06 |
| PR-12 | B3 manifest unchanged (`expected_result: success`, `expected_min_valid_specs: 1`) | Iter 4 is still about reducing rejection rate; tightening to `expected_min_valid_rate` is deferred to iter 5 per P-06 |

### Explicit non-goals

- Not changing rules 1–10 in `SYSTEM_PROMPT_TEMPLATE`
- Not changing `build_schema_summary`, `USER_PROMPT_TEMPLATE`,
  `build_messages`, or `truncate_prompt_text`
- Not changing `_validate_field_types` (or any validator logic)
- Not adding a general "emit separate proposals per item" rule — we
  only add the example and let the LLM infer
- Not adding smart retry prompts or self-correction loops
- Not changing `test_schema_ir.json` — still provisional non-canonical
- Not adding Langfuse trace inspection (PS-06's diagnostic in run
  records is sufficient for iter 4)
- Not touching `LLMFactProposal` / `SegmentExtractionResponse` shape
- Not provider-specific prompt tuning

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
| Test suite | +5 tests | SystemPromptExamplesTest |

### Relationship to PS-01..PS-06

This blueprint is the **direct continuation** of
[`2026-04-11_agent-extraction-prompt-schema-alignment-fix.md`](../archive/2026-04-11_agent-extraction-prompt-schema-alignment-fix.md)
(archived). Key differences:

- PS-01..PS-06 addressed **structural** gaps: the LLM didn't know the
  shape at all (100% rejection rate, all uniform).
- PR-01..PR-12 addresses **pattern recognition** gaps: the LLM knows
  the shape but still defaults to pretrained heuristics for two
  specific patterns (41% combined rejection rate, two distinct
  sub-patterns).

The audit trail is linear:
- iter 1: deps missing → fix environment
- iter 2: strict-schema crash → kernel bugfix (`openai-strict-fix`)
- iter 3 prompt-alignment (PS-01..PS-06) → `prompt-schema-alignment-fix`
- iter 4 prompt-examples (PR-01..PR-12) → **this blueprint**

Each blueprint narrower than the last.

### Pre-implementation regression baseline

- Full suite: 967 tests, 2 baseline skips (as of PS-06 implementation)
- Target post-implementation: 972 tests, 2 baseline skips (5 new)

### Open questions at draft time

- **Q1**: Should the examples also cover a multi-slot predicate
  (e.g., `subject + string + int`)? The current examples only cover
  unary predicates because that's all `test_schema_ir.json` has.
  **Decision**: No, defer to iter 5. Adding a multi-slot example
  without a multi-slot predicate in the schema means the example
  can't be validated against real extraction output, and would risk
  overfitting the example shape. Revisit after schema expansion.
- **Q2**: Should we also add an example showing the `null` / empty
  proposals list case (rule 4)? **Decision**: No, that rule has
  never been violated in B3. Only add examples for observed failure
  modes.
- **Q3**: Should the examples use a deterministic predicate name that
  matches nothing in the schema (e.g., `example:predicate`) to make
  leakage obvious? **Decision**: `doc:has_topic` is generic enough and
  reads naturally as pedagogy; if LLM leaks it into real extractions,
  that's still caught as `schema_pred_id_unknown` in iter 4.

### Status transitions

- 2026-04-11 — draft created based on B3 iteration 3 report
- 2026-04-11 — scoped (user review: no blocking findings; two non-blocking wording fixes applied — Pattern B tag-invention claim softened in iter 3 report §0 and §2.4; "Files touched (max 2)" clarified to "Code patch surface (max 2 files)" with separate docs/archive touch point list)
- (pending: implementing → implemented → archive)

### Non-blocking review fixes applied at scoping time

1. **iter 3 report Pattern B wording**: original text said "sometimes
   inventing tags that aren't in the schema summary", which ran ahead
   of the evidence. Current `rejection_samples` only show length
   mismatch; length-mismatch short-circuits `_validate_type_domain`
   so any `tag != type_domain` behavior is not independently proven.
   Softened to "may also be inventing tags outside the schema, but
   current evidence proves overpacking first" and added a §2.4
   Scoping note explaining the short-circuit behavior and how iter 4
   will surface it.
2. **Blueprint §4 header**: "Files touched (max 2)" implied the
   whole blueprint only touches 2 files, which conflicts with the
   repo workflow (blueprint outcome fill, audit log, iter 4 report,
   optional module docs update). Clarified to "Code patch surface
   (max 2 files)" and added a separate "Docs / archive touch points"
   subsection listing the expected non-code updates.
