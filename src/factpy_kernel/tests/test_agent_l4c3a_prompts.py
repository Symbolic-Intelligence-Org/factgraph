"""Layer 4C3-a prompt construction tests."""

from __future__ import annotations

import unittest

from factpy_kernel.agent.documents import DocumentSegment
from factpy_kernel.agent.extraction.prompts import (
    SYSTEM_PROMPT_TEMPLATE,
    build_messages,
    build_schema_summary,
    format_entity_context_header,
    format_gleaning_context,
    truncate_prompt_text,
)
from factpy_kernel.tests._test_helpers import _schema_ir


class AgentLayer4C3aPromptTests(unittest.TestCase):
    def test_build_schema_summary_contains_entities_and_predicates(self) -> None:
        summary = build_schema_summary(_schema_ir())
        self.assertIn("Entities:", summary)
        self.assertIn("User", summary)
        self.assertIn("user:tag", summary)

    def test_build_schema_summary_truncates_deterministically(self) -> None:
        summary = build_schema_summary(_schema_ir(), max_chars=60)
        self.assertLessEqual(len(summary), 60)
        self.assertIn("<schema_summary_truncated>", summary)

    def test_build_messages_uses_doc_id_and_prompt_text(self) -> None:
        segment = DocumentSegment(
            segment_id="seg_1",
            doc_id="doc_1",
            segment_index=0,
            section_label="Section 1",
            page_number=1,
            char_offset_start=0,
            char_offset_end=10,
            raw_text="Alice is VIP",
            structural_clarity=0.8,
            pattern_type="entity_relation",
            parser_version="txt_v1",
        )
        messages = build_messages(
            segment=segment,
            schema_summary="Entities:\n- User",
            raw_text_for_llm=truncate_prompt_text(segment.raw_text, max_text_chars=5),
        )
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("doc_1", messages[1]["content"])
        self.assertIn("Alice", messages[1]["content"])
        self.assertNotIn("VIP", messages[1]["content"])


