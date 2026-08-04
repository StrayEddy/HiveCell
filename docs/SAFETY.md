# HiveCell — Safety (M8, living document)

Machine-safety analysis for a powered steel piston that moves through a space people
occupy. Method: identify hazards (ISO 12100 style), rate risk, assign safety
functions. Users are assumed VULNERABLE (may be intoxicated, unconscious, disabled,
asleep) and may NOT self-rescue.

**Numbered requirements, the Hazard→Requirement→Design→Verification chain, fault trees
and the gap register are in [`TRACEABILITY.md`](TRACEABILITY.md).** This file holds the
hazards, FMEA and safety functions themselves; that one holds what discharges them —
and, more importantly, what does not.

## Design principle (order matters)
1. **PREVENT** — never move while occupied. Occupancy detection is the primary safeguard.
2. **REACT** — on unexpected contact/resistance, STOP and REVERSE.
3. **INHERENT** — slow soft-start, filled gaps: defense-in-depth, never the sole defense.

"Push the occupant out slowly" is NOT a safety case. Retraction with an occupant
present is a detected fault that aborts, not a normal mode.

## Hazard register
Risk = Severity (1-4) x Likelihood (1-4). Severity 4 = permanent injury/death.

| # | Hazard | Scenario | S | L | R | Required safety function |
|---|--------|----------|---|---|---|--------------------------|
| H1 | Push-out / crush of a non-reacting occupant | Retraction starts with an unconscious/intoxicated person inside | 4 | 3 | 12 | Redundant occupancy detection; never retract if occupied; abort + alarm |
| H2 | Shear / draw-in at piston-bore gap | Hair, fingers, skin, clothing caught at the sweeping 3 mm edge | 4 | 3 | 12 | Fill gap with compliant wiper/brush (no open moving gap); occupancy interlock |
| H3 | Crush by force | Slow piston pins a limb/torso against opening frame or bracing | 4 | 2 | 8 | Force/current limit + pressure-sensitive safety edge on piston face -> stop & reverse |
| H4 | Fall from an elevated mouth | Occupant pushed out of a mouth above floor level | 3 | 2 | 6 | SF1 interlock prevents push-out — **sole** fall defense (accepted, see Siting rules); sitting sill ≤ ~500 mm, forgiving surface below; no mouth over a real drop |
| H5 | Reach-in from outside during motion | Bystander/child reaches into the mouth while moving | 3 | 2 | 6 | External presence sensing at the mouth; safety edge; slow speed |
| H6 | Moves while occupied (sensor/control fault) | False "empty", stuck sensor, wiring fault | 4 | 2 | 8 | Redundant, diverse sensors; fail-safe (fault -> no motion); rated safety controller |
| H7 | Trapped under self-locking hold | Someone caught; drive is self-locking, power lost | 4 | 1 | 4 | Fail-open / back-drivable drive: power loss cannot sustain a holding force (passive pin relief). NO occupant-operated release (see FMEA) |
| H8 | Pinch at the mouth lip | Piston reaching flush pinches at the opening edge | 3 | 2 | 6 | Safety edge; final approach speed reduction; lip geometry |

## Safety functions
Status: **[sim]** = logic/behaviour implemented and machine-checked in the digital
twin (see below) — NOT rated hardware, no performance-level claim yet. **[todo]** =
not started.

- **SF1 Occupancy detection (primary)** — *[sim: fail-safe voting logic]* redundant +
  diverse sensors (e.g. load/weight in the floor + optical/IR beam + capacitive/radar
  + mmWave/UWB vital-sign radar for a still, cold, blanketed occupant). Fault or
  "possibly occupied" => no motion. Architecture in **ADR-0012**: diverse-redundant
  suite (radar vitals + thermal + CO2 + load/BCG), fail-safe voting, target **ISO 13849
  PL e** — sensor parts + certification TBD.
- **SF2 Contact reaction** — *[sim: force cap + safety-edge trip]* chain-drive
  current/force monitoring + pressure-sensitive safety edge on the piston face =>
  immediate stop and reverse to deployed — from **every** state the piston can be in,
  including closed-and-flush (ADR-0022; the mouth-lip pinch H8 sits exactly there).
  Independent of SF1. The trip is on YIELD,
  not resistance magnitude: movable trash stays bounded; a non-yielding body makes
  force climb steeply — that is what a cap below the injury threshold catches.
