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
**Status:** Accepted — but **challenged by ADR-0010 (proposed)**: SF4 (ADR-0009) wants
a back-drivable drive, which negates rigid-chain's self-locking advantage. See ADR-0010.

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
- **Seal drag vs. passive relief — CHECKED (`scripts/pin_relief.py`, first-order).**
  Back-drive stalls when the tissue reaction equals the seal drag, so the residual pin
  floors at the resisting force ~1.2 kN — about **12x** a safe sustained contact force
  (100 N, ADR-0024). **Passive relief alone is INSUFFICIENT.** Therefore a stored-energy
  return element (~1.5 kN spring / gas strut biasing toward deployed, held off by the
  flush latch at close) is **required** to unload the occupant — at a cost of ~2.3x the
  closing design force (2411 -> ~5546 N). Reducing seal drag enough (<=~10.6 N/m, a >14x
  cut) is not credible for a lip seal. Alternative worth exploring: a seal that sheds
  its drag on power loss (relaxes / retracts) so passive back-drive suffices. Confirm
  with real tissue + seal-drag data before freezing.
- Verify the rigid-chain actuator is genuinely back-drivable in the occupant zone
  (link/tooth geometry); if not, an output-side release clutch is required there.
- The latch engagement zone must be provably past any occupant presence (final flush
  mm only); the SF2 safety edge covers the final-approach pinch (H8).
- Supersedes the tentative options (a)/(b) sketched in SAFETY.md's FMEA note.

**Follow-ups.** Add the return element (~1.5 kN) to the drive concept and re-run
actuator sizing with the higher closing force; or investigate a power-loss
drag-shedding seal as an alternative. Model the latch + back-drive path in CAD once
the mechanism is chosen. Confirm the pin-relief numbers with real tissue/seal data.

---

## ADR-0010 — Actuator: single-acting tension-close + spring-open (supersedes ADR-0008)
**Date:** 2026-07-21
**Status:** Proposed (supersedes ADR-0008 if accepted). **Architecture de-risked
against the seal-drag unknown (2026-07-23, `scripts/seal_drag_sweep.py`): the
number sets the *sizing*, not the *choice* — see "Sensitivity" below.**

**Context.** ADR-0008 chose rigid-chain for three reasons: shallow install depth,
self-locking hold without power, and compactness. Two later decisions moved the goal
posts:
- **ADR-0009 (SF4)** requires the drive to be BACK-DRIVABLE in the occupant zone (fail
  open on power loss so a pin relieves), and moved holding-closed to a passive flush
  latch. So self-locking is now a *liability*, and the drive need not self-lock at all.
- **`pin_relief.py`** showed passive relief needs a ~1.5 kN stored-energy RETURN
  element biasing toward deployed. Sizing (`actuator_sizing.py`) shows that spring
  already drives the whole opening stroke (opening resist -362 N) -- i.e. a full-stroke
  deploy actuator now exists for safety reasons regardless of the drive choice.

Net: rigid-chain's self-locking advantage is gone (unwanted); only shallow depth
remains, which other architectures also achieve.

**Decision (proposed).** A SINGLE-ACTING drive: a tension member (toothed chain/belt
or cable) that only PULLS the piston closed, with the SF4 return spring PUSHING it
open.
- Closing: a powered drum/sprocket winds the tension member in, fighting seal drag +
  the return spring (~5.5 kN design, `actuator_sizing.py`).
- Deploy: the return spring drives the piston out; the drive brakes/controls a damped
  descent.
- Holding: passive flush latch (closed) + hard stop (deployed); powered tension holds
  mid-cycle.

**Why.**
- **Fail-open by nature (ADR-0009).** A tension member cannot push. On power loss it
  goes slack and the spring deploys the piston, relieving a pin -- no clutch, no
  self-lock to defeat. Checked: 1567 N spring vs 1206 N resist => net +361 N, unloads
  to zero contact.
- **Reuses the mandatory SF4 spring as the opener** -- the safety element and the
  deploy actuator are the same part (fewer parts, not more).
- **Shallow install depth** -- a drum/sprocket is as compact as the chain magazine, so
  rigid-chain's one surviving advantage is retained.
- **Simple / cheap / robust** -- chain-in-tension + drum is well-understood tech vs. a
  niche rigid chain.

**Rejected alternatives.**
- Rigid-chain (ADR-0008): self-locking is now unwanted (must be forced back-drivable or
  given an output clutch); its holding advantage is superseded by the flush latch. Only
  shallow depth remains, which this option also achieves.
- Ball / lead screw + motor: retract length ~ full stroke => deep install (what
  ADR-0008 avoided); strongly self-locking (wrong way for fail-open).
- Hydraulic cylinder: fail-open is easy (dump valve) but needs a stroke-length barrel
  (deep) and adds fluid/leak/freeze/hygiene problems for an outdoor unattended unit.
- Double-acting rigid drive + separate safety spring: more parts than folding the
  deploy into the mandatory spring.

**Accepted costs / constraints / to verify.**
- Softer position control on a tension drive (cable stretch). Mitigate with a toothed
  chain/belt (positive engagement); end stops + latch define the travel ends, and
  mid-stroke precision is not critical for this slow motion.
- The return spring stores ~3.4 kJ over the 2.2 m stroke (1567 N x stroke). Deploy MUST
  be damped -- the piston cannot slam open. Size a damper; a gas strut gives spring +
  damping in one.
- Single-acting: if the spring fails, the pod won't deploy -> stuck CLOSED. Fails safe
  (no occupant can be in a flush pod) but is an availability cost; the spring becomes a
  reliability-critical item (inspect/monitor).
- Closing design force ~5.5 kN on the winch/sprocket (x2 factor) -- verify the
  drum/motor/gearing and the tension member rating.
- Verify the drum freewheels/back-drives on power loss (not self-locking; a
  fail-released brake, not a fail-applied one).

**Sensitivity to seal drag (2026-07-23, `scripts/seal_drag_sweep.py`).** Seal drag is
the master unknown (~16–700 N/m; SF3/ADR-0011). Sweeping it through the same force
model as `actuator_sizing.py` / `pin_relief.py` shows the *architecture* is robust and
only the *sizing* moves:
- **Passive fail-open relief is safe only below ~13 N/m**, and the credible range
  *starts* at ~16 — so the SF4 return spring is mandatory across essentially the whole
  range. ADR-0009 isn't marginal, and ADR-0010's premise (reuse that mandatory
  full-stroke spring as the opener) holds nearly everywhere.
- **This decision therefore does not hinge on the measurement.** The measured number
  sets the *size*: design force swings ~60× (437 N at 10 N/m → ~25.6 kN at 700 N/m),
  spring energy 0.3 → 16 kJ. Spring-open + tension-close stays the right shape.
- **Rework trigger: ~300 N/m.** Above it, forces are 2–4× the model and the design must
  change (cut interference, drop to one lip, or change seal tech) rather than just
  resize the drive. So the bench test is also a go/no-go on the 2-lip / 3 mm design.
Practical read: accept ADR-0010's architecture now; leave the drum/motor/spring/damper
*sizing* open until the bench test (`docs/seal_drag_bench_test.md`) returns a number,
then read it against the sweep table.

**Follow-ups (if accepted).** CAD: replace ChainMagazine/ChainColumn with a drum +
tension member + return spring + flush latch; re-export to the twin. Update the
component tree. Add a damper spec. Re-confirm force/energy with the real spring rate.

---

