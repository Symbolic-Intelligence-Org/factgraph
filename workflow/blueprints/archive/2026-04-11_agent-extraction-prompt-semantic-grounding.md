# Blueprint: Agent Extraction — Prompt Semantic Grounding fix

- Status: implemented with deviations
- Created: 2026-04-11
- Kind: **scoped prompt iteration** (not a feature blueprint)
- Parent (structural): [2026-04-11_agent-extraction-prompt-residual-patterns-fix.md](../archive/2026-04-11_agent-extraction-prompt-residual-patterns-fix.md) (archived)
- Trigger: [B3 review summary 2026-04-11](../../references/working/load-test-2026-04-11/review/review_summary_2026-04-11.md)
- Related Modules:
  - `src/factpy_kernel/agent/extraction/prompts.py` (patch — `SYSTEM_PROMPT_TEMPLATE` only)
  - `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py` (extend)
- Audit Log:
  - [2026-04-11_agent-extraction-prompt-semantic-grounding.audit.md](./2026-04-11_agent-extraction-prompt-semantic-grounding.audit.md)

---

## 0. Scope

Teach the LLM two semantic grounding behaviors that the B3 review pass
identified as the dominant approval-rate blockers on both samples:

- **F-01** (39 of 76 failures = 51%; 45% of all 86 reviewed drafts):
  `Document.title` is fabricated from doc_id hashes, body prose, or section
  headings instead of a stable identifier that appears **verbatim** in
  source text.
- **F-02** (35 of 76 failures = 46%; 41% of all 86 reviewed drafts):
  `module:description` is filled with checklist / acceptance / coverage
  items instead of **declarative descriptions** of what the module is or
  does.

**Framing** (this is the core decision, not an afterthought):

