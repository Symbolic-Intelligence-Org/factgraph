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

- ``validate_derivation`` — rejects non-SDK ``Inference``. Kept for callers
  that genuinely require the DSL form; the capability shells use
  ``resolve_derivation_plan`` instead.
- ``validate_binding`` — G1 + G4 + G2 Fact Overlay (validates
  ``$``-prefixed variable name mapping).
- ``validate_evaluation_overlay`` — G2 (rejects non-``FactOverlay``
  including ``None``; used at boundaries that require an overlay).
- ``validate_rule`` — rejects anything that is neither an SDK ``Rule`` nor an
  application ``Rule``.

Rule-form resolvers (accept either form, return what the runtime takes):

- ``resolve_derivation_plan`` — G1 + G4 + G2 Fact Overlay. ``Inference``,
  application ``Rule`` or ``RuleExpr`` in, ``CompiledDerivationPlan`` out.
- ``resolve_rule_spec`` — G3. Either ``Rule`` form in, ``RuleSpec`` out.
- ``validate_support_artifact`` — G2 ProofFrame + G3 (rejects
  non-``ProofReceipt``).
- ``validate_optional_evaluation_overlay`` — G3 (rejects non-
  ``FactOverlay`` non-None AND rejects non-empty
  ``FactOverlay``; allows ``None`` because the G3 rule-overlay A
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

from factgraph.application.protocol import FactOverlay
from factgraph.core.rules.rule_ir import RuleCompileError
from factgraph.core.store._support import ProofReceipt

from ..dsl import Inference, Rule
from ..errors import SDKStoreError
from ..store import _compiled_derivation_plan_to_application


def validate_derivation(derivation: Any, *, path: str) -> None:
    """Reject anything that is not an SDK ``Inference`` instance.

    The ``path`` argument is the ``SDKStoreError.path`` boundary identifier
    that the calling shell wants attached, e.g. ``"$.check.inference"`` or
    ``"$.diagnose.inference"``. The error message text is shared across
    callers — only the path differs.

    Kept for callers that genuinely require the DSL form. The capability shells
    use :func:`resolve_derivation_plan`, which accepts both rule forms.
    """

    if not isinstance(derivation, Inference):
        raise SDKStoreError("inference must be SDK Inference", path=path)


def resolve_derivation_plan(
    sdk: Any,
    derivation: Any,
    *,
    head: Any = None,
    engine: str = "native",
    path: str,
) -> Any:
    """Resolve either rule form to the ``CompiledDerivationPlan`` the runtime takes.

    The capability runtimes never asked for an ``Inference``: they take a
    ``CompiledDerivationPlan``. Only the shells in front of them did, which left
    the whole capability surface closed to the rule form the application layer
    authors. This resolves both to the same plan.

    * ``Inference`` — the existing compile path, unchanged.
    * ``Rule`` / ``RuleExpr`` — the lowering that already runs for rule programs
      and for the adapters, through the public ``compile_derivation_plan``.

    ``head`` is required for the rule form and there is no default: a rule says
    what holds, not what it concludes, so a standin head would invent the
    conclusion. Passing one with an ``Inference`` is ignored, since an inference
    already carries its head.
    """
    from factgraph.application.protocol import Rule as ApplicationRule
    from factgraph.application.protocol import compile_derivation_plan
    from factgraph.application.protocol.rule_expr import RuleExprError, _RuleExpr

    if isinstance(derivation, Inference):
        compiled_plans = sdk._compile_derivation_input(derivation)
        if len(compiled_plans) != 1:
            raise SDKStoreError(
                "inference must compile to exactly one plan", path=path
            )
        try:
            return _compiled_derivation_plan_to_application(
                compiled_plans[0], mode=engine, engine_options=None
            )
        except ValueError as exc:
            raise SDKStoreError(f"invalid derivation input: {exc}", path=path) from exc

    if isinstance(derivation, (ApplicationRule, _RuleExpr)):
        if not isinstance(head, ApplicationRule):
            raise SDKStoreError(
                "a Rule or RuleExpr needs head= Rule: it states what holds, not "
                "what it concludes",
                path=path,
            )
        try:
            return compile_derivation_plan(derivation, head=head, engine=engine)
        except RuleExprError as exc:
            raise SDKStoreError(f"invalid derivation input: {exc}", path=path) from exc

    raise SDKStoreError(
        "derivation must be SDK Inference, application Rule, or RuleExpr", path=path
    )


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
    """Reject anything that is not an ``FactOverlay`` instance.

    Used by Fact Overlay Check (``$.check_fact_overlay.overlay``) and
    ProofFrame Recheck (``$.recheck_proof_frame.overlay``) to enforce the
    G2 §5.1 + §5.2 lock that the SDK boundary accepts only
    ``FactOverlay`` — narrower than the application
    ``FactOverlayCheckRequest.overlay`` field which also tolerates
    ``tuple[ReplaceFact, ...]``. Rejects ``None``; G3 callers that
    accept a None default use ``validate_optional_evaluation_overlay``
    instead.
    """

    if not isinstance(value, FactOverlay):
        raise SDKStoreError("overlay must be FactOverlay", path=path)


def validate_rule(rule: Any, *, path: str) -> None:
    """Reject anything that is neither an SDK ``Rule`` nor an application ``Rule``.

    The type guard on its own. Shells use :func:`resolve_rule_spec`, which also
    returns the spec the runtime takes.
    """

    from factgraph.application.protocol import Rule as ApplicationRule

    if not isinstance(rule, (Rule, ApplicationRule)):
        raise SDKStoreError("rule must be SDK Rule or application Rule", path=path)


def resolve_rule_spec(sdk: Any, rule: Any, *, path: str) -> Any:
    """Resolve either rule form to the ``RuleSpec`` the rule-overlay runtimes take.

    The runtimes never asked for the SDK DSL ``Rule``; they take a ``RuleSpec``.
    Both forms compile to one through the same ``SDKStore._compile_rule_input``:
    the SDK ``Rule`` through its authoring payload, the application ``Rule``
    through its own ``to_rule_spec``, which lowers the body with the same
    ``lower_ast_to_where_ir`` the derivation lowering uses.

    Replaces the ``RuleSpec(...)`` each rule-overlay shell used to assemble by
    hand from the compiled dict — one place, one shape.
    """

    from factgraph.core.rules.rule_ir import RuleCompileError, RuleSpec

    validate_rule(rule, path=path)
    try:
        compiled = sdk._compile_rule_input(rule)
        return RuleSpec(
            rule_id=compiled["rule_id"],
            version=compiled["version"],
            select_vars=list(compiled["select_vars"]),
            where=list(compiled["where"]),
            expose=bool(compiled.get("expose", False)),
        )
    except (SDKStoreError, RuleCompileError) as exc:
        raise SDKStoreError(f"invalid rule: {exc}", path=path) from exc


def validate_support_artifact(value: Any, *, path: str) -> None:
    """Reject anything that is not a ``ProofReceipt`` instance.

    Used by G2 ProofFrame Recheck
    (``$.recheck_proof_frame.support_artifact``) and the three G3
    rule-overlay shells (``$.<method>.support``). Promoted from G2
    ProofFrame's local helper at G3 Phase 0 hygiene per the §5.2
    deferred trigger ("until G3/G5 also need them").
    """

    if not isinstance(value, ProofReceipt):
        raise SDKStoreError("support must be ProofReceipt", path=path)


def validate_optional_evaluation_overlay(value: Any, *, path: str) -> None:
    """Reject non-``FactOverlay`` and non-empty ``FactOverlay``.

    G3 rule-overlay A helpers (``build_rule_disable_request`` /
    ``build_rule_literal_replace_request`` /
    ``build_rule_add_condition_request``) construct the single rule-action
    overlay internally; SDK callers pass either ``None`` or an empty
    ``FactOverlay()``. This validator pre-rejects (a) non-
    ``FactOverlay`` non-None inputs, and (b) non-empty
    ``FactOverlay`` (i.e. with any ``fact_actions`` or
    ``rule_actions``). After this check, the application-layer
    ``_request_overlay(...)`` non-empty rejection becomes defensive /
    unreachable from SDK.

    Allows ``None`` because the rule-overlay shells default ``overlay``
    to ``None``; G2's ``validate_evaluation_overlay`` rejects ``None``
    because Fact Overlay and ProofFrame Recheck require an overlay.
    """

    if value is None:
        return
    if not isinstance(value, FactOverlay):
        raise SDKStoreError("overlay must be FactOverlay or None", path=path)
    if value.fact_actions or value.rule_actions:
        raise SDKStoreError(
            "overlay must be empty FactOverlay (or None); "
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
    "resolve_derivation_plan",
    "resolve_rule_spec",
    "resolve_runtime_registry",
    "validate_binding",
    "validate_derivation",
    "validate_evaluation_overlay",
    "validate_optional_evaluation_overlay",
    "validate_rule",
    "validate_support_artifact",
]
