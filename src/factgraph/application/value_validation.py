from __future__ import annotations

import re
from typing import Any

from .schema_runtime import PredicateInfo


class FieldValueValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        pred_info: PredicateInfo,
        reason: str,
        value: Any,
    ) -> None:
        super().__init__(message)
        self.code = "FIELD_VALUE_VALIDATION_FAILED"
        self.path = ("planned_ops", "value")
        self.details = {
            "pred_id": pred_info.pred_id,
            "owner_type": pred_info.owner_type,
            "field_name": pred_info.py_field_name,
            "reason": reason,
            "value_repr": repr(value),
        }


def validate_field_value(value: Any, *, pred_info: PredicateInfo) -> None:
    """Validate a planned field value against predicate schema constraints."""
    enum_values = pred_info.enum_values
    if enum_values is not None and value not in enum_values:
        raise FieldValueValidationError(
            f"value {value!r} is not allowed for {pred_info.pred_id}; "
            f"expected one of {tuple(enum_values)!r}",
            pred_info=pred_info,
            reason="enum_miss",
            value=value,
        )

    pattern = pred_info.pattern
    if pattern is None:
        return
    if not isinstance(value, str):
        raise FieldValueValidationError(
            f"pattern validation expects str value for {pred_info.pred_id}; got {type(value).__name__}",
            pred_info=pred_info,
            reason="pattern_non_string",
            value=value,
        )
    if re.fullmatch(pattern, value) is None:
        raise FieldValueValidationError(
            f"value {value!r} does not match pattern {pattern!r} for {pred_info.pred_id}",
            pred_info=pred_info,
            reason="pattern_miss",
            value=value,
        )


__all__ = ["FieldValueValidationError", "validate_field_value"]