## ADR-0011 — Specify a low-friction seal (seal drag is the master design lever)
**Date:** 2026-07-21
**Status:** Accepted

**Context.** Seal drag is the dominant load and, via `pin_relief.py`, sets the SF4
residual-pin floor (passive relief stalls when tissue reaction == seal drag). It
therefore couples SF3 (the seal), SF4 (return spring / fail-open) and the actuator
size. `seal_drag.py` (first principles, researched dry rubber-steel mu ~1.0-1.4) puts
the credible range at ~16-700 N/m; the 150 N/m working assumption is a mid value, and
a dry gritty street lip trends toward the HIGH end.

**Decision.** Make LOW seal friction a hard requirement for SF3: specify a low-friction
wiper (PTFE-faced / lubricated / brush), minimise lip count and interference, and
MEASURE the drag on a real sample before freezing any force numbers.

**Why (quantified, `SEAL_DRAG_PER_M` = 40 vs 150 N/m).**

| metric | 150 N/m (dry lip) | 40 N/m (low-friction) |
|--------|-------------------|-----------------------|
| resisting force | 1206 N | 333 N |
| passive residual pin | 1206 N (~10x safe) | 333 N (~3x safe) |
| SF4 return spring | 1567 N | 433 N |
| closing design force | 5546 N | 1532 N |

Everything scales ~3.6x down. The spring's stored energy (the deploy-slam hazard)
falls with it (~3.4 kJ -> ~0.95 kJ), easing the damper. Low friction does NOT remove
the spring (passive-only-safe needs <=~13 N/m, i.e. near-frictionless), but it shrinks
the whole SF4 + actuator apparatus from heavy to modest.

**Rejected / not chosen.**
- Aggressive dry elastomer lip (best wiping/hygiene): trends to the high end of the
  drag range -> huge actuator + spring. Rejected as the primary sealing approach.

**Accepted costs / to verify.**
- A low-friction (PTFE / lubricated / brush) wiper may scrape LESS aggressively --
  check hygiene + grit exclusion; may need a two-stage soft-scraper + low-friction
  seal, with the drag budget counting both stages.
- Lubrication in an unattended street unit: dry-film / grease retention, contamination.
- MEASURE drag on a real sample (dry, with grit). This one number gates the actuator,
  the SF4 spring, and whether ADR-0010's drive complexity is even warranted.

**Follow-ups.** Once measured, re-run `pin_relief.py` / `actuator_sizing.py`
(`SEAL_DRAG_PER_M=<n>`) and revisit ADR-0010 -- a small spring + light actuator may
simplify the drive choice.

---

## ADR-0012 — SF1 occupancy sensing: diverse-redundant, fail-safe, PL e
**Date:** 2026-07-22
**Status:** Accepted (architecture + PL target); sensor part numbers + certification TBD

**Context.** SF1 (occupancy detection) is the PRIMARY safeguard -- PREVENT: never move
while occupied (H1/H6); the whole safety case leans on it. Users are assumed VULNERABLE
and may NOT self-rescue, so a missed occupant can be fatal. The twin has fail-safe
*voting logic* (`safety_interlock.gd`) but no physical sensor suite, redundancy
architecture, or performance level. This ADR fixes those.

**Decision.**
1. **Target ISO 13849-1 PL e, Category 3-4.** Risk graph: S2 (death) + F2 (occupant
   present for hours) + P2 (vulnerable, scarcely able to avoid) => PLr = **e**. The
   safety function "presence detected => motion inhibited" runs on a rated safety
   controller (dual-channel / safety PLC), not the ordinary control MCU.
2. **Diverse-redundant sensor suite** (different physics, so no single common-cause
   failure can blind it):
   - **A. mmWave / UWB vital-sign radar (primary)** -- respiration + heartbeat
     micro-motion on a MOTIONLESS person; penetrates clothing / blanket / sleeping bag.
     Catches the still, cold, covered occupant the others miss (e.g. 60 GHz FMCW).
   - **B. Thermal IR array** -- body-heat signature/shape. Supportive; weak on a
     hypothermic occupant, so never sole.
   - **C. NDIR CO2** -- exhaled-CO2 rise = metabolism. Independent physics,
     penetration-independent (works under a blanket), slow.
   - **D. Floor load cells + ballistocardiography** -- static mass = something present;
     micro weight-shifts from pulse/breathing = alive. Threshold low enough for a small
     animal.
   - (Optional E: mouth-plane light-curtain / ToF for external reach-in during motion,
     H5.)
3. **Fail-safe voting** (matches the sim reference):
   - **OR toward life** -- ANY credible presence/life channel => occupied => inhibit.
   - **AND toward clear** -- motion only when ALL channels agree "empty" for a dwell
     (covers breath-hold / apnea).
   - **Fault = occupied** -- any channel faulted, stale, out-of-range, or disagreeing
     beyond tolerance => occupied. Absence of proof of emptiness is never "empty".
   - **Diversity for common cause** -- RF + IR + chemical + mechanical fail differently
     (dust/fog blinds optical but not radar/CO2/load).
4. **Must catch a small animal, not just an adult** -- radar/CO2/load thresholds tuned
   down; ambiguity (mass with no life signs) errs to possibly-occupied => hold.

**Why.** No single sensor sees the worst case (motionless, cold, blanketed, maybe a
small animal). Diverse redundancy + OR-toward-life + fault-is-occupied is the only way
to reach PL e for a may-not-self-rescue occupant. The sim already encodes the LOGIC;
this ADR fixes the PHYSICS and the RATING.

**Rejected alternatives.**
- Single sensor (PIR or a weight mat alone): common-cause blind spots -- a motionless
  person defeats PIR, a bag fools weight-only. Cannot reach PL e.
- Camera + vision AI as the primary channel: opaque failure modes, privacy (people
  sleeping), poor in dark / under a blanket, hard to certify to PL e. At most auxiliary.
- "Possibly occupied => push out slowly": ruled out project-wide (SAFETY.md).

**Accepted costs / to verify.**
- Cost/complexity of 4 diverse channels + a rated safety controller -- justified by
  S4 / PL e.
- Validate radar vital-sign range/reliability through bedding, multi-occupant and
  small-animal sensitivity, on real hardware.
- Sensor placement / field-of-view: no dead zones in the bore; radar EMC in a metal bore.
- Privacy: prefer non-imaging sensors (radar / CO2 / load / thermal-array) over cameras.
- Formal PL e verification (category, MTTFd, DC, CCF per ISO 13849-1) once parts chosen.
- Dwell time vs. apnea / breath-hold: set from clinical data.

**Modelled (2026-07-23).** The diverse-redundant voting is now a real module,
`godot/occupancy_fusion.gd` (four channels: radar vitals / thermal / NDIR CO2 /
load-BCG), replacing the stub OR in `safety_interlock.gd` (which now consults the
fusion when attached). It encodes the three fail-safe rules — OR-toward-life,
fault=occupied (unhealthy / out-of-range / stale), AND-toward-clear — and a runtime
`self_test()`. The headless test `godot/tests/test_occupancy_fusion.gd` fault-injects
each channel/mode, checks the diversity cases (hypothermic-covered occupant; static
mass with no life signs; fully blinded suite), and exhaustively verifies the invariant
across all 3⁴ vote combinations: "empty" only when **every** channel positively reads
clear. This is `[sim]` — logic + rating, still no physical sensors.

