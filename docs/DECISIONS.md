# Engineering Decision Log

Append-only record of significant engineering decisions (an ADR — Architecture
Decision Record — log). Each entry: what we decided, why, and what it rules out.
Newest at the bottom.

---

## ADR-0001 — Motion principle: true syringe (Option B)
**Date:** 2026-07-21
**Status:** Accepted

**Decision.** A single cell moves as a piston inside a fixed tube ("barrel").
- Retracted: the piston sits deep; the open tube ahead of it is the sleeping cavity;
  the piston face is the surface the occupant rests against.
- Advanced: the piston travels to the wall plane; its face becomes the flush public
  wall. No separate door or plug. The cavity now lies behind the piston, on the
  hidden service side, sealed and ready for cleaning.

**Why.** Fewest moving parts (one piston, one actuator) → best score on reliability,
cost, simplicity. Cylindrical bore has no corners → best hygiene and vandal
resistance. Cleaning is intrinsic to the stroke (piston sweeps the bore). One part
serves as both resting surface and flush closure.

**Rejected alternatives.**
- A — Linear shuttle/drawer + separate flush plug: more parts, more seals, plug is
  its own mechanism.
- C — Rotary/carousel swap of two pods: zero downtime but most mechanism and failure
  modes; conflicts with simplicity/reliability priorities.

**Accepted costs / constraints.** Sleeping space is a capsule; stroke is roughly one
body length (~2.1 m target, TBD in M1); installation depth ~4 m front-to-back
(cavity + service chamber). These must be validated against real building envelopes.

---

## Component tree (one cell) — reference for ADR-0001

1. Structure/enclosure: sleeping shell (bore), fixed barrel/frame, wall-interface
   flange & trim, internal ribs, piston (also the closing element).
2. Motion/actuation: linear actuator, guide rails + carriages, actuator-to-piston
   coupling, mechanical hard stops.
3. Sealing/hygiene: perimeter wiper seals, floor slope + drain port, splash gaskets.
4. Sensing/safety/control: position sensors + limit switches, occupancy/obstruction
   sensors, pressure-sensitive safety edge, e-stop + manual release, controller.
5. Services: power, cable carrier (drag chain), interior lighting, water/drain.
6. Cleaning subsystem: deferred; reserve mounting bosses and space claim.
7. User interface: exterior availability indicator, interior grab feature, call button.