- **SF3 Gap elimination** — *[cad: gap-fill geometry + drag budget]* compliant
  wiper/brush seal fills the 3 mm so there is no open moving shear line (also serves
  hygiene + the seal-drag budget). Two lip rings on the piston perimeter; the
  COMPLIANCE (a finger/hair deflects the lip instead of being sheared) is a material
  property — asserted, not yet proven by test. **Low friction is now a hard
  requirement (ADR-0011):** seal drag couples SF3 ↔ SF4 ↔ actuator — it sets the SF4
  residual-pin floor and the actuator force, so a low-friction seal (PTFE/lubricated/
  brush) shrinks the SF4 spring + actuator ~3.6x (40 vs 150 N/m). Must be measured.
- **SF4 Fail-open drive** *(was: manual release + interior E-stop)* — *[decision:
  design-out, see FMEA; sim: fail-open + latch + no-auto-restart]* power loss must not
  sustain a holding force; the drive fails
  OPEN / back-drivable so a mis-detected pin relieves passively — no lever, no
  occupant-operated release device. An accessible release was rejected: it is a
  vandalism/abuse surface in unattended public units, and the sealed-in trap is
  already removed by geometry (the piston always sweeps toward the open mouth, never
  enclosing the occupant). Fail behavior is position-dependent: back-drivable in the
  occupant zone (pin relief), a passive latch holds the flush end without power (stays
  closed, no occupant can be there). See **ADR-0009**.
- **SF5 Motion signalling + soft profile** — *[sim]* warning (light/sound) before and
  during motion; slow soft-start/stop; reduced final-approach speed. Soft velocity
  profile (`soft_profile.gd`: soft-start/stop + speed-limited final approach) and
  signalling (green = ready to occupy, red = about to move / moving, orange = closed,
  flashing red = occupied + refusing to move → beacon) modelled in the twin + self-test.
  Defense-in-depth only — never a primary safeguard.

## FMEA — trap / crush failure chain (basis for the SF4 decision)
Component-level companion to the hazard register: how the drive/interlock can fail
and what happens. Scale 1-4 each (engineering judgment, not measured): **S**everity,
**O**ccurrence, **D**etection (4 = hard to detect / nothing acts). RPN = S×O×D.

| # | Failure mode | Cause | Effect | S | O | D | RPN | Mitigation / decision |
|---|--------------|-------|--------|---|---|---|-----|-----------------------|
| F1 | SF1 reads false-empty | stuck/blind/mis-cal sensor | a sweep starts with a person inside | 4 | 2 | 3 | 24 | SF2 independent force trip (backstop); diverse redundant SF1 |
| F2 | F1, then contact **with power** | — | SF2 force cap trips → stop & reverse → occupant freed | 1 | 2 | 1 | 2 | designed defense-in-depth path (works in sim) |
| F3 | F1, then contact **and power lost**; self-locking drive holds | blackout, cut supply, fault | sustained pin/crush; no powered reverse; occupant held under force | 4 | 1 | 4 | 16 | **fail-open drive (SF4)** — power loss must not sustain a holding force |
| F4 | Sweep stops in free space | any fault / power loss, no contact | occupant sits in an OPEN pod → exits under own power | 1 | 2 | 1 | 2 | none needed — geometry keeps occupant mouth-side of the piston |
| F5 | Occupant sealed *behind* piston | — | — | — | — | — | — | eliminated by geometry (piston sweeps toward the mouth) |
| F6 | Fail-open path does not release | clutch stuck engaged / not back-drivable | pin persists on power loss | 4 | 1 | 3 | 12 | reliable release path + periodic self-test of the clutch/back-drive |
| F7 | Occupant-operated interior release *(had one been fitted)* | vandalism, nuisance, misuse | pod forced open / held out of service; tamper with mechanism | 1 | 3 | 2 | 6 | **not fitted** — rejected in favour of the passive fail-open drive |

