"""World adapter + native evaluation wrapper + result normalization (§5.4.3/§5.4.4).

EXPERIMENTAL / NON-NORMATIVE / NON-PUBLIC / NON-COMPATIBLE / NO SEMVER COMMITMENT

One fresh in-memory FactGraph per cell. Native engine only; typed failure on
fault, never a fallback. Expectations are evaluated server-side over the
normalized QueryResult (never inside the body). Explain targets one explicit
anchor; zero-row Explain uses the summary/expectation anchor, never row[0].
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from contracts import (
    EXECUTION_ENGINE_FAULT,
    EXPECTATION_SET_MODE_UNSUPPORTED,
    ProbeError,
    digest,
    exists_summary_result,
    rows_result,
    typed_failure_result,
)

from factgraph.sdk import Entity, FactGraph, Field, Identity


def _class_name(entity_type: str) -> str:
    return "".join(p.capitalize() for p in entity_type.split("_"))


def build_world(world: dict) -> tuple[FactGraph, dict]:
    """Dynamic Entity classes + facts -> fresh in-memory workspace."""
    entity_types = list(world.get("entity_types", ()))
    lookup = [et for et in entity_types if et.get("identity") not in (None, "value")]
    facts = list(world.get("facts", ()))

    classes: dict[str, type] = {}
    if lookup:
        assert len(lookup) == 1, "probe worlds declare at most one lookup entity type"
        et = lookup[0]
        idf = et["identity"]
        declared = {f["name"]: (int if f.get("type") == "int" else str) for f in et.get("fields", ())}
        # relational fact predicates (arity>=3: [pred, subj, value]) become fields
        for f in facts:
            if len(f) >= 3 and f[0] not in declared:
                declared[f[0]] = int if isinstance(f[2], int) else str
        attrs: dict[str, Any] = {"__annotations__": {}}
        attrs["__annotations__"][idf] = str
        attrs[idf] = Identity()
        for fname, ftype in declared.items():
            attrs["__annotations__"][fname] = ftype
            attrs[fname] = Field()
        cls = type(_class_name(et["name"]), (Entity,), attrs)
        classes[et["name"]] = cls
    else:
        # scalar world: singleton World carrier
        preds: dict[str, type] = {}
        for f in facts:
            preds[f[0]] = int if isinstance(f[1], int) else str
        attrs = {"__annotations__": {"key": str}, "key": Identity()}
        for pname, ptype in preds.items():
            attrs["__annotations__"][pname] = ptype
            attrs[pname] = Field()
        cls = type("World", (Entity,), attrs)
        classes["__world__"] = cls

    fg = FactGraph.create(schema_classes=list(classes.values()))

    refs: dict[str, Any] = {}
    if lookup:
        et = lookup[0]
        cls = classes[et["name"]]
        idf = et["identity"]
        subjects = []
        for f in facts:
            if len(f) >= 3 and f[1] not in refs:
                subjects.append(f[1])
                refs[f[1]] = fg.entities.create(cls, **{idf: f[1]})
        multi_guard: set = set()
        for f in facts:
            pred, subj, val = f[0], f[1], f[2]
            key = (pred, subj)
            fld = getattr(cls, pred)
            if key in multi_guard:
                fg.fields.add(fld, refs[subj], val)
            else:
                fg.fields.set(fld, refs[subj], val)
                multi_guard.add(key)
    else:
        cls = classes["__world__"]
        w = fg.entities.create(cls, key="w0")
        refs["__world__"] = w
        for f in facts:
            fg.fields.set(getattr(cls, f[0]), w, f[1])
    return fg, {"classes": classes, "refs": refs}


class _EngineFault(RuntimeError):
    pass


def run_cell(fixture: dict, resolution: dict, compile_result: dict) -> dict:
    """Native evaluation + normalization to ProbeExecutionResultV0 (dict form)."""
    prof = fixture["profile"]
    task_kind = prof["task_kind"]
    cutoff = fixture.get("fixture_cutoff")
    fault = bool(fixture.get("engine_fault_injection"))

    fg, world_ctx = build_world(fixture["world"])
    try:
        # translate bind values: entity ids -> e_refs where the engine anchor needs identity value.
        # (binds were compiled as identity-anchor atoms on the identity FIELD VALUE, so no
        #  e_ref substitution is needed: the Const carries the identity value itself.)
        expr, head = compile_result["expr"], compile_result["head"]
        engine_attempted = False
        try:
            if fault:
                engine_attempted = True
                with patch("factgraph.sdk.store.evaluate_derivation_plans",
                           side_effect=_EngineFault("injected native engine fault")):
                    fg.eval.evaluate(expr, head=head, engine="native")
                raise AssertionError("fault injection did not raise")  # pragma: no cover
            engine_attempted = True
            shipped = fg.eval.evaluate(expr, head=head, engine="native")
        except _EngineFault:
            return {
                "task_kind": task_kind,
                "engine_invocations": 1,
                "result": typed_failure_result({"code": EXECUTION_ENGINE_FAULT,
                                                "stage": "native_evaluation"}),
                "expectation": None,
                "explain": {"anchor": "none", "content_class": "none"},
                "shipped_fingerprint": None,
            }

        # ---- normalize rows via select_map (aliases <- qualified head ports) ----
        select_map = compile_result["select_map"]
        rows: list[dict] = []
        row_anchors: list[str] = []
        raw_rows = list(shipped)
        for row in raw_rows:
            out = {}
            for alias, port in select_map.items():
                b = row.bindings.get(port)
                if b is None:
                    raise ProbeError("SELECTION_PORT_MISSING", stage="normalization",
                                     diagnostics=[alias, port])
                out[alias] = b.get("value") if b.get("kind") == "literal" else _entity_display(b, world_ctx)
            rows.append(out)
            row_anchors.append(row.row_id)
        rows_sorted = sorted(rows, key=lambda r: __import__("json").dumps(r, sort_keys=True))

        completeness, truncated = "complete", False
        if cutoff:
            if cutoff.get("kind") == "post_engine_truncate_all":
                rows_sorted, row_anchors = [], []
                completeness, truncated = cutoff.get("mark", "incomplete"), True
            else:
                raise ProbeError("CUTOFF_KIND_UNSUPPORTED", stage="normalization",
                                 diagnostics=[str(cutoff)])

        mode = compile_result["query_mode"]
        observed = len(raw_rows) if not cutoff else len(raw_rows)
        if mode == "exists":
            status: Any
            if raw_rows and not cutoff:
                status = True
            elif completeness == "complete":
                status = False
            else:
                status = "underdetermined"
            result = exists_summary_result(status, observed, completeness)
        else:
            summary = None
            if not rows_sorted:
                if completeness == "complete":
                    summary = {"status": False}
                else:
                    summary = {"status": "underdetermined"}
            result = rows_result(rows_sorted, completeness, truncated, summary)

        # ---- server-owned expectation over the normalized QueryResult ----------
        expectation = None
        if task_kind == "validation":
            tpl = prof["expectation_template"]
            expectation = _evaluate_expectation(tpl, resolution, rows_sorted, completeness)

        # ---- explain targeting --------------------------------------------------
        explain = _explain_target(task_kind, result, expectation, raw_rows, row_anchors, cutoff)

        return {
            "task_kind": task_kind,
            "engine_invocations": 1 if engine_attempted else 0,
            "result": result,
            "expectation": expectation,
            "explain": explain,
            "row_anchors": row_anchors,
            "shipped_fingerprint": {
                "run_id": shipped.fingerprint.run_id,
                "result_digest": shipped.fingerprint.result_digest,
                "view_snapshot_digest": shipped.fingerprint.view_snapshot_digest,
            },
            "raw_row_count": len(raw_rows),
        }
    finally:
        fg.close()


def _entity_display(binding: dict, world_ctx: dict) -> str:
    """Map an entity_ref binding back to its identity value for row display."""
    val = binding.get("value")
    for ident, ref in world_ctx["refs"].items():
        if ref == val:
            return ident
    return str(val)


def _evaluate_expectation(tpl: dict, resolution: dict, rows: list[dict], completeness: str) -> dict:
    kind = tpl["kind"]
    if tpl.get("set_mode"):
        return {"kind": kind, "status": "unsupported", "matched_row_count": 0,
                "completeness_relied_upon": completeness,
                "diagnostics": [EXPECTATION_SET_MODE_UNSUPPORTED]}
    if kind == "exists":
        if rows:
            return _exp(kind, "satisfied", len(rows), completeness)
        if completeness == "complete":
            return _exp(kind, "not_satisfied", 0, completeness)
        return _exp(kind, "underdetermined", 0, completeness)
    if kind == "contains_row":
        expected = {}
        for alias, slot in (tpl.get("row_template") or {}).items():
            slot_val = resolution["normalized_slot_values"][slot]
            expected[alias] = slot_val.get("id", slot_val.get("value"))
        matches = [r for r in rows if all(r.get(a) == v for a, v in expected.items())]
        if matches:
            return _exp(kind, "satisfied", len(matches), completeness)
        if completeness == "complete":
            return _exp(kind, "not_satisfied", 0, completeness)
        return _exp(kind, "underdetermined", 0, completeness)
    return {"kind": kind, "status": "unsupported", "matched_row_count": 0,
            "completeness_relied_upon": completeness,
            "diagnostics": ["EXPECTATION_KIND_UNSUPPORTED"]}


def _exp(kind: str, status: str, matched: int, completeness: str) -> dict:
    return {"kind": kind, "status": status, "matched_row_count": matched,
            "completeness_relied_upon": completeness, "diagnostics": []}


def _explain_target(task_kind: str, result: dict, expectation: dict | None,
                    raw_rows: list, row_anchors: list[str], cutoff: dict | None) -> dict:
    """Choose the anchor per §5.4.4; run live row.explain() only for a row anchor."""
    if task_kind == "validation" and expectation is not None:
        return {"anchor": "expectation", "content_class": "structured_diagnostic",
                "diagnostic": {"expectation_status": expectation["status"],
                               "matched_row_count": expectation["matched_row_count"]}}
    if result["kind"] == "exists_summary" or (result["kind"] == "rows" and not result["rows"]):
        return {"anchor": "query_summary", "content_class": "structured_diagnostic",
                "diagnostic": {"summary": result.get("query_summary"),
                               "completeness": result.get("completeness")}}
    if result["kind"] == "rows" and raw_rows and not cutoff:
        row = raw_rows[0]  # explicit selected row for probe evidence (recorded, not implicit-first for zero-row)
        ex = row.explain()
        return {"anchor": "row", "content_class": "native_evidence_graph",
                "selected_row_anchor": row.row_id,
                "explanation_status": ex.status,
                "has_evidence_graph": ex.evidence is not None}
    return {"anchor": "none", "content_class": "none"}
