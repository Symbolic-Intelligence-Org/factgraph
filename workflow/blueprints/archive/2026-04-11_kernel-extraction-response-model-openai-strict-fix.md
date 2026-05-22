# Blueprint: Kernel Extraction Response Model — OpenAI strict function-calling fix

- Status: implemented
- Created: 2026-04-11
- Kind: **scoped bugfix** (not a feature blueprint)
- Parent: [2026-04-10_agent-layer4c3a-single-segment-extraction.md](../archive/2026-04-10_agent-layer4c3a-single-segment-extraction.md) (archived)
- Related Modules:
  - `src/factpy_kernel/agent/extraction/llm.py` (patch)
  - `src/factpy_kernel/agent/extraction/validation.py` (patch)
  - `src/factpy_kernel/tests/test_agent_l4c3a_response_model_schema.py` (new)

---

## 0. Scope

Fix a single production-blocker bug discovered by the B3 load test on the first real-LLM call:

```
litellm.BadRequestError: OpenAIException -
Invalid schema for function 'SegmentExtractionResponse':
In context=('properties', 'field_values', 'items'), array schema missing items.
```

**Not in scope**: redesigning the response model, changing the LLM provider, adding new extraction features, or revisiting any 4C3-a design decisions other than the `field_values` and `entity_identity` types (both of which violate OpenAI strict mode and are covered by this single patch).

---

## 1. Root Cause

### 1.1 The general class of bug: permissive object schemas

`src/factpy_kernel/agent/extraction/llm.py` currently declares two fields that become **permissive object schemas** when Pydantic serializes them for OpenAI's strict function-calling mode:

```python
entity_identity=(dict[str, Any], Field(..., description="Identity fields")),
# ...
field_values=(
    list[tuple[str, Any]],
    Field(..., description="List of (tag, value) pairs for predicate fields"),
),
```