Note the driver is **F3**: low occurrence, but Severity 4 with **nothing able to
detect or act once power is gone** (D=4). High severity + zero un-powered mitigation
⇒ it must be *designed out*, not merely made unlikely (ALARP).

### SF4 decision
Reject an occupant-operated manual release + interior E-stop (F7): in unattended
public street units it is a vandalism/abuse surface, and the geometry already removes
the sealed-in trap (F4/F5). Replace it with an INHERENT requirement — **the drive
must not sustain a holding force without power** (F3): on power loss during motion the
transmission fails OPEN / back-drivable, so a pin relieves passively with no
accessible part.

Implementation: **ADR-0009**. Fail behavior is position-dependent — back-drivable in
the occupant zone (pin relief on power loss), with a PASSIVE flush latch holding the
closed end without power (security + zero standby), engaging only where no occupant
can be. A motor-side declutch does NOT work (the rigid chain's self-lock is intrinsic
and downstream). CHECKED (`scripts/pin_relief.py`): passive back-drive stalls at the
seal drag, so the residual pin floors at ~1.2 kN ≈ 10x a safe force — passive relief
is INSUFFICIENT, so a ~1.5 kN stored-energy return element is REQUIRED (raising
closing force ~2.3x). Retained, not occupant-facing: an EXTERNAL / operator E-stop +
remote tamper/fault monitoring (availability, not a trap function).

## Formal verification (TLA+ / TLC)
The interlock's safety claims are **machine-proven over all reachable states**, not
only the hand-written scenarios below: `spec/HiveCellInterlock.tla`, run by
`scripts/run_modelcheck.sh` (gated on every push via `.githooks/pre-push`). The model
covers the clearing FSM, the ADR-0012 fusion voter, the SF2 trip, and the external
E-stop + SF4 fail-open drive. Full claim list, the model↔code correspondence table, and
the abstractions it relies on: [`../spec/README.md`](../spec/README.md).

The claim worth naming here is **`Inv_NoCrush`**: the piston never drives past a real
occupant *even with all four SF1 channels blind*. That is the FMEA F1→F2 chain — the
"defense in depth" phrase above — proven over a ground-truth occupant the sensors may
miss entirely, at every position in every reachable state, rather than at the single
hand-picked position scenario S5 checks. Also proven: SF4's pin actually relieves
under FMEA F3 (blind SF1, occupant inside, power gone and not returning).

Eight injected defects — mostly designs the ADRs explicitly rejected (a self-locking
drive, 2-of-4 voting, faults reading clear) — are all caught, so the green result is
evidence rather than decoration: `scripts/run_modelcheck.sh --mutants`.

**It does not confer a PL rating** — it is logic, not rated hardware. Timing-layer
faults (dropouts, races, stall) are deliberately abstracted away and remain open as
roadmap #3. The model is hand-written and can drift from the GDScript.

**Finding F-1 — fixed (ADR-0022).** Model checking found a real defect in shipped
logic that the scenario self-test had not caught: `CLEARED_HOLD` re-read *neither*
safety trip, testing only the dwell timer, so with the piston flush a safety-edge trip
went unacted-on for up to `hold_seconds` (2.0 s). Reachable by someone reaching into
the mouth (**H5**) as the sweep completes, held against the flush face — **H8**, the
mouth-lip pinch, exactly where SF2 should act. Bounded, not a crush (`Inv_NoCrush` held
throughout; contact stays at the 100 N cap), but a latency SF2's spec does not allow.
`CLEARED_HOLD` now exits on either trip; guarded by `Inv_NoTripHeldAtFlush`, scenario
S6, and a mutant that re-injects the pre-fix code. **This is the concrete argument for
the method** — the defect survived review and scenario testing, and exhaustive state
exploration found it in the first run.

## Implementation status (digital twin)
The safety *logic* has a reference implementation in the Godot twin. It models
behaviour and is regression-checked; it is NOT rated hardware and makes no
performance-level (PL) claim.

