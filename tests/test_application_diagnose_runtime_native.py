"""Native runtime tests for `factgraph.application.diagnose_runtime` (§8 Step 2)."""
from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from factgraph.application import (
    build_schema_index,
    diagnose_derivation_binding,
    entity_info,
    field_predicate,
    resolve_selector,
)
from factgraph.application.protocol import (
    CompiledDerivationPlan,
    CompiledHeadCall,
    DiagnoseRequest,
    EntitySelector,
)
from factgraph.core.evidence.write_protocol import set_field
from factgraph.core.rules.rule_ir import RuleRegistry, RuleSpec
from factgraph.core.store import Store
from factgraph.sdk import Entity, Field, Identity, compile_schema_from_classes


class Person(Entity):
    name: str = Identity()
    age: int = Field()
    region: str = Field()


def _build_store() -> tuple[Store, Any]:
    schema_ir = compile_schema_from_classes([Person])
    store = Store(schema_ir)
    index = build_schema_index(schema_ir)
    return store, index


def _seed_person(
    store: Store,
    index: Any,
    name: str,
    age: int,
    region: str,
) -> str:
    ref = resolve_selector(
        EntitySelector(entity_type="Person", identity={"name": name}),
        index=index,
    )
    info = entity_info(index, "Person")
    encoded = ref.encoded_ref or ""
    set_field(store.ledger, info.exists_predicate_id, encoded, [])
    set_field(
        store.ledger,
        info.identity_predicates["name"].pred_id,
        encoded,
        [("string", name)],
    )
    set_field(
        store.ledger,
        field_predicate(index, "Person", "age").pred_id,
        encoded,
        [("int", age)],
    )
    set_field(
        store.ledger,
        field_predicate(index, "Person", "region").pred_id,
        encoded,
        [("string", region)],
    )
    return encoded


def _build_plan(
    body_ir: list[Any],
    target_pred_id: str,
    head_var_names: tuple[str, ...] = ("$p",),
) -> CompiledDerivationPlan:
    return CompiledDerivationPlan(
        derivation_id="diagnose-test",
        version="1.0",
        body_ir=body_ir,
        heads=(
            CompiledHeadCall(
                target_pred_id=target_pred_id,
                head_var_names=head_var_names,
            ),
        ),
    )


def _exists_body(index: Any) -> tuple[list[Any], str]:
    info = entity_info(index, "Person")
    body: list[Any] = [("pred", info.exists_predicate_id, ["$p"])]
    return body, info.exists_predicate_id


def _exists_age_region_body(index: Any) -> tuple[list[Any], str]:
    info = entity_info(index, "Person")
    age_pred = field_predicate(index, "Person", "age").pred_id
    region_pred = field_predicate(index, "Person", "region").pred_id
    body: list[Any] = [
        ("pred", info.exists_predicate_id, ["$p"]),
        ("pred", age_pred, ["$p", "$age"]),
        ("pred", region_pred, ["$p", "$region"]),
    ]
    return body, info.exists_predicate_id


