"""Red + guard baseline for post-Track-3 Case identity / rule inspect."""

from __future__ import annotations

import unittest

from factgraph.authoring.rule_compile import AuthoringRuleCompileError, compile_authoring_rule_v1
from factgraph.sdk import Case, EmitSpec, Inference, Pred, SDKStore
from factgraph.sdk import vars as sdk_vars
from factgraph.sdk.dsl import Rule
from factgraph.sdk.dsl.errors import SDKDSLError
from factgraph.sdk.schema import Entity, Field, Identity
from factgraph.sdk.store import SDKStoreError


class User(Entity):
    user_id: str = Identity()
    name: str = Field()
    tag_seed: str = Field()
    tag_hint: str = Field()
    tag: str = Field()
    region: str = Field()


def _rule_with_branches() -> Rule:
    with sdk_vars("u", "tag") as (u, tag):
        return Rule(
            id="rule.track1.user_tag_source",
            version="v1",
            select=[u, tag],
            where=[
                Case([Pred("user:tag_seed", u, tag)], id="seed_path"),
                Case([Pred("user:tag_hint", u, tag)]),
            ],
            expose=True,
        )


def _derivation_with_branches() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="drv.track1.user_tag",
            version="v1",
            when=[
                Case([Pred("user:tag_seed", u, tag)], id="seed_path"),
                Case([Pred("user:tag_hint", u, tag)]),
            ],
            emits=EmitSpec("user:tag", [u, tag]),
        )


def _single_head_derivation() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="drv.track1.single",
            version="v1",
            when=[Pred("user:tag_seed", u, tag)],
            emits=EmitSpec("user:tag", [u, tag]),
        )


def _multi_head_derivation() -> Inference:
    with sdk_vars("u", "tag", "region") as (u, tag, region):
        return Inference(
            id="drv.track1.multi",
            version="v1",
            when=[Pred("user:tag_seed", u, tag)],
            head=[User.tag(value=tag), User.region(value=region)],
        )


def _multi_head_derivation_bypass() -> Inference:
    with sdk_vars("u", "tag", "region") as (u, tag, region):
        derivation = Inference(
            id="drv.track1.multi_bypass",
            version="v1",
            when=[Pred("user:tag_seed", u, tag)],
            head=User.tag(value=tag),
        )
        object.__setattr__(derivation, "_heads", (User.tag(value=tag), User.region(value=region)))
        return derivation


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


