import json

import pytest

from factgraph.application.protocol.common import ProtocolShapeError
from factgraph.application.protocol.scenario_v1 import (
    ExactLocalClosureTargetV1,
    ScenarioCreateEphemeralEntityV1,
    ScenarioEnsureMemberV1,
    ScenarioEnsureRelationV1,
    ScenarioSetEffectiveValueV1,
    ScenarioSetExactMembersV1,
    ScenarioSpecV1,
    ScenarioValueV1,
    ScenarioWithoutAssertionV1,
    ScenarioWithoutEntityV1,
    ScenarioWithoutFieldV1,
    ScenarioWithoutRelationV1,
    ScenarioWithoutValueV1,
)
from factgraph.application.protocol.schema_runtime import EntityRef, FieldPath
from factgraph.application.protocol.sealed_evaluation_scenario_v1 import (
    exact_local_closure_target_v1_from_wire,
    exact_local_closure_target_v1_to_wire,
    scenario_spec_v1_bytes,
    scenario_spec_v1_from_bytes,
)


def ent(identity=None, typ="Person"):
    return EntityRef(typ, identity or {"id": "a"})


def all_ops():
    e = ent()
    f = FieldPath("Person", "age")
    v = ScenarioValueV1("int", 1)
    return (
        ScenarioSetEffectiveValueV1("p1", e, f, v),
        ScenarioEnsureMemberV1("p2", e, f, v),
        ScenarioSetExactMembersV1("p3", e, f, (v,)),
        ScenarioWithoutFieldV1("p4", e, f),
        ScenarioWithoutValueV1("p5", e, f, v),
        ScenarioCreateEphemeralEntityV1("p6", e),
        ScenarioEnsureRelationV1("p7", "knows", (v,)),
        ScenarioWithoutRelationV1("p8", "knows"),
        ScenarioWithoutEntityV1("p9", e),
        ScenarioWithoutAssertionV1("p10", "assertion"),
    )


def test_all_ten_operation_arms_roundtrip_and_golden_stable():
    spec = ScenarioSpecV1(all_ops())
    raw = scenario_spec_v1_bytes(spec)
    assert raw == scenario_spec_v1_bytes(scenario_spec_v1_from_bytes(raw))
    assert scenario_spec_v1_from_bytes(raw).spec_digest == spec.spec_digest


def test_closure_target_wire_roundtrip():
    target = ExactLocalClosureTargetV1("member", "entity-token", "age", ScenarioValueV1("int", 2))
    wire = exact_local_closure_target_v1_to_wire(target)
    assert exact_local_closure_target_v1_from_wire(wire).target_digest == target.target_digest


@pytest.mark.parametrize("bad", [1.0, float("nan"), float("inf"), -0.0])
def test_entity_identity_rejects_all_raw_float_forms(bad):
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_bytes(ScenarioSpecV1((ScenarioWithoutEntityV1("p", ent({"x": bad})),)))


def test_entity_hint_is_not_a_wire_escape():
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_bytes(
            ScenarioSpecV1(
                (ScenarioWithoutEntityV1("p", EntityRef("Person", {"id": "a"}, "spoof")),)
            )
        )


def test_entity_digest_and_type_identity_are_bound():
    raw = scenario_spec_v1_bytes(ScenarioSpecV1((ScenarioWithoutEntityV1("p", ent()),)))
    obj = json.loads(raw)
    entity = obj["operations"][0]["entity"]
    entity["entity_type"] = "Company"
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(json.dumps(obj, separators=(",", ":"), sort_keys=True).encode())


def test_duplicate_unknown_noncanonical_and_limits_reject():
    spec = ScenarioSpecV1((ScenarioWithoutAssertionV1("p", "a"),))
    raw = scenario_spec_v1_bytes(spec)
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(raw.replace(b'"operations":', b'"operations":', 1) + b" ")
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(raw.replace(b'"kind":"without_assertion"', b'"kind":"nope"'))
    too_many = ScenarioSpecV1(
        tuple(ScenarioWithoutAssertionV1(f"p{i}", f"a{i}") for i in range(256))
    )
    assert len(scenario_spec_v1_bytes(too_many)) > 0
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_bytes(
            ScenarioSpecV1(tuple(ScenarioWithoutAssertionV1(f"p{i}", f"a{i}") for i in range(257)))
        )


