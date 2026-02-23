"""Neo4j integration utilities.

This component is intentionally independent from existing providers.
It can import graph data from plain structures (example-style) and
from canonical ``Instance`` objects produced by this package.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from symir.errors import ProviderError
from symir.ir.fact_schema import FactSchema, FactView
from symir.ir.instance import Instance
from symir.mappers.renderers import CypherRenderer, RenderContext

SchemaDict = dict[str, Any]
RelKey = tuple[str, str, str]
Runner = Callable[[str, dict[str, object]], None]


def _safe_ident(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", str(value))
    if not safe or not re.match(r"^[A-Za-z_]", safe):
        safe = f"L_{safe}"
    return safe


def _chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    if size <= 0:
        raise ProviderError("batch size must be positive.")
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def _is_number_str(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", text))


def _parse_number(text: str) -> object:
    text = text.strip()
    if re.fullmatch(r"-?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    if re.fullmatch(r"-?\d+\.\d+", text):
        try:
            return float(text)
        except ValueError:
            return text
    return text


def _maybe_coerce_numeric(values: list[object]) -> list[object]:
    str_vals = [item for item in values if isinstance(item, str)]
    if str_vals and all(_is_number_str(item) for item in str_vals):
        return [(_parse_number(item) if isinstance(item, str) else item) for item in values]
    return values


def read_col_csv(path: str, col: str) -> list[str]:
    rows: list[str] = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if col not in (reader.fieldnames or []):
            raise ProviderError(f"{path} missing column {col}, has {reader.fieldnames}")
        for row in reader:
            value = (row.get(col) or "").strip()
            if value:
                rows.append(value)
    return rows


def read_rel_csv(path: str, sub_col: str = "sub", obj_col: str = "obj") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if sub_col not in fields or obj_col not in fields:
            raise ProviderError(f"{path} must have columns {sub_col},{obj_col}; has {fields}")
        for row in reader:
            sub = (row.get(sub_col) or "").strip()
            obj = (row.get(obj_col) or "").strip()
            if sub and obj:
                rows.append((sub, obj))
    return rows


@dataclass(frozen=True)
class Neo4jCfg:
    uri: str
    user: str
    password: str
    database: str = "neo4j"


class Neo4jComponent:
    """Minimal Neo4j writer that can run generated Cypher batches."""

    def __init__(
        self,
        cfg: Neo4jCfg,
        *,
        runner: Runner | None = None,
        cypher_renderer: CypherRenderer | None = None,
    ) -> None:
        self.cfg = cfg
        self._runner = runner
        self._cypher_renderer = cypher_renderer or CypherRenderer()

    def run(self, query: str, params: dict[str, object] | None = None) -> None:
        payload = params or {}
        if self._runner is not None:
            self._runner(query, payload)
            return
        try:
            from neo4j import GraphDatabase  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise ProviderError(
                "neo4j driver is required for live execution. Install with `pip install neo4j`."
            ) from exc
        with GraphDatabase.driver(self.cfg.uri, auth=(self.cfg.user, self.cfg.password)) as driver:
            driver.verify_connectivity()
            with driver.session(database=self.cfg.database) as session:
                session.run(query, payload)

    def run_script(self, script: str) -> None:
        for stmt in [line.strip() for line in script.split(";") if line.strip()]:
            self.run(stmt)

    def execute_cypher(self, cypher: str) -> None:
        """Execute one or multiple Cypher statements separated by ';'."""
        self.run_script(cypher)

    def render_cypher_for_instances(
        self,
        schema: FactSchema | FactView,
        instances: Iterable[Instance],
    ) -> str:
        """Render Cypher script for instances without executing it."""
        registry = schema.schema if isinstance(schema, FactView) else schema
        materialized = list(instances)
        if not materialized:
            return ""
        return self._cypher_renderer.render_facts(
            materialized,
            RenderContext(schema=registry),
        )

    # -------- Example-style plain structure import --------
    def ensure_constraints_from_schema(self, schema: SchemaDict) -> None:
        nodes = schema.get("nodes", {})
        if not isinstance(nodes, dict):
            raise ProviderError("schema['nodes'] must be a dict.")
        for label, props in nodes.items():
            if not isinstance(props, list):
                raise ProviderError(f"schema['nodes'][{label}] must be a list of properties.")
            if props:
                pk = str(props[0])
            else:
                pk = "value"
            cname = f"{_safe_ident(str(label).lower())}_{_safe_ident(pk)}_unique"
            query = (
                f"CREATE CONSTRAINT {_safe_ident(cname)} IF NOT EXISTS "
                f"FOR (n:{_safe_ident(label)}) REQUIRE n.`{pk}` IS UNIQUE"
            )
            self.run(query)

    def import_graph(
        self,
        schema: SchemaDict,
        nodes: dict[str, list[object]],
        rels: dict[RelKey, list[tuple[object, object]]],
        *,
        batch: int = 5000,
    ) -> None:
        self.ensure_constraints_from_schema(schema)
        for label, values in nodes.items():
            node_props = schema.get("nodes", {}).get(label)
            if not isinstance(node_props, list):
                pk = "value"
            elif node_props:
                pk = str(node_props[0])
            else:
                pk = "value"
            self._import_nodes(label=label, pk=pk, values=values, batch=batch)

        # Build implicit dst nodes when destination labels are not declared.
        implicit_nodes: dict[str, list[object]] = {}
        for (_src, _rel, dst), pairs in rels.items():
            if dst not in schema.get("nodes", {}) and dst not in nodes:
                implicit_nodes.setdefault(dst, [])
                implicit_nodes[dst].extend([obj for _, obj in pairs])
        for label, values in implicit_nodes.items():
            seen: set[tuple[type, object]] = set()
            uniq: list[object] = []
            for value in values:
                marker = (type(value), value)
                if marker in seen:
                    continue
                seen.add(marker)
                uniq.append(value)
            self._import_nodes(label=label, pk="value", values=uniq, batch=batch)

        for (src, rel, dst), pairs in rels.items():
            src_props = schema.get("nodes", {}).get(src)
            dst_props = schema.get("nodes", {}).get(dst)
            src_pk = str(src_props[0]) if isinstance(src_props, list) and src_props else "value"
            dst_pk = str(dst_props[0]) if isinstance(dst_props, list) and dst_props else "value"
            self._import_rels(
                src_label=src,
                rel_type=rel,
                dst_label=dst,
                src_pk=src_pk,
                dst_pk=dst_pk,
                pairs=pairs,
                batch=batch,
            )

    def import_graph_from_csv_files(
        self,
        schema: SchemaDict,
        node_files: dict[str, str],
        rel_files: dict[RelKey, str],
        *,
        batch: int = 5000,
    ) -> None:
        nodes: dict[str, list[object]] = {}
        for label, path in node_files.items():
            props = schema.get("nodes", {}).get(label)
            pk = str(props[0]) if isinstance(props, list) and props else "value"
            nodes[label] = read_col_csv(path, pk)
        rels: dict[RelKey, list[tuple[object, object]]] = {}
        for key, path in rel_files.items():
            rels[key] = read_rel_csv(path, "sub", "obj")
        self.import_graph(schema=schema, nodes=nodes, rels=rels, batch=batch)

    # -------- Instance-based import (project-native) --------
    def ensure_constraints(self, schema: FactSchema | FactView) -> None:
        registry = schema.schema if isinstance(schema, FactView) else schema
        for predicate in registry.facts():
            keys = list(predicate.key_fields or [])
            if not keys:
                raise ProviderError(f"Fact {predicate.name} has no key_fields.")
            label = _safe_ident(predicate.name)
            if len(keys) == 1:
                key = keys[0]
                cname = _safe_ident(f"{predicate.name}_{key}_unique".lower())
                query = (
                    f"CREATE CONSTRAINT {cname} IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.`{key}` IS UNIQUE"
                )
            else:
                key_tuple = ", ".join(f"n.`{key}`" for key in keys)
                cname = _safe_ident(
                    f"{predicate.name}_{'_'.join(keys)}_unique".lower()
                )
                query = (
                    f"CREATE CONSTRAINT {cname} IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE ({key_tuple}) IS UNIQUE"
                )
            self.run(query)

    def import_instances(
        self,
        schema: FactSchema | FactView,
        instances: Iterable[Instance],
        *,
        batch: int = 5000,
    ) -> None:
        registry = schema.schema if isinstance(schema, FactView) else schema
        self.ensure_constraints(registry)
        _ = batch  # kept for backward-compatible signature
        script = self.render_cypher_for_instances(registry, instances)
        if script:
            self.run_script(script)

    # -------- Internal query builders --------
    def _import_nodes(self, *, label: str, pk: str, values: list[object], batch: int) -> None:
        values = _maybe_coerce_numeric(list(values))
        safe_label = _safe_ident(label)
        query = (
            "UNWIND $rows AS row\n"
            f"MERGE (n:{safe_label} {{`{pk}`: row.v}})"
        )
        for part in _chunks(values, batch):
            rows = [{"v": value} for value in part]
            self.run(query, {"rows": rows})

    def _import_rels(
        self,
        *,
        src_label: str,
        rel_type: str,
        dst_label: str,
        src_pk: str,
        dst_pk: str,
        pairs: list[tuple[object, object]],
        batch: int,
    ) -> None:
        if pairs:
            obj_vals = _maybe_coerce_numeric([obj for _, obj in pairs])
            pairs = [(sub, obj_vals[idx]) for idx, (sub, _) in enumerate(pairs)]
        safe_src = _safe_ident(src_label)
        safe_dst = _safe_ident(dst_label)
        safe_rel = _safe_ident(rel_type.upper())
        query = (
            "UNWIND $rows AS row\n"
            f"MATCH (s:{safe_src} {{`{src_pk}`: row.sub}})\n"
            f"MATCH (o:{safe_dst} {{`{dst_pk}`: row.obj}})\n"
            f"MERGE (s)-[:{safe_rel}]->(o)"
        )
        for part in _chunks(pairs, batch):
            rows = [{"sub": sub, "obj": obj} for sub, obj in part]
            self.run(query, {"rows": rows})
