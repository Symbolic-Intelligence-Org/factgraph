from __future__ import annotations

import unittest

import factpy_kernel.tests._warnings as test_warnings
from factpy_kernel.sdk import (
    CardinalityError,
    EditorClosedError,
    Entity,
    EntityNotFoundError,
    Field,
    FrozenSnapshotError,
    Identity,
    SDKSchemaError,
    SDKStore,
)


def setUpModule() -> None:
    test_warnings.install_test_warning_filters()


class Country(Entity):
    source_id: str = Identity()
    name: str = Field(cardinality="functional", pred_id="country:name")


class Person(Entity):
    source_id: str = Identity()
    country: str = Field(cardinality="functional", pred_id="person:country")
    name: str = Field(cardinality="multi", pred_id="person:name")
    name_by_lang: str = Field(
        cardinality="functional",
        pred_id="person:name_by_lang",
        dims=[("lang", "string")],
        fact_key=["lang"],
    )


class LivesIn(Entity):
    uid: str = Identity()
    person: Person = Field(cardinality="functional")
    country: Country = Field(cardinality="functional")

    class Meta:
        is_record = True


class SDKReadWriteFacadeV1Tests(unittest.TestCase):
    def _seed(self) -> tuple[SDKStore, dict[str, str]]:
        sdk = SDKStore.from_schema_classes([Person, Country, LivesIn])

        alice_ref = sdk.ref(Person, source_id="u1")
        bob_ref = sdk.ref(Person, source_id="u2")
        de_ref = sdk.ref(Country, source_id="DE")
        cn_ref = sdk.ref(Country, source_id="CN")

        sdk.set(Country.name, de_ref, "Germany")
        sdk.set(Country.name, cn_ref, "China")

        asrt_alice_en = sdk.add(Person.name, alice_ref, "Alice", meta={"source": "seed"})
        sdk.add(Person.name, alice_ref, "爱丽丝", meta={"source": "seed"})
        sdk.retract(asrt_alice_en, meta={"source": "seed_fix"})
        sdk.add(Person.name, alice_ref, "Alicia", meta={"source": "seed_fix"})
        sdk.set(Person.country, alice_ref, "cn", meta={"source": "seed"})
        sdk.set(Person.country, alice_ref, "de", meta={"source": "seed_fix"})
        sdk.set(Person.name_by_lang, alice_ref, "Alice", dims={"lang": "en"}, meta={"source": "seed"})

        sdk.add(Person.name, bob_ref, "Bob", meta={"source": "seed"})
        sdk.set(Person.country, bob_ref, "de", meta={"source": "seed"})

        with sdk.batch(meta={"source": "seed", "trace_id": "seed-record"}) as tx:
            alice = tx.entity(Person, source_id="u1")
            de = tx.entity(Country, source_id="DE")
            rec = tx.entity(LivesIn, uid="li_u1_de")
            rec.person.set(alice)
            rec.country.set(de)
            tx.commit()

        return sdk, {"alice": alice_ref, "bob": bob_ref, "de": de_ref, "cn": cn_ref}

    def test_get_snapshot_read_only_and_assertions(self) -> None:
        sdk, refs = self._seed()

        alice = sdk.get(Person, source_id="u1")
        self.assertIsNotNone(alice)
        assert alice is not None

        self.assertEqual(alice.ref, refs["alice"])
        self.assertEqual(alice.source_id, "u1")
        self.assertEqual(alice.country, "de")
        self.assertEqual(set(alice.name), {"爱丽丝", "Alicia"})

        chosen_country = alice.assertions.country.chosen
        self.assertIsNotNone(chosen_country)
        assert chosen_country is not None
        self.assertEqual(chosen_country.value, "de")
        self.assertTrue(chosen_country.is_active)

        name_history = alice.assertions.name.history
        self.assertEqual(len(name_history), 3)
        self.assertEqual(len([row for row in name_history if row.is_revoked]), 1)
        self.assertEqual(len(alice.assertions.name.active), 2)

        with self.assertRaises(CardinalityError):
            _ = alice.assertions.name.chosen
        with self.assertRaises(CardinalityError):
            _ = alice.assertions.name_by_lang.chosen
        with self.assertRaises(FrozenSnapshotError):
            alice.country = "fr"
        with self.assertRaises(SDKSchemaError):
            sdk.get(Person, source_id="u1", country="de")

        text = repr(alice)
        self.assertIn("EntitySnapshot(", text)
        self.assertIn("entity_type='Person'", text)
        self.assertIn(refs["alice"], text)
        self.assertIn("source_id='u1'", text)
        self.assertIn("country='de'", text)

    def test_find_filters_use_current_view(self) -> None:
        sdk, refs = self._seed()

        self.assertEqual(sdk.find(Person, name="Alice"), [])

        rows = sdk.find(Person, name="Alicia")
        self.assertEqual(len(rows), 1)
        alice = rows[0]
        self.assertEqual(alice.country, "de")

        rows_by_identity = sdk.find(Person, source_id="u1", country="de")
        self.assertEqual(len(rows_by_identity), 1)
        self.assertEqual(rows_by_identity[0].source_id, "u1")

        lives_by_snap = sdk.find(LivesIn, person=alice)
        self.assertEqual(len(lives_by_snap), 1)
        self.assertEqual(lives_by_snap[0].person, alice.ref)
        self.assertEqual(lives_by_snap[0].country, refs["de"])

        lives_by_ref = sdk.find(LivesIn, person=alice.ref)
        self.assertEqual(len(lives_by_ref), 1)
        self.assertEqual(lives_by_ref[0].ref, lives_by_snap[0].ref)

        self.assertEqual(sdk.find(Person, limit=0), [])

        with self.assertRaises(SDKSchemaError):
            sdk.find(Person, name_by_lang="Alice")

    def test_edit_context_manager_auto_commit_and_closed_state(self) -> None:
        sdk, _ = self._seed()

        with sdk.edit(Person, source_id="u1") as user:
            user.country.set("fr", meta={"source": "manual_fix"})
            user.name.add("Ali", meta={"source": "manual_fix"})
            plan = user.preview()
            self.assertGreaterEqual(len(plan.ops), 3)  # ref + set + add
            with self.assertRaises(CardinalityError):
                user.country.add("xx")
            with self.assertRaises(CardinalityError):
                user.name.set("wrong")

        alice = sdk.get(Person, source_id="u1")
        self.assertIsNotNone(alice)
        assert alice is not None
        self.assertEqual(alice.country, "fr")
        self.assertIn("Ali", alice.name)

        with self.assertRaises(EditorClosedError):
            user.preview()

    def test_edit_missing_entity_raises(self) -> None:
        sdk, _ = self._seed()
        with self.assertRaises(EntityNotFoundError):
            sdk.edit(Person, source_id="missing")


if __name__ == "__main__":
    unittest.main()