@pytest.mark.parametrize(
    "index",
    range(10),
    ids=[
        "set-effective-value",
        "ensure-member",
        "set-exact-members",
        "without-field",
        "without-value",
        "create-ephemeral-entity",
        "ensure-relation",
        "without-relation",
        "without-entity",
        "without-assertion",
    ],
)
def test_each_operation_arm_rejects_unknown_missing_and_null_fields(index):
    raw = scenario_spec_v1_bytes(ScenarioSpecV1((all_ops()[index],)))
    body = json.loads(raw)
    body["operations"][0]["unexpected"] = 1
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )
    body = json.loads(raw)
    operation = body["operations"][0]
    removed = next(key for key in operation if key not in {"$type", "kind", "statement_digest"})
    del operation[removed]
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )
    body = json.loads(raw)
    body["operations"][0]["statement_digest"] = None
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )


@pytest.mark.parametrize(
    "kind,kwargs",
    [
        ("field", {"entity_ref": "e", "predicate_id": "p"}),
        ("member", {"entity_ref": "e", "predicate_id": "p", "value": ScenarioValueV1("int", 1)}),
        (
            "exact_set",
            {"entity_ref": "e", "predicate_id": "p", "members": (ScenarioValueV1("int", 1),)},
        ),
        ("relation", {"predicate_id": "p"}),
        ("entity", {"entity_ref": "e"}),
        ("assertion", {"predicate_id": "p", "assertion_id": "a"}),
    ],
)
def test_all_six_exact_local_closure_target_modes_roundtrip(kind, kwargs):
    params = dict(kwargs)
    target = ExactLocalClosureTargetV1(
        kind, params.pop("entity_ref", None), params.pop("predicate_id", None), **params
    )
    wire = exact_local_closure_target_v1_to_wire(target)
    assert exact_local_closure_target_v1_from_wire(wire).target_digest == target.target_digest


def test_closure_members_duplicate_and_invalid_mode_reject():
    with pytest.raises(ProtocolShapeError):
        ExactLocalClosureTargetV1(
            "exact_set", "e", "p", members=(ScenarioValueV1("int", 1), ScenarioValueV1("int", 1))
        )
    with pytest.raises(ProtocolShapeError):
        ExactLocalClosureTargetV1("unknown", None, None)


def test_operation_origin_and_value_duplicates_are_digest_bound():
    value = ScenarioValueV1("int", 1)
    with pytest.raises(ProtocolShapeError):
        ScenarioSetExactMembersV1("p", ent(), FieldPath("Person", "age"), (value, value))
    op = ScenarioWithoutRelationV1("p", "rel", ("z", "a"))
    raw = scenario_spec_v1_bytes(ScenarioSpecV1((op,)))
    assert json.loads(raw)["operations"][0]["origin_refs"] == ["a", "z"]
    body = json.loads(raw)
    body["operations"][0]["origin_refs"] = ["a", "a"]
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )


def test_stale_frozen_spec_and_statement_digests_reject():
    body = json.loads(
        scenario_spec_v1_bytes(ScenarioSpecV1((ScenarioWithoutAssertionV1("p", "a"),)))
    )
    body["spec_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )
    body = json.loads(
        scenario_spec_v1_bytes(ScenarioSpecV1((ScenarioWithoutAssertionV1("p", "a"),)))
    )
    body["operations"][0]["statement_digest"] = "sha256:" + "0" * 64
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )


@pytest.mark.parametrize(
    "identity",
    [
        {"x": float("nan")},
        {"x": float("inf")},
        {"x": -0.0},
        {"x": 1.0},
    ],
)
def test_entity_identity_rejects_all_raw_float_semantics(identity):
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_bytes(ScenarioSpecV1((ScenarioWithoutEntityV1("p", ent(identity)),)))


