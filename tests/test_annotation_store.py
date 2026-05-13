"""Tests for Annotation Store (ledger annotation_rows).

Covers: AnnotationRow dataclass, append_assertion with annotations,
append_annotations (standalone), find_annotations (all filter combos),
upsert semantics, validation, persistence round-trip, and backward
compatibility with meta_rows.
"""
from __future__ import annotations

import unittest

from factpy.core.store.ledger import (
    ANNOTATION_CATEGORIES,
    ANNOTATION_ORIGINS,
    META_KINDS,
    AnnotationRow,
    Claim,
    ClaimArg,
    Ledger,
    MetaRow,
)


def _make_ledger_with_claim(asrt_id: str = "a001") -> Ledger:
    """Create an in-memory ledger with one claim already appended."""
    ledger = Ledger()
    ledger.append_assertion(
        claim=Claim(asrt_id="", pred_id="user:name", e_ref="alice", rest_terms=[("string", "Alice")]),
        claim_args=[ClaimArg(asrt_id="", idx=0, val_atom="Alice", tag="string")],
        meta_rows=[MetaRow(asrt_id="", key="confidence", kind="float", value=0.8)],
        asrt_id=asrt_id,
    )
    return ledger


def _anno(
    asrt_id: str = "a001",
    namespace: str = "pyreason",
    category: str = "semantic",
    key: str = "bound_lower",
    kind: str = "float",
    value: float | str | int | bool = 0.6,
    origin: str = "observed",
    derivation: str | None = None,
) -> AnnotationRow:
    return AnnotationRow(
        asrt_id=asrt_id,
        namespace=namespace,
        category=category,
        key=key,
        kind=kind,
        value=value,
        origin=origin,
        derivation=derivation,
    )


class TestAnnotationRowDataclass(unittest.TestCase):
    """AnnotationRow frozen dataclass basics."""

    def test_frozen(self) -> None:
        row = _anno()
        with self.assertRaises(AttributeError):
            row.value = 0.9  # type: ignore[misc]

    def test_derivation_defaults_to_none(self) -> None:
        row = _anno()
        self.assertIsNone(row.derivation)

    def test_equality(self) -> None:
        a = _anno(value=0.6)
        b = _anno(value=0.6)
        self.assertEqual(a, b)


class TestAppendAssertionWithAnnotations(unittest.TestCase):
    """append_assertion(..., annotation_rows=[...]) integration."""

    def test_annotations_written_atomically_with_claim(self) -> None:
        ledger = Ledger()
        annos = [
            _anno(key="bound_lower", value=0.6),
            _anno(key="bound_upper", value=0.9),
            _anno(
                namespace="shared",
                category="derived",
                key="confidence",
                value=0.6,
                origin="derived",
                derivation="pyreason:lower_bound",
            ),
        ]
        result = ledger.append_assertion(
            claim=Claim(asrt_id="", pred_id="user:name", e_ref="alice", rest_terms=[("string", "Alice")]),
            claim_args=[ClaimArg(asrt_id="", idx=0, val_atom="Alice", tag="string")],
            meta_rows=[MetaRow(asrt_id="", key="confidence", kind="float", value=0.6)],
            annotation_rows=annos,
            asrt_id="a001",
        )
        self.assertTrue(result.written)
        found = ledger.find_annotations(asrt_id="a001")
        self.assertEqual(len(found), 3)
        keys = {r.key for r in found}
        self.assertEqual(keys, {"bound_lower", "bound_upper", "confidence"})

    def test_annotations_get_effective_asrt_id(self) -> None:
        """Annotations should use the effective asrt_id, not the placeholder."""
        ledger = Ledger()
        anno = _anno(asrt_id="placeholder")
        ledger.append_assertion(
            claim=Claim(asrt_id="", pred_id="p", e_ref="e", rest_terms=[]),
            claim_args=[],
            meta_rows=[],
            annotation_rows=[anno],
            asrt_id="real_id",
        )
        found = ledger.find_annotations(asrt_id="real_id")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].asrt_id, "real_id")
        self.assertEqual(len(ledger.find_annotations(asrt_id="placeholder")), 0)

    def test_no_annotations_is_fine(self) -> None:
        ledger = Ledger()
        result = ledger.append_assertion(
            claim=Claim(asrt_id="", pred_id="p", e_ref="e", rest_terms=[]),
            claim_args=[],
            meta_rows=[],
            asrt_id="a001",
        )
        self.assertTrue(result.written)
        self.assertEqual(len(ledger.annotation_rows), 0)

    def test_empty_annotation_list_is_fine(self) -> None:
        ledger = Ledger()
        result = ledger.append_assertion(
            claim=Claim(asrt_id="", pred_id="p", e_ref="e", rest_terms=[]),
            claim_args=[],
            meta_rows=[],
            annotation_rows=[],
            asrt_id="a001",
        )
        self.assertTrue(result.written)
        self.assertEqual(len(ledger.annotation_rows), 0)


