# Blueprint: Agent Extraction — Prompt Residual Patterns fix

- Status: implemented
- Created: 2026-04-11
- Kind: **scoped prompt iteration** (not a feature blueprint)
- Parent (structural): [2026-04-11_agent-extraction-prompt-schema-alignment-fix.md](../archive/2026-04-11_agent-extraction-prompt-schema-alignment-fix.md) (archived)
- Trigger: [B3 iteration 3 report](../../references/working/load-test-2026-04-11/report/load_test_report_2026-04-11_iter3.md)
- Related Modules:
  - `src/factpy_kernel/agent/extraction/prompts.py` (patch — `SYSTEM_PROMPT_TEMPLATE` only)
  - `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py` (extend)

---

## 0. Scope

Eliminate two residual LLM output patterns that B3 iteration 3's PS-06
enriched diagnostic surfaced for the first time:

- **Pattern A — subject leakage** (41/112 proposals, long_01 only):
  `field_values length mismatch for pred_id 'document:mentions': got 2, expected 1`.
  The LLM includes the subject entity (arg0, `entity_ref`) in
  `field_values` in addition to encoding it in `entity_identity`.
- **Pattern B — multi-entry overpacking** (7/112 proposals, medium_01 only):
  `got 3, expected 1` / `got 4, expected 1` on unary predicates.
  The LLM splits a single string slot into multiple `{tag, value}`
  entries instead of emitting multiple separate proposals.

These patterns slipped through iteration 3's PS-01..PS-06 fix because
that fix taught the LLM the **structure** (subject/field split, length
contract, tag==type_domain) in plain text, but never showed a
**wrong-vs-right example** of either failure mode. Rule 9's prose
wording is not enough to dislodge a pretrained heuristic.

**Framing note**: this blueprint is a **prompt iteration**, not a
validator fix. The validator is correctly rejecting both patterns
— rejections are the signal, not the defect. The defect is that the
prompt does not yet provide enough negative examples to stop the LLM
from emitting those shapes in the first place.

**Not in scope**: validator logic, response model (`LLMFactProposal` /
`SegmentExtractionResponse`), schema IR format, scope guard logic,
staging / segmentation, resolution, bundle, manifest schema, LLM
provider change, adding new rules beyond rules 7–10 (we add one
**Examples** section, not new numbered rules).

---

## 1. Root Cause (from B3 iteration 3 data)

### 1.1 Pattern A — subject leakage

**Shape (uniform across 41 rejections)**:
```
reason: schema_field_type_mismatch
detail: field_values length mismatch for pred_id 'document:mentions': got 2, expected 1
```

**Predicate canonical shape**: `document:mentions` in the provisional
`test_schema_ir.json` has `arg_specs = [{"type_domain": "entity_ref"}, {"type_domain": "string"}]`.
After PS-01/PS-02 the LLM sees:
```
- document:mentions subject=arg0:entity_ref field_values=[arg1:string]
```
So the validator's `rest_specs = arg_specs[1:]` has length 1, and
`field_values` is expected to have length 1.

**What the LLM emits**: `field_values = [{tag:entity_ref, value:<ref>}, {tag:string, value:<str>}]`
— length 2, with the subject entity_ref included as the **first**
entry. This is the most natural "unpack the tuple" behavior for a
pretrained model: it sees the predicate has two arg positions and
copies all of them into `field_values`, even though rule 9 says
not to.

**Why rule 9 isn't enough**: rule 9 currently reads:
> "Do NOT include the subject entity in `field_values` — it belongs in `entity_identity`."

This is a **prohibition without a demonstration**. The LLM has to
hold two mental models simultaneously: (a) "the predicate has 2 arg
slots" and (b) "I only fill 1 of them here". Without a concrete
wrong example to contrast against the right one, the pretrained
"unpack everything" habit wins roughly 40% of the time on long_01.

### 1.2 Pattern B — multi-entry overpacking

**Shape (non-uniform across 7 rejections)**:
```
got 3, expected 1   for 'document:mentions'
got 4, expected 1   for 'document:mentions'
got 4, expected 1   for 'module:description'
```

