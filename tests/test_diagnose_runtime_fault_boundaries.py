"""Characterization for the empty-case contract of ``_primary_env`` (FURB192).

``_primary_env`` deliberately keeps ``sorted(...)[0]`` instead of ``min(...)``:
the two differ exactly in the empty case, where ``sorted(...)[0]`` raises
``IndexError`` and ``min(...)`` would raise ``ValueError``.  Diagnose treats an
empty environment list as a programming error surfaced as ``IndexError``; this
test pins that so the noqa cannot be silently "fixed" into a different type.
"""

from __future__ import annotations

import unittest
from typing import Any

from factgraph.application.diagnose_runtime import _primary_env


class PrimaryEnvContractTests(unittest.TestCase):
    """src/factgraph/application/diagnose_runtime.py: ``_primary_env`` selection contract."""

    def test_empty_env_list_raises_index_error_not_value_error(self) -> None:
        with self.assertRaises(IndexError):
            _primary_env([])

    def test_primary_env_is_the_lowest_sorted_environment(self) -> None:
        envs: list[dict[str, Any]] = [
            {"$x": "b"},
            {"$x": "a"},
            {"$x": "c"},
        ]
        self.assertEqual(_primary_env(envs), {"$x": "a"})

    def test_primary_env_is_stable_for_multi_key_environments(self) -> None:
        envs: list[dict[str, Any]] = [
            {"$b": 1, "$a": 2},
            {"$a": 1, "$b": 2},
        ]
        self.assertEqual(_primary_env(envs), {"$a": 1, "$b": 2})


if __name__ == "__main__":
    unittest.main()