class SchemaSummaryFallbackTest(unittest.TestCase):
    """PS-01 / PS-02: predicate arg_specs without a ``name`` get a positional
    fallback (``arg{i}:type_domain``). Entity ``identity_fields`` without a
    ``name`` are NOT given a fallback — they are intentionally skipped to
    avoid teaching the LLM non-canonical identity keys (PS-05 dropped).

    Canonical SchemaIR would reject such inputs upstream, but
    ``build_schema_summary`` does not require canonical validation, so it
    must be robust against provisional / B3-smoke schemas that omit ``name``.
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
        summary = build_schema_summary(self._SCHEMA_NO_NAMES)
        # Must contain both arg slots, not args=[]
        self.assertIn("document:mentions", summary)
        self.assertIn("entity_ref", summary)
        self.assertIn("arg1:string", summary)
        self.assertNotIn("args=[]", summary)

    def test_subject_is_marked_explicitly(self) -> None:
        summary = build_schema_summary(self._SCHEMA_NO_NAMES)
        # Format: subject=arg0:entity_ref field_values=[arg1:string]
        self.assertIn("subject=arg0:entity_ref", summary)
        self.assertIn("field_values=[arg1:string]", summary)

    def test_identity_fields_without_names_are_skipped(self) -> None:
        """PS-05 NOT applied: malformed identity_fields (no canonical name)
        are intentionally omitted. Canonical SchemaIR requires ``name`` to
        be a non-empty string, so synthesizing placeholders would teach the
        LLM to emit identity keys the validator rejects.
        """
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
        """A predicate with only a subject arg should show ``field_values=[]``."""
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

    def test_named_args_preserve_explicit_names(self) -> None:
        """When arg_specs have ``name``, use the canonical name, not the positional fallback."""
        schema = {
            "entities": [
                {
                    "entity_type": "Doc",
                    "identity_fields": [{"name": "id", "type_domain": "string"}],
                }
            ],
            "predicates": [
                {
                    "pred_id": "doc:title",
                    "arg_specs": [
                        {"name": "subject", "type_domain": "entity_ref"},
                        {"name": "title", "type_domain": "string"},
                    ],
                }
            ],
        }
        summary = build_schema_summary(schema)
        # Canonical name wins over positional fallback
        self.assertIn("subject=subject:entity_ref", summary)
        self.assertIn("field_values=[title:string]", summary)
        self.assertNotIn("arg0:", summary)
        self.assertNotIn("arg1:", summary)


class SystemPromptResponseFormatTest(unittest.TestCase):
    """PS-03 / PS-04: SYSTEM_PROMPT_TEMPLATE must include the response-format
    contract rules so the LLM can construct ``field_values`` correctly, and
    must preserve the existing rules 1–6 verbatim.
    """

    def test_prompt_mentions_field_values_length_contract(self) -> None:
        lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # Core rule: length must match schema summary
        self.assertIn("field_values", lower)
        self.assertIn("length", lower)
        # Existing content still present
        self.assertIn("only propose facts", lower)
        # New rule: tag == type_domain
        self.assertIn("type_domain", lower)

    def test_prompt_mentions_subject_not_in_field_values(self) -> None:
        lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # The LLM must be told subject belongs in entity_identity, not field_values
        self.assertIn("entity_identity", lower)
        self.assertIn("subject", lower)

    def test_prompt_keeps_original_six_rules(self) -> None:
        """PS-04: existing rules 1–6 remain unchanged."""
        self.assertIn("1. Only propose facts", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("2. Do not invent", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("3. Only extract facts directly", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("4. If no valid facts can be extracted", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("5. Do not generate provenance", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("6. Assign a confidence score", SYSTEM_PROMPT_TEMPLATE)


class SystemPromptExamplesTest(unittest.TestCase):
    """PR-01..PR-06: SYSTEM_PROMPT_TEMPLATE has an Examples section
    with two wrong/right pairs targeting the two residual patterns
    surfaced by B3 iteration 3:

    - Pattern A (subject leakage): LLM duplicates the subject entity_ref
      into ``field_values`` in addition to ``entity_identity``. Observed
      as ``got 2, expected 1`` on long_01_kernel_p0 (41/41 rejections).
    - Pattern B (multi-entry overpacking): LLM splits a single string
      slot into multiple ``{tag, value}`` entries when the source text
      enumerates several items. Observed as ``got 3/4, expected 1`` on
      medium_01_security (7/7 rejections).
    """

    def test_prompt_has_examples_section(self) -> None:
        lower = SYSTEM_PROMPT_TEMPLATE.lower()
        self.assertIn("examples", lower)
        examples_idx = lower.find("examples")
        schema_idx = lower.find("schema:")
        self.assertGreater(
            schema_idx,
            examples_idx,
            "Examples section must appear before the Schema placeholder",
        )

    def test_prompt_has_subject_leakage_example(self) -> None:
        self.assertIn("Example 1", SYSTEM_PROMPT_TEMPLATE)
        wrong_block_start = SYSTEM_PROMPT_TEMPLATE.find("Example 1")
        right_block_start = SYSTEM_PROMPT_TEMPLATE.find("RIGHT:", wrong_block_start)
        self.assertGreater(right_block_start, wrong_block_start)
        wrong_block = SYSTEM_PROMPT_TEMPLATE[wrong_block_start:right_block_start]
        self.assertIn("WRONG:", wrong_block)
        self.assertIn("entity_ref", wrong_block)
        right_end = SYSTEM_PROMPT_TEMPLATE.find("Example 2", right_block_start)
        right_block = SYSTEM_PROMPT_TEMPLATE[right_block_start:right_end]
        self.assertIn("field_values", right_block)
        self.assertIn("length 1", right_block)

    def test_prompt_has_multi_entry_overpacking_example(self) -> None:
        self.assertIn("Example 2", SYSTEM_PROMPT_TEMPLATE)
        example2_start = SYSTEM_PROMPT_TEMPLATE.find("Example 2")
        schema_start = SYSTEM_PROMPT_TEMPLATE.find("Schema:", example2_start)
        self.assertGreater(schema_start, example2_start)
        example2_block = SYSTEM_PROMPT_TEMPLATE[example2_start:schema_start]
        self.assertIn("WRONG", example2_block)
        self.assertIn("RIGHT", example2_block)
        self.assertIn("proposal A", example2_block)
        self.assertIn("proposal B", example2_block)
        self.assertIn("proposal C", example2_block)

    def test_prompt_examples_do_not_leak_b3_schema_names(self) -> None:
        """PR-03: examples must use a generic ``doc:has_topic`` predicate,
        NOT the B3 provisional ``document:mentions`` or
        ``module:description``. Locking this in prevents accidental
        overfit to one specific schema and makes any example-predicate
        leakage self-detecting in iter 4 (would surface as
        ``schema_pred_id_unknown``).
        """

        examples_start = SYSTEM_PROMPT_TEMPLATE.find("Examples")
        schema_start = SYSTEM_PROMPT_TEMPLATE.find("Schema:", examples_start)
        examples_block = SYSTEM_PROMPT_TEMPLATE[examples_start:schema_start]
        self.assertNotIn("document:mentions", examples_block)
        self.assertNotIn("module:description", examples_block)
        self.assertIn("doc:has_topic", examples_block)

    def test_prompt_keeps_rules_seven_through_ten_unchanged(self) -> None:
        """PR-07: rules 7-10 are preserved verbatim from iteration 3's
        PS-01..PS-06 fix. The Examples section is additive.
        """

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

    Strict approval rate 11.6% -> target >=40%. Salvageable rate 100%
    guardrail (must not drop).
    """

    def test_prompt_has_semantic_examples_section(self) -> None:
        """SG-02: new section exists and is positioned after iter 4
        Examples and before the Schema: placeholder.
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
        with the verbatim-identifier positive rule and a per-type
        abstention fallback.
        """
        self.assertIn("Example 3", SYSTEM_PROMPT_TEMPLATE)
        example3_start = SYSTEM_PROMPT_TEMPLATE.find("Example 3")
        example4_start = SYSTEM_PROMPT_TEMPLATE.find("Example 4")
        self.assertGreater(example4_start, example3_start)
        block = SYSTEM_PROMPT_TEMPLATE[example3_start:example4_start]

        self.assertIn("verbatim", block.lower())
        self.assertIn("WRONG", block)
        self.assertIn("Emit NO", block)
        self.assertIn("Per-type abstention", block)
        self.assertIn("other entity types", block)
        self.assertIn("Rule 4", block)
        self.assertIn("RIGHT:", block)

    def test_prompt_has_module_description_example(self) -> None:
        """SG-03 / SG-06 / SG-07: Example 4 covers module:description
        narrowing with the declarative positive rule and a per-type
        abstention fallback.
        """
        self.assertIn("Example 4", SYSTEM_PROMPT_TEMPLATE)
        example4_start = SYSTEM_PROMPT_TEMPLATE.find("Example 4")
        schema_start = SYSTEM_PROMPT_TEMPLATE.find("Schema:", example4_start)
        self.assertGreater(schema_start, example4_start)
        block = SYSTEM_PROMPT_TEMPLATE[example4_start:schema_start]

        self.assertIn("declarative", block.lower())
        self.assertIn("WRONG", block)
        self.assertIn("Emit NO", block)
        self.assertIn("Per-type abstention", block)
        self.assertIn("other entity types", block)
        self.assertIn("Rule 4", block)
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

        self.assertIn("Example 1 — subject leakage", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("length 2 — WRONG", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("Example 2 — multi-entry overpacking", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("proposal A:", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("proposal B:", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("proposal C:", SYSTEM_PROMPT_TEMPLATE)


class EntityContextHeaderTests(unittest.TestCase):
    """Tests for format_entity_context_header and build_messages context injection."""

    def test_empty_entries_returns_empty_string(self) -> None:
        self.assertEqual(format_entity_context_header([]), "")

    def test_single_entity_with_facts(self) -> None:
        result = format_entity_context_header([
            {
                "entity_type": "Module",
                "identity": {"name": "ingest"},
                "facts": ['module:owner="data-infra team"', 'module:description="handles ingestion"'],
            }
        ])
        self.assertIn("Previously identified entities", result)
        self.assertIn('Module (name="ingest")', result)
        self.assertIn('module:owner="data-infra team"', result)
        self.assertIn('module:description="handles ingestion"', result)

    def test_multiple_entities(self) -> None:
        result = format_entity_context_header([
            {"entity_type": "Module", "identity": {"name": "ingest"}, "facts": ['module:owner="team-a"']},
            {"entity_type": "Module", "identity": {"name": "resolve"}, "facts": ['module:owner="Alice"']},
        ])
        self.assertIn('Module (name="ingest")', result)
        self.assertIn('Module (name="resolve")', result)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 3)

    def test_entity_without_facts(self) -> None:
        result = format_entity_context_header([
            {"entity_type": "Document", "identity": {"title": "README"}, "facts": []},
        ])
        self.assertIn('Document (title="README")', result)
        self.assertNotIn(":", result.split("\n")[-1])

    def test_truncation_at_max_context_chars(self) -> None:
        entries = [
            {"entity_type": f"Entity{i}", "identity": {"id": f"e{i}"}, "facts": [f'pred:f="value-{i}"']}
            for i in range(100)
        ]
        result = format_entity_context_header(entries, max_context_chars=200)
        self.assertLessEqual(len(result), 200 + len("\n... (context truncated)"))
        self.assertIn("... (context truncated)", result)

    def test_build_messages_with_prior_entity_context(self) -> None:
        segment = DocumentSegment(
            segment_id="seg_0",
            doc_id="doc_1",
            segment_index=0,
            section_label=None,
            page_number=None,
            char_offset_start=0,
            char_offset_end=10,
            raw_text="Hello world",
            structural_clarity=0.5,
            pattern_type="narrative",
            parser_version="txt_v1",
        )
        context = 'Previously identified entities:\n- Module (name="auth")'
        messages = build_messages(
            segment=segment,
            schema_summary="Entities:\n- User identity=[user_id:string]",
            raw_text_for_llm="Hello world",
            prior_entity_context=context,
        )
        user_content = messages[1]["content"]
        self.assertIn("Previously identified entities", user_content)
        self.assertIn('Module (name="auth")', user_content)
        clarity_pos = user_content.index("Structural clarity:")
        text_pos = user_content.index("Text:")
        context_pos = user_content.index("Previously identified")
        self.assertGreater(context_pos, clarity_pos)
        self.assertLess(context_pos, text_pos)

    def test_build_messages_without_context_backward_compatible(self) -> None:
        segment = DocumentSegment(
            segment_id="seg_0",
            doc_id="doc_1",
            segment_index=0,
            section_label=None,
            page_number=None,
            char_offset_start=0,
            char_offset_end=10,
            raw_text="Hello world",
            structural_clarity=0.5,
            pattern_type="narrative",
            parser_version="txt_v1",
        )
        messages = build_messages(
            segment=segment,
            schema_summary="Entities:\n- User identity=[user_id:string]",
            raw_text_for_llm="Hello world",
        )
        user_content = messages[1]["content"]
        self.assertIn("Document: doc_1", user_content)
        self.assertIn("Text:", user_content)
        self.assertIn("Hello world", user_content)
        self.assertNotIn("Previously identified", user_content)


class GleaningContextTests(unittest.TestCase):
    """Tests for format_gleaning_context."""

    def test_empty_entries_returns_empty(self) -> None:
        self.assertEqual(format_gleaning_context([], 0), "")

    def test_produces_gleaning_prefix_with_entity_header(self) -> None:
        result = format_gleaning_context(
            [
                {
                    "entity_type": "Module",
                    "identity": {"name": "ingest"},
                    "facts": ['module:owner="team-a"'],
                }
            ],
            pass1_yield=0,
        )
        self.assertIn("GLEANING PASS", result)
        self.assertIn("yielded 0 fact(s)", result)
        self.assertIn("ADDITIONAL facts", result)
        self.assertIn('Module (name="ingest")', result)
        self.assertIn('module:owner="team-a"', result)

    def test_nonzero_yield_reflected_in_prefix(self) -> None:
        result = format_gleaning_context(
            [{"entity_type": "User", "identity": {"id": "u1"}, "facts": []}],
            pass1_yield=2,
        )
        self.assertIn("yielded 2 fact(s)", result)


class SourceDocNameTests(unittest.TestCase):
    """Tests for source_doc_name passthrough in build_messages."""

    def _make_segment(self) -> DocumentSegment:
        return DocumentSegment(
            segment_id="seg_0",
            doc_id="abc123hash",
            segment_index=0,
            section_label=None,
            page_number=None,
            char_offset_start=0,
            char_offset_end=10,
            raw_text="Hello world",
            structural_clarity=0.5,
            pattern_type="narrative",
            parser_version="txt_v1",
        )

    def test_source_doc_name_overrides_doc_id(self) -> None:
        messages = build_messages(
            segment=self._make_segment(),
            schema_summary="Entities:\n- User identity=[user_id:string]",
            raw_text_for_llm="Hello world",
            source_doc_name="readme.md",
        )
        user_content = messages[1]["content"]
        self.assertIn("Document: readme.md", user_content)
        self.assertNotIn("abc123hash", user_content)

    def test_no_source_doc_name_falls_back_to_doc_id(self) -> None:
        messages = build_messages(
            segment=self._make_segment(),
            schema_summary="Entities:\n- User identity=[user_id:string]",
            raw_text_for_llm="Hello world",
        )
        user_content = messages[1]["content"]
        self.assertIn("Document: abc123hash", user_content)


class ModuleIdentityGroundingTests(unittest.TestCase):
    """Tests for I1 (Example 5) and I2 (entity_descriptions in schema summary)."""

    def test_system_prompt_contains_module_name_grounding_example(self) -> None:
        self.assertIn("Example 5", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("Module name grounding", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("data-infra team", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("WRONG (team name as module identity)", SYSTEM_PROMPT_TEMPLATE)
        self.assertIn("AuthService", SYSTEM_PROMPT_TEMPLATE)

    def test_build_schema_summary_with_entity_descriptions(self) -> None:
        summary = build_schema_summary(
            _schema_ir(),
            entity_descriptions={"User": "A registered user account."},
        )
        self.assertIn("User identity=", summary)
        self.assertIn("(A registered user account.)", summary)

    def test_build_schema_summary_without_descriptions_backward_compatible(self) -> None:
        summary_without = build_schema_summary(_schema_ir())
        summary_none = build_schema_summary(_schema_ir(), entity_descriptions=None)
        self.assertEqual(summary_without, summary_none)
        self.assertNotIn("(", summary_without.split("Predicates:")[0])


if __name__ == "__main__":
    unittest.main()
