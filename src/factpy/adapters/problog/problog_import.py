from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from factpy.adapters.problog._parsing import _split_top_level_args
from factpy.core.derivation.candidates import CandidateSet
from factpy.core.store import builders as store_builders
from factpy.core.store.ledger import Ledger
from factpy.core.store.runtime import Store
from factpy.core.rules.where_eval import WhereValidationError

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][+-]?\d+)?$")


class ProbLogImportError(Exception):
    pass


def parse_problog_output(raw: str, rule_spec: dict[str, Any], ledger: Ledger) -> list[CandidateSet]:
    if not isinstance(raw, str):
        raise ProbLogImportError("raw must be string")
    if not isinstance(rule_spec, dict):
        raise ProbLogImportError("rule_spec must be object")
    if not isinstance(ledger, Ledger):
        raise ProbLogImportError("ledger must be Ledger")

    store = rule_spec.get("store")
    if not isinstance(store, Store):
        raise ProbLogImportError("rule_spec.store must be Store")

    query_vars = rule_spec.get("query_vars", [])
    if not isinstance(query_vars, list):
        raise ProbLogImportError("rule_spec.query_vars must be list")
    if any(not isinstance(token, str) or not token.startswith("$") for token in query_vars):
        raise ProbLogImportError("rule_spec.query_vars must contain '$' variable tokens")

    query_pred = rule_spec.get("query_pred", "answer")
    if not isinstance(query_pred, str) or not query_pred:
        raise ProbLogImportError("rule_spec.query_pred must be non-empty string")

    parsed_rows = _parse_rows(raw, query_pred=query_pred, query_vars=query_vars)
    if not parsed_rows:
        return []

    max_prob_by_binding: dict[tuple[Any, ...], float] = {}
    binding_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for binding, prob in parsed_rows:
        key = _binding_key(binding, query_vars)
        prev = max_prob_by_binding.get(key)
        if prev is None or prob > prev:
            max_prob_by_binding[key] = prob
            binding_by_key[key] = binding

    bindings = [binding_by_key[key] for key in max_prob_by_binding]
    prob_by_candidate_key: dict[str, float] = {}
    for key, binding in binding_by_key.items():
        prob = max_prob_by_binding[key]
        temp_candidates = _build_candidates_from_bindings(store, rule_spec, [binding])
        for candidate in temp_candidates:
            prev = prob_by_candidate_key.get(candidate.candidate_key)
            if prev is None or prob > prev:
                prob_by_candidate_key[candidate.candidate_key] = prob

    candidates = _build_candidates_from_bindings(store, rule_spec, bindings)
    out: list[CandidateSet] = []
    for candidate in candidates:
        prob = prob_by_candidate_key.get(candidate.candidate_key)
        if prob is None:
            out.append(candidate)
        else:
            out.append(replace(candidate, confidence=float(prob), confidence_kind="probability"))
    return out


def _build_candidates_from_bindings(
    store: Store,
    rule_spec: dict[str, Any],
    bindings: list[dict[str, Any]],
) -> list[CandidateSet]:
    derivation_id = rule_spec.get("derivation_id")
    version = rule_spec.get("version")
    target_pred_id = rule_spec.get("target_pred_id")
    head_vars = rule_spec.get("head_vars")
    head = rule_spec.get("head")

    if not isinstance(derivation_id, str) or not derivation_id:
        raise ProbLogImportError("rule_spec.derivation_id must be non-empty string")
    if not isinstance(version, str) or not version:
        raise ProbLogImportError("rule_spec.version must be non-empty string")
    if not isinstance(target_pred_id, str) or not target_pred_id:
        raise ProbLogImportError("rule_spec.target_pred_id must be non-empty string")

    if isinstance(head, dict) and head.get("callee_kind") == "entity_type":
        entity_spec = store_builders.entity_spec_from_head(
            store,
            entity_type=target_pred_id,
            head=head,
        )
        return store_builders.entity_candidates_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            entity_spec=entity_spec,
            bindings=bindings,
        )

    schema_pred = store_builders.find_schema_pred(store, target_pred_id)
    if schema_pred is None:
        raise WhereValidationError(f"target predicate not found: {target_pred_id}")

    arg_specs = schema_pred.get("arg_specs")
    if not isinstance(arg_specs, list) or not arg_specs:
        raise WhereValidationError("target predicate arg_specs must be non-empty list")

    if not isinstance(head_vars, list) or len(head_vars) != len(arg_specs):
        raise WhereValidationError("head_vars length must match target arg_specs")

    return store_builders.candidates_from_bindings(
        store,
        derivation_id=derivation_id,
        version=version,
        target_pred_id=target_pred_id,
        arg_specs=arg_specs,
        head_vars=head_vars,
        schema_pred=schema_pred,
        bindings=bindings,
    )


