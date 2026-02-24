from __future__ import annotations

# PR-7 regression anchor: changes to where_ast_validate / where_eval / where_compile
# must preserve these case expectations unless the where contract is intentionally
# version-bumped (e.g. where_v2 / export_v2 / policy_v2).

import os
from dataclasses import dataclass
from typing import Any, Iterable, Literal
from unittest.mock import patch

from factpy_kernel.adapters.souffle.where_compile import compile_where_to_query_dl
from factpy_kernel.core.rules.where_ast import WhereASTError, parse_where_ir_to_ast
from factpy_kernel.core.rules.where_ast_validate import (
    WhereASTValidationError,
    validate_where_ast,
)
from factpy_kernel.core.rules.where_eval import WhereValidationError, evaluate_where

FAIL_SHAPE = "shape"
FAIL_DATAFLOW_EQ = "dataflow_eq"
FAIL_DATAFLOW_BUILTIN = "dataflow_builtin"
FAIL_NOT_CORRELATION = "not_correlation"
FAIL_NOT_UNBOUND_OUTER = "not_unbound_outer"
FAIL_RULEREF_SHAPE = "ruleref_shape"
FAIL_MODE_CAPABILITY = "mode_capability"

FAILURE_KINDS = {
    FAIL_SHAPE,
    FAIL_DATAFLOW_EQ,
    FAIL_DATAFLOW_BUILTIN,
    FAIL_NOT_CORRELATION,
    FAIL_NOT_UNBOUND_OUTER,
    FAIL_RULEREF_SHAPE,
    FAIL_MODE_CAPABILITY,
}

Target = Literal["ast", "eval", "compile"]
Mode = Literal["python", "souffle"]


@dataclass(frozen=True)
class WhereGoldenCase:
    case_id: str
    title: str
    where_ir: Any
    mode: Mode | None
    expect: Literal["ok", "error"]
    error_kind: str | None = None
    notes: str | None = None
    targets: tuple[Target, ...] = ("ast", "eval", "compile")
    capabilities: dict[str, Any] | None = None


def iter_cases(*, mode: Mode | None = None, target: Target | None = None) -> list[WhereGoldenCase]:
    out: list[WhereGoldenCase] = []
    for case in _CASES:
        if mode is not None and case.mode is not None and case.mode != mode:
            continue
        if target is not None and target not in case.targets:
            continue
        out.append(case)
    return out


def default_eval_view_facts() -> dict[str, list[tuple[Any, ...]]]:
    return {
        "x:v": [("e1", 3), ("e2", 10)],
        "person:country": [("p1", "de"), ("p2", "fr")],
        "person:block_reason": [("p1", "ban"), ("p1", "warning")],
        "x:local": [("l1",)],
    }


def default_compile_schema_ir() -> dict[str, Any]:
    return {
        "predicates": [
            {
                "pred_id": "x:v",
                "cardinality": "functional",
                "arg_specs": [
                    {"name": "e", "type_domain": "entity_ref"},
                    {"name": "v", "type_domain": "int"},
                ],
            },
            {
                "pred_id": "person:country",
                "cardinality": "functional",
                "arg_specs": [
                    {"name": "e", "type_domain": "entity_ref"},
                    {"name": "country", "type_domain": "string"},
                ],
            },
            {
                "pred_id": "person:block_reason",
                "cardinality": "multi",
                "arg_specs": [
                    {"name": "e", "type_domain": "entity_ref"},
                    {"name": "reason", "type_domain": "string"},
                ],
            },
            {
                "pred_id": "x:local",
                "cardinality": "multi",
                "arg_specs": [
                    {"name": "x", "type_domain": "entity_ref"},
                ],
            },
        ]
    }


def run_ast_validate_case(case: WhereGoldenCase) -> Any:
    ast = parse_where_ir_to_ast(case.where_ir)
    validate_where_ast(ast, mode=case.mode or "python", capabilities=case.capabilities)
    return ast


