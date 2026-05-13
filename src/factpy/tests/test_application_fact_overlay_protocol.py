"""Fact Overlay protocol shape tests (blueprint §7.2 + §8 Step 2)."""

from __future__ import annotations

import dataclasses
import typing
import unittest
from dataclasses import FrozenInstanceError

from factpy.application import protocol as protocol_pkg
from factpy.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    ErrorDTO,
    EvaluationOverlay,
    FactOverlayCheckRequest,
    FactOverlayCheckResult,
    FactRemoveAction,
    FactValueOverride,
    OverlayCheckDiff,
    OverlayCheckEngine,
    OverlayCheckPhase,
    OverlayCheckPhaseStatus,
    OverlayCheckStatus,
    ProtocolShapeError,
    RuleDisableAction,
    RuleLiteralPath,
    RuleLiteralReplaceAction,
)
from factpy.application.protocol import derivation_fact_overlay as overlay_protocol


def _head(target: str = "doc:eligible", vars_: tuple[str, ...] = ("$doc",)) -> CompiledHeadCall:
    return CompiledHeadCall(target_pred_id=target, head_var_names=vars_)


def _plan(*, heads: tuple[CompiledHeadCall, ...] | None = None) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="drv.overlay",
        version="1.0",
        body_ir=[("pred", "doc:risk", ["$doc", "$risk"]), ("eq", "$risk", "high")],
        heads=heads if heads is not None else (_head(),),
    )


def _binding() -> tuple[tuple[str, object], ...]:
    return (("$doc", "d-1"), ("$risk", "high"))


def _partial_binding() -> tuple[tuple[str, object], ...]:
    return (("$doc", "d-1"),)


def _override(**kwargs: object) -> FactValueOverride:
    fields = {
        "asrt_id": "asrt-1",
        "pred_id": "doc:risk",
        "e_ref": "doc-1",
        "old_fact_tuple": ("doc-1", "low"),
        "new_fact_tuple": ("doc-1", "high"),
    }
    fields.update(kwargs)
    return FactValueOverride(**fields)  # type: ignore[arg-type]


def _remove(**kwargs: object) -> FactRemoveAction:
    fields = {
        "asrt_id": "asrt-1",
        "pred_id": "doc:risk",
        "e_ref": "doc-1",
        "old_fact_tuple": ("doc-1", "low"),
    }
    fields.update(kwargs)
    return FactRemoveAction(**fields)  # type: ignore[arg-type]


def _disable(**kwargs: object) -> RuleDisableAction:
    fields = {
        "rule_id": "person.eligible",
        "version": "1.0",
        "branch_index": 0,
        "atom_index": 1,
    }
    fields.update(kwargs)
    return RuleDisableAction(**fields)  # type: ignore[arg-type]


def _replace_rule_literal(**kwargs: object) -> RuleLiteralReplaceAction:
    fields = {
        "rule_id": "person.eligible",
        "version": "1.0",
        "branch_index": 0,
        "atom_index": 3,
        "literal_path": RuleLiteralPath(kind="rhs"),
        "old_literal": "us",
        "new_literal": "eu",
    }
    fields.update(kwargs)
    return RuleLiteralReplaceAction(**fields)  # type: ignore[arg-type]


_DEFAULT_MATCHED_BINDING = object()


def _phase(
    *,
    status: OverlayCheckStatus = "passed",
    matched_count: int = 1,
    matched_binding: object = _DEFAULT_MATCHED_BINDING,
) -> OverlayCheckPhase:
    return OverlayCheckPhase(
        status=status,
        matched_count=matched_count,
        matched_binding=(
            _binding() if matched_binding is _DEFAULT_MATCHED_BINDING else matched_binding
        ),  # type: ignore[arg-type]
    )


def _diff(**kwargs: object) -> OverlayCheckDiff:
    fields = {
        "status_changed": False,
        "matched_count_delta": 0,
        "bindings_added": (),
        "bindings_removed": (),
    }
    fields.update(kwargs)
    return OverlayCheckDiff(**fields)  # type: ignore[arg-type]


def _error(code: str = "ENGINE_OVERLAY_NOT_SUPPORTED") -> ErrorDTO:
    return ErrorDTO(code=code, message="overlay unsupported")