- `godot/safety_interlock.gd` — the interlock state machine. SF1, SF2 and SF4 are three
  independent layers. SF4: `powered` / `estop` inputs and an `UNPOWERED` state implement
  ADR-0009's position-dependent fail-open — the return element relieves a pin anywhere in
  the occupant zone, the passive latch holds the flush end, and restoring power or
  releasing the E-stop backs the piston out rather than resuming the sweep (ADR-0023).
  SF1 and SF2 are two independent trips. SF1 = fail-safe OR across (simulated) diverse life-detection
  channels (radar vitals, thermal, CO₂, load-cell BCG); any channel, or any sensor
  fault, => "occupied" => no motion. SF2 = contact force over a safe cap
  (`SAFE_CONTACT_N` = 100 N — sourced from injury/biomechanical data, see
  [`force_limit_injury_data.md`](force_limit_injury_data.md) and ADR-0024). Either trip stops
  and reverses a sweep, reversing from the current position; a sweep never starts
  while either trip is active.
- `godot/tests/test_interlock.gd` — headless self-test enforcing the invariant "the
  sweep never advances while a safety trip is active", across: empty+clear, occupied,
  mid-sweep intrusion (SF1), sensor-fault fail-safe, SF1-blind / SF2-catches, a
  trip while closed-and-flush (S6, the ADR-0022 regression guard), and SF4 —
  blackout mid-sweep relieving the pin (S7), the flush latch holding without power
  (S8), and an E-stop that does not resume the sweep on release (S9, ADR-0023).
  Runs on every push via `.githooks/pre-push`.
- `godot/physics_demo.gd` — physics scenarios (default Play scene). The drive-load
  model demonstrates yield-vs-magnitude: a 10-item trash pile peaks ~63 N (bounded,
  yields) while a non-yielding body spikes to ~138 N and trips SF2. Includes the
  SENSOR BLIND case where SF1 misses the occupant and SF2 alone catches the contact.
- `godot/soft_profile.gd` — SF5 soft motion profile (soft-start, cruise, soft-stop,
  speed-limited final approach) shaping the interlock's sweep velocity; signalling
  (green ready / red moving / orange closed / flashing-red occupied-alarm) drives a
  beacon in both twins. `test_soft_profile.gd`
  checks the shape, monotonicity, completion, and timing.
- `scripts/build_model.py` — the wiper seals (SF3): two lip rings on the piston
  perimeter filling the 3 mm gap, verified to touch the bore and hug the piston
  (~0 overlap). `scripts/actuator_sizing.py` budgets their drag: 2 lips × ~4 m
  perimeter @ 150 N/m ⇒ ~1190 N, the dominant load. With the SF4 return element
  (1567 N, ADR-0009) the closing resistance is 2773 N ⇒ **design force ~5546 N**
  (×2 factor) — 2.3× the 2411 N sized before SF4.
  Exported to both twins as `WiperSeals.obj`, riding with the piston.

Addressed in sim: H1/H6 by SF1 (+ fail-safe), H3/H5/H8 contact behaviour by SF2,
H2 gap-fill *geometry* by SF3 (compliance TBV), H5/H8 further eased by SF5 (warning +
slow final approach). H7 has a design decision (SF4/ADR-0009); H4 — sitting-height sill
is an accepted single-layer trade (SF1 is the fall defense), see Siting rules. H7 is now
also modelled, not only decided: the fail-open relief, the passive flush latch, and the
no-auto-restart rule run in the twin and are machine-checked (SF4 above, ADR-0022/0023).

## Siting rules (facility-level, H4)
Install constraints on the operator/installer, not device functions.

**Mouth at sitting height (design decision, ADR-0013).** The opening sill is set at ~sitting
height (~450–500 mm) so ejected inanimate items fall *clear* of the opening instead of
piling at the sill (clearing + hygiene), and for natural sit-and-swing entry.

**Accepted risk trade (H4).** A sitting-height mouth removes the floor-level fall
protection that would otherwise catch a person swept toward the mouth: *any edge debris
falls off, a non-reacting person could fall off too.* So fall protection in the H4
scenario now rests ENTIRELY on SF1 (never move while occupied) — a deliberate
single-layer choice, a conscious departure from the "never the sole defense" principle
for this one hazard. Accepted because: (a) SF1 is diverse-redundant, fail-safe, PL e
(ADR-0012) with the SF2 contact backstop, so a push-out needs several independent
failures; and (b) the residual fall is low (~450–500 mm, ≈ a high step), not a fall
from height. Logged here as accepted, not overlooked.

