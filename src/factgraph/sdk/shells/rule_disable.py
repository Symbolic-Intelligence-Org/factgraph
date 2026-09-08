"""SDK shell for G3 Batch 5a Rule Disable capability.

Implements the ``sdk_rule_disable`` facade method per the
archived G3 blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g3-rule-overlays.md``
§5.

Public surface contract per blueprint §5 locks:

- Method:      ``sdk_rule_disable(...)`` (instance method;
               not a free function in ``factgraph.sdk.__all__`` — see
               §5.7 lock and G1 + G4 + G2 precedent).
- Signature:   ``check_rule_disable(rule, support, *, case_index,
               condition_index, overlay=None, note=None)`` per §5.1 / §5.2 /
               §5.4 locks. ``rule`` is an SDK ``Rule`` (lowered through
               ``SDKStore._compile_rule_input`` to a ``RuleSpec``);
               ``support`` is a raw ``ProofReceipt`` from a prior
               Check; ``overlay`` is ``None`` or an empty
               ``FactOverlay`` (the rule-action overlay is
               constructed internally by the A helper).
- Return:      ``RuleDisableResult`` (raw application protocol DTO;
               documented passthrough per §5.3 lock; not re-exported
               from ``factgraph.sdk.__all__``).
- Errors:      Non-SDK exceptions crossing the SDK boundary remap to
               ``SDKStoreError(...) from exc`` per §5.8 lock with
               capability-specific paths
               (``$.check_rule_disable.rule`` /
               ``$.check_rule_disable.support`` /
               ``$.check_rule_disable.overlay`` /
               ``$.check_rule_disable.dependencies`` /
               ``$.check_rule_disable.request`` / base
               ``$.check_rule_disable`` for unexpected runtime). The
               application runtime represents native-eval / target-not-
               found / rule-mismatch failure modes as
               ``RuleDisableResult(status="invalid_request" or
               "unsupported")`` and those results are passed through
               unchanged; only truly unexpected runtime exceptions
               reach the base-path remap.
- Sibling:     ``sdk_rule_disable`` does NOT call any sibling SDK shell
               (``sdk_check`` / ``sdk_diagnose`` / ``sdk_why_not`` /
               ``sdk_fact_overlay_check`` / ``sdk_proof_frame_recheck``
               / ``sdk_rule_literal_replace`` / ``sdk_rule_add_condition``).
               It owns its own dispatch and never extracts a
               ``ProofReceipt`` from a ``CheckResult.proof``
               (a ``ProofReceipt | ProvenanceEnvelope`` union).
"""

from __future__ import annotations

from typing import Any

from factgraph.application.capability_helpers import build_rule_disable_request
from factgraph.application.capability_helpers.errors import CapabilityHelperError
from factgraph.application.protocol import ProtocolShapeError, RuleDisableResult
from factgraph.application.rule_disable_runtime import check_rule_disable_action

from ..errors import SDKStoreError
from ._validation import (
    resolve_rule_spec,
    resolve_runtime_registry,
    validate_optional_evaluation_overlay,
    validate_support_artifact,
)


def sdk_rule_disable(
    sdk: Any,
    rule: Any,
    support: Any,
    *,
    case_index: int,
    condition_index: int,
    overlay: Any = None,
    note: str | None = None,
) -> RuleDisableResult:
    """Run Rule Disable for one SDK ``Rule`` + support + (branch, atom) target.

    Returns the application ``RuleDisableResult`` DTO directly. The SDK
    shell does not import sibling SDK shells; the runtime
    ``check_rule_disable_action(...)`` represents unsupported support /
    rule-mismatch / target-not-found / native-eval failure modes as
    result DTOs and passes them through unchanged.
    """

    rule_spec = resolve_rule_spec(sdk, rule, path="$.check_rule_disable.rule")
    validate_support_artifact(support, path="$.check_rule_disable.support")
    validate_optional_evaluation_overlay(overlay, path="$.check_rule_disable.overlay")


    resolved_registry = resolve_runtime_registry(
        sdk,
        rule,
        explicit_registry=None,
        path="$.check_rule_disable.dependencies",
    )

    try:
        request = build_rule_disable_request(
            rule_spec,
            support,
            case_index=case_index,
            condition_index=condition_index,
            overlay=overlay,
            note=note,
        )
    except (CapabilityHelperError, ProtocolShapeError) as exc:
        raise SDKStoreError(
            f"invalid check_rule_disable request: {exc}",
            path="$.check_rule_disable.request",
        ) from exc

    try:
        return check_rule_disable_action(
            request, store=sdk._store, registry=resolved_registry
        )
    except Exception as exc:
        raise SDKStoreError(
            f"check_rule_disable runtime failed: {exc}",
            path="$.check_rule_disable",
        ) from exc


__all__ = [
    "sdk_rule_disable",
]
