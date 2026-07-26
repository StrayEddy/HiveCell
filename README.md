# HiveCell

**🌐 Project site & demo video: [strayeddy.github.io/HiveCell](https://strayeddy.github.io/HiveCell/)**

> **Open-source hardware research — uncertified, not a deployable product.**
> HiveCell moves a powered steel piston through a space a person occupies. It is
> **design and simulation only**: no built hardware, no physical validation, no
> safety certification. **Do not build this to put a person inside it.** See
> [`LICENSE`](LICENSE) for the full safety notice and licensing.

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
| SF1 Occupancy detection (primary) | fail-safe voting logic + self-test; architecture decided — diverse-redundant suite (radar vitals + thermal + CO₂ + load/BCG), target ISO 13849 PL e (ADR-0012) — `[sim]` |
| SF2 Contact-force reaction (safety edge) | independent force-cap trip in the twin + self-test — `[sim]` |
| SF3 Gap-filling wiper seal | CAD geometry + drag budget; low friction now required (ADR-0011) — `[cad]` |
| SF4 Fail-open drive (no occupant release) | decided: back-drivable + passive flush latch + ~1.5 kN return spring (ADR-0009; required per the pin-relief check) — `[decision]` |
| SF5 Motion signalling + soft profile | soft velocity profile + signalling (green ready / red moving / orange closed / flashing-red alarm) in the twin + self-test — `[sim]` |

The SF1+SF2 interlock is a shared, headless-testable state machine; its core invariant
— *the sweep never advances while a safety trip is active* — is enforced by a self-test
that gates every push (see Setup). The design principle is PREVENT (never move while
occupied) → REACT (stop & reverse on contact) → fail safe; "push the occupant out" is
not a mode the machine can enter.

**Notable decisions** (full rationale in `docs/DECISIONS.md`): the fail-open + return-spring
requirements challenge the original rigid-chain actuator, so the **drive architecture is
under review** (ADR-0010, *proposed*). H4 (fall from the mouth) is a **documented
accepted-risk trade** — a sitting-height sill for object-clearing leaves fall protection
resting on SF1 alone (ADR-0013); recorded transparently, with the safer alternative noted.

**Biggest open risk:** seal drag is the master variable — it couples the seal (SF3), the
SF4 return spring, and the actuator size, yet is currently only estimated (~16–700 N/m).
It must be measured on a real seal sample before the force numbers are frozen (ADR-0011).
A ~$200 bench procedure to do exactly that — the highest-value next experiment, and a
great first contribution — is in [`docs/seal_drag_bench_test.md`](docs/seal_drag_bench_test.md).

Everything above is design/simulation and first-order analysis. Real progress from here
is physical-world validation: bench-measure seal drag, prototype the SF1 radar, and build
the certification dossiers (ISO 13849 PL e for SF1; force/injury data for SF2).

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
- `docs/ROADMAP.md`  — prioritized roadmap, indexing the [GitHub Issues](https://github.com/StrayEddy/HiveCell/issues)

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

## License & contributing

HiveCell is open-source, licensed by file type so each part uses the right license
for its medium:

- **Hardware** (`cad/`, `blender/`, `renders/`) — CERN-OHL-S-2.0 (strongly reciprocal)
- **Documentation** (`docs/`, this README) — CC-BY-4.0
- **Software** (`godot/`, `scripts/`) — Apache-2.0

You may use, modify, and redistribute — including commercially — with attribution;
hardware derivatives must stay open under the same terms. Full texts are in
[`LICENSES/`](LICENSES/); the scheme and the **safety notice** are in
[`LICENSE`](LICENSE).

Some cinematic cast motion is derived from [Mixamo](https://www.mixamo.com/)
animations, used under Adobe's royalty-free terms; those source clips are **not**
redistributed here (they stay out of git) — re-fetch and re-bake via
`blender/retarget_mixamo.py`.

Contributions are welcome — see
[`CONTRIBUTING.md`](CONTRIBUTING.md); the most valuable one right now is a real
bench measurement of seal drag (ADR-0011).