class NativeDiagnoseHappyPathTests(unittest.TestCase):
    def test_complete_binding_passes(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, target = _exists_age_region_body(index)
        request = DiagnoseRequest(
            plan=_build_plan(body, target),
            binding=(("$age", 25), ("$p", encoded), ("$region", "us")),
            engine="native",
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)
        self.assertIsNotNone(result.matched_binding)
        self.assertIsNone(result.failure_kind)
        self.assertIsNone(result.diagnostic_payload)

    def test_partial_binding_passes_with_full_primary_binding(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, target = _exists_age_region_body(index)
        request = DiagnoseRequest(
            plan=_build_plan(body, target),
            binding=(("$p", encoded),),
            engine="native",
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)
        keys = {key for key, _ in result.matched_binding or ()}
        self.assertIn("$p", keys)
        self.assertIn("$age", keys)
        self.assertIn("$region", keys)

    def test_passed_primary_uses_branch_index_before_binding_items(self) -> None:
        store, _index = _build_store()
        body: list[Any] = [
            [("eq", "$p", "z-branch-zero")],
            [("eq", "$p", "a-branch-one")],
        ]
        request = DiagnoseRequest(
            plan=_build_plan(body, "Person:exists"),
            binding=(),
            engine="native",
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_binding, (("$p", "z-branch-zero"),))


class NativeAtomLocalizationTests(unittest.TestCase):
    def test_failed_binding_reports_first_failed_atom_index(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, target = _exists_age_region_body(index)
        request = DiagnoseRequest(
            plan=_build_plan(body, target),
            binding=(("$p", encoded), ("$region", "eu")),
            engine="native",
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_kind, "atom_localized")
        locator = result.diagnostic_payload
        assert locator is not None
        self.assertEqual(locator.branch_index, 0)
        self.assertEqual(locator.failed_atom_index, 2)
        self.assertIn(("$age", 25), locator.attempted_binding)

    def test_primary_failure_prefers_most_progressed_branch(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        info = entity_info(index, "Person")
        age_pred = field_predicate(index, "Person", "age").pred_id
        region_pred = field_predicate(index, "Person", "region").pred_id
        body: list[Any] = [
            [("pred", age_pred, ["$missing", "$age"])],
            [
                ("pred", info.exists_predicate_id, ["$p"]),
                ("pred", age_pred, ["$p", "$age"]),
                ("pred", region_pred, ["$p", "$region"]),
            ],
        ]
        request = DiagnoseRequest(
            plan=_build_plan(body, info.exists_predicate_id),
            binding=(("$p", encoded), ("$region", "eu")),
            engine="native",
        )

        result = diagnose_derivation_binding(request, store=store)

        locator = result.diagnostic_payload
        assert locator is not None
        self.assertEqual(locator.branch_index, 1)
        self.assertEqual(locator.failed_atom_index, 2)

    def test_localizer_keeps_candidate_frontier_instead_of_single_primary_path(self) -> None:
        store, index = _build_store()
        _seed_person(store, index, "alice", 25, "us")
        _seed_person(store, index, "bob", 25, "eu")
        info = entity_info(index, "Person")
        age_pred = field_predicate(index, "Person", "age").pred_id
        region_pred = field_predicate(index, "Person", "region").pred_id
        body: list[Any] = [
            ("pred", info.exists_predicate_id, ["$p"]),
            ("pred", region_pred, ["$p", "eu"]),
            ("pred", age_pred, ["$p", "$age"]),
            ("eq", "$age", 99),
        ]
        request = DiagnoseRequest(
            plan=_build_plan(body, info.exists_predicate_id),
            binding=(),
            engine="native",
        )

        result = diagnose_derivation_binding(request, store=store)

        locator = result.diagnostic_payload
        assert locator is not None
        self.assertEqual(locator.failed_atom_index, 3)
        self.assertIn(("$age", 25), locator.attempted_binding)

    def test_no_candidate_fallback_when_localizer_has_no_branch_candidate(self) -> None:
        store, index = _build_store()
        body, target = _exists_body(index)
        request = DiagnoseRequest(
            plan=_build_plan(body, target),
            binding=(),
            engine="native",
        )

        # Empty binding + empty store still has a failing branch, so force the
        # fallback path by patching the implementation-detail localizer result.
        from unittest.mock import patch

        with patch(
            "factgraph.application.diagnose_runtime._localize_failed_atom",
            return_value=None,
        ):
            result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_kind, "no_candidate")
        self.assertIsNone(result.diagnostic_payload)


class NativeInvalidRequestTests(unittest.TestCase):
    def test_unknown_variable_invalid_request(self) -> None:
        store, index = _build_store()
        body, target = _exists_body(index)
        request = DiagnoseRequest(
            plan=_build_plan(body, target),
            binding=(("$missing", "x"),),
            engine="native",
        )

        result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "UNKNOWN_VARIABLE_IN_BINDING")

    def test_ruleref_without_registry_invalid_request(self) -> None:
        store, index = _build_store()
        body, target = _exists_body(index)
        plan = _build_plan(body + [("ruleref", "child", "1.0", ["$p"])], target)
        request = DiagnoseRequest(plan=plan, binding=(), engine="native")

        result = diagnose_derivation_binding(request, store=store, registry=None)

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "REGISTRY_REQUIRED")

    def test_ruleref_unresolvable_invalid_request(self) -> None:
        store, index = _build_store()
        body, target = _exists_body(index)
        plan = _build_plan(body + [("ruleref", "missing", "1.0", ["$p"])], target)
        request = DiagnoseRequest(plan=plan, binding=(), engine="native")

        result = diagnose_derivation_binding(request, store=store, registry=RuleRegistry())

        self.assertEqual(result.status, "invalid_request")
        self.assertEqual(result.errors[0].code, "RULE_REF_UNRESOLVABLE")


class NativeRuleRefHappyPathTests(unittest.TestCase):
    def test_ruleref_with_valid_registry_passes(self) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        child_body, target = _exists_body(index)
        registry = RuleRegistry()
        registry.register(
            RuleSpec(
                rule_id="person.exists",
                version="1.0",
                select_vars=["$p"],
                where=child_body,
                expose=True,
            )
        )
        parent_body: list[Any] = [("ruleref", "person.exists", "1.0", ["$p"])]
        request = DiagnoseRequest(
            plan=_build_plan(parent_body, target),
            binding=(("$p", encoded),),
            engine="native",
        )

        result = diagnose_derivation_binding(request, store=store, registry=registry)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.matched_count, 1)
        self.assertEqual(result.matched_binding, (("$p", encoded),))


class NativeAtomExtensionPrimitiveTests(unittest.TestCase):
    def test_extend_env_with_atom_enumerates_new_variable(self) -> None:
        from factgraph.application.diagnose_runtime import _extend_env_with_atom

        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        age_pred = field_predicate(index, "Person", "age").pred_id
        view_facts = {
            age_pred: [(encoded, 25)],
        }

        extensions = _extend_env_with_atom(
            view_facts,
            {"$p": encoded},
            ("pred", age_pred, ["$p", "$age"]),
        )

        self.assertEqual(extensions, [{"$p": encoded, "$age": 25}])

    def test_extend_env_with_atom_returns_empty_on_bound_mismatch(self) -> None:
        from factgraph.application.diagnose_runtime import _extend_env_with_atom

        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        age_pred = field_predicate(index, "Person", "age").pred_id
        view_facts = {
            age_pred: [(encoded, 25)],
        }

        extensions = _extend_env_with_atom(
            view_facts,
            {"$p": encoded, "$age": 99},
            ("pred", age_pred, ["$p", "$age"]),
        )

        self.assertEqual(extensions, [])


class DiagnoseSevenFourAntiRegressionTests(unittest.TestCase):
    def test_failed_atom_localization_does_not_call_support_capture_atom_satisfies(
        self,
    ) -> None:
        store, index = _build_store()
        encoded = _seed_person(store, index, "alice", 25, "us")
        body, target = _exists_age_region_body(index)
        request = DiagnoseRequest(
            plan=_build_plan(body, target),
            binding=(("$p", encoded), ("$region", "eu")),
            engine="native",
        )

        with patch(
            "factgraph.core.store._support_capture._atom_satisfies",
            side_effect=AssertionError("_atom_satisfies must not be used by Diagnose localization"),
        ):
            result = diagnose_derivation_binding(request, store=store)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.failure_kind, "atom_localized")


if __name__ == "__main__":
    unittest.main()