def _parse_rows(
    raw: str,
    *,
    query_pred: str,
    query_vars: list[str],
) -> list[tuple[dict[str, Any], float]]:
    out: list[tuple[dict[str, Any], float]] = []
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("%") or line.startswith("#"):
            continue

        split = _split_result_line(line)
        if split is None:
            continue
        expr, prob_text = split

        if expr.startswith("query(") and expr.endswith(")"):
            expr = expr[6:-1].strip()

        name, args = _parse_predicate_expr(expr)
        if name != query_pred:
            continue
        if len(args) != len(query_vars):
            raise ProbLogImportError(
                f"query result arity mismatch: expected {len(query_vars)}, got {len(args)}"
            )
        prob = _parse_probability(prob_text)
        binding = {
            var: _decode_term(token)
            for var, token in zip(query_vars, args)
        }
        out.append((binding, prob))
    return out


def _split_result_line(line: str) -> tuple[str, str] | None:
    if "\t" in line:
        lhs, rhs = line.rsplit("\t", 1)
        lhs_text = lhs.strip()
        if lhs_text.endswith(":"):
            lhs_text = lhs_text[:-1].rstrip()
        return lhs_text, rhs.strip()
    if ":" in line:
        # F-PL-2: rsplit at rightmost colon; safe because _FLOAT_RE guard
        # rejects any split where rhs is not a valid float literal
        lhs, rhs = line.rsplit(":", 1)
        rhs_trimmed = rhs.strip()
        if rhs_trimmed and _FLOAT_RE.fullmatch(rhs_trimmed):
            return lhs.strip(), rhs_trimmed
    return None


def _parse_predicate_expr(expr: str) -> tuple[str, list[str]]:
    text = expr.strip()
    if not text:
        raise ProbLogImportError("empty predicate expression in ProbLog output")
    if "(" not in text:
        return text, []
    idx = text.find("(")
    if idx <= 0 or not text.endswith(")"):
        raise ProbLogImportError(f"invalid predicate expression: {expr}")
    name = text[:idx].strip()
    args_text = text[idx + 1 : -1].strip()
    if not name:
        raise ProbLogImportError(f"invalid predicate expression: {expr}")
    if args_text == "":
        return name, []
    return name, _split_top_level_args(args_text)


def _parse_probability(text: str) -> float:
    value = text.strip()
    if not _FLOAT_RE.fullmatch(value):
        raise ProbLogImportError(f"invalid probability value: {text}")
    prob = float(value)
    if prob < 0.0 or prob > 1.0:
        raise ProbLogImportError(f"probability out of range [0,1]: {prob}")
    return prob


def _decode_term(token: str) -> Any:
    text = token.strip()
    if not text:
        return ""

    if len(text) >= 2 and text[0] == "'" and text[-1] == "'":
        inner = text[1:-1]
        inner = inner.replace("''", "'").replace("\\\\", "\\")
        return inner
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    if text == "true":
        return True
    if text == "false":
        return False
    if _INT_RE.fullmatch(text):
        return int(text)
    if _FLOAT_RE.fullmatch(text):
        return float(text)
    return text


def _binding_key(binding: dict[str, Any], query_vars: list[str]) -> tuple[Any, ...]:
    return tuple((var, _freeze_value(binding.get(var))) for var in query_vars)


def _freeze_value(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze_value(item)) for key, item in value.items()))
    return value
