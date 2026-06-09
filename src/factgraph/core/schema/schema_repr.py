from __future__ import annotations

import re
from collections.abc import Iterable


class SchemaReprTemplateError(ValueError):
    """Raised when schema repr templates violate placeholder rules."""


_PLACEHOLDER_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)")
_MALFORMED_PERCENT_RE = re.compile(r"%(?![A-Za-z_])")
_RESERVED_PLACEHOLDERS = frozenset({"CLS", "ENT", "FLD"})


def validate_member_repr_template(template: str | None, *, field_name: str) -> None:
    """Validate a Field/Identity repr template.

    Member templates may reference only class/entity placeholders and the
    current field value placeholder. They cannot reference sibling fields.
    """

    if template is None:
        return
    _require_non_empty_template(template)
    _reject_reserved_field_name(field_name, label="field_name")
    for placeholder in _placeholders(template):
        if placeholder not in {"CLS", "ENT", "FLD"}:
            raise SchemaReprTemplateError(
                f"member repr references unsupported placeholder %{placeholder}; "
                "allowed placeholders are %CLS, %ENT, and %FLD"
            )


def validate_meta_repr_template(template: str | None, *, identity_field_names: Iterable[str]) -> None:
    """Validate an Entity.Meta repr template.

    Meta templates may reference the class placeholder and identity field
    placeholders. They cannot reference %ENT or %FLD.
    """

    if template is None:
        return
    _require_non_empty_template(template)
    identity_fields = tuple(identity_field_names)
    identity_set = set(identity_fields)
    for name in identity_fields:
        _reject_reserved_field_name(name, label="identity field")
    for placeholder in _placeholders(template):
        if placeholder == "CLS":
            continue
        if placeholder in {"ENT", "FLD"}:
            raise SchemaReprTemplateError(f"Meta.repr cannot reference %{placeholder}")
        if placeholder not in identity_set:
            raise SchemaReprTemplateError(
                f"Meta.repr references non-identity placeholder %{placeholder}"
            )


def _require_non_empty_template(template: object) -> None:
    if not isinstance(template, str) or not template:
        raise SchemaReprTemplateError("repr must be a non-empty string when provided")
    if _MALFORMED_PERCENT_RE.search(template):
        raise SchemaReprTemplateError("repr contains malformed percent placeholder")


def _placeholders(template: str) -> tuple[str, ...]:
    return tuple(match.group(1) for match in _PLACEHOLDER_RE.finditer(template))


def _reject_reserved_field_name(name: str, *, label: str) -> None:
    if name in _RESERVED_PLACEHOLDERS:
        raise SchemaReprTemplateError(f"{label} {name!r} conflicts with reserved repr placeholder")
