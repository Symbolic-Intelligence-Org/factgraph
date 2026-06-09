from __future__ import annotations

import unittest

from factgraph.authoring.schema_dsl_parse import AuthoringSchemaDSLParseError, parse_authoring_schema_dsl_v1
from factgraph.authoring.schemas import compile_authoring_schema_v1
from factgraph.core.schema.schema_ir import schema_digest


def _parse(source: str) -> dict:
    return parse_authoring_schema_dsl_v1(source)


class AuthoringSchemaReprTests(unittest.TestCase):
    def test_member_and_meta_repr_are_authored(self) -> None:
        parsed = _parse(
            """
class User(Entity):
    class Meta:
        repr = "%CLS %user_id"

    user_id: str = Identity(repr="%CLS %ENT %FLD")
    display_name: str = Field(repr="%CLS %ENT %FLD")
"""
        )

        self.assertEqual(parsed["entities"][0]["entity_type"], "User")
        self.assertEqual(parsed["entities"][0]["repr"], "%CLS %user_id")
        self.assertEqual(parsed["entities"][0]["identity_fields"][0]["repr"], "%CLS %ENT %FLD")
        self.assertEqual(parsed["entities"][0]["fields"][0]["repr"], "%CLS %ENT %FLD")

    def test_repr_enters_compiled_ir_without_changing_schema_digest(self) -> None:
        without_repr = _parse(
            """
class User(Entity):
    user_id: str = Identity()
    display_name: str = Field()
"""
        )
        with_repr = _parse(
            """
class User(Entity):
    class Meta:
        repr = "%CLS %user_id"

    user_id: str = Identity(repr="%CLS %ENT %FLD")
    display_name: str = Field(repr="%CLS %ENT %FLD")
"""
        )

        without_ir = compile_authoring_schema_v1(without_repr, generated_at="2026-06-09T00:00:00Z")
        with_ir = compile_authoring_schema_v1(with_repr, generated_at="2026-06-09T00:00:00Z")

        self.assertEqual(schema_digest(without_ir), schema_digest(with_ir))
        self.assertNotIn("repr", str(without_ir))
        self.assertIn("repr", str(with_ir))

    def test_member_repr_rejects_sibling_and_unknown_placeholders(self) -> None:
        for template in ("%display_name", "%UNKNOWN"):
            with self.subTest(template=template):
                with self.assertRaises(AuthoringSchemaDSLParseError):
                    _parse(
                        f'''
class User(Entity):
    user_id: str = Identity(repr="{template}")
    display_name: str = Field()
'''
                    )

    def test_meta_repr_rejects_ent_fld_and_non_identity_placeholders(self) -> None:
        for template in ("%ENT", "%FLD", "%display_name", "%UNKNOWN"):
            with self.subTest(template=template):
                with self.assertRaises(AuthoringSchemaDSLParseError):
                    _parse(
                        f'''
class User(Entity):
    class Meta:
        repr = "{template}"

    user_id: str = Identity()
    display_name: str = Field()
'''
                    )

    def test_repr_extends_form_i_allow_list_without_opening_unknown_kwargs(self) -> None:
        _parse(
            """
class User(Entity):
    user_id: str = Identity(repr="%FLD")
    display_name: str = Field(repr="%FLD")
"""
        )
        with self.assertRaises(AuthoringSchemaDSLParseError):
            _parse(
                """
class User(Entity):
    user_id: str = Identity(label="%FLD")
"""
            )
        with self.assertRaises(AuthoringSchemaDSLParseError):
            _parse(
                """
class User(Entity):
    user_id: str = Identity()
    display_name: str = Field(label="%FLD")
"""
            )

    def test_schema_description_metadata_is_not_accepted(self) -> None:
        for source in (
            """
class User(Entity):
    user_id: str = Identity(description="legacy description")
""",
            """
class User(Entity):
    user_id: str = Identity()
    display_name: str = Field(description="legacy description")
""",
            """
class User(Entity):
    class Meta:
        description = "legacy description"

    user_id: str = Identity()
""",
        ):
            with self.subTest(source=source):
                with self.assertRaises(AuthoringSchemaDSLParseError):
                    _parse(source)

        parsed = _parse(
            """
class User(Entity):
    \"\"\"This docstring is no longer schema metadata.\"\"\"

    user_id: str = Identity()
"""
        )
        self.assertNotIn("description", parsed["entities"][0])


if __name__ == "__main__":
    unittest.main()
