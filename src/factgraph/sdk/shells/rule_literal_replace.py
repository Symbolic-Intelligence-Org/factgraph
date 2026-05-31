"""SDK shell for G3 Batch 5b Rule Literal Replace capability.

Implements the ``sdk_rule_literal_replace`` facade method
per the archived G3 blueprint
``docs/blueprints/archive/2026-05-08_l-direction-g3-rule-overlays.md``
§5.

Public surface contract per blueprint §5 locks:

- Method:      ``sdk_rule_literal_replace(...)`` (instance
               method; not a free function in ``factgraph.sdk.__all__``).
- Signature:   ``check_rule_literal_replace(rule, support, *,
               branch_index, atom_index, literal_path, old_literal,
               new_literal, overlay=None, note=None)`` per §5.1 / §5.2 /
               §5.4 locks. ``rule`` is an SDK ``Rule`` (lowered through
               ``SDKStore._compile_rule_input`` to a ``RuleSpec``);
               ``support`` is a raw ``SupportArtifact`` from a prior
               Check; ``literal_path`` is a raw ``RuleLiteralPath``
               (G2 §5.1+§5.2 cross-cutting precedent — frozen
               application-canonical, no SDK alternative); ``overlay``
               is ``None`` or an empty ``EvaluationOverlay`` (the
               rule-action overlay is constructed internally by the A
               helper).
- Return:      ``RuleLiteralReplaceResult`` (raw application protocol
               DTO; documented passthrough per §5.3 lock; not
               re-exported from ``factgraph.sdk.__all__``).
- Errors:      Non-SDK exceptions crossing the SDK boundary remap to
               ``SDKStoreError(...) from exc`` per §5.8 lock with
               capability-specific paths
               (``$.check_rule_literal_replace.rule`` /
               ``$.check_rule_literal_replace.support`` /
               ``$.check_rule_literal_replace.overlay`` /
               ``$.check_rule_literal_replace.dependencies`` /
               ``$.check_rule_literal_replace.request`` / base
               ``$.check_rule_literal_replace`` for unexpected
               runtime). The application runtime represents support /
               rule-mismatch / target-not-found / native-eval failure
               modes as result DTOs and those results are passed
               through unchanged.
- Sibling:     ``sdk_rule_literal_replace`` does NOT call any sibling
               SDK shell (``sdk_check`` / ``sdk_diagnose`` /
               ``sdk_why_not`` / ``sdk_fact_overlay_check`` /
               ``sdk_proof_frame_recheck`` / ``sdk_rule_disable`` /
               ``sdk_rule_add_condition``). It owns its own dispatch
               and never extracts a ``SupportArtifact`` from a
               ``CheckResult.engine_payload``.
"""

from __future__ import annotations

from typing import Any

from factgraph.application.capability_helpers import build_rule_literal_replace_request
from factgraph.application.capability_helpers.errors import CapabilityHelperError
from factgraph.application.protocol import ProtocolShapeError, RuleLiteralReplaceResult
from factgraph.application.rule_literal_replace_runtime import (
    check_rule_literal_replace_action,
)
from factgraph.core.rules.rule_ir import RuleCompileError, RuleSpec

from ._validation import (
    resolve_runtime_registry,
    validate_optional_evaluation_overlay,
    validate_rule,
    validate_support_artifact,
)
from ..errors import SDKStoreError


def sdk_rule_literal_replace(
    sdk: Any,
    rule: Any,
    support: Any,
    *,
    branch_index: int,
    atom_index: int,
    literal_path: Any,
    old_literal: Any,
    new_literal: Any,
    overlay: Any = None,
    note: str | None = None,
) -> RuleLiteralReplaceResult:
    """Run Rule Literal Replace for one SDK ``Rule`` + support + (branch, atom, literal-path) target.

    Returns the application ``RuleLiteralReplaceResult`` DTO directly.
    The SDK shell does not import sibling SDK shells; the runtime
    represents unsupported support / rule-mismatch / target-not-found /
    native-eval failure modes as result DTOs and passes them through
    unchanged.
    """

    validate_rule(rule, path="$.check_rule_literal_replace.rule")
    validate_support_artifact(support, path="$.check_rule_literal_replace.support")
    validate_optional_evaluation_overlay(
        overlay, path="$.check_rule_literal_replace.overlay"
    )

    try:
        compiled = sdk._compile_rule_input(rule)
        rule_spec = RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )
    except (SDKStoreError, RuleCompileError) as exc:
        raise SDKStoreError(
            f"invalid check_rule_literal_replace rule: {exc}",
            path="$.check_rule_literal_replace.rule",
        ) from exc

    resolved_registry = resolve_runtime_registry(
        sdk,
        rule,
        explicit_registry=None,
        path="$.check_rule_literal_replace.dependencies",
    )

    try:
        request = build_rule_literal_replace_request(
            rule_spec,
            support,
            branch_index=branch_index,
            atom_index=atom_index,
            literal_path=literal_path,
            old_literal=old_literal,
            new_literal=new_literal,
            overlay=overlay,
            note=note,
        )
    except (CapabilityHelperError, ProtocolShapeError) as exc:
        raise SDKStoreError(
            f"invalid check_rule_literal_replace request: {exc}",
            path="$.check_rule_literal_replace.request",
        ) from exc

    try:
        return check_rule_literal_replace_action(
            request, store=sdk._store, registry=resolved_registry
        )
    except Exception as exc:
        raise SDKStoreError(
            f"check_rule_literal_replace runtime failed: {exc}",
            path="$.check_rule_literal_replace",
        ) from exc


__all__ = [
    "sdk_rule_literal_replace",
]
