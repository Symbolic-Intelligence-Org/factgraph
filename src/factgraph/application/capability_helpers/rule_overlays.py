"""Rule overlay capability helper builders."""

from __future__ import annotations

from typing import Any

from factgraph.core.rules.rule_ir import RuleSpec
from factgraph.core.store._support import SupportArtifact

from factgraph.application.protocol import (
    EvaluationOverlay,
    RuleAddConditionAction,
    RuleAddConditionRequest,
    RuleAddedAtom,
    RuleDisableAction,
    RuleDisableRequest,
    RuleLiteralPath,
    RuleLiteralReplaceAction,
    RuleLiteralReplaceRequest,
    RuleOverlayAction,
)

from ._binding import _reject_sdk_origin
from .errors import CapabilityHelperError


def build_rule_disable_request(
    rule_spec: RuleSpec,
    support: SupportArtifact,
    *,
    branch_index: int,
    atom_index: int,
    overlay: EvaluationOverlay | None = None,
    note: str | None = None,
) -> RuleDisableRequest:
    """Build a RuleDisableRequest with exactly one RuleDisableAction."""

    _validate_rule_overlay_inputs(rule_spec, support, overlay)
    _reject_sdk_origin(branch_index, path="branch_index")
    _reject_sdk_origin(atom_index, path="atom_index")
    _reject_sdk_origin(note, path="note")
    action = RuleDisableAction(
        rule_id=rule_spec.rule_id,
        version=rule_spec.version,
        branch_index=branch_index,
        atom_index=atom_index,
        note=note,
    )
    overlay_value = _request_overlay(action, overlay=overlay)
    return RuleDisableRequest(
        rule_spec=rule_spec,
        support_artifact=support,
        overlay=overlay_value,
    )


def build_rule_literal_replace_request(
    rule_spec: RuleSpec,
    support: SupportArtifact,
    *,
    branch_index: int,
    atom_index: int,
    literal_path: RuleLiteralPath,
    old_literal: Any,
    new_literal: Any,
    overlay: EvaluationOverlay | None = None,
    note: str | None = None,
) -> RuleLiteralReplaceRequest:
    """Build a RuleLiteralReplaceRequest with exactly one RuleLiteralReplaceAction."""

    _validate_rule_overlay_inputs(rule_spec, support, overlay)
    _reject_sdk_origin(branch_index, path="branch_index")
    _reject_sdk_origin(atom_index, path="atom_index")
    _reject_sdk_origin(literal_path, path="literal_path")
    _reject_sdk_origin(old_literal, path="old_literal")
    _reject_sdk_origin(new_literal, path="new_literal")
    _reject_sdk_origin(note, path="note")
    action = RuleLiteralReplaceAction(
        rule_id=rule_spec.rule_id,
        version=rule_spec.version,
        branch_index=branch_index,
        atom_index=atom_index,
        literal_path=literal_path,
        old_literal=old_literal,
        new_literal=new_literal,
        note=note,
    )
    overlay_value = _request_overlay(action, overlay=overlay)
    return RuleLiteralReplaceRequest(
        rule_spec=rule_spec,
        support_artifact=support,
        overlay=overlay_value,
    )


def build_rule_add_condition_request(
    rule_spec: RuleSpec,
    support: SupportArtifact,
    *,
    branch_index: int,
    added_atom: RuleAddedAtom,
    overlay: EvaluationOverlay | None = None,
    note: str | None = None,
) -> RuleAddConditionRequest:
    """Build a RuleAddConditionRequest with exactly one RuleAddConditionAction."""

    _validate_rule_overlay_inputs(rule_spec, support, overlay)
    _reject_sdk_origin(branch_index, path="branch_index")
    _reject_sdk_origin(added_atom, path="added_atom")
    _reject_sdk_origin(note, path="note")
    action = RuleAddConditionAction(
        rule_id=rule_spec.rule_id,
        version=rule_spec.version,
        branch_index=branch_index,
        added_atom=added_atom,
        note=note,
    )
    overlay_value = _request_overlay(action, overlay=overlay)
    return RuleAddConditionRequest(
        rule_spec=rule_spec,
        support_artifact=support,
        overlay=overlay_value,
    )


def _validate_rule_and_support(rule_spec: RuleSpec, support: SupportArtifact) -> None:
    if not isinstance(rule_spec, RuleSpec):
        raise CapabilityHelperError("rule_spec must be RuleSpec")
    if not isinstance(support, SupportArtifact):
        raise CapabilityHelperError("support must be SupportArtifact")


def _validate_rule_overlay_inputs(
    rule_spec: RuleSpec,
    support: SupportArtifact,
    overlay: EvaluationOverlay | None,
) -> None:
    """Scan raw inputs before protocol DTO construction, then type-check."""

    _reject_sdk_origin(rule_spec, path="rule_spec")
    _reject_sdk_origin(support, path="support")
    if overlay is not None:
        _reject_sdk_origin(overlay, path="overlay")

    _validate_rule_and_support(rule_spec, support)
    if overlay is not None and not isinstance(overlay, EvaluationOverlay):
        raise CapabilityHelperError("overlay must be EvaluationOverlay or None")


def _request_overlay(
    action: RuleOverlayAction,
    *,
    overlay: EvaluationOverlay | None,
) -> EvaluationOverlay:
    if overlay is None:
        return EvaluationOverlay(rule_actions=(action,))
    if not isinstance(overlay, EvaluationOverlay):
        raise CapabilityHelperError("overlay must be EvaluationOverlay or None")
    if overlay.fact_actions or overlay.rule_actions:
        raise CapabilityHelperError(
            "non-empty overlay not supported; use overlay=None or EvaluationOverlay()"
        )
    return EvaluationOverlay(rule_actions=(action,))


__all__ = [
    "build_rule_add_condition_request",
    "build_rule_disable_request",
    "build_rule_literal_replace_request",
]
