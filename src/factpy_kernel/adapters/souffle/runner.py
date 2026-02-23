from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from factpy_kernel.adapters.souffle.pred_norm import normalize_pred_id
from factpy_kernel.adapters.souffle.tsv_v1 import tsv_cell_v1_decode, write_tsv


class RunnerCapabilityError(Exception):
    pass


def find_souffle_binary() -> Path | None:
    env_value = os.getenv("SOUFFLE_BIN")
    if env_value is not None:
        candidate = Path(env_value).expanduser()
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
        return None

    resolved = shutil.which("souffle")
    if resolved is None:
        return None
    return Path(resolved)


def run_package(
    package_dir: Path,
    entrypoints: list[str],
    engine: str = "souffle",
) -> Path:
    if engine not in {"souffle", "noop"}:
        raise ValueError("engine must be 'souffle' or 'noop'")

    pkg_dir = Path(package_dir)
    started_at = time.time_ns()

    manifest_path = pkg_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_package_layout(pkg_dir, manifest)
    _validate_facts_tsv(pkg_dir / "facts")

    resolved_entrypoints = _resolve_entrypoints(entrypoints, manifest)
    resolved_engine_preds = _resolve_output_engine_preds(resolved_entrypoints, manifest)
    resolved_outputs = [
        f"outputs/{engine_pred}.out.facts" for engine_pred in resolved_engine_preds
    ]

    outputs_dir = pkg_dir / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    raw_dir, work_dir = _prepare_output_workspace(outputs_dir)

    engine_mode = engine
    fallback_reason: str | None = None
    souffle_bin_path: Path | None = None
    engine_stdout = ""
    engine_stderr = ""
    exit_code = 0

    if engine == "souffle":
        souffle_bin_path = find_souffle_binary()
        if souffle_bin_path is None:
            engine_mode = "noop"
            fallback_reason = "souffle_not_found"
        else:
            try:
                program_path = _build_program_file(pkg_dir, manifest, work_dir)
                if program_path.read_text(encoding="utf-8").strip():
                    proc = subprocess.run(
                        [
                            str(souffle_bin_path),
                            "-F",
                            str(pkg_dir / "facts"),
                            "-D",
                            str(raw_dir),
                            str(program_path),
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    engine_stdout = proc.stdout
                    engine_stderr = proc.stderr
                    exit_code = proc.returncode
                if exit_code == 0:
                    _convert_raw_outputs(raw_dir, outputs_dir)
            except RunnerCapabilityError as exc:
                exit_code = 70
                engine_stderr = _append_error(engine_stderr, str(exc))

    if engine_mode == "noop":
        _write_noop_outputs(outputs_dir, resolved_engine_preds)
    else:
        _ensure_entrypoint_outputs(outputs_dir, resolved_engine_preds)

    outputs_digest = _compute_outputs_digest(pkg_dir)
    finished_at = time.time_ns()

    generated_outputs = sorted(
        f"outputs/{path.name}" for path in outputs_dir.glob("*.out.facts")
    )

    run_manifest = {
        "started_at": started_at,
        "finished_at": finished_at,
        "entrypoints": sorted(set(resolved_entrypoints)),
        "resolved_outputs": resolved_outputs,
        "generated_outputs": generated_outputs,
        "requested_engine": engine,
        "engine_mode": engine_mode,
        "fallback_reason": fallback_reason,
        "souffle_bin": str(souffle_bin_path) if souffle_bin_path is not None else None,
        "engine_stdout": engine_stdout,
        "engine_stderr": engine_stderr,
        "exit_code": exit_code,
        "digests": {
            "outputs_digest": outputs_digest,
        },
    }

    run_manifest_path = outputs_dir / "run_manifest.json"
    run_manifest_path.write_text(
        json.dumps(run_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
        newline="\n",
    )
    return run_manifest_path


def _prepare_output_workspace(outputs_dir: Path) -> tuple[Path, Path]:
    for out_file in outputs_dir.glob("*.out.facts"):
        out_file.unlink()

    raw_dir = outputs_dir / ".raw"
    work_dir = outputs_dir / ".work"

    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)

    raw_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir, work_dir


def _resolve_entrypoints(entrypoints: list[str], manifest: dict[str, Any]) -> list[str]:
    resolved = list(entrypoints)
    if not resolved:
        raw_entrypoints = manifest.get("entrypoints", [])
        if isinstance(raw_entrypoints, list):
            resolved = [item for item in raw_entrypoints if isinstance(item, str) and item]
    return sorted(set(resolved))


def _resolve_output_engine_preds(
    entrypoints: list[str],
    manifest: dict[str, Any],
) -> list[str]:
    outputs_map = _parse_outputs_map(manifest.get("outputs_map"))
    if outputs_map is not None:
        out: list[str] = []
        for entrypoint in entrypoints:
            if entrypoint not in outputs_map:
                available = ",".join(sorted(outputs_map.keys()))
                raise RunnerCapabilityError(
                    f"entrypoint missing in outputs_map: {entrypoint} (available: {available})"
                )
            out.extend(outputs_map[entrypoint])
        return sorted(set(out))

    return sorted({normalize_pred_id(entrypoint) for entrypoint in entrypoints})


def _parse_outputs_map(raw_outputs_map: Any) -> dict[str, list[str]] | None:
    if not isinstance(raw_outputs_map, dict):
        return None

    parsed: dict[str, list[str]] = {}
    for pred_id, engine_preds in raw_outputs_map.items():
        if not isinstance(pred_id, str) or not pred_id:
            return None
        if not isinstance(engine_preds, list) or not engine_preds:
            return None
        out_preds: list[str] = []
        for engine_pred in engine_preds:
            if not isinstance(engine_pred, str) or not engine_pred:
                return None
            out_preds.append(engine_pred)
        parsed[pred_id] = sorted(set(out_preds))
    return parsed


def _build_program_file(pkg_dir: Path, manifest: dict[str, Any], work_dir: Path) -> Path:
    view_rel = _manifest_path(manifest, "paths", "rules", "view")
    idb_rel = _manifest_path(manifest, "paths", "rules", "idb")

    view_path = pkg_dir / view_rel
    idb_path = pkg_dir / idb_rel

    view_text = view_path.read_text(encoding="utf-8")
    idb_text = idb_path.read_text(encoding="utf-8")
    policy_mode = manifest.get("policy_mode", "edb")
    if policy_mode not in {"edb", "idb"}:
        raise RunnerCapabilityError(f"unsupported policy_mode: {policy_mode}")
    policy_text = ""
    if policy_mode == "idb":
        policy_rules_path = pkg_dir / "policy" / "policy_rules.dl"
        if not policy_rules_path.exists():
            raise FileNotFoundError(f"missing policy rules: {policy_rules_path}")
        policy_text = policy_rules_path.read_text(encoding="utf-8")

    program_path = work_dir / "program.dl"
    program_path.write_text(
        "\n".join([view_text, policy_text, idb_text]) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return program_path


def _convert_raw_outputs(raw_dir: Path, outputs_dir: Path) -> None:
    for raw_path in sorted(raw_dir.iterdir()):
        if raw_path.suffix not in {".csv", ".facts"}:
            continue

        rows: list[list[str]] = []
        with raw_path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                if line == "":
                    continue
                rows.append(_parse_souffle_line(line, raw_path.name))

        rows.sort(key=lambda row: tuple(row))
        out_path = outputs_dir / f"{raw_path.stem}.out.facts"
        write_tsv(out_path, rows)


def _parse_souffle_line(line: str, file_name: str) -> list[str]:
    if "\t" in line and "," not in line:
        parts = line.split("\t")
    else:
        try:
            reader = csv.reader(
                [line],
                delimiter=",",
                quotechar='"',
                escapechar="\\",
                strict=True,
            )
            parts = next(reader)
        except csv.Error as exc:
            raise RunnerCapabilityError(
                f"invalid quoted CSV output in {file_name}: {exc}"
            ) from exc

    return [part for part in parts]


def _write_noop_outputs(outputs_dir: Path, engine_preds: list[str]) -> None:
    for engine_pred in engine_preds:
        file_name = f"{engine_pred}.out.facts"
        write_tsv(outputs_dir / file_name, [])


def _ensure_entrypoint_outputs(outputs_dir: Path, engine_preds: list[str]) -> None:
    for engine_pred in engine_preds:
        expected = outputs_dir / f"{engine_pred}.out.facts"
        if not expected.exists():
            write_tsv(expected, [])


def _validate_package_layout(pkg_dir: Path, manifest: dict[str, Any]) -> None:
    required_relpaths = [
        _manifest_path(manifest, "paths", "schema"),
        _manifest_path(manifest, "paths", "policy"),
        _manifest_path(manifest, "paths", "rules", "view"),
        _manifest_path(manifest, "paths", "rules", "idb"),
        _manifest_path(manifest, "paths", "facts", "claim"),
        _manifest_path(manifest, "paths", "facts", "claim_arg"),
        _manifest_path(manifest, "paths", "facts", "meta_str"),
        _manifest_path(manifest, "paths", "facts", "meta_time"),
        _manifest_path(manifest, "paths", "facts", "revokes"),
    ]

    optional_relpaths: list[str] = []
    for key in ("meta_num", "meta_bool"):
        try:
            optional_relpaths.append(_manifest_path(manifest, "paths", "facts", key))
        except FileNotFoundError:
            pass

    missing = [
        str(pkg_dir / rel)
        for rel in [*required_relpaths, *optional_relpaths]
        if not (pkg_dir / rel).exists()
    ]
    if missing:
        raise FileNotFoundError(f"package missing required files: {missing}")


def _manifest_path(manifest: dict[str, Any], *keys: str) -> str:
    cur: Any = manifest
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            raise FileNotFoundError(f"manifest missing path key: {'.'.join(keys)}")
        cur = cur[key]
    if not isinstance(cur, str) or not cur:
        raise FileNotFoundError(f"manifest path key is invalid: {'.'.join(keys)}")
    return cur


def _validate_facts_tsv(facts_dir: Path) -> None:
    for facts_path in sorted(facts_dir.glob("*.facts")):
        with facts_path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                if line == "":
                    continue
                for cell in line.split("\t"):
                    tsv_cell_v1_decode(cell)


def _compute_outputs_digest(package_dir: Path) -> str:
    outputs_dir = package_dir / "outputs"
    out_files = sorted(
        outputs_dir.glob("*.out.facts"),
        key=lambda p: p.relative_to(package_dir).as_posix(),
    )

    hasher = hashlib.sha256()
    for path in out_files:
        rel = path.relative_to(package_dir).as_posix().encode("utf-8")
        payload = path.read_bytes()
        hasher.update(rel)
        hasher.update(b"\x00")
        hasher.update(payload)
    return f"sha256:{hasher.hexdigest()}"


def _append_error(existing: str, extra: str) -> str:
    if not existing:
        return extra
    return f"{existing}\n{extra}"