The fix is framed as **positive grounding** (teach the LLM the correct
shape), combined with **per-type abstention when grounding for that type
is weak** (teach the LLM that omitting a proposal of a specific entity
type is a valid action, independent of rule 4's segment-level "empty
proposals list"). Per-type abstention and rule 4 are NOT the same thing:
if the same segment contains valid material for another entity type, the
LLM should still emit those proposals. Rule 4 only applies when no valid
proposals of any type can be made for the segment. The fix is **not**
framed as purely prohibitive rules like "forbid doc_id as title" because
prohibition alone does not teach the LLM what to do instead.

**Not in scope**: validator logic, response model, schema IR changes,
staging changes, `build_schema_summary`, `USER_PROMPT_TEMPLATE`, the numbered
rules 1–10 (verbatim), the iter 4 `Examples` section (verbatim), adding new
rules to the numbered list, `test_schema_ir.json` modification, doc_name /
filename plumbing into the prompt, LLM provider change, smart retry / repair
prompts, Langfuse observability changes, sample set expansion.

---

## 1. Root Cause (from B3 review)

### 1.1 F-01: Document.title fabrication

**Review evidence**: 39/86 drafts tagged `WRONG_ENTITY` (§2.3 and F-01 of
[review summary](../../references/working/load-test-2026-04-11/review/review_summary_2026-04-11.md#31-f-01-documenttitle-fabrication-dominates)).

On medium (7 Document drafts):
- 5 drafts use opaque doc_id hash `8e729d68d5deab3a` as the title
- 1 draft synthesizes a title from body prose
- 1 draft places a code-literal env var name into `Document.title` (dual-axis
  wrong; also counted under F-03 of the review summary)

On long (34 Document WRONG_ENTITY drafts): analogous patterns.

**Positive evidence** — 2 CORRECT Document drafts on long:

- Draft #063: `Document(title="SECURITY.md")` — filename from source text
- Draft #064: `Document(title="KP0-04")` — blueprint hazard ID from source text

Both share a common shape: the `title` value is a **stable identifier that
appears verbatim in the source segment**. The LLM demonstrably knows how to
do this correctly; it just only chooses to ~6% of the time without explicit
guidance.

**Root cause**: The iter 4 `SYSTEM_PROMPT_TEMPLATE` tells the LLM what
`entity_identity` is structurally (rule 8) but never tells it what content
belongs there for entity types whose identity is a "title" or "name" field.
When the source text does not begin with an explicit "Title: X" line, the
LLM falls back to whatever stable-looking string it can reach. The opaque
doc_id shows up in the prompt's contextual data, so it is the most reachable
"stable identifier" from the LLM's perspective.

### 1.2 F-02: `module:description` overreach

**Review evidence**: 35/86 drafts tagged `WRONG_ARG` (§2.3 and F-02 of
[review summary](../../references/working/load-test-2026-04-11/review/review_summary_2026-04-11.md#32-f-02-moduledescription-overreach-dominates-on-long)).

**What the LLM does wrong**: given a segment like

> `AuthService: [ ] Add MFA support [ ] Rotate session keys weekly`

the LLM emits

```
entity_type: "Module"
entity_identity: [{name: "module_name", value: "AuthService"}]
pred_id: "module:description"
field_values: [{tag: "string", value: "Add MFA support"}]
```

The Module identity is correct (clean code-literal). The problem is that
the `field_values` value is a planned task, not a description of what
AuthService currently is or does.

**Positive evidence** — the 8 CORRECT Module drafts (2 on medium, 6 on long):

- `FACTPY_KERNEL_API_KEYS` → "Comma-separated allow-list of valid API keys"
- `FACTPY_KERNEL_AUTH_DISABLED` → "Local-development escape hatch..."
- `HttpRuntimeAPI` → "Minimal HTTP client..."
- `test_service_auth` → "require_a..."
- `test_service_app_v1_auth` → "路由..."
- `test_agent_http_runtime_api_auth` → "..."
- `test_ledger_concurrency` → "并发测..."
- `test_ledger_close` → "thread-lo..."

All 8 share a common shape: the description value is a **declarative noun
phrase** that describes **what the module IS or DOES**, not what someone
plans to do to it.

**Root cause**: `module:description` is semantically permissive — it accepts
any string, and the LLM interprets it as "any text associated with this
module name in the segment". When the segment contains checklists,
acceptance criteria, or coverage headings (common in blueprint-style docs
like long_01_kernel_p0), the LLM binds them to `module:description` because
that is the only description-shaped predicate in the schema.

### 1.3 Why rules 1–10 and iter 4 examples do not catch these

- Rules 1–6 are about predicate/entity type selection and confidence; they
  don't speak to content quality of specific field values.
- Rules 7–10 are about `field_values` structural format (length, tag, arg
  order); they don't speak to what text should appear as an identity value
  or a description value.
- Iter 4 Example 1 (subject leakage) and Example 2 (multi-entry overpacking)
  are **structural** demonstrations about the output shape. Neither
  addresses content selection.

The gap is: there is no prompt-level guidance about **which strings from
the source text should become identity values or description values, and
when to omit a specific proposal type instead** (while still emitting
other valid proposals for the same segment). That is the gap this
blueprint closes.

---

## 2. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| SG-01 | **Core framing is positive grounding + "per-type abstention when grounding for that type is weak"**, NOT purely prohibitive rules. The RIGHT side of each example pair includes both a positive output (when grounding is available) and an "omit this proposal type" fallback labeled `(Emit NO <Doc\|Mod> proposal for this segment ...)` (when grounding is weak). Per-type abstention is **independent** of rule 4: omitting one proposal type does NOT force the segment to return an empty proposals list; if the same segment contains valid material for other entity types, those proposals are still emitted | Prohibition alone leaves the LLM to guess what to do instead. Positive grounding gives the LLM something to copy. Per-type abstention and rule 4 are distinct contracts — conflating them would teach the LLM to skip entire segments whenever one entity type lacks grounding, which is wrong. The review's 8+2 CORRECT drafts prove the positive pattern is learnable |
| SG-02 | **Add one new "Semantic Examples" block** to `SYSTEM_PROMPT_TEMPLATE`, appearing *after* the iter 4 `Examples` block and *before* the `Schema:` section. Section heading is literally "Semantic Examples" (not "Examples 3 / 4" appended into the iter 4 block) | Keeps structural vs. semantic guidance visually separated. A reader (human or LLM) can see immediately that iter 4's Examples and iter 5's Semantic Examples cover different concerns |
| SG-03 | **Exactly two wrong/right pairs** in the Semantic Examples block: (a) Document title grounding (F-01), (b) `module:description` narrowing (F-02) | Matches the two dominant failure modes from the review. More pairs risk bloating the prompt and introducing new failure modes; fewer pairs would leave one of the two dominant failure modes uncovered |
| SG-04 | **Examples use generic predicates** `doc:has_topic`, `mod:has_description`, NOT the B3 provisional `document:mentions` / `module:description`. Same precedent as iter 4 PR-03 | Decouples examples from the B3 provisional schema. Prevents overfit. Self-detecting: if LLM leaks example predicate names into real extractions, iter 4 rerun catches it as `schema_pred_id_unknown` |
| SG-05 | **Document grounding example** must encode exactly this rule: *`Document.title` must be a stable identifier that appears **verbatim** in the source text. If no such identifier exists, emit no Document proposal for that segment.* The word "verbatim" is canonical and appears in the example text | "Verbatim" is the single strongest test of grounding — it rules out doc_id hashes (not in text), body prose synthesis (not verbatim), and section-heading paraphrase (not verbatim). It also gives the LLM a concrete test it can apply token-by-token |
| SG-06 | **Module description example** must encode exactly this rule: *`module:description` must be a **declarative description** of what the module is or does, not a plan / checklist / test expectation / coverage label. If the source text only contains tasks or expectations for the module, emit no Module proposal for that segment.* The word "declarative" is canonical and appears in the example text | "Declarative" is the most orthogonal term to "task / checklist / acceptance / coverage". Unlike those, a declarative statement makes a claim about the current state of the thing being described. A task describes a future action on the thing. This is a distinction the LLM understands natively when prompted |
| SG-07 | **Each example pair shows**: one RIGHT block (positive grounding), one or more WRONG blocks (common failure modes), and one RIGHT block labeled "(omit this proposal type)" showing the explicit per-type fallback. The fallback text must explicitly call out per-type abstention and distinguish it from rule 4's segment-level empty proposals list | Two WRONG blocks in Example 3 (doc_id hash, body-prose synthesis) mirror the two most common medium failure modes. Two WRONG blocks in Example 4 (task, acceptance) mirror the long failure modes. Keeping both example pairs parallel in structure helps the LLM generalize. The explicit per-type-vs-rule-4 distinction prevents the LLM from over-abstaining (skipping entire segments when one type lacks grounding) |
| SG-08 | **Rules 1–10 stay verbatim. Iter 4 Examples 1 and 2 stay verbatim.** Only the new "Semantic Examples" block is inserted | Minimal-diff to a working prompt. All existing structural behavior is preserved. Regression risk is bounded to the new block only |
| SG-09 | **No validator changes, no schema changes, no response model changes, no staging changes, no user-prompt-template changes.** The fix is single-file: `prompts.py` `SYSTEM_PROMPT_TEMPLATE` only | Maximum scope minimization. Any change outside `SYSTEM_PROMPT_TEMPLATE` would invalidate the "prompt-only scoped iteration" framing |
| SG-10 | **No doc_name / filename plumbing** into the prompt or user template | Tempting but out of scope. Plumbing doc_name would require changes to `build_messages` and `USER_PROMPT_TEMPLATE`, and would introduce a new failure mode (what if the doc_name is unhelpful?). Defer to a separate future blueprint if iter 5 alone proves insufficient |
| SG-11 | **Tests use substring checks** on canonical keywords (`verbatim`, `declarative`, `Example 3`, `Example 4`, `Emit NO`, `Per-type abstention`, `other entity types`, `doc:has_topic`, `mod:has_description`), not exact-string matches. Same precedent as iter 4 PR-10 | Substring locks in semantic content without blocking future wording tweaks. Exact-string assertions would break on any whitespace or phrasing change. The `Per-type abstention` and `other entity types` keywords specifically lock in the P1 fix that abstention is type-level and does NOT force rule 4's segment-level empty proposals list |
| SG-12 | **Extend existing `test_agent_l4c3a_prompts.py`** with a new `SystemPromptSemanticExamplesTest` class. Existing test classes (including iter 4's `SystemPromptExamplesTest`) stay untouched | Same discoverability pattern as iter 4 PR-11. Tests stay with the module they cover |
| SG-13 | **B3 manifest unchanged.** `expected_result: success`, `expected_min_valid_specs: 1` | Iter 5's target is strict semantic approval rate, not structural validity. The existing manifest expectations correctly capture "must produce at least one valid draft" and do not need tightening for iter 5 |
| SG-14 | **Target: combined strict approval rate ≥40%** (from 11.6%). **Guardrail: combined salvageable rate ≥95%** (must not drop — drop would signal new hallucination) | 11.6% → 40% is a ~3.5× improvement and a realistic ceiling for a scoped prompt-only iteration. Pushing past 40% likely requires schema expansion (new entity types), which is explicitly out of scope |
| SG-15 | **Absolute proposal volume may decrease** in iter 5's B3 rerun. A decrease accompanied by a strict-rate increase is a pure win and is explicitly NOT a regression | The emit-nothing fallback is expected to reduce total proposals. Measuring only absolute volume would penalize the very behavior the fix teaches. Strict approval rate is the target metric |

### Explicit non-goals

- Not changing rules 1–10 or iter 4 Examples 1 / 2 in `SYSTEM_PROMPT_TEMPLATE`
- Not changing `build_schema_summary`, `USER_PROMPT_TEMPLATE`,
  `build_messages`, or `truncate_prompt_text`
- Not changing `_validate_field_types` (or any validator logic)
- Not changing `LLMFactProposal` / `SegmentExtractionResponse`
- Not changing `test_schema_ir.json`
- Not adding a general "emit separate proposals per item" rule to the
  numbered rules (iter 4 already covered this via Example 2)
- Not adding smart retry prompts or self-correction loops
- Not plumbing doc_name / filename into the prompt
- Not expanding the entity type set, predicate set, or schema surface
- Not adding Langfuse trace inspection
- Not provider-specific prompt tuning (no gpt-4o-specific wording)
- Not adding sample set expansion or new B3 samples
- Not touching `run_load_test.py`, `generate_review_packet.py`, or any
  harness code
- Not re-running or modifying the B3 review packets from 2026-04-11 (those
  are frozen evidence)
- Not backfilling archived iter 4 run_records

---

## 3. The Fix

### 3.1 `SYSTEM_PROMPT_TEMPLATE` change

Append a new "Semantic Examples" block between the existing iter 4
`Examples` block and the `Schema:` placeholder. The full replacement
template is shown below. The new block is the only change — everything
before it is verbatim identical to the current iter 4 template.

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

Examples (study these before you answer — proposals that repeat these mistakes will be rejected):

Suppose the schema summary contains:
  Entities:
  - Doc identity=[title:string]
  Predicates:
  - doc:has_topic subject=arg0:entity_ref field_values=[arg1:string]

Example 1 — subject leakage (common mistake).

Source text: "The security handbook covers key rotation."

WRONG:
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "security handbook"}}]
  pred_id: "doc:has_topic"
  field_values: [
    {{tag: "entity_ref", value: "Doc:security handbook"}},
    {{tag: "string",     value: "key rotation"}}
  ]
  # length 2 — WRONG: the subject entity_ref is duplicated here; it already lives in entity_identity.

RIGHT:
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "security handbook"}}]
  pred_id: "doc:has_topic"
  field_values: [
    {{tag: "string", value: "key rotation"}}
  ]
  # length 1 — matches field_values=[arg1:string]. Subject lives only in entity_identity.

