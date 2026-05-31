from __future__ import annotations

import dataclasses
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Callable, Protocol

from factgraph.core.rules._trace import (
    RuleTraceArtifact,
    rule_trace_artifact_bytes,
    rule_trace_artifact_from_dict,
)
from factgraph.core.store._support import (
    ProofReceipt,
    support_artifact_bytes,
    support_artifact_from_dict,
)

_LOG = logging.getLogger(__name__)


class ArtifactSidecar(Protocol):
    def write_support(self, support_digest: str, artifact: ProofReceipt) -> None: ...

    def write_rule_trace(self, rule_run_id: str, artifact: RuleTraceArtifact) -> None: ...

    def read_support(self, support_digest: str) -> ProofReceipt | None: ...

    def read_rule_trace(self, rule_run_id: str) -> RuleTraceArtifact | None: ...


@dataclasses.dataclass(frozen=True)
class GCResult:
    total_scanned: int
    deleted_keys: tuple[str, ...]
    deleted_orphan_meta_paths: tuple[str, ...]
    skipped_orphan_payload_paths: tuple[str, ...]
    failed_keys: tuple[tuple[str, str, str], ...]


class FileArtifactSidecar:
    def __init__(self, sidecar_root: Path | str, *, clock: Callable[[], int] = time.time_ns) -> None:
        self._sidecar_root = Path(sidecar_root)
        self._clock = clock

    def write_support(self, support_digest: str, artifact: ProofReceipt) -> None:
        if not isinstance(artifact, ProofReceipt):
            raise ValueError("artifact must be ProofReceipt")
        payload_path = self._support_path(support_digest)
        first_write = self._write_bytes(
            payload_path,
            support_artifact_bytes(artifact),
            f"support_digest collision for different ProofReceipt on disk: {support_digest}",
        )
        if first_write:
            self._write_meta(payload_path)

    def write_rule_trace(self, rule_run_id: str, artifact: RuleTraceArtifact) -> None:
        if not isinstance(artifact, RuleTraceArtifact):
            raise ValueError("artifact must be RuleTraceArtifact")
        payload_path = self._rule_trace_path(rule_run_id)
        first_write = self._write_bytes(
            payload_path,
            rule_trace_artifact_bytes(artifact),
            f"rule_run_id collision for different RuleTraceArtifact on disk: {rule_run_id}",
        )
        if first_write:
            self._write_meta(payload_path)

    def read_support(self, support_digest: str) -> ProofReceipt | None:
        path = self._support_path(support_digest)
        row = self._read_json_row(path)
        if row is None:
            return None
        return support_artifact_from_dict(row)

    def read_rule_trace(self, rule_run_id: str) -> RuleTraceArtifact | None:
        path = self._rule_trace_path(rule_run_id)
        row = self._read_json_row(path)
        if row is None:
            return None
        return rule_trace_artifact_from_dict(row)

    def gc_rule_trace(self, ttl_ns: int, *, dry_run: bool = False) -> GCResult:
        if not isinstance(ttl_ns, int) or isinstance(ttl_ns, bool) or ttl_ns <= 0:
            raise ValueError("ttl_ns must be positive int")

        now_ns = self._clock()
        rule_trace_dir = self._sidecar_root / "rule_trace"
        if not rule_trace_dir.exists():
            return GCResult(
                total_scanned=0,
                deleted_keys=(),
                deleted_orphan_meta_paths=(),
                skipped_orphan_payload_paths=(),
                failed_keys=(),
            )

        payload_paths_by_stem: dict[str, Path] = {}
        meta_paths_by_stem: dict[str, Path] = {}
        for path in sorted(rule_trace_dir.iterdir(), key=lambda item: item.name):
            if path.name.endswith(".meta.json"):
                meta_paths_by_stem[path.name[: -len(".meta.json")]] = path
            elif path.suffix == ".json":
                payload_paths_by_stem[path.stem] = path

        deleted_keys: list[str] = []
        deleted_orphan_meta_paths: list[str] = []
        skipped_orphan_payload_paths: list[str] = []
        failed_keys: list[tuple[str, str, str]] = []

        for rule_run_id in sorted(meta_paths_by_stem.keys() - payload_paths_by_stem.keys()):
            meta_path = meta_paths_by_stem[rule_run_id]
            _LOG.warning("orphan rule trace metadata without payload: %s", meta_path)
            if not dry_run:
                try:
                    self._unlink_if_exists(meta_path)
                except OSError as exc:
                    failed_keys.append((rule_run_id, str(meta_path), str(exc)))
                    continue
            deleted_orphan_meta_paths.append(str(meta_path))

        for rule_run_id in sorted(payload_paths_by_stem.keys() - meta_paths_by_stem.keys()):
            payload_path = payload_paths_by_stem[rule_run_id]
            _LOG.warning("rule trace payload missing retention metadata, skipping GC: %s", payload_path)
            skipped_orphan_payload_paths.append(str(payload_path))

        for rule_run_id in sorted(payload_paths_by_stem.keys() & meta_paths_by_stem.keys()):
            payload_path = payload_paths_by_stem[rule_run_id]
            meta_path = meta_paths_by_stem[rule_run_id]
            active_path = str(meta_path)
            try:
                meta_row = self._read_json_row(meta_path)
                if meta_row is None:
                    raise ValueError(f"artifact row missing: {meta_path}")
                captured_at_ns = meta_row.get("captured_at_ns")
                if not isinstance(captured_at_ns, int) or isinstance(captured_at_ns, bool):
                    raise ValueError(f"captured_at_ns must be int: {meta_path}")
                if captured_at_ns >= now_ns - ttl_ns:
                    continue
                if not dry_run:
                    active_path = str(payload_path)
                    self._unlink_if_exists(payload_path)
                    active_path = str(meta_path)
                    self._unlink_if_exists(meta_path)
                deleted_keys.append(rule_run_id)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                failed_keys.append((rule_run_id, active_path, str(exc)))

        return GCResult(
            total_scanned=len(set(payload_paths_by_stem) | set(meta_paths_by_stem)),
            deleted_keys=tuple(deleted_keys),
            deleted_orphan_meta_paths=tuple(deleted_orphan_meta_paths),
            skipped_orphan_payload_paths=tuple(skipped_orphan_payload_paths),
            failed_keys=tuple(failed_keys),
        )

    def _support_path(self, support_digest: str) -> Path:
        if not isinstance(support_digest, str) or not support_digest.startswith("sha256:"):
            raise ValueError("support_digest must use sha256: prefix")
        digest_hex = support_digest[len("sha256:") :]
        if not digest_hex:
            raise ValueError("support_digest hex must be non-empty")
        return self._sidecar_root / "support" / "sha256" / f"{digest_hex}.json"

    def _rule_trace_path(self, rule_run_id: str) -> Path:
        if not isinstance(rule_run_id, str) or not rule_run_id:
            raise ValueError("rule_run_id must be non-empty string")
        if "/" in rule_run_id or "\\" in rule_run_id or "\x00" in rule_run_id:
            raise ValueError("rule_run_id must be filesystem-safe")
        return self._sidecar_root / "rule_trace" / f"{rule_run_id}.json"

    def _read_json_row(self, path: Path) -> dict[str, object] | None:
        try:
            payload = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        row = json.loads(payload)
        if not isinstance(row, dict):
            raise ValueError(f"artifact row must decode to object: {path}")
        return row

    @staticmethod
    def _meta_path(artifact_path: Path) -> Path:
        return artifact_path.with_suffix(".meta.json")

    def _write_meta(self, artifact_path: Path) -> None:
        payload = json.dumps(
            {"captured_at_ns": self._clock()},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self._replace_bytes(self._meta_path(artifact_path), payload)

    def _write_bytes(self, path: Path, payload: bytes, collision_message: str) -> bool:
        try:
            existing = path.read_bytes()
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing == payload:
                return False
            raise ValueError(collision_message)

        self._replace_bytes(path, payload)
        return True

    def _replace_bytes(self, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
            os.replace(tmp_path, path)
        finally:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

    @staticmethod
    def _unlink_if_exists(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


__all__ = ["ArtifactSidecar", "FileArtifactSidecar", "GCResult"]
