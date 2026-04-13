"""Offline guard for OpenAI strict function-calling compatibility.

This test inspects the schema that would actually be sent to OpenAI's API
(via openai.pydantic_function_tool), not the raw Pydantic JSON schema.

It guards against structural features OpenAI strict mode rejects:
  - prefixItems (JSON Schema 2020-12; not in OpenAI's subset)
  - Empty / untyped items schemas ({})
  - Objects with additionalProperties != false

If this test breaks, it means someone added a field to the response model
that will fail with 'BadRequestError: Invalid schema' in production.

The OpenAIStrictSchemaGuardTest class is SKIPPED if the openai package is
not installed (Layer 4C3-a optional dependency). When skipped, the
_normalize_* unit tests still run unconditionally.

Blueprint reference: docs/blueprints/archive/2026-04-11_kernel-extraction-
response-model-openai-strict-fix.md
"""

from __future__ import annotations

import unittest
from typing import Any

from factpy_kernel.agent.extraction.llm import build_response_model


try:
    import openai  # type: ignore # noqa: F401

    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False


_MINIMAL_SCHEMA_IR: dict[str, Any] = {
    "entities": [
        {
            "entity_type": "Document",
            "identity_fields": [{"name": "title", "type_domain": "string"}],
            "arg_specs": [
                {"field_name": "title", "type_domain": "string", "cardinality": "single"}
            ],
        }
    ],
    "predicates": [
        {
            "pred_id": "document:mentions",
            "relationship_type": "true",
            "arg_specs": [
                {"type_domain": "entity_ref"},
                {"type_domain": "string"},
            ],
        }
    ],
}


def _walk_schema(node: Any, path: str = "$"):
    """Yield (path, node_dict) for every dict encountered in the JSON schema."""
    if isinstance(node, dict):
        yield path, node
        for key, child in node.items():
            yield from _walk_schema(child, f"{path}.{key}")
    elif isinstance(node, list):
        for idx, child in enumerate(node):
            yield from _walk_schema(child, f"{path}[{idx}]")


def _resolve_ref(schema: dict[str, Any], ref: str) -> dict[str, Any] | None:
    """Resolve a local $ref like '#/$defs/FooBar' against the schema root."""
    if not ref.startswith("#/"):
        return None
    parts = ref[2:].split("/")
    node: Any = schema
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node if isinstance(node, dict) else None


@unittest.skipUnless(_HAS_OPENAI, "openai package not installed; strict-schema guard skipped")
class OpenAIStrictSchemaGuardTest(unittest.TestCase):
    """Guards against JSON schema features OpenAI strict mode rejects.

    BF-04: Inspects the exact strict-mode schema sent to the API,
    obtained via openai.pydantic_function_tool(). This is the same
    transformation path used by openai-python's structured outputs
    and by Instructor when operating in tools mode.
    """

    def setUp(self) -> None:
        import openai  # type: ignore

        self.model_cls = build_response_model(_MINIMAL_SCHEMA_IR)
        # Build the strict function tool schema — same as the real request path
        tool = openai.pydantic_function_tool(self.model_cls)
        self.schema = tool["function"]["parameters"]

    def test_no_prefixItems_anywhere(self) -> None:
        """prefixItems is a 2020-12 feature; OpenAI strict rejects it."""
        for path, node in _walk_schema(self.schema):
            self.assertNotIn(
                "prefixItems",
                node,
                f"prefixItems found at {path} — OpenAI strict rejects this",
            )

    def test_no_empty_or_untyped_items_schemas(self) -> None:
        """items schema must be explicitly typed (no {} / no bare Any)."""
        for path, node in _walk_schema(self.schema):
            if "items" not in node:
                continue
            items = node["items"]
            if not isinstance(items, dict):
                continue
            self.assertTrue(
                items,
                f"items at {path} is empty dict — OpenAI strict rejects this",
            )
            has_type = "type" in items
            has_ref = "$ref" in items
            has_combinator = any(k in items for k in ("anyOf", "oneOf", "allOf"))
            self.assertTrue(
                has_type or has_ref or has_combinator,
                f"items at {path} must have type/$ref/combinator; got {sorted(items.keys())}",
            )

    def test_all_objects_have_additional_properties_false(self) -> None:
        """BF-09: every object schema must declare additionalProperties: false.

        This is the canonical guard against dict[str, Any] leaks:
        OpenAI strict mode rejects objects where additionalProperties is
        either absent (defaults to true) or explicitly true.
        """
        for path, node in _walk_schema(self.schema):
            if node.get("type") != "object":
                continue
            self.assertIn(
                "additionalProperties",
                node,
                (
                    f"object at {path} is missing additionalProperties "
                    f"— OpenAI strict requires explicit additionalProperties: false"
                ),
            )
            self.assertIs(
                node["additionalProperties"],
                False,
                (
                    f"object at {path} has additionalProperties="
                    f"{node['additionalProperties']!r}; must be False"
                ),
            )

    def test_entity_identity_is_list_of_typed_objects(self) -> None:
        """BF-07: entity_identity is list[_LLMIdentityEntry], not dict[str, Any]."""
        proposal = self._find_proposal_defn()
        ei = proposal.get("properties", {}).get("entity_identity")
        self.assertIsNotNone(ei, "entity_identity not found in LLMFactProposal properties")
        assert ei is not None
        self.assertEqual(ei.get("type"), "array", f"entity_identity should be array; got {ei}")
        items = ei.get("items")
        self.assertIsInstance(items, dict, "entity_identity.items must be a dict")
        resolved = self._resolve_or_self(items)
        self.assertEqual(resolved.get("type"), "object")
        props = resolved.get("properties", {})
        self.assertIn("name", props)
        self.assertIn("value", props)
        self.assertEqual(props["name"].get("type"), "string")

    def test_field_values_is_list_of_typed_objects(self) -> None:
        """BF-01: field_values is list[_LLMFieldValue], not list[tuple[str, Any]]."""
        proposal = self._find_proposal_defn()
        fv = proposal.get("properties", {}).get("field_values")
        self.assertIsNotNone(fv, "field_values not found in LLMFactProposal properties")
        assert fv is not None
        self.assertEqual(fv.get("type"), "array", f"field_values should be array; got {fv}")
        items = fv.get("items")
        self.assertIsInstance(items, dict, "field_values.items must be a dict")
        resolved = self._resolve_or_self(items)
        self.assertEqual(resolved.get("type"), "object")
        props = resolved.get("properties", {})
        self.assertIn("tag", props)
        self.assertIn("value", props)
        self.assertEqual(props["tag"].get("type"), "string")

    # ── helpers ──

    def _find_proposal_defn(self) -> dict[str, Any]:
        """Locate LLMFactProposal in $defs (strict schema puts all nested models there)."""
        defs = self.schema.get("$defs", {}) or self.schema.get("definitions", {})
        for name, defn in defs.items():
            if not isinstance(defn, dict):
                continue
            if name == "LLMFactProposal" or defn.get("title") == "LLMFactProposal":
                return defn
        self.fail(f"LLMFactProposal not found in $defs; got {sorted(defs.keys())}")
        raise RuntimeError("unreachable")  # for type narrowing

    def _resolve_or_self(self, node: dict[str, Any]) -> dict[str, Any]:
        """If node is a $ref, resolve it; otherwise return node as-is."""
        if "$ref" in node:
            resolved = _resolve_ref(self.schema, node["$ref"])
            self.assertIsNotNone(resolved, f"cannot resolve $ref: {node['$ref']}")
            assert resolved is not None
            return resolved
        return node


