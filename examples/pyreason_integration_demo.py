#!/usr/bin/env python3
"""PyReason Integration Demo: Schema → Session → Reason → Provenance.

Demonstrates the full factpy + PyReason integration path:
1. Define Entity + Relationship schema using factpy SDK
2. Compile to shared schema_ir
3. Create PyReason engine-specific write session
4. Write node + edge facts with interval bounds and temporal scope
5. Run PyReason reasoning with real engine
6. Extract provenance trace using adapter-local carrier
7. Print summary

Requires: pyreason==3.0.0 (pip install 'pyreason==3.0.0')
Note: First run has ~85s JIT warmup (numba); subsequent runs ~8-10s.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Ensure src/ is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from factpy_kernel.sdk import Entity, Identity, Field, Relationship
from factpy_kernel.sdk.compile import compile_schema_from_classes
from factpy_kernel.adapters.pyreason.session import PyReasonSession

start = time.time()


# ════════════════════════════════════════════════════════════════
# 1. Schema Definition (shared — same for all engines)
# ════════════════════════════════════════════════════════════════

class User(Entity):
    user_id: str = Identity(primary_key=True)
    locale: str = Identity()
    name: str = Field(cardinality="single")
    popular: str = Field(cardinality="single")
    outdoorsy: str = Field(cardinality="single")


class Pet(Entity):
    pet_id: str = Identity(primary_key=True)
    locale: str = Identity()
    species: str = Field(cardinality="single")
    dog_breed: str = Field(cardinality="single")


class Friends(Relationship):
    from_entity = User
    to_entity = User
    strength: str = Field(cardinality="single")


class Owns(Relationship):
    from_entity = User
    to_entity = Pet
    since: str = Field(cardinality="single")


schema_ir = compile_schema_from_classes([User, Pet, Friends, Owns])
pred_ids = [p["pred_id"] for p in schema_ir["predicates"]]
rel_preds = [p["pred_id"] for p in schema_ir["predicates"] if p.get("relationship_type")]

print(f"[{time.time()-start:.1f}s] Schema compiled: {len(pred_ids)} predicates ({len(rel_preds)} relationship)")
for pid in pred_ids:
    marker = " [rel]" if pid in rel_preds else ""
    print(f"  {pid}{marker}")


# ════════════════════════════════════════════════════════════════
# 2. PyReason Session: Write Facts (engine-specific path)
# ════════════════════════════════════════════════════════════════

session = PyReasonSession(schema_ir)

# Node facts — entity attributes with interval bounds
session.write_node_fact("user:popular", "Alice", "true",
    bound=[1.0, 1.0], meta={"source": "manual_assessment", "analyst": "Admin"})
session.write_node_fact("user:name", "Alice", "Alice",
    bound=[1.0, 1.0], meta={"source": "user_profile"})
session.write_node_fact("user:name", "Bob", "Bob",
    bound=[1.0, 1.0], meta={"source": "user_profile"})
session.write_node_fact("pet:species", "Dog", "canine",
    bound=[1.0, 1.0])
session.write_node_fact("pet:dog_breed", "Dog", "labrador",
    bound=[1.0, 1.0])

# Edge facts — relationships with interval bounds
session.write_edge_fact("friends:strength", "Alice", "Bob", "0.9",
    bound=[0.9, 0.9], meta={"source": "social_network_data"})
session.write_edge_fact("friends:strength", "Bob", "Alice", "0.9",
    bound=[0.9, 0.9], meta={"source": "social_network_data"})
session.write_edge_fact("owns:since", "Alice", "Dog", "2024",
    bound=[1.0, 1.0], meta={"source": "pet_registry"})
session.write_edge_fact("owns:since", "Bob", "Dog", "2023",
    bound=[1.0, 1.0], meta={"source": "pet_registry"})

print(f"\n[{time.time()-start:.1f}s] Session facts written:")
print(f"  Node facts: {len(session.node_facts)}")
print(f"  Edge facts: {len(session.edge_facts)}")
print(f"  Audit meta entries: {len(session.all_facts_meta)}")

# Show auto-derived confidence
for entry in session.all_facts_meta[:3]:
    print(f"  {entry['pred_id']} → confidence={entry['meta'].get('confidence')}")


# ════════════════════════════════════════════════════════════════
# 3. PyReason Reasoning (requires pyreason==3.0.0)
# ════════════════════════════════════════════════════════════════

try:
    import pyreason as pr
except ImportError:
    print("\n[ERROR] pyreason not installed. Run: pip install 'pyreason==3.0.0'")
    print("Skipping reasoning + provenance. Schema + session demo complete.")
    sys.exit(0)

import networkx as nx

# Build graph from session facts
g = nx.DiGraph()

# Add nodes
nodes = set()
for f in session.node_facts:
    nodes.add(f["node_ref"])
for f in session.edge_facts:
    nodes.add(f["from_ref"])
    nodes.add(f["to_ref"])
for node in nodes:
    g.add_node(node)

# Add node attributes from facts
for f in session.node_facts:
    attr_name = f["pred_id"].split(":")[-1]
    g.nodes[f["node_ref"]][attr_name] = 1

# Add edges from edge facts
for f in session.edge_facts:
    attr_name = f["pred_id"].split(":")[-1]
    if g.has_edge(f["from_ref"], f["to_ref"]):
        g.edges[f["from_ref"], f["to_ref"]][attr_name] = 1
    else:
        g.add_edge(f["from_ref"], f["to_ref"], **{attr_name: 1})

print(f"\n[{time.time()-start:.1f}s] Graph built: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")

# Load graph + rules + facts into PyReason
pr.reset()
pr.load_graph(g)

# Rules (engine-specific — not through factpy Rule DSL in this demo)
pr.add_rule(pr.Rule(
    "popular(x) <-1 popular(y), strength(x,y), since(y,z), since(x,z)",
    "shared_pet_popularity",
))
pr.add_rule(pr.Rule(
    "outdoorsy(x) <-0 since(x,y), dog_breed(y)",
    "dog_owner_outdoorsy",
))

# Initial facts
pr.add_fact(pr.Fact("popular(Alice)", "alice_popular", 0, 3))
pr.add_fact(pr.Fact("dog_breed(Dog)", "dog_is_dog", 0, 3))

pr.settings.atom_trace = True

print(f"[{time.time()-start:.1f}s] Starting PyReason reasoning...")
interpretation = pr.reason(timesteps=2)
print(f"[{time.time()-start:.1f}s] Reasoning complete")


# ════════════════════════════════════════════════════════════════
# 4. Provenance: Extract trace using adapter-local carrier
# ════════════════════════════════════════════════════════════════

from factpy_kernel.adapters.pyreason.provenance import (
    parse_pyreason_trace,
    pyreason_trace_to_dict,
)

nodes_trace, edges_trace = pr.get_rule_trace(interpretation)
trace = parse_pyreason_trace(nodes_trace, edges_trace, timesteps=2)
trace_dict = pyreason_trace_to_dict(trace)

print(f"\n[{time.time()-start:.1f}s] Provenance extracted:")
print(f"  Engine: {trace_dict['engine']}")
print(f"  Trace type: {trace_dict['trace_type']}")
print(f"  Timesteps: {trace_dict['timesteps']}")
print(f"  Node events: {len(trace_dict['node_events'])}")
print(f"  Edge events: {len(trace_dict['edge_events'])}")


# ════════════════════════════════════════════════════════════════
# 5. Results: Interpretation per timestep
# ════════════════════════════════════════════════════════════════

print(f"\n{'='*60}")
print("INTERPRETATION (state per timestep)")
print(f"{'='*60}")

d = interpretation.get_dict()
for t in sorted(d.keys()):
    print(f"\n  t={t}:")
    for comp, preds in d[t].items():
        for pred_name, (lo, hi) in preds.items():
            status = "TRUE" if lo == 1.0 and hi == 1.0 else f"[{lo},{hi}]"
            print(f"    {comp}.{pred_name} = {status}")


# ════════════════════════════════════════════════════════════════
# 6. Summary
# ════════════════════════════════════════════════════════════════

elapsed = time.time() - start
print(f"\n{'='*60}")
print("INTEGRATION DEMO SUMMARY")
print(f"{'='*60}")
print(f"  Schema: {len(pred_ids)} predicates ({len(rel_preds)} relationship)")
print(f"  Session: {len(session.node_facts)} node + {len(session.edge_facts)} edge facts")
print(f"  Graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
print(f"  Rules: 2 (1 temporal <-1, 1 immediate <-0)")
print(f"  Reasoning: {trace_dict['timesteps']} timesteps")
print(f"  Trace: {len(trace_dict['node_events'])} events")
print(f"  Total time: {elapsed:.1f}s")
print()
print("  Key integration points:")
print("  1. Schema: factpy Relationship type → schema_ir predicates")
print("  2. Session: PyReasonSession validates against shared schema_ir")
print("  3. Confidence: bound=[0.9,0.9] → auto-derived confidence=0.9 for audit")
print("  4. Provenance: PyReasonTraceV0 event log (not proof tree)")
print("  5. Audit: session.all_facts_meta carries shared meta for all facts")
print(f"{'='*60}")

pr.reset()