class TestAppendAnnotations(unittest.TestCase):
    """Standalone append_annotations() after claim exists."""

    def test_basic_append(self) -> None:
        ledger = _make_ledger_with_claim()
        ledger.append_annotations([
            _anno(key="bound_lower", value=0.6),
            _anno(key="bound_upper", value=0.9),
        ])
        self.assertEqual(len(ledger.annotation_rows), 2)

    def test_rejects_unknown_asrt_id(self) -> None:
        ledger = _make_ledger_with_claim()
        with self.assertRaises(ValueError) as ctx:
            ledger.append_annotations([_anno(asrt_id="nonexistent")])
        self.assertIn("unknown asrt_id", str(ctx.exception))

    def test_upsert_same_key(self) -> None:
        """INSERT OR REPLACE: updating same (asrt_id, ns, cat, key) replaces."""
        ledger = _make_ledger_with_claim()
        ledger.append_annotations([_anno(key="bound_lower", value=0.6)])
        self.assertEqual(len(ledger.annotation_rows), 1)
        self.assertEqual(ledger.annotation_rows[0].value, 0.6)

        ledger.append_annotations([_anno(key="bound_lower", value=0.7)])
        self.assertEqual(len(ledger.annotation_rows), 1)
        self.assertEqual(ledger.annotation_rows[0].value, 0.7)

    def test_upsert_does_not_leave_stale_index_entries(self) -> None:
        """After upsert, old value should not appear in any index."""
        ledger = _make_ledger_with_claim()
        ledger.append_annotations([_anno(key="bound_lower", value=0.6)])
        ledger.append_annotations([_anno(key="bound_lower", value=0.7)])

        found = ledger.find_annotations(asrt_id="a001", key="bound_lower")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].value, 0.7)

        found_by_ns = ledger.find_annotations(namespace="pyreason", category="semantic")
        values = [r.value for r in found_by_ns if r.key == "bound_lower"]
        self.assertEqual(values, [0.7])

    def test_multiple_assertions_independent(self) -> None:
        """Annotations for different assertions don't interfere."""
        ledger = Ledger()
        for aid in ("a001", "a002"):
            ledger.append_assertion(
                claim=Claim(asrt_id="", pred_id="p", e_ref=aid, rest_terms=[]),
                claim_args=[],
                meta_rows=[],
                asrt_id=aid,
            )
        ledger.append_annotations([_anno(asrt_id="a001", key="bound_lower", value=0.6)])
        ledger.append_annotations([_anno(asrt_id="a002", key="bound_lower", value=0.8)])

        self.assertEqual(ledger.find_annotations(asrt_id="a001")[0].value, 0.6)
        self.assertEqual(ledger.find_annotations(asrt_id="a002")[0].value, 0.8)