**What the LLM emits**: when a segment enumerates several things
(for example, a paragraph listing "encryption at rest, TLS in transit,
key rotation, and audit logging"), the LLM bundles them into a single
proposal:
```
field_values = [
    {tag: string, value: "encryption at rest"},
    {tag: string, value: "TLS in transit"},
    {tag: string, value: "key rotation"},
    {tag: string, value: "audit logging"},
]
```
— length 4 instead of the required length 1. In other words, the LLM
is using `field_values` as a horizontal "list of mentioned things"
rather than as the ordered tuple of arg1..argN.

**Why rule 9 isn't enough**: rule 9's "length must equal the schema
summary" wording is technically correct, but the LLM has to recognize
that enumeration segments should become **N separate proposals**, not
one proposal with N entries. The prompt never says "emit one proposal
per fact, even if the source paragraph contains multiple facts". The
LLM's default enumeration-handling behavior (bundle them) wins.

### 1.3 Why both patterns are prompt-layer and not validator

- Zero `schema_entity_type_unknown` rejections — the LLM knows which
  entity types exist
- Zero `schema_pred_id_unknown` rejections — the LLM knows which
  predicates exist
- Zero `spec_construction_failure` — the response model shape accepts
  what the LLM emits; it's the validator's `_validate_field_types`
  that correctly rejects the length mismatch
- Zero `scope_*` rejections — scope contract is satisfied
- **100% of rejections** are on `field_values.length` specifically,
  and the two over-count shapes (`+1` and `+N`) map cleanly to the
  two behavioral patterns above

The validator is doing its job. The prompt needs a narrower,
example-driven iteration.

---

## 2. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| PR-01 | **Add one "Examples" section** to `SYSTEM_PROMPT_TEMPLATE`, appearing *after* rules 7–10 and *before* the `Schema:` section. No new numbered rules. | Examples are more effective than another rule for pattern-driven LLMs; separating "Examples" from "Rules" keeps the existing contract clean |
| PR-02 | **The Examples section contains exactly two wrong/right pairs**: (a) subject-leakage pair targeting Pattern A; (b) multi-entry overpacking pair targeting Pattern B | Two pairs are enough to cover the observed residual patterns; more than two risks bloating the prompt and introducing new failure modes |
| PR-03 | **Examples use a generic predicate shape** (`Doc.title:string` style), not `document:mentions` from the B3 provisional schema | Examples should generalize beyond B3; coupling them to `document:mentions` would overfit the prompt to one specific predicate name |
| PR-04 | **Each example pair has explicit `entity_identity` + `field_values` JSON-like fragments** (not full Pydantic JSON, just enough shape to be unambiguous) | The LLM needs to see the shape, not a complete response body. Keeping each example ≤12 lines minimizes token cost |
| PR-05 | **Examples explicitly label the wrong side as "WRONG:" and the right side as "RIGHT:"**, followed by a one-line explanation | Labels give the LLM a classifier signal; the explanation gives it a causal signal |
| PR-06 | **For Pattern B specifically, the right side shows THREE separate proposals for the same source text**, making explicit that enumeration → multiple proposals | The LLM needs to see "N facts in one paragraph become N proposals, each with length-1 `field_values`" rather than inferring it |
| PR-07 | **Rules 7–10 remain unchanged verbatim**; only the new "Examples" section is added | Iteration 3's rules are correct; this blueprint doesn't rewrite them, it supplements them |
| PR-08 | **No validator changes** (no logic, no error message, no detail string) | Validator is behaving correctly; PS-06's enriched detail is already sufficient for future diagnosis |
| PR-09 | **No schema IR changes, no response model changes, no staging changes** | Out of scope |
| PR-10 | **Tests assert on the new examples' presence and shape via substring checks**, not exact-string match | Exact-string match is too brittle for prompt iteration; substring checks lock in the semantic content without blocking future wording tweaks |
| PR-11 | **Extend `test_agent_l4c3a_prompts.py` with a new `SystemPromptExamplesTest` class** | Same file as the existing prompt tests; discoverability and regression coverage follow the PS-01..PS-06 pattern |
| PR-12 | **No B3 manifest change** (`expected_result: success` + `expected_min_valid_specs: 1` stays as-is) | Iteration 4 is still about reducing rejection rate from 43% toward ≤10%; tightening the manifest threshold is deferred to iter 5 per P-06 |

### Explicit non-goals

- Not changing rules 1–6 or rules 7–10 in `SYSTEM_PROMPT_TEMPLATE`
- Not changing `build_schema_summary` output
- Not changing `USER_PROMPT_TEMPLATE` (the per-segment wrapper)
- Not changing `_validate_field_types` logic or error messages
- Not adding "emit separate proposals for each mentioned item" as a
  general rule — we only add the example; the rule inference is the
  LLM's job
- Not adding "smart" retry prompts, self-correction loops, or
  automatic repair of malformed output
- Not changing `test_schema_ir.json` — still provisional and
  non-canonical
- Not adding Langfuse trace inspection for diagnosing prompts (PS-06's
  enriched diagnostic in run records is sufficient for iteration 4)
- Not touching `build_messages`, `build_response_model`, or
  `truncate_prompt_text` — all unchanged

---

## 3. The Fix

### 3.1 `SYSTEM_PROMPT_TEMPLATE` change

Append a new "Examples" section to `SYSTEM_PROMPT_TEMPLATE` between
rules 7–10 and the `Schema:` placeholder. Rules 1–10 are unchanged
verbatim. Below is the full replacement template (the new block is
marked with a comment for review).

```python
SYSTEM_PROMPT_TEMPLATE = """You are a knowledge extraction assistant.
Your task is to extract structured facts from a text segment,
using ONLY the entity types and predicates defined in the provided schema.

Rules:
1. Only propose facts that can be expressed with the given schema.
2. Do not invent new entity types or predicates.
3. Only extract facts directly supported by the text.
4. If no valid facts can be extracted, return an empty proposals list.
5. Do not generate provenance fields (doc_id, segment_id, offsets) — those are injected by the system.
6. Assign a confidence score (0.0-1.0) based on how directly the text supports the fact.

Response format (strict contract — proposals that violate these rules will be rejected):

7. Each predicate in the schema is written as:
     - pred_id subject=<arg0_spec> field_values=[<arg1_spec>, <arg2_spec>, ...]
   The `subject=...` part is the predicate's first argument (arg 0) and represents
   the entity the fact is about. The `field_values=[...]` part lists the remaining
   arguments in order.

8. For each proposal you emit:
   - Put the subject entity's type in `entity_type` (must match one of the
     listed entity types).
   - Put the subject entity's identity field values in `entity_identity` as a
     list of `{{name, value}}` entries, one per identity field declared on that
     entity type. Use the entity's identity field names exactly as shown in
     the schema summary. Do NOT invent identity field names that are not in
     the schema summary.
   - Put the predicate ID in `pred_id` (must match one of the listed predicates).
   - Put the remaining arg values in `field_values` as a list of `{{tag, value}}`
     entries, one per slot in the `field_values=[...]` list shown in the schema
     summary. The order must match the schema summary.

9. `field_values` length contract:
   - `field_values.length` MUST equal the number of entries shown in the
     schema summary's `field_values=[...]` for that predicate.
   - Do NOT include the subject entity in `field_values` — it belongs in
     `entity_identity`.
   - If the predicate's schema summary shows `field_values=[]`, emit an
     empty list.

10. `field_values` tag contract:
    - For each entry, set `tag` to the arg's `type_domain` exactly as shown
      in the schema summary (the part after the colon, e.g. `string`, `int`,
      `entity_ref`).
    - Set `value` to the actual value, typed as one of: string, int, float,
      bool, or null.

Examples (study these before you answer — rejecting proposals that repeat these mistakes):

Suppose the schema summary contains:
  Entities:
  - Doc identity=[title:string]
  Predicates:
  - doc:has_topic subject=arg0:entity_ref field_values=[arg1:string]

Example 1 — subject leakage (Pattern A).

Source text: "The security handbook covers key rotation."

WRONG:
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "security handbook"}}]
  pred_id: "doc:has_topic"
  field_values: [
    {{tag: "entity_ref", value: "Doc:security handbook"}},
    {{tag: "string",     value: "key rotation"}}
  ]
  # length 2 — the subject entity_ref is duplicated here; it already lives in entity_identity.

RIGHT:
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "security handbook"}}]
  pred_id: "doc:has_topic"
  field_values: [
    {{tag: "string", value: "key rotation"}}
  ]
  # length 1 — matches field_values=[arg1:string]. Subject lives only in entity_identity.

Example 2 — multi-entry overpacking (Pattern B).

Source text: "The security handbook covers key rotation, TLS, and audit logging."

WRONG (one proposal):
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "security handbook"}}]
  pred_id: "doc:has_topic"
  field_values: [
    {{tag: "string", value: "key rotation"}},
    {{tag: "string", value: "TLS"}},
    {{tag: "string", value: "audit logging"}}
  ]
  # length 3 — cramming three facts into one proposal's field_values.

RIGHT (three proposals, each length 1):
  proposal A:
    entity_type: "Doc"
    entity_identity: [{{name: "title", value: "security handbook"}}]
    pred_id: "doc:has_topic"
    field_values: [{{tag: "string", value: "key rotation"}}]
  proposal B:
    entity_type: "Doc"
    entity_identity: [{{name: "title", value: "security handbook"}}]
    pred_id: "doc:has_topic"
    field_values: [{{tag: "string", value: "TLS"}}]
  proposal C:
    entity_type: "Doc"
    entity_identity: [{{name: "title", value: "security handbook"}}]
    pred_id: "doc:has_topic"
    field_values: [{{tag: "string", value: "audit logging"}}]
  # Each proposal carries exactly one fact. Enumeration in the source text becomes multiple proposals, not one bloated proposal.

Schema:
{schema_summary}
"""
```

**Size check**: the new Examples section adds roughly 55 lines of
text. Combined with the existing 40-line rules block, the full
`SYSTEM_PROMPT_TEMPLATE` stays under 120 lines (well within any
reasonable context budget for the extraction call).

**Formatting note**: the double-brace `{{...}}` is required because
`SYSTEM_PROMPT_TEMPLATE.format(schema_summary=...)` is called with
`.format()`. The `{{` and `}}` in the examples render as literal
`{` and `}` in the final prompt sent to the LLM. Keep this discipline
consistent with rule 8's existing `{{name, value}}` notation.

### 3.2 Test extensions

Add a new `SystemPromptExamplesTest` class to
`src/factpy_kernel/tests/test_agent_l4c3a_prompts.py`. Keep existing
test classes untouched.

```python
class SystemPromptExamplesTest(unittest.TestCase):
    """PR-01..PR-06: SYSTEM_PROMPT_TEMPLATE has an Examples section
    with two wrong/right pairs targeting the two residual patterns
    from B3 iteration 3.
    """

    def test_prompt_has_examples_section(self) -> None:
        # Section header is present, located before the Schema placeholder
        lower = SYSTEM_PROMPT_TEMPLATE.lower()
        self.assertIn("examples", lower)
        examples_idx = lower.find("examples")
        schema_idx = lower.find("schema:")
        self.assertGreater(schema_idx, examples_idx,
                           "Examples section must appear before the Schema placeholder")

    def test_prompt_has_subject_leakage_example(self) -> None:
        # PR-02 / PR-05: Pattern A has labeled wrong and right variants
        self.assertIn("Example 1", SYSTEM_PROMPT_TEMPLATE)
        # Wrong side shows entity_ref duplicated in field_values
        wrong_block_start = SYSTEM_PROMPT_TEMPLATE.find("Example 1")
        right_block_start = SYSTEM_PROMPT_TEMPLATE.find("RIGHT:", wrong_block_start)
        self.assertGreater(right_block_start, wrong_block_start)
        wrong_block = SYSTEM_PROMPT_TEMPLATE[wrong_block_start:right_block_start]
        self.assertIn("WRONG:", wrong_block)
        self.assertIn("entity_ref", wrong_block)
        # Right side does NOT duplicate subject in field_values
        right_end = SYSTEM_PROMPT_TEMPLATE.find("Example 2", right_block_start)
        right_block = SYSTEM_PROMPT_TEMPLATE[right_block_start:right_end]
        self.assertIn("field_values", right_block)
        # length 1 is asserted via the comment tail
        self.assertIn("length 1", right_block)

    def test_prompt_has_multi_entry_overpacking_example(self) -> None:
        # PR-02 / PR-06: Pattern B has labeled wrong and right variants,
        # right side shows MULTIPLE proposals for one source
        self.assertIn("Example 2", SYSTEM_PROMPT_TEMPLATE)
        example2_start = SYSTEM_PROMPT_TEMPLATE.find("Example 2")
        schema_start = SYSTEM_PROMPT_TEMPLATE.find("Schema:", example2_start)
        self.assertGreater(schema_start, example2_start)
        example2_block = SYSTEM_PROMPT_TEMPLATE[example2_start:schema_start]
        self.assertIn("WRONG", example2_block)
        self.assertIn("RIGHT", example2_block)
        # Right side shows at least three separate proposals
        self.assertIn("proposal A", example2_block)
        self.assertIn("proposal B", example2_block)
        self.assertIn("proposal C", example2_block)

    def test_prompt_examples_do_not_leak_b3_schema_names(self) -> None:
        # PR-03: examples must use a generic 'doc:has_topic' predicate,
        # NOT the B3 provisional 'document:mentions' or 'module:description'.
        # Locking this in prevents accidental overfit to one specific schema.
        examples_start = SYSTEM_PROMPT_TEMPLATE.find("Examples")
        schema_start = SYSTEM_PROMPT_TEMPLATE.find("Schema:", examples_start)
        examples_block = SYSTEM_PROMPT_TEMPLATE[examples_start:schema_start]
        self.assertNotIn("document:mentions", examples_block)
        self.assertNotIn("module:description", examples_block)
        self.assertIn("doc:has_topic", examples_block)

    def test_prompt_keeps_rules_seven_through_ten_unchanged(self) -> None:
        # PR-07: rules 7-10 are preserved verbatim from iteration 3
        self.assertIn("7. Each predicate in the schema is written as:", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("8. For each proposal you emit:", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("9. `field_values` length contract:", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("10. `field_values` tag contract:", SYSTEM_PROMPT_TEMPLATE)
```

**Test count**: 5 new tests in `SystemPromptExamplesTest`, plus the
existing classes untouched. Full suite post-fix: 967 → 972.

### 3.3 No changes to prompts.py functions other than the template

- `build_schema_summary`: unchanged
- `truncate_prompt_text`: unchanged
- `build_messages`: unchanged (still uses
  `SYSTEM_PROMPT_TEMPLATE.format(schema_summary=...)`)
- `USER_PROMPT_TEMPLATE`: unchanged

---

## 4. Impact Analysis

### Code patch surface (max 2 files)

Code-level changes are bounded to these two files. Documentation and
archive updates (blueprint outcome section, module docs, report
followups) are expected in addition and are **not** counted against
this surface.

1. `src/factpy_kernel/agent/extraction/prompts.py` — `SYSTEM_PROMPT_TEMPLATE` only (add Examples section)
2. `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py` — append `SystemPromptExamplesTest` (5 tests)

### Docs / archive touch points (not counted against code surface)

- `docs/blueprints/active/2026-04-11_agent-extraction-prompt-residual-patterns-fix.md` — outcome section filled, then moved to `archive/`
- `docs/blueprints/active/2026-04-11_agent-extraction-prompt-residual-patterns-fix.audit.md` — status transitions + final decisions
- `docs/references/working/load-test-2026-04-11/report/load_test_report_2026-04-11_iter4.md` — new report
- `docs/references/working/load-test-2026-04-11/samples_manifest.yaml` — unchanged (PR-12)
- `src/factpy_kernel/agent/extraction/docs/README.md` — optional update to mention the Examples section if needed

### Backward compatibility

- `SYSTEM_PROMPT_TEMPLATE` is a module-level string; any test that
  asserts on the first 10 rules will still find them verbatim (PR-07).
  The new Examples section sits between rules 10 and `Schema:`.
- `.format(schema_summary=...)` call pattern unchanged. The double-brace
  escaping in the Examples section keeps `{{name, value}}` as literal
  braces, consistent with rule 8.
- No function signature, response model, or validator change.

### Regression surface

- Existing `SystemPromptResponseFormatTest` tests check for phrases
  `"field_values"`, `"length"`, `"type_domain"`, `"entity_identity"`,
  `"subject"`. All still present in the new template (the Examples
  section also mentions them), so no existing prompt test should break.
- The existing `SchemaSummaryFallbackTest` tests operate on
  `build_schema_summary`, which is untouched.
- `test_agent_l4c3a_extractor.py` uses synthetic prompt strings via
  helpers (not the live `SYSTEM_PROMPT_TEMPLATE`), so it's unaffected.

### New failure modes introduced

- **Token cost**: the prompt grows by ~55 lines (~500 extra tokens).
  At `gpt-4o-mini` prices this is negligible (~$0.00008 extra per
  extraction call). Not a blocker.
- **Risk of example-conditioned overfit**: the LLM might start
  emitting every fact as "doc:has_topic" because it's the example
  predicate. Mitigation: PR-03 uses a generic name (`doc:has_topic`)
  that doesn't exist in `test_schema_ir.json`, so any proposal with
  that pred_id would be rejected as `schema_pred_id_unknown` —
  which means this failure mode is **self-detecting** in B3 iteration 4.
- **Risk of the LLM refusing to produce output for unfamiliar predicates**:
  low, because the Examples section explicitly uses a generic predicate
  that's not in the actual schema. The LLM should treat the examples
  as pedagogical and use the live schema for extraction.

---

## 5. Implementation Order

```
Step 1: Apply SYSTEM_PROMPT_TEMPLATE change in prompts.py
        → preserve rules 1-10 verbatim
        → insert Examples section between rule 10 and Schema: placeholder
        → verify double-brace escaping in the examples (f-string → .format)

Step 2: Extend test_agent_l4c3a_prompts.py with SystemPromptExamplesTest
        → 5 new test methods

Step 3: Run prompt-targeted regression first:
        → python -m unittest src.factpy_kernel.tests.test_agent_l4c3a_prompts
        → expected: 5 new + all existing pass

Step 4: Run 4C3-a-specific regression:
        → python -m unittest \
              src.factpy_kernel.tests.test_agent_l4c3a_models \
              src.factpy_kernel.tests.test_agent_l4c3a_validation \
              src.factpy_kernel.tests.test_agent_l4c3a_prompts \
              src.factpy_kernel.tests.test_agent_l4c3a_extractor \
              src.factpy_kernel.tests.test_agent_l4c3a_workflow \
              src.factpy_kernel.tests.test_agent_l4c3a_response_model_schema

Step 5: Run full regression:
        → python -m unittest discover -s src/factpy_kernel/tests
        → expected: 967 prior + 5 new = 972 (2 baseline skips)

Step 6: Rerun B3 iteration 4:
        → PYTHONPATH=src /Users/zhenzhili/miniforge3/bin/python \
            docs/references/working/load-test-2026-04-11/run_load_test.py \
            --manifest docs/references/working/load-test-2026-04-11/samples_manifest.yaml \
            --sample medium_01_security
        → expected: total_rejection_count on Pattern B drops from 7 toward 0
        → then long_01_kernel_p0
        → expected: total_rejection_count on Pattern A drops from 41 toward 0
        → target combined valid rate: >= 90% (from iter 3's 57%)

Step 7: Write B3 iteration 4 report documenting the rejection-rate delta.
```

---

## 6. Acceptance Criteria

### prompts.py

- [ ] `SYSTEM_PROMPT_TEMPLATE` retains rules 1–10 verbatim (PR-07)
- [ ] New "Examples" section appears between rule 10 and `Schema:`
- [ ] Section contains exactly two wrong/right pairs (PR-02)
- [ ] Pair 1 targets Pattern A (subject leakage); the WRONG variant
      includes an `entity_ref` entry in `field_values`, the RIGHT
      variant does not (PR-02)
- [ ] Pair 2 targets Pattern B (overpacking); the WRONG variant
      packs multiple entries into one proposal's `field_values`,
      the RIGHT variant shows three separate proposals (PR-06)
- [ ] Examples use a generic `doc:has_topic` predicate, **not**
      `document:mentions` or `module:description` (PR-03)
- [ ] Double-brace `{{name, value}}` escaping is consistent with
      rule 8 so `.format(schema_summary=...)` doesn't break
- [ ] `build_schema_summary`, `USER_PROMPT_TEMPLATE`, `build_messages`,
      `truncate_prompt_text` are all unchanged

### tests

- [ ] `SystemPromptExamplesTest` — 5 tests pass
- [ ] `SystemPromptResponseFormatTest` — 3 tests still pass (unchanged
      assertions still hold on the new template)
- [ ] `SchemaSummaryFallbackTest` — 5 tests still pass (unchanged)
- [ ] Existing prompt tests in the file — still pass
- [ ] Full regression: 972 tests, 2 baseline skips

### B3 iteration 4

- [ ] Manifest unchanged (`expected_result: success`,
      `expected_min_valid_specs: 1`)
- [ ] `medium_01_security` rerun shows `rejection_count < 7`, ideally 0
      on Pattern B (`got 3/4, expected 1`)
- [ ] `long_01_kernel_p0` rerun shows `rejection_count < 41`, ideally
      low single digits on Pattern A (`got 2, expected 1`)

---

## 7. Outcome / Deviations

### Outcome

- Implemented in:
  - `src/factpy_kernel/agent/extraction/prompts.py`
  - `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py`
  - `src/factpy_kernel/agent/extraction/docs/README.md`
  - `docs/references/working/load-test-2026-04-11/report/load_test_report_2026-04-11_iter4.md`
- Prompt-targeted regression passed.
- 4C3-a regression passed.
- Full regression passed: **972 tests**, **2 skipped**.
- B3 iteration 4 reruns succeeded on both smoke samples:
  - `medium_01_security`: `15 proposals / 14 valid / 1 rejected`, bundle preview `bundle_5cd1b343998c`
  - `long_01_kernel_p0`: `79 proposals / 57 valid / 22 rejected`, bundle preview `bundle_172f0fcd7765`
- The new examples materially improved extraction quality:
  - combined valid rate: **57% -> 76%**
  - medium rejection count: **7 -> 1**
  - long rejection count: **41 -> 22**

### Deviations

- The blueprint target of **>=90% combined valid rate** was **not met**. Iteration 4 ended at **76%**.
- Pattern B (multi-entry overpacking) was effectively removed from the observed smoke set, but Pattern A (subject leakage) remains the dominant residual shape on `long_01_kernel_p0`.
- Resolution remained reachable and bundle preview quality improved, but `merge_count` stayed at `0`; this blueprint did not produce new evidence on dedupe behavior.
- [ ] Combined valid rate across both samples ≥ 90%
- [ ] New run records written with different timestamps
- [ ] B3 iteration 4 report written with the delta table

---

## 7. Known Constraints

1. **LLM behavior is non-deterministic across model versions**: even
   at `temperature=0.0`, future OpenAI updates could shift example
   following strength. The fix targets the most plausible durable
   signal (paired wrong/right examples) but cannot guarantee future
   stability.
2. **Examples are LLM-facing, not user-facing**: their wording is
   optimized for `gpt-4o-mini` comprehension, not for human
   documentation. If a future iteration needs human-doc wording, that's
   a separate concern.
3. **Does not address schema coverage or sample diversity**: if the
   current two B3 samples stay the only ones, iteration 4's measured
   valid rate improvement could be an artifact of those two specific
   documents. Sample expansion (iter 5+) will decouple this.
4. **Does not add a real LLM integration test for example compliance**:
   B3 iteration 4 serves that role. The unit tests only verify the
   prompt's static structure, not LLM compliance with the examples.
5. **Cannot guarantee zero rejections on iteration 4**: the goal is
   ≥90% valid rate, not 100%. Some residual rejection is expected
   because the LLM occasionally still misreads multi-slot predicates,
   and we only have unary predicates in `test_schema_ir.json` so the
   new multi-slot example pattern can't even be tested here.
6. **Rules 1–10 stay at 10**: we're adding an Examples section, not
   new numbered rules. Iteration history (rules 1–6 → rules 1–10 →
   rules 1–10 + Examples) stays linear and auditable.

---

## 8. Outcome / Deviations

Task-complete section (to be filled after Step 7):

- Implemented in:
  - `src/factpy_kernel/agent/extraction/prompts.py` (SYSTEM_PROMPT_TEMPLATE)
  - `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py` (SystemPromptExamplesTest)
- Prompt-targeted regression: <pending>
- 4C3-a regression: <pending>
- Full regression: <pending> (target: 972 tests, 2 skips)
- B3 iteration 4 results:
  - medium_01_security: <pending>
  - long_01_kernel_p0: <pending>
- Measured delta from iter 3: <pending>
- Deviations from blueprint: <pending>

### Audit log

See [2026-04-11_agent-extraction-prompt-residual-patterns-fix.audit.md](./2026-04-11_agent-extraction-prompt-residual-patterns-fix.audit.md)
