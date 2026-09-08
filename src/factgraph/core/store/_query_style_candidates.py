from __future__ import annotations

from typing import Any
from uuid import uuid4

from factgraph.core.derivation.candidates import DerivationOutput, make_derivation_output
from factgraph.core.evidence.write_protocol import now_epoch_nanos
from factgraph.core.protocol.digests import sha256_token
from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.core.store._builders import coerce_value_for_tag, resolve_head_ref
from factgraph.core.store._support import (
    ENGINE_NO_WITNESS_KIND,
    BindingSupportCapture,
    normalize_binding_items,
)


def query_style_derivation_outputs_from_bindings(
    store: Any,
    *,
    derivation_id: str,
    version: str,
    target_pred_id: str,
    head_vars: list[Any],
    rows: list[BindingSupportCapture] | None = None,
    bindings: list[dict[str, Any]] | None = None,
    confidence_kind_resolver: Any | None = None,
) -> list[DerivationOutput]:
    run_id = uuid4().hex
    binding_rows = _coerce_binding_rows(rows=rows, bindings=bindings)

    outputs: list[DerivationOutput] = []
    for row in binding_rows:
        binding = row.binding_dict()
        tagged_args = [_infer_query_style_tagged_arg(resolve_head_ref(head_ref, binding)) for head_ref in head_vars]
        key_terms = [("string", target_pred_id), *tagged_args]
        tup_digest = sha256_token(canonical_bytes_tup_v1(tagged_args))
        output = make_derivation_output(
            derivation_id=derivation_id,
            derivation_version=version,
            run_id=run_id,
            target=target_pred_id,
            key_terms=key_terms,
            payload={
                "pred_id": target_pred_id,
                "terms": [_term_from_tag_value(tag, value) for tag, value in tagged_args],
            },
            support_digest=row.support_digest,
            support_kind=row.support_kind,
            generated_at=now_epoch_nanos(),
            tup_digest=tup_digest,
            state="generated",
            candidate_kind="fact",
            confidence_kind=_resolve_confidence_kind(
                confidence_kind_resolver,
                row.support_digest,
                row.support_kind,
                store,
            ),
        )
        outputs.append(output)

    unique: dict[tuple[Any, ...], DerivationOutput] = {}
    for output in outputs:
        key = (output.candidate_kind, output.candidate_key)
        existing = unique.get(key)
        if existing is None or _support_is_better(output, existing):
            unique[key] = output
    if getattr(store, "_capture_all_query_style_supports", False):
        return sorted(
            outputs,
            key=lambda cand: (
                cand.candidate_kind,
                cand.candidate_key,
                cand.support_digest,
                cand.support_kind,
            ),
        )
    return sorted(unique.values(), key=lambda cand: (cand.candidate_kind, cand.candidate_key))


def _coerce_binding_rows(
    *,
    rows: list[BindingSupportCapture] | None,
    bindings: list[dict[str, Any]] | None,
) -> list[BindingSupportCapture]:
    if rows is not None and bindings is not None:
        raise ValueError("pass either rows or bindings, not both")
    if rows is not None:
        return list(rows)
    if bindings is None:
        raise ValueError("rows or bindings must be provided")
    return [
        BindingSupportCapture(
            binding_items=normalize_binding_items(binding),
            support_digest=f"sha256:{'0' * 64}",
            support_kind=ENGINE_NO_WITNESS_KIND,
        )
        for binding in bindings
    ]


def _infer_query_style_tagged_arg(value: Any) -> tuple[str, Any]:
    if isinstance(value, str) and value.startswith("idref_v1:"):
        return "entity_ref", coerce_value_for_tag("entity_ref", value)
    if isinstance(value, bool):
        return "bool", coerce_value_for_tag("bool", value)
    if isinstance(value, int):
        return "int", coerce_value_for_tag("int", value)
    if isinstance(value, float):
        return "float64", coerce_value_for_tag("float64", value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "bytes", coerce_value_for_tag("bytes", value)
    if isinstance(value, str):
        return "string", coerce_value_for_tag("string", value)
    raise WhereValidationError(f"unsupported query-style head value: {type(value).__name__}")


def _term_from_tag_value(tag: str, value: Any) -> dict[str, Any]:
    if tag == "entity_ref":
        if not isinstance(value, str) or not value:
            raise WhereValidationError("entity_ref value must be non-empty string")
        return {"kind": "entity_ref", "value": value}
    return {"kind": "literal", "tag": tag, "value": value}


def _resolve_confidence_kind(
    resolver: Any | None,
    support_digest: str,
    support_kind: str,
    store: Any,
) -> str:
    if resolver is None:
        return "none"
    return resolver.resolve(support_digest, support_kind, store._lookup_support_artifact)


def _support_is_better(output: DerivationOutput, existing: DerivationOutput) -> bool:
    if output.support_digest < existing.support_digest:
        return True
    if output.support_digest == existing.support_digest:
        return output.support_kind < existing.support_kind
    return False
