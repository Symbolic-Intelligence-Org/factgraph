from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.evaluation_run_v1 import ProviderReceiptRefV1
from factgraph.application.protocol.goal_plan_v1 import GoalValueV1
from factgraph.application.protocol.relation_provider_v1 import (
    ProviderMaterializationError,
    ProviderMaterializationV1,
    ProviderRelationRowV1,
    ProviderRequestV1,
    RelationProviderV1,
    invoke_relation_provider_v1,
)


def _token(character: str) -> str:
    return f"sha256:{hashlib.sha256(character.encode('utf-8')).hexdigest()}"


def _request(
    provider: RelationProviderV1,
    *,
    dependencies: tuple[str, ...] = ("Person.age", "Person.skills"),
    supplied: tuple[str, ...] | None = None,
    bindings: tuple[tuple[str, GoalValueV1], ...] = (),
) -> ProviderRequestV1:
    return ProviderRequestV1(
        provider_digest=provider.provider_digest,
        query_digest=_token("q"),
        schema_digest=_token("s"),
        dependency_predicate_ids=dependencies,
        supplied_predicate_ids=provider.supplied_predicate_ids if supplied is None else supplied,
        bindings=bindings,
    )


def _provider(
    callback,
    *,
    supplied: tuple[str, ...] = ("Person.age",),
    required: tuple[str, ...] = (),
) -> RelationProviderV1:
    return RelationProviderV1(
        provider_id="lookup.people",
        version="1",
        kind="lookup",
        code_digest=_token("c"),
        required_binding_aliases=required,
        supplied_predicate_ids=supplied,
        materialize=callback,
    )


def _row(age: int, *, origin: str = "receipt-row") -> ProviderRelationRowV1:
    return ProviderRelationRowV1(
        "Person.age",
        (GoalValueV1("entity_ref", "idref_v1:Person:alice"), GoalValueV1("int", age)),
        origin,
    )


def test_request_records_full_dependencies_and_provider_subset_canonically() -> None:
    provider = _provider(lambda request: pytest.fail("not invoked"), supplied=("Person.age",))
    request = _request(
        provider,
        bindings=(
            ("z", GoalValueV1("string", "z")),
            ("a", GoalValueV1("string", "a")),
        ),
    )

    assert request.dependency_predicate_ids == ("Person.age", "Person.skills")
    assert request.supplied_predicate_ids == ("Person.age",)
    assert tuple(alias for alias, _ in request.bindings) == ("a", "z")
    assert request.request_digest.startswith("sha256:")

    with pytest.raises(ProtocolShapeError, match="subset"):
        _request(provider, supplied=("Person.unknown",))


def test_provider_subset_is_pinned_on_declaration_request_and_output() -> None:
    def materialize(request: ProviderRequestV1) -> ProviderMaterializationV1:
        return ProviderMaterializationV1(
            request.provider_digest,
            request.request_digest,
            "receipt:lookup:7",
            _token("r"),
            ("Person.skills",),
            (),
        )

    provider = _provider(materialize)
    request = _request(provider)
    with pytest.raises(ProviderMaterializationError) as error:
        invoke_relation_provider_v1(provider, request)
    assert error.value.code == "PROVIDER_MATERIALIZATION_COVERAGE_MISMATCH"

    mismatched_request = _request(provider, supplied=("Person.skills",))
    with pytest.raises(ProviderMaterializationError) as error:
        invoke_relation_provider_v1(provider, mismatched_request)
    assert error.value.code == "PROVIDER_REQUEST_SUPPLIED_PREDICATES_MISMATCH"


def test_provider_requires_declared_bindings_and_wraps_callback_errors() -> None:
    provider = _provider(
        lambda request: (_ for _ in ()).throw(RuntimeError("transport timed out")),
        required=("subject",),
    )
    with pytest.raises(ProviderMaterializationError) as error:
        invoke_relation_provider_v1(provider, _request(provider))
    assert error.value.code == "PROVIDER_REQUIRED_BINDING_MISSING"

    request = _request(
        provider,
        bindings=(("subject", GoalValueV1("entity_ref", "idref_v1:Person:alice")),),
    )
    with pytest.raises(ProviderMaterializationError) as error:
        invoke_relation_provider_v1(provider, request)
    assert error.value.code == "PROVIDER_MATERIALIZATION_FAILED"


def test_materialization_seals_opaque_receipt_and_bridges_run_receipt_ref() -> None:
    def materialize(request: ProviderRequestV1) -> ProviderMaterializationV1:
        return ProviderMaterializationV1(
            request.provider_digest,
            request.request_digest,
            "receipt:lookup:7",
            _token("r"),
            request.supplied_predicate_ids,
            (_row(30),),
        )

    provider = _provider(materialize)
    output = invoke_relation_provider_v1(provider, _request(provider))
    receipt = output.to_receipt_ref_v1()

    assert isinstance(receipt, ProviderReceiptRefV1)
    assert receipt.provider_digest == output.provider_digest
    assert receipt.request_digest == output.request_digest
    assert receipt.materialization_digest == output.materialization_digest
    assert receipt.receipt_digest == output.receipt_digest
    assert receipt.receipt_ref == output.receipt_ref

    changed_receipt = replace(output, receipt_digest=_token("x"))
    assert changed_receipt.materialization_digest != output.materialization_digest


def test_materialization_rejects_duplicate_logical_rows_even_with_distinct_origins() -> None:
    with pytest.raises(ProtocolShapeError, match="duplicate logical tuples"):
        ProviderMaterializationV1(
            _token("p"),
            _token("q"),
            "receipt:duplicate",
            _token("r"),
            ("Person.age",),
            (_row(30, origin="first"), _row(30, origin="second")),
        )


def test_provider_digest_commits_to_supplied_predicate_contract() -> None:
    left = _provider(lambda request: pytest.fail("not invoked"), supplied=("Person.age",))
    right = _provider(
        lambda request: pytest.fail("not invoked"),
        supplied=("Person.age", "Person.skills"),
    )
    assert left.provider_digest != right.provider_digest
