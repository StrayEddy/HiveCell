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
| H7 | Trapped under self-locking hold | Someone caught; drive is self-locking, power lost | 4 | 1 | 4 | Manual mechanical release + interior E-stop, reachable by a trapped person |
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
- **SF3 Gap elimination** — *[todo]* compliant wiper/brush seal fills the 3 mm so
  there is no open moving shear line (also serves hygiene + the seal-drag budget).
- **SF4 Manual release + interior E-stop** — *[todo]* a trapped person can stop and
  free themselves without power or tools.
- **SF5 Motion signalling + soft profile** — *[todo]* warning (light/sound) before and
  during motion; slow soft-start/stop; reduced final-approach speed.

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

Addressed in sim: H1/H6 by SF1 (+ fail-safe), H3/H5/H8 contact behaviour by SF2.
Unaddressed: H2 (gap/SF3), H4 (mouth height), H7 (manual release/SF4).

## Open items
- **SF1 real sensing:** the voting *logic* exists in sim, but the physical sensor
  suite, redundancy architecture, and PL rating do not. Select modalities (must catch
  a still/cold/blanketed occupant and small animals) and target ISO 13849 PL d/e.
- **SF2 real force limit:** sim shows a force-limited drive with a cap below the door
  limit is a viable backstop (discriminates yield vs magnitude). Real cap must come
  from injury data + the drive's *actual* force-limitability; SF1 remains primary
  either way (force alone cannot be trusted if a heavy jam can exceed the cap).
- Mouth height / site guarding rules (facility-level) — H4.
- SF4: E-stop + manual release mechanism reachable from inside a confined capsule.
- SF3: wiper/brush seal design + seal-drag budget.