Both violate OpenAI strict mode, but for different reasons under the same umbrella (["raw permissive schemas incompatible with strict"](https://developers.openai.com/api/docs/guides/structured-outputs)):

### 1.2 Problem A: `list[tuple[str, Any]]`

Pydantic serializes `tuple[str, Any]` to:

```json
{
  "type": "array",
  "prefixItems": [{"type": "string"}, {}],
  "minItems": 2,
  "maxItems": 2
}
```

OpenAI strict rejects this because:
1. `prefixItems` is a JSON Schema 2020-12 feature not in OpenAI's supported subset
2. The `Any` → `{}` untyped entry violates "every schema must have explicit type"

Observed error from B3 smoke (first failure surface):
```
Invalid schema for function 'SegmentExtractionResponse':
In context=('properties', 'field_values', 'items'), array schema missing items.
```

### 1.3 Problem B: `dict[str, Any]`

Pydantic serializes `dict[str, Any]` to:

```json
{
  "type": "object",
  "additionalProperties": true
}
```

OpenAI strict requires **`additionalProperties: false` on every object schema**. An `additionalProperties: true` object is uncapturable in a strict schema — there's no way to enumerate allowed properties, so the API rejects the whole function definition.

This error would surface as the **second failure** after Problem A is fixed. Confirmed via local inspection of `openai.pydantic_function_tool(build_response_model(schema_ir))["function"]["parameters"]`, which mutates the raw Pydantic schema for strict mode and leaves `entity_identity` still failing.

### 1.4 Why we only saw Problem A in the first B3 run

OpenAI validates the function definition as a whole and returns the first structural error it hits. Our raw Pydantic output had both problems simultaneously, but Problem A fired first because `field_values` comes before `entity_identity` in OpenAI's deterministic traversal. Fixing only Problem A would unblock the request past that specific check, and then the next request would fail on Problem B with a different message. This is a classic "peel the onion" failure mode that a partial fix would hide behind a fresh error class.

### 1.5 Why current tests don't catch either problem

[`test_agent_l4c3a_extractor.py:54`](../../src/factpy_kernel/tests/test_agent_l4c3a_extractor.py#L54) mocks `build_default_llm_client` with `_FakeClient(lambda kwargs: kwargs)` that echoes Pydantic-validated kwargs back. **The real OpenAI strict-mode schema validation path is never exercised**, so both bugs sat latent until B3 made a live API call.

Even worse: inspecting `model.model_json_schema()` (raw Pydantic output) is **not sufficient** to catch these bugs because it shows the un-mutated schema. The actual request path runs through `openai.pydantic_function_tool(model)` (or equivalent in Instructor), which applies strict-mode transformations. Problem B only manifests in the transformed schema. **The CI guard test must inspect the transformed schema, not raw Pydantic.**

---

## 2. Frozen Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| BF-01 | **Reframed**: Replace *all* permissive object schemas in the response model (`tuple[str, Any]`, `dict[str, Any]`, raw `Any`) with typed Pydantic sub-models that serialize to strict-compatible JSON schema | The root cause is "raw permissive object schemas incompatible with OpenAI strict", not just the tuple variant. Fixing only one is guaranteed to surface the next problem on rerun |
| BF-02 | All new sub-models (`_LLMFieldValue`, `_LLMIdentityEntry`) are **private** helpers; not exported; Layer 4C3-a's external contract is unchanged | The external `FactDraftSpec.field_values` / `FactDraftSpec.entity_identity` types stay the same; only the LLM response path changes |
| BF-03 | `_normalize_field_values` gets extended to accept dict and attr-based entry forms in addition to tuple/list | Single chokepoint already exists; purely additive; backward compatible with mock tests |
| BF-04 | **Revised**: The CI guard test inspects `openai.pydantic_function_tool(model_cls)["function"]["parameters"]` — the actual strict-mode schema sent to the API — not `model.model_json_schema()` | Raw Pydantic output is insufficient: it would miss `additionalProperties: true` on `dict[str, Any]` because that field only manifests after strict-mode transformation. The guard must validate the real API-boundary artifact |
| BF-05 | All `value` fields in the sub-models are constrained to `str \| int \| float \| bool \| None` | OpenAI strict refuses `Any`; these four primitives cover every `type_domain` at the LLM boundary (`string / int / float / bool / entity_ref / uuid / time / bytes` — the last four are serialized as `str`) |
| BF-06 | Do not change `LLMFactProposal` class name or `SegmentExtractionResponse` structure | Keeps blueprint narrow; minimizes diff; new names (`_LLMFieldValue`, `_LLMIdentityEntry`) live inside `build_response_model` |
| BF-07 | **New**: `entity_identity` in the response model becomes `list[_LLMIdentityEntry]` (entries with `name: str, value: str|int|float|bool|None`), symmetric with `field_values` | `dict[str, Any]` is not expressible in OpenAI strict mode. A typed list of name/value entries is the minimal compatible shape. `validate_proposal` normalizes it back to `dict[str, Any]` for all downstream code |
| BF-08 | **New**: `_normalize_entity_identity` helper added to `validation.py`, called from `validate_proposal` before `_validate_entity_identity` | Mirrors the `_normalize_field_values` pattern. Accepts four forms: dict (back-compat for mocks), list of `{name, value}` dicts (LLM JSON form), list of attr-based objects (Pydantic instance form), and rejects anything else |
| BF-09 | **New**: Guard test asserts **every object** in the strict schema has `"additionalProperties": false` (not just absent or `true`) | This is the canonical way to detect Problem B (`dict[str, Any]` leakage) and any future leak of the same class. Single assertion catches the entire family of bugs |

### Explicit non-goals

- Not changing `FactDraftSpec.field_values` or `FactDraftSpec.entity_identity` external types
- Not changing `validate_proposal` callable signature
- Not changing Instructor / LiteLLM version pins
- Not changing prompt templates
- Not opening a broader schema-validation review for other Layer-4 types (none currently use permissive schemas on LLM response paths — verified by grep)
- Not adding a runtime config toggle ("strict vs loose mode")
- Not covering Anthropic / Gemini model-specific quirks (separate B3 will surface those)

---

## 3. The Fix

### 3.1 `llm.py` change

Replace **both** `dict[str, Any]` (entity_identity) and `list[tuple[str, Any]]` (field_values) with typed private sub-models:

```python
# src/factpy_kernel/agent/extraction/llm.py

from __future__ import annotations

from importlib import import_module
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model


def build_response_model(schema_ir: dict[str, Any]) -> type[BaseModel]:
    """Build a runtime-constrained response model from schema IR."""

    entities = schema_ir.get("entities", [])
    predicates = schema_ir.get("predicates", [])
    allowed_entity_types = tuple(
        entry["entity_type"]
        for entry in entities
        if isinstance(entry, dict) and isinstance(entry.get("entity_type"), str) and entry.get("entity_type")
    )
    allowed_pred_ids = tuple(
        entry["pred_id"]
        for entry in predicates
        if isinstance(entry, dict) and isinstance(entry.get("pred_id"), str) and entry.get("pred_id")
    )
    if not allowed_entity_types or not allowed_pred_ids:
        raise ValueError("schema_ir must contain at least one entity_type and pred_id")

    entity_literal = Literal.__getitem__(allowed_entity_types)  # type: ignore[attr-defined]
    pred_literal = Literal.__getitem__(allowed_pred_ids)  # type: ignore[attr-defined]

    # BF-01/BF-02/BF-07: typed sub-models, not permissive object schemas.
    # Leading underscore = private; not exported.

    # BF-07: entity_identity becomes list[_LLMIdentityEntry] — name/value
    # entries. dict[str, Any] is not expressible in OpenAI strict mode
    # because it requires additionalProperties=true, which strict refuses.
    llm_identity_entry = create_model(
        "_LLMIdentityEntry",
        name=(str, Field(..., description="Identity field name from schema")),
        value=(
            str | int | float | bool | None,
            Field(..., description="Identity field value; one of string, int, float, bool, or null"),
        ),
    )

    # BF-01: field_values becomes list[_LLMFieldValue] — same shape pattern
    # as _LLMIdentityEntry for consistency.
    llm_field_value = create_model(
        "_LLMFieldValue",
        tag=(str, Field(..., description="Field tag matching schema arg_specs type_domain")),
        value=(
            str | int | float | bool | None,
            Field(..., description="Field value; one of string, int, float, bool, or null"),
        ),
    )

    llm_fact_proposal = create_model(
        "LLMFactProposal",
        entity_type=(entity_literal, Field(..., description="Entity type from allowed list")),
        entity_identity=(
            list[llm_identity_entry],  # ← was: dict[str, Any]
            Field(..., description="Entity identity as a list of {name, value} entries"),
        ),
        pred_id=(pred_literal, Field(..., description="Predicate ID from allowed list")),
        field_values=(
            list[llm_field_value],     # ← was: list[tuple[str, Any]]
            Field(..., description="Predicate field entries (tag, value)"),
        ),
        confidence=(float | None, Field(None, ge=0.0, le=1.0, description="LLM self-assessed confidence")),
        llm_note=(str | None, Field(None, description="Optional reasoning note")),
    )
    return create_model(
        "SegmentExtractionResponse",
        proposals=(
            list[llm_fact_proposal],
            Field(default_factory=list, description="Extracted fact proposals. Empty if no facts found."),
        ),
    )


def build_default_llm_client() -> Any:
    """Build the default Instructor-over-LiteLLM client."""

    instructor = import_module("instructor")
    litellm = import_module("litellm")
    return instructor.from_litellm(litellm.completion)
```

### 3.2 `validation.py` change

Two changes:
1. **Extend `_normalize_field_values`** (BF-03) to accept dict/attr-based forms
2. **Add `_normalize_entity_identity`** (BF-08) following the same pattern
3. **Call `_normalize_entity_identity`** inside `validate_proposal` before any downstream validation

```python
# In validate_proposal(), change line 24:
entity_identity = _normalize_entity_identity(_proposal_field(proposal, "entity_identity"))
```

```python
# BF-03 (additive): _normalize_field_values gains dict + attr-based handlers
def _normalize_field_values(value: Any) -> list[tuple[str, Any]]:
    if not isinstance(value, list):
        raise AgentContractError("field_values must be list")
    out: list[tuple[str, Any]] = []
    for item in value:
        # Existing: tuple form
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
            out.append((item[0], item[1]))
            continue
        # Existing: list form
        if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str):
            out.append((item[0], item[1]))
            continue
        # BF-03 NEW: dict form (JSON response shape)
        if isinstance(item, dict) and "tag" in item and "value" in item:
            tag = item["tag"]
            if not isinstance(tag, str):
                raise AgentContractError("field_values entries must have string tag")
            out.append((tag, item["value"]))
            continue
        # BF-03 NEW: Pydantic object form (_LLMFieldValue instance)
        if hasattr(item, "tag") and hasattr(item, "value"):
            tag = getattr(item, "tag")
            if not isinstance(tag, str):
                raise AgentContractError("field_values entries must have string tag")
            out.append((tag, getattr(item, "value")))
            continue
        raise AgentContractError("field_values entries must be pair or {tag,value} object")
    return out


# BF-08 (new helper): _normalize_entity_identity — mirrors field_values pattern
def _normalize_entity_identity(value: Any) -> dict[str, Any]:
    """
    Normalize entity_identity from any of four accepted forms to a canonical dict.

    Accepted forms:
      1. dict[str, Any]                                — back-compat for mock tests
      2. list[dict] with "name" + "value" keys         — LLM JSON response form
      3. list of objects with .name / .value attrs     — Pydantic instance form
                                                          (from _LLMIdentityEntry)
      4. (rejected) anything else                      — raises AgentContractError

    Returns: dict[str, Any] suitable for downstream _validate_entity_identity
             and FactDraftSpec.
    """
    if isinstance(value, dict):
        # Back-compat: mock tests and any upstream caller that already has a dict
        return dict(value)
    if not isinstance(value, list):
        raise AgentContractError("entity_identity must be dict or list")

    out: dict[str, Any] = {}
    for item in value:
        # Dict form (LLM JSON response shape)
        if isinstance(item, dict) and "name" in item and "value" in item:
            name = item["name"]
            if not isinstance(name, str) or not name:
                raise AgentContractError("entity_identity entries must have non-empty string name")
            if name in out:
                raise AgentContractError(f"entity_identity has duplicate name: {name}")
            out[name] = item["value"]
            continue
        # Pydantic object form (_LLMIdentityEntry instance)
        if hasattr(item, "name") and hasattr(item, "value"):
            name = getattr(item, "name")
            if not isinstance(name, str) or not name:
                raise AgentContractError("entity_identity entries must have non-empty string name")
            if name in out:
                raise AgentContractError(f"entity_identity has duplicate name: {name}")
            out[name] = getattr(item, "value")
            continue
        raise AgentContractError("entity_identity entries must be {name, value} object")
    return out
```

**Nothing else in `validation.py` changes.** The rest of `validate_proposal` — including `_validate_entity_identity` and `FactDraft.from_checkpoint` — continues to work with `dict[str, Any]` because the normalizer returns that form.

### 3.3 Duplicate-name handling

`_normalize_entity_identity` rejects duplicate `name` entries from the LLM list (one identity field should appear at most once). This is defensive: the LLM *could* emit duplicates; dict-form input cannot, by construction. Strict rejection is safer than silent last-write-wins.

### 3.4 New test: offline OpenAI-strict schema guard

New file: `src/factpy_kernel/tests/test_agent_l4c3a_response_model_schema.py`

**Key difference from v1 draft (BF-04 revision)**: inspects `openai.pydantic_function_tool(model_cls)["function"]["parameters"]` — the exact strict-mode schema that would be sent to the API — not raw `model.model_json_schema()`. This catches `additionalProperties: true` leaks that raw Pydantic output would miss.

```python
"""Offline guard for OpenAI strict function-calling compatibility.

This test inspects the schema that would actually be sent to OpenAI's API
(via openai.pydantic_function_tool), not the raw Pydantic JSON schema.

It guards against structural features OpenAI strict mode rejects:
  - prefixItems (JSON Schema 2020-12; not in OpenAI's subset)
  - Empty / untyped items schemas ({})
  - Objects with additionalProperties != false

If this test breaks, it means someone added a field to the response model
that will fail with 'BadRequestError: Invalid schema' in production.

This test is SKIPPED if the openai package is not installed (Layer 4C3-a
optional dependency). When skipped, the dict/attr normalize tests below
still run unconditionally.
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
        result = _normalize_field_values([
            {"tag": "string", "value": "hello"},
            {"tag": "int", "value": 42},
        ])
        self.assertEqual(result, [("string", "hello"), ("int", 42)])

    def test_accepts_pydantic_object_form(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_field_values

        class FakeLLMFieldValue:
            def __init__(self, tag, value):
                self.tag = tag
                self.value = value

        result = _normalize_field_values([
            FakeLLMFieldValue("string", "hello"),
            FakeLLMFieldValue("bool", True),
        ])
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
        result = _normalize_entity_identity([
            {"name": "title", "value": "README"},
            {"name": "year", "value": 2026},
        ])
        self.assertEqual(result, {"title": "README", "year": 2026})

    def test_accepts_list_of_attr_objects(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_entity_identity

        class FakeLLMIdentityEntry:
            def __init__(self, name, value):
                self.name = name
                self.value = value

        result = _normalize_entity_identity([
            FakeLLMIdentityEntry("title", "README"),
            FakeLLMIdentityEntry("year", 2026),
        ])
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
            _normalize_entity_identity([
                {"name": "title", "value": "A"},
                {"name": "title", "value": "B"},
            ])

    def test_rejects_non_dict_non_list(self) -> None:
        from factpy_kernel.agent.extraction.validation import _normalize_entity_identity
        from factpy_kernel.agent.errors import AgentContractError
        with self.assertRaises(AgentContractError):
            _normalize_entity_identity("not a dict or list")


if __name__ == "__main__":
    unittest.main()
```

---

## 4. Impact Analysis

### Files touched (3 total, unchanged count)

1. `src/factpy_kernel/agent/extraction/llm.py` — `build_response_model` body:
   - Add `_LLMIdentityEntry` sub-model
   - Add `_LLMFieldValue` sub-model
   - Change `entity_identity` field type to `list[_LLMIdentityEntry]`
   - Change `field_values` field type to `list[_LLMFieldValue]`
2. `src/factpy_kernel/agent/extraction/validation.py`:
   - Extend `_normalize_field_values` with dict / attr-based handlers
   - Add new `_normalize_entity_identity` helper
   - Change one line in `validate_proposal` to call the new normalizer
3. `src/factpy_kernel/tests/test_agent_l4c3a_response_model_schema.py` — new file with 3 test classes (15 tests total)

### Backward compatibility

- **External contract**: `FactDraftSpec.field_values` stays `list[tuple[str, Any]]`; `FactDraftSpec.entity_identity` stays `dict[str, Any]`. Zero external API changes.
- **Public class names**: `LLMFactProposal` and `SegmentExtractionResponse` unchanged.
- **`validate_proposal` signature**: unchanged.
- **Existing mock-based tests**:
  - `test_agent_l4c3a_extractor.py` — fake clients currently construct proposals with `entity_identity={"title": "README"}` (dict form) and `field_values=[("string", "x"), ...]` (tuple/list form). Both forms stay accepted. **BF-03 and BF-08 are purely additive**.
  - `test_agent_l4c3a_validation.py` — same applies. Any existing direct-dict or tuple-list inputs remain legal.

### New failure modes introduced

- **`value` constrained to `str | int | float | bool | None`**: LLM can no longer emit nested lists/dicts as values. Acceptable because:
  - All current `type_domain` values (`string / int / float / bool / entity_ref / uuid / time / bytes`) are encoded as scalars at the LLM boundary
  - `entity_ref / uuid / time / bytes` were already serialized as strings before — no behavior change
  - Nested structural values were never valid in `FactDraftSpec.field_values` anyway (downstream type checks reject them)
- **Duplicate identity names rejected**: `_normalize_entity_identity` raises on duplicate `name` entries. New failure mode only for LLM-generated duplicates; dict inputs cannot produce this case.
- **OpenAI provider-specific test skipped without `openai` package**: the guard test gracefully skips if `openai` is not installed (e.g., in CI environments that only install base deps). When skipped, the `_normalize_*` unit tests still run unconditionally.

### Tests that must run (not just pass)

The guard test is only meaningful **when `openai` is installed**. In the B3 smoke environment (miniforge) that already has `instructor` + `litellm`, `openai` is present as a transitive dep, so the guard executes normally. In a pure CI environment that only installs `pydantic>=2` and not the extraction optional deps, the guard skips — which is acceptable because that CI environment can't exercise the bug anyway.

---

## 5. Implementation Order

```
Step 1: Apply llm.py patch (build_response_model)
        → add _LLMIdentityEntry sub-model (BF-07)
        → add _LLMFieldValue sub-model (BF-01)
        → entity_identity: list[_LLMIdentityEntry]
        → field_values: list[_LLMFieldValue]

Step 2: Apply validation.py patches
        → extend _normalize_field_values with dict/attr handlers (BF-03)
        → add _normalize_entity_identity helper (BF-08)
        → update validate_proposal to call _normalize_entity_identity

Step 3: Add test_agent_l4c3a_response_model_schema.py
        → OpenAIStrictSchemaGuardTest       (5 tests, skipped if openai missing)
        → NormalizeFieldValuesAcceptsObjectFormTest (5 tests)
        → NormalizeEntityIdentityTest       (7 tests)
        → total: 17 new tests (5 conditionally skipped)

Step 4: Run 4C3-a-specific tests first:
        → python -m unittest src.factpy_kernel.tests.test_agent_l4c3a_models \
                             src.factpy_kernel.tests.test_agent_l4c3a_validation \
                             src.factpy_kernel.tests.test_agent_l4c3a_prompts \
                             src.factpy_kernel.tests.test_agent_l4c3a_extractor \
                             src.factpy_kernel.tests.test_agent_l4c3a_workflow \
                             src.factpy_kernel.tests.test_agent_l4c3a_response_model_schema

Step 5: Run full regression:
        → python -m unittest discover -s src/factpy_kernel/tests
        → expected: 942 tests (prior baseline) + 17 new = 959 tests
        → 1 baseline skip (pymupdf4llm) + 0-5 conditional skips (openai guard) depending on env

Step 6: Rerun B3 smoke:
        → PYTHONPATH=src /Users/zhenzhili/miniforge3/bin/python \
            docs/references/working/load-test-2026-04-11/run_load_test.py \
            --manifest docs/references/working/load-test-2026-04-11/samples_manifest.yaml \
            --sample medium_01_security
        → expected: no more instructor_retry_exhausted
        → expected: either success with valid_specs > 0, or a different
          (more informative) failure mode (schema rejection, scope rejection, etc.)
```

---

## 6. Acceptance Criteria

### llm.py
- [ ] `build_response_model` adds `_LLMIdentityEntry` sub-model (private, not exported)
- [ ] `build_response_model` adds `_LLMFieldValue` sub-model (private, not exported)
- [ ] `entity_identity` field type is `list[_LLMIdentityEntry]` (not `dict[str, Any]`)
- [ ] `field_values` field type is `list[_LLMFieldValue]` (not `list[tuple[str, Any]]`)
- [ ] `LLMFactProposal` / `SegmentExtractionResponse` class names unchanged

### validation.py
- [ ] `_normalize_field_values` accepts all 4 forms: tuple, list, dict, attr-based
- [ ] `_normalize_field_values` rejects non-string tag
- [ ] `_normalize_entity_identity` helper added
- [ ] `_normalize_entity_identity` accepts: dict, list of dict, list of attr-based
- [ ] `_normalize_entity_identity` rejects: non-string name, empty name, duplicate name, non-dict/non-list input
- [ ] `validate_proposal` calls `_normalize_entity_identity` on the input
- [ ] `validate_proposal` signature unchanged

### New test file
- [ ] `OpenAIStrictSchemaGuardTest` uses `openai.pydantic_function_tool(model_cls)["function"]["parameters"]` (not raw `model_json_schema()`)
- [ ] `test_no_prefixItems_anywhere` passes
- [ ] `test_no_empty_or_untyped_items_schemas` passes
- [ ] `test_all_objects_have_additional_properties_false` passes **(this is the canonical BF-09 guard)**
- [ ] `test_entity_identity_is_list_of_typed_objects` passes
- [ ] `test_field_values_is_list_of_typed_objects` passes
- [ ] Guard test gracefully skips if `openai` package is absent
- [ ] `NormalizeFieldValuesAcceptsObjectFormTest` — 5 tests pass unconditionally
- [ ] `NormalizeEntityIdentityTest` — 7 tests pass unconditionally

### Regression
- [ ] All existing 4C3-a tests pass unchanged
- [ ] Full regression: 942 prior + 17 new = 959; baseline 1 skip + env-dependent skips

### B3 reactivation
- [ ] `medium_01_security` exits the `instructor_retry_exhausted` failure mode
- [ ] Run record shows either `valid_count > 0` or a different, informative error class
- [ ] **No `BadRequestError: Invalid schema`** in the error samples

---

## 7. Known Constraints

1. **`value` is constrained**: nested list/dict values from LLM are no longer representable. If a future schema needs compound values, this layer needs revisiting.
2. **Guard test is OpenAI-specific**: it asserts the schema satisfies OpenAI strict mode via `openai.pydantic_function_tool`. If the project later moves off OpenAI exclusively, the assertions may need relaxation or provider-parameterization.
3. **Does not fix other providers**: this only validates against OpenAI's rules. Anthropic / Gemini specific quirks must be discovered via separate B3 runs against those providers.
4. **Guard test conditionally skipped**: when `openai` is not installed, the `OpenAIStrictSchemaGuardTest` class is skipped via `@unittest.skipUnless`. The `_normalize_*` tests still run unconditionally. This is an acceptable trade-off: environments that can't run OpenAI also can't exercise the bug.
5. **Instructor / OpenAI SDK version-specific**: if either library changes its default schema-generation mode in a future release, the guard test may need updating. The test's `openai.pydantic_function_tool` call is the canonical entry point for OpenAI strict schema generation as of 2026-04; it is stable but not immutable.
6. **Does not add a real LLM integration test**: B3 itself serves that role. This blueprint intentionally stays offline.
7. **Duplicate identity field names are rejected**: the new behavior of `_normalize_entity_identity` raises on duplicates. This is stricter than the old dict-only path (where the LLM couldn't produce duplicates anyway). If a real use case emerges where the LLM needs to emit duplicates, revisit.

---

## 8. Outcome / Deviations

### Outcome

- Implemented in:
  - `src/factpy_kernel/agent/extraction/llm.py`
  - `src/factpy_kernel/agent/extraction/validation.py`
  - `src/factpy_kernel/tests/test_agent_l4c3a_response_model_schema.py`
- Existing mock-based extraction tests that instantiated `response_model(...)` were updated to use the new strict-compatible `entity_identity` / `field_values` shapes.
- Targeted regression passed:
  - `PYTHONPATH=src /Users/zhenzhili/miniforge3/bin/python -m unittest ...test_agent_l4c3a_* ...test_agent_observability_extraction_hooks`
  - `43 tests` passed
- Full regression passed:
  - `PYTHONPATH=src /Users/zhenzhili/miniforge3/bin/python -m unittest discover -s src/factpy_kernel/tests`
  - `959 tests` passed, `2 skipped`
- B3 rerun passed the original gate:
  - `medium_01_security` no longer hits `Invalid schema` / `instructor_retry_exhausted`
  - `long_01_kernel_p0` also clears strict-schema validation
  - Current next bottleneck is business-level rejection: `schema_field_type_mismatch` / `field_values length mismatch`

### Deviations

- The original draft expected `1` baseline skip plus optional OpenAI guard skips. In the validating environment, the suite finished with `2 skipped` because the existing baseline skip remained and one additional environment-dependent skip was present.
- The fix remained kernel/agent-internal and did not require any runtime_v1 or ledger changes.
