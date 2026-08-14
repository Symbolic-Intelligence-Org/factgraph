"""Runtime validation/materialization for restricted relation providers.

Provider code runs before this module is called.  The output is converted to
the same ``ProjectedFact`` representation used by the Scenario resolver and
the portable engine seam.  This module does not retain a provider callable,
perform network I/O, or consult a source Store.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

from factgraph.core.protocol.tup_v1 import canonical_bytes_tup_v1
from factgraph.core.store._support import ProjectedFact
from factgraph.core.schema.schema_ir import ensure_schema_ir

from .protocol.goal_plan_v1 import GoalValueV1
from .protocol.relation_provider_v1 import (
    ProviderMaterializationV1,
    ProviderRequestV1,
)


class ProviderRelationMaterializationError(ValueError):
    """A typed provider output cannot become a FactGraph relation."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def provider_materialization_to_relation_v1(
    materialization: ProviderMaterializationV1,
    *,
    schema_ir: dict[str, Any],
) -> Mapping[str, tuple[ProjectedFact, ...]]:
    """Validate and make an immutable exact predicate relation.

    An empty predicate is represented by its key and an empty tuple.  A
    missing key is therefore not silently read from a live Store later.
    """

    if not isinstance(materialization, ProviderMaterializationV1):
        raise ProviderRelationMaterializationError(
            "materialization must be ProviderMaterializationV1",
            code="PROVIDER_MATERIALIZATION_INVALID",
        )
    try:
        schema = ensure_schema_ir(schema_ir)
    except Exception as exc:
        raise ProviderRelationMaterializationError(
            "schema_ir is not valid",
            code="PROVIDER_SCHEMA_INVALID",
        ) from exc
    predicate_specs = _predicate_specs(schema)

    missing = tuple(
        pred_id for pred_id in materialization.predicate_ids if pred_id not in predicate_specs
    )
    if missing:
        raise ProviderRelationMaterializationError(
            "provider materialization references predicates outside the schema",
            code="PROVIDER_PREDICATE_UNKNOWN",
        )
    rows_by_predicate: dict[str, list[ProjectedFact]] = {
        pred_id: [] for pred_id in materialization.predicate_ids
    }
    seen_witnesses: set[str] = set()
    seen_tuples: dict[str, set[tuple[object, ...]]] = {
        pred_id: set() for pred_id in materialization.predicate_ids
    }
    for row in materialization.rows:
        tags = predicate_specs[row.predicate_id]
        if not tags or tags[0] != "entity_ref":
            raise ProviderRelationMaterializationError(
                "provider predicates require entity_ref as their first argument",
                code="PROVIDER_PREDICATE_CONTRACT_UNSUPPORTED",
            )
        if len(row.values) != len(tags):
            raise ProviderRelationMaterializationError(
                "provider row arity does not match the schema predicate",
                code="PROVIDER_ROW_ARITY_MISMATCH",
            )
        values: list[object] = []
        for expected_tag, typed in zip(tags, row.values, strict=True):
            if typed.tag != expected_tag:
                raise ProviderRelationMaterializationError(
                    "provider row value tag does not match the schema predicate",
                    code="PROVIDER_ROW_VALUE_DOMAIN_MISMATCH",
                )
            values.append(_raw_goal_value(typed))
        fact_tuple = tuple(values)
        if fact_tuple in seen_tuples[row.predicate_id]:
            # Logical relation semantics are set semantics.  Preserve evidence
            # multiplicity in a provider-owned receipt, not as duplicate input
            # rows to an engine.
            raise ProviderRelationMaterializationError(
                "provider materialization contains a duplicate logical tuple",
                code="PROVIDER_DUPLICATE_LOGICAL_TUPLE",
            )
        seen_tuples[row.predicate_id].add(fact_tuple)
        witness = f"provider:{row.row_digest}"
        if witness in seen_witnesses:  # defensive against a malformed digest implementation
            raise ProviderRelationMaterializationError(
                "provider materialization repeats a witness",
                code="PROVIDER_DUPLICATE_WITNESS",
            )
        seen_witnesses.add(witness)
        rows_by_predicate[row.predicate_id].append(ProjectedFact(witness, fact_tuple))

    return MappingProxyType(
        {
            predicate_id: tuple(
                sorted(
                    rows,
                    key=lambda item: _fact_sort_key(predicate_specs[predicate_id], item),
                )
            )
            for predicate_id, rows in sorted(rows_by_predicate.items())
        }
    )


