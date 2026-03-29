"""Tests for write_protocol annotation projection (Step 2).

Covers: shared annotation whitelist projection via set_field/add_field/replace_field,
non-whitelisted keys stay in meta_rows only, confidence category/origin/derivation,
revocation shared annotation dual-write, and dual-write consistency.
"""
from __future__ import annotations

import unittest

from factpy_kernel.core.evidence.write_protocol import (
    WriteProtocolError,
    _SHARED_ANNOTATION_WHITELIST,
    add_field,
    replace_field,
    retract_by_asrt,
    set_field,
)
from factpy_kernel.core.store.ledger import Ledger


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

    def test_confidence_projected_as_shared_derived(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "user:name",
            _eref("alice"),
            [("string", "Alice")],
            meta={"confidence": 0.85},
        )
        annos = ledger.find_annotations(asrt_id=asrt_id, namespace="shared", category="derived")
        self.assertEqual(len(annos), 1)
        self.assertEqual(annos[0].key, "confidence")
        self.assertEqual(annos[0].value, 0.85)
        self.assertEqual(annos[0].kind, "float")
        self.assertEqual(annos[0].origin, "derived")
        self.assertEqual(annos[0].derivation, "meta:confidence")

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
                "confidence": 0.9,
                "approved_by": "reviewer_A",
                "note": "verified manually",
            },
        )
        annos = ledger.find_annotations(asrt_id=asrt_id)
        self.assertEqual(len(annos), 6)

        source_annos = ledger.find_annotations(asrt_id=asrt_id, category="source")
        self.assertEqual(len(source_annos), 5)
        source_keys = {a.key for a in source_annos}
        self.assertEqual(source_keys, {"source", "source_loc", "trace_id", "approved_by", "note"})

        derived_annos = ledger.find_annotations(asrt_id=asrt_id, category="derived")
        self.assertEqual(len(derived_annos), 1)
        self.assertEqual(derived_annos[0].key, "confidence")

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
                "confidence": 0.5,
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

    def test_confidence_in_both_stores(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("e"),
            [("string", "v")],
            meta={"confidence": 0.75},
        )
        meta_conf = ledger.find_meta(asrt_id=asrt_id, key="confidence")
        self.assertEqual(len(meta_conf), 1)
        self.assertEqual(meta_conf[0].value, 0.75)

        anno_conf = ledger.find_annotations(asrt_id=asrt_id, key="confidence")
        self.assertEqual(len(anno_conf), 1)
        self.assertEqual(anno_conf[0].value, 0.75)

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


class TestAddFieldAndReplaceField(unittest.TestCase):
    """add_field and replace_field also produce annotations."""

    def test_add_field_projects_annotations(self) -> None:
        ledger = Ledger()
        asrt_id = add_field(
            ledger,
            "user:tag",
            _eref("alice"),
            [("string", "vip")],
            meta={"source": "crm", "confidence": 0.9},
        )
        annos = ledger.find_annotations(asrt_id=asrt_id)
        self.assertEqual(len(annos), 2)
        keys = {a.key for a in annos}
        self.assertEqual(keys, {"source", "confidence"})

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
            meta={"source": "review", "confidence": 0.4, "confidence_source": "manual:review"},
        )
        self.assertIsNotNone(revoker_id)

        annos = ledger.find_annotations(asrt_id=revoker_id, namespace="shared")
        by_key = {row.key: row for row in annos}
        self.assertEqual(by_key["source"].origin, "observed")
        self.assertEqual(by_key["source"].value, "review")
        self.assertEqual(by_key["confidence"].origin, "derived")
        self.assertEqual(by_key["confidence"].derivation, "manual:review")
        self.assertEqual(by_key["confidence"].value, 0.4)