Example 2 — multi-entry overpacking (common mistake).

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
  # length 3 — WRONG: cramming three facts into one proposal's field_values.

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

Semantic Examples (content grounding — these rules decide WHAT strings are allowed as identity values and field values, and when to omit a specific proposal type for a segment while still emitting other valid proposals for the same segment):

Suppose the schema summary contains:
  Entities:
  - Doc identity=[title:string]
  - Mod identity=[mod_name:string]
  Predicates:
  - doc:has_topic subject=arg0:entity_ref field_values=[arg1:string]
  - mod:has_description subject=arg0:entity_ref field_values=[arg1:string]

Example 3 — Document title grounding.

Rule: Doc.title MUST be a stable identifier that appears VERBATIM in the source text (for example: a filename, a blueprint ID, a section anchor, or an explicit self-reference). If the source text does NOT contain a verbatim stable identifier that can serve as the Doc.title, emit NO Doc proposal for that segment.

Source text (has a verbatim stable identifier): "SECURITY.md documents the current key rotation policy."

RIGHT:
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "SECURITY.md"}}]
  pred_id: "doc:has_topic"
  field_values: [{{tag: "string", value: "key rotation policy"}}]
  # Doc.title "SECURITY.md" appears verbatim in the source text. Good grounding.

Source text (no verbatim stable identifier): "This document records the repository-level security hygiene rules."

WRONG (opaque identifier not in source):
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "8e729d68d5deab3a"}}]
  pred_id: "doc:has_topic"
  field_values: [{{tag: "string", value: "security hygiene rules"}}]
  # WRONG: "8e729d68d5deab3a" is an opaque hash and does NOT appear verbatim in the source text. This is a fabricated identity.

