from __future__ import annotations

import json
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import factpy_kernel.tests._warnings as test_warnings
from factpy_kernel.adapters.souffle.package import ExportOptions
from factpy_kernel.core.store.ledger import Ledger
from factpy_kernel.sdk import (
    Derivation,
    Entity,
    Field,
    Identity,
    INVALID_ROW_FORMAT,
    Not,
    Pred,
    QUERY_INVALID_ROW_FORMAT,
    Rule,
    RuleRef,
    SDKStore,
    SDKStoreError,
    vars,
)


def setUpModule() -> None:
    test_warnings.install_test_warning_filters()


class Company(Entity):
    source_id: str = Identity()
    sector: str = Field(cardinality="functional")


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
    blacklist: str = Field(cardinality="multi", pred_id="person:blacklist")
    name_by_lang: str = Field(
        cardinality="functional",
        dims=[("lang", "string")],
        fact_key=["lang"],
        pred_id="person:name_by_lang",
    )
    tag: str = Field(cardinality="multi", pred_id="person:tag")
    works_at: Company = Field(cardinality="multi", pred_id="person:works_at")


class Language(Entity):
    source_system: str = Identity(default="ISO639")
    code: str = Identity()
    name: str = Field(cardinality="multi", pred_id="language:name")


class PersonAge(Entity):
    source_id: str = Identity()
    birth_year: int = Field(cardinality="functional", pred_id="person:birth_year")


class LivesIn(Entity):
    uid: str = Identity()
    person: Person = Field(cardinality="functional")
    country: str = Field(cardinality="functional")


