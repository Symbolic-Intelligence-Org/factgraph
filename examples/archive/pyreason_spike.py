"""PyReason Provenance Adapter V0 Spike.

Minimal demonstration of PyReason's graph-based temporal reasoning
with full rule trace extraction. This is NOT a factpy integration —
it's a standalone spike to validate the adapter pattern.

Prerequisites:
    pip install 'pyreason==3.0.0'

Environment notes:
    - ARM64 macOS + miniforge: first Numba JIT ~85s, cached ~8.7s
    - pyreason 3.4.0 fails import on this platform; use 3.0.0
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    start = time.time()

    import networkx as nx
    import pyreason as pr

    print(f"[{time.time() - start:.1f}s] PyReason imported")

    # 1. Build graph: a small social network with pet ownership.
    g = nx.DiGraph()
    g.add_node("Alice")
    g.add_node("Bob")
    g.add_node("Carol")
    g.add_node("Dog")
    g.add_node("Cat")

    g.add_edge("Alice", "Bob", Friends=1)
    g.add_edge("Bob", "Carol", Friends=1)
    g.add_edge("Alice", "Dog", owns=1)
    g.add_edge("Bob", "Dog", owns=1)
    g.add_edge("Bob", "Cat", owns=1)
    g.add_edge("Carol", "Cat", owns=1)

    pr.load_graph(g)
    print(
        f"[{time.time() - start:.1f}s] Graph loaded: "
        f"{g.number_of_nodes()} nodes, {g.number_of_edges()} edges"
    )

    # 2. Define rules with temporal propagation.
    pr.add_rule(
        pr.Rule(
            "popular(x) <-1 popular(y), Friends(x,y), owns(y,z), owns(x,z)",
            "shared_pet_popularity",
        )
    )
    pr.add_rule(
        pr.Rule(
            "outdoorsy(x) <-0 owns(x,y), dog_breed(y)",
            "dog_owner_outdoorsy",
        )
    )
    print(f"[{time.time() - start:.1f}s] Rules added")

    # 3. Add initial facts with interval bounds.
    pr.add_fact(pr.Fact("popular(Alice)", "alice_popular", 0, 3))
    pr.add_fact(pr.Fact("dog_breed(Dog)", "dog_is_dog", 0, 3))
    print(f"[{time.time() - start:.1f}s] Facts added")

    # 4. Run reasoning with atom trace enabled.
    pr.settings.atom_trace = True
    reasoning_start = time.time()
    interpretation = pr.reason(timesteps=3)
    reasoning_end = time.time()
    print(f"[{time.time() - start:.1f}s] Reasoning complete ({reasoning_end - reasoning_start:.1f}s)")

    # 5. Extract rule trace (the provenance data).
    nodes_trace, edges_trace = pr.get_rule_trace(interpretation)

    print(f"\n{'=' * 70}")
    print("NODES TRACE (every bound change during reasoning)")
    print(f"{'=' * 70}")
    print(f"Columns: {list(nodes_trace.columns)}")
    print(f"Rows: {len(nodes_trace)}")
    print()
    print(nodes_trace.to_string())

    if len(edges_trace) > 0:
        print(f"\n{'=' * 70}")
        print("EDGES TRACE")
        print(f"{'=' * 70}")
        print(edges_trace.to_string())

    # 6. Extract interpretation (final state per timestep).
    print(f"\n{'=' * 70}")
    print("INTERPRETATION (state per timestep)")
    print(f"{'=' * 70}")

    interpretation_dict = interpretation.get_dict()
    for timestep in sorted(interpretation_dict.keys()):
        print(f"\n  t={timestep}:")
        for component, predicates in sorted(interpretation_dict[timestep].items(), key=lambda item: str(item[0])):
            if predicates:
                print(f"    {component}: {predicates}")

    # 7. Convert to adapter-local JSON carrier.
    from factpy_kernel.adapters.pyreason.provenance import (
        parse_pyreason_trace,
        pyreason_trace_to_dict,
    )

    trace = parse_pyreason_trace(nodes_trace, edges_trace, timesteps=3)
    trace_dict = pyreason_trace_to_dict(trace)

    print(f"\n{'=' * 70}")
    print("ADAPTER-LOCAL JSON CARRIER")
    print(f"{'=' * 70}")
    print(json.dumps(trace_dict, indent=2, ensure_ascii=False))

    # 8. Summary.
    print(f"\n{'=' * 70}")
    print("SPIKE SUMMARY")
    print(f"{'=' * 70}")
    print("  PyReason version: 3.0.0")
    print(f"  Graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    print("  Rules: 2 (1 temporal, 1 immediate)")
    print("  Timesteps: 3")
    print(f"  Node trace events: {len(trace.node_events)}")
    print(f"  Edge trace events: {len(trace.edge_events)}")
    print(f"  Total time: {time.time() - start:.1f}s")
    print()
    print("  Key difference from Souffle:")
    print("    Souffle: proof TREE per conclusion (JSON)")
    print("    PyReason: event LOG of all changes (DataFrame)")
    print("    -> Cannot assume all engines produce trees")
    print("    -> Unified abstraction must accommodate both shapes")

    pr.reset()


if __name__ == "__main__":
    main()