class FactValueOverrideProtocolTests(unittest.TestCase):
    def test_override_construction_defaults_note(self) -> None:
        override = _override()
        self.assertEqual(override.asrt_id, "asrt-1")
        self.assertEqual(override.old_fact_tuple, ("doc-1", "low"))
        self.assertIsNone(override.note)

    def test_override_accepts_note(self) -> None:
        self.assertEqual(_override(note="caller context").note, "caller context")

    def test_override_is_frozen(self) -> None:
        override = _override()
        with self.assertRaises(FrozenInstanceError):
            override.asrt_id = "other"  # type: ignore[misc]

    def test_override_requires_non_empty_ids(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _override(asrt_id="")
        with self.assertRaises(ProtocolShapeError):
            _override(pred_id="")
        with self.assertRaises(ProtocolShapeError):
            _override(e_ref="")

    def test_override_requires_fact_tuples(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _override(old_fact_tuple=["doc-1", "low"])
        with self.assertRaises(ProtocolShapeError):
            _override(new_fact_tuple=["doc-1", "high"])

    def test_override_rejects_non_string_note(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _override(note=123)


class FactRemoveActionProtocolTests(unittest.TestCase):
    def test_remove_construction_defaults_note(self) -> None:
        action = _remove()
        self.assertEqual(action.asrt_id, "asrt-1")
        self.assertEqual(action.old_fact_tuple, ("doc-1", "low"))
        self.assertIsNone(action.note)

    def test_remove_accepts_note(self) -> None:
        self.assertEqual(_remove(note="caller context").note, "caller context")

    def test_remove_is_frozen(self) -> None:
        action = _remove()
        with self.assertRaises(FrozenInstanceError):
            action.asrt_id = "other"  # type: ignore[misc]

    def test_remove_requires_non_empty_ids(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _remove(asrt_id="")
        with self.assertRaises(ProtocolShapeError):
            _remove(pred_id="")
        with self.assertRaises(ProtocolShapeError):
            _remove(e_ref="")

    def test_remove_requires_old_fact_tuple(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _remove(old_fact_tuple=["doc-1", "low"])

    def test_remove_rejects_non_string_note(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _remove(note=123)


class RuleDisableActionProtocolTests(unittest.TestCase):
    def test_disable_construction_defaults_note(self) -> None:
        action = _disable()
        self.assertEqual(action.rule_id, "person.eligible")
        self.assertEqual(action.version, "1.0")
        self.assertEqual(action.branch_index, 0)
        self.assertEqual(action.atom_index, 1)
        self.assertIsNone(action.note)

    def test_disable_accepts_note(self) -> None:
        self.assertEqual(_disable(note="caller context").note, "caller context")

    def test_disable_is_frozen(self) -> None:
        action = _disable()
        with self.assertRaises(FrozenInstanceError):
            action.rule_id = "other"  # type: ignore[misc]

    def test_disable_rejects_bad_shape(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _disable(rule_id="")
        with self.assertRaises(ProtocolShapeError):
            _disable(version="")
        with self.assertRaises(ProtocolShapeError):
            _disable(branch_index=-1)
        with self.assertRaises(ProtocolShapeError):
            _disable(branch_index=True)
        with self.assertRaises(ProtocolShapeError):
            _disable(atom_index=-1)
        with self.assertRaises(ProtocolShapeError):
            _disable(note=123)


class RuleLiteralReplaceActionProtocolTests(unittest.TestCase):
    def test_literal_path_shape(self) -> None:
        self.assertEqual(RuleLiteralPath(kind="rhs").index, None)
        self.assertEqual(RuleLiteralPath(kind="pred_term", index=1).index, 1)
        self.assertEqual(RuleLiteralPath(kind="in_value", index=0).index, 0)

        with self.assertRaises(ProtocolShapeError):
            RuleLiteralPath(kind="pred_term")
        with self.assertRaises(ProtocolShapeError):
            RuleLiteralPath(kind="rhs", index=1)
        with self.assertRaises(ProtocolShapeError):
            RuleLiteralPath(kind="unknown")  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            RuleLiteralPath(kind="in_value", index=-1)

    def test_replace_action_construction(self) -> None:
        action = _replace_rule_literal()
        self.assertEqual(action.rule_id, "person.eligible")
        self.assertEqual(action.literal_path, RuleLiteralPath(kind="rhs"))
        self.assertEqual(action.old_literal, "us")
        self.assertEqual(action.new_literal, "eu")
        self.assertIsNone(action.note)

    def test_replace_action_is_frozen_and_rejects_bad_shape(self) -> None:
        action = _replace_rule_literal()
        with self.assertRaises(FrozenInstanceError):
            action.rule_id = "other"  # type: ignore[misc]
        with self.assertRaises(ProtocolShapeError):
            _replace_rule_literal(rule_id="")
        with self.assertRaises(ProtocolShapeError):
            _replace_rule_literal(version="")
        with self.assertRaises(ProtocolShapeError):
            _replace_rule_literal(branch_index=-1)
        with self.assertRaises(ProtocolShapeError):
            _replace_rule_literal(atom_index=True)
        with self.assertRaises(ProtocolShapeError):
            _replace_rule_literal(literal_path=("rhs", None))
        with self.assertRaises(ProtocolShapeError):
            _replace_rule_literal(note=123)


class EvaluationOverlayProtocolTests(unittest.TestCase):
    def test_overlay_accepts_replace_and_remove_actions(self) -> None:
        overlay = EvaluationOverlay(fact_actions=(_override(), _remove()))
        self.assertEqual(overlay.fact_actions, (_override(), _remove()))
        self.assertEqual(overlay.rule_actions, ())

    def test_overlay_allows_empty_actions_for_runtime_invalid_request(self) -> None:
        overlay = EvaluationOverlay()
        self.assertEqual(overlay.fact_actions, ())
        self.assertEqual(overlay.rule_actions, ())

    def test_overlay_preserves_legacy_positional_fact_actions(self) -> None:
        overlay = EvaluationOverlay((_override(),))
        self.assertEqual(overlay.fact_actions, (_override(),))
        self.assertEqual(overlay.rule_actions, ())

    def test_overlay_accepts_rule_actions_lane(self) -> None:
        overlay = EvaluationOverlay(rule_actions=(_disable(), _replace_rule_literal()))
        self.assertEqual(overlay.fact_actions, ())
        self.assertEqual(overlay.rule_actions, (_disable(), _replace_rule_literal()))

    def test_overlay_is_frozen(self) -> None:
        overlay = EvaluationOverlay(fact_actions=(_override(),))
        with self.assertRaises(FrozenInstanceError):
            overlay.fact_actions = ()  # type: ignore[misc]

    def test_overlay_rejects_non_tuple_actions(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            EvaluationOverlay(fact_actions=[_override()])  # type: ignore[arg-type]

    def test_overlay_rejects_unknown_action_type(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            EvaluationOverlay(fact_actions=(object(),))  # type: ignore[arg-type]

    def test_overlay_rejects_bad_rule_actions(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            EvaluationOverlay(rule_actions=[_disable()])  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            EvaluationOverlay(rule_actions=(object(),))  # type: ignore[arg-type]


class FactOverlayCheckRequestProtocolTests(unittest.TestCase):
    """§7-Overlay-2 / §7-Overlay-6: intent-only request DTO shape."""

    def test_request_construction(self) -> None:
        request = FactOverlayCheckRequest(
            plan=_plan(),
            binding=_binding(),
            overlay=(_override(),),
            engine="native",
        )
        self.assertEqual(request.binding, _binding())
        self.assertEqual(request.overlay, (_override(),))

    def test_request_is_frozen(self) -> None:
        request = FactOverlayCheckRequest(
            plan=_plan(),
            binding=_binding(),
            overlay=(_override(),),
            engine="native",
        )
        with self.assertRaises(FrozenInstanceError):
            request.engine = "souffle"  # type: ignore[misc]

    def test_request_allows_empty_overlay_for_runtime_invalid_request(self) -> None:
        request = FactOverlayCheckRequest(
            plan=_plan(),
            binding=_binding(),
            overlay=(),
            engine="native",
        )
        self.assertEqual(request.overlay, ())

    def test_request_accepts_evaluation_overlay(self) -> None:
        overlay = EvaluationOverlay(fact_actions=(_override(), _remove()))
        request = FactOverlayCheckRequest(
            plan=_plan(),
            binding=_binding(),
            overlay=overlay,
            engine="native",
        )
        self.assertEqual(request.overlay, overlay)

    def test_request_rejects_invalid_engine(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            FactOverlayCheckRequest(
                plan=_plan(),
                binding=_binding(),
                overlay=(_override(),),
                engine="lambda",  # type: ignore[arg-type]
            )

    def test_request_rejects_multi_head_plan(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            FactOverlayCheckRequest(
                plan=_plan(heads=(_head("doc:a"), _head("doc:b"))),
                binding=_binding(),
                overlay=(_override(),),
                engine="native",
            )

    def test_request_rejects_runtime_side_channel_fields(self) -> None:
        for field_name in ("store", "registry", "projection", "cache"):
            with self.subTest(field_name=field_name):
                with self.assertRaises(TypeError):
                    FactOverlayCheckRequest(
                        plan=_plan(),
                        binding=_binding(),
                        overlay=(_override(),),
                        engine="native",
                        **{field_name: object()},
                    )


class OverlayCheckPhaseProtocolTests(unittest.TestCase):
    def test_phase_construction(self) -> None:
        phase = _phase()
        self.assertEqual(phase.status, "passed")
        self.assertEqual(phase.matched_count, 1)
        self.assertEqual(phase.matched_binding, _binding())

    def test_failed_phase_accepts_no_matched_binding(self) -> None:
        phase = _phase(status="failed", matched_count=0, matched_binding=None)
        self.assertIsNone(phase.matched_binding)

    def test_phase_rejects_negative_or_bool_matched_count(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _phase(matched_count=-1)
        with self.assertRaises(ProtocolShapeError):
            _phase(matched_count=True)  # type: ignore[arg-type]

    def test_phase_rejects_invalid_status(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _phase(status="maybe")  # type: ignore[arg-type]

    def test_phase_rejects_result_level_statuses(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _phase(status="unsupported")  # type: ignore[arg-type]
        with self.assertRaises(ProtocolShapeError):
            _phase(status="invalid_request")  # type: ignore[arg-type]

    def test_passed_phase_requires_match(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _phase(status="passed", matched_count=0)
        with self.assertRaises(ProtocolShapeError):
            _phase(status="passed", matched_count=1, matched_binding=None)

    def test_failed_phase_requires_no_match(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _phase(status="failed", matched_count=1, matched_binding=None)
        with self.assertRaises(ProtocolShapeError):
            _phase(status="failed", matched_count=0, matched_binding=_binding())

    def test_phase_is_frozen(self) -> None:
        phase = _phase()
        with self.assertRaises(FrozenInstanceError):
            phase.matched_count = 2  # type: ignore[misc]


class OverlayCheckDiffProtocolTests(unittest.TestCase):
    def test_diff_construction(self) -> None:
        diff = _diff(
            status_changed=True,
            matched_count_delta=-1,
            bindings_added=(_binding(),),
            bindings_removed=(_partial_binding(),),
        )
        self.assertTrue(diff.status_changed)
        self.assertEqual(diff.matched_count_delta, -1)
        self.assertEqual(diff.bindings_added, (_binding(),))

    def test_diff_is_frozen(self) -> None:
        diff = _diff()
        with self.assertRaises(FrozenInstanceError):
            diff.status_changed = True  # type: ignore[misc]

    def test_diff_requires_bool_status_changed(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _diff(status_changed=1)

    def test_diff_requires_signed_int_delta(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _diff(matched_count_delta=True)
        with self.assertRaises(ProtocolShapeError):
            _diff(matched_count_delta="1")

    def test_diff_requires_tuple_binding_collections(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            _diff(bindings_added=[_binding()])
        with self.assertRaises(ProtocolShapeError):
            _diff(bindings_removed=[_binding()])

    def test_diff_normalizes_nested_binding_items(self) -> None:
        diff = _diff(bindings_added=((("$risk", "high"), ("$doc", "d-1")),))
        self.assertEqual(diff.bindings_added, (_binding(),))


class FactOverlayCheckResultProtocolTests(unittest.TestCase):
    """§7-Overlay-5 / §7-Overlay-12: nullable matrix and status semantics."""

    def test_passed_nullable_matrix(self) -> None:
        result = FactOverlayCheckResult(
            status="passed",
            requested_binding=_partial_binding(),
            before=_phase(status="failed", matched_count=0, matched_binding=None),
            after=_phase(status="passed", matched_count=1),
            diff=_diff(status_changed=True, matched_count_delta=1, bindings_added=(_binding(),)),
        )
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.after.status, "passed")
        self.assertEqual(result.errors, ())
        self.assertEqual(result.warnings, ())

    def test_failed_nullable_matrix(self) -> None:
        result = FactOverlayCheckResult(
            status="failed",
            requested_binding=_partial_binding(),
            before=_phase(status="passed", matched_count=1),
            after=_phase(status="failed", matched_count=0, matched_binding=None),
            diff=_diff(status_changed=True, matched_count_delta=-1, bindings_removed=(_binding(),)),
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.after.status, "failed")

    def test_unsupported_nullable_matrix(self) -> None:
        result = FactOverlayCheckResult(
            status="unsupported",
            requested_binding=_partial_binding(),
            before=None,
            after=None,
            diff=None,
            errors=(_error(),),
        )
        self.assertIsNone(result.before)
        self.assertIsNone(result.after)
        self.assertIsNone(result.diff)

    def test_invalid_request_nullable_matrix(self) -> None:
        result = FactOverlayCheckResult(
            status="invalid_request",
            requested_binding=_partial_binding(),
            before=None,
            after=None,
            diff=None,
            errors=(_error("EMPTY_OVERLAY_NOT_PERMITTED"),),
        )
        self.assertEqual(result.status, "invalid_request")

    def test_passed_requires_after_status_match(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            FactOverlayCheckResult(
                status="passed",
                requested_binding=_partial_binding(),
                before=_phase(status="failed", matched_count=0, matched_binding=None),
                after=_phase(status="failed", matched_count=0, matched_binding=None),
                diff=_diff(),
            )

    def test_passed_rejects_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            FactOverlayCheckResult(
                status="passed",
                requested_binding=_partial_binding(),
                before=_phase(),
                after=_phase(),
                diff=_diff(),
                errors=(_error(),),
            )

    def test_unsupported_rejects_partial_phase_population(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            FactOverlayCheckResult(
                status="unsupported",
                requested_binding=_partial_binding(),
                before=_phase(),
                after=None,
                diff=None,
                errors=(_error(),),
            )

    def test_unsupported_requires_errors(self) -> None:
        with self.assertRaises(ProtocolShapeError):
            FactOverlayCheckResult(
                status="unsupported",
                requested_binding=_partial_binding(),
                before=None,
                after=None,
                diff=None,
            )

    def test_result_is_frozen(self) -> None:
        result = FactOverlayCheckResult(
            status="unsupported",
            requested_binding=_partial_binding(),
            before=None,
            after=None,
            diff=None,
            errors=(_error(),),
        )
        with self.assertRaises(FrozenInstanceError):
            result.status = "failed"  # type: ignore[misc]


class FactOverlayProtocolStaticInvariantTests(unittest.TestCase):
    """§7-Overlay-2 / §7-Overlay-10 / §7-Overlay-11 / §7-Overlay-12."""

    def test_status_literal_exact_members(self) -> None:
        self.assertEqual(
            set(typing.get_args(OverlayCheckStatus)),
            {"passed", "failed", "unsupported", "invalid_request"},
        )

    def test_engine_literal_exact_members(self) -> None:
        self.assertEqual(
            set(typing.get_args(OverlayCheckEngine)),
            {"native", "souffle", "problog", "pyreason"},
        )

    def test_phase_status_literal_exact_members(self) -> None:
        self.assertEqual(set(typing.get_args(OverlayCheckPhaseStatus)), {"passed", "failed"})

    def test_request_dataclass_fields_are_intent_only(self) -> None:
        self.assertEqual(
            [field.name for field in dataclasses.fields(FactOverlayCheckRequest)],
            ["plan", "binding", "overlay", "engine"],
        )

    def test_result_has_no_engine_payload_or_evidence_fields(self) -> None:
        result_fields = {field.name for field in dataclasses.fields(FactOverlayCheckResult)}
        self.assertNotIn("evidence_envelope", result_fields)
        self.assertNotIn("engine_payload", result_fields)
        self.assertNotIn("support_artifact", result_fields)
        self.assertNotIn("provenance_envelope", result_fields)

    def test_phase_and_diff_do_not_import_engine_payload_types(self) -> None:
        self.assertFalse(hasattr(overlay_protocol, "EvidenceEnvelope"))
        self.assertFalse(hasattr(overlay_protocol, "SupportArtifact"))
        self.assertFalse(hasattr(overlay_protocol, "ProvenanceEnvelope"))

    def test_protocol_package_exports_overlay_dtos(self) -> None:
        self.assertIs(protocol_pkg.FactOverlayCheckRequest, FactOverlayCheckRequest)
        self.assertIs(protocol_pkg.FactOverlayCheckResult, FactOverlayCheckResult)
        self.assertIs(protocol_pkg.FactValueOverride, FactValueOverride)
        self.assertIs(protocol_pkg.RuleDisableAction, RuleDisableAction)
        self.assertIs(protocol_pkg.RuleLiteralPath, RuleLiteralPath)
        self.assertIs(protocol_pkg.RuleLiteralReplaceAction, RuleLiteralReplaceAction)
        self.assertIs(protocol_pkg.OverlayCheckPhase, OverlayCheckPhase)
        self.assertIs(protocol_pkg.OverlayCheckPhaseStatus, OverlayCheckPhaseStatus)
        self.assertIs(protocol_pkg.OverlayCheckDiff, OverlayCheckDiff)


if __name__ == "__main__":
    unittest.main()