class SDKStoreV1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.sdk = SDKStore.from_schema_classes([Person, Company, LivesIn])
        self.p_ref = self.sdk.ref(Person, source_id="u1")
        self.c_ref = self.sdk.ref(Company, source_id="c1")

    def test_ref_set_add_retract_flow(self) -> None:
        a1 = self.sdk.set(
            Person.country,
            self.p_ref,
            "de",
            meta={"source": "sdk", "source_loc": "test", "trace_id": "t1"},
        )
        a2 = self.sdk.add(
            Person.works_at,
            self.p_ref,
            self.c_ref,
            meta={"source": "sdk", "source_loc": "test", "trace_id": "t2"},
        )
        self.assertNotEqual(a1, a2)

        fact = self.sdk.explain_fact("person:country", self.p_ref, "de")
        self.assertEqual(fact["pred_id"], "person:country")
        self.assertEqual(fact["chosen_asrt_id"], a1)

        revoker = self.sdk.retract(a2, meta={"source": "sdk", "source_loc": "test", "trace_id": "t3"})
        self.assertIsInstance(revoker, str)
        self.assertTrue(self.sdk.ledger.has_active_revocation(a2))

    def test_dims_are_encoded_from_named_or_positional_inputs(self) -> None:
        a_named = self.sdk.set(Person.name_by_lang, self.p_ref, "Alice", dims={"lang": "en"})
        a_pos = self.sdk.set(
            Person.name_by_lang,
            self.p_ref,
            "Alicia",
            dims=["es"],
            meta={"source": "sdk", "source_loc": "test", "trace_id": "t4"},
        )
        claims = {c.asrt_id: c for c in self.sdk.ledger.find_claims(pred_id="person:name_by_lang", e_ref=self.p_ref)}
        self.assertEqual(claims[a_named].rest_terms, [("string", "en"), ("string", "Alice")])
        self.assertEqual(claims[a_pos].rest_terms, [("string", "es"), ("string", "Alicia")])

    def test_dims_validation_rejects_missing_or_extra(self) -> None:
        with self.assertRaises(SDKStoreError):
            self.sdk.set(Person.name_by_lang, self.p_ref, "Alice")
        with self.assertRaises(SDKStoreError):
            self.sdk.set(Person.name_by_lang, self.p_ref, "Alice", dims={"lang": "en", "x": "y"})

    def test_export_and_run_passthrough(self) -> None:
        self.sdk.set(Person.country, self.p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t5"})
        with tempfile.TemporaryDirectory() as tmp:
            pkg_dir = Path(tmp) / "pkg"
            manifest_path = self.sdk.export_package(pkg_dir, ExportOptions(package_kind="inference"))
            self.assertTrue(manifest_path.exists())
            run_manifest_path = self.sdk.run_package(pkg_dir, entrypoints=["person:country"], engine="noop")
            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(run_manifest["engine_mode"], "noop")

    def test_ref_uses_identity_default_values(self) -> None:
        sdk = SDKStore.from_schema_classes([Language])
        ref = sdk.ref(Language, code="de")
        self.assertIn("idref_v1:", ref)

    def test_from_schema_classes_with_ledger_path_persists_schema_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "ledger.db")
            with patch("factpy_kernel.authoring.schema_compile._utc_now_iso_z", return_value="2026-01-01T00:00:00Z"):
                sdk_1 = SDKStore.from_schema_classes([Person, Company], ledger_path=ledger_path)
            stored_digest = sdk_1.ledger.get_ledger_meta("schema_digest")
            self.assertIsInstance(stored_digest, str)
            self.assertTrue(stored_digest.startswith("sha256:"))

            with patch("factpy_kernel.authoring.schema_compile._utc_now_iso_z", return_value="2026-01-01T00:00:00Z"):
                sdk_2 = SDKStore.from_schema_classes([Person, Company], ledger_path=ledger_path)
            self.assertEqual(sdk_2.ledger.get_ledger_meta("schema_digest"), stored_digest)

    def test_from_schema_classes_with_ledger_path_rejects_schema_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "ledger.db")
            SDKStore.from_schema_classes([Person, Company], ledger_path=ledger_path)

            with self.assertRaises(SDKStoreError) as ctx:
                SDKStore.from_schema_classes([Person], ledger_path=ledger_path)
            self.assertIn("schema mismatch", str(ctx.exception))

    def test_from_schema_classes_rejects_ledger_and_ledger_path_together(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger_path = str(Path(tmp) / "ledger.db")
            with self.assertRaises(SDKStoreError) as ctx:
                SDKStore.from_schema_classes([Person], ledger=Ledger(), ledger_path=ledger_path)
            self.assertIn("provide either ledger or ledger_path", str(ctx.exception))

    def test_run_accept_facades_align_with_blueprint_style(self) -> None:
        self.sdk.set(Person.country, self.p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t6"})
        rows = self.sdk.run(
            {
                "rule_id": "q_country_rows",
                "version": "1.0.0",
                "select": ["p", "c"],
                "where": [("pred", "person:country", ["$p", "$c"])],
            }
        )
        self.assertEqual(rows, [{"p": self.p_ref, "c": "de"}])

        candidate = self.sdk.store.evaluate_dummy(
            derivation_id="drv.copy_country",
            version="1.0.0",
            target="person:country",
            e_ref=self.p_ref,
            rest_terms=[("string", "fr")],
            dims_terms=[],
        )
        res = self.sdk.accept(candidate, meta_overrides={"approved_by": "alice"})
        self.assertEqual(res.accepted_count, 1)
        asrt_id = res.written_assertions[0]["asrt_id"]
        approved_meta = self.sdk.ledger.find_meta(asrt_id=asrt_id, key="approved_by", kind="str")
        self.assertEqual([m.value for m in approved_meta], ["alice"])

    def test_run_and_evaluate_accept_support_sdk_objects(self) -> None:
        self.sdk.set(Person.country, self.p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7"})
        with vars("p", "c") as (p, c):
            rule = Rule(
                id="q_country_rows_obj",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
            drv = Derivation(
                id="drv.country_copy_obj",
                version="1.0.0",
                target="person:country",
                head_vars=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        rows = self.sdk.run(rule)
        self.assertEqual(rows, [{"p": self.p_ref, "c": "de"}])
        cands = self.sdk.evaluate(drv)
        self.assertEqual(len(cands), 1)
        res = self.sdk.accept(cands[0])
        self.assertEqual(res.run_id, cands[0].run_id)

    def test_evaluate_multi_head_flattens_in_head_order_with_shared_run_id(self) -> None:
        p2_ref = self.sdk.ref(Person, source_id="u2")
        self.sdk.set(Person.country, self.p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7m1"})
        self.sdk.set(Person.country, p2_ref, "fr", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7m2"})
        with vars("p", "c") as (p, c):
            drv = Derivation(
                id="drv.multi_head_tag_blacklist",
                version="1.0.0",
                head=[
                    Person.tag(person=p, tag=c),
                    Person.blacklist(person=p, blacklist=c),
                ],
                where=[("pred", "person:country", ["$p", "$c"])],
            )

        cands = self.sdk.evaluate(drv)
        self.assertEqual(len(cands), 4)
        self.assertEqual([cand.target for cand in cands[:2]], ["person:tag", "person:tag"])
        self.assertEqual([cand.target for cand in cands[2:]], ["person:blacklist", "person:blacklist"])

        run_ids = {cand.run_id for cand in cands}
        self.assertEqual(len(run_ids), 1)
        run_id = next(iter(run_ids))
        self.assertTrue(run_id.startswith("drv.multi_head_tag_blacklist:"))

        rows = self.sdk.accept_many(cands, mode="atomic")
        self.assertEqual({row["state"] for row in rows}, {"ACCEPTED"})
        self.assertEqual(len(self.sdk.ledger.find_claims(pred_id="person:tag")), 2)
        self.assertEqual(len(self.sdk.ledger.find_claims(pred_id="person:blacklist")), 2)

    def test_run_row_format_default_returns_dict_without_warning(self) -> None:
        self.sdk.set(Person.country, self.p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7a"})
        with vars("p", "c") as (p, c):
            rule = Rule(
                id="q_country_default_tuple",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        with warnings.catch_warnings(record=True) as rec:
            warnings.simplefilter("always", DeprecationWarning)
            rows = self.sdk.run(rule)
        self.assertEqual(rows, [{"p": self.p_ref, "c": "de"}])
        self.assertEqual([w for w in rec if issubclass(w.category, DeprecationWarning)], [])

    def test_run_row_format_tuple_explicit_emits_deprecation_warning(self) -> None:
        self.sdk.set(Person.country, self.p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7a2"})
        with vars("p", "c") as (p, c):
            rule = Rule(
                id="q_country_tuple_explicit",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        with warnings.catch_warnings(record=True) as rec:
            warnings.simplefilter("always", DeprecationWarning)
            rows = self.sdk.run(rule, row_format="tuple")
        self.assertEqual(rows, [(self.p_ref, "de")])
        dep_warnings = [w for w in rec if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(len(dep_warnings), 1)
        self.assertIn("row_format='dict'", str(dep_warnings[0].message))
        self.assertIn("FACTPY_ROW_FORMAT=dict", str(dep_warnings[0].message))

    def test_run_row_format_dict_from_call_site_has_highest_priority(self) -> None:
        with patch.dict("os.environ", {"FACTPY_ROW_FORMAT": "tuple"}):
            sdk = SDKStore.from_schema_classes([Person, Company], default_row_format="tuple")
        p_ref = sdk.ref(Person, source_id="u1")
        sdk.set(Person.country, p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7b"})
        with vars("p", "c") as (p, c):
            rule = Rule(
                id="q_country_dict_callsite",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        with warnings.catch_warnings(record=True) as rec:
            warnings.simplefilter("always", DeprecationWarning)
            rows = sdk.run(rule, row_format="dict")
        self.assertEqual(rows, [{"p": p_ref, "c": "de"}])
        self.assertEqual([w for w in rec if issubclass(w.category, DeprecationWarning)], [])

    def test_run_row_format_store_default_overrides_env(self) -> None:
        with patch.dict("os.environ", {"FACTPY_ROW_FORMAT": "tuple"}):
            sdk = SDKStore.from_schema_classes([Person, Company], default_row_format="dict")
        p_ref = sdk.ref(Person, source_id="u1")
        sdk.set(Person.country, p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7c"})
        with vars("p", "c") as (p, c):
            rule = Rule(
                id="q_country_dict_store",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        with warnings.catch_warnings(record=True) as rec:
            warnings.simplefilter("always", DeprecationWarning)
            rows = sdk.run(rule)
        self.assertEqual(rows, [{"p": p_ref, "c": "de"}])
        self.assertEqual([w for w in rec if issubclass(w.category, DeprecationWarning)], [])

    def test_run_row_format_store_default_tuple_emits_deprecation_warning(self) -> None:
        sdk = SDKStore.from_schema_classes([Person, Company], default_row_format="tuple")
        p_ref = sdk.ref(Person, source_id="u1")
        sdk.set(Person.country, p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7c2"})
        with vars("p", "c") as (p, c):
            rule = Rule(
                id="q_country_store_tuple",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        with warnings.catch_warnings(record=True) as rec:
            warnings.simplefilter("always", DeprecationWarning)
            rows = sdk.run(rule)
        self.assertEqual(rows, [(p_ref, "de")])
        dep_warnings = [w for w in rec if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(len(dep_warnings), 1)
        self.assertIn("source=store_default", str(dep_warnings[0].message))

    def test_run_row_format_env_used_when_call_and_store_default_absent(self) -> None:
        with patch.dict("os.environ", {"FACTPY_ROW_FORMAT": "dict"}):
            sdk = SDKStore.from_schema_classes([Person, Company])
        p_ref = sdk.ref(Person, source_id="u1")
        sdk.set(Person.country, p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7d"})
        with vars("p", "c") as (p, c):
            rule = Rule(
                id="q_country_dict_env",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        with warnings.catch_warnings(record=True) as rec:
            warnings.simplefilter("always", DeprecationWarning)
            rows = sdk.run(rule)
        self.assertEqual(rows, [{"p": p_ref, "c": "de"}])
        self.assertEqual([w for w in rec if issubclass(w.category, DeprecationWarning)], [])

    def test_run_row_format_env_tuple_emits_deprecation_warning(self) -> None:
        with patch.dict("os.environ", {"FACTPY_ROW_FORMAT": "tuple"}):
            sdk = SDKStore.from_schema_classes([Person, Company])
        p_ref = sdk.ref(Person, source_id="u1")
        sdk.set(Person.country, p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7d2"})
        with vars("p", "c") as (p, c):
            rule = Rule(
                id="q_country_tuple_env",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        with warnings.catch_warnings(record=True) as rec:
            warnings.simplefilter("always", DeprecationWarning)
            rows = sdk.run(rule)
        self.assertEqual(rows, [(p_ref, "de")])
        dep_warnings = [w for w in rec if issubclass(w.category, DeprecationWarning)]
        self.assertEqual(len(dep_warnings), 1)
        self.assertIn("source=env_var", str(dep_warnings[0].message))

    def test_run_row_format_invalid_call_site_value_raises(self) -> None:
        self.sdk.set(Person.country, self.p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7e"})
        with vars("p", "c") as (p, c):
            rule = Rule(
                id="q_country_invalid_row_format",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        with self.assertRaises(SDKStoreError) as ctx:
            self.sdk.run(rule, row_format="list")
        self.assertEqual(ctx.exception.code, INVALID_ROW_FORMAT)

    def test_run_row_format_invalid_env_value_raises(self) -> None:
        with patch.dict("os.environ", {"FACTPY_ROW_FORMAT": "list"}):
            sdk = SDKStore.from_schema_classes([Person, Company])
        p_ref = sdk.ref(Person, source_id="u1")
        sdk.set(Person.country, p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t7f"})
        with vars("p", "c") as (p, c):
            rule = Rule(
                id="q_country_invalid_env_row_format",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        with self.assertRaises(SDKStoreError) as ctx:
            sdk.run(rule)
        self.assertEqual(ctx.exception.code, INVALID_ROW_FORMAT)

    def test_run_rejects_derivation_object_with_evaluate_hint(self) -> None:
        with vars("p", "c") as (p, c):
            drv = Derivation(
                id="drv.country_copy_run_reject",
                version="1.0.0",
                target="person:country",
                head_vars=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
            )
        with self.assertRaises(SDKStoreError) as ctx:
            self.sdk.run(drv)
        self.assertEqual(ctx.exception.code, QUERY_INVALID_ROW_FORMAT)
        self.assertIn("use sdk.evaluate()", str(ctx.exception))

    def test_run_supports_rule_ref_with_rule_object_dependencies(self) -> None:
        self.sdk.set(Person.country, self.p_ref, "de", meta={"source": "sdk", "source_loc": "test", "trace_id": "t8"})
        with vars("p", "c", "x") as (p, c, x):
            base = Rule(
                id="q_country_rows_base",
                version="1.0.0",
                select=[p, c],
                where=[("pred", "person:country", ["$p", "$c"])],
                expose=True,
            )
            top = Rule(
                id="q_country_rows_ref",
                version="1.0.0",
                select=[p],
                where=[
                    RuleRef(base)(p, c),
                    x == "xx",
                    c != x,
                ],
            )
        rows = self.sdk.run(top)
        self.assertEqual(rows, [{"p": self.p_ref}])

    def test_run_supports_record_path_sugar_and_not_pred(self) -> None:
        p2_ref = self.sdk.ref(Person, source_id="u2")
        self.sdk.add(Person.blacklist, p2_ref, "x", meta={"source": "sdk", "source_loc": "test", "trace_id": "t8b"})

        with self.sdk.batch(meta={"source": "sdk", "trace_id": "t8c"}) as tx:
            p1 = tx.entity(Person, source_id="u1")
            p2 = tx.entity(Person, source_id="u2")
            li1 = tx.entity(LivesIn, uid="li_u1_de")
            li1.person.set(p1)
            li1.country.set("de")
            li2 = tx.entity(LivesIn, uid="li_u2_fr")
            li2.person.set(p2)
            li2.country.set("fr")
            tx.commit()

        with vars("li", "p", "c") as (li, p, c):
            top = Rule(
                id="q_country_rows_filtered",
                version="1.0.0",
                select=[p, c],
                where=[
                    LivesIn(li),
                    li.person == p,
                    li.country == c,
                    Not([Pred("person:blacklist", p, "x")]),
                ],
            )

        rows = self.sdk.run(top)
        self.assertEqual(rows, [{"p": self.p_ref, "c": "de"}])

    def test_run_supports_linear_arithmetic_builtins_from_sdk_dsl(self) -> None:
        sdk = SDKStore.from_schema_classes([PersonAge])
        p1 = sdk.ref(PersonAge, source_id="u1")
        p2 = sdk.ref(PersonAge, source_id="u2")
        sdk.set(
            PersonAge.birth_year,
            p1,
            2000,
            meta={"source": "sdk", "source_loc": "test", "trace_id": "t9"},
        )
        sdk.set(
            PersonAge.birth_year,
            p2,
            2012,
            meta={"source": "sdk", "source_loc": "test", "trace_id": "t10"},
        )

        with vars("p", "by", "age") as (p, by, age):
            rule = Rule(
                id="q_adults",
                version="1.0.0",
                select=[p, age],
                where=[
                    ("pred", "person:birth_year", ["$p", "$by"]),
                    age == (2026 - by),
                    age >= 18,
                ],
            )
        rows = sdk.run(rule)
        self.assertEqual(rows, [{"p": p1, "age": 26}])


if __name__ == "__main__":
    unittest.main()
