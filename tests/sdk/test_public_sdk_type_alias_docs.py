"""The declaration-doc exception is bounded to one exact, unchanged Literal."""

from __future__ import annotations

import inspect
import unittest
from typing import Literal
from unittest.mock import patch

from factgraph import sdk
from factgraph.application.protocol import semantic_candidates
from tests.sdk import test_public_sdk_docstrings as doc_guards


class CandidateAliasDocumentationGuardTests(unittest.TestCase):
    def _original_guard(self) -> None:
        case = doc_guards.PublicSDKDocstringTests(
            "test_every_public_export_and_exported_class_member_has_a_docstring"
        )
        case.test_every_public_export_and_exported_class_member_has_a_docstring()

    def test_runtime_literal_object_is_not_modified(self) -> None:
        literal = Literal["exact", "unicode_casefold_v1"]
        before = literal.__doc__
        self._original_guard()
        self.assertIs(sdk.SemanticCandidateMatchMode, literal)
        self.assertEqual(literal.__doc__, before)

    def test_replaced_export_is_not_exempt(self) -> None:
        with (
            patch.object(sdk, "SemanticCandidateMatchMode", Literal["exact"]),
            self.assertRaises(AssertionError),
        ):
            self._original_guard()

    def test_changed_declaration_is_not_exempt(self) -> None:
        source = inspect.getsource(semantic_candidates).replace(
            'Literal["exact", "unicode_casefold_v1"]', 'Literal["exact"]', 1
        )
        with self.assertRaises(AssertionError):
            doc_guards._assert_candidate_match_mode_documented(self, sdk.SemanticCandidateMatchMode, source)

    def test_missing_adjacent_documentation_is_rejected(self) -> None:
        source = 'SemanticCandidateMatchMode: TypeAlias = Literal["exact", "unicode_casefold_v1"]\n'
        with self.assertRaises(AssertionError):
            doc_guards._assert_candidate_match_mode_documented(self, sdk.SemanticCandidateMatchMode, source)

    def test_unknown_literal_export_has_no_documentation_exemption(self) -> None:
        with (
            patch.object(sdk, "UnexpectedMode", Literal["unexpected"], create=True),
            patch.object(sdk, "__all__", [*sdk.__all__, "UnexpectedMode"]),
            self.assertRaisesRegex(AssertionError, "UnexpectedMode is missing a docstring"),
        ):
            self._original_guard()

    def test_an_ordinary_export_still_requires_a_docstring(self) -> None:
        with (
            patch.object(sdk.SemanticValueCandidateRequestV1, "__doc__", None),
            self.assertRaisesRegex(AssertionError, "SemanticValueCandidateRequestV1 is missing"),
        ):
            self._original_guard()
