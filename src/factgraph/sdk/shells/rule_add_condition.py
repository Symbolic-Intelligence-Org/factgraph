"""SDK shell for G3 Batch 5c Rule Add Condition capability.

Implements the ``sdk_rule_add_condition`` facade method per
the archived G3 blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g3-rule-overlays.md``
§5.

Public surface contract per blueprint §5 locks:

- Method:      ``sdk_rule_add_condition(...)`` (instance
               method; not a free function in ``factgraph.sdk.__all__``).
- Signature:   ``check_rule_add_condition(rule, support, *,
               case_index, added_atom, overlay=None, note=None)``
               per §5.1 / §5.2 / §5.4 locks. ``rule`` is an SDK ``Rule``
               (lowered through ``SDKStore._compile_rule_input`` to a
               ``RuleSpec``); ``support`` is a raw ``ProofReceipt``
               from a prior Check; ``added_atom`` is a raw
               ``AddedCondition`` (G2 §5.1+§5.2 cross-cutting precedent —
               frozen application-canonical, no SDK alternative);
               ``overlay`` is ``None`` or an empty ``FactOverlay``
               (the rule-action overlay is constructed internally by
               the A helper). Note the absence of ``condition_index`` —
               Add Condition appends a new atom rather than pointing at
               an existing locator.
- Return:      ``RuleAddConditionResult`` (raw application protocol
               DTO; documented passthrough per §5.3 lock; not
               re-exported from ``factgraph.sdk.__all__``).
- Errors:      Non-SDK exceptions crossing the SDK boundary remap to
               ``SDKStoreError(...) from exc`` per §5.8 lock with
               capability-specific paths
               (``$.check_rule_add_condition.rule`` /
               ``$.check_rule_add_condition.support`` /
               ``$.check_rule_add_condition.overlay`` /
               ``$.check_rule_add_condition.dependencies`` /
               ``$.check_rule_add_condition.request`` / base
               ``$.check_rule_add_condition`` for unexpected runtime).
- Sibling:     ``sdk_rule_add_condition`` does NOT call any sibling
               SDK shell (``sdk_check`` / ``sdk_diagnose`` /
               ``sdk_why_not`` / ``sdk_fact_overlay_check`` /
               ``sdk_proof_frame_recheck`` / ``sdk_rule_disable`` /
               ``sdk_rule_literal_replace``). It owns its own dispatch
               and never extracts a ``ProofReceipt`` from a
               ``CheckResult.proof``.
"""

from __future__ import annotations

from typing import Any

from factgraph.application.capability_helpers import build_rule_add_condition_request
from factgraph.application.capability_helpers.errors import CapabilityHelperError
from factgraph.application.protocol import ProtocolShapeError, RuleAddConditionResult
from factgraph.application.rule_add_condition_runtime import (
    check_rule_add_condition_action,
)

from ..errors import SDKStoreError
from ._validation import (
    resolve_rule_spec,
    resolve_runtime_registry,
    validate_optional_evaluation_overlay,
    validate_support_artifact,
)


def sdk_rule_add_condition(
    sdk: Any,
    rule: Any,
    support: Any,
    *,
    case_index: int,
    added_atom: Any,
    overlay: Any = None,
    note: str | None = None,
) -> RuleAddConditionResult:
    """Run Rule Add Condition for one SDK ``Rule`` + support + branch + new atom.

    Returns the application ``RuleAddConditionResult`` DTO directly.
    The SDK shell does not import sibling SDK shells; the runtime
    represents unsupported support / rule-mismatch / native-eval
    failure modes as result DTOs and passes them through unchanged.
    """

    rule_spec = resolve_rule_spec(sdk, rule, path="$.check_rule_add_condition.rule")
    validate_support_artifact(support, path="$.check_rule_add_condition.support")
    validate_optional_evaluation_overlay(
        overlay, path="$.check_rule_add_condition.overlay"
    )


    resolved_registry = resolve_runtime_registry(
        sdk,
        rule,
        explicit_registry=None,
        path="$.check_rule_add_condition.dependencies",
    )

    try:
        request = build_rule_add_condition_request(
            rule_spec,
            support,
            case_index=case_index,
            added_atom=added_atom,
            overlay=overlay,
            note=note,
        )
    except (CapabilityHelperError, ProtocolShapeError) as exc:
        raise SDKStoreError(
            f"invalid check_rule_add_condition request: {exc}",
            path="$.check_rule_add_condition.request",
        ) from exc

    try:
        return check_rule_add_condition_action(
            request, store=sdk._store, registry=resolved_registry
        )
    except Exception as exc:
        raise SDKStoreError(
            f"check_rule_add_condition runtime failed: {exc}",
            path="$.check_rule_add_condition",
        ) from exc


__all__ = [
    "sdk_rule_add_condition",
]
