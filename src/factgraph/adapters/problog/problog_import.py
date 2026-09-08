from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import Any

from factgraph.adapters.problog._parsing import _split_top_level_args
from factgraph.core.derivation.candidates import DerivationOutput
from factgraph.core.rules.where_eval import WhereValidationError
from factgraph.core.store import builders as store_builders
from factgraph.core.store.ledger import Ledger
from factgraph.core.store.runtime import Store

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][+-]?\d+)?$")
_VARIABLE_RE = re.compile(r"[A-Z_][A-Za-z0-9_]*\Z")
_RESULT_TOKEN_RE = re.compile(
    r"(?:[+-]?(?:\d+\.\d*|\d*\.\d+|\d+)(?:[eE][+-]?\d+)?)"
    r"|(?:[^\W\d]\w*)", re.UNICODE,
)


class ProbLogImportError(Exception):
    pass


def parse_problog_output(raw: str, rule_spec: dict[str, Any], ledger: Ledger) -> list[DerivationOutput]:
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
        temp_outputs = _build_derivation_outputs_from_bindings(store, rule_spec, [binding])
        for output in temp_outputs:
            prev = prob_by_candidate_key.get(output.candidate_key)
            if prev is None or prob > prev:
                prob_by_candidate_key[output.candidate_key] = prob

    outputs = _build_derivation_outputs_from_bindings(store, rule_spec, bindings)
    out: list[DerivationOutput] = []
    for output in outputs:
        output_probability = prob_by_candidate_key.get(output.candidate_key)
        if output_probability is None:
            out.append(output)
        else:
            out.append(
                replace(
                    output,
                    confidence=float(output_probability),
                    confidence_kind="probability",
                )
            )
    return out


def _build_derivation_outputs_from_bindings(
    store: Store,
    rule_spec: dict[str, Any],
    bindings: list[dict[str, Any]],
) -> list[DerivationOutput]:
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
        return store_builders.entity_derivation_outputs_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            entity_spec=entity_spec,
            bindings=bindings,
        )

    schema_pred = store_builders.find_schema_pred(store, target_pred_id)
    if schema_pred is None:
        if not isinstance(head_vars, list) or not head_vars:
            raise WhereValidationError("head_vars must be non-empty list")
        return store_builders.query_style_derivation_outputs_from_bindings(
            store,
            derivation_id=derivation_id,
            version=version,
            target_pred_id=target_pred_id,
            head_vars=head_vars,
            bindings=bindings,
        )

    arg_specs = schema_pred.get("arg_specs")
    if not isinstance(arg_specs, list) or not arg_specs:
        raise WhereValidationError("target predicate arg_specs must be non-empty list")

    if not isinstance(head_vars, list) or len(head_vars) != len(arg_specs):
        raise WhereValidationError("head_vars length must match target arg_specs")

    return store_builders.derivation_outputs_from_bindings(
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
        if line.startswith(("%", "#")):
            continue

        split = _split_result_line(line)
        if split is None:
            if re.match(rf"^(?:query\(\s*)?{re.escape(query_pred)}\s*\(", line):
                raise ProbLogImportError("invalid query result or probability")
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
        free_variables = [_term_variables(token) for token in args]
        if any(free_variables):
            if prob == 0.0 and _is_query_variant(args, query_vars):
                continue
            raise ProbLogImportError("non-ground query result is not a zero query variant")
        binding = {
            var: _decode_term(token)
            for var, token in zip(query_vars, args)
        }
        out.append((binding, prob))
    return out


def _is_query_variant(args: list[str], query_vars: list[str]) -> bool:
    """Recognize only the whole variable-only query with its equality pattern."""
    if not args or not all(_VARIABLE_RE.fullmatch(arg) for arg in args):
        return False
    # Anonymous variables denote a fresh variable at every occurrence.
    identities = [("anonymous", i) if arg == "_" else ("named", arg)
                  for i, arg in enumerate(args)]
    return all(
        (query_vars[i] == query_vars[j]) == (identities[i] == identities[j])
        for i in range(len(args)) for j in range(i)
    )


def _term_variables(token: str) -> set[str]:
    """Inspect balanced output terms without interpreting quoted data as Prolog.

    This lexer does not import the optional engine library or decode compounds.
    Ground terms retain the existing decoder; free variables fail before it.
    """
    if not token:
        raise ProbLogImportError("empty result term")
    variables: set[str] = set()
    closers: list[str] = []
    expecting_value = True
    may_call = False
    last = ""
    i = 0
    while i < len(token):
        ch = token[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "'\"":
            if not expecting_value:
                raise ProbLogImportError("adjacent result terms")
            quote = ch
            i += 1
            while i < len(token):
                if token[i] == "\\":
                    i += 2
                elif token[i] == quote:
                    if i + 1 < len(token) and token[i + 1] == quote:
                        i += 2
                    else:
                        i += 1
                        break
                else:
                    i += 1
            else:
                raise ProbLogImportError("unterminated quoted result term")
            expecting_value, may_call, last = False, quote == "'", "value"
            continue
        if ch in "([{":
            if ch == "(":
                if expecting_value or not may_call:
                    raise ProbLogImportError("invalid result functor")
            elif not expecting_value:
                raise ProbLogImportError("adjacent result terms")
            closers.append({"(": ")", "[": "]", "{": "}"}[ch])
            expecting_value, may_call, last = True, False, ch
        elif ch in ")]}":
            if expecting_value and (ch == ")" or last != {"]": "[", "}": "{"}.get(ch)):
                raise ProbLogImportError("missing result term")
            if not closers or closers.pop() != ch:
                raise ProbLogImportError("unbalanced result term")
            expecting_value, may_call, last = False, False, ch
        elif ch in ",|:":
            if expecting_value or not closers or (ch == "|" and closers[-1] != "]"):
                raise ProbLogImportError("invalid result separator")
            expecting_value, may_call, last = True, False, ch
        else:
            match = _RESULT_TOKEN_RE.match(token, i)
            if match:
                if not expecting_value:
                    raise ProbLogImportError("adjacent result terms")
                word = match.group()
                if word[0].isupper() or word[0] == "_":
                    variables.add(word)
                expecting_value, may_call, last = False, word[0].islower(), "value"
                i = match.end()
                continue
            raise ProbLogImportError("invalid result token")
        i += 1
    if closers or expecting_value:
        raise ProbLogImportError("unbalanced result term")
    return variables


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
    if not math.isfinite(prob) or prob < 0.0 or prob > 1.0:
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
