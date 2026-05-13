from __future__ import annotations

import unittest

from factpy.sdk import Entity, Field, Identity
from factpy.sdk.schema import SDKSchemaError


class IdentityPrimaryKeyRequiredTests(unittest.TestCase):
    def test_entity_with_no_identity_raises(self) -> None:
        with self.assertRaises(SDKSchemaError) as ctx:

            class _NoIdentity(Entity):
                name: str = Field(cardinality="single")

        self.assertIn("at least one Identity field", str(ctx.exception))

    def test_entity_with_only_secondary_identity_raises(self) -> None:
        with self.assertRaises(SDKSchemaError) as ctx:

            class _OnlySecondary(Entity):
                locale: str = Identity()
                name: str = Field(cardinality="single")

        self.assertIn("Identity(primary_key=True)", str(ctx.exception))

    def test_entity_with_multiple_secondary_only_raises(self) -> None:
        with self.assertRaises(SDKSchemaError) as ctx:

            class _MultiSecondaryOnly(Entity):
                locale: str = Identity()
                region: str = Identity()
                name: str = Field(cardinality="single")

        self.assertIn("Identity(primary_key=True)", str(ctx.exception))

    def test_entity_with_primary_and_secondary_passes(self) -> None:
        class _PrimaryAndSecondary(Entity):
            user_id: str = Identity(primary_key=True)
            locale: str = Identity()
            name: str = Field(cardinality="single")

        spec_field_names = [
            row["name"] for row in _PrimaryAndSecondary.sdk_entity_spec()["identity_fields"]
        ]
        self.assertEqual(spec_field_names, ["user_id", "locale"])

    def test_entity_with_only_primary_passes(self) -> None:
        class _OnlyPrimary(Entity):
            user_id: str = Identity(primary_key=True)
            name: str = Field(cardinality="single")

        spec = _OnlyPrimary.sdk_entity_spec()
        primary_flags = [row.get("primary_key", False) for row in spec["identity_fields"]]
        self.assertEqual(primary_flags, [True])

    def test_entity_with_multiple_primary_passes(self) -> None:
        class _Composite(Entity):
            tenant: str = Identity(primary_key=True)
            user_id: str = Identity(primary_key=True)
            name: str = Field(cardinality="single")

        spec = _Composite.sdk_entity_spec()
        primary_flags = [row.get("primary_key", False) for row in spec["identity_fields"]]
        self.assertEqual(primary_flags, [True, True])


if __name__ == "__main__":
    unittest.main()
