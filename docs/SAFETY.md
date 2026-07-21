# HiveCell — Safety (M8, living document)

Machine-safety analysis for a powered steel piston that moves through a space people
occupy. Method: identify hazards (ISO 12100 style), rate risk, assign safety
functions. Users are assumed VULNERABLE (may be intoxicated, unconscious, disabled,
asleep) and may NOT self-rescue.

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
| H4 | Fall from an elevated mouth | Occupant pushed out of a mouth above floor level | 3 | 2 | 6 | Site rule: mouth at floor level, or guarding; occupancy interlock upstream |
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
  "possibly occupied" => no motion. Target a rated performance level (e.g. ISO 13849
  PL d/e) — TBD on real hardware.
- **SF2 Contact reaction** — *[sim: force cap + safety-edge trip]* chain-drive
  current/force monitoring + pressure-sensitive safety edge on the piston face =>
  immediate stop and reverse to deployed. Independent of SF1. The trip is on YIELD,
  not resistance magnitude: movable trash stays bounded; a non-yielding body makes
  force climb steeply — that is what a cap below the injury threshold catches.
- **SF3 Gap elimination** — *[cad: gap-fill geometry + drag budget]* compliant
  wiper/brush seal fills the 3 mm so there is no open moving shear line (also serves
  hygiene + the seal-drag budget). Two lip rings on the piston perimeter; the
  COMPLIANCE (a finger/hair deflects the lip instead of being sheared) is a material
  property — asserted, not yet proven by test.
- **SF4 Fail-open drive** *(was: manual release + interior E-stop)* — *[decision:
  design-out, see FMEA]* power loss must not sustain a holding force; the drive fails
  OPEN / back-drivable so a mis-detected pin relieves passively — no lever, no
  occupant-operated release device. An accessible release was rejected: it is a
  vandalism/abuse surface in unattended public units, and the sealed-in trap is
  already removed by geometry (the piston always sweeps toward the open mouth, never
  enclosing the occupant). Fail behavior is position-dependent: back-drivable in the
  occupant zone (pin relief), a passive latch holds the flush end without power (stays
  closed, no occupant can be there). See **ADR-0009**.
- **SF5 Motion signalling + soft profile** — *[todo]* warning (light/sound) before and
  during motion; slow soft-start/stop; reduced final-approach speed.

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
and downstream). KEY RISK: SF3 seal drag (~1.2 kN) may exceed a pinned occupant's
elastic reaction, so back-drivability alone may not relieve a pin — may need a
stored-energy return element (verify). Retained, not occupant-facing: an EXTERNAL /
operator E-stop + remote tamper/fault monitoring (availability, not a trap function).

## Implementation status (digital twin)
The safety *logic* has a reference implementation in the Godot twin. It models
behaviour and is regression-checked; it is NOT rated hardware and makes no
performance-level (PL) claim.

- `godot/safety_interlock.gd` — the interlock state machine. SF1 and SF2 are two
  independent trips. SF1 = fail-safe OR across (simulated) diverse life-detection
  channels (radar vitals, thermal, CO₂, load-cell BCG); any channel, or any sensor
  fault, => "occupied" => no motion. SF2 = contact force over a safe cap
  (`SAFE_CONTACT_N` = 120 N, below the ~150 N powered-door limit). Either trip stops
  and reverses a sweep, reversing from the current position; a sweep never starts
  while either trip is active.
- `godot/tests/test_interlock.gd` — headless self-test enforcing the invariant "the
  sweep never advances while a safety trip is active", across: empty+clear, occupied,
  mid-sweep intrusion (SF1), sensor-fault fail-safe, and SF1-blind / SF2-catches.
  Runs on every push via `.githooks/pre-push`.
- `godot/physics_demo.gd` — physics scenarios (default Play scene). The drive-load
  model demonstrates yield-vs-magnitude: a 10-item trash pile peaks ~63 N (bounded,
  yields) while a non-yielding body spikes to ~138 N and trips SF2. Includes the
  SENSOR BLIND case where SF1 misses the occupant and SF2 alone catches the contact.
- `scripts/build_model.py` — the wiper seals (SF3): two lip rings on the piston
  perimeter filling the 3 mm gap, verified to touch the bore and hug the piston
  (~0 overlap). `scripts/actuator_sizing.py` budgets their drag: 2 lips × ~4 m
  perimeter @ 150 N/m ⇒ ~1190 N, the dominant load (design force ~2411 N, ×2 factor).
  Exported to both twins as `WiperSeals.obj`, riding with the piston.

Addressed in sim: H1/H6 by SF1 (+ fail-safe), H3/H5/H8 contact behaviour by SF2,
H2 gap-fill *geometry* by SF3 (compliance TBV). Unaddressed: H4 (mouth height),
H7 (manual release/SF4).

## Open items
- **SF1 real sensing:** the voting *logic* exists in sim, but the physical sensor
  suite, redundancy architecture, and PL rating do not. Select modalities (must catch
  a still/cold/blanketed occupant and small animals) and target ISO 13849 PL d/e.
- **SF2 real force limit:** sim shows a force-limited drive with a cap below the door
  limit is a viable backstop (discriminates yield vs magnitude). Real cap must come
  from injury data + the drive's *actual* force-limitability; SF1 remains primary
  either way (force alone cannot be trusted if a heavy jam can exceed the cap).
- **SF3 lip material + compliance:** geometry + drag budget exist; still need to
  select the elastomer/brush and PROVE a finger/hair deflects rather than shears,
  and validate the 150 N/m drag assumption by test (it dominates the actuator sizing).
- Mouth height / site guarding rules (facility-level) — H4.
- **SF4 fail-open drive (ADR-0009):** verify the rigid chain is back-drivable in the
  occupant zone; verify a pin actually relieves passively despite ~1.2 kN seal drag
  (else add a stored-energy return element); design the passive flush latch + its
  fail-safe powered release; confirm the latch zone is provably past any occupant.
