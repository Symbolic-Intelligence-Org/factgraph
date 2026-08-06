"""Tests for write_protocol annotation projection (Step 2).

Covers: shared annotation whitelist projection via set_field/add_field/replace_field,
non-whitelisted keys stay in meta_rows only, confidence category/origin/derivation,
revocation shared annotation dual-write, and dual-write consistency.
"""
from __future__ import annotations

import unittest

from factgraph.core.evidence.write_protocol import (
    WriteProtocolError,
    _SHARED_ANNOTATION_WHITELIST,
    add_field,
    replace_field,
    retract_by_asrt,
    set_field,
)
from factgraph.core.store.ledger import Ledger


def _eref(token: str) -> str:
    return f"idref_v1:User:{token}"


class TestSetFieldAnnotationProjection(unittest.TestCase):
    """set_field writes whitelisted meta keys to annotation_rows."""

    def test_source_projected_as_shared_source(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "user:name",
            _eref("alice"),
            [("string", "Alice")],
            meta={"source": "ESA handbook"},
        )
        annos = ledger.find_annotations(asrt_id=asrt_id, namespace="shared", category="source")
        self.assertEqual(len(annos), 1)
        self.assertEqual(annos[0].key, "source")
        self.assertEqual(annos[0].value, "ESA handbook")
        self.assertEqual(annos[0].kind, "str")
        self.assertEqual(annos[0].origin, "observed")
        self.assertIsNone(annos[0].derivation)

    def test_raw_uncertainty_point_estimate_projects_meta_and_annotations(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "user:name",
            _eref("alice"),
            [("string", "Alice")],
            meta={"raw_kind": "probabilistic", "bound": [0.85, 0.85]},
        )
        meta = {row.key: row.value for row in ledger.find_meta(asrt_id=asrt_id)}
        self.assertEqual(meta["raw_kind"], "probabilistic")
        self.assertEqual(meta["bound"], [0.85, 0.85])

        annos = ledger.find_annotations(asrt_id=asrt_id, namespace="shared", category="semantic")
        by_key = {row.key: row.value for row in annos}
        self.assertEqual(by_key["raw_kind"], "probabilistic")
        self.assertEqual(by_key["bound"], [0.85, 0.85])

    def test_multiple_whitelisted_keys(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "user:name",
            _eref("alice"),
            [("string", "Alice")],
            meta={
                "source": "handbook",
                "source_loc": "ch3.2",
                "trace_id": "t001",
                "raw_kind": "probabilistic",
                "bound": [0.9, 0.9],
                "approved_by": "reviewer_A",
                "note": "verified manually",
            },
        )
        annos = ledger.find_annotations(asrt_id=asrt_id)
        self.assertEqual(len(annos), 7)

        source_annos = ledger.find_annotations(asrt_id=asrt_id, category="source")
        self.assertEqual(len(source_annos), 5)
        source_keys = {a.key for a in source_annos}
        self.assertEqual(source_keys, {"source", "source_loc", "trace_id", "approved_by", "note"})

        derived_annos = ledger.find_annotations(asrt_id=asrt_id, category="derived")
        self.assertEqual(derived_annos, [])

    def test_all_whitelist_keys_are_namespace_shared(self) -> None:
        """Every annotation produced by write_protocol must be namespace='shared'."""
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("e"),
            [("string", "v")],
            meta={
                "source": "s",
                "source_loc": "sl",
                "trace_id": "t",
                "raw_kind": "probabilistic",
                "bound": [0.5, 0.5],
                "approved_by": "a",
                "note": "n",
            },
        )
        for anno in ledger.find_annotations(asrt_id=asrt_id):
            self.assertEqual(anno.namespace, "shared", f"annotation key={anno.key} has wrong namespace")


