from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from factpy_kernel.core.rules.rule_ast import RuleASTError, parse_rule_ir_to_ast
from factpy_kernel.core.rules.rule_ast_validate import RuleASTValidationError, validate_rule_ast

FAIL_SHAPE = "shape"
FAIL_HEAD_SHAPE = "head_shape"
FAIL_WHERE_SHAPE = "where_shape"
FAIL_RULE_REF_SHAPE = "rule_ref_shape"

FAILURE_KINDS = {
    FAIL_SHAPE,
    FAIL_HEAD_SHAPE,
    FAIL_WHERE_SHAPE,
    FAIL_RULE_REF_SHAPE,
}


@dataclass(frozen=True)
class RuleGoldenCase:
    case_id: str
    title: str
    rule_ir: Any
    expect: Literal["ok", "error"]
    error_kind: str | None = None
    mode: Literal["python", "souffle"] = "python"
    where_capabilities: dict[str, Any] | None = None


def iter_cases() -> list[RuleGoldenCase]:
    return list(_CASES)


def run_rule_ast_validate_case(case: RuleGoldenCase) -> Any:
    ast = parse_rule_ir_to_ast(case.rule_ir)
    validate_rule_ast(ast, mode=case.mode, where_capabilities=case.where_capabilities)
    return ast


def classify_error_category(exc: Exception) -> str | None:
    text = str(exc or "").lower()
    path = str(getattr(exc, "path", "") or "")

    if "is required" in text or "must be dict" in text:
        return FAIL_SHAPE
    if "ruleref" in text:
        return FAIL_RULE_REF_SHAPE
    if path.startswith("$.rule.where") or text.startswith("where validation failed:"):
        return FAIL_WHERE_SHAPE
    if path.startswith("$.rule.head") or "head " in text:
        return FAIL_HEAD_SHAPE
    if any(token in text for token in ("rule_id", "version", "meta must be", "rule_ir")):
        return FAIL_SHAPE
    return None


def assert_error_category(exc: Exception, expected_kind: str) -> None:
    if expected_kind not in FAILURE_KINDS:
        raise AssertionError(f"unknown expected failure kind: {expected_kind}")
    got = classify_error_category(exc)
    if got == expected_kind:
        return
    raise AssertionError(f"error category mismatch: expected={expected_kind}, got={got}, message={exc}")


_CASES: tuple[RuleGoldenCase, ...] = (
    RuleGoldenCase(
        case_id="ok-minimal-and",
        title="minimal rule with AND where body",
        rule_ir={
            "rule_id": "q_country_rows",
            "version": "v1",
            "head": ("pred", "query:country_rows", ["$E", "$C"]),
            "where": [("pred", "person:country", ["$E", "$C"])],
        },
        expect="ok",
    ),
    RuleGoldenCase(
        case_id="ok-where-or",
        title="rule preserves OR-of-AND where shape",
        rule_ir={
            "rule_id": "q_country_or",
            "version": "v1",
            "head": ("pred", "query:country_or", ["$E"]),
            "where": [
                [("pred", "person:country", ["$E", "de"])],
                [("pred", "person:country", ["$E", "fr"])],
            ],
            "meta": {"owner": "tests"},
        },
        expect="ok",
    ),
    RuleGoldenCase(
        case_id="err-missing-head",
        title="missing head field is invalid rule IR shape",
        rule_ir={
            "rule_id": "q_missing_head",
            "version": "v1",
            "where": [("pred", "person:country", ["$E", "$C"])],
        },
        expect="error",
        error_kind=FAIL_SHAPE,
    ),
    RuleGoldenCase(
        case_id="err-missing-where",
        title="missing where field is invalid rule IR shape",
        rule_ir={
            "rule_id": "q_missing_where",
            "version": "v1",
            "head": ("pred", "query:x", ["$E"]),
        },
        expect="error",
        error_kind=FAIL_SHAPE,
    ),
    RuleGoldenCase(
        case_id="err-head-pred-type",
        title="head pred_id must be string",
        rule_ir={
            "rule_id": "q_bad_head",
            "version": "v1",
            "head": ("pred", 123, ["$E"]),
            "where": [("pred", "person:country", ["$E", "$C"])],
        },
        expect="error",
        error_kind=FAIL_HEAD_SHAPE,
    ),
    RuleGoldenCase(
        case_id="err-where-dataflow",
        title="where dataflow error bubbles as where-shape category at rule validator layer",
        rule_ir={
            "rule_id": "q_bad_where_flow",
            "version": "v1",
            "head": ("pred", "query:x", ["$X"]),
            "where": [("eq", "$X", "$Y")],
        },
        expect="error",
        error_kind=FAIL_WHERE_SHAPE,
    ),
    RuleGoldenCase(
        case_id="err-where-ruleref-shape",
        title="where ruleref shape error classified distinctly",
        rule_ir={
            "rule_id": "q_bad_ruleref",
            "version": "v1",
            "head": ("pred", "query:x", ["$E"]),
            "where": [("ruleref", "", "1.0.0", ["$E"])],
        },
        expect="error",
        error_kind=FAIL_RULE_REF_SHAPE,
    ),
)


__all__ = [
    "RuleGoldenCase",
    "RuleASTError",
    "RuleASTValidationError",
    "assert_error_category",
    "iter_cases",
    "run_rule_ast_validate_case",
]
