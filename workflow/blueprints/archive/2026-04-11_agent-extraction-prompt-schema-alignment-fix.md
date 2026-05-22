# Blueprint: Agent Extraction — Prompt / Schema Alignment fix

- Status: implemented
- Created: 2026-04-11
- Kind: **scoped bugfix** (not a feature blueprint)
- Parent: [2026-04-10_agent-layer4c3a-single-segment-extraction.md](../archive/2026-04-10_agent-layer4c3a-single-segment-extraction.md) (archived)
- Trigger: [B3 iteration 2 report](../../references/working/load-test-2026-04-11/report/load_test_report_2026-04-11_iter2.md)
- Related Modules:
  - `src/factpy_kernel/agent/extraction/prompts.py` (patch)
  - `src/factpy_kernel/agent/extraction/validation.py` (optional drive-by for P-03)
  - `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py` (extend)

---

## 0. Scope

Fix two prompt-side defects discovered in B3 iteration 2 that cause 100%
of LLM proposals to be rejected with `schema_field_type_mismatch: field_values length mismatch`:

- **P-01**: `build_schema_summary` drops arg information entirely when
  an arg lacks a `name` field, emitting `- pred_id args=[]`. The LLM
  receives no information about predicate arguments.
- **P-02**: `SYSTEM_PROMPT_TEMPLATE` never explains the `field_values`
  construction contract: the subject entity is in `entity_identity`,
  `field_values.length == len(arg_specs) - 1`, and each `tag` must equal
  the corresponding arg's `type_domain`.