def run_eval_case(case: WhereGoldenCase, *, gate_enabled: bool) -> Any:
    env = {"FACTPY_WHERE_AST_VALIDATE": "1" if gate_enabled else "0"}
    with patch.dict(os.environ, env):
        return evaluate_where(default_eval_view_facts(), case.where_ir)


def run_compile_case(case: WhereGoldenCase, *, gate_enabled: bool) -> str:
    env = {"FACTPY_WHERE_AST_VALIDATE": "1" if gate_enabled else "0"}
    with patch.dict(os.environ, env):
        return compile_where_to_query_dl(
            schema_ir=default_compile_schema_ir(),
            where=case.where_ir,
            query_rel=f"q_{case.case_id.replace('-', '_')}",
        )


def classify_error_category(exc: Exception) -> str | None:
    details = getattr(exc, "details", None)
    if isinstance(details, dict):
        msg = str(details.get("message") or str(exc))
        ast_error_code = details.get("ast_error_code") or details.get("error_code") or details.get("code")
        if ast_error_code == "WhereASTValidationError":
            return _classify_from_message(msg)
    return _classify_from_message(str(exc))


def assert_error_category(exc: Exception, expected_kind: str) -> None:
    if expected_kind not in FAILURE_KINDS:
        raise AssertionError(f"unknown expected failure kind: {expected_kind}")
    got = classify_error_category(exc)
    if got == expected_kind:
        return
    # Fallback for legacy path (gate off) where messages may be coarser.
    msg = str(exc)
    if expected_kind == FAIL_SHAPE and any(
        token in msg for token in ("atom must be", "invalid atom structure", "where ", "not body ")
    ):
        return
    if expected_kind in {FAIL_DATAFLOW_BUILTIN, FAIL_NOT_UNBOUND_OUTER} and "bound earlier in branch" in msg:
        return
    if expected_kind == FAIL_NOT_UNBOUND_OUTER and "variable must be bound before filter" in msg:
        return
    if expected_kind == FAIL_RULEREF_SHAPE and "ruleref" in msg.lower():
        return
    raise AssertionError(f"error category mismatch: expected={expected_kind}, got={got}, message={msg}")


def _classify_from_message(msg: str) -> str | None:
    text = (msg or "").lower()
    if "outer bound variable" in text or "not body free vars" in text:
        return FAIL_NOT_CORRELATION
    if "rule refatom" in text or "ruleref" in text:
        return FAIL_RULEREF_SHAPE
    if "op not allowed" in text or "not allowed in this mode" in text:
        return FAIL_MODE_CAPABILITY
    if "eq requires at least one bound/constant side" in text:
        return FAIL_DATAFLOW_EQ
    if "input variable must be bound before use" in text:
        return FAIL_DATAFLOW_BUILTIN
    if "variable must be bound before filter" in text:
        return FAIL_NOT_UNBOUND_OUTER
    if "bound earlier in branch" in text:
        # Ambiguous without more context (builtin input vs not-body unbound outer).
        return None
    if any(
        token in text
        for token in (
            "must be non-empty",
            "atom must be",
            "unsupported atom",
            "unsupported whereexpr",
            "branches must be non-empty",
            "expects ",
            "must be list",
            "invalid atom structure",
        )
    ):
        return FAIL_SHAPE
    return None


