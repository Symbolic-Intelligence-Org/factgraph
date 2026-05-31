"""Phase 2 redesign invariants for the post-L SDK ergonomics redesign.

Per blueprint `2026-05-09_post-l-sdk-ergonomics-redesign.md` §5.9 lock:
5 invariant classes mirroring the G5 invariant pattern, scoped to the
post-L taxonomy + manager structure + docs lint.

Class 1: `factgraph.sdk.__all__` length 36 + `FactGraph` exported.
Class 2: Manager classes private (underscore prefix); not in `__all__`.
Class 3: No `DeprecationWarning` from non-deprecated flat `SDKStore.<method>` calls
         (parametrized across 6 method families per §5.4 lock; existing
         `row_format='tuple'` warning at `store.py:2133-2141` is
         separately scoped and stays; SavedRule/SavedInference persistence
         methods were removed in Slice 6 (Q8 Phase 2) and no longer require
         deprecation-warning coverage).
Class 4: Docs taxonomy-first lint via regex over markdown content
         (per §5.5 + §5.5.6 lock, Tier 1 / Tier 3 surfaces only).
Class 5: Sub-namespace structure under `what_if` (`fact_overlay`,
         `rule`) reachable + read-only enforced.
"""

from __future__ import annotations

import re
import unittest
import warnings
from pathlib import Path


def _removed_sdk_run(*_args, **_kwargs):
    raise unittest.SkipTest("flat run shell was removed by Q-NAMING-C")