**Follow-ups.** Choose sensor part numbers; optionally surface the per-channel votes in
the visual twin (`physics_demo`); build the PL e verification dossier (category, MTTFd,
DC, CCF per ISO 13849-1) once parts are chosen.

---

## ADR-0013 — Sitting-height mouth: accept single-layer fall protection (H4)
**Date:** 2026-07-22
**Status:** Accepted (risk acceptance — needs a named sign-off at commissioning)

**Context.** H4 = fall from an elevated mouth. The prior siting rule was "mouth at floor
level, or guard it", so a person swept toward the mouth in an SF1 fault cannot also
fall. But a floor-level sill lets ejected inanimate items pile right at the opening
(bad for the clearing function + hygiene). A sitting-height sill (~450–500 mm) makes
ejected items fall *clear*, and suits sit-and-swing entry.

**Decision.** Set the mouth sill at ~sitting height (~450–500 mm). Accept that this
removes the floor-level fall protection: H4 fall protection now rests SOLELY on SF1
(never move while occupied) — a deliberate single-layer choice for this one hazard.

**Why accepted.**
- SF1 is diverse-redundant, fail-safe, PL e (ADR-0012) with the independent SF2 contact
  backstop, so a push-out needs several independent failures (low probability).
- The residual fall is low — ~450–500 mm, roughly a high step, not a fall from height
  (H4 is S3, not S4).
- Real function benefit: items fall clear instead of jamming the sill; better hygiene;
  natural entry.
- Physical reality: any edge debris falls off, a limp person could fall off too — a
  floor-level sill was the only way to get BOTH object-clearing and no drop. We chose
  object-clearing.

**Rejected alternatives.**
- Floor-level sill + walkable grated recess / catch tray: keeps the H4 layer AND
  object-clearing (debris drops through a grate; a person is supported). The safer
  option; not chosen, in favour of the simpler sitting-height opening.
- Sitting sill + same-level guarded landing + person-excluding grate: preserves the
  layer but more complex; not chosen.

**Accepted costs / constraints (bounds on the trade).**
- Fall protection is now SINGLE-LAYER (SF1) — a conscious exception to the project's
  "never the sole defense" principle, logged not overlooked.
- The accepted drop is ~500 mm ONLY: do not stack cells so a mouth opens over a real
  drop; upper tiers still need a same-level access gallery.
- Require a forgiving, non-slip drop-zone + collection tray below/in front of the mouth.
- Needs a NAMED risk-acceptance sign-off at commissioning; confirm sill height +
  drop-zone against local building code.
- Validate the ~500 mm residual against human-factors data for a NON-REACTING person (a
  limp fall differs from a stumble) — the one soft number in this trade.

**Follow-ups.** SAFETY.md Siting rules + H4 row carry this; obtain the sign-off; HF check
on the limp-fall residual.

---

## ADR-0014 — Interior lighting: warm, blue-depleted, occupancy-staged, top status
**Date:** 2026-07-23
**Status:** Accepted

**Context.** The cell needs interior light to (a) let a user orient on entry and while
inside, and (b) show status — without (c) preventing sleep. The users are vulnerable
(asleep / intoxicated / unwell) and can't self-rescue, inside a sealed steel cavity.
Fixed constraints: vandal resistance, hygiene (must survive the cleaning sweep +
washdown), low energy, and NO interior user-accessible controls (ADR-0009). The three
jobs pull against each other — light-to-see vs dark-to-sleep vs be-noticeable.

**Decision.** A single warm, blue-depleted (≤2200 K / amber), flicker-free luminaire,
recessed FLUSH into the crown (top) of the fixed barrel and running along the bore.
Levels are occupancy-staged off SF1: on entry a brief orientation level (~20–50 lx),
then a settled night-glow (~1–5 lx) held for the whole stay. The luminaire *is* the
interior status indicator, by colour, but only while the pod is EMPTY — available =
green, in-movement = red; the instant it is occupied it holds warm amber. An always-lit
warm line marks the mouth threshold (egress) whenever occupied. "Closed" is not shown
inside (self-evident once the piston face is the exterior wall).

**Why.**
- **Top / crown mount:** a lying body or bedding can't cover it, and the piston's top
  wiper cleans it every sweep. Flush → no gap that would raise seal drag (SF3 / ADR-0011).
- **Warm + blue-depleted + very low lux at rest:** minimal melanopic (melatonin) load,
  so it doesn't block sleep. A large diffuse strip = low *luminance* → no glare even
  though it is overhead (luminance dazzles, not lumens).
- **Colour status only while empty:** green/red never fall on a sleeper; the occupancy
  state itself switches the fixture from "signal" to "warm glow".
- **Night-glow + egress marker are SAFETY, not comfort:** a pitch-black sealed steel box
  for an intoxicated/unwell person invites panic, hides whether they have been sick, and
  buries the only exit — the same non-self-rescue logic that drives SF1/SF2.
- **Interior placement** keeps it cleaned by the sweep and is separate from the external
  **SF5 beacon** (which still warns the PUBLIC face before motion) — two audiences.

**Rejected alternatives.**
- Floor / side mount: coverable by a body or bedding; not cleaned by the top wiper.
- Fixed brightness: cannot satisfy see-on-entry AND sleep at once.
- Cool/neutral white, or a bright status colour while occupied: melatonin suppression +
  glare on the sleeper.
- Occupant dimmer / any interior control: a tamperable, hygiene-trapping actuable that
  conflicts with ADR-0009 (no interior release/controls). Staged auto-levels instead.

**Accepted costs / constraints.**
- Small standby energy for the always-on night-glow (bounded: one low-output warm LED
  strip, order a few hundred mW).
- The diffuser must survive repeated wiper contact + washdown — sealed, impact-resistant,
  flush; a defined maintenance item.
- Spectral/level targets (≤2200 K; ~1–5 lx rest, ~20–50 lx entry; melanopic EDI TBV) are
  first-pass — validate against sleep/circadian + wayfinding human-factors data.
- Flicker-free (no visible temporal light modulation): DC / constant-current drive.

**Follow-ups.** SAFETY.md carries the night-glow + egress marker as occupant protection
for non-self-rescue. CAD adds a flush crown `Luminaire` part (build_model.py); the twin
and the render show the state→colour + warm glow. Confirm melanopic EDI + lux targets
with a photometric spec.

---

## ADR-0015 — Cleaning: motion-driven wash-in-transit + thermal-chemical sanitize, plumbed
**Date:** 2026-07-27
**Status:** Accepted (architecture + method); part selection, sizing, sewer-discharge
compliance and freeze design TBD. Specifies the deferred component-tree item 6.
**Revised by ADR-0016** — the exterior mouth rinse bar + drop tray (points 4 / 5a) and the
internal FloorDrain are removed for vandal resistance; everything exits the mouth to a
flush pavement trench drain instead.

**Context.** Until now "cleaning" was only the piston's dry wiper sweep (ADR-0001):
mechanically squeegee the bore and eject loose solids out the mouth. The real cleaning
subsystem was deferred ("reserve mounting bosses and space claim"). Users are assumed
intoxicated / unwell / vulnerable, so the design case is **bodily fluids every cycle**,
not dust — a dry wiper cannot sanitize, cannot remove fluid films, and just smears
biofilm. Two topology facts drive the whole design:
1. The **piston face** is both the occupant's backrest AND the flush public wall
   (ADR-0001). It is public-side when closed (street grime, graffiti, ejected splatter)
   and interior when open — it swaps a contaminated exterior surface straight onto the
   next sleeper.