class TestWhitelistCoverage(unittest.TestCase):
    """Verify whitelist is complete and categories are correct."""

    def test_whitelist_categories_are_valid(self) -> None:
        from factpy_kernel.core.store.ledger import ANNOTATION_CATEGORIES

        for key, (category, origin) in _SHARED_ANNOTATION_WHITELIST.items():
            self.assertIn(category, ANNOTATION_CATEGORIES, f"whitelist key={key} has invalid category={category}")

    def test_whitelist_origins_are_valid(self) -> None:
        from factpy_kernel.core.store.ledger import ANNOTATION_ORIGINS

        for key, (category, origin) in _SHARED_ANNOTATION_WHITELIST.items():
            self.assertIn(origin, ANNOTATION_ORIGINS, f"whitelist key={key} has invalid origin={origin}")

    def test_confidence_is_derived_not_source(self) -> None:
        cat, origin = _SHARED_ANNOTATION_WHITELIST["confidence"]
        self.assertEqual(cat, "derived")
        self.assertEqual(origin, "derived")

    def test_source_keys_are_source_category(self) -> None:
        for key in ("source", "source_loc", "trace_id", "approved_by", "note"):
            cat, _ = _SHARED_ANNOTATION_WHITELIST[key]
            self.assertEqual(cat, "source", f"key={key} should be category=source")


class TestProbabilityWriteLane(unittest.TestCase):
    """probability is a first-class semantic key, separate from confidence."""

    def test_probability_projected_as_shared_semantic(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("x"),
            [("string", "v")],
            meta={"probability": 0.42},
        )
        anns = ledger.find_annotations(asrt_id=asrt_id, key="probability")
        self.assertEqual(len(anns), 1)
        self.assertEqual(anns[0].namespace, "shared")
        self.assertEqual(anns[0].category, "semantic")
        self.assertEqual(anns[0].value, 0.42)
        self.assertEqual(anns[0].origin, "observed")

    def test_probability_also_in_meta_rows(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("x"),
            [("string", "v")],
            meta={"probability": 0.65},
        )
        meta = ledger.find_meta(asrt_id=asrt_id, key="probability")
        self.assertEqual(len(meta), 1)
        self.assertAlmostEqual(meta[0].value, 0.65)

    def test_probability_auto_derives_confidence(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("x"),
            [("string", "v")],
            meta={"probability": 0.42},
        )
        conf_anns = ledger.find_annotations(asrt_id=asrt_id, key="confidence")
        self.assertEqual(len(conf_anns), 1)
        self.assertAlmostEqual(conf_anns[0].value, 0.42)
        self.assertEqual(conf_anns[0].category, "derived")

        meta_conf = ledger.find_meta(asrt_id=asrt_id, key="confidence")
        self.assertEqual(len(meta_conf), 1)
        self.assertAlmostEqual(meta_conf[0].value, 0.42)

    def test_explicit_confidence_not_overwritten_by_probability(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("x"),
            [("string", "v")],
            meta={"probability": 0.42, "confidence": 0.9},
        )
        conf_anns = ledger.find_annotations(asrt_id=asrt_id, key="confidence")
        self.assertEqual(len(conf_anns), 1)
        self.assertAlmostEqual(conf_anns[0].value, 0.9)

    def test_probability_without_confidence_still_works(self) -> None:
        ledger = Ledger()
        asrt_id = set_field(
            ledger,
            "p:test",
            _eref("x"),
            [("string", "v")],
            meta={"probability": 0.7, "source": "model"},
        )
        anns = ledger.find_annotations(asrt_id=asrt_id)
        keys = {a.key for a in anns}
        self.assertIn("probability", keys)
        self.assertIn("confidence", keys)
        self.assertIn("source", keys)

    def test_probability_whitelist_category_is_semantic(self) -> None:
        cat, origin = _SHARED_ANNOTATION_WHITELIST["probability"]
        self.assertEqual(cat, "semantic")
        self.assertEqual(origin, "observed")


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
        """confidence='bad' should raise before revoking the old assertion."""
        ledger, old_asrt_id = self._setup_existing()

        with self.assertRaises(WriteProtocolError):
            replace_field(
                ledger,
                "user:name",
                _eref("alice"),
                old_rest_terms=[("string", "Alice")],
                new_rest_terms=[("string", "Alice Updated")],
                meta={"confidence": "bad"},
            )

        # Old assertion must still be active (not revoked).
        self.assertIsNone(ledger.find_revoker(old_asrt_id))
        self.assertFalse(ledger.has_active_revocation(old_asrt_id))

    def test_invalid_probability_preserves_old_assertion(self) -> None:
        """probability=2.0 should raise before revoking the old assertion."""
        ledger, old_asrt_id = self._setup_existing()

        with self.assertRaises(WriteProtocolError):
            replace_field(
                ledger,
                "user:name",
                _eref("alice"),
                old_rest_terms=[("string", "Alice")],
                new_rest_terms=[("string", "Alice Updated")],
                meta={"probability": 2.0},
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
