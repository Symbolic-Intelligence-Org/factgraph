from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = ROOT / "src" / "factpy_kernel"

# Old compatibility import paths that should not appear in new code.
_OLD_PREFIXES = (
    "protocol",
    "schema",
    "store",
    "evidence",
    "policy",
    "view",
    "rules",
    "derivation",
    "mapping",
    "export",
    "runner",
)
_BANNED_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+factpy_kernel\.(%s)(?:\.|\b)" % "|".join(_OLD_PREFIXES)
)
_BANNED_INTERNAL_SHIM_RE = re.compile(
    r"^\s*(?:from|import)\s+factpy_kernel\.core\.(?:rules\.where_compile|view\.souffle_view_gen)(?:\.|\b)"
)

# If a future test intentionally exercises compatibility imports, add an explicit
# allowlist entry here instead of weakening the global rule.
_ALLOWLIST: set[Path] = set()


class NoNewCompatImportsV1Tests(unittest.TestCase):
    def test_no_new_compat_imports_in_source_modules(self) -> None:
        violations: list[str] = []
        for path in sorted(SRC_ROOT.rglob("*.py")):
            if "/tests/" in path.as_posix():
                continue
            if path in _ALLOWLIST:
                continue
            rel = path.relative_to(ROOT)
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if _BANNED_IMPORT_RE.search(line) or _BANNED_INTERNAL_SHIM_RE.search(line):
                    violations.append(f"{rel}:{lineno}: {line.strip()}")
        if violations:
            self.fail(
                "compat import paths are forbidden in new source code; use factpy_kernel.core.* "
                "or factpy_kernel.adapters.* instead:\n" + "\n".join(violations)
            )


if __name__ == "__main__":
    unittest.main()