WRONG (synthesized from body prose):
  entity_type: "Doc"
  entity_identity: [{{name: "title", value: "repository-level security hygiene rules"}}]
  pred_id: "doc:has_topic"
  field_values: [{{tag: "string", value: "security hygiene rules"}}]
  # WRONG: the title is paraphrased from sentence content. A body prose phrase is not a stable identifier, even if it appears verbatim.

RIGHT (omit this proposal type):
  (Emit NO Doc proposal for this segment. The source text does not contain a verbatim stable identifier that could serve as Doc.title. Per-type abstention: if the same segment contains valid material for other entity types (for example a Mod proposal), still emit those — do NOT skip the entire segment. Rule 4's empty proposals list only applies when no valid proposals of any type can be made for the segment.)

Example 4 — Module description narrowing.

Rule: Mod.has_description's field value MUST be a DECLARATIVE description of what the module IS or DOES, not a plan, checklist, test expectation, acceptance criterion, or coverage label. If the source text only contains tasks or expectations for the module and no declarative description, emit NO Mod proposal for that segment.

Source text (has a declarative description): "AuthService handles token validation and user session management."

RIGHT:
  entity_type: "Mod"
  entity_identity: [{{name: "mod_name", value: "AuthService"}}]
  pred_id: "mod:has_description"
  field_values: [{{tag: "string", value: "handles token validation and user session management"}}]
  # The field value is a declarative description of what AuthService DOES. Good grounding.

Source text (checklist / task items, not declarative): "AuthService: [ ] Add MFA support. [ ] Rotate session keys weekly."

WRONG (task as description):
  entity_type: "Mod"
  entity_identity: [{{name: "mod_name", value: "AuthService"}}]
  pred_id: "mod:has_description"
  field_values: [{{tag: "string", value: "Add MFA support"}}]
  # WRONG: "Add MFA support" is a planned task, not a description of what AuthService currently is or does.

WRONG (acceptance / operational expectation as description):
  entity_type: "Mod"
  entity_identity: [{{name: "mod_name", value: "AuthService"}}]
  pred_id: "mod:has_description"
  field_values: [{{tag: "string", value: "Rotate session keys weekly"}}]
  # WRONG: "Rotate session keys weekly" is an operational expectation, not a declarative description.

RIGHT (omit this proposal type):
  (Emit NO Mod proposal for this segment. The source text only contains tasks and operational expectations for AuthService, not a declarative description of what it is or does. Per-type abstention: if the same segment contains valid material for other entity types (for example a Doc proposal grounded on a verbatim stable identifier), still emit those — do NOT skip the entire segment. Rule 4's empty proposals list only applies when no valid proposals of any type can be made for the segment.)

Schema:
{schema_summary}
"""
```

**Size check**: the new "Semantic Examples" block adds roughly 90 lines.
Combined with the existing rules (40 lines) and iter 4 Examples (55 lines),
the full `SYSTEM_PROMPT_TEMPLATE` is approximately 185 lines. At
`gpt-4o-mini` tokenization that is roughly 1500-1800 tokens in the system
prompt, still well within any reasonable budget.

**Formatting discipline**: the double-brace `{{...}}` escaping is
maintained consistently in the new examples so `.format(schema_summary=...)`
continues to work. No other format placeholders added.

### 3.2 Test extensions

Add a new `SystemPromptSemanticExamplesTest` class to
`src/factpy_kernel/tests/test_agent_l4c3a_prompts.py`. All existing test
classes (including iter 4's `SystemPromptExamplesTest`) stay untouched.

```python
class SystemPromptSemanticExamplesTest(unittest.TestCase):
    """SG-01..SG-15: iter 5 adds a 'Semantic Examples' block after the
    iter 4 'Examples' block, targeting the two dominant semantic grounding
    failures from the 2026-04-11 B3 review pass:

    - F-01 (39 of 76 partial drafts = 51% of failures): Document.title
      fabricated from doc_id, body prose, or section heading. Fix: title
      must be a stable identifier that appears verbatim in source text,
      or omit the Document proposal for that segment.
    - F-02 (35 of 76 partial drafts = 46% of failures): module:description
      populated with checklist/task/acceptance items. Fix: description
      must be declarative, or omit the Module proposal for that segment.

    Per-type abstention is independent of rule 4's segment-level empty
    proposals list: omitting one proposal type does NOT force the segment
    to be skipped entirely. If the same segment contains valid material
    for other entity types, those proposals are still emitted.

    Strict approval rate 11.6% → target ≥40%. Salvageable rate 100%
    guardrail (must not drop).
    """

    def test_prompt_has_semantic_examples_section(self) -> None:
        """SG-02: new section exists, is positioned after iter 4 Examples
        and before the Schema: placeholder.
        """
        lower = SYSTEM_PROMPT_TEMPLATE.lower()
        self.assertIn("semantic examples", lower)
        iter4_examples_idx = lower.find("examples (study these")
        semantic_idx = lower.find("semantic examples")
        schema_idx = lower.find("schema:")
        self.assertGreater(
            semantic_idx,
            iter4_examples_idx,
            "Semantic Examples must appear after iter 4 Examples",
        )
        self.assertGreater(
            schema_idx,
            semantic_idx,
            "Semantic Examples must appear before the Schema: placeholder",
        )

    def test_prompt_has_document_grounding_example(self) -> None:
        """SG-03 / SG-05 / SG-07: Example 3 covers Document.title grounding
        with verbatim-identifier positive rule and emit-nothing fallback.
        """
        self.assertIn("Example 3", SYSTEM_PROMPT_TEMPLATE)
        example3_start = SYSTEM_PROMPT_TEMPLATE.find("Example 3")
        example4_start = SYSTEM_PROMPT_TEMPLATE.find("Example 4")
        self.assertGreater(example4_start, example3_start)
        block = SYSTEM_PROMPT_TEMPLATE[example3_start:example4_start]

        # Positive grounding word (SG-05)
        self.assertIn("verbatim", block.lower())

        # At least one WRONG variant (doc_id hash)
        self.assertIn("WRONG", block)

        # Per-type abstention fallback (SG-07): type-specific, NOT segment-level.
        # These two assertions jointly lock in the P1 fix — abstention is
        # per-entity-type, and it does NOT force rule 4's segment-level
        # empty proposals list.
        self.assertIn("Emit NO", block)
        self.assertIn("Per-type abstention", block)
        self.assertIn("other entity types", block)
        # Must explicitly distinguish per-type abstention from rule 4
        self.assertIn("Rule 4", block)

        # At least one RIGHT variant with positive grounding
        self.assertIn("RIGHT:", block)

    def test_prompt_has_module_description_example(self) -> None:
        """SG-03 / SG-06 / SG-07: Example 4 covers module:description
        narrowing with declarative positive rule and per-type abstention
        fallback.
        """
        self.assertIn("Example 4", SYSTEM_PROMPT_TEMPLATE)
        example4_start = SYSTEM_PROMPT_TEMPLATE.find("Example 4")
        schema_start = SYSTEM_PROMPT_TEMPLATE.find("Schema:", example4_start)
        self.assertGreater(schema_start, example4_start)
        block = SYSTEM_PROMPT_TEMPLATE[example4_start:schema_start]

        # Positive grounding word (SG-06)
        self.assertIn("declarative", block.lower())

        # At least one WRONG variant (task or acceptance)
        self.assertIn("WRONG", block)

        # Per-type abstention fallback (SG-07): type-specific, NOT segment-level.
        # Same P1-fix invariant as Example 3.
        self.assertIn("Emit NO", block)
        self.assertIn("Per-type abstention", block)
        self.assertIn("other entity types", block)
        # Must explicitly distinguish per-type abstention from rule 4
        self.assertIn("Rule 4", block)

        # At least one RIGHT variant with positive grounding
        self.assertIn("RIGHT:", block)

    def test_prompt_semantic_examples_do_not_leak_b3_schema_names(self) -> None:
        """SG-04: Semantic Examples must use generic predicates
        (doc:has_topic, mod:has_description), NOT the B3 provisional
        document:mentions or module:description. Locking this in prevents
        overfit to the specific B3 schema and makes any example-predicate
        leakage self-detecting in the iter 5 B3 rerun (would surface as
        schema_pred_id_unknown).
        """
        semantic_start = SYSTEM_PROMPT_TEMPLATE.find("Semantic Examples")
        schema_start = SYSTEM_PROMPT_TEMPLATE.find("Schema:", semantic_start)
        self.assertGreater(schema_start, semantic_start)
        block = SYSTEM_PROMPT_TEMPLATE[semantic_start:schema_start]

        self.assertNotIn("document:mentions", block)
        self.assertNotIn("module:description", block)

        self.assertIn("doc:has_topic", block)
        self.assertIn("mod:has_description", block)

    def test_prompt_keeps_rules_and_iter4_examples_unchanged(self) -> None:
        """SG-08: rules 1-10 and iter 4 Examples 1 and 2 are preserved
        verbatim from the iter 4 residual-patterns fix. The Semantic
        Examples block is strictly additive.
        """
        # Rules 7-10 verbatim
        self.assertIn(
            "7. Each predicate in the schema is written as:",
            SYSTEM_PROMPT_TEMPLATE,
        )
        self.assertIn(
            "8. For each proposal you emit:",
            SYSTEM_PROMPT_TEMPLATE,
        )
        self.assertIn(
            "9. `field_values` length contract:",
            SYSTEM_PROMPT_TEMPLATE,
        )
        self.assertIn(
            "10. `field_values` tag contract:",
            SYSTEM_PROMPT_TEMPLATE,
        )

        # Iter 4 Example 1 markers
        self.assertIn("Example 1 — subject leakage", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("length 2 — WRONG", SYSTEM_PROMPT_TEMPLATE)

        # Iter 4 Example 2 markers
        self.assertIn("Example 2 — multi-entry overpacking", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("proposal A:", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("proposal B:", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("proposal C:", SYSTEM_PROMPT_TEMPLATE)
```

**Test count**: 5 new tests in `SystemPromptSemanticExamplesTest`. Full
suite target post-fix: 972 → **977** (2 baseline skips unchanged).

### 3.3 No other changes

- `build_schema_summary`: unchanged
- `truncate_prompt_text`: unchanged
- `build_messages`: unchanged (still uses `SYSTEM_PROMPT_TEMPLATE.format(schema_summary=...)`)
- `USER_PROMPT_TEMPLATE`: unchanged
- `validation.py`: unchanged
- `llm.py`: unchanged
- `extractor.py`: unchanged
- Batch extractor, entity resolver, bundle manager: unchanged
- `test_schema_ir.json`: unchanged
- `samples_manifest.yaml`: unchanged
- Runner / review packet generator: unchanged

---

## 4. Impact Analysis

### Code patch surface (max 2 files)

1. `src/factpy_kernel/agent/extraction/prompts.py` — `SYSTEM_PROMPT_TEMPLATE` only (add "Semantic Examples" block)
2. `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py` — append `SystemPromptSemanticExamplesTest` class (5 tests)

### Docs / archive touch points (not counted against code surface)

- `docs/blueprints/active/2026-04-11_agent-extraction-prompt-semantic-grounding.md` — outcome section filled, then moved to `archive/`
- `docs/blueprints/active/2026-04-11_agent-extraction-prompt-semantic-grounding.audit.md` — status transitions + final decisions
- `docs/references/working/load-test-2026-04-11/report/load_test_report_2026-04-11_iter5.md` — new report
- Optional: `src/factpy_kernel/agent/extraction/docs/README.md` — brief note that Semantic Examples block targets content grounding, complementing structural Examples

### Backward compatibility

- `SYSTEM_PROMPT_TEMPLATE` is a module-level string. All iter 4 tests that
  assert on rules 1–10 or Examples 1 / 2 keep passing (verbatim preserved,
  per SG-08).
- `.format(schema_summary=...)` call pattern unchanged. Double-brace
  escaping in the new examples keeps `{{name, value}}` as literal braces,
  consistent with rules 8 and 10.
- No function signature change, no response model change, no validator
  change.

### Regression surface

- Existing `SystemPromptExamplesTest` tests (iter 4) check for "Example 1",
  "Example 2", "proposal A/B/C", "length 1", etc. All still present and
  verbatim in the new template (per SG-08). No iter 4 test should break.
- Existing `SystemPromptResponseFormatTest` and `SchemaSummaryFallbackTest`
  operate on different parts of the prompt; unaffected.
- 4C3-a extractor, batch, resolver, and workflow tests use synthetic prompt
  helpers; unaffected.
- Any test that does a naive length check on `SYSTEM_PROMPT_TEMPLATE` would
  need updating. Per audit of the current tests, no such check exists.

### New failure modes introduced

- **Token cost**: the prompt grows by ~90 lines (~800 extra tokens). At
  `gpt-4o-mini` pricing this is roughly $0.00012 per extraction call;
  negligible.
- **Risk of example-conditioned overfit**: the LLM might start emitting
  every fact with the example predicate `doc:has_topic` or
  `mod:has_description`. Mitigation: PR-04 / SG-04 generic predicates are
  not in `test_schema_ir.json`, so any leakage surfaces as
  `schema_pred_id_unknown` in iter 5 B3 rerun — self-detecting.
- **Risk of the LLM refusing to produce Document proposals entirely**: if
  the per-type abstention fallback is over-applied to Doc, Document
  proposals could drop to near zero. This is acceptable per SG-15 as long
  as the strict
  approval rate on the remaining proposals improves. Measured by iter 5 B3
  rerun.
- **Risk of the LLM refusing Module proposals too aggressively**: same as
  above, same mitigation.

---

## 5. Implementation Order

```
Step 1: Apply SYSTEM_PROMPT_TEMPLATE change in prompts.py
        → keep rules 1-10 verbatim (SG-08)
        → keep iter 4 Examples 1 and 2 verbatim (SG-08)
        → insert new "Semantic Examples" block between iter 4 Examples and Schema: placeholder
        → verify double-brace escaping on all {{name, value}} placeholders
        → verify .format(schema_summary=...) still works by eye-review of placeholder count

Step 2: Extend test_agent_l4c3a_prompts.py
        → append SystemPromptSemanticExamplesTest class
        → 5 new test methods per §3.2

Step 3: Run prompt-targeted regression:
        → python -m unittest src.factpy_kernel.tests.test_agent_l4c3a_prompts
        → expected: 5 new + all existing pass
        → fix any iter 4 test that broke (should be none per SG-08)

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
        → expected: 972 prior + 5 new = 977 (2 baseline skips)

Step 6: Rerun B3 iteration 5 on both samples:
        → PYTHONPATH=src /Users/zhenzhili/miniforge3/bin/python \
              docs/references/working/load-test-2026-04-11/run_load_test.py \
              --manifest docs/references/working/load-test-2026-04-11/samples_manifest.yaml \
              --sample medium_01_security
        → then long_01_kernel_p0
        → new run records go to run_records/

Step 7: Regenerate review packet for iter 5:
        → PYTHONPATH=src /Users/zhenzhili/miniforge3/bin/python \
              docs/references/working/load-test-2026-04-11/generate_review_packet.py \
              --manifest docs/references/working/load-test-2026-04-11/samples_manifest.yaml \
              --sample-ids medium_01_security,long_01_kernel_p0
        → new packet files at review/review_pass_2026-04-XX_*.md

Step 8: Human review pass on iter 5 packets
        → measure new strict approval rate
        → measure new reason_code distribution
        → compare against iter 4 review summary §2 baseline

Step 9: Write B3 iteration 5 report
        → §0 TL;DR with strict-rate delta
        → §1 per-packet comparison table (iter 4 review vs iter 5 review)
        → §2 reason_code distribution shift
        → §3 qualitative findings (which failure mode was closed, which wasn't)
        → §4 residual problems (if any)
        → §5 recommendation for iter 6

Step 10: Move blueprint from active/ to archive/ with filled Outcome section
```

---

## 6. Acceptance Criteria

### prompts.py

- [ ] `SYSTEM_PROMPT_TEMPLATE` retains rules 1–10 verbatim (SG-08)
- [ ] `SYSTEM_PROMPT_TEMPLATE` retains iter 4 Example 1 (subject leakage) verbatim (SG-08)
- [ ] `SYSTEM_PROMPT_TEMPLATE` retains iter 4 Example 2 (multi-entry overpacking) verbatim (SG-08)
- [ ] New "Semantic Examples" block appears between iter 4 Examples and `Schema:` placeholder (SG-02)
- [ ] Block contains exactly two wrong/right pairs (SG-03): Example 3 (Document grounding), Example 4 (Module description narrowing)
- [ ] Example 3 contains the word "verbatim" as the canonical positive grounding signal (SG-05)
- [ ] Example 4 contains the word "declarative" as the canonical positive grounding signal (SG-06)
- [ ] Each example pair has: at least one RIGHT positive-grounding variant, at least one WRONG variant, and one "(Emit NO...)" fallback (SG-07)
- [ ] Examples use generic predicates `doc:has_topic` and `mod:has_description`, not `document:mentions` or `module:description` (SG-04)
- [ ] Double-brace `{{name, value}}` escaping is consistent throughout the new block
- [ ] `build_schema_summary`, `USER_PROMPT_TEMPLATE`, `build_messages`, `truncate_prompt_text` are unchanged

### tests

- [ ] `SystemPromptSemanticExamplesTest` — 5 tests pass
- [ ] `SystemPromptExamplesTest` (iter 4) — 5 tests still pass (unchanged assertions still hold)
- [ ] `SystemPromptResponseFormatTest` (iter 3) — 3 tests still pass
- [ ] `SchemaSummaryFallbackTest` (iter 3) — 5 tests still pass
- [ ] Base `AgentLayer4C3aPromptTests` — still pass
- [ ] Full regression: 977 tests, 2 baseline skips
- [ ] Zero test modifications outside the new class (SG-12)

### B3 iteration 5

- [ ] `samples_manifest.yaml` unchanged (SG-13)
- [ ] Both samples rerun produces new run_records in `run_records/`
- [ ] New review packet generated via `generate_review_packet.py`
- [ ] Human review pass completes; per-draft REVIEW blocks filled
- [ ] **Strict approval rate ≥40% combined** (SG-14), up from 11.6%
- [ ] **Salvageable rate ≥95% combined** (SG-14 guardrail), no regression from 100%
- [ ] Absolute proposal volume decrease is accepted as not a regression (SG-15) if accompanied by strict-rate increase
- [ ] Pattern A (`got 2, expected 1`) rejection shape is unchanged (should still exist because iter 5 does not touch structural layer)
- [ ] Iter 5 report written per Step 9

---

## 7. Known Constraints

1. **Semantic correctness is LLM-text-judgment dependent**. Even with
   perfect examples, the LLM may occasionally misclassify a declarative
   statement as a task or vice versa. The 40% target is realistic, not
   aspirational.
2. **Variance from OBS-01 still applies**. Iter 5 B3 results will be one
   sample from a post-fix distribution. Interpreting small count
   differences (±3 drafts) as iteration effects is unsafe; focus on the
   ratio (strict approval rate), not absolute counts.
3. **Does not address schema expansion**. If the B3 review after iter 5
   shows that the remaining failures are because the schema lacks a
   useful entity type (e.g., `RepoFile`, `EnvVar`, `Script`), that is a
   separate concern requiring a schema expansion blueprint.
4. **Does not address the reason_code taxonomy's single-category
   limitation** (F-03 of review summary). If iter 5's review surfaces
   more dual-axis failures, taxonomy refinement is a separate concern.
5. **Does not add a real LLM integration test for semantic example
   compliance**. B3 iter 5 rerun serves that role. Unit tests only verify
   the prompt's static structure, not LLM compliance with it.
6. **Non-determinism unchanged**. Iter 5 does not land record-replay
   (FUP-01 still deferred). Count variance between runs will be comparable
   to OBS-01.
7. **`document:mentions` and `module:description` predicate names
   themselves may be too loose**. The review mentioned this as a limitation
   (§6.6 of review summary). Iter 5 does not rename them because that
   would be a schema change.
8. **Rules 1–10 remain at 10**. SG-02 adds a new block, not new numbered
   rules. Iteration history (rules 1–6 → rules 1–10 → rules 1–10 +
   Examples → rules 1–10 + Examples + Semantic Examples) stays linear and
   auditable.

---

## 8. Outcome / Deviations

**Status**: implemented with deviations (2026-04-11)

Iter 5 landed the semantic grounding fix on `SYSTEM_PROMPT_TEMPLATE`, full regression passed at 977 tests, and both B3 samples were rerun under a conservative gate. Human review pass completed on the 37-draft combined packet. Verdict locked as "implemented with deviations" on the basis that the primary F-01 goal succeeded on long but the SG-14 strict rate target was missed by 23.8pp and a new F-03 Module routing regression appeared.

### Implementation summary

- Implemented in:
  - `src/factpy_kernel/agent/extraction/prompts.py` — new "Semantic Examples" block added to `SYSTEM_PROMPT_TEMPLATE` between iter 4 Examples and the `Schema:` placeholder. Rules 1–10 and iter 4 Examples 1 & 2 kept verbatim (SG-08)
  - `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py` — new `SystemPromptSemanticExamplesTest` class, 5 tests
  - `src/factpy_kernel/agent/extraction/docs/README.md` — brief note that Semantic Examples block targets content grounding, complementing structural Examples
- Prompt-targeted regression: **21 tests** (iter 3+iter 4's 16 existing + iter 5's 5 new) — all pass
- 4C3-a six-module regression: **52 tests** — all pass
- Full regression: **977 tests, 2 skipped** (+5 from iter 4 baseline of 972, as targeted by SG-12)

### B3 iter 5 canonical runs

- `medium_01_security`: 1 proposal / 1 valid / 0 rejected — `run_records/b3_20260410T233354Z_medium_01_security.json`
- `long_01_kernel_p0`: 43 proposals / 36 valid / 7 rejected — `run_records/b3_20260410T234302Z_long_01_kernel_p0.json`
- Combined canonical: **44 / 37 / 7**
- Volume reduction vs iter 4 mean (94 combined): **−57%** (per SG-15, expected and accepted)

### Conservative gate execution

Before running long, a medium-first gate was applied to catch potential over-abstention (Reading B):

1. **Medium**: 1 valid draft, 0 rejections, 0 structural regression — at the boundary of "near 0" stop condition
2. Gate paused; reviewer chose to continue to long despite the warning because the medium result was ambiguous (could be Reading A or B)
3. **Long**: 36 valid drafts, clearly ruling out segment-level collapse (36 ≫ single-digit threshold)

Gate verdict: **not Reading B**. Proceed with review.

### Review packet generation

- `review/iter5/review_pass_2026-04-11_medium_01_security.md` (1 draft, header re-written with iter 5 context block)
- `review/iter5/review_pass_2026-04-11_long_01_kernel_p0.md` (36 drafts, header re-written with iter 5 context block)
- Regen `valid_count` matched canonical **exactly** on both samples — a small positive signal for iter 5 reproducibility that iter 4 did not achieve (per OBS-01)

### Human review results

| metric | medium | long | combined |
|---|---:|---:|---:|
| drafts | 1 | 36 | 37 |
| yes | 0 | 6 | 6 |
| partial | 1 | 30 | 31 |
| no | 0 | 0 | 0 |
| `WRONG_ENTITY` | 1 | 19 | 20 |
| `WRONG_ARG` | 0 | 8 | 8 |
| `OVERGENERAL` | 0 | 3 | 3 |
| `CORRECT` | 0 | 6 | 6 |

### Target compliance

| metric | target (SG-14) | result | status |
|---|---|---:|:---:|
| combined strict approval rate | ≥40% | **16.2%** | **MISS by 23.8pp** |
| combined salvageable rate | ≥95% (guardrail) | **100%** | **PASS** |

### Qualitative outcome by blueprint goal

- **F-01 Document title grounding** — primary target:
  - **Success on long** (long Document strict rate 5.6% → 33.3%, **+27.7pp**)
  - 11 of 12 long Document drafts now use verbatim stable identifiers (filenames, blueprint hazard IDs)
  - **Residual on medium** (the 1 surviving draft is still a doc_id hash fabrication)
  - Small secondary failure subtype: 3 WRONG_ARG + 3 OVERGENERAL cases on long where title is grounded but field value is imperfect
- **F-02 `module:description` narrowing** — secondary target:
  - **Rate-wise success** (WRONG_ARG rate among Module drafts dropped from ~81% to ~21%)
  - **Net impact muted** because of F-03 below
- **F-03 Module routing breadth** — **NEW regression not anticipated**:
  - iter 4 long Module WRONG_ENTITY count: 0
  - iter 5 long Module WRONG_ENTITY count: **17**
  - Failing identity shapes: file paths (`app_v1.py`), HTTP headers (`X-FactPy-API-Key`), Python stdlib classes (`RLock`), function names (`post_commit`), blueprint hazard IDs (`KP0-04`)
  - Root cause (hypothesis): SG-06 taught description narrowing but did not constrain what counts as a valid `module_name`. The prompt implicitly assumed Module entity routing was already correct, which iter 4 data supported but iter 5 falsified.
- **F-04 Document OVERGENERAL** — **NEW minor failure class**:
  - 3 long drafts with verbatim-grounded titles but vague field values
  - Side effect of successful F-01: with titles correctly verbatim, the LLM extracts Document mentions for segments whose content is too general
  - Severity low
- **Per-type abstention invariant** (P1 fix): **HELD**. Salvageable rate 100%; no segment-level collapse; no new hallucination behavior.

### Deviations from blueprint

1. **Strict rate missed SG-14 target by 23.8pp** (16.2% vs ≥40%). The blueprint was optimistic about the prompt's ability to teach both F-01 and F-02 simultaneously without side effects.
2. **New failure class F-03 (Module routing breadth)** not anticipated in blueprint. SG-06's rationale focused on "description must be declarative" and implicitly assumed Module entity routing was already correct. Iter 4 review data supported that assumption but iter 5 falsified it.
3. **Absolute CORRECT count dropped from 10 to 6** (secondary metric). Four of the 10 iter 4 CORRECT drafts did not survive the abstention: both medium Module drafts (`FACTPY_KERNEL_API_KEYS`, `FACTPY_KERNEL_AUTH_DISABLED`) and the 4 long `test_*` Module drafts. Per SG-15, a volume decrease accompanied by a strict-rate increase is not a regression — but the absolute count drop is worth noting as a sanity-check signal.
4. **New minor failure class F-04 (Document OVERGENERAL)** not anticipated. Small volume (3 drafts), probably tolerable. This is a win-adjacent failure caused by successful F-01 grounding, not a regression of the fix itself.

### What was kept; what was left in place

- **Iter 5 `SYSTEM_PROMPT_TEMPLATE` is retained as the current state.** Do NOT rollback — F-01 Document grounding gain (+27.7pp on long) is real and valuable, salvageable guardrail held, and the F-03 regression is limited to Module routing.
- Iter 5 canonical run records: frozen evidence.
- Iter 5 review packets (medium + long): frozen evidence with filled REVIEW blocks.
- Iter 5 review summary at `docs/references/working/load-test-2026-04-11/review/iter5/review_summary_iter5_2026-04-11.md`: authoritative source for F-01/F-02/F-03/F-04 findings and per-entity-type strict rates.

### Decision on next direction

Reviewer chose **Option β — B3 sample expansion**, deferring any iter 6 prompt iteration until F-03 can be tested across more documents. Rationale:

- 2-sample finding base is too narrow to trust for further prompt tuning (1 medium draft, 24 long Module drafts — noise-dominated)
- F-03 may be specific to `long_01_kernel_p0`'s code-literal-heavy content; needs cross-sample validation
- Sample expansion is cheaper than another prompt iteration and directly tests whether the regression generalizes
- Prompt iteration fatigue: iter 3/4/5 were three consecutive prompt changes with diminishing returns; breaking the pattern with measurement is methodologically cleaner

Iter 6 direction will be decided based on sample expansion results. No new iter 6 blueprint has been opened at archival time.

### Related archived artifacts

- [review_summary_iter5_2026-04-11.md](../../references/working/load-test-2026-04-11/review/iter5/review_summary_iter5_2026-04-11.md) — authoritative iter 5 outcome summary
- Review packets (filled): medium + long at `docs/references/working/load-test-2026-04-11/review/iter5/`
- Canonical run records: `b3_20260410T233354Z_medium_01_security.json`, `b3_20260410T234302Z_long_01_kernel_p0.json`
- Audit log: [2026-04-11_agent-extraction-prompt-semantic-grounding.audit.md](./2026-04-11_agent-extraction-prompt-semantic-grounding.audit.md)