def merge_provider_materialization_v1(
    baseline_relation: Mapping[str, Sequence[ProjectedFact]],
    *,
    request: ProviderRequestV1,
    materialization: ProviderMaterializationV1,
    schema_ir: dict[str, Any],
) -> Mapping[str, tuple[ProjectedFact, ...]]:
    """Replace one declared predicate subset in a sealed baseline relation.

    ``ProviderMaterializationV1`` is not a patch and it is not a second
    evidence source to union with the baseline.  For every predicate declared
    in ``request.supplied_predicate_ids`` it supplies the *entire* finite
    relation, including an explicit empty relation when no rows were found.
    All other dependencies retain their baseline rows.  This makes provider
    composition deterministic and prevents ambiguous duplicate tuples from
    silently acquiring two unrelated witnesses.

    The helper deliberately has no ``Store`` or callable argument.  Call
    ``invoke_relation_provider_v1`` first, then merge this already-materialized
    snapshot before Scenario resolution and before any engine is entered.
    """

    if not isinstance(request, ProviderRequestV1):
        raise ProviderRelationMaterializationError(
            "request must be ProviderRequestV1",
            code="PROVIDER_REQUEST_INVALID",
        )
    if not isinstance(materialization, ProviderMaterializationV1):
        raise ProviderRelationMaterializationError(
            "materialization must be ProviderMaterializationV1",
            code="PROVIDER_MATERIALIZATION_INVALID",
        )
    if (
        materialization.provider_digest != request.provider_digest
        or materialization.request_digest != request.request_digest
    ):
        raise ProviderRelationMaterializationError(
            "materialization is not sealed to the supplied provider request",
            code="PROVIDER_MATERIALIZATION_REQUEST_MISMATCH",
        )
    if materialization.predicate_ids != request.supplied_predicate_ids:
        raise ProviderRelationMaterializationError(
            "materialization does not cover exactly the requested provider predicate subset",
            code="PROVIDER_MATERIALIZATION_COVERAGE_MISMATCH",
        )
    try:
        schema = ensure_schema_ir(schema_ir)
    except Exception as exc:
        raise ProviderRelationMaterializationError(
            "schema_ir is not valid",
            code="PROVIDER_SCHEMA_INVALID",
        ) from exc
    predicate_specs = _predicate_specs(schema)
    baseline = _normalize_baseline_relation(
        baseline_relation,
        dependency_predicate_ids=request.dependency_predicate_ids,
        predicate_specs=predicate_specs,
    )
    supplied = provider_materialization_to_relation_v1(materialization, schema_ir=schema)
    # The conversion above establishes that all provider keys are real schema
    # predicates.  This second subset check is still necessary because a
    # well-formed provider output could name a schema predicate that this
    # particular Query did not admit as a dependency.
    unexpected = tuple(sorted(set(supplied) - set(request.dependency_predicate_ids)))
    if unexpected:
        raise ProviderRelationMaterializationError(
            "provider supplied predicates outside this Query's dependency relation",
            code="PROVIDER_SUPPLIED_PREDICATE_NOT_DEPENDENCY",
        )

    merged: dict[str, tuple[ProjectedFact, ...]] = {}
    seen_witnesses: set[str] = set()
    for predicate_id in request.dependency_predicate_ids:
        # Replacement is intentional: no baseline/provider union is allowed.
        rows = supplied[predicate_id] if predicate_id in supplied else baseline[predicate_id]
        for row in rows:
            if row.asrt_id in seen_witnesses:
                raise ProviderRelationMaterializationError(
                    "merged relation repeats an assertion witness",
                    code="PROVIDER_MERGED_DUPLICATE_WITNESS",
                )
            seen_witnesses.add(row.asrt_id)
        merged[predicate_id] = rows
    return MappingProxyType(merged)


