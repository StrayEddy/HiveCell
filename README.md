# HiveCell

Modular public sleeping infrastructure. Each cell is a recessed cavity in a large
wall that provides one clean, safe overnight sleeping space. When unavailable, the
cavity retracts into the wall until the public face is flush, moving the sleeping
surface into a hidden service area for automated cleaning.

Design priorities (in order): vandal resistance, hygiene, reliability, low
maintenance, low energy, low cost, simplicity, easy servicing, long lifetime.
Comfort is intentionally low priority.

## Mechanism

**True syringe (Option B):** a single piston moves inside a fixed tube (barrel).
Retracted, the piston is the floor/back of an open sleeping capsule. Advanced, its
own face becomes the flush public wall — no separate door. The sweep of the piston
performs cleaning and seals the cavity on the hidden service side.

## Safety status

This machine moves a powered steel piston through a space people occupy, and users are
assumed VULNERABLE (asleep, intoxicated, unwell) and unable to self-rescue — so safety
is the first design constraint, not a feature. Full analysis in
[`docs/SAFETY.md`](docs/SAFETY.md) (hazards, FMEA, safety functions); decisions in
[`docs/DECISIONS.md`](docs/DECISIONS.md).

Current state — **design + simulation / first-order analysis, no certified hardware yet:**

| Safety function | Status |
|-----------------|--------|
| SF1 Occupancy detection (primary) | fail-safe voting logic in the twin + self-test — `[sim]` |
| SF2 Contact-force reaction (safety edge) | independent force-cap trip in the twin + self-test — `[sim]` |
| SF3 Gap-filling wiper seal | CAD geometry + drag budget; low friction now required (ADR-0011) — `[cad]` |
| SF4 Fail-open drive (no occupant release) | decided: back-drivable + passive flush latch (ADR-0009) — `[decision]` |
| SF5 Motion signalling + soft profile | not started |

The SF1+SF2 interlock is a shared, headless-testable state machine; its core invariant
— *the sweep never advances while a safety trip is active* — is enforced by a self-test
that gates every push (see Setup). The design principle is PREVENT (never move while
occupied) → REACT (stop & reverse on contact) → fail safe; "push the occupant out" is
not a mode the machine can enter.

**Biggest open risk:** seal drag is the master variable — it couples the seal (SF3), the
SF4 return spring, and the actuator size, yet is currently only estimated (~16–700 N/m).
It must be measured on a real seal sample before the force numbers are frozen (ADR-0011).

## Software stack

| Tool     | Role                                    |
|----------|-----------------------------------------|
| FreeCAD  | Mechanical design (parametric, source of truth) |
| Godot    | Motion simulation & digital twin        |
| Blender  | Rendering & presentation (later only)   |
| Git      | Version control                         |

## Layout

- `cad/`     — FreeCAD models (parametric)
- `docs/`    — engineering notes, calculations
- `godot/`   — simulation / digital twin project
- `blender/` — rendering assets (later)
- `docs/DECISIONS.md` — engineering decision log (read this first)
- `docs/SAFETY.md`   — machine-safety analysis (hazards + safety functions)

## Setup

The piston retracts into a space people occupy, so its motion is gated behind a
life-detection interlock (`godot/safety_interlock.gd`, per `docs/SAFETY.md`). A
headless self-test enforces the core invariant — the clearing sweep never
advances while life is detected — and a pre-push hook blocks pushes if it fails.

After cloning, enable the hook once (it lives in `.githooks/`, but `git` must be
pointed at it):

```sh
git config core.hooksPath .githooks
```

Run the self-tests manually anytime (set `GODOT_BIN` if Godot isn't on `PATH`):

```sh
./scripts/run_selftest.sh
```
