"""Phase 1 alias-parity tests for the post-L SDK ergonomics redesign.

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
        ("run", "run"),
        ("evaluate", "evaluate"),
        ("accept", "accept"),
        ("accept_many", "accept_many"),
    )

    def test_eval_methods_delegate(self) -> None:
        self._run_all()


class WhatIfDirectMethodParityTests(_AliasParityBase):
    """G1 + G4 direct methods on `what_if` (not in sub-namespaces)."""

    namespace_attr = "what_if"
    flat_to_nested = (
        ("check", "check"),
        ("diagnose", "diagnose"),
        ("why_not", "why_not"),
    )

    def test_what_if_direct_methods_delegate(self) -> None:
        self._run_all()


class WhatIfFactOverlayParityTests(unittest.TestCase):
    """G2 sub-namespace `what_if.fact_overlay`.

    Note: `check_fact_overlay` flat method maps to `fact_overlay.check`
    nested name (prefix dropped at sub-namespace level per §5.2 split).
    """

    def test_check_delegates_to_check_fact_overlay(self) -> None:
        fg = _new_fg()
        with patch.object(fg, "check_fact_overlay") as mock:
            mock.return_value = "fo-result"
            result = fg.what_if.fact_overlay.check("arg1", kw="kw1")
        mock.assert_called_once_with("arg1", kw="kw1")
        self.assertEqual(result, "fo-result")

    def test_recheck_proof_frame_delegates(self) -> None:
        fg = _new_fg()
        with patch.object(fg, "recheck_proof_frame") as mock:
            mock.return_value = "rpf-result"
            result = fg.what_if.fact_overlay.recheck_proof_frame("arg1", kw="kw1")
        mock.assert_called_once_with("arg1", kw="kw1")
        self.assertEqual(result, "rpf-result")


class WhatIfRuleParityTests(unittest.TestCase):
    """G3 sub-namespace `what_if.rule`.

    Note: `check_rule_*` flat methods map to `rule.<verb>` nested names
    (prefix dropped at sub-namespace level per §5.2 split).
    """

    def test_disable_delegates_to_check_rule_disable(self) -> None:
        fg = _new_fg()
        with patch.object(fg, "check_rule_disable") as mock:
            mock.return_value = "rd-result"
            result = fg.what_if.rule.disable("arg1", kw="kw1")
        mock.assert_called_once_with("arg1", kw="kw1")
        self.assertEqual(result, "rd-result")

    def test_literal_replace_delegates(self) -> None:
        fg = _new_fg()
        with patch.object(fg, "check_rule_literal_replace") as mock:
            mock.return_value = "rlr-result"
            result = fg.what_if.rule.literal_replace("arg1", kw="kw1")
        mock.assert_called_once_with("arg1", kw="kw1")
        self.assertEqual(result, "rlr-result")

    def test_add_condition_delegates(self) -> None:
        fg = _new_fg()
        with patch.object(fg, "check_rule_add_condition") as mock:
            mock.return_value = "rac-result"
            result = fg.what_if.rule.add_condition("arg1", kw="kw1")
        mock.assert_called_once_with("arg1", kw="kw1")
        self.assertEqual(result, "rac-result")


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
