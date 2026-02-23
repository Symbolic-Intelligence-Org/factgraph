"""Renderer interfaces and ProbLog implementation for rule IR."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Optional, Callable, Literal

from symir.errors import RenderError
from symir.ir.rule_schema import Rule, Cond, Expr, Query
from symir.ir.expr_ir import Var, Const, Call, Unify, If, NotExpr, ExprIR, Ref
from symir.ir.fact_schema import FactSchema
from symir.ir.instance import Instance
from symir.rules.library import Library
from symir.rules.library_runtime import LibraryRuntime
from symir.probability import ProbabilityConfig, resolve_probability


@dataclass(frozen=True)
class RenderContext:
    schema: FactSchema
    library: Optional[Library] = None
    library_runtime: Optional[LibraryRuntime] = None


@dataclass
class _VarNamePolicy:
    mode: Literal["error", "sanitize", "prefix", "capitalize"]
    prefix: str
    _mapping: dict[str, str] = field(default_factory=dict)
    _used: set[str] = field(default_factory=set)

    _VALID_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9_]*$")
    _SAFE_PATTERN = re.compile(r"[^A-Za-z0-9_]")

    def render(self, name: str) -> str:
        if name in self._mapping:
            return self._mapping[name]
        candidate = self._candidate(name)
        unique = self._dedupe(candidate)
        self._mapping[name] = unique
        self._used.add(unique)
        return unique

    def _candidate(self, name: str) -> str:
        if self.mode == "error":
            if not self._is_valid(name):
                raise RenderError(
                    f"Invalid ProbLog variable name: {name}. "
                    "Use uppercase-leading names or set a non-error variable mode."
                )
            return name
        if self.mode == "capitalize":
            if not name:
                base = "V"
            else:
                base = name[0].upper() + name[1:]
            return self._force_valid(base)
        if self.mode == "prefix":
            token = self._sanitize_token(name)
            return self._force_valid(f"{self.prefix}{token}")
        # sanitize (default)
        base = self._sanitize_token(name)
        return self._force_valid(base)

    def _sanitize_token(self, name: str) -> str:
        cleaned = self._SAFE_PATTERN.sub("_", name)
        cleaned = cleaned.strip("_")
        if not cleaned:
            return "V"
        return cleaned

    def _force_valid(self, token: str) -> str:
        safe = self._SAFE_PATTERN.sub("_", token)
        if not safe:
            safe = "V"
        if safe[0].isdigit():
            safe = f"V_{safe}"
        if not safe[0].isupper():
            safe = safe[0].upper() + safe[1:]
        if not self._is_valid(safe):
            safe = f"V_{self._sanitize_token(safe)}"
            if not safe[0].isupper():
                safe = safe[0].upper() + safe[1:]
        return safe

    def _is_valid(self, name: str) -> bool:
        return bool(self._VALID_PATTERN.match(name))

    def _dedupe(self, base: str) -> str:
        if base not in self._used:
            return base
        idx = 2
        while f"{base}_{idx}" in self._used:
            idx += 1
        return f"{base}_{idx}"


class Renderer:
    """Base renderer interface."""

    backend: str = "base"

    def render_rule(self, rule: Rule, context: RenderContext) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def render_facts(  # pragma: no cover - interface
        self, facts: list[Instance], context: RenderContext
    ) -> str:
        raise NotImplementedError

    def render_query(  # pragma: no cover - interface
        self, query: Query, context: RenderContext
    ) -> str:
        raise NotImplementedError

    def render_queries(  # pragma: no cover - interface
        self, queries: list[Query], context: RenderContext
    ) -> str:
        raise NotImplementedError

    def render_program(  # pragma: no cover - interface
        self,
        facts: list[Instance],
        rules: list[Rule],
        context: RenderContext,
        queries: list[Query] | None = None,
    ) -> str:
        raise NotImplementedError


class ProbLogRenderer(Renderer):
    backend = "problog"

    def __init__(
        self,
        *,
        prob_config: ProbabilityConfig | None = None,
        var_mode: Literal["error", "sanitize", "prefix", "capitalize"] = "sanitize",
        var_prefix: str = "VAR_",
        rel_mode: Literal["none", "flattened", "composed"] = "none",
    ) -> None:
        self.prob_config = prob_config or ProbabilityConfig()
        self.var_mode = var_mode
        self.var_prefix = var_prefix
        self.rel_mode = rel_mode

    def render_rule(self, rule: Rule, context: RenderContext) -> str:
        configs = self._validated_render_configs(rule)
        mode, prefix = self._resolve_var_rendering(configs)
        rel_mode = self._resolve_rel_mode(configs)
        clauses: list[str] = []
        for idx, cond in enumerate(rule.conditions):
            var_policy = _VarNamePolicy(mode=mode, prefix=prefix)
            prob = resolve_probability(
                cond.prob,
                default_value=self.prob_config.default_rule_prob,
                policy=self.prob_config.missing_prob_policy,
                context=f"rule {rule.predicate.name} condition {idx}",
            )
            head_text = self._render_head(rule.predicate, prob, var_policy, rel_mode)
            body_text = self._render_body(
                cond,
                context,
                var_policy,
                head_predicate=rule.predicate,
                rel_mode=rel_mode,
            )
            clauses.append(f"{head_text} :- {body_text}.")
        return "\n".join(clauses)

    def render_facts(self, facts: list[Instance], context: RenderContext) -> str:
        lines: list[str] = []
        var_policy = _VarNamePolicy(
            mode=self.var_mode,
            prefix=self.var_prefix,
        )
        for idx, fact in enumerate(facts):
            prob = resolve_probability(
                fact.prob,
                default_value=self.prob_config.default_fact_prob,
                policy=self.prob_config.missing_prob_policy,
                context=f"fact {idx}",
            )
            pred_name, arity, runtime_handler = self._resolve_predicate(fact.schema_id, context)
            schema = context.schema.get(fact.schema_id)
            terms = [self._render_term(t, var_policy) for t in fact.to_terms(schema)]
            if runtime_handler is not None:
                atom = runtime_handler(terms)
            else:
                atom = f"{pred_name}({', '.join(terms)})" if arity > 0 else pred_name
            prefix = f"{prob}::" if prob is not None else ""
            lines.append(f"{prefix}{atom}.")
        return "\n".join(lines)

    def render_query(self, query: Query, context: RenderContext) -> str:
        var_policy = _VarNamePolicy(
            mode=self.var_mode,
            prefix=self.var_prefix,
        )
        if query.predicate_id is not None:
            pred_name, arity, runtime_handler = self._resolve_predicate(query.predicate_id, context)
        else:
            pred_name = query.predicate.name
            arity = query.predicate.arity
            runtime_handler = None
        terms = [self._render_term(t, var_policy) for t in query.terms]
        if runtime_handler is not None:
            atom = runtime_handler(terms)
        else:
            atom = f"{pred_name}({', '.join(terms)})" if arity > 0 else pred_name
        return f"query({atom})."

    def render_queries(self, queries: list[Query], context: RenderContext) -> str:
        return "\n".join(self.render_query(q, context) for q in queries)

    def render_program(
        self,
        facts: list[Instance],
        rules: list[Rule],
        context: RenderContext,
        queries: list[Query] | None = None,
    ) -> str:
        parts: list[str] = []
        if facts:
            parts.append(self.render_facts(facts, context))
        if rules:
            parts.append("\n".join(self.render_rule(rule, context) for rule in rules))
        if queries:
            parts.append(self.render_queries(queries, context))
        return "\n\n".join(part for part in parts if part)

    def _render_head(
        self,
        predicate,
        prob: float,
        var_policy: _VarNamePolicy,
        rel_mode: Literal["none", "flattened", "composed"],
    ) -> str:
        terms = ", ".join(self._render_term(t, var_policy) for t in self._head_terms(predicate, rel_mode))
        prefix = f"{prob}::" if prob is not None else ""
        if predicate.arity == 0:
            return f"{prefix}{predicate.name}"
        return f"{prefix}{predicate.name}({terms})"

    def _render_body(
        self,
        body: Cond,
        context: RenderContext,
        var_policy: _VarNamePolicy,
        *,
        head_predicate,
        rel_mode: Literal["none", "flattened", "composed"],
    ) -> str:
        rendered_literals: list[str] = []
        if rel_mode == "composed" and getattr(head_predicate, "kind", None) == "rel":
            rendered_literals.extend(
                self._render_rel_binding_literals(head_predicate, context, var_policy)
            )
        for lit in body.literals:
            text = self._render_literal(lit, context, var_policy)
            if text not in rendered_literals:
                rendered_literals.append(text)
        if not rendered_literals:
            return "true"
        return ", ".join(rendered_literals)

    def _render_literal(self, literal, context: RenderContext, var_policy: _VarNamePolicy) -> str:
        if isinstance(literal, Ref):
            return self._render_ref(literal, context, negate=literal.negated, var_policy=var_policy)
        if isinstance(literal, Expr):
            return self._render_expr(literal.expr, context, var_policy)
        raise RenderError("Unknown literal type.")

    def _render_expr(self, expr: ExprIR, context: RenderContext, var_policy: _VarNamePolicy) -> str:
        if isinstance(expr, Var):
            return var_policy.render(expr.name)
        if isinstance(expr, Const):
            return self._render_const(expr)
        if isinstance(expr, Ref):
            if expr.negated:
                raise RenderError("Negated ref not allowed in expression context.")
            return self._render_ref(expr, context, negate=False, var_policy=var_policy)
        if isinstance(expr, Unify):
            return (
                f"{self._render_expr(expr.lhs, context, var_policy)} = "
                f"{self._render_expr(expr.rhs, context, var_policy)}"
            )
        if isinstance(expr, Call):
            return self._render_call(expr, context, var_policy)
        if isinstance(expr, If):
            cond = self._render_expr(expr.cond, context, var_policy)
            then = self._render_expr(expr.then, context, var_policy)
            else_ = self._render_expr(expr.else_, context, var_policy)
            # ProbLog does not support '->' control syntax; use branch-style disjunction.
            # (Cond, Then ; \+ Cond, Else)
            return f"(({cond}, {then}) ; (\\+ ({cond}), {else_}))"
        if isinstance(expr, NotExpr):
            return f"\\+ {self._render_expr(expr.expr, context, var_policy)}"
        raise RenderError(f"Unsupported ExprIR type: {type(expr)}")

    def _render_call(self, call: Call, context: RenderContext, var_policy: _VarNamePolicy) -> str:
        op = call.op
        args = [self._render_expr(arg, context, var_policy) for arg in call.args]
        builtin_infix = {
            "eq": "=",
            "ne": "\\=",
            "lt": "<",
            "le": "=<",
            "gt": ">",
            "ge": ">=",
        }
        builtin_arith = {
            "add": "+",
            "sub": "-",
            "mul": "*",
            "div": "/",
            "mod": "mod",
        }
        if op in builtin_infix and len(args) == 2:
            return f"{args[0]} {builtin_infix[op]} {args[1]}"
        if op in builtin_arith and len(args) == 2:
            if op == "mod":
                return f"{args[0]} mod {args[1]}"
            return f"{args[0]} {builtin_arith[op]} {args[1]}"
        if context.library_runtime:
            handler = context.library_runtime.get(op, len(args), "expr", self.backend)
            if handler is not None:
                return handler(args)
        mapping = None
        if context.library:
            mapping = context.library.resolve_mapping(op, len(args), "expr", self.backend)
        if mapping:
            return mapping.format(*args)
        return f"{op}({', '.join(args)})"

    def _render_term(self, term, var_policy: _VarNamePolicy) -> str:
        if isinstance(term, Var):
            return var_policy.render(term.name)
        if isinstance(term, Const):
            return self._render_const(term)
        if isinstance(term, (str, int, float, bool)):
            return self._render_const(Const(value=term))
        raise RenderError("Ref term must be Var/Const.")

    def _head_terms(
        self,
        predicate,
        rel_mode: Literal["none", "flattened", "composed"],
    ) -> list[ExprIR]:
        if getattr(predicate, "kind", None) == "rel" and rel_mode in {"none", "composed"}:
            prop_names = [
                arg.name
                for arg in (getattr(predicate, "props", None) or [])
                if getattr(arg, "name", None)
            ]
            return [Var("Sub"), Var("Obj"), *[Var(name) for name in prop_names]]
        return [Var(arg.name) for arg in predicate.signature]

    def _render_ref(
        self,
        ref: Ref,
        context: RenderContext,
        *,
        negate: bool,
        var_policy: _VarNamePolicy,
    ) -> str:
        pred_name, arity, runtime_handler = self._resolve_predicate(ref.schema, context)
        terms = [self._render_term(t, var_policy) for t in ref.terms]
        if runtime_handler is not None:
            atom = runtime_handler(terms)
        else:
            atom = f"{pred_name}({', '.join(terms)})" if arity > 0 else pred_name
        return f"\\+ {atom}" if negate else atom

    def _render_rel_binding_literals(
        self,
        rel_predicate,
        context: RenderContext,
        var_policy: _VarNamePolicy,
    ) -> list[str]:
        sub_schema_id = getattr(rel_predicate, "sub_schema_id", None)
        obj_schema_id = getattr(rel_predicate, "obj_schema_id", None)
        if not sub_schema_id or not obj_schema_id:
            raise RenderError("Rel-head binding requires valid sub/obj schema_id.")
        sub_schema = context.schema.get(sub_schema_id)
        obj_schema = context.schema.get(obj_schema_id)
        sub_terms = [Var(f"sub_{arg.name}") for arg in sub_schema.signature if arg.name]
        obj_terms = [Var(f"obj_{arg.name}") for arg in obj_schema.signature if arg.name]

        sub_ref = Ref(schema=sub_schema, terms=sub_terms)
        obj_ref = Ref(schema=obj_schema, terms=obj_terms)
        sub_bind = Unify(lhs=Var("Sub"), rhs=sub_ref)
        obj_bind = Unify(lhs=Var("Obj"), rhs=obj_ref)

        return [
            self._render_expr(sub_bind, context, var_policy),
            self._render_expr(obj_bind, context, var_policy),
            self._render_ref(sub_ref, context, negate=False, var_policy=var_policy),
            self._render_ref(obj_ref, context, negate=False, var_policy=var_policy),
        ]

    def _validated_render_configs(self, rule: Rule) -> dict[str, object]:
        configs = dict(rule.render_configs or {})
        allowed = {"var_mode", "var_prefix", "rel_mode"}
        unknown = sorted(key for key in configs if key not in allowed)
        if unknown:
            raise RenderError(
                f"Unknown render_configs keys: {unknown}. "
                f"Supported keys: {sorted(allowed)}."
            )
        return configs

    def _resolve_var_rendering(
        self, configs: dict[str, object]
    ) -> tuple[Literal["error", "sanitize", "prefix", "capitalize"], str]:
        mode: str = self.var_mode
        prefix = self.var_prefix
        if "var_mode" in configs:
            mode = str(configs["var_mode"])
        if "var_prefix" in configs:
            prefix = str(configs["var_prefix"])
        normalized_mode = mode.strip().lower()
        allowed = {"error", "sanitize", "prefix", "capitalize"}
        if normalized_mode not in allowed:
            raise RenderError(
                f"Unknown problog var mode: {mode}. "
                f"Expected one of {sorted(allowed)}."
            )
        if not isinstance(prefix, str) or not prefix:
            prefix = "VAR_"
        return normalized_mode, prefix

    def _resolve_rel_mode(
        self, configs: dict[str, object]
    ) -> Literal["none", "flattened", "composed"]:
        mode: str = self.rel_mode
        if "rel_mode" in configs:
            mode = str(configs["rel_mode"])

        normalized_mode = mode.strip().lower()
        allowed = {"none", "flattened", "composed"}
        if normalized_mode not in allowed:
            raise RenderError(
                f"Unknown problog rel mode: {mode}. "
                f"Expected one of {sorted(allowed)}."
            )
        return normalized_mode  # type: ignore[return-value]

    def _render_const(self, const: Const) -> str:
        value = const.value
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if not isinstance(value, str):
            raise RenderError(f"Unsupported const type: {type(value)}")
        if value and value[0].islower() and value.replace("_", "").isalnum():
            return value
        escaped = value.replace("'", "\\'")
        return f"'{escaped}'"

    def _resolve_predicate(
        self, predicate_id: str, context: RenderContext
    ) -> tuple[str, int, Optional[Callable[[list[str]], str]]]:
        try:
            pred = context.schema.get(predicate_id)
            return pred.name, pred.arity, None
        except Exception:
            if context.library:
                spec = context.library.get_predicate_by_id(predicate_id)
                if spec:
                    handler = None
                    if context.library_runtime:
                        handler = context.library_runtime.get(spec.name, spec.arity, "predicate", self.backend)
                    mapped = context.library.resolve_mapping(spec.name, spec.arity, "predicate", self.backend)
                    return (mapped or spec.name), spec.arity, handler
        raise RenderError(f"Unknown predicate_id in renderer: {predicate_id}")


class PrologRenderer(ProbLogRenderer):
    backend = "prolog"


class DatalogRenderer(Renderer):
    backend = "datalog"

    def render_rule(self, rule: Rule, context: RenderContext) -> str:  # pragma: no cover - stub
        raise RenderError("Datalog renderer not implemented yet.")


class CypherRenderer(Renderer):
    backend = "cypher"

    def __init__(
        self,
        *,
        include_prob_in_rule_return: bool = True,
        uppercase_rel_type: bool = True,
    ) -> None:
        self.include_prob_in_rule_return = include_prob_in_rule_return
        self.uppercase_rel_type = uppercase_rel_type

    def render_rule(self, rule: Rule, context: RenderContext) -> str:
        queries: list[str] = []
        for idx, cond in enumerate(rule.conditions):
            lines = [f"// rule {rule.predicate.name} condition {idx}"]
            builder = _CypherRuleBuilder(self, context)
            builder.consume_literals(cond.literals)
            query = builder.render_rule_query(
                rule.predicate,
                prob=cond.prob if self.include_prob_in_rule_return else None,
            )
            lines.append(query)
            queries.append("\n".join(lines))
        return ";\n\n".join(queries) + ";"

    def render_facts(self, facts: list[Instance], context: RenderContext) -> str:
        statements: list[str] = []
        for instance in facts:
            pred = context.schema.get(instance.schema_id)
            if pred.kind == "fact":
                label = self._label(pred.name)
                key_fields = list(pred.key_fields or [])
                key_map = {key: instance.props[key] for key in key_fields}
                key_expr = self._map_literal(key_map)
                prop_expr = self._map_literal(instance.props)
                statements.append(
                    f"MERGE (n:{label} {key_expr})\n"
                    f"SET n += {prop_expr}"
                )
                continue

            payload = instance.to_dict(include_keys=True)
            sub_schema = context.schema.get(str(pred.sub_schema_id))
            obj_schema = context.schema.get(str(pred.obj_schema_id))
            sub_label = self._label(sub_schema.name)
            obj_label = self._label(obj_schema.name)
            rel_type = self._rel_type(pred.name)
            sub_key_expr = self._map_literal(dict(payload.get("sub_key") or {}))
            obj_key_expr = self._map_literal(dict(payload.get("obj_key") or {}))
            rel_prop_expr = self._map_literal(instance.props)
            statements.append(
                f"MATCH (s:{sub_label} {sub_key_expr})\n"
                f"MATCH (o:{obj_label} {obj_key_expr})\n"
                f"MERGE (s)-[r:{rel_type}]->(o)\n"
                f"SET r += {rel_prop_expr}"
            )
        return ";\n\n".join(statements) + (";" if statements else "")

    def render_query(self, query: Query, context: RenderContext) -> str:
        if query.predicate_id is not None:
            predicate = context.schema.get(query.predicate_id)
        elif query.predicate is not None:
            predicate = query.predicate
        else:
            raise RenderError("Query requires predicate_id or predicate.")
        if len(query.terms) != predicate.arity:
            raise RenderError("Query terms length must match predicate arity.")
        ref = Ref(schema=predicate, terms=list(query.terms))
        builder = _CypherRuleBuilder(self, context)
        builder.consume_literals([ref])
        return builder.render_query_projection(query.terms) + ";"

    def render_queries(self, queries: list[Query], context: RenderContext) -> str:
        return "\n\n".join(self.render_query(query, context).rstrip(";") + ";" for query in queries)

    def render_program(
        self,
        facts: list[Instance],
        rules: list[Rule],
        context: RenderContext,
        queries: list[Query] | None = None,
    ) -> str:
        parts: list[str] = []
        if facts:
            parts.append(self.render_facts(facts, context))
        if rules:
            parts.append("\n\n".join(self.render_rule(rule, context).rstrip(";") + ";" for rule in rules))
        if queries:
            parts.append(self.render_queries(queries, context))
        return "\n\n".join(part for part in parts if part)

    def _label(self, name: str) -> str:
        return f"`{name.replace('`', '``')}`"

    def _rel_type(self, name: str) -> str:
        rel = name.upper() if self.uppercase_rel_type else name
        return f"`{rel.replace('`', '``')}`"

    def _prop(self, alias: str, key: str) -> str:
        return f"{alias}.`{key.replace('`', '``')}`"

    def _literal(self, value: object) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
        raise RenderError(f"Unsupported Cypher literal type: {type(value)}")

    def _map_literal(self, data: dict[str, object]) -> str:
        items = [f"`{key.replace('`', '``')}`: {self._literal(value)}" for key, value in data.items()]
        return "{ " + ", ".join(items) + " }"


class _CypherRuleBuilder:
    def __init__(self, renderer: CypherRenderer, context: RenderContext) -> None:
        self.renderer = renderer
        self.context = context
        self.matches: list[str] = []
        self.where: list[str] = []
        self.bindings: dict[str, str] = {}
        self._counter = 0

    def consume_literals(self, literals: list[Ref | Expr]) -> None:
        for literal in literals:
            if isinstance(literal, Ref):
                if literal.negated:
                    self.where.append(self._render_negated_ref(literal))
                else:
                    self._consume_positive_ref(literal, allow_bind=True)
                continue
            if isinstance(literal, Expr):
                self._consume_expr(literal.expr)
                continue
            raise RenderError("Unsupported literal type for Cypher renderer.")

    def render_rule_query(self, head_predicate, prob: float | None) -> str:
        parts: list[str] = []
        if self.matches:
            parts.extend(self.matches)
        else:
            parts.append("WITH 1 AS _")
        if self.where:
            parts.append("WHERE " + " AND ".join(self.where))
        projections: list[str] = []
        for arg in head_predicate.signature:
            arg_name = arg.name or "Arg"
            expr = self.bindings.get(arg_name, "null")
            projections.append(f"{expr} AS `{arg_name}`")
        if prob is not None:
            projections.append(f"{prob} AS `prob`")
        parts.append("RETURN DISTINCT " + ", ".join(projections))
        return "\n".join(parts)

    def render_query_projection(self, terms: list[ExprIR]) -> str:
        parts: list[str] = []
        if self.matches:
            parts.extend(self.matches)
        else:
            parts.append("WITH 1 AS _")
        if self.where:
            parts.append("WHERE " + " AND ".join(self.where))
        seen_vars: set[str] = set()
        projections: list[str] = []
        const_idx = 0
        for term in terms:
            if isinstance(term, Var):
                expr = self.bindings.get(term.name)
                if expr is None:
                    raise RenderError(f"Unbound query variable: {term.name}")
                if term.name in seen_vars:
                    continue
                seen_vars.add(term.name)
                projections.append(f"{expr} AS `{term.name}`")
            elif isinstance(term, Const):
                const_idx += 1
                projections.append(f"{self.renderer._literal(term.value)} AS `const_{const_idx}`")
            else:
                raise RenderError("Query terms must be Var or Const.")
        if not projections:
            projections.append("1 AS `_`")
        parts.append("RETURN DISTINCT " + ", ".join(projections))
        return "\n".join(parts)

    def _consume_positive_ref(self, ref: Ref, *, allow_bind: bool) -> None:
        pred = self.context.schema.get(ref.schema)
        idx = self._counter
        self._counter += 1
        if pred.kind == "fact":
            node_alias = f"n{idx}"
            self.matches.append(f"MATCH ({node_alias}:{self.renderer._label(pred.name)})")
            for term, arg in zip(ref.terms, pred.signature):
                if arg.name is None:
                    raise RenderError(f"Predicate {pred.name} has unnamed signature argument.")
                prop_expr = self.renderer._prop(node_alias, arg.name)
                self._consume_term(term, prop_expr, allow_bind=allow_bind)
            return

        sub_schema = self.context.schema.get(str(pred.sub_schema_id))
        obj_schema = self.context.schema.get(str(pred.obj_schema_id))
        sub_alias = f"s{idx}"
        obj_alias = f"o{idx}"
        rel_alias = f"r{idx}"
        self.matches.append(
            f"MATCH ({sub_alias}:{self.renderer._label(sub_schema.name)})"
            f"-[{rel_alias}:{self.renderer._rel_type(pred.name)}]->"
            f"({obj_alias}:{self.renderer._label(obj_schema.name)})"
        )
        for term, arg in zip(ref.terms, pred.signature):
            if arg.name is None:
                raise RenderError(f"Predicate {pred.name} has unnamed signature argument.")
            if arg.role == "sub_key":
                key = arg.name[4:] if arg.name.startswith("sub_") else arg.name
                expr = self.renderer._prop(sub_alias, key)
            elif arg.role == "obj_key":
                key = arg.name[4:] if arg.name.startswith("obj_") else arg.name
                expr = self.renderer._prop(obj_alias, key)
            else:
                expr = self.renderer._prop(rel_alias, arg.name)
            self._consume_term(term, expr, allow_bind=allow_bind)

    def _render_negated_ref(self, ref: Ref) -> str:
        pred = self.context.schema.get(ref.schema)
        idx = self._counter
        self._counter += 1
        local_where: list[str] = []
        if pred.kind == "fact":
            node_alias = f"nn{idx}"
            match = f"MATCH ({node_alias}:{self.renderer._label(pred.name)})"
            for term, arg in zip(ref.terms, pred.signature):
                if arg.name is None:
                    raise RenderError(f"Predicate {pred.name} has unnamed signature argument.")
                expr = self.renderer._prop(node_alias, arg.name)
                local_where.append(self._negated_term_condition(term, expr))
            return self._exists_block(match, local_where, negate=True)

        sub_schema = self.context.schema.get(str(pred.sub_schema_id))
        obj_schema = self.context.schema.get(str(pred.obj_schema_id))
        sub_alias = f"ns{idx}"
        obj_alias = f"no{idx}"
        rel_alias = f"nr{idx}"
        match = (
            f"MATCH ({sub_alias}:{self.renderer._label(sub_schema.name)})"
            f"-[{rel_alias}:{self.renderer._rel_type(pred.name)}]->"
            f"({obj_alias}:{self.renderer._label(obj_schema.name)})"
        )
        for term, arg in zip(ref.terms, pred.signature):
            if arg.name is None:
                raise RenderError(f"Predicate {pred.name} has unnamed signature argument.")
            if arg.role == "sub_key":
                key = arg.name[4:] if arg.name.startswith("sub_") else arg.name
                expr = self.renderer._prop(sub_alias, key)
            elif arg.role == "obj_key":
                key = arg.name[4:] if arg.name.startswith("obj_") else arg.name
                expr = self.renderer._prop(obj_alias, key)
            else:
                expr = self.renderer._prop(rel_alias, arg.name)
            local_where.append(self._negated_term_condition(term, expr))
        return self._exists_block(match, local_where, negate=True)

    def _consume_expr(self, expr: ExprIR) -> None:
        if isinstance(expr, Unify):
            lhs_var = expr.lhs if isinstance(expr.lhs, Var) else None
            rhs_var = expr.rhs if isinstance(expr.rhs, Var) else None
            if lhs_var is not None and lhs_var.name not in self.bindings:
                rhs_expr = self._expr_value(expr.rhs)
                self.bindings[lhs_var.name] = rhs_expr
                return
            if rhs_var is not None and rhs_var.name not in self.bindings:
                lhs_expr = self._expr_value(expr.lhs)
                self.bindings[rhs_var.name] = lhs_expr
                return
            lhs_expr = self._expr_value(expr.lhs)
            rhs_expr = self._expr_value(expr.rhs)
            self.where.append(f"({lhs_expr} = {rhs_expr})")
            return
        self.where.append(self._expr_bool(expr))

    def _expr_bool(self, expr: ExprIR) -> str:
        if isinstance(expr, Ref):
            return self._render_negated_ref(expr) if expr.negated else self._render_exists_ref(expr)
        if isinstance(expr, NotExpr):
            return f"(NOT ({self._expr_bool(expr.expr)}))"
        if isinstance(expr, Call):
            return self._call(expr)
        if isinstance(expr, If):
            cond = self._expr_bool(expr.cond)
            then = self._expr_value(expr.then)
            else_ = self._expr_value(expr.else_)
            return f"(CASE WHEN {cond} THEN {then} ELSE {else_} END)"
        if isinstance(expr, Unify):
            lhs = self._expr_value(expr.lhs)
            rhs = self._expr_value(expr.rhs)
            return f"({lhs} = {rhs})"
        if isinstance(expr, (Var, Const)):
            return self._expr_value(expr)
        raise RenderError(f"Unsupported ExprIR type in Cypher renderer: {type(expr)}")

    def _expr_value(self, expr: ExprIR) -> str:
        if isinstance(expr, Var):
            bound = self.bindings.get(expr.name)
            if bound is None:
                raise RenderError(f"Unbound variable in Cypher expression: {expr.name}")
            return bound
        if isinstance(expr, Const):
            return self.renderer._literal(expr.value)
        if isinstance(expr, Call):
            return self._call(expr)
        if isinstance(expr, If):
            cond = self._expr_bool(expr.cond)
            then = self._expr_value(expr.then)
            else_ = self._expr_value(expr.else_)
            return f"(CASE WHEN {cond} THEN {then} ELSE {else_} END)"
        if isinstance(expr, Unify):
            lhs = self._expr_value(expr.lhs)
            rhs = self._expr_value(expr.rhs)
            return f"({lhs} = {rhs})"
        if isinstance(expr, Ref):
            return self._render_exists_ref(expr)
        if isinstance(expr, NotExpr):
            return f"(NOT ({self._expr_bool(expr.expr)}))"
        raise RenderError(f"Unsupported ExprIR value for Cypher renderer: {type(expr)}")

    def _call(self, call: Call) -> str:
        args = [self._expr_value(arg) for arg in call.args]
        infix = {
            "eq": "=",
            "ne": "<>",
            "lt": "<",
            "le": "<=",
            "gt": ">",
            "ge": ">=",
            "add": "+",
            "sub": "-",
            "mul": "*",
            "div": "/",
            "mod": "%",
        }
        if call.op in infix and len(args) == 2:
            return f"({args[0]} {infix[call.op]} {args[1]})"
        op = call.op.replace("`", "``")
        return f"{op}({', '.join(args)})"

    def _render_exists_ref(self, ref: Ref) -> str:
        pred = self.context.schema.get(ref.schema)
        idx = self._counter
        self._counter += 1
        local_where: list[str] = []
        if pred.kind == "fact":
            node_alias = f"en{idx}"
            match = f"MATCH ({node_alias}:{self.renderer._label(pred.name)})"
            for term, arg in zip(ref.terms, pred.signature):
                if arg.name is None:
                    raise RenderError(f"Predicate {pred.name} has unnamed signature argument.")
                expr = self.renderer._prop(node_alias, arg.name)
                local_where.append(self._negated_term_condition(term, expr))
            return self._exists_block(match, local_where, negate=False)

        sub_schema = self.context.schema.get(str(pred.sub_schema_id))
        obj_schema = self.context.schema.get(str(pred.obj_schema_id))
        sub_alias = f"es{idx}"
        obj_alias = f"eo{idx}"
        rel_alias = f"er{idx}"
        match = (
            f"MATCH ({sub_alias}:{self.renderer._label(sub_schema.name)})"
            f"-[{rel_alias}:{self.renderer._rel_type(pred.name)}]->"
            f"({obj_alias}:{self.renderer._label(obj_schema.name)})"
        )
        for term, arg in zip(ref.terms, pred.signature):
            if arg.name is None:
                raise RenderError(f"Predicate {pred.name} has unnamed signature argument.")
            if arg.role == "sub_key":
                key = arg.name[4:] if arg.name.startswith("sub_") else arg.name
                expr = self.renderer._prop(sub_alias, key)
            elif arg.role == "obj_key":
                key = arg.name[4:] if arg.name.startswith("obj_") else arg.name
                expr = self.renderer._prop(obj_alias, key)
            else:
                expr = self.renderer._prop(rel_alias, arg.name)
            local_where.append(self._negated_term_condition(term, expr))
        return self._exists_block(match, local_where, negate=False)

    def _exists_block(self, match: str, local_where: list[str], *, negate: bool) -> str:
        lines = ["NOT EXISTS {" if negate else "EXISTS {", f"  {match}"]
        if local_where:
            lines.append("  WHERE " + " AND ".join(local_where))
        lines.append("}")
        return "\n".join(lines)

    def _consume_term(self, term: ExprIR, prop_expr: str, *, allow_bind: bool) -> None:
        if isinstance(term, Const):
            self.where.append(f"({prop_expr} = {self.renderer._literal(term.value)})")
            return
        if isinstance(term, Var):
            bound = self.bindings.get(term.name)
            if bound is None:
                if not allow_bind:
                    raise RenderError(
                        f"Unsafe variable '{term.name}' in negated/existential ref for Cypher renderer."
                    )
                self.bindings[term.name] = prop_expr
                return
            self.where.append(f"({bound} = {prop_expr})")
            return
        raise RenderError("Ref term must be Var or Const.")

    def _negated_term_condition(self, term: ExprIR, prop_expr: str) -> str:
        if isinstance(term, Const):
            return f"({prop_expr} = {self.renderer._literal(term.value)})"
        if isinstance(term, Var):
            bound = self.bindings.get(term.name)
            if bound is None:
                raise RenderError(
                    f"Unsafe variable '{term.name}' in negated/existential ref for Cypher renderer."
                )
            return f"({prop_expr} = {bound})"
        raise RenderError("Ref term must be Var or Const.")