def test_entity_identity_boolean_is_not_integer_and_digest_tamper_rejects():
    assert scenario_spec_v1_bytes(ScenarioSpecV1((ScenarioWithoutEntityV1("p", ent({"x": True})),)))
    raw = scenario_spec_v1_bytes(ScenarioSpecV1((ScenarioWithoutEntityV1("p", ent()),)))
    body = json.loads(raw)
    entity = body["operations"][0]["entity"]
    entity["identity"]["id"] = "different"
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )
    body = json.loads(raw)
    body["operations"][0]["entity"]["identity_digest"] = "sha256:" + "f" * 64
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        )


def test_identity_bounds_depth_nodes_container_key_type_string_and_bytes():
    def encode(identity):
        return scenario_spec_v1_bytes(
            ScenarioSpecV1((ScenarioWithoutEntityV1("p", ent(identity)),))
        )

    assert encode({"x": "a" * 4096})
    with pytest.raises(ProtocolShapeError):
        encode({"x": "a" * 4097})
    with pytest.raises(ProtocolShapeError):
        encode({"x" * 257: 1})
    with pytest.raises(ProtocolShapeError):
        encode({str(i): i for i in range(65)})
    with pytest.raises(ProtocolShapeError):
        encode({"x": list(range(65))})
    with pytest.raises(ProtocolShapeError):
        encode({"x": [{"y": [0] * 64}] * 4})
    nested = 0
    for _ in range(6):
        nested = {"x": nested}
    assert encode({"x": nested})
    with pytest.raises(ProtocolShapeError):
        encode({"x": {"x": nested}})
    with pytest.raises(ProtocolShapeError):
        encode({str(i): i for i in range(257)})
    with pytest.raises(ProtocolShapeError):
        encode({"x": "é" * 2049})
    with pytest.raises(ProtocolShapeError):
        encode({str(i): "a" * 4096 for i in range(4)})


def test_entity_type_and_identity_text_are_control_free_unicode_with_utf8_bounds():
    assert scenario_spec_v1_bytes(
        ScenarioSpecV1((ScenarioWithoutEntityV1("p", EntityRef("é" * 128, {"id": "a"})),))
    )
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_bytes(
            ScenarioSpecV1((ScenarioWithoutEntityV1("p", EntityRef("é" * 129, {"id": "a"})),))
        )
    for invalid in ("Person\nInjected", "Person\x7f", "\ud800"):
        with pytest.raises(ProtocolShapeError):
            scenario_spec_v1_bytes(
                ScenarioSpecV1((ScenarioWithoutEntityV1("p", EntityRef(invalid, {"id": "a"})),))
            )
    for invalid_identity in ({"id": "line\nbreak"}, {"id\x00": "a"}, {"id": "\ud800"}):
        with pytest.raises(ProtocolShapeError):
            scenario_spec_v1_bytes(
                ScenarioSpecV1((ScenarioWithoutEntityV1("p", ent(invalid_identity)),))
            )


def test_encoded_ref_spoof_and_wrong_concrete_live_types_reject():
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_bytes(
            ScenarioSpecV1((ScenarioWithoutEntityV1("p", EntityRef("P", {"id": "a"}, "spoof")),))
        )

    class EntityChild(EntityRef):
        pass

    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_bytes(
            ScenarioSpecV1((ScenarioWithoutEntityV1("p", EntityChild("P", {"id": "a"})),))
        )
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_bytes(
            ScenarioSpecV1((ScenarioWithoutEntityV1("p", {"entity_type": "P"}),))
        )


def test_canonical_key_order_duplicate_keys_and_noncanonical_utf8_reject():
    raw = scenario_spec_v1_bytes(ScenarioSpecV1((ScenarioWithoutAssertionV1("p", "a"),)))
    assert scenario_spec_v1_from_bytes(raw).spec_digest
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(raw + b" ")
    duplicate = raw.replace(
        b'"spec_digest":', b'"spec_digest":"sha256:' + b"0" * 64 + b'","spec_digest":', 1
    )
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(duplicate)
    with pytest.raises(ProtocolShapeError):
        scenario_spec_v1_from_bytes(b"\xff")
