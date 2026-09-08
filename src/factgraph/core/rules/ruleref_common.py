from __future__ import annotations

from collections.abc import Callable
from typing import Any


def internal_rule_pred_id(rule_id: str, version: str) -> str:
    safe_rule = _sanitize(rule_id)
    safe_ver = _sanitize(version)
    return f"__rule_ref__{safe_rule}__{safe_ver}"


def resolve_exposed_rule_ref(
    registry: Any,
    *,
    rule_id: Any,
    version: Any,
    terms_len: int,
    error_factory: Callable[[str], Exception],
) -> Any:
    if not hasattr(registry, "resolve"):
        raise error_factory("registry must provide resolve(rule_id, version)")
    if not isinstance(rule_id, str) or not rule_id:
        raise error_factory("ruleref rule_id must be non-empty string")
    if not isinstance(version, str) or not version:
        raise error_factory("ruleref version must be non-empty string")
    if isinstance(terms_len, bool) or not isinstance(terms_len, int) or terms_len <= 0:
        raise error_factory("ruleref terms must be non-empty list")
    try:
        ref_spec = registry.resolve(rule_id, version)
    except Exception as exc:  # Normalize to caller error type.
        raise error_factory(str(exc)) from exc
    if not bool(getattr(ref_spec, "expose", False)):
        raise error_factory(f"RuleRef target must be expose=True: {rule_id}@{version}")
    select_vars = getattr(ref_spec, "select_vars", None)
    if not isinstance(select_vars, list):
        raise error_factory(f"RuleRef target has invalid select_vars: {rule_id}@{version}")
    if terms_len != len(select_vars):
        raise error_factory(
            f"RuleRef arity mismatch for {rule_id}@{version}: expected {len(select_vars)}, got {terms_len}"
        )
    return ref_spec


def _sanitize(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch.isalnum():
            out.append(ch.lower())
        else:
            out.append("_")
    return "".join(out)
