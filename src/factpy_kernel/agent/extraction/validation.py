from __future__ import annotations

from typing import Any

from ..documents import DocumentSegment, ExtractionProvenance, FactDraftSpec
from ..errors import AgentContractError, AgentScopeViolation
from ..session import AgentScope, AgentScopeGuard
from ..draft import FactDraft
from .models import ExtractionRejection


def validate_proposal(
    proposal: Any,
    proposal_index: int,
    *,
    schema_ir: dict[str, Any],
    scope: AgentScope,
    segment: DocumentSegment,
) -> tuple[FactDraftSpec | None, ExtractionRejection | None]:
    """Validate a single LLM proposal against schema, scope, and FactDraftSpec."""

    entity_type = _proposal_field(proposal, "entity_type")
    pred_id = _proposal_field(proposal, "pred_id")
    entity_identity = _normalize_entity_identity(_proposal_field(proposal, "entity_identity"))
    field_values = _normalize_field_values(_proposal_field(proposal, "field_values"))
    confidence = _normalize_confidence(_proposal_optional_field(proposal, "confidence"))
    llm_note = _proposal_optional_field(proposal, "llm_note")

    if not _schema_has_entity_type(schema_ir, entity_type):
        return None, ExtractionRejection(
            reason="schema_entity_type_unknown",
            detail=f"entity_type '{entity_type}' not in schema",
            proposal_index=proposal_index,
        )
    if not _schema_has_pred_id(schema_ir, pred_id):
        return None, ExtractionRejection(
            reason="schema_pred_id_unknown",
            detail=f"pred_id '{pred_id}' not in schema",
            proposal_index=proposal_index,
        )

    type_error = _validate_entity_identity(schema_ir, entity_type, entity_identity)
    if type_error is not None:
        return None, ExtractionRejection(
            reason="schema_field_type_mismatch",
            detail=type_error,
            proposal_index=proposal_index,
        )
    type_error = _validate_field_types(schema_ir, pred_id, field_values)
    if type_error is not None:
        return None, ExtractionRejection(
            reason="schema_field_type_mismatch",
            detail=type_error,
            proposal_index=proposal_index,
        )

    try:
        preview = FactDraft.from_checkpoint(
            {
                "draft_id": f"draft_extract_preview_{proposal_index}",
                "entity_type": entity_type,
                "entity_identity": entity_identity,
                "pred_id": pred_id,
                "field_values": field_values,
                "confidence": confidence,
                "source": f"doc:{segment.doc_id}:seg:{segment.segment_id}",
                "source_loc": f"chars:{segment.char_offset_start}-{segment.char_offset_end}",
                "note": llm_note,
                "created_at": 0,
                "status": "pending",
                "session_id": "extract_preview",
                "conversation_turn": 0,
                "assertion_id": None,
            }
        )
        AgentScopeGuard().validate(preview, scope)
    except AgentScopeViolation as exc:
        reason = "scope_entity_type_denied"
        if "pred_id" in exc.details:
            reason = "scope_pred_id_denied"
        elif "min_confidence" in exc.details:
            reason = "scope_min_confidence"
        return None, ExtractionRejection(
            reason=reason,  # type: ignore[arg-type]
            detail=str(exc),
            proposal_index=proposal_index,
        )
    except AgentContractError as exc:
        return None, ExtractionRejection(
            reason="spec_construction_failure",
            detail=str(exc),
            proposal_index=proposal_index,
        )

    try:
        spec = FactDraftSpec(
            entity_type=entity_type,
            entity_identity=entity_identity,
            pred_id=pred_id,
            field_values=field_values,
            extraction_provenance=_build_provenance_from_segment(segment),
            confidence=confidence,
            note=llm_note,
        )
    except AgentContractError as exc:
        return None, ExtractionRejection(
            reason="spec_construction_failure",
            detail=str(exc),
            proposal_index=proposal_index,
        )
    return spec, None


def _build_provenance_from_segment(segment: DocumentSegment) -> ExtractionProvenance:
    return ExtractionProvenance(
        source_document_id=segment.doc_id,
        segment_id=segment.segment_id,
        char_offset_start=segment.char_offset_start,
        char_offset_end=segment.char_offset_end,
        raw_text=segment.raw_text,
        page_number=segment.page_number,
        extraction_method="llm_refined",
    )


def _schema_has_entity_type(schema_ir: dict[str, Any], entity_type: str) -> bool:
    return any(
        isinstance(entry, dict) and entry.get("entity_type") == entity_type
        for entry in schema_ir.get("entities", [])
    )


def _schema_has_pred_id(schema_ir: dict[str, Any], pred_id: str) -> bool:
    return any(
        isinstance(entry, dict) and entry.get("pred_id") == pred_id
        for entry in schema_ir.get("predicates", [])
    )


