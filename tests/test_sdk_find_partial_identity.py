from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import factgraph.sdk as sdk_module
from factgraph.application import execute_read_request
from factgraph.application.protocol import EntityReadRequest
from factgraph.sdk import Entity, Field, Identity, SDKSchemaError, SDKStore


class User(Entity):
    user_id: str = Identity()
    locale: str = Identity()
    name: str = Field()
    tag: list[str] = Field()


def _seed_store() -> SDKStore:
    sdk = SDKStore([User])
    user_en = sdk.entities.ref(User, user_id="u-1", locale="en")
    user_zh = sdk.entities.ref(User, user_id="u-1", locale="zh")
    user_other = sdk.entities.ref(User, user_id="u-2", locale="en")

    sdk.fields.set(User.name, user_en, "Alice")
    sdk.fields.add(User.tag, user_en, "vip")
    sdk.fields.add(User.tag, user_en, "editor")

    sdk.fields.set(User.name, user_zh, "Alice")
    sdk.fields.add(User.tag, user_zh, "viewer")

    sdk.fields.set(User.name, user_other, "Bob")
    sdk.fields.add(User.tag, user_other, "vip")
    return sdk


class SDKFindPartialIdentityTests(unittest.TestCase):
    def test_partial_identity_filter_returns_all_matching_full_coordinates(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="u-1")

        self.assertEqual({row.identity["locale"] for row in rows}, {"en", "zh"})
        self.assertEqual({row.identity["user_id"] for row in rows}, {"u-1"})
        self.assertTrue(all(row.identity_available for row in rows))

    def test_partial_identity_filter_exposes_full_identity_for_each_snapshot(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="u-1")

        self.assertEqual(
            {tuple(sorted(row.identity.items())) for row in rows},
            {
                (("locale", "en"), ("user_id", "u-1")),
                (("locale", "zh"), ("user_id", "u-1")),
            },
        )
        self.assertTrue(all(row.identity_available for row in rows))

    def test_full_identity_filter_keeps_exact_coordinate_behavior(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="u-1", locale="en")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].identity, {"user_id": "u-1", "locale": "en"})
        self.assertEqual(rows[0].name, "Alice")
        self.assertEqual(set(rows[0].tag), {"vip", "editor"})

    def test_combined_identity_and_field_filters_use_and_semantics(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="u-1", tag="vip")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].identity, {"user_id": "u-1", "locale": "en"})
        self.assertEqual(set(rows[0].tag), {"vip", "editor"})

    def test_partial_identity_no_match_returns_empty_list(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="missing")

        self.assertEqual(rows, [])

    def test_limit_applies_after_partial_identity_filters_match(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User, user_id="u-1", limit=1)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].identity["user_id"], "u-1")
        self.assertIn(rows[0].identity["locale"], {"en", "zh"})

    def test_zero_filter_find_behavior_is_unchanged(self) -> None:
        sdk = _seed_store()

        rows = sdk.entities.where(User)

        self.assertEqual(len(rows), 3)

    def test_unknown_filter_names_remain_schema_errors(self) -> None:
        sdk = _seed_store()

        with self.assertRaises(SDKSchemaError) as ctx:
            sdk.entities.where(User, unknown="x")

        self.assertIn("unknown", str(ctx.exception))
        self.assertIn("User", str(ctx.exception))

    def test_get_still_requires_complete_identity_coordinate(self) -> None:
        sdk = _seed_store()

        with self.assertRaises(SDKSchemaError) as ctx:
            sdk.entities.get(User, user_id="u-1")

        self.assertIn("locale", str(ctx.exception))

    def test_application_protocol_still_rejects_identity_field_filters(self) -> None:
        sdk = _seed_store()

        response = execute_read_request(
            EntityReadRequest(
                mode="find",
                entity_type="User",
                field_filters={"user_id": "u-1"},
            ),
            store=sdk.store,
            index=sdk._application_schema_index,
        )

        self.assertEqual(response.items, ())
        self.assertEqual(len(response.errors), 1)
        self.assertEqual(response.errors[0].code, "IDENTITY_FILTER_NOT_SUPPORTED")

    def test_no_new_public_sdk_names_or_read_helpers_are_added(self) -> None:
        sdk = _seed_store()

        # Pin refreshed: the 63 baseline predated deliberate public additions
        # (RuleStructure/Structure* inspection surface, release-surface sync,
        # MetaExclusion for premise admissibility) and was stale at 74 before
        # MetaExclusion landed. Bumped to 76 for the deliberate
        # PredicatePremiseAllowance addition, then to 77 for the deliberate
        # PredicatePremiseBlock addition (per-predicate premise blocklist,
        # complement of the allowance). Bumped from 77 to 84 for the deliberate
        # RuleProgram, closed-goal, per-call scope, and explanation value objects.
        # Bumped from 84 to 85 for the deliberate compile_derivation_plan
        # addition (the public lowering that lets the capability shells take
        # the application rule form).
        # Bumped from 85 to 86 for the Stage A RevocationInput DTO exposed by
        # the unified Database.commit_changes assertion/revocation entrypoint,
        # then to 88 for the Phase 3 MetaAppendInput/SchemaTransitionInput DTOs.
        # C3 withdrew policy-free SchemaTransitionInput from the SDK namespace,
        # returning the intentional surface to 87 names. Slice 3b Phase 3 adds
        # the typed MetaKeyPolicy authoring DTO, bringing the deliberate total
        # to 88. The subsequent shipped service/query surface had already
        # grown the base to 105. Q18 deliberately adds 46 V1 GoalPlan,
        # Scenario, provider, execution-profile, Run/Explain/replay, and
        # immutable-comparison names (including explicit assertion absence and
        # the non-causal Scenario diff and V1 detached-Explain Policy
        # projection), bringing the explicit total to 152. Q19 deliberately
        # adds ten typed Policy-authoring values (the frozen target, draft,
        # authoring error, and seven typed handle categories), bringing the
        # explicit total to 162. Q20 deliberately adds 38 Product Rule/Policy,
        # Scenario V2, provenance, execution-profile, ProbLog-semantics and
        # Product outcome façade names, bringing the total to 200. Q21 adds
        # eight Product Function asset/builder/occurrence/binding names,
        # bringing the explicit total to 208.
        # Intent unchanged: no ACCIDENTAL name creep.
        # The retained 8d7e6b8f producer deliberately adds 17 candidate/Store
        # witness/RuleProgram witness names to eb36a76d's exact 208-name set.
        # Freeze names, not just a count: replacing a public name with a private
        # helper must fail even when the total remains unchanged.
        expected = json.loads(
            (Path(__file__).parent / "fixtures" / "public_sdk_exports.json").read_text()
        )
        self.assertEqual(len(expected), 225)
        self.assertEqual(len(set(expected)), len(expected))
        self.assertEqual(sorted(sdk_module.__all__), expected)
        self.assertIn("compile_derivation_plan", sdk_module.__all__)
        self.assertIn("RuleProgram", sdk_module.__all__)
        self.assertIn("RuleProgramFact", sdk_module.__all__)
        self.assertIn("EvaluationPremiseScope", sdk_module.__all__)
        self.assertIn("PredicatePremiseAllowance", sdk_module.__all__)
        self.assertIn("PredicatePremiseBlock", sdk_module.__all__)
        self.assertNotIn("ReadPolicy", sdk_module.__all__)
        self.assertIn("SemanticsProfile", sdk_module.__all__)
        self.assertIn("ProbLogConfig", sdk_module.__all__)
        self.assertIn("PyReasonConfig", sdk_module.__all__)
        self.assertIn("ResultFingerprint", sdk_module.__all__)
        self.assertIn("PolicyDraft", sdk_module.__all__)
        self.assertIn("AuthoredPolicyTargetV1", sdk_module.__all__)
        self.assertNotIn("EntityDomainSet", sdk_module.__all__)
        self.assertFalse(hasattr(sdk, "read"))

    def test_export_inventory_rejects_unknown_duplicate_and_same_count_substitution(self) -> None:
        original = list(sdk_module.__all__)
        cases = (
            [*original, "ThirdPartyHelper"],
            [*original, original[0]],
            ["PrivateStoreReader", *original[1:]],
            original[1:],
        )
        for altered in cases:
            with self.subTest(exports=altered[:1], count=len(altered)):
                with patch.object(sdk_module, "__all__", altered), self.assertRaises(AssertionError):
                    self.test_no_new_public_sdk_names_or_read_helpers_are_added()


if __name__ == "__main__":
    unittest.main()
