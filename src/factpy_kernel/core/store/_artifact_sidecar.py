from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

from factpy_kernel.core.rules._trace import (
    RuleTraceArtifact,
    rule_trace_artifact_bytes,
    rule_trace_artifact_from_dict,
)
from factpy_kernel.core.store._support import (
    SupportArtifact,
    support_artifact_bytes,
    support_artifact_from_dict,
)


class ArtifactSidecar(Protocol):
    def write_support(self, support_digest: str, artifact: SupportArtifact) -> None: ...

    def write_rule_trace(self, rule_run_id: str, artifact: RuleTraceArtifact) -> None: ...

    def read_support(self, support_digest: str) -> SupportArtifact | None: ...

    def read_rule_trace(self, rule_run_id: str) -> RuleTraceArtifact | None: ...


class FileArtifactSidecar:
    def __init__(self, sidecar_root: Path | str) -> None:
        self._sidecar_root = Path(sidecar_root)

    def write_support(self, support_digest: str, artifact: SupportArtifact) -> None:
        if not isinstance(artifact, SupportArtifact):
            raise ValueError("artifact must be SupportArtifact")
        self._write_bytes(
            self._support_path(support_digest),
            support_artifact_bytes(artifact),
            f"support_digest collision for different SupportArtifact on disk: {support_digest}",
        )

    def write_rule_trace(self, rule_run_id: str, artifact: RuleTraceArtifact) -> None:
        if not isinstance(artifact, RuleTraceArtifact):
            raise ValueError("artifact must be RuleTraceArtifact")
        self._write_bytes(
            self._rule_trace_path(rule_run_id),
            rule_trace_artifact_bytes(artifact),
            f"rule_run_id collision for different RuleTraceArtifact on disk: {rule_run_id}",
        )

    def read_support(self, support_digest: str) -> SupportArtifact | None:
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

    def _write_bytes(self, path: Path, payload: bytes, collision_message: str) -> None:
        try:
            existing = path.read_bytes()
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing == payload:
                return
            raise ValueError(collision_message)

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


__all__ = ["ArtifactSidecar", "FileArtifactSidecar"]
