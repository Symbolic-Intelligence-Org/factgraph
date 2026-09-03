from __future__ import annotations

import shutil
import unittest

from factgraph import sdk
from factgraph.adapters.souffle.runner import find_souffle_binary
from factgraph.core.evidence.write_protocol import set_field
from factgraph.sdk import Entity, Field, Identity
from factgraph.sdk.dsl import agg_count, build_application_rule, vars
from factgraph.sdk.dsl.expr import lower_where


class Device(Entity):
    device_id: str = Identity()
    owner: str = Field(repr="%ENT owner %FLD")
    rank: int = Field()


def _device_rule():
    with vars("d1", "d2", "owner", "id1", "id2", "rank1", "rank2") as (
        d1,
        d2,
        owner,
        id1,
        id2,
        rank1,
        rank2,
    ):
        return build_application_rule(
            id="shared_device_ne",
            when=[
                Device(d1).owner == owner,
                Device(d2).owner == owner,
                Device(d1).device_id == id1,
                Device(d2).device_id == id2,
                Device(d1).rank == rank1,
                Device(d2).rank == rank2,
                id1 != id2,
                rank1 < rank2,
            ],
            ports={"owner": owner},
            repr="owner %owner has two devices",
        )


def _seed_device(graph: sdk.SDKStore, device_id: str, *, owner: str, rank: int) -> str:
    ref = graph.entities.ref(Device, device_id=device_id)
    set_field(graph.ledger, "Device:exists", ref, [])
    set_field(graph.ledger, "device:device_id", ref, [("string", device_id)])
    set_field(graph.ledger, "device:owner", ref, [("string", owner)])
    set_field(graph.ledger, "device:rank", ref, [("int", rank)])
    return ref


def _binding_value(value: object) -> object:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


class NePrimitiveLoweringTests(unittest.TestCase):
    def test_object_dsl_ne_lowers_to_primitive(self) -> None:
        with vars("left", "right") as (left, right):
            lowered = lower_where([left != right])

        self.assertEqual(lowered, [("ne", "$left", "$right")])

    def test_aggregate_ne_lowers_to_primitive(self) -> None:
        with vars("u", "d", "n") as (u, d, n):
            lowered = lower_where([n != agg_count(where=[Device(d).owner == u])])

        self.assertEqual(lowered[0][0], "ne")
        self.assertEqual(lowered[0][1], "$n")
        self.assertEqual(lowered[0][2][0], "count")

    @unittest.skipIf(find_souffle_binary() is None, "souffle binary is not available")
    def test_object_dsl_ne_souffle_eval_succeeds(self) -> None:
        graph = sdk.SDKStore([Device])
        _seed_device(graph, "D1", owner="C-EVE", rank=1)
        _seed_device(graph, "D2", owner="C-EVE", rank=2)
        _seed_device(graph, "D3", owner="C-MALLORY", rank=3)

        result = graph.eval.evaluate(_device_rule(), head=_device_rule(), engine="souffle")

        self.assertEqual(result.count(), 1)
        self.assertEqual({_binding_value(row.bindings["owner"]) for row in result}, {"C-EVE"})

    @unittest.skipIf(shutil.which("problog") is None, "problog CLI is not available")
    def test_object_dsl_ne_problog_explain_stays_rich(self) -> None:
        graph = sdk.SDKStore([Device])
        _seed_device(graph, "D1", owner="C-EVE", rank=1)
        _seed_device(graph, "D2", owner="C-EVE", rank=2)
        _seed_device(graph, "D3", owner="C-MALLORY", rank=3)

        result = graph.eval.evaluate(_device_rule(), head=_device_rule(), engine="problog")
        narrative = result[0].explain().narrate()

        assert narrative is not None
        text = "\n".join(narrative)
        self.assertIn("does not equal", text)
        self.assertIn("[c0:atom:", text)
        self.assertNotIn("edb_fact", text)
        self.assertNotIn("'='(", text)


if __name__ == "__main__":
    unittest.main()