_CASES: tuple[WhereGoldenCase, ...] = (
    WhereGoldenCase(
        case_id="ok-eq-bind-const",
        title="eq binds var from constant then compare",
        where_ir=[("pred", "x:v", ["$e", "$x"]), ("eq", "$y", 4), ("ge", "$x", "$y")],
        mode=None,
        expect="ok",
        targets=("ast", "eval"),
    ),
    WhereGoldenCase(
        case_id="err-eq-unbound-both",
        title="eq with two unresolved vars is illegal",
        where_ir=[("eq", "$x", "$y")],
        mode=None,
        expect="error",
        error_kind=FAIL_DATAFLOW_EQ,
    ),
    WhereGoldenCase(
        case_id="err-eq-order",
        title="eq cannot use later-bound var",
        where_ir=[("eq", "$x", "$y"), ("pred", "x:v", ["$e", "$y"])],
        mode=None,
        expect="error",
        error_kind=FAIL_DATAFLOW_EQ,
    ),
    WhereGoldenCase(
        case_id="ok-builtin-binds-output",
        title="builtin binds output z when inputs are bound",
        where_ir=[("pred", "x:v", ["$e", "$x"]), ("addc", "$y", "$x", 1), ("ge", "$y", 2)],
        mode=None,
        expect="ok",
    ),
    WhereGoldenCase(
        case_id="err-builtin-input-unbound",
        title="builtin rejects unbound input",
        where_ir=[("add", "$z", "$x", 1)],
        mode=None,
        expect="error",
        error_kind=FAIL_DATAFLOW_BUILTIN,
    ),
    WhereGoldenCase(
        case_id="ok-builtin-eq-cross",
        title="builtin output then eq use is legal",
        where_ir=[("pred", "x:v", ["$e", "$x"]), ("addc", "$z", "$x", 2), ("eq", "$y", "$z")],
        mode=None,
        expect="ok",
    ),
    WhereGoldenCase(
        case_id="err-builtin-eq-cross-order",
        title="eq using builtin output before builtin is illegal",
        where_ir=[("eq", "$y", "$z"), ("pred", "x:v", ["$e", "$x"]), ("addc", "$z", "$x", 2)],
        mode=None,
        expect="error",
        error_kind=FAIL_DATAFLOW_EQ,
    ),
    WhereGoldenCase(
        case_id="ok-not-correlation-local",
        title="not uses outer var and local join var",
        where_ir=[
            ("pred", "person:country", ["$p", "$c"]),
            ("not", [("pred", "person:block_reason", ["$p", "$r"]), ("eq", "$r", "ban")]),
        ],
        mode=None,
        expect="ok",
    ),
    WhereGoldenCase(
        case_id="err-not-no-correlation",
        title="not body without outer correlation is illegal",
        where_ir=[
            ("pred", "person:country", ["$p", "$c"]),
            ("not", [("pred", "x:local", ["$x"]), ("eq", "$x", 1)]),
        ],
        mode=None,
        expect="error",
        error_kind=FAIL_NOT_CORRELATION,
    ),
    WhereGoldenCase(
        case_id="err-not-unbound-outer",
        title="not body references external var not yet bound",
        where_ir=[
            ("pred", "person:country", ["$p", "$c"]),
            ("not", [("pred", "person:block_reason", ["$p", "$r"]), ("gt", "$age", 18)]),
        ],
        mode=None,
        expect="error",
        error_kind=FAIL_NOT_UNBOUND_OUTER,
    ),
    WhereGoldenCase(
        case_id="ok-not-or-local-branches",
        title="not OR-of-AND allows branch-local vars with correlated outer var",
        where_ir=[
            ("pred", "person:country", ["$p", "$c"]),
            (
                "not",
                [
                    [("pred", "person:block_reason", ["$p", "$r"]), ("eq", "$r", "ban")],
                    [("pred", "person:country", ["$p", "xx"])],
                ],
            ),
        ],
        mode=None,
        expect="ok",
    ),
    WhereGoldenCase(
        case_id="err-ruleref-shape",
        title="ruleref shape invalid in AST validator",
        where_ir=[("ruleref", "", None, ["$x"])],
        mode="python",
        expect="error",
        error_kind=FAIL_RULEREF_SHAPE,
        targets=("ast",),
    ),
    WhereGoldenCase(
        case_id="err-mode-capability-builtin",
        title="builtin denied by capability profile",
        where_ir=[("neg", "$y", "$x")],
        mode="souffle",
        expect="error",
        error_kind=FAIL_MODE_CAPABILITY,
        targets=("ast",),
        capabilities={"builtin_allow": {"add"}},
    ),
    WhereGoldenCase(
        case_id="err-shape-arity",
        title="atom arity mismatch (pred tuple too short)",
        where_ir=[("pred",)],
        mode=None,
        expect="error",
        error_kind=FAIL_SHAPE,
    ),
)
