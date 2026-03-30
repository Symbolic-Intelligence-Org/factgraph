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

import sys
import time
from pathlib import Path

# Ensure src/ is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from factpy_kernel.sdk import Entity, Identity, Field, Relationship
from factpy_kernel.sdk.compile import compile_schema_from_classes
from factpy_kernel.sdk.dsl.expr import LogicVar, Pred
from factpy_kernel.sdk.dsl.rule import Rule
from factpy_kernel.adapters.pyreason.accept import accept_pyreason_session
from factpy_kernel.adapters.pyreason.runner import PyReasonRunConfig, run_pyreason
from factpy_kernel.adapters.pyreason.rule_ext import (
    PyReasonFactDef,
    PyReasonRuleExt,
)
from factpy_kernel.adapters.pyreason.session import PyReasonSession
from factpy_kernel.core.store.ledger import Ledger

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
# 2. PyReason Session: Write Facts (engine-specific batch path)
# ════════════════════════════════════════════════════════════════

session = PyReasonSession(schema_ir)

with session.batch() as tx:
    alice = tx.entity(User, user_id="Alice")
    bob = tx.entity(User, user_id="Bob")
    dog = tx.entity(Pet, pet_id="Dog")

    # Node facts — entity attributes with interval bounds
    alice.popular.set("true", bound=[1.0, 1.0], meta={"source": "manual_assessment", "analyst": "Admin"})
    alice.name.set("Alice", bound=[1.0, 1.0], meta={"source": "user_profile"})
    bob.name.set("Bob", bound=[1.0, 1.0], meta={"source": "user_profile"})
    dog.species.set("canine", bound=[1.0, 1.0])
    dog.dog_breed.set("labrador", bound=[1.0, 1.0])

    # Edge facts — relationships with interval bounds
    tx.relationship(
        Friends,
        from_entity=alice,
        to_entity=bob,
        strength="0.9",
        bound=[0.9, 0.9],
        meta={"source": "social_network_data"},
    )
    tx.relationship(
        Friends,
        from_entity=bob,
        to_entity=alice,
        strength="0.9",
        bound=[0.9, 0.9],
        meta={"source": "social_network_data"},
    )
    tx.relationship(
        Owns,
        from_entity=alice,
        to_entity=dog,
        since="2024",
        bound=[1.0, 1.0],
        meta={"source": "pet_registry"},
    )
    tx.relationship(
        Owns,
        from_entity=bob,
        to_entity=dog,
        since="2023",
        bound=[1.0, 1.0],
        meta={"source": "pet_registry"},
    )
    tx.commit()

print(f"\n[{time.time()-start:.1f}s] Session facts written:")
print(f"  Node facts: {len(session.node_facts)}")
print(f"  Edge facts: {len(session.edge_facts)}")
print(f"  Audit meta entries: {len(session.all_facts_meta)}")
print(f"  Annotation templates: {len(session.annotation_templates)}")

# Show auto-derived confidence
for entry in session.all_facts_meta[:3]:
    print(f"  {entry['pred_id']} → confidence={entry['meta'].get('confidence')}")


# ════════════════════════════════════════════════════════════════
# 3. PyReason Runner (requires pyreason==3.0.0)
# ════════════════════════════════════════════════════════════════

try:
    x = LogicVar("x")
    y = LogicVar("y")
    z = LogicVar("z")
    run_result = run_pyreason(
        session,
        rule_defs=[
            Rule(
                id="shared_pet_popularity",
                version="1.0",
                select=[Pred("user:popular", x)],
                where=[
                    Pred("user:popular", y),
                    Pred("friends:strength", x, y),
                    Pred("owns:since", y, z),
                    Pred("owns:since", x, z),
                ],
                engine_ext=PyReasonRuleExt(timestep_delay=1),
            ),
            Rule(
                id="dog_owner_outdoorsy",
                version="1.0",
                select=[Pred("user:outdoorsy", x)],
                where=[
                    Pred("owns:since", x, y),
                    Pred("pet:dog_breed", y),
                ],
                engine_ext=PyReasonRuleExt(timestep_delay=0),
            ),
        ],
        fact_defs=[
            PyReasonFactDef(atom="popular(Alice)", name="alice_popular", start=0, end=3),
            PyReasonFactDef(atom="dog_breed(Dog)", name="dog_is_dog", start=0, end=3),
        ],
        config=PyReasonRunConfig(timesteps=2, atom_trace=True),
    )
except Exception as exc:
    print(f"\n[ERROR] pyreason run failed: {exc}")
    print("Expected environment: pyreason==3.0.0 with a working numba cache/runtime.")
    print("Skipping reasoning + provenance. Schema + session demo complete.")
    sys.exit(0)

interpretation = run_result.interpretation
trace_dict = run_result.trace_dict or {}
derived_session = run_result.derived_session

print(f"\n[{time.time()-start:.1f}s] Runner complete:")
print(f"  Derived node facts: {len(derived_session.node_facts)}")
print(f"  Derived edge facts: {len(derived_session.edge_facts)}")
print(f"  Elapsed: {run_result.elapsed_seconds:.1f}s")


# ════════════════════════════════════════════════════════════════
# 4. Provenance: Parsed by runner helper
# ════════════════════════════════════════════════════════════════

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
# 6. Accept: Derived session -> Ledger
# ════════════════════════════════════════════════════════════════

ledger = Ledger()
accept_result = accept_pyreason_session(ledger, derived_session)

print(f"\n[{time.time()-start:.1f}s] Derived facts accepted:")
print(f"  Node assertions: {len(accept_result.node_asrt_ids)}")
print(f"  Edge assertions: {len(accept_result.edge_asrt_ids)}")
print(f"  PyReason annotations: {accept_result.annotation_count}")


# ════════════════════════════════════════════════════════════════
# 7. Summary
# ════════════════════════════════════════════════════════════════

elapsed = time.time() - start
print(f"\n{'='*60}")
print("INTEGRATION DEMO SUMMARY")
print(f"{'='*60}")
print(f"  Schema: {len(pred_ids)} predicates ({len(rel_preds)} relationship)")
print(f"  Session: {len(session.node_facts)} node + {len(session.edge_facts)} edge facts")
print(f"  Derived session: {len(derived_session.node_facts)} node + {len(derived_session.edge_facts)} edge facts")
print(f"  Rules: 2 (1 temporal <-1, 1 immediate <-0)")
print(f"  Reasoning: {trace_dict['timesteps']} timesteps")
print(f"  Trace: {len(trace_dict['node_events'])} events")
print(f"  Accepted annotations: {accept_result.annotation_count}")
print(f"  Total time: {elapsed:.1f}s")
print()
print("  Key integration points:")
print("  1. Schema: factpy Relationship type → schema_ir predicates")
print("  2. Session: entity-level batch API routes fields/relationships into facts")
print("  3. Rules: shared Rule(engine_ext=PyReasonRuleExt(...)) carries timestep_delay")
print("  4. Runner: session -> graph -> reason -> trace -> derived_session")
print("  5. Confidence: bound=[0.9,0.9] → auto-derived confidence=0.9 for audit")
print("  6. Annotations: session.annotation_templates + accept helper persist pyreason semantics")
print("  7. Provenance: PyReasonTraceV0 event log (not proof tree)")
print("  8. Audit: session.all_facts_meta carries shared meta for buffered facts")
print(f"{'='*60}")
