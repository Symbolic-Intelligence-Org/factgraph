"""FactPy SDK full example aligned with the current SDK surface.

Coverage:
1. Schema preflight + store initialization
2. Batch writes with entity refs and record-like entities
3. Read paths (`get` / `find`)
4. Edit and ingest flows
5. Rule queries + `RuleRef`
6. Derivation evaluation + accept
7. Provenance validation
8. A few common error shapes
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from factpy_kernel.sdk import (
    CardinalityError,
    Derivation,
    EditorClosedError,
    Entity,
    EntityNotFoundError,
    Field,
    FrozenSnapshotError,
    Identity,
    Rule,
    RuleRef,
    SDKDSLError,
    SDKSchemaError,
    SDKStore,
    schema_preflight_from_classes,
    vars,
)


class Country(Entity):
    country_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="single")
    official_name: str = Field(cardinality="single")


class Language(Entity):
    language_id: str = Identity(primary_key=True)
    label: str = Field(cardinality="single")


class User(Entity):
    user_id: str = Identity(primary_key=True)
    name: str = Field(cardinality="multi")
    country: Country = Field(cardinality="single")
    age: int = Field(cardinality="single")
    score: float = Field(cardinality="single")
    popular: str = Field(cardinality="single")


class HasLanguage(Entity):
    link_id: str = Identity(primary_key=True, default_factory="uuid4")
    country: Country = Field(cardinality="single")
    language: Language = Field(cardinality="single")


class LivesIn(Entity):
    record_id: str = Identity(primary_key=True, default_factory="uuid4")
    user: User = Field(cardinality="single")
    country: Country = Field(cardinality="single")
    since: int = Field(cardinality="single")


class Speaks(Entity):
    record_id: str = Identity(primary_key=True, default_factory="uuid4")
    user: User = Field(cardinality="single")
    language: Language = Field(cardinality="single")


SCHEMA_CLASSES = [Country, Language, User, HasLanguage, LivesIn, Speaks]


def main() -> None:
    print("=== 1. Schema Preflight + Store Initialization ===")
    preflight = schema_preflight_from_classes(SCHEMA_CLASSES)
    assert preflight["ok"], preflight
    print("[preflight] ok =", preflight["ok"])
    print("[preflight] predicates =", preflight["summary"]["predicate_count"])

    sdk = SDKStore(SCHEMA_CLASSES)
    print("[init] store ready")

    print("\n=== 2. Batch Writes ===")
    with sdk.batch(meta={"source": "demo_seed", "trace_id": "seed-001"}) as tx:
        france = tx.entity(Country, country_id="FR")
        france.name.set("France")
        france.official_name.set("French Republic")

        germany = tx.entity(Country, country_id="DE")
        germany.name.set("Germany")
        germany.official_name.set("Federal Republic of Germany")

        french = tx.entity(Language, language_id="fr")
        french.label.set("French")

        german = tx.entity(Language, language_id="de")
        german.label.set("German")

        alice = tx.entity(User, user_id="u-alice")
        alice.name.add("Alice")
        alice.country.set(france)
        alice.age.set(30)
        alice.score.set(9.5)

        bob = tx.entity(User, user_id="u-bob")
        bob.name.add("Bob")
        bob.country.set(germany)
        bob.age.set(25)
        bob.score.set(8.0)

        lives_alice = tx.entity(LivesIn)
        lives_alice.user.set(alice)
        lives_alice.country.set(france)
        lives_alice.since.set(2020)

        lives_bob = tx.entity(LivesIn)
        lives_bob.user.set(bob)
        lives_bob.country.set(germany)
        lives_bob.since.set(2018)

        fr_lang = tx.entity(HasLanguage)
        fr_lang.country.set(france)
        fr_lang.language.set(french)

        de_lang = tx.entity(HasLanguage)
        de_lang.country.set(germany)
        de_lang.language.set(german)

        tx.commit()

    print("[batch] ledger assertions =", len(sdk.ledger.claims))

    print("\n=== 3. Read Paths ===")
    alice_snap = sdk.get(User, user_id="u-alice")
    assert alice_snap is not None
    print("[get] Alice ref =", alice_snap.ref)
    print("[get] Alice active names =", [row.value for row in alice_snap.assertions.name.active])
    print("[get] Alice age =", alice_snap.age)

    age_30 = sdk.find(User, age=30)
    print("[find] age=30 count =", len(age_30))
    print("[find] all users =", len(sdk.find(User)))

    print("\n=== 4. Edit + Ingest ===")
    with sdk.edit(User, user_id="u-alice") as editor:
        editor.name.add("Alicia")
        editor.age.set(31)

    updated_alice = sdk.get(User, user_id="u-alice")
    assert updated_alice is not None
    print("[edit] Alice names =", [row.value for row in updated_alice.assertions.name.active])
    print("[edit] Alice age =", updated_alice.age)

    alice_ref = sdk.ref(User, user_id="u-alice")
    france_ref = sdk.ref(Country, country_id="FR")
    ingest_result = sdk.ingest(
        [
            {"kind": "add", "field": User.name, "e_ref": alice_ref, "value": "Ali"},
            {"kind": "set", "field": User.country, "e_ref": alice_ref, "value": france_ref},
        ],
        meta={"source": "csv_import", "trace_id": "import-001"},
    )
    print("[ingest] written =", ingest_result.written_assertion_ids)
    print("[ingest] skipped =", ingest_result.skipped_count)

    print("\n=== 5. Rule Queries ===")
    with vars("li", "u", "c") as (li, u, c):
        lives_rule = Rule(
            id="q.lives_in",
            version="1.0.0",
            select=[u, c],
            where=[
                LivesIn(li),
                li.user == u,
                li.country == c,
            ],
            expose=True,
        )

    rows = sdk.run(lives_rule, row_format="dict")
    print("[rule] lives_in rows =", rows)

    with vars("u", "c") as (u, c):
        ref_rule = Rule(
            id="q.lives_in_via_ref",
            version="1.0.0",
            select=[u, c],
            where=[RuleRef(lives_rule)(u, c)],
        )
    print("[rule-ref] rows =", sdk.run(ref_rule, row_format="dict"))

    print("\n=== 6. Derivation Evaluate + Accept ===")
    with vars("u", "age", "flag") as (u, age, flag):
        popular_drv = Derivation(
            id="drv.popular",
            version="1.0.0",
            where=[
                User(u),
                u.age == age,
                age >= 30,
                flag == "yes",
            ],
            target="user:popular",
            head_vars=[u, flag],
        )

    candidates = sdk.evaluate(popular_drv, mode="native")
    print("[derive] candidate sets =", len(candidates))

    if candidates:
        report = sdk.validate_provenance(candidates[0], standard="derivation_v1")
        print("[derive] provenance ok =", report.ok)
        accept_result = sdk.accept(candidates[0], approved_by="demo")
        print("[derive] accepted =", accept_result.accepted_count)

    derived_alice = sdk.get(User, user_id="u-alice")
    assert derived_alice is not None
    print("[derive] Alice popular =", derived_alice.popular)

    print("\n=== 7. Provenance Validation ===")
    flat_report = sdk.validate_provenance(
        {
            "derived_rule_id": "drv.popular",
            "derived_rule_version": "1.0.0",
            "run_id": "run-demo-001",
            "support_kind": "python_in_memory",
            "support_digest": "sha256:" + ("a" * 64),
        },
        standard="derivation_v1",
    )
    print("[provenance] flat dict ok =", flat_report.ok)

    invalid_report = sdk.validate_provenance({"derived_rule_id": "drv.missing"}, standard="derivation_v1")
    print("[provenance] invalid errors =", [item["code"] for item in invalid_report.errors])

    print("\n=== 8. Common Error Shapes ===")
    frozen = sdk.get(User, user_id="u-alice")
    assert frozen is not None
    try:
        frozen.age = 99  # type: ignore[misc]
    except FrozenSnapshotError as exc:
        print("[error] FrozenSnapshotError:", exc)

    try:
        with sdk.edit(User, user_id="u-alice") as editor:
            editor.name.set("wrong")
    except CardinalityError as exc:
        print("[error] CardinalityError:", exc)

    editor = sdk.edit(User, user_id="u-alice")
    editor.__enter__()
    editor.commit()
    try:
        editor.age.set(99)
    except EditorClosedError as exc:
        print("[error] EditorClosedError:", exc)

    try:
        sdk.edit(User, user_id="missing-user")
    except EntityNotFoundError as exc:
        print("[error] EntityNotFoundError:", exc)

    try:
        sdk.get(User, age=30)  # type: ignore[call-arg]
    except SDKSchemaError as exc:
        print("[error] SDKSchemaError:", exc)

    try:
        with vars("u") as (u,):
            Rule(id="bad_rule", version="1.0.0", select=[u], where=[])
    except SDKDSLError as exc:
        print("[error] SDKDSLError:", exc)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