class NormalizeFieldValuesAcceptsObjectFormTest(unittest.TestCase):
    """BF-03: _normalize_field_values must accept the new object form."""

    def test_accepts_dict_form(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_field_values

        result = _normalize_field_values(
            [
                {"tag": "string", "value": "hello"},
                {"tag": "int", "value": 42},
            ]
        )
        self.assertEqual(result, [("string", "hello"), ("int", 42)])

    def test_accepts_pydantic_object_form(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_field_values

        class FakeLLMFieldValue:
            def __init__(self, tag, value):
                self.tag = tag
                self.value = value

        result = _normalize_field_values(
            [
                FakeLLMFieldValue("string", "hello"),
                FakeLLMFieldValue("bool", True),
            ]
        )
        self.assertEqual(result, [("string", "hello"), ("bool", True)])

    def test_still_accepts_tuple_form(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_field_values

        result = _normalize_field_values([("string", "x")])
        self.assertEqual(result, [("string", "x")])

    def test_still_accepts_list_form(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_field_values

        result = _normalize_field_values([["string", "x"]])
        self.assertEqual(result, [("string", "x")])

    def test_rejects_non_string_tag(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_field_values
        from factpy_kernel.agent.errors import AgentContractError

        with self.assertRaises(AgentContractError):
            _normalize_field_values([{"tag": 42, "value": "x"}])


class NormalizeEntityIdentityTest(unittest.TestCase):
    """BF-08: _normalize_entity_identity must accept dict and list forms."""

    def test_accepts_dict_form(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_entity_identity

        result = _normalize_entity_identity({"title": "README", "year": 2026})
        self.assertEqual(result, {"title": "README", "year": 2026})

    def test_accepts_list_of_dict_entries(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_entity_identity

        result = _normalize_entity_identity(
            [
                {"name": "title", "value": "README"},
                {"name": "year", "value": 2026},
            ]
        )
        self.assertEqual(result, {"title": "README", "year": 2026})

    def test_accepts_list_of_attr_objects(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_entity_identity

        class FakeLLMIdentityEntry:
            def __init__(self, name, value):
                self.name = name
                self.value = value

        result = _normalize_entity_identity(
            [
                FakeLLMIdentityEntry("title", "README"),
                FakeLLMIdentityEntry("year", 2026),
            ]
        )
        self.assertEqual(result, {"title": "README", "year": 2026})

    def test_rejects_non_string_name(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_entity_identity
        from factpy_kernel.agent.errors import AgentContractError

        with self.assertRaises(AgentContractError):
            _normalize_entity_identity([{"name": 42, "value": "x"}])

    def test_rejects_empty_name(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_entity_identity
        from factpy_kernel.agent.errors import AgentContractError

        with self.assertRaises(AgentContractError):
            _normalize_entity_identity([{"name": "", "value": "x"}])

    def test_rejects_duplicate_name(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_entity_identity
        from factpy_kernel.agent.errors import AgentContractError

        with self.assertRaises(AgentContractError):
            _normalize_entity_identity(
                [
                    {"name": "title", "value": "A"},
                    {"name": "title", "value": "B"},
                ]
            )

    def test_rejects_non_dict_non_list(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_entity_identity
        from factpy_kernel.agent.errors import AgentContractError

        with self.assertRaises(AgentContractError):
            _normalize_entity_identity("not a dict or list")


if __name__ == "__main__":
    unittest.main()