2. The **mouth sill / bottom lip** catches everything swept out (ADR-0013 drop tray).
Both are on the **public** side and are **never inside a sealed chamber**, so a flooded
"seal the service side and wash the box" CIP reaches the bore walls but never the two
dirtiest surfaces. Siting assumption (new): the unit is plumbed to **city mains water +
sewer**, so wet wash + drain is available (vs a self-contained tank).

**Decision.** Design for the worst case (fluids every cycle) with a **motion-driven
"wash-in-transit"** subsystem — fixed cleaning stations the piston sweeps *past*, using
its own stroke as the motion — not a flooded CIP box. Sanitize is **thermal + chemical**.
1. **Debris (existing).** The closing sweep ejects big items out the mouth to the tray,
   so interior residual is **liquids + fines only → no macerator** on the drain.
2. **In-bore wash / squeegee ring (fixed station).** The piston face and bore walls pass
   through it every stroke: pre-rinse → dosed detergent → **82–90 °C hot-water/steam
   sanitize** → **metered chemical disinfectant** → full-perimeter squeegee. Runoff to a
   sloped floor + drain port → sewer.
3. **Thermal + chemical sanitize.** Hot water/steam covers most pathogens; a **metered
   disinfectant dose** closes the spore gap (*C. diff* / norovirus) that thermal alone
   misses — justified by the every-cycle vulnerable-user case. Chemical is a refill
   consumable.
4. **Mouth rinse bar + flushed sloped tray.** A rinse bar at the mouth lip washes the
   sill; the ADR-0013 drop tray becomes a sloped, flushed catch basin → same sewer line.
5. **Pre-present purge + dry choreography (on open, before the next guest):**
   a. **Crack open** ~a piston-width; the rinse bar cleans the exposed exterior
      face-edge + mouth.
   b. **Close** to squeegee/push it all out over the sill into the tray → drain
      (repeat 1–2× as agitation).
   c. **Open a second time with a drying dwell** — pause partly open at a drying station
      (warm-air knife + the squeegee ring) to dry the face and near-bore, **then** open
      fully. Presents the cell **clean and dry**.
   The deep clean happens on the previous guest's **close**; the purge + dry-dwell happen
   on **open**, so the face is cleaned *on the way in, every time* and street grime picked
   up while closed can never reach an occupant. The small aperture + immediate squeegee-out
   make the purge **self-containing** — no wet cell is ever fully exposed to the street.

**Why.**
- **Worst-case fluids demand wet wash + sanitize + dry.** A dry sweep can't do any of the
  three; this is priority #2 (hygiene) for a non-self-rescue user.
- **Wash-in-transit reaches what a sealed CIP can't** — the piston face and near-mouth
  band — by reusing the existing stroke. Few added parts (fixed nozzles, squeegee ring,
  rinse bar) keeps faith with simplicity/reliability/cost.
- **The purge cleans the two public-side surfaces right before presenting**, and is
  contained by choreography rather than by adding a shroud.
- **Thermal + chemical** — heat is cheap and logistics-free and kills most pathogens; the
  chemical dose covers spores for the worst case. Plumbed mains+sewer makes both viable.