**Framing note**: B3 iteration 2 used the provisional non-canonical
`test_schema_ir.json` (which intentionally omits `name` on arg_specs).
Canonical SchemaIR validation in
[`core/schema/schema_ir.py:_validate_predicates`](../../src/factpy_kernel/core/schema/schema_ir.py#L144)
forbids that shape. The problem this blueprint fixes is **prompt-layer
robustness against non-canonical input**, plus the pre-existing gap in
the response-format contract that would affect canonical inputs too.
**Validator logic is untouched.**

**Not in scope**: validator logic, canonical SchemaIR schema, response
model shape, adding new arg types, LLM provider change, prompt
engineering beyond the minimal rules needed to align LLM output with
the existing validator contract.

---

## 1. Root Cause

### 1.0 Scope of the diagnosis

**Important framing**: the bug B3 iteration 2 surfaced is **prompt
robustness against the provisional non-canonical B3 smoke schema**, not
"canonical SchemaIR silently loses args". The B3 `test_schema_ir.json`
file explicitly says at the top:

> "Not a real FactPy SchemaIR — only satisfies the runner's preflight
> (non-empty dict with entities + predicates lists). If you want to
> exercise the LLM extraction path, replace this with a real schema..."

Its `predicates[].arg_specs` intentionally omit the `name` field (only
providing `type_domain`), which is not permitted by canonical
SchemaIR validation in
[`core/schema/schema_ir.py:_validate_predicates`](../../src/factpy_kernel/core/schema/schema_ir.py#L144).
A canonically-validated schema would never reach `build_schema_summary`
with nameless arg_specs; only the smoke path does.

**But**: the prompt layer currently accepts `dict[str, Any]` schema
input without demanding canonical validation. That means any input —
B3 smoke, hand-written test fixtures, pre-validation dry runs — could
hit the same silent-drop behavior. The fix makes the prompt robust to
non-canonical input without changing the validator contract.

**Validator logic is untouched.** Canonical SchemaIR still enforces all
existing name/type_domain requirements. This blueprint only changes what
the **prompt** emits and what the **LLM** is taught.

### 1.1 Defect A (prompt-side): `build_schema_summary` silently drops nameless args

[`prompts.py:71-80`](../../src/factpy_kernel/agent/extraction/prompts.py#L71) currently does:

```python
for arg in predicate.get("arg_specs", []):
    if not isinstance(arg, dict):
        continue
    name = arg.get("name")
    type_domain = arg.get("type_domain")
    if isinstance(name, str) and name:
        suffix = f":{type_domain}" if isinstance(type_domain, str) and type_domain else ""
        arg_specs.append(f"{name}{suffix}")
predicate_lines.append(f"- {pred_id} args={arg_specs}")
```

**Bug**: The `if isinstance(name, str) and name:` gate means any arg
without a `name` is silently dropped. On the B3 provisional schema
(arg_specs like `{"type_domain": "entity_ref"}`), the emitted line for
`document:mentions` becomes `- document:mentions args=[]`.

The LLM then sees a predicate with apparently zero arguments and has
to guess what `field_values` should be.

**Why this matters even for canonical schemas**: even when all args
have `name`, the rendered output `args=[name1:type, name2:type]` does
not tell the LLM that `args[0]` is the subject (entity_identity) and
`args[1:]` is `field_values`. The LLM would still have to infer the
split. The fix addresses both problems in one pass.

### 1.2 Defect B (prompt-side): `SYSTEM_PROMPT_TEMPLATE` never teaches the `field_values` contract

[`prompts.py:8-22`](../../src/factpy_kernel/agent/extraction/prompts.py#L8) `SYSTEM_PROMPT_TEMPLATE` lists 6 rules but never:

1. Names what `entity_identity` is supposed to contain
2. States that `arg_specs[0]` is the subject entity (encoded in
   `entity_type` + `entity_identity`, **not** in `field_values`)
3. States `field_values.length == len(arg_specs) - 1`
4. States that each `tag` in `field_values` must equal the corresponding
   arg slot's `type_domain` (this is a hard validator contract:
   [validation.py:195-198](../../src/factpy_kernel/agent/extraction/validation.py#L195))

Without these rules, even if the schema summary rendered perfectly, the
LLM still wouldn't know how to construct `field_values` correctly.
Defect A makes the problem worse; Defect B would still exist with a
canonical schema input.

### 1.3 Evidence from B3 iteration 2

Both run records used the provisional `test_schema_ir.json`:

- 35 LLM proposals produced across 229 segments
- **100%** rejected with `schema_field_type_mismatch: field_values length mismatch`
- Zero `schema_entity_type_unknown` / `schema_pred_id_unknown` rejections,
  which means the Literal constraints from `build_response_model` are
  working — the LLM is picking legal entity_types and pred_ids
- The failure is at the `field_values` structural level, not at the
  semantic content level
- Because the provisional schema was non-canonical, we cannot tell from
  iteration 2 alone whether a canonical schema would have produced the
  same failure shape — but Defect B (the prompt contract gap) means it
  very likely would have, just with slightly more informative LLM guesses

---

## 2. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| PS-01 | **`build_schema_summary` always emits arg info** — if `name` is present, use `name:type_domain`; otherwise use `arg{i}:type_domain` where `i` is the zero-based position in `arg_specs`. No arg is silently dropped | Fixes P-01. Keeps positional information explicit so the LLM can map arg slots to its response |
| PS-02 | **Schema summary marks the subject arg explicitly**: emit `- pred_id subject=<arg0> field_values=[<arg1>, <arg2>, ...]` so the LLM visually sees the split. Unary predicates render as `field_values=[]` (empty). This is the exact rendering used everywhere else in the blueprint | Gives the LLM an unambiguous mental model matching the validator's `rest_specs = arg_specs[1:]` logic |
| PS-03 | **`SYSTEM_PROMPT_TEMPLATE` gains a "Response format" section** with exactly these rules: (a) `entity_type` + `entity_identity` name/values encode the predicate's subject (arg 0); (b) `field_values` has one entry per remaining arg slot in order; (c) each entry's `tag` equals the arg's `type_domain`; (d) `field_values.length` must equal the number of non-subject args | Closes P-02. Gives the LLM the exact contract enforced by `_validate_field_types` |
| PS-04 | **Keep existing 6 rules unchanged**; append new "Response format" as rules 7–10 | Minimal edit; no regression risk for existing working prompts |
| PS-05 | **Dropped.** Do NOT add a fallback for `identity_fields` without `name`. Canonical SchemaIR (`core/schema/schema_ir.py:_validate_entities`) requires `identity_fields[].name` to be a non-empty string and `type_domain` to be in `CANONICAL_TAGS`. Emitting `identity{i}:...` placeholders would teach the LLM to produce identity keys that canonical validation could never accept downstream | Prevents the prompt from normalizing a non-canonical shape into the LLM's vocabulary. If an `identity_fields[]` entry lacks a `name`, that's a malformed schema and the prompt should surface nothing for it (keep the entity line short rather than synthesize fake field names) |
| PS-06 | **P-03 drive-by**: update `_validate_field_types` length-mismatch message to include actual vs expected counts | One-line change; improves diagnosis without touching logic. Strictly additive to the string |
| PS-07 | **Do not change `validate_proposal` logic or the validator contract** | Validator is behaving correctly per its spec. The bug is that the LLM wasn't taught the contract. Changing the validator would paper over the real defect |
| PS-08 | **Do not rename or change any public API** | Prompt strings are implementation details; `build_schema_summary` / `SYSTEM_PROMPT_TEMPLATE` have no external consumers outside `extraction/` |
| PS-09 | **Extend existing `test_agent_l4c3a_prompts.py` rather than create a new file** | That file is the existing home for prompt-shape assertions. New tests here keep discoverability |

### Explicit non-goals

- Not changing validator logic or contract
- Not changing response model (`build_response_model`) — that's a separate archived bugfix
- Not changing `schema_ir` format or what fields it may contain
- Not adding "smart" retry / repair prompts for malformed LLM output
- Not adding positional coercion in `_normalize_field_values` (would paper over bugs)
- Not changing `test_schema_ir.json` — it is explicitly provisional and non-canonical (self-declared "Not a real FactPy SchemaIR"). The bug addressed here is prompt-layer robustness against such non-canonical input plus the pre-existing canonical-affecting contract gap (P-02). Making the provisional schema canonical is a separate concern and out of scope here
- Not adding Langfuse trace inspection for diagnosing prompts (separate concern)
- Not touching prompts for non-extraction flows (there are none today, but stated for clarity)

---

## 3. The Fix

### 3.1 `build_schema_summary` change

Replace the entity and predicate loops with fallback-aware versions. Full
replacement of the function body below.

```python
def build_schema_summary(schema_ir: dict[str, Any], *, max_chars: int = 8000) -> str:
    """Build a deterministic prompt summary from schema IR.

    PS-01 / PS-02: every predicate `arg_spec` contributes a positional
    entry even if it lacks a `name`, and predicate lines mark the subject
    arg (arg0) explicitly so the LLM can map arg slots to entity_identity
    vs field_values.

    PS-05 (NOT applied): `identity_fields[]` that lack a canonical `name`
    are intentionally skipped. Canonical SchemaIR requires `name` on every
    identity field, so synthesizing a placeholder would teach the LLM to
    emit identity keys that downstream canonical validation rejects.
    """

    entities = schema_ir.get("entities", [])
    predicates = schema_ir.get("predicates", [])
    entity_lines: list[str] = ["Entities:"]
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        entity_type = entity.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type:
            continue
        identity_entries: list[str] = []
        for field in entity.get("identity_fields", []):
            if not isinstance(field, dict):
                continue
            name = field.get("name")
            type_domain = field.get("type_domain")
            # PS-05 (not applied): only emit fields with a canonical name.
            # Non-canonical entries are silently skipped — the prompt intentionally
            # does not teach the LLM to produce synthetic identity keys.
            if isinstance(name, str) and name:
                td_str = type_domain if isinstance(type_domain, str) and type_domain else "unknown"
                identity_entries.append(f"{name}:{td_str}")
        entity_lines.append(f"- {entity_type} identity=[{', '.join(identity_entries)}]")

    predicate_lines: list[str] = ["Predicates:"]
    for predicate in predicates:
        if not isinstance(predicate, dict):
            continue
        pred_id = predicate.get("pred_id")
        if not isinstance(pred_id, str) or not pred_id:
            continue
        arg_specs = predicate.get("arg_specs", [])
        if not isinstance(arg_specs, list):
            arg_specs = []

        rendered_args: list[str] = []
        for idx, arg in enumerate(arg_specs):
            if not isinstance(arg, dict):
                continue
            name = arg.get("name")
            type_domain = arg.get("type_domain")
            td_str = type_domain if isinstance(type_domain, str) and type_domain else "unknown"
            if isinstance(name, str) and name:
                rendered_args.append(f"{name}:{td_str}")
            else:
                # PS-01: positional fallback — arg0, arg1, ...
                rendered_args.append(f"arg{idx}:{td_str}")

        # PS-02: mark the subject (arg 0) explicitly.
        # Unary predicates render as `subject=... field_values=[]` (empty list).
        # Zero-arg predicates (degenerate) render the same way with no subject.
        if rendered_args:
            subject = rendered_args[0]
            rest = rendered_args[1:]
            rest_str = ", ".join(rest)  # empty string for unary predicates
            predicate_lines.append(
                f"- {pred_id} subject={subject} field_values=[{rest_str}]"
            )
        else:
            # Degenerate case: predicate with no args at all.
            # Kept for defensiveness; canonical SchemaIR requires at least one arg.
            predicate_lines.append(f"- {pred_id} subject=<missing> field_values=[]")

    summary = "\n".join(entity_lines + [""] + predicate_lines)
    if len(summary) <= max_chars:
        return summary
    suffix = "\n...<schema_summary_truncated>"
    return summary[: max(0, max_chars - len(suffix))] + suffix
```

**Expected output for the B3 test schema**:

```
Entities:
- Document identity=[title:string]
- Module identity=[module_name:string]

Predicates:
- document:mentions subject=arg0:entity_ref field_values=[arg1:string]
- module:description subject=arg0:entity_ref field_values=[arg1:string]
```

vs. the current broken output:

```
Entities:
- Document identity=['title:string']
- Module identity=['module_name:string']

Predicates:
- document:mentions args=[]
- module:description args=[]
```

### 3.2 `SYSTEM_PROMPT_TEMPLATE` change

Replace the existing template with an expanded version that appends the
response-format rules (rules 7–10) below the existing rules. The "Schema"
section and the `{schema_summary}` placeholder stay in the same location.

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
     list of `{name, value}` entries, one per identity field declared on that
     entity type. Use the entity's identity field names exactly as shown in
     the schema summary. Do NOT invent identity field names that are not in
     the schema summary.
   - Put the predicate ID in `pred_id` (must match one of the listed predicates).
   - Put the remaining arg values in `field_values` as a list of `{tag, value}`
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

Schema:
{schema_summary}
"""
```

### 3.3 `_validate_field_types` drive-by (optional but recommended, PS-06)

One line in `validation.py` around line 193–194:

```python
# Before:
if len(field_values) != len(rest_specs):
    return f"field_values length mismatch for pred_id '{pred_id}'"

# After:
if len(field_values) != len(rest_specs):
    return (
        f"field_values length mismatch for pred_id '{pred_id}': "
        f"got {len(field_values)}, expected {len(rest_specs)}"
    )
```

No other logic change. Strictly additive to the error string.

### 3.4 Test extensions

Extend `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py` with these
assertions (add a new `SchemaSummaryFallbackTest` class):

```python
class SchemaSummaryFallbackTest(unittest.TestCase):
    """PS-01 / PS-02: predicate arg_specs without a `name` get a positional
    fallback (arg{i}:type_domain). Entity identity_fields without a `name`
    are NOT given a fallback — they are intentionally skipped to avoid
    teaching the LLM non-canonical identity keys (PS-05 dropped).
    """

    _SCHEMA_NO_NAMES: dict = {
        "entities": [
            {
                "entity_type": "Document",
                "identity_fields": [{"name": "title", "type_domain": "string"}],
            }
        ],
        "predicates": [
            {
                "pred_id": "document:mentions",
                "arg_specs": [
                    {"type_domain": "entity_ref"},
                    {"type_domain": "string"},
                ],
            }
        ],
    }

    def test_predicate_args_not_silently_dropped(self) -> None:
        from factpy_kernel.agent.extraction.prompts import build_schema_summary
        summary = build_schema_summary(self._SCHEMA_NO_NAMES)
        # Must contain both arg slots, not args=[]
        self.assertIn("document:mentions", summary)
        self.assertIn("entity_ref", summary)
        self.assertIn("arg1:string", summary)
        self.assertNotIn("args=[]", summary)

    def test_subject_is_marked_explicitly(self) -> None:
        from factpy_kernel.agent.extraction.prompts import build_schema_summary
        summary = build_schema_summary(self._SCHEMA_NO_NAMES)
        # Format: subject=arg0:entity_ref field_values=[arg1:string]
        self.assertIn("subject=arg0:entity_ref", summary)
        self.assertIn("field_values=[arg1:string]", summary)

    def test_identity_fields_without_names_are_skipped(self) -> None:
        """PS-05 NOT applied: malformed identity_fields (no canonical name)
        are intentionally omitted. Canonical SchemaIR requires name to be
        a non-empty string, so synthesizing placeholders would teach the
        LLM to emit identity keys the validator rejects.
        """
        from factpy_kernel.agent.extraction.prompts import build_schema_summary
        schema = {
            "entities": [
                {
                    "entity_type": "Foo",
                    "identity_fields": [{"type_domain": "string"}],  # no name
                }
            ],
            "predicates": [
                {
                    "pred_id": "foo:bar",
                    "arg_specs": [{"type_domain": "entity_ref"}],
                }
            ],
        }
        summary = build_schema_summary(schema)
        # The entity line should exist but have no identity entries
        self.assertIn("- Foo identity=[]", summary)
        # The LLM should NOT see synthesized placeholders
        self.assertNotIn("identity0", summary)

    def test_empty_field_values_for_unary_predicate(self) -> None:
        """A predicate with only a subject arg should show field_values=[]."""
        from factpy_kernel.agent.extraction.prompts import build_schema_summary
        schema = {
            "entities": [
                {
                    "entity_type": "Foo",
                    "identity_fields": [{"name": "id", "type_domain": "string"}],
                }
            ],
            "predicates": [
                {
                    "pred_id": "foo:exists",
                    "arg_specs": [{"type_domain": "entity_ref"}],
                }
            ],
        }
        summary = build_schema_summary(schema)
        self.assertIn("foo:exists subject=arg0:entity_ref field_values=[]", summary)


class SystemPromptResponseFormatTest(unittest.TestCase):
    """PS-03 / PS-04: SYSTEM_PROMPT_TEMPLATE must include the response-format
    contract rules so the LLM can construct field_values correctly.
    """

    def test_prompt_mentions_field_values_length_contract(self) -> None:
        from factpy_kernel.agent.extraction.prompts import SYSTEM_PROMPT_TEMPLATE
        lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # Core rule: length must match schema summary
        self.assertIn("field_values", lower)
        self.assertIn("length", lower)
        # The existing rules still present
        self.assertIn("only propose facts", lower)
        # New rule: tag == type_domain
        self.assertIn("type_domain", lower)

    def test_prompt_mentions_subject_not_in_field_values(self) -> None:
        from factpy_kernel.agent.extraction.prompts import SYSTEM_PROMPT_TEMPLATE
        lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # The LLM must be told subject belongs in entity_identity, not field_values
        self.assertIn("entity_identity", lower)
        self.assertIn("subject", lower)

    def test_prompt_keeps_original_six_rules(self) -> None:
        """PS-04: existing rules 1-6 remain unchanged."""
        from factpy_kernel.agent.extraction.prompts import SYSTEM_PROMPT_TEMPLATE
        self.assertIn("1. Only propose facts", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("2. Do not invent", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("3. Only extract facts directly", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("4. If no valid facts can be extracted", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("5. Do not generate provenance", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("6. Assign a confidence score", SYSTEM_PROMPT_TEMPLATE)
```

---

## 4. Impact Analysis

### Files touched (max 3)

1. `src/factpy_kernel/agent/extraction/prompts.py` — `build_schema_summary` + `SYSTEM_PROMPT_TEMPLATE`
2. `src/factpy_kernel/agent/extraction/validation.py` — single-line message update (PS-06, optional)
3. `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py` — append two test classes (~7 new tests)

### Backward compatibility

- **`build_schema_summary` signature unchanged**: same args, same return
  type (`str`), same `max_chars` semantics
- **`SYSTEM_PROMPT_TEMPLATE` is a module-level string**: any test that
  currently asserts on the first 6 rules will still find them (PS-04).
  Tests that assert specific substrings should be reviewed.
- **No response model change**: `LLMFactProposal` / `SegmentExtractionResponse`
  shape is unchanged.
- **No validator logic change**: `_validate_field_types` still enforces the
  same contract; the only change is the error detail string.

### Regression surface

Existing `test_agent_l4c3a_prompts.py` tests may assert on the exact
output of `build_schema_summary`. Expected format changes:

| Before | After |
|---|---|
| `- Document identity=['title:string']` | `- Document identity=[title:string]` (no quotes from list repr) |
| `- document:mentions args=['title:string']` or `- document:mentions args=[]` | `- document:mentions subject=arg0:entity_ref field_values=[arg1:string]` |

If the existing test asserts exact substrings like `identity=['` or
`args=[`, those assertions will break and must be updated. This is
expected and acceptable — the new format is strictly more informative
and the new test classes lock it in.

### New failure modes introduced

None at runtime. The prompt changes make the LLM more likely to succeed,
not less. If for some reason a particular LLM model now misinterprets
the expanded rules and fails, we'd see a different rejection pattern
in B3 iteration 3 — which is the informative signal we want.

---

## 5. Implementation Order

```
Step 1: Apply prompts.py patch
        → build_schema_summary rewrite
        → SYSTEM_PROMPT_TEMPLATE expansion

Step 2: Apply validation.py drive-by (PS-06)
        → _validate_field_types error message enriched

Step 3: Extend test_agent_l4c3a_prompts.py
        → SchemaSummaryFallbackTest (4 tests)
        → SystemPromptResponseFormatTest (3 tests)

Step 4: Run prompt-targeted tests first:
        → python -m unittest src.factpy_kernel.tests.test_agent_l4c3a_prompts
        → expected: 7 new + existing unchanged, all pass
        → fix any existing prompt tests that asserted on the old format

Step 5: Run 4C3-a-specific regression:
        → python -m unittest src.factpy_kernel.tests.test_agent_l4c3a_models \
                             src.factpy_kernel.tests.test_agent_l4c3a_validation \
                             src.factpy_kernel.tests.test_agent_l4c3a_prompts \
                             src.factpy_kernel.tests.test_agent_l4c3a_extractor \
                             src.factpy_kernel.tests.test_agent_l4c3a_workflow \
                             src.factpy_kernel.tests.test_agent_l4c3a_response_model_schema

Step 6: Run full regression:
        → python -m unittest discover -s src/factpy_kernel/tests
        → expected: 959 prior + 7 new = 966 (2 baseline skips)

Step 7: Tighten samples_manifest.yaml for iteration 3:
        → expected_result: "success" on both medium_01_security and long_01_kernel_p0
        → expected_min_valid_specs: 1

Step 8: Rerun B3 iteration 3:
        → PYTHONPATH=src /Users/zhenzhili/miniforge3/bin/python \
            docs/references/working/load-test-2026-04-11/run_load_test.py \
            --manifest docs/references/working/load-test-2026-04-11/samples_manifest.yaml \
            --sample medium_01_security
        → expected: valid_count > 0 OR new, different rejection reason
        → if medium passes, run long_01_kernel_p0
        → if still all-rejected, inspect new rejection_samples for next diagnostic
```

---

## 6. Acceptance Criteria

### prompts.py
- [ ] `build_schema_summary` emits predicate arg info even when `arg_specs[i]` has no `name`
- [ ] Arg entries use `name:type_domain` if name present, `arg{i}:type_domain` otherwise (**predicates only**)
- [ ] **`identity_fields` without `name` are silently skipped** (PS-05 dropped — no synthetic placeholder)
- [ ] Predicate lines mark the subject explicitly: `subject=... field_values=[...]`
- [ ] A predicate with only arg0 (unary) emits `field_values=[]` (empty list, no placeholder)
- [ ] `SYSTEM_PROMPT_TEMPLATE` retains rules 1–6 verbatim
- [ ] `SYSTEM_PROMPT_TEMPLATE` adds rules 7–10 covering response format contract
- [ ] `SYSTEM_PROMPT_TEMPLATE` mentions: `field_values` length, `tag == type_domain`, `entity_identity` vs `field_values` subject separation

### validation.py
- [ ] `_validate_field_types` length-mismatch message includes actual and expected counts
- [ ] No other logic change in `validate_proposal` / `_validate_field_types` / `_validate_entity_identity`

### tests
- [ ] `SchemaSummaryFallbackTest` — 4 tests pass
- [ ] `SystemPromptResponseFormatTest` — 3 tests pass
- [ ] Any existing prompt test asserting old format is updated to match new output
- [ ] Full regression: 966 tests, 2 baseline skips

### B3 iteration 3
- [ ] `samples_manifest.yaml` tightened: `expected_result: success`, `expected_min_valid_specs >= 1`
- [ ] `medium_01_security` rerun produces either:
  - **Success case**: `total_valid_count > 0` and `matches_expectation=true`, or
  - **Informative failure**: a different `rejection_reason` than `schema_field_type_mismatch` (e.g. `schema_pred_id_unknown`, `scope_entity_type_denied`, or a legitimate semantic rejection from the LLM hallucinating)
- [ ] `long_01_kernel_p0` rerun same criteria

---

## 7. Known Constraints

1. **LLM behavior is non-deterministic across model versions**: even with `temperature=0.0`, OpenAI model updates can shift proposal counts between runs. The fix targets the structural contract, not proposal content.
2. **The fix does not guarantee the LLM will find meaningful facts in narrative-heavy documents**: README.md and security docs are mostly narrative. Even with perfect structural compliance, iteration 3 may produce few valid specs simply because there isn't much to extract. That is expected and not a bug.
3. **Does not address schema coverage**: if the LLM cannot express a fact using the 2 entity types + 2 predicates in `test_schema_ir.json`, it will correctly return empty proposals. Schema expansion is a separate future concern.
4. **Does not retroactively fix historical run records**: iteration 1 and 2 records stay as-is; iteration 3 gets its own timestamp.
5. **Does not add a real LLM integration test for prompt correctness**: B3 iteration 3 serves that role. The unit tests in this blueprint only verify the prompt's static structure, not LLM compliance with it.
6. **No provider-specific prompt tuning**: the new rules are written in plain English and should work with any instruction-tuned model. If Anthropic / Gemini need different wording, that's a separate concern.

---

## 8. Outcome / Deviations

### Outcome

- Implemented in:
  - `src/factpy_kernel/agent/extraction/prompts.py`
  - `src/factpy_kernel/agent/extraction/validation.py`
  - `src/factpy_kernel/tests/test_agent_l4c3a_prompts.py`
  - `src/factpy_kernel/agent/extraction/docs/README.md`
- Prompt-targeted regression passed.
- 4C3-a regression passed.
- Full regression passed: **967 tests**, **2 skipped**.
- B3 iteration 3 reruns succeeded on both smoke samples:
  - `medium_01_security`: `11 proposals / 4 valid / 7 rejected`, bundle preview created
  - `long_01_kernel_p0`: `101 proposals / 60 valid / 41 rejected`, bundle preview created
- This blueprint closes the iteration-2 diagnosis loop:
  - iteration 2 blocker (`100% field_values length mismatch`) is no longer total
  - extraction now produces valid `FactDraftSpec` output on the real OpenAI path

### Deviations

- No validator logic was changed beyond the scoped PS-06 drive-by: the length-mismatch message now includes `got N, expected M`.
- B3 iteration 3 still shows residual `schema_field_type_mismatch` rejections (`got 2, expected 1`) for part of the proposal set. That is not a deviation from scope; it is the next diagnostic signal after restoring partial success.
- The blueprint's pre-fix regression expectation (`966 tests`) was exceeded because the current suite baseline at implementation time was higher; the actual post-fix result is **967 tests / 2 skipped**.
