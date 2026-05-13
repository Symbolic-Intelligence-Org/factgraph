from __future__ import annotations

import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
PRODUCTION_ROOTS = ("src/service", "src/agent")

PRODUCTION_SDK_IMPORT_ALLOWLIST: dict[tuple[str, str], str] = {
    (
        "src/agent/extraction/api.py",
        "from factpy.sdk.compile import compile_schema_from_classes",
    ): "authoring helper used to compile Entity classes into schema_ir",
}


class SDKConsumerBoundaryTests(unittest.TestCase):
    def test_no_new_service_agent_production_sdk_runtime_imports(self) -> None:
        actual = _scan_production_sdk_imports()

        self.assertEqual(
            actual,
            set(PRODUCTION_SDK_IMPORT_ALLOWLIST),
            "Production service/agent SDK imports must be explicitly allowlisted. "
            "Runtime operations should go through factpy.application; add only "
            "authoring or ergonomic exceptions with rationale.",
        )


def _scan_production_sdk_imports() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for root in PRODUCTION_ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*.py")):
            rel_path = path.relative_to(REPO_ROOT)
            if "tests" in rel_path.parts:
                continue
            rel_text = rel_path.as_posix()
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=rel_text)
            lines = source.splitlines()
            for node in ast.walk(tree):
                if _is_factpy_sdk_import(node):
                    out.add((rel_text, lines[node.lineno - 1].strip()))
    return out


def _is_factpy_sdk_import(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(alias.name == "factpy.sdk" or alias.name.startswith("factpy.sdk.") for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        if module == "factpy.sdk" or module.startswith("factpy.sdk."):
            return True
        return module == "factpy" and any(alias.name == "sdk" for alias in node.names)
    return False


if __name__ == "__main__":
    unittest.main()
