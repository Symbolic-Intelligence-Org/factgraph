from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factpy_kernel.adapters.souffle.tsv_v1 import tsv_cell_v1_decode

from .reader import AuditPackageData


class AuditAssertionReadError(Exception):
    pass


@dataclass(frozen=True)
class AuditAssertionIndex:
    package_dir: Path
    claims: dict[str, dict[str, Any]]
    claim_args: dict[str, list[dict[str, Any]]]
    meta: dict[str, dict[str, list[dict[str, Any]]]]
    revoked_by: dict[str, list[str]]
    revokes: dict[str, list[str]]

    def get_assertion_detail(self, asrt_id: str) -> dict[str, Any] | None:
        if not isinstance(asrt_id, str) or not asrt_id:
            raise AuditAssertionReadError("asrt_id must be non-empty string")
        claim = self.claims.get(asrt_id)
        if claim is None:
            return None
        claim_args = [dict(row) for row in self.claim_args.get(asrt_id, [])]
        meta = {
            kind: [dict(row) for row in rows]
            for kind, rows in sorted(self.meta.get(asrt_id, {}).items())
        }
        revoked_by = sorted(self.revoked_by.get(asrt_id, []))
        revokes = sorted(self.revokes.get(asrt_id, []))
        return {
            "asrt_id": asrt_id,
            "claim": dict(claim),
            "claim_args": claim_args,
            "meta": meta,
            "revoked_by": revoked_by,
            "revokes": revokes,
            "is_revoked": len(revoked_by) > 0,
        }


def load_assertion_index(package: AuditPackageData | str | Path) -> AuditAssertionIndex:
    if isinstance(package, AuditPackageData):
        package_dir = package.package_dir
        manifest = package.manifest
    else:
        package_dir = Path(package)
        manifest = _read_manifest(package_dir)

    facts = _manifest_facts(manifest)
    claim_rows = _read_tsv_rows(package_dir / facts["claim"], expected_cols=4)
    claim_arg_rows = _read_tsv_rows(package_dir / facts["claim_arg"], expected_cols=4)
    meta_str_rows = _read_tsv_rows(package_dir / facts["meta_str"], expected_cols=3)
    meta_time_rows = _read_tsv_rows(package_dir / facts["meta_time"], expected_cols=3)
    meta_num_rows = _read_tsv_rows(package_dir / facts["meta_num"], expected_cols=3)
    meta_bool_rows = _read_tsv_rows(package_dir / facts["meta_bool"], expected_cols=3)
    revokes_rows = _read_tsv_rows(package_dir / facts["revokes"], expected_cols=2)

    claims: dict[str, dict[str, Any]] = {}
    for row in claim_rows:
        asrt_id, pred_id, e_ref, tup_digest = row
        claims[asrt_id] = {
            "asrt_id": asrt_id,
            "pred_id": pred_id,
            "e_ref": e_ref,
            "tup_digest": tup_digest,
        }

    claim_args: dict[str, list[dict[str, Any]]] = {}
    for row in claim_arg_rows:
        asrt_id, idx_text, val, tag = row
        try:
            idx = int(idx_text)
        except ValueError as exc:
            raise AuditAssertionReadError(f"claim_arg idx must be int: {idx_text!r}") from exc
        claim_args.setdefault(asrt_id, []).append(
            {"asrt_id": asrt_id, "idx": idx, "val": val, "tag": tag}
        )
    for asrt_id, rows in claim_args.items():
        rows.sort(key=lambda r: (int(r["idx"]), str(r["tag"]), str(r["val"])))

    meta: dict[str, dict[str, list[dict[str, Any]]]] = {}
    _append_meta_rows(meta, meta_str_rows, kind="str", parser=_parse_meta_str)
    _append_meta_rows(meta, meta_time_rows, kind="time", parser=_parse_meta_time)
    _append_meta_rows(meta, meta_num_rows, kind="num", parser=_parse_meta_num)
    _append_meta_rows(meta, meta_bool_rows, kind="bool", parser=_parse_meta_bool)
    for asrt_id in list(meta.keys()):
        for kind in list(meta[asrt_id].keys()):
            meta[asrt_id][kind].sort(key=lambda r: (str(r["key"]), str(r["value"])))

    revoked_by: dict[str, list[str]] = {}
    revokes: dict[str, list[str]] = {}
    for revoker_asrt_id, revoked_asrt_id in revokes_rows:
        revokes.setdefault(revoker_asrt_id, []).append(revoked_asrt_id)
        revoked_by.setdefault(revoked_asrt_id, []).append(revoker_asrt_id)
    for mapping in (revokes, revoked_by):
        for asrt_id, values in mapping.items():
            values.sort()

    return AuditAssertionIndex(
        package_dir=package_dir,
        claims=claims,
        claim_args=claim_args,
        meta=meta,
        revoked_by=revoked_by,
        revokes=revokes,
    )


def _append_meta_rows(
    out: dict[str, dict[str, list[dict[str, Any]]]],
    rows: list[list[str]],
    *,
    kind: str,
    parser,
) -> None:
    for row in rows:
        asrt_id, key, raw_value = row
        value = parser(raw_value)
        out.setdefault(asrt_id, {}).setdefault(kind, []).append(
            {"asrt_id": asrt_id, "key": key, "kind": kind, "value": value}
        )


def _parse_meta_str(raw: str) -> str:
    return raw


def _parse_meta_time(raw: str) -> int:
    return _parse_int(raw, kind="time")


def _parse_meta_num(raw: str) -> int:
    return _parse_int(raw, kind="num")


def _parse_meta_bool(raw: str) -> bool:
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise AuditAssertionReadError(f"invalid meta_bool value: {raw!r}")


def _parse_int(raw: str, *, kind: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise AuditAssertionReadError(f"invalid {kind} integer value: {raw!r}") from exc
    return value


def _read_manifest(package_dir: Path) -> dict[str, Any]:
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        raise AuditAssertionReadError(f"missing manifest.json: {manifest_path}")
    import json

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuditAssertionReadError(f"invalid manifest JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuditAssertionReadError("manifest.json must be object")
    return payload


def _manifest_facts(manifest: dict[str, Any]) -> dict[str, str]:
    paths = manifest.get("paths")
    if not isinstance(paths, dict):
        raise AuditAssertionReadError("manifest.paths must be object")
    facts = paths.get("facts")
    if not isinstance(facts, dict):
        raise AuditAssertionReadError("manifest.paths.facts must be object")
    required = {"claim", "claim_arg", "meta_str", "meta_time", "meta_num", "meta_bool", "revokes"}
    out: dict[str, str] = {}
    for key in required:
        value = facts.get(key)
        if not isinstance(value, str) or not value:
            raise AuditAssertionReadError(f"manifest.paths.facts.{key} must be non-empty string")
        out[key] = value
    return out


def _read_tsv_rows(path: Path, *, expected_cols: int) -> list[list[str]]:
    if not path.exists():
        raise AuditAssertionReadError(f"missing facts file: {path}")
    rows: list[list[str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\n")
            if line == "":
                continue
            cells = [tsv_cell_v1_decode(part) for part in line.split("\t")]
            if len(cells) != expected_cols:
                raise AuditAssertionReadError(
                    f"invalid TSV arity at {path}:{lineno}; expected {expected_cols}, got {len(cells)}"
                )
            rows.append(cells)
    return rows