def _predicate_specs(schema: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    predicate_specs: dict[str, tuple[str, ...]] = {}
    for raw in schema["predicates"]:
        if not isinstance(raw, dict):  # pragma: no cover: schema validator owns this
            continue
        pred_id = raw.get("pred_id")
        arg_specs = raw.get("arg_specs")
        if not isinstance(pred_id, str) or not isinstance(arg_specs, list):
            continue
        try:
            tags = tuple(str(arg["type_domain"]) for arg in arg_specs)
        except (KeyError, TypeError) as exc:  # pragma: no cover: schema validator owns this
            raise ProviderRelationMaterializationError(
                "schema predicate has invalid arg specs",
                code="PROVIDER_SCHEMA_INVALID",
            ) from exc
        predicate_specs[pred_id] = tags
    return predicate_specs


def _normalize_baseline_relation(
    relation: Mapping[str, Sequence[ProjectedFact]],
    *,
    dependency_predicate_ids: tuple[str, ...],
    predicate_specs: Mapping[str, tuple[str, ...]],
) -> Mapping[str, tuple[ProjectedFact, ...]]:
    if not isinstance(relation, Mapping):
        raise ProviderRelationMaterializationError(
            "baseline_relation must be a mapping",
            code="PROVIDER_BASELINE_RELATION_INVALID",
        )
    expected = set(dependency_predicate_ids)
    actual = set(relation)
    if actual != expected:
        raise ProviderRelationMaterializationError(
            "baseline relation must exactly cover the Query dependency inventory",
            code="PROVIDER_BASELINE_RELATION_INVENTORY_MISMATCH",
        )
    normalized: dict[str, tuple[ProjectedFact, ...]] = {}
    seen_witnesses: set[str] = set()
    for predicate_id in dependency_predicate_ids:
        tags = predicate_specs.get(predicate_id)
        if tags is None or not tags or tags[0] != "entity_ref":
            raise ProviderRelationMaterializationError(
                "baseline relation predicate violates the provider relation contract",
                code="PROVIDER_PREDICATE_CONTRACT_UNSUPPORTED",
            )
        rows = relation[predicate_id]
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
            raise ProviderRelationMaterializationError(
                "baseline relation rows must be a sequence",
                code="PROVIDER_BASELINE_RELATION_ROWS_INVALID",
            )
        copied: list[ProjectedFact] = []
        for row in rows:
            if not isinstance(row, ProjectedFact) or len(row.fact_tuple) != len(tags):
                raise ProviderRelationMaterializationError(
                    "baseline relation row does not match the schema predicate",
                    code="PROVIDER_BASELINE_RELATION_ROW_INVALID",
                )
            try:
                canonical_bytes_tup_v1(list(zip(tags, row.fact_tuple, strict=True)))
            except (TypeError, ValueError) as exc:
                raise ProviderRelationMaterializationError(
                    "baseline relation row is not canonical for the schema predicate",
                    code="PROVIDER_BASELINE_RELATION_VALUE_INVALID",
                ) from exc
            if row.asrt_id in seen_witnesses:
                raise ProviderRelationMaterializationError(
                    "baseline relation repeats an assertion witness",
                    code="PROVIDER_BASELINE_DUPLICATE_WITNESS",
                )
            seen_witnesses.add(row.asrt_id)
            copied.append(ProjectedFact(row.asrt_id, tuple(row.fact_tuple)))
        normalized[predicate_id] = tuple(
            sorted(copied, key=lambda item: _fact_sort_key(tags, item))
        )
    return MappingProxyType(normalized)


def _fact_sort_key(value_tags: tuple[str, ...], row: ProjectedFact) -> tuple[bytes, str]:
    try:
        encoded = canonical_bytes_tup_v1(list(zip(value_tags, row.fact_tuple, strict=True)))
    except (TypeError, ValueError) as exc:  # callers validate with a stable code first
        raise ProviderRelationMaterializationError(
            "relation row is not canonical for its schema predicate",
            code="PROVIDER_ROW_VALUE_INVALID",
        ) from exc
    return encoded, row.asrt_id


def _raw_goal_value(value: GoalValueV1) -> object:
    """Invert the JSON-safe goal codec for the ordinary ledger write codec."""

    if value.tag != "bytes":
        return value.value
    assert isinstance(value.value, str)
    try:
        padding = "=" * (-len(value.value) % 4)
        return base64.urlsafe_b64decode((value.value + padding).encode("ascii"))
    except (
        UnicodeEncodeError,
        binascii.Error,
        ValueError,
    ) as exc:  # constructor already rejects this
        raise ProviderRelationMaterializationError(
            "provider bytes value is not canonical base64url",
            code="PROVIDER_ROW_VALUE_INVALID",
        ) from exc


__all__ = [
    "ProviderRelationMaterializationError",
    "merge_provider_materialization_v1",
    "provider_materialization_to_relation_v1",
]