class BranchIdentityConstructionTests(unittest.TestCase):
    def test_branch_accepts_optional_keyword_id(self) -> None:
        branch = Case([Pred("user:tag_seed", "$u", "$tag")], id="seed_path")

        self.assertEqual(branch.id, "seed_path")
        self.assertEqual(len(branch.atoms), 1)

    def test_branch_without_id_keeps_positional_atoms_behavior(self) -> None:
        branch = Case([Pred("user:tag_seed", "$u", "$tag")])

        self.assertEqual(len(branch.atoms), 1)

    def test_branch_rejects_invalid_id_values(self) -> None:
        for invalid in ("", "1seed", "seed-path", "seed.path"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(SDKDSLError) as ctx:
                    Case([Pred("user:tag_seed", "$u", "$tag")], id=invalid)

                self.assertIn("Case.id", str(ctx.exception))

    def test_branch_still_rejects_engine_semantic_keywords(self) -> None:
        for keyword, value in (
            ("confidence", 0.9),
            ("probability", 0.9),
            ("engine_ext", object()),
        ):
            with self.subTest(keyword=keyword):
                with self.assertRaises((TypeError, SDKDSLError)):
                    Case([Pred("user:tag_seed", "$u", "$tag")], **{keyword: value})


class RuleInspectTests(unittest.TestCase):
    def test_rules_namespace_exists_and_is_read_only(self) -> None:
        sdk = SDKStore([User])

        self.assertTrue(hasattr(sdk, "rules"))
        with self.assertRaises(Exception) as ctx:
            sdk.rules.inspect = object()  # type: ignore[attr-defined]

        self.assertIn("read-only", str(ctx.exception))

    def test_inspect_rule_exposes_explicit_and_fallback_branch_ids(self) -> None:
        sdk = SDKStore([User])

        inspected = sdk.rules.inspect(_rule_with_branches())

        self.assertEqual(inspected["kind"], "Rule")
        self.assertEqual(inspected["id"], "rule.track1.user_tag_source")
        self.assertEqual(inspected["version"], "v1")
        self.assertEqual(len(inspected["branches"]), 2)
        self.assertEqual(inspected["branches"][0]["id"], "seed_path")
        self.assertEqual(inspected["branches"][0]["fallback_id"], "c0")
        self.assertTrue(inspected["branches"][0]["is_explicit_id"])
        self.assertEqual(inspected["branches"][0]["index"], 0)
        self.assertEqual(inspected["branches"][0]["atom_count"], 1)
        self.assertEqual(inspected["branches"][0]["atom_ids"], ["c0.c0"])
        self.assertEqual(inspected["branches"][1]["id"], "c1")
        self.assertEqual(inspected["branches"][1]["fallback_id"], "c1")
        self.assertFalse(inspected["branches"][1]["is_explicit_id"])

    def test_inspect_derivation_uses_same_branch_shape(self) -> None:
        sdk = SDKStore([User])

        inspected = sdk.rules.inspect(_derivation_with_branches())

        self.assertEqual(inspected["kind"], "Inference")
        self.assertEqual(inspected["id"], "drv.track1.user_tag")
        self.assertEqual(inspected["branches"][0]["id"], "seed_path")
        self.assertEqual(inspected["branches"][1]["id"], "c1")
        self.assertIn("heads", inspected)

    def test_inspect_rejects_duplicate_branch_ids(self) -> None:
        with sdk_vars("u", "tag") as (u, tag):
            rule = Rule(
                id="rule.track1.duplicate",
                version="v1",
                select=[u, tag],
                where=[
                    Case([Pred("user:tag_seed", u, tag)], id="dup"),
                    Case([Pred("user:tag_hint", u, tag)], id="dup"),
                ],
            )
        sdk = SDKStore([User])

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.rules.inspect(rule)

        self.assertIn("duplicate Case.id", str(ctx.exception))


class SingleHeadCutTests(unittest.TestCase):
    def test_derivation_constructor_rejects_multi_head(self) -> None:
        with self.assertRaises(SDKDSLError) as ctx:
            _multi_head_derivation()

        self.assertIn("multi-head", str(ctx.exception))

    def test_single_head_derivation_still_constructs(self) -> None:
        derivation = _single_head_derivation()

        self.assertEqual(len(derivation.heads), 0)
        self.assertEqual(derivation.emits, EmitSpec("user:tag", ["$u", "$tag"]))

    def test_sdk_evaluate_rejects_multi_head_if_it_reaches_runtime(self) -> None:
        sdk = SDKStore([User])

        with self.assertRaises(SDKStoreError) as ctx:
            sdk.eval.evaluate(_multi_head_derivation_bypass(), engine="native")

        self.assertIn("multi-head", str(ctx.exception))

    # Slice 7C / Q6-A (a.2): `test_sdk_registry_rejects_multi_head_if_it_reaches_runtime`
    # was removed because the `SDKRegistry` class no longer exists. Multi-head
    # rejection at the rule-compile / eval boundary is exercised by
    # `test_multi_head_inference_eval_bypass_rejects` above.


class BranchIdentityGuardTests(unittest.TestCase):
    def test_positional_branch_to_authoring_payload_stays_branch_id_free(self) -> None:
        with sdk_vars("u", "tag") as (u, tag):
            rule = Rule(
                id="rule.track1.payload",
                version="v1",
                select=[u, tag],
                where=[Case([Pred("user:tag_seed", u, tag)])],
            )

        payload = rule.to_authoring_payload()

        self.assertFalse(_contains_key(payload, "branch_id"))
        self.assertFalse(_contains_key(payload, "branch_ids"))
        self.assertIn("where", payload)

    def test_condition_weights_remain_positional(self) -> None:
        payload = {
            "rule_id": "rule.track1.condition_weights",
            "version": "v1",
            "select": ["$u", "$tag"],
            "where": [[("pred", "user:tag_seed", ["$u", "$tag"])]],
            "condition_weights": {"c0.c0": 1.0},
        }

        compiled = compile_authoring_rule_v1(payload)

        self.assertEqual(compiled["condition_weights"], {"c0.c0": 1.0})

    def test_condition_weights_do_not_accept_branch_id_keys(self) -> None:
        payload = {
            "rule_id": "rule.track1.condition_weights_reject",
            "version": "v1",
            "select": ["$u", "$tag"],
            "where": [[("pred", "user:tag_seed", ["$u", "$tag"])]],
            "condition_weights": {"seed_path.c0": 1.0},
        }

        with self.assertRaises(AuthoringRuleCompileError) as ctx:
            compile_authoring_rule_v1(payload)

        self.assertIn("condition_weights key must match existing where atom position", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
