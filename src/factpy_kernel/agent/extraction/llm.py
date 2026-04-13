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

    llm_identity_entry = create_model(
        "_LLMIdentityEntry",
        name=(str, Field(..., description="Identity field name from schema")),
        value=(
            str | int | float | bool | None,
            Field(..., description="Identity field value; one of string, int, float, bool, or null"),
        ),
    )

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
            list[llm_identity_entry],
            Field(..., description="Entity identity as a list of {name, value} entries"),
        ),
        pred_id=(pred_literal, Field(..., description="Predicate ID from allowed list")),
        field_values=(
            list[llm_field_value],
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