**Still required (bound + soften the residual):**
- Surface below/in front of the mouth: non-slip, clear, and *forgiving*, so a low fall
  or a stumble on exit doesn't injure; with a collection zone/tray for ejected items.
- The accepted drop is ~500 mm only. Do NOT stack cells so a mouth opens over a real
  drop — upper tiers still need a same-level access gallery (a ~500 mm sill is the
  accepted trade, not a multi-metre fall).
- Mouth edge + step-down legible in low light (complements SF5 signalling). The interior
  luminaire's always-lit warm egress line at the mouth threshold (ADR-0014) makes the
  exit findable for a disoriented occupant; its low warm night-glow keeps the sealed
  cavity from being pitch black (anti-panic, and sickness/hazards stay visible) — these
  are occupant-protection functions, not comfort. Interior lighting is otherwise a
  Services item (not an SF), but this egress/night-glow role is safety-relevant.

**Responsibility.** Documented install requirement, verified at commissioning; the
device cannot enforce it. The risk acceptance should carry a named sign-off.

## Open items
- **SF1 real sensing (ADR-0012, revised by ADR-0025):** architecture decided
  (diverse-redundant suite, fail-safe voting, PL e). Placement resolved: all sensors
  crown-mounted (fixed barrel ceiling) except load cells (floor, by necessity); nothing
  on the piston. CO2 dropped from the suite (vent-exposure vs. flush-window channels);
  confirmed suite is now radar + thermal (2 of the original 4 independent physics
  domains), with load cells provisional pending a bench test. This is a real reduction
  in common-cause-failure margin from ADR-0012's original architecture — **re-justify
  against the PL e target once the load-cell bench test lands and part numbers are
  final.** Candidate parts + prices in
  [`occupancy_sensor_selection.md`](occupancy_sensor_selection.md). Still to do:
  bench-validate radar vital-sign detection through bedding + small-animal sensitivity
  + crown-mount range/FOV to the deep end of the bore; bench-test piston-vibration
  coupling into the floor load cells (ADR-0025); build the ISO 13849 PL e verification
  dossier (category, MTTFd, DC, CCF) once parts are confirmed.
- **SF2 real force limit — injury-data half DONE (ADR-0024):** `SAFE_CONTACT_N` is now
  100 N, sourced from FMVSS 118's child-finger pinch limit and ISO/TS 15066's abdomen
  pain-onset threshold — see [`force_limit_injury_data.md`](force_limit_injury_data.md).
  Still open: the drive's *actual* force-limitability (can the real actuator hold the
  cap under a hard jam, given real seal drag?) — hardware, coupled to #9. SF1 remains
  primary either way (force alone cannot be trusted if a heavy jam can exceed the cap).
- **SF3 lip material + compliance + LOW FRICTION (ADR-0011):** select a low-friction
  wiper (PTFE/lubricated/brush) and PROVE a finger/hair deflects rather than shears.
  Seal drag is the master lever (couples SF3/SF4/actuator; `seal_drag.py` range
  ~16-700 N/m) — MEASURE it on a real sample (dry, with grit); it gates the SF4 spring,
  the actuator, and whether ADR-0010's drive complexity is warranted.
- **H4 mouth height / siting (ADR-0013):** sitting-height sill decided — accepted
  single-layer trade (SF1 is the sole fall defense; ~500 mm residual). To do: confirm the sill height
  + forgiving drop-zone against local code, obtain a named risk-acceptance sign-off, and
  add a commissioning acceptance check.
- **SF4 fail-open drive (ADR-0009):** first-order check (`pin_relief.py`) says passive
  relief is insufficient (~1.2 kN residual) → a ~1.5 kN return element is required (or
  a drag-shedding seal); add it to the drive concept and re-run actuator sizing (~2.3x
  closing force). Verify the rigid chain is back-drivable in the occupant zone; design
  the passive flush latch + fail-safe powered release; confirm the latch zone is
  provably past any occupant; confirm all numbers with real tissue/seal data.
