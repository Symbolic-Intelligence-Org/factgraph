# Audit Log: Agent Extraction Prompt/Schema Alignment fix

## 2026-04-11 — Initial scoped bugfix

### Trigger

B3 iteration 2 (post-kernel-bugfix) ran both samples to completion on the
real OpenAI path: 229 segments, 35 proposals, but **100% rejection rate**
with `schema_field_type_mismatch: field_values length mismatch`.

See: [B3 iteration 2 report](../../references/working/load-test-2026-04-11/report/load_test_report_2026-04-11_iter2.md)

### Root cause — two combined defects

**Defect A (P-01)**: `build_schema_summary` in prompts.py silently drops
arg_specs without a `name` field. Result: for the B3 provisional schema
(where arg_specs have only `type_domain`), the emitted summary line is
`- document:mentions args=[]` — zero information about predicate arguments.

**Defect B (P-02)**: `SYSTEM_PROMPT_TEMPLATE` never explains the
`field_values` construction contract — that `arg_specs[0]` is the
subject entity (goes in `entity_identity`, not `field_values`), that
`field_values.length == len(arg_specs) - 1`, and that each `tag` must
equal the arg's `type_domain`. Validator enforces these rules
(validation.py:195-198) but the LLM was never told.

Combined effect: even if one defect were fixed alone, the other would
still leave the LLM guessing. Fix both in one patch.

### Why B3 iteration 1 hid this

Iteration 1 failed earlier in the pipeline — instructor_retry_exhausted
from the strict-schema crash kept the LLM from producing any proposals
at all. Only after the strict-schema crash was fixed (see
`2026-04-11_kernel-extraction-response-model-openai-strict-fix.md` —
archived) did the prompt/schema alignment defect become visible.

This is the expected sequence for B3: fix the first blocker, rerun,
discover the next blocker. Each fix is narrower than the last.

### Frozen decisions

| # | Decision | Rationale |
|---|----------|-----------|
| PS-01 | `build_schema_summary` always emits arg info; falls back to `arg{i}:type_domain` if no name | Closes defect A without changing data model |
| PS-02 | Predicate lines mark the subject explicitly: `subject=... field_values=[...]` | Maps visually to what the validator expects; matches `rest_specs = arg_specs[1:]` logic |
| PS-03 | `SYSTEM_PROMPT_TEMPLATE` gets a "Response format" section (rules 7–10) | Closes defect B. States the exact contract the validator enforces |
| PS-04 | Keep existing rules 1–6 unchanged | Minimum diff; no regression risk |
| PS-05 | **Dropped.** Do NOT give `identity_fields` a positional fallback. Canonical SchemaIR (`core/schema/schema_ir.py:_validate_entities`, line 133–136) requires `identity_fields[].name` to be a non-empty string. Emitting `identity{i}:type_domain` placeholders would teach the LLM to produce identity keys that canonical validation would reject downstream. Malformed identity_fields (no canonical name) are silently skipped by `build_schema_summary`; the entity line renders with an empty `identity=[]` rather than synthesized placeholders | An earlier draft of this blueprint proposed the symmetric fallback as "consistency with PS-01". Reviewer caught that canonical validation forbids it. The correct posture is "only predicates get a positional fallback; identity_fields must have real names or be skipped" |
| PS-06 | Optional drive-by: enrich `_validate_field_types` error message with actual/expected counts | One-line improvement to diagnosis; strictly additive |
| PS-07 | Do not change validator logic or contract | Validator is correct per its spec. The bug is that the LLM wasn't taught the contract. Changing the validator would paper over the real defect |
| PS-08 | Do not rename or change any public API | Prompt strings are implementation details |
| PS-09 | Extend existing test_agent_l4c3a_prompts.py rather than add a new file | Discoverability; tests stay with the module they cover |

### Explicit non-goals

- Not changing validator logic
- Not changing response model shape
- Not adding smart retry/repair prompts
- Not adding positional coercion to `_normalize_field_values`
- Not touching `test_schema_ir.json` — B3 intentionally uses provisional non-canonical input; this fix targets prompt-layer robustness when such input reaches extraction, not the schema fixture itself
- Not adding Langfuse trace inspection
- Not doing provider-specific prompt tuning

### Impact on other layers

| Layer | Impact | Reason |
|-------|--------|--------|
| 4C1 (staging) | None | No change to document parsing |
| 4C2 (bundle) | None | No change to FactDraftSpec / DraftBundle |
| 4C3-a (single extract) | Fixed | This is where the prompt lives |
| 4C3-b (batch extract) | Fixed transitively | Calls 4C3-a |
| 4C3-c (entity resolution) | None | Operates on validated FactDraftSpec |
| Observability / Langfuse | None | Metrics unchanged |
| Kernel runtime | None | Zero kernel-side change |

### Relationship to the earlier kernel bugfix

This blueprint is the **direct sequel** to
`2026-04-11_kernel-extraction-response-model-openai-strict-fix.md`
(archived earlier the same day). That fix unblocked the OpenAI strict
schema crash at the API boundary. This fix addresses the prompt/schema
alignment one level up in the stack. Together they close the gap between
"LLM path crashes" and "LLM path produces valid specs".

### Regression expectation

- Prior baseline: 959 tests (2 skipped — 1 pymupdf4llm, 1 other)
- New tests: 7 (4 SchemaSummaryFallback + 3 SystemPromptResponseFormat)
- **Possible**: existing prompt tests asserting on old format need updating.
  Expected minor test-fix churn in `test_agent_l4c3a_prompts.py`.
- Post-fix target: 966 total tests, 2 baseline skips

### B3 iteration 3 expectation

After the fix:
- `schema_field_type_mismatch` should **no longer** be the bulk rejection
  reason
- Either: at least one `valid_count > 0` in the run records, or
- A different, more informative rejection reason (e.g. LLM hallucinates a
  fact the text doesn't support → `scope_min_confidence`, or a wrong
  identity field value → `spec_construction_failure`)
- Both outcomes are valid B3 progress
- If `schema_field_type_mismatch` persists with the actual-vs-expected
  counts now visible (PS-06), that tells us whether the LLM is emitting
  too few or too many field_values — the next diagnostic signal

### Why not a bigger blueprint

Per user direction (2026-04-11):
> 然后开一个很小的 prompt/schema alignment bugfix blueprint ...
> 只改 prompts.py / schema summary wording ...
> 先不要放宽 validator — 当前 validator 合同看起来是对的

Scope is deliberately narrow: only the prompt-side files, no validator
changes, no schema changes, no response model changes. This is the
minimum viable fix for the iteration 2 signal.

### Audit trail

- B3 iteration 2 surfaced this bug
- iteration 2 report is the primary evidence document
- This blueprint closes iteration 2 → iteration 3 transition
- If iteration 3 shows `valid_count > 0`, the blueprint closes cleanly and
  B3 moves on to sample expansion + schema breadth concerns
- If iteration 3 shows a new, different rejection class, the next
  blueprint targets that class — same pattern continues
