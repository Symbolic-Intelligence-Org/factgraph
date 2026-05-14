"""Shared boundary helpers for SDK shell methods.

Used by ``factgraph.sdk.shells.check`` / ``factgraph.sdk.shells.diagnose`` (G1),
``factgraph.sdk.shells.why_not`` (G4), ``factgraph.sdk.shells.fact_overlay`` /
``factgraph.sdk.shells.proof_frame`` (G2), and
``factgraph.sdk.shells.rule_disable`` /
``factgraph.sdk.shells.rule_literal_replace`` /
``factgraph.sdk.shells.rule_add_condition`` (G3). Each helper accepts a
caller-specific ``SDKStoreError.path`` boundary identifier so a single
implementation serves multiple shells. Lives at
``factgraph/sdk/shells/_validation.py`` after G2 Phase 0 hygiene migrated
all SDK shell modules into the ``factgraph/sdk/shells/`` subpackage.

The module is private (``_validation``) and the functions are imported
locally by sibling shell modules — nothing here is part of
``factgraph.sdk.__all__`` (per blueprint §5.2 / §5.4 / §6 narrow public API).

Helper inventory:

Input validators (pure type / shape guards):

- ``validate_derivation`` — G1 + G4 + G2 Fact Overlay (rejects non-SDK
  ``Inference``).
- ``validate_binding`` — G1 + G4 + G2 Fact Overlay (validates
  ``$``-prefixed variable name mapping).
- ``validate_evaluation_overlay`` — G2 (rejects non-``EvaluationOverlay``
  including ``None``; used at boundaries that require an overlay).
- ``validate_rule`` — G3 (rejects non-SDK ``Rule``; mirrors
  ``validate_derivation`` shape).
- ``validate_support_artifact`` — G2 ProofFrame + G3 (rejects
  non-``SupportArtifact``).
- ``validate_optional_evaluation_overlay`` — G3 (rejects non-
  ``EvaluationOverlay`` non-None AND rejects non-empty
  ``EvaluationOverlay``; allows ``None`` because the G3 rule-overlay A
  helpers construct the rule-action overlay internally).

Boundary normalizers (catch + re-raise with caller-supplied path):

- ``resolve_runtime_registry`` — G1 + G4 + G2 Fact Overlay + G3 (wraps
  ``SDKStore._resolve_runtime_registry`` to remap both
  ``RuleCompileError`` (from ``RuleRegistry.register`` validation) and
  ``SDKStoreError`` (from ``_compile_rule_input`` wrapping
  authoring-compile failures of dependency rules) to
  ``SDKStoreError(path="$.<method>.dependencies") from exc``. Without
  this helper the inner ``SDKStoreError`` from ``_compile_rule_input``
  leaks past the shell with ``path=None``).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from factgraph.application.protocol import EvaluationOverlay
from factgraph.core.rules.rule_ir import RuleCompileError
from factgraph.core.store._support import SupportArtifact

from ..dsl import Inference, Rule
from ..errors import SDKStoreError


def validate_derivation(derivation: Any, *, path: str) -> None:
    """Reject anything that is not an SDK ``Inference`` instance.

    The ``path`` argument is the ``SDKStoreError.path`` boundary identifier
    that the calling shell wants attached, e.g. ``"$.check.inference"`` or
    ``"$.diagnose.inference"``. The error message text is shared across
    callers — only the path differs.
    """

    if not isinstance(derivation, Inference):
        raise SDKStoreError("inference must be SDK Inference", path=path)


def validate_binding(binding: Any, *, path: str) -> dict[str, Any]:
    """Validate the SDK shell binding mapping and return a plain ``dict`` copy.

    Accepts any ``collections.abc.Mapping`` whose keys are ``$``-prefixed
    variable-name strings (length ≥ 2). Returns a fresh ``dict[str, Any]``
    so callers can pass it onward without retaining the original mapping
    reference.
    """

    if not isinstance(binding, Mapping):
        raise SDKStoreError("binding must be Mapping[str, Any]", path=path)

    out: dict[str, Any] = {}
    for key, value in binding.items():
        if not isinstance(key, str) or not key.startswith("$") or len(key) == 1:
            raise SDKStoreError(
                "binding keys must be $-prefixed variable names",
                path=path,
            )
        out[key] = value
    return out


def validate_evaluation_overlay(value: Any, *, path: str) -> None:
    """Reject anything that is not an ``EvaluationOverlay`` instance.

    Used by Fact Overlay Check (``$.check_fact_overlay.overlay``) and
    ProofFrame Recheck (``$.recheck_proof_frame.overlay``) to enforce the
    G2 §5.1 + §5.2 lock that the SDK boundary accepts only
    ``EvaluationOverlay`` — narrower than the application
    ``FactOverlayCheckRequest.overlay`` field which also tolerates
    ``tuple[FactValueOverride, ...]``. Rejects ``None``; G3 callers that
    accept a None default use ``validate_optional_evaluation_overlay``
    instead.
    """

    if not isinstance(value, EvaluationOverlay):
        raise SDKStoreError("overlay must be EvaluationOverlay", path=path)


def validate_rule(rule: Any, *, path: str) -> None:
    """Reject anything that is not an SDK ``Rule`` instance.

    Mirrors ``validate_derivation``. The ``path`` argument is the
    ``SDKStoreError.path`` boundary identifier the calling shell wants
    attached, e.g. ``"$.check_rule_disable.rule"`` or
    ``"$.check_rule_literal_replace.rule"``. Used by G3 rule-overlay
    SDK shells (``check_rule_disable`` / ``check_rule_literal_replace``
    / ``check_rule_add_condition``) per blueprint §5.2 lock.
    """

    if not isinstance(rule, Rule):
        raise SDKStoreError("rule must be SDK Rule", path=path)


def validate_support_artifact(value: Any, *, path: str) -> None:
    """Reject anything that is not a ``SupportArtifact`` instance.

    Used by G2 ProofFrame Recheck
    (``$.recheck_proof_frame.support_artifact``) and the three G3
    rule-overlay shells (``$.<method>.support``). Promoted from G2
    ProofFrame's local helper at G3 Phase 0 hygiene per the §5.2
    deferred trigger ("until G3/G5 also need them").
    """

    if not isinstance(value, SupportArtifact):
        raise SDKStoreError("support must be SupportArtifact", path=path)


def validate_optional_evaluation_overlay(value: Any, *, path: str) -> None:
    """Reject non-``EvaluationOverlay`` and non-empty ``EvaluationOverlay``.

    G3 rule-overlay A helpers (``build_rule_disable_request`` /
    ``build_rule_literal_replace_request`` /
    ``build_rule_add_condition_request``) construct the single rule-action
    overlay internally; SDK callers pass either ``None`` or an empty
    ``EvaluationOverlay()``. This validator pre-rejects (a) non-
    ``EvaluationOverlay`` non-None inputs, and (b) non-empty
    ``EvaluationOverlay`` (i.e. with any ``fact_actions`` or
    ``rule_actions``). After this check, the application-layer
    ``_request_overlay(...)`` non-empty rejection becomes defensive /
    unreachable from SDK.

    Allows ``None`` because the rule-overlay shells default ``overlay``
    to ``None``; G2's ``validate_evaluation_overlay`` rejects ``None``
    because Fact Overlay and ProofFrame Recheck require an overlay.
    """

    if value is None:
        return
    if not isinstance(value, EvaluationOverlay):
        raise SDKStoreError("overlay must be EvaluationOverlay or None", path=path)
    if value.fact_actions or value.rule_actions:
        raise SDKStoreError(
            "overlay must be empty EvaluationOverlay (or None); "
            "rule-action overlay is constructed internally",
            path=path,
        )


def resolve_runtime_registry(
    sdk: Any,
    obj: Any,
    *,
    explicit_registry: Any,
    path: str,
) -> Any:
    """Resolve dependency registry; normalize boundary exceptions.

    Wraps ``SDKStore._resolve_runtime_registry(obj, explicit_registry=...)``
    so both error sources at the dependency boundary remap to a single
    ``SDKStoreError(path=...)`` shape:

    - ``RuleCompileError`` from ``RuleRegistry.register(...)`` validation
      (e.g., duplicate rule registration, RuleRef cycle, unknown
      RuleRef).
    - ``SDKStoreError`` from ``SDKStore._compile_rule_input(dep_rule)``
      which itself wraps any ``Exception`` (including
      ``AuthoringRuleCompileError`` from ``compile_authoring_rule_v1``)
      as a pathless ``SDKStoreError("invalid rule input: ...")``. Without
      this re-wrap the pathless ``SDKStoreError`` would leak past the
      shell — a verification-round Blocker the helper exists to prevent.

    The original exception is preserved as ``__cause__`` so callers can
    still inspect the underlying compile failure.
    """

    try:
        return sdk._resolve_runtime_registry(obj, explicit_registry=explicit_registry)
    except (RuleCompileError, SDKStoreError) as exc:
        raise SDKStoreError(
            f"invalid dependencies: {exc}",
            path=path,
        ) from exc


__all__ = [
    "resolve_runtime_registry",
    "validate_binding",
    "validate_derivation",
    "validate_evaluation_overlay",
    "validate_optional_evaluation_overlay",
    "validate_rule",
    "validate_support_artifact",
]
