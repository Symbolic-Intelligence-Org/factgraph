from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path
from typing import Any, Callable

from factgraph.authoring.registry_fs import FileAuthoringRegistry
from factgraph.sdk import Database, Entity, FactGraph, Field, Identity, Inference, Pred, Rule, SDKStoreError
from factgraph.sdk import vars as sdk_vars
from factgraph.sdk.compile import compile_schema_from_classes
from factgraph.sdk.registry import SDKRegistry


class User(Entity):
    user_id: str = Identity(primary_key=True)
    tag_seed: str = Field(cardinality="single")
    tag: str = Field(cardinality="single")


def _schema_ir() -> dict[str, Any]:
    return compile_schema_from_classes([User])


def _rule() -> Rule:
    with sdk_vars("u", "tag") as (u, tag):
        return Rule(
            id="rule.savedrule.phase1",
            version="v1",
            select=[u, tag],
            where=[Pred("user:tag_seed", u, tag)],
            expose=True,
        )


def _inference() -> Inference:
    with sdk_vars("u", "tag") as (u, tag):
        return Inference(
            id="inf.savedrule.phase1",
            version="v1",
            where=[Pred("user:tag_seed", u, tag)],
            target="user:tag",
            head_vars=[u, tag],
        )


class SavedRulePhase1DeprecationTests(unittest.TestCase):
    def _call_ignoring_errors(self, call: Callable[[], Any]) -> Any:
        try:
            return call()
        except Exception:
            return None

    def _deprecation_warnings_from(self, call: Callable[[], Any]) -> list[warnings.WarningMessage]:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self._call_ignoring_errors(call)
        return [warning for warning in caught if issubclass(warning.category, DeprecationWarning)]

    def assert_deprecated_once(self, call: Callable[[], Any], method_name: str) -> None:
        deprecations = self._deprecation_warnings_from(call)
        self.assertEqual(len(deprecations), 1, [str(warning.message) for warning in deprecations])
        message = str(deprecations[0].message)
        self.assertIn(method_name, message)
        self.assertIn("Q8 Phase 1", message)
        self.assertIn("Rule(...) / Inference(...)", message)

    def assert_no_deprecation(self, call: Callable[[], Any]) -> None:
        deprecations = self._deprecation_warnings_from(call)
        self.assertEqual(deprecations, [], [str(warning.message) for warning in deprecations])

    def test_sdkstore_flat_rule_inference_methods_emit_one_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fg = FactGraph.create(schema_classes=[User], registry_root=Path(tmp) / "registry")
            calls: dict[str, Callable[[], Any]] = {
                "fg.save_rule": lambda: fg.save_rule(_rule()),
                "fg.load_rule": lambda: fg.load_rule("missing-rule", version="v1"),
                "fg.list_rules": fg.list_rules,
                "fg.get_rule": lambda: fg.get_rule("missing-rule"),
                "fg.save_inference": lambda: fg.save_inference(_inference()),
                "fg.load_inference": lambda: fg.load_inference("missing-inf", version="v1"),
                "fg.list_inferences": fg.list_inferences,
                "fg.get_inference": lambda: fg.get_inference("missing-inf"),
            }

            for method_name, call in calls.items():
                with self.subTest(method=method_name):
                    self.assert_deprecated_once(call, method_name)

    def test_manager_rule_inference_methods_warn_once_via_flat_methods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fg = FactGraph.create(schema_classes=[User], registry_root=Path(tmp) / "registry")
            calls: dict[str, tuple[str, Callable[[], Any]]] = {
                "fg.rules.save": ("fg.save_rule", lambda: fg.rules.save(_rule())),
                "fg.rules.load": ("fg.load_rule", lambda: fg.rules.load("missing-rule", version="v1")),
                "fg.rules.list": ("fg.list_rules", fg.rules.list),
                "fg.rules.get": ("fg.get_rule", lambda: fg.rules.get("missing-rule")),
                "fg.inferences.save": ("fg.save_inference", lambda: fg.inferences.save(_inference())),
                "fg.inferences.load": (
                    "fg.load_inference",
                    lambda: fg.inferences.load("missing-inf", version="v1"),
                ),
                "fg.inferences.list": ("fg.list_inferences", fg.inferences.list),
                "fg.inferences.get": ("fg.get_inference", lambda: fg.inferences.get("missing-inf")),
            }

            for label, (warning_method, call) in calls.items():
                with self.subTest(method=label):
                    self.assert_deprecated_once(call, warning_method)

    def test_rule_inspect_and_non_deprecated_flat_methods_do_not_warn(self) -> None:
        fg = FactGraph.from_schema_classes([User])

        self.assert_no_deprecation(lambda: fg.rules.inspect(_rule()))
        self.assert_no_deprecation(lambda: fg.ref(User, user_id="u-1"))
        self.assert_no_deprecation(lambda: fg.find(User))

    def test_attached_savedrule_writes_warn_before_reject(self) -> None:
        db = Database.create(schema_ir=_schema_ir())
        fg = FactGraph.attach(db, schema_classes=[User])

        for method_name, call in {
            "fg.save_rule": lambda: fg.save_rule(_rule()),
            "fg.save_inference": lambda: fg.save_inference(_inference()),
        }.items():
            with self.subTest(method=method_name):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    with self.assertRaisesRegex(SDKStoreError, "fg\\.commit_assertions"):
                        call()
                deprecations = [warning for warning in caught if issubclass(warning.category, DeprecationWarning)]
                self.assertEqual(len(deprecations), 1)
                self.assertIn(method_name, str(deprecations[0].message))

    def test_sdkregistry_rule_inference_methods_emit_one_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fg = FactGraph.from_schema_classes([User])
            registry = SDKRegistry(tmp)
            rule_spec = fg._compile_rule_input(_rule())
            inference_payload = _inference().to_authoring_payload()
            calls: dict[str, Callable[[], Any]] = {
                "SDKRegistry.register_rule_spec": lambda: registry.register_rule_spec(rule_spec),
                "SDKRegistry.register_rule": lambda: registry.register_rule(_rule(), schema_ir=fg.schema_ir),
                "SDKRegistry.register_inference_spec": lambda: registry.register_inference_spec(inference_payload),
                "SDKRegistry.register_inference": lambda: registry.register_inference(
                    _inference(),
                    schema_ir=fg.schema_ir,
                ),
                "SDKRegistry.list_rule_ids": registry.list_rule_ids,
                "SDKRegistry.list_inference_ids": registry.list_inference_ids,
                "SDKRegistry.list_rule_versions": lambda: registry.list_rule_versions("missing-rule"),
                "SDKRegistry.list_inference_versions": lambda: registry.list_inference_versions("missing-inf"),
                "SDKRegistry.get_latest_rule_spec": lambda: registry.get_latest_rule_spec("missing-rule"),
                "SDKRegistry.get_latest_inference_spec": lambda: registry.get_latest_inference_spec("missing-inf"),
                "SDKRegistry.read_rule_spec": lambda: registry.read_rule_spec("missing-rule", "v1"),
                "SDKRegistry.read_inference_spec": lambda: registry.read_inference_spec("missing-inf", "v1"),
            }

            for method_name, call in calls.items():
                with self.subTest(method=method_name):
                    self.assert_deprecated_once(call, method_name)

    def test_sdkregistry_wrapper_methods_do_not_double_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fg = FactGraph.from_schema_classes([User])
            registry = SDKRegistry(tmp)

            self.assert_deprecated_once(
                lambda: registry.register_rule(_rule(), schema_ir=fg.schema_ir),
                "SDKRegistry.register_rule",
            )
            self.assert_deprecated_once(
                lambda: registry.register_inference(_inference(), schema_ir=fg.schema_ir),
                "SDKRegistry.register_inference",
            )

    def test_apply_authoring_bundle_warns_only_for_rule_or_inference_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = SDKRegistry(tmp)
            schema_ir = _schema_ir()
            rule_request = {"rule": _rule().to_authoring_payload()}
            derivation_request = {"derivation": _inference().to_authoring_payload()}

            self.assert_deprecated_once(
                lambda: registry.apply_authoring_bundle(rule_request=rule_request, schema_ir=schema_ir),
                "SDKRegistry.apply_authoring_bundle(rule/inference)",
            )
            self.assert_deprecated_once(
                lambda: registry.apply_authoring_bundle(derivation_request=derivation_request, schema_ir=schema_ir),
                "SDKRegistry.apply_authoring_bundle(rule/inference)",
            )
            self.assert_deprecated_once(
                lambda: registry.apply_authoring_bundle(
                    rule_request=rule_request,
                    derivation_request=derivation_request,
                    schema_ir=schema_ir,
                ),
                "SDKRegistry.apply_authoring_bundle(rule/inference)",
            )
            self.assert_no_deprecation(lambda: registry.apply_schema_classes([User]))
            self.assert_no_deprecation(lambda: registry.apply_authoring_bundle(authoring_schema={"entities": []}))

    def test_sdkregistry_audit_manifest_schema_and_substrate_methods_do_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = SDKRegistry(tmp)
            substrate = FileAuthoringRegistry(Path(tmp) / "substrate")
            schema_ir = _schema_ir()

            no_warn_calls: list[Callable[[], Any]] = [
                registry.read_manifest,
                registry.list_apply_run_ids,
                registry.list_apply_runs,
                lambda: registry.show_apply_run("missing-run"),
                lambda: registry.upsert_schema_ir(schema_ir),
                registry.get_schema_entry,
                lambda: substrate.register_rule_spec({}),
                lambda: substrate.register_inference_spec({}),
            ]

            for index, call in enumerate(no_warn_calls):
                with self.subTest(index=index):
                    self.assert_no_deprecation(call)


if __name__ == "__main__":
    unittest.main()
