"""PyReason adapter-local accept helper.

Bridges ``PyReasonSession.annotation_templates`` to
``Ledger.annotation_rows`` via the shared ``set_field()`` write path.

Each buffered fact is accepted through ``set_field()`` to obtain a real
``asrt_id``, then the ``pyreason/*`` annotation templates are
materialized with that ``asrt_id`` and appended to the Ledger.

``shared/*`` annotations are NOT written here. They are already
produced by ``set_field()`` → ``_annotation_rows_for_claim()``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from factpy.adapters.pyreason.session import PyReasonSession
from factpy.core.evidence.write_protocol import set_field
from factpy.core.protocol.tup_v1 import ENTITY_REF_PREFIX
from factpy.core.store.ledger import AnnotationRow, Ledger

_ANNOTATION_ORIGINS = {"observed", "derived"}


@dataclass
class AcceptResult:
    """Result of accepting a PyReasonSession into the Ledger."""

    node_asrt_ids: list[str] = field(default_factory=list)
    edge_asrt_ids: list[str] = field(default_factory=list)
    annotation_count: int = 0


def persist_pyreason_annotations(
    ledger: Ledger,
    run_id: str,
    store: Any,
    accept_result: Any,
) -> int:
    """Persist pending ``pyreason/*`` annotations after shared ``Store.accept()``."""
    if not isinstance(ledger, Ledger):
        raise ValueError("ledger must be a Ledger instance")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id must be non-empty string")

    pending_by_run = getattr(store, "_engine_pending_annotations", {})
    if not isinstance(pending_by_run, dict):
        return 0
    templates = pending_by_run.pop(run_id, [])
    if not isinstance(templates, list) or not templates:
        return 0

    written = getattr(accept_result, "written_assertions", [])
    if not isinstance(written, list) or not written:
        return 0
    # Build index -> asrt_id mapping from written assertions (F-PR-5)
    asrt_id_by_index: dict[int, str] = {}
    for idx, entry in enumerate(written):
        if not isinstance(entry, dict):
            continue
        aid = entry.get("asrt_id", "")
        if isinstance(aid, str) and aid and aid != "<dry_run>":
            asrt_id_by_index[idx] = aid
    if not asrt_id_by_index:
        return 0

    rows: list[AnnotationRow] = []
    for template in templates:
        if not _is_validated_pyreason_template(template):
            continue
        fact_index = template.get("fact_index", 0)
        asrt_id = asrt_id_by_index.get(fact_index if isinstance(fact_index, int) else 0)
        if asrt_id is None:
            continue
        rows.append(
            AnnotationRow(
                asrt_id=asrt_id,
                namespace=str(template["namespace"]),
                category=str(template["category"]),
                key=str(template["key"]),
                kind=str(template["kind"]),
                value=template["value"],
                origin=str(template["origin"]),
                derivation=template.get("derivation"),
            )
        )
    if not rows:
        return 0
    ledger.append_annotations(rows)
    return len(rows)


def accept_pyreason_session(ledger: Ledger, session: PyReasonSession) -> AcceptResult:
    """Accept all buffered facts from *session* into *ledger*."""
    if not isinstance(ledger, Ledger):
        raise ValueError("ledger must be a Ledger instance")
    if not isinstance(session, PyReasonSession):
        raise ValueError("session must be a PyReasonSession instance")

    pred_specs = _predicate_specs_by_id(session)
    asrt_id_map: dict[tuple[str, int], str] = {}
    node_asrt_ids: list[str] = []
    edge_asrt_ids: list[str] = []

    for idx, fact in enumerate(session.node_facts):
        pred_id = str(fact["pred_id"])
        pred_spec = pred_specs[pred_id]
        asrt_id = set_field(
            ledger,
            pred_id,
            _node_e_ref(str(fact["node_ref"]), pred_spec),
            _node_rest_terms(fact, pred_spec),
            dict(fact["meta"]),
        )
        asrt_id_map[("node", idx)] = asrt_id
        node_asrt_ids.append(asrt_id)

    for idx, fact in enumerate(session.edge_facts):
        pred_id = str(fact["pred_id"])
        pred_spec = pred_specs[pred_id]
        asrt_id = set_field(
            ledger,
            pred_id,
            _edge_from_e_ref(str(fact["from_ref"]), pred_spec),
            _edge_rest_terms(fact, pred_spec),
            dict(fact["meta"]),
        )
        asrt_id_map[("edge", idx)] = asrt_id
        edge_asrt_ids.append(asrt_id)

    pyreason_rows: list[AnnotationRow] = []
    for template in session.annotation_templates:
        if not _is_validated_pyreason_template(template):
            continue
        key = (str(template["fact_kind"]), int(template["fact_index"]))
        asrt_id = asrt_id_map.get(key)
        if asrt_id is None:
            continue
        pyreason_rows.append(
            AnnotationRow(
                asrt_id=asrt_id,
                namespace=str(template["namespace"]),
                category=str(template["category"]),
                key=str(template["key"]),
                kind=str(template["kind"]),
                value=template["value"],
                origin=str(template["origin"]),
                derivation=template.get("derivation"),
            )
        )

    if pyreason_rows:
        ledger.append_annotations(pyreason_rows)

    return AcceptResult(
        node_asrt_ids=node_asrt_ids,
        edge_asrt_ids=edge_asrt_ids,
        annotation_count=len(pyreason_rows),
    )


def _predicate_specs_by_id(session: PyReasonSession) -> dict[str, dict[str, Any]]:
    predicates = session._schema_ir.get("predicates", [])
    if not isinstance(predicates, list):
        raise ValueError("session schema_ir.predicates must be list")
    result: dict[str, dict[str, Any]] = {}
    for pred in predicates:
        if isinstance(pred, dict) and isinstance(pred.get("pred_id"), str):
            result[pred["pred_id"]] = pred
    return result


def _node_rest_terms(fact: dict[str, Any], pred_spec: dict[str, Any]) -> list[tuple[str, Any]]:
    arg_specs = pred_spec.get("arg_specs")
    if not isinstance(arg_specs, list) or len(arg_specs) < 2:
        raise ValueError(f"node predicate arg_specs invalid for {pred_spec.get('pred_id')}")
    value_spec = arg_specs[1]
    if not isinstance(value_spec, dict):
        raise ValueError(f"node value arg_spec invalid for {pred_spec.get('pred_id')}")
    value_tag = value_spec.get("type_domain")
    if not isinstance(value_tag, str) or not value_tag:
        raise ValueError(f"node value type_domain missing for {pred_spec.get('pred_id')}")
    return [(value_tag, fact["value"])]


def _edge_rest_terms(fact: dict[str, Any], pred_spec: dict[str, Any]) -> list[tuple[str, Any]]:
    arg_specs = pred_spec.get("arg_specs")
    if not isinstance(arg_specs, list) or len(arg_specs) < 3:
        raise ValueError(f"edge predicate arg_specs invalid for {pred_spec.get('pred_id')}")
    to_ref_spec = arg_specs[1]
    value_spec = arg_specs[2]
    if not isinstance(to_ref_spec, dict) or not isinstance(value_spec, dict):
        raise ValueError(f"edge arg_specs invalid for {pred_spec.get('pred_id')}")

    to_ref_value = _edge_to_ref_value(str(fact["to_ref"]), pred_spec, to_ref_spec.get("type_domain"))
    to_ref_tag = "entity_ref" if isinstance(to_ref_value, str) and to_ref_value.startswith(ENTITY_REF_PREFIX) else "string"
    value_tag = value_spec.get("type_domain")
    if not isinstance(value_tag, str) or not value_tag:
        raise ValueError(f"edge value type_domain missing for {pred_spec.get('pred_id')}")

    return [
        (to_ref_tag, to_ref_value),
        (value_tag, fact["value"]),
    ]


def _node_e_ref(node_ref: str, pred_spec: dict[str, Any]) -> str:
    return _materialize_entity_ref(node_ref, _entity_type_for_node(pred_spec))


def _edge_from_e_ref(from_ref: str, pred_spec: dict[str, Any]) -> str:
    return _materialize_entity_ref(from_ref, _entity_type_for_edge(pred_spec, "from_entity_type"))


def _edge_to_ref_value(to_ref: str, pred_spec: dict[str, Any], declared_tag: Any) -> str:
    if declared_tag == "entity_ref":
        return _materialize_entity_ref(to_ref, _entity_type_for_edge(pred_spec, "to_entity_type"))
    return to_ref


def _entity_type_for_node(pred_spec: dict[str, Any]) -> str:
    owner_type = pred_spec.get("owner_type")
    if isinstance(owner_type, str) and owner_type:
        return owner_type
    return "PyReasonNode"


def _entity_type_for_edge(pred_spec: dict[str, Any], key: str) -> str:
    entity_type = pred_spec.get(key)
    if isinstance(entity_type, str) and entity_type:
        return entity_type
    return "PyReasonNode"


def _is_validated_pyreason_template(template: Any) -> bool:
    if not isinstance(template, dict):
        return False
    if template.get("namespace") != "pyreason":
        return False
    _validate_template_origin(template)
    return True


def _validate_template_origin(template: dict[str, Any]) -> None:
    origin = template.get("origin")
    if origin not in _ANNOTATION_ORIGINS:
        raise ValueError(f"unsupported annotation origin in template: {origin!r}")
    derivation = template.get("derivation")
    if origin == "derived" and (not isinstance(derivation, str) or not derivation):
        raise ValueError("derived annotation template must include non-empty derivation")
    if derivation is not None and not isinstance(derivation, str):
        raise ValueError("annotation template derivation must be str when provided")


def _materialize_entity_ref(raw_ref: str, entity_type: str) -> str:
    if raw_ref.startswith(ENTITY_REF_PREFIX):
        return raw_ref
    return f"{ENTITY_REF_PREFIX}{entity_type}:{raw_ref}"
