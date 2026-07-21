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

## ADR-0002 — Authoring workflow: code-first FreeCAD scripting
**Date:** 2026-07-21
**Status:** Accepted

**Decision.** The model is authored as git-tracked Python (`scripts/build_model.py`)
run headless via `freecadcmd` (FreeCAD Flatpak). The Python is the source of truth;
`cad/HiveCell.FCStd` is a generated build artifact. The FreeCAD GUI is used only to
view/measure, never to hand-edit geometry (edits would be overwritten on regenerate).

**Why.** User is an experienced software engineer who wanted to move fast and keep
the design in code/version control. FreeCAD's Python API gives full parametric
control (sketches, constraints, pads, spreadsheet) while retaining manufacturing-
grade BREP output, STEP export, the free GUI viewer, and an early motion-preview
path. Beats manual clicking (speed) and OpenSCAD (mesh/CSG, weak STEP).

**Rejected alternatives.**
- Manual GUI modeling: too slow; not diffable.
- CadQuery/build123d: elegant pure-Python BREP, but blocked on this machine by
  Python 3.14 (no OpenCASCADE wheels yet); would need a separate 3.12 env + a viewer
  add-on, and has no motion preview. Revisit later if desired.
- OpenSCAD: not installed; CSG/mesh, poor STEP export -- unfit for "manufacturable".

**Regenerate command.**
`flatpak run --command=freecadcmd org.freecad.FreeCAD scripts/build_model.py`

---

## ADR-0003 — Cross-section: rounded rectangle (capsule), not a cylinder
**Date:** 2026-07-21
**Status:** Accepted (amends the "cylindrical bore" note in ADR-0001)

**Decision.** The living space is a rounded-rectangular capsule (Japanese
capsule-hotel style): a box extruded along +X whose four long edges are rounded
(`cornerRadius`). Ends are flat. The flat back face is the piston that pushes
in/out and seals flush with the exterior wall; the front face is the entry opening.

**Why.** User requirement: a capsule pod is more usable and recognizable than a
round tube, while a flat floor (`floorWidth = cavityWidth - 2*cornerRadius`) gives a
real lying surface. Rounded corners preserve the hygiene/vandal-resistance rationale
(no sharp internal corners); a flat back is required so the piston can seal flush.

**Parameter change.** Replaced `boreDiameter` with `cavityWidth` (1000), reused
`interiorHeight` (950) as capsule height, added `cornerRadius` (125). `floorWidth`
is now derived and checked to exceed `shoulderP95`.

---

## ADR-0004 — Capsule shell = fixed barrel, an open-ended sleeve
**Date:** 2026-07-21
**Status:** Accepted

**Decision.** The `CapsuleShell` is the fixed barrel: a rounded-rectangular sleeve
of uniform `wallThickness`, shelled OUTWARD from the keep-out envelope (inner surface
= envelope; outer corner R = inner R + t). It is open at BOTH ends -- front (X=0) =
public opening / piston seal plane; back (deep) = service side. The flat back wall the
occupant perceives is the PISTON (a separate part, next milestone), not the shell.

**Why.** Shelling outward keeps the human envelope sacred. An open-ended sleeve is the
true syringe barrel and keeps each part independently manufacturable. Uniform wall
(concentric corners) eases fabrication and stress. Built as a boolean cut of two
rounded boxes and baked as a Part::Feature (Python is the source of truth, ADR-0002).

**Placeholders.** `wallThickness` 6 mm is structural TBD (vandal/load analysis).
`barrelLength` = `cavityLength` for now; must extend deeper to house the retracted
piston + actuator once the piston is sized (M4).

---

## ADR-0005 — Piston: the single moving part
**Date:** 2026-07-21
**Status:** Accepted

**Decision.** The `Piston` is a rounded-rectangular plug riding in the bore with a
`runningClearance` (3 mm/side), so cross-section = bore minus 2*clearance and
pistonR = cornerRadius - clearance. `pistonLength` = 300 mm. Modeled at the DEPLOYED
position: flat front face at X=cavityLength (the occupant's back wall), body extending
to X=cavityLength+pistonLength. Its front face becomes the flush exterior wall when
closed. Consequently `barrelLength = cavityLength + pistonLength`.

**Why.** A running fit prevents binding; wiper seals (later) bridge the 3 mm gap and
squeegee the bore, separating public/service sides. Piston depth resists tilt/jam.
Modeling in the deployed pose means the whole mechanism's motion is ONE part
translating -X by `stroke` -- ideal for the Godot digital twin.

**Placeholders.** Solid plug now; lightweighting (ribs / shelled face) and seal
grooves are later milestones. `pistonLength` and `runningClearance` are tunable.

---

## ADR-0006 — CAD -> Godot export conventions
**Date:** 2026-07-21
**Status:** Accepted

**Decision.** `scripts/export_godot.py` writes one OBJ per part to `godot/models/`
plus `hivecell.json` (stroke, timings). Every mesh is baked to Godot space at export:
scale x0.001 (mm->m) and rotate -90 deg about X (FreeCAD Z-up -> Godot Y-up), i.e.
(x,y,z) -> (x, z, -y). The +X motion axis is preserved, so retraction is a single
-X translation of the Piston node. Godot digital twin lives in `godot/` (Godot 4).

**Why.** Baking units + axis at export means Godot needs no per-import fiddling and
parts keep correct relative positions. One mesh per part keeps the piston an
independent, animatable node. The JSON manifest keeps the twin in sync with the
parametric model instead of hardcoding dimensions.

**Rule.** Any new part added to the model must be added to `PARTS` in export_godot.py
and (if it moves) wired in the Godot scene.

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