class TestFindAnnotations(unittest.TestCase):
    """find_annotations() with various filter combinations."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = _make_ledger_with_claim()
        cls.ledger.append_annotations([
            _anno(namespace="pyreason", category="semantic", key="bound_lower", value=0.6),
            _anno(namespace="pyreason", category="semantic", key="bound_upper", value=0.9),
            _anno(
                namespace="shared",
                category="source",
                key="source",
                kind="str",
                value="ESA handbook",
                origin="observed",
            ),
            _anno(
                namespace="shared",
                category="derived",
                key="confidence",
                kind="float",
                value=0.6,
                origin="derived",
                derivation="pyreason:lower_bound",
            ),
            _anno(
                namespace="shared",
                category="operational",
                key="truncated",
                kind="bool",
                value=False,
                origin="observed",
            ),
        ])

    def test_all(self) -> None:
        self.assertEqual(len(self.ledger.find_annotations()), 5)

    def test_by_asrt_id(self) -> None:
        self.assertEqual(len(self.ledger.find_annotations(asrt_id="a001")), 5)
        self.assertEqual(len(self.ledger.find_annotations(asrt_id="nonexistent")), 0)

    def test_by_namespace_category(self) -> None:
        found = self.ledger.find_annotations(namespace="pyreason", category="semantic")
        self.assertEqual(len(found), 2)
        keys = {r.key for r in found}
        self.assertEqual(keys, {"bound_lower", "bound_upper"})

    def test_by_key(self) -> None:
        found = self.ledger.find_annotations(key="confidence")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].namespace, "shared")
        self.assertEqual(found[0].category, "derived")

    def test_by_asrt_id_and_namespace(self) -> None:
        found = self.ledger.find_annotations(asrt_id="a001", namespace="pyreason")
        self.assertEqual(len(found), 2)

    def test_by_asrt_id_and_category(self) -> None:
        found = self.ledger.find_annotations(asrt_id="a001", category="source")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].key, "source")

    def test_by_asrt_id_namespace_category_key(self) -> None:
        found = self.ledger.find_annotations(
            asrt_id="a001",
            namespace="pyreason",
            category="semantic",
            key="bound_lower",
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].value, 0.6)

    def test_no_match_returns_empty(self) -> None:
        self.assertEqual(len(self.ledger.find_annotations(namespace="problog")), 0)


class TestAnnotationValidation(unittest.TestCase):
    """Validation rules from _validate_annotation_rows."""

    def test_reject_empty_asrt_id(self) -> None:
        ledger = _make_ledger_with_claim()
        with self.assertRaises(ValueError):
            ledger.append_annotations([_anno(asrt_id="")])

    def test_reject_empty_namespace(self) -> None:
        ledger = _make_ledger_with_claim()
        with self.assertRaises(ValueError):
            ledger.append_annotations([_anno(namespace="")])

    def test_reject_invalid_category(self) -> None:
        ledger = _make_ledger_with_claim()
        with self.assertRaises(ValueError):
            ledger.append_annotations([_anno(category="unknown_cat")])

    def test_reject_empty_key(self) -> None:
        ledger = _make_ledger_with_claim()
        with self.assertRaises(ValueError):
            ledger.append_annotations([_anno(key="")])

    def test_reject_invalid_kind(self) -> None:
        ledger = _make_ledger_with_claim()
        with self.assertRaises(ValueError):
            ledger.append_annotations([_anno(kind="interval")])

    def test_reject_invalid_origin(self) -> None:
        ledger = _make_ledger_with_claim()
        with self.assertRaises(ValueError):
            ledger.append_annotations([_anno(origin="guessed")])

    def test_reject_derived_without_derivation(self) -> None:
        ledger = _make_ledger_with_claim()
        with self.assertRaises(ValueError):
            ledger.append_annotations([_anno(origin="derived", derivation=None)])

    def test_accept_all_valid_categories(self) -> None:
        ledger = _make_ledger_with_claim()
        for i, cat in enumerate(sorted(ANNOTATION_CATEGORIES)):
            origin = "derived" if cat == "derived" else "observed"
            derivation = "test" if origin == "derived" else None
            ledger.append_annotations([
                _anno(
                    key=f"test_{cat}_{i}",
                    category=cat,
                    origin=origin,
                    derivation=derivation,
                ),
            ])
        self.assertEqual(len(ledger.annotation_rows), len(ANNOTATION_CATEGORIES))

    def test_accept_all_valid_kinds(self) -> None:
        ledger = _make_ledger_with_claim()
        sample_values = {
            "str": "x",
            "int": 1,
            "float": 0.5,
            "bool": True,
            "time": 123456789,
            "json": {"k": "v"},
        }
        for i, kind in enumerate(sorted(META_KINDS)):
            ledger.append_annotations([
                _anno(key=f"test_{kind}_{i}", kind=kind, value=sample_values[kind]),
            ])
        self.assertEqual(len(ledger.annotation_rows), len(META_KINDS))

    def test_accept_all_valid_origins(self) -> None:
        ledger = _make_ledger_with_claim()
        for i, origin in enumerate(sorted(ANNOTATION_ORIGINS)):
            derivation = "test" if origin == "derived" else None
            ledger.append_annotations([
                _anno(key=f"test_{origin}_{i}", origin=origin, derivation=derivation),
            ])
        self.assertEqual(len(ledger.annotation_rows), len(ANNOTATION_ORIGINS))


class TestAnnotationPersistence(unittest.TestCase):
    """Round-trip: write -> reload from SQLite -> verify."""

    def test_round_trip_in_memory(self) -> None:
        ledger = _make_ledger_with_claim()
        annos = [
            _anno(key="bound_lower", value=0.6),
            _anno(
                namespace="shared",
                category="derived",
                key="confidence",
                value=0.6,
                origin="derived",
                derivation="pyreason:lower_bound",
            ),
        ]
        ledger.append_annotations(annos)

        ledger._load_from_db()

        found = ledger.find_annotations(asrt_id="a001")
        self.assertEqual(len(found), 2)

        bound = [r for r in found if r.key == "bound_lower"][0]
        self.assertEqual(bound.value, 0.6)
        self.assertEqual(bound.namespace, "pyreason")
        self.assertEqual(bound.category, "semantic")
        self.assertEqual(bound.origin, "observed")
        self.assertIsNone(bound.derivation)

        conf = [r for r in found if r.key == "confidence"][0]
        self.assertEqual(conf.value, 0.6)
        self.assertEqual(conf.origin, "derived")
        self.assertEqual(conf.derivation, "pyreason:lower_bound")

    def test_upsert_persists_after_reload(self) -> None:
        ledger = _make_ledger_with_claim()
        ledger.append_annotations([_anno(key="bound_lower", value=0.6)])
        ledger.append_annotations([_anno(key="bound_lower", value=0.7)])

        ledger._load_from_db()

        found = ledger.find_annotations(asrt_id="a001", key="bound_lower")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].value, 0.7)


class TestAnnotationPropertyAndIsolation(unittest.TestCase):
    """annotation_rows property and isolation from meta_rows."""

    def test_property_returns_copy(self) -> None:
        ledger = _make_ledger_with_claim()
        ledger.append_annotations([_anno(key="bound_lower", value=0.6)])
        snapshot = ledger.annotation_rows
        snapshot.append(_anno(key="fake"))
        self.assertEqual(len(ledger.annotation_rows), 1)

    def test_annotations_and_meta_rows_independent(self) -> None:
        """Writing annotations does not affect meta_rows and vice versa."""
        ledger = _make_ledger_with_claim()
        meta_count_before = len(ledger.meta_rows)
        ledger.append_annotations([_anno(key="bound_lower", value=0.6)])
        self.assertEqual(len(ledger.meta_rows), meta_count_before)
        self.assertEqual(len(ledger.annotation_rows), 1)


class TestAnnotationWithAppendAssertionIntegration(unittest.TestCase):
    """Full scenario: PyReason-style assertion with both meta and annotations."""

    def test_pyreason_assertion_dual_write(self) -> None:
        """Simulates PyReason-style annotation + legacy meta projection."""
        ledger = Ledger()
        result = ledger.append_assertion(
            claim=Claim(asrt_id="", pred_id="user:popular", e_ref="alice", rest_terms=[("string", "true")]),
            claim_args=[ClaimArg(asrt_id="", idx=0, val_atom="true", tag="string")],
            meta_rows=[
                MetaRow(asrt_id="", key="confidence", kind="float", value=0.6),
                MetaRow(asrt_id="", key="source", kind="str", value="pyreason_run_001"),
            ],
            annotation_rows=[
                _anno(
                    namespace="pyreason",
                    category="semantic",
                    key="bound_lower",
                    kind="float",
                    value=0.6,
                    origin="observed",
                ),
                _anno(
                    namespace="pyreason",
                    category="semantic",
                    key="bound_upper",
                    kind="float",
                    value=0.9,
                    origin="observed",
                ),
                _anno(
                    namespace="pyreason",
                    category="semantic",
                    key="active_from",
                    kind="int",
                    value=0,
                    origin="observed",
                ),
                _anno(
                    namespace="shared",
                    category="source",
                    key="source",
                    kind="str",
                    value="pyreason_run_001",
                    origin="observed",
                ),
                _anno(
                    namespace="shared",
                    category="derived",
                    key="confidence",
                    kind="float",
                    value=0.6,
                    origin="derived",
                    derivation="pyreason:lower_bound",
                ),
                _anno(
                    namespace="shared",
                    category="derived",
                    key="confidence_source",
                    kind="str",
                    value="pyreason:lower_bound",
                    origin="derived",
                    derivation="pyreason:lower_bound",
                ),
            ],
            asrt_id="pr001",
        )
        self.assertTrue(result.written)

        legacy_conf = ledger.find_meta(asrt_id="pr001", key="confidence")
        self.assertEqual(len(legacy_conf), 1)
        self.assertEqual(legacy_conf[0].value, 0.6)

        semantic = ledger.find_annotations(
            asrt_id="pr001",
            namespace="pyreason",
            category="semantic",
        )
        self.assertEqual(len(semantic), 3)
        bound_keys = {r.key: r.value for r in semantic}
        self.assertEqual(bound_keys["bound_lower"], 0.6)
        self.assertEqual(bound_keys["bound_upper"], 0.9)
        self.assertEqual(bound_keys["active_from"], 0)

        derived = ledger.find_annotations(
            asrt_id="pr001",
            namespace="shared",
            category="derived",
        )
        self.assertEqual(len(derived), 2)
        conf_row = [r for r in derived if r.key == "confidence"][0]
        self.assertEqual(conf_row.value, 0.6)
        self.assertEqual(conf_row.derivation, "pyreason:lower_bound")


if __name__ == "__main__":
    unittest.main()
