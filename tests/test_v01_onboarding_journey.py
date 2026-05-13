"""
v0.1 user journey probe (D7 acceptance driver).

kernel-only + native-only + test-backed pseudo demo. NOT in release-surface
allowlist; only used as hardening acceptance gate.

Covers: schema with primary + secondary identity -> SDKStore ->
sdk.ref + sdk.set/add -> sdk.get + sdk.run(Query) -> native derivation +
accept -> sdk.export_package(audit).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from factpy.adapters.souffle.package import ExportOptions
from factpy.sdk import Inference, Entity, Field, Identity, Query, SDKStore, vars as sdk_vars


class Country(Entity):
    code: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity(default="zh")
    name: str = Field(cardinality="single")
    tag: str = Field(cardinality="multi")
    home: Country = Field(cardinality="single")


class V01OnboardingJourneyTests(unittest.TestCase):
    def test_full_journey_set_get_query_derive_export(self) -> None:
        sdk = SDKStore([Country, User])

        de = sdk.ref(Country, code="DE")
        alice = sdk.ref(User, user_id="u1", locale="zh")

        sdk.set(Country.name, de, "Germany")
        sdk.set(User.name, alice, "Alice")
        sdk.set(User.home, alice, de)
        sdk.add(User.tag, alice, "admin")
        sdk.add(User.tag, alice, "vip")

        snap = sdk.get(User, user_id="u1", locale="zh")
        self.assertIsNotNone(snap)
        assert snap is not None
        self.assertEqual(snap.name, "Alice")
        self.assertEqual(set(snap.tag), {"admin", "vip"})
        self.assertEqual(snap.home, de)

        with sdk_vars("u", "name") as (u, name):
            q = Query(
                head=[User(u), User.name(value=name)],
                where=[User(u), u.name == name],
            )
        rows = sdk.run(q)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Alice")

        with sdk_vars("u", "loc", "derived") as (u, loc, derived):
            derivation = Inference(
                id="journey.derived_tag",
                version="1.0.0",
                where=[User(u), u.locale == loc, u.tag == "admin", derived == "audited"],
                head=User.tag(locale=loc, tag=derived),
            )

        candidates = sdk.evaluate(derivation, engine="native")
        self.assertGreaterEqual(len(candidates), 1)
        sdk.accept(candidates[0], approved_by="journey", note="accept derived audit tag")

        with sdk_vars("u") as (u,):
            derived_query = Query(
                head=User(u),
                where=[User(u), u.tag == "audited"],
            )
        derived_rows = sdk.run(derived_query)
        self.assertEqual(len(derived_rows), 1)

        with tempfile.TemporaryDirectory() as tmp:
            sdk.export_package(tmp, ExportOptions(package_kind="audit"))
            self.assertTrue((Path(tmp) / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
