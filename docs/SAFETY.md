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

## Safety functions (to design)
- **SF1 Occupancy detection (primary):** redundant + diverse sensors (e.g. load/weight
  in the floor + optical/IR beam + capacitive/radar). Fault or "possibly occupied" =>
  no retraction. Target a rated performance level (e.g. ISO 13849 PL d/e) — TBD.
- **SF2 Contact reaction:** chain-drive current/force monitoring + pressure-sensitive
  safety edge on the piston face => immediate stop and reverse to deployed.
- **SF3 Gap elimination:** compliant wiper/brush seal fills the 3 mm so there is no
  open moving shear line (also serves hygiene + the seal-drag budget).
- **SF4 Manual release + interior E-stop:** a trapped person can stop and free
  themselves without power or tools.
- **SF5 Motion signalling + soft profile:** warning (light/sound) before and during
  motion; slow soft-start/stop; reduced final-approach speed.

## Open items
- Occupancy sensing technology + redundancy architecture and performance level.
- Force/speed limits vs. recognised powered-door limits (~150 N) — is our drive
  force-limitable to a safe contact force, or do we rely on presence detection alone?
- Mouth height / site guarding rules (facility-level).
- E-stop + manual release mechanism reachable from inside a confined capsule.
