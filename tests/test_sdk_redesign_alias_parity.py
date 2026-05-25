"""Alias-parity tests for the post-T5 SDK taxonomy.

Per blueprint `2026-05-09_post-l-sdk-ergonomics-redesign.md` §5.9 lock:
each `FactGraph.<namespace>.<method>(...)` call must delegate to the
flat `SDKStore.<method>(...)` and produce identical results — alias
parity is the primary correctness invariant of the additive redesign.

Per §5.4 Option 2 lock: managers delegate to flat methods (no behavior
duplication). Per §5.7 non-commitment #1: ``FactGraph`` is a literal
alias of ``SDKStore`` (same class object); these tests assert the
delegation contract end-to-end.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from factgraph.sdk import Entity, Field, FactGraph, Identity, SDKStore


class Person(Entity):
    pid: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    age: int = Field(cardinality="single")


def _new_fg() -> FactGraph:
    return FactGraph.from_schema_classes([Person])


class FactGraphIsSDKStoreAliasTests(unittest.TestCase):
    """`FactGraph` and `SDKStore` are the same class object."""

    def test_factgraph_is_sdkstore(self) -> None:
        self.assertIs(FactGraph, SDKStore)

    def test_factgraph_constructs_sdkstore_instance(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg, SDKStore)
        self.assertIsInstance(fg, FactGraph)


class _AliasParityBase(unittest.TestCase):
    """Base helper: each manager method delegates to the flat method."""

    namespace_attr: str = ""
    flat_to_nested: tuple[tuple[str, str], ...] = ()

    def _assert_delegates(self, flat_name: str, nested_name: str) -> None:
        fg = _new_fg()
        manager = getattr(fg, self.namespace_attr)
        with patch.object(fg, flat_name) as mock:
            mock.return_value = "sentinel-result"
            result = getattr(manager, nested_name)("arg1", kw="kw1")
        mock.assert_called_once_with("arg1", kw="kw1")
        self.assertEqual(result, "sentinel-result")

    def _run_all(self) -> None:
        if not self.flat_to_nested:
            self.skipTest("base class")
        for flat_name, nested_name in self.flat_to_nested:
            with self.subTest(flat=flat_name, nested=nested_name):
                self._assert_delegates(flat_name, nested_name)


class SchemaNamespaceParityTests(_AliasParityBase):
    namespace_attr = "schema"
    flat_to_nested = (
        ("ingest", "ingest"),
        ("validate_provenance", "validate_provenance"),
    )

    def test_schema_methods_delegate(self) -> None:
        self._run_all()


class ReadNamespaceParityTests(_AliasParityBase):
    namespace_attr = "read"
    flat_to_nested = (
        ("get", "get"),
        ("find", "find"),
        ("ref", "ref"),
    )

    def test_read_methods_delegate(self) -> None:
        self._run_all()


class WriteNamespaceParityTests(_AliasParityBase):
    namespace_attr = "write"
    flat_to_nested = (
        ("set", "set"),
        ("add", "add"),
        ("retract", "retract"),
        ("edit", "edit"),
    )

    def test_write_methods_delegate(self) -> None:
        self._run_all()


class EvalNamespaceParityTests(_AliasParityBase):
    namespace_attr = "eval"
    flat_to_nested = (
        ("evaluate", "evaluate"),
        ("explain", "explain"),
        ("inspect_semantics", "inspect_semantics"),
    )

    def test_eval_methods_delegate(self) -> None:
        self._run_all()


class AuditNamespaceParityTests(_AliasParityBase):
    """Per §5.2 §5.2.1 placement #2, ``diff_proof_frames`` lives here."""

    namespace_attr = "audit"
    flat_to_nested = (
        ("explain_fact", "explain_fact"),
        ("conflicts", "conflicts"),
        ("diff_proof_frames", "diff_proof_frames"),
    )

    def test_audit_methods_delegate(self) -> None:
        self._run_all()


class PackageNamespaceParityTests(_AliasParityBase):
    namespace_attr = "package"
    flat_to_nested = (
        ("export_package", "export_package"),
        ("run_package", "run_package"),
    )

    def test_package_methods_delegate(self) -> None:
        self._run_all()


class RealResultParityTests(unittest.TestCase):
    """End-to-end real-result parity for representative read methods.

    Verifies that the alias delegation produces identical results, not
    just that the call is forwarded. Limited to read-side methods to
    avoid double-mutation cost; write paths are covered by delegation
    tests above.
    """

    def test_read_ref_real_parity(self) -> None:
        fg = _new_fg()
        flat = fg.ref(Person, pid="p-1")
        nested = fg.read.ref(Person, pid="p-1")
        self.assertEqual(flat, nested)

    def test_read_get_real_parity_after_set(self) -> None:
        fg = _new_fg()
        ref = fg.ref(Person, pid="p-1")
        fg.set(Person.name, ref, "Alice")

        flat = fg.get(Person, pid="p-1")
        nested = fg.read.get(Person, pid="p-1")
        self.assertEqual(flat.name, nested.name)
        self.assertEqual(flat.ref, nested.ref)

    def test_read_find_real_parity(self) -> None:
        fg = _new_fg()
        ref = fg.ref(Person, pid="p-1")
        fg.set(Person.name, ref, "Alice")

        flat = fg.find(Person)
        nested = fg.read.find(Person)
        self.assertEqual(len(flat), len(nested))


if __name__ == "__main__":
    unittest.main()
