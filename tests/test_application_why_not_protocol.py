"""Why-not Universe Diagnose protocol shape tests (blueprint §7.2 + §8 Step 1)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
import typing
import unittest
from dataclasses import FrozenInstanceError

from factgraph.application import protocol as protocol_pkg
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    ErrorDTO,
    EvidenceEnvelope,
    ProtocolShapeError,
    WhyNotAtomLocator,
    WhyNotEngine,
    WhyNotFailureKind,
    WhyNotRedRow,
    WhyNotRowDiagnostic,
    WhyNotRowGranularity,
    WhyNotRowStatus,
    WhyNotStatus,
    WhyNotUniverseRequest,
    WhyNotUniverseResult,
)
from factgraph.application.protocol import derivation_why_not as why_not_protocol
from factgraph.core.store._support import ProvenanceEnvelope, SupportArtifact


def _head(
    target: str = "doc:eligible", vars_: tuple[str, ...] = ("$doc",)
) -> CompiledHeadCall:
    return CompiledHeadCall(target_pred_id=target, head_var_names=vars_)


def _plan(
    *,
    heads: tuple[CompiledHeadCall, ...] | None = None,
    head_vars: tuple[str, ...] = ("$doc",),
) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="drv.why_not",
        version="1.0",
        body_ir=[("pred", "doc:risk", ["$doc", "$risk"]), ("eq", "$risk", "high")],
        heads=heads if heads is not None else (_head(vars_=head_vars),),
    )


def _binding(doc_id: str = "d-1") -> tuple[tuple[str, object], ...]:
    return (("$doc", doc_id),)


def _unsorted_binding() -> tuple[tuple[str, object], ...]:
    return (("$risk", "high"), ("$doc", "d-1"))


def _two_var_binding(doc_id: str = "d-1") -> tuple[tuple[str, object], ...]:
    return (("$doc", doc_id), ("$risk", "high"))


def _attempted_binding() -> tuple[tuple[str, object], ...]:
    return (("$doc", "d-1"), ("$risk", "high"))


def _error(code: str = "WHY_NOT_UNSUPPORTED") -> ErrorDTO:
    return ErrorDTO(code=code, message="why-not unavailable")


def _atom_locator(**kwargs: object) -> WhyNotAtomLocator:
    fields = {
        "branch_index": 0,
        "failed_atom_index": 1,
        "attempted_binding": _attempted_binding(),
    }
    fields.update(kwargs)
    return WhyNotAtomLocator(**fields)  # type: ignore[arg-type]


def _diagnostic(**kwargs: object) -> WhyNotRowDiagnostic:
    fields = {
        "status": "failed",
        "failure_kind": "no_candidate",
        "diagnostic_granularity": "coarse",
        "atom_locator": None,
    }
    fields.update(kwargs)
    return WhyNotRowDiagnostic(**fields)  # type: ignore[arg-type]


def _red_row(
    binding: tuple[tuple[str, object], ...] = _binding("d-2"),
    diagnostic: WhyNotRowDiagnostic | None = None,
) -> WhyNotRedRow:
    return WhyNotRedRow(binding=binding, diagnostic=diagnostic or _diagnostic())


class WhyNotAtomLocatorProtocolTests(unittest.TestCase):
    def test_atom_locator_construction(self) -> None:
        locator = _atom_locator()
        self.assertEqual(locator.branch_index, 0)
        self.assertEqual(locator.failed_atom_index, 1)
        self.assertEqual(locator.attempted_binding, _attempted_binding())

    def test_atom_locator_normalizes_attempted_binding(self) -> None:
        locator = _atom_locator(attempted_binding=_unsorted_binding())
        self.assertEqual(locator.attempted_binding, _attempted_binding())

    def test_atom_locator_rejects_negative_indexes(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _atom_locator(branch_index=-1)
        with self.assertRaises(ProtocolShapeError):
            _atom_locator(failed_atom_index=-1)

    def test_atom_locator_rejects_bool_indexes(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _atom_locator(branch_index=True)
        with self.assertRaises(ProtocolShapeError):
            _atom_locator(failed_atom_index=False)

    def test_atom_locator_rejects_invalid_binding(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _atom_locator(attempted_binding=(("doc", "d-1"),))

    def test_atom_locator_is_frozen(self) -> None:
        locator = _atom_locator()
        with self.assertRaises(FrozenInstanceError):
            locator.branch_index = 2  # type: ignore[misc]


class WhyNotUniverseRequestProtocolTests(unittest.TestCase):
    """§7-WhyNot-1 / 2 / 3 / 4 / 5 request-shape gates."""

    def test_request_construction(self) -> None:
        request = WhyNotUniverseRequest(
            plan=_plan(),
            candidate_universe=(_binding("d-1"), _binding("d-2")),
            engine="native",
        )
        self.assertEqual(request.candidate_universe, (_binding("d-1"), _binding("d-2")))
        self.assertEqual(request.engine, "native")

    def test_request_normalizes_universe_bindings(self) -> None:
        request = WhyNotUniverseRequest(
            plan=_plan(head_vars=("$doc", "$risk")),
            candidate_universe=(_unsorted_binding(),),
            engine="native",
        )
        self.assertEqual(request.candidate_universe, (_two_var_binding(),))

    def test_empty_universe_is_allowed(self) -> None:
        request = WhyNotUniverseRequest(plan=_plan(), candidate_universe=(), engine="native")
        self.assertEqual(request.candidate_universe, ())

    def test_request_ignores_literal_head_args_for_binding_coverage(self) -> None:
        request = WhyNotUniverseRequest(
            plan=_plan(head_vars=("$doc", "age_role")),
            candidate_universe=(_binding(),),
            engine="native",
        )
        self.assertEqual(request.candidate_universe, (_binding(),))

    def test_request_allows_literal_only_head_with_empty_binding(self) -> None:
        request = WhyNotUniverseRequest(
            plan=_plan(head_vars=("age_role",)),
            candidate_universe=((),),
            engine="native",
        )
        self.assertEqual(request.candidate_universe, ((),))

    def test_request_rejects_non_plan(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseRequest(
                plan=object(),  # type: ignore[arg-type]
                candidate_universe=(),
                engine="native",
            )

    def test_request_rejects_multi_head_plan(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseRequest(
                plan=_plan(heads=(_head("doc:a"), _head("doc:b"))),
                candidate_universe=(_binding(),),
                engine="native",
            )

    def test_request_rejects_missing_head_variable(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseRequest(
                plan=_plan(head_vars=("$doc", "$risk")),
                candidate_universe=(_binding(),),
                engine="native",
            )

    def test_request_rejects_extra_or_body_only_variable(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseRequest(
                plan=_plan(),
                candidate_universe=(_two_var_binding(),),
                engine="native",
            )

    def test_request_rejects_duplicate_universe_bindings(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseRequest(
                plan=_plan(),
                candidate_universe=(_binding("d-1"), _binding("d-1")),
                engine="native",
            )

    def test_request_rejects_duplicate_unhashable_universe_bindings(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseRequest(
                plan=_plan(),
                candidate_universe=((("$doc", ["d-1"]),), (("$doc", ["d-1"]),)),
                engine="native",
            )

    def test_request_rejects_duplicate_binding_variables(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseRequest(
                plan=_plan(),
                candidate_universe=((("$doc", "d-1"), ("$doc", "d-2")),),
                engine="native",
            )

    def test_request_rejects_duplicate_dollar_head_vars(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseRequest(
                plan=_plan(head_vars=("$doc", "$doc")),
                candidate_universe=(_binding(),),
                engine="native",
            )

    def test_request_accepts_unhashable_binding_values(self) -> None:
        request = WhyNotUniverseRequest(
            plan=_plan(),
            candidate_universe=((("$doc", ["d-1"]),),),
            engine="native",
        )
        self.assertEqual(request.candidate_universe, ((("$doc", ["d-1"]),),))

    def test_request_rejects_invalid_engine(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseRequest(
                plan=_plan(),
                candidate_universe=(),
                engine="lambda",  # type: ignore[arg-type]
            )

    def test_request_engine_has_no_default(self) -> None:
        with self.assertRaises(TypeError):
            WhyNotUniverseRequest(plan=_plan(), candidate_universe=())  # type: ignore[call-arg]

    def test_request_rejects_side_channel_and_escape_fields(self) -> None:
        banned_fields = (
            "store",
            "registry",
            "search_budget",
            "limit",
            "max_candidates",
            "mode",
            "diagnostic_mode",
            "engine_options",
            "run_id",
            "green",
        )
        for field_name in banned_fields:
            with self.subTest(field_name=field_name):
                with self.assertRaises(TypeError):
                    WhyNotUniverseRequest(
                        plan=_plan(),
                        candidate_universe=(),
                        engine="native",
                        **{field_name: object()},
                    )

    def test_request_is_frozen(self) -> None:
        request = WhyNotUniverseRequest(plan=_plan(), candidate_universe=(), engine="native")
        with self.assertRaises(FrozenInstanceError):
            request.engine = "souffle"  # type: ignore[misc]


class WhyNotRowDiagnosticProtocolTests(unittest.TestCase):
    """§7-WhyNot-10 / 11 row diagnostic matrix."""

    def test_failed_no_candidate_coarse_construction(self) -> None:
        diagnostic = _diagnostic()
        self.assertEqual(diagnostic.status, "failed")
        self.assertEqual(diagnostic.failure_kind, "no_candidate")
        self.assertEqual(diagnostic.diagnostic_granularity, "coarse")
        self.assertIsNone(diagnostic.atom_locator)

    def test_failed_atom_localized_construction(self) -> None:
        diagnostic = _diagnostic(
            failure_kind="atom_localized",
            diagnostic_granularity="atom_localized",
            atom_locator=_atom_locator(),
        )
        self.assertEqual(diagnostic.failure_kind, "atom_localized")
        self.assertIsInstance(diagnostic.atom_locator, WhyNotAtomLocator)

    def test_unsupported_unavailable_construction(self) -> None:
        diagnostic = _diagnostic(
            status="unsupported",
            failure_kind=None,
            diagnostic_granularity="unavailable",
            atom_locator=None,
            errors=(_error(),),
        )
        self.assertEqual(diagnostic.status, "unsupported")
        self.assertEqual(diagnostic.diagnostic_granularity, "unavailable")

    def test_rejects_invalid_row_status(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(status="passed")
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(status="invalid_request")

    def test_failed_requires_failure_kind(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(failure_kind=None)

    def test_failed_rejects_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(errors=(_error(),))

    def test_failed_no_candidate_requires_coarse_without_locator(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(diagnostic_granularity="atom_localized")
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(atom_locator=_atom_locator())

    def test_failed_atom_localized_requires_locator_and_granularity(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(failure_kind="atom_localized", diagnostic_granularity="coarse")
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(
                failure_kind="atom_localized",
                diagnostic_granularity="atom_localized",
                atom_locator=None,
            )

    def test_unsupported_requires_unavailable_error_and_no_locator(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(
                status="unsupported",
                failure_kind=None,
                diagnostic_granularity="coarse",
                errors=(_error(),),
            )
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(
                status="unsupported",
                failure_kind=None,
                diagnostic_granularity="unavailable",
                errors=(),
            )
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(
                status="unsupported",
                failure_kind=None,
                diagnostic_granularity="unavailable",
                atom_locator=_atom_locator(),
                errors=(_error(),),
            )

    def test_diagnostic_requires_tuple_errors_and_warnings(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(errors=[_error()])
        with self.assertRaises(ProtocolShapeError):
            _diagnostic(warnings=[object()])

    def test_diagnostic_is_frozen(self) -> None:
        diagnostic = _diagnostic()
        with self.assertRaises(FrozenInstanceError):
            diagnostic.status = "unsupported"  # type: ignore[misc]


class WhyNotRedRowProtocolTests(unittest.TestCase):
    def test_red_row_construction(self) -> None:
        row = _red_row()
        self.assertEqual(row.binding, _binding("d-2"))
        self.assertEqual(row.diagnostic, _diagnostic())

    def test_red_row_normalizes_binding(self) -> None:
        row = _red_row(binding=_unsorted_binding())
        self.assertEqual(row.binding, _attempted_binding())

    def test_red_row_rejects_invalid_binding(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _red_row(binding=(("doc", "d-1"),))

    def test_red_row_requires_why_not_diagnostic(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotRedRow(binding=_binding(), diagnostic=object())  # type: ignore[arg-type]

    def test_red_row_is_frozen(self) -> None:
        row = _red_row()
        with self.assertRaises(FrozenInstanceError):
            row.binding = _binding("d-3")  # type: ignore[misc]


class WhyNotUniverseResultProtocolTests(unittest.TestCase):
    """§7-WhyNot-5 / 6 / 7 result status and partition gates."""

    def test_completed_partition_construction(self) -> None:
        result = WhyNotUniverseResult(
            status="completed",
            requested_universe=(_binding("d-1"), _binding("d-2")),
            green=(_binding("d-1"),),
            red=(_red_row(_binding("d-2")),),
        )
        self.assertEqual(result.green, (_binding("d-1"),))
        self.assertEqual(result.red[0].binding, _binding("d-2"))

    def test_completed_partition_accepts_unhashable_binding_values(self) -> None:
        result = WhyNotUniverseResult(
            status="completed",
            requested_universe=((("$doc", ["d-1"]),),),
            green=((("$doc", ["d-1"]),),),
            red=(),
        )
        self.assertEqual(result.green, ((("$doc", ["d-1"]),),))

    def test_completed_empty_universe_construction(self) -> None:
        result = WhyNotUniverseResult(
            status="completed",
            requested_universe=(),
            green=(),
            red=(),
        )
        self.assertEqual(result.green, ())
        self.assertEqual(result.red, ())

    def test_completed_rejects_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="completed",
                requested_universe=(),
                green=(),
                red=(),
                errors=(_error(),),
            )

    def test_completed_requires_green_red_cover_requested_universe(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="completed",
                requested_universe=(_binding("d-1"), _binding("d-2")),
                green=(_binding("d-1"),),
                red=(),
            )

    def test_completed_rejects_overlap(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="completed",
                requested_universe=(_binding("d-1"),),
                green=(_binding("d-1"),),
                red=(_red_row(_binding("d-1")),),
            )

    def test_completed_rejects_order_drift(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="completed",
                requested_universe=(_binding("d-1"), _binding("d-2")),
                green=(_binding("d-2"), _binding("d-1")),
                red=(),
            )

    def test_completed_rejects_duplicate_green_or_red(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="completed",
                requested_universe=(_binding("d-1"),),
                green=(_binding("d-1"), _binding("d-1")),
                red=(),
            )
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="completed",
                requested_universe=(_binding("d-1"),),
                green=(),
                red=(_red_row(_binding("d-1")), _red_row(_binding("d-1"))),
            )

    def test_completed_rejects_duplicate_unhashable_green_or_red(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="completed",
                requested_universe=((("$doc", ["d-1"]),),),
                green=((("$doc", ["d-1"]),), (("$doc", ["d-1"]),)),
                red=(),
            )
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="completed",
                requested_universe=((("$doc", ["d-1"]),),),
                green=(),
                red=(
                    _red_row((("$doc", ["d-1"]),)),
                    _red_row((("$doc", ["d-1"]),)),
                ),
            )

    def test_unsupported_nullable_matrix(self) -> None:
        result = WhyNotUniverseResult(
            status="unsupported",
            requested_universe=(_binding("d-1"),),
            green=(),
            red=(),
            errors=(_error("BINDING_EXTRACTION_NOT_SUPPORTED"),),
        )
        self.assertEqual(result.status, "unsupported")
        self.assertEqual(result.green, ())
        self.assertEqual(result.red, ())

    def test_invalid_request_nullable_matrix(self) -> None:
        result = WhyNotUniverseResult(
            status="invalid_request",
            requested_universe=(),
            green=(),
            red=(),
            errors=(_error("DUPLICATE_CANDIDATE_UNIVERSE_BINDING"),),
        )
        self.assertEqual(result.status, "invalid_request")

    def test_non_completed_requires_empty_board_and_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="unsupported",
                requested_universe=(_binding("d-1"),),
                green=(_binding("d-1"),),
                red=(),
                errors=(_error(),),
            )
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="invalid_request",
                requested_universe=(_binding("d-1"),),
                green=(),
                red=(_red_row(),),
                errors=(_error(),),
            )
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="unsupported",
                requested_universe=(_binding("d-1"),),
                green=(),
                red=(),
            )

    def test_result_rejects_invalid_status(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="passed",  # type: ignore[arg-type]
                requested_universe=(),
                green=(),
                red=(),
                errors=(_error(),),
            )

    def test_result_requires_red_rows(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            WhyNotUniverseResult(
                status="completed",
                requested_universe=(_binding("d-1"),),
                green=(),
                red=(_binding("d-1"),),  # type: ignore[arg-type]
            )

    def test_result_is_frozen(self) -> None:
        result = WhyNotUniverseResult(
            status="completed",
            requested_universe=(),
            green=(),
            red=(),
        )
        with self.assertRaises(FrozenInstanceError):
            result.status = "unsupported"  # type: ignore[misc]


class WhyNotProtocolStaticInvariantTests(unittest.TestCase):
    """§7-WhyNot-1 / 2 / 8 / 10 / 11 static protocol invariants."""

    def test_status_literal_exact_members(self) -> None:
        self.assertEqual(
            set(typing.get_args(WhyNotStatus)),
            {"completed", "unsupported", "invalid_request"},
        )

    def test_engine_literal_exact_members(self) -> None:
        self.assertEqual(
            set(typing.get_args(WhyNotEngine)),
            {"native", "souffle", "problog", "pyreason"},
        )

    def test_row_status_literal_exact_members(self) -> None:
        self.assertEqual(set(typing.get_args(WhyNotRowStatus)), {"failed", "unsupported"})

    def test_failure_kind_literal_exact_members(self) -> None:
        self.assertEqual(
            set(typing.get_args(WhyNotFailureKind)),
            {"no_candidate", "atom_localized"},
        )

    def test_row_granularity_literal_exact_members(self) -> None:
        self.assertEqual(
            set(typing.get_args(WhyNotRowGranularity)),
            {"atom_localized", "coarse", "unavailable"},
        )

    def test_request_dataclass_fields_are_intent_only(self) -> None:
        self.assertEqual(
            [field.name for field in dataclasses.fields(WhyNotUniverseRequest)],
            ["plan", "candidate_universe", "engine"],
        )

    def test_result_dataclass_fields_match_frozen_contract(self) -> None:
        self.assertEqual(
            [field.name for field in dataclasses.fields(WhyNotUniverseResult)],
            ["status", "requested_universe", "green", "red", "errors", "warnings"],
        )
        self.assertEqual(
            [field.name for field in dataclasses.fields(WhyNotRedRow)],
            ["binding", "diagnostic"],
        )
        self.assertEqual(
            [field.name for field in dataclasses.fields(WhyNotRowDiagnostic)],
            [
                "status",
                "failure_kind",
                "diagnostic_granularity",
                "atom_locator",
                "errors",
                "warnings",
            ],
        )

    def test_protocol_module_does_not_expose_sibling_or_payload_dtos(self) -> None:
        banned_names = (
            "DiagnoseResult",
            "DiagnoseAtomLocator",
            "CheckRequest",
            "CheckResult",
            "EvidenceEnvelope",
            "SupportArtifact",
            "ProvenanceEnvelope",
        )
        for name in banned_names:
            with self.subTest(name=name):
                self.assertFalse(hasattr(why_not_protocol, name))

    def test_protocol_module_has_no_banned_imports_or_annotations(self) -> None:
        source = Path(why_not_protocol.__file__).read_text()
        tree = ast.parse(source)
        banned_names = {
            "DiagnoseResult",
            "DiagnoseAtomLocator",
            "CheckRequest",
            "CheckResult",
            "EvidenceEnvelope",
            "SupportArtifact",
            "ProvenanceEnvelope",
        }
        imported_names: set[str] = set()
        annotation_names: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    imported_names.add(alias.name.rsplit(".", maxsplit=1)[-1])
                    if alias.asname:
                        imported_names.add(alias.asname)
                continue
            annotation = getattr(node, "annotation", None)
            if annotation is not None:
                for child in ast.walk(annotation):
                    if isinstance(child, ast.Name):
                        annotation_names.add(child.id)
                    elif isinstance(child, ast.Attribute):
                        annotation_names.add(child.attr)
                    elif isinstance(child, ast.Constant) and isinstance(child.value, str):
                        annotation_names.update(banned for banned in banned_names if banned in child.value)

        self.assertFalse(imported_names & banned_names)
        self.assertFalse(annotation_names & banned_names)

    def test_why_not_atom_locator_not_evidence_engine_payload(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            EvidenceEnvelope(
                engine="native",
                support_kind="native_binding_v1",
                support_digest="sha256:" + ("1" * 64),
                branch_index=0,
                engine_payload=_atom_locator(),  # type: ignore[arg-type]
            )

    def test_evidence_envelope_existing_payload_types_unchanged(self) -> None:
        support = SupportArtifact(
            kind="native_binding_v1",
            root_result_kind="fact",
            binding_items=_binding(),
            pred_witnesses=(),
        )
        provenance = ProvenanceEnvelope(
            candidate_id="cand_v2:why-not-test",
            engine="problog",
            payload_type="proof_graph",
            payload={"nodes": []},
        )
        self.assertIsInstance(
            EvidenceEnvelope(
                engine="native",
                support_kind="native_binding_v1",
                support_digest="sha256:" + ("1" * 64),
                branch_index=0,
                engine_payload=support,
            ).engine_payload,
            SupportArtifact,
        )
        self.assertIsInstance(
            EvidenceEnvelope(
                engine="problog",
                support_kind="problog_provenance_v1",
                support_digest="sha256:" + ("2" * 64),
                branch_index=None,
                engine_payload=provenance,
            ).engine_payload,
            ProvenanceEnvelope,
        )

    def test_protocol_package_exports_why_not_dtos(self) -> None:
        self.assertIs(protocol_pkg.WhyNotUniverseRequest, WhyNotUniverseRequest)
        self.assertIs(protocol_pkg.WhyNotUniverseResult, WhyNotUniverseResult)
        self.assertIs(protocol_pkg.WhyNotRedRow, WhyNotRedRow)
        self.assertIs(protocol_pkg.WhyNotRowDiagnostic, WhyNotRowDiagnostic)
        self.assertIs(protocol_pkg.WhyNotAtomLocator, WhyNotAtomLocator)
        self.assertIs(protocol_pkg.WhyNotStatus, WhyNotStatus)
        self.assertIs(protocol_pkg.WhyNotEngine, WhyNotEngine)
        self.assertIs(protocol_pkg.WhyNotRowStatus, WhyNotRowStatus)
        self.assertIs(protocol_pkg.WhyNotRowGranularity, WhyNotRowGranularity)
        self.assertIs(protocol_pkg.WhyNotFailureKind, WhyNotFailureKind)


if __name__ == "__main__":
    unittest.main()