class TestNonWhitelistedKeysExcluded(unittest.TestCase):
    """Non-whitelisted meta keys must NOT appear in annotation_rows."""

    def test_custom_meta_stays_in_meta_rows_only(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "user:name",
            _eref("alice"),
            [("string", "Alice")],
            meta={"source": "handbook", "custom_field": "custom_value"},
        )
        annos = ledger.find_annotations(asrt_id=asrt_id)
        anno_keys = {a.key for a in annos}
        self.assertIn("source", anno_keys)
        self.assertNotIn("custom_field", anno_keys)

        meta = ledger.find_meta(asrt_id=asrt_id, key="custom_field")
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta[0].value, "custom_value")

    def test_no_meta_means_no_annotations(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(ledger, "p:test", _eref("e"), [("string", "v")])
        annos = ledger.find_annotations(asrt_id=asrt_id)
        self.assertEqual(len(annos), 0)

    def test_only_custom_meta_means_no_annotations(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("e"),
            [("string", "v")],
            meta={"my_custom": "value"},
        )
        annos = ledger.find_annotations(asrt_id=asrt_id)
        self.assertEqual(len(annos), 0)


class TestDualWriteConsistency(unittest.TestCase):
    """meta_rows and annotation_rows contain consistent values."""

    def test_raw_uncertainty_in_both_stores(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("e"),
            [("string", "v")],
            meta={"raw_kind": "probabilistic", "bound": [0.75, 0.75]},
        )
        meta_bound = ledger.find_meta(asrt_id=asrt_id, key="bound")
        self.assertEqual(len(meta_bound), 1)
        self.assertEqual(meta_bound[0].value, [0.75, 0.75])

        anno_bound = ledger.find_annotations(asrt_id=asrt_id, key="bound")
        self.assertEqual(len(anno_bound), 1)
        self.assertEqual(anno_bound[0].value, [0.75, 0.75])

    def test_source_in_both_stores(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("e"),
            [("string", "v")],
            meta={"source": "handbook"},
        )
        meta_src = ledger.find_meta(asrt_id=asrt_id, key="source")
        self.assertEqual(len(meta_src), 1)
        self.assertEqual(meta_src[0].value, "handbook")

        anno_src = ledger.find_annotations(asrt_id=asrt_id, key="source")
        self.assertEqual(len(anno_src), 1)
        self.assertEqual(anno_src[0].value, "handbook")


class TestRawUncertaintyWriteLane(unittest.TestCase):
    """raw_kind/bound are the canonical Phase 1 raw uncertainty write lane."""

    def test_raw_uncertainty_projected_as_shared_semantic_and_meta_rows(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:risk",
            _eref("asset-17"),
            [("string", "elevated")],
            meta={"raw_kind": "probabilistic", "bound": [0.2, 0.8]},
        )

        raw_kind_meta = ledger.find_meta(asrt_id=asrt_id, key="raw_kind")
        bound_meta = ledger.find_meta(asrt_id=asrt_id, key="bound")
        self.assertEqual(len(raw_kind_meta), 1)
        self.assertEqual(len(bound_meta), 1)
        self.assertEqual(raw_kind_meta[0].kind, "str")
        self.assertEqual(raw_kind_meta[0].value, "probabilistic")
        self.assertEqual(bound_meta[0].kind, "json")
        self.assertEqual(bound_meta[0].value, [0.2, 0.8])

        annos = ledger.find_annotations(asrt_id=asrt_id, namespace="shared", category="semantic")
        by_key = {row.key: row for row in annos}
        self.assertEqual(set(by_key), {"raw_kind", "bound"})
        self.assertEqual(by_key["raw_kind"].kind, "str")
        self.assertEqual(by_key["raw_kind"].value, "probabilistic")
        self.assertEqual(by_key["raw_kind"].origin, "observed")
        self.assertIsNone(by_key["raw_kind"].derivation)
        self.assertEqual(by_key["bound"].kind, "json")
        self.assertEqual(by_key["bound"].value, [0.2, 0.8])
        self.assertEqual(by_key["bound"].origin, "observed")
        self.assertIsNone(by_key["bound"].derivation)

    def test_possibilistic_raw_uncertainty_accepts_integer_bounds_and_normalizes(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:allowed",
            _eref("asset-17"),
            [("bool", True)],
            meta={"raw_kind": "possibilistic", "bound": [0, 1]},
        )

        meta = ledger.find_meta(asrt_id=asrt_id, key="bound")
        self.assertEqual(len(meta), 1)
        self.assertEqual(meta[0].value, [0.0, 1.0])

        annos = ledger.find_annotations(asrt_id=asrt_id, key="bound")
        self.assertEqual(len(annos), 1)
        self.assertEqual(annos[0].value, [0.0, 1.0])

    def test_raw_kind_and_bound_must_be_written_together(self) -> None:
        cases = (
            {"raw_kind": "probabilistic"},
            {"bound": [0.2, 0.8]},
        )
        for meta in cases:
            with self.subTest(meta=meta):
                with self.assertRaises(WriteProtocolError) as ctx:
                    set_field(Ledger(), "p:risk", _eref("asset-17"), [("string", "v")], meta=meta)
                self.assertIn("raw_kind", str(ctx.exception))
                self.assertIn("bound", str(ctx.exception))

    def test_invalid_raw_kind_rejected(self) -> None:
        for raw_kind in ("probability", "PROBABILISTIC", "", 3):
            with self.subTest(raw_kind=raw_kind):
                with self.assertRaises(WriteProtocolError) as ctx:
                    set_field(
                        Ledger(),
                        "p:risk",
                        _eref("asset-17"),
                        [("string", "v")],
                        meta={"raw_kind": raw_kind, "bound": [0.2, 0.8]},
                    )
                self.assertIn("raw_kind", str(ctx.exception))

    def test_invalid_bound_shape_rejected(self) -> None:
        cases = (
            [0.2],
            [0.2, 0.8, 0.9],
            (0.2, 0.8),
            {"lower": 0.2, "upper": 0.8},
            "0.2,0.8",
        )
        for bound in cases:
            with self.subTest(bound=bound):
                with self.assertRaises(WriteProtocolError) as ctx:
                    set_field(
                        Ledger(),
                        "p:risk",
                        _eref("asset-17"),
                        [("string", "v")],
                        meta={"raw_kind": "probabilistic", "bound": bound},
                    )
                self.assertIn("bound", str(ctx.exception))

    def test_invalid_bound_values_rejected(self) -> None:
        cases = (
            [True, 0.8],
            [0.2, False],
            ["0.2", 0.8],
            [0.2, "0.8"],
            [-0.1, 0.8],
            [0.2, 1.1],
            [0.9, 0.2],
        )
        for bound in cases:
            with self.subTest(bound=bound):
                with self.assertRaises(WriteProtocolError) as ctx:
                    set_field(
                        Ledger(),
                        "p:risk",
                        _eref("asset-17"),
                        [("string", "v")],
                        meta={"raw_kind": "probabilistic", "bound": bound},
                    )
                self.assertIn("bound", str(ctx.exception))


class TestAddFieldAndReplaceField(unittest.TestCase):
    """add_field and replace_field also produce annotations."""

    def test_add_field_projects_annotations(self) -> None:
        ledger = Ledger()
        asrt_id = add_field(
            ledger,
            "user:tag",
            _eref("alice"),
            [("string", "vip")],
            meta={"source": "crm", "raw_kind": "probabilistic", "bound": [0.9, 0.9]},
        )
        annos = ledger.find_annotations(asrt_id=asrt_id)
        self.assertEqual(len(annos), 3)
        keys = {a.key for a in annos}
        self.assertEqual(keys, {"source", "raw_kind", "bound"})

    def test_replace_field_new_assertion_has_annotations(self) -> None:
        ledger = Ledger()
        set_field(
            ledger,
            "user:name",
            _eref("alice"),
            [("string", "Alice")],
            meta={"source": "initial"},
        )
        _, new_id = replace_field(
            ledger,
            "user:name",
            _eref("alice"),
            old_rest_terms=[("string", "Alice")],
            new_rest_terms=[("string", "Alice Updated")],
            meta={"source": "correction"},
        )
        new_annos = ledger.find_annotations(asrt_id=new_id)
        self.assertGreaterEqual(len(new_annos), 1)
        source_anno = [a for a in new_annos if a.key == "source"]
        self.assertEqual(len(source_anno), 1)
        self.assertEqual(source_anno[0].value, "correction")


class TestRetractAnnotationProjection(unittest.TestCase):
    """Revocations project shared annotations when whitelisted meta is provided."""

    def test_retract_no_annotations(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("e"),
            [("string", "v")],
            meta={"source": "s"},
        )
        original_anno_count = len(ledger.annotation_rows)

        revoker_id = retract_by_asrt(ledger, asrt_id)
        self.assertIsNotNone(revoker_id)

        revoker_annos = ledger.find_annotations(asrt_id=revoker_id)
        self.assertEqual(len(revoker_annos), 0)
        self.assertEqual(len(ledger.annotation_rows), original_anno_count)

    def test_retract_projects_whitelisted_meta(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("e"),
            [("string", "v")],
            meta={"source": "s"},
        )

        revoker_id = retract_by_asrt(
            ledger,
            asrt_id,
            meta={"source": "review", "raw_kind": "probabilistic", "bound": [0.4, 0.4]},
        )
        self.assertIsNotNone(revoker_id)

        annos = ledger.find_annotations(asrt_id=revoker_id, namespace="shared")
        by_key = {row.key: row for row in annos}
        self.assertEqual(by_key["source"].origin, "observed")
        self.assertEqual(by_key["source"].value, "review")
        self.assertNotIn("confidence", by_key)
        self.assertEqual(by_key["bound"].value, [0.4, 0.4])

    def test_retract_by_asrt_rejects_system_claim_target_without_writing(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("system-target"),
            [("string", "v")],
        )
        revoker_id = retract_by_asrt(ledger, asrt_id)
        before_claims = tuple(ledger.claims)
        before_revokes = tuple(ledger.revokes)
        before_meta = tuple(ledger.meta_rows)

        with self.assertRaisesRegex(WriteProtocolError, "revoke-of-revoke is forbidden"):
            retract_by_asrt(ledger, revoker_id)

        self.assertEqual(tuple(ledger.claims), before_claims)
        self.assertEqual(tuple(ledger.revokes), before_revokes)
        self.assertEqual(tuple(ledger.meta_rows), before_meta)


class TestWhitelistCoverage(unittest.TestCase):
    """Verify whitelist is complete and categories are correct."""

    def test_whitelist_categories_are_valid(self) -> None:
        from factgraph.core.store.ledger import ANNOTATION_CATEGORIES

        for key, (category, origin) in _SHARED_ANNOTATION_WHITELIST.items():
            self.assertIn(category, ANNOTATION_CATEGORIES, f"whitelist key={key} has invalid category={category}")

    def test_whitelist_origins_are_valid(self) -> None:
        from factgraph.core.store.ledger import ANNOTATION_ORIGINS

        for key, (category, origin) in _SHARED_ANNOTATION_WHITELIST.items():
            self.assertIn(origin, ANNOTATION_ORIGINS, f"whitelist key={key} has invalid origin={origin}")

    def test_confidence_is_not_shared_annotation_key(self) -> None:
        self.assertNotIn("confidence", _SHARED_ANNOTATION_WHITELIST)

    def test_source_keys_are_source_category(self) -> None:
        for key in ("source", "source_loc", "trace_id", "approved_by", "note"):
            cat, _ = _SHARED_ANNOTATION_WHITELIST[key]
            self.assertEqual(cat, "source", f"key={key} should be category=source")


class TestRemovedUncertaintyWriteKeys(unittest.TestCase):
    """Removed raw uncertainty write keys are rejected for user-authored meta."""

    def test_removed_uncertainty_keys_rejected(self) -> None:
        for key in ("probability", "bound_lower", "bound_upper"):
            with self.subTest(key=key):
                with self.assertRaises(WriteProtocolError) as ctx:
                    set_field(
                        Ledger(),
                        "p:test",
                        _eref("x"),
                        [("string", "v")],
                        meta={key: 0.42},
                    )
                self.assertIn(key, str(ctx.exception))

    def test_probability_no_longer_whitelisted_for_user_meta_projection(self) -> None:
        self.assertNotIn("probability", _SHARED_ANNOTATION_WHITELIST)


class TestReplaceFieldAtomicity(unittest.TestCase):
    """F-CORE-1: replace_field must not revoke old assertion if new assertion validation fails."""

    def _setup_existing(self) -> tuple[Ledger, str]:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "user:name",
            _eref("alice"),
            [("string", "Alice")],
            meta={"source": "initial"},
        )
        return ledger, asrt_id

    def test_invalid_meta_preserves_old_assertion(self) -> None:
        """Invalid raw uncertainty should raise before revoking the old assertion."""
        ledger, old_asrt_id = self._setup_existing()

        with self.assertRaises(WriteProtocolError):
            replace_field(
                ledger,
                "user:name",
                _eref("alice"),
                old_rest_terms=[("string", "Alice")],
                new_rest_terms=[("string", "Alice Updated")],
                meta={"raw_kind": "probabilistic", "bound": "bad"},
            )

        # Old assertion must still be active (not revoked).
        self.assertIsNone(ledger.find_revoker(old_asrt_id))
        self.assertFalse(ledger.has_active_revocation(old_asrt_id))

    def test_invalid_raw_uncertainty_preserves_old_assertion(self) -> None:
        """Invalid raw uncertainty should raise before revoking the old assertion."""
        ledger, old_asrt_id = self._setup_existing()

        with self.assertRaises(WriteProtocolError):
            replace_field(
                ledger,
                "user:name",
                _eref("alice"),
                old_rest_terms=[("string", "Alice")],
                new_rest_terms=[("string", "Alice Updated")],
                meta={"raw_kind": "probabilistic", "bound": [0.9, 0.2]},
            )

        self.assertIsNone(ledger.find_revoker(old_asrt_id))
        self.assertFalse(ledger.has_active_revocation(old_asrt_id))

    def test_valid_replacement_still_works(self) -> None:
        """Happy path regression: valid replace should revoke old and create new."""
        ledger, old_asrt_id = self._setup_existing()

        revoker_id, new_id = replace_field(
            ledger,
            "user:name",
            _eref("alice"),
            old_rest_terms=[("string", "Alice")],
            new_rest_terms=[("string", "Alice Updated")],
            meta={"source": "correction"},
        )

        # Old assertion must be revoked.
        self.assertIsNotNone(revoker_id)
        self.assertTrue(ledger.has_active_revocation(old_asrt_id))

        # New assertion must exist with correct annotations.
        new_annos = ledger.find_annotations(asrt_id=new_id)
        source_annos = [a for a in new_annos if a.key == "source"]
        self.assertEqual(len(source_annos), 1)
        self.assertEqual(source_annos[0].value, "correction")


if __name__ == "__main__":
    unittest.main()
