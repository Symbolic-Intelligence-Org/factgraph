from __future__ import annotations

import os
from importlib.util import find_spec
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile

from setuptools import find_packages


REPO_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = REPO_ROOT / "pyproject.toml"


class KernelOnlyPackagingTests(unittest.TestCase):
    def test_pyproject_discovers_only_kernel_packages(self) -> None:
        text = PYPROJECT.read_text(encoding="utf-8")
        package_section = _toml_section(text, "tool.setuptools.packages.find")

        self.assertIn('where = ["src"]', package_section)
        self.assertIn('include = ["kernel*"]', package_section)
        self.assertIn('exclude = ["kernel.tests*"]', package_section)

        packages = find_packages(
            where=str(REPO_ROOT / "src"),
            include=["kernel*"],
            exclude=["kernel.tests*"],
        )
        self.assertIn("kernel", packages)
        self.assertNotIn("kernel.tests", packages)
        self.assertTrue(
            all(package == "kernel" or package.startswith("kernel.") for package in packages),
            packages,
        )

    def test_publishable_extras_do_not_expose_private_surfaces(self) -> None:
        text = PYPROJECT.read_text(encoding="utf-8")
        extras_section = _toml_section(text, "project.optional-dependencies")

        self.assertIn("dev =", extras_section)
        for private_extra in ("service", "documents", "extraction", "observability"):
            self.assertNotIn(f"{private_extra} =", extras_section)
        for private_dependency in (
            "pymupdf",
            "pymupdf4llm",
            "python-docx",
            "fastapi",
            "mistralai",
            "langfuse",
        ):
            self.assertNotIn(private_dependency, extras_section.lower())

    @unittest.skipUnless(
        os.getenv("FACTPY_BUILD_CHECK") == "1",
        "set FACTPY_BUILD_CHECK=1 to build and inspect the wheel",
    )
    def test_built_wheel_contains_kernel_only(self) -> None:
        if find_spec("build") is None:
            self.skipTest("python build module is unavailable")

        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-m", "build", "--wheel", "--outdir", tmp],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)

            wheels = sorted(Path(tmp).glob("*.whl"))
            self.assertEqual(len(wheels), 1, wheels)

            with ZipFile(wheels[0]) as wheel:
                names = wheel.namelist()
                self.assertTrue(any(name.startswith("kernel/") for name in names), names[:20])
                for private_prefix in ("agent/", "service/", "domains/", "kernel/tests/"):
                    self.assertFalse(
                        any(name.startswith(private_prefix) for name in names),
                        private_prefix,
                    )
                metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
                metadata = wheel.read(metadata_name).decode("utf-8")
                self.assertIn("License: Apache-2.0", metadata)
                self.assertNotIn("Provides-Extra: documents", metadata)
                self.assertNotIn("Requires-Dist: pymupdf", metadata.lower())


def _toml_section(text: str, section_name: str) -> str:
    header = f"[{section_name}]"
    start = text.index(header)
    rest = text[start + len(header) :]
    end = rest.find("\n[")
    if end == -1:
        return rest
    return rest[:end]


if __name__ == "__main__":
    unittest.main()
