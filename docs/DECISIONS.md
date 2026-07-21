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

## ADR-0007 — Drive: central electric linear actuator; bore-as-guide (no external rails)
**Date:** 2026-07-21
**Status:** Accepted

**Decision.** A single central electric linear actuator (self-locking lead/ball
screw preferred) behind the piston in the service area drives the stroke. The rod
is RIGID and fixed-length: it is attached to the piston, TRANSLATES with it, and
telescopes into the fixed housing (it never changes length). Guidance is NOT
external rails but the "syringe" scheme: (1) the bore guides the piston laterally at
the front via wear rings; (2) the non-circular section prevents rotation for free;
(3) the actuator supports the rear. Representative geometry: rod 70 mm dia; housing
160 mm dia x (stroke + 150) = 2350 mm.

**Depth consequence (important).** A rigid push-rod over the full 2.2 m stroke needs
~one stroke of depth behind it to retract into, so total install depth behind the
wall = **4.91 m**. RESOLVED in ADR-0008: a rigid-chain actuator was chosen instead,
cutting depth to 2.86 m.

**Why external rails were rejected.** Linear rails run alongside the travel, outside
the part; connecting them to a piston inside a sealed bore needs a longitudinal SLOT
through the barrel wall -> breaks the seal and hygiene barrier. The syringe topology
forbids it, and provides guidance intrinsically instead.

**First-order sizing (scripts/actuator_sizing.py; assumptions flagged there).**
- piston mass SOLID = 2579 kg -> the model demands lightweighting; ~160 kg as a 6 mm
  shell. Real piston = face plate + ribs (future milestone).
- seal drag dominates: 595 N of 611 N resistive (seals are the thing to engineer).
- design force ~1221 N (x2 SF) -> a modest electric cylinder.
- speed 3.67 mm/s; power ~4.5 W elec; energy 0.75 Wh per stroke (negligible).

**Type choice.** Electric screw over hydraulic/pneumatic: no fluid/compressor
(hygiene, maintenance), self-locking holds the flush piston with zero power and
resists a vandal push (priorities #1/#3/#5).

**Placeholders.** Actuator geometry is representative (space claim), not a selected
unit. Seal drag is the biggest unknown -> validate by test.

---

## ADR-0008 — Actuator architecture: rigid-chain ("zip-chain"), not telescoping rod
**Date:** 2026-07-21
**Status:** Accepted (supersedes the telescoping-rod depth in ADR-0007)

**Decision.** Drive the piston with a rigid-chain actuator: a chain whose links lock
straight to PUSH and bend to coil into a compact flat magazine (no long retract tube).
Parts: `ChainMagazine` (fixed, 300 deep x 650 sq) + `ChainColumn` (the exposed rigid
column; variable length -- physically correct, chain feeds from the coil).

**Why.** Cuts install depth from 4.91 m (rigid rod) to **2.86 m** -- a wall of cells
can't afford ~5 m of back-of-house per unit. Rigid chain is proven (stage lifts /
Serapid). Trade: a more complex drive than a plain screw (mild hit to
simplicity/reliability), accepted for the space saving.

**Twin note.** `ChainColumn` is procedural with a variable length -- correct here
because chain length is conserved (column + coil = const), unlike a solid rod. The
earlier stretching *rod* was wrong; a stretching *chain column* is right.

**Placeholders.** Chain cross-section, magazine size are representative; real sizing
(link geometry, coil radius, drive sprocket, motor) TBD. Force numbers from ADR-0007
hold (~1.2 kN design; seal drag dominates). Validated headless on Godot 4.7.1.

---

## ADR-0009 — SF4 as a fail-open drive + passive flush latch (no occupant release)
**Date:** 2026-07-21
**Status:** Accepted

**Context.** H7 (trapped under self-locking hold) and the SAFETY.md FMEA row F3: if
SF1 mis-detects an occupant and power is lost mid-contact, a self-locking drive holds
a sustained pin with no powered reverse — Severity 4, and nothing can act once power
is gone. Separately, a firm requirement: once fully closed (flush), the pod must STAY
closed without power (security / vandal resistance + zero standby energy).