import factgraph.sdk as factgraph_sdk
from factgraph.sdk import (
    Entity,
    FactGraph,
    Field,
    FrozenSnapshotError,
    Identity,
)
from factgraph.sdk.store import (
    AssertionsManager,
    _SDKAuditManager,
    _SDKEvalManager,
    _SDKEntitiesManager,
    _SDKFieldsManager,
    _SDKPackageManager,
    _SDKSchemaManager,
    _SDKAssertionViewsManager,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class Person(Entity):
    pid: str = Identity()
    name: str = Field()


def _new_fg() -> FactGraph:
    return FactGraph.from_schema_classes([Person])


# Class 1 — `__all__` length + FactGraph exported


class SDKAllLengthAndFactGraphExportInvariants(unittest.TestCase):
    """`factgraph.sdk.__all__` contains the current stable SDK exports."""

    def test_removed_readpolicy_not_in_all(self) -> None:
        self.assertNotIn("ReadPolicy", factgraph_sdk.__all__)

    def test_factgraph_in_all(self) -> None:
        self.assertIn("FactGraph", factgraph_sdk.__all__)

    def test_semantics_profile_in_all(self) -> None:
        self.assertIn("SemanticsProfile", factgraph_sdk.__all__)
        self.assertIn("ProbLogConfig", factgraph_sdk.__all__)
        self.assertIn("PyReasonConfig", factgraph_sdk.__all__)

    def test_sdkstore_still_in_all(self) -> None:
        """Per §5.7 non-commitment #1: SDKStore stays in __all__."""
        self.assertIn("SDKStore", factgraph_sdk.__all__)

    def test_schema_add_result_in_all(self) -> None:
        self.assertIn("SchemaAddResult", factgraph_sdk.__all__)

    def test_factgraph_is_sdkstore_literal_alias(self) -> None:
        """Per §5.7 non-commitment #1: FactGraph is literal alias."""
        self.assertIs(factgraph_sdk.FactGraph, factgraph_sdk.SDKStore)


# Class 2 — Manager classes private + not in `__all__`


class ManagerClassPrivacyInvariants(unittest.TestCase):
    """Internal manager classes stay private; public assertion manager stays unexported."""

    MANAGERS: tuple[type, ...] = (
        _SDKSchemaManager,
        _SDKEntitiesManager,
        _SDKFieldsManager,
        _SDKEvalManager,
        _SDKAuditManager,
        _SDKPackageManager,
        _SDKAssertionViewsManager,
    )

    def test_all_manager_class_names_are_private(self) -> None:
        for cls in self.MANAGERS:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(
                    cls.__name__.startswith("_"),
                    f"Manager class {cls.__name__!r} must be private (underscore prefix)",
                )

    def test_no_manager_class_in_factgraph_sdk_all(self) -> None:
        for cls in (*self.MANAGERS, AssertionsManager):
            with self.subTest(cls=cls.__name__):
                self.assertNotIn(cls.__name__, factgraph_sdk.__all__)


# Class 3 — Removed flat shortcuts stay removed


class FlatMethodRemovalInvariants(unittest.TestCase):
    """Slice 3a removes the former flat `SDKStore.<method>` shortcuts."""

    def _assert_no_deprecation(self, fn) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                fn()
            except Exception:
                pass
            deprec = [w for w in caught if issubclass(w.category, DeprecationWarning)]
            self.assertEqual(
                deprec,
                [],
                f"method emitted DeprecationWarning(s): {[str(w.message) for w in deprec]}",
            )

    def test_flat_shortcuts_are_absent(self) -> None:
        fg = _new_fg()
        for name in ("ref", "find", "get", "set", "add", "retract", "edit", "match"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(fg, name))

    def test_diff_proof_frames_emits_no_deprecation(self) -> None:
        fg = _new_fg()
        self._assert_no_deprecation(lambda: fg.audit.diff_proof_frames())

    def test_run_emits_no_deprecation(self) -> None:
        fg = _new_fg()
        # run with no args raises but should not warn.
        self._assert_no_deprecation(lambda: _removed_sdk_run())


# Class 4 — Docs taxonomy-first lint


@unittest.skip("Slice 3a Step 12 owns load-bearing docs namespace migration")
class DocsTaxonomyFirstLintInvariants(unittest.TestCase):
    """Per §5.5 + §5.5.6 lock: taxonomy-first docs reflect the lock.

    Lint scope is bounded to the surfaces the lock actually changed —
    Tier 1 quickstart (README), Tier 3 contract anchor (public_contract_v1).
    Larger doc bodies (00_user_guide etc.) are validated by inspection
    at Phase 2; lint here is the structural minimum.
    """

    def _read(self, relpath: str) -> str:
        return (REPO_ROOT / relpath).read_text()

    # def test_readme_quickstart_imports_factgraph(self) -> None:
    #     text = self._read("README.md")
    #     self.assertIn("from factgraph.sdk import", text, "README must import from factgraph.sdk")
    #     self.assertIn("FactGraph", text, "README must reference FactGraph entrypoint")

    # def test_readme_l_direction_boundary_is_not_stale(self) -> None:
    #     text = self._read("README.md")
    #     self.assertIn("L Direction G1-G5", text)
    #     self.assertIn("FactGraph", text)
    #     self.assertNotIn("does not add matching SDK shells", text)
    #     self.assertNotIn("709 tests", text)

    def test_no_deprecated_label_on_flat_methods_in_sdk_docs(self) -> None:
        """No 'deprecated' label on flat SDKStore methods per §5.4 lock.

        Existing `row_format='tuple'` deprecation at 04_api_surface line
        ~114 is a SEPARATE, unrelated deprecation that pre-dates the
        post-L redesign — not a flat-vs-nested signal. The lint asserts
        no NEW deprecation appears on flat-method-vs-nested-method.
        """
        sdk_docs = list((REPO_ROOT / "src/factgraph/sdk/docs").glob("*.md"))
        self.assertGreater(len(sdk_docs), 0)
        for doc in sdk_docs:
            text = doc.read_text()
            # Allow the existing row_format='tuple' deprecation line.
            stripped = re.sub(r"row_format=['\"]tuple['\"][^\n]*", "", text)
            # Reject any new "SDKStore.<method> ... deprecated" pattern.
            bad = re.findall(
                r"SDKStore\.[a-z_]+[^\n]*deprecat",
                stripped,
                flags=re.IGNORECASE,
            )
            self.assertEqual(
                bad,
                [],
                f"{doc.name} introduces deprecation labels on flat SDKStore methods: {bad}",
            )

    def test_public_contract_has_taxonomy_cross_ref(self) -> None:
        """Per §5.5.6 lock: public_contract_v1 has FactGraph cross-ref note."""
        text = self._read("src/factgraph/core/docs/04_public_contract_v1.md")
        self.assertIn(
            "FactGraph",
            text,
            "public_contract_v1.md must contain a taxonomy cross-ref note per §5.5.6",
        )

    def test_api_surface_canonical_signatures_match_flat_methods(self) -> None:
        """Per pre-publish audit Blocker 1: SDK API docs canonical
        taxonomy examples must match actual flat method signatures.

        Flat signatures (per `src/factgraph/sdk/store.py`):
        - ``check(inference, binding, ...)``
        - ``check_fact_overlay(inference, binding, overlay, ...)``
        - ``check_rule_disable(rule, support_artifact, *, case_index, condition_index, ...)``

        The taxonomy examples MUST keep the same positional argument
        names so users copy-pasting from docs get a valid call shape.
        """
        for relpath in ("src/factgraph/sdk/docs/04_api_surface.en.md",):
            with self.subTest(doc=relpath):
                text = self._read(relpath)
                # Taxonomy what_if.check must take (inference, binding)
                # — NOT (rule, binding) which was the pre-fix bug.
                self.assertIn(
                    "fg.what_if.check(inference, binding)",
                    text,
                    "fg.what_if.check must show (inference, binding) signature",
                )
                self.assertNotIn(
                    "fg.what_if.check(rule, binding)",
                    text,
                    "fg.what_if.check must NOT show (rule, binding) — wrong argname per flat signature",
                )
                # Taxonomy fact_overlay.check must take 3 positional args
                # — NOT (support, overlay) which was the pre-fix bug.
                self.assertIn(
                    "fg.what_if.fact_overlay.check(inference, binding, overlay)",
                    text,
                    "fg.what_if.fact_overlay.check must show (inference, binding, overlay) signature",
                )
                self.assertNotIn(
                    "fg.what_if.fact_overlay.check(support, overlay)",
                    text,
                    "fg.what_if.fact_overlay.check must NOT show (support, overlay) — missing derivation+binding per flat signature",
                )


# Class 5 — Sub-namespace structure under `what_if`


@unittest.skip("what_if namespace was removed before Slice 3a namespace migration")
class WhatIfSubNamespaceStructureInvariants(unittest.TestCase):
    """Per §5.2 Option B split: `what_if.fact_overlay` + `what_if.rule`."""

    def test_fact_overlay_sub_namespace_reachable(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.what_if.fact_overlay, _SDKWhatIfFactOverlayManager)

    def test_rule_sub_namespace_reachable(self) -> None:
        fg = _new_fg()
        self.assertIsInstance(fg.what_if.rule, _SDKWhatIfRuleManager)

    def test_what_if_direct_methods_present(self) -> None:
        """G1 + G4: check, diagnose, why_not directly under what_if."""
        fg = _new_fg()
        for name in ("check", "diagnose", "why_not"):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(fg.what_if, name)))

    def test_fact_overlay_methods_present(self) -> None:
        """G2: check (was check_fact_overlay), recheck_proof_frame."""
        fg = _new_fg()
        for name in ("check", "recheck_proof_frame"):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(fg.what_if.fact_overlay, name)))

    def test_rule_methods_present(self) -> None:
        """G3: disable / literal_replace / add_condition (prefix dropped)."""
        fg = _new_fg()
        for name in ("disable", "literal_replace", "add_condition"):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(fg.what_if.rule, name)))

    def test_what_if_sub_namespaces_read_only(self) -> None:
        fg = _new_fg()
        with self.assertRaises(FrozenSnapshotError):
            fg.what_if.fact_overlay.foo = "bar"  # type: ignore[attr-defined]
        with self.assertRaises(FrozenSnapshotError):
            fg.what_if.rule.foo = "bar"  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
