from __future__ import annotations

import os
import subprocess
from pathlib import Path


class ProbLogEngineError(Exception):
    pass


def run_problog(pl_path: Path, timeout: int = 30) -> str:
    path = Path(pl_path)
    if not path.exists():
        raise ProbLogEngineError(f"ProbLog program not found: {path}")

    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
        raise ProbLogEngineError("timeout must be positive int seconds")

    problog_bin = os.getenv("PROBLOG_BIN", "problog")
    try:
        proc = subprocess.run(
            [problog_bin, str(path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ProbLogEngineError(
            f"ProbLog CLI is not available: {problog_bin}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbLogEngineError(
            f"ProbLog CLI timed out after {timeout}s"
        ) from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        if stderr:
            raise ProbLogEngineError(f"ProbLog CLI failed with exit code {proc.returncode}: {stderr}")
        raise ProbLogEngineError(f"ProbLog CLI failed with exit code {proc.returncode}")
    return proc.stdout or ""