**Decision.** SF4 is a property of the drivetrain, not an occupant-operated device.
1. **No interior manual release or E-stop.** The geometry already removes the
   sealed-in trap: the occupant is always mouth-side of the piston, so a stopped sweep
   leaves an OPEN pod they can exit (FMEA F4/F5). An accessible release is only a
   vandalism/abuse surface (F7).
2. **Fail-open in the occupant zone.** Through the closing stroke where an occupant
   could be, loss of power must NOT sustain a holding force — the output is
   back-drivable / releases, so a pin relieves passively (F3).
3. **Passive flush latch for "stay closed without power."** A spring / over-center
   latch holds the piston at the fully-closed (flush) end with zero power, engaging
   ONLY in the final travel where the cavity is closed to flush and no occupant can be
   present. A powered solenoid releases it at cycle start to re-open. Deployed (in-use)
   rest is held by a mechanical hard stop.

   => Fail behavior is **position-dependent**: back-drivable in the occupant zone,
   latched only at flush. That is what reconciles "release to free a pin" with "stay
   closed without power" — they apply in different, non-overlapping places.

**Why.** Turns SF4 into a drivetrain property with nothing to touch or break. The
flush latch also *improves* vandal resistance (a closed pod can't be pushed open) and
needs no standby power. No occupant can be pinned where the latch holds (flush), so
holding-without-power there is safe.

**Rejected alternatives.**
- Occupant-operated manual release + interior E-stop: vandalism/abuse surface;
  unnecessary given the geometry (FMEA F7).
- Self-locking chain holds everywhere without power: simplest, satisfies "stay
  closed", but sustains a pin on power loss (F3). Rejected.
- Motor-side declutch on power loss: does NOT work — the rigid chain's self-lock is
  intrinsic and downstream of the motor, so it would still hold the pin. Pin relief
  must come from a back-drivable OUTPUT, not a motor clutch.
- Fully back-drivable + powered brake to hold closed: a powered / fail-applied brake
  either needs standby power or re-creates the held-pin problem. Rejected in favour of
  the passive flush latch.

**Accepted costs / constraints / to verify.**
- Gives up the zip-chain's zero-power holding mid-stroke and at deployed; holding
  during operation is by a powered brake + end stops, at-rest-closed by the latch.
- Adds the flush latch as a new part: must be reliable and self-tested; its powered
  release must fail safe (release fails -> pod stays closed -> safe, since no occupant
  can be inside a flush pod; an availability cost only).
- **KEY RISK — seal drag vs. passive relief.** SF3 seal drag (~1.2 kN, ADR-0007) is a
  friction force a back-drivable output must overcome to relieve a pin. If a pinned
  occupant's elastic reaction is below seal drag, back-drivability ALONE will not
  relieve the pin. Verify by analysis/test; if it can't, add a stored-energy return
  element (spring / gas strut / counterbalance) biasing toward deployed in the
  occupant zone, held off by the flush latch at the closed end.
- Verify the rigid-chain actuator is genuinely back-drivable in the occupant zone
  (link/tooth geometry); if not, an output-side release clutch is required there.
- The latch engagement zone must be provably past any occupant presence (final flush
  mm only); the SF2 safety edge covers the final-approach pinch (H8).
- Supersedes the tentative options (a)/(b) sketched in SAFETY.md's FMEA note.

**Follow-ups.** Model the latch + back-drive path in CAD once the mechanism is chosen.

---

## Component tree (one cell) — reference for ADR-0001

1. Structure/enclosure: sleeping shell (bore), fixed barrel/frame, wall-interface
   flange & trim, internal ribs, piston (also the closing element).
2. Motion/actuation: linear actuator, guide rails + carriages, actuator-to-piston
   coupling, mechanical hard stops.
3. Sealing/hygiene: perimeter wiper seals, floor slope + drain port, splash gaskets.
4. Sensing/safety/control: position sensors + limit switches, occupancy/obstruction
   sensors, pressure-sensitive safety edge, external/operator e-stop + passive flush
   latch (NO interior release, ADR-0009), controller.
5. Services: power, cable carrier (drag chain), interior lighting, water/drain.
6. Cleaning subsystem: deferred; reserve mounting bosses and space claim.
7. User interface: exterior availability indicator, interior grab feature, call button.