**Rejected alternatives.**
- **Pyrolytic burn-to-ash (self-cleaning-oven, ~480 °C):** heats a ~2 m steel bore every
  cycle (kills priority #5/#7); destroys the wiper seals, crown luminaire (ADR-0014) and
  the radar/thermal/CO2/load occupancy sensors (ADR-0012); thermally warps the 3 mm
  running fit; emits smoke/VOCs on a public street; and the heat-up/cool-down wrecks
  turnaround. Heat is retained only as **thermal sanitization (≤~90 °C)**, never
  incineration.
- **Flooded sealed-chamber CIP only:** cannot reach the piston face or the mouth sill.
- **Dry mechanical sweep only (status quo):** no sanitize; smears fluids/biofilm.
- **Waterless (UV-C / consumable liner) only:** UV-C is line-of-sight (shadowed by soil),
  degrades seals/diffuser, and removes no fluid; liners need restocking (not unattended).
  UV-C survives only as an optional dry finisher.
- **Interior macerator:** unneeded once the sweep ejects big items first.
- **Thermal-only sanitize:** misses spores; rejected for the every-cycle worst case.

**Accepted costs / constraints / to verify.**
- **Material spec (hard, new).** Every wetted part — wiper seals (SF3), luminaire diffuser
  (ADR-0014), sensors behind splash gaskets — must tolerate **~90 °C + water + detergent +
  disinfectant, repeatedly**. Constrains SF3 and ADR-0014.
- **Chemical = a consumable.** Breaks pure unattended operation: a disinfectant reservoir
  to refill + monitor. Dosing must **fail safe** — empty/failed dose ⇒ flag + fall back to
  thermal, never report "sanitized".
- **Sewer discharge compliance.** Disinfectant + wash effluent must meet municipal
  trade-effluent limits (dilution/neutralization) — a permitting item.
- **Seal wear / drag budget (ADR-0011).** The purge (1–2×) and wash strokes add wiper
  passes over the bore; bound the cycle count and add it to the seal-life + drag budget.
- **Drying is mandatory** (no wet backrest): warm-air knife + squeegee ring; the air
  heater adds energy — bound it.
- **Safety at the mouth.** Crack-purge strokes are in the near-flush **no-occupant** zone
  (ADR-0009), but a reach-in is possible ⇒ the **mouth-plane presence sensor** (ADR-0012
  optional channel E) is **promoted to required**, with the SF2 safety edge and an SF5
  "cleaning — stand clear" signal. Gate the exterior rinse on presence.
- **Freeze protection.** Outdoor unit: trace-heat / self-drain the exterior nozzles, tray,
  mains and drain.
- **Water + energy per cycle.** Quantify liters (in-bore wash + 1–2 purges + hot sanitize)
  and heater energy; challenges priority #5 (low energy), accepted for hygiene #2.
- **Backflow prevention** on the potable mains connection.
- **Space claim / install depth.** Nozzles, manifold, heater/steam gen, disinfectant
  reservoir + doser, dry-air blower and drain must fit the service chamber; update the
  depth budget (ADR-0007/0008/0010).

**Follow-ups.**
- **CAD (`build_model.py`):** add space-claim parts — in-bore spray ring (SprayRing), mouth
  rinse bar, sloped floor + drain port, disinfectant reservoir + doser, heater/steam
  generator, dry-air blower/knife; convert component-tree #6 bosses from "reserved" to
  real geometry; re-export to twin (add to `PARTS`, ADR-0006).
- **Safety:** promote ADR-0012 channel E (mouth-plane presence) to required; SF5 add the
  cleaning-cycle signal; SAFETY.md carry the wash/purge hazards + water-on-public.
- **Materials:** 90 °C / wet / chemical-tolerant seals, diffuser, gaskets (SF3, ADR-0014).
- **Analysis:** water + energy + chemical per cycle; sewer-discharge compliance; freeze.
- **Twin / render:** the digital twin and the cinematic S3 should depict this exact
  choreography (crack → purge → close → open-with-dry-dwell → full open) — the film's
  "cleaning" is now grounded in a real mechanism, not an invented glow.

---

## ADR-0016 — Cleaning stays off the public face; everything exits the mouth (revises ADR-0015)
**Date:** 2026-07-27
**Status:** Accepted. Revises ADR-0015 points 4 and 5a and its internal FloorDrain.
**Drainage refined by ADR-0017** — the wash media (hot water + chemicals) drains to an
internal piston-hidden back sump, not out the mouth; only gross solids exit to the grate.

**Context.** ADR-0015 put two cleaning parts on the STREET face — a mouth rinse bar and a
drop tray under the opening. Both are exposed even when the cell is closed, so they are
grab-able / smashable / trash-able: they violate design priority #1 (vandal resistance),
the very reason the closed cell is otherwise just a flush, handleless, latched steel face.
A tempting fix — capture the debris on the SERVICE side — was rejected because it breaks
the machine's core invariant: the cell **pushes everything OUT the mouth and traps
nothing; the service side is always sealed** (ADR-0001; the occupant is always mouth-side
of the piston, ADR-0009). Debris cannot cross the piston seal into the sealed chamber.

**Decision.** Keep the push-out invariant and take ALL cleaning hardware off the public face.
1. **Everything exits the mouth.** Solids AND wash water leave via the mouth; the bore
   floor **slopes toward the mouth** (no internal low-point drain to clog or trap). The
   ADR-0015 internal FloorDrain is dropped.
2. **A flush pavement trench drain, not an appendage.** A grated, load-rated channel set
   into the PAVEMENT at the mouth base takes the ejected solids + runoff straight to sewer.
   It is streetscape infrastructure — bolted, walk-on, flush — with the solids interceptor
   serviced from **below / behind (a manhole)**, never from the street face. (CAD part
   `TrenchDrain`.)
3. **No mouth rinse bar, no hanging tray.** The interior `SprayRing` cleans the mouth /
   sill / exterior face-edge during the crack-open purge; the runoff drains back out the
   mouth into the trench. If a dedicated mouth rinse is later needed it is **flush jets
   recessed in the sill frame**, not a protruding bar.
4. **Closed = flush face only.** The public sees the hardened piston face; the sole other
   street element is the bolted pavement grate.

**Why.** Priority #1: nothing fragile or grab-able on the public face. The trench is
infrastructure-grade (a city gutter / trench grate), effectively unvandalizable. It keeps
the push-out / never-trap invariant and the sealed service side intact, and it is simpler
(three cleaning parts, not five).

**Rejected alternatives.**
- **Service-side / internal debris capture:** violates the sealed-service, never-trap
  invariant (ADR-0001 / 0009) — debris would have to cross the piston seal. Rejected.
- **Hardened rinse bar / tray on the wall face:** still a street-face target; a flush
  pavement drain is strictly better.

**Accepted costs / to verify.**
- Siting now needs a **plumbed pavement trench + sewer tie** at the mouth, a load-rated
  walk-on grate, and freeze protection (trace-heat / self-drain).
- The **solids interceptor** basket is a maintenance item, reached from below.
- Confirm the bore-floor slope fully drains to the mouth and does not pool at the sill.
- Biohazard runoff crosses the pavement only at the mouth base before dropping through the
  grate — keep the trench hard against the mouth; confirm splash / hygiene.
- **Revisits ADR-0013:** the "drop zone / collection tray" is now this trench drain; the
  sitting-height sill (object-clearing) rationale still holds — items fall into the trench.

**Follow-ups.** CAD: drop `MouthRinseBar` + `DropTray` + `FloorDrain`, add `TrenchDrain`,
slope the bore to the mouth; re-export + update the anatomy diagram. SAFETY.md: note the
pavement drain + slip / hygiene. Confirm grate load rating + trench sewer tie at siting.

---

## ADR-0017 — Wash media drains internally via a piston-hidden back sump (refines ADR-0016)
**Date:** 2026-07-27
**Status:** Accepted. Refines ADR-0016 drainage; reinstates an internal drain (done right).

**Context.** ADR-0016, chasing vandal resistance, routed EVERYTHING out the mouth —
including the wash liquids. But the wash media is hot water + detergent + disinfectant;
sheeting hot chemical water across a public sidewalk (even onto a grate) is worse than the
street hardware it avoided. The wash media needs a proper, contained drain to sewer.

**Decision.** SPLIT the drainage by what it is:
1. **Gross solids** still ride the closing sweep OUT the mouth to the flush pavement grate
   (`TrenchDrain`) — solids can't cross to the sealed service side (ADR-0001 / 0009) and
   would clog an internal drain.
2. **Wash media (hot water + chemicals)** drains INTERNALLY to a **back sump** (`SumpDrain`)
   → sewer; the bore floor slopes to it. Hot chemical water never reaches the street.
3. **The sump is hidden UNDER the piston when it is deployed to the very back** (Eddy's
   refinement). It is covered by the piston when the cell is OPEN — so there is never a
   grate in the occupied cavity (no tamper point, no debris trap, hygienic) — and it is
   behind the flush face when CLOSED. The public and the occupant never see it. So the
   internal drain is *more* vandal-resistant than a street feature, not less.

**Why.** Keeps ADR-0016's principle (no cleaning hardware on the public FACE) while giving
the hot / chemical wash a correct, contained path to sewer. Hiding the sump under the
deployed piston removes the only downside of an internal floor drain — an exposed grate in
the occupied space.

**Rejected alternatives.**
- **Everything out the mouth (ADR-0016 as written):** dumps hot disinfectant water on the
  pavement. Rejected.
- **Exposed floor drain in the occupied cavity:** tamper point, debris trap, hygiene risk.
  Rejected for the piston-hidden position.

**Accepted costs / to verify.**
- The wash choreography must actually deliver the media to the back sump: confirm nozzle
  placement (SprayRing + any deep jets) and the floor slope so the media reaches the sump
  in whatever piston position the wash runs. Space-claim reserves the sump; the hydraulic
  detail is TBD.
- Sump strainer / interceptor serviced from below; sewer tie + trap + freeze protection.
- The sump sits under the deployed piston body (X ≈ cavityLength..barrelLength); confirm it
  clears the piston + actuator and drains fully.

**Follow-ups.** CAD: `SumpDrain` added (space claim); slope the bore to it; re-export +
update the anatomy diagram. SAFETY.md: hot-water / chemical drain to sewer + trap.

---

## ADR-0018 — Two spray rings: front (past the closed piston) + a hidden service-side ring
**Date:** 2026-07-27
**Status:** Accepted. Resolves the ADR-0017 "nozzle placement" to-verify.

**Context.** The wash must reach the surfaces the occupant touched — which end up in the
SEALED CHAMBER behind the piston when the cell is CLOSED (X > ~300; the piston body is
~300 mm wide). A single spray ring near the mouth (ADR-0015, at X=40–120) sits INSIDE that
closed-piston zone, so it can only hit the piston's side, not the chamber.

**Decision.** Two fixed spray rings, so the closed chamber is washed from both ends:
1. **SprayRing (front)** moves to just PAST the closed piston (X = pistonLength + 40 ≈ 340).
   Still near the mouth, but on the service side of the flush face, so it sprays the front
   of the sealed chamber — and the piston face still sweeps past it in transit for a rinse.
2. **ServiceSprayRing (deep)** sits BEHIND the deployed piston face (X = cavityLength + 60 ≈
   2260), so it is NEVER in the occupant space — never seen or reached by the user. It
   washes the deep end of the sealed chamber when the cell is closed.

**Why.** One ring can't be both within reach of the mouth AND past the wide piston; the two
requirements are ~2 m apart. Two rings, front + deep, cover the whole closed chamber, keep
the deep ring permanently hidden from the occupant, and the front ring doubles as the
in-transit face rinse.

**Rejected alternatives.**
- **Single mouth-side ring (ADR-0015):** buried in the closed piston; can't wash the chamber.
- **Single deep ring only:** would miss the piston face / front region and the in-transit rinse.

**Accepted costs / to verify.** Two nozzle manifolds + supply lines (more plumbing). The
deep ring shares the bore cross-section with the deployed piston body — confirm clearance.
Spray coverage/overlap along the 2.2 m chamber is still TBD (two stations may not be enough;
the sump slope must carry the media from both).

**Follow-ups.** CAD: SprayRing repositioned + ServiceSprayRing added (space claim);
re-export + diagram updated.

---

## ADR-0019 — Cleaning method: spray-and-squeegee + a traveling service-side squeegee
**Date:** 2026-07-27
**Status:** Accepted (method + component). Stow via option (b), a deeper chamber. Drive + wash
hydraulics TBD.

**Context.** With the spray stations set (ADR-0018), how does the wash actually clean the full
2.2 m bore and use the drain? Options surveyed: (1) fixed rings + the piston's own seals as the
squeegee; (2) many distributed rings; (3) nozzles on the moving piston; (4) flood-and-soak
immersion; plus a recirculating loop as a cross-cutting enhancement. The syringe already owns a
full-length squeegee — the piston's wiper seals — so coverage can come from MECHANICAL spreading,
not spray reach, favouring few stations (Option 1). But there's a gap: during the sealed-chamber
wash the piston is PARKED flush, so it can't traverse the chamber to scrub it.

**Decision.**
1. **Method = Option 1 (spray-and-squeegee).** The two fixed rings (ADR-0018) wet + dose + hot
   rinse; scrub + spread + drive-to-drain are done by wipers, not spray reach. A recirculating
   loop is added later only if coverage/sanitize proves marginal.
2. **Add a traveling service squeegee (`ServiceSqueegee`).** A wiper that runs the FULL sealed
   chamber while the piston is parked flush — a car wash over the stopped piston, scrubbing from
   inside the bore and driving the wash media to the sump. It lives ENTIRELY on the service side /
   hidden — never seen by the occupant, nothing on the public face.
3. **Stow via a deeper chamber (option b).** The barrel is extended by `squeegeeStow` (80 mm) so
   the squeegee stows behind the deployed piston when the cell is open. Cost: install depth
   2.86 → **2.94 m**. Chosen over (a) a thin disc in the actuator gap (too tight, fouls the chain)
   and (c) nesting it on the piston carrier (most mechanism).

**Cycle.** Close (eject solids out the mouth) → rings spray → squeegee traverses the chamber
scrubbing + pushing media to the sump → hot rinse + final squeegee pass → dry → open (squeegee
retreats into the stow bay behind the piston).

**Why.** Keeps the syringe-native squeegee idea but gives it a dedicated traveler, closing the
parked-piston coverage gap at full-length scrub quality for the worst-case hygiene case. Keeping
it service-side costs nothing in vandal resistance or occupant space.

**Rejected alternatives.** Distributed rings (#2): more penetrations/plumbing/service. Nozzles on
the moving piston (#3): a fluid line on the moving, occupant-contacting part. Immersion (#4): asks
a wiper seal to hold a water column; water/energy/drying/freeze. All revisitable if bench tests demand.

**Accepted costs / to verify.**
- A SECOND moving mechanism + its own light drive (fights only wiper drag, not seal pressure),
  hidden service-side. Against simplicity, bought for hygiene.
- +80 mm install depth for the stow bay (against the ADR-0008/0010 shallow-depth budget).
- The squeegee shares the bore axis with the central chain/rod — confirm the passage/clearance.
- Bench gates (from the survey): does the wiper spread + scrub a full-length film; is
  spray+squeegee+heat+chemical enough log-reduction or is immersion needed; water/energy per cycle;
  does gravity + squeegee actually clear the sump.

**Follow-ups.** CAD: `ServiceSqueegee` added, barrel extended (space claim); its drive is TBD.
Twin: a new mover (added to `moving_parts`) — animate its traverse. Re-export + diagram.

---

## ADR-0020 — Squeegee drive: a dedicated, swappable rigid-chain unit
**Date:** 2026-07-27
**Status:** Accepted (drive choice + space claim). Chain sizing, the offset→central coupling,
and the motor are TBD.

**Context.** ADR-0019's `ServiceSqueegee` needs its own drive. The syringe topology forbids
external rails / wall slots (ADR-0007), so the drive must be central/coaxial like the piston's.
Options surveyed: (1) water-driven "cleaning pig" + tether (reuses the wash pump, no motor);
(2) shared piston actuator + a drive-transfer clutch (one motor, but a fragile clutch);
(3) a dedicated compact rigid-chain (a second zip-chain, its own motor); (4) a central
lead/ball screw (whip + depth + wash-zone corrosion).

**Decision.** Option 3 — give the squeegee its OWN compact rigid-chain drive (`SqueegeeDrive`),
a modular unit that nests in the back-of-house BESIDE the piston's actuator (no added install
depth) and pushes the squeegee's back.

**Why.** Chosen for SERVICEABILITY / reliability (priorities #3 / #4 / #8): an independent module
that can be bench-tested and swapped on its own, decoupled from the piston drive — no shared
clutch to fail (rules out #2), no dependence on wash-pump pressure or a mostly-sealing disc
(rules out #1's soft force/positioning), no long whippy screw in the wash zone (rules out #4).
Rigid-chain is proven (ADR-0008) and the squeegee's load is light (one low-friction wiper), so
the unit is small.

**Rejected alternatives.** Water pig (#1): elegant and motorless, but soft force/positioning and
the disc must mostly-seal — revisit if the chain proves overkill. Shared clutch (#2): a transfer
dog is a reliability risk for an unattended unit. Lead screw (#4): whip + retract depth (the
problem ADR-0007 avoided) + wash-zone corrosion.

**Accepted costs / to verify.** A second motor + controller (against simplicity #7, bought for
serviceability). **Coupling:** the drive nests offset in +Y, so a yoke/arm must transfer its push
to the central squeegee ring **without a wall slot** — confirm the routing. Chain/motor sizing vs
the (light) wiper drag. The back-of-house cross-section grows to house it (depth unchanged).
An independent self-test + quick-swap mounting are needed to actually realise the serviceability win.

**Follow-ups.** CAD: `SqueegeeDrive` space claim added beside the actuator; coupling + chain
column TBD (resolved in ADR-0021). Twin: drive the squeegee's traverse from it. Re-export + diagram.

---

## ADR-0021 — Squeegee-drive coupling: an in-bore offset chain lane + rigid yoke
**Date:** 2026-08-02
**Status:** Accepted (routing + space claim). Yoke stiffness/anti-rack detail, chain sizing,
and the motor remain TBD.

**Context.** ADR-0020 chose a dedicated rigid-chain `SqueegeeDrive` nested OFFSET in +Y beside
the piston's central magazine, and parked the hard question: how does that offset drive push the
CENTERED `ServiceSqueegee` ring **without a wall slot** (ADR-0007 forbids breaching the sealed
barrel, and ADR-0007 also rules out external rails)? The piston's own rigid chain already occupies
the central axis of the whole chamber when the cell is closed, so the squeegee drive cannot be
coaxial with it.

**Decision.** Run the squeegee's rigid chain **INSIDE the sealed bore**, in an **offset +Y lane**
near the wall (`squeegeeChainOffsetY = 430 mm`, chain 60×60, wall at Y=500), and couple it to the
ring's +Y frame with a **short rigid yoke** (`SqueegeeYoke`). No slot, no gland, no wall
penetration. The bore itself guides the ring against rack (same principle as the piston in its
non-circular bore), so the push is applied on the +Y side only.

**Why it's sound (temporal exclusivity).** The piston (central) and the squeegee (offset) **never
occupy the chamber at the same time**, so they can share the one sealed volume at different times:
- **Cell open** → piston deployed into the chamber (X 0–2200); the squeegee + its chain + yoke are
  fully retracted to the stow bay behind the deployed piston (X ≥ 2500). The offset lane is empty.
- **Cleaning** → piston parked **flush at the mouth** (X 0–300); the whole chamber (X 300–2500) is
  sealed and free, and the offset chain extends down the +Y lane to sweep the squeegee across it,
  parallel to (and clear of) the piston's fully-extended central chain.
CAD confirms zero `CavityReference` intrusion for both the chain and the yoke (they stow at
X > cavityLength = 2200, behind the deployed piston) and that install depth is unchanged (2.94 m).

**Sizing (first pass, placeholder pending the wiper spec).** Wiped bore perimeter ≈ 3.98 m; a
single soft scrub lip (it does NOT seal — the piston does) at ~0.2 N/mm preload, wet-detergent
μ≈0.3 → drag ≈ 240 N; design to ~500 N with margin. Sweep 2.2 m at ~0.2 m/s → ~100 W mechanical,
sprocket torque ~24 N·m, ~40 rpm → a ~150–200 W gearmotor. Roughly an order of magnitude lighter
than the sealing piston actuator, confirming ADR-0020's "small unit / light load."

**Rejected / deferred.** A widened-wall chain channel with a traveling sealed gland (reintroduces
a slot — rejected). A two-point push bar spanning +Y to −Y (stiffer, no cocking, but crosses the
bore cross-section — deferred; revisit only if single-side push racks in test). The motorless
water-pig (ADR-0020) stays the fallback if the chain proves overkill.

**Accepted costs / to verify.** Single-side push relies on the bore as the anti-rack guide —
confirm the ring doesn't cock under wiper drag (else the two-point yoke). Chain column + motor
sizing vs the real wiper drag once the lip is specced. The +Y lane must stay clear of the deep
`ServiceSprayRing` (X 2260–2340) and the luminaire (top crown) — CAD clearance holds.

**Follow-ups.** CAD: `SqueegeeChain` + `SqueegeeYoke` added, offset +Y lane, stowed pose. Twin:
drive the squeegee's traverse along the lane. Re-export objs + update `docs/cell_anatomy.svg`.

---

## ADR-0022 — CLEARED_HOLD re-reads both safety trips (found by model checking)
**Date:** 2026-08-03
**Status:** Accepted. Implemented in the twin + spec; the availability cost is accepted as-is.

**Context.** The formal model added for roadmap #1 (`spec/`, TLA+/TLC) found a defect in
shipped interlock logic that neither the scenario self-test nor review had caught. The
`CLEARED_HOLD` branch of `safety_interlock.gd` — the dwell with the piston closed and flush
at the mouth — tested only `t >= hold_seconds`. It re-read **neither** SF1 nor SF2.

So a safety-edge trip at the flush position went unacted-on for the remainder of the dwell
(**2.0 s** at the twin's default). TLC reaches it by the route that matters: someone reaches
into the mouth (**H5**) at the exact position the piston is completing to, and is held
against the flush face. That is **H8**, the mouth-lip pinch — precisely the hazard SF2 exists
to answer. Every other state already reversed on either trip; this one state did not.

Bounded, not a crush: `Inv_NoCrush` held throughout (the piston never drives *past* the
occupant, and contact stays at the 120 N cap in effect at the time (revised to 100 N
under **ADR-0024**, sourced from injury/biomechanical data). The
defect is in the *latency* of the response, not its existence — but SF2's specification in
`SAFETY.md` says "immediate stop and reverse", and up to a full dwell is not immediate.

**Decision.** `CLEARED_HOLD` exits to `REDEPLOY` on `life_present() or contact_over_limit or
t >= hold_seconds` — either trip cuts the dwell short, matching what `CLEARING` already did.

**Why it's sound.** Reversing is the safe direction (the piston sweeps *away* from the
occupant, toward the open mouth), so an early exit is never worse than serving out the dwell.
There is no state in which staying flush longer is the safer choice: the "stay closed without
power" requirement is met by the passive flush latch (ADR-0009), which is unpowered and
unaffected by this path. Including SF1 as well as SF2 costs nothing and keeps the two trips
symmetric across every state — a fault now opens the pod rather than holding it closed, which
is the fail-safe direction.

**Accepted costs.** Availability, not safety: a spurious edge or channel reading at the flush
position now re-opens the cell instead of being ignored for ≤2 s. Judged the right trade for
an unattended public unit where the alternative is a bounded pinch at the mouth lip. If
nuisance re-opens show up in testing, the fix is a debounce on the trip, **not** restoring
the dwell.

**Follow-ups.** Done: twin (`safety_interlock.gd`), regression scenario S6 in
`test_interlock.gd`, spec `ClearedHold` + `Inv_NoTripHeldAtFlush` in `Safety.cfg`, and a
`hold-ignores-trips` mutant that re-injects the pre-fix code so the guard cannot silently rot.
`SAFETY.md` SF2 updated.

---

## ADR-0023 — The external E-stop is a Category 0 stop into the SF4 fail-open path
**Date:** 2026-08-03
**Status:** Accepted (behaviour + twin/spec implementation). Rated hardware + PL assessment TBD.

**Context.** ADR-0009 retained "an EXTERNAL / operator E-stop + remote tamper/fault
monitoring (availability, not a trap function)" but never said what pressing it *does*.
The twin had no E-stop input and no notion of drive power at all, so when the formal model
(roadmap #1) encoded SF4, its E-stop and power-loss claims were verified against *intent*
rather than against code — the one gap that verification effort left behind.

**Decision.** The E-stop **removes drive power** (Category 0, IEC 60204-1) rather than
commanding a controlled halt. It therefore enters exactly the same fail-open path as a
blackout, with ADR-0009's position-dependent behaviour: the return element relieves the
piston anywhere in the occupant zone, the passive latch holds the flush end. Releasing the
button does **not** restart anything — the machine backs out to deployed and re-enters the
cycle through `LIFE_CHECK`, so a fresh life-check must pass before the piston can advance.

**Why it's sound.** A "freeze in place" E-stop would recreate **FMEA F3** exactly: a
sustained pin with power gone and nothing able to detect or act (S4, D4 — the failure that
forced the whole SF4 design-out). It would be a deliberate mechanism for violating the one
requirement SF4 exists to enforce. Category 0 instead makes the E-stop *inherit* the
mitigation rather than bypass it: the same stored-energy return element, the same latch, the
same relief. And the no-auto-restart rule is what stops the E-stop from becoming a way to
resume a sweep over someone an operator hit the button to protect.

**Rejected.**
- *Freeze in place / hold position.* Recreates F3. Rejected.
- *Category 1 (controlled decel, then power removal).* The decel phase buys a smooth stop
  the machine does not need — the piston's design speed is millimetres per second
  (ADR-0007's sizing put it at ~3.7 mm/s), so there is nothing to decelerate, and the phase
  would keep the drive powered during exactly the window the E-stop was pressed to end.
- *Interior / occupant-operated E-stop.* Already rejected in ADR-0009 as a vandalism and
  abuse surface in unattended public units. Unchanged: this one is external/operator only.

**Accepted costs / to verify.** The E-stop's effectiveness now rests entirely on the same
~1.5 kN return element as SF4, so **FMEA F6** ("fail-open path does not release") covers it
too — that is the same single failure mode, not a new one, but it does mean the E-stop is no
better than that element's reliability and needs the same periodic self-test. Availability
cost: an E-stop press re-opens the cell rather than holding it closed. Rated hardware, the
safety controller, and the PL assessment remain open (as for all of SF1/SF2).

**Follow-ups.** Done: `safety_interlock.gd` gains `powered` / `estop` / `UNPOWERED` +
`_fail_open` / `_recover`; scenarios S7–S9 in `test_interlock.gd`; the TLA+ spec's SF4
claims (`Inv_EStopHalts`, `P_NoAdvanceUnpowered`, `P_NoAutoRestart`, `P_PinRelieves`) now
verify against code rather than intent. The unpowered return *rate* stays a placeholder —
it is spring force minus seal drag, and seal drag is issue #9.

---

## ADR-0024 — SF2 force cap sourced from injury/biomechanical data (100 N)
**Date:** 2026-08-04
**Status:** Accepted. Implemented in the twin, spec docs, and the pin-relief/seal-drag
sweep scripts. Hardware force-limitability check remains open (#8, gap G2).

**Context.** The FTA for roadmap #2 flagged basic event **B7**: "the 120 N cap is itself
above the injury threshold" as the fault-tree branch most worth chasing — a *systematic*
error, identical in every unit, that no redundancy defends against (`TRACEABILITY.md`
gap **G2**, issue #8). The 120 N figure in `SAFE_CONTACT_N` (`godot/physics_demo.gd`) and
the matching `F_SAFE_SUSTAINED` target in `scripts/pin_relief.py` /
`seal_drag_sweep.py` carried the comment "below the ~150 N powered-door limit" — but no
standard was ever named, and checking it (below) found the real door standard caps lower,
not higher, than that: the comparison itself was wrong, not just unsourced.

**Decision.** Set `SAFE_CONTACT_N` = **100 N**, propagated to the matching
`F_SAFE_SUSTAINED` target in the two pin-relief/seal-drag scripts. Full survey and
rationale in [`force_limit_injury_data.md`](force_limit_injury_data.md); summary:

- **FMVSS 118** (US federal power-window anti-pinch standard): **100 N**, tested down to
  a 4 mm rod representing a small child's finger — real regulatory precedent for the
  identical hazard class (a powered mechanism closing on a body part), and the only
  source surveyed validated against a sub-adult limb.
- **ISO/TS 15066** Annex A (biomechanical pain-onset limits by body region, University
  of Mainz study): **abdomen 110 N quasi-static** is the applicable worst-case region
  for H3/H8 (piston pinning a limb/torso, or the mouth-lip pinch) — hands/fingers,
  chest, neck, and pelvis are all higher (140–180 N) and not the binding constraint.
  100 N clears this with margin.
- The old "~150 N powered-door limit" comparator (ANSI/BHMA A156.19) actually caps
  normal-operation stop force at **67 N** — confirming the old 120 N cap was being
  checked against a number that was itself wrong, in the permissive direction.

**Why 100 N and not 110 N (the ISO abdomen figure).** 100 N clears *both* relevant
thresholds at once (100 ≤ 100 and 100 ≤ 110) rather than sitting between them, and it is
the one source validated against a body part smaller than an adult's — consistent with
`SAFETY.md`'s stated user model (vulnerable: intoxicated, unconscious, disabled, asleep).
It is also a real regulatory number, not a synthesized one — the property a reviewer
asking "where did this come from" needs.

**Consequences, checked, not re-derived.** `SAFE_CONTACT_N` feeds `physics_demo.gd`'s
SR-007 discrimination test (unaffected: trash-pile load ~63 N stays well under, the
non-yielding-body load ~138 N stays well over — margin preserved both directions).
`F_SAFE_SUSTAINED` feeds `pin_relief.py`'s passive-relief verdict (ADR-0009): re-run,
the qualitative conclusion is unchanged (passive relief still fails — residual pin is
1206 N either way, now ~12× the target instead of ~10×) because the return-element
sizing (`f_return`, `f_close_design` — 1567 N / 5546 N) depends on seal drag and design
margins, not on this target. This is **not** the actuator re-run tracked as issue #11 —
that item still owns re-deriving the return-element/actuator numbers once seal drag
(#9) is measured; this ADR only corrects the comparison target those numbers are
checked against.

**Rejected.**
- *Keep 120 N, drop the door comparison.* Would leave the cap unsourced again — the
  original sin gap G2 flagged. Rejected.
- *Use the ISO/TS 15066 abdomen figure (110 N) directly.* Real and sourced, but sits
  above FMVSS 118's child-finger figure; 100 N dominates both. Rejected in favour of the
  lower, doubly-anchored value.

**Accepted costs.** None functional — 100 N is a stricter cap than 120 N, so SF2 trips
earlier, not later; the only cost is a marginally higher nuisance-trip rate against
compliant/soft obstructions, judged acceptable for the safety margin bought.

**Still open.** The hardware half of issue #8: whether the real actuator + controller,
under real seal drag (#9) and real jam dynamics, can actually be held to 100 N — sim
force is a modelled quantity, not a measurement of force-limitability. `TRACEABILITY.md`
gap G2 renamed accordingly (no longer "cap unvalidated," now "drive's real
force-limitability under a jam unverified").

**Follow-ups.** Done: `godot/physics_demo.gd`, `scripts/pin_relief.py`,
`scripts/seal_drag_sweep.py`, `SAFETY.md`, `TRACEABILITY.md` (SR-007, B7, G2),
`spec/README.md`. `docs/force_limit_injury_data.md` holds the full source survey.

---

## Component tree (one cell) — reference for ADR-0001

1. Structure/enclosure: sleeping shell (bore), fixed barrel/frame, wall-interface
   flange & trim, internal ribs, piston (also the closing element).
2. Motion/actuation: linear actuator, guide rails + carriages, actuator-to-piston
   coupling, mechanical hard stops.
3. Sealing/hygiene: perimeter wiper seals, floor slope + drain port, splash gaskets.
4. Sensing/safety/control: position sensors + limit switches, diverse-redundant
   occupancy sensors (radar vitals + thermal + CO2 + load/BCG, ADR-0012),
   pressure-sensitive safety edge, external/operator e-stop + passive flush latch
   (NO interior release, ADR-0009), rated safety controller.
5. Services: power, cable carrier (drag chain), interior lighting, water/drain.
6. Cleaning subsystem: ADR-0015–0019 (spray-and-squeegee wash, thermal-chemical sanitize, plumbed;
   solids out the mouth to a flush pavement grate, wash media to an internal piston-hidden sump —
   no street-face hardware) — SprayRing + deep ServiceSprayRing, a traveling ServiceSqueegee,
   SumpDrain, TrenchDrain, ServicePlant, + the squeegee's own SqueegeeDrive with an in-bore
   offset chain + yoke (ADR-0020/0021); wash hydraulics TBD in build_model.py.
7. User interface: exterior availability indicator, interior grab feature, call button.