def _validate_entity_identity(
    schema_ir: dict[str, Any],
    entity_type: str,
    entity_identity: dict[str, Any],
) -> str | None:
    entity_row = next(
        (
            entry
            for entry in schema_ir.get("entities", [])
            if isinstance(entry, dict) and entry.get("entity_type") == entity_type
        ),
        None,
    )
    if not isinstance(entity_row, dict):
        return f"entity_type '{entity_type}' not in schema"
    expected_fields = [
        field
        for field in entity_row.get("identity_fields", [])
        if isinstance(field, dict) and isinstance(field.get("name"), str)
    ]
    expected_names = {field["name"] for field in expected_fields}
    if set(entity_identity.keys()) != expected_names:
        return f"identity fields mismatch for entity_type '{entity_type}': expected {sorted(expected_names)}"
    for field in expected_fields:
        name = field["name"]
        type_domain = field.get("type_domain", "string")
        error = _validate_type_domain(type_domain, entity_identity.get(name), field_name=name)
        if error is not None:
            return error
    return None


def _validate_field_types(
    schema_ir: dict[str, Any],
    pred_id: str,
    field_values: list[tuple[str, Any]],
) -> str | None:
    predicate_row = next(
        (
            entry
            for entry in schema_ir.get("predicates", [])
            if isinstance(entry, dict) and entry.get("pred_id") == pred_id
        ),
        None,
    )
    if not isinstance(predicate_row, dict):
        return f"pred_id '{pred_id}' not in schema"
    arg_specs = [
        arg
        for arg in predicate_row.get("arg_specs", [])
        if isinstance(arg, dict) and isinstance(arg.get("type_domain"), str)
    ]
    rest_specs = arg_specs[1:] if arg_specs else []
    if len(field_values) != len(rest_specs):
        return (
            f"field_values length mismatch for pred_id '{pred_id}': "
            f"got {len(field_values)}, expected {len(rest_specs)}"
        )
    for idx, ((tag, value), spec) in enumerate(zip(field_values, rest_specs, strict=True)):
        type_domain = spec.get("type_domain", "")
        if tag != type_domain:
            # Fallback: some models (e.g. Mistral) write arg name instead of type_domain.
            # If tag matches the arg spec's name, silently correct to type_domain.
            arg_name = spec.get("name", "")
            if tag == arg_name and type_domain:
                field_values[idx] = (type_domain, value)
                tag = type_domain
            else:
                return f"field tag '{tag}' does not match expected type_domain '{type_domain}'"
        error = _validate_type_domain(type_domain, value, field_name=str(spec.get('name', 'field')))
        if error is not None:
            return error
    return None


def _validate_type_domain(type_domain: Any, value: Any, *, field_name: str) -> str | None:
    if type_domain == "string":
        if not isinstance(value, str):
            return f"{field_name} must be string"
    elif type_domain == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"{field_name} must be int"
    elif type_domain == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"{field_name} must be float"
    elif type_domain == "bool":
        if not isinstance(value, bool):
            return f"{field_name} must be bool"
    elif type_domain == "entity_ref":
        if not isinstance(value, str) or not value:
            return f"{field_name} must be entity_ref string"
    return None


def _proposal_field(proposal: Any, name: str) -> Any:
    if isinstance(proposal, dict):
        if name not in proposal:
            raise AgentContractError(f"proposal missing field: {name}")
        return proposal[name]
    if hasattr(proposal, name):
        return getattr(proposal, name)
    raise AgentContractError(f"proposal missing field: {name}")


def _proposal_optional_field(proposal: Any, name: str) -> Any:
    if isinstance(proposal, dict):
        return proposal.get(name)
    return getattr(proposal, name, None)


def _normalize_field_values(value: Any) -> list[tuple[str, Any]]:
    if not isinstance(value, list):
        raise AgentContractError("field_values must be list")
    out: list[tuple[str, Any]] = []
    for item in value:
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
            out.append((item[0], item[1]))
            continue
        if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str):
            out.append((item[0], item[1]))
            continue
        if isinstance(item, dict) and "tag" in item and "value" in item:
            tag = item["tag"]
            if not isinstance(tag, str):
                raise AgentContractError("field_values entries must have string tag")
            out.append((tag, item["value"]))
            continue
        if hasattr(item, "tag") and hasattr(item, "value"):
            tag = getattr(item, "tag")
            if not isinstance(tag, str):
                raise AgentContractError("field_values entries must have string tag")
            out.append((tag, getattr(item, "value")))
            continue
        raise AgentContractError("field_values entries must be pair or {tag,value} object")
    return out


def _normalize_entity_identity(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, list):
        raise AgentContractError("entity_identity must be dict or list")

    out: dict[str, Any] = {}
    for item in value:
        if isinstance(item, dict) and "name" in item and "value" in item:
            name = item["name"]
            if not isinstance(name, str) or not name:
                raise AgentContractError("entity_identity entries must have non-empty string name")
            if name in out:
                raise AgentContractError(f"entity_identity has duplicate name: {name}")
            out[name] = item["value"]
            continue
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


def _normalize_confidence(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AgentContractError("confidence must be float when provided")
    out = float(value)
    if not (0.0 <= out <= 1.0):
        raise AgentContractError("confidence must be in [0, 1]")
    return out
