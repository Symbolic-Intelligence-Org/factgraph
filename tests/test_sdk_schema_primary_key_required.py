from __future__ import annotations

import unittest

from factgraph.sdk import Entity, Field, Identity
from factgraph.sdk.schema import SDKSchemaError


class FormIIdentityDescriptorTests(unittest.TestCase):
    def test_entity_with_no_identity_raises(self) -> None:
        with self.assertRaises(SDKSchemaError) as ctx:

            class _NoIdentity(Entity):
                name: str = Field()

        self.assertIn("at least one Identity field", str(ctx.exception))

    def test_entity_with_single_identity_passes(self) -> None:
        class _SingleIdentity(Entity):
            user_id: str = Identity()
            name: str = Field()

        spec_field_names = [
            row["name"] for row in _SingleIdentity.sdk_entity_spec()["identity_fields"]
        ]
        self.assertEqual(spec_field_names, ["user_id"])

    def test_entity_with_multiple_identities_passes(self) -> None:
        class _CompositeIdentity(Entity):
            user_id: str = Identity()
            locale: str = Identity()
            name: str = Field()

        spec_field_names = [
            row["name"] for row in _CompositeIdentity.sdk_entity_spec()["identity_fields"]
        ]
        self.assertEqual(spec_field_names, ["user_id", "locale"])

    def test_identity_primary_key_kwarg_is_rejected(self) -> None:
        with self.assertRaises(SDKSchemaError) as ctx:
            Identity(primary_key=True)

        self.assertIn("unsupported argument(s): primary_key", str(ctx.exception))
        self.assertIn("Remove primary_key/default/default_factory", str(ctx.exception))

    def test_identity_default_kwargs_are_rejected(self) -> None:
        for kwargs, legacy_name in (
            ({"default": "en"}, "default"),
            ({"default_factory": "uuid4"}, "default_factory"),
        ):
            with self.subTest(legacy_name=legacy_name):
                with self.assertRaises(SDKSchemaError) as ctx:
                    Identity(**kwargs)
                self.assertIn(f"unsupported argument(s): {legacy_name}", str(ctx.exception))

    def test_field_cardinality_kwarg_is_rejected(self) -> None:
        for cardinality in ("single", "multi"):
            with self.subTest(cardinality=cardinality):
                with self.assertRaises(SDKSchemaError) as ctx:
                    Field(cardinality=cardinality)
                self.assertIn("unsupported argument(s): cardinality", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
